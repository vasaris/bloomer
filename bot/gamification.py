"""Геймификация v1 (Sprint 2): XP, уровни, стрики, ачивки.

Один вход — on_event(): вызывается после логирования события, начисляет XP,
обновляет стрики, разблокирует ачивки и возвращает список «праздничных»
сообщений голосом Блумера (персона C) для отправки пользователю.
"""
from __future__ import annotations

import datetime as dt

import aiosqlite

from . import db, texts

# XP за событие (BLUMER_BOT_SPEC.md §5). groom/health/soc — будущие спринты.
XP_PER_EVENT: dict[str, int] = {
    "walk": 10,
    "nose": 15,
    "command": 15,
    "groom": 20,
    "health": 10,
    "soc": 25,
}

# Уровни: (порог XP, название). Уровень = первый, чей порог ≤ total.
LEVELS: list[tuple[int, str]] = [
    (0, "Новичок"),
    (100, "Ученик"),
    (300, "Искатель"),
    (700, "Следопыт"),
    (1500, "Мастер-трюфельщик"),
]

# Сколько прогулок в день нужно, чтобы день засчитался в стрик прогулок.
WALKS_PER_DAY = 2

# Пороги стриков → код ачивки.
WALK_STREAK_ACH: dict[int, str] = {7: "walk_7", 30: "walk_30", 100: "walk_100", 365: "walk_365"}
NOSE_STREAK_ACH: dict[int, str] = {7: "nose_7", 30: "nose_30"}
COMMAND_STREAK_ACH: dict[int, str] = {7: "command_7", 30: "command_30"}

# Каталог ачивок: code → (эмодзи, название).
ACHIEVEMENTS: dict[str, tuple[str, str]] = {
    "home": ("🏡", "Дома (адаптация 3-3-3 пройдена)"),
    "walk_7": ("🦮", "Неделя прогулок"),
    "walk_30": ("🦮", "30 дней прогулок"),
    "walk_100": ("🦮", "100 дней прогулок"),
    "walk_365": ("🦮", "Год прогулок"),
    "nose_7": ("👃", "Неделя нюхо-тренинга"),
    "nose_30": ("👃", "Месяц нюхо-тренинга"),
    "command_7": ("🧠", "Неделя послушания"),
    "command_30": ("🧠", "Месяц послушания"),
    "recall_master": ("🎯", "Надёжный отзыв (мастерство 5/5)"),
    "truffle_scent": ("👃", "Первый запах — нашёл спрятанный аромат"),
    "truffle_find": ("🍝", "Чёрный трюфель — первая полевая находка"),
}


def level_for(total: int) -> str:
    name = LEVELS[0][1]
    for threshold, label in LEVELS:
        if total >= threshold:
            name = label
        else:
            break
    return name


def level_index(total: int) -> int:
    """Индекс уровня 0..len(LEVELS)-1 (для гейтинга сложности нюхо-игр)."""
    idx = 0
    for i, (threshold, _) in enumerate(LEVELS):
        if total >= threshold:
            idx = i
        else:
            break
    return idx


def ach_title(code: str) -> str:
    emoji, title = ACHIEVEMENTS.get(code, ("🏅", code))
    return f"{emoji} {title}"


async def _maybe_unlock(conn, dog_id: int, code: str, out: list[str]) -> None:
    if await db.unlock_achievement(conn, dog_id, code):
        out.append(texts.BLOOMER_VOICE["achievement_unlocked"].format(title=ach_title(code)))


async def award_xp(conn: aiosqlite.Connection, dog_id: int, amount: int) -> list[str]:
    """Начисляет XP и возвращает сообщение об апе уровня, если уровень сменился."""
    out: list[str] = []
    if amount:
        old, new = await db.add_xp(conn, dog_id, amount)
        if level_for(old) != level_for(new):
            out.append(texts.BLOOMER_VOICE["level_up"].format(level=level_for(new)))
    return out


async def unlock(conn: aiosqlite.Connection, dog_id: int, code: str) -> list[str]:
    """Публичная разблокировка ачивки (для модулей вне on_event). Возвращает сообщения."""
    out: list[str] = []
    await _maybe_unlock(conn, dog_id, code, out)
    return out


async def on_event(
    conn: aiosqlite.Connection, dog_id: int, type_: str, today: dt.date
) -> list[str]:
    """Начисляет XP/стрики/ачивки за событие. Возвращает сообщения для пуша."""
    msgs: list[str] = []

    # 1. XP + возможный ап уровня.
    msgs += await award_xp(conn, dog_id, XP_PER_EVENT.get(type_, 0))

    # 2. Стрики + ачивки порогов.
    if type_ == "walk":
        walks_today = await db.count_events_today(conn, dog_id, "walk", today)
        if walks_today == WALKS_PER_DAY:  # ровно при достижении нормы дня
            cur = await db.register_streak_day(conn, dog_id, "walk", today)
            if cur in WALK_STREAK_ACH:
                await _maybe_unlock(conn, dog_id, WALK_STREAK_ACH[cur], msgs)
    elif type_ == "nose":
        cur = await db.register_streak_day(conn, dog_id, "nose", today)
        if cur in NOSE_STREAK_ACH:
            await _maybe_unlock(conn, dog_id, NOSE_STREAK_ACH[cur], msgs)
    elif type_ == "command":
        cur = await db.register_streak_day(conn, dog_id, "command", today)
        if cur in COMMAND_STREAK_ACH:
            await _maybe_unlock(conn, dog_id, COMMAND_STREAK_ACH[cur], msgs)

    return msgs


async def check_home_achievement(
    conn: aiosqlite.Connection, dog_id: int, adaptation_day: int | None
) -> list[str]:
    """Ачивка «Дома» по достижении 21-го дня адаптации (зовётся из итога дня)."""
    out: list[str] = []
    if adaptation_day is not None and adaptation_day >= 21:
        await _maybe_unlock(conn, dog_id, "home", out)
    return out
