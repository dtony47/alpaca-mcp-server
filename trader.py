"""
trader.py — Place buy/sell orders with built-in risk controls.

Order types:
  - Market order:  Executes immediately at current market price. Fast, no price guarantee.
  - Limit order:   Executes only at your specified price or better. More control.
  - Stop order:    Triggers a market order when price hits your stop price (used for stop-loss).
"""
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, TrailingStopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import config
import risk as risk_module


def get_client() -> TradingClient:
    return TradingClient(config.API_KEY, config.API_SECRET, paper=True)


def buy(symbol: str, notional: float = None, qty: float = None, dry_run: bool = False) -> dict:
    """
    Place a market buy order.

    Args:
        symbol:   Ticker (e.g. 'AAPL', 'BTC/USD')
        notional: Dollar amount to spend (e.g. 500.00). Use this OR qty.
        qty:      Number of shares/coins. Use this OR notional.
        dry_run:  If True, prints the order details without submitting.

    Returns: Order dict with id, status, symbol, size
    """
    client = get_client()

    # Enforce risk limits on notional orders
    if notional is not None:
        max_allowed = risk_module.calc_position_size(client, price=1)
        if notional > max_allowed:
            print(f"[RISK] Capping order from ${notional:,.2f} to ${max_allowed:,.2f} (risk limit)")
            notional = max_allowed

    if dry_run:
        size_str = f"${notional:,.2f}" if notional else f"{qty} shares"
        print(f"[DRY RUN] Would BUY {size_str} of {symbol}")
        return {}

    req = MarketOrderRequest(
        symbol=symbol,
        notional=notional,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)
    size_str = f"${float(order.notional):,.2f}" if order.notional else f"{order.qty} shares"
    print(f"[BUY]  {symbol} {size_str} — Order ID: {order.id} | Status: {order.status}")
    return {"id": str(order.id), "symbol": symbol, "side": "buy", "status": order.status.value}


def sell(symbol: str, qty: float = None, notional: float = None, dry_run: bool = False) -> dict:
    """
    Place a market sell order.

    Args:
        symbol:   Ticker (e.g. 'AAPL')
        qty:      Number of shares/coins to sell. Use this OR notional.
        notional: Dollar value to sell. Use this OR qty.
        dry_run:  If True, prints the order details without submitting.
    """
    client = get_client()

    if dry_run:
        size_str = f"${notional:,.2f}" if notional else f"{qty} shares"
        print(f"[DRY RUN] Would SELL {size_str} of {symbol}")
        return {}

    req = MarketOrderRequest(
        symbol=symbol,
        notional=notional,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)
    size_str = f"${float(order.notional):,.2f}" if order.notional else f"{order.qty} shares"
    print(f"[SELL] {symbol} {size_str} — Order ID: {order.id} | Status: {order.status}")
    return {"id": str(order.id), "symbol": symbol, "side": "sell", "status": order.status.value}


def close_position(symbol: str, dry_run: bool = False) -> dict:
    """Close your entire position in a symbol."""
    client = get_client()

    if dry_run:
        print(f"[DRY RUN] Would CLOSE full position in {symbol}")
        return {}

    order = client.close_position(symbol)
    print(f"[CLOSE] {symbol} position closed — Order ID: {order.id}")
    return {"id": str(order.id), "symbol": symbol, "side": "sell", "status": order.status.value}


def close_all_positions(dry_run: bool = False):
    """Emergency: close ALL open positions."""
    client = get_client()

    if dry_run:
        positions = client.get_all_positions()
        print(f"[DRY RUN] Would CLOSE all {len(positions)} positions")
        return

    client.close_all_positions(cancel_orders=True)
    print("[CLOSE ALL] All positions closed and pending orders cancelled.")
