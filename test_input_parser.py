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

    def test_invalid_strings(self):
        self.assertIsNone(parse_one_line_profile(""))
        self.assertIsNone(parse_one_line_profile("Привет, как дела?"))
        self.assertIsNone(parse_one_line_profile("32.13.1990 10:00 Москва"))


if __name__ == "__main__":
    unittest.main()
