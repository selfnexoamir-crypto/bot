import os

class Config:
    # Bot API (BotFather token)
    BOT_TOKEN: str = os.environ["BOT_TOKEN"]

    # Telethon self-bot
    API_ID: int = int(os.environ["TELEGRAM_API_ID"])
    API_HASH: str = os.environ["TELEGRAM_API_HASH"]
    SESSION_STRING: str = os.environ["TELEGRAM_SESSION_STRING"]

    # Owner
    OWNER_ID: int = int(os.environ["OWNER_USER_ID"])

    # Tuning
    VIEW_DELAY_SECONDS: int = int(os.environ.get("VIEW_DELAY_SECONDS", "3"))
    VIEWS_PER_OPEN: int = int(os.environ.get("VIEWS_PER_OPEN", "20"))
    PROXY_TIMEOUT: int = int(os.environ.get("PROXY_TIMEOUT", "10"))

    # Job queue file (shared between bot and worker on same process)
    JOB_QUEUE_PATH: str = "/tmp/job_queue.json"
