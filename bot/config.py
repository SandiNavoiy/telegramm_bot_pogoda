"""
Модуль конфигурации приложения.
Загружает переменные окружения из файла .env и предоставляет настройки для бота.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv()


@dataclass
class Config:
    """
    Класс конфигурации приложения со всеми параметрами.
    """
    # Токен Telegram бота
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()

    # Ключ OpenWeatherMap API (необязательный, если пустой - используется Open-Meteo)
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "").strip()

    # Часовой пояс по умолчанию
    timezone: str = os.getenv("TIMEZONE", "Europe/Moscow").strip()

    # Время отправки утреннего прогноза
    morning_hour: int = int(os.getenv("MORNING_NOTIFICATION_HOUR", "7"))
    morning_minute: int = int(os.getenv("MORNING_NOTIFICATION_MINUTE", "0"))

    # Время дневной проверки осадков
    afternoon_hour: int = int(os.getenv("AFTERNOON_CHECK_HOUR", "14"))
    afternoon_minute: int = int(os.getenv("AFTERNOON_CHECK_MINUTE", "0"))

    # Путь к файлу базы данных SQLite
    db_path: str = os.getenv("DATABASE_PATH", "weather_bot.db").strip()


# Глобальный объект конфигурации
config = Config()
