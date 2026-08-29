#!/usr/bin/env bash
# AFTER-EDIT: scripts/sysadmin/claude_rotate.py, scripts/sysadmin/daily-digest.sh, scripts/sysadmin/proactive-check.sh, scripts/bootstrap/templates/sysadmin-cron.template
#
# Auth/quota health probe for the health monitors (daily-digest.sh, proactive-check.sh).
#
# The `claude -p ping` WARMTH ping was RETIRED under the single-key ob@ model (2026-08-30,
# vps-claude-quota-governance): a regularly-USED ob@ account needs no keep-warm completion, and that
# ping burned the very quota the governor exists to conserve. The health SIGNAL now comes from the
# FREE `claude_rotate.py --status --json` profile probe — it hits the auth/profile endpoint (proving
# the token works + the API is reachable) and spends NO completion quota. Same log contract:
#   KEEPALIVE_OK <iso8601>              — auth healthy (active account reports live quota windows)
#   KEEPALIVE_FAIL:<reason> <iso8601>   — 401_auth | probe_error
# Single-run overwrite (matches the cron's `>` redirect). No token bytes / response content written.
set -uo pipefail

LOG="${CLAUDE_KEEPALIVE_LOG:-/var/log/claude-keepalive.log}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${CLAUDE_ROTATE_PYTHON:-python3}"

now="$(date -Is)"

# FREE health signal: the status probe checks auth/profile, never a completion → no quota burned.
OUT="$(timeout 40 "$PYTHON" "$DIR/claude_rotate.py" --status --json 2>/dev/null)" || true

# Classify from the parsed payload: healthy iff the ACTIVE account reports a numeric five_hour
# utilization (the token worked + the API answered); a failed/empty/broken probe → a FAIL reason.
reason="$(printf '%s' "$OUT" | "$PYTHON" -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("probe_error"); raise SystemExit
accts = d.get("accounts") or []
active = d.get("active")
row = next((a for a in accts if active in (a.get("slugs") or [])), accts[0] if accts else None)
if not row:
    print("no_active_account"); raise SystemExit
fh = row.get("five_hour") or {}
# CRITICAL (2026-08-30 review): `--status --json` on a fleet box is a CACHE read — it makes a LIVE
# probe only when the active token is <8h fresh; otherwise (incl. when a DEAD token`s live probe
# returns None) it serves the last-known window with source="cache" + a growing age_s. A numeric
# utilization ALONE does NOT prove the token is live. So health = a numeric reading that is EITHER
# source="live" (freshly proven) OR RECENTLY cached (the */5 tick keeps the cache <~1h fresh; a dead
# token stops the cache refreshing, so age grows past the bound and we flag it). Preserves the
# retired ping`s liveness guarantee without burning a completion.
util_ok = isinstance(fh.get("utilization"), (int, float))
source = row.get("source")
age = row.get("age_s")
FRESH_S = 7200  # 2h — generous vs the 5-min status tick; a dead-token cache ages past this same-day
if not util_ok:
    print("probe_incomplete")
elif source == "live" or (isinstance(age, (int, float)) and age <= FRESH_S):
    print("")
else:
    print("stale_unproven")
' 2>/dev/null || echo probe_error)"

if [ -z "$reason" ]; then
    echo "KEEPALIVE_OK ${now}" > "$LOG"
    exit 0
fi
echo "KEEPALIVE_FAIL:${reason} ${now}" > "$LOG"
exit 1
