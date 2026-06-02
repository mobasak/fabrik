---
activation: glob
globs: ["**/docs/RESILIENCE.md", "**/docs/SELF_HEALING.md", "**/pause_state*", "**/circuit_breaker*", "**/error_classifier*", "**/orphan_sweep*", "**/health*", "**/abuse_prevention*", "**/watchdog*", "**/specs/services/*.yaml"]
description: Self-healing escalation ladder — orchestrates the primitives in 58-resilience, 60-watchdog, 75-workers-jobs into one ordered response per failure class
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: One ordered escalation ladder per failure class — first response → fallback → human escalate — citing the primitives from 58-resilience, 60-watchdog, 75-workers-jobs without duplicating them.
     TRAYCER USAGE: When a ticket touches an external dep, async work, or anomaly handling, inject the relevant ladder row + cite this pack as a Context File. Do NOT re-derive the response — name the row and link.
     AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->

# Self-Healing Synthesis

**Activation:** Glob — pause-state, circuit-breaker, abuse-prevention, watchdog, health endpoints, and the per-project `docs/RESILIENCE.md` / `docs/SELF_HEALING.md`.
**Purpose:** **Self-healing in Fabrik = an autonomous-by-default escalation LADDER, NOT a new primitive.** Every step on the ladder is implemented by a primitive that already exists in [`58-resilience`](58-resilience.md), [`60-watchdog`](60-watchdog.md), [`75-workers-jobs`](75-workers-jobs.md), or a vendored fabrik-lib module. This pack's job is to **order** those primitives into one strict response chain per failure class so a service degrades gracefully instead of failing loud and panicking.

**Distinction from adjacent packs:**

- [`58-resilience`](58-resilience.md) — defines preventive primitives (timeout, retry, circuit-breaker, pause-state). Each primitive bounds one failure mode.
- [`60-watchdog`](60-watchdog.md) — the escalation engine. Tier A acts; Tier B opt-in; Tier C escalates to operator.
- **This pack** — the *order* in which those layers run per failure class.

---

## The escalation ladder

Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive) → **Fallback** (another primitive or a `60-watchdog` Tier A action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.

| # | Failure class | Symptom (observed) | 1. First response | 2. Fallback | 3. Escalate |
| --- | --- | --- | --- | --- | --- |
| 1 | **OOM** (main container memory exhaustion) | `oom-killer` line in `docker logs` + restart count delta; mem% > 95 % for >2 m | Docker `restart: unless-stopped` triggers itself (compose contract, [30-ops](30-ops.md)) | Watchdog Tier A `restart_container` (idempotent; refuses shared-infra targets per [60-watchdog](60-watchdog.md)) | Watchdog Tier C → Apprise; deadman re-restart at `deadman_timeout_seconds` |
| 2 | **Queue backlog** (workers can't keep up) | `queue_depth` gauge climbs; `oldest_unfinished_age_seconds` > worker SLA | Adaptive worker pool scale-up ([75-workers-jobs § Adaptive Worker Pool](75-workers-jobs.md)) | Watchdog Tier A `drop_queue_items` (oldest N first; bounded by `LIMIT` + identifier validation) | Watchdog Tier C → operator; consider widening `daily_invocations_cap` |
| 3 | **Upstream rate-limit** (vendor 429 / quota exceeded) | `_429` counter spike; `Retry-After` header present | `pause-state.set_global_pause(resource, ttl=Retry-After)` ([pause-state README § Usage example](../../../../opt/fabrik-lib/pause-state/README.md)) | `async-http-client.CircuitBreakerRegistry` flips OPEN for that upstream until probe succeeds | Watchdog Tier C → operator; check vendor billing |
| 4 | **Upstream timeout / network blip** | repeated `httpx.TimeoutException` or `ConnectError` from one upstream | `pause-state.classify_transient_error(msg) → (resource, ttl_sec)` → SETEX pause flag | Circuit breaker OPEN; queued work waits on pause flag, not on the dep | Watchdog Tier C if pause flag persists past `> 4 × ttl_sec` (dep is wedged, not transient) |
| 5 | **Signup flood** (abuse: bot signups + disposable emails) | `signups_per_ip_per_minute` ratio > threshold; disposable-domain hit rate high | `abuse-prevention` rejects at the registration guard ([abuse-prevention README § Usage](../../../../opt/fabrik-lib/abuse-prevention/README.md)) — progressive quota unlock for legitimate users | Watchdog Tier A `pause_worker` for the `signup` resource (Redis SETEX `<prefix>:pause:signup`) | Watchdog Tier C → operator; consider IP-range UFW block on the hub |
| 6 | **DB connection-pool exhaustion** | `pool.size == pool.max` for >30 s; new requests timeout in `await acquire()` | App-side: `await asyncpg.Pool.close()` then reopen via `/admin/reset-db-pool` endpoint | Watchdog **Tier B** `reset_db_pool` (opt-in via `auto_tier_b`; X-Internal-Token guarded) | Watchdog Tier C → operator; check for connection leak in code, not pool size |
| 7 | **Sustained 5xx burst** (downstream API returning 5xx > 50 % for 5 m) | http_5xx_spike rule in `60-watchdog._LOG_TRIGGERS` (>5 matches in window) | Circuit breaker OPEN against that endpoint; serve cached fallback if present (graceful degradation per [58-resilience § Banned Patterns](58-resilience.md) "No fallback on external call failure") | Watchdog Tier A `pause_worker` for the impacted resource if it gates a worker queue | Watchdog Tier C → operator; deadman re-alert if unacked |
| 8 | **Stuck row locks** (application-level lock held >max_age_sec) | `locked_at` column past `now() − interval` in workers' queue table | Worker's own orphan-sweep task ([75-workers-jobs § Orphan Sweep](75-workers-jobs.md)) | Watchdog Tier A `rotate_locks` (bounded by `max_age_sec` ∈ [30, 86400]) | Watchdog Tier C → operator; investigate why workers crash mid-lock |

**Why a strict order matters:** skipping rightward (e.g., escalating Tier C before letting the circuit breaker try) trains the operator to ignore alerts; falling-back leftward (e.g., re-trying the upstream while the breaker is OPEN) defeats the breaker. The ladder enforces both.

---

## Integration with watchdog

The right column of every ladder row maps to a [`60-watchdog`](60-watchdog.md) tier. Concretely:

- **Tier A (autonomous, default):** rows 1, 2, 5, 7, 8 use `restart_container`, `drop_queue_items`, `pause_worker`, `rotate_locks` respectively. No operator approval, no opt-in flag.
- **Tier B (opt-in via `spec.watchdog.auto_tier_b: true`):** row 6 uses `reset_db_pool`. Defaults to "skipped → escalate Tier C" until the spec author flips it on.
- **Tier C (escalate-only):** any row where the fallback step fails → Apprise → Telegram. Deadman timer rearms; if operator doesn't ack within `WatchdogConfig.deadman_timeout_seconds` (default 300), the watchdog runs `docker restart <main_container>` as bleed-stop and re-alerts with `[DEADMAN-TIMEOUT]`.

If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.

---

## Anti-patterns

These look like self-healing but aren't:

1. **Retry-without-backoff loop.** A `while True: try: call(); break; except: continue` against a wedged upstream is a denial-of-service against your own downstream. Use `tenacity` with explicit `wait_exponential(min, max)` per [58-resilience § Basic Resilience](58-resilience.md), or `pause-state.set_global_pause(resource, ttl)` if the failure is class-wide.
2. **Catch-all `except: pass` on upstream calls.** Silent swallow is data loss; you've removed the only signal a watchdog could see. Pattern from [58-resilience § Banned Patterns](58-resilience.md): classify → pause → re-raise.
3. **Kill-and-restart-everything panic.** When something goes wrong, restarting `traefik` + `postgres-main` + `redis-main` + all tenant containers (any panicked operator script) breaks every other tenant. Watchdog's `_FORBIDDEN_TARGETS` set in [`actions.py`](../../../fabrik-lib/watchdog/sidecar/actions.py) blocks 14 shared-infra names; honor the same list in any operator script.
4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran".
5. **Operational-failure-as-content-verdict.** Recording a timeout / network error as a terminal "this item is bad" decision means the next retry will re-fetch and re-fail; the pause-state pattern's whole point is that operational failures are transient ([58-resilience § Operational failures are transient](58-resilience.md)). Default transient/retryable; require positive content evidence before flipping terminal.

---

## Worked example — SaaS skeleton under signup flood

A SaaS (`shape.kind=service`) using the standard skeleton wires three primitives into one coherent ladder for the signup-flood failure class:

1. **First defense — `abuse-prevention/`** vendored into `libs/abuse_prevention/`. The registration route calls `guard_signup(ip, email, payload)` BEFORE any DB write; disposable-email domains and per-IP rate caps reject inside ~1 ms. Legitimate users hit the progressive quota unlock path.
2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>`. The pause flag is checked by every signup-handling worker via `pause_state.is_globally_paused("signup_<ip_hash>")` and they bail without touching the DB.
3. **Escalate — Watchdog Tier C → Apprise → Telegram.** If the pause flag is re-stamped >4 times within its TTL window (the abuse is sustained, not transient), the watchdog escalates with the IP hash + symptom counters. The operator decides whether to add a UFW deny rule on the hub — the watchdog does NOT touch UFW.

**What's notably missing from this ladder:** `iptables -A INPUT -s <ip> -j DROP` as a Tier A action. Network-level mutation against arbitrary IPs is operator-only because mis-classifying a CGNAT IP would ban thousands of legitimate users; the breaker stays at the application layer.

---

## Acceptance checklist (when shipping a per-project ladder)

- [ ] `docs/RESILIENCE.md` exists per [58-resilience § Per-Project Contract](58-resilience.md). Every external dep has a row.
- [ ] Each ladder step in the per-project doc names a primitive that exists in `fabrik-lib/` or a numbered rule pack — no inventions.
- [ ] Each step emits a Prometheus counter + a structlog row carrying the resource name (no silent action).
- [ ] If a row references Watchdog Tier B (currently row 6), the spec carries `watchdog: { auto_tier_b: true }`, and the operator has been notified of the opt-in.
- [ ] No anti-pattern from the section above is present in code — `grep -rn "while True:" src/` and `grep -rn "except: pass" src/` come back clean.
- [ ] The worked-example pattern (3 layers, last layer is always operator-bound) is the shape of every per-project ladder. If your ladder has >3 fully-autonomous layers, you've crossed into "panic" territory — collapse the bottom two into one explicit step and document the operator-bound terminal.

---

## Cross-references

- Preventive primitives: [`58-resilience`](58-resilience.md)
- Escalation engine: [`60-watchdog`](60-watchdog.md)
- Worker-specific patterns: [`75-workers-jobs`](75-workers-jobs.md)
- Container lifecycle (restart, memory limits): [`30-ops`](30-ops.md)
- Vendor modules cited: [`pause-state/`](../../../../opt/fabrik-lib/pause-state/), [`async-http-client/`](../../../../opt/fabrik-lib/async-http-client/), [`abuse-prevention/`](../../../../opt/fabrik-lib/abuse-prevention/)
