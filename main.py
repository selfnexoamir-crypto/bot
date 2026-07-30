"""
main.py — نقطه ورود اصلی
Bot API (aiogram) و Telethon worker هر دو در یک پروسه اجرا می‌شوند.
دو coroutine موازی: bot polling + worker loop
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Config
import worker
from handlers import start, view, services, owner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    # ── Bot setup ─────────────────────────────────────────────────────────────
    bot = Bot(
        token=Config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # ── Register routers ──────────────────────────────────────────────────────
    dp.include_router(start.router)
    dp.include_router(view.router)
    dp.include_router(services.router)
    dp.include_router(owner.router)

    # ── Inject bot reference into worker ──────────────────────────────────────
    # Worker از این برای edit کردن progress messages استفاده می‌کنه
    worker.set_bot(bot)

    logger.info("Starting bot + worker...")

    # ── Run both concurrently ─────────────────────────────────────────────────
    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        worker.worker_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
