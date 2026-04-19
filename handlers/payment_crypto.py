import httpx
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import CRYPTO_PAY_TOKEN, CRYPTO_PAY_API_BASE
from db.sqlite import ensure_user, get_user, add_balance, crypto_pending_store, crypto_pending_get, crypto_pending_delete, crypto_is_paid, crypto_mark_paid
from keyboards.menus import home, topup_menu
from utils.helpers import usdt_from_uah

router = Router()


class CryptoFlow(StatesGroup):
    amount = State()


async def _crypto_api(method: str, payload: dict) -> dict:
    if not CRYPTO_PAY_TOKEN:
        raise RuntimeError("CRYPTO_PAY_TOKEN не налаштовано")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            f"{CRYPTO_PAY_API_BASE}/{method}",
            headers={"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(str(data))
        result = data.get("result")
        return result if isinstance(result, dict) else {"result": result}


@router.callback_query(F.data == "topup_crypto")
async def topup_crypto_start(cq: CallbackQuery, state: FSMContext) -> None:
    ensure_user(cq.from_user.id)
    if not CRYPTO_PAY_TOKEN:
        await cq.message.edit_text(
            "❌ Крипто-оплата зараз не налаштована.\n\n"
            "Зверніться до адміністратора.",
            reply_markup=home(),
        )
        await cq.answer()
        return

    await state.set_state(CryptoFlow.amount)
    await cq.message.edit_text(
        "🪙 <b>Поповнення криптою (USDT)</b>\n\n"
        "Курс: <b>40 ₴ = 1 USDT</b>\n\n"
        "Введіть суму поповнення в гривнях (ціле число):\n"
        "Приклад: <b>100</b>",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()


@router.message(CryptoFlow.amount, F.text)
async def crypto_amount(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    try:
        uah = int(text)
        if uah <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введіть ціле число більше 0. Наприклад: <b>100</b>", parse_mode="HTML")
        return

    await state.clear()
    usdt = usdt_from_uah(uah)

    try:
        inv = await _crypto_api("createInvoice", {
            "asset": "USDT",
            "amount": usdt,
            "description": f"Поповнення балансу {uah} ₴",
            "paid_btn_name": "viewItem",
            "paid_btn_url": "https://t.me/CryptoBot",
            "allow_comments": False,
            "allow_anonymous": False,
        })
    except Exception as e:
        print(f"[crypto] createInvoice error: {e}")
        await msg.answer(
            "❌ Не вдалося створити інвойс. Спробуйте пізніше.",
            reply_markup=home(),
        )
        return

    invoice_id = int(inv.get("invoice_id") or 0)
    pay_url = str(inv.get("pay_url") or "").strip()

    if not invoice_id or not pay_url:
        await msg.answer("❌ Помилка створення інвойсу. Спробуйте пізніше.", reply_markup=home())
        return

    crypto_pending_store(invoice_id, uah, msg.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳  Оплатити USDT", url=pay_url)],
        [InlineKeyboardButton(text="🔄  Перевірити оплату", callback_data=f"crypto_check_{invoice_id}")],
        [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")],
    ])

    await msg.answer(
        "🪙 <b>Інвойс створено!</b>\n\n"
        f"💱 Курс: 40 ₴ = 1 USDT\n"
        f"💳 Сума: <b>{uah} ₴ ≈ {usdt} USDT</b>\n\n"
        "1. Натисніть «Оплатити USDT»\n"
        "2. Після оплати натисніть «Перевірити оплату»",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("crypto_check_"))
async def crypto_check(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    try:
        invoice_id = int(cq.data.split("_")[-1])
    except Exception:
        await cq.answer("❌ Некоректний інвойс", show_alert=True)
        return

    if crypto_is_paid(invoice_id):
        await cq.message.edit_text("✅ Цей інвойс вже зараховано.", reply_markup=home())
        await cq.answer()
        return

    try:
        res = await _crypto_api("getInvoices", {"invoice_ids": str(invoice_id)})
        items = res.get("items") if isinstance(res, dict) else None
        inv = items[0] if isinstance(items, list) and items else None
        status = (inv or {}).get("status")
    except Exception:
        status = None

    if status != "paid":
        await cq.message.edit_text(
            "⏳ Оплата ще не підтверджена.\n\nСпробуйте через 5–10 секунд.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄  Перевірити ще раз", callback_data=f"crypto_check_{invoice_id}")],
                [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")],
            ]),
        )
        await cq.answer()
        return

    uah = crypto_pending_get(invoice_id) or 0
    if uah <= 0:
        await cq.message.edit_text(
            "✅ Оплата підтверджена, але сума не знайдена. Зверніться до адміністратора.",
            reply_markup=home(),
        )
        crypto_mark_paid(invoice_id, 0, uid)
        crypto_pending_delete(invoice_id)
        await cq.answer()
        return

    new_balance = add_balance(uid, uah)
    crypto_mark_paid(invoice_id, uah, uid)
    crypto_pending_delete(invoice_id)

    await cq.message.edit_text(
        "✅ <b>Оплата підтверджена!</b>\n\n"
        f"💰 Зараховано: <b>{uah} ₴</b>\n"
        f"💳 Поточний баланс: <b>{new_balance} ₴</b>",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()
