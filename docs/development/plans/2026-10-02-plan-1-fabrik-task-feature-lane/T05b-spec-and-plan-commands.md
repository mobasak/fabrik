# T05b — The spec and plan commands: size at spec time, DOWNGRADE, no false approval

## Scope
Implements spec § The delta D9 (command half) and D10 (command half). `commands/_sources/fabrik-spec.md`: Phase 0 reads the newest lane refusal for the repo whose `--file` list overlaps the brief and, if the brief has one reversible decision and no open trade-off, closes with `handoff --resume <seed> --reason "DOWNGRADE: <id> — …"` (the parser requires `--resume`, `scripts/command_run.py:2706-2713`); Phase 5 estimates the size with D-169's rule and writes `Size: small` under `Status:` (the `Profile: delta` paragraph is `:326-339`), and the `:324-325` sentence gains the small-spec exception. `commands/_sources/fabrik-plan-after-chat.md`: `:52-55` does not mint the approval row for a `Size: small` spec; the emit rule (`:210-222`) adds a required `Appetite:` line per phase/ticket.

DO NOT touch `/fabrik-spec-review`, and DO NOT change the full-profile chain (W-8fcd2eb1 owns that).

Depends: —
Parallel: ⚡
Complexity: never-route
Appetite: 45
Gate: python commands/assemble_commands.py --check && python -m pytest tests/test_command_corpus*.py -q
Docs: none

## Touches
- commands/_sources/fabrik-spec.md — PRIMARY PATH
- commands/_sources/fabrik-plan-after-chat.md

## Behavior Contract
- **Given** a lane refusal whose `--file` list overlaps a new brief with one reversible decision, **When** `/fabrik-spec` Phase 0 is read, **Then** it orders the DOWNGRADE handoff naming the refusal id and the `/fabrik-task --from-downgrade` restart (spec § The delta D9)
- **Given** a spec whose deltas estimate ≤ ~400 code lines and ≤ 5 code files, **When** `/fabrik-spec` Phase 5 is read, **Then** it writes `Size: small` and hands the spec straight to `/fabrik-plan-after-chat` (spec § The delta D10)
- **Given** a `Size: small` spec, **When** `/fabrik-plan-after-chat` reaches its approval-row step, **Then** it does not mint an approval row (spec § The delta D10)
- **Given** any plan, **When** `/fabrik-plan-after-chat`'s emit rule is read, **Then** every phase or ticket carries `Appetite: <minutes>` (spec § The delta D11)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-plan-after-chat.md
