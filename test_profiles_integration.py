"""
Интеграционные тесты для системы профилей астрологического бота.
Проверяют совместную работу db_manager, bot.get_user_natal_profile и логики хэндлеров.
"""

import os
import unittest
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

import db_manager
from db_manager import (
    init_db,
    save_profile,
    get_active_profile,
    get_user_profiles,
    get_profile_by_id,
    set_active_profile,
    delete_profile,
    clear_user_profiles,
    count_user_profiles,
)
import bot
from bot import get_user_natal_profile


class TestProfilesIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_jyotish.db")
        db_manager.DB_PATH = self.db_path
        init_db(self.db_path)
        self.user_id = 99887766
        self.gemini_patcher = unittest.mock.patch("bot.get_gemini_client", return_value=None)
        self.gemini_patcher.start()

    def tearDown(self):
        self.gemini_patcher.stop()
        self.temp_dir.cleanup()

    def test_get_user_natal_profile_from_db_and_cache(self):
        # 1. Сначала у пользователя нет профиля
        context_mock = MagicMock()
        context_mock.user_data = {}

        p = get_user_natal_profile(self.user_id, context_mock)
        self.assertIsNone(p)

        # 2. Сохраняем профиль в БД
        chart_data = {"test": 123, "planets": []}
        dt = datetime(1995, 7, 20, 18, 45)
        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=dt,
            place_name="Рим",
            resolved_address="Рим, Италия",
            lat=41.9,
            lon=12.5,
            tz_offset=2.0,
            chart_data=chart_data,
            summary="Карта 1",
            set_as_active=True,
            db_path=self.db_path,
        )

        # 3. get_user_natal_profile должен загрузить профиль из БД и положить в user_data
        loaded = get_user_natal_profile(self.user_id, context_mock)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], prof_id)
        self.assertEqual(loaded["profile_name"], "Мой гороскоп")
        self.assertEqual(loaded["birth_dt"], dt)
        self.assertEqual(context_mock.user_data["natal_profile"], loaded)

        # 4. Проверяем чтение из кэша
        context_mock.user_data["natal_profile"]["profile_name"] = "Кэшированный профиль"
        cached = get_user_natal_profile(self.user_id, context_mock)
        self.assertEqual(cached["profile_name"], "Кэшированный профиль")

    def test_multiple_profiles_creation_and_switching(self):
        context_mock = MagicMock()
        context_mock.user_data = {}

        # Создаём первый профиль: "Мой гороскоп"
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 1, 1, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={"asc": "Aries"},
            summary="Сводка 1",
            set_as_active=True,
            db_path=self.db_path,
        )

        # Создаём второй профиль: "Жена"
        id2 = save_profile(
            user_id=self.user_id,
            profile_name="Жена",
            birth_dt=datetime(1992, 5, 10, 15, 30),
            place_name="Санкт-Петербург",
            resolved_address="СПб",
            lat=59.93,
            lon=30.33,
            tz_offset=3.0,
            chart_data={"asc": "Taurus"},
            summary="Сводка 2",
            set_as_active=True,
            db_path=self.db_path,
        )

        # Создаём третий профиль: "Сын"
        id3 = save_profile(
            user_id=self.user_id,
            profile_name="Сын",
            birth_dt=datetime(2020, 11, 25, 8, 15),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={"asc": "Gemini"},
            summary="Сводка 3",
            set_as_active=True,
            db_path=self.db_path,
        )

        # Всего 3 профиля
        profiles = get_user_profiles(self.user_id, db_path=self.db_path)
        self.assertEqual(len(profiles), 3)

        # Активный сейчас - id3 ("Сын")
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], id3)
        self.assertEqual(active["profile_name"], "Сын")

        # Переключаем активный на "Жена" (id2)
        set_active_profile(id2, self.user_id, db_path=self.db_path)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], id2)
        self.assertEqual(active["profile_name"], "Жена")

        # Переключаем обратно на "Мой гороскоп" (id1)
        set_active_profile(id1, self.user_id, db_path=self.db_path)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], id1)
        self.assertEqual(active["profile_name"], "Мой гороскоп")

    def test_delete_profile_and_automatic_active_selection(self):
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Основной",
            birth_dt=datetime(1990, 1, 1, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={},
            summary="1",
            set_as_active=False,
            db_path=self.db_path,
        )
        id2 = save_profile(
            user_id=self.user_id,
            profile_name="Второй",
            birth_dt=datetime(1995, 2, 2, 12, 0),
            place_name="Казань",
            resolved_address="Казань",
            lat=55.8,
            lon=49.1,
            tz_offset=3.0,
            chart_data={},
            summary="2",
            set_as_active=True,
            db_path=self.db_path,
        )

        # id2 активен
        self.assertEqual(get_active_profile(self.user_id, db_path=self.db_path)["id"], id2)

        # Удаляем id2
        self.assertTrue(delete_profile(id2, self.user_id, db_path=self.db_path))

        # id1 должен автоматически стать активным
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], id1)
        self.assertEqual(active["profile_name"], "Основной")

    async def _run_start_command_with_profile(self, has_profile: bool):
        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.language_code = "ru"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        if has_profile:
            save_profile(
                user_id=self.user_id,
                profile_name="Мой гороскоп",
                birth_dt=datetime(1990, 5, 15, 10, 30),
                place_name="Москва",
                resolved_address="Москва",
                lat=55.75,
                lon=37.61,
                tz_offset=3.0,
                chart_data={},
                summary="",
                set_as_active=True,
                db_path=self.db_path,
            )

        await bot.start_command(update_mock, context_mock)
        return update_mock.effective_message.reply_text.call_args[0][0]

    def test_start_command_renders_active_profile(self):
        import asyncio
        # С профилем
        text_with_prof = asyncio.run(self._run_start_command_with_profile(True))
        self.assertIn("Твой активный профиль", text_with_prof)
        self.assertIn("Мой гороскоп", text_with_prof)

        # Без профиля
        clear_user_profiles(self.user_id, db_path=self.db_path)
        text_without_prof = asyncio.run(self._run_start_command_with_profile(False))
        self.assertNotIn("Твой активный профиль", text_without_prof)
        self.assertIn("нажми /chart, чтобы начать", text_without_prof)

    def test_newprofile_start_resets_editing_id(self):
        import asyncio
        update_mock = MagicMock()
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {"editing_profile_id": 123}

        state = asyncio.run(bot.newprofile_start(update_mock, context_mock))
        self.assertEqual(state, bot.WAITING_PROFILE_NAME)
        self.assertIsNone(context_mock.user_data["editing_profile_id"])

    def test_cancel_command_cleans_temporary_data(self):
        import asyncio
        update_mock = MagicMock()
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {
            "temp_dob": datetime.now().date(),
            "temp_tob": datetime.now().time(),
            "temp_profile_name": "Жена",
            "editing_profile_id": 5,
            "compat_dob": datetime.now().date(),
            "compat_tob": datetime.now().time(),
            "permanent_key": "keep_this",
        }

        asyncio.run(bot.cancel_command(update_mock, context_mock))
        self.assertNotIn("temp_dob", context_mock.user_data)
        self.assertNotIn("temp_tob", context_mock.user_data)
        self.assertNotIn("temp_profile_name", context_mock.user_data)
        self.assertNotIn("editing_profile_id", context_mock.user_data)
        self.assertNotIn("compat_dob", context_mock.user_data)
        self.assertNotIn("compat_tob", context_mock.user_data)
        self.assertEqual(context_mock.user_data["permanent_key"], "keep_this")

    def test_profile_name_received_cancel_trigger(self):
        import asyncio
        update_mock = MagicMock()
        update_mock.message.text = "Отмена"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {"temp_profile_name": "test"}

        state = asyncio.run(bot.profile_name_received(update_mock, context_mock))
        # При вводе 'Отмена' должен сработать cancel_command и вернуть ConversationHandler.END (-1)
        self.assertEqual(state, bot.ConversationHandler.END)
        self.assertNotIn("temp_profile_name", context_mock.user_data)

    @unittest.mock.patch("bot.send_split_message", new_callable=AsyncMock)
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_one_line_profile_flow(self, mock_compute, mock_resolve, mock_summary, mock_split):
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {
            "planets": [{"name": "Moon", "sign": "Cancer"}],
            "houses": [],
            "dashas": {"periods": []}
        }

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "Александр, 20.06.1996, 08:25, Горно-Алтайск"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_one_line_direct(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        # Проверяем, что профиль сохранился в базе данных
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["profile_name"], "Александр")
        self.assertEqual(active["place_name"], "Горно-Алтайск")
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))

    def test_sadesati_command_execution(self):
        import asyncio
        # Сначала без профиля
        update_mock = MagicMock()
        update_mock.effective_user.id = 554433
        update_mock.effective_user.language_code = "ru"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        asyncio.run(bot.sadesati_command(update_mock, context_mock))
        first_call = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Сначала необходимо составить натальную карту", first_call)

        # Теперь сохраняем профиль
        chart_data = {
            "planets": [
                {"name": "Moon", "sign": "Cancer"},
                {"name": "Saturn", "sign": "Pisces"}
            ]
        }
        save_profile(
            user_id=554433,
            profile_name="Саде-Сати Профиль",
            birth_dt=datetime(1996, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data=chart_data,
            summary="",
            set_as_active=True,
            db_path=self.db_path
        )

        update_mock.effective_message.reply_text.reset_mock()
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text.return_value = status_msg

        asyncio.run(bot.sadesati_command(update_mock, context_mock))
        self.assertTrue(status_msg.delete.called)
        second_call = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Саде-Сати", second_call)

    def test_one_line_filter_behavior(self):
        msg_valid = MagicMock()
        msg_valid.text = "Александр, 20.06.1996, 08:25, Горно-Алтайск"
        self.assertTrue(bot.one_line_filter.filter(msg_valid))

        msg_cmd = MagicMock()
        msg_cmd.text = "/chart Александр, 20.06.1996, 08:25, Горно-Алтайск"
        self.assertFalse(bot.one_line_filter.filter(msg_cmd))

        msg_menu = MagicMock()
        msg_menu.text = "🪐 Саде-Сати"
        self.assertFalse(bot.one_line_filter.filter(msg_menu))

        msg_partial = MagicMock()
        msg_partial.text = "15.05.1990"
        self.assertFalse(bot.one_line_filter.filter(msg_partial))

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_one_line_in_waiting_tob_and_waiting_place(self, mock_compute, mock_resolve, mock_summary, mock_split):
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        # Тест 1: Пользователь находится в WAITING_TOB и отправляет полную строку
        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.message.text = "Александр, 20.06.1996, 08:25, Горно-Алтайск"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {"temp_dob": datetime(1996, 6, 20).date()}

        state = asyncio.run(bot.chart_tob_received(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["profile_name"], "Александр")

        # Тест 2: Пользователь находится в WAITING_PLACE и отправляет полную строку
        update_mock.message.text = "Мария, 15.05.1990, 10:30, Москва"
        context_mock.user_data = {
            "temp_dob": datetime(1990, 5, 15).date(),
            "temp_tob": datetime(1990, 5, 15, 10, 30).time()
        }
        state = asyncio.run(bot.chart_place_received(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        active2 = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active2["profile_name"], "Мария")

    def test_name_first_in_chart_dob_received(self):
        import asyncio
        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.language_code = "ru"
        update_mock.message.text = "Александр"
        update_mock.message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_dob_received(update_mock, context_mock))
        self.assertEqual(state, bot.WAITING_DOB)
        self.assertEqual(context_mock.user_data.get("temp_profile_name"), "Александр")
        self.assertTrue(update_mock.message.reply_text.called)
        reply_text = update_mock.message.reply_text.call_args[0][0]
        self.assertIn("Запомнил имя", reply_text)

    def test_rename_command_flow(self):
        import asyncio
        # Сохраняем тестовый профиль
        save_profile(
            user_id=self.user_id,
            profile_name="Старое имя",
            birth_dt=datetime(1996, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.message.text = "/rename Новое Имя"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        asyncio.run(bot.rename_command(update_mock, context_mock))
        self.assertTrue(update_mock.effective_message.reply_text.called)
        reply_text = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Новое Имя", reply_text)

        # Проверяем в БД
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["profile_name"], "Новое Имя")

    def test_admin_command_access(self):
        import asyncio
        # 1. Попытка не-админа
        update_stranger = MagicMock()
        update_stranger.effective_user.id = 999999999
        update_stranger.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        asyncio.run(bot.admin_command(update_stranger, context_mock))
        self.assertTrue(update_stranger.effective_message.reply_text.called)
        self.assertIn("только администратору", update_stranger.effective_message.reply_text.call_args[0][0])

        # 2. Попытка админа (Александр: 1275394562)
        update_admin = MagicMock()
        update_admin.effective_user.id = 1275394562
        update_admin.effective_message.reply_text = AsyncMock()
        asyncio.run(bot.admin_command(update_admin, context_mock))
        self.assertTrue(update_admin.effective_message.reply_text.called)
        reply_text = update_admin.effective_message.reply_text.call_args[0][0]
        self.assertIn("Панель администратора", reply_text)

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_one_line_input_updates_existing_profile_without_duplicate(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: если у пользователя уже есть профиль с ошибочной датой,
        повторный ввод правильных данных одной строкой ОБНОВЛЯЕТ существующий профиль,
        а не плодит 'Профиль 2'."""
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        # Создаем исходный профиль с ошибочной датой (1995 вместо 1996)
        wrong_dt = datetime(1995, 6, 20, 8, 30)
        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=wrong_dt,
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск, Россия",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={"planets": []},
            summary="Старая сводка",
            set_as_active=True,
            db_path=self.db_path,
        )
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)

        # Пользователь отправляет исправленные данные без указания имени
        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "20.06.1996 08:25 Горно-Алтайск"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_one_line_direct(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        # Количество профилей ДОЛЖНО остаться ровно 1 (никакого "Профиль 2"!)
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)

        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["profile_name"], "Мой гороскоп")
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))
        self.assertEqual(active["place_name"], "Горно-Алтайск")

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_one_line_input_with_name_updates_matching_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: ввод с явным именем, совпадающим с текущим, обновляет его без создания дубликата."""
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        wrong_dt = datetime(1996, 6, 19, 8, 25)
        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Александр",
            birth_dt=wrong_dt,
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск, Россия",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="Черновик",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "Александр, 20.06.1996, 08:25, Горно-Алтайск"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_one_line_direct(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_edit_command_with_args_updates_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: вызов /edit с аргументами обновляет активный профиль."""
        import asyncio
        mock_resolve.return_value = (55.75, 37.61, 3.0, "Москва, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 5, 15, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.message.text = "/edit 15.05.1990 10:30 Москва"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.edit_start(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["birth_dt"], datetime(1990, 5, 15, 10, 30))

    def test_edit_command_without_args_prompts_recalc(self):
        """Проверка: вызов /edit без аргументов переводит в WAITING_DOB с запоминанием editing_profile_id."""
        import asyncio
        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Тест",
            birth_dt=datetime(1990, 5, 15, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.message.text = "/edit"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.edit_start(update_mock, context_mock))
        self.assertEqual(state, bot.WAITING_DOB)
        self.assertEqual(context_mock.user_data.get("editing_profile_id"), prof_id)
        self.assertEqual(context_mock.user_data.get("temp_profile_name"), "Тест")

    def test_recalc_callback_start_sets_editing_id(self):
        """Проверка: нажатие кнопки 'Изменить данные' (prof_recalc_start) устанавливает editing_profile_id."""
        import asyncio
        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 5, 15, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.callback_query.data = "prof_recalc_start"
        update_mock.callback_query.from_user.id = self.user_id
        update_mock.callback_query.answer = AsyncMock()
        update_mock.callback_query.message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.recalc_callback_start(update_mock, context_mock))
        self.assertEqual(state, bot.WAITING_DOB)
        self.assertEqual(context_mock.user_data.get("editing_profile_id"), prof_id)
        self.assertEqual(context_mock.user_data.get("temp_profile_name"), "Мой гороскоп")

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_chart_command_with_args_updates_existing_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: /chart <данные> при наличии активного профиля обновляет его, а не создает новый."""
        import asyncio
        mock_resolve.return_value = (55.75, 37.61, 3.0, "Москва, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 1, 1, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "/chart 15.05.1990 10:30 Москва"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_start(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["birth_dt"], datetime(1990, 5, 15, 10, 30))

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_newprofile_command_creates_distinct_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: /newprofile по-прежнему создает отдельный профиль при явном запросе."""
        import asyncio
        mock_resolve.return_value = (55.75, 37.61, 3.0, "Москва, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 1, 1, 10, 0),
            place_name="Москва",
            resolved_address="Москва",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "/newprofile 15.05.1990 10:30 Москва"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.newprofile_start(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        # Здесь профилей должно стать 2, так как был явный /newprofile!
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 2)

    def test_keyboards_contain_edit_button(self):
        """Проверка наличия кнопки редактирования/пересчёта во всех профильных клавиатурах."""
        from i18n import get_chart_inline_keyboard, get_mydata_inline_keyboard, get_profile_management_keyboard

        chart_kb = get_chart_inline_keyboard("ru")
        chart_cbs = [btn.callback_data for row in chart_kb.inline_keyboard for btn in row]
        self.assertIn("prof_recalc_start", chart_cbs)

        mydata_kb = get_mydata_inline_keyboard("ru")
        mydata_cbs = [btn.callback_data for row in mydata_kb.inline_keyboard for btn in row]
        self.assertIn("prof_recalc_start", mydata_cbs)

        test_profiles = [{"id": 1, "profile_name": "Тест", "is_active": True}]
        prof_kb = get_profile_management_keyboard("ru", test_profiles)
        prof_cbs = [btn.callback_data for row in prof_kb.inline_keyboard for btn in row]
        self.assertIn("prof_recalc_start", prof_cbs)
        self.assertIn("prof_edit_1", prof_cbs)
        self.assertIn("prof_cleanup_duplicates", prof_cbs)

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_one_line_natural_language_correction_updates_active_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: ввод с фразой 'исправь дату 20.06.1996 08:25 Горно-Алтайск' обновляет профиль, а не создает профиль 'исправь дату'."""
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1995, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск, Россия",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="Старая карта",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "исправь дату: 20.06.1996 08:25 Горно-Алтайск"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_one_line_direct(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        # Профиль остался 1, не создался профиль "исправь дату"
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["profile_name"], "Мой гороскоп")
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_one_line_user_name_with_correction_updates_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: ввод 'Александр, исправь дату на 20.06.1996 08:25 Горно-Алтайск' корректно задает имя и обновляет профиль."""
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1995, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск, Россия",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="Старая карта",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "Александр, исправь дату на 20.06.1996 08:25 Горно-Алтайск"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.chart_one_line_direct(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["profile_name"], "Александр")
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_edit_command_with_only_date_updates_active_profile(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: /edit с одной лишь датой сохраняет время и город из активного профиля и пересчитывает карту."""
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1995, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск, Россия",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="Старая карта",
            set_as_active=True,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.first_name = "Александр"
        update_mock.message.text = "/edit 20.06.1996"
        status_msg = AsyncMock()
        update_mock.effective_message.reply_text = AsyncMock(return_value=status_msg)
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.edit_start(update_mock, context_mock))
        self.assertEqual(state, bot.ConversationHandler.END)

        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))
        self.assertEqual(active["place_name"], "Горно-Алтайск")

    def test_edit_command_with_profile_selector(self):
        """Проверка: /edit 2 или /edit Сюзанна выбирает целевой профиль для редактирования."""
        import asyncio
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Александр",
            birth_dt=datetime(1996, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )
        id2 = save_profile(
            user_id=self.user_id,
            profile_name="Сюзанна",
            birth_dt=datetime(1998, 8, 28, 11, 0),
            place_name="Рим",
            resolved_address="Рим",
            lat=41.9,
            lon=12.5,
            tz_offset=2.0,
            chart_data={},
            summary="",
            set_as_active=False,
            db_path=self.db_path,
        )

        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.message.text = "/edit Сюзанна"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        state = asyncio.run(bot.edit_start(update_mock, context_mock))
        self.assertEqual(state, bot.WAITING_DOB)
        self.assertEqual(context_mock.user_data.get("editing_profile_id"), id2)
        self.assertEqual(context_mock.user_data.get("temp_profile_name"), "Сюзанна")

    @unittest.mock.patch("bot.send_split_message")
    @unittest.mock.patch("bot.format_chart_summary", return_value="Сводка карты")
    @unittest.mock.patch("bot.resolve_location")
    @unittest.mock.patch("bot.compute_chart")
    def test_interactive_keep_in_tob_and_place(self, mock_compute, mock_resolve, mock_summary, mock_split):
        """Проверка: отправка /keep на шагах времени и города сохраняет значения из профиля."""
        import asyncio
        mock_resolve.return_value = (51.95, 85.96, 7.0, "Горно-Алтайск, Россия")
        mock_compute.return_value = {"planets": [], "houses": [], "dashas": {"periods": []}}

        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1995, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск, Россия",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="Старая карта",
            set_as_active=True,
            db_path=self.db_path,
        )

        context_mock = MagicMock()
        context_mock.user_data = {
            "editing_profile_id": prof_id,
            "temp_profile_name": "Мой гороскоп",
        }

        # 1. Шаг даты: отправляем новую дату
        update_dob = MagicMock()
        update_dob.effective_user.id = self.user_id
        update_dob.message.text = "20.06.1996"
        update_dob.message.reply_text = AsyncMock()
        state1 = asyncio.run(bot.chart_dob_received(update_dob, context_mock))
        self.assertEqual(state1, bot.WAITING_TOB)
        self.assertEqual(context_mock.user_data.get("temp_dob"), datetime(1996, 6, 20).date())

        # 2. Шаг времени: отправляем /keep (оставить 08:25)
        update_tob = MagicMock()
        update_tob.effective_user.id = self.user_id
        update_tob.message.text = "/keep"
        update_tob.message.reply_text = AsyncMock()
        state2 = asyncio.run(bot.chart_tob_received(update_tob, context_mock))
        self.assertEqual(state2, bot.WAITING_PLACE)
        self.assertEqual(context_mock.user_data.get("temp_tob"), datetime(1995, 6, 20, 8, 25).time())

        # 3. Шаг города: отправляем /keep (оставить Горно-Алтайск)
        update_place = MagicMock()
        update_place.effective_user.id = self.user_id
        update_place.message.text = "/keep"
        status_msg = AsyncMock()
        update_place.effective_message.reply_text = AsyncMock(return_value=status_msg)
        state3 = asyncio.run(bot.chart_place_received(update_place, context_mock))
        self.assertEqual(state3, bot.ConversationHandler.END)

        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["birth_dt"], datetime(1996, 6, 20, 8, 25))
        self.assertEqual(active["place_name"], "Горно-Алтайск")

    def test_cleanup_profiles_command_and_callback(self):
        """Проверка: команда /cleanprofiles и callback prof_cleanup_duplicates удаляют паразитные дубликаты."""
        import asyncio
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1996, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="",
            set_as_active=True,
            db_path=self.db_path,
        )
        save_profile(
            user_id=self.user_id,
            profile_name="Профиль 2",
            birth_dt=datetime(1996, 6, 20, 8, 25),
            place_name="Горно-Алтайск",
            resolved_address="Горно-Алтайск",
            lat=51.95,
            lon=85.96,
            tz_offset=7.0,
            chart_data={},
            summary="",
            set_as_active=False,
            db_path=self.db_path,
        )
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 2)

        # Вызываем команду /cleanprofiles
        update_mock = MagicMock()
        update_mock.effective_user.id = self.user_id
        update_mock.effective_user.language_code = "ru"
        update_mock.effective_message.reply_text = AsyncMock()
        context_mock = MagicMock()
        context_mock.user_data = {}

        asyncio.run(bot.cleanup_profiles_command(update_mock, context_mock))
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)

        # Проверяем ответ бота
        self.assertTrue(update_mock.effective_message.reply_text.called)
        reply_text = update_mock.effective_message.reply_text.call_args[0][0]
        self.assertIn("Удалено устаревших дубликатов: 1", reply_text)

    def test_stop_words_in_profile_name_received_does_not_create_profile(self):
        import asyncio
        for stop_query in [
            "бот сказал что сейчас период кончающийся в марте 2026",
            "март 2026",
            "октябрь 2026",
            "ошибка",
            "почему период марс",
        ]:
            update_mock = MagicMock()
            update_mock.effective_user.id = self.user_id
            update_mock.effective_user.language_code = "ru"
            update_mock.message.text = stop_query
            update_mock.message.reply_text = AsyncMock()
            context_mock = MagicMock()
            context_mock.user_data = {}

            state = asyncio.run(bot.profile_name_received(update_mock, context_mock))
            self.assertEqual(state, bot.WAITING_PROFILE_NAME, f"Failed for {stop_query}")
            self.assertIsNone(context_mock.user_data.get("temp_profile_name"), f"Name saved for {stop_query}")
            self.assertTrue(update_mock.message.reply_text.called)
            reply_text = update_mock.message.reply_text.call_args[0][0]
            self.assertIn("режим создания/настройки", reply_text)
            reply_markup = update_mock.message.reply_text.call_args[1].get("reply_markup")
            self.assertIsNotNone(reply_markup)
            buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
            self.assertIn("nav_ask", buttons)
            self.assertIn("reset_cache_only", buttons)

    def test_stop_words_in_chart_dob_received_does_not_set_dob(self):
        import asyncio
        for stop_query in [
            "в боте ошибка даты",
            "март 2026",
            "октябрь 2026",
            "ошибка",
        ]:
            update_mock = MagicMock()
            update_mock.effective_user.id = self.user_id
            update_mock.effective_user.language_code = "ru"
            update_mock.message.text = stop_query
            update_mock.message.reply_text = AsyncMock()
            context_mock = MagicMock()
            context_mock.user_data = {"temp_profile_name": "Александр"}

            state = asyncio.run(bot.chart_dob_received(update_mock, context_mock))
            self.assertEqual(state, bot.WAITING_DOB, f"Failed for {stop_query}")
            self.assertIsNone(context_mock.user_data.get("temp_dob"))
            self.assertEqual(context_mock.user_data.get("temp_profile_name"), "Александр")
            self.assertTrue(update_mock.message.reply_text.called)
            reply_text = update_mock.message.reply_text.call_args[0][0]
            self.assertIn("ожидает дату рождения", reply_text)
            reply_markup = update_mock.message.reply_text.call_args[1].get("reply_markup")
            self.assertIsNotNone(reply_markup)
            buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
            self.assertIn("nav_ask", buttons)
            self.assertIn("reset_cache_only", buttons)

    def test_discussive_message_in_fallback_text_handler(self):
        import asyncio
        for discuss_query in [
            "почему сейчас период марс?",
            "март 2026",
            "октябрь 2026",
            "в боте ошибка даты",
        ]:
            update_mock = MagicMock()
            update_mock.effective_user.id = self.user_id
            update_mock.effective_user.language_code = "ru"
            update_mock.message.text = discuss_query
            update_mock.effective_message.reply_text = AsyncMock()
            context_mock = MagicMock()
            context_mock.user_data = {}

            asyncio.run(bot.fallback_text_handler(update_mock, context_mock))
            self.assertTrue(update_mock.effective_message.reply_text.called)
            reply_text = update_mock.effective_message.reply_text.call_args[0][0]
            self.assertIn("Вопрос астрологу или разбор периодов", reply_text)
            reply_markup = update_mock.effective_message.reply_text.call_args[1].get("reply_markup")
            self.assertIsNotNone(reply_markup)
            buttons = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
            self.assertIn("nav_ask", buttons)


if __name__ == "__main__":
    unittest.main()

