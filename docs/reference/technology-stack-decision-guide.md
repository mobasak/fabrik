# Technology Stack Decision Guide

> **Source of truth for Fabrik defaults:** `AGENTS.md` § Tech Stack Defaults.
> This guide is a **general-purpose reference** for choosing stacks across any product type.
> When building Fabrik projects, the overrides below take precedence over generic recommendations.

---

## Fabrik Stack Overrides

The generic flowchart below recommends industry-standard defaults. For all `/opt/*` Fabrik projects, these **Fabrik-specific choices** apply instead:

### Where Fabrik Differs from Generic Recommendations

| Category | Generic Guide Recommends | Fabrik Uses Instead | Why |
|----------|--------------------------|---------------------|-----|
| **Backend API** | TypeScript + Node.js | **Python + FastAPI + Uvicorn** | Best AI library access, owner's primary language, strong typing via Pydantic |
| **Frontend** | TypeScript + Next.js + Node.js monorepo | **Next.js 14 + TypeScript + Tailwind** (frontend only, backend is separate Python) | Frontend matches, but backend is Python — not a JS monorepo |
| **CLI tooling** | Go (single binary) | **Python** (`src/fabrik/cli.py`) | Shares codebase with backend, direct access to Fabrik's Python modules |
| **Background workers** | Node.js (web-adjacent) | **PostgreSQL jobs table + Python worker** | No Redis dependency by default; Redis only for high-throughput cases |
| **Database** | (not specified) | **PostgreSQL 16** (VPS, Coolify-managed) or Supabase (managed auth/realtime/pgvector) | Single shared PostgreSQL instance for all services |
| **AI/LLM** | Python + managed APIs | **Kilo CLI free tiers → OpenAI/Anthropic APIs → Local Ollama** | Budget-first: free before paid, local before cloud |

### Fabrik Deployment Constraints (Not in Generic Guide)

These constraints are **mandatory** for all Fabrik projects. The generic flowchart does not cover them.

| Constraint | Rule | Enforced By |
|------------|------|-------------|
| **Base images** | `python:<current-stable>-slim-bookworm` or `node:<current-LTS>-bookworm-slim`. **Never Alpine.** | `.windsurfrules`, `30-ops.md`, `AGENTS-compact.md` |
| **amd64** | All Docker images must support `linux/amd64`. VPS is x86_64 (AMD EPYC-Genoa). | `.windsurfrules`, `30-ops.md`, `check_docker.py` |
| **Deployment** | Docker Compose via **Coolify** on VPS. Not Vercel, Railway, or K8s. | `30-ops.md`, `AGENTS.md` |
| **Port ranges** | Python services: **8000–8099**. Frontend/Node.js: **3000–3099**. Register in `PORTS.md`. | `.windsurfrules`, `10-python.md`, `20-typescript.md` |
| **No hardcoded config** | Never hardcode `localhost`, DB strings, API keys. Use `os.getenv()` / `process.env`. | `.windsurfrules`, `10-python.md`, `20-typescript.md` |
| **Health endpoints** | Must test real dependencies (`SELECT 1`), not just return 200. | `.windsurfrules`, `10-python.md` |
| **Networking** | Coolify network (`coolify: external: true`). VPS internal: `http://service-name:PORT`. | `30-ops.md` |
| **Existing services first** | Before building, check if a Fabrik microservice or prebuilt container already solves the need. | `AGENTS.md` § Mandatory Pre-Flight |
| **Solo developer scope** | All architecture must be operable by one person (~50 hrs/week). No K8s, no polyglot backends. | `AGENTS.md` § Planning Constraints |

### Fabrik Infrastructure (Already Deployed)

| Service | Purpose | When to Use |
|---------|---------|-------------|
| PostgreSQL | Shared database | Default for all projects |
| Redis | Shared cache/queue | Only when PostgreSQL jobs table is insufficient |
| Gotenberg | PDF generation | `pdf.vps1.ocoron.com` — use instead of WeasyPrint for complex PDFs |
| MeiliSearch | Full-text search | `search.vps1.ocoron.com` — use instead of PostgreSQL FTS for faceted/typo-tolerant search |
| MinIO | S3-compatible object storage | `s3.vps1.ocoron.com` — use for file uploads, media |
| Apprise | Multi-channel notifications | `notify.vps1.ocoron.com` — use instead of direct API calls |
| Browserless | Headless Chrome | `browser.vps1.ocoron.com` — use for scraping, screenshots |
| n8n | Workflow automation | `auto.vps1.ocoron.com` — use for no-code integrations |

---

## Quick Decision Flowchart

Use this flowchart to quickly navigate to the right stack choice. Answer the questions in order.
**Note:** For Fabrik projects, check the overrides above first — several generic defaults differ.

---

### Level 1: What Are You Building?

```
START HERE
    │
    ├─► Web-based product? ────────────────────────► Go to SECTION A
    │
    ├─► Mobile app? ───────────────────────────────► Go to SECTION B
    │
    ├─► Desktop software? ─────────────────────────► Go to SECTION C
    │
    ├─► Backend/API/Services only? ────────────────► Go to SECTION D
    │
    ├─► AI/ML/Data product? ───────────────────────► Go to SECTION E
    │
    ├─► Hardware/IoT/Embedded? ────────────────────► Go to SECTION F
    │
    └─► Specialized (Games/AR/VR/TV/Car)? ─────────► Go to SECTION G
```

---

### SECTION A: Web-Based Products

```
What type of web product?
    │
    ├─► Marketing site / Landing page / SEO content?
    │       │
    │       └─► ANSWER: TypeScript + Next.js + Tailwind CSS
    │           • Escape hatch: Server/edge functions for custom logic
    │           • Add: Analytics, A/B testing, CMS, forms, consent banners
    │
    ├─► Full SaaS / Web app with backend?
    │       │
    │       ├─► Solo operator / AI-assisted coding?
    │       │       └─► ANSWER: TypeScript + React/Next.js + Node.js (monorepo)
    │       │
    │       └─► Enterprise / Team scale?
    │               └─► ANSWER: Go/Java backend + React frontend (separate)
    │
    │           • Escape hatch: Microservices for hotspots, managed services
    │           • Add: Auth, payments, DB, background jobs, observability
    │
    ├─► E-commerce?
    │       │
    │       ├─► Fastest GTM / MVP?
    │       │       └─► ANSWER: Platform-based (Shopify, etc.)
    │       │
    │       └─► Custom / Full control?
    │               └─► ANSWER: TypeScript web + backend services
    │
    │           • Escape hatch: Start platform, migrate custom later
    │           • Add: Payments, tax, shipping, CRM, anti-fraud
    │
    └─► Real-time (chat, live dashboards)?
            │
            └─► ANSWER: TypeScript/Node.js (WebSockets)
                • Escape hatch: Managed pub/sub, offload fanout
                • Add: Rate limiting, abuse prevention, backpressure
```

---

### SECTION B: Mobile Apps

```
Target platforms?
    │
    ├─► iOS + Android (both)?
    │       │
    │       ├─► Fast iteration / One codebase / AI-assisted?
    │       │       └─► ANSWER: React Native + TypeScript
    │       │
    │       └─► Performance-critical / Complex animations?
    │               └─► ANSWER: Flutter (Dart)
    │
    │           • Escape hatch: Native modules for unsupported APIs
    │           • Add: Push notifications, deep links, crash reporting, OTA
    │
    ├─► iOS only?
    │       │
    │       ├─► Deep Apple integration (HealthKit, etc.)?
    │       │       └─► ANSWER: Swift (native)
    │       │
    │       └─► Speed over native feel?
    │               └─► ANSWER: React Native + native screens
    │
    │           • Escape hatch: Webviews for non-critical screens
    │           • Add: App Store pipeline, signing, keychain, privacy manifests
    │
    └─► Android only?
            │
            ├─► Best UX / OEM integrations?
            │       └─► ANSWER: Kotlin (native)
            │
            └─► Kiosk / POS / Device fleet?
                    └─► ANSWER: Kotlin + MDM/kiosk controls

                • Escape hatch: Shared core + RN for UI if needed
                • Add: Play Store pipeline, device admin, permissions
```

---

### SECTION C: Desktop Software

```
Target operating system(s)?
    │
    ├─► macOS + Windows + Linux (all three)?
    │       │
    │       ├─► Fast ship / Shared UI?
    │       │       └─► ANSWER: Electron + TypeScript
    │       │
    │       └─► Smaller footprint / Performance?
    │               └─► ANSWER: Tauri (Rust)
    │
    │           • Escape hatch: Native helpers as subprocesses
    │           • Add: Auto-update, installers, signing, crash reporting
    │
    ├─► macOS only?
    │       │
    │       └─► ANSWER: Swift (native)
    │           • Escape hatch: Electron if speed > native feel
    │           • Add: Auto-update, notarization, signing, keychain
    │
    ├─► Windows only?
    │       │
    │       ├─► Enterprise / Office integration?
    │       │       └─► ANSWER: C#/.NET
    │       │
    │       └─► Internal tools?
    │               └─► ANSWER: Python or Electron
    │
    │           • Escape hatch: Electron for cross-platform
    │           • Add: Installer, auto-update, signing, telemetry
    │
    └─► Linux only?
            │
            └─► ANSWER: Electron (TS/Node) for speed
                • Alternatives: Qt (C++), GTK, Python + Qt
                • Add: Packaging (deb/rpm/AppImage), auto-update
```

---

### SECTION D: Backend / API / Services

```
What type of backend?
    │
    ├─► API only (no UI)?
    │       │
    │       ├─► Rapid iteration / Broad library coverage?
    │       │       └─► ANSWER: TypeScript + Node.js (REST/GraphQL)
    │       │
    │       └─► High concurrency / Performance?
    │               └─► ANSWER: Go
    │
    │           • Escape hatch: Move hot endpoints to Go/Rust
    │           • Add: OpenAPI, auth (JWT/OAuth), rate limiting, API gateway
    │
    ├─► Background workers / Batch processing?
    │       │
    │       ├─► Data-heavy / ML adjacent?
    │       │       └─► ANSWER: Python
    │       │
    │       └─► Web-adjacent / Queue-based?
    │               └─► ANSWER: Node.js
    │
    │           • Escape hatch: Specialized services for hottest tasks
    │           • Add: Task queues, retries, idempotency, dead-letter queues
    │
    ├─► Microservices platform?
    │       │
    │       └─► ANSWER: Go (services) + infra-as-code
    │           • Escape hatch: Polyglot services behind stable APIs
    │           • Add: K8s/serverless, service discovery, tracing
    │           • WARNING: Team-scale only, not for solo operators
    │
    ├─► Serverless / Functions-first?
    │       │
    │       └─► ANSWER: TypeScript/Node.js functions
    │           • Escape hatch: Migrate stateful parts to containers
    │           • Add: Cold-start mitigation, warmers, stateless design
    │
    ├─► CLI tool?
    │       │
    │       └─► ANSWER: Go
    │           • Reason: Single binary, minimal dependencies
    │           • Escape hatch: Plugin architecture
    │           • Add: Shell completions, config files, cross-platform builds
    │
    └─► Integration / Connectors (iPaaS-like)?
            │
            └─► ANSWER: Node.js/TypeScript
                • Escape hatch: Per-connector sandboxing
                • Add: OAuth handling, token refresh, rate limiting, retries
```

---

### SECTION E: AI / ML / Data Products

```
What type of AI/Data product?
    │
    ├─► LLM app / AI-powered features?
    │       │
    │       ├─► Using managed APIs (OpenAI, Anthropic, etc.)?
    │       │       └─► ANSWER: Python (backend) + TypeScript UI
    │       │
    │       └─► Self-hosted models?
    │               └─► ANSWER: Python + specialized inference stack
    │
    │           • Escape hatch: Isolate models behind APIs, swap providers
    │           • Add: Prompt versioning, eval harness, caching, guardrails
    │
    ├─► Analytics / BI / Reporting?
    │       │
    │       └─► ANSWER: SQL + Python (transform + orchestration)
    │           • Escape hatch: Separate compute from storage
    │           • Add: Data warehouse, lineage, quality checks, access control
    │
    ├─► Streaming data pipeline?
    │       │
    │       └─► ANSWER: Go/Java (stream services) + SQL/Python (consumers)
    │           • Escape hatch: Fall back to batch if streaming overkill
    │           • Add: Schema registry, replay strategy, backpressure
    │
    └─► RPA / Automation bots?
            │
            └─► ANSWER: Python + orchestration
                • Escape hatch: Switch to API integrations when UI breaks
                • Add: Job scheduler, failure detection, screenshot logs
```

---

### SECTION F: Hardware / IoT / Embedded

```
What type of hardware product?
    │
    ├─► Bare-metal MCU / RTOS (non-Android)?
    │       │
    │       ├─► Safety-critical?
    │       │       └─► ANSWER: Rust
    │       │
    │       └─► Standard firmware?
    │               └─► ANSWER: C
    │
    │           • Escape hatch: Move complexity to gateway/cloud
    │           • Add: OTA update strategy, watchdogs, hardware test harness
    │
    ├─► Android-based device (AOSP, kiosk, POS)?
    │       │
    │       └─► ANSWER: Kotlin (native Android)
    │           • Escape hatch: RN for UI + native services for device control
    │           • Add: MDM/kiosk control, remote updates, offline-first
    │
    ├─► Full IoT product (device + cloud + mobile)?
    │       │
    │       └─► ANSWER: C/Rust (device) + Go/Node (cloud) + React Native (mobile)
    │           • Escape hatch: Stable device protocol, swap cloud/mobile independently
    │           • Add: Device identity, provisioning, OTA, command & control
    │
    └─► Network/security agent (endpoint, proxy, VPN)?
            │
            └─► ANSWER: Go (fast distribution)
                • Alternatives: Rust (safety), C++ (deep OS)
                • Add: Auto-update, secure comms, hardening, policy engine
```

---

### SECTION G: Specialized Products

```
What specialized platform?
    │
    ├─► Game (mobile/PC/console)?
    │       │
    │       ├─► Fast production tools?
    │       │       └─► ANSWER: C# (Unity)
    │       │
    │       └─► AAA / Performance-critical?
    │               └─► ANSWER: C++ (Unreal)
    │
    │           • Escape hatch: Native plugins, external backend
    │           • Add: Asset pipeline, build automation, anti-cheat
    │
    ├─► Wearables (Apple Watch / Wear OS)?
    │       │
    │       └─► ANSWER: Swift (watchOS) / Kotlin (Wear OS)
    │           • Escape hatch: Push heavy logic to phone + backend
    │           • Add: Battery tuning, background limitation handling
    │
    ├─► TV apps (Apple TV / Android TV)?
    │       │
    │       └─► ANSWER: Swift (tvOS) / Kotlin (Android TV)
    │           • Escape hatch: Shared backend + shared UI patterns
    │           • Add: DRM, playback analytics, CDN integration
    │
    ├─► Car integrations (CarPlay / Android Auto)?
    │       │
    │       └─► ANSWER: Swift (CarPlay) / Kotlin (Android Auto)
    │           • Escape hatch: Core app on phone, car is projection
    │           • Add: Safety/UX compliance, limited templates
    │
    ├─► AR/VR apps?
    │       │
    │       └─► ANSWER: Unity/Unreal or platform-native
    │           • Escape hatch: Split compute to backend
    │           • Add: Asset pipeline, performance profiling
    │
    ├─► Browser extension?
    │       │
    │       └─► ANSWER: TypeScript + WebExtension APIs
    │           • Escape hatch: Offload heavy work to backend
    │           • Add: Permissions strategy, storage sync, anti-abuse
    │
    ├─► Public SDK / Client libraries?
    │       │
    │       └─► ANSWER: TypeScript SDK first (web + Node)
    │           • Then: Python, Java/Kotlin, Swift, C# as needed
    │           • Escape hatch: Generate SDKs from OpenAPI spec
    │           • Add: Versioning policy, docs, code samples, CI publishing
    │
    └─► Database / Storage engine?
            │
            └─► ANSWER: Rust (safety + performance)
                • Alternatives: C++, Go (simpler KV services)
                • Add: Fuzzing, property tests, crash consistency tests
```

---

### Quick Reference: Solo Operator Recommendations

For your profile (AI-assisted coding, solo operator, API-first, automation focus):

| If Building... | Generic Default | Fabrik Uses | Why Fabrik Differs |
|----------------|-----------------|-------------|--------------------|
| SaaS / Web App | TypeScript + Next.js + Node.js | **Next.js + TS frontend, Python + FastAPI backend** | Backend is Python for AI library access + Pydantic typing |
| Backend API | TypeScript + Node.js | **Python + FastAPI + Uvicorn** | Owner's primary stack, best ML/AI ecosystem |
| Mobile (both platforms) | React Native + TypeScript | React Native + TypeScript | ✅ Same — no override |
| CLI Tool | Go | **Python** (`src/fabrik/cli.py`) | Shares modules with backend, no separate binary needed |
| Background Workers | Node.js | **PostgreSQL jobs table + Python worker** | No Redis dependency by default |
| AI Features | Python backend + TS frontend | **Kilo CLI free → OpenAI/Anthropic → Local Ollama** | Budget-first: free before paid |
| Desktop App | Electron + TypeScript | Electron + TypeScript | ✅ Same — no override |

**Avoid (team-scale only):**
- Kubernetes / microservices architecture
- Polyglot backend stacks
- Self-hosted ML model serving (use managed APIs)

---

### Cost Signals (Missing from Original Table)

| Stack | Hosting Cost Impact |
|-------|---------------------|
| Go / Rust binaries | LOW - minimal RAM, cheap VPS |
| Node.js / Python | MEDIUM - more RAM required |
| Electron desktop | HIGH - memory-heavy |
| Serverless functions | VARIABLE - cheap at low volume, expensive at scale |
| K8s / Microservices | HIGH - ops overhead + compute |

---

## Complete Technology Stack Reference Table

The table below contains all original information without any summarization or shortening.

---

| Final product (deliverable) | Default stack (fastest reliable path) | Common alternatives (when default is not ideal) | Use this when you need… (requirements trigger) | If you have / prefer… (constraints & team reality) | "All-features" / escape hatch (how you avoid dead-ends) | Typical add-ons (almost always needed in real products) | Primary risks / failure modes | Mitigations / design patterns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Website (marketing, landing, SEO, content)** | **TypeScript + Next.js (Node.js runtime) + Tailwind CSS** | Static site generators; CMS-driven sites; plain HTML/CSS for ultra-simple | SEO, fast iteration on pages, forms, analytics, fast deployment | You want one stack that also grows into SaaS later | Escape hatch is **server functions / edge functions** for custom logic; integrate 3rd-party services for everything else | Analytics, A/B testing, CMS, newsletter/email capture, form handling, consent banners, performance monitoring | SEO regressions, slow page load, fragile forms, CMS lock-in | Static generation where possible, performance budgets, form validation + retries, CMS abstraction layer |
| **Web app / SaaS (full product UI + backend)** | **TypeScript + React/Next.js + Node.js API** (monorepo) | Go/Java backend; Python backend; separate frontend SPA + API | Auth, billing, dashboards, multi-tenant logic, CRUD + workflows | Agents can generate TS/React reliably; you want fastest product cycles | Escape hatch is **microservices** for hotspots and **managed services** for hard parts (payments, auth, storage, queues) | Auth provider, payments, database, background jobs, email/SMS, observability (logs/metrics/traces), feature flags | Tight coupling, schema drift, scaling bottlenecks, auth mistakes | Clear domain boundaries, API contracts, migrations, managed auth/billing, horizontal scaling |
| **Backend API only (no UI product)** | **TypeScript + Node.js** (REST/GraphQL) | Go; Java; Python; .NET | Public/internal API platform, integrations hub, partner endpoints | You want rapid iteration and broad library coverage | Escape hatch: move latency/CPU-critical endpoints to Go/Rust services; keep stable API contracts | OpenAPI/Swagger, auth (JWT/OAuth), rate limiting, request validation, API gateway, monitoring, audit logs | Breaking changes, abuse, poor observability | Strict versioning, OpenAPI-first, rate limiting, structured logging, contract tests |
| **Public SDK / client libraries** | **TypeScript SDK** first (web + Node) | Python SDK; Java/Kotlin; Swift; C# | You want adoption by developers, easy integration, typed interface | Your users are web developers or you want fastest first SDK | Escape hatch: generate SDKs from OpenAPI; keep a single canonical spec | Versioning policy, docs site, code samples, CI publishing, backward compatibility tests | SDK drift from API, breaking changes | Code generation from spec, semantic versioning, CI release automation |
| **Mobile app (iOS + Android)** | **React Native + TypeScript** | Flutter (Dart); native Swift + Kotlin | One codebase, fastest multi-platform delivery, frequent iterations | You don't code; agents build; you want the broadest talent/library pool | **Default to React Native + TypeScript for iOS+Android speed, and rely on native modules when you hit unsupported device APIs.** | Push notifications, deep links, crash reporting, analytics, OTA update strategy, offline sync, secure storage, app store release automation | Native feature gaps, performance issues, store rejections | Capability abstraction layer, native module templates, performance profiling, staged rollouts |
| **Native iOS app** | **Swift** | React Native shell + native screens; Flutter; SwiftUI vs UIKit | Best iOS UX, deep Apple platform integration, performance-sensitive UI | Apple-first audience, heavy Apple APIs (HealthKit, advanced background modes, etc.) | Escape hatch: keep a shared backend + shared data contracts; embed webviews for non-critical screens | App Store pipeline, signing/certificates, background tasks, keychain, privacy manifests, observability | App Store rejection, background task limits | Apple HIG compliance, entitlement audits, feature flags, background task budgeting |
| **Native Android app** | **Kotlin** | RN/Flutter; legacy Java; Kotlin Multiplatform for shared core | Best Android UX, deep Android device APIs, OEM integrations | Android-first audience, kiosk/POS/device fleets | Escape hatch: shared core libraries; embed RN for shared UI modules if needed | Play Store pipeline, device admin/kiosk, background services, permissions strategy, observability | Fragmentation, OEM bugs, permission complexity | Device matrix testing, permission abstraction, feature detection, OEM-specific fallbacks |
| **macOS desktop software** | **Swift** (native) | Electron (TS/Node); .NET via cross-platform frameworks | Apple desktop integrations, native UX, system extensions | macOS-only product | Escape hatch: share business logic in a backend; use Electron if speed > native feel | Auto-update, notarization, signing, crash reporting, settings, keychain | OS version breakage, signing issues | Auto-update channels, CI notarization, compatibility testing |
| **Windows desktop software** | **C#/.NET** | Electron (TS/Node); C++ for performance; Python for internal tools | Enterprise desktop apps, Windows APIs, Office integration | Microsoft-heavy customers | Escape hatch: Electron for cross-platform; native C# for deep OS hooks | Installer, auto-update, signing, telemetry, crash reporting | Installer failures, OS API drift | MSI/ClickOnce best practices, auto-update rollback, telemetry |
| **Linux desktop GUI app** | **Electron (TS/Node)** for speed | Qt (C++); GTK; Python + Qt | Cross-distro packaging, fast UI iteration | You want one codebase across OS | Escape hatch: isolate native integrations per distro; containerize where possible | Packaging (deb/rpm/AppImage), auto-update, sandboxing, logging | Distro incompatibility | AppImage/Flatpak, minimal native deps, CI matrix builds |
| **Browser extension (Chrome/Edge/Firefox)** | **TypeScript + WebExtension APIs** | Plain JS; frameworks (React in popup/options) | Lightweight product, browser-native distribution, quick iteration | You want minimal backend, direct user reach | Escape hatch: offload heavy work to a backend; keep extension thin | Permissions strategy, storage sync, update flow, telemetry, anti-abuse measures | Permission rejection, store policy changes | Least-privilege permissions, policy monitoring, feature flags |
| **Cross-platform desktop app (macOS + Windows + Linux)** | **Electron + TypeScript** | Tauri (Rust); Qt; .NET cross-platform | Fast ship, shared UI code, frequent updates | Agents can generate TS/Electron quickly | Escape hatch: native helpers (Swift/Kotlin/C#) called as subprocesses; or Tauri for tighter footprint | Auto-update, installers, signing, sandboxing, crash reporting | High memory usage, security surface | Background process isolation, code signing, auto-update hardening |
| **Command-line tool (Unix CLI)** | **Go** | Node.js for simple CLIs; Python for internal scripts; Rust for performance/safety | Single binary distribution, ops/dev tooling, fast execution | You want minimal runtime dependencies | Escape hatch: plugin architecture; call out to native libs when needed | Shell completions, config files, telemetry (optional), cross-platform builds | Breaking flags, UX friction | Stable CLI contracts, config files, backwards compatibility |
| **Background worker / batch processing product** | **Python** (data-heavy) or **Node.js** (web-adjacent) | Go for concurrency; Java for enterprise | Scheduled jobs, ETL, processing queues, long-running tasks | You want to separate heavy work from API servers | Escape hatch: move hottest tasks into specialized services; use managed queues | Task queues, retries/backoff, idempotency, dead-letter queues, monitoring, audit logs | Job duplication, silent failures | Idempotent jobs, retries with DLQ, monitoring + alerts |
| **Cloud microservices platform** | **Go** (services) + infra-as-code | Node.js services; Java services | Many services, high concurrency, predictable deployment | Infra/devops strength matters | Escape hatch: polyglot services behind stable APIs; service mesh if needed | Kubernetes/serverless, service discovery, config management, tracing, SRE playbooks | Operational complexity | Service templates, golden paths, observability-first design |
| **Serverless app (functions-first)** | **TypeScript/Node.js functions** | Python functions; Go functions | Spiky workloads, pay-per-use, quick prototypes | You want minimal ops | Escape hatch: migrate heavy or stateful parts to containers/services | Monitoring, cold-start mitigation, auth, queues, storage, CI/CD | Cold starts, vendor lock-in | Warmers, stateless design, abstraction over provider APIs |
| **Real-time app (chat, live dashboards, multiplayer-ish)** | **TypeScript/Node.js** (WebSockets) | Go; Elixir; managed realtime services | Low-latency updates, presence, streaming events | You want fastest iteration | Escape hatch: managed pub/sub and state stores; offload fanout | Pub/sub, rate limiting, abuse prevention, observability, backpressure strategy | Fanout overload, abuse | Rate limits, backpressure, managed pub/sub |
| **AI solution (LLM app, ML inference, data science product)** | **Python** (model/inference/services) + **TypeScript** UI | Go/Java for serving; Rust for performance-critical inference wrappers | ML ecosystem, rapid experimentation, pipelines, evaluation loops | You want easiest access to AI tooling | Escape hatch: isolate models behind APIs; swap providers/models without changing client logic | Prompt/versioning, eval harness, vector DB (if needed), caching, guardrails, logging, human feedback loops | Model drift, cost overruns | Versioned prompts, evals, caching, usage caps |
| **Data product: analytics/BI layer** | **SQL + Python** (transform + orchestration) | JVM/Spark stack; managed ELT tools | Dashboards, KPI pipelines, reporting, cohort analysis | You want reliable, repeatable data delivery | Escape hatch: separate compute from storage; incremental pipelines | Data warehouse, lineage, data quality checks, access control, audit logs | Bad data, silent errors | Data tests, lineage tracking, access controls |
| **Streaming data pipeline** | **Go/Java** for stream services; **SQL/Python** for consumers | Managed streaming platforms | Event-driven systems, near-real-time metrics | You need sustained throughput | Escape hatch: fall back to batch if streaming overkill; decouple consumers | Schema registry, replay strategy, backpressure, monitoring, alerting | Consumer lag, schema breaks | Schema registry, replayable topics, backpressure |
| **Integration / iPaaS-like connector product** | **Node.js/TypeScript** (connectors) | Python connectors; Go for agents | Connect SaaS APIs, sync data, webhooks, ETL-ish flows | You want fast connector iteration | Escape hatch: connector sandboxing; split into per-connector workers | OAuth handling, token refresh, rate limiting, retries, mapping UI, audit trails | API changes, rate limits | Adapter pattern, retries, schema mapping |
| **RPA / automation bots (UI automation, ERP, email workflows)** | **Python** (automation) + orchestration | Node.js automation; vendor RPA platforms | Automate repetitive business ops, scraping, UI clicking | You want "no human in loop" operations | Escape hatch: when UI breaks, switch to API integrations; build monitoring | Job scheduler, failure detection, screenshot logs, anti-breakage strategy | UI fragility | API-first fallback, monitoring, alerts |
| **Payments / fintech front-end product** | **TypeScript + Web** + mobile RN shell | Native mobile for strict UX; Java/Go backend | KYC, payments, compliance-heavy flows | Enterprise/compliance constraints | Escape hatch: use regulated payment providers; keep compliance boundaries external | Audit logs, encryption, access controls, risk monitoring, incident response | Regulatory breaches | External providers, audit trails, segregation of duties |
| **E-commerce product** | **TypeScript web** + backend services | Platform-based (Shopify etc.) | Catalog, checkout, inventory integrations | You want fastest GTM | Escape hatch: start on platform, migrate custom later | Payments, tax, shipping, CRM, analytics, anti-fraud | Platform limits | Modular integrations, data portability |
| **Game product (mobile/PC/console)** | **C# (Unity)** for speed | C++ (Unreal) for AAA/perf; native engines | 3D/2D games, physics, real-time rendering | You want fastest production tools | Escape hatch: native plugins for platform APIs; external backend services | Asset pipeline, build automation, telemetry, anti-cheat, matchmaking | Performance bottlenecks | Profiling, asset budgets, engine tooling |
| **Wearables app (Apple Watch / Wear OS)** | **Swift (watchOS)** / **Kotlin (Wear OS)** | Companion-only minimal apps; RN with native components | Device sensors, glanceable UX | Platform constraints are strong | Escape hatch: push heavy logic to phone + backend | Background limitations handling, battery/performance tuning | Battery drain | Offload compute, background limits |
| **TV apps (Apple TV / Android TV)** | **Swift/tvOS** / **Kotlin/Android TV** | Cross-platform only for limited UI | 10-foot UI, remote navigation, media | Media-first products | Escape hatch: shared backend + shared UI patterns; native where required | DRM, playback analytics, CDN integration | Input UX issues | Platform UI guidelines, testing |
| **Car integrations (CarPlay / Android Auto)** | **Swift/CarPlay** / **Kotlin/Android Auto** | Not a general cross-platform domain | Automotive UX constraints, navigation/media | Strict platform rules | Escape hatch: core app runs on phone; car is a projection interface | Safety/UX compliance, limited templates | Rejection by platform | Strict template compliance |
| **AR/VR apps** | Platform-native stacks | Unity/Unreal | High-performance rendering, sensors | Specialized hardware | Escape hatch: split compute to backend; keep client focused | Asset pipeline, performance profiling, device compatibility | Motion sickness, perf | Frame budgets, profiling |
| **Embedded firmware (non-Android MCU/RTOS)** | **C** (default) | Rust (safety-critical); C++ (where supported) | Tight memory, deterministic timing, bare-metal control | Hardware constraints dominate | Escape hatch: move complexity to companion gateway or cloud | OTA update strategy, watchdogs, hardware test harness | Bricking devices | Dual-bank OTA, watchdogs |
| **Embedded device "via Android" (AOSP device, kiosk/POS/IoT gateway)** | **Kotlin** (native Android) | RN UI shell + native services | Full Android device stack, OEM APIs, kiosk | Device fleet management | Escape hatch: native services for device control + RN for UI if desired | MDM/kiosk control, remote updates, telemetry, offline-first logic | Device fleet drift | Centralized MDM, remote updates |
| **Network/security agent (endpoint, proxy, VPN-ish, collectors)** | **Go** (fast distribution) | Rust for safety; C++ for deep OS | Low-level networking, endpoint integration | Needs robust ops and safety | Escape hatch: split into privileged native core + userland UI | Auto-update, secure comms, hardening, policy engine, logging | Security vulnerabilities | Least privilege, audits, auto-update |
| **Database engine / storage engine component** | **Rust** (safety + perf) | C++; Go (for simpler KV services) | Performance-critical, correctness-critical | You can afford slower initial dev | Escape hatch: keep a stable API layer; rigorous testing | Fuzzing, property tests, perf benchmarking, crash consistency tests | Data corruption | Fuzzing, invariants, WAL |
| **Hardware + cloud + mobile "full IoT product"** | **C/Rust (device)** + **Go/Node (cloud)** + **React Native (mobile)** | Android gateway variants | End-to-end product with device fleet | You want modularity and replaceability | Escape hatch: device protocol stable; swap cloud/mobile independently | Device identity, provisioning, OTA, telemetry, command & control, security updates | System-wide failures | Clear protocol contracts, staged rollouts |

---

## Analysis & Commentary

### Strengths of This Table

1. **Escape hatch column is valuable** — Most stack guides ignore what happens when the default choice fails. This acknowledges reality: you'll hit walls, and you need pre-planned exits.

2. **Realistic about TypeScript dominance** — For AI-assisted coding and fast iteration, the table correctly gravitates toward TS/Node for most web-adjacent work. Agents generate TS/React reliably.

3. **Risk/mitigation pairing** — Having risks and mitigations side-by-side forces architectural thinking upfront.

4. **Comprehensive coverage** — From firmware to fintech, the table covers edge cases most guides ignore.

### Gaps & Weaknesses

| Gap | Impact |
|-----|--------|
| **No deployment/hosting column** | Stack choice is inseparable from where it runs. Vercel vs Railway vs VPS vs K8s changes the calculus. |
| **No cost signals** | Go/Rust binaries = cheap hosting. Node/Python = more RAM. For bootstrapped builds, this matters. |
| **AI solution row is too vague** | "Python + TS UI" doesn't address the real decision: managed inference vs self-hosted vs hybrid. |
| **No "solo operator" vs "team" distinction** | Some stacks (microservices, K8s) are team-scale only. Table doesn't flag this. |
| **No maintenance burden indicator** | Some stacks require ongoing attention (K8s, self-hosted ML), others are "set and forget" (serverless, managed services). |

### For Fabrik Specifically (Actual Implementation)

Fabrik is a **deployment orchestration platform** with AI-powered agent management. The actual stack:

| Layer | Technology | Location |
|-------|-----------|----------|
| CLI & orchestrator | **Python** (Click CLI + FastAPI) | `src/fabrik/cli.py`, `src/fabrik/` |
| Backend APIs | **Python + FastAPI + Uvicorn** | Per-project `src/main.py` |
| Frontend (SaaS UIs) | **Next.js 14 + TypeScript + Tailwind** | Per-project `app/` |
| Infrastructure | **Docker Compose via Coolify** on x86_64 VPS | `compose.yaml` per project |
| Database | **PostgreSQL 16** (shared) | Coolify-managed `postgres-main` |
| AI agent selection | **Kilo CLI + Gemini 3.1 Pro** (~$0.19/day) | `scripts/kilo-benchmarks/role_mapper.py` |
| Monitoring | **Netdata** (active) + Grafana/Prometheus/Loki (config ready) | VPS services |

This differs from the generic guide's recommendation of "TypeScript monorepo + Go CLI" because Fabrik's backend logic (scaffold, sync, audit, orchestration) is Python-native and shares modules with the CLI.

---

## Document Information

- **Created**: January 2026
- **Purpose**: Technology stack decision reference for product development
- **Format**: Decision flowchart + complete reference table
- **Usage**: Navigate via flowchart for quick decisions, reference table for detailed analysis
