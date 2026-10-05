"""
Главная точка входа для запуска Telegram-бота погоды.
Инициализирует бота, диспетчер, базу данных, планировщик задач и запускает polling.
"""

import sys
import asyncio
import logging

# Настройка кодировки вывода для корректного отображения Unicode и эмодзи на Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import config
from bot.database import db
from bot.handlers import router
from bot.scheduler import setup_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("WeatherBot")


async def set_bot_commands(bot: Bot) -> None:
    """
    Установка списка команд в меню бота Telegram.
    """
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота / Главное меню"),
        BotCommand(command="weather", description="🌤 Погода прямо сейчас"),
        BotCommand(command="forecast", description="📅 Прогноз на сегодня"),
        BotCommand(command="city", description="🏙 Сменить населенный пункт"),
        BotCommand(command="settings", description="⚙️ Настройки уведомлений"),
        BotCommand(command="help", description="📖 Справка по командам"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    """
    Основная асинхронная функция запуска бота.
    """
    # Проверка наличия токена
    if not config.bot_token:
        logger.error(
            "❌ ОШИБКА: BOT_TOKEN не указан в файле .env!\n"
            "Пожалуйста, создайте бота через @BotFather в Telegram, скопируйте полученный токен "
            "и укажите его в файле .env (BOT_TOKEN=ваш_токен)."
        )
        return

    logger.info("Инициализация базы данных SQLite...")
    await db.init_db()

    logger.info("Создание экземпляров Bot и Dispatcher...")
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутера обработчиков
    dp.include_router(router)

    # Настройка команд меню Telegram
    await set_bot_commands(bot)

    # Настройка и запуск планировщика задач (07:00 и 14:00)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info(
        f"Планировщик запущен. Часовой пояс: {config.timezone}. "
        f"Утренний прогноз: {config.morning_hour:02d}:{config.morning_minute:02d}, "
        f"Дневная проверка осадков: {config.afternoon_hour:02d}:{config.afternoon_minute:02d}."
    )

    try:
        logger.info("Бот успешно запущен и ожидает сообщений...")
        # Удаляем старые обновления (накопившиеся пока бот был выключен)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при работе бота: {e}", exc_info=True)
    finally:
        logger.info("Остановка бота и освобождение ресурсов...")
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Работа программы прервана пользователем.")
