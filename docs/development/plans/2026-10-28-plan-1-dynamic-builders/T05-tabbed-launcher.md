# T05 — `agents_bat.py --tabbed`: the generated, box-wide "All Agents (tabbed).bat"
Appetite: 90

## Scope
Implements spec § The delta D5's generator half (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:180-195` and `:201-204`) and its § Contract deltas row (`:266`). The live `wt.exe` tab append (`:195-200`) is T08's.

1. **`--tabbed`** writes ONE file, `All Agents (tabbed).bat`, with one `new-tab` per (repo, window) — the format of the hand-written file on the operator's desktop (read this run: `@echo off`, the fragment blocks, then one `start "" wt.exe … new-tab … ; new-tab …` line), with these changes: the window is named (`wt.exe -M -w fabrik-agents`, never `-w new`), so T08 can append to it; the marker (`MARKER`, `scripts/sysadmin/agents_bat.py:44`) is line 2. Repos are the ones the per-repo mode already accepts (`scripts/sysadmin/agents_bat.py:143-152`, `_has_grid` at `:208-224`). Per repo: tab 1 runs `<AGENTS_UP> /opt/<repo>` (attach-or-launch, unchanged — so a repo whose grid is down still gets its tab and its grid starts there); for each live window named `agents-<n>` of that repo's tmux session (`tmux list-windows -t =<S> -F '#{window_name}'`, `<S>` derived as `scripts/sysadmin/agents_up.sh:333-334` derives it) one more tab, titled `<Repo> Agents <n>`, running `<AGENTS_UP> --window <n> /opt/<repo>` (T03's mode). A `list-windows` that fails or prints nothing yields tab 1 only — never fewer tabs than repos. Each repo's profile fragment is written as the per-repo mode writes it (`bat_text`, `:72-107`, factored so both modes share the fragment block).
2. **The distro default** becomes the Deck's resolver — `_default_distro` loaded by file path from `scripts/sysadmin/fabrik_deck.py:892-921` (same directory; the module's import is constants and stdlib only, `scripts/sysadmin/fabrik_deck.py:67-109`) — so a run from tmux, systemd or code-server, where `$WSL_DISTRO_NAME` is unset, names this distro from `wslpath -w /` (mail 01M5JXEQQ5). One function, not two copies; `--distro` still overrides; `''` still refuses (`:129-134`).
3. **The box-wide lock and the write.** Every `--desktop` run (both modes) holds `flock` on `~/.config/fabrik/agents-desktop.lock` (blocking, 30 s bound; busy past it → exit 2 said), reads the live grids only AFTER taking it, and `_write` (`:227-253`) writes through `tempfile.mkstemp(dir=target.parent, prefix="." + target.name + ".", suffix=".tmp")` and `os.replace`, never the fixed `<name>.tmp` (`:245-248`) — so two coordinators in different repos can neither interleave a write nor install a snapshot older than the other's.
4. **The remembered desktop.** A run with `--desktop D` writes `D` to `~/.config/fabrik/agents-desktop` (one line, atomic replace); a `--tabbed` run without `--desktop` reads it and writes there; no remembered folder → print mode (as today) plus "no desktop remembered — run once with --desktop" on stderr, exit 0.
5. **First generation** (orchestrator, at T10's live proof): run once as `agents_bat.py --tabbed --desktop "<the operator's terminal agents folder>" --replace "All Agents (tabbed).bat"` — the hand-written file carries no marker and is refused without it (`:238-244`).

DO-NOT: change the per-repo `.bat` text or names (`bat_name`, `:68-69`); delete any desktop file; touch `agents_up.sh` or `fabrik_deck.py`.

Depends: T03
Parallel: ⛓️
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_bat.py -q
Docs: the module docstring (`scripts/sysadmin/agents_bat.py:3-31`) gains `--tabbed`, the lock and the remembered desktop; the rollout doc's Windows-side section is T09's

## Touches
- scripts/sysadmin/agents_bat.py — PRIMARY PATH
- tests/test_agents_bat.py

## Behavior Contract
- **Given** two repos with grids, one whose tmux session has windows `agents` and `agents-2`, **When** `agents_bat.py --tabbed --desktop D` runs, **Then** `D/All Agents (tabbed).bat` has three tabs in one `wt.exe -M -w fabrik-agents` line — two running `agents_up.sh /opt/<repo>` and one running `agents_up.sh --window 2 /opt/<repo>` (spec § The delta D5)
- **Given** a repo `--print` accepts whose tmux session is not up, **When** `--tabbed` runs, **Then** that repo still gets its first tab (scripts/sysadmin/agents_bat.py:208-224; spec § The delta D5)
- **Given** `WSL_DISTRO_NAME` unset and `/usr/bin/wslpath` present, **When** `--tabbed` runs, **Then** every `wsl.exe --distribution` names the distro `wslpath -w /` names (scripts/sysadmin/fabrik_deck.py:892-921; spec § The delta D5)
- **Given** an existing `All Agents (tabbed).bat` without the marker, **When** `--tabbed --desktop D` runs, **Then** it is left untouched with exit 2, and with `--replace "All Agents (tabbed).bat"` it is rewritten carrying the marker (scripts/sysadmin/agents_bat.py:227-244)
- **Given** one earlier run with `--desktop D`, **When** `--tabbed` runs with no `--desktop`, **Then** it writes `D/All Agents (tabbed).bat` (spec § The delta D5)
- **Given** two `--tabbed --desktop D` processes started together, **When** both finish, **Then** `D` holds one whole current file and no temp file (spec § The delta D5)
- **Given** the rename fails, **When** `_write` runs in either mode, **Then** the error reaches the caller and no temp file stays in the folder (tests/test_agents_bat.py:273-296)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_bat.py
- tests/test_agents_bat.py
- scripts/sysadmin/fabrik_deck.py
- scripts/sysadmin/agents_up.sh
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
