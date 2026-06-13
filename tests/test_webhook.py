from unittest.mock import patch, MagicMock
import pytest
import requests as req_lib
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


def _post(client, text=SAMPLE_SMS, secret="test_secret_key_12345", **kwargs):
    body = {"text": text}
    if "sender" in kwargs:
        body["sender"] = kwargs.pop("sender")
    return client.post(
        "/transaction",
        json=body,
        headers={"X-Secret-Key": secret},
        **kwargs,
    )


def test_missing_secret_returns_401(client):
    response = client.post("/transaction", json={"text": SAMPLE_SMS})
    assert response.status_code == 401


def test_wrong_secret_returns_401(client):
    response = _post(client, secret="wrong_secret")
    assert response.status_code == 401


def test_valid_request_returns_200(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client)
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "sent"
    assert "txn_id" in data


def test_valid_request_sends_telegram_message(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        _post(client)
    assert mock_post.called
    call_json = mock_post.call_args[1]["json"]
    assert "MATHAF ALGHIDHA EST" in call_json["text"]
    assert "10.50" in call_json["text"]


def test_allowed_sender_is_processed(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client, sender="alinma")
    assert response.status_code == 200
    assert response.get_json()["status"] == "sent"


def test_unrecognized_sender_does_not_block_card_token_match(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client, sender="Other Bank")
    assert response.status_code == 200
    assert response.get_json()["status"] == "sent"
    assert mock_post.called


def test_missing_required_card_token_is_ignored(client):
    sms = """شراء عبر نقاط بيع SAR 10.50
بطاقة 1234* مدى- ApplePay
من TEST STORE
في 21:41 26-06-13"""
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client, text=sms)
    assert response.status_code == 200
    assert response.get_json() == {"status": "ignored", "reason": "missing_required_card_token"}
    assert not mock_post.called


def test_ehsan_sms_is_ignored(client):
    sms = """شراء عبر نقاط بيع SAR 10.50
بطاقة 7796* مدى- ApplePay
من EHSAN
في 21:41 26-06-13"""
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client, text=sms)
    assert response.status_code == 200
    assert response.get_json() == {"status": "ignored", "reason": "excluded_token"}
    assert not mock_post.called


def test_missing_sender_still_allows_message_content_filter_automation(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client)
    assert response.status_code == 200
    assert response.get_json()["status"] == "sent"


def test_unparseable_sms_returns_200_with_raw(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        response = _post(client, text="رسالة غير معروفة تحتوي 7796 وليست عملية بنك")
    assert response.status_code == 200
    assert response.get_json()["status"] == "unparseable"


def test_missing_text_returns_400(client):
    response = client.post(
        "/transaction",
        json={},
        headers={"X-Secret-Key": "test_secret_key_12345"},
    )
    assert response.status_code == 400


def test_html_special_chars_in_sms_escaped(client):
    sms_with_html = """شراء عبر نقاط بيع SAR 5.00
بطاقة 7796* <TEST>
من STORE & CO
في 10:00 26-06-13"""
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=True)
        _post(client, text=sms_with_html)
    call_json = mock_post.call_args[1]["json"]
    assert "<TEST>" not in call_json["text"]
    assert "&lt;" not in call_json["text"] or "&amp;" in call_json["text"] or "STORE" in call_json["text"]


def test_telegram_failure_returns_502(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.return_value = MagicMock(ok=False, text="Bad Request")
        response = _post(client)
    assert response.status_code == 502
    assert response.get_json()["status"] == "error"


def test_telegram_network_error_returns_502(client):
    with patch("webhook.server.requests.post") as mock_post:
        mock_post.side_effect = req_lib.exceptions.ConnectionError("network down")
        response = _post(client)
    assert response.status_code == 502
