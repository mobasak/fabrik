# Frontend UI integration skill

> A reusable skill for implementing typed, tested frontend workflows against existing backend APIs in enterprise codebases.

This skill is designed for large enterprise frontends (React/TypeScript, Next.js, or similar) where Droids implement or extend user-facing flows against existing backend APIs.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/frontend-ui-integration/
├── SKILL.md
├── references.md (optional)
├── design-system.md (optional)
└── accessibility-checklist.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/frontend-ui-integration
   ```

2. **Copy the skill content below into `.factory/skills/frontend-ui-integration/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to implement a UI feature, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/frontend-ui-integration/SKILL.md`:

```md  theme={null}
---
name: frontend-ui-integration
description: Implement or extend a user-facing workflow in a web application, integrating with existing backend APIs. Use when the feature is primarily a UI/UX change backed by existing APIs, affects only the web frontend, and requires following design system, routing, and testing conventions.
---
# Skill: Frontend UI integration

## Purpose

Implement or extend a user-facing workflow in our primary web application, integrating with **existing backend APIs** and following our **design system, routing, and testing conventions**.

## When to use this skill

- The feature is primarily a **UI/UX change** backed by one or more existing APIs.
- The backend contracts, auth model, and core business rules **already exist**.
- The change affects **only** the web frontend (no schema or service ownership changes).

## Inputs

- **Feature description**: short narrative of the user flow and outcomes.
- **Relevant APIs**: endpoints, request/response types, and links to source definitions.
- **Target routes/components**: paths, component names, or feature modules.
- **Design references**: Figma links or existing screens to mirror.
- **Guardrails**: performance limits, accessibility requirements, and any security constraints.

## Out of scope

- Creating new backend services or changing persistent data models.
- Modifying authentication/authorization flows.
- Introducing new frontend frameworks or design systems.

## Conventions

- **Framework**: React with TypeScript.
- **Routing**: use the existing router and route layout patterns.
- **Styling**: use the in-house design system components (Buttons, Inputs, Modals, Toasts, etc.).
- **State management**: prefer the existing state libraries (e.g., React Query, Redux, Zustand) and follow established patterns.

## Required behavior

1. Implement the UI changes with **strong typing** for all props and API responses.
2. Handle loading, empty, error, and success states using existing primitives.
3. Ensure the UI is **keyboard accessible** and screen-reader friendly.
4. Respect feature flags and rollout mechanisms where applicable.

## Required artifacts

- Updated components and hooks in the appropriate feature module.
- **Unit tests** for core presentation logic.
- **Integration or component tests** for the new flow (e.g., React Testing Library, Cypress, Playwright) where the repo already uses them.
- Minimal **CHANGELOG or PR description text** summarizing the behavior change (to be placed in the PR, not this file).

## Implementation checklist

1. Locate the relevant feature module and existing components.
2. Confirm the backend APIs and types, updating shared TypeScript types if needed.
3. Implement the UI, wiring in API calls via the existing data layer.
4. Add or update tests to cover the new behavior and edge cases.
5. Run the required validation commands (see below).

## Verification

Run the following (adjust commands to match the project):

- `pnpm lint`
- `pnpm test -- --runInBand --watch=false`
- `pnpm typecheck` (if configured separately)

The skill is complete when:

- All tests, linters, and type checks pass.
- The new UI behaves as specified across normal, error, and boundary cases.
- No unrelated files or modules are modified.

## Safety and escalation

- If the requested change requires backend contract changes, **stop** and request a backend-focused task instead.
- If design references conflict with existing accessibility standards, favor accessibility and highlight the discrepancy in the PR description.
```


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Service integration skill

> A reusable skill for extending existing services and wiring integrations in complex enterprise codebases.

Use this skill when a feature requires changes to one or more backend services in a **shared, multi-team codebase** – for example, adding a new endpoint, publishing an event, or calling out to a dependency owned by another team.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/service-integration/
├── SKILL.md
├── schemas/ (optional)
├── patterns.md (optional)
└── observability-checklist.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/service-integration
   ```

2. **Copy the skill content below into `.factory/skills/service-integration/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to extend a backend service or wire an integration, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/service-integration/SKILL.md`:

```md  theme={null}
---
name: service-integration
description: Extend or integrate with existing services in a shared monorepo while preserving ownership boundaries, reliability standards, and observability requirements. Use when changes require adding or modifying backend APIs, jobs, or events in services with clear domain boundaries.
---
# Skill: Service integration in a complex codebase

## Purpose

Extend or integrate with existing services in our main backend codebase while preserving ownership boundaries, reliability standards, and observability requirements.

## When to use this skill

- The change requires adding or modifying a backend API, job, or event.
- The service lives in a **shared monorepo** with clear ownership and domain boundaries.
- The work may require coordination with other teams, but the main implementation happens in our services.

## Inputs

- **Business requirement**: short description of the user or system behavior change.
- **Primary service(s)**: names/paths of the services and domains involved.
- **Existing contracts**: relevant API schemas, events, or message formats.
- **Non-functional requirements**: latency, error budget, data retention, and throughput expectations.
- **Change management**: rollout strategy, feature flags, or migration plan.

## Out of scope

- Greenfield systems that require new infrastructure or data stores.
- Cross-region or cross-cloud replication design.
- Changes that conflict with established ownership boundaries without prior approval.

## Conventions

- Follow the **domain boundaries** and module layout described in `AGENTS.md` and internal architecture docs.
- Use existing **configuration, logging, metrics, and tracing** patterns.
- Reuse established **error handling** and **retry/backoff** utilities.

## Required behavior

1. Introduce new APIs, jobs, or events using existing framework patterns.
2. Maintain backwards compatibility wherever possible; if breaking changes are required, document migration steps.
3. Ensure all new behavior is observable via logs, metrics, and/or traces.
4. Respect existing security and privacy requirements (authN/Z, PII handling, data residency).

## Required artifacts

- Code changes in the relevant service(s) and domain modules.
- **Unit tests** for core logic and boundary conditions.
- **Integration or contract tests** for new or modified interfaces, where harnesses exist.
- Updated **runbooks or design docs** only if required by your team's process (link from the PR description instead of duplicating here).

## Implementation checklist

1. Identify ownership and confirm which service(s) should change.
2. Map the data and control flow across services and dependencies.
3. Design the integration surface (API, event, or job) and validate it against existing conventions.
4. Implement the change, keeping related files and modules co-located.
5. Add or update tests at the appropriate layers (unit, integration, contract).
6. Ensure logs/metrics/traces make the new behavior debuggable in production.
7. Wire in feature flags or configuration for safe rollout if necessary.

## Verification

Run the service-level validation commands, for example:

- `pnpm test --filter <service>` or `pytest` in the service directory
- `pnpm lint` or equivalent linter for the language in use
- Any existing **contract or integration test suites** referenced from `AGENTS.md` or service docs

The skill is complete when:

- All relevant tests and linters pass.
- The new integration behaves correctly in local or staging environments.
- Observability signals (logs, metrics, traces) show the expected behavior without noisy regressions.

## Safety and escalation

- If the change touches **shared schemas, core auth logic, billing, or compliance-critical data**, stop and request explicit human approval and design review.
- If dependencies owned by other teams need changes, create or update their tickets and clearly document assumptions and contract expectations in the PR.
```


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Internal data querying skill

> A reusable skill for safely querying internal analytics and data services and producing shareable, reproducible artifacts.

Use this skill when Droids need to answer questions using **internal data sources** – analytics warehouses, reporting databases, or internal data APIs – in a way that is safe, auditable, and reproducible.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/data-querying/
├── SKILL.md
├── metrics.md (optional)
├── examples.sql (optional)
└── data-governance.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/data-querying
   ```

2. **Copy the skill content below into `.factory/skills/data-querying/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to query internal data or analyze metrics, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/data-querying/SKILL.md`:

```md  theme={null}
---
name: data-querying
description: Query internal data services to answer well-scoped questions, producing results and artifacts that are safe to share and easy to re-run. Use when stakeholders need metrics, trends, or data slices from internal warehouses, marts, or reporting APIs.
---
# Skill: Internal data querying

## Purpose

Query internal data services to answer well-scoped questions, producing results and artifacts that are safe to share and easy to re-run.

## When to use this skill

- A stakeholder asks for **metrics, trends, or slices** that rely on internal data.
- The answers can be derived from existing **warehouses, marts, or reporting APIs**.
- The request needs a **reproducible query** and not an ad-hoc manual export.

## Inputs

- **Business question**: one or two sentences describing what we want to know.
- **Time range and filters**: date boundaries, customer segments, environments, etc.
- **Source systems**: names of warehouses, schemas, or APIs to use.
- **Data sensitivity notes**: whether PII, financial data, or regulated data is involved.

## Out of scope

- Direct queries against production OLTP databases unless explicitly allowed.
- Creating new pipelines or ingestion jobs.
- Sharing raw PII or secrets outside approved destinations.

## Conventions

- Use the **preferred query layer** (e.g., dbt models, semantic layer, analytics API) instead of raw tables when available.
- Follow established **naming and folder conventions** for saved queries or analysis notebooks.
- Respect internal **data classification and access control** policies.

## Required behavior

1. Translate the business question into a precise query spec (metrics, dimensions, filters).
2. Choose appropriate sources and explain tradeoffs if multiple options exist.
3. Write queries that are performant and cost-conscious for the target system.
4. Produce both **results** and a **re-runnable query artifact** (SQL, API call, notebook, or dashboard link).

## Required artifacts

- Query text (SQL, DSL, or API request) checked into the appropriate repo or folder.
- A short **analysis summary** capturing methodology, assumptions, and caveats.
- Links to any **dashboards, notebooks, or reports** created.

## Implementation checklist

1. Clarify the business question, time range, and filters.
2. Identify the best data source(s) based on freshness, completeness, and governance.
3. Draft the query, validate it on a limited time window or sample.
4. Check for joins, filters, and aggregations that could distort the answer; fix as needed.
5. Save the query in the approved location with a descriptive name.
6. Capture results and summarize key findings and limitations.

## Verification

Use whatever validation mechanisms exist for your data stack, for example:

- `dbt test` in the relevant project
- Unit or regression tests for custom metrics or transformations
- Manual spot checks against known benchmarks or historical reports

The skill is complete when:

- The query runs successfully within acceptable time and cost bounds.
- Results match expectations or known reference points (within reasonable tolerance).
- The query and results are documented enough for another engineer or analyst to reuse.

## Safety and escalation

- If the query touches **sensitive or regulated data**, confirm that the destination (PR, doc, ticket) is an approved location before including any sample rows.
- If you identify data quality issues, file or update a data-quality ticket and call them out prominently in the analysis summary.
```


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Internal tools skill

> A reusable skill for building and extending internal tools that support engineers, operators, and support teams.

Use this skill when Droids are building or extending **internal-facing applications** – admin panels, support consoles, operational dashboards, or engineering utilities – where reliability and safety matter more than surface polish.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/internal-tools/
├── SKILL.md
├── rbac.md (optional)
├── audit-patterns.md (optional)
└── operations-checklist.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/internal-tools
   ```

2. **Copy the skill content below into `.factory/skills/internal-tools/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to build or extend internal tools like admin panels or operational dashboards, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/internal-tools/SKILL.md`:

```md  theme={null}
---
name: internal-tools
description: Design, implement, or extend internal tools that help employees operate the system safely and efficiently, while respecting access controls and audit requirements. Use when building for internal staff interacting with production-adjacent systems.
---
# Skill: Internal tools development

## Purpose

Design, implement, or extend internal tools that help employees operate the system safely and efficiently, while respecting access controls and audit requirements.

## When to use this skill

- The audience is **internal staff** (engineers, SREs, support, operations, finance, etc.).
- The tool interacts with **production-adjacent systems** (feature flags, incidents, customer data, billing, etc.).
- The change is scoped to internal workflows and does not directly alter customer-facing UX.

## Inputs

- **User personas** and teams who will use the tool.
- **Workflows** to support (create/update actions, approvals, review flows).
- **Systems touched**: services, queues, flags, and data stores.
- **Risk classification**: what can go wrong if the tool misbehaves or is misused.

## Out of scope

- Tools that require new identity providers or SSO integrations.
- Changes that bypass existing approval or change-management processes.
- Direct manual-write tooling for core financial or compliance systems without explicit approval.

## Conventions

- Use the **standard stack** for internal tools (framework, component library, backend pattern) already used in the repo.
- Apply **role-based access control** and logging patterns consistently.
- Prefer **read-only views and guarded actions** (confirmation dialogs, requiring justification text, etc.) for high-risk operations.

## Required behavior

1. Implement flows that make the happy path fast while making destructive actions clearly intentional.
2. Ensure all state changes are logged with **who**, **what**, and **when**, and link to existing audit/logging infrastructure.
3. Provide clear feedback on success, errors, and partial failures.
4. Design for operational debugging: include ids, timestamps, and links to related systems.

## Required artifacts

- Frontend and backend changes in the appropriate internal-tools modules.
- **Automated tests** for critical operations (at least unit tests; integration tests where harnesses exist).
- Baseline **operational runbook entry** or link explaining how to use the tool and what to do when it fails, if required by your team.

## Implementation checklist

1. Clarify workflow boundaries and risk level with stakeholders.
2. Identify existing components, endpoints, and patterns to reuse.
3. Implement the UI, backend handlers, and data access using established abstractions.
4. Add safeguards: confirmations, rate limiting, or approvals depending on risk.
5. Wire up logging and metrics so usage and failures are visible.
6. Add or update tests and any required runbook entries.

## Verification

Run the standard validation commands for the relevant apps/services (tests, lint, type checks). In addition:

- Exercise both **happy paths and failure modes** in a safe environment.
- Confirm that audit logs and metrics reflect actions accurately.

The skill is complete when:

- Validation commands pass.
- Flows behave correctly in staging or an equivalent environment.
- Stakeholders can perform their target workflows without manual DB access or unsafe workarounds.

## Safety and escalation

- If an operation could cause **irreversible data loss or external customer impact**, require higher-level approvals and consider additional controls (dual control, time-boxed access, or break-glass procedures).
- If you discover that existing internal tools bypass critical controls, document this clearly and escalate through the appropriate risk or security channel.
```


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt



# Vibe coding skill

> A reusable skill for rapidly prototyping and building modern web applications from scratch with a creative, experimental approach.

This skill enables Droids to act as a vibe coding partner, creating complete web applications from scratch on your local machine with speed and creativity. Unlike hosted builders like Lovable, Bolt, or v0, this skill works entirely in your local environment, giving you full control over the stack, deployment, and evolution of your application while maintaining the rapid, creative flow of vibe-based development.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/vibe-coding/
├── SKILL.md
├── framework-references.md (optional)
├── deployment-patterns.md (optional)
└── accessibility-checklist.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/vibe-coding
   ```

2. **Copy the skill content below into `.factory/skills/vibe-coding/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to rapidly prototype or build a web application from scratch, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/vibe-coding/SKILL.md`:

````md  theme={null}
---
name: vibe-coding
description: Rapidly prototype and build modern, responsive web applications from scratch using current frameworks and libraries. Use when you want to quickly create a new web app with full local control, creative flow, and modern best practices. Local alternative to Lovable, Bolt, and v0.
---
# Skill: Vibe coding

## Purpose

Rapidly prototype and build modern, responsive web applications from scratch using current frameworks, libraries, and best practices. This skill handles everything from initial project setup to implementing features, styling, and basic deployment configuration with a focus on creative flow and quick iteration.

## When to use this skill

- You want to **rapidly prototype** a new web application idea.
- You're in a **creative flow** and want to build something quickly without context switching.
- You want to use **modern frameworks** like React, Next.js, Vue, Svelte, or similar.
- You prefer **local development** with full control rather than hosted builder environments.
- You want to **experiment and iterate fast** on designs and features.

## Key differences from Lovable/Bolt/v0

Unlike hosted vibe-coding tools (Lovable, Bolt, v0):

- **Runs locally**: All code lives on your machine, not in a hosted environment.
- **No infrastructure lock-in**: You control deployment, hosting, and infrastructure choices.
- **Framework flexibility**: Not limited to a specific tech stack; can use any modern framework.
- **Full backend support**: Can integrate with any backend, run local servers, use databases, etc.
- **Version control native**: Built with git workflows in mind from the start.
- **No runtime environment required**: Build from scratch locally, not dependent on their infrastructure.

## Inputs

- **Application description**: Purpose, key features, and target users.
- **Technology preferences**: Desired frameworks (React/Next.js/Vue/Svelte), styling approach (Tailwind/CSS-in-JS/CSS Modules), and any specific libraries.
- **Feature requirements**: Core functionality, user flows, and data models.
- **Design direction**: Style preferences, color schemes, or reference sites.
- **Deployment target**: Where you plan to host (Vercel, Netlify, AWS, self-hosted, etc.).

## Out of scope

- Managing production infrastructure or cloud provider accounts.
- Creating complex backend microservices architecture (use service-integration skill instead).
- Mobile native app development (iOS/Android).

## Conventions and best practices

### Framework selection
- **Always search for the most current documentation** from official sources before implementing.
- Example: Search https://nextjs.org/docs for Next.js, https://react.dev for React, etc.
- **Never hardcode outdated commands or patterns** – always verify current best practices.

### Project initialization
1. Search official docs for the latest initialization command (e.g., `npx create-next-app@latest`).
2. Use TypeScript by default for type safety.
3. Set up ESLint and Prettier for code quality.
4. Initialize git repository from the start.

### Architecture patterns
- **Component-based**: Break UI into small, reusable components.
- **Type-safe**: Use TypeScript throughout for better developer experience.
- **Responsive by default**: Mobile-first design approach.
- **Accessibility first**: Semantic HTML, ARIA labels, keyboard navigation.
- **Performance-conscious**: Code splitting, lazy loading, optimized images.

### Styling approach
- Use modern CSS frameworks (Tailwind CSS recommended for rapid development).
- Implement consistent design system with reusable tokens for colors, spacing, typography.
- Support light/dark mode when appropriate.
- Ensure proper contrast ratios and accessibility.

### State and data
- Choose appropriate state management (React Context, Zustand, Redux) based on complexity.
- Use modern data fetching patterns (React Query, SWR, or framework built-ins like Next.js App Router).
- Implement proper loading, error, and empty states.

### Backend integration
- If backend is needed, set up API routes or server components appropriately.
- For databases, use type-safe ORMs (Prisma, Drizzle) when possible.
- Implement proper error handling and validation.

## Required behavior

1. **Research current best practices**: Before any implementation, search for and reference the latest official documentation.
2. **Initialize properly**: Set up project with all necessary tooling, configs, and directory structure.
3. **Implement features incrementally**: Build and test features one at a time.
4. **Write clean, maintainable code**: Follow framework conventions and best practices.
5. **Handle edge cases**: Loading states, errors, empty states, validation.
6. **Ensure accessibility**: Proper semantic HTML, ARIA labels, keyboard navigation.
7. **Test critical paths**: Write tests for core functionality.
8. **Document setup and usage**: README with setup instructions, environment variables, and deployment notes.

## Required artifacts

- Fully initialized project with all configuration files.
- Clean, well-organized component and page structure.
- Styling implementation (Tailwind config, CSS modules, or chosen approach).
- **Tests** for critical user flows and business logic.
- **README.md** with:
  - Project description and features
  - Setup instructions
  - Development commands
  - Environment variables needed
  - Deployment guidance
- **.gitignore** properly configured.
- **Package.json** with clear scripts and dependencies.

## Implementation checklist

### 1. Discovery and planning
- [ ] Search for current best practices for chosen framework
- [ ] Review official documentation for initialization commands
- [ ] Understand feature requirements and user flows
- [ ] Plan component hierarchy and data flow

### 2. Project initialization
- [ ] Run current framework initialization command
- [ ] Set up TypeScript, ESLint, Prettier
- [ ] Initialize git repository
- [ ] Create basic directory structure

### 3. Design system setup
- [ ] Set up styling solution (Tailwind, CSS-in-JS, etc.)
- [ ] Define color palette and design tokens
- [ ] Create base components (Button, Input, Card, etc.)
- [ ] Implement responsive layout system

### 4. Feature implementation
- [ ] Build pages and routes
- [ ] Implement components with proper typing
- [ ] Add state management where needed
- [ ] Integrate data fetching and APIs
- [ ] Handle loading, error, and empty states

### 5. Quality and polish
- [ ] Add accessibility features (ARIA, keyboard nav)
- [ ] Optimize performance (code splitting, image optimization)
- [ ] Write tests for critical flows
- [ ] Add error boundaries and fallbacks
- [ ] Review responsive behavior on different screen sizes

### 6. Documentation and deployment
- [ ] Write comprehensive README
- [ ] Document environment variables
- [ ] Add deployment configuration for target platform
- [ ] Create development and build scripts

## Verification

Run the following commands (adjust based on package manager and setup):

```bash
# Install dependencies
npm install

# Type checking
npm run type-check   # or tsc --noEmit

# Linting
npm run lint

# Tests
npm test

# Build verification
npm run build

# Run locally
npm run dev
```

The skill is complete when:

- All commands run successfully without errors.
- The application builds and runs in development mode.
- Core features work as specified across different screen sizes.
- Accessibility checks pass (use browser dev tools or axe extension).
- Tests cover critical user paths.
- Documentation is clear and complete.

## Safety and escalation

- **External dependencies**: Always verify package security and maintenance status before adding dependencies.
- **Environment secrets**: Never commit API keys, secrets, or credentials. Use `.env.local` and document in README.
- **Framework limitations**: If requirements exceed framework capabilities, suggest alternatives or clarify constraints.
- **Performance concerns**: If the app requires complex state or data handling, consider suggesting more robust solutions.

## Dynamic documentation references

Always search for and reference the most current documentation:

- **React**: https://react.dev
- **Next.js**: https://nextjs.org/docs
- **Vue**: https://vuejs.org/guide
- **Svelte**: https://svelte.dev/docs
- **Tailwind CSS**: https://tailwindcss.com/docs
- **TypeScript**: https://www.typescriptlang.org/docs
- **Vite**: https://vitejs.dev/guide

Before implementing any feature, search these docs to ensure you're using current APIs and best practices.

## Example workflows

### Vibing a landing page
```
User: "Let's vibe a landing page for a SaaS product - hero section, features, pricing, contact form"

Droid will:
1. Search for current Next.js initialization best practices
2. Initialize Next.js project with TypeScript and Tailwind
3. Create component structure (Hero, Features, Pricing, Contact)
4. Implement responsive design with proper accessibility
5. Add form validation and error handling
6. Set up basic SEO with metadata
7. Provide deployment instructions for Vercel/Netlify
```

### Quick dashboard prototype
```
User: "I want to quickly prototype an admin dashboard - auth, data tables, charts"

Droid will:
1. Research current patterns for Next.js App Router with authentication
2. Initialize project with appropriate dependencies
3. Set up authentication flow (NextAuth.js or similar)
4. Create protected route structure
5. Implement data fetching with loading states
6. Add table and chart components with proper typing
7. Include tests for auth and data flows
8. Document setup including database requirements
```

## SEO and web vitals

For public-facing applications, automatically implement:

- **Meta tags**: Title, description, Open Graph, Twitter cards
- **Structured data**: JSON-LD for rich search results
- **Performance**: Image optimization, code splitting, lazy loading
- **Core Web Vitals**: Optimize LCP, FID, CLS metrics
- **Sitemap**: Generate sitemap.xml for better indexing
- **Robots.txt**: Configure crawler behavior

## Integration with other skills

This skill can be combined with:

- **Service integration**: When the web app needs to call existing backend services.
- **Internal tools**: When building internal admin panels or dashboards.
- **Data querying**: When the app needs to display analytics or reports.
````


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# AI data analyst skill

> A reusable skill for performing comprehensive data analysis, visualization, and statistical modeling using code-interpreter style workflows.

This skill enables Droids to act as an AI-powered data analyst, performing exploratory data analysis, statistical modeling, data visualization, and generating insights from structured and unstructured data. Unlike point-solution data analysis tools, this skill runs entirely in your local environment with full Python ecosystem access and customization capabilities.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/ai-data-analyst/
├── SKILL.md
├── visualization-templates.md (optional)
├── statistical-methods.md (optional)
└── example-analyses.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/ai-data-analyst
   ```

2. **Copy the skill content below into `.factory/skills/ai-data-analyst/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to perform data analysis, create visualizations, or build statistical models, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/ai-data-analyst/SKILL.md`:

````md  theme={null}
---
name: ai-data-analyst
description: Perform comprehensive data analysis, statistical modeling, and data visualization by writing and executing self-contained Python scripts. Use when you need to analyze datasets, perform statistical tests, create visualizations, or build predictive models with reproducible, code-based workflows.
---
# Skill: AI data analyst

## Purpose

Perform comprehensive data analysis, statistical modeling, and data visualization by writing and executing self-contained Python scripts. Generate publication-quality charts, statistical reports, and actionable insights from data files or databases.

## When to use this skill

- You need to **analyze datasets** to understand patterns, trends, or relationships.
- You want to perform **statistical tests** or build predictive models.
- You need **data visualizations** (charts, graphs, dashboards) to communicate findings.
- You're doing **exploratory data analysis** (EDA) to understand data structure and quality.
- You need to **clean, transform, or merge** datasets for analysis.
- You want **reproducible analysis** with documented methodology and code.

## Key capabilities

Unlike point-solution data analysis tools:

- **Full Python ecosystem**: Access to pandas, numpy, scikit-learn, statsmodels, matplotlib, seaborn, plotly, and more.
- **Runs locally**: Your data stays on your machine; no uploads to third-party services.
- **Reproducible**: All analysis is code-based and version controllable.
- **Customizable**: Extend with any Python library or custom analysis logic.
- **Publication-quality output**: Generate professional charts and reports.
- **Statistical rigor**: Access to comprehensive statistical and ML libraries.

## Inputs

- **Data sources**: CSV files, Excel files, JSON, Parquet, or database connections.
- **Analysis goals**: Questions to answer or hypotheses to test.
- **Variables of interest**: Specific columns, metrics, or dimensions to focus on.
- **Output preferences**: Chart types, report format, statistical tests needed.
- **Context**: Business domain, data dictionary, or known data quality issues.

## Out of scope

- Real-time streaming data analysis (use appropriate streaming tools).
- Extremely large datasets requiring distributed computing (use Spark/Dask instead).
- Production ML model deployment (use ML ops tools and infrastructure).
- Live dashboarding (use BI tools like Tableau/Looker for operational dashboards).

## Conventions and best practices

### Python environment
- Use **virtual environments** to isolate dependencies.
- Install only necessary packages for the specific analysis.
- Document all dependencies in `requirements.txt` or `environment.yml`.

### Code structure
- Write **self-contained scripts** that can be re-run by others.
- Use **clear variable names** and add comments for complex logic.
- **Separate concerns**: data loading, cleaning, analysis, visualization.
- Save **intermediate results** to files when analysis is multi-stage.

### Data handling
- **Never modify source data files** – work on copies or in-memory dataframes.
- **Document data transformations** clearly in code comments.
- **Handle missing values** explicitly and document approach.
- **Validate data quality** before analysis (check for nulls, outliers, duplicates).

### Visualization best practices
- Choose **appropriate chart types** for the data and question.
- Use **clear labels, titles, and legends** on all charts.
- Apply **appropriate color schemes** (colorblind-friendly when possible).
- Include **sample sizes and confidence intervals** where relevant.
- Save visualizations in **high-resolution formats** (PNG 300 DPI, SVG for vector graphics).

### Statistical analysis
- **State assumptions** for statistical tests clearly.
- **Check assumptions** before applying tests (normality, homoscedasticity, etc.).
- **Report effect sizes** not just p-values.
- **Use appropriate corrections** for multiple comparisons.
- **Explain practical significance** in addition to statistical significance.

## Required behavior

1. **Understand the question**: Clarify what insights or decisions the analysis should support.
2. **Explore the data**: Check structure, types, missing values, distributions, outliers.
3. **Clean and prepare**: Handle missing data, outliers, and transformations appropriately.
4. **Analyze systematically**: Apply appropriate statistical methods or ML techniques.
5. **Visualize effectively**: Create clear, informative charts that answer the question.
6. **Generate insights**: Translate statistical findings into actionable business insights.
7. **Document thoroughly**: Explain methodology, assumptions, limitations, and conclusions.
8. **Make reproducible**: Ensure others can re-run the analysis and get the same results.

## Required artifacts

- **Analysis script(s)**: Well-documented Python code performing the analysis.
- **Visualizations**: Charts saved as high-quality image files (PNG/SVG).
- **Analysis report**: Markdown or text document summarizing:
  - Research question and methodology
  - Data description and quality assessment
  - Key findings with supporting statistics
  - Visualizations with interpretations
  - Limitations and caveats
  - Recommendations or next steps
- **Requirements file**: `requirements.txt` with all dependencies.
- **Sample data** (if appropriate and non-sensitive): Small sample for reproducibility.

## Implementation checklist

### 1. Data exploration and preparation
- [ ] Load data and inspect structure (shape, columns, types)
- [ ] Check for missing values, duplicates, outliers
- [ ] Generate summary statistics (mean, median, std, min, max)
- [ ] Visualize distributions of key variables
- [ ] Document data quality issues found

### 2. Data cleaning and transformation
- [ ] Handle missing values (impute, drop, or flag)
- [ ] Address outliers if needed (cap, transform, or document)
- [ ] Create derived variables if needed
- [ ] Normalize or scale variables for modeling
- [ ] Split data if doing train/test analysis

### 3. Analysis execution
- [ ] Choose appropriate analytical methods
- [ ] Check statistical assumptions
- [ ] Execute analysis with proper parameters
- [ ] Calculate confidence intervals and effect sizes
- [ ] Perform sensitivity analyses if appropriate

### 4. Visualization
- [ ] Create exploratory visualizations
- [ ] Generate publication-quality final charts
- [ ] Ensure all charts have clear labels and titles
- [ ] Use appropriate color schemes and styling
- [ ] Save in high-resolution formats

### 5. Reporting
- [ ] Write clear summary of methods used
- [ ] Present key findings with supporting evidence
- [ ] Explain practical significance of results
- [ ] Document limitations and assumptions
- [ ] Provide actionable recommendations

### 6. Reproducibility
- [ ] Test that script runs from clean environment
- [ ] Document all dependencies
- [ ] Add comments explaining non-obvious code
- [ ] Include instructions for running analysis

## Verification

Run the following to verify the analysis:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run analysis script
python analysis.py

# Check outputs generated
ls -lh outputs/
```

The skill is complete when:

- Analysis script runs without errors from clean environment.
- All required visualizations are generated in high quality.
- Report clearly explains methodology, findings, and limitations.
- Results are interpretable and actionable.
- Code is well-documented and reproducible.

## Common analysis patterns

### Exploratory Data Analysis (EDA)
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load and inspect data
df = pd.read_csv('data.csv')
print(df.info())
print(df.describe())

# Check for missing values
print(df.isnull().sum())

# Visualize distributions
df.hist(figsize=(12, 10), bins=30)
plt.tight_layout()
plt.savefig('distributions.png', dpi=300)

# Check correlations
corr = df.corr()
sns.heatmap(corr, annot=True, cmap='coolwarm')
plt.savefig('correlations.png', dpi=300)
```

### Time series analysis
```python
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import seasonal_decompose

# Load time series data
df = pd.read_csv('timeseries.csv', parse_dates=['date'])
df.set_index('date', inplace=True)

# Decompose time series
decomposition = seasonal_decompose(df['value'], model='additive', period=30)
fig = decomposition.plot()
fig.set_size_inches(12, 8)
plt.savefig('decomposition.png', dpi=300)

# Calculate rolling statistics
df['rolling_mean'] = df['value'].rolling(window=7).mean()
df['rolling_std'] = df['value'].rolling(window=7).std()

# Plot with trends
plt.figure(figsize=(12, 6))
plt.plot(df['value'], label='Original')
plt.plot(df['rolling_mean'], label='7-day Moving Avg', linewidth=2)
plt.fill_between(df.index,
                 df['rolling_mean'] - df['rolling_std'],
                 df['rolling_mean'] + df['rolling_std'],
                 alpha=0.3)
plt.legend()
plt.savefig('trends.png', dpi=300)
```

### Statistical hypothesis testing
```python
from scipy import stats
import numpy as np

# Compare two groups
group_a = df[df['group'] == 'A']['metric']
group_b = df[df['group'] == 'B']['metric']

# Check normality
_, p_norm_a = stats.shapiro(group_a)
_, p_norm_b = stats.shapiro(group_b)

# Choose appropriate test
if p_norm_a > 0.05 and p_norm_b > 0.05:
    # Parametric test (t-test)
    statistic, p_value = stats.ttest_ind(group_a, group_b)
    test_used = "Independent t-test"
else:
    # Non-parametric test (Mann-Whitney U)
    statistic, p_value = stats.mannwhitneyu(group_a, group_b)
    test_used = "Mann-Whitney U test"

# Calculate effect size (Cohen's d)
pooled_std = np.sqrt((group_a.std()**2 + group_b.std()**2) / 2)
cohens_d = (group_a.mean() - group_b.mean()) / pooled_std

print(f"Test used: {test_used}")
print(f"Test statistic: {statistic:.4f}")
print(f"P-value: {p_value:.4f}")
print(f"Effect size (Cohen's d): {cohens_d:.4f}")
```

### Predictive modeling
```python
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import matplotlib.pyplot as plt

# Prepare data
X = df.drop('target', axis=1)
y = df['target']

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print(f"RMSE: {rmse:.4f}")
print(f"R² Score: {r2:.4f}")

# Feature importance
importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

plt.figure(figsize=(10, 6))
plt.barh(importance['feature'][:10], importance['importance'][:10])
plt.xlabel('Feature Importance')
plt.title('Top 10 Most Important Features')
plt.tight_layout()
plt.savefig('feature_importance.png', dpi=300)
```

## Recommended Python libraries

### Data manipulation
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- **polars**: High-performance DataFrame library (alternative to pandas)

### Visualization
- **matplotlib**: Foundational plotting library
- **seaborn**: Statistical visualizations
- **plotly**: Interactive charts
- **altair**: Declarative statistical visualization

### Statistical analysis
- **scipy.stats**: Statistical functions and tests
- **statsmodels**: Statistical modeling
- **pingouin**: Statistical tests with clear output

### Machine learning
- **scikit-learn**: ML algorithms and tools
- **xgboost**: Gradient boosting
- **lightgbm**: Fast gradient boosting

### Time series
- **statsmodels.tsa**: Time series analysis
- **prophet**: Forecasting tool
- **pmdarima**: Auto ARIMA

### Specialized
- **networkx**: Network analysis
- **geopandas**: Geospatial data analysis
- **textblob** / **spacy**: Natural language processing

## Safety and escalation

- **Data privacy**: Never analyze or share data containing PII without proper authorization.
- **Statistical validity**: If sample sizes are too small for reliable inference, call this out explicitly.
- **Causal claims**: Avoid implying causation from correlational analysis; be explicit about limitations.
- **Model limitations**: Document when models may not generalize or when predictions should not be trusted.
- **Data quality**: If data quality issues could materially affect conclusions, flag this prominently.

## Integration with other skills

This skill can be combined with:

- **Internal data querying**: To fetch data from warehouses or databases for analysis.
- **Web app builder**: To create interactive dashboards displaying analysis results.
- **Internal tools**: To build analysis tools for non-technical stakeholders.
````


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Product management AI skill

> A reusable skill for assisting with product management workflows including PRDs, feature analysis, roadmap planning, and user research synthesis.

This skill enables Droids to act as a product management assistant, helping with the documentation, analysis, and planning activities that are core to the PM role. Unlike point-solution PM tools, this skill integrates directly with your development workflow, codebase, and documentation.

## Setup Instructions

To use this skill with Factory, create the following directory structure in your repository:

```
.factory/skills/product-management/
├── SKILL.md
├── prd-template.md (optional)
├── feature-analysis-framework.md (optional)
└── user-research-templates.md (optional)
```

### Quick Start

1. **Create the skill directory:**
   ```bash  theme={null}
   mkdir -p .factory/skills/product-management
   ```

2. **Copy the skill content below into `.factory/skills/product-management/SKILL.md` (or `skill.mdx`)**

<Tip>
  When you ask Factory to help with PRDs, feature analysis, roadmap planning, or research synthesis, it will automatically invoke this skill based on the task description.
</Tip>

## Skill Definition

Copy the following content into `.factory/skills/product-management/SKILL.md`:

````md  theme={null}
---
name: product-management
description: Assist with core product management activities including writing PRDs, analyzing features, synthesizing user research, planning roadmaps, and communicating product decisions. Use when you need help with PM documentation, analysis, or planning workflows that integrate with your codebase.
---
# Skill: Product management AI

## Purpose

Assist with core product management activities including writing product requirements documents (PRDs), analyzing feature requests, synthesizing user research, planning roadmaps, and communicating product decisions to stakeholders and engineering teams.

## When to use this skill

- You need to **write or update PRDs** with clear requirements, success metrics, and technical considerations.
- You're **evaluating feature requests** and need structured analysis of impact, effort, and priority.
- You need to **synthesize user research** findings into actionable insights.
- You're **planning roadmaps** and need to organize, prioritize, and communicate plans.
- You need to **communicate product decisions** clearly to engineering, design, and business stakeholders.
- You're doing **competitive analysis** or market research synthesis.
- You need to **track and analyze product metrics** to inform decisions.

## Key capabilities

Unlike point-solution PM tools:

- **Integrated with codebase**: Can reference actual code, APIs, and technical constraints.
- **Context-aware**: Understands your specific product, architecture, and technical debt.
- **Flexible templates**: Adapt documentation to your organization's needs.
- **Version controlled**: All artifacts live in git alongside code.
- **Collaborative**: Works within existing dev workflows (PRs, issues, docs).

## Inputs

- **Product context**: Current state, key stakeholders, strategic goals.
- **Feature requests**: User feedback, business needs, or strategic initiatives.
- **Technical constraints**: Known limitations, dependencies, or technical debt.
- **User research**: Interview notes, survey results, analytics data.
- **Business goals**: Metrics, OKRs, or success criteria to optimize for.

## Out of scope

- Making final product decisions (this is the PM's job; the skill assists).
- Managing stakeholder relationships and politics.
- Detailed UI/UX design work (use design tools and collaborate with designers).
- Project management and sprint planning (use project management tools).

## Conventions and best practices

### PRD structure
A good PRD should include:

1. **Problem statement**: What user pain point or business need are we addressing?
2. **Goals and success metrics**: What does success look like quantitatively?
3. **User stories and use cases**: Who will use this and how?
4. **Requirements**: Functional and non-functional requirements, prioritized.
5. **Technical considerations**: Architecture implications, dependencies, constraints.
6. **Design and UX notes**: Key interaction patterns or design requirements.
7. **Risks and mitigations**: What could go wrong and how to address it.
8. **Launch plan**: Rollout strategy, feature flags, monitoring.
9. **Open questions**: What still needs to be decided or researched.

### Feature prioritization
Use structured frameworks to evaluate features:

- **RICE**: Reach × Impact × Confidence / Effort
- **ICE**: Impact × Confidence × Ease
- **Value vs. Effort**: 2×2 matrix plotting value against implementation cost
- **Kano Model**: Categorize features into basic, performance, and delighters

### User research synthesis
When synthesizing research:

1. **Identify patterns**: What themes emerge across participants?
2. **Quote verbatim**: Include actual user quotes to illustrate points.
3. **Quantify when possible**: "7 out of 10 participants said..."
4. **Segment findings**: Different user types may have different needs.
5. **Connect to metrics**: How do qualitative findings explain quantitative data?

### Roadmap planning
Effective roadmaps should:

- **Theme-based**: Group work into strategic themes, not just feature lists.
- **Time-horizoned**: Now / Next / Later or Quarterly structure.
- **Outcome-focused**: Emphasize goals and outcomes, not just outputs.
- **Flexible**: Leave room for learning and adjustment.
- **Communicated clearly**: Different views for different audiences.

## Required behavior

1. **Understand context deeply**: Review existing docs, code, and prior discussions before proposing changes.
2. **Ask clarifying questions**: Don't assume; clarify ambiguous requirements or goals.
3. **Be specific and actionable**: Avoid vague language; provide concrete, testable requirements.
4. **Consider tradeoffs**: Explicitly discuss pros/cons of different approaches.
5. **Connect to strategy**: Tie features and decisions back to higher-level goals.
6. **Involve stakeholders**: Identify who needs to review or approve.
7. **Think through edge cases**: Don't just focus on happy paths.
8. **Make it measurable**: Propose concrete metrics to track success.

## Required artifacts

Depending on the task, generate:

- **PRD document**: Comprehensive product requirements in markdown format.
- **Feature analysis**: Structured evaluation of a feature request.
- **Research synthesis**: Summary of user research findings with insights.
- **Roadmap document**: Organized view of planned work with themes and timelines.
- **Decision document**: Record of key product decisions and rationale.
- **Competitive analysis**: Comparison of competitor features and approaches.
- **Metric definitions**: Clear definitions of success metrics and how to measure them.

## Implementation checklist

### Writing a PRD
- [ ] Understand the problem space and strategic context
- [ ] Review related code, APIs, and technical constraints
- [ ] Interview key stakeholders (engineering, design, business)
- [ ] Research user needs and competitive landscape
- [ ] Draft problem statement and goals
- [ ] Define user stories and use cases
- [ ] Specify functional and non-functional requirements
- [ ] Document technical considerations and dependencies
- [ ] Define success metrics and measurement approach
- [ ] Identify risks and mitigation strategies
- [ ] Plan rollout and launch approach
- [ ] Review with stakeholders and iterate

### Analyzing a feature request
- [ ] Clarify the user problem or business need
- [ ] Identify target users and use cases
- [ ] Estimate impact (users affected, business value)
- [ ] Assess implementation effort and complexity
- [ ] Identify dependencies and risks
- [ ] Check alignment with product strategy
- [ ] Compare against alternatives
- [ ] Calculate prioritization score (RICE, ICE, etc.)
- [ ] Make recommendation with clear reasoning

### Synthesizing user research
- [ ] Review all research materials (transcripts, notes, data)
- [ ] Identify key themes and patterns
- [ ] Extract representative quotes
- [ ] Segment findings by user type if relevant
- [ ] Connect qualitative findings to quantitative data
- [ ] Formulate insights and implications
- [ ] Generate actionable recommendations
- [ ] Prioritize recommendations by impact

### Planning a roadmap
- [ ] Review strategic goals and OKRs
- [ ] Collect input from stakeholders
- [ ] Assess current state and technical debt
- [ ] Group potential work into strategic themes
- [ ] Prioritize themes and initiatives
- [ ] Estimate sizing and dependencies
- [ ] Organize into time horizons (Now/Next/Later)
- [ ] Define success criteria for each initiative
- [ ] Create views for different audiences
- [ ] Review and socialize with stakeholders

## Example workflows

### Example 1: Writing a PRD for a new feature

```markdown
# PRD: Advanced Search Functionality

## Problem Statement
Users frequently report difficulty finding specific items in our catalog when they have multiple criteria (price range, location, category, features). Our current search only supports simple text queries, leading to:
- High bounce rates on search results pages (65% bounce rate vs 32% site average)
- Increased support tickets asking for search help (150/month)
- Lost conversion opportunities (estimated $500K annual revenue impact)

## Goals and Success Metrics
**Primary Goal**: Enable users to find relevant items quickly using multiple filters.

**Success Metrics**:
- Reduce search result page bounce rate from 65% to <40%
- Increase search-to-purchase conversion rate by 25%
- Reduce search-related support tickets by 50%
- 70% of users engage with at least one filter within 30 days

## User Stories

### Must Have
1. As a buyer, I want to filter by price range so I can find items within my budget
2. As a buyer, I want to filter by location so I can find items near me
3. As a buyer, I want to filter by category so I can narrow down item types
4. As a buyer, I want to combine multiple filters so I can find exactly what I need
5. As a buyer, I want to see filter counts so I know how many items match before applying

### Should Have
6. As a buyer, I want to save my filter preferences so I don't have to reapply them
7. As a buyer, I want to see suggested filters based on my search query
8. As a buyer, I want to sort filtered results by relevance, price, or date

### Nice to Have
9. As a buyer, I want to create saved searches that notify me of new matches
10. As a buyer, I want to share a filtered search URL with others

## Requirements

### Functional Requirements

**Filter Types** (Priority: Must Have)
- Price range filter: min/max inputs + common presets ($0-50, $50-100, etc.)
- Location filter: radius selector + zip code input
- Category filter: hierarchical category tree with multi-select
- Custom attribute filters: based on item type (size, color, condition, etc.)

**Filter Behavior** (Priority: Must Have)
- Filters apply instantly (no "Apply" button) or with <500ms latency
- URL updates to reflect active filters (shareable links)
- Clear all filters button visible when any filter is active
- Filter state persists within session
- Mobile-friendly filter UI (drawer or modal on mobile)

**Search Integration** (Priority: Must Have)
- Filters work alongside text search query
- Filter facet counts update based on text query
- Auto-suggest filters based on search terms (e.g., "red" → suggest color filter)

### Non-Functional Requirements

**Performance** (Priority: Must Have)
- Initial page load <2s at p95
- Filter application response <500ms at p95
- Support 10,000+ concurrent users without degradation
- Efficient indexing for 1M+ items

**Scalability** (Priority: Should Have)
- Filter definitions configurable without code changes
- Support for 50+ filter types
- Easily add new filter types for new categories

**Accessibility** (Priority: Must Have)
- Keyboard navigation for all filters
- Screen reader support with proper ARIA labels
- High contrast mode support
- Touch target sizes ≥44×44px on mobile

## Technical Considerations

### Architecture
- **Search Backend**: Extend existing Elasticsearch cluster with filter aggregations
- **API Changes**: New `/search` endpoint query params for filters; return filter facets in response
- **Frontend**: React components with URL state management (React Router)
- **Caching**: Cache filter definitions and facet counts (Redis, 5-minute TTL)

### Dependencies
- Elasticsearch 8.x upgrade (currently on 7.x) to support efficient aggregations
- Update item schema to include filter-specific fields
- Backend API versioning to support gradual rollout

### Data Model
```typescript
interface SearchFilters {
  price?: { min: number; max: number };
  location?: { lat: number; lng: number; radius: number };
  categories?: string[]; // Category IDs
  attributes?: Record<string, string[]>; // Dynamic attributes
}

interface SearchResponse {
  items: Item[];
  facets: {
    [filterName: string]: {
      values: Array<{ value: string; count: number }>;
    };
  };
  total: number;
}
```

### Technical Risks
1. **Elasticsearch performance**: Complex aggregations may impact search latency
   - *Mitigation*: Load test with production data; add caching; consider pre-aggregation
2. **Index size growth**: More fields = larger indices and slower indexing
   - *Mitigation*: Monitor index size; potentially separate indices for different item types
3. **Schema evolution**: Adding new filters requires index updates
   - *Mitigation*: Design flexible schema; plan for gradual rollout

## Design and UX Notes

### Desktop Layout
- Filters in left sidebar (persistent, not collapsible)
- Main results area with sort controls at top
- Filter chips above results showing active filters

### Mobile Layout
- "Filters" button in header opens bottom sheet
- Show active filter count badge on button
- Apply button in bottom sheet (don't auto-apply on mobile to reduce requests)

### Filter UI Patterns
- Price: Dual slider + text inputs
- Location: Autocomplete location search + radius selector
- Category: Expandable tree with checkboxes
- Attributes: Checkbox groups, collapsible sections

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Performance degradation with complex filters | Medium | High | Load testing; caching; gradual rollout with feature flag |
| Low filter adoption by users | Medium | High | User testing; prominent UI; tutorial on first visit |
| Elasticsearch upgrade issues | Low | High | Test in staging; plan rollback; off-peak deployment |
| Filter options become overwhelming | Medium | Medium | User research to prioritize filters; consider "More filters" progressive disclosure |

## Launch Plan

### Phase 1: MVP (Week 1-2)
- Price, location, and category filters only
- Desktop web only
- 5% rollout to test performance

### Phase 2: Expansion (Week 3-4)
- Add custom attribute filters
- Mobile responsive design
- Expand to 25% of users

### Phase 3: Full Launch (Week 5-6)
- Saved search preferences (logged-in users)
- 100% rollout
- Monitor metrics and iterate

### Feature Flags
- `advanced_search_enabled`: Master flag for entire feature
- `advanced_search_filters`: Individual filter types can be enabled/disabled
- `advanced_search_saved_prefs`: Saved preferences feature

### Monitoring
- Dashboards tracking success metrics (bounce rate, conversion, engagement)
- Error rates and latency for search API
- Filter usage analytics (which filters used most, combinations)
- Alerts for search latency >1s or error rate >1%

## Open Questions

1. **Filter Defaults**: Should any filters be pre-applied based on user history or location? (Owner: PM, Due: Week 1)
2. **Personalization**: How should we handle conflicting saved preferences vs. shared filter URLs? (Owner: Eng, Due: Week 2)
3. **Mobile UX**: Should mobile use instant apply or require an "Apply" button? (Owner: Design, Due: Week 1)
4. **Analytics**: What specific filter interactions should we track? (Owner: Data, Due: Week 2)

## Stakeholders and Reviewers

- **PM Owner**: Jane Doe
- **Engineering Lead**: John Smith
- **Design**: Alice Johnson
- **Data Science**: Bob Lee (metrics and instrumentation)
- **Approvals Needed**: VP Product, VP Engineering

---
*Last Updated*: 2025-11-19
*Status*: Draft → Review → Approved → In Progress
```

### Example 2: Feature request analysis

```markdown
# Feature Analysis: Dark Mode Support

## Request Summary
**Source**: User feedback (150+ requests in past 6 months), competitive pressure
**Description**: Add dark mode theme option to web and mobile apps

## User Need
Users working in low-light environments report eye strain with current light-only theme. Power users (25% of DAU) spend 3+ hours/day in app and strongly prefer dark mode. Common feedback: "I use dark mode everywhere else, why not here?"

## Target Users
- Power users: 300K users, 3+ hrs/day usage
- Evening/night users: 450K users who primarily use app 6pm-12am
- Accessibility users: Users with light sensitivity or visual impairments

## Impact Assessment

### User Impact
- **Reach**: ~750K users (45% of user base) have requested or would use dark mode
- **Impact Score**: 8/10 - High impact for target users; neutral for others
- **Confidence**: 85% - Strong signal from user research and competitive data

### Business Impact
- **Retention**: Likely improves retention for power users (high-value segment)
- **Acquisition**: Table stakes for competitive positioning
- **Revenue**: Indirect impact through retention and satisfaction
- **Estimated Value**: +2% overall retention = ~$800K annual revenue

## Effort Assessment

### Engineering Effort
- **Frontend**: 3 weeks (2 engineers)
  - Design system updates (color tokens, theme provider)
  - Component updates (~150 components)
  - Testing across browsers and devices
- **Backend**: 1 week (1 engineer)
  - User preference storage and API
  - Default theme logic
- **Total Effort**: ~7 engineer-weeks

### Design Effort
- 2 weeks to design and validate dark theme
- Audit all screens and components
- Accessibility testing for contrast ratios

### Dependencies
- Requires design system update first (already planned Q2)
- Mobile apps need React Native theme provider update
- Email templates will remain light mode (out of scope for now)

## Alternatives Considered

### Option 1: Full Dark Mode (Recommended)
- **Pros**: Meets user needs; industry standard; future-proof
- **Cons**: More implementation work upfront
- **Effort**: 7 engineer-weeks

### Option 2: Auto Dark Mode Only (follow system preference)
- **Pros**: Simpler (no user preference storage); still helps users
- **Cons**: Doesn't give user control; may not match user preference
- **Effort**: 5 engineer-weeks

### Option 3: Premium Feature (dark mode for paid users)
- **Pros**: Potential revenue from feature upgrades
- **Cons**: User backlash (expected table stakes); limits adoption
- **Effort**: 7 engineer-weeks + paywall logic

## Prioritization Score

Using RICE framework:
- **Reach**: 750K users = 750
- **Impact**: 8/10 (high for target segment) = 0.8
- **Confidence**: 85% = 0.85
- **Effort**: 7 weeks = 7

**RICE Score**: (750 × 0.8 × 0.85) / 7 = **73.2**

For comparison:
- Recent feature A: RICE = 45
- Recent feature B: RICE = 92
- Average feature RICE: 55

## Risks

1. **Scope Creep**: Easy to bikeshed colors; need clear design authority
   - *Mitigation*: Lock designs early; time-box feedback cycles
2. **Accessibility**: Poor contrast choices could harm accessibility
   - *Mitigation*: WCAG AA testing; accessibility audit before launch
3. **Maintenance Burden**: Need to test everything in both modes going forward
   - *Mitigation*: Automated visual regression testing; CI checks
4. **Incomplete Coverage**: Users notice when parts don't respect theme
   - *Mitigation*: Comprehensive component audit; phased rollout

## Strategic Alignment

**Product Strategy**: ✅ Aligned - Improves core user experience for power users (strategic segment)
**Technical Strategy**: ✅ Aligned - Modernizes design system and component architecture
**Business Goals**: ✅ Aligned - Supports retention goals and competitive positioning

## Recommendation

**✅ Proceed with Option 1 (Full Dark Mode)**

**Reasoning**:
- High impact for large user segment (45% of base)
- Strong user demand and competitive pressure
- Effort is reasonable relative to value
- RICE score above our threshold (>50)
- Aligns with product, technical, and business strategy

**Suggested Timeline**:
- Q2 2025: Design and design system updates
- Q3 2025: Implementation and testing
- Q4 2025: Launch with marketing push

**Next Steps**:
1. Get stakeholder approval
2. Add to Q2 roadmap
3. Kick off design work
4. Plan engineering sprint allocation

---
*Analysis by*: Jane Doe (PM)
*Reviewed by*: Design, Engineering, Data
*Date*: 2025-11-19
```

## Common PM artifacts

### PRD (Product Requirements Document)
Comprehensive specification of what to build and why. Include problem statement, goals, user stories, requirements, technical considerations, risks, and launch plan.

### Feature Brief
Lighter-weight than PRD; quick summary of a feature idea with key details. Use for early-stage exploration before committing to full PRD.

### User Research Synthesis
Summary of user research findings (interviews, surveys, usability tests) with patterns, insights, and recommendations.

### Roadmap
Strategic plan of what to build over time. Organize by themes and time horizons; focus on outcomes not just outputs.

### Decision Document
Record of important product decisions, the options considered, the decision made, and the reasoning. Critical for institutional memory.

### Launch Plan
Detailed plan for rolling out a feature including phases, feature flags, metrics, monitoring, and rollback procedures.

### Competitive Analysis
Comparison of competitors' features, approaches, and positioning. Inform product strategy and feature prioritization.

### One-Pager
Executive summary of a product initiative. Use to communicate to leadership and get alignment.

## Best practices for AI-assisted PM work

### When using AI to write PRDs
- Provide comprehensive context about the product, users, and technical constraints.
- Review and edit generated content carefully; AI may miss nuances or make wrong assumptions.
- Use AI for structure and first drafts; refine with human judgment and stakeholder input.
- Validate technical details with engineering; don't assume AI knows your architecture.

### When using AI for feature analysis
- Provide quantitative data when possible (usage numbers, customer feedback counts).
- Use structured frameworks (RICE, ICE) to make analysis consistent and defensible.
- Don't let AI make the final decision; use it to organize thinking and surface considerations.
- Supplement AI analysis with qualitative stakeholder input and strategic context.

### When using AI for research synthesis
- Provide full transcripts or detailed notes for best results.
- Ask AI to identify patterns but validate with your own reading of the data.
- Use AI to extract quotes and organize themes; add your own interpretation and implications.
- Don't let AI over-summarize; sometimes important details are in the nuances.

## Safety and escalation

- **Strategic decisions**: AI should inform, not make, key product decisions. Involve human PMs and stakeholders.
- **User data**: Don't feed PII or sensitive user data to AI without proper data handling procedures.
- **Technical feasibility**: Always validate technical assumptions and effort estimates with engineering.
- **Competitive intelligence**: Be cautious about including confidential competitive info in prompts.
- **Tone and voice**: Review and adjust tone for your audience; AI may be too formal or informal.

## Integration with other skills

This skill can be combined with:

- **Data querying**: To analyze product metrics and user behavior data.
- **AI data analyst**: To perform deeper quantitative analysis for feature decisions.
- **Frontend UI integration**: To implement features designed in PRDs.
- **Internal tools**: To build PM tools like feature flag dashboards or metrics viewers.
````


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# Browser automation skill

> Minimal Chrome DevTools Protocol helpers that let Droids start Chrome, navigate tabs, evaluate JavaScript, take screenshots, and capture DOM metadata without building a full MCP server.

<Note>
  This cookbook is inspired by [Mario Zechner's “What if you don't need
  MCP?”](https://mariozechner.at/posts/2025-11-02-what-if-you-dont-need-mcp/),
  adapted into a reusable Factory skill so teams can share lightweight browser
  helpers without standing up new services.
</Note>

The browser skill bundles a handful of executable scripts (`start.js`, `nav.js`, `eval.js`, `screenshot.js`, `pick.js`) plus a concise `SKILL.md`. Together they give Factory Droids a reliable way to spin up Chrome on port `9222`, drive an existing tab, scrape structured data, and capture visual evidence while staying entirely on the developer machine.

## When to use this skill

* You need **real-browser context** (authenticated sessions, production-only behavior, visual regressions) to complete a task.
* You want to **inspect or extract DOM state** without building a dedicated MCP server.
* You must **capture screenshots or DOM element metadata** as part of QA notes, bug triage, or documentation.
* You prefer a **portable, git-tracked bundle** that any teammate can run locally with zero additional infrastructure.

## What the scripts provide

| Script          | Purpose                                                                                       | Typical usage                                                 |
| --------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `start.js`      | Launches Chrome with remote debugging on `:9222`, with optional profile sync via `--profile`. | `~/.factory/skills/browser/start.js --profile`                |
| `nav.js`        | Navigates the active tab or opens a new tab when `--new` is passed.                           | `~/.factory/skills/browser/nav.js https://example.com --new`  |
| `eval.js`       | Runs arbitrary JavaScript (async supported) in the focused tab and prints structured results. | `~/.factory/skills/browser/eval.js "document.title"`          |
| `screenshot.js` | Captures the current viewport to a timestamped PNG stored under `$TMPDIR`.                    | `~/.factory/skills/browser/screenshot.js`                     |
| `pick.js`       | Injects a visual picker so you can click DOM nodes and return tag/id/class/text metadata.     | `~/.factory/skills/browser/pick.js "Click the submit button"` |

All scripts rely on `puppeteer-core` and connect to a Chrome instance that you control. Because everything runs locally, existing cookies and auth tokens never leave your machine.

## Setup

<Steps>
  <Step title="Create the skill folder">
    Run `mkdir -p .factory/skills/browser`.
  </Step>

  <Step title="Copy scripts and package metadata">
    Copy `start.js`, `nav.js`, `eval.js`, `screenshot.js`, `pick.js`, and
    `package.json` into `.factory/skills/browser/` (or symlink to a shared
    dotfiles repo).
  </Step>

  <Step title="Install dependencies">
    Run `npm install --prefix .factory/skills/browser puppeteer-core`, then
    `chmod +x .factory/skills/browser/*.js`.
  </Step>

  <Step title="Restart Droid">
    Restart `droid` (or your IDE integration) so it rescans workspace skills and
    discovers `browser`.
  </Step>
</Steps>

## Skill definition

Copy the following into `.factory/skills/browser/SKILL.md`:

````md  theme={null}
---
name: browser
description: Minimal Chrome DevTools Protocol tools for browser automation and scraping. Use when you need to start Chrome, navigate pages, execute JavaScript, take screenshots, or interactively pick DOM elements.
---

# Browser Tools

Minimal CDP tools for collaborative site exploration and scraping.

**IMPORTANT**: All scripts are located in `~/.factory/skills/browser/` and must be called with full paths.

## Start Chrome

```bash
~/.factory/skills/browser/start.js              # Fresh profile
~/.factory/skills/browser/start.js --profile    # Copy your profile (cookies, logins)
```

Start Chrome on `:9222` with remote debugging.

## Navigate

```bash
~/.factory/skills/browser/nav.js https://example.com
~/.factory/skills/browser/nav.js https://example.com --new
```

Navigate current tab or open new tab.

## Evaluate JavaScript

```bash
~/.factory/skills/browser/eval.js 'document.title'
~/.factory/skills/browser/eval.js 'document.querySelectorAll("a").length'
```

Execute JavaScript in active tab (async context).

**IMPORTANT**: The code must be a single expression or use IIFE for multiple statements:

- Single expression: `'document.title'`
- Multiple statements: `'(() => { const x = 1; return x + 1; })()'`
- Avoid newlines in the code string - keep it on one line

## Screenshot

```bash
~/.factory/skills/browser/screenshot.js
```

Screenshot current viewport, returns temp file path.

## Pick Elements

```bash
~/.factory/skills/browser/pick.js "Click the submit button"
```

Interactive element picker. Click to select, Cmd/Ctrl+Click for multi-select, Enter to finish.

## Usage Notes

- Start Chrome first before using other tools
- The `--profile` flag syncs your actual Chrome profile so you're logged in everywhere
- JavaScript evaluation runs in an async context in the page
- Pick tool allows you to visually select DOM elements by clicking on them

```

## Workflow recipe

1. **Start Chrome** with `start.js --profile` to mirror your authenticated state.
2. **Drive navigation** via `nav.js https://target.app` or open secondary tabs with `--new`.
3. **Inspect the DOM** using `eval.js` for quick counts, attribute checks, or extracting JSON payloads.
4. **Capture artifacts** with `screenshot.js` for visual proof or `pick.js` when you need precise selectors or text snapshots.
5. **Return the gathered evidence** (file paths, DOM metadata, query outputs) in your session summary or PR description.

This workflow keeps the agent focused on the current browsing context and avoids shipping raw credentials or cookies outside your machine.

## Verification

- `~/.factory/skills/browser/start.js --profile` should print `✓ Chrome started on :9222 with your profile`.
- `~/.factory/skills/browser/nav.js https://example.com` should confirm navigation.
- `~/.factory/skills/browser/eval.js 'document.title'` should echo the current page title.
- `~/.factory/skills/browser/screenshot.js` should output a valid PNG path under your system temp directory.

If any step fails, rerun `start.js`, confirm Chrome is listening on `localhost:9222/json/version`, and ensure `puppeteer-core` is installed.
```
````


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt
