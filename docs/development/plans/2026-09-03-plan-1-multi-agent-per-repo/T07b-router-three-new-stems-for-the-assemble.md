# T07b — router: three new stems for the assembled commands

## Scope
`.claude/hooks/skill_router.py:256` `KEYWORD_STEMS` (30 tuples today, and `grep -c '\bfab-'` → 0 — it never routed the orchestrator chain at all) gains three stems: "vision / mega epic / product vision" → `fabrik-vision`, "epics / decompose into epics / epic files" → `fabrik-epics`, "epic review / cross-epic / assign epics" → `fabrik-epics-review`. Placement matters: the router returns the FIRST match (`:671`), so the three sit ABOVE the `spec` and `plan` stems or a multi-epic prompt routes to `/fabrik-spec` instead. The hook is fleet-synced, so the stems must be correct for every project — they are, because the three commands are box-wide once rendered. SPLIT NOTE: was T07 with the assembler; the breadth check scored that pairing 8. DO-NOT: touch `commands/assemble_commands.py` (T07a).

Depends: T07a
Parallel: ⛓️
Complexity: native
Gate: python -m pytest tests/test_skill_router_hook.py -q
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- .claude/hooks/skill_router.py — PRIMARY PATH
- tests/test_skill_router_hook.py

## Behavior Contract
- **Given** the prompt "decompose this vision into epics", **When** `first_regex_match` runs, **Then** it returns `fabrik-epics` (.claude/hooks/skill_router.py:671)
- **Given** "write the product vision for a multi-epic project", **When** it runs, **Then** it returns `fabrik-vision`, not `spec` (.claude/hooks/skill_router.py:256)
- **Given** "assign the epics to the three windows", **When** it runs, **Then** it returns `fabrik-epics-review` (.claude/hooks/skill_router.py:671)
- **Given** a prompt matching none of the three, **When** it runs, **Then** routing is unchanged from today (.claude/hooks/skill_router.py:671)

## Context Files
- .windsurf/rules/core/10-python.md
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
