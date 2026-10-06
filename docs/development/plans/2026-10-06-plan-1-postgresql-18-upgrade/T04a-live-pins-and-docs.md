# T04a — The hub's live pins and smaller current-state docs say 18

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 40
Gate: python -m pytest tests/test_live_docs_pg18.py -q
Docs: README.md, docs/reference/prebuilt-app-containers.md, docs/reference/technology-stack-decision-guide.md, docs/workstation/session-recall.md

## Scope
Implements spec § The delta › D3 (the real-PG test and the live-docs bullet) and § Documentation landing sites. `tests/test_app_role_real_pg.py:30,102` move to `postgres:18.6-alpine`; `scripts/container_images.py:565` and `scripts/generate_vps_inventory.py:72` name 18; the current-state docs `README.md:859`, `docs/reference/prebuilt-app-containers.md:87`, `docs/reference/technology-stack-decision-guide.md:21,518` and `docs/workstation/session-recall.md:3,15` say 18. Of the spec's 29 files the rest are frozen history (dated plans, specs, research ledgers, retired orchestrator docs, `docs/DECISIONS.md`, `docs/LESSONS_LEARNT.md`) and are never rewritten; `agents-fabrik.md` is a governance-sync path routed to infra, and `docs/STRATEGIC_BACKLOG.md:131` is the orchestrator's; the two large docs are T04b's (split for the READ budget). The branch merges after the hub window. DO-NOT: edit a frozen artifact or a governance-sync path.

## Touches
- tests/test_app_role_real_pg.py — PRIMARY PATH
- scripts/container_images.py
- scripts/generate_vps_inventory.py
- README.md
- docs/reference/prebuilt-app-containers.md
- docs/reference/technology-stack-decision-guide.md
- docs/workstation/session-recall.md
- tests/test_live_docs_pg18.py

## Behavior Contract
- **Given** the files this ticket owns, **When** they are searched for `PostgreSQL 16`, `Postgres 16`, `postgres:16` or `PG16`, **Then** none matches (README.md:859; spec § Documentation landing sites)
- **Given** docker on WSL, **When** `tests/test_app_role_real_pg.py` runs, **Then** its scratch container is `postgres:18.6-alpine` and the suite passes (tests/test_app_role_real_pg.py:30; spec § Validation V4)

## Context Files
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- tests/test_app_role_real_pg.py
- README.md
