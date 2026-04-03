# **Fabrik Data Architecture: PostgreSQL 16 and SQLAlchemy 2.0 Rulebook**

## **Executive Summary**

The architectural design of a data persistence layer for a solo-developer platform introduces a unique set of constraints that fundamentally differ from those of a large engineering organization. Operating within a strict boundary of approximately fifty focused hours per week, the solo developer cannot afford to absorb the operational overhead of managing fragmented database schemas, debugging obscure connection pool exhaustion errors, or manually resolving split-brain migration states. Furthermore, the deployment environment for the Fabrik platform—an ARM64 Ubuntu Virtual Private Server (VPS) managed via Coolify, utilizing Docker Compose—demands a highly deterministic, low-maintenance approach to resource management. The chosen stack relies on Python, FastAPI, Uvicorn, SQLAlchemy 2.0 (asynchronous), and PostgreSQL 16\. While highly capable, this asynchronous architecture is unforgiving of improper transaction scoping and blocking I/O operations.

This comprehensive research report establishes the permanent, immutable data architecture rules for the Fabrik platform. It synthesizes current PostgreSQL 16 optimization strategies, SQLAlchemy 2.0 asynchronous best practices, and infrastructure-as-code philosophies to create a durable, low-operations paradigm. The core thesis of this architecture dictates that the database is not a passive storage bucket; it is the ultimate, active guardian of data integrity. Constraints must be explicit, schema evolution must be version-controlled through Alembic, and the application layer must respect the mechanical realities of PostgreSQL's architecture, including its Multi-Version Concurrency Control (MVCC), B-tree implementation, and The Oversized-Attribute Storage Technique (TOAST) mechanics.

By adhering to the principles outlined in this document, the Fabrik platform will maintain a highly performant and stable backend capable of enduring years of product iteration without requiring a dedicated Database Administrator. The directives herein separate immutable rules—which must be enforced programmatically via Continuous Integration (CI) and parsing scripts such as final\_gate.py—from human-guided architectural heuristics. The ultimate output is a definitive rule file proposal, 25-data-postgres.md, designed to strictly guide autonomous LLM agents and the human developer in maintaining a robust, future-proof data layer.

## **The Mechanical Realities of the Deployment Environment**

To fully internalize the rules governing the Fabrik data layer, one must first analyze the mechanical realities of the underlying infrastructure and the software stack. Decisions regarding base images, memory allocation, and connection pooling are not merely preferences; they are structural requirements dictated by the deployment environment.

### **Base Image Selection and Cross-Architecture Compilation**

The development environment utilizes Windows Subsystem for Linux (WSL) running Ubuntu 24.04 (an x86\_64 architecture), while the production environment is an ARM64 Ubuntu VPS managed via Coolify. This cross-architecture deployment model introduces significant friction if container base images are not selected with extreme prejudice.

The absolute prohibition of Alpine Linux base images is the foremost infrastructure rule. Alpine Linux utilizes the musl C standard library rather than the GNU C Library (glibc), which is standard across Debian and Ubuntu distributions.1 While Alpine produces exceptionally small container image sizes, the musl library frequently causes compilation failures, missing wheel distributions, and obscure runtime segmentation faults with Python database drivers. Specifically, drivers like psycopg and asyncpg rely heavily on C-extensions for performance.1 Compiling these dependencies from source on an ARM64 Alpine image drastically increases build times and introduces fragility into the deployment pipeline. Therefore, the slim-bookworm Debian base image is mandated. It provides native glibc support, allowing the installation of pre-compiled Python wheels via pip, ensuring fast, deterministic builds that behave identically across the x86\_64 WSL development environment and the ARM64 production VPS.

### **PostgreSQL 16 Resource Allocation on a Constrained VPS**

PostgreSQL 16 introduces several sophisticated features that enhance performance without requiring manual application tuning, including improved bulk loading (COPY operations), parallelized hash joins, and incremental sorting that utilizes already-sorted data to reduce memory consumption.3 However, out of the box, PostgreSQL is configured for broad compatibility with legacy hardware rather than optimized for modern, memory-rich VPS environments.6

For a solo developer prioritizing low maintenance, configuring automated background processes is paramount. The Multi-Version Concurrency Control (MVCC) architecture of PostgreSQL dictates that UPDATE and DELETE operations do not immediately remove old data; instead, they leave behind "dead tuples" to ensure transaction isolation for concurrent readers.7 If these dead tuples are not routinely cleaned, the database suffers from table bloat, and sequential scans degrade significantly. Therefore, the Autovacuum daemon must be tuned to run aggressively.

Memory allocation must also be explicitly defined in the postgresql.conf file deployed via Coolify. The shared\_buffers parameter, which determines how much memory PostgreSQL uses to cache data pages, should typically be set to 15% to 25% of the total available RAM on the VPS.6 Setting this value too low forces the database to constantly read from the disk, destroying application latency. Conversely, setting it too high starves the Linux kernel's page cache. Similarly, the work\_mem parameter—the amount of memory used for internal sort operations and hash tables before writing to temporary disk files—must be carefully calculated. Because work\_mem is allocated per operation (not per query or per connection), a complex query with multiple sorts can consume multiples of the work\_mem value.6 On a constrained VPS, setting this too high will result in fatal Out-Of-Memory (OOM) killer terminations.

## **Schema Evolution and Migration Discipline**

The database schema is the rigid skeleton upon which the entire application is built. In a fast-moving solo-developer environment, ad-hoc modifications to this skeleton are a primary source of technical debt.

### **The Alembic Supremacy Principle vs. Raw SQL**

A recurring question in backend architecture is determining when direct schema.sql updates should be utilized instead of formal migration scripts. For the Fabrik platform, the answer is definitive: raw SQL schema updates are strictly banned. All schema evolution, from the initial database creation to the most minor constraint modification, must be executed through Alembic.8

Alembic acts as version control for the database schema. Instead of relying on manual ALTER TABLE commands executed directly against a staging or production database—which inevitably leads to untracked schema drift and deployment failures—Alembic captures every schema change as an explicit, versioned, and auditable Python script.10 This creates a predictable process where the Continuous Integration (CI) pipeline, the development environment, and the production VPS all utilize the exact same mechanism to reach the desired state.

### **The Mechanics and Limitations of Autogenerate**

Alembic's \--autogenerate feature operates by inspecting the current SQLAlchemy models declared in the Python application and comparing them against the live reflection of the target database schema.9 When differences are detected, Alembic generates a draft migration script. However, relying blindly on this feature is an anti-pattern.

Autogenerate is an imperfect tool. It frequently fails to detect subtle changes, such as the renaming of a column (often misinterpreting it as a drop of the old column and an addition of a new one, which would result in catastrophic data loss), complex unique constraint modifications, or alterations to PostgreSQL ENUM types.8 Therefore, the generated migration script must be treated strictly as a rough draft. It is mandatory for the developer or the autonomous agent to manually review the upgrade() and downgrade() functions, ensuring that no unintentional op.drop\_column() directives have been erroneously included.9

### **Deterministic Naming Conventions**

To guarantee that Alembic can accurately target constraints for modification or deletion, SQLAlchemy's MetaData must be initialized with a strict naming convention dictionary.11 Without an explicit naming convention, PostgreSQL automatically generates randomized names for unnamed constraints (e.g., users\_email\_key). If the database in the WSL environment names a constraint differently than the production VPS, Alembic migration scripts attempting to drop or alter that constraint will crash.

Implementing a naming convention dictionary ensures that indexes, unique constraints, check constraints, and foreign keys are named deterministically based on the table and column names.11 This eliminates a massive category of migration failures and ensures that the schema remains identical bit-for-bit across all environments.

### **Managing Migration Bloat: Squashing**

As an application matures over months and years, the alembic/versions directory can accumulate hundreds of individual migration files. This long history slows down the execution of CI pipelines and makes it exceedingly difficult to understand the current schema state.12 To mitigate this, migrations should be periodically squashed.13 Once a major version of the Fabrik platform reaches stability, the extensive history of incremental migrations should be replaced with a single, consolidated "baseline" migration that represents the complete, current state of the database.13 This practice dramatically reduces deployment times for new environments and minimizes cognitive overhead.

## **Transaction Boundaries and Concurrency Safety**

FastAPI’s architecture—built upon Starlette and utilizing the asyncio event loop—provides exceptional throughput for I/O-bound applications. However, integrating this asynchronous architecture with a relational database requires a fundamental understanding of transaction boundaries. A blocked event loop halts the entire application process, meaning that database connections must be managed with extreme precision.2

### **The Perils of Middleware Database Sessions**

A common, yet highly destructive, anti-pattern in FastAPI development is the instantiation of database sessions within global HTTP middleware.14 Middleware in FastAPI wraps the entire lifecycle of an HTTP request. It intercepts the request before it reaches the routing logic and intercepts the response before it is returned to the client.15

Opening a database transaction inside middleware means that the database connection is checked out from the pool and held open during the entire request lifecycle. This includes the time spent parsing JSON payloads, validating input via Pydantic, executing business logic, and serializing the final response.14 If the application performs any external network calls (e.g., calling a third-party API) while the middleware holds the database transaction open, the connection is effectively paralyzed. In a high-concurrency scenario, this leads to rapid connection pool exhaustion, causing the application to stall and reject new requests.2

### **Dependency Injection as the Transaction Boundary**

To enforce precise transaction boundaries, the Fabrik architecture mandates the use of FastAPI's Dependency Injection system (Depends) for providing database sessions to route handlers.14 Dependencies allow logic to be executed immediately before the specific route handler requires it, rather than globally for every request.14

By utilizing an asynchronous generator (the yield keyword) within a dependency function, the application can cleanly check out a session from the SQLAlchemy async\_sessionmaker, pass it to the route, and subsequently commit or rollback the transaction based on the execution result.18 This ensures that the database transaction is active for the absolute minimum duration required to execute the SQL statements, drastically improving the throughput and concurrency safety of the application.18

### **Asynchronous Session Safety: Expire on Commit**

When using SQLAlchemy 2.0 with the asyncpg driver, synchronous lazy-loading of relational attributes is mechanically impossible. If an application attempts to access a relationship that has not been loaded into memory, SQLAlchemy attempts to implicitly emit a new SQL query. In an asynchronous context, this implicit query lacks an await keyword, resulting in a fatal MissingGreenletException.20

By default, SQLAlchemy expires the attributes of an object immediately after a commit() operation, forcing a refresh on the next access.21 To prevent random exceptions throughout the application, the async\_sessionmaker must be explicitly configured with expire\_on\_commit=False.20 Furthermore, to avoid the notorious N+1 query problem, all required relational data must be explicitly loaded during the initial query using eager loading techniques such as selectinload or joinedload.21

## **Connection Pooling for VPS Deployments**

In a standard deployment, Uvicorn runs multiple worker processes to utilize the available CPU cores. If the server is configured with four workers, and each worker's SQLAlchemy instance maintains a connection pool of 10 persistent connections with an overflow of 20, the application could theoretically attempt to open 120 concurrent connections to the PostgreSQL database.16

### **Application-Level vs. Infrastructure-Level Pooling**

PostgreSQL is historically highly sensitive to the number of active connections. Each connection forks a new process in the operating system, consuming substantial memory. Default PostgreSQL installations on small VPS environments typically limit max\_connections to 100\.16 Exceeding this limit causes immediate application failure.

For initial deployments or low-traffic internal applications, application-level pooling via SQLAlchemy's QueuePool is sufficient. It is critical to enable pessimistic disconnect handling (pool\_pre\_ping=True) within the SQLAlchemy engine configuration. This instructs SQLAlchemy to emit a lightweight SELECT 1 query to verify the health of the connection before passing it to the application, gracefully recovering from dropped connections caused by VPS network fluctuations or database restarts.22

However, as the Fabrik platform scales or if background task workers (e.g., Celery or FastStream) are introduced, the multiplication effect of application-level connection pools will inevitably exhaust the database limits.16 At this inflection point, an external infrastructure-level connection pooler, specifically PgBouncer, must be deployed alongside the PostgreSQL container.16 PgBouncer sits between the application and the database, accepting thousands of lightweight client connections and multiplexing them over a small, fixed number of heavy database connections.22 When PgBouncer is active (configured in transaction-pooling mode), the FastAPI application must switch its SQLAlchemy configuration to NullPool. This disables the internal SQLAlchemy pool, preventing the application from hoarding connections and allowing PgBouncer to manage the connection lifecycle optimally.22

## **Data Integrity, Nullability, and Foreign Key Policy**

A database that relies entirely on the application layer to enforce data integrity is fundamentally fragile. Application code contains bugs, race conditions occur, and direct database access for maintenance or reporting bypasses application-level validation entirely. Therefore, the Fabrik architecture dictates that the database schema itself must aggressively reject invalid states.

### **The "NOT NULL by Default" Discipline**

The concept of NULL in SQL represents the absence of a value, or an "unknown" state. Allowing NULL values indiscriminately leads to complex querying logic involving IS NULL checks and unpredictable results when utilizing COUNT or aggregation functions.

The canonical rule for the Fabrik platform is that all database columns must be declared as NOT NULL by default.24 Nullability is only permitted when the absence of a value explicitly represents a discrete, mathematically logical business state (e.g., a canceled\_at timestamp where NULL implies the entity is active). If a field semantically requires a default baseline, the DEFAULT constraint must be applied at the database schema level, not merely in the SQLAlchemy model instantiation.24

### **Constraint Enforcement**

Pydantic validation within FastAPI is excellent for API sanitation and providing descriptive error messages to the client, but it cannot prevent race conditions. For example, ensuring that an integer column representing a monetary balance never drops below zero must be enforced by a PostgreSQL CHECK constraint (e.g., CHECK (balance \>= 0)).25

Similarly, relational integrity must be enforced via Foreign Keys. A Foreign Key policy must explicitly define the behavior upon deletion of the parent record. Relying on default behaviors is discouraged. Developers must explicitly define ON DELETE CASCADE (if the child record cannot logically exist without the parent) or ON DELETE RESTRICT (to explicitly prevent the deletion of a parent if children exist, protecting the audit trail).25

## **The Soft Delete Illusion and Data Retention**

A pervasive pattern in modern software development is the "soft delete," typically implemented by adding a deleted\_at timestamp or an is\_deleted boolean to a table.26 When a user requests the deletion of a record, the application merely updates this flag instead of issuing a true DELETE command. While this seems to offer a safety net against accidental data loss, it introduces a cascade of severe architectural liabilities.

### **The Consequences of Soft Deletes**

Soft deletes create an illusion that actively works against the database's relational design.26 The primary consequence is the proliferation of "leaky queries." Every single SELECT, JOIN, and aggregation query written across the entire application must explicitly remember to append WHERE deleted\_at IS NULL.26 If a developer forgets this clause in a complex report or a nested subquery, deleted data silently leaks into the active application state.

Furthermore, soft deletes destroy the utility of unique constraints.26 If a user deletes their account and later attempts to re-register with the same email address, the database will throw a unique constraint violation because the "deleted" row still occupies that email address in the index. Workarounds require complex partial unique indexes (e.g., CREATE UNIQUE INDEX ON users (email) WHERE deleted\_at IS NULL), which complicate migrations and increase maintenance overhead.26 Finally, soft deletes only track the final moment of deletion; they provide no historical audit trail of how the record was updated prior to its deletion.26

### **The Journal Table Imperative**

For the Fabrik platform, soft deletes are strictly banned. If data retention, compliance, or auditability is required, the architecture mandates the use of Journal Tables (also known as shadow tables or audit logs).26

Under this paradigm, the application issues true DELETE and UPDATE commands, keeping the primary table strictly lean and containing only active data.26 A PostgreSQL row-level trigger is attached to the primary table. Upon any modification, the trigger automatically captures the OLD and NEW state of the row and inserts it into an append-only \[table\_name\]\_journal table, often serializing the payload into a JSONB column to elegantly handle future schema changes.26 This provides a perfect, immutable audit trail without poisoning the active application logic or polluting current-state queries.26

## **Primary Key Generation and B-Tree Locality**

The selection of a primary key strategy is one of the most consequential decisions in database design, directly dictating the performance of data ingestion and index maintenance at scale.

### **The Liability of UUIDv4**

Serial integer primary keys (e.g., SERIAL or BIGSERIAL) are highly efficient but problematic for distributed systems and RESTful APIs, as they expose the total volume of records to external observers. To obscure this data, developers frequently turn to Universally Unique Identifiers (UUIDs), specifically UUIDv4.28

However, UUIDv4 is generated using pure cryptographic randomness. PostgreSQL stores primary key indexes using B-tree data structures, which are optimized for sequential ordering. When inserting a completely random UUIDv4, PostgreSQL must traverse the B-tree to find the correct, randomized leaf node to insert the new data.29 As the table grows, this causes massive fragmentation. The database must constantly load different, random index pages from disk into the shared\_buffers cache, evicting other useful data.28 Furthermore, when an index page becomes full, PostgreSQL must perform an expensive "page split." This random insertion pattern generates up to 20 times more Write-Ahead Log (WAL) volume compared to sequential inserts, drastically reducing the throughput of bulk data loads and increasing disk wear on the VPS.28

### **The UUIDv7 Solution**

To resolve the conflict between security and performance, the Fabrik platform mandates the use of UUIDv7 for all primary keys.29 The UUIDv7 standard begins with a 48-bit Unix timestamp representing the exact millisecond of creation, followed by random data to ensure uniqueness.30

Because the leading bits are time-ordered, UUIDv7 identifiers naturally sort chronologically. This ensures that new records are consistently inserted at the right-most edge of the PostgreSQL B-tree.29 This sequential insertion pattern eliminates unnecessary page splits, maximizes cache hits within shared\_buffers, and significantly reduces WAL generation, matching the performance of legacy integer keys while maintaining the decentralized benefits of a UUID.28

While native uuidv7() generation is introduced in PostgreSQL 18, the Fabrik platform running on PostgreSQL 16 must generate these identifiers at the application layer. The Python application must utilize a standard library (such as uuid\_utils) to generate the UUIDv7 before committing the transaction to the database.30

## **JSONB Usage Boundaries and TOAST Mechanics**

The introduction of the JSONB data type transformed PostgreSQL, allowing it to compete directly with NoSQL document stores by natively supporting unstructured data.33 However, the overuse of JSONB as a substitute for disciplined relational schema design is a severe anti-pattern that leads to hidden performance degradation.

### **The Mechanics of TOAST**

PostgreSQL stores data in fixed-size pages, strictly limited to 8 Kilobytes.34 Ordinarily, all attributes of a single row must fit within this 8KB page. When a developer stores a massive, nested JSONB document within a column, it frequently exceeds this physical limit.

To accommodate this, PostgreSQL utilizes The Oversized-Attribute Storage Technique (TOAST).34 When a value exceeds the page size, PostgreSQL quietly cuts the JSONB document into smaller chunks, moves it to a hidden side-table, and leaves a small pointer in the primary row.34 While this abstraction is convenient, it carries a heavy latency penalty. Querying a TOASTed JSONB column requires the database to perform additional disk I/O to fetch and reassemble the chunks from the side-table.34 Overuse of JSONB ensures that the database spends disproportionate resources on reassembly rather than efficient querying.

### **The Collapse of Query Statistics**

The second major penalty of JSONB lies in the PostgreSQL query planner. For traditional relational columns (integers, text, timestamps), the database automatically maintains sophisticated statistical histograms, tracking the most common values, null fractions, and data distribution.35 When a query is executed, the planner uses these statistics to determine whether an index scan or a sequential scan is the fastest execution path.

The query planner cannot maintain granular statistical histograms for deeply nested, dynamic keys within a JSONB document.35 Consequently, when an application heavily filters, sorts, or joins data based on values buried inside a JSONB column, the query planner is flying blind. It frequently defaults to highly inefficient execution plans, resulting in full-table sequential scans that bring application performance to a halt.35

Therefore, the boundary rule for JSONB is strict: It must only be used for highly sparse data, unpredictable third-party API payloads, or flexible user-defined settings that are rarely used in WHERE or ORDER BY clauses.25 If a specific attribute inside a JSONB document becomes a common filter criteria, it must be extracted and normalized into a dedicated, strictly-typed relational column.37

## **Indexing Strategy and Automated Maintenance**

Indexes are fundamentally a cache, and like all caches, they represent a tradeoff between read acceleration and write degradation.38 Every INSERT, UPDATE, or DELETE executed against a table requires the database to synchronously update all associated indexes.39

A common fallacy among developers is to preemptively index every column that might conceivably be queried. This "over-indexing" strategy drastically slows down write operations, inflates the storage footprint, and wastes valuable RAM within the shared\_buffers cache.39

### **Strategic Indexing**

The indexing strategy must be deliberate and reactive. Primary keys and Foreign keys must always be indexed to facilitate efficient relational joins.25 Beyond that, indexes should only be created when a specific, slow query path has been identified via application profiling.

When dealing with highly skewed data, Partial Indexes should be utilized.39 For example, in a system processing millions of background jobs, querying for the few jobs that have a status of 'FAILED' using a standard index is inefficient. Creating a partial index (CREATE INDEX idx\_failed\_jobs ON jobs (id) WHERE status \= 'FAILED') creates a tiny, highly efficient index that consumes negligible memory while instantly resolving the query.39

Finally, index maintenance must be automated. The pg\_stat\_user\_indexes system view provides exact metrics on how often an index is actually used (idx\_scan). Any index that accumulates zero or extremely low scans over a significant period is dead weight and must be dropped.40

## ---

**Output Requirements**

The following sections define the explicit operational boundaries, automated enforcement checks, and the final Markdown rule file required for the Fabrik platform.

### **Canonical Rules for the Fabrik Data Architecture**

* **Alembic Exclusivity:** All schema modifications, without exception, must be executed via Alembic migrations. Direct execution of raw SQL DDL is prohibited.
* **UUIDv7 Primacy:** All primary keys must utilize the time-sorted UUIDv7 standard to guarantee B-tree locality and prevent write-amplification. UUIDv4 is banned.
* **Dependency-Injected Transactions:** Database AsyncSession objects must be strictly scoped to FastAPI route handlers via Depends(). Middleware-based session management is prohibited.
* **Expire on Commit Disabled:** SQLAlchemy async\_sessionmaker must be explicitly configured with expire\_on\_commit=False to prevent asynchronous lazy-loading exceptions.
* **Hard Deletes Only:** The use of deleted\_at or is\_deleted flags is forbidden. Implement hard deletes, utilizing PostgreSQL trigger-based Journal tables if historical auditability is required.
* **NOT NULL Default:** All columns must default to NOT NULL. Nullability is only permitted when the absence of a value mathematically represents a distinct business state.
* **JSONB Boundary:** JSONB is restricted to sparse, schema-less, or third-party payload data. Any attribute used frequently in a WHERE or ORDER BY clause must be extracted to a standard relational column.
* **Pessimistic Pooling:** Application-level connection pools (QueuePool) must implement pool\_pre\_ping=True to gracefully recover from stale connections on the VPS.
* **Deterministic Constraint Naming:** SQLAlchemy MetaData must be initialized with a comprehensive naming convention dictionary to ensure deterministic Alembic migration execution across environments.

### **Anti-Patterns and Banned Practices**

| Anti-Pattern | Justification for Ban | Mandatory Alternative |
| :---- | :---- | :---- |
| **Soft Deletes (deleted\_at)** | Causes pervasive leaky queries, destroys unique constraints, and forces full-table scans if partial indexes are omitted.26 | Hard deletes. If tracking is needed, use trigger-based append-only Journal/Audit Tables.26 |
| **UUIDv4 Primary Keys** | Destroys B-tree index locality. Causes massive page splitting, cache thrashing, and extreme WAL volume amplification.28 | UUIDv7, generated at the Python application layer, ensuring time-sequential database inserts.30 |
| **Middleware DB Sessions** | Keeps transactions active during HTTP serialization and network I/O, leading rapidly to connection pool exhaustion.14 | FastAPI Depends() yielding an AsyncSession scoped exactly to the execution of the route handler.14 |
| **Alpine Linux Base Images** | Alpine uses musl libc, causing compilation failures, slow builds, and obscure runtime bugs with Python Postgres C-extension drivers.1 | debian:slim-bookworm (e.g., python:3.12-slim-bookworm) to utilize standard glibc pre-compiled wheels. |
| **Raw SQL Schema Edits** | Bypasses version control entirely, leading to catastrophic schema drift between WSL dev environments and the ARM64 VPS.8 | All schema changes must be declared in SQLAlchemy models and generated via Alembic.9 |
| **Over-Indexing** | Each index dramatically slows down INSERT, UPDATE, and DELETE operations, while consuming RAM in shared\_buffers.39 | Index only highly utilized query paths. Rely on Partial Indexes and monitor pg\_stat\_user\_indexes.39 |

### **What to Enforce in Execute Handoffs**

When an autonomous agent completes a task and prepares a handoff summary for the solo developer or a subsequent agent, the following verifications must be explicitly documented in the handoff log:

| Handoff Checkpoint | Required Verification Data |
| :---- | :---- |
| **Migration Review** | Confirmation that alembic revision \--autogenerate was run, and the output was manually reviewed to verify that no unintended column drops or renaming errors occurred. |
| **Nullability & Foreign Keys** | Explicit documentation of any new columns, confirming that NOT NULL constraints were applied and that ON DELETE cascading behaviors were deliberately selected for Foreign Keys. |
| **Index Justification** | If an index was created, the handoff must include the specific SQL query pattern it optimizes. |
| **Transaction Boundaries** | Confirmation that any new database interaction utilizes the Depends(get\_db) injection pattern and does not rely on global session state. |

### **What to Verify in final\_gate.py**

The final\_gate.py script serves as the absolute, non-negotiable CI/CD blockade for the Fabrik platform. It must contain objective, mechanically parseable checks that instantly fail the build if violated.

| Mechanical Verification | Parsing Strategy |
| :---- | :---- |
| **Base Image Compliance** | Regex parsing of all Dockerfile assets to assert FROM python:.\*-slim-bookworm is present and the string alpine is entirely absent. |
| **Alembic DAG Integrity** | Execution of alembic heads to ensure there are no branching or split-head migration states before deployment.41 |
| **Middleware Session Ban** | Python Abstract Syntax Tree (AST) parsing of main.py and router files to ensure AsyncSession or related imports are never utilized within a @app.middleware block. |
| **UUIDv4 Ban** | Regex search across all SQLAlchemy models and utility directories for uuid4(), forcing failure if found, requiring uuid7() instead. |
| **Soft Delete Ban** | AST and Regex parsing of SQLAlchemy models to fail if columns named deleted\_at, is\_deleted, or deleted are defined on declarative bases. |

### **What Belongs in AGENTS.md / AGENTS-compact.md**

These instruction files provide the continuous system prompt context for LLM agents working within the repository. They must concisely and forcefully convey the operational boundaries of the Fabrik stack to prevent LLM hallucination of standard (but banned) practices.

* **Identity & Scope:** "You are an expert Python/PostgreSQL systems architect. You prioritize low-maintenance, highly durable, and highly deterministic solutions. You are operating under strict resource constraints on an ARM64 VPS."
* **The Unbreakable Rules:**
  * "NEVER use Alpine Linux base images. Only use slim-bookworm."
  * "NEVER implement soft deletes (deleted\_at). Use hard deletes. If tracking is required, implement trigger-based journal tables."
  * "NEVER use UUIDv4 for primary keys due to B-tree fragmentation. Always use UUIDv7 generated via uuid\_utils in Python."
  * "NEVER execute raw SQL DDL. All schema evolution must pass through Alembic."
  * "NEVER manage database sessions inside FastAPI middleware. Always use Depends() injection for route scoping."
* **Data Discipline:** "Use JSONB strictly for sparse, unstructured, or third-party payload data. Normalize all heavily filtered attributes. Default to NOT NULL for all new columns."

### **Minimal Practical Examples for the Fabrik Stack**

To ensure exact architectural compliance, the following code patterns dictate the mechanical implementation of the rules discussed above.

#### **A. Centralized Naming Convention**

This configuration ensures Alembic generates deterministic, named constraints, preventing migration drift and crashes across environments.11

Python

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

\# Enforce strict naming conventions for all database constraints
POSTGRES\_INDEXES\_NAMING\_CONVENTION \= {
    "ix": "ix\_%(column\_0\_label)s",
    "uq": "uq\_%(table\_name)s\_%(column\_0\_name)s",
    "ck": "ck\_%(table\_name)s\_%(constraint\_name)s",
    "fk": "fk\_%(table\_name)s\_%(column\_0\_name)s\_%(referred\_table\_name)s",
    "pk": "pk\_%(table\_name)s",
}

class Base(DeclarativeBase):
    metadata \= MetaData(naming\_convention=POSTGRES\_INDEXES\_NAMING\_CONVENTION)

#### **B. UUIDv7 Generation and Model Application**

Because native uuidv7() generation is not available until PostgreSQL 18, the Python application must generate it using a standardized library.30

Python

import uuid\_utils
from sqlalchemy import UUID
from sqlalchemy.orm import Mapped, mapped\_column
from datetime import datetime, UTC
from.database import Base

def generate\_uuidv7() \-\> uuid\_utils.UUID:
    return uuid\_utils.uuid7()

class User(Base):
    \_\_tablename\_\_ \= "users"

    \# UUIDv7 ensures strict B-Tree locality and fast sequential inserts
    id: Mapped \= mapped\_column(
        UUID(as\_uuid=True),
        primary\_key=True,
        default=generate\_uuidv7
    )
    email: Mapped\[str\] \= mapped\_column(unique=True, index=True, nullable=False)
    created\_at: Mapped\[datetime\] \= mapped\_column(default=lambda: datetime.now(UTC))

    \# Notice: NO deleted\_at column is present. Soft deletes are strictly banned.

#### **C. Async SQLAlchemy Session and FastAPI Dependency Injection**

This pattern guarantees that transactions are isolated exclusively to the route handler lifecycle and that lazy-loading exceptions are mitigated via expire\_on\_commit=False.19

Python

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create\_async\_engine, async\_sessionmaker, AsyncSession
from fastapi import Depends, FastAPI

DATABASE\_URL \= "postgresql+asyncpg://user:password@localhost/fabrik"

engine \= create\_async\_engine(
    DATABASE\_URL,
    pool\_pre\_ping=True,  \# Pessimistic disconnect handling for VPS stability
    pool\_size=10,        \# Conservative pool size
    max\_overflow=20,
)

\# expire\_on\_commit=False is strictly required for AsyncSession usage
AsyncSessionLocal \= async\_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire\_on\_commit=False,
    class\_=AsyncSession
)

async def get\_db() \-\> AsyncGenerator:
    """Dependency for providing a safely scoped, transactional database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

app \= FastAPI()

@app.post("/users/")
async def create\_user(user\_data: dict, db: AsyncSession \= Depends(get\_db)):
    \# Business logic executes here.
    \# The transaction is managed safely and deterministically by the dependency generator.
    pass

### **Recommended Final Content for Rule File**

The following markdown represents the finalized output to be saved permanently as 25-data-postgres.md within the Fabrik repository. It strips away the exhaustive rationale provided in this report and presents the actionable, mechanical rules required for immediate execution by autonomous agents.

# **Rule File: Postgres & Data Architecture (25-data-postgres.md)**

**Context**: Fabrik is deployed on an ARM64 Ubuntu VPS (Coolify). The stack consists of FastAPI, async SQLAlchemy 2.0, Alembic, and PostgreSQL 16\. All optimizations target a low-maintenance, high-durability, and solo-developer operational profile.

## **1\. Core Architecture Directives**

* **Base Images**: Strictly use slim-bookworm for Python and Node containers. **Never** use Alpine Linux, as the musl libc implementation causes catastrophic build and runtime failures with Python Postgres C-extensions (asyncpg, psycopg) on ARM64 architectures.
* **Alembic is Absolute**: Schema changes occur exclusively via Alembic migrations. Manual SQL DDL is forbidden. Do not blindly trust \--autogenerate; you must manually verify relationships, column drops, and ENUM alterations before execution.
* **Naming Conventions**: SQLAlchemy MetaData must be instantiated with a comprehensive naming convention dictionary (ix, uq, ck, fk, pk) to ensure deterministic Alembic constraint migrations across all environments.

## **2\. Model & Schema Rules**

* **Primary Keys**: Always use UUIDv7 for primary keys. UUIDv4 is completely banned due to B-tree fragmentation, cache eviction, and excessive WAL generation. Generate UUIDv7 in Python (uuid\_utils.uuid7()) and pass it to SQLAlchemy's UUID type.
* **Nullability**: All columns must be NOT NULL by default. NULL is only permitted if the absolute absence of data explicitly represents a discrete, mathematically sound business state.
* **Soft Deletes are Banned**: Never use deleted\_at columns. They leak data in queries, ruin unique constraints, and bloat indexes. Use strict hard deletes. If historical audit history is required, implement append-only Journal tables via Postgres row-level triggers.
* **JSONB Boundaries**: Use JSONB exclusively for highly sparse, schema-less, or 3rd-party payload data. If a field is frequently used in WHERE, JOIN, or ORDER BY clauses, it must be extracted into a strictly typed relational column to prevent TOAST table performance degradation and query planner statistics failures.

## **3\. Transactions & Concurrency**

* **Transaction Boundaries**: Database sessions must be strictly scoped to the HTTP request via FastAPI Depends(). **Never** open a database session or transaction within a global FastAPI middleware block, as this exhausts connection pools during network serialization and payload validation.
* **Async Session Configuration**: async\_sessionmaker must explicitly declare expire\_on\_commit=False to prevent MissingGreenletException during asynchronous property access.
* **Connection Pooling**: Use SQLAlchemy QueuePool with pool\_pre\_ping=True for local and early-stage deployments. When the application scales to require PgBouncer on the VPS, switch SQLAlchemy to NullPool.

## **4\. Indexing Discipline**

* Index Foreign Keys and highly filtered fields. Do not preemptively index every column; write operations bear the penalty of every existing index.
* Utilize Partial Indexes (e.g., WHERE is\_active \= true) for heavily skewed boolean queries to preserve RAM and maximize cache hit ratios.
* Use pg\_stat\_user\_indexes periodically to identify and drop unused indexes (idx\_scan \= 0).

## **5\. CI/CD & Final Gate Enforcement**

* The final\_gate.py script must mechanically enforce:
  1. Rejection of any Dockerfile containing alpine.
  2. Rejection of uuid4 anywhere in the codebase.
  3. Rejection of deleted\_at or is\_deleted column declarations.
  4. Abstract Syntax Tree (AST) checks verifying AsyncSession is absent from any @app.middleware definitions.

#### **Works cited**

1. FastAPI with SQLAlchemy, PostgreSQL and Alembic | by Hasan Mahir Ateş | Medium, accessed March 31, 2026, [https://medium.com/@hasanmahira/fastapi-with-sqlalchemy-postgresql-and-alembic-1ccaba79572e](https://medium.com/@hasanmahira/fastapi-with-sqlalchemy-postgresql-and-alembic-1ccaba79572e)
2. How to properly set pool\_size (and max\_overflow) in SQLAlchemy for ASGI app, accessed March 31, 2026, [https://stackoverflow.com/questions/72543167/how-to-properly-set-pool-size-and-max-overflow-in-sqlalchemy-for-asgi-app](https://stackoverflow.com/questions/72543167/how-to-properly-set-pool-size-and-max-overflow-in-sqlalchemy-for-asgi-app)
3. Documentation: 16: E.14. Release 16 \- PostgreSQL, accessed March 31, 2026, [https://www.postgresql.org/docs/16/release-16.html](https://www.postgresql.org/docs/16/release-16.html)
4. PostgreSQL Updates: 2020-2024 | Features & Upgrade Tips \- Aiven, accessed March 31, 2026, [https://aiven.io/blog/whats-new-with-postgresql-and-why-its-still-your-go-to-database](https://aiven.io/blog/whats-new-with-postgresql-and-why-its-still-your-go-to-database)
5. Synopsis of several compelling features in PostgreSQL 16 | AWS Database Blog, accessed March 31, 2026, [https://aws.amazon.com/blogs/database/synopsis-of-several-compelling-features-in-postgresql-16/](https://aws.amazon.com/blogs/database/synopsis-of-several-compelling-features-in-postgresql-16/)
6. PostgreSQL Configurations Every Senior Developer Should Know | by Harshith \- Medium, accessed March 31, 2026, [https://medium.com/@harshithgowdakt/postgresql-configurations-every-senior-developer-should-know-12c2ff357db3](https://medium.com/@harshithgowdakt/postgresql-configurations-every-senior-developer-should-know-12c2ff357db3)
7. PostgreSQL 16 Maintenance Essentials | PDF | Postgre Sql | Database Index \- Scribd, accessed March 31, 2026, [https://www.scribd.com/document/931370092/PostgreSQL-16-Maintenance-Guide](https://www.scribd.com/document/931370092/PostgreSQL-16-Maintenance-Guide)
8. Database Migrations : r/Python \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1q7ixsf/database\_migrations/](https://www.reddit.com/r/Python/comments/1q7ixsf/database_migrations/)
9. How to Handle Database Migrations with Alembic \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2025-07-02-python-alembic-migrations/view](https://oneuptime.com/blog/post/2025-07-02-python-alembic-migrations/view)
10. Database Migrations with Python: Why Alembic \+ SQLModel is the Perfect Combo, accessed March 31, 2026, [https://www.amitavroy.com/articles/database-migrations-with-python-why-alembic-sqlmodel-is-the-perfect-combo](https://www.amitavroy.com/articles/database-migrations-with-python-why-alembic-sqlmodel-is-the-perfect-combo)
11. The Importance of Naming Constraints — Alembic 1.18.4 documentation \- SQLAlchemy, accessed March 31, 2026, [https://alembic.sqlalchemy.org/en/latest/naming.html](https://alembic.sqlalchemy.org/en/latest/naming.html)
12. DB Migrations \- when to stop : r/Backend \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Backend/comments/1rn6vg5/db\_migrations\_when\_to\_stop/](https://www.reddit.com/r/Backend/comments/1rn6vg5/db_migrations_when_to_stop/)
13. Squashing a history of migrations. · sqlalchemy alembic · Discussion \#1572 \- GitHub, accessed March 31, 2026, [https://github.com/sqlalchemy/alembic/discussions/1572](https://github.com/sqlalchemy/alembic/discussions/1572)
14. Depends or Middleware : r/FastAPI \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1pgdbeu/depends\_or\_middleware/](https://www.reddit.com/r/FastAPI/comments/1pgdbeu/depends_or_middleware/)
15. Middleware \- FastAPI, accessed March 31, 2026, [https://fastapi.tiangolo.com/tutorial/middleware/](https://fastapi.tiangolo.com/tutorial/middleware/)
16. Scaling Database Connections: From SQLAlchemy Pools to PGBouncer in a Production URL Shortener | by Sultan Mahmud | Medium, accessed March 31, 2026, [https://medium.com/@kazisultanmahmud/scaling-database-connections-from-sqlalchemy-pools-to-pgbouncer-in-a-production-url-shortener-03b780a9467a](https://medium.com/@kazisultanmahmud/scaling-database-connections-from-sqlalchemy-pools-to-pgbouncer-in-a-production-url-shortener-03b780a9467a)
17. FastAPI dependency vs middleware \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/66632841/fastapi-dependency-vs-middleware](https://stackoverflow.com/questions/66632841/fastapi-dependency-vs-middleware)
18. Help me figure out transactions in FastAPI \- where should I commit? \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1o1xe46/help\_me\_figure\_out\_transactions\_in\_fastapi\_where/](https://www.reddit.com/r/FastAPI/comments/1o1xe46/help_me_figure_out_transactions_in_fastapi_where/)
19. \[Python\] How to implement a transactional decorator in FastAPI \+ SQLAlchemy \- with reviewing other approaches \- DEV Community, accessed March 31, 2026, [https://dev.to/uponthesky/python-post-reviewhow-to-implement-a-transactional-decorator-in-fastapi-sqlalchemy-ein](https://dev.to/uponthesky/python-post-reviewhow-to-implement-a-transactional-decorator-in-fastapi-sqlalchemy-ein)
20. Setting up a FastAPI App with Async SQLALchemy 2.0 & Pydantic V2 \- Medium, accessed March 31, 2026, [https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308)
21. How to Use SQLAlchemy with FastAPI \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-27-sqlalchemy-fastapi/view](https://oneuptime.com/blog/post/2026-01-27-sqlalchemy-fastapi/view)
22. SQLAlchemy Pooling for Serverless FastAPI: QueuePool vs. NullPool \- David Muraya, accessed March 31, 2026, [https://davidmuraya.com/blog/sqlalchemy-connection-pooling-for-serverless-fastapi/](https://davidmuraya.com/blog/sqlalchemy-connection-pooling-for-serverless-fastapi/)
23. How to best use connection pooling in SQLAlchemy for PgBouncer transaction-level pooling? \- Database Administrators Stack Exchange, accessed March 31, 2026, [https://dba.stackexchange.com/questions/36828/how-to-best-use-connection-pooling-in-sqlalchemy-for-pgbouncer-transaction-level](https://dba.stackexchange.com/questions/36828/how-to-best-use-connection-pooling-in-sqlalchemy-for-pgbouncer-transaction-level)
24. PostgreSQL Convention 2024 · Vonng, accessed March 31, 2026, [https://vonng.com/en/pg/pg-convention/](https://vonng.com/en/pg/pg-convention/)
25. PostgreSQL Best Practices for Production: Indexing, JSONB, UUIDv7, Partitioning, and Performance Tuning | Medium, accessed March 31, 2026, [https://medium.com/@pothiq/postgresql-in-production-a-beginner-to-pro-guide-82db452ffc88](https://medium.com/@pothiq/postgresql-in-production-a-beginner-to-pro-guide-82db452ffc88)
26. Soft deletes vs. Journal tables in PostgreSQL — why I chose ..., accessed March 31, 2026, [https://levelup.gitconnected.com/soft-deletes-vs-journal-tables-in-postgresql-why-i-chose-journaling-and-how-i-automated-it-74fb3c9857d7](https://levelup.gitconnected.com/soft-deletes-vs-journal-tables-in-postgresql-why-i-chose-journaling-and-how-i-automated-it-74fb3c9857d7)
27. Understanding Soft Delete and Hard Delete in Software Development: Best Practices and Importance | by Suraj Singh Bisht, accessed March 31, 2026, [https://surajsinghbisht054.medium.com/understanding-soft-delete-and-hard-delete-in-software-development-best-practices-and-importance-539a935d71b5](https://surajsinghbisht054.medium.com/understanding-soft-delete-and-hard-delete-in-software-development-best-practices-and-importance-539a935d71b5)
28. PostgreSQL UUID: Bulk insert with UUIDv7 vs UUIDv4 \- DEV Community, accessed March 31, 2026, [https://dev.to/aws-heroes/postgresql-uuid-bulk-insert-with-uuidv7-vs-uuidv4-4oca](https://dev.to/aws-heroes/postgresql-uuid-bulk-insert-with-uuidv7-vs-uuidv4-4oca)
29. UUIDv4 vs UUIDv7 in PostgreSQL \- DEV Community, accessed March 31, 2026, [https://dev.to/fazal\_mansuri\_/uuidv4-vs-uuidv7-in-postgresql-2m0l](https://dev.to/fazal_mansuri_/uuidv4-vs-uuidv7-in-postgresql-2m0l)
30. PostgreSQL UUIDv7 Performance Benchmark: Native vs Custom Implementations, accessed March 31, 2026, [https://www.saybackend.com/blog/uuidv7-postgres-comparison/](https://www.saybackend.com/blog/uuidv7-postgres-comparison/)
31. UUIDv7 Comes to PostgreSQL 18 \- Nile Postgres, accessed March 31, 2026, [https://www.thenile.dev/blog/uuidv7](https://www.thenile.dev/blog/uuidv7)
32. UUIDv7 in postgresql : r/SQL \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/SQL/comments/1e8s4ry/uuidv7\_in\_postgresql/](https://www.reddit.com/r/SQL/comments/1e8s4ry/uuidv7_in_postgresql/)
33. JSON vs. JSONB in PostgreSQL: A Complete Comparison \- DbVisualizer, accessed March 31, 2026, [https://www.dbvis.com/thetable/json-vs-jsonb-in-postgresql-a-complete-comparison/](https://www.dbvis.com/thetable/json-vs-jsonb-in-postgresql-a-complete-comparison/)
34. Postgres JSONB Columns and TOAST: A Performance Guide, accessed March 31, 2026, [https://www.snowflake.com/en/engineering-blog/postgres-jsonb-columns-and-toast/](https://www.snowflake.com/en/engineering-blog/postgres-jsonb-columns-and-toast/)
35. When To Avoid JSONB In A PostgreSQL Schema \- Heap.io, accessed March 31, 2026, [https://www.heap.io/blog/when-to-avoid-jsonb-in-a-postgresql-schema](https://www.heap.io/blog/when-to-avoid-jsonb-in-a-postgresql-schema)
36. When to use JSONB vs. separate columns : r/PostgreSQL \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/PostgreSQL/comments/mop9ju/when\_to\_use\_jsonb\_vs\_separate\_columns/](https://www.reddit.com/r/PostgreSQL/comments/mop9ju/when_to_use_jsonb_vs_separate_columns/)
37. Postgres jsonb column or standard normalized table? \- Database Administrators Stack Exchange, accessed March 31, 2026, [https://dba.stackexchange.com/questions/221955/postgres-jsonb-column-or-standard-normalized-table](https://dba.stackexchange.com/questions/221955/postgres-jsonb-column-or-standard-normalized-table)
38. An automatic indexing system for Postgres: How we built the pganalyze Indexing Engine, accessed March 31, 2026, [https://pganalyze.com/blog/automatic-indexing-system-postgres-pganalyze-indexing-engine](https://pganalyze.com/blog/automatic-indexing-system-postgres-pganalyze-indexing-engine)
39. Golden Rules for PostgreSQL Indexing Best Practices \- Backup Education, accessed March 31, 2026, [https://backup.education/showthread.php?tid=8912](https://backup.education/showthread.php?tid=8912)
40. PostgreSQL Performance: Essential Indexing Guidelines \- DEV Community, accessed March 31, 2026, [https://dev.to/shrsv/postgresql-performance-essential-indexing-guidelines-1i90](https://dev.to/shrsv/postgresql-performance-essential-indexing-guidelines-1i90)
41. Handling multiple Alembic migrations with a full team of developers? : r/Python \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1p7api3/handling\_multiple\_alembic\_migrations\_with\_a\_full/](https://www.reddit.com/r/Python/comments/1p7api3/handling_multiple_alembic_migrations_with_a_full/)
