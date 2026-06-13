# Notion Database Setup

## 1. Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **+ New integration**
3. Name it `المحاسب`
4. Under **Capabilities** → keep "Read content", "Update content", "Insert content" checked
5. Click **Save** → copy the **Internal Integration Secret** → this is your `NOTION_API_KEY`

## 2. Create the Database

1. In Notion, open any page and type `/database` → choose **Table - Full page**
2. Name the database: **المحاسب**
3. Set up the columns exactly as follows (names must match exactly — the bot uses them by name):

| Column name | Type   | Notes                             |
|-------------|--------|-----------------------------------|
| المتجر      | Title  | The default title column          |
| المبلغ      | Number | Format: Number (not currency)     |
| التاريخ     | Date   | —                                 |
| النوع       | Select | Add two options: `بنكي`, `يدوي`   |
| ملاحظة      | Text   | —                                 |
| البطاقة     | Text   | —                                 |

## 3. Share the Database with the Integration

1. Open the database page
2. Click **⋯** (top-right) → **Connections** → **Connect to** → search for `المحاسب`
3. Click **Confirm**

## 4. Get the Database ID

The database URL looks like:
```
https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=...
```

The 32-character string before `?v=` is the database ID. Format it as a UUID:
```
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

This goes into `NOTION_DATABASE_ID` in your `.env`.

## 5. Allow the Report Recipient to Receive Messages

The user `43444478` must start a conversation with the bot **before** `/report` can send them the PDF.

They need to:
1. Search for your bot in Telegram by its username
2. Tap **Start**

After that, the bot can send them documents. If they haven't done this, `/report` will still work for the owner — it just shows a warning that the recipient copy failed.
