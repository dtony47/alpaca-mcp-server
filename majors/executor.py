"""Executor for majors entries: market buy, initial stop, audit log."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from core.audit import TradeRecord, log_trade
from core.types import OrderIntent
from majors.alpaca_client import AlpacaClient, AlpacaError, AlpacaOrder
from majors.trail import initial_stop


@dataclass(frozen=True)
class ExecutionResult:
    buy_order_id: str
    stop_order_id: str
    fill_price: Decimal
    stop_price: Decimal


def execute_buy(
    client: AlpacaClient,
    intent: OrderIntent,
    now: datetime,
    trade_log_path: Path,
    thesis: str,
) -> ExecutionResult:
    """Place a market buy, place the initial stop-limit sell, then audit-log."""
    buy_coid = f"majors-{intent.symbol}-{_minute_iso(now)}"

    try:
        buy = client.place_market_buy(
            symbol=intent.symbol,
            notional=intent.intended_cost_usd,
            client_order_id=buy_coid,
        )
    except AlpacaError as exc:
        if "client_order_id" not in str(exc).lower() or "already" not in str(exc).lower():
            raise
        buy = _find_existing_order(client, intent.symbol, buy_coid)

    if buy.status != "filled" or buy.filled_avg_price is None:
        raise RuntimeError(f"buy not filled (status={buy.status})")

    fill_price = buy.filled_avg_price
    stop_price = initial_stop(fill_price)
    limit_price = (stop_price * Decimal("0.999")).quantize(Decimal("0.01"))
    stop = client.place_stop_limit_sell(
        symbol=intent.symbol,
        qty=buy.filled_qty,
        stop_price=stop_price,
        limit_price=limit_price,
        client_order_id=f"{buy_coid}-stop",
    )

    log_trade(
        TradeRecord(
            trade_id=buy_coid,
            timestamp=now,
            leg="majors",
            venue="alpaca",
            symbol=intent.symbol,
            side="buy",
            qty=buy.filled_qty,
            price=fill_price,
            cost_usd=(buy.filled_qty * fill_price).quantize(Decimal("0.01")),
            thesis=thesis,
            stop_price=stop_price,
            target_price=None,
        ),
        path=trade_log_path,
    )

    return ExecutionResult(
        buy_order_id=buy.id,
        stop_order_id=stop.id,
        fill_price=fill_price,
        stop_price=stop_price,
    )


def _find_existing_order(client: AlpacaClient, symbol: str, client_order_id: str) -> AlpacaOrder:
    for order in client.list_open_orders(symbol=symbol):
        if order.client_order_id == client_order_id:
            return order
    raise AlpacaError(f"duplicate client_order_id not found: {client_order_id}")


def _minute_iso(now: datetime) -> str:
    minute = now.replace(second=0, microsecond=0)
    if minute.tzinfo is not None:
        minute = minute.astimezone(UTC).replace(tzinfo=None)
    return f"{minute.isoformat()}Z"
