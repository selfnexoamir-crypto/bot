import json
import os
import aiohttp
from typing import Optional

PROXY_STORE_PATH = "/tmp/proxies.json"

def _load() -> list[dict]:
    if not os.path.exists(PROXY_STORE_PATH):
        return []
    with open(PROXY_STORE_PATH, "r") as f:
        return json.load(f)

def _save(proxies: list[dict]) -> None:
    with open(PROXY_STORE_PATH, "w") as f:
        json.dump(proxies, f, indent=2)

def add_proxy(host: str, port: int, proxy_type: str = "socks5",
              username: Optional[str] = None, password: Optional[str] = None) -> bool:
    proxies = _load()
    for p in proxies:
        if p["host"] == host and p["port"] == port:
            return False
    proxies.append({
        "host": host, "port": port, "type": proxy_type,
        "username": username, "password": password,
        "active": True, "fail_count": 0
    })
    _save(proxies)
    return True

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

def proxy_to_telethon(proxy: dict) -> tuple:
    import socks
    type_map = {"socks5": socks.SOCKS5, "socks4": socks.SOCKS4, "http": socks.HTTP}
    return (
        type_map.get(proxy["type"], socks.SOCKS5),
        proxy["host"], proxy["port"], True,
        proxy.get("username"), proxy.get("password"),
    )

async def validate_proxy(proxy: dict, timeout: int = 10) -> bool:
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

# Alias: previous name before rename — kept for backward compat with stale deploy caches
reset_proxy_failures = reset_all
