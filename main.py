"""
main.py — CLI dashboard for your Alpaca paper trading toolkit.

Usage:
  python main.py                          # Full dashboard
  python main.py account                  # Account overview
  python main.py positions                # Open positions
  python main.py orders                   # Recent orders
  python main.py risk                     # Risk summary
  python main.py quote AAPL               # Get a quote
  python main.py quote BTC/USD            # Crypto quote
  python main.py snapshot AAPL            # Polygon full snapshot
  python main.py sentiment AAPL           # News sentiment analysis
  python main.py flow AAPL                # Options flow / whale activity
  python main.py dex CREPE                # DEX token full data + signal
  python main.py dex PEPE                 # Works for any Web3/DeFi token
  python main.py buy AAPL 500             # Buy $500 of AAPL
  python main.py sell AAPL 500            # Sell $500 of AAPL
  python main.py close AAPL               # Close full AAPL position
  python main.py closeall                 # Close ALL positions (careful!)
  python main.py analyze AAPL             # Combined signal analysis
  python main.py scan AAPL MSFT BTC/USD   # Scan multiple symbols
  python main.py trade AAPL               # Analyze + auto-trade (dry run)
  python main.py trade AAPL --live        # Analyze + auto-trade (REAL paper order)
"""
import sys
import account
import market_data
import polygon_data
import sentiment as sentiment_mod
import strategy
import dex_data
import dex_strategy
import trader
import risk as risk_module
from account import get_client

# Default watchlist for scanning
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTC/USD", "ETH/USD"]


def cmd_dashboard():
    account.show_account()
    account.show_positions()
    risk_module.risk_report(get_client())
    account.show_orders(limit=5)


def cmd_quote(symbol: str):
    q = market_data.get_quote(symbol)
    print(f"\n{symbol}  |  Bid: ${q['bid']:,.4f}  Ask: ${q['ask']:,.4f}  Mid: ${q['mid']:,.4f}")


def main():
    args = sys.argv[1:]

    if not args:
        cmd_dashboard()

    elif args[0] == "account":
        account.show_account()

    elif args[0] == "positions":
        account.show_positions()

    elif args[0] == "orders":
        limit = int(args[1]) if len(args) > 1 else 10
        account.show_orders(limit=limit)

    elif args[0] == "risk":
        risk_module.risk_report(get_client())

    elif args[0] == "quote" and len(args) > 1:
        cmd_quote(args[1])

    elif args[0] == "snapshot" and len(args) > 1:
        polygon_data.show_snapshot(args[1])

    elif args[0] == "sentiment" and len(args) > 1:
        sentiment_mod.show(args[1])

    elif args[0] == "flow" and len(args) > 1:
        polygon_data.show_options_flow(args[1])

    elif args[0] == "dex" and len(args) > 1:
        query = " ".join(args[1:])
        dex_data.show_token(query)
        dex_strategy.run(query)

    elif args[0] == "buy" and len(args) >= 3:
        symbol, amount = args[1], float(args[2])
        trader.buy(symbol, notional=amount)

    elif args[0] == "sell" and len(args) >= 3:
        symbol, amount = args[1], float(args[2])
        trader.sell(symbol, notional=amount)

    elif args[0] == "close" and len(args) > 1:
        trader.close_position(args[1])

    elif args[0] == "closeall":
        confirm = input("Close ALL positions? Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            trader.close_all_positions()
        else:
            print("Cancelled.")

    elif args[0] == "analyze" and len(args) > 1:
        strategy.run(args[1], execute=False)

    elif args[0] == "scan":
        symbols = args[1:] if len(args) > 1 else DEFAULT_WATCHLIST
        strategy.scan(symbols)

    elif args[0] == "trade" and len(args) > 1:
        symbol  = args[1]
        live    = "--live" in args
        dry_run = not live
        if live:
            print("[LIVE MODE] Orders will be submitted to paper account.")
        else:
            print("[DRY RUN] No orders will be submitted. Pass --live to execute.")
        strategy.run(symbol, execute=True, dry_run=dry_run)

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
