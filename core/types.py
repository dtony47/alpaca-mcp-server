"""Shared data structures used across all trading-bot legs.

These are pure dataclasses with no logic. All money values use Decimal.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Venue = Literal["alpaca", "solana"]
Leg = Literal["majors", "meme"]
Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class AccountState:
    """Snapshot of an account on a single venue."""

    equity: Decimal
    cash: Decimal
    venue: Venue
    day_pl_pct: Decimal
    phase_pl_pct: Decimal
    open_positions_count: int
    trades_last_hour: int


@dataclass(frozen=True)
class Position:
    """An open position on a venue."""

    symbol: str
    venue: Venue
    qty: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pl_pct: Decimal
    stop_price: Decimal | None


@dataclass(frozen=True)
class OrderIntent:
    """A proposed trade, pre-gate. Gates evaluate this; on pass it becomes a real order."""

    symbol: str
    venue: Venue
    side: Side
    qty: Decimal
    intended_cost_usd: Decimal
    leg: Leg


@dataclass(frozen=True)
class GateResult:
    """Result of a single gate evaluation."""

    passed: bool
    gate_name: str
    reason: str | None
