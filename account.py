"""
account.py — View account info, open positions, and recent orders.

Key concepts:
  - Equity:        Total portfolio value (cash + market value of positions)
  - Buying Power:  How much you can still spend (may be 2x equity on margin)
  - Unrealized P&L: Profit/loss on positions you haven't closed yet
"""
from tabulate import tabulate
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
import config


def get_client() -> TradingClient:
    return TradingClient(config.API_KEY, config.API_SECRET, paper=True)


def show_account():
    """Print a summary of your account balances."""
    client = get_client()
    acct = client.get_account()

    rows = [
        ["Equity",           f"${float(acct.equity):,.2f}"],
        ["Cash",             f"${float(acct.cash):,.2f}"],
        ["Buying Power",     f"${float(acct.buying_power):,.2f}"],
        ["Portfolio Value",  f"${float(acct.portfolio_value):,.2f}"],
        ["Day Trade Count",  acct.daytrade_count],
        ["Account Status",   acct.status],
    ]
    print("\n=== Account Overview ===")
    print(tabulate(rows, headers=["Field", "Value"], tablefmt="rounded_outline"))


def show_positions():
    """Print all open positions with P&L."""
    client = get_client()
    positions = client.get_all_positions()

    if not positions:
        print("\nNo open positions.")
        return

    rows = []
    for p in positions:
        rows.append([
            p.symbol,
            p.qty,
            f"${float(p.avg_entry_price):,.2f}",
            f"${float(p.current_price):,.2f}",
            f"${float(p.market_value):,.2f}",
            f"${float(p.unrealized_pl):,.2f}",
            f"{float(p.unrealized_plpc)*100:.2f}%",
        ])

    headers = ["Symbol", "Qty", "Avg Entry", "Current", "Mkt Value", "Unrealized P&L", "P&L %"]
    print("\n=== Open Positions ===")
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))


def show_orders(limit: int = 10):
    """Print the most recent orders."""
    client = get_client()
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
    orders = client.get_orders(filter=request)

    if not orders:
        print("\nNo orders found.")
        return

    rows = []
    for o in orders:
        qty_or_notional = f"${float(o.notional):,.2f}" if o.notional else str(o.qty)
        rows.append([
            str(o.created_at)[:19],
            o.symbol,
            o.side.value,
            o.type.value,
            qty_or_notional,
            o.status.value,
            f"${float(o.filled_avg_price):,.2f}" if o.filled_avg_price else "-",
        ])

    headers = ["Time", "Symbol", "Side", "Type", "Size", "Status", "Fill Price"]
    print(f"\n=== Last {limit} Orders ===")
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
