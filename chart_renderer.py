"""
Модуль отрисовки Северо-индийской натальной карты (Кундли D1)
в высоком графическом разрешении с использованием библиотеки Pillow (PIL).
"""
import io
import os
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont

# Порядковые номера знаков Зодиака (1 = Овен, ..., 12 = Рыбы)
SIGN_NUMBERS: Dict[str, int] = {
    'Aries': 1, 'Taurus': 2, 'Gemini': 3, 'Cancer': 4,
    'Leo': 5, 'Virgo': 6, 'Libra': 7, 'Scorpio': 8,
    'Sagittarius': 9, 'Capricorn': 10, 'Aquarius': 11, 'Pisces': 12
}

SIGN_NAMES_RU: Dict[str, str] = {
    'Aries': 'Овен', 'Taurus': 'Телец', 'Gemini': 'Близнецы', 'Cancer': 'Рак',
    'Leo': 'Лев', 'Virgo': 'Дева', 'Libra': 'Весы', 'Scorpio': 'Скорпион',
    'Sagittarius': 'Стрелец', 'Capricorn': 'Козерог', 'Aquarius': 'Водолей', 'Pisces': 'Рыбы'
}

# Аббревиатуры планет
PLANET_ABBR: Dict[str, str] = {
    'Ascendant': 'As',
    'Sun': 'Su',
    'Moon': 'Mo',
    'Mars': 'Ma',
    'Mercury': 'Me',
    'Jupiter': 'Ju',
    'Venus': 'Ve',
    'Saturn': 'Sa',
    'Rahu': 'Ra',
    'Ketu': 'Ke',
}

# Гармоничные ведические цвета планет на тёмном фоне
PLANET_COLORS: Dict[str, str] = {
    'As': '#38BDF8',  # Лагна (Асцендент) - Небесно-голубой
    'Su': '#FB923C',  # Солнце (Сурья) - Золотисто-оранжевый
    'Mo': '#F8FAFC',  # Луна (Чандра) - Лунно-белый / Серебристый
    'Ma': '#F87171',  # Марс (Мангала) - Кораллово-красный
    'Me': '#34D399',  # Меркурий (Будха) - Изумрудно-зелёный
    'Ju': '#FBBF24',  # Юпитер (Гуру) - Тёплый янтарный
    'Ve': '#F472B6',  # Венера (Шукра) - Нежно-розовый
    'Sa': '#A78BFA',  # Сатурн (Шани) - Лавандово-фиолетовый
    'Ra': '#94A3B8',  # Раху - Дымчато-серый
    'Ke': '#CBD5E1',  # Кету - Серебристо-дымчатый
}


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Кроссплатформенная загрузка шрифта с безопасным fallback."""
    font_names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "tahoma.ttf",
        "seguiemj.ttf",
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size=size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_kundli_chart(
    chart_data: Dict[str, Any],
    profile_name: Optional[str] = None,
    dob_str: Optional[str] = None,
    tob_str: Optional[str] = None,
    place_str: Optional[str] = None,
) -> io.BytesIO:
    """
    Генерирует высококачественное PNG-изображение Северо-индийской натальной карты (D1).
    Возвращает BytesIO с бинарными данными PNG.
    """
    # Размеры холста
    CANVAS_W, CANVAS_H = 800, 860
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), color="#0B132B")  # Глубокий сапфировый/космический фон
    draw = ImageDraw.Draw(img)

    font_title = _get_font(20, bold=True)
    font_sub = _get_font(13, bold=False)
    font_lagna = _get_font(14, bold=True)
    font_sign = _get_font(13, bold=True)
    font_planet = _get_font(14, bold=True)
    font_footer = _get_font(11, bold=False)

    # 1. Заголовок карты
    title_text = "ВЕДИЧЕСКАЯ КАРТА КУНДЛИ (РАШИ D1)"
    draw.text((CANVAS_W // 2, 22), title_text, fill="#F59E0B", font=font_title, anchor="mt")

    # Сведения о рождении
    meta_parts = []
    if profile_name:
        meta_parts.append(str(profile_name))
    if dob_str:
        meta_parts.append(str(dob_str))
    if tob_str:
        meta_parts.append(str(tob_str))
    if place_str:
        meta_parts.append(str(place_str))

    meta_line = " • ".join(meta_parts) if meta_parts else "Натальная карта"
    draw.text((CANVAS_W // 2, 48), meta_line, fill="#94A3B8", font=font_sub, anchor="mt")

    # Определение знака Лагны
    houses = chart_data.get("houses", [])
    lagna_sign = None
    lagna_deg = None
    if houses and len(houses) > 0 and isinstance(houses[0], dict):
        lagna_sign = houses[0].get("sign")
        lagna_deg = houses[0].get("degrees")

    lagna_ru = SIGN_NAMES_RU.get(lagna_sign, lagna_sign or "Неизвестно")
    lagna_deg_str = f"{lagna_deg:.1f}°" if lagna_deg is not None else ""
    lagna_text = f"Лагна (Асцендент): {lagna_ru} {lagna_deg_str}".strip()
    draw.text((CANVAS_W // 2, 68), lagna_text, fill="#38BDF8", font=font_lagna, anchor="mt")

    # 2. Геометрия Северо-индийской карты (Diamond chart)
    x0, y0 = 50, 95
    w, h = 700, 700
    x1, y1 = x0 + w, y0 + h

    xmid = (x0 + x1) // 2
    ymid = (y0 + y1) // 2
    xq1 = x0 + w // 4
    xq3 = x0 + 3 * w // 4
    yq1 = y0 + h // 4
    yq3 = y0 + 3 * h // 4

    # Декоративная фоновая заливка центральных домов (Кендры 1, 4, 7, 10)
    kendra_color = "#111C44"
    draw.polygon([(xmid, y0), (xq1, yq1), (xmid, ymid), (xq3, yq1)], fill=kendra_color)  # Дом 1
    draw.polygon([(x0, ymid), (xq1, yq1), (xmid, ymid), (xq1, yq3)], fill=kendra_color)  # Дом 4
    draw.polygon([(xmid, y1), (xq1, yq3), (xmid, ymid), (xq3, yq3)], fill=kendra_color)  # Дом 7
    draw.polygon([(x1, ymid), (xq3, yq1), (xmid, ymid), (xq3, yq3)], fill=kendra_color)  # Дом 10

    # Линии сетки
    BORDER_COLOR = "#D97706"  # Тёплое золото
    DIAG_COLOR = "#B45309"    # Глубокий янтарь

    # Внешняя рамка
    draw.rectangle([x0, y0, x1, y1], outline=BORDER_COLOR, width=3)
    # Диагонали
    draw.line([x0, y0, x1, y1], fill=DIAG_COLOR, width=2)
    draw.line([x1, y0, x0, y1], fill=DIAG_COLOR, width=2)
    # Ромб в центре (линии между серединами сторон)
    draw.line([xmid, y0, x1, ymid], fill=BORDER_COLOR, width=2)
    draw.line([x1, ymid, xmid, y1], fill=BORDER_COLOR, width=2)
    draw.line([xmid, y1, x0, ymid], fill=BORDER_COLOR, width=2)
    draw.line([x0, ymid, xmid, y0], fill=BORDER_COLOR, width=2)

    # 3. Координаты домов (Центр для планет и позиция для номера знака)
    # Формат: house_num: ((center_x, center_y), (sign_x, sign_y))
    house_positions: Dict[int, Tuple[Tuple[int, int], Tuple[int, int]]] = {
        1:  ((xmid, yq1), (xmid, ymid - 28)),
        2:  ((xq1, y0 + h // 11), (xq1 + 32, yq1 - 25)),
        3:  ((x0 + w // 11, yq1), (xq1 - 25, yq1 + 32)),
        4:  ((xq1, ymid), (xmid - 28, ymid)),
        5:  ((x0 + w // 11, yq3), (xq1 - 25, yq3 - 32)),
        6:  ((xq1, y1 - h // 11), (xq1 + 32, yq3 + 25)),
        7:  ((xmid, yq3), (xmid, ymid + 28)),
        8:  ((xq3, y1 - h // 11), (xq3 - 32, yq3 + 25)),
        9:  ((x1 - w // 11, yq3), (xq3 + 25, yq3 - 32)),
        10: ((xq3, ymid), (xmid + 28, ymid)),
        11: ((x1 - w // 11, yq1), (xq3 + 25, yq1 + 32)),
        12: ((xq3, y0 + h // 11), (xq3 - 32, yq1 - 25)),
    }

    # Построение соответствия: дом -> номер знака Зодиака
    house_sign_num: Dict[int, int] = {}
    for h_obj in houses:
        h_num = h_obj.get("number")
        s_name = h_obj.get("sign")
        if h_num and s_name in SIGN_NUMBERS:
            house_sign_num[h_num] = SIGN_NUMBERS[s_name]

    # Отрисовка номеров знаков в домах
    for h_num in range(1, 13):
        pos = house_positions[h_num]
        sign_n = house_sign_num.get(h_num)
        if sign_n is not None:
            sx, sy = pos[1]
            draw.text((sx, sy), str(sign_n), fill="#CBD5E1", font=font_sign, anchor="mm")

    # Группировка планет по домам
    house_planets: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(1, 13)}

    # Добавляем Лагну (As) в Дом 1
    if lagna_sign:
        house_planets[1].append({
            "abbr": "As",
            "name": "Ascendant",
            "degrees": lagna_deg,
            "motion": "direct"
        })

    # Добавляем все остальные планеты
    for p in chart_data.get("planets", []):
        h_idx = p.get("house")
        if h_idx in house_planets:
            p_name = p.get("name", "")
            abbr = PLANET_ABBR.get(p_name, p_name[:2])
            house_planets[h_idx].append({
                "abbr": abbr,
                "name": p_name,
                "degrees": p.get("degrees"),
                "motion": p.get("motion", "direct")
            })

    # 4. Отрисовка планет внутри домов
    for h_num, p_list in house_planets.items():
        if not p_list:
            continue
        cx, cy = house_positions[h_num][0]
        n_planets = len(p_list)
        line_height = 16
        start_y = cy - ((n_planets - 1) * line_height) // 2

        for idx, pl in enumerate(p_list):
            abbr = pl["abbr"]
            deg = pl.get("degrees")
            motion = pl.get("motion")
            retro = " [R]" if motion == "retrograde" and abbr != "As" else ""
            deg_str = f" {int(deg)}°" if deg is not None else ""

            label = f"{abbr}{retro}{deg_str}"
            color = PLANET_COLORS.get(abbr, "#FFFFFF")
            py = start_y + idx * line_height

            draw.text((cx, py), label, fill=color, font=font_planet, anchor="mm")

    # 5. Нижний колонтитул
    footer_text = "NASA JPL DE421 Ephemeris • Аянамша Читра-Пакша (Лахири) • ИИ-Джьотиш"
    draw.text((CANVAS_W // 2, 825), footer_text, fill="#64748B", font=font_footer, anchor="mt")

    # Сохранение в BytesIO
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
