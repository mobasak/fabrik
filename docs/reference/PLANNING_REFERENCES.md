# Planning Phase References

**Last Updated:** 2026-01-08

> **AI agents MUST consult these files during planning phases (idea, scope, spec).**
> This index ensures consistent technology decisions across all Fabrik projects.

---

## Quick Reference Categories

| Category | When to Consult |
|----------|-----------------|
| **Technology Selection** | Choosing frameworks, languages, platforms |
| **Infrastructure** | Docker images, databases, deployment |
| **AI/ML Decisions** | Selecting AI tools, models, APIs |
| **Code Standards** | Before writing Python, TypeScript code |

---

## 1. Technology Selection

### `technology-stack-decision-guide.md`
**Purpose:** Decision flowchart for choosing the right tech stack.
**Consult when:** Starting any new product or feature requiring tech decisions.
```
Path: docs/reference/technology-stack-decision-guide.md
```

### `stack.md`
**Purpose:** Complete technology inventory - ALL tools, APIs, databases, and services used across Fabrik projects.
**Contains:** External APIs (AI, DNS, Calendar), database instances, infrastructure services, deployment patterns.
**Consult when:** Checking what tools/services already exist, understanding deployment patterns, avoiding duplicate integrations.
```
Path: docs/reference/stack.md
```

### `SaaS-GUI.md`
**Purpose:** SaaS application UI/UX patterns and component choices.
**Consult when:** Building web applications with user interfaces.
```
Path: docs/reference/SaaS-GUI.md
```

---

## 2. Infrastructure & Containers

### `prebuilt-app-containers.md`
**Purpose:** Catalog of prebuilt Docker containers for common services.
**Consult when:** Need a service (DB, cache, monitoring) - check here BEFORE building custom.
```
Path: docs/reference/prebuilt-app-containers.md
```

### `trueforge-images.md`
**Purpose:** Supply-chain secure container images from TrueForge.
**Consult when:** Security-critical deployments requiring verified images.
```
Path: docs/reference/trueforge-images.md
```

### `DATABASE_STRATEGY.md`
**Purpose:** Database selection (PostgreSQL, Supabase, pgvector) and migration policy.
**Consult when:** Any project needing data persistence.
```
Path: docs/reference/DATABASE_STRATEGY.md
```

### `plugin-stack.md`
**Purpose:** Curated WordPress plugin stack for Docker multi-site.
**Consult when:** WordPress projects.
```
Path: docs/reference/wordpress/plugin-stack.md
```

---

## 3. AI/ML Decisions

### `AI_TAXONOMY.md`
**Purpose:** 15-category AI taxonomy with tool recommendations.
**Consult when:** Selecting AI tools, APIs, or models for any feature.
```
Path: docs/reference/AI_TAXONOMY.md
```

**Key Categories:**
- Speech/Audio, Vision, Language, Multimodal
- Agentic, Code, Data/Predictive
- Robotics, Synthetic Data, Recommendation
- Cybersecurity, Bio/Healthcare, Edge/Embedded
- Governance/Trust, Generative Design

---

## 4. Code Standards

### `PYTHON_PRODUCTION_STANDARDS.md`
**Purpose:** Python coding best practices for production code.
**Consult when:** Writing or reviewing Python code.
```
Path: templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md
```

### `.windsurf/rules/10-python.md`
**Purpose:** FastAPI patterns, type hints, async patterns.
**Consult when:** Python projects (auto-loaded by Windsurf for *.py files).
```
Path: .windsurf/rules/10-python.md
```

### `.windsurf/rules/20-typescript.md`
**Purpose:** Next.js, React, TypeScript patterns.
**Consult when:** TypeScript projects (auto-loaded by Windsurf for *.ts/*.tsx files).
```
Path: .windsurf/rules/20-typescript.md
```

---

## AI Agent Instructions

### During `idea` Phase
1. Read `technology-stack-decision-guide.md` to understand product type options
2. Read `AI_TAXONOMY.md` if AI features are mentioned

### During `scope` Phase
1. Read `stack.md` to understand deployment constraints
2. Read `DATABASE_STRATEGY.md` if data persistence needed
3. Read `prebuilt-app-containers.md` to identify reusable components

### During `spec` Phase
1. Consult ALL relevant files from above
2. Reference specific decisions in the spec document
3. Include container/service choices from `prebuilt-app-containers.md`

---

## Adding New References

When adding a new planning reference:
1. Place in `docs/reference/`
2. Add entry to this index with purpose and "consult when"
3. Update the relevant AI agent instructions above
