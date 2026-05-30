"""Контроль доступа: бот отвечает только whitelisted чатам (Иван, Лена).

Whitelist = OWNER_CHAT_IDS из .env. Чужие сообщения отбиваются с подсказкой
их chat_id (удобно, чтобы добавить Лену).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

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
        if isinstance(event, Message):
            chat_id = event.chat.id
            # Пустой whitelist = режим первичной настройки: пускаем всех,
            # чтобы узнать свой id через /start, и сразу же вписать в .env.
            if self.allowed and chat_id not in self.allowed:
                await event.answer(texts.ACCESS_DENIED.format(chat_id=chat_id))
                return None
        return await handler(event, data)
