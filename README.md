# Axiom ViewBot — معماری دو لایه

## معماری
```
کاربر تلگرام
     ↓
[Bot API — aiogram]          ← رابط کاربری، inline keyboards، FSM
     ↓ push_job()
[job_queue.json]             ← صف مشترک بین دو لایه
     ↓ get_pending_job()
[Telethon Worker]            ← فقط اجرا می‌کنه، ویو می‌زنه
     ↓ edit_message_text()
[Bot API — progress update]  ← نتیجه رو به کاربر برمی‌گردونه
```

## ساختار فایل‌ها
```
axiom-viewbot/
├── main.py                  # entry point — bot + worker موازی
├── config.py                # متغیرهای محیطی
├── worker.py                # Telethon self-bot، اجرای job
├── job_queue.py             # صف job بین bot و worker
├── proxy_manager.py         # مدیریت پروکسی
├── keyboards.py             # همه inline keyboard ها
├── states.py                # FSM states (aiogram)
├── handlers/
│   ├── __init__.py
│   ├── start.py             # /start، /menu، /panel
│   ├── view.py              # فلوی کامل ویو گرفتن
│   ├── services.py          # ری‌اکشن، ممبر، لایک (placeholder)
│   └── owner.py             # مدیریت پروکسی + جاب‌ها
├── generate_session.py      # یک بار لوکال اجرا کنید
├── render.yaml
└── requirements.txt
```

## راه‌اندازی

### ۱. ساخت ربات در BotFather
```
به @BotFather پیام دهید
/newbot
نام ربات را وارد کنید
توکن را کپی کنید → BOT_TOKEN
```

### ۲. API Credentials تلگرام
به my.telegram.org بروید → App Configuration
`API_ID` و `API_HASH` را کپی کنید.

### ۳. Session String (لوکال، یک بار)
```bash
pip install telethon
python generate_session.py
```
خروجی = `TELEGRAM_SESSION_STRING`

### ۴. OWNER_USER_ID
به @userinfobot پیام دهید → عدد را کپی کنید.

### ۵. Render — Worker Service
- New → Background Worker
- Start Command: `python main.py`
- Build Command: `pip install -r requirements.txt`

## متغیرهای محیطی Render

| متغیر | اجباری | توضیح |
|---|---|---|
| `BOT_TOKEN` | ✅ | از BotFather |
| `TELEGRAM_API_ID` | ✅ | از my.telegram.org |
| `TELEGRAM_API_HASH` | ✅ | از my.telegram.org |
| `TELEGRAM_SESSION_STRING` | ✅ | از generate_session.py |
| `OWNER_USER_ID` | ✅ | آیدی عددی مالک |
| `VIEW_DELAY_SECONDS` | ❌ | پیش‌فرض: 3 |
| `VIEWS_PER_OPEN` | ❌ | پیش‌فرض: 20 |
| `PROXY_TIMEOUT` | ❌ | پیش‌فرض: 10 |

## دستورات ربات

### همه کاربران
- `/start` — منوی اصلی با دکمه‌های سرویس
- `/menu` — منوی اصلی

### فقط مالک
- `/panel` — پنل مدیریت پروکسی

## فرمت پروکسی (از پنل مالک)
```
1.2.3.4 1080 socks5
1.2.3.4 1080 socks5 username password
1.2.3.4 8080 http
```
