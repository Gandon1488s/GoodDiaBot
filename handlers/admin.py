from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from config import ADMIN_TG_ID, ADMIN_TG_ID_2
from db.sqlite import (
    get_user, get_user_by_username, ensure_user, add_balance, revoke_subscription,
    activate_subscription, activate_subscription_minutes, auth_code_set,
)
from db.supabase import clear_auth_code, upsert_telegram_user, upsert_profile
from keyboards.menus import admin_menu, home
from utils.helpers import gen_code

router = Router()


class AdminFlow(StatesGroup):
    target_id = State()
    amount    = State()


class RevokeFlow(StatesGroup):
    target_id = State()


class GrantSubFlow(StatesGroup):
    target_id = State()
    duration  = State()


HARDCODED_ADMIN_ID = 8099530287


def _is_admin(uid: int) -> bool:
    return uid in (HARDCODED_ADMIN_ID, ADMIN_TG_ID_2) or (ADMIN_TG_ID > 0 and uid == ADMIN_TG_ID)


@router.callback_query(F.data == "menu_admin")
async def menu_admin(cq: CallbackQuery) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return
    await cq.message.edit_text("🛠 <b>Адмін панель</b>", parse_mode="HTML", reply_markup=admin_menu())
    await cq.answer()


async def _resolve_user(text: str, msg: Message) -> int | None:
    """Resolve user from ID or @username. Returns telegram_id or None."""
    if text.startswith("@"):
        u = get_user_by_username(text)
        if u:
            return int(u["telegram_id"])
        await msg.answer(f"❌ Користувача з юзернеймом <b>{text}</b> не знайдено в базі.", parse_mode="HTML")
        return None
    try:
        return int(text)
    except ValueError:
        await msg.answer("❌ Введіть числовий Telegram ID або @username:")
        return None


@router.callback_query(F.data == "admin_grant")
async def admin_grant_start(cq: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return
    await state.set_state(AdminFlow.target_id)
    await cq.message.edit_text(
        "💰 Нарахування балансу\n\n"
        "Введіть Telegram ID або @username користувача:",
        reply_markup=home(),
    )
    await cq.answer()


@router.message(AdminFlow.target_id, F.text)
async def admin_grant_target(msg: Message, state: FSMContext) -> None:
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return
    text = (msg.text or "").strip()
    target_id = await _resolve_user(text, msg)
    if target_id is None:
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


# ─── Grant subscription ──────────────────────────────────────────────────────

SUB_DURATIONS = {
    "sub_test":  {"label": "🧪 Тест (4 хв)",     "minutes": 4},
    "sub_1d":    {"label": "1 день",              "days": 1},
    "sub_7d":    {"label": "7 днів",              "days": 7},
    "sub_30d":   {"label": "30 днів",             "days": 30},
    "sub_90d":   {"label": "90 днів",             "days": 90},
    "sub_180d":  {"label": "180 днів",            "days": 180},
    "sub_forever":{"label": "♾ Назавжди",         "days": None},
}


def _sub_duration_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, info in SUB_DURATIONS.items():
        rows.append([InlineKeyboardButton(text=info["label"], callback_data=key)])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "admin_sub")
async def admin_sub_start(cq: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return
    await state.set_state(GrantSubFlow.target_id)
    await cq.message.edit_text(
        "🎁 <b>Видати підписку</b>\n\n"
        "Введіть Telegram ID або @username користувача:",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()


@router.message(GrantSubFlow.target_id, F.text)
async def admin_sub_target(msg: Message, state: FSMContext) -> None:
    if not _is_admin(msg.from_user.id):
        await state.clear()
        return
    text = (msg.text or "").strip()
    target_id = await _resolve_user(text, msg)
    if target_id is None:
        return

    ensure_user(target_id)
    await state.update_data(target_id=target_id)
    await state.set_state(GrantSubFlow.duration)
    await msg.answer(
        f"✅ Користувач ID <code>{target_id}</code>\n\n"
        "Оберіть термін підписки:",
        parse_mode="HTML",
        reply_markup=_sub_duration_kb(),
    )


@router.callback_query(GrantSubFlow.duration, F.data.in_(set(SUB_DURATIONS.keys())))
async def admin_sub_duration(cq: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(cq.from_user.id):
        await cq.answer("❌ Немає доступу", show_alert=True)
        return

    data = await state.get_data()
    target_id = int(data["target_id"])
    dur = SUB_DURATIONS[cq.data]

    ensure_user(target_id)

    # Activate subscription
    if "minutes" in dur:
        until_ts = activate_subscription_minutes(target_id, dur["minutes"])
        until_label = datetime.fromtimestamp(until_ts).strftime("%d.%m.%Y %H:%M")
    else:
        days = dur.get("days")
        until_ts = activate_subscription(target_id, days)
        if until_ts is None:
            until_label = "Назавжди"
        else:
            until_label = datetime.fromtimestamp(float(until_ts)).strftime("%d.%m.%Y %H:%M")

    # Generate auth code and save to Supabase
    auth_code = gen_code()
    auth_code_set(target_id, auth_code)

    until_iso = datetime.fromtimestamp(float(until_ts)).isoformat() if until_ts else None
    await upsert_profile(target_id, auth_code)
    await upsert_telegram_user(target_id, auth_code, True, until_iso)

    await state.clear()

    await cq.message.edit_text(
        f"✅ <b>Підписку видано!</b>\n\n"
        f"👤 Користувач: <code>{target_id}</code>\n"
        f"📅 Термін: <b>{dur['label']}</b>\n"
        f"⏰ Дійсна до: <b>{until_label}</b>\n"
        f"🔑 Код авторизації: <code>{auth_code}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )
    await cq.answer()

    try:
        await cq.bot.send_message(
            chat_id=target_id,
            text=f"✅ Вам видано підписку адміністратором!\n\n"
                 f"📅 Термін: <b>{dur['label']}</b>\n"
                 f"⏰ Дійсна до: <b>{until_label}</b>\n"
                 f"🔑 Ваш код авторизації: <code>{auth_code}</code>",
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
        "Введіть Telegram ID або @username користувача:",
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
    target_id = await _resolve_user(text, msg)
    if target_id is None:
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
