from notion_client import Client
from notion_client.helpers import collect_paginated_api
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
    """Return all entries sorted by date ascending, handling pagination automatically."""
    return collect_paginated_api(
        notion.databases.query,
        database_id=NOTION_DATABASE_ID,
        sorts=[{"property": "التاريخ", "direction": "ascending"}],
    )


def get_total() -> float:
    """Sum المبلغ across all entries."""
    entries = get_all_entries()
    return sum(
        e["properties"]["المبلغ"]["number"]
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
            merchant = title[0].get("plain_text", title[0]["text"]["content"])

        amount = props.get("المبلغ", {}).get("number") or 0.0

        date_str = ""
        date_prop = props.get("التاريخ", {}).get("date")
        if date_prop:
            date_str = date_prop.get("start", "")

        note = ""
        note_parts = props.get("ملاحظة", {}).get("rich_text", [])
        if note_parts:
            note = note_parts[0].get("plain_text", note_parts[0]["text"]["content"])

        result.append({"merchant": merchant, "amount": amount, "date": date_str, "note": note})
    return result
