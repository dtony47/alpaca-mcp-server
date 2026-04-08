"""
dex_strategy.py — Signal analysis for DEX/Web3 tokens.

DEX tokens are very different from stocks — we can't use moving averages on
historical bars (most DEX APIs don't give clean OHLCV data for free), so
instead we score based on on-chain health metrics:

SCORING SYSTEM (-4 to +4):

  Signal                Weight    Bullish                    Bearish
  ─────────────────     ──────    ─────────────────────────  ─────────────────────
  Price momentum         1.0      24h change > +5%           24h change < -5%
  Short-term momentum    0.5      1h change > +2%            1h change < -2%
  Buy pressure           1.0      >60% buys in 24h txns      <40% buys
  Volume/Liquidity       0.5      Vol/Liq > 0.3 (active)     Vol/Liq < 0.05 (dead)
  Liquidity health       0.5      Liq > $100k (safer)        Liq < $10k (risky)
  CoinGecko sentiment    0.5      >60% community votes up    <40% up

Risk flags (always shown, don't affect score):
  - Very low liquidity (<$50k): easy to manipulate
  - New pair (<7 days): higher rug pull risk
  - Sells >> Buys: possible dump in progress
  - Vol/Liq > 5: potential wash trading or pump
"""
from dataclasses import dataclass, field
from typing import Literal
import dex_data


@dataclass
class DexSignal:
    symbol: str
    name: str
    chain: str
    dex: str
    action: Literal["BUY", "SELL", "HOLD"]
    score: float
    price_usd: float
    liquidity_usd: float
    volume_24h: float
    vol_liq_ratio: float
    change_1h: float
    change_24h: float
    buy_pct: float
    risk_flags: list = field(default_factory=list)
    score_breakdown: dict = field(default_factory=dict)
    reason: str = ""
    url: str = ""


def analyze(query: str) -> DexSignal:
    """
    Fetch DEX data for a token and return a scored signal.

    Args:
        query: Token name or symbol (e.g. 'CREPE', 'PEPE', 'SHIB')

    Returns:
        DexSignal with action BUY/SELL/HOLD and full breakdown
    """
    # ── Fetch data ───────────────────────────────────────────────────────────
    pair = dex_data.get_best_pair(query)

    # Try CoinGecko for community sentiment
    cg_sentiment_up = 50.0  # default neutral
    try:
        cg_id = dex_data.find_coingecko_id(query)
        if cg_id:
            cg = dex_data.coingecko_price(cg_id)
            cg_sentiment_up = cg.get("sentiment_up", 50.0) or 50.0
    except Exception:
        pass

    # ── Score each signal ────────────────────────────────────────────────────

    # 1. 24h price momentum
    change_24h = pair["change_24h"]
    if change_24h > 10:
        momentum_score = 1.0
        momentum_reason = f"Strong 24h gain ({change_24h:+.1f}%)"
    elif change_24h > 5:
        momentum_score = 0.5
        momentum_reason = f"Moderate 24h gain ({change_24h:+.1f}%)"
    elif change_24h < -10:
        momentum_score = -1.0
        momentum_reason = f"Strong 24h decline ({change_24h:+.1f}%)"
    elif change_24h < -5:
        momentum_score = -0.5
        momentum_reason = f"Moderate 24h decline ({change_24h:+.1f}%)"
    else:
        momentum_score = 0.0
        momentum_reason = f"Flat 24h ({change_24h:+.1f}%)"

    # 2. 1h short-term momentum
    change_1h = pair["change_1h"]
    if change_1h > 2:
        short_score = 0.5
        short_reason = f"1h pumping ({change_1h:+.1f}%)"
    elif change_1h < -2:
        short_score = -0.5
        short_reason = f"1h dumping ({change_1h:+.1f}%)"
    else:
        short_score = 0.0
        short_reason = f"1h flat ({change_1h:+.1f}%)"

    # 3. Buy pressure (buys vs sells ratio)
    buy_pct = pair["buy_pct"]
    if buy_pct > 60:
        buy_score = 1.0
        buy_reason = f"High buy pressure ({buy_pct:.0f}% buys)"
    elif buy_pct > 50:
        buy_score = 0.5
        buy_reason = f"Slight buy pressure ({buy_pct:.0f}% buys)"
    elif buy_pct < 40:
        buy_score = -1.0
        buy_reason = f"Sell pressure ({buy_pct:.0f}% buys — {100-buy_pct:.0f}% sells)"
    elif buy_pct < 50:
        buy_score = -0.5
        buy_reason = f"Slight sell pressure ({buy_pct:.0f}% buys)"
    else:
        buy_score = 0.0
        buy_reason = f"Balanced buys/sells ({buy_pct:.0f}% buys)"

    # 4. Volume/Liquidity ratio
    vl = pair["vol_liq_ratio"]
    if vl > 0.3:
        vl_score = 0.5
        vl_reason = f"Active trading (Vol/Liq={vl:.2f})"
    elif vl < 0.05:
        vl_score = -0.5
        vl_reason = f"Very low activity (Vol/Liq={vl:.2f})"
    else:
        vl_score = 0.0
        vl_reason = f"Normal activity (Vol/Liq={vl:.2f})"

    # 5. Liquidity health
    liq = pair["liquidity_usd"]
    if liq > 500_000:
        liq_score = 0.5
        liq_reason = f"Strong liquidity (${liq:,.0f})"
    elif liq > 100_000:
        liq_score = 0.25
        liq_reason = f"Adequate liquidity (${liq:,.0f})"
    elif liq < 10_000:
        liq_score = -0.5
        liq_reason = f"Dangerously low liquidity (${liq:,.0f})"
    else:
        liq_score = 0.0
        liq_reason = f"Low liquidity (${liq:,.0f})"

    # 6. CoinGecko community sentiment
    if cg_sentiment_up > 60:
        sent_score = 0.5
        sent_reason = f"Community bullish ({cg_sentiment_up:.0f}% up votes)"
    elif cg_sentiment_up < 40:
        sent_score = -0.5
        sent_reason = f"Community bearish ({cg_sentiment_up:.0f}% up votes)"
    else:
        sent_score = 0.0
        sent_reason = f"Community neutral ({cg_sentiment_up:.0f}% up votes)"

    # ── Composite score ──────────────────────────────────────────────────────
    total = momentum_score + short_score + buy_score + vl_score + liq_score + sent_score

    if total >= 1.5:
        action = "BUY"
    elif total <= -1.5:
        action = "SELL"
    else:
        action = "HOLD"

    # ── Risk flags ───────────────────────────────────────────────────────────
    risk_flags = []
    if liq < 50_000:
        risk_flags.append(f"LOW LIQUIDITY (${liq:,.0f}) — price easily manipulated")
    if liq < 10_000:
        risk_flags.append("VERY LOW LIQUIDITY — possible rug pull risk")
    if vl > 5:
        risk_flags.append(f"EXTREME Vol/Liq ({vl:.1f}x) — possible pump & dump or wash trading")
    if buy_pct < 35:
        risk_flags.append(f"HEAVY SELLING ({100-buy_pct:.0f}% sells) — possible dump in progress")
    if pair["change_24h"] > 50:
        risk_flags.append(f"PARABOLIC PUMP (+{pair['change_24h']:.0f}% in 24h) — high reversal risk")
    if pair["change_24h"] < -30:
        risk_flags.append(f"HEAVY CRASH ({pair['change_24h']:.0f}% in 24h) — possible dead token")

    reason = " | ".join([momentum_reason, short_reason, buy_reason, liq_reason])

    return DexSignal(
        symbol=pair["symbol"],
        name=pair["name"],
        chain=pair["chain"],
        dex=pair["dex"],
        action=action,
        score=round(total, 2),
        price_usd=pair["price_usd"],
        liquidity_usd=liq,
        volume_24h=pair["volume_24h"],
        vol_liq_ratio=vl,
        change_1h=change_1h,
        change_24h=change_24h,
        buy_pct=buy_pct,
        risk_flags=risk_flags,
        reason=reason,
        url=pair["url"],
        score_breakdown={
            "momentum_24h": momentum_score,
            "momentum_1h":  short_score,
            "buy_pressure": buy_score,
            "vol_liq":      vl_score,
            "liquidity":    liq_score,
            "sentiment":    sent_score,
            "total":        round(total, 2),
        },
    )


def run(query: str):
    """Analyze a DEX token and print a full signal report."""
    print(f"\n{'='*60}")
    print(f"  DEX Signal Analysis — {query.upper()}")
    print(f"  Sources: DexScreener + CoinGecko")
    print(f"{'='*60}")

    sig = analyze(query)

    bar_len = 20
    bar_pos = int((sig.score + 4) / 8 * bar_len)
    bar     = "░" * bar_pos + "▓" + "░" * (bar_len - bar_pos)

    print(f"  Token:        {sig.symbol} ({sig.name})")
    print(f"  Chain/DEX:    {sig.chain} / {sig.dex}")
    print(f"  Price:        ${sig.price_usd:,.8g}")
    print(f"  Liquidity:    ${sig.liquidity_usd:,.0f}")
    print(f"  Volume 24h:   ${sig.volume_24h:,.0f}")
    print(f"  Vol/Liq:      {sig.vol_liq_ratio:.3f}")
    print(f"  Change 1h:    {sig.change_1h:+.2f}%")
    print(f"  Change 24h:   {sig.change_24h:+.2f}%")
    print(f"  Buy pressure: {sig.buy_pct:.0f}% buys")
    print(f"  Score:        {sig.score:+.2f}  [{bar}]")
    print(f"  ── Breakdown: "
          f"Momentum={sig.score_breakdown['momentum_24h']:+.1f} | "
          f"1h={sig.score_breakdown['momentum_1h']:+.1f} | "
          f"Buys={sig.score_breakdown['buy_pressure']:+.1f} | "
          f"Vol/Liq={sig.score_breakdown['vol_liq']:+.1f} | "
          f"Liq={sig.score_breakdown['liquidity']:+.1f} | "
          f"Sent={sig.score_breakdown['sentiment']:+.1f}")

    action_icon = "🟢" if sig.action == "BUY" else ("🔴" if sig.action == "SELL" else "⚪")
    print(f"\n  SIGNAL: {action_icon} {sig.action}")

    if sig.risk_flags:
        print(f"\n  ⚠ RISK FLAGS:")
        for flag in sig.risk_flags:
            print(f"    • {flag}")

    if sig.url:
        print(f"\n  Chart: {sig.url}")
    print(f"{'='*60}")

    return sig
