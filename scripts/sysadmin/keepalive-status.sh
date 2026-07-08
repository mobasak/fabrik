#!/usr/bin/env bash
# AFTER-EDIT: scripts/sysadmin/daily-digest.sh, scripts/sysadmin/proactive-check.sh, scripts/sysadmin/test_keepalive_status.py
#
# Shared keepalive-log CONTENT classifier — sourced by daily-digest.sh (digest health line)
# and proactive-check.sh (15-min pager). Both monitors used to trust the log's *mtime*,
# which the hourly keepalive refreshes even while writing a 401/usage-limit token — so a
# real month-long 401 outage read as "fresh". This parses the CONTENT instead.
#
#   keepalive_reason <logfile>
#     echoes a failure reason ("401_auth" | "usage_limit" | "KEEPALIVE_FAIL:<reason>") when
#     the keepalive is broken, or an EMPTY string when healthy / no break detected.
#     Prefers the token written by claude-keepalive-rotate.sh (KEEPALIVE_OK / KEEPALIVE_FAIL),
#     falling back to raw auth/quota detection for a pre-shim (old-format) log. A bare "401"
#     substring without auth wording is NOT treated as a failure.

# Mirrors claude_rotate.py::_USAGE_LIMIT_RE (all 5 branches, incl. "limit · resets") so a
# rotation-triggering render is also classified a usage-limit by the monitors.
_KEEPALIVE_LIMIT_RE='usage limit reached|hit your (weekly|session|opus|[0-9]+-hour) limit|[0-9]+-hour limit reached|out of extra usage|limit[[:space:]]*·[[:space:]]*resets'

keepalive_reason() {
    local log="$1"
    [ -e "$log" ] || { echo ""; return; }
    if grep -qiE 'KEEPALIVE_FAIL' "$log"; then
        local r
        r="$(grep -oiE 'KEEPALIVE_FAIL:[a-z0-9_]+' "$log" | head -1)"
        echo "${r:-KEEPALIVE_FAIL}"
        return
    fi
    if grep -qiE 'KEEPALIVE_OK' "$log"; then
        echo ""   # explicit healthy token
        return
    fi
    # Pre-shim (old-format) log with no token — fall back to raw auth/quota detection.
    if grep -qiE 'authentication|credential' "$log" && grep -qiE '\b401\b' "$log"; then
        echo "401_auth"
        return
    fi
    if grep -qiE "$_KEEPALIVE_LIMIT_RE" "$log"; then
        echo "usage_limit"
        return
    fi
    echo ""   # no break detected
}
