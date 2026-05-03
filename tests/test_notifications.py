from pathlib import Path

import pytest

from core.notifications import NotificationResult, send


@pytest.fixture
def fallback_path(tmp_path: Path) -> Path:
    return tmp_path / "NOTIFICATIONS.md"


def test_send_falls_back_to_file_when_telegram_unconfigured(fallback_path: Path):
    result = send(
        message="Test message",
        urgency="info",
        telegram_token=None,
        telegram_chat_id=None,
        fallback_path=fallback_path,
    )
    assert result.delivered_via == "file"
    assert result.success is True
    assert fallback_path.exists()
    content = fallback_path.read_text()
    assert "Test message" in content
    assert "info" in content


def test_send_appends_to_existing_fallback_file(fallback_path: Path):
    fallback_path.write_text("# Existing\n\n")
    send(
        message="First",
        urgency="info",
        telegram_token=None,
        telegram_chat_id=None,
        fallback_path=fallback_path,
    )
    send(
        message="Second",
        urgency="alert",
        telegram_token=None,
        telegram_chat_id=None,
        fallback_path=fallback_path,
    )
    content = fallback_path.read_text()
    assert "First" in content
    assert "Second" in content
    assert content.startswith("# Existing")


def test_send_uses_telegram_when_configured(monkeypatch, fallback_path: Path):
    sent_payloads = []

    def fake_post(url, data, timeout):  # noqa: ARG001
        sent_payloads.append({"url": url, "data": data})

        class FakeResp:
            status_code = 200

            def json(self):
                return {"ok": True}

        return FakeResp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    result = send(
        message="Hello",
        urgency="alert",
        telegram_token="fake-token",
        telegram_chat_id="12345",
        fallback_path=fallback_path,
    )
    assert result.delivered_via == "telegram"
    assert result.success is True
    assert len(sent_payloads) == 1
    assert "fake-token" in sent_payloads[0]["url"]
    assert sent_payloads[0]["data"]["chat_id"] == "12345"
    assert "Hello" in sent_payloads[0]["data"]["text"]


def test_send_falls_back_when_telegram_request_fails(monkeypatch, fallback_path: Path):
    import requests

    def fake_post(url, data, timeout):  # noqa: ARG001
        raise requests.RequestException("connection refused")

    monkeypatch.setattr(requests, "post", fake_post)

    result = send(
        message="Hello",
        urgency="critical",
        telegram_token="fake-token",
        telegram_chat_id="12345",
        fallback_path=fallback_path,
    )
    assert result.delivered_via == "file"
    assert result.success is True
    assert "Hello" in fallback_path.read_text()


def test_send_falls_back_when_telegram_returns_non_200(monkeypatch, fallback_path: Path):
    def fake_post(url, data, timeout):  # noqa: ARG001
        class FakeResp:
            status_code = 500

            def json(self):
                return {"ok": False, "description": "internal error"}

        return FakeResp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    result = send(
        message="Hello",
        urgency="info",
        telegram_token="fake-token",
        telegram_chat_id="12345",
        fallback_path=fallback_path,
    )
    assert result.delivered_via == "file"
    assert result.success is True


def test_notification_result_is_immutable():
    r = NotificationResult(success=True, delivered_via="file", error=None)
    with pytest.raises(Exception):
        r.success = False  # type: ignore[misc]
