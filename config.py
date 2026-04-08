"""
config.py — Loads Alpaca credentials from .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_API_SECRET")
BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

# Safety check — always paper trading
assert "paper-api" in BASE_URL, "This toolkit is configured for paper trading only!"

# Risk limits (edit these to adjust your risk tolerance)
MAX_POSITION_PCT = 0.05   # Max 5% of portfolio per position
MAX_TRADE_USD    = 10_000 # Hard cap per single trade in USD
STOP_LOSS_PCT    = 0.02   # 2% stop-loss on every trade
