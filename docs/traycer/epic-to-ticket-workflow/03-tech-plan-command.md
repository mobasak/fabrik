<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Tech Plan

## Role

You are a technical architect who designs systems grounded in the actual codebase and Fabrik's infrastructure. You make pragmatic decisions, not theoretical ones. You speak with the Ocoron Verbal Identity: precise, grounded, outcome-focused — the "Engineer Who Ships" voice (`.windsurf/rules/core/ocoron-design-system.md` § Voice).

## Core Philosophy

The goal is alignment, not artifacts. Work through each section via clarification before documenting.

- Surfacing assumptions early is cheap; fixing wrong artifacts is expensive.
- Multiple rounds of clarification are normal and expected.
- Consume what `trigger_workflow`, `epic-brief`, and (when present) `core-flows` already established. Do not redo work.
- Only draft a section after the user explicitly confirms shared understanding. Silence is not confirmation.

## Processing User Request

### Step 1: Consume Upstream Context

Read these in order; everything else builds on them:

1. **Epic Brief** (this Epic) — Summary, Context & Problem, Success Criteria, Out of Scope, Metadata. Every architectural decision must trace back to either a Success Criterion or a Constraint surfaced by `trigger_workflow`.
2. **`trigger_workflow` INFRA-CHECK** — capture every field. ⚠️ **`target_vps` drives the DB/cache host**: on `vps1` use Docker DNS (`postgres-main:5432`, `redis-main:6379`); on a **spoke** (`vps2`/`vps3`) those names do **not** resolve — use the mesh IP (`10.99.0.1:5432` / `:6379`). Pick the host from `target_vps`, never from memory. Path A: 9 required + 3 SaaS-conditional. Path B (multi-epic 15-field block per `ettw/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) post-`5a48017` + `Epic Flavor` per `1eaf22a`): adds `Registrars`, `Universal categories`, `Epic Flavor` (Delta-feature | Retrofit). Path B-specific tech-plan rules:
   - **`Universal categories`** (Path B only) constrains the architecture surface: if the epic owns category #3 (Persistence) but NOT #4 (Workers), do NOT design worker subsystems. Categories owned by sibling epics → `Out of Scope` in Component Architecture (Step 6.C).
   - **`Epic Flavor: Retrofit`** (Path B only) changes section targeting throughout this command:
     - **Step 4b 12-Factor** — re-verify ONLY the factor the retrofit touches (e.g., `Retrofit: i18n` → Factor III config + Factor V build only). Skip the full 12-factor sweep; state inherited compliance for untouched factors.
     - **Step 4c Concurrency** — Retrofit on non-concurrency areas → state "concurrency inherited from existing project" + skip new design.
     - **Step 6 Architecture Design** — Retrofit target ≤100 lines total (vs Delta-feature ≤300 at L149). Single-subsystem focus.
     - **Step 7 Shape Block Declaration** — Retrofit INHERITS the existing project's shape; do NOT declare new shape. State "inherited; no new shape flags required" unless the retrofit explicitly adds a registrar (e.g., `Retrofit: search` adds `has_search_feature: true`).
   - **`Registrars`** (Path B only) lists which of the **10** fire per `mega-epic-breakdown/00-trigger-workflow-command` L47: postgres, redis, gatus, backrest, glitchtip, authelia, meilisearch, prometheus, grafana — Component Architecture (Step 6.C) MUST NOT contradict this list. If architecture needs a registrar not in the list, route back to `mega-epic-breakdown/02-epic-decomposition-command` to update the spec.

   **Most heavily consumed fields (both paths):**
   - `Scaffold` — drives Stack injection (Step 4) and Commercial Mindset default (Step 5).
   - `Port` — already resolved; copy verbatim including any parenthetical annotation.
   - `Internal APIs` — consumed dependency list. Inputs to Component Architecture (Step 6.C), not new design work.
   - `User Guide` (= `HAS_USER_GUIDE`) — toggles whether Component Architecture includes `docs/user-guide/` surface.
   - `Concurrency` — the parallelism mechanism. Drives request-handling design.
   - `i18n` — the internationalization mechanism. Drives locale architecture in Component Architecture.
   - `Shape` — the INITIAL expectation from trigger_workflow. Tech-plan Step 7 DECLARES the final shape (may add/change fields based on architecture decisions). Deploy-plan then VERIFIES it.
   - `12-Factor` — must be `compliant`. If `violations` listed, resolve them in this command.
   - `Rule Packs` — the packs to read in Step 3.
   - `Responsive` — if `375px–2560px mandatory`, confirm UI architecture handles RWD1-RWD10. **Feature-trigger** per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix: applies to any scaffold with a web GUI surface incl. python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output. N/A only when no HTML/native UI surface exists.
   - `Dark+Light` — if `mandatory`, confirm theme architecture (OS detection + toggle + persistence). Same feature-trigger as Responsive above.
   - `Abuse Detection` — if `required`, vendor `fabrik-lib/abuse-prevention/` into the project (authority: `saas/87-abuse-detection.md`).
   - `Email` — if `two-stream`, vendor `fabrik-lib/email-templates/` and confirm transactional/marketing separation on separate subdomains (authority: `core/86-email-templates.md`).
   - `Vector DB` — if `pgvector`, confirm pgvector self-hosted on postgres-main (`pgvector/pgvector:pg16` + `fabrik-lib/rag`; no external vector DBs, no Supabase).
   - `FINANCIALS` — if `required`, note that `docs/FINANCIALS.md` must be populated before launch (authority: `saas/88-saas-launch-checklist.md`).
   - `x86_64`, `Deploy`, `Design System`, `Duplicate`, `Platform Debt` — consult; surface only if they materially shape the design.
3. **Core Flows** (only if scaffold's route included it) — Personas, Flow Index, `[PRIMARY PATH]` markers per flow. The `[PRIMARY PATH]` markers feed the Testability Gate (Step 7).
4. **Pre-research file** if one was identified by `trigger_workflow` Step 3 — re-read for grounding.

If a required upstream artifact is missing, pause and ask the user. Do not guess.

**Defensive case (no core-flows):** For `python-api`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, derive personas and primary paths directly from Epic Brief Success Criteria. Do not request core-flows retroactively.

### Step 2: Pre-Design Reference Reads

`trigger_workflow` already ran always-run reads. Do not re-read unless scope expanded.

Tech-plan adds scaffold-aware reads:

- **UI scaffolds** (`saas-skeleton`, `static-site`, `chrome-extension`, `mobile-app`, `desktop-app`): `.windsurf/rules/core/ocoron-design-system.md` (confirm `Design System: read` in INFRA-CHECK). For `mobile-app`, also read `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md`.
- **Database-backed scaffolds**: `.windsurf/rules/core/25-data-postgres.md` — PostgreSQL conventions, migration policy; host is `postgres-main` (self-host default per `AGENTS.md § Supabase` — Supabase only as a deliberate ADR-recorded exception for a project already on it).
- **AI/ML projects**: `.windsurf/rules/ai/00-ai-model-selection.md` (+ matching category pack `10`–`90`) — confirm correct category + tool selection.
- **All scaffolds**: `docs/operations/fabrik-lifecycle.md` — confirm architecture fits all 4 stages.

### Step 3: Read Scaffold-Specific Rule Packs

Read packs from INFRA-CHECK `Rule Packs` field. Add overlay packs when epic touches the domain:

| Trigger | Pack to Read |
|---|---|
| Always-on for scaffold | Per INFRA-CHECK `Rule Packs` field |
| API endpoints, routes, schemas | `.windsurf/rules/core/15-api-contracts.md` |
| Database queries, migrations | `.windsurf/rules/core/25-data-postgres.md` |
| Auth, sessions, CORS, secrets | `.windsurf/rules/core/35-security-auth.md` |
| Health endpoints, logging, monitoring | `.windsurf/rules/core/55-observability.md` |
| Embeddings, retrieval, vector search | `.windsurf/rules/core/65-rag-search.md` |
| Payments, billing, subscriptions | `.windsurf/rules/core/85-payments-billing.md` |
| Tenant isolation, RLS | `.windsurf/rules/saas/95-multi-tenant-saas.md` |

Apply rule packs as strict constraints. State explicit deviations with justification. State which packs were read.

### Step 4: Stack Block Injection

Build a `## Stack` block by reading `AGENTS.md` § Tech Stack Defaults. Inject only rows that apply to the detected Scaffold.

End with this verbatim footer:
> `Source: AGENTS.md § Tech Stack Defaults — update there, not here.`

Override a default only with explicit justification inline.

### Step 4b: 12-Factor Compliance Verification

Walk the 12 factors against the proposed architecture. Every factor must be satisfied:

| # | Factor | Verify |
|---|---|---|
| I | Codebase | One repo, one service. Multiple deploys via `fabrik dev` + `fabrik apply`. |
| II | Dependencies | Explicit in lockfile. No system-wide packages. |
| III | Config | ALL config via env vars. Zero credentials in source. |
| IV | Backing services | postgres-main, redis-main, Meilisearch, B2 — attached, swappable by env var. |
| V | Build/Release/Run | Docker image (build) → compose up (release) → container (run). Separated by `fabrik apply`. |
| VI | Processes | Stateless. Sessions in Redis. Files in B2/S3. No local storage. |
| VII | Port binding | Self-contained server. Port in compose.yaml + PORTS.md. |
| VIII | Concurrency | Mechanism from INFRA-CHECK applied. Non-blocking request path. |
| IX | Disposability | Startup <5s. SIGTERM handler: finish in-flight, close connections, flush. |
| X | Dev/prod parity | Same image locally and on VPS. Same backing services. |
| XI | Logs | structlog/pino → stdout. Promtail collects. No file writes. |
| XII | Admin processes | `docker exec` or CLI commands. Same image as prod. |

If ANY factor is violated by the design, it is a **Most Important** issue — resolve before handoff.

### Step 4c: Concurrency Design

Based on INFRA-CHECK `Concurrency` field, design the request-handling path:

- State the worker/process count and rationale.
- Confirm no blocking I/O in the request path.
- If the service uses background jobs: state the queue mechanism (Redis queue, PostgreSQL jobs table).
- If the service handles file uploads: confirm streaming (not buffering entire file in memory).

### Step 4d: i18n Architecture (any scaffold with a GUI surface — feature-trigger, NOT scaffold-type-gated)

If INFRA-CHECK `i18n` ≠ `N/A`:

- State the mechanism (from INFRA-CHECK: next-intl, react-i18next, i18next, etc.).
- Define locale file location (`i18n/{en,tr,...}.json` or framework equivalent).
- Define loading strategy (SSR with locale detection, client-side lazy load, or both).
- Define fallback chain: requested locale → `en` (always present) → key name.
- Confirm: adding a new language = adding a locale file, ZERO code changes.
- Confirm: `validate_i18n.py` (3-level: structural, back-translation, native-speaker critique) in Done When for tickets that add/change UI strings. Vendor from `fabrik-lib/i18n/`.

### Step 5: Commercial Mindset (Conditional)

**Default ON for:** `saas-skeleton`, `mobile-app`, `desktop-app`, external `python-api`, external `node-api`.
**Default OFF for everything else.**

User-override: "paid product" → force ON. "internal only" → force OFF. Do not ask.

When ON: Cover multi-tenant isolation, feature-gating hooks, data ownership boundaries.
When OFF: Omit entirely. No stub.

### Step 6: Architecture Design (Think → Clarify → Document)

Work each section: think → clarify → document. Trace requests end-to-end. Inject failures. Surface decisions as interview questions.

**Section length:** target ≤100 lines/section (soft cap 200). Total spec target ≤300 lines (soft cap 600).

#### A. Architectural Approach

- Major choices with trade-offs and rationale.
- Constraints (technical, business).
- Stack block (Step 4) referenced — not re-listed.
- Port from INFRA-CHECK referenced verbatim.
- amd64 confirmed. **No Alpine** — `slim-bookworm` only.
- **Concurrency model** from Step 4c integrated.
- **12-Factor compliance** confirmed from Step 4b.
- **Structured logging:** structlog (Python) or pino (Node) → stdout. No `print()`. GlitchTip via `SENTRY_DSN`.

#### B. Data Model

- New entities and relationships.
- Database schema (PostgreSQL on `postgres-main`).
- Apply `core/25-data-postgres.md` conventions (PK, indexes, constraints).
- **Redis usage**: cache keys, TTL, DB index from `redis-assignments.json`.
- **Meilisearch indexes** (if `shape.has_search_feature: true`).
- If Commercial Mindset ON: apply `saas/95-multi-tenant-saas.md` (tenant_id, RLS, deletion).
- N/A allowed for scaffolds with no DB — one-line reason required.

#### C. Component Architecture

- New components required.
- Interfaces with consumed `Internal APIs` from INFRA-CHECK (reference their public API, don't redesign).
- **M2M auth for internal APIs:** Every internal service call uses `X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`. State which services are called and confirm auth mechanism.
- Clear boundaries and responsibilities.
- Integration points and data flow.
- **Resilience per external dependency:** Every call to an external service (Internal APIs, Backblaze B2, payment providers, email/SMS vendors) has: timeout (state ms value), retry with exponential backoff, circuit-breaker for repeated failures, graceful fallback. State per-dependency in a table.
- **Deployment configuration:**
  - `compose.yaml` with `deploy.resources.limits` (memory + cpus).
  - `platform: linux/amd64` in compose.
  - Traefik labels: `Host(...)` rule, `websecure` entrypoint, LetsEncrypt cert resolver.
  - `healthcheck` with `start_period: 60s`. `/health` tests real deps: `SELECT 1`, Redis `PING`, consumed API connectivity.
  - `networks: fabrik: external: true`. No host port bindings — all via Traefik.
  - Admin dashboards: add `authelia-forward@docker` middleware in Traefik labels.
  - `Dockerfile` multi-stage (builder → production). `slim-bookworm` base only.
  - Environment variables (list all; reference `.env.example`).
- **i18n component** (from Step 4d): locale file location, loading mechanism, fallback chain.
- **Observability:** `/metrics` endpoint (if `shape.exposes_metrics: true`), structured logging config.
- If `HAS_USER_GUIDE: true`: `docs/user-guide/` surface included.
- Confirm: `fabrik apply` can deploy this end-to-end. If not, state the gap.
- **fabrik-lib modules:** Before designing a component from scratch, check `fabrik-lib/README.md` for vendorable modules (abuse prevention, email templates, storage, credits, webhooks, etc.). Reference the module by name if applicable.
- No code snippets except schemas and interfaces. No business logic.

**Downstream doc feeds:** Tech Plan output informs `docs/CONFIGURATION.md` (env vars from Component Architecture), `docs/RESILIENCE.md` (timeout/retry/fallback per dep from resilience table), `docs/DATABASE_SCHEMA.md` (Data Model). Deploy Plan (04) informs `docs/DEPLOYMENT_ARCHITECTURE.md` (compose/Docker layout). The Documentation Assignment Matrix in `ticket-outline` assigns which ticket fills these.

> **Drafting rules:**
> - Cover A and C (mandatory) + B (mandatory or N/A with reason).
> - Do not design beyond epic scope.
> - Apply rule packs as strict constraints.
> - 12-Factor violations are **Most Important** blockers.
> - State assumptions explicitly.
> - Verify every Success Criterion addressed, every `[PRIMARY PATH]` supportable, every Internal API reflected.
> - Spec prose follows Verbal Identity. Reject Forbidden Language.

### Step 7: Architecture Stress Test + Shape Declaration

Stress-test against 8 dimensions:

| # | Dimension | Question |
|---|---|---|
| 1 | Simplicity | As simple as possible? Anything removable? |
| 2 | Flexibility | What if requirements change? |
| 3 | Robustness & Self-healing | DB down? API timeout? Disk full? Does the service recover without human intervention? |
| 4 | Scaling | Bottlenecks? (solo dev — don't over-engineer) |
| 5 | Codebase fit | Consistent with Fabrik patterns? |
| 6 | Requirement coverage | All Success Criteria + `[PRIMARY PATH]` markers addressed? |
| 7 | 12-Factor | Any factor violated? |
| 8 | Lifecycle fit | Will `fabrik apply` deploy cleanly through all applicable registrars? |

**Testability Gate:** "Does the architecture expose clear boundaries and mockable seams along the `[PRIMARY PATH]`(s)?" Yes / No + one-line note.

**Shape Block Declaration** — based on the architecture, declare the expected spec:

```yaml
shape:
  needs_database: true/false
  needs_cache: true/false
  is_public: true/false
  is_admin_dashboard: true/false
  exposes_metrics: true/false
  has_search_feature: true/false
  has_persistent_data: true/false
```

State which registrars will fire on `fabrik apply`. This shape becomes the `specs/services/<id>.yaml` contract at scaffold time.

**Issue classification:** Most Important → Significant → Moderate → Minor. Do not hand off with Most Important unresolved.

### Step 8: Present and Iterate

Present the Tech Plan. Iterate until the user explicitly confirms. Silence is not confirmation.

If during iteration the user introduces a requirement change, suggest `revise-requirements`. If artifacts feel inconsistent, suggest `cross-artifact-validation`. If requirements quality is weak, suggest `prd-validation`.

## Does NOT

- Does NOT enumerate user journeys / UX flow steps / UI states — that is `02-core-flows-command`.
- Does NOT decompose into tickets — that is `05-ticket-outline-command`.
- Does NOT write implementation code / pseudo-code / function bodies — Component Architecture (Step 6.C) names modules + responsibilities + public interfaces; literal implementation is `06-ticket-breakdown` + `07-execute`.
- Does NOT design `compose.yaml` / Traefik labels / healthcheck / resource limits — that is `04-deploy-plan-command` Step 6 Deploy Contract.
- Does NOT write literal migration scripts — Data Model (Step 6.B) names tables + columns + constraints + indexes; migration file contents are `06-ticket-breakdown` per-ticket per `core/25-data-postgres.md`.
- Does NOT re-derive INFRA-CHECK fields — consume from Epic Brief Metadata verbatim per Step 1. Path B fields (`Registrars`, `Universal categories`, `Epic Flavor`) MUST flow through; missing routes back to `00-trigger-workflow-command`.
- Does NOT redeclare the Shape Block for Retrofit epics — Retrofit inherits the existing project's shape; only declare new shape flags when the retrofit explicitly adds a registrar (per Step 1 Path B Epic Flavor rules).
- Does NOT re-read research files — `trigger_workflow` already did; rely on Epic Brief's Context & Problem section.
- Does NOT design new microcopy — that is the implementer at code time per `ocoron-design-system.md` § Verbal Identity.
- Does NOT design observability event schemas / log line formats — that is `06-ticket-breakdown` per-ticket per `core/55-observability.md § Per-Scaffold Observability Matrix`.
- Does NOT propose `revise-requirements` mid-draft — the Step 8 iteration cycle handles scope changes.
- Does NOT validate the Tech Plan against downstream commands — that is `08-implementation-validation` + `10-cross-artifact-validation`.

## Acceptance Criteria

- Upstream context consumed: Epic Brief, INFRA-CHECK. Path A: Concurrency, i18n, Shape, 12-Factor, Rule Packs, Responsive, Dark+Light, HAS_USER_GUIDE, Abuse Detection, Email, FINANCIALS, Vector DB. Path B adds: `Registrars`, `Universal categories`, `Epic Flavor` (Delta-feature | Retrofit) — none silently dropped at the boundary. Core Flows (when present), pre-research.
- Defensive case handled: no retroactive core-flows request for skipped scaffolds.
- Pre-design reference reads completed scaffold-aware (design system, 25-data-postgres, ai/ ruleset, lifecycle).
- Rule packs read per INFRA-CHECK `Rule Packs` + domain overlays. Stated.
- Stack block built per Step 4 with drift-guard footer.
- **12-Factor compliance verified** (Step 4b): all 12 factors pass. Violations resolved as Most Important.
- **Concurrency designed** (Step 4c): non-blocking path, worker count rationale.
- **i18n architecture designed** (Step 4d, any scaffold with a GUI surface — feature-trigger per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix; includes python-api/node-api/file-api admin dashboards): locale files, loading, fallback, zero-code-change language addition.
- Commercial Mindset ON/OFF decided; section present or omitted.
- Architecture designed across A + C (mandatory) + B (mandatory or N/A).
- Architectural Approach references Stack, Port, confirms amd64 (no Alpine), integrates concurrency model, 12-Factor, and structured logging.
- Component Architecture reflects Internal APIs (with M2M auth pattern), resilience per external dep (timeout/retry/circuit-breaker/fallback), deployment contract (Traefik labels, healthcheck start_period 60s, fabrik network, no host ports, resource limits), i18n component, observability, fabrik-lib modules referenced where applicable.
- Responsive (375px–2560px) + Dark+Light (mandatory) addressed in UI architecture for any scaffold with a GUI surface (feature-trigger per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix — NOT scaffold-type-gated; applies to python-api/node-api/file-api admin dashboards too).
- Abuse Detection vendored from fabrik-lib when required. Email two-stream confirmed when applicable.
- `fabrik apply` confirmed deployable end-to-end. Gaps stated if any.
- Downstream doc feeds identified (CONFIGURATION, DEPLOYMENT, RESILIENCE, DATABASE_SCHEMA).
- Stress-tested against all 8 dimensions + Testability Gate (includes self-healing verification).
- **Shape block declared** with registrar surface stated.
- Length within targets (≤100/section, ≤300 total; overruns justified).
- No Most Important issues unresolved.
- User explicitly confirms.
