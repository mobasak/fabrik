---
description: Full-project adversarial code review + fix — discover units → parallel read-only review waves → triage → risk-ordered serial fixes with regression tests → incremental convergence, with a coverage ledger. TRIGGER — EN: "audit the whole repo", "sweep the entire project for bugs"; TR: "tüm repoyu denetle", "projenin tamamını incele" — fires for a whole-repo sweep, not one diff. SKIP: a single diff/PR's changed-surface gate (→ /fabrik-review). Stage: gate.
argument-hint: "[subsystem/dir/risk-tier to scope — omit for the whole repo]"
---

FULL PROJECT CODE REVIEW

Adversarially review — and fix — this Fabrik project's codebase using multiple
subagents. Orchestrate in phases; do not free-form. Obey this project's CLAUDE.md /
AGENTS.md. If an argument was given, scope the whole run to it: `$ARGUMENTS` (a
subsystem, dir, or risk-tier); otherwise review the ENTIRE repo.

{{include:term-coverage}}
{{include:grounding-code}}
## PHASE 0 — DISCOVER THIS PROJECT (you, first — do NOT assume conventions)

Read `project.yaml::type` (one of the real `SCAFFOLD_TYPES`: python-api / python-api-gpu /
saas-skeleton / node-api / file-api / file-worker / wordpress / docusaurus /
chrome-extension / mobile-app / desktop-app / static-site; the hub and fabrik-lib have NO project.yaml — there, skip this step and detect surfaces directly). Run `python scripts/select_rules.py` (if present) and READ
every ACTIVE pack + every AVAILABLE pack matching a unit — the `.windsurf/rules` packs are
AUTHORITATIVE on *how* code must be written (conflict order: rule pack > ticket). Detect
which surfaces EXIST, hence which review axes apply: `compose.yaml` (deployable VPS
service → deploy invariants apply), the DB migrations dir, `specs/services/*.yaml`
(usually ABSENT — only apply the shape axis if it exists), a web build (vitest/tsc), and
the FABRIK-SYNCED set (manifest `/opt/fabrik/scripts/fabrik_synced_manifest.py` + the
`.gitignore` "Fabrik-synced" block — these files are REVIEW-ONLY, never edited locally).

Partition the codebase into INDEPENDENT review units (by subsystem/dir so two units never
share files) — **fine-grained: a large repo is DOZENS of units, not a handful.** Size each
unit to what one reviewer holds in context (a file / package / the changed surface), not
coarse buckets; more, smaller units = better recall AND more parallelism. Risk-rank by
blast radius (money / auth / data-integrity / domain-correctness highest). **Emit a COVERAGE LEDGER and PERSIST it to the scratchpad as
the single source of truth** for all later phases: `unit → files → risk → fabrik-synced?
→ which axes apply → assigned`. If `$ARGUMENTS` scoped the run, restrict the ledger to it
and say so.

## PHASE 1 — PARALLEL ADVERSARIAL REVIEW (read-only)

One reviewer per unit, READ-ONLY — no edits, so parallel workers can't collide. **Scale the
fan-out to the repo — a big repo is 20+ workers, not 2–3.** Dispatch the bulk of units as
**cheap flywheel-ranked pool workers** via
**`fanout("review", units=[<unit code inlined> …], mode="read_only", max_concurrency=…)`** —
it picks family-diverse, flywheel-ranked models (no default price cap; `max_cost_per_mtok=`
opt-in) and sets `tools_enabled=False`+`allow_ungrounded=True` for the single-shot
reviewers. The mass pool fan-out is the **default worker** for gradeable fan-out (per
`62-using-subagents.md` § Dispatch policy; see § Subagents) — **reserve native Claude
finders for the highest-blast-radius units** (money / auth / data-integrity — the
authoritative pass). `fanout` **auto-records each worker UNSCORED** and returns
`(results, results_table)` → **back-fill**
`set_quality(r.agent_id, <0–5>, project="repo-review", task_type="review", model=r.model)`
per worker (⚠️ never `record_run` — it silently no-ops). **Batch the fan-out in WAVES by
risk tier (cap concurrency via `max_concurrency`; don't spawn all 20+ at literally once)** —
highest-blast-radius units first. Each reviewer applies the `/fabrik-review` adversarial
methodology to its unit PLUS everything it calls / is called by, hunting these failure
classes:

- CORRECTNESS/LOGIC: off-by-one, null/empty/None, idempotency, effective-dating/ordering,
  error/edge paths, concurrency & transaction atomicity, resource cleanup,
  precision/timezone/encoding.
- DOMAIN SAFETY (fail-open vs fail-closed): identify THIS project's "never silently wrong
  in the unsafe direction" invariant (e.g. never under-charge money / understate a levy,
  never over-grant a permission, never serve stale-as-fresh, never drop a job) and prove
  the code cannot violate it.
- SECURITY: auth, cross-tenant/RLS isolation (every read/write scoped to the authed
  principal; service-role paths can't leak across tenants), secret handling
  (`os.getenv("KEY","default")`, no hardcoded secrets).
- RULE-PACK COMPLIANCE: deviations from the ACTIVE `.windsurf/rules` packs — cite
  pack:rule. A finding that contradicts an ACTIVE pack is by definition a defect.
- PORTABILITY (Fabrik 3-env invariant — only if a service scaffold): the SAME code must
  run unmodified in local dev (`.venv`, PG localhost, `.env`) · VPS Docker
  (`postgres-main:5432` / `redis-main:6379`, compose) · managed env (env vars). Flag
  hardcoded localhost, `DB_HOST=localhost`, env-specific branches.
- DEPLOY/COMPOSE INVARIANTS — ONLY IF `compose.yaml` EXISTS: every service has
  `deploy.resources.limits.memory` (OOM guard); on the `fabrik` network, no host-bound
  ports (Traefik routes); health endpoints (`/health /healthz /metrics /api/health`)
  NEVER behind auth; health/monitoring targets use stable Docker DNS (compose service
  name / registered alias), never per-redeploy UUIDs; health checks hit real deps. Phase 0's
  surface detection governs (chrome-extension, mobile-app, static-site and docusaurus all scaffold a
  compose.yaml; only desktop-app has none).
- SPEC↔CODE — ONLY IF `specs/services/*.yaml` EXISTS (usually it does NOT): code adding a
  DB call ⇒ `shape.needs_database:true`, cache ⇒ `needs_cache`, `/metrics` ⇒
  `exposes_metrics`, search ⇒ `has_search_feature`, admin UI ⇒ `is_admin_dashboard`. If
  no specs dir, record "N/A — no spec contract in this project."
- SPEC/PLAN↔CODE deviations generally (the written spec can be wrong — judge against
  intent).

**Prove before you flag, WITHOUT breaking read-only** (this obligation falls on the NATIVE finders and on YOUR triage — a single-shot `read_only` pool worker has no shell, so its findings arrive unproven and get verified at Phase 2): reproduce each suspected bug with
a THROWAWAY repro in the scratchpad or a read-only execution — NOT a committed test and
NOT an edit to any repo file (the kept regression test is written later, in Phase 3).
Return STRUCTURED findings only: `{file:line, failure_class, severity:
correctness|security|style, reproduction, root-cause, proposed_fix, confidence,
fabrik_synced: yes/no}`. A unit that finds nothing must still enumerate exactly what it
inspected (files × failure classes × rule packs) — empty claims without coverage evidence
don't count. Update the ledger with each unit's coverage as waves complete.

## PHASE 2 — MERGE, DEDUPE, TRIAGE (you)

Consolidate all units; dedupe cross-unit findings; re-verify each to drop false positives;
keep ONLY confirmed correctness/security for fixing (style → a separate list); rank by
severity × blast radius. Produce the ranked fix list and set a **fix budget**: the top
severity×blast-radius tier is fixed THIS run; the long tail is handed off as a tracked
backlog (Phase 4 output), not force-fixed in one exhausting turn.

## PHASE 3 — PROVE + FIX

**Serialized in the working tree by DEFAULT** (parallel worktree-isolated subagents ONLY
when that isolation is explicitly set up — never two agents on one file at once). Fix in
risk order, honoring the Phase-2 fix budget — top tier now; fold the remainder into the
tracked backlog rather than rushing unsafe fixes. For each confirmed bug: write the failing
test FIRST (red), then fix it, keep the test as a regression guard (verify red→green).
**A test that passes because the environment cannot express the
failure has proven nothing** — "it passed locally" is not evidence when local is the one
place the bug is unreachable (a superuser role for an RLS bug, one tenant for an isolation
bug). Reach for the missing constraint in a throwaway/ephemeral instance you own; **never**
degrade shared or paid infrastructure (`postgres-main`/`redis-main`, the VPS fleet, real
vendor quota) to manufacture a red — if that is the only way to see it, say so in the
finding instead. Stay in scope.

CONSTRAINTS: if this is a SHARED multi-lane worktree, do NOT edit other lanes' files; do
NOT touch deps files unless authorized; and NEVER edit a FABRIK-SYNCED file locally (it is
overwritten on the next governance sync — `scripts/sync_enforcement_to_projects.py`, run by the pre-commit hook — gate-enforced) — if a synced file has a real bug,
fix it in `/opt/fabrik/<path>` (if correct for ALL projects) or propose it upstream, and
note that in findings; never fork it here. Schema changes = a NEW tracked migration
applied by the project's migration runner (idempotent), never hand-DDL. Commit ONLY by
explicit pathspec, never `git add -A`. Re-run `final_gate.py` after each fix cluster
(`--lean` for fast mid-loop self-review only · `--json` the FULL Tier-2 completion gate · `--systemic` Tier-3 repo-health only (docker/ports/docs sprawl — narrower, NOT a superset; completion still needs `--json`)) — fixes regress;
a green gate is necessary but NOT proof of correctness (it doesn't test logic), and
known-environmental reds (e.g. Traefik/templates checks on a repo with no templates dir)
don't count as new failures.

## PHASE 4 — CONVERGE (incremental)

After each fix cluster, re-review ONLY the CHANGED surface + its callers/callees (fixes
create new surface) and update the ledger — do NOT re-run all units from scratch every
iteration. When the incremental re-reviews stop producing findings, run ONE final,
demonstrably-thorough FULL certification pass across all in-scope units — a complete re-adjudication of the
**Coverage Checklist (unit × failure-class × rule-pack)**. You EXIT when, after that pass, **every checklist
row is adjudicated** (CLEAN / FIXED / REFUTED — the only standing residual being the explicitly-tracked
deferred backlog) and every class the certification's own fixes touched has been re-checked. If certification
surfaces anything new, adjudicate it (fix, or budget it into the backlog) and re-certify the touched classes
— with no round ceiling; a finding stuck after 3 fix attempts is BLOCKED-escalated per the Termination
contract while the rest keeps converging. Do not claim the exit without embedded proof: the adjudicated Coverage Checklist + the verbatim `final_gate.py --json` success
+ each fix's regression test. Run the FULL test suite (pytest and, if a web surface was touched, vitest/tsc)
— not just the in-scope tests.

**`found` counts every candidate a unit-reviewer RAISED — including ones you drop as false positives in
triage** (a certification pass that raised 3 and refuted all 3 still re-opens the touched classes). Run every
owed pass **UNPROMPTED** — *"already reviewed per-unit," "I triaged them all away," "obviously clean"* each
mean: run the pass.

## DEPLOY / FABRIK LIFECYCLE — out of scope for this run

Do NOT deploy. For a VPS service scaffold, deploying is a human-gated step = commit → PUSH
(the VPS `git pull`s from the GitHub remote, so push-before-redeploy is mandatory) →
`fabrik redeploy` (or `fabrik apply` for spec/registrar/compose changes); migrations are
applied separately. Other scaffold types deploy differently (extension store, app bundle,
package publish). The review MUST assess deploy-READINESS against whichever invariants
apply and list any blocker — but state the deploy steps as a RECOMMENDATION and let the
owner run them.

## OUTPUT

The coverage ledger; per-unit findings with verdicts; the fixes with their regression
tests; a rule-pack & (where applicable) Fabrik-invariant compliance summary; the
DEFERRED-BACKLOG list (fixes budgeted out of this run, ready to fold into
`docs/development/plans/*`); and an explicit RESIDUAL-RISKS list (incl. any
Fabrik-synced-file bugs needing an upstream fix, and any deploy blockers). When unsure
whether something is a bug, surface it. Scale effort to risk — exhaustive on
money/auth/domain-correctness units, proportionate on low-blast-radius ones — and log
anything you deliberately skip.

{{include:subagents-core}}
