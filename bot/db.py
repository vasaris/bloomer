"""Слой БД на aiosqlite. Тонкий: соединение, init схемы, пара хелперов.

В Sprint 0 нужно немного — зарегистрировать пользователя и обеспечить
наличие профиля собаки. Репозитории под остальные таблицы добавим в
соответствующих спринтах.
"""
from __future__ import annotations

import pathlib

import aiosqlite

_SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"


async def init_db(db_path: str) -> None:
    """Создаёт таблицы по schema.sql (idempotent)."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(schema)
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


async def active_chat_ids(db: aiosqlite.Connection) -> list[int]:
    cur = await db.execute(
        "SELECT tg_chat_id FROM app_user WHERE is_active = 1"
    )
    rows = await cur.fetchall()
    return [r["tg_chat_id"] for r in rows]


# ── Профиль собаки ─────────────────────────────────────────────
async def get_dog(db: aiosqlite.Connection) -> aiosqlite.Row | None:
    cur = await db.execute("SELECT * FROM dog ORDER BY id LIMIT 1")
    return await cur.fetchone()


async def ensure_dog(db: aiosqlite.Connection, name: str, breed: str) -> int:
    """Создаёт профиль собаки, если его ещё нет. Возвращает dog_id."""
    dog = await get_dog(db)
    if dog is not None:
        return dog["id"]
    cur = await db.execute(
        "INSERT INTO dog (name, breed) VALUES (?, ?)", (name, breed)
    )
    await db.commit()
    return cur.lastrowid
