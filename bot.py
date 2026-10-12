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
)

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
            "➕ Добавить профиль", "➕ Новый профиль", "❌ Отмена", "Отмена"
        }
        if text in menu_buttons:
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


# ===================== КЛАВИАТУРЫ И НАВИГАЦИЯ =====================

def get_main_reply_keyboard():
    """Постоянная нижняя клавиатура быстрого доступа (ReplyKeyboardMarkup)."""
    keyboard = [
        ["🔮 Натальная карта", "⏳ Периоды Даша"],
        ["💰 Деньги и карьера", "🔮 Кармическая задача"],
        ["🪐 Саде-Сати", "🧘 Детектор йог"],
        ["🛡 Упайи (Гармонизация)", "💞 Совместимость"],
        ["❓ Задать вопрос", "👤 Мои профили"],
        ["⭐️ Тарифы", "📖 Справка"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def get_start_inline_keyboard():
    """Инлайн-кнопки приветствия /start."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔮 Натальная карта", callback_data="nav_chart"),
            InlineKeyboardButton("👤 Мои профили", callback_data="prof_menu"),
        ],
        [
            InlineKeyboardButton("💰 Деньги и карьера", callback_data="nav_money"),
            InlineKeyboardButton("🔮 Кармическая задача", callback_data="nav_karma"),
        ],
        [
            InlineKeyboardButton("⭐️ Тарифы", callback_data="nav_prices"),
            InlineKeyboardButton("📖 Справка", callback_data="nav_help"),
        ],
    ])


def get_chart_inline_keyboard():
    """Инлайн-кнопки следующих шагов после расчета натальной карты."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Изображение карты (D1)", callback_data="nav_chart_img"),
        ],
        [
            InlineKeyboardButton("💰 Деньги и карьера", callback_data="nav_money"),
            InlineKeyboardButton("🔮 Кармическая задача", callback_data="nav_karma"),
        ],
        [
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
            InlineKeyboardButton("🪐 Саде-Сати", callback_data="nav_sadesati"),
        ],
        [
            InlineKeyboardButton("🧘 Детектор йог", callback_data="nav_yoga"),
            InlineKeyboardButton("🛡 Упайи (Гармонизация)", callback_data="nav_upaya"),
        ],
        [
            InlineKeyboardButton("❓ Задать вопрос", callback_data="nav_ask"),
            InlineKeyboardButton("💞 Совместимость", callback_data="nav_compat"),
        ],
        [
            InlineKeyboardButton("👤 Профили", callback_data="prof_menu"),
            InlineKeyboardButton("⭐️ Тарифы", callback_data="nav_prices"),
        ],
    ])


def get_karma_inline_keyboard():
    """Инлайн-кнопки после разбора кармической задачи души."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❓ Задать вопрос по карме", callback_data="nav_ask"),
            InlineKeyboardButton("💰 Финансы и карьера", callback_data="nav_money"),
        ],
        [
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
            InlineKeyboardButton("🛡 Упайи (Гармонизация)", callback_data="nav_upaya"),
        ],
        [
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
            InlineKeyboardButton("⭐️ Все тарифы", callback_data="nav_prices"),
        ],
    ])


def get_money_inline_keyboard():
    """Инлайн-кнопки после финансового анализа карты."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❓ Вопрос по финансам", callback_data="nav_ask"),
            InlineKeyboardButton("🔮 Кармическая задача", callback_data="nav_karma"),
        ],
        [
            InlineKeyboardButton("🧘 Детектор йог", callback_data="nav_yoga"),
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
        ],
        [
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
            InlineKeyboardButton("⭐️ Все тарифы", callback_data="nav_prices"),
        ],
    ])


def get_upaya_inline_keyboard():
    """Инлайн-кнопки после отображения ведических Упай."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❓ Задать вопрос по упайям", callback_data="nav_ask"),
            InlineKeyboardButton("🪐 Проверить Саде-Сати", callback_data="nav_sadesati"),
        ],
        [
            InlineKeyboardButton("💰 Деньги и карьера", callback_data="nav_money"),
            InlineKeyboardButton("🔮 Кармическая задача", callback_data="nav_karma"),
        ],
        [
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
            InlineKeyboardButton("⭐️ Все тарифы", callback_data="nav_prices"),
        ],
    ])


def get_dasha_inline_keyboard():
    """Инлайн-кнопки следующих шагов после показа периодов Даша."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🪐 Проверить Саде-Сати", callback_data="nav_sadesati"),
            InlineKeyboardButton("🧘 Найти йоги", callback_data="nav_yoga"),
        ],
        [
            InlineKeyboardButton("❓ Задать вопрос по Даша", callback_data="nav_ask"),
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
        ],
    ])


def get_sadesati_inline_keyboard():
    """Инлайн-кнопки следующих шагов после проверки Саде-Сати."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
            InlineKeyboardButton("🧘 Детектор йог", callback_data="nav_yoga"),
        ],
        [
            InlineKeyboardButton("❓ Вопрос астрологу", callback_data="nav_ask"),
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
        ],
    ])


def get_yoga_inline_keyboard():
    """Инлайн-кнопки следующих шагов после проверки йог."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❓ Вопрос по йогам", callback_data="nav_ask"),
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
        ],
        [
            InlineKeyboardButton("🪐 Саде-Сати", callback_data="nav_sadesati"),
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
        ],
    ])


def get_ask_inline_keyboard():
    """Инлайн-кнопки после ответа на экспресс-вопрос."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❓ Ещё один вопрос", callback_data="nav_ask"),
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
        ],
        [
            InlineKeyboardButton("🧘 Детектор йог", callback_data="nav_yoga"),
            InlineKeyboardButton("⭐️ Все тарифы", callback_data="nav_prices"),
        ],
    ])


def get_compat_inline_keyboard():
    """Инлайн-кнопки после анализа совместимости."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❓ Вопрос об отношениях", callback_data="nav_ask"),
            InlineKeyboardButton("⏳ Мои периоды", callback_data="nav_dasha"),
        ],
        [
            InlineKeyboardButton("🔮 Моя карта", callback_data="nav_mydata"),
            InlineKeyboardButton("⭐️ Тарифы", callback_data="nav_prices"),
        ],
    ])


# ===================== КОМАНДЫ БОТА =====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и описание возможностей бота."""
    user_id = update.effective_user.id
    active_profile = get_user_natal_profile(user_id, context)

    greeting = (
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
        "👉 /prices — стоимость услуг в Звёздах Telegram (⭐️)\n"
        "👉 /mydata — посмотреть сохранённые данные\n"
        "👉 /reset — сброс данных\n"
        "👉 /help — справка\n\n"
    )

    if active_profile:
        dt_str = active_profile["birth_dt"].strftime("%d.%m.%Y %H:%M")
        prof_name = active_profile.get("profile_name", "Мой гороскоп")
        place = active_profile.get("place_name", "")
        greeting += (
            f"👤 *Твой активный профиль:* «{prof_name}»\n"
            f"📅 Дата: `{dt_str}` | 📍 `{place}`\n\n"
            "Карта готова! Ты можешь сразу перейти к расчётам или управлять профилями через /profile.\n"
            "👇 *Выбери действие на кнопках ниже:*"
        )
    else:
        greeting += "👇 *Выбери действие на кнопках ниже или нажми /chart, чтобы начать:*"

    await update.effective_message.reply_text(
        greeting,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам."""
    help_text = (
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
        "🔹 /mydata — Показывает введённые дату, время и координаты активного профиля.\n"
        "🔹 /reset — Сброс сохранённых данных.\n"
        "🔹 /cancel — Отмена текущего шага ввода.\n\n"
        "💡 *Оплата:* Базовые расчёты бесплатны. Подробные трактовки оплачиваются в ⭐️ Telegram Stars прямо в приложении."
    )
    await update.effective_message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard()
    )


async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прайс-лист на услуги в Звёздах Telegram."""
    text = (
        "⭐️ *Прайс-лист на ИИ-разборы (Telegram Stars):*\n\n"
        f"🔮 **Полный разбор натальной карты:** `{PRICE_CHART_STARS} ⭐️`\n"
        "  • Характер, Лагна, миссия души, карьера, финансы, отношения, персональные упайи.\n\n"
        f"🔮 **Кармическая задача души (Атмакарака):** `{PRICE_KARMA_STARS} ⭐️`\n"
        "  • Расчёт 7 карак Джаймини, главные кармические уроки души и вектор предназначения.\n\n"
        f"💰 **Финансовый код и карьера:** `{PRICE_MONEY_STARS} ⭐️`\n"
        "  • Анализ 2-го и 11-го домов богатства, Дхана-йоги и стратегия заработка от ИИ.\n\n"
        f"⏳ **Разбор периодов Вимшоттари Даша:** `{PRICE_DASHA_STARS} ⭐️`\n"
        "  • Текущая Маха-Даша и Антар-Даша, уроки периода, точки роста, предостережения.\n\n"
        f"💞 **Анализ совместимости (Аштакута):** `{PRICE_COMPAT_STARS} ⭐️`\n"
        "  • 8 факторов гармонии, сексуальное притяжение (Йони), ментальное согласие, кармические узлы.\n\n"
        f"❓ **Экспресс-вопрос ИИ-астрологу:** `{PRICE_ASK_STARS} ⭐️`\n"
        "  • Задай любой вопрос по своей натальной карте и получи персональный ответ.\n\n"
        f"🧘 **Детектор йог + ИИ-трактовка:** `{PRICE_YOGA_STARS} ⭐️`\n"
        "  • Раджа-йога, Гаджакешари, Будхадитья, Дхана, Панча Махапуруша + разбор от ИИ.\n\n"
        f"🌟 **Бандл «Вся судьба 360°»:** `{PRICE_BUNDLE_STARS} ⭐️`\n"
        "  • Натальная карта + Даша + Йоги + 1 вопрос — всё в одном со скидкой!\n\n"
        "🆓 *Бесплатно:* базовые расчёты, /sadesati (Саде-Сати), /upaya (Ведические Упайи), 1-й вопрос к ИИ.\n\n"
        "✨ Оплата производится в 1 клик через официальные звёзды Telegram (Apple Pay / Google Pay / карты)."
    )
    prices_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🔮 Карта ({PRICE_CHART_STARS} ⭐️)", callback_data="buy_chart"),
            InlineKeyboardButton(f"⏳ Даша ({PRICE_DASHA_STARS} ⭐️)", callback_data="buy_dasha"),
        ],
        [
            InlineKeyboardButton(f"🔮 Карма ({PRICE_KARMA_STARS} ⭐️)", callback_data="buy_karma"),
            InlineKeyboardButton(f"💰 Деньги ({PRICE_MONEY_STARS} ⭐️)", callback_data="buy_money"),
        ],
        [
            InlineKeyboardButton(f"💞 Совместимость ({PRICE_COMPAT_STARS} ⭐️)", callback_data="buy_compat"),
            InlineKeyboardButton(f"❓ Вопрос ({PRICE_ASK_STARS} ⭐️)", callback_data="buy_ask"),
        ],
        [
            InlineKeyboardButton(f"🧘 Йоги ({PRICE_YOGA_STARS} ⭐️)", callback_data="buy_yoga"),
            InlineKeyboardButton(f"🌟 Бандл 360° ({PRICE_BUNDLE_STARS} ⭐️)", callback_data="buy_bundle"),
        ],
    ])
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=prices_keyboard
    )


async def show_active_profile_card(update: Update, context: ContextTypes.DEFAULT_TYPE, profile: dict):
    """Показать карточку активного профиля с быстрыми действиями."""
    dt_str = profile["birth_dt"].strftime("%d.%m.%Y")
    time_str = profile["birth_dt"].strftime("%H:%M")
    text = (
        f"🔮 *Активный профиль: «{profile['profile_name']}»*\n\n"
        f"📅 Дата: `{dt_str}`\n"
        f"⏰ Время: `{time_str}`\n"
        f"📍 Место: `{profile['place_name']}`\n"
        f"🌐 Координаты: `{profile['lat']:.4f}, {profile['lon']:.4f}` (UTC{profile['tz_offset']:+.1f})\n\n"
        "Натальная карта для этого профиля уже сохранена! Выбери действие:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Изображение карты", callback_data="nav_chart_img"),
            InlineKeyboardButton("📜 Полный разбор", callback_data="prof_view_active"),
        ],
        [
            InlineKeyboardButton("💰 Деньги и карьера", callback_data="nav_money"),
            InlineKeyboardButton("🔮 Кармическая задача", callback_data="nav_karma"),
        ],
        [
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
            InlineKeyboardButton("🪐 Саде-Сати", callback_data="nav_sadesati"),
        ],
        [
            InlineKeyboardButton("🧘 Детектор йог", callback_data="nav_yoga"),
            InlineKeyboardButton("🛡 Упайи (Гармонизация)", callback_data="nav_upaya"),
        ],
        [
            InlineKeyboardButton("👤 Мои профили", callback_data="prof_menu"),
            InlineKeyboardButton("➕ Новый профиль", callback_data="prof_add_start"),
        ],
        [
            InlineKeyboardButton("🔄 Пересчитать этот", callback_data="prof_recalc_start"),
        ],
    ])
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню управления профилями пользователя."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profiles = get_user_profiles(user_id)
    if not profiles:
        text = (
            "👤 *У тебя пока нет сохранённых профилей.*\n\n"
            "Создай свой первый астрологический профиль с помощью команды /chart или кнопки ниже:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔮 Создать натальную карту", callback_data="prof_add_start")],
        ])
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return

    lines = ["👤 *Твои астрологические профили:*\n"]
    buttons = []
    for i, p in enumerate(profiles, 1):
        status = "⭐️ [АКТИВЕН]" if p["is_active"] else "🔹"
        dt_str = p["birth_dt"].strftime("%d.%m.%Y %H:%M")
        lines.append(f"{i}. {status} *{p['profile_name']}*\n   📅 {dt_str} | 📍 {p['place_name']}")

        btn_text = f"⭐️ {p['profile_name']} (выбран)" if p["is_active"] else f"👉 Выбрать «{p['profile_name']}»"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"prof_switch_{p['id']}")])

    lines.append("\n_Нажми кнопку ниже, чтобы переключить профиль или добавить новый:_")

    buttons.append([
        InlineKeyboardButton("➕ Добавить профиль", callback_data="prof_add_start"),
        InlineKeyboardButton("🗑 Удалить профиль", callback_data="prof_delete_menu"),
    ])
    buttons.append([
        InlineKeyboardButton("📜 Показать карту", callback_data="prof_view_active"),
        InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
    ])

    keyboard = InlineKeyboardMarkup(buttons)
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=keyboard)


async def mydata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сохранённые данные активного профиля."""
    user_id = update.effective_user.id
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "У тебя пока нет сохранённой натальной карты.\nНажми кнопку ниже или /chart, чтобы составить её!",
            reply_markup=get_main_reply_keyboard()
        )
        return

    all_profs = get_user_profiles(user_id)
    text = (
        f"📋 *Сохранённые данные профиля «{profile.get('profile_name', 'Мой гороскоп')}»:*\n\n"
        f"📅 Дата: `{profile['birth_dt'].strftime('%d.%m.%Y')}`\n"
        f"⏰ Время: `{profile['birth_dt'].strftime('%H:%M')}`\n"
        f"📍 Место: `{profile['place_name']}`\n"
        f"🌐 Координаты: `{profile['lat']:.4f}, {profile['lon']:.4f}` (UTC{profile['tz_offset']:+.1f})\n"
        f"👥 Всего профилей в памяти: {len(all_profs)}\n\n"
        "Чтобы посмотреть карту или сменить профиль, используй кнопки ниже:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📜 Показать карту", callback_data="prof_view_active"),
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
        ],
        [
            InlineKeyboardButton("👤 Все профили", callback_data="prof_menu"),
            InlineKeyboardButton("➕ Новый профиль", callback_data="prof_add_start"),
        ],
    ])
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить сохранённые данные или профили."""
    user_id = update.effective_user.id
    profiles = get_user_profiles(user_id)
    if not profiles:
        context.user_data.clear()
        await update.effective_message.reply_text(
            "Данные сессии очищены. Профилей в базе не найдено. Чтобы создать карту, нажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    text = (
        "⚠️ *Управление сбросом данных*\n\n"
        f"В базе данных сохранено профилей: *{len(profiles)}*.\n"
        "Что именно ты хочешь сделать?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Очистить кэш сессии", callback_data="reset_cache_only")],
        [InlineKeyboardButton("🗑 Удалить ВСЕ профили из базы", callback_data="reset_all_confirm")],
        [InlineKeyboardButton("👤 Перейти в управление профилями", callback_data="prof_menu")],
    ])
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переименовать активный астрологический профиль."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "У тебя пока нет сохранённого профиля. Нажми /chart, чтобы создать его!",
            reply_markup=get_main_reply_keyboard()
        )
        return

    text = update.message.text.strip() if update.message and update.message.text else ""
    args = re.sub(r"^/rename\b\s*", "", text, flags=re.IGNORECASE).strip()
    if not args:
        await update.effective_message.reply_text(
            f"Текущее имя активного профиля: *«{profile['profile_name']}»*.\n\n"
            "Чтобы переименовать его, укажи новое имя:\n"
            "👉 `/rename Александр`",
            parse_mode="Markdown"
        )
        return

    if len(args) > 50:
        await update.effective_message.reply_text("Имя профиля не должно превышать 50 символов.")
        return

    if rename_profile(profile["id"], user_id, args):
        updated = get_profile_by_id(profile["id"], user_id)
        if context is not None and context.user_data is not None:
            context.user_data["natal_profile"] = updated
        await update.effective_message.reply_text(
            f"✅ Профиль успешно переименован в *«{args}»*!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📜 Показать карту", callback_data="prof_view_active"),
                    InlineKeyboardButton("👤 Все профили", callback_data="prof_menu"),
                ]
            ])
        )
    else:
        await update.effective_message.reply_text("Не удалось переименовать профиль. Попробуй позже.")


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
    dt = datetime.combine(dob, tob)
    status_msg = await update.effective_message.reply_text("🌍 Определяю координаты и часовой пояс города...")

    try:
        lat, lon, tz_offset, address = resolve_location(place_input, target_date=dt)
    except Exception as e:
        if context is not None and context.user_data is not None:
            context.user_data["temp_dob"] = dob
            context.user_data["temp_tob"] = tob
            if profile_name:
                context.user_data["temp_profile_name"] = profile_name
            context.user_data["editing_profile_id"] = editing_id

        await status_msg.edit_text(
            f"❌ Не удалось найти город '{place_input}'.\n"
            f"Ошибка: {e}\n\n"
            "Пожалуйста, укажи город ещё раз (или нажми /cancel):"
        )
        return WAITING_PLACE

    await status_msg.edit_text("🧮 Вычисляю позиции планет и домов по NASA JPL эфемеридам...")

    try:
        user_id = (
            update.effective_user.id
            if update.effective_user
            else (update.callback_query.from_user.id if update.callback_query else 0)
        )
        first_name = update.effective_user.first_name if update.effective_user else "User"
        chart_name = profile_name or first_name or "User"
        chart_data = compute_chart(
            birth_dt=dt,
            lat=lat,
            lon=lon,
            tz_offset=tz_offset,
            name=chart_name
        )
        summary = format_chart_summary(chart_data)

        # Сохраняем в базу данных SQLite (jyotish.db)
        if not profile_name:
            existing = get_user_profiles(user_id)
            if not existing:
                profile_name = "Мой гороскоп"
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
            )
            await update.effective_message.reply_photo(
                photo=chart_img,
                caption=f"🔮 *Ведическая карта Кундли (D1): {profile_name}*",
                parse_mode="Markdown"
            )
        except Exception as img_err:
            logger.warning(f"Не удалось отправить изображение карты: {img_err}")

        header = f"🎉 *Профиль «{profile_name}» сохранён в базу!*\n\n"
        await send_split_message(update, header + summary)

    except Exception as e:
        logger.exception("Ошибка расчёта карты")
        await status_msg.edit_text(f"❌ Ошибка при расчёте карты: {e}")
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        await update.effective_message.reply_text(
            "ℹ️ *Астрономический расчёт готов!*\n\n"
            "Для подключения глубокой текстовой трактовки карты от ИИ добавь `GEMINI_API_KEY` в файл `.env`.",
            parse_mode="Markdown",
            reply_markup=get_chart_inline_keyboard()
        )
        return ConversationHandler.END

    # Проверка монетизации (если включен платный режим)
    has_paid = context.user_data.get("paid_chart", False) if context and context.user_data else False
    if PAYMENT_REQUIRED and not has_paid:
        await update.effective_message.reply_text(
            "🌟 *Натальная карта успешно построена!*\n\n"
            "Хочешь получить подробную расшифровку судьбы, предназначения, сильных сторон и кармических уроков от ИИ-астролога?\n"
            f"Стоимость разбора: **{PRICE_CHART_STARS} ⭐️**",
            parse_mode="Markdown",
            reply_markup=get_chart_inline_keyboard()
        )
        await send_chart_invoice(update, context)
        return ConversationHandler.END

    # Если оплачено или в бесплатном режиме:
    ai_status = await update.effective_message.reply_text("🔮 ИИ-Астролог составляет подробную трактовку твоей карты...")
    try:
        interpretation = await gemini.interpret_chart(chart_data, summary)
        await ai_status.delete()
        await send_split_message(
            update,
            f"📜 *Интерпретация карты от ИИ:*\n\n{interpretation}",
            reply_markup=get_chart_inline_keyboard()
        )
    except Exception as e:
        logger.exception("Ошибка генерации Gemini")
        await ai_status.edit_text(f"⚠️ Не удалось получить ответ ИИ: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_chart_inline_keyboard()
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
    name = parsed.get("name")
    if not name:
        existing = get_user_profiles(user_id)
        name = "Мой гороскоп" if not existing else f"Профиль {len(existing) + 1}"

    return await process_and_save_chart(
        update=update,
        context=context,
        profile_name=name,
        dob=parsed["dob"],
        tob=parsed["tob"],
        place_input=parsed["city"],
        editing_id=None
    )


async def newprofile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /newprofile: начало создания дополнительного профиля."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    context.user_data["editing_profile_id"] = None

    msg_text = update.message.text.strip() if update.message and isinstance(getattr(update.message, "text", None), str) else ""
    cmd_args = re.sub(r"^/newprofile\b\s*", "", msg_text, flags=re.IGNORECASE).strip()
    if cmd_args:
        parsed = parse_one_line_profile(cmd_args)
        if parsed and parsed.get("is_complete"):
            name = parsed.get("name")
            if not name:
                existing = get_user_profiles(user_id)
                name = f"Профиль {len(existing) + 1}"
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
        "👤 *Создание нового астрологического профиля*\n\n"
        "Введи данные одной строкой:\n"
        "`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n"
        "_(например: `Анна, 20.08.1992, 14:15, Санкт-Петербург`)_\n\n"
        "Или укажи только имя профиля _(например: `Жена`, `Анна`)_ для пошагового ввода.\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return WAITING_PROFILE_NAME


async def newprofile_callback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажатие инлайн-кнопки «➕ Добавить профиль»."""
    query = update.callback_query
    await query.answer()
    context.user_data["editing_profile_id"] = None
    await query.message.reply_text(
        "👤 *Создание нового астрологического профиля*\n\n"
        "Введи данные одной строкой:\n"
        "`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n"
        "_(например: `Анна, 20.08.1992, 14:15, Санкт-Петербург`)_\n\n"
        "Или укажи только имя профиля _(например: `Жена`, `Анна`)_ для пошагового ввода.\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return WAITING_PROFILE_NAME


async def recalc_callback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Нажатие инлайн-кнопки «🔄 Пересчитать текущий»."""
    query = update.callback_query
    await query.answer()
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    active = get_user_natal_profile(user_id, context)
    name = active["profile_name"] if active else "Мой гороскоп"
    context.user_data["temp_profile_name"] = name
    context.user_data["editing_profile_id"] = active["id"] if active else None

    await query.message.reply_text(
        f"🔄 *Пересчёт профиля «{name}»*\n\n"
        "Введи новые данные одной строкой:\n"
        "`ДД.ММ.ГГГГ, ЧЧ:ММ, Город` (например: `15.05.1990, 10:30, Москва`)\n\n"
        "Или начни с даты рождения в формате `ДД.ММ.ГГГГ`:\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def profile_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение имени нового профиля или полной строки с данными."""
    text = update.message.text.strip()
    if text.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or "Новый профиль"
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
        name = parsed.get("name") or "Новый профиль"
        context.user_data["temp_profile_name"] = name
        context.user_data["temp_dob"] = parsed["dob"]
        if parsed.get("tob"):
            context.user_data["temp_tob"] = parsed["tob"]
            await update.message.reply_text(
                "📍 *Шаг 3 из 3:* Введи город рождения\n"
                "_(Например: `Москва`, `Рим`, `Дели`, `Санкт-Петербург`)_:",
                parse_mode="Markdown"
            )
            return WAITING_PLACE
        await update.message.reply_text(
            "⏰ *Шаг 2 из 3:* Введи точное время рождения в формате `ЧЧ:ММ` (24 часа)\n"
            "_(Например: `10:30` или `23:45`)_:\n\n"
            "Если точное время неизвестно, укажи `12:00`.",
            parse_mode="Markdown"
        )
        return WAITING_TOB

    if not text or len(text) > 50:
        await update.message.reply_text("Пожалуйста, укажи понятное имя (до 50 символов):")
        return WAITING_PROFILE_NAME

    context.user_data["temp_profile_name"] = text
    await update.message.reply_text(
        f"👤 Профиль: *{text}*\n\n"
        "Введи данные одной строкой:\n"
        "`ДД.ММ.ГГГГ, ЧЧ:ММ, Город` (например: `15.05.1990, 10:30, Москва`)\n\n"
        "Или начни с даты рождения в формате `ДД.ММ.ГГГГ`:\n\n"
        "Для отмены набери /cancel",
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

    msg_text = update.message.text.strip() if update.message and isinstance(getattr(update.message, "text", None), str) else ""
    cmd_args = re.sub(r"^/(?:chart|natal)\b\s*", "", msg_text, flags=re.IGNORECASE).strip()
    if cmd_args:
        parsed = parse_one_line_profile(cmd_args)
        if parsed and parsed.get("is_complete"):
            name = parsed.get("name")
            if not name:
                existing = get_user_profiles(user_id)
                name = "Мой гороскоп" if not existing else f"Профиль {len(existing) + 1}"
            return await process_and_save_chart(
                update=update,
                context=context,
                profile_name=name,
                dob=parsed["dob"],
                tob=parsed["tob"],
                place_input=parsed["city"],
                editing_id=None
            )

    active_profile = get_user_natal_profile(user_id, context)
    if active_profile:
        await show_active_profile_card(update, context, active_profile)
        return ConversationHandler.END

    context.user_data["temp_profile_name"] = "Мой гороскоп"
    context.user_data["editing_profile_id"] = None

    await update.effective_message.reply_text(
        "🔮 *Составление натальной карты*\n\n"
        "Введи данные одной строкой:\n"
        "`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n"
        "_(например: `Александр, 15.05.1990, 10:30, Москва`)_\n\n"
        "Или начни с даты рождения (`ДД.ММ.ГГГГ`), и мы заполним данные пошагово.\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def chart_dob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты рождения или строки с полными данными."""
    text = update.message.text.strip()
    if text.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or context.user_data.get("temp_profile_name")
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
        if parsed.get("name"):
            context.user_data["temp_profile_name"] = parsed["name"]
        context.user_data["temp_dob"] = parsed["dob"]
        if parsed.get("tob"):
            context.user_data["temp_tob"] = parsed["tob"]
            await update.message.reply_text(
                "📍 *Шаг 3 из 3:* Введи город рождения\n"
                "_(Например: `Москва`, `Рим`, `Дели`, `Алматы`, `Санкт-Петербург`)_:",
                parse_mode="Markdown"
            )
            return WAITING_PLACE

        await update.message.reply_text(
            "⏰ *Шаг 2 из 3:* Введи точное время рождения в формате `ЧЧ:ММ` (24 часа)\n"
            "_(Например: `10:30` или `23:45`)_\n\n"
            "Если точное время неизвестно, укажи `12:00`.",
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
                f"👤 Запомнил имя: *{text}*!\n\n"
                "Теперь введи дату рождения (`ДД.ММ.ГГГГ`), например: `20.06.1996`\n"
                "или отправь остальные данные одной строкой (`ДД.ММ.ГГГГ, ЧЧ:ММ, Город`):",
                parse_mode="Markdown"
            )
            return WAITING_DOB

        await update.message.reply_text(
            "⚠️ Неверный формат даты.\n\n"
            "Введи данные одной строкой:\n"
            "`Имя, ДД.ММ.ГГГГ, ЧЧ:ММ, Город`\n"
            "_(например: `Александр, 15.05.1990, 10:30, Москва`)_\n\n"
            "Или укажи только дату в виде `ДД.ММ.ГГГГ` (например: `15.05.1990`):",
            parse_mode="Markdown"
        )
        return WAITING_DOB

    await update.message.reply_text(
        "⏰ *Шаг 2 из 3:* Введи точное время рождения в формате `ЧЧ:ММ` (24 часа)\n"
        "_(Например: `10:30` или `23:45`)_\n\n"
        "Если точное время неизвестно, укажи `12:00`.",
        parse_mode="Markdown"
    )
    return WAITING_TOB


async def chart_tob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени рождения или полной строки данных."""
    text = update.message.text.strip()
    if text.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    # Проверяем, не ввёл ли пользователь полную строку данных
    parsed = parse_one_line_profile(text)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or context.user_data.get("temp_profile_name")
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
                    "⚠️ Неверный формат времени. Пожалуйста, укажи в виде `ЧЧ:ММ` (например: `10:30`):",
                    parse_mode="Markdown"
                )
                return WAITING_TOB

    await update.message.reply_text(
        "📍 *Шаг 3 из 3:* Введи город рождения\n"
        "_(Например: `Москва`, `Рим`, `Дели`, `Алматы`, `Санкт-Петербург`)_:",
        parse_mode="Markdown"
    )
    return WAITING_PLACE


async def chart_place_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение города, геокодинг, расчёт карты и генерация ИИ-интерпретации."""
    place_input = update.message.text.strip()
    if place_input.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    # Проверяем, не ввёл ли пользователь полную строку данных
    parsed = parse_one_line_profile(place_input)
    if parsed and parsed.get("is_complete"):
        name = parsed.get("name") or context.user_data.get("temp_profile_name")
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

    dob = context.user_data.get("temp_dob")
    tob = context.user_data.get("temp_tob")

    if not dob or not tob:
        await update.message.reply_text("Произошла ошибка сессии. Начни заново с /chart.")
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
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    chart_data = profile["chart_data"]
    summary = profile["summary"]
    dasha_raw = format_dasha_periods(chart_data)
    dasha_text = f"👤 *Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»*\n\n" + dasha_raw

    gemini = get_gemini_client()
    if not gemini:
        await send_split_message(update, dasha_text, reply_markup=get_dasha_inline_keyboard())
        await update.effective_message.reply_text(
            "💡 Чтобы получить анализ текущего периода жизни от ИИ, добавь `GEMINI_API_KEY` в файл `.env`.",
            reply_markup=get_dasha_inline_keyboard()
        )
        return

    has_paid = context.user_data.get("paid_dasha", False)
    if PAYMENT_REQUIRED and not has_paid:
        await send_split_message(update, dasha_text)
        await update.effective_message.reply_text(
            "⏳ *Периоды рассчитаны!*\n\n"
            "Чтобы получить глубокий анализ текущего планетного периода (Маха-Даша и Антар-Даша) от ИИ с рекомендациями упай:\n"
            f"Стоимость разбора: **{PRICE_DASHA_STARS} ⭐️**",
            parse_mode="Markdown",
            reply_markup=get_dasha_inline_keyboard()
        )
        await send_dasha_invoice(update, context)
        return

    await send_split_message(update, dasha_text)
    status_msg = await update.effective_message.reply_text("🔮 Анализирую текущий период жизни через ИИ...")
    try:
        interpretation = await gemini.interpret_dasha(chart_data, summary)
        await status_msg.delete()
        await send_split_message(
            update,
            f"🌟 *Анализ текущего периода жизни:*\n\n{interpretation}",
            reply_markup=get_dasha_inline_keyboard()
        )
    except Exception as e:
        logger.exception("Ошибка анализа даша")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе даша: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_dasha_inline_keyboard()
        )


# ===================== ДИАЛОГ СОВМЕСТИМОСТИ =====================

def format_kuja_compatibility(chart1: dict, chart2: dict, name1: str = "Партнёр 1", name2: str = "Партнёр 2") -> str:
    """Сравнительный анализ поражения Марсом (Куджа-Доша / Манглика) для обоих партнёров."""
    k1 = check_kuja_dosha(chart1)
    k2 = check_kuja_dosha(chart2)
    has1 = k1.get("has_dosha", False)
    has2 = k2.get("has_dosha", False)
    lines = ["🔥 *Анализ Куджа-Доши (Манглика в отношениях):*"]
    desc1 = f"• *{name1}*: Марс в доме {k1.get('mars_house')} ({k1.get('mars_sign_ru')}). "
    if has1:
        desc1 += "⚠️ Присутствует Куджа-Доша (повышенная страстность и требовательность)."
    elif k1.get("is_cancelled"):
        desc1 += f"✅ Манглика нейтрализована ({k1.get('cancel_reason')})."
    else:
        desc1 += "✅ Куджа-Доша отсутствует."
    lines.append(desc1)

    desc2 = f"• *{name2}*: Марс в доме {k2.get('mars_house')} ({k2.get('mars_sign_ru')}). "
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
    my_profile = get_user_natal_profile(user_id, context)
    if not my_profile:
        await update.effective_message.reply_text(
            "Для анализа совместимости сначала нужен твой сохранённый профиль!\n"
            "Нажми /chart, чтобы составить свою карту, затем вернись в /compat."
        )
        return ConversationHandler.END

    all_profs = get_user_profiles(user_id)
    other_profs = [p for p in all_profs if p["id"] != my_profile["id"]]

    if other_profs:
        text = (
            "💞 *Анализ совместимости партнёров (Кута / Аштакута)*\n\n"
            f"Твой активный профиль: *«{my_profile['profile_name']}»* "
            f"({my_profile['birth_dt'].strftime('%d.%m.%Y')}, {my_profile['place_name']}).\n\n"
            "Выбери второго человека из сохранённых профилей или введи новые данные:"
        )
        buttons = []
        for p in other_profs:
            buttons.append([InlineKeyboardButton(f"💞 {p['profile_name']} ({p['birth_dt'].strftime('%d.%m.%Y')})", callback_data=f"compat_p_{p['id']}")])
        buttons.append([InlineKeyboardButton("✏️ Ввести новые данные вручную", callback_data="compat_p_manual")])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return COMPAT_SELECT_PARTNER

    await update.effective_message.reply_text(
        "💞 *Анализ совместимости партнёров (Кута / Аштакута)*\n\n"
        f"Твой профиль (*«{my_profile['profile_name']}»*) уже сохранён.\n"
        "Теперь введи данные *партнёра*.\n\n"
        "📅 *Шаг 1 из 3:* Дата рождения партнёра `ДД.ММ.ГГГГ` (например: `20.08.1992`):\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_DOB


async def compat_partner_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор партнёра из сохранённых профилей или переход к ручному вводу."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    my_profile = get_user_natal_profile(user_id, context)

    if data == "compat_p_manual":
        await query.message.reply_text(
            "📅 *Шаг 1 из 3:* Введи дату рождения партнёра `ДД.ММ.ГГГГ` (например: `20.08.1992`):\n\n"
            "Для отмены набери /cancel",
            parse_mode="Markdown"
        )
        return COMPAT_WAITING_DOB

    if data.startswith("compat_p_"):
        partner_id = int(data.split("compat_p_")[1])
        partner_profile = get_profile_by_id(partner_id, user_id)
        if not partner_profile:
            await query.message.reply_text("Профиль партнёра не найден. Попробуй снова: /compat")
            return ConversationHandler.END

        partner_chart = partner_profile["chart_data"]
        partner_summary = partner_profile["summary"]
        context.user_data["partner_chart"] = partner_chart
        context.user_data["partner_summary"] = partner_summary

        status_msg = await query.message.reply_text(
            f"💞 Сопоставляю карты *{my_profile['profile_name']}* и *{partner_profile['profile_name']}*..."
        )

        kuja_text = format_kuja_compatibility(
            my_profile["chart_data"],
            partner_chart,
            my_profile.get("profile_name", "Партнёр 1"),
            partner_profile.get("profile_name", "Партнёр 2")
        )

        gemini = get_gemini_client()
        if not gemini:
            await status_msg.edit_text(
                f"ℹ️ *Карты обоих партнёров загружены!*\n\n{kuja_text}\n\n"
                "Для детального анализа совместимости от ИИ добавь `GEMINI_API_KEY` в `.env`.",
                parse_mode="Markdown",
                reply_markup=get_compat_inline_keyboard()
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
            await send_compat_invoice(update, context)
            return ConversationHandler.END

        try:
            result = await gemini.interpret_compatibility(
                chart1_data=my_profile["chart_data"],
                chart1_summary=my_profile["summary"],
                chart2_data=partner_chart,
                chart2_summary=partner_summary,
            )
            await status_msg.delete()
            header = f"💘 *Совместимость: {my_profile['profile_name']} ❤️ {partner_profile['profile_name']}*\n\n{kuja_text}\n\n"
            await send_split_message(
                update,
                header + result,
                reply_markup=get_compat_inline_keyboard()
            )
        except Exception as e:
            logger.exception("Ошибка совместимости")
            await status_msg.edit_text(f"⚠️ Ошибка при анализе: {e}")
            await update.effective_message.reply_text(
                "Выбери следующее действие:",
                reply_markup=get_compat_inline_keyboard()
            )

        return ConversationHandler.END

    return ConversationHandler.END


async def compat_dob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты партнёра."""
    text = update.message.text.strip()
    if text.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    try:
        dob = datetime.strptime(text, "%d.%m.%Y").date()
        context.user_data["compat_dob"] = dob
    except ValueError:
        await update.message.reply_text(
            "⚠️ Неверный формат. Укажи дату партнёра как `ДД.ММ.ГГГГ` (например: `20.08.1992`):",
            parse_mode="Markdown"
        )
        return COMPAT_WAITING_DOB

    await update.message.reply_text(
        "⏰ *Шаг 2 из 3:* Время рождения партнёра `ЧЧ:ММ` (например: `14:20` или `12:00`):",
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_TOB


async def compat_tob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение времени партнёра."""
    text = update.message.text.strip()
    if text.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    try:
        tob = datetime.strptime(text, "%H:%M").time()
        context.user_data["compat_tob"] = tob
    except ValueError:
        await update.message.reply_text(
            "⚠️ Неверный формат. Укажи время партнёра как `ЧЧ:ММ` (например: `14:20`):",
            parse_mode="Markdown"
        )
        return COMPAT_WAITING_TOB

    await update.message.reply_text(
        "📍 *Шаг 3 из 3:* Город рождения партнёра (например: `Санкт-Петербург`, `Рим`, `Минск`):",
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_PLACE


async def compat_place_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расчёт второй карты и сравнительный анализ."""
    place_input = update.message.text.strip()
    if place_input.lower() in ("отмена", "❌ отмена", "/cancel"):
        return await cancel_command(update, context)

    dob = context.user_data.get("compat_dob")
    tob = context.user_data.get("compat_tob")
    user_id = update.effective_user.id
    my_profile = get_user_natal_profile(user_id, context)

    if not dob or not tob or not my_profile:
        await update.message.reply_text("Сессия истекла. Начни заново с /compat.")
        return ConversationHandler.END

    dt = datetime.combine(dob, tob)
    status_msg = await update.message.reply_text("🌍 Вычисляю координаты и строю карту партнёра...")

    try:
        lat, lon, tz_offset, address = resolve_location(place_input, target_date=dt)
        partner_chart = compute_chart(
            birth_dt=dt,
            lat=lat,
            lon=lon,
            tz_offset=tz_offset,
            name="Партнёр"
        )
        partner_summary = format_chart_summary(partner_chart)
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
        await status_msg.edit_text(f"❌ Не удалось рассчитать карту партнёра: {e}")
        return ConversationHandler.END

    kuja_text = format_kuja_compatibility(
        my_profile["chart_data"],
        partner_chart,
        my_profile.get("profile_name", "Партнёр 1"),
        "Партнёр 2"
    )

    gemini = get_gemini_client()
    if not gemini:
        await status_msg.edit_text(
            f"ℹ️ *Карта партнёра построена!*\n\n{kuja_text}\n\n"
            "Для анализа совместимости от ИИ добавь `GEMINI_API_KEY` в `.env`.",
            parse_mode="Markdown",
            reply_markup=get_compat_inline_keyboard()
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
        await send_compat_invoice(update, context)
        return ConversationHandler.END

    await status_msg.edit_text("💞 ИИ сопоставляет две карты по системе Аштакута...")
    try:
        result = await gemini.interpret_compatibility(
            chart1_data=my_profile["chart_data"],
            chart1_summary=my_profile["summary"],
            chart2_data=partner_chart,
            chart2_summary=partner_summary,
        )
        await status_msg.delete()
        await send_split_message(
            update,
            f"💘 *Анализ совместимости парных карт:*\n\n{kuja_text}\n\n{result}",
            reply_markup=get_compat_inline_keyboard()
        )

    except Exception as e:
        logger.exception("Ошибка совместимости")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_compat_inline_keyboard()
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
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    status_msg = await update.effective_message.reply_text("🪐 Вычисляю положение транзитного Сатурна...")
    try:
        chart_data = profile["chart_data"]
        result = check_sade_sati(chart_data)
        prof_title = f" (Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»)"

        moon_ru = result.get("natal_moon_sign_ru") or result.get("natal_moon_sign")
        saturn_ru = result.get("transit_saturn_sign_ru") or result.get("saturn_sign")

        if result["active"]:
            phase_names = {
                "rising": "🌅 Восходящая фаза (Сатурн в 12-м знаке от Луны)",
                "peak": "🔥 Пиковая фаза (Сатурн в знаке натальной Луны)",
                "setting": "🌇 Нисходящая фаза (Сатурн во 2-м знаке от Луны)",
            }
            phase_text = phase_names.get(result["phase"], result["phase"])
            cyc = result.get("current_cycle") or {}
            cur_p_start = cyc.get("phase_start_ru", "")
            cur_p_end = cyc.get("phase_end_ru", "")
            full_end = cyc.get("end_date_ru", "")
            start_dt = cyc.get("start_date_ru", "")

            date_block = (
                f"📅 *Даты текущего периода:*\n"
                f"• Начало Саде-Сати: *{start_dt}*\n"
                f"• Текущая фаза: с *{cur_p_start}* по *{cur_p_end}*\n"
                f"• 🏁 *Полное окончание Саде-Сати: {full_end}*\n\n"
            ) if cyc else ""

            text = (
                f"🪐 *Саде-Сати — АКТИВЕН!*{prof_title}\n\n"
                f"🌙 Твоя натальная Луна: *{moon_ru}*\n"
                f"🪐 Транзитный Сатурн: *{saturn_ru}*\n\n"
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
                f"🌙 Твоя натальная Луна: *{moon_ru}*\n"
                f"🪐 Транзитный Сатурн: *{saturn_ru}*\n\n"
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
            reply_markup=get_sadesati_inline_keyboard()
        )

    except Exception as e:
        logger.exception("Ошибка проверки Саде-Сати")
        await status_msg.edit_text(f"⚠️ Ошибка при проверке Саде-Сати: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_sadesati_inline_keyboard()
        )


# ===================== ДЕТЕКТОР ЙОГ =====================

async def yoga_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Найти йоги (мощные комбинации планет) в натальной карте."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    chart_data = profile["chart_data"]

    status_msg = await update.effective_message.reply_text("🧘 Анализирую натальную карту на наличие йог...")
    try:
        yogas = detect_yogas(chart_data)
        active_yogas = [y for y in yogas if y.get("active", False)]
        prof_name = profile.get("profile_name", "Мой гороскоп")

        if not active_yogas:
            await status_msg.edit_text(
                f"🧘 *Детектор йог — Профиль «{prof_name}»*\n\n"
                "В карте не обнаружено классических йог из базового набора.\n"
                "Это не означает слабую карту — многие благоприятные комбинации "
                "требуют более глубокого анализа варг (дробных карт).",
                parse_mode="Markdown"
            )
            await update.effective_message.reply_text(
                "Выбери следующее действие:",
                reply_markup=get_yoga_inline_keyboard()
            )
            return

        # Формируем список найденных йог
        yoga_lines = []
        for y in active_yogas:
            name = y.get("name_ru", y.get("name", "Йога"))
            desc = y.get("description", "")
            planets = ", ".join(y.get("planets", []))
            yoga_lines.append(f"✨ *{name}*\n   {desc}\n   🪐 Планеты: {planets}")

        yoga_text = (
            f"🧘 *Детектор йог — Профиль «{prof_name}»*\n"
            f"Найдено йог: {len(active_yogas)}\n\n"
            + "\n\n".join(yoga_lines)
        )

        await status_msg.delete()
        await send_split_message(update, yoga_text)

    except Exception as e:
        logger.exception("Ошибка детектора йог")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе йог: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_yoga_inline_keyboard()
        )
        return

    # ИИ-интерпретация йог
    gemini = get_gemini_client()
    if not gemini or not active_yogas:
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_yoga_inline_keyboard()
        )
        return

    has_paid = context.user_data.get("paid_yoga", False)
    if PAYMENT_REQUIRED and not has_paid:
        await update.effective_message.reply_text(
            "🌟 *Йоги найдены!*\n\n"
            "Хочешь получить персональную трактовку найденных йог от ИИ-астролога? "
            "Как они влияют на твою судьбу, карьеру и отношения?\n"
            f"Стоимость разбора: **{PRICE_YOGA_STARS} ⭐️**",
            parse_mode="Markdown",
            reply_markup=get_yoga_inline_keyboard()
        )
        await send_yoga_invoice(update, context)
        return

    ai_status = await update.effective_message.reply_text("🔮 ИИ-астролог трактует найденные йоги...")
    try:
        interpretation = await gemini.interpret_yogas(chart_data, profile["summary"], active_yogas)
        await ai_status.delete()
        await send_split_message(
            update,
            f"🧘 *ИИ-трактовка йог:*\n\n{interpretation}",
            reply_markup=get_yoga_inline_keyboard()
        )
    except Exception as e:
        logger.exception("Ошибка ИИ-трактовки йог")
        await ai_status.edit_text(f"⚠️ Ошибка при трактовке йог: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_yoga_inline_keyboard()
        )


# ===================== КАРМИЧЕСКАЯ ЗАДАЧА ДУШИ (/karma) =====================

async def karma_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кармическая задача души и Чара-Караки Джаймини (Атмакарака и др.)."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    chart_data = profile["chart_data"]
    karakas = calculate_chara_karakas(chart_data)
    karaka_text = format_chara_karakas(karakas)
    header = f"🌟 *Кармическая задача души (Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»)*\n\n"
    full_text = header + karaka_text

    gemini = get_gemini_client()
    if not gemini:
        await send_split_message(update, full_text, reply_markup=get_karma_inline_keyboard())
        return

    has_paid = context.user_data.get("paid_karma", False) if context and context.user_data else False
    if PAYMENT_REQUIRED and not has_paid:
        await send_split_message(update, full_text)
        await update.effective_message.reply_text(
            "🌟 *Караки души рассчитаны!*\n\n"
            "Хочешь получить глубокий разбор кармической задачи души от ИИ-астролога? "
            "В чём твой главный жизненный урок и через что раскрывается истинный путь души?\n"
            f"Стоимость разбора: **{PRICE_KARMA_STARS} ⭐️**",
            parse_mode="Markdown",
            reply_markup=get_karma_inline_keyboard()
        )
        await send_karma_invoice(update, context)
        return

    await send_split_message(update, full_text)
    status_msg = await update.effective_message.reply_text("🔮 ИИ-астролог анализирует кармическую задачу души...")
    try:
        interpretation = await gemini.interpret_karma(chart_data, profile.get("summary", ""), karakas)
        await status_msg.delete()
        await send_split_message(
            update,
            f"🔮 *Глубокий кармический разбор (ИИ-Астролог):*\n\n{interpretation}",
            reply_markup=get_karma_inline_keyboard()
        )
    except Exception as e:
        logger.exception("Ошибка ИИ-разбора кармы")
        await status_msg.edit_text(f"⚠️ Ошибка при генерации кармического разбора: {e}")
        await update.effective_message.reply_text("Выбери следующее действие:", reply_markup=get_karma_inline_keyboard())


# ===================== ФИНАНСОВЫЙ КОД И КАРЬЕРА (/money) =====================

async def money_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финансовый потенциал, дома богатства и стратегия карьеры."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    chart_data = profile["chart_data"]
    wealth_data = analyze_wealth_and_career(chart_data)
    wealth_text = format_wealth_analysis(wealth_data)
    header = f"💰 *Финансовый код и карьера (Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»)*\n\n"
    full_text = header + wealth_text

    gemini = get_gemini_client()
    if not gemini:
        await send_split_message(update, full_text, reply_markup=get_money_inline_keyboard())
        return

    has_paid = context.user_data.get("paid_money", False) if context and context.user_data else False
    if PAYMENT_REQUIRED and not has_paid:
        await send_split_message(update, full_text)
        await update.effective_message.reply_text(
            "💰 *Финансовый анализ составлен!*\n\n"
            "Хочешь получить персональную стратегию заработка и масштабирования от ИИ-астролога? "
            "Какие ниши принесут максимум дохода и как гармонизировать денежный поток?\n"
            f"Стоимость стратегии: **{PRICE_MONEY_STARS} ⭐️**",
            parse_mode="Markdown",
            reply_markup=get_money_inline_keyboard()
        )
        await send_money_invoice(update, context)
        return

    await send_split_message(update, full_text)
    status_msg = await update.effective_message.reply_text("💼 ИИ-астролог формирует финансовую стратегию...")
    try:
        interpretation = await gemini.interpret_wealth(chart_data, profile.get("summary", ""), wealth_data)
        await status_msg.delete()
        await send_split_message(
            update,
            f"💼 *Персональная финансовая стратегия (ИИ-Астролог):*\n\n{interpretation}",
            reply_markup=get_money_inline_keyboard()
        )
    except Exception as e:
        logger.exception("Ошибка ИИ-разбора финансов")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе финансов: {e}")
        await update.effective_message.reply_text("Выбери следующее действие:", reply_markup=get_money_inline_keyboard())


# ===================== ВЕДИЧЕСКИЕ УПАЙИ (/upaya) =====================

async def upaya_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ведические Упайи (методы гармонизации планетных влияний) — 100% бесплатно."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    chart_data = profile["chart_data"]
    upaya_data = get_upayas(chart_data)
    upaya_text = format_upayas(upaya_data)
    header = f"🛡 *Персональные Ведические Упайи (Профиль: «{profile.get('profile_name', 'Мой гороскоп')}»)*\n\n"
    await send_split_message(update, header + upaya_text, reply_markup=get_upaya_inline_keyboard())


# ===================== ЭКСПРЕСС-ВОПРОС (/ask) =====================

async def ask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога экспресс-вопроса ИИ-астрологу."""
    user_id = (
        update.effective_user.id
        if update.effective_user
        else (update.callback_query.from_user.id if update.callback_query else 0)
    )
    profile = get_user_natal_profile(user_id, context)
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        await update.effective_message.reply_text(
            "ℹ️ ИИ-астролог недоступен. Для подключения добавь `GEMINI_API_KEY` в `.env`.",
            parse_mode="Markdown",
            reply_markup=get_main_reply_keyboard()
        )
        return ConversationHandler.END

    free_available = is_free_ask_available(user_id)
    has_paid = context.user_data.get("paid_ask", False) if context and context.user_data else False

    if PAYMENT_REQUIRED and not has_paid and not free_available:
        await update.effective_message.reply_text(
            "❓ *Экспресс-вопрос ИИ-астрологу*\n\n"
            "Задай любой вопрос по своей натальной карте — карьера, отношения, здоровье, переезд, финансы.\n\n"
            f"Стоимость: **{PRICE_ASK_STARS} ⭐️**",
            parse_mode="Markdown"
        )
        await send_ask_invoice(update, context)
        return ConversationHandler.END

    prof_name = profile.get("profile_name", "Мой гороскоп")
    free_notice = "🎁 *Твой 1-й вопрос к ИИ-астрологу — БЕСПЛАТНО!*\n\n" if (free_available and not has_paid) else ""
    await update.effective_message.reply_text(
        f"{free_notice}❓ *Задай вопрос ИИ-астрологу (Профиль: «{prof_name}»)*\n\n"
        "Напиши свой вопрос свободным текстом. Бот сопоставит натальную карту с твоим текущим периодом (Даша) и транзитами!\n\n"
        "Примеры вопросов:\n"
        "• 💼 _«Стоит ли менять работу в 2026–2027 годах?»_\n"
        "• ✈️ _«Благоприятен ли сейчас переезд за границу?»_\n"
        "• 💍 _«Когда благоприятный период для брака или отношений?»_\n"
        "• 💰 _«Что ждёт в финансовой сфере в текущий период?»_\n"
        "• ⏳ _«Почему сейчас ощущение застоя и когда это закончится?»_\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return ASK_WAITING_QUESTION


async def ask_question_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение вопроса и генерация ответа от ИИ-астролога."""
    question = update.message.text.strip()
    user_id = update.effective_user.id
    profile = get_user_natal_profile(user_id, context)

    if not profile:
        await update.effective_message.reply_text(
            "Сессия истекла. Начни заново с /chart.",
            reply_markup=get_main_reply_keyboard()
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
            md_str = f"Махадаша: {md.get('planet_ru', md['planet'])} ({md['start']} — {md['end']})"
            if curr_dasha.get("antar_dasha"):
                ad = curr_dasha["antar_dasha"]
                ad_str = f", Антардаша: {ad.get('planet_ru', ad['planet'])} ({ad['start']} — {ad['end']})"
                md_str += ad_str
            forecast_context_parts.append(f"Текущий планетарный период (Вимшоттари Даша): {md_str}")
    except Exception as e:
        logger.debug(f"Не удалось рассчитать дашу для /ask: {e}")

    try:
        ss_info = check_sade_sati(chart_data)
        if ss_info:
            if ss_info.get("active"):
                forecast_context_parts.append(
                    f"Транзит Саде-Сати (Сатурн): АКТИВЕН, фаза {ss_info.get('phase_ru', ss_info.get('phase'))}. "
                    f"Натальная Луна в {ss_info.get('moon_sign_ru', ss_info.get('moon_sign'))}, Сатурн в {ss_info.get('saturn_sign_ru', ss_info.get('saturn_sign'))}."
                )
            else:
                forecast_context_parts.append(
                    f"Транзит Саде-Сати: НЕ активен (Сатурн в {ss_info.get('saturn_sign_ru', ss_info.get('saturn_sign'))}, Луна в {ss_info.get('moon_sign_ru', ss_info.get('moon_sign'))})."
                )
    except Exception as e:
        logger.debug(f"Не удалось проверить Саде-Сати для /ask: {e}")

    forecast_context = "\n".join(forecast_context_parts)

    status_msg = await update.effective_message.reply_text("🔮 ИИ-астролог анализирует твою карту и готовит ответ...")
    try:
        answer = await gemini.interpret_ask_question(
            chart_data, summary, question, forecast_context=forecast_context
        )
        await status_msg.delete()
        await send_split_message(
            update,
            f"📜 *Ответ ИИ-астролога:*\n\n{answer}",
            reply_markup=get_ask_inline_keyboard()
        )
        # Если это был первый бесплатный вопрос, помечаем его использованным
        if is_free_ask_available(user_id) and not (context.user_data and context.user_data.get("paid_ask", False)):
            mark_free_ask_used(user_id)
    except Exception as e:
        logger.exception("Ошибка ответа на вопрос")
        await status_msg.edit_text(f"⚠️ Ошибка при генерации ответа: {e}")
        await update.effective_message.reply_text(
            "Выбери следующее действие:",
            reply_markup=get_ask_inline_keyboard()
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

    await update.message.reply_text(
        f"🎉 *Оплата успешно получена ({stars_amount} ⭐️)!*\n"
        "Запускаю расчёт и генерацию персонального разбора...",
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
        status_msg = await update.effective_message.reply_text("🔮 Составляю твой премиальный разбор натальной карты...")
        try:
            interpretation = await gemini.interpret_chart(chart_data, summary)
            await status_msg.delete()
            await send_split_message(
                update,
                f"📜 *Персональный разбор натальной карты:*\n\n{interpretation}",
                reply_markup=get_chart_inline_keyboard()
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_dasha_interpretation":
        context.user_data["paid_dasha"] = True
        status_msg = await update.effective_message.reply_text("⏳ Формирую подробный анализ планетных периодов...")
        try:
            interpretation = await gemini.interpret_dasha(chart_data, summary)
            await status_msg.delete()
            await send_split_message(
                update,
                f"🌟 *Анализ периодов судьбы (Даша):*\n\n{interpretation}",
                reply_markup=get_dasha_inline_keyboard()
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_compat_interpretation":
        context.user_data["paid_compat"] = True
        partner_chart = context.user_data.get("partner_chart")
        partner_summary = context.user_data.get("partner_summary")
        if partner_chart and partner_summary:
            status_msg = await update.effective_message.reply_text("💞 Сопоставляю две карты по системе Аштакута...")
            try:
                interpretation = await gemini.interpret_compatibility(
                    chart_data, summary, partner_chart, partner_summary
                )
                await status_msg.delete()
                await send_split_message(
                    update,
                    f"💘 *Анализ совместимости парных карт:*\n\n{interpretation}",
                    reply_markup=get_compat_inline_keyboard()
                )
            except Exception as e:
                await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_ask_question":
        context.user_data["paid_ask"] = True
        await update.effective_message.reply_text(
            "❓ *Экспресс-вопрос оплачен!*\n\n"
            "Теперь нажми кнопку ниже или набери /ask и задай свой вопрос ИИ-астрологу.",
            parse_mode="Markdown",
            reply_markup=get_ask_inline_keyboard()
        )

    elif payload == "payload_yoga_interpretation":
        context.user_data["paid_yoga"] = True
        # Запускаем ИИ-трактовку йог сразу после оплаты
        yogas = detect_yogas(chart_data)
        active_yogas = [y for y in yogas if y.get("active", False)]
        if active_yogas:
            status_msg = await update.effective_message.reply_text("🧘 ИИ-астролог трактует найденные йоги...")
            try:
                interpretation = await gemini.interpret_yogas(chart_data, summary, active_yogas)
                await status_msg.delete()
                await send_split_message(
                    update,
                    f"🧘 *ИИ-трактовка йог:*\n\n{interpretation}",
                    reply_markup=get_yoga_inline_keyboard()
                )
            except Exception as e:
                await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")
        else:
            await update.effective_message.reply_text(
                "🧘 Оплата принята! Набери /yoga для анализа йог.",
                parse_mode="Markdown",
                reply_markup=get_yoga_inline_keyboard()
            )

    elif payload == "payload_karma_interpretation":
        context.user_data["paid_karma"] = True
        karakas = calculate_chara_karakas(chart_data)
        status_msg = await update.effective_message.reply_text("🔮 Составляю глубокий кармический разбор души...")
        try:
            interpretation = await gemini.interpret_karma(chart_data, summary, karakas)
            await status_msg.delete()
            await send_split_message(
                update,
                f"🔮 *Глубокий кармический разбор (ИИ-Астролог):*\n\n{interpretation}",
                reply_markup=get_karma_inline_keyboard()
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_money_interpretation":
        context.user_data["paid_money"] = True
        wealth_data = analyze_wealth_and_career(chart_data)
        status_msg = await update.effective_message.reply_text("💼 Составляю финансовую стратегию...")
        try:
            interpretation = await gemini.interpret_wealth(chart_data, summary, wealth_data)
            await status_msg.delete()
            await send_split_message(
                update,
                f"💼 *Персональная финансовая стратегия (ИИ-Астролог):*\n\n{interpretation}",
                reply_markup=get_money_inline_keyboard()
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
        status_msg = await update.effective_message.reply_text(
            "🌟 *Бандл «Вся судьба 360°» активирован!*\n\n"
            "Тебе доступны: разбор карты, Даша, йоги, карма, деньги и 1 вопрос.\n"
            "Начинаю полный разбор натальной карты...",
            parse_mode="Markdown"
        )
        try:
            interpretation = await gemini.interpret_chart(chart_data, summary)
            await status_msg.delete()
            await send_split_message(
                update,
                f"📜 *Персональный разбор натальной карты:*\n\n{interpretation}",
                reply_markup=get_chart_inline_keyboard()
            )
            await update.effective_message.reply_text(
                "✅ Теперь используй /dasha, /karma, /money, /yoga и /ask — все они разблокированы!",
                reply_markup=get_main_reply_keyboard()
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
    if context.user_data:
        context.user_data.pop("temp_dob", None)
        context.user_data.pop("temp_tob", None)
        context.user_data.pop("temp_profile_name", None)
        context.user_data.pop("editing_profile_id", None)
        context.user_data.pop("compat_dob", None)
        context.user_data.pop("compat_tob", None)
    await update.effective_message.reply_text(
        "Ввод отменён. Нажми кнопку ниже или /chart в любой момент.",
        reply_markup=get_main_reply_keyboard()
    )
    return ConversationHandler.END


# ===================== НАВИГАЦИОННЫЕ И ИНЛАЙН ХЕНДЛЕРЫ =====================

async def inline_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единый диспетчер для навигационных, профильных и платёжных инлайн-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    logger.info(f"Нажата инлайн-кнопка: {data}")

    # Управление профилями
    if data == "prof_menu":
        await profile_command(update, context)

    elif data.startswith("prof_switch_"):
        prof_id = int(data.split("prof_switch_")[1])
        if set_active_profile(prof_id, user_id):
            new_active = get_profile_by_id(prof_id, user_id)
            context.user_data["natal_profile"] = new_active
            await query.message.reply_text(
                f"✅ Активный профиль переключён на *«{new_active['profile_name']}»*!\n\n"
                "Теперь все расчёты (/chart, /dasha, /sadesati, /yoga, /ask) работают для этого человека.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📜 Показать карту", callback_data="prof_view_active"),
                        InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
                    ],
                    [
                        InlineKeyboardButton("👤 Все профили", callback_data="prof_menu"),
                        InlineKeyboardButton("⭐️ Тарифы", callback_data="nav_prices"),
                    ],
                ])
            )
        else:
            await query.message.reply_text("Не удалось переключить профиль. Открой /profile.")

    elif data == "prof_view_active":
        active = get_user_natal_profile(user_id, context)
        if not active:
            await query.message.reply_text("Профиль не найден. Начни с /chart.")
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
                    place_str=active.get("place_name")
                )
                await query.message.reply_photo(
                    photo=chart_img,
                    caption=f"🔮 *Ведическая карта Кундли (D1): {active.get('profile_name', 'Профиль')}*",
                    parse_mode="Markdown"
                )
            except Exception as img_err:
                logger.warning(f"Не удалось отправить изображение карты: {img_err}")

        summary = active.get("summary")
        if not summary and active.get("chart_data"):
            try:
                summary = format_chart_summary(active["chart_data"])
            except Exception:
                summary = ""
        header = f"👤 *Натальная карта профиля «{active['profile_name']}»*\n\n"
        await send_split_message(update, header + (summary or ""), reply_markup=get_chart_inline_keyboard())

    elif data == "prof_delete_menu":
        profiles = get_user_profiles(user_id)
        if not profiles:
            await query.message.reply_text("У тебя нет сохранённых профилей.")
            return
        buttons = []
        for p in profiles:
            buttons.append([InlineKeyboardButton(f"❌ Удалить «{p['profile_name']}»", callback_data=f"prof_del_{p['id']}")])
        buttons.append([InlineKeyboardButton("🔙 Назад к профилям", callback_data="prof_menu")])
        await query.message.reply_text(
            "🗑 *Выбери профиль для удаления:*\n_Внимание: удаление необратимо._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("prof_del_"):
        prof_id = int(data.split("prof_del_")[1])
        deleted_prof = get_profile_by_id(prof_id, user_id)
        name = deleted_prof["profile_name"] if deleted_prof else "Профиль"
        if delete_profile(prof_id, user_id):
            new_active = get_active_profile(user_id)
            context.user_data["natal_profile"] = new_active
            await query.message.reply_text(f"🗑 Профиль *«{name}»* успешно удалён.", parse_mode="Markdown")
            await profile_command(update, context)
        else:
            await query.message.reply_text("Не удалось удалить профиль. Возможно, он уже был удалён.")

    elif data == "reset_cache_only":
        context.user_data.clear()
        await query.message.reply_text("🔄 Кэш текущей сессии очищен. Профили в базе данных сохранены!")

    elif data == "reset_all_confirm":
        clear_user_profiles(user_id)
        context.user_data.clear()
        await query.message.reply_text("🗑 Все твои астрологические профили полностью удалены из базы данных.")

    # Навигационные переходы
    elif data == "nav_chart_img":
        active = get_user_natal_profile(user_id, context)
        if not active or not active.get("chart_data"):
            await query.message.reply_text("Профиль не найден. Начни с /chart.")
            return
        status_msg = await query.message.reply_text("🎨 Рисую карту Кундли D1...")
        try:
            b_dt = active.get("birth_dt")
            dob_s = b_dt.strftime("%d.%m.%Y") if b_dt else None
            tob_s = b_dt.strftime("%H:%M") if b_dt else None
            chart_img = render_kundli_chart(
                chart_data=active["chart_data"],
                profile_name=active.get("profile_name"),
                dob_str=dob_s,
                tob_str=tob_s,
                place_str=active.get("place_name")
            )
            try:
                await status_msg.delete()
            except Exception:
                pass
            await query.message.reply_photo(
                photo=chart_img,
                caption=f"🔮 *Ведическая карта Кундли (D1): {active.get('profile_name', 'Профиль')}*",
                parse_mode="Markdown",
                reply_markup=get_chart_inline_keyboard()
            )
        except Exception as e:
            logger.exception("Ошибка отправки изображения карты")
            await status_msg.edit_text(f"❌ Не удалось сгенерировать изображение карты: {e}")

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
        await send_chart_invoice(update, context)

    elif data == "buy_dasha":
        await send_dasha_invoice(update, context)

    elif data == "buy_karma":
        await send_karma_invoice(update, context)

    elif data == "buy_money":
        await send_money_invoice(update, context)

    elif data == "buy_compat":
        await send_compat_invoice(update, context)

    elif data == "buy_ask":
        await send_ask_invoice(update, context)

    elif data == "buy_yoga":
        await send_yoga_invoice(update, context)

    elif data == "buy_bundle":
        await send_bundle_invoice(update, context)

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
    if text == "🔮 Натальная карта":
        profile = get_user_natal_profile(user_id, context)
        if profile:
            return await show_active_profile_card(update, context, profile)
        else:
            return await chart_start(update, context)
    elif text in ("👤 Мои профили", "👤 Профили", "📋 Мои данные", "🔄 Сменить профиль"):
        return await profile_command(update, context)
    elif text == "⏳ Периоды Даша":
        return await dasha_command(update, context)
    elif text == "🪐 Саде-Сати":
        return await sadesati_command(update, context)
    elif text == "🧘 Детектор йог":
        return await yoga_command(update, context)
    elif text == "💰 Деньги и карьера":
        return await money_command(update, context)
    elif text == "🔮 Кармическая задача":
        return await karma_command(update, context)
    elif text in ("🛡 Упайи (Гармонизация)", "🛡 Упайи (Коррекция)", "🛡 Упайи"):
        return await upaya_command(update, context)
    elif text == "❓ Задать вопрос":
        return await ask_start(update, context)
    elif text == "💞 Совместимость":
        return await compat_start(update, context)
    elif text == "⭐️ Тарифы":
        return await prices_command(update, context)
    elif text == "📖 Справка":
        return await help_command(update, context)


async def post_init(application: Application) -> None:
    """Регистрация списка команд в системном меню Telegram (кнопка [/] Меню)."""
    commands = [
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
        BotCommand("mydata", "📋 Мои сохранённые данные"),
        BotCommand("reset", "🔄 Сброс данных"),
        BotCommand("help", "📖 Справка и помощь"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Системное меню команд Telegram успешно зарегистрировано!")
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
        MessageHandler(filters.Regex(r"^(❌ Отмена|Отмена|/cancel)$"), cancel_command),
    ]

    # ConversationHandler для натальной карты
    chart_conv = ConversationHandler(
        entry_points=[
            CommandHandler("chart", chart_start),
            CommandHandler("natal", chart_start),
            CommandHandler("newprofile", newprofile_start),
            MessageHandler(filters.Regex(r"^🔮 Натальная карта$"), chart_start),
            MessageHandler(filters.Regex(r"^(➕ Добавить профиль|➕ Новый профиль)$"), newprofile_start),
            MessageHandler(one_line_filter, chart_one_line_direct),
            CallbackQueryHandler(newprofile_callback_start, pattern=r"^prof_add_start$"),
            CallbackQueryHandler(recalc_callback_start, pattern=r"^prof_recalc_start$"),
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
            MessageHandler(filters.Regex(r"^💞 Совместимость$"), compat_start),
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
            MessageHandler(filters.Regex(r"^❓ Задать вопрос$"), ask_start),
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
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("profiles", profile_command))
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
    MENU_BUTTON_REGEX = r"^(⏳ Периоды Даша|🪐 Саде-Сати|🧘 Детектор йог|💰 Деньги и карьера|🔮 Кармическая задача|🛡 Упайи.*|⭐️ Тарифы|📋 Мои данные|👤 Мои профили|👤 Профили|🔄 Сменить профиль|📖 Справка)$"
    app.add_handler(MessageHandler(filters.Regex(MENU_BUTTON_REGEX), handle_menu_text_button))

    # Регистрация платёжных хэндлеров (Telegram Stars)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    print("🚀 Джьотиш-бот успешно запущен с поддержкой Telegram Stars и интерактивной навигацией!")
    app.run_polling()


if __name__ == "__main__":
    main()

