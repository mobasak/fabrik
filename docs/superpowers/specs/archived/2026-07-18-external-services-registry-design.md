# External Services & Credentials Registry — Design Spec

Status: CONVERGED
Date: 2026-07-18
Converged: 2026-07-18 (/fabrik-spec-review — 3 passes; all 3 cited billing endpoints were defective and corrected against live docs)
Owner: ob@ocoron.com
Type: operator-side host tooling (NOT a deployed container / not a scaffolded fabrik service)

## Goal

One authoritative, always-fresh inventory of **every external service used across all `/opt/*/`
projects**, keyed by the *service/provider*, carrying its credential(s) **plus** billing
intelligence — current credit/balance, subscription renewal date, price, and the account email
that owns the key. It answers, in one place: *what external services do we depend on, which
project uses each, what does each cost, how much credit is left, and when does it renew* — so
procurement (free → cheapest-paid → build) and renewal/credit awareness stop being tribal
knowledge.

Replaces the retired `scripts/consolidate_envs.py` (the old ".env merger" that "caused many
issues").

## Decomposition (one system, three phases — build in order)

| Phase | Scope | Status |
|---|---|---|
| **1 — Consolidation + catalog + classify** | scan `/opt/*/.env` → deduped, category-grouped, `#svc`-annotated `secrets/all-envs.env`; durable `service_catalog.json`; pool-based web classifier for unknowns | **BUILT** (this session) — retro-captured here |
| **2 — Registry (the main new work)** | local Postgres registry of services/keys/**credits/renewals/prices/account-email**; hybrid credit sourcing (auto-fetch where a balance API exists, declared otherwise) | **TO BUILD** |
| **3 — Automation** | cron gather (cheap, hourly) + event-gated classify (paid, only-on-new-provider) wrapped in the fabrik unattended-paid-LLM mandates | **TO BUILD** |

Phases 2 and 3 are separable: the registry (2) is useful without full automation; automation (3)
wraps existing scripts. Phase 1 is the shared foundation both consume.

## Chosen approach

**Phase 1 (built).** `scripts/gather_envs.py` scans every `/opt/*/.env` (excluding fabrik's own
`.env` + the output), skips empty values, and writes `secrets/all-envs.env` (chmod 600,
gitignored). Secrets dedupe **by value** (same credential under different names → one line +
aliases; distinct values always kept). Output is grouped by capability category with a
machine-parseable `#svc name=… category=… cost=… capability=… url=… status=… used_by=…` line per
provider, injected from the durable `scripts/service_catalog.json` (fail-soft if malformed).
Idempotent (byte-compare of the body; no-op when unchanged → no watcher churn). Uncatalogued
providers auto-flag `category=?` (never silently dropped). `scripts/classify_services.py`
web-grounds the flagged ones via the OpenRouter pool (`libs/subagents.fanout`, cheap models,
**names + public URLs only — never a secret value**), returning `?` rather than inventing.
A peer AI (Traycer) owns the downstream `gen_service_inventory.py`, which reads `#svc` + key
names only (no values) → the `#svc` line is the contract between the two.

**Phase 2 (registry).** A local Postgres schema is the source of truth for billing intelligence
that a flat file can't hold (values that change over time + human-declared metadata):

```
services         (id, provider, canonical_name, category, cost_tier, url, status, notes)
api_keys         (id, service_id, value_sha256, aliases[], used_by_projects[], account_email,
                  first_seen, last_seen)              -- value_sha256, NOT the secret itself
credit_snapshots (id, service_id, balance, unit, fetched_at)        -- time-series (burn-down)
subscriptions    (id, service_id, plan, price, currency, billing_cycle, renews_on, account_email)
```
`gather_envs` remains the ingestion front-end (upserts services/keys); a new `registry_sync.py`
loads its output into Postgres. **Hybrid credit sourcing:** for providers whose API exposes a
balance/usage endpoint, a per-provider fetcher writes `credit_snapshots`; renewal dates + prices
+ account_email are **declared** (operator-entered; not public). The `#svc status`/`used_by` +
`account_email` unify the file view and the DB view.

**Phase 3 (automation).** A thin `refresh_service_inventory` wrapper, cron-hourly, under a
`flock`/`file-cache` run-lock + `timeout`/`systemd-run --scope` caps:
`gather_envs --apply` (cheap, always) → diff `category=?` vs a seen/cooldown set → for genuinely
**new** providers only, `classify_services --apply --only <new>` (wrapped in `cost-budget`) →
`gen_service_inventory.py` → `alerting.send_alert()` on new-found/failure. `classify` is **never** on a
fixed frequent schedule (it is paid); `gather` is cheap+idempotent so hourly is free.

## Rejected alternatives (+ why)

- **Old `consolidate_envs.py` (merge all `.env` into fabrik's own `.env`)** — REJECTED: dedup-by-key-name
  flattened distinct values (every project's `DATABASE_URL` collapsed to one → wrong DB); writing into
  `/opt/fabrik/.env` triggered the DR watcher loop + polluted fabrik's runtime. (This is the "caused many
  issues" system.) → separate gitignored file + dedup-by-value + idempotent no-op.
- **`claude -p haiku` for classification** — REJECTED: recreates the youtube 33k-session-file pollution in
  `~/.claude`, records nothing to the flywheel, uses the subscription instead of metered cheap models. The
  pool (`fanout`) is HTTP-only (no session files) + flywheel-recorded.
- **`job-queue` for the automation** — REJECTED: Postgres queue + forked worker pool is overkill for a
  periodic host cron. `flock` + `timeout` + `cost-budget` + a cooldown file is right-sized.
- **Single YAML / SQLite storage** — REJECTED by owner in favour of local Postgres (history/queries/renewal
  alerts).
- **inotify watcher for freshness** — REJECTED: the fragile rename/temp-file-race + cascade path the old
  system hit. Cron (idempotent no-op) is robust; missed ticks while WSL is down are simply skipped (crontab,
  not anacron) → no pile-up.
- **Confidence-scoring / gating the classifier writes** — REJECTED by owner as over-engineering; kept only
  the "return `?` if web-search can't identify it" anti-hallucination floor + a dry-run→apply human glance.

## External dependencies (live-verified 2026-07-18 by native Opus /fabrik-spec-review)

The hybrid credit-sourcing decision requires that a meaningful subset of providers expose a
balance/usage API. ⚠️ The *initial* pool citations were all defective (1 hallucinated, 1 dead URL, 1
stale) — corrected below against the real docs by the authoritative Opus pass:

| Provider | Balance/usage API | Endpoint | Auth | Source (fetched 2026-07-18) |
|---|---|---|---|---|
| Apify | yes | `GET /v2/users/me/usage/monthly` (`totalUsageCreditsUsd`) + `GET /v2/users/me/limits` | Bearer token | https://docs.apify.com/api/v2/users-me-usage-monthly-get |
| DeepL | yes | `GET /v2/usage` (`character_count` / `character_limit`) | `Authorization: DeepL-Auth-Key` | https://developers.deepl.com/api-reference/usage-and-quota |
| Exa | yes | `GET admin-api.exa.ai/team-management/api-keys/{id}/usage` (`total_cost_usd`) | `apikey` header | https://exa.ai/docs/reference/team-management/get-api-key-usage |
| Replicate | yes | `GET /v1/account` | token | https://replicate.com/docs/reference/http#account |

Correction detail (kept as a build-time warning): Apify `/v2/users/me` returns only *plan-level* limits,
not usage → use `/usage/monthly`; DeepL's endpoint was right but the cited URL 404'd; Exa's `GET /user/usage`
does **not exist** (account balance is dashboard/Stripe-only; per-key *usage* is the admin-api path above).

- **OpenRouter, ElevenLabs, Firecrawl, DashScope** — grounding run truncated (pool capped mid-search); NOT
  re-confirmed live. NOT a design blocker: the design assumes *no specific* provider API; per-provider
  endpoint enumeration is a **bounded Phase-2 task** (same pool grounder, but each endpoint re-verified by a
  live fetch — the defects above prove pool citations alone are unreliable), and any provider without an
  auto-endpoint falls back to **declared** credits. Resolution step: live-verify + record each endpoint in
  the catalog during Phase-2 build.
- **OpenRouter pool** (`libs/subagents.fanout`) — vendored + in use; `OPENROUTER_API_KEY` present. Web tools
  `exa`/`brave` (`web-tools/`) keys present.

## fabrik-lib vendor→enhance→build verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| Parallel web-grounded classification of unknown providers | **VENDOR (done)** | `subagents` (`libs/subagents`) | `fanout` + `web_tools` + flywheel; already powering `classify_services.py` |
| Phase-2 Postgres registry access (sync, from a script/cron) | **VENDOR** | `db-pool` | the documented `core/75-workers-jobs` sync-psycopg2 exception for cron/scripts — correct vs async asyncpg |
| Cost cap on the unattended paid classify loop | **VENDOR** | `cost-budget` | `record_cost()`/`check_caps()` — the fabrik mandate for an unattended paid-LLM loop; local SQLite-WAL fail-open works host-side by passing `pg_conn=None` (keyword-required, no default), shared `cost_ledger` optional — it assumes a fabrik-applied project user |
| Alert on new-provider-found / run failure | **VENDOR** | `alerting` | `send_alert(title, body, severity)` SSH→Apprise→Telegram, never raises, title-dedup (NB: public fn is `send_alert`, not `send`) |
| Classify cooldown (don't re-bill the same unknowns) + run-lock | **VENDOR** | `file-cache` | TTL cache (cooldown) + file-locking (no-overlap); `flock` acceptable for the lock alone |
| Heavy job queue | **REJECT** | `job-queue` | Postgres queue + forked workers = overkill for a periodic host cron |
| Per-provider balance-API fetchers (Phase 2) | **BUILD (thin)** | — | tiny per-vendor HTTP calls; project-local, not a fabrik-lib candidate (vendor-specific glue) |

💡 **fabrik-lib candidates:** none clear the bar — the novel core (env-scan → value-dedup → category/`#svc`
annotation → registry) is operator-specific business logic, not a generic reusable module.

## Shape / infra implications

- **Host-side operator tooling**, NOT a deployed container and NOT a scaffolded fabrik service → **no
  `specs/services/<id>.yaml`, no `fabrik apply`, no Traefik/compose/shape registrars.** The `shape:` contract
  is N/A (nothing is registered infra).
- **Phase-2 DB = the local WSL Postgres** (`localhost`). This is the deliberate, correct exception to the
  container `postgres-main` rule: that rule binds **deployed containers**; this is host infra whose only
  runtime IS the WSL box (no separate prod). Conceptually `needs_database: true`.
- Output `secrets/all-envs.env` + `secrets/` are gitignored (verified); `service_catalog.json` is tracked
  (non-secret metadata). The generated inventory (Traycer) + AGENTS.md pointer hold no secret values.

## Constraints (binding)

- **LLM gateway = OpenRouter only** ✓ (the pool; no direct vendor SDK).
- **No secret value ever leaves the box** — the classifier and the billing grounder receive env-var **names +
  public URLs only**. A secret in a pool/`web_tools` task would exfiltrate.
- **Unattended paid-LLM loop → `cost-budget` + bounded** (pool per-call `max_cost_usd` is the first line; a
  persistent cap via `cost-budget` is the mandate).
- **Never re-bill stuck unknowns** — classify only genuinely-new providers (cooldown/seen-set).
- **Secret-concentration threat model** — Phase 1 aggregates *every* project's `.env` secrets into a single
  host file (`secrets/all-envs.env`), a real blast-radius increase over per-project `.env`s. Accepted for
  single-operator host tooling, mitigated by chmod 600 + gitignore + local-only (never committed, never sent
  to the pool). The Phase-2 DB stores `value_sha256`, not the secret. No further hardening warranted at
  single-operator scale (per the standing threat model — no realistic multi-tenant attacker on the dev box).
- Not-Stripe / not-vector-DB / not-GUI / not-i18n — headless operator tool; those mandates don't apply.

## Open / blocking unknowns

Resolved:
- Storage = local Postgres (owner). Sourcing = hybrid (owner). Dedup = by-value (validated live). Automation
  cadence = gather hourly / classify event-gated (design).
- Hybrid viability = confirmed (4 balance/usage APIs live-verified: apify, deepl, exa, replicate).

Still open (each with a resolution step — none block the DESIGN):
- **Per-provider balance endpoints beyond the 4 confirmed** → bounded Phase-2 grounding task (each re-verified by a live fetch, not pool-citation alone).
- **The 11 `category=?` triage providers** (`boldata/zari/orbisearch/puter` identified pending confirm;
  `captcha/dna/factory/seo/tco/translator` unknown) → operator confirms + one-line catalog entries.
- **Flywheel recording gap** — the pool test showed 0 recorded `service-catalog` rows (`set_quality` didn't
  land / recorded elsewhere) → Phase-2/commit-time fix + verify (`audit_unrecorded`).
- **Behavior tests** — `gather_envs`/`classify_services` ship without regression tests (two real bugs already
  slipped: empty-merge, idempotency-compare) → write before commit.

## Success criteria

1. One `secrets/all-envs.env` with every provider under a category, `#svc`-annotated (name/category/cost/
   capability/url/status/used_by), 0 secret values in any generated (tracked) artifact. ✓ (Phase 1)
2. Postgres registry answers "credit left / renews-on / price / account-email / which projects" per service. (Phase 2)
3. A new project's `.env` or a new provider flows in automatically (gather) and gets auto-classified once
   (classify), never silently dropped, never re-billed on repeat. (Phase 3)
4. The paid loop cannot overspend (cost-budget) and cannot pile up / hang the box (lock + timeout + skip). (Phase 3)
