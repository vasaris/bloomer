"""Экспорт журнала (Sprint 8): /export → zip с CSV по таблицам + lossless JSON.

В архиве:
  event_log.csv     — все события (прогулки/кормёжка/нюхо/команды/груминг/здоровье/…)
  health_metric.csv — замеры (вес и пр.)
  asthma_check.csv  — астма-чек Макса
  export.json       — то же структурировано, с распарсенным payload (без потерь)

CSV — в utf-8-sig (BOM), чтобы Excel/Sheets корректно открывали кириллицу.
Файл собирается в памяти и уходит документом в тот же чат (своя же копия данных).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from .. import db
from ..config import Settings

router = Router()


def _csv_bytes(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")  # BOM → кириллица в Excel


def _parse_payload(raw: str | None) -> dict:
    try:
        return json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}


@router.message(Command("export"))
async def cmd_export(message: Message, settings: Settings, bot: Bot) -> None:
    await message.answer("📦 Собираю выгрузку журнала…")
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        events = await db.all_events(conn, dog["id"])
        health = await db.all_health_metrics(conn, dog["id"])
        asthma = await db.all_asthma(conn)
    finally:
        await conn.close()

    # CSV по таблицам.
    events_csv = _csv_bytes(
        ["id", "local_date", "created_at", "module", "type", "payload_json", "user"],
        [[e["id"], e["local_date"], e["created_at"], e["module"], e["type"],
          e["payload_json"], e["user_name"] or ""] for e in events],
    )
    health_csv = _csv_bytes(
        ["id", "metric", "value", "unit", "measured_at"],
        [[h["id"], h["metric"], h["value"], h["unit"] or "", h["measured_at"]] for h in health],
    )
    asthma_csv = _csv_bytes(
        ["id", "date", "status", "note"],
        [[a["id"], a["date"], a["status"] or "", a["note"] or ""] for a in asthma],
    )

    # Lossless JSON (payload распарсен в объект).
    export = {
        "exported_at": dt.datetime.now().isoformat(timespec="seconds"),
        "dog": dog["name"],
        "events": [
            {"id": e["id"], "local_date": e["local_date"], "created_at": e["created_at"],
             "module": e["module"], "type": e["type"],
             "payload": _parse_payload(e["payload_json"]), "user": e["user_name"]}
            for e in events
        ],
        "health_metric": [
            {"id": h["id"], "metric": h["metric"], "value": h["value"],
             "unit": h["unit"], "measured_at": h["measured_at"]} for h in health
        ],
        "asthma_check": [
            {"id": a["id"], "date": a["date"], "status": a["status"], "note": a["note"]}
            for a in asthma
        ],
    }
    json_bytes = json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8")

    # Zip в памяти.
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("event_log.csv", events_csv)
        z.writestr("health_metric.csv", health_csv)
        z.writestr("asthma_check.csv", asthma_csv)
        z.writestr("export.json", json_bytes)
    zbuf.seek(0)

    fname = f"blumer-journal-{settings.today().strftime('%Y%m%d')}.zip"
    caption = (
        f"📦 Журнал {dog['name']}: событий {len(events)}, "
        f"замеров {len(health)}, астма-чеков {len(asthma)}.\n"
        f"Внутри: CSV по таблицам + export.json (без потерь)."
    )
    await bot.send_document(
        message.chat.id, BufferedInputFile(zbuf.getvalue(), filename=fname), caption=caption
    )
