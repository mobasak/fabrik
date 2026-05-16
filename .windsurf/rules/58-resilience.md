---
activation: glob
globs: ["**/docs/RESILIENCE.md", "**/pause_state*", "**/error_classifier*", "**/circuit_breaker*", "**/healthz*", "**/readyz*", "**/orphan_sweep*", "**/balance_check*", "**/dispatch*", "**/beat.py", "**/celerybeat*"]
description: Autonomous resilience contract — pause-state, sliding-TTL recovery, queue-bloat prevention, error classifier, vendor-balance checks
trigger: glob
---

# Resilience & Autonomy Rules

**Activation:** Glob — any file in the autonomous-recovery path (RESILIENCE.md, pause state, error classifier, health/ready endpoints, orphan sweep, beat tasks, vendor balance checks, dispatchers).
**Purpose:** Encode the autonomous SaaS-grade recovery contract proven in the YouTube pipeline. Every project ships with a `docs/RESILIENCE.md` that is treated as code.

---

## The Four Properties

A SaaS-grade autonomous system is defined by FOUR properties. Every project covered by this rule MUST exhibit all four:

1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail. Error classifiers map exceptions to pause keys on the way through. Never one without the other for any critical dependency.
2. **Pause flags are sliding-TTL.** Set/refreshed by every check, auto-clear when checks stop firing. No human page. No permanent stuck state. Worst case: a 30-minute TTL.
3. **Queue depth = job count, exactly.** Dispatch-dedup + worker-keeps-flag-on-pause + sweeper-headroom together prevent the pause→re-queue→re-pause→queue-explodes failure mode.
4. **The database is the source of truth.** Queues lose state on restart; orphan sweeps reconcile from the DB.

Canonical implementation: `/opt/youtube/docs/reference/pipeline-resilience.md` + `pause_state.py`. Read it before rolling your own.

---

## The Per-Project Contract (`docs/RESILIENCE.md`)

Every project scaffolded by Fabrik gets `docs/RESILIENCE.md` from `templates/scaffold/docs/RESILIENCE_TEMPLATE.md`. Its 14 sections are the contract. The non-negotiable ones:

| § | Title | Why it's enforceable |
|---|---|---|
| 2a | Dependency Inventory — summary | If a `fetch()` / `httpx.get()` / `aiohttp.request()` call site has no row here, the PR is rejected. |
| 2b | Detail card per dependency | Failure signature, detection mechanism, pause key, TTL+env, scope, resume trigger, jobs affected, bloat note. |
| 3a | Queue Bloat Prevention | Required if `kind: worker` or any async job processing. |
| 6 | Concrete Primitives | Pause state + classifier + /healthz + /readyz + disk Beat + storage tiering. Copy-paste, don't redesign. |
| 7 | Proactive Monitoring Schedule | Every billable external API MUST have a `<api>_balance_check` Beat row. |
| 7a | Tuning Knobs | Every TTL, floor, threshold = a single env var. |
| 9 | Accepted Gaps | A gap without a `Review by` date is a bug, not a gap. |
| 10 | Recovery Drills | A recovery procedure you haven't run is a guess. Quarterly. |

---

## Pause-Key Conventions

- Namespace: `<service_name>:pause:<resource>` (Redis key).
- Service name is `SERVICE_NAME` env var, required at boot.
- Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`, never permanent.
- Scope (see §2c of the project's RESILIENCE.md):

| Scope | Use when | Example |
|---|---|---|
| **global** | ≥50% of work hits this dep, or partial work is worthless | Postgres down, Redis maxmem |
| **per-job-type** | Dep affects only one job class — pausing everything is wasteful | YouTube Data API quota → per-job `defer_until_*` |
| **per-token / per-key** | Multi-tenant — one abusive tenant must not stop others | API token rate limit |
| **per-region / rotation** | Dep has multiple instances; rotate instead of stop | Multi-key API quota rotation |

**Anti-pattern:** defaulting to global pause for a dependency only 5% of jobs need. That halts 95% of healthy work.

---

## Queue Bloat Prevention — The Five Mechanisms (for `kind: worker`)

All five must be present together. Any one missing → queues balloon under load.

| Mechanism | Implementation |
|---|---|
| **Dispatch dedup flag** | `<svc>:dispatched:<job_id>` (TTL 30 min) set on `dispatch_job()`, checked by all sweepers via `_filter_recently_dispatched()` (Redis `MGET`, O(1)). |
| **Worker keeps flag on pause-skip** | If `is_paused(...)`, worker returns WITHOUT clearing flag → sweepers see "already queued" → no re-push. |
| **Worker clears flag on success** | After pause check passes, `clear_dispatched_flag(job_id)` runs → sweepers may re-dispatch on future retry. |
| **Sweeper headroom** | Sweepers pull **4× their limit**, post-filter against dedup flags, trim to limit. Handles top-N all in-flight. |
| **`create_job` auto-dispatches** | Every `create_job(...)` call bundles `dispatch_job(...)`. No caller path can create orphans. |

---

## Health Endpoint Contract

Required for every `kind: service` with `is_public: true`:

| Endpoint | Always returns | Semantics |
|---|---|---|
| `GET /healthz` | **200**, unless the process is literally dead | Liveness — "is the bin running?" |
| `GET /readyz` | **200** if no critical pause active; **503** with `{paused: <key>}` body if any is | Readiness — "can we serve traffic right now?" |

Gatus probes `/healthz` for uptime SLO. Load balancer / Coolify uses `/readyz` for traffic gating. NEVER conflate the two.

---

## Error Classifier — One Source of Truth

There is ONE file (`src/error_classifier.py` or equivalent) that maps exception/log-pattern → (pause_key, ttl). All worker error handlers and HTTP middleware call this single classifier. Adding a new transient pattern means editing ONE place.

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
| `requests.get()` / `httpx.get()` site with no row in §2a of RESILIENCE.md | Add the row first, then the call site |
| `time.sleep(N)` on transient error | `set_pause(key, ttl)` and return — let the sweeper retry |
| Global pause for a dep only one job-type uses | `defer_until_*()` on the job row (per-job-type scope) |
| Permanent flag (`SET` without TTL) on pause keys | `SETEX` / `set(ex=ttl)` — sliding-TTL is the contract |
| `try: ... except: pass` on upstream calls | Classifier → pause → re-raise. Silent swallow is data loss. |
| New TTL literal in code (e.g. `ttl=1800`) | Read from `os.environ["PAUSE_TTL_<RESOURCE>"]` — knob in §7a |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| `/healthz` that pings the DB | That's `/readyz`. `/healthz` is "is the process alive?" only |
| Two error classifiers in different files | One file. Always. |
| Adding a billable vendor without a `<vendor>_balance_check` Beat task | Proactive check is mandatory for any dep with a balance |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |

---

## Done When

- [ ] `docs/RESILIENCE.md` exists, §1 (Shape Card) is filled, and `Last drill` has a date within the last 90 days.
- [ ] Every external call site in the codebase has a matching row in §2a.
- [ ] Every billable external API has both: a §2b detail card AND a row in §7 (Proactive Monitoring Schedule).
- [ ] Single error-classifier file exists; every `except` block calls it.
- [ ] `GET /healthz` and `GET /readyz` exist and obey the contract above (services).
- [ ] All pause-key namespaces use `$SERVICE_NAME` env var.
- [ ] No literal TTL constants in code — all read from env vars listed in §7a.
- [ ] For workers: all five queue-bloat-prevention mechanisms are wired (§3a).
- [ ] For services with `has_persistent_data: true`: disk-space Beat task running (§6e).
- [ ] §9 Accepted Gaps each have a `Review by` date.
- [ ] §10 Recovery Drills have at least one row with a real `Last run` date.

Reference: `templates/scaffold/docs/RESILIENCE_TEMPLATE.md` (the source of truth for the contract structure).
