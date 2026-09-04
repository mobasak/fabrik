# T03 — Epic assignment — epic_order.py --assign, owner in the schema and the mega checklist

## Scope
Add one subcommand to `scripts/epic_order.py`: `--assign <a,b,c>` takes `phased_order()`'s `list[list[int]]` (`scripts/epic_order.py:127`) and hands each phase's epics to the named agents round-robin in `epic_n` order (deterministic, balanced, no judgment), writing `owner: <name>` into each epic's frontmatter (parser `:29`, loader `:53`); it refuses to write when `check_integrity()` (`:83`) has findings. `--check --owners <a,b,c>` adds one finding class: an epic whose `owner` is missing or outside the named set. The frontmatter field `owner: ""` is documented in `EPIC-ARTIFACT-SCHEMA.md` (`:16-21` block; consumers table `:32-34` drops the `traycer_mirror.py` row). The mega checklist rows that enumerate the schema or the one-epic-at-a-time assumption are rewritten: row 48 (`:93` "one epic at a time"), 77 (`:137`), 78 (`:138`), 84a (`:153`) — epics in the same phase run concurrently, one per named agent, `owner` is a frontmatter field. The band at `02:153-155` is NOT edited here (T06b carries it into `/fabrik-epics`). DO-NOT: touch `scripts/final_gate.py` (T05 registers the optional gate check); touch `traycer_mirror.py` (T09 deletes it).

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/test_epic_order.py -q
Gate: python3 scripts/epic_order.py --help | grep -c 'assign'
Docs: docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md · EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md rows 48/77/78/84a · CHANGELOG.md · INDEX.md (new test) — orchestrator-applied

## Touches
- scripts/epic_order.py — PRIMARY PATH
- tests/test_epic_order.py
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
- docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md

## Behavior Contract
- **Given** five epics in two phases, **When** `--assign alpha,beta,gamma` runs, **Then** phase 1's epics get alpha, beta, gamma in `epic_n` order and phase 2 continues the rotation, written into each file's frontmatter (scripts/epic_order.py:127)
- **Given** the same epics, **When** `--assign` runs twice, **Then** the second run changes no byte (scripts/epic_order.py:53)
- **Given** an integrity finding, **When** `--assign` runs, **Then** no file is written and the exit code is 1 (scripts/epic_order.py:83)
- **Given** an epic with `owner: delta`, **When** `--check --owners alpha,beta,gamma` runs, **Then** a finding names the epic and the exit code is 1 (scripts/epic_order.py:83)
- **Given** an epic with no `owner` field, **When** `--check` runs without `--owners`, **Then** the result is unchanged from today (scripts/epic_order.py:160)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
