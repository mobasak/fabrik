#!/usr/bin/env bash
# AFTER-EDIT: scripts/sysadmin/proactive-check.sh, scripts/sysadmin/morning-report.sh, scripts/sysadmin/weekly-security.sh, scripts/sysadmin/monthly-backup-verify.sh
#
# Unified Claude entrypoint for ALL sysadmin scripts. A drop-in for `claude`:
#     claude-run.sh <claude-args...>
# It runs `claude` through claude_rotate.py (usage-limit auto-rotation) and ALWAYS as the
# operator account, so every caller — including the root-run cron scripts, whose own
# /root/.claude has no credentials — shares the ONE credential home /home/ozgur/.claude
# that the rotation mechanism manages. When the caller already IS the operator it runs
# directly; when it's root (or anyone else) it re-enters as the operator via
# `sudo -u <operator> -H` (root→operator sudo needs no password; -H sets HOME so `claude`
# reads the right ~/.claude). It swaps NO credential files itself — claude_rotate.py owns
# the atomic swap; this only ever passes the claude binary + args.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPERATOR="${CLAUDE_OPERATOR_USER:-ozgur}"
ROTATE="$DIR/claude_rotate.py"
PYTHON="${CLAUDE_ROTATE_PYTHON:-python3}"

# Resolve an absolute claude binary that works regardless of the caller's PATH (root's cron
# PATH is minimal). On the fleet /usr/bin/claude exists (the live keepalive uses it) and
# /usr/local/bin/claude symlinks the operator's copy.
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || true)}"
if [ -z "$CLAUDE_BIN" ]; then
    for c in /usr/local/bin/claude "/home/$OPERATOR/.local/bin/claude" /usr/bin/claude; do
        [ -x "$c" ] && { CLAUDE_BIN="$c"; break; }
    done
fi
CLAUDE_BIN="${CLAUDE_BIN:-/usr/bin/claude}"

# The sysadmin analyses run Opus on a large system prompt; the old bare `claude -p` had NO
# timeout, so give claude_rotate a generous default (matches bot.py's 300s) instead of its
# 120s so routing through rotation doesn't newly cut off a long analysis. Forward it across
# the sudo boundary with `env VAR=val` (independent of the sudoers env-reset policy, unlike
# a plain exported var which sudo would drop).
TIMEOUT="${CLAUDE_ROTATE_TIMEOUT:-300}"
# Sanitize: claude_rotate.py does int(CLAUDE_ROTATE_TIMEOUT); a non-integer OR zero would crash
# it (subprocess.run rejects timeout=0 with "timeout value must be positive"). Require a
# POSITIVE integer, else fall back to the default. Forwarding across sudo exposes this.
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || TIMEOUT=300

# Run from a cwd the OPERATOR can access. A root cron job starts in /root (mode 0700); after
# `sudo -u $OPERATOR` (which switches UID but does NOT chdir), claude_rotate.py runs claude
# with cwd=os.getcwd()=/root, and subprocess.run's os.chdir("/root") then fails with
# PermissionError as the operator → every call would crash. cd to the operator's home
# (or /tmp) first so the inherited cwd is traversable after the UID switch. ROTATE/CLAUDE_BIN
# are absolute, so this cd doesn't affect them. Final fallback is `/` (always world-traversable)
# — NOT `|| true`, which would leave the inaccessible /root cwd and reintroduce the crash.
cd "/home/$OPERATOR" 2>/dev/null || cd /tmp 2>/dev/null || cd /

if [ "$(id -un)" = "$OPERATOR" ]; then
    exec env "CLAUDE_ROTATE_TIMEOUT=$TIMEOUT" "$PYTHON" "$ROTATE" "$CLAUDE_BIN" "$@"
else
    exec sudo -u "$OPERATOR" -H env "CLAUDE_ROTATE_TIMEOUT=$TIMEOUT" "$PYTHON" "$ROTATE" "$CLAUDE_BIN" "$@"
fi
