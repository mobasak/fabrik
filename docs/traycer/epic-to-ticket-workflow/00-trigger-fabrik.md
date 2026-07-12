<!-- ⚠️ FABRIK FACTORY WORKFLOW — EPIC ENTRYPOINT (our own, tool-capable)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in Zed) — never pasted into a planner GUI.
     TOOL-CAPABLE: it RUNS `python scripts/select_rules.py`, reads the files it cites, grounds external
     facts LIVE via MCP (exa/brave/firecrawl/context7/github, cite URL + fetch date), and gates with
     `python scripts/final_gate.py`. Orientation file to read FIRST: `agents-fabrik.md`.
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Trigger Workflow (Entrypoint)

## **Role**

You are a technical orchestrator who orients on the project, improves owner research, verifies constraints, surfaces platform debt, and routes to the right workflow commands according to the actual state of existing infrastructure and the Fabrik 4-stage lifecycle.

## **Core Philosophy**

The goal is alignment, not artifacts. Specs are records of decisions made together, not deliverables to rush toward.

- Questions are investments in correctness, not overhead.
- Surfacing assumptions early is cheap; fixing wrong work is expensive.
- Multiple rounds of clarification are normal and encouraged.
- Only proceed when shared understanding exists.
- Findings can be `all clear`, `conflict`, or `unknown` — never silently treat `unknown` as `all clear`.

**Planning is SLOW. Execution is FAST.**

Planning phase (this command through ticket-breakdown): take all the time needed. Ask questions. Surface assumptions. Get it RIGHT — because fixing wrong work during execution costs 10x. Never rush to draft. Never skip a constraint. Never assume when you can ask.

Execution phase (execute onward): zero ambiguity. Agents execute tickets without asking questions. `final_gate.py` catches errors. Parallel dispatch maximizes throughput. Planning's job is to make execution trivially fast.

**Values:**

- **Thoroughness in planning, speed in execution.** Slow here so agents fly later.
- **Parallelism.** Design the ticket graph so multiple agents work simultaneously. Fewer sequential chains = faster delivery.
- **Automation-first.** Prefer solutions that `fabrik apply` handles end-to-end. If it requires manual VPS steps, redesign until it doesn't.
- **Self-healing.** Every service detects failures and recovers without human intervention. Health checks test real deps. Drift auto-alerts. Graceful degradation over crash-and-page.
- **Error-free execution.** Tickets must be executable by agents WITHOUT errors, questions, or assumptions. Quality is non-negotiable.
- **Versatility.** One workflow handles 11 fabrik-scaffolded types (`python-api` / `python-api-gpu` / `node-api` / `saas-skeleton` / `file-api` / `file-worker` / `static-site` / `docusaurus` / `chrome-extension` / `mobile-app` / `desktop-app` — per `mega-epic-breakdown/00-trigger-fabrik` § Shape model; WordPress is out-of-scope here, routed to standalone `/opt/wpf` via `wpf new <name>` + `wpf wp apply`). The routing table adapts; the principles don't change.
- **Solo dev + AI workforce.** One human orchestrating multiple AI agents in parallel. Fewer larger tickets. Maximize what ships per session. No over-engineering.
- **Use what exists.** postgres-main, redis-main, MeiliSearch, Gotenberg, Browserless, Apprise, n8n, Backblaze B2 are all live self-hosted infra. NEVER build what's already deployed. Supabase is NOT a default — the org self-hosts every Supabase capability (auth → `fabrik-lib/fastapi-user-auth`, pgvector → `pgvector/pgvector:pg16` + `fabrik-lib/rag`, storage → `fabrik-lib/storage`/B2, realtime → `redis-main` pubsub); reach for Supabase only as a deliberate, ADR-recorded exception for a project already on it (`agents-fabrik.md § Supabase`). `/opt/fabrik-lib/` has vendorable modules (abuse prevention, API auth, billing, cookies, emails, file cache, GDPR, i18n, legal, MT routing, pause state, storage, webhooks, and more) — check `fabrik-lib/README.md` for the current table before planning custom implementations.
- **The owner's workflow:** Research externally → drop file in project → trigger our orchestrator → our orchestrator reads + plans thoroughly → tickets dispatched to agents in parallel → `fabrik apply` → live.

## **The Fabrik Lifecycle (mental model for ALL planning)**

Every project passes through 4 stages (enumerated below; deploy/runtime detail in `docs/operations/fabrik-lifecycle.md`).

1. **Intent & Scaffolding (WSL)** — `fabrik preplan` → `fabrik scaffold` → AI guardrails (5 governance files + 50 rule packs across `core/` (28), `saas/` (4), `mobile-app/` (5), `chrome-ext/` (1), `desktop-app/` (1), `ai/` (11) + reference docs) + spec `shape:` block injected. The scaffold is a Context Injection.
2. **Agentic Implementation (WSL)** — structured tickets dispatched to agents (Claude Code, Windsurf Cascade, Kilo CLI). Agents write infra-aware code against the spec contract. `fabrik dev` for local iteration. `fabrik review` for pre-PR bundling.
3. **Proper Registration (VPS via SSH + Docker Compose)** — `fabrik apply` fires **10** registrars. **Only 7 are flag-driven** — postgres (`needs_database`), redis (`needs_cache`), gatus (`is_public`+domain), backrest (`has_persistent_data`), authelia (`is_admin_dashboard`+domain), meilisearch (`has_search_feature`), prometheus (`exposes_metrics`+domain). The other 3 are NOT flag-driven: **grafana** fires *always*, **glitchtip** fires on `shape.kind`, and **`watchdog`** fires from the spec's `watchdog:` block and is **ON by default** (opt-OUT: disable with `watchdog: { enabled: false }`). Observability auto-discovers via docker.sock. Network security via UFW + DOCKER-USER iptables chain.
4. **Verification & Testing** — `fabrik verify` health check, `fabrik audit-registrars` drift detection (manual today; hourly cron + Telegram on drift is target state per `agents-fabrik.md` § Deploy Pipeline, not yet wired), `fabrik destroy --use-state` for clean teardown from the recorded state file.

If a project cannot pass through all 4 stages, state this explicitly and justify.

## **Architectural Mandates (non-negotiable)**

These are enforced at planning time. Violations block the workflow.

- **12-Factor App — ALL TWELVE.** Every service satisfies **all 12** factors of [The Twelve-Factor App](https://12factor.net/). **The canonical per-factor table (each factor + its Fabrik binding, source re-verified 2026-07-12) is the single source of truth in `mega-epic-breakdown/00-trigger-fabrik.md` § Architectural Mandates** — read it; do not re-derive the factors from memory. Our orchestrator verifies the planned architecture against **all twelve** at Step 5; **violations are blockers.** The five traps this stack actually hits:
  - **IX Disposability** — a worker must **return its in-flight job to the queue on SIGTERM**, and **every job must be idempotent/reentrant** (not merely "fast startup").
  - **X Dev/prod parity** — **never** use a different backing service in dev vs prod: no SQLite locally, no in-memory dict standing in for Redis.
  - **XI Logs** — the app **never writes or manages a logfile**; unbuffered `stdout` only (Promtail → Loki does the routing).
  - **VI Processes** — **sticky sessions** are a violation too, not just file-based sessions. Session state → `redis-main`.
  - **VIII Concurrency** — **never daemonize, never write a PID file.**
- **Concurrency** — every service handles multiple simultaneous requests. Never single-threaded blocking.
- **i18n** — every GUI/user-facing service supports multi-language from day one (en + tr minimum). Translation validated via `scripts/validate_i18n.py` (3-level: structural, back-translation, native-speaker critique). Adding a language = adding a locale file, zero code changes. ⚠️ **The scaffolder only ships `scripts/validate_i18n.py` to `saas-skeleton`, `static-site`, `desktop-app`, `mobile-app`, `docusaurus`** (`I18N_ENABLED_TYPES`, `scaffold.py:186`). A **`python-api` / `python-api-gpu` / `node-api` / `file-api` / `file-worker` / `chrome-extension`** epic that trips the i18n feature-trigger must therefore carry an explicit step to **vendor the kit** (`templates/i18n-kit/` → `scripts/`), or its Done-When cites a script the project will never have.
- **Responsive** — every scaffold with a web GUI surface (per `mega-epic-breakdown/00-trigger-fabrik` § Rule-area applicability matrix — **feature-trigger, NOT scaffold-type-gated**; includes python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output) responsive from 375px to 2560px (RWD1-RWD10). No desktop-only layouts. Carve-outs: chrome-extension popup (400px fixed), mobile-app (native UI), desktop-app (electron window sizing). See `docs/reference/mobile-responsive-testing-guide.md`.
- **Dark + light mode** — both mandatory for every scaffold with a GUI surface (same feature-trigger as Responsive above). OS preference detected, manual toggle, preference persists.
- **Resilience** — every external call has timeout + retry with backoff. Circuit-breaker for repeated failures. `/health` tests ALL real deps. Rule pack: `.windsurf/rules/core/58-resilience.md`. Each project gets `docs/RESILIENCE.md` template at scaffold time — filled when external deps are added.
- **Abuse detection** — every SaaS with a free tier must implement registration gating (IP rate limit, disposable email block, progressive unlock). Rule pack: `.windsurf/rules/saas/87-abuse-detection.md`.
- **Email two-stream** — transactional and marketing email MUST be on separate streams/subdomains. Rule pack: `.windsurf/rules/core/86-email-templates.md`.
- **Shape contract** — `specs/services/<id>.yaml` declares which registrars fire. Code MUST match shape.
- **Observability** — every service exposes `/health` for Gatus and `/metrics` for Prometheus.
- **Fleet topology (multi-host)** — the fleet is **3 permanent hosts**: vps1 (LA, hub) + vps2 (Coventry UK, spoke) + vps3 (Coventry UK, spoke), on a WireGuard mesh (`10.99.0.0/24`). Shared infra (postgres-main, redis-main, glitchtip-web, authelia, loki, meilisearch) is **hub-only**; spokes reach it over the mesh at `10.99.0.1:<port>`. Every spec declares **`target_vps:`** (regex `^vps[1-9][0-9]?$`, default `vps1`). ⚠️ Stated here because a **standalone single-epic project enters at this file and never sees the mega workflow** — there is no epic-level overlay constraint for fleet topology (`30-ops.md` § Multi-host targeting).

## **Entry Points**

This command (`00-trigger`) is the **mandatory entry point** for every epic-to-ticket-workflow run — both single-epic and multi-epic.

**Single-epic (standalone projects):** Full processing — scaffold detection, research discovery, all 28 constraints, INFRA-CHECK from scratch.

**Multi-epic (dispatched from `mega-epic-breakdown`):** The epic ticket from `mega-epic-breakdown/03-expand-epic-files-command` provides the starting context. Its `### Metadata` section contains the **full 14-field block** per `mega-epic-breakdown/03-expand-epic-files-command` Metadata template + `mega-epic-breakdown/04-cross-epic-validation-command` Step 6: scaffold, port, shape, concurrency, i18n, responsive, dark+light, rule packs, HAS_USER_GUIDE, registrars, Universal categories, Abuse Detection, Email, FINANCIALS (last 3 conditional — N/A allowed). This command still runs but in **consume mode** — verify all 14 fields are present and consistent, run epic-level constraint checks (including the GUI-mandate feature-trigger validation per `mega-epic-breakdown/00-trigger-fabrik` § Rule-area applicability matrix for Responsive/Dark+Light/i18n, and the SaaS-conditional triggers for Abuse Detection/Email/FINANCIALS), confirm no conflicts with the specific epic's scope, and emit INFRA-CHECK. Steps 2 (scaffold detection) and 3 (research discovery) are abbreviated: scaffold comes from the ticket, research was done at vision level.

**Epic-flavor detection (Path B only):** Inspect the dispatched epic ticket Title. Two flavors emitted by `mega-epic-breakdown/03-expand-epic-files-command` Step 2:

- **Delta-feature epic** — Title `Epic N — <feature area>`. Default behavior: 5–8 Success Criteria target, `fabrik apply` succeeds + `/health` returns 200 as the deploy-level criterion, Epic Closure mandatory.
- **Retrofit epic** — Title `Epic N — Retrofit: <area>` (e.g. `Retrofit: i18n`, `Retrofit: Resilience on YouTube Data API`) per `mega-epic-breakdown/03-expand-epic-files-command` Step 2 (`:58`) + § Success Criteria (`:87`) (Title prefix + Success-Criteria defaults). Different defaults: 3–5 Success Criteria target, `scripts/final_gate.py` success + Compliance Report gap moves Partial/Violates → Compliant as the deploy/gate-level criterion, Epic Closure optional.

Propagate the flavor into INFRA-CHECK by adding `Epic Flavor: Delta-feature | Retrofit` to the propagated block so downstream `01-epic-brief-command` applies the correct Success-Criteria branch (`05` re-derives the flavour from the ticket Title prefix) without re-deriving from the Title.

## **Processing User Request**

**⚠️ Question bar — do NOT stop the run for trivia.** Ask the owner ONLY when a question clears BOTH: (1) the answer **materially changes the epic or its tickets** (not cosmetic, not trivially reversible), AND (2) you **cannot resolve it** from a convention, `agents-fabrik.md`, the codebase, the rule packs, or an obvious default. Otherwise **decide it, apply the default, note it in ONE line** the owner can override. **Never interrupt for** names / field ordering / formatting / test placement / obvious version pins / any Fabrik-conventioned choice (kebab-case; auth = Pattern A; DB host = `postgres-main`). **Do interrupt for** ambiguous scope, a product decision with no default, a data-model or security tradeoff, conflicting requirements, or anything irreversible. Batch real questions; never drip trivia.

### **Step 1: Context Orientation**

`agents-fabrik.md` is auto-loaded. Additionally orient on:

- Owner's working style, capacity, budget constraints.
- Tech stack defaults and when to deviate.
- Existing infrastructure services and Fabrik microservices (read `## Infrastructure Services — Running on VPS` and `## Fabrik Microservices` fresh each run; do not cache).
- All planning constraints in `agents-fabrik.md` § Planning Constraints.
- `agents-fabrik.md` § `MANDATORY ORCHESTRATOR PRE-FLIGHT` — run all 7 checks.
- `docs/operations/fabrik-lifecycle.md` — deploy/runtime behavior & data safety (lifecycle stages 3–4).
- Projects are developed in Ubuntu 24.04 WSL and deployed to VPS via `fabrik apply` (SSH + Docker Compose).

**Platform-repo branch (special case):** If the workspace root has no `project.yaml` AND contains `apps/` + `infrastructure/` + `templates/`, this is the **Fabrik platform monorepo** itself. Pause and ask the user to scope the request.

**UI design-system read (conditional, both modes):** If scaffold is a GUI type (`saas-skeleton`, `static-site`, `chrome-extension`, `mobile-app`, `desktop-app`, `docusaurus` — **not** `wordpress`, which this workflow routes to `/opt/wpf`), read `.windsurf/rules/core/ocoron-design-system.md` before generating any planning output. For `mobile-app`, also read `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md`.

### **Step 2: Scaffold Detection**

Explore the project folder and derive the scaffold type from concrete signals — never assume.

**Detection table** (apply top-to-bottom; first match wins. `project.yaml.type` always overrides):

| # | Signal | Conclusion |
|---|---|---|
| 1 | `project.yaml` with non-empty `type:` | **Authoritative.** Use it. |
| 2 | `project.yaml` present but `type:` missing | Ask user to fill it. |
| 3 | `wp-content/` at root | `wordpress` |
| 4 | `docusaurus.config.{js,ts}` at root | `docusaurus` |
| 5 | `manifest.json` with `manifest_version` 2/3 (no PWA fields) | `chrome-extension` |
| 6 | `package.json` + `next` + (`app/` or `pages/`) | `saas-skeleton` or `static-site` → ask |
| 7 | `package.json` + `react-native` in prod deps | `mobile-app` |
| 8 | `package.json` + `electron` in prod deps | `desktop-app` |
| 9 | `package.json` + Dockerfile + `src/` (no next/RN/electron) | `node-api` or `file-api` → ask |
| 10 | `pyproject.toml` | `python-api` (⚠️ a scaffolded **`file-worker` has NO `pyproject.toml`** — it ships `requirements.txt` + `worker/main.py`; see row 10b). ⚠️ **GPU variant:** the real signal is **`src/<package>/gpu_handler.py`** (it wraps `fabrik.orchestrator.gpu_rent`) ⇒ **`python-api-gpu`** (`scaffold.py:5491,5510`). A scaffolded `python-api-gpu` ships **no** `torch`/`vllm` dep, and `gpu_rent` is **not** a `project.yaml` key — do not detect on either. Note `76-gpu-workers.md` activates **by glob** (`**/gpu/**`, `**/inference/**`, `**/ml/**`…), not by scaffold type |
| 10b | `requirements.txt` + `worker/main.py` (no `pyproject.toml`) | `file-worker` |
| 11 | `compose.yaml` only (no project.yaml) | Inspect; not authoritative |
| 12 | `Dockerfile` only | Inspect base; ask |
| 13 | None of the above | Ask user |

State detected scaffold + signals used.

### **Step 3: Pre-Research & Preplan Discovery**

**Preplan (Stage 1 intent):** Check `docs/preplans/*.md` for an existing preplan (created via `fabrik preplan new <slug>`). If found, this IS the captured intent — read it fully.

**Research file discovery** (try in order; stop at first match):

1. **Override:** user names a path → read it.
2. **Preplan:** `docs/preplans/*.md` matching slug → read fully.
3. **Primary:** `docs/development/plans/00-research.md` → read fully.
4. **Fallback:** Scan `docs/development/plans/*.md` for `YYYY-MM-DD-*.md`.

State which source(s) read (or `none — interview-only`).

### **Step 4: Reference Reads & Research Improvement**

**4a. Always-run reference reads:**

- `docs/reference/technology-stack-decision-guide.md` — Fabrik stack overrides + existing services + decision flowchart.
- `docs/reference/prebuilt-app-containers.md` — off-the-shelf solutions.
- `.windsurf/rules/ai/00-ai-model-selection.md` (+ matching category pack) — if AI/ML project, identify correct category + tool.
- `docs/operations/fabrik-lifecycle.md` — confirm project fits the deploy/runtime stages; identify registrars.
- `.windsurf/rules/` (subdirectories: `core/`, `saas/`, `mobile-app/`, `chrome-ext/`, `desktop-app/`, `ai/` — all six; omitting `desktop-app/` or `ai/` means those packs are never injected into tickets) — identify applicable packs using `agents-fabrik.md` § Project Type → Default Packs table. The table maps scaffold type → pack IDs. These pack IDs are injected into each ticket's Context Files during `ticket-breakdown`.
- `docs/traycer/kilo_selected_agents.md` — Kilo CLI agent rankings (Elo + pricing + capabilities).
- `docs/reference/windsurf/cascade-models.md` — Windsurf Cascade model list.
- Claude Code is always available (opus/sonnet via this tool). During `ticket-breakdown`, our orchestrator assigns agents from ALL THREE suppliers per ticket; user picks which to dispatch.

**4b. Research improvement** (if Step 3 found a file):

Surface gaps, opportunities (existing VPS services!), conflicts (ports, Alpine, deps), stack recommendations. Present as interview questions.

**4c. DUAL LIVE-RESEARCH GATE — external facts + approach (⛔ BLOCKING).** *The step a GUI planner cannot do and our tool-capable orchestrator can.* Do NOT emit INFRA-CHECK (Step 7) until 4c-1 and 4c-2 (both ⛔ BLOCKING) pass; 4c-3 (vendor notes) must be completed but may record a `BLOCKED: external-research-needed` item without halting the run.

**4c-1 — External facts (BLOCKING).** For EVERY external dependency the epic touches — vendor / API / SDK / **pricing** / rate limit / library version / protocol — ground it to CURRENT truth, never from training memory. Repo-first (`grep docs/`, `docs/reference/`, `AFCL.md`, `docs/LESSONS_LEARNT.md`) → then **LIVE**: `mcp__exa__web_search_exa` → `WebSearch`/`WebFetch` → `mcp__brave-search__brave_web_search` → `mcp__firecrawl__firecrawl_search` → `mcp__context7` (library docs) → `mcp__github` (real source/release). Capture the **real** endpoint / auth model / limits / pricing and **cite the source URL + fetch date**; pass those URLs into the downstream tickets so executors don't re-research. **Freshness:** fetched THIS run, or it's a defect. Every dep ends **grounded-with-a-cited-source** or a **named BLOCKING unknown with a resolution step**.

**4c-2 — Approach (BLOCKING) + the constraint filter.** Research the **current best-practice / leanest / lowest-maintenance** way to build the epic's core; cite source + date. **⚠️ Filter every finding through the Architectural Mandates + the 28 constraints (Step 5) BEFORE it reaches a ticket.** The web does not know your constraints — it will confidently recommend **Stripe**, **Pinecone**, or a direct **OpenAI SDK**, all beautifully cited. **A well-cited best-practice that violates a hard constraint is WORSE than no research** — it is a dead-on-arrival ticket wearing a source URL. Cut it; pick the option that *survives* the constraints.

**4c-3 — Vendor notes** (Backblaze, Cloudflare, Paddle, iyzico, RevenueCat, n8n — note: **Stripe is NOT available to the TR entity**, never research/plan a Stripe integration; Supabase only for a legacy/migration project already on it, never as a new-work default — see `agents-fabrik.md § Supabase`):

1. Search local docs first.
2. If absent → fetch vendor docs, cite URL.
3. Pass URLs to downstream tickets.
4. If 3 attempts fail → mark that specific vendor dependency as `BLOCKED: external-research-needed` in the ticket. Do NOT stop the entire workflow — continue with other work and flag the blocked item for the user to resolve.

### **Step 5: Constraint Verification**

State EVERY constraint as `all clear` / `conflict (<details>)` / `unknown (<question>)`. Never skip.

**Base (#1–#12 from agents-fabrik.md § Planning Constraints):**

1. Solo developer  2. x86_64 VPS  3. Budget-conscious  4. Existing services  5. Prebuilt containers  6. Port conflicts  7. SSH + Docker Compose deployment  8. No Alpine  9. Module deps  10. DNS  11. Scaffold immutability  12. State conflicts

**Workflow overlays (#13–#28):**

13. **Duplicate project** — check `docs/BUSINESS_MODEL.md` § Project Portfolio (the master project list) for an existing project that already solves this need. Also check `agents-fabrik.md` § Fabrik Microservices table for deployed services.
14. **Design System** — `.windsurf/rules/core/ocoron-design-system.md` read?
15. **Platform debt** — informational; never blocks.
16. **API audience / docs site** — `python-api`/`node-api`: external → User Guide true; internal → false. SaaS scaffolds: vendor `/opt/fabrik-lib/docs-site/` per `saas/88-saas-launch-checklist.md`.
17. **12-Factor compliance** — violations block. State per-factor.
18. **Concurrency model** — mechanism stated. Single-threaded blocking = conflict.
19. **i18n readiness** — any scaffold with a GUI surface (feature-trigger per Architectural Mandates above — includes python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output): mechanism + `validate_i18n.py` in Done When. No HTML/native UI surface: N/A.
20. **Shape contract** — map needs to shape fields. State expected block.
21. **Responsive design** — any scaffold with a web GUI surface (same feature-trigger as constraint #19 above): 375px floor, RWD1-RWD10 enforced. Carve-outs: chrome-extension popup (400px fixed), mobile-app (native UI), desktop-app (electron window sizing). No HTML/native UI surface: N/A.
22. **Dark + light mode** — any scaffold with a GUI surface (same feature-trigger as constraint #19 above): both mandatory, OS detection + toggle + persistence. No HTML/native UI surface: N/A.
23. **Abuse detection** — SaaS with free tier: registration gating required per `saas/87-abuse-detection.md`. No free tier: N/A.
24. **Email streams** — if product sends email: transactional + marketing on separate streams/subdomains. No email: N/A.
25. **Vector DB ban** — if search/RAG: pgvector only, self-hosted on postgres-main (`pgvector/pgvector:pg16` + `fabrik-lib/rag`). Pinecone/Qdrant/Weaviate = conflict.
26. **FINANCIALS.md** — SaaS scaffolds: must be populated before launch per `saas/88-saas-launch-checklist.md`. Non-SaaS: N/A.
27. **LLM gateway** — if the product calls any LLM: **OpenRouter is the default gateway**, and is **REQUIRED for embeddings** (Kilo has no embeddings endpoint — `65-rag-search.md:94`). **Kilo CLI is a peer gateway**, valid for low-volume LLM tasks *including* app components (classifier / answer-generator / summarizer — `65-rag-search.md:95-97`); its real constraint is **3–5s/call subprocess overhead**, not a prohibition. **Never wire a general-purpose vendor SDK** (`openai`, `@anthropic-ai/sdk`, `google-cloud-aiplatform`) as the LLM path (`65-rag-search.md:108` + `12-node.md:238`). ⚠️ **Direct-API gateways are CONTESTED — do not silently pick a side:** `ai/00-ai-model-selection.md:62,135` and `ai/30-language.md:39` permit DashScope / SiliconFlow / ModelScope when the model is on neither Kilo nor OpenRouter (Fabrik's own sweet-spot MT model, `qwen-mt-turbo`, is **DashScope-only**), while `65-rag-search.md:108` bans direct vendor APIs outright. If the epic needs one, **flag the pack conflict and get an operator ruling** — do not plan around it either way. No LLM call: N/A.
28. **Watchdog + cost guardrails** — ⚠️ the watchdog sidecar is **opt-OUT on the `fabrik apply` path**: a spec with **no** `watchdog:` block still gets one (the dispatcher reads the raw dict — `.get("enabled", True)`). Its caps come from the **driver's** raw-dict defaults — **$5.00/day + 200 invocations/day** (`src/fabrik/drivers/watchdog.py:526-527`). ⚠️ The `$1.00` in `WatchdogConfig` (`spec_loader.py:389-390`) and its both-caps-zero validator are **dead on this path** — `fabrik apply` validates with `yaml.safe_load` and never constructs the Pydantic model, so a spec with `daily_budget_usd: 0` + `daily_invocations_cap: 0` **deploys genuinely uncapped — and NOTHING rejects it**: the Pydantic both-caps-zero validator (`spec_loader.py:621`) short-circuits on `self.enabled`, which defaults to `False`, so a spec that zeroes the caps without writing `enabled: true` is accepted on every path — while `fabrik apply` (raw dict, `.get("enabled", True)`) still deploys the sidecar. The epic MUST therefore state one of three: **accept** the defaults, **raise** them (`daily_budget_usd` / `daily_invocations_cap`), or **opt out** (`watchdog: {enabled: false}`) — never leave it unstated (`core/cost-budget.md` + `core/60-watchdog.md`).

### **Step 6: Project Type Classification & Smart Routing**

| Scaffold | Route | Skip | User Guide |
|---|---|---|---|
| `saas-skeleton` | epic-brief → core-flows → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | — | true |
| `python-api` | epic-brief → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | core-flows | per #16 |
| `python-api-gpu` | epic-brief → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | core-flows | per #16 |
| `node-api` | epic-brief → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | core-flows | per #16 |
| `file-api` | epic-brief → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | core-flows | false |
| `file-worker` | epic-brief → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | core-flows | false |
| `chrome-extension` | epic-brief → core-flows → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | — | true |
| `mobile-app` | epic-brief → core-flows → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | — | true |
| `desktop-app` | epic-brief → core-flows → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | — | true |
| `static-site` | epic-brief → core-flows → tech-plan → deploy-plan → ticket-outline → ticket-breakdown → execute | — | true |
| `wordpress` | Use `/opt/wpf/` factory (`wpf wp apply <domain>`) instead | not this workflow | — |
| `docusaurus` | epic-brief → ticket-outline → ticket-breakdown → deploy-plan → execute | core-flows, tech-plan | false |
| Feature (existing) | Use `mega-epic-breakdown/00-trigger-fabrik` (declare EXISTING mode at Step 0) instead | not this workflow | — |

**Cross-cutting** (anytime): `revise-requirements`, `cross-artifact-validation`, `implementation-validation`, `deploy`.

### **Step 7: Smart Route Presentation**

Emit **verbatim**, all fields populated:

> ***INFRA-CHECK:** Port:* `XXXX` *| Scaffold:* `<type>` *| x86_64:* `Confirmed/Unknown/Conflict` *| Duplicate:* `[none / name]` *| Internal APIs:* `[list or none]` *| User Guide:* `true/false` *| Design System:* `read/N-A` *| Platform Debt:* `<N> open` *| 12-Factor:* `compliant/violations` *| Concurrency:* `<mechanism>` *| i18n:* `<mechanism>/N-A` *| Responsive:* `375px/N-A` *| Dark+Light:* `mandatory/N-A` *| Abuse Detection:* `required/N-A` *| Email:* `two-stream/none/N-A` *| Vector DB:* `pgvector/none` *| FINANCIALS:* `required/N-A` *| Shape:* `<fields>` *| Rule Packs:* `<IDs>` *| Epic Flavor:* `Delta-feature/Retrofit/N-A` *| LLM Gateway:* `openrouter/kilo-cli/contested-<vendor>/none` *| Watchdog:* `accept-defaults/raise/opt-out`

**Propagated downstream:** Port, Scaffold, User Guide, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, **Epic Flavor** (Path B only — consumed by `01`'s Success-Criteria branch; `05` has **no** `Epic Flavor` field and re-derives the flavour from the ticket Title prefix), plus the **3 SaaS-conditional** fields `01` requires (`N/A` allowed): **Abuse Detection**, **Email**, **FINANCIALS** (`01-epic-brief-command:35`).
**Informational:** x86_64, Duplicate, Internal APIs, Design System, Platform Debt, 12-Factor, Vector DB, **Watchdog**, **LLM Gateway** — ⚠️ recorded on the INFRA-CHECK line **only**; `01`'s Metadata has no field for Watchdog / LLM Gateway, so restate them in the tech-plan rather than assuming they carry forward.

Present:

1. Project type + detection signals.
2. Research status + improvements.
3. Constraint findings (all 28).
4. Recommended route + skipped commands.
5. Suggested next command.

User confirms. Proceed.

## **Acceptance Criteria**

- MANDATORY ORCHESTRATOR PRE-FLIGHT (all 7) completed.
- `docs/operations/fabrik-lifecycle.md` read (it covers only stages 3–4 — deploy/runtime); project fits all 4 stages as enumerated in this file (or justified).
- Scaffold derived from concrete signals; never assumed.
- Preplan read if exists (`docs/preplans/`).
- All reference reads completed (tech-stack guide, prebuilt containers, AI taxonomy, lifecycle, rule packs, kilo agents).
- **4c-1 (⛔ BLOCKING) satisfied** — EVERY external dependency live-grounded THIS run via MCP, with the real
  endpoint / limits / **pricing** and a **cited source URL + fetch date**; any ungrounded dep is a named
  BLOCKING unknown with a resolution step. A memory-based external claim is a defect.
- **4c-2 (⛔ BLOCKING) satisfied** — the approach is backed by **cited current best-practice**, and every
  finding was **filtered through the Architectural Mandates + the 28 constraints**. A well-cited
  best-practice that violates a hard constraint (Stripe / a managed vector DB / a direct vendor LLM SDK)
  was **cut, not planned**.
- Cited source URLs passed into the downstream tickets so executors don't re-research them.
- **4c-3 (vendor notes)** applied for third-party vendors; any vendor unresolved after 3 attempts recorded as `BLOCKED: external-research-needed` on that ticket (does not halt the run).
- All 28 constraints verified. No silent unknowns.
- 12-Factor: compliant or violations resolved.
- Concurrency: mechanism stated; blocking rejected.
- i18n: mechanism confirmed for GUI types.
- Responsive: 375px floor confirmed for web GUI types.
- Dark + light mode: mandatory confirmed for GUI types.
- Shape block stated.
- Rule packs identified.
- INFRA-CHECK emitted verbatim, all fields populated.
- Route includes `deploy-plan` and `ticket-outline` in the sequence.
- Route confirmed by user.
- No unresolved conflicts at hand-off.
