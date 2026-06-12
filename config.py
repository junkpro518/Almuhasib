import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_OWNER_CHAT_ID: int = int(os.environ["TELEGRAM_OWNER_CHAT_ID"])
NOTION_API_KEY: str = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID: str = os.environ["NOTION_DATABASE_ID"]
WEBHOOK_SECRET_KEY: str = os.environ["WEBHOOK_SECRET_KEY"]
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))
