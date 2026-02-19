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

## Planning (Required for Non-Trivial Work)

### Plan Location & Naming
- Location: `docs/development/plans/`
- Filename: `YYYY-MM-DD-plan-<name>.md` (e.g., `2026-01-14-plan-feature-auth.md`)

### Plan Lifecycle
1. **Create** plan in `docs/development/plans/`
2. **Add** to [docs/development/PLANS.md](cci:7://file:///opt/fabrik/docs/development/PLANS.md:0:0-0:0) index
3. **Update** `**Status:**` as work progresses
4. **Check boxes** as items complete
5. **Archive** when COMPLETE → move to `docs/archive/`

### Traycer-Managed Plans

For Traycer-managed work:
- The plan is created and managed in Traycer (Phases)
- Plan MUST be exported from Traycer and saved to `docs/development/plans/`
- Plan MUST still be indexed in `docs/development/PLANS.md`
- Coding agents only execute steps from the Traycer-managed plan

### Required Plan Sections
- `**Status:**` line (NOT_STARTED, IN_PROGRESS, PARTIAL, COMPLETE, NOT_DONE)
- `## Goal` - One-line description
- `## DONE WHEN` - Checkboxes for completion criteria
- `## Out of Scope` - What's excluded
- `## Steps` - Implementation steps

---

## Plan Document Types

### 1. Exploration Plans (Phase A)
Use [templates/docs/PLAN_TEMPLATE.md](cci:7://file:///opt/fabrik/templates/docs/PLAN_TEMPLATE.md:0:0-0:0) for **research and design** phase:
- The Problem
- The Solution
- What We're Building
- How It Works
- What This Fixes
- Timeline

### 2. Execution Plans (Phase B)
Use [templates/docs/EXECUTION_PLAN_TEMPLATE.md](cci:7://file:///opt/fabrik/templates/docs/EXECUTION_PLAN_TEMPLATE.md:0:0-0:0) for **locked implementation**:
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
