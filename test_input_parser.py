"""
Unit-тесты для модуля умного парсинга одной строки input_parser.py.
"""

import unittest
from datetime import date, time
from input_parser import parse_one_line_profile


class TestInputParser(unittest.TestCase):
    def test_standard_comma_separated(self):
        res = parse_one_line_profile("Александр, 20.06.1996, 08:25, Горно-Алтайск")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Александр")
        self.assertEqual(res["dob"], date(1996, 6, 20))
        self.assertEqual(res["tob"], time(8, 25))
        self.assertEqual(res["city"], "Горно-Алтайск")
        self.assertTrue(res["is_complete"])

    def test_space_separated(self):
        res = parse_one_line_profile("Александр 15.05.1990 10:30 Москва")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Александр")
        self.assertEqual(res["dob"], date(1990, 5, 15))
        self.assertEqual(res["tob"], time(10, 30))
        self.assertEqual(res["city"], "Москва")
        self.assertTrue(res["is_complete"])

    def test_no_name(self):
        res = parse_one_line_profile("20.06.1996 08:25 Горно-Алтайск")
        self.assertIsNotNone(res)
        self.assertIsNone(res["name"])
        self.assertEqual(res["dob"], date(1996, 6, 20))
        self.assertEqual(res["tob"], time(8, 25))
        self.assertEqual(res["city"], "Горно-Алтайск")
        self.assertTrue(res["is_complete"])

    def test_name_at_end(self):
        res = parse_one_line_profile("15.05.1990 10:30 Москва, Александр")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Александр")
        self.assertEqual(res["dob"], date(1990, 5, 15))
        self.assertEqual(res["tob"], time(10, 30))
        self.assertEqual(res["city"], "Москва")
        self.assertTrue(res["is_complete"])

    def test_with_chart_command_prefix(self):
        res = parse_one_line_profile("/chart Александр, 20.06.1996, 08:25, Горно-Алтайск")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Александр")
        self.assertEqual(res["dob"], date(1996, 6, 20))
        self.assertEqual(res["tob"], time(8, 25))
        self.assertEqual(res["city"], "Горно-Алтайск")
        self.assertTrue(res["is_complete"])

    def test_with_newprofile_command_prefix(self):
        res = parse_one_line_profile("/newprofile Анна, 20.08.1992, 14:15, Санкт-Петербург")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Анна")
        self.assertEqual(res["dob"], date(1992, 8, 20))
        self.assertEqual(res["tob"], time(14, 15))
        self.assertEqual(res["city"], "Санкт-Петербург")
        self.assertTrue(res["is_complete"])

    def test_with_prepositions_and_prefixes(self):
        res = parse_one_line_profile("Имя: Александр 20.06.1996 в 08:25 в г. Горно-Алтайск")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Александр")
        self.assertEqual(res["dob"], date(1996, 6, 20))
        self.assertEqual(res["tob"], time(8, 25))
        self.assertEqual(res["city"], "Горно-Алтайск")
        self.assertTrue(res["is_complete"])

    def test_time_with_dot(self):
        res = parse_one_line_profile("Александр 20.06.1996 8.25 Горно-Алтайск")
        self.assertIsNotNone(res)
        self.assertEqual(res["tob"], time(8, 25))
        self.assertTrue(res["is_complete"])

    def test_date_with_hyphen_and_slash(self):
        res_hyphen = parse_one_line_profile("Александр 20-06-1996 08:25 Горно-Алтайск")
        self.assertEqual(res_hyphen["dob"], date(1996, 6, 20))

        res_slash = parse_one_line_profile("Александр 20/06/1996 08:25 Горно-Алтайск")
        self.assertEqual(res_slash["dob"], date(1996, 6, 20))

    def test_partial_only_date(self):
        res = parse_one_line_profile("15.05.1990")
        self.assertIsNotNone(res)
        self.assertEqual(res["dob"], date(1990, 5, 15))
        self.assertIsNone(res["tob"])
        self.assertIsNone(res["city"])
        self.assertFalse(res["is_complete"])

    def test_partial_name_and_date(self):
        res = parse_one_line_profile("Александр, 15.05.1990")
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "Александр")
        self.assertEqual(res["dob"], date(1990, 5, 15))
        self.assertIsNone(res["tob"])
        self.assertIsNone(res["city"])
        self.assertFalse(res["is_complete"])

    def test_partial_date_and_time_no_city(self):
        res = parse_one_line_profile("15.05.1990 10:30")
        self.assertIsNotNone(res)
        self.assertEqual(res["dob"], date(1990, 5, 15))
        self.assertEqual(res["tob"], time(10, 30))
        self.assertIsNone(res["city"])
        self.assertFalse(res["is_complete"])

    def test_country_region_not_mistaken_for_name(self):
        res1 = parse_one_line_profile("20.06.1996 08:25 Горно-Алтайск, Россия")
        self.assertIsNotNone(res1)
        self.assertIsNone(res1["name"])
        self.assertEqual(res1["city"], "Горно-Алтайск, Россия")

        res2 = parse_one_line_profile("20.06.1996 08:25 Рим, Италия")
        self.assertIsNotNone(res2)
        self.assertIsNone(res2["name"])
        self.assertEqual(res2["city"], "Рим, Италия")

        res3 = parse_one_line_profile("20.06.1996 08:25 Санкт-Петербург, Ленинградская область")
        self.assertIsNotNone(res3)
        self.assertIsNone(res3["name"])
        self.assertEqual(res3["city"], "Санкт-Петербург, Ленинградская область")

    def test_city_prefix_variations(self):
        res1 = parse_one_line_profile("Александр, 20.06.1996 в 08:25 в городе Горно-Алтайск")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["name"], "Александр")
        self.assertEqual(res1["city"], "Горно-Алтайск")

        res2 = parse_one_line_profile("Александр 20.06.1996 08:25 в г. Горно-Алтайск")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["name"], "Александр")
        self.assertEqual(res2["city"], "Горно-Алтайск")

    def test_name_in_parentheses_or_keyword_at_end(self):
        res1 = parse_one_line_profile("20.06.1996 08:25 Горно-Алтайск (Александр)")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["name"], "Александр")
        self.assertEqual(res1["city"], "Горно-Алтайск")

        res2 = parse_one_line_profile("20.06.1996 08:25 Москва, имя: Александр")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["name"], "Александр")
        self.assertEqual(res2["city"], "Москва")

    def test_with_edit_and_recalc_command_prefix(self):
        res_edit = parse_one_line_profile("/edit Александр, 20.06.1996, 08:25, Горно-Алтайск")
        self.assertIsNotNone(res_edit)
        self.assertEqual(res_edit["name"], "Александр")
        self.assertEqual(res_edit["dob"], date(1996, 6, 20))
        self.assertEqual(res_edit["tob"], time(8, 25))
        self.assertEqual(res_edit["city"], "Горно-Алтайск")
        self.assertTrue(res_edit["is_complete"])

        res_recalc = parse_one_line_profile("/recalc 15.05.1990 10:30 Москва")
        self.assertIsNotNone(res_recalc)
        self.assertIsNone(res_recalc["name"])
        self.assertEqual(res_recalc["dob"], date(1990, 5, 15))
        self.assertEqual(res_recalc["tob"], time(10, 30))
        self.assertEqual(res_recalc["city"], "Москва")
        self.assertTrue(res_recalc["is_complete"])

        res_update = parse_one_line_profile("/update 24.12.1985 18:00 Рим")
        self.assertIsNotNone(res_update)
        self.assertEqual(res_update["city"], "Рим")
        self.assertTrue(res_update["is_complete"])

    def test_natural_language_edit_and_correction_prefixes(self):
        cases_none_name = [
            "исправь дату: 20.06.1996 08:25 Горно-Алтайск",
            "ошибка в дате 20.06.1996 08:25 Горно-Алтайск",
            "пересчитай 20.06.1996 08:25 Горно-Алтайск",
            "edit 20.06.1996 08:25 Rome",
            "дата: 20.06.1996 08:25 Горно-Алтайск",
            "новая дата 20.06.1996 08:25 Горно-Алтайск",
            "верная дата: 20.06.1996 08:25 Горно-Алтайск",
        ]
        for c in cases_none_name:
            res = parse_one_line_profile(c)
            self.assertIsNotNone(res, f"Failed to parse: {c}")
            self.assertIsNone(res["name"], f"Expected name=None for {c}, got {res['name']}")
            self.assertEqual(res["dob"], date(1996, 6, 20))
            self.assertEqual(res["tob"], time(8, 25))
            self.assertTrue(res["is_complete"])

        # Случаи, когда имя указано вместе с фразой пересчёта
        res_with_name1 = parse_one_line_profile("Александр, исправь дату на 20.06.1996 08:25 Горно-Алтайск")
        self.assertIsNotNone(res_with_name1)
        self.assertEqual(res_with_name1["name"], "Александр")
        self.assertEqual(res_with_name1["dob"], date(1996, 6, 20))

        res_with_name2 = parse_one_line_profile("исправь дату Александр 20.06.1996 08:25 Горно-Алтайск")
        self.assertIsNotNone(res_with_name2)
        self.assertEqual(res_with_name2["name"], "Александр")
        self.assertEqual(res_with_name2["dob"], date(1996, 6, 20))

    def test_discussive_and_error_queries_return_none(self):
        queries = [
            "бот сказал что сейчас период кончающийся в марте 2026",
            "сейчас октябрь 2026",
            "в боте ошибка даты",
            "почему период марс",
            "почему даша меркурий?",
            "in march 2026 ended dasha",
            "bot says period ends in october 2026",
        ]
        for q in queries:
            self.assertIsNone(
                parse_one_line_profile(q),
                f"Expected None for discussive query: {q}"
            )


if __name__ == "__main__":
    unittest.main()

