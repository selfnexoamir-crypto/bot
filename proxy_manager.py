import json
import os
import re
import aiohttp
from typing import Optional
from urllib.parse import urlparse, parse_qs

PROXY_STORE_PATH = "/tmp/proxies.json"


def _load() -> list[dict]:
    if not os.path.exists(PROXY_STORE_PATH):
        return []
    with open(PROXY_STORE_PATH, "r") as f:
        proxies = json.load(f)
    # Migrate: normalize any base64url secrets stored from old parse_mtproto_link
    dirty = False
    for p in proxies:
        if p.get("type") == "mtproto" and p.get("secret"):
            import re as _re
            if not _re.fullmatch(r"[0-9a-f]+", p["secret"]):
                fixed = _normalize_secret(p["secret"])
                if fixed:
                    p["secret"] = fixed
                    dirty = True
    if dirty:
        _save(proxies)
    return proxies


def _save(proxies: list[dict]) -> None:
    with open(PROXY_STORE_PATH, "w") as f:
        json.dump(proxies, f, indent=2)


# ── MTProto link parser ───────────────────────────────────────────────────────
# Handles: https://t.me/proxy?server=...&port=...&secret=...
#          tg://proxy?server=...&port=...&secret=...

def parse_mtproto_link(link: str) -> Optional[dict]:
    """
    Parse a Telegram MTProto proxy link into a proxy dict.
    Returns None if the link is not a valid MTProto proxy link.

    Secret formats supported:
      - dd<hex>  → MTProto Fake-TLS (most common)
      - ee<hex>  → MTProto obfuscated (older clients)
      - <hex>    → plain MTProto (legacy, 32 hex chars)
    """
    link = link.strip()
    # Normalise tg:// → https://t.me/ so urlparse can handle it
    link = re.sub(r"^tg://proxy\?", "https://t.me/proxy?", link, flags=re.IGNORECASE)

    try:
        parsed = urlparse(link)
    except Exception:
        return None

    host_ok = parsed.netloc in ("t.me", "telegram.me", "telegram.dog")
    path_ok = parsed.path.rstrip("/") == "/proxy"
    if not (host_ok and path_ok):
        return None

    qs = parse_qs(parsed.query)
    server_parts = qs.get("server") or qs.get("Server")
    port_parts   = qs.get("port")   or qs.get("Port")
    secret_parts = qs.get("secret") or qs.get("Secret")

    if not (server_parts and port_parts and secret_parts):
        return None

    server = server_parts[0].rstrip(".")   # strip trailing dot sometimes present
    port_str = port_parts[0]
    secret = secret_parts[0]

    if not port_str.isdigit():
        return None

    # Normalize secret — t.me/proxy encodes as base64url, not hex
    normalized = _normalize_secret(secret)
    if normalized is None:
        return None

    return {
        "host": server,
        "port": int(port_str),
        "type": "mtproto",
        "secret": normalized,
        "username": None,
        "password": None,
        "active": True,
        "fail_count": 0,
    }


def is_mtproto_link(text: str) -> bool:
    """Quick check — does this string look like a t.me/proxy link?"""
    text = text.strip()
    return bool(
        re.match(r"https?://t(?:elegram)?\.(?:me|dog)/proxy\?", text, re.IGNORECASE)
        or text.lower().startswith("tg://proxy?")
    )


# ── Core CRUD ─────────────────────────────────────────────────────────────────

def add_proxy(host: str, port: int, proxy_type: str = "socks5",
              username: Optional[str] = None, password: Optional[str] = None,
              secret: Optional[str] = None) -> bool:
    proxies = _load()
    for p in proxies:
        if p["host"] == host and p["port"] == port:
            return False
    proxies.append({
        "host": host, "port": port, "type": proxy_type,
        "username": username, "password": password,
        "secret": secret,
        "active": True, "fail_count": 0,
    })
    _save(proxies)
    return True


def add_proxy_from_link(link: str) -> Optional[dict]:
    """
    Parse an MTProto link and add it to the store.
    Returns the proxy dict on success, None if parse failed, False if duplicate.
    """
    proxy = parse_mtproto_link(link)
    if proxy is None:
        return None
    proxies = _load()
    for p in proxies:
        if p["host"] == proxy["host"] and p["port"] == proxy["port"]:
            return False
    proxies.append(proxy)
    _save(proxies)
    return proxy


def remove_proxy(host: str, port: int) -> bool:
    proxies = _load()
    new = [p for p in proxies if not (p["host"] == host and p["port"] == port)]
    _save(new)
    return len(new) < len(proxies)


def list_proxies() -> list[dict]:
    return _load()


def get_active_proxies() -> list[dict]:
    return [p for p in _load() if p["active"]]


def mark_failed(host: str, port: int) -> None:
    proxies = _load()
    for p in proxies:
        if p["host"] == host and p["port"] == port:
            p["fail_count"] += 1
            if p["fail_count"] >= 3:
                p["active"] = False
    _save(proxies)


def reset_all() -> None:
    proxies = _load()
    for p in proxies:
        p["fail_count"] = 0
        p["active"] = True
    _save(proxies)


def _normalize_secret(secret: str) -> Optional[str]:
    """
    MTProto secrets in t.me/proxy links are base64url encoded.
    Telethon needs raw bytes — we store as hex string.

    Handles:
      - Pure hex (old manual entries): "ee1603..."
      - base64url with or without padding: "7hYDB..."
    """
    import base64 as _b64
    secret = secret.strip().replace("%3D", "").replace("%3d", "")

    # Pure hex check
    if re.fullmatch(r"[0-9a-fA-F]+", secret):
        return secret.lower()

    # base64url (Telegram's actual format in t.me links)
    padded = secret + "=" * (-len(secret) % 4)
    try:
        decoded = _b64.urlsafe_b64decode(padded)
        return decoded.hex()
    except Exception:
        pass

    # standard base64 fallback
    try:
        decoded = _b64.b64decode(padded)
        return decoded.hex()
    except Exception:
        pass

    return None  # unparseable


# ── Telethon integration ──────────────────────────────────────────────────────

def proxy_to_telethon(proxy: dict) -> dict:
    """
    Convert a stored proxy dict to kwargs for TelegramClient.

    Returns a dict with keys that map directly to TelegramClient constructor:
      SOCKS5/SOCKS4/HTTP → {"proxy": (socks.TYPE, host, port, True, user, pass)}
      MTProto            → {"connection": ConnectionTcpMTProxyRandomizedIntermediate,
                            "proxy": (host, port, secret_bytes)}
    Unpack with **proxy_to_telethon(proxy) when constructing the client.
    """
    if proxy["type"] == "mtproto":
        from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
        secret_bytes = bytes.fromhex(proxy["secret"])
        return {
            "connection": ConnectionTcpMTProxyRandomizedIntermediate,
            "proxy": (proxy["host"], proxy["port"], secret_bytes),
        }

    import socks
    type_map = {"socks5": socks.SOCKS5, "socks4": socks.SOCKS4, "http": socks.HTTP}
    return {
        "proxy": (
            type_map.get(proxy["type"], socks.SOCKS5),
            proxy["host"], proxy["port"], True,
            proxy.get("username"), proxy.get("password"),
        )
    }


async def validate_proxy(proxy: dict, timeout: int = 10) -> bool:
    if proxy["type"] == "mtproto":
        # MTProto validation: attempt a raw TCP connection to host:port
        # Full Telethon handshake would require a session — TCP reachability is enough for a health check
        import asyncio
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy["host"], proxy["port"]),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    proxy_url = f"{proxy['type']}://"
    if proxy.get("username") and proxy.get("password"):
        proxy_url += f"{proxy['username']}:{proxy['password']}@"
    proxy_url += f"{proxy['host']}:{proxy['port']}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://httpbin.org/ip", proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


# ── Backward-compat aliases ───────────────────────────────────────────────────
reset_proxy_failures = reset_all
mark_proxy_failed = mark_failed
