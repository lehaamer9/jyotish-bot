"""
Telegram-бот ИИ-Джьотиш Астролог.
Полноценный бот с расчётом натальных карт, периодов Вимшоттари Даша,
анализом совместимости, экспертной интерпретацией через Google Gemini
и приёмом оплаты в Звёздах Telegram (Stars / XTR).
"""
import os
import sys
import logging
from datetime import datetime
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

from jyotish_engine import (
    compute_chart,
    format_chart_summary,
    format_dasha_periods,
    get_current_dasha,
    check_sade_sati,
    detect_yogas,
)
from geo_helper import resolve_location
from gemini_interpreter import GeminiInterpreter
from payment_helper import (
    send_chart_invoice,
    send_dasha_invoice,
    send_compat_invoice,
    send_ask_invoice,
    send_yoga_invoice,
    send_bundle_invoice,
    precheckout_callback,
    PAYMENT_REQUIRED,
    PRICE_CHART_STARS,
    PRICE_DASHA_STARS,
    PRICE_COMPAT_STARS,
    PRICE_ASK_STARS,
    PRICE_YOGA_STARS,
    PRICE_BUNDLE_STARS,
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога для натальной карты
(
    WAITING_DOB,
    WAITING_TOB,
    WAITING_PLACE,
) = range(3)

# Состояния диалога для совместимости (партнёр)
(
    COMPAT_WAITING_DOB,
    COMPAT_WAITING_TOB,
    COMPAT_WAITING_PLACE,
) = range(3, 6)

# Состояние диалога для экспресс-вопроса /ask
ASK_WAITING_QUESTION = 6

TELEGRAM_MAX_MESSAGE_LENGTH = 4000


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
        ["🪐 Саде-Сати", "🧘 Детектор йог"],
        ["❓ Задать вопрос", "💞 Совместимость"],
        ["⭐️ Тарифы", "📋 Мои данные"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def get_start_inline_keyboard():
    """Инлайн-кнопки приветствия /start."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔮 Составить натальную карту", callback_data="nav_chart"),
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
            InlineKeyboardButton("⏳ Периоды Даша", callback_data="nav_dasha"),
            InlineKeyboardButton("🪐 Саде-Сати", callback_data="nav_sadesati"),
        ],
        [
            InlineKeyboardButton("🧘 Детектор йог", callback_data="nav_yoga"),
            InlineKeyboardButton("❓ Задать вопрос", callback_data="nav_ask"),
        ],
        [
            InlineKeyboardButton("💞 Совместимость", callback_data="nav_compat"),
            InlineKeyboardButton("⭐️ Тарифы", callback_data="nav_prices"),
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
        "🧘 Находить мощные йоги в натальной карте\n\n"
        "📌 *Команды бота:*\n"
        "👉 /chart — составить натальную карту\n"
        "👉 /dasha — периоды жизни (Вимшоттари Даша)\n"
        "👉 /compat — совместимость с партнёром\n"
        "👉 /ask — задать вопрос ИИ-астрологу\n"
        "👉 /sadesati — проверить Саде-Сати\n"
        "👉 /yoga — найти йоги в карте\n"
        "👉 /prices — стоимость услуг в Звёздах Telegram (⭐️)\n"
        "👉 /mydata — посмотреть сохранённые данные\n"
        "👉 /reset — сбросить данные\n"
        "👉 /help — справка\n\n"
        "👇 *Выбери действие на кнопках ниже или нажми /chart:*"
    )
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
        "🔹 /dasha — Разбор планетных периодов Вимшоттари Даша.\n"
        "🔹 /compat — Синастрия и совместимость по 8 ведическим показателям.\n"
        "🔹 /ask — Задать любой вопрос ИИ-астрологу по своей карте.\n"
        "🔹 /sadesati — Проверить, идёт ли период Саде-Сати (транзит Сатурна).\n"
        "🔹 /yoga — Найти мощные йоги (комбинации планет) в натальной карте.\n"
        "🔹 /prices — Тарифы на подробные ИИ-разборы (оплата в ⭐️ Telegram Stars).\n"
        "🔹 /mydata — Показывает введённые дату, время и координаты.\n"
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
        "🆓 *Бесплатно:* базовые расчёты, /sadesati (Саде-Сати).\n\n"
        "✨ Оплата производится в 1 клик через официальные звёзды Telegram (Apple Pay / Google Pay / карты)."
    )
    prices_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🔮 Карта ({PRICE_CHART_STARS} ⭐️)", callback_data="buy_chart"),
            InlineKeyboardButton(f"⏳ Даша ({PRICE_DASHA_STARS} ⭐️)", callback_data="buy_dasha"),
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


async def mydata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сохранённые данные пользователя."""
    profile = context.user_data.get("natal_profile")
    if not profile:
        await update.effective_message.reply_text(
            "У тебя пока нет сохранённой натальной карты.\nНажми кнопку ниже или /chart, чтобы составить её!",
            reply_markup=get_main_reply_keyboard()
        )
        return

    text = (
        "📋 *Твои сохранённые данные:*\n\n"
        f"📅 Дата: `{profile['birth_dt'].strftime('%d.%m.%Y')}`\n"
        f"⏰ Время: `{profile['birth_dt'].strftime('%H:%M')}`\n"
        f"📍 Место: `{profile['place_name']}`\n"
        f"🌐 Координаты: `{profile['lat']:.4f}, {profile['lon']:.4f}` (UTC{profile['tz_offset']:+.1f})\n\n"
        "Чтобы пересчитать с новыми данными, используй /reset или /chart."
    )
    await update.effective_message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_chart_inline_keyboard()
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить сохранённые данные."""
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Данные сброшены. Чтобы составить новую карту, нажми /chart или кнопку ниже:",
        reply_markup=get_main_reply_keyboard()
    )


# ===================== ДИАЛОГ СОСТАВЛЕНИЯ КАРТЫ =====================

async def chart_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало составления натальной карты."""
    await update.message.reply_text(
        "🔮 *Шаг 1 из 3:* Введи дату рождения в формате `ДД.ММ.ГГГГ`\n"
        "_(Например: `15.05.1990`)_\n\n"
        "Для отмены набери /cancel",
        parse_mode="Markdown"
    )
    return WAITING_DOB


async def chart_dob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты рождения."""
    text = update.message.text.strip()
    try:
        dob = datetime.strptime(text, "%d.%m.%Y").date()
        context.user_data["temp_dob"] = dob
    except ValueError:
        await update.message.reply_text(
            "⚠️ Неверный формат даты. Пожалуйста, укажи в виде `ДД.ММ.ГГГГ` (например: `15.05.1990`):",
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
    """Получение времени рождения."""
    text = update.message.text.strip()
    try:
        tob = datetime.strptime(text, "%H:%M").time()
        context.user_data["temp_tob"] = tob
    except ValueError:
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
    dob = context.user_data.get("temp_dob")
    tob = context.user_data.get("temp_tob")

    if not dob or not tob:
        await update.message.reply_text("Произошла ошибка сессии. Начни заново с /chart.")
        return ConversationHandler.END

    dt = datetime.combine(dob, tob)
    status_msg = await update.message.reply_text("🌍 Определяю координаты и часовой пояс города...")

    try:
        lat, lon, tz_offset, address = resolve_location(place_input, target_date=dt)
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Не удалось найти город '{place_input}'.\n"
            f"Ошибка: {e}\n"
            "Попробуй ещё раз указать город (или нажми /chart заново):"
        )
        return WAITING_PLACE

    await status_msg.edit_text("🧮 Вычисляю позиции планет и домов по NASA JPL эфемеридам...")

    try:
        user_name = update.effective_user.first_name or "User"
        chart_data = compute_chart(
            birth_dt=dt,
            lat=lat,
            lon=lon,
            tz_offset=tz_offset,
            name=user_name
        )
        summary = format_chart_summary(chart_data)

        # Сохраняем в профиль пользователя
        context.user_data["natal_profile"] = {
            "birth_dt": dt,
            "place_name": place_input,
            "resolved_address": address,
            "lat": lat,
            "lon": lon,
            "tz_offset": tz_offset,
            "chart_data": chart_data,
            "summary": summary,
        }

        # Отправляем астрономический расчёт бесплатно всем
        await status_msg.delete()
        chart_buttons = get_chart_inline_keyboard()
        await send_split_message(update, summary)

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
    has_paid = context.user_data.get("paid_chart", False)
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


# ===================== КОМАНДА ДАША (ПЕРИОДЫ) =====================

async def dasha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать и интерпретировать периоды жизни Вимшоттари Даша."""
    profile = context.user_data.get("natal_profile")
    if not profile:
        await update.effective_message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart или кнопку ниже:",
            reply_markup=get_main_reply_keyboard()
        )
        return

    chart_data = profile["chart_data"]
    summary = profile["summary"]
    dasha_text = format_dasha_periods(chart_data)

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

async def compat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало проверки совместимости."""
    my_profile = context.user_data.get("natal_profile")
    if not my_profile:
        await update.message.reply_text(
            "Для анализа совместимости сначала нужны твои данные!\n"
            "Нажми /chart, чтобы составить свою карту, затем вернись в /compat."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "💞 *Анализ совместимости партнёров (Кута / Аштакута)*\n\n"
        "Твоя натальная карта уже сохранена.\n"
        "Теперь введи данные *партнёра*.\n\n"
        "📅 *Шаг 1 из 3:* Дата рождения партнёра `ДД.ММ.ГГГГ` (например: `20.08.1992`):",
        parse_mode="Markdown"
    )
    return COMPAT_WAITING_DOB


async def compat_dob_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение даты партнёра."""
    text = update.message.text.strip()
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
    dob = context.user_data.get("compat_dob")
    tob = context.user_data.get("compat_tob")
    my_profile = context.user_data.get("natal_profile")

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

    except Exception as e:
        await status_msg.edit_text(f"❌ Не удалось рассчитать карту партнёра: {e}")
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        await status_msg.edit_text(
            "ℹ️ Карта партнёра построена!\n"
            "Для анализа совместимости от ИИ добавь `GEMINI_API_KEY` в `.env`."
        )
        return ConversationHandler.END

    has_paid = context.user_data.get("paid_compat", False)
    if PAYMENT_REQUIRED and not has_paid:
        await status_msg.edit_text(
            "💞 *Карты обоих партнёров построены!*\n\n"
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
            f"💘 *Анализ совместимости парных карт:*\n\n{result}",
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
    profile = context.user_data.get("natal_profile")
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

        if result["active"]:
            phase_names = {
                "rising": "🌅 Восходящая фаза (Сатурн в 12-м знаке от Луны)",
                "peak": "🔥 Пиковая фаза (Сатурн в знаке Луны)",
                "setting": "🌇 Нисходящая фаза (Сатурн во 2-м знаке от Луны)",
            }
            phase_text = phase_names.get(result["phase"], result["phase"])
            text = (
                "🪐 *Саде-Сати — АКТИВНА!*\n\n"
                f"🌙 Твоя натальная Луна: *{result['natal_moon_sign']}*\n"
                f"🪐 Транзитный Сатурн: *{result['saturn_sign']}*\n\n"
                f"📍 Фаза: {phase_text}\n\n"
                "⏳ Саде-Сати длится ~7.5 лет — это период кармической трансформации, "
                "глубоких уроков и духовного роста.\n\n"
                "💡 *Упайя (гармонизация):* пение мантры Шани — *«Ом Шам Шанайе Намаха»* — "
                "по субботам, ношение синего сапфира (после консультации), служение пожилым людям."
            )
        else:
            text = (
                "🪐 *Саде-Сати — НЕ активна*\n\n"
                f"🌙 Твоя натальная Луна: *{result['natal_moon_sign']}*\n"
                f"🪐 Транзитный Сатурн: *{result['saturn_sign']}*\n\n"
                "✅ Сейчас период Саде-Сати не затрагивает твою Луну. "
                "Влияние Сатурна менее интенсивно.\n\n"
                "ℹ️ Саде-Сати наступает, когда транзитный Сатурн проходит "
                "через 12-й, 1-й и 2-й знаки от натальной Луны (~7.5 лет)."
            )

        await status_msg.delete()
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
    profile = context.user_data.get("natal_profile")
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

        if not active_yogas:
            await status_msg.edit_text(
                "🧘 *Детектор йог*\n\n"
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
            f"🧘 *Найдено йог: {len(active_yogas)}*\n\n"
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


# ===================== ЭКСПРЕСС-ВОПРОС (/ask) =====================

async def ask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало диалога экспресс-вопроса ИИ-астрологу."""
    profile = context.user_data.get("natal_profile")
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

    has_paid = context.user_data.get("paid_ask", False)
    if PAYMENT_REQUIRED and not has_paid:
        await update.effective_message.reply_text(
            "❓ *Экспресс-вопрос ИИ-астрологу*\n\n"
            "Задай любой вопрос по своей натальной карте — карьера, отношения, здоровье, переезд, финансы.\n\n"
            f"Стоимость: **{PRICE_ASK_STARS} ⭐️**",
            parse_mode="Markdown"
        )
        await send_ask_invoice(update, context)
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "❓ *Задай вопрос ИИ-астрологу (в т.ч. прогноз)*\n\n"
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
    profile = context.user_data.get("natal_profile")

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
    profile = context.user_data.get("natal_profile")

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

    elif payload == "payload_bundle_360":
        # Бандл активирует все платные функции
        context.user_data["paid_chart"] = True
        context.user_data["paid_dasha"] = True
        context.user_data["paid_yoga"] = True
        context.user_data["paid_ask"] = True
        # Генерируем полный разбор карты как основной продукт бандла
        status_msg = await update.effective_message.reply_text(
            "🌟 *Бандл «Вся судьба 360°» активирован!*\n\n"
            "Тебе доступны: разбор карты, Даша, йоги и 1 вопрос.\n"
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
                "✅ Теперь используй /dasha, /yoga и /ask — все они разблокированы!",
                reply_markup=get_main_reply_keyboard()
            )
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего ввода и возврат к главному меню."""
    await update.effective_message.reply_text(
        "Ввод отменён. Нажми кнопку ниже или /chart в любой момент.",
        reply_markup=get_main_reply_keyboard()
    )
    return ConversationHandler.END


# ===================== НАВИГАЦИОННЫЕ И ИНЛАЙН ХЕНДЛЕРЫ =====================

async def inline_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единый диспетчер для навигационных и платёжных инлайн-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data

    logger.info(f"Нажата инлайн-кнопка: {data}")

    # Навигационные переходы
    if data == "nav_chart":
        profile = context.user_data.get("natal_profile")
        if profile:
            await query.message.reply_text(
                "🔮 Твоя натальная карта уже составлена. Вот твои данные:\n"
                "(Если хочешь пересчитать с новой датой — нажми /reset)",
                reply_markup=get_chart_inline_keyboard()
            )
            await mydata_command(update, context)
        else:
            await chart_start(update, context)

    elif data == "nav_dasha":
        await dasha_command(update, context)

    elif data == "nav_sadesati":
        await sadesati_command(update, context)

    elif data == "nav_yoga":
        await yoga_command(update, context)

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

    elif data == "buy_compat":
        await send_compat_invoice(update, context)

    elif data == "buy_ask":
        await send_ask_invoice(update, context)

    elif data == "buy_yoga":
        await send_yoga_invoice(update, context)

    elif data == "buy_bundle":
        await send_bundle_invoice(update, context)


async def handle_menu_text_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на постоянную нижнюю клавиатуру (ReplyKeyboardMarkup)."""
    text = update.message.text.strip() if update.message and update.message.text else ""
    if text == "🔮 Натальная карта":
        profile = context.user_data.get("natal_profile")
        if profile:
            await mydata_command(update, context)
        else:
            return await chart_start(update, context)
    elif text == "⏳ Периоды Даша":
        return await dasha_command(update, context)
    elif text == "🪐 Саде-Сати":
        return await sadesati_command(update, context)
    elif text == "🧘 Детектор йог":
        return await yoga_command(update, context)
    elif text == "❓ Задать вопрос":
        return await ask_start(update, context)
    elif text == "💞 Совместимость":
        return await compat_start(update, context)
    elif text == "⭐️ Тарифы":
        return await prices_command(update, context)
    elif text == "📋 Мои данные":
        return await mydata_command(update, context)


async def post_init(application: Application) -> None:
    """Регистрация списка команд в системном меню Telegram (кнопка [/] Меню)."""
    commands = [
        BotCommand("chart", "🔮 Составить натальную карту"),
        BotCommand("dasha", "⏳ Периоды жизни (Даша)"),
        BotCommand("sadesati", "🪐 Калькулятор Саде-Сати"),
        BotCommand("yoga", "🧘 Детектор йог"),
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
    start_health_server()
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
            MessageHandler(filters.Regex(r"^🔮 Натальная карта$"), chart_start),
        ],
        states={
            WAITING_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_dob_received)],
            WAITING_TOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_tob_received)],
            WAITING_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_place_received)],
        },
        fallbacks=common_fallbacks,
    )

    # ConversationHandler для совместимости
    compat_conv = ConversationHandler(
        entry_points=[
            CommandHandler("compat", compat_start),
            MessageHandler(filters.Regex(r"^💞 Совместимость$"), compat_start),
        ],
        states={
            COMPAT_WAITING_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_dob_received)],
            COMPAT_WAITING_TOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_tob_received)],
            COMPAT_WAITING_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_place_received)],
        },
        fallbacks=common_fallbacks,
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
    )

    # Регистрация команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prices", prices_command))
    app.add_handler(CommandHandler("mydata", mydata_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("dasha", dasha_command))
    app.add_handler(CommandHandler("sadesati", sadesati_command))
    app.add_handler(CommandHandler("yoga", yoga_command))

    # Регистрация диалогов
    app.add_handler(chart_conv)
    app.add_handler(compat_conv)
    app.add_handler(ask_conv)

    # Регистрация нажатий на инлайн-кнопки
    app.add_handler(CallbackQueryHandler(inline_nav_callback))

    # Регистрация нажатий на постоянную нижнюю клавиатуру
    MENU_BUTTON_REGEX = r"^(⏳ Периоды Даша|🪐 Саде-Сати|🧘 Детектор йог|⭐️ Тарифы|📋 Мои данные)$"
    app.add_handler(MessageHandler(filters.Regex(MENU_BUTTON_REGEX), handle_menu_text_button))

    # Регистрация платёжных хэндлеров (Telegram Stars)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    print("🚀 Джьотиш-бот успешно запущен с поддержкой Telegram Stars и интерактивной навигацией!")
    app.run_polling()


if __name__ == "__main__":
    main()
