"""Бэкапы SQLite (Sprint 8): консистентная онлайн-копия БД + ротация.

Используем SQLite online backup API (`conn.backup`) — он делает целостный снимок
даже при активных записях. Сырое копирование файла (shutil.copy) так не умеет:
под запись можно схватить полузаписанную страницу и получить битый бэкап.

Куда складываем: по умолчанию подкаталог `backups/` рядом с файлом БД — чтобы на
Railway бэкапы лежали на том же Volume и переживали редеплой. Имя файла
сортируется лексикографически по времени, на этом же построена ротация.

Расписание (ежедневный джоб) и офсайт-отправка в Telegram — в scheduler.py.
По запросу — команда /backup (handlers/common.py).
"""
from __future__ import annotations

import datetime as dt
import logging
import pathlib

import aiosqlite

log = logging.getLogger(__name__)

_PREFIX = "blumer-"
_SUFFIX = ".db"
_STAMP = "%Y%m%d-%H%M%S"  # zero-padded → имя сортируется как время


def backup_dir_for(db_path: str, override: str | None = None) -> pathlib.Path:
    """Каталог бэкапов: BACKUP_DIR из .env или `<каталог БД>/backups`."""
    if override:
        return pathlib.Path(override)
    return pathlib.Path(db_path).resolve().parent / "backups"


async def make_backup(
    db_path: str, backup_dir: pathlib.Path, keep: int = 7
) -> pathlib.Path:
    """Делает целостную копию БД в backup_dir и подчищает старые. Возвращает путь."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"{_PREFIX}{dt.datetime.now().strftime(_STAMP)}{_SUFFIX}"

    # Источник держим открытым во время backup() — это и есть «онлайн» режим.
    async with aiosqlite.connect(db_path) as src, aiosqlite.connect(dest) as dst:
        await src.backup(dst)

    log.info("БД забэкаплена → %s (%d байт)", dest.name, dest.stat().st_size)
    _rotate(backup_dir, keep)
    return dest


def _rotate(backup_dir: pathlib.Path, keep: int) -> None:
    """Оставляет `keep` самых свежих бэкапов, остальные удаляет. keep<=0 — не чистим."""
    if keep <= 0:
        return
    files = sorted(backup_dir.glob(f"{_PREFIX}*{_SUFFIX}"), key=lambda p: p.name)
    for old in files[:-keep]:
        try:
            old.unlink()
            log.info("Удалён старый бэкап %s", old.name)
        except OSError as e:  # не валим бэкап из-за неудачной уборки
            log.warning("Не удалось удалить старый бэкап %s: %s", old.name, e)


def latest_backup(backup_dir: pathlib.Path) -> pathlib.Path | None:
    """Самый свежий бэкап в каталоге (или None)."""
    files = sorted(backup_dir.glob(f"{_PREFIX}*{_SUFFIX}"), key=lambda p: p.name)
    return files[-1] if files else None


def list_backups(backup_dir: pathlib.Path) -> list[pathlib.Path]:
    """Все бэкапы, от старых к свежим."""
    return sorted(backup_dir.glob(f"{_PREFIX}*{_SUFFIX}"), key=lambda p: p.name)
