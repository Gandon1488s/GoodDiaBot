from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from db.sqlite import ensure_user, ref_register
from keyboards.menus import main_menu
from middleware.cleanup import track_message

router = Router()

WELCOME = (
    "🪪 <b>T-seven Dia</b>\n\n"
    "Вітаємо на проєкті <b>T-seven Dia</b>!\n\n"
    "Тут ви отримуєте доступ до цифрового документа\n"
    "в застосунку Дія.\n\n"
    "Оберіть потрібну функцію:"
)


@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    uid = msg.from_user.id
    is_new = ensure_user(uid) is not None

    args = msg.text.split() if msg.text else []
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            inviter_id = int(args[1].split("_", 1)[1])
            ref_register(inviter_id, uid)
        except Exception:
            pass

    sent = await msg.answer(WELCOME, parse_mode="HTML", reply_markup=main_menu())
    track_message(msg.chat.id, sent.message_id)
