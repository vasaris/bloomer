"""Слой БД на aiosqlite: соединение, init схемы, лёгкие миграции, репозитории.

Sprint 1 добавил: колонку dog.arrived_at (миграция), лог событий
(прогулки/кормёжка) и астма-чек Макса с трендом.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

import aiosqlite

_SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


# ── Инициализация и миграции ───────────────────────────────────
async def _ensure_column(
    db: aiosqlite.Connection, table: str, column: str, decl: str
) -> None:
    """Идемпотентно добавляет колонку, если её ещё нет (мягкая миграция)."""
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


async def init_db(db_path: str) -> None:
    """Создаёт таблицы по schema.sql и докатывает миграции (idempotent)."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(schema)
        # Sprint 1: дата приезда — точка отсчёта адаптации (3-3-3).
        await _ensure_column(db, "dog", "arrived_at", "TEXT")
        # Sprint 2: помесячное пополнение заморозок стрика.
        await _ensure_column(db, "streak", "freeze_month", "TEXT")
        await db.commit()


async def connect(db_path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


# ── Пользователи ───────────────────────────────────────────────
async def upsert_user(
    db: aiosqlite.Connection, tg_chat_id: int, name: str | None, role: str = "owner"
) -> None:
    await db.execute(
        """
        INSERT INTO app_user (tg_chat_id, name, role)
        VALUES (?, ?, ?)
        ON CONFLICT(tg_chat_id) DO UPDATE SET
            name = COALESCE(excluded.name, app_user.name),
            is_active = 1
        """,
        (tg_chat_id, name, role),
    )
    await db.commit()


async def user_id_by_chat(db: aiosqlite.Connection, tg_chat_id: int) -> int | None:
    cur = await db.execute(
        "SELECT id FROM app_user WHERE tg_chat_id = ?", (tg_chat_id,)
    )
    row = await cur.fetchone()
    return row["id"] if row else None


async def active_chat_ids(db: aiosqlite.Connection) -> list[int]:
    cur = await db.execute("SELECT tg_chat_id FROM app_user WHERE is_active = 1")
    rows = await cur.fetchall()
    return [r["tg_chat_id"] for r in rows]


# ── Профиль собаки ─────────────────────────────────────────────
async def get_dog(db: aiosqlite.Connection) -> aiosqlite.Row | None:
    cur = await db.execute("SELECT * FROM dog ORDER BY id LIMIT 1")
    return await cur.fetchone()


async def ensure_dog(db: aiosqlite.Connection, name: str, breed: str) -> int:
    dog = await get_dog(db)
    if dog is not None:
        return dog["id"]
    cur = await db.execute(
        "INSERT INTO dog (name, breed) VALUES (?, ?)", (name, breed)
    )
    await db.commit()
    return cur.lastrowid


async def set_arrived(db: aiosqlite.Connection, day: dt.date) -> None:
    dog = await get_dog(db)
    if dog is None:
        return
    await db.execute(
        "UPDATE dog SET arrived_at = ? WHERE id = ?", (day.isoformat(), dog["id"])
    )
    await db.commit()


async def get_arrived(db: aiosqlite.Connection) -> dt.date | None:
    dog = await get_dog(db)
    if dog is None or not dog["arrived_at"]:
        return None
    return dt.date.fromisoformat(dog["arrived_at"])


# ── Лог событий (прогулки, кормёжка, …) ────────────────────────
async def log_event(
    db: aiosqlite.Connection,
    dog_id: int,
    module: str,
    type_: str,
    user_id: int | None = None,
    payload: dict | None = None,
) -> None:
    await db.execute(
        """INSERT INTO event_log (dog_id, user_id, module, type, payload_json)
           VALUES (?, ?, ?, ?, ?)""",
        (dog_id, user_id, module, type_, json.dumps(payload or {}, ensure_ascii=False)),
    )
    await db.commit()


async def count_events_today(
    db: aiosqlite.Connection, dog_id: int, type_: str, day: dt.date
) -> int:
    cur = await db.execute(
        """SELECT COUNT(*) AS n FROM event_log
           WHERE dog_id = ? AND type = ? AND date(created_at) = ?""",
        (dog_id, type_, day.isoformat()),
    )
    row = await cur.fetchone()
    return row["n"] if row else 0


# ── Астма-чек Макса ────────────────────────────────────────────
async def log_asthma(
    db: aiosqlite.Connection, day: dt.date, status: str, note: str | None = None
) -> None:
    """Один чек на дату; повторный тап обновляет статус."""
    await db.execute("DELETE FROM asthma_check WHERE date = ?", (day.isoformat(),))
    await db.execute(
        "INSERT INTO asthma_check (date, status, note) VALUES (?, ?, ?)",
        (day.isoformat(), status, note),
    )
    await db.commit()


async def asthma_done_today(db: aiosqlite.Connection, day: dt.date) -> bool:
    cur = await db.execute(
        "SELECT 1 FROM asthma_check WHERE date = ? LIMIT 1", (day.isoformat(),)
    )
    return await cur.fetchone() is not None


async def asthma_trend(db: aiosqlite.Connection, limit: int = 14) -> list[aiosqlite.Row]:
    cur = await db.execute(
        "SELECT date, status, note FROM asthma_check ORDER BY date DESC LIMIT ?",
        (limit,),
    )
    rows = await cur.fetchall()
    return list(reversed(rows))  # по возрастанию даты


# ── Геймификация: XP (Sprint 2) ───────────────────────────────
async def add_xp(db: aiosqlite.Connection, dog_id: int, amount: int) -> tuple[int, int]:
    """Начисляет XP собаке (shared, user_id IS NULL). Возвращает (было, стало)."""
    cur = await db.execute(
        "SELECT id, total FROM xp WHERE dog_id = ? AND user_id IS NULL", (dog_id,)
    )
    row = await cur.fetchone()
    if row is None:
        await db.execute(
            "INSERT INTO xp (dog_id, user_id, total, level) VALUES (?, NULL, ?, 1)",
            (dog_id, amount),
        )
        await db.commit()
        return 0, amount
    old = row["total"]
    new = old + amount
    await db.execute("UPDATE xp SET total = ? WHERE id = ?", (new, row["id"]))
    await db.commit()
    return old, new


async def get_xp(db: aiosqlite.Connection, dog_id: int) -> int:
    cur = await db.execute(
        "SELECT total FROM xp WHERE dog_id = ? AND user_id IS NULL", (dog_id,)
    )
    row = await cur.fetchone()
    return row["total"] if row else 0


# ── Геймификация: стрики (Sprint 2) ───────────────────────────
async def register_streak_day(
    db: aiosqlite.Connection, dog_id: int, kind: str, day: dt.date, freezes: int = 2
) -> int:
    """Засчитывает день для стрика. Возвращает текущее значение стрика.

    Логика заморозок: на новый календарный месяц freezes_left пополняется до
    `freezes`. Пропуски покрываются заморозками, если их хватает; иначе стрик
    сбрасывается на 1.
    """
    cur = await db.execute(
        "SELECT * FROM streak WHERE dog_id = ? AND kind = ?", (dog_id, kind)
    )
    row = await cur.fetchone()
    month = day.strftime("%Y-%m")

    if row is None:
        await db.execute(
            """INSERT INTO streak (dog_id, kind, current, best, last_day,
                                   freezes_left, freeze_month)
               VALUES (?, ?, 1, 1, ?, ?, ?)""",
            (dog_id, kind, day.isoformat(), freezes, month),
        )
        await db.commit()
        return 1

    last = dt.date.fromisoformat(row["last_day"]) if row["last_day"] else None
    freezes_left = row["freezes_left"]
    if row["freeze_month"] != month:        # новый месяц — пополнить заморозки
        freezes_left = freezes

    if last == day:                          # уже засчитан сегодня
        # всё равно зафиксируем возможное пополнение заморозок
        await db.execute(
            "UPDATE streak SET freezes_left = ?, freeze_month = ? WHERE id = ?",
            (freezes_left, month, row["id"]),
        )
        await db.commit()
        return row["current"]

    if last is None:
        current = 1
    else:
        gap = (day - last).days
        if gap == 1:
            current = row["current"] + 1
        else:
            missed = gap - 1
            if freezes_left >= missed:
                freezes_left -= missed
                current = row["current"] + 1
            else:
                current = 1

    best = max(row["best"], current)
    await db.execute(
        """UPDATE streak SET current = ?, best = ?, last_day = ?,
                             freezes_left = ?, freeze_month = ? WHERE id = ?""",
        (current, best, day.isoformat(), freezes_left, month, row["id"]),
    )
    await db.commit()
    return current


async def get_streak(db: aiosqlite.Connection, dog_id: int, kind: str) -> int:
    cur = await db.execute(
        "SELECT current FROM streak WHERE dog_id = ? AND kind = ?", (dog_id, kind)
    )
    row = await cur.fetchone()
    return row["current"] if row else 0


# ── Геймификация: ачивки (Sprint 2) ───────────────────────────
async def unlock_achievement(db: aiosqlite.Connection, dog_id: int, code: str) -> bool:
    """Разблокирует ачивку. True — если разблокирована впервые."""
    cur = await db.execute(
        "SELECT 1 FROM achievement WHERE dog_id = ? AND code = ? AND user_id IS NULL LIMIT 1",
        (dog_id, code),
    )
    if await cur.fetchone() is not None:
        return False
    await db.execute(
        "INSERT INTO achievement (dog_id, user_id, code) VALUES (?, NULL, ?)",
        (dog_id, code),
    )
    await db.commit()
    return True


async def list_achievements(db: aiosqlite.Connection, dog_id: int) -> list[str]:
    cur = await db.execute(
        "SELECT code FROM achievement WHERE dog_id = ? ORDER BY unlocked_at", (dog_id,)
    )
    return [r["code"] for r in await cur.fetchall()]
