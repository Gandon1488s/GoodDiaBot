from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove

from db.sqlite import ensure_user, ref_register
from keyboards.menus import main_menu
from middleware.cleanup import track_message

router = Router()

WELCOME = (
    "\U0001faaa <b>T-seven Dia</b>\n\n"
    "Вітаємо на проєкті <b>T-seven Dia</b>!\n\n"
    "Тут ви отримуєте доступ до цифрового документа\n"
    "в застосунку Дія.\n\n"
    "─────────────────────────────\n"
    "<b>🎁 Зараз ми даємо 50 підписок безкоштовно!\n"
    "Щоб отримати — напишіть менеджеру:\n"
    "@Tseven_menenger</b>\n"
    "─────────────────────────────\n\n"
    "Оберіть потрібну функцію:"
)


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    uid = msg.from_user.id
    chat_id = msg.chat.id
    is_new = ensure_user(uid) is not None

    args = msg.text.split() if msg.text else []
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            inviter_id = int(args[1].split("_", 1)[1])
            ref_register(inviter_id, uid)
        except Exception:
            pass

    # Delete all previous messages in chat (up to 50 recent)
    try:
        for offset in range(1, 50):
            try:
                await msg.bot.delete_message(chat_id, msg.message_id - offset)
            except Exception:
                pass
    except Exception:
        pass

    # Remove any leftover reply keyboard
    try:
        rm = await msg.answer("\u200b", reply_markup=ReplyKeyboardRemove())
        await msg.bot.delete_message(chat_id, rm.message_id)
    except Exception:
        pass

    # Delete the /start command message itself
    try:
        await msg.bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass

    sent = await msg.answer(WELCOME, parse_mode="HTML", reply_markup=main_menu(uid))
    track_message(chat_id, sent.message_id)
