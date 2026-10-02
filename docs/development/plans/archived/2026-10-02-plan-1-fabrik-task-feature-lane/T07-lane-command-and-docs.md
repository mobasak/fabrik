# T07 — /fabrik-task's own text and the run-record protocol

## Scope
Implements spec § The delta D3 (the command half), D6, D7, D8 (lane note) and § Documentation landing sites. `commands/_sources/fabrik-task.md`: the design note's six fields (`commands/_sources/fabrik-task.md:56`) gain the `## Behaviours` list (≤ 7, one test each), the multi-commit build (one commit for a sync-path run), `--design-amend`, the review flavour by surface (today `:78`), the close refusal (today recorded, `:110-111`), the UPGRADE tokens (`:113`) gain `contract`, `new-source`, `behaviours`, `appetite`, and independent slices are several runs (D6). `commands/_fragments/scope-growth-exit.md` states the lane variant of the scope-growth stop in one sentence (D8). `docs/reference/command-run-protocol.md` documents every new flag (`consumers`, `--appetite`, `--why`, `--from-downgrade`, `--design-amend`, `done --commit <sha>…`, `done`/`handoff --review`, `step --appetite`) and every feedback field (`parent`, `size`, `from_downgrade`, `design_amends`, `loc_added`, `over_appetite`, `upgrade`, `upgrades`, `over_appetite_phases`, `phase_marks`) and the `gate: 2` stamp. The 2026-09-17 lane spec gets a SUPERSEDED-IN-PART banner naming this spec.

DO NOT restate rules the code enforces beyond one line each; the protocol doc is the reference.

Depends: T03b
Parallel: ⛓️
Complexity: never-route
Appetite: 45
Gate: python -m pytest tests/test_fabrik_task_source.py tests/test_check_command_corpus.py -q
Docs: docs/reference/command-run-protocol.md

## Touches
- commands/_sources/fabrik-task.md — PRIMARY PATH
- commands/_fragments/scope-growth-exit.md
- docs/reference/command-run-protocol.md
- docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md
- tests/test_fabrik_task_source.py

## Behavior Contract
- **Given** the `/fabrik-task` source, **When** it is read, **Then** it names the Behaviours list with its cap of 7, multi-commit closes and the single commit for a sync-path run, `--design-amend`, the refusal of undeclared paths, the full review for heavy and sync surfaces, and the four new UPGRADE tokens (spec § The delta D3, D7)
- **Given** `docs/reference/command-run-protocol.md`, **When** it is read, **Then** every flag and field named in this ticket's Scope is documented (spec § Contract deltas)
- **Given** the scope-growth fragment, **When** it is read, **Then** it names the lane variant and that the review still closes only on a confirmed-zero pass (spec § The delta D8; D-355)
- **Given** the 2026-09-17 lane spec, **When** its header is read, **Then** it carries a SUPERSEDED-IN-PART banner pointing to this spec (spec § Documentation landing sites)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- commands/_sources/fabrik-task.md
- docs/reference/command-run-protocol.md
- commands/_fragments/scope-growth-exit.md
