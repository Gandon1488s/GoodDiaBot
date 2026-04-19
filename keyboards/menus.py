from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤  Мій профіль", callback_data="menu_profile")],
        [
            InlineKeyboardButton(text="💎  Придбати підписку", callback_data="menu_buy"),
            InlineKeyboardButton(text="💳  Поповнити баланс", callback_data="menu_topup"),
        ],
        [
            InlineKeyboardButton(text="🔑  Код авторизації", callback_data="menu_auth"),
            InlineKeyboardButton(text="📲  Встановити застосунок", callback_data="menu_install"),
        ],
        [InlineKeyboardButton(text="✏️  Змінити дані профілю", callback_data="menu_edit")],
        [InlineKeyboardButton(text="✍️  Завантажити підпис", callback_data="menu_signature")],
        [
            InlineKeyboardButton(text="🤝  Реферальна програма", callback_data="menu_ref"),
            InlineKeyboardButton(text="💬  Підтримка", callback_data="menu_support"),
        ],
        [InlineKeyboardButton(text="ℹ️  Про нас", callback_data="menu_about")],
        [InlineKeyboardButton(text="🛠  Адмін панель", callback_data="menu_admin")],
    ])


def home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")]
    ])


def back_home() -> InlineKeyboardMarkup:
    return home()


def cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌  Скасувати", callback_data="menu_home")]
    ])


def buy_plans() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅  1 день  — 30 ₴",    callback_data="buy_1d")],
        [InlineKeyboardButton(text="📅  30 днів — 70 ₴",   callback_data="buy_30d")],
        [InlineKeyboardButton(text="✨  90 днів — 180 ₴",  callback_data="buy_90d")],
        [InlineKeyboardButton(text="🚀  180 днів — 320 ₴", callback_data="buy_180d")],
        [InlineKeyboardButton(text="♾️  Назавжди — 550 ₴", callback_data="buy_forever")],
        [InlineKeyboardButton(text="🏠  Головне меню",     callback_data="menu_home")],
    ])


def topup_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐  Зірками Telegram", callback_data="topup_stars")],
        [InlineKeyboardButton(text="🪙  Криптою (USDT)",   callback_data="topup_crypto")],
        [InlineKeyboardButton(text="🏠  Головне меню",     callback_data="menu_home")],
    ])


def stars_packages() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐  50 зірок  = 39 грн",  callback_data="stars_50")],
        [InlineKeyboardButton(text="⭐  100 зірок = 78 грн",  callback_data="stars_100")],
        [InlineKeyboardButton(text="⭐  200 зірок = 156 грн", callback_data="stars_200")],
        [InlineKeyboardButton(text="⭐  500 зірок = 390 грн", callback_data="stars_500")],
        [InlineKeyboardButton(text="🏠  Головне меню",        callback_data="menu_home")],
    ])


def fill_skip() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭  Пропустити заповнення", callback_data="skip_fill")]
    ])


def sex_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨  Чоловік", callback_data="sex_M"),
            InlineKeyboardButton(text="👩  Жінка",   callback_data="sex_F"),
        ],
    ])


def signature_skip() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭  Пропустити підпис", callback_data="skip_signature")]
    ])


def auth_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋  Отримати код ще раз", callback_data="copy_auth")],
        [InlineKeyboardButton(text="🏠  Головне меню",        callback_data="menu_home")],
    ])


def about_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣  Telegram-канал",  url="https://t.me/")],
        [InlineKeyboardButton(text="⭐  Відгуки",         callback_data="about_reviews")],
        [InlineKeyboardButton(text="🏠  Головне меню",    callback_data="menu_home")],
    ])


def ref_menu(can_claim: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_claim:
        rows.append([InlineKeyboardButton(text="🎁  Активувати бонус", callback_data="ref_activate")])
    rows.append([InlineKeyboardButton(text="🏠  Головне меню", callback_data="menu_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰  Нарахувати баланс",   callback_data="admin_grant")],
        [InlineKeyboardButton(text="🚫  Забрати підписку",    callback_data="admin_revoke")],
        [InlineKeyboardButton(text="🏠  Головне меню",        callback_data="menu_home")],
    ])
