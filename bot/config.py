"""
Конфигурация бота.
"""
import os
from pathlib import Path

# Загружаем переменные из .env (если используется python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# Токен бота из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Mini App (нужно задеплоить webapp и указать URL)
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# ID пользователя — бот работает только для этого пользователя
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID") or "0")

# Часовой пояс Красноярска
TIMEZONE = "Asia/Krasnoyarsk"

# Время опросов (часы, минуты)
MORNING_HOUR, MORNING_MINUTE = 9, 0
EVENING_HOUR, EVENING_MINUTE = 21, 0

# Недельная сводка по воскресеньям
WEEKLY_SUMMARY_HOUR, WEEKLY_SUMMARY_MINUTE = 14, 0

# Проверка целей в пятницу вечером
FRIDAY_REMINDER_HOUR, FRIDAY_REMINDER_MINUTE = 22, 0

# Проверка месячных целей (каждый день, внутри функции проверяется, последний ли день)
END_OF_MONTH_CHECK_HOUR, END_OF_MONTH_CHECK_MINUTE = 22, 30

# Финансовая модель алкоголя
ALCOHOL_COST_PER_EPISODE = 3000  # стоимость одного эпизода
WEEKLY_ALCOHOL_BUDGET = 7000     # недельный бюджет (≈30 000 / 4.33)

# Путь к базе данных
DB_PATH = Path(__file__).parent.parent / "data" / "habits.db"
