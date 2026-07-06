# DATA CONTRACT — [Project Name]

> **Status:** DRAFT | FROZEN  ·  **Version:** v1  ·  **Date:** YYYY-MM-DD  ·  **Mode:** A (spec-driven) | B (reverse-generated) | C (fresh)
>
> The **single frozen truth for field naming across the whole stack** — every GUI/form field ↔ its exact DB
> column. Produced/refreshed by **`/fabrik-data-contract`** (spec-driven for new work, reverse-generated from the
> live schema when backfilling an existing project). Traycer reads it when planning; Kilo / frontend / backend
> agents implement against it.
>
> **FROZEN — no agent adds a field, column, or enum value not listed here. Any change = bump Version + re-freeze
> via `/fabrik-data-contract`.**

---

## House rules — every field inherits these (do not repeat per row)

- **IDs:** UUIDv7, **app-generated** (never sequential ints). DB-side `uuidv7()` (PG18) / `pg_uuidv7` extension where the PG version allows.
- **Naming:** `snake_case`; tables **plural**; foreign keys `<entity>_id`.
- **Timestamps:** `timestamptz`, stored in **UTC**.
- **Money:** `amount_minor BIGINT` + `currency CHAR(3)` (ISO 4217). Never float. Minor-unit exponent is **per-currency** (JPY 0, most 2, some dinars 3).
- **Every entity also carries** (implied — omit from the per-entity tables): `id`, `created_at`, `updated_at` [, `tenant_id` if multi-tenant SaaS] [, `deleted_at` if it soft-deletes].
- **Fleet-wide grandfather (state ONCE here, never per-row):** schema-wide violations that apply to *every* entity — e.g. all PKs serial-int not UUIDv7, all table names singular not plural — go here as a single note, not repeated in every table. Per-row `⚠ non-standard` is reserved for *entity-specific* deviations.
- **Missing / renamed implied field:** omitting an audit field means "present AND standard." If an entity is *missing* an implied field or uses a *renamed* one, you MUST say so on the entity as a `⚠ audit:` note (e.g. `⚠ audit: no updated_at; created→imported_at`). Silence must never hide an absent field.

---

## Entities

> One block per entity. Standard audit fields (above) are implied — list only entity-specific fields (+ any `⚠ audit:` deviation note).
> `PII` ∈ `none | personal | sensitive` (sensitive = KVKK Art. 6 / GDPR Art. 9); an operator/actor audit identifier (`changed_by`, `reviewed_by`, set from the app user) is `personal`.
> `references` = the `entity.column` a FK points at, or `—`. A GUI field folded into a **jsonb key** is written `column.jsonkey` in the DB-column cell.
> `type` = a SQL type, or `enum:<x>` (native PG enum) / `chk:<x>` (CHECK-constraint-backed enum) — both draw their values from the Enum registry below.

### Entity: `<entity_name>`   (depends on: `<entity>`, …)

| GUI field | DB column | type | req | validation | PII | references |
|---|---|---|---|---|---|---|
| Email | `email` | text | yes | RFC5322, ≤255, lowercased | personal | — |
| — | `tenant_id` | uuid | yes | — | none | `tenants.id` |
| Plan | `plan` | enum:plan_status | yes | — | none | — |

<!-- duplicate the block per entity; keep (depends on: …) accurate — it is the build order -->

---

## GUI ↔ DB reconciliation notes

> Mismatches Phase 1 surfaced that don't fit a single row — a form field with no column, a dropdown whose values
> aren't valid for its column's enum, two tables the UI treats as one, a stale client-side type. One numbered
> note each. **These are the highest-value findings — they must survive to the frozen file, not get dropped at
> emit.** (Omit the section only if a clean pass genuinely found none.)

- **R1** — `<e.g. Events "Source URL" has no column; folded into calendar_event.context.source_url (jsonb key)>`
- **R2** — `<e.g. the event_type dropdown offers enrichment vocabulary; none are valid event_type enum literals, and no server-side validation catches it>`

---

## Enum registry — single source (agents use ONLY these values)

> Register BOTH native PG enums (`enum:<x>`) and CHECK-constraint value sets (`chk:<x>`) — real schemas use CHECK
> far more often than native enums. Note the backing so a migration to native later is unambiguous.

| Enum | Backing | Allowed values |
|---|---|---|
| `plan_status` | native | `trialing` \| `active` \| `past_due` \| `canceled` |
| `<enum_name>` | native / CHECK | `<v1>` \| `<v2>` |

---

## Retention & lawful basis — KVKK/GDPR (project-level; only for `personal`/`sensitive` data)

> Light, not per-field. One row per personal/sensitive data category — enough to be KVKK-defensible.

| Data category | PII class | Lawful basis | Retention | Cross-border? |
|---|---|---|---|---|
| Account | personal | contract | account life + 30d | no |
| `<category>` | personal/sensitive | `<Art.5/6 basis>` | `<period>` | yes/no + mechanism (adequacy/SCC) |

---

## FREEZE CHECKLIST

- [ ] Every GUI/form field maps to a DB column (no orphans in either direction)
- [ ] Every field has `type` + `req` + `PII` class
- [ ] Every FK `references` resolves to a real `entity.column`; `depends on` order has no cycle
- [ ] Every `enum:<x>`-typed field's values ⊆ the Enum registry
- [ ] House rules applied to new fields; existing violations flagged `⚠ non-standard: <what>` (grandfathered, not migrated)
- [ ] A retention row exists for every `personal`/`sensitive` category
- [ ] `Status: FROZEN`, `Version` bumped
