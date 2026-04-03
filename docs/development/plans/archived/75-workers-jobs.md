# **75-workers-jobs.md: Architecture and Enforcements for Background Processing**

## **1\. Executive Summary**

The architectural trajectory of modern background processing for resource-constrained environments demands a rigorous pivot away from complex, multi-broker topologies. Historically, distributed systems have defaulted to deploying dedicated message brokers such as Redis, RabbitMQ, or Apache Kafka to manage asynchronous workloads. However, for the Fabrik platform—constrained by a single developer’s capacity of approximately fifty focused hours per week, hosted on an ARM64 Ubuntu Virtual Private Server via Coolify, and bounded by stringent low-maintenance requirements—introducing secondary infrastructure solely for queue management constitutes a significant architectural anti-pattern.1

The optimal, durable, and low-maintenance model for 2025 and 2026 relies exclusively on PostgreSQL 16 as the converged operational and queuing database. By leveraging PostgreSQL's SELECT... FOR UPDATE SKIP LOCKED mechanism, combined with LISTEN/NOTIFY for sub-second task distribution, the architecture achieves high-concurrency, exactly-once dequeue semantics without the operational overhead of maintaining a Redis cluster.1 Benchmark data indicates that while Redis BRPOP operations average 0.1ms and PostgreSQL SKIP LOCKED averages 0.3ms, this 0.2ms differential is negligible for nearly all application workloads.7 Conversely, the reduction in infrastructure complexity, network hops, and point-of-failure vectors yields massive dividends in systemic reliability, as PostgreSQL is capable of handling up to 50,000 jobs per second natively.1

This exhaustive report establishes the canonical engineering standards for asynchronous task execution within the Fabrik technology stack, which comprises Python, FastAPI, and PostgreSQL. It mandates strict adherence to at-least-once processing semantics bound by immutable idempotency constraints, definitive dead-letter handling, and rigorous graceful shutdown protocols orchestrating Linux POSIX signals (SIGTERM) within Docker containers.8 The objective is to codify these principles into a permanent, automated rule file (75-workers-jobs.md) that acts as an unyielding architectural constraint for all autonomous agents operating within the Fabrik ecosystem.

The findings dictate that a PostgreSQL-native queueing library, such as PgQueuer or Procrastinate, or a meticulously structured custom SKIP LOCKED implementation, is the definitive standard.5 Furthermore, transient in-memory background tasks, such as FastAPI's BackgroundTasks, are strictly relegated to non-critical, ephemeral, fire-and-forget operations, while all durable state mutations must traverse the PostgreSQL transactional outbox and worker pipeline.13 The following sections dissect the theoretical underpinnings, practical enforcement mechanisms, and systemic guardrails required to maintain this zero-overhead, highly durable architecture over the next several years.

## **2\. Canonical Rules for the Rule File**

The following principles form the immutable foundation of the Fabrik background processing architecture. These directives must be enforced across all system states, pull requests, and autonomous agent code-generation actions.

| Rule ID | Architectural Directive | Core Mechanism | Primary Objective |
| :---- | :---- | :---- | :---- |
| **CR-01** | PostgreSQL-Exclusive Queuing | FOR UPDATE SKIP LOCKED | Eliminate secondary broker (Redis) infrastructure. |
| **CR-02** | Strict Idempotency by Default | Deterministic Hash Keys | Prevent duplicate state mutations during network partitions. |
| **CR-03** | Transactional Enqueueing | The Outbox Pattern | Guarantee absolute atomicity between application state and job creation. |
| **CR-04** | Dead-Letter Queue (DLQ) Routing | Threshold-based table migration | Prevent infinite processing loops caused by poison-pill messages. |
| **CR-05** | Exponential Backoff with Jitter | Randomized polynomial delays | Mitigate thundering herd phenomena upon external service recovery. |
| **CR-06** | Explicit Visibility Windows | ![][image1] | Reclaim jobs abandoned by catastrophic worker node failures (e.g., OOM kills). |
| **CR-07** | Heartbeat Monitoring | Periodic UPDATE statements | Safely extend visibility for inherently long-running tasks without risking zombie locks. |
| **CR-08** | Graceful POSIX Termination | signal.SIGTERM trapping | Ensure database connections drain cleanly before container destruction. |
| **CR-09** | PID 1 Container Compliance | JSON Array exec format in Docker | Prevent shell wrappers from swallowing OS termination signals. |
| **CR-10** | Composite B-Tree Indexing | Partial indexes on pending status | Prevent sequential table scans that devastate database CPU resources. |
| **CR-11** | Process Isolation | Sub-process worker forks | Protect the master orchestrator from child memory leaks or segmentation faults. |
| **CR-12** | In-Memory Task Restriction | FastAPI BackgroundTasks limits | Prevent the loss of critical financial or state data during application restarts. |
| **CR-13** | At-Least-Once Acceptance | Distributed Systems Theory | Abandon the pursuit of exactly-once delivery; rely wholly on idempotency. |
| **CR-14** | Base Image Exclusivity | slim-bookworm (Debian) | Avoid musl libc compilation overhead and bugs associated with Alpine Linux. |
| **CR-15** | Native SQL Observability | pg\_stat\_statements & SQL Aggregates | Monitor queue depth and latency without deploying secondary dashboard UI services. |

The rationale and implementation details for these canonical rules are deeply intertwined with the realities of managing a distributed system as a solo developer.

The mandate for PostgreSQL-exclusive queuing (CR-01) fundamentally alters the operational posture of the Fabrik platform. Traditional architectures often introduce Redis to utilize its BRPOP or Streams capabilities, absorbing a latency of 0.1ms.7 However, maintaining Redis requires managing its memory eviction policies, securing its network boundaries, and orchestrating its persistence to disk (AOF or RDB). By employing PostgreSQL 9.5+ and its SKIP LOCKED feature, multiple worker processes can concurrently query the jobs table. The lock manager seamlessly bypasses rows held by sibling workers, instantly returning the next available unlocked row. This yields perfect linear scaling up to the database's connection limits, allowing a single relational database to handle both transactional state and message passing with zero additional infrastructure.1

Idempotency (CR-02) and Transactional Enqueueing (CR-03) are inextricably linked. The Transactional Outbox pattern ensures that the creation of a background job occurs within the exact same ACID transaction that modifies the primary business entity.16 If a user creation process fails midway, the transaction rolls back, and the welcome email job is never committed to the queue. This eliminates the dual-write problem, where a system might successfully write to a Postgres database but fail to push a message to a standalone Redis queue due to a sudden network partition.4 Furthermore, because the architecture accepts at-least-once delivery (CR-13)—acknowledging that network hiccups will occasionally cause a worker to process a job, fail to acknowledge it, and allow it to be re-processed—every task must be strictly idempotent.10 Idempotency keys must be deterministically derived from the business logic (e.g., creating a SHA-256 hash of the user ID, action type, and timestamp) and stored within a unique constraint column. If a retry occurs, the database will reject the duplicate key, allowing the worker to safely discard the redundant task.8

Systemic degradation is managed through Dead-Letter Queues (CR-04) and Exponential Backoff (CR-05). Poison-pill messages—tasks containing malformed data that will deterministically crash the worker—must not be allowed to consume CPU cycles indefinitely. Once a task exceeds a hardcoded retry threshold, it is atomically moved to a DLQ table for manual inspection.20 For transient errors, such as a rate-limited external API, retries must utilize an exponential backoff formula, typically ![][image2]. The addition of randomized jitter is crucial; without it, a recovering external service would immediately be overwhelmed by perfectly synchronized retries from the queue, causing cascading failures.10

Worker lifecycle management (CR-08, CR-09) dictates how the application behaves during deployments. When Coolify or Docker initiates a deployment, it does not instantaneously sever the container's execution. It issues a SIGTERM signal to PID 1\.9 A critical systemic failure occurs when a Dockerfile uses the shell form (e.g., CMD python worker.py). Linux parses this as /bin/sh \-c, meaning the shell becomes PID 1\. The shell explicitly ignores SIGTERM and does not forward it to the Python child process.9 Docker waits for the grace period to expire, assumes the application is hanging, and issues a SIGKILL, which immediately terminates the kernel allocation for the process, severing active database connections and corrupting in-flight tasks.24 Utilizing the JSON array exec form (CMD \["python", "worker.py"\]) guarantees Python receives the signal. The Python script must use the signal module to trap SIGTERM, set an internal shutdown flag, cease polling the database, and cleanly finalize the current task within the overridden stop\_grace\_period.9

## **3\. Anti-Patterns / Banned Patterns**

To maintain a low-ops profile, autonomous agents must actively detect, flag, and refactor specific anti-patterns during code generation or repository review phases. The introduction of these patterns introduces unacceptable technical debt, resource bloat, or race conditions.

| Anti-Pattern | Description | Systemic Consequence |
| :---- | :---- | :---- |
| **External Broker Bloat** | Deploying Celery alongside RabbitMQ or Redis. | Unnecessary RAM consumption on ARM64 VPS, complex failover orchestration, and split-brain dual-write risks. |
| **Naive Database Locks** | Utilizing SELECT FOR UPDATE without the SKIP LOCKED directive. | Extreme lock contention; multi-threaded worker pools degrade into a single-threaded sequential bottleneck. |
| **Volatile In-Memory Tasks** | Utilizing asyncio.create\_task() for state-mutating logic. | Permanent data loss if the FastAPI uvicorn process crashes or undergoes a routine deployment restart. |
| **Non-Deterministic Idempotency** | Generating a random UUID inside the task loop as an idempotency key. | The key changes upon every retry, entirely defeating the idempotency check and causing duplicate billing or actions. |
| **The Zombie Worker** | Using while True: loops without trapping Linux SIGTERM signals. | Database connections are violently severed by Docker's SIGKILL, leaving orphan row locks and corrupted data. |
| **Alpine Linux Compilation** | Using python:alpine base images to save minimal disk space. | The musl libc implementation causes massive compilation times for Python C-extensions and introduces obscure runtime segmentation faults. |

The dependency on external brokers, commonly referred to as Celery/Redis bloat, is strictly prohibited. While Celery is an exceptionally powerful framework with robust routing, rate-limiting, and chord capabilities, it violates the zero-overhead principle required for a solo developer environment.2 Configuring celery-beat for scheduled tasks, celery-worker for execution, and a Redis instance for message brokering consumes highly valuable memory on a constrained ARM64 VPS.27 Furthermore, managing the network topology between these services introduces latency and serialization overhead. In modern Python ecosystems, relying on PostgreSQL's native capabilities through libraries like Procrastinate or PgQueuer provides the same asynchronous capabilities without managing a single piece of external infrastructure.5

Naive database queuing is equally destructive. An untrained autonomous agent might attempt to implement a PostgreSQL queue using standard optimistic locking or basic SELECT FOR UPDATE syntax. This leads to catastrophic lock contention. If fifty workers query the jobs table simultaneously without SKIP LOCKED, they will all attempt to acquire a row-level ExclusiveLock on the exact same row.1 The first worker succeeds, while workers two through fifty are blocked, waiting for the first transaction to commit. This degrades a highly parallelized system into a sequential processing line. The SKIP LOCKED directive ensures that the query optimizer ignores any rows currently holding a lock, allowing all fifty workers to instantly retrieve fifty unique jobs with zero contention.15

The misuse of volatile fire-and-forget logic represents a severe risk to data integrity. FastAPI provides a built-in BackgroundTasks class, which is frequently misused by developers seeking a quick method to offload slow operations without configuring a queue.13 These tasks execute within the same asyncio event loop as the web server, utilizing the system's active memory. If the operation involves critical logic—such as finalizing a payment gateway charge or synchronizing user states—and the application is restarted by Coolify for a routine deployment, the memory is wiped, and the task is permanently destroyed.13 The architecture strictly limits BackgroundTasks to non-critical, sub-second operations, such as emitting localized telemetry or writing to an ephemeral log file. Any logic requiring absolute durability must be written to the PostgreSQL queue via the Outbox Pattern.14

Idempotency requires cryptographic strictness. An anti-pattern often observed in hastily constructed microservices is the generation of a random UUID at the beginning of a worker function, followed by its insertion into an idempotency table.10 If the task crashes halfway through execution and is retried by the queue manager ten minutes later, a completely new UUID is generated. The database check will pass, and the task will execute twice. The architecture dictates that idempotency keys must never rely on runtime randomness; they must be deterministic hashes derived from the immutable properties of the triggering event.8

Finally, the use of Alpine Linux base images is categorically banned \[Context constraint\]. While historically popular for producing small container footprints, Alpine relies on musl libc instead of the standard glibc found in Debian or Ubuntu. Because many Python libraries (such as psycopg, numpy, or various cryptography packages) distribute pre-compiled wheels built against glibc, installing them on Alpine forces pip to compile them from source. This drastically increases Docker build times, consumes unnecessary CPU resources during CI/CD pipelines, and frequently introduces obscure, difficult-to-debug runtime memory faults. The slim-bookworm (Debian 12\) image provides a nearly identical footprint while maintaining perfect compatibility with standard Python wheels.

## **4\. What to Enforce in Execution Handoffs**

When an autonomous agent transfers context, initiates a pull request, or completes a development milestone, the handoff protocol must explicitly validate and document its compliance with the queuing architecture. The following criteria must be actively enforced and articulated in the agent's output protocol.

### **4.1. Database Migration Verification**

Any new task queue, worker, or delayed job mechanism requires a corresponding declarative schema change. The autonomous agent must provide Alembic migration scripts (or raw SQL equivalent definitions) that explicitly detail the queue infrastructure. This must include the creation of the required tables (e.g., jobs, dead\_letters), the exact definition of the status enumeration (pending, processing, completed, failed), and the application of highly optimized indexes. Unindexed queue polling is a critical violation that degrades database performance to full sequential scans; therefore, the agent must prove the inclusion of partial composite B-tree indexes, such as CREATE INDEX idx\_pending\_jobs ON jobs (created\_at) WHERE status \= 'pending'.15

### **4.2. Idempotency Contract Documentation**

For every new background worker added to the system, the execution handoff must document the specific Idempotency Contract governing that task. The agent must clearly state what constitutes the deterministic idempotency key, detailing the concatenation of variables used to generate the hash.8 Furthermore, the handoff must identify the database table where the key is stored (e.g., a dedicated idempotency\_keys table or a processed\_at column on the mutated domain entity). Finally, the agent must define the worker's behavior upon detecting a duplicate key, specifying whether it returns a cached success response, quietly acknowledges the task and exits, or raises a non-fatal warning.10

### **4.3. Resource Budgeting and Temporal Boundaries**

The agent must define the strict temporal boundaries and fault-tolerance limits of the task. The handoff documentation must explicitly state the max\_retries value, representing the absolute limit before the task is subjected to DLQ routing.20 It must detail the retry\_backoff exponential multiplier to prove thundering herd mitigation. Most critically, the agent must declare the visibility\_timeout, which defines the hard lock duration for the SKIP LOCKED retrieval before a peer worker is permitted to assume the job has stalled. The rule dictates that visibility timeouts must be calculated as six times the expected average processing time, with a hard minimum of thirty seconds.32

### **4.4. Docker Lifecycle Configuration**

If the execution handoff involves modifying the deployment topology—such as altering the docker-compose.yml file for Coolify deployments—it must enforce the inclusion of the stop\_grace\_period directive. The agent must mathematically align this grace period with the application's longest possible visibility timeout. For instance, if a specific reporting task requires forty seconds to complete, the stop\_grace\_period must be set to at least forty-five seconds, ensuring the Linux kernel grants the Docker container sufficient time to drain active database connections and finalize the transaction before issuing the terminal SIGKILL.9

## **5\. What to Verify in final\_gate.py**

The final\_gate.py continuous integration script acts as the final automated defense against architectural drift. Relying solely on human code review or LLM prompting is insufficient for a solo developer seeking absolute durability. The script must utilize deep static analysis, regular expressions, and Python Abstract Syntax Tree (ast) parsing to guarantee structural compliance before any code is permitted to merge and deploy.

### **5.1. AST Parsing for Retry Parameters**

Using the ast module, final\_gate.py must traverse the entire application codebase and inspect all functions decorated with the designated task queue decorator (e.g., @task, @procrastinate.task, or @pgqueuer.actor). The AST visitor must recursively evaluate the decorator's structure to verify that it contains explicitly defined keyword arguments dictating retry and backoff semantics.34 If a developer or agent attempts to use a default, argument-free decorator, the static analysis must fail the build.

Python

import ast
import sys

class TaskDecoratorValidator(ast.NodeVisitor):
    def \_\_init\_\_(self):
        self.violations \=

    def visit\_FunctionDef(self, node):
        for decorator in node.decorator\_list:
            \# Check if the decorator is a call (e.g., @task(max\_retries=5))
            if isinstance(decorator, ast.Call):
                func\_name \= getattr(decorator.func, 'id', getattr(decorator.func, 'attr', ''))
                if func\_name in \['task', 'actor', 'job'\]:
                    kwargs \= {kw.arg: kw.value for kw in decorator.keywords if kw.arg}
                    if 'max\_retries' not in kwargs or 'retry\_backoff' not in kwargs:
                        self.violations.append(
                            f"Violation in '{node.name}': Missing explicit retry/backoff kwargs."
                        )
            \# Check if the decorator is just a name (e.g., @task), which is banned
            elif isinstance(decorator, ast.Name) and decorator.id in \['task', 'actor', 'job'\]:
                self.violations.append(
                    f"Violation in '{node.name}': Decorators must be invoked with kwargs."
                )
        self.generic\_visit(node)

\# Execution block for CI pipeline
if \_\_name\_\_ \== "\_\_main\_\_":
    with open("worker.py", "r") as file:
        tree \= ast.parse(file.read())
    validator \= TaskDecoratorValidator()
    validator.visit(tree)
    if validator.violations:
        for violation in validator.violations:
            print(violation)
        sys.exit(1)

This strict AST parsing prevents default configurations that might lead to infinite retry loops or immediate thundering-herd retries, effectively shifting the detection of distributed systems failures leftward into the compilation phase.36

### **5.2. AST Parsing for Ephemeral BackgroundTasks**

The script must statically analyze all FastAPI route definitions. The AST visitor will inspect the arguments of any asynchronous function decorated with @router.post or @app.get. If fastapi.BackgroundTasks is injected into the route signature, the script must flag a severe warning. Because identifying the exact criticality of the background task via static analysis is impossible, the CI pipeline must mandate an explicit inline ignore comment (e.g., \# fabrik: ignore-ephemeral-task) to prove that a human developer has manually verified the task does not mutate critical persistent state.14

### **5.3. Dockerfile Exec Form Validation**

To prevent the catastrophic "Zombie Worker" scenario where POSIX signals are swallowed by shell processes, the final\_gate.py script must evaluate all Dockerfile assets.9 Regular expressions are highly effective for this specific validation.

The regex rule ^CMD\\s+\\\[\\s\*".+"\\s\*(,\\s\*".+"\\s\*)\*\\\]$ must be applied to the final lines of the Dockerfile. If the parser detects standard shell invocations such as CMD python main.py or CMD uvicorn api:app, it must fail the build instantly. The failure output must instruct the agent or developer to format the invocation as a JSON array (e.g., CMD \["uvicorn", "api:app", "--host", "0.0.0.0"\]) or to utilize ENTRYPOINT \["/usr/bin/tini", "--"\] as the primary initialization subreaper.

### **5.4. Signal Handler Verification**

The static analyzer must ensure that the worker's primary entrypoint file contains the necessary logic to orchestrate graceful shutdowns.23 The AST tree must be parsed to confirm the existence of import signal, followed by an explicit mapping for signal.signal(signal.SIGTERM, \<handler\_function\>). A background worker lacking this mapping is mathematically guaranteed to corrupt database state during routine deployment cycles, as it cannot pause its queue consumption prior to the container's destruction.

### **5.5. Banned Module Imports**

A strict AST check for prohibited architectural imports must run against all Python files. The validator will scan the Import and ImportFrom nodes. The banned list includes celery, redis, rq, pika, and kombu. If any of these modules are detected within the codebase, the CI pipeline fails immediately, enforcing the zero-broker, PostgreSQL-exclusive architectural mandate.

## **6\. What Belongs in AGENTS.md / AGENTS-compact.md**

To effectively condition Large Language Models executing autonomous tasks within the Fabrik repository, the AGENTS.md file (and its highly compressed counterpart, AGENTS-compact.md) must contain explicit, rigidly structured directives regarding the queuing architecture. LLMs are trained on vast amounts of historical data, which overwhelmingly biases them toward suggesting Celery and Redis for any background task prompt. The agent documentation must aggressively overwrite this bias.

### **6.1. Content for AGENTS.md**

**Background Processing & Queues**

1. **No Redis or Celery:** The Fabrik architecture uses PostgreSQL 16 as its exclusive message broker. All queues must be implemented using SELECT... FOR UPDATE SKIP LOCKED. You may use libraries like Procrastinate or PgQueuer, or a custom minimal implementation matching this exact SQL standard. Do not suggest or import Redis.
2. **Transactional Outbox:** Always enqueue jobs in the exact same database transaction that modifies the relevant application state. If the primary transaction rolls back, the job must not exist.
3. **Idempotency is Mandatory:** Never assume a task will run only once. Derive an idempotency key deterministically from the business logic (e.g., hash of user ID \+ action). Check for this key in the database and skip execution if it is already processed. Do not use randomly generated UUIDs as idempotency keys.
4. **Graceful Shutdown:** Docker deployments send SIGTERM. Your Python worker must use the signal module to trap SIGTERM, stop accepting new jobs, finish current tasks within the 30-second stop\_grace\_period, and exit cleanly. Dockerfiles must use CMD \["python", "worker.py"\] (exec form).
5. **Retries & Dead Letters:** Hardcode max\_retries with exponential backoff on all task decorators. Failed tasks must automatically route to a Dead-Letter Queue (DLQ) table after exhausting retries.

### **6.2. Content for AGENTS-compact.md**

\`\` PG16 exclusively. No Redis/Celery/RabbitMQ. Use FOR UPDATE SKIP LOCKED. Enqueue via Transactional Outbox (same ACID transaction). Enforce strict idempotency using deterministic hashes. Trap SIGTERM for graceful Docker shutdown (exec CMD form only). Enforce max retries, exp backoff, and DLQ routing for all workers.

## **7\. What Belongs Left as Human Guidance Only**

While automated static analysis and rigid LLM conditioning handle the structural enforcement of the architecture, certain operational realities require nuanced human judgment. The following aspects of the queuing architecture cannot be safely automated or perfectly prescribed via standard rules; they belong purely in the domain of the solo developer's operational playbook.

First, tuning the PostgreSQL Autovacuum daemon for queue tables is highly subjective. Because a queue table experiences constant INSERT, UPDATE (to processing state), and DELETE (or status updates to completed) operations, it generates massive amounts of dead tuples due to PostgreSQL's Multi-Version Concurrency Control (MVCC).28 An LLM cannot accurately predict the transaction velocity of the application. The human developer must manually monitor pg\_stat\_user\_tables to observe the dead tuple bloat on the jobs table and selectively lower the autovacuum\_vacuum\_scale\_factor to ensure the table is swept aggressively, preventing performance degradation.

Second, the manual resolution of the Dead-Letter Queue (DLQ) is an inherently human task. When a poison-pill message exhausts its retries and lands in the DLQ, it represents a fundamental flaw in the business logic or an unpredictable external API mutation.20 An automated agent cannot safely "fix" a DLQ message, as it lacks the holistic business context to determine whether a payment should be forcefully pushed through, refunded, or abandoned. The developer must manually inspect the DLQ payload, patch the underlying Python code, and utilize an administrative SQL query to transition the job back to a pending state.

Finally, managing catastrophic Virtual Private Server (VPS) failures requires human intervention. If the underlying ARM64 hardware experiences a hypervisor crash, all active jobs stuck in the processing state will remain there indefinitely until their visibility timeouts expire. While the timeout mechanism (CR-06) automatically re-queues them, the human developer must investigate the root cause of the hardware fault. Automated systems should not attempt to automatically scale or migrate databases without human oversight in a solo-developer context, as this directly conflicts with the budget-conscious, low-ops mandate.

## **8\. Minimal Practical Examples for Fabrik Stack**

The following implementations translate the theoretical constraints into production-ready Python and SQL logic, tailored specifically for the Fabrik technology stack, encompassing WSL, Coolify deployments, ARM64 compatibility, FastAPI routers, and PostgreSQL 16\.

### **8.1. Database Schema: The Job and Idempotency Tables**

The foundation of the architecture is the schema. It relies on a custom ENUM for status tracking and, crucially, a partial index that ensures the SKIP LOCKED query only scans rows that actually require processing, keeping the index tree microscopic regardless of how many millions of completed jobs exist in the table.15

SQL

\-- Schema enforcement for queue and idempotency
CREATE TYPE job\_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    task\_name VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    status job\_status DEFAULT 'pending' NOT NULL,
    attempts INT DEFAULT 0 NOT NULL,
    max\_retries INT DEFAULT 5 NOT NULL,
    run\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

\-- Critical: Partial index to optimize SKIP LOCKED retrieval
\-- Without this, the database performs a sequential scan on millions of rows.
CREATE INDEX idx\_jobs\_pending ON jobs(run\_at) WHERE status \= 'pending';

\-- Idempotency tracking table
CREATE TABLE idempotency\_keys (
    idempotency\_key VARCHAR(255) PRIMARY KEY,
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

### **8.2. Enqueueing with Transactional Outbox (FastAPI)**

This example demonstrates the Transactional Outbox pattern.16 The job to send a welcome email is inserted during the exact same SQLAlchemy asynchronous session that creates the user. If the database commit() fails due to a unique constraint on the email address, the job insertion is automatically rolled back, guaranteeing absolute consistency.4

Python

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get\_db
import hashlib
import json

router \= APIRouter()

@router.post("/users/")
async def create\_user(user\_data: dict, db: AsyncSession \= Depends(get\_db)):
    try:
        \# 1\. Mutate primary application state
        new\_user \= await insert\_user\_record(db, user\_data)

        \# 2\. Derive deterministic idempotency key for the downstream task
        payload \= {"user\_id": new\_user.id, "email": new\_user.email}
        payload\_str \= json.dumps(payload, sort\_keys=True).encode('utf-8')
        idem\_key \= hashlib.sha256(b"welcome\_email\_" \+ payload\_str).hexdigest()

        \# 3\. Enqueue background task in the SAME transaction
        await db.execute(
            """
            INSERT INTO jobs (task\_name, payload, run\_at)
            VALUES ('send\_welcome\_email', :payload, NOW())
            """,
            {"payload": json.dumps({"data": payload, "idem\_key": idem\_key})}
        )

        \# Commit seals both the user creation and the job enqueue
        await db.commit()
        return {"status": "success", "user\_id": new\_user.id}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status\_code=400, detail="Transaction failed.")

### **8.3. The SKIP LOCKED Worker with Graceful Shutdown**

This implementation showcases the core queuing loop. It utilizes the signal module to trap Docker's termination signals, ensuring that any in-flight database transactions are completed before the process exits.9 It applies the SKIP LOCKED query for contention-free fetching 29 and implements exponential backoff for error handling.20

Python

import asyncio
import signal
import sys
import logging
from sqlalchemy.ext.asyncio import create\_async\_engine

logger \= logging.getLogger(\_\_name\_\_)

class WorkerConfig:
    def \_\_init\_\_(self):
        self.is\_shutting\_down \= False

config \= WorkerConfig()

def handle\_sigterm(\*args):
    """Trap Docker's SIGTERM and initiate a graceful drain sequence."""
    logger.info("SIGTERM received. Draining worker tasks...")
    config.is\_shutting\_down \= True

\# Register the POSIX signals
signal.signal(signal.SIGTERM, handle\_sigterm)
signal.signal(signal.SIGINT, handle\_sigterm)

async def process\_queue(engine):
    while not config.is\_shutting\_down:
        async with engine.begin() as conn:
            \# Atomically lock and fetch exactly ONE job without blocking peers
            result \= await conn.execute("""
                UPDATE jobs
                SET status \= 'processing', attempts \= attempts \+ 1
                WHERE id \= (
                    SELECT id FROM jobs
                    WHERE status \= 'pending' AND run\_at \<= NOW()
                    ORDER BY run\_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, task\_name, payload, max\_retries, attempts;
            """)
            job \= result.fetchone()

        if not job:
            \# Prevent CPU thrashing when the queue is empty
            await asyncio.sleep(1)
            continue

        try:
            \# Extract idempotency key and attempt processing
            idem\_key \= job.payload.get("idem\_key")

            async with engine.begin() as conn:
                \# Enforce Idempotency Contract
                try:
                    await conn.execute(
                        "INSERT INTO idempotency\_keys (idempotency\_key) VALUES (:key)",
                        {"key": idem\_key}
                    )
                except Exception:
                    logger.info(f"Duplicate job {job.id} detected. Skipping.")
                else:
                    \# Execute primary business logic
                    await execute\_task(job.task\_name, job.payload)

                \# Mark completed within the same session
                await conn.execute(
                    "UPDATE jobs SET status \= 'completed' WHERE id \= :id",
                    {"id": job.id}
                )

        except Exception as e:
            logger.error(f"Job {job.id} failed: {str(e)}")
            \# Handle Retries and DLQ Routing via Exponential Backoff
            async with engine.begin() as conn:
                await conn.execute("""
                    UPDATE jobs
                    SET status \= CASE
                            WHEN attempts \>= max\_retries THEN 'failed'::job\_status
                            ELSE 'pending'::job\_status
                        END,
                        run\_at \= NOW() \+ (POWER(2, attempts) \* INTERVAL '1 second')
                    WHERE id \= :id
                """, {"id": job.id})

    logger.info("Worker drained and gracefully terminated.")
    sys.exit(0)

### **8.4. Docker Compose and Dockerfile Alignment**

To ensure the Python signals are accurately routed by the underlying operating system, the Docker container must be meticulously structured.9

| Component | Configuration | Rationale |
| :---- | :---- | :---- |
| **Dockerfile Base** | python:3.12-slim-bookworm | Avoids Alpine musl libc compilation issues. |
| **PID 1 Manager** | tini | Acts as a subreaper to handle zombie child processes and perfectly proxy SIGTERM to the worker. |
| **Entrypoint Form** | ENTRYPOINT \["/usr/bin/tini", "--"\] | JSON Exec form; prevents shell wrapping. |
| **Command Form** | CMD \["python", "worker.py"\] | JSON Exec form; maintains exact signal parity. |
| **Compose Grace** | stop\_grace\_period: 45s | Overrides the Docker default of 10s, ensuring long database transactions have time to commit before SIGKILL. |

## **9\. Recommended Final Content for 75-workers-jobs.md**

The following section represents the precise markdown structure to be preserved as 75-workers-jobs.md within the autonomous agent's central rule repository. It acts as the immutable standard for all background processing logic in the Fabrik codebase.

# **Rule 75: Background Workers and Job Queues**

**Context:** Fabrik operates as a solo-developer platform prioritizing extreme operational durability, minimal infrastructure bloat, and long-term stability on an ARM64 Ubuntu VPS via Coolify.

## **1\. Core Architecture**

* **PostgreSQL is the Message Broker:** The system strictly forbids the use of Redis, RabbitMQ, or Celery. All queuing must be executed natively within PostgreSQL 16 utilizing the SELECT... FOR UPDATE SKIP LOCKED paradigm.
* **Transactional Enqueueing:** Background tasks must be inserted into the queue table within the exact same database transaction that updates the primary entity. This Outbox Pattern ensures consistency without dual-write edge cases.
* **FastAPI BackgroundTasks:** Restricted exclusively to ephemeral, non-critical telemetry or transient I/O operations. Any task requiring guaranteed execution must be routed to the PostgreSQL queue.

## **2\. Idempotency & Delivery Guarantees**

* **At-Least-Once Delivery:** The system assumes tasks will randomly fail and restart due to network partitions or deployments. Exactly-once execution is a myth.
* **Strict Idempotency:** Every task must be inherently idempotent. Derivation of an Idempotency Key (e.g., hash of user\_id \+ action \+ timestamp) is mandatory. Check for this key's existence and mutate the state in a single transaction. Do not use runtime UUIDs.

## **3\. Retries, Timeouts, and Dead Letters**

* **Exponential Backoff:** Retries must implement exponential backoff with randomized jitter (e.g., run\_at \= NOW() \+ 2^attempts).
* **Dead-Letter Queue (DLQ):** Tasks exceeding max\_retries (default: 5\) must be atomically transitioned to a failed state or moved to a dedicated DLQ table. Poison pills must never loop infinitely.
* **Visibility Timeouts:** Long-running tasks must define a visibility timeout calculated as 6x the average processing time. If a task exceeds this without a heartbeat, peer workers must assume the process died and reclaim the job.

## **4\. Lifecycle and Graceful Shutdown**

* **SIGTERM Trapping:** Coolify/Docker initiates termination via SIGTERM. Python workers must catch signal.SIGTERM, halt queue polling, complete the in-flight job, and exit successfully before Docker sends a terminal SIGKILL.
* **Docker stop\_grace\_period:** Align the Docker Compose termination grace period (e.g., 45s) with the worker's maximum allowed task execution time.
* **Exec Form Entrypoints:** Dockerfiles must invoke processes using the JSON exec form (e.g., CMD \["python", "worker.py"\]) and utilize tini as PID 1 to ensure POSIX signals are transmitted correctly. Never use the shell form.

## **5\. Automated Enforcements (final\_gate.py)**

* Python AST traversal will automatically verify that all queue decorators explicitly declare max\_retries and backoff keyword arguments.
* Regex validation will block any Pull Requests containing import celery or import redis.
* Missing composite B-Tree indexes on (status, run\_at) for queue tables will trigger immediate database migration CI failures.

#### **Works cited**

1. Postgres is the only Queue you need (until 50k jobs/sec) | by Harsh Vaghela \- Medium, accessed March 31, 2026, [https://medium.com/@harsh.vaghela.work/postgres-is-the-only-queue-you-need-until-50k-jobs-sec-5931611b551c](https://medium.com/@harsh.vaghela.work/postgres-is-the-only-queue-you-need-until-50k-jobs-sec-5931611b551c)
2. Don't Split My Data: I Will Use a Database (Not PostgreSQL) for My Data Needs \- EloqData, accessed March 31, 2026, [http://www.eloqdata.com/blog/2025/11/07/use-real-database-for-data-needs](http://www.eloqdata.com/blog/2025/11/07/use-real-database-for-data-needs)
3. Been using Postgres my entire career \- what am I missing out on? : r/ExperiencedDevs, accessed March 31, 2026, [https://www.reddit.com/r/ExperiencedDevs/comments/1jgix2f/been\_using\_postgres\_my\_entire\_career\_what\_am\_i/](https://www.reddit.com/r/ExperiencedDevs/comments/1jgix2f/been_using_postgres_my_entire_career_what_am_i/)
4. Show HN: Pq – Simple, durable background tasks in Python using Postgres \- Hacker News, accessed March 31, 2026, [https://news.ycombinator.com/item?id=47110669](https://news.ycombinator.com/item?id=47110669)
5. PgQueuer – PostgreSQL-native job & schedule queue, gathering ideas for 1.0 \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1kd6ci0/pgqueuer\_postgresqlnative\_job\_schedule\_queue/](https://www.reddit.com/r/Python/comments/1kd6ci0/pgqueuer_postgresqlnative_job_schedule_queue/)
6. PgQueuer is a Python library leveraging PostgreSQL for efficient job queuing. \- GitHub, accessed March 31, 2026, [https://github.com/janbjorge/pgqueuer](https://github.com/janbjorge/pgqueuer)
7. I Replaced Redis with PostgreSQL (And It's Faster) \- DEV Community, accessed March 31, 2026, [https://dev.to/polliog/i-replaced-redis-with-postgresql-and-its-faster-4942](https://dev.to/polliog/i-replaced-redis-with-postgresql-and-its-faster-4942)
8. How to Handle Idempotency in Microservices \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-24-idempotency-in-microservices/view](https://oneuptime.com/blog/post/2026-01-24-idempotency-in-microservices/view)
9. How to Handle Docker Container Graceful Shutdown and Signal Handling \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-16-docker-graceful-shutdown-signals/view](https://oneuptime.com/blog/post/2026-01-16-docker-graceful-shutdown-signals/view)
10. Reliable Python Queues: 7 Celery/Dramatiq/RQ Choices | by Nexumo \- Medium, accessed March 31, 2026, [https://medium.com/@Nexumo\_/reliable-python-queues-7-celery-dramatiq-rq-choices-266ac544a4a5](https://medium.com/@Nexumo_/reliable-python-queues-7-celery-dramatiq-rq-choices-266ac544a4a5)
11. Load Tests Python Task Queues \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1digyfg/load\_tests\_python\_task\_queues/](https://www.reddit.com/r/Python/comments/1digyfg/load_tests_python_task_queues/)
12. procrastinate/docs/howto/production/retry\_stalled\_jobs.md at main \- GitHub, accessed March 31, 2026, [https://github.com/procrastinate-org/procrastinate/blob/main/docs/howto/production/retry\_stalled\_jobs.md?plain=true](https://github.com/procrastinate-org/procrastinate/blob/main/docs/howto/production/retry_stalled_jobs.md?plain=true)
13. Managing Background Tasks in FastAPI: BackgroundTasks vs ARQ \+ Redis \- David Muraya, accessed March 31, 2026, [https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/)
14. How to Build Background Task Processing in FastAPI \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-25-background-task-processing-fastapi/view](https://oneuptime.com/blog/post/2026-01-25-background-task-processing-fastapi/view)
15. Use SKIP LOCKED for Non-Blocking Queue Processing \- Postgres Best Practice, accessed March 31, 2026, [https://supaexplorer.com/best-practices/supabase-postgres/lock-skip-locked/](https://supaexplorer.com/best-practices/supabase-postgres/lock-skip-locked/)
16. The Transactional Outbox Pattern: Transforming Real-Time Data Distribution at SeatGeek, accessed March 31, 2026, [https://chairnerd.seatgeek.com/transactional-outbox-pattern/](https://chairnerd.seatgeek.com/transactional-outbox-pattern/)
17. PostgreSQL \+ Outbox Pattern Revamped — Part 1 \- DEV Community, accessed March 31, 2026, [https://dev.to/msdousti/postgresql-outbox-pattern-revamped-part-1-3lai](https://dev.to/msdousti/postgresql-outbox-pattern-revamped-part-1-3lai)
18. Implementing Idempotency Keys in REST APIs \- Zuplo, accessed March 31, 2026, [https://zuplo.com/learning-center/implementing-idempotency-keys-in-rest-apis-a-complete-guide](https://zuplo.com/learning-center/implementing-idempotency-keys-in-rest-apis-a-complete-guide)
19. Implementing Stripe-like Idempotency Keys in Postgres \- Brandur, accessed March 31, 2026, [https://brandur.org/idempotency-keys](https://brandur.org/idempotency-keys)
20. Retry policies and dead-letter queues \- \- Alibaba Cloud Documentation Center, accessed March 31, 2026, [https://www.alibabacloud.com/help/en/eventbridge/retry-policies-and-dead-letter-queues](https://www.alibabacloud.com/help/en/eventbridge/retry-policies-and-dead-letter-queues)
21. Using dead-letter queues in Amazon SQS \- AWS Documentation, accessed March 31, 2026, [https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
22. How to Build a Graceful Shutdown Handler in Python \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2025-01-06-python-graceful-shutdown-kubernetes/view](https://oneuptime.com/blog/post/2025-01-06-python-graceful-shutdown-kubernetes/view)
23. Building Robust Graceful Shutdown in Python: Beyond with open() | by Har Avetisyan, accessed March 31, 2026, [https://medium.com/@har.avetisyan2002/building-robust-graceful-shutdown-in-python-beyond-with-open-25ac490b1b9b](https://medium.com/@har.avetisyan2002/building-robust-graceful-shutdown-in-python-beyond-with-open-25ac490b1b9b)
24. Gracefully Stopping Python Processes Inside a Docker Container | by Khaerul Umam, accessed March 31, 2026, [https://medium.com/@khaerulumam42/gracefully-stopping-python-processes-inside-a-docker-container-0692bb5f860f](https://medium.com/@khaerulumam42/gracefully-stopping-python-processes-inside-a-docker-container-0692bb5f860f)
25. Go Best Practices: 5 Essential Context Patterns for Graceful Service Shutdown | by Nithin Bharadwaj | TechKoala Insights, accessed March 31, 2026, [https://techkoalainsights.com/go-best-practices-5-essential-context-patterns-for-graceful-service-shutdown-3f3ebc447165](https://techkoalainsights.com/go-best-practices-5-essential-context-patterns-for-graceful-service-shutdown-3f3ebc447165)
26. How to Use Graceful Shutdown Handlers for Long-Running Kubernetes Processes, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-09-graceful-shutdown-handlers/view](https://oneuptime.com/blog/post/2026-02-09-graceful-shutdown-handlers/view)
27. Ultimate guide to Celery library in Python \- Deepnote, accessed March 31, 2026, [https://deepnote.com/blog/ultimate-guide-to-celery-library-in-python](https://deepnote.com/blog/ultimate-guide-to-celery-library-in-python)
28. Documentation: 18: 13.3. Explicit Locking \- PostgreSQL, accessed March 31, 2026, [https://www.postgresql.org/docs/current/explicit-locking.html](https://www.postgresql.org/docs/current/explicit-locking.html)
29. The Unreasonable Effectiveness of SKIP LOCKED in PostgreSQL \- Inferable, accessed March 31, 2026, [https://www.inferable.ai/blog/posts/postgres-skip-locked](https://www.inferable.ai/blog/posts/postgres-skip-locked)
30. Implementing a Postgres job queue in less than an hour \- AmineDiro, accessed March 31, 2026, [https://aminediro.com/posts/pg\_job\_queue/](https://aminediro.com/posts/pg_job_queue/)
31. Using FOR UPDATE SKIP LOCKED for Queue-Based Workflows without Deadlocks, accessed March 31, 2026, [https://www.netdata.cloud/academy/update-skip-locked/](https://www.netdata.cloud/academy/update-skip-locked/)
32. Amazon SQS visibility timeout \- Amazon Simple Queue Service \- AWS Documentation, accessed March 31, 2026, [https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)
33. How to Handle SQS Message Visibility Timeout \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-27-sqs-message-visibility-timeout/view](https://oneuptime.com/blog/post/2026-01-27-sqs-message-visibility-timeout/view)
34. Define a retry strategy on a task \- Procrastinate documentation, accessed March 31, 2026, [https://procrastinate.readthedocs.io/en/stable/howto/advanced/retry.html](https://procrastinate.readthedocs.io/en/stable/howto/advanced/retry.html)
35. ast — Abstract syntax trees — Python 3.14.3 documentation, accessed March 31, 2026, [https://docs.python.org/3/library/ast.html](https://docs.python.org/3/library/ast.html)
36. Machine-Learning/Exploring Python's Abstract Syntax Tree Manipulation.md at main, accessed March 31, 2026, [https://github.com/xbeat/Machine-Learning/blob/main/Exploring%20Python's%20Abstract%20Syntax%20Tree%20Manipulation.md](https://github.com/xbeat/Machine-Learning/blob/main/Exploring%20Python's%20Abstract%20Syntax%20Tree%20Manipulation.md)
37. Python | Semgrep, accessed March 31, 2026, [https://semgrep.dev/docs/languages/python](https://semgrep.dev/docs/languages/python)
38. Write rules \- Semgrep, accessed March 31, 2026, [https://semgrep.dev/docs/writing-rules/overview](https://semgrep.dev/docs/writing-rules/overview)
39. Graceful shutdown of forked workers in Python and JavaScript running in Docker containers, accessed March 31, 2026, [https://javaoraclesoa.blogspot.com/2019/06/how-to-achieve-graceful-shutdown-of.html](https://javaoraclesoa.blogspot.com/2019/06/how-to-achieve-graceful-shutdown-of.html)
40. Graceful shutdown of forked workers in Python and JavaScript running in Docker containers, accessed March 31, 2026, [https://technology.amis.nl/platform/docker/graceful-shutdown-of-forked-workers-in-python-and-javascript-running-in-docker-containers/](https://technology.amis.nl/platform/docker/graceful-shutdown-of-forked-workers-in-python-and-javascript-running-in-docker-containers/)
41. Turning PostgreSQL into a Robust Queue for Go Applications \- DEV Community, accessed March 31, 2026, [https://dev.to/shrsv/turning-postgresql-into-a-robust-queue-for-go-applications-1hob](https://dev.to/shrsv/turning-postgresql-into-a-robust-queue-for-go-applications-1hob)
42. Best Practices to Avoid Locks in PostgreSQL, accessed March 31, 2026, [https://wearecommunity.io/communities/javaro/articles/5144](https://wearecommunity.io/communities/javaro/articles/5144)
43. Postgres Pro Enterprise : Documentation: 18: F.55. pgpro\_queue — message queueing management, accessed March 31, 2026, [https://postgrespro.com/docs/enterprise/current/pgpro-queue](https://postgrespro.com/docs/enterprise/current/pgpro-queue)
44. Using an SQL database as a job queue \- Mathieu GAILLARD, accessed March 31, 2026, [http://www.mgaillard.fr/2024/12/01/job-queue-postgresql.html](http://www.mgaillard.fr/2024/12/01/job-queue-postgresql.html)
45. How-To: Enable the transactional outbox pattern | Dapr Docs, accessed March 31, 2026, [https://docs.dapr.io/developing-applications/building-blocks/state-management/howto-outbox/](https://docs.dapr.io/developing-applications/building-blocks/state-management/howto-outbox/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMEAAAAYCAYAAABDc5l7AAAFJklEQVR4Xu2aTagcRRCAaxEhgmKiCP4hL4ooag4qIRA0B8FA8BDBn0NEPQsePHiQILkKXiQESSAEghgCmkMEwUNADARJbhFBFNSD/wcVVAQhgvb3uutNTW3P7szO293Z3fmgeG+qZmZnqrp6qnpGZIEYeMUq0zujp2eRWbEMbnO7bY7t6elR+kzqDn0s5kjv/BaslvOOBjleKYPS9stBnk1y7/rRHWa1wtiG1fbUnUH+S3IlyDdJvjX6X43+Z6M/IsNcLYV9aen4kLkmyJ9SxAG5XNqj68zYwWfC7/3ilYG7pHAgA9vCJaLfu7FV8ESy/VvS9syKhyT6/y2je1RiPA4Y3eYy40G72eCwG70y8IZE21/ekPgtyE1embjZKxabhYnwdRJjdtHpdTJ7x+l7JJZCn3tl4juJjjvlDYm5lTsLMyRnD7EkLrc7/bGkX3P6ISby7UQHdYeTQfZ4ZUJnj13ekPjHK3rmCn2AxmwzyCVTDhLshFcuA7YfqJvn2yXWnRxzv7PBixJtv0vRY9yattFz7MNJD68kPfJlkKuMLcfOIN9LccxzZfPS87zE+6ZMhf1BvpL4JCdBmnKtjH96sFr4hVd2i7rDdxhWfaxDx/GAFM31eRmeje6QGBDA9ofEGYTaVa/yk2Sjn/hbikEc7AP06HIQLBII+/VJxzl5UsXGfSxlR03utrnyoUT/sarHwNR7P5j0r6btJmyV6kQYmQAL6sMSP0m8+ZNOXwUDUGd3PXZLYZZPg9yX/teZGidamLnUtlY2yddJb88JGqRcgnwc5DWvnAPnpLivSUT9Ng71EfKCs70X9QMmq6bkEmFkAsyKaSeaOpMSY4OKH6Vu/Cz9H1cnBkNLrpwLdPUiM2gHuhp12Fskzup6DgvnQb/b6TVwuVWvllR4QUZZZoJNAg99H3ofl7rYROhEAkzb2cw86symP6UDuWo9+kmJ9txLNl2N8suuzP7o/VItCarXydtrgnNWYmmEbC92dVTfFRZeGNadfadG9SVWcl6iL+ixPNZX/p1PXTQRtKxdapr2AxadsatiSImC/UFvkCJIHhIqlzisSKBnBrxHYpPNk6YNPDlIoEkHyjzhHUBV3GwSTOqj9yUmAOeY+yQxbZr2A4p+fnHJGwy6euTR1SgtqyxVTwhNKJ4+XYZBR4JOKlUTiudpmV4SkABaAulnMXcX5uVDnVXqB2rwkcTjdqTtM1JendF+IBckLaNecnpd+7alkH6OoTMfDXVd/IDyjfY2t20h+GMGkD/9Oo+L/yCxmdR9Kqmv1D8WmwRNsQmgtEuErJtq0ubYmrTpB7yTvcMn6QdICvQ62+8Lcjr9vzvZXk/bnoMSlw3hmSBPBflB4jlAG0mg3v0gyJsSk9mCHyjz6DFuk/guoqvoR48+durHpi+1SICqD+80EdacfiHRx+5jEr8S1cHMDKu2OnAMAwvelTjwLOck7pOrJ10CbcRQg8dMhtOZ5WyAWe3wOvbjOmxZxhItsC/JCFr/gwaaBKDMspC0utTK38zKVmfQ5hVfK/iG+2x63TyFRpW2sBSJcIMUA3CU1EFrUuSQswEzaO5Rras/rGXn+FGi/Yrk33xekPK1Mtv7pVF+Q3sWiwYZPwD2HW4apaxDz/U/UjZNAT+HlxhpVG6RDV+sv2REeOPelLov10gE+6a/p8MwmG3jTel1wGxTJuWSlJHHINIBZY9ZPWrlYQVtju2RzXAgDbltvOkt7Fmpp99OOnoD4NMOWxNTLuV6mp4F5X8Qtn4vOeq5XwAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,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>
