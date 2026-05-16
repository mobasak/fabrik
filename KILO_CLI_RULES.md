# KILO_CLI_RULES — Spec contract awareness for Kilo CLI

Loaded by Kilo CLI via `opencode.json` `instructions:` array (alongside `AGENTS-compact.md`). Propagated to every Fabrik project via `scripts/sync_enforcement_to_projects.py` (`GOVERNANCE_FILES` list).

This file is the single source of truth for Kilo's shape/registrar awareness. The same content also lives at the bottom of `CLAUDE.md`, `.windsurfrules`, and `AFCL.md` so every executor sees it (V2-S6 reference-not-duplicate principle is honoured here only for `AGENTS-compact.md`, which carries a one-line cross-reference instead of the full snippet — see Lesson 63 / T3-02 rationale).

## Spec contract awareness

Every Fabrik project has `specs/services/<id>.yaml` with a `shape:` block that drives:

- Which Postgres DB / Redis index / Backrest plan / Gatus endpoint / Prometheus job / GlitchTip project / Authelia rule / Meilisearch index get auto-created on `fabrik apply`
- The shape contract is canonical: code MUST match it, not the other way around

If your code:

- Adds a database call → `shape.needs_database` MUST be `true` in the spec
- Adds a Redis cache → `shape.needs_cache` MUST be `true`
- Exposes `/metrics` → `shape.exposes_metrics` MUST be `true`
- Adds Meilisearch indexes → `shape.has_search_feature` MUST be `true`
- Adds an admin UI behind auth → `shape.is_admin_dashboard` MUST be `true`

If you change code in a way that affects any of the above, ALSO update `specs/services/<id>.yaml`.
Don't ship code that contradicts the spec — `fabrik apply` will skip the registrar and you'll have a silently broken deploy.

To preview what the spec will trigger: `fabrik plan specs/services/<id>.yaml`
