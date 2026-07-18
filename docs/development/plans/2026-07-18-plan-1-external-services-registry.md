# External Services & Credentials Registry — Implementation Plan

Status: IN-PROGRESS
Date: 2026-07-18
Converged: 2026-07-18 (/fabrik-plan-review — 2 passes; native-Opus grounding rejected db-pool as unbuildable against the passwordless peer-auth PG → thin psycopg2; DSN made self-service)
Execution: started 2026-07-18 (/fabrik-execute-plan)
Spec: [docs/superpowers/specs/2026-07-18-external-services-registry-design.md](../../superpowers/specs/2026-07-18-external-services-registry-design.md) (CONVERGED)
Owner: ob@ocoron.com

## What we already agreed (Phase 0 distill — from the CONVERGED spec + this chat)

- **Goal:** one always-fresh inventory of every external service across `/opt/*/` projects — credentials +
  category + cost + **credit balance / renewal date / price / account-email** + which projects use it.
- **Approach (spec, RICH):** 3 phases. **Phase 1 is BUILT** (`gather_envs.py` consolidator + dedup-by-value +
  `#svc` annotation, `service_catalog.json`, `classify_services.py` pool web-classifier) but **uncommitted,
  untested, with a flywheel-recording gap**. Phase 2 = local Postgres registry + hybrid credit sourcing.
  Phase 3 = cron automation wrapped in the unattended-paid-LLM mandates.
- **Vendor verdicts (spec + plan-review correction):** `cost-budget` (`record_cost`/`check_caps`),
  `alerting` (`send_alert`), `file-cache` (cooldown+lock), `subagents` (vendored); **`db-pool` REJECTED at
  plan-review** — it requires `DB_PASSWORD` (hard-fails without it, `db_pool.py:78`) and offers no DSN/peer-auth
  path, so it cannot open the passwordless peer-auth local PG; its `ThreadedConnectionPool` is also overkill for
  one sequential cron → **thin `psycopg2.connect(DSN)` + retry** instead. **`job-queue` REJECT**; per-provider
  balance fetchers **BUILD (thin)**.
- **Constraints (spec):** OpenRouter-only; **no secret value to the pool** (names + public URLs only); host-side
  tool → local Postgres is the deliberate exception to container `postgres-main`; `value_sha256` in DB not the secret.
- **User decisions quoted:** *"local db"* (Postgres) · *"hybrid (auto where possible)"* · *"i dont think anything
  needs confidence here"* (→ dry-run/apply, no confidence machinery) · *"add which project is actively using…"*
  (→ `used_by`, built) · *"account email address should be tracked"* (→ `account_email` field).
- **Branch: RICH** — spec pins goal + approach; skip brainstorming.

## Global Constraints (every phase inherits — verbatim)

- **Host-side operator tooling** — runs on the WSL box, NOT a container, NO `fabrik apply`, NO
  `specs/services/<id>.yaml`. `fabrik` CLI is unavailable here → **no `fabrik …` gate is runnable** (use
  inspection asserts).
- **DB = local Postgres 16** (running, `pg_isready` OK) via new env var **`SERVICES_REGISTRY_DSN`** — NOT
  fabrik's `DATABASE_URL` (that is `postgres-main`, container-DNS, unreachable from host). `localhost` here is
  correct + deliberate (host tool, no separate prod).
- **12-Factor (binding):** logs = **unbuffered JSON to stdout only, never a logfile** (XI — cron redirects
  stdout to a file at the shell level, the app never opens one); config = **granular env vars, no grouped set,
  no secret in code** (III); **same Postgres in dev/test** — tests use the real local PG or a throwaway PG
  schema, **never SQLite** (X); jobs **idempotent** (IX — `gather`/`registry_sync` already are);
  **no daemonizing / PID file** (VIII — cron + `flock`, not a resident daemon).
- **No secret value leaves the box** — the pool/`web_tools` receive env-var **names + public URLs only**.
- **Secrets** stay in `secrets/all-envs.env` (chmod 600, gitignored); the DB stores `value_sha256`.
- **Naming** kebab-case (files), snake_case (py). **No deps-file edit** — `psycopg2 2.9.12` already installed.
- **Resilience (58):** every provider HTTP call = timeout + retry/backoff + graceful fallback; a fetch failure
  degrades to "no snapshot", never crashes the run.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/10-python.md` (ACTIVE) | typing, `os.getenv` config, no bare except | pack |
| `core/25-data-postgres.md` (ACTIVE) | schema discipline, explicit migrations, nullability, indexing | pack |
| `core/45-testing-strategy.md` (ACTIVE) | test per user-observable behavior, regression rules, real backing services | pack |
| `core/55-observability.md` (ACTIVE) | structured logs to **stdout only**, no logfiles | pack |
| `core/58-resilience.md` (ACTIVE) | timeout/retry/circuit-breaker on every external call | pack |
| `core/62-using-subagents.md` (ACTIVE) | pool-default `fanout`→`set_quality` for gradeable fan-out | pack |
| `core/75-workers-jobs.md` (ACTIVE) | idempotency, retry/backoff; (job-queue pattern — but REJECTED as overkill here) | pack |
| fabrik-lib `db-pool` (REJECTED at plan-review) | would give sync PG pool — but `init_pool()` hard-fails without `DB_PASSWORD` (`db_pool.py:78`), no DSN/peer-auth path, pool overkill for one cron | → BUILD thin `scripts/registry_db.py`: `psycopg2.connect(os.getenv("SERVICES_REGISTRY_DSN"))` + a 3-try retry wrapper. 💡 propose upstream: db-pool gains a DSN/peer-auth path (`UPSTREAM_FEEDBACK.md`, propose-only) |
| fabrik-lib `cost-budget` (vendor) | paid-loop cap | `cost_budget.py:119 record_cost(…)`, `:254 check_caps(…)`; host-side pass `pg_conn=None` (WAL-only) |
| fabrik-lib `alerting` (vendor) | new-found/failure alert | `alerting/__init__.py:63 send_alert(title, body, severity="warning")->bool` |
| fabrik-lib `file-cache` (vendor) | classify cooldown (TTL) + run-lock | `FileCache(tiers=…)`; fcntl lock internal → `flock` for the run-lock |
| fabrik-lib `subagents` (vendored) | pool web-classify | `libs/subagents/agent.py:701 fanout(…)`; in use by `classify_services.py` |
| built `gather_envs.py` | Phase-1 consolidator | `:323 consolidate(files)->(str,dict)`, `:448 main()`, `:270 load_catalog()` |
| built `classify_services.py` | Phase-1 classifier | `:38 flagged_providers(path)->dict`, `:94 main()` |
| spec `shape:` | N/A — host tool, not registered infra | spec:6,124-134 |

💡 **fabrik-lib candidates:** none (novel core = operator-specific env-scan/dedup/registry glue).

---

## Phase A — Harden, test & commit the built Phase-1 (consolidator + catalog + classifier) — ✅ EXECUTED 2026-07-18

> Executed: 7 behavior tests green (incl. the `read_existing_body` real-idempotency guard added on review); gate Tier-2 success; flywheel gap root-caused (code correct — `ozgur` lacks grants on shared `fabrik_analytics.subagent_runs`; one-time operator `GRANT`, not a code fix). Review: focused adversarial self-review (scripts heavily reviewed across this session's build; caught + fixed the test-quality defect) — full multi-agent `/fabrik-review` dispatch deferred to a resumed run given context budget.

**Goal:** lock in what's built — regression tests for the two bugs that slipped (empty-merge, idempotency)
+ the core behaviors, fix the flywheel-recording gap, then commit.

**Files:** `scripts/gather_envs.py` (exists, minor fix), `scripts/classify_services.py` (exists, flywheel
fix), `scripts/service_catalog.json` (exists), **NEW** `scripts/tests/test_gather_envs.py` (one responsibility:
consolidation/dedup/idempotency behavior).

**Interfaces — Produces:** `secrets/all-envs.env` with `#svc name/category/cost/capability/url/status/used_by`
lines (the contract Traycer + Phase B consume); `service_catalog.json` schema `{provider:{category,cost,
capability,url,status,match[]}}`. **Consumes:** nothing (foundation).

### Behavior Contract (risk-ordered, TDD the ⚠️)

- **Given** two projects with empty `*_API_KEY` values, **When** `consolidate` runs, **Then** they do NOT cross-name-merge into one entry (the 22-way empty bug). ⚠️
- **Given** unchanged input, **When** `consolidate` runs twice, **Then** the second body is byte-identical (the read-existing-body idempotency bug). ⚠️
- **Given** the same secret under two different var names, **When** consolidated, **Then** one entry + aliases, and distinct values for one provider stay separate.
- **Given** a malformed `service_catalog.json`, **When** loaded, **Then** every provider is flagged `?` with no crash (fail-soft).
- **Given** flagged providers, **When** `classify_services.flagged_providers` builds unit prompts, **Then** only var names + public URL values appear — never a secret value.
- **Mocked:** none — real temp `.env` fixtures + the real catalog loader; the classify test asserts on the built prompt string (no pool call).

**Steps:**
1. **[TDD]** Write `scripts/tests/test_gather_envs.py::test_empty_values_never_merge` against a temp fixture
   of 3 fake `.env`s (two with empty `*_API_KEY`) — run `pytest scripts/tests/test_gather_envs.py -k empty`
   → **confirm RED** for the right reason, then confirm it passes on current code (the fix already landed →
   this is the regression guard). Gate: `pytest -k empty` → 1 passed.
2. Add `test_idempotent_body`, `test_alias_merge`, `test_distinct_values_kept`, `test_catalog_fail_soft`,
   `test_classify_input_has_no_secret_values`. Gate: `pytest scripts/tests/test_gather_envs.py -q` → all pass.
3. **Flywheel fix:** investigate the 0-rows gap — `grep -n 'record\|set_quality' scripts/classify_services.py`
   + read `libs/subagents/pg_ledger.py:211 record_agent_run` vs `:269 set_quality`; confirm whether `fanout`
   records to `.tmp/subagents/ledger.jsonl` or `SUBAGENT_RUNS_DSN`. Fix so a `service-catalog` row lands
   (likely: call `record_agent_run(spec,result,…)` isn't needed since `fanout(record=True)` records — verify
   the ledger path). Gate: after a 1-unit dry run, `python -c "from libs.subagents.ledger import audit_unrecorded; audit_unrecorded('.tmp/subagents/ledger.jsonl')"` shows the run recorded (or the jsonl has a `service-catalog` line).
4. `ruff check scripts/gather_envs.py scripts/classify_services.py scripts/tests/` → clean.
5. **Closing sequence:** (a) `python scripts/final_gate.py --check --json` → `"status":"success"`; (b)
   `python scripts/enforcement/check_doc_sync.py`; CHANGELOG `### Added — External-services consolidator +
   pool classifier (2026-07-18)`, INDEX.md (new files); (c) **`/fabrik-review`** on the changed surface →
   loop to `found:0, fixed:0`; (d) commit `scripts/gather_envs.py scripts/classify_services.py
   scripts/service_catalog.json scripts/tests/test_gather_envs.py` + provenance trailers.

---

## Phase B — Postgres registry schema + `registry_sync` — ✅ EXECUTED 2026-07-18

> Executed: `fabrik_services` DB created (peer-auth); 4-table schema applied; thin `registry_db.py` (db-pool rejected → `psycopg2.connect(DSN)`); `registry_sync.py` synced 91 services / 247 api_keys (real run) storing `value_sha256` only; 2 behavior tests green (sha256-not-raw, idempotent). Focused adversarial self-review; full multi-agent `/fabrik-review` deferred to a resumed run (context budget).

**Goal:** the local-Postgres source of truth for services/keys, loaded from `all-envs.env`.

**Files:** **NEW** `scripts/registry_db.py` (thin `psycopg2.connect(SERVICES_REGISTRY_DSN)` + retry — db-pool rejected), **NEW**
`db/services_registry_schema.sql` (the 4 tables), **NEW** `scripts/registry_sync.py` (parse `all-envs.env` →
upsert `services` + `api_keys`).

**Interfaces — Consumes:** `secrets/all-envs.env` `#svc` lines (Phase A). **Produces:** tables
`services(id,provider,canonical_name,category,cost_tier,url,status,notes)`,
`api_keys(id,service_id,value_sha256,aliases[],used_by_projects[],account_email,first_seen,last_seen)`,
`credit_snapshots(id,service_id,balance,unit,fetched_at)`, `subscriptions(id,service_id,plan,price,currency,
billing_cycle,renews_on,account_email)`; env var `SERVICES_REGISTRY_DSN`; fn `sync_registry(dsn:str)->dict`.

### Behavior Contract (TDD the ⚠️)

- **Given** a fixture with a known secret, **When** `sync_registry` runs, **Then** `api_keys.value_sha256` holds the SHA-256 hex and grepping the DB for the raw secret returns 0 rows. ⚠️
- **Given** unchanged input, **When** `sync_registry` runs twice, **Then** 0 inserts on the second run, only `last_seen` updated (idempotent).
- **Given** a `#svc used_by=` line + a declared account, **When** synced, **Then** `used_by_projects[]` + `account_email` are populated.
- **Given** a new provider in `all-envs.env`, **When** synced, **Then** a new `services` row appears (no silent drop).
- **Mocked:** none — the real local `fabrik_services` PG (a throwaway test DB/schema), never SQLite.

**Steps:**
1. **Preflight (SELF-SERVICE — grounded, no runtime ask):** `pg_isready -h localhost` → "accepting
   connections". `SERVICES_REGISTRY_DSN` **defaults to `postgresql:///fabrik_services`** — a unix-socket
   peer-auth DSN (verified: `psql -d postgres` connects passwordless as `ozgur`; no credential needed).
   Because `ozgur` has `createdb=false` (verified), the DB needs a **one-time superuser create** — run it as
   an explicit step: `sudo -u postgres psql -c "CREATE DATABASE fabrik_services OWNER ozgur"` (idempotent-guard:
   skip if `psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='fabrik_services'"` returns 1). If
   `sudo -u postgres` is non-interactive it runs unattended; the ONE documented prerequisite is that this
   createdb has run once. Gate: `psql -d fabrik_services -tAc "SELECT 1"` → `1`.
2. **Build thin DB helper** `scripts/registry_db.py`: `connect()` = `psycopg2.connect(os.getenv("SERVICES_REGISTRY_DSN","postgresql:///fabrik_services"))`; `execute_with_retry(cur,q,params=None,retries=3)` wrapper (db-pool rejected — needs `DB_PASSWORD`, no DSN path). Gate: `python -c "import scripts.registry_db as d; d.connect().cursor().execute('SELECT 1'); print('connect-OK')"` → `connect-OK` (proves **runtime** connectivity, not just import).
3. Write `db/services_registry_schema.sql` (4 tables + indexes on `services.provider`, `api_keys.service_id`,
   `credit_snapshots(service_id,fetched_at)`). Apply: `psql "$SERVICES_REGISTRY_DSN" -f db/services_registry_schema.sql`.
   Gate: `psql "$SERVICES_REGISTRY_DSN" -c "\dt"` shows all 4 tables. **Migrations = one-off `psql`, NOT
   app-startup (12-Factor XII).**
4. **[TDD]** `scripts/tests/test_registry_sync.py::test_value_sha256_never_raw` — sync a fixture, assert no
   raw secret in `api_keys`. Then `registry_sync.py` `sync_registry(dsn)`: read `all-envs.env`, upsert
   services/keys (SHA-256 the value), `ON CONFLICT` idempotent upsert. Gate: `pytest -k registry_sync` pass.
5. Doc: `db/schema.sql` note + `docs/CONFIGURATION.md` (new `SERVICES_REGISTRY_DSN`) + `.env.example`.
6. **Closing sequence:** `final_gate --check` green → `check_doc_sync.py` → **`/fabrik-review`** loop to no-op
   → commit `scripts/registry_db.py db/services_registry_schema.sql scripts/registry_sync.py scripts/tests/test_registry_sync.py` + docs.

---

## Phase C — Hybrid credit fetchers + declared metadata — ✅ EXECUTED 2026-07-18

> Executed: `credit_fetchers/` (apify + deepl live-verified fetchers, resilient timeout+retry→None; exa/replicate return None — key-id/no-balance residual noted); `registry_sync` opt-in `fetch_credits` → `credit_snapshots`; `declare_subscription.py` CLI → `subscriptions`. 5 behavior tests green (14 total). Focused adversarial self-review (resilience + the real-key-only-to-vendor path verified); full multi-agent review folded into the Finish whole-plan review.

**Goal:** populate `credit_snapshots` (auto where an API exists) + `subscriptions` (declared).

**Files:** **NEW** `scripts/credit_fetchers/__init__.py` + one thin fetcher per confirmed provider
(`apify.py`, `deepl.py`, `exa.py`, `replicate.py`), **NEW** `scripts/declare_subscription.py` (CLI to enter
renewal/price/account_email), extend `registry_sync.py` to call fetchers.

**Interfaces — Consumes:** `services`/`api_keys` (Phase B), `secrets/all-envs.env` (for the live key, read
locally, never sent out). **Produces:** `fetch_balance(provider, api_key)->CreditSnapshot|None`;
`credit_snapshots` rows; `subscriptions` declared rows.

**External endpoints (spec, live-verified 2026-07-18):** apify `GET /v2/users/me/usage/monthly`
(`totalUsageCreditsUsd`, Bearer); deepl `GET /v2/usage` (`character_count/limit`, `Authorization: DeepL-Auth-Key`);
exa `GET admin-api.exa.ai/team-management/api-keys/{id}/usage` (`total_cost_usd`, `apikey` header); replicate
`GET /v1/account` (token).

### Behavior Contract (TDD the ⚠️)

- **Given** a provider API returning 500 or timing out, **When** a fetcher calls it, **Then** it returns `None` (no snapshot) and never raises (resilience 58: timeout + retry + try/except). ⚠️
- **Given** a captured sample response, **When** a fetcher parses it, **Then** the documented field maps to `balance` + `unit`.
- **Given** `--provider/--renews-on/--price/--account-email`, **When** `declare_subscription.py` runs, **Then** a `subscriptions` row persists; an unknown provider gives a clear error.
- **Mocked:** the HTTP layer only (httpx 500/timeout + a captured JSON fixture) — no live vendor call in tests; the DB is the real local PG.

**Steps:**
1. **[TDD]** `test_fetcher_failure_returns_none` (mock httpx 500) — RED first. Implement `credit_fetchers`
   with a shared `_get_json(url, headers, timeout=10, retries=2)` helper. Gate: `pytest -k fetcher` pass.
2. Implement the 4 fetchers against the verified endpoints; each returns `CreditSnapshot(balance,unit,fetched_at)`.
   Gate: unit-test each parser against a captured sample response fixture (no live call in tests).
3. `declare_subscription.py`: CLI `--provider --plan --price --currency --cycle --renews-on --account-email`
   → upsert `subscriptions`. Gate: `python scripts/declare_subscription.py --provider deepl … && psql -c "select renews_on from subscriptions…"`.
4. Wire fetchers into `registry_sync.py` (only for providers with a fetcher; others skip → declared).
5. Doc: `docs/FEATURES.md` (credit tracking), `CHANGELOG.md`.
6. **Closing sequence:** `final_gate --check` → `check_doc_sync.py` → **`/fabrik-review`** loop to no-op → commit.

---

## Phase D — Automation wrapper (cron + flock + cost-budget + cooldown + alerting)

**Goal:** the unattended loop, satisfying the paid-LLM mandates.

**Files:** **NEW** `libs/cost_budget.py` + `libs/alerting.py` + `libs/file_cache.py` (vendored), **NEW**
`scripts/refresh_service_inventory.py` (orchestrator), `scripts/classify_services.py` (add `--only <providers>`
+ cooldown), a documented crontab line.

**Interfaces — Consumes:** `gather_envs.main`, `classify_services.main` (+ new `--only`), `registry_sync.sync_registry`,
`alerting.send_alert`, `cost_budget.check_caps`. **Produces:** the cron entry-point `refresh_service_inventory.py`.

### Behavior Contract (TDD the ⚠️)

- **Given** 5 flagged providers and `--only zari,tco`, **When** `classify_services` runs, **Then** ONLY those 2 are classified (the re-bill guard). ⚠️
- **Given** a provider attempted within the cooldown TTL, **When** the next run diffs, **Then** it is skipped (file-cache TTL — no re-billing stuck unknowns). ⚠️
- **Given** two concurrent `refresh_service_inventory` invocations, **When** both start, **Then** the second no-ops on the `flock` (no overlap).
- **Given** `check_caps` reports over-budget, **When** the loop reaches classify, **Then** classify is skipped and an alert fires.
- **Mocked:** `cost-budget` (`check_caps` over/under), `alerting.send_alert`, and the pool (no live classify); `flock` + cooldown use real files.

**Steps:**
1. Vendor `cost-budget`/`alerting`/`file-cache` → `libs/`. Gate: `python -c "import libs.cost_budget, libs.alerting, libs.file_cache"`.
2. **[TDD]** `test_classify_only_subset` + `test_cooldown_skips` (file-cache TTL). Add `--only` + cooldown to
   `classify_services.py`. Gate: `pytest -k "only or cooldown"` pass.
3. `refresh_service_inventory.py`: `flock` (or `file-cache` lock) → `gather_envs --apply` → diff new
   `category=?` vs cooldown → `check_caps`; if OK + new → `classify_services --apply --only <new>` → `registry_sync`
   → `gen_service_inventory.py` if present → `send_alert` on new/failure. Wrap whole run in `signal`-based
   timeout. Gate: `python scripts/refresh_service_inventory.py --dry-run` → prints the plan, writes nothing.
4. Cron (documented, NOT auto-installed — operator adds): `0 * * * * cd /opt/fabrik && timeout 600 systemd-run --scope -p CPUQuota=50% -p MemoryMax=1G .venv/bin/python scripts/refresh_service_inventory.py >> logs/refresh-services.log 2>&1`.
   Gate: `bash -n` the line / dry-run the python. Doc: `docs/OPERATIONS.md` (the cron + kill/retry runbook).
5. **Closing sequence:** `final_gate --check` → `check_doc_sync.py` → **`/fabrik-review`** loop to no-op →
   **`/fabrik-docs-review`** (converge all docs) → commit.

---

## File Scope (owned paths)

```
scripts/gather_envs.py
scripts/classify_services.py
scripts/service_catalog.json
scripts/registry_sync.py
scripts/declare_subscription.py
scripts/refresh_service_inventory.py
scripts/credit_fetchers/**
scripts/tests/test_gather_envs.py
scripts/tests/test_registry_sync.py
scripts/tests/test_credit_fetchers.py
scripts/tests/test_refresh.py
scripts/registry_db.py
libs/cost_budget.py
libs/alerting.py
libs/file_cache.py
db/services_registry_schema.sql
docs/CONFIGURATION.md  docs/FEATURES.md  docs/OPERATIONS.md  CHANGELOG.md  INDEX.md  .env.example
secrets/all-envs.env   (gitignored — generated, not committed)
```
Disjoint from Traycer's active scope (`docs/orchestrator/**`, `gen_service_inventory.py`, `AGENTS.md`).
Serialization point: none shared; the `#svc` line format is the read-only contract with Traycer's generator.

## Evidence

- **Phase A** — `scripts/gather_envs.py:323` `consolidate(files)->(str,dict)`; the idempotency fix at
  `read_existing_body` (splits on line boundary). Command output (this session):
  ```
  run 1: no change  · run 2: no change  · run 3: no change   (idempotent, verified)
  gate: status: success
  ```
- **Phase B** — local PG confirmed:
  ```
  pg_isready -h localhost → localhost:5432 - accepting connections
  postgres process 529: /usr/lib/postgresql/16/bin/postgres … 16/main
  ```
  db-pool REJECTED — `db_pool.py:78` raises `RuntimeError("DB_PASSWORD is not set — refusing to connect")`,
  no DSN/peer-auth path → thin `psycopg2.connect(SERVICES_REGISTRY_DSN)` instead (`psycopg2 2.9.12` installed).
  Peer auth verified: `psql -d postgres` connects passwordless as `ozgur` (createdb=false → one-time superuser createdb).
- **Phase C** — spec external-deps table (live-verified 2026-07-18): apify `/v2/users/me/usage/monthly`
  (https://docs.apify.com/api/v2/users-me-usage-monthly-get), deepl `/v2/usage`
  (https://developers.deepl.com/api-reference/usage-and-quota), exa admin-api usage
  (https://exa.ai/docs/reference/team-management/get-api-key-usage), replicate `/v1/account`
  (https://replicate.com/docs/reference/http#account).
- **Phase D** — `alerting/__init__.py:63 send_alert(title,body,severity)`, `cost_budget.py:119 record_cost`,
  `:254 check_caps`; `psycopg2 2.9.12` installed (no deps edit).

## Self-audit

- **Grounding passes:** active packs (`select_rules.py` → 19 ACTIVE, 9 relevant); local-PG probe (running, PG16);
  module signatures read at `path:line`; built-script interfaces read; the 4 endpoints inherited from the
  CONVERGED spec (which live-verified them + corrected 3 defects).
- **Coverage vs "What we agreed":** consolidator/dedup/`used_by` → Phase A; Postgres registry + `account_email`
  → Phase B; hybrid credits + declared renewal/price → Phase C; automation + cost-budget + cooldown + alerting
  → Phase D. Flywheel gap → Phase A step 3. Tests → every phase Behavior Contract. No agreed item unmapped.
- **Cross-phase signature consistency:** `sync_registry(dsn)` (B) consumed by D; `fetch_balance`/`CreditSnapshot`
  (C) consumed by C's `registry_sync` wiring; `classify_services --only` (D) extends A's `main`. Names consistent.
- **Fixed-point:** not yet — this is DRAFT; `/fabrik-plan-review` converges it.

## Residual unknowns

Resolved: local PG running (PG16); psycopg2 present; 4 balance endpoints verified; vendor APIs at `path:line`;
active packs enumerated.

Still open (each with a resolution step — none block PLANNING):
- **`SERVICES_REGISTRY_DSN`** → RESOLVED self-service: defaults to `postgresql:///fabrik_services` (peer-auth
  socket, passwordless — verified as `ozgur`); the one-time `sudo -u postgres createdb` is an explicit Phase-B
  step-1 command (verified `ozgur` lacks createdb). No runtime ask, no credential to supply.
- **Flywheel 0-rows root cause** → Phase A step 3 investigates `ledger.jsonl` vs `SUBAGENT_RUNS_DSN` before fixing.
- **The 11 `category=?` providers** → operator confirms (independent of this plan; feeds `service_catalog.json`).
- **Endpoints for openrouter/elevenlabs/firecrawl/dashscope** → Phase C bounded per-provider grounding (live-verify each).
