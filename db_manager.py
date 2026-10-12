"""
Модуль постоянного хранения астрологических профилей в SQLite (jyotish.db).
Обеспечивает сохранение, извлечение, переключение и управление несколькими профилями на пользователя.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jyotish.db")
DB_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
DEFAULT_BACKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.json")
BACKUP_PATH = os.getenv("PROFILES_BACKUP_PATH", DEFAULT_BACKUP_PATH)


def export_db_to_backup(db_path: Optional[str] = None, json_path: Optional[str] = None) -> None:
    """Экспорт всех профилей из SQLite в JSON файл резервной копии."""
    path = db_path or DB_PATH
    if json_path is None:
        target_path = os.path.abspath(path)
        prod_path = os.path.abspath(DEFAULT_DB_PATH)
        env_path = os.path.abspath(os.getenv("DATABASE_PATH", DEFAULT_DB_PATH))
        if target_path != prod_path and target_path != env_path:
            return
        json_path = BACKUP_PATH
    try:
        with get_db(path) as conn:
            cur = conn.execute("SELECT * FROM profiles ORDER BY id ASC;")
            rows = cur.fetchall()
            data = []
            for r in rows:
                data.append({
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "profile_name": r["profile_name"],
                    "birth_dt": r["birth_dt"],
                    "place_name": r["place_name"],
                    "resolved_address": r["resolved_address"] or "",
                    "lat": float(r["lat"]),
                    "lon": float(r["lon"]),
                    "tz_offset": float(r["tz_offset"]),
                    "chart_data": r["chart_data"],
                    "summary": r["summary"] or "",
                    "is_active": int(r["is_active"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                })
        temp_path = json_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, json_path)
        logger.debug(f"Резервная копия профилей обновлена: {json_path} ({len(data)} профилей)")
    except Exception as e:
        logger.error(f"Ошибка экспорта профилей в {json_path}: {e}")


def restore_backup_to_db(db_path: Optional[str] = None, json_path: Optional[str] = None) -> int:
    """Восстановление профилей из JSON резервной копии в SQLite, если таблица пуста."""
    path = db_path or DB_PATH
    if json_path is None:
        target_path = os.path.abspath(path)
        prod_path = os.path.abspath(DEFAULT_DB_PATH)
        env_path = os.path.abspath(os.getenv("DATABASE_PATH", DEFAULT_DB_PATH))
        if target_path != prod_path and target_path != env_path:
            return 0
        json_path = BACKUP_PATH
    if not json_path or not os.path.exists(json_path):
        return 0
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            return 0
        restored = 0
        with get_db(path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM profiles;")
            count = cur.fetchone()[0]
            if count == 0:
                for item in data:
                    chart_str = item.get("chart_data")
                    if isinstance(chart_str, dict):
                        chart_str = json.dumps(chart_str, ensure_ascii=False)
                    conn.execute("""
                        INSERT INTO profiles (
                            id, user_id, profile_name, birth_dt, place_name, resolved_address,
                            lat, lon, tz_offset, chart_data, summary, is_active, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        item.get("id"),
                        item["user_id"],
                        item["profile_name"],
                        str(item["birth_dt"]),
                        item["place_name"],
                        item.get("resolved_address", ""),
                        float(item["lat"]),
                        float(item["lon"]),
                        float(item["tz_offset"]),
                        chart_str,
                        item.get("summary", ""),
                        int(item.get("is_active", 1)),
                        item.get("created_at", datetime.now(timezone.utc).isoformat()),
                        item.get("updated_at", datetime.now(timezone.utc).isoformat())
                    ))
                    restored += 1
                conn.commit()
                logger.info(f"Восстановлено {restored} профилей из {json_path} в базу {path}")
        return restored
    except Exception as e:
        logger.error(f"Ошибка восстановления профилей из {json_path}: {e}")
        return 0


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Создать подключение к SQLite базе данных с поддержкой WAL и Row-фабрики."""
    path = db_path or DB_PATH
    dir_name = os.path.dirname(os.path.abspath(path))
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db(db_path: Optional[str] = None):
    """Контекстный менеджер подключения к базе данных, гарантирующий закрытие соединения."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Инициализация таблиц базы данных, индексов и восстановление из резервной копии."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_name TEXT NOT NULL,
                birth_dt TEXT NOT NULL,
                place_name TEXT NOT NULL,
                resolved_address TEXT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                tz_offset REAL NOT NULL,
                chart_data TEXT NOT NULL,
                summary TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_user ON profiles(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_profiles_user_active ON profiles(user_id, is_active);")
        conn.commit()
    logger.info(f"База данных профилей инициализирована: {path}")

    # Восстановление из JSON резервной копии, если база пуста
    restore_backup_to_db(path)
    # Актуализация JSON-бэкапа
    export_db_to_backup(path)


def _row_to_profile(row: sqlite3.Row) -> Dict[str, Any]:
    """Преобразовать строку из таблицы profiles в словарь с десериализованными объектами."""
    chart_data = {}
    raw_chart = row["chart_data"]
    if isinstance(raw_chart, str) and raw_chart:
        try:
            chart_data = json.loads(raw_chart)
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON chart_data для профиля {row['id']}: {e}")
    elif isinstance(raw_chart, dict):
        chart_data = raw_chart

    birth_dt_raw = row["birth_dt"]
    birth_dt = None
    if isinstance(birth_dt_raw, str):
        for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                if fmt is None:
                    birth_dt = datetime.fromisoformat(birth_dt_raw)
                else:
                    birth_dt = datetime.strptime(birth_dt_raw, fmt)
                break
            except Exception:
                continue
        if birth_dt is None:
            logger.error(f"Не удалось распарсить birth_dt '{birth_dt_raw}' для профиля {row['id']}, fallback на текущее время")
            birth_dt = datetime.now()
    elif isinstance(birth_dt_raw, datetime):
        birth_dt = birth_dt_raw
    else:
        birth_dt = datetime.now()

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "profile_name": row["profile_name"],
        "birth_dt": birth_dt,
        "place_name": row["place_name"],
        "resolved_address": row["resolved_address"] or "",
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "tz_offset": float(row["tz_offset"]),
        "chart_data": chart_data,
        "summary": row["summary"] or "",
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def save_profile(
    user_id: int,
    profile_name: str,
    birth_dt: Any,
    place_name: str,
    resolved_address: str,
    lat: float,
    lon: float,
    tz_offset: float,
    chart_data: Any,
    summary: str,
    set_as_active: bool = True,
    profile_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> int:
    """
    Сохранить или обновить натальный профиль пользователя.
    
    Если profile_id указан — обновляет существующий профиль.
    Если profile_id не указан — создает новый профиль.
    Возвращает id сохраненного профиля.
    """
    path = db_path or DB_PATH
    now_iso = datetime.now(timezone.utc).isoformat()
    birth_dt_iso = birth_dt.isoformat() if isinstance(birth_dt, datetime) else str(birth_dt)
    chart_json = json.dumps(chart_data, ensure_ascii=False, default=str) if isinstance(chart_data, dict) else str(chart_data)

    with get_db(path) as conn:
        if profile_id is not None:
            # Обновление существующего профиля
            if set_as_active:
                conn.execute("UPDATE profiles SET is_active = 0 WHERE user_id = ?;", (user_id,))
            
            cur = conn.execute("""
                UPDATE profiles SET
                    profile_name = ?,
                    birth_dt = ?,
                    place_name = ?,
                    resolved_address = ?,
                    lat = ?,
                    lon = ?,
                    tz_offset = ?,
                    chart_data = ?,
                    summary = ?,
                    is_active = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ?;
            """, (
                profile_name,
                birth_dt_iso,
                place_name,
                resolved_address or "",
                lat,
                lon,
                tz_offset,
                chart_json,
                summary or "",
                1 if set_as_active else 0,
                now_iso,
                profile_id,
                user_id
            ))
            if cur.rowcount > 0:
                conn.commit()
                export_db_to_backup(path)
                return profile_id

        # Создание нового профиля (если profile_id is None или профиль для обновления не найден)
        if set_as_active:
            conn.execute("UPDATE profiles SET is_active = 0 WHERE user_id = ?;", (user_id,))

        cur = conn.execute("""
            INSERT INTO profiles (
                user_id,
                profile_name,
                birth_dt,
                place_name,
                resolved_address,
                lat,
                lon,
                tz_offset,
                chart_data,
                summary,
                is_active,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            user_id,
            profile_name,
            birth_dt_iso,
            place_name,
            resolved_address or "",
            lat,
            lon,
            tz_offset,
            chart_json,
            summary or "",
            1 if set_as_active else 0,
            now_iso,
            now_iso
        ))
        conn.commit()
        export_db_to_backup(path)
        return cur.lastrowid


def get_active_profile(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Получить активный профиль пользователя.
    Если явного активного профиля нет, выбирает самый свежий и делает его активным.
    """
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute(
            "SELECT * FROM profiles WHERE user_id = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1;",
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            return _row_to_profile(row)

        # Fallback: самый свежий профиль
        cur = conn.execute(
            "SELECT * FROM profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1;",
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE profiles SET is_active = 1 WHERE id = ?;", (row["id"],))
            conn.commit()
            return _row_to_profile(row)

        return None


def get_user_profiles(user_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Получить все профили пользователя (активный в начале списка)."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute(
            "SELECT * FROM profiles WHERE user_id = ? ORDER BY is_active DESC, updated_at DESC;",
            (user_id,)
        )
        rows = cur.fetchall()
        return [_row_to_profile(r) for r in rows]


def get_profile_by_id(profile_id: int, user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Получить профиль по id с проверкой принадлежности user_id."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute(
            "SELECT * FROM profiles WHERE id = ? AND user_id = ?;",
            (profile_id, user_id)
        )
        row = cur.fetchone()
        if row:
            return _row_to_profile(row)
        return None


def set_active_profile(profile_id: int, user_id: int, db_path: Optional[str] = None) -> bool:
    """Сделать выбранный профиль активным для пользователя."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute("SELECT id FROM profiles WHERE id = ? AND user_id = ?;", (profile_id, user_id))
        if not cur.fetchone():
            return False
        conn.execute("UPDATE profiles SET is_active = 0 WHERE user_id = ?;", (user_id,))
        cur = conn.execute(
            "UPDATE profiles SET is_active = 1, updated_at = ? WHERE id = ? AND user_id = ?;",
            (datetime.now(timezone.utc).isoformat(), profile_id, user_id)
        )
        conn.commit()
        export_db_to_backup(path)
        return cur.rowcount > 0


def delete_profile(profile_id: int, user_id: int, db_path: Optional[str] = None) -> bool:
    """
    Удалить профиль пользователя.
    Если удаляемый профиль был активным, активирует следующий оставшийся.
    """
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute("SELECT is_active FROM profiles WHERE id = ? AND user_id = ?;", (profile_id, user_id))
        row = cur.fetchone()
        if not row:
            return False

        was_active = bool(row["is_active"])
        conn.execute("DELETE FROM profiles WHERE id = ? AND user_id = ?;", (profile_id, user_id))

        if was_active:
            cur = conn.execute("SELECT id FROM profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1;", (user_id,))
            next_row = cur.fetchone()
            if next_row:
                conn.execute("UPDATE profiles SET is_active = 1 WHERE id = ?;", (next_row["id"],))

        conn.commit()
        export_db_to_backup(path)
        return True


def rename_profile(profile_id: int, user_id: int, new_name: str, db_path: Optional[str] = None) -> bool:
    """Переименовать профиль пользователя."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute(
            "UPDATE profiles SET profile_name = ?, updated_at = ? WHERE id = ? AND user_id = ?;",
            (new_name, datetime.now(timezone.utc).isoformat(), profile_id, user_id)
        )
        conn.commit()
        export_db_to_backup(path)
        return cur.rowcount > 0


def clear_user_profiles(user_id: int, db_path: Optional[str] = None) -> int:
    """Удалить все профили пользователя."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute("DELETE FROM profiles WHERE user_id = ?;", (user_id,))
        conn.commit()
        export_db_to_backup(path)
        return cur.rowcount


def count_user_profiles(user_id: int, db_path: Optional[str] = None) -> int:
    """Посчитать количество профилей пользователя."""
    path = db_path or DB_PATH
    with get_db(path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM profiles WHERE user_id = ?;", (user_id,))
        return cur.fetchone()[0]
