# T08 — Integration: whole-plan validation, hub adoption, the fleet announcement, the receipt

## Scope

The set's one Integration ticket (the orchestrator's receipt surface). After T07a and T07b merge:

1. **Whole-plan validation (the D7 floor).** `/fabrik-review` over the plan's cumulative diff, then the
   cross-ticket seam tests together: `tests/test_work_linked.py`, `tests/test_work_view.py`, `tests/test_work_prompt.py`,
   `tests/test_work_harvest_rules.py`, `tests/test_mail_items.py`, `tests/test_command_feedback_report.py`,
   `tests/test_next_census.py`, `tests/test_work_hook_seam.py`, `tests/test_thread_anchor.py`,
   `tests/test_work_contract_rule.py`, `tests/test_work_doc_verbs.py`, plus the parent's suites
   (`tests/test_work.py`, `tests/test_work_claims.py`, `tests/test_work_sync.py`, `tests/test_work_migrate.py`).
2. `python3 scripts/enforcement/check_doc_sync.py --range <base>..HEAD` and
   `python3 scripts/enforcement/check_doc_stubs.py --range <base>..HEAD`; `/fabrik-docs-review` over the
   five T07b docs; `.venv/bin/python scripts/final_gate.py --check --json` → `"status": "success"`;
   `python3 scripts/enforcement/check_convergence.py`.
3. **Hub adoption.** The command corpus renders from the main checkout (T04's source change); the
   governance-sync distributes `work.py`, `mail.py`, `thread_anchor.py` and the template (a plumbing
   commit is followed by a hand-run `bash scripts/governance_sync_postcommit.sh`). The V-readings on the
   hub, embedded in the receipt: V2 (`mail.py claim` then `ack` on one real hub message — the item
   appears, then closes), V3 (`work.py ready` and `ready --all` output heads), V4 (`prompt_block` timed on
   the hub), and the first V5 reading — `python3 scripts/sysadmin/next_census.py --since 7 --repo /opt/fabrik`.
   The two-week V5 reading is a work item the orchestrator creates, owned by intel, due 2026-10-09.
4. **The announcement** (spec § Lifecycle — Adoption, I16): one fleet mail (`mail.py send --broadcast
   --kind finding --ack no`) and a `SendMessage` to every live session quoting the contract sentence
   exactly as T07a merged it (read it from `CLAUDE.md`, never retyped), so the announcement and the
   contract cannot differ.

DO-NOT: any code file (a defect found here routes back to the owning ticket's surface through the orchestrator's review-fix loop).

Depends: T07a, T07b
Parallel: ⛓️
Complexity: native
Integration: true
Gate: .venv/bin/python scripts/final_gate.py --check --json
Docs: the receipt

## Touches
- docs/development/reviews/2026-09-25-plan-1-work-store-single-tracker-review.md

## Behavior Contract
- **Given** every work ticket merged, **When** the whole-plan gate and `check_convergence.py` run, **Then** both are green and the receipt embeds the verbatim `"status": "success"` block
- **Given** the hub after adoption, **When** a real message is claimed and acked with `mail.py`, **Then** the receipt shows the mail item created and then closed `done`
- **Given** the hub after adoption, **When** `next_census.py --since 7 --repo /opt/fabrik` runs, **Then** the receipt embeds its output as the first V5 reading

## Context Files
- docs/superpowers/specs/2026-09-25-work-store-single-tracker-design.md
