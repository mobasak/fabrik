# Traycer Verification Template

## Template Metadata
- **Type**: Verification
- **Scope**: User (available across all projects)
- **Name**: Spec-Based Task Verification

---

## Template Prompt

You are verifying that a task was implemented correctly. Check against the project specification.

## Verification Process

### Step 1: Load Context
1. Read the project specification (`spec/SPEC.md` or similar)
2. Understand what was supposed to be implemented
3. Review the acceptance criteria for this task

### Step 2: Check Implementation
For each acceptance criterion:
- [ ] **Criterion met?** — Does the code actually implement this?
- [ ] **Spec aligned?** — Does it match the spec's terminology and structure?
- [ ] **No extras?** — Were unrequested features added?
- [ ] **No regressions?** — Does existing functionality still work?

### Step 3: Code Quality Check
- [ ] **Runs without errors** — Can the app start?
- [ ] **No TypeScript/linting errors** — Clean build?
- [ ] **Consistent style** — Matches project patterns?
- [ ] **No hardcoded values** — Uses env vars/config?

### Step 4: Spec Compliance
- [ ] **Entity names match** — Same as Data Model section?
- [ ] **Screen names match** — Same as UI section?
- [ ] **Workflow implemented** — Matches Workflows section?
- [ ] **API endpoints match** — Same as API Design section?

## Verification Output

### Status: [PASS / FAIL / PARTIAL]

### Acceptance Criteria Results
| Criterion | Status | Notes |
|-----------|--------|-------|
| [criterion 1] | ✅/❌ | [notes] |
| [criterion 2] | ✅/❌ | [notes] |

### Issues Found
1. [Issue description + how to fix]
2. [Issue description + how to fix]

### Spec Deviations
1. [What differs from spec + is it acceptable?]

### Recommendation
- [ ] **Proceed to next task** — All criteria met
- [ ] **Fix and re-verify** — Issues must be resolved
- [ ] **Re-plan needed** — Task scope was wrong

---

## Task Being Verified

[Traycer will inject the completed task details here]
