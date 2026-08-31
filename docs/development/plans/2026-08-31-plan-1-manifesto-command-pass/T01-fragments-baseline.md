# T01 — Fragments manifesto baseline (all 21 shared fragments)

## Scope
Evaluate ALL 21 shared fragments (`commands/_fragments/*.md`) against checklist item 63b's six manifesto intersections (checkable gates · ledger routing + one-way field block · rigor-scales-with-irreversibility · labeled evidence · captured disorder · most-reversible default) so fragment-level findings are fixed ONCE here and every later command ticket verifies instead of re-fixing. Read docs/reference/operating-manifesto.md IN FULL first. For each fragment: verdict per intersection (CONFORMS at path:line / FIXED at path:line / N/A because X) into the review artifact; apply minimal fixes in place. Then /fabrik-review over the changed fragments to its no-op round; `python commands/assemble_commands.py --check` green; commit explicit paths + trailers; push; render the corpus from THIS master MAIN checkout (`python commands/assemble_commands.py` — merge-time render law). DO-NOT: touch `commands/_sources/` (the per-command tickets own those); do not inject manifesto vocabulary into a fragment where an intersection is genuinely N/A — the verdict is the deliverable, not the edit.

Depends: —
Parallel: ⛓️
Complexity: native
Gate: python commands/assemble_commands.py --check
Docs: CHANGELOG.md entry via the orchestrator Deltas mechanism (command contract changed); INDEX.md row for the new review artifact (orchestrator-applied)

## Touches
- commands/_fragments/ — all 21 fragments, this ticket's exclusive write window
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T01-fragments-baseline-review.md — the ticket's 63b verdict table + review artifact

## Behavior Contract
- **Given** all 21 fragment files under `commands/_fragments/`, **When** each is evaluated against checklist item 63b's six intersections, **Then** a per-fragment verdict table (CONFORMS/FIXED/N-A per intersection) lands in the ticket's review artifact with 21/21 fragments adjudicated (commands/_fragments/run-record.md:1)
- **Given** fragment fixes applied, **When** /fabrik-review runs on the changed fragments and `python commands/assemble_commands.py --check` runs, **Then** the review converges to new: 0 and the check is green — fragment-level manifesto classes are SWEPT so command tickets verify-only (docs/reference/operating-manifesto.md:93)

## Context Files
- docs/reference/operating-manifesto.md
- docs/reference/command-evaluation-checklist.md
- commands/_fragments/run-record.md
- commands/_fragments/term-coverage.md
- commands/_fragments/term-edit.md
- commands/_fragments/close-feedback.md
- .windsurf/rules/core/40-documentation.md
