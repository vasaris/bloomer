"""BLUMER BOT — точка входа.

Поднимает: БД → бота → планировщик пушей → polling.
Запуск локально:   python -m bot.main
Railway (Procfile): worker: python -m bot.main
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from . import db, texts
from .config import load_settings
from .handlers import build_root_router
from .middlewares import AccessMiddleware
from .scheduler import build_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("blumer")


async def main() -> None:
    settings = load_settings()

    # 1. БД: создать схему и убедиться, что есть профиль Блумера.
    await db.init_db(settings.db_path)
    conn = await db.connect(settings.db_path)
    try:
        await db.ensure_dog(conn, name=texts.DOG_NAME, breed="Лаготто-романьоло")
    finally:
        await conn.close()

    # 2. Бот и диспетчер.
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    # 3. Планировщик пушей (создаём до polling, передаём в хендлеры через DI).
    scheduler, push = build_scheduler(bot, settings)

    # Прокидываем зависимости в хендлеры (settings, push) через workflow_data.
    dp["settings"] = settings
    dp["push"] = push

    # 4. Доступ только whitelisted чатам.
    dp.message.middleware(AccessMiddleware(settings.owner_chat_ids))

    # 5. Роутеры.
    dp.include_router(build_root_router())

    # 6. Старт.
    scheduler.start()
    log.info("Планировщик запущен. Пуши: %s", list(settings.pushes))
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("BLUMER BOT v%s — polling...", __import__("bot").__version__)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлено.")
