# Axiom ViewBot

Telegram self-bot for automated post view generation via proxy rotation.
Built on Telethon (MTProto), deployed as a Render worker service.

---

## Setup

### 1. Get Telegram API credentials
Go to https://my.telegram.org → App Configuration → copy `API_ID` and `API_HASH`.

### 2. Generate session string (local, once)
```bash
pip install telethon
python generate_session.py
```
Paste the output string into Render as `TELEGRAM_SESSION_STRING`. Never commit it.

### 3. Find your Telegram user ID
Message `@userinfobot` on Telegram. Copy the numeric ID into `ADMIN_USER_ID`.

### 4. Deploy to Render
- Create a new **Worker** service (not Web Service — no port needed)
- Connect your repo or upload files
- Set environment variables (see below)
- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`

---

## Environment Variables (Render)

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_API_ID` | ✅ | — | From my.telegram.org |
| `TELEGRAM_API_HASH` | ✅ | — | From my.telegram.org |
| `TELEGRAM_SESSION_STRING` | ✅ | — | Output of generate_session.py |
| `ADMIN_USER_ID` | ✅ | — | Your numeric Telegram user ID |
| `VIEW_DELAY_SECONDS` | ❌ | 60 | Seconds between each view |
| `PROXY_TIMEOUT` | ❌ | 10 | Proxy validation timeout (seconds) |
| `MAX_PROXIES` | ❌ | 50 | Max proxies in pool |

---

## Commands

### Admin only
| Command | Description |
|---|---|
| `/addproxy <host> <port> [type] [user] [pass]` | Add a proxy (type: socks5/socks4/http) |
| `/removeproxy <host> <port>` | Remove a proxy |
| `/listproxies` | List all proxies with status |
| `/validateproxies` | Test all proxies live |
| `/resetproxies` | Re-enable all disabled proxies |

### All users
| Command | Description |
|---|---|
| `/view <post_link> <count>` | Generate N views (max 500) |
| `/status` | Proxy pool stats |
| `/help` | Command list |
| `/start` | Show role and help |

---

## Proxy Format Examples
```
/addproxy 192.168.1.1 1080 socks5
/addproxy 192.168.1.2 1080 socks5 myuser mypass
/addproxy 192.168.1.3 8080 http
```

---

## Post Link Formats
```
https://t.me/channelname/123
https://t.me/c/1234567890/123   ← private channels
```

---

## Proxy Persistence Note
Proxies are stored in `/tmp/proxies.json`. This resets on Render redeploy.
For persistent storage, replace `_load_raw`/`_save_raw` in `proxy_manager.py`
with a Render PostgreSQL or Redis add-on.

---

## File Structure
```
axiom-viewbot/
├── bot.py               # Main self-bot, all command handlers
├── view_engine.py       # View generation loop, proxy cycling
├── proxy_manager.py     # Proxy CRUD, validation, failure tracking
├── config.py            # Environment variable bindings
├── generate_session.py  # One-time local session string generator
├── render.yaml          # Render deployment config
├── requirements.txt     # Python dependencies
└── README.md
```
