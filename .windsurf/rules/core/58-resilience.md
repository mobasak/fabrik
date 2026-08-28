---
activation: glob
globs: ["**/docs/RESILIENCE.md", "**/pause_state*", "**/error_classifier*", "**/circuit_breaker*", "**/health*", "**/orphan_sweep*", "**/balance_check*", "**/dispatch*", "**/beat.py", "**/httpx*", "**/client*"]
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
| `python-api-gpu` | Yes — **and provider-death handling is mandatory** (§ Provider-death resilience; `76-gpu-workers.md` § Provider Failover) | Yes (scaffolded) + report per-provider status | Yes | Only if async/batch inference jobs queue (real-time streaming bypasses it — `76-gpu-workers.md`) | Same condition |
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
from src.config import get_settings

client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
    # For internal M2M calls, add X-Internal-Token header per 35-security-auth.md.
    # Do NOT send internal tokens to third-party APIs.
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
- **Retry with exponential backoff.** Use `tenacity` (Python) — 3 attempts, 1-10s backoff. Retry transient errors: timeout, connection, and 5xx (502/503/504 are transient gateway errors). Never retry 4xx.
- **Graceful fallback.** The caller must handle the failure case — return cached data, a default, or a user-facing error message. Never let an external service failure crash your endpoint.

### The timeout you didn't set (third-party libraries, shared sessions, DNS)

"Every external call has a timeout" is necessary but NOT sufficient. Three gaps bite repeatedly (YouTube pipeline, 2026-05-31 — `docs/LESSONS_LEARNT.md` Lessons 72 & 74):

1. **A library you call may make an un-timeout'd request through *your* session.** You set a proxy on a shared `requests.Session`/client and hand it to a third-party library; the library's internal `session.get(url)` sets no timeout → a stalled proxy (connection accepted, no bytes) blocks the socket read **forever**, hanging the whole worker until something external kills it. The fix is to put a **default timeout on the session itself**, so every request the library makes inherits it:

   ```python
   # Force a default (connect, read) timeout on EVERY request a handed-off
   # session makes. setdefault (NOT functools.partial) so callers that pass
   # timeout explicitly aren't clobbered with "got multiple values for 'timeout'".
   _orig = session.request
   def _request(method, url, **kw):
       kw.setdefault("timeout", (10, 30))
       return _orig(method, url, **kw)
   session.request = _request
   ```

   **Verify in the library source** that every request path is timeout-bounded — "the library has timeouts" is not the same as "every call has one" (the offending lib timed out its AJAX calls but not its initial page fetch).

2. **A request `timeout=` does NOT bound DNS resolution.** `requests`/`httpx`/`urllib3` timeouts cover connect + read, not `getaddrinfo` — a stalled resolver hangs *through* the timeout. On WSL/containers/flaky-resolver hosts, harden the resolver (static public DNS, made immutable) — don't rely on `timeout=`. Diagnose with `getent ahostsv4 <host>` (hangs) vs `getent ahostsv6` / `nslookup -type=A <host> 1.1.1.1` (instant). For long-lived clients, give them a resolver with its own deadline rather than the system stub.

3. **A `while not <flag>: sleep()` wait is an unbounded hang in disguise.** Any "wait for condition" loop (network-up flag, lock acquired, dependency ready) MUST have a ceiling, then proceed/bail to a transient error. An unbounded conditional wait burns the job's whole hard-timeout budget exactly like a missing socket timeout.

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

### FastAPI Client Resilience (SaaS / Mobile)

Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`, per `agents-fabrik.md § Supabase`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry for these calls — wire them explicitly:

```typescript
async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    signal: AbortSignal.timeout(30_000),  // no request hangs forever
  });
  if (!resp.ok && resp.status >= 500) throw new Error(`Server error: ${resp.status}`);
  return resp;
}
```

- **Explicit timeout on every client→backend call** (`AbortSignal.timeout`) — the default `fetch` has none.
- **Wrap backend calls in try/catch** at the service layer. Handle non-2xx responses and network errors gracefully; retry transient failures (timeout, connection, 5xx) with backoff, never 4xx.
- **Backend outage fallback:** if the FastAPI API is down, the app shows cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** Pattern A issues its own JWTs with atomic refresh-token rotation; the app's auth client owns the refresh flow (per `35-security-auth.md` Pattern A). Do not scatter ad-hoc refresh logic across service calls — centralize it in the auth client.

> **Legacy note.** A project still on Supabase Auth (Pattern B) wraps `supabase-js` REST calls (`from('table').select()`) in the same try/catch + cached-data-fallback discipline, and lets the SDK own token refresh. Pattern B is legacy — migrate to self-hosted Pattern A (`agents-fabrik.md § Supabase`).

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

## VPS Service Client Patterns

The VPS runs several services your code may call. Each is an external dependency — apply basic resilience (timeout + retry + fallback) per the patterns above. Quick reference:

| Service | Address | Client | Timeout | Fallback |
|---|---|---|---|---|
| **Backblaze B2** | S3-compatible API | `boto3` with `endpoint_url` from env | 30s connect, 120s read (large files) | Return error; never block request on upload failure |
| **Gotenberg** (PDF) | `http://gotenberg:3000` on `fabrik` network | `httpx.AsyncClient` POST multipart | 60s (PDF generation is slow) | Return "PDF unavailable, retry later" |
| **Browserless** | `http://browserless:3000` on `fabrik` network | `httpx.AsyncClient` or Playwright connect | 30s | Return cached/fallback content |
| **Apprise** (notifications) | `http://apprise:8000` on `fabrik` network | `httpx.AsyncClient` POST | 10s | Log warning, don't block — notifications are fire-and-forget |
| **MeiliSearch** | `http://meilisearch:7700` on `fabrik` network | `meilisearch` Python SDK or `httpx` | 5s search, 30s indexing | Search: return empty results. Indexing: retry via job queue |

**Rules:**
- All credentials via env vars (`B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, etc.).
- Every service above must have a row in `docs/RESILIENCE.md` §2a if your project calls it.
- B2 file uploads: async via job queue (per `75-workers-jobs.md`), never inline in API handlers. **boto3 is sync** — keep its network calls in the worker/sync context or a thread executor (`run_in_executor`), never inline in an `async def` route.
- Presigned URLs for B2 downloads: generate server-side (presigned URL generation is local — no network I/O, safe in async), return URL to client. Never proxy file bytes through FastAPI.

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

Every service exposes `/health` that actively verifies critical dependencies before returning 200. This is the single health endpoint — consistent across all rule packs, Gatus, the compose `HEALTHCHECK`, and the scaffold.

| Check | What to verify |
|---|---|
| Database | `await session.execute(text("SELECT 1"))` |
| Redis | `await redis.ping()` |
| Consumed internal APIs | `httpx.get(f"{service_url}/health", timeout=5)` |
| File storage (B2) | Check bucket accessibility (if critical path) |

- `/health` is Authelia-bypassed on all services (global rule). Never protect it.
- `HEALTHCHECK` in compose.yaml points to `/health`. See `30-ops.md` for the template.
- Enforcement: `scripts/enforcement/check_health.py` verifies real dependency checks exist (not static 200).
- Gatus probes `/health` externally for uptime SLO.
- The Docker daemon uses the compose HEALTHCHECK for container restart decisions (`restart: unless-stopped`).

**Advanced (workers only):** If the project uses the pause-state pipeline, add a readiness dimension — `/health` returns 200 but includes a `paused` field in the JSON body listing any active pause keys. This lets operators see pause state without it triggering Gatus alerts.

```python
@app.get("/health")
async def health():
    from sqlalchemy import text
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
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

Canonical implementation: `fabrik scaffold` emits `pause_state.py` (from `templates/scaffold/python/pause_state.py`) into every `python-api` and `file-worker` project. Customize the `TRANSIENT_PATTERNS` list for your project's dependencies. Production reference: `/opt/youtube/docs/reference/pipeline-resilience.md` + `/opt/youtube/pause_state.py`.

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

### Operational failures are transient — never a terminal *content* verdict

The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and only ever record a content terminal (`deleted`, `private`, `unavailable`, `no_captions`, etc.) when there is **positive content evidence** for it. Everything else is transient/retryable.

| Outcome | Classify as | NOT as |
|---|---|---|
| Timeout / hard-kill (poison) / worker restart | transient · `processing_timeout` · retry (don't burn retry budget) | `unavailable` / `deleted` |
| Network / proxy / DNS error | transient → pause/retry | `no_captions` / `unavailable` |
| Lock contention (another worker holds the per-resource lock) | transient → short defer | a content failure |
| Empty API response *after* a timeout | inconclusive → re-verify | `deleted` (an empty body is not proof of removal) |
| API confirms removal / metadata says private / transcript genuinely empty after fallback | **terminal content verdict** (evidence exists) | — |

Why it matters: a terminal mislabeled as transient just costs a retry; a **transient mislabeled as terminal is silent, unrecoverable data loss** — the user is told "unavailable" for content that's actually fine. Make the classifier's **default transient**, and require explicit evidence to escalate to a content terminal. (YouTube pipeline 2026-05-31: poison/`retry_exhausted`, API-verify→`deleted`, restart retry-burn, and a comments lock-collision→`captions_unavailable` were all this bug — `docs/LESSONS_LEARNT.md` Lesson 73.)

---

## Provider-death resilience — unattended external-dependency loops (PLANNING-PHASE requirement)

**Applies to any unattended loop over a paid/free external dependency** — an LLM provider chain, a paid
API a backfill hammers, any long-running job whose forward progress depends on a third party you do not
control. Operator directive 2026-08-28: a de-facto standard for every service, not a suggestion. If the
project has no such loop, this section does not apply.

**Why the rest of this pack is not enough.** Timeout, retry, backoff, circuit-breaker and resumable
checkpointing all heal a **transient** fault — a quota window resets, a blip passes. None of them heals a
**permanent provider death**: a model or endpoint that is down for this whole run needs a **SWAP**, a
decision no retry loop is empowered to make. Live incident (youtube RAG backfill, 2026-08-28): stalled
**8h at zero progress** while every mechanism in this pack ran correctly. The primary free model went
ReadTimeout-down *while other free models of the same provider stayed up*; both paid fallback tiers were
billing-gated (`http_402`); the capped last resort was silently dead; and **nothing alarmed**, because
zero progress is not an error.

**A plan or spec that introduces such a loop must state how it satisfies all THREE outcomes. A design
carrying retry/backoff but no provider-death handling and no zero-progress alarm is a DEFECT** — that is
what `/fabrik-spec-review` §E and `/fabrik-plan-review` grade. **These are OUTCOMES, and the mechanism
depends on your ROUTE** — measured 2026-08-28 across 43 repos: 26 carry such a loop, and **19 of those 26
route only through OpenRouter**, where hand-rolling a probe re-implements the gateway.

| # | Required outcome | Routed through OpenRouter (the sanctioned gateway) | Calling a provider endpoint DIRECTLY |
|---|---|---|---|
| 1 | **No single point of death in the chain** — one model or endpoint dying must not stop the loop | **Declare** which mechanism you rely on in §2b. Outage-aware routing is step 1 of OpenRouter's DEFAULT strategy, and a `models` request-body array falls back on **any** error (incl. rate-limiting and downtime). ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing — and the outage step is *part of* load balancing.** Pinning a provider silently opts you OUT of the protection you believe you have; if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidate list **once at run start** (never per item), rebuild the chain from live survivors, best candidate first so it self-restores on recovery. Build it on `fabrik-lib/health-probe/` (Active — pluggable probing, feeds `alerting/`); the shared chain-rebuild helper on top is REQUESTED, not yet shipped (fabrik-lib `01M14E3MWN`), so today the promotion logic is project-local. Needs **intra-provider** diversity (2+ models of one provider) AND **cross-provider** diversity |
| 2 | **The last rung is actually exercised** | No gateway provides this. Exercise it on a schedule | Same |
| 3 | **Absence of progress is alarmed** — N minutes of zero forward progress fires ONE operator alert, cleared on recovery | No gateway provides this. Export a monotonically-increasing **progress** counter (rows done, items classified) and alert on it — not on error codes. Threshold ≥ 2 full runs of your loop, as a §7a knob. Deliver via `fabrik-lib/alerting/`, whose title-based dedup IS the "exactly one alert" property | Same |

**"We use OpenRouter" is not a resilience design** — it is the name of a gateway that can be configured
out of the protection being claimed. Name the mechanism, not the vendor.

> **Note — this rule and the scaffold template currently differ on the gateway path.** The project-facing
> `docs/RESILIENCE.md` §3b (emitted by the scaffold) states outcome 1 as an unconditional build. This rule
> scopes it by route, on the measurement above. The divergence is filed as `01M14E2VZM` and is unresolved
> at time of writing; a divergence written down is a known state, a silently picked winner is not. When it
> resolves, both say the same thing and this note goes.

---

## Banned Patterns

| Pattern | Use Instead |
|---|---|
| `requests.get()` (sync, blocks event loop) | `httpx.AsyncClient` with explicit timeout |
| `httpx.get()` without explicit timeout | `httpx.Timeout(connect=5, read=30, write=10, pool=5)` |
| Handing a `requests.Session`/client to a 3rd-party library without a **default timeout on the session** | Wrap `session.request` with `kwargs.setdefault('timeout', (c, r))` — the library's internal calls may set none |
| Trusting a request `timeout=` to bound DNS | It doesn't cover `getaddrinfo`. Harden the resolver (static/immutable DNS) or give the client its own resolver deadline |
| `while not <flag>: sleep()` with no ceiling | Bound every conditional wait; then proceed or bail to a transient error |
| Recording an operational failure (timeout/network/proxy/hard-kill/lock) as a terminal **content** verdict | Default transient/retryable; terminal-content requires positive content evidence (see § Operational failures are transient) |
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
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule. An untested fallback is a silently-dead fallback — youtube's last-resort had an expired credential nobody had run in weeks, so the chain was one rung shorter than its author believed |
| An unattended external-dependency loop with **no zero-progress alarm** | Export a monotonically-increasing progress counter + alert on it (§ Provider-death resilience). Retry/backoff cannot detect an *absence* of events |
| Scattered ad-hoc token refresh across service calls | Centralize refresh in the Pattern A auth client (legacy Pattern B: SDK handles it) — per `35-security-auth.md` |

---

## Related Rule Packs

- `10-python.md` — Pydantic Settings for secrets/config, async httpx, error handling
- `30-ops.md` — HEALTHCHECK `start_period: 20s`, `/health` Authelia bypass
- `35-security-auth.md` — M2M `X-Internal-Token` (internal calls only — never to third-party APIs)
- `55-observability.md` — `/health` contract, GlitchTip error capture, structlog
- `75-workers-jobs.md` — adaptive worker pool, orphan sweep, beat scheduler (consumer of pause-state)
- `76-gpu-workers.md` — provider failover chain, orchestrator resilience

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

- [ ] Client→FastAPI-backend calls configured with explicit timeout (`AbortSignal.timeout`).
- [ ] Backend call errors handled with try/catch at the service layer.
- [ ] Backend outage fallback shows cached data or clear error state — never blank screen.
