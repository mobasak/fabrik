# T02b — the Agent-Name enum in both governance contracts

## Scope
`.claude/hooks/agent_role.py:2` (`# AFTER-EDIT: … docs/workstation/hooks-index.md, CLAUDE.md`) and `:19` (*"edit all three together"*) require the hook's relaxation to reach the contracts that document it. The `Agent-Name` row in the hub `CLAUDE.md` § Agent Provenance Trailers and its twin in `templates/governance/CLAUDE.md` both state `infra · fleet · intel` as the permitted set; after T02a that is wrong in every project. State the relaxed rule instead: any `[a-z0-9-]{1,32}` name, hub sessions still using the three role names. ⚠️ `templates/governance/CLAUDE.md` distributes to ~46 repos on commit, and **T14a edits both files too** — the Depends edge serialises them; commit with an explicit pathspec naming only your own lines. SPLIT NOTE: split from T02 by the breadth check (score 9) and by the read budget. DO-NOT: touch the hook or its test (T02a).

Depends: T02a
Parallel: ⛓️
Complexity: native
Gate: test -z "$(git grep -n 'infra` · `fleet` · `intel' -- CLAUDE.md templates/governance/CLAUDE.md)"
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- CLAUDE.md — PRIMARY PATH
- templates/governance/CLAUDE.md

## Behavior Contract
- **Given** both governance contracts after this ticket, **When** their `Agent-Name` rows are read, **Then** neither states the three-value enum as the permitted set, and both name the `[a-z0-9-]{1,32}` rule (.claude/hooks/agent_role.py:19)

## Context Files
- .claude/hooks/agent_role.py
