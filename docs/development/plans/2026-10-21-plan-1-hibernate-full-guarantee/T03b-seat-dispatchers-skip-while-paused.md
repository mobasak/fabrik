# T03b — Seat dispatchers skip while paused
Appetite: 60

## Scope
Implements spec § Personas (the headless row): each hub seat dispatcher checks `hibernate.py paused` (interface P) before every NEW seat — `scripts/sysadmin/claude_broker.py` in `handle()` (:149), returning a paused status and still auditing; `scripts/cloud_dispatch.py` in `_cmd_dispatch` (:1327) before any ledger write; `scripts/rivals_run.py` (synced) once in `main()` (:1368), never per call, calling the hub path only when it exists and proceeding otherwise (fail-open, no import). `scripts/claude_p_cost.py` starts nothing and is not touched (routed I17). DO-NOT: change the broker's audit format or rivals_run's synthesis.

Depends: T01
Parallel: ⚡
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_dispatchers_pause.py tests/test_claude_broker.py tests/test_cloud_dispatch.py tests/test_rivals_run.py -q
Docs: none (T06 documents the dispatchers' pause check in hooks-index.md)

Grounded at: `scripts/sysadmin/claude_broker.py:149` (`handle`), `scripts/cloud_dispatch.py:1327` (`_cmd_dispatch`), `scripts/rivals_run.py:1368` (`main`)

## Touches
- scripts/sysadmin/claude_broker.py — PRIMARY PATH
- scripts/cloud_dispatch.py
- scripts/rivals_run.py
- tests/test_dispatchers_pause.py

## Behavior Contract
- **Given** a synced launcher in a repo with no hub `hibernate.py`, **When** it runs, **Then** it proceeds as if not paused (scripts/rivals_run.py:1368; spec § Personas)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/claude_broker.py
- scripts/cloud_dispatch.py
- scripts/rivals_run.py
