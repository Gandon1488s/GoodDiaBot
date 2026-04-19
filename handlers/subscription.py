from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from db.sqlite import (
    ensure_user, get_user, deduct_balance, activate_subscription,
    auth_code_set, ref_mark_paid,
)
from db.supabase import upsert_profile, upsert_telegram_user, get_profile
from keyboards.menus import buy_plans, home, fill_skip
from utils.helpers import gen_code, fmt_dt, fmt_date
from handlers.profile import FillProfile

router = Router()

PLANS = {
    "buy_1d":      (30,  1),
    "buy_30d":     (70,  30),
    "buy_90d":     (180, 90),
    "buy_180d":    (320, 180),
    "buy_forever": (550, None),
}


@router.callback_query(F.data == "menu_buy")
async def show_buy(cq: CallbackQuery) -> None:
    ensure_user(cq.from_user.id)
    await cq.message.edit_text(
        "💎 <b>Преміум підписка</b>\n\n"
        "Після активації ви зможете:\n"
        "• Увійти в застосунок із кодом авторизації\n"
        "• Завантажити своє фото і підпис\n"
        "• Поділитись QR-кодом документа\n\n"
        "Оберіть термін:",
        parse_mode="HTML",
        reply_markup=buy_plans(),
    )
    await cq.answer()


@router.callback_query(F.data.in_(set(PLANS.keys())))
async def process_buy(cq: CallbackQuery, state: FSMContext) -> None:
    uid = cq.from_user.id
    ensure_user(uid)
    user = get_user(uid)
    price_uah, days = PLANS[cq.data]
    balance = int(user["balance_uah"] or 0)

    if balance < price_uah:
        await cq.message.edit_text(
            "❌ <b>Недостатньо коштів на балансі.</b>\n\n"
            f"💰 Ваш баланс: <b>{balance} ₴</b>\n"
            f"💳 Вартість плану: <b>{price_uah} ₴</b>\n"
            f"📉 Не вистачає: <b>{price_uah - balance} ₴</b>\n\n"
            "Поповніть баланс через меню → Поповнити баланс.",
            parse_mode="HTML",
            reply_markup=home(),
        )
        await cq.answer()
        return

    deduct_balance(uid, price_uah)
    until_ts = activate_subscription(uid, days)
    ref_mark_paid(uid)

    # ── Supabase ──────────────────────────────────────────────────────────────
    auth_code = gen_code()
    auth_code_set(uid, auth_code)

    until_iso = datetime.fromtimestamp(float(until_ts)).isoformat() if until_ts else None

    await upsert_profile(uid, auth_code)
    await upsert_telegram_user(uid, auth_code, True, until_iso)
    # ─────────────────────────────────────────────────────────────────────────

    until_label = "Назавжди" if until_ts is None else fmt_date(until_ts)
    user_after = get_user(uid)
    new_balance = int((dict(user_after) if user_after else {}).get("balance_uah") or 0)

    # Start post-purchase fill flow
    await state.set_state(FillProfile.photo)
    await state.update_data(auth_code=auth_code)

    await cq.message.edit_text(
        "✅ <b>Підписку активовано!</b>\n\n"
        f"💳 Списано: <b>{price_uah} ₴</b>\n"
        f"💰 Залишок: <b>{new_balance} ₴</b>\n"
        f"🛠 Термін дії: <b>{until_label}</b>\n\n"
        f"🔑 Ваш код авторизації: <code>{auth_code}</code>\n\n"
        "─────────────────────────────\n"
        "📸 <b>Крок 1 з 3 — Фото</b>\n\n"
        "Надішліть ваше фото у форматі 3×4:\n"
        "• Чітке обличчя, рівний фон\n"
        "• Пропорції портрет (3×4)\n"
        "• Не використовуйте фото публічних осіб",
        parse_mode="HTML",
        reply_markup=fill_skip(),
    )
    await cq.answer()
