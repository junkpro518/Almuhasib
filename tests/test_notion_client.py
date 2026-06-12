from unittest.mock import MagicMock
import pytest
import notion.client as nc


@pytest.fixture(autouse=True)
def mock_notion_client(monkeypatch):
    """Replace the notion SDK client with a MagicMock for all tests."""
    mock = MagicMock()
    monkeypatch.setattr(nc, "notion", mock)
    return mock


def _make_query_response(results):
    """Helper: notion SDK returns results list directly from collect_paginated_api."""
    return results


def test_add_entry_creates_page(mock_notion_client):
    mock_notion_client.pages.create.return_value = {"id": "page-id-1"}

    nc.add_entry(
        amount=10.50,
        merchant="MATHAF ALGHIDHA EST",
        date_str="2026-06-13",
        entry_type="بنكي",
        card="7796* مدى- ApplePay",
        note="",
    )

    assert mock_notion_client.pages.create.called
    kwargs = mock_notion_client.pages.create.call_args[1]
    assert kwargs["parent"] == {"database_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
    props = kwargs["properties"]
    assert props["المبلغ"]["number"] == 10.50
    assert props["النوع"]["select"]["name"] == "بنكي"
    assert props["المتجر"]["title"][0]["text"]["content"] == "MATHAF ALGHIDHA EST"
    assert "ملاحظة" not in props  # empty note should not be added


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


def test_get_total_sums_all_amounts(mock_notion_client, monkeypatch):
    entries = [
        {"properties": {"المبلغ": {"number": 10.50}}},
        {"properties": {"المبلغ": {"number": 20.00}}},
        {"properties": {"المبلغ": {"number": -5.00}}},
    ]
    monkeypatch.setattr(nc, "get_all_entries", lambda: entries)

    total = nc.get_total()
    assert total == pytest.approx(25.50)


def test_clear_all_archives_each_entry(mock_notion_client, monkeypatch):
    entries = [{"id": "id-1"}, {"id": "id-2"}, {"id": "id-3"}]
    monkeypatch.setattr(nc, "get_all_entries", lambda: entries)

    count = nc.clear_all_entries()

    assert count == 3
    assert mock_notion_client.pages.update.call_count == 3
    for c in mock_notion_client.pages.update.call_args_list:
        assert c[1]["archived"] is True


def test_extract_entries_for_pdf_maps_fields(mock_notion_client):
    raw = [{
        "properties": {
            "المتجر": {"title": [{"plain_text": "Test Shop", "text": {"content": "Test Shop"}}]},
            "المبلغ": {"number": 42.5},
            "التاريخ": {"date": {"start": "2026-06-13"}},
            "ملاحظة": {"rich_text": [{"plain_text": "note here", "text": {"content": "note here"}}]},
        }
    }]
    result = nc.extract_entries_for_pdf(raw)
    assert result == [{"merchant": "Test Shop", "amount": 42.5, "date": "2026-06-13", "note": "note here"}]


def test_extract_entries_handles_missing_fields(mock_notion_client):
    raw = [{"properties": {}}]
    result = nc.extract_entries_for_pdf(raw)
    assert result == [{"merchant": "", "amount": 0.0, "date": "", "note": ""}]
