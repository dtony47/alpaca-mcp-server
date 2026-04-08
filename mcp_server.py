#!/opt/homebrew/bin/python3.14
"""
mcp_server.py — Custom MCP server exposing all market data tools to Claude.

This makes Claude natively aware of your market data in ANY conversation,
not just when running scripts.

Setup:
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  cp .env.example .env   # fill in your API keys
  .venv/bin/python mcp_server.py

Then add to your MCP config (Claude Code, Openclaw, etc.):
  {
    "mcpServers": {
      "alpaca-market": {
        "command": "/path/to/repo/.venv/bin/python",
        "args": ["/path/to/repo/mcp_server.py"],
        "cwd": "/path/to/repo"
      }
    }
  }

Available tools exposed to Claude:
  - get_quote          : Real-time quote for any stock or crypto
  - get_snapshot       : Full Polygon snapshot (price, VWAP, change, volume)
  - get_sentiment      : News sentiment score for a ticker
  - get_options_flow   : Put/call ratio + unusual whale activity
  - get_large_trades   : Recent block trades (dark pool proxy)
  - get_account        : Your paper account balance & buying power
  - get_positions      : Open positions with P&L
  - run_strategy       : Run MA crossover + sentiment analysis on any ticker
  - scan_watchlist     : Scan multiple tickers and return signals table
  - get_dex_token      : Full DEX data for any Web3/DeFi token (DexScreener + CoinGecko)
  - run_dex_strategy   : Signal analysis for a DEX token (buy/sell/hold + risk flags)
  - search_dex_token   : Search for a token and return top pairs by liquidity
"""
import sys
import os
import json

# Ensure the Alpaca project directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env before importing project modules
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from mcp.server.fastmcp import FastMCP
import config
import polygon_data
import sentiment as sentiment_mod
import market_data
import strategy as strategy_mod
import dex_data
import dex_strategy
import trader
import policy
import audit_log
import backtest
import execution_store
import strategy_library
from account import get_client

mcp = FastMCP("alpaca-market")

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTC/USD", "ETH/USD"]

_EXEC_POLICY = policy.load_policy()
execution_store.init_db()


def _ok(data):
    return json.dumps({"ok": True, "data": data})


def _err(message: str, *, data=None):
    payload = {"ok": False, "error": message}
    if data is not None:
        payload["data"] = data
    return json.dumps(payload)


# ─── Market Data Tools ───────────────────────────────────────────────────────

@mcp.tool()
def get_quote(symbol: str) -> str:
    """
    Get real-time bid/ask quote for a stock or crypto ticker.
    Use for: BTC/USD, AAPL, TSLA, ETH/USD, etc.
    """
    try:
        q = market_data.get_quote(symbol)
        return _ok(q)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_snapshot(symbol: str) -> str:
    """
    Get full Polygon.io market snapshot for a stock ticker.
    Includes: price, open, high, low, volume, VWAP, % change vs yesterday.
    Note: stocks only (not crypto).
    """
    try:
        s = polygon_data.get_snapshot(symbol)
        return _ok(s)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_sentiment(symbol: str, lookback_hours: int = 48) -> str:
    """
    Analyse recent news sentiment for a ticker.
    Returns: score (-1 bearish to +1 bullish), label, confidence, top headlines.
    """
    try:
        result = sentiment_mod.analyze(symbol, lookback_hours)
        return _ok({
            "symbol":        result.symbol,
            "score":         result.score,
            "label":         result.label,
            "confidence":    result.confidence,
            "article_count": result.article_count,
            "summary":       result.summary,
            "top_headlines": result.top_headlines,
        })
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_options_flow(symbol: str) -> str:
    """
    Get options market data for a stock: put/call ratio, call/put volume,
    and any unusual options activity that may indicate whale positioning.
    Put/call > 1.0 = bearish bets. < 0.7 = bullish.
    Note: stocks only.
    """
    try:
        flow = polygon_data.get_options_snapshot(symbol)
        return _ok(flow)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_large_trades(symbol: str, min_size: int = 10000) -> str:
    """
    Fetch recent large block trades for a stock (dark pool proxy).
    Trades >= min_size shares. Large institutional prints can signal direction.
    """
    try:
        trades = polygon_data.get_large_trades(symbol, min_size)
        return _ok(trades[:20])
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_ticker_details(symbol: str) -> str:
    """
    Get fundamental details for a stock: company name, sector, market cap,
    shares outstanding, exchange.
    """
    try:
        details = polygon_data.get_ticker_details(symbol)
        return _ok(details)
    except Exception as e:
        return _err(str(e))


# ─── Account Tools ───────────────────────────────────────────────────────────

@mcp.tool()
def get_account() -> str:
    """
    Get your Alpaca paper trading account summary:
    equity, cash, buying power, portfolio value.
    """
    try:
        client = get_client()
        acct = client.get_account()
        return _ok({
            "equity":        float(acct.equity),
            "cash":          float(acct.cash),
            "buying_power":  float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value),
            "status":        str(acct.status),
        })
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_positions() -> str:
    """
    Get all open positions in your paper trading account with P&L.
    """
    try:
        client = get_client()
        positions = client.get_all_positions()
        result = [{
            "symbol":          p.symbol,
            "qty":             str(p.qty),
            "avg_entry":       float(p.avg_entry_price),
            "current_price":   float(p.current_price),
            "market_value":    float(p.market_value),
            "unrealized_pl":   float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
        } for p in positions]
        return _ok(result)
    except Exception as e:
        return _err(str(e))


# ─── Strategy Tools ──────────────────────────────────────────────────────────

@mcp.tool()
def run_strategy(symbol: str, short_period: int = 20, long_period: int = 50) -> str:
    """
    Run the full combined analysis on a symbol:
    - MA crossover signal (trend direction)
    - RSI level (overbought/oversold)
    - News sentiment score
    Returns a combined BUY / SELL / HOLD recommendation with reasoning.
    """
    try:
        sig = strategy_mod.analyze(symbol, short_period, long_period)
        sent = sentiment_mod.analyze(symbol)
        return _ok({
            "symbol":        sig.symbol,
            "ma_signal":     sig.action,
            "ma_reason":     sig.reason,
            "short_ma":      sig.short_ma,
            "long_ma":       sig.long_ma,
            "price":         sig.current_price,
            "rsi":           sig.rsi,
            "sentiment":     sent.label,
            "sentiment_score": sent.score,
            "sentiment_summary": sent.summary,
        })
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def scan_watchlist(symbols: list = None) -> str:
    """
    Scan a list of symbols (default watchlist if none provided) and return
    MA crossover signals + sentiment for each. Good for morning market overview.
    """
    tickers = symbols or DEFAULT_WATCHLIST
    results = []
    for sym in tickers:
        try:
            sig  = strategy_mod.analyze(sym)
            sent = sentiment_mod.analyze(sym)
            results.append({
                "symbol":    sym,
                "price":     sig.current_price,
                "signal":    sig.action,
                "rsi":       sig.rsi,
                "sentiment": sent.label,
                "score":     sent.score,
            })
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)})
    return _ok(results)


# ─── DEX / Web3 Tools ────────────────────────────────────────────────────────

@mcp.tool()
def search_dex_token(query: str) -> str:
    """
    Search for a DEX/Web3 token by name or symbol across all chains.
    Returns top pairs sorted by liquidity. Use this to discover the contract
    address and chain for a token before running analysis.
    Examples: 'CREPE', 'PEPE', 'SHIB', 'bonk'
    """
    try:
        pairs = dex_data.search_token(query)
        if not pairs:
            return _err(f"No DEX pairs found for '{query}'")
        results = [dex_data.parse_pair(p) for p in pairs[:5]]
        return _ok(results)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_dex_token(query: str) -> str:
    """
    Get full market data for a DEX/Web3 token: price, liquidity, volume,
    buy/sell pressure, price changes (5m/1h/6h/24h), and CoinGecko fundamentals.
    Works for any token on any chain (Ethereum, BSC, Solana, Base, etc.)
    Examples: 'CREPE', 'PEPE', 'WIF', 'BONK'
    """
    try:
        pair = dex_data.get_best_pair(query)
        # Also try CoinGecko
        cg_data = None
        try:
            cg_id = dex_data.find_coingecko_id(query)
            if cg_id:
                cg_data = dex_data.coingecko_price(cg_id)
        except Exception:
            pass
        return _ok({"dex": pair, "coingecko": cg_data})
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def run_dex_strategy(query: str) -> str:
    """
    Run full signal analysis on a DEX/Web3 token.
    Returns BUY/SELL/HOLD signal with score breakdown and risk flags.

    Scoring factors: price momentum, buy/sell pressure, liquidity health,
    volume/liquidity ratio, community sentiment.

    Risk flags highlight: low liquidity, dump activity, pump & dump patterns.
    Examples: 'CREPE', 'PEPE', 'DOGE', 'FLOKI'
    """
    try:
        sig = dex_strategy.analyze(query)
        return _ok({
            "symbol":        sig.symbol,
            "name":          sig.name,
            "chain":         sig.chain,
            "dex":           sig.dex,
            "action":        sig.action,
            "score":         sig.score,
            "price_usd":     sig.price_usd,
            "liquidity_usd": sig.liquidity_usd,
            "volume_24h":    sig.volume_24h,
            "vol_liq_ratio": sig.vol_liq_ratio,
            "change_1h":     sig.change_1h,
            "change_24h":    sig.change_24h,
            "buy_pct":       sig.buy_pct,
            "risk_flags":    sig.risk_flags,
            "score_breakdown": sig.score_breakdown,
            "reason":        sig.reason,
            "url":           sig.url,
        })
    except Exception as e:
        return _err(str(e))


# ─── Execution Tools (guarded) ───────────────────────────────────────────────

@mcp.tool()
def get_execution_policy() -> str:
    """Return the currently loaded execution policy (for transparency)."""
    p = _EXEC_POLICY
    return _ok({
        "enabled": p.enabled,
        "mode": p.mode,
        "allowed_symbols": p.allowed_symbols,
        "allowed_asset_classes": p.allowed_asset_classes,
        "max_notional_usd": p.max_notional_usd,
        "max_trades_per_day": p.max_trades_per_day,
        "min_seconds_between_trades": p.min_seconds_between_trades,
        "require_live_token": p.require_live_token,
        "live_token_configured": bool(p.live_token),
    })


def _enforce_rate_limits(tool: str) -> None:
    # daily limit applies to successful *live* executions only
    if _EXEC_POLICY.max_trades_per_day:
        used = execution_store.count_today(tool, live_only=True)
        if used >= _EXEC_POLICY.max_trades_per_day:
            raise ValueError(f"Daily live trade limit reached for {tool} ({used}/{_EXEC_POLICY.max_trades_per_day})")

    if _EXEC_POLICY.min_seconds_between_trades:
        last_ts = execution_store.last_live_ts(tool)
        if last_ts:
            import time

            since = time.time() - last_ts
            if since < _EXEC_POLICY.min_seconds_between_trades:
                wait = int(_EXEC_POLICY.min_seconds_between_trades - since)
                raise ValueError(f"Cooldown active for {tool}; wait ~{wait}s before next live trade")


@mcp.tool()
def place_order(
    symbol: str,
    side: str,
    notional_usd: float,
    live: bool = False,
    live_token: str | None = None,
    idempotency_key: str | None = None,
) -> str:
    """
    Place a market order through Alpaca (paper account).

    Safety:
      - Defaults to dry-run (live=false).
      - Requires LLM_TRADING_ENABLED=true.
      - Enforces allowlists and notional caps from policy.
      - If live=true and LLM_REQUIRE_LIVE_TOKEN=true, requires live_token match.
    """
    payload = {
        "symbol": symbol,
        "side": side,
        "notional_usd": notional_usd,
        "live": live,
        "idempotency_key": idempotency_key,
    }
    try:
        if not _EXEC_POLICY.enabled:
            raise ValueError("Execution disabled (set LLM_TRADING_ENABLED=true to allow)")

        asset_class = policy.classify_symbol(symbol)
        _EXEC_POLICY.check_asset_class(symbol, asset_class)
        _EXEC_POLICY.check_symbol(symbol)
        _EXEC_POLICY.check_notional(float(notional_usd))

        dry_run = not bool(live)
        if live:
            if execution_store.already_processed(idempotency_key):
                raise ValueError("Duplicate idempotency_key (already processed)")
            _EXEC_POLICY.check_live_token(live_token)
            if _EXEC_POLICY.mode != "paper":
                raise ValueError("Live mode is blocked by policy (LLM_TRADING_MODE must be 'paper')")
            _enforce_rate_limits("place_order")

        side_norm = (side or "").strip().lower()
        if side_norm not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")

        import time

        rec = execution_store.ExecutionRecord(
            ts=time.time(),
            tool="place_order",
            symbol=symbol,
            side=side_norm,
            notional_usd=float(notional_usd),
            live=bool(live),
            dry_run=dry_run,
            idempotency_key=idempotency_key,
        )

        if side_norm == "buy":
            result = trader.buy(symbol, notional=float(notional_usd), dry_run=dry_run)
        else:
            result = trader.sell(symbol, notional=float(notional_usd), dry_run=dry_run)

        audit_log.append("place_order", payload, ok=True, error=None)
        out = {"submitted": not dry_run, "result": result, "dry_run": dry_run}
        execution_store.insert_result(rec, ok=True, error=None, result=out)
        return _ok(out)
    except Exception as e:
        audit_log.append("place_order", payload, ok=False, error=str(e))
        try:
            import time

            rec = execution_store.ExecutionRecord(
                ts=time.time(),
                tool="place_order",
                symbol=symbol,
                side=(side or "").strip().lower() or None,
                notional_usd=float(notional_usd) if notional_usd is not None else None,
                live=bool(live),
                dry_run=True,
                idempotency_key=idempotency_key,
            )
            execution_store.insert_result(rec, ok=False, error=str(e), result=None)
        except Exception:
            pass
        return _err(str(e), data={"dry_run": True})


@mcp.tool()
def close_position(symbol: str, live: bool = False, live_token: str | None = None, idempotency_key: str | None = None) -> str:
    """
    Close an entire open position for a symbol.
    Defaults to dry-run unless live=true, and still enforces the execution policy.
    """
    payload = {"symbol": symbol, "live": live, "idempotency_key": idempotency_key}
    try:
        if not _EXEC_POLICY.enabled:
            raise ValueError("Execution disabled (set LLM_TRADING_ENABLED=true to allow)")

        asset_class = policy.classify_symbol(symbol)
        _EXEC_POLICY.check_asset_class(symbol, asset_class)
        _EXEC_POLICY.check_symbol(symbol)

        dry_run = not bool(live)
        if live:
            if execution_store.already_processed(idempotency_key):
                raise ValueError("Duplicate idempotency_key (already processed)")
            _EXEC_POLICY.check_live_token(live_token)
            if _EXEC_POLICY.mode != "paper":
                raise ValueError("Live mode is blocked by policy (LLM_TRADING_MODE must be 'paper')")
            _enforce_rate_limits("close_position")

        import time

        rec = execution_store.ExecutionRecord(
            ts=time.time(),
            tool="close_position",
            symbol=symbol,
            side="sell",
            notional_usd=None,
            live=bool(live),
            dry_run=dry_run,
            idempotency_key=idempotency_key,
        )

        result = trader.close_position(symbol, dry_run=dry_run)
        audit_log.append("close_position", payload, ok=True, error=None)
        out = {"submitted": not dry_run, "result": result, "dry_run": dry_run}
        execution_store.insert_result(rec, ok=True, error=None, result=out)
        return _ok(out)
    except Exception as e:
        audit_log.append("close_position", payload, ok=False, error=str(e))
        try:
            import time

            rec = execution_store.ExecutionRecord(
                ts=time.time(),
                tool="close_position",
                symbol=symbol,
                side="sell",
                notional_usd=None,
                live=bool(live),
                dry_run=True,
                idempotency_key=idempotency_key,
            )
            execution_store.insert_result(rec, ok=False, error=str(e), result=None)
        except Exception:
            pass
        return _err(str(e), data={"dry_run": True})


@mcp.tool()
def close_all_positions(live: bool = False, live_token: str | None = None, idempotency_key: str | None = None) -> str:
    """
    Close ALL open positions (paper account).
    Defaults to dry-run unless live=true, and still enforces the execution policy.
    """
    payload = {"live": live, "idempotency_key": idempotency_key}
    try:
        if not _EXEC_POLICY.enabled:
            raise ValueError("Execution disabled (set LLM_TRADING_ENABLED=true to allow)")

        dry_run = not bool(live)
        if live:
            if execution_store.already_processed(idempotency_key):
                raise ValueError("Duplicate idempotency_key (already processed)")
            _EXEC_POLICY.check_live_token(live_token)
            if _EXEC_POLICY.mode != "paper":
                raise ValueError("Live mode is blocked by policy (LLM_TRADING_MODE must be 'paper')")
            _enforce_rate_limits("close_all_positions")

        import time

        rec = execution_store.ExecutionRecord(
            ts=time.time(),
            tool="close_all_positions",
            symbol=None,
            side="sell",
            notional_usd=None,
            live=bool(live),
            dry_run=dry_run,
            idempotency_key=idempotency_key,
        )

        trader.close_all_positions(dry_run=dry_run)
        audit_log.append("close_all_positions", payload, ok=True, error=None)
        out = {"submitted": not dry_run, "dry_run": dry_run}
        execution_store.insert_result(rec, ok=True, error=None, result=out)
        return _ok(out)
    except Exception as e:
        audit_log.append("close_all_positions", payload, ok=False, error=str(e))
        try:
            import time

            rec = execution_store.ExecutionRecord(
                ts=time.time(),
                tool="close_all_positions",
                symbol=None,
                side="sell",
                notional_usd=None,
                live=bool(live),
                dry_run=True,
                idempotency_key=idempotency_key,
            )
            execution_store.insert_result(rec, ok=False, error=str(e), result=None)
        except Exception:
            pass
        return _err(str(e), data={"dry_run": True})


@mcp.tool()
def decide_and_trade(symbol: str, notional_usd: float, live: bool = False, live_token: str | None = None, idempotency_key: str | None = None) -> str:
    """
    High-level orchestration tool:
      - runs combined strategy analysis
      - if BUY/SELL and permitted, places the corresponding order
      - enforces all execution policy checks, idempotency, daily limits, cooldowns

    Defaults to dry-run unless live=true.
    """
    payload = {"symbol": symbol, "notional_usd": notional_usd, "live": live, "idempotency_key": idempotency_key}
    try:
        sig = strategy_mod.analyze(symbol)

        action = sig.action
        decision = {
            "symbol": sig.symbol,
            "action": action,
            "score": sig.score,
            "reason": sig.reason,
            "price": sig.current_price,
            "rsi": sig.rsi,
            "short_ma": sig.short_ma,
            "long_ma": sig.long_ma,
            "sentiment_label": sig.sentiment_label,
            "sentiment_score": sig.sentiment_score,
            "options_signal": sig.options_signal,
            "put_call_ratio": sig.put_call_ratio,
            "score_breakdown": sig.score_breakdown,
        }

        if action == "HOLD":
            return _ok({"decision": decision, "executed": False, "dry_run": True})

        # reuse guarded execution path
        if action == "BUY":
            resp = json.loads(place_order(symbol, "buy", float(notional_usd), live=live, live_token=live_token, idempotency_key=idempotency_key))
        else:
            resp = json.loads(place_order(symbol, "sell", float(notional_usd), live=live, live_token=live_token, idempotency_key=idempotency_key))

        audit_log.append("decide_and_trade", payload, ok=bool(resp.get("ok")), error=resp.get("error"))
        if resp.get("ok"):
            return _ok({"decision": decision, "execution": resp["data"]})
        return _err(resp.get("error") or "Execution failed", data={"decision": decision, "execution": resp.get("data")})
    except Exception as e:
        audit_log.append("decide_and_trade", payload, ok=False, error=str(e))
        return _err(str(e))


@mcp.tool()
def backtest_strategy(symbol: str, days: int = 365, short_period: int = 20, long_period: int = 50) -> str:
    """
    Run a lightweight backtest for the combined strategy.
    Sentiment is disabled by default in backtests to reduce API calls.
    """
    try:
        r = backtest.run_backtest(
            symbol,
            days=int(days),
            short_period=int(short_period),
            long_period=int(long_period),
            use_sentiment=False,
        )
        return _ok({
            "symbol": r.symbol,
            "days": r.days,
            "trades": r.trades,
            "start_price": r.start_price,
            "end_price": r.end_price,
            "buy_and_hold_return": r.buy_and_hold_return,
            "strategy_return": r.strategy_return,
            "equity_curve": r.equity_curve,
        })
    except Exception as e:
        return _err(str(e))


# ─── Strategy Template Library ───────────────────────────────────────────────

@mcp.tool()
def list_strategy_templates() -> str:
    """List available strategy templates (starting points)."""
    try:
        return _ok(strategy_library.list_templates())
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def describe_strategy_template(template_id: str) -> str:
    """
    Return a plain-English summary and default parameters for a strategy template.
    """
    try:
        return _ok(strategy_library.describe_template(template_id))
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def run_strategy_template(template_id: str, symbol: str, params: dict | None = None) -> str:
    """
    Run a strategy template with optional parameter overrides.

    Example overrides:
      params={"short_period":10,"long_period":30,"bars_days":120}
    """
    try:
        r = strategy_library.run_template(template_id, symbol, params=params or {})
        return _ok({
            "template_id": r.template_id,
            "symbol": r.symbol,
            "action": r.action,
            "reason": r.reason,
            "price": r.price,
            "params": r.params,
            "metrics": r.metrics,
        })
    except Exception as e:
        return _err(str(e))


if __name__ == "__main__":
    print("Starting Alpaca Market MCP server...", file=sys.stderr, flush=True)
    mcp.run(transport="stdio")
