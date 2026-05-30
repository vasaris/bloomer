"""Базовые хендлеры: /start, /help, /profile, /ping, /today, /stats, /walks."""
from __future__ import annotations

import datetime as dt

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from .. import db, gamification, reports, texts
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


@router.message(Command("backup"))
async def cmd_backup(message: Message, push: PushService, bot: Bot) -> None:
    """Сделать бэкап БД сейчас и прислать файл сюда (офсайт-копия по запросу)."""
    await message.answer("🗄 Делаю бэкап БД…")
    try:
        path = await push.make_backup()
    except Exception as e:  # noqa: BLE001 — показываем причину, не падаем
        await message.answer(f"⚠️ Не удалось сделать бэкап: {e}")
        return
    size_kb = path.stat().st_size / 1024
    await bot.send_document(
        message.chat.id,
        FSInputFile(str(path)),
        caption=f"🗄 Бэкап БД — {path.name} ({size_kb:.0f} КБ)",
    )


@router.message(Command("today"))
async def cmd_today(message: Message, settings: Settings) -> None:
    """Утренний бриф по запросу."""
    built = await reports.build_push("morning_brief", settings)
    if built:
        text, markup = built
        await message.answer(text, reply_markup=markup)


@router.message(Command("walks"))
async def cmd_walks(message: Message, settings: Settings) -> None:
    """Разбивка прогулок за последние 7 дней по местам."""
    since = settings.today() - dt.timedelta(days=6)
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        counts = await db.walks_by_place(conn, dog["id"], since)
    finally:
        await conn.close()
    total = sum(counts.values())
    if not total:
        await message.answer("🚶 За последние 7 дней прогулок не отмечено.")
        return
    labels = {"danube": "🌊 Дунай", "park": "🌳 Парк", "yard": "🏘 Двор"}
    rows = "\n".join(
        f"{labels.get(p, p)}: {n}" for p, n in sorted(counts.items(), key=lambda x: -x[1])
    )
    await message.answer(f"🚶 <b>Прогулки за 7 дней</b> — всего {total}\n{rows}")


@router.message(Command("stats"))
async def cmd_stats(message: Message, settings: Settings) -> None:
    """Прогресс: уровень, XP, стрики, число ачивок."""
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        xp = await db.get_xp(conn, dog["id"])
        walk = await db.get_streak(conn, dog["id"], "walk")
        nose = await db.get_streak(conn, dog["id"], "nose")
        cmd = await db.get_streak(conn, dog["id"], "command")
        ach = await db.list_achievements(conn, dog["id"])
    finally:
        await conn.close()

    text = texts.STATS.format(
        dog=dog["name"], level=gamification.level_for(xp), xp=xp,
        walk=walk, nose=nose, cmd=cmd, ach_count=len(ach),
    )
    if ach:
        text += "\n" + "\n".join("• " + gamification.ach_title(c) for c in ach)
    await message.answer(text)
