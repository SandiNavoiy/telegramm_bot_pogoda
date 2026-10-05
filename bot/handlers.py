"""
Модуль обработчиков команд, текстовых сообщений, геолокации и колбэков.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database import db
from bot.weather_service import weather_service
from bot.keyboards import (
    get_main_keyboard,
    get_city_request_keyboard,
    get_settings_keyboard
)

# Роутер для регистрации обработчиков
router = Router()


class CityStates(StatesGroup):
    """Состояния FSM для ввода населенного пункта"""
    waiting_for_city = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start.
    Приветствует пользователя и проверяет наличие сохраненного города.
    """
    await state.clear()
    user = await db.get_user(message.from_user.id)

    if user and user.get("city"):
        city = user["city"]
        await message.answer(
            f"👋 <b>С возвращением, {message.from_user.first_name}!</b>\n\n"
            f"📍 Ваш текущий населенный пункт: <b>{city}</b>\n\n"
            f"⏰ <b>Автоматические уведомления:</b>\n"
            f"  • В <b>07:00</b> — утренний прогноз погоды на день.\n"
            f"  • В <b>14:00</b> — проверка на дождь/снег и предупреждение об осадках.\n\n"
            f"Вы можете в любой момент запросить погоду вручную или сменить город через меню ниже 👇",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await state.set_state(CityStates.waiting_for_city)
        await message.answer(
            f"👋 <b>Здравствуйте, {message.from_user.first_name}!</b>\n\n"
            f"Я бот погоды 🌤\n"
            f"Я могу:\n"
            f"  1. 🌅 Каждый день в <b>07:00</b> отправлять утренний прогноз погоды.\n"
            f"  2. ⚠️ В <b>14:00</b> проверять вероятность дождя или снега и предупреждать вас.\n"
            f"  3. 🌤 Показывать погоду по вашей команде в любое время.\n\n"
            f"📍 Для начала работы, пожалуйста, <b>введите название вашего населенного пункта</b> "
            f"(например: <i>Москва</i>, <i>Казань</i>, <i>Алматы</i>) "
            f"или нажмите кнопку отправки геолокации 👇",
            reply_markup=get_city_request_keyboard(),
            parse_mode="HTML"
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Обработчик команды /help.
    Показывает справочную информацию о возможностях бота.
    """
    help_text = (
        "📖 <b>Справка по использованию бота:</b>\n\n"
        "🔹 <b>Основные команды:</b>\n"
        "  • /start — перезапустить бота / проверить настройки\n"
        "  • /weather — узнать текущую погоду\n"
        "  • /forecast — подробный прогноз на сегодня\n"
        "  • /city — изменить населенный пункт\n"
        "  • /settings — настроить время и параметры рассылок\n"
        "  • /help — показать эту справку\n\n"
        "⏰ <b>Автоматические расписания:</b>\n"
        "  • <b>07:00</b> — утренний прогноз погоды на текущий день.\n"
        "  • <b>14:00</b> — проверка осадков на вторую половину дня (дождь/снег/ливень).\n\n"
        "💡 Вы также можете пользоваться удобными кнопками меню внизу экрана."
    )
    await message.answer(help_text, reply_markup=get_main_keyboard(), parse_mode="HTML")


@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    """
    Отмена текущего действия FSM.
    """
    await state.clear()
    await message.answer(
        "Действие отменено. Возвращаемся в главное меню.",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("city"))
@router.message(F.text == "🏙 Сменить город")
async def cmd_change_city(message: Message, state: FSMContext):
    """
    Запрос на изменение населенного пункта.
    """
    await state.set_state(CityStates.waiting_for_city)
    await message.answer(
        "🏙 <b>Введите название нового населенного пункта</b> (например, <i>Санкт-Петербург</i> или <i>Сочи</i>)\n"
        "или отправьте геолокацию с помощью кнопки ниже 👇",
        reply_markup=get_city_request_keyboard(),
        parse_mode="HTML"
    )


@router.message(CityStates.waiting_for_city, F.location)
async def process_city_location(message: Message, state: FSMContext):
    """
    Обработка полученной геолокации от пользователя.
    """
    lat = message.location.latitude
    lon = message.location.longitude

    wait_msg = await message.answer("🔍 Определяю ваш населенный пункт по координатам...")

    city_name = await weather_service.reverse_geocode(lat, lon)

    # Сохраняем в базу данных
    await db.set_user_city(
        user_id=message.from_user.id,
        city=city_name,
        latitude=lat,
        longitude=lon,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await state.clear()

    await wait_msg.delete()
    await message.answer(
        f"✅ <b>Населенный пункт успешно сохранен:</b> {city_name}!\n\n"
        f"Теперь вы будете получать утренние сводки и предупреждения об осадках для этого места.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

    # Сразу покажем текущую погоду для подтверждения
    current = await weather_service.get_current_weather(city_name, lat, lon)
    if current:
        weather_text = (
            f"🌤 <b>Погода прямо сейчас в {current.city}:</b>\n\n"
            f"{current.icon_emoji} <b>{current.description}</b>\n"
            f"🌡 Температура: <b>{current.temp:+0.1f}°C</b> (ощущается как {current.feels_like:+0.1f}°C)\n"
            f"💨 Ветер: <b>{current.wind_speed} м/с</b>\n"
            f"💧 Влажность: <b>{current.humidity}%</b>\n"
            f"🧭 Давление: <b>{current.pressure_mmhg} мм рт. ст.</b>"
        )
        await message.answer(weather_text, parse_mode="HTML")


@router.message(CityStates.waiting_for_city, F.text)
async def process_city_text(message: Message, state: FSMContext):
    """
    Обработка текстового названия города.
    """
    city_query = message.text.strip()
    if city_query == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_keyboard())
        return

    wait_msg = await message.answer(f"🔍 Ищу населенный пункт «{city_query}»...")

    geo_data = await weather_service.geocode_city(city_query)

    if not geo_data:
        await wait_msg.delete()
        await message.answer(
            f"❌ К сожалению, населенный пункт <b>«{city_query}»</b> не найден.\n\n"
            f"Пожалуйста, проверьте правильность написания и попробуйте еще раз "
            f"или нажмите «❌ Отмена».",
            parse_mode="HTML"
        )
        return

    city_name, lat, lon = geo_data

    # Сохраняем в базу данных
    await db.set_user_city(
        user_id=message.from_user.id,
        city=city_name,
        latitude=lat,
        longitude=lon,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await state.clear()

    await wait_msg.delete()
    await message.answer(
        f"✅ <b>Населенный пункт установлен:</b> {city_name}!\n\n"
        f"Теперь бот настроен на этот город.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

    # Сразу покажем текущую погоду для проверки
    current = await weather_service.get_current_weather(city_name, lat, lon)
    if current:
        weather_text = (
            f"🌤 <b>Погода прямо сейчас в {current.city}:</b>\n\n"
            f"{current.icon_emoji} <b>{current.description}</b>\n"
            f"🌡 Температура: <b>{current.temp:+0.1f}°C</b> (ощущается как {current.feels_like:+0.1f}°C)\n"
            f"💨 Ветер: <b>{current.wind_speed} м/с</b>\n"
            f"💧 Влажность: <b>{current.humidity}%</b>\n"
            f"🧭 Давление: <b>{current.pressure_mmhg} мм рт. ст.</b>"
        )
        await message.answer(weather_text, parse_mode="HTML")


@router.message(Command("weather"))
@router.message(F.text == "🌤 Погода сейчас")
async def cmd_weather_now(message: Message, state: FSMContext):
    """
    Ручной запрос текущей погоды для сохраненного города.
    """
    await state.clear()
    user = await db.get_user(message.from_user.id)

    if not user or not user.get("city"):
        await state.set_state(CityStates.waiting_for_city)
        await message.answer(
            "⚠️ Вы еще не указали свой населенный пункт.\n"
            "Пожалуйста, введите название города или отправьте геолокацию:",
            reply_markup=get_city_request_keyboard()
        )
        return

    city = user["city"]
    lat = user["latitude"]
    lon = user["longitude"]

    wait_msg = await message.answer(f"⏳ Получаю данные о погоде для <b>{city}</b>...", parse_mode="HTML")

    current = await weather_service.get_current_weather(city, lat, lon)

    await wait_msg.delete()

    if not current:
        await message.answer(
            f"❌ Не удалось получить данные о погоде для города <b>{city}</b>. "
            f"Попробуйте повторить запрос позже.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return

    weather_text = (
        f"📍 <b>Погода в {current.city}:</b>\n\n"
        f"{current.icon_emoji} <b>{current.description}</b>\n"
        f"🌡 Температура: <b>{current.temp:+0.1f}°C</b>\n"
        f"🤔 Ощущается как: <b>{current.feels_like:+0.1f}°C</b>\n"
        f"💨 Скорость ветра: <b>{current.wind_speed} м/с</b>\n"
        f"💧 Влажность воздуха: <b>{current.humidity}%</b>\n"
        f"🧭 Атмосферное давление: <b>{current.pressure_mmhg} мм рт. ст.</b>\n"
    )
    await message.answer(weather_text, reply_markup=get_main_keyboard(), parse_mode="HTML")


@router.message(Command("forecast"))
@router.message(F.text == "📅 Прогноз на день")
async def cmd_daily_forecast(message: Message, state: FSMContext):
    """
    Ручной запрос подробного прогноза погоды на день.
    """
    await state.clear()
    user = await db.get_user(message.from_user.id)

    if not user or not user.get("city"):
        await state.set_state(CityStates.waiting_for_city)
        await message.answer(
            "⚠️ Вы еще не указали свой населенный пункт.\n"
            "Пожалуйста, введите название города:",
            reply_markup=get_city_request_keyboard()
        )
        return

    city = user["city"]
    lat = user["latitude"]
    lon = user["longitude"]

    wait_msg = await message.answer(f"⏳ Загружаю прогноз на день для <b>{city}</b>...", parse_mode="HTML")

    forecast_text = await weather_service.get_daily_forecast(city, lat, lon)

    await wait_msg.delete()

    if not forecast_text:
        await message.answer(
            f"❌ Не удалось загрузить прогноз для города <b>{city}</b>. Попробуйте позже.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return

    await message.answer(forecast_text, reply_markup=get_main_keyboard(), parse_mode="HTML")


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message):
    """
    Настройки уведомлений и информация о пользователе.
    """
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("city"):
        city_info = "Не задан"
        morning_notify = True
        afternoon_notify = True
    else:
        city_info = user["city"]
        morning_notify = bool(user.get("morning_notify", 1))
        afternoon_notify = bool(user.get("afternoon_notify", 1))

    text = (
        f"⚙️ <b>Настройки уведомлений:</b>\n\n"
        f"📍 Населенный пункт: <b>{city_info}</b>\n\n"
        f"Нажимайте на кнопки ниже, чтобы включить или отключить нужные уведомления:"
    )

    await message.answer(
        text,
        reply_markup=get_settings_keyboard(morning_notify, afternoon_notify),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "toggle_morning")
async def cb_toggle_morning(callback: CallbackQuery):
    """
    Переключение утреннего уведомления.
    """
    new_val = await db.toggle_notification(callback.from_user.id, "morning")
    user = await db.get_user(callback.from_user.id)

    morning_notify = bool(user.get("morning_notify", 1)) if user else bool(new_val)
    afternoon_notify = bool(user.get("afternoon_notify", 1)) if user else True

    status_text = "включен ✅" if morning_notify else "отключен ❌"
    await callback.answer(f"Утренний прогноз {status_text}")

    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(morning_notify, afternoon_notify)
    )


@router.callback_query(F.data == "toggle_afternoon")
async def cb_toggle_afternoon(callback: CallbackQuery):
    """
    Переключение дневной проверки осадков.
    """
    new_val = await db.toggle_notification(callback.from_user.id, "afternoon")
    user = await db.get_user(callback.from_user.id)

    morning_notify = bool(user.get("morning_notify", 1)) if user else True
    afternoon_notify = bool(user.get("afternoon_notify", 1)) if user else bool(new_val)

    status_text = "включена ✅" if afternoon_notify else "отключена ❌"
    await callback.answer(f"Проверка осадков {status_text}")

    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(morning_notify, afternoon_notify)
    )


@router.callback_query(F.data == "refresh_settings")
async def cb_refresh_settings(callback: CallbackQuery):
    """
    Обновление клавиатуры настроек.
    """
    user = await db.get_user(callback.from_user.id)
    morning_notify = bool(user.get("morning_notify", 1)) if user else True
    afternoon_notify = bool(user.get("afternoon_notify", 1)) if user else True

    await callback.answer("Настройки обновлены")
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(morning_notify, afternoon_notify)
    )
