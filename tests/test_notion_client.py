from unittest.mock import MagicMock, patch
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
