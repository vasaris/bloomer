"""Базовые хендлеры Sprint 0: /start, /help, /profile, /ping."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from .. import db, reports, texts
from ..config import Settings
from ..scheduler import PushService

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, settings: Settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        await db.upsert_user(
            conn,
            tg_chat_id=message.chat.id,
            name=message.from_user.full_name if message.from_user else None,
        )
    finally:
        await conn.close()
    await message.answer(texts.START.format(dog=texts.DOG_NAME))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP.format(dog=texts.DOG_NAME))


@router.message(Command("profile"))
async def cmd_profile(message: Message, settings: Settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
    finally:
        await conn.close()

    if dog is None:
        await message.answer("Профиль ещё не создан. Нажми /start.")
        return

    await message.answer(
        texts.PROFILE.format(
            name=dog["name"],
            breed=dog["breed"] or "—",
            neutered="да" if dog["neutered"] else "нет / планируется",
            breeder=dog["breeder_contact"] or "Ideal Dale (Горан Каранович)",
        ),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("ping"))
async def cmd_ping(message: Message, push: PushService) -> None:
    """Принудительно отправить тестовый пуш (минуя тихие часы)."""
    await push.send("test", force=True)


@router.message(Command("today"))
async def cmd_today(message: Message, settings: Settings) -> None:
    """Утренний бриф по запросу."""
    built = await reports.build_push("morning_brief", settings)
    if built:
        text, markup = built
        await message.answer(text, reply_markup=markup)
