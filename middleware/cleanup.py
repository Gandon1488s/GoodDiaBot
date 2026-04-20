"""Middleware to auto-delete previous bot message when a new one is sent.

How it works:
- Every time the bot sends or edits a message, we track that message_id.
- When the bot sends/edits the NEXT message, the previous one gets deleted.
- Result: only the latest bot message stays in chat.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

# Store last bot message ID per chat
_last_bot_msg: Dict[int, int] = {}


def track_message(chat_id: int, message_id: int) -> None:
    """Track a bot message as the latest one in this chat."""
    _last_bot_msg[chat_id] = message_id


async def delete_previous(bot, chat_id: int) -> None:
    """Delete the previously tracked bot message."""
    mid = _last_bot_msg.pop(chat_id, None)
    if mid:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass


class MessageCleanupMiddleware(BaseMiddleware):
    """For message handlers: delete previous bot msg + user's text message."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        chat_id = event.chat.id

        # Delete previous bot message
        await delete_previous(event.bot, chat_id)

        # Delete user's own text message (keeps chat clean)
        # Don't delete photos/documents — they may be needed by handlers
        if event.text or event.web_app_data:
            try:
                await event.bot.delete_message(chat_id, event.message_id)
            except Exception:
                pass

        result = await handler(event, data)
        return result


class CallbackCleanupMiddleware(BaseMiddleware):
    """For callback handlers: track the message being edited so it can be
    deleted later when a NEW message is sent (e.g. reply keyboard answer)."""

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)

        # After handler runs, track the message that was edited
        if event.message:
            track_message(event.message.chat.id, event.message.message_id)

        return result
