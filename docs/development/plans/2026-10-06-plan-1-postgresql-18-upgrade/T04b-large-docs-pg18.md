# T04b — The two large current-state docs say 18

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 20
Gate: python -m pytest tests/test_large_docs_pg18.py -q
Docs: docs/infrastructure/vps-complete-inventory.md, docs/traycer/fabrik-workflow.md

## Scope
Implements spec § Documentation landing sites for the two docs too large to share T04a's READ budget: `docs/infrastructure/vps-complete-inventory.md:120,168` and `docs/traycer/fabrik-workflow.md:412` say 18 — only those lines and any other `PostgreSQL 16`/`postgres:16` statement of the CURRENT major in the two files; history they quote is left. The branch merges after the hub window. DO-NOT: touch any other file.

## Touches
- docs/infrastructure/vps-complete-inventory.md — PRIMARY PATH
- docs/traycer/fabrik-workflow.md
- tests/test_large_docs_pg18.py

## Behavior Contract
- **Given** the two docs, **When** they are searched for a statement that the fleet or postgres-main runs `PostgreSQL 16` or `postgres:16`, **Then** none matches (docs/infrastructure/vps-complete-inventory.md:120; spec § Documentation landing sites)

## Context Files
- .windsurf/rules/core/40-documentation.md
