import hmac
import html
import logging
import requests
from flask import Flask, request, jsonify
from config import (
    EXCLUDED_SMS_TOKENS,
    REQUIRED_CARD_TOKENS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_OWNER_CHAT_ID,
    WEBHOOK_SECRET_KEY,
)
from bot.parser import parse_bank_sms, Transaction
from bot import state


logger = logging.getLogger(__name__)


def _format_message(txn: Transaction) -> str:
    return (
        f"💳 <b>عملية شراء جديدة</b>\n\n"
        f"المتجر:  <code>{html.escape(txn.merchant)}</code>\n"
        f"المبلغ:  <b>SAR {txn.amount:.2f}</b>\n"
        f"البطاقة: {html.escape(txn.card)}\n"
        f"التاريخ: {txn.datetime_str}\n\n"
        f"هل هذه العملية تحت الحساب؟"
    )


def _send_telegram_message(text: str, reply_markup: dict | None = None) -> bool:
    """Send a message to the bot owner. Returns True on success."""
    payload: dict = {
        "chat_id": TELEGRAM_OWNER_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        )
        return resp.ok
    except requests.exceptions.RequestException:
        return False


def _make_transaction_keyboard(txn_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ نعم", "callback_data": f"yes:{txn_id}"},
                {"text": "📝 نعم + ملاحظة", "callback_data": f"yes_note:{txn_id}"},
            ],
            [
                {"text": "📎 نعم + فاتورة", "callback_data": f"yes_receipt:{txn_id}"},
                {"text": "📝📎 ملاحظة + فاتورة", "callback_data": f"yes_note_receipt:{txn_id}"},
            ],
            [{"text": "❌ لا", "callback_data": f"no:{txn_id}"}],
        ]
    }


def _message_allowed(text: str) -> tuple[bool, str | None]:
    normalized = text.casefold()
    if any(token in normalized for token in EXCLUDED_SMS_TOKENS):
        return False, "excluded_token"
    if REQUIRED_CARD_TOKENS and not any(token in normalized for token in REQUIRED_CARD_TOKENS):
        return False, "missing_required_card_token"
    return True, None


def _log_webhook_outcome(status: str, reason: str | None, sender: object, text: object) -> None:
    """Log routing decisions without exposing full bank SMS contents."""
    text_value = text if isinstance(text, str) else ""
    normalized = text_value.casefold()
    logger.info(
        "transaction_webhook status=%s reason=%s sender_present=%s text_len=%s has_required_token=%s has_excluded_token=%s",
        status,
        reason or "-",
        bool(sender),
        len(text_value),
        bool(REQUIRED_CARD_TOKENS and any(token in normalized for token in REQUIRED_CARD_TOKENS)),
        any(token in normalized for token in EXCLUDED_SMS_TOKENS),
    )


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/transaction", methods=["POST"])
    def receive_transaction():
        secret = request.headers.get("X-Secret-Key", "")
        if not hmac.compare_digest(secret.encode(), WEBHOOK_SECRET_KEY.encode()):
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(silent=True)
        if not data or "text" not in data:
            _log_webhook_outcome("bad_request", "missing_text", None, None)
            return jsonify({"error": "Missing 'text' field"}), 400

        sender = data.get("sender")
        text = data["text"]
        if not isinstance(text, str):
            _log_webhook_outcome("bad_request", "text_not_string", sender, text)
            return jsonify({"error": "'text' field must be a string"}), 400

        allowed, reason = _message_allowed(text)
        if not allowed:
            _log_webhook_outcome("ignored", reason, sender, text)
            return jsonify({"status": "ignored", "reason": reason}), 200

        txn = parse_bank_sms(text)
        if txn is None:
            _log_webhook_outcome("unparseable", None, sender, text)
            _send_telegram_message(f"⚠️ رسالة غير معروفة:\n\n{html.escape(text)}")
            return jsonify({"status": "unparseable"}), 200

        txn_id = state.store_transaction(txn)
        ok = _send_telegram_message(
            _format_message(txn),
            reply_markup=_make_transaction_keyboard(txn_id),
        )
        if not ok:
            state.pop_transaction(txn_id)  # rollback — don't leave orphan in state
            _log_webhook_outcome("error", "telegram_delivery_failed", sender, text)
            return jsonify({"status": "error", "detail": "Telegram delivery failed"}), 502

        _log_webhook_outcome("sent", None, sender, text)
        return jsonify({"status": "sent", "txn_id": txn_id}), 200

    return app
