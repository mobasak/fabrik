# T07a — assembler: render the three sources, delete the orchestrator-wrapper path

## Scope
`commands/assemble_commands.py`: delete `ORCH_SOURCES` (`:101`, 17 entries), `TRAYCER_SKILLS` (`:198`), `_orch_phase_count`, `_render_orch_wrapper` (`:230`), `_emit_orch_wrappers`, the `_emit_orch_wrappers(...)` call and **every** live `ORCH_SOURCES` reference — enumerate them with `grep -n 'ORCH_SOURCES'` rather than by range, because two sit OUTSIDE the obvious block and a partial delete leaves a `NameError` on every render: `:792` `collisions = source_names & set(ORCH_SOURCES)` with its error text at `:797`, `:810` the `keep` union, `:855` and `:870-873` the tracked-wrapper loops in `check()`, and `:877` `src_names = … | set(ORCH_SOURCES)`, which is the ORPHAN-DETECTION union rather than a `_traycer-skills` loop. The render-time uses at `:237`, `:241`, `:260` and `:277` go with `_render_orch_wrapper` and `_emit_orch_wrappers` themselves. Add `NEXT` rows (`:49`) for `fabrik-vision` ("/fabrik-epics — decompose the confirmed Vision into typed epic files"), `fabrik-epics` ("/fabrik-epics-review — prove integrity, assign owners, re-cut shared owned_paths") and `fabrik-epics-review` ("per window: /fabrik-spec docs/development/epics/<its epic>.md — the corpus chain to /fabrik-execute-plan; agent-1 in the main checkout, agents 2..N via `claude --worktree <name> -n <name>-<repo>`"); `fabrik-rivals`' NEXT gains "… or /fabrik-vision when the work is multi-epic". The render is MERGE-TIME (`CLAUDE.md:155`): in the main master checkout the order is render → `--check` → commit, because the `command-corpus-check` pre-commit hook refuses sources ahead of the installed corpus. The prune deletes the 17 installed `fab-*` skills and their `~/.claude/skills` symlinks once the names leave the keep-set — a render side effect, never a Touches entry. SPLIT NOTE: was T07 until the breadth check scored it 8 (assembler + router, code+governance mix); the router half is T07b. DO-NOT: touch `.claude/hooks/skill_router.py` (T07b); touch `check_command_corpus.py` (T08a) or delete the wrapper tree (T09).

Depends: T06a, T06b, T06c
Parallel: ⛓️
Complexity: native
Gate: python -m pytest tests/test_assemble_orch_retired.py -q
Gate: python3 commands/assemble_commands.py --check
Docs: CHANGELOG.md · INDEX.md — orchestrator-applied; the render itself is the merge-time step

## Touches
- commands/assemble_commands.py — PRIMARY PATH
- tests/test_assemble_orch_retired.py

## Behavior Contract
- **Given** the three new sources exist, **When** the assembler renders to a temp dir, **Then** `fabrik-vision.md`, `fabrik-epics.md` and `fabrik-epics-review.md` and their `SKILL.md` wrappers are emitted with the run-record, close-feedback and NEXT fragments, and no `fab-*` wrapper is emitted (commands/assemble_commands.py:720)
- **Given** the assembler module, **When** imported, **Then** it exposes no `ORCH_SOURCES`, `TRAYCER_SKILLS`, `_render_orch_wrapper` or `_emit_orch_wrappers` name, and `grep -c 'ORCH_SOURCES' commands/assemble_commands.py` prints 0 — no surviving reference to raise `NameError` at render time (commands/assemble_commands.py:877)
- **Given** `commands/assemble_commands.py` after this ticket, **When** `git grep -c '_traycer-skills\|fab-mega-0\|fab-ettw-\|epic-to-ticket-workflow' -- commands/assemble_commands.py` runs, **Then** it returns 0 — the file carries the tokens at five lines today (`:95`, `:198`, `:276`, `:803`, `:859`), and pinning only `ORCH_SOURCES` to 0 would leave T14b's strict allowlist gate unreachable (commands/assemble_commands.py:95)
- **Given** an installed `fab-mega-00-trigger/SKILL.md` carrying the generator banner, **When** the render runs against a temp skills dir seeded with it, **Then** the prune removes it (commands/assemble_commands.py:809)
- **Given** the NEXT map, **When** `_emit_skill` renders `fabrik-epics-review`, **Then** the skill description's NEXT names `/fabrik-spec docs/development/epics/<its epic>.md` per window (commands/assemble_commands.py:288)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
