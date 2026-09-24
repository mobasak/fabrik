# T01b — the kaizen vocabulary: the `decision_block` event and `deferral` as a premature cause

## Scope
Implements spec § Contract deltas (the new `decision_block` event carrying `ground`) and keeps the premature-stop outcome metric counting the stops this plan re-labels: T03 moves today's permission stall and every DEFERRAL from `cause="promise-stall"` to `cause="deferral"`, and `PREMATURE_CAUSES` (`scripts/sysadmin/kaizen_collect_v2.py:118`, read by `scripts/sysadmin/kaizen_outcomes.py:113`) must include it or the metric silently drops them (review round 2, A-O19). Both land BEFORE the hook emits either, and are inert until it does. DO-NOT: change any other event type, cause or collector logic.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: uv run pytest tests/test_kaizen_deferral_vocabulary.py -q
Docs: CHANGELOG (Deltas) — the event-stream doc row is T05's

## Touches
- scripts/sysadmin/kaizen_events.py — PRIMARY PATH
- scripts/sysadmin/kaizen_collect_v2.py
- tests/test_kaizen_deferral_vocabulary.py

## Behavior Contract
- **Given** the kaizen modules, **When** T01b lands, **Then** `decision_block` is a registered event type and `deferral` is a premature stop cause (spec § Contract deltas; A-O19)

## Steps (the coder's order)
1. Red first, `tests/test_kaizen_deferral_vocabulary.py` (new): `"decision_block" in kaizen_events.EVENT_TYPES`; `"deferral" in kaizen_collect_v2.PREMATURE_CAUSES`; `"promise-stall"` and `"run-record"` still in it. Watch it FAIL.
2. Add `"decision_block"` to `EVENT_TYPES` (`scripts/sysadmin/kaizen_events.py:114`), so `emit()` never warns on it (`:559-560`).
3. Add `"deferral"` to `PREMATURE_CAUSES` (`scripts/sysadmin/kaizen_collect_v2.py:118`).
4. Gate green; `uv run ruff check` on the touched files; CHANGELOG line into the Deltas block.
5. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit; every finding FIXED or REFUTED.
6. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T01b`).

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/sysadmin/kaizen_events.py
- scripts/sysadmin/kaizen_collect_v2.py
