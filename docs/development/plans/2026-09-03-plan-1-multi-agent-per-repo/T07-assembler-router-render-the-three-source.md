# T07 — Assembler + router — render the three sources, delete the orchestrator-wrapper path, route the stems

## Scope
`commands/assemble_commands.py`: delete `ORCH_SOURCES` (`:101`, 17 entries), `TRAYCER_SKILLS` (`:198`), `_orch_phase_count`, `_render_orch_wrapper` (`:230`), `_emit_orch_wrappers`, the `_emit_orch_wrappers(...)` call and the `keep = source_names | set(ORCH_SOURCES)` union in `render()` (`:795-815`), and the three `_traycer-skills` loops in `check()` (`:855-885`); add `NEXT` rows (`:49`) for `fabrik-vision` ("/fabrik-epics — decompose the confirmed Vision into typed epic files"), `fabrik-epics` ("/fabrik-epics-review — prove integrity, assign owners, re-cut shared owned_paths"), `fabrik-epics-review` ("per window: /fabrik-spec docs/development/epics/<its epic>.md — the corpus chain to /fabrik-execute-plan; agent-1 in the main checkout, agents 2..N via `claude --worktree <name> -n <name>-<repo>`"); `fabrik-rivals`' NEXT gains the vision hand-off ("… or /fabrik-vision when the work is multi-epic"). `.claude/hooks/skill_router.py:256` `KEYWORD_STEMS` (30 tuples, 0 `fab-` today) gains three stems routing "vision / mega epic / product vision" → `fabrik-vision`, "epics / decompose into epics / epic files" → `fabrik-epics`, "epic review / cross-epic / assign epics" → `fabrik-epics-review`, placed so they sit above `spec` and `plan` (the router's first-match order, `:671`). The render is MERGE-TIME (CLAUDE.md:150): in the main master checkout the order is render → `--check` → commit (the `command-corpus-check` pre-commit hook refuses sources ahead of the installed corpus); the render's prune deletes the 17 `fab-*` installed skills + their `~/.claude/skills` symlinks (banner-carrying) — a render side effect, never a Touches entry. DO-NOT: touch `check_command_corpus.py` (T08); delete `docs/orchestrator/_traycer-skills/` (T09).

Depends: T06a, T06b, T06c
Parallel: ⛓️
Complexity: native
Gate: python -m pytest tests/test_assemble_orch_retired.py tests/test_skill_router_hook.py -q
Gate: python3 commands/assemble_commands.py --check
Docs: docs/reference/command-corpus-check.md (T14b) · CHANGELOG.md · INDEX.md — orchestrator-applied; the render itself is the merge-time step

## Touches
- commands/assemble_commands.py — PRIMARY PATH
- .claude/hooks/skill_router.py
- tests/test_skill_router_hook.py
- tests/test_assemble_orch_retired.py

## Behavior Contract
- **Given** the three new sources exist, **When** `assemble_commands.py` renders to a temp dir, **Then** `fabrik-vision.md`, `fabrik-epics.md`, `fabrik-epics-review.md` and their `SKILL.md` wrappers are emitted with the run-record, close-feedback and NEXT fragments, and no `fab-*` wrapper is emitted (commands/assemble_commands.py:720)
- **Given** the assembler module, **When** imported, **Then** it exposes no `ORCH_SOURCES`, `TRAYCER_SKILLS`, `_render_orch_wrapper` or `_emit_orch_wrappers` name (commands/assemble_commands.py:101)
- **Given** an installed `fab-mega-00-trigger/SKILL.md` carrying the generator banner, **When** the render runs against a temp skills dir seeded with it, **Then** the prune removes it (commands/assemble_commands.py:809)
- **Given** the prompt "decompose this vision into epics", **When** `first_regex_match` runs, **Then** it returns `fabrik-epics`; "write the product vision for a multi-epic project" returns `fabrik-vision`; "assign the epics to the three windows" returns `fabrik-epics-review` (.claude/hooks/skill_router.py:671)
- **Given** the NEXT map, **When** `_emit_skill` renders `fabrik-epics-review`, **Then** the skill description's NEXT names `/fabrik-spec docs/development/epics/<its epic>.md` per window (commands/assemble_commands.py:288)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
- tests/test_assemble_agents_dest.py
