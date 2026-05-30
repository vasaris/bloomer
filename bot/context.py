"""Сборка персонального контекста о Блумере из БД для Claude (Sprint 7).

Компактный снимок «здесь и сейчас» (адаптация, свежие логи, стрики, этап
трюфелей, соц-прогресс, что пора по здоровью/грумингу, вес, астма) — чтобы ответы
были под текущий момент, а не общая справка. Держим коротко: это префикс к вопросу.
"""
from __future__ import annotations

import datetime as dt

from . import db, gamification as gam
from .modules import m3_grooming as m3
from .modules import m4_health as m4
from .modules import m5_training as m5
from .modules import m6_socialization as m6


def _phase_line(arrived: dt.date | None, today: dt.date) -> str:
    from .modules import m0_adaptation as m0
    n = m0.adaptation_day(arrived, today)
    if n is None:
        return "Адаптация: Блумер ещё не приехал (дата приезда не задана)."
    if n < 1:
        return f"Адаптация: приезжает через {1 - n} дн."
    if n <= m0.ADAPT_LEN:
        return f"Адаптация: день {n}/{m0.ADAPT_LEN} (правило 3-3-3, ещё привыкает)."
    return f"Адаптация пройдена (фаза «дома»), {n}-й день с приезда."


async def build_context(settings, today: dt.date | None = None) -> str:
    today = today or settings.today()
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        if dog is None:
            return "Профиль Блумера ещё не создан."
        dog_id = dog["id"]
        arrived = await db.get_arrived(conn)

        lines: list[str] = ["[Контекст о Блумере на сегодня]"]
        lines.append(_phase_line(arrived, today))

        # Геймификация.
        xp = await db.get_xp(conn, dog_id)
        ws = await db.get_streak(conn, dog_id, "walk")
        ns = await db.get_streak(conn, dog_id, "nose")
        cs = await db.get_streak(conn, dog_id, "command")
        lines.append(f"Уровень: {gam.level_for(xp)} ({xp} XP). Стрики — прогулки {ws}, нюх {ns}, команды {cs}.")

        # Сегодня.
        w = await db.count_events_today(conn, dog_id, "walk", today)
        f = await db.count_events_today(conn, dog_id, "feed", today)
        no = await db.count_events_today(conn, dog_id, "nose", today)
        cm = await db.count_events_today(conn, dog_id, "command", today)
        lines.append(f"Сегодня: прогулок {w}, кормёжек {f}, нюхо-сессий {no}, тренировок команд {cm}.")

        # Прогулки за неделю.
        since = today - dt.timedelta(days=6)
        places = await db.walks_by_place(conn, dog_id, since)
        if places:
            lbl = {"danube": "Дунай", "park": "парк", "yard": "двор"}
            br = ", ".join(f"{lbl.get(p, p)} {n}" for p, n in sorted(places.items(), key=lambda x: -x[1]))
            lines.append(f"Прогулки за 7 дней: {sum(places.values())} ({br}).")

        # Команды: отзыв (приоритет) + слабые места.
        prog = await db.get_command_progress(conn, dog_id)
        if prog:
            recall = prog.get("recall")
            rl = recall["mastery"] if recall else 0
            lines.append(f"Отзыв (recall): уровень {rl}/{m5.MASTERY_MAX} — {m5.MASTERY_LABELS[rl]}.")

        # Трюфель-программа.
        stages = await db.get_truffle_stages(conn, dog_id)
        if stages:
            act = m5.truffle_active(stages)
            if act is None:
                lines.append("Трюфель-программа: все этапы пройдены.")
            else:
                lines.append(f"Трюфель-программа: активен этап {act}/{m5.TRUFFLE_LEN} — {m5.TRUFFLE_STAGES[act][0]}.")
        else:
            lines.append("Трюфель-программа ещё не начата.")

        # Социализация.
        soc = await db.get_soc_progress(conn, dog_id)
        if soc:
            pct = m6.progress_pct(soc)
            weak = [m6.SOC_ITEMS[c][1] for c in m6.SOC_ORDER
                    if (soc.get(c) or {"level": 0})["level"] < m6.CONFIDENT]
            tail = f"; ещё не «спокойно»: {', '.join(weak)}" if weak else ""
            lines.append(f"Социализация: {pct}%{tail}.")

        # Что пора по графику.
        groom_due = await m3.due_codes(conn, dog_id, today)
        if groom_due:
            lines.append("Груминг пора: " + ", ".join(m3.GROOM[c][1] for c in groom_due) + ".")
        health_due = await m4.due_codes(conn, dog_id, today)
        if health_due:
            lines.append("Здоровье пора: " + ", ".join(m4.HEALTH[c][1] for c in health_due) + ".")

        # Вес.
        series = await db.weight_series(conn, dog_id, limit=10)
        if series:
            cur = series[-1][1]
            delta = cur - series[0][1]
            arrow = "→" if abs(delta) < 0.05 else ("↑" if delta > 0 else "↓")
            lines.append(f"Вес: {cur:.1f} кг (тренд {arrow}{abs(delta):.1f}).")

        # Астма Макса — только в окне адаптации.
        from .modules import m0_adaptation as m0
        n = m0.adaptation_day(arrived, today)
        if n is not None and 1 <= n <= m0.ADAPT_LEN:
            tr = await db.asthma_trend(conn, limit=3)
            if tr:
                last = tr[-1]
                lines.append(f"Астма Макса (мониторинг): последний статус — {last['status']}.")
    finally:
        await conn.close()
    return "\n".join(lines)
