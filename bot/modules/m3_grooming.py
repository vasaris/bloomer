"""M3 — Груминг. Цикл по типам с интервалами (BLUMER_SYSTEM.md §4):
расчёсывание (нед.), уши, купание (2–3 нед.), стрижка у грумера (6–8 нед.).

Последняя дата по каждому типу берётся из журнала (event_log, type='groom',
payload.kind). «Пора» = прошло ≥ интервала. Логирование сбрасывает таймер
и даёт XP (+20, через logbook → gamification).
"""
from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, keyboards, logbook

router = Router()

# code → (эмодзи, название, интервал в днях, заметка)
GROOM: dict[str, tuple[str, str, int, str]] = {
    "brush": ("🪮", "Расчёсывание", 7, "кудри сваливаются — раз в неделю"),
    "ears": ("👂", "Чистка ушей", 14, "склонность к отитам — чистить регулярно"),
    "bath": ("🛁", "Купание", 18, "раз в 2–3 недели, чаще нельзя — сушит кожу"),
    "haircut": ("✂️", "Стрижка у грумера", 49, "каждые 6–8 недель, не брить наголо"),
}
GROOM_ORDER = ["brush", "ears", "bath", "haircut"]


def status_line(code: str, last: dt.date | None, today: dt.date) -> tuple[bool, str]:
    """Возвращает (пора_ли, строка статуса)."""
    emoji, label, interval, _ = GROOM[code]
    if last is None:
        return True, f"{emoji} <b>{label}</b> — ещё не отмечали, пора."
    days = (today - last).days
    if days >= interval:
        return True, f"{emoji} <b>{label}</b> — пора (прошло {days} дн.)."
    return False, f"{emoji} {label} — ок, через {interval - days} дн."


async def _all_status(conn, dog_id: int, today: dt.date) -> list[tuple[str, bool, str]]:
    out = []
    for code in GROOM_ORDER:
        last = await db.last_groom(conn, dog_id, code)
        due, line = status_line(code, last, today)
        out.append((code, due, line))
    return out


async def due_codes(conn, dog_id: int, today: dt.date) -> list[str]:
    return [c for c, due, _ in await _all_status(conn, dog_id, today) if due]


@router.message(Command("groom"))
async def cmd_groom(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        rows = await _all_status(conn, dog["id"], settings.today())
    finally:
        await conn.close()
    text = "🧼 <b>Груминг</b>\n" + "\n".join(line for _, _, line in rows)
    await message.answer(text, reply_markup=keyboards.groom_kb())


@router.callback_query(F.data.startswith("groom:"))
async def on_groom(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in GROOM:
        await cb.answer()
        return
    extra = await logbook.log_and_reward(
        settings, cb.from_user.id, "M3", "groom", {"kind": code}
    )
    emoji, label, _, _ = GROOM[code]
    await cb.message.edit_text(f"{emoji} {label} — отмечено. Таймер сброшен.")
    await cb.answer("Записал 🧼")
    for msg in extra:
        await cb.message.answer(msg)
