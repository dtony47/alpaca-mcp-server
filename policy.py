"""
policy.py — Guardrails for LLM-driven execution.

This module is intentionally conservative:
  - Execution is disabled by default.
  - When enabled, orders are constrained by allowlists and hard limits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default


def _env_csv(name: str) -> list[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name) or default)
    except Exception:
        return default


def _env_float(name: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(name) or default)
    except Exception:
        return default


@dataclass(frozen=True)
class ExecutionPolicy:
    enabled: bool
    mode: str  # "paper" or "live" (live not recommended)
    allowed_symbols: list[str]
    allowed_asset_classes: list[str]  # e.g. ["crypto"] or ["stocks","crypto"]
    max_notional_usd: float
    max_trades_per_day: int
    min_seconds_between_trades: int
    require_live_token: bool
    live_token: Optional[str]

    def check_symbol(self, symbol: str) -> None:
        if self.allowed_symbols and symbol not in self.allowed_symbols:
            raise ValueError(f"Symbol '{symbol}' not in allowlist")

    def check_asset_class(self, symbol: str, asset_class: str) -> None:
        if self.allowed_asset_classes and asset_class not in self.allowed_asset_classes:
            raise ValueError(f"Asset class '{asset_class}' not allowed")

    def check_notional(self, notional: float) -> None:
        if notional <= 0:
            raise ValueError("Notional must be > 0")
        if self.max_notional_usd and notional > self.max_notional_usd:
            raise ValueError(f"Notional ${notional:,.2f} exceeds policy max ${self.max_notional_usd:,.2f}")

    def check_live_token(self, token: Optional[str]) -> None:
        if not self.require_live_token:
            return
        if not self.live_token:
            raise ValueError("Live trading token is not configured")
        if token != self.live_token:
            raise ValueError("Invalid live trading token")


def load_policy() -> ExecutionPolicy:
    """
    Policy is configured via env vars (in `.env` or shell):

      LLM_TRADING_ENABLED=false
      LLM_TRADING_MODE=paper
      LLM_ALLOWED_SYMBOLS=BTC/USD,ETH/USD
      LLM_ALLOWED_ASSET_CLASSES=crypto
      LLM_MAX_NOTIONAL_USD=500
      LLM_MAX_TRADES_PER_DAY=10
      LLM_MIN_SECONDS_BETWEEN_TRADES=30
      LLM_REQUIRE_LIVE_TOKEN=true
      LLM_LIVE_TOKEN=some-long-random-string
    """
    enabled = _env_bool("LLM_TRADING_ENABLED", default=False)
    mode = (os.getenv("LLM_TRADING_MODE") or "paper").strip().lower()
    if mode not in ("paper", "live"):
        mode = "paper"

    allowed_symbols = _env_csv("LLM_ALLOWED_SYMBOLS")
    allowed_asset_classes = [s.lower() for s in _env_csv("LLM_ALLOWED_ASSET_CLASSES")] or ["crypto"]

    max_notional = _env_float("LLM_MAX_NOTIONAL_USD", default=0.0) or 0.0
    max_trades_per_day = max(0, _env_int("LLM_MAX_TRADES_PER_DAY", default=0))
    min_seconds_between_trades = max(0, _env_int("LLM_MIN_SECONDS_BETWEEN_TRADES", default=0))

    require_token = _env_bool("LLM_REQUIRE_LIVE_TOKEN", default=True)
    live_token = (os.getenv("LLM_LIVE_TOKEN") or "").strip() or None

    return ExecutionPolicy(
        enabled=enabled,
        mode=mode,
        allowed_symbols=allowed_symbols,
        allowed_asset_classes=allowed_asset_classes,
        max_notional_usd=max_notional,
        max_trades_per_day=max_trades_per_day,
        min_seconds_between_trades=min_seconds_between_trades,
        require_live_token=require_token,
        live_token=live_token,
    )


def classify_symbol(symbol: str) -> str:
    """Return 'crypto' for BTC/USD style symbols, else 'stocks'."""
    return "crypto" if "/" in symbol else "stocks"

