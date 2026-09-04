# T02 — Identity — agent_role.py accepts any project-local agent name, charter optional

## Scope
Relax `.claude/hooks/agent_role.py:20` `_ROLES = ("infra", "fleet", "intel")` to any name matching `[a-z0-9-]{1,32}` (`:25-26` is the gate); the charter at `docs/reference/agents/<name>.md` becomes optional — present → injected as today, absent → silent no-op (today's non-hub path, `:8`). The realpath containment (`:32`) and the 32 KB cut are unchanged. `CLAUDE_PROJECT_DIR` stays the root (`:28`) — Claude Code pins it to the main checkout inside a worktree (spec § Identity), so charters live once. Fleet-safe by construction: a project with no charters injects nothing. Update the hooks-index row (`docs/workstation/hooks-index.md:19`) to the new rule. DO-NOT: add a new hook, or read `CLAUDE_AGENT` anywhere else.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_agent_role_hook.py -q
Docs: docs/workstation/hooks-index.md (row for agent_role.py) · CHANGELOG.md — orchestrator-applied

## Touches
- .claude/hooks/agent_role.py — PRIMARY PATH
- tests/test_agent_role_hook.py
- docs/workstation/hooks-index.md

## Behavior Contract
- **Given** `CLAUDE_AGENT=alpha` and a charter at `docs/reference/agents/alpha.md`, **When** the hook runs, **Then** the charter is printed (.claude/hooks/agent_role.py:25)
- **Given** `CLAUDE_AGENT=alpha` and no charter file, **When** the hook runs, **Then** it prints nothing and exits 0 (.claude/hooks/agent_role.py:26)
- **Given** `CLAUDE_AGENT=Alpha_1` or a 33-character name, **When** the hook runs, **Then** it prints nothing and exits 0 (.claude/hooks/agent_role.py:20)
- **Given** a symlinked charter escaping `docs/reference/agents/`, **When** the hook runs, **Then** it is refused exactly as today (.claude/hooks/agent_role.py:32)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
