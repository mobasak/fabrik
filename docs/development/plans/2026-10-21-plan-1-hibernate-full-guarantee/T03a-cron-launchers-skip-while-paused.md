# T03a — Cron launchers skip while paused
Appetite: 90

## Scope
Implements spec § Personas (the cron row) and L2's intake stop for the cron-started launchers: each runs `/opt/fabrik/scripts/sysadmin/hibernate.py paused` (Interface P) with a 10 s timeout before it starts a NEW worker or job — exit 0 skips with its stamp untouched and one line to its own log; exit 1, ≥2, a timeout or a missing script proceeds (fail-open) and an error logs one line. `scripts/sysadmin/weekly_catchup.sh` after the fresh-stamp exit (:63) and before `running` (:65); `scripts/ci_fix_dispatcher.py` at the top of `main()` (:259), and its `claude -p` worker (:233) carries `CLAUDE_CODE_RETRY_WATCHDOG=1` and starts with `oom_score_adj` 500 (written in a `preexec_fn`, fail-open — spec L1, L5's headless pool worker); `scripts/audit_all_registrars.py` forces report mode in `_reconcile()` (:181), the audit and metrics push continuing; `scripts/enforcement/check_mutation.py` (synced, never-route) in `_main()` after the `FABRIK_MUTMUT` guard (:119-125), keeping 'always exits 0'. `scripts/wip_backup.sh` gains `WIP_BACKUP_ONLY=<repo>` checked in the loop body (:313), default unchanged, for T06's step snapshot. The weekly_catchup test reuses `tests/test_liveness_audit.py:376`'s recipe. DO-NOT: change any launcher's exit codes or output beyond the skip line.

Depends: T01a
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_launchers_pause.py tests/test_wip_backup.py -q
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_ci_fix_dispatcher.py tests/test_ci_fix_dispatcher_env.py tests/test_check_mutation.py -q
Docs: none in this ticket: the launchers' AFTER-EDIT docs (docs/reference/health-monitoring.md, docs/CONFIGURATION.md, docs/workstation/kaizen.md) gain their pause-skip line in T06

Grounded at: `scripts/sysadmin/weekly_catchup.sh:63` (fresh-stamp exit), `scripts/ci_fix_dispatcher.py:233` (the `claude -p` spawn), `tests/test_liveness_audit.py:376` (the recipe)

## Touches
- scripts/sysadmin/weekly_catchup.sh — PRIMARY PATH
- scripts/ci_fix_dispatcher.py
- scripts/audit_all_registrars.py
- scripts/enforcement/check_mutation.py
- scripts/wip_backup.sh
- tests/test_launchers_pause.py
- tests/test_wip_backup.py

## Behavior Contract
- **Given** a marked pause, **When** any hub launcher in the cron census starts, **Then** it starts no worker, its stamp untouched (scripts/sysadmin/weekly_catchup.sh:63; spec § Personas)
- **Given** `FABRIK_REGISTRY_RECONCILE=apply` and a marked pause, **When** `audit_all_registrars.py` runs, **Then** it reconciles in report mode only (scripts/audit_all_registrars.py:181; spec § Personas)
- **Given** `hibernate.py paused` exits 2, times out or is absent, **When** a launcher checks it, **Then** it proceeds and logs one line (scripts/ci_fix_dispatcher.py:259; spec § Personas)
- **Given** the CI fix dispatcher, **When** it spawns its `claude -p` worker, **Then** the worker's env carries `CLAUDE_CODE_RETRY_WATCHDOG=1` and its `oom_score_adj` reads 500 (scripts/ci_fix_dispatcher.py:233; spec § Chosen approach L1, L5)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/weekly_catchup.sh
- scripts/ci_fix_dispatcher.py
- scripts/audit_all_registrars.py
- scripts/enforcement/check_mutation.py
