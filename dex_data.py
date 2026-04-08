"""
dex_data.py — DEX/Web3 token data via DexScreener & CoinGecko (both free, no API key needed).

Why DEX data is different from stocks:
  - No central exchange — price is set by liquidity pools (AMMs like Uniswap/PancakeSwap)
  - Liquidity matters: low liquidity = price can be moved by small trades (slippage)
  - Volume/Liquidity ratio: >1 = high turnover (hot token); <0.1 = low interest
  - Whale wallets: large holders can dump and crash price instantly

Key metrics for DEX tokens:
  - Price USD:       Current price in the liquidity pool
  - Liquidity USD:   Total value locked in the trading pair (higher = safer/more stable)
  - Volume 24h:      Trading volume in last 24 hours
  - Vol/Liq ratio:   Volume ÷ Liquidity. >0.5 = very active. <0.05 = dead token
  - Price change:    % change over 5m / 1h / 6h / 24h
  - Txns 24h:        Number of buys vs sells (buy pressure indicator)
  - FDV:             Fully diluted valuation (market cap if all tokens were in circulation)
"""
from tabulate import tabulate
from net import get_json

DEXSCREENER_BASE = "https://api.dexscreener.com"
COINGECKO_BASE   = "https://api.coingecko.com/api/v3"


# ─── DexScreener ─────────────────────────────────────────────────────────────

def search_token(query: str) -> list:
    """
    Search DexScreener for a token by name or symbol.
    Returns list of matching pairs sorted by liquidity (most liquid first).
    """
    data = get_json(f"{DEXSCREENER_BASE}/latest/dex/search", params={"q": query}, timeout=12, retries=3)
    pairs = data.get("pairs") or []
    if not pairs:
        return []
    # Sort by liquidity descending so we get the most credible pair first
    pairs.sort(key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
    return pairs


def get_token_pairs(token_address: str) -> list:
    """Fetch all trading pairs for a specific contract address."""
    data = get_json(f"{DEXSCREENER_BASE}/latest/dex/tokens/{token_address}", timeout=12, retries=3)
    return data.get("pairs") or []


def parse_pair(pair: dict) -> dict:
    """Normalise a DexScreener pair object into a clean dict."""
    price_change = pair.get("priceChange", {})
    txns         = pair.get("txns", {}).get("h24", {})
    liquidity    = pair.get("liquidity", {})
    volume       = pair.get("volume", {})
    info         = pair.get("info", {})

    liq_usd = float(liquidity.get("usd", 0) or 0)
    vol_24h = float(volume.get("h24", 0) or 0)
    vol_liq = round(vol_24h / liq_usd, 4) if liq_usd > 0 else 0

    buys  = txns.get("buys", 0) or 0
    sells = txns.get("sells", 0) or 0
    total_txns = buys + sells
    buy_pct = round(buys / total_txns * 100, 1) if total_txns > 0 else 0

    return {
        "symbol":        pair.get("baseToken", {}).get("symbol", "?"),
        "name":          pair.get("baseToken", {}).get("name", "?"),
        "address":       pair.get("baseToken", {}).get("address", ""),
        "chain":         pair.get("chainId", ""),
        "dex":           pair.get("dexId", ""),
        "pair_address":  pair.get("pairAddress", ""),
        "price_usd":     float(pair.get("priceUsd", 0) or 0),
        "price_native":  float(pair.get("priceNative", 0) or 0),
        "liquidity_usd": liq_usd,
        "volume_24h":    vol_24h,
        "vol_liq_ratio": vol_liq,
        "fdv":           float(pair.get("fdv", 0) or 0),
        "market_cap":    float(pair.get("marketCap", 0) or 0),
        "change_5m":     float(price_change.get("m5", 0) or 0),
        "change_1h":     float(price_change.get("h1", 0) or 0),
        "change_6h":     float(price_change.get("h6", 0) or 0),
        "change_24h":    float(price_change.get("h24", 0) or 0),
        "buys_24h":      buys,
        "sells_24h":     sells,
        "buy_pct":       buy_pct,
        "created_at":    pair.get("pairCreatedAt"),
        "url":           pair.get("url", ""),
    }


def get_best_pair(query: str) -> dict:
    """
    Find the highest-liquidity pair for a token name/symbol.
    Raises ValueError if not found.
    """
    pairs = search_token(query)
    if not pairs:
        raise ValueError(f"No DEX pairs found for '{query}'")
    return parse_pair(pairs[0])


def get_recent_trades(pair_address: str, chain: str = "ethereum", limit: int = 20) -> list:
    """
    Fetch recent trades for a DEX pair (whale trade detection).
    Large trades = potential whale activity.
    """
    data = get_json(
        f"{DEXSCREENER_BASE}/latest/dex/pairs/{chain}/{pair_address}",
        timeout=12,
        retries=3,
    )
    pairs = data.get("pairs") or []
    return pairs[0] if pairs else {}


# ─── CoinGecko ───────────────────────────────────────────────────────────────

def coingecko_search(query: str) -> list:
    """Search CoinGecko for a token by name or symbol."""
    data = get_json(f"{COINGECKO_BASE}/search", params={"query": query}, timeout=15, retries=3)
    return data.get("coins", [])[:5]


def coingecko_price(coin_id: str) -> dict:
    """
    Fetch detailed price data from CoinGecko by coin ID.
    More reliable for market cap and circulating supply.
    """
    data = get_json(
        f"{COINGECKO_BASE}/coins/{coin_id}",
        params={
            "localization": "false",
            "tickers": "false",
            "community_data": "true",
            "developer_data": "false",
        },
        timeout=20,
        retries=3,
    )
    market = data.get("market_data", {})

    return {
        "id":              data.get("id"),
        "symbol":          data.get("symbol", "").upper(),
        "name":            data.get("name"),
        "price_usd":       market.get("current_price", {}).get("usd", 0),
        "market_cap":      market.get("market_cap", {}).get("usd", 0),
        "volume_24h":      market.get("total_volume", {}).get("usd", 0),
        "change_24h":      market.get("price_change_percentage_24h", 0),
        "change_7d":       market.get("price_change_percentage_7d", 0),
        "change_30d":      market.get("price_change_percentage_30d", 0),
        "ath":             market.get("ath", {}).get("usd", 0),
        "ath_change_pct":  market.get("ath_change_percentage", {}).get("usd", 0),
        "circulating":     market.get("circulating_supply", 0),
        "total_supply":    market.get("total_supply", 0),
        "description":     data.get("description", {}).get("en", "")[:300],
        "twitter":         data.get("links", {}).get("twitter_screen_name", ""),
        "telegram":        data.get("links", {}).get("telegram_channel_identifier", ""),
        "homepage":        (data.get("links", {}).get("homepage") or [""])[0],
        "sentiment_up":    data.get("sentiment_votes_up_percentage", 0),
        "sentiment_down":  data.get("sentiment_votes_down_percentage", 0),
    }


def find_coingecko_id(symbol: str):
    """Find the CoinGecko coin ID for a symbol/name."""
    results = coingecko_search(symbol)
    if not results:
        return None
    # Prefer exact symbol match
    sym_upper = symbol.upper()
    for coin in results:
        if coin.get("symbol", "").upper() == sym_upper:
            return coin["id"]
    return results[0]["id"]


# ─── Display ─────────────────────────────────────────────────────────────────

def show_token(query: str):
    """Full display: DexScreener pair data + CoinGecko fundamentals."""
    print(f"\nSearching for '{query}'...")

    # DexScreener
    try:
        pair = get_best_pair(query)
        _show_pair(pair)
    except Exception as e:
        print(f"  DexScreener: {e}")
        pair = None

    # CoinGecko
    try:
        cg_id = find_coingecko_id(query)
        if cg_id:
            cg = coingecko_price(cg_id)
            _show_coingecko(cg)
    except Exception as e:
        print(f"  CoinGecko: {e}")


def _show_pair(p: dict):
    liq_warning = " ⚠ LOW LIQUIDITY" if p["liquidity_usd"] < 50_000 else ""
    rows = [
        ["Symbol",          f"{p['symbol']} ({p['name']})"],
        ["Chain / DEX",     f"{p['chain']} / {p['dex']}"],
        ["Price",           f"${p['price_usd']:,.8g}"],
        ["Liquidity",       f"${p['liquidity_usd']:,.0f}{liq_warning}"],
        ["Volume 24h",      f"${p['volume_24h']:,.0f}"],
        ["Vol/Liq Ratio",   f"{p['vol_liq_ratio']:.3f}  {'🔥' if p['vol_liq_ratio'] > 0.5 else ''}"],
        ["Change 5m",       f"{p['change_5m']:+.2f}%"],
        ["Change 1h",       f"{p['change_1h']:+.2f}%"],
        ["Change 6h",       f"{p['change_6h']:+.2f}%"],
        ["Change 24h",      f"{p['change_24h']:+.2f}%"],
        ["Buys / Sells 24h",f"{p['buys_24h']} / {p['sells_24h']}  ({p['buy_pct']}% buys)"],
        ["FDV",             f"${p['fdv']:,.0f}" if p['fdv'] else "N/A"],
        ["DexScreener",     p['url']],
    ]
    print(f"\n=== DEX Data (DexScreener) ===")
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="rounded_outline"))


def _show_coingecko(cg: dict):
    rows = [
        ["Market Cap",      f"${cg['market_cap']:,.0f}" if cg['market_cap'] else "N/A"],
        ["Volume 24h",      f"${cg['volume_24h']:,.0f}" if cg['volume_24h'] else "N/A"],
        ["Change 24h",      f"{cg['change_24h']:+.2f}%" if cg['change_24h'] else "N/A"],
        ["Change 7d",       f"{cg['change_7d']:+.2f}%" if cg['change_7d'] else "N/A"],
        ["Change 30d",      f"{cg['change_30d']:+.2f}%" if cg['change_30d'] else "N/A"],
        ["ATH",             f"${cg['ath']:,.6g}  ({cg['ath_change_pct']:+.1f}% from ATH)" if cg['ath'] else "N/A"],
        ["Supply",          f"{cg['circulating']:,.0f} / {cg['total_supply']:,.0f}" if cg['circulating'] else "N/A"],
        ["Community Sentiment", f"↑{cg['sentiment_up']:.0f}%  ↓{cg['sentiment_down']:.0f}%"],
    ]
    if cg.get("twitter"):
        rows.append(["Twitter", f"@{cg['twitter']}"])
    if cg.get("telegram"):
        rows.append(["Telegram", cg['telegram']])

    print(f"\n=== CoinGecko Fundamentals ===")
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="rounded_outline"))
    if cg.get("description"):
        print(f"\n  About: {cg['description'][:200]}...")
