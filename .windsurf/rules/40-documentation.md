---
trigger: always_on
---
# Documentation Rules

activation: glob
globs: ["*.md", "docs/**/*", "specs/**/*"]

---

## CHANGELOG.md (MANDATORY)

**Every code change MUST update CHANGELOG.md:**

```markdown
## [Unreleased]

### Added/Changed/Fixed - <Brief Title> (YYYY-MM-DD)

**What:** One-line description

**Files:**
- `path/to/file.py` - what changed
```

**No exceptions.** This is enforced by `docs_updater.py`.

---

## Plan Document Types

### 1. Exploration Plans (Phase A)
Use `templates/docs/PLAN_TEMPLATE.md` for **research and design** phase:
- The Problem
- The Solution
- What We're Building
- How It Works
- What This Fixes
- Timeline

### 2. Execution Plans (Phase B)
Use `templates/docs/EXECUTION_PLAN_TEMPLATE.md` for **locked implementation**:
- Task Metadata (goal, done-when, out-of-scope)
- Constraints
- Canonical Gate
- 5-7 Execution Steps (DO → GATE → EVIDENCE)
- Stop Conditions

## When to Use Which

| Situation | Template |
|-----------|----------|
| New feature exploration | PLAN_TEMPLATE.md |
| Locked implementation | EXECUTION_PLAN_TEMPLATE.md |
| Bug fix | EXECUTION_PLAN_TEMPLATE.md |
| Refactoring | EXECUTION_PLAN_TEMPLATE.md |

## Execution Plan Rules (STRICT)

```text
- Follow steps exactly in order
- Do NOT redesign or change scope
- One step at a time
- After each step: show Evidence + Gate result
- If a Gate fails → STOP and report
```

## Writing Style

- **Plain language** — No jargon
- **Show don't tell** — Use examples
- **Before/After tables** — Make improvements obvious
- **5-7 steps max** — Human-manageable
