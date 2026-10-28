# T10 — Integration: the live proof, the whole-plan gates, the receipt
Appetite: 120
Integration: true

## Scope
Owns the spec's DONE condition — § Validation's live proof (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:301-304`) — and the three open unknowns it resolves (§ Open/blocking unknowns, `:425-432`), plus the set's whole-plan gates and the receipt `docs/development/reviews/2026-10-28-plan-1-dynamic-builders-review.md`.

The live proof runs in the hub's MAIN checkout after the set's branch is merged and rendered there (a worktree pane would read the branch's tree, CLAUDE.md § Merge-time render only); launching claude/tmux/wt is the executor's act at this step, run by the hub coordinator (D-874 merge owner) or the builder it hands the turn to:
1. First generation of the launcher: `python3 scripts/sysadmin/agents_bat.py --tabbed --desktop "/mnt/c/Users/user/OneDrive - Tojlo Solutions LLC/Desktop/terminal agents" --replace "All Agents (tabbed).bat"` (the folder holding today's hand-written file, read this run); the operator double-clicks it once (persona step 1).
2. Open a throwaway P3 item (`python3 scripts/work.py add …`) and `scripts/sysadmin/agents_up.sh add /opt/fabrik builder-proof1 --item <its id>`; within 3 minutes: the pane shows in the open tabbed window, the builder's `whoami_agent.py --who` prints `builder-proof1`, `work.py show <id>` shows it claimed, and `tmux capture-pane -p` of its pane contains no `Teach auto mode` and no permission dialog — with no key typed.
3. With the hub's window `agents` at four panes, `add` a fifth builder: window `agents-2` and session `fabrik-2` exist, and a second tab appears in the same Windows Terminal window (unknown `:425-428`; failing it, the regenerated `.bat` shows it at the next click and the spec's step budget records a fourth operator step — say which happened).
4. Have builder-proof1 commit one file on its branch without pushing; `agents_up.sh remove /opt/fabrik builder-proof1` exits 2 naming the unpushed branch; push; `remove` exits 0; the `.bat` is regenerated each time (its mtime moves).
5. `search_chats` (session-recall) for `builder-proof1` returns its transcript.
6. Classifier unknown (`:429-432`): if Claude Code refuses the coordinator's `agents_up.sh add`, the one exact allow rule is boarded by the coordinator as requirement 1.1's one-time operator step (a DECISION NEEDED, ground `gate` — credentials/permissions), never routed around.

Whole-plan gates (the set-shape owner of the monolith's final step): `python3 scripts/enforcement/check_doc_sync.py --range <base>..HEAD`, `python3 scripts/enforcement/check_doc_stubs.py --range <base>..HEAD`, the cross-ticket seam tests (`tests/test_agents_spawn.py`, `tests/test_agents_up.py`, `tests/test_agents_bat.py`, `tests/test_whoami_agent.py`, `tests/test_agent_role_hook.py`, `tests/test_rotate_session.py`, `tests/test_hub_write_root.py` under `capped_run.sh`), `/fabrik-docs-review` over the set's docs, `/opt/fabrik/.venv/bin/python scripts/final_gate.py --check --json` (expect `"status":"success"`; read `skipped_checks` and `advisory` — the hub's pytest leg is OFF, so the slice above is the test evidence) and `python3 scripts/enforcement/check_convergence.py`. A green gate is necessary, not sufficient: the live proof above is the DONE condition. Doc-drift fixes and command outputs flow through the orchestrator's Deltas.

DO-NOT: edit any code file (findings go back to the owning ticket's surface through the orchestrator); keep the proof builders — both are retired by step 4 or by a final `remove`.

Depends: T04, T07, T09
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/.venv/bin/python scripts/final_gate.py --check --json
Docs: docs/FEATURES.md (the dynamic builders row), CHANGELOG.md, docs/DECISIONS.md (a row for the decisions this plan took: point 9 config-first base, point 11 `agents-2` numbering, point 12 MemoryMax fallback, the `--spawned` lock condition), INDEX.md — all governance files, applied by the orchestrator's Deltas

## Touches
- docs/development/reviews/2026-10-28-plan-1-dynamic-builders-review.md

## Behavior Contract
- **Given** the merged build in the hub's main checkout, **When** the coordinator runs `agents_up.sh add /opt/fabrik builder-proof1 --item <id>`, **Then** the builder binds, claims the item and shows in the open tabbed window with no key typed and no dialog (spec § Validation, live proof)
- **Given** four builders in window `agents`, **When** a fifth is added, **Then** window `agents-2`, session `fabrik-2` and a second tab exist (spec § Validation, live proof)
- **Given** an unpushed commit on builder-proof1's branch, **When** `remove` runs, **Then** it refuses, and after the push it retires the builder, regenerating the `.bat` each time (spec § Validation, live proof)
- **Given** builder-proof1 retired, **When** session-recall searches its name, **Then** its transcript is found (spec § Validation, live proof)

## Context Files
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
- docs/reference/repo-coordinator-rollout.md
