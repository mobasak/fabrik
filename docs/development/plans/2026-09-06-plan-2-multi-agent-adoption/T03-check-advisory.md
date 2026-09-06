# T03 — the `--check` advisory: one line when ≥2 sessions share this checkout and ownership is incomplete

## Scope
In `scripts/docs_updater.py`, `validate_docs()` (`docs_updater.py:1357`) gains `validate_ownership_advisory() -> list[str]`: when `count_sessions_sharing(PROJECT_ROOT) >= 2` AND (`read_merge_owner()` is None OR any plan unit in the PLANS table has owner `—` with a non-terminal status OR any STRATEGIC_BACKLOG row is untagged per T02b's classifier), it returns ONE string: `ADVISORY: N sessions share this checkout and ownership is incomplete (<what: merge owner undeclared | K unowned plans | M untagged backlog rows>) — run: python scripts/docs_updater.py --adopt <name>[,<name>…]`. Prefixed `ADVISORY:` so `run_check()`'s issue list prints it but the exit code stays what the OTHER findings decide — implement by collecting it separately and printing it after the issues, never appending it to `issues` (the exit code must not change). At one session it returns nothing and reads no file beyond the `/proc` scan; in the HUB (`PROJECT_ROOT/scripts/fabrik_synced_manifest.py` exists — the hub is outside the worktree model, operating-model doc § Hub vs project) it returns nothing regardless of the count. The gate call `run_optional_check("scripts/docs_updater.py", "Documentation Drift", "--check")` at `final_gate.py:1884` DROPS stdout on exit 0 unless `advisory=True` (`final_gate.py:347-365`), so the call gains `advisory=True` — the row stays non-blocking (a warn-level check), the line becomes visible in the gate's JSON row. DO-NOT: block; add a new check file under `scripts/enforcement/`; change `validate_plans_indexed()`; change anything at `final_gate.py:1884` beyond the one keyword.

Depends: T02b
Parallel: ⛓️
Complexity: never-route
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_docs_updater_adopt.py -q -k advisory
Docs: CHANGELOG (Deltas)

## Touches
- scripts/docs_updater.py — PRIMARY PATH
- tests/test_docs_updater_adopt.py
- scripts/final_gate.py

## Behavior Contract
- **Given** a fake proc tree with two `claude` processes in the repo (`proc_root`) and a repo with no `MERGE OWNER:` row, **When** `docs_updater.py --check` runs, **Then** stdout carries exactly one `ADVISORY:` line naming `2 sessions` and `--adopt`, and the exit code equals the run's exit code with the advisory removed (scripts/docs_updater.py:1357)
- **Given** one process in the fake proc tree, or two processes but `scripts/fabrik_synced_manifest.py` present (hub identity), **When** `--check` runs, **Then** no `ADVISORY:` line is printed (scripts/docs_updater.py:1357)
- **Given** 2 sessions, a declared merge owner, every open plan owned and every backlog row tagged, **When** `--check` runs, **Then** no `ADVISORY:` line is printed — parametrized over the four combinations of (sessions ∈ {1,2}) × (ownership complete/incomplete), only (2, incomplete) prints (scripts/docs_updater.py:1066)
- **Given** the gate run on a tree where the advisory fires, **When** `final_gate.py --check --json` runs, **Then** the `Documentation Drift` row is green and its output carries the `ADVISORY:` line (scripts/final_gate.py:1884)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/docs_updater.py
- tests/test_docs_updater_adopt.py
- scripts/final_gate.py
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
