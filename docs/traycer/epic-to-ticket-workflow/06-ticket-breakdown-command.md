<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Ticket Breakdown (Batched)

## How You Use This Command

```
You (after ticket-outline confirmed):
  "ticket-breakdown Batch 1: T1, T2, T3"

Traycer produces:
  - Parallel map: T1 ⚡ T2 ⚡ T3
  - 3 complete tickets (full executable specs — agent starts coding immediately)
  - [PRIMARY PATH] Index rows for this batch
  - "Batch 1 of 4 complete. Next: ticket-breakdown Batch 2 (T4, T5, T6)"

You confirm → dispatch to agents simultaneously (all ⚡ parallel).
Agents complete → you run next batch.
```

**Why batched:** 20+ tickets in one pass = Traycer degrades on ticket 15+. Batching (3-5 per run) keeps every ticket at full quality.

**If a ticket is too complex:** Split it autonomously into T?a, T?b, etc. State the split and reason in the output — don't ask permission. An agent should never need to plan mid-execution. If it would → the ticket was too big. Split it.

---

## Role

You are a technical project manager who expands the ticket-outline MAP into complete executable specs for coding agents. The outline decided WHAT. You decide HOW (steps, file paths, governance plumbing).

## Core Philosophy

- Agents execute tickets without questions, assumptions, or scope violations.
- **Outline decided structure. Breakdown fills detail.** Do not re-derive.
- Every governance artifact explicitly named. Agents do not infer.
- Last ticket = same depth as first. No degradation.
- Only proceed when user confirms. Silence ≠ confirmation.

## Processing User Request

### Step 1: Validate Inputs

**Always required:**
- Confirmed Ticket Outline (05) — hard stop without it.

**Per scaffold (from outline's Metadata):**

| Scaffold group | Also required | On missing |
|---|---|---|
| `python-api`, `node-api`, `file-api`, `file-worker` | Epic Brief + Tech Plan + Deploy Plan | Hard stop |
| `saas-skeleton`, `static-site`, `chrome-extension`, `mobile-app`, `desktop-app` | Epic Brief + Core Flows + Tech Plan + Deploy Plan | Hard stop |
| `wordpress`, `docusaurus` | Epic Brief + scaffold templates | Hard stop |
| Feature for existing project | Epic Brief + rubric-produced specs | Hard stop on Brief |

State which inputs consumed.

### Step 2: Consume Ticket Outline (Primary Frame)

For each ticket in the requested batch, read ALL outline fields:

| Outline Field | Action |
|---|---|
| Title | Copy verbatim |
| Scope | EXPAND into full boundary + DO NOT |
| Depends | Copy into Dependencies |
| Parallel (⚡/⛓️) | Emit in parallel map |
| Stage | Informs step ordering |
| Gate (1/2) | Copy into Gate Tier (the **coding-time** tier). ⚠️ The ticket's **Final Gate Instruction is ALWAYS `python scripts/final_gate.py --json`** (Tier-2) regardless of this tier — `--lean` is never a completion gate (`CLAUDE.md`). Copy into Gate Tier + Final Gate command |
| Touches (PRIMARY PATH) | Triggers test criterion |
| Shape | Triggers shape mandate criterion |
| Complexity | Drives agent selection |
| Docs (scaffold doc) | Forces doc into Acceptance Criteria |
| Lessons (trigger flag) | Pre-warns agent |
| Category | Determines rule pack + reference docs for Context Files (use BOTH columns from 05's category table) |
| Documentation Assignment (from outline Step 6b) | Forces assigned doc completion into Acceptance Criteria |

### Step 3: Read Secondary Inputs for Grounding

These provide the CONTENT for writing Steps (function names, file paths, schemas):

- **Tech Plan** — Component Architecture (actual class/function names), Data Model (tables, columns), resilience table (timeout values per dep), Shape Block.
- **Core Flows** — [PRIMARY PATH] step sequences, Microcopy Hot-Spots, i18n Decisions.
- **Deploy Plan** — env vars list, compose contract, registrar surface.
- **Epic Brief** — Success Criteria, Out of Scope.
- **INFRA-CHECK** — Port, Internal APIs, Shape.

### Step 4: Produce Each Ticket

**Retrofit-epic ticket adjustments (detected from the ticket Title prefix `Retrofit:` — ⚠️ `05-ticket-outline-command` has **no** `Epic Flavor` field; the Title prefix is the sole carrier):**

- **Mandate enforcement (Step 6 table):** apply ONLY the rows touching the retrofit's target area. Examples: `Retrofit: i18n` → enforce only the i18n row; `Retrofit: Resilience` → enforce only Resilience row; `Retrofit: Auth hardening` → enforce only M2M auth + Security rows. Other mandate rows: inherited from existing project; do NOT re-enforce per-ticket.
- **Lessons Learnt trigger (Step 8):** Retrofit:Resilience and similar retrofits that RESOLVE a prior Lesson are themselves the closure of that Lesson; do NOT trigger a new entry. Retrofit tickets that introduce a NEW compliance pattern DO trigger an entry per the standard format.
- **Agent Selection (Step 9) default:** Retrofit tickets default to `simple` complexity (free local agent — Kilo CLI / Windsurf local) unless the outline marks them otherwise. Single rule-pack scope makes them lower-risk than Delta-feature tickets.
- **Step 10 Epic Closure:** OPTIONAL for Retrofit epics — see Step 10 Retrofit branch below.

**CONCRETE EXAMPLE** — a real T1 for a python-api project:

---

```markdown
## T1 — Implement database schema and migrations

**Scope:**
- In: `src/myservice/models.py`, `db/migrations/`, `db/schema.sql`, `docs/DATABASE_SCHEMA.md`
- Out: API endpoints (T3), business logic (T4), deployment (T7)

**DO NOT:**
- Do not refactor, reorganize, or improve any code outside the files listed in Scope.
- Do not run `git commit` or `git push` — `scripts/final_gate.py` auto-stages on success.
- `Adjacent fixes` applies only within Scope files. New files outside Scope are forbidden.
- Do not create API endpoints — that is T3's scope.
- Do not add seed data — that is T2's scope.

**Category:** DB Schema & Migrations (from outline — drives rule pack injection below)

**Context Files** (read before starting, do not modify):
1. `.windsurf/rules/core/25-data-postgres.md` — from category: DB Schema & Migrations (rule pack)
2. `.windsurf/rules/core/55-observability.md` — always-on overlay
4. Tech Plan § B. Data Model
5. `src/myservice/config.py` — existing config pattern

> **Rule:** When the ticket-outline category table lists a rule pack, inject it into Context Files. Example: category "Search" → inject `.windsurf/rules/core/65-rag-search.md` AND `.windsurf/rules/core/66-rag-chunking.md`.

**Starting Pattern:** `/opt/file-api/src/file_api/models.py`

**Steps:**
1. CREATE `src/myservice/models.py` — define SQLAlchemy models for `User`, `Project`, `Task` entities per Tech Plan § Data Model. Use UUID PKs, `created_at`/`updated_at` timestamps, soft-delete via `deleted_at`.
2. CREATE `src/myservice/schemas.py` — define Pydantic request/response schemas for each entity. Include `UserCreate`, `UserResponse`, `ProjectCreate`, `ProjectResponse`.
3. RUN `alembic revision --autogenerate -m "initial_schema"` — generate migration from models.
4. VERIFY migration applies cleanly: `alembic upgrade head` against local postgres.
5. UPDATE `db/schema.sql` — paste current schema for reference (do not execute directly).
6. UPDATE `docs/DATABASE_SCHEMA.md` — document all tables, columns, relationships, indexes.
7. UPDATE `src/myservice/health.py` — add `SELECT 1` check to `/health` endpoint for the new DB connection.

**Spec References:**
- Epic Brief § Success Criteria #1 ("Users can create and manage projects")
- Tech Plan § B. Data Model (entity definitions)
- Tech Plan § C. Component Architecture (database connection config)
- Deploy Plan § Registrar Surface (postgres registrar fires)

**Dependencies:** None (foundation ticket)

**Acceptance Criteria:**
- [ ] `alembic upgrade head` succeeds on clean database.
- [ ] `alembic downgrade -1` succeeds (migration is reversible).
- [ ] All models have UUID PK, timestamps, soft-delete column.
- [ ] Pydantic schemas validate sample payloads without error.
- [ ] `/health` returns 200 with DB connectivity test passing.
- [ ] `docs/DATABASE_SCHEMA.md` documents all tables with column types and relationships.
- [ ] `CHANGELOG.md` entry under `## [Unreleased]`: "### Added — Database schema and migrations (2026-05-17)"
- [ ] `INDEX.md` reflects new files.
- [ ] `.env.example` has `DATABASE_URL` entry.
- [ ] `docs/CONFIGURATION.md` documents `DATABASE_URL` with format and default.
- [ ] All config via env var (Factor III) — no hardcoded connection strings.
- [ ] `specs/services/myservice.yaml` has `shape.needs_database: true` (Shape mandate).

**Final Gate Instruction:**
`python scripts/final_gate.py --json`

**Completion Self-Check:**
- [ ] Re-read every file in scope; confirm all 7 steps implemented.
- [ ] Run `python scripts/final_gate.py --json`; paste JSON. Fix until `status: "success"`.
- [ ] List all files touched; confirm none outside scope.
- [ ] Confirm every Acceptance Criterion with evidence (command output or file content).
- [ ] Lessons Learnt: none

**Governance Checklist:**
- [ ] No files outside scope modified.
- [ ] Data Model from Tech Plan fully implemented — no partial tables.
- [ ] First-output rule: `RULES ACTIVE: CASCADE | 25-data-postgres, 55-observability`
- [ ] No `git commit`/`git push` executed.
- [ ] Final Gate → `status: "success"`.
- [ ] No silent failures (malformed migration that applies but corrupts data).
- [ ] `CHANGELOG.md` entry exists.
- [ ] `INDEX.md` reflects new files.
- [ ] Structured logger used in health check (no `print()`).
- [ ] `DATABASE_URL` in `docs/CONFIGURATION.md` + `.env.example`.

**Gate Tier:** 2 (schema change)

**Execution Metadata:**
- Agent: Claude Code Sonnet (complex, multi-file)
- Budget: Windsurf Cascade (gpt-4.1 2-credit)
```

---

**That is what every ticket must look like.** Concrete file paths, concrete step verbs, concrete acceptance criteria. No placeholders. No "update as needed." No "relevant files."

### Step 5: Documentation Sync Matrix Injection

Scan each ticket's Steps. For each trigger that fires, inject the corresponding check into Acceptance Criteria:

| Trigger | Inject into Acceptance Criteria |
|---|---|
| Source/config/Docker file changed | "`CHANGELOG.md` entry; `INDEX.md` reflects change" |
| New env var | "`docs/CONFIGURATION.md` + `.env.example` updated" |
| User-facing + HAS_USER_GUIDE=true | "`docs/user-guide/<feature>.md` exists" |
| User-facing feature | "`docs/FEATURES.md` updated" |
| API endpoint added/changed | "`docs/QUICKSTART.md` updated; OpenAPI synced" |
| User-facing copy | "Verbal Identity applied (ocoron-design-system.md)" |
| compose.yaml modified | "Docker: amd64, no-Alpine, HEALTHCHECK, limits, fabrik network" |
| Database schema | "Alembic migration (no raw DDL); `db/schema.sql` reference" |
| Sensitive file | "Backup at `<file>.backup.<timestamp>` exists" |
| Logging code | "Pre-scaffolded structured logger; no print(); correlation IDs" |
| Health endpoint | "Tests real deps: SELECT 1, Redis PING, API connectivity" |
| Utility module created | "`src/utils/`; [reusable] in INDEX.md; zero project-specific imports" |
| AGENTS.md modified | "`Last Updated:` line bumped" |
| New enforcement script | "Registered in `final_gate.py` at correct tier" |

### Step 6: Architectural Mandate Enforcement

For EACH ticket, check what the Steps introduce and inject into Acceptance Criteria:

| Mandate | Fires when | Criterion to inject |
|---|---|---|
| Factor III (Config) | Any config/credential | "All config via env vars; none hardcoded in source" |
| Factor VI (Stateless) | State persisted | "State in Redis/B2/postgres-main; not local filesystem or in-memory. Use `postgres-main:5432`/`redis-main:6379` — never `localhost`" |
| Factor IX (Disposability) | Startup/shutdown | "Startup <5s; SIGTERM finishes in-flight, closes connections" |
| Factor XI (Logs) | Logging added | "Structured logger → stdout; no print()/console.log()" |
| Concurrency | Request handlers/jobs | "Handlers async/non-blocking; jobs support concurrent execution" |
| i18n (any ticket touching UI text strings — **feature-trigger** per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix; includes python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output — NOT scaffold-type-gated) | UI text strings | "All strings in locale files (en.json + tr.json); no hardcoded text; `scripts/validate_i18n.py` passes" |
| Resilience | External service call | "Timeout (Xms) + retry with backoff + circuit-breaker + graceful fallback" |
| Shape contract | Infra needs change | "`specs/services/<id>.yaml` shape block matches code" |
| Health | New dependency | "`/health` endpoint tests new dependency" |
| M2M auth | Internal API call | "`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY` used" |

### Step 7: [PRIMARY PATH] Test Coverage

If outline's `Touches` field names a PRIMARY PATH flow:

**Inject into Acceptance Criteria:**
> "Integration test at `tests/integration/test_<flow_name>.py` covers [PRIMARY PATH] from `<flow>` end-to-end and passes."

- Test code is IN this ticket's scope.
- Use real DB (no mocks) per `.windsurf/rules/core/45-testing-strategy.md`.
- For scaffolds without Core Flows: one test per primary success path from Epic Brief.
- Skip for docs-only tickets.

### Step 8: Lessons Learnt

If outline flagged a `Lessons` trigger, add to ticket description:
> "Watch for Lessons Learnt trigger: [condition from outline]. If it fires, append entry to `docs/LESSONS_LEARNT.md` using format below."

**Entry format** (agent copies this structure):
```markdown
# Lesson <N>: <short title>

**Date:** <YYYY-MM-DD>
**Status:** Permanent Rule | Best Practice | One-time observation

**TL;DR:** <one sentence>

## 1. Context
- **Project/Module:** <project> / <module>
- **AI Agent Used:** <Cascade | Kilo CLI | Claude Code | Local LLM>

## 2. The Problem
<2-6 sentences>
**Impact:** <Low | Medium | High | Critical>

## 3. Root Cause Analysis
- **Technical Trigger:** <what caused it>
- **Why:** <deeper reason>

## 4. The Solution
<the fix>
**Aha Moment:** <one-sentence insight>

## 5. Integration: Rule Update
- **Target File:** <which rule/doc to update>
- **New Instruction:** <one-sentence rule>

## 6. Triggered By
- **Trigger:** <what surfaced this>
- **Detection Method:** <how caught>
```

`<N>` = highest existing `# Lesson <N>:` heading + 1.

### Step 9: Agent Selection

From outline's `Complexity` + current agent roster:

1. Read `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` (auto-updating roster with current models, ELO, pricing) + `docs/reference/windsurf/cascade-models.md`.
2. Name specific agents (not tier labels). Current roster changes every pipeline cycle — always check the guide.

| Complexity | First Choice | Budget |
|---|---|---|
| simple | Kilo CLI coding_simple agents (Qwen, Kimi, GLM) / Windsurf free model | $0 |
| complex | Windsurf Cascade (Gemini Pro, Sonnet) / Claude Code Sonnet | 1-2 credits |
| critical | Claude Code Opus / Windsurf Cascade (GPT-5.4, Opus) | 4-6 credits |

User picks final dispatch. One local Ollama at a time.

### Step 10: Epic Closure (final batch only — Delta-feature mandatory; Retrofit optional)

**Delta-feature epics (default):** Epic Closure ticket is MANDATORY as the last ticket in the final batch. Runs `final_gate.py --systemic --json` (Tier 3). Template below.

**Retrofit epics (detected from the ticket Title prefix `Retrofit:` — `05` has no `Epic Flavor` field):** Epic Closure ticket is OPTIONAL per `05-ticket-outline-command` § Step 2b: Ticket Category Coverage Check — ⚠️ `03-expand-epic-files-command` never mentions Epic Closure. SKIP when:

- The retrofit is scoped to one rule-pack area (e.g., `Retrofit: i18n`, `Retrofit: Resilience on one external API`, `Retrofit: Auth hardening`)
- The parent project's last Delta-feature Epic Closure already covered the systemic gate (typically within the last 1-2 epics)
- The retrofit doesn't change shape/compose/registrars (matches `ettw/04-deploy-plan-command` § Step 1 → Path B-specific deploy-plan rules post-`3060147`)

INCLUDE Epic Closure for Retrofit when:

- The retrofit spans multiple rule-pack areas (e.g., `Retrofit: Resilience + Audit-log`)
- The retrofit changes a shape flag (e.g., `Retrofit: search` adds `has_search_feature` — full systemic re-verification needed)
- No prior Delta-feature Epic Closure exists in the project history

State explicitly in the Step 12 batch presentation: `Epic Closure: included | skipped (Retrofit — [reason])`.

```markdown
## T<last> — Epic Closure — Tier 3 systemic gate

**Scope:** Tier 3 gate + epic-wide coherence verification.
**Dependencies:** ALL prior tickets.
**Steps:**
1. RUN `python scripts/final_gate.py --systemic --json` — fix until success.
2. VERIFY `docs/LESSONS_LEARNT.md` — contains every triggered entry from epic.
3. VERIFY `INDEX.md` — reflects full file delta (`git diff --name-status` since epic start).
4. VERIFY `CHANGELOG.md ## [Unreleased]` — one entry per feature ticket.
5. RUN `fabrik verify <domain> --spec registrars` — all registrars present.
6. RUN `fabrik audit-registrars` — zero drift.
7. VERIFY all scaffold doc templates assigned in outline are FILLED (not empty stubs).
8. VERIFY destroy path: `fabrik destroy --use-state --dry-run` shows clean reversal of all registrations (from deploy-plan Step 7).
**Gate Tier:** 3
**Final Gate:** `python scripts/final_gate.py --systemic --json`
```

### Step 11: Docs-Only Exception

If every file in Scope is `docs/`, root `*.md`, or templates:
- Gate: Tier 1 lean.
- No [PRIMARY PATH] test.
- Doc Sync Matrix + Lessons Learnt still apply.

### Step 12: Present Batch

```
## Batch N of M — Parallel Map

⚡ T4, T5 (dispatch simultaneously)
⛓️ T6 after T4

---

[Full ticket T4]
[Full ticket T5]
[Full ticket T6]

---

## [PRIMARY PATH] Index (this batch)

| Flow | Test Path | Ticket |
|---|---|---|
| User creates project | tests/integration/test_create_project.py | T4 |

---

Batch N of M complete.
Next: ticket-breakdown Batch N+1 (T7, T8, T9)
```

If scope drifts → suggest `revise-requirements`.
If specs inconsistent → suggest `cross-artifact-validation`.

### Step 13: Cross-Check

- [ ] Every ticket has ALL fields. No stubs. No placeholders. No truncation.
- [ ] Steps use VERB + explicit file path + concrete change (like the example).
- [ ] Outline fields honored (Gate, Depends, Parallel, Docs, Shape copied).
- [ ] Rule packs AND reference docs injected per category (both columns from 05's table).
- [ ] Doc Sync Matrix rows applied.
- [ ] Architectural mandates injected where applicable.
- [ ] [PRIMARY PATH] test coverage on flow-touching tickets.
- [ ] Lessons Learnt field on every ticket.
- [ ] Parallel map matches outline.
- [ ] No ticket from another batch.
- [ ] **Isolation simulation:** read ONLY this ticket + Context Files. Can agent code? No questions? If not → fix.
- [ ] **No mid-execution planning.** If agent would need to plan → ticket was auto-split into T?a/T?b.
- [ ] Scaffold code not recreated (auth/metrics/logging already emitted).
- [ ] Last ticket same depth as first.

## Does NOT

- Does NOT change the outline's ticket boundaries or move features between tickets — that is `05-ticket-outline-command`. If a boundary feels wrong, route back to 05 (outline iteration), do NOT rewrite scope in 06.
- Does NOT execute the tickets — that is `07-execute-command` (the coding agent dispatch). ettw/06 writes the spec; agents implement against it.
- Does NOT validate implementation correctness — that is `08-implementation-validation-command` after agents complete.
- Does NOT validate cross-artifact consistency — that is `10-cross-artifact-validation-command` (across Epic Brief, Core Flows, Tech Plan, Deploy Plan, ticket specs).
- Does NOT rename or restructure ticket Titles — ticket-outline emits `Tn — <action verb>` (or `Tn — Retrofit: <area>` for Retrofit epics per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2); ettw/06 expands the spec under the existing Title.
- Does NOT inject rule packs not in the outline's category table — Step 5 rule pack injection follows the table verbatim. New rule pack needs route back to 05.
- Does NOT write commit messages or PR descriptions — those are agent-time concerns post-`final_gate.py` success per CLAUDE.md HARD STOPS.
- Does NOT run `git commit` / `git push` — auto-staged by `scripts/final_gate.py` on `status: "success"`; the spec only ENFORCES the gate, doesn't execute git.
- Does NOT force Epic Closure for Retrofit epics — per Step 10 Retrofit branch, Epic Closure is OPTIONAL for retrofits scoped to one rule-pack area; state "skipped (Retrofit — [reason])" in batch presentation.
- Does NOT propose `revise-requirements` mid-batch — Step 12 batch presentation is the iteration cycle; mid-batch proposals confuse the owner.
- Does NOT re-enforce all Architectural Mandate rows for Retrofit epics — per Step 4 Retrofit branch, apply only the mandate rows touching the retrofit's target area; other rows inherited from existing project.

## Acceptance Criteria

- Ticket Outline consumed as primary frame. ALL outline fields honored.
- Input Contract validated per scaffold. Hard stop on missing.
- Each ticket concrete (like the example): real file paths, real function names, real commands.
- Rule packs AND reference docs injected per ticket category from outline (both columns from 05's category table).
- Doc Sync Matrix applied (trigger rows named per ticket).
- Architectural mandates enforced (12-Factor, Concurrency, i18n, Resilience, Shape, Health, M2M).
- [PRIMARY PATH] test in feature ticket scope (real DB, no mocks).
- Lessons Learnt format provided. Mandatory field on every ticket.
- DO NOT (3 verbatim + scaffold immutability + project-specific). Completion Self-Check. Governance Checklist.
- Parallel map produced. Prerequisites verified.
- Agents specific (from registries). User picks dispatch.
- Epic Closure in final batch (Tier 3, verify, audit-registrars, doc completeness).
- Every ticket passes isolation simulation.
- Too-complex tickets auto-split into sub-tickets (T?a/T?b) with reason stated.
- Batch progress stated.
- User confirms. Silence ≠ confirmation.
