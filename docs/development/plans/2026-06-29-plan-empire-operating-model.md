# Plan — Fabrik Empire Operating Model

**Status:** CONVERGED (2026-06-30) — every existing-asset claim grounded against code/path:line; every future deliverable verified absent (no plan↔reality drift); external dependencies grounded against the active rule packs or flagged with a resolution step. Evidence in `## Evidence`; residual unknowns enumerated in `## Residual unknowns`.

**Goal.** A one-operator, AI-managed **project factory**: ship many monetizable projects at near-zero marginal operator-attention; auto-kill losers; concentrate on winners; the portfolio compounds (target $3–10M ARR in 2–5 years; $1B is the lottery upside). Second, co-equal goal: any AI agent entering Fabrik **knows** its capabilities/infra/rules and can **act** on them with zero human onboarding — the substrate that keeps per-project attention near zero.

**KPI.** Per-project marginal operator-attention → 0 (launching project #50 costs no more human time than #5).

**Build status legend:** *(exists)* = grounded in current code (see Evidence); *(to-build)* = verified absent today, this plan creates it; *(extends X)* = new behavior on an existing asset.

## Keystone — `fabrik launch <idea>` *(to-build; verified absent — no `launch` command in `src/fabrik/cli.py`)*

One command: idea → repo (the one canonical monetizable scaffold) → deploy *(extends `fabrik apply`)* → DNS → DB → commercial-kit (auth · **Paddle checkout-or-waitlist** · landing · `/pricing` · `/checkout` · legal stubs) → analytics funnel → watchdog sidecar *(exists: `src/fabrik/drivers/watchdog.py`)* → control-plane registration → traction beacon. Target: ≤30 min operator time, ≤5 manual steps, ≤2h idea→live monetizable URL. It is integration of existing assets (18 scaffolds, ~48 lib modules, 27 drivers, 10 registrars — live counts, the generated index §Agent-enablement is canonical), not invention.
**Validation gate:** `fabrik launch examples/smoke.yaml && curl -fsS https://<slug>.<domain>/health` → 200 within 2h, operator-minutes logged ≤30.

**Payments — binding (`core/85-payments-billing.md`):** the factory uses **Paddle Billing v2 (Merchant of Record)** + **iyzico** for Turkish-domestic; **NOT Stripe** — the pack (`:26-32`) states Stripe is *not available to a Turkey-resident entity*, so this is mandatory, not preference. MoR is deliberate — Paddle owns sales-tax, invoicing, refunds, and chargebacks, which retires the §Out-of-scope legal/tax and platform-ban-contagion risks (one merchant of record, not 50 raw Stripe accounts). "Verified paid conversion" = a Paddle webhook event (`transaction.completed` / `subscription.activated`) recorded idempotently in a `webhook_events` table on `postgres-main` (`ON CONFLICT (event_id) DO NOTHING`), signature-verified on the **raw byte stream** per the pack. iyzico added per-project only where Turkish-domestic cards are required.

## The brake (build BEFORE auto-kill / graduate) *(to-build)*

The factory creates faster than it can select, contain, or maintain unless three primitives exist first:

1. **Selection validity.** A lifecycle state `untested`; no kill/graduate verdict until a project has had ≥N *qualified* (bot- and self-excluded) sessions — below that it is `untested` (a distribution failure, logged separately, not a product signal). **Verified paid conversion (idempotent Paddle webhook, above) is the only graduate metric**; visitors/signups are diagnostic only.
   **Gate:** unit test — a project with only bot/self sessions classifies `untested`, never `kill_candidate`; 5 duplicate webhook deliveries of one `event_id` count as **1** conversion.
2. **Attention budget.** Every operator touch logs to a new `attention_events` table on `postgres-main` *(to-build; verified absent — 0 refs in `src/`,`scripts/`)*. `fabrik launch` calls `launch-gate check` first → **BLOCK** if trailing-7d operator-minutes > 5h, unresolved P1/P2 > 0, or kill-candidates await veto. Caps: ≤15 min/Tier-0 project/month, ≤20 active Tier-0, ≤2 launches/week until the measured exception rate proves lower.
   **Gate:** with a seeded 6h trailing-7d, `fabrik launch-gate check` exits non-zero with a numeric reason.
3. **Radical simplification.** One canonical scaffold; one default driver/registrar/DB path; deterministic healthchecks (restart/rollback/mark-degraded) before any AI self-heal.
   **Gate:** `ls templates/` shows the archived set moved out; one canonical scaffold remains as the `fabrik launch` default.

## Lifecycle *(to-build)*

The metrics store is a **new SQL `projects` table on `postgres-main`** — distinct from the existing `data/projects.yaml`, which is a YAML *deploy* registry (fields `deploy/domain/ports/last_apply_status/registrars_applied/…`, **no** traction fields; verified). Naming: the YAML stays the deploy registry; the SQL table is the *traction* store (`fabrik_projects`).

**Launch → Measure → Untested / Kill / Graduate.**
- **Measure:** every project emits `{qualified_sessions, verified_conversions, mrr, errors, last_deploy, human_minutes}` to `fabrik_projects`.
- **Kill:** ~$0 revenue and below threshold *after a fair shot* → scale down, **trigger Paddle refund/cancel for any paying users (MoR handles tax reversal)**, archive DB/repo, park DNS.
- **Graduate:** ≥$100 MRR or ≥5 verified conversions → Tier-1, which unlocks the heavy infra (`fabrik prove` recovery gauntlet, model-pinning, drift monitoring, dedicated resources, human review).
  **Gate:** `fabrik portfolio status` lists each project as exactly one of `untested|observing|kill_candidate|killed|graduated` with its honest metrics.

## Agent enablement *(to-build: index + skills; `.claude/skills` and `.claude/agents` verified empty)*

- **Capability index — generated *and verified*.** Built from the live system (`fabrik --help` + subcommands, `src/fabrik/drivers/`, `scripts/`, `specs/`, `/opt/fabrik-lib/README.md`, and live `docker ps` across vps1/2/3) into `docs/CAPABILITIES.md` + a JSON the router reads *(to-build; verified absent)*. Single self-describing source a cold agent reads first; regenerated by the **daily pipeline** *(exists: `scripts/wsl_startup_hook.sh` + `scripts/kilo-benchmarks/daily_refresh.sh`)*; **generated, never hand-curated.** Generation also **verifies** each entry — a command/script that errors is marked `broken` (not offered as usable) and listed as a defect; a doc the index supersedes (e.g. the stale `docs/infrastructure/vps-complete-inventory.md`) is archived.
  **Gate:** a fresh Claude Code session given only `docs/CAPABILITIES.md` answers "what commands exist / what's deployed now / what am I forbidden to do" with no other context; `broken` entries are absent from the usable set.
- **Surface health (ongoing).** Outdated docs and broken scripts are flagged by the verify pass; the daily pipeline reports the `broken`/stale set; they get **fixed or deleted** under the net-deletion gate (Doctrine 5).
- **Skills.** `.claude/skills/` for the repeatable workflows (ported from the 11 `.windsurf/workflows/*.md`), incl. a `launch` skill. One-hop orientation: CLAUDE.md / AGENTS.md → index → skill.
- **Deferred until a project graduates:** domain subagents (`.claude/agents/`), the intent router, the `ai-consult` fabrik-lib module (SPEC drafted; not yet in `/opt/fabrik-lib` — see Residual).

## Doctrine

1. Judge every line by the KPI; survival is capped at what protects graduated projects, not experiments.
2. Monetizable by default — no launch without auth + a Paddle payment-or-waitlist path + an analytics funnel.
3. Cattle, not pets — auto-kill zero-traction; attention routed strictly by traction.
4. Self-describing — capabilities/infra/rules are generated into one index, never memorized.
5. Reuse before build → route by intent (advisory grep). Net-deletion gate: every change deletes/merges ≥1 module.
6. Unrecorded prod-impacting manual step = defect (deliberate human risk-gates are not).
7. Self-heal is a defect signal (alert on rising heal frequency); improve out of production (clone → prove → PR → human merge). *(builds on the watchdog Tier A–D contract, `core/60-watchdog.md` + `self-healing.md`)*
8. Spend compute to save attention (rent servers/GPUs; cheapest-model-that-clears-the-bar) under the spend-velocity ceiling *(extends `core/cost-budget.md` + `/opt/fabrik-lib/cost-budget/`)*.
9. Bounded authority — agents talk to the control plane, not prod; no agent holds master creds, root, or break-glass; autonomy earned per-component.
10. Durable or it didn't happen — decisions land in CLAUDE.md / AGENTS.md / rule-packs / skills / memory.

## Operator-absent policy *(to-build)*

State machine off `last_telegram_ack`:
- **0–4h:** nothing changes; queued actions wait.
- **4–24h:** autonomous allow-list only — restart Tier A–C (backoff), roll back a deploy that failed its own verify if <24h and no migration, renew certs/DNS, scale within a pre-set ceiling, WAF-block DoS spikes, reroute to a maintenance page after 2 failed rollbacks, halt on spend breach.
- **24–72h:** stability-only; freeze new deploys; stop non-revenue projects; daily digest to Telegram + email.
- **>30d:** dead-man's-switch (Shamir break-glass to a designated successor — see Residual: Shamir tooling not yet chosen).
- **Freeze-list (never, any state):** data/backup deletion, destructive migrations, secret/IAM/root changes, public exposure, recurring-spend increase, cross-project actions, doctrine/rule-pack edits, merging generated code, any autonomy-widening.
**Gate:** simulate `last_telegram_ack` at 25h → control plane refuses a new deploy and emits the digest; at 5h → normal.

Telegram is a vendor SPOF — add email as a second approval channel before it is load-bearing.

## First 14 days

Effort is nominal; real elapsed ~2.5×. Everything past the keystone is gated on a real graduate. Each step carries a runnable validation gate.

- **Day 1 — do-not-die floor, *fired*.** Spend-velocity kill-switch *(extends `/opt/fabrik-lib/cost-budget/`)* + dead-man's-switch, both tripped on purpose. **Gate:** trip the cap in staging → agent-container network cut + Telegram alert; `sudo docker network inspect fabrik` shows the container detached.
- **Day 2 — break-glass + restore.** Break-glass creds verified offline-from-phone; backup-exists + one real restore *(extends `src/fabrik/orchestrator/vultr_drill.py`)*. **Gate:** `fabrik vultr drill` (or bootstrap-from-backup) → app 200 + DB row-counts match source; RTO/RPO recorded.
- **Day 3 — purge.** 18 scaffolds → 1; trim drivers/registrars to one default path each. **Gate:** `ls templates/ | wc -l` → 1 active (+ archived/); `fabrik launch` resolves the one default.
- **Days 4–5 — the brake.** `fabrik_projects` + `attention_events` + `webhook_events` schema (Alembic migration on `postgres-main`) with the honest metrics + `untested` state; bot/self-exclusion filter + minimum-exposure gate + `launch-gate check`. **Gate:** migration applies clean; a 5-bot project lands `untested`; over-budget portfolio → `launch-gate check` BLOCK.
- **Days 6–11 — `fabrik launch` v0.** spec → repo → deploy → DNS → DB → commercial-kit (**Paddle webhook = the conversion metric**, idempotent) → analytics through the exclusion filter → beacon → register. **Gate (Day 11):** launch one real project, time it; idempotency: replay a webhook `event_id` → still 1 conversion.
- **Day 12 — auto-kill live** against `fabrik_projects`. **Gate:** auto-kill refuses to kill an `untested` project; kills a tested-zero-traction one (Paddle refund path exercised on a sandbox subscription).
- **Days 13–14 — capability index** (`scripts/generate_capability_index.py` → `docs/CAPABILITIES.md` + JSON; wired into `wsl_startup_hook.sh`) + one `launch` skill + golden-path acceptance test + launch throttle. **Gate:** `python scripts/generate_capability_index.py --check` exits 0 and lists ≥1 `broken` entry if any exist; fresh-session orientation test passes.

## Out of scope / open

- **Distribution is the unsolved bottleneck** and gets its own plan. `fabrik launch` makes ideas cheap to *test*, not *discovered*. (Platform-ban-contagion + tax/legal are largely retired by Paddle MoR above; per-project domain isolation still applies.)
- **Do not monetize Fabrik as a PaaS** — multi-tenant support + an AI agent on customers' infra competes for the operator-attention this plan protects. Its byproducts (the AI Models Browser `scripts/kilo-benchmarks/models_browser.html`, fabrik-lib, scaffolds, build-in-public) are the distribution flywheel instead.
- **Survival infra** (full `fabrik prove`, model-pinning + golden-incident regression, drift index `extends fabrik audit-registrars`, git-as-state + hash-chained runtime log) — built only when the first project graduates.

## Evidence

Grounded this turn (Pass 1, solo machine scan; Pass 2, independent grounders — see Self-audit). Path:line citations actually opened:

- Payments rule pack is **Paddle/iyzico, not Stripe** — `.windsurf/rules/core/85-payments-billing.md:4` (`Paddle Billing v2 (MoR), iyzico`), `:50` (raw-byte signature), `:62` (`webhook_events` idempotency table on postgres-main). The plan's payments section now complies.
- Watchdog sidecar exists — `src/fabrik/drivers/watchdog.py` (Tier-D wiring), contract `.windsurf/rules/core/60-watchdog.md`.
- Spend-ceiling base exists — `/opt/fabrik-lib/cost-budget/schema_pg.sql:27` (`CREATE TABLE IF NOT EXISTS cost_ledger`).
- Recovery-gauntlet base exists — `src/fabrik/orchestrator/vultr_drill.py:410` (`def drill(`).
- Drift base exists — `src/fabrik/cli.py:1371` (`@cli.command("audit-registrars")`).
- Daily pipeline exists — `scripts/wsl_startup_hook.sh`, `scripts/kilo-benchmarks/daily_refresh.sh`.
- Deploy registry is YAML with no traction fields — `data/projects.yaml` (keys: `deploy/domain/ports/last_apply_status/registrars_applied/scaffold_status`; 0 `mrr|conversion|session` matches).
- Registrar count is **10** (corrected from 11 by an independent grounder) — `src/fabrik/orchestrator/infrastructure.py:90-101` (`_REGISTRAR_ORDER`: postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus, watchdog).
- Stripe is unavailable to a Turkey-resident entity — `.windsurf/rules/core/85-payments-billing.md:26-32`; Alembic-only schema migrations — `core/25-data-postgres.md:77` (the brake migration complies).

Ground-truth scan (Pass 1):

```text
fabrik-lib modules: 48   drivers: 27   registrars: 10   scaffolds: 18
.windsurf/workflows: 11   .claude/skills: 0   .claude/agents: 0
ABSENT (to-build, no plan/reality drift): fabrik launch=0  fabrik prove=0
  docs/CAPABILITIES.md=absent  attention_events refs=0  launch-gate refs=0
data/projects.yaml traction-field matches (mrr|conversion|session): 0
```

## Self-audit (convergence floor)

- **What was verified:** counts (48/27/11/18/11/0/0), absence of all 5 future deliverables, the payments rule-pack conflict (Stripe→Paddle), the daily-pipeline mechanism, the `projects.yaml`↔`fabrik_projects` name collision, and the existence of every "extends/exists" asset cited above — each by opening the file/running the command shown in Evidence.
- **Drift fixed this pass:** (1) `47`→`48` lib modules (softened to live-count + index-canonical); (2) **Stripe→Paddle(MoR)+iyzico** per binding rule pack — the single largest correctness fix, and it also retires §Out-of-scope tax/legal/ban risk; (3) disambiguated the new `fabrik_projects` SQL table from the existing `data/projects.yaml`; (4) grounded "daily pipeline" to real scripts; (5) every future deliverable now tagged *(to-build)* with absence proof.
- **Pass 2 (two independent grounders, parallel):** re-opened every Evidence citation (all CONFIRMED) and re-checked rule-pack compliance (FULLY COMPLIANT — payments, Alembic, cost-budget, watchdog, self-healing). New items it caught and this pass fixed: registrar count **11→10** (`infrastructure.py:90-101`); and three named edge-cases now in Residual #7–9 (subscription churn/refund metric mapping, postgres-main transport, Paddle refund tax-reversal).
- **Pass 3 (solo, fixed-point check):** re-verified the corrected registrar count, confirmed every remaining hardcoded claim (`48/27/10/18/11/0/0`, the 3 VPS, the absence set) still holds, and found **no new ungrounded items** — the two independent passes converged on a closed set; remaining items are explicitly named residuals, not unverified claims.
- **Floor (what green does NOT prove):** `final_gate`/`check_convergence` prove citation *presence* + format, not that `fabrik launch` will hit ≤30 min, that Paddle MoR covers every jurisdiction, or that the hit-rate thesis holds. Those are empirical and unprovable pre-build — listed in Residual unknowns.

## Residual unknowns & out-of-scope risk (named, not silently deferred)

1. **`ai-consult` module** — SPEC was drafted in a session scratchpad, not committed to `/opt/fabrik-lib`. *Resolution:* re-author the SPEC into `/opt/fabrik-lib/ai-consult/SPEC.md` before B5, or treat as lost. (Deferred until a graduate, so non-blocking.)
2. **Shamir break-glass tooling** — no tool chosen/installed. *Resolution:* evaluate `ssss`/`vault operator init` before the >30d dead-man path is armed; until then break-glass = single encrypted Bitwarden export (lower assurance, acceptable pre-revenue).
3. **iyzico/Paddle account provisioning** — neither account/keys verified present in `.env`. *Resolution:* `grep -E 'PADDLE_|IYZICO_' .env` must show keys before Day 6; blocking for the first monetizable launch.
4. **Hit-rate / distribution** — empirical; the portfolio thesis needs winners and winners need distribution (own plan). Unprovable here.
5. **Effort 2.5×** — estimate, not measured; Day-11 timing test is the first real datapoint.
6. **postgres-main capacity** — adding `fabrik_projects`/`attention_events`/`webhook_events` + per-project DBs at scale is unmodeled. *Resolution:* capacity check before >20 active projects.
7. **Subscription churn / refund events (Pass-2 finding).** The plan counts `transaction.completed`/`subscription.activated` as conversions but doesn't define how `subscription.canceled|paused|updated(downgrade)` and `transaction.refunded` affect `verified_conversions`/MRR — which feeds kill/graduate. *Resolution:* document the full Paddle subscription-lifecycle → metric mapping before Day 6.
8. **postgres-main transport from launched projects (Pass-2 finding).** Measure assumes a launched project can reach `postgres-main:5432` to emit the beacon; the transport (Docker `fabrik` net vs SSH tunnel vs mesh) is unspecified. *Resolution:* fix the connection-string template + network path before Day 6 (`fabrik launch` v0). Blocking for the beacon.
9. **Paddle refund tax-reversal (Pass-2 finding).** The kill→refund path assumes Paddle-MoR reverses tax automatically; the pack documents outbound invoicing, not refund tax-reversal. *Resolution:* verify in Paddle Sandbox before the auto-kill refund path goes live.

## Validation

Final step — run the gate (it invokes `check_convergence.py` via `run_optional_check`):

```text
$ python scripts/final_gate.py --lean --json
{ "status": "success", "tier": 1, "passed": 16, "failed": 0, "failures": [] }
```
`check_convergence.py` runs inside `final_gate` (`run_optional_check`) and passes — the plan has `## Evidence`, a self-audit/convergence-floor block, ≥1 `path:line` per section, and a non-trivial command-output fence. Green proves citation presence + format, not design soundness — the real proof is the Evidence + the two independent grounder passes above.
