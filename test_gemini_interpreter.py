"""
Unit-тесты для модуля gemini_interpreter.py.
Проверяют корректность инъекции текущей даты и математически активного периода Даша
в промпты на всех поддерживаемых языках (RU, EN, IT).
"""

import unittest
from datetime import datetime
from jyotish_engine import compute_chart, get_current_dasha
from gemini_interpreter import (
    format_current_date_str,
    format_current_dasha_info,
    CHART_INTERPRETATION_PROMPTS,
    DASHA_INTERPRETATION_PROMPTS,
    ASK_QUESTION_PROMPTS,
)


class TestGeminiInterpreter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Дата рождения 28.08.1998, 12:00, Москва
        cls.chart = compute_chart(
            birth_dt=datetime(1998, 8, 28, 12, 0),
            lat=55.7558,
            lon=37.6173,
            tz_offset=3.0,
            name="Test User 1998"
        )
        # Текущая дата: 22 октября 2026 года
        cls.target_now = datetime(2026, 10, 22, 14, 0)

    def test_format_current_date_str(self):
        ru_str = format_current_date_str(self.target_now, lang="ru")
        self.assertIn("22 октября 2026", ru_str)
        self.assertIn("22.10.2026", ru_str)

        en_str = format_current_date_str(self.target_now, lang="en")
        self.assertIn("October 22, 2026", en_str)
        self.assertIn("22.10.2026", en_str)

        it_str = format_current_date_str(self.target_now, lang="it")
        self.assertIn("22 ottobre 2026", it_str)
        self.assertIn("22.10.2026", it_str)

    def test_active_dasha_in_october_2026(self):
        # Для рождения 28.08.1998 на дату 22.10.2026 активным является Сатурн-Марс (11.03.2026 - 20.04.2027)
        curr = get_current_dasha(self.chart, self.target_now)
        self.assertEqual(curr["maha_dasha"]["planet"], "Saturn")
        self.assertEqual(curr["antar_dasha"]["planet"], "Mars")

        # Проверяем форматирование инфостроки RU
        dasha_info_ru, md_ru, ad_ru = format_current_dasha_info(self.chart, self.target_now, lang="ru")
        self.assertIn("Сатурн", dasha_info_ru)
        self.assertIn("Марс", dasha_info_ru)
        self.assertIn("Сатурн", md_ru)
        self.assertIn("Марс", ad_ru)

        # Проверяем форматирование инфостроки EN
        dasha_info_en, md_en, ad_en = format_current_dasha_info(self.chart, self.target_now, lang="en")
        self.assertIn("Saturn", dasha_info_en)
        self.assertIn("Mars", dasha_info_en)
        self.assertIn("Saturn", md_en)
        self.assertIn("Mars", ad_en)

        # Проверяем форматирование инфостроки IT
        dasha_info_it, md_it, ad_it = format_current_dasha_info(self.chart, self.target_now, lang="it")
        self.assertIn("Saturno", dasha_info_it)
        self.assertIn("Marte", dasha_info_it)
        self.assertIn("Saturno", md_it)
        self.assertIn("Marte", ad_it)

    def test_prompt_formatting_contains_exact_date_and_active_dasha(self):
        for lang in ["ru", "en", "it"]:
            date_str = format_current_date_str(self.target_now, lang=lang)
            dasha_info, _, _ = format_current_dasha_info(self.chart, self.target_now, lang=lang)

            # 1. Dasha Prompt
            dasha_prompt = DASHA_INTERPRETATION_PROMPTS[lang].format(
                chart_summary="SUMMARY",
                dasha_json="{}",
                current_date_str=date_str,
                current_dasha_info=dasha_info,
            )
            self.assertIn(date_str, dasha_prompt)
            self.assertIn(dasha_info, dasha_prompt)

            # 2. Chart Prompt
            chart_prompt = CHART_INTERPRETATION_PROMPTS[lang].format(
                chart_summary="SUMMARY",
                chart_json="{}",
                current_date_str=date_str,
                current_dasha_info=dasha_info,
            )
            self.assertIn(date_str, chart_prompt)
            self.assertIn(dasha_info, chart_prompt)

            # 3. Ask Question Prompt
            ask_prompt = ASK_QUESTION_PROMPTS[lang].format(
                chart_summary="SUMMARY",
                chart_json="{}",
                forecast_context="",
                user_question="Какая сейчас даша?",
                current_date_str=date_str,
                current_dasha_info=dasha_info,
            )
            self.assertIn(date_str, ask_prompt)
            self.assertIn(dasha_info, ask_prompt)


if __name__ == "__main__":
    unittest.main()
