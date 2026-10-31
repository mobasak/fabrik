# T08a — `agents_spawn.py`: the live read, placement into named windows of four, adoption
Appetite: 120

## Scope
Adds to `scripts/sysadmin/agents_spawn.py` the placement functions `add` uses at step (6): spec § The delta D4's placement for a spawn (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:154-163`), D9's live read (`:250-256`), D2's adoption (`:129-132`), with W-14219e6f points 8 and 11 and plan-review pass 1, B12, C1, C2, C4, and plan-review pass 2's class rewrite of the grouped-session rule. The cold start and the `add` wiring are T08b's; the launchers and live tab T08c's. Entry point for T08b: `place_pane(root, S, name, uuid, worktree, cmd) -> PlaceResult(window_id, pane_id, new_window_k | None, adopted: bool)`.

Invariants and touchpoints:
1. **The live read (D9; C4).** `tmux list-panes -s -t "=<S>" -F '#{window_id} #{window_name} #{pane_id} #{pane_pid} #{@agent}'` — the base session only, one line per pane. An error, or an empty answer while `has-session -t =<S>` says the grid is up, raises `PlacementRefused("tmux read failed — not placing")`, never reads as an empty grid.
2. **Window targets by id (B12).** Windows are matched by EXACT name over that read and targeted by `#{window_id}`; a created window's id comes from `new-window … -P -F '#{window_id}'`. Names: `agents`, then `agents-<k>`, k ≥ 2 (W-14219e6f point 11, as T03 decided).
3. **Placement (D4; C2).** The pane goes to the lowest window — order `agents`, `agents-2`, `agents-3`, … — that EXISTS and has fewer than four panes: `split-window -d -t <window id> -c <worktree> <cmd>`. Only when no existing window has room: the lowest free name — `agents` if absent, else the lowest unused `agents-<k>` — via `new-window -d -t "=<S>:" -n <name> -P -F '#{window_id}' -c <worktree> <cmd>`. After either: `select-layout -t <window id> even-horizontal`, `set -p -t <pane id> @agent <name>`.
4. **A re-created first window is current (W-14219e6f point 8).** When step 3 created `agents`, `select-window -t <its id>` on `<S>`, so tab 1 (attached to `=<S>`) shows it; otherwise `<S>`'s current window is never moved.
5. **Grouped overflow sessions — the one rule (plan-review pass 2, class rewrite; the same rule as T03 invariant 4).** The overflow session for window `agents-<k>` is named `<S>+<k>`. `+` is outside the base-name alphabet `[A-Za-z0-9_-]` (`scripts/sysadmin/agents_up.sh:332-334`), so `<S>+<k>` can never be another repo's base session (tmux accepts the name: `has-session -t =a+2` exits 0, executed on the orchestrator's scratch server 2026-10-28) and is this repo's by construction. For a new window `agents-<k>` (k = the lowest number no window `agents-<k>` uses): reuse `<S>+<k>` only when `has-session -t "=<S>+<k>"` succeeds AND its `#{session_group}` is NON-EMPTY AND equals `<S>`'s non-empty group; otherwise `kill-session -t "=<S>+<k>"` (when present) and `new-session -d -t "=<S>" -s <S>+<k>`; then `select-window` on `=<S>+<k>` to the window's id. Every target uses the exact `=` form.
6. **Adoption (D2; C1).** Before placing: a pane tagged `@agent <name>` whose process tree — `pane_pid`'s descendants walked recursively through `/proc/<pid>/task/*/children` (claude is a grandchild: `systemd-run --scope` → `bash -c` → claude, `scripts/sysadmin/agents_up.sh:494`, `:501`) — holds a claude whose argv carries `--session-id <uuid>` or `--resume <uuid>` for the name's bound id is ADOPTED (no new pane). A tagged pane with no claude descendant (claude exited; the kept shell) → `PlacementRefused` "b-1's pane runs no claude — respawn it (`tmux respawn-pane -k -t <pane>`) or remove it"; a tagged pane whose claude carries another id → `PlacementRefused` naming both ids. The walk reads the kernel's `children` files (present on this WSL kernel); `FABRIK_PROC_ROOT` (`scripts/sysadmin/agents_up.sh:373`'s seam) roots it, so tests build a fake `/proc` tree (plan-review pass 2, record-only).

DO-NOT: build a pane command (T08b passes `--pane-cmd`'s output in); start a session (T08b's cold start); touch `agents_up.sh`.

Depends: T06
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py -q
Docs: none (T09 documents the finished verbs)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH
- tests/test_agents_spawn.py — placement tests on a scratch `tmux -L <unique>` server, asserting server STATE

## Behavior Contract
- **Given** `list-panes` failing, or answering nothing while `has-session` succeeds, **When** `place_pane` runs, **Then** it refuses and creates nothing (spec § The delta D9; plan-review pass 1, C4)
- **Given** window `agents` holding four panes, **When** a fifth builder is placed, **Then** `agents-2` is opened in the background, `<S>+2` is created and groups `<S>` (whose own group was still empty) with `agents-2` current, and `<S>`'s current window is unchanged (spec § The delta D4; W-14219e6f point 11; plan-review pass 3)
- **Given** no window `agents` and a FULL `agents-2`, **When** a builder is placed, **Then** `agents` is re-created and becomes `<S>`'s current window (W-14219e6f point 8; plan-review pass 1, C2)
- **Given** no window `agents` and `agents-2` with three panes, **When** a builder is placed, **Then** it joins `agents-2` and no `agents` window is created (plan-review pass 1, C2, B12)
- **Given** a stale `<S>+2` grouped with an old killed base, a `<S>+3` already in `<S>`'s group, and a `<S>+4` with an EMPTY group, **When** windows `agents-2`, `agents-3` and `agents-4` are opened, **Then** `<S>+2` and `<S>+4` are killed and re-created in `<S>`'s group and `<S>+3` is reused (plan-review pass 2, class rewrite; plan-review pass 3)
- **Given** another repo's base session named `<S>-2`, **When** a fifth builder is placed, **Then** `<S>+2` is created and `<S>-2` is untouched (scripts/sysadmin/agents_up.sh:332-334; plan-review pass 2, class rewrite)
- **Given** a pane tagged `@agent b-1` whose claude grandchild runs `--resume <b-1's id>`, **When** b-1 is placed, **Then** it is adopted and no pane is added (spec § The delta D2; plan-review pass 1, C1)
- **Given** a pane tagged `@agent b-1` with no claude descendant, or one running another id, **When** b-1 is placed, **Then** it refuses naming the remedy or both ids (plan-review pass 1, C1, C4)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_spawn.py
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
