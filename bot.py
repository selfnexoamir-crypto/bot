import asyncio
import logging
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from config import Config
from proxy_manager import (
    add_proxy,
    remove_proxy,
    list_proxies,
    get_active_proxies,
    reset_proxy_failures,
    validate_proxy,
)
from view_engine import generate_views

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

client = TelegramClient(
    StringSession(Config.SESSION_STRING),
    Config.API_ID,
    Config.API_HASH,
)

def is_admin(user_id: int) -> bool:
    return user_id == Config.ADMIN_ID

HELP_TEXT_ADMIN = """
**Axiom ViewBot — Admin Panel**

**View Generation:**
`/view <post_link> <count>` — Generate N views on a post

**Proxy Management:**
`/addproxy <host> <port> [socks5|socks4|http] [user] [pass]`
`/removeproxy <host> <port>`
`/listproxies` — List all proxies with status
`/validateproxies` — Test all proxies and mark failures
`/resetproxies` — Re-enable all disabled proxies

**System:**
`/status` — Current proxy pool stats
`/help` — This panel
""".strip()

HELP_TEXT_MEMBER = """
**Axiom ViewBot**

`/view <post_link> <count>` — Generate views on a post
`/status` — Proxy pool status
`/help` — This message
""".strip()

@client.on(events.NewMessage(pattern=r"^/start$"))
async def handle_start(event):
    uid = event.sender_id
    role = "Admin" if is_admin(uid) else "Member"
    await event.respond(
        f"ViewBot online. Role: **{role}**\n\n" +
        (HELP_TEXT_ADMIN if is_admin(uid) else HELP_TEXT_MEMBER)
    )

@client.on(events.NewMessage(pattern=r"^/help$"))
async def handle_help(event):
    uid = event.sender_id
    await event.respond(HELP_TEXT_ADMIN if is_admin(uid) else HELP_TEXT_MEMBER)

@client.on(events.NewMessage(pattern=r"^/status$"))
async def handle_status(event):
    all_proxies = list_proxies()
    active = [p for p in all_proxies if p["active"]]
    inactive = [p for p in all_proxies if not p["active"]]
    await event.respond(
        f"**Proxy Pool Status**\n"
        f"Total: {len(all_proxies)}\n"
        f"Active: {len(active)}\n"
        f"Disabled (3+ failures): {len(inactive)}\n"
        f"View delay: {Config.VIEW_DELAY_SECONDS}s between views"
    )

@client.on(events.NewMessage(pattern=r"^/view (.+) (\d+)$"))
async def handle_view(event):
    match = event.pattern_match
    post_link = match.group(1).strip()
    count = int(match.group(2))

    if count > 500:
        await event.respond("Cap is 500 views per command.")
        return

    if not re.match(r"https?://t\.me/.+/\d+", post_link):
        await event.respond("Invalid post link. Use `https://t.me/channel/123` format.")
        return

    active_proxies = get_active_proxies()
    if not active_proxies:
        await event.respond("No active proxies. Add proxies first with `/addproxy`.")
        return

    progress_msg = await event.respond(
        f"Starting {count} views on:\n`{post_link}`\n\nEstimated time: ~{count} min"
    )

    async def status_cb(current, total, success, failed):
        if current % 5 == 0 or current == total:
            try:
                await progress_msg.edit(
                    f"Progress: {current}/{total}\n"
                    f"Success: {success} | Failed: {failed}"
                )
            except Exception:
                pass

    result = await generate_views(post_link, count, status_callback=status_cb)

    await progress_msg.edit(
        f"**View job complete.**\n"
        f"Sent: {result['success']}\n"
        f"Failed: {result['failed']}\n"
        + (f"Error: {result['error']}" if result["error"] else "")
    )

@client.on(events.NewMessage(pattern=r"^/addproxy (\S+) (\d+)(?:\s+(socks5|socks4|http))?(?:\s+(\S+)\s+(\S+))?$"))
async def handle_add_proxy(event):
    if not is_admin(event.sender_id):
        await event.respond("Admin only.")
        return
    m = event.pattern_match
    host = m.group(1).strip()
    port = int(m.group(2))
    ptype = m.group(3) or "socks5"
    username = m.group(4)
    password = m.group(5)

    added = add_proxy(host, port, ptype, username, password)
    if added:
        await event.respond(f"Proxy added: `{host}:{port}` ({ptype})")
    else:
        await event.respond(f"Proxy `{host}:{port}` already exists.")

@client.on(events.NewMessage(pattern=r"^/removeproxy (\S+) (\d+)$"))
async def handle_remove_proxy(event):
    if not is_admin(event.sender_id):
        await event.respond("Admin only.")
        return
    host = event.pattern_match.group(1)
    port = int(event.pattern_match.group(2))
    removed = remove_proxy(host, port)
    msg = f"Removed `{host}:{port}`." if removed else f"Not found: `{host}:{port}`."
    await event.respond(msg)

@client.on(events.NewMessage(pattern=r"^/listproxies$"))
async def handle_list_proxies(event):
    if not is_admin(event.sender_id):
        await event.respond("Admin only.")
        return
    proxies = list_proxies()
    if not proxies:
        await event.respond("No proxies configured.")
        return
    lines = []
    for p in proxies:
        status = "✅" if p["active"] else f"❌ ({p['fail_count']} fails)"
        auth = f" [{p['username']}]" if p.get("username") else ""
        lines.append(f"{status} `{p['host']}:{p['port']}` {p['type']}{auth}")
    await event.respond("\n".join(lines))

@client.on(events.NewMessage(pattern=r"^/validateproxies$"))
async def handle_validate_proxies(event):
    if not is_admin(event.sender_id):
        await event.respond("Admin only.")
        return
    proxies = list_proxies()
    if not proxies:
        await event.respond("No proxies to validate.")
        return
    msg = await event.respond(f"Validating {len(proxies)} proxies...")
    results = await asyncio.gather(*[validate_proxy(p, Config.PROXY_TIMEOUT) for p in proxies])
    passed = sum(results)
    await msg.edit(f"Validation complete.\nPassed: {passed}/{len(proxies)}")

@client.on(events.NewMessage(pattern=r"^/resetproxies$"))
async def handle_reset_proxies(event):
    if not is_admin(event.sender_id):
        await event.respond("Admin only.")
        return
    reset_proxy_failures()
    await event.respond("All proxies re-enabled. Fail counters cleared.")

async def main():
    logger.info("Connecting ViewBot session...")
    await client.start()
    logger.info("ViewBot running.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
