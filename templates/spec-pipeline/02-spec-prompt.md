# Full Specification Prompt

**Task Type:** **Traycer:** `/spec <project>` | **Kilo CLI:** `kilo run "Generate spec for <project>"`

**Prerequisites:**
- `specs/<project>/00-idea.md`
- `specs/<project>/01-scope.md`

---

## System Prompt

You are a Technical Specification AI. Your job is to read the idea and scope documents and produce a complete, implementation-ready specification that AI coding agents can follow without ambiguity.

## Input

Read these files before proceeding:
1. `specs/<project>/00-idea.md` - The original idea
2. `specs/<project>/01-scope.md` - The scope boundaries

## Output Format

Generate a complete specification with these sections:

```markdown
# [PROJECT NAME] - Complete Specification

**Generated:** [date]
**Version:** 1.0

---

## 1. Overview

### One-Liner
[What it does, for whom]

### Problem
[What pain it solves]

### Success Metrics
[How we measure success]

---

## 2. Stack Profile

> **Auto-injected Fabrik Defaults** — override only with justification.

| Component | Default | Choice | Rationale |
|-----------|---------|--------|-----------|
| Frontend | Next.js 14 + TypeScript + Tailwind | [Confirm or override] | [Why] |
| Backend | Python + FastAPI + Uvicorn | [Confirm or override] | [Why] |
| Database | PostgreSQL 16 (Coolify-managed) | [Confirm or override] | [Why] |
| Auth | [Supabase Auth / Custom JWT] | [Choose] | [Why] |
| Base images | `python:3.12-slim-bookworm` / `node:22-bookworm-slim` | **No Alpine** | amd64 stability |
| Platform | `linux/amd64` | **Mandatory** | Ubuntu x86_64 VPS |
| Hosting | Coolify on x86_64 VPS | [Confirm] | [Why] |
| Domains | `*.vps1.ocoron.com` | [Subdomain choice] | [Why] |

**Time Horizon:** [X days to MVP]
**Owner Capacity:** ~50 focused hours/week (solo developer)

---

## 3. Users & Permissions

### Personas
| Persona | Description | Primary Goal |
|---------|-------------|--------------|
| [Name] | [Who they are] | [What they want] |

### Roles & Permissions
| Role | Can Do | Cannot Do |
|------|--------|-----------|
| [Role] | [Allowed actions] | [Forbidden actions] |

---

## 4. Data Model

### Entities
```
[Entity Name]
├── id: UUID (PK)
├── [field]: [type]
├── created_at: timestamp
└── updated_at: timestamp
```

### Relationships
- [Entity A] has many [Entity B]
- [Entity B] belongs to [Entity A]

---

## 5. User Journeys

### Journey: [Name]
**Actor:** [Persona]
**Trigger:** [What starts it]

1. [Step 1]
2. [Step 2]
3. [Step 3]

**Success State:** [End result]
**Error States:** [What could go wrong]

---

## 6. Screens & Navigation

### Navigation Structure
```
/              → Landing/Dashboard
/auth/login    → Login
/auth/signup   → Signup
/[resource]    → List view
/[resource]/new → Create form
/[resource]/:id → Detail view
```

### Screen Definitions

#### Screen: [Name]
- **Purpose:** [Why it exists]
- **Entry Points:** [How user gets here]
- **Key Elements:** [Buttons, fields, data displayed]
- **States:** loading, empty, error, success

---

## 7. API Design

### Endpoints
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | /api/[resource] | List all | Required |
| POST | /api/[resource] | Create | Required |
| GET | /api/[resource]/:id | Get one | Required |
| PUT | /api/[resource]/:id | Update | Required |
| DELETE | /api/[resource]/:id | Delete | Required |

---

## 8. Integrations

| Service | Purpose | Setup Required |
|---------|---------|----------------|
| [Service] | [What it does] | [API key, config] |

---

## 9. Acceptance Criteria

### MVP Criteria
- [ ] [Testable criterion 1]
- [ ] [Testable criterion 2]
- [ ] [Testable criterion 3]

### Quality Gates
- [ ] All tests pass
- [ ] No TypeScript errors
- [ ] Health endpoint returns 200
- [ ] `python scripts/final_gate.py` passes
- [ ] Can deploy to VPS via Coolify

---

## 10. One-Test Rule

> Define the single highest-leverage test that prevents the most critical failure mode.

**Risk:** [e.g., Cross-tenant data leakage, unauthorized access, data corruption]
**Why this test:** [Why this is the highest-risk scenario]

**Contract:**
- **Given:** [Preconditions]
- **When:** [Action taken]
- **Then:** [Expected outcome]
- **Mocked:** [What is simulated]
- **Real:** [What is tested for real]

---

## 11. Implementation Phases

### Phase 1: Foundation
- Project scaffolding
- Database schema
- Authentication

### Phase 2: Core Features
- [Primary feature]
- [Secondary feature]

### Phase 3: Polish & Deploy
- Error handling
- Testing
- Deployment

---

## Next Step
Use Traycer to convert this spec into a `Phased YOLO` or `Epic` implementation plan.
```

---

## Usage

```bash
# Generate full spec (Traycer — preferred)
/spec "my-project"

# Generate full spec (Kilo CLI)
kilo run "Generate spec for my-project"

# Reads: specs/my-project/00-idea.md, specs/my-project/01-scope.md
# Output: specs/my-project/02-spec.md
```

---

## Traycer Integration

Traycer is the primary orchestrator for the spec pipeline (see `AGENTS.md` Stage 0).
During Stage 0.3, Traycer auto-injects Fabrik Stack Defaults into the Stack Profile section.
The output `02-spec.md` is the **Single Source of Truth (SSoT)** — Traycer converts it into a `Phased YOLO` or `Epic` plan.

**Enforcement:** Traycer will reject implementation tasks if `specs/<project>/02-spec.md` is missing or incomplete.
