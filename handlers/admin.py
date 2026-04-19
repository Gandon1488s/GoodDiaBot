from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_TG_ID
from db.sqlite import get_user, ensure_user, add_balance, revoke_subscription
from db.supabase import clear_auth_code, upsert_telegram_user
from keyboards.menus import admin_menu, home

router = Router()


class AdminFlow(StatesGroup):
    target_id = State()
    amount    = State()


class RevokeFlow(StatesGroup):
    target_id = State()


HARDCODED_ADMIN_ID = 8099530287


def _is_admin(uid: int) -> bool:
    return uid == HARDCODED_ADMIN_ID or (ADMIN_TG_ID > 0 and uid == ADMIN_TG_ID)


@router.callback_query(F.data == "menu_admin")
async def menu_admin(cq: CallbackQuery) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return
    await cq.message.edit_text("🛠 <b>Адмін панель</b>", parse_mode="HTML", reply_markup=admin_menu())
    await cq.answer()


@router.callback_query(F.data == "admin_grant")
async def admin_grant_start(cq: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return
    await state.set_state(AdminFlow.target_id)
    await cq.message.edit_text(
        "💰 Нарахування балансу\n\n"
        "Введіть Telegram ID користувача:",
        reply_markup=home(),
    )
    await cq.answer()


@router.message(AdminFlow.target_id, F.text)
async def admin_grant_target(msg: Message, state: FSMContext) -> None:
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return
    text = (msg.text or "").strip()
    try:
        target_id = int(text)
    except ValueError:
        await msg.answer("❌ Введіть числовий Telegram ID:")
        return

    ensure_user(target_id)
    await state.update_data(target_id=target_id)
    await state.set_state(AdminFlow.amount)
    await msg.answer(
        f"✅ Користувач ID <code>{target_id}</code>\n\nВведіть суму (₴) для нарахування:",
        parse_mode="HTML",
    )


@router.message(AdminFlow.amount, F.text)
async def admin_grant_amount(msg: Message, state: FSMContext) -> None:
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return
    text = (msg.text or "").strip()
    try:
        amount = int(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введіть ціле число більше 0:")
        return

    data = await state.get_data()
    target_id = int(data["target_id"])
    new_balance = add_balance(target_id, amount)
    await state.clear()

    await msg.answer(
        f"✅ Нараховано <b>{amount} ₴</b> користувачу <b>{target_id}</b>.\n"
        f"💰 Новий баланс: <b>{new_balance} ₴</b>",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )

    try:
        await msg.bot.send_message(
            chat_id=target_id,
            text=f"✅ Ваш баланс поповнено адміністратором на <b>{amount} ₴</b>.",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ─── Revoke subscription ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_revoke")
async def admin_revoke_start(cq: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return
    await state.set_state(RevokeFlow.target_id)
    await cq.message.edit_text(
        "🚫 <b>Забрати підписку</b>\n\n"
        "Введіть Telegram ID користувача:",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()


@router.message(RevokeFlow.target_id, F.text)
async def admin_revoke_target(msg: Message, state: FSMContext) -> None:
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return
    text = (msg.text or "").strip()
    try:
        target_id = int(text)
    except ValueError:
        await msg.answer("❌ Введіть числовий Telegram ID:")
        return

    ensure_user(target_id)
    revoke_subscription(target_id)

    # Очистити auth_code в Supabase profiles і telegram_users
    await clear_auth_code(target_id)
    await upsert_telegram_user(target_id, "", False, None)

    await state.clear()

    await msg.answer(
        f"✅ Підписку забрано у користувача <code>{target_id}</code>.\n"
        f"🔑 Код авторизації видалено з бази даних.",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )

    try:
        await msg.bot.send_message(
            chat_id=target_id,
            text="❌ Вашу підписку було деактивовано адміністратором.\n"
                 "Код авторизації анульовано.",
            parse_mode="HTML",
        )
    except Exception:
        pass
