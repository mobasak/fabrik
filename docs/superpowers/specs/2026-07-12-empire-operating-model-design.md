# Design Spec — Fabrik Empire Operating Model (re-grounded)

**Status:** CONVERGED (2026-07-12) — `/fabrik-spec-review` fixed point. Pass 1 (all axes) added the
web-analytics/qualified-session BUILD row (a capability that had no ladder verdict; confirmed no fabrik-lib
web-analytics module exists — `request-metering/`/`api-quota/`/`concurrency-throttle/` all refuted as wrong-domain);
Pass 2 re-grounded all axes with **zero edits** (md5 `671bfcf9` start = end). External Paddle/iyzico facts
re-verified live this session; the headline `payments/`-supersedes-build verdict re-confirmed against the module's
real SQL (`webhook_events`/`plans`/`customers`/`subscriptions`) + API (`apply_event`/`has_feature`). One BLOCKING
unknown remains (Residual #1, operator opens Paddle/iyzico accounts) — correctly scoped to sub-spec S5 only, so it
does NOT block the spec (S1–S4 + S6-core need no accounts).

**Provenance.** Distilled + **re-grounded to 2026-07-12 truth** from the stale plan
`docs/development/plans/2026-06-29-plan-empire-operating-model.md` (last grounded 2026-06-30/07-01).
That plan is treated as an **untrusted input** — a record of *intent + decisions*, not fact. Every count,
absence claim, external-API fact, and "build" verdict below was re-verified against the live tree / live web
this session; the deltas are enumerated in **§Re-grounding delta**. This spec grounds the **design** (what to
build, why, which approach); the phased build lives in the per-sub-spec plans (see **§Decomposition**).

---

## Goal (intent — unchanged from the plan)

A **one-operator, AI-managed project factory**: ship monetizable projects at near-zero *marginal* operator
attention; surface non-earners *with their data* and retire them **on operator decision (never auto-killed)**;
concentrate on winners; let the portfolio compound (target $3–10M ARR in 2–5 years; $1B is lottery upside,
not the plan). Co-equal second goal: any AI agent entering Fabrik **knows** its capabilities/infra/rules from a
generated, self-verifying index and can act with zero human onboarding.

**KPI:** per-project marginal operator-attention → 0 (launching project #50 costs no more of your time than #5).

**Explicitly NOT in scope** (from the plan, still valid): selling Fabrik itself as a SaaS/PaaS (competes for
the attention this protects); solving **distribution** (`fabrik launch` makes ideas cheap to *test*, not
*discovered* — its own separate plan).

---

## Re-grounding delta (what changed since 2026-06-30 — the reason this spec exists)

**1. The single biggest correction — payments is now VENDOR, not BUILD.** The plan treats the "commercial-kit"
(auth · Paddle checkout · webhook idempotency · the event→metric mapping) as a per-project **build**. As of
2026-07-12 a **`/opt/fabrik-lib/payments/` module exists** that already implements almost the entire payments
design: Paddle (MoR) + iyzico behind one currency-routed provider interface (fail-closed), **raw-byte HMAC verify
+ `event_id` idempotency (dup ⇒ no-op)**, a webhook-derived entitlement state machine (`apply_event`/`has_feature`,
grace/revoke, order-tolerant), an atomic record+enqueue store, RLS tenant isolation, audit + GDPR purge, and a
Next.js/React/Tailwind plan-pick UI. It **ships its own `webhook_events` table** (+ `plans`/`customers`/
`subscriptions`/`payments_audit_log`). ⇒ **The plan's `webhook_events` build and its hand-rolled Paddle/iyzico
integration are superseded — the factory VENDORS `payments/`.**

**2. Other capabilities the plan called "build" are now vendorable modules** (all live at 2026-07-12):
`fastapi-user-auth/` (Pattern-A auth), `webhooks/` (outgoing HMAC-signed delivery — the traction beacon),
`cookie-consent/` (analytics consent gate for the "qualified session" JS `page_view`), `abuse-prevention/`
(signup abuse / bot exclusion — overlaps the brake's bot filter), `alerting/` (SSH→Apprise→Telegram — the
kill-switch pager), `gdpr-data-rights/` (the retire-path data-subject erasure).

**3. Count drift (point-in-time; the plan's own caveat predicted this).** fabrik-lib **README-table modules
46 → 55**; fabrik-lib **dirs 48 → 71**; **scaffold template dirs 19 → 20**; **`.windsurf/workflows` 11 → 12**.
**Stable:** registrars **10** (`postgres redis gatus backrest glitchtip grafana authelia meilisearch prometheus
watchdog`, `src/fabrik/orchestrator/infrastructure.py:90`), drivers **27**, `.claude/skills` **0**, `.claude/agents`
**0**. *These counts are inputs to the capability-index sub-spec, not load-bearing design facts — the generated
index is canonical, never a hardcoded number.*

**4. Every architectural claim still holds** (re-verified 2026-07-12):
- **Absent / to-build (0 real refs, confirmed):** `fabrik launch` + `fabrik prove` (none in `src/fabrik/cli.py`),
  `docs/CAPABILITIES.md`, and the traction/control tables `fabrik_projects` / `attention_events` /
  `control_state` (0 refs in `src/`+`scripts/` excluding kilo cache).
- **Exists / extend anchors (present):** `src/fabrik/drivers/watchdog.py`; `cost_ledger`
  (`/opt/fabrik-lib/cost-budget/schema_pg.sql`); `src/fabrik/orchestrator/vultr_drill.py:410 def drill(`;
  `src/fabrik/cli.py:1389 @cli.command("audit-registrars")`; `/opt/fabrik-lib/ai-consult/`; the daily pipeline
  (`scripts/wsl_startup_hook.sh` + `scripts/kilo-benchmarks/daily_refresh.sh`).

**5. External payment facts re-verified current (2026-07-12 live fetch):** see **§External dependencies** — all
still accurate; the plan's `transaction.refunded`-does-not-exist correction and the iyzico V3 scheme hold.

---

## fabrik-lib vendor → enhance → build verdict

The reuse-first ladder over every capability the factory needs (stop at the first that fits). This is the
composition that replaces the plan's mostly-build "commercial-kit."

| Capability | Verdict | Module / where | Note |
|---|---|---|---|
| Subscription billing (Paddle MoR + iyzico), webhook verify + idempotency, entitlement state machine, plan-pick UI | **VENDOR** | `/opt/fabrik-lib/payments/` (Active) | Ships `webhook_events`/`plans`/`customers`/`subscriptions` + `apply_event`/`has_feature`. **Supersedes the plan's payments build + its `webhook_events` table.** |
| End-user auth (Pattern A, app-issued JWT) | **VENDOR** | `fastapi-user-auth/` (Active) | Argon2 + timing-equalized login, refresh rotation, `jti` revocation, RLS. The commercial-kit "auth." |
| Outgoing traction beacon (signed webhook delivery) | **VENDOR** | `webhooks/` (Active) | HMAC-SHA256 signing, auto-disable, history. Alt: direct `postgres-main` INSERT (see §Beacon). |
| Analytics consent gate (qualified-session `page_view`) | **VENDOR** | `cookie-consent/` (Active) | Gates JS analytics so the "qualified session" definition is consent-clean. |
| Bot / abuse exclusion (the brake's qualified-session filter) | **VENDOR + ENHANCE** | `abuse-prevention/` (Active) | Per-IP rate limit + blocklist; the brake adds the operator-IP/UA allowlist + JS-`page_view` requirement. |
| Web-analytics funnel + qualified-session `page_view` capture (client JS event → server ingest) | **BUILD** | in the canonical scaffold (S4) | No fabrik-lib web-analytics module exists (grep 2026-07-12 empty); `request-metering/` is *outbound-call* telemetry, not browser analytics. The "qualified session" signal is defined here + filtered by the brake (S2). *Not a 🆕 candidate yet — scope it minimal (one `page_view` beacon), revisit if ≥2 project types need full funnels.* |
| Spend-velocity kill-switch (do-not-die floor) | **VENDOR + ENHANCE** | `cost-budget/` (`check_caps`, `record_cost`, `drop_to_rule_only_mode`) + `src/fabrik/drivers/watchdog.py` | New behavior = a watchdog-sidecar monitor that polls `cost_ledger` velocity and `docker network disconnect fabrik <ctr>` on breach. Enhancement to the **driver**, not the module core. |
| Operational alert (kill-switch pager) | **VENDOR** | `alerting/` (Active) | SSH→VPS Apprise→Telegram fallback, never raises. |
| AI sysadmin sidecar / self-heal | **VENDOR** | `watchdog/` (Active) + driver | Tier A–D contract (`core/60-watchdog.md`); self-heal-frequency alarm is config on top. |
| Retire-path data erasure | **VENDOR** | `gdpr-data-rights/` (Active) | The operator-approved retire flow's data-subject erasure + `payments/` GDPR purge. |
| Recovery gauntlet (Day-2 restore drill) | **VENDOR + ENHANCE** | `src/fabrik/orchestrator/vultr_drill.py:410` | Existing drill; wire the RTO/RPO record. |
| Frontier-AI consult (deferred wiring) | **VENDOR** | `ai-consult/` (Active) | Integration deferred until a project graduates (per plan). |
| **`fabrik launch <idea>` orchestration** | **BUILD** | new `src/fabrik/cli.py` verb | Genuinely novel: composes scaffold→apply→DNS→DB→vendored kits→register. *🆕 not a fabrik-lib candidate — it's fabrik-hub-specific orchestration, not a generic reusable module.* |
| **The brake** (selection-validity state, `attention_events`, `launch-gate check`) | **BUILD** | new tables + CLI | Factory-governance logic; no module fits. |
| **Lifecycle / traction store** (`fabrik_projects` SQL table + retire-recommendation engine) | **BUILD** | new table + engine | Distinct from `data/projects.yaml` (the YAML deploy registry — no traction fields). |
| **Capability index generator** (`docs/CAPABILITIES.md` + JSON) | **BUILD** | new `scripts/generate_capability_index.py` | Self-verifying, generated from live system; agent-enablement. |
| **Operator-absent state machine** (`control_state` table + autonomy tiers) | **BUILD** | new table + handler | Survive-absence; freeze-list enforced. |

**🆕 fabrik-lib candidates surfaced (propose only — do NOT create from here; cross-repo HARD STOP):** none clear
the bar cleanly — the four BUILD items are all fabrik-hub-governance-specific (project-factory logic), not
generic ≥2-project-type modules. If the **attention-budget / launch-gate** primitive later proves reusable by
another operator-run hub, revisit it as a candidate then.

---

## External dependencies (re-verified live 2026-07-12)

Gate the **monetization slice only** (deferred — see Residual #1). All confirmed still-current this session.

- **Paddle Billing v2 (Merchant of Record)** — `developer.paddle.com/webhooks/overview` (fetched 2026-07-12).
  Real events: transactions `transaction.completed` · `transaction.paid` · `transaction.updated` ·
  `transaction.past_due` · `transaction.payment_failed` · `transaction.billed` · `transaction.canceled`;
  subscriptions `subscription.activated` · `subscription.created` · `subscription.updated` ·
  `subscription.canceled` · `subscription.paused` · `subscription.resumed` · `subscription.past_due` ·
  `subscription.trialing`. **`transaction.refunded` does NOT exist** — refunds/chargebacks are
  **`adjustment.created` / `adjustment.updated`** (Adjustments API `POST /adjustments`, `action:"refund"`); as
  MoR, Paddle reverses the proportional VAT inside the adjustment. **Event→metric mapping** (as the plan, verified):
  `transaction.completed` + `subscription.activated`/`resumed` → **+1 verified_conversion / +MRR**;
  `subscription.updated` → reset MRR; `subscription.paused`/`canceled` → **−MRR**; `past_due` → at-risk;
  `created`/`trialing` → not counted. `payments/` performs the raw-byte HMAC verify + `event_id` idempotency.
- **iyzico** (TR-domestic cards only, added per-project) — `docs.iyzico.com/en/advanced/webhook` (fetched
  2026-07-12). Signature header **`X-IYZ-SIGNATURE-V3`**, HMAC-SHA256 **HEX** (V1/V2 deprecated). *Enrichment
  the plan lacked:* three formats — **Subscription** = `merchantId + secretKey + eventType +
  subscriptionReferenceCode + orderReferenceCode + customerReferenceCode` (the plan's cited form, correct for
  recurring billing); **Direct** = `secretKey + iyziEventType + paymentId + paymentConversationId + status`;
  **HPP** adds `token`. Statuses: `SUCCESS` (paid), `CONTACTLESS_REFUND` (refund); retry 15 min × 3.
- **Stripe is unavailable** to a Turkey-resident entity — `.windsurf/rules/core/85-payments-billing.md:26-32`.
  This makes Paddle-MoR mandatory, not preference (and retires the tax/legal + ban-contagion risk: one MoR, not
  50 raw accounts).

**Payments prerequisite (operator action, Residual #1):** no `PADDLE_*`/`IYZICO_*` keys in `.env` (verified);
the operator has not yet opened the accounts. This gates only the paid-conversion metric — the payment-free
core builds now (waitlist path).

---

## Shape / infra implications (design-level only)

- **Not a new scaffold type.** This is **hub-side** work in `/opt/fabrik` (new `src/fabrik/cli.py` verbs, new
  `scripts/`, new Alembic tables on `postgres-main`) **plus** a designation of **one canonical monetizable
  scaffold** that `fabrik launch` emits (chosen from the existing 20 template dirs — likely `saas-skeleton`).
- **DB:** new tables on the **shared `postgres-main`** (Alembic-only per `core/25-data-postgres.md:77`) —
  `fabrik_projects` (traction), `attention_events`, `control_state`. `webhook_events` comes from `payments/`.
  Capacity is trivial (Residual: modeled — combined < ~100 MB/yr; the ≤20-active-Tier-0 brake cap bounds
  per-project DBs; `max_connections` is the binding limit).
- **The launched projects** are ordinary Fabrik deploys — their `shape:` flags (DB/cache/metrics/auth/admin)
  are set by the canonical scaffold's spec, not by this program spec.

---

## Decomposition — this is a PROGRAM, build it as ~6 independent specs

The plan is one document but **not one buildable unit**. Per the decomposition gate, split into independent
specs, each producing working/testable software on its own, in this **dependency order** (the plan's own serial
edges: do-not-die floor → brake/migration → everything reading the tables → retire engine):

| # | Sub-spec | What it is | Depends on | Payments? |
|---|---|---|---|---|
| **S1** | **Do-not-die floor** | Spend-velocity kill-switch (watchdog-sidecar + `cost-budget`) + break-glass + one real restore drill | — (first, before any destructive action) | no |
| **S2** | **The brake + traction schema** | Alembic migration (`fabrik_projects` + `attention_events` + `control_state`); selection-validity `untested` state; bot/self-exclusion filter (vendors `abuse-prevention`); `launch-gate check` | S1 | no |
| **S3** | **Agent-enablement / capability index** | `generate_capability_index.py` → `docs/CAPABILITIES.md` + JSON (self-verifying); port workflows → `.claude/skills/` | — (parallel; no table edge) | no |
| **S4** | **`fabrik launch <idea>` v0 (waitlist path)** | The keystone orchestration verb, composing scaffold→apply→DNS→DB→vendored auth/consent/beacon→register; monetization stubbed to waitlist | S2 (reads the tables) | no (waitlist) |
| **S5** | **Monetization slice** | Vendor `payments/` into the launch scaffold; wire the verified-paid-conversion metric to `fabrik_projects` | S4 + Residual #1 (Paddle/iyzico keys) | **yes (deferred)** |
| **S6** | **Lifecycle: operator-decided retire + operator-absent policy** | Retire-recommendation engine (never auto-kills); `control_state` autonomy tiers + freeze-list | S2; retire needs S5 for the refund path | partial |

Each `Sx` gets its own `/fabrik-spec` → `/fabrik-data-contract` (S2/S5/S6 touch fields) →
`/fabrik-plan-after-chat` → build cycle. **Recommended first build: S1 (do-not-die floor)** — it is the serial
prerequisite for everything and needs no external accounts. This spec is the **program charter** they inherit
(the vendor verdicts + the grounded external facts), so each sub-spec re-grounds only its own slice.

---

## Doctrine (design invariants carried from the plan — verified consistent)

1. Judge every line by the KPI; survival capped at what protects *graduated* projects, not experiments.
2. Monetizable by default — no launch without auth + a Paddle-payment-**or-waitlist** path + an analytics funnel.
3. **Cattle, not pets, but operator-decided** — zero-traction projects are surfaced *with data + a recommendation*
   and retired **only on operator approval; nothing is auto-killed**.
4. Self-describing — capabilities/infra/rules are **generated** into one index, never memorized (counts drift).
5. Reuse before build (this spec's vendor ladder is the enforcement); net-deletion gate on change.
6. Unrecorded prod-impacting manual step = defect (deliberate human risk-gates excepted).
7. Self-heal is a defect *signal* (alarm on rising frequency); fix out of production (clone → prove → PR → merge).
8. Spend compute to save attention, under the spend-velocity ceiling (S1).
9. Bounded authority — agents talk to the control plane, never prod; no agent holds master/root/break-glass.
10. Durable or it didn't happen — decisions land in CLAUDE.md / AGENTS.md / rule-packs / skills / memory.

---

## Success criteria (testable, per sub-spec — the design's acceptance shape)

- **S1:** INSERT a `cost_ledger` row over the daily ceiling → the monitor detaches the agent container within one
  poll interval + `alerting` fires; `docker network inspect fabrik` shows it gone. Fail-**closed**.
- **S2:** `alembic upgrade head` = 0; a 99-qualified-session/0-conversion project stays `untested`, the 100th flips
  to `observing`; 5 duplicate webhook deliveries of one `event_id` count as **1**; a seeded >5h/7d attention load
  makes `launch-gate check` exit 1.
- **S3:** every `status:"ok"` capability returns 0 on `--help`; a deliberately-broken script re-scans to
  `status:"broken"` and is excluded; the live-state block parses from a `docker ps` ≤24h old.
- **S4:** `fabrik launch examples/smoke.yaml` → live waitlist URL 200 within 2h, operator-minutes ≤30.
- **S5:** replay a Paddle `event_id` → still 1 conversion; a Sandbox `adjustment.created` reverses it.
- **S6:** the engine never flags an `untested` project; flags a tested-zero-traction one as `kill_candidate` but
  does not archive without an approval flag; `UPDATE control_state … now()-'25h'` → `launch-gate check` exits 1
  (`operator_absent`); the freeze-list blocks every destructive action in every autonomy tier.

---

## Residuals / open items

**Resolved by this re-grounding:**
- Payments = **vendor `payments/`**, not build (was the plan's largest latent defect at 2026-07-12).
- `webhook_events` = provided by `payments/`, not a factory build.
- All counts refreshed; all absence/exists anchors re-confirmed; Paddle + iyzico re-verified current.

**Still open (each with a named resolution step):**
1. **BLOCKING (operator, not self-resolvable) — Paddle/iyzico accounts + keys.** Gates **S5 only**. Resolution:
   operator opens Paddle (Sandbox+Live) + iyzico merchant accounts and sets `PADDLE_API_KEY`,
   `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_ENVIRONMENT` (+ TR `IYZICO_API_KEY`,
   `IYZICO_SECRET_KEY`, `IYZICO_ENVIRONMENT`) in `.env`. S1–S4 + S6-core proceed without it.
2. **Empirical, not a plan gap (stated bets):** the hit-rate / distribution thesis (whether enough launches
   convert — its own out-of-scope plan) and the effort-multiplier (~2.5×, first measured at S4's timing gate).
3. **Decision, low-risk:** Shamir break-glass tool for the >30d dead-man's-switch — `ssss` (2-of-3) armed at
   first graduate; interim `age`-encrypted bundle. Resolution: `apt install ssss` at graduation (verified not
   installed today).
4. **Design-time choice for S4:** which of the 20 template dirs is the one canonical monetizable scaffold
   (`saas-skeleton` is the likely default). Resolve in the S4 sub-spec, not here.

**Not promising "100% / zero unknowns":** the re-grounding closed the factual + vendor-verdict layer; the
empirical bets (hit-rate, effort) are unprovable pre-build and the payments prerequisite is an operator action.

---

## Handoff

On approval, each sub-spec runs its own pipeline — **start with S1** (`/fabrik-spec` for the do-not-die floor;
it needs no accounts and is the serial prerequisite). This program spec is the charter the sub-specs inherit:
the vendor verdicts (esp. `payments/`, `fastapi-user-auth/`, `webhooks/`, `cost-budget/`, `watchdog/`) and the
grounded external facts (Paddle/iyzico) carry forward — sub-specs re-ground only their own slice.

💡 **fabrik-lib candidates:** none surfaced (the four BUILD items are hub-governance-specific, not generic).
