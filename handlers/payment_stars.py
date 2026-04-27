from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LabeledPrice

from db.sqlite import ensure_user, get_user, add_balance
from keyboards.menus import stars_packages, home

router = Router()

PACKAGES = {
    "stars_7":   7,
    "stars_39":  39,
    "stars_50":  50,
    "stars_65":  65,
    "stars_100": 100,
    "stars_200": 200,
    "stars_500": 500,
}


@router.callback_query(F.data == "topup_stars")
async def topup_stars_menu(cq: CallbackQuery) -> None:
    ensure_user(cq.from_user.id)
    await cq.message.edit_text(
        "⭐ <b>Поповнення зірками Telegram</b>\n\n"
        "Курс: <b>50 ⭐ = 39 ₴</b>\n\n"
        "💡 Купити зірки укр. картою дешевше ніж у Telegram:\n"
        "→ @FluxStar_bot\n\n"
        "Оберіть пакет:",
        parse_mode="HTML",
        reply_markup=stars_packages(),
    )
    await cq.answer()


@router.callback_query(F.data.in_(set(PACKAGES.keys())))
async def send_stars_invoice(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    ensure_user(uid)
    stars = PACKAGES[cq.data]
    from utils.helpers import uah_from_stars
    uah = uah_from_stars(stars)

    await cq.message.answer_invoice(
        title="Поповнення балансу",
        description=f"Поповнення на {uah} ₴ ({stars} ⭐ × 39/50)",
        payload=f"topup:{uid}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
    )
    await cq.answer()


@router.pre_checkout_query()
async def pre_checkout(pcq) -> None:
    await pcq.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(msg: Message) -> None:
    sp = msg.successful_payment
    if sp.currency != "XTR":
        return
    from utils.helpers import uah_from_stars
    stars = int(sp.total_amount or 0)
    uah = uah_from_stars(stars)
    uid = msg.from_user.id
    new_balance = add_balance(uid, uah)
    await msg.answer(
        "✅ <b>Оплата успішна!</b>\n\n"
        f"⭐ Отримано: <b>{stars} зірок</b>\n"
        f"💰 Зараховано: <b>{uah} ₴</b>\n"
        f"💳 Поточний баланс: <b>{new_balance} ₴</b>",
        parse_mode="HTML",
        reply_markup=home(),
    )
