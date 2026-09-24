# T10 — Integration: the shared `tasks/` link, hub adoption, the whole-plan receipt

## Scope

The set's single Integration ticket, LAST in Merge Order. It owns three things.

**1. The shared `tasks/` link** (spec § The native Task list: "A new symlink shares `tasks/` across
accounts, using the mechanism D-287 applies to `sessions/`"). In `scripts/sysadmin/claude_rotate.py`,
`"tasks"` joins `_SHARED_DIR_LINKS` (`scripts/sysadmin/claude_rotate.py:1431`) and `_SHARED_DIR_MKDIR`
(`:1436` — the CLI creates `tasks/` lazily, exactly the case that tuple exists for), so `_scaffold_dir`
(`:1912`, the loop at `:1929`) links it and the drift check (`:3956-3962`) names a real `tasks/`
directory where the link belongs. `tests/test_claude_fleet.py:828` pins the tuple and moves with it,
plus one test that a scaffolded fleet dir gets the `tasks` link. Both files are over the READ budget
(395 KB and 378 KB), which is why they live here — the Integration ticket's hatch for an indivisible
over-budget file.

**2. Hub adoption** (spec § Lifecycle, Adoption step 1), after T01a–T09 are merged, in this order:
1. `python3 scripts/work.py init --distributor intel` (D-395).
2. `python3 scripts/work.py migrate-backlog`, then `render`. The render rewrites the backlog's
   `AUTO-GENERATED:BACKLOG` block, and the header's stale "16 open items" line becomes one sentence
   saying the block is rendered by `work.py render` (spec § Documentation landing sites). Both land in
   `docs/STRATEGIC_BACKLOG.md`, a governance file, so this ticket returns them as a Deltas patch and
   the orchestrator applies them.
3. Two items created with `work.py add`: the V6 reading due 2026-10-08 (two weeks after adoption) —
   its `next` names the spine's § Residual unknowns linked-worktree reader as part of the reading — and
   the fleet rollout request (step 4).
4. One fabrik-mail broadcast to the fleet: `work.py` arrives by the governance sync; each repo's own
   agent runs `init --distributor <its distributor>` and `migrate-backlog` (spec § Lifecycle, step 2).
   The 9 unfilled template repos migrate to an empty store.

**3. The whole-plan receipt** `docs/development/reviews/2026-09-24-plan-2-work-tracking-review.md`:
`check_doc_sync.py --range` + `check_doc_stubs.py --range` over the plan's base..HEAD, the whole-plan
`.venv/bin/python scripts/final_gate.py --check --json` (`"status":"success"`), `check_convergence.py`,
the cross-ticket seam tests (tests/test_thread_anchor.py, tests/test_work_hook_seam.py,
tests/test_final_gate_work_row.py) green together, `/fabrik-docs-review`, and on the hub, with their
outputs pasted verbatim:
- V2: the migration count against an independent reader;
- V5: `work.py status`'s class lists against an independent reader of the hub tree;
- V1: the seam test's output.

The decoder spec's pending design approval
(`docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md`, I11) is NOT seeded by hand.
The orchestrator's closing response carries its DECISION block, so the hub's first awaiting item comes
through the same Stop path every later one will (spec § Lifecycle).

**Operator actions this plan names and does not perform** (outside the tree, or the operator's own):
- name the three hub windows so owners resolve (spec § Identity, the lock, the lease): `CLAUDE_AGENT` at launch, or, with no relaunch, `python3 scripts/whoami_agent.py --as <name>` run inside each live window (D-271 — the resolver `work.py` uses);
- per existing account, link `tasks/` by re-running `python3 scripts/sysadmin/claude_rotate.py --new-dir
  <slug> <account-email>` (resumable: it adds only what is missing), merging any real `tasks/` it
  reports by hand first;
- reload open windows so the settings `env` (T07) takes effect.

DO-NOT: any change to `work.py`, the hooks or the contracts (a defect found here goes back to its ticket's
owner as a finding and a fix commit, reviewed like any other).

Depends: T07, T08, T09
Parallel: ⛓️
Complexity: native
Integration: true
Gate: .venv/bin/python -m pytest tests/test_claude_fleet.py -q -k "shared or scaffold"
Gate: .venv/bin/python scripts/final_gate.py --check --json
Gate: python3 scripts/enforcement/check_convergence.py
Docs: docs/STRATEGIC_BACKLOG.md (the rendered block and header, via Deltas); INDEX.md and docs/README.md rows for docs/reference/work-tracking.md (orchestrator)

## Touches
- scripts/sysadmin/claude_rotate.py
- tests/test_claude_fleet.py
- .fabrik/work/
- docs/development/reviews/2026-09-24-plan-2-work-tracking-review.md

## Behavior Contract
- **Given** a scaffolded fleet dir, **When** `_scaffold_dir` runs, **Then** `tasks` is a symlink to the canonical `tasks/` like `sessions`, and a real `tasks/` directory in its place is reported, never touched (spec § The native Task list)
- **Given** the hub after adoption, **When** `work.py status` runs, **Then** each drift class lists exactly the paths an independent reader of the hub tree selects (spec § Validation V5)
- **Given** the hub after adoption, **When** the migrated items are counted, **Then** they equal the independent reader's open and resolved row counts for the pre-migration backlog (spec § Validation V2)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- docs/reference/multi-agent-operating-model.md
