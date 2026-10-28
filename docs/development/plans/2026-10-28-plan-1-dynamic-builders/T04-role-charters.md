# T04 — Charters by role: the `agent_role.py` fallback and the generic `builder.md`
Appetite: 60

## Scope
Implements spec § The delta D8 (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:239-248`) and its § Contract deltas row (`:267`), and the spec's charter reading recorded in § Decisions taken (`:310-313`, approved by D-1306).

1. **The fallback, in `main()` (`.claude/hooks/agent_role.py:124-157`).** When `docs/reference/agents/<name>.md` is absent or unmarked, and only then, try `docs/reference/agents/<role>.md`, `<role>` = the name with its last `-<suffix>` removed (`name.rsplit("-", 1)[0]`; a name with no `-` has no role). Same marker check (`_has_charter_marker`, `:45-49`), same realpath containment (`:129-135`, applied to the role path too), same output, the header line still naming the session's own name. NEVER for a coordinator name (`name == "coordinator"` or `name.endswith("-coordinator")`, the grid's rule, `scripts/sysadmin/agents_up.sh:128-129`), and never when `<role>` is the repo's declared merge owner (the grid treats that name as the coordinator, `scripts/sysadmin/agents_up.sh:202-210`). The merge owner is read the way the grid reads it (`scripts/sysadmin/agents_up.sh:100-109`): `python3 <decisions.py> --merge-owner <root>` with a 5 s timeout, `<decisions.py>` = `<root>/scripts/decisions.py` when present, else the hub's `/opt/fabrik/scripts/decisions.py`; only when `<root>/docs/DECISIONS.md` exists (no ledger declares nobody). **Fail-closed for the fallback only:** an exit other than 0 (a name) or 3 (UNDECLARED), a timeout, or a missing resolver means no role fallback (the own-name charter path is unchanged and stays fail-open). The resolver runs only on the fallback path, so a session with its own charter never pays for it.
2. **The docstring** (`.claude/hooks/agent_role.py:3-19`) gains the fallback and its two refusals, and its "never reads outside `docs/reference/agents/`" claim is narrowed to name the one read-only merge-owner query.
3. **The census row.** The hook gains a `subprocess.run(` beside a `/opt/fabrik` literal, which the write-root census flags (`tests/test_hub_write_root.py:478-500`, `_LITERAL_RE_SRC` at `:440`): add its `ALLOWLIST` row (`tests/test_hub_write_root.py:310-394`) with the reason `no-write: runs /opt/fabrik/scripts/decisions.py --merge-owner read-only, only to refuse a merge owner's role-charter fallback`.
4. **`docs/reference/agents/builder.md`** (new — verified absent this run; first line exactly `# Agent charter — builder`): the generic builder charter every `<anything>-<suffix>` spawned with `--role builder` inherits. It states, each in one or two lines: bind at your first turn (`whoami_agent.py --as <name> --force`); work only the item your coordinator assigned (`work.py next`); every question — a design doubt, a permission prompt, a Claude Code UI prompt — goes to your coordinator by `SendMessage`, never to the operator (D-1301 point 2); commit and push before you are retired, and request the merge with `merge_request.py request`; write your resume point into the item's run seed (`command_run.py handoff|blocked`), never into personal memory (spec § Intake Inventory I17); you are disposable — `agents_up.sh remove` retires you once your item closes and your queue is empty (spec D6).
5. **Orchestrator step on landing (not the coder's):** mail fleet the path `docs/reference/agents/builder.md` (`python3 scripts/mail.py send --to fabrik --to-agent fleet --kind finding --ack no`, D-035 contract) so its rollout pass copies it into each repo (spec D8, "agreed by message today"; W-cf005f94).

DO-NOT: change the env/binding name resolution (`_bound_name`, `.claude/hooks/agent_role.py:84-121`), the 32 KB cap, or any existing charter file.

Depends: —
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agent_role_hook.py tests/test_hub_write_root.py -q
Docs: docs/workstation/hooks-index.md (the agent_role.py row, `docs/workstation/hooks-index.md:20`, gains the role fallback and its two refusals); the hook's AFTER-EDIT header (`.claude/hooks/agent_role.py:2`) names it and `docs/reference/agents/`

## Touches
- .claude/hooks/agent_role.py — PRIMARY PATH (governance-sync trigger `^\.claude/hooks/` — lane row 1)
- tests/test_agent_role_hook.py
- tests/test_hub_write_root.py
- docs/reference/agents/builder.md
- docs/workstation/hooks-index.md

## Behavior Contract
- **Given** `CLAUDE_AGENT=infra-4` and only a marked `infra.md`, **When** the hook runs, **Then** it prints `infra.md`'s body under the `## AGENT ROLE: infra-4` header (.claude/hooks/agent_role.py:124-157; spec § The delta D8)
- **Given** `CLAUDE_AGENT=builder-w1a2b` and the marked `builder.md`, **When** the hook runs, **Then** it prints `builder.md`'s body (spec § The delta D8)
- **Given** both a marked `infra-2.md` and a marked `infra.md`, **When** the hook runs for `infra-2`, **Then** it prints `infra-2.md`, never `infra.md` (spec § The delta D8)
- **Given** `fabrik-lib-coordinator` with a marked `fabrik-lib.md` and no own charter, **When** the hook runs, **Then** it prints nothing (.claude/hooks/agent_role.py:127-128; spec § The delta D8)
- **Given** a ledger declaring merge owner `lead` and a marked `lead.md`, **When** the hook runs for `lead-2`, **Then** it prints nothing, and with the resolver failing it also prints nothing (scripts/sysadmin/agents_up.sh:202-210)
- **Given** a symlinked `<role>.md` resolving outside the repo, **When** the hook falls back to it, **Then** it prints nothing (.claude/hooks/agent_role.py:129-135)
- **Given** a name with no `-` and no own charter, **When** the hook runs, **Then** it prints nothing (spec § The delta D8)
- **Given** the new `docs/reference/agents/builder.md`, **When** its first line is read, **Then** `_has_charter_marker` accepts it (.claude/hooks/agent_role.py:45-49)

## Context Files
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/45-testing-strategy.md
- .claude/hooks/agent_role.py
- tests/test_agent_role_hook.py
- tests/test_hub_write_root.py
- docs/workstation/hooks-index.md
- docs/reference/agents/infra.md
- docs/reference/agents/coordinator.md
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
