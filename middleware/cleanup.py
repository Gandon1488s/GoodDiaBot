"""Middleware to auto-delete old bot messages when user sends /start."""
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

# Global store of bot message IDs per chat
_bot_msgs: Dict[int, list[int]] = defaultdict(list)


def track_message(chat_id: int, message_id: int) -> None:
    """Track a bot message for future cleanup."""
    _bot_msgs[chat_id].append(message_id)
    if len(_bot_msgs[chat_id]) > 50:
        _bot_msgs[chat_id] = _bot_msgs[chat_id][-50:]


async def cleanup_chat(bot, chat_id: int) -> None:
    """Delete all tracked bot messages in a chat."""
    ids = _bot_msgs.pop(chat_id, [])
    for mid in ids:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass


class CleanupMiddleware(BaseMiddleware):
    """On /start: delete tracked bot messages + the /start message itself."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        chat_id = event.chat.id

        if event.text and event.text.strip().startswith("/start"):
            await cleanup_chat(event.bot, chat_id)
            try:
                await event.bot.delete_message(chat_id, event.message_id)
            except Exception:
                pass

        result = await handler(event, data)
        return result
