#!/usr/bin/env bash
# AFTER-EDIT: scripts/sysadmin/claude_rotate.py, scripts/bootstrap/templates/sysadmin-cron.template, scripts/sysadmin/test_refresh_standbys.py
#
# Standby-token freshness. The ACTIVE account self-refreshes (the hourly keepalive pings it), but
# the frozen manager-accounts/ SNAPSHOTS go stale — an OAuth refresh token dies after ~4 days idle,
# so the day the active account hits its limit, rotation could install a dead standby. This DAILY
# routine keeps every captured account alive: it cycles each snapshot — switch to it, ping it
# DIRECTLY (bare claude, NOT through rotation, so the refresh lands on THAT account), and on success
# copy the now-refreshed active creds back over that snapshot (atomic rename). The ORIGINAL active
# account is restored at the end. Self-contained per host; no WSL dependency.
#
# Classification of each account's ping:
#   401 (auth failure)      -> DEAD: token is gone, can't refresh; snapshot LEFT UNTOUCHED + alerted.
#   success OR usage-limit  -> LIVE: auth succeeded (a limit is post-auth), token valid -> re-snapshot.
#   other non-zero (timeout/network/exec) -> SKIP: uncertain, leave the snapshot as-is, log it.
# A DEAD account cannot be revived here — the operator re-captures it via claude-manager. This
# routine prevents the drift INTO death; it is not a resurrection. Never logs token bytes (only the
# non-secret account dir names + a KEEPALIVE-style summary token to $LOG).
#   REFRESH_OK <n>/<total> <iso>            — all live, n snapshots refreshed
#   REFRESH_DEAD:<names> refreshed=<n>/<t> <iso>  — some accounts dead/uncertain (also Telegram-alerted)
set -uo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
ACCOUNTS_DIR="$CLAUDE_DIR/manager-accounts"
ACTIVE="$CLAUDE_DIR/.credentials.json"
LOG="${CLAUDE_REFRESH_LOG:-/var/log/claude-refresh-standbys.log}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${CLAUDE_ROTATE_PYTHON:-python3}"
ROTATE="$DIR/claude_rotate.py"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || echo /usr/bin/claude)}"
PING_TIMEOUT="${CLAUDE_REFRESH_PING_TIMEOUT:-90}"
now="$(date -Is)"

# Mirrors claude_rotate.py::_USAGE_LIMIT_RE — a usage-limit render means the account AUTHENTICATED
# (the limit is post-auth), so its token is live and worth re-snapshotting, unlike a 401.
_limit_re='usage limit reached|hit your (weekly|session|opus|[0-9]+-hour) limit|[0-9]+-hour limit reached|out of extra usage|limit[[:space:]]*·[[:space:]]*resets'

# Discover captured accounts by dir name (charset-validated — the name is interpolated into paths).
shopt -s nullglob
accounts=()
for d in "$ACCOUNTS_DIR"/*/; do
    [ -f "${d}.credentials.json" ] || continue
    name="$(basename "$d")"
    [[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || continue
    accounts+=("$name")
done
shopt -u nullglob
if [ ${#accounts[@]} -eq 0 ]; then
    echo "REFRESH_SKIP:no_accounts ${now}" > "$LOG"
    exit 0
fi

# Remember the ORIGINAL active account so we can restore it. Prefer the dir name (a --switch back
# then installs its freshly-refreshed snapshot); keep a 0600 byte backup as a fallback for an active
# that matches no snapshot.
orig_name="$("$PYTHON" "$ROTATE" --list 2>/dev/null | awk '/^\*/{print $2; exit}')"
orig_bak="$(mktemp)"; chmod 600 "$orig_bak"
[ -f "$ACTIVE" ] && cp "$ACTIVE" "$orig_bak"

refreshed=0
problem=()
for acc in "${accounts[@]}"; do
    if ! "$PYTHON" "$ROTATE" --switch "$acc" >/dev/null 2>&1; then
        problem+=("${acc}:switch"); continue
    fi
    OUT="$(timeout "$PING_TIMEOUT" "$CLAUDE_BIN" -p ping 2>&1)"; rc=$?

    is401=0
    if grep -qiE '\b401\b' <<<"$OUT" && grep -qiE 'authentication|credential' <<<"$OUT"; then is401=1; fi
    is_limit=0
    if grep -qiE "$_limit_re" <<<"$OUT"; then is_limit=1; fi

    if [ "$is401" -eq 1 ]; then
        problem+=("${acc}:dead_401"); continue           # token gone — do NOT re-snapshot
    fi
    if [ "$rc" -ne 0 ] && [ "$is_limit" -eq 0 ]; then
        problem+=("${acc}:exit_${rc}"); continue          # uncertain (timeout/network) — leave as-is
    fi
    # Live (success or usage-limit): capture the refreshed active creds back into this snapshot,
    # atomically (write to a same-dir temp + rename), 0600, no token bytes logged.
    snap="$ACCOUNTS_DIR/$acc/.credentials.json"
    tmp="${snap}.tmp.$$"
    if cp "$ACTIVE" "$tmp" && chmod 600 "$tmp" && mv -f "$tmp" "$snap"; then
        refreshed=$((refreshed + 1))
    else
        rm -f "$tmp"; problem+=("${acc}:snapshot_write")
    fi
done

# Restore the original active account (freshly-refreshed if it was among the cycled accounts).
if [ -n "$orig_name" ] && "$PYTHON" "$ROTATE" --switch "$orig_name" >/dev/null 2>&1; then
    :
elif [ -s "$orig_bak" ]; then
    tmp="${ACTIVE}.tmp.$$"
    cp "$orig_bak" "$tmp" && chmod 600 "$tmp" && mv -f "$tmp" "$ACTIVE" || rm -f "$tmp"
fi
rm -f "$orig_bak"

if [ ${#problem[@]} -eq 0 ]; then
    echo "REFRESH_OK ${refreshed}/${#accounts[@]} ${now}" > "$LOG"
    exit 0
fi
echo "REFRESH_DEAD:${problem[*]} refreshed=${refreshed}/${#accounts[@]} ${now}" > "$LOG"
# Best-effort operator alert about accounts that could not be refreshed (dead/uncertain standbys).
REFRESH_DIR="$DIR" REFRESH_MSG="⚠️ Claude standby refresh on $(hostname -s): account(s) not refreshed: ${problem[*]} (refreshed ${refreshed}/${#accounts[@]}). A 'dead_401' needs re-capture via claude-manager." \
    "$PYTHON" -c 'import os,sys; sys.path.insert(0, os.environ["REFRESH_DIR"]); import claude_rotate; claude_rotate._notify_telegram(os.environ["REFRESH_MSG"])' 2>/dev/null || true
exit 1
