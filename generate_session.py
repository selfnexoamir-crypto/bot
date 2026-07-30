"""
یک بار روی سیستم لوکال اجرا کنید.
خروجی را در Render به عنوان TELEGRAM_SESSION_STRING وارد کنید.
هرگز روی سرور اجرا نکنید.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(input("API_ID: "))
API_HASH = input("API_HASH: ").strip()

async def gen():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()
    print("\n✅ Session String (در Render وارد کنید):")
    print(client.session.save())
    await client.disconnect()

asyncio.run(gen())
