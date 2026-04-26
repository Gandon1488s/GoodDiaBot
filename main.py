import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from db.sqlite import init_db, get_expired_subscriptions, revoke_subscription
from db.supabase import clear_auth_code, upsert_telegram_user
from middleware.cleanup import MessageCleanupMiddleware, CallbackCleanupMiddleware

from handlers import start, menu, subscription, payment_stars, payment_crypto, profile, auth_code, referral, admin, documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def _subscription_expiry_checker(bot: Bot) -> None:
    """Background task: every 30s check for expired subs, revoke them and clear auth."""
    while True:
        try:
            expired = get_expired_subscriptions()
            for u in expired:
                tid = int(u["telegram_id"])
                logging.info(f"[expiry] Subscription expired for user {tid}")
                revoke_subscription(tid)
                await clear_auth_code(tid)
                await upsert_telegram_user(tid, "", False, None)
                try:
                    await bot.send_message(
                        chat_id=tid,
                        text="⏰ <b>Ваша підписка закінчилась.</b>\n\n"
                             "🔑 Код авторизації анульовано.\n"
                             "Для продовження роботи оформіть нову підписку.",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"[expiry] Error: {e}")
        await asyncio.sleep(30)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не знайдено! Задайте його в .env або bot_token.txt")

    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(MessageCleanupMiddleware())
    dp.callback_query.middleware(CallbackCleanupMiddleware())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(subscription.router)
    dp.include_router(payment_stars.router)
    dp.include_router(payment_crypto.router)
    dp.include_router(profile.router)
    dp.include_router(auth_code.router)
    dp.include_router(referral.router)
    dp.include_router(documents.router)
    dp.include_router(admin.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Головне меню"),
    ])

    logging.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(_subscription_expiry_checker(bot))
    logging.info("Subscription expiry checker started (every 30s)")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
