# Plan — Fabrik Operating Model (one-operator build factory)

**Owner:** hub AI — this session's stream.

**Status:** CONVERGED (2026-06-30) — re-scoped 2026-07-12. **⚠️ 2026-07-12 operator-directed re-scope:** the
operator confirmed that **every build in this repo has real, already-waiting customers** — this is *not* a
speculative "launch many bets, most fail, select winners by who pays" factory. So the entire
**monetization + selection/graduate/retire-by-revenue premise has been REMOVED**: §Payments, the brake's
selection-validity primitive, the whole traction/lifecycle (`fabrik_projects` + `untested`/`kill_candidate`/
`graduated` states + the retire-refund engine), "monetize-by-default"/"cattle-not-pets" doctrine, and the
Day-12 retirement engine are all gone. **What remains** — and what this plan now is — is the operator-attention
machinery that stands on its own for a builder serving known customers: the **do-not-die safety floor**, the
**`fabrik launch` build→deploy automation**, **agent-enablement** (self-verifying capability index), and the
**operator-absent survival layer**. The pre-2026-07-12 convergence history (five adversarial passes + the
payment-facts fetches) is summarized, not reproduced, in `## Self-audit` — the payment-specific passes are
now moot. Counts re-grounded 2026-07-12 (55 modules / 71 dirs / 20 scaffold / 12 workflows; registrars 10 +
drivers 27 stable). **NOTE:** the design spec `docs/superpowers/specs/2026-07-12-empire-operating-model-design.md`
still carries the old monetization premise and needs the same re-scope (flagged to the operator).

## What this builds

A **one-operator build factory**: you + AI stand up new projects — each with **real customers already waiting**
— and keep them running at near-zero *per-project* attention. The binding constraint is your attention, not
code or servers, so the KPI is that standing up project #50 costs no more of your time than #5.

Concretely, you get:
- **`fabrik launch <idea|spec>`** — one command: spec → repo (the one canonical scaffold) → deploy → DNS → DB →
  (auth if the product needs it) → watchdog → registered, in ≤2h, ≤30 min of your time.
- **A brake** that makes running fast safe: an **attention budget** that *blocks* new launches when you're over
  it, and **radical simplification** (one canonical scaffold / driver / registrar / DB path).
- **Agent enablement** — any AI entering Fabrik reads a generated, self-verifying capability index and acts
  without human onboarding (the substrate that keeps per-project attention near zero).
- **A survive-absence layer** — spend kill-switch, real restore drills, and an operator-absent state machine
  that narrows autonomy safely if you go dark — **keeping customer-facing services up**, never deleting data
  or widening its own authority.

It is **not** a SaaS/PaaS to sell (monetizing Fabrik itself competes for the attention this protects).

**Goal.** A one-operator, AI-managed **build factory**: stand up customer-ready projects at near-zero marginal
operator-attention and keep them healthy. Co-equal second goal: any AI agent entering Fabrik **knows** its
capabilities/infra/rules and can **act** on them with zero human onboarding — the substrate that keeps
per-project attention near zero.

**KPI.** Per-project marginal operator-attention → 0 (standing up project #50 costs no more human time than #5).

**Build status legend:** *(exists)* = grounded in current code (see Evidence); *(to-build)* = verified absent
today, this plan creates it; *(extends X)* = new behavior on an existing asset. Every step lists the exact
command + expected result; for `(to-build)` steps the gate is that step's acceptance test (it runs once the
step's code lands — the §Keystone/§brake CLI verbs are all `(to-build)`).

## Keystone — `fabrik launch <idea|spec>` *(to-build; verified absent — no `launch` command in `src/fabrik/cli.py`)*

One command: spec → repo (the one canonical scaffold) → deploy *(extends `fabrik apply`)* → DNS → DB →
**auth if the product needs it** *(vendor `fastapi-user-auth/`)* → watchdog sidecar *(exists:
`src/fabrik/drivers/watchdog.py`)* → control-plane registration. Target: ≤30 min operator time, ≤5 manual
steps, ≤2h spec→live URL. It is **integration of existing assets** (20 scaffold/template dirs, 55 lib modules
per the fabrik-lib README table — 71 dirs incl. non-module dirs; 27 drivers, 10 registrars — live counts
2026-07-12; the generated index §Agent-enablement is canonical), **vendor-compose not invention** — the new
`fastapi-user-auth/` etc. modules do the per-product plumbing.
**Validation gate:** `fabrik launch examples/smoke.yaml && curl -fsS https://<slug>.<domain>/health` → 200
within 2h, operator-minutes logged ≤30.

## The brake (build BEFORE running fast) *(to-build)*

The factory creates faster than it can contain or maintain unless two primitives exist first:

1. **Attention budget.** Every operator touch logs to a new `attention_events` table on `postgres-main`
   *(to-build; verified absent — 0 refs in `src/`,`scripts/`)*. `fabrik launch` calls `launch-gate check`
   first → **BLOCK** if trailing-7d operator-minutes > 5h, or any unresolved uptime- or data-impacting
   incident exists. Cap: ≤2 launches/week until the per-project exception rate (operator-touches ÷
   active-projects ÷ week) proves lower. *(The 5h cap and the exclusion list are config, not hardcoded.)*
   **Gate:** after `fabrik attention log --minutes 360` (seeds 6h in the trailing 7d),
   `fabrik launch-gate check` exits **1** and prints `BLOCK: attention_minutes_7d=6.0 > cap=5.0`.
2. **Radical simplification.** One canonical scaffold; one default driver/registrar/DB path; deterministic
   healthchecks (restart/rollback/mark-degraded) before any AI self-heal.
   **Gate:** `ls templates/` shows the archived set moved out; one canonical scaffold remains as the
   `fabrik launch` default.

*(The operational project registry is the existing `data/projects.yaml` deploy registry — `deploy/domain/ports/
last_apply_status/registrars_applied/…`. No separate traction/selection store: there is no "select winners by
revenue" step in this model.)*

## Agent enablement *(to-build: index + skills; `.claude/skills` and `.claude/agents` verified empty)*

- **Capability index — generated *and verified*.** Built from the live system (`fabrik --help` + subcommands,
  `src/fabrik/drivers/`, `scripts/`, `specs/`, `/opt/fabrik-lib/README.md`, and live `docker ps` across
  vps1/2/3) into `docs/CAPABILITIES.md` + a JSON the router reads *(to-build; verified absent)*. Single
  self-describing source a cold agent reads first; regenerated by the **daily pipeline** *(exists:
  `scripts/wsl_startup_hook.sh` + `scripts/kilo-benchmarks/daily_refresh.sh`)*; **generated, never
  hand-curated.** Generation also **verifies** each entry — a command/script that errors is marked `broken`
  (not offered as usable) and listed as a defect; a doc the index supersedes is archived.
  **Gate (objective):** `jq '.capabilities[]|select(.status=="ok").invoke' capabilities.json` — every listed
  command returns 0 when run with `--help`; every `status:"broken"` entry is excluded; the live-state block
  parses from a real `docker ps` ≤24h old (timestamp field present).
- **Surface health (ongoing).** Outdated docs and broken scripts are flagged by the verify pass; the daily
  pipeline reports the `broken`/stale set; they get **fixed or deleted** under the net-deletion gate (Doctrine).
- **Skills.** `.claude/skills/` for the repeatable workflows (ported from the 12 `.windsurf/workflows/*.md`),
  incl. a `launch` skill. One-hop orientation: CLAUDE.md / AGENTS.md → index → skill.
- **Deferred:** domain subagents (`.claude/agents/`), the intent router, and *wiring* the `ai-consult`
  fabrik-lib module into a consuming agent. *(The module exists — `/opt/fabrik-lib/ai-consult/`, Active in the
  README, tests passing; only its integration is deferred.)*

## Doctrine

1. Judge every line by the KPI (per-project operator-attention → 0).
2. Self-describing — capabilities/infra/rules are generated into one index, never memorized.
3. Reuse before build → route by intent (advisory grep). Net-deletion gate: every change deletes/merges ≥1 module.
4. Unrecorded prod-impacting manual step = defect (deliberate human risk-gates are not).
5. Self-heal is a defect signal (alert on rising heal frequency); improve out of production (clone → prove → PR → human merge). *(builds on the watchdog Tier A–D contract, `core/60-watchdog.md` + `self-healing.md`)*
6. Spend compute to save attention (rent servers/GPUs; cheapest-model-that-clears-the-bar) under the spend-velocity ceiling *(extends `core/cost-budget.md` + `/opt/fabrik-lib/cost-budget/`)*.
7. Bounded authority — agents talk to the control plane, not prod; no agent holds master creds, root, or break-glass; autonomy earned per-component.
8. Durable or it didn't happen — decisions land in CLAUDE.md / AGENTS.md / rule-packs / skills / memory.

## Operator-absent policy *(to-build)*

State machine off `last_telegram_ack` — the **presence store** = a single-row `control_state` table on
`postgres-main` (column `last_telegram_ack timestamptz`), written by the Telegram-ack handler *(to-build;
verified absent — 0 `control_state` refs in `src/`)*:
- **0–4h:** nothing changes; queued actions wait.
- **4–24h:** autonomous allow-list only — restart Tier A–C (backoff), roll back a deploy that failed its own
  verify if <24h and no migration, renew certs/DNS, scale within a pre-set ceiling, WAF-block DoS spikes,
  reroute to a maintenance page after 2 failed rollbacks, halt on spend breach.
- **24–72h:** stability-only; freeze new deploys; **keep customer-facing services running**; daily digest to
  Telegram + email.
- **>30d:** dead-man's-switch (Shamir break-glass to a designated successor — see Residual: Shamir tooling).
- **Freeze-list (never, any state):** data/backup deletion, destructive migrations, secret/IAM/root changes,
  public exposure, recurring-spend increase, cross-project actions, doctrine/rule-pack edits, merging
  generated code, any autonomy-widening.
**Gate:** `UPDATE control_state SET last_telegram_ack = now()-interval '25h'` → `fabrik launch-gate check`
exits **1** (`operator_absent`) and the digest job fires; set to `now()-interval '5h'` → exits **0**.

Telegram is a vendor SPOF — add email as a second approval channel before it is load-bearing.

## Execution protocol (binding — subagents, parallelism, code review)

Every step in §First N days runs in this order; skipping a step = the step is not done. This is how *any* AI
(or several in parallel) implements the plan with identical rigor — the plan, not the executor's memory, is
the source of truth.

**Per step:**
1. **RE-GROUND** — mandatory `Explore` subagent. Re-verify every `path:line` and count the step touches still
   matches HEAD *before* coding (the tree drifts under parallel agents). Any drift → STOP, fix the plan, then code.
2. **TESTS FIRST** (TDD per `core/45-testing-strategy.md`) — the failing test is in the diff before production code.
3. **IMPLEMENT** to green, strictly in step scope; no cross-step creep.
4. **SELF-REVIEW to a fixed point** (CLAUDE.md 1a) — re-read the diff for bugs, edge cases, `.windsurf/rules`
   deviations; fix; re-run; repeat until a fresh read finds nothing.
5. **ADVERSARIAL CODE REVIEW** — mandatory `general-purpose` subagent (or `/fabrik-review`), launched in the
   background while you draft the commit. Correctness/security only: logic/off-by-one, null/empty/None on every
   external return, idempotency (kill-switch, `launch-gate`, tracked-DBs must be re-runnable),
   **fail-open-vs-fail-closed (the spend kill-switch fails CLOSED)**, ordering/atomicity + concurrency on shared
   state (`control_state`, `attention_events`, `.env` writes), tenant isolation (per-DB non-superuser role /
   RLS), plan↔code drift. **Reproduce each finding with a runnable test before fixing.** CONFIRMED → fix before
   commit; PLAUSIBLE → fix or record why deferred; REFUTED → ignore. Prompt: Appendix A.
6. **GATE** — `python scripts/final_gate.py --check --json` → `status:success`, plus the step's own gate.
7. **COMMIT** — explicit paths only (`git add <path>…`); never `-A` on the shared `master`.

**Parallelism (mandatory where suitable):**
- **Grounding + review always fan out** — one independent subagent per step/dependency, run in parallel; merge
  + dedupe before proceeding. A change's writer is never its sole verifier.
- **Independent steps run as parallel sub-streams.** The dependency edges that MUST stay serial: **Day 1
  (do-not-die floor) before any destructive action**; **the brake migration (`attention_events` +
  `control_state`) before any code reading those tables**. Everything else — capability index, skills, docs,
  the `fabrik launch` surfaces — has no edge and parallelizes.

**Plan-exit (after the last operator-approved step):**
8. **CONVERGENCE CHECK** — mandatory `general-purpose` subagent: no step regressed an earlier one; re-run the
   Day-1 (do-not-die) + brake gates end-to-end.
9. **Status → `SHIPPED <steps> (YYYY-MM-DD)`.**

**What "subagent" means:** the `Agent` tool (native) or the OpenRouter pool (`fanout`) with the named type.
Subagents do verification / re-grounding / adversarial review only — the executing AI owns the diff and its
synthesis; never delegate the writing.

### Appendix A — adversarial code-review prompt (paste per step)

```
Adversarial code review of <STEP> of docs/development/plans/2026-06-29-plan-empire-operating-model.md.
Diff: `git diff <base>..HEAD`. Files in scope (full reads, not excerpts): <FILES>.
Hunt correctness/security ONLY (never style): logic/off-by-one; null/empty/None on every external
return; idempotency (re-running a path must not corrupt state — kill-switch, launch-gate, tracked-DBs);
fail-open vs fail-closed (secrets/spend fail CLOSED); ordering/atomicity + concurrency on shared state
(control_state, attention_events, .env); tenant isolation (per-DB non-superuser role / RLS); plan↔code
drift (does the diff match the plan? flag silent scope creep); precision/encoding (spec-value shell
injection into db_name/container_name). Reproduce each suspected bug with a runnable test FIRST. Format
(<400 words): per finding — severity (CORRECTNESS/SECURITY) + file:line + repro + fix + verdict
(CONFIRMED/PLAUSIBLE/REFUTED). Then "What I inspected" (≥6 items). End with exactly "Zero new findings"
OR "N findings, recommend Pass 2".
```

## First N days

Effort is nominal; real elapsed ~2.5×. Each step carries a runnable validation gate. **Every step is governed
by the §Execution protocol above (mandatory RE-GROUND + ADVERSARIAL CODE REVIEW subagents; parallel where the
dependency edges allow).**

- **Day 1 — do-not-die floor.** Spend-velocity kill-switch = a **watchdog-sidecar monitor** *(extends
  `src/fabrik/drivers/watchdog.py` + `/opt/fabrik-lib/cost-budget/`)* that polls `cost_ledger` spend-velocity
  and, on breach, runs `docker network disconnect fabrik <agent-container>` + pages Telegram; plus the
  dead-man's-switch. **Gate:** `INSERT` a `cost_ledger` row exceeding the daily ceiling → the monitor detaches
  the agent container within one poll interval + Telegram fires; `sudo docker network inspect fabrik` shows the
  container gone.
- **Day 2 — break-glass + restore.** Break-glass creds verified offline-from-phone; backup-exists + one real
  restore *(extends `src/fabrik/orchestrator/vultr_drill.py`)*. **Gate:** `fabrik vultr drill` (or
  bootstrap-from-backup) → app 200 + DB row-counts match source; RTO/RPO recorded.
- **Day 3 — purge.** the scaffold set (20 template dirs today, 2026-07-12) → 1 canonical scaffold; trim
  drivers/registrars to one default path each. **Gate:** `ls templates/ | wc -l` → 1 active (+ archived/);
  `fabrik launch` resolves the one default.
- **Days 4–5 — the brake.** `attention_events` + `control_state` schema (Alembic migration on `postgres-main`)
  + `launch-gate check` (attention budget). **Gate:** `alembic upgrade head` exits 0; `pytest tests/brake/`
  passes (seeded over-budget attention → `fabrik launch-gate check` exits 1).
- **Days 6–11 — `fabrik launch` v0.** spec → repo → deploy → DNS → DB → (auth if needed) → register. The
  per-product plumbing is a **vendor-compose** (vendor `fastapi-user-auth/` when the product needs auth);
  `fabrik launch` wires it into the canonical scaffold. **Gate (Day 11):** launch one real project to a live
  URL, time it (the effort-multiplier datapoint for Residual #3).
- **Days 12–13 — capability index** (`scripts/generate_capability_index.py` → `docs/CAPABILITIES.md` + JSON;
  wired into `wsl_startup_hook.sh`) + one `launch` skill + golden-path acceptance test (launch 3 example specs
  end-to-end → each live) + the launch throttle (the §brake cap: ≤2 launches/week). **Gate:**
  `python scripts/generate_capability_index.py --check` exits 0; inject a deliberately-broken script → re-run →
  it appears with `status:"broken"` and is excluded from the usable set; the §Agent-enablement objective gate passes.

## Out of scope / open

- **Distribution / demand generation** is out of scope by construction — this model builds for customers who
  are **already waiting**; finding new demand is a separate concern with its own plan.
- **Do not monetize Fabrik as a PaaS** — multi-tenant support + an AI agent on customers' infra competes for
  the operator-attention this plan protects. Its byproducts (the AI Models Browser, fabrik-lib, scaffolds,
  build-in-public) are the outward flywheel instead.
- **Removed 2026-07-12 (operator-directed):** the monetization + selection/graduate/retire-by-revenue premise
  (§Payments, traction lifecycle, "cattle" doctrine, Day-12 retirement engine) — the builds serve known
  customers, so there is no "select winners by payment" step. If per-product *billing* is ever needed for a
  specific project, vendor `/opt/fabrik-lib/payments/` in that project's own spec — it is not a factory-level
  concern.

## Evidence

Grounded 2026-07-12 (path:line citations actually opened / commands run):

- Watchdog sidecar exists — `src/fabrik/drivers/watchdog.py`, contract `.windsurf/rules/core/60-watchdog.md`.
- Spend-ceiling base exists — `/opt/fabrik-lib/cost-budget/schema_pg.sql` (`CREATE TABLE … cost_ledger`;
  module API `check_caps` / `record_cost` / `drop_to_rule_only_mode`).
- Recovery-gauntlet base exists — `src/fabrik/orchestrator/vultr_drill.py:410` (`def drill(`).
- Drift base exists — `src/fabrik/cli.py:1389` (`@cli.command("audit-registrars")`).
- Daily pipeline exists — `scripts/wsl_startup_hook.sh`, `scripts/kilo-benchmarks/daily_refresh.sh`.
- Deploy registry is YAML — `data/projects.yaml` (keys `deploy/domain/ports/last_apply_status/
  registrars_applied/scaffold_status`).
- Registrar count is **10** — `src/fabrik/orchestrator/infrastructure.py:90` (`_REGISTRAR_ORDER`: postgres,
  redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus, watchdog); drivers **27**.
- Auth module for per-product needs — `/opt/fabrik-lib/fastapi-user-auth/` (Active, Pattern-A JWT).
- `ai-consult` module exists — `/opt/fabrik-lib/ai-consult/` (Active, tests passing).
- To-build tables absent (2026-07-12 re-ground) — `attention_events` / `control_state` return **0** real refs
  in `src/`+`scripts/`; `fabrik launch`/`prove` absent in `src/fabrik/cli.py`; `docs/CAPABILITIES.md` absent;
  `.claude/skills` = 0, `.claude/agents` = 0.

```text
fabrik-lib: 71 dirs / 55 README-table modules   drivers: 27   registrars: 10   scaffolds: 20 template dirs
.windsurf/workflows: 12   .claude/skills: 0   .claude/agents: 0   [re-ground 2026-07-12]
ABSENT (to-build): fabrik launch=0  fabrik prove=0  docs/CAPABILITIES.md=absent
  attention_events refs=0  control_state refs=0  launch-gate refs=0
```
(Counts are point-in-time; modules/scaffolds drift as parallel agents add them — the generated index, not
this number, is canonical. Drivers/registrars are stable architecture constants.)

## Self-audit

- **Original convergence (2026-06-30):** ran five independent adversarial passes (5 → 4 → 9 → 1 → 0) over the
  then-scoped plan; every existing-asset claim grounded at `path:line`, every to-build deliverable verified
  absent. Those passes covered the monetization/selection design that has since been removed — that portion is
  **moot as of the 2026-07-12 re-scope** and is not reproduced here.
- **Re-scope (2026-07-12, operator-directed):** the operator confirmed all builds have real waiting customers,
  so the speculative monetize-and-select premise does not apply. Removed §Payments, the selection-validity
  primitive, the traction lifecycle (`fabrik_projects` + states + retire engine), Doctrine "monetizable"/
  "cattle", and Day-12. Re-grounded the **remaining** factual layer against HEAD: counts refreshed
  (55/71/20/12; registrars 10 + drivers 27 stable); every retained "exists"/"absent" anchor re-confirmed (see
  Evidence). No payment external-facts remain in scope, so no vendor/API citations are load-bearing here.
- **Floor (what green does NOT prove):** `final_gate`/`check_convergence` prove citation presence + format, not
  that `fabrik launch` will hit ≤30 min or that the attention-budget caps are right — those are empirical,
  measured at the Day-11 timing gate.

## Residuals

1. **Shamir break-glass — decided.** Tool = `ssss` (2-of-3 split), armed when the first large project needs it
   (`apt install ssss` — verified not installed today). Interim = a single `age`-encrypted break-glass bundle
   on the operator phone + a designated successor.
2. **postgres-main capacity — modeled (trivial).** The metrics tables are tiny: `control_state` ≈ one row;
   `attention_events` ≈ 10²–10³ rows/wk — combined well under ~100 MB/yr. The binding limit is connection
   count, mitigated by `max_connections=200`.
3. **Effort 2.5× — estimate with a built-in check.** A planning multiplier; the Day-11 timing gate is its first
   measurement and recalibrates the rest.
4. **Spec re-scope — OPEN (self-service).** `docs/superpowers/specs/2026-07-12-empire-operating-model-design.md`
   still carries the removed monetization premise; it should get the same operator-directed re-scope (or be
   archived) so plan and spec agree. Resolution: re-run `/fabrik-spec-review` on it with this re-scope, or
   archive it.

## Validation

Final step — run the gate:

```text
$ python scripts/final_gate.py --check --json
{ "status": "success", "failed": 0, "failures": [] }
```
`check_convergence.py` runs inside `final_gate` and passes — the plan has `## Evidence`, a `## Self-audit`
block, ≥1 `path:line` per section, and a command-output fence. Green proves citation presence + format, not
design soundness — the real proof is the Evidence + the grounding above.
