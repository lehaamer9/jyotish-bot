"""
Модуль интерпретации через Google Gemini API.
Использует официальный SDK google-genai для генерации персонализированных
ведических трактовок на русском языке.
"""
import os
import json
import asyncio
from typing import Optional


# Системный промпт для Джьотиш-астролога (оптимизирован для скорости)
JYOTISH_SYSTEM_PROMPT = """Ты — ведический астролог (Джьотиши) традиции Парашара (BPHS).
Отвечай ТОЛЬКО на русском. Используй ведическую терминологию с краткими пояснениями.
Анализируй: Лагну/Лагнешу, Чандру/накшатру, Сурью, бхавы, Вимшоттари Дашу.
Учитывай достоинство планет (учча/нича/сваграха/вакри).
Описывай кармические тенденции без фатальных предсказаний.
Давай упайи (мантры, благотворительность). Используй эмодзи и Markdown.
"""

CHART_INTERPRETATION_PROMPT = """Проанализируй натальную карту (D1).

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

# Актуальные модели (октябрь 2026): gemini-3.8-flash — флагман, gemini-2.5-flash — стабильный legacy
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
]

# Таймаут на один запрос к Gemini (секунды)
_REQUEST_TIMEOUT = 10


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

    async def interpret_chart(self, chart_data: dict, chart_summary: str) -> str:
        """Интерпретировать натальную карту."""
        compact = _compact_chart_json(chart_data)
        prompt = CHART_INTERPRETATION_PROMPT.format(
            chart_summary=chart_summary,
            chart_json=compact,
        )
        return await self._generate(prompt)

    async def interpret_dasha(self, chart_data: dict, chart_summary: str) -> str:
        """Интерпретировать периоды Даша."""
        prompt = DASHA_INTERPRETATION_PROMPT.format(
            chart_summary=chart_summary,
            dasha_json=json.dumps(chart_data["dashas"], ensure_ascii=False, indent=2),
        )
        return await self._generate(prompt)

    async def interpret_compatibility(self, chart1_data: dict, chart1_summary: str,
                                       chart2_data: dict, chart2_summary: str) -> str:
        """Интерпретировать совместимость двух карт."""
        compact1 = _compact_chart_json(chart1_data)
        compact2 = _compact_chart_json(chart2_data)
        prompt = COMPATIBILITY_PROMPT.format(
            chart1_summary=chart1_summary,
            chart2_summary=chart2_summary,
            chart1_json=compact1,
            chart2_json=compact2,
        )
        return await self._generate(prompt)

    async def interpret_ask_question(self, chart_data: dict, chart_summary: str,
                                      user_question: str, forecast_context: str = "") -> str:
        """Ответить на свободный вопрос пользователя на основе его натальной карты и прогноза."""
        compact = _compact_chart_json(chart_data)
        prompt = ASK_QUESTION_PROMPT.format(
            chart_summary=chart_summary,
            chart_json=compact,
            forecast_context=forecast_context,
            user_question=user_question,
        )
        return await self._generate(prompt)

    async def interpret_yogas(self, chart_data: dict, chart_summary: str,
                               yogas: list) -> str:
        """Интерпретировать обнаруженные ведические йоги через ИИ."""
        compact = _compact_chart_json(chart_data)
        prompt = YOGA_INTERPRETATION_PROMPT.format(
            chart_summary=chart_summary,
            chart_json=compact,
            yogas_json=json.dumps(yogas, ensure_ascii=False, indent=2),
        )
        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> str:
        """Выполнить асинхронный вызов модели Gemini с автоматическим фолбэком.

        Каждый запрос ограничен _REQUEST_TIMEOUT секунд.
        Последняя рабочая модель кэшируется и пробуется первой.
        """
        last_error = None

        # Построить порядок моделей: кэшированная первой, затем остальные
        models_to_try = list(CANDIDATE_MODELS)
        if GeminiInterpreter._working_model and GeminiInterpreter._working_model in models_to_try:
            models_to_try.remove(GeminiInterpreter._working_model)
            models_to_try.insert(0, GeminiInterpreter._working_model)

        for model_name in models_to_try:
            try:
                result = await asyncio.wait_for(
                    self._call_model(model_name, prompt),
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

    async def _call_model(self, model_name: str, prompt: str) -> Optional[str]:
        """Один вызов конкретной модели (без таймаута — обёртка в _generate)."""
        if self._use_new_sdk:
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=dict(system_instruction=JYOTISH_SYSTEM_PROMPT),
            )
            return response.text if response and response.text else None
        else:
            import google.generativeai as legacy_genai
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                system_instruction=JYOTISH_SYSTEM_PROMPT,
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
