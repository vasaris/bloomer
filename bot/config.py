"""Конфиг бота: читаем .env, держим дефолты расписания в одном месте.

Любой пуш можно отключить, задав его время как off/none в .env
(напр. PUSH_FEED_MORNING=off).
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass

import pytz
from dotenv import load_dotenv

load_dotenv()

# Дефолтное расписание (BLUMER_BOT_SPEC.md §4). Перебивается через .env.
_DEFAULT_PUSHES: dict[str, str] = {
    "morning_brief": "07:30",   # план дня
    "walk_morning": "08:00",    # утренняя прогулка (+ кнопки лога)
    "feed_morning": "08:30",    # кормёжка ×2 (Sprint 1)
    "health_check": "09:00",    # проверка здоровья (шлётся, если что-то пора)
    "nose_task": "13:00",       # нюхо-задача дня
    "groom_check": "10:30",     # проверка цикла груминга (шлётся, если что-то пора)
    "feed_evening": "18:30",    # кормёжка ×2 (Sprint 1)
    "walk_evening": "19:00",    # вечерняя прогулка (+ кнопки лога)
    "asthma_check": "20:00",    # астма-чек Макса (первые 21 день)
    "day_summary": "21:30",     # итог дня
}
_DEFAULT_WEEKLY = ("sun", "20:00")

_PUSH_ENV = {
    "morning_brief": "PUSH_MORNING_BRIEF",
    "walk_morning": "PUSH_WALK_MORNING",
    "feed_morning": "PUSH_FEED_MORNING",
    "health_check": "PUSH_HEALTH_CHECK",
    "nose_task": "PUSH_NOSE_TASK",
    "groom_check": "PUSH_GROOM_CHECK",
    "feed_evening": "PUSH_FEED_EVENING",
    "walk_evening": "PUSH_WALK_EVENING",
    "asthma_check": "PUSH_ASTHMA_CHECK",
    "day_summary": "PUSH_DAY_SUMMARY",
}

_OFF = {"off", "none", "-", ""}


def _parse_hm(raw: str) -> tuple[int, int]:
    hh, mm = raw.strip().split(":")
    return int(hh), int(mm)


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_chat_ids: list[int]
    timezone: str
    db_path: str

    pushes: dict[str, tuple[int, int]]   # code -> (hour, minute)
    weekly_review_dow: str
    weekly_review_time: tuple[int, int]

    quiet_start: tuple[int, int]
    quiet_end: tuple[int, int]

    anthropic_api_key: str | None

    def is_quiet(self, hour: int, minute: int) -> bool:
        now = hour * 60 + minute
        start = self.quiet_start[0] * 60 + self.quiet_start[1]
        end = self.quiet_end[0] * 60 + self.quiet_end[1]
        if start <= end:
            return start <= now < end
        return now >= start or now < end  # окно через полночь

    def now(self) -> dt.datetime:
        """Текущее время в часовом поясе пользователя (а не сервера/UTC)."""
        return dt.datetime.now(pytz.timezone(self.timezone))

    def today(self) -> dt.date:
        """Локальная дата по TZ. Использовать ВЕЗДЕ вместо date.today()."""
        return self.now().date()


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан — заполни .env (см. .env.example)")

    pushes: dict[str, tuple[int, int]] = {}
    for code, env_key in _PUSH_ENV.items():
        raw = os.getenv(env_key, _DEFAULT_PUSHES[code])
        if raw.strip().lower() in _OFF:
            continue  # пуш отключён
        pushes[code] = _parse_hm(raw)

    return Settings(
        bot_token=token,
        owner_chat_ids=_parse_ids(os.getenv("OWNER_CHAT_IDS")),
        timezone=os.getenv("TIMEZONE", "Europe/Belgrade"),
        db_path=os.getenv("DB_PATH", "blumer.db"),
        pushes=pushes,
        weekly_review_dow=os.getenv("PUSH_WEEKLY_REVIEW_DOW", _DEFAULT_WEEKLY[0]),
        weekly_review_time=_parse_hm(os.getenv("PUSH_WEEKLY_REVIEW", _DEFAULT_WEEKLY[1])),
        quiet_start=_parse_hm(os.getenv("QUIET_HOURS_START", "22:00")),
        quiet_end=_parse_hm(os.getenv("QUIET_HOURS_END", "07:00")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
