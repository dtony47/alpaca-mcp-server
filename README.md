# Alpaca Trading Toolkit

Python toolkit for paper trading with Alpaca, enriched with Polygon market data, news sentiment, and DEX/Web3 token analysis.

This repository supports two main workflows:

- CLI commands for account views, analysis, and paper orders
- MCP server tools so an LLM can call market/trading functions in chat

## Features

- Alpaca paper account dashboard (account, positions, orders, risk)
- Real-time stock/crypto quotes and historical bars
- Polygon snapshot, options flow, large-trade, and ticker detail utilities
- Combined stock/crypto strategy:
  - SMA crossover trend scoring
  - RSI filter
  - Headline sentiment
  - Options flow weighting (stocks)
- DEX strategy for Web3 tokens using DexScreener + CoinGecko
- Trade execution helpers with risk sizing and dry-run support

## Project Structure

- `main.py` - CLI entrypoint
- `mcp_server.py` - MCP server exposing project tools over stdio
- `strategy.py` - Combined MA/RSI/sentiment/options signal logic
- `dex_strategy.py` - DEX token scoring logic
- `trader.py` - Buy/sell/close order helpers
- `risk.py` - Position sizing and risk report
- `account.py` - Account, positions, and order display helpers
- `market_data.py` - Alpaca stock/crypto quote and bar retrieval
- `polygon_data.py` - Polygon market/news/options integrations
- `sentiment.py` - Keyword-based news sentiment scoring
- `dex_data.py` - DexScreener/CoinGecko data adapters
- `config.py` - Env loading and risk constants

## Requirements

- Python 3.10+ recommended
- Alpaca paper trading credentials
- Polygon API key for Polygon-powered endpoints

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
POLYGON_API_KEY=your_polygon_key

# LLM-driven execution controls (used by MCP execution tools)
LLM_TRADING_ENABLED=false
LLM_TRADING_MODE=paper
LLM_ALLOWED_ASSET_CLASSES=crypto
LLM_ALLOWED_SYMBOLS=BTC/USD,ETH/USD
LLM_MAX_NOTIONAL_USD=500
LLM_MAX_TRADES_PER_DAY=10
LLM_MIN_SECONDS_BETWEEN_TRADES=30
LLM_REQUIRE_LIVE_TOKEN=true
LLM_LIVE_TOKEN=choose_a_long_random_string
```

Notes:

- The code is configured for paper trading. `config.py` asserts `paper-api` is in `ALPACA_BASE_URL`.
- Keep secrets out of source control.

## CLI Usage

Run the default dashboard:

```bash
python main.py
```

Common commands:

```bash
python main.py account
python main.py positions
python main.py orders
python main.py risk
python main.py quote AAPL
python main.py quote BTC/USD
python main.py snapshot AAPL
python main.py sentiment AAPL
python main.py flow AAPL
python main.py analyze AAPL
python main.py scan AAPL MSFT BTC/USD
python main.py trade AAPL
python main.py trade AAPL --live
python main.py buy AAPL 500
python main.py sell AAPL 500
python main.py close AAPL
python main.py closeall
python main.py dex PEPE
```

Execution behavior:

- `trade` defaults to dry-run unless `--live` is provided
- `closeall` prompts for confirmation

## MCP Server Usage

Start server:

```bash
python3 mcp_server.py
```

Example MCP config snippet:

```json
{
  "mcpServers": {
    "alpaca-market": {
      "command": "python3",
      "args": ["/absolute/path/to/Alpaca/mcp_server.py"]
    }
  }
}
```

Exposed MCP tools include:

- `get_quote`
- `get_snapshot`
- `get_sentiment`
- `get_options_flow`
- `get_large_trades`
- `get_ticker_details`
- `get_account`
- `get_positions`
- `run_strategy`
- `scan_watchlist`
- `search_dex_token`
- `get_dex_token`
- `run_dex_strategy`
- `get_execution_policy`
- `place_order`
- `close_position`
- `close_all_positions`
- `decide_and_trade`
- `backtest_strategy`
- `list_strategy_templates`
- `describe_strategy_template`
- `run_strategy_template`

## Strategy Overview

### Combined stock/crypto signal (`strategy.py`)

Composite score is built from:

- MA crossover/trend score
- RSI regime score
- News sentiment score
- Options flow score (stocks only)

Decision thresholds:

- BUY if score >= `1.5`
- SELL if score <= `-1.5`
- HOLD otherwise

### DEX signal (`dex_strategy.py`)

DEX scoring combines:

- 24h and 1h momentum
- Buy vs sell pressure
- Volume/liquidity activity ratio
- Liquidity health
- CoinGecko community sentiment

It also emits risk flags (for example low liquidity, heavy selling, pump/crash conditions).

## Risk Controls

Risk parameters are defined in `config.py`:

- `MAX_POSITION_PCT`
- `MAX_TRADE_USD`
- `STOP_LOSS_PCT`

Position sizing is calculated in `risk.py` and used by order helpers in `trader.py`.

## Known Gaps

- No formal test suite is included yet
- No CI/CD pipeline is configured
- No container/deployment manifests are included

## Disclaimer

This project is for educational and tooling purposes. Market data and strategy outputs are not financial advice. Use only with paper trading unless you fully understand and accept the risks.
