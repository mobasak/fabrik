<!-- ⚠️ FABRIK FACTORY WORKFLOW — IMPLEMENTATION VALIDATION (our own, tool-capable twin of
     08-implementation-validation-fabrik). Run DIRECTLY by our orchestrator agent (Opus 4.8, via the
     driver) — never pasted into a planner GUI.
     THIS IS 07-EXECUTE'S PAIRED REVIEW (north star § Command-chain build plan — CC5): the epic-level
     code-vs-spec pass that catches the cross-ticket regressions a per-ticket converge cannot see. Opus
     orchestrates reviewer agents (find drift) AND coder agents (fix it), loops the implemented epic to a
     its lens-adjudicated exit, and DOES NOT STOP until it validates clean — halting only on the 3 BLOCKED cases. There is NO
     human step between the plan-in gate (passed) and the deploy-out gate (`11-deploy`).

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the validation specs — Decisions Lock (`01-decisions-lock-fabrik`) · Core Flows (`02-core-flows-fabrik`) ·
         Tech Plan (`03-tech-plan-fabrik`) · Deploy Plan (`04-deploy-plan-fabrik`) — the "what was planned"
       · the ticket set (`06-ticket-breakdown-fabrik` output) — every ticket's Scope / Steps / Acceptance
       · the `[PRIMARY PATH]` Index (from `06`) — the test files + the flows they cover
       · the implementation — every file in each ticket's Scope (critical tickets full, simple spot-checked)
       · `compose.yaml` · `Dockerfile` · `.env.example` · `specs/services/<id>.yaml` (shape block)
       · the scaffold docs — `docs/CHANGELOG.md` · `INDEX.md` · `docs/CONFIGURATION.md` ·
         `docs/RESILIENCE.md` · `docs/data-contract.md` · `docs/DEPLOYMENT.md` · `docs/FEATURES.md` ·
         `docs/LESSONS_LEARNT.md`
       · each fixup agent's returned diff + its `final_gate.py --json` output
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Implementation Validation

## Role

The **epic-level implementation-vs-spec review orchestrator** — Opus 4.8, running the driver's loop `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`. After `07-execute-fabrik` converges every ticket per-ticket, this reads the **implemented epic as a whole** and compares it against the planned specs — reasoning about alignment and correctness by reading actual files, never by trusting an agent's self-report. It dispatches reviewer agents to find drift and coder agents to fix it, and **runs the epic to its lens-adjudicated exit — it does not stop and ask** except on the three BLOCKED cases. It writes no code itself; the coder agents do (Step 4).

**Why this runs after execute** `[canonical: 07-execute-fabrik § Step 3 — per-ticket converge is not epic-wide]`: `07` converges each ticket as it lands, but **later tickets can break earlier ones** (regressions), and **cross-ticket patterns are invisible per-ticket** (schema ↔ query mismatches, API contract breaks, scattered convention violations). This command catches those. It is **implementation-vs-spec**; the **spec-vs-spec** cross-artifact pass is `10-cross-artifact-validation-fabrik`.

## Core Philosophy

Two questions, answered by reading code + running commands + reasoning — never by self-report:

1. **Alignment** — does the code match what was planned (Decisions Lock, Core Flows, Tech Plan, Deploy Plan, tickets)?
2. **Correctness** — does it actually work? Bugs, silent failures, security gaps?

- **Every finding cites** `[canonical: 08-implementation-validation-fabrik § Core Philosophy]`: a code location (`file:line`), the spec it should align with (document + section), and a verification (command output or the code you read). A finding without all three is not a finding.
- **Autonomous between the two human gates** `[canonical: north star § Human gates — R14]`. The plan was approved (plan-in gate); the deploy is a separate human gate (`11-deploy-fabrik`). This whole pass runs without a human step — drift → a scoped fixup ticket, re-dispatched, re-reviewed, until the epic validates.
- **The only halt conditions are the 3 BLOCKED cases** `[canonical: CLAUDE.md § Behavior — the three BLOCKED cases]`: **(1)** 3 consecutive same-test failures on one fixup; **(2)** missing infra; **(3)** an unresolvable spec contradiction. On any → Apprise→Telegram `BLOCKED: <what> — searched: <sources> — missing: <need>`, pause THAT thread, continue the rest.

## Processing User Request

### Step 1: Identify Scope

From the argument: **`validate all`** → the entire epic; **`validate T5, T6`** → specific tickets. Confirm `07-execute-fabrik` reported the tickets Done before validating.

**Multi-pass for large epics (>8 tickets)** — one converging run, three lenses layered:

| Lens | Focus |
|---|---|
| **1 — Mechanical** | Read every file in scope. Check against the specs. Surface alignment findings. |
| **2 — Deep** | Read the critical paths (auth, payments, external calls, migrations). Correctness, security, resilience. |
| **3 — Resolution** | Classify findings (Step 5), dispatch fixups (Step 4), re-review — loop to the lens-adjudicated exit. |

Small epics (≤8 tickets): the three lenses combine into one run. Either way the run **loops to the lens-adjudicated exit** (Step 4) — a single pass is never the completion.

**Retrofit-epic adjustments** (Title prefix `Retrofit:` `[canonical: mega-epic-breakdown/03-expand-epic-files-fabrik § Step 2 — Retrofit detected from the Title prefix]`):

- **Success Criteria count** — a Retrofit Decisions Lock is 3–5 SC (not 5–8); flag low-SC as PASS when Retrofit, Blocker only for a Delta-feature with <5 SC `[canonical: mega-epic-breakdown/03-expand-epic-files-fabrik § Success Criteria]`.
- **Deploy Plan absence** — if `04-deploy-plan-fabrik` was SKIPPED per its Retrofit branch, state `Deploy Plan: skipped per Retrofit branch` and proceed; do NOT flag missing.
- **Core Flows absence** — if `02-core-flows-fabrik` produced no flows for a code-only retrofit, do NOT flag missing; verify only the flows it produced.
- **Per-ticket Architectural Mandate scope** — for Retrofit tickets, enforce only the mandate rows touching the retrofit's target area `[canonical: 06-ticket-breakdown-fabrik § Step 4 Retrofit branch — Step-6 mandate rows]` (others inherited from the existing project).
- **Epic Closure / systemic gate** — for Retrofit epics where Epic Closure was SKIPPED at `06`/`07`, do NOT force `final_gate.py --systemic` here; use Tier-2 `--json` — the prior Delta-feature closure already covered the systemic gate `[canonical: 06-ticket-breakdown-fabrik § Step 10]`.

### Step 2: Read Everything (the Reads budget)

Read the **specs** (the "what was planned"): Decisions Lock Success Criteria · Core Flows `[PRIMARY PATH]` markers + error paths · Tech Plan Component Architecture + Data Model + resilience table + Shape Block · Deploy Plan registrar surface + compose contract + env vars · every ticket's Scope/Steps/Acceptance · the `[PRIMARY PATH]` Index.

Read the **implementation**: every file in each ticket's Scope (critical tickets full, simple spot-checked) · the test files named in the Index · `compose.yaml` · `Dockerfile` · `.env.example` · `specs/services/<id>.yaml` shape block · and the scaffold docs the completeness lens (Step 3) checks — `docs/CHANGELOG.md` · `INDEX.md` · `docs/CONFIGURATION.md` · `docs/RESILIENCE.md` · `docs/data-contract.md` · `docs/DEPLOYMENT.md` · `docs/FEATURES.md` · `docs/LESSONS_LEARNT.md`.

### Step 3: Dispatch the Epic-Level Review — reviewer agents (BOTH mechanisms)

**ARM every reviewer FIRST (spec G5/G6 — an un-armed reviewer measured ~0–22% defect recall):** run
`python scripts/review_rubric.py --changed <the epic's implemented diff paths>` and
**inject its output into every reviewer agent's prompt** as the rubric they hunt against. The rubric
carries two layers: **(1) the mandatory-core floor** — `core/35-security-auth` +
`core/25-data-postgres` + `core/30-ops` + all twelve 12-Factor axes — always injected regardless of glob
and never skippable, so the review is never un-armed on the high-blast-radius rules; **(2)** every pack
whose glob matches a changed path (mandate lines only). (No `--workflow` here: this command reviews the
chain's runtime PRODUCTS — epics / artifacts / implemented code — not the 00-N command files themselves;
the `EVALUATION_CHECKLIST_*` authoring-QA injects only when a review's subject IS a command file, e.g.
`/fabrik-workflow-review`.) The whole rubric is computed fresh by the script; nothing is inherited from
the doer. Honesty (L1): the injection STEP is maximally enforced (the rubric is always injected); this
raises compliance probability — it does **not** make compliance guaranteed.

Dispatch the review across the implemented epic through the **`libs/subagents` module** — **BOTH** layers, never either/or `[canonical: core/62-using-subagents.md § Dispatch policy]`:

- **Pool breadth** — `fanout("review", …, mode="read_only")` `[canonical: libs/subagents/agent.py — fanout]` picks family-diverse, flywheel-ranked review models (no default price cap) (`pick_models("review")`) and **auto-records each run to the flywheel**; after you adjudicate, back-fill your 0–5 verdict with `set_quality(r.agent_id, score, project="impl-validation", task_type="review", model=r.model)` `[canonical: libs/subagents/pg_ledger.py — set_quality]` (a `fanout` row left unscored teaches the flywheel nothing; ⚠️ never hand-roll `run_agents`+`record_run` — it no-ops).
- **≥1 native `fabrik-reviewer` on Opus** — the authoritative pass (the pool never runs `anthropic/*`, so a pool-only review has no Opus eyes and is not valid). It owns the high-risk slices (auth / `internal_auth` / migrations / schema / secrets / concurrency).

Each reviewer commits to a lens before seeing the others; **you (Opus) refute/merge/decide**. The lenses:

- **Spec alignment** — for EACH Success Criterion, find the code that delivers it (name file + function); can't find it → **Blocker**. Read each `[PRIMARY PATH]` test — does it exercise the flow end-to-end, or is it a stub that always passes? Are the Tech Plan's components actually built and wired as described? Are all of Core Flows' error scenarios handled?
- **Cross-ticket integration (the star — invisible per-ticket)** — read files from MULTIPLE tickets together: does the DB schema (T1) match the queries (T3)? column names, types. Do internal API calls (T5) match the endpoint signatures (T4)? Do cross-module imports resolve? Are shared env vars used consistently? **Scope creep** — files modified outside every ticket's Scope: reasonable adjacent fix or unauthorized change?
- **Correctness** — silent failures (proceeds without error, produces a wrong result); logic bugs (off-by-one, wrong variable, missing null check); security for user-input services (SQL parameterized? path traversal sanitized? hardcoded secrets? CORS explicit not `*`?).
- **Fabrik convention** — **12-Factor** (config from env, no `localhost` DB string — must be `postgres-main:5432`/`redis-main:6379`; state in Redis/PG/B2 not local FS; structlog/pino not `print`; SIGTERM handled) · **concurrency** (multi-worker/async, no module-global mutable state, no blocking I/O in async) · **i18n** on any GUI surface (locale keys not hardcoded English; `en.json`+`tr.json` key-matched) · **resilience** on external calls (timeout + retry/backoff + graceful degradation; `docs/RESILIENCE.md` filled, not the empty template) · **M2M auth** (`X-Internal-Token` present; `hmac.compare_digest` constant-time) · **shape ↔ code** (`specs/services/<id>.yaml` shape block matches what the code actually does — mismatch = bug) · **deployment** (compose has resource limits + `platform: linux/amd64` + healthcheck `start_period` + fabrik network + Traefik labels; Dockerfile `-slim-bookworm` multi-stage; `.env.example` lists every env var the code references).
- **Documentation completeness** — the scaffold docs are FILLED, not empty templates: `CHANGELOG.md` (one entry per ticket under `## [Unreleased]`) · `INDEX.md` (all files) · `docs/CONFIGURATION.md` (every env var) · `docs/FEATURES.md` · `docs/RESILIENCE.md` (dependency inventory) · `docs/data-contract.md` (frozen DB field/enum/model contract, if a DB project) · `docs/DEPLOYMENT.md` (compose/deploy setup, deployed types) · `docs/LESSONS_LEARNT.md` (entries where triggers fired, numbering sequential). **Per-ticket Lessons Learnt** — every ticket's Completion Self-Check states `Lessons Learnt:` (an entry or `none`); **silence = Blocker**.

### Step 4: Converge to a No-Op — fixup, don't stop

Classify every surviving finding (Step 5), then handle it autonomously — everything short of a BLOCKED case:

- **Mechanical / correctness / drift** (missing timeout, wrong column name, missing CHANGELOG entry, shape mismatch, silent failure) → create a **scoped fixup ticket** (one fix per issue, NOT a re-do) carrying the finding's `file:line` + spec ref as context, and **dispatch it to a coder agent** — the pool `pick_models("code")` via `fanout` (flywheel-ranked, records the flywheel) for simple mechanical fixes, or **`claude -p opus`** in an isolated git worktree for a high-risk fix (auth/schema/migrations/concurrency/secrets) `[canonical: 06-ticket-breakdown-fabrik § Step 9 — the coder tiers]`. Re-read the affected files + re-review to confirm resolution.
- **Product misalignment** (code deviates from Decisions Lock / Core Flows intent — not a code bug but a requirements gap) → **route to `09-revise-requirements-fabrik`**; do NOT edit the Decisions Lock / Core Flows / Tech Plan here.
- **3 consecutive same-test failures on one fixup** → **BLOCKED case 1** → Telegram, pause THAT thread, continue. **Missing infra** → **BLOCKED case 2**. **Unresolvable spec contradiction** → **BLOCKED case 3** → route to `09`.

**LOOP:** every fixup dispatched → re-reviewed → re-classified — **until every lens of this command's review structure carries an adjudicated PASS-with-evidence, with zero unresolved findings** (the lens/dimension breakdown above is the single source of the lens set). An empty round proves that *sample* found nothing, not that nothing exists — the lens verdicts are the exit, not a lucky quiet pass. **Minimum two full rounds, ALWAYS** (the round that first completes the lenses is never the exit round — a fresh round must re-adjudicate them); the pass that produced a fixup is never the last look at the lenses it touched. **Hard cap 20 rounds:** still churning at the cap → STOP and declare the residual (which lenses, what risk) in the report instead of looping on. Keep the `found:`/`fixed:` ledger per round (`found` counts refuted candidates too).

### Step 5: Classify + Present

| Severity | Meaning | Action |
|---|---|---|
| **Blocker** | Broken core, security hole, missing Success Criterion, gate failing | Fixup ticket → coder (Step 4). |
| **Bug** | Logic error, broken flow, missing/stub test, wrong behavior | Fixup ticket → coder. |
| **Edge Case** | Unhandled Core Flows scenario | Fixup if cheap + clearly in-scope; else a Telegram note for the operator. |
| **Technical Drift** | Deviated from Tech Plan, technically sound | Note it (Telegram); the Tech Plan re-freeze routes to `09-revise-requirements-fabrik` (spec edits live there, never a direct edit here). |
| **Product Misalignment** | Deviated from Decisions Lock / Core Flows | Route to `09-revise-requirements-fabrik`. |
| **Validated** | Meets criteria, aligned, correct | Confirm. |

Post the running result to the Telegram digest (`Validation: 10 clean / 2 fixups → re-review`), not a per-finding human prompt.

### Step 6: Systemic Gate + Handoff

When the epic-level review reaches its lens-adjudicated exit: run **`final_gate.py --systemic --json`** `[canonical: scripts/final_gate.py — Tier-3 repo-health]` to prove nothing regressed epic-wide (⚠️ **except** a Retrofit epic where Epic Closure was skipped → Tier-2 `--json`, per Step 1). Confirm `status:"success"`, then hand off: the next step is `10-cross-artifact-validation-fabrik` (the spec-vs-spec integration review), then the **deploy-out human gate** → `11-deploy-fabrik`. This command never runs `fabrik apply`.

## Does NOT

- **Write code itself** — coder agents implement the fixups (Step 4 creates the scoped fixup + dispatches it: pool `pick_models("code")` or `claude -p`). The review finds + orchestrates; it does not hand-edit the implementation.
- **Re-run the ticket execution** — that is `07-execute-fabrik` (the full coder dispatch + per-ticket converge). `08` validates the finished epic and dispatches *scoped fixups*, not a re-do.
- **Validate cross-artifact (spec-vs-spec) consistency** — that is `10-cross-artifact-validation-fabrik` (across Decisions Lock, Core Flows, Tech Plan, Deploy Plan, ticket specs). `08` is implementation-vs-spec.
- **Change the Decisions Lock / Core Flows / Tech Plan / Deploy Plan** — Product Misalignment routes to `09-revise-requirements-fabrik`, never a direct edit here.
- **Stop and wait for a human on a finding** — drift is handled by fixup + re-dispatch + re-review; only the 3 BLOCKED cases pause a thread (via Telegram).
- **Trust agent self-reports** — every finding needs `file:line` + spec ref + verification (Core Philosophy). A coder's "gate passed" is a claim; the returned `final_gate.py --json` `status:"success"` is the proof.
- **Force `final_gate.py --systemic` for a Retrofit epic where Epic Closure was skipped** at `06`/`07` — use Tier-2 `--json` there (Step 1).
- **Flag a Retrofit Decisions Lock with 3–5 Success Criteria as under-specced** — that is the Retrofit default; low-SC is a Blocker only for a Delta-feature with <5 SC.
- **Execute `fabrik apply` / deploy** — that is `11-deploy-fabrik` (the deploy-out gate). `08` is the PRE-deploy epic-level review.
- **Run `git commit` / `push`** — `scripts/final_gate.py` auto-stages on success (CLAUDE.md HARD STOPS); the coder fixups merge via `07`-style worktree→default-branch.

## Acceptance Criteria

- Every file in scope read — critical tickets fully, simple tickets spot-checked.
- Spec alignment verified: every Success Criterion traceable to a named file + function; each `[PRIMARY PATH]` test read + confirmed to exercise a real path (not a stub).
- **Cross-ticket integration verified** (schema ↔ queries, internal-API contracts, cross-module imports, shared env vars) — the regressions a per-ticket converge can't see.
- Correctness (silent failures, bugs, security), 12-Factor, concurrency, i18n, resilience, M2M auth, shape ↔ code, and deployment readiness all verified by reading.
- Documentation completeness verified (all scaffold docs filled — `data-contract.md`/`DEPLOYMENT.md`, not the archived `DATABASE_SCHEMA.md`/hub-only `DEPLOYMENT_ARCHITECTURE.md`); per-ticket Lessons stated (silence = Blocker).
- Review dispatched through `libs/subagents` — **pool `fanout("review")` recording the flywheel AND ≥1 native `fabrik-reviewer` on Opus** — with Opus refuting/merging/deciding.
- Findings handled **autonomously**: scoped fixup tickets dispatched to coders (pool `pick_models("code")` or `claude -p`), re-reviewed, **looping to the lens-adjudicated exit (min-2 rounds, cap 20)**; Product Misalignment routes to `09`; only the 3 BLOCKED cases pause (Telegram).
- The lens-adjudicated exit is followed by `final_gate.py --systemic --json` `status:"success"` (Tier-2 for a skipped-closure Retrofit); then handoff to `10` → the deploy-out gate. Never runs `fabrik apply`.

---

**Next (CC1 pairing, north star § Command-chain build plan):** `08` IS `07-execute`'s paired review `[canonical: north star § Command-chain build plan — CC5, "08 is 07-execute's review"]`. After the epic validates to its lens-adjudicated exit, the chain continues to `10-cross-artifact-validation-fabrik` (the spec-vs-spec integration review), then the **deploy-out human gate** → `11-deploy-fabrik`. A Product Misalignment routes to `09-revise-requirements-fabrik` and re-enters the chain.
