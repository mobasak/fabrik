#!/usr/bin/env bash
# AFTER-EDIT: scripts/sysadmin/claude_rotate.py, scripts/sysadmin/daily-digest.sh, scripts/sysadmin/proactive-check.sh, scripts/bootstrap/templates/sysadmin-cron.template
#
# OAuth keepalive shim. Runs `claude -p ping` THROUGH account rotation (claude_rotate.py),
# then writes a CONTENT token to the keepalive log — for the health monitors (daily-digest.sh,
# proactive-check.sh) to check the token, not just the log mtime, and so surface a REAL
# auth/quota break (that content-check is added in the monitoring-honesty phase):
#   KEEPALIVE_OK <iso8601>              — claude answered; auth + quota healthy
#   KEEPALIVE_FAIL:<reason> <iso8601>   — 401_auth | usage_limit | exit_<rc>
# Single-run overwrite (matches the cron's `>` redirect). The claude output itself is NEVER
# written to the log — only the classification word — so no token bytes / response content leak.
set -uo pipefail

LOG="${CLAUDE_KEEPALIVE_LOG:-/var/log/claude-keepalive.log}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${CLAUDE_ROTATE_PYTHON:-python3}"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || echo /usr/bin/claude)}"

now="$(date -Is)"

# Run claude via rotation; capture combined output into a variable (never to the log).
OUT="$("$PYTHON" "$DIR/claude_rotate.py" "$CLAUDE_BIN" -p ping 2>&1)"
RC=$?

# Mirrors claude_rotate.py::_USAGE_LIMIT_RE (all 5 branches) so the same output that triggers
# a rotation is also classified a usage-limit here — incl. the "limit · resets" render.
_limit_re='usage limit reached|hit your (weekly|session|opus|[0-9]+-hour) limit|[0-9]+-hour limit reached|out of extra usage|limit[[:space:]]*·[[:space:]]*resets'

# Classify STRICTLY and consistently — a benign response that merely contains the substring
# "401" (e.g. a port number) is NOT a failure. A real 401 needs the auth wording; a usage
# limit needs a limit phrase. Only then does a non-zero exit count as a generic failure.
reason=""
if grep -qiE '\b401\b' <<<"$OUT" && grep -qiE 'authentication|credential' <<<"$OUT"; then
    reason="401_auth"
elif grep -qiE "$_limit_re" <<<"$OUT"; then
    reason="usage_limit"
elif [ "$RC" -ne 0 ]; then
    reason="exit_${RC}"
fi

if [ -z "$reason" ]; then
    echo "KEEPALIVE_OK ${now}" > "$LOG"
    exit 0
fi
echo "KEEPALIVE_FAIL:${reason} ${now}" > "$LOG"
exit 1
