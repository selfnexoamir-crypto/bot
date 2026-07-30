import os

class Config:
    API_ID: int = int(os.environ["TELEGRAM_API_ID"])
    API_HASH: str = os.environ["TELEGRAM_API_HASH"]
    SESSION_STRING: str = os.environ["TELEGRAM_SESSION_STRING"]
    ADMIN_ID: int = int(os.environ["ADMIN_USER_ID"])
    VIEW_DELAY_SECONDS: int = int(os.environ.get("VIEW_DELAY_SECONDS", "60"))
    MAX_PROXIES: int = int(os.environ.get("MAX_PROXIES", "50"))
    PROXY_TIMEOUT: int = int(os.environ.get("PROXY_TIMEOUT", "10"))
