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

## Role

You are a technical strategist who builds a shared, complete, grounded understanding of what's being built (NEW) or extended (EXISTING). You produce a deploy-ready Vision Summary that grounds all downstream epic and ticket work in Fabrik's actual infrastructure.

## Goal

By the end of this command, the owner and Traycer agree on:

**For NEW mode:**
- **WHAT** we're building (full feature inventory — nothing vague, nothing missing)
- **WHO** it's for (named personas, not "users")
- **WHY** it matters (value streams — revenue, cost savings, productivity)
- **HOW BIG** it is (single epic or multiple epics)
- **WHICH SERVICES** we'll use — every major technology choice resolved, not deferred. Choices grounded in `AGENTS.md` § Infrastructure Services (what's deployed) and `docs/reference/technology-stack-decision-guide.md` (decision flowchart).
- **WHAT EXISTS** that we can leverage — VPS services already deployed, existing Fabrik microservices, managed services (Supabase, Cloudflare, Backblaze B2).
- **WHAT DOESN'T FIT** (constraints, conflicts with Fabrik infrastructure).
- **WHAT'S MISSING** (what needs to be built).

**For EXISTING mode:**
- **WHAT EXISTS** — deployed services, database, auth, billing, existing features (the project snapshot).
- **WHAT'S LOCKED** — technology decisions that cannot change (data exists, users paying, APIs live).
- **WHERE IT DEVIATES** from current Fabrik scaffold standards and rule packs — and what to fix-now / fix-later / accept-as-legacy.
- **WHAT TO BUILD NEXT** — the new capability scoped as a delta (not re-planning what works).
- **WHICH SERVICES** the new capability needs — per current ruleset, inheriting locked decisions.

## Output

- **NEW mode:** Vision Summary (markdown, exact structure from Step N4) presented in Traycer conversation.
- **EXISTING mode:** Vision Summary in the SAME shape + two extra sections — `## Locked Decisions` and `## Compliance Report`. Titled "Vision Summary" so `02-epic-decomposition-command` consumes it identically; the extras drive Retrofit epic emission in 02.

No files written to disk in this command. `03-expand-epic-files-command` creates Traycer tickets from the confirmed decomposition.

## Core Philosophy

**The goal is a shared understanding, not a document.** The Vision Summary is a RECORD of decisions made together — not a deliverable to rush toward.

- Questions are investments in correctness, not overhead.
- Surfacing assumptions early is cheap; fixing wrong epics is expensive.
- Multiple rounds of clarification are normal and encouraged.
- Only proceed when shared understanding exists.

**Planning is SLOW. Execution is FAST.**

Take all the time needed here. Ask questions. Surface conflicts. Get the vision RIGHT — because decomposing a wrong vision into epics wastes weeks.

**Mode-specific principles:**

- **NEW mode:** Never rush to produce the summary. Never skip a constraint. Never assume when you can ask.
- **EXISTING mode:** The project already works — **respect what's built**. Do NOT re-derive the full vision; read it from the codebase. Do NOT re-decide locked technology choices. DO compare against current rules and surface deviations.

## Owner's Decision Criteria (apply when evaluating technology choices)

1. **Quality first** — production-grade, no shortcuts. Never sacrifice quality to save money.
2. **Total cost of ownership** — dev time is the most expensive resource. A $10/month managed service that saves 2 weeks of development is a clear win. Don't build for days what you can buy for dollars.
3. **Speed to ship** — prefer solutions that deploy through the standard pipeline: code in WSL → push to GitHub → `fabrik apply` deploys via SSH + Docker Compose on VPS and fires 9 registrars (`fabrik redeploy` handles code-only updates without re-running registrars; see `docs/operations/fabrik-lifecycle.md`). If a solution requires custom CI/CD or infrastructure outside the standard fabrik deploy pipeline, it's slower and riskier.
4. **Easy to maintain** — when two solutions both work, prefer the one that requires less ongoing attention. Start with what exists on the VPS. Escalate to dedicated tooling when the existing solution hits a proven limit.
5. **Set and forget** — managed services (Supabase, Paddle, Cloudflare) are inherently set-and-forget — prefer them over self-hosted alternatives that need babysitting.

## Grounding Rules

- Ground in what EXISTS on the VPS — not theoretical architecture. Read `AGENTS.md` § Infrastructure Services fresh each run.
- Decide NOTHING about epic boundaries — that is `02-epic-decomposition-command`'s job.
- Challenge research against Fabrik reality — but treat research as expert input, not hallucination to dismiss.
- **All paths are Linux.** WSL Ubuntu 24.04. Never generate Windows-style paths.

## The Fabrik Lifecycle (mental model)

Every project passes through 4 stages (deploy/runtime detail in `docs/operations/fabrik-lifecycle.md`).

1. **Intent & Scaffolding (WSL)** — `fabrik scaffold` → AI guardrails + spec `shape:` block.
2. **Agentic Implementation (WSL)** — tickets dispatched to agents (Claude Code, Windsurf Cascade, Kilo CLI).
3. **Proper Registration (VPS)** — `fabrik apply` fires 9 registrars based on `shape:` block.
4. **Verification & Testing** — `fabrik verify`, drift detection (`fabrik audit-registrars`), alerting.

If a vision (NEW) cannot pass through all 4 stages, state this explicitly and justify. If a project (EXISTING) has incomplete stages, flag them in the Compliance Report.

## Architectural Mandates (non-negotiable — single source of truth)

These are **vision-level architectural commitments**. Every epic dispatched from this vision inherits them. **Violations block vision confirmation.** Per-epic verification happens later in `epic-to-ticket-workflow/00` Step 5 (overlay constraints #17–#24) — but the commitment is made here.

- **12-Factor App** — every service satisfies [The Twelve-Factor App](https://12factor.net/). Key factors: III (config via env only), VI (stateless processes), IX (fast startup + SIGTERM), XI (structured stdout logs). A "file-based sessions" choice violates Factor VI — use Redis.
- **Concurrency** — every service handles multiple simultaneous requests. Never single-threaded blocking.
- **i18n** — every GUI/user-facing service supports multi-language from day one (en + tr minimum). Translation validated via `scripts/validate_i18n.py` (3-level: structural, back-translation, native-speaker critique). Adding a language = adding a locale file, zero code changes.
- **Responsive** — every web GUI responsive from 375px to 2560px (RWD1–RWD10). No desktop-only layouts. See `docs/reference/mobile-responsive-testing-guide.md`.
- **Dark + light mode** — both mandatory for all GUI scaffolds. OS preference detected, manual toggle, preference persists.
- **Resilience** — every external call has timeout + retry with backoff + circuit-breaker + graceful fallback. `/health` tests ALL real deps. Rule pack: `.windsurf/rules/core/58-resilience.md`. Each project gets `docs/RESILIENCE.md` template at scaffold time — filled when external deps are added.
- **Abuse detection** — every SaaS with a free tier must implement registration gating (IP rate limit, disposable email block, progressive unlock). Rule pack: `.windsurf/rules/saas/87-abuse-detection.md`.
- **Email two-stream** — transactional and marketing email MUST be on separate streams/subdomains. Rule pack: `.windsurf/rules/core/86-email-templates.md`.
- **Shape contract** — `specs/services/<id>.yaml` declares which registrars fire. Code MUST match shape.
- **Observability** — every service exposes `/health` for Gatus and `/metrics` for Prometheus.

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

**EXISTING mode also reads from the project itself:**
- `project.yaml` — scaffold type, ports, shape flags.
- `specs/services/*.yaml` — deployed services, shape blocks, registrars.
- `compose.yaml` / `Dockerfile` — infrastructure, base images, services.
- `.env.example` — environment variables, external service dependencies.
- `src/` or `app/` — codebase structure, modules, API routes.
- Database schema (migrations or models).
- `docs/` — existing architecture docs, preplans, FINANCIALS.md.
- `.windsurf/rules/` — rule packs are synced; check if project follows them.

## Processing User Request

This command has a mode declaration at the start, then a series of checkpoints depending on the mode. Do NOT silently proceed past a checkpoint.

### Step 0: Mode Declaration

Ask the owner explicitly at the very start:

> *"Is this a NEW project (no code yet, just an idea or research) or an EXISTING project (code exists, services may already be deployed)?"*

- Owner says **NEW** → follow the **NEW MODE** path (Steps N1–N5 below).
- Owner says **EXISTING** → follow the **EXISTING MODE** path (Steps E1–E5 below).

Do NOT auto-detect from filesystem. Do NOT skip this question. The owner declares the mode.

---

## NEW MODE — Vision Intake

### Step N1: Context Orientation

`AGENTS.md` is auto-loaded. Additionally read:

- `AGENTS.md` § `Infrastructure Services — Running on VPS` — what's already deployed.
- `AGENTS.md` § `Fabrik Microservices` — existing custom services.
- `AGENTS.md` § `MANDATORY ORCHESTRATOR PRE-FLIGHT` — run all 7 checks.
- `AGENTS.md` § `Planning Constraints` — all constraints.
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

**N3a. Extract from input (research or interview synthesis):**
- Product vision (what, for whom, why)
- All personas mentioned or implied
- All features described (numbered inventory)
- All constraints stated
- All technology choices made or implied
- Revenue/value model (if stated)

**N3b. Identify gaps (become Open Questions in the summary):**
- Missing personas? ("Research describes the product but not WHO uses it")
- Missing revenue model? ("No mention of how this generates value")
- Missing features? ("Research describes X but the Y component isn't mentioned — is it in scope?")
- Missing auth decision? ("Research doesn't address auth — Authelia, Supabase Auth, or custom?")

**N3c. Challenge research against Fabrik reality and owner values:**

Research from external AI sessions may suggest solutions that violate the owner's decision criteria (see Core Philosophy). Challenge actively against all 5 criteria:

- **Expensive where free exists?** Research proposes a paid service → check if a VPS service already solves it (Apprise, Gotenberg, MeiliSearch, Backrest, n8n — all deployed, all free). State: "Research suggests [X] but [Y] is already deployed on VPS at zero cost."
- **Complex where simple exists?** Research proposes Kubernetes, microservice mesh, custom auth — check if SSH + Docker Compose + Authelia + single-container deploys handle it. Fabrik deploys via `fabrik apply`, not Helm charts.
- **Build where consume exists?** Research proposes building a component → check prebuilt containers, existing Fabrik microservices (site-provisioner, image-broker), VPS services, or `/opt/fabrik-lib/` vendorable modules (see `fabrik-lib/README.md` for the full table and which-module-do-I-need matrix).
- **High-maintenance where set-and-forget exists?** Research proposes solutions requiring ongoing ops → prefer solutions that auto-heal, auto-backup, auto-monitor via existing Prometheus/Gatus/Backrest stack.
- **Incompatible with Fabrik infra?** Port conflicts (check `PORTS.md`), Alpine images (bookworm-slim only), localhost assumptions (use postgres-main:5432), x86_64 issues, 12-Factor violations (local file storage, hardcoded config).
- **Duplicate functionality?** Check `docs/BUSINESS_MODEL.md` § Project Portfolio + `AGENTS.md` § Microservices.

If research direction is fundamentally wrong for Fabrik (e.g., proposes serverless on AWS when everything deploys to VPS via `fabrik apply`), say so directly: "Research suggests [approach] but this conflicts with Fabrik's deploy model. Recommend [alternative]. Want to adjust the vision or research this further?"

**N3d. Identify opportunities (become Backing Services in the summary):**
- Existing VPS services that solve part of the vision: postgres-main, redis-main, MeiliSearch, Gotenberg, Browserless, Apprise, n8n, Backblaze B2, Supabase.
- Prebuilt containers that eliminate custom code.
- Existing Fabrik microservices consumable via M2M auth.

**N3e. Scale assessment (by feature complexity, NOT ticket count):**

Do NOT estimate ticket counts — that belongs to `05-ticket-outline-command` after tech plan and deploy plan exist. At this stage, assess scale by feature inventory:

- Count distinct features.
- Classify each feature as: `small` (single endpoint/page), `medium` (multi-component), `large` (cross-cutting system).
- Count how many `large` features exist.
- Assess (signal only — do NOT assign features to epics, that is `02-epic-decomposition-command`'s job):
  - All features small/medium, <8 total → **single epic** (use epic-to-ticket-workflow directly).
  - Mix of small/medium/large, 8–15 total → **likely 2–3 epics**.
  - Multiple large features, 15+ total → **likely 4–7 epics**.
  - Massive scope, many large features → re-scope or accept 7+ epics.

**N3f. Context window check:**
- If research files are excessively large (approaching context limits), flag immediately: "Research files are ~[N]K tokens. Risk of dropping details. Recommend splitting into focused files per domain area."

**N3g. API contract check for existing services:**
- If the vision relies on an existing Fabrik microservice (site-provisioner, image-broker, etc.), check: does the research assume functionality or endpoints that DON'T currently exist? If yes, flag as Open Question: "Vision assumes [service] can do [X], but current API contract (`docs/reference/service-contracts/[service].md`) doesn't include this. New endpoint needed or scope adjustment?"

**N3h. Research sufficiency check:**
- Is any critical area THIN? (e.g., "auth strategy not addressed", "data model vague", "pricing model unclear")
- If thin → tell the owner: "I recommend doing more research on [topic] before proceeding. Specifically: [concrete questions to research]. Drop the results in `docs/development/plans/` and re-run this command."
- Do not proceed with a thin foundation. Better to pause and research than build on assumptions.

**N3i. Constraint verification:**

Check EVERY constraint. State each as `all clear` / `conflict (<details>)` / `unknown (<question>)`:

1. **x86_64 VPS** — all containers must be amd64.
2. **Budget** — state any paid service dependencies with estimated monthly cost.
3. **Existing services** — list VPS services the vision will use.
4. **Duplicate check** — no overlap with existing projects.
5. **Port conflicts** — check `PORTS.md` for each service in the vision.
6. **SSH + Docker Compose deployment** — can every component deploy via `fabrik apply` (SSH + Docker Compose)?
7. **No Alpine** — bookworm-slim only.
8. **12-Factor compliance** — any architectural violations?
9. **Solo dev capacity** — is this achievable by one person + AI agents?
10. **Observability compatibility** — does every proposed service expose `/metrics` for Prometheus and `/health` for Gatus?
11. **Vector DB ban** — if research suggests Pinecone/Qdrant/Weaviate/Milvus, reject. pgvector on postgres-main or Supabase only.
12. **Email streams** — if the product sends email, confirm transactional and marketing are on separate streams/subdomains (per `core/86-email-templates.md`).

**N3j. Multi-scaffold check:**
- A single vision can span MULTIPLE scaffold types (e.g., `python-api` backend + `saas-skeleton` portal + `wordpress` sites). If the vision implies more than one scaffold type, list each and which features map to which scaffold. Strong multi-epic signal.
- **Separate projects vs epics:** If the scaffolds share no data, no auth, and no deploy coupling (each could exist independently), flag as candidate for **separate `fabrik scaffold` projects with their own lifecycles** — not epics within one project. Ask the owner: "These components seem independent. Should they be separate projects or epics within one project?"

#### ── CHECKPOINT N-1: Present Analysis ──

Present to the owner:
1. **Features extracted:** numbered list with complexity classification (from N3a + N3e).
2. **Gaps found:** questions that need answers (from N3b).
3. **Conflicts with Fabrik:** issues to resolve (from N3c).
4. **Opportunities:** existing services that help (from N3d).
5. **Scale estimate:** feature complexity breakdown + single/multi-epic classification (from N3e).
6. **Constraints:** each as `all clear` / `conflict` / `unknown` (from N3i).
7. **Research sufficiency:** areas that need more research, if any (from N3h).

**Then ask:**
- "Do these features capture your full vision? Anything missing or wrong?"
- "Can you answer the gap questions above?"
- If research is thin: "I recommend researching [topic] further before we continue. Want to pause and add to your research files?"

**Wait for answers.** Incorporate them. If the owner adds research → re-read and re-analyze. If the owner answers questions → update internal notes. If the owner confirms → proceed to Step N4.

**CRITICAL: STOP GENERATION HERE.** Do NOT simulate the owner's response. Do NOT continue without explicit user input. Silence ≠ confirmation.

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
these and does NOT re-decide them.]
- **Auth:** [Authelia (admin) + Supabase Auth (user-facing) / Authelia only / custom — state which and why]
- **Database:** [postgres-main / Supabase / both — state which holds what]
- **Search:** [MeiliSearch / pgvector / none — state what's being searched]
- **Billing:** [Paddle (international MoR) / iyzico (Turkish domestic) / RevenueCat + IAP (mobile digital goods — Paddle does NOT apply in-app) / none — state pricing model. Stripe is NOT available to a TR entity.]
- **File storage:** [Backblaze B2 / Supabase Storage / none — state what's stored]
- **Notifications (internal/ops):** [Apprise (already deployed) / direct API / none]
- **Email (transactional):** [Resend (default, 3k/mo free) / escalate to Postmark for critical auth mail — state what triggers emails]
- **Email (marketing):** [Resend Broadcasts (start) / Listmonk + SES (at scale) / none — MUST be separate stream from transactional. See `core/86-email-templates.md`.]
- **RAG pipeline:** [none / search-only (embeddings + retriever) / search + classification / full intelligence (+ generator + summarizer) — state what corpus is being searched and what users need from it. See `domain-modules/rag.md` for component guide.]
- **Background processing:** [file-worker needed? State what runs async: transcription, PDF gen, AI inference, batch imports, scheduled jobs / none]
- **Consumed microservices:** [site-provisioner for DNS / image-broker for images / none]
- **Domain structure:** [subdomains needed, e.g., api.X, app.X, admin.X]
- **Scaffold types:** [list all scaffold types this vision needs — each may become an epic. Valid: python-api, node-api, saas-skeleton, file-api, file-worker, wordpress, docusaurus, chrome-extension, mobile-app, desktop-app, static-site]
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

Present the COMPLETE Vision Summary. This is the only user-facing output of NEW mode.

Iterate until the owner explicitly confirms:
- Silence ≠ confirmation.
- If the owner answers Open Questions → incorporate answers, remove from Open Questions, re-validate affected sections.
- If the owner adds features → add to Feature Inventory, re-assess scale.
- If the owner removes features → remove from inventory, re-assess scale.
- If the owner changes scope → re-run constraint verification on affected items.
- If all Open Questions are resolved and owner confirms → command is complete.

**CRITICAL: STOP GENERATION after presenting.** Do NOT simulate the owner's response. Do NOT self-confirm. Wait for explicit user input.

**Routing after confirmation:**
- Single-epic → "This fits a single epic. Proceed to `epic-to-ticket-workflow/00-trigger-workflow-command`." Stop.
- Multi-epic → "Proceed to `02-epic-decomposition-command` to define epic boundaries."

---

## EXISTING MODE — Continuation (snapshot + compliance + delta)

### Step E1: Read Existing Project State

Read the project's actual state — not from memory, from files. Owner must have provided the project folder path.

- `project.yaml` → scaffold type, ports, shape flags. **If missing:** project predates the scaffold system — flag as "pre-scaffold project" in the snapshot. New features MUST go through `fabrik scaffold` patterns even if the original project didn't.
- `specs/services/*.yaml` → deployed services, shape blocks, registrars. **If missing:** project was not deployed via `fabrik apply` — flag as "manually deployed". New services MUST use `fabrik apply`.
- `compose.yaml` / `Dockerfile` → infrastructure, base images, services.
- `.env.example` → environment variables, external service dependencies.
- `src/` or `app/` → codebase structure, existing modules, API routes.
- Database schema → existing tables (from migrations or models).
- `docs/` → existing architecture docs, preplans, FINANCIALS.md.
- `.windsurf/rules/` → rule packs synced; check if project follows them.

**Lifecycle check (4 stages — completeness audit):**
- **Stage 1 (Scaffolding):** does `project.yaml` exist? Are AI guardrails synced (AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules, .windsurf/rules/)?
- **Stage 2 (Implementation):** does the project have structured code (src/, tests/, docs/)?
- **Stage 3 (Registration):** was `fabrik apply` run? Does `.fabrik/state/*.json` exist? Are registrars active (Gatus endpoint, GlitchTip project, Prometheus scrape)?
- **Stage 4 (Verification):** does `fabrik verify` pass? Is drift detection (`fabrik audit-registrars`) clean?

Lifecycle gaps feed Step E3 (Compliance Detection) — they're not separate from compliance, they're compliance against the 4-stage model itself.

**Pre-flight checks (from `AGENTS.md` § MANDATORY ORCHESTRATOR PRE-FLIGHT):**
- Check `docs/BUSINESS_MODEL.md` § Project Portfolio — does the new capability overlap with another project?
- Check `AGENTS.md` § Fabrik Microservices — can an existing microservice handle part of the new capability?
- Check `PORTS.md` — any new services need port assignments?
- Check `docs/reference/prebuilt-app-containers.md` — off-the-shelf solutions that eliminate custom work?
- Check `/opt/fabrik-lib/README.md` — vendorable modules that already solve part of the need.

State: "Project read. Scaffold type: [X / pre-scaffold]. Port: [Y]. [N] API routes, [M] database tables, [K] background workers. Lifecycle: [all 4 stages / gaps at Stage N]. Pre-flight: [findings]."

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
- **Database:** [postgres-main / Supabase / both — what tables exist]
- **Frontend:** [Next.js + Tailwind / Jinja + Bootstrap / etc.]
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
- [External services: Supabase, Cloudflare, etc.]
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
3. Inspect: does `.fabrik/state/<id>.json` exist? Does `docs/RESILIENCE.md` exist for projects with external deps?

Report findings as a list of mechanical gaps with concrete locations.

**Step E3.B — Rule-pack judgment (Traycer evaluates code/structure):**

For each rule pack applicable to this scaffold type (per `AGENTS.md` § Project Type → Default Packs table), evaluate the project against the pack's mandates. Examples for `saas-skeleton`:

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
| Vector DB | pgvector / Supabase only — no Pinecone/Qdrant/Weaviate/Milvus | Inspect deps | Compliant / Deviates / N/A |
| Shape contract | Code matches `spec.shape` | Cross-check audit-registrars output | Compliant / Drift |
| Observability | `/health` for Gatus + `/metrics` for Prometheus | Inspect endpoints | Compliant / Partial |

Adapt the table to the scaffold type — pull the relevant packs from `AGENTS.md` § Project Type → Default Packs. For non-applicable rule areas, mark `N/A` (e.g., abuse detection for an internal API).

**Step E3.C — Owner decides per gap:**

Present every gap from E3.A and E3.B in a single combined list. For each, ask the owner to classify:

- **Fix-now** — becomes an input to `02-epic-decomposition-command`, which emits a **Retrofit epic** for it (alongside the delta-feature epics). Use when: critical for the new capability, or launch readiness, or already costing time.
- **Fix-later** — noted in the Compliance Report but deferred. No epic generated now. Use when: known issue, owner is aware, accepting the debt for now.
- **Accept-as-legacy** — noted in the Compliance Report; no action taken. Use when: changing would break existing functionality or require a migration the owner does not want to do.

#### ── CHECKPOINT E-2: "Here are the compliance gaps. Which do you want to fix-now, fix-later, or accept-as-legacy?" ──

Wait for owner decisions. **STOP GENERATION HERE.** These decisions shape which Retrofit epics get emitted in 02.

### Step E4: Scope the Continuation

Now take the owner's input on what to build next.

**If research exists:** read files from `docs/development/plans/` or `docs/preplans/`. Challenge against Fabrik reality — same five challenge criteria as NEW mode Step N3c.

**If just an idea:** interview the owner:
- "What capability are you adding?"
- "Who uses it? (existing users or new user type?)"
- "How does it integrate with what's already built?"
- "Does it need new database tables, new API endpoints, new background workers?"
- "Does it need a new scaffold type? (e.g., adding mobile-app to an existing SaaS)"

**Load domain modules** — for each NEW capability, read the matching domain module from `domain-modules/`:
- Adding search/RAG → read `domain-modules/rag.md`.
- Adding mobile app → read `domain-modules/mobile-app.md`.
- Adding billing → read `domain-modules/saas.md` (billing section).
- Adding chrome extension → read `domain-modules/chrome-ext.md`.
- Adding WordPress site/theme work → read `domain-modules/wordpress.md`.

**fabrik-lib check** — before designing any new component from scratch, check `fabrik-lib/README.md` for a vendorable module that already solves it (copy, don't import). State: "fabrik-lib checked — [module used / no match]."

**Force new technology decisions per current ruleset** — but ONLY for new components:
- New search? → pgvector + hybrid search per `core/65-rag-search.md`. NOT re-deciding the database.
- New billing? → Paddle per `core/85-payments-billing.md`. NOT re-deciding auth.
- New mobile app? → RevenueCat + IAP per `mobile-app/81-mobile-billing.md`. NOT re-deciding the backend.

**Identify integration points:**
- Which existing tables does the new feature read/write?
- Which existing API endpoints does it extend or depend on?
- Does it share auth with existing features?
- Does it need existing background workers or new ones?

**Constraint verification** for the delta (same 12 constraints as NEW mode Step N3i, scoped to what the delta adds; inherited services are not re-checked).

### Step E5: Produce Vision Summary (Existing mode — with extra sections)

Assemble the summary. Uses the **exact same shape and title as Vision Summary** (so `02-epic-decomposition-command` consumes it identically) PLUS two extra sections (`Locked Decisions`, `Compliance Report`). The artifact is titled `Vision Summary` — not "Continuation Summary" — even though this is the existing-mode branch.

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
[Same format as NEW-mode Vision Summary — 12 constraint checks, scoped to the delta]
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

## Output Contract (both modes)

**NEW mode:**
- **Format:** Vision Summary (markdown, exact structure from Step N4) — presented in Traycer conversation.
- **Token budget:** ≤5,000 target, ≤8,000 hard cap.
- **Sections required:** Product Vision, Personas, Value Streams, Full Feature Inventory, Backing Services, External Services, Technology Decisions, Constraints, Out of Scope, Open Questions, Scale Assessment.

**EXISTING mode:**
- **Format:** Same Vision Summary shape (so 02 consumes identically) + extra sections.
- **Token budget:** ≤6,000 target, ≤10,000 hard cap (extras add length).
- **Sections required:** all NEW-mode sections + **Locked Decisions** + **Compliance Report**.
- **Compliance Report drives Retrofit epics in 02.**

**Both modes:**
- **Key routing output:** Scale Assessment determines whether this is a single-epic (→ epic-to-ticket-workflow) or multi-epic (→ `02-epic-decomposition-command`).
- **Lives in:** Traycer conversation context as a spec titled "Vision Summary."
- **Consumed by:** `02-epic-decomposition-command` reads the Vision Summary from conversation context. In Existing mode, 02 also reads Locked Decisions (inherits them into Infrastructure Decisions) and Compliance Report (emits one Retrofit epic per fix-now item).
- **Persisted by:** Traycer's spec store (automatic). `03-expand-epic-files-command` creates tickets per epic from the confirmed decomposition.

## Does NOT

- Does NOT split the vision into epics — that is `02-epic-decomposition-command`.
- Does NOT decide scaffold types per epic — that is `02-epic-decomposition-command`.
- Does NOT decide shape blocks per epic — that is `02-epic-decomposition-command`.
- Does NOT produce infrastructure decisions per epic — that is `02-epic-decomposition-command`.
- Does NOT create files or tickets — this is an orientation command. Ticket creation happens in `03-expand-epic-files-command`.
- Does NOT blindly accept research — challenges against Fabrik reality, budget, maintainability.
- **EXISTING mode:** Does NOT re-derive the full vision (reads it from the existing project) and does NOT re-decide locked technology choices (inherits them).
- **EXISTING mode:** Does NOT auto-fix compliance gaps. Owner decides per gap. Auto-fix is `02-epic-decomposition-command`'s job once fix-now items become Retrofit epics.
- Does NOT plan refactoring of existing code — that's a separate workflow.

## Acceptance Criteria

**Common to both modes:**
- Mode declared explicitly at Step 0 — never auto-detected.
- Input consumed per declared mode and path.
- Research (if present) improved: gaps, conflicts, opportunities surfaced.
- ALL features (or retrofits + new features in Existing mode) present in Feature Inventory — no silent drops.
- Personas explicitly identified — not just "users."
- Value streams stated — not just "it's useful."
- Backing services grounded in actual VPS inventory (`AGENTS.md` § Infrastructure Services).
- External services identified with cost tier (free/paid).
- Technology Decisions section complete — every major NEW choice resolved. No "TBD" allowed.
- All 12 constraints verified: `all clear` / `conflict` / `unknown`. No silent unknowns.
- Scale assessment present with classification and clear next-step routing.
- Vision Summary within token budget for the declared mode.
- Open Questions section captures ALL unresolved items.
- Owner explicitly confirms. Silence ≠ confirmation.
- Zero open questions remain at confirmation (all answered or explicitly deferred).

**NEW mode adds:**
- Multiple research files handled: conflicts flagged in Open Questions, not silently resolved.
- Multi-scaffold visions identified (e.g., python-api + saas-skeleton + wordpress in one vision).
- Single-epic visions routed to `epic-to-ticket-workflow`, not forced through mega-epic-breakdown.
- One checkpoint after analysis + constraints (owner answers gaps, resolves conflicts). Then draft summary presented for final confirmation.

**EXISTING mode adds:**
- Project state read from actual files — not from memory or assumptions.
- Project Snapshot presented and confirmed by owner (Checkpoint E-1).
- Lifecycle gaps (4 stages) detected and surfaced.
- Pre-flight checks completed.
- Compliance Detection executed in three sub-steps (E3.A mechanical, E3.B rule-pack, E3.C owner decision) — all three required.
- `fabrik validate` run and parsed for scaffold compliance.
- `fabrik audit-registrars` run and parsed for shape drift.
- Owner decided on each compliance gap: fix-now / fix-later / accept-as-legacy (Checkpoint E-2).
- Locked Decisions section produced explicitly — listed reasons (data, users, tokens issued).
- Compliance Report section produced — maps each gap to owner decision and epic action.
- New capability scoped as delta — not re-planning existing features.
- Relevant domain modules loaded for new capability.
- Integration points identified (tables, APIs, auth, workers).

## Concrete Example — NEW mode (illustrative)

**Hypothetical vision intake for a "WordPress Factory" product:**

```markdown
# Vision Summary: WordPress Factory (WPF)

## Product Vision
A platform that automates WordPress site creation, management, and scaling.
Provisions new WP sites with pre-configured themes, plugins, SSL, and
monitoring in under 5 minutes via API. For digital agencies managing
50-200 client WordPress sites.

## Personas
- **Agency Admin** — manages all client sites, creates new sites, monitors health
- **Client** — views their site status, requests changes via portal
- **Developer** — customizes themes/plugins, deploys via git push

## Value Streams
- SaaS subscription per managed site ($15-50/month per site)
- Premium theme marketplace (20% commission)
- Managed hosting margin (VPS cost vs client billing)

## Full Feature Inventory
1. Site provisioning engine — create WP site with domain, SSL, DB in <5min
2. Theme management — install, customize, version themes per site
3. Plugin marketplace — curated plugins with one-click install
4. Client portal — per-client dashboard showing site health, analytics
5. Bulk operations — update WP core/plugins across all sites simultaneously
6. Backup management — per-site backup schedules via Backrest
7. Monitoring dashboard — uptime, performance, error rates per site
8. Billing integration — Paddle subscriptions tied to site count
9. API — programmatic site management for agency automation
10. Multi-user auth — agency teams with role-based access

## Backing Services (from VPS)
- postgres-main:5432 — WPF application database (NOT individual WP site DBs)
- redis-main:6379 — session cache, job queue
- MeiliSearch — site/theme/plugin search
- Apprise — notifications (site down, backup failed, billing events)
- Backrest → B2 — WPF application backups
- Gotenberg — PDF invoice generation

## External Services
- Cloudflare — DNS automation per site (via site-provisioner, already deployed)
- Paddle — subscription billing (paid, ~3% transaction fee)
- Backblaze B2 — per-site media storage (paid, ~$5/TB/month)

## Technology Decisions
- **Auth:** Supabase Auth for agency users (managed, set-and-forget) + Authelia for admin dashboard (already deployed)
- **Database:** postgres-main for WPF application data. Individual WP sites get their own DB containers (not postgres-main).
- **Search:** MeiliSearch (already deployed) for site/theme/plugin search
- **Billing:** Paddle — subscription per managed site. Paddle handles tax/invoicing.
- **File storage:** Backblaze B2 for per-site media. WPF app assets in Docker volume.
- **Notifications:** Apprise (already deployed) for site-down, backup-failed, billing alerts
- **Consumed microservices:** site-provisioner for DNS/domain automation per client site
- **Domain structure:** api.wpf.ocoron.com (API), app.wpf.ocoron.com (client portal), admin.wpf.ocoron.com (admin)
- **Scaffold types:** python-api (backend) + saas-skeleton (client portal) — 2 scaffold types → strong multi-epic signal

## Constraints
- x86_64: all clear
- Budget: Paddle + B2 are paid dependencies (~$20/month base + per-site)
- Existing services: site-provisioner handles DNS/domain — consume, don't rebuild
- Duplicate check: all clear (no WP factory exists)
- Port conflicts: all clear (will need port 8020 — available)
- SSH + Docker Compose deployment: all clear (python-api + separate WP containers per site)
- No Alpine: all clear
- 12-Factor: all clear (stateless API, config via env)
- Solo dev capacity: LARGE project — multiple large features
- Observability: all clear (python-api scaffold emits /health + /metrics)

## Out of Scope (Vision Level)
- Custom WP plugin development (agencies bring their own)
- Email hosting (use external: Google Workspace, etc.)
- Site migration from other hosts (manual process)
- White-label branding of the portal

## Open Questions
- Will individual WP sites run as separate Docker containers or shared hosting?
- What's the target for simultaneous site count on VPS1? (resource planning)
- Should the client portal be a separate saas-skeleton project or part of the API?

## Scale Assessment
- Feature count: 10 (3 small, 4 medium, 3 large)
- Classification: multi-epic (~4 epics)
- Reasoning: 3 large features + 4 medium features + multiple scaffold types → too broad for a single epic-to-ticket-workflow run.
- Next step: Proceed to `02-epic-decomposition-command` to define epic boundaries.
```

## Concrete Example — EXISTING mode (illustrative)

**Hypothetical continuation: "youtube" SaaS adding a RAG-search capability.**

```markdown
# Vision Summary: youtube — Adding RAG-Search Over Comment Archive

## Product Vision
youtube is a deployed SaaS that ingests YouTube channel comments and surfaces
viewer-sentiment trends for B2C brands. We're ADDING natural-language search +
AI Q&A over the comment archive so brand managers can ask "what do viewers say
about retinol?" instead of filtering by tags.

## Personas
- **Brand Manager** — existing persona; new capability they use directly
- **Analyst** — NEW persona; uses the Q&A interface for ad-hoc deep dives

## Value Streams
- Higher seat utilization (analysts now justify additional seats)
- Pricing-tier lift (RAG-search is a Pro-tier feature)

## Full Feature Inventory
1. Embedding pipeline for comment archive — large
2. Hybrid retriever (pgvector + tsvector + RRF) — medium
3. AI Q&A endpoint — medium
4. Search UI in client portal — small
R1. Retrofit: add i18n (en + tr) to client portal — medium
R2. Retrofit: add Resilience layer to YouTube Data API calls — medium

## Backing Services (from VPS)
- postgres-main:5432 — existing comment archive + pgvector for embeddings
- redis-main:6379 — existing cache; will store retriever results

## External Services
- OpenRouter — for embedding model (Voyage embedding-3) and the Q&A LLM

## Technology Decisions

**Inherited (locked — do NOT re-decide):**
- Auth: Supabase Auth (Pattern B) — locked because tokens issued, users paying
- Database: postgres-main (multi-tenant w/ tenant_id) — locked, data exists
- Frontend: Next.js + Tailwind + Shadcn — locked, deployed
- Billing: Paddle — locked, subscriptions active

**New decisions (per current ruleset):**
- RAG pipeline: search + classification (Phase 2 per `domain-modules/rag.md`)
- Background processing: existing pg job queue for embedding batch jobs
- Domain structure: no new subdomains (search lives under existing app.youtube.vps1.ocoron.com)

## Locked Decisions
- Auth: Supabase Auth — locked because 1,800 active users
- Database: postgres-main — locked because 50M comments archived
- Shape block (current): needs_database=true, needs_cache=true, exposes_metrics=true, is_admin_dashboard=false, has_persistent_data=true
- Frontend: Next.js — locked, no React → Vue migration desired

## Compliance Report

| Gap | Source | Owner decision | Epic action |
|---|---|---|---|
| i18n missing (en only) | `core/i18n` rule pack | Fix-now | Retrofit epic R1 |
| Resilience layer absent on YouTube Data API | `core/58-resilience.md` | Fix-now | Retrofit epic R2 |
| psycopg2 used instead of asyncpg | `core/25-data-postgres.md` | Accept-as-legacy | No action |
| Shape drift: prometheus registrar inactive | `fabrik audit-registrars` | Fix-now (folded into R2) | Folded into R2 |
| FINANCIALS.md missing | `saas/88-saas-launch-checklist.md` | Fix-later | Deferred |

## Constraints
- x86_64: all clear
- Budget: OpenRouter ~$30/month estimated for 50M comments
- Port conflicts: all clear (no new ports)
- SSH + Docker Compose deployment: all clear (delta is in-place; same compose)
- 12-Factor: all clear for new code
- Vector DB ban: pgvector only — confirmed
- Email streams: N/A (no new email)

## Out of Scope
- Existing comment-ingestion pipeline — not being modified
- Existing comment-sentiment classifier — not being touched
- Tenant model — not being changed
- WordPress integration (not on roadmap)

## Open Questions
- None — owner confirmed scope, retrofits, and locked decisions.

## Scale Assessment
- New feature count: 4 (1 small, 2 medium, 1 large)
- Retrofit count: 2 (both medium)
- Classification: multi-epic (~3 epics)
- Reasoning: 1 large + 2 medium new features + 2 retrofits → too broad for a single epic-to-ticket-workflow run.
- Next step: Proceed to `02-epic-decomposition-command` to define epic boundaries. 02 will emit Retrofit epics R1 and R2 alongside the delta-feature epics.
```
