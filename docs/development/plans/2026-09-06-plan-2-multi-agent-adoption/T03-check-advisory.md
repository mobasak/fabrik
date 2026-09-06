# T03 — the `--check` advisory: one line when ≥2 sessions share this checkout and ownership is incomplete

## Scope
In `scripts/docs_updater.py`, `validate_docs()` (`docs_updater.py:1357`) gains `validate_ownership_advisory() -> list[str]`: when `count_sessions_sharing(PROJECT_ROOT) >= 2` AND (`read_merge_owner()` is None OR any plan unit in the PLANS table has owner `—` with a non-terminal status OR any STRATEGIC_BACKLOG row is untagged per T02b's classifier), it returns ONE string: `ADVISORY: N sessions share this checkout and ownership is incomplete (<what: merge owner undeclared | K unowned plans | M untagged backlog rows>) — run: python scripts/docs_updater.py --adopt <name>[,<name>…]`. Prefixed `ADVISORY:` so `run_check()`'s issue list prints it but the exit code stays what the OTHER findings decide — implement by collecting it separately and printing it after the issues, never appending it to `issues` (the exit code must not change). At one session it returns nothing and reads no file beyond the `/proc` scan. The gate path is already advisory (`final_gate.py:1884`, `run_optional_check`). DO-NOT: block; add a new check file under `scripts/enforcement/`; change `validate_plans_indexed()`.

Depends: T02b
Parallel: ⛓️
Complexity: simple
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_docs_updater_adopt.py -q -k advisory
Docs: CHANGELOG (Deltas)

## Touches
- scripts/docs_updater.py — PRIMARY PATH
- tests/test_docs_updater_adopt.py

## Behavior Contract
- **Given** `count_sessions_sharing` monkeypatched to 2 and a repo with no `MERGE OWNER:` row, **When** `docs_updater.py --check` runs, **Then** stdout carries exactly one `ADVISORY:` line naming `2 sessions` and `--adopt`, and the exit code equals the run's exit code with the advisory removed (scripts/docs_updater.py:1357)
- **Given** the session count monkeypatched to 1 in the same repo, **When** `--check` runs, **Then** no `ADVISORY:` line is printed (scripts/docs_updater.py:1357)
- **Given** 2 sessions, a declared merge owner, every open plan owned and every backlog row tagged, **When** `--check` runs, **Then** no `ADVISORY:` line is printed — parametrized over the four combinations of (sessions ∈ {1,2}) × (ownership complete/incomplete), only (2, incomplete) prints (scripts/docs_updater.py:1066)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/docs_updater.py
- tests/test_docs_updater_adopt.py
- scripts/final_gate.py
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
