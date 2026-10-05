"""
Модуль для работы с базой данных SQLite через асинхронную библиотеку aiosqlite.
Хранит настройки пользователей: населенный пункт, координаты, статус уведомлений.
"""

import aiosqlite
from typing import Optional, List, Dict, Any
from bot.config import config


class Database:
    """
    Класс управления базой данных SQLite.
    """

    def __init__(self, db_path: str = config.db_path):
        """
        Инициализация менеджера базы данных.

        :param db_path: Путь к файлу базы данных SQLite.
        """
        self.db_path = db_path

    async def init_db(self) -> None:
        """
        Создает необходимые таблицы в базе данных при первом запуске, если они не существуют.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    city TEXT,
                    latitude REAL,
                    longitude REAL,
                    timezone TEXT DEFAULT 'Europe/Moscow',
                    morning_notify INTEGER DEFAULT 1,
                    afternoon_notify INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить данные пользователя по его Telegram ID.

        :param user_id: Идентификатор пользователя в Telegram.
        :return: Словарь с данными пользователя или None.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def set_user_city(
        self,
        user_id: int,
        city: str,
        latitude: float,
        longitude: float,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        timezone: str = "Europe/Moscow"
    ) -> None:
        """
        Сохранить или обновить город и координаты пользователя.

        :param user_id: Идентификатор пользователя.
        :param city: Название населенного пункта.
        :param latitude: Широта.
        :param longitude: Долгота.
        :param username: Юзернейм в Telegram (опционально).
        :param first_name: Имя пользователя (опционально).
        :param timezone: Часовой пояс.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, city, latitude, longitude, timezone, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = COALESCE(excluded.username, users.username),
                    first_name = COALESCE(excluded.first_name, users.first_name),
                    city = excluded.city,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    timezone = excluded.timezone,
                    updated_at = CURRENT_TIMESTAMP;
            """, (user_id, username, first_name, city, latitude, longitude, timezone))
            await db.commit()

    async def get_active_users_for_morning(self) -> List[Dict[str, Any]]:
        """
        Получить список пользователей, у которых включен утренний прогноз и задан город.

        :return: Список словарей пользователей.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE city IS NOT NULL AND morning_notify = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_active_users_for_afternoon(self) -> List[Dict[str, Any]]:
        """
        Получить список пользователей, у которых включена дневная проверка осадков и задан город.

        :return: Список словарей пользователей.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE city IS NOT NULL AND afternoon_notify = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def toggle_notification(self, user_id: int, notify_type: str) -> Optional[int]:
        """
        Переключить состояние уведомления (morning_notify или afternoon_notify).

        :param user_id: Идентификатор пользователя.
        :param notify_type: 'morning' или 'afternoon'.
        :return: Новое состояние (1 или 0) или None при ошибке.
        """
        column = "morning_notify" if notify_type == "morning" else "afternoon_notify"
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущее значение
            async with db.execute(f"SELECT {column} FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                new_val = 0 if row[0] == 1 else 1

            # Обновляем значение
            await db.execute(
                f"UPDATE users SET {column} = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (new_val, user_id)
            )
            await db.commit()
            return new_val


# Глобальный экземпляр базы данных
db = Database()
