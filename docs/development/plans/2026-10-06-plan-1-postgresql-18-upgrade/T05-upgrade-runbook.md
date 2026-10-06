# T05 — The operator runbook for the WSL and hub windows

Depends: T02, T03
Parallel: ⛓️
Complexity: native
Appetite: 120
Gate: python scripts/enforcement/check_doc_links.py
Docs: docs/operations/postgres-major-upgrade-runbook.md

## Scope
Implements spec § The delta › D1, D2, D5 and § Lifecycle as an executable runbook at `docs/operations/postgres-major-upgrade-runbook.md` — a NEW doc (no runbook for a Postgres major upgrade exists; the grounding searched docs/operations, docs/infrastructure, docs/workstation and docs/reference). Sections: (1) pre-window probes — `crontab -u root -l` and the Backrest schedules (`scripts/bootstrap/bootstrap-hub.sh:89` 01:30 cron, `docs/operations/disaster-recovery.md:43` plans 02:00–03:30), the disk gate, `$PGPW` proven, live database list and sizes (U1), `/opt/backups/pre-backup.sh` read (U2), the hub compose diffed against the repo, every pool size against `max_connections`; (2) the WSL window, D2 steps 0–6, with the local writers the grounding found beyond the spec (`docs/operations/wsl-environment.md:52` youtube financials, `:66` trade-intelligence GTIP refresh, `scripts/wsl_startup_hook.sh:227` the MCP tunnel and `:231` the session-recall reindex); (3) the hub window, D1 disk gate and steps 1–8 with 6a, each step a copy-paste command block, a verify line and its rollback, plus the archived plan's operator steps the spec left implicit — a Telegram maintenance notice, an Alertmanager silence for the window, `fabrik audit-registrars` after the restart (`src/fabrik/cli.py:1370`), a GlitchTip error check, one API call per service, a 7-day hold on the final dump; (4) release after the soak — removing `postgres-data` from Backrest, and the old volume and the WSL 16 cluster removed ONLY on the operator's explicit word (CLAUDE.md volumes HARD STOP); (5) appendix — the D5 request texts, one per project, sent after the hub window. DO-NOT: run any step; the runbook is executed by the operator in the windows.

## Touches
- docs/operations/postgres-major-upgrade-runbook.md — PRIMARY PATH
- tests/test_pg18_runbook.py

## Behavior Contract
- **Given** the runbook, **When** its hub-window section is read, **Then** every D1 step (the disk gate, 1–8 and 6a) has a command block, a verify line and a rollback line, in the spec's order (spec § The delta › D1)
- **Given** the runbook, **When** its WSL section is read, **Then** D2 steps 0–6 appear in order and the local-writer stop list names session-recall, the youtube financials cron, the trade-intelligence GTIP refresh and the MCP tunnel (docs/operations/wsl-environment.md:52; spec § The delta › D2)
- **Given** the runbook, **When** its release section is read, **Then** no step removes a docker volume or a cluster without the operator's explicit word (CLAUDE.md volumes HARD STOP; spec § Lifecycle)
- **Given** the runbook's appendix, **When** it is read, **Then** it carries one request text per D5 project, each naming that project's exact files from spec § What exists today (spec § The delta › D5)

## Context Files
- .windsurf/rules/core/30-ops.md
- .windsurf/rules/core/90-bootstrap-scripts.md
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- docs/operations/deployment.md
- docs/operations/wsl-environment.md
- docs/operations/disaster-recovery.md
- infra/vps1/postgres/compose.yaml
- docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md
