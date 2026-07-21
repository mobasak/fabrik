<!-- ⚠️ FABRIK FACTORY WORKFLOW — TICKET BREAKDOWN (our own, tool-capable twin of 06-ticket-breakdown-fabrik)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in VS Code) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the confirmed outline + Tech/Deploy/Core-Flows + the LOCKED Decisions Lock from disk and writes complete
     executable ticket specs. The outline decided WHAT; this decides HOW (steps, file paths, governance).

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the confirmed Ticket Outline (`05-ticket-outline-fabrik` output) — the PRIMARY frame
       · Tech Plan (`03-tech-plan-fabrik`) — real class/function names, Data Model, resilience timeouts
       · Core Flows (`02-core-flows-fabrik`, if present) — `[PRIMARY PATH]` sequences, Microcopy, i18n
       · Deploy Plan (`04-deploy-plan-fabrik`) — env vars, compose contract, registrar surface
       · Decisions Lock (`01-decisions-lock-fabrik`) — Success Criteria, Out of Scope · the `00-trigger-fabrik` INFRA-CHECK
     The category-table rule packs are INJECTED into each ticket's Context Files (the CODING agent reads them,
     not this command); the coder-agent roster is resolved LIVE by `pick_models` at dispatch — both provenance.
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Ticket Breakdown (Batched)

## How You Use This Command

After the outline is confirmed: `06-ticket-breakdown Batch 1: T1, T2, T3` → produces the parallel map (`T1 ⚡ T2 ⚡ T3`), 3 complete executable tickets (an agent starts coding immediately), the `[PRIMARY PATH]` Index rows, and "Batch 1 of N complete. Next: Batch 2." **Why batched:** 20+ tickets in one pass degrades on ticket 15+; batching (3–5/run) keeps every ticket at full quality. **Too-complex ticket:** split it autonomously into `T?a`/`T?b`, state the split + reason — do not ask. An agent should never plan mid-execution; if it would, the ticket was too big.

## Role

Technical project manager who expands the outline MAP into complete executable specs for coder agents. The outline decided WHAT; you decide HOW. Every governance artifact explicitly named — agents do not infer. Last ticket = same depth as the first. Only proceed on explicit confirmation.

## Processing User Request

### Step 1: Validate Inputs

**Always:** the confirmed Ticket Outline (`05-ticket-outline-fabrik`) — hard stop without it. **Per scaffold** (from the outline Metadata): headless (`python-api`/`python-api-gpu`/`node-api`/`file-api`/`file-worker`) → Decisions Lock + Tech Plan + Deploy Plan; GUI (`saas-skeleton`/`static-site`/`chrome-extension`/`mobile-app`/`desktop-app`) → + Core Flows; `docusaurus` → Decisions Lock + scaffold templates; feature-for-existing → Decisions Lock + the produced specs. Hard stop on any missing. State which inputs were consumed.

### Step 2: Consume the Outline (Primary Frame)

For each ticket in the batch, read ALL outline fields: **Title** (verbatim) · **Scope** (expand into full boundary + DO NOT) · **Depends** (→ Dependencies) · **Parallel ⚡/⛓️** (→ parallel map) · **Stage** (step ordering) · **Gate 1/2** (→ Gate Tier — the **coding-time** tier ONLY; ⚠️ do NOT copy into the Final Gate command: the **Final Gate Instruction is `python scripts/final_gate.py --json`** (Tier-2), or `--systemic --json` for the Epic Closure ticket; `--lean` is never a completion gate `[canonical: CLAUDE.md § Completion Contract]`) · **Touches (PRIMARY PATH)** (→ test criterion) · **Shape** (→ shape mandate criterion) · **Complexity** (→ agent selection, Step 9) · **Docs** (→ forces the doc into Acceptance Criteria) · **Lessons** (pre-warn) · **Category** (→ rule pack + reference docs for Context Files, using BOTH columns of the outline's category table) · **Documentation Assignment** (→ forces the assigned doc's completion into Acceptance Criteria).

### Step 3: Read Secondary Inputs for Grounding

For the CONTENT of Steps (function names, paths, schemas): **Tech Plan** (Component Architecture class/function names, Data Model tables/columns, resilience timeouts, Shape Block) · **Core Flows** (`[PRIMARY PATH]` sequences, Microcopy Hot-Spots, i18n Decisions) · **Deploy Plan** (env vars, compose contract, registrar surface) · **Decisions Lock** (Success Criteria, Out of Scope) · **INFRA-CHECK** (Port, Internal APIs, Shape).

### Step 4: Produce Each Ticket

**Retrofit-epic adjustments** (detected from the Title prefix `Retrofit:` — `05-ticket-outline-fabrik` has no `Epic Flavor` field; the prefix is the sole carrier): Step-6 mandates → enforce ONLY the rows touching the retrofit's target area (others inherited); Step-8 Lessons → a `Retrofit: Resilience`-style fix that RESOLVES a prior Lesson is that Lesson's closure (no new entry); a retrofit introducing a NEW compliance pattern DOES trigger one; Step-9 agent → default `simple` complexity unless the outline says otherwise (single-rule-pack scope = lower risk); Step-10 Epic Closure → OPTIONAL (Step 10 branch).

**Every ticket looks like this** — concrete file paths, concrete step verbs, concrete acceptance criteria; no placeholders, no "update as needed", no "relevant files":

```markdown
## T1 — Implement database schema and migrations

**Scope:**
- In: `src/myservice/models.py`, `db/migrations/`, `db/schema.sql`
- Out: API endpoints (T3), business logic (T4), deployment (T7)

**DO NOT:**
- Do not refactor/reorganize/improve any code outside the Scope files.
- Do not run `git commit`/`git push` — `scripts/final_gate.py` auto-stages on success.
- `Adjacent fixes` applies only within Scope files; new files outside Scope are forbidden.
- Do not create API endpoints (T3) or add seed data (T2).

**Category:** DB Schema & Migrations (from outline — drives the rule-pack injection below)

**Context Files** (read before starting, do not modify):
1. `.windsurf/rules/core/25-data-postgres.md` — from category (rule pack)
2. `.windsurf/rules/core/55-observability.md` — always-on overlay
3. Tech Plan § B. Data Model
4. `src/myservice/config.py` — existing config pattern

> **Rule:** when the outline's category table lists a rule pack, inject it into Context Files (e.g. category "Search" → inject `core/65-rag-search.md` AND `core/66-rag-chunking.md`).

**Steps:**
1. CREATE `src/myservice/models.py` — SQLAlchemy models for `User`, `Project`, `Task` per Tech Plan § Data Model (UUID PKs, `created_at`/`updated_at`, soft-delete `deleted_at`).
2. CREATE `src/myservice/schemas.py` — Pydantic request/response schemas per entity.
3. RUN `alembic revision --autogenerate -m "initial_schema"`.
4. VERIFY `alembic upgrade head` applies cleanly against local postgres.
5. UPDATE `db/schema.sql` — the schema source-of-truth reference (do not execute directly).
6. UPDATE `src/myservice/health.py` — add a `SELECT 1` check to `/health` for the new DB connection.

**Spec References:** Decisions Lock § Success Criteria #1 · Tech Plan § B/§ C · Deploy Plan § Registrar Surface (postgres fires).

**Dependencies:** None (foundation ticket).

**Acceptance Criteria:**
- [ ] `alembic upgrade head` succeeds on a clean DB; `alembic downgrade -1` is reversible.
- [ ] All models have UUID PK, timestamps, soft-delete; Pydantic schemas validate sample payloads.
- [ ] `/health` returns 200 with the DB-connectivity check passing.
- [ ] `db/schema.sql` reflects the current schema (⚠️ there is NO `docs/DATABASE_SCHEMA.md` — do not create one).
- [ ] `CHANGELOG.md` `## [Unreleased]`: "### Added — Database schema and migrations (YYYY-MM-DD)"; `INDEX.md` reflects new files.
- [ ] `.env.example` has `DATABASE_URL`; `docs/CONFIGURATION.md` documents it; all config via env var (Factor III).
- [ ] `specs/services/myservice.yaml` has `shape.needs_database: true`.

**Final Gate Instruction:** `python scripts/final_gate.py --json`

**Completion Self-Check:** re-read every scope file; run the gate + paste JSON, fix to `status:"success"`; list files touched (none outside scope); confirm each Acceptance Criterion with evidence; Lessons Learnt: none.

**Governance Checklist:** no out-of-scope files · Data Model fully implemented · first-output `RULES ACTIVE: <agent> | 25-data-postgres, 55-observability` · no `git commit`/`push` · gate `status:"success"` · no silent failures · CHANGELOG + INDEX updated · structured logger in the health check (no `print()`) · `DATABASE_URL` in `docs/CONFIGURATION.md` + `.env.example`.

**Gate Tier:** 2 (schema change).

**Execution Metadata:**
- Complexity: complex (multi-file) → dispatch tier per Step 9 (mid pool model OR `claude -p sonnet`).
```

### Step 5: Documentation Sync Matrix Injection

Scan each ticket's Steps; for each trigger, inject the check into Acceptance Criteria: source/config/Docker changed → "CHANGELOG + INDEX" · new env var → "`docs/CONFIGURATION.md` + `.env.example`" · user-facing + `HAS_USER_GUIDE` → "`docs/user-guide/<feature>.md`" · user-facing feature → "`docs/FEATURES.md`" · API endpoint → "`docs/QUICKSTART.md` + OpenAPI synced" · user-facing copy → "Verbal Identity (`ocoron-design-system.md`)" · compose modified → "amd64, no-Alpine, healthcheck, limits, fabrik network" · DB schema → "Alembic migration (no raw DDL); `db/schema.sql` reference" · sensitive file → "backup at `<file>.backup.<timestamp>`" · logging → "structured logger, no print(), correlation IDs" · health endpoint → "tests real deps (`SELECT 1`, Redis `PING`, API connectivity)" · utility module → "`src/utils/`, `[reusable]` in INDEX, zero project-specific imports" · `AGENTS.md` modified → "`Last Updated:` bumped" · new enforcement script → "registered in `final_gate.py` at the right tier".

### Step 6: Architectural Mandate Enforcement

Per ticket, inject the criterion when the trigger fires: **Factor III** (any config/credential) → "all config via env vars; none hardcoded" · **Factor VI** (state persisted) → "state in Redis/B2/postgres-main, not local FS/memory; use `postgres-main:5432`/`redis-main:6379`, never `localhost`" · **Factor IX** (startup/shutdown) → "startup <5s; SIGTERM finishes in-flight + closes connections" · **Factor XI** (logging) → "structured logger → stdout; no print()/console.log()" · **Concurrency** (handlers/jobs) → "async/non-blocking; jobs concurrent-safe" · **i18n** (any UI text string — **feature-trigger** `[canonical: mega/00 § Rule-area applicability matrix]`, incl. python-api/node-api/file-api with `is_admin_dashboard` OR `is_public` + HTML) → "strings in `en.json` + `tr.json`; no hardcoded text; `scripts/validate_i18n.py` passes" · **Resilience** (external call) → "timeout (Xms) + retry/backoff + circuit-breaker + graceful fallback" · **Shape contract** (infra change) → "`specs/services/<id>.yaml` shape matches code" · **Health** (new dep) → "`/health` tests the new dependency" · **M2M auth** (internal API call) → "`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`".

### Step 7: [PRIMARY PATH] Test Coverage

If the outline `Touches` field names a PRIMARY PATH: inject "integration test at `tests/integration/test_<flow>.py` covers the `[PRIMARY PATH]` end-to-end and passes." Test code is IN scope; use a real DB (no mocks) per `core/45-testing-strategy.md`; for scaffolds without Core Flows, one test per primary success path from the Decisions Lock; skip for docs-only tickets.

### Step 8: Lessons Learnt

If the outline flagged a `Lessons` trigger, add: "Watch for Lessons Learnt trigger: [condition]. If it fires, append to `docs/LESSONS_LEARNT.md` using the format below." Entry format: `# Lesson <N>: <title>` · **Date** · **Status** (Permanent Rule | Best Practice | One-time) · **TL;DR** · **1. Context** (Project/Module; **AI Agent Used:** the dispatched coder — the pool model `pick_models` selected OR `claude -p opus/sonnet/haiku`) · **2. Problem** + Impact · **3. Root Cause** · **4. Solution** + Aha · **5. Rule Update** (target file + one-line rule) · **6. Triggered By**. `<N>` = highest existing `# Lesson <N>:` + 1.

### Step 9: Agent Selection — the fabrik coder-agent roster

Fabrik dispatches each ticket to a coder agent from **two mechanisms** (NOT the retired Kilo/Windsurf/Claude-Code triad):

- **The OpenRouter pool** via `pick_models("code", n)` `[canonical: libs/subagents/select.py — pick_models]` — the **flywheel-ranked** coder roster, best-first, **no default price cap** (`max_cost_per_mtok=` is an opt-in budget). The roster is **LIVE** — never hard-code or name models; it is whatever `pick_models("code")` returns today, ranked by real recorded runs in `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (auto-read by the module). Every run records to the flywheel.
- **Native Claude via `claude -p`** — `opus` / `sonnet` / `haiku` (any Claude model via `claude -p --model`) — for high-risk/authoritative tickets (auth, schema, migrations, concurrency, secrets) where an Opus-grade pass is warranted. ⚠️ The driver's *autonomous* producer defaults to **Opus 4.8** (Fable 5 opt-in, metered) `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`; an operator-directed dispatch may pick a cheaper Claude tier (`sonnet`/`haiku`) for a lower-risk ticket.

Map the outline `Complexity` to a dispatch tier (the exact model is resolved by `pick_models` / the driver at dispatch, not named here):

| Complexity | Dispatch tier |
|---|---|
| simple | cheapest pool coder model (`pick_models("code", prefer="value")`) — records the flywheel |
| complex | a mid pool coder model OR `claude -p sonnet` |
| critical | `claude -p opus` (auth / schema / migrations / concurrency / secrets — the authoritative pass) |

The operator picks the final dispatch; the pool never runs `anthropic/*` (Claude via OpenRouter is expensive — use the native `claude -p` path for Claude).

### Step 10: Epic Closure (final batch — Delta-feature mandatory; Retrofit optional)

**Delta-feature:** the last ticket, MANDATORY, runs `final_gate.py --systemic --json` (Tier 3). **Retrofit** (Title prefix `Retrofit:`): OPTIONAL `[canonical: 05-ticket-outline-fabrik § Step 1 — Epic-flavour rules]` — SKIP when the retrofit is scoped to one rule-pack area, the parent's last Delta-feature closure covered the systemic gate, and it changes no shape/compose/registrar (`04-deploy-plan-fabrik` § Step 1 skip rule); INCLUDE when it spans multiple rule-pack areas, changes a shape flag (e.g. `Retrofit: search` → `has_search_feature`), or no prior Delta-feature closure exists. State in the Step-12 batch: `Epic Closure: included | skipped (Retrofit — [reason])`.

```markdown
## T<last> — Epic Closure — Tier 3 systemic gate
**Scope:** Tier-3 gate + epic-wide coherence. **Dependencies:** ALL prior tickets.
**Steps:** 1. RUN `python scripts/final_gate.py --systemic --json` (fix to success). 2. VERIFY `docs/LESSONS_LEARNT.md` has every triggered entry. 3. VERIFY `INDEX.md` reflects the full file delta. 4. VERIFY `CHANGELOG.md ## [Unreleased]` — one entry per feature ticket. 5. RUN `fabrik verify <domain> --spec registrars` (all present). 6. RUN `fabrik audit-registrars` (zero drift). 7. VERIFY all assigned scaffold docs are FILLED (not stubs). 8. VERIFY `fabrik destroy --use-state --dry-run` shows clean reversal (deploy-plan Step 7).
**Gate Tier:** 3. **Final Gate:** `python scripts/final_gate.py --systemic --json`
```

### Step 11: Docs-Only Exception

If every scope file is `docs/` / root `*.md` / templates: Gate Tier 1 (coding-time), **Final Gate `python scripts/final_gate.py --json`**; no `[PRIMARY PATH]` test; Doc Sync Matrix + Lessons Learnt still apply.

### Step 12: Present Batch

Present: `## Batch N of M — Parallel Map` (⚡/⛓️), the full tickets, the `[PRIMARY PATH]` Index table (Flow · Test Path · Ticket), then "Batch N of M complete. Next: Batch N+1." Scope drift → `09-revise-requirements-fabrik`; inconsistent specs → `10-cross-artifact-validation-fabrik`.

### Step 13: Cross-Check

Every ticket has ALL fields (no stubs/placeholders/truncation) · Steps use VERB + explicit path + concrete change · outline fields honored (Gate, Depends, Parallel, Docs, Shape) · rule packs AND reference docs injected per category (both columns) · Doc Sync Matrix rows applied · architectural mandates injected · `[PRIMARY PATH]` test on flow-touching tickets · Lessons field on every ticket · parallel map matches outline · no ticket from another batch · **isolation simulation** (read ONLY this ticket + Context Files — can an agent code with no questions? if not, fix) · **no mid-execution planning** (else auto-split into `T?a`/`T?b`) · scaffold code not recreated · last ticket = first ticket depth.

## Does NOT

- Change outline ticket boundaries / move features between tickets — that is `05-ticket-outline-fabrik` (route back on a wrong boundary).
- Execute tickets — that is `07-execute-fabrik` (the coder dispatch); this writes the spec.
- Validate implementation correctness — that is `08-implementation-validation-fabrik`; cross-artifact — `10-cross-artifact-validation-fabrik`.
- Rename/restructure Titles — the outline emits `Tn — <verb>` (or `Tn — Retrofit: <area>` `[canonical: mega/03-expand-epic-files-fabrik § Step 2]`); expand the spec under the existing Title.
- Inject rule packs not in the outline's category table (route back to 05); write commit messages/PRs; run `git commit`/`push` (auto-staged by `final_gate.py` on success).
- Force Epic Closure for a scoped Retrofit (state "skipped (Retrofit — [reason])"); propose `revise-requirements` mid-batch; re-enforce all mandate rows for a Retrofit (only the target area).

## Acceptance Criteria

- Outline consumed as the primary frame (all fields honored); Input Contract validated per scaffold (hard stop on missing).
- Each ticket concrete (real paths, function names, commands); rule packs + reference docs injected per category (both columns).
- Doc Sync Matrix applied; architectural mandates enforced (12-Factor, Concurrency, i18n, Resilience, Shape, Health, M2M).
- `[PRIMARY PATH]` test in feature-ticket scope (real DB, no mocks); Lessons format provided + mandatory field on every ticket.
- DO NOT (3 verbatim + scaffold immutability + project-specific) · Completion Self-Check · Governance Checklist per ticket.
- Parallel map produced; **agent selection per Step 9** — complexity → pool `pick_models("code")` or `claude -p` tier, operator picks the dispatch.
- Epic Closure in the final batch (Tier 3) for delta-feature; OPTIONAL for Retrofit (a skip requires the stated justification).
- Every ticket passes the isolation simulation; too-complex tickets auto-split (`T?a`/`T?b`) with reason; batch progress stated; user confirms.

---

**Next (CC1 pairing, north star § Command-chain build plan):** converge this batch with `/fabrik-workflow-review <batch path> ticket-breakdown` — it forces the no-op (every ticket concrete + isolation-simulation-clean, all outline fields honored, Doc Sync + mandate + test + Lessons criteria injected, agent tier assigned via `pick_models`/`claude -p`, no `DATABASE_SCHEMA.md`, zero hollow citations) before dispatch. Then → `07-execute-fabrik` (dispatch Batch 1's ⚡ tickets to separate coder agents).
