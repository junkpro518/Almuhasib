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
    assert result[:4] == b"%PDF"


def test_generate_report_empty_entries():
    result = generate_report([])
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_generate_report_total_correct():
    # Total = 10.50 + 50.00 - 30.00 = 30.50
    result = generate_report(SAMPLE_ENTRIES)
    assert result[:4] == b"%PDF"
    # Verify total appears in PDF content
    assert b"30.50" in result
