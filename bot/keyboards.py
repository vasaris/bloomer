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
        ]
    )
