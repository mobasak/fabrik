# T05 — `agents_bat.py --tabbed`: the generated, box-wide "All Agents (tabbed).bat"
Appetite: 105

## Scope
Implements spec § The delta D5's generator half (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:180-195`, `:201-204`) and its § Contract deltas row (`:266`), with plan-review pass 1, C3, C4, C7, C8. The live `wt.exe` tab append (`:195-200`) is T08c's (plan-review pass 2, C-N4).

Invariants and touchpoints:
1. **`--tabbed`** writes ONE file, `All Agents (tabbed).bat`, in the format of the hand-written file on the operator's desktop (read this run: `@echo off`, the fragment blocks, one `start "" wt.exe … new-tab … ; new-tab …` line), with the window NAMED (`wt.exe -M -w fabrik-agents`, never `-w new`) so T08c can append to it, and `MARKER` (`scripts/sysadmin/agents_bat.py:44`) as line 2. Repos: the ones the per-repo mode accepts (`scripts/sysadmin/agents_bat.py:143-152`, `_has_grid` at `:208-224`). Per repo: tab 1 runs `<AGENTS_UP> /opt/<repo>` (attach-or-launch — a repo whose grid is down still gets its tab); then one tab per live window whose name matches `^agents-([2-9]|[1-9][0-9]+)$` (C4; any other window name is ignored), titled `<Repo> Agents <n>`, running `<AGENTS_UP> --window <n> /opt/<repo>` (T03), which attaches the overflow session `<S>+<n>` by T03 invariant 4's rule (plan-review pass 2, class rewrite: the `<S>+<k>` name can never be another repo's base session, so no tab can attach a foreign grid). Windows come from `tmux list-windows -t =<S> -F '#{window_name}'`, `<S>` derived as `scripts/sysadmin/agents_up.sh:333-334` does; a read that fails or prints nothing yields tab 1 only. The fragment block is factored out of `bat_text` (`:72-107`) so both modes share it.
2. **Distro (C8).** The default is the Deck's resolver — `_default_distro` loaded by file path from `scripts/sysadmin/fabrik_deck.py:892-921` (its import is constants and stdlib only, `scripts/sysadmin/fabrik_deck.py:67-109`) — called ONCE per run, so its stderr note prints once; one function, not two copies; `--distro` overrides; `''` refuses (`:129-134`).
3. **Lock scope (C3).** The slow part — up to N × `agents_up.sh --print` at 60 s each (`:211-216`) — runs OUTSIDE the lock. `main()` is restructured into: (a) compute the repo list (today's `:143-152`), unlocked; (b) take `flock` on `~/.config/fabrik/agents-desktop.lock`, waiting at most 30 s (busy past it → exit 2, said); (c) under the lock, re-read only the live tmux windows (one `list-windows` per repo, milliseconds) and write; (d) release. So two coordinators in different repos neither interleave a write nor install a snapshot older than the other's.
4. **The write.** `_write` (`:227-253`), in both modes, writes through `tempfile.mkstemp(dir=target.parent, prefix="." + target.name + ".", suffix=".tmp")` + `os.replace`, never the fixed `<name>.tmp` (`:245-248`).
5. **Remembered desktop (C7).** A run with `--desktop D` stores `os.path.abspath(D)` in `~/.config/fabrik/agents-desktop` (one line, atomic replace). A `--tabbed` run without `--desktop` reads it; no file, or a folder that is missing or not a directory → print mode (as today) plus a one-line note on stderr ("no desktop remembered" / "the remembered desktop <D> is not a folder — run once with --desktop"), exit 0.
6. **The hand-made `fabrik-2` session** (the old `.bat`'s overflow tab) is not an `<S>+<k>` name and is never reaped by T03; the post-merge live proof's step 1 kills it by hand first (plan-review pass 3, note).
7. **First generation** (orchestrator, before the post-merge live proof): `agents_bat.py --tabbed --desktop "<the operator's terminal agents folder>" --replace "All Agents (tabbed).bat"` — the hand-written file carries no marker and is refused without it (`:238-244`).

DO-NOT: change the per-repo `.bat` text or names (`bat_name`, `:68-69`); delete any desktop file; touch `agents_up.sh` or `fabrik_deck.py`.

Depends: T03
Parallel: ⛓️
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_bat.py -q
Docs: the module docstring (`scripts/sysadmin/agents_bat.py:3-31`) gains `--tabbed`, the lock and the remembered desktop

## Touches
- scripts/sysadmin/agents_bat.py — PRIMARY PATH
- tests/test_agents_bat.py

## Behavior Contract
- **Given** two repos with grids, one whose session has windows `agents`, `agents-2` and `scratch`, **When** `agents_bat.py --tabbed --desktop D` runs, **Then** `D/All Agents (tabbed).bat` has three tabs in one `wt.exe -M -w fabrik-agents` line — two `agents_up.sh /opt/<repo>` and one `agents_up.sh --window 2 /opt/<repo>` — and none for `scratch` (spec § The delta D5; plan-review pass 1, C4)
- **Given** a repo whose tmux session is down, or whose `list-windows` fails or prints nothing, **When** `--tabbed` runs, **Then** that repo gets exactly its first tab (scripts/sysadmin/agents_bat.py:208-224; plan-review pass 1, C4)
- **Given** `WSL_DISTRO_NAME` unset and `/usr/bin/wslpath` present, **When** `--tabbed` runs, **Then** every `wsl.exe --distribution` names the distro `wslpath -w /` names and the derivation note prints once (scripts/sysadmin/fabrik_deck.py:892-921; plan-review pass 1, C8)
- **Given** an existing `All Agents (tabbed).bat` without the marker, **When** `--tabbed --desktop D` runs, **Then** it is left untouched with exit 2, and with `--replace "All Agents (tabbed).bat"` it is rewritten carrying the marker (scripts/sysadmin/agents_bat.py:227-244)
- **Given** one earlier run with a relative `--desktop D`, **When** `--tabbed` runs with no `--desktop` from another cwd, **Then** it writes `D/All Agents (tabbed).bat`; with nothing remembered or a remembered folder since deleted it prints the text, notes why on stderr and exits 0 (spec § The delta D5; plan-review pass 1, C4, C7)
- **Given** two `--tabbed --desktop D` processes started together, **When** both finish, **Then** `D` holds one whole current file and no temp file, and a run whose lock wait passes the bound exits 2 (spec § The delta D5; plan-review pass 1, C3, C4)
- **Given** a fake `agents_up.sh --print` that sleeps, **When** `--tabbed` runs, **Then** the lock file is not held while it sleeps (plan-review pass 1, C3)
- **Given** the rename fails, **When** `_write` runs in either mode, **Then** the error reaches the caller and no temp file stays in the folder (tests/test_agents_bat.py:273-296)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_bat.py
- tests/test_agents_bat.py
- scripts/sysadmin/fabrik_deck.py
- scripts/sysadmin/agents_up.sh
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
