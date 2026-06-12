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
