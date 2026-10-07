# T06 — Integration: the scaffold seeds the PLANS markers, the fleet fire-rate proof, docs, the whole-plan gate

## Scope
Integration: true. (1) The indivisible over-budget file: `src/fabrik/scaffold.py:1436-1452` — the inline PLANS.md literal gains, below its hand table, the same `## Ownership (auto-generated)` + marker pair T02a's `--adopt` seeds, so a new repo is born with the surface; `tests/test_scaffold_doc_seeding.py` gains the red-first guard. (2) The fleet fire-rate proof (spec V4): with T03 merged, run `count_sessions_sharing` and the ownership classifier read-only over the 45 sync targets and record the table `| repo | sessions | would-fire |` in the receipt — every would-fire row must have ≥2 sessions; zero single-session repos fire. (3) Docs the set owes: `docs/reference/multi-agent-operating-model.md` § Ownership surfaces — replace the two "tail sweep" sentences (`:70`) with the adoption step, the row grammar and the two advisories; `templates/governance/CLAUDE.md` § Orient (d) (`:49`) gains one sentence: an existing repo with several windows is adopted ONCE by agent-1 with `python scripts/docs_updater.py --adopt <names>` (synced — distribute with `scripts/sync_enforcement_to_projects.py --force` after the commit; a commit-tree commit skips the post-commit hook). (4) The whole-plan receipt: cross-ticket seam run (`pytest tests/test_decisions_helper.py tests/test_docs_updater_adopt.py tests/test_docs_updater.py tests/test_session_orient_hook.py tests/test_vision_reads_work_stores.py tests/test_scaffold_doc_seeding.py -q`), `check_doc_sync.py --range` + `check_doc_stubs.py --range`, `python scripts/final_gate.py --check --json` verbatim, `check_convergence.py`, `/fabrik-docs-review` over the touched docs, then the corpus render (T05's sources) from the main checkout. DO-NOT: run `--adopt` on any repo (the adoption of real repos is the operator's word per repo, § Lifecycle); modify `--adopt`'s behaviour (T02a/T02b); delete the hand table in the scaffold literal.

Depends: T01, T03, T04, T05
Parallel: ⛓️
Complexity: native
Integration: true
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_scaffold_doc_seeding.py -q && python scripts/final_gate.py --check --json
Docs: `docs/reference/multi-agent-operating-model.md` (Touches) · `templates/governance/CLAUDE.md` (Touches, synced) · CHANGELOG + INDEX + LESSONS_LEARNT + STRATEGIC_BACKLOG rows (Deltas)

## Touches
- docs/development/reviews/2026-09-06-plan-2-multi-agent-adoption-review.md
- src/fabrik/scaffold.py
- tests/test_scaffold_doc_seeding.py
- docs/reference/multi-agent-operating-model.md
- templates/governance/CLAUDE.md

## Behavior Contract
- **Given** a fresh `_scaffold_shared` into a scratch dir, **When** it finishes, **Then** `docs/development/PLANS.md` carries the `AUTO-GENERATED:PLANS` markers below its hand table and `docs_updater.py --sync` (PROJECT_ROOT pointed at it) regenerates the block in place (src/fabrik/scaffold.py:1437)
- **Given** the 45 sync targets read-only, **When** the fire-rate proof runs, **Then** every repo the advisory would fire in has ≥2 live sessions and no single-session repo fires — recorded as a table in the receipt with its denominator (scripts/docs_updater.py:1357)
- **Given** the operating-model doc and the governance template after this ticket, **When** grepped, **Then** neither carries "tail sweep" and both name `--adopt` (docs/reference/multi-agent-operating-model.md:70)

## Context Files
- src/fabrik/scaffold.py
- tests/test_scaffold_doc_seeding.py
- docs/reference/multi-agent-operating-model.md
- templates/governance/CLAUDE.md
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
