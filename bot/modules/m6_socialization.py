"""M6 — Социализация (Sprint 6).

Достраиваем городскую социализацию (BLUMER_SYSTEM §5): машины, шум, лифт,
другие собаки, люди, дети + поездка в машине (мостик к M7). По каждому «новому
опыту» — уровень привыкания 0..3 (его выставляет человек по реальной реакции
Блумера), плюс счётчик отметок. Прогресс-бар = суммарная уверенность по чек-листу.

Принцип — только позитив и постепенность (LIMA): дистанция, лакомство, без
форсажа. Если Блумер насторожился на новизну — увеличиваем дистанцию, не тискаем.

Ачивка «Социальный» 🐕‍🦺 — когда вся базовая городская социализация (city-пункты)
доведена минимум до «спокойно» (уровень ≥ 2).

Отметка опыта = событие type='soc' (+25 XP через logbook → gamification);
«стал увереннее» поднимает уровень и даёт небольшой бонус. Стрика у соц-опыта нет.
"""
from __future__ import annotations

import datetime as dt
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, gamification as gam, keyboards, logbook, texts

router = Router()

# code → (эмодзи, название, city) — city=True входит в базовую городскую соц-ачивку.
SOC_ITEMS: dict[str, tuple[str, str, bool]] = {
    "cars":     ("🚗", "Машины и трафик", True),
    "noise":    ("🔊", "Городской шум", True),
    "elevator": ("🛗", "Лифт", True),
    "dogs":     ("🐕", "Другие собаки", True),
    "people":   ("🧑", "Незнакомые люди", True),
    "kids":     ("👧", "Дети", True),
    "car_ride": ("🚙", "Поездка в машине", False),  # мостик к турам (M7)
}
SOC_ORDER = ["cars", "noise", "elevator", "dogs", "people", "kids", "car_ride"]

LEVEL_MAX = 3
LEVEL_LABELS = {
    0: "не пробовали",
    1: "знакомство (на дистанции)",
    2: "спокойно",
    3: "уверенно",
}
CONFIDENT = 2  # порог «база закрыта» для city-пунктов

SOC_XP_LEVEL = 10  # бонус за поднятый уровень (опыт сам по себе даёт +25 как soc-событие)

# Идея дня — короткое упражнение соц-программы (ротация, как нюхо-игра).
SOC_IDEAS: list[str] = [
    "Посиди с Блумером на лавке у дороги: пусть спокойно смотрит на машины с дистанции. Лакомство за спокойствие.",
    "Зайдите в лифт на 1–2 этажа: угощение за вход и за выход, без принуждения. Коротко и в плюс.",
    "Прогулка в людном месте на комфортной дистанции — наблюдаем людей, не лезем в толпу.",
    "Встреча со спокойной знакомой собакой: параллельная прогулка, без лобового знакомства.",
    "Запиши на телефон городские звуки и включи тихо дома, постепенно громче — десенсибилизация к шуму.",
    "Дай ребёнку угостить Блумера из раскрытой ладони — спокойно, без беготни и тисканья.",
    "Разные поверхности: решётка, мостик, металлический люк — пусть выберет, перейти или обойти.",
    "Короткая сессия в машине без поездки: посидеть, лакомство, выйти. Готовим базу под туры.",
]


def soc_idea_of_day(today: dt.date) -> str:
    return SOC_IDEAS[today.toordinal() % len(SOC_IDEAS)]


def random_idea(exclude: str | None = None) -> str:
    pool = [i for i in SOC_IDEAS if i != exclude] or SOC_IDEAS
    return random.choice(pool)


def _bar(level: int) -> str:
    return "▰" * level + "▱" * (LEVEL_MAX - level)


def progress_pct(prog: dict) -> int:
    """Общий прогресс социализации в % (по сумме уровней всех пунктов)."""
    total = LEVEL_MAX * len(SOC_ORDER)
    have = sum((prog[c]["level"] if c in prog else 0) for c in SOC_ORDER)
    return round(have / total * 100) if total else 0


def city_done(prog: dict) -> bool:
    """Вся базовая городская социализация доведена до «спокойно» (≥2)."""
    city = [c for c in SOC_ORDER if SOC_ITEMS[c][2]]
    return all((prog.get(c) or {"level": 0})["level"] >= CONFIDENT for c in city)


async def check_social_achievement(conn, dog_id: int) -> list[str]:
    """Ачивка «Социальный» при закрытии базовой городской социализации."""
    prog = await db.get_soc_progress(conn, dog_id)
    if city_done(prog):
        return await gam.unlock(conn, dog_id, "social")
    return []


# ── Рендеры ───────────────────────────────────────────────────
def _meter(pct: int) -> str:
    filled = round(pct / 10)
    return "🟩" * filled + "⬜" * (10 - filled)


def render_board(prog: dict, today: dt.date) -> str:
    pct = progress_pct(prog)
    lines = [
        "🐕‍🦺 <b>Социализация</b>",
        f"{_meter(pct)} {pct}%",
        "<i>Тапни пункт, чтобы отметить опыт или поднять уровень.</i>",
    ]
    for code in SOC_ORDER:
        emoji, label, city = SOC_ITEMS[code]
        row = prog.get(code)
        level = row["level"] if row else 0
        sessions = row["sessions"] if row else 0
        star = "" if city else " ✈️"
        lines.append(f"{emoji} <b>{label}</b>{star}\n   {_bar(level)} {LEVEL_LABELS[level]} · {sessions} отм.")
    lines.append(f"\n💡 Идея дня: {soc_idea_of_day(today)}")
    return "\n".join(lines)


def render_item(code: str, prog: dict) -> str:
    emoji, label, city = SOC_ITEMS[code]
    row = prog.get(code)
    level = row["level"] if row else 0
    sessions = row["sessions"] if row else 0
    tag = "базовая городская" if city else "подготовка к поездкам"
    lines = [
        f"{emoji} <b>{label}</b> <i>({tag})</i>",
        f"Уровень: {_bar(level)} <b>{LEVEL_LABELS[level]}</b>",
        f"Отмечено опытов: {sessions}",
    ]
    if level < LEVEL_MAX:
        lines.append(f"\nСледующий уровень: {LEVEL_LABELS[level + 1]}")
        lines.append("Двигаемся только на позитиве: дистанция, лакомство, без форсажа.")
    else:
        lines.append("\nМаксимум — уверенно и спокойно 👍")
    return "\n".join(lines)


# ════════════════════ ХЕНДЛЕРЫ ═════════════════════════════════
@router.message(Command("social"))
async def cmd_social(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_soc_items(conn, dog["id"], SOC_ORDER)
        prog = await db.get_soc_progress(conn, dog["id"])
    finally:
        await conn.close()
    await message.answer(
        render_board(prog, settings.today()),
        reply_markup=keyboards.soc_board_kb(SOC_ORDER, SOC_ITEMS),
    )


@router.callback_query(F.data == "soc:board")
async def on_soc_board(cb: CallbackQuery, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        prog = await db.get_soc_progress(conn, dog["id"])
    finally:
        await conn.close()
    await cb.message.edit_text(
        render_board(prog, settings.today()),
        reply_markup=keyboards.soc_board_kb(SOC_ORDER, SOC_ITEMS),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("soc:"))
async def on_soc_open(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in SOC_ITEMS:  # 'board' перехвачен выше
        await cb.answer()
        return
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_soc_items(conn, dog["id"], SOC_ORDER)
        prog = await db.get_soc_progress(conn, dog["id"])
    finally:
        await conn.close()
    await cb.message.edit_text(
        render_item(code, prog), reply_markup=keyboards.soc_detail_kb(code)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("soclog:"))
async def on_soc_log(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in SOC_ITEMS:
        await cb.answer()
        return
    today = settings.today()
    extra = await logbook.log_and_reward(
        settings, cb.from_user.id, "M6", "soc", {"item": code}, on_date=today
    )
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.bump_soc_session(conn, dog["id"], code, today)
        prog = await db.get_soc_progress(conn, dog["id"])
    finally:
        await conn.close()
    _, label, _ = SOC_ITEMS[code]
    await cb.message.edit_text(
        f"✅ Опыт «{label}» отмечен.\n\n" + render_item(code, prog),
        reply_markup=keyboards.soc_detail_kb(code),
    )
    await cb.answer("Записал 🐕‍🦺")
    for msg in extra:
        await cb.message.answer(msg)


@router.callback_query(F.data.startswith("socup:"))
async def on_soc_up(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in SOC_ITEMS:
        await cb.answer()
        return
    today = settings.today()
    msgs: list[str] = []
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_soc_items(conn, dog["id"], SOC_ORDER)
        prog = await db.get_soc_progress(conn, dog["id"])
        cur = (prog.get(code) or {"level": 0})["level"]
        if cur >= LEVEL_MAX:
            await cb.answer("Уже максимум 👍", show_alert=True)
            return
        new = cur + 1
        await db.set_soc_level(conn, dog["id"], code, new, today)
        _, label, _ = SOC_ITEMS[code]
        msgs.append(texts.BLOOMER_VOICE["soc_level_up"].format(
            label=label, level=LEVEL_LABELS[new]
        ))
        msgs += await gam.award_xp(conn, dog["id"], SOC_XP_LEVEL)
        msgs += await check_social_achievement(conn, dog["id"])
        prog = await db.get_soc_progress(conn, dog["id"])
    finally:
        await conn.close()
    await cb.message.edit_text(
        render_item(code, prog), reply_markup=keyboards.soc_detail_kb(code)
    )
    await cb.answer("Уровень поднят ⬆️")
    for msg in msgs:
        await cb.message.answer(msg)
