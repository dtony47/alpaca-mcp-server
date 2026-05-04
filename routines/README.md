# Claude Code Cloud Routines

Each `.md` file in this directory is a system prompt for a Claude Code cloud routine.
Routines run on their own schedule, clone the repo, execute the prompt, commit and push,
then exit.

| File | Cadence | Purpose |
|---|---|---|
| `pre-market-research.md` | 1x/day, ~07:00 UTC | Read account and market context, write `memory/RESEARCH-LOG.md`, propose ideas |
| `daily-summary.md` | 1x/day, ~22:30 UTC | Recap the trading day in `memory/TRADE-LOG.md` and Telegram |
| `weekly-review.md` | Sunday 23:00 UTC (Plan 4) | Write `memory/WEEKLY-REVIEW.md` with grade and tuning notes |

## Wiring

In Claude Code -> Cloud Routines -> New Routine:

1. Repo: `<your-github-org>/Alpaca`
2. Branch: `main`
3. Schedule: as per the table above
4. Prompt: paste the contents of the corresponding `.md` file
5. Secrets: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_CHAT_ID`, `PERPLEXITY_API_KEY` for research

## Routine Discipline

- Read `memory/KILL-SWITCH.md` first. If `KILLED`, do nothing and exit.
- Read `CLAUDE.md` before any action.
- Write only to `memory/*.md`. Never edit code from a routine.
- Always `git add`, `git commit`, and `git push origin main` before exit.
- Keep messages concise: short bullets, no preamble.
