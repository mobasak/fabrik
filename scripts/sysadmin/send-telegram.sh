#!/bin/bash
# send-telegram.sh — fallback Telegram POST helper for daily-digest.sh.
#
# Reads TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_ID from /opt/fabrik/.env.sysadmin
# (per-host token from the DR-store pool — docs/infrastructure/
# vps-ai-sysadmin.md:692). POSTs a message to api.telegram.org with
# 5s timeout + 2 retries (rule 58-resilience.md).
#
# Used by daily-digest.sh as the fallback path when:
#  - hub aro-wake forwarding fails (spoke fallback)
#  - operator manually invokes for testing
#
# Set DRY_RUN=1 to print the intended URL + body without actually sending.
#
# Returns exit code 0 on success (200 from Telegram), 1 on any failure
# including network errors after retries.

set -eu

MESSAGE="${1:-}"
if [ -z "$MESSAGE" ]; then
    echo "usage: $0 <message-text>" >&2
    exit 2
fi

ENV_FILE="/opt/fabrik/.env.sysadmin"
if [ ! -f "$ENV_FILE" ]; then
    echo "send-telegram.sh: $ENV_FILE missing" >&2
    exit 1
fi

# Read TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_ID without sourcing the whole
# .env.sysadmin (avoid exporting unrelated keys into our env).
BOT_TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
OWNER_ID=$(grep -E '^TELEGRAM_OWNER_ID=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")

if [ -z "$BOT_TOKEN" ] || [ -z "$OWNER_ID" ]; then
    echo "send-telegram.sh: TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_ID missing in $ENV_FILE" >&2
    exit 1
fi

# TELEGRAM_API_BASE override is for local simulation only (mock HTTP server).
# Production leaves it unset → defaults to real Telegram API.
API_BASE="${TELEGRAM_API_BASE:-https://api.telegram.org}"
URL="${API_BASE}/bot${BOT_TOKEN}/sendMessage"

if [ "${DRY_RUN:-0}" = "1" ]; then
    echo "[dry-run] would POST $URL"
    echo "[dry-run] chat_id=$OWNER_ID"
    echo "[dry-run] text (first 200 chars): ${MESSAGE:0:200}"
    exit 0
fi

# Retry loop: 2 retries, 1s + 2s backoff. Only retry on 5xx/network errors.
for attempt in 1 2 3; do
    body=$(jq -cn --arg c "$OWNER_ID" --arg t "$MESSAGE" \
            '{chat_id: $c, text: $t, disable_web_page_preview: true}')
    status=$(curl -s -o /tmp/.send-telegram-$$ \
            -w "%{http_code}" \
            --max-time 5 \
            -X POST "$URL" \
            -H "Content-Type: application/json" \
            -d "$body" || echo "000")
    rm -f /tmp/.send-telegram-$$
    if [ "$status" = "200" ]; then
        exit 0
    fi
    if [ "$attempt" -lt 3 ] && [ "$status" -ge "500" ] || [ "$status" = "000" ] || [ "$status" = "429" ]; then
        sleep "$attempt"
        continue
    fi
    echo "send-telegram.sh: Telegram returned HTTP $status after $attempt attempt(s)" >&2
    exit 1
done

exit 1
