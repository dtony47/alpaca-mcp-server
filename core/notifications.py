"""Notification dispatch. Telegram primary, local-file fallback.

Never raises. On any failure, falls back to appending to fallback_path
and returns success=True (the message is preserved).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import requests

Urgency = Literal["info", "alert", "critical"]


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    delivered_via: Literal["telegram", "file"]
    error: str | None


def send(
    message: str,
    urgency: Urgency,
    telegram_token: str | None,
    telegram_chat_id: str | None,
    fallback_path: Path,
    timeout_seconds: float = 5.0,
) -> NotificationResult:
    """Send a notification via Telegram, falling back to local file on any failure.

    Returns NotificationResult; never raises.
    """
    if telegram_token and telegram_chat_id:
        prefix = {"info": "ℹ️", "alert": "⚠️", "critical": "🚨"}[urgency]
        text = f"{prefix} {message}"
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        try:
            resp = requests.post(
                url,
                data={"chat_id": telegram_chat_id, "text": text},
                timeout=timeout_seconds,
            )
            if resp.status_code == 200:
                return NotificationResult(success=True, delivered_via="telegram", error=None)
            error = f"telegram returned {resp.status_code}"
        except requests.RequestException as e:
            error = f"telegram request failed: {e}"
    else:
        error = "telegram not configured"

    # Fallback to file
    _append_to_fallback(message, urgency, fallback_path)
    return NotificationResult(success=True, delivered_via="file", error=error)


def _append_to_fallback(message: str, urgency: Urgency, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"\n## {stamp} [{urgency}]\n{message}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)
