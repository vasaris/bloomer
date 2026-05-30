"""Настройки времени пушей из бота (Sprint 8): /settings, /settime, /setquiet, /setweekly.

Правки пишутся в таблицу `setting` (переживают рестарт) И сразу применяются к
работающему планировщику через PushService (живой reschedule, без перезапуска).
Отображение берём из push.settings — он держится в актуальном состоянии после
каждой правки, так что /settings всегда показывает текущую картину.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .. import db, pushconf
from ..config import Settings
from ..scheduler import PushService

router = Router()


def _render(push: PushService) -> str:
    s = push.settings
    lines = ["⚙️ <b>Настройки пушей</b>\n"]
    for code in pushconf.PUSH_ORDER:
        label = pushconf.PUSH_LABELS[code]
        if code == "weekly_review":
            dow = pushconf.DOW_RU.get(s.weekly_review_dow, s.weekly_review_dow)
            lines.append(f"{label} — {dow} {pushconf.fmt_hm(s.weekly_review_time)}")
        elif code in s.pushes:
            lines.append(f"{label} — {pushconf.fmt_hm(s.pushes[code])}")
        else:
            lines.append(f"{label} — <i>выкл</i>")
    lines.append(
        f"\n🔕 Тихие часы: {pushconf.fmt_hm(s.quiet_start)}–{pushconf.fmt_hm(s.quiet_end)}"
    )
    lines.append(
        "\n<b>Изменить:</b>\n"
        "• <code>/settime код ЧЧ:ММ</code> (или <code>off</code>)\n"
        "• <code>/setquiet ЧЧ:ММ ЧЧ:ММ</code>\n"
        "• <code>/setweekly дн ЧЧ:ММ</code> (дн: mon…sun)\n\n"
        "Коды: " + ", ".join(pushconf.PUSH_ORDER)
    )
    return "\n".join(lines)


@router.message(Command("settings"))
async def cmd_settings(message: Message, push: PushService) -> None:
    await message.answer(_render(push))


@router.message(Command("settime"))
async def cmd_settime(
    message: Message, command: CommandObject, settings: Settings, push: PushService
) -> None:
    args = (command.args or "").split()
    if len(args) != 2:
        await message.answer(
            "Формат: <code>/settime код ЧЧ:ММ</code> или <code>/settime код off</code>.\n"
            "Список кодов и текущие времена — /settings."
        )
        return
    code, value = args[0], args[1]
    if code not in pushconf.VALID_CODES:
        await message.answer(f"Неизвестный код «{code}». Список — /settings.")
        return

    conn = await db.connect(settings.db_path)
    try:
        if pushconf.is_off(value):
            if code == "weekly_review":
                await message.answer("🗓 Недельный обзор отключать не будем — это сводка раз в неделю. Поменяй время через /setweekly.")
                return
            await db.set_setting(conn, f"push.{code}", "off")
            push.disable_push(code)
            await message.answer(f"🔕 {pushconf.PUSH_LABELS[code]} — отключён.")
            return
        hm = pushconf.parse_hm(value)
        if hm is None:
            await message.answer("Время в формате ЧЧ:ММ (например 07:45).")
            return
        if code == "weekly_review":
            await db.set_setting(conn, "weekly.time", pushconf.fmt_hm(hm))
        else:
            await db.set_setting(conn, f"push.{code}", pushconf.fmt_hm(hm))
        push.set_push_time(code, hm[0], hm[1])
    finally:
        await conn.close()
    await message.answer(f"✅ {pushconf.PUSH_LABELS[code]} — теперь {pushconf.fmt_hm(hm)}.")


@router.message(Command("setquiet"))
async def cmd_setquiet(
    message: Message, command: CommandObject, settings: Settings, push: PushService
) -> None:
    args = (command.args or "").split()
    if len(args) != 2:
        await message.answer("Формат: <code>/setquiet 22:00 07:00</code> (начало конец).")
        return
    start, end = pushconf.parse_hm(args[0]), pushconf.parse_hm(args[1])
    if start is None or end is None:
        await message.answer("Время в формате ЧЧ:ММ (например 22:30 07:00).")
        return
    conn = await db.connect(settings.db_path)
    try:
        await db.set_setting(conn, "quiet.start", pushconf.fmt_hm(start))
        await db.set_setting(conn, "quiet.end", pushconf.fmt_hm(end))
    finally:
        await conn.close()
    push.set_quiet(start, end)
    await message.answer(
        f"🔕 Тихие часы: {pushconf.fmt_hm(start)}–{pushconf.fmt_hm(end)}."
    )


@router.message(Command("setweekly"))
async def cmd_setweekly(
    message: Message, command: CommandObject, settings: Settings, push: PushService
) -> None:
    args = (command.args or "").split()
    if len(args) != 2 or args[0].lower() not in pushconf.DOW_ORDER:
        await message.answer(
            "Формат: <code>/setweekly sun 20:00</code>. Дни: " + ", ".join(pushconf.DOW_ORDER)
        )
        return
    dow = args[0].lower()
    hm = pushconf.parse_hm(args[1])
    if hm is None:
        await message.answer("Время в формате ЧЧ:ММ (например 20:00).")
        return
    conn = await db.connect(settings.db_path)
    try:
        await db.set_setting(conn, "weekly.dow", dow)
        await db.set_setting(conn, "weekly.time", pushconf.fmt_hm(hm))
    finally:
        await conn.close()
    push.set_weekly(dow, hm[0], hm[1])
    await message.answer(
        f"🗓 Недельный обзор — {pushconf.DOW_RU[dow]} {pushconf.fmt_hm(hm)}."
    )
