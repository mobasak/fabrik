# T04b — The two large current-state docs say 18

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 20
Gate: python -m pytest tests/test_large_docs_pg18.py -q
Docs: docs/infrastructure/vps-complete-inventory.md, docs/traycer/fabrik-workflow.md

## Scope
Implements spec § Documentation landing sites for the two docs too large to share T04a's READ budget: `docs/infrastructure/vps-complete-inventory.md:120,168` and `docs/traycer/fabrik-workflow.md:412` say 18 — those lines and any other statement of the CURRENT major in the two files, prose or image tag (`PostgreSQL 16`, `postgres:16`, `pgvector/pgvector:pg16` — line 412 carries both a prose major and the `pg16` tag, which becomes `pgvector/pgvector:0.8.6-pg18`); history they quote is left. The branch merges after the hub window. DO-NOT: touch any other file.

## Touches
- docs/infrastructure/vps-complete-inventory.md — PRIMARY PATH
- docs/traycer/fabrik-workflow.md
- tests/test_large_docs_pg18.py

## Behavior Contract
- **Given** the two docs, **When** they are searched for `PostgreSQL 16`, `postgres:16` or `pgvector:pg16` stated as the current major, **Then** none matches (docs/infrastructure/vps-complete-inventory.md:120; spec § Documentation landing sites)

## Context Files
- .windsurf/rules/core/40-documentation.md
