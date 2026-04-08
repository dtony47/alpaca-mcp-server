"""
polygon_data.py — Polygon.io integration for richer market data.

What Polygon adds over Alpaca free tier:
  - Real-time last trade & quote (SIP feed — all exchanges)
  - Options flow: unusual volume, open interest, put/call ratio
  - Institutional-grade OHLCV aggregates
  - Ticker details: market cap, shares outstanding, sector
  - Related news per ticker
  - Snapshot: full market overview in one call

Key concepts:
  - Put/Call Ratio:   High put volume = bearish bets. Low = bullish.
  - Open Interest:    Total open options contracts. Spikes = big money positioning.
  - Unusual Volume:   Options volume >> avg volume = whale activity signal.
  - Dark Pool:        Off-exchange institutional block trades (via trades endpoint).
"""
from datetime import datetime, timedelta, timezone
from tabulate import tabulate
import config
from net import get_json

BASE = "https://api.polygon.io"
KEY  = config.POLYGON_API_KEY


def _get(path: str, params: dict = None) -> dict:
    params = params or {}
    params["apiKey"] = KEY
    return get_json(f"{BASE}{path}", params=params, timeout=12, retries=3)


# ─── Quotes & Snapshots ─────────────────────────────────────────────────────

def get_snapshot(symbol: str) -> dict:
    """
    Full market snapshot for a ticker: price, change, volume, VWAP, today's range.
    VWAP (Volume Weighted Avg Price) is a key institutional benchmark.
    """
    data = _get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}")
    snap = data.get("ticker", {})
    day  = snap.get("day", {})
    prev = snap.get("prevDay", {})
    last = snap.get("lastTrade", {})

    return {
        "symbol":        symbol,
        "price":         last.get("p", 0),
        "open":          day.get("o", 0),
        "high":          day.get("h", 0),
        "low":           day.get("l", 0),
        "close":         day.get("c", 0),
        "volume":        day.get("v", 0),
        "vwap":          day.get("vw", 0),
        "prev_close":    prev.get("c", 0),
        "change_pct":    snap.get("todaysChangePerc", 0),
        "change_usd":    snap.get("todaysChange", 0),
    }


def get_ticker_details(symbol: str) -> dict:
    """Fundamental info: market cap, sector, exchange, description."""
    data = _get(f"/v3/reference/tickers/{symbol}")
    r = data.get("results", {})
    return {
        "symbol":      symbol,
        "name":        r.get("name"),
        "sector":      r.get("sic_description"),
        "market_cap":  r.get("market_cap"),
        "shares_out":  r.get("share_class_shares_outstanding"),
        "exchange":    r.get("primary_exchange"),
        "description": r.get("description", "")[:200],
    }


# ─── Options Flow (Whale Activity) ──────────────────────────────────────────

def get_options_flow(symbol: str, limit: int = 20) -> list:
    """
    Fetch recent options contracts for a ticker.
    Large volume relative to open interest = potential whale positioning.

    Returns list of dicts sorted by volume desc.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data  = _get("/v3/reference/options/contracts", {
        "underlying_ticker": symbol,
        "limit": limit,
        "order": "desc",
        "sort": "expiration_date",
    })
    contracts = data.get("results", [])
    return contracts


def get_options_snapshot(symbol: str) -> dict:
    """
    Get options chain snapshot with put/call ratio and unusual volume flags.

    Put/Call Ratio interpretation:
      < 0.7  → bullish (more calls being bought)
      0.7–1  → neutral
      > 1.0  → bearish (more puts being bought)
      > 1.5  → very bearish / possible hedge by whales
    """
    data = _get(f"/v3/snapshot/options/{symbol}", {"limit": 250})
    results = data.get("results", [])

    total_call_vol = 0
    total_put_vol  = 0
    unusual = []

    for r in results:
        details = r.get("details", {})
        greeks  = r.get("greeks", {})
        day     = r.get("day", {})
        vol     = day.get("volume", 0) or 0
        oi      = r.get("open_interest", 0) or 0

        contract_type = details.get("contract_type", "")
        if contract_type == "call":
            total_call_vol += vol
        elif contract_type == "put":
            total_put_vol += vol

        # Unusual = volume > 3x open interest (whale flag)
        if oi > 0 and vol > oi * 3:
            unusual.append({
                "ticker":    details.get("ticker"),
                "type":      contract_type,
                "strike":    details.get("strike_price"),
                "expiry":    details.get("expiration_date"),
                "volume":    vol,
                "oi":        oi,
                "vol_oi_ratio": round(vol / oi, 2) if oi else 0,
                "delta":     greeks.get("delta", 0),
            })

    pc_ratio = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else 0
    unusual.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)

    signal = "BULLISH" if pc_ratio < 0.7 else ("BEARISH" if pc_ratio > 1.0 else "NEUTRAL")

    return {
        "symbol":          symbol,
        "put_call_ratio":  pc_ratio,
        "call_volume":     total_call_vol,
        "put_volume":      total_put_vol,
        "options_signal":  signal,
        "unusual_trades":  unusual[:10],
    }


# ─── Large Trades (Dark Pool Proxy) ─────────────────────────────────────────

def get_large_trades(symbol: str, min_size: int = 10000) -> list:
    """
    Fetch recent large block trades — a proxy for dark pool / institutional activity.
    Trades >= min_size shares in a single transaction.

    Why it matters: institutions can't buy millions of shares at once without
    moving the price. They break orders up, but large prints still leak through.
    """
    now   = datetime.now(timezone.utc)
    start = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    data   = _get(f"/v3/trades/{symbol}", {"timestamp.gte": start, "limit": 50, "order": "desc"})
    trades = data.get("results", [])

    large = [t for t in trades if t.get("size", 0) >= min_size]
    large.sort(key=lambda x: x.get("size", 0), reverse=True)
    return large


# ─── News ────────────────────────────────────────────────────────────────────

def get_news(symbol: str, limit: int = 10) -> list:
    """Fetch recent news articles for a ticker from Polygon."""
    data = _get("/v2/reference/news", {"ticker": symbol, "limit": limit, "order": "desc"})
    return data.get("results", [])


# ─── Display helpers ─────────────────────────────────────────────────────────

def show_snapshot(symbol: str):
    s = get_snapshot(symbol)
    sign = "+" if s["change_pct"] >= 0 else ""
    rows = [
        ["Price",       f"${s['price']:,.4f}"],
        ["Change",      f"{sign}{s['change_pct']:.2f}%  ({sign}${s['change_usd']:.2f})"],
        ["VWAP",        f"${s['vwap']:,.2f}"],
        ["Open",        f"${s['open']:,.2f}"],
        ["High",        f"${s['high']:,.2f}"],
        ["Low",         f"${s['low']:,.2f}"],
        ["Volume",      f"{s['volume']:,.0f}"],
        ["Prev Close",  f"${s['prev_close']:,.2f}"],
    ]
    print(f"\n=== {symbol} Snapshot (Polygon) ===")
    print(tabulate(rows, headers=["Field", "Value"], tablefmt="rounded_outline"))


def show_options_flow(symbol: str):
    flow = get_options_snapshot(symbol)
    print(f"\n=== {symbol} Options Flow ===")
    rows = [
        ["Put/Call Ratio", flow["put_call_ratio"]],
        ["Call Volume",    f"{flow['call_volume']:,}"],
        ["Put Volume",     f"{flow['put_volume']:,}"],
        ["Signal",         flow["options_signal"]],
        ["Unusual Trades", len(flow["unusual_trades"])],
    ]
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="rounded_outline"))

    if flow["unusual_trades"]:
        print(f"\n  Unusual Options Activity (Vol/OI > 3x):")
        ut_rows = [[
            u["ticker"], u["type"].upper(), f"${u['strike']}", u["expiry"],
            f"{u['volume']:,}", f"{u['oi']:,}", u["vol_oi_ratio"]
        ] for u in flow["unusual_trades"]]
        print(tabulate(ut_rows,
            headers=["Contract", "Type", "Strike", "Expiry", "Volume", "OI", "Vol/OI"],
            tablefmt="rounded_outline"))
