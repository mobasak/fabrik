# T03 — Fleet-mode `--status`/tick + idle-dir keepalive

## Scope
Feature-detected fleet telemetry: when the fleet root contains ≥1 dir (`_fleet_root()` — a NEW
call-time helper honoring `CLAUDE_FLEET_ROOT`, default `~/.claude-fleet`, mirroring
`_rotate_state_dir()`'s env pattern at `scripts/sysadmin/claude_rotate.py:1064-1067` for
tmp_path-testability), `_collect_statuses` (`:985`) groups fleet dirs by account using the
identity from `assignments.json`. **Identity pinning is THIS ticket's** (the spine Interfaces
rule): a row still `"pending-login"` gets ONE profile probe with that dir's own access token —
on success the verified email is written back (the pin; never re-probed after), on failure the
row stays pending and is excluded from account grouping (shown as `pending-login` in output).
Usage: once per account with the freshest dir's token (~4 calls/tick), falling back to a
cached last-known-with-age row when no token in the account is <8h old (cache file in
`_rotate_state_dir()`); the legacy manager-accounts view remains when the fleet root is empty.
**The tick's fleet branch is REWRITTEN, not reused** (adversary finding B2 — `_tick_inner`
at `:1381-1420` is single-live-account-shaped: `live_name` from `_active_account()` matches no
fleet slug, so an unmodified tick either early-returns dead or, if a fleet row were nominated
live, could reach `_tick_switch`): in fleet mode the tick computes per-ACCOUNT utilization,
emits the ≥85% advisory Telegram per account (24h-suppressed per account), and **structurally
never calls `_pick_successor`/`_tick_switch`** (the fleet branch contains no successor logic
at all — not merely paused). Drain-mail routing: a walled account's mapped slugs resolve to
`/opt/<slug>` where that directory exists (hub role slugs `fabrik-*` → `/opt/fabrik`),
intersected with `_mailbox_repos()` (`:1105`); slugs with no repo (e.g. `cron-ci-fix`) are
skipped. New `--keepalive`: for each fleet dir whose
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
- **Given** a fleet dir whose assignments row is `pending-login` and whose own token answers the profile probe, **When** `--status` runs, **Then** the verified email is written back once and never re-probed (scripts/sysadmin/claude_rotate.py:985)
- **Given** fleet mode with an account at 96% utilization, **When** the tick runs, **Then** it emits the per-account advisory and installs nothing — the fleet branch contains no successor or switch call (scripts/sysadmin/claude_rotate.py:1381)

## Context Files
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
- .windsurf/rules/core/45-testing-strategy.md
- tests/test_claude_rotate_v2.py
