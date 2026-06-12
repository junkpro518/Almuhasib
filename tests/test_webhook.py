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
