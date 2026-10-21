# T05 — Grid relaunch, watchdog env and the memory ceiling
Appetite: 180

## Scope
Implements spec § Chosen approach L4 (`--detach`, the wake prompt), L5, and L1's watchdog for the tmux builders (routed I15: VS Code coordinators get it from W-ea993618's process wrapper, Agent-tool seats inherit their parent's env, hub seats get it in T03b). First step: measure U7 (why the 00:47 panes carry no `systemd-run`) from the launch path, and prove U3 (`claude -n x --resume <sid> "<prompt>"` delivers the prompt as the first turn on 2.1.305) in a throwaway pane; record both in the ticket's commit. `scripts/sysadmin/agents_up.sh`: `--detach` stops before `switch-client`/`attach` (:478-479), argument parsing reworked from the `--print`-only check (:60-62); the inner command (:362) becomes `claude -n <name> --resume <sid> "<wake prompt>"` with `CLAUDE_CODE_RETRY_WATCHDOG=1` and `oom_score_adj` 200, the prompt ordering the self-watch arm and `hibernate.py woke` and resuming only on exit 0; the cap block (:282-293, `slice_ceiling` :396) sets the parent `fabrik-agents.slice` `MemoryHigh`=MemTotal−4G and `MemoryMax`=MemTotal−2G, rounded down to whole G, read through a `FABRIK_PROC_ROOT` meminfo seam — a MemTotal under 8G or unreadable keeps D-1075's 16G ceiling and says so — and drops the per-pane `MemoryMax` (`FABRIK_AGENT_MEM_MAX` retired: a set value warns and is ignored; `FABRIK_AGENT_SLICE_MAX` still overrides the derived ceiling); on the `.bat` path an uncapped start refuses unless `FABRIK_AGENTS_UNCAPPED=1`, while `--detach` (the boot path) launches uncapped with D-1075's warning; the relaunch's permission mode follows `permissions.defaultMode` (routed I6). Re-expects `tests/test_agents_up.py` :204/:270, :1153-1170, :1185/:1203, :1263/:1276, :1279/:1286-1325, :1309/:1333 for the new cap and run lines and adds a `--detach` test. `scripts/capped_run.sh`: the slice is `fabrik-agents-tests.slice` (systemd nests by the dashed name) so the parent ceiling bounds it, its 12G cap kept; an admission band waits while MemAvailable < 3G or PSI `some avg10` > 10, up to `FABRIK_TEST_ADMIT_WAIT` (default 300 s), through the same seam, an unreadable meminfo or PSI starting at once and saying so; exit codes 124/137/2 and the `capped_run: killed at the memory ceiling` prefix stay (`scripts/final_gate.py:3675` reads the prefix only), and `tests/test_capped_run.py:407`'s slice name in the killed line is re-expected.

Depends: T01a
Parallel: ⚡
Complexity: complex
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_agents_up.py tests/test_capped_run.py -q
Docs: scripts/sysadmin/agents_up.sh header (the cap rules); docs/reference/repo-coordinator-rollout.md (its AFTER-EDIT doc)

Grounded at: `scripts/sysadmin/agents_up.sh:362` (the launch line), `scripts/sysadmin/agents_up.sh:479` (`exec tmux attach`), `scripts/capped_run.sh:30` (the defaults)

## Touches
- scripts/sysadmin/agents_up.sh — PRIMARY PATH
- scripts/capped_run.sh
- tests/test_agents_up.py
- tests/test_capped_run.py
- docs/reference/repo-coordinator-rollout.md

## Behavior Contract
- **Given** `agents_up.sh --detach <repo>`, **When** the grid is built, **Then** no `attach` or `switch-client` runs (scripts/sysadmin/agents_up.sh:479; spec § Chosen approach L4)
- **Given** a relaunched builder, **When** its pane starts, **Then** the command is `claude -n <name> --resume <sid> "<wake prompt>"` with `CLAUDE_CODE_RETRY_WATCHDOG=1` in its env and `oom_score_adj` 200 (scripts/sysadmin/agents_up.sh:362; spec § Chosen approach L1, L4, L5)
- **Given** a box with 27 GiB MemTotal, **When** the grid is built, **Then** the parent slice gets `MemoryHigh`=MemTotal−4G and `MemoryMax`=MemTotal−2G and no pane gets a `MemoryMax`, and a MemTotal under 8G keeps the old ceiling (scripts/sysadmin/agents_up.sh:282; spec § Chosen approach L5)
- **Given** MemAvailable under 3 GiB, **When** `capped_run.sh` starts a job, **Then** it waits up to the admission bound, then starts and says so, and an unreadable meminfo starts at once (scripts/capped_run.sh:30; spec § Chosen approach L5)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/agents_up.sh
- scripts/capped_run.sh
- tests/test_agents_up.py
- tests/test_capped_run.py
