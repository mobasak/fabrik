# 2026-02-16-plan-gap08-property-testing

**Status:** NOT_STARTED
**Created:** 2026-02-16
**Priority:** P2 (Medium)
**Estimated Effort:** 6-8 hours (MVP: 4h, expansion: 2-4h)
**Source:** Research document "Optimizing Workflows Across AI Coding Platforms"

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-08 Property-Based Testing only
NEXT REQUIRED: Mode 4 — Verify with Factory Droid after each step

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope (spec freeze)
- One step at a time
- After each step: show Evidence + Gate result
- After each step: Mode 4 verification
- If a Gate fails → STOP and report
- Maintain same session ID throughout execution

ROLE SEPARATION:
- Builder (Cascade/You): Implements code, runs self-review
- Verifier (Factory Droid): Independent audit, approves changes
- Rule: "Verifier never fixes. Builder never self-verifies."
```

---

## TASK METADATA

```text
TASK:
Add Hypothesis property-based testing to Fabrik test suite

GOAL:
Catch edge cases that AI-generated code often misses (empty lists, nulls, boundary values) through automatic test case generation.

DONE WHEN (all true):
- [ ] hypothesis installed as dev dependency
- [ ] At least 3 property-based tests added
- [ ] Tests integrated with existing pytest suite
- [ ] Documentation updated
- [ ] Gate command passes: test $(pytest tests/ -v -k "property" --co 2>/dev/null | grep -c "test_") -ge 3

OUT OF SCOPE:
- Mutation testing (mutmut/Stryker)
- Converting all existing tests to property-based
- Hypothesis profiles for CI optimization
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Library: hypothesis (Python)
- Integration: pytest plugin (pytest-hypothesis)
- Location: tests/ directory, follow existing patterns
- No breaking existing tests
- Type annotations required for strategies
- Dependencies: pyproject.toml [project.optional-dependencies].dev (NOT requirements-dev.txt)
- Focus: Pure utility functions first (avoid stateful/time-dependent initially)
- Invariants: Bounded (define expected false-positive/negative limits)

SESSION MANAGEMENT:
- Start: droid exec -m swe-1-5 "Start GAP-08" (captures session_id)
- Continue: droid exec --session-id <id> "Next step..."
- WARNING: Changing models mid-session loses context
- Verification uses SEPARATE session (Verifier independence)

MODEL ASSIGNMENTS (from config/models.yaml):
- Execution: swe-1-5 or gpt-5.1-codex (Stage 3 - Build)
- Verification: gpt-5.3-codex (Stage 4 - Verify)
- Documentation: claude-haiku-4-5 (Stage 5 - Ship)
```

---

## EXISTING INFRASTRUCTURE (integrate with)

| Component | Location | Status |
|-----------|----------|--------|
| Test suite | `tests/` | pytest-based |
| Test config | `pyproject.toml` | pytest config exists |
| CI pipeline | `.github/workflows/` | Runs pytest |
| Pre-commit | `.pre-commit-config.yaml` | Runs tests |
| Docs | `docs/TESTING.md` | Testing guide |

**Key insight:** Add hypothesis as optional testing tool, not replacement.

---

## CANONICAL GATE

```text
CANONICAL GATE:
pytest tests/ -v -k "property" && echo "PASS"
```

---

## EXECUTION STEPS

### Step 1 — Install Hypothesis

```text
DO:
- Add hypothesis to pyproject.toml [project.optional-dependencies].dev
- Example: dev = ["hypothesis>=6.100.0", ...]
- Install: pip install -e ".[dev]"
- Verify installation: python -c "import hypothesis; print(hypothesis.__version__)"

GATE:
- python -c "import hypothesis; print('OK')"
- grep -q "hypothesis" pyproject.toml

EVIDENCE REQUIRED:
- pyproject.toml diff showing [project.optional-dependencies].dev
- Import test output

PRE-FLIGHT GATES:
- python -c "import hypothesis; print('OK')"

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit hypothesis installation: Correct? Dependencies? List issues as JSON."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Create Property Test for scaffold.py

```text
DO:
- Create tests/test_scaffold_property.py
- Test: _validate_project_name() (NOTE: private function, import from fabrik.scaffold)
- Import: from fabrik.scaffold import _validate_project_name, RESERVED_NAMES
- Properties to verify:
  - Valid alphanumeric names (matching ^[a-z][a-z0-9-]*$) pass
  - Names in RESERVED_NAMES raise ValueError
  - Empty strings raise ValueError
  - Names starting with digit raise ValueError
- Use hypothesis.strategies.from_regex for valid name generation

GATE:
- pytest tests/test_scaffold_property.py -v

EVIDENCE REQUIRED:
- test_scaffold_property.py content
- Test run output

PRE-FLIGHT GATES:
- ruff check tests/test_scaffold_property.py && mypy tests/test_scaffold_property.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit scaffold property tests: Correct properties? Coverage? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create Property Test for Pure Utility Functions

```text
DO:
- Create tests/test_utils_property.py
- Focus on PURE functions only (no I/O, no time, no filesystem)
- Target functions:
  - Model name validation from config/models.yaml parsing
  - CheckResult construction and severity validation
  - Any pure string/data transformation utilities
- Avoid: droid_session.py (stateful, time-dependent, filesystem I/O)

Properties to verify:
  - CheckResult severity is always in ['pass', 'warn', 'error']
  - Model config parsing handles missing keys gracefully
  - String transformations are idempotent where expected

GATE:
- pytest tests/test_utils_property.py -v

EVIDENCE REQUIRED:
- test_utils_property.py content
- Test run output

PRE-FLIGHT GATES:
- ruff check tests/test_utils_property.py && mypy tests/test_utils_property.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit utils property tests: Pure functions only? Coverage? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create Property Test for enforcement checks

```text
DO:
- Create tests/test_enforcement_property.py
- Test check functions with arbitrary inputs
- BOUNDED INVARIANTS (realistic, not absolute):
  - check_env_vars: detects 'localhost', '127.0.0.1' in obvious contexts (>95% recall)
  - check_secrets: catches KNOWN_WEAK_PASSWORDS list (100% recall on known set)
  - False positive rate: <10% on random alphanumeric strings
  - CheckResult severity always in allowed set
- Use hypothesis.strategies.text, sampled_from, from_regex

NOTE: Regex-based checks have inherent limits. Test known patterns, not "always".

GATE:
- pytest tests/test_enforcement_property.py -v

EVIDENCE REQUIRED:
- test_enforcement_property.py content
- Test run output with recall/precision notes

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review enforcement property tests for bounded claims"
- droid exec -m gemini-3-pro-preview "Review security test coverage"
```

---

### Step 5 — Configure Hypothesis Settings

```text
DO:
- Add hypothesis profile to conftest.py or pyproject.toml
- Configure:
  - Default: 100 examples (local development)
  - CI: 500 examples (thorough)
  - Quick: 10 examples (pre-commit)
- Add suppress_health_check for slow tests

Configuration in pyproject.toml:
[tool.hypothesis]
deadline = 500
max_examples = 100

GATE:
- pytest tests/ -v -k "property" --hypothesis-show-statistics

EVIDENCE REQUIRED:
- Configuration content
- Statistics output

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review Hypothesis configuration"
- droid exec -m gemini-3-pro-preview "Review CI performance settings"
```

---

### Step 6 — Update Documentation

```text
DO:
- Add property testing section to docs/TESTING.md
- Include:
  - When to use property tests
  - How to write strategies
  - Example patterns
  - Running with different profiles
- Update CHANGELOG.md

GATE:
- test $(grep -c "hypothesis\|property" docs/TESTING.md) -ge 3

EVIDENCE REQUIRED:
- docs/TESTING.md diff
- CHANGELOG entry

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review testing documentation"
- droid exec -m gemini-3-pro-preview "Review documentation clarity"
```

---

### Step 7 — Final Verification

```text
DO:
- Run full test suite including property tests
- Verify no regressions
- Verify CI compatibility
- Document any found bugs (property tests often find edge cases!)

GATE:
- pytest tests/ -v (all tests pass)
- test $(pytest tests/ -v -k "property" --co 2>/dev/null | grep -c "test_") -ge 3

EVIDENCE REQUIRED:
- Full test run output
- Property test count
- Any bugs found (create issues)

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Final review of property testing"
- droid exec -m gemini-3-pro-preview "Final review of test quality"
```

---

## STOP CONDITIONS

```text
STOP IF:
- Hypothesis conflicts with existing test setup
- Property tests cause CI timeout (> 10 min)
- Critical bugs found that need immediate fix

ON STOP:
- Report exact blocker
- If bugs found: create GitHub issue, continue with plan
- Propose at most 2 resolution options
```

---

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Edge case detection | Find bugs AI-generated code misses |
| Self-documenting | Properties describe invariants |
| Reduced manual work | 100s of test cases auto-generated |
| Regression prevention | Shrinking finds minimal failing case |

---

## PROPERTY TEST PATTERNS

### Pattern 1: Round-trip
```python
@given(st.text())
def test_roundtrip(s):
    assert decode(encode(s)) == s
```

### Pattern 2: Invariant
```python
@given(st.lists(st.integers()))
def test_sort_invariant(lst):
    result = sorted(lst)
    assert len(result) == len(lst)
    assert all(a <= b for a, b in zip(result, result[1:]))
```

### Pattern 3: Oracle
```python
@given(st.integers(), st.integers())
def test_against_oracle(a, b):
    assert fast_add(a, b) == slow_but_correct_add(a, b)
```

---

## COMMON STRATEGIES

| Strategy | Use For |
|----------|---------|
| `st.text()` | String inputs |
| `st.integers()` | Numeric inputs |
| `st.lists(st.X())` | List of X |
| `st.none() \| st.X()` | Optional X |
| `st.sampled_from([...])` | Enum-like |
| `st.builds(Class)` | Object construction |

---

## REPORTING FORMAT (strict)

After **every step**, the agent must output:

```text
STEP <N> STATUS: PASS / FAIL

Changed files:
- <path>

Gate output:
<pasted output>

Code Review (GPT-5.3):
<summary of findings>

Code Review (Gemini Pro):
<summary of findings>

Next:
- Proceed to Step <N+1> OR STOP
```
