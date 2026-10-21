# T03b — Seat dispatchers skip while paused
Appetite: 75

## Scope
Implements spec § Personas (the headless row) and L1's watchdog and L5's kill order for hub seats: each dispatcher checks `hibernate.py paused` (Interface P, the same fail-open rule as T03a) before every NEW seat — `scripts/sysadmin/claude_broker.py` in `handle()` (:149), returning a paused status and still auditing; `scripts/cloud_dispatch.py` in `_cmd_dispatch` (:1327) before any ledger write; `scripts/rivals_run.py` (synced) once in `main()` (:1368), never per call; and each seat it spawns carries `CLAUDE_CODE_RETRY_WATCHDOG=1` and starts with `oom_score_adj` 500 (written to `/proc/self/oom_score_adj` in a `preexec_fn`, fail-open). Not touched, with the reason: `scripts/claude_p_cost.py` starts nothing (routed I17); `scripts/ci_health_probe.py` runs a probe, not a seat; operator-initiated spawns (`scripts/sysadmin/bot.py:175`, `scripts/aro-wake/main.py:523`) run on the operator's own request. DO-NOT: change the broker's audit format or rivals_run's synthesis.

Depends: T01a
Parallel: ⚡
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_dispatchers_pause.py tests/test_claude_broker.py tests/test_cloud_dispatch.py tests/test_rivals_run.py -q
Docs: docs/workstation/cloud-dispatch.md and docs/reference/rivals-command.md (one line each naming the pause check, per their AFTER-EDIT headers)

Grounded at: `scripts/sysadmin/claude_broker.py:149` (`handle`), `scripts/cloud_dispatch.py:1327` (`_cmd_dispatch`), `scripts/rivals_run.py:1368` (`main`)

## Touches
- scripts/sysadmin/claude_broker.py — PRIMARY PATH
- scripts/cloud_dispatch.py
- scripts/rivals_run.py
- tests/test_dispatchers_pause.py
- docs/workstation/cloud-dispatch.md
- docs/reference/rivals-command.md

## Behavior Contract
- **Given** a synced launcher in a repo with no hub `hibernate.py`, **When** it runs, **Then** it proceeds as if not paused (scripts/rivals_run.py:1368; spec § Personas)
- **Given** a hub seat dispatcher, **When** it spawns a `claude -p` seat, **Then** the seat's env carries `CLAUDE_CODE_RETRY_WATCHDOG=1` and its `oom_score_adj` reads 500 (scripts/sysadmin/claude_broker.py:65; spec § Chosen approach L1, L5)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/claude_broker.py
- scripts/cloud_dispatch.py
- scripts/rivals_run.py
