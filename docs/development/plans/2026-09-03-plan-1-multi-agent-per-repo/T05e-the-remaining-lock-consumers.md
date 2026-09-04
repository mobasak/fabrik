# T05e — the remaining lock consumers: cert coverage, the manifest, the tests

## Scope
Resolve the directory with the SAME four-line snippet in every consumer — there is no shared helper and there cannot be one (`scripts/enforcement/` is synced dependency-free; `.claude/hooks/final_gate_stop.py` is a standalone synced hook that cannot import it). Census re-derived 2026-09-04: **55** tracked files match `\.fabrik/plan-locks`, **69** match the broader `-e plan-locks -e plan_locks` — the slash form is a bounded search that misses every componentwise consumer. **This ticket owns the tail — five code consumers and two files the first draft missed entirely:**
1. **`scripts/enforcement/check_phase_tests.py:36`** `LOCK_DIR = PROJECT_ROOT / ".fabrik" / "plan-locks"` — componentwise, so no slash-grep census found it. `_active_locks()` (`:44`) returns `[]` when the directory is absent, so after the move the WHOLE phase-tests gate passes silently for every plan: a fleet-synced check reduced to a no-op with nothing red. This is the ticket's primary path.
2. **`scripts/enforcement/check_certification_coverage.py`** — the functional site is the constant **`FORBIDDEN_LOCK_DIR`** (`:59` today, cited BY SYMBOL per § Global Constraints) consumed at `:237` `root.joinpath(*FORBIDDEN_LOCK_DIR)`; `:257` is only the f-string inside the `Finding`. Leaving the constant makes the anti-mix-up detector scan a directory that no longer holds plan locks — a BLOCKING check quietly reduced to nothing while a message-only edit reports green. While in the file, correct its message's stale citation of `final_gate_stop.py:785` (the line is `:864`; cite `_midrun_marker` by symbol), and the same stale anchor in `tests/enforcement/test_certification_coverage.py:176`.
3. **`tests/test_check_certification_coverage.py:47`** builds its fixture at `tmp_path / ".fabrik" / "plan-locks"` and drives `test_a_cert_lock_in_the_plan_lock_dir_also_blocks` — a different file from `tests/enforcement/test_certification_coverage.py`, and a guaranteed red if it is not moved with the constant.
4. **`scripts/fabrik_synced_manifest.py:258`** — the `".fabrik/plan-locks/*-salvage-*.diff"` gitignore leg must be **DELETED, not re-pointed**: the new directory is outside every repo and `.gitignore` patterns are repo-relative, so there is nothing to point at. The hub's own copy at `.gitignore:211` goes with it.
5. `scripts/final_gate.py:1153` names the old path in a comment — **handed to T05b**, which already owns that file: carrying a 123 KB file into this ticket for one comment blew the read budget (337,981 B against 262,144), and the cheaper, correct move is for the file's owner to fix its own line.
6. The remaining assertions in `tests/enforcement/test_phase_tests_gate.py` (22 hits), `tests/enforcement/test_plan_lock_release.py`, `tests/enforcement/test_certification_coverage.py`, and `docs/reference/plan-lock-lifecycle.md` (3 hits).
⚠️ **Shares `scripts/fabrik_synced_manifest.py` with T01a** — serialised by the Depends edge. DO-NOT: touch the hook (T05c), `check_plan_tickets.py` (T05d) or `final_gate.py` at all (T05b).

Depends: T01a, T05d
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_phase_tests_gate.py tests/enforcement/test_plan_lock_release.py tests/enforcement/test_certification_coverage.py tests/test_check_certification_coverage.py -q
Gate: test -z "$(git grep -lE '\.fabrik/plan-locks|\"\.fabrik\"\s*/\s*\"plan-locks\"|\(\"\.fabrik\", \"plan-locks\"\)' -- '*.py' '*.sh')"   # BOTH forms, repo-wide — the slash-only pattern missed three breaking consumers
Docs: docs/reference/plan-lock-lifecycle.md · templates/governance/CLAUDE.md's lock-path sentence is T14a's · CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_phase_tests.py — PRIMARY PATH
- scripts/enforcement/check_certification_coverage.py
- tests/test_check_certification_coverage.py
- .gitignore
- scripts/fabrik_synced_manifest.py
- tests/enforcement/test_phase_tests_gate.py
- tests/enforcement/test_plan_lock_release.py
- tests/enforcement/test_certification_coverage.py
- docs/reference/plan-lock-lifecycle.md

## Behavior Contract
- **Given** a plan lock in the new directory, **When** `check_phase_tests` runs, **Then** it enumerates that lock — proving the gate did not silently degrade to `[]` for every plan (scripts/enforcement/check_phase_tests.py:44)
- **Given** a cert lock and a plan lock in the new directory, **When** `check_certification_coverage` runs, **Then** it still tells them apart, driven by the relocated `FORBIDDEN_LOCK_DIR` constant rather than by its message text (scripts/enforcement/check_certification_coverage.py:59)
- **Given** the manifest's gitignore legs, **When** rendered, **Then** the salvage-diff leg is REMOVED — the new directory is outside every repo, so a repo-relative ignore pattern cannot address it — and no project ignores a path that no longer exists (scripts/fabrik_synced_manifest.py:258)
- **Given** the whole repo after this ticket, **When** `git grep -l '.fabrik/plan-locks' -- '*.py' '*.sh'` runs, **Then** it prints nothing (scripts/enforcement/check_phase_tests.py:36)

## Context Files
- .windsurf/rules/core/10-python.md
