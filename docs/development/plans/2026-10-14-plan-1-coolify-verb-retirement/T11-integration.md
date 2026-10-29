# T11 — Integration: the capability index, the two over-budget docs, the whole-plan gate and the receipt
Appetite: 60

## Scope
Implements `spec § Validation` V8–V10 and the last two landing sites (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:325-340`, `:285`, `:290`). `docs/CAPABILITIES.md` is REGENERATED with `scripts/generate_capability_index.py` (never hand-edited; its `:214` and `:233` rows for the two deleted scripts leave with the run) and `docs/reference/apis/EXTERNAL_SYSTEMS.md:284` (`cli.py:399 --skip-dns`) is reworded — both files sit in this ticket because each alone exceeds the per-ticket READ budget (83 KB and 537 KB; the Integration ticket is the gate's hatch for an indivisible over-budget file). Then the whole-plan steps: `python3 scripts/enforcement/check_doc_sync.py --range <base>..HEAD` + `check_doc_stubs.py --range`, V8's census and `vulture` baseline restated over the merged tree, `.venv/bin/python scripts/final_gate.py --check --json` → `"status":"success"` pasted verbatim into the receipt, `check_convergence.py`, `/fabrik-docs-review` over the touched docs, the Finish `/fabrik-review` over the whole-plan diff (file partition, Sonnet + Haiku finders per slice, the orchestrator executing every refutation — D-344, D-335), and the receipt `docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md` CONVERGED. The D-row naming the deletion commit (T09's sha, the retrieval address spec § Decisions taken promises) and the `CHANGELOG.md` `### Changed` entry are orchestrator-applied through `Docs:`. DO-NOT: edit any file another ticket owns; never hand-edit `docs/CAPABILITIES.md`.

Depends: T10a, T10b
Parallel: ⛓️
Complexity: native
Integration: true
Gate: .venv/bin/python scripts/final_gate.py --check --json && .venv/bin/python scripts/enforcement/check_convergence.py
Docs: `CHANGELOG.md` (one `### Changed` entry); `docs/DECISIONS.md` (the row naming T09's deletion commit); `INDEX.md` (the receipt's row); `docs/FEATURES.md` (confirm `:313`, `:686` landed)

## Touches
- docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md — PRIMARY PATH
- docs/CAPABILITIES.md
- docs/reference/apis/EXTERNAL_SYSTEMS.md

## Behavior Contract
- **Given** the merged tree, **When** `scripts/generate_capability_index.py` runs, **Then** `docs/CAPABILITIES.md` lists neither `health_check_autonomous.py` nor `migrate_db_rename.py` and a second run produces no diff (spec § The delta D11; V10).
- **Given** `docs/reference/apis/EXTERNAL_SYSTEMS.md:284`, **When** read, **Then** it no longer cites `cli.py:399 --skip-dns` (spec § Documentation landing sites).
- **Given** the whole-plan diff, **When** V8's census runs over the merged tree, **Then** it lists 0 files of the 981-file denominator, `vulture src/fabrik --min-confidence 80` reports 0 items, and the receipt states both numbers with the commands (spec § Validation V8).
- **Given** the receipt, **When** `check_convergence.py` and `final_gate.py --check --json` run, **Then** the gate's `"status":"success"` envelope is pasted verbatim in the receipt, the receipt is CONVERGED after the Finish review's closing pass confirms 0, and the plan's `Status:` is EXECUTED (spec § Validation V10).

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md
- scripts/generate_capability_index.py
