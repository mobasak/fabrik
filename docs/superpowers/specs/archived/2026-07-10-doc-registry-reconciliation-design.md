# Design — Canonical, type-aware project-doc registry (one source of truth)

Status: CONVERGED
Date: 2026-07-10
Converged: 2026-07-10 (/fabrik-spec-review — 2 passes to an edit-free md5-verified no-op; every path:line re-grounded against real code [scaffold.py:137/194, check_structure allowlist, the stale ref corrected :237→:240], the 3 best-practice citations re-verified to support their claims, fabrik-lib verdict confirmed [no module fits; manifest owns the registry→derive pattern], grandfather strategy proven to avoid a fleet WARN storm)
Scaffold type: fabrik hub itself (changes fabrik's own scaffold + enforcement + synced manifest; distributed fleet-wide)

## Goal

Fix the scaffolded-doc mess: **three surfaces that independently list "which docs a project has/allows/updates" have drifted out of sync.** Replace them with **one canonical, type-aware doc registry** that all three surfaces **derive from**, so they can never drift again — plus cleanup of dead templates, stale references, naming drift, and empty-stub rot.

**The three surfaces today (the drift):**
- **Seed map** — `SHARED_TEMPLATE_MAP` (`src/fabrik/scaffold.py:194`), 18 docs, **shared-all** (not type-aware).
- **Allowlist** — the `docs/` allowlist in `check_structure.py` (`scripts/enforcement/check_structure.py:~202`), a *hand-maintained second copy*.
- **Doc Sync Matrix** — the when-to-update table in `CLAUDE.md` (authoritative) + a **stale duplicate** in `~/.claude/commands/fabrik-plan-after-chat.md:240`.

**Audited defects (this session's ground truth):**
1. Seeded but the structure gate WARNs (not allowlisted): `RESILIENCE.md`, `STRATEGIC_BACKLOG.md`, `LESSONS_LEARNT.md`, `data-contract.md`, `ui-design.md`.
2. Allowlisted but never seeded, no template — **phantom**: `EXTERNAL_SYSTEMS.md`, `FAQ.md`, `TESTING.md`.
3. Seeded but no update trigger → **rots as an empty stub**: `BUSINESS_MODEL.md`, `STRATEGIC_BACKLOG.md`, `docs/README.md`.
4. Not type-aware: a headless `python-api`/`worker` gets `BUSINESS_MODEL.md`; a no-DB API could get `data-contract.md`. Irrelevant stubs everywhere.
5. Dead/superseded templates: `API_REFERENCE_TEMPLATE` (→ QUICKSTART + live `/docs`), `DATABASE_SCHEMA_TEMPLATE` (→ `db/schema.sql` + `data-contract.md`); neither allowlisted.
6. Stale reference: `fabrik-plan-after-chat:240` tells agents to update `docs/DATABASE_SCHEMA.md` — which the structure gate *rejects*.
7. Naming drift: `LESSONS_LEARNT.md` (map) vs `lessons-learnt.md` (older projects).

## Chosen approach — Registry-in-manifest + derived surfaces (RECOMMENDED)

Add a **`PROJECT_DOCS` registry** (the single source of truth) to `scripts/fabrik_synced_manifest.py`, and **derive** every other surface from it:

- **Registry shape (one row per doc):** `name` (project-relative path) · `template` (source template, or `None` for command-authored contract docs) · `applies_to` (a **type-bucket** set) · `trigger` (the Doc Sync Matrix when-to-update rule) · `fills` (`scaffold-stub` | agent | `/fabrik-data-contract` | `/fabrik-ui-design` | static).
- **Type buckets** (matched to the real `SCAFFOLD_TYPES` in `src/fabrik/scaffold.py:137` — `python-api`, `python-api-gpu`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`):
  - `universal` — all types.
  - `deployed` (a running server/service → gets `SERVICES`/`OPERATIONS`/`RESILIENCE`/`PORTS`): `python-api`, `python-api-gpu`, `node-api`, `file-api`, `file-worker`, `saas-skeleton`, `wordpress`. **Excludes** the client-app types (`chrome-extension`, `mobile-app`, `desktop-app`) and the static-site types (`docusaurus`, `static-site`) — they have no backend service. *(This exact membership is a Phase-1 grounding item for the plan — confirm against each type's compose/service shape.)*
  - `data` — types whose `shape.needs_database` is true (grounded per project, not a fixed type list).
  - `gui` — `saas-skeleton`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`, `docusaurus`.
  - `saas` — `saas-skeleton`.
- **Derive `check_structure`'s `docs/` allowlist** via a new `manifest.docs_allowlist()` — the *identical* pattern the manifest already uses for the gitignore block (`gitignore_block_text()` derives from `GOVERNANCE_FILES`/`VENDORED_DIRS`). `check_structure.py` imports it instead of hard-coding a list. **SSOT: the allowlist is a projection, structurally can't drift.**
- **Make scaffold seeding type-aware** — `scaffold.py` iterates `PROJECT_DOCS`, seeds a doc only when `project_type ∈ applies_to`, using each row's `template`.
- **Align the Doc Sync Matrix** — every registry doc has a `trigger`; `CLAUDE.md`'s matrix is the human-readable rendering of the registry's triggers (and is the synced authoritative copy). Fix the stale `fabrik-plan-after-chat:240` line → `db/schema.sql` + `docs/data-contract.md`.
- **Force-fill enforcement** — a new advisory gate `scripts/enforcement/check_doc_stubs.py`: for a seeded doc **whose Doc-Sync trigger fired in this change** (e.g. an API route changed → QUICKSTART) that **still carries template placeholders** (`[Project Name]`, `YYYY-MM-DD`, `[PROJECT_NAME]`, `> **Purpose:**` boilerplate un-edited), WARN. Stubs can't silently rot past the moment they became relevant. Registered advisory (never blocks).
- **Cleanup:** archive the 2 dead templates → `templates/.archive/`; drop the 3 phantom allowlist entries (registry-derived allowlist simply won't include them); canonicalize `LESSONS_LEARNT.md`.
- **Grandfather existing projects (fleet blast radius):** `check_structure.py` is Fabrik-synced → a registry change re-distributes to 45 projects. Per the SSOT-as-shared-contract discipline, **do NOT retro-migrate**: the derived allowlist is a **superset-tolerant** set (registry docs ∪ a small explicit `LEGACY_TOLERATED` set covering docs older projects already carry, e.g. `DEPLOYMENT.md`), and the force-fill WARN is advisory. An older project with a legacy doc name gets at most an advisory nudge, never a hard fail.

This is **build-by-extension** of the manifest, ~1 new registry constant + 2 derivations + 1 advisory check + template cleanup — minimal new code, maximal reuse of the proven registry+derive pattern.

## Rejected alternatives

- **B — New standalone `doc_registry.py` module.** Rejected: duplicates the manifest's registry+derive machinery; the manifest is the established home (§ fabrik-lib verdict); a second registry is itself the "don't duplicate" anti-pattern the SSOT best-practice forbids.
- **C — Keep 3 surfaces, hand-sync + a consistency CHECK** (a gate asserting seed == allowlist == matrix). Rejected: SSOT best-practice (Google SRE, SSOT patterns) says **derive, don't hand-sync-then-check**. A check catches drift *after* it happens but still requires maintaining three copies — the exact root cause of today's mess. Derivation makes drift structurally impossible ("make derived state impossible to be wrong").

## External dependencies

**None** — this is fabrik-hub-internal tooling (scaffold + enforcement + synced manifest + governance docs); no 3rd-party API/SDK/pricing/limits. The **best-practice/approach** grounding (1c), cited live this session:

- **Google SRE Workbook, Ch.14 "Configuration Design & Best Practices"** + "Configuration Specifics" — https://sre.google/workbook/configuration-design/ , https://sre.google/workbook/configuration-specifics/ (fetched 2026-07-10). Operate on static data *generated* from a higher-level source; "generate configuration in the necessary formats… unify, synchronize, and **eliminate repetition across your entire config corpus.**"
- **SSOT / Design Patterns In Action (2024)** — https://designpatternsinaction.com/dry/ssot (fetched 2026-07-10). "Never store what can be computed… generate types from schemas… canonical source is always authoritative… **make derived state structurally impossible to diverge.**"
- **"One Config to Rule Them All" (Medium, 2026-06-14)** — https://medium.com/@nitingummidela/one-config-to-rule-them-all-a-single-source-of-truth-guide-2914937ff810 (fetched 2026-07-10). A central config is a **shared contract**: add fields optional-with-default, never remove/rename until no reader depends → the grandfather discipline for the fleet blast radius.

These three validate: one registry (source) → derived surfaces (not duplicated), evolved as a backward-compatible shared contract.

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| Doc registry + derive surfaces | **BUILD in fabrik (extend `fabrik_synced_manifest.py`)** | No fabrik-lib module fits — the `doc-*` modules (`doc-convert`/`doc-crawl`/`doc-translate`/`docx-io`/`docs-site`) are content-processing, not a scaffold-doc registry. The manifest **already** implements the registry+derive pattern (`GOVERNANCE_FILES`/`VENDORED_DIRS` → `gitignore_block_text()`); this is a within-fabrik reuse, not a new module. |
| Placeholder-stub WARN check | **BUILD in fabrik (`scripts/enforcement/check_doc_stubs.py`)** | Project-specific governance enforcement; belongs with the other `check_*` gates, not fabrik-lib. Follows the established enforcement-script shape (`# AFTER-EDIT:` header, gate registration, advisory). |

Neither is a 🆕 fabrik-lib candidate — both are hub-governance-specific (project-type buckets, fabrik doc set), not generic/reusable across project *types*.

## Shape / infra implications

- Scaffold type context: **the fabrik hub itself** (`/opt/fabrik`). No new `shape:` flags — this changes fabrik's scaffolder + enforcement + manifest, not a deployed service.
- **Fleet-synced surfaces touched:** `scripts/fabrik_synced_manifest.py`, `scripts/enforcement/check_structure.py`, `scripts/enforcement/check_doc_stubs.py` (new), and `CLAUDE.md` — all Fabrik-synced → re-distributed to ~45 projects on the manifest commit (governance-sync pre-commit hook). The grandfather strategy (above) makes this safe.
- Templates live in `templates/scaffold/docs/` (already the scaffold source of truth for the doc *bodies*); the registry adds the *which/when/who* metadata around them.

## Constraints

- **SSOT invariant:** after this, the `docs/` allowlist and the type-aware seed set are *derived* from `PROJECT_DOCS` — never a second hand-maintained copy. A future doc is added in ONE place (the registry).
- **Grandfather, don't migrate:** existing projects are not retro-edited; drift is tolerated advisory, not hard-failed.
- **`CLAUDE.md` Doc Sync Matrix stays human-readable** (a table), rendered to match the registry triggers — a future step MAY auto-generate it, but v1 keeps it hand-authored-but-aligned (avoid over-engineering).
- Fabrik conventions: kebab-case for new scripts; the new check carries the `# AFTER-EDIT:` coupling header; advisory registration (never blocks a project's gate on a doc-stub).

## Open / blocking unknowns

- **RESOLVED (operator, this turn):** type-aware seeding = yes; SaaS/product docs (`BUSINESS_MODEL`/`STRATEGIC_BACKLOG`/`FINANCIALS`) = SaaS-only; force-fill = build the placeholder-after-trigger WARN.
- **RESOLVED (decided, self-service):** registry home = `fabrik_synced_manifest.py` (1b); `FINANCIALS.md` stays a Traycer-workflow doc, **out of scope** for the per-project scaffold seed; `docs/README.md` trigger = "a doc added/removed"; the 3 phantom allowlist entries (`EXTERNAL_SYSTEMS`/`FAQ`/`TESTING`) are dropped from the derived allowlist but added to `LEGACY_TOLERATED` if any live project already carries them (Phase-1 grounding confirms which).
- **Still-open (non-blocking, for the plan to ground):** the exact placeholder-detection heuristic in `check_doc_stubs.py` (which sentinel strings + how to bound "trigger fired in this change") — an implementation detail for `/fabrik-plan-after-chat` to ground against `check_doc_sync.py`'s existing trigger-detection, not a design blocker.

## The canonical registry (starting content — the design's core artifact)

| Doc | Template | applies_to | Trigger (when to update) | Fills |
|---|---|---|---|---|
| `README.md` | `PROJECT_README_TEMPLATE.md` | universal | project identity change | scaffold-stub → agent |
| `INDEX.md` | `PROJECT_INDEX_TEMPLATE.md` | universal | file added/removed/renamed | agent |
| `docs/README.md` | `DOCS_INDEX_TEMPLATE.md` | universal | a doc added/removed | agent |
| `CHANGELOG.md` | `CHANGELOG_TEMPLATE.md` | universal | any code/Docker/deps change | agent |
| `AGENTS.md` | fabrik root / per-type `.j2` | universal | infra/topology change | scaffold |
| `AFCL.md` | `AFCL_TEMPLATE.md` | universal | friction hit | agent |
| `docs/QUICKSTART.md` | `QUICKSTART_TEMPLATE.md` | universal | API/SDK/CLI changed | agent |
| `docs/CONFIGURATION.md` | `CONFIGURATION_TEMPLATE.md` | universal | new env var (+ `.env.example`) | agent |
| `docs/TROUBLESHOOTING.md` | `TROUBLESHOOTING_TEMPLATE.md` | universal | recurring symptom | agent |
| `docs/FEATURES.md` | `FEATURES_TEMPLATE.md` | universal | feature shipped | agent |
| `docs/LESSONS_LEARNT.md` | `LESSONS_LEARNT_TEMPLATE.md` | universal | end of ticket/run | agent |
| `docs/workflows/kilo-consult-workflow.md` | `workflows/KILO_CONSULT_WORKFLOW.md` | universal | (static, synced) | scaffold |
| `docs/SERVICES.md` | `SERVICES_TEMPLATE.md` | deployed | service added/removed | agent |
| `docs/OPERATIONS.md` | `OPERATIONS_TEMPLATE.md` | deployed | service added/removed | agent |
| `docs/RESILIENCE.md` | `RESILIENCE_TEMPLATE.md` | deployed | resilience pattern changed | agent |
| `docs/DEPLOYMENT.md` | `DEPLOYMENT_TEMPLATE.md` | deployed (optional) | deploy config changed | agent |
| `PORTS.md` | (inline) | deployed | new port | agent |
| `db/schema.sql` | (scaffold sql) | data | schema migration | agent |
| `docs/data-contract.md` | `data-contract-template.md` | data | DB field/enum/model change | `/fabrik-data-contract` |
| `docs/ui-design.md` | (command-authored) | gui | screen/flow/UI change | `/fabrik-ui-design` |
| `docs/design-system.md` | (command-authored / adopt) | gui | brand/token change | `/fabrik-ui-design` |
| `docs/BUSINESS_MODEL.md` | `BUSINESS_MODEL_TEMPLATE.md` | saas | pricing/positioning change | agent/owner |
| `docs/STRATEGIC_BACKLOG.md` | `STRATEGIC_BACKLOG_TEMPLATE.md` | saas | Kilo-session findings | agent |

Retired: `API_REFERENCE_TEMPLATE.md`, `DATABASE_SCHEMA_TEMPLATE.md` → `templates/.archive/`. Out of scaffold scope: `FINANCIALS.md` (Traycer-workflow doc).

## Success criteria (testable)

1. `manifest.docs_allowlist()` returns the derived set; `check_structure.py` imports it (no hard-coded list) — a unit test asserts allowlist == registry-universal+deployed docs' basenames.
2. `scaffold.py` seeds type-aware: a test scaffolds a `python-api` (no `BUSINESS_MODEL`/`data-contract`/`ui-design`) and a `saas-skeleton` (gets them) and asserts the doc set per type.
3. No seeded doc WARNs on `check_structure` (registry ⊆ derived allowlist — the defect-1 class is gone).
4. `check_doc_stubs.py` WARNs on a placeholder-bearing doc whose trigger fired; is advisory (exit 0); fail-safe on any error.
5. `fabrik-plan-after-chat:240` no longer references `docs/DATABASE_SCHEMA.md`.
6. The 2 dead templates are in `templates/.archive/`; grep finds no live seed/allowlist reference to them.
