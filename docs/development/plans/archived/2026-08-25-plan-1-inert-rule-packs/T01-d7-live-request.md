# T01 — D7 requires one live request

Depends: none
Parallel: ⚡
Complexity: simple
Docs: docs/reference/rule-pack-reachability.md (the class this belongs to)
Gate: python -m pytest tests/test_execute_plan_d7.py -q && python scripts/enforcement/check_command_corpus.py

## Scope

Add a live-request requirement to `/fabrik-execute-plan`'s D7 validation (`### D7 — Final validation
+ terminal states`), so a plan shipping HTTP surface cannot reach a terminal state on green suites
alone. Pin it with a PROSE-PIN test: `check_command_corpus.py` proves five mechanical facts
(web-tool names · chain targets · script paths · trailer model · run record) and **none of them can
observe this requirement's presence** — it will pass whether or not the D7 edit says anything, so it
is the secondary gate, never the proof. The test asserts the D7 section names the live-request
requirement; that presence is the only mechanically-decidable observable a prose command file has.
DO-NOT touch the pack corpus, the matcher, or any check — those are T02/T03/T04. DO-NOT revive
transdoc's two withdrawn `final_gate` proposals (heuristic "manual API types" detection; banning e2e
mocking): the first false-positives on domain types, the second bans a legitimate technique. DO-NOT
make this a lint — the defensible core ("one unmocked test per journey") belongs in the
certification commands.

## Touches

- commands/_sources/fabrik-execute-plan.md
- tests/test_execute_plan_d7.py

## Behavior Contract

- **Given** a plan whose tickets ship HTTP surface, **When** D7 validation runs, **Then** it refuses to reach a terminal state without at least one live request/response pasted into `## Evidence` (commands/_sources/fabrik-execute-plan.md:520).
- **Given** the D7 section with its live-request clause deleted, **When** the prose-pin test runs, **Then** it fails — proving the pin observes the clause rather than the file's existence (tests/test_execute_plan_d7.py:1).

## Context Files

- commands/_sources/fabrik-execute-plan.md
- scripts/enforcement/check_command_corpus.py
