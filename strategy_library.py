"""
strategy_library.py — Strategy templates + plain-English summaries.

Goal: provide a curated starting set of common, time-tested strategy families that
can be parameterized and iterated on with an LLM.

Notes:
  - These are not "copied" proprietary strategies; they are standard patterns.
  - All templates return structured output (signal + reason + parameters).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

import pandas as pd

import indicators
import market_data


Action = Literal["BUY", "SELL", "HOLD"]


@dataclass
class TemplateResult:
    template_id: str
    symbol: str
    action: Action
    reason: str
    price: float
    params: dict[str, Any]
    metrics: dict[str, Any]


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "trend_sma_crossover",
            "name": "Trend-following SMA crossover",
            "best_for": ["trending markets", "higher timeframes"],
            "risk": "whipsaws in chop",
        },
        {
            "id": "breakout_donchian",
            "name": "Breakout (Donchian channel)",
            "best_for": ["momentum breakouts", "trend initiation"],
            "risk": "false breakouts without filters",
        },
        {
            "id": "meanreversion_bbands_rsi",
            "name": "Mean reversion (Bollinger + RSI)",
            "best_for": ["range-bound markets", "reversion-to-mean"],
            "risk": "gets steamrolled in strong trends",
        },
        {
            "id": "momentum_macd_filter",
            "name": "Momentum (MACD regime filter)",
            "best_for": ["momentum shifts", "trend continuation"],
            "risk": "late entries on sharp reversals",
        },
    ]


def describe_template(template_id: str) -> dict[str, Any]:
    templates = {t["id"]: t for t in list_templates()}
    if template_id not in templates:
        raise ValueError(f"Unknown template_id '{template_id}'")

    if template_id == "trend_sma_crossover":
        return {
            **templates[template_id],
            "summary": (
                "Buys when a faster SMA crosses above a slower SMA (trend turning bullish), "
                "sells when it crosses below. Optional RSI filter reduces overbought buys."
            ),
            "parameters": {
                "short_period": 20,
                "long_period": 50,
                "rsi_period": 14,
                "rsi_buy_max": 70,
                "bars_days": 200,
            },
            "tuning_notes": [
                "Increase periods to reduce churn (slower, fewer signals).",
                "Add filters (RSI, volatility, volume) to reduce chop trades.",
            ],
        }

    if template_id == "breakout_donchian":
        return {
            **templates[template_id],
            "summary": (
                "Buys when price breaks above the highest high of the last N bars; "
                "sells when price breaks below the lowest low of the last N bars. "
                "This is a classic trend-breakout pattern."
            ),
            "parameters": {
                "lookback": 20,
                "bars_days": 200,
                "use_rsi_filter": True,
                "rsi_period": 14,
                "rsi_breakout_min": 50,
            },
            "tuning_notes": [
                "Use longer lookback to avoid noise; shorter to be more reactive.",
                "Add a regime filter to avoid breakouts during low-volatility chop.",
            ],
        }

    if template_id == "meanreversion_bbands_rsi":
        return {
            **templates[template_id],
            "summary": (
                "Buys when price is below the lower Bollinger band and RSI is oversold; "
                "sells/avoids when price is above the upper band and RSI is overbought. "
                "Works best in sideways regimes."
            ),
            "parameters": {
                "bb_period": 20,
                "bb_std": 2.0,
                "rsi_period": 14,
                "rsi_buy_max": 35,
                "rsi_sell_min": 65,
                "bars_days": 200,
            },
            "tuning_notes": [
                "Lower std makes bands tighter (more trades); higher std reduces signals.",
                "Consider disabling during strong trend regimes.",
            ],
        }

    if template_id == "momentum_macd_filter":
        return {
            **templates[template_id],
            "summary": (
                "Uses MACD crossing its signal line as a momentum trigger, optionally "
                "requiring price to be above a trend SMA to avoid counter-trend entries."
            ),
            "parameters": {
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "trend_sma": 50,
                "bars_days": 250,
                "require_trend_filter": True,
            },
            "tuning_notes": [
                "Trend filter reduces false positives but misses early reversals.",
                "MACD is slower on lower timeframes; consider faster params if needed.",
            ],
        }

    raise ValueError(f"Unhandled template_id '{template_id}'")


def _get_bars(symbol: str, bars_days: int) -> pd.DataFrame:
    df = market_data.get_bars(symbol, days=bars_days)
    if df is None or df.empty:
        raise ValueError(f"No bars returned for {symbol}")
    return df.copy()


def run_template(template_id: str, symbol: str, *, params: Optional[dict[str, Any]] = None) -> TemplateResult:
    info = describe_template(template_id)
    p = {**info["parameters"], **(params or {})}

    df = _get_bars(symbol, int(p.get("bars_days", 200)))
    price = float(df["close"].iloc[-1])

    if template_id == "trend_sma_crossover":
        short_period = int(p["short_period"])
        long_period = int(p["long_period"])
        rsi_period = int(p["rsi_period"])
        rsi_buy_max = float(p["rsi_buy_max"])

        df["sma_s"] = indicators.sma(df, short_period)
        df["sma_l"] = indicators.sma(df, long_period)
        df["rsi"] = indicators.rsi(df, rsi_period)
        if len(df) < long_period + 2:
            raise ValueError("Not enough bars for SMA crossover")

        prev = df.iloc[-2]
        curr = df.iloc[-1]
        crossed_up = prev["sma_s"] <= prev["sma_l"] and curr["sma_s"] > curr["sma_l"]
        crossed_dn = prev["sma_s"] >= prev["sma_l"] and curr["sma_s"] < curr["sma_l"]

        action: Action = "HOLD"
        reason = "No crossover"
        if crossed_up and float(curr["rsi"]) <= rsi_buy_max:
            action = "BUY"
            reason = f"SMA{short_period} crossed above SMA{long_period} with RSI={curr['rsi']:.1f}"
        elif crossed_dn:
            action = "SELL"
            reason = f"SMA{short_period} crossed below SMA{long_period}"
        elif crossed_up:
            action = "HOLD"
            reason = f"Bullish crossover but RSI filter blocked (RSI={curr['rsi']:.1f} > {rsi_buy_max})"

        return TemplateResult(
            template_id=template_id,
            symbol=symbol,
            action=action,
            reason=reason,
            price=price,
            params=p,
            metrics={
                "sma_short": float(curr["sma_s"]),
                "sma_long": float(curr["sma_l"]),
                "rsi": float(curr["rsi"]),
            },
        )

    if template_id == "breakout_donchian":
        lookback = int(p["lookback"])
        use_rsi_filter = bool(p.get("use_rsi_filter", True))
        rsi_period = int(p.get("rsi_period", 14))
        rsi_breakout_min = float(p.get("rsi_breakout_min", 50))

        if len(df) < lookback + 2:
            raise ValueError("Not enough bars for Donchian breakout")

        df["rsi"] = indicators.rsi(df, rsi_period)
        high_n = float(df["high"].iloc[-(lookback + 1):-1].max())
        low_n = float(df["low"].iloc[-(lookback + 1):-1].min())
        rsi_now = float(df["rsi"].iloc[-1])

        action = "HOLD"
        reason = f"Inside channel ({low_n:.2f}..{high_n:.2f})"

        if price > high_n:
            if (not use_rsi_filter) or (rsi_now >= rsi_breakout_min):
                action = "BUY"
                reason = f"Breakout above {lookback}-bar high ({high_n:.2f}); RSI={rsi_now:.1f}"
            else:
                reason = f"Breakout but RSI filter blocked (RSI={rsi_now:.1f} < {rsi_breakout_min})"
        elif price < low_n:
            action = "SELL"
            reason = f"Breakdown below {lookback}-bar low ({low_n:.2f})"

        return TemplateResult(
            template_id=template_id,
            symbol=symbol,
            action=action,
            reason=reason,
            price=price,
            params=p,
            metrics={"donchian_high": high_n, "donchian_low": low_n, "rsi": rsi_now},
        )

    if template_id == "meanreversion_bbands_rsi":
        bb_period = int(p["bb_period"])
        bb_std = float(p["bb_std"])
        rsi_period = int(p["rsi_period"])
        rsi_buy_max = float(p["rsi_buy_max"])
        rsi_sell_min = float(p["rsi_sell_min"])

        if len(df) < bb_period + 5:
            raise ValueError("Not enough bars for Bollinger bands")

        upper, mid, lower = indicators.bollinger_bands(df, bb_period, bb_std)
        df["bb_u"], df["bb_m"], df["bb_l"] = upper, mid, lower
        df["rsi"] = indicators.rsi(df, rsi_period)
        curr = df.iloc[-1]

        bb_u = float(curr["bb_u"])
        bb_l = float(curr["bb_l"])
        rsi_now = float(curr["rsi"])

        action = "HOLD"
        reason = "No extreme"
        if price <= bb_l and rsi_now <= rsi_buy_max:
            action = "BUY"
            reason = f"Below lower band with oversold RSI ({rsi_now:.1f})"
        elif price >= bb_u and rsi_now >= rsi_sell_min:
            action = "SELL"
            reason = f"Above upper band with overbought RSI ({rsi_now:.1f})"

        return TemplateResult(
            template_id=template_id,
            symbol=symbol,
            action=action,
            reason=reason,
            price=price,
            params=p,
            metrics={"bb_upper": bb_u, "bb_lower": bb_l, "rsi": rsi_now},
        )

    if template_id == "momentum_macd_filter":
        macd_fast = int(p["macd_fast"])
        macd_slow = int(p["macd_slow"])
        macd_signal = int(p["macd_signal"])
        trend_sma = int(p["trend_sma"])
        require_trend_filter = bool(p.get("require_trend_filter", True))

        macd_line, sig_line, hist = indicators.macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
        df["macd"] = macd_line
        df["macd_sig"] = sig_line
        df["macd_hist"] = hist
        df["trend_sma"] = indicators.sma(df, trend_sma)
        if len(df) < max(macd_slow, trend_sma) + 5:
            raise ValueError("Not enough bars for MACD template")

        prev = df.iloc[-2]
        curr = df.iloc[-1]
        cross_up = prev["macd"] <= prev["macd_sig"] and curr["macd"] > curr["macd_sig"]
        cross_dn = prev["macd"] >= prev["macd_sig"] and curr["macd"] < curr["macd_sig"]

        trend_ok = True
        if require_trend_filter:
            trend_ok = float(curr["close"]) >= float(curr["trend_sma"])

        action = "HOLD"
        reason = "No MACD cross"
        if cross_up and trend_ok:
            action = "BUY"
            reason = "MACD crossed above signal with trend filter OK"
        elif cross_up and not trend_ok:
            reason = "MACD cross-up but trend filter blocked"
        elif cross_dn:
            action = "SELL"
            reason = "MACD crossed below signal"

        return TemplateResult(
            template_id=template_id,
            symbol=symbol,
            action=action,
            reason=reason,
            price=price,
            params=p,
            metrics={
                "macd": float(curr["macd"]),
                "macd_signal": float(curr["macd_sig"]),
                "macd_hist": float(curr["macd_hist"]),
                "trend_sma": float(curr["trend_sma"]),
            },
        )

    raise ValueError(f"Unknown template_id '{template_id}'")

