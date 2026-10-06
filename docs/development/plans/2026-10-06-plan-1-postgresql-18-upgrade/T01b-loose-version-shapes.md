# T01b — The loose-literal sweep sees the PG18 image shapes

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 20
Gate: python -m pytest tests/sysadmin/test_rules_render_versions.py -q
Docs: none

## Scope
Implements spec § The delta › D3 (the `_LOOSE` bullet). `_LOOSE` (`scripts/sysadmin/rules_render_versions.py:36-51`) gains the `postgres:N(.N)?-alpine` and `pgvector:X.Y.Z-pgN` shapes, so an unmarked literal of either form in a rule pack is caught by the sweep; the existing `PostgreSQL 16` and `pgvector:pg16` shapes keep matching, and a port such as `5432` never fires. The two packs in `CLEANED_PACKS` (`tests/sysadmin/test_rules_render_versions.py:36-44`) carry an unmarked `postgres:16-alpine` today — `.windsurf/rules/core/30-ops.md:320` and `.windsurf/rules/core/25-data-postgres.md:23` — which the new shape would flag, so T01b is gated on infra re-dating those two literals as history (spec D4's 're-dated literals'; the precondition gate). DO-NOT: touch `src/fabrik/ci_scaffold.py` (T01a's) or any rule pack.

## Touches
- scripts/sysadmin/rules_render_versions.py — PRIMARY PATH
- tests/sysadmin/test_rules_render_versions.py

## Behavior Contract
- **Given** the strings `postgres:18-alpine`, `postgres:18.6-alpine` and `pgvector/pgvector:0.8.6-pg18`, **When** `_LOOSE` searches each, **Then** each matches, the existing `PostgreSQL 16` and `pgvector:pg16` cases still match, and `port 5432` does not (scripts/sysadmin/rules_render_versions.py:36)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/rules_render_versions.py
- tests/sysadmin/test_rules_render_versions.py
