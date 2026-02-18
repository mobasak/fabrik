# GAP-02 Windsurf Workflows — Spec-Level Implementation Plan

**Version:** 1.1.0  
**Revision Date:** 2026-02-17  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-02 v1.0  
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap02-windsurf-workflows.md`

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
| `.windsurf/workflows/deploy.md` | CREATE | Deployment workflow | `head -3 .windsurf/workflows/deploy.md` |
| `.windsurf/workflows/new-feature.md` | CREATE | Feature workflow | `test -f .windsurf/workflows/new-feature.md` |
| `.windsurf/workflows/bug-fix.md` | CREATE | Bug fix workflow | `test -f .windsurf/workflows/bug-fix.md` |
| `.windsurf/workflows/code-review.md` | CREATE | Code review workflow | `grep "droid-review" .windsurf/workflows/code-review.md` |
| `CHANGELOG.md` | MODIFY | Document GAP-02 | Manual verify |

---

## Workflow Constraints

| Rule | Enforcement |
|------|-------------|
| Filename: `[a-z0-9-]+\.md` | Gate: `ls .windsurf/workflows/*.md \| grep -E '^[a-z0-9-]+\.md$'` |
| Location: `.windsurf/workflows/` only | Gate: `test -d .windsurf/workflows/` |
| YAML frontmatter required | Gate: `head -1 <file> \| grep '^---$'` |

---

## YAML Validation Command

```bash
# Validate all workflow files have valid YAML frontmatter
for f in .windsurf/workflows/*.md; do
  python -c "
import yaml, sys
content = open('$f').read()
if not content.startswith('---'):
    sys.exit(f'$f: Missing YAML frontmatter')
parts = content.split('---', 2)
if len(parts) < 3:
    sys.exit(f'$f: Incomplete frontmatter')
try:
    data = yaml.safe_load(parts[1])
    if 'description' not in data:
        sys.exit(f'$f: Missing description field')
    print(f'✓ $f: valid')
except yaml.YAMLError as e:
    sys.exit(f'$f: Invalid YAML: {e}')
"
done
```

---

## Example Workflow (Canonical Fixture)

```markdown
---
description: Deploy application to production via Coolify
---

# Deploy Workflow

## Prerequisites
- All tests passing
- Code review approved
- CHANGELOG updated

## Steps

1. **Build Docker Image**
   \`\`\`bash
   // turbo
   docker build -t $PROJECT:latest .
   \`\`\`

2. **Push to Registry**
   \`\`\`bash
   docker push $PROJECT:latest
   \`\`\`

3. **Trigger Coolify Deploy**
   \`\`\`bash
   ssh vps "cd /opt/$PROJECT && docker compose pull && docker compose up -d"
   \`\`\`

4. **Verify Health**
   \`\`\`bash
   // turbo
   curl -f https://$PROJECT.vps1.ocoron.com/health
   \`\`\`

## Verification
- [ ] Health endpoint returns 200
- [ ] No errors in `docker compose logs`
- [ ] Previous version rolled back if issues
```

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

```
/opt/fabrik/
├── .windsurf/
│   └── rules/                  # Existing rules (6 files)
│       ├── 00-critical.md
│       ├── 10-python.md
│       ├── 20-typescript.md
│       ├── 30-ops.md
│       ├── 40-documentation.md
│       └── 90-automation.md
├── templates/
│   └── docs/                   # Plan templates exist
└── docs/
    └── development/
        └── plans/              # GAP plans location
```

### B. GAP-02 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `.windsurf/rules/` | **FOUND** | `.windsurf/rules/` | **VERIFY** — rules exist |
| `.windsurf/workflows/` | **NOT FOUND** | `.windsurf/workflows/` | **CREATE** directory |
| Workflow templates | **NOT FOUND** | `.windsurf/workflows/*.md` | **CREATE** required |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| None identified | — | — |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `.windsurf/workflows/` | **CREATE** dir | GAP-02 DONE WHEN | — | — |
| `.windsurf/workflows/deploy.md` | **CREATE** | Standard workflow | — | **S** (~30 lines) |
| `.windsurf/workflows/new-feature.md` | **CREATE** | Standard workflow | — | **S** (~40 lines) |
| `.windsurf/workflows/bug-fix.md` | **CREATE** | Standard workflow | — | **S** (~30 lines) |
| `.windsurf/workflows/code-review.md` | **CREATE** | Standard workflow | — | **S** (~25 lines) |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** |

**Explicitly NOT created/modified:**
- `.windsurf/rules/*` — Rules already exist
- `scripts/*` — No script changes needed
- `src/*` — No source changes

---

## 3. Interface & Contract Specification

### A. Workflow File Schema

```yaml
---
description: [short title, max 80 chars]
---

# Workflow Title

## Prerequisites
- [required state before running]

## Steps

### 1. [Step Name]
[instructions]

// turbo  (optional: enables auto-run for safe commands)
### 2. [Step Name]
[instructions]

## Verification
- [how to verify success]
```

### B. Required Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy.md` | `/deploy` | Deploy to Coolify/VPS |
| `new-feature.md` | `/feature` | Start new feature development |
| `bug-fix.md` | `/bugfix` | Fix a reported bug |
| `code-review.md` | `/review` | Run dual-model code review |

### C. deploy.md Contract

```markdown
---
description: Deploy application to VPS via Coolify
---

# Deploy Workflow

## Prerequisites
- All tests passing locally
- CHANGELOG.md updated
- Git working tree clean

## Steps

### 1. Pre-flight checks
// turbo
```bash
pytest tests/ -x --tb=short
ruff check .
mypy .
```

### 2. Build verification
```bash
docker compose build
docker compose up -d --wait
curl -f http://localhost:8000/health
```

### 3. Push to production
```bash
git push origin main
# Coolify auto-deploys on push
```

## Verification
- Health endpoint responds on VPS
- No errors in Coolify logs
```

---

## 4. Golden Paths (2 Required)

### Golden Path 1: Invoke Deploy Workflow

**User input:**
```
/deploy
```

**Expected Cascade behavior:**
1. Read `.windsurf/workflows/deploy.md`
2. Execute steps in order
3. Auto-run steps marked with `// turbo`
4. Wait for approval on other steps

**Expected exit:** Workflow completes successfully

---

### Golden Path 2: Invoke Feature Workflow

**User input:**
```
/feature Add user authentication
```

**Expected Cascade behavior:**
1. Read `.windsurf/workflows/new-feature.md`
2. Create feature branch
3. Set up test structure
4. Begin implementation

**Expected exit:** Feature scaffolding complete

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **Workflow file not found** | File read fails | Print available workflows | None |
| 2 | **Invalid YAML frontmatter** | Parse error | Print syntax error | None |
| 3 | **Pre-flight check fails** | Non-zero exit | Stop workflow, show error | None |
| 4 | **Docker build fails** | Build error | Show logs, suggest fixes | None |
| 5 | **Health check timeout** | Curl fails | Show container logs | `docker compose down` |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
ls -la .windsurf/workflows/*.md && \
head -5 .windsurf/workflows/deploy.md && \
echo "PASS"
```

**Expected PASS output:**
```
-rw-r--r-- 1 user user ... .windsurf/workflows/deploy.md
-rw-r--r-- 1 user user ... .windsurf/workflows/new-feature.md
...
---
description: Deploy application to VPS via Coolify
---
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
- [ ] Steps are actionable
- [ ] Verification section present

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
| Windsurf IDE | Workflows become available via `/` commands |
| Developer UX | Standardized procedures |

### Invariants (Hard Rules)

- **MUST follow:** YAML frontmatter + markdown format
- **MUST NOT create:** Workflows that modify system files
- **MUST include:** `// turbo` only for safe read-only commands
- **MUST have:** Verification section in every workflow

### Duplication Avoidance

| Existing Component | Reuse Strategy |
|-------------------|----------------|
| `.windsurf/rules/` | Workflows reference rules, don't duplicate |
| `AGENTS.md` | Workflows follow AGENTS.md conventions |

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Create Workflows Directory

```text
DO:
- Create .windsurf/workflows/ directory
- Verify .windsurf/ directory already exists (should from rules/)

GATE:
ls -d .windsurf/workflows/

EVIDENCE REQUIRED:
- Directory exists
- No errors

SELF-REVIEW (Builder):
- [ ] Directory created at correct path
- [ ] Parent .windsurf/ directory exists

MODE 4 VERIFICATION:
- Verifier confirms directory structure
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Create deploy.md

```text
DO:
- Create .windsurf/workflows/deploy.md
- Use exact content from Section 3.C
- Include YAML frontmatter with description
- Include steps for Docker build, push, Coolify deploy
- Add verification section

GATE:
head -3 .windsurf/workflows/deploy.md | grep -E "^---$|^description:"

EVIDENCE REQUIRED:
- deploy.md file exists
- YAML frontmatter parses correctly

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid (starts/ends with ---)
- [ ] description field present
- [ ] Steps are actionable and specific
- [ ] Verification section included

MODE 4 VERIFICATION:
- Verifier audits: Valid YAML? Steps clear? Verification present?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create new-feature.md

```text
DO:
- Create .windsurf/workflows/new-feature.md
- Include YAML frontmatter with description
- Include steps for:
  1. Create feature branch
  2. Create/update plan document
  3. Implement feature
  4. Run pre-commit and tests
  5. Create PR
- Add verification section

GATE:
test -f .windsurf/workflows/new-feature.md && head -1 .windsurf/workflows/new-feature.md

EVIDENCE REQUIRED:
- new-feature.md file exists
- File starts with ---

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] Follows Fabrik conventions (plan-first)
- [ ] Branch naming convention specified
- [ ] References AGENTS.md workflow

MODE 4 VERIFICATION:
- Verifier audits: Conventions followed? Complete workflow?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create bug-fix.md

```text
DO:
- Create .windsurf/workflows/bug-fix.md
- Include steps for:
  1. Reproduce the bug
  2. Add failing test
  3. Implement fix
  4. Verify test passes
  5. Run regression tests
  6. Update CHANGELOG
- Add verification section

GATE:
test -f .windsurf/workflows/bug-fix.md && grep -c "^#" .windsurf/workflows/bug-fix.md

EVIDENCE REQUIRED:
- bug-fix.md file exists
- Has multiple step headings

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] Follows debugging best practices
- [ ] Test-first approach documented
- [ ] Regression testing mentioned

MODE 4 VERIFICATION:
- Verifier audits: Best practices? Complete workflow?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Create code-review.md

```text
DO:
- Create .windsurf/workflows/code-review.md
- Include dual-model review pattern from AGENTS.md
- Reference droid-review.sh for execution
- Include steps for:
  1. Run pre-flight gates
  2. Run dual-model review
  3. Address findings
  4. Re-verify until clean
- Add // turbo annotation for safe read-only commands

GATE:
test -f .windsurf/workflows/code-review.md && grep "droid-review" .windsurf/workflows/code-review.md

EVIDENCE REQUIRED:
- code-review.md file exists
- References droid-review.sh

SELF-REVIEW (Builder):
- [ ] YAML frontmatter valid
- [ ] Dual-model pattern documented
- [ ] References existing droid-review.sh
- [ ] // turbo only on read-only commands

MODE 4 VERIFICATION:
- Verifier audits: Correct patterns? Safe annotations?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Final Verification

```text
DO:
- Run canonical gate to verify all workflows
- Update CHANGELOG.md with GAP-02 entry
- Test one workflow with Windsurf /workflow command (if possible)

GATE (CANONICAL):
ls .windsurf/workflows/*.md | wc -l && \
head -5 .windsurf/workflows/deploy.md && \
echo "PASS"

EVIDENCE REQUIRED:
- 4+ workflow files exist
- All have valid YAML frontmatter
- CHANGELOG updated

SELF-REVIEW (Builder):
- [ ] All 4 workflows created
- [ ] CHANGELOG entry present
- [ ] Canonical gate passes

MODE 4 VERIFICATION (FINAL):
- Verifier audits: All workflows present? Valid format? Ready to use?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- .windsurf/ directory doesn't exist
- YAML parsing consistently fails
- Windsurf doesn't recognize workflow format

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `deploy.md`, `new-feature.md`, `bug-fix.md`, `code-review.md` |
| Files to MODIFY | `CHANGELOG.md` |
| Canonical Gate | `ls .windsurf/workflows/*.md && echo "PASS"` |
| Workflow format | YAML frontmatter + markdown steps |

**All sections complete.** Ready for Mode 3 (Build) execution.
