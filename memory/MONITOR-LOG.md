# Monitor Log

Batched event log written by the always-on memecoin monitor (`meme/monitor.py`, lands in Plan 4).
Entries are appended in 5-minute batches when the monitor takes action (exit, stop tighten, alert).

Format:
- `## YYYY-MM-DD HH:MM:SS UTC` — batch header
- per-action bullets describing the position, action, and reason

Empty until the monitor is deployed (Plan 4).

## 2026-05-09T10:25:00.198217+00:00 - ETH/USD skipped
- gate position_size: Intended $20153.70 exceeds max $20153.6980 (20% of equity)

## 2026-05-09T13:33:41.543185+00:00 - BTC/USD skipped
- gate position_size: Intended $20153.70 exceeds max $20153.6980 (20% of equity)

## 2026-05-15T11:41:06.480758+00:00 - SOL/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-18T01:45:08.655109+00:00 - UNI/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-18T03:13:33.586895+00:00 - DOGE/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-19T19:36:15.983026+00:00 - AVAX/USD skipped
- gate spread: 0.5544% >= 0.5000%

## 2026-05-20T19:47:00.658381+00:00 - ETH/USD skipped
- gate position_count: Already at 6/6 open positions
