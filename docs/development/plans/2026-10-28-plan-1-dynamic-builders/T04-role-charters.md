# T04 — Charters by role: the `agent_role.py` fallback and the generic `builder.md`
Appetite: 75

## Scope
Implements spec § The delta D8 (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:239-248`), its § Contract deltas row (`:267`) and the charter reading of § Decisions taken (`:310-313`, approved by D-1306), with plan-review pass 1, A1, A3, A10-A13.

Invariants and touchpoints:
1. **When the fallback applies (A10, A11).** In `main()` (`.claude/hooks/agent_role.py:124-157`): only when `docs/reference/agents/<name>.md` is ABSENT (`os.path.lexists` false) — an existing but unmarked own file stays a silent no-op, as today, never a fallback. `<role>` = `name.rsplit("-", 1)[0]`, and only when the name contains `-` with a NON-EMPTY role and a NON-EMPTY suffix (`-x` and `infra-` have no role). Same marker check (`_has_charter_marker`, `:45-49`), the same realpath containment applied to the role path (`:129-135`), the same output with the header naming the session's own name.
2. **Never for a coordinator** — `name == "coordinator"` or `name.endswith("-coordinator")`, the grid's rule (`scripts/sysadmin/agents_up.sh:128-129`) (A12 corrects the earlier cite).
3. **Never for the merge owner's role (A3, A13).** Read exactly as the grid reads it (`scripts/sysadmin/agents_up.sh:100-109`, `:202-206`): only when `<root>/docs/DECISIONS.md` exists (no ledger declares nobody → the fallback applies); resolver = `$FABRIK_DECISIONS_PY` when set and non-empty, else the hub's literal `/opt/fabrik/scripts/decisions.py` — the hub convention (`scripts/docs_updater.py:2519-2523`, `scripts/merge_request.py:329`), so tests inject the failing, hanging and empty-output resolvers by the variable, never by editing the hub file (plan-review pass 3); never the repo's own copy (plan-review pass 2: the hook is fleet-synced, `scripts/fabrik_synced_manifest.py:279`, and runs from the repo's own tree, `.claude/settings.json:64`, so "the hook's own tree" is the downstream repo and a project's own `scripts/decisions.py` is never consulted; the same literal `.claude/hooks/final_gate_stop.py:2467` uses); run `python3 <resolver> --merge-owner <root>` with `stdin=subprocess.DEVNULL` and `timeout=5` (inside the hook's 10 s budget, `.claude/settings.json:65`, after its own ≤ 2 s stdin read). Exit 0 with a non-empty stdout → the owner, `.strip().lower()`d (`:205-206`); exit 0 with an EMPTY stdout, or exit 3 (UNDECLARED) → no owner; any other exit, a timeout, an OSError → NO fallback (fail-closed for the fallback only; the own-name path stays fail-open). `<role> == owner` → no fallback. The resolver runs only on the fallback path.
4. **Docstring** (`.claude/hooks/agent_role.py:3-19`): the fallback, its refusals, and the one read-only merge-owner query that narrows "never reads outside `docs/reference/agents/`".
5. **Census row.** The new `subprocess.run(` beside a `/opt/fabrik` literal is flagged by the write-root census (`tests/test_hub_write_root.py:478-500`, `_LITERAL_RE_SRC` at `:440`): add its `ALLOWLIST` row (`tests/test_hub_write_root.py:310-394`), reason `no-write: runs $FABRIK_DECISIONS_PY, else /opt/fabrik/scripts/decisions.py, --merge-owner read-only, only to refuse a merge owner's role-charter fallback`.
6. **`docs/reference/agents/builder.md`** (new — verified absent; first line exactly `# Agent charter — builder`). It states, each in a line or two: bind at your first turn (`whoami_agent.py --as <name> --force`); work only the item your coordinator assigned (`work.py next`; when it shows nothing, message your coordinator — never merge anything to find it); every question — design doubt, permission prompt, Claude Code UI prompt — goes to your coordinator by `SendMessage`, never to the operator (D-1301 point 2); commit and push before you are retired, and request the merge with `merge_request.py request` (which finds the repo's merge owner itself); write your resume point into the item's run seed (`command_run.py handoff|blocked`), never personal memory (spec § Intake Inventory I17); you are disposable — `agents_up.sh remove` retires you once your item closes and your queue is empty (spec D6). **Decided (A1): the template carries NO canonical merge-owner sentence** — fleet copies it into repos with other owners, so a sentence naming `coordinator` would be wrong there; it names no merger at all.
7. **The charter-set test (A1).** `test_every_charter_names_the_current_merge_owner` (`tests/test_agent_role_hook.py:621-697`) asserts `set(charters) - builders == set(mail.HUB_BEATS)` and one canonical owner sentence per charter; a marked `builder.md` fails both. Edit it: a ROLE TEMPLATE — a charter whose stem is in a module-level `ROLE_TEMPLATES = {"builder"}` in the test — is excluded from both assertions, and a new assertion checks every role template names no hub agent as merger: the `stale_shapes` scan applied to it over EVERY role, the owner included (the existing `others = [r for r in roles if r != owner]` skips the owner, which for a template is wrong — plan-review pass 2, A-N2).
8. **Orchestrator step on landing (not the coder's):** mail fleet the path `docs/reference/agents/builder.md` (`python3 scripts/mail.py send --to fabrik --to-agent fleet --kind finding --ack no`, D-035 contract) so its rollout copies it (spec D8; W-cf005f94).

DO-NOT: change `_bound_name` (`.claude/hooks/agent_role.py:84-121`), the 32 KB cap, or any existing charter file.

Depends: —
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agent_role_hook.py tests/test_hub_write_root.py -q
Docs: docs/workstation/hooks-index.md (the agent_role.py row, `docs/workstation/hooks-index.md:20`, gains the fallback and its refusals); the hook's AFTER-EDIT header (`.claude/hooks/agent_role.py:2`) names it

## Touches
- .claude/hooks/agent_role.py — PRIMARY PATH (governance-sync trigger `^\.claude/hooks/` — lane row 1)
- tests/test_agent_role_hook.py
- tests/test_hub_write_root.py
- docs/reference/agents/builder.md
- docs/workstation/hooks-index.md

## Behavior Contract
- **Given** `CLAUDE_AGENT=infra-4`, no `infra-4.md` and a marked `infra.md`, **When** the hook runs, **Then** it prints `infra.md`'s body under the `## AGENT ROLE: infra-4` header, and `builder-w1a2b` gets `builder.md`'s body (.claude/hooks/agent_role.py:124-157; spec § The delta D8)
- **Given** an UNMARKED `infra-2.md` and a marked `infra.md`, **When** the hook runs for `infra-2`, **Then** it prints nothing; with a marked `infra-2.md` it prints `infra-2.md` (spec § The delta D8; plan-review pass 1, A10)
- **Given** the names `fabrik-lib-coordinator`, `coordinator`, `-x`, `infra-` and `solo` with no own charter and marked candidate role files, **When** the hook runs for each, **Then** it prints nothing (scripts/sysadmin/agents_up.sh:128-129; plan-review pass 1, A11)
- **Given** a temp repo whose ledger declares merge owner `Lead`, a marked `lead.md`, and its own `scripts/decisions.py` printing `infra`, **When** the hook runs for `lead-2`, **Then** it prints nothing — the hub resolver decided (scripts/sysadmin/agents_up.sh:202-206; plan-review pass 1, A3; plan-review pass 2)
- **Given** a resolver that exits 1, one that hangs past the timeout, and one that exits 0 with empty output, **When** the hook falls back for `infra-4` with a marked `infra.md`, **Then** the first two print nothing and the third prints `infra.md` (plan-review pass 1, A3, A13)
- **Given** a symlinked `<role>.md` resolving outside the repo, **When** the hook falls back to it, **Then** it prints nothing (.claude/hooks/agent_role.py:129-135)
- **Given** the new `docs/reference/agents/builder.md`, **When** the charter tests run, **Then** `_has_charter_marker` accepts its first line, it is excluded from the HUB_BEATS set and the canonical-sentence count, and a template line "coordinator merges your branch" fails the edited test (tests/test_agent_role_hook.py:621-697; plan-review pass 1, A1; plan-review pass 2, A-N2)

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
