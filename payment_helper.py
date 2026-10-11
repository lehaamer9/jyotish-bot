"""
Модуль монетизации и приёма платежей через Telegram Stars (валюта XTR).
Позволяет пользователям оплачивать глубокие ИИ-интерпретации в 1 клик прямо в Telegram.
"""
import os
import logging
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Цены в Звёздах Telegram (XTR)
# Значения можно переопределить через переменные окружения в .env
PRICE_CHART_STARS = int(os.getenv("PRICE_CHART_STARS", "150"))
PRICE_DASHA_STARS = int(os.getenv("PRICE_DASHA_STARS", "100"))
PRICE_COMPAT_STARS = int(os.getenv("PRICE_COMPAT_STARS", "150"))  # Снижено с 200 до 150
PRICE_ASK_STARS = int(os.getenv("PRICE_ASK_STARS", "50"))         # Tripwire — экспресс-вопрос
PRICE_YOGA_STARS = int(os.getenv("PRICE_YOGA_STARS", "100"))      # Детектор йог + ИИ-разбор
PRICE_BUNDLE_STARS = int(os.getenv("PRICE_BUNDLE_STARS", "300"))  # Bundle «Вся судьба 360°»

# Флаг: обязательна ли оплата для получения ИИ-трактовки (True = только после оплаты, False = демо-режим)
PAYMENT_REQUIRED = os.getenv("PAYMENT_REQUIRED", "false").lower() in ("true", "1", "yes")


async def send_chart_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить инвойс на оплату полного разбора натальной карты."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="🔮 Полный ИИ-разбор натальной карты", amount=PRICE_CHART_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="🔮 Полный ведический разбор натальной карты",
        description=(
            "Глубокий анализ личности, кармических задач, домов, "
            "планет, текущего периода и персональных упай от ИИ-астролога."
        ),
        payload="payload_chart_interpretation",
        provider_token="",  # Для Telegram Stars (XTR) токен всегда пустой!
        currency="XTR",
        prices=prices,
    )


async def send_dasha_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить инвойс на оплату разбора периодов Вимшоттари Даша."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="⏳ Анализ планетных периодов Даша", amount=PRICE_DASHA_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="⏳ Глубокий разбор периодов Вимшоттари Даша",
        description="Подробный прогноз активной Маха-Даши и Антар-Даши, точки роста, предостережения и упайи.",
        payload="payload_dasha_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_compat_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить инвойс на оплату анализа совместимости парных карт."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="💞 Анализ совместимости пар (Аштакута)", amount=PRICE_COMPAT_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="💞 Ведический анализ совместимости (Аштакута)",
        description="Синастрия двух карт по 8 факторам любви, ментальной связи, темпераментов и кармических узлов.",
        payload="payload_compat_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_ask_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить инвойс на оплату экспресс-вопроса к ИИ-астрологу (Tripwire)."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="💬 Экспресс-вопрос к ИИ-астрологу", amount=PRICE_ASK_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="💬 Экспресс-вопрос к ИИ-астрологу",
        description="Задай любой вопрос по своей карте — ИИ даст персональный ответ на основе твоей натальной карты.",
        payload="payload_ask_question",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_yoga_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить инвойс на оплату ИИ-интерпретации йог."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="🏛️ Детектор Йог + ИИ-интерпретация", amount=PRICE_YOGA_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="🏛️ Детектор ведических Йог",
        description="Поиск Раджа-йог, Дхана-йог, Гаджакешари и Панча Махапуруша с персональным ИИ-разбором.",
        payload="payload_yoga_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_bundle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить инвойс на Bundle «Вся судьба 360°» (скидка 25%)."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="🔥 Вся судьба 360° (Карта+Даша+Совместимость)", amount=PRICE_BUNDLE_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="🔥 Bundle «Вся судьба 360°» — скидка 25%",
        description=(
            "Полный комплект: Натальная карта + Даша-анализ + Совместимость. "
            f"По отдельности {PRICE_CHART_STARS + PRICE_DASHA_STARS + PRICE_COMPAT_STARS} ⭐️, "
            f"в пакете {PRICE_BUNDLE_STARS} ⭐️!"
        ),
        payload="payload_bundle_360",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ответ на pre-checkout запрос Telegram.
    Подтверждает Telegram, что бот готов принять платёж.
    """
    query = update.pre_checkout_query
    payload = query.invoice_payload

    valid_payloads = (
        "payload_chart_interpretation",
        "payload_dasha_interpretation",
        "payload_compat_interpretation",
        "payload_ask_question",
        "payload_yoga_interpretation",
        "payload_bundle_360",
    )

    if payload in valid_payloads:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Ошибка идентификатора заказа. Попробуйте снова.")
