"""
Модуль интерпретации через Google Gemini API.
Использует официальный SDK google-genai для генерации персонализированных
ведических трактовок на русском языке.
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Tuple


from i18n import normalize_language, get_planet_name
from jyotish_engine import get_current_dasha

MONTH_NAMES = {
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
}


def format_current_date_str(dt: Optional[datetime] = None, lang: str = "ru") -> str:
    """Форматирует текущую дату на указанном языке без привязки к локали ОС."""
    if dt is None:
        dt = datetime.now()
    norm_lang = normalize_language(lang)
    m_idx = dt.month - 1
    if norm_lang == "ru":
        return f"{dt.day} {MONTH_NAMES['ru'][m_idx]} {dt.year} г. ({dt.strftime('%d.%m.%Y')})"
    elif norm_lang == "it":
        return f"{dt.day} {MONTH_NAMES['it'][m_idx]} {dt.year} ({dt.strftime('%d.%m.%Y')})"
    else:  # en
        return f"{MONTH_NAMES['en'][m_idx]} {dt.day}, {dt.year} ({dt.strftime('%d.%m.%Y')})"


def format_current_dasha_info(chart_data: dict, dt: Optional[datetime] = None, lang: str = "ru") -> Tuple[str, str, str]:
    """
    Возвращает (dasha_info_str, md_name, ad_name) на указанном языке.
    """
    if dt is None:
        dt = datetime.now()
    norm_lang = normalize_language(lang)
    curr_dasha = get_current_dasha(chart_data, dt)
    md = curr_dasha.get("maha_dasha")
    ad = curr_dasha.get("antar_dasha")

    if norm_lang == "ru":
        md_name = md.get("planet_ru", md.get("planet", "Не определена")) if md else "Не определена"
        ad_name = ad.get("planet_ru", ad.get("planet", "Не определена")) if ad else "Не определена"
        lines = []
        if md:
            lines.append(f"• Маха-Даша: {md_name} (с {md.get('start')} по {md.get('end')})")
        if ad:
            lines.append(f"• Антар-Даша: {ad_name} (с {ad.get('start')} по {ad.get('end')})")
        dasha_info = "\n".join(lines) if lines else "Текущий период не определён"
    elif norm_lang == "it":
        md_p = get_planet_name(md.get("planet", ""), "it") if md else "Non definito"
        ad_p = get_planet_name(ad.get("planet", ""), "it") if ad else "Non definito"
        md_name = md_p
        ad_name = ad_p
        lines = []
        if md:
            lines.append(f"• Maha-Dasha: {md_name} (dal {md.get('start')} al {md.get('end')})")
        if ad:
            lines.append(f"• Antar-Dasha: {ad_name} (dal {ad.get('start')} al {ad.get('end')})")
        dasha_info = "\n".join(lines) if lines else "Periodo attuale non definito"
    else:  # en
        md_p = get_planet_name(md.get("planet", ""), "en") if md else "Not defined"
        ad_p = get_planet_name(ad.get("planet", ""), "en") if ad else "Not defined"
        md_name = md_p
        ad_name = ad_p
        lines = []
        if md:
            lines.append(f"• Maha-Dasha: {md_name} (from {md.get('start')} to {md.get('end')})")
        if ad:
            lines.append(f"• Antar-Dasha: {ad_name} (from {ad.get('start')} to {ad.get('end')})")
        dasha_info = "\n".join(lines) if lines else "Current period not defined"

    return dasha_info, md_name, ad_name


# Системные промпты для Джьотиш-астролога на разных языках
JYOTISH_SYSTEM_PROMPTS = {
    "ru": """Ты — ведический астролог (Джьотиши) традиции Парашара (BPHS).
Отвечай ТОЛЬКО на русском. Используй ведическую терминологию с краткими пояснениями.
Анализируй: Лагну/Лагнешу, Чандру/накшатру, Сурью, бхавы, Вимшоттари Дашу.
Учитывай достоинство планет (учча/нича/сваграха/вакри).
Описывай кармические тенденции без фатальных предсказаний.
Давай упайи (мантры, благотворительность). Используй эмодзи и Markdown.
""",
    "en": """You are a Vedic astrologer (Jyotishi) of the Parashara tradition (BPHS).
Respond ONLY in English. Use Vedic terminology with clear, concise explanations.
Analyze: Lagna/Lagnesha, Chandra/nakshatra, Surya, bhavas, Vimshottari Dasha.
Consider planetary dignity (uchcha/neecha/swagraha/vakra).
Describe karmic tendencies without fatalistic predictions.
Provide upayas (mantras, charity, behavioral remedies). Use emojis and Markdown.
""",
    "it": """Sei un astrologo vedico (Jyotishi) della tradizione Parashara (BPHS).
Rispondi ESCLUSIVAMENTE in italiano. Usa la terminologia vedica con spiegazioni chiare e concise.
Analizza: Lagna/Lagnesha, Chandra/nakshatra, Surya, bhava, Vimshottari Dasha.
Considera la dignità planetaria (uchcha/neecha/swagraha/vakra).
Descrivi le tendenze karmiche senza previsioni fatalistiche.
Fornisci upaya (mantra, beneficenza, rimedi comportamentali). Usa emoji e Markdown.
""",
}

JYOTISH_SYSTEM_PROMPT = JYOTISH_SYSTEM_PROMPTS["ru"]

CHART_INTERPRETATION_PROMPT = """Проанализируй натальную карту (D1).

Текущая дата: {current_date_str}
Текущий период (Вимшоттари Даша на {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{chart_json}
```

Дай интерпретацию по разделам:
1. 👤 **Личность:** Лагна, Лагнеша — характер и предназначение.
2. 🌙 **Эмоции:** Луна, накшатра — ум и реакции.
3. 💼 **Карьера:** 10-й дом, профессия.
4. 💰 **Финансы:** 2-й и 11-й дома, Дхана-йоги.
5. ❤️ **Партнёрство:** 7-й дом, Венера, Юпитер.
6. ⏳ **Текущий период:** Маха-Даша и Антар-Даша.
7. 🪔 **Упайи:** Практические рекомендации.
"""

DASHA_INTERPRETATION_PROMPT = """Проанализируй периоды Вимшоттари Даша.

Текущая дата: {current_date_str}
Текущий активный период (на {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{dasha_json}
```

Разбор:
1. 🌟 **Текущая Маха-Даша:** Хозяин периода, его положение, активируемые сферы.
2. 💫 **Антар-Даша:** Взаимодействие планет периода и подпериода.
3. 🎯 **Возможности:** Благоприятные сферы.
4. ⚠️ **Предостережения:** Чего избегать.
5. 🪔 **Упайи:** Гармонизация планет периода.
"""

COMPATIBILITY_PROMPT = """Синастрический анализ совместимости (Аштакута).

Партнёр 1: {chart1_summary}
Партнёр 2: {chart2_summary}

Карта 1:
```json
{chart1_json}
```
Карта 2:
```json
{chart2_json}
```

Интерпретация:
1. 🧬 **Ментальная гармония (Граха Майтри & Гана).**
2. ⚡ **Физическое притяжение (Йони Кута).**
3. 🌊 **Эмоциональная совместимость (Бхакут).**
4. 🛡️ **Кармическая связь (Нади & Тара).**
5. 💍 **Итог и рекомендации.**
"""

ASK_QUESTION_PROMPT = """Ты — опытный ведический астролог (Джьотиш). Ответь на вопрос пользователя, опираясь на его натальную карту и планетные периоды.

Текущая дата: {current_date_str}
Текущий период (Вимшоттари Даша на {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{chart_json}
```

{forecast_context}

Вопрос пользователя: {user_question}

Инструкция:
1. Если вопрос касается прогноза или времени («когда?», «что ждёт в ближайшие 1-2 года?», «благоприятно ли менять работу/жениться/переезжать?»):
   - Обязательно сопоставь вопрос с текущей Махадашей и Антардашей, их управителями и домами.
   - Укажи конкретные временные окна благоприятности и периоды, требующие осторожности.
2. Объясни астрологическую причину понятным языком: какие дома (бхавы) и планеты (грахи) активированы.
3. Дай практические рекомендации и ведические упайи (гармонизации) для смягчения негативных влияний и усиления благоприятных.
"""

YOGA_INTERPRETATION_PROMPT = """Проанализируй ведические йоги натальной карты.

{chart_summary}

```json
{chart_json}
```

Обнаруженные йоги:
```json
{yogas_json}
```

Для каждой АКТИВНОЙ йоги:
1. 📖 **Классическое описание** по шастрам (BPHS, Пхаладипика).
2. 🌟 **Практическое влияние** с учётом положения формирующих планет.
3. 💪 **Сила йоги** (сильная/средняя/слабая).
4. 🪔 **Рекомендации** для раскрытия потенциала.

Если активных йог нет — объясни ближайшие потенциальные йоги.
"""

KARMA_INTERPRETATION_PROMPT = """Ты — ведический астролог (Джьотиш). Проанализируй кармическую задачу души по системе Чара-Карак Джаймини (Атмакарака, Аматьякарака, Даракарака).

{chart_summary}

```json
{chart_json}
```

Данные карак:
```json
{karakas_json}
```

Структура разбора:
1. 🌟 **Атмакарака (Планета Души):** Главная кармическая задача воплощения, внутренний конфликт и урок, который душа пришла пройти.
2. 💼 **Аматьякарака (Вектор карьеры):** Профессия, социальная реализация, как зарабатывать деньги в согласии со своей природой.
3. 💍 **Даракарака (Партнёрство и любовь):** Какой партнёр предназначен по судьбе, какие кармические уроки в браке.
4. 🪔 **Практические упайи:** Рекомендации по гармонизации Атмакараки на каждый день.
"""

WEALTH_INTERPRETATION_PROMPT = """Ты — ведический астролог (Джьотиш). Проанализируй финансовый потенциал и карьерный код натальной карты (2, 10, 11 дома, Дхана-йоги).

{chart_summary}

```json
{chart_json}
```

Финансовые показатели:
```json
{wealth_json}
```

Структура разбора:
1. 🏦 **Источники богатства:** 2-й и 11-й дома — откуда приходят деньги (найм, бизнес, инвестиции, творчество).
2. 📈 **Карьерная стратегия:** 10-й дом и Аматьякарака — где ждёт признание, статус и масштабирование.
3. ⚠️ **Финансовые риски и блоки:** На что обращать внимание, где возможны утечки ресурсов.
4. 🪔 **Денежные Упайи:** Практические ведические методы привлечения финансового изобилия (дни, цвета, благотворительность).
"""

CHART_INTERPRETATION_PROMPTS = {
    "ru": CHART_INTERPRETATION_PROMPT,
    "en": """Analyze the natal chart (D1).

Current date: {current_date_str}
Active period (Vimshottari Dasha as of {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{chart_json}
```

Provide interpretation by sections:
1. 👤 **Personality:** Lagna, Lagnesha — character and soul purpose.
2. 🌙 **Emotions:** Moon, nakshatra — mind and psychological reactions.
3. 💼 **Career:** 10th house, profession and status.
4. 💰 **Wealth:** 2nd and 11th houses, Dhana yogas.
5. ❤️ **Partnership:** 7th house, Venus, Jupiter.
6. ⏳ **Current Period:** Active Maha-Dasha and Antar-Dasha.
7. 🪔 **Upayas:** Practical remedial recommendations.
""",
    "it": """Analizza il tema natale (D1).

Data corrente: {current_date_str}
Periodo attivo (Vimshottari Dasha al {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{chart_json}
```

Fornisci l'interpretazione suddivisa in sezioni:
1. 👤 **Personalità:** Lagna, Lagnesha — carattere e missione dell'anima.
2. 🌙 **Emozioni:** Luna, nakshatra — mente e reazioni psicologiche.
3. 💼 **Carriera:** 10ª casa, professione e status.
4. 💰 **Finanze:** 2ª e 11ª casa, Dhana Yoga.
5. ❤️ **Relazioni:** 7ª casa, Venere, Giove.
6. ⏳ **Periodo Attuale:** Maha-Dasha e Antar-Dasha attive.
7. 🪔 **Upaya:** Raccomandazioni pratiche di armonizzazione.
"""
}

DASHA_INTERPRETATION_PROMPTS = {
    "ru": DASHA_INTERPRETATION_PROMPT,
    "en": """Analyze Vimshottari Dasha planetary periods.

Current date: {current_date_str}
Active planetary period (as of {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{dasha_json}
```

Analysis breakdown:
1. 🌟 **Current Maha-Dasha:** Period lord, its placement, activated spheres.
2. 💫 **Antar-Dasha:** Interaction between period and sub-period lords.
3. 🎯 **Opportunities:** Favorable life areas and timing.
4. ⚠️ **Cautions:** What to avoid during this phase.
5. 🪔 **Upayas:** Harmonization methods for the period planets.
""",
    "it": """Analizza i periodi planetari Vimshottari Dasha.

Data reale corrente: {current_date_str}
Periodo planetario attivo (al {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{dasha_json}
```

Struttura dell'analisi:
1. 🌟 **Maha-Dasha Attuale:** Governatore del periodo, posizione e sfere attivate.
2. 💫 **Antar-Dasha:** Interazione tra governatore del periodo e del sottoperiodo.
3. 🎯 **Opportunità:** Aree favorevoli e tempistiche propizie.
4. ⚠️ **Precauzioni:** Cosa evitare durante questa fase.
5. 🪔 **Upaya:** Metodi di armonizzazione per i pianeti del periodo.
"""
}

COMPATIBILITY_PROMPTS = {
    "ru": COMPATIBILITY_PROMPT,
    "en": """Synastry relationship compatibility analysis (Ashtakoota).

Partner 1: {chart1_summary}
Partner 2: {chart2_summary}

Chart 1:
```json
{chart1_json}
```
Chart 2:
```json
{chart2_json}
```

Interpretation:
1. 🧬 **Mental Harmony (Graha Maitri & Gana).**
2. ⚡ **Physical Attraction (Yoni Kuta).**
3. 🌊 **Emotional Compatibility (Bhakoot).**
4. 🛡️ **Karmic Bond (Nadi & Tara).**
5. 💍 **Conclusion and Recommendations.**
""",
    "it": """Analisi di sinastria e compatibilità di coppia (Ashtakoota).

Partner 1: {chart1_summary}
Partner 2: {chart2_summary}

Carta 1:
```json
{chart1_json}
```
Carta 2:
```json
{chart2_json}
```

Interpretazione:
1. 🧬 **Armonia Mentale (Graha Maitri & Gana).**
2. ⚡ **Attrazione Fisica (Yoni Kuta).**
3. 🌊 **Compatibilità Emotiva (Bhakoot).**
4. 🛡️ **Legame Karmico (Nadi & Tara).**
5. 💍 **Conclusione e Consigli pratici.**
"""
}

ASK_QUESTION_PROMPTS = {
    "ru": ASK_QUESTION_PROMPT,
    "en": """You are an experienced Vedic astrologer (Jyotishi). Answer the user's question based on their birth chart and planetary periods.

Current date: {current_date_str}
Active period (Vimshottari Dasha as of {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{chart_json}
```

{forecast_context}

User question: {user_question}

Instructions:
1. If the question concerns forecasts or timing ("when?", "what to expect in the next 1-2 years?", "favorable time to change job/get married/relocate?"):
   - Correlate with current Maha-Dasha and Antar-Dasha, their lords and houses.
   - Specify favorable windows and periods requiring caution.
2. Explain astrological reasons clearly: which houses (bhavas) and planets (grahas) are activated.
3. Give practical recommendations and Vedic upayas (remedies).
""",
    "it": """Sei un esperto astrologo vedico (Jyotishi). Rispondi alla domanda dell'utente basandoti sul suo tema natale e sui periodi planetari.

Data corrente: {current_date_str}
Periodo attivo (Vimshottari Dasha al {current_date_str}):
{current_dasha_info}

{chart_summary}

```json
{chart_json}
```

{forecast_context}

Domanda dell'utente: {user_question}

Istruzioni:
1. Se la domanda riguarda previsioni o tempistiche ("quando?", "cosa aspettarsi nei prossimi 1-2 anni?", "è favorevole cambiare lavoro/sposarsi/trasferirsi?"):
   - Collega la domanda alla Maha-Dasha e Antar-Dasha attuali, ai rispettivi governatori e alle case.
   - Indica finestre temporali favorevoli e periodi che richiedono prudenza.
2. Spiega le motivazioni astrologiche in modo chiaro: quali case (bhava) e pianeti (graha) sono attivati.
3. Fornisci consigli pratici e upaya vedici (armonizzazioni).
"""
}

YOGA_INTERPRETATION_PROMPTS = {
    "ru": YOGA_INTERPRETATION_PROMPT,
    "en": """Analyze Vedic yogas in the natal chart.

{chart_summary}

```json
{chart_json}
```

Detected yogas:
```json
{yogas_json}
```

For each ACTIVE yoga:
1. 📖 **Classical Description** from shastras (BPHS, Phaladeepika).
2. 🌟 **Practical Influence** considering forming planets and houses.
3. 💪 **Yoga Strength** (strong/moderate/weak).
4. 🪔 **Recommendations** to unlock its potential.

If no active yogas found, explain nearby potential combinations.
""",
    "it": """Analizza gli yoga vedici nel tema natale.

{chart_summary}

```json
{chart_json}
```

Yoga rilevati:
```json
{yogas_json}
```

Per ciascuno yoga ATTIVO:
1. 📖 **Descrizione Classica** secondo gli shastra (BPHS, Phaladeepika).
2. 🌟 **Influenza Pratica** in base alla posizione dei pianeti formatori.
3. 💪 **Forza dello Yoga** (forte/moderata/debole).
4. 🪔 **Raccomandazioni** per attivare il pieno potenziale.

Se non ci sono yoga attivi, spiega le combinazioni potenziali più vicine.
"""
}

KARMA_INTERPRETATION_PROMPTS = {
    "ru": KARMA_INTERPRETATION_PROMPT,
    "en": """You are a Vedic astrologer (Jyotishi). Analyze the soul's karmic task based on the Jaimini Chara Karakas system (Atmakaraka, Amatyakaraka, Darakaraka).

{chart_summary}

```json
{chart_json}
```

Karaka data:
```json
{karakas_json}
```

Breakdown structure:
1. 🌟 **Atmakaraka (Soul Planet):** Main karmic purpose, inner conflict, and lesson of this lifetime.
2. 💼 **Amatyakaraka (Career Vector):** Vocation, social fulfillment, earning in alignment with soul nature.
3. 💍 **Darakaraka (Partnership & Love):** Destined partner archetype, marriage lessons.
4. 🪔 **Practical Upayas:** Daily recommendations to harmonize Atmakaraka.
""",
    "it": """Sei un astrologo vedico (Jyotishi). Analizza il compito karmico dell'anima basato sul sistema dei Chara Karaka di Jaimini (Atmakaraka, Amatyakaraka, Darakaraka).

{chart_summary}

```json
{chart_json}
```

Dati dei Karaka:
```json
{karakas_json}
```

Struttura dell'analisi:
1. 🌟 **Atmakaraka (Pianeta dell'Anima):** Compito karmico principale, conflitto interiore e lezione di questa vita.
2. 💼 **Amatyakaraka (Vettore Carriera):** Vocazione, realizzazione sociale, guadagnare in accordo con la propria natura.
3. 💍 **Darakaraka (Relazioni e Amore):** Archetipo del partner predestinato, lezioni karmiche nel matrimonio.
4. 🪔 **Upaya Pratici:** Raccomandazioni quotidiane per armonizzare l'Atmakaraka.
"""
}

WEALTH_INTERPRETATION_PROMPTS = {
    "ru": WEALTH_INTERPRETATION_PROMPT,
    "en": """You are a Vedic astrologer (Jyotishi). Analyze the financial code and career potential of the birth chart (2nd, 10th, 11th houses, Dhana yogas).

{chart_summary}

```json
{chart_json}
```

Financial indicators:
```json
{wealth_json}
```

Breakdown structure:
1. 🏦 **Wealth Sources:** 2nd and 11th houses — where money comes from (employment, business, investments, creativity).
2. 📈 **Career Strategy:** 10th house and Amatyakaraka — where recognition, status, and scaling lie.
3. ⚠️ **Financial Risks & Blocks:** Resource leaks and traps to avoid.
4. 🪔 **Money Upayas:** Practical Vedic methods to attract financial abundance (days, colors, charity).
""",
    "it": """Sei un astrologo vedico (Jyotishi). Analizza il codice finanziario e il potenziale di carriera del tema natale (case 2ª, 10ª, 11ª, Dhana Yoga).

{chart_summary}

```json
{chart_json}
```

Indicatori finanziari:
```json
{wealth_json}
```

Struttura dell'analisi:
1. 🏦 **Fonti di Ricchezza:** 2ª e 11ª casa — da dove arriva il denaro (lavoro dipendente, impresa, investimenti, creatività).
2. 📈 **Strategia di Carriera:** 10ª casa e Amatyakaraka — dove risiedono riconoscimento, status e scalabilità.
3. ⚠️ **Rischi e Blocchi Finanziari:** A cosa prestare attenzione, possibili dispersioni di risorse.
4. 🪔 **Upaya per il Denaro:** Metodi vedici pratici per attrarre abbondanza (giorni, colori, beneficenza).
"""
}

# Актуальные модели (октябрь 2026): gemini-3.8-flash — флагман, gemini-2.5-flash — стабильный legacy
CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
]

# Таймаут на один запрос к Gemini (секунды)
_REQUEST_TIMEOUT = 25


class GeminiInterpreter:
    """Интерпретатор астрологических данных через Google Gemini API."""

    # Кэш последней рабочей модели — пробуется первой при следующем запросе
    _working_model: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY не задан.")

        # Попробуем инициализировать новый SDK google.genai
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self._use_new_sdk = True
        except Exception:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.api_key)
            self._use_new_sdk = False

    def get_system_instruction(self, lang: str = "ru") -> str:
        """Получить системную инструкцию на указанном языке."""
        norm = normalize_language(lang)
        return JYOTISH_SYSTEM_PROMPTS.get(norm, JYOTISH_SYSTEM_PROMPTS["ru"])

    async def interpret_chart(self, chart_data: dict, chart_summary: str, lang: str = "ru", now: Optional[datetime] = None) -> str:
        """Интерпретировать натальную карту."""
        lang = normalize_language(lang)
        if now is None:
            now = datetime.now()
        date_str = format_current_date_str(now, lang=lang)
        dasha_info, _, _ = format_current_dasha_info(chart_data, now, lang=lang)

        template = CHART_INTERPRETATION_PROMPTS.get(lang, CHART_INTERPRETATION_PROMPT)
        compact = _compact_chart_json(chart_data)
        prompt = template.format(
            chart_summary=chart_summary,
            chart_json=compact,
            current_date_str=date_str,
            current_dasha_info=dasha_info,
        )
        return await self._generate(prompt, lang=lang)

    async def interpret_dasha(self, chart_data: dict, chart_summary: str, lang: str = "ru", now: Optional[datetime] = None) -> str:
        """Интерпретировать периоды Даша."""
        lang = normalize_language(lang)
        if now is None:
            now = datetime.now()
        date_str = format_current_date_str(now, lang=lang)
        dasha_info, _, _ = format_current_dasha_info(chart_data, now, lang=lang)

        template = DASHA_INTERPRETATION_PROMPTS.get(lang, DASHA_INTERPRETATION_PROMPT)
        prompt = template.format(
            chart_summary=chart_summary,
            dasha_json=json.dumps(chart_data["dashas"], ensure_ascii=False, indent=2),
            current_date_str=date_str,
            current_dasha_info=dasha_info,
        )
        return await self._generate(prompt, lang=lang)

    async def interpret_compatibility(self, chart1_data: dict, chart1_summary: str,
                                       chart2_data: dict, chart2_summary: str, lang: str = "ru") -> str:
        """Интерпретировать совместимость двух карт."""
        lang = normalize_language(lang)
        template = COMPATIBILITY_PROMPTS.get(lang, COMPATIBILITY_PROMPT)
        compact1 = _compact_chart_json(chart1_data)
        compact2 = _compact_chart_json(chart2_data)
        prompt = template.format(
            chart1_summary=chart1_summary,
            chart2_summary=chart2_summary,
            chart1_json=compact1,
            chart2_json=compact2,
        )
        return await self._generate(prompt, lang=lang)

    async def interpret_ask_question(self, chart_data: dict, chart_summary: str,
                                      user_question: str, forecast_context: str = "", lang: str = "ru", now: Optional[datetime] = None) -> str:
        """Ответить на свободный вопрос пользователя на основе его натальной карты и прогноза."""
        lang = normalize_language(lang)
        if now is None:
            now = datetime.now()
        date_str = format_current_date_str(now, lang=lang)
        dasha_info, _, _ = format_current_dasha_info(chart_data, now, lang=lang)

        template = ASK_QUESTION_PROMPTS.get(lang, ASK_QUESTION_PROMPT)
        compact = _compact_chart_json(chart_data)
        prompt = template.format(
            chart_summary=chart_summary,
            chart_json=compact,
            forecast_context=forecast_context,
            user_question=user_question,
            current_date_str=date_str,
            current_dasha_info=dasha_info,
        )
        return await self._generate(prompt, lang=lang)

    async def interpret_yogas(self, chart_data: dict, chart_summary: str,
                               yogas: list, lang: str = "ru") -> str:
        """Интерпретировать обнаруженные ведические йоги через ИИ."""
        lang = normalize_language(lang)
        template = YOGA_INTERPRETATION_PROMPTS.get(lang, YOGA_INTERPRETATION_PROMPT)
        compact = _compact_chart_json(chart_data)
        prompt = template.format(
            chart_summary=chart_summary,
            chart_json=compact,
            yogas_json=json.dumps(yogas, ensure_ascii=False, indent=2),
        )
        return await self._generate(prompt, lang=lang)

    async def interpret_karma(self, chart_data: dict, chart_summary: str,
                              karakas: dict, lang: str = "ru") -> str:
        """Интерпретировать кармическую задачу души и Чара-караки через ИИ."""
        lang = normalize_language(lang)
        template = KARMA_INTERPRETATION_PROMPTS.get(lang, KARMA_INTERPRETATION_PROMPT)
        compact = _compact_chart_json(chart_data)
        prompt = template.format(
            chart_summary=chart_summary,
            chart_json=compact,
            karakas_json=json.dumps(karakas, ensure_ascii=False, indent=2),
        )
        return await self._generate(prompt, lang=lang)

    async def interpret_wealth(self, chart_data: dict, chart_summary: str,
                               wealth_data: dict, lang: str = "ru") -> str:
        """Интерпретировать финансовый потенциал и карьерный код через ИИ."""
        lang = normalize_language(lang)
        template = WEALTH_INTERPRETATION_PROMPTS.get(lang, WEALTH_INTERPRETATION_PROMPT)
        compact = _compact_chart_json(chart_data)
        prompt = template.format(
            chart_summary=chart_summary,
            chart_json=compact,
            wealth_json=json.dumps(wealth_data, ensure_ascii=False, indent=2),
        )
        return await self._generate(prompt, lang=lang)

    async def _generate(self, prompt: str, lang: str = "ru") -> str:
        """Выполнить асинхронный вызов модели Gemini с автоматическим фолбэком.

        Каждый запрос ограничен _REQUEST_TIMEOUT секунд.
        Последняя рабочая модель кэшируется и пробуется первой.
        """
        last_error = None
        lang = normalize_language(lang)

        # Построить порядок моделей: кэшированная первой, затем остальные
        models_to_try = list(CANDIDATE_MODELS)
        if GeminiInterpreter._working_model and GeminiInterpreter._working_model in models_to_try:
            models_to_try.remove(GeminiInterpreter._working_model)
            models_to_try.insert(0, GeminiInterpreter._working_model)

        for model_name in models_to_try:
            try:
                result = await asyncio.wait_for(
                    self._call_model(model_name, prompt, lang=lang),
                    timeout=_REQUEST_TIMEOUT,
                )
                if result:
                    # Запомнить рабочую модель для следующих вызовов
                    GeminiInterpreter._working_model = model_name
                    return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"{model_name}: таймаут {_REQUEST_TIMEOUT}с")
                # Сбросить кэш если кэшированная модель не отвечает
                if GeminiInterpreter._working_model == model_name:
                    GeminiInterpreter._working_model = None
                continue
            except Exception as e:
                last_error = e
                if GeminiInterpreter._working_model == model_name:
                    GeminiInterpreter._working_model = None
                continue
        return f"❌ Ошибка вызова Gemini API: {last_error}"

    async def _call_model(self, model_name: str, prompt: str, lang: str = "ru") -> Optional[str]:
        """Один вызов конкретной модели (без таймаута — обёртка в _generate)."""
        sys_instruction = JYOTISH_SYSTEM_PROMPTS.get(lang, JYOTISH_SYSTEM_PROMPTS["ru"])
        if self._use_new_sdk:
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=dict(system_instruction=sys_instruction),
            )
            return response.text if response and response.text else None
        else:
            import google.generativeai as legacy_genai
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                system_instruction=sys_instruction,
            )
            response = await model.generate_content_async(prompt)
            return response.text if response and response.text else None


def _compact_chart_json(chart_data: dict) -> str:
    """Компактный JSON для отправки в контекст LLM."""
    compact = {
        "panchanga": chart_data.get("panchanga", {}),
        "planets": [],
        "houses": chart_data.get("houses", []),
    }
    for p in chart_data.get("planets", []):
        compact["planets"].append({
            "name": p.get("name"),
            "sign": p.get("sign"),
            "degrees": p.get("degrees"),
            "house": p.get("house"),
            "nakshatra": p.get("nakshatra"),
            "pada": p.get("pada"),
            "motion": p.get("motion"),
            "dignity": p.get("dignity"),
            "lordship": p.get("lordship_houses"),
            "shadbala_rupas": p.get("shadbala_rupas", 0),
        })
    return json.dumps(compact, ensure_ascii=False, indent=2)
