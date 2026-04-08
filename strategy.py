"""
strategy.py — Combined signal strategy: MA Crossover + Sentiment + Options Flow.

HOW THE COMBINED SCORING WORKS:
  Each signal contributes to a composite score from -3 to +3:

    Signal              Weight   BUY (+)              SELL/HOLD (-)
    ──────────────────  ──────   ───────────────────  ─────────────────
    MA Crossover          1.5    Short > Long cross   Short < Long cross
    RSI filter            0.5    RSI 30–60 (healthy)  RSI >70 or <30
    News Sentiment        0.5    Score > 0.2          Score < -0.2
    Options Flow          0.5    P/C ratio < 0.7      P/C ratio > 1.0

  Final decision:
    Score >= +1.5  → BUY
    Score <= -1.5  → SELL
    Otherwise      → HOLD

MA Crossover baseline:
  Short MA (default 20d) crosses above Long MA (50d) → bullish trend change.
  Short MA crosses below Long MA → bearish trend change.
"""
import pandas as pd
from dataclasses import dataclass, field
from typing import Literal, Optional

import market_data
import indicators
import sentiment as sentiment_mod
import trader
import risk as risk_module
from account import get_client


@dataclass
class Signal:
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    reason: str
    score: float                        # composite score -3..+3
    short_ma: float
    long_ma: float
    current_price: float
    rsi: float
    sentiment_label: str = "NEUTRAL"
    sentiment_score: float = 0.0
    options_signal: str = "N/A"
    put_call_ratio: float = 0.0
    score_breakdown: dict = field(default_factory=dict)


def analyze(symbol: str, short_period: int = 20, long_period: int = 50,
            days: int = 100, use_options: bool = True) -> Signal:
    """
    Run full combined analysis on a symbol.

    Args:
        symbol:       Ticker (e.g. 'AAPL' or 'BTC/USD')
        short_period: Short MA window (default 20)
        long_period:  Long MA window (default 50)
        days:         Historical bars to fetch
        use_options:  Include options flow (stocks only, skipped for crypto)

    Returns:
        Signal with composite score, action, and full breakdown
    """
    is_crypto = "/" in symbol

    # ── 1. Fetch bars & compute MAs ─────────────────────────────────────────
    df = market_data.get_bars(symbol, days=days)
    if len(df) < long_period + 2:
        raise ValueError(f"Not enough data for {symbol}. Need at least {long_period + 2} bars.")

    df["short_ma"] = indicators.sma(df, short_period)
    df["long_ma"]  = indicators.sma(df, long_period)
    df["rsi"]      = indicators.rsi(df, 14)

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    short_now, long_now   = curr["short_ma"], curr["long_ma"]
    short_prev, long_prev = prev["short_ma"], prev["long_ma"]
    rsi_now               = curr["rsi"]
    price_now             = curr["close"]

    # ── 2. MA signal score ───────────────────────────────────────────────────
    ma_score = 0.0
    if short_prev <= long_prev and short_now > long_now:
        ma_score = +1.5
        ma_reason = f"Bullish crossover: SMA{short_period} crossed above SMA{long_period}"
    elif short_prev >= long_prev and short_now < long_now:
        ma_score = -1.5
        ma_reason = f"Bearish crossover: SMA{short_period} crossed below SMA{long_period}"
    elif short_now > long_now:
        ma_score = +0.5
        ma_reason = f"Uptrend: SMA{short_period} above SMA{long_period} (no new crossover)"
    else:
        ma_score = -0.5
        ma_reason = f"Downtrend: SMA{short_period} below SMA{long_period} (no new crossover)"

    # ── 3. RSI score ─────────────────────────────────────────────────────────
    rsi_score = 0.0
    if 30 <= rsi_now <= 60:
        rsi_score = +0.5
        rsi_reason = f"RSI {rsi_now:.1f} (healthy range)"
    elif rsi_now > 70:
        rsi_score = -0.5
        rsi_reason = f"RSI {rsi_now:.1f} (overbought — dampening buy signal)"
    elif rsi_now < 30:
        rsi_score = -0.5
        rsi_reason = f"RSI {rsi_now:.1f} (oversold — dampening sell signal)"
    else:
        rsi_score = 0.0
        rsi_reason = f"RSI {rsi_now:.1f} (neutral zone)"

    # ── 4. Sentiment score ───────────────────────────────────────────────────
    sent = sentiment_mod.analyze(symbol)
    if sent.label == "BULLISH":
        sent_score = +0.5
    elif sent.label == "BEARISH":
        sent_score = -0.5
    else:
        sent_score = 0.0

    # ── 5. Options flow score (stocks only) ──────────────────────────────────
    opts_score = 0.0
    pc_ratio   = 0.0
    opts_label = "N/A"

    if not is_crypto and use_options:
        try:
            from polygon_data import get_options_snapshot
            flow = get_options_snapshot(symbol)
            pc_ratio   = flow.get("put_call_ratio", 0)
            opts_label = flow.get("options_signal", "NEUTRAL")
            if opts_label == "BULLISH":
                opts_score = +0.5
            elif opts_label == "BEARISH":
                opts_score = -0.5
        except Exception:
            opts_label = "N/A (unavailable)"

    # ── 6. Composite score & decision ────────────────────────────────────────
    total = ma_score + rsi_score + sent_score + opts_score

    if total >= 1.5:
        action = "BUY"
    elif total <= -1.5:
        action = "SELL"
    else:
        action = "HOLD"

    reason_parts = [
        ma_reason,
        rsi_reason,
        f"Sentiment: {sent.label} ({sent.score:+.2f})",
    ]
    if opts_label != "N/A":
        reason_parts.append(f"Options: {opts_label} (P/C={pc_ratio:.2f})")

    return Signal(
        symbol=symbol,
        action=action,
        reason=" | ".join(reason_parts),
        score=round(total, 2),
        short_ma=round(short_now, 4),
        long_ma=round(long_now, 4),
        current_price=round(price_now, 4),
        rsi=round(rsi_now, 2),
        sentiment_label=sent.label,
        sentiment_score=sent.score,
        options_signal=opts_label,
        put_call_ratio=pc_ratio,
        score_breakdown={
            "ma":        ma_score,
            "rsi":       rsi_score,
            "sentiment": sent_score,
            "options":   opts_score,
            "total":     round(total, 2),
        },
    )


def run(symbol: str, short_period: int = 20, long_period: int = 50,
        execute: bool = False, dry_run: bool = True):
    """
    Analyze a symbol and optionally execute the trade.
    """
    print(f"\n{'='*60}")
    print(f"  Combined Signal Analysis — {symbol}")
    print(f"  MA: {short_period}d / {long_period}d  |  Sentiment + Options flow")
    print(f"{'='*60}")

    sig = analyze(symbol, short_period, long_period)

    # Score bar: -3 to +3 mapped to 0..20
    bar_len  = 20
    bar_pos  = int((sig.score + 3) / 6 * bar_len)
    bar      = "░" * bar_pos + "▓" + "░" * (bar_len - bar_pos)

    print(f"  Price:        ${sig.current_price:,.4f}")
    print(f"  SMA{short_period:02d}:         ${sig.short_ma:,.4f}")
    print(f"  SMA{long_period:02d}:         ${sig.long_ma:,.4f}")
    print(f"  RSI (14):     {sig.rsi:.1f}")
    print(f"  Sentiment:    {sig.sentiment_label} ({sig.sentiment_score:+.2f})")
    if sig.options_signal != "N/A":
        print(f"  Options Flow: {sig.options_signal} (P/C ratio: {sig.put_call_ratio:.2f})")
    print(f"  Score:        {sig.score:+.2f}  [{bar}]")
    print(f"  ── Breakdown: MA={sig.score_breakdown['ma']:+.1f} | "
          f"RSI={sig.score_breakdown['rsi']:+.1f} | "
          f"Sentiment={sig.score_breakdown['sentiment']:+.1f} | "
          f"Options={sig.score_breakdown['options']:+.1f}")
    print(f"\n  SIGNAL: {'🟢 ' if sig.action=='BUY' else '🔴 ' if sig.action=='SELL' else '⚪ '}{sig.action}")
    print(f"{'='*60}")

    if execute:
        client = get_client()
        if sig.action == "BUY":
            notional = risk_module.calc_position_size(client, sig.current_price)
            print(f"\n  → Executing BUY ${notional:,.2f} of {symbol}")
            trader.buy(symbol, notional=notional, dry_run=dry_run)
        elif sig.action == "SELL":
            try:
                position = client.get_open_position(symbol)
                print(f"\n  → Executing SELL (closing {position.qty} shares of {symbol})")
                trader.close_position(symbol, dry_run=dry_run)
            except Exception:
                print(f"\n  → SELL signal but no open position in {symbol}. Nothing to sell.")
        else:
            print("\n  → HOLD — no order placed.")

    return sig


def scan(symbols: list, short_period: int = 20, long_period: int = 50,
         execute: bool = False, dry_run: bool = True):
    """Scan multiple symbols and print a ranked summary table."""
    from tabulate import tabulate
    rows = []
    for sym in symbols:
        try:
            sig = analyze(sym, short_period, long_period)
            rows.append([
                sym,
                f"${sig.current_price:,.2f}",
                f"{sig.rsi:.0f}",
                sig.sentiment_label,
                sig.options_signal.split(" ")[0],
                f"{sig.score:+.1f}",
                sig.action,
            ])
            if execute and sig.action != "HOLD":
                run(sym, short_period, long_period, execute=execute, dry_run=dry_run)
        except Exception as e:
            rows.append([sym, "ERROR", "-", "-", "-", "-", str(e)[:40]])

    # Sort by score descending
    rows.sort(key=lambda r: float(r[5]) if r[5] not in ("-",) else 0, reverse=True)

    headers = ["Symbol", "Price", "RSI", "Sentiment", "Options", "Score", "Signal"]
    print("\n=== Combined Signal Scan ===")
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
