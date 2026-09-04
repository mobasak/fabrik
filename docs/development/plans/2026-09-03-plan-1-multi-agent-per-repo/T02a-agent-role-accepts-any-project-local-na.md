# T02a — agent_role accepts any project-local name, charter optional

## Scope
Relax `.claude/hooks/agent_role.py:20` `_ROLES = ("infra", "fleet", "intel")` to any name matching `[a-z0-9-]{1,32}` (`:25-26` is the gate); the charter at `docs/reference/agents/<name>.md` becomes optional — present → injected as today, absent → silent no-op, which is today's non-hub path (`:8`). The realpath containment (`:34`) and the 32 KB cut are unchanged. `CLAUDE_PROJECT_DIR` stays the root (`:28`): Claude Code pins it to the main checkout even inside a worktree, so charters live once, in main. Fleet-safe by construction — a project with no charters injects nothing. Update the hooks-index row (`docs/workstation/hooks-index.md:19`). SPLIT NOTE: this was T02 until the breadth check scored it 9 (3 areas × 5 behaviours, code+governance mix) AND the read set broke the budget at 264,036 B when the spec grew at r11; the two governance contracts' `Agent-Name` enum is T02b. DO-NOT: touch `CLAUDE.md` or `templates/governance/CLAUDE.md` (T02b).

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_agent_role_hook.py -q
Docs: docs/workstation/hooks-index.md · CHANGELOG.md — orchestrator-applied

## Touches
- .claude/hooks/agent_role.py — PRIMARY PATH
- tests/test_agent_role_hook.py
- docs/workstation/hooks-index.md

## Behavior Contract
- **Given** `CLAUDE_AGENT=alpha` and a charter at `docs/reference/agents/alpha.md`, **When** the hook runs, **Then** the charter is printed (.claude/hooks/agent_role.py:25)
- **Given** `CLAUDE_AGENT=alpha` and no charter file, **When** the hook runs, **Then** it prints nothing and exits 0 (.claude/hooks/agent_role.py:26)
- **Given** `CLAUDE_AGENT=Alpha_1`, or a 33-character name, **When** the hook runs, **Then** it prints nothing and exits 0; a 32-character name is accepted (.claude/hooks/agent_role.py:20)
- **Given** a symlinked charter escaping `docs/reference/agents/`, **When** the hook runs, **Then** it is refused exactly as today (.claude/hooks/agent_role.py:34)

## Context Files
- .windsurf/rules/core/10-python.md
