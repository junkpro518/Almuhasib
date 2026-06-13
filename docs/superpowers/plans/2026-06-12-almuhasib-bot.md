# Almuhasib Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram bot that receives bank purchase notifications from iPhone Shortcuts, lets the user mark transactions as "تحت الحساب", stores them in Notion, and generates PDF reports.

**Architecture:** iPhone Shortcuts sends raw bank SMS text via HTTP POST to a Flask endpoint on VPS. Flask parses the SMS and sends a formatted Telegram message with inline buttons directly via the Bot API. python-telegram-bot (v20, async polling) handles button callbacks, conversation flows (/add, /report, /clear). Both Flask and PTB run in the same Python process — Flask in a daemon thread, PTB in the main asyncio loop.

**Tech Stack:** Python 3.11+, python-telegram-bot 20.x, notion-client 2.x, flask 3.x, fpdf2 2.7.x, arabic-reshaper, python-bidi, python-dotenv, requests, pytest

---

## File Structure

```
almuhasib/
├── config.py                  # All settings from env vars
├── main.py                    # Entry point: Flask thread + PTB polling
├── requirements.txt
├── .env.example
├── .gitignore
├── almuhasib.service          # systemd unit file
├── bot/
│   ├── __init__.py
│   ├── handlers.py            # All Telegram handlers + ConversationHandler
│   ├── parser.py              # Bank SMS regex parser → Transaction dataclass
│   └── state.py               # Thread-safe shared state (pending transactions)
├── notion/
│   ├── __init__.py
│   └── client.py              # Notion CRUD: add_entry, get_all_entries, clear_all, get_total
├── pdf/
│   ├── __init__.py
│   ├── generator.py           # fpdf2 PDF with Arabic headers
│   └── fonts/                 # Arabic font files (Amiri-Regular.ttf)
├── webhook/
│   ├── __init__.py
│   └── server.py              # Flask app factory: POST /transaction
└── tests/
    ├── conftest.py             # Env var fixtures
    ├── test_parser.py
    ├── test_notion_client.py
    ├── test_pdf_generator.py
    └── test_webhook.py
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.py`
- Create: `tests/conftest.py`
- Create: all `__init__.py` files

- [ ] **Step 1: Create directory structure**

```bash
cd /path/to/almuhasib
mkdir -p bot notion pdf/fonts webhook tests
touch bot/__init__.py notion/__init__.py pdf/__init__.py webhook/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

```
python-telegram-bot==20.7
notion-client==2.2.1
flask==3.0.3
fpdf2==2.7.9
arabic-reshaper==3.0.0
python-bidi==0.6.0
python-dotenv==1.0.1
requests==2.32.3
pytest==8.2.2
pytest-asyncio==0.23.7
```

- [ ] **Step 3: Write .env.example**

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_OWNER_CHAT_ID=your_chat_id_here
NOTION_API_KEY=secret_xxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
WEBHOOK_SECRET_KEY=choose_a_strong_random_secret
WEBHOOK_PORT=8080
```

- [ ] **Step 4: Write .gitignore**

```
.env
__pycache__/
*.py[cod]
*.pyc
.pytest_cache/
*.pdf
venv/
.venv/
```

- [ ] **Step 5: Write config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_OWNER_CHAT_ID: int = int(os.environ["TELEGRAM_OWNER_CHAT_ID"])
NOTION_API_KEY: str = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID: str = os.environ["NOTION_DATABASE_ID"]
WEBHOOK_SECRET_KEY: str = os.environ["WEBHOOK_SECRET_KEY"]
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))
```

- [ ] **Step 6: Write tests/conftest.py**

```python
import os

# Set fake env vars before any module imports to prevent KeyError
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:AAFakeTokenForTestingOnly")
os.environ.setdefault("TELEGRAM_OWNER_CHAT_ID", "987654321")
os.environ.setdefault("NOTION_API_KEY", "secret_fakenotionkeyfortesting")
os.environ.setdefault("NOTION_DATABASE_ID", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
os.environ.setdefault("WEBHOOK_SECRET_KEY", "test_secret_key_12345")
os.environ.setdefault("WEBHOOK_PORT", "8080")
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 8: Commit**

```bash
git init
git add .
git commit -m "chore: initial project scaffold"
```

---

## Task 2: SMS Parser (TDD)

**Files:**
- Create: `bot/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_parser.py
from bot.parser import parse_bank_sms, Transaction

SAMPLE_SMS = """شراء عبر نقاط بيع SAR 10.50
بطاقة 7796* مدى- ApplePay
من MATHAF ALGHIDHA EST
في 21:41 26-06-13"""

def test_parse_amount():
    result = parse_bank_sms(SAMPLE_SMS)
    assert result is not None
    assert result.amount == 10.50

def test_parse_merchant():
    result = parse_bank_sms(SAMPLE_SMS)
    assert result.merchant == "MATHAF ALGHIDHA EST"

def test_parse_card():
    result = parse_bank_sms(SAMPLE_SMS)
    assert result.card == "7796* مدى- ApplePay"

def test_parse_datetime():
    result = parse_bank_sms(SAMPLE_SMS)
    assert result.datetime_str == "2026-06-13 21:41"

def test_parse_invalid_returns_none():
    result = parse_bank_sms("hello world not a bank message")
    assert result is None

def test_parse_large_amount():
    sms = """شراء عبر نقاط بيع SAR 1,250.00
بطاقة 7796* مدى- ApplePay
من SOME STORE
في 10:00 26-06-14"""
    result = parse_bank_sms(sms)
    assert result.amount == 1250.00
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_parser.py -v
```

Expected: `ImportError: cannot import name 'parse_bank_sms'`

- [ ] **Step 3: Write bot/parser.py**

```python
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    amount: float
    merchant: str
    card: str
    datetime_str: str  # "YYYY-MM-DD HH:MM"


def parse_bank_sms(text: str) -> Optional[Transaction]:
    """Parse a Saudi bank purchase SMS into a Transaction.

    Expected format:
        شراء عبر نقاط بيع SAR 10.50
        بطاقة 7796* مدى- ApplePay
        من MATHAF ALGHIDHA EST
        في 21:41 26-06-13
    """
    # Amount: SAR followed by digits, optional comma-thousands, decimal
    amount_match = re.search(r'SAR\s+([\d,]+\.?\d*)', text)
    card_match = re.search(r'بطاقة\s+(.+?)(?:\n|$)', text)
    merchant_match = re.search(r'من\s+(.+?)(?:\n|$)', text)
    # Date: HH:MM YY-MM-DD  (e.g. 21:41 26-06-13)
    dt_match = re.search(r'في\s+(\d{2}:\d{2})\s+(\d{2})-(\d{2})-(\d{2})', text)

    if not all([amount_match, card_match, merchant_match, dt_match]):
        return None

    amount_str = amount_match.group(1).replace(',', '')
    yy, mm, dd = dt_match.group(2), dt_match.group(3), dt_match.group(4)
    datetime_str = f"20{yy}-{mm}-{dd} {dt_match.group(1)}"

    return Transaction(
        amount=float(amount_str),
        merchant=merchant_match.group(1).strip(),
        card=card_match.group(1).strip(),
        datetime_str=datetime_str,
    )
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add bot/parser.py tests/test_parser.py
git commit -m "feat: add SMS parser with TDD"
```

---

## Task 3: Shared State (Flask ↔ PTB)

**Files:**
- Create: `bot/state.py`

- [ ] **Step 1: Write bot/state.py**

```python
import uuid
from threading import Lock
from typing import Optional
from bot.parser import Transaction

_lock = Lock()
_pending: dict[str, Transaction] = {}


def store_transaction(txn: Transaction) -> str:
    """Store a pending transaction and return its 8-char ID."""
    txn_id = uuid.uuid4().hex[:8]
    with _lock:
        _pending[txn_id] = txn
    return txn_id


def pop_transaction(txn_id: str) -> Optional[Transaction]:
    """Retrieve and remove a pending transaction by ID. Returns None if not found."""
    with _lock:
        return _pending.pop(txn_id, None)
```

- [ ] **Step 2: Commit**

```bash
git add bot/state.py
git commit -m "feat: add thread-safe pending transaction state"
```

---

## Task 4: Notion Client (TDD)

**Files:**
- Create: `notion/client.py`
- Create: `tests/test_notion_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_notion_client.py
from unittest.mock import MagicMock, patch, call
import pytest
import notion.client as nc


@pytest.fixture(autouse=True)
def mock_notion_client(monkeypatch):
    """Replace the notion SDK client with a MagicMock for all tests."""
    mock = MagicMock()
    monkeypatch.setattr(nc, "notion", mock)
    return mock


def test_add_entry_creates_page(mock_notion_client):
    mock_notion_client.pages.create.return_value = {"id": "page-id-1"}

    result = nc.add_entry(
        amount=10.50,
        merchant="MATHAF ALGHIDHA EST",
        date_str="2026-06-13",
        entry_type="بنكي",
        card="7796* مدى- ApplePay",
        note="",
    )

    assert mock_notion_client.pages.create.called
    kwargs = mock_notion_client.pages.create.call_args[1]
    props = kwargs["properties"]
    assert props["المبلغ"]["number"] == 10.50
    assert props["النوع"]["select"]["name"] == "بنكي"


def test_add_entry_includes_note_when_provided(mock_notion_client):
    mock_notion_client.pages.create.return_value = {"id": "page-id-2"}

    nc.add_entry(
        amount=50.0,
        merchant="مطعم",
        date_str="2026-06-13",
        entry_type="يدوي",
        note="استرجاع",
    )

    kwargs = mock_notion_client.pages.create.call_args[1]
    props = kwargs["properties"]
    assert props["ملاحظة"]["rich_text"][0]["text"]["content"] == "استرجاع"


def test_get_total_sums_all_amounts(mock_notion_client):
    mock_notion_client.databases.query.return_value = {
        "results": [
            {"properties": {"المبلغ": {"number": 10.50}}},
            {"properties": {"المبلغ": {"number": 20.00}}},
            {"properties": {"المبلغ": {"number": -5.00}}},
        ]
    }

    total = nc.get_total()
    assert total == pytest.approx(25.50)


def test_clear_all_archives_each_entry(mock_notion_client):
    mock_notion_client.databases.query.return_value = {
        "results": [{"id": "id-1"}, {"id": "id-2"}, {"id": "id-3"}]
    }

    count = nc.clear_all_entries()

    assert count == 3
    assert mock_notion_client.pages.update.call_count == 3
    # Each call should archive the page
    for c in mock_notion_client.pages.update.call_args_list:
        assert c[1]["archived"] is True
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_notion_client.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write notion/client.py**

```python
from notion_client import Client
from config import NOTION_API_KEY, NOTION_DATABASE_ID

notion = Client(auth=NOTION_API_KEY)


def add_entry(
    amount: float,
    merchant: str,
    date_str: str,       # "YYYY-MM-DD"
    entry_type: str,     # "بنكي" or "يدوي"
    card: str = "",
    note: str = "",
) -> dict:
    """Add a transaction entry to Notion. Returns the created page."""
    properties: dict = {
        "المتجر": {"title": [{"text": {"content": merchant}}]},
        "المبلغ": {"number": amount},
        "التاريخ": {"date": {"start": date_str}},
        "النوع": {"select": {"name": entry_type}},
    }
    if note:
        properties["ملاحظة"] = {"rich_text": [{"text": {"content": note}}]}
    if card:
        properties["البطاقة"] = {"rich_text": [{"text": {"content": card}}]}

    return notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=properties,
    )


def get_all_entries() -> list[dict]:
    """Return all entries sorted by date ascending."""
    response = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        sorts=[{"property": "التاريخ", "direction": "ascending"}],
    )
    return response["results"]


def get_total() -> float:
    """Sum المبلغ across all entries."""
    entries = get_all_entries()
    return sum(
        e["properties"]["المبلغ"]["number"] or 0.0
        for e in entries
        if e["properties"].get("المبلغ", {}).get("number") is not None
    )


def clear_all_entries() -> int:
    """Archive every entry. Returns the count deleted."""
    entries = get_all_entries()
    for entry in entries:
        notion.pages.update(page_id=entry["id"], archived=True)
    return len(entries)


def extract_entries_for_pdf(entries: list[dict]) -> list[dict]:
    """Convert raw Notion pages to dicts suitable for PDF generation."""
    result = []
    for e in entries:
        props = e["properties"]

        merchant = ""
        title = props.get("المتجر", {}).get("title", [])
        if title:
            merchant = title[0]["text"]["content"]

        amount = props.get("المبلغ", {}).get("number") or 0.0

        date_str = ""
        date_prop = props.get("التاريخ", {}).get("date")
        if date_prop:
            date_str = date_prop.get("start", "")

        note = ""
        note_parts = props.get("ملاحظة", {}).get("rich_text", [])
        if note_parts:
            note = note_parts[0]["text"]["content"]

        result.append({"merchant": merchant, "amount": amount, "date": date_str, "note": note})
    return result
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_notion_client.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add notion/client.py tests/test_notion_client.py
git commit -m "feat: add Notion client with TDD"
```

---

## Task 5: Notion Database Setup (Manual Step)

This task requires manual setup in Notion before the bot can run.

- [ ] **Step 1: Create a Notion Integration**
  1. Go to https://www.notion.so/my-integrations
  2. Click "New integration"
  3. Name it "المحاسب"
  4. Copy the "Internal Integration Token" → this is your `NOTION_API_KEY`

- [ ] **Step 2: Create the Database**
  1. In Notion, create a new full-page database
  2. Name it: **المحاسب**
  3. Add these properties (exact names required):

| Property Name | Type   | Notes                        |
|---------------|--------|------------------------------|
| المتجر        | Title  | Default title column         |
| المبلغ        | Number | Format: Number               |
| التاريخ       | Date   |                              |
| النوع         | Select | Add options: بنكي, يدوي      |
| ملاحظة        | Text   |                              |
| البطاقة       | Text   |                              |

- [ ] **Step 3: Share the database with the integration**
  1. Open the database page in Notion
  2. Click "..." → "Add connections" → find "المحاسب" integration
  3. Click "Confirm"

- [ ] **Step 4: Copy the database ID**
  - The URL of a Notion database looks like:
    `https://www.notion.so/YOUR_WORKSPACE/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx?v=...`
  - The 32-character hex string before `?v=` is your `NOTION_DATABASE_ID`
  - Add dashes to format it as UUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

---

## Task 6: PDF Generator (TDD)

**Files:**
- Create: `pdf/generator.py`
- Create: `tests/test_pdf_generator.py`

- [ ] **Step 1: Download Amiri Arabic font**

```bash
curl -L "https://github.com/alif-type/amiri/releases/download/1.000/Amiri-1.000.zip" \
  -o /tmp/amiri.zip
unzip /tmp/amiri.zip -d /tmp/amiri
cp /tmp/amiri/Amiri-Regular.ttf pdf/fonts/
```

If the URL above doesn't work, download Amiri-Regular.ttf from
https://fonts.google.com/specimen/Amiri and place it in `pdf/fonts/`.

- [ ] **Step 2: Write failing tests**

```python
# tests/test_pdf_generator.py
import pytest
from pdf.generator import generate_report

SAMPLE_ENTRIES = [
    {"merchant": "MATHAF ALGHIDHA EST", "amount": 10.50, "date": "2026-06-13", "note": ""},
    {"merchant": "مطعم الكوفي", "amount": 50.00, "date": "2026-06-14", "note": "غداء"},
    {"merchant": "استرجاع", "amount": -30.00, "date": "2026-06-14", "note": "رجعوا الفلوس"},
]


def test_generate_report_returns_bytes():
    result = generate_report(SAMPLE_ENTRIES)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_report_is_valid_pdf():
    result = generate_report(SAMPLE_ENTRIES)
    # PDFs start with %PDF
    assert result[:4] == b"%PDF"


def test_generate_report_empty_entries():
    result = generate_report([])
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_generate_report_total_in_output():
    # Total = 10.50 + 50.00 - 30.00 = 30.50
    # We just verify the function runs without error and returns PDF
    result = generate_report(SAMPLE_ENTRIES)
    assert result[:4] == b"%PDF"
```

- [ ] **Step 3: Run tests — confirm they fail**

```bash
pytest tests/test_pdf_generator.py -v
```

Expected: `ImportError`

- [ ] **Step 4: Write pdf/generator.py**

```python
import io
import os
from datetime import datetime
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_PATH = os.path.join(_FONT_DIR, "Amiri-Regular.ttf")


def _ar(text: str) -> str:
    """Reshape Arabic text and apply bidi for correct LTR-canvas rendering."""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("Amiri", style="", fname=_FONT_PATH)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Amiri", size=18)
        self.cell(0, 12, _ar("حساب المدفوعات"), ln=True, align="C")
        self.set_font("Amiri", size=10)
        today = datetime.now().strftime("%Y-%m-%d")
        self.cell(0, 8, _ar(f"تاريخ التقرير: {today}"), ln=True, align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Amiri", size=8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def generate_report(entries: list[dict]) -> bytes:
    """Generate a PDF report table from a list of entry dicts.

    Each entry: {"merchant": str, "amount": float, "date": str, "note": str}
    Returns raw PDF bytes.
    """
    pdf = _PDF()
    pdf.add_page()
    pdf.set_font("Amiri", size=11)

    # Table headers (Arabic, right-aligned feel via reversed column order)
    col_widths = [10, 30, 65, 25, 50]  # #, Date, Merchant, Amount, Note
    headers = ["#", _ar("التاريخ"), _ar("المتجر"), _ar("المبلغ"), _ar("ملاحظة")]

    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Amiri", size=11)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 9, h, border=1, align="C", fill=True)
    pdf.ln()

    total = 0.0
    for i, entry in enumerate(entries, start=1):
        amount = float(entry.get("amount", 0))
        total += amount

        if amount < 0:
            pdf.set_text_color(200, 0, 0)
        else:
            pdf.set_text_color(0, 0, 0)

        row = [
            str(i),
            entry.get("date", "")[:10],
            entry.get("merchant", ""),
            f"SAR {amount:,.2f}",
            entry.get("note", ""),
        ]
        aligns = ["C", "C", "L", "R", "L"]
        for w, cell, align in zip(col_widths, row, aligns):
            # Arabic text in merchant/note columns needs reshaping
            display = _ar(cell) if any('؀' <= c <= 'ۿ' for c in cell) else cell
            pdf.cell(w, 8, display, border=1, align=align)
        pdf.ln()

    # Total row
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Amiri", size=12)
    pdf.set_fill_color(200, 230, 200)
    total_label = _ar("الإجمالي")
    pdf.cell(sum(col_widths[:3]), 10, total_label, border=1, align="R", fill=True)
    total_color = (200, 0, 0) if total < 0 else (0, 100, 0)
    pdf.set_text_color(*total_color)
    pdf.cell(sum(col_widths[3:]), 10, f"SAR {total:,.2f}", border=1, align="R", fill=True)
    pdf.ln()

    return bytes(pdf.output())
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
pytest tests/test_pdf_generator.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add pdf/ tests/test_pdf_generator.py
git commit -m "feat: add PDF generator with Arabic support"
```

---

## Task 7: Webhook Server (Flask, TDD)

**Files:**
- Create: `webhook/server.py`
- Create: `tests/test_webhook.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_webhook.py
import json
from unittest.mock import patch, MagicMock
import pytest
from webhook.server import create_app

SAMPLE_SMS = """شراء عبر نقاط بيع SAR 10.50
بطاقة 7796* مدى- ApplePay
من MATHAF ALGHIDHA EST
في 21:41 26-06-13"""


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_missing_secret_returns_401(client):
    response = client.post("/transaction", json={"text": SAMPLE_SMS})
    assert response.status_code == 401


def test_wrong_secret_returns_401(client):
    response = client.post(
        "/transaction",
        json={"text": SAMPLE_SMS},
        headers={"X-Secret-Key": "wrong_secret"},
    )
    assert response.status_code == 401


def test_valid_request_returns_200(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = client.post(
            "/transaction",
            json={"text": SAMPLE_SMS},
            headers={"X-Secret-Key": "test_secret_key_12345"},
        )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "sent"
    assert "txn_id" in data


def test_valid_request_sends_telegram_message(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        client.post(
            "/transaction",
            json={"text": SAMPLE_SMS},
            headers={"X-Secret-Key": "test_secret_key_12345"},
        )
    assert mock_post.called
    call_json = mock_post.call_args[1]["json"]
    assert "MATHAF ALGHIDHA EST" in call_json["text"]
    assert "10.50" in call_json["text"]


def test_unparseable_sms_returns_200_with_raw(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = client.post(
            "/transaction",
            json={"text": "some random text that is not a bank SMS"},
            headers={"X-Secret-Key": "test_secret_key_12345"},
        )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "unparseable"


def test_missing_text_returns_400(client):
    response = client.post(
        "/transaction",
        json={},
        headers={"X-Secret-Key": "test_secret_key_12345"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_webhook.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write webhook/server.py**

```python
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
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_webhook.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add webhook/server.py tests/test_webhook.py
git commit -m "feat: add Flask webhook endpoint with TDD"
```

---

## Task 8: Telegram Bot Handlers

**Files:**
- Create: `bot/handlers.py`

This task has no automated unit tests (PTB async testing requires complex fixtures).
Manual testing is done in Task 10.

- [ ] **Step 1: Write bot/handlers.py**

```python
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

# Conversation states
WAITING_NOTE = 1
WAITING_AMOUNT = 2
WAITING_MERCHANT = 3
WAITING_MANUAL_NOTE = 4
WAITING_CLEAR_CONFIRM = 5


# ── Transaction button callbacks ──────────────────────────────────────────────

async def btn_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ✅ نعم — save to Notion without note."""
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
    """Receive note text, save transaction with note to Notion."""
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
    await update.message.reply_text("⏳ جاري إنشاء التقرير...")
    entries_raw = notion_client.get_all_entries()
    entries = extract_entries_for_pdf(entries_raw)

    if not entries:
        await update.message.reply_text("لا توجد عمليات مسجلة بعد.")
        return

    pdf_bytes = generate_report(entries)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(pdf_bytes),
        filename="تقرير-الحساب.pdf",
        caption=f"📊 التقرير — {len(entries)} عملية",
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
    # Conversation handler (note flow + /add flow)
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
```

- [ ] **Step 2: Commit**

```bash
git add bot/handlers.py
git commit -m "feat: add Telegram bot handlers (buttons, /add, /report, /clear)"
```

---

## Task 9: Main Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main.py**

```python
import threading
from telegram.ext import Application
from config import TELEGRAM_BOT_TOKEN, WEBHOOK_PORT
from bot.handlers import register_handlers
from webhook.server import create_app


def _run_flask(flask_app) -> None:
    flask_app.run(host="0.0.0.0", port=WEBHOOK_PORT, use_reloader=False)


def main() -> None:
    # Start Flask webhook in a background daemon thread
    flask_app = create_app()
    flask_thread = threading.Thread(target=_run_flask, args=(flask_app,), daemon=True)
    flask_thread.start()
    print(f"[webhook] listening on port {WEBHOOK_PORT}")

    # Build and run the Telegram bot (blocking, manages its own event loop)
    bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(bot_app)
    print("[bot] starting polling...")
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests to verify nothing is broken**

```bash
pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point (Flask + PTB together)"
```

---

## Task 10: Systemd Service + .env Setup

**Files:**
- Create: `almuhasib.service`

- [ ] **Step 1: Copy .env.example and fill in real values**

```bash
cp .env.example .env
# Edit .env with real values:
# TELEGRAM_BOT_TOKEN=   (from BotFather)
# TELEGRAM_OWNER_CHAT_ID=  (send /start to @userinfobot to get your ID)
# NOTION_API_KEY=       (from step in Task 5)
# NOTION_DATABASE_ID=   (from step in Task 5)
# WEBHOOK_SECRET_KEY=   (any strong random string, e.g. openssl rand -hex 32)
# WEBHOOK_PORT=8080
```

- [ ] **Step 2: Create virtualenv and install on VPS**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 3: Write almuhasib.service**

```ini
[Unit]
Description=Almuhasib Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/almuhasib
ExecStart=/home/ubuntu/almuhasib/venv/bin/python main.py
Restart=on-failure
RestartSec=5
EnvironmentFile=/home/ubuntu/almuhasib/.env

[Install]
WantedBy=multi-user.target
```

Replace `ubuntu` with your VPS username and adjust `WorkingDirectory` to the actual path.

- [ ] **Step 4: Install and start the service on VPS**

```bash
sudo cp almuhasib.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable almuhasib
sudo systemctl start almuhasib
sudo systemctl status almuhasib
```

Expected: `Active: active (running)`

- [ ] **Step 5: Open firewall port for webhook**

```bash
sudo ufw allow 8080/tcp
sudo ufw reload
```

- [ ] **Step 6: Final commit**

```bash
git add almuhasib.service
git commit -m "chore: add systemd service file"
```

---

## Task 11: iPhone Shortcuts Setup

- [ ] **Step 1: Create a new Shortcut in the Shortcuts app**

1. Open **Shortcuts** → tap **+** to create new shortcut
2. Add action: **Receive** → set "Input" to "Text"
3. Add action: **Get Contents of URL**
   - URL: `http://YOUR_VPS_IP:8080/transaction`
   - Method: POST
   - Headers: Add `X-Secret-Key` = your `WEBHOOK_SECRET_KEY`
   - Request Body: JSON → add key `text` with value: **Shortcut Input**
4. Name it "إرسال فاتورة"

- [ ] **Step 2: Create an Automation to trigger the Shortcut**

1. In Shortcuts → **Automation** tab → **+**
2. Choose trigger: **App** → select your banking app → "Is Opened" OR use
   **Notification** trigger if your bank sends push notifications
3. Action: Run Shortcut → "إرسال فاتورة"
4. Pass the notification body or clipboard text as input

> **Note:** The exact automation trigger depends on your bank app. If the bank
> sends an SMS, use **Personal Automation → Message** → filter by sender name.

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_parser.py -v
pytest tests/test_notion_client.py -v
pytest tests/test_pdf_generator.py -v
pytest tests/test_webhook.py -v
```

---

## Manual Smoke Test (after deployment)

1. Send `POST http://VPS_IP:8080/transaction` with the sample SMS to verify bot sends message
2. Click "✅ نعم" → verify Notion entry appears
3. Click "📝 نعم + ملاحظة" → send a note → verify Notion entry with note
4. Click "❌ لا" → verify message updates, no Notion entry
5. Send `/add` → go through conversation → verify Notion entry
6. Send `/report` → verify PDF arrives with correct data
7. Send `/clear` → confirm → verify Notion database is empty
