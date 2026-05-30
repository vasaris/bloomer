"""M7 — Путешествия и винные туры (Sprint 6).

Два блока (BLUMER_SYSTEM §5, §M7):
  • Проверка жары перед выездом — погодное API (bot/weather.py). Лето + Балканы:
    +30 и выше → только утро/вечер, тень, вода, НИКОГДА не оставлять в машине.
  • Чек-лист подготовки к туру — собираемся в один тап (вода, тень, обработка от
    клещей перед Фрушка-Горой/лесом, корм, документы, набор для нюхо-работы).

«Поехали (спокойно)» логирует событие type='trip' (+20 XP) и на первом выезде
даёт ачивку «Путешественник» 🚗. Туры — поле для нюховой/трюфельной работы и
связка с винными маршрутами BalkanOutdoor.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, gamification as gam, keyboards, logbook, texts, weather

router = Router()

# code → (эмодзи, короткая подпись). Порядок = порядок в чек-листе.
TRIP_ITEMS: dict[str, tuple[str, str]] = {
    "water":     ("💧", "Вода + складная миска"),
    "shade":     ("⛱", "План от жары: тень, не в машине"),
    "tick":      ("🕷", "Обработка от клещей актуальна"),
    "leash":     ("🦮", "Поводок/шлейка, адресник"),
    "food":      ("🍖", "Корм/лакомства на день"),
    "towel":     ("🧺", "Полотенце/подстилка в машину"),
    "poop":      ("🛍", "Пакеты для уборки"),
    "nose_kit":  ("🍄", "Набор для нюхо-работы (мостик к трюфелям)"),
    "vet_doc":   ("📇", "Документы + контакт местного вета"),
}
TRIP_ORDER = list(TRIP_ITEMS.keys())


async def _weather_line(settings) -> str:
    w = await weather.fetch_weather(settings.latitude, settings.longitude)
    return weather.heat_line_always(w)


def render_trip(checklist: dict[str, bool], weather_line: str) -> str:
    done = sum(1 for c in TRIP_ORDER if checklist.get(c))
    lines = [
        "🚗 <b>Подготовка к туру</b>",
        weather_line,
        f"\nЧек-лист: {done}/{len(TRIP_ORDER)} готово",
        "<i>Тапни пункт — отметить. Потом «Поехали».</i>",
    ]
    return "\n".join(lines)


# ════════════════════ ХЕНДЛЕРЫ ═════════════════════════════════
@router.message(Command("trip"))
async def cmd_trip(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_trip_items(conn, dog["id"], TRIP_ORDER)
        checklist = await db.get_trip_checklist(conn, dog["id"])
    finally:
        await conn.close()
    wline = await _weather_line(settings)
    await message.answer(
        render_trip(checklist, wline),
        reply_markup=keyboards.trip_kb(checklist, TRIP_ITEMS),
    )


@router.callback_query(F.data.startswith("trip:toggle:"))
async def on_trip_toggle(cb: CallbackQuery, settings) -> None:
    code = cb.data.rsplit(":", 1)[1]
    if code not in TRIP_ITEMS:
        await cb.answer()
        return
    today = settings.today()
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.toggle_trip_item(conn, dog["id"], code, today)
        checklist = await db.get_trip_checklist(conn, dog["id"])
    finally:
        await conn.close()
    wline = await _weather_line(settings)
    await cb.message.edit_text(
        render_trip(checklist, wline),
        reply_markup=keyboards.trip_kb(checklist, TRIP_ITEMS),
    )
    await cb.answer()


@router.callback_query(F.data == "trip:reset")
async def on_trip_reset(cb: CallbackQuery, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.reset_trip_checklist(conn, dog["id"])
        checklist = await db.get_trip_checklist(conn, dog["id"])
    finally:
        await conn.close()
    wline = await _weather_line(settings)
    await cb.message.edit_text(
        render_trip(checklist, wline),
        reply_markup=keyboards.trip_kb(checklist, TRIP_ITEMS),
    )
    await cb.answer("Сбросил чек-лист")


@router.callback_query(F.data == "trip:go")
async def on_trip_go(cb: CallbackQuery, settings) -> None:
    today = settings.today()
    # Какие пункты остались неотмеченными — мягко напомним (не блокируем выезд).
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        checklist = await db.get_trip_checklist(conn, dog["id"])
    finally:
        await conn.close()
    missing = [TRIP_ITEMS[c][1] for c in TRIP_ORDER if not checklist.get(c)]

    extra = await logbook.log_and_reward(
        settings, cb.from_user.id, "M7", "trip", {"calm": True}, on_date=today
    )
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        trips = await db.count_events_type(conn, dog["id"], "trip")
        if trips == 1:  # первый выезд → «Путешественник»
            extra = list(extra) + await gam.unlock(conn, dog["id"], "traveler")
        await db.reset_trip_checklist(conn, dog["id"])
    finally:
        await conn.close()

    head = texts.BLOOMER_VOICE["trip_go"]
    if missing:
        head += "\n\n⚠️ Не отмечено: " + ", ".join(missing) + " — глянь, всё ли взяли."
    await cb.message.edit_text(head)
    await cb.answer("Хорошей дороги 🚗")
    for msg in extra:
        await cb.message.answer(msg)


@router.message(Command("weather"))
async def cmd_weather(message: Message, settings) -> None:
    """Быстрая проверка жары по локации (по умолчанию Нови-Сад)."""
    w = await weather.fetch_weather(settings.latitude, settings.longitude)
    await message.answer("🌍 <b>Погода / жара</b>\n" + weather.heat_line_always(w))
