---
activation: glob
globs: ["**/workers/**", "**/jobs/**", "**/tasks/**", "**/queue/**"]
description: Workers & jobs discipline — retry/backoff, dead-letter handling, idempotent job processing
trigger: glob
---

# Workers & Jobs Rules

Apply when working on background job processing, task queues, workers, or scheduled jobs. Skip for synchronous API logic, UI, or infrastructure files.

## PostgreSQL as Queue

- PostgreSQL 16 is the **default** message broker. External brokers (Celery, RabbitMQ, ARQ, Kombu) are banned. Redis is permitted **only** when PostgreSQL queue throughput is a proven bottleneck (>50,000 jobs/second) or for ephemeral fire-and-forget messages where data loss is acceptable.
- Use `SELECT ... FOR UPDATE SKIP LOCKED` for contention-free job dequeuing. Without `SKIP LOCKED`, concurrent workers block each other into a single-threaded bottleneck.
- Use libraries like PgQueuer or Procrastinate, or a custom `SKIP LOCKED` implementation.

## Transactional Enqueueing (Outbox Pattern)

- Insert jobs into the queue table within the **same ACID transaction** that modifies the primary business entity.
- If the primary transaction rolls back, the job must never exist. This eliminates dual-write inconsistencies between application state and the queue.

## Idempotency

- Accept **at-least-once delivery** as the baseline. Exactly-once is a distributed systems myth.
- Every job handler must be strictly idempotent. Derive the idempotency key **deterministically** from business properties (e.g. `SHA-256(user_id + action + timestamp)`).
- Store the key in a unique constraint column (dedicated `idempotency_keys` table or `processed_at` on the domain entity). On duplicate key, skip execution.
- **Never** use a runtime-generated random UUID as an idempotency key — it changes on every retry, defeating the check entirely.

## Retry & Backoff

- All job decorators / task definitions must explicitly declare `max_retries` and `retry_backoff`. Default-free decorators are banned.
- Default: `max_retries = 5`, exponential backoff with jitter: `delay = base * 2^attempt + random_jitter`.
- Base delay: 5 seconds. Jitter prevents thundering herd on external service recovery.

## Dead-Letter Handling

- Jobs exceeding `max_retries` must transition to `status = 'failed'` (in-place) or move to a dedicated `dead_letters` table.
- Poison-pill messages must never loop infinitely. The DLQ is for human inspection — automated agents do not resolve DLQ entries.

## Visibility Timeout

- Define a visibility timeout for each job type: **6× the expected average processing time**, minimum 30 seconds.
- If a worker dies mid-processing (OOM kill, network partition), peer workers reclaim the job after the visibility timeout expires.
- For long-running tasks, implement periodic heartbeat `UPDATE` statements to extend the lock window.

## Queue Table Schema

- Required columns: `id`, `task_name`, `payload` (JSONB), `status` (enum: pending/processing/completed/failed), `attempts`, `max_retries`, `run_at` (timestamp for scheduling + backoff), `created_at`.
- **Partial index is mandatory**: `CREATE INDEX idx_jobs_pending ON jobs(run_at) WHERE status = 'pending'`. Without it, workers trigger full table scans.

## Worker Wake-Up

- Use PostgreSQL `LISTEN/NOTIFY` to instantly wake idle workers on job insertion. Fall back to polling only as a safety net (e.g. 60-second timeout).
- Naive `while True: sleep(1)` polling is banned — it drains connections and wastes CPU on idle systems.

## Process Isolation & Lifecycle

- Execute job handlers in **forked child processes**. The parent monitors via `os.waitpid()`. If the child OOMs or segfaults, the parent marks the job failed and continues.
- Workers must trap `SIGTERM` and `SIGINT` via Python's `signal` module. On signal: stop accepting new jobs, finish the current task, then exit cleanly.
- Docker Compose `stop_grace_period` must be ≥ the longest possible task execution time (default: 45s).

## Docker Entrypoint

- Dockerfiles must use **JSON exec form**: `CMD ["python", "worker.py"]`. Shell form (`CMD python worker.py`) swallows SIGTERM — the shell becomes PID 1 and ignores the signal.
- Use `tini` as PID 1 init process to handle zombie child reaping and signal proxying: `ENTRYPOINT ["/usr/bin/tini", "--"]`.

## FastAPI BackgroundTasks

- `BackgroundTasks` is restricted to **ephemeral, non-critical** operations only (telemetry, transient logging).
- Any task requiring guaranteed execution or state mutation must go through the PostgreSQL job queue. `BackgroundTasks` runs in the asyncio event loop — a deployment restart destroys all in-flight tasks.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Celery / RabbitMQ / ARQ / Kombu for queuing | PostgreSQL `FOR UPDATE SKIP LOCKED` |
| Redis for queuing (default) | PostgreSQL `FOR UPDATE SKIP LOCKED` (Redis allowed only above 50k jobs/s or for ephemeral messages) |
| `SELECT FOR UPDATE` without `SKIP LOCKED` | Add `SKIP LOCKED` to prevent lock contention |
| `while True: sleep(1)` polling | `LISTEN/NOTIFY` with polling fallback |
| Random UUID as idempotency key | Deterministic hash from business properties |
| `asyncio.create_task()` / `BackgroundTasks` for durable work | PostgreSQL job queue via outbox pattern |
| Shell-form `CMD python worker.py` | JSON exec form `CMD ["python", "worker.py"]` |
| Worker without `signal.SIGTERM` handler | Trap SIGTERM, drain current job, exit cleanly |
| Queue table without partial index on `status = 'pending'` | `CREATE INDEX ... WHERE status = 'pending'` |

---

## Done When

- [ ] Jobs dequeued via `FOR UPDATE SKIP LOCKED` — no external broker dependencies.
- [ ] Job insertion occurs in the same transaction as the business state change (outbox pattern).
- [ ] Every job handler has a deterministic idempotency key — no random UUIDs.
- [ ] All task decorators declare explicit `max_retries` and `retry_backoff`.
- [ ] Failed jobs transition to `failed` status or DLQ table after exhausting retries.
- [ ] Partial index exists on the jobs table: `WHERE status = 'pending'`.
- [ ] Worker traps `SIGTERM` and drains cleanly before exit.
- [ ] Dockerfile uses JSON exec form for CMD/ENTRYPOINT.
- [ ] `stop_grace_period` in Docker Compose ≥ longest task execution time.
