"""
Комплексные тесты интернационализации и многоязычной поддержки (i18n).
Проверяют:
1. Нормализацию кодов языков (normalize_language)
2. Иерархию разрешения языка пользователя (get_user_lang: БД > Telegram language_code > Фолбэк 'ru')
3. Сохранение и сброс выбора языка в БД (db_manager: get_user_language / set_user_language)
4. Астрологические словари (планеты, знаки, достоинства на ru, en, it)
5. Функцию форматирования переводов (t(key, lang, **kwargs))
6. Генераторы клавиатур (Reply и Inline) на трёх языках
7. Маппинг и регулярные выражения кнопок меню (MENU_BUTTON_ACTIONS, MENU_REGEX_PATTERN, CANCEL_REGEX_PATTERN)
8. Парсер профилей одной строкой на RU, EN, IT (input_parser)
9. Астрологические форматирования и сводки на RU, EN, IT (jyotish_engine)
10. Графический рендерер карты Кундли на RU, EN, IT (chart_renderer)
11. Системные промпты и шаблоны Google Gemini на RU, EN, IT (gemini_interpreter)
12. Тексты инвойсов Telegram Stars на RU, EN, IT (payment_helper)
"""

import os
import re
import tempfile
import unittest
from datetime import date, time, datetime
from unittest.mock import MagicMock, AsyncMock, patch

import db_manager
from db_manager import init_db, get_user_language, set_user_language

import i18n
from i18n import (
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    normalize_language,
    get_user_lang,
    t,
    get_planet_name,
    get_sign_name,
    get_dignity_name,
    get_main_reply_keyboard,
    get_cancel_reply_keyboard,
    get_language_inline_keyboard,
    get_start_inline_keyboard,
    get_chart_inline_keyboard,
    get_karma_inline_keyboard,
    get_money_inline_keyboard,
    get_upaya_inline_keyboard,
    get_dasha_inline_keyboard,
    get_sadesati_inline_keyboard,
    get_yoga_inline_keyboard,
    get_ask_inline_keyboard,
    get_compat_inline_keyboard,
    get_prices_inline_keyboard,
    get_profile_management_keyboard,
    get_mydata_inline_keyboard,
    get_reset_inline_keyboard,
    get_profile_switched_keyboard,
    is_cancel_input,
    get_yoga_description,
    YOGA_DESCRIPTIONS,
    TRANSLATIONS,
    MENU_BUTTON_ACTIONS,
    MENU_REGEX_PATTERN,
    CANCEL_REGEX_PATTERN,
)
from input_parser import parse_one_line_profile
from jyotish_engine import (
    compute_chart,
    format_chart_summary,
    format_dasha_periods,
    calculate_chara_karakas,
    format_chara_karakas,
    analyze_wealth_and_career,
    format_wealth_analysis,
    get_upayas,
    format_upayas,
)
from chart_renderer import render_kundli_chart
from gemini_interpreter import GeminiInterpreter, JYOTISH_SYSTEM_PROMPTS
from payment_helper import INVOICE_TEXTS


class TestI18nCore(unittest.TestCase):
    """Тесты ядра нормализации и перевода."""

    def test_supported_languages_list(self):
        self.assertEqual(SUPPORTED_LANGUAGES, ["ru", "en", "it"])
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        self.assertIn("ru", LANGUAGE_LABELS)
        self.assertIn("en", LANGUAGE_LABELS)
        self.assertIn("it", LANGUAGE_LABELS)

    def test_normalize_language(self):
        # Russian and Slavic variants
        self.assertEqual(normalize_language("ru"), "ru")
        self.assertEqual(normalize_language("RU"), "ru")
        self.assertEqual(normalize_language("ru-RU"), "ru")
        self.assertEqual(normalize_language("ru_RU"), "ru")
        self.assertEqual(normalize_language("uk"), "ru")
        self.assertEqual(normalize_language("be"), "ru")
        self.assertEqual(normalize_language("kk"), "ru")

        # English variants
        self.assertEqual(normalize_language("en"), "en")
        self.assertEqual(normalize_language("EN"), "en")
        self.assertEqual(normalize_language("en-US"), "en")
        self.assertEqual(normalize_language("en_GB"), "en")
        self.assertEqual(normalize_language("en-AU"), "en")

        # Italian variants
        self.assertEqual(normalize_language("it"), "it")
        self.assertEqual(normalize_language("IT"), "it")
        self.assertEqual(normalize_language("it-IT"), "it")
        self.assertEqual(normalize_language("it_CH"), "it")

        # Non-supported or empty fallbacks to DEFAULT_LANGUAGE ('en')
        self.assertEqual(normalize_language(""), "en")
        self.assertEqual(normalize_language(None), "en")
        self.assertEqual(normalize_language(123), "en")
        self.assertEqual(normalize_language("de"), "en")
        self.assertEqual(normalize_language("fr"), "en")
        self.assertEqual(normalize_language("es"), "en")
        self.assertEqual(normalize_language("zh"), "en")
        self.assertEqual(normalize_language("ar"), "en")
        self.assertEqual(normalize_language("unknown"), "en")

    def test_t_function_translations_and_placeholders(self):
        # Test key existence across all 3 languages
        for lang in ["ru", "en", "it"]:
            # Simple string
            greeting = t("start_greeting", lang=lang)
            self.assertTrue(len(greeting) > 50)

            # String with placeholders
            switched_auto = t("lang_auto_switched", lang, selected_lang=LANGUAGE_LABELS[lang])
            self.assertIn(LANGUAGE_LABELS[lang], switched_auto)

        # Italian specific keyword
        it_greeting = t("start_greeting", lang="it")
        self.assertIn("Astrologo Vedico", it_greeting)

        # English specific keyword
        en_greeting = t("start_greeting", lang="en")
        self.assertIn("AI Vedic Astrologer", en_greeting)

        # Russian specific keyword
        ru_greeting = t("start_greeting", lang="ru")
        self.assertIn("ИИ-Джьотиш Астролог", ru_greeting)

        # Missing key fallback
        missing = t("totally_non_existent_key_123", lang="it")
        self.assertEqual(missing, "totally_non_existent_key_123")


class TestI18nLanguageResolution(unittest.TestCase):
    """Тесты разрешения языка пользователя (get_user_lang)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_i18n.db")
        init_db(self.db_path)
        self.user_id = 12345678

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_db_setting_persistence_and_reset(self):
        # 1. No setting initially
        self.assertIsNone(get_user_language(self.user_id, db_path=self.db_path))

        # 2. Set to Italian
        self.assertTrue(set_user_language(self.user_id, "it", db_path=self.db_path))
        self.assertEqual(get_user_language(self.user_id, db_path=self.db_path), "it")

        # 3. Change to English
        self.assertTrue(set_user_language(self.user_id, "en", db_path=self.db_path))
        self.assertEqual(get_user_language(self.user_id, db_path=self.db_path), "en")

        # 4. Reset to auto (None)
        self.assertTrue(set_user_language(self.user_id, None, db_path=self.db_path))
        self.assertIsNone(get_user_language(self.user_id, db_path=self.db_path))

    def test_resolution_hierarchy_priority(self):
        # Case A: Neither DB nor Telegram client -> Fallback 'en'
        res = get_user_lang(user_id=self.user_id, db_path=self.db_path)
        self.assertEqual(res, "en")

        # Case B: Telegram client says 'it', no DB setting -> Resolves to 'it'
        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.language_code = "it-IT"
        context_mock = MagicMock()
        context_mock.user_data = {}

        res = get_user_lang(update=update_mock, context=context_mock, user_id=self.user_id, db_path=self.db_path)
        self.assertEqual(res, "it")
        self.assertEqual(context_mock.user_data.get("user_lang"), "it")

        # Case C: Telegram client says 'it', but DB setting is manually set to 'en' -> DB overrides client!
        set_user_language(self.user_id, "en", db_path=self.db_path)
        context_mock.user_data.clear()

        res = get_user_lang(update=update_mock, context=context_mock, user_id=self.user_id, db_path=self.db_path)
        self.assertEqual(res, "en")
        self.assertEqual(context_mock.user_data.get("user_lang"), "en")

        # Case D: Reset DB to None -> Auto-detect resumes and resolves to client language 'it'
        set_user_language(self.user_id, None, db_path=self.db_path)
        context_mock.user_data.clear()

        res = get_user_lang(update=update_mock, context=context_mock, user_id=self.user_id, db_path=self.db_path)
        self.assertEqual(res, "it")


class TestAstrologicalTerminology(unittest.TestCase):
    """Тесты терминологических словарей (планеты, знаки зодиака, достоинства)."""

    def test_planet_names(self):
        self.assertIn("Солнце", get_planet_name("Sun", "ru"))
        self.assertIn("Sun", get_planet_name("Sun", "en"))
        self.assertIn("Sole", get_planet_name("Sun", "it"))

        self.assertIn("Луна", get_planet_name("Moon", "ru"))
        self.assertIn("Moon", get_planet_name("Moon", "en"))
        self.assertIn("Luna", get_planet_name("Moon", "it"))

        self.assertIn("Юпитер", get_planet_name("Jupiter", "ru"))
        self.assertIn("Jupiter", get_planet_name("Jupiter", "en"))
        self.assertIn("Giove", get_planet_name("Jupiter", "it"))

        # Unknown planet returns original key
        self.assertEqual(get_planet_name("UnknownPlanet", "it"), "UnknownPlanet")

    def test_sign_names_full_and_short(self):
        # Full sign names
        self.assertIn("Овен", get_sign_name("Aries", "ru"))
        self.assertIn("Aries", get_sign_name("Aries", "en"))
        self.assertIn("Ariete", get_sign_name("Aries", "it"))

        self.assertIn("Рыбы", get_sign_name("Pisces", "ru"))
        self.assertIn("Pisces", get_sign_name("Pisces", "en"))
        self.assertIn("Pesci", get_sign_name("Pisces", "it"))

        # Short sign names
        self.assertEqual(get_sign_name("Taurus", "ru", short=True), "Телец")
        self.assertEqual(get_sign_name("Taurus", "en", short=True), "Taurus")
        self.assertEqual(get_sign_name("Taurus", "it", short=True), "Toro")

    def test_dignity_names(self):
        self.assertIn("Экзальтация", get_dignity_name("Exalted", "ru"))
        self.assertIn("Exalted", get_dignity_name("Exalted", "en"))
        self.assertIn("Esaltazione", get_dignity_name("Exalted", "it"))

        self.assertIn("Падение", get_dignity_name("Debilitated", "ru"))
        self.assertIn("Debilitated", get_dignity_name("Debilitated", "en"))
        self.assertIn("Caduta", get_dignity_name("Debilitated", "it"))


class TestKeyboardsAndMenuActions(unittest.TestCase):
    """Тесты клавиатур и маршрутизации кнопок меню."""

    def test_main_reply_keyboards_structure(self):
        for lang in ["ru", "en", "it"]:
            kb = get_main_reply_keyboard(lang)
            buttons = [b.text for row in kb.keyboard for b in row]
            self.assertEqual(len(buttons), 12)

        # Check Russian buttons
        ru_buttons = [b.text for row in get_main_reply_keyboard("ru").keyboard for b in row]
        self.assertIn("🔮 Натальная карта", ru_buttons)
        self.assertIn("💰 Деньги и карьера", ru_buttons)
        self.assertIn("⏳ Периоды Даша", ru_buttons)

        # Check English buttons
        en_buttons = [b.text for row in get_main_reply_keyboard("en").keyboard for b in row]
        self.assertIn("🔮 Natal Chart", en_buttons)
        self.assertIn("💰 Money & Career", en_buttons)
        self.assertIn("⏳ Dasha Periods", en_buttons)

        # Check Italian buttons
        it_buttons = [b.text for row in get_main_reply_keyboard("it").keyboard for b in row]
        self.assertIn("🔮 Carta Natale", it_buttons)
        self.assertIn("💰 Denaro e Carriera", it_buttons)
        self.assertIn("⏳ Periodi Dasha", it_buttons)

    def test_cancel_reply_keyboards(self):
        self.assertEqual(get_cancel_reply_keyboard("ru").keyboard[0][0].text, "❌ Отмена")
        self.assertEqual(get_cancel_reply_keyboard("en").keyboard[0][0].text, "❌ Cancel")
        self.assertEqual(get_cancel_reply_keyboard("it").keyboard[0][0].text, "❌ Annulla")

    def test_language_inline_keyboard(self):
        kb_ru = get_language_inline_keyboard("ru")
        kb_en = get_language_inline_keyboard("en")
        kb_it = get_language_inline_keyboard("it")

        # Verify active checkmark
        ru_texts = [b.text for row in kb_ru.inline_keyboard for b in row]
        en_texts = [b.text for row in kb_en.inline_keyboard for b in row]
        it_texts = [b.text for row in kb_it.inline_keyboard for b in row]

        self.assertTrue(any("Русский ✅" in t for t in ru_texts))
        self.assertTrue(any("English ✅" in t for t in en_texts))
        self.assertTrue(any("Italiano ✅" in t for t in it_texts))

        # Check callback_data
        cb_datas = [b.callback_data for row in kb_ru.inline_keyboard for b in row]
        self.assertEqual(cb_datas, ["set_lang_ru", "set_lang_en", "set_lang_it", "set_lang_auto"])

    def test_menu_button_actions_mapping(self):
        # Ensure all RU, EN, IT main buttons map to valid actions
        for lang in ["ru", "en", "it"]:
            kb = get_main_reply_keyboard(lang)
            for row in kb.keyboard:
                for btn in row:
                    btn_text = btn.text if hasattr(btn, "text") else btn
                    action = MENU_BUTTON_ACTIONS.get(btn_text)
                    self.assertIsNotNone(action, f"Button '{btn_text}' not in MENU_BUTTON_ACTIONS")
                    self.assertIn(action, [
                        "chart", "dasha", "money", "karma", "sadesati", "yoga",
                        "upaya", "compat", "ask", "profile", "prices", "help", "lang"
                    ])

    def test_menu_regex_pattern_matches_all_languages(self):
        # Russian
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "🔮 Натальная карта"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "⏳ Периоды Даша"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "💰 Деньги и карьера"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "🛡 Упайи (Гармонизация)"))

        # English
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "🔮 Natal Chart"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "⏳ Dasha Periods"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "💰 Money & Career"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "🛡 Upayas (Remedies)"))

        # Italian
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "🔮 Carta Natale"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "⏳ Periodi Dasha"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "💰 Denaro e Carriera"))
        self.assertTrue(re.match(MENU_REGEX_PATTERN, "🛡 Upaya (Rimedi)"))

        # Non-menu text should not match
        self.assertIsNone(re.match(MENU_REGEX_PATTERN, "Hello World"))
        self.assertIsNone(re.match(MENU_REGEX_PATTERN, "15.05.1990 10:30 Москва"))

    def test_cancel_regex_pattern(self):
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "❌ Отмена"))
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "Отмена"))
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "❌ Cancel"))
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "Cancel"))
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "❌ Annulla"))
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "Annulla"))
        self.assertTrue(re.match(CANCEL_REGEX_PATTERN, "/cancel"))


class TestInputParserMultilingual(unittest.TestCase):
    """Тесты распознавания данных рождения одной строкой на разных языках."""

    def test_russian_input_parsing(self):
        parsed = parse_one_line_profile("Александр, 15.05.1990, 10:30, Москва")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["is_complete"])
        self.assertEqual(parsed["name"], "Александр")
        self.assertEqual(parsed["dob"], date(1990, 5, 15))
        self.assertEqual(parsed["tob"], time(10, 30))
        self.assertEqual(parsed["city"], "Москва")

    def test_english_input_parsing(self):
        parsed = parse_one_line_profile("John, 15.05.1990 at 10:30, London")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["is_complete"])
        self.assertEqual(parsed["name"], "John")
        self.assertEqual(parsed["dob"], date(1990, 5, 15))
        self.assertEqual(parsed["tob"], time(10, 30))
        self.assertEqual(parsed["city"], "London")

    def test_italian_input_parsing(self):
        parsed = parse_one_line_profile("Marco, 15.05.1990 alle ore 10:30, Roma")
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["is_complete"])
        self.assertEqual(parsed["name"], "Marco")
        self.assertEqual(parsed["dob"], date(1990, 5, 15))
        self.assertEqual(parsed["tob"], time(10, 30))
        self.assertEqual(parsed["city"], "Roma")


class TestEngineAndRenderingMultilingual(unittest.TestCase):
    """Тесты вывода астрологического ядра и графического рендерера на RU, EN, IT."""

    @classmethod
    def setUpClass(cls):
        cls.birth_dt = datetime(1990, 5, 15, 10, 30)
        cls.chart = compute_chart(
            birth_dt=cls.birth_dt,
            lat=41.9028,
            lon=12.4964,
            tz_offset=2.0,
            name="Test Marco"
        )

    def test_format_chart_summary_languages(self):
        summary_ru = format_chart_summary(self.chart, lang="ru")
        summary_en = format_chart_summary(self.chart, lang="en")
        summary_it = format_chart_summary(self.chart, lang="it")

        # RU keywords
        self.assertIn("Лагна (Асцендент):", summary_ru)
        self.assertIn("Позиции планет:", summary_ru)

        # EN keywords
        self.assertIn("Lagna (Ascendant):", summary_en)
        self.assertIn("Planetary Positions:", summary_en)

        # IT keywords
        self.assertIn("Lagna (Ascendente):", summary_it)
        self.assertIn("Posizioni Planetarie:", summary_it)

    def test_format_dasha_periods_languages(self):
        dasha_ru = format_dasha_periods(self.chart, lang="ru")
        dasha_en = format_dasha_periods(self.chart, lang="en")
        dasha_it = format_dasha_periods(self.chart, lang="it")

        self.assertIn("Вимшоттари Даша", dasha_ru)
        self.assertIn("Vimshottari Dasha", dasha_en)
        self.assertIn("Vimshottari Dasha", dasha_it)

    def test_format_chara_karakas_languages(self):
        karakas = calculate_chara_karakas(self.chart)
        text_ru = format_chara_karakas(karakas, lang="ru")
        text_en = format_chara_karakas(karakas, lang="en")
        text_it = format_chara_karakas(karakas, lang="it")

        self.assertIn("Атмакарака", text_ru)
        self.assertIn("Atmakaraka", text_en)
        self.assertIn("Atmakaraka", text_it)

    def test_format_wealth_analysis_languages(self):
        wealth = analyze_wealth_and_career(self.chart)
        text_ru = format_wealth_analysis(wealth, lang="ru")
        text_en = format_wealth_analysis(wealth, lang="en")
        text_it = format_wealth_analysis(wealth, lang="it")

        self.assertIn("2-й дом", text_ru)
        self.assertIn("2nd House", text_en)
        self.assertIn("2ª Casa", text_it)

    def test_format_upayas_languages(self):
        upayas = get_upayas(self.chart)
        text_ru = format_upayas(upayas, lang="ru")
        text_en = format_upayas(upayas, lang="en")
        text_it = format_upayas(upayas, lang="it")

        self.assertIn("Ведические Упайи", text_ru)
        self.assertIn("Vedic Upayas", text_en)
        self.assertIn("Upaya Vedici", text_it)

    def test_render_kundli_chart_languages(self):
        # Test rendering PNG image for each language
        img_ru = render_kundli_chart(self.chart, profile_name="Александр", lang="ru")
        img_en = render_kundli_chart(self.chart, profile_name="Alexander", lang="en")
        img_it = render_kundli_chart(self.chart, profile_name="Alessandro", lang="it")

        buf_ru = img_ru.getvalue()
        buf_en = img_en.getvalue()
        buf_it = img_it.getvalue()

        self.assertTrue(len(buf_ru) > 1000)
        self.assertTrue(len(buf_en) > 1000)
        self.assertTrue(len(buf_it) > 1000)
        self.assertTrue(buf_ru.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(buf_en.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(buf_it.startswith(b"\x89PNG\r\n\x1a\n"))


class TestInterpreterAndPaymentsMultilingual(unittest.TestCase):
    """Тесты локализации системных промптов Gemini и инвойсов Telegram Stars."""

    def test_gemini_system_prompts(self):
        self.assertIn("ru", JYOTISH_SYSTEM_PROMPTS)
        self.assertIn("en", JYOTISH_SYSTEM_PROMPTS)
        self.assertIn("it", JYOTISH_SYSTEM_PROMPTS)

        interpreter = GeminiInterpreter(api_key="TEST_API_KEY_MOCK")
        inst_ru = interpreter.get_system_instruction(lang="ru")
        inst_en = interpreter.get_system_instruction(lang="en")
        inst_it = interpreter.get_system_instruction(lang="it")

        self.assertIn("ведический астролог", inst_ru)
        self.assertIn("Vedic astrologer", inst_en)
        self.assertIn("astrologo vedico", inst_it)

    def test_invoice_texts_multilingual(self):
        # Verify invoice keys and descriptions across RU, EN, IT
        for lang in ["ru", "en", "it"]:
            invoices = INVOICE_TEXTS[lang]
            self.assertIn("chart_title", invoices)
            self.assertIn("chart_desc", invoices)
            self.assertIn("dasha_title", invoices)
            self.assertIn("dasha_desc", invoices)
            self.assertIn("karma_title", invoices)
            self.assertIn("money_title", invoices)
            self.assertIn("bundle_title", invoices)


class TestMultilingualCancellation(unittest.TestCase):
    """Тесты многоязычного распознавания отмены во всех диалогах."""

    def test_cancel_recognition_ru(self):
        self.assertTrue(is_cancel_input("Отмена"))
        self.assertTrue(is_cancel_input("отмена"))
        self.assertTrue(is_cancel_input("  ❌ Отмена  "))
        self.assertTrue(is_cancel_input("/cancel"))

    def test_cancel_recognition_en(self):
        self.assertTrue(is_cancel_input("Cancel"))
        self.assertTrue(is_cancel_input("cancel"))
        self.assertTrue(is_cancel_input("  ❌ Cancel  "))
        self.assertTrue(is_cancel_input("abort"))

    def test_cancel_recognition_it(self):
        self.assertTrue(is_cancel_input("Annulla"))
        self.assertTrue(is_cancel_input("annulla"))
        self.assertTrue(is_cancel_input("❌ Annulla"))
        self.assertTrue(is_cancel_input("annullare"))

    def test_cancel_negative_inputs(self):
        self.assertFalse(is_cancel_input("Александр"))
        self.assertFalse(is_cancel_input("Roma"))
        self.assertFalse(is_cancel_input("15.05.1990"))
        self.assertFalse(is_cancel_input("10:30"))
        self.assertFalse(is_cancel_input(""))
        self.assertFalse(is_cancel_input(None))
        self.assertFalse(is_cancel_input(12345))


class TestMultilingualYogaDescriptions(unittest.TestCase):
    """Тесты локализации йог (комбинаций планет)."""

    def test_all_yogas_have_three_languages(self):
        ru_yogas = set(YOGA_DESCRIPTIONS["ru"].keys())
        en_yogas = set(YOGA_DESCRIPTIONS["en"].keys())
        it_yogas = set(YOGA_DESCRIPTIONS["it"].keys())
        self.assertEqual(ru_yogas, en_yogas)
        self.assertEqual(ru_yogas, it_yogas)
        for lang in ["ru", "en", "it"]:
            for yoga_name, desc in YOGA_DESCRIPTIONS[lang].items():
                self.assertTrue(len(desc) > 10, f"Description for {yoga_name} in {lang} too short")

    def test_get_yoga_description_lookup(self):
        desc_ru = get_yoga_description("Gajakesari Yoga", "ru")
        desc_en = get_yoga_description("Gajakesari Yoga", "en")
        desc_it = get_yoga_description("Gajakesari Yoga", "it")

        self.assertIn("Юпитер", desc_ru)
        self.assertIn("Jupiter", desc_en)
        self.assertIn("Giove", desc_it)

    def test_get_yoga_description_fallback(self):
        fallback_val = get_yoga_description("Nonexistent Yoga", "it", default="Custom Yoga Description")
        self.assertEqual(fallback_val, "Custom Yoga Description")


class TestMultilingualKeyboards(unittest.TestCase):
    """Тесты клавиатур профилей, управления данными и сброса на RU, EN, IT."""

    def test_profile_management_keyboard(self):
        for lang in ["ru", "en", "it"]:
            kb = get_profile_management_keyboard(lang)
            self.assertTrue(len(kb.inline_keyboard) >= 2)
            for row in kb.inline_keyboard:
                for btn in row:
                    self.assertTrue(len(btn.text) > 0)
                    self.assertTrue(len(btn.callback_data) > 0)

    def test_mydata_and_reset_keyboards(self):
        for lang in ["ru", "en", "it"]:
            mydata_kb = get_mydata_inline_keyboard(lang)
            reset_kb = get_reset_inline_keyboard(lang)
            switch_kb = get_profile_switched_keyboard(lang)
            self.assertTrue(len(mydata_kb.inline_keyboard) >= 1)
            self.assertTrue(len(reset_kb.inline_keyboard) >= 1)
            self.assertTrue(len(switch_kb.inline_keyboard) >= 1)


class TestTranslationsParity(unittest.TestCase):
    """Тест полноты словаря переводов и совпадения параметров подстановки."""

    def test_all_keys_have_three_languages(self):
        ru_keys = set(TRANSLATIONS["ru"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())
        it_keys = set(TRANSLATIONS["it"].keys())
        self.assertEqual(ru_keys, en_keys)
        self.assertEqual(ru_keys, it_keys)

    def test_placeholders_match(self):
        placeholder_regex = re.compile(r"\{([a-zA-Z0-9_]+)\}")
        for key in TRANSLATIONS["ru"]:
            ru_params = set(placeholder_regex.findall(TRANSLATIONS["ru"][key]))
            en_params = set(placeholder_regex.findall(TRANSLATIONS["en"][key]))
            it_params = set(placeholder_regex.findall(TRANSLATIONS["it"][key]))

            self.assertEqual(
                ru_params, en_params,
                f"Placeholder mismatch for '{key}' between ru and en: {ru_params} != {en_params}"
            )
            self.assertEqual(
                ru_params, it_params,
                f"Placeholder mismatch for '{key}' between ru and it: {ru_params} != {it_params}"
            )


class TestBotMultilingualWorkflows(unittest.TestCase):
    """Тесты команд бота на разных языках и многоязычной отмены."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_bot_i18n.db")
        db_manager.DB_PATH = self.db_path
        init_db(self.db_path)

    def tearDown(self):
        db_manager.DB_PATH = db_manager.DEFAULT_DB_PATH
        self.temp_dir.cleanup()

    def test_lang_command_with_args(self):
        import asyncio
        import bot

        user_id = 998877

        # 1. /lang en
        update_mock = MagicMock()
        update_mock.effective_user.id = user_id
        update_mock.effective_user.language_code = "ru"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.args = ["en"]
        context_mock.user_data = {}

        asyncio.run(bot.lang_command(update_mock, context_mock))
        self.assertEqual(get_user_language(user_id, self.db_path), "en")
        reply = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Interface language successfully set to *English*", reply)

        # 2. /lang it
        update_mock.effective_message.reply_text.reset_mock()
        context_mock.args = ["it"]
        asyncio.run(bot.lang_command(update_mock, context_mock))
        self.assertEqual(get_user_language(user_id, self.db_path), "it")
        reply = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Lingua dell'interfaccia impostata su *Italiano*", reply)

        # 3. /lang auto
        update_mock.effective_message.reply_text.reset_mock()
        context_mock.args = ["auto"]
        asyncio.run(bot.lang_command(update_mock, context_mock))
        self.assertIsNone(get_user_language(user_id, self.db_path))
        reply = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertTrue("Авто" in reply or "Auto" in reply)

    def test_cancellation_in_conversation_en_and_it(self):
        import asyncio
        import bot

        user_id = 112233
        set_user_language(user_id, "en", self.db_path)

        # User sends "Cancel" in English during WAITING_DOB
        update_mock = MagicMock()
        update_mock.effective_user.id = user_id
        update_mock.effective_message.reply_text = AsyncMock()
        update_mock.message.text = "Cancel"
        update_mock.message.reply_text = update_mock.effective_message.reply_text
        context_mock = MagicMock()
        context_mock.user_data = {"temp_profile_name": "John"}

        state = asyncio.run(bot.chart_dob_received(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)
        self.assertNotIn("temp_profile_name", context_mock.user_data)
        cancel_reply = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Input cancelled", cancel_reply)

        # User sends "Annulla" in Italian during WAITING_PROFILE_NAME
        set_user_language(user_id, "it", self.db_path)
        update_mock.effective_message.reply_text.reset_mock()
        update_mock.message.text = "Annulla"
        context_mock.user_data = {"temp_profile_name": "Giovanni"}

        state = asyncio.run(bot.profile_name_received(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)
        self.assertNotIn("temp_profile_name", context_mock.user_data)
        cancel_reply_it = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Operazione annullata", cancel_reply_it)


if __name__ == "__main__":
    unittest.main()
