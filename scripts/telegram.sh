#!/usr/bin/env bash
# Telegram notification wrapper.
# Usage: bash scripts/telegram.sh "<message>"
# Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env (or .env if present).
# On missing creds or failure, appends to memory/NOTIFICATIONS.md (gitignored).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
FALLBACK="$ROOT/memory/NOTIFICATIONS.md"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ $# -gt 0 ]]; then
  msg="$*"
else
  msg="$(cat)"
fi

if [[ -z "${msg// /}" ]]; then
  echo "usage: bash scripts/telegram.sh \"<message>\"" >&2
  exit 1
fi

stamp="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  mkdir -p "$(dirname "$FALLBACK")"
  printf "\n## %s [fallback — telegram unconfigured]\n%s\n" "$stamp" "$msg" >> "$FALLBACK"
  echo "[telegram fallback] appended to memory/NOTIFICATIONS.md"
  exit 0
fi

response=$(curl -fsS -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${msg}" 2>&1) || {
  mkdir -p "$(dirname "$FALLBACK")"
  printf "\n## %s [fallback — telegram failed]\n%s\n" "$stamp" "$msg" >> "$FALLBACK"
  echo "[telegram fallback] send failed, appended to memory/NOTIFICATIONS.md" >&2
  exit 0
}

echo "$response"
