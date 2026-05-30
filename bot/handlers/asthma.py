"""Астма-чек Макса (M0): тап по статусу → запись + тренд /asthma.

Ветка 'concern' даёт организационные меры и направляет к аллергологу —
без медицинских назначений (по правилам проекта).
"""
from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, texts

router = Router()


@router.callback_query(F.data.startswith("asthma:"))
async def on_asthma(cb: CallbackQuery, settings) -> None:
    status = cb.data.split(":", 1)[1]  # ok | mild | concern
    conn = await db.connect(settings.db_path)
    try:
        await db.log_asthma(conn, dt.date.today(), status)
    finally:
        await conn.close()
    await cb.message.edit_text(texts.ASTHMA_REPLY.get(status, "Записал."))
    await cb.answer()


@router.message(Command("asthma"))
async def cmd_asthma(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        rows = await db.asthma_trend(conn, limit=14)
    finally:
        await conn.close()

    if not rows:
        await message.answer(texts.ASTHMA_NO_DATA)
        return

    line = " ".join(texts.ASTHMA_EMOJI.get(r["status"], "▫️") for r in rows)
    span = f"{rows[0]['date']} → {rows[-1]['date']}"
    await message.answer(f"{texts.ASTHMA_TREND_TITLE}\n{line}\n<i>{span}</i>")
