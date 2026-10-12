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


if __name__ == "__main__":
    unittest.main()
