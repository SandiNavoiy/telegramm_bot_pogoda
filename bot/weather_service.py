"""
Модуль для работы с сервисами погоды.
Поддерживает работу с:
1. OpenWeatherMap API (если задан OPENWEATHER_API_KEY в .env)
2. Open-Meteo API (бесплатный сервис, не требующий API ключа)
"""

import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from bot.config import config


@dataclass
class WeatherData:
    """Структура текущей погоды"""
    city: str
    temp: float
    feels_like: float
    description: str
    humidity: int
    pressure_mmhg: int
    wind_speed: float
    icon_emoji: str


@dataclass
class PrecipitationWarning:
    """Структура предупреждения об осадках"""
    has_precipitation: bool
    city: str
    events: List[Dict[str, Any]]
    warning_text: str


class WeatherService:
    """
    Асинхронный сервис для получения данных о погоде.
    """

    # Соответствие кодов WMO (Open-Meteo) и текстовых описаний с эмодзи
    WMO_CODES = {
        0: ("Ясно ☀️", "ясно", "☀️"),
        1: ("Преимущественно ясно 🌤", "преимущественно ясно", "🌤"),
        2: ("Переменная облачность ⛅", "переменная облачность", "⛅"),
        3: ("Пасмурно ☁️", "пасмурно", "☁️"),
        45: ("Туман 🌫", "туман", "🌫"),
        48: ("Оседающий инейный туман 🌫", "инейный туман", "🌫"),
        51: ("Легкая морось 🌦", "легкая морось", "🌦"),
        53: ("Умеренная морось 🌧", "умеренная морось", "🌧"),
        55: ("Плотная морось 🌧", "плотная морось", "🌧"),
        56: ("Ледяная морось 🌨", "ледяная морось", "🌨"),
        57: ("Плотная ледяная морось 🌨", "плотная ледяная морось", "🌨"),
        61: ("Небольшой дождь 🌧", "небольшой дождь", "🌧"),
        63: ("Умеренный дождь 🌧", "умеренный дождь", "🌧"),
        65: ("Сильный дождь 🌧", "сильный дождь", "🌧"),
        66: ("Ледяной дождь 🌨", "ледяной дождь", "🌨"),
        67: ("Сильный ледяной дождь 🌨", "сильный ледяной дождь", "🌨"),
        71: ("Небольшой снегопад 🌨", "небольшой снегопад", "🌨"),
        73: ("Умеренный снегопад 🌨", "умеренный снегопад", "🌨"),
        75: ("Сильный снегопад ❄️", "сильный снегопад", "❄️"),
        77: ("Снежные зерна ❄️", "снежные зерна", "❄️"),
        80: ("Слабый ливневый дождь 🌦", "слабый ливень", "🌦"),
        81: ("Умеренный ливневый дождь 🌧", "умеренный ливень", "🌧"),
        82: ("Очень сильный ливень ⛈", "очень сильный ливень", "⛈"),
        85: ("Небольшой снежный ливень 🌨", "небольшой снежный ливень", "🌨"),
        86: ("Сильный снежный ливень ❄️", "сильный снежный ливень", "❄️"),
        95: ("Гроза ⚡", "гроза", "⚡"),
        96: ("Гроза с небольшим градом ⛈", "гроза с градом", "⛈"),
        99: ("Гроза с сильным градом ⛈", "сильная гроза с градом", "⛈"),
    }

    # Коды WMO, означающие осадки
    PRECIPITATION_WMO_CODES = {
        51, 52, 53, 54, 55, 56, 57, 61, 62, 63, 64, 65, 66, 67,
        71, 72, 73, 74, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99
    }

    @staticmethod
    def _hpa_to_mmhg(hpa: float) -> int:
        """Перевод давления из гПа в мм рт. ст."""
        return int(round(hpa * 0.750062))

    @staticmethod
    def _get_owm_emoji(weather_id: int, icon: str = "") -> str:
        """Получить эмодзи по коду погоды OpenWeatherMap"""
        if 200 <= weather_id < 300:
            return "⛈"
        elif 300 <= weather_id < 400:
            return "🌦"
        elif 500 <= weather_id < 600:
            return "🌧"
        elif 600 <= weather_id < 700:
            return "🌨"
        elif 700 <= weather_id < 800:
            return "🌫"
        elif weather_id == 800:
            return "☀️" if "d" in icon else "🌙"
        elif weather_id == 801:
            return "🌤"
        elif weather_id in (802, 803):
            return "⛅"
        else:
            return "☁️"

    async def geocode_city(self, city_name: str) -> Optional[Tuple[str, float, float]]:
        """
        Определение координат (широта, долгота) и официального названия по имени города.

        :param city_name: Название города/населенного пункта.
        :return: (formatted_name, lat, lon) или None, если город не найден.
        """
        # Если есть ключ OpenWeatherMap, пробуем через него
        if config.openweather_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.openweathermap.org/geo/1.0/direct"
                    params = {
                        "q": city_name,
                        "limit": 1,
                        "appid": config.openweather_api_key
                    }
                    async with session.get(url, params=params, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and len(data) > 0:
                                item = data[0]
                                ru_name = item.get("local_names", {}).get("ru", item.get("name"))
                                country = item.get("country", "")
                                name = f"{ru_name}, {country}" if country else ru_name
                                return name, float(item["lat"]), float(item["lon"])
            except Exception:
                pass

        # Бесплатный сервис Open-Meteo Geocoding
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://geocoding-api.open-meteo.com/v1/search"
                params = {
                    "name": city_name,
                    "count": 1,
                    "language": "ru",
                    "format": "json"
                }
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results")
                        if results and len(results) > 0:
                            item = results[0]
                            name = item.get("name")
                            country = item.get("country")
                            admin1 = item.get("admin1")
                            full_name = name
                            if admin1 and admin1 != name:
                                full_name += f" ({admin1})"
                            if country:
                                full_name += f", {country}"
                            return full_name, float(item["latitude"]), float(item["longitude"])
        except Exception:
            pass

        return None

    async def reverse_geocode(self, lat: float, lon: float) -> str:
        """
        Определение названия населенного пункта по координатам.

        :param lat: Широта.
        :param lon: Долгота.
        :return: Название населенного пункта.
        """
        if config.openweather_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.openweathermap.org/geo/1.0/reverse"
                    params = {
                        "lat": lat,
                        "lon": lon,
                        "limit": 1,
                        "appid": config.openweather_api_key
                    }
                    async with session.get(url, params=params, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and len(data) > 0:
                                item = data[0]
                                ru_name = item.get("local_names", {}).get("ru", item.get("name"))
                                country = item.get("country", "")
                                return f"{ru_name}, {country}" if country else ru_name
            except Exception:
                pass

        # Реверс-геокодинг через Open-Meteo BigDataCloud / Nominatim fallback
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.bigdatacloud.net/data/reverse-geocode-client"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "localityLanguage": "ru"
                }
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        city = data.get("city") or data.get("locality") or data.get("principalSubdivision")
                        country = data.get("countryName", "")
                        if city:
                            return f"{city}, {country}" if country else city
        except Exception:
            pass

        return f"Координаты: {lat:.3f}, {lon:.3f}"

    async def get_current_weather(self, city: str, lat: float, lon: float) -> Optional[WeatherData]:
        """
        Получить текущую погоду для заданного места.

        :param city: Название населенного пункта.
        :param lat: Широта.
        :param lon: Долгота.
        :return: Объект WeatherData или None при ошибке.
        """
        # 1. Если настроен OpenWeatherMap
        if config.openweather_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.openweathermap.org/data/2.5/weather"
                    params = {
                        "lat": lat,
                        "lon": lon,
                        "appid": config.openweather_api_key,
                        "units": "metric",
                        "lang": "ru"
                    }
                    async with session.get(url, params=params, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            main = data.get("main", {})
                            weather_list = data.get("weather", [{}])
                            weather_item = weather_list[0] if weather_list else {}
                            wind = data.get("wind", {})

                            temp = round(main.get("temp", 0), 1)
                            feels_like = round(main.get("feels_like", 0), 1)
                            description = weather_item.get("description", "без осадков").capitalize()
                            humidity = main.get("humidity", 0)
                            pressure_hpa = main.get("pressure", 1013)
                            pressure_mmhg = self._hpa_to_mmhg(pressure_hpa)
                            wind_speed = round(wind.get("speed", 0), 1)
                            icon_emoji = self._get_owm_emoji(weather_item.get("id", 800), weather_item.get("icon", ""))

                            return WeatherData(
                                city=city,
                                temp=temp,
                                feels_like=feels_like,
                                description=description,
                                humidity=humidity,
                                pressure_mmhg=pressure_mmhg,
                                wind_speed=wind_speed,
                                icon_emoji=icon_emoji
                            )
            except Exception:
                pass

        # 2. Open-Meteo (бесплатный провайдер)
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,surface_pressure,wind_speed_10m",
                    "timezone": "auto"
                }
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get("current", {})
                        temp = round(current.get("temperature_2m", 0), 1)
                        feels_like = round(current.get("apparent_temperature", 0), 1)
                        weather_code = current.get("weather_code", 0)
                        info = self.WMO_CODES.get(weather_code, ("Ясно ☀️", "ясно", "☀️"))
                        description = info[0]
                        icon_emoji = info[2]
                        humidity = int(current.get("relative_humidity_2m", 0))
                        pressure_hpa = current.get("surface_pressure", 1013)
                        pressure_mmhg = self._hpa_to_mmhg(pressure_hpa)
                        wind_speed = round(current.get("wind_speed_10m", 0), 1)

                        return WeatherData(
                            city=city,
                            temp=temp,
                            feels_like=feels_like,
                            description=description,
                            humidity=humidity,
                            pressure_mmhg=pressure_mmhg,
                            wind_speed=wind_speed,
                            icon_emoji=icon_emoji
                        )
        except Exception:
            pass

        return None

    async def get_daily_forecast(self, city: str, lat: float, lon: float) -> Optional[str]:
        """
        Получить подробный прогноз погоды на сегодня (для утренней рассылки).

        :param city: Название населенного пункта.
        :param lat: Широта.
        :param lon: Долгота.
        :return: Текст сообщения с прогнозом.
        """
        # Попробуем Open-Meteo для получения почасового прогноза на сегодня
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
                    "timezone": "auto",
                    "forecast_days": 1
                }
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        daily = data.get("daily", {})
                        temp_min = round(daily.get("temperature_2m_min", [0])[0], 1)
                        temp_max = round(daily.get("temperature_2m_max", [0])[0], 1)
                        max_pop = daily.get("precipitation_probability_max", [0])[0]
                        daily_code = daily.get("weather_code", [0])[0]
                        desc, _, icon = self.WMO_CODES.get(daily_code, ("Ясно ☀️", "ясно", "☀️"))

                        # Почасовые срезы (утро 09:00, день 15:00, вечер 21:00)
                        hourly = data.get("hourly", {})
                        times = hourly.get("time", [])
                        temps = hourly.get("temperature_2m", [])
                        codes = hourly.get("weather_code", [])

                        slots = []
                        for target_hour, label in [(9, "Утро 🌅"), (15, "День ☀️"), (21, "Вечер 🌆")]:
                            if len(times) > target_hour:
                                t = round(temps[target_hour], 1)
                                c = codes[target_hour]
                                _, _, h_icon = self.WMO_CODES.get(c, ("", "", "🌤"))
                                slots.append(f"  • {label}: {t:+0.1f}°C {h_icon}")

                        slots_str = "\n".join(slots)

                        msg = (
                            f"🌅 <b>Доброе утро! Прогноз на сегодня</b>\n"
                            f"📍 <b>{city}</b>\n\n"
                            f"{icon} <b>Погода в целом:</b> {desc}\n"
                            f"🌡 <b>Температура:</b> от {temp_min:+0.1f}°C до {temp_max:+0.1f}°C\n"
                            f"💧 <b>Вероятность осадков:</b> {max_pop}%\n\n"
                            f"<b>В течение дня:</b>\n{slots_str}\n\n"
                            f"Желаем отличного и продуктивного дня! ✨"
                        )
                        return msg
        except Exception:
            pass

        # Резервный вариант через текущую погоду
        current = await self.get_current_weather(city, lat, lon)
        if current:
            return (
                f"🌅 <b>Доброе утро! Погода на сегодня</b>\n"
                f"📍 <b>{city}</b>\n\n"
                f"{current.icon_emoji} <b>{current.description}</b>\n"
                f"🌡 <b>Температура:</b> {current.temp:+0.1f}°C (ощущается как {current.feels_like:+0.1f}°C)\n"
                f"💨 <b>Ветер:</b> {current.wind_speed} м/с\n"
                f"💧 <b>Влажность:</b> {current.humidity}%\n"
                f"🧭 <b>Давление:</b> {current.pressure_mmhg} мм рт. ст.\n\n"
                f"Хорошего вам дня! ☀️"
            )

        return None

    async def check_afternoon_precipitation(self, city: str, lat: float, lon: float) -> PrecipitationWarning:
        """
        Проверить прогноз погоды на вторую половину дня (после 14:00 до полуночи)
        на наличие осадков (дождь, снег, гроза).

        :param city: Название населенного пункта.
        :param lat: Широта.
        :param lon: Долгота.
        :return: Объект PrecipitationWarning.
        """
        # 1. Проверяем через OpenWeatherMap если есть ключ
        if config.openweather_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.openweathermap.org/data/2.5/forecast"
                    params = {
                        "lat": lat,
                        "lon": lon,
                        "appid": config.openweather_api_key,
                        "units": "metric",
                        "lang": "ru"
                    }
                    async with session.get(url, params=params, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            forecast_list = data.get("list", [])
                            today_str = datetime.now().strftime("%Y-%m-%d")

                            precipitation_slots = []
                            for item in forecast_list:
                                dt_txt = item.get("dt_txt", "")
                                # Проверяем сегодняшнюю дату и время от 14:00 до 23:59
                                if dt_txt.startswith(today_str):
                                    hour = int(dt_txt.split(" ")[1].split(":")[0])
                                    if hour >= 14:
                                        weather_items = item.get("weather", [])
                                        pop = item.get("pop", 0)  # Вероятность осадков 0..1
                                        rain = item.get("rain", {}).get("3h", 0)
                                        snow = item.get("snow", {}).get("3h", 0)

                                        # Коды осадков: 2xx (гроза), 3xx (морось), 5xx (дождь), 6xx (снег)
                                        has_precip = False
                                        precip_desc = ""
                                        for w in weather_items:
                                            wid = w.get("id", 800)
                                            if 200 <= wid < 700 or rain > 0 or snow > 0 or pop >= 0.4:
                                                has_precip = True
                                                precip_desc = w.get("description", "осадки").capitalize()
                                                break

                                        if has_precip:
                                            temp = round(item.get("main", {}).get("temp", 0), 1)
                                            precipitation_slots.append({
                                                "time": f"{hour:02d}:00",
                                                "desc": precip_desc,
                                                "temp": temp,
                                                "pop": int(pop * 100),
                                                "rain": rain,
                                                "snow": snow
                                            })

                            if precipitation_slots:
                                lines = []
                                has_snow = False
                                for slot in precipitation_slots:
                                    if "снег" in slot["desc"].lower() or slot["snow"] > 0:
                                        has_snow = True
                                    lines.append(f"  • В <b>{slot['time']}</b>: {slot['desc']}, {slot['temp']:+0.1f}°C (вероятность {slot['pop']}%)")

                                advice = "Одевайтесь теплее и берегите себя! ❄️🧣" if has_snow else "Не забудьте взять с собой зонт! ☔🧥"
                                warning_text = (
                                    f"⚠️ <b>ВНИМАНИЕ: Осадки во второй половине дня!</b>\n"
                                    f"📍 <b>{city}</b>\n\n"
                                    f"По прогнозу с 14:00 до конца дня ожидаются осадки:\n"
                                    + "\n".join(lines) + "\n\n"
                                    f"💡 <i>{advice}</i>"
                                )
                                return PrecipitationWarning(
                                    has_precipitation=True,
                                    city=city,
                                    events=precipitation_slots,
                                    warning_text=warning_text
                                )
            except Exception:
                pass

        # 2. Проверяем через Open-Meteo
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "temperature_2m,precipitation_probability,precipitation,rain,showers,snowfall,weather_code",
                    "timezone": "auto",
                    "forecast_days": 1
                }
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hourly = data.get("hourly", {})
                        times = hourly.get("time", [])
                        temps = hourly.get("temperature_2m", [])
                        pops = hourly.get("precipitation_probability", [])
                        precips = hourly.get("precipitation", [])
                        snowfalls = hourly.get("snowfall", [])
                        codes = hourly.get("weather_code", [])

                        precipitation_slots = []
                        # Проверяем часы с 14 по 23
                        for i, time_str in enumerate(times):
                            hour = int(time_str.split("T")[1].split(":")[0])
                            if hour >= 14:
                                code = codes[i] if i < len(codes) else 0
                                pop = pops[i] if i < len(pops) else 0
                                precip = precips[i] if i < len(precips) else 0
                                snow = snowfalls[i] if i < len(snowfalls) else 0
                                temp = round(temps[i], 1) if i < len(temps) else 0

                                if code in self.PRECIPITATION_WMO_CODES or precip > 0.1 or snow > 0 or pop >= 40:
                                    desc, _, icon = self.WMO_CODES.get(code, ("Осадки 🌧", "осадки", "🌧"))
                                    precipitation_slots.append({
                                        "time": f"{hour:02d}:00",
                                        "desc": desc,
                                        "temp": temp,
                                        "pop": pop,
                                        "icon": icon,
                                        "snow": snow
                                    })

                        if precipitation_slots:
                            lines = []
                            has_snow = False
                            for slot in precipitation_slots:
                                if "снег" in slot["desc"].lower() or slot.get("snow", 0) > 0:
                                    has_snow = True
                                lines.append(f"  • В <b>{slot['time']}</b>: {slot['desc']}, {slot['temp']:+0.1f}°C (вероятность {slot['pop']}%)")

                            advice = "Одевайтесь теплее и будьте осторожны на дорогах! ❄️🧣" if has_snow else "Не забудьте взять с собой зонт! ☔🧥"
                            warning_text = (
                                f"⚠️ <b>ВНИМАНИЕ: Осадки во второй половине дня!</b>\n"
                                f"📍 <b>{city}</b>\n\n"
                                f"По прогнозу с 14:00 до конца дня ожидаются осадки:\n"
                                + "\n".join(lines) + "\n\n"
                                f"💡 <i>{advice}</i>"
                            )
                            return PrecipitationWarning(
                                has_precipitation=True,
                                city=city,
                                events=precipitation_slots,
                                warning_text=warning_text
                            )
        except Exception:
            pass

        return PrecipitationWarning(
            has_precipitation=False,
            city=city,
            events=[],
            warning_text=""
        )


# Глобальный экземпляр сервиса погоды
weather_service = WeatherService()
