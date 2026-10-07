# T07b — router: three new stems for the assembled commands

## Scope
`.claude/hooks/skill_router.py:256` `KEYWORD_STEMS` (30 tuples today, and `grep -c '\bfab-'` → 0 — it never routed the orchestrator chain at all) gains three STEMS — "vision / mega epic / product vision" → `vision`, "epics / decompose into epics / epic files" → `epics`, "epic review / cross-epic / assign epics" → `epics-review` — and **`STEM_SKILLS` (`.claude/hooks/skill_router.py:108`) gains the three matching stem → skill-name entries** (`"vision": "fabrik-vision"`, and so on). Both dicts, or nothing routes: `first_regex_match` (`:671`) returns the bare STEM and `resolve_target` (`:703`) does `STEM_SKILLS.get(stem)`, so adding only `KEYWORD_STEMS` yields `None` and the router silently never fires for the three commands. Placement matters: the router returns the FIRST match (`:671`), so the three sit ABOVE the `spec` and `plan` stems or a multi-epic prompt routes to `/fabrik-spec` instead. The hook is fleet-synced, so the stems must be correct for every project — they are, because the three commands are box-wide once rendered. SPLIT NOTE: was T07 with the assembler; the breadth check scored that pairing 8. DO-NOT: touch `commands/assemble_commands.py` (T07a).

Depends: T07a
Parallel: ⛓️
Complexity: native
Gate: python -m pytest tests/test_skill_router_hook.py -q
Gate: test "$(grep -c 'fabrik-epics-review' .claude/hooks/skill_router.py)" != 0   # RED today (0): none of the three new stems exists yet. The pytest gate above passes 164 tests today with no work done.
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- .claude/hooks/skill_router.py — PRIMARY PATH
- tests/test_skill_router_hook.py

## Behavior Contract
- **Given** the prompt "decompose this vision into epics", **When** `first_regex_match` runs, **Then** it returns the stem `epics`, and `resolve_target` maps that to `fabrik-epics` (.claude/hooks/skill_router.py:108)
- **Given** "write the product vision for a multi-epic project", **When** it runs, **Then** it returns the stem `vision`, not `spec`, and `resolve_target` maps it to `fabrik-vision` (.claude/hooks/skill_router.py:256)
- **Given** "assign the epics to the three windows", **When** it runs, **Then** it returns the stem `epics-review` and `resolve_target` maps it to `fabrik-epics-review` (.claude/hooks/skill_router.py:703)
- **Given** a prompt matching none of the three, **When** it runs, **Then** routing is unchanged from today (.claude/hooks/skill_router.py:671)

## Context Files
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
