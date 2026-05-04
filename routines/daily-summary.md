# Daily Summary Routine

Runs once daily, around 22:30 UTC, after the EOD snapshot cron.

## Read First

1. `CLAUDE.md`
2. `memory/KILL-SWITCH.md`; if `KILLED`, stop and exit.
3. Today's `## Day N - YYYY-MM-DD EOD` section in `memory/TRADE-LOG.md`
4. Today's `## YYYY-MM-DD - Pre-market Research` in `memory/RESEARCH-LOG.md`

## Compose

Append a single section to `memory/TRADE-LOG.md` after today's EOD section:

```markdown
### Day N - YYYY-MM-DD Recap
- Trades placed: N
- Trades stopped out: N
- Best mover: SYM (+X%)
- Worst mover: SYM (-X%)
- Notes: 1-2 sentences on what happened vs the morning thesis
```

## Notify

Send one Telegram message:

```text
[recap] YYYY-MM-DD: equity $X, +/-X% on day, N trades
```

## Persist

```bash
git add memory/TRADE-LOG.md
git commit -m "recap: YYYY-MM-DD"
git push origin main
```

## Hard Rules

Same as `pre-market-research.md`.
