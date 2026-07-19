<!-- ⚠️ FABRIK FACTORY WORKFLOW — TICKET OUTLINE (our own, tool-capable twin of 05-ticket-outline-command)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in VS Code) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the Decisions Lock + Core Flows + Tech Plan + Deploy Plan + INFRA-CHECK from disk and
     builds the maximum-parallelism dependency graph. Produces the MAP; `06-ticket-breakdown-command` produces
     the DETAIL.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the **LOCKED** Decisions Lock (`01-decisions-lock-fabrik`, locked by `01R` — never consume a `DRAFT`) · Core Flows (`02-core-flows-fabrik`, if the route ran it) ·
         Tech Plan (`03-tech-plan-fabrik`) · Deploy Plan (`04-deploy-plan-fabrik`) · the `00-trigger-fabrik` INFRA-CHECK
       · `docs/operations/fabrik-lifecycle.md` (deploy/runtime, stages 3–4 ONLY — the foundation→…→closure stage model is this chain's own convention, NOT from this doc)
       · `AGENTS.md § "What every API scaffold emits automatically"` (scaffold-provided code — do not re-ticket it)
       · the existing project's `specs/services/<id>.yaml` (feature-for-existing-project only)
     The category-table `Rule Pack` column and cross-command `§` refs are **provenance** — the packs feed
     `06-ticket-breakdown-command`'s injection; you do not open them here.
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Ticket Outline

## Role

Technical project manager who maps the full epic into a **maximum-parallelism dependency graph**. You produce the MAP; `06-ticket-breakdown-command` (run in batches) produces the DETAIL.

## Core Philosophy

- **CHEAP and FAST.** Output ≤100 lines for a 20-ticket epic.
- **MAXIMIZE parallelism — the #1 design goal.** Every ticket that CAN run parallel MUST be marked parallel. Sequential chains waste agent time. Ideal: wide batches (4–5 parallel) + short chains (2–3 sequential). More than 3 sequential hops first→last → justify or redesign.
- **Respect the 4-stage lifecycle:** foundation (scaffold/schema/config) → implementation (endpoints/logic) → integration (wiring/deploy) → closure (validation/docs).
- Get STRUCTURE right (names, scopes, dependencies, parallel lanes, batches); do NOT write Steps / Acceptance Criteria / governance — that's `06-ticket-breakdown-command`. Consume upstream; do not redo work. Only proceed on explicit confirmation.

**Parallelism budget:** after drafting, count `total tickets` vs `longest sequential chain`. Target **≥3:1** (15 tickets / chain of 5 = 3:1). Below 2:1 → redesign to break unnecessary dependencies.

## Processing User Request

### Step 1: Consume Upstream

Read in order: **Decisions Lock** (`01-decisions-lock-fabrik`) — Success Criteria (each maps to ≥1 ticket), Out of Scope (hard boundary), Metadata; **Core Flows** (`02-core-flows-fabrik`, when present) — `[PRIMARY PATH]` markers, Flow Index; **Tech Plan** (`03-tech-plan-fabrik`) — Component Architecture, Data Model, Issue classification, Shape Block, resilience table; **Deploy Plan** (`04-deploy-plan-fabrik`) — Shape confirmation, registrar surface, env vars, compose contract; **INFRA-CHECK** — Internal APIs (consumed), Port, User Guide, Concurrency, i18n, Shape; `docs/operations/fabrik-lifecycle.md` — deploy/runtime mechanics (stages 3–4 only; the foundation→implementation→integration→closure model is this chain's own convention, not from that doc).

**Feature for existing project:** outline covers ONLY the feature scope; consume the existing `specs/services/<id>.yaml` (new tickets may ADD shape fields, never remove).

**Two-faced types** (`chrome-extension`, `mobile-app`, `desktop-app`): split into a backend lane (deploys to VPS) + a client lane (builds locally / ships to store) — naturally parallel.

**Multi-epic dispatch mode:** downstream of `mega-epic-breakdown/05-dispatch-epic-tickets-fabrik` (i.e. `00-trigger-fabrik` ran in consume mode `[canonical: 00-trigger-fabrik § Entry Points → Multi-epic]`):
- **15-field Metadata** inherited verbatim from the dispatched ticket — carry to every ticket, do NOT re-derive.
- **Universal categories** (1–14, from the ticket Metadata `[canonical: mega/02-epic-decomposition-fabrik sub-step 2h]`) constrain scope: only owned categories yield tickets; sibling-owned categories become `Out of Scope` lines.
- **Epic flavour** from the Title prefix `[canonical: mega/03-expand-epic-files-fabrik § Step 2]`: **Delta-feature** (`Epic N — <area>`) → 8–12 tickets for a 5–8-criteria epic; **Retrofit** (`Epic N — Retrofit: <area>`) → **3–5 tickets**, do NOT pad; Epic Closure ticket **OPTIONAL** — include it only if the retrofit genuinely needs a project-wide systemic gate `[canonical: 06-ticket-breakdown-command § Step 10]`.
- **Out of Scope (vision level)** inherited from `mega/00-trigger-fabrik` Vision Summary § Out of Scope — a ticket touching a vision-level exclusion is not allowed; raise back via `09-revise-requirements-command`.

### Step 2: Identify Work Units + Parallel Lanes

Group by component/layer/flow, then **optimize for parallelism.** **Lanes** = work units sharing NO mutual dependency (independent streams). Common Fabrik patterns: Backend API ∥ Frontend UI (merge at integration) · DB schema → then parallel endpoints · independent endpoints sharing no tables · i18n locale files ∥ business logic · observability ∥ features · docs ∥ implementation · test-setup ∥ the code it tests.

**Maximization:** split-don't-merge independent sub-tasks · interface-first (a shared types/contracts ticket unblocks all consumers) · narrow the critical path (the longest sequential chain — can a ticket on it be split to run earlier/parallel?) · keep foundation tickets SMALL+FAST (a 5-min schema unlocks 5 parallel implementation tickets).

**Parallelism validation (HARD):** a ticket CANNOT be ⚡ with any ticket in its `Depends`. If T5 depends on T3, T5 runs AFTER T3 — never simultaneously (broken build). For every `Parallel: ⚡ with TX`, confirm bidirectionally that TX is not in this ticket's `Depends` and this ticket is not in TX's `Depends`. **The mermaid diagram (Step 4) is the visual proof** — an arrow = sequential; no arrow + same subgraph = parallel; the diagram is authoritative if it contradicts the fields.

**Anti-patterns:** no artificial sequential chains · don't merge independent work "for simplicity" (kills parallelism) · don't over-decompose (20 one-function tickets defeat batching) · **⚠️ do NOT mark two tickets ⚡ when one WRITES a file/table/config the other READS — shared state = sequential even without an explicit `Depends`.**

### Step 2b: Ticket Category Coverage Check

Every applicable category MUST have ≥1 ticket (scaffold type + shape block decide which are mandatory). The `Rule Pack` column is provenance for `06-ticket-breakdown-command`'s injection.

| Category | When Mandatory | Rule Pack |
|---|---|---|
| DB Schema & Migrations | `shape.needs_database: true` | `core/25-data-postgres` |
| Cache & Queue | `shape.needs_cache: true` OR async jobs | `core/75-workers-jobs` |
| API Endpoints | python-api / node-api / saas backend | `core/15-api-contracts` |
| Internal API Consumption | INFRA-CHECK `Internal APIs ≠ none` | `core/35-security-auth` + `core/58-resilience` |
| External Service Integration | any external dep (B2, Paddle, Cloudflare, Gotenberg, Browserless, SMTP; Supabase legacy-only) | `core/58-resilience` |
| Background Workers | file-worker / file-api / async processing | `core/75-workers-jobs` |
| GUI / Frontend | any user/admin GUI surface — **feature-trigger** (incl. python-api/node-api/file-api with `is_admin_dashboard` OR `is_public` + HTML) `[canonical: mega/00 § Rule-area applicability matrix]`; brings i18n + Responsive (375px) + Dark+Light | `saas/60-saas-ui` / `chrome-ext/70-chrome-ext` / `mobile-app/80-mobile` |
| i18n Setup | INFRA-CHECK `i18n ≠ N/A` | (from `03-tech-plan-fabrik` Step 4d) |
| Auth & Security | any user-facing / admin-dashboard service | `core/35-security-auth` |
| Observability Configuration | ALL scaffolds | `core/55-observability` — CONFIGURE the scaffold-emitted logger/metrics; do NOT recreate |
| Health Endpoint | ALL `is_public` scaffolds — `/health` tests ALL real deps | `core/55-observability` |
| Resilience & Self-Healing | any service with external calls (workers add pause-state + queue-bloat + orphan-sweep) | `core/58-resilience` |
| Deployment & Compose | ALL VPS-deployed — ticket FILLS the scaffold-emitted compose skeleton | `core/30-ops` |
| Backup & Data Safety | `shape.has_persistent_data: true` | `core/30-ops` |
| Search | `shape.has_search_feature: true` | `core/65-rag-search` + `core/66-rag-chunking` |
| Notifications & Alerts | any alerts/emails/push (Apprise) | (project-specific) |
| Payments & Billing | commercial paid features (Paddle/iyzico — Stripe NOT available to TR) | `core/85-payments-billing` |
| Multi-Tenancy | commercial SaaS tenant isolation | `saas/95-multi-tenant-saas` |
| Automation & Webhooks | webhooks / n8n | `core/58-resilience` + `core/85-payments-billing` |
| GPU / AI Inference | provisions/consumes GPU compute | `core/76-gpu-workers` |
| Docusaurus Site | docusaurus scaffold | `core/42-docusaurus` |
| AI Agent / Prompt Design | new prompts / skills / agent defs | `docs/reference/MD/ai-prompt-templates.md` + `docs/reference/ai_agent_prompt_directives.md` |
| Kilo Integration | calling Kilo CLI / new Kilo use cases | `docs/reference/kilo/KILO_CLI_REFERENCE.md` + `KILO_USE_CASES.md` |
| Testing | ALL (one integration test per PRIMARY PATH) | `core/45-testing-strategy` |
| Documentation | ALL (per the Step-6b matrix) | `core/40-documentation` + `docs/reference/MD/markdown-cheatsheet.md` |
| Audit log (immutable) | any sensitive-ops writer (auth/billing/admin/GDPR/KVKK) | `core/app-audit-log` (vendored `/opt/fabrik-lib/app-audit-log/`) |
| Watchdog sidecar + cost-budget | any paid-LLM call in an unattended/scheduled/re-fire loop — **ON by default, opt-OUT** `[canonical: infrastructure.py:314 — watchdog_cfg.get("enabled", True)]`; declare `daily_budget_usd` + `daily_invocations_cap` | `core/60-watchdog` + `core/cost-budget` |
| KVKK / GDPR data residency | any PII/blob storage (EU-region infra; `file_erasure_audit` + Article-11 sweeper for file-api) | `core/67-file-api` + `mobile-app/80-mobile` + `desktop-app/72-desktop` |
| Email two-stream | sends both transactional AND marketing (separate streams/subdomains) | `core/86-email-templates` |
| Abuse detection | SaaS free-tier signup surface (IP rate-limit, disposable-email block, progressive unlock) | `saas/87-abuse-detection` |
| Epic Closure | Delta-feature: ALL (last ticket). Retrofit: OPTIONAL (§ Step 1) | (cross-cutting) |

**Scaffold already provides (do NOT re-ticket)** `[canonical: AGENTS.md § What every API scaffold emits automatically]`: `internal_auth.py` (M2M), `metrics.py` + `/metrics`, `glitchtip_init` (Sentry SDK), the structured logger module, `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`. Tickets CONFIGURE/EXTEND these. **Combining:** related categories with the SAME dependency chain can share one ticket (Observability + Health); never merge categories with DIFFERENT chains (kills parallelism). "Mandatory" = the WORK must be done, not that it's a separate ticket.

### Step 3: Draft the Outline

Per ticket, ONLY: `T<N> — <imperative Title>` · `Scope` (1–2 sentences, in/out) · `Depends` (`T1, T3` or `none`) · `Parallel` (`⚡ with T2, T4` or `⛓️ after T3` — **mandatory**) · `Stage` (foundation | implementation | integration | closure) · `Category` (from Step 2b — sets the ticket's rule pack) · `Gate` (**1 (lean)** = coding-time only / **2 (full)**) · `Touches` (`[PRIMARY PATH]` flow or none) · `Shape` (fields affected or N/A) · `Complexity` (simple | complex | critical — hints agent tier) · `Docs` (which scaffold docs this ticket fills, or none) · `Lessons` (trigger condition or none).

⚠️ **`Gate` is the CODING-TIME tier only.** A ticket's **Final Gate Instruction** is Tier-2 `--json` (Tier-3 `--systemic --json` for the Epic Closure ticket) — `--lean` is **never** a completion gate `[canonical: CLAUDE.md § Completion Contract]`. **CHANGELOG:** every code ticket adds one `## [Unreleased]` entry — universal, enforced by `06-ticket-breakdown-command`, not per-ticket here. **Lessons:** flag `trigger condition` for auth changes / secret rotation / deploy-compose workaround / new registrar / external integration / high-risk; `06` enforces the actual `docs/LESSONS_LEARNT.md` entry.

Rules: titles are imperatives · Scope ≤2 sentences · `Parallel` mandatory · Stage maps to the lifecycle · Complexity → agent tier (simple→free/local, complex→mid, critical→premium; user picks in `06`) · every Success Criterion → ≥1 ticket · every Tech Plan component → ≥1 ticket (or excluded with reason) · LAST ticket = "Epic Closure — Tier 3 systemic gate" for **delta-feature** (OPTIONAL for Retrofit).

### Step 4: Parallel Dependency Diagram

A mermaid `graph TD` with a `subgraph` per batch grouping parallel-eligible tickets — an arrow = sequential, no-arrow-same-subgraph = parallel. The diagram must be consistent with the `Depends`/`Parallel` fields (diagram authoritative on conflict).

### Step 5: Batch Proposal

Group into batches of **3–5**, maximizing ⚡ per batch. Each batch 3–5 (never >5); batch order respects dependencies; first batch = zero-dependency foundation; last batch = Epic Closure (delta-feature only; a correct Retrofit may have none — state the skip justification). State expected time savings ("Batch 2: 3 ⚡ = ~1 ticket-time instead of 3×").

### Step 6: Lifecycle Stage Distribution

Verify coverage: **Foundation** (schema/config/env/i18n structure — 2–4, usually parallel) · **Implementation** (endpoints/logic/UI/workers — 5–12 delta-feature / 3–5 total for a Retrofit) · **Integration** (wiring/compose/e2e — 2–3, some sequential) · **Closure** (Epic Closure — 1 last for delta-feature; **0 permitted** for a Retrofit that skips it). A stage with 0 tickets → flag as a gap — EXCEPT Closure on a Retrofit (state the skip justification).

### Step 6b: Documentation Assignment Matrix

Every project doc assigned to exactly one ticket — a scaffolded template where one exists, else created by the ticket (⚠️ `API_REFERENCE.md` and `FINANCIALS.md` are NOT scaffold-seeded — API_REFERENCE has no template, FINANCIALS is out-of-scaffold-scope; the ticket creates/fills them). This is the DOC-ASSIGNMENT, separate from `06`'s governance matrix:

| Doc Template | Assigned To | Source |
|---|---|---|
| `docs/CONFIGURATION.md` | T? | Tech Plan env vars |
| `docs/FEATURES.md` | T? | Core Flows |
| `docs/QUICKSTART.md` | T? | Core Flows first-use journey |
| `docs/API_REFERENCE.md` | T? | Tech Plan Component Architecture |
| `docs/DEPLOYMENT.md` | T? | Deploy Plan (⚠️ NOT `DEPLOYMENT_ARCHITECTURE.md`, which is hub-only) |
| `docs/RESILIENCE.md` | T? | Tech Plan resilience table |
| `db/schema.sql` + Alembic migration | T? | Tech Plan Data Model (⚠️ there is no `docs/DATABASE_SCHEMA.md`) |
| `docs/TROUBLESHOOTING.md` | T? | Closure ticket (or the deploy-integration ticket for a Retrofit that skips closure) |
| `docs/BUSINESS_MODEL.md` | T? | Decisions Lock (commercial projects only) |
| `docs/FINANCIALS.md` | T? | required when `Metadata.FINANCIALS: required`; filled by the billing-integration ticket |

Docs are filled BY the ticket that implements the related functionality (not a separate "docs ticket"); if a scaffold lacks a doc (e.g. `file-worker` has no `API_REFERENCE.md`), mark N/A; `06-ticket-breakdown-command` enforces this matrix per-ticket.

### Step 7: Coverage Cross-Check

Every Success Criterion → ≥1 ticket · every Tech Plan component → covered or excluded-with-reason · every `[PRIMARY PATH]` → ≥1 ticket · no circular dependencies · **parallelism validation** (no ticket ⚡ with one it depends on, bidirectional) · **shared-state check** (no two ⚡ tickets write/read the same file/table/config) · `Parallel` populated on every ticket · batches maximize parallelism · all 4 lifecycle stages represented (or gap justified; Closure-on-Retrofit may be 0) · shape-touching tickets identified · Doc Assignment Matrix complete (no orphans) · a ticket changing a shape field notes deploy-plan findings still hold (or flags a mismatch).

### Step 8: Present and Iterate

Present the outline table + parallel mermaid diagram + batch proposal + time-savings estimate. Iterate until the user explicitly confirms. A mid-iteration scope change → `09-revise-requirements-command`. Then instruct: *"Run `06-ticket-breakdown-command` for Batch 1 — its tickets are all ⚡ parallel; dispatch them to separate agents simultaneously."*

## Acceptance Criteria

- Upstream consumed (Decisions Lock, Core Flows when present, Tech Plan, Deploy Plan, INFRA-CHECK, `fabrik-lifecycle.md`); feature-for-existing-project + two-faced types handled.
- Every ticket has Title, Scope, Depends, **Parallel** (⚡/⛓️), Stage, Gate, Touches, Shape, Complexity, Docs, Lessons.
- **Parallelism maximized** (no artificial chains; budget ≥3:1 or justified; ≤3 sequential hops) and **validated** (no ⚡ with a dependency, bidirectional; no shared-state conflict between ⚡ tickets).
- Mermaid uses `subgraph`, consistent with the fields; batches of 3–5 maximizing ⚡; time savings stated.
- All 4 lifecycle stages covered — except Closure on a Retrofit that skips it (0 legal, justified).
- Category-coverage check passed (every mandatory category ≥1 ticket); scaffold-provided code not re-ticketed.
- Every Success Criterion + every Tech Plan component covered; Doc Assignment Matrix complete (every scaffolded doc to exactly one ticket — `docs/DEPLOYMENT.md` not `DEPLOYMENT_ARCHITECTURE.md`; `db/schema.sql` + Alembic, no `DATABASE_SCHEMA.md`).
- Complexity hints + Gate tiers assigned (1 lean / 2 full; Epic Closure = Tier 3); Lessons triggers flagged; CHANGELOG rule acknowledged; `09-revise-requirements-command` suggested on drift.
- Epic Closure final for delta-feature (OPTIONAL for Retrofit); output ≤100 lines (outline table); user explicitly confirms.

---

**Next (CC1 pairing, north star § Command-chain build plan):** converge this outline with `/fabrik-workflow-review <outline path> ticket-outline` — it forces the no-op (parallelism ≥3:1 and bidirectionally validated, no shared-state ⚡ conflicts, every Success Criterion + mandatory category covered, Doc Assignment Matrix complete with the corrected doc names, zero hollow citations) before anything consumes it. Then → `06-ticket-breakdown-command` (Batch 1). *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
