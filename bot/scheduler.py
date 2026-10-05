"""
Модуль планировщика фоновых задач (APScheduler).
Осуществляет:
1. Ежедневную утреннюю рассылку прогноза погоды (по умолчанию в 07:00).
2. Дневную проверку прогноза на наличие дождя/снега во второй половине дня (по умолчанию в 14:00).
"""

import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from bot.config import config
from bot.database import db
from bot.weather_service import weather_service

logger = logging.getLogger(__name__)


async def send_morning_forecast(bot: Bot) -> None:
    """
    Утренняя задача: отправка прогноза погоды всем активным пользователям в 07:00.
    """
    logger.info("Запуск утренней рассылки прогноза погоды...")
    users = await db.get_active_users_for_morning()

    if not users:
        logger.info("Нет активных пользователей для утренней рассылки.")
        return

    count = 0
    for user in users:
        user_id = user["user_id"]
        city = user["city"]
        lat = user["latitude"]
        lon = user["longitude"]

        try:
            forecast_text = await weather_service.get_daily_forecast(city, lat, lon)
            if forecast_text:
                await bot.send_message(chat_id=user_id, text=forecast_text, parse_mode="HTML")
                count += 1
        except Exception as e:
            logger.warning(f"Не удалось отправить утренний прогноз пользователю {user_id}: {e}")

    logger.info(f"Утренняя рассылка успешно завершена. Отправлено сообщений: {count}/{len(users)}")


async def send_afternoon_precipitation_alert(bot: Bot) -> None:
    """
    Дневная задача: проверка погоды в 14:00 и отправка предупреждения при наличии дождя или снега.
    """
    logger.info("Запуск дневной проверки осадков (14:00)...")
    users = await db.get_active_users_for_afternoon()

    if not users:
        logger.info("Нет активных пользователей для дневной проверки осадков.")
        return

    alert_count = 0
    for user in users:
        user_id = user["user_id"]
        city = user["city"]
        lat = user["latitude"]
        lon = user["longitude"]

        try:
            warning = await weather_service.check_afternoon_precipitation(city, lat, lon)
            if warning.has_precipitation and warning.warning_text:
                await bot.send_message(chat_id=user_id, text=warning.warning_text, parse_mode="HTML")
                alert_count += 1
        except Exception as e:
            logger.warning(f"Ошибка при проверке осадков для пользователя {user_id}: {e}")

    logger.info(f"Дневная проверка осадков завершена. Отправлено предупреждений: {alert_count}/{len(users)}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Настройка и регистрация задач в планировщике APScheduler.

    :param bot: Экземпляр бота aiogram.
    :return: Инициализированный объект AsyncIOScheduler.
    """
    tz = pytz.timezone(config.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    # 1. Утренняя рассылка в 07:00
    scheduler.add_job(
        send_morning_forecast,
        trigger=CronTrigger(
            hour=config.morning_hour,
            minute=config.morning_minute,
            timezone=tz
        ),
        args=[bot],
        id="morning_forecast_job",
        name="Утренний прогноз погоды",
        replace_existing=True
    )

    # 2. Дневная проверка осадков в 14:00
    scheduler.add_job(
        send_afternoon_precipitation_alert,
        trigger=CronTrigger(
            hour=config.afternoon_hour,
            minute=config.afternoon_minute,
            timezone=tz
        ),
        args=[bot],
        id="afternoon_precipitation_job",
        name="Дневная проверка осадков",
        replace_existing=True
    )

    return scheduler
