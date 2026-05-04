#!/usr/bin/env bash
# Alpaca v2 / v1beta3 API wrapper.
# Usage:
#   bash scripts/alpaca.sh GET /v2/account
#   bash scripts/alpaca.sh GET /v2/positions
#   bash scripts/alpaca.sh GET '/v1beta3/crypto/us/bars?symbols=BTC/USD&timeframe=1Hour&limit=100' --data-host
#   bash scripts/alpaca.sh POST /v2/orders -d '{"symbol":"BTC/USD","qty":"0.0001","side":"buy","type":"market","time_in_force":"gtc"}'
#
# Reads ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, ALPACA_DATA_URL from env (or .env).
# --data-host flag routes to ALPACA_DATA_URL (market data); default routes to ALPACA_BASE_URL (trading).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${ALPACA_API_KEY:?ALPACA_API_KEY not set}"
: "${ALPACA_SECRET_KEY:?ALPACA_SECRET_KEY not set}"
: "${ALPACA_BASE_URL:?ALPACA_BASE_URL not set}"
: "${ALPACA_DATA_URL:?ALPACA_DATA_URL not set}"

if [[ $# -lt 2 ]]; then
  echo "usage: $(basename "$0") METHOD PATH [--data-host] [-- curl_args...]" >&2
  exit 1
fi

method="$1"
path="$2"
shift 2

host="$ALPACA_BASE_URL"
if [[ "${1:-}" == "--data-host" ]]; then
  host="$ALPACA_DATA_URL"
  shift
fi

curl -fsS -X "$method" \
  -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
  -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
  -H "Content-Type: application/json" \
  "${host}${path}" \
  "$@"
