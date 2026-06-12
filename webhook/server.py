import requests
from flask import Flask, request, jsonify
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_OWNER_CHAT_ID,
    WEBHOOK_SECRET_KEY,
)
from bot.parser import parse_bank_sms, Transaction
from bot import state


def _format_message(txn: Transaction) -> str:
    return (
        f"💳 <b>عملية شراء جديدة</b>\n\n"
        f"المتجر:  <code>{txn.merchant}</code>\n"
        f"المبلغ:  <b>SAR {txn.amount:.2f}</b>\n"
        f"البطاقة: {txn.card}\n"
        f"التاريخ: {txn.datetime_str}\n\n"
        f"هل هذه العملية تحت الحساب؟"
    )


def _send_telegram_message(text: str, reply_markup: dict | None = None) -> None:
    payload: dict = {
        "chat_id": TELEGRAM_OWNER_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json=payload,
        timeout=10,
    )


def _make_transaction_keyboard(txn_id: str) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ نعم", "callback_data": f"yes:{txn_id}"},
            {"text": "📝 نعم + ملاحظة", "callback_data": f"yes_note:{txn_id}"},
            {"text": "❌ لا", "callback_data": f"no:{txn_id}"},
        ]]
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/transaction", methods=["POST"])
    def receive_transaction():
        secret = request.headers.get("X-Secret-Key", "")
        if secret != WEBHOOK_SECRET_KEY:
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json(silent=True)
        if not data or "text" not in data:
            return jsonify({"error": "Missing 'text' field"}), 400

        txn = parse_bank_sms(data["text"])
        if txn is None:
            _send_telegram_message(
                f"⚠️ رسالة غير معروفة:\n\n{data['text']}"
            )
            return jsonify({"status": "unparseable"}), 200

        txn_id = state.store_transaction(txn)
        _send_telegram_message(
            _format_message(txn),
            reply_markup=_make_transaction_keyboard(txn_id),
        )
        return jsonify({"status": "sent", "txn_id": txn_id}), 200

    return app
