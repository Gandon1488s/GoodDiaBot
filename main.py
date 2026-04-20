import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from db.sqlite import init_db
from middleware.cleanup import CleanupMiddleware

from handlers import start, menu, subscription, payment_stars, payment_crypto, profile, auth_code, referral, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не знайдено! Задайте його в .env або bot_token.txt")

    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(CleanupMiddleware())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(subscription.router)
    dp.include_router(payment_stars.router)
    dp.include_router(payment_crypto.router)
    dp.include_router(profile.router)
    dp.include_router(auth_code.router)
    dp.include_router(referral.router)
    dp.include_router(admin.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Головне меню"),
    ])

    logging.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
