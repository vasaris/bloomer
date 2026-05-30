"""Общий сервис логирования: запись события в журнал + начисление XP/стриков/ачивок.

Используется и прогулками/кормёжкой/нюхо (handlers/logging), и грумингом
(modules/m3_grooming), чтобы не дублировать логику.
"""
from __future__ import annotations

import datetime as dt

from . import db, gamification


async def log_and_reward(
    settings, chat_id: int, module: str, type_: str,
    payload: dict | None = None, on_date: dt.date | None = None,
) -> list[str]:
    """Логирует событие и применяет геймификацию. Возвращает праздничные сообщения."""
    today = on_date or settings.today()
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        uid = await db.user_id_by_chat(conn, chat_id)
        await db.log_event(conn, dog["id"], module, type_, today, user_id=uid, payload=payload)
        return await gamification.on_event(conn, dog["id"], type_, today)
    finally:
        await conn.close()
