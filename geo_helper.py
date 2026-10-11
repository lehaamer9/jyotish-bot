"""
Модуль геокодинга и определения часового пояса.
Преобразует название города в координаты (широта, долгота) и смещение UTC (timezone_offset).
"""
from typing import Tuple, Optional
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

_geolocator = Nominatim(user_agent="jyotish_telegram_bot_v1")
_tf = TimezoneFinder()


def resolve_location(place_name: str, target_date: Optional[datetime] = None) -> Tuple[float, float, float, str]:
    """
    Разрешить название места в (latitude, longitude, timezone_offset_hours, formatted_address).
    
    :param place_name: Название города (например, "Москва", "Rome, Italy", "Delhi")
    :param target_date: Дата для расчёта смещения с учётом исторического летнего времени (DST)
    :return: (lat, lon, tz_offset, display_name)
    :raises ValueError: если место не найдено или часовой пояс не определен
    """
    location = _geolocator.geocode(place_name, language="ru")
    if not location:
        # Попробуем без указания языка
        location = _geolocator.geocode(place_name)
        if not location:
            raise ValueError(f"Место '{place_name}' не найдено. Укажи более крупный город или страну.")

    lat = location.latitude
    lon = location.longitude

    # Определяем название часового пояса (e.g. 'Europe/Moscow')
    tz_str = _tf.timezone_at(lat=lat, lng=lon)
    if not tz_str:
        # Fallback по долготе (приблизительно lon / 15)
        approx_offset = round(lon / 15.0, 1)
        return lat, lon, approx_offset, location.address

    # Рассчитываем смещение на указанную дату (важно для DST и смены часовых поясов)
    dt = target_date or datetime.now()
    timezone = pytz.timezone(tz_str)
    
    try:
        localized = timezone.localize(dt)
        offset_seconds = localized.utcoffset().total_seconds()
        offset_hours = offset_seconds / 3600.0
    except Exception:
        # Если дата не локализуется напрямую (исторические аномалии)
        offset_hours = timezone.utcoffset(dt).total_seconds() / 3600.0

    return lat, lon, offset_hours, location.address

