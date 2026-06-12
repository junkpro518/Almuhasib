import io
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
from config import REPORT_RECIPIENT_CHAT_ID

# Conversation states
WAITING_NOTE = 1
WAITING_AMOUNT = 2
WAITING_MERCHANT = 3
WAITING_MANUAL_NOTE = 4


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

    notion_client.add_entry(
        amount=txn.amount,
        merchant=txn.merchant,
        date_str=txn.datetime_str[:10],
        entry_type="بنكي",
        card=txn.card,
    )
    await query.edit_message_text(
        query.message.text + "\n\n✅ <b>تم الحفظ في الحساب</b>",
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

    notion_client.add_entry(
        amount=txn.amount,
        merchant=txn.merchant,
        date_str=txn.datetime_str[:10],
        entry_type="بنكي",
        card=txn.card,
        note=update.message.text,
    )
    await update.message.reply_text(
        f"✅ <b>تم الحفظ مع الملاحظة:</b> {update.message.text}",
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
        query.message.text + "\n\n❌ <b>تم التجاهل</b>",
        parse_mode="HTML",
    )


# ── /add manual entry conversation ────────────────────────────────────────────

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    from datetime import datetime
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
        f"المتجر: {merchant}"
        + (f"\nملاحظة: {note}" if note else ""),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END


# ── /report ───────────────────────────────────────────────────────────────────

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate PDF and send it to the owner AND to REPORT_RECIPIENT_CHAT_ID (43444478)."""
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

    # Send to report recipient (43444478)
    if REPORT_RECIPIENT_CHAT_ID != update.effective_chat.id:
        try:
            await context.bot.send_document(
                chat_id=REPORT_RECIPIENT_CHAT_ID,
                document=io.BytesIO(pdf_bytes),
                filename="تقرير-الحساب.pdf",
                caption=caption,
            )
        except Exception:
            # Don't fail if the recipient hasn't started the bot yet
            await update.message.reply_text(
                "⚠️ تعذّر إرسال التقرير للمستخدم الآخر (قد لا يكون بدأ محادثة مع البوت)."
            )


# ── /clear ────────────────────────────────────────────────────────────────────

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


# ── Handler registration ──────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    """Register all handlers on the PTB Application instance."""
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(btn_yes_note, pattern=r"^yes_note:"),
            CommandHandler("add", cmd_add),
        ],
        states={
            WAITING_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)],
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
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("clear", cmd_clear))
