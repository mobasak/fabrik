# T03 — agents_up.sh: named windows of four on relaunch, the factored grid start, `--window <n>`
Appetite: 150

## Scope
Implements, in `scripts/sysadmin/agents_up.sh` only: spec § The delta D4 for the RELAUNCH path (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:154-164`) and the factored grid start (`:164-174`); D5's `--window <n> <repo>` (`:183-187`); plan-review pass 1, B2, B3, B8, B10, B11, B12. W-14219e6f point 11, decided: **overflow windows start at `agents-2`** — the first window is `agents` (`scripts/sysadmin/agents_up.sh:335`), the k-th (k ≥ 2) `agents-<k>`, its grouped session `<S>-<k>` (D-1132's `fabrik-2`; spec § Validation). W-14219e6f point 6: **this ticket's commit message names W-1961cc42** ("closes W-1961cc42 — the non-TTY detach, `scripts/sysadmin/agents_up.sh:542-547` and `:626-635`, landed in 208dccd76, whose message did not name it").

Invariants and touchpoints:
1. **Window targets by id (B12).** tmux resolves a window NAME target loosely — with only `agents-2` present, `-t =s:agents` and `-t =s:=agents` both select `agents-2` (executed by the review). Every window this script creates is captured by id (`new-session … -P -F '#{window_id}'`, `new-window … -P -F '#{window_id}'`); an existing window is found by an EXACT name match over `tmux list-windows -t "=$S" -F '#{window_id} #{window_name}'`; every later `split-window`, `select-layout`, `set -p`, `select-window` targets the id, never a name.
2. **Factored start.** The branch at `scripts/sysadmin/agents_up.sh:591-624` becomes `start_grid`, called from the same place; for ≤ 4 builders its tmux effect is unchanged (one window `agents`, even-horizontal, `@agent` per pane, pane 0 selected). At its end it sets the session option `@agents_up_built 1` (`tmux set-option -t "=$S:" @agents_up_built 1`, the `=<S>:` option form of `:542-544`) (B3).
3. **Placement on relaunch (D4; B11).** Builders, in the resolver's order, fill windows four PLACED panes at a time — the count is of panes actually created, never the loop index: a `split-window` or `new-window` that fails is said with the pane's command printed (the `:615-617` "no room" message) and the next builder takes that slot. Pane 5 (placed) opens `new-window -d -t "=$S:" -n agents-2 -c <dir> <cmd>`, panes 6-8 split it, pane 9 opens `agents-3`. After each pane: `select-layout -t <window id> even-horizontal`, `set -p -t <pane id> @agent <name>`.
4. **Grouped sessions (B2).** For each window k ≥ 2: reuse `<S>-<k>` only when `tmux display -p -t "=$S-$k:" '#{session_group}'` equals `<S>`'s group; otherwise (a member that outlived its base — executed by the review: killing `=a` leaves `a-2` alive — or another session of that name) `kill-session -t "=$S-$k"` and `new-session -d -t "$S" -s "$S-$k"`; then `select-window` on that session to window `agents-<k>`'s id. Finally `select-window` `<S>` to `agents`'s id and `select-pane` its pane 0, so `<S>`'s current window — tab 1's — is `agents` (W-14219e6f point 8, relaunch half). The relaunch hint at `:590` names every member: `tmux kill-session -t =<S>` plus one `kill-session -t =<S>-<k>` per member of the group.
5. **`--window <n> <repo>`** (argument loop `:77-89`; n an integer ≥ 2, else usage exit 2). Resolves `<S>` (`:333-334`; the resolver's refusals refuse), then polls every 2 s for up to `FABRIK_AGENTS_WINDOW_WAIT_S` seconds (default 120) until `has-session -t "=$S"` answers AND `@agents_up_built` reads `1` (B3 — a grid still being built has the session but not yet its windows); never → "the <S> grid was not built within <n> s", exit 2. Then the ownership check `owned_here` (`:548-574`) — a definite other owner refuses (B8). Window `agents-<n>` present (exact match, invariant 1): ensure `<S>-<n>` as invariant 4, select its window, attach `=<S>-<n>` (the `:631-637` tail). Absent: "the <S> grid has no window agents-<n> now — showing its current window", attach `=<S>`, never create `<S>-<n>`.

DO-NOT: change the resolver, `cmd_of` or exit codes (T02); the attach path when the grid is already up (`:588-590`) beyond the hint text; `adoptable` (`:576-586`).

Depends: T02
Parallel: ⛓️
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_up.py tests/test_agents_bat.py -q
Docs: the header comment of agents_up.sh (`scripts/sysadmin/agents_up.sh:3`, `:17-21`) gains the window layout and `--window`

## Touches
- scripts/sysadmin/agents_up.sh — PRIMARY PATH
- tests/test_agents_up.py — new tests below (the six-builder regression and the window-target rows on a scratch `tmux -L <unique>` server, asserting the server's STATE — windows, panes, groups — never a call log, as the spec's measurements did; plan-review pass 1, B10); the `:agents` target pins (`tests/test_agents_up.py:484-485`, `:612`, `:717`) are re-expected to the id-targeted calls the fake tmux now logs

## Behavior Contract
- **Given** six registered builders and no session on a scratch tmux server, **When** the grid launches, **Then** window `agents` holds four panes, `agents-2` two, session `<S>-2` is in `<S>`'s group with `agents-2` current, and `<S>`'s current window is `agents` (scripts/sysadmin/agents_up.sh:595-623; spec § The delta D4; plan-review pass 1, B10)
- **Given** four or fewer builders, **When** the grid launches, **Then** there is one window `agents` and no grouped session (scripts/sysadmin/agents_up.sh:603-620)
- **Given** the second of six builders' `split-window` fails, **When** the grid launches, **Then** the failure is said with that pane's command and the remaining five fill `agents` (four) and `agents-2` (one) (scripts/sysadmin/agents_up.sh:615-617; plan-review pass 1, B11)
- **Given** a stale session `<S>-2` left from a killed base session (another group), **When** the six-builder grid launches, **Then** `<S>-2` is killed and re-created in `<S>`'s group (plan-review pass 1, B2)
- **Given** a server whose only window is `agents-2`, **When** the script looks up window `agents`, **Then** it finds none and targets nothing by that name (plan-review pass 1, B12)
- **Given** a grid up and built with window `agents-2`, **When** `agents_up.sh --window 2 <R>` runs, **Then** it ensures `<S>-2` in `<S>`'s group with `agents-2` current and attaches `=<S>-2`, while a session recording another repo's root refuses (spec § The delta D5; plan-review pass 1, B8)
- **Given** a built grid without `agents-3`, **When** `--window 3 <R>` runs, **Then** it says so, attaches `=<S>`, and creates no `<S>-3` (spec § The delta D5)
- **Given** the session up but `@agents_up_built` unset, then no session at all, with `FABRIK_AGENTS_WINDOW_WAIT_S=2`, **When** `--window 2 <R>` runs, **Then** both exit 2 saying the grid was not built, and `--window 1` exits 2 with usage (spec § The delta D5; plan-review pass 1, B3)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_up.sh
- tests/test_agents_up.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
