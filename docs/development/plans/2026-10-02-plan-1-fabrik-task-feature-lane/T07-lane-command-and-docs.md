# T07 — /fabrik-task's own text and the run-record protocol

## Scope
Implements spec § The delta D3 (the command half), D6, D7, D8 (lane note) and § Documentation landing sites. `commands/_sources/fabrik-task.md`: the design note's six fields (`commands/_sources/fabrik-task.md:56`) gain the `## Behaviours` list (≤ 7, one test each), the multi-commit build, `--design-amend`, the review flavour by surface (today `:78`), the close refusal (today recorded, `:110-111`), the UPGRADE tokens (`:113`) gain `contract`, `new-source`, `behaviours`, `appetite`, and independent slices are several runs (D6). `docs/reference/command-run-protocol.md` documents every new flag and field. The 2026-09-17 lane spec gets a SUPERSEDED-IN-PART banner naming this spec.

DO NOT restate rules the code enforces beyond one line each; the protocol doc is the reference.

Depends: T03
Parallel: ⛓️
Complexity: never-route
Appetite: 45
Gate: python commands/assemble_commands.py --check && python -m pytest tests/test_fabrik_task_source.py tests/test_command_corpus*.py -q
Docs: docs/reference/command-run-protocol.md

## Touches
- commands/_sources/fabrik-task.md — PRIMARY PATH
- docs/reference/command-run-protocol.md
- docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md
- tests/test_fabrik_task_source.py

## Behavior Contract
- **Given** the rendered `/fabrik-task`, **When** it is read, **Then** it names the Behaviours list with its cap of 7, multi-commit closes, `--design-amend`, the refusal of undeclared paths, the full review for heavy and sync surfaces, and the four new UPGRADE tokens (spec § The delta D3, D7)
- **Given** `docs/reference/command-run-protocol.md`, **When** it is read, **Then** every new flag and field (`consumers`, `--appetite`, `--why`, `--from-downgrade`, `--design-amend`, `--review`, `gate`/`lane`, `design_amends`, `loc_added`, `over_appetite`, `parent`, `size`, `over_appetite_phases`, `phase_marks`) is documented (spec § Contract deltas)
- **Given** the 2026-09-17 lane spec, **When** its header is read, **Then** it carries a SUPERSEDED-IN-PART banner pointing to this spec (spec § Documentation landing sites)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- commands/_sources/fabrik-task.md
- docs/reference/command-run-protocol.md
