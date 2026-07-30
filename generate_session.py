"""
Run this script locally with your API credentials to generate a Telethon session string.
Paste the output into TELEGRAM_SESSION_STRING in Render environment settings.
Never run this on Render directly.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(input("API_ID:"))
API_HASH = input("API_HASH:").strip()

async def gen():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()
    print("\nSession string (paste into Render TELEGRAM_SESSION_STRING):")
    print(client.session.save())
    await client.disconnect()

asyncio.run(gen())
