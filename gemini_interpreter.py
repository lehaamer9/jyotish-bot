"""
Модуль интерпретации через Google Gemini API.
Использует официальный SDK google-genai для генерации персонализированных
ведических трактовок на русском языке.
"""
import os
import json
import asyncio
from typing import Optional


# Системный промпт для Джьотиш-астролога
JYOTISH_SYSTEM_PROMPT = """Ты — опытный ведический астролог (Джьотиши), следующий традициям Парашара Муни.
Ты интерпретируешь натальные карты строго по классическим канонам:
- Брихат Парашара Хора Шастра (BPHS)
- Джатака Париджата
- Пхаладипика
- Саравали

Твои принципы:
1. Отвечай ТОЛЬКО на русском языке.
2. Используй ведическую терминологию с понятными русскими пояснениями (например: "Раджа-йога — союз правителей кендр и трикон, дарующий успех и реализацию").
3. Анализируй структурированно:
   - Лагна (асцендент) и Лагнеша (хозяин 1-го дома) — физическое тело, вектор судьбы
   - Чандра (Луна) и накшатра рождения (Джанма-накшатра) — ум, эмоциональный склад
   - Сурья (Солнце) — дух, эго, жизненная сила
   - Дома (бхавы) и планеты в них
   - Текущие планетные периоды (Вимшоттари Маха-Даша и Антар-Даша)
4. Учитывай достоинство планет: экзальтация (учча), падение (нича), собственный знак (сваграха), ретроградность (вакри).
5. Не делай фатальных предсказаний. Описывай кармические тенденции, уроки души и зоны роста.
6. В конце давай традиционные гармонизирующие рекомендации (упайи): мантра, благотворительность, цвета, режим дня.
7. Используй аккуратные эмодзи (🔮, 🪐, 🌟, ✨) и форматирование Markdown.
"""

CHART_INTERPRETATION_PROMPT = """Проанализируй следующую натальную карту (Кундли D1) ведической астрологии.

{chart_summary}

Структурированные данные карты (JSON):
```json
{chart_json}
```

Дай развёрнутую персональную интерпретацию по разделам:
1. 👤 **Личность и предназначение:** Восходящий знак (Лагна), управитель Лагны и их влияние на характер.
2. 🌙 **Внутренний мир и эмоции:** Луна, знак Луны и лунная накшатра (природа ума, реакции).
3. 💼 **Карьера и статус:** Анализ 10-го дома, сильные стороны в профессии и бизнесе.
4. 💰 **Финансы и благосостояние:** 2-й и 11-й дома богатства (Дхана-йоги).
5. ❤️ **Любовь и партнёрство:** 7-й дом, положение Венеры и Юпитера.
6. ⏳ **Текущий этап жизни:** Активная Маха-Даша и Антар-Даша — какие темы выходят на первый план прямо сейчас.
7. 🪔 **Рекомендации (Упайи):** Практические советы для балансировки слабых и усиления сильных планет.
"""

DASHA_INTERPRETATION_PROMPT = """Проанализируй текущий и предстоящие периоды Вимшоттари Даша для этой натальной карты.

{chart_summary}

Данные периодов:
```json
{dasha_json}
```

Составь глубокий астрологический разбор:
1. 🌟 **Текущая Маха-Даша:** Хозяин периода, его положение в карте, какие сферы жизни он сейчас активирует.
2. 💫 **Текущая Антар-Даша:** Взаимодействие планеты подпериода с главной планетой периода.
3. 🎯 **Благоприятные возможности:** В чем сейчас сопутствует удача (обучение, карьера, недвижимость, духовность).
4. ⚠️ **Предостережения:** Каких ошибок и импульсивных решений стоит избегать.
5. 🪔 **Упайи на текущий период:** Конкретные методы гармонизации управляющих планет.
"""

COMPATIBILITY_PROMPT = """Проведи синастрический анализ совместимости двух карт по системе Аштакута (8 факторов ведической совместимости).

Партнёр 1:
{chart1_summary}

Партнёр 2:
{chart2_summary}

Данные карты 1:
```json
{chart1_json}
```

Данные карты 2:
```json
{chart2_json}
```

Дай подробную интерпретацию союза:
1. 🧬 **Психологическая и ментальная гармония (Граха Майтри & Гана):** Насколько легко людям понимать друг друга.
2. ⚡ **Физическое и сексуальное притяжение (Йони Кута):** Совместимость природных темпераментов.
3. 🌊 **Эмоциональная глубина и поддержка (Бхакут):** Расположение Лун относительно друг друга.
4. 🛡️ **Кармическая связь и здоровье союза (Нади & Тара):** Энергетический баланс пары.
5. 💍 **Итог и рекомендации для гармоничных отношений:** Сильные стороны союза и над чем стоит работать осознанно.
"""


class GeminiInterpreter:
    """Интерпретатор астрологических данных через Google Gemini API."""

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
            self.legacy_model = legacy_genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=JYOTISH_SYSTEM_PROMPT
            )
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

    async def _generate(self, prompt: str) -> str:
        """Выполнить асинхронный вызов модели Gemini."""
        try:
            if self._use_new_sdk:
                # Асинхронный вызов нового google.genai SDK
                response = await self.client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=dict(system_instruction=JYOTISH_SYSTEM_PROMPT)
                )
                return response.text
            else:
                response = await self.legacy_model.generate_content_async(prompt)
                return response.text
        except Exception as e:
            return f"❌ Ошибка вызова Gemini API: {e}"


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
