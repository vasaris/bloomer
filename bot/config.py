"""Конфиг бота: читаем .env, держим дефолты расписания в одном месте.

Все времена пушей и тихие часы настраиваются через .env — править надо
только тут и в .env, код пушей их подхватывает сам.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Дефолтное расписание (из BLUMER_BOT_SPEC.md, §4). Перебивается через .env.
_DEFAULT_PUSHES: dict[str, str] = {
    "morning_brief": "07:30",   # план дня + погода (жара?)
    "walk_morning": "08:00",    # «Пора на Дунай/в парк?»
    "nose_task": "13:00",       # нюхо-задача дня
    "walk_evening": "19:00",    # вечерняя прогулка
    "asthma_check": "20:00",    # астма-чек Макса (первые 21 день)
    "day_summary": "21:30",     # итог дня + стрики/XP
}
# Недельный обзор — отдельный (день недели + время).
_DEFAULT_WEEKLY = ("sun", "20:00")

# Соответствие кода пуша → env-переменная с временем.
_PUSH_ENV = {
    "morning_brief": "PUSH_MORNING_BRIEF",
    "walk_morning": "PUSH_WALK_MORNING",
    "nose_task": "PUSH_NOSE_TASK",
    "walk_evening": "PUSH_WALK_EVENING",
    "asthma_check": "PUSH_ASTHMA_CHECK",
    "day_summary": "PUSH_DAY_SUMMARY",
}


def _parse_hm(raw: str) -> tuple[int, int]:
    """'07:30' -> (7, 30)."""
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

    # code -> (hour, minute)
    pushes: dict[str, tuple[int, int]]
    weekly_review_dow: str
    weekly_review_time: tuple[int, int]

    quiet_start: tuple[int, int]
    quiet_end: tuple[int, int]

    anthropic_api_key: str | None

    def is_quiet(self, hour: int, minute: int) -> bool:
        """Попадает ли время в тихие часы (окно может пересекать полночь)."""
        now = hour * 60 + minute
        start = self.quiet_start[0] * 60 + self.quiet_start[1]
        end = self.quiet_end[0] * 60 + self.quiet_end[1]
        if start <= end:
            return start <= now < end
        # окно через полночь, напр. 22:00–07:00
        return now >= start or now < end


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не задан — заполни .env (см. .env.example)")

    pushes = {
        code: _parse_hm(os.getenv(env_key, _DEFAULT_PUSHES[code]))
        for code, env_key in _PUSH_ENV.items()
    }

    return Settings(
        bot_token=token,
        owner_chat_ids=_parse_ids(os.getenv("OWNER_CHAT_IDS")),
        timezone=os.getenv("TIMEZONE", "Europe/Belgrade"),
        db_path=os.getenv("DB_PATH", "blumer.db"),
        pushes=pushes,
        weekly_review_dow=os.getenv("PUSH_WEEKLY_REVIEW_DOW", _DEFAULT_WEEKLY[0]),
        weekly_review_time=_parse_hm(
            os.getenv("PUSH_WEEKLY_REVIEW", _DEFAULT_WEEKLY[1])
        ),
        quiet_start=_parse_hm(os.getenv("QUIET_HOURS_START", "22:00")),
        quiet_end=_parse_hm(os.getenv("QUIET_HOURS_END", "07:00")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
