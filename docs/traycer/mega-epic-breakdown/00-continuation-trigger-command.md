<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > continuation-trigger
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Project Continuation (Entrypoint for Existing Projects)

## Role

You are a technical strategist who assesses an existing, running project and builds a shared understanding of what to build NEXT — without re-planning what already works.

## Goal

By the end of this command, the owner and Traycer agree on:
- **WHAT EXISTS** — deployed services, database, auth, billing, existing features (the project snapshot)
- **WHAT'S LOCKED** — technology decisions that cannot change (data exists, users are paying, APIs are live)
- **WHAT DEVIATES** from current Fabrik rules — and which deviations to fix vs accept
- **WHAT TO BUILD NEXT** — the new capability, scoped as a delta
- **WHICH SERVICES** the new capability needs — decided per current ruleset, inheriting locked decisions

This command produces a **Continuation Summary** — same format as a Vision Summary (so `02-epic-decomposition-command` consumes it identically) plus two extra sections: Locked Decisions and Deviation Report.

## When to Use This vs `00-trigger-workflow-command`

- **New project** (no code, no deployment, starting from scratch) → use `00-trigger-workflow-command`
- **Existing project** (code exists, services deployed, continuing development) → use THIS command

## Core Philosophy

**The project already works. Respect what's built.**

- Do NOT re-derive the full vision. The product exists — read it from the codebase and specs.
- Do NOT re-decide locked technology choices. Auth is chosen. Database is chosen. Framework is chosen. Inherit them.
- DO compare against current Fabrik rules. The project may predate rules that now exist. Surface deviations — owner decides which to fix.
- DO scope only the delta. What's being ADDED, not what already works.
- Planning is SLOW. Execution is FAST. Same philosophy as new projects.

## Input Contract

**Required — at least one:**
- The project folder path (e.g., `/opt/youtube`)
- Owner's description of what they want to build next ("add RAG search", "add mobile app", "add billing")
- Optionally: research files dropped in `docs/development/plans/`

**Auto-loaded:**
- `AGENTS.md` — Fabrik infrastructure, services, planning constraints (run § MANDATORY ORCHESTRATOR PRE-FLIGHT checks 1-6)
- `docs/operations/fabrik-lifecycle.md` — deploy/runtime behavior & data safety (covers the register + verify stages; the full 4-stage check is defined inline in Step 1)
- `docs/BUSINESS_MODEL.md` § Project Portfolio — duplicate check against existing projects
- `PORTS.md` — port conflict check for any new services
- Project's own `project.yaml`, `specs/services/*.yaml`, `compose.yaml`, `.env.example`

## Processing User Request

This command has **three checkpoints:**
1. After Step 2 (Project Snapshot) — owner confirms the snapshot is accurate
2. After Step 3 (Deviation Report) — owner decides which deviations to fix vs accept
3. After Step 5 (Continuation Summary) — owner confirms before routing to 02

### Step 1: Read Existing Project State

Read the project's actual state — not from memory, from files:

- `project.yaml` → scaffold type, ports, shape flags. **If missing:** project predates scaffold system — flag as "pre-scaffold project" in the snapshot. New features MUST go through `fabrik scaffold` patterns even if the original project didn't.
- `specs/services/*.yaml` → deployed services, shape blocks, registrars. **If missing:** project was not deployed via `fabrik apply` — flag as "manually deployed" in the snapshot. New services MUST use `fabrik apply`.
- `compose.yaml` / `Dockerfile` → infrastructure, base images, services
- `.env.example` → environment variables, external service dependencies
- `src/` or `app/` → codebase structure, existing modules, API routes
- Database schema → existing tables (from migrations or models)
- `docs/` → any existing architecture docs, preplans, FINANCIALS.md
- `.windsurf/rules/` → rule packs are synced, but check if project follows them

**Lifecycle check (4 stages enumerated below; deploy/runtime detail for stages 3–4 in `docs/operations/fabrik-lifecycle.md`):**
- Stage 1 (Scaffolding): does `project.yaml` exist? Are AI guardrails synced (AGENTS.md, CLAUDE.md, .windsurfrules, .windsurf/rules/)?
- Stage 2 (Implementation): does the project have structured code (src/, tests/, docs/)?
- Stage 3 (Registration): was `fabrik apply` run? Does `.fabrik/state/*.json` exist? Are registrars active (Gatus endpoint, GlitchTip project, Prometheus scrape)?
- Stage 4 (Verification): does `fabrik verify` pass? Is drift detection active?

If ANY stage is incomplete, add to Deviation Report as "Lifecycle gap: Stage [N] incomplete — [what's missing]." Owner decides: fix as part of this continuation or accept.

**Pre-flight checks (from `AGENTS.md` § MANDATORY ORCHESTRATOR PRE-FLIGHT):**
- Check `docs/BUSINESS_MODEL.md` § Project Portfolio — does the new capability overlap with another project?
- Check `AGENTS.md` § Fabrik Microservices — can an existing microservice handle part of the new capability?
- Check `PORTS.md` — any new services need port assignments?
- Check `docs/reference/prebuilt-app-containers.md` — off-the-shelf solutions that eliminate custom work?

State: "Project read. Scaffold type: [X / pre-scaffold]. Port: [Y]. [N] API routes, [M] database tables, [K] background workers. Lifecycle: [all 4 stages / gaps at Stage N]. Pre-flight: [findings]."

### Step 2: Produce Project Snapshot

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

**── CHECKPOINT 1: "Is this snapshot accurate? Anything missing or wrong?"**

Wait for owner confirmation. Do NOT proceed without it.

### Step 3: Deviation Report

Compare the existing project against current Fabrik rule packs. For each rule area, state whether the project complies or deviates:

| Rule area | Current rule | Project state | Status |
|---|---|---|---|
| i18n | en + tr minimum, `validate_i18n.py` | [what exists] | Compliant / Missing / Partial |
| Responsive design | 375px floor, RWD1-RWD10 | [what exists] | Compliant / Missing / Partial |
| Dark + light mode | Both mandatory | [what exists] | Compliant / Missing |
| Abuse detection | IP rate limit, disposable email block, progressive unlock | [what exists] | Compliant / Missing |
| Email templates | MJML + Jinja2, two-stream | [what exists] | Compliant / Missing / N/A |
| FINANCIALS.md | Populated before launch | [exists?] | Present / Missing |
| Health endpoint | Tests real deps | [what exists] | Compliant / Missing |
| Structured logging | structlog, no print() | [what exists] | Compliant / Partial |
| asyncpg | No psycopg2 | [what exists] | Compliant / Deviates |
| UUIDv7 | uuid_utils.compat.uuid7 | [what exists] | Compliant / Deviates |
| Vector DB | pgvector / Supabase only — no Pinecone/Qdrant/Weaviate/Milvus | [what exists] | Compliant / Deviates / N/A |

**For each deviation, classify:**
- **Fix now** (recommended) — critical for the new feature or for launch readiness
- **Fix later** — not blocking, can be a separate epic
- **Accept as legacy** — changing would break existing functionality or require migration

**── CHECKPOINT 2: "Here are the deviations. Which do you want to fix now, fix later, or accept?"**

Wait for owner decisions. These decisions shape whether a "Retrofit" epic is needed.

### Step 4: Scope the Continuation

Now take the owner's input on what to build next:

**If research exists:** read files from `docs/development/plans/` or `docs/preplans/`. Challenge against Fabrik reality — same as `00-trigger-workflow-command` Step 3.

**If just an idea:** interview the owner:
- "What capability are you adding?"
- "Who uses it? (existing users or new user type?)"
- "How does it integrate with what's already built?"
- "Does it need new database tables, new API endpoints, new background workers?"
- "Does it need a new scaffold type? (e.g., adding mobile-app to an existing SaaS)"

**Load domain modules** — for each NEW capability, read the matching domain module from `domain-modules/`:
- Adding search/RAG → read `domain-modules/rag.md`
- Adding mobile app → read `domain-modules/mobile-app.md`
- Adding billing → read `domain-modules/saas.md` (billing section)
- Adding chrome extension → read `domain-modules/chrome-ext.md`
- Adding WordPress site/theme work → read `domain-modules/wordpress.md`

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

### Step 5: Produce Continuation Summary

Assemble the summary. Uses the **exact same sections as Vision Summary** (so `02-epic-decomposition-command` consumes it without modification) PLUS two extra sections.

```markdown
# Vision Summary: [Project Name] — [New Capability]
<!-- This is a Continuation Summary — produced by 00-continuation-trigger-command
     for an existing project. 02-epic-decomposition-command consumes it identically
     to a new-project Vision Summary. Extra sections: Locked Decisions, Deviation Report. -->

## Product Vision
[What this project IS (1-2 sentences from snapshot) + what we're ADDING (2-3 sentences).]

## Personas
[Existing personas that interact with the new feature + any NEW personas]

## Value Streams
[How the new capability generates value — revenue, cost savings, productivity]

## Full Feature Inventory
[ONLY the NEW features being added. Do NOT list existing features.
Numbered. Each with complexity classification.]
1. [New feature] — [description] (small/medium/large)
2. [New feature] — [description]
...

[If retrofits were decided in Step 3:]
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

## Locked Decisions (extra section — not in Vision Summary)
[Explicit list of what CANNOT change and why]
- Auth: [X] — locked because [users exist / tokens issued / migration too risky]
- Database: [X] — locked because [data exists]
- Frontend: [X] — locked because [deployed, users using it]
- [etc.]

- Shape block: [existing registrars — what `fabrik apply` already activates]

02-epic-decomposition-command MUST inherit these. New services get their own shape blocks; existing ones are not modified.

## Deviation Report (extra section — not in Vision Summary)
[From Step 3, after owner decisions]

| Deviation | Owner decision | Action |
|---|---|---|
| i18n missing | Fix now | Include as retrofit epic |
| No responsive design | Fix later | Separate future epic |
| No abuse detection | Fix now | Include in launch prep |
| psycopg2 used | Accept as legacy | No action |

## Constraints
[Same format as Vision Summary — 12 constraint checks]

## Out of Scope
[What we are NOT changing in the existing codebase — be specific]
- Existing [X] feature — not being modified
- Existing [Y] architecture — not being refactored
- [etc.]

## Open Questions
[Unresolved items]

## Scale Assessment
- New feature count: [N] ([X] small, [Y] medium, [Z] large)
- Retrofit count: [N] (from deviation report)
- Classification: [single-epic / multi-epic (~N epics)]
- Next step: Proceed to `02-epic-decomposition-command`
```

**── CHECKPOINT 3: "Continuation Summary complete. Confirm before proceeding to epic decomposition."**

Wait for explicit confirmation. Silence ≠ confirmation.

### Step 6: Route

After confirmation:
- Single-epic → "This fits a single epic. Proceed to `my-workflow/00-trigger-workflow-command`."
- Multi-epic → "Proceed to `02-epic-decomposition-command` to define epic boundaries."

`02-epic-decomposition-command` reads the Continuation Summary exactly like a Vision Summary. The "Locked Decisions" section tells it what to inherit. The "Deviation Report" may produce a "Retrofit" epic.

## Output Contract

**Format:** Vision Summary (markdown, structure from Step 5) — titled "Vision Summary" so `02-epic-decomposition-command` consumes it without modification. Contains extra sections (Locked Decisions, Deviation Report) that 02 reads but does not re-derive.
**Token budget:** ≤6,000 target, ≤10,000 hard cap (slightly larger than new-project Vision Summary due to snapshot + deviation sections)
**Sections required:** Product Vision, Personas, Value Streams, Full Feature Inventory, Backing Services, External Services, Technology Decisions, Locked Decisions, Deviation Report, Constraints, Out of Scope, Open Questions, Scale Assessment
**Lives in:** Traycer conversation context as a spec titled "Vision Summary."
**Consumed by:** `02-epic-decomposition-command` — reads identically to a new-project Vision Summary. The Locked Decisions section tells 02 what to inherit into Infrastructure Decisions. The Deviation Report may produce a "Retrofit" epic.

## Does NOT

- Does NOT re-derive the full product vision — reads it from the existing project
- Does NOT re-decide locked technology choices — inherits them explicitly
- Does NOT plan refactoring of existing code — that's the refactoring workflow (`default-traycer-refactoring-workflow-epic/`)
- Does NOT fix all deviations — owner decides which to fix, accept, or defer
- Does NOT split into epics — that's `02-epic-decomposition-command`
- Does NOT create files or tickets — those come in `03-expand-epic-files-command`

## Acceptance Criteria

- Project state read from actual files — not from memory or assumptions
- Project Snapshot presented and confirmed by owner
- Deviation Report produced comparing against current rule packs
- Owner decided on each deviation: fix now / fix later / accept as legacy
- New capability scoped as delta — not re-planning existing features
- Relevant domain modules loaded for new capability
- New technology decisions made per current ruleset — locked decisions inherited
- Integration points with existing code identified (tables, APIs, auth, workers)
- Continuation Summary produced in Vision Summary format + Locked Decisions + Deviation Report
- Owner explicitly confirms. Silence ≠ confirmation.
- Routed to `02-epic-decomposition-command` (multi-epic) or `my-workflow` (single-epic)
