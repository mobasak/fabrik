---
activation: glob
globs: ["**/workers/**", "**/jobs/**", "**/tasks/**", "**/queue/**", "**/beat*", "**/scheduler*", "**/sweep*"]
description: Workers & jobs discipline — PG queue, retry/backoff, dead-letter, idempotency, pause-state, orphan sweep, beat tasks
trigger: glob
---

# Workers & Jobs Rules

Apply when working on background job processing, task queues, workers, scheduled/beat tasks, or orphan sweeps. Skip for synchronous API logic, UI, or infrastructure files.

---

## Applicability

| Scaffold | When this pack applies |
|---|---|
| `file-worker` | Always — core pattern |
| `file-api` | Always — processes files asynchronously |
| `python-api` | Only if the service has async jobs (file processing, email sending, data pipelines) |
| `saas-skeleton` | Only if the backend has background jobs (commission runs, report generation, data sync) |
| `node-api` | Only if async job processing exists |
| Other scaffolds | N/A |

---

## PostgreSQL as Queue

- PostgreSQL 16 on **`postgres-main:5432`** is the default message broker. External brokers (Celery, RabbitMQ, ARQ, Kombu) are banned. Redis (`redis-main:6379`) is permitted **only** when PostgreSQL queue throughput is a proven bottleneck (>50,000 jobs/second) or for ephemeral fire-and-forget messages where data loss is acceptable.
- Use `SELECT ... FOR UPDATE SKIP LOCKED` for contention-free job dequeuing. Without `SKIP LOCKED`, concurrent workers block each other into a single-threaded bottleneck.
- Use libraries like PgQueuer or Procrastinate, or a custom `SKIP LOCKED` implementation.
- Connection string: `postgres-main:5432`, never `localhost`. See `30-ops.md` § Docker DNS.

---

## Transactional Enqueueing (Outbox Pattern)

- Insert jobs into the queue table within the **same ACID transaction** that modifies the primary business entity.
- If the primary transaction rolls back, the job must never exist. This eliminates dual-write inconsistencies between application state and the queue.

---

## Idempotency

- Accept **at-least-once delivery** as the baseline. Exactly-once is a distributed systems myth.
- Every job handler must be strictly idempotent. Derive the idempotency key **deterministically** from business properties (e.g. `SHA-256(user_id + action + timestamp)`).
- Store the key in a unique constraint column (dedicated `idempotency_keys` table or `processed_at` on the domain entity). On duplicate key, skip execution.
- **Never** use a runtime-generated random UUID as an idempotency key — it changes on every retry, defeating the check entirely.

---

## Retry & Backoff

- All job decorators / task definitions must explicitly declare `max_retries` and `retry_backoff`. Default-free decorators are banned.
- Default: `max_retries = 5`, exponential backoff with jitter: `delay = base * 2^attempt + random_jitter`.
- Base delay: 5 seconds. Jitter prevents thundering herd on external service recovery.
- Retry counts and base delay are env vars (tuning knobs per `58-resilience.md` §7a).

---

## Dead-Letter Handling

- Jobs exceeding `max_retries` must transition to `status = 'failed'` (in-place) or move to a dedicated `dead_letters` table.
- Poison-pill messages must never loop infinitely. The DLQ is for human inspection — automated agents do not resolve DLQ entries.

---

## Visibility Timeout

- Define a visibility timeout for each job type: **6x the expected average processing time**, minimum 30 seconds.
- If a worker dies mid-processing (OOM kill, network partition), peer workers reclaim the job after the visibility timeout expires.
- For long-running tasks, implement periodic heartbeat `UPDATE` statements to extend the lock window.

---

## Orphan Sweep

Jobs can become orphaned when workers crash, are OOM-killed, or lose connectivity mid-processing. The visibility timeout handles reclamation for individual jobs, but a systematic orphan sweep is required:

- **Sweep query:** periodically scan for jobs with `status = 'processing'` and `updated_at < NOW() - visibility_timeout`. These are orphans — the worker that claimed them is dead.
- **Sweep action:** transition orphaned jobs back to `status = 'pending'` (if retries remain) or `status = 'failed'` (if retries exhausted).
- **Sweep frequency:** run via Beat task (see Beat/Scheduler below), every 5-10 minutes.
- **The database is the source of truth.** Queues lose state on restart; orphan sweeps reconcile from the DB. See `58-resilience.md` § Four Properties.
- **Dispatch-dedup integration:** if using the dispatch-dedup flag pattern from `58-resilience.md`, the sweep must check `_filter_recently_dispatched()` before re-enqueuing to prevent queue bloat.

---

## Queue Table Schema

- Required columns: `id`, `task_name`, `payload` (JSONB), `status` (enum: pending/processing/completed/failed), `attempts`, `max_retries`, `run_at` (timestamp for scheduling + backoff), `created_at`, `updated_at`.
- **Partial index is mandatory**: `CREATE INDEX idx_jobs_pending ON jobs(run_at) WHERE status = 'pending'`. Without it, workers trigger full table scans.
- `updated_at` is critical for orphan detection — it must be refreshed on every heartbeat and status transition.

---

## Worker Wake-Up

- Use PostgreSQL `LISTEN/NOTIFY` to instantly wake idle workers on job insertion. Fall back to polling only as a safety net (e.g. 60-second timeout).
- Naive `while True: sleep(1)` polling is banned — it drains connections and wastes CPU on idle systems.

---

## Beat / Scheduler (Periodic Tasks)

For recurring tasks (orphan sweep, vendor balance checks, report generation, cache warm-up):

- **Single-leader pattern:** only ONE instance runs the beat scheduler. Use `pg_advisory_lock` or a Redis `SET NX EX` to ensure single-leader across replicas. Without this, every replica fires every beat task — N replicas = N duplicates.
- **Schedule definition:** define beat tasks in a dedicated config file or table, not inline in application code. Each task has: name, callable, interval/cron, enabled flag.
- **Beat tasks are jobs.** The scheduler inserts into the same job queue — beat tasks are dispatched, not executed inline by the scheduler process.
- **Proactive monitoring:** every billable external API must have a `<api>_balance_check` Beat task. See `58-resilience.md` §7 Proactive Monitoring Schedule.

---

## Resilience Integration

Workers are the primary consumer of `58-resilience.md`'s advanced pipeline. Cross-reference:

| Concern | Defined in | What to do |
|---|---|---|
| Pause-state (sliding-TTL) | `58-resilience.md` § Pause-Key Conventions | Workers check `is_paused(key)` before processing. If paused, return WITHOUT clearing the dispatch-dedup flag. |
| Queue-bloat prevention (5 mechanisms) | `58-resilience.md` § Queue Bloat Prevention | All 5 mechanisms must be wired: dispatch-dedup, worker-keeps-flag, worker-clears-on-success, sweeper-headroom, create-job-auto-dispatches. |
| Error classifier | `58-resilience.md` § Error Classifier | ONE file maps exceptions to (pause_key, ttl). All worker `except` blocks call this classifier. |
| Vendor balance checks | `58-resilience.md` §7 | Beat tasks poll billable APIs proactively — before workers fail. |
| `docs/RESILIENCE.md` | `58-resilience.md` § Per-Project Contract | Every external call site in worker code must have a row in §2a. Every billable API must have a §7 Beat row. |

If the worker project does NOT have external dependencies (pure internal data processing), the pause-state pipeline is optional. But `docs/RESILIENCE.md` §2a still applies for any I/O.

---

## Observability

Workers need the same observability as any Fabrik service:

- **Structured logging:** `structlog` — JSON to stdout, `snake_case` event names. `print()` is banned. See `55-observability.md`.
- **Health endpoint:** `/health` must verify: DB connectivity (`SELECT 1`), Redis connectivity (if used), and that the worker process is alive and accepting jobs. Static 200 without dep checks is banned.
- **Metrics:** the scaffold emits `ACTIVE_JOBS` (Gauge), `PROCESSING_COUNT` (Gauge), `REQUEST_COUNT` (Counter), `ERROR_COUNT` (Counter). Expose via `/metrics` when `shape.exposes_metrics: true`.
- **GlitchTip:** init before worker starts processing. Unhandled exceptions in job handlers auto-capture. See `55-observability.md` § Error Reporting.
- **Correlation IDs:** if jobs originate from API requests, propagate the `X-Request-ID` into the job payload. The worker logs every event with this ID for traceability.

---

## Process Isolation & Lifecycle

- Execute job handlers in **forked child processes**. The parent monitors via `os.waitpid()`. If the child OOMs or segfaults, the parent marks the job failed and continues.
- Workers must trap `SIGTERM` and `SIGINT` via Python's `signal` module. On signal: stop accepting new jobs, finish the current task, then exit cleanly.
- Docker Compose `stop_grace_period` must be >= the longest possible task execution time (default: 45s).

---

## Adaptive Worker Pool (mandatory for all worker scaffolds)

Every `file-worker` and `file-api` scaffold must use the adaptive worker pool pattern. Fixed-concurrency workers waste resources when idle and bottleneck when loaded. The pool scales worker count between `min_workers` and `max_workers` based on queue depth and system resources.

### Architecture

```
Parent Process (PID 1 via tini)
├── monitor_loop     (1s tick)  — timeout enforcement, crash detection, respawn
├── metrics_loop     (60s tick) — logs worker stats as structured JSON
├── scale_loop       (30s tick) — reads queue depth, spawns/kills workers
└── N child processes (min..max)
    └── claim_loop — claim job via SKIP LOCKED → process → repeat
```

The parent is the **orchestrator only** — it never processes jobs. Children are forked processes, each running an independent claim loop against the PG queue.

### Resource Detection (container-aware)

The pool auto-detects available resources to calculate `max_workers`:

```python
# 1. Read container limits (cgroup v2)
cpu_max = read_file("/sys/fs/cgroup/cpu.max")        # "200000 100000" = 2 cores
mem_max = read_file("/sys/fs/cgroup/memory.max")      # bytes or "max"

# 2. Fall back to host resources
cpu_cores = multiprocessing.cpu_count()
available_mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")

# 3. Calculate
max_by_cpu = cpu_cores * 2                            # I/O-bound workload
max_by_memory = (available_mem_gb - reserved_gb) / mem_per_fork_mb
max_workers = min(max_by_cpu, max_by_memory, hard_cap)

# 4. Env overrides take precedence
max_workers = int(os.getenv("WORKER_MAX", max_workers))
min_workers = int(os.getenv("WORKER_MIN", max(1, max_workers // 4)))
```

**Rules:**
- Always read cgroup v2 first (`/sys/fs/cgroup/cpu.max`, `/sys/fs/cgroup/memory.max`) — these reflect Docker `deploy.resources.limits`, not the host.
- Fall back to host resources (`multiprocessing.cpu_count()`, `os.sysconf`) only when cgroup files are absent or contain `max` (unbounded).
- `WORKER_MIN` and `WORKER_MAX` env vars always take precedence over auto-detection.
- `mem_per_fork` should be measured per project (run a single worker, observe RSS). Default estimate: 95 MB for I/O-bound Python workers.
- `reserved_memory` covers OS, DB connections, Redis, and the parent process. Default: 2.0 GB.

### Scale-Up Rules

Every `scale_check_interval` (default 30s), the parent reads queue depth from DB:

1. **Condition:** `queue_pending > 0 AND busy_workers >= 80% of alive_workers`.
2. **Action:** spawn `scale_up_batch` workers (default 4) — gradual ramp, not all-at-once.
3. **Cap:** never exceed `max_workers`.
4. **Side effect:** reset the idle counter (prevents immediate scale-down after scale-up).

### Scale-Down Rules

1. **Condition:** `queue_pending == 0 AND busy_workers < 50% of alive_workers`.
2. **Hysteresis:** require `scale_down_idle_checks` consecutive idle checks (default 3, so 90s at 30s interval) before scaling down. Prevents flapping on bursty workloads.
3. **Selection:** kill workers from highest `slot_id` first — preserves stable low-numbered workers that have warm caches/connections.
4. **Safety:** only kill workers with `job_id == 0` (idle, not processing). Never kill a worker mid-job.
5. **Floor:** never go below `min_workers`.
6. **Side effect:** reset idle counter after any scale action.

### Backward Compatibility

`--concurrency=N` sets `min_workers = max_workers = N` — effectively disabling adaptive scaling. Existing scripts and compose commands that pass a fixed concurrency work unchanged.

### Parameters (all env-configurable)

| Parameter | Default | Env var | Notes |
|---|---|---|---|
| `min_workers` | auto (max/4, floor 1) | `WORKER_MIN` | Baseline capacity, always hot |
| `max_workers` | auto (CPU×2 or memory) | `WORKER_MAX` | Capped by system resources |
| `scale_check_interval` | 30s | `WORKER_SCALE_INTERVAL_SEC` | How often to check queue depth |
| `scale_down_idle_checks` | 3 | `WORKER_SCALE_DOWN_IDLE_CHECKS` | 3×30s = 90s before scaling down |
| `scale_up_batch` | 4 | `WORKER_SCALE_UP_BATCH` | Workers added per scale-up check |
| `mem_per_fork` | 95 MB | `WORKER_MEMORY_PER_FORK_MB` | Observed RSS per worker (measure per project) |
| `reserved_memory` | 2.0 GB | `WORKER_RESERVED_MEMORY_GB` | OS + DB + Redis headroom |

### Parent Process DB Connections (critical lesson)

The parent runs 3 loops (monitor, metrics, scale) that need DB access. Workers are forked children that each create their own connection pool. **The parent must NOT use the shared connection pool** — it competes with worker pools and causes `PoolError: connection pool exhausted`.

```python
# WRONG — competes with worker pools
from db_connection import get_db_connection
conn = get_db_connection()  # PoolError under load

# RIGHT — dedicated short-lived connection, no pool contention
import psycopg2
conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = True
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'pending'")
        pending = cur.fetchone()[0]
finally:
    conn.close()
```

Parent loops run infrequently (every 30-60s) — the overhead of connect/close per check is negligible. Pool contention under load is not.

### Health Endpoint Integration

The `/health` endpoint must report adaptive pool state:

```json
{
  "status": "ok",
  "workers": {
    "alive": 25,
    "busy": 20,
    "idle": 5,
    "min": 13,
    "max": 48
  },
  "queue": {
    "pending": 342,
    "processing": 20
  },
  "paused": []
}
```

Gatus checks the top-level `status`. Operators and dashboards consume the `workers` and `queue` objects for capacity planning.

### Metrics Integration

The `metrics_loop` (60s) emits structured JSON log and updates Prometheus gauges:

```python
WORKER_ALIVE = Gauge("worker_alive", "Currently alive workers")
WORKER_BUSY = Gauge("worker_busy", "Currently busy workers")
WORKER_IDLE = Gauge("worker_idle", "Currently idle workers")
WORKER_MAX = Gauge("worker_max_configured", "Configured max workers")
QUEUE_PENDING = Gauge("queue_pending", "Jobs pending in queue")
```

These augment (not replace) the scaffolded `ACTIVE_JOBS` and `PROCESSING_COUNT` gauges.

---

## Docker & Compose

Workers deploy via Coolify like any other Fabrik service. Apply all `30-ops.md` rules:

```dockerfile
FROM python:3.12-slim-bookworm
WORKDIR /app
# ... (uv sync, copy, etc. — see 30-ops.md Dockerfile template)
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.worker"]
```

- **`tini` as PID 1** — handles zombie child reaping and signal proxying. Without it, forked child processes become zombies.
- **JSON exec form** for CMD — shell form swallows SIGTERM.
- **`slim-bookworm`** base image, `platform: linux/amd64`.
- **`deploy.resources.limits.memory`** mandatory in compose.yaml. Workers processing large files may need higher limits than API services.
- **`coolify` network** — worker connects to `postgres-main:5432` and `redis-main:6379` via Docker DNS.
- **No `ports:` section** in compose.yaml — Traefik routes all traffic. See `30-ops.md`.
- **Traefik labels required** — workers expose `/health` (Gatus) and `/metrics` (Prometheus) via HTTP. These endpoints need Traefik labels even though the worker's primary job is background processing, not serving API requests.

---

## FastAPI BackgroundTasks

- `BackgroundTasks` is restricted to **ephemeral, non-critical** operations only (telemetry, transient logging).
- Any task requiring guaranteed execution or state mutation must go through the PostgreSQL job queue. `BackgroundTasks` runs in the asyncio event loop — a deployment restart destroys all in-flight tasks.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Celery / RabbitMQ / ARQ / Kombu for queuing | PostgreSQL `FOR UPDATE SKIP LOCKED` |
| Redis for queuing (default) | PostgreSQL (Redis only above 50k jobs/s or ephemeral) |
| `SELECT FOR UPDATE` without `SKIP LOCKED` | Add `SKIP LOCKED` to prevent lock contention |
| `while True: sleep(1)` polling | `LISTEN/NOTIFY` with polling fallback |
| Random UUID as idempotency key | Deterministic hash from business properties |
| `asyncio.create_task()` / `BackgroundTasks` for durable work | PostgreSQL job queue via outbox pattern |
| Shell-form `CMD python worker.py` | JSON exec form `CMD ["python", "-m", "src.worker"]` |
| Worker without `signal.SIGTERM` handler | Trap SIGTERM, drain current job, exit cleanly |
| Queue table without partial index on `status = 'pending'` | `CREATE INDEX ... WHERE status = 'pending'` |
| Missing `updated_at` on job rows | Required for orphan detection |
| `print()` in worker code | `structlog` structured logger |
| `/health` returning static 200 | Verify DB + Redis + worker-alive before 200 |
| Missing `docs/RESILIENCE.md` row for external deps | Add row to §2a before adding the call site |
| Beat scheduler without single-leader lock | `pg_advisory_lock` or Redis `SET NX EX` |
| Multiple replicas each running their own beat | Single-leader beat, all replicas run workers |
| `localhost` in DB/Redis connection strings | `postgres-main:5432`, `redis-main:6379` |
| Fixed-concurrency workers (`--concurrency=N` as the only mode) | Adaptive worker pool with auto-scaling between min/max |
| Reading host resources inside a container without checking cgroup | Read cgroup v2 first, fall back to host |
| Parent process using the shared connection pool | Dedicated `psycopg2.connect()` per parent loop iteration |
| Killing workers mid-job during scale-down | Only kill workers with `job_id == 0` (idle) |
| Immediate scale-down on first idle check | Require `scale_down_idle_checks` consecutive idle checks (hysteresis) |
| Hardcoded worker count without env override | `WORKER_MIN` / `WORKER_MAX` env vars |

---

## Related Rule Packs

- `10-python.md` — Python/FastAPI patterns, `uv`, structlog, async
- `30-ops.md` — Dockerfile, compose.yaml, Traefik, resource limits, Coolify deploy
- `55-observability.md` — structured logging, `/health`, `/metrics`, GlitchTip
- `58-resilience.md` — pause-state pipeline, queue-bloat prevention, error classifier, vendor balance checks, `docs/RESILIENCE.md` contract
- `45-testing-strategy.md` — test workers with real PostgreSQL, no DB mocks

---

## Done When

- [ ] Jobs dequeued via `FOR UPDATE SKIP LOCKED` on `postgres-main` — no external broker dependencies.
- [ ] Job insertion occurs in the same transaction as the business state change (outbox pattern).
- [ ] Every job handler has a deterministic idempotency key — no random UUIDs.
- [ ] All task definitions declare explicit `max_retries` and `retry_backoff` (env vars, not literals).
- [ ] Failed jobs transition to `failed` status or DLQ table after exhausting retries.
- [ ] Partial index exists on the jobs table: `WHERE status = 'pending'`.
- [ ] `updated_at` column exists and refreshes on heartbeat and status transitions.
- [ ] Orphan sweep runs via Beat task, reclaims stale `processing` jobs.
- [ ] Beat scheduler uses single-leader lock (`pg_advisory_lock` or Redis `SET NX EX`).
- [ ] Worker traps `SIGTERM` and drains cleanly before exit.
- [ ] Dockerfile uses `tini` as ENTRYPOINT, JSON exec form for CMD, `slim-bookworm` base.
- [ ] `stop_grace_period` in compose >= longest task execution time.
- [ ] `deploy.resources.limits.memory` set in compose.yaml.
- [ ] Structured logging via `structlog` — no `print()`.
- [ ] `/health` endpoint verifies DB + Redis + worker-alive.
- [ ] `/metrics` exposes `ACTIVE_JOBS`, `PROCESSING_COUNT` gauges.
- [ ] GlitchTip initialized before worker starts processing.
- [ ] `docs/RESILIENCE.md` §2a has a row for every external call site in worker code.
- [ ] For workers with external deps: pause-state pipeline wired per `58-resilience.md`.
- [ ] For workers with billable APIs: balance-check Beat tasks running per §7.
- [ ] Adaptive worker pool implemented: parent orchestrator + N forked children.
- [ ] Resource detection reads cgroup v2 first, falls back to host, respects `WORKER_MIN` / `WORKER_MAX` env vars.
- [ ] Scale-up: triggers when `queue_pending > 0 AND busy >= 80%`; adds workers in batches, not all-at-once.
- [ ] Scale-down: requires 3 consecutive idle checks (hysteresis); kills highest slot_id first; only idle workers; never below `min_workers`.
- [ ] `--concurrency=N` backward-compat: sets `min = max = N`, disabling adaptive scaling.
- [ ] Parent DB access uses dedicated connections, not the shared pool.
- [ ] `/health` reports worker pool state (alive, busy, idle, min, max) + queue depth.
- [ ] Prometheus gauges: `worker_alive`, `worker_busy`, `worker_idle`, `queue_pending`.
