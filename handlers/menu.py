from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from db.sqlite import ensure_user, get_user, subscription_active, auth_code_get
from keyboards.menus import main_menu, home, about_menu, topup_menu
from utils.helpers import fmt_dt, fmt_date
from config import APP_URL, MANAGER, MANAGER2, MANAGER3

router = Router()

WELCOME = (
    "\U0001faaa <b>T-seven Dia</b>\n\n"
    "Вітаємо на проєкті <b>T-seven Dia</b>!\n\n"
    "Ваш цифровий документ у застосунку Дія —\n"
    "завжди під рукою, на будь-якому смартфоні.\n\n"
    "─────────────────────────────\n"
    "📋 Оформлення за 2 хвилини\n"
    "🔒 Безпечне зберігання даних\n"
    "📲 Працює на iPhone та Android\n"
    "💬 Підтримка 24/7\n"
    "─────────────────────────────\n\n"
    "Оберіть потрібну функцію:"
)


@router.callback_query(F.data == "menu_home")
async def menu_home(cq: CallbackQuery, state: FSMContext) -> None:
    ensure_user(cq.from_user.id, cq.from_user.username or "")
    await state.clear()
    # Remove any leftover reply keyboard (e.g. from signature WebApp)
    try:
        rm = await cq.message.answer("\u200b", reply_markup=ReplyKeyboardRemove())
        await cq.bot.delete_message(cq.message.chat.id, rm.message_id)
    except Exception:
        pass
    await cq.message.edit_text(WELCOME, parse_mode="HTML", reply_markup=main_menu(cq.from_user.id))
    await cq.answer()


@router.callback_query(F.data == "menu_profile")
async def menu_profile(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    ensure_user(uid)
    user = get_user(uid)
    is_active = subscription_active(uid)
    u = dict(user) if user else {}

    balance = int(u.get("balance_uah") or 0)
    sub_label = "✅ Активна" if is_active else "❌ Не активна"
    sub_at = fmt_dt(u.get("sub_at_ts"))
    sub_until_ts = u.get("sub_until_ts")
    if is_active and sub_until_ts is None:
        sub_until = "Назавжди ♾️"
    else:
        sub_until = fmt_date(sub_until_ts) if sub_until_ts else "—"

    code = auth_code_get(uid) or "—"

    await cq.message.edit_text(
        "👤 <b>Мій профіль</b>\n\n"
        f"🆔 Telegram ID: <code>{uid}</code>\n"
        f"💰 Баланс: <b>{balance} ₴</b>\n\n"
        f"💎 Підписка: {sub_label}\n"
        f"� Активована: {sub_at}\n"
        f"🛠 Діє до: {sub_until}\n\n"
        f"🔑 Код авторизації:\n<code>{code}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️  Змінити дані", callback_data="menu_edit")],
            [InlineKeyboardButton(text="✍️  Завантажити підпис", callback_data="menu_signature")],
            [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")],
        ]),
    )
    await cq.answer()


@router.callback_query(F.data == "menu_topup")
async def menu_topup(cq: CallbackQuery) -> None:
    ensure_user(cq.from_user.id)
    await cq.message.edit_text(
        "➕ <b>Поповнення балансу</b>\n\n"
        "Оберіть зручний спосіб:\n\n"
        "⭐ <b>Зірками Telegram</b>\n"
        "Оплата прямо в Telegram\n"
        "💡 Купити Stars укр. картою: @FluxStar_bot\n\n"
        "🪙 <b>Криптою (USDT)</b>\n"
        "Оплата через CryptoBot\n\n"
        "💳 <b>Оплата карткою</b>\n"
        "Напишіть менеджеру — він працює 24/7\n"
        "та допоможе з оплатою і будь-якими питаннями.\n"
        f"👤 {MANAGER}\n"
        f"👤 {MANAGER2}\n"
        f"👤 {MANAGER3}",
        parse_mode="HTML",
        reply_markup=topup_menu(),
    )
    await cq.answer()


@router.callback_query(F.data == "menu_install")
async def menu_install(cq: CallbackQuery) -> None:
    ensure_user(cq.from_user.id)
    await cq.message.edit_text(
        "📲 <b>Встановити застосунок</b>\n\n"
        f"🔗 Посилання: {APP_URL}\n\n"
        "⚠️ <b>Увага:</b> Додаток працює лише на смартфонах!\n"
        "Відкрийте посилання на <b>iPhone</b> або <b>Android</b>.\n\n"
        "📖 <b>Інструкція:</b>\n"
        "1. Відкрийте посилання у браузері телефону\n"
        "2. Натисніть «Додати на головний екран»\n"
        "3. Відкрийте додаток з іконки\n\n"
        "💡 Після першого запуску перезапустіть\n"
        "додаток для стабільної роботи.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📲  Відкрити посилання", url=APP_URL)],
            [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")],
        ]),
    )
    await cq.answer()


@router.callback_query(F.data == "menu_support")
async def menu_support(cq: CallbackQuery) -> None:
    await cq.message.edit_text(
        "💬 <b>Підтримка 24/7</b>\n\n"
        "Потрібна допомога? Напишіть менеджеру —\n"
        "відповідь зазвичай протягом хвилини.\n\n"
        "✅ Підключення та налаштування\n"
        "✅ Оплата / підписка / баланс\n"
        "✅ Будь-які питання по сервісу\n\n"
        f"👤 Менеджер: {MANAGER}\n"
        f"👤 Менеджер: {MANAGER2}\n"
        f"👤 Менеджер: {MANAGER3}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💬  {MANAGER}", url=f"https://t.me/{MANAGER.lstrip('@')}")],
            [InlineKeyboardButton(text=f"💬  {MANAGER2}", url=f"https://t.me/{MANAGER2.lstrip('@')}")],
            [InlineKeyboardButton(text=f"💬  {MANAGER3}", url=f"https://t.me/{MANAGER3.lstrip('@')}")],
            [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")],
        ]),
    )
    await cq.answer()


@router.callback_query(F.data == "menu_about")
async def menu_about(cq: CallbackQuery) -> None:
    await cq.message.edit_text(
        "ℹ️ <b>Про нас</b>\n\n"
        "T-seven Dia — сервіс цифрових документів.\n\n"
        "📣 Підпишіться на канал — там новини та оновлення.\n"
        "⭐ Перегляньте відгуки реальних користувачів.\n"
        "💬 Приєднуйтесь до чату спілкування!",
        parse_mode="HTML",
        reply_markup=about_menu(),
    )
    await cq.answer()
