"""
Тесты новых функций Джьотиш-Бота:
1. Чара-Караки Джаймини (Атмакарака и др.)
2. Финансовый анализ (Дхана-йоги, дома 2 и 11, Аматьякарака)
3. Куджа-Доша (Манглика) и формат совместимости
4. Ведические Упайи (гармонизация планет)
5. 1-й бесплатный вопрос в user_settings
"""
import unittest
import os
import tempfile
from datetime import datetime
from jyotish_engine import (
    compute_chart,
    calculate_chara_karakas,
    format_chara_karakas,
    analyze_wealth_and_career,
    format_wealth_analysis,
    check_kuja_dosha,
    get_upayas,
    format_upayas,
)
from bot import format_kuja_compatibility
from db_manager import init_db, is_free_ask_available, mark_free_ask_used


class TestNewFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Тестовая натальная карта (Москва, 15.05.1990, 10:30)
        cls.chart = compute_chart(
            birth_dt=datetime(1990, 5, 15, 10, 30),
            lat=55.7558,
            lon=37.6173,
            tz_offset=3.0,
            name="Test User"
        )

    def test_chara_karakas(self):
        karakas = calculate_chara_karakas(self.chart)
        self.assertIn("karakas", karakas)
        self.assertEqual(len(karakas["karakas"]), 7)
        ak = karakas.get("atmakaraka")
        self.assertIsNotNone(ak)
        self.assertIn("planet", ak)
        formatted = format_chara_karakas(karakas)
        self.assertIn("Атмакарака", formatted)
        self.assertIn("Главный кармический урок", formatted)

    def test_wealth_and_career(self):
        wealth = analyze_wealth_and_career(self.chart)
        self.assertIn("house_2", wealth)
        self.assertIn("house_11", wealth)
        self.assertIn("house_10", wealth)
        formatted = format_wealth_analysis(wealth)
        self.assertIn("2-й дом", formatted)
        self.assertIn("11-й дом", formatted)
        self.assertIn("10-й дом", formatted)

    def test_kuja_dosha(self):
        kuja = check_kuja_dosha(self.chart)
        self.assertIn("has_dosha", kuja)
        self.assertIn("mars_house", kuja)

        # Проверка форматирования для пары
        kuja_pair_text = format_kuja_compatibility(self.chart, self.chart, "Александр", "Партнёр")
        self.assertIn("Анализ Куджа-Доши", kuja_pair_text)

    def test_upayas(self):
        upayas = get_upayas(self.chart)
        self.assertIn("remedies", upayas)
        self.assertGreater(len(upayas["remedies"]), 0)
        formatted = format_upayas(upayas)
        self.assertIn("Мантра (108 раз):", formatted)
        self.assertIn("День для практики:", formatted)

    def test_free_ask_db(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db = os.path.join(tmp_dir, "test_settings.db")
            init_db(test_db)
            user_id = 999888777
            self.assertTrue(is_free_ask_available(user_id, test_db))
            mark_free_ask_used(user_id, test_db)
            self.assertFalse(is_free_ask_available(user_id, test_db))


if __name__ == "__main__":
    unittest.main()
