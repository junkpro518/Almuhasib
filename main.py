"""Entry point: starts Flask webhook in a daemon thread, then runs PTB polling."""
import logging
import threading

from telegram import BotCommand
from telegram.ext import ApplicationBuilder

from bot.handlers import register_handlers
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_PORT
from webhook.server import create_app

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _run_flask(port: int) -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def _set_bot_commands(application) -> None:
    await application.bot.set_my_commands([
        BotCommand("add", "إضافة عملية يدوية"),
        BotCommand("report", "إرسال تقرير الحساب PDF"),
        BotCommand("clear", "مسح الحساب الحالي بعد تأكيد"),
        BotCommand("cancel", "إلغاء العملية الحالية"),
        BotCommand("skip", "تخطي الملاحظة أثناء الإضافة"),
    ])
    logger.info("Telegram bot commands were installed")


def main() -> None:
    flask_thread = threading.Thread(target=_run_flask, args=(WEBHOOK_PORT,), daemon=True)
    flask_thread.start()
    logger.info("Flask webhook listening on port %s", WEBHOOK_PORT)

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_set_bot_commands)
        .build()
    )
    register_handlers(application)
    logger.info("Starting Telegram bot (polling)")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
