# iPhone Shortcuts Setup

This shortcut runs automatically when you receive an SMS from your bank. It forwards the message to the Almuhasib webhook.

## Prerequisites

- iPhone with iOS 16+
- The "Shortcuts" app (pre-installed)
- Your VPS is running and reachable at `https://almuhasib.mohammed518.com`

## Create the Automation

1. Open the **Shortcuts** app → tap **Automation** (bottom bar) → tap **+** (top right)
2. Choose **Personal Automation**
3. Scroll down and tap **Message** (or **Messages**)
4. Set:
   - **Sender**: leave it empty; some bank sender IDs are not selectable contacts.
   - **Message Contains**: `7796` (the card token used to narrow matching messages)
5. Tap **Next**
6. Tap **Add Action** → search for **"Get Contents of URL"** → select it

### Configure the action

Tap the action to expand its settings:

| Field | Value |
|-------|-------|
| URL | `https://almuhasib.mohammed518.com/transaction` |
| Method | `POST` |
| Request Body | `JSON` |

Add JSON Body fields:

| Key | Value |
|-----|-------|
| `text` | Tap the variable picker → choose **Shortcut Input** → **Message Content** |
| `sender` | Optional: if available, choose **Shortcut Input** → **Sender** |

Tap **Add new header**:

| Key | Value |
|-----|-------|
| `X-Secret-Key` | The value of `WEBHOOK_SECRET_KEY` from your `.env` file |

7. Tap **Next**
8. Turn off **"Ask Before Running"**
9. Tap **Done**

## Test the Shortcut

You can test it manually:

1. Open the shortcut you just created
2. Tap the **▶ Run** button
3. Paste a sample SMS into the input (e.g. `شراء عبر نقاط بيع SAR 10.50\nبطاقة 7796* مدى- ApplePay\nمن MATHAF ALGHIDHA EST\nفي 21:41 26-06-13`)
4. Check your Telegram — the bot should send the formatted message

## Troubleshooting

- **Bot doesn't respond**: check `sudo journalctl -u almuhasib -f` on the VPS
- **401 Unauthorized**: the `X-Secret-Key` header doesn't match `WEBHOOK_SECRET_KEY` in `.env`
- **No automation triggered**: leave the sender filter empty and use `Message Contains: 7796`.
- **EHSAN transactions**: the server ignores messages containing `EHSAN` even if the shortcut runs.
