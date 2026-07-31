"""
Telethon Worker — فقط اجرا می‌کنه.
هر 2 ثانیه job_queue رو چک می‌کنه.
اگه job pending بود، اجرا می‌کنه و نتیجه رو برمی‌گردونه.
هیچ کاری با کاربر مستقیم نداره — فقط با queue حرف می‌زنه.
"""

import asyncio
import logging
import re

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetMessagesViewsRequest
from telethon.tl.types import InputChannel, InputPeerChannel

from config import Config
from job_queue import get_pending_job, update_job, finish_job
from proxy_manager import get_active_proxies, mark_failed, proxy_to_telethon
from session_manager import get_active_sessions, mark_session_failed

logger = logging.getLogger(__name__)

_bot = None

def set_bot(bot):
    global _bot
    _bot = bot


# ── Link parser ───────────────────────────────────────────────────────────────

def parse_post_link(link: str) -> tuple[int, int]:
    """
    Returns (channel_id, msg_id).
    channel_id is always a negative int (-100...) for supergroups/channels.
    Public username links return 0 as channel_id (resolved later).
    """
    link = link.strip().rstrip("/")

    # Private channel: t.me/c/1234567890/99
    m = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if m:
        return int("-100" + m.group(1)), int(m.group(2))

    # Public channel: t.me/username/99
    m = re.search(r"t\.me/([A-Za-z0-9_]+)/(\d+)", link)
    if m:
        return m.group(1), int(m.group(2))  # username string

    raise ValueError(f"Cannot parse post link: {link}")


# ── Resolve entity once (no proxy, direct DC) ─────────────────────────────────

async def _resolve_entity(channel) -> tuple:
    """
    Returns (channel_id: int, access_hash: int) pair.
    Uses first active session, direct connection — called once per job.
    """
    sessions = get_active_sessions()
    if not sessions:
        raise RuntimeError("No active sessions. Add an account from the owner panel.")
    session_str = sessions[0]["session_string"]
    client = TelegramClient(
        StringSession(session_str),
        Config.API_ID,
        Config.API_HASH,
        connection_retries=2,
        receive_updates=False,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("SESSION_STRING is invalid or expired.")
        entity = await client.get_entity(channel)
        return entity.id, entity.access_hash
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


# ── Single view through one proxy ─────────────────────────────────────────────

async def _open_with_proxy(
    proxy: dict,
    session: dict,
    channel_id: int,
    access_hash: int,
    msg_id: int,
) -> bool:
    """
    Send one GetMessagesViewsRequest through the given proxy + session pair.

    InputChannel is built locally from (channel_id, access_hash).
    Each TelegramClient connects through a different proxy → different egress
    IP → Telegram counts it as a unique view.
    """
    proxy_kwargs = proxy_to_telethon(proxy)
    timeout = Config.PROXY_TIMEOUT

    client = TelegramClient(
        StringSession(session["session_string"]),
        Config.API_ID,
        Config.API_HASH,
        connection_retries=1,
        retry_delay=0,
        timeout=timeout,
        request_retries=1,
        receive_updates=False,
        **proxy_kwargs,
    )
    try:
        await asyncio.wait_for(client.connect(), timeout=timeout)

        if not await client.is_user_authorized():
            logger.error("SESSION_STRING invalid/expired.")
            return False

        input_channel = InputChannel(channel_id=channel_id, access_hash=access_hash)

        await asyncio.wait_for(
            client(GetMessagesViewsRequest(
                peer=input_channel,
                id=[msg_id],
                increment=True,
            )),
            timeout=timeout,
        )
        logger.info(f"✅ View → {proxy['host']}:{proxy['port']}")
        return True

    except asyncio.TimeoutError:
        logger.warning(f"⏱ Timeout: {proxy['host']}:{proxy['port']}")
        mark_failed(proxy["host"], proxy["port"])
        return False
    except Exception as e:
        logger.warning(f"❌ {proxy['host']}:{proxy['port']} — {type(e).__name__}: {e}")
        mark_failed(proxy["host"], proxy["port"])
        if "AUTH_KEY" in str(e) or "SessionRevoked" in type(e).__name__:
            mark_session_failed(session["phone"])
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


# ── Execute one job ───────────────────────────────────────────────────────────

async def _execute_job(job: dict) -> None:
    job_id    = job["id"]
    post_link = job["post_link"]
    total     = job["count"]
    chat_id   = job["chat_id"]
    msg_id_bot = job["message_id"]

    try:
        channel_ref, msg_id = parse_post_link(post_link)
    except Exception as e:
        await finish_job(job_id, 0, f"لینک نامعتبر: {e}")
        await _notify(chat_id, msg_id_bot, f"❌ لینک نامعتبر:\n`{post_link}`")
        return

    # Resolve once — get (channel_id, access_hash)
    try:
        channel_id, access_hash = await _resolve_entity(channel_ref)
    except Exception as e:
        await finish_job(job_id, 0, f"Channel resolve failed: {e}")
        await _notify(chat_id, msg_id_bot, f"❌ کانال پیدا نشد: `{channel_ref}`\nخطا: {e}")
        return

    proxies   = get_active_proxies()
    available = len(proxies)

    if available == 0:
        await finish_job(job_id, 0, "پروکسی فعال وجود ندارد.")
        await _notify(chat_id, msg_id_bot, "❌ هیچ پروکسی فعالی وجود ندارد.\nمالک باید پروکسی اضافه کند.")
        return

    opens_needed = min(total, available)
    views_done   = 0
    success      = 0
    failed       = 0

    sessions = get_active_sessions()
    if not sessions:
        await finish_job(job_id, 0, "هیچ اکانت فعالی وجود ندارد.")
        await _notify(chat_id, msg_id_bot, "❌ هیچ اکانت فعالی وجود ندارد.\nاز پنل مالک اکانت اضافه کن.")
        return

    for i in range(opens_needed):
        proxy = proxies[i]
        session = sessions[i % len(sessions)]  # rotate across sessions
        ok = await _open_with_proxy(proxy, session, channel_id, access_hash, msg_id)
        if ok:
            success += 1
            views_done += 1
        else:
            failed += 1

        if (i + 1) % 5 == 0 or (i + 1) == opens_needed:
            await update_job(job_id, views_done=views_done)
            await _notify(
                chat_id, msg_id_bot,
                f"⚙️ **در حال اجرا...**\n\n"
                f"🔗 `{post_link}`\n"
                f"✅ باز شده: {i+1}/{opens_needed}\n"
                f"👁 ویو ارسالی: {views_done}\n"
                f"❌ خطا: {failed}"
            )

        if i < opens_needed - 1:
            await asyncio.sleep(Config.VIEW_DELAY_SECONDS)

    note = ""
    if available < total:
        note = f"\n\n⚠️ فقط {available} پروکسی فعال داشتیم — {total - available} ویو کم موند."

    await finish_job(job_id, views_done)
    await _notify(
        chat_id, msg_id_bot,
        f"✅ **عملیات کامل شد!**\n\n"
        f"🔗 `{post_link}`\n"
        f"👁 ویو ارسالی: {views_done}\n"
        f"✅ موفق: {success}\n"
        f"❌ خطا: {failed}"
        f"{note}"
    )


# ── Notify via bot ────────────────────────────────────────────────────────────

async def _notify(chat_id: int, message_id: int, text: str) -> None:
    if _bot is None:
        return
    try:
        await _bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="Markdown",
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
                    await finish_job(job["id"], 0, "این سرویس هنوز پیاده‌سازی نشده.")
                    await _notify(job["chat_id"], job["message_id"], "⚠️ این سرویس هنوز در دسترس نیست.")
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
        await asyncio.sleep(2)
