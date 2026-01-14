#!/bin/bash
set -euo pipefail

# Simple watchdog to restart container via orchestrator when health fails repeatedly.

SERVICE_NAME="${SERVICE_NAME:-fabrik}"
PORT="${PORT:-8000}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT}/health}"
INTERVAL="${WATCHDOG_INTERVAL:-30}"
MAX_FAILURES="${WATCHDOG_MAX_FAILURES:-3}"

failures=0

while true; do
    if ! curl -fs "$HEALTH_URL" >/dev/null 2>&1; then
        failures=$((failures + 1))
        echo "$(date -Is) [$SERVICE_NAME] health check failed ($failures/$MAX_FAILURES)" >&2
        if [ "$failures" -ge "$MAX_FAILURES" ]; then
            echo "$(date -Is) [$SERVICE_NAME] exiting to allow restart" >&2
            exit 1
        fi
    else
        failures=0
    fi

    sleep "$INTERVAL"
done
