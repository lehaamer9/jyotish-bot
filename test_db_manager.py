"""
Unit tests for db_manager.py.
Tests profile creation, retrieval, active profile switching, updates, deletions, and edge cases.
"""

import os
import unittest
import tempfile
from datetime import datetime
from db_manager import (
    init_db,
    save_profile,
    get_active_profile,
    get_user_profiles,
    get_profile_by_id,
    set_active_profile,
    delete_profile,
    rename_profile,
    clear_user_profiles,
    count_user_profiles,
)


class TestDBManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_jyotish.db")
        init_db(self.db_path)
        self.user_id = 123456789

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_get_active_profile(self):
        chart_mock = {"planets": [{"name": "Sun", "sign": "Aries"}]}
        birth_dt = datetime(1990, 5, 15, 10, 30)
        
        prof_id = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=birth_dt,
            place_name="Москва",
            resolved_address="Москва, Россия",
            lat=55.7558,
            lon=37.6173,
            tz_offset=3.0,
            chart_data=chart_mock,
            summary="Краткая сводка карты",
            set_as_active=True,
            db_path=self.db_path,
        )

        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], prof_id)
        self.assertEqual(active["profile_name"], "Мой гороскоп")
        self.assertEqual(active["birth_dt"], birth_dt)
        self.assertEqual(active["place_name"], "Москва")
        self.assertEqual(active["chart_data"], chart_mock)
        self.assertTrue(active["is_active"])

    def test_multiple_profiles_and_switch(self):
        # 1-й профиль
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 5, 15, 10, 30),
            place_name="Москва",
            resolved_address="Москва, Россия",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={"asc": "Leo"},
            summary="Сводка 1",
            set_as_active=True,
            db_path=self.db_path,
        )

        # 2-й профиль
        id2 = save_profile(
            user_id=self.user_id,
            profile_name="Жена",
            birth_dt=datetime(1992, 8, 20, 14, 20),
            place_name="Санкт-Петербург",
            resolved_address="Санкт-Петербург, Россия",
            lat=59.93,
            lon=30.33,
            tz_offset=3.0,
            chart_data={"asc": "Scorpio"},
            summary="Сводка 2",
            set_as_active=True,
            db_path=self.db_path,
        )

        # После создания id2 активным должен стать id2
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], id2)
        self.assertEqual(active["profile_name"], "Жена")

        # Переключаем обратно на id1
        success = set_active_profile(id1, self.user_id, db_path=self.db_path)
        self.assertTrue(success)

        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertEqual(active["id"], id1)
        self.assertEqual(active["profile_name"], "Мой гороскоп")

        # Проверяем общий список профилей
        profs = get_user_profiles(self.user_id, db_path=self.db_path)
        self.assertEqual(len(profs), 2)
        # Активный должен идти первым в списке
        self.assertEqual(profs[0]["id"], id1)

    def test_update_existing_profile(self):
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп",
            birth_dt=datetime(1990, 5, 15, 10, 30),
            place_name="Москва",
            resolved_address="Москва, Россия",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={"asc": "Leo"},
            summary="Сводка старая",
            set_as_active=True,
            db_path=self.db_path,
        )

        # Обновляем профиль с profile_id=id1
        updated_dt = datetime(1990, 5, 15, 11, 00)
        save_profile(
            user_id=self.user_id,
            profile_name="Мой гороскоп (исправлен)",
            birth_dt=updated_dt,
            place_name="Москва",
            resolved_address="Москва, Россия",
            lat=55.75,
            lon=37.61,
            tz_offset=3.0,
            chart_data={"asc": "Virgo"},
            summary="Сводка новая",
            set_as_active=True,
            profile_id=id1,
            db_path=self.db_path,
        )

        prof = get_profile_by_id(id1, self.user_id, db_path=self.db_path)
        self.assertEqual(prof["profile_name"], "Мой гороскоп (исправлен)")
        self.assertEqual(prof["birth_dt"], updated_dt)
        self.assertEqual(prof["summary"], "Сводка новая")
        self.assertEqual(count_user_profiles(self.user_id, db_path=self.db_path), 1)

    def test_delete_profile_and_fallback_activation(self):
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Профиль 1",
            birth_dt=datetime(1985, 1, 1, 10, 0),
            place_name="Киев",
            resolved_address="Киев",
            lat=50.45,
            lon=30.52,
            tz_offset=2.0,
            chart_data={},
            summary="1",
            set_as_active=False,
            db_path=self.db_path,
        )
        id2 = save_profile(
            user_id=self.user_id,
            profile_name="Профиль 2",
            birth_dt=datetime(1995, 2, 2, 12, 0),
            place_name="Алматы",
            resolved_address="Алматы",
            lat=43.23,
            lon=76.88,
            tz_offset=5.0,
            chart_data={},
            summary="2",
            set_as_active=True,
            db_path=self.db_path,
        )

        # Удаляем активный id2
        del_ok = delete_profile(id2, self.user_id, db_path=self.db_path)
        self.assertTrue(del_ok)

        # id1 должен стать активным автоматически!
        active = get_active_profile(self.user_id, db_path=self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], id1)
        self.assertTrue(active["is_active"])

    def test_rename_and_clear(self):
        id1 = save_profile(
            user_id=self.user_id,
            profile_name="Временный",
            birth_dt=datetime(2000, 1, 1, 12, 0),
            place_name="Рим",
            resolved_address="Рим",
            lat=41.9,
            lon=12.5,
            tz_offset=1.0,
            chart_data={},
            summary="",
            db_path=self.db_path,
        )
        self.assertTrue(rename_profile(id1, self.user_id, "Римский профиль", db_path=self.db_path))
        prof = get_profile_by_id(id1, self.user_id, db_path=self.db_path)
        self.assertEqual(prof["profile_name"], "Римский профиль")

        cleared_count = clear_user_profiles(self.user_id, db_path=self.db_path)
        self.assertEqual(cleared_count, 1)
        self.assertIsNone(get_active_profile(self.user_id, db_path=self.db_path))

    def test_empty_user_returns_none(self):
        self.assertIsNone(get_active_profile(99999999, db_path=self.db_path))
        self.assertEqual(get_user_profiles(99999999, db_path=self.db_path), [])


if __name__ == "__main__":
    unittest.main()
