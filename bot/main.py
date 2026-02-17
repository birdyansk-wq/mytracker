"""
Точка входа. Telegram-бот для ежедневного трекера привычек.
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from .config import BOT_TOKEN, ALLOWED_USER_ID, ALCOHOL_COST_PER_EPISODE, WEEKLY_ALCOHOL_BUDGET, WEBAPP_URL, BOT_USERNAME
from .database import (
    init_db,
    get_or_create_today,
    update_field,
    get_week_stats,
    get_all_questions_numbered,
    update_question_text,
    update_question_options,
    get_options_for_field,
    add_test_data,
    get_questions,
    add_weekly_goals,
    get_weekly_goals,
    toggle_goal_completion,
    get_incomplete_goals,
    move_goals_to_next_week,
    add_monthly_goals,
    get_monthly_goals,
    toggle_monthly_goal_completion,
    get_incomplete_monthly_goals,
    move_monthly_goals_to_next_month,
    get_monthly_stats,
    is_last_day_of_month,
    add_daily_goals,
    get_daily_goals,
    toggle_daily_goal_completion,
    is_onboarding_completed,
    set_onboarding_completed,
    reset_all_data,
)
from .questions import (
    get_question_data,
    get_total_questions,
    get_inline_keyboard,
    parse_callback_data,
)
from .scheduler import setup_jobs

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Состояние опроса: {user_id: {"type": "morning"|"evening", "index": int}}
survey_state = {}
# Состояние редактирования: {user_id: {"action": "edit_text"|"edit_opts", "question_id": int}}
edit_mode = {}
# Тестовый режим: {user_id: {"days_left": int, "current_day": int}}
test_mode = {}
# Состояние ввода целей на неделю: {user_id: True}
weekly_goals_input = {}
# Состояние ввода целей на месяц: {user_id: True}
monthly_goals_input = {}
# Состояние ввода дневных целей: {user_id: True}
daily_goals_input = {}


def is_allowed_user(user_id: int) -> bool:
    """Проверка, что пользователь — разрешённый."""
    return user_id == ALLOWED_USER_ID


async def send_question(chat_id: int, survey_type: str, index: int, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет вопрос по индексу. Сохраняет message_id в survey_state для последующего удаления.
    
    В выходные все вопросы задаются как обычно.
    """
    q = get_question_data(survey_type, index)
    if not q:
        return None
    
    keyboard = get_inline_keyboard(q["field_name"], q["options"]) if q["has_keyboard"] else None
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=q["text"],
        reply_markup=keyboard,
    )
    if chat_id in survey_state:
        survey_state[chat_id]["last_msg_id"] = msg.message_id
    return msg


async def morning_survey(context: ContextTypes.DEFAULT_TYPE):
    """Запуск утреннего опроса в 9:00 по Красноярску.
    
    Сначала спрашивает дневные цели.
    Первого числа месяца добавляет вопрос про цели на месяц.
    По понедельникам добавляет вопрос про цели на неделю.
    """
    if not is_allowed_user(ALLOWED_USER_ID):
        return
    
    # Всегда спрашиваем дневные цели в начале дня
    daily_goals_input[ALLOWED_USER_ID] = True
    await context.bot.send_message(
        ALLOWED_USER_ID,
        "☀️ Доброе утро! Какие задачи на сегодня?\n\nНапиши список (каждая с новой строки):"
    )


async def evening_survey(context: ContextTypes.DEFAULT_TYPE):
    """Запуск вечернего опроса в 21:00 по Красноярску."""
    if not is_allowed_user(ALLOWED_USER_ID):
        return
    survey_state[ALLOWED_USER_ID] = {"type": "evening", "index": 0}
    await send_question(ALLOWED_USER_ID, "evening", 0, context)


async def weekly_summary(context: ContextTypes.DEFAULT_TYPE):
    """Недельная сводка по воскресеньям в 14:00."""
    if not is_allowed_user(ALLOWED_USER_ID):
        return
    stats = get_week_stats()
    
    episodes = stats['days_with_alcohol']
    tasks_done = int(stats['avg_deep_work'] * stats['total_days'])
    
    # Финансовая бухгалтерия
    plan = WEEKLY_ALCOHOL_BUDGET
    fact = episodes * ALCOHOL_COST_PER_EPISODE
    difference = plan - fact
    
    text = f"📊 Недельная сводка\n\n"
    text += f"Главных задач выполнено: {tasks_done} из {stats['total_days']}\n"
    text += f"Средняя энергия: {stats['avg_energy']}\n\n"
    
    text += f"📊 Алкоголь за неделю:\n"
    text += f"План: {plan:,} ₽\n"
    text += f"Факт: {fact:,} ₽\n"
    text += f"Эпизодов: {episodes}\n\n"
    
    if difference > 0:
        text += f"💰 Экономия: +{difference:,} ₽"
    elif difference < 0:
        text += f"⚠️ Перерасход: {abs(difference):,} ₽"
    else:
        text += "✅ По плану"
    
    await context.bot.send_message(ALLOWED_USER_ID, text)


async def friday_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Проверка целей в пятницу вечером."""
    if not is_allowed_user(ALLOWED_USER_ID):
        return
    
    goals = get_weekly_goals()
    if not goals:
        # Если целей нет, отправляем обычное напоминание
        text = "🎯 Отличная неделя! Отдыхай на выходных! 🏖"
        await context.bot.send_message(ALLOWED_USER_ID, text)
        return
    
    completed = [g for g in goals if g["is_completed"] == 1]
    incomplete = [g for g in goals if g["is_completed"] == 0]
    
    if not incomplete:
        # Все задачи выполнены
        text = "🔥 РЕСПЕКТ! 🔥\n\n"
        text += f"Все {len(goals)} целей выполнены!\n\n"
        text += "Отличная неделя, отдыхай на выходных! 🏖"
        await context.bot.send_message(ALLOWED_USER_ID, text)
    else:
        # Есть невыполненные задачи
        text = f"📊 Итоги недели:\n\n"
        text += f"✅ Выполнено: {len(completed)} из {len(goals)}\n"
        text += f"⏳ Осталось: {len(incomplete)}\n\n"
        text += "Невыполненные задачи:\n"
        for g in incomplete:
            text += f"• {g['task_text']}\n"
        
        # Кнопка для переноса
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Перенести на следующую неделю", callback_data="move_goals")]
        ])
        await context.bot.send_message(ALLOWED_USER_ID, text, reply_markup=keyboard)


async def end_of_month_check(context: ContextTypes.DEFAULT_TYPE):
    """Проверка месячных целей в последний день месяца."""
    if not is_allowed_user(ALLOWED_USER_ID):
        return
    
    # Проверяем, что сегодня последний день месяца
    if not is_last_day_of_month():
        return
    
    goals = get_monthly_goals()
    if not goals:
        # Если целей нет, ничего не отправляем
        return
    
    completed = [g for g in goals if g["is_completed"] == 1]
    incomplete = [g for g in goals if g["is_completed"] == 0]
    
    if not incomplete:
        # Все задачи выполнены
        text = "🔥 РЕСПЕКТ! 🔥\n\n"
        text += f"Все {len(goals)} месячных целей выполнены!\n\n"
        text += "Отличный месяц! 🎉"
        await context.bot.send_message(ALLOWED_USER_ID, text)
    else:
        # Есть невыполненные задачи
        text = f"📊 Итоги месяца:\n\n"
        text += f"✅ Выполнено: {len(completed)} из {len(goals)}\n"
        text += f"⏳ Осталось: {len(incomplete)}\n\n"
        text += "Невыполненные задачи:\n"
        for g in incomplete:
            text += f"• {g['task_text']}\n"
        
        # Кнопка для переноса
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Перенести на следующий месяц", callback_data="move_monthly_goals")]
        ])
        await context.bot.send_message(ALLOWED_USER_ID, text, reply_markup=keyboard)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых ответов (wake_time, daily/weekly/monthly goals).
    После ответа: удаляем вопрос, сохраняем в БД, показываем следующий или завершаем."""
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    
    # Проверяем режим ввода дневных целей
    if user_id in daily_goals_input:
        text = update.message.text.strip()
        tasks = [line.strip() for line in text.split('\n') if line.strip()]
        if tasks:
            add_daily_goals(tasks)
            await update.message.reply_text(f"✅ Добавлено задач на сегодня: {len(tasks)}")
        del daily_goals_input[user_id]
        
        # Проверяем, это онбординг или обычное утро
        if not is_onboarding_completed():
            # Онбординг - продолжаем настройку целей
            await continue_onboarding_weekly(update, context)
        else:
            # Обычное утро - проверяем, нужно ли спросить недельные/месячные цели
            today = datetime.now()
            is_monday = today.weekday() == 0
            is_first_of_month = today.day == 1
            
            if is_first_of_month:
                monthly_goals_input[user_id] = True
                await context.bot.send_message(
                    user_id,
                    "🗓 Какие цели на месяц?\n\nНапиши список задач (каждая с новой строки):"
                )
            elif is_monday:
                weekly_goals_input[user_id] = True
                await context.bot.send_message(
                    user_id,
                    "📋 Какие цели на неделю?\n\nНапиши список задач (каждая с новой строки):"
                )
            else:
                # Запускаем обычный утренний опрос
                survey_state[user_id] = {"type": "morning", "index": 0}
                await send_question(user_id, "morning", 0, context)
        return
    
    # Проверяем режим ввода месячных целей
    if user_id in monthly_goals_input:
        text = update.message.text.strip()
        tasks = [line.strip() for line in text.split('\n') if line.strip()]
        if tasks:
            add_monthly_goals(tasks)
            await update.message.reply_text(f"✅ Добавлено месячных целей: {len(tasks)}")
        del monthly_goals_input[user_id]
        
        # Проверяем, это онбординг или обычное утро
        if not is_onboarding_completed():
            # Онбординг завершён!
            set_onboarding_completed()

            # Кнопка Mini App, если настроен
            reply_markup = None
            if WEBAPP_URL and BOT_USERNAME:
                app_url = f"{WEBAPP_URL.rstrip('/')}?bot={BOT_USERNAME}"
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Открыть меню", web_app=WebAppInfo(url=app_url))]
                ])

            await update.message.reply_text(
                "🎉 **Отлично! Настройка завершена.**\n\n"
                "Теперь запускаю утренний опрос...\n\n"
                "💡 Меню с командами и расписанием — в кнопке **«Открыть»** рядом с полем ввода (или в Mini App).",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            # Запускаем утренний опрос
            survey_state[user_id] = {"type": "morning", "index": 0}
            await send_question(user_id, "morning", 0, context)
        else:
            # Обычное утро (первое число, но не онбординг)
            # Проверяем, не понедельник ли (нужно спросить недельные цели)
            is_monday = datetime.now().weekday() == 0
            if is_monday:
                weekly_goals_input[user_id] = True
                await context.bot.send_message(
                    user_id,
                    "📋 Какие цели на неделю?\n\nНапиши список задач (каждая с новой строки):"
                )
            else:
                # Запускаем обычный утренний опрос
                survey_state[user_id] = {"type": "morning", "index": 0}
                await send_question(user_id, "morning", 0, context)
        return
    
    # Проверяем режим ввода целей на неделю
    if user_id in weekly_goals_input:
        text = update.message.text.strip()
        tasks = [line.strip() for line in text.split('\n') if line.strip()]
        if tasks:
            add_weekly_goals(tasks)
            await update.message.reply_text(f"✅ Добавлено недельных целей: {len(tasks)}")
        del weekly_goals_input[user_id]
        
        # Проверяем, это онбординг или обычное утро
        if not is_onboarding_completed():
            # Онбординг - продолжаем с месячными целями
            await continue_onboarding_monthly(update, context)
        else:
            # Обычное утро - запускаем утренний опрос
            survey_state[user_id] = {"type": "morning", "index": 0}
            await send_question(user_id, "morning", 0, context)
        return
    
    # Проверяем режим редактирования
    if user_id in edit_mode:
        mode = edit_mode[user_id]
        text = update.message.text.strip()
        q_id = mode["question_id"]
        
        if mode["action"] == "edit_text":
            update_question_text(q_id, text)
            del edit_mode[user_id]
            await update.message.reply_text("✅ Текст вопроса обновлён!")
        elif mode["action"] == "edit_opts":
            update_question_options(q_id, text)
            del edit_mode[user_id]
            await update.message.reply_text("✅ Варианты обновлены!")
        return
    
    if user_id not in survey_state:
        return

    state = survey_state[user_id]
    survey_type = state["type"]
    index = state["index"]
    q = get_question_data(survey_type, index)
    if not q:
        return
    field = q["field_name"]
    text = update.message.text.strip()

    # Удаляем сообщение с вопросом (предыдущее)
    last_msg_id = state.get("last_msg_id")
    if last_msg_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except Exception:
            pass

    # Сохраняем ответ
    if field == "wake_time":
        update_field("wake_time", text)
    # main_task removed - now using daily_goals

    # Удаляем ответ пользователя
    await update.message.delete()

    # Следующий вопрос или конец
    state["index"] += 1
    total = get_total_questions(survey_type)
    if state["index"] < total:
        await send_question(user_id, survey_type, state["index"], context)
    else:
        del survey_state[user_id]
        
        # Проверяем тестовый режим
        if user_id in test_mode:
            test_state = test_mode[user_id]
            
            if survey_type == "morning":
                # После утреннего опроса — показываем /today и запускаем вечерний
                await context.bot.send_message(user_id, "✅ Утренний опрос завершён!\n\nТвои ответы:")
                row = get_or_create_today()
                await context.bot.send_message(
                    user_id,
                    f"🌅 Утро:\n"
                    f"Проснулся: {row['wake_time']}\n"
                    f"Алкоголь вчера: {'Да' if row['alcohol'] == 1 else 'Нет' if row['alcohol'] == 0 else '—'}"
                )
                await context.bot.send_message(user_id, "Переходим к вечернему опросу! 🌙")
                survey_state[user_id] = {"type": "evening", "index": 0}
                await send_question(user_id, "evening", 0, context)
            else:
                # После вечернего опроса — показываем полный /today
                await context.bot.send_message(user_id, "✅ Вечерний опрос завершён!")
                
                # Показываем /today
                row = get_or_create_today()
                task_opts = get_options_for_field("deep_work_minutes")
                walk_opts = get_options_for_field("walk")
                task_label = task_opts[0] if row["deep_work_minutes"] == 1 else task_opts[1]
                walk_label = walk_opts[0] if row["walk"] == 1 else walk_opts[1]
                
                await context.bot.send_message(
                    user_id,
                    f"📊 День {test_state['current_day']} завершён!\n\n"
                    f"🌅 Утро:\n"
                    f"• Проснулся: {row['wake_time']}\n"
                    f"• Алкоголь вчера: {'Да' if row['alcohol'] == 1 else 'Нет'}\n\n"
                    f"🌙 Вечер:\n"
                    f"• Выполнил задачу: {task_label}\n"
                    f"• Прогулка: {walk_label}\n"
                    f"• Энергия: {row['energy']}"
                )
                
                # Проверяем, есть ли ещё дни
                test_state["days_left"] -= 1
                test_state["current_day"] += 1
                
                if test_state["days_left"] > 0:
                    await context.bot.send_message(
                        user_id,
                        f"\n➡️ День {test_state['current_day']} из {test_state['total_days']}\n"
                        "Начинаем утренний опрос! 🌅"
                    )
                    survey_state[user_id] = {"type": "morning", "index": 0}
                    await send_question(user_id, "morning", 0, context)
                else:
                    # Тест завершён — показываем всю статистику
                    del test_mode[user_id]
                    
                    stats = get_week_stats()
                    days_with = stats['days_with_alcohol']
                    tasks_done = int(stats['avg_deep_work'] * stats['total_days'])
                    
                    await context.bot.send_message(
                        user_id,
                        f"🎉 Тест завершён!\n\n"
                        f"📊 Статистика за {test_state['total_days']} дней:\n\n"
                        f"🍺 Алкоголь: {days_with} раз\n"
                        f"✅ Задач выполнено: {tasks_done} из {stats['total_days']}\n"
                        f"⚡ Средняя энергия: {stats['avg_energy']}\n\n"
                    )
                    
                    # Показываем финансы
                    if days_with == 0:
                        saved = 2.5 * ALCOHOL_COST
                        await context.bot.send_message(
                            user_id,
                            f"💰 Ты заработал ~{saved:,.0f} ₽!\n"
                            "Ни разу не пил — отлично! 🔥"
                        )
                    elif days_with <= 2:
                        spent = days_with * ALCOHOL_COST
                        await context.bot.send_message(
                            user_id,
                            f"💸 Потрачено: {spent:,} ₽\n"
                            "В пределах нормы"
                        )
                    else:
                        spent = days_with * ALCOHOL_COST
                        await context.bot.send_message(
                            user_id,
                            f"💸 Потрачено: {spent:,} ₽\n"
                            "⚠️ Больше обычного"
                        )
        else:
            await context.bot.send_message(user_id, "Опрос завершён. Спасибо!")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий inline-кнопок (alcohol, walk, energy + редактирование вопросов + цели).
    Конвертируем Да/Нет в 0/1 для БД."""
    user_id = update.callback_query.from_user.id
    if not is_allowed_user(user_id):
        return
    
    query = update.callback_query
    data = query.data
    
    # Обработка чекбоксов дневных целей
    if data.startswith("dgoal_"):
        goal_id = int(data.split("_")[1])
        toggle_daily_goal_completion(goal_id)
        await query.answer("Статус обновлён!")
        
        # Обновляем сообщение с новыми чекбоксами
        goals = get_daily_goals()
        completed_count = sum(1 for g in goals if g["is_completed"] == 1)
        text = f"☀️ Задачи на сегодня ({completed_count}/{len(goals)})\n\n"
        
        buttons = []
        for g in goals:
            checkbox = "☑️" if g["is_completed"] == 1 else "☐"
            text += f"{checkbox} {g['task_text']}\n"
            buttons.append([InlineKeyboardButton(
                f"{checkbox} {g['task_text'][:40]}{'...' if len(g['task_text']) > 40 else ''}",
                callback_data=f"dgoal_{g['id']}"
            )])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # Проверяем, все ли выполнены (и отправляем респект)
        if completed_count == len(goals) and completed_count > 0:
            all_done = all(g["is_completed"] == 1 for g in goals)
            if all_done:
                await context.bot.send_message(user_id, "🔥 РЕСПЕКТ! 🔥\n\nВсе задачи на сегодня выполнены!")
        return
    
    # Обработка чекбоксов целей
    if data.startswith("goal_"):
        goal_id = int(data.split("_")[1])
        toggle_goal_completion(goal_id)
        await query.answer("Статус обновлён!")
        
        # Обновляем сообщение с новыми чекбоксами
        goals = get_weekly_goals()
        completed_count = sum(1 for g in goals if g["is_completed"] == 1)
        text = f"📋 Цели на неделю ({completed_count}/{len(goals)})\n\n"
        
        buttons = []
        for g in goals:
            checkbox = "☑️" if g["is_completed"] == 1 else "☐"
            text += f"{checkbox} {g['task_text']}\n"
            buttons.append([InlineKeyboardButton(
                f"{checkbox} {g['task_text'][:40]}{'...' if len(g['task_text']) > 40 else ''}",
                callback_data=f"goal_{g['id']}"
            )])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # Проверяем, все ли выполнены (и отправляем респект)
        if completed_count == len(goals) and completed_count > 0:
            all_done = all(g["is_completed"] == 1 for g in goals)
            if all_done:
                await context.bot.send_message(user_id, "🔥 РЕСПЕКТ! 🔥\n\nВсе цели выполнены!")
        return
    
    # Обработка переноса целей
    if data == "move_goals":
        incomplete = get_incomplete_goals()
        if incomplete:
            goal_ids = [g["id"] for g in incomplete]
            move_goals_to_next_week(goal_ids)
            await query.answer("Задачи перенесены!")
            await query.edit_message_text(
                f"✅ Перенесено {len(incomplete)} задач на следующую неделю.\n\n"
                "Отдыхай на выходных! 🏖"
            )
        else:
            await query.answer("Нет задач для переноса")
        return
    
    # Обработка чекбоксов месячных целей
    if data.startswith("mgoal_"):
        goal_id = int(data.split("_")[1])
        toggle_monthly_goal_completion(goal_id)
        await query.answer("Статус обновлён!")
        
        # Обновляем сообщение с новыми чекбоксами
        goals = get_monthly_goals()
        completed_count = sum(1 for g in goals if g["is_completed"] == 1)
        text = f"🗓 Цели на месяц ({completed_count}/{len(goals)})\n\n"
        
        buttons = []
        for g in goals:
            checkbox = "☑️" if g["is_completed"] == 1 else "☐"
            text += f"{checkbox} {g['task_text']}\n"
            buttons.append([InlineKeyboardButton(
                f"{checkbox} {g['task_text'][:40]}{'...' if len(g['task_text']) > 40 else ''}",
                callback_data=f"mgoal_{g['id']}"
            )])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, reply_markup=keyboard)
        
        # Проверяем, все ли выполнены (и отправляем респект)
        if completed_count == len(goals) and completed_count > 0:
            all_done = all(g["is_completed"] == 1 for g in goals)
            if all_done:
                await context.bot.send_message(user_id, "🔥 РЕСПЕКТ! 🔥\n\nВсе месячные цели выполнены!")
        return
    
    # Обработка переноса месячных целей
    if data == "move_monthly_goals":
        incomplete = get_incomplete_monthly_goals()
        if incomplete:
            goal_ids = [g["id"] for g in incomplete]
            move_monthly_goals_to_next_month(goal_ids)
            await query.answer("Задачи перенесены!")
            await query.edit_message_text(
                f"✅ Перенесено {len(incomplete)} задач на следующий месяц."
            )
        else:
            await query.answer("Нет задач для переноса")
        return
    
    # Обработка сброса данных
    if data == "confirm_reset":
        reset_all_data()
        await query.answer("Все данные удалены")
        await query.edit_message_text(
            "✅ Все данные удалены.\n\n"
            "Напиши /start чтобы начать заново."
        )
        return
    
    if data == "cancel_reset":
        await query.answer("Отменено")
        await query.edit_message_text("❌ Сброс отменён.")
        return
    
    # Обработка кнопок редактирования вопросов
    if data.startswith("editq_") or data.startswith("edittext_") or data.startswith("editopts_") or data == "back_to_questions":
        await handle_edit_question_callback(update, context)
        return
    
    if user_id not in survey_state:
        await query.answer()
        return

    await query.answer()
    field, value = parse_callback_data(data)

    state = survey_state[user_id]
    survey_type = state["type"]
    index = state["index"]
    q = get_question_data(survey_type, index)
    if not q or field != q["field_name"]:
        return

    # Удаляем сообщение с вопросом
    try:
        await query.message.delete()
    except Exception:
        pass

    # Сохраняем в БД (первый вариант -> 1, второй -> 0 для alcohol/walk/deep_work; energy — число)
    if field == "alcohol":
        update_field("alcohol", 1 if value == q["options"][0] else 0)
    elif field == "walk":
        update_field("walk", 1 if value == q["options"][0] else 0)
    elif field == "deep_work_minutes":
        # Теперь это Да/Нет вместо минут
        update_field("deep_work_minutes", 1 if value == q["options"][0] else 0)
    elif field == "energy":
        update_field("energy", int(value))

    # Следующий вопрос или конец
    state["index"] += 1
    total = get_total_questions(survey_type)
    if state["index"] < total:
        await send_question(user_id, survey_type, state["index"], context)
    else:
        del survey_state[user_id]
        
        # Проверяем тестовый режим (для callback)
        if user_id in test_mode:
            test_state = test_mode[user_id]
            
            if survey_type == "morning":
                await context.bot.send_message(user_id, "✅ Утренний опрос завершён!\n\nПереходим к вечернему опросу! 🌙")
                survey_state[user_id] = {"type": "evening", "index": 0}
                await send_question(user_id, "evening", 0, context)
            # Вечерний опрос уже обработан в handle_text
        else:
            await context.bot.send_message(user_id, "Опрос завершён. Спасибо!")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /today — показывает ответы за сегодня."""
    if not is_allowed_user(update.effective_user.id):
        return
    row = get_or_create_today()
    alcohol_opts = get_options_for_field("alcohol")
    walk_opts = get_options_for_field("walk")
    
    alcohol_label = alcohol_opts[1] if row["alcohol"] == 0 else alcohol_opts[0] if row["alcohol"] == 1 else "—"
    walk_label = walk_opts[1] if row["walk"] == 0 else walk_opts[0] if row["walk"] == 1 else "—"
    
    lines = [
        f"📅 {row['date']}",
        f"Проснулся: {row['wake_time'] or '—'}",
        f"Алкоголь вчера: {alcohol_label}",
        f"Прогулка: {walk_label}",
        f"Энергия: {row['energy'] or '—'}",
    ]
    
    # Добавляем дневные цели
    daily_goals = get_daily_goals()
    if daily_goals:
        lines.append("")
        lines.append("☀️ Задачи на сегодня:")
        for g in daily_goals:
            checkbox = "☑️" if g["is_completed"] == 1 else "☐"
            lines.append(f"  {checkbox} {g['task_text']}")
    
    await update.message.reply_text("\n".join(lines))


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /week — статистика за 7 дней."""
    if not is_allowed_user(update.effective_user.id):
        return
    stats = get_week_stats()
    
    episodes = stats['days_with_alcohol']
    tasks_done = int(stats['avg_deep_work'] * stats['total_days'])
    
    # Финансовая бухгалтерия
    plan = WEEKLY_ALCOHOL_BUDGET
    fact = episodes * ALCOHOL_COST_PER_EPISODE
    difference = plan - fact
    
    text = f"📊 Статистика за 7 дней:\n\n"
    text += f"Главных задач выполнено: {tasks_done} из {stats['total_days']}\n"
    text += f"Средняя энергия: {stats['avg_energy']}\n\n"
    
    text += f"📊 Алкоголь за неделю:\n"
    text += f"План: {plan:,} ₽\n"
    text += f"Факт: {fact:,} ₽\n"
    text += f"Эпизодов: {episodes}\n\n"
    
    if difference > 0:
        text += f"💰 Экономия: +{difference:,} ₽"
    elif difference < 0:
        text += f"⚠️ Перерасход: {abs(difference):,} ₽"
    else:
        text += "✅ По плану"
    
    # Добавляем статистику по целям
    daily_goals = get_daily_goals()
    weekly_goals = get_weekly_goals()
    monthly_goals = get_monthly_goals()
    
    if daily_goals:
        d_completed = sum(1 for g in daily_goals if g["is_completed"] == 1)
        text += f"\n\n☀️ Задачи сегодня: {d_completed}/{len(daily_goals)}"
    
    if weekly_goals:
        w_completed = sum(1 for g in weekly_goals if g["is_completed"] == 1)
        text += f"\n📋 Цели недели: {w_completed}/{len(weekly_goals)}"
    
    if monthly_goals:
        m_completed = sum(1 for g in monthly_goals if g["is_completed"] == 1)
        text += f"\n🗓 Цели месяца: {m_completed}/{len(monthly_goals)}"
    
    await update.message.reply_text(text)


async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /goals — показывает цели на неделю с чекбоксами."""
    logger.info("cmd /goals")
    if not is_allowed_user(update.effective_user.id):
        return

    goals = get_weekly_goals()
    
    if not goals:
        await update.message.reply_text("📋 Нет целей на эту неделю.\n\nЦели добавляются автоматически по понедельникам.")
        return
    
    completed_count = sum(1 for g in goals if g["is_completed"] == 1)
    text = f"📋 Цели на неделю ({completed_count}/{len(goals)})\n\n"
    
    buttons = []
    for g in goals:
        checkbox = "☑️" if g["is_completed"] == 1 else "☐"
        text += f"{checkbox} {g['task_text']}\n"
        buttons.append([InlineKeyboardButton(
            f"{checkbox} {g['task_text'][:40]}{'...' if len(g['task_text']) > 40 else ''}",
            callback_data=f"goal_{g['id']}"
        )])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(text, reply_markup=keyboard)
    
    # Проверяем, все ли выполнены
    if completed_count == len(goals) and completed_count > 0:
        await update.message.reply_text("🔥 РЕСПЕКТ! 🔥\n\nВсе цели выполнены!")


async def cmd_month_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /month_goals — показывает цели на месяц с чекбоксами."""
    logger.info("cmd /month_goals")
    if not is_allowed_user(update.effective_user.id):
        return

    goals = get_monthly_goals()
    
    if not goals:
        await update.message.reply_text("🗓 Нет целей на этот месяц.\n\nЦели добавляются автоматически первого числа месяца.")
        return
    
    completed_count = sum(1 for g in goals if g["is_completed"] == 1)
    text = f"🗓 Цели на месяц ({completed_count}/{len(goals)})\n\n"
    
    buttons = []
    for g in goals:
        checkbox = "☑️" if g["is_completed"] == 1 else "☐"
        text += f"{checkbox} {g['task_text']}\n"
        buttons.append([InlineKeyboardButton(
            f"{checkbox} {g['task_text'][:40]}{'...' if len(g['task_text']) > 40 else ''}",
            callback_data=f"mgoal_{g['id']}"
        )])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(text, reply_markup=keyboard)
    
    # Проверяем, все ли выполнены
    if completed_count == len(goals) and completed_count > 0:
        await update.message.reply_text("🔥 РЕСПЕКТ! 🔥\n\nВсе месячные цели выполнены!")


async def cmd_today_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /today_goals — показывает задачи на сегодня с чекбоксами."""
    logger.info("cmd /today_goals")
    if not is_allowed_user(update.effective_user.id):
        return

    goals = get_daily_goals()
    
    if not goals:
        await update.message.reply_text("☀️ Нет задач на сегодня.\n\nЗадачи добавляются каждое утро.")
        return
    
    completed_count = sum(1 for g in goals if g["is_completed"] == 1)
    text = f"☀️ Задачи на сегодня ({completed_count}/{len(goals)})\n\n"
    
    buttons = []
    for g in goals:
        checkbox = "☑️" if g["is_completed"] == 1 else "☐"
        text += f"{checkbox} {g['task_text']}\n"
        buttons.append([InlineKeyboardButton(
            f"{checkbox} {g['task_text'][:40]}{'...' if len(g['task_text']) > 40 else ''}",
            callback_data=f"dgoal_{g['id']}"
        )])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(text, reply_markup=keyboard)
    
    # Проверяем, все ли выполнены
    if completed_count == len(goals) and completed_count > 0:
        await update.message.reply_text("🔥 РЕСПЕКТ! 🔥\n\nВсе задачи на сегодня выполнены!")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — онбординг, показ прогресса или переход из Mini App."""
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("Доступ запрещён.")
        return
    
    # Переход из Mini App: /start today, /start goals и т.д.
    start_param = context.args[0] if context.args else None
    if start_param and is_onboarding_completed():
        await handle_start_param(update, context, start_param)
        return
    
    # Проверяем, первый ли раз запускается бот
    if not is_onboarding_completed():
        # Онбординг - первый запуск
        await start_onboarding(update, context)
    else:
        # Показываем прогресс
        await show_progress(update, context)


async def handle_start_param(update: Update, context: ContextTypes.DEFAULT_TYPE, param: str):
    """Обработка перехода из Mini App — показываем соответствующие данные."""
    handlers = {
        "today": cmd_today,
        "today_goals": cmd_today_goals,
        "goals": cmd_goals,
        "month_goals": cmd_month_goals,
        "week": cmd_week,
        "questions": cmd_questions,
        "start": show_progress,
        "reset": cmd_reset,
    }
    handler = handlers.get(param)
    if handler:
        await handler(update, context)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает процесс первоначальной настройки."""
    user_id = update.effective_user.id
    
    today = datetime.now()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    month_names = ["января", "февраля", "марта", "апреля", "мая", "июня", 
                   "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    
    weekday = weekday_names[today.weekday()]
    date_str = f"{today.day} {month_names[today.month - 1]} {today.year}"
    
    await update.message.reply_text(
        f"👋 Привет! Я твой трекер привычек.\n\n"
        f"📅 Сегодня: {weekday}, {date_str}\n\n"
        f"Давай настроим твои цели, чтобы начать работу! 🚀"
    )
    
    # Начинаем с дневных целей
    daily_goals_input[user_id] = True
    await update.message.reply_text(
        "☀️ **Задачи на сегодня**\n\n"
        "Какие задачи ты хочешь выполнить сегодня?\n\n"
        "Напиши список (каждая с новой строки):",
        parse_mode="Markdown"
    )


async def continue_onboarding_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продолжает онбординг - спрашивает недельные цели с умной логикой."""
    user_id = update.effective_user.id
    today = datetime.now()
    weekday = today.weekday()  # 0=Пн, 4=Пт, 6=Вс
    
    if weekday >= 4:  # Пт, Сб, Вс
        await update.message.reply_text(
            "📋 **Цели на неделю**\n\n"
            "Уже конец недели! Давай установим цели на следующую неделю.\n\n"
            "Какие задачи на следующую неделю?\n"
            "Напиши список (каждая с новой строки):",
            parse_mode="Markdown"
        )
        # Цели будут добавлены на следующий понедельник
        weekly_goals_input[user_id] = True
    else:  # Пн-Чт
        await update.message.reply_text(
            "📋 **Цели на неделю**\n\n"
            "Какие задачи на текущую неделю?\n"
            "Напиши список (каждая с новой строки):",
            parse_mode="Markdown"
        )
        weekly_goals_input[user_id] = True


async def continue_onboarding_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продолжает онбординг - спрашивает месячные цели с умной логикой."""
    from datetime import timedelta
    user_id = update.effective_user.id
    today = datetime.now()
    
    # Сколько дней до конца месяца
    if today.month == 12:
        next_month_first = datetime(today.year + 1, 1, 1)
    else:
        next_month_first = datetime(today.year, today.month + 1, 1)
    
    days_left = (next_month_first.date() - today.date()).days
    
    if days_left < 3:  # Меньше 3 дней до конца
        month_names_next = ["январь", "февраль", "март", "апрель", "май", "июнь", 
                           "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
        next_month_name = month_names_next[next_month_first.month - 1]
        
        await update.message.reply_text(
            "🗓 **Цели на месяц**\n\n"
            f"Месяц почти закончился! Давай установим цели на {next_month_name}.\n\n"
            "Какие задачи на следующий месяц?\n"
            "Напиши список (каждая с новой строки):",
            parse_mode="Markdown"
        )
        monthly_goals_input[user_id] = True
    else:
        await update.message.reply_text(
            "🗓 **Цели на месяц**\n\n"
            "Какие задачи на текущий месяц?\n"
            "Напиши список (каждая с новой строки):",
            parse_mode="Markdown"
        )
        monthly_goals_input[user_id] = True


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает текущий прогресс пользователя."""
    stats = get_week_stats()
    daily_goals = get_daily_goals()
    weekly_goals = get_weekly_goals()
    monthly_goals = get_monthly_goals()
    
    text = "📊 **Твой прогресс**\n\n"
    
    # Дневные цели
    if daily_goals:
        d_completed = sum(1 for g in daily_goals if g["is_completed"] == 1)
        text += f"☀️ Задачи сегодня: {d_completed}/{len(daily_goals)}\n"
    
    # Недельные цели
    if weekly_goals:
        w_completed = sum(1 for g in weekly_goals if g["is_completed"] == 1)
        text += f"📋 Цели недели: {w_completed}/{len(weekly_goals)}\n"
    
    # Месячные цели
    if monthly_goals:
        m_completed = sum(1 for g in monthly_goals if g["is_completed"] == 1)
        text += f"🗓 Цели месяца: {m_completed}/{len(monthly_goals)}\n"
    
    text += f"\n📈 Энергия за неделю: {stats['avg_energy']}\n"
    
    text += "\n**Команды:**\n"
    text += "/today_goals — задачи на сегодня\n"
    text += "/goals — цели на неделю\n"
    text += "/month_goals — цели на месяц\n"
    text += "/week — полная статистика\n"
    text += "/reset — сбросить все данные"
    
    # Кнопка Mini App
    reply_markup = None
    if WEBAPP_URL and BOT_USERNAME:
        app_url = f"{WEBAPP_URL.rstrip('/')}?bot={BOT_USERNAME}"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Открыть меню", web_app=WebAppInfo(url=app_url))]
        ])
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reset — полная очистка данных и перезапуск."""
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    
    # Подтверждение
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, сбросить всё", callback_data="confirm_reset")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
    ])
    
    await update.message.reply_text(
        "⚠️ **ВНИМАНИЕ!**\n\n"
        "Это удалит ВСЕ твои данные:\n"
        "• Все логи\n"
        "• Все цели (дневные, недельные, месячные)\n"
        "• Всю статистику\n\n"
        "Ты уверен?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /test — показать весь функционал бота."""
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    
    import asyncio
    
    await update.message.reply_text("🧪 Демонстрация всего функционала бота\n\nСейчас увидишь все сообщения подряд!")
    
    # Генерируем тестовые данные
    add_test_data(7)
    
    await asyncio.sleep(0.5)
    
    # 1. Утренний опрос
    await asyncio.sleep(0.3)
    
    morning_questions = get_questions("morning")
    for q in morning_questions:
        await asyncio.sleep(0.3)
        if q["options"]:
            keyboard = get_inline_keyboard(q["field_name"], q["options"])
            await context.bot.send_message(user_id, q['text'], reply_markup=keyboard)
        else:
            await context.bot.send_message(user_id, q['text'])
    
    await asyncio.sleep(0.5)
    
    # 2. Вечерний опрос
    await asyncio.sleep(0.3)
    
    evening_questions = get_questions("evening")
    for q in evening_questions:
        await asyncio.sleep(0.3)
        if q["options"]:
            keyboard = get_inline_keyboard(q["field_name"], q["options"])
            await context.bot.send_message(user_id, q['text'], reply_markup=keyboard)
        else:
            await context.bot.send_message(user_id, q['text'])
    
    await asyncio.sleep(0.5)
    
    # 3. Команда /today
    await asyncio.sleep(0.3)
    
    row = get_or_create_today()
    alcohol_opts = get_options_for_field("alcohol")
    walk_opts = get_options_for_field("walk")
    task_opts = get_options_for_field("deep_work_minutes")
    
    alcohol_label = alcohol_opts[1] if row["alcohol"] == 0 else alcohol_opts[0] if row["alcohol"] == 1 else "—"
    walk_label = walk_opts[1] if row["walk"] == 0 else walk_opts[0] if row["walk"] == 1 else "—"
    task_label = task_opts[0] if row["deep_work_minutes"] == 1 else task_opts[1] if row["deep_work_minutes"] == 0 else "—"
    
    await context.bot.send_message(
        user_id,
        f"📅 {row['date']}\n"
        f"Проснулся: {row['wake_time'] or '—'}\n"
        f"Алкоголь вчера: {alcohol_label}\n"
        f"Прогулка: {walk_label}\n"
        f"Энергия: {row['energy'] or '—'}"
    )
    
    await asyncio.sleep(0.5)
    
    # 4. Пятничное напоминание
    await asyncio.sleep(0.3)
    
    await context.bot.send_message(
        user_id,
        "🎯 Доброе утро!\n\n"
        "Сегодня пятница — последний рабочий день недели.\n"
        "Доделай недельные дела сегодня, чтобы на выходных полностью отдыхать! 🏖\n\n"
        "Какая главная задача на сегодня?"
    )
    
    await asyncio.sleep(0.5)
    
    # 5. Воскресная сводка
    await asyncio.sleep(0.3)
    
    stats = get_week_stats()
    days_with = stats['days_with_alcohol']
    tasks_done = int(stats['avg_deep_work'] * stats['total_days'])
    
    # Финансовая бухгалтерия
    plan = WEEKLY_ALCOHOL_BUDGET
    fact = episodes * ALCOHOL_COST_PER_EPISODE
    difference = plan - fact
    
    text = f"📊 Недельная сводка\n\n"
    text += f"Главных задач выполнено: {tasks_done} из {stats['total_days']}\n"
    text += f"Средняя энергия: {stats['avg_energy']}\n\n"
    
    text += f"📊 Алкоголь за неделю:\n"
    text += f"План: {plan:,} ₽\n"
    text += f"Факт: {fact:,} ₽\n"
    text += f"Эпизодов: {episodes}\n\n"
    
    if difference > 0:
        text += f"💰 Экономия: +{difference:,} ₽"
    elif difference < 0:
        text += f"⚠️ Перерасход: {abs(difference):,} ₽"
    else:
        text += "✅ По плану"
    
    await context.bot.send_message(user_id, text)
    
    await asyncio.sleep(0.5)
    
    # 6. Команда /week (показываем то же самое)
    await asyncio.sleep(0.3)
    
    text = f"📊 Статистика за 7 дней:\n\n"
    text += f"Главных задач выполнено: {tasks_done} из {stats['total_days']}\n"
    text += f"Средняя энергия: {stats['avg_energy']}\n\n"
    
    text += f"📊 Алкоголь за неделю:\n"
    text += f"План: {plan:,} ₽\n"
    text += f"Факт: {fact:,} ₽\n"
    text += f"Эпизодов: {episodes}\n\n"
    
    if difference > 0:
        text += f"💰 Экономия: +{difference:,} ₽"
    elif difference < 0:
        text += f"⚠️ Перерасход: {abs(difference):,} ₽"
    else:
        text += "✅ По плану"
    
    await context.bot.send_message(user_id, text)
    
    await asyncio.sleep(0.5)
    
    # 7. Настройка вопросов
    await asyncio.sleep(0.3)
    
    questions = get_all_questions_numbered()
    text = "📝 Настройка вопросов\n\n🌅 — утренние\n🌙 — вечерние\n\n"
    buttons = []
    
    for i, q in enumerate(questions, 1):
        survey = "🌅" if q["survey_type"] == "morning" else "🌙"
        q_text = q['text'][:30] + "..." if len(q['text']) > 30 else q['text']
        text += f"{i}. {survey} {q['text']}\n"
        buttons.append([InlineKeyboardButton(f"✏️ {i}. {q_text}", callback_data=f"editq_{q['id']}")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await context.bot.send_message(user_id, text, reply_markup=keyboard)
    
    await asyncio.sleep(0.5)
    await context.bot.send_message(user_id, "✅ Демонстрация завершена!")


async def cmd_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /questions — список вопросов с кнопками редактирования."""
    if not is_allowed_user(update.effective_user.id):
        return
    questions = get_all_questions_numbered()
    
    text = "📝 Настройка вопросов\n\n"
    text += "🌅 — утренние\n🌙 — вечерние\n\n"
    
    buttons = []
    for i, q in enumerate(questions, 1):
        survey = "🌅" if q["survey_type"] == "morning" else "🌙"
        q_text = q['text'][:30] + "..." if len(q['text']) > 30 else q['text']
        text += f"{i}. {survey} {q['text']}\n"
        buttons.append([InlineKeyboardButton(f"✏️ {i}. {q_text}", callback_data=f"editq_{q['id']}")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(text, reply_markup=keyboard)


async def handle_edit_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки редактирования вопроса."""
    query = update.callback_query
    await query.answer()
    
    if not is_allowed_user(query.from_user.id):
        return
    
    data = query.data
    
    if data.startswith("editq_"):
        # Показать меню редактирования вопроса
        q_id = int(data.split("_")[1])
        questions = get_all_questions_numbered()
        q = next((q for q in questions if q["id"] == q_id), None)
        if not q:
            await query.message.edit_text("❌ Вопрос не найден")
            return
        
        text = f"Редактирование вопроса:\n\n{q['text']}"
        if q["options"]:
            text += f"\n\nВарианты: {q['options']}"
        
        buttons = [[InlineKeyboardButton("📝 Изменить текст", callback_data=f"edittext_{q_id}")]]
        if q["options"]:
            buttons.append([InlineKeyboardButton("🔘 Изменить варианты", callback_data=f"editopts_{q_id}")])
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_questions")])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(text, reply_markup=keyboard)
    
    elif data.startswith("edittext_"):
        # Начать редактирование текста
        q_id = int(data.split("_")[1])
        edit_mode[query.from_user.id] = {"action": "edit_text", "question_id": q_id}
        await query.message.edit_text(
            "✏️ Введи новый текст вопроса:\n\n"
            "(отправь любое сообщение, и оно станет новым текстом вопроса)"
        )
    
    elif data.startswith("editopts_"):
        # Начать редактирование вариантов
        q_id = int(data.split("_")[1])
        edit_mode[query.from_user.id] = {"action": "edit_opts", "question_id": q_id}
        await query.message.edit_text(
            "🔘 Введи варианты ответа через запятую:\n\n"
            "Например: Да,Нет\n"
            "Или: 1,2,3,4,5,6,7,8,9,10"
        )
    
    elif data == "back_to_questions":
        # Вернуться к списку вопросов
        questions = get_all_questions_numbered()
        text = "📝 Настройка вопросов\n\n"
        text += "🌅 — утренние\n🌙 — вечерние\n\n"
        
        buttons = []
        for i, q in enumerate(questions, 1):
            survey = "🌅" if q["survey_type"] == "morning" else "🌙"
            q_text = q['text'][:30] + "..." if len(q['text']) > 30 else q['text']
            text += f"{i}. {survey} {q['text']}\n"
            buttons.append([InlineKeyboardButton(f"✏️ {i}. {q_text}", callback_data=f"editq_{q['id']}")])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(text, reply_markup=keyboard)


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из Telegram Mini App."""
    user_id = update.effective_user.id
    data = update.message.web_app_data.data
    logger.info("Mini App → data=%s user=%s", data, user_id)
    if user_id != ALLOWED_USER_ID:
        logger.warning("Mini App: user %s not allowed", user_id)
        return

    if data == "edit_questions":
        # Открываем редактирование вопросов
        await cmd_questions(update, context)
    elif data == "reset":
        # Сбрасываем данные
        await cmd_reset(update, context)
    else:
        logger.info("Mini App: unknown data=%s", data)
        await update.message.reply_text("✅ Данные получены!")


async def post_init(application):
    """Настройка кнопки Mini App при запуске."""
    if WEBAPP_URL and BOT_USERNAME:
        app_url = f"{WEBAPP_URL.rstrip('/')}?bot={BOT_USERNAME}"
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Открыть", web_app=WebAppInfo(url=app_url))
        )
        logger.info("Mini App menu button configured")


def main():
    """Запуск бота."""
    if not BOT_TOKEN:
        raise ValueError("Укажите BOT_TOKEN в .env")
    if not ALLOWED_USER_ID:
        raise ValueError("Укажите ALLOWED_USER_ID в .env (ваш Telegram ID)")

    init_db()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("today_goals", cmd_today_goals))
    app.add_handler(CommandHandler("goals", cmd_goals))
    app.add_handler(CommandHandler("month_goals", cmd_month_goals))
    app.add_handler(CommandHandler("questions", cmd_questions))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Планировщик опросов и напоминаний
    setup_jobs(app.job_queue, morning_survey, evening_survey, weekly_summary, friday_reminder, end_of_month_check)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()