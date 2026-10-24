"""
Расчётный движок ведической астрологии (Джьотиш).
Обёртка над jyotishganit для использования в Telegram-боте.
"""
from datetime import datetime, date
from typing import Optional, Union
from jyotishganit import calculate_birth_chart, get_birth_chart_json_string
import json
from i18n import (
    normalize_language,
    get_planet_name,
    get_sign_name,
    get_dignity_name,
)


# Названия планет на русском
PLANET_NAMES_RU = {
    "Sun": "Сурья (Солнце)", "Moon": "Чандра (Луна)", "Mars": "Мангала (Марс)",
    "Mercury": "Будха (Меркурий)", "Jupiter": "Гуру (Юпитер)", "Venus": "Шукра (Венера)",
    "Saturn": "Шани (Сатурн)", "Rahu": "Раху", "Ketu": "Кету"
}

# Названия знаков на русском
SIGN_NAMES_RU = {
    "Aries": "Овен (Меша)", "Taurus": "Телец (Вришабха)", "Gemini": "Близнецы (Митхуна)",
    "Cancer": "Рак (Карка)", "Leo": "Лев (Симха)", "Virgo": "Дева (Канья)",
    "Libra": "Весы (Тула)", "Scorpio": "Скорпион (Вришчика)", "Sagittarius": "Стрелец (Дхану)",
    "Capricorn": "Козерог (Макара)", "Aquarius": "Водолей (Кумбха)", "Pisces": "Рыбы (Мина)"
}

# Названия домов (бхав) на русском
HOUSE_PURPOSES_RU = {
    "Dharma": "Дхарма", "Artha": "Артха", "Kama": "Кама", "Moksha": "Мокша",
    "Kendra": "Кендра", "Trikona": "Трикона", "Trik": "Трик", "Upachaya": "Упачая",
    "Maraka": "Марака"
}


def compute_chart(birth_dt: datetime, lat: float, lon: float, tz_offset: float,
                  name: str = "User") -> dict:
    """
    Рассчитать полную натальную карту.
    Возвращает структурированный dict со всеми данными.
    """
    chart = calculate_birth_chart(
        birth_date=birth_dt,
        latitude=lat,
        longitude=lon,
        timezone_offset=tz_offset,
        name=name
    )
    return _extract_chart_data(chart)


def _extract_chart_data(chart) -> dict:
    """Извлечь данные из объекта chart в удобный словарь."""
    data = {
        "person": chart.person.name if hasattr(chart.person, 'name') else str(chart.person),
        "ayanamsa": str(chart.ayanamsa) if chart.ayanamsa else "Chitra Paksha",
        "panchanga": _extract_panchanga(chart.panchanga),
        "planets": _extract_planets(chart.d1_chart.planets),
        "houses": _extract_houses(chart.d1_chart.houses),
        "dashas": _extract_dashas(chart.dashas),
        "ashtakavarga": _extract_ashtakavarga(chart.ashtakavarga),
    }
    return data


def _extract_panchanga(pan) -> dict:
    """Извлечь данные панчанги."""
    return {
        "tithi": str(pan.tithi) if pan.tithi else "N/A",
        "nakshatra": str(pan.nakshatra) if pan.nakshatra else "N/A",
        "yoga": str(pan.yoga) if pan.yoga else "N/A",
        "karana": str(pan.karana) if pan.karana else "N/A",
        "vaara": str(pan.vaara) if pan.vaara else "N/A",
    }


def _extract_planets(planets) -> list:
    """Извлечь данные о планетах."""
    result = []
    for p in planets:
        planet = {
            "name": p.celestial_body,
            "name_ru": PLANET_NAMES_RU.get(p.celestial_body, p.celestial_body),
            "sign": p.sign,
            "sign_ru": SIGN_NAMES_RU.get(p.sign, p.sign),
            "degrees": round(float(p.sign_degrees), 2),
            "nakshatra": p.nakshatra,
            "pada": p.pada,
            "house": p.house,
            "motion": p.motion_type,
            "dignity": p.dignities.dignity if p.dignities else "N/A",
            "lordship_houses": p.has_lordship_houses if p.has_lordship_houses else [],
        }
        # Шадбала (общая сила)
        if p.shadbala and isinstance(p.shadbala, dict):
            sb = p.shadbala.get("Shadbala", {})
            planet["shadbala_total"] = round(float(sb.get("Total", 0)), 1)
            planet["shadbala_rupas"] = round(float(sb.get("Rupas", 0)), 2)
        result.append(planet)
    return result


def _extract_houses(houses) -> list:
    """Извлечь данные о домах."""
    result = []
    for h in houses:
        house_data = {
            "number": h.number,
            "sign": h.sign,
            "sign_ru": SIGN_NAMES_RU.get(h.sign, h.sign),
            "lord": h.lord,
            "lord_ru": PLANET_NAMES_RU.get(h.lord, h.lord),
            "occupants": [p.celestial_body for p in h.occupants] if h.occupants else [],
            "purposes": h.purposes if h.purposes else [],
            "lord_placed_house": h.lord_placed_house,
        }
        result.append(house_data)
    return result


def _extract_dashas(dashas_obj) -> dict:
    """Извлечь данные Вимшоттари Даша."""
    result = {"balance": {}, "periods": []}

    if not dashas_obj:
        return result

    # Баланс даши при рождении
    if hasattr(dashas_obj, 'balance') and dashas_obj.balance:
        for planet, years in dashas_obj.balance.items():
            result["balance"][planet] = round(float(years), 3)

    # Маха-даши и антар-даши
    if hasattr(dashas_obj, 'all') and dashas_obj.all:
        maha_dashas = dashas_obj.all.get('mahadashas', {})
        for planet, md_data in maha_dashas.items():
            period = {
                "planet": planet,
                "planet_ru": PLANET_NAMES_RU.get(planet, planet),
                "start": md_data['start'].strftime("%d.%m.%Y"),
                "end": md_data['end'].strftime("%d.%m.%Y"),
                "antardashas": []
            }
            # Антар-даши (подпериоды)
            for ad_planet, ad_data in md_data.get('antardashas', {}).items():
                antar = {
                    "planet": ad_planet,
                    "planet_ru": PLANET_NAMES_RU.get(ad_planet, ad_planet),
                    "start": ad_data['start'].strftime("%d.%m.%Y"),
                    "end": ad_data['end'].strftime("%d.%m.%Y"),
                }
                period["antardashas"].append(antar)
            result["periods"].append(period)

    return result


def _extract_ashtakavarga(av) -> Optional[dict]:
    """Извлечь данные Аштакаварги если доступны."""
    if not av:
        return None
    try:
        if hasattr(av, 'to_dict'):
            return av.to_dict()
        return str(av)
    except Exception:
        return None


def get_current_dasha(dashas_or_chart: dict, now: Optional[Union[datetime, date]] = None) -> dict:
    """Определить текущий период Маха-Даша и Антар-Даша."""
    if now is None:
        now = datetime.now()
    elif isinstance(now, date) and not isinstance(now, datetime):
        now = datetime.combine(now, datetime.min.time())

    dashas = dashas_or_chart.get("dashas", dashas_or_chart) if isinstance(dashas_or_chart, dict) else {}
    current = {"maha_dasha": None, "antar_dasha": None}

    for period in dashas.get("periods", []):
        try:
            start = datetime.strptime(period["start"], "%d.%m.%Y")
            end = datetime.strptime(period["end"], "%d.%m.%Y")
        except Exception:
            continue
        if start <= now <= end:
            current["maha_dasha"] = {
                "planet": period["planet"],
                "planet_ru": period.get("planet_ru", period["planet"]),
                "start": period["start"],
                "end": period["end"],
            }
            # Ищем антар-дашу
            for ad in period.get("antardashas", []):
                try:
                    ad_start = datetime.strptime(ad["start"], "%d.%m.%Y")
                    ad_end = datetime.strptime(ad["end"], "%d.%m.%Y")
                except Exception:
                    continue
                if ad_start <= now <= ad_end:
                    current["antar_dasha"] = ad
                    break
            break

    return current


# Знаки зодиака в порядке (для расчёта Саде-Сати)
SIGNS_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Экзальтация и собственные знаки для Панча Махапуруша
PLANET_EXALTATION = {
    "Mars": "Capricorn", "Mercury": "Virgo", "Jupiter": "Cancer",
    "Venus": "Pisces", "Saturn": "Libra",
}
PLANET_OWN_SIGNS = {
    "Mars": ["Aries", "Scorpio"], "Mercury": ["Gemini", "Virgo"],
    "Jupiter": ["Sagittarius", "Pisces"], "Venus": ["Taurus", "Libra"],
    "Saturn": ["Capricorn", "Aquarius"],
}
KENDRA_HOUSES = [1, 4, 7, 10]
TRIKONA_HOUSES = [1, 5, 9]
DHANA_HOUSES = [2, 5, 9, 11]


# Астрономическая таблица ингрессий транзитного Сатурна по сидерическим знакам (Лахири) 1975–2065
SATURN_TRANSITS = [
    ("1975-07-23", "Cancer"), ("1977-09-07", "Leo"), ("1979-11-04", "Virgo"),
    ("1982-10-06", "Libra"), ("1984-12-21", "Scorpio"), ("1987-12-17", "Sagittarius"),
    ("1990-03-21", "Capricorn"), ("1993-03-05", "Aquarius"), ("1995-06-02", "Pisces"),
    ("1998-04-17", "Aries"), ("2000-06-06", "Taurus"), ("2002-07-23", "Gemini"),
    ("2004-09-05", "Cancer"), ("2006-11-01", "Leo"), ("2009-09-09", "Virgo"),
    ("2011-11-15", "Libra"), ("2014-11-02", "Scorpio"), ("2017-01-26", "Sagittarius"),
    ("2020-01-24", "Capricorn"), ("2023-01-17", "Aquarius"), ("2025-03-29", "Pisces"),
    ("2028-02-23", "Aries"), ("2030-04-17", "Taurus"), ("2032-05-30", "Gemini"),
    ("2034-07-13", "Cancer"), ("2036-08-27", "Leo"), ("2038-10-22", "Virgo"),
    ("2041-01-28", "Libra"), ("2043-12-12", "Scorpio"), ("2046-12-07", "Sagittarius"),
    ("2049-03-06", "Capricorn"), ("2052-02-25", "Aquarius"), ("2054-05-14", "Pisces"),
    ("2057-04-07", "Aries"), ("2059-05-27", "Taurus"), ("2061-07-11", "Gemini"),
    ("2063-08-24", "Cancer"), ("2065-10-13", "Leo"),
]


def _format_date_ru(iso_str: Optional[str]) -> str:
    """Форматирование даты YYYY-MM-DD в ДД.ММ.ГГГГ."""
    if not iso_str:
        return ""
    try:
        parts = iso_str.split("-")
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    except Exception:
        return iso_str


def check_sade_sati(chart_or_moon_sign) -> dict:
    """Проверить статус Саде-Сати (транзит Сатурна относительно натальной Луны).

    Принимает либо chart_data (dict), либо строку со знаком Луны (str).
    Возвращает dict с полями: active, phase, phase_ru, saturn_sign, moon_sign,
    current_cycle, next_cycle, prev_cycle, description.
    """
    from datetime import date as _date

    if isinstance(chart_or_moon_sign, dict):
        natal_moon_sign = None
        for p in chart_or_moon_sign.get("planets", []):
            if p.get("name") == "Moon":
                natal_moon_sign = p.get("sign")
                break
    elif isinstance(chart_or_moon_sign, int) and 1 <= chart_or_moon_sign <= 12:
        natal_moon_sign = SIGNS_ORDER[chart_or_moon_sign - 1]
    else:
        raw_sign = str(chart_or_moon_sign).strip()
        if raw_sign.isdigit() and 1 <= int(raw_sign) <= 12:
            natal_moon_sign = SIGNS_ORDER[int(raw_sign) - 1]
        else:
            natal_moon_sign = raw_sign
            for en_name, ru_name in SIGN_NAMES_RU.items():
                if raw_sign.lower() in ru_name.lower() or raw_sign.lower() == en_name.lower():
                    natal_moon_sign = en_name
                    break

    if not natal_moon_sign or natal_moon_sign not in SIGNS_ORDER:
        return {
            "active": False, "phase": None, "phase_ru": None,
            "natal_moon_sign": natal_moon_sign or "unknown",
            "moon_sign": natal_moon_sign or "unknown",
            "saturn_sign": "unknown", "transit_saturn_sign": "unknown",
            "description": "Не удалось определить знак Луны."
        }

    # Вычислить текущее положение транзитного Сатурна через skyfield
    transit_saturn_sign = _get_transit_saturn_sign()

    if not transit_saturn_sign:
        return {
            "active": False, "phase": None, "phase_ru": None,
            "natal_moon_sign": natal_moon_sign,
            "moon_sign": natal_moon_sign,
            "saturn_sign": "unknown", "transit_saturn_sign": "unknown",
            "description": "Не удалось вычислить транзит Сатурна."
        }

    moon_idx = SIGNS_ORDER.index(natal_moon_sign)
    saturn_idx = SIGNS_ORDER.index(transit_saturn_sign)

    # Расстояние по знакам (от Луны к Сатурну по часовой стрелке)
    distance = (saturn_idx - moon_idx) % 12

    sign_12 = SIGNS_ORDER[(moon_idx - 1) % 12]  # 12-й знак от Луны (Фаза 1)
    sign_1 = SIGNS_ORDER[moon_idx]              # Знак Луны (Фаза 2 / Пик)
    sign_2 = SIGNS_ORDER[(moon_idx + 1) % 12]   # 2-й знак от Луны (Фаза 3)

    result = {
        "natal_moon_sign": natal_moon_sign,
        "natal_moon_sign_ru": SIGN_NAMES_RU.get(natal_moon_sign, natal_moon_sign),
        "moon_sign": natal_moon_sign,
        "moon_sign_ru": SIGN_NAMES_RU.get(natal_moon_sign, natal_moon_sign),
        "transit_saturn_sign": transit_saturn_sign,
        "transit_saturn_sign_ru": SIGN_NAMES_RU.get(transit_saturn_sign, transit_saturn_sign),
        "saturn_sign": transit_saturn_sign,
        "saturn_sign_ru": SIGN_NAMES_RU.get(transit_saturn_sign, transit_saturn_sign),
        "sign_12_ru": SIGN_NAMES_RU.get(sign_12, sign_12),
        "sign_1_ru": SIGN_NAMES_RU.get(sign_1, sign_1),
        "sign_2_ru": SIGN_NAMES_RU.get(sign_2, sign_2),
        "current_cycle": None,
        "next_cycle": None,
        "prev_cycle": None,
    }

    # Поиск всех 7.5-летних циклов Саде-Сати для натальной Луны по астрономической таблице
    all_cycles = []
    for i in range(len(SATURN_TRANSITS) - 3):
        if SATURN_TRANSITS[i][1] == sign_12:
            p1_start = SATURN_TRANSITS[i][0]
            p2_start = SATURN_TRANSITS[i + 1][0]
            p3_start = SATURN_TRANSITS[i + 2][0]
            end_dt = SATURN_TRANSITS[i + 3][0]
            all_cycles.append({
                "phase1_start": p1_start,
                "phase2_start": p2_start,
                "phase3_start": p3_start,
                "end_date": end_dt,
            })

    today_str = _date.today().isoformat()

    active_cycle = None
    next_cycle = None
    prev_cycle = None

    for c in all_cycles:
        if c["phase1_start"] <= today_str <= c["end_date"]:
            active_cycle = c
            break
        elif c["end_date"] < today_str:
            prev_cycle = c
        elif c["phase1_start"] > today_str and next_cycle is None:
            next_cycle = c

    if active_cycle:
        # Саде-Сати активен прямо сейчас
        if distance == 11:
            phase = "rising"
            phase_ru = "🌅 Восходящая фаза (Сатурн в 12-м знаке от Луны)"
            cur_phase_start = active_cycle["phase1_start"]
            cur_phase_end = active_cycle["phase2_start"]
        elif distance == 0:
            phase = "peak"
            phase_ru = "🔥 Пиковая фаза (Сатурн в знаке натальной Луны)"
            cur_phase_start = active_cycle["phase2_start"]
            cur_phase_end = active_cycle["phase3_start"]
        else:
            phase = "setting"
            phase_ru = "🌇 Нисходящая фаза (Сатурн во 2-м знаке от Луны)"
            cur_phase_start = active_cycle["phase3_start"]
            cur_phase_end = active_cycle["end_date"]

        cycle_info = {
            "start_date": active_cycle["phase1_start"],
            "start_date_ru": _format_date_ru(active_cycle["phase1_start"]),
            "phase2_start_ru": _format_date_ru(active_cycle["phase2_start"]),
            "phase3_start_ru": _format_date_ru(active_cycle["phase3_start"]),
            "end_date": active_cycle["end_date"],
            "end_date_ru": _format_date_ru(active_cycle["end_date"]),
            "phase_start_ru": _format_date_ru(cur_phase_start),
            "phase_end_ru": _format_date_ru(cur_phase_end),
        }
        result.update({
            "active": True,
            "phase": phase,
            "phase_ru": phase_ru,
            "current_cycle": cycle_info,
            "description": (
                f"Саде-Сати АКТИВЕН ({phase_ru}). "
                f"Период текущей фазы: с {cycle_info['phase_start_ru']} по {cycle_info['phase_end_ru']}. "
                f"Полное окончание Саде-Сати: {cycle_info['end_date_ru']}."
            )
        })
    else:
        # Саде-Сати не активен
        years_left = 1
        next_info = None
        if next_cycle:
            try:
                p1_year = int(next_cycle["phase1_start"][:4])
                cur_year = _date.today().year
                years_left = max(1, p1_year - cur_year)
            except Exception:
                years_left = 1

            next_info = {
                "start_date": next_cycle["phase1_start"],
                "start_date_ru": _format_date_ru(next_cycle["phase1_start"]),
                "phase1_start": next_cycle["phase1_start"],
                "phase1_start_ru": _format_date_ru(next_cycle["phase1_start"]),
                "phase2_start": next_cycle["phase2_start"],
                "phase2_start_ru": _format_date_ru(next_cycle["phase2_start"]),
                "phase3_start": next_cycle["phase3_start"],
                "phase3_start_ru": _format_date_ru(next_cycle["phase3_start"]),
                "end_date": next_cycle["end_date"],
                "end_date_ru": _format_date_ru(next_cycle["end_date"]),
                "years_left": years_left,
            }

        prev_info = None
        if prev_cycle:
            prev_info = {
                "start_date": prev_cycle["phase1_start"],
                "start_date_ru": _format_date_ru(prev_cycle["phase1_start"]),
                "end_date": prev_cycle["end_date"],
                "end_date_ru": _format_date_ru(prev_cycle["end_date"]),
            }

        result.update({
            "active": False,
            "phase": None,
            "phase_ru": None,
            "next_cycle": next_info,
            "prev_cycle": prev_info,
            "description": (
                f"Саде-Сати сейчас НЕ активен. "
                + (f"Следующий начнётся {next_info['phase1_start_ru']} (через ~{years_left} лет)." if next_info else "")
            )
        })

    return result


def _get_transit_saturn_sign() -> Optional[str]:
    """Вычислить текущий сидерический знак транзитного Сатурна через skyfield."""
    try:
        from skyfield.api import load
        from skyfield.data import mpc
        from datetime import datetime as _dt

        ts = load.timescale()
        t = ts.now()
        eph = load('de421.bsp')
        earth = eph['earth']
        saturn = eph['saturn barycenter']

        astrometric = earth.at(t).observe(saturn)
        ra, dec, distance_au = astrometric.radec()

        # Тропическая долгота
        from skyfield.positionlib import Apparent
        apparent = earth.at(t).observe(saturn).apparent()
        lat, lon, _ = apparent.ecliptic_latlon()
        tropical_lon = lon.degrees

        # Аянамша Лахири (~24.2° на 2026 год, ⚠️ приблизительная)
        ayanamsa = 24.2
        sidereal_lon = (tropical_lon - ayanamsa) % 360

        sign_index = int(sidereal_lon // 30)
        return SIGNS_ORDER[sign_index]
    except Exception:
        return None


# =========================================================================
# ЧАРА-КАРАКИ ДЖАЙМИНИ (АТМАКАРАКА, АМАТЬЯКАРАКА, ДАРАКАРАКА И ДР.)
# =========================================================================

CHARA_KARAKA_ROLES = [
    {
        "code": "AK",
        "name": "Atmakaraka",
        "name_ru": "🌟 Атмакарака (Планета Души)",
        "meaning": "Царь карты. Олицетворяет истинную сущность души, высшую кармическую цель и главный жизненный урок.",
    },
    {
        "code": "AmK",
        "name": "Amatyakaraka",
        "name_ru": "💼 Аматьякарака (Советник / Карьера)",
        "meaning": "Первый министр. Указывает на карьерное призвание, социальный статус, профессию и материальное развитие.",
    },
    {
        "code": "BK",
        "name": "Bhratrikaraka",
        "name_ru": "🤝 Бхратрикарака (Гуру и Наставники)",
        "meaning": "Олицетворяет учителей, духовных наставников, братьев, сестёр и тех, кто ведёт вас по пути мудрости.",
    },
    {
        "code": "MK",
        "name": "Matrikaraka",
        "name_ru": "🏡 Матрикарака (Мать и Счастье)",
        "meaning": "Показатель матери, домашнего очага, эмоционального покоя, комфорта и недвижимости.",
    },
    {
        "code": "PK",
        "name": "Putrakaraka",
        "name_ru": "👶 Путракарака (Дети и Творчество)",
        "meaning": "Связан с детьми, учениками, интеллектом, творческим самовыражением и божественной милостью.",
    },
    {
        "code": "GK",
        "name": "Gnatikaraka",
        "name_ru": "🛡️ Гнатикарака (Препятствия и Сила)",
        "meaning": "Олицетворяет борьбу, конкурентов, испытания, преодоление болезней и способность побеждать в кризисах.",
    },
    {
        "code": "DK",
        "name": "Darakaraka",
        "name_ru": "💍 Даракарака (Супруг / Партнёр)",
        "meaning": "Показатель супруга, романтического союза, типажа партнёра и отношений в браке и бизнесе.",
    },
]

PLANET_KARMA_LESSONS = {
    "Sun": "Урок преодоления гордыни, развитие истинного благородства, лидерства и заботы о других.",
    "Moon": "Урок безусловной любви, эмоционального спокойствия, заботы без привязанности и зависимостей.",
    "Mars": "Урок контроля гнева, ненасилия (ахимсы), трансформации импульсивности в дисциплинированную защиту слабых.",
    "Mercury": "Урок правдивости речи, чистоты помыслов, непричинения вреда словом и интеллектуальной искренности.",
    "Jupiter": "Урок смирения в знаниях, уважения к учителям, духовной мудрости и наставничества без осуждения.",
    "Venus": "Урок чистоты в отношениях, верности, контроля чувственных страстей и возвышенного искусства.",
    "Saturn": "Урок смирения, терпения, сострадания к страждущим и преданного бескорыстного труда без ропота на судьбу.",
}


def calculate_chara_karakas(chart_data: dict) -> dict:
    """
    Рассчитать 7 Чара-Карак (Jaimini Chara Karakas) по натальной карте.
    Используется классическая 7-карака система: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn.
    Планеты сортируются по убыванию градуса в знаке (0°..30°).
    """
    eligible_planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    planets_data = []

    for p in chart_data.get("planets", []):
        pname = p.get("name")
        if pname in eligible_planets:
            deg = float(p.get("degrees", 0.0)) % 30.0
            planets_data.append({
                "name": pname,
                "name_ru": p.get("name_ru", PLANET_NAMES_RU.get(pname, pname)),
                "sign": p.get("sign"),
                "sign_ru": p.get("sign_ru", p.get("sign")),
                "house": p.get("house", 1),
                "degrees": deg,
                "motion": p.get("motion"),
                "nakshatra": p.get("nakshatra", ""),
            })

    # Сортировка по убыванию градусов внутри знака
    planets_data.sort(key=lambda x: x["degrees"], reverse=True)

    karakas = []
    for idx, p in enumerate(planets_data):
        if idx < len(CHARA_KARAKA_ROLES):
            role = CHARA_KARAKA_ROLES[idx]
            lesson = PLANET_KARMA_LESSONS.get(p["name"], "")
            karakas.append({
                "code": role["code"],
                "role_name": role["name"],
                "role_name_ru": role["name_ru"],
                "meaning": role["meaning"],
                "planet": p["name"],
                "planet_ru": p["name_ru"],
                "sign_ru": p["sign_ru"],
                "house": p["house"],
                "degrees": round(p["degrees"], 2),
                "nakshatra": p["nakshatra"],
                "lesson": lesson,
            })

    return {
        "karakas": karakas,
        "atmakaraka": karakas[0] if karakas else None,
        "amatyakaraka": karakas[1] if len(karakas) > 1 else None,
        "darakaraka": karakas[-1] if karakas else None,
    }


def format_chara_karakas(karakas_dict: dict, lang: str = "ru") -> str:
    """Форматировать разбор Чара-Карак для Telegram."""
    lang = normalize_language(lang)
    if lang == "ru":
        lines = ["🔮 *Кармическая задача души (Чара-Караки Джаймини)*\n"]
        lines.append("В ведической астрологии градусы планет раскрывают ключевые роли вашей души в текущем воплощении:\n")

        for k in karakas_dict.get("karakas", []):
            code = k["code"]
            name_ru = k["role_name_ru"]
            p_ru = k["planet_ru"]
            deg = k["degrees"]
            sign = k["sign_ru"]
            house = k["house"]
            meaning = k["meaning"]

            lines.append(f"*{name_ru}*: *{p_ru}* ({deg}°, {sign}, дом {house})")
            lines.append(f"_{meaning}_")
            if code == "AK":
                lines.append(f"✨ *Главный кармический урок:* {k['lesson']}")
            elif code == "AmK":
                lines.append(f"💼 *Вектор карьеры:* успех через раскрытие качеств {p_ru} в сфере дома {house}.")
            elif code == "DK":
                lines.append(f"💍 *Характер партнёра:* черты супруга и тип союза связаны с качествами {p_ru}.")
            lines.append("")

        return "\n".join(lines).strip()
    elif lang == "it":
        role_names = {
            "AK": "Atmakaraka (Pianeta dell'Anima)",
            "AmK": "Amatyakaraka (Carriera e Intelletto)",
            "BK": "Bhratrikaraka (Fratelli e Maestri)",
            "MK": "Matrikaraka (Madre e Focolare)",
            "PK": "Pitrikaraka (Padre e Antenati)",
            "GK": "Gnatikaraka (Ostacoli e Parenti)",
            "DK": "Darakaraka (Sposo/a e Partner)"
        }
        lines = ["🔮 *Compito Karmico dell'Anima (Chara Karaka di Jaimini)*\n"]
        lines.append("Nell'astrologia vedica i gradi dei pianeti rivelano i ruoli chiave della tua anima nella vita attuale:\n")
        for k in karakas_dict.get("karakas", []):
            code = k["code"]
            r_name = role_names.get(code, k.get("role_name", code))
            p_name = get_planet_name(k.get("planet", ""), "it")
            deg = k["degrees"]
            s_name = get_sign_name(k.get("sign_ru", "").split()[0], "it")
            house = k["house"]
            meaning = k.get("meaning", "")
            lines.append(f"*{r_name}*: *{p_name}* ({deg}°, {s_name}, casa {house})")
            if meaning:
                lines.append(f"_{meaning}_")
            if code == "AK":
                lines.append(f"✨ *Lezione karmica principale:* {k.get('lesson', '')}")
            elif code == "AmK":
                lines.append(f"💼 *Vettore carriera:* successo sviluppando le qualità di {p_name} nella casa {house}.")
            elif code == "DK":
                lines.append(f"💍 *Carattere del partner:* i tratti del coniuge sono legati all'energia di {p_name}.")
            lines.append("")
        return "\n".join(lines).strip()
    else:  # en
        role_names = {
            "AK": "Atmakaraka (Soul Planet)",
            "AmK": "Amatyakaraka (Career & Intellect)",
            "BK": "Bhratrikaraka (Brothers & Gurus)",
            "MK": "Matrikaraka (Mother & Hearth)",
            "PK": "Pitrikaraka (Father & Ancestors)",
            "GK": "Gnatikaraka (Obstacles & Relatives)",
            "DK": "Darakaraka (Spouse & Partnership)"
        }
        lines = ["🔮 *Karmic Task of the Soul (Jaimini Chara Karakas)*\n"]
        lines.append("In Vedic astrology, planetary degrees reveal the key roles of your soul in this incarnation:\n")
        for k in karakas_dict.get("karakas", []):
            code = k["code"]
            r_name = role_names.get(code, k.get("role_name", code))
            p_name = get_planet_name(k.get("planet", ""), "en")
            deg = k["degrees"]
            s_name = get_sign_name(k.get("sign_ru", "").split()[0], "en")
            house = k["house"]
            meaning = k.get("meaning", "")
            lines.append(f"*{r_name}*: *{p_name}* ({deg}°, {s_name}, house {house})")
            if meaning:
                lines.append(f"_{meaning}_")
            if code == "AK":
                lines.append(f"✨ *Main karmic lesson:* {k.get('lesson', '')}")
            elif code == "AmK":
                lines.append(f"💼 *Career vector:* success through expressing {p_name} in house {house}.")
            elif code == "DK":
                lines.append(f"💍 *Spouse qualities:* partner traits and union dynamics are linked to {p_name}.")
            lines.append("")
        return "\n".join(lines).strip()


# =========================================================================
# АНАЛИЗ БОГАТСТВА, ФИНАНСОВ И КАРЬЕРЫ
# =========================================================================

def analyze_wealth_and_career(chart_data: dict) -> dict:
    """
    Детальный анализ финансового кода, богатства и карьеры по натальной карте.
    Анализирует:
    - 2-й дом (Дхана: накопления, личные активы)
    - 11-й дом (Лабха: доходы, бизнес, проекты, масштабирование)
    - 10-й дом (Карма: призвание, авторитет, статус)
    - Дхана-йоги и Раджа-йоги
    - Аматьякараку (AmK)
    """
    houses = chart_data.get("houses", [])
    house_by_num = {h.get("number"): h for h in houses if isinstance(h, dict)}

    h2 = house_by_num.get(2, {})
    h11 = house_by_num.get(11, {})
    h10 = house_by_num.get(10, {})

    h2_lord = h2.get("lord", "unknown")
    h11_lord = h11.get("lord", "unknown")
    h10_lord = h10.get("lord", "unknown")

    # Дхана-йоги
    all_yogas = detect_yogas(chart_data)
    dhana_yogas = [y for y in all_yogas if (y.get("type") == "dhana" or "Дхана" in y.get("name_ru", "")) and y.get("active")]
    raja_yogas = [y for y in all_yogas if (y.get("type") == "raja" or "Раджа" in y.get("name_ru", "")) and y.get("active")]

    # Чара-караки для карьеры
    ck = calculate_chara_karakas(chart_data)
    amk = ck.get("amatyakaraka")

    return {
        "house_2": {
            "sign_ru": h2.get("sign_ru", "Неизвестно"),
            "lord_ru": h2.get("lord_ru", PLANET_NAMES_RU.get(h2_lord, h2_lord)),
            "occupants": [PLANET_NAMES_RU.get(p, p) for p in h2.get("occupants", [])],
        },
        "house_11": {
            "sign_ru": h11.get("sign_ru", "Неизвестно"),
            "lord_ru": h11.get("lord_ru", PLANET_NAMES_RU.get(h11_lord, h11_lord)),
            "occupants": [PLANET_NAMES_RU.get(p, p) for p in h11.get("occupants", [])],
        },
        "house_10": {
            "sign_ru": h10.get("sign_ru", "Неизвестно"),
            "lord_ru": h10.get("lord_ru", PLANET_NAMES_RU.get(h10_lord, h10_lord)),
            "occupants": [PLANET_NAMES_RU.get(p, p) for p in h10.get("occupants", [])],
        },
        "dhana_yogas": dhana_yogas,
        "raja_yogas": raja_yogas,
        "amatyakaraka": amk,
    }


def format_wealth_analysis(wealth_data: dict, lang: str = "ru") -> str:
    """Форматировать финансовый разбор для Telegram."""
    lang = normalize_language(lang)
    h2 = wealth_data["house_2"]
    h11 = wealth_data["house_11"]
    h10 = wealth_data["house_10"]

    if lang == "ru":
        lines = ["💰 *Финансовый код и Карьера (Дхана & Карма бхавы)*\n"]

        lines.append("🏦 *2-й дом (Накопления и сбережения):*")
        lines.append(f"• Знак: {h2['sign_ru']} | Управитель: *{h2['lord_ru']}*")
        occ2 = ", ".join(h2["occupants"]) if h2["occupants"] else "нет планет (чистый потенциал)"
        lines.append(f"• Планеты в доме: {occ2}\n")

        lines.append("📈 *11-й дом (Прибыль, бизнес и сверхдоходы):*")
        lines.append(f"• Знак: {h11['sign_ru']} | Управитель: *{h11['lord_ru']}*")
        occ11 = ", ".join(h11["occupants"]) if h11["occupants"] else "нет планет"
        lines.append(f"• Планеты в доме: {occ11}\n")

        lines.append("🏛️ *10-й дом (Карьера, статус и признание):*")
        lines.append(f"• Знак: {h10['sign_ru']} | Управитель: *{h10['lord_ru']}*")
        occ10 = ", ".join(h10["occupants"]) if h10["occupants"] else "нет планет"
        lines.append(f"• Планеты в доме: {occ10}\n")

        amk = wealth_data.get("amatyakaraka")
        if amk:
            lines.append(f"💼 *Аматьякарака (Вектор призвания):* *{amk['planet_ru']}* в доме {amk['house']} ({amk['sign_ru']})")
            lines.append("  Максимальный финансовый рост происходит через развитие профессиональных качеств этой планеты.\n")

        dy = wealth_data.get("dhana_yogas", [])
        if dy:
            lines.append(f"✨ *Обнаружено Дхана-йог (комбинаций богатства):* {len(dy)}")
            for y in dy:
                lines.append(f"  • *{y.get('name_ru', y.get('name'))}*: {y.get('description', '')}")
        else:
            lines.append("✨ *Дхана-йоги:* Классические связки домов богатства умеренные. Финансовый рост строится через профессиональное мастерство 10-го дома и транзитные периоды.")

        return "\n".join(lines).strip()
    elif lang == "it":
        lines = ["💰 *Codice Finanziario e Carriera (Dhana & Karma Bhava)*\n"]

        s2 = get_sign_name(h2.get("sign_ru", "").split()[0], "it")
        l2 = get_planet_name(h2.get("lord_ru", "").split()[0], "it")
        lines.append("🏦 *2ª Casa (Risparmi e Accumulo):*")
        lines.append(f"• Segno: {s2} | Governatore: *{l2}*")
        occ2 = ", ".join([get_planet_name(p.split()[0], "it") for p in h2["occupants"]]) if h2["occupants"] else "nessun pianeta (potenziale puro)"
        lines.append(f"• Pianeti nella casa: {occ2}\n")

        s11 = get_sign_name(h11.get("sign_ru", "").split()[0], "it")
        l11 = get_planet_name(h11.get("lord_ru", "").split()[0], "it")
        lines.append("📈 *11ª Casa (Profitti, Business ed Entrate):*")
        lines.append(f"• Segno: {s11} | Governatore: *{l11}*")
        occ11 = ", ".join([get_planet_name(p.split()[0], "it") for p in h11["occupants"]]) if h11["occupants"] else "nessun pianeta"
        lines.append(f"• Pianeti nella casa: {occ11}\n")

        s10 = get_sign_name(h10.get("sign_ru", "").split()[0], "it")
        l10 = get_planet_name(h10.get("lord_ru", "").split()[0], "it")
        lines.append("🏛️ *10ª Casa (Carriera, Status e Riconoscimento):*")
        lines.append(f"• Segno: {s10} | Governatore: *{l10}*")
        occ10 = ", ".join([get_planet_name(p.split()[0], "it") for p in h10["occupants"]]) if h10["occupants"] else "nessun pianeta"
        lines.append(f"• Pianeti nella casa: {occ10}\n")

        amk = wealth_data.get("amatyakaraka")
        if amk:
            p_name = get_planet_name(amk.get("planet_ru", "").split()[0], "it")
            s_name = get_sign_name(amk.get("sign_ru", "").split()[0], "it")
            lines.append(f"💼 *Amatyakaraka (Vettore di Vocazione):* *{p_name}* nella casa {amk['house']} ({s_name})")
            lines.append("  La massima crescita economica avviene attraverso l'espressione professionale di questo pianeta.\n")

        dy = wealth_data.get("dhana_yogas", [])
        if dy:
            lines.append(f"✨ *Dhana Yoga rilevati (combinazioni di ricchezza):* {len(dy)}")
            for y in dy:
                lines.append(f"  • *{y.get('name', '')}*: {y.get('description', '')}")
        else:
            lines.append("✨ *Dhana Yoga:* Combinazioni moderate. La crescita economica si sviluppa tramite la maestria professionale della 10ª casa e i transiti.")

        return "\n".join(lines).strip()
    else:  # en
        lines = ["💰 *Financial Code & Career (Dhana & Karma Bhavas)*\n"]

        s2 = get_sign_name(h2.get("sign_ru", "").split()[0], "en")
        l2 = get_planet_name(h2.get("lord_ru", "").split()[0], "en")
        lines.append("🏦 *2nd House (Accumulation & Savings):*")
        lines.append(f"• Sign: {s2} | Lord: *{l2}*")
        occ2 = ", ".join([get_planet_name(p.split()[0], "en") for p in h2["occupants"]]) if h2["occupants"] else "no planets (pure potential)"
        lines.append(f"• Planets in house: {occ2}\n")

        s11 = get_sign_name(h11.get("sign_ru", "").split()[0], "en")
        l11 = get_planet_name(h11.get("lord_ru", "").split()[0], "en")
        lines.append("📈 *11th House (Profits, Gains & Business):*")
        lines.append(f"• Sign: {s11} | Lord: *{l11}*")
        occ11 = ", ".join([get_planet_name(p.split()[0], "en") for p in h11["occupants"]]) if h11["occupants"] else "no planets"
        lines.append(f"• Planets in house: {occ11}\n")

        s10 = get_sign_name(h10.get("sign_ru", "").split()[0], "en")
        l10 = get_planet_name(h10.get("lord_ru", "").split()[0], "en")
        lines.append("🏛️ *10th House (Career, Status & Recognition):*")
        lines.append(f"• Sign: {s10} | Lord: *{l10}*")
        occ10 = ", ".join([get_planet_name(p.split()[0], "en") for p in h10["occupants"]]) if h10["occupants"] else "no planets"
        lines.append(f"• Planets in house: {occ10}\n")

        amk = wealth_data.get("amatyakaraka")
        if amk:
            p_name = get_planet_name(amk.get("planet_ru", "").split()[0], "en")
            s_name = get_sign_name(amk.get("sign_ru", "").split()[0], "en")
            lines.append(f"💼 *Amatyakaraka (Vocation Vector):* *{p_name}* in house {amk['house']} ({s_name})")
            lines.append("  Maximum financial growth occurs by expressing the professional talents of this planet.\n")

        dy = wealth_data.get("dhana_yogas", [])
        if dy:
            lines.append(f"✨ *Dhana Yogas Detected (Wealth Combinations):* {len(dy)}")
            for y in dy:
                lines.append(f"  • *{y.get('name', '')}*: {y.get('description', '')}")
        else:
            lines.append("✨ *Dhana Yogas:* Moderate wealth combinations. Long-term prosperity is achieved via 10th house excellence and transit timing.")

        return "\n".join(lines).strip()


# =========================================================================
# КУДЖА-ДОША (МАНГЛИКА / ПОВРЕЖДЕНИЕ МАРСОМ В СОВМЕСТИМОСТИ)
# =========================================================================

def check_kuja_dosha(chart_data: dict) -> dict:
    """
    Проверка Куджа-доши (Манглика / Mars dosha).
    Марс в домах 1, 4, 7, 8 или 12 от Лагны.
    Проверяет также правила отмены (нейтрализации).
    """
    planets = chart_data.get("planets", [])
    mars = next((p for p in planets if p.get("name") == "Mars"), None)
    if not mars:
        return {"has_dosha": False, "is_manglik_placement": False, "reason": "Марс не найден"}

    mars_house = mars.get("house", 0)
    mars_sign = mars.get("sign", "")
    mars_sign_ru = mars.get("sign_ru", mars_sign)

    manglik_houses = [1, 4, 7, 8, 12]
    is_manglik = mars_house in manglik_houses

    is_cancelled = False
    cancel_reason = ""

    if is_manglik:
        if mars_sign in ["Aries", "Scorpio"]:
            is_cancelled = True
            cancel_reason = "Марс находится в собственном знаке (Свакшетра), агрессия трансформируется в созидательную энергию."
        elif mars_sign == "Capricorn":
            is_cancelled = True
            cancel_reason = "Марс в экзальтации (Учча) — высочайшая дисциплина и благородство вместо конфликтов."
        else:
            jupiter = next((p for p in planets if p.get("name") == "Jupiter"), None)
            if jupiter and jupiter.get("sign") == mars_sign:
                is_cancelled = True
                cancel_reason = "Юпитер соединён с Марсом (Гуру-Мангала йога), смягчая импульсивность мудростью."

    return {
        "has_dosha": is_manglik and not is_cancelled,
        "is_manglik_placement": is_manglik,
        "mars_house": mars_house,
        "mars_sign_ru": mars_sign_ru,
        "is_cancelled": is_cancelled,
        "cancel_reason": cancel_reason,
    }


# =========================================================================
# ВЕДИЧЕСКИЕ УПАЙИ (КОМПЕНСАТОРИКА И СРЕДСТВА ГАРМОНИЗАЦИИ)
# =========================================================================

UPAYA_CATALOG = {
    "Sun": {
        "planet_ru": "Сурья (Солнце)",
        "day": "Воскресенье",
        "mantra": "Ом Храм Хрим Храум Сах Сурьяйя Намаха",
        "colors": "Золотой, оранжевый, медный, шафрановый",
        "charity": "Помощь отцу, пожилым лидерам, пожертвования пшеницы или золота",
        "practices": "Встреча рассветов (Сурья Намаскар), развитие щедрости, держание обещаний",
    },
    "Moon": {
        "planet_ru": "Чандра (Луна)",
        "day": "Понедельник",
        "mantra": "Ом Шрам Шрим Шраум Сах Чандрайя Намаха",
        "colors": "Белый, молочный, серебристый, перламутровый",
        "charity": "Помощь матери, забота о детях и женщинах, раздача риса и чистой воды",
        "practices": "Медитации на воду, вечерние прогулки при Луне, нормализация сна, отказ от ссор на ночь",
    },
    "Mars": {
        "planet_ru": "Мангала (Марс)",
        "day": "Вторник",
        "mantra": "Ом Крам Крим Краум Сах Бхаумайя Намаха",
        "colors": "Коралловый, алый, ярко-красный",
        "charity": "Помощь военным, спортсменам, приютам, донорство крови",
        "practices": "Регулярный спорт/физическая активность, контроль гнева, защита слабых, исключение агрессии",
    },
    "Mercury": {
        "planet_ru": "Будха (Меркурий)",
        "day": "Среда",
        "mantra": "Ом Брам Брим Браум Сах Будхайя Намаха",
        "colors": "Изумрудный, светло-зелёный, оливковый",
        "charity": "Помощь студентам, сиротам, дарение книг и канцелярских товаров",
        "practices": "Изучение новых языков, осознанность в речи (без сплетен и сарказма), прогулки в лесу",
    },
    "Jupiter": {
        "planet_ru": "Гуру (Юпитер)",
        "day": "Четверг",
        "mantra": "Ом Грам Грим Граум Сах Гураве Намаха",
        "colors": "Жёлтый, шафрановый, горчичный, золотистый",
        "charity": "Помощь духовным учителям, наставникам, храмам, пожертвование книг и нута",
        "practices": "Уважение к наставникам и закону, чтение мудрых книг, благотворительность, чистота помыслов",
    },
    "Venus": {
        "planet_ru": "Шукра (Венера)",
        "day": "Пятница",
        "mantra": "Ом Драм Дрим Драум Сах Шукрайя Намаха",
        "colors": "Белоснежный, пастельно-розовый, радужный, шёлковые ткани",
        "charity": "Помощь женщинам, артистам, подарки сладостей, цветов и красивой одежды",
        "practices": "Чистота и эстетика в доме, верность партнёру, творчество (музыка, дизайн), тонкие ароматы",
    },
    "Saturn": {
        "planet_ru": "Шани (Сатурн)",
        "day": "Суббота",
        "mantra": "Ом Прам Прим Праум Сах Шанайшчарайя Намаха",
        "colors": "Тёмно-синий, графитовый, чёрный",
        "charity": "Помощь пожилым людям, инвалидам, рабочим и бездомным животным",
        "practices": "Субботний пост/аскеза, пунктуальность, наведение порядка, отказ от жалоб на судьбу",
    },
    "Rahu": {
        "planet_ru": "Раху",
        "day": "Суббота / вечер",
        "mantra": "Ом Бхрам Бхрим Бхраум Сах Рахаве Намаха",
        "colors": "Дымчатый, ультрамарин, цвет ночного неба",
        "charity": "Помощь бездомным, приютам для бездомных животных",
        "practices": "Отказ от алкоголя и интоксикаций, цифровой детокс, избегание иллюзий и азартных игр",
    },
    "Ketu": {
        "planet_ru": "Кету",
        "day": "Вторник / рассвет",
        "mantra": "Ом Страм Стрим Страум Сах Кетаве Намаха",
        "colors": "Коричневый, терракотовый, хаки",
        "charity": "Помощь монахам, странникам, духовным центрам",
        "practices": "Медитация, йога, уединение на природе, избавление от хлама и старых вещей",
    },
}


def get_upayas(chart_data: dict) -> dict:
    """
    Подобрать персональные Упайи на основе карты:
    - Для управителя текущей Махадаши
    - Для планет в падении / слабой позиции
    - Для Сатурна (если активен Саде-Сати)
    """
    remedies = []
    curr_dasha = get_current_dasha(chart_data)
    md_planet = None
    if curr_dasha and curr_dasha.get("maha_dasha"):
        md_planet = curr_dasha["maha_dasha"].get("planet")
        if md_planet in UPAYA_CATALOG:
            remedies.append({
                "reason": f"Хозяин текущего периода жизни (Махадаша {curr_dasha['maha_dasha'].get('planet_ru', md_planet)})",
                **UPAYA_CATALOG[md_planet]
            })

    for p in chart_data.get("planets", []):
        pname = p.get("name")
        if p.get("dignity") == "Debilitated" and pname in UPAYA_CATALOG:
            if pname != md_planet:
                remedies.append({
                    "reason": f"Планета в падении ({p.get('name_ru', pname)} в {p.get('sign_ru')}) — требует гармонизации",
                    **UPAYA_CATALOG[pname]
                })

    sade = check_sade_sati(chart_data)
    if sade.get("active") and not any(r.get("planet_ru", "").startswith("Шани") for r in remedies):
        remedies.append({
            "reason": f"Активный период Саде-Сати ({sade.get('phase_ru', 'Транзит Сатурна')})",
            **UPAYA_CATALOG["Saturn"]
        })

    if not remedies and chart_data.get("houses") and isinstance(chart_data["houses"][0], dict):
        asc_lord = chart_data["houses"][0].get("lord")
        if asc_lord in UPAYA_CATALOG:
            remedies.append({
                "reason": "Лагнеша (Хозяин восходящего знака — основа жизненной силы)",
                **UPAYA_CATALOG[asc_lord]
            })

    return {"remedies": remedies}


def format_upayas(upaya_data: dict, lang: str = "ru") -> str:
    """Форматировать рекомендации по Упайям для Telegram."""
    lang = normalize_language(lang)
    if lang == "ru":
        lines = ["🛡️ *Ведические Упайи (Методы гармонизации карты)*\n"]
        lines.append("Упайи — это ведические инструменты коррекции судьбы через осознанные действия, мантры и благотворительность:\n")

        for r in upaya_data.get("remedies", []):
            lines.append(f"🪐 *{r['planet_ru']}*")
            lines.append(f"📍 *Причина:* {r['reason']}")
            lines.append(f"📅 *День для практики:* {r['day']}")
            lines.append(f"📿 *Мантра (108 раз):* `{r['mantra']}`")
            lines.append(f"🎨 *Благоприятные цвета:* {r['colors']}")
            lines.append(f"🤝 *Благотворительность:* {r['charity']}")
            lines.append(f"✨ *Поведенческая практика:* {r['practices']}\n")

        return "\n".join(lines).strip()
    elif lang == "it":
        lines = ["🛡️ *Upaya Vedici (Metodi di Armonizzazione)*\n"]
        lines.append("Gli Upaya sono strumenti vedici di riequilibrio del destino tramite azioni consapevoli, mantra e beneficenza:\n")

        days_it = {
            "Воскресенье": "Domenica", "Понедельник": "Lunedì", "Вторник": "Martedì",
            "Среда": "Mercoledì", "Четверг": "Giovedì", "Пятница": "Venerdì",
            "Суббота": "Sabato", "Суббота / вечер": "Sabato (sera)", "Вторник / рассвет": "Martedì (alba)"
        }
        for r in upaya_data.get("remedies", []):
            p_name = get_planet_name(r.get("planet", r.get("planet_ru", "").split()[0]), "it")
            d_name = days_it.get(r.get("day"), r.get("day"))
            lines.append(f"🪐 *{p_name}*")
            lines.append(f"📍 *Motivo:* {r['reason']}")
            lines.append(f"📅 *Giorno di pratica:* {d_name}")
            lines.append(f"📿 *Mantra (108 volte):* `{r['mantra']}`")
            lines.append(f"🎨 *Colori favorevoli:* {r['colors']}")
            lines.append(f"🤝 *Beneficenza:* {r['charity']}")
            lines.append(f"✨ *Pratica comportamentale:* {r['practices']}\n")

        return "\n".join(lines).strip()
    else:  # en
        lines = ["🛡️ *Vedic Upayas (Remedial Measures)*\n"]
        lines.append("Upayas are Vedic tools to harmonize planetary energies through conscious action, mantras, and charity:\n")

        days_en = {
            "Воскресенье": "Sunday", "Понедельник": "Monday", "Вторник": "Tuesday",
            "Среда": "Wednesday", "Четверг": "Thursday", "Пятница": "Friday",
            "Суббота": "Saturday", "Суббота / вечер": "Saturday (evening)", "Вторник / рассвет": "Tuesday (dawn)"
        }
        for r in upaya_data.get("remedies", []):
            p_name = get_planet_name(r.get("planet", r.get("planet_ru", "").split()[0]), "en")
            d_name = days_en.get(r.get("day"), r.get("day"))
            lines.append(f"🪐 *{p_name}*")
            lines.append(f"📍 *Reason:* {r['reason']}")
            lines.append(f"📅 *Practice Day:* {d_name}")
            lines.append(f"📿 *Mantra (108 times):* `{r['mantra']}`")
            lines.append(f"🎨 *Favorable Colors:* {r['colors']}")
            lines.append(f"🤝 *Charity:* {r['charity']}")
            lines.append(f"✨ *Behavioral Practice:* {r['practices']}\n")

        return "\n".join(lines).strip()


def format_chart_summary(chart_data: dict, lang: str = "ru") -> str:
    """Форматировать краткую сводку карты для отображения пользователю."""
    lang = normalize_language(lang)
    if lang == "ru":
        lines = []
        lines.append("🔮 *Натальная карта (Кундли)*\n")

        # Панчанга
        pan = chart_data["panchanga"]
        lines.append("📅 *Панчанга:*")
        lines.append(f"  Титхи: {pan['tithi']}")
        lines.append(f"  Накшатра: {pan['nakshatra']}")
        lines.append(f"  Йога: {pan['yoga']}")
        lines.append(f"  Карана: {pan['karana']}")
        lines.append(f"  Ваара: {pan['vaara']}")
        lines.append("")

        # Лагна (Асцендент)
        if chart_data["houses"]:
            asc = chart_data["houses"][0]
            lines.append(f"⬆️ *Лагна (Асцендент):* {asc['sign_ru']}")
            lines.append("")

        # Планеты
        lines.append("🪐 *Позиции планет:*")
        for p in chart_data["planets"]:
            retro = " ℞" if p["motion"] == "retrograde" else ""
            dignity = f" ({p['dignity']})" if p["dignity"] != "N/A" else ""
            lines.append(
                f"  {p['name_ru']}: {p['sign_ru']} "
                f"{p['degrees']:.1f}°{retro}{dignity} | "
                f"дом {p['house']} | {p['nakshatra']} пада {p['pada']}"
            )
        lines.append("")

        # Текущая даша
        current = get_current_dasha(chart_data["dashas"])
        if current["maha_dasha"]:
            md = current["maha_dasha"]
            lines.append(f"🕐 *Текущий период:*")
            lines.append(f"  Маха-Даша: {md['planet_ru']} ({md['start']} — {md['end']})")
            if current["antar_dasha"]:
                ad = current["antar_dasha"]
                lines.append(f"  Антар-Даша: {ad['planet_ru']} ({ad['start']} — {ad['end']})")

        return "\n".join(lines)
    elif lang == "it":
        lines = []
        lines.append("🔮 *Carta Natale (Kundli)*\n")

        # Panchanga
        pan = chart_data["panchanga"]
        lines.append("📅 *Panchanga:*")
        lines.append(f"  Tithi: {pan['tithi']}")
        lines.append(f"  Nakshatra: {pan['nakshatra']}")
        lines.append(f"  Yoga: {pan['yoga']}")
        lines.append(f"  Karana: {pan['karana']}")
        lines.append(f"  Vaara: {pan['vaara']}")
        lines.append("")

        # Lagna (Ascendente)
        if chart_data["houses"]:
            asc = chart_data["houses"][0]
            asc_sign = get_sign_name(asc.get("sign", ""), "it")
            lines.append(f"⬆️ *Lagna (Ascendente):* {asc_sign}")
            lines.append("")

        # Pianeti
        lines.append("🪐 *Posizioni Planetarie:*")
        for p in chart_data["planets"]:
            retro = " ℞" if p.get("motion") == "retrograde" else ""
            dignity = f" ({get_dignity_name(p['dignity'], 'it')})" if p.get("dignity") and p["dignity"] != "N/A" else ""
            p_name = get_planet_name(p.get("name", ""), "it")
            s_name = get_sign_name(p.get("sign", ""), "it")
            lines.append(
                f"  {p_name}: {s_name} "
                f"{p['degrees']:.1f}°{retro}{dignity} | "
                f"casa {p['house']} | {p['nakshatra']} pada {p['pada']}"
            )
        lines.append("")

        # Periodo attuale
        current = get_current_dasha(chart_data["dashas"])
        if current["maha_dasha"]:
            md = current["maha_dasha"]
            md_name = get_planet_name(md.get("planet", md.get("planet_ru", "").split()[0]), "it")
            lines.append(f"🕐 *Periodo Attuale:*")
            lines.append(f"  Maha-Dasha: {md_name} ({md['start']} — {md['end']})")
            if current["antar_dasha"]:
                ad = current["antar_dasha"]
                ad_name = get_planet_name(ad.get("planet", ad.get("planet_ru", "").split()[0]), "it")
                lines.append(f"  Antar-Dasha: {ad_name} ({ad['start']} — {ad['end']})")

        return "\n".join(lines)
    else:  # en
        lines = []
        lines.append("🔮 *Natal Chart (Kundli)*\n")

        # Panchanga
        pan = chart_data["panchanga"]
        lines.append("📅 *Panchanga:*")
        lines.append(f"  Tithi: {pan['tithi']}")
        lines.append(f"  Nakshatra: {pan['nakshatra']}")
        lines.append(f"  Yoga: {pan['yoga']}")
        lines.append(f"  Karana: {pan['karana']}")
        lines.append(f"  Vaara: {pan['vaara']}")
        lines.append("")

        # Lagna (Ascendant)
        if chart_data["houses"]:
            asc = chart_data["houses"][0]
            asc_sign = get_sign_name(asc.get("sign", ""), "en")
            lines.append(f"⬆️ *Lagna (Ascendant):* {asc_sign}")
            lines.append("")

        # Planets
        lines.append("🪐 *Planetary Positions:*")
        for p in chart_data["planets"]:
            retro = " ℞" if p.get("motion") == "retrograde" else ""
            dignity = f" ({get_dignity_name(p['dignity'], 'en')})" if p.get("dignity") and p["dignity"] != "N/A" else ""
            p_name = get_planet_name(p.get("name", ""), "en")
            s_name = get_sign_name(p.get("sign", ""), "en")
            lines.append(
                f"  {p_name}: {s_name} "
                f"{p['degrees']:.1f}°{retro}{dignity} | "
                f"house {p['house']} | {p['nakshatra']} pada {p['pada']}"
            )
        lines.append("")

        # Current period
        current = get_current_dasha(chart_data["dashas"])
        if current["maha_dasha"]:
            md = current["maha_dasha"]
            md_name = get_planet_name(md.get("planet", md.get("planet_ru", "").split()[0]), "en")
            lines.append(f"🕐 *Current Period:*")
            lines.append(f"  Maha-Dasha: {md_name} ({md['start']} — {md['end']})")
            if current["antar_dasha"]:
                ad = current["antar_dasha"]
                ad_name = get_planet_name(ad.get("planet", ad.get("planet_ru", "").split()[0]), "en")
                lines.append(f"  Antar-Dasha: {ad_name} ({ad['start']} — {ad['end']})")

        return "\n".join(lines)


def format_dasha_periods(chart_data: dict, lang: str = "ru") -> str:
    """Форматировать полный список Маха-Даш."""
    lang = normalize_language(lang)
    if lang == "ru":
        lines = ["🕐 *Вимшоттари Даша — периоды жизни:*\n"]

        # Баланс при рождении
        bal = chart_data["dashas"].get("balance", {})
        if bal:
            for planet, years in bal.items():
                planet_ru = PLANET_NAMES_RU.get(planet, planet)
                lines.append(f"⚖️ Баланс при рождении: {planet_ru} — {years:.2f} лет\n")

        now = datetime.now()

        for period in chart_data["dashas"].get("periods", []):
            start = datetime.strptime(period["start"], "%d.%m.%Y")
            end = datetime.strptime(period["end"], "%d.%m.%Y")
            is_current = start <= now <= end
            marker = " ◀️ *ТЕКУЩИЙ*" if is_current else ""

            lines.append(f"{'─' * 30}")
            lines.append(f"*{period['planet_ru']}* ({period['start']} — {period['end']}){marker}")

            if is_current and period.get("antardashas"):
                lines.append("  Подпериоды (Антар-Даша):")
                for ad in period["antardashas"]:
                    ad_start = datetime.strptime(ad["start"], "%d.%m.%Y")
                    ad_end = datetime.strptime(ad["end"], "%d.%m.%Y")
                    ad_current = " ⬅️" if ad_start <= now <= ad_end else ""
                    lines.append(f"    {ad['planet_ru']}: {ad['start']} — {ad['end']}{ad_current}")

        return "\n".join(lines)
    elif lang == "it":
        lines = ["🕐 *Vimshottari Dasha — Periodi di Vita:*\n"]
        bal = chart_data["dashas"].get("balance", {})
        if bal:
            for planet, years in bal.items():
                p_name = get_planet_name(planet, "it")
                lines.append(f"⚖️ Bilancio alla nascita: {p_name} — {years:.2f} anni\n")

        now = datetime.now()
        for period in chart_data["dashas"].get("periods", []):
            start = datetime.strptime(period["start"], "%d.%m.%Y")
            end = datetime.strptime(period["end"], "%d.%m.%Y")
            is_current = start <= now <= end
            marker = " ◀️ *ATTUALE*" if is_current else ""
            p_name = get_planet_name(period.get("planet", period.get("planet_ru", "").split()[0]), "it")

            lines.append(f"{'─' * 30}")
            lines.append(f"*{p_name}* ({period['start']} — {period['end']}){marker}")

            if is_current and period.get("antardashas"):
                lines.append("  Sottoperiodi (Antar-Dasha):")
                for ad in period["antardashas"]:
                    ad_start = datetime.strptime(ad["start"], "%d.%m.%Y")
                    ad_end = datetime.strptime(ad["end"], "%d.%m.%Y")
                    ad_current = " ⬅️" if ad_start <= now <= ad_end else ""
                    ad_name = get_planet_name(ad.get("planet", ad.get("planet_ru", "").split()[0]), "it")
                    lines.append(f"    {ad_name}: {ad['start']} — {ad['end']}{ad_current}")
        return "\n".join(lines)
    else:  # en
        lines = ["🕐 *Vimshottari Dasha — Life Periods:*\n"]
        bal = chart_data["dashas"].get("balance", {})
        if bal:
            for planet, years in bal.items():
                p_name = get_planet_name(planet, "en")
                lines.append(f"⚖️ Birth Balance: {p_name} — {years:.2f} years\n")

        now = datetime.now()
        for period in chart_data["dashas"].get("periods", []):
            start = datetime.strptime(period["start"], "%d.%m.%Y")
            end = datetime.strptime(period["end"], "%d.%m.%Y")
            is_current = start <= now <= end
            marker = " ◀️ *CURRENT*" if is_current else ""
            p_name = get_planet_name(period.get("planet", period.get("planet_ru", "").split()[0]), "en")

            lines.append(f"{'─' * 30}")
            lines.append(f"*{p_name}* ({period['start']} — {period['end']}){marker}")

            if is_current and period.get("antardashas"):
                lines.append("  Sub-periods (Antar-Dasha):")
                for ad in period["antardashas"]:
                    ad_start = datetime.strptime(ad["start"], "%d.%m.%Y")
                    ad_end = datetime.strptime(ad["end"], "%d.%m.%Y")
                    ad_current = " ⬅️" if ad_start <= now <= ad_end else ""
                    ad_name = get_planet_name(ad.get("planet", ad.get("planet_ru", "").split()[0]), "en")
                    lines.append(f"    {ad_name}: {ad['start']} — {ad['end']}{ad_current}")
        return "\n".join(lines)


# Порядок знаков зодиака для расчёта Саде-Сати
SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Хозяева знаков по Джьотиш
SIGN_LORDS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"
}

# Знаки экзальтации планет
EXALTATION_SIGNS = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn",
    "Mercury": "Virgo", "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra"
}

# Собственные знаки планет (свакшетра)
OWN_SIGNS = {
    "Mars": ["Aries", "Scorpio"], "Venus": ["Taurus", "Libra"],
    "Mercury": ["Gemini", "Virgo"], "Moon": ["Cancer"],
    "Sun": ["Leo"], "Jupiter": ["Sagittarius", "Pisces"],
    "Saturn": ["Capricorn", "Aquarius"]
}


def _get_current_saturn_sign() -> str:
    """Определить текущий знак Сатурна через skyfield (транзитный)."""
    from skyfield.api import load
    from skyfield.almanac import find_discrete

    ts = load.timescale()
    eph = load("de421.bsp")
    earth = eph["earth"]
    saturn = eph["saturn barycenter"]

    now = ts.now()
    astrometric = earth.at(now).observe(saturn)
    _, lon, _ = astrometric.ecliptic_latlon()
    tropical_lon = lon.degrees

    # Айанамша Лахири (приблизительно, уточнение не критично для знака)
    # Средняя прецессия ~50.29"/год от J2000 (2000.0)
    jd = now.tt
    years_from_j2000 = (jd - 2451545.0) / 365.25
    ayanamsa = 23.856 + (years_from_j2000 * 50.29 / 3600.0)
    sidereal_lon = (tropical_lon - ayanamsa) % 360

    sign_index = int(sidereal_lon // 30)
    return SIGN_ORDER[sign_index]


def detect_yogas(chart_data: dict) -> list:
    """
    Обнаружить ключевые ведические йоги в натальной карте.
    Возвращает список dict с полями: name, name_ru, description, planets, active.
    """
    yogas = []
    planets = chart_data.get("planets", [])
    houses = chart_data.get("houses", [])

    # Индексирование для быстрого доступа
    planet_by_name = {p["name"]: p for p in planets}
    house_by_number = {h["number"]: h for h in houses}

    # ---------- 1. Гаджакешари йога ----------
    # Юпитер в кендре (1, 4, 7, 10) от Луны
    moon = planet_by_name.get("Moon")
    jupiter = planet_by_name.get("Jupiter")
    gk_active = False
    if moon and jupiter:
        moon_house = moon.get("house", 0)
        jup_house = jupiter.get("house", 0)
        distance = ((jup_house - moon_house) % 12) + 1  # 1-based
        # Кендры от Луны: 1, 4, 7, 10 (т.е. distance 1, 4, 7, 10)
        if distance in (1, 4, 7, 10):
            gk_active = True
    yogas.append({
        "name": "Gajakesari Yoga",
        "name_ru": "Гаджакешари Йога",
        "description": "Юпитер в кендре от Луны — мудрость, авторитет, слава и достаток.",
        "planets": ["Jupiter", "Moon"],
        "active": gk_active,
    })

    # ---------- 2. Будхадитья йога ----------
    # Солнце и Меркурий в одном знаке
    sun = planet_by_name.get("Sun")
    mercury = planet_by_name.get("Mercury")
    ba_active = False
    if sun and mercury:
        if sun.get("sign") == mercury.get("sign"):
            ba_active = True
    yogas.append({
        "name": "Budhaditya Yoga",
        "name_ru": "Будхадитья Йога",
        "description": "Солнце и Меркурий в одном знаке — интеллект, красноречие, лидерские качества.",
        "planets": ["Sun", "Mercury"],
        "active": ba_active,
    })

    # ---------- 3. Панча Махапуруша Йоги ----------
    # Марс, Меркурий, Юпитер, Венера, Сатурн в экзальтации или собственном знаке в кендре от Лагны
    mahapurusha_names = {
        "Mars": ("Ручака Йога (Ruchaka)", "Марс в экзальтации/свакшетре в кендре — храбрость, сила, военное мастерство."),
        "Mercury": ("Бхадра Йога (Bhadra)", "Меркурий в экзальтации/свакшетре в кендре — интеллект, коммуникабельность, торговый дар."),
        "Jupiter": ("Хамса Йога (Hamsa)", "Юпитер в экзальтации/свакшетре в кендре — духовность, мудрость, благочестие."),
        "Venus": ("Малавья Йога (Malavya)", "Венера в экзальтации/свакшетре в кендре — красота, роскошь, любовь, искусство."),
        "Saturn": ("Шаша Йога (Sasha)", "Сатурн в экзальтации/свакшетре в кендре — власть, дисциплина, долголетие."),
    }
    kendra_houses = {1, 4, 7, 10}
    for pname, (yoga_name_ru, yoga_desc) in mahapurusha_names.items():
        p = planet_by_name.get(pname)
        mp_active = False
        if p:
            in_kendra = p.get("house") in kendra_houses
            in_exalt = (EXALTATION_SIGNS.get(pname) == p.get("sign"))
            in_own = p.get("sign") in OWN_SIGNS.get(pname, [])
            if in_kendra and (in_exalt or in_own):
                mp_active = True
        yogas.append({
            "name": f"Pancha Mahapurusha - {pname}",
            "name_ru": yoga_name_ru,
            "description": yoga_desc,
            "planets": [pname],
            "active": mp_active,
        })

    # ---------- 4. Раджа-йога ----------
    # Связь хозяев кендр (1,4,7,10) и трикон (1,5,9) — в одном знаке или взаимный обмен
    kendra_lords = set()
    trikona_lords = set()
    for h in houses:
        if h["number"] in (1, 4, 7, 10):
            kendra_lords.add(h["lord"])
        if h["number"] in (1, 5, 9):
            trikona_lords.add(h["lord"])

    raja_active = False
    raja_planets_found = []
    # Проверяем, есть ли хозяева кендр и трикон в одном знаке
    for kl in kendra_lords:
        for tl in trikona_lords:
            if kl == tl:
                continue  # Одна планета владеет и кендрой и триконой — уже раджа-йога-карака
                # Но это сам по себе формирует йогу только при хорошем положении
            kl_planet = planet_by_name.get(kl)
            tl_planet = planet_by_name.get(tl)
            if kl_planet and tl_planet:
                # Конъюнкция (одинаковый знак) или взаимный обмен домами
                if kl_planet.get("sign") == tl_planet.get("sign"):
                    raja_active = True
                    raja_planets_found = list(set(raja_planets_found + [kl, tl]))

    # Планета — хозяин и кендры и триконы (кроме 1-го дома, т.к. он и кендра и трикона)
    for lord in (kendra_lords & trikona_lords):
        # Хозяин 1-го дома всегда в пересечении — считаем раджа-йога-караку
        h1_lord = house_by_number.get(1, {}).get("lord")
        if lord != h1_lord:
            raja_active = True
            if lord not in raja_planets_found:
                raja_planets_found.append(lord)

    yogas.append({
        "name": "Raja Yoga",
        "name_ru": "Раджа-Йога",
        "description": "Связь хозяев кендр и трикон — успех, власть, реализация, высокий статус.",
        "planets": raja_planets_found if raja_planets_found else ["—"],
        "active": raja_active,
    })

    # ---------- 5. Дхана-йога ----------
    # Связь хозяев домов 2, 5, 9, 11 с кендрами (конъюнкция хозяев)
    dhana_house_nums = {2, 5, 9, 11}
    dhana_lords = set()
    for h in houses:
        if h["number"] in dhana_house_nums:
            dhana_lords.add(h["lord"])

    dhana_active = False
    dhana_planets_found = []
    for dl in dhana_lords:
        for kl in kendra_lords:
            if dl == kl:
                continue
            dl_planet = planet_by_name.get(dl)
            kl_planet = planet_by_name.get(kl)
            if dl_planet and kl_planet:
                if dl_planet.get("sign") == kl_planet.get("sign"):
                    dhana_active = True
                    dhana_planets_found = list(set(dhana_planets_found + [dl, kl]))

    yogas.append({
        "name": "Dhana Yoga",
        "name_ru": "Дхана-Йога",
        "description": "Связь хозяев домов богатства (2, 5, 9, 11) с кендрами — материальное благополучие.",
        "planets": dhana_planets_found if dhana_planets_found else ["—"],
        "active": dhana_active,
    })

    return yogas


