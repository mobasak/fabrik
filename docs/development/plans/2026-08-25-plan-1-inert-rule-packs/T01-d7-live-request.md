# T01 — D7 requires one live request

Depends: none
Parallel: ⚡
Complexity: simple
Docs: docs/reference/rule-pack-reachability.md (the class this belongs to)
Gate: python scripts/enforcement/check_command_corpus.py

## Scope

Add a live-request requirement to `/fabrik-execute-plan`'s D7 validation, so a plan shipping HTTP
surface cannot reach a terminal state on green suites alone. DO-NOT touch the pack corpus, the
matcher, or any check — those are T02/T03/T04. DO-NOT revive transdoc's two withdrawn `final_gate`
proposals (heuristic "manual API types" detection; banning e2e mocking): the first false-positives on
domain types, the second bans a legitimate technique. DO-NOT make this a lint — the defensible core
("one unmocked test per journey") belongs in the certification commands.

## Touches

- commands/_sources/fabrik-execute-plan.md

## Behavior Contract

- **Given** a plan whose tickets ship HTTP surface, **When** D7 validation runs, **Then** it refuses to reach a terminal state without at least one live request/response pasted into `## Evidence` (commands/_sources/fabrik-execute-plan.md:520).

## Context Files

- commands/_sources/fabrik-execute-plan.md
