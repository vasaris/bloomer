"""M4 — Здоровье и ветеринария (Sprint 5).

Процедуры по графику (BLUMER_SYSTEM.md §4): прививки, бешенство, обработка от
клещей (критично после Дуная/леса), глистогонное, плановый осмотр у вета.
Последняя дата каждой берётся из журнала (event_log, type='health', payload.kind) —
тот же «один источник правды», что и в груминге (M3). «Пора» = прошло ≥ интервала.
Отметка пишется в журнал и даёт +10 XP (через logbook → gamification).

Вес — тайм-серия в health_metric, тренд текстовым спарклайном (без зависимостей).

ВАЖНО (см. §7 системной инструкции): бот НЕ назначает препараты/дозы и НЕ ставит
диагнозы. Только напоминания по графику и «к вету». Кастрация — advisory, сроки с ветом.
"""
from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from .. import db, gamification as gam, keyboards, logbook

router = Router()

# code → (эмодзи, название, интервал в днях, заметка). Все по графику (interval != None).
HEALTH: dict[str, tuple[str, str, int, str]] = {
    "vet":     ("🩺", "Плановый осмотр у вета", 365,
                "ежегодно; первичный независимый осмотр — в первую неделю"),
    "vaccine": ("💉", "Комплексная прививка", 365, "ежегодно, по графику вета"),
    "rabies":  ("💉", "Бешенство", 365, "ежегодно"),
    "tick":    ("🕷", "Обработка от клещей/блох", 30,
                "в сезон ежемесячно; критично после Дуная и леса"),
    "deworm":  ("🪱", "Глистогонное", 90, "раз в ~3 месяца, по схеме вета"),
}
HEALTH_ORDER = ["vet", "vaccine", "rabies", "tick", "deworm"]

NEUTER_NOTE = (
    "✂️ <b>Кастрация</b> — обсуди сроки с ветом (оптимально 14–18 мес). "
    "Бот не назначает — это решение и сроки за ветом."
)

WEIGHT_NOTE = "⚖️ Лаготто склонны полнеть при недоборе движения — держим вес под контролем."


def status_line(kind: str, last: dt.date | None, today: dt.date) -> tuple[bool, str]:
    """(пора_ли, строка статуса) — зеркало m3_grooming.status_line."""
    emoji, label, interval, _ = HEALTH[kind]
    if last is None:
        return True, f"{emoji} <b>{label}</b> — не отмечено, заведи дату."
    days = (today - last).days
    if days >= interval:
        return True, f"{emoji} <b>{label}</b> — пора (прошло {days} дн.)."
    return False, f"{emoji} {label} — ок, через {interval - days} дн."


async def _all_status(conn, dog_id: int, today: dt.date) -> list[tuple[str, bool, str]]:
    out = []
    for code in HEALTH_ORDER:
        last = await db.last_health(conn, dog_id, code)
        due, line = status_line(code, last, today)
        out.append((code, due, line))
    return out


async def due_codes(conn, dog_id: int, today: dt.date) -> list[str]:
    return [c for c, due, _ in await _all_status(conn, dog_id, today) if due]


async def check_baseline(conn, dog_id: int, today: dt.date) -> list[str]:
    """Ачивка «Здоровяк»: все процедуры заведены и ни одна не просрочена.

    Заметка о честности: спека описывала строже — «год без пропусков».
    Это требует годовой истории; здесь — осмысленный прокси «база здоровья
    заведена и по графику». Ужесточение до годовой проверки — кандидат в Sprint 8.
    """
    statuses = await _all_status(conn, dog_id, today)
    if all(not due for _, due, _ in statuses):  # ни одна не «пора» → всё по графику
        return await gam.unlock(conn, dog_id, "health_baseline")
    return []


# ── Вес: текстовый спарклайн (без matplotlib — рендерится везде) ──
_BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return _BLOCKS[0] * len(values)
    return "".join(
        _BLOCKS[int((v - lo) / (hi - lo) * (len(_BLOCKS) - 1))] for v in values
    )


def render_weight(series: list[tuple[str, float]]) -> str:
    if not series:
        return ("⚖️ <b>Вес</b> — пока нет замеров.\n"
                "Запиши: <code>/weight 12.4</code> (кг).\n" + WEIGHT_NOTE)
    values = [v for _, v in series]
    cur = values[-1]
    first = values[0]
    delta = cur - first
    arrow = "→" if abs(delta) < 0.05 else ("↑" if delta > 0 else "↓")
    lines = [
        "⚖️ <b>Вес</b>",
        f"Сейчас: <b>{cur:.1f} кг</b> · мин {min(values):.1f} · макс {max(values):.1f}",
    ]
    if len(values) > 1:
        lines.append(f"С первого замера: {arrow} {delta:+.1f} кг")
        lines.append(f"<code>{sparkline(values)}</code>  ({len(values)} замеров)")
    lines.append(WEIGHT_NOTE)
    return "\n".join(lines)


# ════════════════════ ХЕНДЛЕРЫ ═════════════════════════════════
@router.message(Command("health"))
async def cmd_health(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        rows = await _all_status(conn, dog["id"], settings.today())
        series = await db.weight_series(conn, dog["id"], limit=1)
    finally:
        await conn.close()
    lines = ["🩺 <b>Здоровье</b>"]
    lines += [line for _, _, line in rows]
    lines.append("")
    if series:
        lines.append(f"⚖️ Вес: {series[-1][1]:.1f} кг (тренд — /weight)")
    else:
        lines.append("⚖️ Вес ещё не записан — /weight 12.4")
    lines.append(NEUTER_NOTE)
    await message.answer("\n".join(lines), reply_markup=keyboards.health_kb())


@router.callback_query(F.data.startswith("health:"))
async def on_health(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in HEALTH:
        await cb.answer()
        return
    today = settings.today()
    extra = await logbook.log_and_reward(
        settings, cb.from_user.id, "M4", "health", {"kind": code}, on_date=today
    )
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        extra += await check_baseline(conn, dog["id"], today)
    finally:
        await conn.close()
    emoji, label, _, _ = HEALTH[code]
    await cb.message.edit_text(f"{emoji} {label} — отмечено {today.isoformat()}. Таймер сброшен.")
    await cb.answer("Записал 🩺")
    for msg in extra:
        await cb.message.answer(msg)


@router.message(Command("weight"))
async def cmd_weight(message: Message, command: CommandObject, settings) -> None:
    arg = (command.args or "").strip().replace(",", ".")
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        if not arg:  # без аргумента — показать тренд
            series = await db.weight_series(conn, dog["id"], limit=30)
            await message.answer(render_weight(series))
            return
        try:
            value = float(arg)
        except ValueError:
            await message.answer("Не понял вес. Пример: <code>/weight 12.4</code> (кг).")
            return
        if not (0.5 <= value <= 80):
            await message.answer("Похоже на опечатку — вес собаки в кг. Пример: <code>/weight 12.4</code>.")
            return
        await db.log_weight(conn, dog["id"], value, settings.today())
        series = await db.weight_series(conn, dog["id"], limit=30)
    finally:
        await conn.close()
    extra = await logbook.log_and_reward(
        settings, message.chat.id, "M4", "health", {"metric": "weight", "value": value}
    )
    await message.answer(f"⚖️ Записал вес: <b>{value:.1f} кг</b>.\n\n" + render_weight(series))
    for msg in extra:
        await message.answer(msg)
