# T04b — The hub commit warning, counted

## Scope
Implements spec § The delta D5 (b) and V6's warning half. `scripts/check_commit_trailers.py`: in the hub's main checkout, a commit whose resolved name (`_session_agent_name`, `scripts/check_commit_trailers.py:561`) is set and is not the merge owner (`python3 scripts/decisions.py --merge-owner`), and whose `Agent-Name` is not `kilo-pipeline`, prints an advisory and emits one kaizen event through `scripts/sysadmin/kaizen_events.py::emit` (`scripts/sysadmin/kaizen_events.py:526`), imported the way `scripts/command_run.py:1155-1166` does it — append `Path(__file__).resolve().parent / "sysadmin"` and `/opt/fabrik/scripts/sysadmin` to `sys.path`, import inside `try/except (Exception, SystemExit)` — so a missing module fails open and never blocks a commit. The check never refuses. DO-NOT: change the trailer-parse verdict or the Agent-Name mismatch advisory.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py -q
Docs: none (hooks-index row is T06b's)

## Touches
- scripts/check_commit_trailers.py — PRIMARY PATH
- scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py

## Behavior Contract
- **Given** the hub's main checkout, a resolved name that is not the merge owner, and an `Agent-Name` other than `kilo-pipeline`, **When** the commit-msg check runs, **Then** it prints the advisory, exits 0, and one kaizen event is written; a commit signed `Agent-Name: kilo-pipeline` prints nothing and writes nothing (spec § Validation V6)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- scripts/check_commit_trailers.py
- scripts/sysadmin/kaizen_events.py
