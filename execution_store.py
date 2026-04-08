"""
execution_store.py — Persistent ledger for LLM-driven execution.

Uses sqlite for:
  - idempotency keys (prevent duplicate submits)
  - daily trade counts + cooldown enforcement
  - basic observability (what ran, when, and with what result)
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


DB_PATH = os.getenv("LLM_EXECUTION_DB_PATH") or "execution.db"


def _utc_day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS executions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts REAL NOT NULL,
              day_utc TEXT NOT NULL,
              tool TEXT NOT NULL,
              symbol TEXT,
              side TEXT,
              notional_usd REAL,
              live INTEGER NOT NULL,
              dry_run INTEGER NOT NULL,
              idempotency_key TEXT,
              ok INTEGER NOT NULL,
              error TEXT,
              result_json TEXT
            );
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_executions_idem ON executions(idempotency_key) "
            "WHERE idempotency_key IS NOT NULL;"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_executions_day ON executions(day_utc, tool);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_executions_ts ON executions(ts);")
        conn.commit()
    finally:
        conn.close()


@dataclass
class ExecutionRecord:
    ts: float
    tool: str
    symbol: Optional[str]
    side: Optional[str]
    notional_usd: Optional[float]
    live: bool
    dry_run: bool
    idempotency_key: Optional[str]


def already_processed(idempotency_key: Optional[str]) -> bool:
    if not idempotency_key:
        return False
    conn = _connect()
    try:
        cur = conn.execute("SELECT 1 FROM executions WHERE idempotency_key = ? LIMIT 1;", (idempotency_key,))
        return cur.fetchone() is not None
    finally:
        conn.close()


def count_today(tool: str, *, live_only: bool = True) -> int:
    now = time.time()
    day = _utc_day(now)
    conn = _connect()
    try:
        if live_only:
            cur = conn.execute(
                "SELECT COUNT(*) FROM executions WHERE day_utc = ? AND tool = ? AND live = 1 AND ok = 1;",
                (day, tool),
            )
        else:
            cur = conn.execute(
                "SELECT COUNT(*) FROM executions WHERE day_utc = ? AND tool = ? AND ok = 1;",
                (day, tool),
            )
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def last_live_ts(tool: str) -> Optional[float]:
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT ts FROM executions WHERE tool = ? AND live = 1 AND ok = 1 ORDER BY ts DESC LIMIT 1;",
            (tool,),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None
    finally:
        conn.close()


def insert_result(
    rec: ExecutionRecord,
    *,
    ok: bool,
    error: Optional[str],
    result: Optional[dict[str, Any]] = None,
) -> None:
    ts = rec.ts
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO executions (
              ts, day_utc, tool, symbol, side, notional_usd,
              live, dry_run, idempotency_key, ok, error, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                ts,
                _utc_day(ts),
                rec.tool,
                rec.symbol,
                rec.side,
                rec.notional_usd,
                1 if rec.live else 0,
                1 if rec.dry_run else 0,
                rec.idempotency_key,
                1 if ok else 0,
                error,
                None if result is None else __import__("json").dumps(result),
            ),
        )
        conn.commit()
    finally:
        conn.close()

