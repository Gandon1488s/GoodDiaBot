import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

from config import REQUIRED_CHANNELS, MANAGER
from db.sqlite import ensure_user, ref_register
from keyboards.menus import main_menu
from middleware.cleanup import track_message

router = Router()
log = logging.getLogger(__name__)

WELCOME = (
    "\U0001faaa <b>T-seven Dia</b>\n\n"
    "Вітаємо на проєкті <b>T-seven Dia</b>!\n\n"
    "Тут ви отримуєте доступ до цифрового документа\n"
    "в застосунку Дія.\n\n"
    "─────────────────────────────\n"
    "<b>🎁 Зараз ми даємо 50 підписок безкоштовно!\n"
    "Щоб отримати — напишіть менеджеру:\n"
    f"{MANAGER}</b>\n"
    "─────────────────────────────\n\n"
    "Оберіть потрібну функцію:"
)

SUB_TEXT = (
    "🔒 <b>Для використання бота необхідно підписатися на наші канали:</b>\n\n"
    "Після підписки натисніть кнопку <b>«✅ Перевірити»</b>"
)


async def check_subscriptions(bot, user_id: int) -> list[dict]:
    """Return list of channels the user is NOT subscribed to."""
    missing = []
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception as e:
            log.warning("Cannot check channel %s for user %s: %s", ch["id"], user_id, e)
            missing.append(ch)
    return missing


def sub_keyboard(missing: list[dict]) -> InlineKeyboardMarkup:
    """Build keyboard with subscribe links + check button."""
    rows = []
    for ch in missing:
        rows.append([InlineKeyboardButton(text=ch["title"], url=ch["url"])])
    rows.append([InlineKeyboardButton(text="✅  Перевірити", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _cleanup_chat(msg: Message) -> None:
    """Delete previous messages and the /start command itself."""
    chat_id = msg.chat.id
    try:
        for offset in range(1, 50):
            try:
                await msg.bot.delete_message(chat_id, msg.message_id - offset)
            except Exception:
                pass
    except Exception:
        pass

    try:
        rm = await msg.answer("\u200b", reply_markup=ReplyKeyboardRemove())
        await msg.bot.delete_message(chat_id, rm.message_id)
    except Exception:
        pass

    try:
        await msg.bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    uid = msg.from_user.id
    chat_id = msg.chat.id
    ensure_user(uid, msg.from_user.username or "")

    args = msg.text.split() if msg.text else []
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            inviter_id = int(args[1].split("_", 1)[1])
            ref_register(inviter_id, uid)
        except Exception:
            pass

    await _cleanup_chat(msg)

    # Check channel subscriptions
    missing = await check_subscriptions(msg.bot, uid)
    if missing:
        sent = await msg.answer(SUB_TEXT, parse_mode="HTML", reply_markup=sub_keyboard(missing))
        track_message(chat_id, sent.message_id)
        return

    sent = await msg.answer(WELCOME, parse_mode="HTML", reply_markup=main_menu(uid))
    track_message(chat_id, sent.message_id)


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: CallbackQuery) -> None:
    uid = cb.from_user.id
    chat_id = cb.message.chat.id

    missing = await check_subscriptions(cb.bot, uid)
    if missing:
        await cb.answer("❌ Ви ще не підписані на всі канали!", show_alert=True)
        try:
            await cb.message.edit_reply_markup(reply_markup=sub_keyboard(missing))
        except Exception:
            pass
        return

    await cb.answer("✅ Дякуємо за підписку!")
    try:
        await cb.message.delete()
    except Exception:
        pass

    sent = await cb.message.answer(WELCOME, parse_mode="HTML", reply_markup=main_menu(uid))
    track_message(chat_id, sent.message_id)
