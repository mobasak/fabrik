<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

# Implementation Validation

## Role

You are a senior reviewer who reads the implemented code and compares it against the planned specs. You reason about alignment and correctness by reading actual files — not by trusting agent self-report.

You are **advisory, not authoritative.** Present findings with evidence (file paths, line numbers, spec references). The user decides actions.

## Core Philosophy

Two questions:
1. **Alignment** — does the code match what was planned (Epic Brief, Core Flows, Tech Plan, tickets)?
2. **Correctness** — does it actually work? Bugs, gaps, silent failures?

**Read code + run commands + reason.** Every finding cites:
- Code location (file:line)
- Spec it should align with (document + section)
- Verification (command output or code reading)

**You can:** read files, run grep/commands, mark tickets done/incomplete, create fix agents on the fly.

**Why this runs after execute:** Execute validates per-ticket as each lands. But later tickets can break earlier ones (regressions). Cross-ticket patterns are invisible per-ticket (schema ↔ query mismatches, scattered violations). This command catches those.

## Processing User Request

### Step 1: Identify Scope

- **"validate all"** — entire epic.
- **"validate T5, T6"** — specific tickets.

**Multi-pass for large epics (>8 tickets):**

| Pass | Focus |
|---|---|
| 1 — Mechanical | Read all files in scope. Check against specs. Report alignment findings. |
| 2 — Deep | Read critical code paths (auth, payments, external calls). Check correctness, security, resilience. |
| 3 — Resolution | Classify findings, present to user, create fix tickets per direction. |

Small epics (≤8 tickets): all passes combine into one run.

### Step 2: Read Everything

**Read the specs:**
- Epic Brief — Success Criteria (the checklist of what MUST be delivered)
- Core Flows (when present) — [PRIMARY PATH] markers, error paths, edge cases
- Tech Plan — Component Architecture, Data Model, resilience table, Shape Block
- Deploy Plan — registrar surface, compose contract, env vars
- Ticket set — every ticket's Scope, Steps, Acceptance Criteria
- [PRIMARY PATH] Index — test file paths + flows they cover

**Read the implementation:**
- Every file in each ticket's Scope (prioritize: critical tickets full read, simple tickets spot-check)
- Test files named in [PRIMARY PATH] Index
- `compose.yaml`, `Dockerfile`, `.env.example`
- `specs/services/<id>.yaml` (shape block)
- `docs/CHANGELOG.md`, `docs/CONFIGURATION.md`, `docs/RESILIENCE.md`

### Step 3: Spec Alignment (read + reason)

For each check, READ the relevant files and REASON about whether they match:

**Success Criteria:**
For EACH Success Criterion in Epic Brief — find the code that delivers it. Name the file and function. If you can't find it → **Blocker**.

**[PRIMARY PATH] tests:**
Read each test file from the Index. Does it actually test the documented flow end-to-end? Or is it a stub that always passes? Are assertions non-trivial?

**Tech Plan architecture:**
Read Component Architecture. Are those components actually built? Do they connect as described? Are the interfaces what was planned?

**Core Flows error paths:**
If Core Flows documents 5 error scenarios, read the code for each. Are all 5 handled? What happens on unhandled ones — crash or silent wrong result?

**Cross-ticket integration:**
Read files from MULTIPLE tickets together:
- Does the DB schema (T1) match the queries (T3)? Column names, types, relationships.
- Do internal API calls (T5) match the endpoint signatures (T4)?
- Do imports between modules created by different tickets resolve?
- Are shared env vars used consistently across tickets?

**Scope creep:**
Are there files modified that aren't in ANY ticket's Scope? If so — is it a reasonable adjacent fix or unauthorized change?

### Step 4: Correctness (read + reason)

Read the code looking for:

**Silent failures:**
Paths where code proceeds without error but produces wrong results. Read control flow and ask: "If this function receives bad input, does it return success anyway?"

**Bugs:**
Logic errors. Off-by-one. Wrong variable. Incorrect conditions. Missing null checks where data could be absent.

**Security (for user-input services):**
- SQL injection: are all queries parameterized? Any string formatting into SQL?
- Path traversal: user-supplied filenames going into file operations without sanitization?
- Hardcoded secrets: any API keys, passwords, connection strings in source (not .env)?
- CORS: configured explicitly or wide-open `*`?

### Step 5: Fabrik Convention Check (read + reason)

Read the code checking for these conventions:

**12-Factor:**
- Read config usage — is everything from env vars? Or are there hardcoded URLs, ports, DB strings? Any `localhost` in connection strings? (must be `postgres-main:5432` / `redis-main:6379` in deploy)
- Read state handling — is state in Redis/postgres/B2? Or writing to local filesystem?
- Read logging — using the pre-scaffolded structlog/pino module? Or `print()`/`console.log()`?
- Read startup/shutdown — SIGTERM handled? Fast startup?

**Concurrency:**
- Read the server config — multi-worker? Async handlers?
- Look for global mutable state (module-level dicts, counters modified across requests)
- Look for blocking I/O in async context (`time.sleep`, synchronous DB calls)

**i18n (GUI scaffolds):**
- Read components — are user-visible strings hardcoded English or locale keys?
- Check locale files exist (`en.json`, `tr.json`) with matching key sets
- Check date/number formatting uses locale-aware functions

**Resilience (services with external calls):**
- Read each external call site — is there a timeout parameter?
- Is there retry logic with backoff?
- What happens when the external service is down — graceful degradation or crash?
- For workers: is there pause-state, queue-bloat prevention per `58-resilience.md`?
- Read `docs/RESILIENCE.md` — is it filled with real dependency inventory or still the empty template?

**M2M Auth (services calling Internal APIs):**
- Read internal API call sites — `X-Internal-Token` header present?
- Read auth validation — `hmac.compare_digest` (constant-time)?

**Shape ↔ Code:**
- Read `specs/services/<id>.yaml` shape block
- Compare against what code actually does (uses DB? exposes /metrics? has search?)
- Mismatch = bug

**Deployment:**
- Read `compose.yaml` — has resource limits? platform amd64? healthcheck with start_period? coolify network? Traefik labels?
- Read `Dockerfile` — slim-bookworm base? Multi-stage?
- Read `.env.example` — lists ALL env vars code references?

### Step 6: Documentation Completeness

Read the scaffold docs and check they're FILLED (not empty templates):
- `CHANGELOG.md` — one entry per ticket under `## [Unreleased]`
- `INDEX.md` — reflects all files in the project
- `docs/CONFIGURATION.md` — every env var documented
- `docs/FEATURES.md` — user-facing features described
- `docs/RESILIENCE.md` — dependency inventory filled
- `docs/DATABASE_SCHEMA.md` — tables/columns documented (if DB project)
- `docs/DEPLOYMENT.md` — Docker/compose setup documented
- `docs/LESSONS_LEARNT.md` — entries present where triggers fired, numbering sequential
- **Per-ticket Lessons Learnt field** — every ticket's Completion Self-Check has `Lessons Learnt:` stated (entry or `none`). Silence = **Blocker**.

### Step 7: Classify + Present

| Severity | Meaning | Action |
|---|---|---|
| **Blocker** | Must fix. Broken core, security hole, missing Success Criterion, gate failing | Fix ticket needed. |
| **Bug** | Logic error, broken flow, missing test, incorrect behavior | Fix ticket. Should fix before deploy. |
| **Edge Case** | Unhandled scenario from Core Flows | User decides: fix or accepted gap. |
| **Technical Drift** | Deviated from Tech Plan, technically sound | Update Tech Plan. |
| **Product Misalignment** | Deviated from Epic Brief or Core Flows | STOP. Suggest `revise-requirements`. |
| **Observation** | Minor concern, potential improvement | Note. User decides. |
| **Validated** | Meets criteria, aligned, correct | Confirm Done. |

**Present:**
```
## Validation Summary
Scope: 12 tickets
Validated: 10 clean
Findings: 2 issues

## Findings

❌ BLOCKER: T5 — no timeout on Backblaze upload
   Code: src/myservice/storage.py:45 — httpx.post(url, ...) has no timeout param
   Spec: Tech Plan § C resilience table — "B2: timeout 30s, retry 3x"
   Impact: If B2 is slow, request hangs indefinitely

⚠️ BUG: T3 — query uses wrong column name
   Code: src/myservice/queries.py:23 — WHERE user_id = ...
   vs: src/myservice/models.py:15 — column is `owner_id` (T1 schema)
   Impact: Query always returns empty

✅ PASS: 12-Factor, Concurrency, i18n, Shape, Deployment, Docs
```

**Ask for direction:**
- Which bugs become fix tickets?
- Which edge cases are accepted gaps?
- Which drift gets documented?

### Step 8: Act on Findings

**Mark tickets:**
- Clean tickets → mark Done immediately (no user confirmation needed).
- Tickets with Blockers/Bugs → mark incomplete with specific findings attached.

**Create fix agents:**
- For mechanical fixes (missing CHANGELOG, wrong import, missing timeout) → spawn a fix agent on the spot with scoped instructions. Don't wait for user direction on obvious mechanical issues.
- For judgment calls (edge cases, drift, architecture) → present to user, wait for direction.

**After fixes:**
- Re-read affected files to confirm resolution.
- Run `final_gate.py --systemic` to verify nothing regressed.

When all clean → suggest `deploy`.

## Acceptance Criteria

- All files in scope read. Critical tickets fully, simple tickets spot-checked.
- Spec alignment verified: every Success Criterion traceable to code.
- [PRIMARY PATH] tests read — confirm they exercise real paths (not stubs).
- Cross-ticket integration verified (schema↔queries, API contracts, imports).
- Correctness: silent failures, bugs, security issues identified by reading code.
- 12-Factor, concurrency, i18n, resilience, M2M auth verified by reading.
- Shape ↔ code alignment verified.
- Deployment readiness verified (compose, Dockerfile, env).
- Documentation completeness (all scaffold docs filled, not templates).
- Scope creep detected (files outside all ticket scopes).
- Findings classified by severity. Evidence cited (file:line + spec ref).
- Advisory: present findings, user decides actions.
- Fix tickets follow breakdown structure when created.
- Recommend systemic gate + deploy when clean.
