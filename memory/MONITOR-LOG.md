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

## 2026-05-24T12:28:14.362540+00:00 - BTC/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-24T12:28:14.362540+00:00 - SOL/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-24T12:28:14.362540+00:00 - AVAX/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-24T15:28:11.732514+00:00 - DOGE/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-24T15:28:11.732514+00:00 - LINK/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-24T16:25:10.321210+00:00 - UNI/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-25T22:25:38.551731+00:00 - SOL/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-25T22:25:38.551731+00:00 - DOGE/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-25T22:25:38.551731+00:00 - AVAX/USD skipped
- gate spread: 0.5905% >= 0.5000%

## 2026-05-25T22:25:38.551731+00:00 - LINK/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-28T00:47:34.440990+00:00 - DOGE/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-29T22:34:13.142689+00:00 - SOL/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-29T23:32:11.534631+00:00 - ETH/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-29T23:32:11.534631+00:00 - DOGE/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-30T03:11:00.481935+00:00 - LINK/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-30T13:34:20.928752+00:00 - UNI/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-30T15:29:46.020603+00:00 - AVAX/USD skipped
- gate spread: 0.6211% >= 0.5000%

## 2026-05-30T19:33:01.184530+00:00 - UNI/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-05-30T20:25:28.677116+00:00 - AVAX/USD skipped
- gate spread: 0.5795% >= 0.5000%

## 2026-06-07T11:36:28.373385+00:00 - LINK/USD skipped
- gate position_count: Already at 6/6 open positions

## 2026-06-07T11:36:28.373385+00:00 - UNI/USD skipped
- gate position_count: Already at 6/6 open positions
