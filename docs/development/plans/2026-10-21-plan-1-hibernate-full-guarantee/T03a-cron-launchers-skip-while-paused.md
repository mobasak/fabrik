# T03a — Cron launchers skip while paused
Appetite: 90

## Scope
Implements spec § Personas (the cron row) and L2's intake stop for the cron-started launchers: each checks `hibernate.py paused` (interface P) before it starts a NEW worker or job and skips with its stamp untouched — `scripts/sysadmin/weekly_catchup.sh` after the fresh-stamp exit (:63) and before `running` (:65); `scripts/ci_fix_dispatcher.py` at the top of `main()` (:259); `scripts/audit_all_registrars.py` forces report mode in `_reconcile()` (:181) instead of skipping (the audit and metrics push continue); `scripts/enforcement/check_mutation.py` (synced, never-route) in `_main()` after the `FABRIK_MUTMUT` guard (:119-125), calling the hub path only when it exists and keeping 'always exits 0'. `scripts/wip_backup.sh` gains a single-repo scope (an optional `WIP_BACKUP_ONLY=<repo>` checked after :313; default unchanged) for T06's step snapshot. The weekly_catchup test reuses `tests/test_liveness_audit.py`'s recipe (`FABRIK_ROOT`, `FABRIK_PY`, a tmp `HOME`) cited here rather than read whole. DO-NOT: change any launcher's exit codes or output beyond the skip line.

Depends: T01
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_launchers_pause.py tests/test_wip_backup.py -q
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_ci_fix_dispatcher.py tests/test_ci_fix_dispatcher_env.py tests/test_check_mutation.py -q
Docs: none (the cron census is documented by T06 in docs/workstation/kaizen.md and hooks-index.md)

Grounded at: `scripts/sysadmin/weekly_catchup.sh:63` (fresh-stamp exit), `scripts/ci_fix_dispatcher.py:233` (the `claude -p` spawn), `tests/test_liveness_audit.py:376` (the weekly_catchup test recipe)

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

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/weekly_catchup.sh
- scripts/ci_fix_dispatcher.py
- scripts/audit_all_registrars.py
- scripts/enforcement/check_mutation.py
