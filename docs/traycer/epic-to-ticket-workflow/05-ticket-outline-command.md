<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Ticket Outline

## Role

You are a technical project manager who maps the full epic into a **maximum-parallelism dependency graph**. You produce the MAP; `ticket-breakdown` (run in batches) produces the DETAIL.

## Core Philosophy

- **CHEAP and FAST.** Output ≤100 lines for a 20-ticket epic.
- **MAXIMIZE parallelism — this is the #1 design goal.** Every ticket that CAN run parallel MUST be marked parallel. Sequential chains are expensive (1 agent waiting = wasted time). The ideal outline has wide batches (4-5 parallel tickets) and short chains (2-3 sequential links). If your outline has more than 3 sequential hops from first to last ticket, justify why or redesign.
- **Respect the 4-stage lifecycle.** Tickets naturally fall into: foundation (scaffold/schema/config) → implementation (endpoints/logic) → integration (wiring/deploy) → closure (validation/docs). Group accordingly.
- Get STRUCTURE right. Names, scopes, dependencies, parallel lanes, batches.
- Do NOT write Steps, Acceptance Criteria, or governance plumbing — that's `ticket-breakdown`'s job.
- Consume upstream context; do not redo work.
- Only proceed when user confirms. Silence is not confirmation.

**Parallelism budget:** After drafting, count: `total tickets` vs `longest sequential chain`. The ratio is your parallelism score. Target: **≥3:1** (e.g. 15 tickets with longest chain of 5 = 3:1). Below 2:1 = redesign the graph to break unnecessary dependencies.

## Processing User Request

### Step 1: Consume Upstream

Read (in order):
1. **Epic Brief** — Success Criteria (each must map to ≥1 ticket), Out of Scope (hard boundary), Metadata (Scaffold, Shape, Concurrency, i18n, Rule Packs).
2. **Core Flows** (when present) — `[PRIMARY PATH]` markers, Flow Index.
3. **Tech Plan** — Component Architecture, Data Model, Issue classification, Shape Block Declaration, resilience table.
4. **Deploy Plan** — Shape confirmation, registrar surface map, env vars checklist, compose contract.
5. **INFRA-CHECK** — Internal APIs (consumed, not built), Port, User Guide, Concurrency, i18n, Shape.
6. `docs/operations/fabrik-lifecycle.md` — confirm tickets cover all 4 stages.

**Feature for existing project:** If `trigger_workflow` classified this as a feature (not a new project), the outline covers ONLY the feature scope — not the entire existing project. Consume the existing project's `specs/services/<id>.yaml` to understand current shape; new tickets may ADD shape fields but never remove.

**Two-faced types** (`chrome-extension`, `mobile-app`, `desktop-app`): tickets split into backend lane (deploys to VPS) and client lane (builds locally / ships to store). These lanes are naturally parallel.

**Multi-epic dispatch mode (from `mega-epic-breakdown`):** If this command was invoked downstream of `mega-epic-breakdown/05-dispatch-epic-tickets-command` (i.e., `epic-to-ticket-workflow/00-trigger-workflow-command` ran in **consume mode** per its § Entry Points → Multi-epic (consume mode)), additional rules apply:

- **15-field Metadata** is inherited verbatim from the dispatched epic ticket: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS. Carry forward to every ticket Metadata field; do NOT re-derive.
- **Universal categories** (1–14, comma-separated, inherited from the ticket's Metadata field per `mega-epic-breakdown/02-epic-decomposition-command` sub-step 2h) constrain the scope of THIS outline: only the categories this epic owns may yield tickets; categories owned by sibling epics are out-of-scope and become `Out of Scope` lines on every ticket that might touch them.
- **Epic flavour** is determined by the ticket Title prefix from `mega-epic-breakdown/03-expand-epic-files-command`:
  - **Delta-feature epic** (Title `Epic N — <feature area>`) → default behaviour, target 8–12 tickets for a 5-8 Success Criteria epic.
  - **Retrofit epic** (Title `Epic N — Retrofit: <area>`, e.g. `Retrofit: i18n`, `Retrofit: Resilience on YouTube Data API`) → smaller outline, target **3–5 tickets** for a 3–5 Success Criteria retrofit; DO NOT pad to delta-feature size. Epic Closure ticket is **OPTIONAL** for Retrofit epics — only include if the retrofit genuinely needs a project-wide systemic gate (most retrofits are scoped to one rule-pack area and the gate is inherited from the parent project's last delta-feature epic closure).
- **Out of Scope (vision level)** — every ticket inherits `mega-epic-breakdown/00-trigger-workflow-command` Vision Summary § Out of Scope. Tickets that would touch a vision-level exclusion are NOT allowed; raise this back to mega-epic-breakdown via `revise-requirements`.

### Step 2: Identify Work Units + Parallel Lanes

Group by component, layer, or flow — then **optimize for parallelism:**

**Lane identification:** Find work units that share NO dependencies on each other. These form parallel lanes — independent streams that different agents execute simultaneously.

Common parallel patterns in Fabrik projects:
- **Backend API + Frontend UI** — separate agents, merge at integration ticket.
- **DB schema + API stubs** — schema lands first (5 min), then multiple endpoint tickets in parallel.
- **Multiple independent endpoints** — /users, /products, /orders can be built simultaneously if they share no tables.
- **i18n locale files + business logic** — locale structure is independent of logic.
- **Observability (/metrics + /health + logging) vs business logic** — observability ticket runs parallel to feature tickets.
- **Docs (CONFIGURATION, DEPLOYMENT, RESILIENCE)** — can run parallel to implementation if source info exists in Tech Plan/Deploy Plan.
- **Tests + implementation** — test SETUP (fixtures, factories) can run parallel to the code it will test.

**Parallelism maximization techniques:**

- **Split, don't merge.** If one ticket has 2 independent sub-tasks, split into 2 parallel tickets.
- **Interface-first.** A shared interface ticket (types, schemas, contracts) enables all consumers to work in parallel after it completes.
- **Narrow the critical path.** The critical path is the longest sequential chain. Find it. Ask: "Can any ticket on this chain be split so part of it runs earlier or in parallel?"
- **Foundation tickets should be SMALL and FAST.** The sooner foundation completes, the sooner the wide parallel batch starts. A 5-minute schema migration unlocks 5 parallel implementation tickets.

**Parallelism validation rule (HARD):**

> A ticket CANNOT be ⚡ (parallel) with any ticket it lists in `Depends`. If T5 depends on T3, T5 runs AFTER T3 — never simultaneously. Violating this = broken build.

To verify: for every ticket marked `Parallel: ⚡ with TX`, confirm TX does NOT appear in that ticket's `Depends` field AND that ticket does not appear in TX's `Depends` field. This is a bidirectional check.

**The mermaid diagram (Step 4) is the visual proof.** If an arrow connects two tickets, they are sequential. If no arrow connects them AND they're in the same subgraph, they are parallel. The diagram must be consistent with the Depends/Parallel fields — if they contradict, the diagram is authoritative (fix the fields).

**Anti-patterns:**
- Do NOT create artificial sequential chains where none exist.
- Do NOT merge independent work into one ticket "for simplicity" — this KILLS parallelism.
- Do NOT over-decompose (20 one-function tickets defeat batch efficiency).
- Do NOT mark tickets as parallel when one WRITES to a file/table/config that the other READS — even if not listed as explicit dependency, shared state = sequential.
- If ambiguous scope boundaries: state assumption.

### Step 2b: Ticket Category Coverage Check

Before drafting, check which categories apply to this project. Every applicable category MUST have at least one ticket. The scaffold type + shape block determines which are mandatory:

| Category | When Mandatory | What It Covers | Rule Pack |
|---|---|---|---|
| **DB Schema & Migrations** | `shape.needs_database: true` | Schema design, migration files, seed data, indexes, constraints | `core/25-data-postgres` |
| **Cache & Queue** | `shape.needs_cache: true` OR async jobs | Redis key design + TTL, OR PostgreSQL job queue (`SKIP LOCKED`), dead-letter handling | `75-workers-jobs` |
| **API Endpoints** | python-api, node-api, saas-skeleton backend | Route handlers, request validation, response schemas, versioning | `15-api-contracts` |
| **Internal API Consumption** | INFRA-CHECK `Internal APIs ≠ none` | M2M auth (`X-Internal-Token`), client wrappers with timeout/retry/circuit-breaker | `35-security-auth` + `core/58-resilience` |
| **External Service Integration** | Any external dep (Backblaze B2, Paddle, Cloudflare, Gotenberg, Browserless, SMTP; Supabase only for a legacy/migration project already on it per `AGENTS.md § Supabase`) | Client setup, credential config, resilience per dep, fallback, vendor balance checks | `core/58-resilience` |
| **Background Workers** | file-worker, file-api, any async processing | Queue consumer (PG `SKIP LOCKED` or Redis), idempotency keys, retry/backoff, dead-letter, orphan sweep | `75-workers-jobs` |
| **GUI / Frontend** | Any scaffold exposing a user/admin GUI surface — saas-skeleton, static-site, docusaurus front, chrome-extension popup, mobile-app, desktop-app, AND python-api/node-api/file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` with HTML output (feature-trigger per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix — NOT scaffold-type-gated). Brings i18n + Responsive (375px floor) + Dark+Light mandates with it. | Components, pages, state management, routing, 5 UI states, Ocoron design system | `saas/60-saas-ui` / `70-chrome-ext` / `80-mobile` |
| **i18n Setup** | INFRA-CHECK `i18n ≠ N/A` | Locale files (en + tr), language switcher, locale-aware formatting (dates/numbers/plurals), fallback chain | (from tech-plan Step 4d) |
| **Auth & Security** | Any user-facing or admin-dashboard service | Login/signup, session management (Redis), Authelia forward-auth, M2M tokens, CORS, CSP | `35-security-auth` |
| **Observability Configuration** | ALL scaffolds (non-negotiable) | Configure pre-scaffolded logging (structlog/pino already emitted by scaffold), add correlation IDs to new endpoints, configure GlitchTip DSN, add custom business metrics beyond scaffold defaults. **Do NOT create logger/metrics modules from scratch — scaffold already emits them.** | `55-observability` |
| **Health Endpoint** | ALL `is_public` scaffolds | `/health` must test ALL real deps (DB `SELECT 1`, Redis `PING`, consumed API connectivity). Scaffold emits the endpoint skeleton; ticket fills in dep checks. | `55-observability` |
| **Resilience & Self-Healing** | Any service with external calls | Timeout + retry + circuit-breaker per dep, graceful degradation, `docs/RESILIENCE.md` filled. **Workers additionally:** pause-state (sliding TTL), queue-bloat prevention (5 mechanisms), orphan sweep, vendor balance checks. | `core/58-resilience` |
| **Deployment & Compose** | ALL VPS-deployed scaffolds | Dockerfile (slim-bookworm), compose.yaml (Traefik labels, healthcheck, resource limits, fabrik network, platform: linux/amd64), `.env.example`. **Scaffold emits compose skeleton; ticket fills in service-specific labels/env/limits.** | `30-ops` |
| **Backup & Data Safety** | `shape.has_persistent_data: true` | Backrest plan → B2, retention policy, restore test procedure | `30-ops` |
| **Search** | `shape.has_search_feature: true` | MeiliSearch index creation, indexing pipeline, search endpoint, reindex strategy | `core/65-rag-search` + `core/66-rag-chunking` |
| **Notifications & Alerts** | Any service sending alerts/emails/push | Apprise integration, email/push templates, notification preferences, delivery failure handling | (project-specific) |
| **Payments & Billing** | Commercial products with paid features | Paddle/iyzico integration (Stripe NOT available to TR entities), webhook handling, subscription lifecycle, receipt generation | `core/85-payments-billing` |
| **Multi-Tenancy** | Commercial SaaS with tenant isolation | tenant_id on all tables, RLS policies, tenant-scoped queries, data export/deletion per tenant | `saas/95-multi-tenant-saas` |
| **Automation & Webhooks** | Services receiving/sending webhooks, n8n integration | Webhook endpoint, signature verification (see `core/85-payments-billing.md`), timeout/retry (see `core/58-resilience.md`), n8n workflows configured in n8n UI | `core/58-resilience` + `core/85-payments-billing` |
| **GPU / AI Inference** | Service provisions or consumes GPU compute for inference, training, or fine-tuning | Provider selection (RunPod/Modal/Vast.ai vs managed API), model serving (vLLM/SGLang), quantization, checkpointing, cost control | `76-gpu-workers` |
| **Docusaurus Site** | docusaurus scaffold | Docusaurus config, sidebars, MDX content, i18n integration, deployment | `42-docusaurus` |
| **AI Agent / Prompt Design** | Ticket creates new system prompts, Kilo skills, agent definitions, or review templates | Prompt structure, output contracts, validation rules, agent memory patterns | `docs/reference/MD/ai-prompt-templates.md` + `docs/reference/ai_agent_prompt_directives.md` |
| **Kilo Integration** | Ticket involves calling Kilo CLI programmatically or adding new Kilo use cases | Liveness monitoring, JSONL parsing, retry patterns, model routing, cost tracking | `docs/reference/kilo/KILO_CLI_REFERENCE.md` + `docs/reference/kilo/KILO_USE_CASES.md` |
| **Testing** | ALL (one integration test per PRIMARY PATH) | Test setup (fixtures, factories), integration test per primary path, regression tests for bugfixes | `45-testing-strategy` |
| **Documentation** | ALL (per Documentation Sync Matrix) | Fill scaffolded doc templates assigned in Step 6b | `40-documentation` + `docs/reference/MD/markdown-cheatsheet.md` |
| **Audit log (tenant-scoped, immutable)** | Any service writing sensitive ops (auth events, billing mutations, admin actions, GDPR data-rights flows, KVKK destruction trail) — applies regardless of scaffold type | Hash-chained audit table per `core/app-audit-log.md` (vendored `/opt/fabrik-lib/app-audit-log/`), `prev_hash` + `current_hash` columns via BEFORE INSERT trigger, quarterly `verify_chain()` schedule | `core/app-audit-log.md` |
| **Watchdog sidecar + cost-budget** | Any service calling paid LLM APIs in an unattended loop / scheduled job / re-fire-without-approval flow (per `mega-epic-breakdown/00-trigger-workflow-command` N3i #19) | Watchdog sidecar is **ON by default** — **opt-OUT** via `watchdog: { enabled: false }` (`infrastructure.py:314` reads `watchdog_cfg.get("enabled", True)`; a spec with NO `watchdog:` block still fires it). Declare `daily_budget_usd` + `daily_invocations_cap` caps | `core/60-watchdog.md` + `core/cost-budget.md` |
| **KVKK / GDPR data residency** | Any service storing user PII or file blobs (TR-resident operator default; international cross-border opt-out) | Data residency follows self-hosted infra location — `postgres-main` on an EU-region VPS (Frankfurt default) + B2 EU bucket via `fabrik-lib/storage`, `file_erasure_audit` hash-chained table with 3-year retention (file-api), Article 11 hard-delete sweeper ≤6-month interval, telemetry opt-in only | `core/67-file-api.md` + `mobile-app/80-mobile.md` + `desktop-app/72-desktop.md` |
| **Email two-stream (transactional ↔ marketing)** | Any service that sends both transactional AND marketing email | Separate streams on separate subdomains (mail.<domain> vs news.<domain>), Resend transactional + Listmonk/SES marketing at scale, MJML+Jinja2 templates | `core/86-email-templates.md` |
| **Abuse detection (SaaS free-tier signup gating)** | saas-skeleton OR any scaffold with a free-tier signup surface (independent of "Auth & Security" category which covers session management only) | IP rate limit, disposable email block (kickbox API), progressive unlock, captcha escalation for repeat offenders | `saas/87-abuse-detection.md` |
| **Epic Closure** | Delta-feature epics: ALL (always last ticket). Retrofit epics: OPTIONAL — only include if the retrofit genuinely needs a project-wide systemic gate; most retrofits inherit closure from the parent project's prior delta-feature closure. | Tier 3 systemic gate, `fabrik verify`, `fabrik audit-registrars`, full validation | (cross-cutting) |

**What the scaffold already provides (do NOT ticket these from scratch):**

Per `AGENTS.md` § "What every API scaffold emits automatically": `internal_auth.py` (M2M auth), `metrics.py` + `/metrics` endpoint, `glitchtip_init` (Sentry SDK), structured logging module (`logger.py`/`logger.js`), `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`. Tickets should CONFIGURE/EXTEND these, not recreate them.

**Usage:** After drafting tickets in Step 3, cross-check: every row marked "mandatory" for this project has ≥1 ticket covering it. Missing category = missing ticket.

**Combining categories:** Related categories with the SAME dependency chain can share one ticket. Example: "Observability Configuration" + "Health Endpoint" → one "Observability" ticket (both depend on service skeleton, no external deps between them). Large categories (API endpoints with 10+ routes) should be split into parallel tickets by resource/domain. Never merge categories that have DIFFERENT dependency chains — this kills parallelism. The table says "mandatory" meaning the WORK must be done, not that it must be a separate ticket.

### Step 3: Draft the Outline

For each ticket produce ONLY:

```
T<N> — <Title (action-oriented imperative)>
  Scope: <1-2 sentences — in/out>
  Depends: <T1, T3> or <none>
  Parallel: <⚡ with T2, T4> or <⛓️ after T3>
  Stage: <foundation | implementation | integration | closure>
  Category: <from Step 2b table — determines rule pack for ticket-breakdown>
  Gate: <1 (lean) | 2 (full)>   # ⚠️ the CODING-TIME tier ONLY. A ticket's **Final Gate Instruction** is Tier-2 `--json` (or Tier-3 `--systemic --json` for the **Epic Closure** ticket) — `--lean` is **never** a completion gate (`CLAUDE.md` § Completion Contract)
  Touches: <PRIMARY PATH flow> or <none>
  Shape: <shape fields affected> or <N/A>
  Complexity: <simple | complex | critical>
  Docs: <which scaffold docs this ticket fills, or none>
  Lessons: <trigger condition if applicable, or none>
```

**Gate tiers** (from `scripts/final_gate.py`):

- **1 (lean):** `--lean --json` — **during coding only**. Fast checks. ⚠️ **Never** a ticket's Final Gate Instruction.
- **2 (full):** `--json` — at milestone/schema/auth tickets. Full checks including spec validation.
- Epic Closure always runs **Tier 3** (`--systemic --json`) — repo-wide health.

**CHANGELOG rule:** Every ticket that ships code MUST add one entry to `CHANGELOG.md` under `## [Unreleased]`. The outline does NOT specify this per-ticket (it's universal) — `ticket-breakdown` enforces it.

**Lessons Learnt field:** Mark `trigger condition` when the ticket involves: auth changes, password/secret rotation, deploy/compose workaround, new registrar interaction, external service integration, or any high-risk area. `ticket-breakdown` enforces the actual entry in `docs/LESSONS_LEARNT.md` — outline just flags which tickets are likely to produce lessons.

Rules:
- Titles are action-oriented imperatives.
- Scope is 1-2 sentences max.
- **Parallel field is mandatory** — explicitly state which other tickets can run simultaneously.
- Stage maps to lifecycle: foundation (Stage 1 setup), implementation (Stage 2 code), integration (Stage 3 deploy-ready), closure (Stage 4 validation).
- Complexity hints at agent selection: simple → free/local agent (Kilo CLI, Windsurf local), complex → mid-tier (Windsurf Cascade), critical → premium (Claude Code Opus). User picks final assignment in `ticket-breakdown`.
- **Docs field:** Each scaffolded doc template (CONFIGURATION, FEATURES, QUICKSTART, API_REFERENCE, DEPLOYMENT, RESILIENCE, DATABASE_SCHEMA, TROUBLESHOOTING, BUSINESS_MODEL) must be assigned to exactly one ticket. An empty template at epic end = governance failure.
- Every Epic Brief Success Criterion maps to at least one ticket.
- Every Tech Plan component maps to at least one ticket (or excluded with reason).
- LAST ticket is "Epic Closure — Tier 3 systemic gate" for **delta-feature** epics. For **Retrofit** epics it is **OPTIONAL** — per § Step 2b's Epic Closure row; most retrofits inherit closure from the parent project's prior delta-feature closure.

### Step 4: Parallel Dependency Diagram

Generate a mermaid graph showing **parallel lanes** clearly:

```mermaid
graph TD
  subgraph "Foundation (Batch 1 — all parallel)"
    T1[T1: DB schema + migrations]
    T2[T2: Project config + env setup]
    T3[T3: i18n locale structure]
  end

  subgraph "Implementation (Batch 2 — parallel lanes)"
    T4[T4: User endpoints]
    T5[T5: Product endpoints]
    T6[T6: Observability setup]
  end

  subgraph "Integration (Batch 3)"
    T7[T7: Wire frontend to API]
    T8[T8: Deploy config + compose]
  end

  subgraph "Closure (Batch 4)"
    T9[T9: Epic Closure]
  end

  T1 --> T4
  T1 --> T5
  T2 --> T4
  T2 --> T5
  T3 --> T7
  T4 --> T7
  T5 --> T7
  T6 --> T8
  T7 --> T9
  T8 --> T9
```

The diagram MUST use `subgraph` to visually group parallel-eligible tickets.

### Step 5: Batch Proposal (optimized for parallelism)

Group into batches of **3-5**, maximizing parallel tickets per batch:

```
Batch 1: T1 ⚡ T2 ⚡ T3 (foundation — ALL parallel, zero mutual deps)
  → 3 agents run simultaneously. Time = longest single ticket, not sum of all three.

Batch 2: T4 ⚡ T5 ⚡ T6 (implementation — ALL parallel after Batch 1)
  → 3 agents simultaneously. Each depends on Batch 1 but NOT on each other.

Batch 3: T7 ⛓️ T8 (integration — T7 first, then T8 needs T7's output)
  → Sequential within batch. 2 agents total but ordered.

Batch 4: T9 [Epic Closure] (depends on all)
  → 1 agent, runs systemic gate.
```

Rules:
- Each batch is 3-5 tickets (never more than 5).
- **Maximize ⚡ (parallel) within each batch.** If a batch has 5 tickets and 4 are parallel → that's a 4x speedup.
- Batch ordering respects dependencies (no batch references an undetailed ticket from a later batch).
- First batch is always zero-dependency foundation (highest parallelism potential).
- Last batch always contains Epic Closure.
- State the **expected time savings** from parallelism: "Batch 2: 3 tickets ⚡ = ~1 ticket time instead of 3x."

### Step 6: Lifecycle Stage Distribution

Verify the tickets cover all applicable lifecycle stages:

| Stage | What it covers | Expected tickets |
|---|---|---|
| Foundation | Schema, config, env, scaffold setup, i18n structure | 2-4 (usually all parallel) |
| Implementation | Endpoints, business logic, UI components, workers | 5-12 (maximize parallel lanes) |
| Integration | Wiring, compose, deploy config, end-to-end tests | 2-3 (some sequential) |
| Closure | Epic Closure systemic gate | 1 (always last) |

If any stage has 0 tickets → flag as a gap (e.g. "no integration tickets means deploy config isn't explicitly ticketed — risk of it being forgotten").

### Step 6b: Documentation Assignment Matrix

Every scaffolded doc template MUST be assigned to exactly one ticket. Build the matrix (note: this is the DOC ASSIGNMENT — which ticket fills which doc. Separate from ticket-breakdown's GOVERNANCE matrix which injects trigger-based ACs):

| Doc Template | Assigned To | Source |
|---|---|---|
| `docs/CONFIGURATION.md` | T? | Tech Plan env vars |
| `docs/FEATURES.md` | T? | Core Flows |
| `docs/QUICKSTART.md` | T? | Core Flows first-use journey |
| `docs/API_REFERENCE.md` | T? | Tech Plan Component Architecture |
| `docs/DEPLOYMENT_ARCHITECTURE.md` | T? | Deploy Plan |
| `docs/RESILIENCE.md` | T? | Tech Plan resilience table |
| `docs/DATABASE_SCHEMA.md` | T? | Tech Plan Data Model |
| `docs/TROUBLESHOOTING.md` | T? | Closure ticket (Epic Closure for delta-feature epics; OR the specific deploy-integration ticket for Retrofit epics that skip Epic Closure) |
| `docs/BUSINESS_MODEL.md` | T? | Epic Brief (only for commercial projects with per-project business model — distinct from FINANCIALS.md below) |
| `docs/FINANCIALS.md` | T? | SaaS launch-gate doc per `saas/88-saas-launch-checklist.md` — required when `Metadata.FINANCIALS: required` (SaaS scaffold pre-launch); N/A otherwise. Filled by the ticket that wires the billing integration (Paddle / iyzico / RevenueCat). |

Rules:
- Docs are filled BY the ticket that implements the related functionality (not a separate "docs ticket").
- If scaffold doesn't have a doc (e.g. `file-worker` has no `API_REFERENCE.md`), mark N/A.
- `ticket-breakdown` enforces this matrix per-ticket in its governance section.

### Step 7: Coverage Cross-Check

Before presenting:
- [ ] Every Success Criterion → at least one ticket.
- [ ] Every Tech Plan component → covered or excluded with reason.
- [ ] Every `[PRIMARY PATH]` from Core Flows → at least one ticket.
- [ ] No circular dependencies.
- [ ] **Parallelism validation:** no ticket marked ⚡ with a ticket it depends on (bidirectional check).
- [ ] **Shared-state check:** no two ⚡ tickets write/read the same file, table, or config.
- [ ] Parallel field populated on every ticket (⚡ or ⛓️).
- [ ] Batch groupings maximize parallelism within each batch.
- [ ] All 4 lifecycle stages represented (or gap justified).
- [ ] Shape-touching tickets identified (for deploy-plan awareness).

- [ ] Documentation Sync Matrix complete — every doc assigned, no orphans.
- [ ] If any ticket changes a shape field, note that deploy-plan findings still hold (or flag mismatch).

### Step 8: Present and Iterate

Present: outline table + parallel mermaid diagram + batch proposal + time savings estimate.

Iterate until user explicitly confirms. Silence ≠ confirmation.

If during iteration the user introduces scope changes (new feature, removed constraint, new persona), suggest `revise-requirements` rather than silently absorbing.

Then instruct: *"Run `ticket-breakdown` for Batch 1 to get full detail. Batch 1 tickets are all ⚡ parallel — you can dispatch them to separate agents simultaneously."*

## Acceptance Criteria

- Upstream consumed: Epic Brief, Core Flows (when present), Tech Plan, Deploy Plan, INFRA-CHECK, `fabrik-lifecycle.md`.
- Feature-for-existing-project handled: scope limited to feature, existing shape consumed.
- Two-faced types handled: backend + client lanes split as parallel.
- Every ticket has: Title, Scope, Depends, **Parallel** (⚡/⛓️), Stage, Gate, Touches, Shape, Complexity, Docs, Lessons.
- **Parallelism maximized:** no artificial sequential chains; parallelism budget ≥3:1 (or justified). Max 3 sequential hops.
- **Parallelism validated:** no ticket ⚡ with a ticket it depends on (bidirectional). No shared-state conflicts between ⚡ tickets.
- Mermaid diagram uses `subgraph` to show parallel groupings; consistent with Depends/Parallel fields.
- Batches of 3-5; parallelism maximized within each batch. Time savings stated.
- Lifecycle stages (foundation → implementation → integration → closure) all covered.
- **Ticket category coverage check passed:** every mandatory category for this scaffold has ≥1 ticket.
- **Scaffold-provided code not re-ticketed:** tickets extend/configure pre-scaffolded modules (auth, metrics, logging, GlitchTip), not recreate them.
- Every Success Criterion covered. Every Tech Plan component covered.
- Documentation Sync Matrix complete: every scaffolded doc assigned to exactly one ticket.
- Agent complexity hints provided (simple/complex/critical → agent tier).
- Gate tiers assigned (1=lean, 2=full). Epic Closure = Tier 3.
- Lessons Learnt triggers flagged on high-risk tickets.
- CHANGELOG rule acknowledged (universal — `ticket-breakdown` enforces).
- `revise-requirements` suggested if scope drifts during iteration.
- Epic Closure ticket present as final.
- Output ≤100 lines for outline table (excluding mermaid, Doc Sync Matrix, category check).
- User explicitly confirms. Silence ≠ confirmation.
