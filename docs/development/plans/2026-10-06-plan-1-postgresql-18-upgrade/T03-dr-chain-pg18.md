# T03 — The disaster-recovery chain restores postgres18-data

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 45
Gate: python -m pytest tests/test_dr_chain_pg18.py -q
Docs: docs/operations/disaster-recovery.md, docs/operations/hub-restore-inventory.md, docs/infrastructure/vps-hub-rebuild.md

## Scope
Implements spec § The delta › D3 (the DR-chain hunk), extended by the grounding to every live `postgres-data` line. `scripts/bootstrap/bootstrap-config.sh:201` lists `postgres18-data` in `FABRIK_HUB_VOLUMES_TO_RESTORE`; the comments and log strings at `scripts/bootstrap/bootstrap-hub.sh:78,83,1170,1315,1324,1334` and `src/fabrik/orchestrator/vultr_drill.py:310` name it; the docs `docs/operations/hub-restore-inventory.md:97,186,193`, `docs/operations/disaster-recovery.md:74,264,266,279,453` and `docs/infrastructure/vps-hub-rebuild.md:105,107,130` say it; the count comment at `docs/operations/disaster-recovery.md:264` becomes '11 until release (both Postgres volumes), the loop restores 10' (it names no volume). After T03 no line in the files it owns names `postgres-data` (today: `docs/operations/disaster-recovery.md:74,266,279,453` and the cited script lines); the old volume's survival until release is the runbook's (T05), not these docs'. This hunk is the ONE part of the work infra merges INSIDE the hub window, at runbook step 8 after V1 is green (spec D1 step 8; D-617), so T03 is committed on its OWN branch `fleet-pg18-dr`: the orchestrator creates it as a dedicated worktree (`git worktree add <scratch>/fleet-pg18-dr -b fleet-pg18-dr master`), and the T03 coder works and gates there — never a branch switch inside the shared fleet worktree. No CHANGELOG hunk rides it (the orchestrator's entry is on the fleet branch); the fleet branch then merges `fleet-pg18-dr` so T05 reads T03's lines. DO-NOT: touch the live Backrest config or any path outside the Touches.

## Touches
- scripts/bootstrap/bootstrap-config.sh — PRIMARY PATH
- scripts/bootstrap/bootstrap-hub.sh
- src/fabrik/orchestrator/vultr_drill.py
- docs/operations/hub-restore-inventory.md
- docs/operations/disaster-recovery.md
- docs/infrastructure/vps-hub-rebuild.md
- tests/test_dr_chain_pg18.py

## Behavior Contract
- **Given** `scripts/bootstrap/bootstrap-config.sh`, **When** `FABRIK_HUB_VOLUMES_TO_RESTORE` is sourced in bash, **Then** it contains `postgres18-data` and not `postgres-data` (scripts/bootstrap/bootstrap-config.sh:201; spec § The delta › D3)
- **Given** the DR scripts and docs this ticket owns, **When** they are searched for `postgres-data` as a whole word (so `postgres18-data` never matches), **Then** no line matches, and `disaster-recovery.md`'s volume-count comment reads 11 until release (docs/operations/disaster-recovery.md:74)

## Context Files
- .windsurf/rules/core/90-bootstrap-scripts.md
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- scripts/bootstrap/bootstrap-config.sh
- docs/operations/disaster-recovery.md
- docs/operations/hub-restore-inventory.md
- docs/infrastructure/vps-hub-rebuild.md
