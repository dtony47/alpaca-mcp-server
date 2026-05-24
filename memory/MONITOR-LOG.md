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

## 2026-05-20T20:46:34.046290+00:00 - AVAX/USD skipped
- gate spread: 0.6174% >= 0.5000%

## 2026-05-20T22:33:57.487825+00:00 - SOL/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-21T05:29:22.617117+00:00 - DOGE/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-22T15:06:51.711816+00:00 - ETH/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-22T17:37:18.318964+00:00 - ETH/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-22T18:40:43.971809+00:00 - UNI/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-24T11:31:21.834125+00:00 - ETH/USD skipped
- gate position_count: Already at 6/6 open positions
