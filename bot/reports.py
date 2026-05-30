"""Сборка текстов пушей из БД: утренний бриф, итог дня, астма-чек.

Держим логику здесь, чтобы scheduler оставался тонким. build_push() возвращает
(text, keyboard) либо None, если пуш сегодня не нужен (напр. астма вне окна 21 дня).
"""
from __future__ import annotations

import datetime as dt

from aiogram.types import InlineKeyboardMarkup

from . import db, gamification as gam, keyboards, texts, weather
from .config import Settings
from .modules import m0_adaptation as m0
from .modules import m3_grooming as m3
from .modules import m4_health as m4
from .modules import m5_training as m5
from .modules import m6_socialization as m6

# Пуши, которые молчат, пока Блумер не приехал (arrived ещё не наступил).
# Утренний бриф намеренно НЕ здесь — он остаётся единственным голосом до приезда
# (короткий, с отсчётом и подсказкой /arrived). «test» тоже не глушим — это /ping.
_PRE_ARRIVAL_SILENT = frozenset({
    "walk_morning", "walk_evening", "feed_morning", "feed_evening",
    "nose_task", "groom_check", "health_check", "asthma_check",
    "day_summary", "weekly_review",
})


async def _morning_brief(conn, settings: Settings, today: dt.date) -> tuple[str, InlineKeyboardMarkup | None]:
    arrived = await db.get_arrived(conn)
    n = m0.adaptation_day(arrived, today)

    # До приезда Блумера — короткий бриф без распорядка (кормить/гулять некого).
    # Остальные пуши в этот период подавлены (см. _PRE_ARRIVAL_SILENT).
    if n is None:
        return (
            "☀️ <b>Утренний бриф</b>\n"
            "• Блумер ещё не у нас. Отметь дату приезда — /arrived (в день приезда) "
            "или /arrived ГГГГ-ММ-ДД. От неё включится весь распорядок и напоминания."
        ), None
    if n < 1:
        return (
            "☀️ <b>Утренний бриф</b>\n"
            f"• До приезда Блумера {1 - n} дн. Пока готовим базу: место с тряпкой от Горана, "
            f"миски, маршрут к Дунаю, HEPA в комнате Макса. Полный распорядок включится в день приезда."
        ), None

    lines = ["☀️ <b>Утренний бриф</b>"]

    # Проверка жары перед утренней прогулкой (Sprint 6). Молчим, когда прохладно.
    w = await weather.fetch_weather(settings.latitude, settings.longitude)
    advice = weather.heat_advice(w)
    if advice is not None:
        lines.append("• " + advice[1])

    in_window = 1 <= n <= m0.ADAPT_LEN
    if in_window:
        lines.append(f"• Адаптация, день {n}/{m0.ADAPT_LEN}: {m0.day_card(n)}")
    # после 21 дня адаптацию в бриф не тащим — фаза «дома»

    lines.append("• Прогулка утром и вечером (отметишь по кнопке на пуше).")
    lines.append("• Кормёжка по графику ×2.")
    dog = await db.get_dog(conn)
    if dog is not None:
        xp = await db.get_xp(conn, dog["id"])
        game_title, _ = m5.game_of_day(today, xp)
        lines.append(f"• 👃 Нюхо-игра дня: <b>{game_title}</b> (/nose).")
        due = await m4.due_codes(conn, dog["id"], today)
        if due:
            labels = ", ".join(m4.HEALTH[c][1] for c in due)
            lines.append(f"• 🩺 По здоровью пора: {labels} (/health).")
    lines.append("• 🎯 Тренинг: отзыв — приоритет (/train).")
    lines.append(f"• 🐕‍🦺 Социализация дня: {m6.soc_idea_of_day(today)} (/social).")
    if in_window:
        lines.append("• Вечером — астма-чек Макса.")
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


async def _weekly_review(
    conn, settings: Settings, today: dt.date
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Недельный обзор: прогресс за 7 дней, стрики (+заморозки), что подтянуть."""
    dog = await db.get_dog(conn)
    dog_id = dog["id"]
    start = today - dt.timedelta(days=6)  # окно из 7 дней, включая сегодня

    counts = await db.count_by_type_range(conn, dog_id, start, today)
    walks = counts.get("walk", 0)
    noses = counts.get("nose", 0)
    cmds = counts.get("command", 0)
    feeds = counts.get("feed", 0)
    grooms = counts.get("groom", 0)
    socs = counts.get("soc", 0)
    trips = counts.get("trip", 0)

    # XP за неделю — из событий окна (леджера XP нет, считаем stateless).
    xp_week = sum(counts.get(t, 0) * gam.XP_PER_EVENT.get(t, 0) for t in counts)
    xp_total = await db.get_xp(conn, dog_id)

    # Дни недели с выполненной нормой прогулок (≥ WALKS_PER_DAY).
    walk_days = await db.daily_event_counts(conn, dog_id, "walk", start, today)
    good_walk_days = sum(1 for c in walk_days.values() if c >= gam.WALKS_PER_DAY)

    rng = f"{start.strftime('%d.%m')}–{today.strftime('%d.%m')}"
    lines = [f"🗓 <b>Недельный обзор</b> ({rng})"]

    # Активность.
    places = await db.walks_by_place(conn, dog_id, start)
    plabel = {"danube": "🌊 Дунай", "park": "🌳 парк", "yard": "🏘 двор"}
    if places:
        br = " · ".join(f"{plabel.get(p, p)} {n}" for p, n in sorted(places.items(), key=lambda x: -x[1]))
        lines.append(f"🚶 Прогулок: <b>{walks}</b> ({br}); норма ×{gam.WALKS_PER_DAY} — {good_walk_days}/7 дн.")
    else:
        lines.append(f"🚶 Прогулок: <b>{walks}</b>")
    extra = []
    if noses:
        extra.append(f"👃 нюх {noses}")
    if cmds:
        extra.append(f"🧠 команды {cmds}")
    if feeds:
        extra.append(f"🍽 кормёжки {feeds}")
    if grooms:
        extra.append(f"🪥 груминг {grooms}")
    if socs:
        extra.append(f"🐕‍🦺 соц-опыт {socs}")
    if trips:
        extra.append(f"🚗 выезды {trips}")
    if extra:
        lines.append("• " + " · ".join(extra))

    # Трюфель / социализация / вес — текущее состояние.
    tstages = await db.get_truffle_stages(conn, dog_id)
    active = m5.truffle_active(tstages) if tstages else None
    if active is not None:
        lines.append(f"🍄 Трюфель: этап {active}/{m5.TRUFFLE_LEN} — {m5.TRUFFLE_STAGES[active][0]}")
    soc = await db.get_soc_progress(conn, dog_id)
    if soc:
        lines.append(f"🐕‍🦺 Социализация: {m6.progress_pct(soc)}%")
    series = await db.weight_series(conn, dog_id, limit=10)
    if series:
        cur_w = series[-1][1]
        delta = cur_w - series[0][1]
        arrow = "→" if abs(delta) < 0.05 else ("↑" if delta > 0 else "↓")
        lines.append(f"⚖️ Вес: {cur_w:.1f} кг (тренд {arrow}{abs(delta):.1f})")

    # Стрики + заморозки (видимость заморозок, Sprint 8).
    st = await db.get_streaks_summary(conn, dog_id, ["walk", "nose", "command"])
    lines.append(
        f"\n🔥 <b>Стрики</b> (рекорд · 🧊 заморозок):\n"
        f"🚶 {st['walk']['current']} (рек. {st['walk']['best']} · 🧊 {st['walk']['freezes_left']})  "
        f"👃 {st['nose']['current']} (рек. {st['nose']['best']} · 🧊 {st['nose']['freezes_left']})  "
        f"🧠 {st['command']['current']} (рек. {st['command']['best']} · 🧊 {st['command']['freezes_left']})"
    )
    lines.append(f"⭐ {gam.level_for(xp_total)} · +{xp_week} XP за неделю (всего {xp_total})")

    # Ачивки за неделю.
    unlocked = await db.achievements_since(conn, dog_id, start)
    if unlocked:
        lines.append("\n🏅 <b>Открыто за неделю:</b>")
        for c in unlocked:
            lines.append("• " + gam.ach_title(c))

    # Что подтянуть (максимум 3 пункта).
    todo: list[str] = []
    prog = await db.get_command_progress(conn, dog_id)
    if prog:
        recall = prog.get("recall")
        rl = recall["mastery"] if recall else 0
        if rl < m5.MASTERY_MAX:
            todo.append(f"🎯 Отзыв (recall): {rl}/{m5.MASTERY_MAX} — приоритет, строим медленно и в плюс")
    if good_walk_days < 7:
        todo.append(f"🚶 Норма ×{gam.WALKS_PER_DAY} прогулок была не каждый день ({good_walk_days}/7)")
    if soc:
        weak = [m6.SOC_ITEMS[c][1] for c in m6.SOC_ORDER
                if (soc.get(c) or {"level": 0})["level"] < m6.CONFIDENT]
        if weak:
            todo.append("🐕‍🦺 Ещё не «спокойно»: " + ", ".join(weak[:4]))
    groom_due = await m3.due_codes(conn, dog_id, today)
    if groom_due:
        todo.append("🪥 Груминг пора: " + ", ".join(m3.GROOM[c][1] for c in groom_due))
    health_due = await m4.due_codes(conn, dog_id, today)
    if health_due:
        todo.append("🩺 Здоровье пора: " + ", ".join(m4.HEALTH[c][1] for c in health_due))

    if todo:
        lines.append("\n📌 <b>Что подтянуть:</b>")
        for t in todo[:3]:
            lines.append("• " + t)
    else:
        lines.append("\n📌 Всё по плану — держим темп 🐾")

    return "\n".join(lines), None


async def build_push(
    code: str, settings: Settings, today: dt.date | None = None
) -> tuple[str, InlineKeyboardMarkup | None] | None:
    """Возвращает (text, keyboard) или None, если пуш сегодня пропускаем."""
    today = today or settings.today()
    conn = await db.connect(settings.db_path)
    try:
        # Пока Блумер не приехал — глушим все операционные пуши (кормёжка/прогулка/
        # нюхо/груминг/здоровье/астма/итоги): собаки ещё нет, напоминания = шум.
        # Говорит только утренний бриф (короткий, с обратным отсчётом до приезда).
        arrived = await db.get_arrived(conn)
        n = m0.adaptation_day(arrived, today)
        arrived_yet = n is not None and n >= 1
        if not arrived_yet and code in _PRE_ARRIVAL_SILENT:
            return None

        if code == "morning_brief":
            return await _morning_brief(conn, settings, today)
        if code == "day_summary":
            return await _day_summary(conn, today)
        if code == "weekly_review":
            return await _weekly_review(conn, settings, today)
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
        if code == "health_check":
            dog = await db.get_dog(conn)
            due = await m4.due_codes(conn, dog["id"], today)
            if not due:
                return None  # ничего не пора — не шумим
            lines = ["🩺 <b>Здоровье — сегодня по графику</b>"]
            for c in due:
                emoji, label, _, note = m4.HEALTH[c]
                lines.append(f"{emoji} {label} — {note}")
            return "\n".join(lines), keyboards.health_kb()
    finally:
        await conn.close()

    # Прогулки — текст + клавиатура лога.
    if code in ("walk_morning", "walk_evening"):
        return texts.neutral(code), keyboards.walk_kb()
    if code in ("feed_morning", "feed_evening"):
        return texts.neutral("feed"), keyboards.feed_kb()

    # Остальные (nose_task, weekly_review, test) — нейтральный шаблон без кнопок.
    return texts.neutral(code), None
