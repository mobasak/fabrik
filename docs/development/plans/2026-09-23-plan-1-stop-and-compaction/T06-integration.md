# T06 — Integration: receipt, whole-plan gate + review, docs-review, the sync, V2/V3, the mail, the V4–V6 row

## Scope
Implements spec § Validation V1 (the judged half), V2 and V3, § Lifecycle Adoption and § Shape / infra (one forced sync). Owns the whole-plan receipt. DO-NOT: edit any file another ticket owns (fixes flow through the orchestrator's Deltas); run more than one forced sync.

Depends: T05
Parallel: ⛓️
Complexity: native
Integration: true
Gate: .venv/bin/python scripts/final_gate.py --check --json && python3 scripts/enforcement/check_convergence.py
Docs: CHANGELOG · `docs/STRATEGIC_BACKLOG.md` (the V4–V6 dated row; the template's duplicated § FINAL OUTPUT) · `docs/DECISIONS.md` (the EXECUTED row) — orchestrator-applied

## Touches
- docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md

## Behavior Contract
- **Given** every work ticket merged, **When** T06 runs, **Then** one forced sync after a clean `--dry-run` distributes the hook, `thread_anchor.py` and the template to every synced repo, the whole-plan `/fabrik-review` closes quiet with its receipt, and the V2/V3 results are recorded (spec § Validation)

## Steps
1. V1, judged half: from T05's backtest, draw a random 60 fires and judge them per record with three native Sonnet seats (non-deferral fires ≤ 5%); confirm ≥ 17 of the 19 premature FALSE records in `verdict-opdec.json` fire and D4 meets its § V1 target. A miss is fixed in the owning ticket's file via Deltas and the check re-run.
2. Whole-plan `/fabrik-review` over the merged diff, partitioned by file, writing `docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md`; seam tests run together.
3. `scripts/sync_enforcement_to_projects.py --dry-run`, then ONE `--force`; count the repos that received the hook, `thread_anchor.py` and the template.
4. V3 dogfood: a manual `/compact` in a hub window mid-command; the first post-compact message names the run's phase and continues; read the post-compact transcript for where the WHERE block sits (spec U2).
5. The fabrik-lib mail with the exact text of T02b's two deltas (`python scripts/mail.py send --to fabrik-lib --kind request`).
6. `/fabrik-docs-review` on the three T05 docs and both contracts.
7. The STRATEGIC_BACKLOG rows (V4–V6 on 2026-09-30 and 2026-10-07 with their commands; the template's duplicated § FINAL OUTPUT); the EXECUTED D-row; CHANGELOG — all through the private-index recipe.
8. The whole-plan gate and `check_convergence.py`; Status EXECUTED; archive the directory.

## Context Files
- docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md
