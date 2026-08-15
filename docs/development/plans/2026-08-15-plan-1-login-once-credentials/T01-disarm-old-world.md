# T01 — Disarm the old world (M-pre): no automation may swap the shared credentials file

## Scope
Gate the last ungated credential-swapper in code and switch off the box-side capture automations,
so the entire migration window has exactly ZERO processes that can install or capture a pair in
`~/.claude/`. Code: `_rotate_active_account()` (`scripts/sysadmin/claude_rotate.py:403`, the
single choke point behind `run_claude()`'s usage-limit/401 retry at `:649` and `:766`) returns
`None` with a loud `PAUSED` line while `_switch_paused()` (`scripts/sysadmin/claude_rotate.py:1072`)
is true. ⚠️ Deliberate side effect, stated: `--next` also routes through
`_rotate_active_account` (`scripts/sysadmin/claude_rotate.py:766`), so the operator's manual
cycle refuses with the same PAUSED line while the marker exists — correct during migration
(nothing may swap); the runbook (T04) names `--resume-switch` as the override. `--switch <name>`
(`:748`) does NOT route through the choke point and stays usable as the explicit manual lever.
Box steps (executed by this ticket's steps, not owned files): remove the hourly
`--drift-check` crontab line (`crontab -l | grep drift-check`), remove the SessionStart
`--drift-check` hook entry from `~/.claude/settings.json` (line ~37), stop
`~/.claude/state/capture-watch.sh` if running, verify `CLAUDE_SOUND_AUTOROTATE` is still `"0"`
in the settings env, and finish with `bash scripts/dr_claude_backup.sh` (config-DR contract:
run after any Claude-config change). DO-NOT: touch `~/.claude/bin/claude-sound.sh` (operator
hard rule — its mesh legs are the successor plan's named, owned step); do not remove any
`claude_rotate.py` subcommand (retirement is the successor plan).

Depends: —
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_claude_rotate_v2.py -q
Docs: none (T04 owns the doc rewrite; CHANGELOG is orchestrator-applied)

## Touches
- scripts/sysadmin/claude_rotate.py — PRIMARY PATH (pause gate in _rotate_active_account)
- scripts/aro-wake/claude_rotate.py — byte-identical twin (cp after edit; md5 must match)
- tests/test_claude_rotate_v2.py — red-first T15 pair

## Behavior Contract
- **Given** the switch-paused marker exists, **When** `run_claude` hits a usage-limit or 401 rotation trigger, **Then** `_rotate_active_account` installs nothing and prints a PAUSED line (scripts/sysadmin/claude_rotate.py:403)
- **Given** the switch-paused marker is absent, **When** the same trigger fires, **Then** rotation behaves exactly as before (regression guard) (scripts/sysadmin/claude_rotate.py:649)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
- tests/test_claude_rotate_v2.py
