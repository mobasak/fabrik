# T05 — Grid relaunch, watchdog env and the memory ceiling
Appetite: 180

## Scope
Implements spec § Chosen approach L4 (`--detach`, the wake prompt) and L5, plus L1's watchdog for the tmux builders (routed I15: VS Code coordinators get it from W-ea993618's process wrapper, and Agent-tool seats inherit their parent's env). First step: measure U7 (why the 00:47 panes carry no `systemd-run`) from the launch path, and prove U3 (`claude -n x --resume <sid> "<prompt>"` delivers the prompt as the first turn on this box) in a throwaway pane. `scripts/sysadmin/agents_up.sh`: `--detach` stops before the `switch-client`/`attach` lines (:478-479) with argument parsing reworked from the `--print`-only check (:40-47); the inner command (:362) becomes `claude -n <name> --resume <sid> "<wake prompt>"` with `CLAUDE_CODE_RETRY_WATCHDOG=1`, the prompt ordering the self-watch arm and `hibernate.py woke` and resuming only on exit 0; the cap block (:282-293, `slice_ceiling` ~:407) sets the parent slice `MemoryHigh`=MemTotal−4G and `MemoryMax`=MemTotal−2G read through a `FABRIK_PROC_ROOT` meminfo seam, drops the per-pane `MemoryMax`, and on the `.bat` path refuses an uncapped start unless `FABRIK_AGENTS_UNCAPPED=1`, while `--detach` (the boot path) launches uncapped with D-1075's warning; the relaunch's permission mode follows `permissions.defaultMode` and is stated in the header (routed I6). `scripts/capped_run.sh`: the test slice becomes a child of the agents parent slice, and an admission band waits while MemAvailable < 3G or PSI `some avg10` > 10, up to `FABRIK_TEST_ADMIT_WAIT` (default 600 s), through the same `FABRIK_PROC_ROOT` seam; exit codes 124/137/2 and the `killed at the memory ceiling` line stay byte-identical (`scripts/final_gate.py:3675` reads them). DO-NOT: change `--print`'s `pane`/`cap`/`run`/`session` line shapes beyond the `cap` values.

Depends: T04
Parallel: ⛓️
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_agents_up.py tests/test_capped_run.py -q
Docs: scripts/sysadmin/agents_up.sh header (the cap rules); docs/reference/repo-coordinator-rollout.md per its AFTER-EDIT header

Grounded at: `scripts/sysadmin/agents_up.sh:362` (the launch line), `scripts/sysadmin/agents_up.sh:479` (`exec tmux attach`), `scripts/capped_run.sh:22` (the defaults)

## Touches
- scripts/sysadmin/agents_up.sh — PRIMARY PATH
- scripts/capped_run.sh
- tests/test_agents_up.py
- tests/test_capped_run.py

## Behavior Contract
- **Given** `agents_up.sh --detach <repo>`, **When** the grid is built, **Then** no `attach` or `switch-client` runs (scripts/sysadmin/agents_up.sh:479; spec § Chosen approach L4)
- **Given** a relaunched builder, **When** its pane starts, **Then** the command is `claude -n <name> --resume <sid> "<wake prompt>"` with `CLAUDE_CODE_RETRY_WATCHDOG=1` in its env (scripts/sysadmin/agents_up.sh:362; spec § Chosen approach L1, L4)
- **Given** a box with 27 GiB MemTotal, **When** the grid is built, **Then** the parent slice gets `MemoryHigh`=MemTotal−4G and `MemoryMax`=MemTotal−2G and no pane gets a `MemoryMax` (scripts/sysadmin/agents_up.sh:282; spec § Chosen approach L5)
- **Given** MemAvailable under 3 GiB, **When** `capped_run.sh` starts a job, **Then** it waits up to the admission bound, then starts and says so (scripts/capped_run.sh:22; spec § Chosen approach L5)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_up.sh
- scripts/capped_run.sh
- tests/test_agents_up.py
- tests/test_capped_run.py
