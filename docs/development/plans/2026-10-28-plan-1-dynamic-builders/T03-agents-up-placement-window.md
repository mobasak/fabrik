# T03 — agents_up.sh: named windows of four on relaunch, the factored grid start, `--window <n>`
Appetite: 120

## Scope
Implements, in `scripts/sysadmin/agents_up.sh` only: spec § The delta D4 for the RELAUNCH path (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:154-164`) and the factored grid start D4 names (`:164-174`); D5's `--window <n> <repo>` attach mode (`:183-187`). W-14219e6f point 11 is decided here: **overflow windows start at `agents-2`** — the first window is `agents` (`scripts/sysadmin/agents_up.sh:335`), the k-th (k ≥ 2) is `agents-<k>`, its grouped session `<S>-<k>`, matching the hand-made `fabrik-2` tab (D-1132) and spec § Validation's "a fifth builder opens `agents-2`". W-14219e6f point 6: **the commit that factors the grid start names W-1961cc42 in its message** ("closes W-1961cc42 — the non-TTY detach, `scripts/sysadmin/agents_up.sh:542-547` and `:626-635`, landed in 208dccd76, whose message did not name it"), so the orchestrator can run `python3 scripts/work.py done W-1961cc42 --evidence "<that sha>"` at merge (spec § Intake Inventory I22).

1. **Factored start.** The `else` branch at `scripts/sysadmin/agents_up.sh:591-624` (slice ceiling, then one pane per resolved builder) becomes a function `start_grid` called from the same place; behaviour for ≤ 4 builders is byte-identical in its tmux calls (the existing `new-session -d -s <S> -n agents -c <dir> -x 240 -y 60`, `split-window -t =<S>:agents`, `select-layout … even-horizontal`, `set -p … @agent`, `select-pane -t =<S>:agents.0`).
2. **Placement on relaunch (D4).** Builders, in the resolver's name order, fill windows four at a time: panes 1-4 into `agents` as today; pane 5 opens `tmux new-window -d -t "=$S:" -n agents-2 -c <dir> <cmd>`, panes 6-8 `split-window -t "=$S:agents-2"`, and so on (`agents-3` from pane 9). After each pane: `select-layout -t <that window> even-horizontal` and `set -p -t <that window> @agent <name>` (the `:619-620` pair, re-targeted at the pane's window). After the loop, for every k ≥ 2 window: `tmux new-session -d -t "$S" -s "$S-$k"` unless `has-session -t "=$S-$k"` already answers, then `tmux select-window -t "=$S-$k:agents-$k"` so that grouped session's CURRENT window is its own; then `select-window -t "=$S:agents"` and `select-pane -t "=$S:agents.0"`, so `<S>`'s current window — the one tab 1 attaches — is `agents` (W-14219e6f point 8's relaunch half: a relaunch re-creates the first window as the base session's current one). The "no room for <name>'s pane" fallback (`:615-617`) is kept per window.
3. **`--window <n> <repo>`** (argument loop `:77-89`; n an integer ≥ 2, else usage exit 2). It resolves `<S>` as today (`:333-334`) — the resolver runs and its refusals refuse — then polls `tmux has-session -t "=$S"` every 2 s for up to `FABRIK_AGENTS_WINDOW_WAIT_S` seconds (default 120; the seam keeps the test fast); never up → "the <S> grid did not come up in <n> s", exit 2. Up with a window `agents-<n>` (`tmux list-windows -t "=$S" -F '#{window_name}'`): create `<S>-<n>` if missing, `select-window -t "=$S-$n:agents-$n"`, then attach `=<S>-<n>` (the `:631-637` tail: `switch-client` inside tmux, the no-terminal message and exit 0 without one). Up WITHOUT that window: say "the <S> grid has no window agents-<n> now — showing its current window", attach `=<S>`, and never create `<S>-<n>`.

DO-NOT: change the resolver, `cmd_of`, or the exit codes (T02); the attach-or-launch default path's behaviour when the grid is already up (`:588-590`, "leaving it as it is"); `owned_here`/`adoptable` (`:548-586`).

Depends: T02
Parallel: ⛓️
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_up.py tests/test_agents_bat.py -q
Docs: the header comment of agents_up.sh (`scripts/sysadmin/agents_up.sh:3`, `:17-21`) gains the window layout and `--window`; the rollout doc's launcher section is T09's

## Touches
- scripts/sysadmin/agents_up.sh — PRIMARY PATH
- tests/test_agents_up.py — new tests below; the `:agents` target pins of W-14219e6f point 4 (`tests/test_agents_up.py:484-485`, `:612`, `:717`) are re-run and stay as they are for grids of ≤ 4 builders (window 1 keeps the name `agents`); any of them whose fixture registers more than four builders is re-expected to the per-window targets

## Behavior Contract
- **Given** six registered builders and no tmux session, **When** the grid launches, **Then** window `agents` holds four panes, window `agents-2` holds two, the grouped session `<S>-2` exists with `agents-2` as its current window, and `<S>`'s current window is `agents` (scripts/sysadmin/agents_up.sh:595-623; spec § The delta D4; spec § Validation, the 10-22 regression)
- **Given** four or fewer builders, **When** the grid launches, **Then** the fake tmux log shows one window `agents`, no `new-window` and no grouped session (scripts/sysadmin/agents_up.sh:603-620)
- **Given** a nine-builder relaunch, **When** the grid launches, **Then** every pane carries `@agent <its name>` set against its own window and every window is laid out even-horizontal (scripts/sysadmin/agents_up.sh:619-620)
- **Given** a grid up with a window `agents-2` and no session `<S>-2`, **When** `agents_up.sh --window 2 <R>` runs, **Then** it creates `<S>-2`, selects `agents-2` in it, and attaches `=<S>-2` (spec § The delta D5)
- **Given** a grid up without a window `agents-3`, **When** `agents_up.sh --window 3 <R>` runs, **Then** it says so, attaches `=<S>`, and creates no `<S>-3` (spec § The delta D5)
- **Given** no grid and `FABRIK_AGENTS_WINDOW_WAIT_S=2`, **When** `agents_up.sh --window 2 <R>` runs, **Then** it polls has-session and exits 2 saying the grid did not come up (spec § The delta D5)
- **Given** `--window 1`, `--window x` or `--window` with no number, **When** parsed, **Then** usage exit 2 (scripts/sysadmin/agents_up.sh:86-89)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_up.sh
- tests/test_agents_up.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
