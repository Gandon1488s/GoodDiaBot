from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.sqlite import ensure_user, auth_code_get, auth_code_set, subscription_active
from keyboards.menus import auth_menu, home

router = Router()


@router.callback_query(F.data == "menu_auth")
async def menu_auth(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    ensure_user(uid)

    if not subscription_active(uid):
        await cq.message.edit_text(
            "🔑 <b>Код авторизації</b>\n\n"
            "❌ Доступно лише після купівлі підписки.\n\n"
            "Придбайте підписку через меню → Придбати підписку.",
            parse_mode="HTML",
            reply_markup=home(),
        )
        await cq.answer()
        return

    code = auth_code_get(uid)
    if not code:
        await cq.message.edit_text(
            "❌ Код авторизації не знайдено.\n\n"
            "Спробуйте придбати підписку повторно або зверніться в підтримку.",
            reply_markup=home(),
        )
        await cq.answer()
        return

    await cq.message.edit_text(
        "🔑 <b>Ваш код авторизації</b>\n\n"
        f"<code>{code}</code>\n\n"
        "Натисніть на код щоб скопіювати, потім введіть його в застосунку:\n"
        "📲 https://dia1.pages.dev/",
        parse_mode="HTML",
        reply_markup=auth_menu(),
    )
    await cq.answer()


@router.callback_query(F.data == "copy_auth")
async def copy_auth(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    if not subscription_active(uid):
        await cq.answer("❌ Підписка не активна", show_alert=True)
        return
    code = auth_code_get(uid)
    if not code:
        await cq.answer("❌ Код не знайдено", show_alert=True)
        return
    await cq.message.answer(
        f"🔑 Ваш код: <code>{code}</code>",
        parse_mode="HTML",
    )
    await cq.answer("✅ Код надіслано")
