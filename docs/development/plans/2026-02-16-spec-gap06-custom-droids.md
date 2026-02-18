# GAP-06 Custom Droids — Spec-Level Implementation Plan

**Version:** 1.1.0  
**Revision Date:** 2026-02-17  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-06 v1.0  
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap06-custom-droids.md`

---

## Implementation Readiness Checklist

> **Pre-implementation step:** Before starting, verify repo paths exist and run the canonical gate on a clean checkout. Check boxes as verified.

- [ ] **Spec-Level Implementation Plan (implementable specs) attached**
- [ ] Repo grounding paths verified (all referenced files/dirs either exist or are explicitly CREATE)
- [ ] Required Artifacts list complete (CREATE/MODIFY + exact paths)
- [ ] Deterministic Gate is **one exact command** (copy/paste) and passes on a clean checkout
- [ ] DONE WHEN criteria are measurable and mapped to artifacts + gate output
- [ ] Failure modes/rollback defined (even if minimal)

---

## Artifacts Table

| Path | Action | Purpose | Gate Coverage |
|------|--------|---------|---------------|
| `/home/ozgur/.factory/droids/planner.md` | CREATE | Planning droid | `test -f /home/ozgur/.factory/droids/planner.md` |
| `/home/ozgur/.factory/droids/security-auditor.md` | CREATE | Security audit droid | `grep "severity" /home/ozgur/.factory/droids/security-auditor.md` |
| `/home/ozgur/.factory/droids/test-generator.md` | CREATE | Test generation droid | `grep "pytest" /home/ozgur/.factory/droids/test-generator.md` |
| `/home/ozgur/.factory/droids/documentation-writer.md` | CREATE | Documentation droid | `grep "CHANGELOG" /home/ozgur/.factory/droids/documentation-writer.md` |
| `docs/reference/custom-droids.md` | CREATE | Droids documentation | `test -f docs/reference/custom-droids.md` |
| `CHANGELOG.md` | MODIFY | Document GAP-06 | Manual verify |

---

## Droid Definition Schema (Minimal Contract)

```yaml
# Required fields for all droids
name: string        # Unique identifier (e.g., "planner")
model: string       # Model ID from config/models.yaml
autonomy: enum      # "low" | "medium" | "high"
description: string # One-line purpose

# Optional fields
tools: list[string] # Allowed tools (default: all)
constraints: list   # Behavioral constraints
output_format: string # Expected output format
```

---

## YAML Validation Command

**Validate droid frontmatter:**

```bash
# Validate all droids have required fields
for f in /home/ozgur/.factory/droids/*.md; do
  python -c "
import yaml, sys
content = open('$f').read()
if not content.startswith('---'):
    sys.exit(f'$f: Missing YAML frontmatter')
fm = content.split('---')[1]
data = yaml.safe_load(fm)
required = ['name', 'model', 'autonomy', 'description']
missing = [k for k in required if k not in data]
if missing:
    sys.exit(f'$f: Missing fields: {missing}')
print(f'✓ $f: valid')
"
done
```

**List all droids command:**

```bash
# List available droids with their models
ls /home/ozgur/.factory/droids/*.md | xargs -I{} sh -c 'echo "=== {} ===" && head -10 {} | grep -E "^name:|^model:|^autonomy:"'
```

---

## Example Droid Definition (Canonical Fixture)

```markdown
---
name: planner
model: claude-sonnet-4-5-20250929
autonomy: low
description: Creates detailed execution plans from task descriptions
tools:
  - read_file
  - grep_search
  - find_by_name
---

# Planner Droid

## Role
You are a planning specialist. You analyze tasks and create detailed execution plans.

## Constraints
- Do NOT implement code
- Do NOT modify files
- Output must be markdown
- Include risk assessment

## Output Format
```markdown
# Plan: [Task Title]

## Risk Assessment
[LOW | MEDIUM | HIGH] - [reasoning]

## Steps
1. [Step 1]
2. [Step 2]
...
```
```

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (External to Repo)

```
/home/ozgur/.factory/
├── settings.json               # Factory CLI settings (EXISTS)
├── mcp.json                    # MCP config (GAP-03 scope)
└── droids/                     # Custom droids directory (EXISTS)
    ├── coder.md                # Existing droid
    ├── analyst.md              # Existing droid
    └── writer.md               # Existing droid
```

### B. GAP-06 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `/home/ozgur/.factory/droids/` | **FOUND** | `/home/ozgur/.factory/droids/` | **VERIFY** — directory exists |
| `/home/ozgur/.factory/droids/coder.md` | **FOUND** | Existing | **VERIFY** — pattern reference |
| `planner.md` | **NOT FOUND** | `/home/ozgur/.factory/droids/` | **CREATE** required |
| `security-auditor.md` | **NOT FOUND** | `/home/ozgur/.factory/droids/` | **CREATE** required |
| `test-generator.md` | **NOT FOUND** | `/home/ozgur/.factory/droids/` | **CREATE** required |
| `documentation-writer.md` | **NOT FOUND** | `/home/ozgur/.factory/droids/` | **CREATE** required |
| `docs/reference/custom-droids.md` | **NOT FOUND** | `docs/reference/` | **CREATE** required |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| `/home/ozgur/.factory/droids/` missing | Create directory | Factory CLI creates on first use |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `/home/ozgur/.factory/droids/planner.md` | **CREATE** | GAP-06 DONE WHEN: 4 new droids | — | **M** (~50 lines) |
| `/home/ozgur/.factory/droids/security-auditor.md` | **CREATE** | GAP-06 DONE WHEN | — | **M** (~50 lines) |
| `/home/ozgur/.factory/droids/test-generator.md` | **CREATE** | GAP-06 DONE WHEN | — | **M** (~50 lines) |
| `/home/ozgur/.factory/droids/documentation-writer.md` | **CREATE** | GAP-06 DONE WHEN | — | **M** (~50 lines) |
| `docs/reference/custom-droids.md` | **CREATE** | Documentation | — | **M** (~80 lines) |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** |

**Explicitly NOT created/modified:**
- Existing droids (`coder.md`, `analyst.md`, `writer.md`) — Only add new
- `/home/ozgur/.factory/settings.json` — No settings changes
- Repo source code — Droids are external

---

## 3. Interface & Contract Specification

### A. Droid File Schema

```markdown
---
name: [Droid Name]
description: [One-line description]
model: [preferred model from config/models.yaml]
autonomy: [low|medium|high]
---

# [Droid Name]

## Role
[Detailed role description]

## Capabilities
- [Capability 1]
- [Capability 2]

## Constraints
- [Constraint 1]
- [Constraint 2]

## Instructions
[Detailed instructions for the droid]

## Output Format
[Expected output format]
```

### B. New Droids Specification

| Droid | Purpose | Model | Autonomy |
|-------|---------|-------|----------|
| `planner` | Create execution plans | claude-sonnet-4-5-20250929 | low |
| `security-auditor` | Security review | gpt-5.3-codex | low |
| `test-generator` | Generate tests | swe-1-5 | medium |
| `documentation-writer` | Update docs | claude-haiku-4-5 | medium |

### C. planner.md Contract

```markdown
---
name: Planner
description: Creates detailed execution plans from requirements
model: claude-sonnet-4-5-20250929
autonomy: low
---

# Planner Droid

## Role
Create detailed, step-by-step execution plans that can be implemented without ambiguity.

## Capabilities
- Analyze requirements and break into steps
- Identify dependencies between steps
- Define gates and verification criteria
- Estimate effort and risk

## Constraints
- Do NOT implement code
- Do NOT modify files
- Output plan document only
- Follow EXECUTION_PLAN_TEMPLATE.md format

## Instructions
1. Read the requirement carefully
2. Scan repo for existing related code
3. Identify what needs CREATE vs MODIFY
4. Break into 5-7 implementable steps
5. Define gate for each step
6. Output as markdown plan

## Output Format
Markdown following templates/docs/EXECUTION_PLAN_TEMPLATE.md
```

### D. security-auditor.md Contract

```markdown
---
name: Security Auditor
description: Reviews code for security vulnerabilities
model: gpt-5.3-codex
autonomy: low
---

# Security Auditor Droid

## Role
Audit code changes for security issues before merge.

## Capabilities
- Detect hardcoded secrets
- Find injection vulnerabilities
- Check authentication/authorization
- Review cryptographic usage

## Constraints
- Do NOT fix issues (report only)
- Do NOT modify files
- Output JSON report only

## Instructions
1. Review all changed files
2. Check against OWASP Top 10
3. Verify no hardcoded secrets
4. Check input validation
5. Output findings as JSON

## Output Format
```json
{
  "severity": "low|medium|high|critical",
  "findings": [
    {"file": "...", "line": N, "issue": "...", "recommendation": "..."}
  ],
  "approved": true|false
}
```
```

---

## 4. Golden Paths (2 Required)

### Golden Path 1: Invoke Planner Droid

**Command:**
```bash
droid exec --droid planner "Create a plan for adding rate limiting to the API"
```

**Expected output:**
```markdown
# Rate Limiting Implementation Plan

## Step 1 — Research existing patterns
...

## Step 2 — Define rate limit config
...
```

---

### Golden Path 2: Invoke Security Auditor

**Command:**
```bash
droid exec --droid security-auditor "Audit src/api/auth.py"
```

**Expected output:**
```json
{
  "severity": "low",
  "findings": [],
  "approved": true
}
```

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **Droid file not found** | File read fails | List available droids | None |
| 2 | **Invalid YAML frontmatter** | Parse error | Print syntax error | Fix YAML |
| 3 | **Model not available** | droid exec error | Suggest fallback model | None |
| 4 | **Droid exceeds autonomy** | Makes unauthorized changes | Reject, log violation | Revert changes |
| 5 | **Output format mismatch** | Parser fails | Show expected format | None |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
ls /home/ozgur/.factory/droids/*.md | wc -l && \
head -5 /home/ozgur/.factory/droids/planner.md && \
echo "PASS"
```

**Expected PASS output:**
```
7
---
name: Planner
description: Creates detailed execution plans from requirements
model: claude-sonnet-4-5-20250929
PASS
```

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

After **every step**, builder/verifier MUST output:

```text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [ ] YAML frontmatter valid
- [ ] Role clearly defined
- [ ] Constraints appropriate

Pre-Flight Gates:
- File exists: PASS/FAIL
- YAML valid: PASS/FAIL

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| Factory CLI | New droids become available |
| `droid exec` | Can invoke with `--droid` flag |

### Invariants (Hard Rules)

- **MUST follow:** YAML frontmatter + markdown format
- **MUST NOT modify:** Existing droids
- **MUST specify:** Model and autonomy level
- **MUST include:** Constraints section

### Autonomy Levels

| Level | Allowed Actions |
|-------|-----------------|
| `low` | Read-only, output only |
| `medium` | File edits allowed |
| `high` | Commits, installs allowed |

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Create planner.md

```text
DO:
- Create /home/ozgur/.factory/droids/planner.md
- Use exact content from Section 3.C
- Include YAML frontmatter with:
  - name: Planner
  - description: Creates detailed execution plans
  - model: claude-sonnet-4-5-20250929
  - autonomy: low
- Include Role, Capabilities, Constraints, Instructions, Output Format sections

GATE:
head -5 /home/ozgur/.factory/droids/planner.md | grep -E "^name:|^model:"

EVIDENCE REQUIRED:
- planner.md file exists
- YAML frontmatter parses correctly
- Role and constraints clearly defined

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] Role clearly defined
- [ ] Constraints include "Do NOT implement code"
- [ ] Output format specifies markdown plan

MODE 4 VERIFICATION:
- Verifier audits: Valid format? Constraints appropriate?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Create security-auditor.md

```text
DO:
- Create /home/ozgur/.factory/droids/security-auditor.md
- Use content from Section 3.D
- Include YAML frontmatter with:
  - name: Security Auditor
  - model: gpt-5.3-codex (or current verification model)
  - autonomy: low
- Define JSON output format for findings

GATE:
test -f /home/ozgur/.factory/droids/security-auditor.md && grep "severity" /home/ozgur/.factory/droids/security-auditor.md

EVIDENCE REQUIRED:
- security-auditor.md file exists
- Output format specifies JSON structure

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] Checks OWASP Top 10
- [ ] Output is JSON with severity, findings, approved fields
- [ ] Constraints include "Do NOT fix issues"

MODE 4 VERIFICATION:
- Verifier audits: JSON format correct? Security checks comprehensive?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create test-generator.md

```text
DO:
- Create /home/ozgur/.factory/droids/test-generator.md
- Include YAML frontmatter with:
  - name: Test Generator
  - model: swe-1-5 (or current execution model)
  - autonomy: medium (can create test files)
- Include patterns for:
  - pytest unit tests
  - hypothesis property tests
  - Given/When/Then structure

GATE:
test -f /home/ozgur/.factory/droids/test-generator.md && grep "pytest" /home/ozgur/.factory/droids/test-generator.md

EVIDENCE REQUIRED:
- test-generator.md file exists
- pytest patterns documented

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] pytest patterns included
- [ ] hypothesis patterns included
- [ ] Output generates valid Python test code

MODE 4 VERIFICATION:
- Verifier audits: Test patterns correct? Autonomy appropriate?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create documentation-writer.md

```text
DO:
- Create /home/ozgur/.factory/droids/documentation-writer.md
- Include YAML frontmatter with:
  - name: Documentation Writer
  - model: claude-haiku-4-5 (or current docs model)
  - autonomy: medium (can edit docs)
- Reference Fabrik doc conventions from .windsurf/rules/40-documentation.md
- Include patterns for README, API docs, guides

GATE:
test -f /home/ozgur/.factory/droids/documentation-writer.md && grep "CHANGELOG" /home/ozgur/.factory/droids/documentation-writer.md

EVIDENCE REQUIRED:
- documentation-writer.md file exists
- References Fabrik conventions

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] References Fabrik doc standards
- [ ] CHANGELOG update pattern included
- [ ] docs/ structure referenced

MODE 4 VERIFICATION:
- Verifier audits: Conventions correct? Patterns useful?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Create Reference Documentation

```text
DO:
- Create docs/reference/custom-droids.md
- Document all droids (existing 3 + new 4):
  - Name, purpose, model, autonomy level
  - How to invoke: droid exec --droid <name> "prompt"
  - Example use cases
  - Output format for each

GATE:
test -f docs/reference/custom-droids.md && grep -c "^##" docs/reference/custom-droids.md
# Expected: 7+ (one section per droid)

EVIDENCE REQUIRED:
- custom-droids.md file exists
- All 7 droids documented

SELF-REVIEW (Builder):
- [ ] All droids listed
- [ ] Invocation syntax documented
- [ ] Example commands provided
- [ ] Output formats documented

MODE 4 VERIFICATION:
- Verifier audits: Complete? Accurate? Useful?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Test Each Droid

```text
DO:
- Test planner droid: droid exec --droid planner "Create plan for adding health endpoint"
- Test security-auditor droid: droid exec --droid security-auditor "Audit src/fabrik/scaffold.py"
- Test test-generator droid: droid exec --droid test-generator "Generate tests for scaffold.py"
- Test documentation-writer droid: droid exec --droid documentation-writer "Update README.md"
- Verify each produces expected output format

GATE:
ls /home/ozgur/.factory/droids/*.md | wc -l
# Expected: 7 or more

EVIDENCE REQUIRED:
- All 4 new droids respond correctly
- Output matches expected format

SELF-REVIEW (Builder):
- [ ] planner outputs markdown plan
- [ ] security-auditor outputs JSON
- [ ] test-generator outputs valid Python
- [ ] documentation-writer follows conventions

MODE 4 VERIFICATION:
- Verifier audits: All droids work? Output formats correct?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 7 — Final Verification

```text
DO:
- Run canonical gate
- Update CHANGELOG.md with GAP-06 entry
- Verify all droids accessible via Factory CLI

GATE (CANONICAL):
ls /home/ozgur/.factory/droids/*.md | wc -l && \
head -5 /home/ozgur/.factory/droids/planner.md && \
echo "PASS"

EVIDENCE REQUIRED:
- 7+ droid files exist
- planner.md has valid YAML
- CHANGELOG updated

SELF-REVIEW (Builder):
- [ ] All 4 new droids created
- [ ] Documentation complete
- [ ] CHANGELOG entry present

MODE 4 VERIFICATION (FINAL):
- Verifier audits: All droids ready? Documentation complete?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- /home/ozgur/.factory/droids/ directory doesn't exist
- Factory CLI doesn't support --droid flag
- Model names in config changed significantly

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `planner.md`, `security-auditor.md`, `test-generator.md`, `documentation-writer.md`, `custom-droids.md` |
| Files to MODIFY | `CHANGELOG.md` |
| Canonical Gate | 7+ droid files exist |
| Format | YAML frontmatter + markdown |

**All sections complete.** Ready for Mode 3 (Build) execution.
