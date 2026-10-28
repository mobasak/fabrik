# T08b — `agents_spawn.py add`, part 2: cold start, the second headroom measure, the launch
Appetite: 90

## Scope
Wires `add`'s steps (3) and (6) in `scripts/sysadmin/agents_spawn.py`: spec § The delta D2 steps (3), (6) (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:108-109`, `:128`), D4's cold start (`:164-174`), D1's single pane-command path (`:89-93`), with two spec CORRECTIONS from W-14219e6f implemented as stated here, and plan-review pass 1, C4.

Invariants and touchpoints:
1. **Point 1 — the cold-start pane never precedes its UUID.** Step (3) runs `agents_up.sh --detach <root>` (T03's factored start) only when `tmux has-session -t =<S>` fails. Exit 0: every registered builder is back and the new one is placed at step (6) like any spawn. Exit 3 (no builder, T02): nothing starts; steps (4)-(5) record the new builder (T06); step (6) runs `agents_up.sh --detach <root>` AGAIN, which now resolves it (binding and worktree exist, no transcript → T02 launches `--session-id` with the first prompt) and makes the grid with it as the first pane — so step (6) is then DONE and `place_pane` is skipped (plan-review pass 2, C-N3). Any other code stops `add` at step 3 with its stderr.
2. **Point 7 — headroom after the cold start (panel PF4: after it SETTLES).** After step (3) exits 0, `add` waits until every restored pane's status reads `running` (T02's `status_of`, via `agents_up.sh --print`) or `FABRIK_AGENTS_SETTLE_S` seconds (default 20) elapse; `headroom_bytes()` (T06) is then measured again and immediately BEFORE step (6)'s launch; under 2 GB → exit 2, said, one `agents-spawn.jsonl` row, steps (1)-(5) left in place for a re-run (a reboot's empty slice passes the preflight; the grid step 3 restored may have used the room).
4. **Prompt facts and registry healing (panel PO1, PO2, PF3).** `--pane-cmd` gets `--coordinator <T06's caller name>` and, when `add` got `--item`, `--item <W-id>`; the no-builder branch's second `--detach` gets the same through `FABRIK_SPAWN_NAME`/`FABRIK_SPAWN_COORDINATOR`/`FABRIK_SPAWN_ITEM` (T02). After the adoption walk (T08a), `heal_registry(root, panes)` re-points any `.fabrik/session-agents.json` row whose session id differs from the `--session-id`/`--resume` id in the live pane's claude argv for that name (atomic replace, under the agents lock) — so a rotation that returned `refused:agents lock busy` (`scripts/sysadmin/rotate_session.py:1188-1194` continues regardless) heals at the next `add` (T09 calls the same function). The expected agents-lock hold is one grid start plus one pane launch.
3. **Adoption first, then one pane-command path (D1; plan-review pass 2, C-N3).** In the grid-up case, step (6) first runs T08a's adoption check (a live pane of the name is adopted even when the resolver would now fail), and only when nothing is adopted gets (in the cold-start exit-0 case adoption finds nothing — the new builder was not registered when the grid came back — so `--pane-cmd` always follows there) `<cmd>` from `agents_up.sh --pane-cmd <root> <name> <uuid> --new` (T02) and hands it to `place_pane` (T08a) unchanged; a non-zero exit stops `add` at step 6 with that stderr (C4).

DO-NOT: build any pane command; change placement (T08a); regenerate launchers (T08c).

Depends: T02, T08a
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py -q
Docs: none (T09 documents the finished verbs)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH
- tests/test_agents_spawn.py

## Behavior Contract
- **Given** no tmux session and two registered builders, **When** `add <R> b-3` runs, **Then** `agents_up.sh --detach <R>` brings both back before b-3 is recorded, headroom is measured again after it and before b-3's launch, and a second measure under 2 GB exits 2 with a refusal row and b-3's worktree and binding kept (spec § The delta D4; W-14219e6f point 7; plan-review pass 1, C4)
- **Given** no tmux session and no builder, **When** `add <R> b-1` runs, **Then** the first `--detach` exits 3 and starts nothing, after the binding is written the second `--detach` makes the grid with b-1 as its first pane launched with `--session-id`, and `place_pane` is not called (W-14219e6f point 1; plan-review pass 2, C-N3)
- **Given** a restored grid whose panes read `running` only after 2 s and a fake cgroup whose usage grows between reads, **When** `add` re-measures, **Then** the measure is taken after the panes settle (or `FABRIK_AGENTS_SETTLE_S=1` elapses) and uses the grown value (panel PF4)
- **Given** `add <R> builder-4 --item W-1a2b3c4d` by a caller bound as `coord-a`, and separately with no `--item`, **When** the pane launches, **Then** its first prompt names coord-a and W-1a2b3c4d, and the no-item launch still starts (panel PO1, PO2)
- **Given** a registry row for builder-2 holding an old id while its live pane runs `--resume <new id>`, **When** `add` places builder-4, **Then** the row is re-pointed to the new id (panel PF3)
- **Given** a grid up, **When** `add` places b-4, **Then** its pane's command is byte-identical to `agents_up.sh --pane-cmd <R> b-4 <uuid> --new`'s output, the window is even-horizontal and the pane carries `@agent b-4` (scripts/sysadmin/agents_up.sh:455-505; spec § The delta D1)
- **Given** `--pane-cmd` exiting 2, **When** `add` reaches step 6, **Then** it stops there with that stderr and no pane is created (plan-review pass 1, C4)
- **Given** a live pane tagged `@agent b-4` running b-4's bound id and a resolver that now refuses, **When** `add <R> b-4` reaches step 6, **Then** the pane is adopted and `--pane-cmd` is never called (plan-review pass 2, C-N3)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_spawn.py
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
