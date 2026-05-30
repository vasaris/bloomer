"""Claude API в боте (Sprint 7): /ask, свободный текст и персональная нюхо-задача.

- /ask <вопрос> или просто текст без команды → ответ Claude с системным промптом
  «мозга» (bot/blumer_system.md) + персональный контекст из БД (bot/context.py).
- Кнопка «✨ Идея под Блумера» на нюхо-карточке (nose:ai) → Claude генерит одно
  упражнение под текущий этап трюфелей / уровень (спека §7: «персональные нюхо-задачи»).

Деградация: нет ANTHROPIC_API_KEY → дружелюбная подсказка; ошибка API → мягкое
сообщение, бот не падает. Ответы шлём обычным текстом (parse_mode=None), чтобы
произвольный вывод модели не ломал HTML-парсер Telegram.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from .. import claude_client as claude, context as ctx, texts

router = Router()

_TG_LIMIT = 4000  # запас под лимит Telegram (4096)


def _chunks(text: str) -> list[str]:
    """Бьём длинный ответ на части по границам строк, влезающие в лимит Telegram."""
    if len(text) <= _TG_LIMIT:
        return [text]
    out, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > _TG_LIMIT:
            if buf:
                out.append(buf)
            # одиночная сверхдлинная строка — режем жёстко
            while len(line) > _TG_LIMIT:
                out.append(line[:_TG_LIMIT])
                line = line[_TG_LIMIT:]
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        out.append(buf)
    return out


async def _send(message: Message, text: str) -> None:
    for part in _chunks(text):
        await message.answer(part, parse_mode=None)


async def _run(message: Message, settings, question: str, *, extra_system: str = "") -> None:
    if not claude.configured(settings):
        await message.answer(texts.ASK_NO_KEY)
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    snapshot = await ctx.build_context(settings)
    try:
        answer = await claude.ask(settings, question, snapshot, extra_system=extra_system)
    except claude.ClaudeUnavailable as e:
        await message.answer(texts.ASK_NO_KEY if e.reason == "no_key" else texts.ASK_ERROR)
        return
    await _send(message, answer)


# ── /ask и свободный текст ─────────────────────────────────────
@router.message(Command("ask"))
async def cmd_ask(message: Message, command: CommandObject, settings) -> None:
    question = (command.args or "").strip()
    if not question:
        await message.answer(texts.ASK_USAGE)
        return
    await _run(message, settings, question)


@router.message(F.text & ~F.text.startswith("/"))
async def free_text(message: Message, settings) -> None:
    """Любой текст без слэша = вопрос к Claude (свободный диалог по уходу)."""
    await _run(message, settings, message.text.strip())


# ── Персональная нюхо-задача (кнопка на /nose) ─────────────────
_NOSE_BRIEF = (
    "Задача: предложи ОДНО нюховое/трюфельное упражнение на сегодня (~15 минут) "
    "именно под текущий этап трюфель-программы и уровень Блумера из контекста. "
    "Формат: название жирным словом не нужно — просто 2–4 коротких строки: что делать, "
    "зачем, на что обратить внимание. Только позитив/LIMA. Без вступлений и дисклеймеров."
)


@router.callback_query(F.data == "nose:ai")
async def on_nose_ai(cb: CallbackQuery, settings) -> None:
    if not claude.configured(settings):
        await cb.answer()
        await cb.message.answer(texts.ASK_NO_KEY)
        return
    await cb.answer("Думаю над идеей… ✨")
    await cb.bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
    snapshot = await ctx.build_context(settings)
    try:
        answer = await claude.ask(
            settings, "Нюхо-задача под Блумера на сегодня.", snapshot, extra_system=_NOSE_BRIEF
        )
    except claude.ClaudeUnavailable as e:
        await cb.message.answer(texts.ASK_NO_KEY if e.reason == "no_key" else texts.ASK_ERROR)
        return
    await cb.message.answer("✨ <b>Идея под Блумера</b>")
    await _send(cb.message, answer)
