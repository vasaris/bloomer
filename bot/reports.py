"""Сборка текстов пушей из БД: утренний бриф, итог дня, астма-чек.

Держим логику здесь, чтобы scheduler оставался тонким. build_push() возвращает
(text, keyboard) либо None, если пуш сегодня не нужен (напр. астма вне окна 21 дня).
"""
from __future__ import annotations

import datetime as dt

from aiogram.types import InlineKeyboardMarkup

from . import db, gamification as gam, keyboards, texts
from .config import Settings
from .modules import m0_adaptation as m0
from .modules import m3_grooming as m3
from .modules import m5_training as m5


async def _morning_brief(conn, today: dt.date) -> tuple[str, InlineKeyboardMarkup | None]:
    arrived = await db.get_arrived(conn)
    lines = ["☀️ <b>Утренний бриф</b>"]

    n = m0.adaptation_day(arrived, today)
    in_window = n is not None and 1 <= n <= m0.ADAPT_LEN
    if n is None:
        lines.append("• Дата приезда не задана — отметь командой /arrived.")
    elif n < 1:
        lines.append(f"• Блумер приезжает через {1 - n} дн. — адаптация ещё не началась.")
    elif in_window:
        lines.append(f"• Адаптация, день {n}/{m0.ADAPT_LEN}: {m0.day_card(n)}")
    # после 21 дня адаптацию в бриф не тащим — фаза «дома»

    lines.append("• Прогулка утром и вечером (отметишь по кнопке на пуше).")
    lines.append("• Кормёжка по графику ×2.")
    dog = await db.get_dog(conn)
    if dog is not None:
        xp = await db.get_xp(conn, dog["id"])
        game_title, _ = m5.game_of_day(today, xp)
        lines.append(f"• 👃 Нюхо-игра дня: <b>{game_title}</b> (/nose).")
    lines.append("• 🎯 Тренинг: отзыв — приоритет (/train).")
    if in_window:
        lines.append("• Вечером — астма-чек Макса.")
    # TODO Sprint 6: проверка жары (погодное API) перед утренней прогулкой.
    return "\n".join(lines), None


async def _day_summary(conn, today: dt.date) -> tuple[str, InlineKeyboardMarkup | None]:
    dog = await db.get_dog(conn)
    dog_id = dog["id"]
    walks = await db.count_events_today(conn, dog_id, "walk", today)
    feeds = await db.count_events_today(conn, dog_id, "feed", today)
    noses = await db.count_events_today(conn, dog_id, "nose", today)
    cmds = await db.count_events_today(conn, dog_id, "command", today)
    asthma_done = await db.asthma_done_today(conn, today)
    arrived = await db.get_arrived(conn)
    n = m0.adaptation_day(arrived, today)
    in_window = n is not None and 1 <= n <= m0.ADAPT_LEN

    walk_streak = await db.get_streak(conn, dog_id, "walk")
    nose_streak = await db.get_streak(conn, dog_id, "nose")
    cmd_streak = await db.get_streak(conn, dog_id, "command")
    xp = await db.get_xp(conn, dog_id)

    lines = ["🌙 <b>Итог дня</b>"]
    lines.append(f"🚶 Прогулок: {walks}" + (" ✓" if walks >= gam.WALKS_PER_DAY else ""))
    lines.append(f"🍽 Кормёжек: {feeds}")
    if noses:
        lines.append(f"👃 Нюхо-тренинг: {noses}")
    if cmds:
        lines.append(f"🧠 Тренировок команд: {cmds}")
    if in_window:
        lines.append(f"🫁 Астма-чек: {'✓' if asthma_done else '— не отмечен'}")

    tstages = await db.get_truffle_stages(conn, dog_id)
    active = m5.truffle_active(tstages) if tstages else None
    if active is not None:
        lines.append(f"🍄 Трюфель: этап {active}/{m5.TRUFFLE_LEN} — {m5.TRUFFLE_STAGES[active][0]}")

    lines.append(
        f"\n🔥 Стрики — 🚶 {walk_streak} · 👃 {nose_streak} · 🧠 {cmd_streak} | "
        f"{gam.level_for(xp)}, {xp} XP"
    )

    # Ачивка «Дома» (день 21) — проверяем здесь, раз в день.
    home_msgs = await gam.check_home_achievement(conn, dog_id, n)

    # Персона C: голос Блумера в удачный день (норма прогулок + еда + астма).
    done_ok = walks >= gam.WALKS_PER_DAY and feeds >= 1 and (asthma_done or not in_window)
    if done_ok:
        lines.append("\n" + texts.BLOOMER_VOICE["good_day"])
    for m in home_msgs:
        lines.append("\n" + m)
    return "\n".join(lines), None


async def build_push(
    code: str, settings: Settings, today: dt.date | None = None
) -> tuple[str, InlineKeyboardMarkup | None] | None:
    """Возвращает (text, keyboard) или None, если пуш сегодня пропускаем."""
    today = today or settings.today()
    conn = await db.connect(settings.db_path)
    try:
        if code == "morning_brief":
            return await _morning_brief(conn, today)
        if code == "day_summary":
            return await _day_summary(conn, today)
        if code == "asthma_check":
            arrived = await db.get_arrived(conn)
            n = m0.adaptation_day(arrived, today)
            if n is None or n < 1 or n > m0.ADAPT_LEN:
                return None  # до приезда или вне окна 21 дня — не шлём
            if await db.asthma_done_today(conn, today):
                return None  # уже ответили сегодня
            return texts.NEUTRAL["asthma_check"], keyboards.asthma_kb()
        if code == "groom_check":
            dog = await db.get_dog(conn)
            due = await m3.due_codes(conn, dog["id"], today)
            if not due:
                return None  # ничего не пора — не шумим
            lines = ["🧼 <b>Груминг сегодня</b>"]
            for c in due:
                emoji, label, _, note = m3.GROOM[c]
                lines.append(f"{emoji} {label} — {note}")
            return "\n".join(lines), keyboards.groom_kb()
        if code == "nose_task":
            dog = await db.get_dog(conn)
            xp = await db.get_xp(conn, dog["id"])
            title, desc = m5.game_of_day(today, xp)
            return m5.nose_game_text(title, desc), keyboards.nose_kb()
    finally:
        await conn.close()

    # Прогулки — текст + клавиатура лога.
    if code in ("walk_morning", "walk_evening"):
        return texts.neutral(code), keyboards.walk_kb()
    if code in ("feed_morning", "feed_evening"):
        return texts.neutral("feed"), keyboards.feed_kb()

    # Остальные (nose_task, weekly_review, test) — нейтральный шаблон без кнопок.
    return texts.neutral(code), None
