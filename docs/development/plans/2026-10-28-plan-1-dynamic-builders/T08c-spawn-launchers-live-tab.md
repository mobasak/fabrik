# T08c — `agents_spawn.py add`, part 3: regenerate the launchers, append the live tab
Appetite: 60

## Scope
Wires `add`'s step (7) in `scripts/sysadmin/agents_spawn.py`: spec § The delta D5's regeneration and live `wt.exe` tab (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:188-200`) and § Lifecycle's degradation rule (`:364-366`), with plan-review pass 1, C8.

Invariants and touchpoints:
1. **Launchers (D5).** Step (7) runs `python3 <script dir>/agents_bat.py --tabbed` (T05; no `--desktop` → the remembered folder). Its non-zero exit, or its "no desktop remembered" note, is said on stderr and does not fail `add` — the `.bat` is regenerated at the next verb.
2. **The distro, once (C8).** `add` calls `_default_distro()` (loaded from `scripts/sysadmin/fabrik_deck.py:892-921` by file path, as T05 does) ONCE per run and passes the value where needed, so its stderr note prints once.
3. **The live tab (D5).** Only when step (6)'s `PlaceResult.new_window_k` is set: run `<wt.exe> -w fabrik-agents new-tab --title "<Repo> Agents <k>" wsl.exe --distribution <distro> --exec tmux attach -t =<S>-<k>`. `<wt.exe>` = `$FABRIK_WT_EXE`, else `shutil.which("wt.exe")`, else the single match of `/mnt/c/Users/*/AppData/Local/Microsoft/WindowsApps/wt.exe` (this run: not on PATH, present at that glob). `wt.exe` missing or failing → said, `add` exits 0; distro `''` → "no WSL distro could be derived — tab not appended" and the call is skipped (the `.bat` refusal stays T05's).

DO-NOT: touch placement or the cold start (T08a, T08b); write the `.bat` here (T05 does).

Depends: T05, T08b
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_agents_spawn.py tests/test_agents_bat.py -q
Docs: none (T09 documents the finished verbs)

## Touches
- scripts/sysadmin/agents_spawn.py — PRIMARY PATH
- tests/test_agents_spawn.py

## Behavior Contract
- **Given** step 6 opened `agents-2`, **When** `add` finishes, **Then** a fake `wt.exe` received `-w fabrik-agents new-tab … tmux attach -t =<S>-2`, and with `wt.exe` absent `add` says so and still exits 0 (spec § The delta D5; spec § Lifecycle)
- **Given** `WSL_DISTRO_NAME` unset and a fake `wslpath` that fails, **When** `add` opens a new window, **Then** the tab is skipped with the no-distro note printed once and `add` exits 0 (plan-review pass 1, C8)
- **Given** a remembered desktop, **When** `add` finishes, **Then** `All Agents (tabbed).bat` there lists the new window's tab, and with no remembered desktop `add` says so and exits 0 (spec § The delta D5)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_spawn.py
- tests/test_agents_spawn.py
- scripts/sysadmin/agents_bat.py
- scripts/sysadmin/fabrik_deck.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
