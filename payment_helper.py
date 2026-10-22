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
PRICE_KARMA_STARS = int(os.getenv("PRICE_KARMA_STARS", "100"))    # Атмакарака и карма души
PRICE_MONEY_STARS = int(os.getenv("PRICE_MONEY_STARS", "100"))    # Финансовый код и карьера
PRICE_BUNDLE_STARS = int(os.getenv("PRICE_BUNDLE_STARS", "300"))  # Bundle «Вся судьба 360°»

# Флаг: обязательна ли оплата для получения ИИ-трактовки (True = только после оплаты, False = демо-режим)
PAYMENT_REQUIRED = os.getenv("PAYMENT_REQUIRED", "false").lower() in ("true", "1", "yes")

INVOICE_TEXTS = {
    "ru": {
        "chart_title": "🔮 Полный ведический разбор натальной карты",
        "chart_desc": "Глубокий анализ личности, кармических задач, домов, планет, текущего периода и персональных упай от ИИ-астролога.",
        "chart_label": "🔮 Полный ИИ-разбор натальной карты",
        "dasha_title": "⏳ Глубокий разбор периодов Вимшоттари Даша",
        "dasha_desc": "Подробный прогноз активной Маха-Даши и Антар-Даши, точки роста, предостережения и упайи.",
        "dasha_label": "⏳ Анализ планетных периодов Даша",
        "compat_title": "💞 Ведический анализ совместимости (Аштакута)",
        "compat_desc": "Синастрия двух карт по 8 факторам любви, ментальной связи, темпераментов и кармических узлов.",
        "compat_label": "💞 Анализ совместимости пар (Аштакута)",
        "ask_title": "💬 Экспресс-вопрос к ИИ-астрологу",
        "ask_desc": "Задай любой вопрос по своей карте — ИИ даст персональный ответ на основе твоей натальной карты.",
        "ask_label": "💬 Экспресс-вопрос к ИИ-астрологу",
        "yoga_title": "🏛️ Детектор ведических Йог",
        "yoga_desc": "Поиск Раджа-йог, Дхана-йог, Гаджакешари и Панча Махапуруша с персональным ИИ-разбором.",
        "yoga_label": "🏛️ Детектор Йог + ИИ-интерпретация",
        "bundle_title": "🔥 Bundle «Вся судьба 360°» — скидка 25%",
        "bundle_desc": "Полный комплект: Натальная карта + Даша-анализ + Совместимость. В пакете {bundle} ⭐️!",
        "bundle_label": "🔥 Вся судьба 360° (Карта+Даша+Совместимость)",
        "karma_title": "🔮 Разбор кармической задачи души (Атмакарака)",
        "karma_desc": "Глубокий анализ высшей цели воплощения, кармических уроков и вектора карьеры по Джаймини.",
        "karma_label": "🔮 Кармическая задача души (Атмакарака)",
        "money_title": "💰 Финансовый код и Карьера (Дхана & Карма)",
        "money_desc": "Анализ источников богатства (2 и 11 дома), карьерного призвания (10 дом), Дхана-йог и денежных упай.",
        "money_label": "💰 Финансовый код и Карьера",
    },
    "en": {
        "chart_title": "🔮 Full Vedic Natal Chart Reading",
        "chart_desc": "Deep analysis of personality, soul purpose, houses, planets, active periods, and personal upayas from AI astrologer.",
        "chart_label": "🔮 Full AI Natal Chart Reading",
        "dasha_title": "⏳ Deep Vimshottari Dasha Analysis",
        "dasha_desc": "Detailed forecast for active Maha-Dasha and Antar-Dasha, growth opportunities, cautions, and upayas.",
        "dasha_label": "⏳ Vimshottari Dasha Periods Analysis",
        "compat_title": "💞 Vedic Compatibility Analysis (Ashtakoota)",
        "compat_desc": "Synastry of two charts across 8 factors of love, mental harmony, temperaments, and karmic knots.",
        "compat_label": "💞 Partnership Compatibility (Ashtakoota)",
        "ask_title": "💬 Express Question to AI Astrologer",
        "ask_desc": "Ask any question about your chart — AI provides a personalized answer based on your Vedic birth chart.",
        "ask_label": "💬 Express Question to AI Astrologer",
        "yoga_title": "🏛️ Vedic Yoga Detector + AI Interpretation",
        "yoga_desc": "Detection of Raja, Dhana, Gaja Kesari, and Pancha Mahapurusha yogas with custom AI interpretation.",
        "yoga_label": "🏛️ Yoga Detector + AI Reading",
        "bundle_title": "🔥 All-in-One 360° Bundle — 25% Discount",
        "bundle_desc": "Full package: Natal Chart + Dasha Analysis + Compatibility. In package {bundle} ⭐️!",
        "bundle_label": "🔥 All-in-One 360° (Chart+Dasha+Synastry)",
        "karma_title": "🔮 Soul Karmic Task (Atmakaraka)",
        "karma_desc": "Deep analysis of the highest incarnation purpose, life lessons, and career vector according to Jaimini.",
        "karma_label": "🔮 Soul Karmic Task (Atmakaraka)",
        "money_title": "💰 Wealth Code & Career Strategy",
        "money_desc": "Analysis of wealth houses (2 & 11), career vocation (10), Dhana yogas, and remedial money practices.",
        "money_label": "💰 Wealth Code & Career",
    },
    "it": {
        "chart_title": "🔮 Analisi Completa del Tema Natale",
        "chart_desc": "Studio approfondito della personalità, missione dell'anima, case, pianeti, periodi attivi e upaya personalizzati dall'Astrologo IA.",
        "chart_label": "🔮 Analisi Completa Tema Natale",
        "dasha_title": "⏳ Analisi Periodi Vimshottari Dasha",
        "dasha_desc": "Previsione dettagliata per Maha-Dasha e Antar-Dasha attive, punti di forza, avvertimenti e upaya.",
        "dasha_label": "⏳ Analisi Periodi Planetari Dasha",
        "compat_title": "💞 Analisi di Compatibilità Vedica (Ashtakoota)",
        "compat_desc": "Sinastria di due carte attraverso gli 8 fattori dell'amore, armonia mentale, temperamento e nodi karmici.",
        "compat_label": "💞 Compatibilità di Coppia (Ashtakoota)",
        "ask_title": "💬 Domanda Espressa all'Astrologo IA",
        "ask_desc": "Poni qualsiasi domanda sul tuo tema natale — l'IA fornirà una risposta personalizzata.",
        "ask_label": "💬 Domanda Espressa all'Astrologo IA",
        "yoga_title": "🏛️ Rilevatore Yoga Vedici + Interpretazione IA",
        "yoga_desc": "Ricerca di Raja Yoga, Dhana Yoga, Gaja Kesari e Pancha Mahapurusha con interpretazione personalizzata.",
        "yoga_label": "🏛️ Rilevatore Yoga + Lettura IA",
        "bundle_title": "🔥 Pacchetto Completo 360° — Sconto 25%",
        "bundle_desc": "Kit completo: Tema Natale + Analisi Dasha + Compatibilità. Nel pacchetto a {bundle} ⭐️!",
        "bundle_label": "🔥 Tutto Incluso 360° (Carta+Dasha+Coppia)",
        "karma_title": "🔮 Compito Karmico dell'Anima (Atmakaraka)",
        "karma_desc": "Analisi dello scopo supremo dell'incarnazione, delle lezioni karmiche e della vocazione professionale secondo Jaimini.",
        "karma_label": "🔮 Compito Karmico (Atmakaraka)",
        "money_title": "💰 Codice Finanziario e Carriera",
        "money_desc": "Analisi delle case della ricchezza (2ª e 11ª), della carriera (10ª), Dhana Yoga e upaya per il denaro.",
        "money_label": "💰 Codice Finanziario e Carriera",
    }
}


def _get_invoice_text(key: str, lang: str = "ru", **kwargs) -> str:
    lang = lang.lower() if lang else "ru"
    if lang not in ("ru", "en", "it"):
        lang = "ru"
    t_dict = INVOICE_TEXTS.get(lang, INVOICE_TEXTS["ru"])
    val = t_dict.get(key, INVOICE_TEXTS["ru"].get(key, ""))
    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val


async def send_chart_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату полного разбора натальной карты."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("chart_label", lang), amount=PRICE_CHART_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("chart_title", lang),
        description=_get_invoice_text("chart_desc", lang),
        payload="payload_chart_interpretation",
        provider_token="",  # Для Telegram Stars (XTR) токен всегда пустой!
        currency="XTR",
        prices=prices,
    )


async def send_dasha_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату разбора периодов Вимшоттари Даша."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("dasha_label", lang), amount=PRICE_DASHA_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("dasha_title", lang),
        description=_get_invoice_text("dasha_desc", lang),
        payload="payload_dasha_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_compat_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату анализа совместимости парных карт."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("compat_label", lang), amount=PRICE_COMPAT_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("compat_title", lang),
        description=_get_invoice_text("compat_desc", lang),
        payload="payload_compat_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_ask_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату экспресс-вопроса к ИИ-астрологу (Tripwire)."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("ask_label", lang), amount=PRICE_ASK_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("ask_title", lang),
        description=_get_invoice_text("ask_desc", lang),
        payload="payload_ask_question",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_yoga_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату ИИ-интерпретации йог."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("yoga_label", lang), amount=PRICE_YOGA_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("yoga_title", lang),
        description=_get_invoice_text("yoga_desc", lang),
        payload="payload_yoga_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_bundle_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на Bundle «Вся судьба 360°» (скидка 25%)."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("bundle_label", lang), amount=PRICE_BUNDLE_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("bundle_title", lang),
        description=_get_invoice_text("bundle_desc", lang, bundle=PRICE_BUNDLE_STARS),
        payload="payload_bundle_360",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_karma_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату ИИ-разбора кармической задачи души (Атмакарака)."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("karma_label", lang), amount=PRICE_KARMA_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("karma_title", lang),
        description=_get_invoice_text("karma_desc", lang),
        payload="payload_karma_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_money_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = "ru"):
    """Отправить инвойс на оплату ИИ-разбора финансового кода и карьеры."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label=_get_invoice_text("money_label", lang), amount=PRICE_MONEY_STARS)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=_get_invoice_text("money_title", lang),
        description=_get_invoice_text("money_desc", lang),
        payload="payload_money_interpretation",
        provider_token="",
        currency="XTR",
        prices=prices,
    )


async def send_test_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить тестовый инвойс на 1 Звезду (для проверки работы платежей админом)."""
    chat_id = update.effective_chat.id
    prices = [LabeledPrice(label="🧪 Тестовый платёж Stars", amount=1)]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="🧪 Тестовый платёж (1 ⭐️)",
        description="Проверка работы платёжной системы Telegram Stars. Спишет ровно 1 ⭐️.",
        payload="payload_test_payment",
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
        "payload_karma_interpretation",
        "payload_money_interpretation",
        "payload_bundle_360",
        "payload_test_payment",
    )

    if payload in valid_payloads:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Ошибка идентификатора заказа. Попробуйте снова.")

