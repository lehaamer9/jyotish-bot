"""
Telegram-бот ИИ-Джьотиш Астролог.
Полноценный бот с расчётом натальных карт, периодов Вимшоттари Даша,
анализом совместимости, экспертной интерпретацией через Google Gemini
и приёмом оплаты в Звёздах Telegram (Stars / XTR).
"""
import os
import sys
import re
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, time
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Настройка кодировки консоли Windows для корректного вывода emoji
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Загружаем переменные окружения из .env
load_dotenv()

from telegram import (
    Update,
    BotCommand,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from telegram.ext.filters import MessageFilter
from input_parser import parse_one_line_profile
from chart_renderer import render_kundli_chart

from jyotish_engine import (
    compute_chart,
    format_chart_summary,
    format_dasha_periods,
    get_current_dasha,
    check_sade_sati,
    detect_yogas,
    calculate_chara_karakas,
    format_chara_karakas,
    analyze_wealth_and_career,
    format_wealth_analysis,
    check_kuja_dosha,
    get_upayas,
    format_upayas,
)
from geo_helper import resolve_location
from gemini_interpreter import GeminiInterpreter
from payment_helper import (
    send_chart_invoice,
    send_dasha_invoice,
    send_compat_invoice,
    send_ask_invoice,
    send_yoga_invoice,
    send_karma_invoice,
    send_money_invoice,
    send_bundle_invoice,
    send_test_invoice,
    precheckout_callback,
    PAYMENT_REQUIRED,
    PRICE_CHART_STARS,
    PRICE_DASHA_STARS,
    PRICE_COMPAT_STARS,
    PRICE_ASK_STARS,
    PRICE_YOGA_STARS,
    PRICE_KARMA_STARS,
    PRICE_MONEY_STARS,
    PRICE_BUNDLE_STARS,
)
from db_manager import (
    init_db,
    save_profile,
    get_active_profile,
    get_user_profiles,
    get_profile_by_id,
    set_active_profile,
    delete_profile,
    rename_profile,
    clear_user_profiles,
    count_user_profiles,
    get_system_stats,
    is_free_ask_available,
    mark_free_ask_used,
    get_user_language,
    set_user_language,
    update_profile_data,
    cleanup_duplicate_profiles,
    get_profile_by_name_or_index,
)
from i18n import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    normalize_language,
    get_user_lang,
    t,
    get_main_reply_keyboard,
    get_cancel_reply_keyboard,
    get_language_inline_keyboard,
    get_start_inline_keyboard,
    get_chart_inline_keyboard,
    get_karma_inline_keyboard,
    get_money_inline_keyboard,
    get_upaya_inline_keyboard,
    get_dasha_inline_keyboard,
    get_sadesati_inline_keyboard,
    get_yoga_inline_keyboard,
    get_ask_inline_keyboard,
    get_compat_inline_keyboard,
    get_prices_inline_keyboard,
    get_profile_management_keyboard,
    get_mydata_inline_keyboard,
    get_reset_inline_keyboard,
    get_profile_switched_keyboard,
    MENU_BUTTON_ACTIONS,
    MENU_REGEX_PATTERN,
    CANCEL_REGEX_PATTERN,
    is_cancel_input,
    get_sign_name,
    get_planet_name,
    get_yoga_description,
)


def is_keep_input(text: Optional[str]) -> bool:
    """Проверяет, выразил ли пользователь намерение оставить текущее значение параметра при редактировании."""
    if not text:
        return False
    norm = text.strip().lower()
    return norm in {
        "/keep", "keep", "/skip", "skip",
        "оставить", "сохранить", "пропустить", "дальше", "без изменений",
        "lascia", "mantieni", "salta", "avanti"
    }


# Telegram ID администратора (Александр)
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "1275394562"))

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога для натальной карты
(
    WAITING_PROFILE_NAME,
    WAITING_DOB,
    WAITING_TOB,
    WAITING_PLACE,
) = range(4)

# Состояния диалога для совместимости (партнёр)
(
    COMPAT_SELECT_PARTNER,
    COMPAT_WAITING_DOB,
    COMPAT_WAITING_TOB,
    COMPAT_WAITING_PLACE,
) = range(4, 8)

# Состояние диалога для экспресс-вопроса /ask
ASK_WAITING_QUESTION = 8

TELEGRAM_MAX_MESSAGE_LENGTH = 4000


class OneLineProfileFilter(MessageFilter):
    """Фильтр сообщений, содержащих полные данные натальной карты одной строкой."""
    def filter(self, message):
        if not message or not message.text:
            return False
        if message.text.startswith("/"):
            return False
        text = message.text.strip()
        menu_buttons = {
            "🔮 Натальная карта", "👤 Мои профили", "👤 Профили", "📋 Мои данные",
            "🔄 Сменить профиль", "⏳ Периоды Даша", "🪐 Саде-Сати", "🧘 Детектор йог",
            "❓ Задать вопрос", "💞 Совместимость", "⭐️ Тарифы", "📖 Справка",
            "➕ Добавить профиль", "➕ Новый профиль", "❌ Отмена", "Отмена",
            "🔮 Natal Chart", "⏳ Dasha Periods", "💰 Money & Career", "🔮 Karmic Task",
            "🪐 Sade-Sati", "🧘 Yoga Detector", "🛡 Upayas (Remedies)", "💞 Compatibility",
            "❓ Ask a Question", "👤 My Profiles", "⭐️ Prices", "📖 Help", "🌐 Language",
            "🔮 Carta Natale", "⏳ Periodi Dasha", "💰 Denaro e Carriera", "🔮 Compito Karmico",
            "🛡 Upaya (Rimedi)", "💞 Compatibilità", "❓ Fai una Domanda", "👤 I Miei Profili",
            "⭐️ Tariffe", "📖 Guida", "🌐 Lingua", "❌ Cancel", "Cancel", "❌ Annulla", "Annulla"
        }
        if text in menu_buttons or text in MENU_BUTTON_ACTIONS:
            return False
        if re.match(MENU_REGEX_PATTERN, text) or re.match(CANCEL_REGEX_PATTERN, text):
            return False
        parsed = parse_one_line_profile(text)
        return bool(parsed and parsed.get("is_complete"))


one_line_filter = OneLineProfileFilter()


def get_user_natal_profile(user_id: int, context: ContextTypes.DEFAULT_TYPE = None):
    """
    Получить активный натальный профиль пользователя.
    Сначала проверяет кэш текущей сессии context.user_data,
    если его нет — загружает активный профиль из базы данных SQLite (jyotish.db).
    """
    if not user_id:
        return None

    if context is not None and context.user_data is not None:
        cached = context.user_data.get("natal_profile")
        if cached and isinstance(cached, dict) and cached.get("chart_data"):
            return cached

    profile = get_active_profile(user_id)
    if profile and context is not None and context.user_data is not None:
        context.user_data["natal_profile"] = profile
    return profile


def get_gemini_client():
    """Получить клиент Gemini, если задан токен."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY":
        return None
    try:
        return GeminiInterpreter(api_key=api_key)
    except Exception as e:
        logger.error(f"Ошибка инициализации Gemini: {e}")
        return None


async def send_split_message(update: Update, text: str, parse_mode: str = "Markdown", reply_markup=None):
    """Отправить длинное сообщение частями, соблюдая лимит Telegram, прикрепляя клавиатуру к концу."""
    if len(text) <= TELEGRAM_MAX_MESSAGE_LENGTH:
        try:
            await update.effective_message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=reply_markup)
        return

    paragraphs = text.split("\n\n")
    current_chunk = ""
    chunks = []
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > TELEGRAM_MAX_MESSAGE_LENGTH:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        current_chunk += para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await update.effective_message.reply_text(chunk, parse_mode=parse_mode, reply_markup=markup)
        except Exception:
            await update.effective_message.reply_text(chunk, reply_markup=markup)


# ===================== ВЫБОР ЯЗЫКА (/lang) =====================

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /lang для ручного выбора языка интерфейса."""
    user_id = update.effective_user.id if update.effective_user else None
    if context and getattr(context, "args", None) and len(context.args) > 0:
        arg = context.args[0].lower().strip()
        if arg in ("ru", "en", "it"):
            if user_id:
                set_user_language(user_id, arg)
            if context.user_data is not None:
                context.user_data["user_lang"] = arg
            text = t("lang_switched", arg, selected_lang=LANGUAGE_LABELS.get(arg, arg))
            await update.effective_message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_main_reply_keyboard(arg)
            )
            return
        elif arg in ("auto", "default", "reset"):
            if user_id:
                set_user_language(user_id, "")
            if context.user_data is not None:
                context.user_data.pop("user_lang", None)
            lang = get_user_lang(update, context)
            text = t("lang_auto_switched", lang, selected_lang=LANGUAGE_LABELS.get(lang, lang))
            await update.effective_message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_main_reply_keyboard(lang)
            )
            return

    lang = get_user_lang(update, context)
    keyboard = get_language_inline_keyboard(current_lang=lang)
    text = t("choose_language", lang)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")



# ===================== КОМАНДЫ БОТА =====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и описание возможностей бота."""
    user_id = update.effective_user.id
    lang = get_user_lang(update, context)
    active_profile = get_user_natal_profile(user_id, context)

    greeting = t("start_greeting", lang)

    if active_profile:
        dt_str = active_profile["birth_dt"].strftime("%d.%m.%Y %H:%M") if active_profile.get("birth_dt") else ""
        prof_name = active_profile.get("profile_name", "Мой гороскоп")
        place = active_profile.get("place_name", "")
        greeting += t("start_active_profile", lang, name=prof_name, dt=dt_str, place=place)
    else:
        greeting += t("start_no_profile", lang)

    await update.effective_message.reply_text(
        greeting,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard(lang)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам."""
    lang = get_user_lang(update, context)
    help_text = t("help_text", lang)
    await update.effective_message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard(lang)
    )


async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прайс-лист на услуги в Звёздах Telegram."""
    lang = get_user_lang(update, context)
    header = t("prices_header", lang)
    body = t(
        "prices_body",
        lang,
        chart=PRICE_CHART_STARS,
        karma=PRICE_KARMA_STARS,
        money=PRICE_MONEY_STARS,
        dasha=PRICE_DASHA_STARS,
        compat=PRICE_COMPAT_STARS,
        ask=PRICE_ASK_STARS,
        yoga=PRICE_YOGA_STARS,
        bundle=PRICE_BUNDLE_STARS,
    )
    text = header + body
    prices_map = {
        "chart": PRICE_CHART_STARS,
        "dasha": PRICE_DASHA_STARS,
        "karma": PRICE_KARMA_STARS,
        "money": PRICE_MONEY_STARS,
        "compat": PRICE_COMPAT_STARS,
        "ask": PRICE_ASK_STARS,
        "yoga": PRICE_YOGA_STARS,
        "bundle": PRICE_BUNDLE_STARS,
    }
    prices_keyboard = get_prices_inline_keyboard(lang, prices_map)
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=prices_keyboard
    )


async def show_active_profile_card(update: Update, context: ContextTypes.DEFAULT_TYPE, profile: dict):
    """Показать карточку активного профиля с быстрыми действиями."""
    lang = get_user_lang(update, context)
    dt_str = profile["birth_dt"].strftime("%d.%m.%Y")
    time_str = profile["birth_dt"].strftime("%H:%M")
    text = t("profile_card_header", lang,
             name=profile.get('profile_name', 'Мой гороскоп'),
             dob=dt_str,
             tob=time_str,
             place=profile.get('place_name', ''),
             lat=profile.get('lat', 0.0),
             lon=profile.get('lon', 0.0),
             tz=profile.get('tz_offset', 0.0))
    keyboard = get_chart_inline_keyboard(lang)
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления профилями пользователя."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profiles = get_user_profiles(user_id)
    if not profiles:
        text = t("profile_card_empty", lang)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t("btn_show_chart", lang), callback_data="prof_add_start")],
        ])
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return

    lines = [t("profile_list_header", lang, count=len(profiles))]
    for i, p in enumerate(profiles, 1):
        status = t("profile_active_badge", lang) if p["is_active"] else t("profile_other_badge", lang)
        dt_str = p["birth_dt"].strftime("%d.%m.%Y %H:%M")
        lines.append(f"{i}. {status} *{p['profile_name']}*\n   📅 {dt_str} | 📍 {p['place_name']}")

    lines.append(t("profile_action_prompt", lang))

    keyboard = get_profile_management_keyboard(lang, profiles)
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=keyboard)


async def mydata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сохранённые данные активного профиля."""
    user_id = update.effective_user.id
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("mydata_empty", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    all_profs = get_user_profiles(user_id)
    text = t(
        "mydata_card",
        lang,
        name=profile.get('profile_name', t('default_profile_name', lang)),
        dob=profile['birth_dt'].strftime('%d.%m.%Y'),
        tob=profile['birth_dt'].strftime('%H:%M'),
        place=profile['place_name'],
        lat=profile['lat'],
        lon=profile['lon'],
        tz=profile['tz_offset'],
        count=len(all_profs),
    )
    keyboard = get_mydata_inline_keyboard(lang)
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить сохранённые данные или профили."""
    user_id = update.effective_user.id
    lang = get_user_lang(update, context)
    profiles = get_user_profiles(user_id)
    if not profiles:
        context.user_data.clear()
        await update.effective_message.reply_text(
            t("reset_empty", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    text = t("reset_prompt", lang, count=len(profiles))
    keyboard = get_reset_inline_keyboard(lang)
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переименовать активный астрологический профиль."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("no_profile_found", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    text = update.message.text.strip() if update.message and update.message.text else ""
    args = re.sub(r"^/rename\b\s*", "", text, flags=re.IGNORECASE).strip()
    if not args:
        await update.effective_message.reply_text(
            t("rename_prompt_usage", lang, name=profile['profile_name']),
            parse_mode="Markdown"
        )
        return

    if len(args) > 50:
        await update.effective_message.reply_text(t("rename_too_long", lang))
        return

    if rename_profile(profile["id"], user_id, args):
        updated = get_profile_by_id(profile["id"], user_id)
        if context is not None and context.user_data is not None:
            context.user_data["natal_profile"] = updated
        await update.effective_message.reply_text(
            t("rename_success", lang, name=args),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(t("btn_show_chart", lang), callback_data="prof_view_active"),
                    InlineKeyboardButton(t("btn_all_profiles", lang), callback_data="prof_menu"),
                ]
            ])
        )
    else:
        await update.effective_message.reply_text(t("rename_fail", lang))


async def cleanup_profiles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить дубликаты и неактуальные профили (/cleanprofiles, /cleanup, /dedup)."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    deleted = cleanup_duplicate_profiles(user_id)
    active = get_user_natal_profile(user_id, context)
    active_name = active["profile_name"] if active else t("default_profile_name", lang)
    if deleted > 0:
        msg = t("duplicates_cleaned", lang, count=deleted, name=active_name)
    else:
        msg = t("duplicates_none", lang)
    profiles = get_user_profiles(user_id)
    await update.effective_message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=get_profile_management_keyboard(lang, profiles)
    )


def get_admin_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопки панели администратора."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Обновить данные", callback_data="admin_refresh"),
            InlineKeyboardButton("🧪 Тестовый платёж (1 ⭐️)", callback_data="admin_test_pay"),
        ],
        [
            InlineKeyboardButton("📁 Скачать profiles.json", callback_data="admin_get_backup"),
        ],
    ])


def format_admin_panel() -> str:
    """Форматирование текста панели администратора."""
    stats = get_system_stats()
    status_pay = "🟢 Платный (XTR Stars)" if PAYMENT_REQUIRED else "🟡 Бесплатный (Демо-режим)"
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    server_status = (
        f"🟢 Render Cloud (`{render_url}`)\n• Self-Pinger: *🟢 Активен (каждые 9 мин)*"
        if render_url
        else "💻 Локальный запуск (Localhost)\n• Self-Pinger: *⚪️ Не требуется*"
    )

    recent_text = ""
    if stats["recent_profiles"]:
        for p in stats["recent_profiles"]:
            name = p.get("profile_name") or "Без имени"
            city = p.get("place_name") or "Не указан"
            created = (p.get("created_at") or "")[:10]
            recent_text += f"• *{name}* ({city}) — `{created}`\n"
    else:
        recent_text = "_Пока нет сохранённых профилей_\n"

    return (
        "👑 *Панель администратора Джьотиш-Бота*\n\n"
        f"🖥 *Сервер и статус работы:*\n"
        f"• Окружение: {server_status}\n\n"
        f"👥 *Пользователи и профили:*\n"
        f"• Уникальных пользователей: *{stats['total_users']}*\n"
        f"• Всего создано карт/профилей: *{stats['total_profiles']}*\n\n"
        f"💳 *Статус монетизации:*\n"
        f"• Текущий режим: *{status_pay}*\n"
        f"• `PAYMENT_REQUIRED = {PAYMENT_REQUIRED}`\n"
        f"• Тарифы: Карта `{PRICE_CHART_STARS}⭐️`, Даша `{PRICE_DASHA_STARS}⭐️`, "
        f"Совместимость `{PRICE_COMPAT_STARS}⭐️`, Вопрос `{PRICE_ASK_STARS}⭐️`\n\n"
        f"📋 *Последние профили в базе:*\n{recent_text}\n"
        "💡 _Чтобы включить платный приём платежей на Render, установи в Environment Variables:_ "
        "`PAYMENT_REQUIRED=true`"
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора бота (доступна только создателю)."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    if user_id != ADMIN_USER_ID:
        await update.effective_message.reply_text("⛔️ Команда доступна только администратору бота.")
        return

    text = format_admin_panel()
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_inline_keyboard()
    )


# ===================== ДИАЛОГ СОСТАВЛЕНИЯ КАРТЫ =====================

def resolve_profile_target(
    user_id: int,
    parsed_name: Optional[str],
    active_profile: Optional[dict],
    existing_profiles: List[dict],
    lang: str = "ru",
    user_first_name: Optional[str] = None
) -> tuple[str, Optional[int]]:
    """
    Определяет целевое имя профиля и editing_id для расчёта натальной карты.
    Предотвращает ошибочное создание дубликатов («Профиль 2»), когда пользователь
    исправляет опечатку в дате/времени/городе своего текущего профиля.
    
    Возвращает (profile_name, editing_id):
      - editing_id is not None -> обновляет существующий профиль с данным id
      - editing_id is None -> создает новый профиль
    """
    if not existing_profiles:
        name = parsed_name or t("default_profile_name", lang)
        return name, None

    if not parsed_name:
        # Имя не указано (пользователь ввёл только дату, время, город) -> обновление активного профиля!
        target = active_profile or existing_profiles[0]
        return target["profile_name"], target["id"]

    # Имя указано явно. Проверяем, есть ли уже профиль с таким именем
    clean_parsed = parsed_name.strip().lower()
    match = next(
        (p for p in existing_profiles if p["profile_name"].strip().lower() == clean_parsed),
        None
    )
    if match:
        return match["profile_name"], match["id"]

    # Проверяем совпадение с именем пользователя в Telegram
    first_name_match = user_first_name.strip().lower() if user_first_name else None
    is_user_self = bool(
        first_name_match
        and (clean_parsed == first_name_match or clean_parsed in first_name_match or first_name_match in clean_parsed)
    )

    # Набор стандартных системных имен профилей
    default_names = {
        "мой гороскоп", "my horoscope", "mio oroscopo",
        "профиль 1", "профиль 2", "профиль 3", "профиль",
        "profile 1", "profile 2", "profile 3", "profile",
        "profilo 1", "profilo 2", "profilo 3", "profilo",
        "user"
    }

    target = active_profile or existing_profiles[0]
    target_name_clean = target["profile_name"].strip().lower()
    target_is_default = (
        target_name_clean in default_names
        or bool(re.match(r'^(?:профиль|profile|profilo)\s*\d+$', target_name_clean))
    )

    # Если активный профиль имеет стандартное имя (например, "Мой гороскоп" или "Профиль 2")
    # ИЛИ пользователь указал своё имя (first_name_match), обновляем активный профиль и задаем ему новое имя!
    if target_is_default or is_user_self:
        return parsed_name, target["id"]

    # Если у пользователя ровно 1 профиль (любой), обновляем его единственный профиль и переименовываем
    if len(existing_profiles) == 1:
        return parsed_name, existing_profiles[0]["id"]

    # Иначе — создаём новый профиль с указанным именем
    return parsed_name, None


async def process_and_save_chart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    profile_name: Optional[str],
    dob: date,
    tob: time,
    place_input: str,
    editing_id: Optional[int] = None
) -> int:
    """Единая функция вычисления, сохранения и отображения натальной карты."""
    lang = get_user_lang(update, context)
    dt = datetime.combine(dob, tob)
    status_msg = await update.effective_message.reply_text(t("resolving_city", lang))

    try:
        lat, lon, tz_offset, address = resolve_location(place_input, target_date=dt)
    except Exception as e:
        if context is not None and context.user_data is not None:
            context.user_data["temp_dob"] = dob
            context.user_data["temp_tob"] = tob
            if profile_name:
                context.user_data["temp_profile_name"] = profile_name
            context.user_data["editing_profile_id"] = editing_id

        await status_msg.edit_text(t("city_not_found", lang, city=place_input, err=e))
        return WAITING_PLACE

    await status_msg.edit_text(t("computing_chart", lang))

    try:
        user_id = (
            update.effective_user.id
            if update.effective_user
            else (update.callback_query.from_user.id if update.callback_query else 0)
        )
        lang = get_user_lang(update, context)
        first_name = update.effective_user.first_name if update.effective_user else "User"
        chart_name = profile_name or first_name or "User"
        chart_data = compute_chart(
            birth_dt=dt,
            lat=lat,
            lon=lon,
            tz_offset=tz_offset,
            name=chart_name
        )
        summary = format_chart_summary(chart_data, lang=lang)

        # Сохраняем в базу данных SQLite (jyotish.db)
        if not profile_name:
            if editing_id:
                existing_p = get_profile_by_id(editing_id, user_id)
                if existing_p:
                    profile_name = existing_p["profile_name"]
            if not profile_name:
                existing = get_user_profiles(user_id)
                if not existing:
                    profile_name = "Мой гороскоп" if lang == "ru" else ("My Horoscope" if lang == "en" else "Mio Oroscopo")
                else:
                    profile_name = f"Профиль {len(existing) + 1}"

        saved_id = save_profile(
            user_id=user_id,
            profile_name=profile_name,
            birth_dt=dt,
            place_name=place_input,
            resolved_address=address,
            lat=lat,
            lon=lon,
            tz_offset=tz_offset,
            chart_data=chart_data,
            summary=summary,
            set_as_active=True,
            profile_id=editing_id,
        )

        saved_profile = get_profile_by_id(saved_id, user_id)
        if context is not None and context.user_data is not None:
            context.user_data["natal_profile"] = saved_profile
            context.user_data.pop("temp_dob", None)
            context.user_data.pop("temp_tob", None)
            context.user_data.pop("temp_profile_name", None)
            context.user_data.pop("editing_profile_id", None)

        # Отправляем астрономический расчёт бесплатно всем
        await status_msg.delete()

        # Генерируем и отправляем графическую карту Кундли D1
        try:
            chart_img = render_kundli_chart(
                chart_data=chart_data,
                profile_name=profile_name,
                dob_str=dob.strftime("%d.%m.%Y"),
                tob_str=tob.strftime("%H:%M"),
                place_str=place_input,
                lang=lang,
            )
            caption_text = {
                "ru": f"🔮 *Ведическая карта Кундли (D1): {profile_name}*",
                "en": f"🔮 *Vedic Kundli Chart (D1): {profile_name}*",
                "it": f"🔮 *Carta Vedica Kundli (D1): {profile_name}*",
            }.get(lang, f"🔮 *Ведическая карта Кундли (D1): {profile_name}*")
            await update.effective_message.reply_photo(
                photo=chart_img,
                caption=caption_text,
                parse_mode="Markdown"
            )
        except Exception as img_err:
            logger.warning(f"Не удалось отправить изображение карты: {img_err}")

        if editing_id:
            header = t("profile_updated_header", lang, name=profile_name)
        else:
            header = {
                "ru": f"🎉 *Профиль «{profile_name}» сохранён в базу!*\n\n",
                "en": f"🎉 *Profile '{profile_name}' saved to database!*\n\n",
                "it": f"🎉 *Profilo '{profile_name}' salvato nel database!*\n\n",
            }.get(lang, f"🎉 *Профиль «{profile_name}» сохранён в базу!*\n\n")
        await send_split_message(update, header + summary)

    except Exception as e:
        logger.exception("Ошибка расчёта карты")
        await status_msg.edit_text(t("chart_error", lang, err=e))
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        no_key_text = {
            "ru": "ℹ️ *Астрономический расчёт готов!*\n\nДля подключения глубокой текстовой трактовки карты от ИИ добавь `GEMINI_API_KEY` в файл `.env`.",
            "en": "ℹ️ *Astronomical calculations complete!*\n\nTo enable in-depth AI chart readings, add `GEMINI_API_KEY` to `.env`.",
            "it": "ℹ️ *Calcolo astronomico completato!*\n\nPer attivare le interpretazioni approfondite dell'IA, aggiungi `GEMINI_API_KEY` a `.env`.",
        }.get(lang, "ℹ️ *Астрономический расчёт готов!*\n\nДля подключения глубокой текстовой трактовки карты от ИИ добавь `GEMINI_API_KEY` в файл `.env`.")
        await update.effective_message.reply_text(
            no_key_text,
            parse_mode="Markdown",
            reply_markup=get_chart_inline_keyboard(lang)
        )
        return ConversationHandler.END

    # Проверка монетизации (если включен платный режим)
    has_paid = context.user_data.get("paid_chart", False) if context and context.user_data else False
    if PAYMENT_REQUIRED and not has_paid:
        pay_prompt = {
            "ru": (
                "🌟 *Натальная карта успешно построена!*\n\n"
                "Хочешь получить подробную расшифровку судьбы, предназначения, сильных сторон и кармических уроков от ИИ-астролога?\n"
                f"Стоимость разбора: **{PRICE_CHART_STARS} ⭐️**"
            ),
            "en": (
                "🌟 *Natal chart successfully created!*\n\n"
                "Want a comprehensive reading of your destiny, purpose, strengths, and life lessons from the AI Astrologer?\n"
                f"Price: **{PRICE_CHART_STARS} ⭐️**"
            ),
            "it": (
                "🌟 *Carta natale calcolata con successo!*\n\n"
                "Vuoi un'interpretazione dettagliata di destino, vocazione e lezioni karmiche dall'astrologo IA?\n"
                f"Prezzo: **{PRICE_CHART_STARS} ⭐️**"
            ),
        }.get(lang, (
            "🌟 *Натальная карта успешно построена!*\n\n"
            "Хочешь получить подробную расшифровку судьбы, предназначения, сильных сторон и кармических уроков от ИИ-астролога?\n"
            f"Стоимость разбора: **{PRICE_CHART_STARS} ⭐️**"
        ))
        await update.effective_message.reply_text(
            pay_prompt,
            parse_mode="Markdown",
            reply_markup=get_chart_inline_keyboard(lang)
        )
        await send_chart_invoice(update, context, lang=lang)
        return ConversationHandler.END

    # Если оплачено или в бесплатном режиме:
    ai_status_text = {
        "ru": "🔮 ИИ-Астролог составляет подробную трактовку твоей карты...",
        "en": "🔮 AI Astrologer is compiling a detailed reading of your chart...",
        "it": "🔮 L'astrologo IA sta redigendo l'interpretazione dettagliata della tua carta...",
    }.get(lang, "🔮 ИИ-Астролог составляет подробную трактовку твоей карты...")
    ai_status = await update.effective_message.reply_text(ai_status_text)
    try:
        interpretation = await gemini.interpret_chart(chart_data, summary, lang=lang)
        await ai_status.delete()
        res_header = {
            "ru": "📜 *Интерпретация карты от ИИ:*\n\n",
            "en": "📜 *AI Chart Interpretation:*\n\n",
            "it": "📜 *Interpretazione della Carta con IA:*\n\n",
        }.get(lang, "📜 *Интерпретация карты от ИИ:*\n\n")
        await send_split_message(
            update,
            res_header + interpretation,
            reply_markup=get_chart_inline_keyboard(lang)
        )
    except Exception as e:
        logger.exception("Ошибка генерации Gemini")
        await ai_status.edit_text(f"⚠️ Не удалось получить ответ ИИ: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_chart_inline_keyboard(lang)
        )

    return ConversationHandler.END


async def chart_one_line_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прямой ввод всех данных одной строкой без предварительного вызова команды."""
    text = update.message.text.strip() if update.message and isinstance(getattr(update.message, "text", None), str) else ""
    parsed = parse_one_line_profile(text)
    if not parsed or not parsed.get("is_complete"):
        return ConversationHandler.END

    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    active = get_user_natal_profile(user_id, context)
    existing = get_user_profiles(user_id)
    first_name = update.effective_user.first_name if update.effective_user else None

    name, editing_id = resolve_profile_target(
        user_id=user_id,
        parsed_name=parsed.get("name"),
        active_profile=active,
        existing_profiles=existing,
        lang=lang,
        user_first_name=first_name
    )

    return await process_and_save_chart(
        update=update,
        context=context,
        profile_name=name,
        dob=parsed["dob"],
        tob=parsed["tob"],
        place_input=parsed["city"],
        editing_id=editing_id
    )


async def newprofile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /newprofile: начало создания дополнительного профиля."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    context.user_data["editing_profile_id"] = None

    msg_text = update.message.text.strip() if update.message and isinstance(getattr(update.message, "text", None), str) else ""
    cmd_args = re.sub(r"^/newprofile\b\s*", "", msg_text, flags=re.IGNORECASE).strip()
    if cmd_args:
        parsed = parse_one_line_profile(cmd_args)
        if parsed and parsed.get("is_complete"):
            name = parsed.get("name")
            if not name:
                existing = get_user_profiles(user_id)
                name = t("profile_indexed_name", lang, index=len(existing) + 1)
            return await process_and_save_chart(
                update=update,
                context=context,
                profile_name=name,
                dob=parsed["dob"],
                tob=parsed["tob"],
                place_input=parsed["city"],
                editing_id=None
            )

    await update.effective_message.reply_text(
        t("newprofile_intro", lang),
        parse_mode="Markdown"
    )
    return WAITING_PROFILE_NAME


async def newprofile_callback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажатие инлайн-кнопки «➕ Добавить профиль»."""
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(update, context)
    context.user_data["editing_profile_id"] = None
    await query.message.reply_text(
        t("newprofile_intro", lang),
        parse_mode="Markdown"
    )
    return WAITING_PROFILE_NAME


async def recalc_callback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажатие инлайн-кнопки «✏️ Изменить данные» или «🔄 Пересчитать»."""
    query = update.callback_query
    await query.answer()
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)

    prof_id = None
    data = query.data or ""
    if data.startswith("prof_edit_"):
        try:
            prof_id = int(data.split("prof_edit_")[1])
        except ValueError:
            prof_id = None
    elif data.startswith("prof_recalc_") and data != "prof_recalc_start":
        try:
            prof_id = int(data.split("prof_recalc_")[1])
        except ValueError:
            prof_id = None

    target = None
    if prof_id is not None:
        target = get_profile_by_id(prof_id, user_id)

    if not target:
        target = get_user_natal_profile(user_id, context)

    name = target["profile_name"] if target else t("default_profile_name", lang)
    context.user_data["temp_profile_name"] = name
    context.user_data["editing_profile_id"] = target["id"] if target else None

    await query.message.reply_text(
        t("recalc_intro", lang, name=name),
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /edit или /recalc: редактирование/пересчёт активного или выбранного профиля."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    existing_profiles = get_user_profiles(user_id)
    if not existing_profiles:
        await update.effective_message.reply_text(
            t("no_profile_found", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return ConversationHandler.END

    msg_text = update.message.text.strip() if update.message and isinstance(getattr(update.message, "text", None), str) else ""
    cmd_args = re.sub(r"^/(?:edit|recalc|editprofile|update)\b\s*", "", msg_text, flags=re.IGNORECASE).strip()

    target_profile = get_user_natal_profile(user_id, context) or existing_profiles[0]

    # Если первым словом указан номер профиля или его имя (например "/edit 2" или "/edit Сюзанна"):
    if cmd_args:
        first_token = cmd_args.split()[0]
        matched_p = get_profile_by_name_or_index(user_id, first_token)
        if matched_p:
            target_profile = matched_p
            cmd_args = cmd_args[len(first_token):].strip(" ,;:\t\n-")

    editing_id = target_profile["id"]
    name = target_profile.get("profile_name", t("default_profile_name", lang))
    context.user_data["editing_profile_id"] = editing_id
    context.user_data["temp_profile_name"] = name

    if cmd_args:
        parsed = parse_one_line_profile(cmd_args)
        if parsed and parsed.get("dob"):
            new_dob = parsed["dob"]
            new_tob = parsed.get("tob")
            new_city = parsed.get("city")
            prof_name = parsed.get("name") or name

            # Если время или город не указаны в строке /edit, сохраняем существующие из профиля
            if not new_tob and target_profile.get("birth_dt"):
                new_tob = target_profile["birth_dt"].time()
            if not new_city and target_profile.get("place_name"):
                new_city = target_profile["place_name"]

            if new_dob and new_tob and new_city:
                return await process_and_save_chart(
                    update=update,
                    context=context,
                    profile_name=prof_name,
                    dob=new_dob,
                    tob=new_tob,
                    place_input=new_city,
                    editing_id=editing_id
                )
            else:
                context.user_data["temp_dob"] = new_dob
                if new_tob:
                    context.user_data["temp_tob"] = new_tob
                    await update.effective_message.reply_text(t("step3_prompt", lang), parse_mode="Markdown")
                    return WAITING_PLACE
                else:
                    await update.effective_message.reply_text(t("step2_prompt", lang), parse_mode="Markdown")
                    return WAITING_TOB

    await update.effective_message.reply_text(
        t("recalc_intro", lang, name=name),
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def profile_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение имени нового профиля или полной строки с данными."""
    text = update.message.text.strip()
    if is_cancel_input(text):
        return await cancel_command(update, context)

    lang = get_user_lang(update, context)
    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or t("default_profile_name", lang)
        editing_id = context.user_data.get("editing_profile_id")
        return await process_and_save_chart(
            update=update,
            context=context,
            profile_name=name,
            dob=parsed["dob"],
            tob=parsed["tob"],
            place_input=parsed["city"],
            editing_id=editing_id
        )

    if parsed and parsed.get("dob"):
        name = parsed.get("name") or t("default_profile_name", lang)
        context.user_data["temp_profile_name"] = name
        context.user_data["temp_dob"] = parsed["dob"]
        if parsed.get("tob"):
            context.user_data["temp_tob"] = parsed["tob"]
            await update.message.reply_text(
                t("step3_prompt", lang),
                parse_mode="Markdown"
            )
            return WAITING_PLACE
        await update.message.reply_text(
            t("step2_prompt", lang),
            parse_mode="Markdown"
        )
        return WAITING_TOB

    if not text or len(text) > 50:
        await update.message.reply_text(t("invalid_name_prompt", lang))
        return WAITING_PROFILE_NAME

    context.user_data["temp_profile_name"] = text
    await update.message.reply_text(
        t("name_saved_prompt", lang, name=text),
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def chart_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало составления натальной карты."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)

    msg_text = update.message.text.strip() if update.message and isinstance(getattr(update.message, "text", None), str) else ""
    cmd_args = re.sub(r"^/(?:chart|natal)\b\s*", "", msg_text, flags=re.IGNORECASE).strip()
    if cmd_args:
        parsed = parse_one_line_profile(cmd_args)
        if parsed and parsed.get("is_complete"):
            active = get_user_natal_profile(user_id, context)
            existing = get_user_profiles(user_id)
            first_name = update.effective_user.first_name if update.effective_user else None
            name, editing_id = resolve_profile_target(
                user_id=user_id,
                parsed_name=parsed.get("name"),
                active_profile=active,
                existing_profiles=existing,
                lang=lang,
                user_first_name=first_name
            )
            return await process_and_save_chart(
                update=update,
                context=context,
                profile_name=name,
                dob=parsed["dob"],
                tob=parsed["tob"],
                place_input=parsed["city"],
                editing_id=editing_id
            )

    active_profile = get_user_natal_profile(user_id, context)
    if active_profile:
        await show_active_profile_card(update, context, active_profile)
        return ConversationHandler.END

    context.user_data["temp_profile_name"] = t("default_profile_name", lang)
    context.user_data["editing_profile_id"] = None

    await update.effective_message.reply_text(
        t("chart_intro", lang),
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def chart_dob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты рождения или строки с полными данными."""
    text = update.message.text.strip()
    if is_cancel_input(text):
        return await cancel_command(update, context)

    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    editing_id = context.user_data.get("editing_profile_id")

    # Если пользователь хочет оставить текущую дату при редактировании:
    if is_keep_input(text) and editing_id:
        target = get_profile_by_id(editing_id, user_id)
        if target and target.get("birth_dt"):
            context.user_data["temp_dob"] = target["birth_dt"].date()
            await update.message.reply_text(
                t("step2_prompt", lang),
                parse_mode="Markdown"
            )
            return WAITING_TOB

    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or context.user_data.get("temp_profile_name")
        return await process_and_save_chart(
            update=update,
            context=context,
            profile_name=name,
            dob=parsed["dob"],
            tob=parsed["tob"],
            place_input=parsed["city"],
            editing_id=editing_id
        )

    if parsed and parsed.get("dob"):
        if parsed.get("name"):
            context.user_data["temp_profile_name"] = parsed["name"]
        context.user_data["temp_dob"] = parsed["dob"]
        if parsed.get("tob"):
            context.user_data["temp_tob"] = parsed["tob"]
            await update.message.reply_text(
                t("step3_prompt", lang),
                parse_mode="Markdown"
            )
            return WAITING_PLACE

        await update.message.reply_text(
            t("step2_prompt", lang),
            parse_mode="Markdown"
        )
        return WAITING_TOB

    try:
        dob = datetime.strptime(text, "%d.%m.%Y").date()
        context.user_data["temp_dob"] = dob
    except ValueError:
        # Если пользователь ввёл только имя (буквы, дефис, пробел, 2-50 символов без цифр)
        if re.match(r'^[A-Za-zА-Яа-яЁё\s\-]{2,50}$', text) and not any(ch.isdigit() for ch in text):
            context.user_data["temp_profile_name"] = text
            await update.message.reply_text(
                t("name_saved_prompt", lang, name=text),
                parse_mode="Markdown"
            )
            return WAITING_DOB

        await update.message.reply_text(
            t("invalid_date_format", lang),
            parse_mode="Markdown"
        )
        return WAITING_DOB

    await update.message.reply_text(
        t("step2_prompt", lang),
        parse_mode="Markdown"
    )
    return WAITING_TOB


async def chart_tob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени рождения или полной строки данных."""
    text = update.message.text.strip()
    if is_cancel_input(text):
        return await cancel_command(update, context)

    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    editing_id = context.user_data.get("editing_profile_id")

    # Если пользователь хочет оставить текущее время при редактировании:
    if is_keep_input(text) and editing_id:
        target = get_profile_by_id(editing_id, user_id)
        if target and target.get("birth_dt"):
            context.user_data["temp_tob"] = target["birth_dt"].time()
            await update.message.reply_text(
                t("step3_prompt", lang),
                parse_mode="Markdown"
            )
            return WAITING_PLACE

    # Проверяем, не ввёл ли пользователь полную строку данных
    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or context.user_data.get("temp_profile_name")
        return await process_and_save_chart(
            update=update,
            context=context,
            profile_name=name,
            dob=parsed["dob"],
            tob=parsed["tob"],
            place_input=parsed["city"],
            editing_id=editing_id
        )

    try:
        tob = datetime.strptime(text, "%H:%M").time()
        context.user_data["temp_tob"] = tob
    except ValueError:
        if parsed and parsed.get("tob"):
            context.user_data["temp_tob"] = parsed["tob"]
        else:
            time_match = re.search(r'\b([01]?\d|2[0-3])[:.]([0-5]\d)\b', text)
            if time_match:
                context.user_data["temp_tob"] = time(int(time_match.group(1)), int(time_match.group(2)))
            else:
                await update.message.reply_text(
                    t("invalid_time_format", lang),
                    parse_mode="Markdown"
                )
                return WAITING_TOB

    await update.message.reply_text(
        t("step3_prompt", lang),
        parse_mode="Markdown"
    )
    return WAITING_PLACE


async def chart_place_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение города, геокодинг, расчёт карты и генерация ИИ-интерпретации."""
    place_input = update.message.text.strip()
    if is_cancel_input(place_input):
        return await cancel_command(update, context)

    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    editing_id = context.user_data.get("editing_profile_id")

    # Если пользователь хочет оставить текущий город при редактировании:
    if is_keep_input(place_input) and editing_id:
        target = get_profile_by_id(editing_id, user_id)
        if target and target.get("place_name"):
            place_input = target["place_name"]

    # Проверяем, не ввёл ли пользователь полную строку данных
    parsed = parse_one_line_profile(place_input)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or context.user_data.get("temp_profile_name")
        return await process_and_save_chart(
            update=update,
            context=context,
            profile_name=name,
            dob=parsed["dob"],
            tob=parsed["tob"],
            place_input=parsed["city"],
            editing_id=editing_id
        )

    dob = context.user_data.get("temp_dob")
    tob = context.user_data.get("temp_tob")

    if not dob or not tob:
        await update.message.reply_text(t("session_error", lang))
        return ConversationHandler.END

    profile_name = context.user_data.get("temp_profile_name")
    editing_id = context.user_data.get("editing_profile_id")
    return await process_and_save_chart(
        update=update,
        context=context,
        profile_name=profile_name,
        dob=dob,
        tob=tob,
        place_input=place_input,
        editing_id=editing_id
    )



# ===================== КОМАНДА ДАША (ПЕРИОДЫ) =====================

async def dasha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать и интерпретировать периоды жизни Вимшоттари Даша."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("dasha_need_chart", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    chart_data = profile["chart_data"]
    summary = profile["summary"]
    dasha_raw = format_dasha_periods(chart_data, lang=lang)
    prof_title = {
        "ru": f"👤 *Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»*\n\n",
        "en": f"👤 *Profile: '{profile.get('profile_name', 'My Horoscope')}'*\n\n",
        "it": f"👤 *Profilo: '{profile.get('profile_name', 'Mio Oroscopo')}'*\n\n",
    }.get(lang, f"👤 *Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»*\n\n")
    dasha_text = prof_title + dasha_raw

    gemini = get_gemini_client()
    if not gemini:
        await send_split_message(update, dasha_text, reply_markup=get_dasha_inline_keyboard(lang))
        hint = {
            "ru": "💡 Чтобы получить анализ текущего периода жизни от ИИ, добавь `GEMINI_API_KEY` в файл `.env`.",
            "en": "💡 To get AI analysis of your current life period, add `GEMINI_API_KEY` to `.env`.",
            "it": "💡 Per ricevere l'analisi del periodo di vita dall'IA, aggiungi `GEMINI_API_KEY` a `.env`.",
        }.get(lang, "💡 Чтобы получить анализ текущего периода жизни от ИИ, добавь `GEMINI_API_KEY` в файл `.env`.")
        await update.effective_message.reply_text(
            hint,
            reply_markup=get_dasha_inline_keyboard(lang)
        )
        return

    has_paid = context.user_data.get("paid_dasha", False)
    if PAYMENT_REQUIRED and not has_paid:
        await send_split_message(update, dasha_text)
        pay_prompt = {
            "ru": (
                "⏳ *Периоды рассчитаны!*\n\n"
                "Чтобы получить глубокий анализ текущего планетного периода (Маха-Даша и Антар-Даша) от ИИ с рекомендациями упай:\n"
                f"Стоимость разбора: **{PRICE_DASHA_STARS} ⭐️**"
            ),
            "en": (
                "⏳ *Periods calculated!*\n\n"
                "To get an in-depth AI analysis of your current planetary period (Maha Dasha & Antar Dasha) with remedies:\n"
                f"Price: **{PRICE_DASHA_STARS} ⭐️**"
            ),
            "it": (
                "⏳ *Periodi calcolati!*\n\n"
                "Per ricevere un'analisi approfondita del periodo planetario attuale (Maha Dasha e Antar Dasha) dall'IA:\n"
                f"Prezzo: **{PRICE_DASHA_STARS} ⭐️**"
            ),
        }.get(lang, (
            "⏳ *Периоды рассчитаны!*\n\n"
            "Чтобы получить глубокий анализ текущего планетного периода (Маха-Даша и Антар-Даша) от ИИ с рекомендациями упай:\n"
            f"Стоимость разбора: **{PRICE_DASHA_STARS} ⭐️**"
        ))
        await update.effective_message.reply_text(
            pay_prompt,
            parse_mode="Markdown",
            reply_markup=get_dasha_inline_keyboard(lang)
        )
        await send_dasha_invoice(update, context, lang=lang)
        return

    await send_split_message(update, dasha_text)
    status_text = {
        "ru": "🔮 Анализирую текущий период жизни через ИИ...",
        "en": "🔮 Analyzing current life period with AI...",
        "it": "🔮 Analisi del periodo di vita attuale tramite IA...",
    }.get(lang, "🔮 Анализирую текущий период жизни через ИИ...")
    status_msg = await update.effective_message.reply_text(status_text)
    try:
        interpretation = await gemini.interpret_dasha(chart_data, summary, lang=lang)
        await status_msg.delete()
        res_header = {
            "ru": "🌟 *Анализ текущего периода жизни:*\n\n",
            "en": "🌟 *Current Life Period Analysis:*\n\n",
            "it": "🌟 *Analisi del periodo di vita attuale:*\n\n",
        }.get(lang, "🌟 *Анализ текущего периода жизни:*\n\n")
        await send_split_message(
            update,
            res_header + interpretation,
            reply_markup=get_dasha_inline_keyboard(lang)
        )
    except Exception as e:
        logger.exception("Ошибка анализа даша")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе даша: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_dasha_inline_keyboard(lang)
        )


# ===================== ДИАЛОГ СОВМЕСТИМОСТИ =====================

def format_kuja_compatibility(chart1: dict, chart2: dict, name1: str = "Партнёр 1", name2: str = "Партнёр 2", lang: str = "ru") -> str:
    """Сравнительный анализ поражения Марсом (Куджа-Доша / Манглика) для обоих партнёров."""
    lang = normalize_language(lang)
    k1 = check_kuja_dosha(chart1)
    k2 = check_kuja_dosha(chart2)
    has1 = k1.get("has_dosha", False)
    has2 = k2.get("has_dosha", False)

    sign1 = get_sign_name(k1.get("mars_sign", "Aries"), lang=lang)
    sign2 = get_sign_name(k2.get("mars_sign", "Aries"), lang=lang)

    if lang == "en":
        lines = ["🔥 *Kuja Dosha Analysis (Manglik in relationships):*"]
        desc1 = f"• *{name1}*: Mars in house {k1.get('mars_house')} ({sign1}). "
        if has1:
            desc1 += "⚠️ Kuja Dosha is present (high passion and demanding nature)."
        elif k1.get("is_cancelled"):
            desc1 += f"✅ Manglik is neutralized ({k1.get('cancel_reason')})."
        else:
            desc1 += "✅ Kuja Dosha is absent."
        lines.append(desc1)

        desc2 = f"• *{name2}*: Mars in house {k2.get('mars_house')} ({sign2}). "
        if has2:
            desc2 += "⚠️ Kuja Dosha is present."
        elif k2.get("is_cancelled"):
            desc2 += f"✅ Manglik is neutralized ({k2.get('cancel_reason')})."
        else:
            desc2 += "✅ Kuja Dosha is absent."
        lines.append(desc2)

        if has1 and has2:
            lines.append("✨ *Summary:* Both partners have Manglik energy — they balance each other out (mutual neutralization)!")
        elif not has1 and not has2:
            lines.append("✨ *Summary:* Neither partner has Mars affliction — harmonious and calm astrological background.")
        else:
            lines.append("⚠️ *Summary:* One-sided Kuja Dosha. Requires gentleness to partner's emotions, joint sports, and patience during the first year of living together.")
        return "\n".join(lines)

    elif lang == "it":
        lines = ["🔥 *Analisi Kuja Dosha (Manglik nelle relazioni):*"]
        desc1 = f"• *{name1}*: Marte nella casa {k1.get('mars_house')} ({sign1}). "
        if has1:
            desc1 += "⚠️ Kuja Dosha presente (forte passionalità ed elevate aspettative)."
        elif k1.get("is_cancelled"):
            desc1 += f"✅ Manglik neutralizzato ({k1.get('cancel_reason')})."
        else:
            desc1 += "✅ Kuja Dosha assente."
        lines.append(desc1)

        desc2 = f"• *{name2}*: Marte nella casa {k2.get('mars_house')} ({sign2}). "
        if has2:
            desc2 += "⚠️ Kuja Dosha presente."
        elif k2.get("is_cancelled"):
            desc2 += f"✅ Manglik neutralizzato ({k2.get('cancel_reason')})."
        else:
            desc2 += "✅ Kuja Dosha assente."
        lines.append(desc2)

        if has1 and has2:
            lines.append("✨ *Conclusione:* Entrambi i partner possiedono l'energia Manglik — si equilibrano a vicenda (neutralizzazione reciproca)!")
        elif not has1 and not has2:
            lines.append("✨ *Conclusione:* Nessuna afflizione di Marte — sfondo astrologico armonioso e sereno.")
        else:
            lines.append("⚠️ *Conclusione:* Kuja Dosha unilaterale. Si raccomanda delicatezza verso le emozioni del partner, attività sportiva insieme e pazienza durante il primo anno di convivenza.")
        return "\n".join(lines)

    # Russian (default)
    lines = ["🔥 *Анализ Куджа-Доши (Манглика в отношениях):*"]
    desc1 = f"• *{name1}*: Марс в доме {k1.get('mars_house')} ({k1.get('mars_sign_ru') or sign1}). "
    if has1:
        desc1 += "⚠️ Присутствует Куджа-Доша (повышенная страстность и требовательность)."
    elif k1.get("is_cancelled"):
        desc1 += f"✅ Манглика нейтрализована ({k1.get('cancel_reason')})."
    else:
        desc1 += "✅ Куджа-Доша отсутствует."
    lines.append(desc1)

    desc2 = f"• *{name2}*: Марс в доме {k2.get('mars_house')} ({k2.get('mars_sign_ru') or sign2}). "
    if has2:
        desc2 += "⚠️ Присутствует Куджа-Доша."
    elif k2.get("is_cancelled"):
        desc2 += f"✅ Манглика нейтрализована ({k2.get('cancel_reason')})."
    else:
        desc2 += "✅ Куджа-Доша отсутствует."
    lines.append(desc2)

    if has1 and has2:
        lines.append("✨ *Итог:* Оба партнёра обладают энергией Манглика — энергии уравновешивают друг друга (взаимная нейтрализация)!")
    elif not has1 and not has2:
        lines.append("✨ *Итог:* Поражения Марсом нет ни у кого — гармоничный и спокойный астрологический фон.")
    else:
        lines.append("⚠️ *Итог:* Односторонняя Куджа-Доша. Требуется бережность к эмоциям партнёра, совместный спорт и терпение в первый год совместной жизни.")
    return "\n".join(lines)


async def compat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало проверки совместимости."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    my_profile = get_user_natal_profile(user_id, context)
    if not my_profile:
        await update.effective_message.reply_text(
            t("compat_missing_profile", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return ConversationHandler.END

    all_profs = get_user_profiles(user_id)
    other_profs = [p for p in all_profs if p["id"] != my_profile["id"]]

    if other_profs:
        text = t(
            "compat_select_second",
            lang,
            name=my_profile['profile_name'],
            dob=my_profile['birth_dt'].strftime('%d.%m.%Y'),
            place=my_profile['place_name']
        )
        buttons = []
        for p in other_profs:
            buttons.append([InlineKeyboardButton(f"💞 {p['profile_name']} ({p['birth_dt'].strftime('%d.%m.%Y')})", callback_data=f"compat_p_{p['id']}")])
        buttons.append([InlineKeyboardButton(t("btn_manual_input", lang), callback_data="compat_p_manual")])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return COMPAT_SELECT_PARTNER

    await update.effective_message.reply_text(
        t("compat_step1_new", lang, name=my_profile['profile_name']),
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_DOB


async def compat_partner_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор партнёра из сохранённых профилей или переход к ручному вводу."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    lang = get_user_lang(update, context)
    my_profile = get_user_natal_profile(user_id, context)

    if data == "compat_p_manual":
        await query.message.reply_text(
            t("compat_partner_step1", lang),
            parse_mode="Markdown"
        )
        return COMPAT_WAITING_DOB

    if data.startswith("compat_p_"):
        partner_id = int(data.split("compat_p_")[1])
        partner_profile = get_profile_by_id(partner_id, user_id)
        if not partner_profile:
            await query.message.reply_text(t("compat_partner_not_found", lang))
            return ConversationHandler.END

        partner_chart = partner_profile["chart_data"]
        partner_summary = partner_profile["summary"]
        context.user_data["partner_chart"] = partner_chart
        context.user_data["partner_summary"] = partner_summary

        status_msg = await query.message.reply_text(
            t("compat_status_matching", lang, name1=my_profile['profile_name'], name2=partner_profile['profile_name'])
        )

        kuja_text = format_kuja_compatibility(
            my_profile["chart_data"],
            partner_chart,
            my_profile.get("profile_name", "Партнёр 1"),
            partner_profile.get("profile_name", "Партнёр 2"),
            lang=lang,
        )

        gemini = get_gemini_client()
        if not gemini:
            await status_msg.edit_text(
                t("compat_gemini_missing", lang, kuja_text=kuja_text),
                parse_mode="Markdown",
                reply_markup=get_compat_inline_keyboard(lang)
            )
            return ConversationHandler.END

        has_paid = context.user_data.get("paid_compat", False)
        if PAYMENT_REQUIRED and not has_paid:
            await status_msg.edit_text(
                f"💞 *Карты сопоставлены ({my_profile['profile_name']} + {partner_profile['profile_name']})!*\n\n"
                f"{kuja_text}\n\n"
                "Чтобы получить полный психологический и кармический анализ синастрии по 8 факторам (Аштакута) от ИИ-астролога:\n"
                f"Стоимость разбора: **{PRICE_COMPAT_STARS} ⭐️**",
                parse_mode="Markdown"
            )
            await send_compat_invoice(update, context, lang=lang)
            return ConversationHandler.END

        try:
            result = await gemini.interpret_compatibility(
                chart1_data=my_profile["chart_data"],
                chart1_summary=my_profile["summary"],
                chart2_data=partner_chart,
                chart2_summary=partner_summary,
                lang=lang,
            )
            await status_msg.delete()
            header = f"💘 *Совместимость: {my_profile['profile_name']} ❤️ {partner_profile['profile_name']}*\n\n{kuja_text}\n\n"
            await send_split_message(
                update,
                header + result,
                reply_markup=get_compat_inline_keyboard(lang)
            )
        except Exception as e:
            logger.exception("Ошибка совместимости")
            await status_msg.edit_text(f"⚠️ Ошибка при анализе: {e}")
            await update.effective_message.reply_text(
                t("choose_next_action", lang),
                reply_markup=get_compat_inline_keyboard(lang)
            )

        return ConversationHandler.END

    return ConversationHandler.END


async def compat_dob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты партнёра."""
    text = update.message.text.strip()
    if is_cancel_input(text):
        return await cancel_command(update, context)

    lang = get_user_lang(update, context)
    try:
        dob = datetime.strptime(text, "%d.%m.%Y").date()
        context.user_data["compat_dob"] = dob
    except ValueError:
        await update.message.reply_text(
            t("compat_invalid_dob", lang),
            parse_mode="Markdown"
        )
        return COMPAT_WAITING_DOB

    await update.message.reply_text(
        t("compat_partner_step2", lang),
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_TOB


async def compat_tob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени партнёра."""
    text = update.message.text.strip()
    if is_cancel_input(text):
        return await cancel_command(update, context)

    lang = get_user_lang(update, context)
    try:
        tob = datetime.strptime(text, "%H:%M").time()
        context.user_data["compat_tob"] = tob
    except ValueError:
        await update.message.reply_text(
            t("compat_invalid_tob", lang),
            parse_mode="Markdown"
        )
        return COMPAT_WAITING_TOB

    await update.message.reply_text(
        t("compat_partner_step3", lang),
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_PLACE


async def compat_place_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расчёт второй карты и сравнительный анализ."""
    place_input = update.message.text.strip()
    if is_cancel_input(place_input):
        return await cancel_command(update, context)

    lang = get_user_lang(update, context)
    dob = context.user_data.get("compat_dob")
    tob = context.user_data.get("compat_tob")
    user_id = update.effective_user.id
    my_profile = get_user_natal_profile(user_id, context)

    if not dob or not tob or not my_profile:
        await update.message.reply_text(t("compat_session_expired", lang))
        return ConversationHandler.END

    dt = datetime.combine(dob, tob)
    status_msg = await update.message.reply_text(t("compat_partner_calc_status", lang))

    try:
        lat, lon, tz_offset, address = resolve_location(place_input, target_date=dt)
        partner_chart = compute_chart(
            birth_dt=dt,
            lat=lat,
            lon=lon,
            tz_offset=tz_offset,
            name="Партнёр"
        )
        partner_summary = format_chart_summary(partner_chart, lang=lang)
        context.user_data["partner_chart"] = partner_chart
        context.user_data["partner_summary"] = partner_summary

        # Автоматически сохраняем профиль партнёра как неактивный для повторного использования
        try:
            partner_prof_name = "Партнёр"
            existing = get_user_profiles(user_id)
            names = [p["profile_name"] for p in existing]
            if partner_prof_name in names:
                partner_prof_name = f"Партнёр ({place_input})"
            save_profile(
                user_id=user_id,
                profile_name=partner_prof_name,
                birth_dt=dt,
                place_name=place_input,
                resolved_address=address,
                lat=lat,
                lon=lon,
                tz_offset=tz_offset,
                chart_data=partner_chart,
                summary=partner_summary,
                set_as_active=False,
            )
        except Exception as e_save:
            logger.warning(f"Не удалось автосохранить профиль партнёра: {e_save}")

    except Exception as e:
        await status_msg.edit_text(t("compat_city_error", lang, city=place_input, err=e))
        return ConversationHandler.END

    kuja_text = format_kuja_compatibility(
        my_profile["chart_data"],
        partner_chart,
        my_profile.get("profile_name", "Партнёр 1"),
        "Партнёр 2",
        lang=lang,
    )

    gemini = get_gemini_client()
    if not gemini:
        await status_msg.edit_text(
            t("compat_gemini_missing", lang, kuja_text=kuja_text),
            parse_mode="Markdown",
            reply_markup=get_compat_inline_keyboard(lang)
        )
        return ConversationHandler.END

    has_paid = context.user_data.get("paid_compat", False)
    if PAYMENT_REQUIRED and not has_paid:
        await status_msg.edit_text(
            f"💞 *Карты обоих партнёров построены!*\n\n"
            f"{kuja_text}\n\n"
            "Чтобы запустить детальный анализ синастрии по 8 факторам ведической гармонии (Аштакута) от ИИ:\n"
            f"Стоимость разбора: **{PRICE_COMPAT_STARS} ⭐️**",
            parse_mode="Markdown"
        )
        await send_compat_invoice(update, context, lang=lang)
        return ConversationHandler.END

    await status_msg.edit_text(t("compat_ai_matching_status", lang))
    try:
        result = await gemini.interpret_compatibility(
            chart1_data=my_profile["chart_data"],
            chart1_summary=my_profile["summary"],
            chart2_data=partner_chart,
            chart2_summary=partner_summary,
            lang=lang,
        )
        await status_msg.delete()
        header = t("compat_analysis_header", lang)
        await send_split_message(
            update,
            f"{header}{kuja_text}\n\n{result}",
            reply_markup=get_compat_inline_keyboard(lang)
        )

    except Exception as e:
        logger.exception("Ошибка совместимости")
        await status_msg.edit_text(t("compat_analysis_error", lang, err=e))
        await update.effective_message.reply_text(
            t("choose_next_action", lang),
            reply_markup=get_compat_inline_keyboard(lang)
        )

    return ConversationHandler.END


# ===================== САДЕ-САТИ (БЕСПЛАТНО) =====================

async def sadesati_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка текущего статуса Саде-Сати (транзит Сатурна по Луне)."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("need_chart_first", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    status_text = {
        "ru": "🪐 Вычисляю положение транзитного Сатурна...",
        "en": "🪐 Calculating transiting Saturn position...",
        "it": "🪐 Calcolo della posizione di Saturno in transito...",
    }.get(lang, "🪐 Вычисляю положение транзитного Сатурна...")
    status_msg = await update.effective_message.reply_text(status_text)
    try:
        chart_data = profile["chart_data"]
        result = check_sade_sati(chart_data)
        prof_name = profile.get("profile_name", "Мой гороскоп")
        prof_title = f" (Профиль: «{prof_name}»)"

        moon_sign = result.get("natal_moon_sign", "Aries")
        saturn_sign = result.get("saturn_sign") or result.get("transit_saturn_sign", "Pisces")
        moon_lbl = get_sign_name(moon_sign, lang=lang)
        saturn_lbl = get_sign_name(saturn_sign, lang=lang)

        if result["active"]:
            phase_names = {
                "ru": {
                    "rising": "🌅 Восходящая фаза (Сатурн в 12-м знаке от Луны)",
                    "peak": "🔥 Пиковая фаза (Сатурн в знаке натальной Луны)",
                    "setting": "🌇 Нисходящая фаза (Сатурн во 2-м знаке от Луны)",
                },
                "en": {
                    "rising": "🌅 Rising Phase (Saturn in 12th from Moon)",
                    "peak": "🔥 Peak Phase (Saturn in natal Moon sign)",
                    "setting": "🌇 Setting Phase (Saturn in 2nd from Moon)",
                },
                "it": {
                    "rising": "🌅 Fase Ascendente (Saturno nella 12ª dalla Luna)",
                    "peak": "🔥 Fase di Picco (Saturno nel segno della Luna natale)",
                    "setting": "🌇 Fase Discendente (Saturno nella 2ª dalla Luna)",
                }
            }.get(lang, {})
            phase_text = phase_names.get(result["phase"], result.get("phase_ru", result["phase"]))
            cyc = result.get("current_cycle") or {}
            cur_p_start = cyc.get("phase_start_ru", "")
            cur_p_end = cyc.get("phase_end_ru", "")
            full_end = cyc.get("end_date_ru", "")
            start_dt = cyc.get("start_date_ru", "")

            if lang == "en":
                text = (
                    f"🪐 *Sade-Sati — ACTIVE!* (Profile: '{prof_name}')\n\n"
                    f"🌙 Natal Moon: *{moon_lbl}*\n"
                    f"🪐 Transiting Saturn: *{saturn_lbl}*\n\n"
                    f"📍 *Phase:* {phase_text}\n\n"
                    "⏳ Sade-Sati lasts ~7.5 years — a period of karmic transformation, "
                    "deep life lessons, and spiritual growth.\n\n"
                    "💡 *Vedic Upayas for Saturn:*\n"
                    "• Chant Shani Mantra: *'Om Sham Shanaishcharaye Namaha'* (108 times on Saturdays)\n"
                    "• Saturdays: vegetarian food or fasting, refrain from alcohol\n"
                    "• Service and charity towards the elderly or animal shelters\n"
                    "• Saturday colors: dark blue, charcoal, black"
                )
            elif lang == "it":
                text = (
                    f"🪐 *Sade-Sati — ATTIVO!* (Profilo: '{prof_name}')\n\n"
                    f"🌙 Luna natale: *{moon_lbl}*\n"
                    f"🪐 Saturno in transito: *{saturn_lbl}*\n\n"
                    f"📍 *Fase:* {phase_text}\n\n"
                    "⏳ Il Sade-Sati dura ~7.5 anni — periodo di trasformazione karmica, "
                    "maturità e crescita spirituale.\n\n"
                    "💡 *Upaya vedici per Saturno:*\n"
                    "• Mantra di Shani: *'Om Sham Shanaishcharaye Namaha'* (108 volte di sabato)\n"
                    "• Di sabato: dieta vegetariana o digiuno, evitare alcol\n"
                    "• Volontariato e assistenza agli anziani\n"
                    "• Colori del sabato: blu notte, antracite, nero"
                )
            else:
                date_block = (
                    f"📅 *Даты текущего периода:*\n"
                    f"• Начало Саде-Сати: *{start_dt}*\n"
                    f"• Текущая фаза: с *{cur_p_start}* по *{cur_p_end}*\n"
                    f"• 🏁 *Полное окончание Саде-Сати: {full_end}*\n\n"
                ) if cyc else ""
                text = (
                    f"🪐 *Саде-Сати — АКТИВЕН!*{prof_title}\n\n"
                    f"🌙 Твоя натальная Луна: *{moon_lbl}*\n"
                    f"🪐 Транзитный Сатурн: *{saturn_lbl}*\n\n"
                    f"📍 *Фаза:* {phase_text}\n\n"
                    f"{date_block}"
                    "⏳ Саде-Сати длится ~7.5 лет — это период кармической трансформации, "
                    "глубоких жизненных уроков и духовного роста.\n\n"
                    "💡 *Упайя (гармонизация Сатурна):*\n"
                    "• Пение мантры Шани: *«Ом Шам Шанайе Намаха»* (108 раз по субботам)\n"
                    "• По субботам: вегетарианство или пост, отказ от алкоголя\n"
                    "• Служение, помощь пожилым людям и приютам животных\n"
                    "• Цвета субботы: тёмно-синий, графитовый, чёрный"
                )
        else:
            if lang == "en":
                text = (
                    f"🪐 *Sade-Sati — NOT ACTIVE* (Profile: '{prof_name}')\n\n"
                    f"🌙 Natal Moon: *{moon_lbl}*\n"
                    f"🪐 Transiting Saturn: *{saturn_lbl}*\n\n"
                    "✅ Saturn is not currently afflicting your natal Moon. The planetary influence is calm.\n\n"
                    "ℹ️ Sade-Sati occurs when transiting Saturn passes through the 12th, 1st, and 2nd houses from natal Moon."
                )
            elif lang == "it":
                text = (
                    f"🪐 *Sade-Sati — NON ATTIVO* (Profilo: '{prof_name}')\n\n"
                    f"🌙 Luna natale: *{moon_lbl}*\n"
                    f"🪐 Saturno in transito: *{saturn_lbl}*\n\n"
                    "✅ Attualmente Saturno non transita vicino alla Luna natale. Influenza armoniosa.\n\n"
                    "ℹ️ Il Sade-Sati si verifica quando Saturno transita nel 12°, 1° e 2° segno dalla Luna natale."
                )
            else:
                nxt = result.get("next_cycle") or {}
                prev = result.get("prev_cycle") or {}
                s12_ru = result.get("sign_12_ru", "")
                s1_ru = result.get("sign_1_ru", "")
                s2_ru = result.get("sign_2_ru", "")

                next_block = ""
                if nxt:
                    p1 = nxt.get("phase1_start_ru")
                    p2 = nxt.get("phase2_start_ru")
                    p3 = nxt.get("phase3_start_ru")
                    n_end = nxt.get("end_date_ru")
                    y_left = nxt.get("years_left", 1)
                    next_block = (
                        f"📅 *Когда начнётся следующий период Саде-Сати:*\n"
                        f"• 🌅 *Фаза 1 (Нарастание):* с *{p1}* (вход Сатурна в {s12_ru})\n"
                        f"• 🔥 *Фаза 2 (Пик):* с *{p2}* (вход Сатурна в {s1_ru})\n"
                        f"• 🌇 *Фаза 3 (Спад):* с *{p3}* (вход Сатурна в {s2_ru})\n"
                        f"• 🏁 *Окончание периода:* *{n_end}*\n"
                        f"⏳ До начала следующего Саде-Сати: *~{y_left} лет* (время спокойствия и созидания!).\n\n"
                    )

                prev_block = ""
                if prev:
                    pr_start = prev.get("start_date_ru")
                    pr_end = prev.get("end_date_ru")
                    prev_block = (
                        f"⏪ *Предыдущий Саде-Сати был:*\n"
                        f"• С *{pr_start}* по *{pr_end}* (~7.5 лет назад уроки уже пройдены).\n\n"
                    )

                text = (
                    f"🪐 *Саде-Сати — НЕ АКТИВЕН*{prof_title}\n\n"
                    f"🌙 Твоя натальная Луна: *{moon_lbl}*\n"
                    f"🪐 Транзитный Сатурн: *{saturn_lbl}*\n\n"
                    f"✅ Сейчас транзитный Сатурн не аспектирует натальную Луну. Влияние гармоничное.\n\n"
                    f"{next_block}"
                    f"{prev_block}"
                    "ℹ️ Саде-Сати наступает, когда транзитный Сатурн проходит "
                    "через 12-й, 1-й и 2-й знаки от натальной Луны (цикл повторяется каждые ~29.5 лет)."
                )

        try:
            await status_msg.delete()
        except Exception:
            pass
        await update.effective_message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_sadesati_inline_keyboard(lang)
        )

    except Exception as e:
        logger.exception("Ошибка проверки Саде-Сати")
        await status_msg.edit_text(f"⚠️ Ошибка при проверке Саде-Сати: {e}")
        await update.effective_message.reply_text(
            t("choose_next_action", lang),
            reply_markup=get_sadesati_inline_keyboard(lang)
        )


# ===================== ДЕТЕКТОР ЙОГ =====================

async def yoga_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Найти йоги (мощные комбинации планет) в натальной карте."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("need_chart_first", lang),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    chart_data = profile["chart_data"]

    status_text = {
        "ru": "🧘 Анализирую натальную карту на наличие йог...",
        "en": "🧘 Analyzing birth chart for Vedic yogas...",
        "it": "🧘 Analisi della carta natale per combinazioni Yoga...",
    }.get(lang, "🧘 Анализирую натальную карту на наличие йог...")
    status_msg = await update.effective_message.reply_text(status_text)
    try:
        yogas = detect_yogas(chart_data)
        active_yogas = [y for y in yogas if y.get("active", False)]
        prof_name = profile.get("profile_name", "Мой гороскоп")

        if not active_yogas:
            no_yogas_msg = {
                "ru": (
                    f"🧘 *Детектор йог — Профиль «{prof_name}»*\n\n"
                    "В карте не обнаружено классических йог из базового набора.\n"
                    "Это не означает слабую карту — многие благоприятные комбинации "
                    "требуют более глубокого анализа варг (дробных карт)."
                ),
                "en": (
                    f"🧘 *Yoga Detector — Profile '{prof_name}'*\n\n"
                    "No classical primary yogas detected in the basic configuration.\n"
                    "This does not imply a weak chart — many auspicious combinations "
                    "require divisional chart (varga) analysis."
                ),
                "it": (
                    f"🧘 *Rilevatore Yoga — Profilo '{prof_name}'*\n\n"
                    "Nessuna combinazione yoga classica rilevata nella configurazione di base.\n"
                    "Molte combinazioni propizie emergono dall'analisi delle carte divisionali (varga)."
                ),
            }.get(lang, f"🧘 *Детектор йог — Профиль «{prof_name}»*\n\nВ карте не обнаружено классических йог из базового набора.")
            await status_msg.edit_text(no_yogas_msg, parse_mode="Markdown")
            await update.effective_message.reply_text(
                t("choose_next_action", lang),
                reply_markup=get_yoga_inline_keyboard(lang)
            )
            return

        # Формируем список найденных йог
        yoga_lines = []
        for y in active_yogas:
            if lang == "en":
                name = y.get("name", "Yoga")
            elif lang == "it":
                name = y.get("name_it", y.get("name", "Yoga"))
            else:
                name = y.get("name_ru", y.get("name", "Йога"))
            desc = get_yoga_description(y.get("name", ""), lang=lang, default=y.get("description", ""))
            planets = ", ".join(get_planet_name(p, lang=lang) for p in y.get("planets", []))
            planets_lbl = {"ru": "🪐 Планеты", "en": "🪐 Planets", "it": "🪐 Pianeti"}.get(lang, "🪐 Планеты")
            yoga_lines.append(f"✨ *{name}*\n   {desc}\n   {planets_lbl}: {planets}")

        title_lbl = {
            "ru": f"🧘 *Детектор йог — Профиль «{prof_name}»*\nНайдено йог: {len(active_yogas)}\n\n",
            "en": f"🧘 *Yoga Detector — Profile '{prof_name}'*\nYogas found: {len(active_yogas)}\n\n",
            "it": f"🧘 *Rilevatore Yoga — Profilo '{prof_name}'*\nYoga rilevati: {len(active_yogas)}\n\n",
        }.get(lang, f"🧘 *Детектор йог — Профиль «{prof_name}»*\nНайдено йог: {len(active_yogas)}\n\n")

        yoga_text = title_lbl + "\n\n".join(yoga_lines)

        await status_msg.delete()
        await send_split_message(update, yoga_text)

    except Exception as e:
        logger.exception("Ошибка детектора йог")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе йог: {e}")
        await update.effective_message.reply_text(
            t("choose_next_action", lang),
            reply_markup=get_yoga_inline_keyboard(lang)
        )
        return

    # ИИ-интерпретация йог
    gemini = get_gemini_client()
    if not gemini or not active_yogas:
        await update.effective_message.reply_text(
            t("choose_next_action", lang),
            reply_markup=get_yoga_inline_keyboard(lang)
        )
        return

    has_paid = context.user_data.get("paid_yoga", False)
    if PAYMENT_REQUIRED and not has_paid:
        pay_prompt = {
            "ru": (
                "🌟 *Йоги найдены!*\n\n"
                "Хочешь получить персональную трактовку найденных йог от ИИ-астролога? "
                "Как они влияют на твою судьбу, карьеру и отношения?\n"
                f"Стоимость разбора: **{PRICE_YOGA_STARS} ⭐️**"
            ),
            "en": (
                "🌟 *Yogas found!*\n\n"
                "Want a personalized reading of these yogas from the AI Astrologer? "
                "How do they influence your destiny, career, and relationships?\n"
                f"Price: **{PRICE_YOGA_STARS} ⭐️**"
            ),
            "it": (
                "🌟 *Combinazioni Yoga trovate!*\n\n"
                "Vuoi una lettura personalizzata delle combinazioni Yoga dall'astrologo IA?\n"
                f"Prezzo: **{PRICE_YOGA_STARS} ⭐️**"
            )
        }.get(lang, (
            "🌟 *Йоги найдены!*\n\n"
            "Хочешь получить персональную трактовку найденных йог от ИИ-астролога? "
            "Как они влияют на твою судьбу, карьеру и отношения?\n"
            f"Стоимость разбора: **{PRICE_YOGA_STARS} ⭐️**"
        ))
        await update.effective_message.reply_text(
            pay_prompt,
            parse_mode="Markdown",
            reply_markup=get_yoga_inline_keyboard(lang)
        )
        await send_yoga_invoice(update, context, lang=lang)
        return

    ai_status_text = {
        "ru": "🔮 ИИ-астролог трактует найденные йоги...",
        "en": "🔮 AI Astrologer is interpreting the yogas...",
        "it": "🔮 L'astrologo IA sta interpretando le combinazioni Yoga...",
    }.get(lang, "🔮 ИИ-астролог трактует найденные йоги...")
    ai_status = await update.effective_message.reply_text(ai_status_text)
    try:
        interpretation = await gemini.interpret_yogas(chart_data, profile["summary"], active_yogas, lang=lang)
        await ai_status.delete()
        res_header = {
            "ru": "🧘 *ИИ-трактовка йог:*\n\n",
            "en": "🧘 *AI Interpretation of Yogas:*\n\n",
            "it": "🧘 *Interpretazione IA degli Yoga:*\n\n",
        }.get(lang, "🧘 *ИИ-трактовка йог:*\n\n")
        await send_split_message(
            update,
            res_header + interpretation,
            reply_markup=get_yoga_inline_keyboard(lang)
        )
    except Exception as e:
        logger.exception("Ошибка ИИ-трактовки йог")
        await ai_status.edit_text(f"⚠️ Ошибка при трактовке йог: {e}")
        await update.effective_message.reply_text(
            t("choose_next_action", lang),
            reply_markup=get_yoga_inline_keyboard(lang)
        )


# ===================== КАРМИЧЕСКАЯ ЗАДАЧА ДУШИ (/karma) =====================

async def karma_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кармическая задача души и Чара-Караки Джаймини (Атмакарака и др.)."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("dasha_need_chart", lang) or "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    chart_data = profile["chart_data"]
    karakas = calculate_chara_karakas(chart_data)
    karaka_text = format_chara_karakas(karakas, lang=lang)
    prof_name = profile.get('profile_name', 'Мой гороскоп')
    header_map = {
        "ru": f"🌟 *Кармическая задача души (Профиль: «{prof_name}»)*\n\n",
        "en": f"🌟 *Soul Karmic Task (Profile: «{prof_name}»)*\n\n",
        "it": f"🌟 *Compito Karmico dell'Anima (Profilo: «{prof_name}»)*\n\n",
    }
    header = header_map.get(lang, header_map["ru"])
    full_text = header + karaka_text

    gemini = get_gemini_client()
    if not gemini:
        await send_split_message(update, full_text, reply_markup=get_karma_inline_keyboard(lang))
        return

    has_paid = context.user_data.get("paid_karma", False) if context and context.user_data else False
    if PAYMENT_REQUIRED and not has_paid:
        await send_split_message(update, full_text)
        pitch_map = {
            "ru": (
                "🌟 *Караки души рассчитаны!*\n\n"
                "Хочешь получить глубокий разбор кармической задачи души от ИИ-астролога? "
                "В чём твой главный жизненный урок и через что раскрывается истинный путь души?\n"
                f"Стоимость разбора: **{PRICE_KARMA_STARS} ⭐️**"
            ),
            "en": (
                "🌟 *Soul Karakas calculated!*\n\n"
                "Would you like to get a deep reading of your soul's karmic task from the AI Astrologer? "
                "What is your primary life lesson and how does your true spiritual path unfold?\n"
                f"Reading price: **{PRICE_KARMA_STARS} ⭐️**"
            ),
            "it": (
                "🌟 *Karaka dell'anima calcolati!*\n\n"
                "Vuoi ricevere un'analisi profonda del compito karmico della tua anima dall'Astrologo IA? "
                "Qual è la tua lezione di vita principale e come si rivela la vera via della tua anima?\n"
                f"Prezzo dell'analisi: **{PRICE_KARMA_STARS} ⭐️**"
            )
        }
        await update.effective_message.reply_text(
            pitch_map.get(lang, pitch_map["ru"]),
            parse_mode="Markdown",
            reply_markup=get_karma_inline_keyboard(lang)
        )
        await send_karma_invoice(update, context, lang=lang)
        return

    await send_split_message(update, full_text)
    status_text_map = {
        "ru": "🔮 ИИ-астролог анализирует кармическую задачу души...",
        "en": "🔮 AI Astrologer is analyzing the soul's karmic task...",
        "it": "🔮 L'Astrologo IA sta analizzando il compito karmico dell'anima...",
    }
    status_msg = await update.effective_message.reply_text(status_text_map.get(lang, status_text_map["ru"]))
    try:
        interpretation = await gemini.interpret_karma(chart_data, profile.get("summary", ""), karakas, lang=lang)
        await status_msg.delete()
        res_header_map = {
            "ru": "🔮 *Глубокий кармический разбор (ИИ-Астролог):*\n\n",
            "en": "🔮 *Deep Karmic Analysis (AI Astrologer):*\n\n",
            "it": "🔮 *Analisi Karmica Approfondita (Astrologo IA):*\n\n",
        }
        await send_split_message(
            update,
            f"{res_header_map.get(lang, res_header_map['ru'])}{interpretation}",
            reply_markup=get_karma_inline_keyboard(lang)
        )
    except Exception as e:
        logger.exception("Ошибка ИИ-разбора кармы")
        await status_msg.edit_text(f"⚠️ Ошибка при генерации кармического разбора: {e}")
        await update.effective_message.reply_text(t("choose_next_action", lang), reply_markup=get_karma_inline_keyboard(lang))


# ===================== ФИНАНСОВЫЙ КОД И КАРЬЕРА (/money) =====================

async def money_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финансовый потенциал, дома богатства и стратегия карьеры."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("dasha_need_chart", lang) or "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    chart_data = profile["chart_data"]
    wealth_data = analyze_wealth_and_career(chart_data)
    wealth_text = format_wealth_analysis(wealth_data, lang=lang)
    prof_name = profile.get('profile_name', 'Мой гороскоп')
    header_map = {
        "ru": f"💰 *Финансовый код и карьера (Профиль: «{prof_name}»)*\n\n",
        "en": f"💰 *Wealth Code & Career (Profile: «{prof_name}»)*\n\n",
        "it": f"💰 *Codice Finanziario e Carriera (Profilo: «{prof_name}»)*\n\n",
    }
    header = header_map.get(lang, header_map["ru"])
    full_text = header + wealth_text

    gemini = get_gemini_client()
    if not gemini:
        await send_split_message(update, full_text, reply_markup=get_money_inline_keyboard(lang))
        return

    has_paid = context.user_data.get("paid_money", False) if context and context.user_data else False
    if PAYMENT_REQUIRED and not has_paid:
        await send_split_message(update, full_text)
        pitch_map = {
            "ru": (
                "💰 *Финансовый анализ составлен!*\n\n"
                "Хочешь получить персональную стратегию заработка и масштабирования от ИИ-астролога? "
                "Какие ниши принесут максимум дохода и как гармонизировать денежный поток?\n"
                f"Стоимость стратегии: **{PRICE_MONEY_STARS} ⭐️**"
            ),
            "en": (
                "💰 *Wealth analysis completed!*\n\n"
                "Would you like to get a personalized earning and scaling strategy from the AI Astrologer? "
                "Which niches bring the highest income and how to harmonize your cash flow?\n"
                f"Strategy price: **{PRICE_MONEY_STARS} ⭐️**"
            ),
            "it": (
                "💰 *Analisi finanziaria completata!*\n\n"
                "Vuoi ricevere una strategia personalizzata di guadagno e crescita dall'Astrologo IA? "
                "Quali settori portano il massimo reddito e come armonizzare il flusso di denaro?\n"
                f"Prezzo della strategia: **{PRICE_MONEY_STARS} ⭐️**"
            )
        }
        await update.effective_message.reply_text(
            pitch_map.get(lang, pitch_map["ru"]),
            parse_mode="Markdown",
            reply_markup=get_money_inline_keyboard(lang)
        )
        await send_money_invoice(update, context, lang=lang)
        return

    await send_split_message(update, full_text)
    status_text_map = {
        "ru": "💼 ИИ-астролог формирует финансовую стратегию...",
        "en": "💼 AI Astrologer is formulating your financial strategy...",
        "it": "💼 L'Astrologo IA sta elaborando la tua strategia finanziaria...",
    }
    status_msg = await update.effective_message.reply_text(status_text_map.get(lang, status_text_map["ru"]))
    try:
        interpretation = await gemini.interpret_wealth(chart_data, profile.get("summary", ""), wealth_data, lang=lang)
        await status_msg.delete()
        res_header_map = {
            "ru": "💼 *Персональная финансовая стратегия (ИИ-Астролог):*\n\n",
            "en": "💼 *Personal Wealth Strategy (AI Astrologer):*\n\n",
            "it": "💼 *Strategia Finanziaria Personalizzata (Astrologo IA):*\n\n",
        }
        await send_split_message(
            update,
            f"{res_header_map.get(lang, res_header_map['ru'])}{interpretation}",
            reply_markup=get_money_inline_keyboard(lang)
        )
    except Exception as e:
        logger.exception("Ошибка ИИ-разбора финансов")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе финансов: {e}")
        await update.effective_message.reply_text(t("choose_next_action", lang), reply_markup=get_money_inline_keyboard(lang))


# ===================== ВЕДИЧЕСКИЕ УПАЙИ (/upaya) =====================

async def upaya_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ведические Упайи (методы гармонизации планетных влияний) — 100% бесплатно."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("dasha_need_chart", lang) or "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard(lang)
        )
        return

    chart_data = profile["chart_data"]
    upaya_data = get_upayas(chart_data)
    upaya_text = format_upayas(upaya_data, lang=lang)
    prof_name = profile.get('profile_name', 'Мой гороскоп')
    header_map = {
        "ru": f"🛡 *Персональные Ведические Упайи (Профиль: «{prof_name}»)*\n\n",
        "en": f"🛡 *Personal Vedic Upayas (Profile: «{prof_name}»)*\n\n",
        "it": f"🛡 *Upaya Vedici Personalizzati (Profilo: «{prof_name}»)*\n\n",
    }
    header = header_map.get(lang, header_map["ru"])
    await send_split_message(update, header + upaya_text, reply_markup=get_upaya_inline_keyboard(lang))


# ===================== ЭКСПРЕСС-ВОПРОС (/ask) =====================

async def ask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога экспресс-вопроса ИИ-астрологу."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            t("dasha_need_chart", lang) or "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard(lang)
        )
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        ai_unavail_map = {
            "ru": "ℹ️ ИИ-астролог недоступен. Для подключения добавь `GEMINI_API_KEY` в `.env`.",
            "en": "ℹ️ AI Astrologer is unavailable. Add `GEMINI_API_KEY` to `.env` to enable.",
            "it": "ℹ️ Astrologo IA non disponibile. Aggiungi `GEMINI_API_KEY` in `.env` per attivare.",
        }
        await update.effective_message.reply_text(
            ai_unavail_map.get(lang, ai_unavail_map["ru"]),
            parse_mode="Markdown",
            reply_markup=get_main_reply_keyboard(lang)
        )
        return ConversationHandler.END

    free_available = is_free_ask_available(user_id)
    has_paid = context.user_data.get("paid_ask", False) if context and context.user_data else False

    if PAYMENT_REQUIRED and not has_paid and not free_available:
        pitch_map = {
            "ru": (
                "❓ *Экспресс-вопрос ИИ-астрологу*\n\n"
                "Задай любой вопрос по своей натальной карте — карьера, отношения, здоровье, переезд, финансы.\n\n"
                f"Стоимость: **{PRICE_ASK_STARS} ⭐️**"
            ),
            "en": (
                "❓ *Express Question to AI Astrologer*\n\n"
                "Ask any question about your chart — career, relationships, health, relocation, finance.\n\n"
                f"Price: **{PRICE_ASK_STARS} ⭐️**"
            ),
            "it": (
                "❓ *Domanda Espressa all'Astrologo IA*\n\n"
                "Poni qualsiasi domanda sul tuo tema natale — carriera, relazioni, salute, trasferimenti, finanze.\n\n"
                f"Prezzo: **{PRICE_ASK_STARS} ⭐️**"
            )
        }
        await update.effective_message.reply_text(
            pitch_map.get(lang, pitch_map["ru"]),
            parse_mode="Markdown"
        )
        await send_ask_invoice(update, context, lang=lang)
        return ConversationHandler.END

    prof_name = profile.get("profile_name", "Мой гороскоп")
    free_notices = {
        "ru": "🎁 *Твой 1-й вопрос к ИИ-астрологу — БЕСПЛАТНО!*\n\n",
        "en": "🎁 *Your 1st question to AI Astrologer is FREE!*\n\n",
        "it": "🎁 *La tua 1ª domanda all'Astrologo IA è GRATUITA!*\n\n",
    }
    free_notice = free_notices.get(lang, free_notices["ru"]) if (free_available and not has_paid) else ""

    instructions_map = {
        "ru": (
            f"{free_notice}❓ *Задай вопрос ИИ-астрологу (Профиль: «{prof_name}»)*\n\n"
            "Напиши свой вопрос свободным текстом. Бот сопоставит натальную карту с твоим текущим периодом (Даша) и транзитами!\n\n"
            "Примеры вопросов:\n"
            "• 💼 _«Стоит ли менять работу в 2026–2027 годах?»_\n"
            "• ✈️ _«Благоприятен ли сейчас переезд за границу?»_\n"
            "• 💍 _«Когда благоприятный период для брака или отношений?»_\n"
            "• 💰 _«Что ждёт в финансовой сфере в текущий период?»_\n"
            "• ⏳ _«Почему сейчас ощущение застоя и когда это закончится?»_\n\n"
            "Для отмены набери /cancel"
        ),
        "en": (
            f"{free_notice}❓ *Ask AI Astrologer (Profile: «{prof_name}»)*\n\n"
            "Write your question in free text. The bot will cross-reference your natal chart with your current Dasha period and transits!\n\n"
            "Example questions:\n"
            "• 💼 _«Should I change my career in 2026–2027?»_\n"
            "• ✈️ _«Is this a favorable time to move abroad?»_\n"
            "• 💍 _«When is an auspicious period for marriage or relationships?»_\n"
            "• 💰 _«What should I expect financially during my current period?»_\n"
            "• ⏳ _«Why do I feel stuck right now and when will it pass?»_\n\n"
            "Type /cancel to cancel."
        ),
        "it": (
            f"{free_notice}❓ *Fai una domanda all'Astrologo IA (Profilo: «{prof_name}»)*\n\n"
            "Scrivi la tua domanda in testo libero. Il bot collegherà la tua carta natale al periodo Dasha attuale e ai transiti!\n\n"
            "Esempi di domande:\n"
            "• 💼 _«Dovrei cambiare lavoro nel 2026–2027?»_\n"
            "• ✈️ _«È un momento favorevole per trasferirmi all'estero?»_\n"
            "• 💍 _«Quando ci sarà un periodo favorevole per il matrimonio o l'amore?»_\n"
            "• 💰 _«Cosa mi aspetta nell'ambito finanziario nel periodo attuale?»_\n"
            "• ⏳ _«Perché sento un blocco in questo momento e quando passerà?»_\n\n"
            "Digita /cancel per annullare."
        )
    }
    await update.effective_message.reply_text(
        instructions_map.get(lang, instructions_map["ru"]),
        parse_mode="Markdown"
    )
    return ASK_WAITING_QUESTION


async def ask_question_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение вопроса и генерация ответа от ИИ-астролога."""
    question = update.message.text.strip()
    user_id = update.effective_user.id
    lang = get_user_lang(update, context)
    profile = get_user_natal_profile(user_id, context)

    if not profile:
        sess_exp_map = {
            "ru": "Сессия истекла. Начни заново с /chart.",
            "en": "Session expired. Please start again with /chart.",
            "it": "Sessione scaduta. Ricomincia con /chart.",
        }
        await update.effective_message.reply_text(
            sess_exp_map.get(lang, sess_exp_map["ru"]),
            reply_markup=get_main_reply_keyboard(lang)
        )
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        await update.effective_message.reply_text("⚠️ ИИ-астролог недоступен.")
        return ConversationHandler.END

    chart_data = profile["chart_data"]
    summary = profile["summary"]

    # Рассчитываем прогностический контекст (текущая Даша и Саде-Сати)
    forecast_context_parts = []
    now = datetime.now()
    forecast_context_parts.append(f"Текущая дата запроса: {now.strftime('%d.%m.%Y')}")

    try:
        curr_dasha = get_current_dasha(chart_data, now)
        if curr_dasha and curr_dasha.get("maha_dasha"):
            md = curr_dasha["maha_dasha"]
            md_p = get_planet_name(md['planet'], lang)
            md_str = f"Махадаша / Mahadasha: {md_p} ({md['start']} — {md['end']})"
            if curr_dasha.get("antar_dasha"):
                ad = curr_dasha["antar_dasha"]
                ad_p = get_planet_name(ad['planet'], lang)
                ad_str = f", Антардаша / Antardasha: {ad_p} ({ad['start']} — {ad['end']})"
                md_str += ad_str
            forecast_context_parts.append(f"Текущий планетарный период (Вимшоттари Даша): {md_str}")
    except Exception as e:
        logger.debug(f"Не удалось рассчитать дашу для /ask: {e}")

    try:
        ss_info = check_sade_sati(chart_data)
        if ss_info:
            moon_s = get_sign_name(ss_info.get('moon_sign', ''), lang)
            sat_s = get_sign_name(ss_info.get('saturn_sign', ''), lang)
            if ss_info.get("active"):
                forecast_context_parts.append(
                    f"Транзит Саде-Сати (Сатурн): АКТИВЕН, фаза {ss_info.get('phase_ru', ss_info.get('phase'))}. "
                    f"Натальная Луна в {moon_s}, Сатурн в {sat_s}."
                )
            else:
                forecast_context_parts.append(
                    f"Транзит Саде-Сати: НЕ активен (Сатурн в {sat_s}, Луна в {moon_s})."
                )
    except Exception as e:
        logger.debug(f"Не удалось проверить Саде-Сати для /ask: {e}")

    forecast_context = "\n".join(forecast_context_parts)

    status_map = {
        "ru": "🔮 ИИ-астролог анализирует твою карту и готовит ответ...",
        "en": "🔮 AI Astrologer is analyzing your chart and preparing an answer...",
        "it": "🔮 L'Astrologo IA sta analizzando la tua carta e preparando la risposta...",
    }
    status_msg = await update.effective_message.reply_text(status_map.get(lang, status_map["ru"]))
    try:
        answer = await gemini.interpret_ask_question(
            chart_data, summary, question, forecast_context=forecast_context, lang=lang
        )
        await status_msg.delete()
        res_map = {
            "ru": "📜 *Ответ ИИ-астролога:*\n\n",
            "en": "📜 *AI Astrologer's Answer:*\n\n",
            "it": "📜 *Risposta dell'Astrologo IA:*\n\n",
        }
        await send_split_message(
            update,
            f"{res_map.get(lang, res_map['ru'])}{answer}",
            reply_markup=get_ask_inline_keyboard(lang)
        )
        # Если это был первый бесплатный вопрос, помечаем его использованным
        if is_free_ask_available(user_id) and not (context.user_data and context.user_data.get("paid_ask", False)):
            mark_free_ask_used(user_id)
    except Exception as e:
        logger.exception("Ошибка ответа на вопрос")
        await status_msg.edit_text(f"⚠️ Ошибка при генерации ответа: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_ask_inline_keyboard(lang)
        )

    return ConversationHandler.END


# ===================== ОБРАБОТКА ОПЛАТЫ В ЗВЁЗДАХ (STARS) =====================

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка успешной оплаты в Звёздах Telegram (XTR).
    Мгновенно активирует разбор и отправляет ответ пользователю.
    """
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    stars_amount = payment.total_amount

    logger.info(f"Получена оплата: {stars_amount} XTR, payload={payload}")

    lang = get_user_lang(update, context)

    success_notices = {
        "ru": f"🎉 *Оплата успешно получена ({stars_amount} ⭐️)!*\nЗапускаю расчёт и генерацию персонального разбора...",
        "en": f"🎉 *Payment received successfully ({stars_amount} ⭐️)!*\nStarting calculation and AI reading generation...",
        "it": f"🎉 *Pagamento ricevuto con successo ({stars_amount} ⭐️)!*\nAvvio del calcolo e della generazione dell'analisi IA...",
    }
    await update.message.reply_text(
        success_notices.get(lang, success_notices["ru"]),
        parse_mode="Markdown"
    )

    gemini = get_gemini_client()
    user_id = update.effective_user.id
    profile = get_user_natal_profile(user_id, context)

    if not gemini or not profile:
        await update.message.reply_text("Спасибо за оплату! Твой премиум-статус активирован.")
        return

    chart_data = profile["chart_data"]
    summary = profile["summary"]

    if payload == "payload_chart_interpretation":
        context.user_data["paid_chart"] = True
        status_msg = await update.effective_message.reply_text(t("payment_status_chart", lang))
        try:
            interpretation = await gemini.interpret_chart(chart_data, summary, lang=lang)
            await status_msg.delete()
            res_headers = {
                "ru": "📜 *Персональный разбор натальной карты:*\n\n",
                "en": "📜 *Personal Natal Chart Reading:*\n\n",
                "it": "📜 *Interpretazione Personale del Tema Natale:*\n\n",
            }
            await send_split_message(
                update,
                f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                reply_markup=get_chart_inline_keyboard(lang)
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_dasha_interpretation":
        context.user_data["paid_dasha"] = True
        status_msg = await update.effective_message.reply_text(t("payment_status_dasha", lang))
        try:
            interpretation = await gemini.interpret_dasha(chart_data, summary, lang=lang)
            await status_msg.delete()
            res_headers = {
                "ru": "🌟 *Анализ периодов судьбы (Даша):*\n\n",
                "en": "🌟 *Vimshottari Dasha Analysis:*\n\n",
                "it": "🌟 *Analisi dei Periodi Vimshottari Dasha:*\n\n",
            }
            await send_split_message(
                update,
                f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                reply_markup=get_dasha_inline_keyboard(lang)
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_compat_interpretation":
        context.user_data["paid_compat"] = True
        partner_chart = context.user_data.get("partner_chart")
        partner_summary = context.user_data.get("partner_summary")
        if partner_chart and partner_summary:
            status_msg = await update.effective_message.reply_text(t("payment_status_compat", lang))
            try:
                interpretation = await gemini.interpret_compatibility(
                    chart_data, summary, partner_chart, partner_summary, lang=lang
                )
                await status_msg.delete()
                res_headers = {
                    "ru": "💘 *Анализ совместимости парных карт:*\n\n",
                    "en": "💘 *Synastry & Compatibility Reading:*\n\n",
                    "it": "💘 *Analisi di Sinastria e Compatibilità:*\n\n",
                }
                await send_split_message(
                    update,
                    f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                    reply_markup=get_compat_inline_keyboard(lang)
                )
            except Exception as e:
                await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_ask_question":
        context.user_data["paid_ask"] = True
        ask_paid_msgs = {
            "ru": "❓ *Экспресс-вопрос оплачен!*\n\nТеперь нажми кнопку ниже или набери /ask и задай свой вопрос ИИ-астрологу.",
            "en": "❓ *Express Question unlocked!*\n\nTap the button below or type /ask to ask your question to the AI Astrologer.",
            "it": "❓ *Domanda espressa sbloccata!*\n\nPremi il pulsante qui sotto o digita /ask per porre la tua domanda all'Astrologo IA.",
        }
        await update.effective_message.reply_text(
            ask_paid_msgs.get(lang, ask_paid_msgs["ru"]),
            parse_mode="Markdown",
            reply_markup=get_ask_inline_keyboard(lang)
        )

    elif payload == "payload_yoga_interpretation":
        context.user_data["paid_yoga"] = True
        # Запускаем ИИ-трактовку йог сразу после оплаты
        yogas = detect_yogas(chart_data)
        active_yogas = [y for y in yogas if y.get("active", False)]
        if active_yogas:
            status_msg = await update.effective_message.reply_text(t("payment_status_yoga", lang))
            try:
                interpretation = await gemini.interpret_yogas(chart_data, summary, active_yogas, lang=lang)
                await status_msg.delete()
                res_headers = {
                    "ru": "🧘 *ИИ-трактовка йог:*\n\n",
                    "en": "🧘 *AI Interpretation of Yogas:*\n\n",
                    "it": "🧘 *Interpretazione IA degli Yoga:*\n\n",
                }
                await send_split_message(
                    update,
                    f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                    reply_markup=get_yoga_inline_keyboard(lang)
                )
            except Exception as e:
                await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")
        else:
            await update.effective_message.reply_text(
                t("payment_yoga_ready", lang),
                parse_mode="Markdown",
                reply_markup=get_yoga_inline_keyboard(lang)
            )

    elif payload == "payload_karma_interpretation":
        context.user_data["paid_karma"] = True
        karakas = calculate_chara_karakas(chart_data)
        status_msg = await update.effective_message.reply_text(t("payment_status_karma", lang))
        try:
            interpretation = await gemini.interpret_karma(chart_data, summary, karakas, lang=lang)
            await status_msg.delete()
            res_headers = {
                "ru": "🔮 *Глубокий кармический разбор (ИИ-Астролог):*\n\n",
                "en": "🔮 *Deep Karmic Analysis (AI Astrologer):*\n\n",
                "it": "🔮 *Analisi Karmica Approfondita (Astrologo IA):*\n\n",
            }
            await send_split_message(
                update,
                f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                reply_markup=get_karma_inline_keyboard(lang)
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_money_interpretation":
        context.user_data["paid_money"] = True
        wealth_data = analyze_wealth_and_career(chart_data)
        status_msg = await update.effective_message.reply_text(t("payment_status_money", lang))
        try:
            interpretation = await gemini.interpret_wealth(chart_data, summary, wealth_data, lang=lang)
            await status_msg.delete()
            res_headers = {
                "ru": "💼 *Персональная финансовая стратегия (ИИ-Астролог):*\n\n",
                "en": "💼 *Personal Wealth Strategy (AI Astrologer):*\n\n",
                "it": "💼 *Strategia Finanziaria Personalizzata (Astrologo IA):*\n\n",
            }
            await send_split_message(
                update,
                f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                reply_markup=get_money_inline_keyboard(lang)
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_bundle_360":
        # Бандл активирует все платные функции
        context.user_data["paid_chart"] = True
        context.user_data["paid_dasha"] = True
        context.user_data["paid_yoga"] = True
        context.user_data["paid_karma"] = True
        context.user_data["paid_money"] = True
        context.user_data["paid_ask"] = True
        # Генерируем полный разбор карты как основной продукт бандла
        bundle_notices = {
            "ru": (
                "🌟 *Бандл «Вся судьба 360°» активирован!*\n\n"
                "Тебе доступны: разбор карты, Даша, йоги, карма, деньги и 1 вопрос.\n"
                "Начинаю полный разбор натальной карты..."
            ),
            "en": (
                "🌟 *All-in-One 360° Bundle activated!*\n\n"
                "Unlocked: Natal Chart, Dasha, Yogas, Karma, Wealth, and 1 Question.\n"
                "Generating full natal chart analysis..."
            ),
            "it": (
                "🌟 *Pacchetto Completo 360° attivato!*\n\n"
                "Sbloccati: Tema Natale, Dasha, Yoga, Karma, Denaro e 1 Domanda.\n"
                "Generazione dell'analisi completa del tema natale in corso..."
            )
        }
        status_msg = await update.effective_message.reply_text(
            bundle_notices.get(lang, bundle_notices["ru"]),
            parse_mode="Markdown"
        )
        try:
            interpretation = await gemini.interpret_chart(chart_data, summary, lang=lang)
            await status_msg.delete()
            res_headers = {
                "ru": "📜 *Персональный разбор натальной карты:*\n\n",
                "en": "📜 *Personal Natal Chart Reading:*\n\n",
                "it": "📜 *Interpretazione Personale del Tema Natale:*\n\n",
            }
            await send_split_message(
                update,
                f"{res_headers.get(lang, res_headers['ru'])}{interpretation}",
                reply_markup=get_chart_inline_keyboard(lang)
            )
            unlock_notices = {
                "ru": "✅ Теперь используй /dasha, /karma, /money, /yoga и /ask — все они разблокированы!",
                "en": "✅ Now use /dasha, /karma, /money, /yoga, and /ask — all features are unlocked!",
                "it": "✅ Ora usa /dasha, /karma, /money, /yoga e /ask — tutte le sezioni sono sbloccate!",
            }
            await update.effective_message.reply_text(
                unlock_notices.get(lang, unlock_notices["ru"]),
                reply_markup=get_main_reply_keyboard(lang)
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_test_payment":
        await update.effective_message.reply_text(
            "🎉 *Тестовый платёж на 1 ⭐️ успешно получен!*\n\n"
            "Платёжная система Telegram Stars полностью исправна и готова к приёму реальных платежей.",
            parse_mode="Markdown",
            reply_markup=get_admin_inline_keyboard()
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего ввода и возврат к главному меню."""
    lang = get_user_lang(update, context)
    if context.user_data:
        context.user_data.pop("temp_dob", None)
        context.user_data.pop("temp_tob", None)
        context.user_data.pop("temp_profile_name", None)
        context.user_data.pop("editing_profile_id", None)
        context.user_data.pop("compat_dob", None)
        context.user_data.pop("compat_tob", None)
    cancel_msgs = {
        "ru": "Ввод отменён. Нажми кнопку ниже или /chart в любой момент.",
        "en": "Input cancelled. Tap a button below or /chart anytime.",
        "it": "Operazione annullata. Premi un pulsante sotto o /chart in qualsiasi momento.",
    }
    await update.effective_message.reply_text(
        cancel_msgs.get(lang, cancel_msgs["ru"]),
        reply_markup=get_main_reply_keyboard(lang)
    )
    return ConversationHandler.END


# ===================== НАВИГАЦИОННЫЕ И ИНЛАЙН ХЕНДЛЕРЫ =====================

async def inline_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единый диспетчер для навигационных, профильных и платёжных инлайн-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    lang = get_user_lang(update, context)

    logger.info(f"Нажата инлайн-кнопка: {data}")

    # Языковые настройки
    if data == "nav_lang":
        await lang_command(update, context)

    elif data.startswith("set_lang_"):
        code = data.replace("set_lang_", "")
        if code == "auto":
            set_user_language(user_id, None)
            if context.user_data is not None:
                context.user_data.pop("user_lang", None)
            new_lang = get_user_lang(update, context)
            confirm_text = t("lang_auto_switched", new_lang, selected_lang=LANGUAGE_LABELS.get(new_lang, new_lang))
        else:
            set_user_language(user_id, code)
            if context.user_data is not None:
                context.user_data["user_lang"] = code
            new_lang = code
            confirm_text = t("lang_switched", new_lang)

        try:
            await query.edit_message_reply_markup(reply_markup=get_language_inline_keyboard(current_lang=new_lang))
        except Exception:
            pass

        await query.message.reply_text(
            confirm_text,
            parse_mode="Markdown",
            reply_markup=get_main_reply_keyboard(new_lang)
        )

    # Управление профилями
    elif data == "prof_menu":
        await profile_command(update, context)

    elif data.startswith("prof_switch_"):
        prof_id = int(data.split("prof_switch_")[1])
        if set_active_profile(prof_id, user_id):
            new_active = get_profile_by_id(prof_id, user_id)
            context.user_data["natal_profile"] = new_active
            await query.message.reply_text(
                t("profile_switched_success", lang, name=new_active['profile_name']),
                parse_mode="Markdown",
                reply_markup=get_profile_switched_keyboard(lang)
            )
        else:
            await query.message.reply_text(t("profile_switch_fail", lang))

    elif data == "prof_view_active":
        active = get_user_natal_profile(user_id, context)
        if not active:
            await query.message.reply_text(t("no_profile_found", lang))
            return

        # Отправляем графическую карту Кундли D1
        if active.get("chart_data"):
            try:
                b_dt = active.get("birth_dt")
                dob_s = b_dt.strftime("%d.%m.%Y") if b_dt else None
                tob_s = b_dt.strftime("%H:%M") if b_dt else None
                chart_img = render_kundli_chart(
                    chart_data=active["chart_data"],
                    profile_name=active.get("profile_name"),
                    dob_str=dob_s,
                    tob_str=tob_s,
                    place_str=active.get("place_name"),
                    lang=lang
                )
                caption = t("chart_ready_header", lang, name=active.get('profile_name', 'Профиль'))
                await query.message.reply_photo(
                    photo=chart_img,
                    caption=caption,
                    parse_mode="Markdown"
                )
            except Exception as img_err:
                logger.warning(f"Не удалось отправить изображение карты: {img_err}")

        summary = active.get("summary")
        if not summary and active.get("chart_data"):
            try:
                summary = format_chart_summary(active["chart_data"], lang=lang)
            except Exception:
                summary = ""
        header = t("chart_summary_caption", lang, name=active['profile_name'])
        await send_split_message(update, header + (summary or ""), reply_markup=get_chart_inline_keyboard(lang))

    elif data == "prof_delete_menu":
        profiles = get_user_profiles(user_id)
        if not profiles:
            await query.message.reply_text(t("profile_no_profiles_to_delete", lang))
            return
        buttons = []
        for p in profiles:
            buttons.append([InlineKeyboardButton(t("btn_delete_format", lang, name=p['profile_name']), callback_data=f"prof_del_{p['id']}")])
        buttons.append([InlineKeyboardButton(t("btn_clean_duplicates", lang), callback_data="prof_cleanup_duplicates")])
        buttons.append([InlineKeyboardButton(t("btn_back_to_profiles", lang), callback_data="prof_menu")])
        await query.message.reply_text(
            t("profile_delete_menu", lang),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "prof_cleanup_duplicates":
        deleted = cleanup_duplicate_profiles(user_id)
        active = get_user_natal_profile(user_id, context)
        active_name = active["profile_name"] if active else t("default_profile_name", lang)
        if deleted > 0:
            msg = t("duplicates_cleaned", lang, count=deleted, name=active_name)
        else:
            msg = t("duplicates_none", lang)
        await query.message.reply_text(msg, parse_mode="Markdown")
        await profile_command(update, context)

    elif data.startswith("prof_del_"):
        prof_id = int(data.split("prof_del_")[1])
        deleted_prof = get_profile_by_id(prof_id, user_id)
        name = deleted_prof["profile_name"] if deleted_prof else t("default_profile_name", lang)
        if delete_profile(prof_id, user_id):
            new_active = get_active_profile(user_id)
            context.user_data["natal_profile"] = new_active
            await query.message.reply_text(t("profile_delete_success", lang, name=name), parse_mode="Markdown")
            await profile_command(update, context)
        else:
            await query.message.reply_text(t("profile_delete_fail", lang))

    elif data == "reset_cache_only":
        context.user_data.clear()
        await query.message.reply_text(t("reset_cache_done", lang))

    elif data == "reset_all_confirm":
        clear_user_profiles(user_id)
        context.user_data.clear()
        await query.message.reply_text(t("reset_all_done", lang))

    # Навигационные переходы
    elif data == "nav_chart_img":
        active = get_user_natal_profile(user_id, context)
        if not active or not active.get("chart_data"):
            await query.message.reply_text(t("no_profile_found", lang))
            return
        status_map = {
            "ru": "🎨 Рисую карту Кундли D1...",
            "en": "🎨 Rendering Kundli D1 chart...",
            "it": "🎨 Disegno della carta Kundli D1...",
        }
        status_msg = await query.message.reply_text(status_map.get(lang, status_map["ru"]))
        try:
            b_dt = active.get("birth_dt")
            dob_s = b_dt.strftime("%d.%m.%Y") if b_dt else None
            tob_s = b_dt.strftime("%H:%M") if b_dt else None
            chart_img = render_kundli_chart(
                chart_data=active["chart_data"],
                profile_name=active.get("profile_name"),
                dob_str=dob_s,
                tob_str=tob_s,
                place_str=active.get("place_name"),
                lang=lang
            )
            try:
                await status_msg.delete()
            except Exception:
                pass
            caption = t("chart_ready_header", lang, name=active.get('profile_name', 'Профиль'))
            await query.message.reply_photo(
                photo=chart_img,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=get_chart_inline_keyboard(lang)
            )
        except Exception as e:
            logger.exception("Ошибка отправки изображения карты")
            await status_msg.edit_text(t("chart_img_error", lang, err=e))

    elif data == "nav_chart":
        profile = get_user_natal_profile(user_id, context)
        if profile:
            await show_active_profile_card(update, context, profile)
        else:
            await chart_start(update, context)

    elif data == "nav_dasha":
        await dasha_command(update, context)

    elif data == "nav_sadesati":
        await sadesati_command(update, context)

    elif data == "nav_yoga":
        await yoga_command(update, context)

    elif data == "nav_karma":
        await karma_command(update, context)

    elif data == "nav_money":
        await money_command(update, context)

    elif data == "nav_upaya":
        await upaya_command(update, context)

    elif data == "nav_ask":
        await ask_start(update, context)

    elif data == "nav_compat":
        await compat_start(update, context)

    elif data == "nav_prices":
        await prices_command(update, context)

    elif data == "nav_mydata":
        await mydata_command(update, context)

    elif data == "nav_help":
        await help_command(update, context)

    # Покупка услуг напрямую из меню /prices
    elif data == "buy_chart":
        await send_chart_invoice(update, context, lang=lang)

    elif data == "buy_dasha":
        await send_dasha_invoice(update, context, lang=lang)

    elif data == "buy_karma":
        await send_karma_invoice(update, context, lang=lang)

    elif data == "buy_money":
        await send_money_invoice(update, context, lang=lang)

    elif data == "buy_compat":
        await send_compat_invoice(update, context, lang=lang)

    elif data == "buy_ask":
        await send_ask_invoice(update, context, lang=lang)

    elif data == "buy_yoga":
        await send_yoga_invoice(update, context, lang=lang)

    elif data == "buy_bundle":
        await send_bundle_invoice(update, context, lang=lang)

    # Админские действия
    elif data == "admin_refresh":
        if user_id != ADMIN_USER_ID:
            await query.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        await query.answer("Статистика обновлена")
        text = format_admin_panel()
        try:
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_admin_inline_keyboard()
            )
        except Exception:
            pass

    elif data == "admin_test_pay":
        if user_id != ADMIN_USER_ID:
            await query.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        await query.answer("Отправляю тестовый инвойс на 1 ⭐️...")
        await send_test_invoice(update, context)

    elif data == "admin_get_backup":
        if user_id != ADMIN_USER_ID:
            await query.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        await query.answer("Отправляю файл базы...")
        backup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")
        if os.path.exists(backup_file):
            with open(backup_file, "rb") as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename="profiles.json",
                    caption="📁 Резервная копия базы профилей бота (JSON)"
                )
        else:
            await query.message.reply_text("Файл бэкапа пока не найден.")


async def handle_menu_text_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на постоянную нижнюю клавиатуру (ReplyKeyboardMarkup)."""
    text = update.message.text.strip() if update.message and update.message.text else ""
    user_id = update.effective_user.id
    action = MENU_BUTTON_ACTIONS.get(text)

    if action == "chart" or text == "🔮 Натальная карта":
        profile = get_user_natal_profile(user_id, context)
        if profile:
            return await show_active_profile_card(update, context, profile)
        else:
            return await chart_start(update, context)
    elif action == "profile" or text in ("👤 Мои профили", "👤 Профили", "📋 Мои данные", "🔄 Сменить профиль"):
        return await profile_command(update, context)
    elif action == "dasha" or text == "⏳ Периоды Даша":
        return await dasha_command(update, context)
    elif action == "sadesati" or text == "🪐 Саде-Сати":
        return await sadesati_command(update, context)
    elif action == "yoga" or text == "🧘 Детектор йог":
        return await yoga_command(update, context)
    elif action == "money" or text == "💰 Деньги и карьера":
        return await money_command(update, context)
    elif action == "karma" or text == "🔮 Кармическая задача":
        return await karma_command(update, context)
    elif action == "upaya" or text in ("🛡 Упайи (Гармонизация)", "🛡 Упайи (Коррекция)", "🛡 Упайи"):
        return await upaya_command(update, context)
    elif action == "compat" or text == "💞 Совместимость":
        return await compat_start(update, context)
    elif action == "ask" or text == "❓ Задать вопрос":
        return await ask_start(update, context)
    elif action == "prices" or text == "⭐️ Тарифы":
        return await prices_command(update, context)
    elif action == "help" or text == "📖 Справка":
        return await help_command(update, context)
    elif action == "lang" or text in ("🌐 Язык", "🌐 Language", "🌐 Lingua"):
        return await lang_command(update, context)


async def post_init(application: Application) -> None:
    """Регистрация списка команд в системном меню Telegram (кнопка [/] Меню) для RU, EN, IT."""
    commands_ru = [
        BotCommand("chart", "🔮 Составить натальную карту"),
        BotCommand("profile", "👤 Управление профилями"),
        BotCommand("rename", "✏️ Переименовать профиль"),
        BotCommand("newprofile", "➕ Добавить новый профиль"),
        BotCommand("dasha", "⏳ Периоды жизни (Даша)"),
        BotCommand("sadesati", "🪐 Калькулятор Саде-Сати"),
        BotCommand("yoga", "🧘 Детектор йог"),
        BotCommand("karma", "🔮 Кармическая задача (Атмакарака)"),
        BotCommand("money", "💰 Финансы и карьера"),
        BotCommand("upaya", "🛡 Ведические Упайи"),
        BotCommand("ask", "❓ Экспресс-вопрос ИИ"),
        BotCommand("compat", "💞 Совместимость с партнёром"),
        BotCommand("prices", "⭐️ Тарифы и Звёзды"),
        BotCommand("lang", "🌐 Выбор языка / Language"),
        BotCommand("mydata", "📋 Мои сохранённые данные"),
        BotCommand("reset", "🔄 Сброс данных"),
        BotCommand("help", "📖 Справка и помощь"),
    ]
    commands_en = [
        BotCommand("chart", "🔮 Calculate natal chart"),
        BotCommand("profile", "👤 Manage profiles"),
        BotCommand("rename", "✏️ Rename profile"),
        BotCommand("newprofile", "➕ Add new profile"),
        BotCommand("dasha", "⏳ Life periods (Dasha)"),
        BotCommand("sadesati", "🪐 Sade-Sati calculator"),
        BotCommand("yoga", "🧘 Yoga detector"),
        BotCommand("karma", "🔮 Soul karmic task"),
        BotCommand("money", "💰 Wealth & Career"),
        BotCommand("upaya", "🛡 Vedic remedies (Upayas)"),
        BotCommand("ask", "❓ Express AI question"),
        BotCommand("compat", "💞 Relationship compatibility"),
        BotCommand("prices", "⭐️ Prices & Stars"),
        BotCommand("lang", "🌐 Language selection"),
        BotCommand("mydata", "📋 Saved birth details"),
        BotCommand("reset", "🔄 Reset saved data"),
        BotCommand("help", "📖 User guide & help"),
    ]
    commands_it = [
        BotCommand("chart", "🔮 Calcola tema natale"),
        BotCommand("profile", "👤 Gestione profili"),
        BotCommand("rename", "✏️ Rinomina profilo"),
        BotCommand("newprofile", "➕ Aggiungi nuovo profilo"),
        BotCommand("dasha", "⏳ Periodi di vita (Dasha)"),
        BotCommand("sadesati", "🪐 Calcolatore Sade-Sati"),
        BotCommand("yoga", "🧘 Rilevatore Yoga"),
        BotCommand("karma", "🔮 Compito karmico dell'anima"),
        BotCommand("money", "💰 Denaro e carriera"),
        BotCommand("upaya", "🛡 Rimedi vedici (Upaya)"),
        BotCommand("ask", "❓ Domanda espressa all'IA"),
        BotCommand("compat", "💞 Compatibilità di coppia"),
        BotCommand("prices", "⭐️ Tariffe e Stelle"),
        BotCommand("lang", "🌐 Selezione lingua"),
        BotCommand("mydata", "📋 Dati salvati"),
        BotCommand("reset", "🔄 Reset dati"),
        BotCommand("help", "📖 Guida e comandi"),
    ]
    try:
        await application.bot.set_my_commands(commands_ru)
        await application.bot.set_my_commands(commands_en, language_code="en")
        await application.bot.set_my_commands(commands_it, language_code="it")
        logger.info("Системное меню команд Telegram успешно зарегистрировано для RU, EN, IT!")
    except Exception as e:
        logger.warning(f"Не удалось зарегистрировать команды меню Telegram: {e}")

    # Уведомление администратора при запуске на облачном сервере Render
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        try:
            await application.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=(
                    f"👑 *Джьотиш-Бот успешно запущен на сервере Render!*\n\n"
                    f"🌐 Публичный адрес: `{render_url}`\n"
                    f"💓 Self-Pinger: *активен* (каждые 9 мин)\n"
                    f"Сервер не уснёт и будет работать 24/7."
                ),
                parse_mode="Markdown"
            )
            logger.info(f"Уведомление о старте на Render отправлено администратору ({render_url})")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о запуске на Render: {e}")


import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Jyotish Bot is running 24/7!")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port_str = os.getenv("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"Healthcheck HTTP-сервер запущен на порту {port}")
    except Exception as e:
        logger.warning(f"Не удалось запустить healthcheck-сервер: {e}")


def start_keep_alive_pinger():
    """
    Автоматический фоновый пингер для удержания сервера активным 24/7.
    Бесплатный тариф Render усыпляет Web Service через 15 минут неактивности.
    Каждые 9 минут пингер отправляет HTTP GET на свой собственный адрес,
    регистрируя входящий веб-трафик и предотвращая засыпание контейнера.
    """
    external_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_URL")
    if not external_url:
        logger.info("RENDER_EXTERNAL_URL не задан, self-pinger отключён (локальный запуск).")
        return

    if not external_url.startswith("http"):
        external_url = f"https://{external_url}"
    ping_target = f"{external_url.rstrip('/')}/health"

    def _pinger_loop():
        import time
        import urllib.request
        logger.info(f"🚀 Запущен фоновый Self-Pinger для удержания сервера: {ping_target}")
        # Первый пинг через 3 минуты после старта
        time.sleep(180)
        while True:
            try:
                req = urllib.request.Request(
                    ping_target,
                    headers={"User-Agent": "JyotishBot-KeepAlive/1.0"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        logger.info(f"💓 Keep-alive пинг успешен ({ping_target})")
            except Exception as e:
                logger.warning(f"⚠️ Предупреждение keep-alive пинга ({ping_target}): {e}")
            time.sleep(540)  # каждые 9 минут

    t = threading.Thread(target=_pinger_loop, daemon=True)
    t.start()


def warmup_ephemeris():
    """Прогрев астрологического ядра и кэширование NASA эфемерид при старте."""
    try:
        logger.info("Прогрев астрологического ядра NASA JPL...")
        compute_chart(
            birth_dt=datetime(2000, 1, 1, 12, 0),
            lat=55.7558,
            lon=37.6173,
            tz_offset=3.0,
            name="Warmup"
        )
        logger.info("Эфемериды NASA JPL успешно закешированы!")
    except Exception as e:
        logger.warning(f"Ошибка прогрева эфемерид: {e}")


# ===================== ТОЧКА ВХОДА =====================



async def fallback_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик любого произвольного текста вне диалогов."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else 0
    lang = get_user_lang(update, context)

    # Проверим, может пользователь ввёл данные рождения одной строкой:
    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        return await chart_one_line_direct(update, context)

    fallback_msgs = {
        "ru": (
            "🙏 *Я на связи!*\n\n"
            "Чтобы составить гороскоп или рассчитать периоды, нажми на кнопку в меню ниже "
            "или воспользуйся быстрыми командами:\n\n"
            "• /chart — составить натальную карту\n"
            "• /dasha — периоды жизни (Вимшоттари Даша)\n"
            "• /money — анализ финансов и карьеры\n"
            "• /karma — кармическая задача (Атмакарака)\n"
            "• /sadesati — расчёт периода Саде-Сати\n"
            "• /yoga — поиск йог в гороскопе\n"
            "• /compat — совместимость партнёров\n"
            "• /ask — задать вопрос ИИ-астрологу\n"
            "• /profile — мои профили и переключение\n"
            "• /lang — выбор языка (RU/EN/IT)\n"
            "• /help — подробная справка"
        ),
        "en": (
            "🙏 *I am here!*\n\n"
            "To calculate a chart or life periods, tap a button in the menu below "
            "or use the quick commands:\n\n"
            "• /chart — calculate natal chart\n"
            "• /dasha — life periods (Vimshottari Dasha)\n"
            "• /money — wealth & career analysis\n"
            "• /karma — soul karmic task (Atmakaraka)\n"
            "• /sadesati — Sade-Sati transit calculator\n"
            "• /yoga — Vedic yoga detector\n"
            "• /compat — relationship compatibility\n"
            "• /ask — ask AI Astrologer a question\n"
            "• /profile — manage profiles & switch\n"
            "• /lang — select language (RU/EN/IT)\n"
            "• /help — user guide"
        ),
        "it": (
            "🙏 *Sono qui!*\n\n"
            "Per calcolare il tema natale o i periodi planetari, premi un pulsante nel menu sotto "
            "oppure usa i comandi rapidi:\n\n"
            "• /chart — calcola la carta natale\n"
            "• /dasha — periodi di vita (Vimshottari Dasha)\n"
            "• /money — analisi finanze e carriera\n"
            "• /karma — compito karmico dell'anima (Atmakaraka)\n"
            "• /sadesati — calcolo transito Sade-Sati\n"
            "• /yoga — rilevatore di yoga vedici\n"
            "• /compat — compatibilità di coppia\n"
            "• /ask — fai una domanda all'Astrologo IA\n"
            "• /profile — gestione profili e cambio\n"
            "• /lang — seleziona lingua (RU/EN/IT)\n"
            "• /help — guida comandi"
        ),
    }
    msg = fallback_msgs.get(lang, fallback_msgs["ru"])
    await update.effective_message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard(lang)
    )


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный перехватчик любых необработанных исключений."""
    logger.exception(f"Необработанное исключение: {context.error}")
    if isinstance(update, Update) and update.effective_message:
        try:
            lang = get_user_lang(update, context)
            err_msgs = {
                "ru": "⚠️ Произошла ошибка при обработке запроса. Пожалуйста, попробуй ещё раз или отправь команду /start",
                "en": "⚠️ An error occurred while processing your request. Please try again or send /start",
                "it": "⚠️ Si è verificato un errore durante l'elaborazione della richiesta. Riprova o invia /start",
            }
            await update.effective_message.reply_text(
                err_msgs.get(lang, err_msgs["ru"]),
                reply_markup=get_main_reply_keyboard(lang)
            )
        except Exception:
            pass

def main():
    init_db()
    start_health_server()
    start_keep_alive_pinger()
    warmup_ephemeris()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в .env файле!")
        print("Открой c:\\Users\\Aleksandr\\Documents\\Private\\jyotish-bot\\.env и укажи токен от @BotFather.")
        sys.exit(1)

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # Общие fallbacks для диалогов
    common_fallbacks = [
        CommandHandler("cancel", cancel_command),
        MessageHandler(filters.Regex(CANCEL_REGEX_PATTERN), cancel_command),
    ]

    # ConversationHandler для натальной карты
    chart_conv = ConversationHandler(
        entry_points=[
            CommandHandler("chart", chart_start),
            CommandHandler("natal", chart_start),
            CommandHandler(["edit", "recalc", "editprofile", "update"], edit_start),
            CommandHandler("newprofile", newprofile_start),
            MessageHandler(filters.Regex(r"^(🔮\s*Натальная карта|🔮\s*Natal Chart|🔮\s*Carta Natale)$"), chart_start),
            MessageHandler(filters.Regex(r"^(➕ Добавить профиль|➕ Новый профиль|➕ Add Profile|➕ Aggiungi Profilo)$"), newprofile_start),
            MessageHandler(filters.Regex(r"^(✏️\s*Изменить\s*(данные|профиль)?|🔄\s*Пересчитать\s*(карту|профиль)?|✏️\s*Edit\s*(details|profile)?|🔄\s*Recalculate|✏️\s*Modifica\s*(dati|profilo)?|🔄\s*Ricalcola)$"), edit_start),
            MessageHandler(one_line_filter, chart_one_line_direct),
            CallbackQueryHandler(newprofile_callback_start, pattern=r"^prof_add_start$"),
            CallbackQueryHandler(recalc_callback_start, pattern=r"^(?:prof_recalc_start|prof_recalc_\d+|prof_edit_\d+)$"),
        ],
        states={
            WAITING_PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name_received)],
            WAITING_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_dob_received)],
            WAITING_TOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_tob_received)],
            WAITING_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_place_received)],
        },
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    # ConversationHandler для совместимости
    compat_conv = ConversationHandler(
        entry_points=[
            CommandHandler("compat", compat_start),
            MessageHandler(filters.Regex(r"^(💞\s*Совместимость|💞\s*Compatibility|💞\s*Compatibilità)$"), compat_start),
        ],
        states={
            COMPAT_SELECT_PARTNER: [
                CallbackQueryHandler(compat_partner_selected, pattern=r"^compat_p_"),
            ],
            COMPAT_WAITING_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_dob_received)],
            COMPAT_WAITING_TOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_tob_received)],
            COMPAT_WAITING_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_place_received)],
        },
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    # ConversationHandler для экспресс-вопроса /ask
    ask_conv = ConversationHandler(
        entry_points=[
            CommandHandler("ask", ask_start),
            MessageHandler(filters.Regex(r"^(❓\s*Задать вопрос|❓\s*Ask a Question|❓\s*Fai una Domanda)$"), ask_start),
        ],
        states={
            ASK_WAITING_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question_received)],
        },
        fallbacks=common_fallbacks,
        allow_reentry=True,
    )

    # Регистрация команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prices", prices_command))
    app.add_handler(CommandHandler(["lang", "language"], lang_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("profiles", profile_command))
    app.add_handler(CommandHandler(["edit", "recalc", "editprofile", "update"], edit_start))
    app.add_handler(CommandHandler(["cleanprofiles", "cleanup", "dedup"], cleanup_profiles_command))
    app.add_handler(CommandHandler("rename", rename_command))
    app.add_handler(CommandHandler("mydata", mydata_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("dasha", dasha_command))
    app.add_handler(CommandHandler("sadesati", sadesati_command))
    app.add_handler(CommandHandler("yoga", yoga_command))
    app.add_handler(CommandHandler("karma", karma_command))
    app.add_handler(CommandHandler("money", money_command))
    app.add_handler(CommandHandler("upaya", upaya_command))
    app.add_handler(CommandHandler("admin", admin_command))

    # Регистрация диалогов
    app.add_handler(chart_conv)
    app.add_handler(compat_conv)
    app.add_handler(ask_conv)

    # Регистрация нажатий на инлайн-кнопки
    app.add_handler(CallbackQueryHandler(inline_nav_callback))

    # Регистрация нажатий на постоянную нижнюю клавиатуру
    app.add_handler(MessageHandler(filters.Regex(MENU_REGEX_PATTERN), handle_menu_text_button))

    # Регистрация платёжных хэндлеров (Telegram Stars)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Регистрация глобального обработчика ошибок и фолбэка текста
    app.add_error_handler(global_error_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text_handler))

    print("🚀 Джьотиш-бот успешно запущен с поддержкой Telegram Stars и интерактивной навигацией!")
    app.run_polling()


if __name__ == "__main__":
    main()

