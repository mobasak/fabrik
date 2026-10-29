# T10 — Integration: the pre-merge whole-plan gates, the receipt, the merge request
Appetite: 90
Integration: true

## Scope
Owns the set's whole-plan gates on the branch `infra-3-dynamic-builders`, the receipt `docs/development/reviews/2026-10-28-plan-1-dynamic-builders-review.md`, and the ONE merge request. **Decided (plan-review pass 1, D1): the live proof is split off.** The spec's DONE condition — § Validation's live proof (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:301-304`) — needs the merged build in the hub's MAIN checkout (a pane's hooks and charters come from the target repo's own tree, and a builder worktree is cut from the base branch), and the set reaches master only through this ticket's merge request; so the live proof is the coordinator's post-merge turn, specified in the spine's § Post-merge live proof, and the plan flips to `EXECUTED` only when it passes. T10 is pre-merge only.

Steps, from the set's branch:
1. Whole-plan gates: `python3 scripts/enforcement/check_doc_sync.py --range <base>..HEAD`; `python3 scripts/enforcement/check_doc_stubs.py --range <base>..HEAD`; the cross-ticket seam suite `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py tests/test_agents_bat.py tests/test_whoami_agent.py tests/test_agent_role_hook.py tests/test_rotate_session.py tests/test_hub_write_root.py -q`; `/fabrik-docs-review` over the set's docs; `/opt/fabrik/.venv/bin/python scripts/final_gate.py --check --json` (expect `"status":"success"`; read `skipped_checks` and `advisory` — the hub's pytest leg is OFF, so the suite above is the test evidence); `python3 scripts/enforcement/check_convergence.py`. A green gate is necessary, not sufficient.
2. The whole-plan `/fabrik-review` receipt at the path above, to its coverage-adjudicated exit.
3. `python3 scripts/merge_request.py request --review docs/development/reviews/2026-10-28-plan-1-dynamic-builders-review.md --item W-b9ad80ae`, and send the `SendMessage` lines it prints.

DO-NOT: edit any code file (findings return to the owning ticket's surface through the orchestrator); launch any builder pane (the live proof is post-merge).

Depends: T04, T07, T09
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/.venv/bin/python scripts/final_gate.py --check --json
Docs: docs/FEATURES.md (the dynamic builders row), CHANGELOG.md, docs/DECISIONS.md (one row for the decisions this plan took — the spine's § Decisions for the D-row), INDEX.md — governance files, applied by the orchestrator's Deltas

## Touches
- docs/development/reviews/2026-10-28-plan-1-dynamic-builders-review.md

## Behavior Contract
- **Given** the set's branch with every ticket merged onto it, **When** the seam suite runs under `capped_run.sh`, **Then** every test passes (spec § Validation, unit list)
- **Given** the same branch, **When** `final_gate.py --check --json` runs, **Then** it reports `"status":"success"` and its `skipped_checks`/`advisory` are read into the receipt (CLAUDE.md § Completion Contract 2)
- **Given** the whole-plan `/fabrik-review` at a quiet closing round, **When** `merge_request.py request` runs with that receipt, **Then** it exits 0 and prints the merge owner's `SendMessage` line (scripts/merge_request.py:41-55)

## Context Files
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
- docs/reference/repo-coordinator-rollout.md
