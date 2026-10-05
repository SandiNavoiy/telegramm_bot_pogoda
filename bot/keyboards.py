"""
Модуль создания клавиатур (Reply и Inline) для взаимодействия с пользователем.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Главное меню бота с основными кнопками.
    """
    kb = [
        [
            KeyboardButton(text="🌤 Погода сейчас"),
            KeyboardButton(text="📅 Прогноз на день")
        ],
        [
            KeyboardButton(text="🏙 Сменить город"),
            KeyboardButton(text="⚙️ Настройки")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие в меню..."
    )


def get_city_request_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для запроса города с кнопкой отправки геолокации.
    """
    kb = [
        [
            KeyboardButton(text="📍 Отправить мою геолокацию", request_location=True)
        ],
        [
            KeyboardButton(text="❌ Отмена")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Введите название населенного пункта..."
    )


def get_settings_keyboard(morning_notify: bool, afternoon_notify: bool) -> InlineKeyboardMarkup:
    """
    Инлайн-клавиатура настроек уведомлений.

    :param morning_notify: Включен ли утренний прогноз (07:00).
    :param afternoon_notify: Включено ли предупреждение об осадках (14:00).
    """
    morning_icon = "✅ Вкл" if morning_notify else "❌ Выкл"
    afternoon_icon = "✅ Вкл" if afternoon_notify else "❌ Выкл"

    buttons = [
        [
            InlineKeyboardButton(
                text=f"🌅 Утренний прогноз (07:00): {morning_icon}",
                callback_data="toggle_morning"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⚠️ Проверка осадков (14:00): {afternoon_icon}",
                callback_data="toggle_afternoon"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Обновить статус",
                callback_data="refresh_settings"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
