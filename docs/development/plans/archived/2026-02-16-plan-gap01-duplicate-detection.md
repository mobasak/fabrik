# 2026-02-16-plan-gap01-duplicate-detection

**Status:** NOT_STARTED
**Created:** 2026-02-16
**Priority:** P0 (Critical)
**Estimated Effort:** 2-4 hours
**Source:** Research document "Optimizing Workflows Across AI Coding Platforms"

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-01 Duplicate Detection only
NEXT REQUIRED: Mode 4 — Verify with Factory Droid after each step

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope (spec freeze)
- One step at a time
- After each step: show Evidence + Gate result
- After each step: Mode 4 verification (see VERIFICATION section)
- If a Gate fails → STOP and report
- Maintain same session ID throughout execution (context preservation)

ROLE SEPARATION:
- Builder (Cascade/You): Implements code, runs self-review
- Verifier (Factory Droid): Independent audit, approves changes
- Rule: "Verifier never fixes. Builder never self-verifies."
```

---

## TASK METADATA

```text
TASK:
Add jscpd duplicate detection to pre-commit and CI

GOAL:
Prevent AI agents from re-implementing existing functionality by detecting code clones before commit.

DONE WHEN (all true):
- [ ] jscpd runs on pre-commit for Python/TypeScript files
- [ ] jscpd runs in CI pipeline
- [ ] Threshold configured (max 3% duplication)
- [ ] Existing duplicates documented or refactored
- [ ] Gate command passes: pre-commit run jscpd --all-files

OUT OF SCOPE:
- Refactoring all existing duplicates (only document)
- PMD CPD (using jscpd only for simplicity)
- Custom Semgrep rules (separate gap)
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Tool: jscpd (npm package, works for Python/TS/JS)
- No new Python deps (jscpd is npm-based, run via npx)
- Follow existing pre-commit patterns in .pre-commit-config.yaml
- Backward compatibility: yes (warning mode first, then blocking)

SESSION MANAGEMENT:
- Start: droid exec -m gpt-5.3-codex "Start GAP-01" (captures session_id)
- Continue: droid exec --session-id <id> "Next step..." (preserves context)
- WARNING: Changing models mid-session loses context
- If model change required: Document context summary before switch

MODEL ASSIGNMENTS (from config/models.yaml):
- Execution: swe-1-5 or gpt-5.1-codex (Stage 3 - Build)
- Verification: gpt-5.3-codex (Stage 4 - Verify)
- Documentation: claude-haiku-4-5 (Stage 5 - Ship)
```

---

## EXISTING INFRASTRUCTURE (avoid duplication)

| Component | Location | Status |
|-----------|----------|--------|
| Pre-commit config | `.pre-commit-config.yaml` | 12 hooks exist |
| Enforcement scripts | `scripts/enforcement/` | 15 scripts exist |
| CI pipeline | `.github/workflows/` | Exists |
| Code quality | ruff, mypy, bandit | Already integrated |

**Key insight:** Add jscpd as a local hook (like `fabrik-conventions`) to avoid npm dependency issues.

---

## CANONICAL GATE

```text
CANONICAL GATE:
pre-commit run jscpd --all-files && echo "PASS"
```

---

## EXECUTION STEPS

### Step 1 — Install and Configure jscpd

```text
DO:
- Create .jscpd.json config file at repo root
- Configure thresholds:
  - minLines: 10 (minimum clone size)
  - minTokens: 50 (minimum token count)
  - threshold: 3 (max 3% duplication)
- Include: src/, scripts/, templates/
- Exclude: node_modules, .venv, __pycache__, .next

GATE:
- npx jscpd --version succeeds
- .jscpd.json is valid JSON

EVIDENCE REQUIRED:
- .jscpd.json file content
- jscpd version output

SELF-REVIEW (Builder):
- Check: File follows Fabrik patterns
- Check: No hardcoded values

PRE-FLIGHT GATES (run BEFORE AI verification):
- ruff check . && mypy . (must pass before LLM verification)

MODE 4 VERIFICATION (Verifier - Factory Droid):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit .jscpd.json: Does it follow Fabrik conventions? List issues as JSON."
- If issues found → Builder fixes → Re-verify
- MAX RE-VERIFY: 2 iterations, then escalate to human or second verifier
- Only proceed when: "issues": []
```

---

### Step 2 — Add Pre-commit Hook

```text
DO:
- Add jscpd hook to .pre-commit-config.yaml
- Use local hook with npx (no repo dependency)
- Configure to run on: *.py, *.ts, *.tsx, *.js
- Set pass_filenames: false (jscpd scans directories)

GATE:
- pre-commit run jscpd --all-files (may have warnings initially)

EVIDENCE REQUIRED:
- .pre-commit-config.yaml diff
- pre-commit run output

SELF-REVIEW (Builder):
- Check: Hook syntax matches existing patterns
- Check: pass_filenames correctly set

PRE-FLIGHT GATES:
- ruff check . && mypy . (must pass)

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit pre-commit hook: Correct syntax? Follows patterns? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create Enforcement Script Wrapper

```text
DO:
- Create scripts/enforcement/check_duplicates.py
- Wrapper that calls jscpd with JSON output
- Parse results and return CheckResult objects
- Follow existing check_*.py patterns (see check_secrets.py)
- Exit codes: 0=pass, 1=warn, 2=block

GATE:
- python -m scripts.enforcement.check_duplicates src/ succeeds

EVIDENCE REQUIRED:
- check_duplicates.py content
- Test run output

SELF-REVIEW (Builder):
- Check: Type annotations on all functions
- Check: Follows check_*.py patterns
- Check: Returns CheckResult objects

PRE-FLIGHT GATES:
- ruff check scripts/enforcement/check_duplicates.py && mypy scripts/enforcement/check_duplicates.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit check_duplicates.py: Type hints? Pattern compliance? Security issues?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Integrate with validate_conventions.py

```text
DO:
- Add run_check_duplicates() to validate_conventions.py
- Import from check_duplicates module
- Add to run_all_checks() for *.py and *.ts files
- Update __init__.py if needed

GATE:
- python -m scripts.enforcement.validate_conventions --strict src/fabrik/scaffold.py

EVIDENCE REQUIRED:
- validate_conventions.py diff
- Test run output

SELF-REVIEW (Builder):
- Check: Import added correctly
- Check: Integrated in run_all_checks()

PRE-FLIGHT GATES:
- ruff check scripts/enforcement/ && pytest tests/test_enforcement.py -x

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit validate_conventions.py changes: Integration correct? No regressions?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Run Baseline and Document Existing Duplicates

```text
DO:
- Run jscpd on entire codebase
- Document existing duplicates in docs/reference/duplicate-baseline.md
- Categorize: intentional (templates) vs accidental
- Create TODO list for refactoring high-priority duplicates

GATE:
- npx jscpd --reporters json > .jscpd-baseline.json
- docs/reference/duplicate-baseline.md exists

EVIDENCE REQUIRED:
- Baseline report summary
- duplicate-baseline.md content

SELF-REVIEW (Builder):
- Check: Documentation follows Fabrik standards
- Check: Categories are clear

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit duplicate-baseline.md: Clear? Complete? Actionable?"
- If issues → fix → re-verify
```

---

### Step 6 — Add CI Integration

```text
DO:
- Add jscpd step to .github/workflows/ci.yml (or create if not exists)
- Run after lint, before tests
- Fail CI if threshold exceeded
- Upload report as artifact

GATE:
- YAML is valid: yq . .github/workflows/ci.yml
- CI step syntax correct

EVIDENCE REQUIRED:
- CI workflow diff
- Gate output

SELF-REVIEW (Builder):
- Check: YAML syntax valid
- Check: Step order correct (after lint, before tests)

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit CI workflow: Valid YAML? Correct ordering? Will it pass?"
- If issues → fix → re-verify
```

---

### Step 7 — Final Verification and Documentation

```text
DO:
- Run full pre-commit check
- Update CHANGELOG.md
- Update docs/TESTING.md with duplication section
- Add to AGENTS.md if needed

GATE:
- pre-commit run --all-files passes
- git diff --stat shows expected changes

EVIDENCE REQUIRED:
- pre-commit run output
- CHANGELOG.md entry

SELF-REVIEW (Builder):
- Check: All files updated
- Check: CHANGELOG entry present

MODE 4 VERIFICATION (Verifier - FINAL):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Final audit GAP-01: All gates pass? All docs updated? Ready to merge?"
- Must return: {"ready": true, "issues": []}
```

---

## STOP CONDITIONS

```text
STOP IF:
- jscpd cannot be installed (npm not available)
- Existing duplicates exceed 20% (need manual intervention)
- pre-commit hook causes infinite loops

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Prevent code bloat | -20% redundant code commits |
| Catch copy-paste drift | Early detection before bugs spread |
| Reduce review cycles | "We already have this" feedback eliminated |
| Lower token costs | Smaller codebase = less context needed |

---

## REPORTING FORMAT (strict)

After **every step**, the agent must output:

```text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [x] Check 1 passed
- [x] Check 2 passed

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

---

## SESSION MANAGEMENT

```text
SESSION RULES:
1. Start execution session: droid exec -m swe-1-5 "Begin GAP-01 Step 1"
2. Capture session_id from response
3. Continue with: droid exec --session-id <id> "Step 2..."
4. Verification uses SEPARATE session (Verifier independence)
5. If model change needed: Start new session, summarize context first
6. Document session_id in each step report

WHY THIS MATTERS:
- Same session = AI remembers previous steps
- Different model = context lost (new session auto-created)
- Provider switch (OpenAI↔Anthropic) = full context reset
```
