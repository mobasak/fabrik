# T05 — The operator runbook for the WSL and hub windows

Depends: T02, T03
Parallel: ⛓️
Complexity: native
Appetite: 120
Gate: python -m pytest tests/test_pg18_runbook.py -q
Docs: docs/operations/postgres-major-upgrade-runbook.md

## Scope
Implements spec § The delta › D1, D2, D5, D6, § Compatibility checks and § Lifecycle as an executable runbook at `docs/operations/postgres-major-upgrade-runbook.md` — a NEW doc (no runbook for a Postgres major upgrade exists; the grounding searched docs/operations, docs/infrastructure, docs/workstation and docs/reference). Sections: (1) pre-window probes — `crontab -u root -l` and the Backrest schedules (`scripts/bootstrap/bootstrap-hub.sh:89` 01:30 cron, `docs/operations/disaster-recovery.md:43` plans 02:00–03:30), the disk gate, `$PGPW` proven, live database list and sizes (U1), `/opt/backups/pre-backup.sh` read (U2), the hub compose diffed against the repo, every pool size against `max_connections`; (2) the WSL window, D2 steps 0–6, with the local writers the grounding found beyond the spec (`docs/operations/wsl-environment.md:52` youtube financials, `:66` trade-intelligence GTIP refresh, `scripts/wsl_startup_hook.sh:231` the session-recall reindex on shell open), and spec § Compatibility checks as D2 step 4's verify lines; (3) the hub window, D1 disk gate and steps 1–8 with 6a — step 1 stopping the WSL MCP tunnel (`scripts/wsl_startup_hook.sh:227`, it reaches the HUB cluster) — each step a copy-paste command block, a verify line and its rollback, spec § Compatibility checks (the restore blockers, the `pg_trgm` index check, roles and grants re-measured) folded into step 6's verify before the point of no return, plus the archived plan's operator steps the spec left implicit — a Telegram maintenance notice, an Alertmanager silence for the window, `fabrik audit-registrars` after the restart (`src/fabrik/cli.py:1370`), a GlitchTip error check, one API call per service, a 7-day hold on the final dump; (4) release after the soak — the V8 DR drill (`vultr_drill.py` core boot of `postgres18-data`, spec § Validation V8) first, then removing `postgres-data` from Backrest, and the old volume and the WSL 16 cluster removed ONLY on the operator's explicit word (CLAUDE.md volumes HARD STOP); (5) appendix — the D5 and D6 request texts, one per spec D5 bullet (the 27 doc-only projects share one broadcast, as the spec says), sent after the hub window. DO-NOT: run any step; the runbook is executed by the operator in the windows.

## Touches
- docs/operations/postgres-major-upgrade-runbook.md — PRIMARY PATH
- tests/test_pg18_runbook.py

## Behavior Contract
- **Given** the runbook, **When** its hub-window section is read, **Then** every D1 step (the disk gate, 1–8 and 6a) has a command block, a verify line and a rollback line, in the spec's order, and step 6's verify carries the § Compatibility checks items (spec § The delta › D1; § Compatibility checks)
- **Given** the runbook, **When** its WSL section is read, **Then** D2 steps 0–6 appear in order and the local-writer stop list names session-recall, the youtube financials cron and the trade-intelligence GTIP refresh (docs/operations/wsl-environment.md:52; spec § The delta › D2)
- **Given** the runbook, **When** its release section is read, **Then** the V8 DR drill precedes any release step, and no step removes a docker volume or a cluster without the operator's explicit word (CLAUDE.md volumes HARD STOP; spec § Lifecycle; § Validation V8)
- **Given** the runbook's appendix, **When** it is read, **Then** it carries one request text per spec D5 bullet and for D6, each naming its projects' exact files from spec § What exists today, the 27 doc-only projects in one broadcast (spec § The delta › D5)

## Context Files
- .windsurf/rules/core/30-ops.md
- .windsurf/rules/core/90-bootstrap-scripts.md
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- docs/operations/deployment.md
- docs/operations/wsl-environment.md
- docs/operations/disaster-recovery.md
- infra/vps1/postgres/compose.yaml
- scripts/bootstrap/bootstrap-config.sh
- docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md
