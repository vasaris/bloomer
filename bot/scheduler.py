"""Планировщик проактивных пушей на APScheduler (AsyncIOScheduler).

- Регистрирует cron-джобы из config.Settings (время правится в .env).
- Тихие часы: пуш молча пропускается, если время попало в окно.
- Снуз: каркас (планируем одноразовый джоб «напомнить позже»).

Реальное наполнение текстов/кнопок — со Sprint 1+. Здесь — рассылка
нейтрального шаблона активным пользователям.
"""
from __future__ import annotations

import datetime as dt
import logging

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import db, reports
from .config import Settings

log = logging.getLogger(__name__)


class PushService:
    """Отправка пушей + учёт тихих часов. Держит bot и настройки."""

    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self.tz = pytz.timezone(settings.timezone)

    async def _recipients(self) -> list[int]:
        """Активные получатели: из БД, с фолбэком на whitelist из .env."""
        conn = await db.connect(self.settings.db_path)
        try:
            ids = await db.active_chat_ids(conn)
        finally:
            await conn.close()
        return ids or self.settings.owner_chat_ids

    async def send(self, code: str, *, force: bool = False) -> None:
        """Отправить пуш по коду. force=True игнорирует тихие часы (для /ping)."""
        now = dt.datetime.now(self.tz)
        if not force and self.settings.is_quiet(now.hour, now.minute):
            log.info("Пуш '%s' пропущен — тихие часы (%02d:%02d)", code, now.hour, now.minute)
            return

        built = await reports.build_push(code, self.settings, now.date())
        if built is None:
            log.info("Пуш '%s' пропущен — сегодня не нужен", code)
            return
        text, markup = built

        for chat_id in await self._recipients():
            try:
                await self.bot.send_message(chat_id, text, reply_markup=markup)
            except Exception as e:  # сеть/блокировка — не роняем планировщик
                log.warning("Не доставлен пуш '%s' в %s: %s", code, chat_id, e)

    async def snooze(self, code: str, minutes: int = 60) -> None:
        """Заглушка снуза: переотправить пуш через N минут.

        Sprint 8 повесит это на кнопку «Отложить» и таблицу snooze.
        Здесь — рабочий разовый джоб, чтобы механика была готова.
        """
        run_at = dt.datetime.now(self.tz) + dt.timedelta(minutes=minutes)
        _scheduler.add_job(
            self.send, "date", run_date=run_at, args=[code],
            id=f"snooze:{code}:{run_at.timestamp()}",
        )
        log.info("Пуш '%s' отложен до %s", code, run_at.strftime("%H:%M"))


_scheduler: AsyncIOScheduler | None = None


def build_scheduler(bot: Bot, settings: Settings) -> tuple[AsyncIOScheduler, PushService]:
    """Создаёт планировщик и регистрирует все джобы из настроек."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    _scheduler = scheduler
    svc = PushService(bot, settings)

    # Ежедневные пуши из config (время — из .env).
    for code, (hour, minute) in settings.pushes.items():
        scheduler.add_job(
            svc.send,
            CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
            args=[code],
            id=f"daily:{code}",
            replace_existing=True,
        )
        log.info("Зарегистрирован пуш '%s' на %02d:%02d", code, hour, minute)

    # Недельный обзор (день недели + время).
    wh, wm = settings.weekly_review_time
    scheduler.add_job(
        svc.send,
        CronTrigger(
            day_of_week=settings.weekly_review_dow,
            hour=wh, minute=wm, timezone=settings.timezone,
        ),
        args=["weekly_review"],
        id="weekly:review",
        replace_existing=True,
    )
    log.info("Зарегистрирован недельный обзор: %s %02d:%02d", settings.weekly_review_dow, wh, wm)

    return scheduler, svc
