# Crypto Trading Bot — Design Spec

**Date:** 2026-05-03
**Status:** Approved (brainstorming complete; awaiting implementation plan)
**Owner:** dtony47
**Code base:** extends `/Users/kofi/.openclaw/workspace/Alpaca/`
**Reference:** Nate Herk's "Opus 4.7 Trading Bot — Setup Guide" (architectural pattern only; instrument universe diverges)

---

## 1. Goals

- Fully automated 24/7 crypto trading bot with two execution legs:
  - **Majors leg** — BTC/ETH/SOL/DOGE/AVAX/LINK/UNI on Alpaca (CEX), swing-style.
  - **Memecoin leg** — on-chain Solana memecoins via Jupiter aggregator, fast-cut/trail.
- Disciplined risk gates enforced programmatically *before* every order.
- Git-as-state: all memory in markdown files committed to `main`. Free audit, rollback, diff.
- LLM-driven daily research and weekly review via Claude Code cloud routines.
- Always-on Python monitor for open memecoin positions; scheduled cron jobs for entries.
- Phased rollout: paper → 25% → 50% → 100% live capital, gated on prior-phase performance.

## 2. Non-goals (explicit)

- ❌ Custodying user keys or executing trades on the user's behalf. The user holds the wallet; the user flips the live switch.
- ❌ Options. Ever.
- ❌ Leverage, perpetual futures, margin. Spot only.
- ❌ MEV-extraction, sandwich attacks, frontrunning. We *defend* against MEV; we do not perform it.
- ❌ Promise of profit. The bot's edge is risk control and execution discipline, not picking winners.
- ❌ Copy-trading specific influencers (legally murky, frequently exploited as pump-and-dump bait).
- ❌ Sub-second high-frequency strategies. Lowest reaction time targeted: ~5 seconds.
- ❌ Stocks. The bot trades crypto only. (Existing stock-related code in `Alpaca/` is preserved but not extended.)
- ❌ Investment advice from the assistant building this. The user is responsible for all financial decisions.

## 3. Architecture

```
                    ┌──────────────────────────┐
                    │   git memory (main)      │  ← single source of state
                    └──────────────────────────┘
                                 ▲
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────────────┐      ┌───────────────────┐    ┌────────────────────┐
│ MAJORS LEG    │      │ MEMECOIN LEG       │    │ LLM ROUTINES       │
│ (Alpaca CEX)  │      │ (Solana / Jupiter) │    │ (Claude Code cloud)│
│               │      │                    │    │                    │
│ cron 1-4h     │      │ Scanner: cron 5min │    │ daily research     │
│ swing-style   │      │ Monitor: always-on │    │ daily recap        │
│ BTC/ETH/SOL   │      │ tight stops, fast  │    │ weekly review      │
│ DOGE/AVAX/UNI │      │ exits, rug-checks  │    │ strategy tuning    │
└───────────────┘      └───────────────────┘    └────────────────────┘
        │                        │                        │
        └────────────────────────┴────────────────────────┘
                                 │
                    ┌──────────────────────────┐
                    │  Shared Python core      │
                    │  - risk gates            │
                    │  - position sizing       │
                    │  - audit log             │
                    │  - notifications         │
                    │  - state reconciliation  │
                    │  - kill switch           │
                    └──────────────────────────┘
```

### Three execution legs

| Leg | Trigger | Latency target | Decision-maker |
|---|---|---|---|
| Majors (Alpaca) | GitHub Actions cron, every 60 min during US hours | minutes OK | Python strategy, no LLM in hot path |
| Memecoin scanner (Solana) | GitHub Actions cron, every 5 min, 24/7 | minutes OK for entries | Python filters → optional LLM review pass |
| Memecoin monitor (Solana) | Always-on Python service on Fly.io | ~5 sec for exits | Pure Python, deterministic, no LLM |
| LLM research / recap | Claude Code cloud routines | not latency-sensitive | Claude reads memory, writes memory |

### Hosting split

- **Always-on monitor**: Fly.io free tier (or Hetzner $4/mo if free tier insufficient). Single-region, single-machine. Watchdog + auto-restart.
- **Scheduled cron jobs**: GitHub Actions (free, 5-min minimum granularity). Reliable, integrated with the repo, secrets via GitHub Secrets.
- **LLM routines**: Claude Code cloud routines (per Nate Herk PDF pattern). Stateless containers, clone repo, run, push, exit.

## 4. Repository layout

Extends existing `Alpaca/` to preserve the strategy, risk, MCP, and backtest code already written.

```
Alpaca/
├── CLAUDE.md                       # NEW. Agent rulebook (PDF-style)
├── README.md                       # update for new scope
├── env.template                    # NEW. All required env vars enumerated
├── .env                            # gitignored, user fills in
├── .gitignore                      # ensure .env, *.db, wallet files present
│
├── core/                           # NEW. Shared logic across all legs
│   ├── __init__.py
│   ├── risk_gates.py               # buy-side + sell-side gate functions
│   ├── sizing.py                   # position sizing (% of equity, kelly cap)
│   ├── audit.py                    # trade audit log writer (append-only)
│   ├── reconcile.py                # reconcile local state with exchange/chain state
│   ├── notifications.py            # Telegram + file fallback
│   └── kill_switch.py              # daily-loss / drawdown / global-pause logic
│
├── majors/                         # NEW. CEX (Alpaca) leg
│   ├── __init__.py
│   ├── strategy.py                 # composite signal — extends existing strategy.py
│   ├── scanner.py                  # cron entrypoint
│   ├── executor.py                 # gate → buy → place trailing stop
│   └── eod.py                      # end-of-day snapshot
│
├── meme/                           # NEW. Solana DEX leg
│   ├── __init__.py
│   ├── jupiter.py                  # Jupiter swap quote + execute API wrapper
│   ├── solana_client.py            # RPC, wallet load, sign+send
│   ├── discovery.py                # DexScreener + Birdeye scanners
│   ├── filters.py                  # liquidity / age / holder / mint-auth filters
│   ├── rug_check.py                # GoPlus + Honeypot.is integration
│   ├── llm_review.py               # Perplexity/Claude research pass per candidate
│   ├── monitor.py                  # ALWAYS-ON service main loop
│   ├── scanner.py                  # cron entrypoint
│   └── executor.py                 # gate → swap → set stop levels
│
├── strategy.py, dex_strategy.py,   # EXISTING. Preserved, refactored as core/ matures
│   trader.py, risk.py, account.py,
│   market_data.py, polygon_data.py,
│   sentiment.py, dex_data.py,
│   config.py, mcp_server.py,
│   backtest.py, audit_log.py,
│   execution_store.py, indicators.py
│
├── routines/                       # NEW. Claude Code cloud routine prompts
│   ├── README.md                   # how to wire each routine
│   ├── pre-market-research.md      # 1×/day, ~07:00 UTC: market context + ideas
│   ├── daily-summary.md            # 1×/day, ~22:00 UTC: P&L + EOD snapshot
│   └── weekly-review.md            # Sunday: stats, grade, strategy tuning
│
├── scripts/                        # NEW. Shell wrappers (PDF pattern)
│   ├── alpaca.sh                   # wraps Alpaca v2 API
│   ├── jupiter.sh                  # wraps Jupiter swap quote/exec
│   ├── solana.sh                   # wraps Solana RPC for balance/positions
│   ├── perplexity.sh               # research wrapper (optional)
│   └── telegram.sh                 # notification wrapper
│
├── memory/                         # NEW. Git-as-state per PDF model
│   ├── TRADING-STRATEGY.md         # rulebook (read first every session)
│   ├── TRADE-LOG.md                # every trade, every EOD snapshot
│   ├── RESEARCH-LOG.md             # daily LLM-written research entry
│   ├── WEEKLY-REVIEW.md            # Sunday recaps with letter grade
│   ├── PROJECT-CONTEXT.md          # mission, capital, phase
│   ├── KILL-SWITCH.md              # bot state: ACTIVE | PAUSED | KILLED
│   ├── MEMECOIN-WATCHLIST.md       # manual override list of tokens
│   ├── PHASE.md                    # current phase (paper / 25% / 50% / 100%)
│   └── MONITOR-LOG.md              # batched writes from always-on monitor
│
├── monitor/                        # NEW. Fly.io always-on deployment
│   ├── Dockerfile
│   ├── fly.toml
│   ├── health.py                   # /health endpoint for watchdog
│   └── entrypoint.py               # imports meme/monitor.py main loop
│
├── .github/workflows/              # NEW. GitHub Actions crons + CI
│   ├── majors-scanner.yml          # */60 min during US hours, weekdays
│   ├── meme-scanner.yml            # */5 min 24/7
│   ├── eod-snapshot.yml            # 22:00 UTC daily
│   └── ci-tests.yml                # on push/PR: pytest, ruff, mypy
│
├── tests/                          # NEW. Pytest suite (currently absent)
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_risk_gates.py          # MUST pass before any live code
│   ├── test_sizing.py
│   ├── test_filters.py             # rug-check / liquidity filters
│   ├── test_kill_switch.py
│   ├── test_reconcile.py
│   ├── test_notifications.py
│   └── fixtures/                   # canned API responses (Alpaca, Jupiter, GoPlus, etc.)
│
└── docs/superpowers/specs/
    └── 2026-05-03-crypto-trading-bot-design.md   # THIS DOC
```

## 5. Risk controls (the critical section)

### 5.1 Pre-trade gates — ALL must pass; failure logs reason and skips order

**Universal gates (both legs):**

| # | Gate | Default value | Configurable in |
|---|---|---|---|
| U1 | Kill switch == `ACTIVE` | n/a | `memory/KILL-SWITCH.md` |
| U2 | Phase == valid phase from `PHASE.md` | n/a | `memory/PHASE.md` |
| U3 | Realized + unrealized day P&L > daily-loss-limit | -3% of equity | `core/risk_gates.py` |
| U4 | Phase-to-date drawdown < phase-DD-limit | -15% of starting equity | `core/risk_gates.py` |
| U5 | Total open positions on this leg ≤ max | majors: 6, meme: 10 | `core/risk_gates.py` |
| U6 | Position cost ≤ allowed % of equity | majors: 20%, meme: 2-3% | `core/risk_gates.py` |
| U7 | Position cost ≤ available cash on that venue | n/a | runtime |
| U8 | Trades-in-last-hour ≤ rate limit | majors: 5, meme: 20 | `core/risk_gates.py` |

**Majors-only gates:**

| # | Gate | Default |
|---|---|---|
| M1 | Symbol in approved list | BTC/ETH/SOL/DOGE/AVAX/LINK/UNI |
| M2 | Spread (ask − bid) / mid | < 0.5% |
| M3 | Strategy composite score crossed buy threshold | score ≥ 1.5 |

**Memecoin-only gates:**

| # | Gate | Default |
|---|---|---|
| C1 | Pool USD liquidity | ≥ $50,000 |
| C2 | Token age | ≥ 24 hours |
| C3 | Holder count | ≥ 500 |
| C4 | Top-10 holder concentration | < 25% of supply |
| C5 | Mint authority | renounced |
| C6 | Freeze authority | renounced |
| C7 | GoPlus rug-check | PASS |
| C8 | Honeypot.is check | PASS |
| C9 | LLM research pass | not `RED_FLAG` or `INSUFFICIENT_DATA` |
| C10 | Estimated slippage at intended size | < 3% |
| C11 | Position size as % of pool liquidity | ≤ 0.5% |

### 5.2 Sell-side rules

**All positions:**
- Hard stop at -7% from entry → market sell immediately. Manual sell, no hoping.
- Trailing stop: 10% on entry. Tightens to 7% at +15%. Tightens to 5% at +20%.
- Never tighten within 3% of current price. Never move a stop down.
- Thesis-broken exit: if conditions invalidate (sector rolls, news event, catalyst gone), exit even before stop hits.

**Memecoin-specific additional sells:**
- Take-profit ladder: sell 25% at +50%, 25% at +100%, 25% at +200%, hold last 25% with trailing stop.
- Liquidity-drain exit: if pool USD liquidity drops by >30% from entry, exit immediately (rug indicator).
- Holder-spike exit: if top-10 holder concentration jumps by >5pp since entry, exit (insider dump signal).

### 5.3 Kill switches (enforced by `core/kill_switch.py`, evaluated every tick)

- Daily realized + unrealized loss > -5% of equity → auto-pause new entries for 24h, exits still permitted.
- Phase-to-date drawdown > -20% → auto-halt all new entries; user must manually edit `KILL-SWITCH.md` back to `ACTIVE` to resume.
- 3 consecutive losing memecoin trades → pause memecoin leg for 24h.
- Manual override: editing `memory/KILL-SWITCH.md` to `KILLED` halts everything within one tick.

## 6. Memory model

Single source of state is git on `main`. Every cron firing reads from main, writes to memory files, commits + pushes before exit.

| File | Purpose | Write cadence |
|---|---|---|
| `TRADING-STRATEGY.md` | Rulebook. Read first every session. | Updated by weekly review only |
| `TRADE-LOG.md` | Every trade + daily EOD snapshot | Every trade, every EOD |
| `RESEARCH-LOG.md` | One dated entry per day | Daily LLM routine |
| `WEEKLY-REVIEW.md` | Friday/Sunday recap with letter grade | Weekly |
| `PROJECT-CONTEXT.md` | Mission, capital target, current phase | Rarely |
| `KILL-SWITCH.md` | `ACTIVE` \| `PAUSED` \| `KILLED` | On any kill-switch event |
| `MEMECOIN-WATCHLIST.md` | Manual-override token list | User-edited |
| `PHASE.md` | Current phase (paper / 25% / 50% / 100%) | Manually advanced by user only |
| `MONITOR-LOG.md` | Batched writes from always-on monitor | Every 5 min if change |

Append-only dated sections in TRADE-LOG / RESEARCH-LOG / WEEKLY-REVIEW prevent merge conflicts in practice. Schedules are ≥5 min apart, so race conditions effectively don't exist.

Reconciliation: every cron firing pulls live state from Alpaca + Solana and reconciles against memory. If a position exists on the exchange but not in TRADE-LOG, the bot logs the discrepancy and adopts the exchange state as truth.

## 7. External dependencies

| Service | Purpose | Cost | Required for |
|---|---|---|---|
| Alpaca (paper) | CEX majors paper trading | free | Phase 1 |
| Alpaca (live) | CEX majors live trading | free | Phase 2+ |
| Helius | Solana RPC + webhooks | free tier sufficient initially | meme leg |
| Jupiter | Solana DEX aggregator | free | meme execution |
| DexScreener | trending + price data | free | meme discovery |
| Birdeye | token data | free tier sufficient | meme discovery |
| GoPlus | rug-check API | free tier sufficient | meme rug-check |
| Honeypot.is | honeypot detection | free | meme rug-check |
| Perplexity | LLM research backend | ~$5/mo | LLM routines |
| Telegram Bot | notifications | free | all legs |
| Fly.io | always-on monitor host | free tier sufficient initially | meme monitor |
| GitHub | repo + Actions crons | free | scheduled jobs, CI |
| Claude Code cloud | LLM-driven routines | per usage | research, recap, weekly review |

**Key custody:** the user holds all keys. The assistant never sees Alpaca secrets, Solana wallet seeds, Telegram tokens, or Perplexity API keys. The Solana wallet is created by the user (Phantom export or `solana-keygen`), funded with the meme-sleeve allocation, and the keypair file is mounted to a path the monitor reads at runtime. Key-handling protocol is documented separately when that step is reached.

## 8. Phasing

| Phase | Window | Capital | Pass-bar to advance |
|---|---|---|---|
| 0 — Build | Week 0 | none | All unit tests green; CI green; smoke test against Alpaca paper succeeds |
| 1 — Paper | Weeks 1-4 | Alpaca paper + $50-100 SOL on mainnet | Net positive P&L OR clear evidence rules are protecting capital correctly |
| 2a — Live 25% | Weeks 5-6 | 25% of target ($500-2,500) | Net positive OR ≤ -5% loss |
| 2b — Live 50% | Weeks 7-8 | 50% of target ($1,000-5,000) | Net positive OR ≤ -5% loss |
| 2c — Live 100% | Week 9+ | 100% of target ($2,000-10,000) | n/a (operational from here) |

Phase transitions require the user to manually edit `memory/PHASE.md`. The bot does not promote itself.

**Hard gate the assistant enforces:** when transitioning from Phase 1 to Phase 2a (first real money), the assistant pauses and requires explicit written confirmation in chat ("yes, go live with $X on leg Y") before any live order ships. This applies even if Phase 1 results are excellent.

## 9. Testing approach

Hard requirement, not nice-to-have. Bare minimum before *any* live money:

- 100% unit test coverage on `core/risk_gates.py` and `core/kill_switch.py` — these are the safety net.
- Unit tests on sizing, reconciliation, filters, rug-check parsing, notification fallback.
- Integration tests against Alpaca paper API.
- Integration test against Solana devnet for swap flow.
- Backtest harness for the majors strategy (extend existing `backtest.py`).
- Chaos drill: simulate API failures, partial fills, network drops; verify state reconciliation works.

CI runs all tests on every push/PR via GitHub Actions. **No live deploy if tests are red.**

## 10. Honest limitations

- Memecoin slippage on real entries will be worse than the simulator estimates. Always.
- The bot will get rugged occasionally despite filters. The filters reduce frequency, not eliminate.
- LLM research (Perplexity/Claude pass) is fallible. It's a filter, not an oracle.
- Real-time monitor on Fly.io free tier will occasionally hiccup. Watchdog + Telegram alerting mitigate but do not eliminate.
- The first month of live trading typically reveals "real-money behavior gap" — slippage, partial fills, panic — that paper does not. Phasing exists for this reason.
- Past performance, especially in crypto, is not predictive.

## 11. Build milestones (rough)

| Week | Deliverable |
|---|---|
| 1 | Repo restructure; `core/` (risk, sizing, kill-switch, notifications) with full test coverage; env scaffolding; Telegram + memory wiring |
| 2 | Majors leg complete on Alpaca paper. End-to-end: scanner → gate → buy → trailing stop → EOD snapshot. Daily LLM routine wired |
| 3 | Memecoin leg — Jupiter wrapper, discovery, filters, rug-check, LLM review. Devnet swap integration test |
| 4 | Always-on monitor on Fly.io. Mainnet smoke test with $50-100 SOL. Weekly review routine. Operational dashboards |
| 5-8 | Phase 1 paper run; tune thresholds; iterate strategy based on observed behavior |
| 9+ | Phased live rollout per Section 8 |

## 12. Open questions / decisions deferred

- Specific allocation split inside the majors leg (BTC vs ETH vs SOL weights) — defer to Phase 1 observations.
- Whether to add multi-chain memecoin support (Base, Ethereum) — defer to Phase 2c if volume warrants.
- Whether to add Helius webhook subscriptions for known tokens (in addition to polling) — defer; polling is sufficient at the latency target.
- Specific Telegram channel/group structure (single chat vs separate alert/log channels) — confirm at wiring time.
- Whether to add a small read-only web dashboard (Streamlit / FastAPI) for portfolio state — nice-to-have, deferred.

## 13. Document control

This spec is the source of truth for the build. If the implementation diverges, the spec is updated first, change is noted in commit message, and the user is informed in chat.
