---
activation: glob
globs: ["**/docs/RESILIENCE.md", "**/pause_state*", "**/error_classifier*", "**/circuit_breaker*", "**/health*", "**/orphan_sweep*", "**/balance_check*", "**/dispatch*", "**/beat.py", "**/httpx*", "**/client*"]
description: Resilience contract — timeout/retry/circuit-breaker for all services, plus autonomous pause-state/queue-bloat for workers
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Every production failure class bounded by a primitive AND recovered without a human — timeout/retry/circuit-breaker
           for all services, boot+shutdown edges, overload control, and the advanced pause-state pipeline for workers
     TRAYCER USAGE: Injects resilience requirements per external dependency into ticket ACs. References docs/RESILIENCE.md §2a.
     AGENT USAGE: Walk § The coverage map for the classes this service can suffer; wrap every external call with
                  timeout+retry; handle SIGTERM and boot dependency waits. Workers: wire pause-state pipeline. -->

# Resilience & Autonomy Rules

**Activation:** Glob — resilience files (RESILIENCE.md, health endpoints, HTTP clients, pause state, error classifier, dispatchers, beat tasks).
**Purpose:** Every production failure class has a bounding primitive AND a recovery that needs no human
(§ The coverage map): external calls get timeout + retry + circuit-breaker + fallback, every process
handles its own boot and shutdown edges, workers add the autonomous pause-state pipeline.

---

## Per-Scaffold Applicability

Not every scaffold needs the full autonomous pipeline:

| Scaffold | Basic resilience (timeout/retry/CB) | `/health` with dep checks | `docs/RESILIENCE.md` | Pause-state pipeline | Queue-bloat prevention |
|---|---|---|---|---|---|
| `python-api` | Yes — every external call | Yes (scaffolded) | Yes | Only if async jobs exist | Only if async jobs exist |
| `python-api-gpu` | Yes — **plus mandatory provider-death handling** (`76-gpu-workers` § Provider Failover) | Yes + per-provider status | Yes | Only if async/batch inference queues (streaming bypasses it) | Same condition |
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

## The coverage map — every production failure class, and what recovers it WITHOUT a human

**The bar: a service, worker or connector handles every failure class production can throw at it and
returns to service BY ITSELF.** A mechanism that detects a fault and then waits for a person is not
resilience, it is monitoring. **A design that leaves a row blank for a class it can actually suffer is
a DEFECT** — what `/fabrik-spec-review` and `/fabrik-plan-review` grade. Rows owned elsewhere are
indexed here, never restated; "can actually suffer" is decided by § Per-Scaffold Applicability above.
An N/A with a reason is a complete answer, a silent gap is not.

| # | Failure class | Bounded by | Autorecovers when… | Owner |
|---|---|---|---|---|
| 1 | Dependency **slow or hung** | connect/read/write/pool timeouts | the call gives up; the next is unaffected | here |
| 2 | Dependency **transient error** | bounded jittered retry, inside the deadline | an attempt succeeds | here |
| 3 | Dependency **failing repeatedly** | circuit-breaker + graceful fallback | a half-open probe succeeds | here |
| 4 | Dependency **refuses work** (429/402/quota) | `Retry-After` inline, else a pause key | detection stops and the sliding TTL lapses — a pause outliving N× TTL escalates once | here + `75-workers-jobs` |
| 5 | Dependency **permanently dead** | chain rebuilt from live survivors + zero-progress alarm | the next run-start probe promotes a survivor | here (§ Provider-death) |
| 6 | **DNS** stalls | hardened resolver / resolver deadline | the resolver recovers; timeouts bound the damage | here |
| 7 | **Boot**: dependency not ready | bounded startup retry + startup deadline | it accepts — or the process exits non-zero and restarts | here (§ The lifecycle edges) |
| 8 | **Shutdown**: SIGTERM mid-work | drain inside `stop_grace_period`; workers requeue | the next start resumes cleanly | here + `75-workers-jobs` |
| 9 | **Process death** (crash, OOM, segfault) | memory limit + `restart:` policy + supervised child | Docker restarts the container | `30-ops`, `75`; ladder row 1 |
| 10 | **Overload** — arrivals exceed capacity | bounded queue + concurrency cap + shedding | shedding lets the backlog drain | here (§ Overload) |
| 11 | **Retry amplification** across layers | retry at ONE layer + population retry budget | the budget refills as successes return | here |
| 12 | **Ghost work** outliving its caller | one absolute deadline; expired work dropped on dequeue | the queue self-purges doomed work | here (§ Overload) |
| 13 | **Cache stampede** on expiry | single-flight + early refresh | one rebuild serves every waiter | here (§ Overload) |
| 14 | **The substrate itself is down** (Redis) | a DECLARED fail-open/closed posture per key | Redis returns; the posture holds the line meanwhile | here (§ When the resilience substrate itself fails) |
| 15 | **DB pool exhausted / stale conns** | bounded pool + `pool_pre_ping` | pre-ping discards the dead connection | `25-data-postgres`; ladder row 6 |
| 16 | **Job stranded** (worker died holding it) | visibility timeout + orphan sweep | the sweep requeues it | `75-workers-jobs` |
| 17 | **Poison job** | attempt cap → dead-letter | the queue stops re-running it and drains | `75-workers-jobs` |
| 18 | **Duplicate side-effect** from a retry | `Idempotency-Key` on non-idempotent calls | the retry collapses onto the first result | here + `15-api-contracts` |
| 19 | **Disk fills** | retention + disk-space Beat task | old data is reaped before the volume fills | `RESILIENCE.md` §6e |
| 20 | **Clock moves** (NTP step, suspend) | `monotonic()` elapsed; absolute epoch deadlines | nothing to recover — jumps stop corrupting timers | here |
| 21 | **Operational failure → content verdict** | classifier defaults transient; terminal needs evidence | the item stays retryable, so a later run fixes it | here |
| 22 | **Nothing fails, nothing progresses** | monotonic progress counter + zero-progress alarm | the alarm fires once; recovery clears it | here (§ Provider-death) |

⚠️ **Rows 9 and 22 make "autorecovery" honest.** Everything else recovers a *call*; row 9 recovers the
*process*, and row 22 catches the case where every mechanism above works correctly and the system is
still dead. Retry, backoff and breakers cannot see an ABSENCE of events.

---

## Basic Resilience (ALL services with external calls)

The lifecycle doc mandates: **"every external call has timeout + retry with backoff. Circuit-breaker for repeated failures. Graceful fallback when dependencies are down."**

This is the minimum for ANY `httpx`, `fetch`, or SDK call to an external service.

### Python (httpx — async)

```python
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from tenacity import (
    RetryCallState, retry, retry_if_exception, stop_after_attempt, wait_random_exponential,
)

# 1. Configure the client ONCE with timeouts.
import structlog

logger = structlog.get_logger()

client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
    # Internal M2M calls add X-Internal-Token (35-security-auth); never to third parties.
)

# 2. WHICH failures are retryable. `raise_for_status()` raises HTTPStatusError, so a predicate
#    naming only TimeoutException/ConnectError never retries a 5xx or a 429 — it gives up on
#    exactly the failures backoff exists for.
# ⚠️ Every literal below is illustrative: each ships as a §7a env knob, read from settings.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_FALLBACK = wait_random_exponential(multiplier=1, max=10)  # JITTERED — see the rules below
_RETRY_AFTER_CAP_S = 60.0


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in RETRYABLE_STATUS


def _wait(state: RetryCallState) -> float:
    """Honour Retry-After (429/503) in BOTH legal formats, clamped; else jittered backoff."""
    exc = state.outcome.exception() if state.outcome else None
    if isinstance(exc, httpx.HTTPStatusError):
        raw = exc.response.headers.get("retry-after")
        if raw:
            delay: float | None
            try:
                delay = float(raw)                                   # delay-seconds
            except ValueError:
                try:                                                 # or an HTTP-date
                    delay = (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError):
                    delay = None                                     # unparseable → fall through
            # ⚠️ CLAMP BOTH BRANCHES, not just the top. `Retry-After: -1` or `nan` reaches
            # tenacity as a sleep length and raises ValueError("sleep length must be
            # non-negative") — which is NOT an httpx.HTTPError, so it sails past the
            # graceful fallback below and crashes the caller on one hostile header byte.
            if delay is not None and math.isfinite(delay):
                return min(max(delay, 0.0), _RETRY_AFTER_CAP_S)
    return _FALLBACK(state)


# 3. Wrap calls with retry + jittered backoff
@retry(
    stop=stop_after_attempt(3),
    wait=_wait,
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
async def fetch_data(item_id: str) -> dict:
    resp = await client.get(f"/items/{item_id}")
    resp.raise_for_status()
    return resp.json()

# 4. Graceful fallback at the call site
async def get_item(item_id: str) -> dict | None:
    try:
        return await fetch_data(item_id)
    except httpx.HTTPError:  # the base class — ReadError/RemoteProtocolError are TransportErrors
        logger.warning("external_service_unavailable", service="example", item_id=item_id)
        return None  # graceful degradation — caller handles missing data
```

**Rules:**
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
- **Timeout is mandatory.** No `httpx.get()` without explicit timeout. The default `httpx.Timeout(5.0)` is often too short for read — set per dependency.
- **Retry with JITTERED exponential backoff.** `tenacity` (Python) — 3 attempts, 1-10s, and
  **`wait_random_exponential` / `wait_exponential_jitter`, never bare `wait_exponential`**. Not a style
  preference: tenacity's own docstring says `wait_exponential`'s intervals "are fixed (i.e. there is no
  jitter) … *not* suitable for resolving contention between multiple processes for a shared resource".
  N workers that fail together retry in lockstep and re-hammer the dependency exactly as it recovers —
  the thundering herd. Every worker fleet here is that "multiple processes" case.
- **Which statuses are retryable.** Timeouts, connection errors and 5xx. Do **not** retry
  400/401/403/404/422 — a permanent client error retried is just load. ⚠️ **`429` and `408` are the
  exceptions and they matter most**: `429` is the commonest retryable response from a rate-limited
  vendor and `408` is transient by definition, so a flat "never retry 4xx" makes an agent give up on
  precisely the failure backoff exists for.
- **Honour `Retry-After`** (on `429`/`503`) — the server knows its recovery window better than your
  curve does. ⚠️ **Two legal formats**: delay-seconds (`120`) *or* an HTTP-date
  (`Wed, 21 Oct 2026 07:28:00 GMT`). Parse both, **clamp both ends** (a hostile `86400` must not park a
  worker for a day; a hostile `-1` must not raise out of your retry machinery), and fall back to
  jittered backoff when absent or unparseable. `tenacity.wait_exception` exposes the response for this.
- **⚠️ Inline retry vs PAUSE — and `429` is where they meet.** An inline retry handles a **blip**; a
  pause handles a **condition**, where every job will hit the same wall and retrying inline just
  multiplies load across the queue. The test is not the status code but **whether the next job would
  fail for the same reason**: a single `429` with a short `Retry-After` → honour it inline; repeated
  `429`s, or a `Retry-After` beyond your inline budget → `set_pause(key, ttl)` so one worker's
  discovery spares the whole queue. ⚠️ **Clamp that TTL too** (§7a): the inline cap stops a hostile
  `86400` parking ONE worker for a day; the same unvalidated value in a pause key parks the ENTIRE
  QUEUE for a day. A vendor number never becomes a TTL unclamped. This is why the classifier pauses on
  `402` — credit exhaustion is a condition, not a blip.
- **⚠️ Retry at ONE layer.** Retries compose multiplicatively: tenacity ×3 in a job, a queue retry ×3
  around it, your caller ×3 = up to **27** upstream calls per logical operation, long before a breaker
  sees a pattern. Pick the owning layer; make the inner ones fail fast. For worker jobs the queue retry
  IS the retry — do not also wrap the call in `@retry`.
- **⚠️ Retrying a non-idempotent write can double-charge, double-send or double-create.** A `POST` (or
  non-idempotent `PATCH`) needs an `Idempotency-Key` before it gets a retry — otherwise retrying after
  a timeout you never saw the response to is a second real mutation. `PUT`/`DELETE` are idempotent by
  HTTP semantics. `15-api-contracts` owns the SERVING side; this pack owns the caller's question —
  *may I retry this at all?* No key, no safety: surface the failure instead of retrying blind.
- **Graceful fallback** — cached data, a default, or a clear error. Never let an external failure crash
  your endpoint. ⚠️ That includes the *parse*: a `200` with malformed JSON raises `JSONDecodeError`,
  which is not an `httpx.HTTPError` and will sail straight past the `except` above.

### The timeout you didn't set (third-party libraries, shared sessions, DNS)

"Every external call has a timeout" is necessary but NOT sufficient. Three gaps bite repeatedly (`docs/LESSONS_LEARNT.md` Lessons 72 & 74):

1. **A library you call may make an un-timeout'd request through *your* session.** Hand a shared `requests.Session`/client to a third-party library and its internal `session.get(url)` sets no timeout → a stalled proxy (connection accepted, no bytes) blocks the socket read **forever**, hanging the worker. Put a **default timeout on the session itself** so every request inherits it:

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

2. **A request `timeout=` does NOT bound DNS resolution.** `requests`/`httpx`/`urllib3` timeouts cover connect + read, not `getaddrinfo` — a stalled resolver hangs *through* the timeout. Harden the resolver (static, immutable DNS) rather than trusting `timeout=`; diagnose with `getent ahostsv4 <host>` (hangs) vs `nslookup -type=A <host> 1.1.1.1` (instant). Long-lived clients get a resolver with its own deadline.

3. **A `while not <flag>: sleep()` wait is an unbounded hang in disguise.** Every "wait for condition" loop (network-up, lock acquired, dependency ready) needs a ceiling, then proceeds or bails to a transient error — otherwise it burns the job's whole hard-timeout budget exactly like a missing socket timeout.

### Node.js / TypeScript

```typescript
import { setTimeout } from 'timers/promises';

// Retry-After in BOTH legal formats → ms, or NaN when absent/unparseable.
// ⚠️ `Number(null)` is 0 and `Number('')` is 0 — so an ABSENT header must never reach
// Number() directly: it yields a 0 ms wait, i.e. an un-jittered hot loop against exactly
// the dependency you are trying to spare. Header-less 5xx is the COMMON case.
function retryAfterMs(raw: string | null): number {
  if (raw == null || raw.trim() === '') return NaN;
  const secs = Number(raw);
  if (Number.isFinite(secs)) return Math.max(secs, 0) * 1000;   // delay-seconds
  const at = Date.parse(raw);                                    // or an HTTP-date
  return Number.isFinite(at) ? Math.max(at - Date.now(), 0) : NaN;
}

async function fetchWithRetry(url: string, options: RequestInit = {}, maxRetries = 3): Promise<Response> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = globalThis.setTimeout(() => controller.abort(), 30_000);
      let resp: Response;
      try {
        resp = await fetch(url, { ...options, signal: controller.signal });
      } finally {
        clearTimeout(timeoutId);  // finally: a rejected fetch would otherwise leak the abort timer
      }
      // Same retryable set as § Python — `>= 500` alone returns a 429 as if it succeeded.
      if (!resp.ok && (resp.status >= 500 || resp.status === 429 || resp.status === 408)) {
        const err = new Error(`Retryable HTTP ${resp.status}`);
        (err as any).retryAfter = resp.headers.get('retry-after');
        throw err;
      }
      return resp;
    } catch (err) {
      if (attempt === maxRetries) throw err;
      // Honour Retry-After (capped), else JITTERED backoff. Un-jittered retries synchronise
      // across clients and re-hammer the dependency as it recovers — the thundering herd.
      const hinted = retryAfterMs((err as any)?.retryAfter ?? null);
      const backoff = Math.min(1000 * 2 ** attempt, 10_000) * (0.5 + Math.random());
      await setTimeout(Number.isFinite(hinted) ? Math.min(hinted, 60_000) : backoff);
    }
  }
  throw new Error('Unreachable');
}
```

### FastAPI Client Resilience (SaaS / Mobile)

Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry — wire them explicitly:

```typescript
// ONE client helper — reuse fetchWithRetry above; do not hand-roll a second retry loop.
const apiFetch = (path: string, options: RequestInit = {}) =>
  fetchWithRetry(`${API_BASE_URL}${path}`, {
    ...options,
    signal: options.signal ?? AbortSignal.timeout(30_000),  // never clobber a caller's signal
  });
```

- **Explicit timeout on every client→backend call** (`AbortSignal.timeout`) — the default `fetch` has
  none — and the retry, jitter, status set and `Retry-After` parsing all come from `fetchWithRetry`.
  A second, simpler client-side loop is how the 408/429 cases and the HTTP-date format get dropped.
- **Backend outage fallback:** cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** the app's auth client owns the refresh flow (`35-security-auth.md` Pattern A). Never scatter ad-hoc refresh logic across service calls.

### Circuit-Breaker Pattern

For dependencies that fail repeatedly, a circuit-breaker stops you hammering a dead service.
**Vendor it, don't hand-roll it** — `fabrik-lib/async-http-client/circuit_breaker.py` ships
`CircuitBreakerRegistry` (the module `self-healing` row 3 already names). The invariants below are the
CONTRACT to check any implementation against, not a spec to retype:

**The invariants any breaker must satisfy** — check the vendored module against these; a hand-rolled
dataclass gets them wrong by default, and each is a live production failure:

| Invariant | The bug when it's missing |
|---|---|
| **`closed → open`** at `failure_threshold` consecutive failures | — |
| **`open` returns the fallback IMMEDIATELY**, never a queued timeout wait | you re-pay the read timeout on every call to a dead dependency |
| **`open → half-open` after `recovery_timeout`, admitting a COUNTED few** (`half_open_max_calls`, default 1) | a half-open admitting every caller dumps full traffic onto a dependency that is halfway up, re-kills it, and repeats every `recovery_timeout` — the overload it opened to prevent, on a schedule |
| **A failed probe re-opens at once; only a probe success closes** | with no explicit `half-open → open` edge you rely on stale counters — and a `record_success()` that closes from ANY state lets a call *issued before the breaker opened* close it seconds later, erasing the recovery window |

- One breaker per dependency (not per endpoint); thresholds and `half_open_max_calls` are §7a knobs.
- **Per-PROCESS by design** — each replica learns independently, none can trip the fleet. Not a
  distributed breaker: never back it with Redis to "share" state. ⚠️ Corollary: with N workers, up to
  `N × failure_threshold` calls hit a dead dependency first. When that matters the fleet-wide stop is a
  **pause key**, not a breaker.
- **Record failures per logical operation, not per retry attempt** — a threshold of 5 around a ×3
  tenacity retry is 15 upstream calls, not 5.

---

## The lifecycle edges — boot and shutdown (rows 7–8)

Everything above bounds a call in a *running* process. The edges are where whole deploys are lost.

### Boot — a dependency that is not ready yet is not an error

**`depends_on` is start ORDER, not readiness**; `condition: service_healthy` gates only the *first*
start and says nothing about a dependency that restarts later. Postgres may be replaying WAL, Redis
loading its RDB, while the container already reads "up".

- **Retry your dependencies at boot: bounded, jittered, with a startup DEADLINE** (a §7a knob), then
  exit **non-zero** — the unbounded-conditional-wait ban applied to boot. An entrypoint that waits
  forever is worse than one that dies: Docker reports *Up* while it serves nothing.
- **Distinguish fatal from transient first** — a wrong password or missing env var will not fix itself:
  one high-signal line, then exit. Retrying a deterministic failure is a crash loop against the very
  dependency it waits for.
- **Never auto-run migrations at startup** — a one-shot deploy step (`30-ops` § Release & Admin).
- **A crash loop must be VISIBLE** — alert on container restart count (`55-observability`); restarting
  forever with nobody watching is a silent outage, not healing.

### Shutdown — SIGTERM is a normal event, not a failure

Every deploy and OOM-restart sends it. `stop_signal` defaults to `SIGTERM` and **`stop_grace_period`
defaults to 10 seconds**, after which Docker sends SIGKILL and in-flight work dies. The sequence:
**stop accepting new work → finish what is in flight → close pools and clients → exit.** Refusing
instantly is not a drain; closing pools first severs your own handlers. The app's shutdown timeout
must be **strictly less than `stop_grace_period`** or the grace period is decorative.

⚠️ **The "fail readiness first, then drain" step in every Kubernetes guide does NOT apply here by
default** — it lets a load balancer deregister one replica while its siblings serve, and this stack
does not set `deploy.replicas` on app services (`30-ops`). Add it only with real multi-replica
Traefik routing; unconditionally it buys a longer outage per deploy, not a shorter one.

- **Set `stop_grace_period` deliberately.** 10s suits a stateless API; a worker needs `>=` its longest
  task (`75-workers-jobs` sets 45s and owns the worker path, incl. the **SIGTERM requeue fast path**).
- **The signal must arrive.** Shell-form `CMD` makes `/bin/sh` PID 1, which never forwards SIGTERM —
  exec-form, or `sh -c "exec ..."` (`30-ops`).
- **Exit 143 is a clean SIGTERM exit; 137 is SIGKILL** (grace blown, or OOM) — 137 on stop events is a
  broken drain whatever the code looks like. **Prove it** with a real `docker kill --signal=SIGTERM`.

---

## Overload is a failure class (rows 10–13)

Retry, backoff and breakers assume the *dependency* is the problem. When **you** are the bottleneck they
make it worse. None of these primitives is a retry.

- **One absolute DEADLINE per logical operation, propagated — not a timeout per hop.** Per-hop timeouts
  compose into work outliving its caller: A gives up at 2s while B, C and D burn capacity on a result
  nobody will read. Pass an absolute deadline (epoch), derive each outbound timeout from
  `remaining - reserve`, and **short-circuit rather than start an attempt that cannot finish** in it.
  A retry scheduled past the deadline is pure amplification.
- **A per-request attempt cap does NOT cap fleet retry traffic** — 3 attempts still triples load when
  every request fails at once, exactly when the dependency is struggling. Add a **population retry
  budget** (token bucket, or a ~10% ratio ceiling) and fail fast when spent. Twin of § "Retry at ONE
  layer": that caps retry DEPTH, this its WIDTH.
- **Bound the queue, cap concurrency, then SHED.** Unbounded in-memory queueing turns overload into an
  OOM-kill (row 9) that loses everything buffered. Cap in-flight work with a semaphore; return
  **`503` + `Retry-After`** at the bound. A queued request past its deadline is dropped **on dequeue**.
- **Serve a hot key's rebuild ONCE.** On expiry every concurrent request misses at the same instant and
  stampedes the origin — a herd from your own cache, not a retry loop, so jitter and backoff never
  touch it. Coalesce behind a single-flight lock, or refresh before expiry.
- **Elapsed time is `time.monotonic()`; deadlines are absolute epoch.** An NTP step or a suspended
  container makes a wall-clock duration negative or enormous — an instant TTL, or a permanent one.

---

## When the resilience substrate itself fails (row 14)

Pause state, rate limits and dedup flags are all **Redis-backed** — so "what happens when Redis is
down" is a question about your resilience, not your cache. There is no safe default, and an undeclared
answer is whatever `except` clause someone wrote first. **Every Redis-gated decision DECLARES its
posture in §2b; the two are not interchangeable:**

| Posture | When Redis is unreachable | Use when |
|---|---|---|
| **fail-OPEN** | the guard is skipped, work proceeds | the guard OPTIMISES (rate limits, pause flags, dedup). A blip must not 503 the API — and if Redis died *of load*, failing closed removes the only thing still serving |
| **fail-CLOSED** | the guarded work is refused | the guard PROTECTS something a breach does not recover from — a contractual vendor limit, a paid-per-call dep, a spend cap |

- **Say it out loud, and COUNT it.** An `except RedisError:` returning `False` from `is_paused()` IS a
  fail-open decision — undeclared and invisible. Name the posture at the call site and emit a counter +
  log line when it fires, or the guard silently disables itself with no signal that it did.
- **Degrade, don't just open** — hold an approximate local bound (`global_limit / replicas`) instead.
- **Queue-bloat prevention is fail-open by construction** — a lost `dispatched:<id>` flag costs a
  re-dispatch, not data, since the DB is the source of truth (Property 4). **Pause keys are the
  dangerous ones**: losing them un-pauses a paused dependency, so the next detection event must re-set
  the flag — which is why detection is *both* proactive and reactive (Property 1).

---

## VPS Service Client Patterns

Each is an external dependency — timeout + retry + fallback per the patterns above. Starting timeouts
(tune per §7a; all on the `fabrik` network, via `httpx.AsyncClient` unless noted):

| Service | Timeout | Fallback |
|---|---|---|
| **Backblaze B2** (S3 API, `boto3`) | 30s connect / 120s read | return an error; never block a request on an upload |
| **Gotenberg** (PDF, `:3000`) | 60s — generation is slow | "PDF unavailable, retry later" |
| **Browserless** (`:3000`, or Playwright connect) | 30s | cached / fallback content |
| **Apprise** (notify, `:8000`) | 10s | log a warning, don't block — notifications are fire-and-forget |
| **MeiliSearch** (`:7700`, SDK or httpx) | 5s search / 30s indexing | search → empty results; indexing → retry via the job queue |

**Rules:**
- Credentials via env vars; every service you call needs its `docs/RESILIENCE.md` §2a row.
- B2 uploads go async via the job queue, never inline in a handler. **boto3 is sync** — keep it in the
  worker or a thread executor, never inside an `async def` route.
- B2 downloads use server-side presigned URLs (generation is local, no I/O — safe in async). Never
  proxy file bytes through FastAPI.

---

## The Per-Project Contract (`docs/RESILIENCE.md`)

Every scaffolded project gets `docs/RESILIENCE.md` from
`templates/scaffold/docs/RESILIENCE_TEMPLATE.md` — the source of truth for the full section list. The
non-negotiable ones:

| § | Why it's enforceable |
|---|---|
| **2a** Dependency inventory | an `httpx.get()`/`fetch()` call site with no row here → the PR is rejected |
| **2b** Detail card per dependency | failure signature, detection, timeout/retry, fallback, scope, **fail-open/closed posture**. Workers add: pause key, TTL+env, resume trigger, jobs affected, bloat note |
| **3a** Queue bloat prevention | required for `kind: worker` or any async job processing |
| **6** Concrete primitives | timeout/retry/CB; workers add pause state + classifier + `/health` checks + beat tasks |
| **7** Proactive monitoring | every billable external API needs a `<api>_balance_check` Beat row |
| **7a** Tuning knobs | every timeout, retry count, CB threshold, TTL and floor is one env var |
| **9** Accepted gaps | a gap without a `Review by` date is a bug, not a gap |
| **10** Recovery drills | a recovery procedure you have not run is a guess. Quarterly |

---

## Health Endpoint Contract

**There are TWO endpoints and they have different jobs** (`30-ops`, `55-observability`):
`/healthz` is the **dep-free LIVENESS** probe the compose `HEALTHCHECK` targets — it answers "is this
process alive", nothing more. `/health` is the **READINESS** probe Gatus consumes, and it actively
verifies critical dependencies before returning 200.

⚠️ **Never point `HEALTHCHECK` at the dependency-checking endpoint** — one `postgres-main` blip would
flip every container on the fleet to `unhealthy` at once. A DB blip degrades readiness; it must never
mark the container unhealthy.

`/health` verifies what the request path actually needs: DB (`SELECT 1`), Redis (`ping()`), consumed
internal APIs (`GET /health`, 5s), and object storage if it is on the critical path.

- Both endpoints are Authelia-bypassed on all services. Never protect them.
- Enforcement: `check_health.py` verifies real dependency checks exist (not a static 200).
- ⚠️ **Docker does NOT restart an unhealthy container.** `restart: unless-stopped` acts on process
  EXIT only; health status feeds `up --wait`, `depends_on: service_healthy` and Traefik routing —
  never a restart. A process that is **wedged but alive** is recovered by nothing in compose: that is
  the watchdog's Tier A `restart_container` (`60-watchdog`), and it is why the watchdog exists. Never
  design as if the daemon will do it.

**Workers:** `/health` returns 200 but carries a `paused` field listing active pause keys — operators
see pause state without it firing Gatus alerts. ⚠️ That deliberate green is exactly why a long pause
must escalate on its own (§ The Four Properties, property 2).

---

## Advanced: Autonomous Pause-State Pipeline (workers only)

Applies ONLY to `file-worker`, `file-api`, and any service with async job processing. `fabrik scaffold`
emits the canonical `pause_state.py` into every `python-api` and `file-worker` project — customise it
there. Production reference: `/opt/youtube/docs/reference/pipeline-resilience.md`.

### The Four Properties

1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail; error classifiers map exceptions to pause keys on the way through. Never one without the other for a critical dependency.
2. **Pause flags are sliding-TTL — which auto-clears a BLIP, not a CONDITION.** Every detection event
   refreshes the TTL, so the worst case is *one TTL after the cause stops* and **unbounded while it
   persists**. That is correct, and it is a trap: the queue is stopped while `/health` deliberately
   still returns 200 and Gatus stays green, so a fleet can sit paused for days with nothing paging.
   ⚠️ **So a pause carries its FIRST-set time and escalates exactly once past N× its TTL**
   (`self-healing` row 4; `fabrik-lib/alerting/`'s title dedup gives the exactly-one property). A
   sliding `SETEX` keeps no first-set timestamp — store it beside the flag, or that escalation is
   unimplementable. Detection with no terminus is not autorecovery.
3. **Queue depth = job count, exactly.** Dispatch-dedup + worker-keeps-flag-on-pause + sweeper-headroom together prevent the pause-then-re-queue-then-re-pause queue-explosion failure mode.
4. **The database is the source of truth.** Queues lose state on restart; orphan sweeps reconcile from the DB.

### Pause-Key Conventions

Redis key `<service_name>:pause:<resource>`, where the name is the `SERVICE_NAME` env var (required at
boot). Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`,
never permanent. Scope (§2c of the project's RESILIENCE.md):

| Scope | Use when |
|---|---|
| **global** | ≥50% of work hits this dep, or partial work is worthless (Postgres down, Redis maxmem) |
| **per-job-type** | the dep affects one job class — pausing everything is wasteful (a per-job API quota) |
| **per-token / per-key** | multi-tenant: one abusive tenant must not stop the others |
| **per-region / rotation** | the dep has multiple instances — rotate instead of stopping |

**Anti-pattern:** a global pause for a dependency only 5% of jobs need. It halts 95% of healthy work.

### Queue Bloat Prevention — The Five Mechanisms

All five must be present together. Any one missing → queues balloon under load.

| Mechanism | Implementation |
|---|---|
| **Dispatch dedup flag** | `<svc>:dispatched:<job_id>` (TTL 30 min) set on `dispatch_job()`, checked by every sweeper via `_filter_recently_dispatched()` (Redis `MGET`, O(1)) |
| **Worker keeps flag on pause-skip** | if `is_paused(...)`, return WITHOUT clearing → sweepers see "already queued", no re-push |
| **Worker clears flag on success** | `clear_dispatched_flag(job_id)` after the pause check passes → future retries may re-dispatch |
| **Sweeper headroom** | pull **4× the limit**, post-filter against dedup flags, trim — handles top-N all in-flight |
| **`create_job` auto-dispatches** | every `create_job(...)` bundles `dispatch_job(...)`; no caller path can create orphans |

### Error Classifier — One Source of Truth

There is ONE file (`src/error_classifier.py` or equivalent) mapping exception/log-pattern →
`(pause_key, ttl)`. Every worker error handler and HTTP middleware calls it; a new transient pattern is
edited in ONE place. The scaffold emits the starting table (`templates/scaffold/python/pause_state.py`,
`TRANSIENT_PATTERNS` — credit/`402`, DNS, pool-exhaustion, rate-limit/`429`); customise it there for
your dependencies, never inline at a call site.

### Operational failures are transient — never a terminal *content* verdict

The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and record a content terminal (`deleted`, `private`, `unavailable`…) only on **positive content evidence**. Everything else is transient.

| Outcome | Classify as | NOT as |
|---|---|---|
| Timeout / hard-kill (poison) / worker restart | transient · `processing_timeout` · retry (don't burn retry budget) | `unavailable` / `deleted` |
| Network / proxy / DNS error | transient → pause/retry | `no_captions` / `unavailable` |
| Lock contention (another worker holds the per-resource lock) | transient → short defer | a content failure |
| Empty API response *after* a timeout | inconclusive → re-verify | `deleted` (an empty body is not proof of removal) |
| API confirms removal / metadata says private / transcript genuinely empty after fallback | **terminal content verdict** (evidence exists) | — |

Why it matters: a terminal mislabeled transient costs a retry; a **transient mislabeled terminal is silent, unrecoverable data loss** — the user is told "unavailable" for content that is fine. Default transient; require evidence to escalate (`docs/LESSONS_LEARNT.md` Lesson 73).

---

## Provider-death resilience — unattended external-dependency loops (PLANNING-PHASE requirement)

**Applies to any unattended loop over an external dependency** — an LLM provider chain, an API a
backfill hammers, any long-running job whose forward progress depends on a third party you do not
control. A standard for every such service, not a suggestion; no such loop, no obligation.

**Why the rest of this pack is not enough.** Timeout, retry, backoff, breakers and checkpointing all
heal a **transient** fault. None heals a **permanent provider death**: an endpoint down for the whole
run needs a **SWAP**, a decision no retry loop is empowered to make. `self-healing` row 10 carries the
motivating incident — a backfill stalled 8h at zero progress while every mechanism here ran correctly,
and nothing alarmed, because zero progress is not an error.

**A plan or spec introducing such a loop states how it satisfies all THREE outcomes; retry/backoff with
no provider-death handling and no zero-progress alarm is a DEFECT** — what `/fabrik-spec-review` §E and
`/fabrik-plan-review` grade. **These are OUTCOMES; the mechanism depends on your ROUTE.**

| # | Required outcome | Routed through OpenRouter (the sanctioned gateway) | Calling a provider endpoint DIRECTLY |
|---|---|---|---|
| 1 | **No single point of death** — one model or endpoint dying must not stop the loop | **Declare** the mechanism in §2b. Outage-aware routing is step 1 of OpenRouter's default strategy and a `models` array falls back on **any** error. ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing, and the outage step is *part of* it** — pinning silently opts you out of the protection you think you have (claims row `openrouter-pin-disables-failover`); if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidates **once at run start** (never per item) and rebuild the chain from live survivors, best first, so it self-restores on recovery. Base it on `fabrik-lib/health-probe/`; the shared chain-rebuild helper is requested, not shipped, so promotion logic is project-local today. Needs **intra-provider** (2+ models of one provider) AND **cross-provider** diversity |
| 2 | **The last rung is actually exercised** | No gateway provides this — exercise it on a schedule | Same |
| 3 | **Absence of progress is alarmed** — N minutes of zero progress fires ONE alert, cleared on recovery | No gateway provides this. Export a monotonically-increasing **progress** counter (rows done, items classified) and alert on *it*, not on error codes. Threshold ≥ 2 full loop runs, a §7a knob. `fabrik-lib/alerting/`'s title dedup IS the exactly-one property | Same |

**"We use OpenRouter" is not a resilience design** — it is the name of a gateway that can be configured
out of the protection being claimed. Name the mechanism, not the vendor.

---

## Banned Patterns

| Pattern | Use Instead |
|---|---|
| `requests.get()` (sync, blocks event loop) | `httpx.AsyncClient` with explicit timeout |
| `httpx.get()` without explicit timeout | `httpx.Timeout(connect=5, read=30, write=10, pool=5)` |
| Handing a `requests.Session` to a 3rd-party library without a **default timeout on the session** | Wrap `session.request` with `kwargs.setdefault('timeout', (c, r))` — its internal calls may set none |
| Trusting a request `timeout=` to bound DNS | It doesn't cover `getaddrinfo` — harden the resolver, or give the client its own resolver deadline |
| `while not <flag>: sleep()` with no ceiling | Bound every conditional wait, then proceed or bail to a transient error |
| Recording an operational failure (timeout/network/proxy/hard-kill/lock) as a terminal **content** verdict | Default transient; a terminal content verdict requires positive evidence |
| External call site with no row in §2a of RESILIENCE.md | Add the row first, then the call site |
| Exiting on the FIRST failed dependency connection at boot — or waiting for it forever | Bounded jittered retry + startup deadline, then exit non-zero. An endless wait reports *Up* while serving nothing |
| App shutdown timeout `>=` `stop_grace_period`, or closing pools before in-flight work finishes | Drain, then close, then exit — app timeout strictly INSIDE the grace period |
| Unbounded in-memory queue or uncapped concurrency | Bound it, cap in-flight work, shed `503` + `Retry-After` — unbounded buffering turns overload into an OOM-kill that loses the buffer |
| A timeout per hop instead of one propagated deadline | One absolute deadline per operation; each hop derives its timeout from what remains |
| A per-request attempt cap as the ONLY retry limit | Add a population retry budget — a per-request cap does not bound FLEET retry traffic |
| Rebuilding an expired hot cache key without coalescing | Single-flight lock or early refresh — one rebuild serves every waiter |
| A Redis-gated guard with no DECLARED fail-open/fail-closed posture | Declare it in §2b and count when it fires — `except RedisError: return False` is an undeclared fail-open |
| Circuit-breaker whose half-open state admits unlimited callers | Cap concurrent probes; a failed probe re-opens immediately |
| Wall-clock (`datetime.now()`) for elapsed-time or TTL arithmetic | `monotonic()` for elapsed, absolute epoch for deadlines — an NTP step must not expire or freeze a timer |
| `time.sleep(N)` on transient error | Retry with JITTERED backoff (`tenacity.wait_random_exponential`) or `set_pause(key, ttl)` for workers |
| No fallback on external call failure | Graceful degradation: cached data, default, or clear error state |
| Global pause for a dep only one job-type uses | `defer_until_*()` on the job row (per-job-type scope) |
| Permanent flag (`SET` without TTL) on pause keys | `SETEX` / `set(ex=ttl)` — sliding-TTL is the contract |
| A pause key with no first-set timestamp — nothing can tell a 5-minute pause from a 5-day one | Store the first-set time beside the flag, escalate once past N× TTL — a silently-permanent pause is a stopped queue at Gatus-green |
| `try: ... except: pass` on upstream calls | Classifier → pause → re-raise. Silent swallow is data loss. |
| New TTL/timeout literal in code (e.g. `ttl=1800`) | Read from `os.environ["PAUSE_TTL_<RESOURCE>"]` — knob in §7a |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Two error classifiers in different files | One file. Always. |
| Adding a billable vendor without a balance check Beat task | Proactive check is mandatory for any dep with a balance |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule — an untested fallback is a silently-dead one, and the chain is a rung shorter than its author believes |
| An unattended external-dependency loop with **no zero-progress alarm** | A monotonic progress counter + an alert on it. Retry/backoff cannot detect an *absence* of events |
| Scattered ad-hoc token refresh across service calls | Centralize it in the auth client (`35-security-auth.md`) |

---

## Doc Sync — the lifecycle edges are DEPLOY-TIME facts (D-065)

`docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are how the hub's deploy AI learns what runs on the VPS and
how it behaves. Most of this pack is internal to a process and belongs in `docs/RESILIENCE.md` — but
four things are visible to whoever deploys, and **a change to any of them updates OPERATIONS.md (and
DEPLOYMENT.md where it is a deploy step) in the SAME change:**

- **`stop_grace_period`** — a redeploy stopping a worker mid-task loses it when this is wrong, and the
  deploy AI cannot infer "needs 5 minutes to drain" from the code.
- **Boot dependency order + the startup deadline** — what must be healthy first, and how long it waits.
- **The restart policy, and what a restart LOOP means here** — including which alert fires.
- **The §7a knobs that change behaviour under load** (concurrency cap, shed threshold, pause TTLs) — an
  operator tuning a live incident reads OPERATIONS.md, not the source.

Everything else stays in `docs/RESILIENCE.md`; mirroring it creates two copies that drift.

---

## Related Rule Packs

- `10-python.md` — Pydantic Settings, async httpx, error handling
- `15-api-contracts.md` — the SERVING side of `Idempotency-Key`; this pack owns the caller's question
- `57-external-data-sourcing.md` — WHAT to reach for + the Capability Profile whose "behaviour AT the
  cap" field says whether a dependency's 429 even carries a `Retry-After`
- `25-data-postgres.md` — engine/pool config (`pool_pre_ping`) — coverage-map row 15
- `30-ops.md` — HEALTHCHECK → `/healthz`, exec-form CMD (so SIGTERM arrives), restart policy, and the
  one-shot migration step boot must never do
- `self-healing.md` — the ORDER these primitives run in per failure class
- `35-security-auth.md` — M2M `X-Internal-Token` (internal calls only)
- `55-observability.md` — the `/healthz` vs `/health` split, GlitchTip capture, structlog
- `75-workers-jobs.md` — worker pool, orphan sweep, beat scheduler, DLQ, SIGTERM requeue
- `76-gpu-workers.md` — provider failover chain, orchestrator resilience

---

## Done When

### All services with external calls

- [ ] Every external call has an explicit timeout and a graceful fallback (cached data, default, or
      error state) — including on a malformed `200`.
- [ ] Retries use **jittered** backoff (`wait_random_exponential`/`wait_exponential_jitter`, never bare
      `wait_exponential`) on transient errors only.
- [ ] The retry predicate covers retryable STATUSES (408/429/5xx), not just transport exceptions — one
      naming only `TimeoutException`/`ConnectError` never retries a 429.
- [ ] `Retry-After` is honoured on 429/503, parsed in BOTH formats, and clamped at both ends.
- [ ] No retry wraps a non-idempotent write without an `Idempotency-Key` (`15-api-contracts` serves it).
- [ ] Circuit-breaker per external dependency (threshold + recovery from env vars).
- [ ] `docs/RESILIENCE.md` exists; §2a has a row for every external call site.
- [ ] Each dependency's card LINKS its Capability Profile (`57-external-data-sourcing`) rather than
      copying its numbers — the profile records the VENDOR's contract, this pack records YOUR handling
      of it, and its "behaviour AT the cap" field says whether 429 even carries a `Retry-After` here.
- [ ] Every timeout, retry count, CB threshold is an env var (§7a tuning knobs).
- [ ] **Every § coverage-map row this service can actually suffer has a mechanism AND a named
      autorecovery trigger.** A row whose recovery is "an operator notices" is not done.
- [ ] Boot: dependencies retry with bounded jittered backoff + a startup deadline; a fatal config
      error exits once with one high-signal line instead of crash-looping.
- [ ] Shutdown: in-flight work finishes, pools close, process exits — app timeout strictly inside a
      `stop_grace_period` set for the longest unit of work. **Proven with a real SIGTERM (exit 143).**
- [ ] One absolute deadline per logical operation, with every retry fitting inside it.
- [ ] Retry traffic is bounded at FLEET level (population budget), not only per request.
- [ ] In-flight work is capped; overload sheds `503` + `Retry-After`; nothing buffers unbounded.
- [ ] Every Redis-gated guard declares fail-open or fail-closed in §2b and counts when it fires.
- [ ] Circuit-breaker caps concurrent half-open probes; a failed probe re-opens it.
- [ ] Container restart count is alerted — an unwatched crash loop is a silent outage, not healing.

### Workers (additionally)

- [ ] §1 Shape Card filled; `Last drill` dated within 90 days.
- [ ] Every billable external API has a §2b detail card AND a §7 monitoring row.
- [ ] One error-classifier file; every `except` block calls it.
- [ ] Pause-key namespaces use `$SERVICE_NAME`; no literal TTLs in code (§7a env vars).
- [ ] Pause keys carry a first-set timestamp, and a pause outliving N× its TTL escalates exactly once.
- [ ] All five queue-bloat-prevention mechanisms are wired (§3a).
- [ ] `has_persistent_data: true` → disk-space Beat task running (§6e).
- [ ] §9 Accepted Gaps each carry a `Review by` date; §10 has a real `Last run`.

### SaaS / Mobile (additionally)

- [ ] Client→backend calls carry an explicit timeout and go through the ONE retry helper.
- [ ] Backend errors handled at the service layer; outage falls back to cached data or a clear error
      state — never a blank screen.
