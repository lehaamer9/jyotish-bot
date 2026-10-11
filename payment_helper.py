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
PRICE_COMPAT_STARS = int(os.getenv("PRICE_COMPAT_STARS", "200"))

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


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ответ на pre-checkout запрос Telegram.
    Подтверждает Telegram, что бот готов принять платёж.
    """
    query = update.pre_checkout_query
    payload = query.invoice_payload

    if payload in (
        "payload_chart_interpretation",
        "payload_dasha_interpretation",
        "payload_compat_interpretation",
    ):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Ошибка идентификатора заказа. Попробуйте снова.")
