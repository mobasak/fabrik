# T24 — /fabrik-rivals — 63b manifesto conformance + fixes + per-command review

## Scope
Evaluate `/fabrik-rivals` against checklist item 63b (docs/reference/command-evaluation-checklist.md § Governance Chain) and fix what fails. Steps: (1) read the RENDERED command at the box path `$HOME/.claude/commands/fabrik-rivals.md` (checklist law: evaluate the RENDERED command, not the source alone) AND the source `commands/_sources/fabrik-rivals.md`; read docs/reference/operating-manifesto.md if not fresh in context. (2) Adjudicate the six 63b intersections — checkable-gate termination · ledger routing + one-way field block where the command makes/receives decisions · rigor-scales-with-irreversibility · labeled verified/assumption evidence · captured disorder (findings/lessons/feedback recorded) · most-reversible default under ambiguity — verdict per intersection (CONFORMS at path:line / FIXED at path:line / N/A because X) written into this ticket's review artifact under a heading titled `## 63b Verdict Table` — NEVER `Coverage Checklist`, which stays reserved for the /fabrik-review step's own checklist (check_review_coverage greps that heading for CLEAN/FIXED/REFUTED tokens). (3) Apply the minimal fixes to the SOURCE (never the rendered wrapper). A NEW fragment-level finding T01 did not sweep (expected rare — T01's ledger is the reference) is an ORCHESTRATOR-APPLIED edit: the dispatching session applies it directly under the plan File Scope (orchestrator carve-out), records it in THIS ticket's review artifact, and re-renders — never an in-ticket edit outside Touches. (4) /fabrik-review on this ticket's changed surface to its no-op round (per the spine Execution Discipline). (5) `python commands/assemble_commands.py --check` green; commit explicit paths + trailers (NO-POOL line); push; render from master MAIN. DO-NOT: re-litigate what check_command_corpus.py already gates (checklist § Do not re-litigate); do not inject manifesto vocabulary where an intersection is N/A; do not touch other commands' sources.

Depends: T23
Parallel: ⛓️
Complexity: native
Gate: python commands/assemble_commands.py --check
Docs: CHANGELOG.md entry via the orchestrator Deltas mechanism (command contract changed); INDEX.md row for the new review artifact (orchestrator-applied)

## Touches
- commands/_sources/fabrik-rivals.md — PRIMARY PATH
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T24-fabrik-rivals-review.md — the ticket's 63b verdict table + review artifact

## Behavior Contract
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-rivals.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-rivals.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-rivals.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)

## Context Files
- docs/development/plans/2026-08-31-plan-1-manifesto-command-pass/2026-08-31-plan-1-manifesto-command-pass.md — the spine; its Execution Discipline binds every step incl. the no-change case
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T01-fragments-baseline-review.md — T01's fragment verdict ledger (exists once T01 merges; the verify-only reference)
- commands/_sources/fabrik-rivals.md
- docs/reference/operating-manifesto.md
- docs/reference/command-evaluation-checklist.md
- .windsurf/rules/core/40-documentation.md
