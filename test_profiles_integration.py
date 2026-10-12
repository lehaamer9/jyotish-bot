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

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main()
