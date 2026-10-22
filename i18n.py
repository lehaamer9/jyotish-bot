"""
Модуль интернационализации (i18n) и локализации для Джьотиш-Бота.
Поддерживает три языка:
- Русский (ru) — язык по умолчанию и фолбэк
- Английский (en)
- Итальянский (it)

Обеспечивает автоматическое определение языка пользователя по клиенту Telegram,
ручное переключение через /lang, локализацию текстов, клавиатур, астрологических терминов
и системных инструкций для ИИ-интерпретатора.
"""

import re
from typing import Optional, Dict, Any, List
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

SUPPORTED_LANGUAGES: List[str] = ["ru", "en", "it"]
DEFAULT_LANGUAGE: str = "ru"

LANGUAGE_LABELS: Dict[str, str] = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "it": "🇮🇹 Italiano",
}


def normalize_language(lang_code: Optional[str]) -> str:
    """
    Нормализует код языка Telegram (например, 'it', 'it-IT', 'en-US', 'ru')
    к поддерживаемым 'ru', 'en', 'it'. По умолчанию возвращает 'ru'.
    """
    if not lang_code or not isinstance(lang_code, str):
        return DEFAULT_LANGUAGE

    code = lang_code.strip().lower().replace("_", "-")
    if code.startswith("it"):
        return "it"
    elif code.startswith("en"):
        return "en"
    elif code.startswith(("ru", "be", "uk", "kk")):
        return "ru"

    return DEFAULT_LANGUAGE


def get_user_lang(
    update: Optional[Any] = None,
    context: Optional[Any] = None,
    user_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> str:
    """
    Определяет язык пользователя по приоритету:
    1. Ручная настройка в БД (user_settings.language)
    2. Язык Telegram-клиента (update.effective_user.language_code)
    3. Фолбэк по умолчанию ('ru')
    """
    uid = user_id
    if uid is None and update and getattr(update, "effective_user", None):
        uid = update.effective_user.id

    if uid:
        if context is not None and getattr(context, "user_data", None) is not None:
            if "user_lang" in context.user_data and context.user_data["user_lang"]:
                return context.user_data["user_lang"]

        try:
            from db_manager import get_user_language
            saved = get_user_language(uid, db_path=db_path)
            if saved:
                norm = normalize_language(saved)
                if context is not None and getattr(context, "user_data", None) is not None:
                    context.user_data["user_lang"] = norm
                return norm
        except Exception:
            pass

    if update and getattr(update, "effective_user", None):
        lang_code = getattr(update.effective_user, "language_code", None)
        if lang_code:
            norm = normalize_language(lang_code)
            if context is not None and getattr(context, "user_data", None) is not None:
                context.user_data["user_lang"] = norm
            return norm

    return DEFAULT_LANGUAGE


# =========================================================================
# АСТРОЛОГИЧЕСКИЕ НАИМЕНОВАНИЯ (Планеты, Знаки, Дома)
# =========================================================================

PLANET_NAMES: Dict[str, Dict[str, str]] = {
    "ru": {
        "Sun": "Сурья (Солнце)", "Moon": "Чандра (Луна)", "Mars": "Мангала (Марс)",
        "Mercury": "Будха (Меркурий)", "Jupiter": "Гуру (Юпитер)", "Venus": "Шукра (Венера)",
        "Saturn": "Шани (Сатурн)", "Rahu": "Раху", "Ketu": "Кету", "Ascendant": "Лагна (Асцендент)"
    },
    "en": {
        "Sun": "Sun (Surya)", "Moon": "Moon (Chandra)", "Mars": "Mars (Mangala)",
        "Mercury": "Mercury (Budha)", "Jupiter": "Jupiter (Guru)", "Venus": "Venus (Shukra)",
        "Saturn": "Saturn (Shani)", "Rahu": "Rahu", "Ketu": "Ketu", "Ascendant": "Lagna (Ascendant)"
    },
    "it": {
        "Sun": "Sole (Surya)", "Moon": "Luna (Chandra)", "Mars": "Marte (Mangala)",
        "Mercury": "Mercurio (Budha)", "Jupiter": "Giove (Guru)", "Venus": "Venere (Shukra)",
        "Saturn": "Saturno (Shani)", "Rahu": "Rahu", "Ketu": "Ketu", "Ascendant": "Lagna (Ascendente)"
    }
}

SIGN_NAMES: Dict[str, Dict[str, str]] = {
    "ru": {
        "Aries": "Овен (Меша)", "Taurus": "Телец (Вришабха)", "Gemini": "Близнецы (Митхуна)",
        "Cancer": "Рак (Карка)", "Leo": "Лев (Симха)", "Virgo": "Дева (Канья)",
        "Libra": "Весы (Тула)", "Scorpio": "Скорпион (Вришчика)", "Sagittarius": "Стрелец (Дхану)",
        "Capricorn": "Козерог (Макара)", "Aquarius": "Водолей (Кумбха)", "Pisces": "Рыбы (Мина)"
    },
    "en": {
        "Aries": "Aries (Mesha)", "Taurus": "Taurus (Vrishabha)", "Gemini": "Gemini (Mithuna)",
        "Cancer": "Cancer (Karka)", "Leo": "Leo (Simha)", "Virgo": "Virgo (Kanya)",
        "Libra": "Libra (Tula)", "Scorpio": "Scorpio (Vrishchika)", "Sagittarius": "Sagittarius (Dhanu)",
        "Capricorn": "Capricorn (Makara)", "Aquarius": "Aquarius (Kumbha)", "Pisces": "Pisces (Meena)"
    },
    "it": {
        "Aries": "Ariete (Mesha)", "Toro": "Toro (Vrishabha)", "Taurus": "Toro (Vrishabha)", "Gemini": "Gemelli (Mithuna)",
        "Cancer": "Cancro (Karka)", "Leo": "Leone (Simha)", "Virgo": "Vergine (Kanya)",
        "Libra": "Bilancia (Tula)", "Scorpio": "Scorpione (Vrishchika)", "Sagittarius": "Sagittario (Dhanu)",
        "Capricorn": "Capricorno (Makara)", "Aquarius": "Acquario (Kumbha)", "Pisces": "Pesci (Meena)"
    }
}

SHORT_SIGN_NAMES: Dict[str, Dict[str, str]] = {
    "ru": {
        "Aries": "Овен", "Taurus": "Телец", "Gemini": "Близнецы", "Cancer": "Рак",
        "Leo": "Лев", "Virgo": "Дева", "Libra": "Весы", "Scorpio": "Скорпион",
        "Sagittarius": "Стрелец", "Capricorn": "Козерог", "Aquarius": "Водолей", "Pisces": "Рыбы"
    },
    "en": {
        "Aries": "Aries", "Taurus": "Taurus", "Gemini": "Gemini", "Cancer": "Cancer",
        "Leo": "Leo", "Virgo": "Virgo", "Libra": "Libra", "Scorpio": "Scorpio",
        "Sagittarius": "Sagittarius", "Capricorn": "Capricorn", "Aquarius": "Aquarius", "Pisces": "Pisces"
    },
    "it": {
        "Aries": "Ariete", "Taurus": "Toro", "Gemini": "Gemelli", "Cancer": "Cancro",
        "Leo": "Leone", "Virgo": "Vergine", "Libra": "Bilancia", "Scorpio": "Scorpione",
        "Sagittarius": "Sagittario", "Capricorn": "Capricorno", "Aquarius": "Acquario", "Pisces": "Pesci"
    }
}

DIGNITY_NAMES: Dict[str, Dict[str, str]] = {
    "ru": {
        "Exalted": "Экзальтация (Учча)",
        "Own Sign": "Свой знак (Сваграха)",
        "Moolatrikona": "Мулатрикона",
        "Debilitated": "Падение (Нича)",
        "Great Friend": "Большой друг",
        "Friend": "Друг",
        "Neutral": "Нейтральный",
        "Enemy": "Враг",
        "Great Enemy": "Большой враг",
    },
    "en": {
        "Exalted": "Exalted (Uchcha)",
        "Own Sign": "Own Sign (Swagraha)",
        "Moolatrikona": "Moolatrikona",
        "Debilitated": "Debilitated (Neecha)",
        "Great Friend": "Great Friend",
        "Friend": "Friend",
        "Neutral": "Neutral",
        "Enemy": "Enemy",
        "Great Enemy": "Great Enemy",
    },
    "it": {
        "Exalted": "Esaltazione (Uchcha)",
        "Own Sign": "Segno proprio (Swagraha)",
        "Moolatrikona": "Moolatrikona",
        "Debilitated": "Caduta (Neecha)",
        "Great Friend": "Grande amico",
        "Friend": "Amico",
        "Neutral": "Neutrale",
        "Enemy": "Nemico",
        "Great Enemy": "Grande nemico",
    }
}


def get_planet_name(planet: str, lang: str = "ru") -> str:
    lang = normalize_language(lang)
    return PLANET_NAMES.get(lang, PLANET_NAMES["ru"]).get(planet, planet)


def get_sign_name(sign: str, lang: str = "ru", short: bool = False) -> str:
    lang = normalize_language(lang)
    src = SHORT_SIGN_NAMES if short else SIGN_NAMES
    return src.get(lang, src["ru"]).get(sign, sign)


def get_dignity_name(dignity: str, lang: str = "ru") -> str:
    lang = normalize_language(lang)
    return DIGNITY_NAMES.get(lang, DIGNITY_NAMES["ru"]).get(dignity, dignity)


# =========================================================================
# СЛОВАРЬ ТЕКСТОВЫХ СООБЩЕНИЙ (TRANSLATIONS)
# =========================================================================

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ru": {
        # Общие команды и интерфейс
        "choose_language": (
            "🌐 *Выбор языка интерфейса / Select language:*\n\n"
            "Выбери предпочитаемый язык для общения с ботом, расчётов карт и ИИ-трактовок:\n"
            "• 🇷🇺 Русский\n"
            "• 🇬🇧 English\n"
            "• 🇮🇹 Italiano\n\n"
            "Или выбери *Auto*, чтобы язык определялся по настройкам приложения Telegram."
        ),
        "lang_switched": "✅ Язык интерфейса успешно изменён на *Русский*! 🇷🇺\nВсе расчёты и ответы ИИ теперь будут на русском языке.",
        "lang_auto_switched": "🌐 Язык интерфейса переключён в режим *Авто* (по языку твоего Telegram: *{selected_lang}*).",

        # Start
        "start_greeting": (
            "🙏 *Намасте! Я — ИИ-Джьотиш Астролог.*\n\n"
            "Я сочетаю традиционную ведическую астрологию Парашара Муни "
            "с современными космическими эфемеридами NASA JPL и искусственным интеллектом Google Gemini.\n\n"
            "✨ *Что я умею:*\n"
            "🪐 Рассчитывать точную натальную карту (Кундли D1, Лагна, дома, планеты, Шадбала)\n"
            "⏳ Вычислять периоды судьбы (*Вимшоттари Даша* на всю жизнь)\n"
            "💞 Анализировать совместимость партнёров (*Аштакута / 8 факторов любви*)\n"
            "❓ Задавать вопросы ИИ-астрологу по своей карте\n"
            "🔄 Проверять период Саде-Сати (транзит Сатурна)\n"
            "🧘 Находить мощные йоги в натальной карте\n"
            "👥 Сохранять несколько профилей (для себя, партнёра, детей, семьи)\n\n"
            "📌 *Команды бота:*\n"
            "👉 /chart — составить натальную карту\n"
            "👉 /profile — управление профилями (выбор, добавление, удаление)\n"
            "👉 /newprofile — создать новый профиль\n"
            "👉 /dasha — периоды жизни (Вимшоттари Даша)\n"
            "👉 /compat — совместимость с партнёром\n"
            "👉 /ask — задать вопрос ИИ-астрологу\n"
            "👉 /sadesati — проверить Саде-Сати\n"
            "👉 /yoga — найти йоги в карте\n"
            "👉 /karma — кармическая задача души\n"
            "👉 /money — финансы и карьера\n"
            "👉 /upaya — ведические упайи (гармонизация)\n"
            "👉 /prices — стоимость услуг в Звёздах Telegram (⭐️)\n"
            "👉 /lang — смена языка интерфейса (RU/EN/IT)\n"
            "👉 /mydata — посмотреть сохранённые данные\n"
            "👉 /reset — сброс данных\n"
            "👉 /help — справка\n\n"
        ),
        "start_active_profile": (
            "👤 *Твой активный профиль:* «{name}»\n"
            "📅 Дата: `{dt}` | 📍 `{place}`\n\n"
            "Карта готова! Ты можешь сразу перейти к расчётам или управлять профилями через /profile.\n"
            "👇 *Выбери действие на кнопках ниже:*"
        ),
        "start_no_profile": "👇 *Выбери действие на кнопках ниже или нажми /chart, чтобы начать:*",

        # Help
        "help_text": (
            "📖 *Справка по Джьотиш-Боту:*\n\n"
            "🔹 /chart — Составление натальной карты (дата, время, город рождения).\n"
            "🔹 /profile — Управление профилями (выбор активного, просмотр, удаление).\n"
            "🔹 /newprofile — Создание дополнительного профиля (партнёр, родственники).\n"
            "🔹 /karma — Кармическая задача души и Чара-Караки (Атмакарака).\n"
            "🔹 /money — Финансовый код, дома богатства и стратегия карьеры.\n"
            "🔹 /upaya — Персональные Ведические Упайи (методы гармонизации).\n"
            "🔹 /dasha — Разбор планетных периодов Вимшоттари Даша.\n"
            "🔹 /compat — Синастрия и совместимость по 8 ведическим показателям.\n"
            "🔹 /ask — Задать любой вопрос ИИ-астрологу по своей карте.\n"
            "🔹 /sadesati — Проверить, идёт ли период Саде-Сати (транзит Сатурна).\n"
            "🔹 /yoga — Найти мощные йоги (комбинации планет) в натальной карте.\n"
            "🔹 /prices — Тарифы на подробные ИИ-разборы (оплата в ⭐️ Telegram Stars).\n"
            "🔹 /lang — Выбор языка (Русский, English, Italiano).\n"
            "🔹 /mydata — Показывает введённые дату, время и координаты активного профиля.\n"
            "🔹 /reset — Сброс сохранённых данных.\n"
            "🔹 /cancel — Отмена текущего шага ввода.\n\n"
            "💡 *Оплата:* Базовые расчёты бесплатны. Подробные трактовки оплачиваются в ⭐️ Telegram Stars прямо в приложении."
        ),

        # Prices
        "prices_header": "⭐️ *Прайс-лист на ИИ-разборы (Telegram Stars):*\n\n",
        "prices_body": (
            "🔮 **Полный разбор натальной карты:** `{chart} ⭐️`\n"
            "  • Характер, Лагна, миссия души, карьера, финансы, отношения, персональные упайи.\n\n"
            "🔮 **Кармическая задача души (Атмакарака):** `{karma} ⭐️`\n"
            "  • Расчёт 7 карак Джаймини, главные кармические уроки души и вектор предназначения.\n\n"
            "💰 **Финансовый код и карьера:** `{money} ⭐️`\n"
            "  • Анализ 2-го и 11-го домов богатства, Дхана-йоги и стратегия заработка от ИИ.\n\n"
            "⏳ **Разбор периодов Вимшоттари Даша:** `{dasha} ⭐️`\n"
            "  • Текущая Маха-Даша и Антар-Даша, уроки периода, точки роста, предостережения.\n\n"
            "💞 **Анализ совместимости (Аштакута):** `{compat} ⭐️`\n"
            "  • 8 факторов гармонии, сексуальное притяжение (Йони), ментальное согласие, кармические узлы.\n\n"
            "❓ **Экспресс-вопрос ИИ-астрологу:** `{ask} ⭐️`\n"
            "  • Задай любой вопрос по своей натальной карте и получи персональный ответ.\n\n"
            "🧘 **Детектор йог + ИИ-трактовка:** `{yoga} ⭐️`\n"
            "  • Раджа-йога, Гаджакешари, Будхадитья, Дхана, Панча Махапуруша + разбор от ИИ.\n\n"
            "🌟 **Бандл «Вся судьба 360°»:** `{bundle} ⭐️`\n"
            "  • Натальная карта + Даша + Йоги + 1 вопрос — всё в одном со скидкой!\n\n"
            "🆓 *Бесплатно:* базовые расчёты, /sadesati (Саде-Сати), /upaya (Ведические Упайи), 1-й вопрос к ИИ.\n\n"
            "✨ Оплата производится в 1 клик через официальные звёзды Telegram (Apple Pay / Google Pay / карты)."
        ),

        # Profiles
        "profile_card_header": "🔮 *Активный профиль: «{name}»*\n\n📅 Дата: `{dob}`\n⏰ Время: `{tob}`\n📍 Место: `{place}`\n🌐 Координаты: `{lat:.4f}, {lon:.4f}` (UTC{tz:+.1f})\n\nНатальная карта для этого профиля уже сохранена! Выбери действие:",
        "no_profile_found": "У тебя пока нет сохранённого астрологического профиля.\nНажми /chart, чтобы составить первую натальную карту!",
        "profile_list_header": "👤 *Твои сохранённые профили:*\n(Всего: {count})\n\n",
        "profile_active_badge": "⭐️ *АКТИВНЫЙ:*",
        "profile_other_badge": "•",
        "profile_action_prompt": "\nВыбери профиль для переключения или используй кнопки ниже:",
        "profile_switched_success": "✅ Активный профиль переключён на *«{name}»*!\n\nТеперь все расчёты (/chart, /dasha, /sadesati, /yoga, /ask) работают для этого человека.",
        "profile_switch_fail": "Не удалось переключить профиль. Открой /profile.",
        "profile_delete_menu": "🗑 *Выбери профиль для удаления:*\n_Внимание: удаление необратимо._",
        "profile_delete_success": "🗑 Профиль *«{name}»* успешно удалён.",
        "profile_delete_fail": "Не удалось удалить профиль.",
        "profile_no_profiles_to_delete": "У тебя нет сохранённых профилей для удаления.",
        "rename_prompt": "✏️ Введи команду в формате:\n`/rename Новое_Имя`",
        "rename_success": "✅ Профиль успешно переименован в *«{name}»*!",
        "profile_updated_header": "✅ *Профиль «{name}» успешно обновлён и пересчитан!*\n\n",
        "reset_success": "🗑 Все твои сохранённые профили и данные успешно сброшены.\nЧтобы начать заново, нажми /chart.",

        # Chart Dialog
        "ask_profile_name": "👤 Введи имя для нового профиля (например: *Александр*, *Анна*, *Сын Михаил*):",
        "ask_dob": (
            "📅 *Шаг 1 из 3:* Введи **дату рождения** в формате ДД.ММ.ГГГГ\n"
            "Например: `15.05.1990` или `24.12.1985`\n\n"
            "💡 *Лайфхак:* Ты можешь ввести все данные одной строкой:\n"
            "`Александр, 15.05.1990, 10:30, Москва`"
        ),
        "invalid_dob": "❌ Неверный формат даты! Введи дату в виде ДД.ММ.ГГГГ (например, `15.05.1990`):",
        "ask_tob": (
            "⏰ *Шаг 2 из 3:* Введи **точное время рождения** (местное) в формате ЧЧ:ММ\n"
            "Например: `10:30`, `18:45`, `04:15`\n\n"
            "_Если точное время неизвестно, введи `12:00` (полдень)._"
        ),
        "invalid_tob": "❌ Неверный формат времени! Введи время в виде ЧЧ:ММ (например, `10:30`):",
        "ask_place": (
            "📍 *Шаг 3 из 3:* Введи **город рождения** (и страну, если город небольшой)\n"
            "Например: `Москва`, `Рим, Италия`, `Новосибирск`, `London`"
        ),
        "place_resolving": "🔍 Ищу координаты города *«{place}»*...",
        "place_not_found": "❌ Не удалось найти город *«{place}»*. Попробуй ввести более крупный соседний город или указать страну:",
        "chart_calculating": "🌌 Рассчитываю планеты, Лагну, накшатры и периоды Даша через NASA JPL эфемериды...",
        "chart_ready_header": "🔮 *Ведическая карта Кундли (D1): {name}*",
        "chart_summary_caption": "👤 *Натальная карта профиля «{name}»*\n\n",
        "chart_one_line_success": "✅ Данные распознаны: *{name}*, `{dob}`, `{tob}`, `{place}`.",

        # Dasha
        "dasha_header": "🕐 *Вимшоттари Даша — периоды жизни:*\n\n",
        "dasha_balance": "⚖️ Баланс при рождении: {planet} — {years:.2f} лет\n\n",
        "dasha_current_badge": " ◀️ *ТЕКУЩИЙ*",
        "dasha_need_chart": "Сначала составь натальную карту через /chart.",

        # Compatibility
        "compat_choose_first": "💞 *Анализ совместимости партнёров (Аштакута)*\n\nУ тебя сохранён профиль: *«{name}»*.\nВыбери второго партнёра из списка или создай новый профиль:",
        "compat_ask_second_name": "👤 Введи имя партнёра для проверки совместимости:",
        "compat_result_header": "💞 *Результат ведической совместимости (Аштакута — 36 гун)*\n\n",
        "compat_score": "🏆 **Общий балл совместимости:** `{score} из 36`\n",
        "compat_verdict_excellent": "🌟 **Отличная совместимость!** Гармоничный союз для брака и совместной жизни.",
        "compat_verdict_good": "✨ **Хорошая совместимость.** Благоприятный союз с высоким взаимопониманием.",
        "compat_verdict_average": "⚖️ **Средняя совместимость.** Отношения требуют взаимных компромиссов и осознанности.",
        "compat_verdict_difficult": "⚠️ **Низкая совместимость.** Возможны частые разногласия, рекомендован глубокий анализ карт.",

        # Sade-Sati
        "sadesati_active": "🪐 *Период Саде-Сати:* ⚠️ **АКТИВЕН**\nФаза: *{phase}*\nПериод действия: `{start}` — `{end}`\n\nСатурн идёт транзитом по натальной Луне. Это время глубокой трансформации, дисциплины и духовного взросления.",
        "sadesati_inactive": "🪐 *Период Саде-Сати:* ✅ **НЕ АКТИВЕН**\nБлижайший транзит Сатурна начнётся: `{next_start}`.\n\nТекущий период свободен от прямого давления Саде-Сати.",

        # Yoga Detector
        "yogas_found_header": "🧘 *Обнаруженные йоги (планетные комбинации):*\n\n",
        "no_yogas_found": "В текущей конфигурации карты классических маха-йог первого уровня не обнаружено.",

        # Ask AI
        "ask_intro": "💬 *Задай любой вопрос ИИ-астрологу*\n\nСпроси о предназначении, карьере, браке, периодах жизни или здоровье. Ответ будет составлен строго по твоей натальной карте.\n\n👇 Напиши свой вопрос следующим сообщением:",
        "ask_free_available": "🎁 Твой первый вопрос к ИИ — *абсолютно бесплатно*!",
        "ask_thinking": "🔮 ИИ-Джьотиш анализирует твою натальную карту и планетные периоды... Пожалуйста, подожди несколько секунд.",

        # Cancel & Fallback
        "cancelled": "❌ Действие отменено.",
        "fallback_unknown": "Я не совсем понял команду. Нажми /help для справки или выбери действие в меню ниже.",

        # General UI & Dialogs
        "choose_next_action": "Выбери следующее действие:",
        "need_chart_first": "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
        "session_error": "Произошла ошибка сессии. Начни заново с /chart.",
        "chart_error": "❌ Ошибка при расчёте карты: {err}",
        "default_profile_name": "Мой гороскоп",
        "profile_indexed_name": "Профиль {index}",
        "resolving_city": "🌍 Определяю координаты и часовой пояс города...",
        "computing_chart": "🧮 Вычисляю позиции планет и домов по NASA JPL эфемеридам...",
        "city_not_found": "❌ Не удалось найти город '{city}'.\nОшибка: {err}\n\nПожалуйста, укажи город ещё раз (или нажми /cancel):",
        "name_saved_prompt": "👤 Запомнил имя: *{name}*!\n\nТеперь введи дату рождения (`ДД.ММ.ГГГГ`), например: `20.06.1996`\nили отправь остальные данные одной строкой (`ДД.ММ.ГГГГ, ЧЧ:ММ, Город`):",
        "invalid_name_prompt": "Пожалуйста, укажи понятное имя (до 50 символов):",
        "newprofile_intro": "👤 *Создание нового астрологического профиля*\n\nВведи данные одной строкой:\n`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n_(например: `Анна, 20.08.1992, 14:15, Санкт-Петербург`)_\n\nИли укажи только имя профиля _(например: `Жена`, `Анна`)_ для пошагового ввода.\n\nДля отмены набери /cancel",
        "chart_intro": "🔮 *Составление натальной карты*\n\nВведи данные одной строкой:\n`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n_(например: `Александр, 15.05.1990, 10:30, Москва`)_\n\nИли начни с даты рождения (`ДД.ММ.ГГГГ`), и мы заполним данные пошагово.\n\nДля отмены набери /cancel",
        "recalc_intro": "🔄 *Пересчёт профиля «{name}»*\n\nВведи новые данные одной строкой:\n`ДД.ММ.ГГГГ, ЧЧ:ММ, Город` (например: `15.05.1990, 10:30, Москва`)\n\nИли начни с даты рождения в формате `ДД.ММ.ГГГГ`:\n\nДля отмены набери /cancel",
        "step2_prompt": "⏰ *Шаг 2 из 3:* Введи точное время рождения в формате `ЧЧ:ММ` (24 часа)\n_(Например: `10:30` или `23:45`)_\n\nЕсли точное время неизвестно, укажи `12:00`.",
        "step3_prompt": "📍 *Шаг 3 из 3:* Введи город рождения\n_(Например: `Москва`, `Рим`, `Дели`, `Санкт-Петербург`)_:",
        "invalid_date_format": "⚠️ Неверный формат даты.\n\nВведи данные одной строкой:\n`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n_(например: `Александр, 15.05.1990, 10:30, Москва`)_\n\nИли укажи только дату в виде `ДД.ММ.ГГГГ` (например: `15.05.1990`):",
        "invalid_time_format": "⚠️ Неверный формат времени. Пожалуйста, укажи в виде `ЧЧ:ММ` (например: `10:30`):",

        # Profile Manager & Commands
        "mydata_empty": "У тебя пока нет сохранённой натальной карты.\nНажми кнопку ниже или /chart, чтобы составить её!",
        "mydata_card": "📋 *Сохранённые данные профиля «{name}»:*\n\n📅 Дата: `{dob}`\n⏰ Время: `{tob}`\n📍 Место: `{place}`\n🌐 Координаты: `{lat:.4f}, {lon:.4f}` (UTC{tz:+.1f})\n👥 Всего профилей в памяти: {count}\n\nЧтобы посмотреть карту или сменить профиль, используй кнопки ниже:",
        "reset_empty": "Данные сессии очищены. Профилей в базе не найдено. Чтобы создать карту, нажми /chart или кнопку ниже:",
        "reset_prompt": "⚠️ *Управление сбросом данных*\n\nВ базе данных сохранено профилей: *{count}*.\nЧто именно ты хочешь сделать?",
        "reset_cache_done": "🔄 Кэш текущей сессии очищен. Профили в базе данных сохранены!",
        "reset_all_done": "🗑 Все твои астрологические профили полностью удалены из базы данных.",
        "rename_prompt_usage": "Текущее имя активного профиля: *«{name}»*.\n\nЧтобы переименовать его, укажи новое имя:\n👉 `/rename Александр`",
        "rename_too_long": "Имя профиля не должно превышать 50 символов.",
        "rename_fail": "Не удалось переименовать профиль. Попробуй позже.",
        "profile_card_empty": "👤 *У тебя пока нет сохранённых профилей.*\n\nСоздай свой первый астрологический профиль с помощью команды /chart или кнопки ниже:",
        "chart_img_error": "❌ Не удалось сгенерировать изображение карты: {err}",

        # Compatibility
        "compat_missing_profile": "Для анализа совместимости сначала нужен твой сохранённый профиль!\nНажми /chart, чтобы составить свою карту, затем вернись в /compat.",
        "compat_select_second": "💞 *Анализ совместимости партнёров (Кута / Аштакута)*\n\nТвой активный профиль: *«{name}»* ({dob}, {place}).\n\nВыбери второго человека из сохранённых профилей или введи новые данные:",
        "compat_partner_not_found": "Профиль партнёра не найден. Попробуй снова: /compat",
        "compat_step1_new": "💞 *Анализ совместимости партнёров (Кута / Аштакута)*\n\nТвой профиль (*«{name}»*) уже сохранён.\nТеперь введи данные *партнёра*.\n\n📅 *Шаг 1 из 3:* Дата рождения партнёра `ДД.ММ.ГГГГ` (например: `20.08.1992`):\n\nДля отмены набери /cancel",
        "compat_partner_step1": "📅 *Шаг 1 из 3:* Введи дату рождения партнёра `ДД.ММ.ГГГГ` (например: `20.08.1992`):\n\nДля отмены набери /cancel",
        "compat_partner_step2": "⏰ *Шаг 2 из 3:* Время рождения партнёра `ЧЧ:ММ` (например: `14:15`):\n\nЕсли точное время неизвестно, укажи `12:00`.",
        "compat_partner_step3": "📍 *Шаг 3 из 3:* Город рождения партнёра (например: `Санкт-Петербург`):",
        "compat_invalid_dob": "⚠️ Неверный формат. Укажи дату партнёра как `ДД.ММ.ГГГГ` (например: `20.08.1992`):",
        "compat_invalid_tob": "⚠️ Неверный формат. Укажи время партнёра как `ЧЧ:ММ` (например: `14:15`):",
        "compat_session_expired": "Сессия истекла. Начни заново с /compat.",
        "compat_status_matching": "💞 Сопоставляю карты *{name1}* и *{name2}*...",
        "compat_partner_calc_status": "🌍 Вычисляю координаты и строю карту партнёра...",
        "compat_city_error": "❌ Не удалось найти город '{city}'.\nОшибка: {err}\n\nПожалуйста, укажи город партнёра ещё раз (или нажми /cancel):",
        "compat_chart_error": "❌ Ошибка расчёта карты партнёра: {err}",
        "compat_gemini_missing": "ℹ️ *Карты обоих партнёров загружены!*\n\n{kuja_text}\n\nДля детального анализа совместимости от ИИ добавь `GEMINI_API_KEY` в `.env`.",
        "compat_ai_matching_status": "💞 ИИ сопоставляет две карты по системе Аштакута...",
        "compat_analysis_header": "💘 *Анализ совместимости парных карт:*\n\n",
        "compat_analysis_error": "⚠️ Ошибка при анализе совместимости: {err}",

        # Payments & Services
        "payment_success_generic": "Спасибо за оплату! Твой премиум-статус активирован.",
        "payment_status_chart": "🔮 Составляю твой премиальный разбор натальной карты...",
        "payment_status_dasha": "⏳ Формирую подробный анализ планетных периодов...",
        "payment_status_compat": "💞 Сопоставляю две карты по системе Аштакута...",
        "payment_status_yoga": "🧘 ИИ-астролог трактует найденные йоги...",
        "payment_status_karma": "🔮 Составляю глубокий кармический разбор души...",
        "payment_status_money": "💼 Составляю финансовую стратегию...",
        "payment_yoga_ready": "🧘 Оплата принята! Набери /yoga для анализа йог.",
        "ai_unavailable": "⚠️ ИИ-астролог недоступен.",

        # Button labels
        "btn_show_chart": "📜 Показать карту",
        "btn_dasha_periods": "⏳ Периоды Даша",
        "btn_all_profiles": "👤 Все профили",
        "btn_prices": "⭐️ Тарифы",
        "btn_add_profile": "➕ Добавить профиль",
        "btn_edit_profile": "✏️ Изменить данные",
        "btn_delete_profile": "🗑 Удалить профиль",
        "btn_back_to_profiles": "🔙 Назад к профилям",
        "btn_manual_input": "✏️ Ввести новые данные вручную",
        "btn_new_profile": "➕ Новый профиль",
        "btn_clear_cache": "🔄 Очистить кэш сессии",
        "btn_delete_all_db": "🗑 Удалить ВСЕ профили из базы",
        "btn_profile_menu": "👤 Перейти в управление профилями",
        "btn_select_format": "👉 Выбрать «{name}»",
        "btn_active_format": "⭐️ {name} (выбран)",
        "btn_delete_format": "❌ Удалить «{name}»",
        "btn_clean_duplicates": "🧹 Очистить дубликаты",
        "duplicates_cleaned": "✅ Удалено устаревших дубликатов: {count}. Активный профиль: «{name}».",
        "duplicates_none": "ℹ️ Дубликатов не найдено. Все профили уникальны.",
    },

    "en": {
        "choose_language": (
            "🌐 *Select Interface Language:*\n\n"
            "Choose your preferred language for bot messages, chart calculations, and AI interpretations:\n"
            "• 🇷🇺 Русский\n"
            "• 🇬🇧 English\n"
            "• 🇮🇹 Italiano\n\n"
            "Or choose *Auto* to follow your Telegram application language."
        ),
        "lang_switched": "✅ Interface language successfully set to *English*! 🇬🇧\nAll chart calculations and AI readings will now be in English.",
        "lang_auto_switched": "🌐 Language set to *Auto* (following your Telegram language: *{selected_lang}*).",

        # Start
        "start_greeting": (
            "🙏 *Namaste! I am your AI Vedic Astrologer (Jyotishi).*\n\n"
            "I combine the authentic Parashara Muni Vedic tradition "
            "with NASA JPL high-precision ephemerides and Google Gemini AI.\n\n"
            "✨ *Features:*\n"
            "🪐 Accurate Kundli birth chart (D1, Lagna, houses, planets, Shadbala)\n"
            "⏳ Lifetime destiny periods (*Vimshottari Dasha*)\n"
            "💞 Partnership compatibility (*Ashtakoota / 8 Love Factors*)\n"
            "❓ Ask any personal question to the AI Astrologer\n"
            "🔄 Sade-Sati calculator (Saturn's 7.5-year transit)\n"
            "🧘 Vedic Yoga detector (Raja, Dhana, Mahapurusha)\n"
            "👥 Multi-profile support (yourself, partner, family)\n\n"
            "📌 *Bot Commands:*\n"
            "👉 /chart — calculate natal chart\n"
            "👉 /profile — profile manager (switch, add, delete)\n"
            "👉 /newprofile — add a new profile\n"
            "👉 /dasha — life periods (Vimshottari Dasha)\n"
            "👉 /compat — relationship compatibility\n"
            "👉 /ask — ask a question to AI Astrologer\n"
            "👉 /sadesati — check Sade-Sati transit\n"
            "👉 /yoga — detect planetary yogas\n"
            "👉 /karma — soul karmic task (Atmakaraka)\n"
            "👉 /money — wealth code & career strategy\n"
            "👉 /upaya — Vedic remedies & harmonization\n"
            "👉 /prices — pricing in Telegram Stars (⭐️)\n"
            "👉 /lang — change language (EN/IT/RU)\n"
            "👉 /mydata — view active profile data\n"
            "👉 /reset — reset saved data\n"
            "👉 /help — user guide\n\n"
        ),
        "start_active_profile": (
            "👤 *Active Profile:* «{name}»\n"
            "📅 Date: `{dt}` | 📍 `{place}`\n\n"
            "Your chart is ready! You can explore the features below or manage profiles via /profile.\n"
            "👇 *Choose an action below:*"
        ),
        "start_no_profile": "👇 *Select an option below or tap /chart to get started:*",

        # Help
        "help_text": (
            "📖 *Jyotish Bot User Guide:*\n\n"
            "🔹 /chart — Calculate natal chart (date, time, birthplace).\n"
            "🔹 /profile — Profile manager (switch active, view, delete).\n"
            "🔹 /newprofile — Create an additional profile (partner, relatives).\n"
            "🔹 /karma — Soul's karmic task & Jaimini Chara Karakas (Atmakaraka).\n"
            "🔹 /money — Wealth houses, financial code & career strategy.\n"
            "🔹 /upaya — Personalized Vedic Upayas (remedial practices).\n"
            "🔹 /dasha — Vimshottari Dasha planetary life periods.\n"
            "🔹 /compat — Ashtakoota synastry (36 Gunas & Kuja Dosha).\n"
            "🔹 /ask — Ask any question to the AI Astrologer based on your chart.\n"
            "🔹 /sadesati — Check active Saturn Sade-Sati transit.\n"
            "🔹 /yoga — Discover auspicious yogas and combinations.\n"
            "🔹 /prices — Pricing in ⭐️ Telegram Stars.\n"
            "🔹 /lang — Interface language (Russian, English, Italian).\n"
            "🔹 /mydata — Show active profile birth details.\n"
            "🔹 /reset — Clear saved profile data.\n"
            "🔹 /cancel — Cancel current input.\n\n"
            "💡 *Payment:* Basic calculations are free. Deep AI interpretations are powered by ⭐️ Telegram Stars."
        ),

        # Prices
        "prices_header": "⭐️ *AI Interpretations Price List (Telegram Stars):*\n\n",
        "prices_body": (
            "🔮 **Full Natal Chart Reading:** `{chart} ⭐️`\n"
            "  • Personality, Lagna, soul mission, career, wealth, relations, upayas.\n\n"
            "🔮 **Soul Karmic Task (Atmakaraka):** `{karma} ⭐️`\n"
            "  • Jaimini 7 Karakas, main life lessons, destiny direction.\n\n"
            "💰 **Wealth Code & Career:** `{money} ⭐️`\n"
            "  • 2nd & 11th houses, Dhana yogas, and career scaling strategy.\n\n"
            "⏳ **Vimshottari Dasha Analysis:** `{dasha} ⭐️`\n"
            "  • Active Maha-Dasha & Antar-Dasha, growth points, warnings & upayas.\n\n"
            "💞 **Compatibility Analysis (Ashtakoota):** `{compat} ⭐️`\n"
            "  • 8 harmony factors, attraction, mental sync, karmic bonds.\n\n"
            "❓ **Express AI Question:** `{ask} ⭐️`\n"
            "  • Ask any specific question and receive a personalized chart analysis.\n\n"
            "🧘 **Yoga Detector + AI Interpretation:** `{yoga} ⭐️`\n"
            "  • Raja Yoga, Gaja Kesari, Budhaditya, Dhana, Pancha Mahapurusha.\n\n"
            "🌟 **All-in-One 360° Bundle:** `{bundle} ⭐️`\n"
            "  • Natal Chart + Dasha + Yogas + 1 Question — discounted package!\n\n"
            "🆓 *Free:* basic calculations, /sadesati, /upaya, 1st question to AI.\n\n"
            "✨ Secure 1-click payments via Telegram Stars (Apple Pay / Google Pay / Card)."
        ),

        # Profiles
        "profile_card_header": "🔮 *Active Profile: «{name}»*\n\n📅 Date: `{dob}`\n⏰ Time: `{tob}`\n📍 Place: `{place}`\n🌐 Coordinates: `{lat:.4f}, {lon:.4f}` (UTC{tz:+.1f})\n\nNatal chart is already saved! Choose an action:",
        "no_profile_found": "You do not have any saved astrological profiles yet.\nTap /chart to create your first natal chart!",
        "profile_list_header": "👤 *Your Saved Profiles:*\n(Total: {count})\n\n",
        "profile_active_badge": "⭐️ *ACTIVE:*",
        "profile_other_badge": "•",
        "profile_action_prompt": "\nSelect a profile to switch or use the buttons below:",
        "profile_switched_success": "✅ Active profile switched to *«{name}»*!\n\nAll calculations (/chart, /dasha, /sadesati, /yoga, /ask) are now active for this person.",
        "profile_switch_fail": "Failed to switch profile. Please open /profile.",
        "profile_delete_menu": "🗑 *Select a profile to delete:*\n_Note: Deletion is permanent._",
        "profile_delete_success": "🗑 Profile *«{name}»* has been deleted.",
        "profile_delete_fail": "Failed to delete profile.",
        "profile_no_profiles_to_delete": "You have no profiles to delete.",
        "rename_prompt": "✏️ Enter command as:\n`/rename New_Name`",
        "rename_success": "✅ Profile renamed to *«{name}»*!",
        "profile_updated_header": "✅ *Profile '{name}' successfully updated and recalculated!*\n\n",
        "reset_success": "🗑 All your saved profiles and data have been cleared.\nTo start fresh, tap /chart.",

        # Chart Dialog
        "ask_profile_name": "👤 Enter a name for this profile (e.g. *Alexander*, *Anna*, *Son Michael*):",
        "ask_dob": (
            "📅 *Step 1 of 3:* Enter your **Date of Birth** in DD.MM.YYYY format\n"
            "Example: `15.05.1990` or `24.12.1985`\n\n"
            "💡 *Tip:* You can also enter all details in one line:\n"
            "`Alexander, 15.05.1990, 10:30, London`"
        ),
        "invalid_dob": "❌ Invalid date format! Please enter date as DD.MM.YYYY (e.g. `15.05.1990`):",
        "ask_tob": (
            "⏰ *Step 2 of 3:* Enter your **Time of Birth** (local time) in HH:MM format\n"
            "Example: `10:30`, `18:45`, `04:15`\n\n"
            "_If birth time is unknown, enter `12:00` (noon)._"
        ),
        "invalid_tob": "❌ Invalid time format! Please enter time as HH:MM (e.g. `10:30`):",
        "ask_place": (
            "📍 *Step 3 of 3:* Enter your **Birth City** (and country for smaller towns)\n"
            "Example: `London`, `Rome, Italy`, `New York`, `Berlin`"
        ),
        "place_resolving": "🔍 Finding coordinates for *«{place}»*...",
        "place_not_found": "❌ Could not find city *«{place}»*. Please try a larger nearby city or specify the country:",
        "chart_calculating": "🌌 Computing planets, Lagna, nakshatras, and Dasha periods via NASA JPL ephemerides...",
        "chart_ready_header": "🔮 *Vedic Kundli Chart (D1): {name}*",
        "chart_summary_caption": "👤 *Natal Chart for «{name}»*\n\n",
        "chart_one_line_success": "✅ Details recognized: *{name}*, `{dob}`, `{tob}`, `{place}`.",

        # Dasha
        "dasha_header": "🕐 *Vimshottari Dasha — Life Periods:*\n\n",
        "dasha_balance": "⚖️ Birth Balance: {planet} — {years:.2f} years\n\n",
        "dasha_current_badge": " ◀️ *CURRENT*",
        "dasha_need_chart": "Please calculate your natal chart first using /chart.",

        # Compatibility
        "compat_choose_first": "💞 *Relationship Compatibility (Ashtakoota)*\n\nActive profile: *«{name}»*.\nSelect a second partner from your profiles or enter new details:",
        "compat_ask_second_name": "👤 Enter partner's name for compatibility check:",
        "compat_result_header": "💞 *Vedic Compatibility Result (Ashtakoota — 36 Gunas)*\n\n",
        "compat_score": "🏆 **Overall Compatibility Score:** `{score} of 36`\n",
        "compat_verdict_excellent": "🌟 **Excellent Compatibility!** Highly harmonious union for marriage and life.",
        "compat_verdict_good": "✨ **Good Compatibility.** Favorable union with high mutual understanding.",
        "compat_verdict_average": "⚖️ **Average Compatibility.** Relationship requires compromise and patience.",
        "compat_verdict_difficult": "⚠️ **Challenging Compatibility.** Differences may arise; deep synastry review recommended.",

        # Sade-Sati
        "sadesati_active": "🪐 *Sade-Sati Period:* ⚠️ **ACTIVE**\nPhase: *{phase}*\nActive timeframe: `{start}` — `{end}`\n\nSaturn is transiting your natal Moon. A period of profound transformation, discipline, and maturity.",
        "sadesati_inactive": "🪐 *Sade-Sati Period:* ✅ **INACTIVE**\nNext Saturn transit begins: `{next_start}`.\n\nCurrent period is free from direct Sade-Sati pressure.",

        # Yoga Detector
        "yogas_found_header": "🧘 *Detected Vedic Yogas (Planetary Combinations):*\n\n",
        "no_yogas_found": "No major first-tier classical planetary yogas found in the current configuration.",

        # Ask AI
        "ask_intro": "💬 *Ask Any Question to AI Astrologer*\n\nAsk about your purpose, career, relationships, timing, or life challenges. The answer is calculated specifically from your chart.\n\n👇 Send your question in your next message:",
        "ask_free_available": "🎁 Your first question to AI is *completely free*!",
        "ask_thinking": "🔮 AI Jyotishi is analyzing your birth chart and planetary periods... Please wait a few seconds.",

        # Cancel & Fallback
        "cancelled": "❌ Action cancelled.",
        "fallback_unknown": "I didn't quite catch that. Type /help for assistance or choose an option from the menu below.",

        # General UI & Dialogs
        "choose_next_action": "Choose your next action:",
        "need_chart_first": "Please calculate your natal chart first!\nTap /chart or the button below:",
        "session_error": "Session error occurred. Please start again with /chart.",
        "chart_error": "❌ Error calculating chart: {err}",
        "default_profile_name": "My Horoscope",
        "profile_indexed_name": "Profile {index}",
        "resolving_city": "🌍 Resolving city coordinates and timezone...",
        "computing_chart": "🧮 Calculating planetary positions and houses via NASA JPL ephemerides...",
        "city_not_found": "❌ Could not find city '{city}'.\nError: {err}\n\nPlease enter the city again (or type /cancel):",
        "name_saved_prompt": "👤 Saved name: *{name}*!\n\nNow enter date of birth (`DD.MM.YYYY`), e.g. `20.06.1996`\nor send the remaining details in one line (`DD.MM.YYYY, HH:MM, City`):",
        "invalid_name_prompt": "Please provide a valid name (up to 50 characters):",
        "newprofile_intro": "👤 *Create New Astrological Profile*\n\nEnter details in one line:\n`Name, DD.MM.YYYY, HH:MM, City`\n_(e.g. `Anna, 20.08.1992, 14:15, London`)_\n\nOr enter only profile name _(e.g. `Wife`, `Anna`)_ for step-by-step entry.\n\nTo cancel, type /cancel",
        "chart_intro": "🔮 *Create Natal Chart*\n\nEnter details in one line:\n`Name, DD.MM.YYYY, HH:MM, City`\n_(e.g. `Alexander, 15.05.1990, 10:30, London`)_\n\nOr start with date of birth (`DD.MM.YYYY`) for step-by-step entry.\n\nTo cancel, type /cancel",
        "recalc_intro": "🔄 *Recalculate Profile '{name}'*\n\nEnter new details in one line:\n`DD.MM.YYYY, HH:MM, City` (e.g. `15.05.1990, 10:30, London`)\n\nOr start with date of birth (`DD.MM.YYYY`):\n\nTo cancel, type /cancel",
        "step2_prompt": "⏰ *Step 2 of 3:* Enter exact time of birth in `HH:MM` format (24-hour)\n_(e.g. `10:30` or `23:45`)_\n\nIf exact time is unknown, enter `12:00`.",
        "step3_prompt": "📍 *Step 3 of 3:* Enter birth city\n_(e.g. `London`, `Rome`, `Delhi`, `New York`)_:",
        "invalid_date_format": "⚠️ Invalid date format.\n\nEnter details in one line:\n`Name, DD.MM.YYYY, HH:MM, City`\n_(e.g. `Alexander, 15.05.1990, 10:30, London`)_\n\nOr enter date only as `DD.MM.YYYY` (e.g. `15.05.1990`):",
        "invalid_time_format": "⚠️ Invalid time format. Please enter as `HH:MM` (e.g. `10:30`):",

        # Profile Manager & Commands
        "mydata_empty": "You do not have a saved natal chart yet.\nTap a button below or /chart to create one!",
        "mydata_card": "📋 *Saved Details for Profile '{name}':*\n\n📅 Date: `{dob}`\n⏰ Time: `{tob}`\n📍 Place: `{place}`\n🌐 Coordinates: `{lat:.4f}, {lon:.4f}` (UTC{tz:+.1f})\n👥 Total saved profiles: {count}\n\nTo view chart or switch profile, use the buttons below:",
        "reset_empty": "Session data cleared. No profiles found in database. To create a chart, tap /chart or the button below:",
        "reset_prompt": "⚠️ *Data Reset Manager*\n\nSaved profiles in database: *{count}*.\nWhat would you like to do?",
        "reset_cache_done": "🔄 Session cache cleared. Profiles in database preserved!",
        "reset_all_done": "🗑 All your astrological profiles have been deleted from the database.",
        "rename_prompt_usage": "Current active profile name: *'{name}'*.\n\nTo rename it, specify the new name:\n👉 `/rename Alexander`",
        "rename_too_long": "Profile name must not exceed 50 characters.",
        "rename_fail": "Failed to rename profile. Please try again later.",
        "profile_card_empty": "👤 *You have no saved profiles yet.*\n\nCreate your first astrological profile with /chart or the button below:",
        "chart_img_error": "❌ Failed to render chart image: {err}",

        # Compatibility
        "compat_missing_profile": "To analyze compatibility, you need a saved birth profile first!\nTap /chart to calculate your chart, then return to /compat.",
        "compat_select_second": "💞 *Relationship Compatibility Analysis (Ashtakoota)*\n\nYour active profile: *«{name}»* ({dob}, {place}).\n\nSelect a partner from saved profiles or enter new details:",
        "compat_partner_not_found": "Partner profile not found. Try again: /compat",
        "compat_step1_new": "💞 *Relationship Compatibility Analysis (Ashtakoota)*\n\nYour profile (*'{name}'*) is saved.\nNow enter *partner's* birth details.\n\n📅 *Step 1 of 3:* Partner's date of birth `DD.MM.YYYY` (e.g. `20.08.1992`):\n\nTo cancel, type /cancel",
        "compat_partner_step1": "📅 *Step 1 of 3:* Enter partner's date of birth `DD.MM.YYYY` (e.g. `20.08.1992`):\n\nTo cancel, type /cancel",
        "compat_partner_step2": "⏰ *Step 2 of 3:* Partner's time of birth `HH:MM` (e.g. `14:15`):\n\nIf exact time is unknown, enter `12:00`.",
        "compat_partner_step3": "📍 *Step 3 of 3:* Partner's birth city (e.g. `London`, `Rome`):",
        "compat_invalid_dob": "⚠️ Invalid format. Enter partner's date as `DD.MM.YYYY` (e.g. `20.08.1992`):",
        "compat_invalid_tob": "⚠️ Invalid format. Enter partner's time as `HH:MM` (e.g. `14:15`):",
        "compat_session_expired": "Session expired. Start again with /compat.",
        "compat_status_matching": "💞 Matching charts of *{name1}* and *{name2}*...",
        "compat_partner_calc_status": "🌍 Resolving coordinates and creating partner's chart...",
        "compat_city_error": "❌ Could not find city '{city}'.\nError: {err}\n\nPlease enter partner's city again (or type /cancel):",
        "compat_chart_error": "❌ Error calculating partner's chart: {err}",
        "compat_gemini_missing": "ℹ️ *Both partner charts loaded!*\n\n{kuja_text}\n\nTo enable detailed AI compatibility analysis, add `GEMINI_API_KEY` to `.env`.",
        "compat_ai_matching_status": "💞 AI is analyzing synastry across Ashtakoota system...",
        "compat_analysis_header": "💘 *Synastry & Compatibility Analysis:*\n\n",
        "compat_analysis_error": "⚠️ Error during compatibility analysis: {err}",

        # Payments & Services
        "payment_success_generic": "Thank you for your payment! Your premium reading is activated.",
        "payment_status_chart": "🔮 Generating your premium natal chart reading...",
        "payment_status_dasha": "⏳ Generating in-depth planetary periods analysis...",
        "payment_status_compat": "💞 Analyzing synastry between the two charts...",
        "payment_status_yoga": "🧘 AI Astrologer is interpreting detected yogas...",
        "payment_status_karma": "🔮 Generating deep soul karmic analysis...",
        "payment_status_money": "💼 Generating financial strategy & wealth code...",
        "payment_yoga_ready": "🧘 Payment received! Tap /yoga to analyze yogas.",
        "ai_unavailable": "⚠️ AI Astrologer is currently unavailable.",

        # Button labels
        "btn_show_chart": "📜 Show Chart",
        "btn_dasha_periods": "⏳ Dasha Periods",
        "btn_all_profiles": "👤 All Profiles",
        "btn_prices": "⭐️ Prices",
        "btn_add_profile": "➕ Add Profile",
        "btn_edit_profile": "✏️ Edit Details",
        "btn_delete_profile": "🗑 Delete Profile",
        "btn_back_to_profiles": "🔙 Back to Profiles",
        "btn_manual_input": "✏️ Enter details manually",
        "btn_new_profile": "➕ New Profile",
        "btn_clear_cache": "🔄 Clear Session Cache",
        "btn_delete_all_db": "🗑 Delete ALL Profiles from DB",
        "btn_profile_menu": "👤 Go to Profile Manager",
        "btn_select_format": "👉 Select '{name}'",
        "btn_active_format": "⭐️ {name} (selected)",
        "btn_delete_format": "❌ Delete '{name}'",
        "btn_clean_duplicates": "🧹 Clean Duplicates",
        "duplicates_cleaned": "✅ Removed {count} duplicate profiles. Active profile: '{name}'.",
        "duplicates_none": "ℹ️ No duplicate profiles found. All profiles are unique.",
    },

    "it": {
        "choose_language": (
            "🌐 *Selezione Lingua dell'Interfaccia:*\n\n"
            "Scegli la lingua preferita per le risposte del bot, i calcoli astrologici e le letture IA:\n"
            "• 🇷🇺 Русский\n"
            "• 🇬🇧 English\n"
            "• 🇮🇹 Italiano\n\n"
            "Oppure seleziona *Auto* per seguire la lingua impostata nella tua app Telegram."
        ),
        "lang_switched": "✅ Lingua dell'interfaccia impostata su *Italiano*! 🇮🇹\nTutti i calcoli e le interpretazioni IA saranno ora in lingua italiana.",
        "lang_auto_switched": "🌐 Lingua impostata su *Auto* (seguendo la lingua di Telegram: *{selected_lang}*).",

        # Start
        "start_greeting": (
            "🙏 *Namasté! Sono il tuo Astrologo Vedico IA (Jyotishi).*\n\n"
            "Unisco l'autentica tradizione vedica di Parashara Muni "
            "alle effemeridi spaziali ad alta precisione NASA JPL e all'intelligenza artificiale Google Gemini.\n\n"
            "✨ *Funzionalità:*\n"
            "🪐 Carta natale Kundli precisa (D1, Ascendente, case, pianeti, Shadbala)\n"
            "⏳ Periodi planetari della vita (*Vimshottari Dasha*)\n"
            "💞 Compatibilità di coppia (*Ashtakoota / 8 Fattori d'Amore*)\n"
            "❓ Domande libere all'Astrologo IA basate sul tuo tema natale\n"
            "🔄 Calcolatore del transito di Saturno (*Sade-Sati*)\n"
            "🧘 Rilevatore di Yoga vedici benefici (Raja, Dhana, Mahapurusha)\n"
            "👥 Gestione profili multipli (te stesso, partner, famiglia)\n\n"
            "📌 *Comandi del Bot:*\n"
            "👉 /chart — calcola la carta natale\n"
            "👉 /profile — gestione profili (cambia, aggiungi, elimina)\n"
            "👉 /newprofile — aggiungi un nuovo profilo\n"
            "👉 /dasha — periodi di vita (Vimshottari Dasha)\n"
            "👉 /compat — compatibilità di coppia\n"
            "👉 /ask — fai una domanda all'Astrologo IA\n"
            "👉 /sadesati — verifica transito Sade-Sati\n"
            "👉 /yoga — rileva gli yoga planetari\n"
            "👉 /karma — compito karmico dell'anima (Atmakaraka)\n"
            "👉 /money — codice finanziario e carriera\n"
            "👉 /upaya — rimedi vedici e armonizzazione\n"
            "👉 /prices — tariffe in Stelle Telegram (⭐️)\n"
            "👉 /lang — cambia lingua (IT/EN/RU)\n"
            "👉 /mydata — visualizza i dati del profilo attivo\n"
            "👉 /reset — resetta i dati salvati\n"
            "👉 /help — guida utente\n\n"
        ),
        "start_active_profile": (
            "👤 *Profilo Attivo:* «{name}»\n"
            "📅 Data: `{dt}` | 📍 `{place}`\n\n"
            "La tua carta è pronta! Puoi esplorare le sezioni qui sotto o gestire i profili con /profile.\n"
            "👇 *Scegli un'azione qui sotto:*"
        ),
        "start_no_profile": "👇 *Scegli un'opzione qui sotto o premi /chart per iniziare:*",

        # Help
        "help_text": (
            "📖 *Guida di Jyotish Bot:*\n\n"
            "🔹 /chart — Calcolo tema natale (data, ora, luogo di nascita).\n"
            "🔹 /profile — Gestione profili (selezione attivo, visualizzazione, eliminazione).\n"
            "🔹 /newprofile — Crea un nuovo profilo (partner, parenti).\n"
            "🔹 /karma — Compito karmico dell'anima e Chara Karaka di Jaimini (Atmakaraka).\n"
            "🔹 /money — Case della ricchezza, finanze e carriera.\n"
            "🔹 /upaya — Rimedi vedici personalizzati (Upaya).\n"
            "🔹 /dasha — Periodi planetari di vita Vimshottari Dasha.\n"
            "🔹 /compat — Sinastria di coppia Ashtakoota (36 Guna e Kuja Dosha).\n"
            "🔹 /ask — Fai qualsiasi domanda all'Astrologo IA basata sul tuo tema natale.\n"
            "🔹 /sadesati — Calcolo del transito di Saturno Sade-Sati.\n"
            "🔹 /yoga — Rilevamento di potenti combinazioni planetarie (Yoga).\n"
            "🔹 /prices — Tariffe in ⭐️ Stelle Telegram.\n"
            "🔹 /lang — Lingua dell'interfaccia (Italiano, English, Russo).\n"
            "🔹 /mydata — Mostra data, ora e luogo del profilo attivo.\n"
            "🔹 /reset — Elimina tutti i profili salvati.\n"
            "🔹 /cancel — Annulla l'operazione corrente.\n\n"
            "💡 *Pagamenti:* I calcoli base sono gratuiti. Le analisi approfondite sono fornite tramite ⭐️ Stelle Telegram."
        ),

        # Prices
        "prices_header": "⭐️ *Listino Interpretazioni IA (Stelle Telegram):*\n\n",
        "prices_body": (
            "🔮 **Analisi Completa del Tema Natale:** `{chart} ⭐️`\n"
            "  • Personalità, Ascendente, missione dell'anima, carriera, finanze, relazioni, upaya.\n\n"
            "🔮 **Compito Karmico dell'Anima (Atmakaraka):** `{karma} ⭐️`\n"
            "  • Calcolo di 7 Karaka di Jaimini, lezioni karmiche e direzione del destino.\n\n"
            "💰 **Codice Finanziario e Carriera:** `{money} ⭐️`\n"
            "  • Analisi della 2ª e 11ª casa, Dhana Yoga e strategia di guadagno.\n\n"
            "⏳ **Analisi dei Periodi Vimshottari Dasha:** `{dasha} ⭐️`\n"
            "  • Maha-Dasha e Antar-Dasha attive, punti di forza, avvertimenti e upaya.\n\n"
            "💞 **Compatibilità di Coppia (Ashtakoota):** `{compat} ⭐️`\n"
            "  • 8 fattori di armonia, attrazione fisica, affinità mentale, nodi karmici.\n\n"
            "❓ **Domanda Espressa all'Astrologo IA:** `{ask} ⭐️`\n"
            "  • Poni qualsiasi domanda e ricevi una risposta personalizzata sul tuo tema natale.\n\n"
            "🧘 **Rilevatore Yoga + Analisi IA:** `{yoga} ⭐️`\n"
            "  • Raja Yoga, Gaja Kesari, Budhaditya, Dhana, Pancha Mahapurusha.\n\n"
            "🌟 **Pacchetto Completo 360°:** `{bundle} ⭐️`\n"
            "  • Tema Natale + Dasha + Yoga + 1 Domanda — tutto incluso a prezzo scontato!\n\n"
            "🆓 *Gratis:* calcoli base, /sadesati, /upaya, 1ª domanda all'IA.\n\n"
            "✨ Pagamenti sicuri in 1 clic con Stelle Telegram (Apple Pay / Google Pay / Carte)."
        ),

        # Profiles
        "profile_card_header": "🔮 *Profilo Attivo: «{name}»*\n\n📅 Data: `{dob}`\n⏰ Ora: `{tob}`\n📍 Luogo: `{place}`\n🌐 Coordinate: `{lat:.4f}, {lon:.4f}` (UTC{tz:+.1f})\n\nIl tema natale per questo profilo è già salvato! Scegli un'azione:",
        "no_profile_found": "Non hai ancora nessun profilo astrologico salvato.\nPremi /chart per creare la tua prima carta natale!",
        "profile_list_header": "👤 *I Tuoi Profili Salvati:*\n(Totale: {count})\n\n",
        "profile_active_badge": "⭐️ *ATTIVO:*",
        "profile_other_badge": "•",
        "profile_action_prompt": "\nSeleziona un profilo per attivarlo o usa i pulsanti sotto:",
        "profile_switched_success": "✅ Profilo attivo cambiato in *«{name}»*!\n\nTutti i calcoli (/chart, /dasha, /sadesati, /yoga, /ask) ora fanno riferimento a questa persona.",
        "profile_switch_fail": "Impossibile cambiare profilo. Apri /profile.",
        "profile_delete_menu": "🗑 *Seleziona il profilo da eliminare:*\n_Attenzione: l'operazione è irreversibile._",
        "profile_delete_success": "🗑 Profilo *«{name}»* eliminato con successo.",
        "profile_delete_fail": "Impossibile eliminare il profilo.",
        "profile_no_profiles_to_delete": "Non hai profili da eliminare.",
        "rename_prompt": "✏️ Invia il comando nel formato:\n`/rename Nuovo_Nome`",
        "rename_success": "✅ Profilo rinominato con successo in *«{name}»*!",
        "profile_updated_header": "✅ *Profilo '{name}' aggiornato e ricalcolato con successo!*\n\n",
        "reset_success": "🗑 Tutti i tuoi profili e dati salvati sono stati eliminati.\nPer ricominciare da capo, premi /chart.",

        # Chart Dialog
        "ask_profile_name": "👤 Inserisci un nome per questo profilo (es. *Marco*, *Giulia*, *Figlio Matteo*):",
        "ask_dob": (
            "📅 *Passo 1 di 3:* Inserisci la **data di nascita** nel formato GG.MM.AAAA\n"
            "Esempio: `15.05.1990` oppure `24.12.1985`\n\n"
            "💡 *Scorciatoia:* Puoi inserire tutti i dati su una sola riga:\n"
            "`Marco, 15.05.1990, 10:30, Roma`"
        ),
        "invalid_dob": "❌ Formato data non valido! Inserisci la data come GG.MM.AAAA (es. `15.05.1990`):",
        "ask_tob": (
            "⏰ *Passo 2 di 3:* Inserisci l'**ora di nascita** (ora locale) nel formato HH:MM\n"
            "Esempio: `10:30`, `18:45`, `04:15`\n\n"
            "_Se l'ora esatta non è nota, inserisci `12:00` (mezzogiorno)._"
        ),
        "invalid_tob": "❌ Formato ora non valido! Inserisci l'ora come HH:MM (es. `10:30`):",
        "ask_place": (
            "📍 *Passo 3 di 3:* Inserisci la **città di nascita** (e il paese per città minori)\n"
            "Esempio: `Roma`, `Milano, Italia`, `Napoli`, `Londra`"
        ),
        "place_resolving": "🔍 Ricerca coordinate per *«{place}»*...",
        "place_not_found": "❌ Città *«{place}»* non trovata. Prova con una città vicina più grande o specifica la nazione:",
        "chart_calculating": "🌌 Calcolo posizioni planetarie, Ascendente, nakshatra e periodi Dasha tramite effemeridi NASA JPL...",
        "chart_ready_header": "🔮 *Carta Vedica Kundli (D1): {name}*",
        "chart_summary_caption": "👤 *Tema Natale del profilo «{name}»*\n\n",
        "chart_one_line_success": "✅ Dati riconosciuti: *{name}*, `{dob}`, `{tob}`, `{place}`.",

        # Dasha
        "dasha_header": "🕐 *Vimshottari Dasha — Periodi di Vita:*\n\n",
        "dasha_balance": "⚖️ Bilancio alla nascita: {planet} — {years:.2f} anni\n\n",
        "dasha_current_badge": " ◀️ *ATTUALE*",
        "dasha_need_chart": "Prima calcola il tuo tema natale tramite /chart.",

        # Compatibility
        "compat_choose_first": "💞 *Analisi di Compatibilità di Coppia (Ashtakoota)*\n\nProfilo attivo: *«{name}»*.\nSeleziona il secondo partner dall'elenco o creane uno nuovo:",
        "compat_ask_second_name": "👤 Inserisci il nome del partner per verificare la compatibilità:",
        "compat_result_header": "💞 *Risultato Compatibilità Vedica (Ashtakoota — 36 Guna)*\n\n",
        "compat_score": "🏆 **Punteggio Totale di Compatibilità:** `{score} su 36`\n",
        "compat_verdict_excellent": "🌟 **Compatibilità Eccellente!** Unione armoniosa per matrimonio e vita insieme.",
        "compat_verdict_good": "✨ **Buona Compatibilità.** Unione favorevole con profonda comprensione reciproca.",
        "compat_verdict_average": "⚖️ **Compatibilità Media.** Il rapporto richiede compromessi e pazienza.",
        "compat_verdict_difficult": "⚠️ **Compatibilità Impegnativa.** Possibili divergenze; si raccomanda una sinastria approfondita.",

        # Sade-Sati
        "sadesati_active": "🪐 *Periodo Sade-Sati:* ⚠️ **ATTIVO**\nFase: *{phase}*\nPeriodo di validità: `{start}` — `{end}`\n\nSaturno è in transito sulla Luna natale. Un periodo di profonda trasformazione, disciplina e maturazione.",
        "sadesati_inactive": "🪐 *Periodo Sade-Sati:* ✅ **NON ATTIVO**\nIl prossimo transito inizierà il: `{next_start}`.\n\nIl periodo attuale è libero dall'influenza diretta di Sade-Sati.",

        # Yoga Detector
        "yogas_found_header": "🧘 *Yoga Vedici Rilevati (Combinazioni Planetarie):*\n\n",
        "no_yogas_found": "Nessun grande yoga classico di primo livello rilevato nella configurazione attuale.",

        # Ask AI
        "ask_intro": "💬 *Fai qualsiasi domanda all'Astrologo IA*\n\nChiedi riguardo alla tua missione, carriera, relazioni, tempistiche o salute. La risposta sarà generata su misura per il tuo tema natale.\n\n👇 Invia la tua domanda nel prossimo messaggio:",
        "ask_free_available": "🎁 La tua prima domanda all'IA è *completamente gratuita*!",
        "ask_thinking": "🔮 L'Astrologo IA sta analizzando il tuo tema natale e i periodi planetari... Attendi qualche secondo.",

        # Cancel & Fallback
        "cancelled": "❌ Operazione annullata.",
        "fallback_unknown": "Comando non compreso. Digita /help per la guida o usa i pulsanti del menu qui sotto.",

        # General UI & Dialogs
        "choose_next_action": "Scegli la prossima azione:",
        "need_chart_first": "Prima è necessario calcolare la carta natale!\nPremi /chart o il pulsante qui sotto:",
        "session_error": "Errore di sessione. Ricomincia con /chart.",
        "chart_error": "❌ Errore durante il calcolo della carta: {err}",
        "default_profile_name": "Mio Oroscopo",
        "profile_indexed_name": "Profilo {index}",
        "resolving_city": "🌍 Rilevamento coordinate e fuso orario della città...",
        "computing_chart": "🧮 Calcolo delle posizioni planetarie e delle case con le effemeridi NASA JPL...",
        "city_not_found": "❌ Impossibile trovare la città '{city}'.\nErrore: {err}\n\nPer favore, inserisci nuovamente la città (o digita /cancel):",
        "name_saved_prompt": "👤 Nome memorizzato: *{name}*!\n\nOra inserisci la data di nascita (`GG.MM.AAAA`), es. `20.06.1996`\noppure invia i dati rimanenti su una riga (`GG.MM.AAAA, HH:MM, Città`):",
        "invalid_name_prompt": "Per favore, fornisci un nome valido (fino a 50 caratteri):",
        "newprofile_intro": "👤 *Creazione Nuovo Profilo Astrologico*\n\nInserisci i dati su una riga:\n`Nome, GG.MM.AAAA, HH:MM, Città`\n_(es. `Anna, 20.08.1992, 14:15, Roma`)_\n\nOppure inserisci solo il nome _(es. `Moglie`, `Anna`)_ per l'inserimento guidato.\n\nPer annullare, digita /cancel",
        "chart_intro": "🔮 *Creazione Carta Natale*\n\nInserisci i dati su una sola riga:\n`Nome, GG.MM.AAAA, HH:MM, Città`\n_(es. `Marco, 15.05.1990, 10:30, Roma`)_\n\nOppure inizia dalla data di nascita (`GG.MM.AAAA`) per l'inserimento guidato.\n\nPer annullare, digita /cancel",
        "recalc_intro": "🔄 *Ricalcolo Profilo '{name}'*\n\nInserisci i nuovi dati su una riga:\n`GG.MM.AAAA, HH:MM, Città` (es. `15.05.1990, 10:30, Roma`)\n\nOppure inizia dalla data di nascita (`GG.MM.AAAA`):\n\nPer annullare, digita /cancel",
        "step2_prompt": "⏰ *Passo 2 di 3:* Inserisci l'ora esatta di nascita in formato `HH:MM` (24 ore)\n_(es. `10:30` o `23:45`)_\n\nSe l'ora esatta non è nota, inserisci `12:00`.",
        "step3_prompt": "📍 *Passo 3 di 3:* Inserisci la città di nascita\n_(es. `Roma`, `Milano`, `Napoli`, `Londra`)_:",
        "invalid_date_format": "⚠️ Formato data non valido.\n\nInserisci i dati su una riga:\n`Nome, GG.MM.AAAA, HH:MM, Città`\n_(es. `Marco, 15.05.1990, 10:30, Roma`)_\n\nOppure inserisci solo la data come `GG.MM.AAAA` (es. `15.05.1990`):",
        "invalid_time_format": "⚠️ Formato ora non valido. Inserisci come `HH:MM` (es. `10:30`):",

        # Profile Manager & Commands
        "mydata_empty": "Non hai ancora una carta natale salvata.\nPremi un pulsante sotto o /chart per crearne una!",
        "mydata_card": "📋 *Dati Salvati del Profilo '{name}':*\n\n📅 Data: `{dob}`\n⏰ Ora: `{tob}`\n📍 Luogo: `{place}`\n🌐 Coordinate: `{lat:.4f}, {lon:.4f}` (UTC{tz:+.1f})\n👥 Profili salvati totali: {count}\n\nPer visualizzare la carta o cambiare profilo, usa i pulsanti sotto:",
        "reset_empty": "Dati della sessione cancellati. Nessun profilo trovato. Per creare una carta, premi /chart o il pulsante sotto:",
        "reset_prompt": "⚠️ *Gestione Reset Dati*\n\nProfili salvati nel database: *{count}*.\nCosa desideri fare?",
        "reset_cache_done": "🔄 Cache di sessione svuotata. Profili nel database conservati!",
        "reset_all_done": "🗑 Tutti i tuoi profili astrologici sono stati eliminati dal database.",
        "rename_prompt_usage": "Nome del profilo attivo attuale: *'{name}'*.\n\nPer rinominarlo, specifica il nuovo nome:\n👉 `/rename Marco`",
        "rename_too_long": "Il nome del profilo non deve superare i 50 caratteri.",
        "rename_fail": "Impossibile rinominare il profilo. Riprova più tardi.",
        "profile_card_empty": "👤 *Non hai ancora profili salvati.*\n\nCrea il tuo primo profilo astrologico con /chart o il pulsante qui sotto:",
        "chart_img_error": "❌ Impossibile generare l'immagine della carta: {err}",

        # Compatibility
        "compat_missing_profile": "Per analizzare la compatibilità serve prima il tuo profilo salvato!\nPremi /chart per calcolare la tua carta, poi torna su /compat.",
        "compat_select_second": "💞 *Analisi di Compatibilità di Coppia (Ashtakoota)*\n\nIl tuo profilo attivo: *«{name}»* ({dob}, {place}).\n\nSeleziona il partner dai profili salvati o inserisci nuovi dati:",
        "compat_partner_not_found": "Profilo del partner non trovato. Riprova: /compat",
        "compat_step1_new": "💞 *Analisi di Compatibilità di Coppia (Ashtakoota)*\n\nIl tuo profilo (*'{name}'*) è salvato.\nOra inserisci i dati del *partner*.\n\n📅 *Passo 1 di 3:* Data di nascita del partner `GG.MM.AAAA` (es. `20.08.1992`):\n\nPer annullare, digita /cancel",
        "compat_partner_step1": "📅 *Passo 1 di 3:* Inserisci la data di nascita del partner `GG.MM.AAAA` (es. `20.08.1992`):\n\nPer annullare, digita /cancel",
        "compat_partner_step2": "⏰ *Passo 2 di 3:* Ora di nascita del partner `HH:MM` (es. `14:15`):\n\nSe l'ora esatta non è nota, inserisci `12:00`.",
        "compat_partner_step3": "📍 *Passo 3 di 3:* Inserisci la città di nascita del partner (es. `Roma`, `Milano`):",
        "compat_invalid_dob": "⚠️ Formato non valido. Inserisci la data del partner come `GG.MM.AAAA` (es. `20.08.1992`):",
        "compat_invalid_tob": "⚠️ Formato non valido. Inserisci l'ora del partner come `HH:MM` (es. `14:15`):",
        "compat_session_expired": "Sessione scaduta. Ricomincia con /compat.",
        "compat_status_matching": "💞 Confronto delle carte di *{name1}* e *{name2}*...",
        "compat_partner_calc_status": "🌍 Calcolo coordinate e creazione carta del partner...",
        "compat_city_error": "❌ Impossibile trovare la città '{city}'.\nErrore: {err}\n\nInserisci nuovamente la città del partner (o digita /cancel):",
        "compat_chart_error": "❌ Errore nel calcolo della carta del partner: {err}",
        "compat_gemini_missing": "ℹ️ *Carte di entrambi i partner caricate!*\n\n{kuja_text}\n\nPer l'analisi dettagliata di compatibilità con l'IA, aggiungi `GEMINI_API_KEY` a `.env`.",
        "compat_ai_matching_status": "💞 L'IA sta confrontando le due carte con il sistema Ashtakoota...",
        "compat_analysis_header": "💘 *Analisi di Sinastria e Compatibilità:*\n\n",
        "compat_analysis_error": "⚠️ Errore durante l'analisi di compatibilità: {err}",

        # Payments & Services
        "payment_success_generic": "Grazie per il pagamento! Il tuo consulto premium è attivo.",
        "payment_status_chart": "🔮 Elaborazione dell'interpretazione approfondita del tema natale...",
        "payment_status_dasha": "⏳ Elaborazione dell'analisi approfondita dei periodi planetari...",
        "payment_status_compat": "💞 Analisi della sinastria tra le due carte...",
        "payment_status_yoga": "🧘 L'Astrologo IA sta interpretando gli yoga rilevati...",
        "payment_status_karma": "🔮 Elaborazione dell'analisi karmica profonda dell'anima...",
        "payment_status_money": "💼 Elaborazione della strategia finanziaria...",
        "payment_yoga_ready": "🧘 Pagamento ricevuto! Premi /yoga per analizzare gli yoga.",
        "ai_unavailable": "⚠️ L'Astrologo IA non è al momento disponibile.",

        # Button labels
        "btn_show_chart": "📜 Mostra Carta",
        "btn_dasha_periods": "⏳ Periodi Dasha",
        "btn_all_profiles": "👤 I Miei Profili",
        "btn_prices": "⭐️ Tariffe",
        "btn_add_profile": "➕ Aggiungi Profilo",
        "btn_edit_profile": "✏️ Modifica Dati",
        "btn_delete_profile": "🗑 Elimina Profilo",
        "btn_back_to_profiles": "🔙 Torna ai Profili",
        "btn_manual_input": "✏️ Inserisci dati manualmente",
        "btn_new_profile": "➕ Nuovo Profilo",
        "btn_clear_cache": "🔄 Svuota Cache Sessione",
        "btn_delete_all_db": "🗑 Elimina TUTTI i Profili",
        "btn_profile_menu": "👤 Gestione Profili",
        "btn_select_format": "👉 Seleziona '{name}'",
        "btn_active_format": "⭐️ {name} (attivo)",
        "btn_delete_format": "❌ Elimina '{name}'",
        "btn_clean_duplicates": "🧹 Pulisci Duplicati",
        "duplicates_cleaned": "✅ Rimossi {count} profili duplicati. Profilo attivo: '{name}'.",
        "duplicates_none": "ℹ️ Nessun profilo duplicato trovato. Tutti i profili sono unici.",
    }
}


def t(key: str, lang: str = "ru", **kwargs) -> str:
    """
    Получить локализованный текст по ключу с автоматическим фолбэком на русский язык.
    Поддерживает подстановку именованных параметров через str.format(**kwargs).
    """
    lang = normalize_language(lang)
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    template = lang_dict.get(key)
    if template is None:
        template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


# =========================================================================
# КЛАВИАТУРЫ И КНОПКИ (Многоязычные генераторы)
# =========================================================================

REPLY_KEYBOARD_LAYOUTS: Dict[str, List[List[str]]] = {
    "ru": [
        ["🔮 Натальная карта", "⏳ Периоды Даша"],
        ["💰 Деньги и карьера", "🔮 Кармическая задача"],
        ["🪐 Саде-Сати", "🧘 Детектор йог"],
        ["🛡 Упайи (Гармонизация)", "💞 Совместимость"],
        ["❓ Задать вопрос", "👤 Мои профили"],
        ["⭐️ Тарифы", "📖 Справка"],
    ],
    "en": [
        ["🔮 Natal Chart", "⏳ Dasha Periods"],
        ["💰 Money & Career", "🔮 Karmic Task"],
        ["🪐 Sade-Sati", "🧘 Yoga Detector"],
        ["🛡 Upayas (Remedies)", "💞 Compatibility"],
        ["❓ Ask a Question", "👤 My Profiles"],
        ["⭐️ Prices", "📖 Help"],
    ],
    "it": [
        ["🔮 Carta Natale", "⏳ Periodi Dasha"],
        ["💰 Denaro e Carriera", "🔮 Compito Karmico"],
        ["🪐 Sade-Sati", "🧘 Rilevatore Yoga"],
        ["🛡 Upaya (Rimedi)", "💞 Compatibilità"],
        ["❓ Fai una Domanda", "👤 I Miei Profili"],
        ["⭐️ Tariffe", "📖 Guida"],
    ]
}


def get_main_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Главная нижняя клавиатура быстрого доступа на выбранном языке."""
    lang = normalize_language(lang)
    layout = REPLY_KEYBOARD_LAYOUTS.get(lang, REPLY_KEYBOARD_LAYOUTS["ru"])
    return ReplyKeyboardMarkup(layout, resize_keyboard=True, is_persistent=True)


def get_cancel_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    lang = normalize_language(lang)
    btn_text = {
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "it": "❌ Annulla",
    }.get(lang, "❌ Отмена")
    return ReplyKeyboardMarkup([[btn_text]], resize_keyboard=True, one_time_keyboard=True)


def get_language_inline_keyboard(current_lang: str = "ru") -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для переключения языка интерфейса."""
    lang = normalize_language(current_lang)

    def mark(code: str) -> str:
        return " ✅" if lang == code else ""

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🇷🇺 Русский{mark('ru')}", callback_data="set_lang_ru"),
            InlineKeyboardButton(f"🇬🇧 English{mark('en')}", callback_data="set_lang_en"),
        ],
        [
            InlineKeyboardButton(f"🇮🇹 Italiano{mark('it')}", callback_data="set_lang_it"),
            InlineKeyboardButton("🌐 Auto (Telegram)", callback_data="set_lang_auto"),
        ]
    ])


def get_start_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Инлайн-кнопки приветствия /start."""
    lang = normalize_language(lang)
    labels = {
        "ru": ("🔮 Натальная карта", "👤 Мои профили", "💰 Деньги и карьера", "🔮 Кармическая задача", "⭐️ Тарифы", "📖 Справка", "🌐 Язык"),
        "en": ("🔮 Natal Chart", "👤 My Profiles", "💰 Money & Career", "🔮 Karmic Task", "⭐️ Prices", "📖 Help", "🌐 Language"),
        "it": ("🔮 Carta Natale", "👤 I Miei Profili", "💰 Denaro e Carriera", "🔮 Compito Karmico", "⭐️ Tariffe", "📖 Guida", "🌐 Lingua"),
    }.get(lang, ("🔮 Натальная карта", "👤 Мои профили", "💰 Деньги и карьера", "🔮 Кармическая задача", "⭐️ Тарифы", "📖 Справка", "🌐 Язык"))

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(labels[0], callback_data="nav_chart"),
            InlineKeyboardButton(labels[1], callback_data="prof_menu"),
        ],
        [
            InlineKeyboardButton(labels[2], callback_data="nav_money"),
            InlineKeyboardButton(labels[3], callback_data="nav_karma"),
        ],
        [
            InlineKeyboardButton(labels[4], callback_data="nav_prices"),
            InlineKeyboardButton(labels[5], callback_data="nav_help"),
        ],
        [
            InlineKeyboardButton(labels[6], callback_data="nav_lang"),
        ]
    ])


def get_chart_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Инлайн-кнопки после отображения натальной карты."""
    lang = normalize_language(lang)
    lbls = {
        "ru": {
            "img": "🖼 Изображение карты (D1)",
            "money": "💰 Деньги и карьера",
            "karma": "🔮 Кармическая задача",
            "dasha": "⏳ Периоды Даша",
            "sadesati": "🪐 Саде-Сати",
            "yoga": "🧘 Детектор йог",
            "upaya": "🛡 Упайи (Гармонизация)",
            "ask": "❓ Задать вопрос",
            "compat": "💞 Совместимость",
            "edit": "✏️ Изменить данные",
            "profiles": "👤 Профили",
            "prices": "⭐️ Тарифы",
            "lang": "🌐 Язык / Language",
        },
        "en": {
            "img": "🖼 Chart Image (D1)",
            "money": "💰 Money & Career",
            "karma": "🔮 Karmic Task",
            "dasha": "⏳ Dasha Periods",
            "sadesati": "🪐 Sade-Sati",
            "yoga": "🧘 Yoga Detector",
            "upaya": "🛡 Upayas (Remedies)",
            "ask": "❓ Ask a Question",
            "compat": "💞 Compatibility",
            "edit": "✏️ Edit Details",
            "profiles": "👤 Profiles",
            "prices": "⭐️ Prices",
            "lang": "🌐 Language",
        },
        "it": {
            "img": "🖼 Immagine Carta (D1)",
            "money": "💰 Denaro e Carriera",
            "karma": "🔮 Compito Karmico",
            "dasha": "⏳ Periodi Dasha",
            "sadesati": "🪐 Sade-Sati",
            "yoga": "🧘 Rilevatore Yoga",
            "upaya": "🛡 Upaya (Rimedi)",
            "ask": "❓ Fai una Domanda",
            "compat": "💞 Compatibilità",
            "edit": "✏️ Modifica Dati",
            "profiles": "👤 Profili",
            "prices": "⭐️ Tariffe",
            "lang": "🌐 Lingua",
        }
    }.get(lang, {
        "img": "🖼 Изображение карты (D1)",
        "money": "💰 Деньги и карьера",
        "karma": "🔮 Кармическая задача",
        "dasha": "⏳ Периоды Даша",
        "sadesati": "🪐 Саде-Сати",
        "yoga": "🧘 Детектор йог",
        "upaya": "🛡 Упайи (Гармонизация)",
        "ask": "❓ Задать вопрос",
        "compat": "💞 Совместимость",
        "edit": "✏️ Изменить данные",
        "profiles": "👤 Профили",
        "prices": "⭐️ Тарифы",
        "lang": "🌐 Язык / Language",
    })

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls["img"], callback_data="nav_chart_img")],
        [InlineKeyboardButton(lbls["money"], callback_data="nav_money"), InlineKeyboardButton(lbls["karma"], callback_data="nav_karma")],
        [InlineKeyboardButton(lbls["dasha"], callback_data="nav_dasha"), InlineKeyboardButton(lbls["sadesati"], callback_data="nav_sadesati")],
        [InlineKeyboardButton(lbls["yoga"], callback_data="nav_yoga"), InlineKeyboardButton(lbls["upaya"], callback_data="nav_upaya")],
        [InlineKeyboardButton(lbls["ask"], callback_data="nav_ask"), InlineKeyboardButton(lbls["compat"], callback_data="nav_compat")],
        [InlineKeyboardButton(lbls["edit"], callback_data="prof_recalc_start"), InlineKeyboardButton(lbls["profiles"], callback_data="prof_menu")],
        [InlineKeyboardButton(lbls["prices"], callback_data="nav_prices"), InlineKeyboardButton(lbls["lang"], callback_data="nav_lang")],
    ])


def get_karma_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("❓ Задать вопрос по карме", "💰 Финансы и карьера", "⏳ Периоды Даша", "🛡 Упайи (Гармонизация)", "🔮 Моя карта", "⭐️ Все тарифы"),
        "en": ("❓ Question on Karma", "💰 Finance & Career", "⏳ Dasha Periods", "🛡 Upayas (Remedies)", "🔮 My Chart", "⭐️ All Prices"),
        "it": ("❓ Domanda sul Karma", "💰 Finanze e Carriera", "⏳ Periodi Dasha", "🛡 Upaya (Rimedi)", "🔮 La Mia Carta", "⭐️ Tutte le Tariffe"),
    }.get(lang, ("❓ Задать вопрос по карме", "💰 Финансы и карьера", "⏳ Периоды Даша", "🛡 Упайи (Гармонизация)", "🔮 Моя карта", "⭐️ Все тарифы"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_ask"), InlineKeyboardButton(lbls[1], callback_data="nav_money")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_dasha"), InlineKeyboardButton(lbls[3], callback_data="nav_upaya")],
        [InlineKeyboardButton(lbls[4], callback_data="nav_mydata"), InlineKeyboardButton(lbls[5], callback_data="nav_prices")],
    ])


def get_money_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("❓ Вопрос по финансам", "🔮 Кармическая задача", "🧘 Детектор йог", "⏳ Периоды Даша", "🔮 Моя карта", "⭐️ Все тарифы"),
        "en": ("❓ Finance Question", "🔮 Karmic Task", "🧘 Yoga Detector", "⏳ Dasha Periods", "🔮 My Chart", "⭐️ All Prices"),
        "it": ("❓ Domanda Finanze", "🔮 Compito Karmico", "🧘 Rilevatore Yoga", "⏳ Periodi Dasha", "🔮 La Mia Carta", "⭐️ Tutte le Tariffe"),
    }.get(lang, ("❓ Вопрос по финансам", "🔮 Кармическая задача", "🧘 Детектор йог", "⏳ Периоды Даша", "🔮 Моя карта", "⭐️ Все тарифы"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_ask"), InlineKeyboardButton(lbls[1], callback_data="nav_karma")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_yoga"), InlineKeyboardButton(lbls[3], callback_data="nav_dasha")],
        [InlineKeyboardButton(lbls[4], callback_data="nav_mydata"), InlineKeyboardButton(lbls[5], callback_data="nav_prices")],
    ])


def get_upaya_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("❓ Задать вопрос по упайям", "🪐 Проверить Саде-Сати", "💰 Деньги и карьера", "🔮 Кармическая задача", "🔮 Моя карта", "⭐️ Все тарифы"),
        "en": ("❓ Question on Upayas", "🪐 Check Sade-Sati", "💰 Money & Career", "🔮 Karmic Task", "🔮 My Chart", "⭐️ All Prices"),
        "it": ("❓ Domanda sugli Upaya", "🪐 Verifica Sade-Sati", "💰 Denaro e Carriera", "🔮 Compito Karmico", "🔮 La Mia Carta", "⭐️ Tutte le Tariffe"),
    }.get(lang, ("❓ Задать вопрос по упайям", "🪐 Проверить Саде-Сати", "💰 Деньги и карьера", "🔮 Кармическая задача", "🔮 Моя карта", "⭐️ Все тарифы"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_ask"), InlineKeyboardButton(lbls[1], callback_data="nav_sadesati")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_money"), InlineKeyboardButton(lbls[3], callback_data="nav_karma")],
        [InlineKeyboardButton(lbls[4], callback_data="nav_mydata"), InlineKeyboardButton(lbls[5], callback_data="nav_prices")],
    ])


def get_dasha_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("🪐 Проверить Саде-Сати", "🧘 Найти йоги", "❓ Задать вопрос по Даша", "🔮 Моя карта"),
        "en": ("🪐 Check Sade-Sati", "🧘 Find Yogas", "❓ Question on Dasha", "🔮 My Chart"),
        "it": ("🪐 Verifica Sade-Sati", "🧘 Trova gli Yoga", "❓ Domanda su Dasha", "🔮 La Mia Carta"),
    }.get(lang, ("🪐 Проверить Саде-Сати", "🧘 Найти йоги", "❓ Задать вопрос по Даша", "🔮 Моя карта"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_sadesati"), InlineKeyboardButton(lbls[1], callback_data="nav_yoga")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_ask"), InlineKeyboardButton(lbls[3], callback_data="nav_mydata")],
    ])


def get_sadesati_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("⏳ Периоды Даша", "🧘 Детектор йог", "❓ Вопрос астрологу", "🔮 Моя карта"),
        "en": ("⏳ Dasha Periods", "🧘 Yoga Detector", "❓ Ask Astrologer", "🔮 My Chart"),
        "it": ("⏳ Periodi Dasha", "🧘 Rilevatore Yoga", "❓ Chiedi all'Astrologo", "🔮 La Mia Carta"),
    }.get(lang, ("⏳ Периоды Даша", "🧘 Детектор йог", "❓ Вопрос астрологу", "🔮 Моя карта"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_dasha"), InlineKeyboardButton(lbls[1], callback_data="nav_yoga")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_ask"), InlineKeyboardButton(lbls[3], callback_data="nav_mydata")],
    ])


def get_yoga_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("❓ Вопрос по йогам", "⏳ Периоды Даша", "🪐 Саде-Сати", "🔮 Моя карта"),
        "en": ("❓ Question on Yogas", "⏳ Dasha Periods", "🪐 Sade-Sati", "🔮 My Chart"),
        "it": ("❓ Domanda sugli Yoga", "⏳ Periodi Dasha", "🪐 Sade-Sati", "🔮 La Mia Carta"),
    }.get(lang, ("❓ Вопрос по йогам", "⏳ Периоды Даша", "🪐 Саде-Сати", "🔮 Моя карта"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_ask"), InlineKeyboardButton(lbls[1], callback_data="nav_dasha")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_sadesati"), InlineKeyboardButton(lbls[3], callback_data="nav_mydata")],
    ])


def get_ask_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("❓ Ещё один вопрос", "⏳ Периоды Даша", "🧘 Детектор йог", "⭐️ Все тарифы"),
        "en": ("❓ Another Question", "⏳ Dasha Periods", "🧘 Yoga Detector", "⭐️ All Prices"),
        "it": ("❓ Un'Altra Domanda", "⏳ Periodi Dasha", "🧘 Rilevatore Yoga", "⭐️ Tutte le Tariffe"),
    }.get(lang, ("❓ Ещё один вопрос", "⏳ Периоды Даша", "🧘 Детектор йог", "⭐️ Все тарифы"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_ask"), InlineKeyboardButton(lbls[1], callback_data="nav_dasha")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_yoga"), InlineKeyboardButton(lbls[3], callback_data="nav_prices")],
    ])


def get_compat_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    lbls = {
        "ru": ("❓ Вопрос об отношениях", "⏳ Мои периоды", "🔮 Моя карта", "⭐️ Тарифы"),
        "en": ("❓ Question on Relations", "⏳ My Periods", "🔮 My Chart", "⭐️ Prices"),
        "it": ("❓ Domanda sulla Coppia", "⏳ I Miei Periodi", "🔮 La Mia Carta", "⭐️ Tariffe"),
    }.get(lang, ("❓ Вопрос об отношениях", "⏳ Мои периоды", "🔮 Моя карта", "⭐️ Тарифы"))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls[0], callback_data="nav_ask"), InlineKeyboardButton(lbls[1], callback_data="nav_dasha")],
        [InlineKeyboardButton(lbls[2], callback_data="nav_mydata"), InlineKeyboardButton(lbls[3], callback_data="nav_prices")],
    ])


def get_prices_inline_keyboard(lang: str = "ru", prices: Optional[Dict[str, int]] = None) -> InlineKeyboardMarkup:
    lang = normalize_language(lang)
    p = prices or {
        "chart": 150, "dasha": 100, "karma": 100, "money": 100,
        "compat": 150, "ask": 50, "yoga": 100, "bundle": 300
    }
    lbls = {
        "ru": {
            "chart": f"🔮 Карта ({p['chart']} ⭐️)", "dasha": f"⏳ Даша ({p['dasha']} ⭐️)",
            "karma": f"🔮 Карма ({p['karma']} ⭐️)", "money": f"💰 Деньги ({p['money']} ⭐️)",
            "compat": f"💞 Совместимость ({p['compat']} ⭐️)", "ask": f"❓ Вопрос ({p['ask']} ⭐️)",
            "yoga": f"🧘 Йоги ({p['yoga']} ⭐️)", "bundle": f"🌟 Бандл 360° ({p['bundle']} ⭐️)",
        },
        "en": {
            "chart": f"🔮 Chart ({p['chart']} ⭐️)", "dasha": f"⏳ Dasha ({p['dasha']} ⭐️)",
            "karma": f"🔮 Karma ({p['karma']} ⭐️)", "money": f"💰 Money ({p['money']} ⭐️)",
            "compat": f"💞 Compatibility ({p['compat']} ⭐️)", "ask": f"❓ Question ({p['ask']} ⭐️)",
            "yoga": f"🧘 Yogas ({p['yoga']} ⭐️)", "bundle": f"🌟 Bundle 360° ({p['bundle']} ⭐️)",
        },
        "it": {
            "chart": f"🔮 Carta ({p['chart']} ⭐️)", "dasha": f"⏳ Dasha ({p['dasha']} ⭐️)",
            "karma": f"🔮 Karma ({p['karma']} ⭐️)", "money": f"💰 Denaro ({p['money']} ⭐️)",
            "compat": f"💞 Compatibilità ({p['compat']} ⭐️)", "ask": f"❓ Domanda ({p['ask']} ⭐️)",
            "yoga": f"🧘 Yoga ({p['yoga']} ⭐️)", "bundle": f"🌟 Bundle 360° ({p['bundle']} ⭐️)",
        }
    }.get(lang, {
        "chart": f"🔮 Карта ({p['chart']} ⭐️)", "dasha": f"⏳ Даша ({p['dasha']} ⭐️)",
        "karma": f"🔮 Карма ({p['karma']} ⭐️)", "money": f"💰 Деньги ({p['money']} ⭐️)",
        "compat": f"💞 Совместимость ({p['compat']} ⭐️)", "ask": f"❓ Вопрос ({p['ask']} ⭐️)",
        "yoga": f"🧘 Йоги ({p['yoga']} ⭐️)", "bundle": f"🌟 Бандл 360° ({p['bundle']} ⭐️)",
    })

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbls["chart"], callback_data="buy_chart"), InlineKeyboardButton(lbls["dasha"], callback_data="buy_dasha")],
        [InlineKeyboardButton(lbls["karma"], callback_data="buy_karma"), InlineKeyboardButton(lbls["money"], callback_data="buy_money")],
        [InlineKeyboardButton(lbls["compat"], callback_data="buy_compat"), InlineKeyboardButton(lbls["ask"], callback_data="buy_ask")],
        [InlineKeyboardButton(lbls["yoga"], callback_data="buy_yoga"), InlineKeyboardButton(lbls["bundle"], callback_data="buy_bundle")],
    ])


# =========================================================================
# МАППИНГ КНОПОК МЕНЮ НА ВНУТРЕННИЕ ДЕЙСТВИЯ (Многоязычный)
# =========================================================================

MENU_BUTTON_ACTIONS: Dict[str, str] = {
    # Russian
    "🔮 Натальная карта": "chart",
    "⏳ Периоды Даша": "dasha",
    "💰 Деньги и карьера": "money",
    "🔮 Кармическая задача": "karma",
    "🪐 Саде-Сати": "sadesati",
    "🧘 Детектор йог": "yoga",
    "🛡 Упайи (Гармонизация)": "upaya",
    "🛡 Упайи (Коррекция)": "upaya",
    "🛡 Упайи": "upaya",
    "💞 Совместимость": "compat",
    "❓ Задать вопрос": "ask",
    "👤 Мои профили": "profile",
    "👤 Профили": "profile",
    "📋 Мои данные": "profile",
    "🔄 Сменить профиль": "profile",
    "⭐️ Тарифы": "prices",
    "📖 Справка": "help",
    "🌐 Язык": "lang",
    "🌐 Сменить язык": "lang",

    # English
    "🔮 Natal Chart": "chart",
    "⏳ Dasha Periods": "dasha",
    "💰 Money & Career": "money",
    "🔮 Karmic Task": "karma",
    "🪐 Sade-Sati": "sadesati",
    "🧘 Yoga Detector": "yoga",
    "🛡 Upayas (Remedies)": "upaya",
    "🛡 Upayas": "upaya",
    "💞 Compatibility": "compat",
    "❓ Ask a Question": "ask",
    "👤 My Profiles": "profile",
    "👤 Profiles": "profile",
    "⭐️ Prices": "prices",
    "📖 Help": "help",
    "🌐 Language": "lang",
    "🌐 Change Language": "lang",

    # Italian
    "🔮 Carta Natale": "chart",
    "⏳ Periodi Dasha": "dasha",
    "💰 Denaro e Carriera": "money",
    "🔮 Compito Karmico": "karma",
    "🪐 Sade-Sati": "sadesati",
    "🧘 Rilevatore Yoga": "yoga",
    "🛡 Upaya (Rimedi)": "upaya",
    "🛡 Upaya": "upaya",
    "💞 Compatibilità": "compat",
    "❓ Fai una Domanda": "ask",
    "👤 I Miei Profili": "profile",
    "👤 Profili": "profile",
    "⭐️ Tariffe": "prices",
    "📖 Guida": "help",
    "🌐 Lingua": "lang",
    "🌐 Cambia Lingua": "lang",
}

# Регулярные выражения для MessageHandler фильтров
MENU_REGEX_PATTERN: str = r"^(" + "|".join([
    # RU
    r"🔮\s*Натальная карта", r"⏳\s*Периоды Даша", r"💰\s*Деньги и карьера", r"🔮\s*Кармическая задача",
    r"🪐\s*Саде-Сати", r"🧘\s*Детектор йог", r"🛡\s*Упайи.*", r"💞\s*Совместимость", r"❓\s*Задать вопрос",
    r"👤\s*Мои профили", r"👤\s*Профили", r"📋\s*Мои данные", r"🔄\s*Сменить профиль", r"⭐️\s*Тарифы", r"📖\s*Справка",
    # EN
    r"🔮\s*Natal Chart", r"⏳\s*Dasha Periods", r"💰\s*Money & Career", r"🔮\s*Karmic Task",
    r"🪐\s*Sade-Sati", r"🧘\s*Yoga Detector", r"🛡\s*Upayas.*", r"💞\s*Compatibility", r"❓\s*Ask a Question",
    r"👤\s*My Profiles", r"👤\s*Profiles", r"⭐️\s*Prices", r"📖\s*Help",
    # IT
    r"🔮\s*Carta Natale", r"⏳\s*Periodi Dasha", r"💰\s*Denaro e Carriera", r"🔮\s*Compito Karmico",
    r"🪐\s*Sade-Sati", r"🧘\s*Rilevatore Yoga", r"🛡\s*Upaya.*", r"💞\s*Compatibilità", r"❓\s*Fai una Domanda",
    r"👤\s*I Miei Profili", r"👤\s*Profili", r"⭐️\s*Tariffe", r"📖\s*Guida",
    # Common
    r"🌐\s*(?:Язык|Language|Lingua).*"
]) + r")$"

CANCEL_REGEX_PATTERN: str = r"^(❌\s*(?:Отмена|Cancel|Annulla)|Отмена|Cancel|Annulla|annullare|abort|/cancel)$"


def is_cancel_input(text: Optional[str]) -> bool:
    """Проверяет, является ли введённый текст командой отмены на любом из языков (RU, EN, IT)."""
    if not text or not isinstance(text, str):
        return False
    return bool(re.match(CANCEL_REGEX_PATTERN, text.strip(), flags=re.IGNORECASE))


# =========================================================================
# ОПИСАНИЯ ЙОГ (Многоязычные)
# =========================================================================

YOGA_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "ru": {
        "Gajakesari Yoga": "Юпитер в кендре от Луны — мудрость, авторитет, слава и достаток.",
        "Budhaditya Yoga": "Солнце и Меркурий в одном знаке — интеллект, красноречие, лидерские качества.",
        "Pancha Mahapurusha - Mars": "Марс в экзальтации/свакшетре в кендре — храбрость, сила, военное мастерство.",
        "Pancha Mahapurusha - Mercury": "Меркурий в экзальтации/свакшетре в кендре — интеллект, коммуникабельность, торговый дар.",
        "Pancha Mahapurusha - Jupiter": "Юпитер в экзальтации/свакшетре в кендре — духовность, мудрость, благочестие.",
        "Pancha Mahapurusha - Venus": "Венера в экзальтации/свакшетре в кендре — красота, роскошь, любовь, искусство.",
        "Pancha Mahapurusha - Saturn": "Сатурн в экзальтации/свакшетре в кендре — власть, дисциплина, долголетие.",
        "Raja Yoga": "Связь хозяев кендр и трикон — успех, власть, реализация, высокий статус.",
        "Dhana Yoga": "Связь хозяев домов богатства (2, 5, 9, 11) с кендрами — материальное благополучие.",
    },
    "en": {
        "Gajakesari Yoga": "Jupiter in Kendra from Moon — wisdom, authority, fame, and abundance.",
        "Budhaditya Yoga": "Sun and Mercury in the same sign — intellect, eloquence, leadership qualities.",
        "Pancha Mahapurusha - Mars": "Mars in Kendra (exalted/own) — courage, strength, heroic energy (Ruchaka).",
        "Pancha Mahapurusha - Mercury": "Mercury in Kendra (exalted/own) — sharp intellect, commerce, communication (Bhadra).",
        "Pancha Mahapurusha - Jupiter": "Jupiter in Kendra (exalted/own) — wisdom, righteousness, high spirituality (Hamsa).",
        "Pancha Mahapurusha - Venus": "Venus in Kendra (exalted/own) — beauty, luxury, elegance, refined arts (Malavya).",
        "Pancha Mahapurusha - Saturn": "Saturn in Kendra (exalted/own) — authority, discipline, perseverance, longevity (Sasha).",
        "Raja Yoga": "Lords of Kendras & Trikonas combined — power, success, high social status.",
        "Dhana Yoga": "Lords of wealth houses (2, 5, 9, 11) in Kendras — financial growth and abundance.",
    },
    "it": {
        "Gajakesari Yoga": "Giove in casa Kendra dalla Luna — saggezza, autorevolezza, fama e prosperità.",
        "Budhaditya Yoga": "Sole e Mercurio nello stesso segno — intelligenza brillante, eloquenza e leadership.",
        "Pancha Mahapurusha - Mars": "Marte in Kendra (esaltato/proprio) — coraggio, vigore e determinazione (Ruchaka).",
        "Pancha Mahapurusha - Mercury": "Mercurio in Kendra (esaltato/proprio) — intelletto acuto, talento commerciale (Bhadra).",
        "Pancha Mahapurusha - Jupiter": "Giove in Kendra (esaltato/proprio) — spiritualità, saggezza e nobiltà d'animo (Hamsa).",
        "Pancha Mahapurusha - Venus": "Venere in Kendra (esaltata/propria) — bellezza, eleganza, lusso e arte (Malavya).",
        "Pancha Mahapurusha - Saturn": "Saturno in Kendra (esaltato/proprio) — autorità, disciplina, rigore e longevità (Sasha).",
        "Raja Yoga": "Connessione tra i governatori di Kendra e Trikona — successo, influenza e prestigio.",
        "Dhana Yoga": "Governatori delle case del denaro (2, 5, 9, 11) in Kendra — prosperità economica.",
    }
}


def get_yoga_description(yoga_name: str, lang: str = "ru", default: str = "") -> str:
    """Возвращает локализованное описание йоги на RU, EN, IT."""
    lang = normalize_language(lang)
    return YOGA_DESCRIPTIONS.get(lang, YOGA_DESCRIPTIONS["ru"]).get(yoga_name, default)


def get_profile_management_keyboard(lang: str = "ru", profiles: Optional[List[Dict[str, Any]]] = None) -> InlineKeyboardMarkup:
    """Генерирует инлайн-кнопки для списка профилей на выбранном языке."""
    lang = normalize_language(lang)
    buttons = []
    if profiles:
        for p in profiles:
            p_id = p.get("id")
            p_name = p.get("profile_name", "")
            is_act = p.get("is_active", False)
            if is_act:
                btn_lbl = t("btn_active_format", lang, name=p_name)
            else:
                btn_lbl = t("btn_select_format", lang, name=p_name)
            buttons.append([
                InlineKeyboardButton(btn_lbl, callback_data=f"prof_switch_{p_id}"),
                InlineKeyboardButton("✏️", callback_data=f"prof_edit_{p_id}"),
            ])

    buttons.append([
        InlineKeyboardButton(t("btn_edit_profile", lang), callback_data="prof_recalc_start"),
        InlineKeyboardButton(t("btn_add_profile", lang), callback_data="prof_add_start"),
    ])
    buttons.append([
        InlineKeyboardButton(t("btn_show_chart", lang), callback_data="prof_view_active"),
        InlineKeyboardButton(t("btn_clean_duplicates", lang), callback_data="prof_cleanup_duplicates"),
    ])
    buttons.append([
        InlineKeyboardButton(t("btn_delete_profile", lang), callback_data="prof_delete_menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def get_mydata_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Инлайн-кнопки под карточкой /mydata на выбранном языке."""
    lang = normalize_language(lang)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_edit_profile", lang), callback_data="prof_recalc_start"),
            InlineKeyboardButton(t("btn_show_chart", lang), callback_data="prof_view_active"),
        ],
        [
            InlineKeyboardButton(t("btn_all_profiles", lang), callback_data="prof_menu"),
            InlineKeyboardButton(t("btn_new_profile", lang), callback_data="prof_add_start"),
        ],
        [
            InlineKeyboardButton(t("btn_dasha_periods", lang), callback_data="nav_dasha"),
        ],
    ])


def get_reset_inline_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Инлайн-кнопки меню сброса данных /reset на выбранном языке."""
    lang = normalize_language(lang)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_clear_cache", lang), callback_data="reset_cache_only")],
        [InlineKeyboardButton(t("btn_delete_all_db", lang), callback_data="reset_all_confirm")],
        [InlineKeyboardButton(t("btn_profile_menu", lang), callback_data="prof_menu")],
    ])


def get_profile_switched_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Инлайн-кнопки после успешного переключения профиля на выбранном языке."""
    lang = normalize_language(lang)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_show_chart", lang), callback_data="prof_view_active"),
            InlineKeyboardButton(t("btn_dasha_periods", lang), callback_data="nav_dasha"),
        ],
        [
            InlineKeyboardButton(t("btn_all_profiles", lang), callback_data="prof_menu"),
            InlineKeyboardButton(t("btn_prices", lang), callback_data="nav_prices"),
        ],
    ])
