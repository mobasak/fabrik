# **Fabrik Technical Architecture: Persistent State and Retrieval Systems**

## **Executive Summary**

The architectural mandates for the Fabrik platform are dictated by the absolute constraints of a solo-developer environment operating within a strict 50-hour weekly time budget. In this paradigm, infrastructural minimalism is not merely a preference; it is a critical survival mechanism. Every additional stateful service introduced into the deployment topology—such as Redis, RabbitMQ, Elasticsearch, or standalone vector databases like Pinecone or Weaviate—imposes compounding operational taxes in the form of security patching, memory monitoring, network configuration, and cross-service state synchronization.1 To maximize product velocity, ensure long-term durability, and maintain strict budget constraints, the architecture must centralize state management, background processing, and high-dimensional semantic search entirely within PostgreSQL 16\.

The deployment environment comprises a WSL Ubuntu 24.04 local development setup and an ARM64 Ubuntu Virtual Private Server (VPS) managed via Coolify using Docker Compose. The software stack strictly utilizes Python with FastAPI and Uvicorn for backend services, Next.js 14 with TypeScript and Tailwind for frontend interfaces, and React Native for mobile clients. Within this specific ecosystem, the introduction of external message brokers for asynchronous task execution represents an unacceptable anti-pattern. The analysis indicates that modern PostgreSQL capabilities are vastly underutilized in standard web frameworks. For background worker and job orchestration, the introduction of the FOR UPDATE SKIP LOCKED primitive fundamentally alters the viability of relational databases as high-throughput message brokers.1 By completely bypassing the row-level lock wait queues, PostgreSQL can safely dispatch jobs to highly concurrent, fork-isolated Python worker processes without introducing deadlocks or race conditions.4 This entirely eliminates the necessity for external queuing infrastructure for workloads processing fewer than 50,000 jobs per second.1

Similarly, the evolution of Retrieval-Augmented Generation (RAG) architectures has popularized decoupled vector stores. However, the data demonstrates that pgvector running within PostgreSQL provides state-of-the-art Hierarchical Navigable Small World (HNSW) index performance capable of scaling flawlessly beyond 50 million vectors, directly challenging the necessity of purpose-built vector databases.6 Furthermore, pure semantic search is critically deficient when handling exact-match entity queries, acronyms, or specific alphanumeric identifiers like SKUs.8 A production-grade RAG implementation requires a Hybrid Search architecture, natively combining pgvector dense similarities with PostgreSQL's native tsvector (BM25) sparse lexical scoring. Fusing these disparate scoring paradigms via Reciprocal Rank Fusion (RRF) delivers the highest precision and recall metrics without requiring a secondary search cluster.9

The following comprehensive specification codifies the rules, anti-patterns, enforcement mechanisms, and automated gating checks required to build the Fabrik infrastructure. It separates deterministic machine-enforceable rules from human architectural guidance. It is designed to remain highly durable, maintenance-light, and technologically relevant through the 2025–2027 lifecycle, ensuring the solo developer can focus on business logic rather than infrastructure orchestration.

## **Canonical Rules for the Fabrik Rule File**

The following directives form the immutable core of the Fabrik implementation standard for both job orchestration and information retrieval. These rules govern agent behavior and system architecture.

* **The PostgreSQL Singularity:** PostgreSQL 16 is the sole authorized message broker, task queue, and state store. External brokers like Redis, RabbitMQ, and Celery are strictly prohibited to prevent infrastructural sprawl.1
* **Atomic Dequeuing:** All worker instances must acquire jobs exclusively utilizing the SELECT... FOR UPDATE SKIP LOCKED SQL primitive.1
* **Fork-Isolated Execution:** Task handlers must be executed in forked child processes, monitored by the parent worker via mechanisms like os.wait4(). This prevents memory leaks or out-of-memory (OOM) errors from crashing the master daemon.4
* **Idempotent Processing via Upsert:** Job ingestion must utilize INSERT... ON CONFLICT DO UPDATE (upsert) logic with a unique client\_id to debounce duplicate triggers and ensure graceful handling of at-least-once delivery semantics.4
* **In-Place Dead-Letter Handling:** No separate dead-letter queue (DLQ) tables are permitted. Failed jobs must increment a retry\_count column and transition to a terminal failed status within the primary table upon exceeding limits.2
* **Exponential Backoff Protocol:** Retry logic must utilize standard exponential backoff with a factor of 2, starting with a 5-second initial delay, capped at a defined maximum duration to prevent perpetual failing loops.13
* **Partial Indexing for Queue Health:** The jobs table must strictly enforce a partial index on the status column (WHERE status \= 'pending') to preserve primary OLTP application performance.15
* **Container Base Images:** All Python and Node.js Dockerfiles must utilize slim-bookworm base images. Alpine Linux is strictly banned due to musl-libc compatibility issues with Python C-extensions and numerical libraries.
* **Native Hybrid Search:** Pure vector similarity search is prohibited for user-facing queries. Systems must combine pgvector (dense) and native tsvector (sparse/BM25) methodologies.8
* **Reciprocal Rank Fusion (RRF):** Dense and sparse lexical scores must be merged exclusively using the RRF algorithm (![][image1]), where ![][image2] defaults to 60\.9
* **HNSW Index Parameterization:** All pgvector deployments must utilize HNSW indexes with m=16 and ef\_construction=64 to balance memory consumption and recall accuracy.9
* **Pragmatic Recursive Chunking:** Semantic chunking algorithms are banned. Text ingestion must utilize Recursive Character Splitting with a defined overlap buffer to preserve contextual boundaries.22
* **The 85% Token Budget:** Context retrieval must be capped at 85% of the LLM's published limit, reserving 15% for system prompts, internal generation, and API safety margins.25
* **Pre-Flight Byte Pair Encoding (BPE):** Python implementations must use the tiktoken library to programmatically count tokens before dispatching requests to external APIs; heuristic character-division is banned.26
* **Citation Provenance tracking:** Document metadata must be preserved directly within the vector payload, and the LLM must be explicitly prompted to cite these internal IDs.29

## **Anti-Patterns and Banned Patterns**

The implementation of persistent state and retrieval logic in solo-developer architectures is highly vulnerable to over-engineering. The following patterns introduce unacceptable levels of maintenance debt and are explicitly banned within the Fabrik platform.

### **Job Orchestration Anti-Patterns**

The most pervasive anti-pattern in modern Python web development is the automatic defaulting to Celery and Redis for asynchronous task processing.10 While highly capable, this topology requires managing a separate Redis instance, configuring Celery beat schedules, monitoring Redis memory eviction policies, and handling serialization edge-cases.2 For a solo developer, this creates a secondary failure domain. Furthermore, it breaks transactional guarantees. If the primary PostgreSQL transaction that creates a user rolls back, but the Redis task to send a welcome email has already been enqueued, the system enters an inconsistent state. By storing jobs in PostgreSQL, the INSERT into the queue table occurs within the same ACID transaction as the business logic, guaranteeing absolute consistency.4

Another severe anti-pattern is utilizing a database queue without the SKIP LOCKED directive. Standard row locking (SELECT FOR UPDATE) causes concurrent workers to queue and block each other, degrading a 50-worker cluster into a single-threaded bottleneck and causing high connection pool exhaustion.1 Similarly, utilizing aggressive polling (e.g., while True: sleep(1)) drains database resources and increases CPU utilization on idle systems.2 Implementations must leverage PostgreSQL's LISTEN/NOTIFY pub/sub mechanism to instantly wake idle workers upon job insertion, falling back to polling only as a safety net.32

### **Retrieval and RAG Anti-Patterns**

In the domain of semantic search, the rapid proliferation of dedicated vector databases (such as Pinecone, Milvus, or Qdrant) has led developers to mistakenly believe PostgreSQL is insufficient for AI workloads.7 This is empirically false for the vast majority of use cases. Dedicated vector stores introduce network latency, necessitate complex duplicate data synchronization pipelines, and complicate disaster recovery.6 PostgreSQL 16 with pgvector using HNSW indexing operates with sub-millisecond similarity search latency on datasets exceeding 50 million records, which is orders of magnitude beyond Fabrik's projected capacity needs.6

When implementing Hybrid Search, a common mathematical anti-pattern is hardcoding score fusion by attempting to directly add or linearly weight vector cosine similarity scores with BM25 ts\_rank scores.35 This fails catastrophically in production because the scoring distributions exist on entirely distinct scales; cosine distances range tightly from 0 to 2, whereas BM25 scores can scale unboundedly from 10 to 100+ based on term frequency.35 Rank-based fusion (RRF) must be utilized because rank normalization preserves the statistical distribution regardless of the underlying algorithm's numerical scale.8

In data ingestion pipelines, Semantic Chunking—which attempts to split documents based on embedding cosine similarity shifts between sentences—is banned. Empirical evaluations demonstrate that it slows ingestion pipelines drastically and incurs high API costs for a negligible 3-5% retrieval gain compared to standard Recursive Character Splitting with proper overlap configuration.22

| Architectural Domain | Banned Pattern | Failure Mode & Rationale | Authorized Fabrik Alternative |
| :---- | :---- | :---- | :---- |
| **State Management** | External Brokers (Redis, Celery, RabbitMQ) | Introduces secondary points of failure, breaks cross-domain ACID transactional guarantees, increases deployment complexity.1 | PostgreSQL FOR UPDATE SKIP LOCKED handles millions of jobs natively with zero added infra.3 |
| **Concurrency** | SELECT FOR UPDATE without SKIP LOCKED | Row locking causes concurrent workers to block each other, causing extreme contention.1 | Append the SKIP LOCKED clause to instruct the execution planner to bypass tuples holding an active xmax lock.5 |
| **Resource Management** | Naive Polling Loops | Drains connection pools and increases CPU utilization up to 25% on idle databases.2 | Implement PostgreSQL LISTEN/NOTIFY pub/sub to wake idle workers instantly upon an INSERT trigger.32 |
| **Vector Storage** | Dedicated Vector DBs (Pinecone, Qdrant) | Introduces network latency, duplicate data synchronization, and complicates backup procedures.6 | pgvector HNSW indexes support sub-millisecond search on datasets exceeding 50 million records.6 |
| **Search Mathematics** | Linear Score Addition (Vector \+ BM25) | Fails because scoring distributions exist on entirely different mathematical scales.35 | Reciprocal Rank Fusion (RRF) normalizes arbitrary distributions mathematically.8 |
| **Data Ingestion** | Semantic Chunking | High computational overhead and LLM API costs yielding only a 3% retrieval gain.22 | Recursive Character Splitting with 10-20% token overlaps provides highly reliable context retention.24 |
| **Token Operations** | Heuristic Token Counting (Length / 4\) | Fails unpredictably with code blocks or non-English text, resulting in API truncation errors.28 | Implement tiktoken.encoding\_for\_model() to deterministically count Byte Pair Encoding (BPE) integers.26 |

## **What to Enforce in Execute Handoffs**

When an autonomous agent completes a development step and hands off execution to another agent (e.g., transitioning from database schema creation to Python API implementation), specific contextual payloads must be passed to ensure the next agent adheres to the Fabrik constraints.36 Handoffs must be strict, deterministic, and heavily parameterized.

### **Job Orchestration Handoffs**

When handing off queue implementation from the database layer to the application layer, the agent must verify that the database migration scripts define the precise queue schema, including the execute\_after timestamp column for delayed execution, the retry\_count integer, and the status enum. The handoff payload must explicitly state the expected JSONB payload structure required by the target worker function.

Furthermore, the handoff must contain the exact retry parameters defined for the target job class. The payload must instruct the subsequent agent to implement the specific exponential backoff equation: ![][image3]. The agent must confirm that the target API endpoint does not execute long-running tasks synchronously but correctly inserts them into the PostgreSQL job table within the same ACID transaction as the primary data mutation.4 This guarantees that if the API request fails, the background job is never orphaned. Finally, the handoff must explicitly dictate the graceful shutdown behavior, instructing the implementation agent to capture SIGINT and SIGTERM signals in Python to allow the current job to finish processing before terminating the worker process.

### **RAG and Semantic Search Handoffs**

For retrieval pipelines, the handoff payload must certify that the PostgreSQL instance has both pgvector and pg\_trgm extensions enabled.9 When handing off chunking implementation from the ingestion agent to the pipeline agent, the payload must explicitly dictate the maximum chunk size (e.g., 512 tokens) and the overlap window (e.g., 50 tokens) to ensure the downstream agent writes the recursive text-splitter correctly.37

The execution handoff must also mandate the specific embedding model parameters. In 2025/2026, the optimal balance of cost, speed, and recall dictates the use of voyage-3-large for proprietary API usage (offering 1024 dimensions and ultra-low latency) or Qwen3-Embedding for self-hosted scenarios.38 The handoff must contain the explicit prompt engineering directives that instruct the LLM to output structured citations referencing the chunk\_id metadata provided in the augmented context.29 If the handoff does not include the instruction to trace citations via metadata injection, the operation must be aborted.

## **What to Verify in final\_gate.py**

The final\_gate.py script serves as the CI/CD gateway, ensuring no non-compliant code is merged into the Fabrik main branch. To achieve zero-ops durability, this script must be unforgiving. It must utilize Abstract Syntax Tree (AST) parsing and regular expressions to automate structural checks across the Python and SQL codebases.42

### **Queue and Worker Validation**

The pipeline must enforce database safety dynamically. The script must parse SQL strings within the Python codebase and assert the presence of FOR UPDATE SKIP LOCKED inside any query that SELECTs from the jobs table.3 A failure to include this primitive will block the build. Similarly, the script must inspect Alembic or raw SQL migration files. If a table contains a status column indicative of a queue structure, the script must fail the build if a CREATE INDEX... WHERE status \= 'pending' partial index is not physically present in the migration.15

At the application level, AST parsing must ensure that the Python worker loop contains global exception handling. The script will verify that an except Exception as e: block exists that correctly executes a SQL update to transition the database row to failed and increments the retry counter when a task throws an unhandled exception.44 If the worker loop lacks this error containment, a silent failure loop could occur, and the gate must reject the commit.

### **Retrieval and AI Integration Validation**

Token economics are a primary point of failure in large AI applications. The gate must reject any codebase interacting with OpenAI or Anthropic APIs if the tiktoken library is not imported and explicitly utilized to check the prompt length against the model limit.26 Specifically, the gate should look for the 85% budget logic, ensuring that len(encoding.encode(prompt)) \< (MODEL\_LIMIT \* 0.85) is evaluated before network dispatch.25

Database schema validation must be equally rigorous. Migration files utilizing CREATE INDEX... USING hnsw must be flagged and rejected if they omit the WITH (m \= 16, ef\_construction \= 64\) tuning parameters, as default parameters yield sub-optimal recall.21

For search logic, AST analysis of the query generation must ensure that hybrid queries use mathematical ranking standardizations. It must fail any Pull Request that attempts to mathematically sum a ts\_rank directly with an \<=\> cosine distance operator.35 Finally, for RAG pipelines, the gate must verify the presence of automated evaluation frameworks (such as Ragas or DeepEval). It must confirm that unit tests execute automated checks for Context Precision, Answer Relevancy, and Faithfulness utilizing a synthetic golden dataset before allowing the pipeline to deploy to production.46

## **What Belongs in AGENTS.md / AGENTS-compact.md vs Human Guidance**

To program autonomous coding agents to generate compliant architecture reliably, the AGENTS.md system file must contain tightly scoped, deterministic instructions. Agents do not interpret nuance well; they require absolute constraints. Conversely, human developers require overarching philosophical guidance to handle edge cases and architectural shifts.

### **Explicit Content for AGENTS.md (Deterministic Rules)**

The agent instruction file must be written in imperative, restrictive language. It should serve as the absolute boundary for code generation within the Fabrik platform.

* **Rule 1:** You are restricted to using PostgreSQL 16 for all state, including queues, caching, and background jobs. NEVER suggest, import, install, or configure Redis, Celery, RabbitMQ, TaskIQ, or ARQ in Python.
* **Rule 2:** To dequeue jobs, you must write SQL containing exactly: SELECT \* FROM jobs WHERE status \= 'pending' LIMIT 1 FOR UPDATE SKIP LOCKED;
* **Rule 3:** Execute all jobs in isolated Python processes. The parent process must use os.wait4() or subprocess to monitor the child to prevent memory leaks from crashing the main API.
* **Rule 4:** Jobs must rely on PostgreSQL LISTEN/NOTIFY to wake workers. Do not write endless time.sleep() polling loops.
* **Rule 5:** Do not create secondary Dead Letter Queue (DLQ) tables. Failed jobs remain in the main table with status \= 'failed' and an incremented retry\_count.
* **Rule 6:** For AI applications, you are restricted to pgvector and PostgreSQL native full-text search (tsvector). NEVER suggest Pinecone, Weaviate, Qdrant, or Elasticsearch.
* **Rule 7:** All RAG retrieval MUST be Hybrid. You must write SQL that executes an HNSW vector cosine search and a tsvector BM25 search in parallel Common Table Expressions (CTEs).
* **Rule 8:** You MUST fuse the results using Reciprocal Rank Fusion (RRF) with the formula 1.0 / (60 \+ rank). Do not add raw vector scores to BM25 scores.
* **Rule 9:** Use tiktoken (BPE) to count tokens before calling LLMs. Hard limit contexts to 85% of the model's stated capacity.
* **Rule 10:** Use Recursive Character Text Splitting. Do not write complex NLP-based semantic chunkers.

### **Human Guidance Only (Nuance and Scaling)**

Human operators require context that agents do not. The following concepts should be documented outside the agent rule files, reserved for the solo developer's operational manual.

* **Database Vacuuming:** While SKIP LOCKED prevents contention, high-throughput queues generate significant dead tuples in PostgreSQL. The human operator must monitor autovacuum performance and may need to tune autovacuum\_vacuum\_scale\_factor aggressively on the jobs table to prevent bloat.
* **Exactly-Once Trade-offs:** The human architect must understand that exactly-once delivery is a distributed systems myth. The system is designed for at-least-once delivery. Therefore, if a third-party API lacks idempotency keys, the human must design compensating transactions (e.g., checking if a stripe customer exists before creating one) rather than relying on the queue to never duplicate a task.48
* **Evaluating RAG Quality:** While agents can write Ragas tests, humans must review the failure modes. If precision drops, the human must decide whether the issue is the chunk size, the embedding model's domain knowledge, or the quality of the raw ingested data.49
* **Scaling Triggers:** The architecture is designed for up to 50,000 jobs per second. If Fabrik experiences hyper-growth beyond this, the human must evaluate migrating the queue to an external broker, though this scenario falls outside the 2025-2027 solo-developer scope.1

## **Minimal Practical Examples for Fabrik Stack**

The following implementations demonstrate the required standards utilizing the Fabrik stack (Python, FastAPI, PostgreSQL 16), showcasing the precise mechanics of lock management and hybrid search fusions.

### **Example 1: PostgreSQL Queue with SKIP LOCKED and Fork Isolation**

This example demonstrates the safe, concurrency-proof extraction of a job utilizing the required primitives, combined with fork isolation to ensure the main worker process remains perfectly stable even if a third-party library causes a segmentation fault.1

Python

import os
import sys
import time
import signal
import psycopg
from psycopg\_pool import ConnectionPool
from contextlib import contextmanager

\# Assuming pool is initialized globally in the FastAPI/Worker app
pool \= ConnectionPool("dbname=fabrik user=postgres", min\_size=2, max\_size=10)

def dequeue\_and\_process\_job():
    """
    Acquires a single job using SKIP LOCKED to prevent race conditions,
    and executes it in a fork-isolated child process.
    """
    with pool.connection() as conn:
        with conn.transaction():
            \# 1\. Acquire lock on the next available job, skipping locked rows
            cursor \= conn.execute("""
                SELECT id, payload, retry\_count
                FROM background\_jobs
                WHERE status \= 'pending'
                  AND execute\_after \<= NOW()
                ORDER BY priority DESC, created\_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED;
            """)

            job \= cursor.fetchone()
            if not job:
                return False \# Queue is empty

            job\_id, payload, retry\_count \= job

            \# 2\. Mark as processing to prevent visibility timeout issues
            conn.execute("""
                UPDATE background\_jobs
                SET status \= 'processing', updated\_at \= NOW()
                WHERE id \= %s;
            """, (job\_id,))

    \# 3\. Fork isolation to protect the main worker from OOM/Segfaults
    child\_pid \= os.fork()
    if child\_pid \== 0:
        \# Child process execution
        try:
            \# Re-establish DB connection for child to avoid sharing socket
            execute\_business\_logic(payload)

            with psycopg.connect("dbname=fabrik user=postgres") as child\_conn:
                child\_conn.execute("""
                    UPDATE background\_jobs
                    SET status \= 'completed', updated\_at \= NOW()
                    WHERE id \= %s;
                """, (job\_id,))
            os.\_exit(0) \# Exit cleanly
        except Exception as e:
            \# Log error details here
            os.\_exit(1) \# Exit with error code
    else:
        \# Parent process monitoring
        \_, status \= os.waitpid(child\_pid, 0)

        \# Check if child exited with an error or was killed by a signal (e.g., OOM)
        if status\!= 0:
            handle\_job\_failure(job\_id, retry\_count)

    return True

def handle\_job\_failure(job\_id: int, current\_retries: int):
    """
    Implements dead-letter logic and exponential backoff within the primary table.
    Uses factor of 2: 5s, 10s, 20s, 40s...
    """
    max\_retries \= 5
    if current\_retries \>= max\_retries:
        next\_status \= 'failed'
        delay\_interval \= "0 seconds"
    else:
        next\_status \= 'pending'
        delay\_seconds \= 5 \* (2 \*\* current\_retries)
        delay\_interval \= f"{delay\_seconds} seconds"

    with pool.connection() as conn:
        conn.execute(f"""
            UPDATE background\_jobs
            SET status \= %s,
                retry\_count \= retry\_count \+ 1,
                execute\_after \= NOW() \+ INTERVAL '{delay\_interval}',
                updated\_at \= NOW()
            WHERE id \= %s;
        """, (next\_status, job\_id))

def worker\_loop():
    """
    Main loop utilizing LISTEN/NOTIFY for instant wake-up.
    """
    with pool.connection() as conn:
        conn.execute("LISTEN new\_background\_job;")
        while True:
            \# Attempt to drain the queue
            while dequeue\_and\_process\_job():
                pass

            \# Queue is empty, wait for a notification instead of busy-polling
            gen \= conn.notifies(timeout=60.0)
            try:
                next(gen) \# Blocks until a notification arrives or timeout
            except StopIteration:
                pass \# Timeout reached, loop will restart and check queue anyway

### **Example 2: Hybrid Search with Reciprocal Rank Fusion (RRF) and Token Counting**

This SQL logic demonstrates the correct method for combining pgvector semantic similarity with tsvector full-text keyword matching, normalizing the outputs via RRF.18 The Python wrapper demonstrates the mandatory token budgeting required before dispatching to an LLM.25

Python

import tiktoken
import psycopg

def execute\_hybrid\_search(query\_text: str, query\_embedding: list\[float\], limit: int \= 10):
    """
    Executes a parallel dense and sparse search, fused via RRF.
    """
    sql \= """
    WITH semantic\_search AS (
        SELECT
            id,
            content,
            metadata,
            RANK() OVER (ORDER BY embedding \<=\> %s::vector) AS rank
        FROM document\_chunks
        ORDER BY embedding \<=\> %s::vector
        LIMIT 40
    ),
    keyword\_search AS (
        SELECT
            id,
            content,
            metadata,
            RANK() OVER (ORDER BY ts\_rank\_cd(to\_tsvector('english', content), plainto\_tsquery('english', %s)) DESC) AS rank
        FROM document\_chunks
        WHERE to\_tsvector('english', content) @@ plainto\_tsquery('english', %s)
        ORDER BY ts\_rank\_cd(to\_tsvector('english', content), plainto\_tsquery('english', %s)) DESC
        LIMIT 40
    )
    SELECT
        COALESCE(semantic\_search.id, keyword\_search.id) AS chunk\_id,
        COALESCE(semantic\_search.content, keyword\_search.content) AS content,
        COALESCE(semantic\_search.metadata, keyword\_search.metadata) AS metadata,
        \-- RRF Formula: 1.0 / (k \+ rank) where k=60
        COALESCE(1.0 / (60 \+ semantic\_search.rank), 0.0) \+
        COALESCE(1.0 / (60 \+ keyword\_search.rank), 0.0) AS rrf\_score
    FROM semantic\_search
    FULL OUTER JOIN keyword\_search ON semantic\_search.id \= keyword\_search.id
    ORDER BY rrf\_score DESC
    LIMIT %s;
    """

    with psycopg.connect("dbname=fabrik user=postgres") as conn:
        cursor \= conn.execute(sql, (
            query\_embedding, query\_embedding,
            query\_text, query\_text, query\_text,
            limit
        ))
        return cursor.fetchall()

def construct\_rag\_context(query: str, retrieved\_chunks: list, model: str \= "gpt-4o") \-\> str:
    """
    Constructs the LLM context while strictly enforcing the 85% token budget.
    """
    encoding \= tiktoken.encoding\_for\_model(model)
    MAX\_MODEL\_TOKENS \= 128000
    BUDGET\_TOKENS \= int(MAX\_MODEL\_TOKENS \* 0.85)

    context\_parts \=
    current\_tokens \= 0

    \# Base prompt tokens
    system\_prompt \= "You are a helpful assistant. Use the provided context to answer the question. Cite chunk\_ids."
    current\_tokens \+= len(encoding.encode(system\_prompt))
    current\_tokens \+= len(encoding.encode(query))

    for chunk in retrieved\_chunks:
        chunk\_id, content, metadata, score \= chunk
        formatted\_chunk \= f"\\n\\nContent: {content}\\nSource: {metadata.get('source\_url')}\\n"
        chunk\_tokens \= len(encoding.encode(formatted\_chunk))

        \# Stop appending if adding this chunk exceeds the safety budget
        if current\_tokens \+ chunk\_tokens \> BUDGET\_TOKENS:
            print(f"Token budget reached. Truncating context at {current\_tokens} tokens.")
            break

        context\_parts.append(formatted\_chunk)
        current\_tokens \+= chunk\_tokens

    final\_context \= "".join(context\_parts)
    return final\_context

## **Recommended Final Content for Rule Files**

The following sections represent the exact markdown files to be integrated into the Fabrik agents' rule repository. They serve as permanent, highly durable architectural guidelines, directly answering the specific requirements of the design prompt.

### **75-workers-jobs.md**

# **Background Workers and Job Orchestration**

## **Core Philosophy**

The Fabrik architecture operates under severe constraints on maintenance overhead (Solo Developer, 50 hours/week). We do not run external message brokers. All background jobs, deferred tasks, and event queues exist exclusively inside PostgreSQL 16\. This provides strict ACID guarantees, atomic backups, and zero network configuration overhead while gracefully scaling to millions of jobs daily.

## **1\. The Queue Table Architecture**

Jobs must be stored in a dedicated background\_jobs table.

* **Payloads:** Store job parameters in a JSONB column.
* **State Machine:** Track lifecycle using a status column constrained to pending, processing, completed, and failed.
* **Visibility Timeout:** Implement an execute\_after timestamp column to handle scheduling and delayed retries.
* **Idempotency:** Utilize a unique client\_id or idempotency\_key constraint to enable INSERT... ON CONFLICT DO UPDATE debouncing. Job handlers must be written to assume at-least-once delivery, checking database state before executing external side effects (e.g., verifying a user isn't already created in Stripe before calling the API).
* **Indexing:** A partial index on status \= 'pending' is strictly required to prevent table scans during worker wake-ups.

## **2\. Worker Concurrency Control**

Race conditions are the primary threat in database-backed queues.

* **Enforced Primitive:** You must extract jobs using SELECT... FOR UPDATE SKIP LOCKED.
* **Mechanism:** This commands PostgreSQL's lock manager to acquire an exclusive row-level lock while entirely bypassing any tuples currently locked by other transactions. It achieves Redis-like concurrency without deadlocks or query queuing.

## **3\. Worker Lifecycle and Isolation**

Python's memory management and third-party C-extensions can introduce severe system instability.

* **Forked Execution:** The primary worker daemon must not execute business logic directly. It must fork a child process for each task.
* **Parent Monitoring:** The parent process utilizes os.wait4() or os.waitpid() to track the child. If the child segfaults or triggers an OOM kill, the parent catches the signal, marks the job as failed, and continues operating without interrupting the main worker loop.
* **Graceful Shutdown:** Workers must capture SIGTERM and SIGINT signals. Upon receiving a shutdown signal, the worker must refuse to accept new jobs and wait for the currently executing child process to finish before exiting.

## **4\. Failure, Retries, and Dead Letters**

Over-engineering Dead Letter Queues (DLQs) by creating secondary tables fragments state and complicates observability.

* **In-Place DLQ:** A failed job is simply a row where status \= 'failed'. Retain it in the primary table. This is sufficient for the Fabrik operational scale without requiring complex routing logic.
* **Backoff Math:** Implement standard exponential backoff: Delay \= Base \* (2 ^ Attempt). The standard default base is 5 seconds.
* **Terminal States:** Set a strict limit of 5 retries. Once exceeded, update status to failed and do not schedule further execution.

## **5\. Performance and Latency**

* **LISTEN/NOTIFY:** Naive polling (e.g., time.sleep(1)) drains database connections and harms the primary application. Utilize PostgreSQL's LISTEN/NOTIFY pub/sub interface. The worker yields asynchronously until a new INSERT trigger fires NOTIFY new\_background\_job, enabling near-zero latency dispatch.

## **FAQ: When is Redis Justified?**

A PostgreSQL queue is fully sufficient until the system approaches \~50,000 job enqueues per second. Redis is only justified when the workload requires ultra-low latency, ephemeral fire-and-forget messages where data loss is acceptable, or when the sheer volume of dead tuples from high-throughput job creation overwhelms PostgreSQL's autovacuum processes. For Fabrik's 2025/2026 horizon, PostgreSQL is the absolute standard.

### **65-rag-search.md**

# **Retrieval-Augmented Generation (RAG) and Search**

## **Core Philosophy**

The objective of the Fabrik RAG stack is to maximize recall and answer faithfulness while rigidly controlling token economics and architectural complexity. Standalone vector databases (Pinecone, Qdrant) are strictly prohibited. PostgreSQL 16 with the pgvector extension serves as the single source of truth for dense embeddings, structural metadata, and sparse text indexes, eliminating network boundaries and synchronization debt.

## **1\. Chunking Strategy**

Semantic chunking models are expensive to run, add high ingestion latency, and offer marginal (3-5%) gains in retrieval quality.

* **Standard:** Use standard Recursive Character Splitting. This strategy produces the best baseline retrieval quality with the least tuning.
* **Parameters:** Aim for chunk sizes of 512 to 1024 tokens, ensuring an overlap window of 10% to 20% to prevent hard cuts across critical context boundaries.
* **Ingestion Pipeline:** Pre-process text asynchronously via the background worker queue, never blocking the main API thread.

## **2\. Embedding Models**

The selection of an embedding model dictates long-term database sizing and retrieval latency.

* **Defaults:** Prefer voyage-3-large (1024 dimensions) for high-speed, high-accuracy API usage, or text-embedding-3-large for deep OpenAI ecosystem integration. For purely open-source environments, utilize Qwen3-Embedding.
* **Dimensions:** Lower dimensionality reduces memory overhead in PostgreSQL. 1024-1536 dimensions is the optimal tradeoff for 2025/2026.

## **3\. Database and Vector Storage**

Vectors must be indexed to support fast approximate nearest neighbor (ANN) searches. pgvector natively supports 50M+ vectors, rendering dedicated DBs unnecessary for our scale.

* **Index Type:** Always use HNSW (Hierarchical Navigable Small World). Do not use IVFFlat as it requires manual rebuilding to maintain recall precision.
* **Build Parameters:** Specify WITH (m \= 16, ef\_construction \= 64).
* **Query Parameters:** Adjust hnsw.ef\_search dynamically. Use 40 for interactive UI latency, and 200 for analytical background completeness.

## **4\. Hybrid Search and Re-Ranking**

Dense vectors are semantically intelligent but fail at exact keyword matches (e.g., error codes, UUIDs, SKUs).

* **Dual Execution:** Every search must independently query the pgvector index (via cosine distance \<=\>) and the native PostgreSQL full-text index tsvector (via BM25/ts\_rank).
* **Fusion Strategy:** These scores are mathematically incompatible. You must use Reciprocal Rank Fusion (RRF) to combine them.
* **Formula:** Score \= 1.0 / (k \+ rank), where k is a tuning constant strictly set to 60\. Do not deploy external Cross-Encoder re-rankers unless specifically tasked, as they add massive latency to the critical path.

## **5\. Token Budgeting and Context Management**

Failure to manage token budgets results in API failures, unpredictable costs, and LLM context amnesia (hallucination).

* **The 85% Rule:** Never load the LLM context window past 85% of its stated maximum capacity. The remaining 15% is the safety buffer for system prompts and token estimation errors.
* **Pre-Flight Counting:** Use tiktoken (specifically o200k\_base or cl100k\_base for OpenAI models) in Python to strictly count the Byte Pair Encoding (BPE) lengths of chunks before dispatch. Do not use character-division heuristics.

## **6\. Citations and Source Attribution**

End-users must be able to verify AI claims.

* **Metadata Injection:** Inject the document's global ID and sequence number into the chunk's JSON payload during the chunking phase.
* **Prompting:** Explicitly instruct the LLM in the system prompt: "You must cite the provided for every claim."
* **Resolution:** The frontend or backend presentation layer maps the cited chunk IDs back to human-readable source documents or URLs before rendering.

## **7\. Retrieval Quality Evaluation**

Avoid over-engineering complex, multi-agent evaluation frameworks until the baseline is proven.

* **Core Metrics:** Measure only *Faithfulness* (does the output match the retrieved chunk exactly?) and *Context Precision* (was the highly relevant chunk returned in the top-K of the hybrid search?).
* **Automation:** Utilize frameworks like Ragas or DeepEval in unit tests to evaluate these two metrics against a static golden dataset of 50-100 test queries. Do not deploy prompt changes if Faithfulness drops.

#### **Works cited**

1. Postgres is the only Queue you need (until 50k jobs/sec) | by Harsh Vaghela \- Medium, accessed March 31, 2026, [https://medium.com/@harsh.vaghela.work/postgres-is-the-only-queue-you-need-until-50k-jobs-sec-5931611b551c](https://medium.com/@harsh.vaghela.work/postgres-is-the-only-queue-you-need-until-50k-jobs-sec-5931611b551c)
2. Implementing a Postgres job queue in less than an hour \- AmineDiro, accessed March 31, 2026, [https://aminediro.com/posts/pg\_job\_queue/](https://aminediro.com/posts/pg_job_queue/)
3. Using FOR UPDATE SKIP LOCKED for Queue-Based Workflows without Deadlocks, accessed March 31, 2026, [https://www.netdata.cloud/academy/update-skip-locked/](https://www.netdata.cloud/academy/update-skip-locked/)
4. Show HN: Pq – Simple, durable background tasks in Python using ..., accessed March 31, 2026, [https://news.ycombinator.com/item?id=47110669](https://news.ycombinator.com/item?id=47110669)
5. Building real-time, thread-safe, resilient, and type safe Queue with Postgres \- Naveen Negi, accessed March 31, 2026, [https://naveennegi.medium.com/postgres-as-queue-deep-dive-into-fairly-advanced-implementation-68f28041853e](https://naveennegi.medium.com/postgres-as-queue-deep-dive-into-fairly-advanced-implementation-68f28041853e)
6. Best Vector Databases in 2026: A Complete Comparison Guide \- Firecrawl, accessed March 31, 2026, [https://www.firecrawl.dev/blog/best-vector-databases](https://www.firecrawl.dev/blog/best-vector-databases)
7. What's the best Vector DB? What's new in vector db and how is one better than other? \[D\], accessed March 31, 2026, [https://www.reddit.com/r/MachineLearning/comments/1ijxrqj/whats\_the\_best\_vector\_db\_whats\_new\_in\_vector\_db/](https://www.reddit.com/r/MachineLearning/comments/1ijxrqj/whats_the_best_vector_db_whats_new_in_vector_db/)
8. Building Hybrid Search for RAG: Combining pgvector and Full-Text Search with Reciprocal Rank Fusion \- DEV Community, accessed March 31, 2026, [https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk](https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk)
9. Hybrid Search in PostgreSQL: The Missing Manual | ParadeDB, accessed March 31, 2026, [https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
10. Building a Scalable Background Task System in Python | by Code with Margaret, accessed March 31, 2026, [https://python.plainenglish.io/building-a-scalable-background-task-system-in-python-3d37f543afdb](https://python.plainenglish.io/building-a-scalable-background-task-system-in-python-3d37f543afdb)
11. The best way to use a DB table as a job queue (a.k.a batch queue or message queue) \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/297280/the-best-way-to-use-a-db-table-as-a-job-queue-a-k-a-batch-queue-or-message-queu](https://stackoverflow.com/questions/297280/the-best-way-to-use-a-db-table-as-a-job-queue-a-k-a-batch-queue-or-message-queu)
12. postgres as queue \- leontrolski, accessed March 31, 2026, [https://leontrolski.github.io/postgres-as-queue.html](https://leontrolski.github.io/postgres-as-queue.html)
13. Retry jobs | Cloud Scheduler \- Google Cloud Documentation, accessed March 31, 2026, [https://docs.cloud.google.com/scheduler/docs/configuring/retry-jobs](https://docs.cloud.google.com/scheduler/docs/configuring/retry-jobs)
14. How to Configure Optimal Retry Backoff Settings in ArgoCD \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-26-argocd-configure-optimal-retry-backoff-settings/view](https://oneuptime.com/blog/post/2026-02-26-argocd-configure-optimal-retry-backoff-settings/view)
15. Postgres as queue \- Hacker News, accessed March 31, 2026, [https://news.ycombinator.com/item?id=39315833](https://news.ycombinator.com/item?id=39315833)
16. Implementing Efficient Queue Systems in PostgreSQL | by Epm Mcys \- Medium, accessed March 31, 2026, [https://medium.com/@epam.macys/implementing-efficient-queue-systems-in-postgresql-c219ccd56327](https://medium.com/@epam.macys/implementing-efficient-queue-systems-in-postgresql-c219ccd56327)
17. I implemented Hybrid Search (BM25 \+ pgvector) in Postgres to fix RAG retrieval for exact keywords. Here is the logic. \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Rag/comments/1pcvtan/i\_implemented\_hybrid\_search\_bm25\_pgvector\_in/](https://www.reddit.com/r/Rag/comments/1pcvtan/i_implemented_hybrid_search_bm25_pgvector_in/)
18. How to Create Hybrid Search \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-30-hybrid-search/view](https://oneuptime.com/blog/post/2026-01-30-hybrid-search/view)
19. Optimizing Hybrid Search Query with Reciprocal Rank Fusion (RRF) | Server \- MariaDB, accessed March 31, 2026, [https://mariadb.com/docs/server/reference/sql-structure/vectors/optimizing-hybrid-search-query-with-reciprocal-rank-fusion-rrf](https://mariadb.com/docs/server/reference/sql-structure/vectors/optimizing-hybrid-search-query-with-reciprocal-rank-fusion-rrf)
20. Hybrid search with PostgreSQL and pgvector \- Jonathan Katz, accessed March 31, 2026, [https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)
21. pgvector/pgvector: Open-source vector similarity search for Postgres \- GitHub, accessed March 31, 2026, [https://github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)
22. What chunking strategies are you using in your RAG pipelines? \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Rag/comments/1rab7rs/what\_chunking\_strategies\_are\_you\_using\_in\_your/](https://www.reddit.com/r/Rag/comments/1rab7rs/what_chunking_strategies_are_you_using_in_your/)
23. Chunking Strategies for RAG: Fixed, Recursive, Semantic, Language-Based, and Context-Aware Approaches \- Matheus Jericó, accessed March 31, 2026, [https://matheusjerico.medium.com/chunking-strategies-for-rag-fixed-recursive-semantic-language-based-and-context-aware-4ab476aea7d1](https://matheusjerico.medium.com/chunking-strategies-for-rag-fixed-recursive-semantic-language-based-and-context-aware-4ab476aea7d1)
24. Chunking Strategies for LLM Applications \- Pinecone, accessed March 31, 2026, [https://www.pinecone.io/learn/chunking-strategies/](https://www.pinecone.io/learn/chunking-strategies/)
25. Token Budgeting Architecture for Large AI Apps \- Medium, accessed March 31, 2026, [https://medium.com/@vasanthancomrads/token-budgeting-architecture-for-large-ai-apps-8c2ba5cd9c82](https://medium.com/@vasanthancomrads/token-budgeting-architecture-for-large-ai-apps-8c2ba5cd9c82)
26. How to count tokens with Tiktoken \- OpenAI Developers, accessed March 31, 2026, [https://developers.openai.com/cookbook/examples/how\_to\_count\_tokens\_with\_tiktoken](https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken)
27. tiktoken is a fast BPE tokeniser for use with OpenAI's models. \- GitHub, accessed March 31, 2026, [https://github.com/openai/tiktoken](https://github.com/openai/tiktoken)
28. How Tiktoken Stops AI Token Costs From Exploding in Production | Galileo, accessed March 31, 2026, [https://galileo.ai/blog/tiktoken-guide-production-ai](https://galileo.ai/blog/tiktoken-guide-production-ai)
29. Agentforce and RAG: Best Practices for Better Agents \- Salesforce, accessed March 31, 2026, [https://www.salesforce.com/agentforce/agentforce-and-rag/](https://www.salesforce.com/agentforce/agentforce-and-rag/)
30. Advanced RAG Techniques for High-Performance LLM Applications \- Neo4j, accessed March 31, 2026, [https://neo4j.com/blog/genai/advanced-rag-techniques/](https://neo4j.com/blog/genai/advanced-rag-techniques/)
31. Why are all the task libraries and frameworks I see so heavy? : r/Python \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1mrxbxc/why\_are\_all\_the\_task\_libraries\_and\_frameworks\_i/](https://www.reddit.com/r/Python/comments/1mrxbxc/why_are_all_the_task_libraries_and_frameworks_i/)
32. janbjorge/pgqueuer: PgQueuer is a Python library ... \- GitHub, accessed March 31, 2026, [https://github.com/janbjorge/pgqueuer](https://github.com/janbjorge/pgqueuer)
33. Introducing PgQueuer: A Minimalist Python Job Queue Built on PostgreSQL \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1ckrmog/introducing\_pgqueuer\_a\_minimalist\_python\_job/](https://www.reddit.com/r/Python/comments/1ckrmog/introducing_pgqueuer_a_minimalist_python_job/)
34. what place do vector-native databases have in 2025? I feel using pgvector or red... | Hacker News, accessed March 31, 2026, [https://news.ycombinator.com/item?id=44954123](https://news.ycombinator.com/item?id=44954123)
35. I rewrote hybrid search four times \- here's what actually matters : r/Rag \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Rag/comments/1pd7tao/i\_rewrote\_hybrid\_search\_four\_times\_heres\_what/](https://www.reddit.com/r/Rag/comments/1pd7tao/i_rewrote_hybrid_search_four_times_heres_what/)
36. A practical guide to building agents \- OpenAI, accessed March 31, 2026, [https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
37. From RAG to Context \- A 2025 year-end review of RAG \- RAGFlow, accessed March 31, 2026, [https://ragflow.io/blog/rag-review-2025-from-rag-to-context](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)
38. How to Choose the Best Embedding Model for RAG in 2026: 10 Models Benchmarked, accessed March 31, 2026, [https://milvus.io/blog/choose-embedding-model-rag-2026.md](https://milvus.io/blog/choose-embedding-model-rag-2026.md)
39. Best Embedding Models for RAG (2026): Ranked by MTEB Score, Cost, and Self-Hosting, accessed March 31, 2026, [https://blog.premai.io/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/](https://blog.premai.io/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/)
40. How To Choose The Best Embedding Model For Your LLM Application \- MongoDB, accessed March 31, 2026, [https://www.mongodb.com/company/blog/technical/how-choose-best-embedding-model-for-your-llm-application](https://www.mongodb.com/company/blog/technical/how-choose-best-embedding-model-for-your-llm-application)
41. Retrieval-Augmented Generation (RAG): 2025 Definitive Guide \- Chitika, accessed March 31, 2026, [https://www.chitika.com/retrieval-augmented-generation-rag-the-definitive-guide-2025/](https://www.chitika.com/retrieval-augmented-generation-rag-the-definitive-guide-2025/)
42. How to run a background procedure while constantly checking for input \- threading?, accessed March 31, 2026, [https://stackoverflow.com/questions/22648765/how-to-run-a-background-procedure-while-constantly-checking-for-input-threadin](https://stackoverflow.com/questions/22648765/how-to-run-a-background-procedure-while-constantly-checking-for-input-threadin)
43. Final project (RAG Pipeline) for Generative AI Course \- GitHub, accessed March 31, 2026, [https://github.com/seansica/w267-final-project-rag-pipeline](https://github.com/seansica/w267-final-project-rag-pipeline)
44. Task Scheduling and Background Jobs in Python — The Ultimate Guide, accessed March 31, 2026, [https://blog.naveenpn.com/task-scheduling-and-background-jobs-in-python-the-ultimate-guide](https://blog.naveenpn.com/task-scheduling-and-background-jobs-in-python-the-ultimate-guide)
45. Supercharging vector search performance and relevance with pgvector 0.8.0 on Amazon Aurora PostgreSQL | AWS Database Blog, accessed March 31, 2026, [https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)
46. Automating RAG Pipeline Evaluation with RAGAS: A Testing Framework for RAG Applications | by Sumit Soman | Medium, accessed March 31, 2026, [https://medium.com/@sumit.somanchd/automating-rag-pipeline-evaluation-with-ragas-a-testing-framework-for-rag-applications-f5443ccd4e09](https://medium.com/@sumit.somanchd/automating-rag-pipeline-evaluation-with-ragas-a-testing-framework-for-rag-applications-f5443ccd4e09)
47. RAG Evaluation: The Definitive Guide to Unit Testing RAG in CI/CD \- Confident AI, accessed March 31, 2026, [https://www.confident-ai.com/blog/how-to-evaluate-rag-applications-in-ci-cd-pipelines-with-deepeval](https://www.confident-ai.com/blog/how-to-evaluate-rag-applications-in-ci-cd-pipelines-with-deepeval)
48. Retry with backoff pattern \- AWS Prescriptive Guidance, accessed March 31, 2026, [https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html)
49. RAG evaluation guide: metrics, frameworks & infrastructure \- Redis, accessed March 31, 2026, [https://redis.io/blog/rag-system-evaluation/](https://redis.io/blog/rag-system-evaluation/)
50. Result Evaluation for RAG: Metrics & Best Practices \- IBM, accessed March 31, 2026, [https://www.ibm.com/think/architectures/rag-cookbook/result-evaluation](https://www.ibm.com/think/architectures/rag-cookbook/result-evaluation)
51. Hybrid search on Postgres with pgvector using vecs \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/79795559/hybrid-search-on-postgres-with-pgvector-using-vecs](https://stackoverflow.com/questions/79795559/hybrid-search-on-postgres-with-pgvector-using-vecs)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAgCAYAAADJ2fKUAAABaUlEQVR4XqWTvUoFMRCFzyAWggiCIohPYGchgoWlta2FD+AT6BvY2PkCIlxsrGytbqfYKPoEgnZWcsFC0JlMNpn87S54YJLNdzL5md0FBkS+cX1BRytfoZZbY0MalyOzWjNb3Imwzu1mjo1C+hbHr4k757ZXT5wJNOnAwv6jAZ/QpCUZFHMt8M/SdccbrR1owjQ3VMW+TjeQJMJRQglz3KwlrBOv88Wt7LRs8DuBXrl/4rg13Gke6X14DeJFsMBxwiPhUiS1vPa88cDBx8G3cd+gi13n99L7AOccM/ZkJ3VcRyu1OjwjHu8w81SanKAu4Sw+06UYcVqasOqr9mHYPbT8+4ZFcb68F0m6MPjUM+lF8tVP7V5SMTmO/R2ulGHbj7ly2I22lloiANaxZxvQdzgznpOYj4FF/uK9H45FRUXdDaj9fQFVvH+pf730HkbU4D1yn58+tNR2qlbK4qg2d1jtEhcgqHPyGX9H50DTIEV3WwAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,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>
