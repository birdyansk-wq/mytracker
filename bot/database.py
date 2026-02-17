"""
Работа с SQLite базой данных.
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .config import DB_PATH


def get_connection():
    """Создаёт подключение к БД, создаёт папку и таблицу при необходимости."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Результаты как словари
    return conn


# Дефолтные вопросы (для первой инициализации)
DEFAULT_QUESTIONS = [
    ("morning", 0, "wake_time", "Во сколько проснулся? (например: 7:30)", None),
    ("morning", 1, "alcohol", "Был ли алкоголь вчера?", "Да,Нет"),
    ("evening", 0, "walk", "Была ли прогулка?", "Да,Нет"),
    ("evening", 1, "energy", "Энергия 1–10", "1,2,3,4,5,6,7,8,9,10"),
]


def init_db():
    """Создаёт таблицы daily_logs, questions и weekly_goals если их нет."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            wake_time TEXT,
            main_task TEXT,
            alcohol INTEGER,
            deep_work_minutes INTEGER,
            walk INTEGER,
            energy INTEGER,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_type TEXT NOT NULL,
            order_idx INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            text TEXT NOT NULL,
            options TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weekly_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start_date TEXT NOT NULL,
            task_text TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monthly_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_start_date TEXT NOT NULL,
            task_text TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            task_text TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            onboarding_completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    # Заполняем дефолтными вопросами, если таблица пуста
    if conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0:
        for st, oi, fn, txt, opt in DEFAULT_QUESTIONS:
            conn.execute(
                "INSERT INTO questions (survey_type, order_idx, field_name, text, options) VALUES (?, ?, ?, ?, ?)",
                (st, oi, fn, txt, opt),
            )
        conn.commit()
    conn.close()


def get_or_create_today():
    """Возвращает запись на сегодня. Создаёт пустую, если нет."""
    conn = get_connection()
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT * FROM daily_logs WHERE date = ?", (today,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO daily_logs (date, created_at) VALUES (?, ?)",
            (today, datetime.now().isoformat())
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM daily_logs WHERE date = ?", (today,)
        ).fetchone()
    conn.close()
    return dict(zip(row.keys(), row))


def update_field(field: str, value):
    """Обновляет одно поле в записи на сегодня."""
    conn = get_connection()
    today = date.today().isoformat()
    conn.execute(
        f"UPDATE daily_logs SET {field} = ? WHERE date = ?",
        (value, today)
    )
    conn.commit()
    conn.close()


def get_questions(survey_type: str) -> list:
    """Возвращает список вопросов для опроса. Каждый элемент — dict с field_name, text, options."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT field_name, text, options FROM questions WHERE survey_type = ? ORDER BY order_idx",
        (survey_type,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        opt = r["options"].split(",") if r["options"] else None
        result.append({"field_name": r["field_name"], "text": r["text"], "options": opt})
    return result


def get_all_questions_numbered() -> list:
    """Все вопросы с глобальным номером (1-based) для /questions и /edit_q."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, survey_type, order_idx, field_name, text, options FROM questions 
           ORDER BY CASE survey_type WHEN 'morning' THEN 0 ELSE 1 END, order_idx"""
    ).fetchall()
    conn.close()
    return [dict(zip(r.keys(), r)) for r in rows]


def update_question_text(question_id: int, new_text: str):
    """Обновляет текст вопроса по id."""
    conn = get_connection()
    conn.execute("UPDATE questions SET text = ? WHERE id = ?", (new_text, question_id))
    conn.commit()
    conn.close()


def update_question_options(question_id: int, options_str: str):
    """Обновляет варианты ответа (через запятую)."""
    conn = get_connection()
    conn.execute("UPDATE questions SET options = ? WHERE id = ?", (options_str, question_id))
    conn.commit()
    conn.close()


def add_test_data(days: int):
    """Добавляет тестовые данные за N дней назад."""
    import random
    from datetime import timedelta
    
    conn = get_connection()
    today = date.today()
    
    for i in range(days):
        test_date = (today - timedelta(days=i)).isoformat()
        
        # Проверяем, есть ли уже запись
        existing = conn.execute("SELECT id FROM daily_logs WHERE date = ?", (test_date,)).fetchone()
        if existing:
            continue
        
        # Генерируем случайные данные
        wake_time = f"{random.randint(6, 9)}:{random.choice(['00', '15', '30', '45'])}"
        alcohol = random.choice([0, 0, 0, 0, 1])  # 20% вероятность
        deep_work = random.choice([0, 1, 1])  # 66% выполнения
        walk = random.choice([0, 1, 1])  # 66% прогулок
        energy = random.randint(5, 9)
        
        conn.execute(
            """INSERT INTO daily_logs 
               (date, wake_time, alcohol, deep_work_minutes, walk, energy, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (test_date, wake_time, alcohol, deep_work, walk, energy, datetime.now().isoformat())
        )
    
    conn.commit()
    conn.close()


def get_options_for_field(field_name: str) -> list:
    """Варианты ответа для поля (для отображения в /today). Первый = 1, второй = 0."""
    conn = get_connection()
    row = conn.execute(
        "SELECT options FROM questions WHERE field_name = ?", (field_name,)
    ).fetchone()
    conn.close()
    if row and row["options"]:
        return row["options"].split(",")
    return ["Да", "Нет"]  # fallback


def get_week_stats():
    """Статистика за последние 7 дней."""
    conn = get_connection()
    today = date.today()
    rows = conn.execute(
        """SELECT alcohol, deep_work_minutes, energy FROM daily_logs
           WHERE date >= date(?, '-7 days') AND date <= ?""",
        (today.isoformat(), today.isoformat())
    ).fetchall()
    conn.close()

    days_without_alcohol = sum(1 for r in rows if r["alcohol"] == 0)
    days_with_alcohol = sum(1 for r in rows if r["alcohol"] == 1)
    deep_work_values = [r["deep_work_minutes"] for r in rows if r["deep_work_minutes"] is not None]
    energy_values = [r["energy"] for r in rows if r["energy"] is not None]

    return {
        "days_without_alcohol": days_without_alcohol,
        "days_with_alcohol": days_with_alcohol,
        "avg_deep_work": round(sum(deep_work_values) / len(deep_work_values), 1) if deep_work_values else 0,
        "avg_energy": round(sum(energy_values) / len(energy_values), 1) if energy_values else 0,
        "total_days": len(rows),
    }


def get_monday_of_week(target_date=None):
    """Возвращает дату понедельника для заданной даты (или сегодня)."""
    from datetime import timedelta
    if target_date is None:
        target_date = date.today()
    # weekday: 0=Monday, 6=Sunday
    days_since_monday = target_date.weekday()
    monday = target_date - timedelta(days=days_since_monday)
    return monday.isoformat()


def add_weekly_goals(tasks_list):
    """Добавляет список задач на текущую неделю."""
    conn = get_connection()
    week_start = get_monday_of_week()
    now = datetime.now().isoformat()
    for task in tasks_list:
        task = task.strip()
        if task:  # пропускаем пустые строки
            conn.execute(
                "INSERT INTO weekly_goals (week_start_date, task_text, is_completed, created_at) VALUES (?, ?, 0, ?)",
                (week_start, task, now)
            )
    conn.commit()
    conn.close()


def get_weekly_goals(week_start=None):
    """Возвращает список целей на неделю."""
    conn = get_connection()
    if week_start is None:
        week_start = get_monday_of_week()
    rows = conn.execute(
        "SELECT id, task_text, is_completed FROM weekly_goals WHERE week_start_date = ? ORDER BY id",
        (week_start,)
    ).fetchall()
    conn.close()
    return [dict(zip(row.keys(), row)) for row in rows]


def toggle_goal_completion(goal_id):
    """Переключает статус выполнения задачи."""
    conn = get_connection()
    conn.execute(
        "UPDATE weekly_goals SET is_completed = 1 - is_completed WHERE id = ?",
        (goal_id,)
    )
    conn.commit()
    conn.close()


def get_incomplete_goals(week_start=None):
    """Возвращает список невыполненных задач на неделю."""
    conn = get_connection()
    if week_start is None:
        week_start = get_monday_of_week()
    rows = conn.execute(
        "SELECT id, task_text FROM weekly_goals WHERE week_start_date = ? AND is_completed = 0 ORDER BY id",
        (week_start,)
    ).fetchall()
    conn.close()
    return [dict(zip(row.keys(), row)) for row in rows]


def move_goals_to_next_week(goal_ids):
    """Переносит задачи на следующую неделю."""
    from datetime import timedelta
    conn = get_connection()
    current_monday = date.fromisoformat(get_monday_of_week())
    next_monday = (current_monday + timedelta(days=7)).isoformat()
    now = datetime.now().isoformat()
    
    for goal_id in goal_ids:
        # Получаем текст задачи
        row = conn.execute("SELECT task_text FROM weekly_goals WHERE id = ?", (goal_id,)).fetchone()
        if row:
            task_text = row["task_text"]
            # Создаём новую задачу на следующую неделю
            conn.execute(
                "INSERT INTO weekly_goals (week_start_date, task_text, is_completed, created_at) VALUES (?, ?, 0, ?)",
                (next_monday, task_text, now)
            )
    conn.commit()
    conn.close()


def get_first_day_of_month(target_date=None):
    """Возвращает дату первого дня месяца для заданной даты (или сегодня)."""
    if target_date is None:
        target_date = date.today()
    first_day = date(target_date.year, target_date.month, 1)
    return first_day.isoformat()


def is_last_day_of_month(target_date=None):
    """Проверяет, является ли дата последним днём месяца."""
    from datetime import timedelta
    if target_date is None:
        target_date = date.today()
    next_day = target_date + timedelta(days=1)
    return next_day.month != target_date.month


def add_monthly_goals(tasks_list):
    """Добавляет список задач на текущий месяц."""
    conn = get_connection()
    month_start = get_first_day_of_month()
    now = datetime.now().isoformat()
    for task in tasks_list:
        task = task.strip()
        if task:  # пропускаем пустые строки
            conn.execute(
                "INSERT INTO monthly_goals (month_start_date, task_text, is_completed, created_at) VALUES (?, ?, 0, ?)",
                (month_start, task, now)
            )
    conn.commit()
    conn.close()


def get_monthly_goals(month_start=None):
    """Возвращает список целей на месяц."""
    conn = get_connection()
    if month_start is None:
        month_start = get_first_day_of_month()
    rows = conn.execute(
        "SELECT id, task_text, is_completed FROM monthly_goals WHERE month_start_date = ? ORDER BY id",
        (month_start,)
    ).fetchall()
    conn.close()
    return [dict(zip(row.keys(), row)) for row in rows]


def toggle_monthly_goal_completion(goal_id):
    """Переключает статус выполнения месячной задачи."""
    conn = get_connection()
    conn.execute(
        "UPDATE monthly_goals SET is_completed = 1 - is_completed WHERE id = ?",
        (goal_id,)
    )
    conn.commit()
    conn.close()


def get_incomplete_monthly_goals(month_start=None):
    """Возвращает список невыполненных месячных задач."""
    conn = get_connection()
    if month_start is None:
        month_start = get_first_day_of_month()
    rows = conn.execute(
        "SELECT id, task_text FROM monthly_goals WHERE month_start_date = ? AND is_completed = 0 ORDER BY id",
        (month_start,)
    ).fetchall()
    conn.close()
    return [dict(zip(row.keys(), row)) for row in rows]


def move_monthly_goals_to_next_month(goal_ids):
    """Переносит задачи на следующий месяц."""
    from datetime import timedelta
    conn = get_connection()
    current_first = date.fromisoformat(get_first_day_of_month())
    # Следующий месяц = первое число следующего месяца
    if current_first.month == 12:
        next_first = date(current_first.year + 1, 1, 1)
    else:
        next_first = date(current_first.year, current_first.month + 1, 1)
    next_month_start = next_first.isoformat()
    now = datetime.now().isoformat()
    
    for goal_id in goal_ids:
        # Получаем текст задачи
        row = conn.execute("SELECT task_text FROM monthly_goals WHERE id = ?", (goal_id,)).fetchone()
        if row:
            task_text = row["task_text"]
            # Создаём новую задачу на следующий месяц
            conn.execute(
                "INSERT INTO monthly_goals (month_start_date, task_text, is_completed, created_at) VALUES (?, ?, 0, ?)",
                (next_month_start, task_text, now)
            )
    conn.commit()
    conn.close()


def get_monthly_stats():
    """Возвращает статистику по месячным целям за текущий месяц."""
    month_start = get_first_day_of_month()
    goals = get_monthly_goals(month_start)
    if not goals:
        return {"total": 0, "completed": 0, "completion_rate": 0}
    
    completed = sum(1 for g in goals if g["is_completed"] == 1)
    total = len(goals)
    completion_rate = round((completed / total) * 100, 1) if total > 0 else 0
    
    return {
        "total": total,
        "completed": completed,
        "completion_rate": completion_rate
    }


def add_daily_goals(tasks_list, target_date=None):
    """Добавляет список дневных задач."""
    conn = get_connection()
    if target_date is None:
        target_date = date.today()
    date_str = target_date.isoformat()
    now = datetime.now().isoformat()
    for task in tasks_list:
        task = task.strip()
        if task:
            conn.execute(
                "INSERT INTO daily_goals (date, task_text, is_completed, created_at) VALUES (?, ?, 0, ?)",
                (date_str, task, now)
            )
    conn.commit()
    conn.close()


def get_daily_goals(target_date=None):
    """Возвращает список дневных целей."""
    conn = get_connection()
    if target_date is None:
        target_date = date.today()
    date_str = target_date.isoformat()
    rows = conn.execute(
        "SELECT id, task_text, is_completed FROM daily_goals WHERE date = ? ORDER BY id",
        (date_str,)
    ).fetchall()
    conn.close()
    return [dict(zip(row.keys(), row)) for row in rows]


def toggle_daily_goal_completion(goal_id):
    """Переключает статус выполнения дневной задачи."""
    conn = get_connection()
    conn.execute(
        "UPDATE daily_goals SET is_completed = 1 - is_completed WHERE id = ?",
        (goal_id,)
    )
    conn.commit()
    conn.close()


def is_onboarding_completed():
    """Проверяет, прошёл ли пользователь онбординг."""
    conn = get_connection()
    row = conn.execute("SELECT onboarding_completed FROM user_settings ORDER BY id LIMIT 1").fetchone()
    conn.close()
    if row is None:
        # Создаём запись, если её нет
        conn = get_connection()
        conn.execute("INSERT INTO user_settings (onboarding_completed, created_at) VALUES (0, ?)", (datetime.now().isoformat(),))
        conn.commit()
        conn.close()
        return False
    return row["onboarding_completed"] == 1


def set_onboarding_completed():
    """Отмечает онбординг как завершённый."""
    conn = get_connection()
    conn.execute("UPDATE user_settings SET onboarding_completed = 1")
    conn.commit()
    conn.close()


def reset_all_data():
    """Полностью очищает все данные пользователя."""
    conn = get_connection()
    conn.execute("DELETE FROM daily_logs")
    conn.execute("DELETE FROM daily_goals")
    conn.execute("DELETE FROM weekly_goals")
    conn.execute("DELETE FROM monthly_goals")
    conn.execute("UPDATE user_settings SET onboarding_completed = 0")
    conn.commit()
    conn.close()


def get_today_log():
    """Получить запись за сегодня."""
    conn = get_connection()
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT * FROM daily_logs WHERE date = ?",
        (today,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_last_n_days(n=7):
    """Получить записи за последние N дней."""
    conn = get_connection()
    today = date.today()
    rows = conn.execute(
        """SELECT * FROM daily_logs
           WHERE date >= date(?, ? || ' days') AND date <= ?
           ORDER BY date DESC""",
        (today.isoformat(), f'-{n}', today.isoformat())
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
