# **Testing Strategy and Rule File Specification for Fabrik**

## **Executive Summary**

The transition toward artificial intelligence-assisted software development fundamentally alters the economics and execution of application testing. Historically, software engineering has been constrained by the time required to write implementation code, making exhaustive, granular unit testing a logical safeguard against human error. However, when an autonomous coding agent is capable of generating thousands of lines of functional code in a matter of minutes, the primary development bottleneck shifts rapidly from code creation to code verification and architectural maintenance.1 For a solo developer managing a complex, multi-platform stack—comprising a Python FastAPI backend, a Next.js 14 frontend, a React Native mobile application, and a Manifest V3 Chrome Extension—traditional testing paradigms become a liability rather than an asset.

The analysis indicates that the highest-return-on-investment (ROI) approach for the Fabrik platform is the adoption of the "Testing Trophy" or "Honeycomb" model.3 This model deliberately depreciates the value of isolated unit tests in favor of robust integration and contract testing. The traditional "Testing Pyramid" dictates a massive base of unit tests that inherently bind to implementation details.5 When AI agents rapidly refactor these implementation details to optimize performance or add features, highly coupled unit tests break, creating a maintenance nightmare that paralyzes velocity and introduces severe friction into the continuous integration pipeline.5 Instead, the strategy must mandate behavioral verification: testing what the application actually does from the user's perspective, rather than evaluating the specific syntax or private methods of the internal functions.5

Furthermore, operating within the specific environmental constraints of Fabrik—developing within Windows Subsystem for Linux (WSL) on Ubuntu 24.04 and deploying to an ARM64 Virtual Private Server (VPS) via Coolify—demands infrastructure-aware testing protocols. I/O boundaries dictate that all code must remain strictly within the native Linux filesystem to prevent catastrophic performance degradation during local test execution and hot-module replacement (HMR).7 Base images for testing and deployment must rely exclusively on Debian-based slim-bookworm distributions, unequivocally banning Alpine Linux to avoid the high-maintenance compilation overhead associated with musl libc when installing Python wheels and Node.js native modules.

The testing architecture must also address the specific idiosyncrasies of the chosen frameworks. Next.js 14 Server Components render traditional DOM-based unit testing obsolete, necessitating a reliance on Playwright for end-to-end verification.10 Backend testing must interact with real PostgreSQL 16 instances rather than mocked abstractions, as mocking ORM sessions frequently masks critical transaction deadlocks and unique constraint violations.13 Mobile testing must eschew highly coupled, gray-box frameworks like Detox in favor of resilient, black-box YAML-driven automation via Maestro.15

This exhaustive report delineates the theoretical foundations, the architectural mechanisms, and the strict operational constraints necessary to define the Fabrik testing strategy. It establishes the canonical rules, identifies critical anti-patterns, and constructs the execution handoff requirements required to build the permanent 45-testing-strategy.md rule file. The resulting guidelines are engineered to be durable, maintenance-light, and strictly enforceable by automated gatekeeping scripts, ensuring that AI agents contribute to a resilient codebase capable of scaling over the next several years.

## **The Economics of AI-Assisted Testing and the ROI Model**

For a single developer working approximately 50 focused hours per week, test maintenance operates as a direct and compounding tax on feature development. The introduction of AI coding agents multiplies the volume of code produced, and consequently, the volume of potential regressions multiplies at an equivalent or greater rate.1 Without a mathematically rigorous approach to testing ROI, the solo developer risks spending the majority of their operational hours debugging test suites rather than shipping user-facing value.

### **Mathematical Modeling of Testing ROI**

The value of a software test is not static; it is a function of its ability to catch critical failures weighed against the time required to create and maintain it over the software's lifecycle. This dynamic can be modeled mathematically to determine the highest-leverage activities for a solo developer utilizing AI assistants:

![][image1]
In this equation, ![][image2] represents the business cost of a bug reaching production, ![][image3] represents the probability of the test successfully catching that specific regression, ![][image4] is the initial time investment to author the test, and ![][image5] is the ongoing time required to update the test when the underlying code changes.

The introduction of advanced Large Language Models (LLMs) and AI coding agents fundamentally disrupts this equation. Because an AI agent can generate test boilerplate and implementation code near-instantaneously, ![][image4] approaches zero.17 Consequently, the denominator is dominated almost entirely by ![][image6]. Therefore, the optimal strategy for Fabrik must strictly filter out any testing methodologies where ![][image5] is high. A test suite with even a 5% flakiness rate becomes wholly unreliable, conditioning developers to ignore test outputs and destroying the continuous integration feedback loop.19

### **The "Testing Trophy" vs. The "Testing Pyramid"**

For decades, the standard architectural doctrine was the "Testing Pyramid," coined by Mike Cohn, which prescribed a voluminous foundation of unit tests, a smaller middle layer of integration tests, and a microscopic apex of end-to-end (E2E) UI tests.5 While this model proved adequate for logic-heavy, monolithic backend systems, it is demonstrably disastrous for modern, highly distributed, full-stack applications heavily reliant on asynchronous boundaries and third-party APIs.5

The analysis indicates that Fabrik must adopt the "Testing Trophy" paradigm.3 This model redistributes testing priorities to maximize ROI in a modern environment. The base of the trophy relies entirely on robust static analysis—TypeScript strict mode, ESLint, and OpenAPI schema generation—which provides mathematical guarantees about data shapes with zero maintenance overhead.5 The massive center of the trophy consists of integration tests, which verify that the database, the backend orchestration, and the frontend data-fetching layers communicate correctly.3 Unit tests are relegated to a minimal sliver, used exclusively for isolated, complex algorithmic transformations.22

### **The One-Test Rule Optimization**

A central tenet of the Fabrik testing philosophy is the "One-Test Rule." When test execution is computationally expensive or when test maintenance is high, optimizing the number of executed paths is critical.23 The One-Test Rule stipulates that for the vast majority of standard application features—such as user registration, basic CRUD operations, or data visualization—a single, high-fidelity integration test that successfully traverses the "happy path" of the entire application stack provides exponentially more value than dozens of isolated unit tests covering every conceivable minor edge case.23

This optimization acknowledges that AI agents excel at pattern matching and standard implementation but occasionally hallucinate structural boundaries.1 A single test that verifies a user can create an account, log in, and view their dashboard inherently verifies the database connection, the password hashing utility, the JWT middleware, the Next.js server-side rendering execution, and the client-side state management.

### **Avoiding Over-Testing and the 19% Penalty**

Over-engineering tests is a primary source of technical debt.25 Teams striving for arbitrary metrics, such as 100% test coverage, inevitably automate trivial cases, such as UI alignment or cosmetic text, which are better verified through visual inspection or left to standard component libraries.25

Recent randomized controlled trials have demonstrated the hidden costs of integrating AI coding tools. In specific scenarios involving experienced developers working on familiar codebases, the use of AI tools actually increased issue completion time by 19%.17 This paradoxical slowdown is attributed to the cognitive load required to review, verify, and write tests for the massive volume of code generated by the AI.17 To counteract this, Fabrik must rigorously avoid overly broad assertions and excessive abstraction in test code, ensuring that when an AI generates a feature, the accompanying test is singular, readable, and highly focused on the core business logic.25

## **Test Categorization by Ticket Type and Scope**

To maintain velocity, a solo developer must not approach every feature with a uniform testing rigor. The testing requirements must be systematically mapped to the specific nature of the change being introduced. This mapping defines the default "minimum test" for various ticket types, establishing a standard that AI agents can autonomously follow.

### **Minimum Test Requirements by Development Task**

The table below outlines the strict testing requirements categorized by the type of work being executed. This matrix serves as the operational baseline for both human execution and AI agent prompting.

| Ticket Classification | Definition & Scope | Mandatory Minimum Testing Requirement |
| :---- | :---- | :---- |
| **New Feature (Backend)** | Creation of new API endpoints, database models, or core business logic in FastAPI. | One integration test utilizing pytest and TestClient executing against a local PostgreSQL instance. Must verify HTTP status and response schema. |
| **New Feature (Frontend)** | Introduction of new Next.js routes, complex interactive components, or data-fetching layers. | One Playwright E2E test verifying the user's "happy path." Assertions must target semantic accessibility roles (e.g., getByRole), never CSS classes. |
| **Bugfix** | Resolution of an identified defect in production or staging environments. | One Regression Test. The agent must first write a test that reliably fails by reproducing the bug, then implement the fix to ensure the test passes. |
| **Refactor** | Restructuring existing code without altering external behavior or user-facing functionality. | Zero new tests required. Existing integration and smoke tests must pass. If previous tests were brittle unit tests, they should be deleted and replaced with a single integration test. |
| **Chore / Infrastructure** | Dependency upgrades, CI/CD pipeline modifications, or static asset updates. | Zero new tests required. The automated deployment pipeline must rely on existing Smoke Tests to verify environmental stability. |

### **When is One High-Value Test Not Enough?**

While the One-Test Rule is the default optimization, specific architectural boundaries carry catastrophic failure risks that necessitate exhaustive permutation testing. A single "happy path" test is fundamentally insufficient in the following domains:

1. **Authentication and Authorization Boundaries:** A single test proving a user can log in does not prove that a malicious actor is prevented from accessing administrative resources. Role-Based Access Control (RBAC) middleware requires exhaustive negative testing to ensure 401 Unauthorized and 403 Forbidden responses are correctly issued.
2. **Financial Transactions and Payment Gateways:** Any logic handling stripe webhooks, calculating prorated subscriptions, or managing ledger balances must be subjected to rigorous unit and integration testing across multiple edge cases, including race conditions and idempotent retry scenarios.
3. **Data Deletion and Cascades:** Soft-delete and hard-delete logic must be explicitly tested to ensure that cascading deletions do not unintentionally wipe out orphaned records or violate foreign key constraints in the PostgreSQL database.

### **Smoke, Unit, Integration, and End-to-End Definitions**

To prevent AI hallucinations regarding testing terminology, the Fabrik rule file must strictly define these terms within the context of the established technology stack.

* **Smoke Tests:** Ultra-fast, non-destructive network requests designed to verify that the environments (VPS, Database, API) are successfully booted and communicating. Typically executed as a curl request to a /health endpoint during the Coolify deployment pipeline.
* **Unit Tests:** Execution of isolated functions in memory. In the Fabrik stack, unit tests are exclusively reserved for complex Python data transformations or specialized TypeScript utility functions. They must never involve DOM rendering or mock database sessions.
* **Integration Tests (The Core):** The vast majority of the test suite. In Python, this involves utilizing FastAPI's TestClient to send requests through the router, triggering SQLAlchemy to execute real queries against a transient PostgreSQL container, and validating the Pydantic response.27
* **End-to-End (E2E) Tests:** Simulated user interactions executed within a real browser engine (Chromium/WebKit) via Playwright, or on a mobile accessibility tree via Maestro.29 These tests treat the entire application as a black box.

## **Infrastructure, Fast Local Feedback Loops, and WSL2**

The physical and virtual environment in which code is written directly dictates the feasibility of the testing strategy. For a solo developer, the local feedback loop—the time elapsed between saving a file and seeing the test result—must be measured in milliseconds, not minutes.7 The Fabrik environment relies on Windows Subsystem for Linux (WSL2), which introduces severe I/O boundary constraints.

### **The WSL2 Filesystem Boundary**

WSL2 utilizes a lightweight utility virtual machine running a true Linux kernel. While internal Linux file system (ext4) performance is exceptional, accessing files across the operating system boundary incurs catastrophic I/O penalties.9 Storing the Next.js or FastAPI project in the Windows filesystem (e.g., /mnt/c/Users/Name/Project) and executing npm or pytest from within the WSL2 terminal forces the system to translate thousands of file read requests through the 9P network protocol.8

This cross-OS translation degrades Next.js Turbopack compilation speeds exponentially and severely limits the efficacy of inotify filesystem watchers.7 Consequently, hot-module replacement (HMR) fails, and test runners cannot detect file changes promptly.33 To maintain the fast local feedback loop necessary for rapid AI iteration, the strict rule is that all source code, testing artifacts, and database volumes must exclusively reside within the native WSL2 /home/user/ directory structure.8

### **Base Images: The slim-bookworm Mandate**

The Fabrik deployment and testing architecture mandates the use of Debian-based slim-bookworm container images, explicitly banning the use of Alpine Linux. While Alpine Linux is popular for its minimal footprint, it relies on the musl C standard library instead of the GNU C Library (glibc) used by mainstream Linux distributions.

This seemingly minor architectural difference creates massive friction in Python and Node.js environments. Many critical Python packages utilized by FastAPI, such as psycopg2 (for PostgreSQL) or asyncpg, as well as machine learning or cryptographic libraries, are distributed as pre-compiled binary wheels built against glibc. When these packages are installed on Alpine Linux, the pre-compiled wheels are incompatible, forcing the package manager to download the source code and compile the C extensions from scratch during the docker build process. This adds minutes to the CI/CD pipeline and the local testing feedback loop, drastically increasing maintenance burden. Furthermore, inconsistencies between local glibc testing and musl production environments lead to obscure segmentation faults. Relying strictly on slim-bookworm ensures parity with the ARM64 Ubuntu VPS deployed via Coolify, guaranteeing that code behaving correctly in local testing will execute identically in production.

## **Architectural Testing Strategy by Domain**

A unified testing philosophy must be translated into specific tactical implementations for each layer of the Fabrik technology stack.

### **FastAPI, PostgreSQL, and the Zero-Mock Policy**

In the Python backend ecosystem, a pervasive and highly destructive anti-pattern is the heavy utilization of mocking libraries (such as unittest.mock.patch) to simulate database interactions during API testing.28 While mocking artificially isolates the API layer and executes quickly, it fundamentally fails to verify the application's most critical failure boundary: the interaction between the Object-Relational Mapper (SQLAlchemy/SQLModel) and the PostgreSQL database engine.13

Database constraints, cascading deletions, JSONB indexing logic, default value generation, and asynchronous transaction deadlocks cannot be accurately simulated by a mock.13 When AI agents generate complex relational queries, verifying them against a mock is economically worthless; the bugs will only manifest in production.

For Fabrik, all backend integration tests must execute against a real PostgreSQL 16 database.14 Leveraging pytest, developers and AI agents must override the FastAPI database dependency (typically get\_db or get\_session) to yield a connection to a temporary, isolated test database.13 This database is provisioned locally via Docker Compose alongside the development environment.

To ensure tests remain performant and state isolation is maintained, the testing framework must utilize transactional rollbacks. Rather than truncating tables between every test, the pytest fixture opens a database transaction, yields the session to the application, and issues a strict .rollback() operation during the fixture teardown.34 This completely negates disk write overhead and guarantees a pristine database state for every test, enabling the suite to run in seconds.34

### **Next.js 14 App Router and Playwright**

The Next.js 14 App Router fundamentally restructures the React ecosystem by introducing asynchronous React Server Components (RSC). This paradigm shifts rendering to the server, meaning components frequently await database queries or external API calls before they are ever serialized and sent to the client browser.10

Traditional synchronous unit testing frameworks, such as Jest and Vitest, struggle profoundly with this architecture.10 These tools operate in simulated DOM environments (like JSDOM) that lack native support for Node.js server runtimes, data streaming, and asynchronous component resolution.10 Attempting to unit test a Next.js 14 Server Component requires elaborate mocking of the fetch API, the Next.js router, and the server context, resulting in highly fragile tests that verify the mock rather than the component logic.12

The official recommendation from Vercel, and the most durable path forward for a solo developer, is to abandon component-level unit testing for Server Components entirely and rely exclusively on End-to-End (E2E) testing with Playwright.10 Playwright boots the actual Next.js server, allowing server-side rendering, client-side hydration, and API route execution to occur exactly as they will in the production ARM64 Docker container.10 By interacting with the application precisely as a human user would, Playwright ensures behavioral verification that survives major code refactoring.5

### **Contract Testing via OpenAPI Schema Validation**

To minimize the reliance on slower, full-stack E2E tests, Fabrik must leverage Contract Testing.35 In a decoupled architecture, the most frequent point of failure is "integration drift"—where the backend alters a data structure, but the frontend continues to expect the legacy format.35 Traditional E2E tests catch this, but they are expensive to run and maintain.

Contract testing verifies that the frontend consumer and the backend provider agree on the exact shape of the data being transmitted.35 Because FastAPI automatically generates a highly accurate, standards-compliant OpenAPI (Swagger) schema based directly on its internal Pydantic models 21, this schema serves as the absolute, cryptographic source of truth for the application contract.20

Instead of writing manual tests that verify if the Next.js application correctly parses a specific user object, the Next.js build process must enforce strict TypeScript type generation derived directly from the FastAPI openapi.json file.21 If an AI agent modifies the backend to change a user's id field from a string to a number, the frontend TypeScript compiler will immediately fail during static analysis. This methodology effectively provides 100% API integration coverage with zero additional test code written, maximizing the ROI of the static analysis layer of the Testing Trophy.20

### **Mobile Testing: Maestro Over Detox**

React Native applications present distinct testing challenges due to the asynchronous architectural bridge communicating between the JavaScript execution thread and the native iOS/Android operating system threads.40

Historically, the industry standard for React Native testing was Detox, a gray-box testing framework.15 Detox integrates deeply into the application binary to monitor internal states, such as the JavaScript event loop and native animation queues, to ensure tests only execute when the application is completely idle.15 While Detox is highly performant and eliminates flakiness by synchronizing with the app's lifecycle, it carries a massive maintenance burden.41 It requires extensive native iOS and Android build configuration, breaks frequently upon minor React Native version upgrades, and demands significant technical expertise to orchestrate within CI pipelines.41

For a solo developer prioritizing low-maintenance durability, Maestro is the definitive framework.15 Maestro is a modern, black-box testing framework that interacts with the device purely through the operating system's native accessibility layer.15 Tests are written in simple, declarative YAML syntax.30 Maestro automatically handles asynchronous waiting and UI element polling, drastically reducing test flakiness without requiring any native build hooks or codebase integration.15 While execution speed is marginally slower than Detox (e.g., a login flow taking 12 seconds instead of 8 seconds), the near-zero maintenance overhead and extreme readability make it the optimal choice for AI-generated testing.15

| Evaluation Metric | Detox (Gray-Box) | Maestro (Black-Box) |
| :---- | :---- | :---- |
| **Testing Approach** | Internal thread and event loop monitoring | External interaction via accessibility layer |
| **Scripting Language** | JavaScript / TypeScript | Declarative YAML |
| **Maintenance Burden** | High (Requires native build hooks and SDK updates) | Minimal (Runs externally via independent CLI binary) |
| **Setup Complexity** | Complex (Requires deep Xcode/Android Studio alignment) | Trivial (Single binary installation, cross-platform) |
| **Flakiness Management** | Relies on internal thread synchronization mechanisms | Built-in smart wait times and automatic visual retries |
| **Execution Speed** | Fastest (In-process execution minimizes overhead) | Fast (Lightweight runner, but slower than native sync) |
| **Fabrik Suitability** | **Banned** (Too fragile and costly for solo developer) | **Mandated** (Highly durable, easily generated by LLMs) |

### **Chrome Extension Manifest V3 Service Worker Testing**

Testing Manifest V3 Chrome Extensions requires navigating exceptionally strict browser security and lifecycle policies. Manifest V3 replaces persistent, hidden background pages with ephemeral Service Workers that sleep when inactive and wake only in response to specific events.43 Consequently, standard browser automation frameworks, including older versions of Puppeteer, fail to load extensions properly in default headless modes because the Chromium engine actively disables extension loading in standard headless contexts for security reasons.43

Playwright provides the necessary API to test Manifest V3 extensions, but it requires highly specific configuration. The browser must be launched utilizing the chromium.launchPersistentContext method, providing a path to an empty, isolated user data directory, and passing the \--disable-extensions-except and \--load-extension flags pointing directly to the compiled extension build directory.43

Furthermore, because the extension runs in a separate execution context from standard web pages, testing the background service worker logic requires the test framework to extract the dynamic chrome-extension://\<id\> URL at runtime from the browser context's active service workers array.43 This ID is then used to manually route Playwright to the extension's popup HTML file to verify the user interface.43 Standard unit testing of Chrome APIs (e.g., chrome.storage.local) via mocks is heavily discouraged; Playwright must execute the actual extension in a real Chromium context to guarantee functional accuracy.

## **Canonical Rules for the Rule File**

Based on the preceding architectural and economic analysis, the following canonical rules must be encoded directly into the permanent 45-testing-strategy.md file. These represent the immutable laws of the Fabrik testing philosophy and must be followed by all AI agents.

1. **Testing Trophy Supremacy:** Integration and end-to-end tests constitute the primary source of truth. Unit tests are strictly reserved for complex, pure mathematical or isolated algorithmic functions. Generating unit tests for UI components or database CRUD operations is forbidden.
2. **Zero-Mock Database Policy:** Backend tests must never mock PostgreSQL, SQLAlchemy, or SQLModel sessions. All data-layer tests must execute against a real, local PostgreSQL 16 container instance. State must be managed strictly via transactional rollbacks after each test fixture yields.
3. **Playwright Mandate for Next.js:** Because Next.js 14 relies heavily on asynchronous React Server Components, DOM-simulation tools (Vitest, Jest, React Testing Library) are structurally ineffective. All frontend behavioral verification must be conducted via Playwright targeting a running local build.
4. **Maestro Over Detox for Mobile:** React Native UI testing must exclusively utilize Maestro. Tests will be authored in declarative YAML. Integrating Detox is strictly forbidden due to unacceptable native maintenance overhead.
5. **Manifest V3 Extension Contexts:** Chrome extension tests must utilize Playwright's launchPersistentContext targeting the bundled Chromium binary. Headless execution is permitted only if invoking the specific headless channel that supports extension side-loading.
6. **OpenAPI Contract Enforcement:** The primary integration boundary between the Next.js frontend and the FastAPI backend must be verified via strict TypeScript generation derived from the FastAPI openapi.json schema. Compiler failures serve as the first line of integration testing.
7. **The One-Test Minimum:** Every new feature ticket requires, at minimum, one high-value "happy path" integration or E2E test. Agents must not aim for 100% line coverage; they must aim for 100% critical-path behavioral coverage.
8. **Strict File System Isolation:** All tests must be executed from within the native WSL2 Linux filesystem (\~/ or /home/user/). Executing tests against files mounted from the Windows host (/mnt/c/) is explicitly prohibited due to critical I/O performance degradation and file-watcher failure.
9. **No Cosmetic Testing:** Tests must verify user behavior and application state changes. Assertions against CSS classes, Tailwind utility strings, or exact pixel layouts are banned. Playwright locators must utilize semantic DOM accessibility roles (e.g., getByRole).
10. **Test Data Factories Over Fixtures:** Use programmatic factories to generate dynamic database records for pytest. Do not rely on static JSON fixture files, which become brittle and require manual updates as database schemas evolve over time.
11. **slim-bookworm Exclusivity:** All testing and deployment Docker environments must utilize Debian slim-bookworm base images. Alpine Linux is banned to prevent musl libc compilation overhead and inconsistencies with Python and Node.js native binary wheels.

## **Anti-Patterns and Banned Patterns**

To prevent AI agents from hallucinating outdated, trendy, or high-maintenance architectural testing patterns, the rule file must explicitly define what is not allowed.

| Banned Pattern or Framework | Reason for Prohibition | Mandated Alternative for Fabrik |
| :---- | :---- | :---- |
| **Jest / React Testing Library** | Inherently incapable of natively handling React 18 asynchronous Server Components without elaborate mocking. Creates highly coupled tests that break on internal refactors. | **Playwright E2E** for complete behavioral verification in a real browser engine. |
| **Mocking SQLAlchemy / DBs** | Artificially hides genuine integration bugs, including foreign key constraints, unique violations, and asynchronous deadlocks. | **Real PostgreSQL 16 container** utilized via pytest dependency overrides and fast transactional rollbacks. |
| **Detox (React Native)** | Gray-box architecture requires deep native Xcode/Android integration, causing frequent CI breaks and demanding heavy ongoing maintenance. | **Maestro** (Black-box, YAML-driven, interacts exclusively with the native accessibility layer). |
| **Puppeteer (Extensions)** | Playwright offers superior, native support for Manifest V3 service worker extraction and persistent context management. | **Playwright** executing chromium.launchPersistentContext. |
| **Testing Implementation Details** | Writing assertions to check if a specific internal class method was called creates brittle tests that halt development velocity when refactoring code. | **Testing User Outcomes** (e.g., verifying the DOM displays the success message after a button click). |
| **Executing from /mnt/c/** | WSL2 cross-OS file system operations destroy test execution speed and completely disable inotify file watchers, breaking test runners and hot-reloading. | **Working strictly in native WSL2 (\~/\*)**, leveraging the Linux ext4 filesystem. |
| **Alpine Linux Docker Images** | Forces from-scratch compilation of C-extensions for Python (psycopg2) and Node.js due to musl libc incompatibility, adding massive latency. | **Debian slim-bookworm** to natively support pre-compiled glibc binary wheels. |

## **Enforcement in Execute Handoffs**

When an AI agent is instructed to execute a development task (the "execute handoff"), the system prompt must contain specific, actionable directives to ensure the testing strategy is upheld dynamically during the code generation phase. These instructions must be heavily contextualized.

* **Determine Ticket Type Requirements:** Before generating test code, the agent must categorize the ticket. If executing a backend API feature, the agent must author a pytest file utilizing TestClient and the real database override pattern. If executing a frontend UI feature, the agent must author a Playwright .spec.ts file.
* **Locate Existing Test Infrastructure:** The agent must search the workspace for existing test setup configuration files (e.g., conftest.py for Python, playwright.config.ts for Next.js) and strictly adhere to the established dependency injection patterns rather than inventing new setup and teardown logic.
* **Execute the One-Test Minimum:** The agent must generate exactly one comprehensive test file that covers the newly implemented "happy path" user flow. It must explicitly refrain from generating exhaustive edge-case permutation tests unless specifically commanded by the user to do so for high-risk domains (e.g., payments, auth).
* **Target Accessibility Roles:** For any Playwright test generated, the agent is required to use semantic locators (e.g., page.getByRole('button', { name: 'Submit' })). It must never use brittle XPath selectors or generic CSS class selectors that are prone to breaking upon minor visual styling updates.

## **Verification in final\_gate.py**

The final\_gate.py script serves as the absolute, automated gatekeeper before any code is committed to the repository. It is a Python script that analyzes the Git working tree and enforces repository rules statically and dynamically. To uphold the testing strategy, final\_gate.py must execute the following verifications:

1. **Change Detection and Correlation:** The script must utilize gitpython or the standard library subprocess.run(\['git', 'status', '--porcelain'\]) to detect all modified, added, or deleted files.45 If a core source file is modified (e.g., app/api/routes/users.py), the script must check if a corresponding test file was either modified or exists and passes (e.g., tests/api/test\_users.py). If a new feature file is added without a corresponding test file, the gate must reject the commit and demand fulfillment of the "One-Test Minimum."
2. **Static Anti-Pattern Scanning via AST:** The script must read the contents of modified test files and scan for banned imports and patterns using regular expressions or Abstract Syntax Tree (AST) parsing.
   * *Python:* Reject the commit if from unittest.mock import patch is found within the database-layer integration tests.
   * *TypeScript:* Reject the commit if import { render } from '@testing-library/react' or import jest is detected anywhere within the Next.js application directory.
   * *Mobile:* Reject the commit if detox is found as a dependency in package.json or within test files.
3. **Schema Drift Validation:** If Pydantic models in the FastAPI backend were modified, final\_gate.py must automatically trigger the OpenAPI JSON export command and run the TypeScript frontend schema generator. If the frontend compiler (tsc \--noEmit) fails due to contract mismatches, the gate must fail, preventing broken API contracts from entering the main branch.21
4. **Targeted Test Execution:** Based on the modified files, final\_gate.py should execute only the relevant subset of tests. Running the entire exhaustive Playwright suite on every minor backend documentation change is a severe violation of the requirement for fast local feedback loops.7 The script should leverage tools like pytest \--lf (last failed) or specific path filtering.

## **Content for AGENTS.md / AGENTS-compact.md**

The AGENTS.md and AGENTS-compact.md files define the persistent system prompts and contextual guardrails for the AI coding agents. The testing instructions within these files must be highly condensed to preserve token context windows while remaining completely unambiguous.

**Recommended Addition to AGENTS-compact.md:**

# **TESTING STRATEGY ENFORCEMENT**

* **Philosophy:** "Testing Trophy" model. 1 high-value Integration/E2E test is infinitely superior to 10 highly coupled unit tests.
* **Backend (FastAPI):** Use pytest \+ httpx (TestClient). ZERO MOCKING for databases. Override the get\_db dependency to inject a real, local PostgreSQL 16 container session. Ensure the fixture rolls back the transaction after each test.
* **Frontend (Next.js 14):** Playwright E2E only. Do NOT use Jest, Vitest, or React Testing Library for UI components; they are structurally incompatible with React Server Components. Test user behavior strictly via semantic locators (getByRole).
* **Mobile (React Native):** Maestro YAML scripts exclusively. Detox is strictly banned due to heavy maintenance.
* **Chrome Extensions:** Use Playwright with chromium.launchPersistentContext targeting the Manifest V3 service worker dynamically.
* **Contract Enforcement:** OpenAPI schema validation acts as the ultimate frontend-to-backend integration test. Changes to Pydantic models must reflect in compiled Next.js TypeScript types.
* **Environment:** Execute all code within native WSL2 (\~/). Never use /mnt/c/. Use slim-bookworm Docker images; Alpine Linux is banned.

## **Minimal Practical Examples for Fabrik Stack**

To anchor the theoretical rules in practical application, the rule file must contain minimal, copy-pasteable examples of the accepted testing patterns. AI agents learn exceptionally well via few-shot prompting equipped with exact syntax examples.

### **1\. FastAPI \+ Real PostgreSQL Transactional Rollback (pytest)**

This configuration demonstrates the correct methodology to override the FastAPI database dependency, providing a real PostgreSQL session to the application while rolling back the transaction to maintain execution speed and test isolation.34

Python

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create\_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import get\_db, Base

\# Must connect to a real PostgreSQL 16 instance running in a slim-bookworm Docker container
SQLALCHEMY\_DATABASE\_URL \= "postgresql://user:pass@localhost:5433/fabrik\_test"
engine \= create\_engine(SQLALCHEMY\_DATABASE\_URL)
TestingSessionLocal \= sessionmaker(autocommit=False, autoflush=False, bind=engine)

\# Ensure schema is created before tests run
Base.metadata.create\_all(bind=engine)

@pytest.fixture(scope="function")
def db\_session():
    """Yields a database session and rolls back the transaction after the test completes."""
    connection \= engine.connect()
    transaction \= connection.begin()
    session \= TestingSessionLocal(bind=connection)

    yield session

    \# Teardown: close session and rollback to ensure a pristine database state for the next test
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db\_session):
    """Overrides the FastAPI get\_db dependency to use the transactional test session."""
    def override\_get\_db():
        yield db\_session

    app.dependency\_overrides\[get\_db\] \= override\_get\_db
    with TestClient(app) as test\_client:
        yield test\_client
    app.dependency\_overrides.clear()

def test\_create\_user\_happy\_path(client):
    """The 'One-Test Minimum' covering the entire user creation boundary."""
    response \= client.post("/users/", json={"email": "test@fabrik.com", "password": "secure"})
    assert response.status\_code \== 200
    assert response.json()\["email"\] \== "test@fabrik.com"

### **2\. Next.js 14 App Router Behavioral Testing (Playwright)**

This example demonstrates the mandatory behavioral approach for Next.js frontend testing. It interacts with the application utilizing semantic HTML roles rather than attempting to test internal React state or mocking async data fetches.10

TypeScript

import { test, expect } from '@playwright/test';

test('User can navigate to the dashboard and view server-rendered metrics', async ({ page }) \=\> {
  // Playwright boots the Next.js server, executing Server Components naturally
  await page.goto('http://localhost:3000/login');

  // Rule: Use semantic accessibility roles, never brittle CSS classes or XPaths
  await page.getByRole('textbox', { name: /email/i }).fill('test@fabrik.com');
  await page.getByRole('textbox', { name: /password/i }).fill('secure');
  await page.getByRole('button', { name: /sign in/i }).click();

  // Verify successful network navigation
  await expect(page).toHaveURL(/.\*dashboard/);

  // Verify asynchronous server-rendered data successfully reached the client
  await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
});

### **3\. React Native Mobile UI Testing (Maestro)**

This example highlights the extreme simplicity and durability of Maestro for mobile UI testing. No JavaScript bridge interaction or native compilation hooks are required, virtually eliminating test maintenance.15

YAML

appId: com.fabrik.mobile
\---
\# The 'One-Test Minimum' covering mobile authentication flow
\- launchApp
\- assertVisible: "Login"
\- tapOn: "Email Input"
\- inputText: "test@fabrik.com"
\- tapOn: "Password Input"
\- inputText: "secure"
\- tapOn: "Sign In"
\# Built-in smart waits handle the asynchronous network request automatically
\- assertVisible: "Dashboard Overview"
\- assertNotVisible: "Login"

### **4\. Chrome Extension Manifest V3 Testing (Playwright)**

This configuration demonstrates how to properly bootstrap the Chromium engine with a persistent context to bypass headless extension security restrictions and access Manifest V3 service workers.43

TypeScript

import { test as base, chromium, expect, BrowserContext } from '@playwright/test';
import path from 'path';

// Define a custom fixture to load the extension into Chromium
export const test \= base.extend\<{
  context: BrowserContext;
  extensionId: string;
}\>({
  context: async ({}, use) \=\> {
    const pathToExtension \= path.join(\_\_dirname, '../dist');
    const context \= await chromium.launchPersistentContext('', {
      channel: 'chromium', // Required to bypass headless extension restrictions
      args:,
    });
    await use(context);
    await context.close();
  },
  extensionId: async ({ context }, use) \=\> {
    // Extract Manifest V3 Service Worker dynamically from the browser context
    let \= context.serviceWorkers();
    if (\!serviceWorker) {
      serviceWorker \= await context.waitForEvent('serviceworker');
    }
    // The extension ID is required to route to internal extension pages
    const extensionId \= serviceWorker.url().split('/');
    await use(extensionId);
  },
});

test('Popup interface renders and displays extension state', async ({ page, extensionId }) \=\> {
  // Navigate directly to the popup HTML using the extracted ID
  await page.goto(\`chrome-extension://${extensionId}/popup.html\`);
  await expect(page.getByRole('heading', { name: /fabrik tools/i })).toBeVisible();
});

## **Recommended Final Content for 45-testing-strategy.md**

The following section contains the literal markdown output that should be written to the 45-testing-strategy.md file within the Fabrik repository. It incorporates all established constraints, tactical instructions, and verified examples into a concise, easily parsed format designed permanently guide AI agents.

# ---

**45-testing-strategy.md**

## **1\. Core Testing Philosophy**

Fabrik operates on a low-maintenance, high-ROI engineering model optimized for a solo developer heavily augmented by AI coding agents. To maintain velocity, we exclusively utilize the **Testing Trophy** methodology.

* **Integration over Isolation:** We prioritize testing actual user flows and database interactions across network boundaries. Highly coupled unit tests that verify implementation details are permanently banned.
* **The One-Test Rule:** For every feature ticket, author exactly *one* high-value "happy path" end-to-end or integration test. Do not chase 100% line coverage; ensure 100% critical-path behavioral coverage.
* **No Cosmetic Assertions:** Assertions must target application state and functionality. Never assert against CSS classes, tailwind strings, or pixel measurements.

## **2\. Technology Specific Rules & Anti-Patterns**

### **Backend: FastAPI & PostgreSQL**

* **Mandatory Framework:** pytest and httpx (TestClient).
* **Banned:** Mocking the database, SQLAlchemy, or SQLModel (unittest.mock.patch).
* **Rule:** All backend API tests must execute against a real PostgreSQL 16 test container. Use dependency overrides (app.dependency\_overrides\[get\_db\]) to inject a database session. To keep tests fast, yield the session within a transaction block and issue a .rollback() during teardown.

### **Frontend: Next.js 14 App Router**

* **Mandatory Framework:** Playwright.
* **Banned:** Jest, Vitest, React Testing Library, Enzyme.
* **Rule:** Because Next.js 14 relies heavily on async React Server Components, DOM-simulation tools (JSDOM) are inherently broken. All frontend verification must be done via Playwright hitting a local development server. Use semantic locators (page.getByRole).

### **Mobile: React Native**

* **Mandatory Framework:** Maestro.
* **Banned:** Detox, Appium.
* **Rule:** Detox is too fragile and requires extensive native hooks. Use Maestro to write declarative, black-box YAML tests that interact with the native accessibility layer.

### **Chrome Extensions: Manifest V3**

* **Mandatory Framework:** Playwright.
* **Banned:** Puppeteer standard headless mode.
* **Rule:** You must use chromium.launchPersistentContext with the \--load-extension flag. Extract the Manifest V3 background service worker dynamically to test background scripts, and route to chrome-extension://\<id\>/popup.html to test the UI.

### **API Contract Enforcement**

* **Rule:** The most robust integration test is the TypeScript compiler. Rely on Pydantic to generate openapi.json, and generate TypeScript types for the frontend from this schema. If the backend schema changes, the Next.js TypeScript compiler must fail.

## **3\. Environmental Constraints (WSL2 & Docker)**

* **Rule:** All code, databases, and test execution must occur natively within the WSL2 Linux filesystem (e.g., /home/ubuntu/fabrik).
* **Banned:** Never execute tests or store the repository in the mounted Windows file system (/mnt/c/). This severely degrades cross-OS I/O performance and breaks inotify file watchers, breaking test runners.
* **Rule:** Docker environments must strictly use slim-bookworm Debian base images. Alpine Linux is banned to prevent musl compilation overhead with Python binary wheels.

## **4\. final\_gate.py Verifications**

When executing final\_gate.py before a commit, the system will execute the following automated gatekeeping:

1. **Check Test Existence:** Identify modified source files via gitpython and assert that a relevant test file was created or modified to fulfill the "One-Test Minimum."
2. **Scan for Banned Imports:** Reject commits containing unittest.mock for database operations, or jest/@testing-library anywhere within the Next.js application structure.
3. **Validate Schema Contract:** Regenerate the OpenAPI schema from FastAPI and run tsc \--noEmit on the frontend. Reject the commit if API drift causes a TypeScript type error.

## **5\. Reference Implementations**

### **FastAPI Pytest DB Override**

Python

@pytest.fixture(scope="function")
def db\_session():
    connection \= engine.connect()
    transaction \= connection.begin()
    session \= TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback() \# Crucial for speed and state isolation
    connection.close()

@pytest.fixture(scope="function")
def client(db\_session):
    app.dependency\_overrides\[get\_db\] \= lambda: db\_session
    with TestClient(app) as test\_client:
        yield test\_client
    app.dependency\_overrides.clear()

### **Next.js Playwright E2E**

TypeScript

test('Dashboard workflow', async ({ page }) \=\> {
  await page.goto('http://localhost:3000');
  await page.getByRole('button', { name: /login/i }).click();
  await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
});

### **Maestro React Native**

YAML

appId: com.fabrik.app
\---
\- launchApp
\- tapOn: "Login"
\- assertVisible: "Dashboard"

#### **Works cited**

1. Demystifying evals for AI agents \- Anthropic, accessed March 31, 2026, [https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
2. Six New Tips for Better Coding With Agents | by Steve Yegge | Medium, accessed March 31, 2026, [https://steve-yegge.medium.com/six-new-tips-for-better-coding-with-agents-d4e9c86e42a9](https://steve-yegge.medium.com/six-new-tips-for-better-coding-with-agents-d4e9c86e42a9)
3. Unit vs Integration Testing: Guide for Legacy Codebases \- Augment Code, accessed March 31, 2026, [https://www.augmentcode.com/learn/unit-vs-integration-testing-guide-for-legacy-codebases](https://www.augmentcode.com/learn/unit-vs-integration-testing-guide-for-legacy-codebases)
4. Test Automation 2030: Rethinking Test-Pyramid Strategies for the AI-Era | Keploy Blog, accessed March 31, 2026, [https://keploy.io/blog/technology/future-of-test-automation-in-ai-era](https://keploy.io/blog/technology/future-of-test-automation-in-ai-era)
5. Stop Writing Unit Tests for React Components: The Paradigm Shift in Frontend QA, accessed March 31, 2026, [https://www.compiler.today/frontend-engineering/stop-unit-tests-react-behavioral-verification](https://www.compiler.today/frontend-engineering/stop-unit-tests-react-behavioral-verification)
6. Software testing \- Wikipedia, accessed March 31, 2026, [https://en.wikipedia.org/wiki/Software\_testing](https://en.wikipedia.org/wiki/Software_testing)
7. How to optimize your local development environment \- Next.js, accessed March 31, 2026, [https://nextjs.org/docs/app/guides/local-development](https://nextjs.org/docs/app/guides/local-development)
8. How to solve the problems caused by WSL 2's filesystem changes? \- Super User, accessed March 31, 2026, [https://superuser.com/questions/1594279/how-to-solve-the-problems-caused-by-wsl-2s-filesystem-changes](https://superuser.com/questions/1594279/how-to-solve-the-problems-caused-by-wsl-2s-filesystem-changes)
9. Large file read/write is much, much slower on WSL2 than native windows. Is this normal?, accessed March 31, 2026, [https://www.reddit.com/r/bashonubuntuonwindows/comments/otij5d/large\_file\_readwrite\_is\_much\_much\_slower\_on\_wsl2/](https://www.reddit.com/r/bashonubuntuonwindows/comments/otij5d/large_file_readwrite_is_much_much_slower_on_wsl2/)
10. Guides: Testing | Next.js, accessed March 31, 2026, [https://nextjs.org/docs/app/guides/testing](https://nextjs.org/docs/app/guides/testing)
11. Testing: Vitest \- Next.js, accessed March 31, 2026, [https://nextjs.org/docs/app/guides/testing/vitest](https://nextjs.org/docs/app/guides/testing/vitest)
12. Next.js Playwright Testing: Full Guide \- Autonoma AI, accessed March 31, 2026, [https://www.getautonoma.com/blog/nextjs-playwright-testing-guide](https://www.getautonoma.com/blog/nextjs-playwright-testing-guide)
13. Beyond Speed: The Underrated Advantages of Pairing FastAPI with PostgreSQL \- Medium, accessed March 31, 2026, [https://medium.com/@shreyj75/beyond-speed-the-underrated-advantages-of-pairing-fastapi-with-postgresql-dea8aea31f83](https://medium.com/@shreyj75/beyond-speed-the-underrated-advantages-of-pairing-fastapi-with-postgresql-dea8aea31f83)
14. FastAPI \- Unit Testing with Database \- Whats the correct approach? Mock vs. Local ... \- YouTube, accessed March 31, 2026, [https://www.youtube.com/watch?v=ToqyR-MmpkM](https://www.youtube.com/watch?v=ToqyR-MmpkM)
15. Detox vs. Maestro: Reducing Flakiness in React Native, accessed March 31, 2026, [https://maestro.dev/insights/detox-vs-maestro-reducing-flakiness-react-native](https://maestro.dev/insights/detox-vs-maestro-reducing-flakiness-react-native)
16. The 3 Best React Native Testing Frameworks \- Maestro, accessed March 31, 2026, [https://maestro.dev/insights/best-react-native-testing-frameworks](https://maestro.dev/insights/best-react-native-testing-frameworks)
17. The ROI of AI in Coding Development: What Teams Need to Know in 2025 \- Medium, accessed March 31, 2026, [https://medium.com/@riccardo.tartaglia/the-roi-of-ai-in-coding-development-what-teams-need-to-know-in-2025-4572f11c63c4](https://medium.com/@riccardo.tartaglia/the-roi-of-ai-in-coding-development-what-teams-need-to-know-in-2025-4572f11c63c4)
18. How to Measure the ROI of AI Coding Assistants \- The New Stack, accessed March 31, 2026, [https://thenewstack.io/how-to-measure-the-roi-of-ai-coding-assistants/](https://thenewstack.io/how-to-measure-the-roi-of-ai-coding-assistants/)
19. Test automation: How it affects developer productivity and code quality \- DX, accessed March 31, 2026, [https://getdx.com/blog/test-automation/](https://getdx.com/blog/test-automation/)
20. Contract Testing vs. Schema Testing \- Pactflow, accessed March 31, 2026, [https://pactflow.io/blog/contract-testing-using-json-schemas-and-open-api-part-1/](https://pactflow.io/blog/contract-testing-using-json-schemas-and-open-api-part-1/)
21. Enforcing API Correctness: Automated Contract Testing with OpenAPI and Dredd, accessed March 31, 2026, [https://dev.to/r3d\_cr0wn/enforcing-api-correctness-automated-contract-testing-with-openapi-and-dredd-2212](https://dev.to/r3d_cr0wn/enforcing-api-correctness-automated-contract-testing-with-openapi-and-dredd-2212)
22. Do You Actually Write Front End Tests? : r/ExperiencedDevs \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/ExperiencedDevs/comments/1oig8ax/do\_you\_actually\_write\_front\_end\_tests/](https://www.reddit.com/r/ExperiencedDevs/comments/1oig8ax/do_you_actually_write_front_end_tests/)
23. One Test to Rule Them All, accessed March 31, 2026, [https://www.cefns.nau.edu/\~adg326/issta17.pdf](https://www.cefns.nau.edu/~adg326/issta17.pdf)
24. Unit Testing with an Optimization Problem \- Software Engineering Stack Exchange, accessed March 31, 2026, [https://softwareengineering.stackexchange.com/questions/230355/unit-testing-with-an-optimization-problem](https://softwareengineering.stackexchange.com/questions/230355/unit-testing-with-an-optimization-problem)
25. Over-Engineering Tests: How to Recognize the Signs and Fix \- testRigor AI-Based Automated Testing Tool, accessed March 31, 2026, [https://testrigor.com/blog/over-engineering-tests/](https://testrigor.com/blog/over-engineering-tests/)
26. CTO's Guide to AI Development Tool ROI | Augment Code, accessed March 31, 2026, [https://www.augmentcode.com/tools/cto-s-guide-to-ai-development-tool-roi](https://www.augmentcode.com/tools/cto-s-guide-to-ai-development-tool-roi)
27. Testing FastAPI Applications: A Complete Guide with pytest and HTTPX | Kiran Kumar V, accessed March 31, 2026, [https://kirankumarvel.wordpress.com/2025/09/09/testing-fastapi-apps-pytest-guide/](https://kirankumarvel.wordpress.com/2025/09/09/testing-fastapi-apps-pytest-guide/)
28. Tests with FastAPI and PostgreSQL \[closed\] \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/76530308/tests-with-fastapi-and-postgresql](https://stackoverflow.com/questions/76530308/tests-with-fastapi-and-postgresql)
29. Testing: Playwright \- Next.js, accessed March 31, 2026, [https://nextjs.org/docs/pages/guides/testing/playwright](https://nextjs.org/docs/pages/guides/testing/playwright)
30. React Native Automation: Setup Guide \- Maestro, accessed March 31, 2026, [https://maestro.dev/insights/react-native-automation-setup-guide](https://maestro.dev/insights/react-native-automation-setup-guide)
31. Why is WSL extremely slow when compared with native Windows NPM/Yarn processing?, accessed March 31, 2026, [https://stackoverflow.com/questions/68972448/why-is-wsl-extremely-slow-when-compared-with-native-windows-npm-yarn-processing](https://stackoverflow.com/questions/68972448/why-is-wsl-extremely-slow-when-compared-with-native-windows-npm-yarn-processing)
32. How I fixed WSL 2 filesystem performance issues \- Rob Pomeroy, accessed March 31, 2026, [https://pomeroy.me/2023/12/how-i-fixed-wsl-2-filesystem-performance-issues/](https://pomeroy.me/2023/12/how-i-fixed-wsl-2-filesystem-performance-issues/)
33. Fast Refresh is not working in version 10.0.7 (Windows 10\) · vercel next.js · Discussion \#22214 \- GitHub, accessed March 31, 2026, [https://github.com/vercel/next.js/discussions/22214](https://github.com/vercel/next.js/discussions/22214)
34. Is this really what I have to do to test? : r/FastAPI \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1888a59/is\_this\_really\_what\_i\_have\_to\_do\_to\_test/](https://www.reddit.com/r/FastAPI/comments/1888a59/is_this_really_what_i_have_to_do_to_test/)
35. Contract Testing : What Is It, Benefits & Use Cases | PFLB, accessed March 31, 2026, [https://pflb.us/blog/contract-testing/](https://pflb.us/blog/contract-testing/)
36. Stop E2E Testing Your Next.js App\! Write Better Tests with Contract Tests \- Craft Conference, accessed March 31, 2026, [https://craft-conf.com/2025/talk/markus-oberlehner](https://craft-conf.com/2025/talk/markus-oberlehner)
37. FastAPI Best Practices \- Auth0, accessed March 31, 2026, [https://auth0.com/blog/fastapi-best-practices/](https://auth0.com/blog/fastapi-best-practices/)
38. What're contract test value in the light of generated HTTP clients? : r/ExperiencedDevs, accessed March 31, 2026, [https://www.reddit.com/r/ExperiencedDevs/comments/1j02u07/whatre\_contract\_test\_value\_in\_the\_light\_of/](https://www.reddit.com/r/ExperiencedDevs/comments/1j02u07/whatre_contract_test_value_in_the_light_of/)
39. How API Schema Validation Boosts Effective Contract Testing \- Zuplo, accessed March 31, 2026, [https://zuplo.com/learning-center/how-api-schema-validation-boosts-effective-contract-testing](https://zuplo.com/learning-center/how-api-schema-validation-boosts-effective-contract-testing)
40. React Native in 2025 \- Detox or Appium? \- DEV Community, accessed March 31, 2026, [https://dev.to/berthaw82414312/react-native-in-2025-detox-or-appium-2g3l](https://dev.to/berthaw82414312/react-native-in-2025-detox-or-appium-2g3l)
41. The Best Mobile E2E Testing Frameworks in 2026: Strengths, Tradeoffs, and Use Cases, accessed March 31, 2026, [https://www.qawolf.com/blog/best-mobile-app-testing-frameworks-2026](https://www.qawolf.com/blog/best-mobile-app-testing-frameworks-2026)
42. Detox vs Maestro: Comparing Modern Mobile Testing Frameworks \- Panto AI, accessed March 31, 2026, [https://www.getpanto.ai/blog/detox-vs-maestro](https://www.getpanto.ai/blog/detox-vs-maestro)
43. Chrome extensions | Playwright, accessed March 31, 2026, [https://playwright.dev/docs/chrome-extensions](https://playwright.dev/docs/chrome-extensions)
44. End-to-end testing for Chrome Extensions \- Chrome for Developers, accessed March 31, 2026, [https://developer.chrome.com/docs/extensions/how-to/test/end-to-end-testing](https://developer.chrome.com/docs/extensions/how-to/test/end-to-end-testing)
45. gitpython to check for if there are any changes in files using PYTHON \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/42382487/gitpython-to-check-for-if-there-are-any-changes-in-files-using-python](https://stackoverflow.com/questions/42382487/gitpython-to-check-for-if-there-are-any-changes-in-files-using-python)
46. python \- Get changed files using gitpython \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/33733453/get-changed-files-using-gitpython](https://stackoverflow.com/questions/33733453/get-changed-files-using-gitpython)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAfCAYAAACcai8CAAACzElEQVR4XtWXT6gPURTHzywU4WEhFha8UmJDIlmwkY2FlVJ69jZWFlja2NghCykpG0mKjZSslB1ZspKkHq8eKfV+9ZzvnDn33jnz597fb24/P586v9+ce87c+d65596ZIZoFisr+e1IGkZITI9ZHGY8l/StmVVcicfm+nOO5beCsB2yrYkX1TyO2XVXOZrY/1XGUyWQo/Wc/IS/utIltqtr3k+S8rIcHYDVZvwWk/CYRcsPEQraRu/N0ysSmRFGKHfEvRJy14RZ+kAhebwPT4huJgBc20MErktJoJWE2B3GJ/BQXiZeD4Hz1GyOQhEMVeztsbFBvfMN2stYyJS6SF4xtKjOtQxd6Qn18Jr+FDcMVU7eS7kg6enff2sAEbLcN7QyTrYKv20APu9nWBP4dthVKHvR4gn22HKngy67dx7r4xbZWDl0iHtEL6qRj5cRZJBF8zwZq+N4Osb3zgRKIRx9bTHsezEiukVwMD44YOBWLMywHwNtb+XIE8Ni2bMRP4w42GkqSBj0qRPRxGzD8ZDvsXXfF5yQDucW2gaQvDGonSX0/pGCPJ6n1m4GPrk6Q9I/zX7OtFM0XLwf2X63lKyYGjpDE9tpABWr6auB/Iikx/IOPbPddVPo6EPhYxGjTO7Cu8re6jOZ0FGj5QF54aHjd7AJ30nRergs8ujG9GtctD3mhOLBMkq8cI8nJgxlrW+fwddfBzhG+5F9gWwp8XbDhY/4x2/vAn5DGrJSgznTqmeIoiQBdmLhzqHEFQiAIC/Fc9Y/8uSAHJYaBxWhX1KCeNs/2NfAxvWcCH290EAi0PDAreIfRdxcs2B3VMdaCLbEeZRrpzmgDXyffSS68x7VKHxCJp+AXtkds50m+au66PFlk2FZhKI3VxvWtP4ysvWWq33FJHYN8kuHrXDwph4M+YfbAt+EzlvqUpKT2mfi4pN6qccnWb7aOsvMXji+QZHQEgfcAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEMAAAAfCAYAAAC8hnD/AAADb0lEQVR4Xt2YS6hOURTH10lCKHkUusrrlohEUgZ3SMhjIDEzMbilDJRrIAN1kwwMlJTSTaFkQMkAZWLAjAnJYyCv8iivUhTrf9Ze96yzv/P+zsn5vl+t+539Wmevtfdae59L1ARBynPP0hdG9Copzk+pLk7XCpqghknVoKK9lDeu/Ihu2cbyMkeus4xQ5dlVHFYDZd+8imU3yxWWv072uzoVOEPbxsJR/U1wlMTYd36LQR2yq6zHe43nJIae8RsML0j64Lev0VVf7jcY/lBhZ7Rv7xSd0VyKnJHGFIr6HPfaClFkMkX6NM0hys8XoyR9sDv6mmeUnS8GKdoV2CEto979pIYeofiReorlp2t7MN67ZyjjJOlr88V5T/ayLHW9K1FmOmV7M5OddEPspdgNcMR3W1mM0pOvi/ksN0jmnXX6lUbvF9f8hpazhLJPPzBA+X1iaIgM/bd1rsYJyj79QJE+IDR9gH/UGRMT2vOYQEkxK0OnerUKxkCKMsevcLym6PRD3kviFaWdkAnmwXNV8sUykvvGapYFLF9N22mSeJ7E8plE/3TXNsJz2Mi/X1hWujqQFPtjLPdI9GB+Vg9A+S7JR+UsV57h2k6yXHR1l0gOgwTzpRIJaD0/6rGJ6/VCSvewZS3FdxLuKHoRw2f+B/cMdlAUs3gvvowB6ta5Z6y89lFwwXtrypso3kfzxSJThzLep1brrs8goM0kAzslCFcyTqc/f1FklAXOgZ6dpg5J+bF7hib02UBxw4YD2UFKnh4o8nMBdGOMDSl8hSfki06DqqKrGN/Son+ra7M5BOEwbMrgIctNU4aR2MoKwsjXgzCxemy+ALzAgf+ZkJ4vagLh5U9UwWTtiusKw4HHTD3qYLAtD7FsYZlJLrTM+lk9ir8guB6MuTFnw78SItoHO6kR8JLZpjyN5Q3LYtem3DHlp6YeKwjjAeetsA8M1jBAErR6nnjlpLsDyqjfQ5L3kGi1D/Sdc8+GesJlHolB+N8oXrjPtB1m+cbyg+SDDknwI8lElTUk4z6xbGe5TRJOcIwQ0Ar++5vlPstlMvmCOUgSApZbLO9ZDpi6RyTvv2rq8unWR1XHFxzn54tyFHxJG5GPxmD82B0Myx0XQpBhZUZTDtVHNoDG+gWSbY7wacv/T5yjWuWvarTPhIZmVFXtPxYv0aFFf17DAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADgAAAAfCAYAAACyLw6QAAADD0lEQVR4Xu2YPYgVMRDHZxHBDzz8QDjEymtEsBRF8AQLWy3kCsHSQhFsRCysbGwFEYVrDkGwEEQULeREucpGEBsFP0DwA/QQtBEUnvN/mWzmTTZv39vNHifcD4bNzmSSmWySlzyiGgqraEy+lhrSNIAavxpzNVVOsS7W5ASt6x667S0vyyXWdnG084782za3FFxnmeVAZ/GskTMsMyI7+97LnB0sPZE/LO9E3iv9d6X/ovRXKTcdTIc7LF+tkpmikMhqY0MY0B82+jHoIJMECHSLVTKXydl+WYOwyLLVKsel6zQxPV9ZpfCRXIK3rMFRwFZP1xnUMMcybZVCj4NDEnutQfhtFf8TU0VYf919g+5ajjF9YXdEclhn+ahKaFQdiTphG5fP5BKcM/rm+MBaBtjKXTn76bknqKqBT7NOm3nlYBeFDWapozhHbvfulLD+MqVnm7HvihcsN4zuKGXesfOvv3Y8Z3lQvg0ZnT5pe2kZef0x661CsYoGu1ujysAe/zaYdw9iGXYknLSKYbj1V//7t5HlHstFlkdKv8hOJ6SMNt6iULgAD4juCrmbyHmWU1L3MYWz71rR4eZyX3T+JuNBHVwMTpIbSJyl7YCVbINwEIfI3RZ8gke8LVQtc16Q4hMRgA7g1z+fsvkgSYLMG3nCfprc10L5OLn6eCJobG79Lyk9HaN4/fl+9ikdjpMY9IjNFBIaJhb4Adh2SxlHOl0Xgfrr1CYR2O1I4x35XKL4VvOM9Ppz4B3tzMhs+cBydrBKI6IZu58GE8IovlTv04Wbdh4Ek7qZAHwpfEkN2rfrD6crTOkhRLEKKX01NylMPfCN5YJ6X1BlNI3dEHfPKvylGxHgmgYmCqfzm9NDeSJB3U9noBPc+j1/yW06AOsBa02DYFM3FwwWBgDMyxO7eE9GHdMfv4fgGstdKXvgW7kG2/Ka3N8ZP1gmyO1sOInc1pWYdRS+UBXb2QRftKP5yfKJ4jWG2YF+YX9apNtdYTxWxrEdqfFL6TPRpnnlm2ompS/RFVKVU3rLqPVakqubfw98o7qHIyUlAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHIAAAAfCAYAAAA7t5n5AAAExUlEQVR4Xu2aW8htUxSAx5/kfieSJ5dCPJBDEUqueeBBSHkW6bxQToen83JeTkkSkvqJlEshLy7pvLml6JTIrdxzK6QUxfj+MYc91thr7eta7b3/f301+vccc86xxpxj3przF1kp1rKi0KTf0nTfKd1/oUdGdXNzznIxk58zVVpyVqNNq+Fl97TYDy2aqqFb692wWJ8fVnlsQrlT5cYip1O5Zzk4WeXfIn+rfF7ki6D/Oei/D/oHZTOwqEkUvzuTD9VKz6v8UNEYp8ggYPunPCygvzLpxzCFt1MUnZgubM5Ne04RkGOyUtktlvdHziif/kXluErGZqa9/u4EltV9WVn4SiyQT+eMAnnLT2cB6MzwTKyrXJKVBV9WL8gZhb+yYrOyXCGbzp+4P05Tbyo6M9zzP5xGCSL7YM8K851YINeTfoswz1oxT9322VhW1aVtOWPT0FZ/D9kZUiyMM6WF/XHmigMeUXkvK40WrLdFq660amzc/tjux0bwtcrdWTkh+M+A3NIseH+ce6D4iTvQbLM5Z/XxZXXc/si1XeyHw1T2C2k4NqUzubxzVFYoB0r1e5Spi8N9YoOxiTo/8w3V8SmdOTgrCtPaqe8fa9W4uiOZdH88S+Vmseu7K1Q+EOvo98X2tndULlU5T4Zmx4Zdlu2rVc5V+bSkHW6aTpSqD9erXFx0F6m8oXKAyjcyWH6vFXud+Ufl3fL71JIHz6p8LBbI21R2FT03WFeJ+fCc2P3xaWLfynfML4i9FB0q9pAQ29ZsZ23Izksqb4v1GVvZLUW/pg3+UawPGWx7xW7fJoJOQy4Te93wQF4X8nJUPyx/ud15Peh3yHAHkN6wUeCCfntIf6bySvnNQLpQ5QSpBhK/AB0Bcp5U+SSkgTJ5f8THWO5wlWdUThIbJNxuUe/IUIYAnBPSfHdf6Afa6rdbo+1IxQ4D9dXy+xCxfGzBnyo7y2+4Qaw/xnK0DAI3SjLUI1jkxWWQmehBARoY6+MY6TguSPsrCiMU6OR4B4ye71A2DhJmQXxKy98Dljt094q9oXJ3zKjHB7fFCxC+O/4t94dZTDpuN7Gtk9o5u6RjoJ3bxfJuEvMTO6wineOjLxKDAg+JvWs6zIq4fzEzYkMddHkk3irVlxgCQTmC59Ttj6ws2c8MdrHvMEPicn+XRBs2DHNbYZwdAt90R/2myk9ZOQWjtsKRjBt9wH7FksMI5C+dHF9TaLQ37K3ylwB6pz1V/gLf4psO+4rXfa38ZdD4DGV5ZY8aF8i6leU3seWfttwhZvPXkB/b+kTRTWKHYPm2lCEP6ZLaYOfRF4MCvqRReV02GrrGkunBQE+gcZ5Auy3SlCH/8aIDbMWXGmY3HXyQygNFRxlf/lh2gXz3w+FFhwMF5JXF9y06H7vUZ3DF1eCjUgY4tMAkdq4RO6BF7hHbcury7lc5P+laBydxznlRbG+LfCt2uOF06nBypJP3igUQO+xZDmXZ9KnrcNzPwaCBlIt7KSfY32WwBzoEjvrMWOqcEfIeVXk5pIFTOMvc5UHHoOGkyszkRMl3+O373TR28IGgIUeEvD0lj3+n+VKq/ds+tfOzZ5XpQ7pE9MFYNE0RaNK3RMfm22ZGd+ur1Wt7egbMMUb+A/PjKYljzDcOAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,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>
