"""
Telethon Worker — فقط اجرا می‌کنه.
هر 2 ثانیه job_queue رو چک می‌کنه.
اگه job pending بود، اجرا می‌کنه و نتیجه رو برمی‌گردونه.
هیچ کاری با کاربر مستقیم نداره — فقط با queue حرف می‌زنه.
"""

import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetMessagesViewsRequest

from config import Config
from job_queue import get_pending_job, update_job, finish_job
from proxy_manager import get_active_proxies, mark_failed, proxy_to_telethon

logger = logging.getLogger(__name__)

# ── Shared bot reference برای ارسال progress update ──────────────────────────
# از main.py inject میشه
_bot = None

def set_bot(bot):
    global _bot
    _bot = bot

# ── Link parser ───────────────────────────────────────────────────────────────
def parse_post_link(link: str) -> tuple[str, int]:
    link = link.strip().rstrip("/")
    parts = link.split("/")
    if "t.me/c/" in link:
        return str(int("-100" + parts[-2])), int(parts[-1])
    return parts[-2], int(parts[-1])

# ── Single open with one proxy ────────────────────────────────────────────────
async def _open_with_proxy(proxy: dict, channel: str, msg_id: int) -> bool:
    client = TelegramClient(
        StringSession(Config.SESSION_STRING),
        Config.API_ID,
        Config.API_HASH,
        proxy=proxy_to_telethon(proxy),
        connection_retries=2,
        timeout=15,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Session string expired.")
            return False
        entity = await client.get_entity(channel)
        await client(GetMessagesViewsRequest(
            peer=entity,
            id=[msg_id],
            increment=True
        ))
        logger.info(f"View sent via {proxy['host']}:{proxy['port']}")
        return True
    except Exception as e:
        logger.warning(f"Proxy {proxy['host']}:{proxy['port']} failed: {e}")
        mark_failed(proxy["host"], proxy["port"])
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

# ── Execute one job ───────────────────────────────────────────────────────────
async def _execute_job(job: dict) -> None:
    job_id = job["id"]
    post_link = job["post_link"]
    total_views = job["count"]
    chat_id = job["chat_id"]
    message_id = job["message_id"]

    try:
        channel, msg_id = parse_post_link(post_link)
    except Exception as e:
        await finish_job(job_id, 0, f"لینک نامعتبر: {e}")
        await _notify(chat_id, message_id, f"❌ لینک نامعتبر:\n`{post_link}`")
        return

    proxies = get_active_proxies()
    if not proxies:
        await finish_job(job_id, 0, "پروکسی فعال وجود ندارد.")
        await _notify(chat_id, message_id, "❌ هیچ پروکسی فعالی وجود ندارد.\nمالک باید پروکسی اضافه کند.")
        return

    # هر call از یه IP مجزا = یه ویو واقعی
    # opens_needed == total_views — سقف واقعی تعداد پروکسی‌هاست
    opens_needed = total_views
    available = len(proxies)
    if opens_needed > available:
        opens_needed = available

    views_done = 0
    success = 0
    failed = 0

    for i in range(opens_needed):
        proxy = proxies[i % available]
        ok = await _open_with_proxy(proxy, channel, msg_id)
        if ok:
            success += 1
            views_done += 1
        else:
            failed += 1

        # هر 5 بار یا آخر، progress رو آپدیت کن
        if (i + 1) % 5 == 0 or (i + 1) == opens_needed:
            await update_job(job_id, views_done=views_done)
            await _notify(
                chat_id, message_id,
                f"⚙️ **در حال اجرا...**\n\n"
                f"🔗 `{post_link}`\n"
                f"✅ باز شده: {i+1}/{opens_needed}\n"
                f"👁 ویو ارسالی: {views_done}\n"
                f"❌ خطا: {failed}"
            )

        if i < opens_needed - 1:
            await asyncio.sleep(Config.VIEW_DELAY_SECONDS)

    # اگه پروکسی کمتر از درخواست بود، به کاربر بگو
    note = ""
    if available < total_views:
        note = f"\n\n⚠️ فقط {available} پروکسی فعال داشتیم — {total_views - available} ویو کم موند."

    await finish_job(job_id, views_done)
    await _notify(
        chat_id, message_id,
        f"✅ **عملیات کامل شد!**\n\n"
        f"🔗 `{post_link}`\n"
        f"👁 ویو ارسالی: {views_done}\n"
        f"✅ موفق: {success} بار\n"
        f"❌ خطا: {failed} بار"
        f"{note}"
    )

# ── Notify back through bot ───────────────────────────────────────────────────
async def _notify(chat_id: int, message_id: int, text: str) -> None:
    if _bot is None:
        return
    try:
        await _bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Progress update failed: {e}")

# ── Main worker loop ──────────────────────────────────────────────────────────
async def worker_loop():
    logger.info("Telethon worker started — polling job queue every 2s")
    while True:
        try:
            job = await get_pending_job()
            if job:
                logger.info(f"Executing job {job['id']} type={job['type']}")
                if job["type"] == "view":
                    await _execute_job(job)
                else:
                    # placeholder برای ری‌اکشن و سرویس‌های بعدی
                    await finish_job(job["id"], 0, "این سرویس هنوز پیاده‌سازی نشده.")
                    await _notify(job["chat_id"], job["message_id"], "⚠️ این سرویس هنوز در دسترس نیست.")
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
        await asyncio.sleep(2)
