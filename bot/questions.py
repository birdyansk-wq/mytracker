"""
Тексты вопросов и логика опросов.
Вопросы хранятся в БД, редактируются через /edit_q.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .database import get_questions


def get_inline_keyboard(field_name: str, options: list = None):
    """Создаёт inline-клавиатуру для вопроса."""
    if not options:
        return None
    # Для 6+ вариантов — два ряда, иначе один
    if len(options) >= 6:
        mid = (len(options) + 1) // 2
        buttons = [
            [InlineKeyboardButton(str(o), callback_data=f"{field_name}_{o}") for o in options[:mid]],
            [InlineKeyboardButton(str(o), callback_data=f"{field_name}_{o}") for o in options[mid:]],
        ]
    else:
        buttons = [[InlineKeyboardButton(str(o), callback_data=f"{field_name}_{o}") for o in options]]
    return InlineKeyboardMarkup(buttons)


def get_question_data(survey_type: str, index: int) -> dict:
    """Возвращает данные вопроса: field_name, text, has_keyboard, options."""
    questions = get_questions(survey_type)
    if index >= len(questions):
        return None
    q = questions[index]
    has_keyboard = q["options"] is not None
    return {
        "field_name": q["field_name"],
        "text": q["text"],
        "has_keyboard": has_keyboard,
        "options": q["options"],
    }


def get_total_questions(survey_type: str) -> int:
    """Количество вопросов в опросе."""
    return len(get_questions(survey_type))


def parse_callback_data(data: str) -> tuple:
    """Парсит callback_data: energy_7 -> (energy, 7), alcohol_Да -> (alcohol, Да)."""
    parts = data.split("_", 1)
    return parts[0], parts[1] if len(parts) > 1 else None
