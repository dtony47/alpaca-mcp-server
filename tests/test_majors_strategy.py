"""Tests for majors.strategy — composite signal computation."""

from decimal import Decimal

import pandas as pd
import pytest

from majors.strategy import compute_signal


def _make_bars(closes: list[float]) -> pd.DataFrame:
    """Build a minimal OHLC DataFrame with monotone close prices."""
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.001 for c in closes],
            "low": [c * 0.999 for c in closes],
            "close": closes,
            "volume": [1.0] * len(closes),
        }
    )


def test_signal_has_required_fields():
    closes = [100.0 + i for i in range(60)]  # rising line
    bars = _make_bars(closes)

    sig = compute_signal(bars, short_period=20, long_period=50)

    assert sig.symbol_action in {"BUY", "SELL", "HOLD"}
    assert isinstance(sig.score, float)
    assert isinstance(sig.current_price, Decimal)
    assert isinstance(sig.short_ma, Decimal)
    assert isinstance(sig.long_ma, Decimal)
    assert isinstance(sig.rsi, Decimal)
    assert isinstance(sig.score_breakdown, dict)


def test_compute_signal_too_few_bars_raises():
    bars = _make_bars([100.0] * 50)  # < long_period + 2 = 52
    with pytest.raises(ValueError, match="Need at least 52 bars"):
        compute_signal(bars, short_period=20, long_period=50)


def test_compute_signal_bullish_cross_buys():
    # 20 flat bars, then 10 bars zigzagging below (SMA5 < SMA20), then a jump that
    # pulls SMA5 above SMA20 exactly at the last bar (fresh bullish crossover).
    closes = [100.0] * 20 + [99, 98, 99, 98, 99, 98, 99, 98, 99, 98] + [104.0]
    bars = _make_bars(closes)

    sig = compute_signal(bars, short_period=5, long_period=20)

    assert sig.symbol_action == "BUY"
    assert sig.score >= 1.5
    assert "crossover" in sig.reason.lower() or "uptrend" in sig.reason.lower()


def test_compute_signal_bearish_cross_sells():
    # 20 flat bars, then 10 bars zigzagging above (SMA5 > SMA20), then a sharp drop
    # that pulls SMA5 below SMA20 exactly at the last bar (fresh bearish crossover).
    closes = [100.0] * 20 + [101, 102, 101, 102, 101, 102, 101, 102, 101, 102] + [92.0]
    bars = _make_bars(closes)

    sig = compute_signal(bars, short_period=5, long_period=20)

    assert sig.symbol_action == "SELL"
    assert sig.score <= -1.5


def test_compute_signal_flat_holds():
    closes = [100.0] * 60
    bars = _make_bars(closes)

    sig = compute_signal(bars, short_period=20, long_period=50)

    assert sig.symbol_action == "HOLD"
    assert -1.5 < sig.score < 1.5


def test_compute_signal_score_breakdown_sums_to_total():
    closes = [100.0 + i for i in range(60)]
    bars = _make_bars(closes)

    sig = compute_signal(bars, short_period=20, long_period=50)
    bd = sig.score_breakdown

    assert pytest.approx(bd["ma"] + bd["rsi"]) == bd["total"]
    assert bd["total"] == sig.score
