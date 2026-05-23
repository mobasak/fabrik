---
activation: glob
globs: ["**/docs/RESILIENCE.md", "**/pause_state*", "**/error_classifier*", "**/circuit_breaker*", "**/health*", "**/readyz*", "**/orphan_sweep*", "**/balance_check*", "**/dispatch*", "**/beat.py", "**/celerybeat*", "**/httpx*", "**/client*"]
description: Resilience contract — timeout/retry/circuit-breaker for all services, plus autonomous pause-state/queue-bloat for workers
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Timeout/retry/circuit-breaker for all services + advanced pause-state pipeline for workers
     TRAYCER USAGE: Injects resilience requirements per external dependency into ticket ACs. References docs/RESILIENCE.md §2a.
     AGENT USAGE: Wrap every external call with timeout+retry. Workers: wire pause-state pipeline. -->

# Resilience & Autonomy Rules

**Activation:** Glob — resilience-related files (RESILIENCE.md, health endpoints, HTTP clients, pause state, error classifier, dispatchers, beat tasks).
**Purpose:** Every external call has timeout + retry + circuit-breaker + graceful fallback. Workers additionally get the autonomous pause-state pipeline.

---

## Per-Scaffold Applicability

Not every scaffold needs the full autonomous pipeline. This matrix defines what applies:

| Scaffold | Basic resilience (timeout/retry/CB) | `/health` with dep checks | `docs/RESILIENCE.md` | Pause-state pipeline | Queue-bloat prevention |
|---|---|---|---|---|---|
| `python-api` | Yes — every external call | Yes (scaffolded) | Yes | Only if async jobs exist | Only if async jobs exist |
| `node-api` | Yes — every external call | Yes (scaffolded) | Yes | Only if async jobs exist | Only if async jobs exist |
| `file-api` | Yes — every external call | Yes (scaffolded) | Yes | Yes (processes files) | Yes |
| `file-worker` | Yes — every external call | Yes (scaffolded) | Yes | Yes (core pattern) | Yes (all 5 mechanisms) |
| `saas-skeleton` | Yes — API routes + server actions | Yes (scaffolded) | Yes | Only if background jobs | Only if background jobs |
| `chrome-extension` | Backend: yes; Frontend: retry + offline UX | Backend only | Backend only | No | No |
| `mobile-app` | Backend: yes; Client: retry + offline fallback | Backend only | Backend only | No | No |
| `desktop-app` | Backend: yes; Client: retry + offline fallback | Backend only | Backend only | No | No |
| `wordpress` | N/A — plugins handle resilience | Gatus checks site URL | No | No | No |
| `docusaurus` | N/A — static site | Nginx responds on `/` | No | No | No |
| `static-site` | N/A — static site | Nginx responds on `/` | No | No | No |

---

## Basic Resilience (ALL services with external calls)

The lifecycle doc mandates: **"every external call has timeout + retry with backoff. Circuit-breaker for repeated failures. Graceful fallback when dependencies are down."**

This is the minimum for ANY `httpx`, `fetch`, or SDK call to an external service.

### Python (httpx — async)

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# 1. Configure the client ONCE with timeouts
client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
    headers={"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]},
)

# 2. Wrap calls with retry + backoff
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)
async def fetch_data(item_id: str) -> dict:
    resp = await client.get(f"/items/{item_id}")
    resp.raise_for_status()
    return resp.json()

# 3. Graceful fallback at the call site
async def get_item(item_id: str) -> dict | None:
    try:
        return await fetch_data(item_id)
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError):
        logger.warning("external_service_unavailable", service="example", item_id=item_id)
        return None  # graceful degradation — caller handles missing data
```

**Rules:**
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
- **Timeout is mandatory.** No `httpx.get()` without explicit timeout. The default `httpx.Timeout(5.0)` is often too short for read — set per dependency.
- **Retry with exponential backoff.** Use `tenacity` (Python) — 3 attempts, 1-10s backoff. Only retry transient errors (timeout, connection), never 4xx.
- **Graceful fallback.** The caller must handle the failure case — return cached data, a default, or a user-facing error message. Never let an external service failure crash your endpoint.

### Node.js / TypeScript

```typescript
import { setTimeout } from 'timers/promises';

async function fetchWithRetry(url: string, options: RequestInit = {}, maxRetries = 3): Promise<Response> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = globalThis.setTimeout(() => controller.abort(), 30_000);
      const resp = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      if (!resp.ok && resp.status >= 500) throw new Error(`Server error: ${resp.status}`);
      return resp;
    } catch (err) {
      if (attempt === maxRetries) throw err;
      await setTimeout(Math.min(1000 * 2 ** attempt, 10_000));
    }
  }
  throw new Error('Unreachable');
}
```

### Supabase Client Resilience (SaaS / Mobile)

The Supabase JS client (`supabase-js`) has built-in retry for realtime connections but NOT for REST API calls (`from('table').select()`). Configure:

```typescript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(url, anonKey, {
  global: {
    fetch: (url, options) => fetch(url, { ...options, signal: AbortSignal.timeout(30_000) }),
  },
  realtime: {
    params: { eventsPerSecond: 10 },
  },
});
```

- **Wrap Supabase REST calls in try/catch** at the service layer. Handle `PostgrestError` and network errors gracefully.
- **Supabase outage fallback:** if the Supabase API is down, the app should show cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Supabase Auth token refresh:** the SDK handles this automatically. Do not build custom refresh logic (per `35-security-auth.md` Pattern B).

### Circuit-Breaker Pattern

For dependencies that fail repeatedly, implement a circuit-breaker to stop hammering a dead service:

```python
import time
from dataclasses import dataclass, field

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    _failures: int = field(default=0, init=False)
    _last_failure: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)

    def can_execute(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure > self.recovery_timeout:
                self._state = "half-open"
                return True
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure = time.monotonic()
        if self._failures >= self.failure_threshold:
            self._state = "open"
```

- One circuit-breaker per external dependency (not per endpoint).
- `failure_threshold` and `recovery_timeout` as env vars (tuning knobs per §7a of RESILIENCE.md).
- When circuit is open, return the graceful fallback immediately — don't queue up timeout waits.

---

## The Per-Project Contract (`docs/RESILIENCE.md`)

Every project scaffolded by Fabrik gets `docs/RESILIENCE.md` from `templates/scaffold/docs/RESILIENCE_TEMPLATE.md`. Its 14 sections are the contract. The non-negotiable ones:

| § | Title | Why it's enforceable |
|---|---|---|
| 2a | Dependency Inventory — summary | If an `httpx.get()` / `fetch()` call site has no row here, the PR is rejected. |
| 2b | Detail card per dependency | Failure signature, detection mechanism, timeout/retry config, fallback, scope. Workers additionally: pause key, TTL+env, resume trigger, jobs affected, bloat note. |
| 3a | Queue Bloat Prevention | Required if `kind: worker` or any async job processing. |
| 6 | Concrete Primitives | Basic: timeout/retry/CB. Workers additionally: pause state + classifier + /health checks + beat tasks. |
| 7 | Proactive Monitoring Schedule | Every billable external API MUST have a `<api>_balance_check` Beat row. |
| 7a | Tuning Knobs | Every timeout, retry count, CB threshold, TTL, floor = a single env var. |
| 9 | Accepted Gaps | A gap without a `Review by` date is a bug, not a gap. |
| 10 | Recovery Drills | A recovery procedure you haven't run is a guess. Quarterly. |

Reference: `templates/scaffold/docs/RESILIENCE_TEMPLATE.md` (the source of truth for the contract structure).

---

## Health Endpoint Contract

Every service exposes `/health` that actively verifies critical dependencies before returning 200. This is the single health endpoint — consistent across all rule packs, Gatus, Coolify, and the scaffold.

| Check | What to verify |
|---|---|
| Database | `await db.execute("SELECT 1")` |
| Redis | `await redis.ping()` |
| Consumed internal APIs | `httpx.get(f"{service_url}/health", timeout=5)` |
| File storage (B2) | Check bucket accessibility (if critical path) |

- `/health` is Authelia-bypassed on all services (global rule). Never protect it.
- `HEALTHCHECK` in compose.yaml points to `/health`. See `30-ops.md` for the template.
- Enforcement: `scripts/enforcement/check_health.py` verifies real dependency checks exist (not static 200).
- Gatus probes `/health` externally for uptime SLO.
- Coolify uses the compose HEALTHCHECK for container restart decisions.

**Advanced (workers only):** If the project uses the pause-state pipeline, add a readiness dimension — `/health` returns 200 but includes a `paused` field in the JSON body listing any active pause keys. This lets operators see pause state without it triggering Gatus alerts.

```python
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    paused = get_active_pauses()  # list of active pause keys, empty if none
    return {"status": "ok", "paused": paused}
```

---

## Advanced: Autonomous Pause-State Pipeline (workers only)

The following sections apply ONLY to `file-worker`, `file-api`, and any service with async job processing. This is the production-proven pattern from the YouTube pipeline.

### The Four Properties

A SaaS-grade autonomous system is defined by FOUR properties:

1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail. Error classifiers map exceptions to pause keys on the way through. Never one without the other for any critical dependency.
2. **Pause flags are sliding-TTL.** Set/refreshed by every check, auto-clear when checks stop firing. No human page. No permanent stuck state. Worst case: a 30-minute TTL.
3. **Queue depth = job count, exactly.** Dispatch-dedup + worker-keeps-flag-on-pause + sweeper-headroom together prevent the pause-then-re-queue-then-re-pause queue-explosion failure mode.
4. **The database is the source of truth.** Queues lose state on restart; orphan sweeps reconcile from the DB.

Canonical implementation: `/opt/youtube/docs/reference/pipeline-resilience.md` + `pause_state.py`. Read it before rolling your own.

### Pause-Key Conventions

- Namespace: `<service_name>:pause:<resource>` (Redis key).
- Service name is `SERVICE_NAME` env var, required at boot.
- Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`, never permanent.
- Scope (see §2c of the project's RESILIENCE.md):

| Scope | Use when | Example |
|---|---|---|
| **global** | >=50% of work hits this dep, or partial work is worthless | Postgres down, Redis maxmem |
| **per-job-type** | Dep affects only one job class — pausing everything is wasteful | YouTube Data API quota per job |
| **per-token / per-key** | Multi-tenant — one abusive tenant must not stop others | API token rate limit |
| **per-region / rotation** | Dep has multiple instances; rotate instead of stop | Multi-key API quota rotation |

**Anti-pattern:** defaulting to global pause for a dependency only 5% of jobs need. That halts 95% of healthy work.

### Queue Bloat Prevention — The Five Mechanisms

All five must be present together. Any one missing → queues balloon under load.

| Mechanism | Implementation |
|---|---|
| **Dispatch dedup flag** | `<svc>:dispatched:<job_id>` (TTL 30 min) set on `dispatch_job()`, checked by all sweepers via `_filter_recently_dispatched()` (Redis `MGET`, O(1)). |
| **Worker keeps flag on pause-skip** | If `is_paused(...)`, worker returns WITHOUT clearing flag → sweepers see "already queued" → no re-push. |
| **Worker clears flag on success** | After pause check passes, `clear_dispatched_flag(job_id)` runs → sweepers may re-dispatch on future retry. |
| **Sweeper headroom** | Sweepers pull **4x their limit**, post-filter against dedup flags, trim to limit. Handles top-N all in-flight. |
| **`create_job` auto-dispatches** | Every `create_job(...)` call bundles `dispatch_job(...)`. No caller path can create orphans. |

### Error Classifier — One Source of Truth

There is ONE file (`src/error_classifier.py` or equivalent) that maps exception/log-pattern to (pause_key, ttl). All worker error handlers and HTTP middleware call this single classifier. Adding a new transient pattern means editing ONE place.

```python
TRANSIENT_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (re.compile(r"insufficient.?credit|payment.?required|\b402\b", re.I), "vendor_credit", 1800),
    (re.compile(r"NameResolutionError|getaddrinfo failed",           re.I), "network",       30),
    (re.compile(r"pool.*exhausted|too many connections",             re.I), "pool",          120),
    # ... project-specific additions here, NEVER inline elsewhere
]
```

---

## Banned Patterns

| Pattern | Use Instead |
|---|---|
| `requests.get()` (sync, blocks event loop) | `httpx.AsyncClient` with explicit timeout |
| `httpx.get()` without explicit timeout | `httpx.Timeout(connect=5, read=30, write=10, pool=5)` |
| External call site with no row in §2a of RESILIENCE.md | Add the row first, then the call site |
| `time.sleep(N)` on transient error | Retry with backoff (`tenacity`) or `set_pause(key, ttl)` for workers |
| No fallback on external call failure | Graceful degradation: cached data, default, or clear error state |
| Global pause for a dep only one job-type uses | `defer_until_*()` on the job row (per-job-type scope) |
| Permanent flag (`SET` without TTL) on pause keys | `SETEX` / `set(ex=ttl)` — sliding-TTL is the contract |
| `try: ... except: pass` on upstream calls | Classifier → pause → re-raise. Silent swallow is data loss. |
| New TTL/timeout literal in code (e.g. `ttl=1800`) | Read from `os.environ["PAUSE_TTL_<RESOURCE>"]` — knob in §7a |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Two error classifiers in different files | One file. Always. |
| Adding a billable vendor without a balance check Beat task | Proactive check is mandatory for any dep with a balance |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| Custom Supabase token refresh logic | SDK handles refresh automatically (per `35-security-auth.md`) |

---

## Done When

### All services with external calls

- [ ] Every external call has explicit timeout configured.
- [ ] Every external call has retry with exponential backoff (transient errors only).
- [ ] Every external call has a graceful fallback (cached data, default, or error state).
- [ ] Circuit-breaker implemented per external dependency (threshold + recovery from env vars).
- [ ] `docs/RESILIENCE.md` exists; §2a has a row for every external call site.
- [ ] Every timeout, retry count, CB threshold is an env var (§7a tuning knobs).

### Workers (additionally)

- [ ] §1 (Shape Card) filled; `Last drill` has a date within the last 90 days.
- [ ] Every billable external API has both: a §2b detail card AND a row in §7 (Proactive Monitoring Schedule).
- [ ] Single error-classifier file exists; every `except` block calls it.
- [ ] All pause-key namespaces use `$SERVICE_NAME` env var.
- [ ] No literal TTL constants in code — all read from env vars listed in §7a.
- [ ] All five queue-bloat-prevention mechanisms are wired (§3a).
- [ ] For services with `has_persistent_data: true`: disk-space Beat task running (§6e).
- [ ] §9 Accepted Gaps each have a `Review by` date.
- [ ] §10 Recovery Drills have at least one row with a real `Last run` date.

### SaaS / Mobile (additionally)

- [ ] Supabase client configured with explicit timeout.
- [ ] Supabase REST call errors handled with try/catch at service layer.
- [ ] Supabase outage fallback shows cached data or clear error state — never blank screen.
