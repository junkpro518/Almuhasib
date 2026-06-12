"""PDF report generator for the Almuhasib bot.

Requires Amiri-Regular.ttf in pdf/fonts/ (not committed to git).
Download: https://fonts.google.com/specimen/Amiri
"""
import os
from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import arabic_reshaper
from bidi.algorithm import get_display

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_PATH = os.path.join(_FONT_DIR, "Amiri-Regular.ttf")


def _ar(text: str) -> str:
    """Reshape Arabic text and apply bidi for correct LTR-canvas rendering."""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def _has_arabic(text: str) -> bool:
    """Return True if text contains any Arabic Unicode characters."""
    return any('؀' <= c <= 'ۿ' for c in text)


def _compute_total(entries: list[dict]) -> float:
    """Sum the amount field across all entries."""
    return sum(float(e.get("amount", 0)) for e in entries)


class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("Amiri", style="", fname=_FONT_PATH)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Amiri", size=18)
        self.cell(0, 12, _ar("حساب المدفوعات"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_font("Amiri", size=10)
        today = datetime.now().strftime("%Y-%m-%d")
        self.cell(0, 8, _ar(f"تاريخ التقرير: {today}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
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

    # Column widths: #, Date, Merchant, Amount, Note
    col_widths = [10, 30, 65, 30, 45]
    headers = ["#", _ar("التاريخ"), _ar("المتجر"), _ar("المبلغ"), _ar("ملاحظة")]

    # Header row
    pdf.set_fill_color(220, 220, 220)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 9, h, border=1, align="C", fill=True)
    pdf.ln()

    # Data rows
    total = 0.0
    for i, entry in enumerate(entries, start=1):
        amount = float(entry.get("amount", 0))
        total += amount

        pdf.set_text_color(200, 0, 0) if amount < 0 else pdf.set_text_color(0, 0, 0)

        merchant = entry.get("merchant", "")
        note = entry.get("note", "")

        row = [
            str(i),
            entry.get("date", "")[:10],
            _ar(merchant) if _has_arabic(merchant) else merchant,
            f"SAR {amount:,.2f}",
            _ar(note) if _has_arabic(note) else note,
        ]
        for w, cell, align in zip(col_widths, row, ["C", "C", "L", "R", "L"]):
            pdf.cell(w, 8, cell, border=1, align=align)
        pdf.ln()

    # Total row
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Amiri", size=12)
    pdf.set_fill_color(200, 230, 200)
    label_width = sum(col_widths[:3])
    value_width = sum(col_widths[3:])
    pdf.cell(label_width, 10, _ar("الإجمالي"), border=1, align="R", fill=True)
    pdf.set_text_color(200, 0, 0) if total < 0 else pdf.set_text_color(0, 100, 0)
    pdf.cell(value_width, 10, f"SAR {total:,.2f}", border=1, align="R", fill=True)
    pdf.ln()

    return bytes(pdf.output())
