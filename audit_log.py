"""
audit_log.py — Minimal JSONL audit logging.

We log execution *requests* and outcomes so you can inspect what the LLM asked
the system to do. Avoid logging secrets.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional


LOG_PATH = "trade_audit.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(event: str, payload: dict[str, Any], *, ok: bool, error: Optional[str] = None) -> None:
    record = {
        "ts": _now_iso(),
        "event": event,
        "ok": ok,
        "error": error,
        "payload": payload,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

