"""
Настройка расписания опросов через JobQueue.
"""
from datetime import time

import pytz

from .config import (
    TIMEZONE,
    MORNING_HOUR,
    MORNING_MINUTE,
    EVENING_HOUR,
    EVENING_MINUTE,
    WEEKLY_SUMMARY_HOUR,
    WEEKLY_SUMMARY_MINUTE,
    FRIDAY_REMINDER_HOUR,
    FRIDAY_REMINDER_MINUTE,
    END_OF_MONTH_CHECK_HOUR,
    END_OF_MONTH_CHECK_MINUTE,
)


def setup_jobs(job_queue, morning_callback, evening_callback, weekly_summary_callback, friday_reminder_callback, end_of_month_callback):
    """
    Добавляет опросы и напоминания в планировщик.
    job_queue — app.job_queue из python-telegram-bot.
    """
    tz = pytz.timezone(TIMEZONE)
    
    # Ежедневные опросы
    job_queue.run_daily(morning_callback, time=time(MORNING_HOUR, MORNING_MINUTE, tzinfo=tz))
    job_queue.run_daily(evening_callback, time=time(EVENING_HOUR, EVENING_MINUTE, tzinfo=tz))
    
    # Недельная сводка по воскресеньям (0 = Sunday)
    job_queue.run_daily(
        weekly_summary_callback,
        time=time(WEEKLY_SUMMARY_HOUR, WEEKLY_SUMMARY_MINUTE, tzinfo=tz),
        days=(0,)
    )
    
    # Проверка недельных целей в пятницу вечером (5 = Friday)
    job_queue.run_daily(
        friday_reminder_callback,
        time=time(FRIDAY_REMINDER_HOUR, FRIDAY_REMINDER_MINUTE, tzinfo=tz),
        days=(5,)
    )
    
    # Проверка месячных целей каждый день (внутри функции проверяется, последний ли день)
    job_queue.run_daily(
        end_of_month_callback,
        time=time(END_OF_MONTH_CHECK_HOUR, END_OF_MONTH_CHECK_MINUTE, tzinfo=tz)
    )
