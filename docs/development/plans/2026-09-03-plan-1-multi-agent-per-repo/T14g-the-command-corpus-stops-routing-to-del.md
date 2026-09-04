# T14g — the command corpus stops routing to deleted chain steps

## Scope
The author-blind pass proved T14b's zero-references gate still unreachable: six tracked files match it after every other ticket runs, and one is a live ROUTING instruction. This ticket owns them. **Functional:** `commands/_sources/fabrik-conformance-review.md:11` tells the reader that "`/fab-ettw-08-implementation-validation` validates ONE epic against its decisions-lock" — a command T07a's render deletes, so the instruction routes an operator to nothing; re-point it at `/fabrik-review` + `/fabrik-conformance-review`'s own per-pair sweep, which is what replaced it. `docs/reference/command-evaluation-checklist.md:8` points at `EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md`, which T11 moves — the exact sibling of the defect T14d fixes in `review_rubric.py`. **Prose, but wrong after the retirement:** `commands/_sources/fabrik-flows.md:10` (names the ettw Core Flows stage as an alternative route), `commands/_sources/fabrik-workflow-review.md:20` (a table row describing the ettw chain as reviewable — the whole row goes), `commands/_sources/fabrik-spec.md:14` (the scale up-route's mirror of "mega-00's down-route", which must now name `/fabrik-vision`). ⚠️ **Shares `commands/_sources/fabrik-spec.md` with T04a** — serialised by the Depends edge below; commit with an explicit pathspec. Every source edited here renders in the main checkout before committing, per § Global Constraints. DO-NOT: touch `agents-fabrik.md` or the north-star (T14b), `review_rubric.py` (T14d).

Depends: T04a, T07a, T11
Parallel: ⛓️
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: test -z "$(git grep -l 'fab-ettw-\|fab-mega-0\|epic-to-ticket-workflow' -- commands/_sources/ docs/reference/command-evaluation-checklist.md)"
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- commands/_sources/fabrik-conformance-review.md — PRIMARY PATH
- commands/_sources/fabrik-flows.md
- commands/_sources/fabrik-workflow-review.md
- commands/_sources/fabrik-spec.md
- docs/reference/command-evaluation-checklist.md

## Behavior Contract
- **Given** `/fabrik-conformance-review` after this ticket, **When** its per-epic guidance is read, **Then** it names a command that exists and never `/fab-ettw-08-implementation-validation` (commands/_sources/fabrik-conformance-review.md:11)
- **Given** `docs/reference/command-evaluation-checklist.md`, **When** its checklist pointer is followed, **Then** the path resolves after T11's move (docs/reference/command-evaluation-checklist.md:8)
- **Given** the four command sources, **When** grepped for `fab-ettw-`, `fab-mega-0` or `epic-to-ticket-workflow`, **Then** the count is 0 and `assemble_commands.py --check` is clean (commands/_sources/fabrik-flows.md:10)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
