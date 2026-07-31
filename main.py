"""
main.py — نقطه ورود اصلی
Bot API (aiogram) و Telethon worker هر دو در یک پروسه اجرا می‌شوند.
"""

import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
import worker
from handlers import start, view, services, owner, account

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(view.router)
    dp.include_router(services.router)
    dp.include_router(account.router)
    dp.include_router(owner.router)

    worker.set_bot(bot)

    logger.info("Starting bot + worker...")

    # Render web service requires an open HTTP port — health check server
    port = int(os.environ.get("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ok"))
    app.router.add_get("/health", lambda r: web.Response(text="ok"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server listening on port {port}")

    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        worker.worker_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
