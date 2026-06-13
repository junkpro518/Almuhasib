import html
import io
import logging
import os
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from bot import state
from notion import client as notion_client
from notion.client import extract_entries_for_pdf
from pdf.generator import generate_report
from config import REPORT_RECIPIENT_CHAT_ID, TELEGRAM_OWNER_CHAT_ID
from receipts.store import clear_receipts, normalize_extension, save_receipt

logger = logging.getLogger(__name__)

# Conversation states
WAITING_NOTE = 1
WAITING_AMOUNT = 2
WAITING_MERCHANT = 3
WAITING_MANUAL_NOTE = 4
WAITING_RECEIPT = 5
WAITING_NOTE_WITH_RECEIPT = 6


def _is_owner(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == TELEGRAM_OWNER_CHAT_ID


def _can_confirm_transfer(update: Update) -> bool:
    return (
        update.effective_user is not None
        and update.effective_user.id in {TELEGRAM_OWNER_CHAT_ID, REPORT_RECIPIENT_CHAT_ID}
    )


def _save_bank_entry(txn, note: str = "") -> dict:
    return notion_client.add_entry(
        amount=txn.amount,
        merchant=txn.merchant,
        date_str=txn.datetime_str[:10],
        entry_type="بنكي",
        card=txn.card,
        note=note,
    )


# ── Transaction button callbacks ──────────────────────────────────────────────

async def btn_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ✅ نعم — save transaction to Notion without note."""
    query = update.callback_query
    await query.answer()
    txn_id = query.data.split(":", 1)[1]
    txn = state.pop_transaction(txn_id)

    if txn is None:
        await query.edit_message_text("⚠️ انتهت صلاحية هذه العملية.")
        return

    _save_bank_entry(txn)
    await query.edit_message_text(
        query.message.text_html + "\n\n✅ <b>تم الحفظ في الحساب</b>",
        parse_mode="HTML",
    )


async def btn_yes_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 📝 نعم + ملاحظة — store txn_id then ask for note."""
    query = update.callback_query
    await query.answer()
    txn_id = query.data.split(":", 1)[1]
    context.user_data["pending_txn_id"] = txn_id
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="📝 أرسل ملاحظتك:",
    )
    return WAITING_NOTE


async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive note text after ✅+📝, save transaction with note."""
    txn_id = context.user_data.pop("pending_txn_id", None)
    txn = state.pop_transaction(txn_id) if txn_id else None

    if txn is None:
        await update.message.reply_text("⚠️ انتهت صلاحية هذه العملية.")
        return ConversationHandler.END

    note_text = update.message.text
    _save_bank_entry(txn, note=note_text)
    await update.message.reply_text(
        f"✅ <b>تم الحفظ مع الملاحظة:</b> {html.escape(note_text)}",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def btn_yes_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 📎 نعم + فاتورة — ask for receipt image before saving."""
    query = update.callback_query
    await query.answer()
    txn_id = query.data.split(":", 1)[1]
    context.user_data["pending_receipt_txn_id"] = txn_id
    context.user_data.pop("pending_receipt_note", None)
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="📎 أرسل صورة الفاتورة لهذه العملية. الصورة للتوثيق فقط ولا تدخل في الحساب.",
    )
    return WAITING_RECEIPT


async def btn_yes_note_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 📝📎 ملاحظة + فاتورة."""
    query = update.callback_query
    await query.answer()
    txn_id = query.data.split(":", 1)[1]
    context.user_data["pending_receipt_txn_id"] = txn_id
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="📝 أرسل ملاحظتك أولا، وبعدها سأطلب صورة الفاتورة:",
    )
    return WAITING_NOTE_WITH_RECEIPT


async def handle_note_then_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pending_receipt_note"] = update.message.text
    await update.message.reply_text("📎 الآن أرسل صورة الفاتورة. الصورة للتوثيق فقط ولا تدخل في الحساب.")
    return WAITING_RECEIPT


async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save transaction with a receipt photo/document."""
    txn_id = context.user_data.get("pending_receipt_txn_id")
    txn = state.get_transaction(txn_id) if txn_id else None
    if txn is None:
        context.user_data.pop("pending_receipt_txn_id", None)
        context.user_data.pop("pending_receipt_note", None)
        await update.message.reply_text("⚠️ انتهت صلاحية هذه العملية.")
        return ConversationHandler.END

    document = update.message.document
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        extension = ".jpg"
    elif document and document.mime_type and document.mime_type.startswith("image/"):
        file_id = document.file_id
        extension = normalize_extension(document.file_name, document.mime_type)
    else:
        await update.message.reply_text("أرسل صورة الفاتورة كصورة أو كملف صورة.")
        return WAITING_RECEIPT

    note = context.user_data.pop("pending_receipt_note", "")
    context.user_data.pop("pending_receipt_txn_id", None)

    tmp_path = None
    try:
        telegram_file = await context.bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp_path = tmp.name
        await telegram_file.download_to_drive(tmp_path)

        txn = state.pop_transaction(txn_id)
        if txn is None:
            await update.message.reply_text("⚠️ انتهت صلاحية هذه العملية.")
            return ConversationHandler.END

        page = _save_bank_entry(txn, note=note)
        page_id = str(page.get("id", txn_id))
        receipt_path = save_receipt(page_id, tmp_path, extension)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    await update.message.reply_text(
        "✅ تم حفظ العملية مع الفاتورة.\n"
        f"📎 الفاتورة محفوظة للتوثيق فقط: {html.escape(receipt_path.name)}",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def btn_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ❌ لا — discard transaction."""
    query = update.callback_query
    await query.answer()
    txn_id = query.data.split(":", 1)[1]
    state.pop_transaction(txn_id)
    await query.edit_message_text(
        query.message.text_html + "\n\n❌ <b>تم التجاهل</b>",
        parse_mode="HTML",
    )


# ── /add manual entry conversation ────────────────────────────────────────────

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_owner(update):
        return ConversationHandler.END
    await update.message.reply_text("كم المبلغ؟ (سالب للخصم، مثال: -30)")
    return WAITING_AMOUNT


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amount = float(text.replace(',', ''))
    except ValueError:
        await update.message.reply_text("❌ رقم غير صحيح. أرسل المبلغ مرة أخرى:")
        return WAITING_AMOUNT

    context.user_data["manual_amount"] = amount
    await update.message.reply_text("ما المتجر أو الوصف؟")
    return WAITING_MERCHANT


async def handle_merchant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["manual_merchant"] = update.message.text.strip()
    await update.message.reply_text("ملاحظة إضافية؟ (أرسل /skip للتخطي)")
    return WAITING_MANUAL_NOTE


async def handle_manual_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note = update.message.text.strip()
    return await _save_manual_entry(update, context, note)


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _save_manual_entry(update, context, "")


async def _save_manual_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE, note: str
) -> int:
    amount = context.user_data.pop("manual_amount", 0.0)
    merchant = context.user_data.pop("manual_merchant", "—")
    date_str = datetime.now().strftime("%Y-%m-%d")

    notion_client.add_entry(
        amount=amount,
        merchant=merchant,
        date_str=date_str,
        entry_type="يدوي",
        note=note,
    )
    sign = "+" if amount >= 0 else ""
    await update.message.reply_text(
        f"✅ <b>تم الحفظ</b>\n"
        f"المبلغ: <b>SAR {sign}{amount:,.2f}</b>\n"
        f"المتجر: {html.escape(merchant)}"
        + (f"\nملاحظة: {html.escape(note)}" if note else ""),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END


# ── /report ───────────────────────────────────────────────────────────────────

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate PDF and send it to the owner AND to REPORT_RECIPIENT_CHAT_ID."""
    if not _is_owner(update):
        return

    await update.message.reply_text("⏳ جاري إنشاء التقرير...")
    entries_raw = notion_client.get_all_entries()
    entries = extract_entries_for_pdf(entries_raw)

    if not entries:
        await update.message.reply_text("لا توجد عمليات مسجلة بعد.")
        return

    pdf_bytes = generate_report(entries)
    total = sum(e["amount"] for e in entries)
    caption = f"📊 التقرير — {len(entries)} عملية | الإجمالي: SAR {total:,.2f}"

    # Send to owner
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(pdf_bytes),
        filename="تقرير-الحساب.pdf",
        caption=caption,
    )

    # Send to report recipient
    if REPORT_RECIPIENT_CHAT_ID != update.effective_chat.id:
        try:
            await context.bot.send_document(
                chat_id=REPORT_RECIPIENT_CHAT_ID,
                document=io.BytesIO(pdf_bytes),
                filename="تقرير-الحساب.pdf",
                caption=caption,
            )
            transfer_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تم التحويل", callback_data="transfer_done"),
                InlineKeyboardButton("❌ لم يتم التحويل", callback_data="transfer_pending"),
            ]])
            await context.bot.send_message(
                chat_id=REPORT_RECIPIENT_CHAT_ID,
                text="هل تم تحويل مبلغ هذا التقرير؟",
                reply_markup=transfer_keyboard,
            )
        except Exception:
            logger.warning("Failed to send report to recipient %s", REPORT_RECIPIENT_CHAT_ID)
            await update.message.reply_text(
                "⚠️ تعذّر إرسال التقرير للمستخدم الآخر (قد لا يكون بدأ محادثة مع البوت)."
            )


# ── /clear ────────────────────────────────────────────────────────────────────

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ نعم، امسح الكل", callback_data="clear_confirm"),
        InlineKeyboardButton("❌ إلغاء", callback_data="clear_cancel"),
    ]])
    await update.message.reply_text(
        "⚠️ <b>هل أنت متأكد؟</b>\nسيتم حذف جميع العمليات المسجلة.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def btn_clear_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    count = notion_client.clear_all_entries()
    await query.edit_message_text(f"✅ تم حذف {count} عملية. الحساب الآن فارغ.")


async def btn_clear_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("تم الإلغاء.")


async def btn_transfer_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _can_confirm_transfer(update):
        return
    count = notion_client.clear_all_entries()
    receipt_count = clear_receipts()
    await query.edit_message_text(
        "✅ تم الانتهاء من الحساب وسيتم بدء حساب جديد.\n"
        f"تم أرشفة {count} عملية ومسح {receipt_count} فاتورة محلية."
    )


async def btn_transfer_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _can_confirm_transfer(update):
        return
    await query.edit_message_text("تم تسجيل أن التحويل لم يتم بعد. الحساب الحالي سيبقى مفتوحا.")


# ── Handler registration ──────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    """Register all handlers on the PTB Application instance."""
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(btn_yes_note, pattern=r"^yes_note:"),
            CallbackQueryHandler(btn_yes_receipt, pattern=r"^yes_receipt:"),
            CallbackQueryHandler(btn_yes_note_receipt, pattern=r"^yes_note_receipt:"),
            CommandHandler("add", cmd_add),
        ],
        states={
            WAITING_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)],
            WAITING_NOTE_WITH_RECEIPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note_then_receipt)],
            WAITING_RECEIPT: [
                MessageHandler((filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_receipt)
            ],
            WAITING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            WAITING_MERCHANT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_merchant)],
            WAITING_MANUAL_NOTE: [
                CommandHandler("skip", cmd_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_note),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(btn_yes, pattern=r"^yes:"))
    app.add_handler(CallbackQueryHandler(btn_no, pattern=r"^no:"))
    app.add_handler(CallbackQueryHandler(btn_clear_confirm, pattern=r"^clear_confirm$"))
    app.add_handler(CallbackQueryHandler(btn_clear_cancel, pattern=r"^clear_cancel$"))
    app.add_handler(CallbackQueryHandler(btn_transfer_done, pattern=r"^transfer_done$"))
    app.add_handler(CallbackQueryHandler(btn_transfer_pending, pattern=r"^transfer_pending$"))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("clear", cmd_clear))
