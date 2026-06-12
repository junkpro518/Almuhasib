import os

# Set fake env vars before any module imports to prevent KeyError
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAFakeTokenForTestingOnly")
os.environ.setdefault("TELEGRAM_OWNER_CHAT_ID", "987654321")
os.environ.setdefault("NOTION_API_KEY", "secret_fakenotionkeyfortesting")
os.environ.setdefault("NOTION_DATABASE_ID", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
os.environ.setdefault("WEBHOOK_SECRET_KEY", "test_secret_key_12345")
os.environ.setdefault("WEBHOOK_PORT", "8080")
os.environ.setdefault("REPORT_RECIPIENT_CHAT_ID", "43444478")
