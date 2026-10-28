# T08 — `agents_spawn.py add`, part 2: cold start, placement, launch, launchers, the live tab
Appetite: 150

## Scope
Completes `add` in `scripts/sysadmin/agents_spawn.py`: spec § The delta D2 steps (3), (6), (7) (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:108-109`, `:128-129`), D4's placement for a spawn and its cold start (`:154-174`), D5's regeneration and live `wt.exe` tab (`:188-200`), and D9's live read (`:250-256`), with three spec CORRECTIONS from W-14219e6f that this ticket implements as stated here, not as the spec words them:

- **Point 1 (the no-builder branch needs the UUID first).** Step (3) runs `agents_up.sh --detach <R>` (the factored start, T03) only when `tmux has-session -t =<S>` fails. On its exit 3 (no builder, T02) it starts NOTHING; steps (4)-(5) then mint and record the new builder (T06), and step (6) runs `agents_up.sh --detach <R>` AGAIN — which now resolves the new builder (its binding and worktree exist; no transcript, so T02 launches it with `--session-id` and the first prompt) and makes the grid with it as the first pane through the same factored start. The cold-start pane is therefore never built before its UUID exists. Exit 0 at step (3) means the grid (every registered builder) is up and the new builder is placed at step (6) like any other spawn; any other code stops `add` at step 3.
- **Point 7 (headroom after the cold start).** `headroom_bytes()` (T06) is measured again AFTER step (3) and immediately BEFORE step (6)'s launch — a reboot's empty slice passes the preflight, and the grid step (3) just brought back may have used the room. Under 2 GB at either point refuses (exit 2, said, `agents-spawn.jsonl` row) with steps (1)-(5)'s artifacts left in place for a re-run.
- **Point 8 (a re-created first window is `<S>`'s current window).** When placement re-creates the window `agents` (it had emptied and tmux destroyed it), `add` runs `tmux select-window -t "=<S>:agents"` right after creating it, so tab 1 (which attaches `=<S>`) shows it; in every other case `add` never moves `<S>`'s current window.

1. **The live read (D9).** `tmux list-panes -s -t "=<S>" -F '#{window_name} #{pane_id} #{@agent}'` — the base session only, one line per pane. An error or an empty answer while `has-session` says the grid is up refuses ("tmux read failed — not placing"), never reads as an empty grid.
2. **Placement (D4; point 11 as T03 decided).** The lowest-named window (`agents`, then `agents-2`, `agents-3`, … in that order) with fewer than four panes gets the pane: `tmux split-window -d -t "=<S>:<window>" -c <worktree> <cmd>`; none → the lowest free name: `agents` if absent (then point 8), else the lowest unused `agents-<k>` (k ≥ 2) via `tmux new-window -d -t "=<S>:" -n <name> -c <worktree> <cmd>`, then `tmux new-session -d -t <S> -s <S>-<k>` and `tmux select-window -t "=<S>-<k>:agents-<k>"`. After either: `select-layout -t "=<S>:<window>" even-horizontal` and `set -p -t <the new pane id> @agent <name>`.
3. **The pane command (D1).** `<cmd>` is exactly the one line `agents_up.sh --pane-cmd <R> <name> <uuid> --new` prints (T02) — the env allow-list, the scope, the caps and the suppression are its, never rebuilt here; that call's non-zero exit stops `add` at step 6 with its stderr.
4. **Adoption (D2 idempotency).** Before placing: a live pane tagged `@agent <name>` in the base session, whose claude process's argv (under `/proc/<pane pid>`'s children) carries `--session-id <uuid>` or `--resume <uuid>` for the name's bound id, is adopted — no second pane; a pane tagged with the name but another id refuses, naming both ids.
5. **Launchers (D5).** Step (7) runs `python3 <script dir>/agents_bat.py --tabbed` (T05; no `--desktop`, so the remembered folder) — its non-zero exit or a missing remembered folder is said on stderr and does not fail `add` (the `.bat` is regenerated at the next verb; spec § Lifecycle, Degradation).
6. **The live tab (D5).** Only when step (6) opened a NEW window `agents-<k>`: run `<wt.exe> -w fabrik-agents new-tab --title "<Repo> Agents <k>" wsl.exe --distribution <distro> --exec tmux attach -t =<S>-<k>`, `<wt.exe>` resolved as `$FABRIK_WT_EXE`, else `shutil.which("wt.exe")`, else the single match of `/mnt/c/Users/*/AppData/Local/Microsoft/WindowsApps/wt.exe` (this run: not on the shell's PATH, present at that glob), `<distro>` from the same `_default_distro` T05 uses. Missing or failing → said, `add` still exits 0 (spec § Lifecycle, Degradation).

DO-NOT: build any pane command by hand; move `<S>`'s current window except under point 8; touch `agents_up.sh` (its placement on relaunch is T03's).

Depends: T02, T05, T06
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_up.py tests/test_agents_bat.py -q
Docs: none in this ticket (T09 documents the finished verbs)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH
- tests/test_agents_spawn.py

## Behavior Contract
- **Given** no tmux session and two registered builders, **When** `add <R> b-3` runs, **Then** `agents_up.sh --detach <R>` brings both back before b-3 is recorded, headroom is measured again after it and before b-3's launch, and b-3 is then placed (spec § The delta D4 cold start; W-14219e6f point 7)
- **Given** no tmux session and no builder, **When** `add <R> b-1` runs, **Then** the first `--detach` exits 3 and starts nothing, and after the binding is written the second `--detach` makes the grid with b-1 as its first pane launched with `--session-id` (W-14219e6f point 1)
- **Given** window `agents` holding four panes, **When** `add` places a fifth builder, **Then** it opens `agents-2` in the background, creates `<S>-2` with `agents-2` current, and `<S>`'s current window is unchanged (spec § The delta D4; spec § Validation)
- **Given** the window `agents` gone and `agents-2` live, **When** `add` places a builder, **Then** it re-creates `agents` and makes it `<S>`'s current window (W-14219e6f point 8)
- **Given** placement, **When** the pane starts, **Then** its command is byte-identical to `agents_up.sh --pane-cmd`'s output, the window is even-horizontal, and the pane carries `@agent <name>` (scripts/sysadmin/agents_up.sh:455-505; spec § The delta D1)
- **Given** a NEW window opened, **When** `add` finishes, **Then** the fake `wt.exe` received `-w fabrik-agents new-tab … tmux attach -t =<S>-2`, and with `wt.exe` absent `add` says so and still exits 0 (spec § The delta D5)
- **Given** a remembered desktop, **When** `add` finishes, **Then** `All Agents (tabbed).bat` there lists the new window's tab, and with no remembered desktop `add` says so and exits 0 (spec § The delta D5)
- **Given** a live pane tagged `@agent b-1` running b-1's bound id and no worktree record step left to do, **When** `add <R> b-1` runs again, **Then** no second pane is created (spec § The delta D2)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_spawn.py
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_up.sh
- scripts/sysadmin/agents_bat.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
