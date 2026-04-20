from datetime import datetime, timedelta
import time

from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.sqlite import ensure_user, get_user, ref_stats, ref_claim_batch, _sync_patch
from keyboards.menus import ref_menu, home
from utils.helpers import fmt_date

router = Router()


def _extend_subscription(tid: int, days: int = 30) -> float:
    u = get_user(tid)
    now = time.time()
    if u and u.get("sub_until_ts") and float(u["sub_until_ts"]) > now:
        base = float(u["sub_until_ts"])
    else:
        base = now
    until_ts = (datetime.fromtimestamp(base) + timedelta(days=days)).timestamp()
    _sync_patch("bot_users", {"telegram_id": f"eq.{tid}"}, {"sub_active": True, "sub_until_ts": until_ts})
    return until_ts


@router.callback_query(F.data == "menu_ref")
async def menu_ref(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    ensure_user(uid)
    me = await cq.bot.get_me()
    username = me.username or ""
    ref_link = f"https://t.me/{username}?start=ref_{uid}" if username else "—"

    registered, paid, claimed = ref_stats(uid)
    available = paid // 3
    can_claim = available > claimed

    await cq.message.edit_text(
        "🤝 <b>Реферальна програма</b>\n\n"
        "За кожні <b>3 людини</b>, що оплатять підписку\n"
        "за вашим посиланням — ви отримуєте\n"
        "<b>30 днів підписки безкоштовно</b>.\n\n"
        "📊 <b>Ваша статистика:</b>\n"
        f"👥 Зареєстровано: <b>{registered}</b>\n"
        f"💰 Сплатили: <b>{paid}</b>\n"
        f"🎁 Доступно бонусів: <b>{max(0, available - claimed)}</b>\n\n"
        "🔗 <b>Ваше посилання:</b>\n"
        f"<code>{ref_link}</code>",
        parse_mode="HTML",
        reply_markup=ref_menu(can_claim),
    )
    await cq.answer()


@router.callback_query(F.data == "ref_activate")
async def ref_activate(cq: CallbackQuery) -> None:
    uid = cq.from_user.id
    if not ref_claim_batch(uid):
        await cq.message.edit_text(
            "ℹ️ Поки що немає доступного бонусу.\n\n"
            "Бонус видається за кожні 3 оплати за вашим посиланням.",
            reply_markup=home(),
        )
        await cq.answer()
        return

    until_ts = _extend_subscription(uid, 30)
    await cq.message.edit_text(
        "✅ <b>Бонус активовано!</b>\n\n"
        "🎁 Додано: <b>30 днів підписки</b>\n"
        f"🛠 Термін дії до: <b>{fmt_date(until_ts)}</b>",
        parse_mode="HTML",
        reply_markup=home(),
    )
    await cq.answer()
