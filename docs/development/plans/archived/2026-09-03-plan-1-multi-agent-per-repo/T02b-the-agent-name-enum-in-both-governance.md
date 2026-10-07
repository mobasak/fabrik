# T02b — the Agent-Name enum in both governance contracts

## Scope
`.claude/hooks/agent_role.py:2` (`# AFTER-EDIT: … docs/workstation/hooks-index.md, CLAUDE.md`) and `:19` (*"mirrors CLAUDE.md § Agent Provenance Trailers"*) require the hook's relaxation to reach the contract that documents it. **That is the HUB contract only — one file, not two.** `CLAUDE.md:280`'s `Agent-Name` row states `infra · fleet · intel` as the permitted set and must state the relaxed rule instead: any `[a-z0-9-]{1,32}` name, with the hub's own sessions still using the three role names. ⚠️ **`templates/governance/CLAUDE.md` is deliberately NOT touched** — an author-blind pass proved it carries no `Agent-Name` row at all (`grep -c 'Agent-Name' templates/governance/CLAUDE.md` → 0; its trailer table runs Agent-Role, Agent-Phase, Agent-Task, Agent-Context, Merged-From, Conflicts-Resolved). Agent-Name is hub-only by design, so an earlier draft's claim that the template carried a 'twin' row was false, and adding one would push a hub concept to ~46 repos that the spec never authorised. T14a edits `CLAUDE.md` too, so the Depends edge serialises the pair; commit with an explicit pathspec naming only your own line. SPLIT NOTE: split from T02 by the breadth check (score 9) and by the read budget. DO-NOT: touch the hook or its test (T02a).

Depends: T02a
Parallel: ⛓️
Complexity: native
Gate: test -z "$(git grep -n 'infra` · `fleet` · `intel' -- CLAUDE.md)" && test "$(grep -c '\[a-z0-9-\]{1,32}' CLAUDE.md)" != 0   # ONE file: the template has no Agent-Name row (verified 0 hits), so including it would let this gate pass with the real edit undone
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- CLAUDE.md — PRIMARY PATH

## Behavior Contract
- **Given** the hub contract after this ticket, **When** its `Agent-Name` row is read, **Then** it no longer states the three-value enum as the permitted set and names the `[a-z0-9-]{1,32}` rule; and `templates/governance/CLAUDE.md` is UNCHANGED, because it never carried an `Agent-Name` row (.claude/hooks/agent_role.py:19)

## Context Files
- .claude/hooks/agent_role.py
