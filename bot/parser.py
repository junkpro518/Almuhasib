import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
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
    # Anchor Arabic keyword patterns to line-start to prevent substring collisions
    card_match = re.search(r'(?m)^بطاقة\s+(.+?)$', text)
    merchant_match = re.search(r'(?m)^من\s+(.+?)$', text)
    # Date: HH:MM YY-MM-DD  (e.g. 21:41 26-06-13)
    dt_match = re.search(r'(?m)^في\s+(\d{2}:\d{2})\s+(\d{2})-(\d{2})-(\d{2})', text)

    if not all([amount_match, card_match, merchant_match, dt_match]):
        return None

    amount_str = amount_match.group(1).replace(',', '')
    try:
        amount = float(amount_str)
    except ValueError:
        return None

    yy, mm, dd = dt_match.group(2), dt_match.group(3), dt_match.group(4)
    year = 2000 + int(yy)
    datetime_str = f"{year}-{mm}-{dd} {dt_match.group(1)}"

    return Transaction(
        amount=amount,
        merchant=merchant_match.group(1).strip(),
        card=card_match.group(1).strip(),
        datetime_str=datetime_str,
    )
