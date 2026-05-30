"""Логирование в один тап: прогулки, кормёжка, нюхо-тренинг.

Кнопки приходят на пушах (walk_kb/feed_kb) и через /log. Тап → запись в
event_log → начисление XP/стриков/ачивок (gamification) → правка сообщения
на подтверждение + праздничные сообщения голосом Блумера, если что-то открылось.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, gamification, keyboards, texts

router = Router()


async def _dog_and_user(settings, chat_id: int):
    conn = await db.connect(settings.db_path)
    dog = await db.get_dog(conn)
    uid = await db.user_id_by_chat(conn, chat_id)
    return conn, dog, uid


async def _log_and_reward(settings, chat_id, module, type_, payload=None):
    """Запись события + геймификация. Возвращает список праздничных сообщений."""
    today = settings.today()
    conn, dog, uid = await _dog_and_user(settings, chat_id)
    try:
        await db.log_event(conn, dog["id"], module, type_, today, user_id=uid, payload=payload)
        return await gamification.on_event(conn, dog["id"], type_, today)
    finally:
        await conn.close()


@router.message(Command("log"))
async def cmd_log(message: Message) -> None:
    await message.answer(texts.LOG_MENU, reply_markup=keyboards.log_menu_kb())


@router.callback_query(F.data == "logmenu:walk")
async def logmenu_walk(cb: CallbackQuery) -> None:
    await cb.message.edit_text("🚶 Где гуляли?", reply_markup=keyboards.walk_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("walk:"))
async def on_walk(cb: CallbackQuery, settings) -> None:
    place = cb.data.split(":", 1)[1]  # danube | park | yard
    extra = await _log_and_reward(settings, cb.from_user.id, "M2", "walk", {"place": place})
    await cb.message.edit_text(texts.WALK_LOGGED.get(place, "🚶 Прогулка записана."))
    await cb.answer("Записал 🐾")
    for msg in extra:
        await cb.message.answer(msg)


@router.callback_query(F.data == "feed:done")
async def on_feed(cb: CallbackQuery, settings) -> None:
    await _log_and_reward(settings, cb.from_user.id, "M1", "feed")  # XP за кормёжку не начисляем
    await cb.message.edit_text(texts.FEED_LOGGED)
    await cb.answer("Записал 🍽")


@router.callback_query(F.data == "nose:done")
async def on_nose(cb: CallbackQuery, settings) -> None:
    extra = await _log_and_reward(settings, cb.from_user.id, "M5", "nose")
    await cb.message.edit_text(texts.NOSE_LOGGED)
    await cb.answer("Записал 👃")
    for msg in extra:
        await cb.message.answer(msg)


@router.callback_query(F.data.startswith("snooze:"))
async def on_snooze(cb: CallbackQuery, push) -> None:
    """Отложить пуш на час (повторно придёт с теми же кнопками)."""
    what = cb.data.split(":", 1)[1]  # walk | feed
    code = "walk_morning" if what == "walk" else "feed_morning"
    await push.snooze(code, minutes=60)
    await cb.message.edit_text("⏰ Отложил на час.")
    await cb.answer()
