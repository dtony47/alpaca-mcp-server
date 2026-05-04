"""Composite signal: SMA crossover + RSI.

Pure functions over pandas DataFrames. No I/O.

Score breakdown (sum, range -2.0 to +2.0):
  MA crossover         ±1.5 on cross, ±0.5 trend, 0.0 ambiguous
  RSI filter           +0.5 healthy (30-60), -0.5 overbought (>70) or oversold (<30), 0 neutral

Decision:
  score >= +1.5 → BUY
  score <= -1.5 → SELL
  otherwise     → HOLD
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class Signal:
    symbol_action: Action
    score: float
    reason: str
    current_price: Decimal
    short_ma: Decimal
    long_ma: Decimal
    rsi: Decimal
    score_breakdown: dict[str, float] = field(default_factory=dict)


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_signal(
    bars: pd.DataFrame,
    short_period: int = 20,
    long_period: int = 50,
    rsi_period: int = 14,
) -> Signal:
    if len(bars) < long_period + 2:
        raise ValueError(
            f"Need at least {long_period + 2} bars; got {len(bars)}"
        )

    closes = bars["close"].astype(float)
    short_ma = _sma(closes, short_period)
    long_ma = _sma(closes, long_period)
    rsi_series = _rsi(closes, rsi_period)

    short_now = float(short_ma.iloc[-1])
    long_now = float(long_ma.iloc[-1])
    short_prev = float(short_ma.iloc[-2])
    long_prev = float(long_ma.iloc[-2])
    price_now = float(closes.iloc[-1])
    rsi_now = float(rsi_series.iloc[-1])

    # MA component
    if short_prev <= long_prev and short_now > long_now:
        ma_score = 1.5
        ma_reason = f"Bullish crossover SMA{short_period}>SMA{long_period}"
    elif short_prev >= long_prev and short_now < long_now:
        ma_score = -1.5
        ma_reason = f"Bearish crossover SMA{short_period}<SMA{long_period}"
    elif short_now > long_now:
        ma_score = 0.5
        ma_reason = f"Uptrend (SMA{short_period}>SMA{long_period}, no fresh cross)"
    else:
        ma_score = -0.5
        ma_reason = f"Downtrend (SMA{short_period}<SMA{long_period}, no fresh cross)"

    # RSI component
    if 30 <= rsi_now <= 60:
        rsi_score = 0.5
        rsi_reason = f"RSI {rsi_now:.1f} healthy"
    elif rsi_now > 70:
        rsi_score = -0.5
        rsi_reason = f"RSI {rsi_now:.1f} overbought"
    elif rsi_now < 30:
        rsi_score = -0.5
        rsi_reason = f"RSI {rsi_now:.1f} oversold"
    else:
        rsi_score = 0.0
        rsi_reason = f"RSI {rsi_now:.1f} neutral"

    total = round(ma_score + rsi_score, 2)
    if total >= 1.5:
        action: Action = "BUY"
    elif total <= -1.5:
        action = "SELL"
    else:
        action = "HOLD"

    return Signal(
        symbol_action=action,
        score=total,
        reason=" | ".join([ma_reason, rsi_reason]),
        current_price=Decimal(str(price_now)),
        short_ma=Decimal(str(round(short_now, 8))),
        long_ma=Decimal(str(round(long_now, 8))),
        rsi=Decimal(str(round(rsi_now, 4))),
        score_breakdown={"ma": ma_score, "rsi": rsi_score, "total": total},
    )
