"""Тонкая async-обёртка над Claude API (Sprint 7).

«Мозг» бота: системный промпт = bot/blumer_system.md (то же, что в Claude Project),
поверх — короткая Telegram-преамбула (канал, формат). Контекст из БД подмешивается
вызывающим (см. bot/context.py) в текст вопроса.

Модель — claude-sonnet-4-6 по умолчанию (актуальный Sonnet; Sonnet 4 выведен из
эксплуатации в апреле 2026), переопределяется через CLAUDE_MODEL в .env.

Деградация: нет ключа → ClaudeUnavailable('no_key'); ошибка API/сети →
ClaudeUnavailable('api_error'). Хендлеры ловят и отвечают по-человечески,
бот не падает.
"""
from __future__ import annotations

import logging
import pathlib

from anthropic import APIError, AsyncAnthropic

log = logging.getLogger(__name__)

MAX_TOKENS = 1024
_SYSTEM_PATH = pathlib.Path(__file__).parent / "blumer_system.md"

# Преамбула про канал: Telegram не рендерит markdown-заголовки/таблицы, а ответы
# бота шлются обычным текстом — просим Claude отвечать кратко и без разметки.
_TELEGRAM_NOTE = (
    "Ты отвечаешь через Telegram-бота владельцу Блумера. Пиши кратко и по делу "
    "(в чате длинные простыни читать неудобно), обычным текстом без markdown — "
    "без #-заголовков, **звёздочек**, таблиц и код-блоков. Списки — короткими "
    "строками с «•». Эмодзи можно умеренно. Ниже — твоя полная системная инструкция.\n\n"
)


class ClaudeUnavailable(Exception):
    """reason: 'no_key' | 'api_error'."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_system_cache: str | None = None
_client: AsyncAnthropic | None = None


def load_system_prompt() -> str:
    global _system_cache
    if _system_cache is None:
        body = _SYSTEM_PATH.read_text(encoding="utf-8")
        _system_cache = _TELEGRAM_NOTE + body
    return _system_cache


def _get_client(api_key: str) -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=api_key)
    return _client


def configured(settings) -> bool:
    return bool(settings.anthropic_api_key)


async def ask(settings, question: str, context: str = "", *, extra_system: str = "") -> str:
    """Задать вопрос Claude с системным промптом «мозга» + контекстом из БД.

    extra_system — доп. инструкция под конкретную задачу (напр. «только нюхо-игра»).
    Возвращает текст ответа. Кидает ClaudeUnavailable при отсутствии ключа/ошибке.
    """
    if not settings.anthropic_api_key:
        raise ClaudeUnavailable("no_key")

    system = load_system_prompt()
    if extra_system:
        system += "\n\n" + extra_system

    user = question if not context else f"{context}\n\n— Вопрос/просьба: {question}"

    client = _get_client(settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=settings.claude_model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except APIError as e:
        log.warning("Claude API error: %s", e)
        raise ClaudeUnavailable("api_error") from e
    except Exception as e:  # сеть/таймаут/прочее — не роняем бота
        log.warning("Claude вызов не удался: %s", e)
        raise ClaudeUnavailable("api_error") from e

    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip() or "Хм, пустой ответ — попробуй переформулировать."
