"""Entry point: starts Flask webhook in a daemon thread, then runs PTB polling."""
import logging
import threading

from telegram.ext import ApplicationBuilder

from bot.handlers import register_handlers
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_PORT
from webhook.server import create_app

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _run_flask(port: int) -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=port, use_reloader=False)


def main() -> None:
    flask_thread = threading.Thread(target=_run_flask, args=(WEBHOOK_PORT,), daemon=True)
    flask_thread.start()
    logger.info("Flask webhook listening on port %s", WEBHOOK_PORT)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(application)
    logger.info("Starting Telegram bot (polling)")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
