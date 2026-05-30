"""Конфигурация времени пушей с override-ами из БД (Sprint 8).

Источники, по приоритету: дефолты (config) → .env → правки пользователя в БД
(таблица `setting`, ключи push.<code> / quiet.* / weekly.*). Здесь — словарь
лейблов, валидация времени и мердж override-ов в эффективный Settings при старте.

Живое перепланирование работающих джобов — в scheduler.PushService (set_push_time
и пр.); персистентность правок — db.set_setting; команды — handlers/settings.
"""
from __future__ import annotations

import dataclasses

from . import config
from .config import Settings

# Человекочитаемые лейблы пушей (RU). Порядок — как в дефолтах + обзор в конце.
PUSH_LABELS: dict[str, str] = {
    "morning_brief": "☀️ Утренний бриф",
    "walk_morning": "🚶 Прогулка утро",
    "feed_morning": "🍽 Кормёжка утро",
    "health_check": "🩺 Проверка здоровья",
    "nose_task": "👃 Нюхо-задача",
    "groom_check": "🧼 Проверка груминга",
    "feed_evening": "🍽 Кормёжка вечер",
    "walk_evening": "🌆 Прогулка вечер",
    "asthma_check": "🫁 Астма-чек Макса",
    "day_summary": "🌙 Итог дня",
    "weekly_review": "🗓 Недельный обзор",
}

# Порядок отображения и список валидных кодов для команд.
PUSH_ORDER: list[str] = list(config.DEFAULT_PUSHES) + ["weekly_review"]
VALID_CODES = set(PUSH_ORDER)

DOW_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DOW_RU = {"mon": "пн", "tue": "вт", "wed": "ср", "thu": "чт",
          "fri": "пт", "sat": "сб", "sun": "вс"}

_OFF = {"off", "none", "-", ""}


def is_off(raw: str) -> bool:
    return raw.strip().lower() in _OFF


def parse_hm(raw: str) -> tuple[int, int] | None:
    """'HH:MM' → (h, m) с валидацией диапазона; иначе None."""
    try:
        hh, mm = raw.strip().split(":")
        h, m = int(hh), int(mm)
    except (ValueError, AttributeError):
        return None
    if 0 <= h < 24 and 0 <= m < 60:
        return (h, m)
    return None


def fmt_hm(hm: tuple[int, int]) -> str:
    return f"{hm[0]:02d}:{hm[1]:02d}"


async def load_overrides(conn) -> dict[str, str]:
    """Все override-настройки из таблицы setting (push.* / quiet.* / weekly.*)."""
    from . import db
    return await db.all_settings(conn)


def apply_overrides(settings: Settings, ov: dict[str, str]) -> Settings:
    """Накатывает override-ы поверх env-настроек и возвращает новый Settings."""
    pushes = dict(settings.pushes)
    for code in config.DEFAULT_PUSHES:
        raw = ov.get(f"push.{code}")
        if raw is None:
            continue
        if is_off(raw):
            pushes.pop(code, None)
        else:
            hm = parse_hm(raw)
            if hm:
                pushes[code] = hm

    qs = parse_hm(ov["quiet.start"]) if "quiet.start" in ov else None
    qe = parse_hm(ov["quiet.end"]) if "quiet.end" in ov else None
    wt = parse_hm(ov["weekly.time"]) if "weekly.time" in ov else None
    wd = ov.get("weekly.dow")

    return dataclasses.replace(
        settings,
        pushes=pushes,
        quiet_start=qs or settings.quiet_start,
        quiet_end=qe or settings.quiet_end,
        weekly_review_time=wt or settings.weekly_review_time,
        weekly_review_dow=wd if wd in DOW_ORDER else settings.weekly_review_dow,
    )
