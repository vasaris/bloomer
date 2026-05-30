"""Инлайн-клавиатуры. callback_data — короткие строки 'домен:значение'.

Логирование в один тап: прогулка (место), кормёжка, астма-чек, снуз.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def walk_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌊 Дунай", callback_data="walk:danube"),
                InlineKeyboardButton(text="🌳 Парк", callback_data="walk:park"),
                InlineKeyboardButton(text="🏘 Двор", callback_data="walk:yard"),
            ],
            [InlineKeyboardButton(text="⏰ Отложить на час", callback_data="snooze:walk")],
        ]
    )


def feed_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Покормили", callback_data="feed:done")],
            [InlineKeyboardButton(text="⏰ Отложить", callback_data="snooze:feed")],
        ]
    )


def asthma_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Ок", callback_data="asthma:ok")],
            [InlineKeyboardButton(text="🟡 Лёгкие симптомы", callback_data="asthma:mild")],
            [InlineKeyboardButton(text="🔴 Беспокоит", callback_data="asthma:concern")],
        ]
    )


def log_menu_kb() -> InlineKeyboardMarkup:
    """Ручное меню /log."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚶 Прогулка", callback_data="logmenu:walk")],
            [InlineKeyboardButton(text="🍽 Кормёжка", callback_data="feed:done")],
            [InlineKeyboardButton(text="👃 Нюхо-игра / тренинг", callback_data="nose:done")],
        ]
    )


def groom_kb() -> InlineKeyboardMarkup:
    """Кнопки отметки груминга (M3). Коды совпадают с m3_grooming.GROOM."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🪮 Расчесали", callback_data="groom:brush"),
                InlineKeyboardButton(text="👂 Уши", callback_data="groom:ears"),
            ],
            [
                InlineKeyboardButton(text="🛁 Купание", callback_data="groom:bath"),
                InlineKeyboardButton(text="✂️ Стрижка", callback_data="groom:haircut"),
            ],
        ]
    )


# ── M5: Тренинг (Sprint 4) ─────────────────────────────────────
def train_board_kb(order: list[str], commands: dict) -> InlineKeyboardMarkup:
    """Доска команд: по кнопке на команду (открывает деталь)."""
    rows = []
    for code in order:
        emoji, label, priority = commands[code]
        star = " ⭐" if priority else ""
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {label}{star}", callback_data=f"cmd:{code}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def command_detail_kb(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отработали сегодня", callback_data=f"cmdlog:{code}")],
            [InlineKeyboardButton(text="⬆️ Освоил уровень", callback_data=f"cmdup:{code}")],
            [InlineKeyboardButton(text="⬅️ К доске команд", callback_data="cmd:board")],
        ]
    )


def nose_kb() -> InlineKeyboardMarkup:
    """Нюхо-игра дня: отметить (общий nose:done) + другая игра."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👃 Сделали", callback_data="nose:done"),
                InlineKeyboardButton(text="🔁 Другая", callback_data="nose:shuffle"),
            ],
        ]
    )


def truffle_kb(active_stage: int | None) -> InlineKeyboardMarkup | None:
    """Кнопка закрытия активного этапа трюфель-программы (если есть)."""
    if active_stage is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Закрыл этап {active_stage}",
                callback_data=f"truffle:done:{active_stage}",
            )],
        ]
    )


# ── M4: Здоровье (Sprint 5) ────────────────────────────────────
def health_kb() -> InlineKeyboardMarkup:
    """Кнопки отметки процедур здоровья. Коды совпадают с m4_health.HEALTH."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🩺 Осмотр", callback_data="health:vet"),
                InlineKeyboardButton(text="💉 Прививка", callback_data="health:vaccine"),
            ],
            [
                InlineKeyboardButton(text="💉 Бешенство", callback_data="health:rabies"),
                InlineKeyboardButton(text="🕷 Клещи", callback_data="health:tick"),
            ],
            [InlineKeyboardButton(text="🪱 Глистогон", callback_data="health:deworm")],
        ]
    )


# ── M6: Социализация (Sprint 6) ────────────────────────────────
def soc_board_kb(order: list[str], items: dict) -> InlineKeyboardMarkup:
    """Доска опыта: по кнопке на каждый «новый опыт» (открывает деталь)."""
    rows = []
    for code in order:
        emoji, label, _city = items[code]
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {label}", callback_data=f"soc:{code}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def soc_detail_kb(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отметить опыт сегодня", callback_data=f"soclog:{code}")],
            [InlineKeyboardButton(text="⬆️ Стал увереннее", callback_data=f"socup:{code}")],
            [InlineKeyboardButton(text="⬅️ К чек-листу", callback_data="soc:board")],
        ]
    )


# ── M7: Путешествия (Sprint 6) ─────────────────────────────────
def trip_kb(checklist: dict[str, bool], labels: dict[str, tuple[str, str]]) -> InlineKeyboardMarkup:
    """Чек-лист подготовки к туру: тап по пункту = toggle. + сброс и «Поехали»."""
    rows = []
    for code, (emoji, label) in labels.items():
        mark = "☑️" if checklist.get(code) else "▫️"
        rows.append([InlineKeyboardButton(
            text=f"{mark} {emoji} {label}", callback_data=f"trip:toggle:{code}"
        )])
    rows.append([
        InlineKeyboardButton(text="🔄 Сбросить", callback_data="trip:reset"),
        InlineKeyboardButton(text="🚗 Поехали (спокойно)", callback_data="trip:go"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
