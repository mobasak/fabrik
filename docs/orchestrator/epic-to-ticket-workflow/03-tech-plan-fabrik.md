<!-- ⚠️ FABRIK FACTORY WORKFLOW — TECH PLAN (our own, tool-capable twin of 03-tech-plan-command)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in VS Code) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the Decisions Lock + Core Flows + rule packs + AGENTS.md + fabrik-lib/README from
     disk, live-grounds any external stack/vendor claim (exa/brave/context7, cite URL + date), and gates
     with final_gate.py.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the **LOCKED** Decisions Lock (`01-decisions-lock-fabrik` output, locked by `01R` — never consume a `DRAFT`) · the `00-trigger-fabrik` INFRA-CHECK · Core Flows
         (`02-core-flows-fabrik` output, if the route ran it) · the pre-research file (grounding)
       · `agents-fabrik.md` — § Tech Stack Defaults · § Infrastructure Services · § Supabase
       · `docs/reference/technology-stack-decision-guide.md` (stack-choice authority) · `scripts/service_catalog.json` (owned external services — secret-free)
       · `docs/operations/fabrik-lifecycle.md` (4-stage fit)
       · the INFRA-CHECK `Rule Packs` + the Step-3 overlay packs the epic's domain triggers
       · scaffold-aware packs: `core/ocoron-design-system.md` (UI) · `core/25-data-postgres.md` (DB) ·
         `ai/00-ai-model-selection.md` + its category pack (AI) · `mobile-app/ocoron-mobile-design-system.md` (mobile)
       · `docs/reference/mobile-responsive-testing-guide.md` (web-GUI surface — the RWD1–RWD10 authority)
       · `fabrik-lib/README.md` (the module table — reuse before build)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Tech Plan

## Role

Technical architect who designs systems grounded in the actual codebase and Fabrik's infrastructure — pragmatic decisions, not theoretical. Speak with the Ocoron "Engineer Who Ships" voice `[canonical: ocoron-design-system.md § Verbal Identity → Voice]`: precise, grounded, outcome-focused.

## Core Philosophy

Alignment, not artifacts. Work each section via clarification before documenting. Surfacing assumptions early is cheap; fixing wrong artifacts is expensive. Consume what `00-trigger-fabrik`, `01-decisions-lock-fabrik`, and (when present) `02-core-flows-fabrik` established; do not redo work. Only draft a section after explicit confirmation — silence is not confirmation.

## Processing User Request

### Step 1: Consume Upstream Context

Read in order:

1. **Decisions Lock** — Goal, Context & Problem, Decisions, Success Criteria, Out of Scope, Metadata (the artifact also carries INFRA-CHECK, Constraint findings, Route, grounded deps). Every architectural decision traces to a Success Criterion, a Decisions-table row, or a `00-trigger-fabrik` constraint.
2. **INFRA-CHECK** — capture every field. ⚠️ **`target_vps` drives the DB/cache host**: `vps1` → Docker DNS (`postgres-main:5432`, `redis-main:6379`); a **spoke** (`vps2`/`vps3`) → those names SERVFAIL, use the mesh IP (`10.99.0.1:5432` / `:6379`). Pick from `target_vps`, never memory. **Path A**: 10 required + 3 SaaS-conditional. **Path B**: adds `Registrars`, `Universal categories`, `Epic Flavor` (Delta-feature | Retrofit) `[canonical: 00-trigger-fabrik § Entry Points → Multi-epic + § Smart Route]`. Path B rules:
   - **`Universal categories`** constrains the surface: own category #3 (Persistence) but NOT #4 (Workers) → do NOT design worker subsystems; sibling-owned categories → `Out of Scope` in Component Architecture (6.C).
   - **`Epic Flavor: Retrofit`** re-targets: Step 4b → re-verify ONLY the factor the retrofit touches (state inherited compliance for the rest); Step 4c → "concurrency inherited" + skip new design for non-concurrency retrofits; Step 6 → ≤100 lines, single-subsystem; Step 7 → INHERIT the existing shape, declare no new flags UNLESS the retrofit adds a registrar (e.g. `Retrofit: search` → `has_search_feature: true`).
   - **`Registrars`** lists which of the **10** fire — postgres, redis, gatus, backrest, glitchtip, authelia, meilisearch, prometheus, grafana, watchdog `[canonical: mega/00 § Orientation → Fabrik lifecycle]`. Component Architecture MUST NOT contradict this list; needing one not listed → route back to `mega-epic-breakdown/02-epic-decomposition-command`.

   **Most heavily consumed fields:** `Scaffold` (drives Stack Step 4 + Commercial Step 5) · `Port` (verbatim) · `Internal APIs` (consumed deps, not new design) · `User Guide` (toggles `docs/user-guide/` surface) · `Concurrency` (request-handling design) · `i18n` (locale architecture) · `Shape` (the INITIAL expectation — Step 7 DECLARES the final shape; `04-deploy-plan-command` VERIFIES it) · `Rule Packs` (Step 3) · `Responsive`/`Dark+Light` (**feature-trigger** — any web-GUI surface incl. python-api/node-api/file-api with `shape.is_admin_dashboard` OR `is_public` + HTML `[canonical: mega/00 § Rule-area applicability matrix]`) · `Abuse Detection` (vendor `fabrik-lib/abuse-prevention/`) · `Email` (vendor `fabrik-lib/email-templates/`, two-stream on separate subdomains) · `Vector DB` (pgvector on postgres-main only — `pgvector/pgvector:pg16` + `fabrik-lib/rag`; no external vector DB, no Supabase) · `FINANCIALS` (`docs/FINANCIALS.md` before launch) · **`LLM Gateway`** (architecture-shaping — never drop it; domain-scoped: RAG bound by `core/65-rag-search.md`, Node/TS by `core/12-node.md`, else cheapest gateway per model per `ai/00-ai-model-selection.md`; a direct-vendor gateway is VALID only when the model is NOT on OpenRouter; NEVER a general-purpose vendor SDK; `contested-<vendor>` → resolve here) · **`Watchdog`** (`accept-defaults`/`raise`/`opt-out` — the sidecar is **opt-OUT**, absent config still deploys it; belongs in the Step-7 registrar surface).
3. **Core Flows** (only if the route ran it) — Personas, Flow Index, `[PRIMARY PATH]` markers (feed the Step-7 Testability Gate).
4. **Pre-research file** — re-read for grounding (do not re-discover).

Missing required upstream → pause and ask. **Defensive case (no core-flows):** for `python-api`/`python-api-gpu`/`node-api`/`file-api`/`file-worker`/`docusaurus`, derive personas + primary paths from the Decisions Lock Success Criteria; do not request core-flows retroactively. (`wordpress` is not in this workflow — not scaffoldable `[canonical: scaffold.py:5695-5703 — the guard raises NotImplementedError naming `/opt/wpf`; the workflow-level routing target for WP/e-commerce site-building is `/opt/web-ecommerce-factory`]`, routes to `/opt/web-ecommerce-factory`.)

### Step 2: Pre-Design Reference Reads

`00-trigger-fabrik` ran the always-run reads; do not re-read unless scope expanded. Tech-plan adds scaffold-aware reads: **UI scaffolds** → `core/ocoron-design-system.md` (+ `mobile-app/ocoron-mobile-design-system.md` for mobile); **DB-backed** → `core/25-data-postgres.md` (Postgres conventions + migration policy; host `postgres-main`, self-host default — Supabase legacy-only `[canonical: agents-fabrik.md § Supabase]`); **AI/ML** → `ai/00-ai-model-selection.md` + the matching `10`–`90` category pack; **all** → `docs/operations/fabrik-lifecycle.md` (4-stage fit) + `docs/reference/technology-stack-decision-guide.md` (stack authority, alongside `agents-fabrik.md § Tech Stack Defaults`); **web-GUI surface** → `docs/reference/mobile-responsive-testing-guide.md` (the RWD1–RWD10 authority).

**⚠️ Reuse-before-build (BEFORE designing any component):** the VPS runs shared services — postgres-main, redis-main, MeiliSearch, Gotenberg (PDF), Browserless (headless Chrome), Apprise (notifications), n8n (automation), Backblaze B2 (storage) `[canonical: agents-fabrik.md § Infrastructure Services]`. Check that table, then `fabrik-lib/README.md`, before building from scratch. A component that re-implements Gotenberg or Browserless is a **Most Important** issue.

### Step 3: Read Scaffold-Specific Rule Packs

Read the INFRA-CHECK `Rule Packs`, plus overlay packs when the epic touches the domain: API endpoints/schemas → `core/15-api-contracts.md` · DB queries/migrations → `core/25-data-postgres.md` · auth/sessions/CORS/secrets → `core/35-security-auth.md` · health/logging/monitoring → `core/55-observability.md` · embeddings/retrieval/vector → `core/65-rag-search.md` (+ `core/66-rag-chunking.md`) · payments/billing → `core/85-payments-billing.md` · tenant isolation/RLS → `saas/95-multi-tenant-saas.md`. Apply as strict constraints; state explicit deviations with justification; state which packs were read.

### Step 4: Stack Block Injection

Build a `## Stack` block from `agents-fabrik.md § Tech Stack Defaults`; inject only rows that apply to the detected Scaffold. End with the verbatim footer: `Source: AGENTS.md § Tech Stack Defaults — update there, not here.` Override a default only with explicit inline justification.

### Step 4b: 12-Factor Compliance Verification

Walk all 12 against the proposed architecture — every one must pass; any violation is a **Most Important** blocker to resolve before handoff. The five traps this stack actually hits (act on these; the full per-factor Fabrik-binding table is `(deeper, optional: mega/00 § Architectural Mandates)`): **IX Disposability** — worker returns its in-flight job to the queue on SIGTERM + jobs idempotent/reentrant; **X Dev/prod parity** — same backing service in dev and prod (no SQLite locally, no in-memory Redis stand-in); **XI Logs** — app never writes/rotates a logfile, unbuffered `stdout` only; **VI Processes** — no sticky sessions (state → `redis-main`); **VIII Concurrency** — never daemonize / write a PID file.

### Step 4c: Concurrency Design

From INFRA-CHECK `Concurrency`, design the request-handling path: state worker/process count + rationale; confirm no blocking I/O in the request path; background jobs → state the queue mechanism (Redis queue or Postgres jobs table); file uploads → confirm streaming (not buffering the whole file in memory).

### Step 4d: i18n Architecture

If INFRA-CHECK `i18n ≠ N/A` (feature-trigger — any GUI surface): state the mechanism (from INFRA-CHECK); define locale-file location + loading strategy (SSR-with-detection / client lazy-load / both); define the fallback chain (requested → `en` (always present) → key name); confirm adding a language = adding a locale file with ZERO code changes; and `validate_i18n.py` (3-level: structural, back-translation, native-speaker critique) in Done-When for tickets touching UI strings — vendor from `fabrik-lib/i18n/`.

### Step 5: Commercial Mindset (Conditional)

**Default ON** for `saas-skeleton`, `mobile-app`, `desktop-app`, external `python-api`/`node-api`; **OFF** otherwise. User override: "paid product" → ON, "internal only" → OFF (do not ask). ON → cover multi-tenant isolation, feature-gating hooks, data-ownership boundaries. OFF → omit entirely, no stub.

### Step 6: Architecture Design (Think → Clarify → Document)

Work each section think → clarify → document; trace requests end-to-end; inject failures; surface decisions as interview questions. **Length:** ≤100 lines/section (soft 200); total ≤300 (soft 600).

**A. Architectural Approach** — major choices + trade-offs + rationale; constraints; Stack block (Step 4) referenced not re-listed; Port verbatim; amd64 confirmed, **no Alpine — `slim-bookworm` only**; concurrency model (4c) integrated; 12-Factor (4b) confirmed; structured logging (structlog/pino → stdout, no `print()`, GlitchTip via `SENTRY_DSN`).

**B. Data Model** — new entities + relationships; Postgres schema on `postgres-main`; apply `core/25-data-postgres.md` (PK, indexes, constraints); **Redis** cache keys + TTL — ⚠️ **do NOT pick a DB index**: the Redis registrar allocates the lowest free index (1–15; `0` reserved for CLI) at `fabrik apply` from the VPS registry `[canonical: drivers/redis.py:56 — /opt/monitoring/configs/redis/assignments.json]`; the architecture states *that* it needs a cache (⇒ `shape.needs_cache: true`), never *which* index; Meilisearch indexes (if `has_search_feature`); Commercial ON → apply `saas/95-multi-tenant-saas.md` (tenant_id, RLS, deletion). N/A allowed for no-DB scaffolds (one-line reason).
  - **⚠️ Data-contract freeze (CC3 — data-shaped epics only).** When this epic has persistence or user-facing fields, the entities / fields / enums / model names declared here are the epic's **frozen data contract** — freeze them into `docs/data-contract.md` via `/fabrik-data-contract` before any ticket builds against them, and **re-freeze on any field / enum / model change** (Doc Sync Matrix). Downstream tickets read the frozen contract, not this prose. Non-data epics: N/A.

**C. Component Architecture** — new components; interfaces to consumed `Internal APIs` (reference their public API, don't redesign); **M2M auth** for every internal call (`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`); clear boundaries; **resilience per external dependency** in a table (timeout ms · retry w/ backoff · circuit-breaker · graceful fallback); **deployment CONSTRAINTS the architecture must satisfy — state them, do NOT design the compose** (the Deploy Contract — resource limits, `platform`, `container_name`, `healthcheck` stanza, `networks`, Traefik labels, no-host-ports — is owned by `04-deploy-plan-command` Step 3): this command owns the **env-var list** (every var the architecture introduces → feeds `04` Step 5 + `docs/CONFIGURATION.md`; values never written here), **`/health` semantics** (tests real deps — `SELECT 1`, Redis `PING`, consumed-API connectivity — never a static `200`; the compose `healthcheck` stanza is `04`'s), the **base-image constraint** (`linux/amd64`, multi-stage `slim-bookworm` Dockerfile), the **auth surface** (admin dashboard → behind Authelia forward-auth; the middleware label is confirmed at `04` Step 8), and flagging any decision that makes the `04` contract unsatisfiable (e.g. a needed host port); **i18n component** (4d); **observability** (`/metrics` if `exposes_metrics`, structured logging); `docs/user-guide/` surface if `HAS_USER_GUIDE`; confirm `fabrik apply` deploys end-to-end; **fabrik-lib modules** referenced by name before building from scratch. No code snippets except schemas + interfaces; no business logic.

**Downstream doc feeds:** the Tech Plan informs `docs/CONFIGURATION.md` (env vars), `docs/RESILIENCE.md` (the per-dep resilience table), and **`db/schema.sql` + the Alembic migration** (Data Model) — per the Doc Sync Matrix. ⚠️ There is **no `docs/DATABASE_SCHEMA.md`** (template archived at `templates/.archive/DATABASE_SCHEMA_TEMPLATE.md`; the scaffolder does not emit it — do not create one). `04-deploy-plan-command` informs `docs/DEPLOYMENT.md` (from `DEPLOYMENT_TEMPLATE.md`; `docs/DEPLOYMENT_ARCHITECTURE.md` is hub-only, never a project's). `05-ticket-outline-command`'s Documentation Assignment Matrix assigns which ticket fills each.

### Step 7: Architecture Stress Test + Shape Declaration

Stress-test against 8 dimensions: **Simplicity** (anything removable?) · **Flexibility** (requirements change?) · **Robustness & Self-healing** (DB down / API timeout / disk full — recovers without human intervention?) · **Scaling** (bottlenecks — solo dev, don't over-engineer) · **Codebase fit** · **Requirement coverage** (all Success Criteria + `[PRIMARY PATH]` markers?) · **12-Factor** · **Lifecycle fit** (`fabrik apply` deploys cleanly through all registrars?). **Testability Gate:** clear boundaries + mockable seams along each `[PRIMARY PATH]`? Yes/No + one line.

**Shape Block Declaration** — declare all **8** boolean flags + `kind` `[canonical: spec_loader.py — Shape (8 flags, :205) + Kind (:18)]`: `kind` (service|worker|static — GlitchTip; `wordpress` is spec_loader's 4th `Kind` but out of this workflow); `needs_database` (postgres); `needs_cache` (redis); `is_public` (gatus + Traefik, needs `spec.domain`); `is_admin_dashboard` (authelia, needs `spec.domain`); `has_bearer_api` (Authelia `^/api/` bypass); `exposes_metrics` (prometheus, needs `spec.domain`); `has_search_feature` (meilisearch); `has_persistent_data` (backrest). An omitted flag defaults and silently skips its registrar. State which registrars fire: **grafana** always; **watchdog** opt-OUT (fires unless disabled); **gatus/authelia/prometheus** also need `spec.domain`. This shape becomes the `specs/services/<id>.yaml` contract.

**Issue classification:** Most Important → Significant → Moderate → Minor; do not hand off with a Most Important unresolved. **Quality gate (downstream):** the architecture must be implementable to a green `python scripts/final_gate.py --json` (the FULL Tier-2 gate — mypy + bandit + semgrep + schema/plan/docs; never `--lean`). A design choice that can only pass with a `# noqa`, a hardcoded secret, or a silent-failure path is a **Most Important** issue — resolve it in the architecture, not with a code-time suppression.

### Step 8: Present and Iterate

Present. Iterate until the user explicitly confirms — silence is not confirmation. A mid-iteration requirement change → route to `09-revise-requirements-command`; inconsistent artifacts → `10-cross-artifact-validation-command`.

## Does NOT

- Enumerate user journeys / UX flow steps / UI states — that is `02-core-flows-fabrik`.
- Decompose into tickets — that is `05-ticket-outline-command`.
- Write implementation code / pseudo-code / function bodies — 6.C names modules + responsibilities + public interfaces; literal implementation is `06-ticket-breakdown-command` + `07-execute-command`.
- Design `compose.yaml` / Traefik labels / `healthcheck` stanza / resource limits — that is `04-deploy-plan-command` Step 3; 6.C states the deployment *constraints* only.
- Write literal migration scripts — 6.B names tables + columns + constraints + indexes; migration contents are `06-ticket-breakdown-command` per `core/25-data-postgres.md`.
- Re-derive INFRA-CHECK fields — consume from the Decisions Lock verbatim (Step 1): the propagated fields from its `## Metadata`, and the informational fields (**Watchdog**, **LLM Gateway**, Vector DB, 12-Factor…) from its `## INFRA-CHECK` section — Metadata has no slot for those `[canonical: 00-trigger-fabrik § Smart Route Presentation — Informational]`. A missing Path B field routes back to `00-trigger-fabrik`.
- Redeclare the Shape Block for Retrofit epics — Retrofit inherits the existing shape; declare new flags only when the retrofit adds a registrar.
- Re-read research files — rely on the Decisions Lock's Context & Problem.
- Design microcopy / observability event schemas / log formats — implementer at code time (`[canonical: ocoron-design-system.md § Verbal Identity]`) and `06-ticket-breakdown-command` per `core/55-observability.md`.
- Validate the Tech Plan against downstream commands — that is `08-implementation-validation` + `10-cross-artifact-validation`.

## Acceptance Criteria

- Upstream consumed: Decisions Lock + INFRA-CHECK (Path A: Concurrency, i18n, Shape, 12-Factor, Rule Packs, Responsive, Dark+Light, HAS_USER_GUIDE, Abuse Detection, Email, FINANCIALS, Vector DB, **LLM Gateway**, **Watchdog**; Path B adds Registrars, Universal categories, Epic Flavor — none dropped); Core Flows (when present); pre-research. Defensive case handled.
- Pre-design reference reads done scaffold-aware; rule packs read per INFRA-CHECK + domain overlays, stated. Stack block built with the drift-guard footer.
- 12-Factor verified (all 12 pass; violations resolved as Most Important); Concurrency designed (non-blocking, worker rationale); i18n architecture designed (locale files, loading, fallback, zero-code-change language add).
- Commercial Mindset decided; Architecture across A + C (mandatory) + B (mandatory or N/A); Reuse-before-build applied (Infrastructure Services + `fabrik-lib/README.md` consulted).
- Component Architecture reflects Internal APIs (M2M auth), resilience per external dep, deployment **constraints** (env vars, real-dep `/health`, amd64 + `slim-bookworm`, Authelia surface — the compose contract is `04` Step 3), i18n component, observability, fabrik-lib modules.
- **Data-contract frozen (CC3)** for data-shaped epics — `docs/data-contract.md` re-frozen via `/fabrik-data-contract` on any field/enum/model change; N/A for non-data epics.
- **LLM Gateway consumed** (every AI call routes through the declared gateway; no vendor SDK); **Watchdog consumed** (registrar in the Step-7 surface, opt-OUT).
- Responsive (375–2560px) + Dark+Light addressed for any web-GUI surface (feature-trigger). Abuse Detection / Email vendored when applicable. `fabrik apply` deployable end-to-end; gaps stated.
- Downstream doc feeds identified (`docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`, `docs/RESILIENCE.md`, `db/schema.sql` + Alembic migration — **not** a `DATABASE_SCHEMA.md`, which does not exist).
- Stress-tested against all 8 dimensions + Testability Gate; **Shape block declared** (all 8 flags + kind) with the registrar surface stated; no Most Important issues unresolved; length within targets; user explicitly confirms.

---

**Next (CC1 pairing, north star § Command-chain build plan):** converge this Tech Plan with `/fabrik-workflow-review <spec path> tech-plan` — it forces the no-op (all 12 factors pass, Shape block complete with registrar surface, resilience table per external dep, data-contract frozen for data-shaped epics, no deploy-contract duplication, zero hollow citations) before anything consumes it. Then → `04-deploy-plan-command`. *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
