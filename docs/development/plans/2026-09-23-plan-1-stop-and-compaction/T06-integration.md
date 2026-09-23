# T06 — Integration: receipt, whole-plan gate + review, docs-review, distribution check, V1/V3, the mail, the V4–V6 row

## Scope
Implements spec § Validation V3 and records V1 (run by T03 before its commit), § Lifecycle Adoption and § Shape / infra. Distribution is NOT a separate forced sync: every merge touching a governance-sync path (`templates/governance/`, `.claude/hooks/`, `scripts/thread_anchor.py` — the files-filter in `.pre-commit-config.yaml`) is distributed at merge time by the installed post-commit hook (`scripts/governance_sync_postcommit.sh`). T06 verifies that distribution landed and that nothing is pending. Owns the whole-plan receipt. DO-NOT: edit any file another ticket owns (fixes flow through the orchestrator's Deltas); run a `--force` sync unless the dry-run shows a pending difference, and then exactly one.

Depends: T05
Parallel: ⛓️
Complexity: native
Integration: true
Gate: .venv/bin/python scripts/final_gate.py --check --json && python3 scripts/enforcement/check_convergence.py
Docs: CHANGELOG · `docs/STRATEGIC_BACKLOG.md` (the V4–V6 dated row; the template's duplicated § FINAL OUTPUT) · `docs/DECISIONS.md` (the EXECUTED row) — orchestrator-applied

## Touches
- docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md

## Behavior Contract
- **Given** every work ticket merged, **When** T06 runs, **Then** a `--dry-run` sync shows no pending difference for the hook, `thread_anchor.py` and the template in any synced repo (the per-merge post-commit sync already distributed them), the whole-plan `/fabrik-review` closes quiet with its receipt, and the V1 and V3 results are recorded (spec § Validation)

## Steps
1. V1 record: copy T03's V1 result (its backtest summary and the judged-60 verdicts) into the receipt; re-run T05's `stop_mine.py --backtest` on the merged hook and confirm it reproduces T03's per-shape counts. A divergence is a finding against T03 or T05.
2. Whole-plan `/fabrik-review` over the merged diff, partitioned by file, writing `docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md`; seam tests run together.
3. Distribution: `python3 scripts/sync_enforcement_to_projects.py --dry-run`; expect no pending hook, `thread_anchor.py` or template rows. Count the repos whose copies match HEAD (`scripts/enforcement/check_synced_unmodified.py` semantics); a pending difference gets exactly one `--force` and a re-count.
4. V3 dogfood: a manual `/compact` in a hub window mid-command; the first post-compact message names the run's phase and continues; read the post-compact transcript for where the WHERE block sits (spec U2).
5. The fabrik-lib mail with the exact text of T02b's two deltas (`python scripts/mail.py send --to fabrik-lib --kind request`, body on stdin).
6. `/fabrik-docs-review` on the three T05 docs and both contracts.
7. The STRATEGIC_BACKLOG rows (V4–V6 due 2026-09-30 and 2026-10-07, with their commands; the template's duplicated § FINAL OUTPUT); the EXECUTED D-row; CHANGELOG — all through the private-index recipe.
8. The whole-plan gate and `check_convergence.py`; Status EXECUTED; archive the directory.

## Context Files
- docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md
