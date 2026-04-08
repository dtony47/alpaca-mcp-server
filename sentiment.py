"""
sentiment.py — News sentiment scoring using Polygon news + keyword analysis.

How sentiment scoring works (free tier, no paid NLP API needed):
  - Fetch recent news headlines for a ticker
  - Score each headline using a weighted bullish/bearish keyword dictionary
  - Aggregate into a -1.0 (very bearish) to +1.0 (very bullish) score
  - Classify: BULLISH (>0.2), BEARISH (<-0.2), NEUTRAL

Why sentiment matters for trading:
  - News drives short-term price action even when technicals say otherwise
  - Strongly negative sentiment can invalidate a bullish MA crossover
  - Earnings surprises, analyst upgrades/downgrades = high-impact events

Free data sources used:
  - Polygon.io news API (included in free tier)
  - Alpaca news API (already connected)
"""
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Literal
import config
from net import get_json

# ─── Sentiment keyword dictionaries ─────────────────────────────────────────

BULLISH_KEYWORDS = {
    # Strong positive (weight 2)
    "beat": 2, "beats": 2, "record": 2, "surge": 2, "surges": 2,
    "breakout": 2, "upgrade": 2, "upgraded": 2, "buy rating": 2,
    "strong buy": 2, "outperform": 2, "raised target": 2, "blowout": 2,
    # Moderate positive (weight 1)
    "growth": 1, "profit": 1, "revenue": 1, "gain": 1, "gains": 1,
    "rally": 1, "bullish": 1, "positive": 1, "higher": 1, "up": 1,
    "rise": 1, "rises": 1, "rose": 1, "strong": 1, "expand": 1,
    "innovation": 1, "partnership": 1, "deal": 1, "contract": 1,
    "dividend": 1, "buyback": 1, "acquisition": 1, "launch": 1,
}

BEARISH_KEYWORDS = {
    # Strong negative (weight 2)
    "miss": 2, "missed": 2, "downgrade": 2, "downgraded": 2, "sell rating": 2,
    "underperform": 2, "crash": 2, "collapsed": 2, "bankruptcy": 2,
    "fraud": 2, "investigation": 2, "lawsuit": 2, "recall": 2,
    # Moderate negative (weight 1)
    "loss": 1, "losses": 1, "decline": 1, "declines": 1, "fell": 1,
    "fall": 1, "drop": 1, "drops": 1, "weak": 1, "bearish": 1,
    "concern": 1, "warning": 1, "risk": 1, "debt": 1, "cut": 1,
    "layoff": 1, "layoffs": 1, "charges": 1, "writedown": 1, "slump": 1,
}


@dataclass
class SentimentResult:
    symbol: str
    score: float                          # -1.0 to +1.0
    label: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float                     # 0.0 to 1.0 (how many articles had signal)
    article_count: int
    top_headlines: list = field(default_factory=list)
    summary: str = ""


def _score_headline(text: str) -> float:
    """Score a single headline. Returns positive (bullish) or negative (bearish) float."""
    text_lower = text.lower()
    score = 0.0

    for word, weight in BULLISH_KEYWORDS.items():
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            score += weight

    for word, weight in BEARISH_KEYWORDS.items():
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            score -= weight

    return score


def _fetch_polygon_news(symbol: str, limit: int = 20) -> list:
    """Fetch news from Polygon.io free tier."""
    try:
        data = get_json(
            "https://api.polygon.io/v2/reference/news",
            params={"ticker": symbol, "limit": limit, "order": "desc", "apiKey": config.POLYGON_API_KEY},
            timeout=12,
            retries=2,
        )
        return data.get("results", [])
    except Exception as e:
        print(f"[sentiment] Polygon news error: {e}")
        return []


def _fetch_alpaca_news(symbol: str, limit: int = 10) -> list:
    """Fetch news from Alpaca's free news API."""
    try:
        data = get_json(
            "https://data.alpaca.markets/v1beta1/news",
            params={"symbols": symbol, "limit": limit, "sort": "desc"},
            headers={
                "APCA-API-KEY-ID": config.API_KEY,
                "APCA-API-SECRET-KEY": config.API_SECRET,
            },
            timeout=12,
            retries=2,
        )
        raw = data.get("news", [])
        # Normalise to same shape as Polygon news
        return [{"title": a.get("headline", ""), "published_utc": a.get("created_at", "")} for a in raw]
    except Exception as e:
        print(f"[sentiment] Alpaca news error: {e}")
        return []


def analyze(symbol: str, lookback_hours: int = 48) -> SentimentResult:
    """
    Fetch recent news and compute a sentiment score for a ticker.

    Args:
        symbol:          Ticker (e.g. 'AAPL')
        lookback_hours:  Only consider news from the last N hours

    Returns:
        SentimentResult with score, label, confidence, and top headlines
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    # Pull from both sources and deduplicate by title
    polygon_articles = _fetch_polygon_news(symbol, limit=20)
    alpaca_articles  = _fetch_alpaca_news(symbol, limit=10)
    all_articles     = polygon_articles + alpaca_articles

    seen_titles = set()
    articles = []
    for a in all_articles:
        title = a.get("title") or a.get("headline", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            articles.append({"title": title, "published_utc": a.get("published_utc", "")})

    if not articles:
        return SentimentResult(
            symbol=symbol, score=0.0, label="NEUTRAL",
            confidence=0.0, article_count=0,
            summary="No recent news found."
        )

    scores = []
    top_headlines = []

    for a in articles:
        title = a.get("title", "")
        s = _score_headline(title)
        scores.append(s)
        top_headlines.append({"headline": title, "score": s})

    # Sort headlines by abs(score) so most impactful are first
    top_headlines.sort(key=lambda x: abs(x["score"]), reverse=True)

    # Normalise aggregate score to -1..+1
    raw_total = sum(scores)
    max_possible = sum(abs(s) for s in scores) or 1
    normalised = max(-1.0, min(1.0, raw_total / max_possible))

    # Confidence = proportion of articles that had any signal
    with_signal = sum(1 for s in scores if s != 0)
    confidence = round(with_signal / len(scores), 2)

    if normalised > 0.2:
        label = "BULLISH"
    elif normalised < -0.2:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    summary = f"{len(articles)} articles | score {normalised:+.2f} | {label}"

    return SentimentResult(
        symbol=symbol,
        score=round(normalised, 3),
        label=label,
        confidence=confidence,
        article_count=len(articles),
        top_headlines=top_headlines[:5],
        summary=summary,
    )


def show(symbol: str):
    """Print a formatted sentiment report for a ticker."""
    from tabulate import tabulate
    result = analyze(symbol)

    bar_len = 20
    filled  = int((result.score + 1) / 2 * bar_len)
    bar     = "█" * filled + "░" * (bar_len - filled)

    print(f"\n=== {symbol} Sentiment ({result.article_count} articles) ===")
    rows = [
        ["Score",      f"{result.score:+.3f}  [{bar}]"],
        ["Signal",     result.label],
        ["Confidence", f"{result.confidence*100:.0f}%"],
    ]
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="rounded_outline"))

    if result.top_headlines:
        print("\n  Top headlines:")
        for h in result.top_headlines:
            sign = "↑" if h["score"] > 0 else ("↓" if h["score"] < 0 else "→")
            score_str = f"{h['score']:+.0f}"
            print(f"  {sign} [{score_str:>3}]  {h['headline'][:90]}")
