"""Сборка текстов пушей из БД: утренний бриф, итог дня, астма-чек.

Держим логику здесь, чтобы scheduler оставался тонким. build_push() возвращает
(text, keyboard) либо None, если пуш сегодня не нужен (напр. астма вне окна 21 дня).
"""
from __future__ import annotations

import datetime as dt

from aiogram.types import InlineKeyboardMarkup

from . import db, keyboards, texts
from .config import Settings
from .modules import m0_adaptation as m0


async def _morning_brief(conn, today: dt.date) -> tuple[str, InlineKeyboardMarkup | None]:
    arrived = await db.get_arrived(conn)
    lines = ["☀️ <b>Утренний бриф</b>"]

    n = m0.adaptation_day(arrived, today)
    if n is None:
        lines.append("• Дата приезда не задана — отметь командой /arrived.")
    elif n <= m0.ADAPT_LEN:
        lines.append(f"• Адаптация, день {n}/{m0.ADAPT_LEN}: {m0.day_card(n)}")
    # после 21 дня адаптацию в бриф не тащим — фаза «дома»

    lines.append("• Прогулка утром и вечером (отметишь по кнопке на пуше).")
    lines.append("• Кормёжка по графику ×2.")
    if n is not None and n <= m0.ADAPT_LEN:
        lines.append("• Вечером — астма-чек Макса.")
    # TODO Sprint 6: проверка жары (погодное API) перед утренней прогулкой.
    return "\n".join(lines), None


async def _day_summary(conn, today: dt.date) -> tuple[str, InlineKeyboardMarkup | None]:
    dog = await db.get_dog(conn)
    dog_id = dog["id"]
    walks = await db.count_events_today(conn, dog_id, "walk", today)
    feeds = await db.count_events_today(conn, dog_id, "feed", today)
    asthma_done = await db.asthma_done_today(conn, today)
    arrived = await db.get_arrived(conn)
    n = m0.adaptation_day(arrived, today)
    in_window = n is not None and n <= m0.ADAPT_LEN

    lines = ["🌙 <b>Итог дня</b>"]
    lines.append(f"🚶 Прогулок: {walks}")
    lines.append(f"🍽 Кормёжек: {feeds}")
    if in_window:
        lines.append(f"🫁 Астма-чек: {'✓' if asthma_done else '— не отмечен'}")
    # Стрики/XP — Sprint 2.

    # Персона C: эмоц. точка — голос Блумера в удачный день.
    done_ok = walks >= 1 and feeds >= 1 and (asthma_done or not in_window)
    if done_ok:
        lines.append("\n" + texts.BLOOMER_VOICE["good_day"])
    return "\n".join(lines), None


async def build_push(
    code: str, settings: Settings, today: dt.date | None = None
) -> tuple[str, InlineKeyboardMarkup | None] | None:
    """Возвращает (text, keyboard) или None, если пуш сегодня пропускаем."""
    today = today or dt.date.today()
    conn = await db.connect(settings.db_path)
    try:
        if code == "morning_brief":
            return await _morning_brief(conn, today)
        if code == "day_summary":
            return await _day_summary(conn, today)
        if code == "asthma_check":
            arrived = await db.get_arrived(conn)
            n = m0.adaptation_day(arrived, today)
            if n is None or n > m0.ADAPT_LEN:
                return None  # вне окна 21 дня — не шлём
            if await db.asthma_done_today(conn, today):
                return None  # уже ответили сегодня
            return texts.NEUTRAL["asthma_check"], keyboards.asthma_kb()
    finally:
        await conn.close()

    # Прогулки — текст + клавиатура лога.
    if code in ("walk_morning", "walk_evening"):
        return texts.neutral(code), keyboards.walk_kb()
    if code in ("feed_morning", "feed_evening"):
        return texts.neutral("feed"), keyboards.feed_kb()

    # Остальные (nose_task, weekly_review, test) — нейтральный шаблон без кнопок.
    return texts.neutral(code), None
