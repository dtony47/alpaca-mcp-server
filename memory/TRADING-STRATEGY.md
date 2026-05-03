# Trading Strategy

## Mission
Multi-leg crypto trading bot. Beat a 60/40 BTC/ETH benchmark over the challenge window, with capital preservation as the primary objective.

## Capital
- Phase target (Phase 2c): $2,000-$10,000
- Memecoin sleeve: 20-30% of total
- Majors sleeve: 70-80% of total

## Universe
- **Majors (CEX, Alpaca):** BTC, ETH, SOL, DOGE, AVAX, LINK, UNI
- **Memecoins (Solana DEX, Jupiter):** dynamically discovered, filtered, manually overridable via `MEMECOIN-WATCHLIST.md`

## Hard Rules (non-negotiable)
1. NO options, ever
2. NO leverage, perps, margin — spot only
3. Stops are real GTC orders on Alpaca; on-chain stops are enforced by the always-on monitor
4. Cut losers at -7% from entry. Manual sell. No averaging down.
5. Trailing stops: 10% on entry, 7% at +15%, 5% at +20%
6. Never tighten within 3% of current price; never move a stop down
7. Memecoin take-profit ladder: sell 25% at +50%, +100%, +200%; hold last 25% on trail
8. Memecoin liquidity-drain exit: pool down >30% from entry → exit immediately
9. Patience > activity. A day with zero trades is fine.

## Position Limits
- Max majors positions: 6 (max 20% per position)
- Max meme positions: 10 (max 2-3% per position)
- Max trades per hour: majors 5, meme 20

## Kill Switches
- Daily P&L < -5% → 24h pause on new entries
- Phase drawdown > -20% → halt; manual reset required
- 3 consecutive memecoin losses → 24h pause on memecoin leg
- `KILL-SWITCH.md == KILLED` → halt everything within one tick

## Memecoin entry filters (ALL must pass)
- Liquidity ≥ $50,000
- Age ≥ 24 hours
- Holders ≥ 500
- Top-10 holder concentration < 25%
- Mint authority renounced
- Freeze authority renounced
- GoPlus rug-check PASS
- Honeypot.is PASS
- Estimated slippage < 3%
- Position size ≤ 0.5% of pool liquidity
- LLM research pass not RED_FLAG
