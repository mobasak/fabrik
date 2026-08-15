# T03 — Fleet-mode `--status`/tick + idle-dir keepalive

## Scope
Feature-detected fleet telemetry: when `~/.claude-fleet/` contains ≥1 dir, `_collect_statuses`
(`scripts/sysadmin/claude_rotate.py:985`) groups fleet dirs by account using the PINNED
identity from `assignments.json` (never a per-dir profile re-probe — the R4 rule), queries
usage once per account with the freshest dir's access token (~4 calls/tick), and falls back to
a cached last-known-with-age row when no token in the account is <8h old (cache file in
`_rotate_state_dir()`); the legacy manager-accounts view remains when the fleet root is empty.
The tick's advisory/drain legs read the same rows; drain mail routes to the repos mapped to the
walled account via `assignments.json`. New `--keepalive`: for each fleet dir whose
`.credentials.json` mtime is >7 days old, run one `claude -p ping` with that dir's env
(`CLAUDE_CONFIG_DIR`+`CLAUDE_QUOTA_HOME` set to the dir — in-place sole-owner refresh, the
youtube-proven path, NOT the retired temp-dir copy pattern), and alert on a failed ping via the
same mesh-notify invocation `scripts/sysadmin/ci_health_probe.py:140-146` uses
(`bash ~/.claude/bin/claude-sound.sh mesh-notify <sid> /opt/fabrik "<msg>"` — invoking the
sound script is sanctioned; editing it is not); plus the box step installing the weekly cron
line `20 6 * * 1 python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --keepalive >>
$HOME/.claude/keepalive.log 2>&1`. DO-NOT: no switch/install
logic anywhere in fleet mode; do not remove legacy code paths (successor plan).

Depends: T02a
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_claude_fleet.py tests/test_claude_rotate_v2.py -q
Docs: none (T04 owns the doc rewrite)

## Touches
- scripts/sysadmin/claude_rotate.py — PRIMARY PATH (fleet-mode status/tick, --keepalive)
- scripts/aro-wake/claude_rotate.py — byte-identical twin (cp after edit; md5 must match)
- tests/test_claude_fleet.py — fleet-mode + keepalive behaviors

## Behavior Contract
- **Given** a fleet root with dirs on two accounts, **When** `--status` runs, **Then** rows group by account with live quota from the freshest token and never print "parked — quota unknown" (scripts/sysadmin/claude_rotate.py:985)
- **Given** an account none of whose dirs was used in the last 8h, **When** `--status` runs, **Then** its row shows the cached last-known values with their age, marked stale
- **Given** a fleet dir whose credentials mtime is 8 days old, **When** `--keepalive` runs, **Then** exactly one ping executes with that dir's own env and a failing ping produces a mesh-notify alert
- **Given** an empty fleet root, **When** `--status` runs, **Then** the legacy manager-accounts view renders unchanged (regression guard)

## Context Files
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
- .windsurf/rules/core/45-testing-strategy.md
- tests/test_claude_rotate_v2.py
