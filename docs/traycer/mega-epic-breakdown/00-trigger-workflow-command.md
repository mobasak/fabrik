<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > trigger-workflow
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md.
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Project Intake (Entrypoint — Vision for NEW, Continuation for EXISTING)

This command is the **single entry point** for the `mega-epic-breakdown` workflow. It serves two modes — both produce a Vision Summary in the same shape so `02-epic-decomposition-command` consumes them identically.

- **NEW mode** — green-field project, no code, just an idea or research. Produces a fresh Vision Summary.
- **EXISTING mode** — running project, code exists, services may already be deployed. Produces a Vision Summary + Locked Decisions section + Compliance Report section (the deltas + retrofits driving epic decomposition).

Mode is **owner-declared at the start** (Step 0). Do not auto-detect from filesystem heuristics.

## Orientation

**Role.** Technical strategist. Build a shared, grounded understanding of what's being built (NEW) or extended (EXISTING), and produce a deploy-ready Vision Summary that grounds all downstream epic + ticket work in Fabrik's actual infrastructure.

**Output.** NEW mode → Vision Summary (exact structure from Step N4). EXISTING mode → same Vision Summary shape + `## Locked Decisions` + `## Compliance Report` (so `02-epic-decomposition-command` consumes both modes identically; the extras drive Retrofit epic emission in 02). No files written to disk by this command. Tickets are created later by `03-expand-epic-files-command`.

**Agreed outputs by mode:**

- **NEW:** WHAT we're building (full feature inventory, nothing vague), WHO it's for (named personas, not "users"), WHY it matters (value streams), HOW BIG it is (single vs multi-epic), WHICH SERVICES (every major tech choice resolved — grounded in `AGENTS.md` § Infrastructure Services + `docs/reference/technology-stack-decision-guide.md`), WHAT EXISTS to leverage, WHAT DOESN'T FIT, WHAT'S MISSING.
- **EXISTING:** WHAT EXISTS (project snapshot), WHAT'S LOCKED (decisions that cannot change — data exists, users paying, APIs live), WHERE IT DEVIATES from current scaffold standards/rule packs (and per-gap fix-now/fix-later/accept-as-legacy), WHAT TO BUILD NEXT (delta only, not re-planning), WHICH SERVICES the delta needs (per current ruleset, inheriting locked decisions).

**Core principles.** The goal is shared understanding, not a document. Questions are investments in correctness; surfacing assumptions early is cheap, fixing wrong epics is expensive. **Planning is SLOW. Execution is FAST.** NEW: never rush, never skip a constraint, never assume when you can ask. EXISTING: respect what's built — read the vision from the codebase, do NOT re-derive it; do NOT re-decide locked tech choices; DO compare against current rules and surface deviations.

**Owner's decision criteria** (apply to every tech choice, and used in N3c challenges):

1. **Quality first** — production-grade, no shortcuts. Never sacrifice quality to save money.
2. **Total cost of ownership** — dev time is the most expensive resource. A $10/month managed service that saves 2 weeks of dev is a win. Don't build for days what you can buy for dollars.
3. **Speed to ship** — prefer solutions that deploy through the standard pipeline (WSL → push → `fabrik apply` deploys via SSH+Compose and fires 10 registrars (only 7 are flag-driven; grafana is always-on, glitchtip is kind-driven, and `watchdog` is ON by default — opt-OUT); `fabrik redeploy` handles code-only updates — see `docs/operations/fabrik-lifecycle.md`). Custom CI/CD or off-pipeline infra = slower and riskier.
4. **Easy to maintain** — when two solutions both work, prefer the one needing less ongoing attention. Start with what exists on the VPS; escalate when proven necessary.
5. **Set and forget** — prefer low-maintenance solutions (self-hosted `postgres-main` / `redis-main` on the fleet; managed Paddle, Cloudflare, Resend where a managed edge genuinely wins) over anything that needs babysitting.

**Grounding rules.** Ground in what EXISTS on the VPS (read `AGENTS.md` § Infrastructure Services fresh each run), not theoretical architecture. Decide NOTHING about epic boundaries — that is `02-epic-decomposition-command`. Challenge research against Fabrik reality, but treat it as expert input, not hallucination to dismiss. All paths are Linux (WSL Ubuntu 24.04) — never generate Windows-style paths.

**Fabrik lifecycle (mental model).** Every project passes through 4 stages (full detail in `docs/operations/fabrik-lifecycle.md`):

1. **Intent & Scaffolding (WSL)** — `fabrik preplan` → `fabrik scaffold` → AI guardrails + spec `shape:` block. The scaffold is a Context Injection.
2. **Agentic Implementation (WSL)** — tickets dispatched to agents (Claude Code, Windsurf Cascade, Kilo CLI).
3. **Proper Registration (VPS)** — `fabrik apply` fires **10** registrars. **Only 7 are flag-driven** — postgres (`needs_database`), redis (`needs_cache`), gatus (`is_public`+domain), backrest (`has_persistent_data`), authelia (`is_admin_dashboard`+domain), meilisearch (`has_search_feature`), prometheus (`exposes_metrics`+domain). The other 3 are NOT flag-driven: **grafana** fires *always*, **glitchtip** fires on `shape.kind`, and **`watchdog`** fires from the spec's `watchdog:` block and is **ON by default** (opt-OUT: disable with `watchdog: { enabled: false }`).
4. **Verification & Testing** — `fabrik verify`, drift detection (`fabrik audit-registrars`), alerting.

If a NEW vision cannot pass all 4 stages, state this explicitly and justify. If an EXISTING project has incomplete stages, flag them in the Compliance Report (these are lifecycle gaps, not separate from compliance).

## Architectural Mandates (non-negotiable — single source of truth)

These are **vision-level architectural commitments**. Every epic dispatched from this vision inherits them. **Violations block vision confirmation.** Per-epic verification happens later in `epic-to-ticket-workflow/00-trigger-workflow-command` Step 5 — but ⚠️ its overlay constraints #17–#24 cover only **8 of these mandates** (12-Factor, Concurrency, i18n, Shape, Responsive, Dark+Light, Abuse Detection, Email). **Resilience, Observability, and Fleet-topology (`target_vps`) have NO epic-level overlay constraint** — they are asserted here at vision level and never re-checked per epic. Verify them explicitly in the epic's tech-plan — but the commitment is made here.

- **12-Factor App — ALL TWELVE.** Every backend service satisfies **all 12** factors of [The Twelve-Factor App](https://12factor.net/) — not just the four most often quoted. Each below carries its **Fabrik binding** (source re-verified live 2026-07-12). **Violations are blockers.**

| # | Factor | The mandate (12factor.net) | Fabrik binding — the violation to catch |
|---|---|---|---|
| I | Codebase | One codebase per app, many deploys. *"Multiple apps sharing the same code is a violation."* | One repo per project; shared code → `fabrik-lib`. **Deliberate, stated deviation:** 12F prescribes including shared code *"through the dependency manager"*; Fabrik **vendors (copies)** it for self-contained builds. Each app still owns its codebase, so the intent holds. |
| II | Dependencies | *"Never relies on implicit existence of system-wide packages."* Shelling out to a system tool ⇒ **vendor the tool**. | Declare every dep. **Never assume `curl` / ImageMagick exist in the image.** PDF/browser work → **Gotenberg / Browserless** backing services, not a system binary. |
| III | Config | Config in **env vars**. Litmus test: *"could the codebase be open-sourced at any moment without compromising credentials?"* **Rejects grouped named environments** — env vars are granular + orthogonal. | `os.getenv("KEY", "default")`; zero secrets in code. ⚠️ No `config/production.yml`-style env group — 12F names that anti-pattern explicitly. |
| IV | Backing services | Attached resources, swappable by **config alone** — *"no distinction between local and third party services."* | `DATABASE_URL` / `REDIS_URL` are config: WSL-dev ↔ `postgres-main:5432` is an **env change, never a code change**. |
| V | Build, release, run | Strict separation; releases **immutable** with a **unique release ID**. *"Impossible to make changes to the code at runtime."* | `fabrik apply`/`redeploy` build then deploy; the **git SHA is the release ID**. **Never hot-patch a running container.** |
| VI | Processes | Stateless + share-nothing. *"**Sticky sessions are a violation of twelve-factor and should never be used or relied upon.**"* Session state → **Memcached or Redis**. | Sessions/cache → `redis-main`. **Both** file-based **and sticky** sessions are violations. |
| VII | Port binding | **Completely self-contained**; exports HTTP by **binding to a port**; *"does not rely on runtime injection of a webserver."* | Uvicorn binds inside the container; **Traefik is the routing layer** — which is *why* compose declares **no host `ports:`**. |
| VIII | Concurrency | Scale **out** via the process model. *"**Processes should never daemonize or write PID files.**"* | `web` + `file-worker` types; scale by adding processes. Docker/systemd supervises — **never daemonize or write a PID file**. |
| IX | Disposability | Fast startup. **SIGTERM:** web = stop listening + drain; **worker = return the current job to the queue**; *"all jobs are reentrant… idempotent."* | ⚠️ **The missing half.** `fabrik-lib/job-queue` must **requeue on SIGTERM** and **every job must be idempotent** — not merely "fast startup". |
| X | Dev/prod parity | *"**Resists the urge to use different backing services between development and production.**"* Same type **and version**. | ⚠️ **Binds the two-env rule:** WSL dev and VPS both run **PostgreSQL + Redis**. **No SQLite locally**, no in-memory stand-in for Redis. |
| XI | Logs | **Unbuffered to `stdout`**. *"**Never** concerns itself with routing or storage… should not attempt to write to or manage logfiles."* | `structlog` → stdout. **Never write or rotate a logfile.** Promtail → Loki is the *environment* doing the routing. |
| XII | Admin processes | One-off tasks run **against the same release + config**; admin code **ships with the app**. | Alembic migrations live in the repo and run against the **deployed release/env** — never from a laptop against prod. |

- **Concurrency** — every service handles multiple simultaneous requests. Never single-threaded blocking.
- **i18n** — every scaffold with a user/admin GUI surface (per the Rule-area applicability matrix at Step E3.B — **feature-trigger, NOT scaffold-type-gated**; includes python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output) supports multi-language from day one (en + tr minimum). Translation validated via `scripts/validate_i18n.py` (3-level: structural, back-translation, native-speaker critique). Adding a language = adding a locale file, zero code changes.
- **Responsive** — every scaffold with a web GUI surface (same feature-trigger as i18n) responsive from 375px to 2560px (RWD1–RWD10). No desktop-only layouts. See `docs/reference/mobile-responsive-testing-guide.md`. Carve-outs: chrome-extension (400px fixed popup/sidepanel), mobile-app (native UI, not web breakpoints), desktop-app (electron window sizing).
- **Dark + light mode** — both mandatory for every scaffold with a GUI surface (same feature-trigger as i18n). OS preference detected, manual toggle, preference persists.
- **Resilience** — every external call has timeout + retry with backoff + circuit-breaker + graceful fallback. `/health` tests ALL real deps. Rule pack: `.windsurf/rules/core/58-resilience.md`. Each project gets `docs/RESILIENCE.md` template at scaffold time — filled when external deps are added.
- **Abuse detection** — every SaaS with a free tier must implement registration gating (IP rate limit, disposable email block, progressive unlock). Rule pack: `.windsurf/rules/saas/87-abuse-detection.md`.
- **Email two-stream** — transactional and marketing email MUST be on separate streams/subdomains. Rule pack: `.windsurf/rules/core/86-email-templates.md`.
- **Shape contract** — every Fabrik-deployed service has a `specs/services/<id>.yaml` whose `shape:` block declares which registrars fire; code MUST match shape. Client-only artifacts (chrome-extension CRX, mobile-app binary, desktop-app binary) ship through their own distribution channels (Chrome Web Store, EAS/App Stores, signed installers) and have no Fabrik spec — only their backends do.
- **Observability** — every backend service exposes `/health` for Gatus and `/metrics` for Prometheus. Static artifacts (static-site, docusaurus) have no app process exposing these endpoints — Gatus probes them externally for liveness instead.
- **Fleet topology (multi-host)** — the fleet is **3 permanent hosts**: vps1 (LA, hub) + vps2 (Coventry UK, spoke) + vps3 (Coventry UK, spoke), connected by a WireGuard mesh (`10.99.0.0/24`). Shared infra (postgres-main, redis-main, glitchtip-web, authelia, loki, meilisearch) is **hub-only**; spoke services reach them via the mesh IP `10.99.0.1:<port>`. Every spec declares **`target_vps:`** (`vps1` | `vps2` | `vps3`; default = `vps1`) per the `Spec.target_vps` field in `src/fabrik/spec_loader.py` (regex `^vps[1-9][0-9]?$`). Resolution order: `--target-vps` CLI flag > `.fabrik/state/<id>.json::target_vps` > spec `target_vps:` field > `vps1` default (see `30-ops.md` § Multi-host targeting). Hub vs spoke decision is a Vision-level choice: hub for shared-infra-coupled services; spokes for tenant-isolated, lower-latency-to-EU, or capacity-spillover workloads. See [`docs/infrastructure/vps-complete-inventory.md`](../../infrastructure/vps-complete-inventory.md) for live state. Live example: `specs/services/spoke-canary.yaml`.

### Shape model (8 canonical flags)

Every `specs/services/<id>.yaml` declares `shape:` with these booleans. Each flag fires registrars on `fabrik apply`. The Vision Summary must propose the shape per service.

| Flag | True when | Fires |
| --- | --- | --- |
| `is_public` | Anonymous traffic hits it (marketing site, landing, public API) | **Gatus** uptime probe (⚠️ requires `spec.domain` too) — `infrastructure.py::resolve_applicability` |
| `is_admin_dashboard` | UI behind auth for owner/staff | **Authelia** forward-auth middleware (⚠️ requires `spec.domain` too) |
| `has_bearer_api` | M2M/token-auth API endpoints | **No registrar of its own.** It only takes effect *inside* the Authelia registrar — which requires `is_admin_dashboard: true` **+** `spec.domain` — where it installs the `^/api/` bypass so M2M callers skip 2FA (narrow it with `shape.bearer_bypass_prefix`). ⚠️ On a spec WITHOUT an admin dashboard it fires **nothing**: `saas-skeleton` ships `is_admin_dashboard: false` + `has_bearer_api: true`, so no bypass is installed (and nothing 302s — there is no Authelia rule at all). It does NOT fire gzip; gzip is a scaffold-emitted Traefik label, not a registrar. |
| `has_persistent_data` | Writes durable state (DB rows, uploaded files, vector store) | Backrest backup plan |
| `needs_database` | Reads/writes PostgreSQL | Postgres registrar creates DB + user on `postgres-main` |
| `has_search_feature` | Full-text or semantic search | Meilisearch index |
| `needs_cache` | Redis for sessions, queues, rate-limit, cache | Redis registrar allocates index, injects `REDIS_URL` |
| `exposes_metrics` | App serves `/metrics` (Prometheus format) | **Prometheus** scrape target (⚠️ requires `spec.domain` too — a domainless worker with this flag gets NO Prometheus job, silently) |

Plus `kind:` (`service` / `worker` / `static`; the `Kind` enum also has a 4th member, `WORDPRESS`, kept for the legacy deploy path — per `src/fabrik/spec_loader.py:Kind`) — drives template selection and applicability gates (e.g., `kind: service|worker|wordpress` gates GlitchTip; `static` skips it). Scaffold-to-kind mapping: python-api/python-api-gpu/node-api/saas-skeleton/file-api/chrome-extension/mobile-app/desktop-app → `service`; file-worker → `worker`; static-site/docusaurus → `static`. (chrome-extension/mobile-app/desktop-app are `kind: service` — their companion backend deploys per `templates/<type>/defaults.yaml`; only the client artefact ships separately.) **WordPress is out of scope for this workflow** — `Kind.WORDPRESS` is recognised by the codebase for legacy reasons but Fabrik scaffolding does NOT produce WordPress projects; WordPress site creation + deployment lives in the standalone `/opt/wpf` project (use `wpf new <name>` + `wpf wp apply` there). If a Vision Summary names "wordpress site" as a feature, route the owner to `/opt/wpf` and treat the WordPress side as out-of-scope for the current mega-epic-breakdown run.

## Input Contract

**Auto-loaded (both modes):**
- `AGENTS.md` — full project context, infrastructure services, microservices table, planning constraints.
- `docs/operations/fabrik-lifecycle.md` — deploy/runtime behavior, data safety.
- `docs/reference/technology-stack-decision-guide.md` — stack defaults and decision flowchart.
- `docs/reference/prebuilt-app-containers.md` — off-the-shelf solutions that eliminate custom work.
- `docs/BUSINESS_MODEL.md` § Project Portfolio — duplicate check.
- `PORTS.md` — port allocations.

**NEW mode — two entry paths:**

**Path A — Research exists:**
- Discovery order (stop at first match):
  1. User names a path → read it.
  2. `docs/preplans/*.md` → read fully.
  3. `docs/development/plans/00-research.md` → read fully.
  4. Scan `docs/development/plans/*.md` for `YYYY-MM-DD-*.md` files.
- Multiple files? Read ALL. If they conflict, flag the conflict — do not silently resolve.

**Path B — Just an idea:**
- Owner describes the idea in conversation. No files needed.
- Interview to build the vision: What is it? Who uses it? What does it do? What's the revenue model?
- Guide the owner to think through features, personas, constraints.
- If an area is complex, suggest: "This needs deeper research. Want to pause, research [topic] with Gemini/Claude, and drop the results in `docs/development/plans/`?"

**EXISTING mode — required inputs:**
- The project folder path (e.g., `/opt/youtube`) — owner provides.
- Owner's description of what they want to build next ("add RAG search", "add mobile app", "add billing").
- Optionally: research files dropped in `docs/development/plans/` (consumed the same way as NEW mode Path A).

**EXISTING mode — additional auto-loads:**

- `docs/reference/fabrik-cli-reference.md` — needed to interpret `fabrik validate` and `fabrik audit-registrars` output (present/missing/drift/n/a/override/unknown) in Step E3.A.

**EXISTING mode also reads from the project itself:**
- `project.yaml` — scaffold type, ports, shape flags.
- `specs/services/*.yaml` — deployed services, shape blocks, registrars.
- `compose.yaml` / `Dockerfile` — infrastructure, base images, services.
- `.env.example` — environment variables, external service dependencies.
- `src/` or `app/` — codebase structure, modules, API routes.
- Database schema (migrations or models).
- `docs/` — existing architecture docs, preplans, FINANCIALS.md.
- `.windsurf/rules/` — rule packs are synced; check if project follows them. Index below.

**⚠ Project files may be pre-rules, missing, or stale.** Existing projects predate current Fabrik conventions. Treat the files above as *evidence*, not as ground truth. Specifically:

- `project.yaml` may be absent entirely (project predates the scaffolder) → infer scaffold type from `compose.yaml` + `src/` structure; flag as gap.
- `specs/services/*.yaml` may have no `shape:` block, partial flags, or flags that contradict the code → cross-check by reading the code, not by trusting the spec. Missing/wrong shape = compliance gap → Retrofit epic.
- `compose.yaml` may violate current rule pack `core/30-ops.md` (Alpine images, `ports:` exposed, no `container_name`, no `deploy.resources.limits.memory`, `localhost` in env, wrong Traefik entrypoint) → each violation is a compliance gap.
- `.env.example` may be missing, out of sync with `.env` on VPS, or expose secrets → flag and treat the live VPS state as authoritative for current behavior. The SSH command must target the host the service actually runs on — derive from `specs/services/<id>.yaml::target_vps` (default `vps1`): `ssh root@<target_vps> "cat /opt/<name>/.env"`. Hub services → `ssh root@vps1`; spoke services → `ssh root@vps2` or `ssh root@vps3`.
- `docs/` may contain pre-rules conventions, dead links, or files outside the current allowlist (root files · scaffold docs · `docs/development/plans/YYYY-MM-DD-*.md` · `docs/reference/**` · `docs/archive/**`) → flag as doc-hygiene gap.
- Database schema may have drifted from migrations → treat the live DB (`docker exec postgres-main psql -d <db> -c '\d'`) as authoritative.
- `.windsurf/rules/` directory may be absent (older scaffolds didn't sync rules) → flag and propose syncing via `fabrik fix /opt/<project> --type <scaffold-type>` (per `fabrik fix --help`, adds missing required files including `.windsurfrules` and `.windsurf/rules/`) as part of the Retrofit set.

**How gaps surface:** Every divergence between project files and current rule packs / shape model becomes a row in the Compliance Report (Step E3.C). Per-gap owner decision (Fix-now / Fix-later / Accept-as-legacy) determines whether it becomes a Retrofit epic in 02, goes to the Compliance Report as deferred (Fix-later), or is recorded as accepted legacy (no action).

**Rule pack index** (consulted in Step E3.B for rule-pack judgment):

| Pack | Covers |
| --- | --- |
| `core/10-python.md`, `core/12-node.md`, `core/20-typescript.md` | Language-level conventions, project layout (Python / Node.js / TypeScript) |
| `core/15-api-contracts.md` | API request/response contracts, error shapes |
| `core/25-data-postgres.md` | Schema, migrations, connection patterns |
| `core/30-ops.md` | Compose structure, Traefik labels, base images, networking |
| `core/35-security-auth.md` | Authelia, M2M tokens, password policy, secrets |
| `core/40-documentation.md` | Doc Sync Matrix, allowed `.md` locations |
| `core/42-docusaurus.md` | Docusaurus-specific structure |
| `core/45-testing-strategy.md` | Test pyramid, integration vs unit, no-mock-DB rule |
| `core/50-code-review.md` | Review gates, pre-merge checks |
| `core/55-observability.md` | `/health` + `/metrics`, Gatus, Prometheus, Promtail |
| `core/58-resilience.md` | Timeout/retry/circuit-breaker/fallback for external calls |
| `core/60-watchdog.md` | Sidecar/auto-recovery patterns (e.g. watchdog-test → Claude-Code-driven container self-heal) |
| `core/65-rag-search.md`, `core/66-rag-chunking.md` | RAG ingestion, embedding, chunking; MeiliSearch vs pgvector decision |
| `core/67-file-api.md` | File-handling discipline — storage backend (`fabrik-lib/storage`: B2/R2), presigned URLs, multipart streaming, MIME validation, content-hash dedup, AV scan, image-broker delegation |
| `core/75-workers-jobs.md`, `core/76-gpu-workers.md` | Background jobs, GPU workers |
| `core/85-payments-billing.md` | Paddle / iyzico billing flows (Stripe NOT available to TR entity) |
| `core/86-email-templates.md` | Email two-stream (transactional vs marketing) |
| `core/90-bootstrap-scripts.md` | `bootstrap-vps.sh` / `bootstrap-spoke-restore.sh` / `bootstrap-hub.sh` — fresh-install + DR-restore paths |
| `core/app-audit-log.md` | In-app audit trail (tenant-scoped, immutable rows) |
| `core/cost-budget.md` | Per-ticket / per-feature LLM + infra cost budgeting; OpenRouter gateway constraint |
| `core/self-healing.md` | Higher-level self-healing strategy: drift → diagnose → action loops; Tier A/B/C decision matrix |
| `saas/60-saas-ui.md`, `saas/95-multi-tenant-saas.md` | SaaS UI patterns, tenancy |
| `saas/87-abuse-detection.md` | Free-tier abuse gating |
| `saas/88-saas-launch-checklist.md` | Launch gates |
| `chrome-ext/70-chrome-ext.md` | Manifest V3, popup/sidepanel patterns |
| `desktop-app/72-desktop.md` | Electron 30+, process isolation + IPC zero-trust, Azure Trusted Signing / Apple notarization, R2 auto-update, SQLCipher local storage, KVKK opt-in telemetry |
| `mobile-app/80-mobile.md`, `81-mobile-billing.md`, `89-mobile-launch-checklist.md` | RN/Expo, IAP, store launch |
| `core/*-design-system.md`, `mobile-app/*-design-system.md` | Brand design systems (Ocoron, Tojlo) |

## Processing User Request

This command has a mode declaration at the start, then a series of checkpoints depending on the mode. Do NOT silently proceed past a checkpoint.

**Owner non-responsive at a checkpoint** — if the owner stops replying mid-run, the partial Vision Summary persists in Traycer's conversation context (no files written by this command). To resume: the owner re-enters the conversation and Traycer picks up at the last unresolved checkpoint. **Do NOT** time out and self-confirm; **do NOT** start over from Step 0 unless the owner explicitly says "restart". Silence ≠ confirmation; silence = "session paused, waiting for owner".

### Step 0: Mode Declaration

Ask the owner explicitly at the very start:

> *"Is this a NEW project (no code yet, just an idea or research) or an EXISTING project (code exists, services may already be deployed)?"*

- Owner says **NEW** → follow the **NEW MODE** path (Steps N1–N5 below).
- Owner says **EXISTING** → follow the **EXISTING MODE** path (Steps E1–E5 below).

Do NOT auto-detect from filesystem. Do NOT skip this question. The owner declares the mode.

---

## NEW MODE — Vision Intake

### Step N1: Context Orientation

The Input Contract files are already auto-loaded. Now focus on these specific sections within them (and one new file):

- `AGENTS.md` § `Infrastructure Services — Running on VPS` — what's already deployed (hub vs spoke per service).
- `AGENTS.md` § `Development Environment` — **3-host fleet topology** (vps1 hub + vps2/vps3 spokes, wg0 mesh, per-host DNS).
- `AGENTS.md` § `Fabrik Microservices` — existing custom services (live vs retired/not-deployed).
- `AGENTS.md` § `Scaffold Types` — the 11 scaffoldable types + shape flags emitted by each (`templates/<type>/defaults.yaml` is the contract). ⚠️ The table also carries a **`wordpress` row, marked RETIRED** (scaffold path retired 2026-06-17, `ef27a2c`) — it is **not** a scaffoldable type: treat WordPress as out of scope and route it to `/opt/wpf`.
- `AGENTS.md` § `MANDATORY ORCHESTRATOR PRE-FLIGHT` — run all 7 checks listed there (Ports, Business Model, Microservices, Hardware Audit, Design System, External Knowledge, fabrik-lib).
- `AGENTS.md` § `Planning Constraints` — all 12 constraints. **These are a separate list from Step N3i's 20 checks** and cover angles mostly absent from N3i (Module dependencies, DNS via site-provisioner, Scaffold immutability, State conflicts). Note Solo-dev capacity DOES appear in both (N3i #9). Apply both: AGENTS.md's 12 at orientation time, N3i's 20 at vision-verification time.
- `docs/infrastructure/vps-complete-inventory.md` — canonical fleet inventory if the AGENTS.md summary is ambiguous on host placement.
- `docs/operations/fabrik-lifecycle.md` — runtime behavior, data safety, deploy/redeploy/destroy.
- `docs/reference/technology-stack-decision-guide.md` — stack defaults.
- `docs/reference/prebuilt-app-containers.md` — off-the-shelf solutions.
- `docs/BUSINESS_MODEL.md` § Project Portfolio — duplicate check.
- `PORTS.md` — port allocations.
- If `project.yaml` exists in the working directory → read it for scaffold type and existing shape.

### Step N2: Consume Input

**Path A (research files exist):** Read ALL research files found in the Input Contract discovery. Treat as EXPERT INPUT — do not second-guess well-reasoned conclusions. Do challenge conclusions that conflict with Fabrik's actual infrastructure or constraints. If multiple files conflict, flag the conflict — do not silently resolve.

**Path B (just an idea, no files):** Conduct a structured interview:
- "What is this product? What problem does it solve?"
- "Who uses it? Name the user types."
- "What are the main features? Walk me through what a user does."
- "How does it make money or save money?"
- "Are there any constraints you already know about?"

Synthesize answers into the same internal structure (vision, personas, features, constraints, tech choices) that research would produce. Then continue to Step N3 identically — the analysis steps work the same regardless of input path.

### Step N3: Analyze and Improve Input

**Execute N3a → N3j in order. Do not skip; some later sub-steps depend on earlier ones (e.g., N3i constraint verification consumes the feature list from N3a, the tech choices from N3c, and the opportunities from N3d).**

**N3a. Extract** from input (research or interview synthesis): product vision (what/for whom/why), all personas (named/implied), all features (numbered inventory), all constraints, all tech choices (made/implied), revenue/value model.

**N3b. Identify gaps** → become Open Questions: missing personas, missing revenue model, missing features (Y component not mentioned — in scope?), missing auth decision (`fabrik-lib/fastapi-user-auth` Pattern A / Authelia / custom?), etc.

**N3c. Challenge research against Fabrik reality and owner's decision criteria.** External research may violate the owner's 5 decision criteria (Orientation § Owner's decision criteria). Apply these 6 checks:

- **Expensive where free exists?** Research proposes paid service → check if a VPS service already solves it (Apprise, Gotenberg, MeiliSearch, Backrest, n8n — all deployed, all free). State: "Research suggests [X] but [Y] is already deployed on VPS at zero cost."
- **Complex where simple exists?** K8s/microservice mesh/custom auth proposed → SSH+Docker Compose + Authelia + single-container deploys handle it. Fabrik uses `fabrik apply`, not Helm.
- **Build where consume exists?** Check prebuilt containers, existing Fabrik microservices (site-provisioner — the only one live on the fleet; image-broker and the rest are retired/not deployed), VPS services, `/opt/fabrik-lib/` vendorable modules (see `fabrik-lib/README.md` for the module table).
- **High-maintenance where set-and-forget exists?** Prefer solutions that auto-heal/auto-backup/auto-monitor via the existing Prometheus/Gatus/Backrest stack.
- **Incompatible with Fabrik infra?** Port conflicts (`PORTS.md`), Alpine images (bookworm-slim only), `localhost` assumptions (use `postgres-main:5432`), x86_64 issues, 12-Factor violations.
- **Duplicate functionality?** Check `docs/BUSINESS_MODEL.md` § Portfolio + `AGENTS.md` § Microservices.

If research direction is fundamentally wrong for Fabrik (e.g., AWS serverless when everything deploys to VPS via `fabrik apply`), say so directly and recommend an alternative or pause for re-research.

**N3d. Identify opportunities** → become Backing Services: VPS services (postgres-main, redis-main, MeiliSearch, Gotenberg, Browserless, Apprise, n8n, Backblaze B2), prebuilt containers, consumable Fabrik microservices.

**N3e. Scale assessment** (by feature complexity, NOT ticket count — ticket counts belong to `05-ticket-outline-command`):

- Classify each feature: `small` (single endpoint/page), `medium` (multi-component), `large` (cross-cutting system).
- Signal only — do NOT assign features to epics (that's `02-epic-decomposition-command`):
  - **Under 8 features total** → **single epic** (use the epic-to-ticket workflow directly) — unless 2+ are large, which forces 2 epics.
  - **8–15 features total** → **likely 2–3 epics**.
  - **More than 15 features total** → **likely 4–7 epics**.
  (Bands are on the **total feature count** and are disjoint; size only escalates, never de-escalates.)
  - Massive scope, many large → re-scope or accept 7+ epics.

**N3f. Context window check.** Research files >approaching context limits → flag: "Research files ~[N]K tokens. Risk of dropping details. Recommend splitting into focused files per domain."

**N3g. API contract check.** If vision relies on an existing Fabrik microservice (site-provisioner — the sole live one) and assumes endpoints not in current contract (`docs/reference/service-contracts/[service].md`) → Open Question: "Vision assumes [service] can do [X], but contract doesn't include it. New endpoint or scope adjustment?"

**N3h. Research sufficiency.** Any critical area THIN (auth not addressed, data model vague, pricing unclear)? → Recommend pause-and-research with concrete questions, drop results into `docs/development/plans/`, re-run. Do NOT proceed on a thin foundation.

**N3i. Constraint verification** (20 checks — state each as `all clear` / `conflict (<details>)` / `unknown (<question>)`):

1. **x86_64 VPS** — all containers amd64.
2. **Budget** — state any paid service dependencies with estimated monthly cost.
3. **Existing services** — list VPS services the vision will use.
4. **Duplicate check** — no overlap with existing projects.
5. **Port conflicts** — check `PORTS.md` per service.
6. **SSH+Docker Compose deployment** — every component deployable via `fabrik apply`?
7. **No Alpine** — bookworm-slim only (`30-ops.md`).
8. **12-Factor compliance** — any architectural violations?
9. **Solo dev capacity** — achievable by one person + AI agents?
10. **Observability** — every service exposes `/metrics` (Prometheus) and `/health` (Gatus)?
11. **Vector DB ban** — Pinecone/Qdrant/Weaviate/Milvus = reject. pgvector on `postgres-main` only (`65-rag-search.md`).
12. **Email streams** — if product sends email, transactional + marketing on separate streams/subdomains (`86-email-templates.md`).
13. **Compose invariants** — every Fabrik-deployed service declares `container_name: <name>`, `deploy.resources.limits.memory`, `platform: linux/amd64`, no `ports:`, and joins the **`fabrik`** Docker network (NOT `coolify` — renamed 2026-05-31; `fabrik apply` REJECTS the old name). Enforced fatally by `deployer_ssh._validate_compose()`. See `30-ops.md`.
14. **Billing routing** — if product takes payment: TR domestic SaaS → **iyzico**; international cross-border → **Paddle Billing v2** (MoR); mobile digital goods → **RevenueCat + IAP**. **Stripe is NOT available to the TR-resident LLC** — never plan around it (`85-payments-billing.md`). PayTR is WooCommerce-only, not SaaS.
15. **LLM gateway** — if the product calls any LLM: **OpenRouter is the default gateway**, and is **REQUIRED for embeddings** (Kilo has no embeddings endpoint — `65-rag-search.md:94`). **Kilo CLI is a peer gateway**, valid for low-volume LLM tasks *including* app components (classifier / answer-generator / summarizer — `65-rag-search.md:95-97`); its real constraint is **3–5s/call subprocess overhead**, not a prohibition. **Never wire a general-purpose vendor SDK** (`openai`, `@anthropic-ai/sdk`, `google-cloud-aiplatform`) as the LLM path (`65-rag-search.md:108` + `12-node.md:238`). ⚠️ **Direct-API gateways are CONTESTED — do not silently pick a side:** `ai/00-ai-model-selection.md:62,135` and `ai/30-language.md:39` permit DashScope / SiliconFlow / ModelScope when the model is on neither Kilo nor OpenRouter (Fabrik's own sweet-spot MT model, `qwen-mt-turbo`, is **DashScope-only**), while `65-rag-search.md:108` bans direct vendor APIs outright. If the epic needs one, **flag the pack conflict and get an operator ruling** — do not plan around it either way. No LLM call: N/A.
16. **i18n en+tr from day 1** — every GUI / user-facing surface ships with `en` + `tr` locale files. Translation validated via `scripts/validate_i18n.py`. Adding a language = locale file only, zero code changes (Architectural Mandate § i18n).
17. **Target host (per service)** — every Fabrik-deployed service declares `target_vps:` (`vps1` / `vps2` / `vps3`; absent → `vps1`). Hub for shared-infra-coupled; spoke for tenant-isolated / EU-proximate / capacity-spillover (Fleet topology mandate above).
18. **KVKK / GDPR data residency** — if product stores user PII or file blobs: PII lives on self-hosted `postgres-main` and blobs in `fabrik-lib/storage` (Backblaze B2) — for KVKK/EU alignment host the storing service on an EU-proximate spoke (`vps2`/`vps3`, Coventry UK) and/or a B2 EU-region bucket; file erasure events use `file_erasure_audit` hash-chained table with 3-year retention (`67-file-api.md`, Article 7(3)); telemetry opt-in only — no foreign-cloud egress without consent (`72-desktop.md`).
19. **Watchdog sidecar (when needed)** — if any service calls paid LLM APIs in **any unattended loop, scheduled job, or user-triggered flow that can re-fire without human approval** (i.e., not strictly one call per explicit human click): declare the watchdog sidecar explicitly (`60-watchdog.md`) **AND a `cost-budget` cap** (`cost-budget.md`) — ⚠️ the watchdog is **opt-OUT on the `fabrik apply` path**: apply feeds `resolve_applicability()` the RAW spec dict, where `enabled` defaults to `true`, so EVERY spec without `watchdog: { enabled: false }` gets the sidecar — and one that declares **no** caps inherits the **driver's** defaults, **$5.00/day + 200 invocations/day** (`src/fabrik/drivers/watchdog.py:526`). ⚠️ The `$1.00` default and the both-caps-zero validator on `WatchdogConfig` (`spec_loader.py:361`) are **dead on the apply path** — apply parses with `yaml.safe_load` and never builds the Pydantic model — so `daily_budget_usd: 0` + `daily_invocations_cap: 0` ships a **genuinely uncapped** sidecar. Declare the caps deliberately — accept, raise, or opt out — never inherit or zero them by accident. (⚠️ Known code bug: `audit-registrars` and `destroy` feed the *validated* model instead, where `enabled` defaults to `false` — so the same sidecar is reported `n/a` and is never torn down. Declare the caps explicitly; do not rely on the default.). Concrete trigger examples: agentic loop with self-retry, cron job that calls an LLM, webhook that re-invokes on retry, user chat with reasoning steps. Concrete non-triggers: one LLM call per human button-press with no auto-retry and no agentic recursion. State the chosen caps in the epic; a cap raised without thought is how a runaway-reasoning loop empties the budget overnight.
20. **Node ESM / Python version floors** — Node greenfield: `"type": "module"` + `engines.node ">=22.0.0"` (24 LTS preferred). Python: `python:<current-stable>-slim-bookworm` (3.13 today). `12-node.md` + `10-python.md`.

**N3j. Multi-scaffold check.** Single vision spanning multiple scaffold types (e.g., python-api + saas-skeleton + mobile-app, or chrome-extension + python-api backend) → list which features map to which scaffold. Strong multi-epic signal. **If scaffolds share no data, no auth, no deploy coupling** → candidate for **separate `fabrik scaffold` projects with own lifecycles**, not epics. Ask: "These components seem independent. Separate projects or epics within one project?" Note: if the vision includes a WordPress site, route the WordPress side to the standalone `/opt/wpf` project (out of scope here) and only retain the non-WordPress scaffolds for this run.

#### ── CHECKPOINT N-1: Present Analysis ──

Present: (1) Features extracted with complexity classification (N3a+N3e), (2) Gaps (N3b), (3) Conflicts with Fabrik (N3c), (4) Opportunities (N3d), (5) Scale estimate + single/multi-epic classification (N3e), (6) Constraints `all clear`/`conflict`/`unknown` (N3i), (7) Research sufficiency notes (N3h).

Ask: "Do these features capture your full vision? Anything missing or wrong?" + "Can you answer the gap questions?" + (if research thin) "Recommend researching [topic] further. Want to pause?"

Owner adds research → re-read + re-analyze. Owner answers questions → update notes. Owner confirms → Step N4.

**CRITICAL: STOP GENERATION HERE.** Do NOT simulate the owner's response. Silence ≠ confirmation.

### Step N4: Draft Vision Summary

Assemble the Vision Summary from Steps N1–N3 + owner's checkpoint answers. Use these exact sections (target ≤5,000 tokens, hard cap 8,000):

```markdown
# Vision Summary: [Product Name]

## Product Vision
[3-5 sentences. What is this product? What problem does it solve? For whom?
Derived from research — not invented.]

## Personas
- **[Name]** — [who they are, what they need]
- **[Name]** — [who they are, what they need]

## Value Streams
[How this product generates value — revenue, cost savings, productivity]
- [Stream 1]
- [Stream 2]

## Full Feature Inventory
[Every feature the vision describes, numbered. This is the COMPLETE scope.
Every feature from the research MUST appear here. Nothing silently dropped.]
1. [Feature name] — [one-line description]
2. [Feature name] — [one-line description]
...

## Backing Services (from VPS)
[Which existing VPS services this vision will use — grounded in AGENTS.md]
- postgres-main:5432 — [what for]
- redis-main:6379 — [what for]
- [etc.]

## External Services
[Third-party dependencies outside the VPS]
- [Service] — [what for, cost tier (free/paid)]

## Technology Decisions
[Every major technology choice RESOLVED — not deferred. These are the
contracts that all epics inherit. 02-epic-decomposition-command reads
these and does NOT re-decide them. Fill ONLY bullets relevant to this
vision — omit N/A bullets entirely rather than writing "Billing: N/A"
across multiple lines.]
- **Auth:** [`fabrik-lib/fastapi-user-auth` Pattern A (user-facing, DEFAULT — the app issues its own JWTs) + Authelia (admin) / Authelia only / custom — state which and why. Supabase Auth is legacy/migration-only per `AGENTS.md § Supabase`; pick it only for a project already on it.]
- **Database:** [postgres-main (DEFAULT) / Supabase (legacy — plan migration to postgres-main) — state which holds what]
- **Search:** [MeiliSearch / pgvector / none — state what's being searched]
- **Billing:** [Paddle (international MoR) / iyzico (Turkish domestic) / RevenueCat + IAP (mobile digital goods — Paddle does NOT apply in-app) / none — state pricing model. Stripe is NOT available to a TR entity.]
- **File storage:** [`fabrik-lib/storage` (Backblaze B2 backend, DEFAULT) / none — state what's stored. Supabase Storage is legacy/migration-only.]
- **Notifications (internal/ops):** [Apprise (already deployed) / direct API / none]
- **Email (transactional):** [Resend (default, 3k/mo free) / escalate to Postmark for critical auth mail — state what triggers emails]
- **Email (marketing):** [Resend Broadcasts (start) / Listmonk + SES (at scale) / none — MUST be separate stream from transactional. See `core/86-email-templates.md`.]
- **RAG pipeline:** [none / search-only (embeddings + retriever) / search + classification / full intelligence (+ generator + summarizer) — state what corpus is being searched and what users need from it. See `domain-modules/rag.md` for component guide.]
- **Background processing:** [file-worker needed? State what runs async: transcription, PDF gen, AI inference, batch imports, scheduled jobs / none]
- **Consumed microservices:** [site-provisioner for DNS / none — image-broker is retired/not deployed]
- **Watchdog sidecar + cost-budget:** [enabled (state per-project `daily_budget_usd` + `daily_invocations_cap` per `cost-budget.md`) / not needed (no paid AI APIs / no cost-sensitive ops) — ⚠️ `cost-budget.md:28` makes the **cost CAP** mandatory for any project that runs the watchdog (or calls paid AI APIs); it does **not** mandate the watchdog itself — and on the `fabrik apply` path the sidecar is **on by default** regardless, so the live question is the cap, not the sidecar. Without a cap a feedback loop (the sidecar diagnosing the sidecar) could empty the budget overnight]
- **Domain structure:** [subdomains needed, e.g., api.X, app.X, admin.X]
- **Scaffold types:** [list all scaffold types this vision needs — each may become an epic. Valid: python-api, python-api-gpu, node-api, saas-skeleton, file-api, file-worker, docusaurus, chrome-extension, mobile-app, desktop-app, static-site. **wordpress is NOT valid here** — route any WordPress site requirement to the standalone `/opt/wpf` project.]
- **Target host (per service, YAML field `target_vps:`):** [`vps1` (hub, default — shared infra here) / `vps2` or `vps3` (spoke — public Traefik only, reaches hub infra via `10.99.0.1:<port>`) — state per service. Hub = anything needing low-latency to postgres/redis/glitchtip/authelia; spoke = tenant-isolated, EU-proximate, or capacity-spillover.]
- **Documentation site:** [SaaS scaffolds: vendor `/opt/fabrik-lib/docs-site/` (Docusaurus + Scalar + legal pages). Non-SaaS: N/A]

## Constraints
[Hard constraints from research + constraint verification (N3i).
Each states the constraint and its status: all clear / conflict / unknown.]
- x86_64: all clear
- Budget: [status]
- [etc.]

## Out of Scope (Vision Level)
[What is explicitly NOT being built — even if adjacent.
"Everything else" is not acceptable. Name specific exclusions.]
- [Exclusion 1]
- [Exclusion 2]

## Open Questions
[Unresolved items from Step N3 that need owner input before proceeding.
Research conflicts between multiple files go here too.
If no open questions: state "None — research was comprehensive."]
- [Question 1]
- [Question 2]

## Scale Assessment
- Feature count: [N] ([X] small, [Y] medium, [Z] large)
- Classification: [single-epic / multi-epic (~N epics)]
- Reasoning: [why this classification — based on feature count and complexity, NOT which features become which epics]
- Next step:
  - If single-epic: "Proceed to epic-to-ticket-workflow/00-trigger-workflow-command. Confirm?"
  - If multi-epic: "Proceed to 02-epic-decomposition-command to define epic boundaries."
```

### Step N5: Present and Iterate

Present the COMPLETE Vision Summary — the only user-facing output of NEW mode. Iterate until the owner explicitly confirms:

- Owner answers Open Questions → incorporate, remove from Open Questions, re-validate affected sections.
- Owner adds/removes features → update Feature Inventory, re-assess scale.
- Owner changes scope → re-run constraint verification on affected items.
- All Open Questions resolved + owner confirms → command complete.

**CRITICAL: STOP GENERATION after presenting.** Do NOT simulate the owner's response. Do NOT self-confirm. Silence ≠ confirmation.

**Routing after confirmation:** single-epic → "Proceed to `epic-to-ticket-workflow/00-trigger-workflow-command`." Multi-epic → "Proceed to `02-epic-decomposition-command` to define epic boundaries."

---

## EXISTING MODE — Continuation (snapshot + compliance + delta)

### Step E1: Read Existing Project State

Read the project's actual state — not from memory, from files. Owner must have provided the project folder path.

- `project.yaml` → scaffold type, ports, shape flags. **If missing:** project predates the scaffold system — flag as "pre-scaffold project" in the snapshot. New features MUST go through `fabrik scaffold` patterns even if the original project didn't.
- `specs/services/*.yaml` → deployed services, shape blocks, registrars, **`target_vps`** (defaults to `vps1` if absent). **If missing:** project was not deployed via `fabrik apply` — flag as "manually deployed". New services MUST use `fabrik apply`.
- `templates/<scaffold-type>/` (in Fabrik repo) → the canonical scaffold tree this project was generated from. Compare against actual layout to detect drift from scaffold defaults.
- `compose.yaml` / `Dockerfile` → infrastructure, base images, services.
- `.env.example` → environment variables, external service dependencies.
- `src/` or `app/` → codebase structure, existing modules, API routes.
- Database schema → existing tables (from migrations or models).
- `docs/` → existing architecture docs, preplans, FINANCIALS.md.
- `.windsurf/rules/` → rule packs synced from `/opt/fabrik/.windsurf/rules/`. **Local edits to any Fabrik-synced file are a Tier-1 violation** — gate-enforced by `scripts/enforcement/check_synced_unmodified.py` (since commit `4ab2eb3`). The full synced set (AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules, `.windsurf/rules/`, scripts/enforcement/, etc.) is defined by `scripts/fabrik_synced_manifest.py`. Run the gate check from project root; any drift is a Compliance gap that must be fixed by reverting the local edit + proposing the change upstream in `/opt/fabrik` (only if the change applies to ALL projects).

**Lifecycle check (4 stages — completeness audit; gaps feed Step E3):**

- **Stage 1 (Scaffolding):** `project.yaml` exists? **Full Fabrik-synced set** (canonical list in `scripts/fabrik_synced_manifest.py`; covers the 5 governance files — AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules, `opencode.json` — plus `.windsurf/rules/`, `scripts/enforcement/`, etc.) present AND byte-identical to `/opt/fabrik` source? Run `python scripts/enforcement/check_synced_unmodified.py` to verify both presence and unmodified state in one shot — same gate referenced above. A missing file and a locally-edited file are different gaps: missing → propose `fabrik fix /opt/<project> --type <scaffold-type>`; modified → revert + propose upstream change in `/opt/fabrik`.
- **Stage 2 (Implementation):** structured code (src/, tests/, docs/)?
- **Stage 3 (Registration):** `fabrik apply` run? `.fabrik/state/*.json` exists? Registrars active (Gatus, GlitchTip, Prometheus)?
- **Stage 4 (Verification):** `fabrik verify` passes? `fabrik audit-registrars` clean?

**Pre-flight checks** — run all 7 checks per `AGENTS.md` § MANDATORY ORCHESTRATOR PRE-FLIGHT (same as Step N1): Ports, Business Model, Microservices, Hardware Audit, Design System, External Knowledge, fabrik-lib.

**Scope note for pre-scaffold projects:** if the project predates `fabrik scaffold` (no `project.yaml`), several pre-flight checks are *retrospective only* — they document the current state rather than gate a new decision. Specifically: Hardware Audit and Design System checks describe what the project already runs/looks like (no "decide" step); Ports, Business Model, Microservices, External Knowledge, and fabrik-lib still apply forward (the delta being scoped in E4 must satisfy them). State pre-flight findings in the format "Retrospective: \[X\]" vs "Forward: \[Y\]" so E3 gaps are unambiguous.

State: "Project read. Scaffold: [X / pre-scaffold]. Port: [Y]. [N] API routes, [M] DB tables, [K] workers. Lifecycle: [all 4 / gaps at Stage N]. Pre-flight: [findings]."

### Step E2: Produce Project Snapshot

Present the snapshot — what EXISTS right now:

```markdown
## Project Snapshot: [Project Name]

### Deployed State
- Scaffold type: [X]
- Port: [Y]
- Shape: [registrar flags]
- Status: [deployed on VPS via fabrik apply / local dev only / partially deployed]

### Locked Technology Decisions (cannot change)
- **Auth:** [what's implemented — Pattern A / Pattern B / custom]
- **Database:** [postgres-main / Supabase (legacy — plan migration to postgres-main) / both — what tables exist]
- **Frontend:** [Next.js 15 + React 19 + Tailwind (current saas-skeleton default — bumped 2026-06-18) / Jinja + Bootstrap / etc.]
- **Target host:** [`vps1` (hub) / `vps2` / `vps3` — read from `specs/services/<id>.yaml::target_vps`; missing = `vps1`]
- **Billing:** [Paddle / iyzico / RevenueCat / none — if wired, it's locked]
- **Background processing:** [Celery / PG job queue / none]
- **Search:** [MeiliSearch / pgvector / none]
- **Other locked choices:** [any framework, library, or pattern that has production data or live users]

### Existing Features (working — do not re-plan)
1. [Feature] — [status: shipped / partially built / scaffolded]
2. [Feature] — [status]
...

### Existing Infrastructure
- [VPS services used: postgres-main, redis-main, etc.]
- [External services: Cloudflare, Backblaze B2, Paddle, Supabase (legacy — only if the project still runs on it), etc.]
- [Monitoring: Gatus endpoint, GlitchTip project, Prometheus scrape]
```

#### ── CHECKPOINT E-1: "Is this snapshot accurate? Anything missing or wrong?" ──

Wait for owner confirmation. Do NOT proceed without it. **STOP GENERATION HERE.**

### Step E3: Compliance Detection

Compare the existing project against current Fabrik scaffold standards AND current rule packs. This step has three sub-steps; produce a single combined Compliance Report at the end.

**Step E3.A — Mechanical detection (run commands, parse output):**

Run these in the project's directory:

1. `fabrik validate <project_path> --type <scaffold_type>` — scaffold-standard compliance:
   - Required files present (project.yaml, AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules, README, spec, .env.example, etc.)?
   - Required directory structure?
   - Outdated governance files (older than current scaffold template)?
   - Spec schema valid?
2. `fabrik audit-registrars --spec specs/services/<id>.yaml` — shape/registrar drift:
   - For each declared registrar: `present` / `missing` / `drift` / `n/a` / `override` / `unknown`.
   - Drift cases: orphan resources (created outside fabrik), ghost entries (spec says yes, live says no, vice versa).
   - **Use `audit-registrars`, NOT `reconcile-all`.** Per AGENTS.md, `fabrik reconcile-all` is **currently broken** (still wired to the decommissioned Coolify — `CoolifyClient` is queried at runtime, so it fails when the command is invoked; pending Phase 11-2 migration). `audit-registrars` is the read-only audit path and works; `reconcile-all` is the auto-fix path and is unavailable today. Do not plan tickets that invoke reconcile-all.
3. Inspect: does `.fabrik/state/<id>.json` exist? Does `docs/RESILIENCE.md` exist for projects with external deps?

Report findings as a list of mechanical gaps with concrete locations.

**Step E3.B — Rule-pack judgment (Traycer evaluates code/structure):**

For each rule pack applicable to this scaffold type (per `AGENTS.md` § Project Type → Default Packs table; the Rule Pack Index above in the Input Contract section — ⚠️ that index is NOT exhaustive (it omits `core/62-using-subagents.md` and all 11 `ai/` packs); for the authoritative live set run `python scripts/select_rules.py`), evaluate the project against the pack's mandates. Example table below is for `saas-skeleton`; for other scaffold types build the equivalent table:

- **Scaffold has a `domain-modules/<type>.md`** (chrome-ext, desktop-app, mobile-app, saas — plus the capability module `rag`, which is NOT a scaffold type) → use that as the structural starting point + add applicable rows from the Rule Pack Index.
- **Scaffold has NO `domain-modules/<type>.md`** (python-api, **python-api-gpu**, node-api, file-api, file-worker, static-site, docusaurus) → build the table directly from the Rule Pack Index, scoped to the scaffold's Default Packs in `AGENTS.md` § Project Type → Default Packs. Use the applicability matrix below to decide which rows survive.
- **WordPress projects are out of scope here** — delegate to `/opt/wpf`; do NOT build a Compliance table for WordPress sites under this workflow.

**Rule-area applicability matrix** (use to scope rows in/out of the Compliance table for a given scaffold):

| Rule area | Applies to (kind) |
| --- | --- |
| 12-Factor App, Resilience, Health endpoint, Structured logging, Shape contract, Observability, Compose invariants, Authelia bypass scope, Fabrik-synced files unmodified, Bootstrap scripts | every `service` + `worker` scaffold; `static` skips Health/Observability/Resilience (no app process) |
| asyncpg, UUIDv7 | every Python `service` + `worker` that touches Postgres |
| Python version floor | every Python scaffold |
| Node ESM mandate | every Node scaffold |
| LLM gateway (OpenRouter default + required for embeddings; Kilo CLI is a peer; direct-API gateways CONTESTED — flag) | any scaffold that calls an LLM — N/A otherwise |
| Vector DB ban | any scaffold doing vector search — N/A otherwise |
| Cost budget, Watchdog sidecar | any scaffold calling paid AI APIs — N/A otherwise |
| Target host (multi-host) | every Fabrik-deployed scaffold (`service`/`worker`); `static` N/A unless deployed via spec |
| i18n, Responsive design, Dark+light mode | **Any scaffold exposing a user/admin GUI surface** — saas-skeleton, docusaurus front, chrome-extension popup, mobile-app, desktop-app, AND python-api/node-api/file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` with HTML output. Trigger on the *GUI surface*, not the scaffold type — a python-api admin dashboard needs dark+light + responsive + i18n exactly like a saas-skeleton does. N/A only when the scaffold has no HTML/native UI at all (pure JSON API, file-worker queue consumer, static-site with no localization needs). |
| Audit log | scaffolds storing tenant-scoped sensitive data (saas-skeleton, file-api when KVKK-bound) — N/A otherwise |
| Self-healing strategy | services critical to fleet uptime (per `core/self-healing.md`) — N/A for one-off internal tools |
| Abuse detection, Email two-stream, FINANCIALS.md | SaaS-only (saas-skeleton) — N/A everywhere else |
| Billing routing | scaffolds taking payment — N/A otherwise |
| file_erasure_audit hash-chain | file-api scaffold only — N/A everywhere else |

| Rule area | Current rule | How to evaluate the project | Status |
|---|---|---|---|
| 12-Factor App | Config via env, stateless, structured logs | Check for hardcoded config, session storage, print() vs structlog | Compliant / Partial / Violates |
| i18n | en + tr minimum, `validate_i18n.py` 3-level | Inspect locale files; run validator if present | Compliant / Missing / Partial |
| Responsive design | 375px floor, RWD1–RWD10 | Inspect components, viewport meta, breakpoints | Compliant / Missing / Partial |
| Dark + light mode | Both mandatory, OS detection + toggle + persistence | Inspect theme provider, root toggle | Compliant / Missing |
| Resilience | Timeout + retry + circuit-breaker + graceful fallback | Inspect external-call sites; check `docs/RESILIENCE.md` | Compliant / Missing / Partial |
| Abuse detection (SaaS w/ free tier) | IP rate limit, disposable email block, progressive unlock | Inspect signup endpoint, middleware | Compliant / Missing / N/A |
| Email templates | MJML + Jinja2, two-stream (transactional/marketing) | Inspect email module + ESP config | Compliant / Missing / N/A |
| FINANCIALS.md (SaaS) | Populated before launch | File exists? Has content? | Present / Missing |
| Health endpoint | Tests real deps (`SELECT 1`, `PING`) | Inspect `/health` handler | Compliant / Missing / Partial |
| Structured logging | structlog, no `print()` | grep `print(` in src/ | Compliant / Partial |
| asyncpg | No psycopg2 | grep imports | Compliant / Deviates |
| UUIDv7 | `uuid_utils.compat.uuid7` | grep `uuid.uuid4` | Compliant / Deviates |
| Vector DB | pgvector on postgres-main only — no Pinecone/Qdrant/Weaviate/Milvus | Inspect deps | Compliant / Deviates / N/A |
| Shape contract | Code matches `spec.shape` | Cross-check audit-registrars output | Compliant / Drift |
| Observability | `/health` for Gatus + `/metrics` for Prometheus | Inspect endpoints | Compliant / Partial |
| Target host (multi-host) | `spec.target_vps` declared (or absent → `vps1` by default); spoke services use mesh IPs for hub infra | Read spec; grep for hardcoded `vps1.ocoron.com` URLs in spoke services | Compliant / Drift / N/A |
| Watchdog / sidecar self-heal | Critical services have a watchdog sidecar (per `core/60-watchdog.md`) | Inspect compose for watchdog sidecar pattern | Compliant / Missing / N/A |
| Self-healing strategy | Drift → diagnose → action loops; Tier A/B/C decision matrix (per `core/self-healing.md`) | Inspect: does the project surface Tier A actions to AI Sysadmin? | Compliant / Missing / N/A |
| Audit log | Tenant-scoped, immutable rows for sensitive ops (per `core/app-audit-log.md`) | Inspect schema for audit table; grep for audit writes on mutations | Compliant / Missing / N/A |
| Cost budget | Per-feature LLM + infra cost capped; OpenRouter gateway only (per `core/cost-budget.md`) | Inspect for direct vendor SDKs, uncapped loops | Compliant / Deviates / N/A |
| Bootstrap scripts | Project deploy path covered by `bootstrap-vps.sh` / restore scripts (per `core/90-bootstrap-scripts.md`) | Inspect `scripts/` + DR docs | Compliant / Missing / N/A |
| Compose invariants | Every service has `container_name:`, `deploy.resources.limits.memory`, `platform: linux/amd64`, no `ports:`, joins `fabrik` network (NOT `coolify`) — enforced by `deployer_ssh._validate_compose()` — ⚠️ **only on the template + docker-image paths** (`deployer_ssh.py:373,481`); **`_deploy_git` never calls it** (`:404`), and *network membership* is never checked at all (only a stray legacy `coolify` key is rejected). A **git-sourced** project — the standard Fabrik deploy path — must self-enforce these in its own gate. Per `30-ops.md` | Read `compose.yaml`; grep each invariant | Compliant / Violates |
| Authelia bypass scope | `/health`, `/healthz`, `/metrics`, `/api/health` bypassed **resource-based, not domain-bound** (hub + spokes via `authelia-vps1@file`); never protected | grep code for `/health` auth middleware; check Traefik labels for protections | Compliant / Drift |
| Billing routing | iyzico for TR SaaS / Paddle for international / RevenueCat for mobile IAP; Stripe NOT wired; PayTR only if WooCommerce (per `85-payments-billing.md`) | grep imports for `@stripe/stripe-node`, `stripe`, `iyzipay`, `@paddle/paddle-node`, `@paddle/paddle-js` | Compliant / Deviates / N/A |
| LLM gateway | **OpenRouter** default + **required for embeddings**; **Kilo CLI** a peer gateway (3–5s subprocess overhead, incl. low-volume app components per `65-rag-search.md:95-97`); no general-purpose vendor SDKs (`openai`, `@anthropic-ai/sdk`); ⚠️ direct-API gateways (DashScope/SiliconFlow) **CONTESTED** — `ai/00:62,135` permits, `65-rag-search.md:108` bans → flag for a ruling | grep deps + imports | Compliant / Deviates / N/A |
| Node ESM mandate | Greenfield Node: `"type": "module"` in `package.json`; `engines.node: ">=22.0.0"` (24 LTS preferred); `npm ci --ignore-scripts` in Dockerfile (per `12-node.md`) | Inspect `package.json` + `Dockerfile` | Compliant / Deviates / N/A |
| Python version floor | `python:<current-stable>-slim-bookworm` (3.13 at time of writing); `uv` package manager — no raw `pip` (per `10-python.md` + `30-ops.md`) | Inspect `Dockerfile` + `pyproject.toml` | Compliant / Deviates / N/A |
| file_erasure_audit hash-chain (file-api scaffold) | Tamper-evident sibling audit table with `prev_hash` + `current_hash` columns via `BEFORE INSERT` trigger; `verify_chain()` adapted from `/opt/fabrik-lib/app-audit-log/`; quarterly verification scheduled (per `67-file-api.md` § KVKK + Article 7(3)) | Inspect schema for `file_erasure_audit` + trigger + verify scheduler | Compliant / Missing / N/A |
| Fabrik-synced files unmodified | The set in `scripts/fabrik_synced_manifest.py` (AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules, `.windsurf/rules/`, etc.) must be byte-identical to `/opt/fabrik` source — never edited locally; gate-enforced by `scripts/enforcement/check_synced_unmodified.py` | Run `python scripts/enforcement/check_synced_unmodified.py` from project root | Compliant / Drift |

Adapt the table to the scaffold type — pull the relevant packs from `AGENTS.md` § Project Type → Default Packs. For non-applicable rule areas, mark `N/A` (e.g., abuse detection for an internal API).

**Step E3.C — Owner decides per gap:**

Present every gap from E3.A and E3.B in a single combined list. For each, ask the owner to classify:

- **Fix-now** — becomes an input to `02-epic-decomposition-command`, which emits a **Retrofit epic** for it (alongside the delta-feature epics). Use when: critical for the new capability, or launch readiness, or already costing time.
- **Fix-later** — noted in the Compliance Report but deferred. No epic generated now. Use when: known issue, owner is aware, accepting the debt for now.
- **Accept-as-legacy** — noted in the Compliance Report; no action taken. Use when: changing would break existing functionality or require a migration the owner does not want to do.

#### ── CHECKPOINT E-2: "Here are the compliance gaps. Which do you want to fix-now, fix-later, or accept-as-legacy?" ──

Wait for owner decisions. **STOP GENERATION HERE.** These decisions shape which Retrofit epics get emitted in 02.

### Step E4: Scope the Continuation

**Research path:** read files from `docs/development/plans/` or `docs/preplans/`; challenge against Fabrik reality using N3c's six checks.

**Idea path:** interview the owner — What capability are you adding? Who uses it (existing/new persona)? How does it integrate with what's built? New tables/endpoints/workers needed? New scaffold type (e.g., adding mobile-app to existing SaaS)?

**Load domain modules** — for each NEW capability, read the matching `domain-modules/` file: search/RAG → `rag.md`; mobile app → `mobile-app.md`; billing → `saas.md` (billing section); chrome extension → `chrome-ext.md`; desktop app → `desktop-app.md`. (WordPress site/theme work is delegated to `/opt/wpf` — do NOT load `domain-modules/wordpress.md` for new visions in this workflow.)

**fabrik-lib check** — before designing any new component, check `fabrik-lib/README.md` for a vendorable module (copy, don't import). State: "fabrik-lib checked — [module used / no match]."

**Force new tech decisions per current ruleset — for NEW components only** (do NOT re-decide locked choices): new search → pgvector + hybrid per `core/65-rag-search.md`; new billing → Paddle per `core/85-payments-billing.md`; new mobile → RevenueCat + IAP per `mobile-app/81-mobile-billing.md`.

**Identify integration points:** existing tables read/written, existing API endpoints extended/depended on, shared auth, existing vs new background workers.

**Constraint verification for the delta** (same 20 checks as N3i, scoped to what the delta adds; inherited services not re-checked). Scoping rules — re-run a constraint only when the delta touches its trigger:

- **Always re-check** (these surface in every delta): #1 x86_64, #6 deployable via `fabrik apply`, #9 solo-dev capacity.
- **Re-check when delta adds a NEW Fabrik-deployed service** (new container/spec): #5 port conflicts, #7 no Alpine, #10 observability, #13 compose invariants, #17 target_vps. (If the delta only modifies existing service code without adding a new container, skip these — the existing spec's `target_vps` is inherited; no new port allocation needed.)
- **Re-check when delta adds a paid external dependency**: #2 budget.
- **Re-check when the trigger applies to the delta**: #11 vector DB (delta adds vector search), #12 email streams (delta sends email), #14 billing (delta wires payment), #15 LLM gateway (delta calls an LLM), #16 i18n (delta adds user-facing surface), #18 KVKK (delta stores PII or file blobs), #19 watchdog (delta calls paid LLM at non-trivial volume), #20 Node/Python floors (delta touches dependency files).
- **Skip when inherited** (locked decisions): #3 existing services, #4 duplicate check, #8 12-Factor (inherited from project's existing stack — only re-check if the delta introduces a new process model).

### Step E5: Produce Vision Summary (EXISTING mode — with extra sections)

Same shape and title as NEW-mode Vision Summary (so `02-epic-decomposition-command` consumes both identically) + two extra sections (`Locked Decisions`, `Compliance Report`). Artifact title is `Vision Summary` — not "Continuation Summary".

```markdown
# Vision Summary: [Project Name] — [New Capability]
<!-- This is an Existing-mode Continuation produced by 00-trigger-workflow-command.
     02-epic-decomposition-command consumes it identically to a new-project
     Vision Summary. Extra sections: Locked Decisions, Compliance Report. -->

## Product Vision
[What this project IS (1-2 sentences from snapshot) + what we're ADDING (2-3 sentences).]

## Personas
[Existing personas that interact with the new feature + any NEW personas]

## Value Streams
[How the new capability generates value — revenue, cost savings, productivity]

## Full Feature Inventory
[ONLY the NEW features being added. Do NOT list existing features.
Numbered. Each with complexity classification (small/medium/large).]
1. [New feature] — [description] (small/medium/large)
2. [New feature] — [description]
...

[Fix-now retrofits (from Compliance Report):]
R1. [Retrofit: add i18n] — [description] (medium)
R2. [Retrofit: add responsive design] — [description] (medium)

## Backing Services (from VPS)
[Which existing VPS services the NEW features will use]

## External Services
[Any NEW third-party dependencies]

## Technology Decisions
[ONLY decisions for NEW components. State explicitly:]

**Inherited (locked — do NOT re-decide):**
- Auth: [inherited from snapshot]
- Database: [inherited from snapshot]
- Frontend: [inherited from snapshot]
- Billing: [inherited from snapshot, if exists]

**New decisions (per current ruleset):**
- [New component]: [decision per rule pack]
- [New component]: [decision per rule pack]
- RAG pipeline: [none / search-only / search + classification / full intelligence]
- Email (transactional): [Resend / already configured / none]
- Email (marketing): [Resend Broadcasts → Listmonk+SES / none]
- Background processing: [file-worker needed? what runs async]
- Scaffold types: [any NEW scaffold types — e.g., adding mobile-app alongside existing saas-skeleton]
- Watchdog sidecar + cost-budget: [enable for new paid-AI-API callers? Per-project `daily_budget_usd` + `daily_invocations_cap` per `cost-budget.md`]
- Target host (per new service, YAML `target_vps:`): [`vps1` (hub, default) / `vps2` / `vps3` (spoke)]
- Deploy target: VPS via fabrik apply / SSH + Docker Compose (confirmed — same as existing services)
- Domain structure: [any NEW subdomains needed for the new capability]

## Locked Decisions (Existing-mode extra section)
[Explicit list of what CANNOT change and why. 02-epic-decomposition-command
MUST inherit these. New services get their own shape blocks; existing ones
are not modified.]
- Auth: [X] — locked because [users exist / tokens issued / migration too risky]
- Database: [X] — locked because [data exists]
- Frontend: [X] — locked because [deployed, users using it]
- Shape block (current): [existing registrars — what `fabrik apply` already activates]
- [etc.]

## Compliance Report (Existing-mode extra section)
[From Step E3, after owner decisions. 02-epic-decomposition-command emits
one Retrofit epic per Fix-now item, alongside the delta-feature epics.]

| Gap | Source | Owner decision | Epic action |
|---|---|---|---|
| i18n missing | Rule pack `core/i18n` | Fix-now | Retrofit epic |
| No responsive design | Rule pack `saas/60-saas-ui.md` | Fix-later | Deferred (no epic now) |
| No abuse detection | Rule pack `saas/87-abuse-detection.md` | Fix-now | Retrofit epic |
| psycopg2 used | Rule pack `core/25-data-postgres.md` | Accept-as-legacy | No action |
| Shape drift: prometheus | `fabrik audit-registrars` | Fix-now | Retrofit epic |

## Constraints
[Same format as NEW-mode Vision Summary — 20 constraint checks, scoped to the delta]
- x86_64: all clear
- Budget: [status]
- [etc.]

## Out of Scope
[What we are NOT changing in the existing codebase — be specific]
- Existing [X] feature — not being modified
- Existing [Y] architecture — not being refactored
- [etc.]

## Open Questions
[Unresolved items]

## Scale Assessment
- New feature count: [N] ([X] small, [Y] medium, [Z] large)
- Retrofit count: [N] (from Compliance Report fix-now items)
- Classification: [single-epic / multi-epic (~N epics)]
- Reasoning: [why this classification — based on feature + retrofit complexity, NOT which become which epics]
- Next step:
  - If single-epic: "Proceed to `epic-to-ticket-workflow/00-trigger-workflow-command`."
  - If multi-epic: "Proceed to `02-epic-decomposition-command` to define epic boundaries."
```

#### ── CHECKPOINT E-3: "Vision Summary complete (with Locked Decisions + Compliance Report sections). Confirm before proceeding to epic decomposition." ──

Wait for explicit confirmation. **STOP GENERATION HERE.** Silence ≠ confirmation.

**Routing after confirmation:**
- Single-epic → "This fits a single epic. Proceed to `epic-to-ticket-workflow/00-trigger-workflow-command`."
- Multi-epic → "Proceed to `02-epic-decomposition-command` to define epic boundaries."

---

## Output Contract & Acceptance Criteria

**Format.** Vision Summary (markdown, exact structure from Step N4 / E5 skeleton) presented in Traycer conversation. No files written. Lives in Traycer conversation context titled "Vision Summary." Persisted by Traycer's spec store automatically. Consumed by `02-epic-decomposition-command` from conversation context; `03-expand-epic-files-command` creates tickets per epic from the confirmed decomposition.

**Token budget.** NEW: ≤5,000 target / ≤8,000 hard cap. EXISTING: ≤6,000 target / ≤10,000 hard cap (extras add length).

**Required sections** (both modes): Product Vision, Personas, Value Streams, Full Feature Inventory, Backing Services, External Services, Technology Decisions, Constraints, Out of Scope, Open Questions, Scale Assessment. **EXISTING adds:** `Locked Decisions` + `Compliance Report`. The Compliance Report drives Retrofit epics in 02.

**Key routing output.** Scale Assessment determines single-epic (→ `epic-to-ticket-workflow/00-trigger-workflow-command`) vs multi-epic (→ `02-epic-decomposition-command`).

**Acceptance — both modes:**
- Mode declared explicitly at Step 0 — never auto-detected.
- Input consumed per declared mode and path.
- ALL features (or retrofits + new features in EXISTING) present in Feature Inventory — no silent drops.
- Personas named explicitly — not just "users." Value streams stated — not just "it's useful."
- Backing services grounded in actual VPS inventory (`AGENTS.md` § Infrastructure Services). External services identified with cost tier (free/paid).
- Technology Decisions complete — every major NEW choice resolved. No "TBD" allowed.
- All 20 constraints verified: `all clear` / `conflict` / `unknown`. No silent unknowns.
- Scale Assessment present with classification and clear next-step routing.
- Vision Summary within token budget for the declared mode.
- Open Questions captures ALL unresolved items; zero remain at confirmation (all answered or explicitly deferred).
- Owner explicitly confirms. Silence ≠ confirmation.

**Acceptance — NEW adds:**

- Research (if present) improved: gaps, conflicts, opportunities surfaced. Multiple research files: conflicts flagged in Open Questions, not silently resolved.
- Multi-scaffold visions identified (e.g., python-api + saas-skeleton + mobile-app; or chrome-extension + python-api backend). WordPress components routed to `/opt/wpf` and excluded from epic decomposition.
- Single-epic visions routed to `epic-to-ticket-workflow`, not forced through mega-epic-breakdown.
- One analysis checkpoint (N-1) before draft, one confirmation after.

**Acceptance — EXISTING adds:**

- Project state read from actual files — not memory or assumptions.
- Project Snapshot confirmed by owner (Checkpoint E-1).
- Lifecycle gaps (4 stages) detected; pre-flight checks completed.
- Compliance Detection executed in all three sub-steps: E3.A mechanical (`fabrik validate` + `fabrik audit-registrars` run and parsed), E3.B rule-pack judgment, E3.C owner decision per gap (Checkpoint E-2).
- Locked Decisions section produced with explicit reasons (data, users, tokens issued).
- Compliance Report maps each gap to owner decision + epic action.
- New capability scoped as delta — not re-planning existing features.
- Relevant domain modules loaded for the new capability.
- Integration points identified (tables, APIs, auth, workers).

**Does NOT.** Split the vision into epics, decide scaffold types per epic, decide shape blocks per epic, or produce per-epic infrastructure decisions — all of those are `02-epic-decomposition-command`. Create files or tickets — orientation only; tickets in `03-expand-epic-files-command`. Blindly accept research — challenges against Fabrik reality, budget, maintainability. Plan refactoring of existing code — separate workflow. **EXISTING-specific:** does NOT re-derive the vision (reads from project) or re-decide locked tech choices (inherits them); does NOT auto-fix compliance gaps (owner decides per gap; auto-fix happens later as Retrofit epics in 02).

## Examples

The skeletons in Step N4 (NEW) and Step E5 (EXISTING) above are the authoritative output shape — Traycer follows them at runtime. Historical filled-in examples (read-once illustrative anchors, never pasted into Traycer) are archived at `docs/archive/2026-06-18-traycer-mega-epic-vision-summary-examples.md`.
