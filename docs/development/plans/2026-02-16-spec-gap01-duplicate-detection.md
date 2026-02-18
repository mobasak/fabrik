# GAP-01 Duplicate Detection — Spec-Level Implementation Plan

**Version:** 1.1.0  
**Revision Date:** 2026-02-17  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-01 v1.0  
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap01-duplicate-detection.md`

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
| `.jscpd.json` | CREATE | jscpd configuration | `jscpd --config .jscpd.json src/ scripts/` |
| `.pre-commit-config.yaml` | MODIFY | Add jscpd hook | `pre-commit run jscpd --all-files` |
| `scripts/enforcement/check_duplicates.py` | CREATE | Enforcement script | `python scripts/enforcement/check_duplicates.py` |
| `.github/workflows/ci.yml` | CREATE | CI workflow with dup check | `yq '.jobs.duplicates' .github/workflows/ci.yml` |
| `docs/reference/duplicate-baseline.md` | CREATE | Baseline documentation | Manual verify |
| `CHANGELOG.md` | MODIFY | Document GAP-01 | Manual verify |

---

## Scope Clarification: CI Workflow

> **CI workflow creation is IN SCOPE** for GAP-01 but as an **optional enhancement step**.

| Step | Scope | Gate |
|------|-------|------|
| jscpd config + pre-commit | **REQUIRED** | Canonical gate |
| Enforcement script | **REQUIRED** | `python scripts/enforcement/check_duplicates.py` |
| CI workflow creation | **OPTIONAL** | `yq '.jobs.duplicates' .github/workflows/ci.yml` |

If CI workflow already exists, modify it. If not, creation is optional (pre-commit is sufficient for local enforcement).

---

## Duplicate Detection Threshold Config

```json
// .jscpd.json
{
  "threshold": 5,
  "minLines": 5,
  "minTokens": 50,
  "reporters": ["console", "json"],
  "output": ".tmp/jscpd-report",
  "ignore": [
    "**/node_modules/**",
    "**/.venv/**",
    "**/tests/fixtures/**",
    "**/__pycache__/**"
  ],
  "format": ["python", "typescript", "javascript", "markdown"]
}
```

**Threshold rules:**
- `threshold: 5` = max 5% duplication allowed
- `minLines: 5` = blocks shorter than 5 lines ignored
- `minTokens: 50` = blocks with fewer than 50 tokens ignored

---

## Sample Fixture (for testing detection)

Create this folder structure to verify detection works:

```
tests/fixtures/duplicates/
├── original.py
└── duplicate.py
```

**original.py:**
```python
def calculate_total(items: list[dict]) -> float:
    total = 0.0
    for item in items:
        price = item.get('price', 0)
        quantity = item.get('quantity', 1)
        total += price * quantity
    return total
```

**duplicate.py:**
```python
def compute_sum(products: list[dict]) -> float:
    total = 0.0
    for product in products:
        price = product.get('price', 0)
        quantity = product.get('quantity', 1)
        total += price * quantity
    return total
```

**Test command:**
```bash
jscpd tests/fixtures/duplicates/ --config .jscpd.json
# Expected: Report showing duplicate block detected
```

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

```
/opt/fabrik/
├── .pre-commit-config.yaml     # 12 hooks exist
├── scripts/
│   └── enforcement/            # 15 scripts exist
│       ├── __init__.py
│       ├── check_secrets.py    # Pattern to follow
│       ├── check_changelog.py
│       └── validate_conventions.py
├── .github/workflows/
│   ├── droid-review.yml        # Primary CI workflow
│   ├── daily-maintenance.yml
│   └── security-scanner.yml
└── docs/
    └── reference/              # For baseline doc
```

### B. GAP-01 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `.pre-commit-config.yaml` | **FOUND** | Root | **MODIFY** — add jscpd hook |
| `scripts/enforcement/check_secrets.py` | **FOUND** | Pattern reference | **VERIFY** — follow this pattern |
| `scripts/enforcement/validate_conventions.py` | **FOUND** | `scripts/enforcement/` | **MODIFY** — integrate check_duplicates |
| `scripts/enforcement/__init__.py` | **FOUND** | `scripts/enforcement/` | **MODIFY** — export new check |
| `.github/workflows/ci.yml` | **NOT FOUND** | `.github/workflows/` | **CREATE** — new workflow for duplicate detection |
| `.jscpd.json` | **NOT FOUND** | Root | **CREATE** required |
| `scripts/enforcement/check_duplicates.py` | **NOT FOUND** | `scripts/enforcement/` | **CREATE** required |
| `docs/reference/duplicate-baseline.md` | **NOT FOUND** | `docs/reference/` | **CREATE** required |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| npm/npx not installed | See **Step 0 Bootstrap** below | Use Docker container with npm |
| Existing duplicates > 20% | Document baseline, enable warn-only mode | Refactor critical duplicates first |

### D. Bootstrap Requirement (MANDATORY)

**Problem:** jscpd requires Node.js/npm which is not installed in this Python-only repo.

**Deterministic Bootstrap (execute before Step 1):**

```bash
# Option A: Install Node.js via nvm (recommended for dev)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
node --version  # Must output: v20.x.x
npm --version   # Must output: 10.x.x

# Option B: Install via apt (simpler but older version)
sudo apt update && sudo apt install -y nodejs npm
node --version && npm --version

# Option C: Use npx via container (CI-only)
# See CI workflow definition below
```

**Bootstrap Gate:**
```bash
node --version && npm --version && npx jscpd --version && echo "BOOTSTRAP PASS"
```

**Expected output:**
```
v20.x.x
10.x.x
jscpd: 4.x.x
BOOTSTRAP PASS
```

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `.jscpd.json` | **CREATE** | GAP-01 DONE WHEN: config exists | — | **S** (~20 lines) |
| `.pre-commit-config.yaml` | **MODIFY** | GAP-01 DONE WHEN: hook runs | All other hooks | **S** (~15 lines) |
| `scripts/enforcement/check_duplicates.py` | **CREATE** | GAP-01 DONE WHEN: enforcement wrapper | — | **M** (~100 lines) |
| `scripts/enforcement/validate_conventions.py` | **MODIFY** | Integration point | All other checks | **S** (~10 lines) |
| `scripts/enforcement/__init__.py` | **MODIFY** | Export new function | Existing exports | **S** (~2 lines) |
| `.github/workflows/ci.yml` | **CREATE** | GAP-01 DONE WHEN: CI runs | — | **M** (~40 lines) |
| `docs/reference/duplicate-baseline.md` | **CREATE** | GAP-01 DONE WHEN: baseline documented | — | **M** (~50 lines) |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** (~5 lines) |

**Explicitly NOT created/modified:**
- `src/` — No source code changes
- `scripts/droid_core.py` — Unrelated to duplicate detection
- Other enforcement scripts — Only check_duplicates.py is new

---

## 3. Interface & Contract Specification

### A. .jscpd.json Schema

```json
{
  "threshold": 3,
  "minLines": 10,
  "minTokens": 50,
  "reporters": ["json", "console"],
  "ignore": [
    "**/.venv/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.next/**",
    "**/dist/**",
    "**/.git/**"
  ],
  "format": ["python", "typescript", "javascript", "tsx"],
  "absolute": true,
  "gitignore": true
}
```

**Required fields:**
- `threshold`: integer 1-100 (max % duplication allowed)
- `minLines`: integer >= 5 (minimum clone size)
- `minTokens`: integer >= 25 (minimum token count)

### B. Pre-commit Hook Contract

```yaml
# Exact stanza to add to .pre-commit-config.yaml
- repo: local
  hooks:
    - id: jscpd
      name: Check for code duplicates (jscpd)
      entry: npx jscpd --config .jscpd.json --exitCode 1
      language: system
      pass_filenames: false
      types: [file]
      files: \.(py|ts|tsx|js)$
      stages: [commit]
```

### C. check_duplicates.py Interface

```python
# Function signatures (mandatory)
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DuplicateResult:
    path: Path
    start_line: int
    end_line: int
    clone_path: Path
    clone_start: int
    clone_end: int
    lines: int
    tokens: int

def run_jscpd(paths: list[Path], threshold: int = 3) -> tuple[bool, list[DuplicateResult]]:
    """Run jscpd and return (passed, duplicates)."""
    ...

def check_duplicates(paths: list[Path]) -> int:
    """Main entry point. Returns exit code 0/1/2."""
    ...
```

**Exit codes:**
| Code | Meaning |
|------|---------|
| `0` | Pass — no duplicates above threshold |
| `1` | Warn — duplicates found but below blocking threshold |
| `2` | Block — duplicates exceed blocking threshold |

### D. CI Workflow (CREATE new file)

```yaml
# .github/workflows/ci.yml (CREATE this file)
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  duplicate-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Check for code duplicates
        run: |
          npx jscpd --config .jscpd.json --reporters json,console --output .jscpd-report
          if [ -f .jscpd-report/jscpd-report.json ]; then
            DUPS=$(jq '.statistics.total.percentage' .jscpd-report/jscpd-report.json)
            echo "Duplication: ${DUPS}%"
            if (( $(echo "$DUPS > 3" | bc -l) )); then
              echo "::error::Duplication exceeds 3% threshold"
              exit 1
            fi
          fi
      
      - name: Upload duplicate report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: jscpd-report
          path: .jscpd-report/
          retention-days: 7
```

---

## 4. Golden Paths (2 Required)

### Golden Path 1: Clean Commit (No Duplicates)

**Command:**
```bash
echo "def unique_function(): pass" > /tmp/test.py
pre-commit run jscpd --files /tmp/test.py
```

**Expected output:**
```
Check for code duplicates (jscpd)...........................Passed
```

**Expected exit code:** `0`

---

### Golden Path 2: Duplicate Detected (Blocked)

**Command:**
```bash
# Create duplicate code
cat > /tmp/dup1.py << 'EOF'
def calculate_total(items):
    total = 0
    for item in items:
        if item.active:
            total += item.price * item.quantity
            if item.discount:
                total -= item.discount
    return total
EOF
cp /tmp/dup1.py /tmp/dup2.py
npx jscpd /tmp --config .jscpd.json --exitCode 1
```

**Expected output:**
```
Clone found (python):
 - /tmp/dup1.py [1-9]
 - /tmp/dup2.py [1-9]

Duplicates detection: Found 1 exact clones
```

**Expected exit code:** `1`

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **npm/npx not installed** | `which npx` returns empty | Print install instructions, exit 1 | None |
| 2 | **jscpd.json invalid JSON** | `jq . .jscpd.json` fails | Print JSON error, exit 3 | Remove malformed file |
| 3 | **Existing duplicates > 20%** | Initial baseline scan | Enable warn-only mode, document baseline | N/A (planning phase) |
| 4 | **Pre-commit hook infinite loop** | Hook takes > 60s | Add `--ignore` patterns, timeout | Remove hook from config |
| 5 | **CI step fails on ARM64** | GitHub Actions ARM runner error | Use `npm install -g jscpd` instead of npx | Pin to x86 runner |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
pre-commit run jscpd --all-files && echo "PASS"
```

**Expected PASS output:**
```
Check for code duplicates (jscpd)...........................Passed
PASS
```

**Expected FAIL output:**
```
Check for code duplicates (jscpd)...........................Failed
- hook id: jscpd
- exit code: 1
```

**Secondary verification:**
```bash
python -m scripts.enforcement.check_duplicates src/ && echo "PASS"
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
- [ ] File follows Fabrik patterns
- [ ] Type annotations complete
- [ ] No hardcoded values

Pre-Flight Gates:
- ruff: PASS/FAIL
- mypy: PASS/FAIL

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
| `pre-commit` framework | New hook registered |
| CI pipeline | New step added |
| Developer workflow | New check on commit |

### Invariants (Hard Rules)

- **MUST reuse:** `scripts/enforcement/check_*.py` pattern
- **MUST NOT create:** New Python dependencies (jscpd is npm-based)
- **MUST NOT modify:** Existing pre-commit hooks (only add new)
- **MUST pass:** `ruff check .` and `mypy .` before verification

### Duplication Avoidance

| Existing Component | Reuse Strategy |
|-------------------|----------------|
| `check_secrets.py` pattern | Follow exact function signatures and CheckResult pattern |
| `validate_conventions.py` | Import and call `check_duplicates()` |
| `.pre-commit-config.yaml` local hooks | Follow existing `fabrik-conventions` hook pattern |

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 0 — Bootstrap Node.js Environment (PREREQUISITE)

```text
DO:
- Check if Node.js installed: node --version
- If NOT installed, use one of:
  - Option A: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash && nvm install 20
  - Option B: sudo apt update && sudo apt install -y nodejs npm
- Verify npm available: npm --version

GATE:
node --version && npm --version && npx jscpd --version && echo "BOOTSTRAP PASS"

EXPECTED OUTPUT:
v20.x.x
10.x.x
jscpd: 4.x.x
BOOTSTRAP PASS

IF FAIL:
- STOP — cannot proceed without Node.js
- Report exact error and which install option failed
```

---

### Step 1 — Create jscpd Configuration

```text
DO:
- Create .jscpd.json at repo root using schema from Section 3.A
- Set threshold: 3 (max 3% duplication)
- Set minLines: 10, minTokens: 50
- Add ignore patterns for .venv, node_modules, __pycache__, .next, dist, .git
- Set formats: python, typescript, javascript, tsx

GATE:
jq . .jscpd.json && npx jscpd --version

EVIDENCE REQUIRED:
- .jscpd.json file content
- jq validation output (no errors)

SELF-REVIEW (Builder):
- [ ] JSON valid (jq passes)
- [ ] Threshold set to 3
- [ ] Ignore patterns include all build directories
- [ ] Python format included

PRE-FLIGHT GATES:
ruff check . && mypy .

MODE 4 VERIFICATION:
- Verifier audits: Valid JSON? Threshold appropriate? Ignores correct?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Add Pre-commit Hook

```text
DO:
- Add jscpd hook to .pre-commit-config.yaml
- Use exact stanza from Section 3.B:
  - repo: local
  - id: jscpd
  - entry: npx jscpd --config .jscpd.json --exitCode 1
  - language: system
  - pass_filenames: false
  - files: \.(py|ts|tsx|js)$

GATE:
pre-commit run jscpd --all-files

EVIDENCE REQUIRED:
- .pre-commit-config.yaml diff showing new hook
- pre-commit run output (may have warnings initially)

SELF-REVIEW (Builder):
- [ ] Hook syntax matches existing local hook patterns
- [ ] pass_filenames: false (jscpd scans directories)
- [ ] files pattern covers Python and TypeScript

PRE-FLIGHT GATES:
ruff check . && mypy .

MODE 4 VERIFICATION:
- Verifier audits: Correct syntax? Follows existing patterns?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create Enforcement Script Wrapper

```text
DO:
- Create scripts/enforcement/check_duplicates.py
- Follow check_secrets.py pattern exactly:
  - Import dataclass, Path, subprocess
  - Define DuplicateResult dataclass (from Section 3.C)
  - Implement run_jscpd(paths, threshold) -> tuple[bool, list[DuplicateResult]]
  - Implement check_duplicates(paths) -> int (exit code 0/1/2)
- Parse JSON output from jscpd
- Return CheckResult-compatible objects

GATE:
python -m scripts.enforcement.check_duplicates src/

EVIDENCE REQUIRED:
- check_duplicates.py content
- Test run output showing pass/warn/block

SELF-REVIEW (Builder):
- [ ] Type annotations on all functions
- [ ] Follows check_secrets.py patterns
- [ ] Returns appropriate exit codes (0=pass, 1=warn, 2=block)
- [ ] Handles jscpd not found gracefully

PRE-FLIGHT GATES:
ruff check scripts/enforcement/check_duplicates.py && mypy scripts/enforcement/check_duplicates.py

MODE 4 VERIFICATION:
- Verifier audits: Type hints? Pattern compliance? Error handling?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Integrate with validate_conventions.py

```text
DO:
- Import check_duplicates in validate_conventions.py:
  from scripts.enforcement.check_duplicates import check_duplicates
- Add run_check_duplicates() call to run_all_checks() function
- Run for *.py and *.ts files only
- Update scripts/enforcement/__init__.py exports if needed

GATE:
python -m scripts.enforcement.validate_conventions --strict src/fabrik/scaffold.py

EVIDENCE REQUIRED:
- validate_conventions.py diff
- __init__.py diff (if changed)
- Test run output showing duplicates check runs

SELF-REVIEW (Builder):
- [ ] Import added correctly
- [ ] Integrated in run_all_checks()
- [ ] No regressions on other checks

PRE-FLIGHT GATES:
ruff check scripts/enforcement/ && pytest tests/test_enforcement.py -x

MODE 4 VERIFICATION:
- Verifier audits: Integration correct? No regressions?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Run Baseline and Document Existing Duplicates

```text
DO:
- Run jscpd on entire codebase: npx jscpd --reporters json > .jscpd-baseline.json
- Create docs/reference/duplicate-baseline.md with:
  - Current duplication percentage
  - List of identified clones
  - Categorization: intentional (templates/scaffolds) vs accidental
  - TODO list for refactoring high-priority duplicates

GATE:
test -f .jscpd-baseline.json && test -f docs/reference/duplicate-baseline.md

EVIDENCE REQUIRED:
- .jscpd-baseline.json exists
- duplicate-baseline.md content with categories

SELF-REVIEW (Builder):
- [ ] Documentation follows Fabrik standards
- [ ] Categories are clear (intentional vs accidental)
- [ ] Actionable TODOs for refactoring

MODE 4 VERIFICATION:
- Verifier audits: Clear? Complete? Actionable?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Create CI Workflow

```text
DO:
- Create .github/workflows/ci.yml (file does NOT exist)
- Use exact content from Section 3.D:
  - name: CI
  - triggers: push/PR to main
  - job: duplicate-check with actions/setup-node@v4
  - Node version pinned to '20'
  - Upload report as artifact

GATE:
yq . .github/workflows/ci.yml

EVIDENCE REQUIRED:
- ci.yml file content
- yq validation output (valid YAML)

SELF-REVIEW (Builder):
- [ ] YAML syntax valid
- [ ] Node.js version pinned (20)
- [ ] actions/setup-node@v4 used
- [ ] Artifact upload configured

PRE-FLIGHT GATES:
# Workflow syntax check (if actionlint available)
actionlint .github/workflows/ci.yml || echo "actionlint not available, skipping"

MODE 4 VERIFICATION:
- Verifier audits: Valid YAML? Correct actions versions? Will it pass?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 7 — Final Verification and Documentation

```text
DO:
- Run full pre-commit check: pre-commit run --all-files
- Update CHANGELOG.md with GAP-01 entry
- Update docs/TESTING.md with duplication section if it exists
- Verify canonical gate passes

GATE (CANONICAL):
pre-commit run jscpd --all-files && echo "PASS"

EVIDENCE REQUIRED:
- pre-commit run output (all hooks pass)
- CHANGELOG.md entry
- git diff --stat showing expected changes

SELF-REVIEW (Builder):
- [ ] All files created/updated
- [ ] CHANGELOG entry present
- [ ] Canonical gate passes

MODE 4 VERIFICATION (FINAL):
- Verifier audits: All gates pass? All docs updated? Ready to merge?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- jscpd cannot be installed (npm not available)
- Existing duplicates exceed 20% (need manual intervention first)
- pre-commit hook causes infinite loops or timeouts

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `.jscpd.json`, `check_duplicates.py`, `duplicate-baseline.md`, **`ci.yml`** |
| Files to MODIFY | `.pre-commit-config.yaml`, `validate_conventions.py`, `CHANGELOG.md` |
| Canonical Gate | `pre-commit run jscpd --all-files && echo "PASS"` |
| Exit Codes | 0=pass, 1=warn, 2=block |
| Threshold | 3% max duplication |

**All sections complete.** Ready for Mode 3 (Build) execution.
