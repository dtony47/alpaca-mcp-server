"""
backtest.py — Simple historical evaluation for the combined strategy.

This is intentionally lightweight (no external backtesting framework).
It simulates a single-position strategy:
  - enter (buy) when signal becomes BUY
  - exit (sell) when signal becomes SELL
  - ignore HOLD

It is meant to give an LLM (and you) quick feedback on strategy behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

import indicators
import market_data
import sentiment as sentiment_mod


@dataclass
class BacktestResult:
    symbol: str
    days: int
    trades: int
    start_price: float
    end_price: float
    buy_and_hold_return: float
    strategy_return: float
    equity_curve: list[dict[str, Any]]


def _signal_for_row(
    symbol: str,
    df: pd.DataFrame,
    i: int,
    *,
    short_period: int,
    long_period: int,
    use_sentiment: bool,
) -> str:
    """
    Row-based approximation of `strategy.analyze` that avoids calling external APIs
    repeatedly. Sentiment is optionally computed once and applied as a constant bias.
    """
    if i < long_period + 2:
        return "HOLD"

    prev = df.iloc[i - 1]
    curr = df.iloc[i]

    short_prev, long_prev = prev["short_ma"], prev["long_ma"]
    short_now, long_now = curr["short_ma"], curr["long_ma"]
    rsi_now = curr["rsi"]

    # MA score
    ma_score = 0.0
    if short_prev <= long_prev and short_now > long_now:
        ma_score = +1.5
    elif short_prev >= long_prev and short_now < long_now:
        ma_score = -1.5
    elif short_now > long_now:
        ma_score = +0.5
    else:
        ma_score = -0.5

    # RSI score
    rsi_score = 0.0
    if 30 <= rsi_now <= 60:
        rsi_score = +0.5
    elif rsi_now > 70 or rsi_now < 30:
        rsi_score = -0.5

    sent_score = 0.0
    if use_sentiment:
        sent = sentiment_mod.analyze(symbol)
        if sent.label == "BULLISH":
            sent_score = +0.5
        elif sent.label == "BEARISH":
            sent_score = -0.5

    total = ma_score + rsi_score + sent_score
    if total >= 1.5:
        return "BUY"
    if total <= -1.5:
        return "SELL"
    return "HOLD"


def run_backtest(
    symbol: str,
    *,
    days: int = 365,
    short_period: int = 20,
    long_period: int = 50,
    use_sentiment: bool = False,
) -> BacktestResult:
    """
    Backtest over daily bars for the past `days`.

    Args:
      use_sentiment: default False to avoid rate limits and keep test deterministic.
    """
    df = market_data.get_bars(symbol, days=days)
    if df.empty or len(df) < long_period + 5:
        raise ValueError(f"Not enough bars to backtest {symbol}")

    df = df.copy()
    df["short_ma"] = indicators.sma(df, short_period)
    df["long_ma"] = indicators.sma(df, long_period)
    df["rsi"] = indicators.rsi(df, 14)

    prices = df["close"].astype(float)
    start_price = float(prices.iloc[0])
    end_price = float(prices.iloc[-1])
    buy_and_hold_return = (end_price / start_price) - 1.0

    in_pos = False
    entry_price = 0.0
    equity = 1.0
    trades = 0
    curve: list[dict[str, Any]] = []

    for i in range(len(df)):
        ts = str(df.index[i])[:19]
        price = float(prices.iloc[i])
        sig = _signal_for_row(
            symbol,
            df,
            i,
            short_period=short_period,
            long_period=long_period,
            use_sentiment=use_sentiment,
        )

        if sig == "BUY" and not in_pos:
            in_pos = True
            entry_price = price
            trades += 1
        elif sig == "SELL" and in_pos:
            # realize PnL
            equity *= price / entry_price
            in_pos = False
            entry_price = 0.0

        # mark-to-market
        m2m = equity * (price / entry_price) if in_pos and entry_price else equity
        curve.append({"t": ts, "price": price, "signal": sig, "equity": round(m2m, 6)})

    # close at end if still holding
    if in_pos and entry_price:
        equity *= end_price / entry_price

    return BacktestResult(
        symbol=symbol,
        days=days,
        trades=trades,
        start_price=start_price,
        end_price=end_price,
        buy_and_hold_return=round(buy_and_hold_return, 6),
        strategy_return=round(equity - 1.0, 6),
        equity_curve=curve[-250:],  # keep payload small
    )

