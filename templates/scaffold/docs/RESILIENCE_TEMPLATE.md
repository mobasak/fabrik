# [Project Name] — Resilience & Autonomy Contract

> **Purpose**: This file is the **operational contract** for [Project Name]. It declares every external dependency, the failure modes that can break the service, and the autonomous detection + recovery posture that makes human intervention optional, not required.
>
> **Inherited from**: `fabrik/templates/scaffold/docs/RESILIENCE_TEMPLATE.md`. The canonical reference implementation is `transcriber/docs/reference/pipeline-resilience.md` (the YouTube pipeline) — read it before rolling your own primitives.
>
> **Standard**: A change to any dependency, quota, credit account, or failure mode MUST update this file in the same PR. CI fails if a new external call site is added without a matching row here (`tests/test_resilience_inventory.py`).

---

## 1. Project Shape Card

| Field                  | Value                |
| ---------------------- | -------------------- |
| Project                | <project>            |
| Type                   | _(fill: python-api / node-api / file-api / file-worker / saas-skeleton / docusaurus / static-site / chrome-extension / mobile-app / desktop-app / wordpress)_ |
| Shape kind             | _(service / worker / static / wordpress)_ |
| `is_public`            | _(true / false)_     |
| `is_admin_dashboard`   | _(true / false)_     |
| `has_bearer_api`       | _(true / false)_     |
| `has_persistent_data`  | _(true / false)_     |
| `needs_database`       | _(true / false)_     |
| `has_search_feature`   | _(true / false)_     |
| `exposes_metrics`      | _(true / false)_     |
| Pause-key namespace    | `<svc>` _(short slug)_ |
| Owner                  | Ozgur Basak          |
| Last drill             | YYYY-MM-DD           |

> Source: `defaults.yaml` `shape:` block. Each flag toggles a Fabrik registrar (see §11).

---

## 2. Dependency Inventory — The Contract

Every external thing this service touches at runtime. **If it's not in §2a, it doesn't exist** — code review rejects new fetch/connect sites without a matching row.

### 2a. Summary Table (scannable index)

| # | Dependency | Class | Criticality | Pause scope | Pause key |
|---|------------|-------|-------------|-------------|-----------|
| 1 | _(e.g. OpenAI API)_  | external_api  | critical | global | `<svc>:pause:openai_credit`  |
| 2 | _(e.g. PostgreSQL)_  | datastore     | critical | global | `<svc>:pause:db`             |
| 3 | _(e.g. R2 / S3)_     | object_store  | high     | global | `<svc>:pause:r2`             |
| 4 | _(e.g. Redis)_       | cache+broker  | critical | n/a (graceful degrade) | — |
| 5 | _(e.g. vendor RL)_   | external_api  | high     | per-token | `<svc>:pause:token:<id>`  |
| 6 | …                    | …             | …        | …      | …                              |

**Classes**: `runtime` (CPU/disk/mem), `external_api`, `datastore`, `cache`, `broker`, `object_store`, `cdn`, `auth`, `dns`, `tls`.
**Criticality**: `critical` (project stops) / `high` (degraded mode acceptable) / `low` (best-effort).

### 2b. Detail Card Per Dependency

For each row in §2a, fill one card. §2a is the index; this is the operational truth.

```
─── <dependency name> ──────────────────────────────────────
Failure signature  : <literal exception types / log substrings to grep>
                     e.g. "Pool exhausted", "402 payment required",
                     "NameResolutionError", "bot_check"
Detection          : reactive (error classifier) | proactive (Beat task) | both
                     mechanism: <classify_transient_error() | <vendor>_balance_check Beat>
                     location: src/error_classifier.py:NN  or  worker/beat.py:NN
Pause key          : <svc>:pause:<resource>
TTL + env var      : 1800s  (env: PAUSE_TTL_<RESOURCE>)
                     re-stamped on each Beat fire while still bad (sliding)
Pause scope        : global | per-job-type:<x> | per-token | per-region | per-key-rotation
Resume trigger     : TTL expiry  |  next Beat sees recovery → clear_pause()
                     |  human top-up + Beat confirms
Jobs affected      : all  |  only <job-type> jobs (and why scope was chosen)
Bloat / dedup note : worker keeps dispatched-flag on pause-skip so
                     sweeper sees "already queued" and doesn't re-push
```

**Worked example 1 — vendor credit (proactive + reactive pause):**

```
─── Soniox Transcription Credit ─────────────────────────────
Failure signature  : "insufficient credit", "payment required", "402"
Detection          : both — proactive Beat task every 15 min reads /v1/usage-logs;
                     reactive classifier matches error patterns.
Pause key          : <svc>:pause:soniox_credit
TTL + env var      : 1800s (env: PAUSE_TTL_SONIOX), re-stamped each Beat fire while < floor
Pause scope        : global (only audio-path jobs need it, but global is simpler)
Resume trigger     : human top-up → next Beat sees balance > $5 → clear_pause()
Jobs affected      : captions-unavailable transcripts (audio path)
Bloat / dedup note : worker keeps dispatched-flag on pause-skip
```

**Worked example 2 — quota with per-job deferral (NOT global pause):**

```
─── YouTube Data API v3 Quota ───────────────────────────────
Failure signature  : Google 403 quotaExceeded, local counter ≥ 9,900/key
Detection          : pre-call check in _ensure_key_with_quota() + reactive 403 catch
Pause key          : NONE (per-job defer_until_pt_midnight() instead)
Reset              : Redis yt_data_api:exhausted:<fp>:<date> TTL =
                     seconds-until-PT-midnight via zoneinfo
Pause scope        : per-job-type (only 5% of jobs touch Data API)
Resume trigger     : TTL auto-expires at exact PT-midnight reset moment
Jobs affected      : watchlist sweep + video enrichment + comments only;
                     captions + audio unaffected
Why not global     : global pause would halt 95% of healthy work for a 5% problem
```

### 2c. Choosing Pause Scope

| Scope                  | Use when                                                                | Example                          |
| ---------------------- | ----------------------------------------------------------------------- | -------------------------------- |
| **global**             | ≥50% of work hits this dep, or partial work isn't valuable              | Postgres down, Redis maxmem      |
| **per-job-type**       | Dep affects only one job class; pausing everything is wasteful          | YouTube Data API → defer_until_* |
| **per-token / per-key**| Multi-tenant — one tenant abusive shouldn't stop others                 | API token rate limit             |
| **per-region / rotation**| Dep has multiple instances; rotate instead of stop                    | 6 YouTube API keys               |

---

## 3. The Universal Pause → Resume → Recover Loop

Every dependency in §2 plugs into this pattern. No exceptions.

```
                ┌───────────────────────────────────┐
                │   pause_state (Redis)             │
                │   key: <svc>:pause:<resource>     │
                │   value: reason + expiry          │
                │   sliding TTL = auto-clears       │
                └────────────┬──────────────────────┘
                             │
   ┌─────────────────────────┼─────────────────────────┐
   │                         │                         │
┌──▼─────────┐         ┌─────▼──────┐         ┌────────▼─────┐
│ Request /  │         │ Dispatcher │         │  Beat tasks  │
│ Job entry  │         │ Scheduler  │         │  (cron)      │
│            │         │            │         │              │
│ if paused: │         │ if paused: │         │ SET pause if │
│   503 +    │         │   skip;    │         │   credit low │
│   Retry-   │         │   row      │         │   /quota hit │
│   After    │         │   stays    │         │ CLEAR if OK  │
│            │         │   orphan   │         │              │
└────────────┘         └────────────┘         └──────────────┘
```

**Three rules:**

1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs before workers fail; error classifiers map exceptions to pause keys on the way through.
2. **Pause is sliding-TTL.** Set/re-stamped by every check; auto-clears when checks stop firing. No human page, no permanent stuck state.
3. **State of truth is the DB**, not the queue. Orphan sweep reconciles anything Redis loses.

---

## 3a. Queue Bloat Prevention

When pause + dispatch interact badly, queues balloon. These five mechanisms keep the message:job ratio exactly 1:1.

| Mechanism | How it works |
|-----------|--------------|
| **Dispatch dedup flag** | `<svc>:dispatched:<job_id>` (TTL 30 min) set on `dispatch_job()`, checked by all sweepers via `_filter_recently_dispatched()` (Redis `MGET`, O(1) per sweep). |
| **Worker keeps flag on pause-skip** | If `is_paused(...)`, worker returns WITHOUT clearing flag → sweepers see "already queued" → no re-push. |
| **Worker clears flag on success** | After pause check passes, `clear_dispatched_flag(job_id)` runs → sweepers may re-dispatch on future retry. |
| **Sweeper headroom** | Sweepers pull **4× their limit**, post-filter against dedup flags, trim to limit. Handles case where top-N are all recently-dispatched. |
| **`create_job` auto-dispatches** | Every `create_job(...)` call bundles `dispatch_job(...)`. No caller path can create orphans by forgetting to dispatch. |

**Failure mode this prevents**: pause fires → sweeper sees pending rows → re-queues them → workers wake, see pause, keep flag → sweeper re-queues again → queue depth explodes. The dedup flag breaks the loop.

---

## 4. Per-Kind Addendum

> Apply ONLY the section matching your shape kind. Delete the others.

### 4a. `kind: service` — HTTP services (python-api, node-api, file-api, saas-skeleton companion backends)

| Concern             | Pattern                                                              |
| ------------------- | -------------------------------------------------------------------- |
| Request timeout     | 30s default; per-endpoint overrides in `config/timeouts.yaml`        |
| Upstream timeout    | Always `connect=5s, read=25s`. Never `None`.                         |
| Circuit breaker     | `pybreaker` (py) or `opossum` (node) on every upstream call          |
| Retry policy        | Exponential backoff w/ jitter, max 3 attempts, only on idempotent ops |
| Rate limit (in)     | `slowapi` (py) / `express-rate-limit` (node) on public endpoints     |
| Rate limit (out)    | Token bucket per upstream API (see §2)                               |
| Health endpoint     | `GET /healthz` → 200 always, `GET /readyz` → 503 if any pause active |
| Graceful shutdown   | SIGTERM → stop accepting → drain 30s → exit                          |
| Bot/abuse detection | Pause `<svc>:pause:abuse` for 60s on auth-fail spike (>10/min)       |

### 4b. `kind: worker` — Job processors (file-worker, anything Celery/BullMQ/RQ)

| Concern              | Pattern                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| Job state            | Postgres `jobs(id, status, started_at, retry_after_at)` — source of truth |
| Dispatch dedup       | Redis `<svc>:dispatched:<job_id>` TTL 30min                             |
| Pause-aware claim    | Worker checks `<svc>:pause:*` BEFORE claiming row; keeps dispatch flag if paused |
| Bundled dispatch     | `create_job(...)` MUST call `dispatch_job(...)`. No caller path creates without dispatching. |
| Orphan sweep         | Beat task every 5min: `status='pending' AND started_at IS NULL AND retry_after_at IS NULL` → re-dispatch (capped 500/fire) |
| Sweeper headroom     | Sweepers pull 4× their limit, post-filter against dedup flags, trim. Handles top-N all in-flight. |
| Per-child memory cap | `worker_max_tasks_per_child=100` to bound OOM blast radius              |
| Retry classifier     | Transient (network, 5xx, pool-exhausted) → defer + backoff; Permanent (4xx, schema) → fail row |
| Concurrency throttle | Semaphore slot per upstream (e.g. 8 slots for Soniox-class APIs)        |
| Shutdown safety      | `task_reject_on_worker_lost=True` so killed workers re-deliver          |

### 4c. `kind: static` — Build-then-serve (docusaurus, static-site)

| Concern        | Pattern                                                                 |
| -------------- | ----------------------------------------------------------------------- |
| Build failures | CI fails the deploy; `fabrik redeploy` auto-reverts to last-good.       |
| CDN miss storm | Cloudflare cache rules; long max-age on hashed assets                   |
| Broken link    | `lychee` link-checker in CI (weekly cron job)                           |
| Search index   | If Algolia/Meilisearch: rebuild as post-build step, fail-open on error  |
| External embed | _(e.g. third-party widgets)_: lazy-load, SRI hash, fallback `<noscript>` |

### 4d. `kind: wordpress` — WP sites

| Concern               | Pattern                                                                |
| --------------------- | ---------------------------------------------------------------------- |
| MariaDB pool          | Per-site container, `max_connections=50`, `wait_timeout=120s`          |
| Redis object cache    | Plugin: `redis-cache`, fail-open if Redis down (WP falls back to DB)   |
| wp-cron               | Disable WP-Cron, run via host cron every 5min (VPS host-scheduled)     |
| PHP-FPM saturation    | `pm=ondemand`, max_children=10/site; Gatus alerts on 502 spike         |
| Plugin auto-update    | DISABLED; managed via `wp-cli` from Fabrik deploy job                  |
| File uploads          | Off-load to R2 via plugin; local `wp-content/uploads` is ephemeral     |
| Backrest snapshot     | Hourly DB dump + daily file-system snapshot to B2                      |

---

## 5. Per-Shape-Flag Addendum

> Each flag below is consumed by a Fabrik registrar at `fabrik apply` time. The registrar handles the infra side; this section is YOUR application-side contract.

### 5a. `needs_database: true` (Postgres registrar)

- Connection pool: max=20, recycle=1800s, pre-ping=on.
- Pool exhaustion → pause `<svc>:pause:db` 30s + log + Grafana annotation.
- Slow query alert: anything >2s logs + sends to GlitchTip.
- Migrations: forward-only, idempotent, gated by `alembic` (py) / `node-pg-migrate` (node).
- WAL disk: Beat task (15min) reads `pg_database_size` + `df`; pause `<svc>:pause:db_disk` at >85% used.

### 5b. `has_persistent_data: true` (Backrest registrar)

- Backrest schedule: hourly snapshot to Backblaze B2.
- **Restore drill quarterly** — record date in Project Shape Card §1. A backup you haven't restored doesn't exist.
- Disk pause: Beat task (5min) reads `df` on data volume; pause `<svc>:pause:disk` at >90%.
- Cleanup policy: explicit, documented, automated. No "we'll clean it later" without a ticket.
- See §6f for storage tiering (hot/cold offload to B2).

### 5c. `is_public: true` + `domain` set (Gatus registrar)

- Gatus probes the public domain every 60s — handled by Fabrik, no app-side work needed.
- App MUST expose `GET /healthz` (always 200, even when degraded) and `GET /readyz` (503 if any §2 critical pause is active).
- TLS auto-renewed via Traefik + Let's Encrypt. Cert expiry alert is automatic via Gatus.

### 5d. `has_search_feature: true` (Meilisearch registrar)

- Index name namespaced by project: `<project>_<entity>`.
- Indexing pipeline is async + idempotent: queue → upsert → ack. No live writes in request path.
- Reindex job: full rebuild on demand via `make reindex`, atomic via shadow-index swap.
- Health: Beat task (5min) pings Meilisearch; pause `<svc>:pause:search` on failure → app falls back to Postgres LIKE / tsvector.

### 5e. `has_bearer_api: true`

- Per-token rate limit: 60 RPM default, configurable per token in `auth.tokens` table.
- Abuse pause per token: 100 errors in 60s → token gets `<svc>:pause:token:<id>` for 300s.
- All requests logged with token-id (not value) to Loki.

### 5f. `is_admin_dashboard: true` + `domain` set (Authelia registrar)

- Authelia handles auth; app reads `Remote-User` / `Remote-Groups` headers.
- Auth-fail spike (>20/min from one IP) → log + GlitchTip event. Authelia handles the lockout.
- Bypass `^/api/` first if `has_bearer_api: true` (Critical Success Factor §10).

---

## 6. Concrete Primitives — Copy-Paste Patterns

### 6a. Pause-state primitive (Python)

```python
# pause_state.py — minimal viable implementation
import os, time, redis
from typing import Optional

_r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
_NS = os.environ.get("SERVICE_NAME", "app")

def set_pause(resource: str, reason: str, ttl: int) -> None:
    """Set or refresh a sliding-TTL pause flag."""
    _r.setex(f"{_NS}:pause:{resource}", ttl, f"{reason}|exp={int(time.time())+ttl}")

def is_paused(resource: str) -> bool:
    return _r.exists(f"{_NS}:pause:{resource}") == 1

def any_critical_paused() -> Optional[str]:
    """Returns the first paused critical resource, or None."""
    for k in _r.scan_iter(f"{_NS}:pause:*"):
        return k
    return None

def clear_pause(resource: str) -> None:
    _r.delete(f"{_NS}:pause:{resource}")
```

### 6b. Pause-state primitive (Node)

```typescript
// pauseState.ts
import { createClient } from "redis";
const r = createClient({ url: process.env.REDIS_URL! });
await r.connect();
const NS = process.env.SERVICE_NAME ?? "app";

export const setPause = (res: string, reason: string, ttl: number) =>
  r.setEx(`${NS}:pause:${res}`, ttl, `${reason}|exp=${Date.now() + ttl * 1000}`);

export const isPaused = async (res: string) =>
  (await r.exists(`${NS}:pause:${res}`)) === 1;

export const clearPause = (res: string) => r.del(`${NS}:pause:${res}`);
```

### 6c. Error classifier — maps exception → (pause_key, ttl)

```python
# error_classifier.py — extend per project, ONE place to map errors
import re
TRANSIENT_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (re.compile(r"insufficient.?credit|payment.?required|\b402\b", re.I), "vendor_credit", 1800),
    (re.compile(r"bot.?check|sign.?in.?to.?confirm",                re.I), "bot_detect",    60),
    (re.compile(r"NameResolutionError|getaddrinfo failed",          re.I), "network",       30),
    (re.compile(r"SSL.+EOF|ssl handshake|unexpected_eof",           re.I), "network_ssl",   30),
    (re.compile(r"pool.*exhausted|too many connections",            re.I), "pool",          120),
    (re.compile(r"\b5\d\d\b|gateway timeout",                       re.I), "upstream_5xx",  30),
]

def classify(err: Exception) -> tuple[str, int] | None:
    msg = f"{type(err).__name__}: {err}"
    for pat, key, ttl in TRANSIENT_PATTERNS:
        if pat.search(msg):
            return key, ttl
    return None
```

### 6d. Readiness endpoint contract

```python
# Liveness: always 200 unless process is dead
@app.get("/healthz")
def healthz(): return {"status": "ok"}

# Readiness: 503 if a critical pause is active
@app.get("/readyz")
def readyz():
    paused = pause_state.any_critical_paused()
    if paused:
        return JSONResponse({"status": "degraded", "paused": paused}, status_code=503)
    return {"status": "ready"}
```

### 6e. Disk-space Beat task (the missing autonomous check)

```python
# Schedule: every 30 min. TTL 1h, re-stamped while above DISK_PAUSE_PCT.
@app.task
def disk_space_check():
    import shutil, os
    pause_pct = float(os.environ.get("DISK_PAUSE_PCT", "85"))
    usage = shutil.disk_usage("/")
    pct_used = usage.used / usage.total * 100
    if pct_used >= pause_pct:
        set_pause("disk_full", f"{pct_used:.1f}% used", ttl=3600)
    else:
        clear_pause("disk_full")
```

Separate `DISK_ALERT_PCT` (default 95) sends an alert to GlitchTip — that's a notification, not a pause refresh.

### 6f. Storage tiering — hot/cold offload (for `has_persistent_data: true`)

VPS disk is finite. Default lifecycle:

| Data class                         | Where           | When to offload      | How                                         |
| ---------------------------------- | --------------- | -------------------- | ------------------------------------------- |
| Hot (read in last 30d)             | Local SSD       | —                    | —                                           |
| Cold (>30d, rarely read)           | Backblaze B2    | nightly cron         | `rclone sync --min-age 30d <local> b2:<bucket>` |
| Logs                               | Local SSD       | daily                | `logrotate` 7-day retention, compress, 500MB cap |
| DB dumps                           | Local + B2      | daily                | `pg_dump --format=custom` → B2, keep 7 local |
| Transient outputs (e.g. audio)     | Local SSD       | post-processing      | delete immediately after sink success       |

Lazy-fetch from B2 on cache-miss is acceptable for cold reads; use a signed-URL redirect or stream-through.

---

## 7. Proactive Monitoring Schedule

The Beat / cron jobs that detect depletion BEFORE workers fail. **Every external API in §2 with a billable balance MUST have a row here.**

| Job                          | Interval | Action                                                          |
| ---------------------------- | -------- | --------------------------------------------------------------- |
| `db_disk_check`              | 15 min   | `df` on PG volume → pause `db_disk` if >85%                     |
| `disk_space_check`           | 30 min   | `shutil.disk_usage('/')` → pause `disk_full` if >85% (see §6e)  |
| `redis_memory_check`         | 5 min    | `INFO memory` → alert if used > 80% of maxmemory                |
| `<api>_balance_check`        | 15 min   | Read vendor balance API → pause `<api>_credit` if below floor   |
| `<api>_quota_reset`          | hourly   | Reset local Redis quota counters as windows roll                |
| `orphan_sweep` _(workers)_   | 5 min    | Re-dispatch DB rows that Redis lost                             |
| `cert_expiry_check`          | daily    | Alert if any TLS cert <14d to expiry _(Gatus handles this)_     |
| `backrest_restore_drill`     | quarterly | Manual: restore latest snapshot to a staging volume, validate   |
| `cold_data_offload`          | nightly  | `rclone sync --min-age 30d` to B2 (§6f)                         |

---

## 7a. Tuning Knobs — Environment Variables

Every TTL, floor, threshold, and interval in this file is a single env var. Ops tune without code changes. **Project-specific knobs MUST land here too.**

| Variable                              | Default     | Purpose                                                |
| ------------------------------------- | ----------- | ------------------------------------------------------ |
| `SERVICE_NAME`                        | _(required)_| Namespace for all Redis keys                           |
| `REDIS_URL`                           | _(required)_| Connection string for pause state + dedup              |
| `PAUSE_TTL_DB`                        | 30          | Postgres pool-exhaustion pause seconds                 |
| `PAUSE_TTL_NETWORK`                   | 30          | DNS / connection blip pause                            |
| `PAUSE_TTL_NETWORK_SSL`               | 30          | SSL / handshake blip pause                             |
| `PAUSE_TTL_POOL`                      | 120         | Upstream pool-exhaustion pause                         |
| `PAUSE_TTL_UPSTREAM_5XX`              | 30          | Upstream 5xx/gateway-timeout pause                     |
| `PAUSE_TTL_BOT_DETECT`                | 60          | Bot-detection / captcha pause                          |
| `PAUSE_TTL_<VENDOR>_CREDIT`           | 1800        | Vendor credit-depletion pause (per vendor)             |
| `PAUSE_TTL_<VENDOR>_RATE`             | 120         | Vendor rate-limit pause (per vendor)                   |
| `<VENDOR>_MIN_REMAINING_<UNIT>`       | _varies_    | Floor below which proactive Beat task pauses           |
| `<VENDOR>_CHECK_INTERVAL_SEC`         | 900         | How often to poll vendor balance API                   |
| `DISPATCH_DEDUP_TTL_SEC`              | 1800        | Maximum life of a dispatch flag                        |
| `ORPHAN_SWEEP_INTERVAL_SEC`           | 300         | Orphan-sweep period                                    |
| `ORPHAN_SWEEP_LIMIT`                  | 500         | Max orphans dispatched per fire                        |
| `DISK_PAUSE_PCT`                      | 85          | Disk-usage pct at which to pause                       |
| `DISK_ALERT_PCT`                      | 95          | Disk-usage pct at which to page separately             |
| `WORKER_MAX_TASKS_PER_CHILD`          | 100         | Bound OOM blast radius per worker child                |

---

## 8. SLO Targets — Defaults by Shape

| Shape kind   | Uptime (30d)  | p95 latency  | Error rate | Backlog            |
| ------------ | ------------- | ------------ | ---------- | ------------------ |
| `service`    | 99.5%         | <500ms       | <1%        | n/a                |
| `worker`     | 99.9% (sweep) | <30s p95 job | <5% retry  | <10k pending       |
| `static`     | 99.9% (CDN)   | <100ms TTFB  | <0.1%      | n/a                |
| `wordpress`  | 99.5%         | <800ms       | <1%        | n/a                |

> Adjust per project — these are **defaults you start with**, not contractual minimums. SaaS customer contracts override.

---

## 9. Accepted Gaps — Explicit Sign-Off

Things this project knowingly does NOT autonomously handle. Each row is a conscious deferral, not an oversight. Review quarterly.

| # | Gap | Risk | Why deferred | Owner | Review by |
|---|-----|------|--------------|-------|-----------|
| 1 | _(e.g. worker auto-restart on crash)_ | _(High in prod, low in dev)_ | _(systemd handles in VPS deploy)_ | Ozgur | 2026-Q3 |
| 2 | _(e.g. Redis maxmemory not capped)_   | _(Low — 117MB current)_      | _(Set on production deploy)_                      | Ozgur | 2026-Q3 |
| 3 | …                                     | …                            | …                                                 | …      | …         |

> A gap without a `Review by` date is not a gap — it's a bug.

---

## 10. Recovery Drills — Prove It Works

Schedule and record outcomes. **A recovery procedure you haven't run is a guess.**

| Drill                          | Frequency  | Last run    | Actual RTO | Notes |
| ------------------------------ | ---------- | ----------- | ---------- | ----- |
| Kill Redis → recover           | quarterly  | YYYY-MM-DD  | _(min)_    |       |
| Kill DB → recover              | quarterly  | YYYY-MM-DD  | _(min)_    |       |
| Fill disk to 95% → pause fires | quarterly  | YYYY-MM-DD  | _(min)_    |       |
| Pull plug on upstream API      | quarterly  | YYYY-MM-DD  | _(min)_    |       |
| Backrest restore to staging    | quarterly  | YYYY-MM-DD  | _(min)_    |       |
| OOM-kill worker mid-job        | quarterly  | YYYY-MM-DD  | _(min)_    |       |

---

## 11. What Fabrik Already Handles (Don't Reimplement)

Auto-provisioned by `fabrik apply` based on the shape flags in §1. **Do not duplicate these in app code.**

| Fabrik registrar | Handles                                       | Triggered by                                |
| ---------------- | --------------------------------------------- | ------------------------------------------- |
| `postgres`       | DB provisioning, conn string, migrations dir  | `needs_database: true`                      |
| `gatus`          | Public uptime probe + alert routing            | `is_public: true` + `domain` set            |
| `glitchtip`      | Error tracking DSN injection + project create  | `kind ∈ {service, worker, wordpress}`       |
| `grafana`        | Deployment annotations on every deploy         | always                                      |
| `backrest`       | Snapshot schedule + B2 offsite                 | `has_persistent_data: true`                 |
| `meilisearch`    | Index provisioning + API key                   | `has_search_feature: true`                  |
| `authelia`       | Auth layer + `^/api/` bypass if bearer-API    | `is_admin_dashboard: true` + `domain` set   |
| `traefik`        | TLS, routing, HTTP→HTTPS                      | auto-discovered from compose labels         |
| `promtail/loki`  | Log shipping                                   | auto-discovered                             |
| `prometheus`     | Metrics scrape                                 | `exposes_metrics: true` + compose label     |
| `cadvisor`       | Container resource metrics                     | auto-discovered                             |

**Application code is responsible for**: the §2 inventory, §6 primitives (pause state, error classifier, /healthz + /readyz, disk-space Beat, storage tiering), §7 proactive checks for vendor balances, and §7a env-var hygiene.

---

## 11a. Key Files Map

Where each resilience primitive lives in this project. Fill in on first refactor — the value is letting a new contributor (or Claude/Kilo agent) find the right file without spelunking.

| Role                                     | File                                  |
| ---------------------------------------- | ------------------------------------- |
| Pause primitive (set / get / clear)      | `src/pause_state.py`                  |
| Error classifier (transient → pause key) | `src/error_classifier.py`             |
| Worker / job processor                   | `src/worker/tasks.py`                 |
| Beat / cron schedule                     | `src/worker/celery_app.py` _(or `cron.yaml`)_ |
| Dispatcher + dedup helpers               | `src/dispatcher.py`                   |
| Vendor balance check (per vendor)        | `src/checks/<vendor>_balance.py`      |
| Disk-space Beat task                     | `src/checks/disk_space.py`            |
| Cold-data offload script                 | `scripts/offload_cold_to_b2.sh`       |
| Orphan recovery tool (manual)            | `scripts/dispatch_orphans.py`         |
| Health endpoints                         | `src/api/health.py`                   |

---

## 12. Change Log for This File

| Date       | Change                                                     | By     |
| ---------- | ---------------------------------------------------------- | ------ |
| YYYY-MM-DD | Created from `fabrik/templates/scaffold/docs/RESILIENCE_TEMPLATE.md` | scaffold |

---

_Standard reference: `fabrik/.windsurf/rules/core/58-resilience.md`. Canonical implementation: `transcriber/docs/reference/pipeline-resilience.md` (YouTube pipeline)._
