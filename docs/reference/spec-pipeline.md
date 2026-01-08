# Spec Pipeline Reference

**Last Updated:** 2026-01-08

Complete workflow for going from idea → scope → spec → implementation.

---

## Overview

The spec pipeline fills the gap between "I have an idea" and "I have a plan to implement."

```
idea → scope → spec → plan → code → review → deploy
```

---

## Commands

| Command | Input | Output |
|---------|-------|--------|
| `droid exec idea "..."` | Your product idea | `specs/<project>/00-idea.md` |
| `droid exec scope "<project>"` | 00-idea.md | `specs/<project>/01-scope.md` |
| `droid exec spec "<project>"` | 00-idea.md + 01-scope.md | `specs/<project>/02-spec.md` |

---

## Quick Start

```bash
# 1. Capture and explore your idea
droid exec idea "Voice-controlled home automation for elderly users"

# 2. Define IN/OUT scope boundaries
droid exec scope "home-automation"

# 3. Generate full specification
droid exec spec "home-automation"

# 4. Continue with implementation
droid exec plan "Implement home-automation per specs/home-automation/02-spec.md"
```

---

## Output Structure

```
specs/
└── <project-name>/
    ├── 00-idea.md      # Problem, users, solution direction
    ├── 01-scope.md     # IN/OUT boundaries, P0/P1 features
    └── 02-spec.md      # Full implementation-ready spec
```

---

## Stage Details

### Stage 1: Idea Discovery

**Purpose:** Capture and explore the product idea through discovery questions.

**Questions Explored:**
- What problem are we solving?
- Who experiences this problem?
- What's the simplest solution?
- What are the constraints?

**Output:** Structured idea document with one-liner, problem statement, target users, proposed solution.

### Stage 2: Scope Definition

**Purpose:** Define explicit IN/OUT boundaries to prevent scope creep.

**Sections:**
- Core value proposition
- IN SCOPE (P0 must-have, P1 should-have)
- OUT OF SCOPE (explicit exclusions)
- DEFERRED (future versions)
- Constraints and risks

**Output:** Scope document with clear boundaries.

### Stage 3: Full Specification

**Purpose:** Generate implementation-ready specification.

**Sections:**
- Overview and success metrics
- Stack profile
- Users and permissions
- Data model
- User journeys
- Screens and navigation
- API design
- Integrations
- Acceptance criteria
- Implementation phases

**Output:** Complete spec that AI coding agents can follow.

---

## Task Type Configuration

| Task | Model | Reasoning | Auto |
|------|-------|-----------|------|
| `idea` | claude-sonnet-4.5 | high | low |
| `scope` | claude-sonnet-4.5 | high | low |
| `spec` | claude-sonnet-4.5 | high | low |

These use premium models with high reasoning for thorough discovery.

---

## Traycer Integration (Optional)

If using Traycer.ai for enhanced planning:

1. Complete the spec pipeline (idea → scope → spec)
2. Point Traycer to `specs/<project>/02-spec.md`
3. Use templates from `templates/traycer/`:
   - `plan_template.md` - Generate phased plan
   - `task_execution_template.md` - Execute tasks
   - `verification_template.md` - Verify completion

See `templates/traycer/README.md` for details.

---

## Templates Location

| Directory | Purpose |
|-----------|---------|
| `templates/spec-pipeline/` | Prompts for idea/scope/spec stages |
| `templates/traycer/` | Optional Traycer integration templates |

---

## See Also

- [droid-exec-usage.md](droid-exec-usage.md) - Core droid exec usage
- [FABRIK_OVERVIEW.md](../FABRIK_OVERVIEW.md) - Full Fabrik overview
- [templates/spec-pipeline/README.md](../../templates/spec-pipeline/README.md) - Template details
