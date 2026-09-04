#!/bin/bash
# AFTER-EDIT: scripts/wsl_startup_hook.sh, tests/test_wait_for_network.py, docs/workstation/hooks-index.md
#
# Block until DNS resolves, or a budget expires. ALWAYS exits 0 — fail-open by construction.
#
# WHY (measured 2026-09-04): WSL boots at T+0 and ~/.bashrc sources wsl_startup_hook.sh as soon as
# the first interactive shell opens — which on this box was T+3min, while the network stack was
# still coming up. Three separate failures in ONE boot traced to that single race:
#   1. `pipeline_alert.sh` lost a REAL contract-drift alert: telegram-direct died on
#      "[Errno -3] Temporary failure in name resolution" and ssh-apprise on "No route to host".
#   2. `[auto-commit] push failed — commit left local` — the daily pipeline's own commit stranded
#      off-box until a human pushed it hours later.
#   3. the pool classification round returned 0 of 10 units with cost $0.0000.
# All three would have succeeded ninety seconds later. The alert path itself is healthy: a
# selftest the same evening returned "PASS: alert delivered".
#
# FAIL-OPEN IS THE WHOLE CONTRACT. A boot-time guard that can hang is worse than the race it
# fixes: it would freeze every login shell on this box behind a network that may never arrive
# (a laptop booted offline, a WSL instance with no adapter). So the budget is bounded, the exit
# is unconditionally 0, and a timeout is a printed warning rather than a failure.
set -u

HOST="${WAIT_NET_HOST:-api.telegram.org}"
BUDGET_S="${WAIT_NET_TIMEOUT_S:-90}"
INTERVAL_S="${WAIT_NET_INTERVAL_S:-3}"

# A non-numeric override must not turn the guard into an infinite loop or a crash.
case "$BUDGET_S" in ''|*[!0-9]*) BUDGET_S=90 ;; esac
case "$INTERVAL_S" in ''|*[!0-9]*) INTERVAL_S=3 ;; esac
[ "$INTERVAL_S" -lt 1 ] && INTERVAL_S=1

elapsed=0
while :; do
    if getent hosts "$HOST" >/dev/null 2>&1; then
        [ "$elapsed" -gt 0 ] && echo "[wait_for_network] network up after ${elapsed}s"
        exit 0
    fi
    [ "$elapsed" -ge "$BUDGET_S" ] && break
    sleep "$INTERVAL_S"
    elapsed=$((elapsed + INTERVAL_S))
done

echo "[wait_for_network] WARNING: $HOST did not resolve within ${BUDGET_S}s — continuing anyway."
echo "[wait_for_network] Network-dependent steps below (alerts, git push, pool calls) may fail this boot."
exit 0
