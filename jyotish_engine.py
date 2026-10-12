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


def get_current_dasha(dashas_or_chart: dict, now: Optional[datetime] = None) -> dict:
    """Определить текущий период Маха-Даша и Антар-Даша."""
    if now is None:
        now = datetime.now()

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


def check_sade_sati(chart_or_moon_sign) -> dict:
    """Проверить статус Саде-Сати (транзит Сатурна относительно натальной Луны).

    Принимает либо chart_data (dict), либо строку со знаком Луны (str).
    Возвращает dict с полями: active, phase, phase_ru, saturn_sign, moon_sign, description.
    """
    if isinstance(chart_or_moon_sign, dict):
        natal_moon_sign = None
        for p in chart_or_moon_sign.get("planets", []):
            if p.get("name") == "Moon":
                natal_moon_sign = p.get("sign")
                break
    else:
        natal_moon_sign = str(chart_or_moon_sign)

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

    result = {
        "natal_moon_sign": natal_moon_sign,
        "natal_moon_sign_ru": SIGN_NAMES_RU.get(natal_moon_sign, natal_moon_sign),
        "moon_sign": natal_moon_sign,
        "moon_sign_ru": SIGN_NAMES_RU.get(natal_moon_sign, natal_moon_sign),
        "transit_saturn_sign": transit_saturn_sign,
        "transit_saturn_sign_ru": SIGN_NAMES_RU.get(transit_saturn_sign, transit_saturn_sign),
        "saturn_sign": transit_saturn_sign,
        "saturn_sign_ru": SIGN_NAMES_RU.get(transit_saturn_sign, transit_saturn_sign),
    }

    if distance == 11:  # 12-й знак от Луны
        result.update({"active": True, "phase": "rising",
                       "phase_ru": "🌅 Нарастание (Rising)",
                       "description": "Саде-Сати начинается. Сатурн в 12-м знаке от натальной Луны. "
                                      "Период подготовки и внутренних трансформаций."})
    elif distance == 0:  # Тот же знак = пик
        result.update({"active": True, "phase": "peak",
                       "phase_ru": "🔥 Пик (Peak)",
                       "description": "Пик Саде-Сати. Сатурн проходит по знаку натальной Луны. "
                                      "Самый интенсивный период кармических уроков."})
    elif distance == 1:  # 2-й знак от Луны
        result.update({"active": True, "phase": "setting",
                       "phase_ru": "🌇 Спад (Setting)",
                       "description": "Саде-Сати идёт на спад. Сатурн во 2-м знаке от натальной Луны. "
                                      "Уроки усвоены, начало восстановления."})
    else:
        result.update({"active": False, "phase": None, "phase_ru": None,
                       "description": "Саде-Сати сейчас НЕ активен. "
                                      f"Сатурн в {distance + 1}-м знаке от натальной Луны."})

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


def detect_yogas(chart_data: dict) -> list:
    """Обнаружить ведические йоги в натальной карте.

    Проверяет: Гаджакешари, Будхадитья, Панча Махапуруша, Раджа-йоги, Дхана-йоги.
    """
    yogas = []
    planets = chart_data.get("planets", [])
    houses = chart_data.get("houses", [])

    # Индекс планет по имени
    planet_map = {p["name"]: p for p in planets}

    # === 1. Гаджакешари йога: Юпитер в кендре от Луны ===
    moon = planet_map.get("Moon")
    jupiter = planet_map.get("Jupiter")
    if moon and jupiter:
        moon_sign_idx = SIGNS_ORDER.index(moon["sign"]) if moon["sign"] in SIGNS_ORDER else -1
        jup_sign_idx = SIGNS_ORDER.index(jupiter["sign"]) if jupiter["sign"] in SIGNS_ORDER else -1
        if moon_sign_idx >= 0 and jup_sign_idx >= 0:
            dist = (jup_sign_idx - moon_sign_idx) % 12
            if dist in [0, 3, 6, 9]:  # Кендры = 1, 4, 7, 10-й знак
                yogas.append({
                    "name": "Gajakeshari Yoga",
                    "name_ru": "🐘 Гаджакешари Йога",
                    "type": "success",
                    "description": "Юпитер в кендре от Луны — йога мудрости, славы и благосостояния.",
                    "planets": ["Moon", "Jupiter"],
                    "active": True,
                })

    # === 2. Будхадитья йога: Солнце и Меркурий в одном знаке ===
    sun = planet_map.get("Sun")
    mercury = planet_map.get("Mercury")
    if sun and mercury and sun["sign"] == mercury["sign"]:
        yogas.append({
            "name": "Budhaditya Yoga",
            "name_ru": "☀️ Будхадитья Йога",
            "type": "intellect",
            "description": "Солнце и Меркурий соединены — йога интеллекта и красноречия.",
            "planets": ["Sun", "Mercury"],
            "active": True,
        })

    # === 3. Панча Махапуруша йоги ===
    mahapurusha_names = {
        "Mars": ("Ручака", "Ruchaka", "силы и мужества"),
        "Mercury": ("Бхадра", "Bhadra", "интеллекта и общения"),
        "Jupiter": ("Хамса", "Hamsa", "духовности и мудрости"),
        "Venus": ("Малавья", "Malavya", "красоты и комфорта"),
        "Saturn": ("Шаша", "Shasha", "дисциплины и власти"),
    }
    for planet_name, (ru_name, en_name, quality) in mahapurusha_names.items():
        p = planet_map.get(planet_name)
        if not p:
            continue
        sign = p.get("sign")
        house = p.get("house")
        is_exalted = sign == PLANET_EXALTATION.get(planet_name)
        is_own = sign in PLANET_OWN_SIGNS.get(planet_name, [])
        is_kendra = house in KENDRA_HOUSES
        if (is_exalted or is_own) and is_kendra:
            yogas.append({
                "name": f"{en_name} Yoga",
                "name_ru": f"🏛️ {ru_name} Йога ({en_name})",
                "type": "mahapurusha",
                "description": f"{PLANET_NAMES_RU.get(planet_name, planet_name)} в своём знаке или экзальтации в кендре — йога {quality}.",
                "planets": [planet_name],
                "active": True,
            })

    # === 4. Раджа-йоги: связь хозяев кендр и трикон ===
    # Построить маппинг: хозяин → дом
    lord_to_houses = {}
    for h in houses:
        lord = h.get("lord")
        num = h.get("number")
        if lord:
            lord_to_houses.setdefault(lord, []).append(num)

    kendra_lords = set()
    trikona_lords = set()
    for lord, h_list in lord_to_houses.items():
        if any(h in KENDRA_HOUSES for h in h_list):
            kendra_lords.add(lord)
        if any(h in TRIKONA_HOUSES for h in h_list):
            trikona_lords.add(lord)

    # Планеты, являющиеся одновременно хозяевами кендры и триконы
    raja_lords = kendra_lords & trikona_lords
    # Или планеты-хозяева кендр и трикон, находящиеся в одном знаке
    for kl in kendra_lords:
        for tl in trikona_lords:
            if kl == tl:
                continue
            kl_p = planet_map.get(kl)
            tl_p = planet_map.get(tl)
            if kl_p and tl_p and kl_p.get("sign") == tl_p.get("sign"):
                yogas.append({
                    "name": "Raja Yoga",
                    "name_ru": f"👑 Раджа Йога ({PLANET_NAMES_RU.get(kl, kl)} + {PLANET_NAMES_RU.get(tl, tl)})",
                    "type": "raja",
                    "description": f"Соединение хозяина кендры ({kl}) и хозяина триконы ({tl}) — йога власти и успеха.",
                    "planets": [kl, tl],
                    "active": True,
                })

    # Одна планета — хозяин и кендры, и триконы
    for lord in raja_lords:
        h_list = lord_to_houses[lord]
        k_houses = [h for h in h_list if h in KENDRA_HOUSES]
        t_houses = [h for h in h_list if h in TRIKONA_HOUSES]
        if k_houses and t_houses:
            yogas.append({
                "name": "Raja Yoga",
                "name_ru": f"👑 Раджа Йога ({PLANET_NAMES_RU.get(lord, lord)})",
                "type": "raja",
                "description": f"{PLANET_NAMES_RU.get(lord, lord)} — хозяин и кендры ({k_houses}), и триконы ({t_houses}).",
                "planets": [lord],
                "active": True,
            })

    # === 5. Дхана-йоги: связь хозяев домов богатства (2, 5, 9, 11) с кендрами ===
    dhana_lords = set()
    for lord, h_list in lord_to_houses.items():
        if any(h in DHANA_HOUSES for h in h_list):
            dhana_lords.add(lord)

    for dl in dhana_lords:
        for kl in kendra_lords:
            if dl == kl:
                continue
            dl_p = planet_map.get(dl)
            kl_p = planet_map.get(kl)
            if dl_p and kl_p and dl_p.get("sign") == kl_p.get("sign"):
                yogas.append({
                    "name": "Dhana Yoga",
                    "name_ru": f"💰 Дхана Йога ({PLANET_NAMES_RU.get(dl, dl)} + {PLANET_NAMES_RU.get(kl, kl)})",
                    "type": "dhana",
                    "description": f"Соединение хозяина дома богатства ({dl}) и хозяина кендры ({kl}) — йога финансового благополучия.",
                    "planets": [dl, kl],
                    "active": True,
                })

    return yogas


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


