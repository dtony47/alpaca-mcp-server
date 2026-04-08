"""
market_data.py — Fetch real-time quotes and historical OHLCV bars.

Key concepts:
  - OHLCV: Open, High, Low, Close, Volume — the building blocks of every chart
  - Bar:   A single time period's price summary (e.g. one day)
  - Quote: The current bid (buy) and ask (sell) price
"""
import pandas as pd
from datetime import datetime, timedelta, timezone
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import (
    StockLatestQuoteRequest,
    StockBarsRequest,
    CryptoLatestQuoteRequest,
    CryptoBarsRequest,
)
from alpaca.data.timeframe import TimeFrame
import config

# These clients don't require auth for market data (but we pass keys anyway)
_stock_client  = StockHistoricalDataClient(config.API_KEY, config.API_SECRET)
_crypto_client = CryptoHistoricalDataClient(config.API_KEY, config.API_SECRET)


def is_crypto(symbol: str) -> bool:
    """Crypto symbols on Alpaca use slash notation: BTC/USD, ETH/USD."""
    return "/" in symbol


def get_quote(symbol: str) -> dict:
    """
    Get the latest bid/ask quote for a stock or crypto.
    Returns a dict with 'bid', 'ask', and 'mid' price.
    """
    if is_crypto(symbol):
        req = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
        quote = _crypto_client.get_crypto_latest_quote(req)[symbol]
    else:
        # Free accounts use IEX feed
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed="iex")
        quote = _stock_client.get_stock_latest_quote(req)[symbol]

    bid = float(quote.bid_price)
    ask = float(quote.ask_price)
    return {"symbol": symbol, "bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 4)}


def get_bars(symbol: str, days: int = 60, timeframe: TimeFrame = TimeFrame.Day) -> pd.DataFrame:
    """
    Fetch historical OHLCV bars as a pandas DataFrame.

    Args:
        symbol:    Ticker like 'AAPL' or 'BTC/USD'
        days:      How many calendar days of history to fetch
        timeframe: TimeFrame.Day, TimeFrame.Hour, TimeFrame.Minute, etc.

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    if is_crypto(symbol):
        req  = CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start, end=end)
        bars = _crypto_client.get_crypto_bars(req)[symbol]
    else:
        # Free Alpaca accounts use the IEX feed (not SIP which requires a paid subscription)
        req  = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start, end=end, feed="iex")
        bars = _stock_client.get_stock_bars(req)[symbol]

    df = pd.DataFrame([{
        "timestamp": b.timestamp,
        "open":      float(b.open),
        "high":      float(b.high),
        "low":       float(b.low),
        "close":     float(b.close),
        "volume":    float(b.volume),
    } for b in bars])

    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df
