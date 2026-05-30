"""Логирование в один тап: прогулки и кормёжка.

Кнопки приходят на пушах (walk_kb/feed_kb) и через /log. Тап → запись в
event_log → правка сообщения на подтверждение (чтобы не плодить чат).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, keyboards, texts

router = Router()

_PLACE_MODULE = "M2"  # прогулки относятся к модулю активности


async def _dog_and_user(settings, chat_id: int):
    conn = await db.connect(settings.db_path)
    dog = await db.get_dog(conn)
    uid = await db.user_id_by_chat(conn, chat_id)
    return conn, dog, uid


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
    conn, dog, uid = await _dog_and_user(settings, cb.from_user.id)
    try:
        await db.log_event(
            conn, dog["id"], _PLACE_MODULE, "walk", user_id=uid, payload={"place": place}
        )
    finally:
        await conn.close()
    await cb.message.edit_text(texts.WALK_LOGGED.get(place, "🚶 Прогулка записана."))
    await cb.answer("Записал 🐾")


@router.callback_query(F.data == "feed:done")
async def on_feed(cb: CallbackQuery, settings) -> None:
    conn, dog, uid = await _dog_and_user(settings, cb.from_user.id)
    try:
        await db.log_event(conn, dog["id"], "M1", "feed", user_id=uid)
    finally:
        await conn.close()
    await cb.message.edit_text(texts.FEED_LOGGED)
    await cb.answer("Записал 🍽")
