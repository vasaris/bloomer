"""Контроль доступа: бот реагирует только на whitelisted чаты (Иван, Лена).

Whitelist = OWNER_CHAT_IDS из .env. Покрывает И сообщения, И тапы по кнопкам
(callback_query пишут в БД, поэтому их тоже нужно проверять).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from . import texts


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_ids: list[int]) -> None:
        self.allowed = set(allowed_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat_id: int | None = None
        if isinstance(event, Message):
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            chat_id = event.from_user.id if event.from_user else None

        # Пустой whitelist = режим первичной настройки: пускаем всех,
        # чтобы узнать свой id через /start и сразу вписать в .env.
        if self.allowed and chat_id is not None and chat_id not in self.allowed:
            if isinstance(event, Message):
                await event.answer(texts.ACCESS_DENIED.format(chat_id=chat_id))
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ ограничен.", show_alert=True)
            return None
        return await handler(event, data)
