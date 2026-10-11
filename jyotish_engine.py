"""
Расчётный движок ведической астрологии (Джьотиш).
Обёртка над jyotishganit для использования в Telegram-боте.
"""
from datetime import datetime
from typing import Optional
from jyotishganit import calculate_birth_chart, get_birth_chart_json_string
import json


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


def get_current_dasha(dashas: dict, now: Optional[datetime] = None) -> dict:
    """Определить текущий период Маха-Даша и Антар-Даша."""
    if now is None:
        now = datetime.now()

    current = {"maha_dasha": None, "antar_dasha": None}

    for period in dashas.get("periods", []):
        start = datetime.strptime(period["start"], "%d.%m.%Y")
        end = datetime.strptime(period["end"], "%d.%m.%Y")
        if start <= now <= end:
            current["maha_dasha"] = {
                "planet": period["planet"],
                "planet_ru": period["planet_ru"],
                "start": period["start"],
                "end": period["end"],
            }
            # Ищем антар-дашу
            for ad in period.get("antardashas", []):
                ad_start = datetime.strptime(ad["start"], "%d.%m.%Y")
                ad_end = datetime.strptime(ad["end"], "%d.%m.%Y")
                if ad_start <= now <= ad_end:
                    current["antar_dasha"] = ad
                    break
            break

    return current


def format_chart_summary(chart_data: dict) -> str:
    """Форматировать краткую сводку карты для отображения пользователю."""
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


def format_dasha_periods(chart_data: dict) -> str:
    """Форматировать полный список Маха-Даш."""
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

