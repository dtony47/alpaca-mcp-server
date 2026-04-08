"""
risk.py — Position sizing and risk management.

Key concepts:
  - Position Sizing:  Never put too much capital in one trade.
  - Stop-Loss:        A pre-set price at which you exit to cap your loss.
  - Risk/Reward:      Good trades aim for at least 2:1 reward vs risk.
"""
from alpaca.trading.client import TradingClient
import config


def get_portfolio_value(client: TradingClient) -> float:
    """Return current total portfolio value in USD."""
    acct = client.get_account()
    return float(acct.portfolio_value)


def calc_position_size(client: TradingClient, price: float) -> float:
    """
    Calculate a safe dollar amount to invest in a single trade.

    Rules applied (from config.py):
      - Never exceed MAX_POSITION_PCT of portfolio value
      - Never exceed MAX_TRADE_USD hard cap

    Returns: dollar amount to invest
    """
    portfolio = get_portfolio_value(client)
    max_by_pct = portfolio * config.MAX_POSITION_PCT
    safe_amount = min(max_by_pct, config.MAX_TRADE_USD)

    # Don't invest more than available buying power
    buying_power = float(client.get_account().buying_power)
    return round(min(safe_amount, buying_power), 2)


def calc_stop_loss_price(entry_price: float, side: str = "buy") -> float:
    """
    Calculate stop-loss price based on entry.

    For a buy: stop = entry * (1 - STOP_LOSS_PCT)   e.g. 2% below entry
    For a short: stop = entry * (1 + STOP_LOSS_PCT)  e.g. 2% above entry
    """
    if side == "buy":
        return round(entry_price * (1 - config.STOP_LOSS_PCT), 4)
    else:
        return round(entry_price * (1 + config.STOP_LOSS_PCT), 4)


def risk_report(client: TradingClient):
    """Print a risk summary for the current portfolio."""
    from tabulate import tabulate
    acct = client.get_account()
    portfolio = float(acct.portfolio_value)
    cash      = float(acct.cash)
    equity    = float(acct.equity)
    positions = client.get_all_positions()

    invested = sum(float(p.market_value) for p in positions)
    cash_pct  = (cash / portfolio * 100) if portfolio else 0
    inv_pct   = (invested / portfolio * 100) if portfolio else 0

    rows = [
        ["Portfolio Value",   f"${portfolio:,.2f}"],
        ["Cash (idle)",       f"${cash:,.2f}  ({cash_pct:.1f}%)"],
        ["Invested",          f"${invested:,.2f}  ({inv_pct:.1f}%)"],
        ["Max per trade",     f"${min(portfolio * config.MAX_POSITION_PCT, config.MAX_TRADE_USD):,.2f}"],
        ["Stop-loss %",       f"{config.STOP_LOSS_PCT*100:.1f}%"],
        ["Open positions",    len(positions)],
    ]
    print("\n=== Risk Summary ===")
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="rounded_outline"))
