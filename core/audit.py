"""Append-only trade log writer. Idempotent on trade_id."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from core.types import Leg, Side, Venue


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    timestamp: datetime
    leg: Leg
    venue: Venue
    symbol: str
    side: Side
    qty: Decimal
    price: Decimal
    cost_usd: Decimal
    thesis: str
    stop_price: Decimal | None
    target_price: Decimal | None


def log_trade(record: TradeRecord, path: Path) -> None:
    """Append a TradeRecord to the trade log markdown file. Idempotent on trade_id."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if record.trade_id in existing:
            return  # idempotent: already logged
    else:
        path.write_text("", encoding="utf-8")

    entry = _format_entry(record)
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)


def _format_entry(r: TradeRecord) -> str:
    stop = f"${r.stop_price}" if r.stop_price is not None else "—"
    target = f"${r.target_price}" if r.target_price is not None else "—"
    timestamp_str = r.timestamp.isoformat()
    return (
        f"\n### Trade {r.trade_id} — {timestamp_str}\n"
        f"- **Leg:** {r.leg}\n"
        f"- **Venue:** {r.venue}\n"
        f"- **Symbol:** {r.symbol}\n"
        f"- **Side:** {r.side}\n"
        f"- **Qty:** {r.qty}\n"
        f"- **Price:** ${r.price}\n"
        f"- **Cost:** ${r.cost_usd}\n"
        f"- **Stop:** {stop}\n"
        f"- **Target:** {target}\n"
        f"- **Thesis:** {r.thesis}\n"
    )
