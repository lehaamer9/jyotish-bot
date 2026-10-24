"""
Модуль умного парсинга строкового ввода данных рождения.
Позволяет пользователю вводить все данные натальной карты одной строкой:
«Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город» или вариации.
"""

import re
from datetime import date, time
from typing import Optional, Dict, Any


INSTRUCTION_WORDS = {
    'исправь', 'исправьте', 'измени', 'измените', 'обнови', 'обновите',
    'поменяй', 'поменяйте', 'пересчитай', 'пересчитайте', 'пересчет', 'пересчёт',
    'скорректируй', 'скорректируйте', 'ошибка', 'опечатка', 'неверная', 'неправильная',
    'верная', 'правильная', 'новая', 'новые', 'новый', 'моя', 'моё', 'мой', 'актуальная',
    'точная', 'дата', 'дату', 'даты', 'дате', 'время', 'времени', 'город', 'городе',
    'данные', 'данных', 'информация', 'информацию', 'профиль', 'профиля', 'карту', 'карта',
    'гороскоп', 'рождения', 'на', 'в', 'во', 'плиз', 'пожалуйста', 'и', 'или',
    'edit', 'recalc', 'recalculate', 'update', 'fix', 'change', 'correct', 'correction',
    'date', 'time', 'city', 'profile', 'chart', 'horoscope', 'birth', 'dob', 'tob', 'new',
    'actual', 'true', 'wrong', 'at', 'to', 'in', 'and', 'or', 'for',
    'modifica', 'ricalcola', 'aggiorna', 'correggi', 'errore', 'data', 'ora', 'città', 'citta',
    'profilo', 'carta', 'dati', 'nuova', 'corretta', 'esatta', 'di', 'nascita', 'a', 'e'
}


DISCUSSIVE_STOP_WORDS_RE = re.compile(
    r'\b(?:'
    r'в\s+боте|бот[а-яё]*|bot[s]?|'
    r'период[а-яё]*|period[s]?|periodo|periodi|'
    r'даш[а-яё]*|dasha[s]?|dasa[s]?|махадаш[а-яё]*|антардаш[а-яё]*|mahadasha|antardasha|'
    r'почему|зачем|why|perch[eé]|'
    r'сейчас|adesso|currently|attualmente|now|'
    r'кончающ[а-яё]*|закончил[а-яё]*|завершил[а-яё]*|заканчива[а-яё]*|ended|ends|terminat[a-z]*|'
    r'сказал[а-яё]*|говорит|пишет|показывает|said|says|dice|mostra|'
    r'ошибк[а-яё]*|error[s]?|errore|errori|wrong|incorrect|sbagliat[oaie]|errat[oaie]|неправильн[а-яё]*|неверн[а-яё]*|баг[а-яё]*|bug[s]?|сбой[а-яё]*|'
    r'март|марте|(?:(?:с|до|по|в|вплоть\s+до)\s+)?марта\s+\d{4}|march|marzo|'
    r'октябр[а-яё]*|october|ottobre'
    r')\b',
    re.IGNORECASE
)


def is_discussive_or_error_query(text: Optional[str]) -> bool:
    """Проверяет, содержит ли текст рассуждения о периодах/датах/ошибках бота."""
    if not text or not isinstance(text, str):
        return False
    cleaned = re.sub(r'@\w+bot\b', '', text, flags=re.IGNORECASE)
    return bool(DISCUSSIVE_STOP_WORDS_RE.search(cleaned))


def is_instruction_phrase(text: Optional[str]) -> bool:
    """Проверяет, состоит ли строка исключительно из служебных/инструкционных слов."""
    if not text:
        return True
    cleaned = re.sub(r'[:=,\-–\s]+', ' ', text.strip().lower())
    words = cleaned.split()
    return len(words) > 0 and all(w in INSTRUCTION_WORDS for w in words)


def extract_clean_name(text: Optional[str]) -> Optional[str]:
    """Очищает имя от служебных префиксов («Имя:»), команд редактирования и инструкций."""
    if not text:
        return None
    raw = text.strip()
    raw = re.sub(
        r'^(?:имя\s*[:=-]?\s*|профиль\s*[:=-]?\s*|меня\s+зовут\s+|name\s*[:=-]?\s*|profile\s*[:=-]?\s*|my\s+name\s+is\s+|nome\s*[:=-]?\s*|profilo\s*[:=-]?\s*|mi\s+chiamo\s+)',
        '',
        raw,
        flags=re.IGNORECASE
    ).strip(" ,;:\t\n-")
    raw = re.sub(r'\s+(?:родился|родилась|born|nato|nata)\b.*', '', raw, flags=re.IGNORECASE).strip(" ,;:\t\n-")

    if is_discussive_or_error_query(raw) or is_instruction_phrase(raw):
        return None

    words = [w for w in re.split(r'[,;:\s]+', raw) if w]
    while words and words[0].lower() in INSTRUCTION_WORDS:
        words.pop(0)
    while words and words[-1].lower() in INSTRUCTION_WORDS:
        words.pop()

    if not words:
        return None

    res = " ".join(words)
    if is_discussive_or_error_query(res) or is_instruction_phrase(res):
        return None
    return res


def parse_one_line_profile(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Умный парсер строки для быстрого создания или обновления натального профиля.
    
    Поддерживаемые форматы:
    - «Александр, 20.06.1996, 08:25, Горно-Алтайск»
    - «Александр 15.05.1990 10:30 Москва»
    - «20.06.1996 08:25 Горно-Алтайск»
    - «15.05.1990 10:30 Москва, Александр»
    - «/chart Александр, 20.06.1996, 08:25, Горно-Алтайск»
    - «/edit 20.06.1996 08:25 Горно-Алтайск»
    - «исправь дату 20.06.1996 08:25 Горно-Алтайск»
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
    text = re.sub(r"^/(?:chart|natal|newprofile|edit|recalc|editprofile|update|fix)\b\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"^@\w+\s*", "", text).strip()
    # Очистка вводных фраз пересчёта/редактирования в начале строки
    text = re.sub(
        r"^(?:\b(?:edit|recalc|recalculate|update|fix|change)\b|"
        r"\b(?:исправь(?:те)?|измени(?:те)?|обнови(?:те)?|поменяй(?:те)?|пересчитай(?:те)?|скорректируй(?:те)?)\b(?:\s+(?:пожалуйста|плиз))?(?:\s+(?:мне|нам))?(?:\s+(?:дату|время|город|место|данные|профиль|карту|гороскоп))?(?:\s+(?:на|в|to|a))?|"
        r"\b(?:ошибка|опечатка)\s+(?:в\s+дате|даты|во\s+времени|времени|в\s+городе|города|в\s+данных)?(?:\s*[:=-])?|"
        r"\b(?:верная|правильная|новая|моя|моё|мой|актуальная|точная)\s+(?:дата|время|город|информация|данные)?(?:\s*[:=-])?|"
        r"\b(?:дата|время|город|место|данные)(?:\s+рождения)?\s*[:=-]|"
        r"\b(?:data|ora|citt[àa])(?:\s+di\s+nascita)?\s*[:=-]|"
        r"\b(?:modifica|ricalcola|aggiorna|correggi)\b(?:\s+(?:data|ora|citt[àa]|profilo|carta|dati))?(?:\s+(?:a|in))?|"
        r"\b(?:date|time|city|dob|tob)\s*[:=-])\s*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip(" ,;:\t\n-")
    if not text or is_discussive_or_error_query(text):
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
    # Игнорируем предлоги 'в', 'at', 'alle', 'ore'
    time_match = re.search(r'(?:\b(?:в|at|alle|ore)\s+)?\b([01]?\d|2[0-3])[:.]([0-5]\d)\b', masked, flags=re.IGNORECASE)
    
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

        # Очистка вводных предлогов из промежуточной части (RU, EN, IT)
        part_middle = re.sub(r'^(?:в|родился\s+в|родилась\s+в|born\s+in|nato\s+a|nata\s+a|at|alle|ore)\s*', '', part_middle, flags=re.IGNORECASE).strip(" ,;:\t\n-")
        part_after = re.sub(r'^(?:в\s+|in\s+|at\s+|a\s+)?(?:г\.|г(?:ород[еау]?)\b|city\b|citt[àa]\b)?\s*', '', part_after, flags=re.IGNORECASE).strip(" ,;:\t\n-")

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
            # Сначала проверяем явное указание имени в конце (в скобках или с префиксом)
            paren_match = re.search(r'\((?:(?:имя|name|nome)\s*[:=-]?\s*)?([^)]+)\)\s*$', part_after, flags=re.IGNORECASE)
            name_kw_match = re.search(r'[,;]?\s*(?:имя|профиль|зов[уе]т|name|profile|nome|profilo)\s*[:=-]?\s*([A-Za-zА-Яа-яЁё\s]+)$', part_after, flags=re.IGNORECASE)

            if paren_match:
                name = paren_match.group(1).strip()
                city = part_after[:paren_match.start()].strip(" ,;:\t\n-")
            elif name_kw_match:
                name = name_kw_match.group(1).strip()
                city = part_after[:name_kw_match.start()].strip(" ,;:\t\n-")
            elif "," in part_after:
                parts = [p.strip() for p in part_after.split(",") if p.strip()]
                # Проверяем, не является ли вторая часть страной или регионом (например «Рим, Италия», «London, UK»)
                country_region_keywords = {
                    "россия", "рф", "италия", "украина", "беларусь", "казахстан", "сша", "германия",
                    "франция", "испания", "турция", "индия", "таиланд", "китай", "грузия", "армения",
                    "азербайджан", "узбекистан", "кыргызстан", "таджикистан", "оаэ", "египет", "греция",
                    "кипр", "польша", "израиль", "канада", "великобритания", "англия",
                    "область", "обл", "край", "район", "республика", "респ", "округ", "штат",
                    "russia", "italy", "italia", "usa", "uk", "germany", "france", "spain", "turkey", "india",
                    "thailand", "china", "georgia", "armenia", "uae", "egypt", "greece", "cyprus",
                    "poland", "israel", "canada", "state", "region", "province"
                }
                last_part = parts[-1].lower()
                last_part_words = set(re.findall(r'[a-za-яё]+', last_part))
                is_geo = bool(last_part_words & country_region_keywords)

                if not is_geo and len(parts) == 2 and len(parts[1].split()) <= 2:
                    # «15.05.1990 10:30 Москва, Александр» -> city='Москва', name='Александр'
                    city = parts[0]
                    name = parts[1]
                else:
                    # «15.05.1990 10:30 Горно-Алтайск, Россия» -> city='Горно-Алтайск, Россия', name=None
                    city = part_after
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

    # Очистка имени от служебных префиксов и команд
    name = extract_clean_name(name)

    # Очистка города
    if city:
        city = re.sub(r'^(?:в\s+|in\s+|at\s+|a\s+)?(?:г\.|г(?:ород[еау]?)\b|city\b|citt[àa]\b)?\s*', '', city, flags=re.IGNORECASE).strip(" ,;:\t\n-")
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
