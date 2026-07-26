# **Architectural Directive and Agent Orchestration Rulebook for the Fabrik Platform**

## **Executive Summary**

The contemporary software engineering landscape offers a vast proliferation of frameworks, deployment paradigms, and architectural patterns. While this abundance provides flexibility for enterprise teams, it introduces severe operational hazards for the solo developer. Operating under a strict constraint of approximately fifty focused hours per week, a solo developer cannot afford to dedicate time to chasing transient technological trends, untangling complex microservice orchestrations, or debugging fragile deployment pipelines. The Fabrik platform is conceived under a mandate of rigorous budget consciousness and operational minimalism. It demands a durable, low-maintenance, and low-operations architecture that will remain technically sound, highly functional, and easily upgradeable for at least the next two to three years.

This comprehensive research report establishes the foundational architectural directives for the Fabrik platform. It is designed not merely as a theoretical exploration of industry best practices, but as the underlying logic for a permanent, deterministic rule file. This rule file is explicitly tailored to govern autonomous coding agents (such as Cursor, Windsurf, or Cline) operating within the repository. To maximize the leverage of a single developer, these AI agents must act as force multipliers. However, AI agents are probabilistic text generators by nature. Without rigid boundaries, they are prone to introducing architectural drift, hallucinatory dependencies, and fragile, high-maintenance design patterns.

The Fabrik technology stack is strictly defined to eliminate decision fatigue and ensure cross-platform harmony. The development environment utilizes WSL running Ubuntu 24.04, targeting an ARM64 Ubuntu Virtual Private Server (VPS) deployed via Coolify using Docker Compose. The application layer is bifurcated into a Backend-for-Frontend (BFF) model. The backend API utilizes Python, FastAPI, and Uvicorn, coupled with PostgreSQL 16 for persistent storage. The web frontend presentation layer relies on Next.js 14 utilizing the App Router, TypeScript, and Tailwind CSS. Mobile delivery is achieved natively via React Native utilizing TypeScript, while browser extensions are strictly constrained to Google's Manifest V3 specifications. Crucially, containerization is restricted exclusively to Debian slim-bookworm base images, explicitly banning Alpine Linux variants to avoid severe compilation overhead and architectural incompatibilities on ARM64 processors.

This document mitigates operational risk by defining a rigid, file-based memory architecture that enforces software engineering best practices.1 It separates directives into four distinct operational categories: absolute canonical mandates that must govern all AI generation, automated programmatic verifications relegated to a final\_gate.py validation script, static contextual knowledge stored in an AGENTS.md framework, and nuanced subjective decisions reserved exclusively for human guidance. By standardizing on end-to-end type safety via OpenAPI-to-TypeScript code generation 2, deterministic database migrations via Alembic 4, and unified state management principles 6, the Fabrik platform achieves enterprise-grade resilience without the overhead of an enterprise-sized operations team.

## **Canonical Rules for the Agent Rule File**

To guarantee architectural stability and prevent autonomous coding agents from introducing unapproved paradigms, the following canonical rules must be explicitly codified into the agent's system prompt. These represent the absolute "must enforce always" constraints for the Fabrik stack.

* **Strict Containerization Mandate**: All Dockerfiles must exclusively utilize slim-bookworm (Debian 12\) base images for Python and Node.js environments.8 Alpine Linux is strictly prohibited across the entire application stack due to musl libc compatibility issues with pre-compiled Python wheels.8 Images must be pinned to explicit, deterministic tags (e.g., python:3.12-slim-bookworm) rather than relying on the volatile :latest tag.11
* **Deployment Single Source of Truth**: The docker-compose.yml file serves as the absolute single source of truth for Coolify deployments. All environment variables, volume mappings, build contexts, and network configurations must be defined declaratively within this file to ensure infrastructure-as-code principles and prevent configuration drift within the Coolify UI.12
* **Next.js as a Backend-For-Frontend (BFF)**: Next.js 14 must be utilized primarily for routing, server-side rendering, and acting as a secure BFF layer. It must never replace the FastAPI backend for complex business logic, rate limiting, heavy compute, or database interactions.13 Next.js Server Actions are restricted to direct UI mutations, while API Routes must be used when external services require access.14
* **FastAPI Asynchronous Paradigms**: The FastAPI backend must strictly isolate I/O-bound tasks from CPU-bound tasks. The async def syntax is mandated for all I/O operations (database queries, network requests), while standard def (which FastAPI executes in an external thread pool) is required for CPU-intensive computations to prevent blocking the ASGI event loop.15
* **End-to-End Type Synchronization**: Shared types between the Python FastAPI backend and the TypeScript frontends (Next.js and React Native) must be automatically generated using OpenAPI specifications via openapi-ts or similar robust codegen tooling.2 Manual type duplication or manual interface creation across the monorepo is strictly forbidden.17
* **Database Migration Determinism**: All PostgreSQL 16 schema changes must be managed via Alembic. Migrations must be static, reversible, and entirely devoid of dynamically generated data.16 Alembic must be configured with strict naming conventions for constraints to prevent anonymous constraint errors during rollbacks.5
* **React Native Navigation Standard**: Mobile applications must utilize Expo Router for file-based navigation. The traditional React Navigation library is deprecated for new implementations within Fabrik to reduce configuration boilerplate, natively support deep linking, and synchronize web-routing paradigms.19
* **Strict Separation of UI and Logic in Cross-Platform Code**: UI components must never be shared directly between Next.js and React Native due to the differing requirements of DOM and Native runtimes. Code sharing is strictly limited to non-UI logic: Zod validation schemas, TypeScript interface definitions, Zustand global stores, and React Query request hooks.21
* **Chrome Extension Manifest V3 Compliance**: Background processes must be implemented as transient Service Workers. Global variables for state management are banned; all state must persist using chrome.storage.session or chrome.storage.local.22 The setTimeout and setInterval functions are prohibited in background scripts; the chrome.alarms API must be utilized for periodic execution.23
* **Pydantic Validation Boundary**: Data validation must occur exclusively at the Pydantic model boundary. Business logic functions should never manually validate data structures via if/else dictionary checks; they must inherently trust the Pydantic models validated by FastAPI's dependency injection system.16
* **Dependency Injection for Lifecycles**: FastAPI dependency injection must be used for database sessions, caching clients, and external API clients to ensure proper setup and teardown via the Python yield pattern, eliminating resource leaks.26
* **Centralized Error Handling**: The BFF layer (Next.js) must insulate the client from raw backend errors. It must capture 422 Unprocessable Entity or 500 Internal Server Error responses from FastAPI and map them to standardized, user-friendly frontend state objects.13
* **State Management Minimalism**: React and React Native state management must default to local component state (useState). Shared UI state utilizes React Context or Zustand. Server cache state must be handled exclusively by React Query. Heavy global state libraries like Redux are entirely banned from the stack.6
* **Handoff and Documentation Symmetry**: AI agents must adhere to the Memory Bank pattern, explicitly reading the AGENTS.md context file before executing any task and updating architectural decision records prior to task completion.1

## **Anti-Patterns and Banned Practices**

To maintain the durability, performance, and low-maintenance profile of the Fabrik platform, autonomous coding agents must be explicitly instructed to avoid specific practices. These anti-patterns generate technical debt, degrade deployment performance, and complicate the operational responsibilities of a solo developer. The reasoning behind these bans is rooted in the specific constraints of the target deployment environment and the required lifespan of the codebase.

### **The Alpine Linux Fallacy in Python Ecosystems**

One of the most persistent anti-patterns introduced by autonomous coding agents is the default selection of alpine base images for Docker containers. AI models frequently recommend Alpine due to its minimal disk footprint, which often sits under five megabytes. However, in the context of Python applications deployed on ARM64 architectures, this choice represents a severe operational failure.8

Alpine Linux utilizes musl libc as its standard C library, whereas mainstream Linux distributions (like Debian and Ubuntu) utilize glibc.8 The Python ecosystem relies heavily on pre-compiled binaries distributed as "wheels." The vast majority of these wheels are compiled against glibc through the manylinux standard.8 When pip attempts to install dependencies inside an Alpine container, it cannot utilize these pre-compiled manylinux wheels. Consequently, it is forced to download the source code and compile C-extensions (such as numpy, psycopg2, pydantic-core, or cryptography) from scratch during the Docker build process.8

This dynamic increases Docker build times by orders of magnitude—sometimes up to fifty times slower—and requires the installation of heavy system dependencies like build-essential, gcc, and g++ within the Dockerfile.9 Once these build tools are installed, the theoretical size advantage of Alpine is entirely negated. Furthermore, the compiled binaries are often less performant or contain subtle bugs compared to the official manylinux releases.10 Therefore, python:3.x-alpine is strictly banned. The python:3.x-slim-bookworm (Debian 12\) image is the mandated alternative, providing a highly optimized, glibc-compatible environment that installs dependencies in seconds rather than minutes.8

### **The Full-Stack Next.js Monolith**

While modern Next.js 14 provides highly capable API routes and Server Actions, relying on it as a monolithic primary backend for a highly complex application is an architectural anti-pattern for durable systems.13 Next.js excels at server-side rendering, routing, and acting as an integration layer, but it lacks the robust middleware composition, native background task scheduling, and mature Object-Relational Mapping (ORM) integration patterns found in dedicated backend frameworks like FastAPI.13

For the Fabrik platform, agents must treat Next.js exclusively as a Backend-For-Frontend (BFF). Agents must never attempt to implement complex database migrations, heavy asynchronous cron jobs, or computationally intensive tasks directly within the Next.js runtime.13 Instead, Next.js must securely handle HTTP-only cookies, negotiate Cross-Origin Resource Sharing (CORS) with the browser, and proxy sanitized, authenticated requests to the internal FastAPI network.13 Attempting to force Next.js to act as a full-fledged enterprise backend inevitably leads to tangled data-fetching logic and performance bottlenecks that are difficult for a solo developer to untangle.13

### **Synchronous Blocking in the FastAPI Event Loop**

FastAPI achieves its exceptional high performance through the implementation of the Asynchronous Server Gateway Interface (ASGI) standard and a highly optimized asynchronous event loop. A critical failure mode commonly introduced by generative AI is the mixing of synchronous blocking code—such as heavy CPU calculations, image processing, or synchronous database drivers—within an async def routing function.15

When blocking operations are placed inside an async def function, they freeze the entire underlying event loop. This prevents the server from handling any other concurrent requests until the blocking operation completes, effectively degrading the application to a single-threaded, sequential processor.25 Agents must be explicitly programmed to use standard def declarations for synchronous, CPU-bound tasks. When a standard def is used, FastAPI intelligently offloads the execution to an external thread pool, preserving the responsiveness of the main event loop.15 The async def syntax must be reserved strictly for operations that can be await-ed, specifically I/O-bound tasks like network requests or asynchronous database queries via SQLAlchemy.15

### **Imperative Mobile Routing via React Navigation**

Historically the undisputed standard for React Native applications, React Navigation requires extensive imperative boilerplate and complex manual type definitions for nested navigators.19 In a solo developer environment where time is paramount, maintaining this manual mapping creates unacceptable overhead.

Expo Router, which utilizes file-based routing mechanisms and automatically infers TypeScript types from the file system structure, eliminates this boilerplate entirely.19 Furthermore, Expo Router inherently supports robust deep linking and aligns mobile routing paradigms closely with Next.js web routing paradigms, reducing cognitive friction for the developer moving between codebases.19 Consequently, agents must not install or configure @react-navigation/native in any new mobile modules; Expo Router is the sole permitted routing architecture.19

### **Volatile Chrome Extension State Management**

The transition to Chrome Extension Manifest V3 fundamentally altered the extension execution environment by replacing persistent background pages with ephemeral Service Workers.23 These Service Workers spin up to handle specific browser events and terminate immediately when idle to conserve system memory.23

A critical anti-pattern is storing application state in standard global JavaScript variables within the service worker file (e.g., let isUploading \= true;). When the browser terminates the sleeping worker, this data is permanently destroyed, leading to unpredictable extension behavior upon reactivation.23 Agents must be forced to utilize chrome.storage.session for rapid, in-memory persistence that securely survives service worker restarts.22 Furthermore, relying on standard setTimeout or setInterval for polling operations is banned, as the browser will kill the worker and the timers along with it; the chrome.alarms API must be utilized for all scheduled background processing.23

### **Anonymous Database Constraints and Migrations**

When using Alembic in conjunction with SQLAlchemy, relying on the PostgreSQL database engine to auto-generate arbitrary names for constraints (such as Foreign Keys, Unique Constraints, or Check Constraints) causes catastrophic failures during migration rollbacks.18 If a constraint is anonymous, Alembic cannot predictably identify its name to execute a DROP CONSTRAINT command, resulting in a locked migration state.18

Agents must strictly utilize SQLAlchemy's MetaData naming conventions to ensure all constraints are predictably and deterministically named upon creation.5 For example, the convention dictionary must dictate that an index is named ix\_%(column\_0\_label)s and a foreign key is named fk\_%(table\_name)s\_%(column\_0\_name)s\_%(referred\_table\_name)s.5 If an agent generates an Alembic migration containing anonymous constraints, the code must be rejected.

| Architectural Domain | Permitted Practice (Enforce) | Banned Anti-Pattern (Reject) | Rationale for Solo Developer |
| :---- | :---- | :---- | :---- |
| **Container Base Images** | slim-bookworm (Debian 12\) | alpine Linux | Ensures manylinux wheel compatibility; prevents massive compilation delays.8 |
| **Web Backend Logic** | FastAPI \+ Uvicorn | Next.js Server Actions for heavy compute | Preserves Next.js as a lightweight BFF; offloads heavy processing to dedicated API.13 |
| **FastAPI Concurrency** | async def for I/O; def for CPU tasks | Synchronous blocking inside async def | Prevents event loop freezing; ensures high concurrent throughput.15 |
| **Mobile Navigation** | Expo Router (File-based) | React Navigation (Imperative) | Eliminates boilerplate mapping; aligns web/mobile routing paradigms.19 |
| **Extension Background** | Manifest V3 Service Workers \+ Alarms | setInterval / Global Variables | Prevents state loss when browser terminates idle background scripts.23 |
| **Database Migrations** | Deterministic MetaData Constraint Names | Anonymous Database Constraints | Ensures Alembic can reliably downgrade and drop schema modifications.5 |

## **What to Enforce in Execute Handoffs**

In the context of autonomous coding agents, an "execute handoff" occurs when an AI agent shifts context, delegates a sub-task, reaches a logical stopping point, or prepares generated code for human review. Because LLM context windows are finite and heavily prone to "forgetting" earlier instructions as conversations lengthen, the handoff protocol must be meticulously structured.1 For a solo developer, handoffs usually occur between distinct agent sessions (e.g., resuming work on a different day) or when transitioning between domains (e.g., a frontend agent finishing a UI component and signaling a backend agent to map the corresponding API).

Agents must be explicitly instructed to perform the following enforcement actions prior to terminating a generation sequence:

### **1\. Contextual Summarization and Memory Bank Updates**

Before halting execution, the agent must generate a highly structured, precise summary of the current system state, explicitly updating the project's Memory Bank or Architectural Decision Records (ADRs).1 This summary must document the specific files modified, the exact endpoints touched, and any unresolved edge cases. Handoffs must never rely on the LLM's raw conversation history to persist context, as this leads to context overflow and hallucinatory code generation in subsequent sessions.31 The state update must be saved to a persistent markdown file (e.g., docs/ADR/current\_state.md) before the agent relinquishes control.

### **2\. Cross-Boundary Schema Synchronization**

During a handoff that bridges the backend and frontend domains, the agent must explicitly invoke the openapi-ts generation script.3 If the FastAPI schema has been modified, the handoff process must block and require the agent to execute the generation command, subsequently running a TypeScript compiler check (tsc \--noEmit). The handoff is considered invalid if the regenerated Next.js or React Native interfaces fail to compile against the new schema.2 This ensures that type safety is cryptographically enforced across the monorepo boundary at all times.

### **3\. Environment Variable Protocol Verification**

If a newly developed feature introduces required secrets, API keys, or dynamic environment variables, the handoff protocol mandates that the agent adds the empty key definitions to the .env.example file and updates the deployment docker-compose.yml configuration guidelines. Crucially, the agent must intentionally pause execution and prompt the human developer to inject the actual sensitive data into the Coolify UI or the local .env file.12 Agents must be strictly forbidden from hardcoding placeholder secrets (e.g., password123) directly into the application logic.15

### **4\. Migration Readiness and Safety Validation**

If SQLAlchemy database models were modified during the session, the handoff sequence must conclude with the agent successfully staging an Alembic migration file. The agent must verify that the auto-generated migration script possesses a highly descriptive, human-readable slug (e.g., 2026-03-31\_add\_user\_preferences.py) rather than an arbitrary hash.16 Furthermore, the agent must scan the migration file to confirm that it does not rely on dynamically generated runtime data, ensuring the migration remains completely static and reproducible across local and production environments.16

### **5\. Multi-Stage Build Target Clarification**

When Dockerfiles are altered or dependencies are updated, the agent must explicitly specify which stage of the multi-stage build is targeted for the handoff review. For instance, the agent must distinguish between changes made to the builder stage (responsible for resolving uv dependencies and caching wheels) versus the runner stage (responsible for final execution as a non-root user).33 This clarity allows the solo developer to quickly verify security boundaries and image bloat without re-parsing the entire Dockerfile.

## **What to Verify in final\_gate.py**

To enforce the Fabrik standards comprehensively without relying on the inherently non-deterministic nature of LLMs, the platform utilizes a strict, programmatic validation script named final\_gate.py.35 This script functions as a localized Continuous Integration (CI) pipeline, running as a pre-commit or post-save hook directly within the WSL Ubuntu 24.04 environment.37

The agent must be bound by a supreme directive: *Task completion is impossible until final\_gate.py returns an exit code of 0\.* The script executes the following verifications, utilizing native tooling to enforce compliance.

### **Containerization Compliance (Dockerfile AST Parsing)**

The validation script must parse all Dockerfiles located within the repository utilizing regular expressions or a dedicated Abstract Syntax Tree (AST) parser to guarantee absolute compliance with the base image mandate.38

* **Verification**: Ensure all FROM statements stringently match the python:\*-slim-bookworm or node:\*-slim pattern.
* **Fatal Blocker**: Any detection of the strings alpine or latest within a FROM clause triggers an immediate pipeline failure.9
* **External Linter Integration**: The script must invoke hadolint Dockerfile to check for structural best practices, such as combining RUN apt-get update with apt-get install to reduce layer bloat, and enforcing rule DL3020 (Use COPY instead of ADD).39

### **Alembic Migration Integrity and Synchronization**

* **Verification**: The script executes alembic check against the local development database.4 This powerful command compares the currently declared SQLAlchemy MetaData objects in the Python code against the live schema deployed in the local Docker Postgres instance.
* **Fatal Blocker**: If alembic check detects any unmigrated model changes, the script fails immediately, explicitly forcing the agent to generate a new revision via \--autogenerate before proceeding.4
* **Verification**: The script parses the text of the newest migration file located in alembic/versions/ to verify that no anonymous constraints have been inadvertently generated, ensuring downgrade safety.18

### **Code Quality, Formatting, and Static Typing**

* **Verification**: Execute ruff check. and ruff format \--check. across the entire Python backend to ensure PEP-8 compliance, import sorting, and syntax safety.16
* **Fatal Blocker**: Any linting errors, unused imports, or formatting deviations return a non-zero exit code.
* **Verification**: Execute tsc \--noEmit sequentially in both the Next.js and React Native project directories. This verifies absolute type safety across the frontend stack without incurring the computational overhead of actually bundling the JavaScript output.

### **Manifest V3 Security and CSP Checks**

* **Verification**: The script parses the Chrome extension's manifest.json file to ensure structural integrity and security compliance.
* **Fatal Blocker**: The pipeline rejects the code if manifest\_version is not explicitly set to 3\. It rejects the code if deprecated fields like background.scripts are utilized instead of the mandated background.service\_worker.23 Finally, it parses the Content Security Policy (CSP) directives to ensure that inline scripts or eval() functions are strictly blocked, neutralizing cross-site scripting vulnerabilities.22

### **Dependency Lockfile Synchronization**

* **Verification**: Verify that the generated lockfiles (uv.lock for the Python backend and pnpm-lock.yaml or package-lock.json for the Node.js ecosystems) are perfectly synchronized with their respective configuration files (pyproject.toml and package.json). Out-of-sync lockfiles inevitably cause deployment failures on the Coolify VPS.

| Validation Layer | Tooling Required | Target Artifact | Failure Condition |
| :---- | :---- | :---- | :---- |
| **Base Images** | hadolint, Regex Parsing | Dockerfile | Presence of alpine or :latest tags; non-compliant RUN structures.38 |
| **Database Schema** | alembic check | /alembic/versions/ | Detected delta between SQLAlchemy metadata and live database.4 |
| **Backend Code** | ruff | Python Source (.py) | Linting violations, unused dependencies, formatting drift.16 |
| **Frontend Types** | tsc \--noEmit | TypeScript Source (.ts, .tsx) | Type mismatch between OpenAPI generated types and React components.3 |
| **Extension Rules** | JSON Parser | manifest.json | Manifest V2 keys, eval() in CSP, background page declarations.22 |

## **What Belongs in AGENTS.md vs. AGENTS-compact.md**

Modern Agentic IDEs (like Cursor) and CLI agents (like Cline) rely on system prompts and memory files to understand their operating environment. However, LLM context windows represent a finite economy.1 Injecting a massive, 10,000-word architectural treatise into every single prompt exponentially increases API latency, drives up token costs, and heavily dilutes the model's attention mechanism, leading to degraded code generation. Therefore, contextual knowledge must be strictly stratified into an exhaustive reference document (AGENTS.md) and a highly compressed execution prompt (AGENTS-compact.md).

### **AGENTS.md (The Exhaustive Context)**

This file serves as the comprehensive architectural reference repository. It is not injected into every prompt. Instead, it is read explicitly by the agent during high-level planning phases, major system refactors, or when a new sub-agent is spawned to map out a highly complex feature implementation.43

* **System Architecture Visualization**: A detailed textual representation of the Coolify deployment topology, illustrating how the Docker Compose network isolates the Next.js container, routes internal traffic to the FastAPI container, and persistently mounts the PostgreSQL database volumes.12
* **Memory Bank Mechanics**: Deep explanations of how Product Requirements Documents (PRDs) map to the docs/ folder, and explicit instructions on how the agent should search and read past Architectural Decision Records (ADRs) to understand historical context.1
* **Data Flow and Security Mechanics**: Detailed explanations of the Backend-For-Frontend (BFF) pattern lifecycle. It documents exactly how a React Native client or Web client requests data, how Next.js intercepts that request, applies HTTP-only session cookies for security, and forwards the heavily authenticated Bearer token request to the internal FastAPI network.13
* **Extensive Troubleshooting History**: Historical context on edge cases specific to the solo developer's environment. This includes strategies for resolving WSL 2 networking constraints with local Docker, or methodologies for mitigating Coolify ARM64 build server RAM limitations via Swapfile configuration or Nixpacks tuning.45

### **AGENTS-compact.md (The Execution Context)**

This is a highly compressed, rule-dense markdown file injected directly into the system prompt for every single interaction. It contains absolutely no philosophical justifications, historical context, or conversational filler—only executable constraints.

* **Core Tech Stack Enumeration**: Exact version requirements (Python 3.12, Node 20, Postgres 16, Next.js 14, Expo SDK).
* **Banned Vocabulary Array**: A minimalist string array for quick attention filtering: \[alpine, react-navigation, redux, pip, requirements.txt, background\_page, setInterval\].
* **Directory Layout Tree**: A minimalist ASCII tree mapping the monorepo boundaries: /backend, /web, /mobile, /extension.
* **Validation Command Directive**: The single command required to trigger validation: Execute./final\_gate.py prior to completion.
* **Formatting Imperatives**: "Use Ruff. Use Prettier. End files with a newline. Never leave dead code. Do not apologize."

### **What to Leave as Human Guidance Only**

While autonomous agents excel at generating boilerplate, enforcing typings, and orchestrating standard APIs, they possess inherent blind spots. Attempting to force an LLM to govern subjective domains inevitably leads to endless prompt engineering loops and frustrating, robotic outputs. For a solo developer, time is better spent applying human intuition to the following areas, explicitly omitting them from the agent rule files:

* **UI/UX Aesthetic Alignment and "Taste"**: Agents are exceptionally poor at designing cohesive, delightful user interfaces. While they can implement Tailwind utility classes based on strict wireframes, the overarching design system, spacing rhythms, micro-interactions, and visual hierarchy must be driven by human taste. Agents should only be tasked with building the structural components, leaving the aesthetic polish to the developer.
* **Subjective Component Splitting**: The decision of when to abstract a React component into smaller, reusable sub-components is often more art than science, depending heavily on future product roadmaps that the agent cannot foresee. Over-instructing the agent on component architecture leads to premature optimization and deeply fragmented file structures.
* **Complex Algorithmic Tuning and Postgres Query Optimization**: While agents can write basic SQL and implement standard indexing, complex database tuning—such as analyzing EXPLAIN ANALYZE outputs, configuring multi-column partial indexes for specific business queries, or tuning PostgreSQL memory parameters for a specific 4GB RAM VPS—requires deep human contextual awareness of actual data distribution and traffic patterns.47
* **Product Feature Prioritization**: The agent must never be allowed to dictate the product roadmap or decide which edge cases are worth ignoring. The solo developer must hold the absolute authority on feature scope to prevent scope creep.

## **Minimal Practical Examples for the Fabrik Stack**

To anchor the AI agent's generative parameters and prevent hallucinated syntax, precise, practical examples must be provided. These examples demonstrate the specific flavor of the stack mandated by the Fabrik architecture.

### **Example 1: The Dockerfile Mandate (Backend)**

This example highlights the required multi-stage build pattern, the strict avoidance of Alpine in favor of slim-bookworm, the utilization of the uv package manager for incredibly rapid dependency resolution, and the security best practice of running the final container as a non-root user.48

Dockerfile

\# syntax=docker/dockerfile:1
\# STAGE 1: Builder \- Uses slim-bookworm, NEVER alpine
FROM python:3.12\-slim-bookworm AS builder
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

\# Install 'uv' for rapid, deterministic dependency resolution
COPY \--from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock./
\# Sync dependencies without relying on legacy pip/requirements.txt
RUN uv sync \--frozen \--no-cache

\# STAGE 2: Runner \- Minimal footprint for production deployment
FROM python:3.12\-slim-bookworm AS runner
WORKDIR /app

\# Create non-root user for strict container security
RUN useradd \-m fabrik\_user
COPY \--from=builder /app/.venv /app/.venv
COPY./src./src

\# Drop privileges
USER fabrik\_user
ENV PATH="/app/.venv/bin:$PATH"

\# Execute Uvicorn utilizing the virtual environment
CMD \["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"\]

### **Example 2: Next.js Server Action vs. API Route (The BFF Pattern)**

This code block clarifies the boundary between internal UI mutations and external API integrations, reinforcing Next.js as an intermediary Backend-For-Frontend.14

TypeScript

// app/actions/user.ts
'use server'
import { z } from 'zod';
import { cookies } from 'next/headers';

// SERVER ACTION: Exclusively for direct usage by Next.js React components (e.g., Web Forms)
export async function updateProfile(formData: FormData) {
  const name \= formData.get('name');
  const sessionToken \= cookies().get('session')?.value;

  // Proxy request to the internal FastAPI backend network
  const res \= await fetch('http://backend:8000/api/users', {
    method: 'POST',
    body: JSON.stringify({ name }),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': \`Bearer ${sessionToken}\`
    }
  });

  if (\!res.ok) throw new Error("Failed to update profile");
  return await res.json();
}

// app/api/webhooks/stripe/route.ts
// API ROUTE: Exposing a public endpoint for external services
export async function POST(req: Request) {
  const body \= await req.text();
  // Validate external signature, then process webhook data
  // External services CANNOT call Server Actions directly
  return new Response(JSON.stringify({ status: 'ok' }), { status: 200 });
}

### **Example 3: Coolify Docker Compose (The Single Source of Truth)**

This demonstrates handling database provisioning and environment variable mapping directly within code, avoiding fragile manual GUI configurations in the Coolify dashboard.12

YAML

services:
  api:
    build:
      context:./backend
      dockerfile: Dockerfile
    environment:
      \# Internal routing utilizing Docker Compose DNS
      \- DATABASE\_URL=postgresql://fabrik\_user:${DB\_PASSWORD}@postgres:5432/fabrik
    depends\_on:
      postgres:
        condition: service\_healthy
  web:
    build:
      context:./web
      dockerfile: Dockerfile
    ports:
      \- "3000:3000"
  postgres:
    \# ONLY EXCEPTION TO ALPINE RULE: Official infrastructure images
    image: postgres:16-alpine
    volumes:
      \- fabrik\_db\_data:/var/lib/postgresql/data
    environment:
      \- POSTGRES\_USER=fabrik\_user
      \- POSTGRES\_PASSWORD=${DB\_PASSWORD}
      \- POSTGRES\_DB=fabrik
    healthcheck:
      test:
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  fabrik\_db\_data:

### **Example 4: Chrome MV3 State Persistence Mechanics**

Demonstrating the secure survival of application state across ephemeral service worker lifecycles, replacing legacy global variables with the Chrome Storage API and Alarms.22

JavaScript

// background.js (Manifest V3 Service Worker)

// INITIALIZATION: Runs only when the extension is installed/updated
chrome.runtime.onInstalled.addListener(() \=\> {
  // Initialize state in session storage, strictly avoiding global variables
  chrome.storage.session.set({ processingQueue: });

  // Create an alarm instead of using the banned setInterval function
  chrome.alarms.create('queueProcessor', { periodInMinutes: 5 });
});

// EXECUTION: Wakes the service worker periodically
chrome.alarms.onAlarm.addListener(async (alarm) \=\> {
  if (alarm.name \=== 'queueProcessor') {
    // Retrieve state from persistent session storage
    const { processingQueue } \= await chrome.storage.session.get('processingQueue');

    if (processingQueue && processingQueue.length \> 0) {
      console.log("Processing background queue...", processingQueue);
      // Execute required network fetch or sync...
    }
  }
});

## ---

**Recommended Final Content for the Rule File**

The following markdown payload is precisely formulated to be saved directly as .cursorrules, .clinerules, or AGENTS-compact.md within the root directory of the Fabrik monorepo. It utilizes deterministic phrasing, categorizes constraints logically for LLM ingestion, and integrates directly with the final\_gate.py programmatic pipeline.

# **Fabrik Agent Architectural Directives**

**Identity**: You are an expert Principal Engineer operating autonomously on the Fabrik platform. You execute tasks meticulously, optimizing for durability, extreme low-maintenance, and low-ops paradigms strictly tailored for a solo developer operating under strict time constraints.

## **1\. Core Stack Constraints**

* **Backend**: Python 3.12+, FastAPI, Uvicorn, PostgreSQL 16\. Dependency management is executed strictly via uv.
* **Frontend (Web)**: Next.js 14 (App Router), TypeScript, Tailwind CSS.
* **Frontend (Mobile)**: React Native, Expo Router.
* **Browser Extension**: Manifest V3 specifications ONLY.
* **Deployment**: ARM64 Ubuntu VPS via Coolify. docker-compose.yml serves as the absolute, overriding single source of truth.

## **2\. Unbreakable Technical Mandates**

### **Containerization**

* **NEVER** utilize alpine Linux base images for Python or Node.js Dockerfiles. Alpine relies on musl libc, destroying Python manylinux wheel compatibility and catastrophically halting ARM64 builds.
* **ALWAYS** utilize slim-bookworm (Debian 12\) for application base images (e.g., python:3.12-slim-bookworm).
* Multi-stage Docker builds are mandatory. Final production stages must drop root privileges and execute as a non-root user.

### **Backend Architecture (FastAPI & DB)**

* **Async Isolation**: Utilize async def EXCLUSIVELY for I/O operations (Database queries, external API calls). Utilize standard def for CPU-intensive calculations to leverage thread pooling and prevent ASGI event loop freezing.
* **Pydantic Boundaries**: Validate all data at the boundaries using Pydantic models. Never write manual dictionary validation logic within business functions.
* **Database Migrations**: Utilize Alembic. Migrations must be statically defined and highly deterministic. Never auto-generate anonymous constraints; utilize SQLAlchemy MetaData naming conventions (ix\_, fk\_, pk\_) to ensure safe rollbacks.

### **Frontend Architecture (Next.js & React Native)**

* **The BFF Pattern**: Next.js functions strictly as a Backend-for-Frontend. It handles HTTP-only auth cookies, normalizes external data, and protects the client. It MUST NOT replace FastAPI for core business logic, cron jobs, or heavy DB interactions.
* **Server Actions vs API Routes**: Utilize Server Actions exclusively for internal web UI mutations. Utilize API Routes when exposing public endpoints for external consumers (React Native app, third-party webhooks).
* **Mobile Navigation**: Utilize Expo Router. The legacy @react-navigation/native library is BANNED.
* **Code Sharing**: Do NOT attempt to share DOM-dependent UI components between Web and Mobile. Share ONLY TypeScript interfaces, Zod validation schemas, React Query hooks, and Zustand data stores.
* **Type Synchronization**: End-to-end type safety is mandatory. Utilize OpenAPI-to-TypeScript code generation; never manually duplicate backend Pydantic types to the TypeScript frontend.

### **Extension Architecture (Manifest V3)**

* Service workers terminate unpredictably based on browser resource constraints. **NEVER** utilize standard global variables to store state.
* Utilize chrome.storage.session for rapid, ephemeral data persistence, and chrome.storage.local for long-term persistence.
* setTimeout and setInterval functions are BANNED in background scripts. Utilize chrome.alarms for asynchronous scheduling.

## **3\. Execution and Handoff Protocols**

1. **Planning Phase**: Before generating code, read .env.example and docker-compose.yml to fully understand the infrastructure boundaries and network layout.
2. **Context Retention**: Never assume the LLM context window remembers instructions from previous sessions. Write rigorous state updates to docs/ADR/ when completing major components or pausing work.
3. **The Final Gate**: You must execute python scripts/final\_gate.py locally via bash before marking any assigned task as complete. This script programmatically runs hadolint, alembic check, ruff check, and tsc \--noEmit.
   * If final\_gate.py returns an error, you must autonomously debug the code and rerun the script.
   * A task is ONLY considered complete when the final exit code is 0\.

## **4\. Anti-Patterns (NEVER Execute These)**

* Do not invent custom error payload structures. Rely on standard HTTP status codes parsed by the Next.js BFF.
* Do not store secrets or API keys in frontend code. Next.js server components handle secrets via environment variables.
* Do not install heavy state libraries like Redux. Utilize local state first, React Query for remote caching, and Zustand for critical global UI state.
* Do not instruct the user to configure deployment settings manually in the Coolify UI; always update the docker-compose.yml declarative configuration.

#### **Works cited**

1. The Ultimate Rules Template for CLINE/Cursor/RooCode/Windsurf that Actually Makes AI Remember Everything\! (w/ Memory Bank & Software Engineering Best Practices) \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/ChatGPTCoding/comments/1jghell/the\_ultimate\_rules\_template\_for/](https://www.reddit.com/r/ChatGPTCoding/comments/1jghell/the_ultimate_rules_template_for/)
2. Types sync for frontend : r/FastAPI \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1l33x1k/types\_sync\_for\_frontend/](https://www.reddit.com/r/FastAPI/comments/1l33x1k/types_sync_for_frontend/)
3. GitHub \- hey-api/openapi-ts: OpenAPI to TypeScript codegen. Production-ready SDKs, Zod schemas, TanStack Query hooks, and 20+ plugins. Used by Vercel, OpenCode, and PayPal., accessed March 31, 2026, [https://github.com/hey-api/openapi-ts](https://github.com/hey-api/openapi-ts)
4. Alembic Database Migrations: The Complete Developer's Guide | by Tejpal Kumawat, accessed March 31, 2026, [https://medium.com/@tejpal.abhyuday/alembic-database-migrations-the-complete-developers-guide-d3fc852a6a9e](https://medium.com/@tejpal.abhyuday/alembic-database-migrations-the-complete-developers-guide-d3fc852a6a9e)
5. The Importance of Naming Constraints — Alembic 1.18.4 documentation \- SQLAlchemy, accessed March 31, 2026, [https://alembic.sqlalchemy.org/en/latest/naming.html](https://alembic.sqlalchemy.org/en/latest/naming.html)
6. React State Management in 2025: What You Actually Need \- Developer Way, accessed March 31, 2026, [https://www.developerway.com/posts/react-state-management-2025](https://www.developerway.com/posts/react-state-management-2025)
7. Mastering React State Management at Scale in 2025 \- DEV Community, accessed March 31, 2026, [https://dev.to/ash\_dubai/mastering-react-state-management-at-scale-in-2025-52e8](https://dev.to/ash_dubai/mastering-react-state-management-at-scale-in-2025-52e8)
8. How to Choose Between Alpine and Debian-Slim Base Images \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-08-how-to-choose-between-alpine-and-debian-slim-base-images/view](https://oneuptime.com/blog/post/2026-02-08-how-to-choose-between-alpine-and-debian-slim-base-images/view)
9. 4 Dockerfile Best Practices You Must Get Acclaimed with in 2023 | by Oren Spiegel | Medium, accessed March 31, 2026, [https://medium.com/analytics-vidhya/4-dockerfile-best-practices-you-must-get-acclaimed-with-in-2023-fbf357e30c07](https://medium.com/analytics-vidhya/4-dockerfile-best-practices-you-must-get-acclaimed-with-in-2023-fbf357e30c07)
10. Alpine vs python-slim for deploying python data science stack? : r/docker \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/docker/comments/g5hb93/alpine\_vs\_pythonslim\_for\_deploying\_python\_data/](https://www.reddit.com/r/docker/comments/g5hb93/alpine_vs_pythonslim_for_deploying_python_data/)
11. Best practices for containerizing Python applications with Docker \- Snyk, accessed March 31, 2026, [https://snyk.io/blog/best-practices-containerizing-python-docker/](https://snyk.io/blog/best-practices-containerizing-python-docker/)
12. Docker Compose | Coolify Docs, accessed March 31, 2026, [https://coolify.io/docs/knowledge-base/docker/compose](https://coolify.io/docs/knowledge-base/docker/compose)
13. The Problem With NextJS. A backend for frontend \- not a backend ..., accessed March 31, 2026, [https://mattburgess.medium.com/the-problem-with-nextjs-e44fd4c99d20](https://mattburgess.medium.com/the-problem-with-nextjs-e44fd4c99d20)
14. Next.js Server Actions vs API Routes: Don't Build Your App Until You Read This, accessed March 31, 2026, [https://dev.to/myogeshchavan97/nextjs-server-actions-vs-api-routes-dont-build-your-app-until-you-read-this-4kb9](https://dev.to/myogeshchavan97/nextjs-server-actions-vs-api-routes-dont-build-your-app-until-you-read-this-4kb9)
15. FastAPI Best Practices: A Complete Guide for Building Production-Ready APIs \- Medium, accessed March 31, 2026, [https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617](https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617)
16. FastAPI Best Practices and Conventions we used at our startup \- GitHub, accessed March 31, 2026, [https://github.com/zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)
17. How to share types between React frontend and Express backend (in TS) in a monorepo?, accessed March 31, 2026, [https://www.reddit.com/r/typescript/comments/1j138xs/how\_to\_share\_types\_between\_react\_frontend\_and/](https://www.reddit.com/r/typescript/comments/1j138xs/how_to_share_types_between_react_frontend_and/)
18. How to migrate naming convention? · sqlalchemy alembic · Discussion \#906 \- GitHub, accessed March 31, 2026, [https://github.com/sqlalchemy/alembic/discussions/906](https://github.com/sqlalchemy/alembic/discussions/906)
19. Expo Router vs React Navigation: How They Compare \- NativeLaunch, accessed March 31, 2026, [https://nativelaunch.dev/articles/compare/expo-router-vs-react-navigation](https://nativelaunch.dev/articles/compare/expo-router-vs-react-navigation)
20. Exploring Navigation Solutions in React Native: Expo Router vs. React Navigation \- Medium, accessed March 31, 2026, [https://medium.com/@pallavi8khedle/exploring-navigation-solutions-in-react-native-expo-router-vs-react-navigation-37c270d45a7b](https://medium.com/@pallavi8khedle/exploring-navigation-solutions-in-react-native-expo-router-vs-react-navigation-37c270d45a7b)
21. Reflecting on Code Sharing Between React and React Native \- Matt Wolfe, accessed March 31, 2026, [https://matthewwolfe.github.io/blog/code-sharing-react-and-react-native](https://matthewwolfe.github.io/blog/code-sharing-react-and-react-native)
22. Understanding Chrome Extensions: A Developer's Guide to Manifest V3 \- DEV Community, accessed March 31, 2026, [https://dev.to/javediqbal8381/understanding-chrome-extensions-a-developers-guide-to-manifest-v3-233l](https://dev.to/javediqbal8381/understanding-chrome-extensions-a-developers-guide-to-manifest-v3-233l)
23. Migrate to a service worker \- Chrome for Developers, accessed March 31, 2026, [https://developer.chrome.com/docs/extensions/develop/migrate/to-service-workers](https://developer.chrome.com/docs/extensions/develop/migrate/to-service-workers)
24. Building persistent Chrome Extension using Manifest V3 | by Rahul Negi \- Medium, accessed March 31, 2026, [https://rahulnegi20.medium.com/building-persistent-chrome-extension-using-manifest-v3-198000bf1db6](https://rahulnegi20.medium.com/building-persistent-chrome-extension-using-manifest-v3-198000bf1db6)
25. 15 FastAPI Best Practices For Production \- YouTube, accessed March 31, 2026, [https://www.youtube.com/watch?v=kmJz8w5ij8Y](https://www.youtube.com/watch?v=kmJz8w5ij8Y)
26. Best Practices in FastAPI Architecture: A Complete Guide to Building Scalable, Modern APIs, accessed March 31, 2026, [https://zyneto.com/blog/best-practices-in-fastapi-architecture](https://zyneto.com/blog/best-practices-in-fastapi-architecture)
27. Mastering State Management in React Native Apps in 2025: A Comprehensive Guide | by praveen sharma | Medium, accessed March 31, 2026, [https://medium.com/@sharmapraveen91/mastering-state-management-in-react-native-apps-in-2025-a-comprehensive-guide-5399b6693dc1](https://medium.com/@sharmapraveen91/mastering-state-management-in-react-native-apps-in-2025-a-comprehensive-guide-5399b6693dc1)
28. Building Minimal Docker Containers for Python Applications \- Real Kinetic Blog, accessed March 31, 2026, [https://blog.realkinetic.com/building-minimal-docker-containers-for-python-applications-37d0272c52f3](https://blog.realkinetic.com/building-minimal-docker-containers-for-python-applications-37d0272c52f3)
29. Extensions / Manifest V3 \- Chrome for Developers, accessed March 31, 2026, [https://developer.chrome.com/docs/extensions/develop/migrate/what-is-mv3](https://developer.chrome.com/docs/extensions/develop/migrate/what-is-mv3)
30. What's new in Chrome extensions \- Chrome for Developers, accessed March 31, 2026, [https://developer.chrome.com/docs/extensions/whats-new](https://developer.chrome.com/docs/extensions/whats-new)
31. designing ai agent handoffs to humans, what's the least jarring approach \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/AI\_Agents/comments/1r6r54e/designing\_ai\_agent\_handoffs\_to\_humans\_whats\_the/](https://www.reddit.com/r/AI_Agents/comments/1r6r54e/designing_ai_agent_handoffs_to_humans_whats_the/)
32. Using bash scripting to get AI Agents make suggestions directly in the terminal \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/AI\_Agents/comments/1i2olbq/using\_bash\_scripting\_to\_get\_ai\_agents\_make/](https://www.reddit.com/r/AI_Agents/comments/1i2olbq/using_bash_scripting_to_get_ai_agents_make/)
33. Coolify: Deploying your app with Docker Compose | by Italo Baeza Cabrera \- Medium, accessed March 31, 2026, [https://darkghosthunter.medium.com/coolify-deploying-your-app-with-docker-compose-8f85c8ae3d9a](https://darkghosthunter.medium.com/coolify-deploying-your-app-with-docker-compose-8f85c8ae3d9a)
34. Building best practices \- Docker Docs, accessed March 31, 2026, [https://docs.docker.com/build/building/best-practices/](https://docs.docker.com/build/building/best-practices/)
35. Building shared coding guidelines for AI (and people too) \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.blog/2026/03/26/coding-guidelines-for-ai-agents-and-people-too/](https://stackoverflow.blog/2026/03/26/coding-guidelines-for-ai-agents-and-people-too/)
36. Claude Code auto mode: a safer way to skip permissions \- Anthropic, accessed March 31, 2026, [https://www.anthropic.com/engineering/claude-code-auto-mode](https://www.anthropic.com/engineering/claude-code-auto-mode)
37. Automated Code Validation: How Post-Save Hooks Turn AI Into a Reliable Coding Partner, accessed March 31, 2026, [https://medium.com/@peterphonix/automated-code-validation-how-post-save-hooks-turn-ai-into-a-reliable-coding-partner-567beb5bca1c](https://medium.com/@peterphonix/automated-code-validation-how-post-save-hooks-turn-ai-into-a-reliable-coding-partner-567beb5bca1c)
38. How to Parse and Analyze Dockerfiles Programmatically \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-08-how-to-parse-and-analyze-dockerfiles-programmatically/view](https://oneuptime.com/blog/post/2026-02-08-how-to-parse-and-analyze-dockerfiles-programmatically/view)
39. How to Lint Dockerfiles with Hadolint \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-08-how-to-lint-dockerfiles-with-hadolint/view](https://oneuptime.com/blog/post/2026-02-08-how-to-lint-dockerfiles-with-hadolint/view)
40. docker \- Is there a way to lint the Dockerfile? \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/28182047/is-there-a-way-to-lint-the-dockerfile](https://stackoverflow.com/questions/28182047/is-there-a-way-to-lint-the-dockerfile)
41. A practical guide to Manifest V3 migration : r/chrome\_extensions \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/chrome\_extensions/comments/1rwvp4x/a\_practical\_guide\_to\_manifest\_v3\_migration/](https://www.reddit.com/r/chrome_extensions/comments/1rwvp4x/a_practical_guide_to_manifest_v3_migration/)
42. Optimizing Coding Agent Rules (./clinerules) for Improved Accuracy \- Arize AI, accessed March 31, 2026, [https://arize.com/blog/optimizing-coding-agent-rules-claude-md-agents-md-clinerules-cursor-rules-for-improved-accuracy/](https://arize.com/blog/optimizing-coding-agent-rules-claude-md-agents-md-clinerules-cursor-rules-for-improved-accuracy/)
43. Best practices for coding with agents \- Cursor, accessed March 31, 2026, [https://cursor.com/blog/agent-best-practices](https://cursor.com/blog/agent-best-practices)
44. Scaling Coolify for Production: From Localhost to Distributed Server Architecture \- Medium, accessed March 31, 2026, [https://medium.com/@meihol/scaling-coolify-for-production-from-localhost-to-distributed-server-architecture-4af8fcb1c06e](https://medium.com/@meihol/scaling-coolify-for-production-from-localhost-to-distributed-server-architecture-4af8fcb1c06e)
45. Build Server | Coolify Docs, accessed March 31, 2026, [https://coolify.io/docs/knowledge-base/server/build-server](https://coolify.io/docs/knowledge-base/server/build-server)
46. Building performance issues and alternatives : r/coolify \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/coolify/comments/1l9tryg/building\_performance\_issues\_and\_alternatives/](https://www.reddit.com/r/coolify/comments/1l9tryg/building_performance_issues_and_alternatives/)
47. Deploy Applications with Coolify on RamNode VPS | Complete Guide, accessed March 31, 2026, [https://ramnode.com/guides/coolify](https://ramnode.com/guides/coolify)
48. Docker Best Practices for Python Developers \- TestDriven.io, accessed March 31, 2026, [https://testdriven.io/blog/docker-best-practices/](https://testdriven.io/blog/docker-best-practices/)
49. This Is How You Write an Efficient Python Dockerfile \- YouTube, accessed March 31, 2026, [https://www.youtube.com/watch?v=tc713anE3UY](https://www.youtube.com/watch?v=tc713anE3UY)
50. Server Actions With Own Backend : r/nextjs \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/nextjs/comments/18vable/server\_actions\_with\_own\_backend/](https://www.reddit.com/r/nextjs/comments/18vable/server_actions_with_own_backend/)
51. Docker Compose Build Packs | Coolify Docs, accessed March 31, 2026, [https://coolify.io/docs/applications/build-packs/docker-compose](https://coolify.io/docs/applications/build-packs/docker-compose)
