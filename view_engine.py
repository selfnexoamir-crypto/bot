import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetMessagesViewsRequest
from proxy_manager import (
    get_active_proxies,
    mark_proxy_failed,
    proxy_to_telethon_format
)
from config import Config

logger = logging.getLogger(__name__)

async def _parse_post_link(link: str) -> tuple[str, int]:
    """
    Accepts:
      https://t.me/channelname/123
      https://t.me/c/1234567890/123  (private channel)
    Returns (channel_identifier, message_id)
    """
    link = link.strip().rstrip("/")
    parts = link.split("/")
    if "t.me/c/" in link:
        channel_id = int("-100" + parts[-2])
        msg_id = int(parts[-1])
        return str(channel_id), msg_id
    channel_username = parts[-2]
    msg_id = int(parts[-1])
    return channel_username, msg_id

async def _view_with_proxy(proxy: dict, channel: str, msg_id: int) -> bool:
    telethon_proxy = proxy_to_telethon_format(proxy)
    client = TelegramClient(
        StringSession(Config.SESSION_STRING),
        Config.API_ID,
        Config.API_HASH,
        proxy=telethon_proxy,
        connection_retries=2,
        timeout=15,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Session string invalid or expired.")
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
        mark_proxy_failed(proxy["host"], proxy["port"])
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

async def generate_views(post_link: str, count: int, status_callback=None) -> dict:
    channel, msg_id = await _parse_post_link(post_link)
    proxies = get_active_proxies()

    if not proxies:
        return {"success": 0, "failed": 0, "error": "No active proxies available."}

    success = 0
    failed = 0

    for i in range(count):
        proxy = proxies[i % len(proxies)]
        result = await _view_with_proxy(proxy, channel, msg_id)
        if result:
            success += 1
        else:
            failed += 1

        if status_callback:
            await status_callback(i + 1, count, success, failed)

        if i < count - 1:
            await asyncio.sleep(Config.VIEW_DELAY_SECONDS)

    return {"success": success, "failed": failed, "error": None}
