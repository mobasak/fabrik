# T03a — epic assignment: --assign, the owner field, and the checklist rows

## Scope
⚠️ **The script is HUB-ONLY** — it is in no synced manifest list, so every consumer that runs inside a project must invoke it as `/opt/fabrik/scripts/epic_order.py` (the form `EPIC-ARTIFACT-SCHEMA.md:47` already uses). Add one subcommand to `scripts/epic_order.py`: `--assign <a,b,c>` takes `phased_order()`'s `list[list[int]]` (`scripts/epic_order.py:127`) and hands each phase's epics to the named agents round-robin in `epic_n` order (deterministic, balanced, no judgment), writing `owner: <name>` into each epic's frontmatter (parser `:29`, loader `:53`); it refuses to write when `check_integrity()` (`:83`) has findings. `--check --owners <a,b,c>` adds one finding class: an epic whose `owner` is missing or outside the named set. The frontmatter field `owner: ""` is documented in `EPIC-ARTIFACT-SCHEMA.md` (`:16-21` block; consumers table `:32-34` drops the `traycer_mirror.py` row). The mega checklist rows that enumerate the schema or the one-epic-at-a-time assumption are rewritten: row 48 (`:93` "one epic at a time"), 77 (`:137`), 78 (`:138`), 84a (`:153`) — epics in the same phase run concurrently, one per named agent, `owner` is a frontmatter field. The band at `02:153-155` is NOT edited here (T06b carries it into `/fabrik-epics`). ⚠️ **While you own these two files, strip their references to things this plan deletes** — the third author-blind pass found them unowned by anyone: `EPIC-ARTIFACT-SCHEMA.md:2,33,41,51` name `scripts/traycer_mirror.py`, which T09 DELETES (the consumers table row goes, and the three prose mentions with it), and `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md:16,38,61,63,67,142` name `epic-to-ticket-workflow`, which T10/T11 retire. This ticket merges at position 4 and T09 at 20, so write the text for the post-retirement world and let the later tickets make it true. DO-NOT: touch `scripts/final_gate.py` (T05b registers the optional gate check); touch `traycer_mirror.py` (T09 deletes it). SPLIT NOTE: this was T03 until the breadth check scored it 9 (one area, EIGHT behaviours) after spec r11 added the disjointness work; that work is T03b, which depends on this one because both edit `check_integrity`. DO-NOT: touch `scripts/final_gate.py` (T05b registers the optional gate check); touch `traycer_mirror.py` (T09 deletes it); implement the disjointness strengthening (T03b).

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
- **Given** the two `mega-epic-breakdown/` files after this ticket, **When** grepped for `traycer_mirror` or `epic-to-ticket-workflow`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md:33)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
