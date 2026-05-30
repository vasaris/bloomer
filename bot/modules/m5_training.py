"""M5 — Обучение и трюфельный поиск (Sprint 4). Ядро ментальной нагрузки.

Три блока (BLUMER_SYSTEM.md §5):
  • Команды послушания — мини-прогресс по каждой (mastery 0..5 + журнал сессий),
    отзыв в приоритете (под спуск с поводка). Стрик 🧠, +15 XP за сессию.
  • Нюхо-игра дня — ротация библиотеки 15-мин игр; сложность (тир) растёт с
    уровнем Блумера. Отметка = стрик 👃 (общий обработчик nose:done в logging).
  • Трюфель-программа — 7 этапов от заряда маркера до полевого поиска. На этапе 5
    подключаем Петара (King of the Truffles). Только позитив/LIMA.

Методика — гуманная (positive reinforcement): маркер + награда, никакого форсажа.
"""
from __future__ import annotations

import datetime as dt
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import db, gamification as gam, keyboards, logbook, texts

router = Router()

# ── Команды послушания ────────────────────────────────────────
# code → (эмодзи, название, приоритет)
COMMANDS: dict[str, tuple[str, str, bool]] = {
    "name":   ("🏷", "Имя / контакт", False),
    "come":   ("🐕", "«Ко мне» (дома)", False),
    "recall": ("🎯", "Отзыв (с дистанции)", True),
    "place":  ("🛏", "«Место»", False),
    "leave":  ("🚫", "«Оставь»", False),
}
COMMAND_ORDER = ["name", "come", "recall", "place", "leave"]

MASTERY_MAX = 5
MASTERY_LABELS = {
    0: "не начато",
    1: "дома, без отвлечений",
    2: "дома, с отвлечениями",
    3: "двор / тихая улица",
    4: "город / на дистанции",
    5: "надёжно везде",
}
CMD_XP_SESSION = 15      # за тренировку (через logbook → gamification)
CMD_XP_MASTERY = 10      # бонус за освоенный уровень


def _bar(mastery: int) -> str:
    return "▰" * mastery + "▱" * (MASTERY_MAX - mastery)


# ── Нюхо-игры (15 минут) ──────────────────────────────────────
# (название, описание, тир сложности 1..3)
NOSE_GAMES: list[tuple[str, str, int]] = [
    ("Рассыпь корм", "Часть дневной нормы рассыпь по траве/коврику — пусть собирает носом. Базовая нюховая разрядка.", 1),
    ("Три стакана", "Под одним из трёх стаканов — лакомство. Пусть выбирает носом, меняй местами.", 1),
    ("Нюхательный коврик", "Спрячь корм в снаффл-мат и отправь искать. Хорошо перед сном.", 1),
    ("Дорожка из лакомств", "Выложи дорожку по квартире, в конце — джекпот. Учит идти по запаху.", 1),
    ("Коробки", "5–6 коробок, в одной — еда. Команда «ищи».", 2),
    ("Найди игрушку", "Покажи игрушку, спрячь в соседней комнате, отправь искать по названию.", 2),
    ("Поиск по квартире", "Спрячь 5 порций в разных местах и на разной высоте. «Ищи».", 2),
    ("Кто спрятался", "Член семьи прячется — Блумер ищет по запаху. Отлично вовлекает детей.", 2),
    ("Поиск в траве", "На прогулке закинь горсть корма в траву — поиск в естественной среде.", 3),
    ("Целевой запах в коробках", "Целевой/трюфельный запах в одной из коробок среди пустых — выбор источника. Мостик к трюфель-программе.", 3),
    ("Закоп на улице", "Неглубоко прикопай источник запаха в землю/песок — поиск и сигнал «нашёл».", 3),
]


def _max_tier(total_xp: int) -> int:
    """Доступная сложность нюхо-игр растёт с уровнем Блумера."""
    idx = gam.level_index(total_xp)   # 0 Новичок … 4 Мастер
    if idx >= 3:
        return 3
    if idx >= 1:
        return 2
    return 1


def _eligible_games(total_xp: int) -> list[tuple[str, str]]:
    tier = _max_tier(total_xp)
    return [(t, d) for (t, d, tr) in NOSE_GAMES if tr <= tier]


def game_of_day(today: dt.date, total_xp: int) -> tuple[str, str]:
    """Детерминированная игра дня (стабильна в течение суток, ротация по дням)."""
    pool = _eligible_games(total_xp)
    return pool[today.toordinal() % len(pool)]


def random_game(total_xp: int, exclude: str | None = None) -> tuple[str, str]:
    pool = [g for g in _eligible_games(total_xp) if g[0] != exclude] or _eligible_games(total_xp)
    return random.choice(pool)


def nose_game_text(title: str, desc: str) -> str:
    return (
        f"👃 <b>Нюхо-игра дня</b>\n"
        f"<b>{title}</b>\n{desc}\n\n"
        f"⏱ ~15 минут. Мозг устаёт быстрее тела — это закрывает энергию без марафонов."
    )


# ── Трюфель-программа: этапы ───────────────────────────────────
TRUFFLE_LEN = 7
PETAR_STAGE = 5
TRUFFLE_STAGE_XP = 40
# этап → код ачивки при закрытии
TRUFFLE_STAGE_ACH: dict[int, str] = {3: "truffle_scent", 7: "truffle_find"}

# stage → (название, описание)
TRUFFLE_STAGES: dict[int, tuple[str, str]] = {
    1: ("Заряд маркера",
        "Кликер или маркер-слово = «сейчас будет награда». 10–15 коротких повторов в день, "
        "пока маркер не вызывает явное ожидание лакомства."),
    2: ("Ассоциация запаха",
        "Целевой запах на ватке в коробочке → нос к источнику → маркер + награда. "
        "Трюфельного масла пока нет — возьми любой чёткий безопасный запах "
        "(капля ванильного/анисового экстракта или сушёный гриб); позже заменишь на трюфельное масло."),
    3: ("Поиск на виду",
        "Источник стоит открыто среди 2–3 пустых коробок → выбор правильной → награда. "
        "Затем начинаем чуть прикрывать."),
    4: ("Спрятанный в комнате",
        "Прячем источник в 3–5 точках комнаты, отправляем «ищи». Растим число точек "
        "и сложность укрытий (высота, под предметами)."),
    5: ("Перенос на улицу",
        "То же на улице/террасе, неглубоко прикопанный источник. ⏱ Здесь — связаться с Петаром "
        "(King of the Truffles, Младеновац) и поставить полевую методику и сигнал «нашёл»."),
    6: ("Закоп в землю",
        "Источник закопан в грунт. Растим площадь поиска и дистанцию, закрепляем чёткий "
        "alert (замер/копок) на находке."),
    7: ("Полевой поиск",
        "Реальная территория (Фрушка-Гора). Поиск по площади, выдержка alert, работа в связке "
        "с винными маршрутами BalkanOutdoor."),
}


def truffle_active(stages: dict[int, str]) -> int | None:
    for s in sorted(stages):
        if stages[s] == "active":
            return s
    return None


def render_truffle(stages: dict[int, str]) -> str:
    icons = {"done": "✅", "active": "▶️", "locked": "🔒"}
    active = truffle_active(stages)
    lines = ["🍄 <b>Трюфель-программа</b>"]
    for s in range(1, TRUFFLE_LEN + 1):
        status = stages.get(s, "locked")
        title, desc = TRUFFLE_STAGES[s]
        head = f"{icons[status]} <b>Этап {s}. {title}</b>"
        if s == active:
            head += f"\n   {desc}"
            if s == PETAR_STAGE:
                head += "\n   ⚠️ Пора подключить Петара."
        lines.append(head)
    if active is None:
        lines.append("\n🏆 Все этапы пройдены — Блумер настоящий трюфельщик!")
    return "\n".join(lines)


# ════════════════════ ХЕНДЛЕРЫ: КОМАНДЫ ════════════════════════
def _render_board(prog: dict) -> str:
    lines = ["🧠 <b>База послушания</b>", "<i>Тапни команду, чтобы отметить тренировку или поднять уровень.</i>"]
    for code in COMMAND_ORDER:
        emoji, label, priority = COMMANDS[code]
        row = prog.get(code)
        mastery = row["mastery"] if row else 0
        sessions = row["sessions"] if row else 0
        star = " ⭐" if priority else ""
        lines.append(
            f"{emoji} <b>{label}</b>{star}\n   {_bar(mastery)} {MASTERY_LABELS[mastery]} · {sessions} трен."
        )
    return "\n".join(lines)


def _render_command(code: str, prog: dict) -> str:
    emoji, label, priority = COMMANDS[code]
    row = prog.get(code)
    mastery = row["mastery"] if row else 0
    sessions = row["sessions"] if row else 0
    star = " ⭐ приоритет (под спуск с поводка)" if priority else ""
    lines = [
        f"{emoji} <b>{label}</b>{star}",
        f"Уровень: {_bar(mastery)} <b>{MASTERY_LABELS[mastery]}</b>",
        f"Тренировок отмечено: {sessions}",
    ]
    if mastery < MASTERY_MAX:
        lines.append(f"\nСледующий уровень: {MASTERY_LABELS[mastery + 1]}")
    else:
        lines.append("\nМаксимум — отлично закреплено 🎯")
    return "\n".join(lines)


@router.message(Command("train"))
async def cmd_train(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_commands(conn, dog["id"], COMMAND_ORDER)
        prog = await db.get_command_progress(conn, dog["id"])
    finally:
        await conn.close()
    await message.answer(
        _render_board(prog),
        reply_markup=keyboards.train_board_kb(COMMAND_ORDER, COMMANDS),
    )


@router.callback_query(F.data == "cmd:board")
async def on_cmd_board(cb: CallbackQuery, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        prog = await db.get_command_progress(conn, dog["id"])
    finally:
        await conn.close()
    await cb.message.edit_text(
        _render_board(prog),
        reply_markup=keyboards.train_board_kb(COMMAND_ORDER, COMMANDS),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cmd:"))
async def on_cmd_open(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in COMMANDS:   # 'board' уже перехвачен выше
        await cb.answer()
        return
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_commands(conn, dog["id"], COMMAND_ORDER)
        prog = await db.get_command_progress(conn, dog["id"])
    finally:
        await conn.close()
    await cb.message.edit_text(
        _render_command(code, prog), reply_markup=keyboards.command_detail_kb(code)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cmdlog:"))
async def on_cmd_log(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in COMMANDS:
        await cb.answer()
        return
    today = settings.today()
    extra = await logbook.log_and_reward(
        settings, cb.from_user.id, "M5", "command", {"cmd": code}, on_date=today
    )
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.bump_command_session(conn, dog["id"], code, today)
        prog = await db.get_command_progress(conn, dog["id"])
    finally:
        await conn.close()
    emoji, label, _ = COMMANDS[code]
    await cb.message.edit_text(
        f"✅ Тренировка «{label}» отмечена.\n\n" + _render_command(code, prog),
        reply_markup=keyboards.command_detail_kb(code),
    )
    await cb.answer("Записал 🧠")
    for msg in extra:
        await cb.message.answer(msg)


@router.callback_query(F.data.startswith("cmdup:"))
async def on_cmd_up(cb: CallbackQuery, settings) -> None:
    code = cb.data.split(":", 1)[1]
    if code not in COMMANDS:
        await cb.answer()
        return
    today = settings.today()
    msgs: list[str] = []
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_commands(conn, dog["id"], COMMAND_ORDER)
        prog = await db.get_command_progress(conn, dog["id"])
        cur = prog[code]["mastery"]
        if cur >= MASTERY_MAX:
            await cb.answer("Уже максимум 🎯", show_alert=True)
            return
        new = cur + 1
        await db.set_command_mastery(conn, dog["id"], code, new, today)
        _, label, _ = COMMANDS[code]
        msgs.append(texts.BLOOMER_VOICE["command_mastery_up"].format(
            label=label, mastery=MASTERY_LABELS[new]
        ))
        msgs += await gam.award_xp(conn, dog["id"], CMD_XP_MASTERY)
        if code == "recall" and new == MASTERY_MAX:
            msgs += await gam.unlock(conn, dog["id"], "recall_master")
        prog = await db.get_command_progress(conn, dog["id"])
    finally:
        await conn.close()
    await cb.message.edit_text(
        _render_command(code, prog), reply_markup=keyboards.command_detail_kb(code)
    )
    await cb.answer("Уровень поднят ⬆️")
    for msg in msgs:
        await cb.message.answer(msg)


# ════════════════════ ХЕНДЛЕРЫ: НЮХО-ИГРА ══════════════════════
@router.message(Command("nose"))
async def cmd_nose(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        xp = await db.get_xp(conn, dog["id"])
    finally:
        await conn.close()
    title, desc = game_of_day(settings.today(), xp)
    await message.answer(nose_game_text(title, desc), reply_markup=keyboards.nose_kb())


@router.callback_query(F.data == "nose:shuffle")
async def on_nose_shuffle(cb: CallbackQuery, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        xp = await db.get_xp(conn, dog["id"])
    finally:
        await conn.close()
    # Текущее название — из первой строки <b>…</b>, чтобы не повторить.
    current = None
    for ln in (cb.message.html_text or cb.message.text or "").splitlines():
        s = ln.strip()
        if s and "Нюхо-игра" not in s and "👃" not in s:
            current = s.replace("<b>", "").replace("</b>", "")
            break
    title, desc = random_game(xp, exclude=current)
    await cb.message.edit_text(nose_game_text(title, desc), reply_markup=keyboards.nose_kb())
    await cb.answer("Другая игра 🔁")


# nose:done обрабатывается в handlers/logging.py (общая отметка нюхо-тренинга).


# ════════════════════ ХЕНДЛЕРЫ: ТРЮФЕЛЬ ════════════════════════
@router.message(Command("truffle"))
async def cmd_truffle(message: Message, settings) -> None:
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_truffle(conn, dog["id"], TRUFFLE_LEN)
        stages = await db.get_truffle_stages(conn, dog["id"])
    finally:
        await conn.close()
    await message.answer(
        render_truffle(stages), reply_markup=keyboards.truffle_kb(truffle_active(stages))
    )


@router.callback_query(F.data.startswith("truffle:done:"))
async def on_truffle_done(cb: CallbackQuery, settings) -> None:
    try:
        stage = int(cb.data.rsplit(":", 1)[1])
    except ValueError:
        await cb.answer()
        return
    today = settings.today()
    msgs: list[str] = []
    conn = await db.connect(settings.db_path)
    try:
        dog = await db.get_dog(conn)
        await db.ensure_truffle(conn, dog["id"], TRUFFLE_LEN)
        stages = await db.get_truffle_stages(conn, dog["id"])
        if truffle_active(stages) != stage:
            # устаревшая кнопка — просто перерисуем актуальное состояние
            await cb.message.edit_text(
                render_truffle(stages), reply_markup=keyboards.truffle_kb(truffle_active(stages))
            )
            await cb.answer("Этап уже закрыт")
            return
        await db.complete_truffle_stage(conn, dog["id"], stage, today)
        title = TRUFFLE_STAGES[stage][0]
        msgs.append(texts.BLOOMER_VOICE["truffle_stage_done"].format(title=title))
        msgs += await gam.award_xp(conn, dog["id"], TRUFFLE_STAGE_XP)
        if stage in TRUFFLE_STAGE_ACH:
            msgs += await gam.unlock(conn, dog["id"], TRUFFLE_STAGE_ACH[stage])
        stages = await db.get_truffle_stages(conn, dog["id"])
        new_active = truffle_active(stages)
    finally:
        await conn.close()
    await cb.message.edit_text(
        render_truffle(stages), reply_markup=keyboards.truffle_kb(new_active)
    )
    await cb.answer("Этап закрыт ✅")
    if new_active == PETAR_STAGE:
        msgs.append("⚠️ Следующий этап — полевой. Самое время связаться с Петаром (King of the Truffles).")
    for msg in msgs:
        await cb.message.answer(msg)
