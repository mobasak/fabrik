# **15-api-contracts.md**

## **1\. Executive Summary**

The architectural longevity of a solo-developer platform hinges on the absolute rigidity of its systemic boundaries and the automated enforcement of its operational contracts. For Fabrik—operating within a highly constrained budget, a strict allowance of approximately 50 focused development hours weekly, and an infrastructure stack comprising a local Windows Subsystem for Linux (WSL) Ubuntu 24.04 environment and a production ARM64 Ubuntu Virtual Private Server (VPS) managed via Coolify—the Application Programming Interface (API) contract represents the primary defense against technical debt, developmental regression, and deployment paralysis. The overarching objective of this research report is to establish an API contract discipline that drastically minimizes operational overhead, leverages standard durable technologies, and remains immune to ephemeral, high-maintenance industry trends over the 2025–2026 horizon.

This document serves as the foundational basis for the permanent rule file (15-api-contracts.md) governing Artificial Intelligence (AI) agents interacting with the Fabrik stack. It dictates an architecture where the OpenAPI specification is generated deterministically via code-first implementation utilizing Python 3.12, FastAPI, and Pydantic, but is subsequently treated as an immutable, cryptographically strict contract across the entire multi-client ecosystem. This ecosystem includes a Next.js 14 web application using TypeScript and Tailwind, a React Native mobile application, and a Chrome Manifest V3 extension. The investigation synthesizes broadly adopted practices, mandating cursor-based pagination to mitigate PostgreSQL 16 Multi-Version Concurrency Control (MVCC) performance degradation 1, enforcing RFC 7807 for universal error schema standardization to eliminate client-side parsing ambiguities 3, and instituting uncompromising idempotency protocols backed by Redis for all mutative operations to survive unreliable mobile networks.5

Furthermore, this report standardizes parameter casing via automated Pydantic serialization boundaries, completely removing the need for manual dictionary mapping.7 It enforces automated breaking-change detection in Continuous Integration (CI) pipelines via tools such as oasdiff and Spectral.8 By shifting the burden of contract verification entirely to the final\_gate.py deployment script, the prescribed architecture ensures that the solo developer can maintain an aggressive feature velocity without sacrificing the stability of the platform. The resulting blueprint is a "Code-Driven, Contract-Enforced" paradigm that entirely isolates the backend business logic from the idiosyncratic demands of disparate frontend clients.

## **The Contract Paradigm: OpenAPI as the Definitive Boundary**

Historically, the software engineering industry has oscillated between "design-first" and "code-first" API methodologies.11 The design-first approach, which necessitates authoring exhaustive OpenAPI YAML specifications prior to writing any execution logic, guarantees platform consistency but introduces an unacceptable metabolic tax on developer velocity. For a solo developer operating within a 50-hour weekly constraint, manually synchronizing a YAML specification with a rapidly evolving Python codebase represents an unsustainable duplication of effort. Conversely, pure code-first approaches frequently result in "API drift," a phenomenon where undocumented, incremental changes to internal models silently cascade into the HTTP transport layer, thereby breaking downstream consumers without triggering pre-deployment warnings.12

The optimized synthesis for the Fabrik stack relies on treating FastAPI and Pydantic as the absolute authoritative source of truth during the design phase.14 The developer models the domain logic using heavily annotated Pydantic models. Uvicorn, the underlying Asynchronous Server Gateway Interface (ASGI) server, automatically generates the openapi.json artifact dynamically at runtime based on these models. However, the critical paradigm shift occurs immediately post-generation: once the openapi.json artifact is exported and committed to the repository, it transitions from a dynamic output to an immutable contractual boundary.

Downstream, this specification is consumed by deterministic code generators, specifically utilizing modern tooling such as @hey-api/openapi-ts, to programmatically construct strongly typed TypeScript client software development kits (SDKs).15 These SDKs are subsequently imported into the Next.js 14 web application, the React Native mobile application, and the Manifest V3 Chrome extension. If a backend modification inadvertently alters the OpenAPI schema in a manner that introduces a backward-incompatible breaking change, the deployment pipeline—specifically the final\_gate.py pre-flight script—must mechanically intercept and terminate the build process. This interception is executed using schema differencing algorithms before the Docker image is ever constructed or deployed to the ARM64 Ubuntu VPS via Coolify.9 This architecture establishes a zero-maintenance contract lifecycle: the developer modifies a Python object, the ecosystem mathematically verifies the integrity of the modification against previous states, and the TypeScript frontends inherit the modifications seamlessly through automated type generation.

## **Multi-Client Ergonomics and the Casing Impedance Mismatch**

A ubiquitous source of silent friction in full-stack software development is the impedance mismatch between Python's idiomatic snake\_case variable naming conventions and JavaScript/TypeScript's idiomatic camelCase naming conventions. In undisciplined architectural environments, developers frequently resort to manual dictionary mapping within API route handlers to bridge this divide. A developer might explicitly map user\_account\_id to userAccountId prior to returning the JSON response. This practice introduces insidious technical debt; it inevitably leads to runtime crashes when a new database column is introduced but the manual mapping layer is inadvertently bypassed or forgotten.7

For Fabrik, managing a multi-client ecosystem inherently amplifies this risk. Manual data mapping is categorized as an extreme anti-pattern. Instead, the boundary translation must occur automatically and universally at the Pydantic serialization layer. By configuring Pydantic's alias\_generator capability within a centralized base model to automatically translate snake\_case to camelCase, the API consumer receives strictly idiomatic JSON, while the Python developer interacts exclusively with idiomatic Python.7

| Architectural Context | Internal Variable Notation | Serialized JSON Output | Consuming TypeScript Client Property |
| :---- | :---- | :---- | :---- |
| Python Core (FastAPI/Pydantic) | user\_account\_id | userAccountId | userAccountId |
| Database Layer (PostgreSQL 16\) | user\_account\_id | N/A | N/A |
| Chrome Extension (Manifest V3) | N/A | userAccountId | userAccountId |

To achieve this without degrading the internal developer experience, the Pydantic configuration must enable populate\_by\_name \= True. This parameter ensures that internal Python logic retains the ability to instantiate models using standard snake\_case keyword arguments, effectively insulating the application's core domain and business logic from the superficial formatting requirements imposed by the HTTP transport layer.7 This singular architectural decision eliminates hundreds of lines of fragile boilerplate code and nullifies a primary vector for human-induced bugs during rapid iteration cycles.

## **The RFC 7807 Imperative for Universal Error Standardization**

When an API serves multiple disparate clients—ranging from heavily interactive Next.js web interfaces to intermittently connected React Native mobile applications and background-executed Manifest V3 service workers—unpredictable error responses severely degrade the developer experience and exponentially increase client-side complexity. If the Next.js application expects an error payload structured as { "error": "Not Found" }, but the mobile application encounters a payload formatted as { "detail": "Resource missing" }, shared TypeScript error handling utility functions become logically impossible to maintain.

To guarantee durability over the 2025–2026 horizon, Fabrik must strictly and unilaterally adopt the Internet Engineering Task Force (IETF) standard **RFC 7807: Problem Details for HTTP APIs**.3 This standard delineates a predictable, machine-readable JSON structure explicitly designed to supersede and eliminate the necessity for bespoke, application-specific error formats.4

The RFC 7807 standard mandates the presence of specific top-level schema properties:

| Property | Data Type | Description and Implementation Guidance |
| :---- | :---- | :---- |
| type | URI String | A URI reference that identifies the specific problem type (e.g., https://api.fabrik.internal/errors/insufficient-funds). |
| title | String | A short, human-readable summary of the problem type. It should not change from occurrence to occurrence. |
| status | Integer | The HTTP status code generated by the origin server for this occurrence of the problem. |
| detail | String | A human-readable explanation providing specific details about this exact occurrence of the problem. |
| instance | URI String | A URI reference that identifies the specific occurrence of the problem, allowing for log correlation. |

FastAPI's default HTTPException handler natively returns a rudimentary {"detail": "..."} response, which is wholly insufficient and non-compliant with the RFC 7807 specification.17 Consequently, the Fabrik architecture mandates overriding the default exception handlers at the application level to enforce the Problem Details schema. This outcome can be realized through the implementation of custom exception middleware or by utilizing maintained, lightweight libraries such as fastapi-rfc7807.18 Furthermore, strict adherence to this schema must be verified during automated linting processes using OpenAPI linters like Spectral. Spectral must be configured via its ruleset to explicitly warn or fail the CI build if any defined 4xx or 5xx response schema within the generated openapi.json lacks the requisite RFC 7807 properties.10

## **Idempotency Engineering for Distributed Client Resilience**

In distributed systems involving mobile clients and background-syncing architectures, network volatility is a primary and constant risk vector. Mobile applications developed in React Native frequently operate on fluctuating 4G/5G connections, while Chrome Extensions relying on Manifest V3 heavily utilize ephemeral background service workers that the browser may terminate unpredictably. If a client initiates a critical, state-mutating operation—such as creating a user entity, processing a financial transaction, or mutating a primary database record—and the network connection drops before the HTTP response is successfully received, the client is left in an indeterminate state. If the client implements naive retry logic, the server may execute the mutation a second time, resulting in severe data corruption, duplicate entity creation, or erroneous financial charges.5

To systematically mitigate this risk without burdening individual route handlers with complex state-tracking logic, all state-mutating endpoints (specifically those utilizing POST, PUT, PATCH, and DELETE HTTP verbs) within the Fabrik platform must natively support cryptographic idempotency.6 Idempotency provides a systemic guarantee that executing the identical request multiple times will reliably yield the exact same state and HTTP response as executing it a single time.23

The standardized implementation relies on the transmission of an X-Idempotency-Key HTTP header, which is typically a uniquely generated UUIDv4 string instantiated by the originating client.6 The backend execution flow operates as a highly concurrent finite state machine, typically backed by a fast, in-memory datastore such as Redis, functioning alongside the FastAPI application 22:

1. **Request Interception and Extraction**: The FastAPI application utilizes an idempotency middleware layer that intercepts the incoming request and extracts the X-Idempotency-Key header.25 If the header is missing on a mutative endpoint, the request is immediately rejected with an HTTP 400 Bad Request.
2. **Distributed Lock Acquisition**: The system queries the Redis instance. If the key already exists and its internal state is marked as COMPLETED, the server entirely bypasses the core application logic. It immediately deserializes and returns the cached HTTP response, including the original status code, payload, and relevant headers.6
3. **Concurrency Conflict Resolution**: If the key exists but the state is marked as PROCESSING, it indicates that a concurrent duplicate request is currently in flight (e.g., the user double-tapped a submission button). The server must immediately return an HTTP 409 Conflict to prevent database race conditions.25
4. **Execution and Persistent Storage**: If the key does not exist within the Redis cluster, it is immediately inserted with a PROCESSING state. The request is then passed downward to the FastAPI route handler. Upon successful completion of the business logic, the final response payload is serialized and stored in Redis under the idempotency key with a COMPLETED state and a predefined Time-To-Live (TTL, typically configured for 24 hours). The response is then safely dispatched to the client.6

Open-source libraries designed for the modern Python ecosystem, such as idemptx or bespoke Redis-backed middleware implementations, seamlessly fulfill this architectural requirement without polluting the underlying business logic of the route handlers, thereby maintaining a clean separation of concerns.23

## **PostgreSQL 16 Pagination Mechanics: The Eradication of Offset**

As the application naturally scales and accumulates data, the database pagination strategy evolves into one of the most critical determinants of overall systemic performance and user experience. The standard LIMIT / OFFSET pagination paradigm, while ubiquitous in elementary tutorials, constitutes a severe anti-pattern for large datasets and is strictly prohibited within the Fabrik architecture.1

### **The Mechanical Failure of Offset Pagination**

The inherent performance degradation associated with offset pagination is fundamentally rooted in the execution mechanics of the PostgreSQL relational database engine. When a client requests a query structured as SELECT \* FROM items ORDER BY created\_at DESC LIMIT 10 OFFSET 10000, the database cannot simply utilize an index to jump instantaneously to the 10,001st row. Due to PostgreSQL's foundational reliance on Multi-Version Concurrency Control (MVCC)—which manages simultaneous transactions by retaining multiple versions of a single row—the database engine must physically scan, evaluate the transactional visibility of, and subsequently discard the first 10,000 rows before it can finally return the requested 10 rows.1

This "scan and discard" mechanism results in a time complexity of ![][image1], where ![][image2] represents the magnitude of the offset value. Consequently, queries attempting to access deep pages consume disproportionate and excessive CPU and I/O resources, inevitably leading to cascading API timeouts and degrading the performance of the entire ARM64 Ubuntu VPS.26 Furthermore, offset pagination suffers from severe "data drift" anomalies. If a new record is inserted at the top of the dataset while a user is actively navigating from Page 1 to Page 2, the entire offset shifts downward, causing the user to observe duplicate records across pages.1

### **The Cursor (Keyset) Pagination Alternative**

To ensure consistent, low-latency performance characterized by ![][image3] time complexity relative to page depth, Fabrik must universally standardize on Cursor (Keyset) Pagination.27 Cursor pagination entirely circumvents the scanning problem by utilizing a unique, sequential identifier—the cursor—to seek directly to the physical location of the subsequent row utilizing an efficient B-Tree index.

Under this paradigm, the SQL query structure fundamentally transforms from an offset-based approach to a strict filtering approach:

* **Legacy Query:** SELECT \* FROM items ORDER BY created\_at DESC LIMIT 10 OFFSET 20;
* **Cursor Query:** SELECT \* FROM items WHERE created\_at \< \[cursor\_value\] ORDER BY created\_at DESC LIMIT 10;

To implement this sophisticated approach efficiently within the FastAPI ecosystem without writing excessive, error-prone boilerplate code, the fastapi-pagination library provides highly robust abstractions for cursor pagination that are baked directly into modern SQLAlchemy 2.0 query structures.26

| Pagination Feature | Offset Pagination (LIMIT/OFFSET) | Cursor (Keyset) Pagination |
| :---- | :---- | :---- |
| **Performance at scale** | Degrades linearly (![][image1]); scans discarded rows. | Remains constant (![][image3]); utilizes direct index seeks. 26 |
| **Data consistency (Drift)** | Highly vulnerable to duplicates/skips during active mutations. | Entirely immune to concurrent insertions/deletions. 2 |
| **Random access** | Supported (Jump directly to arbitrary page X). | Not supported (Strictly sequential traversal only). 30 |
| **Implementation complexity** | Low; native SQL support. | Medium; requires guaranteed deterministic sorting. 26 |

A critical caveat to cursor pagination is the absolute necessity of deterministic sorting. If an API endpoint attempts to sort by a non-unique column (e.g., sorting items by a popularity score), the B-Tree traversal becomes ambiguous when multiple rows share the identical score. To resolve this, a strictly unique secondary column (e.g., the primary id or a uuid) must be definitively appended to the sort clause to prevent data omission.31

## **Low-Maintenance API Versioning Strategies**

API versioning acts as the silent structural backbone of modern mobile and extension software.32 Unlike web applications, where the frontend can be instantaneously and universally force-refreshed to synchronize with the latest backend modifications, mobile applications (such as those built with React Native) and Manifest V3 Chrome Extensions are intrinsically subject to substantial deployment lag. This lag is induced by mandatory app store review processes and user adoption delays.33 Consequently, deploying an API breaking change without a formal versioning strategy will immediately and catastrophically crash legacy client instances operating in the wild.35

Evaluating API versioning strategies specifically tailored for a budget-conscious, solo-developer environment necessitates prioritizing operational visibility and debugging simplicity over theoretical academic purity.

1. **Header-Based Versioning (Accept or Custom Headers)**: While this approach maintains pristine URL structures, header versioning effectively hides complexity in the transport layer. It makes ad-hoc debugging via simple browser requests or basic cURL commands highly cumbersome, as it requires specialized client configuration to explicitly set the Accept: application/vnd.fabrik.v2+json header.36
2. **Query Parameter Versioning**: Utilizing parameters such as ?version=2 is flexible, but it is notoriously prone to being overlooked in aggressive caching layers or inadvertently stripped by intermediate API gateways and proxies.36
3. **URI Path Versioning (/v1/)**: This strategy embeds the version directly into the URL path. It is undeniably explicit, highly visible, and trivially routable at the API gateway or reverse proxy level. More importantly, it natively segments OpenAPI documentation, providing clear, visual demarcations of application boundaries for the developer.35

Fabrik will strictly enforce **URI Path Versioning**, a pattern natively supported by FastAPI's APIRouter.39 Under this rule, all programmatic endpoints must be explicitly mounted under a version prefix (e.g., /api/v1/resource).

When evolving business requirements mandate a breaking change, the developer must spawn a completely new version prefix (e.g., /api/v2/resource). To prevent unmanageable code duplication, shared business logic must be rigorously abstracted into an independent service layer (e.g., within a services.py module). This architectural separation allows both the legacy v1 and the novel v2 routers to invoke the identical core computational functions while exposing differentiated HTTP transport schemas and validation layers.41

Furthermore, deprecated legacy endpoints must clearly advertise their impending sunset status using the standardized Deprecation HTTP header. Simultaneously, the OpenAPI specification must flag the endpoint endpoint using the deprecated: true boolean, which automatically triggers compilation warnings in the generated TypeScript clients, proactively notifying the developer during the build phase.42

## **2\. Canonical Rules for this Rule File**

The following bulleted directives form the absolute, non-negotiable architectural perimeter for all AI agents generating, modifying, or reviewing API logic within the Fabrik repository. These rules are optimized for long-term durability and minimal operational overhead.

1. **Code-First Source of Truth**: The OpenAPI specification is exclusively and deterministically generated from FastAPI path operations and Pydantic validation models. Manual modification of the openapi.json or openapi.yaml artifacts is strictly prohibited under all circumstances.
2. **Automated Client Generation**: Client-side TypeScript interfaces (utilized by Next.js, React Native, and Chrome Extensions) must be generated mechanically via @hey-api/openapi-ts (or an equivalent AST generator) directly from the openapi.json artifact.15 Manual typing of API responses in TypeScript is banned.
3. **Strict Casing Boundaries**: All internal Python variables and database columns must utilize snake\_case. All JSON serialization payloads exposed to the network must utilize camelCase. This translation must be enforced globally via a base Pydantic model utilizing the alias\_generator parameter.7
4. **RFC 7807 Error Standardization**: Every HTTP response with a status code of 4xx or 5xx must strictly adhere to the RFC 7807 Problem Details schema. Emitting raw strings or arbitrary custom error dictionaries is structurally invalid.3
5. **Idempotency Mandate**: All endpoints mutating systemic state (POST, PUT, PATCH, DELETE) must explicitly support the X-Idempotency-Key HTTP header. Requests must be evaluated against a Redis lock to definitively prevent duplicate execution during network transmission failures.5
6. **Pagination Exclusivity**: Cursor (keyset) pagination is the sole acceptable pagination mechanism for iterating over collections. Offset pagination (LIMIT/OFFSET) is permanently banned to prevent MVCC scanning degradation within the PostgreSQL 16 instance.1
7. **Deterministic Sorting Verification**: Any endpoint utilizing cursor pagination on a non-unique database column (e.g., sorting by created\_at or price) must mechanically append a strictly unique column (e.g., id or uuid) to the sort order parameter to ensure deterministic B-Tree traversal.31
8. **Explicit URI Path Versioning**: All endpoints must be explicitly versioned in the URI path (e.g., /api/v1/users). "Versionless" APIs are entirely prohibited to protect the stability of legacy mobile applications and browser extensions.32
9. **Base Image Restriction**: All Dockerized Python backend services must be constructed upon the slim-bookworm base image. alpine images are strictly prohibited to preempt musl-libc C-extension compilation errors and associated DNS resolution anomalies commonly found in complex Python environments.
10. **Service Layer Isolation**: Core business logic must not reside within FastAPI HTTP route handlers. Logic must be abstracted to a dedicated, decoupled service layer to facilitate shared execution across multiple API versions (e.g., v1, v2) without code duplication.41
11. **Breaking Change Enforcement**: The CI/CD pipeline must execute oasdiff against the generated openapi.json, comparing it deterministically to the main branch artifact. Any detection of a breaking change (Severity Level: ERR) without a corresponding version bump must immediately fail the build process.9
12. **Slim Dependency Footprint**: AI agents must avoid introducing hyper-specialized orchestration protocols (e.g., gRPC, GraphQL) unless strictly required for a hyper-specific, low-latency microservice. RESTful JSON over HTTP/2, formally described by OpenAPI, serves as the permanent, maintainable baseline for the Fabrik stack.38

## **3\. Anti-Patterns / Banned Patterns**

To maintain operational sanity for a solo developer constrained to a 50-hour work week, the following patterns are systematically banned from the repository. AI agents detected suggesting these patterns must be corrected immediately.

* **Manual Type Mapping**: Writing bespoke utility functions to manually map a database variable like user\_id to a JSON payload property like userId prior to returning a dictionary from a route. Agents must rely exclusively on Pydantic's populate\_by\_name \= True and alias\_generator to handle this at the boundary layer.7
* **The OFFSET Keyword**: Using the offset parameter in any SQLAlchemy statement or executing Raw SQL queries containing OFFSET involving collections that scale beyond 100 records.
* **Alpine Linux Bases**: Utilizing python:3.12-alpine in Dockerfile definitions. The computational overhead of locally compiling wheels from C-extensions completely negates any theoretical image size benefits. Stick exclusively to Debian-based slim-bookworm \[User Constraint\].
* **Header-Based Versioning**: Attempting to route API versions via complex content negotiation like Accept: application/vnd.fabrik.v2+json. This pattern is virtually un-debuggable from a standard browser without external proxy tools and frustrates rapid solo development.36
* **Blocking the Main Event Loop**: Executing synchronous I/O operations (e.g., utilizing the standard requests library, or instantiating synchronous SQLAlchemy database sessions) within an async def FastAPI route handler.44 Agents must substitute these with their asynchronous counterparts: httpx, asyncpg, and AsyncSession.
* **Beside-the-Point REST Zealotry**: Overcomplicating APIs to adhere to extreme REST theoretical constraints (such as implementing complex HATEOAS link traversal) when a simple, highly predictable RPC-style POST endpoint provides vastly superior developer ergonomics and lower ongoing maintenance.
* **Versionless API Mutability**: Altering an existing /v1/ endpoint's response schema (e.g., removing a previously required field, or changing a data type from integer to string) under the naive assumption that the frontend monorepo has been updated simultaneously. Mobile applications installed on end-user devices do not update simultaneously and will crash.35

## **4\. What to Enforce in Execute Handoffs**

When an AI agent finishes drafting a block of code and prepares to hand off to execution or to another agent within the workflow, the following state conditions must be mechanically verified:

1. **OpenAPI Artifact Regeneration**: The agent must ensure that the openapi.json file has been freshly generated using the Uvicorn runtime after any alterations to FastAPI routes, dependency injections, or Pydantic validation models.
2. **Typescript Synchronization Validation**: The agent must verify that the @hey-api/openapi-ts compilation step (or equivalent generation script) has been successfully executed, confirming that the frontend client definitions perfectly match the newly generated backend schema without throwing any downstream TypeScript compilation errors.15
3. **Migration Integrity and Safety**: If SQLAlchemy database models were altered during the generation step, the agent must ensure an Alembic migration script has been successfully generated. Crucially, the script must be reviewed for safety (e.g., explicitly checking for inadvertent table drops that Alembic occasionally hallucinates), and it must execute flawlessly against the local PostgreSQL 16 testing instance.
4. **Endpoint Security Audit**: The agent must explicitly verify that no newly created endpoint was inadvertently exposed to the public internet without the global authentication dependency being appropriately applied, unless the route is explicitly documented and tagged as a public resource.45

## **5\. What to Verify in final\_gate.py**

The final\_gate.py script acts as the unforgiving, automated CI/CD boundary. Designed to run locally or in the remote pipeline prior to deployment, it must automatically execute the following uncompromising checks before authorizing a Docker deployment to the ARM64 VPS via Coolify:

1. **Breaking Change Detection via oasdiff**:
   * The script must execute the following shell command: oasdiff breaking \--fail-on ERR base\_openapi.json current\_openapi.json
   * If oasdiff detects a schema regression and returns an exit code of 1, final\_gate.py must immediately abort the pipeline. Absolutely no breaking changes to existing versioned paths are permitted in production.9
2. **Schema Linting via Spectral**:
   * The script must run Spectral against the generated OpenAPI schema to verify rigorous RFC 7807 compliance.
   * The applied ruleset constraint must explicitly check that all 4xx and 5xx HTTP response contents map precisely to the standard Problem Details structure. Failure to match this schema aborts the deployment.10
3. **Dependency Vulnerability Scanning**:
   * Execute an automated, rapid scan of requirements.txt or pyproject.toml (e.g., using pip-audit) to ensure no newly introduced Python package contains a known, publicly disclosed Common Vulnerabilities and Exposures (CVE) record.
4. **Static Analysis and Type Coercion Verification**:
   * Static analysis tools (mypy or pyright) must execute and pass with zero errors, guaranteeing that no ambiguous Any types have inadvertently leaked into the strictly defined API contracts.

## **6\. What Belongs in AGENTS.md / AGENTS-compact.md**

To minimize token overhead during interactions while maximizing relevant contextual awareness, AI agents should be fed a strictly condensed, highly dense set of instructions within the AGENTS-compact.md file.

**Condensed Content for AGENTS-compact.md (API Section):**

* "API Contract: FastAPI code is the absolute Source of Truth. TS clients are auto-generated from openapi.json. Do not manually write TS types for APIs under any circumstances."
* "Variables: Python uses snake\_case. Expose to JSON as camelCase exclusively using Pydantic's alias\_generator."
* "Errors: All HTTP exceptions must use RFC 7807 (type, title, status, detail)."
* "Pagination: STRICTLY cursor/keyset via fastapi-pagination. OFFSET is completely banned."
* "Mutations: POST/PUT/PATCH/DELETE require Redis-backed X-Idempotency-Key headers to survive mobile network drops."
* "Versioning: Explicit URI versioning (/api/v1/). Never introduce breaking changes to an existing version; create a new endpoint."
* "Base Image: slim-bookworm only. Never use alpine."

## **7\. Minimal Practical Examples for Fabrik Stack**

The following code snippets demonstrate the precise, minimal architectural implementations required to satisfy the constraints outlined in this report.

### **The Unified Pydantic Base Model (CamelCase conversion)**

This model ensures seamless boundary translation between Python and TypeScript.

Python

from pydantic import BaseModel, ConfigDict
from pydantic.alias\_generators import to\_camel

class FabrikBaseModel(BaseModel):
    """
    Base model ensuring all snake\_case Python attributes
    are serialized to camelCase JSON for TS consumption.
    """
    model\_config \= ConfigDict(
        alias\_generator=to\_camel,
        populate\_by\_name=True,
        from\_attributes=True
    )

class UserResponse(FabrikBaseModel):
    user\_id: str
    is\_active: bool

### **RFC 7807 Error Response Implementation**

This snippet demonstrates overriding FastAPI's standard behavior to enforce structured problem details.

Python

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None \= None

async def rfc7807\_exception\_handler(request: Request, exc: Exception):
    problem \= ProblemDetails(
        type\="https://api.fabrik.internal/errors/internal-error",
        title="Internal Server Error",
        status=500,
        detail=str(exc),
        instance=str(request.url)
    )
    return JSONResponse(status\_code=500, content=problem.model\_dump())

### **Idempotency Middleware Setup**

This middleware utilizes Redis to trap and resolve duplicate mutative requests originating from unstable networks.

Python

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import redis.asyncio as redis
import json

redis\_client \= redis.Redis(host='localhost', port=6379, db=0)

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call\_next):
        if request.method not in:
            return await call\_next(request)

        idem\_key \= request.headers.get("X-Idempotency-Key")
        if not idem\_key:
            return JSONResponse({"error": "Idempotency key required"}, status\_code=400)

        redis\_key \= f"idem:{idem\_key}"
        cached \= await redis\_client.get(redis\_key)

        if cached:
            data \= json.loads(cached)
            if data\["status"\] \== "PROCESSING":
                return JSONResponse({"error": "Conflict"}, status\_code=409)
            return JSONResponse(content=data\["body"\], status\_code=data\["code"\])

        await redis\_client.set(redis\_key, json.dumps({"status": "PROCESSING"}), ex=86400)

        response \= await call\_next(request)
        \# In a complete implementation, response bodies are captured and cached here prior to return
        return response

### **Cursor Pagination with fastapi-pagination**

This endpoint demonstrates how to seamlessly execute high-performance cursor pagination using SQLAlchemy 2.0.

Python

from fastapi import APIRouter, Depends
from fastapi\_pagination import Page, add\_pagination
from fastapi\_pagination.ext.sqlalchemy import paginate
from fastapi\_pagination.cursor import CursorPage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get\_db
from app.models import Item
from app.schemas import ItemResponse

router \= APIRouter(prefix="/v1/items")

@router.get("/", response\_model=CursorPage)
async def get\_items(db: AsyncSession \= Depends(get\_db)):
    \# Requires deterministic sort: primary sort \+ unique id fallback
    stmt \= select(Item).order\_by(Item.created\_at.desc(), Item.id.asc())
    return await paginate(db, stmt)

## **8\. Recommended Final Content for the Rule File**

# **15-api-contracts.md**

## **Architectural Mandate**

This rule file formally governs the API contract layer for the entire Fabrik platform. Explicitly designed for a highly constrained, solo-developer environment (WSL Ubuntu 24.04 local, ARM64 Ubuntu VPS production via Coolify), the API layer must be defensively engineered to require absolutely zero maintenance or manual synchronization once deployed. Velocity is achieved through structural rigidity.

## **Core Directives**

1. **Definitive Source of Truth**: FastAPI Pydantic models dictate the OpenAPI contract. The generated OpenAPI JSON artifact is the definitive systemic boundary. TypeScript clients (Next.js, React Native, Manifest V3 Extensions) MUST be automatically generated from this artifact utilizing @hey-api/openapi-ts. Never manually type API responses in the frontend codebases.
2. **Casing Boundary Standardization**: Python internal logic and database definitions strictly use snake\_case. API JSON payloads strictly use camelCase. Implement this implicitly via a global Pydantic BaseModel using alias\_generator=to\_camel and populate\_by\_name=True.
3. **RFC 7807 Error Compliance**: Custom or arbitrary error dictionaries are strictly banned. All HTTP 4xx and 5xx errors must conform perfectly to RFC 7807 Problem Details (type, title, status, detail, instance).
4. **Idempotency Execution**: Every state-mutating endpoint (POST, PUT, PATCH, DELETE) must expect an X-Idempotency-Key HTTP header. Incoming requests must be evaluated against a distributed Redis lock to prevent duplicate execution during mobile network failures or extension background sync restarts.
5. **Pagination Exclusivity**: OFFSET/LIMIT pagination is completely banned to avoid PostgreSQL MVCC performance degradation. All list endpoints must implement Cursor (Keyset) Pagination utilizing deterministic sorting (e.g., ORDER BY created\_at DESC, id ASC).
6. **Immutable URI Versioning**: All API endpoints must be prefixed with a highly visible URI version (e.g., /api/v1/). You may not introduce breaking changes to existing endpoints. If an API contract must be broken to accommodate new logic, abstract the core logic into a service layer and mount a new /v2/ router. Legacy extensions and mobile apps depend entirely on this stability.
7. **Infrastructure Boundary Limitations**: Base Docker images must be slim-bookworm. The alpine Linux distribution is strictly forbidden due to C-extension compilation overhead.

## **Human Guidance Only**

The following items are recommended practices for the human developer managing the architecture, but are not strictly enforced by automated agents:

* **Deprecation Timelines**: When rolling out a /v2/ API, monitor the logs for the /v1/ endpoint. Set calendar reminders to safely decommission /v1/ code only after mobile client update adoption crosses the 95% threshold.
* **Service Layer Granularity**: Exercise human judgment when deciding how much logic to abstract into services.py. Do not prematurely optimize abstracting logic if an endpoint is trivial and highly unlikely to require a v2 revision.
* **Idempotency Key Generation**: Ensure client-side application logic generates highly entropic UUIDv4 keys for idempotency. Do not rely on sequential counters or predictable timestamps from the client side.

## **Pre-Deployment Verification (final\_gate.py)**

No code may be merged to the primary branch or deployed to the VPS without the final\_gate.py script automatically verifying:

* The execution of oasdiff breaking \--fail-on ERR to guarantee no accidental contract breakage.
* Spectral schema linting to ensure strict RFC 7807 compliance for all error pathways defined in the specification.
* The successful, error-free regeneration and compilation of the TypeScript client models against the Next.js and React Native environments.

#### **Works cited**

1. Cursor vs Offset Pagination: The Hidden Performance Debt \- Medium, accessed March 31, 2026, [https://medium.com/@aphatheology/cursor-vs-offset-pagination-the-hidden-performance-debt-9b60b1a07121](https://medium.com/@aphatheology/cursor-vs-offset-pagination-the-hidden-performance-debt-9b60b1a07121)
2. A Developer's Guide to API Pagination: Offset vs. Cursor-Based \- Embedded Blog, accessed March 31, 2026, [https://embedded.gusto.com/blog/api-pagination/](https://embedded.gusto.com/blog/api-pagination/)
3. Transforming API Error Handling: A Deep Dive into RFC 7807 with Spring Boot \- Medium, accessed March 31, 2026, [https://medium.com/@suraj.sharma3963/transforming-api-error-handling-a-deep-dive-into-rfc-7807-with-spring-boot-3a7d7df9305b](https://medium.com/@suraj.sharma3963/transforming-api-error-handling-a-deep-dive-into-rfc-7807-with-spring-boot-3a7d7df9305b)
4. RFC 7807 \- Problem Details for HTTP APIs \- IETF Datatracker, accessed March 31, 2026, [https://datatracker.ietf.org/doc/html/rfc7807](https://datatracker.ietf.org/doc/html/rfc7807)
5. Best practices for implementing Idempotent Requests with FastAPI \#3555 \- GitHub, accessed March 31, 2026, [https://github.com/fastapi/fastapi/discussions/3555](https://github.com/fastapi/fastapi/discussions/3555)
6. Implementing Idempotency Keys in REST APIs \- Zuplo, accessed March 31, 2026, [https://zuplo.com/learning-center/implementing-idempotency-keys-in-rest-apis-a-complete-guide](https://zuplo.com/learning-center/implementing-idempotency-keys-in-rest-apis-a-complete-guide)
7. Stop Writing Manual snake\_case-camelCase Mappings in Your Python API \- Medium, accessed March 31, 2026, [https://medium.com/@hassanmehmood.dev/stop-writing-manual-snake-case-camelcase-mappings-in-your-python-api-f7c6178e23dc](https://medium.com/@hassanmehmood.dev/stop-writing-manual-snake-case-camelcase-mappings-in-your-python-api-f7c6178e23dc)
8. oasdiff — OpenAPI Breaking Change Detection & PR Review, accessed March 31, 2026, [https://www.oasdiff.com/](https://www.oasdiff.com/)
9. oasdiff/docs/BREAKING-CHANGES.md at main \- GitHub, accessed March 31, 2026, [https://github.com/oasdiff/oasdiff/blob/main/docs/BREAKING-CHANGES.md](https://github.com/oasdiff/oasdiff/blob/main/docs/BREAKING-CHANGES.md)
10. Enhance Your API Standards Using Spectral and Postman \- Learning Lab, accessed March 31, 2026, [https://community.postman.com/t/enhance-your-api-standards-using-spectral-and-postman/76858](https://community.postman.com/t/enhance-your-api-standards-using-spectral-and-postman/76858)
11. A Developer's Guide to API Design-First, accessed March 31, 2026, [https://apisyouwonthate.com/blog/a-developers-guide-to-api-design-first/](https://apisyouwonthate.com/blog/a-developers-guide-to-api-design-first/)
12. Design, Generate, Deploy: Our Contract-First API Strategy with FastAPI and OpenAPI, accessed March 31, 2026, [https://blog.malt.engineering/design-generate-deploy-our-contract-first-api-strategy-with-fastapi-and-openapi-15bb3e855dff](https://blog.malt.engineering/design-generate-deploy-our-contract-first-api-strategy-with-fastapi-and-openapi-15bb3e855dff)
13. When Swagger Lies: Fixing API Drift Before It Breaks You \- DEV Community, accessed March 31, 2026, [https://dev.to/copyleftdev/title-when-swagger-lies-fixing-api-drift-before-it-breaks-you-ijo](https://dev.to/copyleftdev/title-when-swagger-lies-fixing-api-drift-before-it-breaks-you-ijo)
14. FastAPI Best Practices \- Auth0, accessed March 31, 2026, [https://auth0.com/blog/fastapi-best-practices/](https://auth0.com/blog/fastapi-best-practices/)
15. Generating SDKs \- FastAPI, accessed March 31, 2026, [https://fastapi.tiangolo.com/advanced/generate-clients/](https://fastapi.tiangolo.com/advanced/generate-clients/)
16. debkanchan/sdking: Generate TypeScript SDKs from OpenAPI specs. Validate API inputs and outputs using Zod. Own your SDKs\! \- GitHub, accessed March 31, 2026, [https://github.com/debkanchan/sdking](https://github.com/debkanchan/sdking)
17. Support RFC 7807 error handling. \#8059 \- GitHub, accessed March 31, 2026, [https://github.com/tiangolo/fastapi/discussions/8059](https://github.com/tiangolo/fastapi/discussions/8059)
18. fastapi-rfc7807 \- PyPI, accessed March 31, 2026, [https://pypi.org/project/fastapi-rfc7807/](https://pypi.org/project/fastapi-rfc7807/)
19. vapor-ware/fastapi-rfc7807: RFC-7807 compliant problem detail error response handler for ... \- GitHub, accessed March 31, 2026, [https://github.com/vapor-ware/fastapi-rfc7807](https://github.com/vapor-ware/fastapi-rfc7807)
20. APIs You Won't Hate \- The Ruleset · stoplightio spectral · Discussion \#1398 \- GitHub, accessed March 31, 2026, [https://github.com/stoplightio/spectral/discussions/1398](https://github.com/stoplightio/spectral/discussions/1398)
21. Problem Details (RFC 9457): Getting Hands-On with API Error Handling \- Swagger, accessed March 31, 2026, [https://swagger.io/blog/problem-details-rfc9457-api-error-handling/](https://swagger.io/blog/problem-details-rfc9457-api-error-handling/)
22. Understanding Idempotency: A Guide to Reliable System Design \- DEV Community, accessed March 31, 2026, [https://dev.to/leapcell/understanding-idempotency-a-guide-to-reliable-system-design-18e3](https://dev.to/leapcell/understanding-idempotency-a-guide-to-reliable-system-design-18e3)
23. A Simple Way to Handle Idempotency in FastAPI using idemptx | by Riley Chen | Medium, accessed March 31, 2026, [https://medium.com/@riley.dev/a-simple-way-to-handle-idempotency-in-fastapi-using-idemptx-08d57f0faf88](https://medium.com/@riley.dev/a-simple-way-to-handle-idempotency-in-fastapi-using-idemptx-08d57f0faf88)
24. pypy-riley/idemptx: Idempotency decorator for FastAPI. Redis-based locking and replay support. \- GitHub, accessed March 31, 2026, [https://github.com/pypy-riley/idemptx](https://github.com/pypy-riley/idemptx)
25. How to Implement Idempotency Keys with Redis \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-21-redis-idempotency-keys/view](https://oneuptime.com/blog/post/2026-01-21-redis-idempotency-keys/view)
26. How to Implement Pagination in FastAPI \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-02-fastapi-pagination/view](https://oneuptime.com/blog/post/2026-02-02-fastapi-pagination/view)
27. REST Pagination techniques \- DEV Community, accessed March 31, 2026, [https://dev.to/kanakos01/rest-pagination-techniques-p9b](https://dev.to/kanakos01/rest-pagination-techniques-p9b)
28. uriyyo/fastapi-pagination \- GitHub, accessed March 31, 2026, [https://github.com/uriyyo/fastapi-pagination](https://github.com/uriyyo/fastapi-pagination)
29. How do you handle pagination/sorting/filtering with fastAPI? \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1fp1jg3/how\_do\_you\_handle\_paginationsortingfiltering\_with/](https://www.reddit.com/r/FastAPI/comments/1fp1jg3/how_do_you_handle_paginationsortingfiltering_with/)
30. Offset vs Cursor-Based Pagination: Choosing the Best Approach | by Maryam Noor, accessed March 31, 2026, [https://medium.com/@maryam-bit/offset-vs-cursor-based-pagination-choosing-the-best-approach-2e93702a118b](https://medium.com/@maryam-bit/offset-vs-cursor-based-pagination-choosing-the-best-approach-2e93702a118b)
31. Cursor-based vs. Offset Pagination for an Infinite Scroll Book Library – Which is Better?, accessed March 31, 2026, [https://www.reddit.com/r/dotnet/comments/1jxlu89/cursorbased\_vs\_offset\_pagination\_for\_an\_infinite/](https://www.reddit.com/r/dotnet/comments/1jxlu89/cursorbased_vs_offset_pagination_for_an_infinite/)
32. API Versioning: The Silent Backbone of Modern Software | by Adjetadjetey \- Medium, accessed March 31, 2026, [https://medium.com/@adjetadjetey45/api-versioning-the-silent-backbone-of-modern-software-01d2b76a3c13](https://medium.com/@adjetadjetey45/api-versioning-the-silent-backbone-of-modern-software-01d2b76a3c13)
33. Mobile App Development Trends 2026: AI, No-Code & Beyond | Lovable, accessed March 31, 2026, [https://lovable.dev/guides/mobile-app-development-trends-2026](https://lovable.dev/guides/mobile-app-development-trends-2026)
34. API Versioning Strategies \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-02-api-versioning-strategies/view](https://oneuptime.com/blog/post/2026-02-02-api-versioning-strategies/view)
35. API Versioning Strategies That Don't Suck | by Sohail x Codes \- Medium, accessed March 31, 2026, [https://medium.com/@sohail\_saifii/api-versioning-strategies-that-dont-suck-7b8ffa51ac09](https://medium.com/@sohail_saifii/api-versioning-strategies-that-dont-suck-7b8ffa51ac09)
36. API Versioning Strategies That Actually Work in Production (2026 Guide) \- DEV Community, accessed March 31, 2026, [https://dev.to/young\_gao/api-versioning-strategies-that-actually-work-in-production-3hoh](https://dev.to/young_gao/api-versioning-strategies-that-actually-work-in-production-3hoh)
37. Best Practices for Mobile App API Versioning \- Techneosis, accessed March 31, 2026, [https://www.techneosis.com/insights/best-practices-for-mobile-app-api-versioning/](https://www.techneosis.com/insights/best-practices-for-mobile-app-api-versioning/)
38. API Design 2026: Why the Multi-Protocol Approach is the Ultimate Guide \- DEV Community, accessed March 31, 2026, [https://dev.to/dataformathub/api-design-2026-why-the-multi-protocol-approach-is-the-ultimate-guide-2h6o](https://dev.to/dataformathub/api-design-2026-why-the-multi-protocol-approach-is-the-ultimate-guide-2h6o)
39. recommended way to do API versioning · fastapi fastapi · Discussion \#8177 \- GitHub, accessed March 31, 2026, [https://github.com/fastapi/fastapi/discussions/8177](https://github.com/fastapi/fastapi/discussions/8177)
40. Building Advanced FastAPI Applications: A Comprehensive Guide to Middleware, Versioning, and Database Integration | by Faizulkhan | Medium, accessed March 31, 2026, [https://medium.com/@faizulkhan56/building-advanced-fastapi-applications-a-comprehensive-guide-to-middleware-versioning-and-04d0b49769b4](https://medium.com/@faizulkhan56/building-advanced-fastapi-applications-a-comprehensive-guide-to-middleware-versioning-and-04d0b49769b4)
41. How to structure FastAPI app so logic is outside routes \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1b55e8q/how\_to\_structure\_fastapi\_app\_so\_logic\_is\_outside/](https://www.reddit.com/r/FastAPI/comments/1b55e8q/how_to_structure_fastapi_app_so_logic_is_outside/)
42. Modern API Design Best Practices for 2026 \- Xano, accessed March 31, 2026, [https://www.xano.com/blog/modern-api-design-best-practices/](https://www.xano.com/blog/modern-api-design-best-practices/)
43. How to Create API Deprecation Headers \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-30-api-deprecation-headers/view](https://oneuptime.com/blog/post/2026-01-30-api-deprecation-headers/view)
44. FastAPI Best Practices: A Complete Guide for Building Production-Ready APIs \- Medium, accessed March 31, 2026, [https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617](https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617)
45. Global Dependencies \- FastAPI \- Mintlify, accessed March 31, 2026, [https://mintlify.com/fastapi/fastapi/tutorial/dependencies/global-dependencies](https://mintlify.com/fastapi/fastapi/tutorial/dependencies/global-dependencies)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAbCAYAAADcQMc2AAADIElEQVR4XtWYT4hPURTHz0tTJP8TSfJnpywsZEcKJQs2LBR7GxuKLCyUlKIkC81uGilrZUETG1F2bJSZJkWzsZCmFMX5/s4775573r3v3V/z12c6zfzOOfe8c8+95777GyJP5RUxPeZFIZdDTu8ocyvzWmqGyHII137mNdiisJwzHj43jJhl2en0C8FBlq9e6RlhecvyNyFHjV8XMyxnvNKwhWUySIXfj2KXhnskfqNcqVH8rj9vMD63zN8tXpAkf9cbmDES20tvcEv5lGXaKhJsZjnLcpXioqX2xDGWxxR83pOMdb7toStYfpMM2uhsllckPlecXtlEYt/hDRn2snymkPCl2BzxjuW8V+bAFP9Q/4QAKqwJUKI6b1i+e2UHD1iusTwnifkrNkcgx7VemQP7HwGve0MGndR+p8cMoUeSifnWxPpvLFtr0bj7Ig9hNTWF7AcJmMoXof6Xnf50rcdqlmKfq8X9YHTKcZbXXpmi4h9N8LY3dqBjZEWAVF8PmVLQT5/M58MUYq8yevCMpGi9XKQQZL2z5cAxqmNOORt66afTZRhUAf0UVlsKo739pNEL6LU1ThcwW/oLSYCu5vTg9BlMiuNsdzbocZKVov1kuUmhaMpKksn2U4XBRXu1BvvdP1SJYuXOCUM7RjV48Wv8c7X2JMtEEzER2Kp08FikTQyqsQ986GwA+gmvTFP5frLgtYBYP+rP6NWifgKaYGj4HDLR+xTGpKbeOSlXN30/pbDH+26SrVfUT0CbEtefPswqVbmqwV7aU+gn35OWGZKT+SOV9lMNThgMxIHRx3T9EFwmc8AebhOptQzAt4sTFFYru/op8C7Qgbiz5cCdCz7j3XnSFKWSbQ86QGWF1J2Bg2Io8KbGYCwxtpgFk8Z3ItiPOFsi2Qp9Al8fR123sdyoQiEvkHwFcTSBtYdxRRqadRRu6LFUdMc69rCHZNwhb6D4Iozq4z2Hv3HS5RippKhLDlYcN+7/iNaWa6EX5GXAINn+jAvBajXvoFbUlmK+WLDAA3ZR68DIPTCnL8OMLr2Qz+mR+KcLvh91Mof4ntl/A0DQ9Jq8KT0AAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAfCAYAAADjuz3zAAABsUlEQVR4XsWWsUoEMRCGZ7ER5EC7KyysfQFBsbWxERELazvhGh/CB7jyQGxEtLlGtBAEexvBRkQ7xRcQrhD0n01mMzvZXFZR7+N+spmZTGYnWTgiQ2ENf4/fspDR2CdEfvd8xATYhZ6MVhOV3kH30AD+AcZD6KH02AWYr2DYhk6gT683G+QfOO6WQtwxtCneFH3olMKiblRFgP1z7jEdJLxC89CI3MLLmjes75Dzt0aCe0giVTeVsw7rjTWmWCQ5BJdMEveqiMA5tGWNKbi/+2p+Ri4xt8VTFT/CI7djPD6c+9tV1lkKVS8HO01DH2qeJRwG7+R2e/Z2HoU16FrNm6heTfdXw5VK1fwGzBW0UUVk6Bf1/mr4tTkxfzwy70RXJTKUFHJ/DWU03wqpmg/sh/2N0VdvSPn+VnB/H63RwF+gJG/d3yPowBoDZTv4GkrimZrbMAUtQBfkgt+hJXI9bKDg3wup/jafFdEehQq0dnSQWc1XbxhltHOhZk8F/Qff3ju5IOnw5PyC/IVohwnmqZiCK84YWzw6QZbWgW2JSw+Pv75ZI+OaZinaBGlcc1NrvgD0IVV3SH+HdgAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAbCAYAAAAH+20UAAACaElEQVR4Xu2XTStGQRTHzyQLK+8bSV4+gS+glFiyUTbsrVnIXkpZSFZ2KOULWJDYiLUt0hOxsSGlKObMmTEzZ2bu3PsoLPzq9Dz3f86ZOffMvXPvBfjnjyO48Pv8bEk/O1sMoWp4kdbLPFXolfYE4fnwY2iUdibtI2IjTlyAM9KDtEl7WDczQGMlOQAqbFUd+eeyJQX0HXpqyJ60m7APAVNAc3VxB+OOC0iDtDegAdqUEp/wGChmnumGdiB/D3do7iFctVzB/VwQsrZ3cItN0wlmovgJnUp79CUdSD9j0jq0o2zBAXiNYOIid3jYAvVEYtA6FRiBvgWmp6irYBzcJKbxu2ni5zwVYELruArAOhujcsGmI2jLzFeEyeGdNDcsI1kxjSPKFzwLdvIW5nPwJmwFmzPuOoCu3WemFVG5wzVBCa9fSrIZX0yDnaib+VC7ZFoRVQpWlZmEE98XR5/LBdg8htqjM2PRI1APVqVghUnY4o4E+AQ0ORuR5UD9iIsF1F0wv3nCUog1sDm4d3NswdkNQvGhVyVTsB3FPCxKdFg43RW4ffnYJa7zGs6cmmYXKKHGHRFugGI3me6C/vhTLnrkFhyHxYsmsEn4DpDiHChmRx2lm3ENFFcU45ItOMYoUBJeHrjsLnhCL3Jy9A8zX4x1oLH4OC5YHBru4abgbdQE6fgSlqUZ7JsatxUnLscAUM6QlYJWo/9W6lfyV5u4EvQ/3+1guBSFgZ4TV2rfFf465mWqFIV90IhyYS5V41WXg739GyxxIaByiYhN6oP8zRchOqvZ/xPuGKUDPfADtPDjMY03ofqY/QS3Oank52a0wQAAAABJRU5ErkJggg==>
