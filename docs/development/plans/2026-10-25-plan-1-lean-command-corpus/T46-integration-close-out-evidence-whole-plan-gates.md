# T46 — Integration: close-out evidence, whole-plan gates and the review receipt
Appetite: 120

## Scope
Owns the whole-plan receipt for spec § Binding's CLOSE-OUT. The receipt tabulates every command and shared file with its baseline own-text words, its final words and its ratio, or its floor D-row; the full measure against the tooling phase's published baseline; and the evidence that L1, L2 and the standing ledger gate are live and `remove:` rows are flowing. It runs the whole-plan `check_doc_sync.py --range` and `check_doc_stubs.py --range`, `final_gate.py --check --json`, `check_convergence.py`, `/fabrik-docs-review` and the seam test `tests/test_command_rules.py`. DO-NOT: edit any command, fragment, ledger or tooling file; a defect found here goes back to the owning ticket's unit.

Depends: T45
Parallel: ⛓️
Complexity: native
Integration: true
Gate: .venv/bin/python scripts/final_gate.py --check --json — "status": "success"
Gate: python3 scripts/enforcement/check_convergence.py — exit 0
Docs: the receipt `docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-review.md`; the whole plan's Doc Sync rows are verified here and applied by the orchestrator

## Touches
- docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-review.md

## Behavior Contract
- **Given** every command and shared-file ledger merged, **When** the receipt tabulates baseline and final own-text words, **Then** each is at or under 50% or names its floor D-row (spec § Binding)
- **Given** the tooling phase's published full-measure baselines, **When** the full measure is re-run at the close, **Then** no command's full measure has grown (spec § Target)
- **Given** the merged plan, **When** `final_gate.py --check --json` and `check_convergence.py` run, **Then** both report success and the receipt embeds their output (spec § Review and landing)
- **Given** the feedback ledger after slice C merged, **When** the receipt counts close rows, **Then** it reports the `remove:` rows flowing with their `none` share (spec § Lifecycle)

## Context Files
- .windsurf/rules/core/40-documentation.md

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:503` — CLOSE-OUT: every command at or under 50% of its own text, or at a recorded floor; the full measure not grown;

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:504` — L1, L2 and the standing ledger gate live; `remove:` rows flowing.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:430` — - **Rote `remove:` answers.** After L2 lands, the `remove: none` share of all closes stays above 90% for 14

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:431` — consecutive days, which means the field is answered by rote. The source is `command-feedback.jsonl`'s `remove`

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:432` — field, and the denominator is every close row of the day.
