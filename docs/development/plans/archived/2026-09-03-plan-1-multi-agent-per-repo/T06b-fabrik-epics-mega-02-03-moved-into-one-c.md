# T06b — /fabrik-epics — mega 02 + 03 moved into one corpus source; epics in a phase run concurrently

## Scope
Create `commands/_sources/fabrik-epics.md` from `02-epic-decomposition-fabrik.md` (548 lines) + `03-expand-epic-files-fabrik.md` (337 lines): decompose and write the epic files in one command, 02's checkpoint kept as its Phase gate. Rewrites: `02:77` ("One epic runs through epic-to-ticket-workflow at a time. Epics execute sequentially") → epics in the same `epic_order` phase run concurrently, one per named agent; the sanity band `02:153` ("3–7 epics is typical. ≥10 → re-examine the boundaries") and `02:155` ("the band is a signal, not a cap") stay as a SIGNAL with the operator's range written beside them — E = 3–20; a 20-epic decomposition is re-examined for layer-slicing, never re-cut by reflex (D-107); the epic template emits `owner: ""` in the typed frontmatter (`docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md:16-21` — repo-root-relative; the bare filename did not resolve); the `### Entry Point for epic-to-ticket-workflow` section (`03:224-227`) becomes `Entry point: /fabrik-spec <this file>`; `traycer_mirror` steps are deleted (the layer is retired — `status: 0|1|2` stays as the epic's own status). The two old docs are not deleted here (T12a/T12b). DO-NOT: touch `epic_order.py` (T03a owns that file) or the assembler (T07a).

⚠️ **The renderer auto-appends only ONE fragment.** `commands/assemble_commands.py:774` appends `close-feedback` and nothing else; every other fragment is substituted from an explicit `{{include:<name>}}` line (`:760`), which is why 30 of the 33 existing sources carry `{{include:run-record}}` themselves (e.g. `commands/_sources/fabrik-spec.md:8`). So this source MUST carry, verbatim on their own lines: `{{include:run-record}}`, `{{include:questionbar}}`, `{{include:grounding-rules}}` and `{{include:subagents-core}}`. Omit them and the command renders with no run record — no pinned `RUN:` line, and `check_command_corpus` (BLOCKING) flags the missing close sites. NEXT is not a fragment at all: `_emit_skill` (`:288`) injects it into the SKILL description from the assembler's NEXT map, which is T07a's edit.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: python3 -c "import sys; sys.path.insert(0,'scripts/enforcement'); import check_traycer_chain as c; h=c.scan('commands/_sources/fabrik-epics.md'); print('\n'.join(h)); sys.exit(1 if h else 0)"   # the bare check scans only its four docs/ roots until T09 — a plain invocation passes without ever reading this file
Docs: CHANGELOG.md · INDEX.md (new source) — orchestrator-applied; **the render is the merge-time step**: this ticket edits `commands/_sources/` or `commands/_fragments/`, so the merge owner runs `python3 commands/assemble_commands.py` in the MAIN master checkout (never a worktree — it PRUNES box-wide, CLAUDE.md:155) and then `--check`, BEFORE the commit. A commit that lands un-rendered is refused by the `command-corpus-check` pre-commit hook, and every other session's commit under `commands/` is refused until someone renders.

## Touches
- commands/_sources/fabrik-epics.md — PRIMARY PATH

## Behavior Contract
- **Given** a decomposition of 14 epics, **When** `/fabrik-epics` reaches its band check, **Then** it flags re-examination for layer-slicing and proceeds — it does not re-cut to ≤7 (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:153)
- **Given** an epic file is written, **When** its frontmatter is read, **Then** it carries `owner: ""` and the Entry point line names `/fabrik-spec <this file>` (docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md:224)
- **Given** the source, **When** grepped for `execute sequentially`, `epic-to-ticket-workflow`, `traycer_mirror` or `fab-mega-`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:77)
- **Given** the rendered command, **When** `check_traycer_chain.py` scans the source, **Then** it reports 0 findings (scripts/enforcement/check_traycer_chain.py:89)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md
- docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
- scripts/epic_order.py
