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
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
)
from geo_helper import resolve_location
from gemini_interpreter import GeminiInterpreter
from payment_helper import (
    send_chart_invoice,
    send_dasha_invoice,
    send_compat_invoice,
    precheckout_callback,
    PAYMENT_REQUIRED,
    PRICE_CHART_STARS,
    PRICE_DASHA_STARS,
    PRICE_COMPAT_STARS,
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


async def send_split_message(update: Update, text: str, parse_mode: str = "Markdown"):
    """Отправить длинное сообщение частями, соблюдая лимит Telegram."""
    if len(text) <= TELEGRAM_MAX_MESSAGE_LENGTH:
        try:
            await update.effective_message.reply_text(text, parse_mode=parse_mode)
        except Exception:
            await update.effective_message.reply_text(text)
        return

    paragraphs = text.split("\n\n")
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > TELEGRAM_MAX_MESSAGE_LENGTH:
            if current_chunk:
                try:
                    await update.effective_message.reply_text(current_chunk.strip(), parse_mode=parse_mode)
                except Exception:
                    await update.effective_message.reply_text(current_chunk.strip())
                current_chunk = ""
        current_chunk += para + "\n\n"

    if current_chunk.strip():
        try:
            await update.effective_message.reply_text(current_chunk.strip(), parse_mode=parse_mode)
        except Exception:
            await update.effective_message.reply_text(current_chunk.strip())


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
        "🤖 Формировать глубокие персональные разборы и упайи (гармонизации)\n\n"
        "📌 *Команды бота:*\n"
        "👉 /chart — составить натальную карту\n"
        "👉 /dasha — периоды жизни (Вимшоттари Даша)\n"
        "👉 /compat — совместимость с партнёром\n"
        "👉 /prices — стоимость услуг в Звёздах Telegram (⭐️)\n"
        "👉 /mydata — посмотреть сохранённые данные\n"
        "👉 /reset — сбросить данные\n"
        "👉 /help — справка\n\n"
        "Нажми /chart, чтобы начать!"
    )
    await update.message.reply_text(greeting, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам."""
    help_text = (
        "📖 *Справка по Джьотиш-Боту:*\n\n"
        "🔹 /chart — Составление натальной карты (дата, время, город рождения).\n"
        "🔹 /dasha — Разбор планетных периодов Вимшоттари Даша.\n"
        "🔹 /compat — Синастрия и совместимость по 8 ведическим показателям.\n"
        "🔹 /prices — Тарифы на подробные ИИ-разборы (оплата в ⭐️ Telegram Stars).\n"
        "🔹 /mydata — Показывает введённые дату, время и координаты.\n"
        "🔹 /reset — Сброс сохранённых данных.\n"
        "🔹 /cancel — Отмена текущего шага ввода.\n\n"
        "💡 *Оплата:* Базовые расчёты бесплатны. Подробные трактовки оплачиваются в ⭐️ Telegram Stars прямо в приложении."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


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
        "✨ Оплата производится в 1 клик через официальные звёзды Telegram (Apple Pay / Google Pay / карты)."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def mydata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сохранённые данные пользователя."""
    profile = context.user_data.get("natal_profile")
    if not profile:
        await update.message.reply_text(
            "У тебя пока нет сохранённой натальной карты.\nНажми /chart, чтобы составить её!"
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
    await update.message.reply_text(text, parse_mode="Markdown")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить сохранённые данные."""
    context.user_data.clear()
    await update.message.reply_text(
        "Данные сброшены. Чтобы составить новую карту, нажми /chart."
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
        await send_split_message(update, summary)

    except Exception as e:
        logger.exception("Ошибка расчёта карты")
        await status_msg.edit_text(f"❌ Ошибка при расчёте карты: {e}")
        return ConversationHandler.END

    gemini = get_gemini_client()
    if not gemini:
        await update.message.reply_text(
            "ℹ️ *Астрономический расчёт готов!*\n\n"
            "Для подключения глубокой текстовой трактовки карты от ИИ добавь `GEMINI_API_KEY` в файл `.env`.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Проверка монетизации (если включен платный режим)
    has_paid = context.user_data.get("paid_chart", False)
    if PAYMENT_REQUIRED and not has_paid:
        await update.message.reply_text(
            "🌟 *Натальная карта успешно построена!*\n\n"
            "Хочешь получить подробную расшифровку судьбы, предназначения, сильных сторон и кармических уроков от ИИ-астролога?\n"
            f"Стоимость разбора: **{PRICE_CHART_STARS} ⭐️**",
            parse_mode="Markdown"
        )
        await send_chart_invoice(update, context)
        return ConversationHandler.END

    # Если оплачено или в бесплатном режиме:
    ai_status = await update.message.reply_text("🔮 ИИ-Астролог составляет подробную трактовку твоей карты...")
    try:
        interpretation = await gemini.interpret_chart(chart_data, summary)
        await ai_status.delete()
        await send_split_message(update, f"📜 *Интерпретация карты от ИИ:*\n\n{interpretation}")
    except Exception as e:
        logger.exception("Ошибка генерации Gemini")
        await ai_status.edit_text(f"⚠️ Не удалось получить ответ ИИ: {e}")

    return ConversationHandler.END


# ===================== КОМАНДА ДАША (ПЕРИОДЫ) =====================

async def dasha_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать и интерпретировать периоды жизни Вимшоттари Даша."""
    profile = context.user_data.get("natal_profile")
    if not profile:
        await update.message.reply_text(
            "Сначала необходимо составить натальную карту!\nНажми /chart и введи данные рождения."
        )
        return

    chart_data = profile["chart_data"]
    summary = profile["summary"]
    dasha_text = format_dasha_periods(chart_data)

    await send_split_message(update, dasha_text)

    gemini = get_gemini_client()
    if not gemini:
        await update.message.reply_text(
            "💡 Чтобы получить анализ текущего периода жизни от ИИ, добавь `GEMINI_API_KEY` в файл `.env`."
        )
        return

    has_paid = context.user_data.get("paid_dasha", False)
    if PAYMENT_REQUIRED and not has_paid:
        await update.message.reply_text(
            "⏳ *Периоды рассчитаны!*\n\n"
            "Чтобы получить глубокий анализ текущего планетного периода (Маха-Даша и Антар-Даша) от ИИ с рекомендациями упай:\n"
            f"Стоимость разбора: **{PRICE_DASHA_STARS} ⭐️**",
            parse_mode="Markdown"
        )
        await send_dasha_invoice(update, context)
        return

    status_msg = await update.message.reply_text("🔮 Анализирую текущий период жизни через ИИ...")
    try:
        interpretation = await gemini.interpret_dasha(chart_data, summary)
        await status_msg.delete()
        await send_split_message(update, f"🌟 *Анализ текущего периода жизни:*\n\n{interpretation}")
    except Exception as e:
        logger.exception("Ошибка анализа даша")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе даша: {e}")


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
        await send_split_message(update, f"💘 *Анализ совместимости парных карт:*\n\n{result}")

    except Exception as e:
        logger.exception("Ошибка совместимости")
        await status_msg.edit_text(f"⚠️ Ошибка при анализе: {e}")

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
        status_msg = await update.message.reply_text("🔮 Составляю твой премиальный разбор натальной карты...")
        try:
            interpretation = await gemini.interpret_chart(chart_data, summary)
            await status_msg.delete()
            await send_split_message(update, f"📜 *Персональный разбор натальной карты:*\n\n{interpretation}")
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_dasha_interpretation":
        context.user_data["paid_dasha"] = True
        status_msg = await update.message.reply_text("⏳ Формирую подробный анализ планетных периодов...")
        try:
            interpretation = await gemini.interpret_dasha(chart_data, summary)
            await status_msg.delete()
            await send_split_message(update, f"🌟 *Анализ периодов судьбы (Даша):*\n\n{interpretation}")
        except Exception as e:
            await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")

    elif payload == "payload_compat_interpretation":
        context.user_data["paid_compat"] = True
        partner_chart = context.user_data.get("partner_chart")
        partner_summary = context.user_data.get("partner_summary")
        if partner_chart and partner_summary:
            status_msg = await update.message.reply_text("💞 Сопоставляю две карты по системе Аштакута...")
            try:
                interpretation = await gemini.interpret_compatibility(
                    chart_data, summary, partner_chart, partner_summary
                )
                await status_msg.delete()
                await send_split_message(update, f"💘 *Анализ совместимости парных карт:*\n\n{interpretation}")
            except Exception as e:
                await status_msg.edit_text(f"⚠️ Ошибка генерации: {e}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего ввода."""
    await update.message.reply_text(
        "Ввод отменён. Нажми /chart или /help в любой момент.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ===================== ТОЧКА ВХОДА =====================

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не задан в .env файле!")
        print("Открой c:\\Users\\Aleksandr\\Documents\\Private\\jyotish-bot\\.env и укажи токен от @BotFather.")
        sys.exit(1)

    app = Application.builder().token(token).build()

    # ConversationHandler для натальной карты
    chart_conv = ConversationHandler(
        entry_points=[
            CommandHandler("chart", chart_start),
            CommandHandler("natal", chart_start),
        ],
        states={
            WAITING_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_dob_received)],
            WAITING_TOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_tob_received)],
            WAITING_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_place_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    # ConversationHandler для совместимости
    compat_conv = ConversationHandler(
        entry_points=[CommandHandler("compat", compat_start)],
        states={
            COMPAT_WAITING_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_dob_received)],
            COMPAT_WAITING_TOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_tob_received)],
            COMPAT_WAITING_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, compat_place_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    # Регистрация команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prices", prices_command))
    app.add_handler(CommandHandler("mydata", mydata_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("dasha", dasha_command))
    app.add_handler(chart_conv)
    app.add_handler(compat_conv)

    # Регистрация платёжных хэндлеров (Telegram Stars)
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    print("🚀 Джьотиш-бот успешно запущен с поддержкой Telegram Stars!")
    app.run_polling()


if __name__ == "__main__":
    main()
