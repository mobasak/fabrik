# T05 — Ids held until merged; the automated writers identify themselves

## Scope
Implements spec § The delta D7 (ids) and D5 (b) (automated writers), and V5, V11. `scripts/decisions.py`: `--next-id` skips live reservations (`_next_id`, `scripts/decisions.py:540-553`); a reservation is held until its id appears in the integration branch's ledger — read through `_merge_base_ids` (`scripts/decisions.py:392-421`, the ref chain `origin/HEAD`, `origin/master`, `origin/main`, `master`, `main`) — replacing the fixed `_RESERVE_TTL_DAYS` expiry (`:285`) for ids whose rows are not yet there. A reservation whose branch is abandoned stays held; the cost is a gap in the sequence, which the allocator already treats as normal. `scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh:272`: the commit signs `Agent-Name: kilo-pipeline`, and the rule at `:255` stays. `scripts/wsl_startup_hook.sh:175`: the boot hook stops running `sync_projects.py` in the main checkout. DO-NOT: change the ledger format or `--reserve-id`'s key (`:295-321`).

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/test_decisions_helper.py tests/test_automated_writers.py -q
Docs: none

## Touches
- scripts/decisions.py — PRIMARY PATH
- tests/test_decisions_helper.py
- scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh
- scripts/wsl_startup_hook.sh
- tests/test_automated_writers.py

## Behavior Contract
- **Given** one `--reserve-id` in a scratch repo (HOME redirected), **When** `--next-id` runs, **Then** it does not return the reserved id (spec § Validation V5)
- **Given** a reservation aged past 7 days whose id is on an unmerged branch's ledger and not on the main checkout branch's, **When** `--reserve-id` runs from a second worktree, **Then** it returns a different id; once the row is merged, the reservation is released (spec § Validation V5)
- **Given** the pipeline script, **When** its commit command is read, **Then** it carries `Agent-Name: kilo-pipeline`, and the boot hook no longer invokes `sync_projects.py` (spec § Validation V11)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- scripts/decisions.py
- tests/test_decisions_helper.py
- scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh
- scripts/wsl_startup_hook.sh
