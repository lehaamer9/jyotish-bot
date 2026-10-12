"""
Модуль умного парсинга строкового ввода данных рождения.
Позволяет пользователю вводить все данные натальной карты одной строкой:
«Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город» или вариации.
"""

import re
from datetime import date, time
from typing import Optional, Dict, Any


def parse_one_line_profile(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Умный парсер строки для быстрого создания или обновления натального профиля.
    
    Поддерживаемые форматы:
    - «Александр, 20.06.1996, 08:25, Горно-Алтайск»
    - «Александр 15.05.1990 10:30 Москва»
    - «20.06.1996 08:25 Горно-Алтайск»
    - «15.05.1990 10:30 Москва, Александр»
    - «/chart Александр, 20.06.1996, 08:25, Горно-Алтайск»
    - «Александр, 15.05.1990» (частичный ввод: только дата и имя)
    
    Возвращает словарь:
    {
        "name": Optional[str],
        "dob": Optional[date],
        "tob": Optional[time],
        "city": Optional[str],
        "is_complete": bool
    }
    или None, если дата не найдена в строке.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None

    # Очистка команд и упоминаний бота
    text = re.sub(r"^/(?:chart|natal|newprofile)\b\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"^@\w+\s*", "", text).strip()
    if not text:
        return None

    # Поиск даты: ДД.ММ.ГГГГ (разделители: точка, дефис, слэш)
    date_match = re.search(r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b', text)
    if not date_match:
        return None

    d_str, m_str, y_str = date_match.group(1), date_match.group(2), date_match.group(3)
    try:
        dob = date(int(y_str), int(m_str), int(d_str))
    except ValueError:
        return None

    d_start, d_end = date_match.span()

    # Маскируем дату пробелами, чтобы цифры даты не совпадали с временем
    masked = text[:d_start] + (" " * (d_end - d_start)) + text[d_end:]

    # Поиск времени: ЧЧ:ММ или ЧЧ.ММ (0-23:00-59)
    # Игнорируем предлог 'в'
    time_match = re.search(r'(?:\bв\s+)?\b([01]?\d|2[0-3])[:.]([0-5]\d)\b', masked, flags=re.IGNORECASE)
    
    tob: Optional[time] = None
    t_start, t_end = -1, -1
    if time_match:
        h_str, min_str = time_match.group(1), time_match.group(2)
        try:
            tob = time(int(h_str), int(min_str))
            t_start, t_end = time_match.span()
        except ValueError:
            tob = None

    name: Optional[str] = None
    city: Optional[str] = None

    if tob is not None:
        first_s, first_e = (d_start, d_end) if d_start < t_start else (t_start, t_end)
        second_s, second_e = (t_start, t_end) if d_start < t_start else (d_start, d_end)

        part_before = text[:first_s].strip(" ,;:\t\n-")
        part_middle = text[first_e:second_s].strip(" ,;:\t\n-")
        part_after = text[second_e:].strip(" ,;:\t\n-")

        # Очистка вводных предлогов из промежуточной части
        part_middle = re.sub(r'^(?:в|родился\s+в|родилась\s+в)\s*', '', part_middle, flags=re.IGNORECASE).strip(" ,;:\t\n-")
        part_after = re.sub(r'^(?:в\s+г\.|в\s+город|в\s+|г\.\s*|город\s+)', '', part_after, flags=re.IGNORECASE).strip(" ,;:\t\n-")

        if part_before and part_after:
            name = part_before
            city = part_after
        elif not part_before and part_middle and part_after:
            name = part_middle
            city = part_after
        elif part_before and part_middle and not part_after:
            name = part_before
            city = part_middle
        elif not part_before and not part_middle and part_after:
            # Случай: «15.05.1990 10:30 Москва, Александр» или «15.05.1990 10:30 Москва»
            if "," in part_after:
                parts = [p.strip() for p in part_after.split(",") if p.strip()]
                if len(parts) >= 2:
                    city = parts[0]
                    name = parts[1]
                else:
                    city = parts[0]
            else:
                city = part_after
    else:
        # Только дата (без времени)
        part_before = text[:d_start].strip(" ,;:\t\n-")
        part_after = text[d_end:].strip(" ,;:\t\n-")
        if part_before:
            name = part_before
        if part_after:
            city = part_after

    # Очистка имени от префиксов вроде "Имя:", "Профиль:"
    if name:
        name = re.sub(r'^(?:имя\s*[:=-]?\s*|профиль\s*[:=-]?\s*|меня\s+зовут\s+)', '', name, flags=re.IGNORECASE).strip(" ,;:\t\n-")
        name = re.sub(r'\s+(?:родился|родилась)\b.*', '', name, flags=re.IGNORECASE).strip(" ,;:\t\n-")
        if not name:
            name = None

    # Очистка города
    if city:
        city = re.sub(r'^(?:в\s+г\.|в\s+город|в\s+|г\.\s*|город\s+)', '', city, flags=re.IGNORECASE).strip(" ,;:\t\n-")
        if not city:
            city = None

    is_complete = bool(dob and tob and city)

    return {
        "name": name,
        "dob": dob,
        "tob": tob,
        "city": city,
        "is_complete": is_complete
    }
