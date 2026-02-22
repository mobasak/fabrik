# GAP-08 Property-Based Testing — Spec-Level Implementation Plan

**Version:** 1.1.0
**Revision Date:** 2026-02-17
**Status:** SPEC (not implementation)
**Compliance:** GAP-08 v1.0
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap08-property-testing.md`

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
| `pyproject.toml` | MODIFY | Add hypothesis>=6.100.0 | `python -c "import hypothesis"` |
| `tests/conftest.py` | MODIFY | Add Hypothesis profiles | `pytest --collect-only` |
| `tests/test_properties.py` | CREATE | Property tests | Canonical gate |
| `docs/reference/property-testing.md` | CREATE | Documentation | `test -f docs/reference/property-testing.md` |
| `CHANGELOG.md` | MODIFY | Document GAP-08 | Manual verify |

---

## Target Functions (Concrete Paths)

| Module | Function | Invariant |
|--------|----------|-----------|
| `scripts/droid_models.py` | `resolve_model(alias: str) -> str` | Output is always a valid model ID from config/models.yaml |
| `scripts/droid_models.py` | `get_models_for_scenario(scenario: str) -> list[str]` | Returns non-empty list for known scenarios |
| `src/fabrik/scaffold.py` | `sanitize_project_name(name: str) -> str` | Output contains only `[a-z0-9-]`, no leading/trailing hyphens |

---

## Test Profiles

**Canonical profile definition** (see Section 3.B for implementation):

| Profile | max_examples | deadline | Use Case |
|---------|--------------|----------|----------|
| `ci` | 100 | None | CI gates, explicit phase control |
| `dev` | 10 | 5000ms | Fast local feedback |
| `thorough` | 1000 | None | Nightly edge case hunting |

**Note:** Single definition in Section 3.B. Load via `HYPOTHESIS_PROFILE` env var.

---

## Determinism Controls

- **Seed handling:** Hypothesis auto-saves failing seeds to `.hypothesis/` database
- **Reproduce failures:** Run with `--hypothesis-seed=<seed>` from failure output
- **Flakiness controls:** `deadline` prevents timeout-based flakiness; `suppress_health_check` for slow-generating strategies

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

```
/opt/fabrik/
├── pyproject.toml              # Dependencies (EXISTS)
├── tests/
│   ├── __init__.py
│   ├── test_droid_core.py      # Existing tests
│   ├── test_enforcement.py
│   └── contracts/              # Contract tests exist
├── src/fabrik/
│   ├── scaffold.py             # Pure functions target
│   └── utils/                  # Utility functions
└── scripts/
    └── enforcement/            # Enforcement scripts
```

### B. GAP-08 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `pyproject.toml` | **FOUND** | Root | **MODIFY** — add hypothesis |
| `tests/` | **FOUND** | `tests/` | **MODIFY** — add property tests |
| `hypothesis` in deps | **NOT FOUND** | pyproject.toml | **ADD** to dev deps |
| `tests/test_properties.py` | **NOT FOUND** | `tests/` | **CREATE** required |
| Target functions | **FOUND** | Various | **VERIFY** — identify pure functions |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| hypothesis not installed | `pip install hypothesis` | Add to pyproject.toml |
| No pure functions found | Identify candidates in utils | Test enforcement scripts |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `pyproject.toml` | **MODIFY** | Add hypothesis dependency | Core deps | **S** (~3 lines) |
| `tests/test_properties.py` | **CREATE** | GAP-08 DONE WHEN: 3+ property tests | — | **M** (~100 lines) |
| `tests/conftest.py` | **MODIFY** | Add hypothesis settings | Existing fixtures | **S** (~10 lines) |
| `docs/reference/property-testing.md` | **CREATE** | Documentation | — | **M** (~60 lines) |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** |

**Explicitly NOT created/modified:**
- Source code in `src/` — Tests only
- Existing test files — Add new file only
- CI workflow — Property tests run with existing pytest

---

## 3. Interface & Contract Specification

### A. Target Functions (Pure Functions to Test)

| Module | Function | Invariant |
|--------|----------|-----------|
| `src/fabrik/scaffold.py` | `sanitize_project_name()` | Output is valid identifier |
| `scripts/droid_models.py` | `parse_model_name()` | Round-trip preserves name |
| `scripts/enforcement/check_env_vars.py` | `extract_env_vars()` | Finds all `os.getenv` calls |
| `scripts/droid_core.py` | `TaskType.from_string()` | Valid strings map correctly |

### B. Hypothesis Configuration

```python
# tests/conftest.py addition
from hypothesis import settings, Phase

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    phases=[Phase.generate, Phase.target, Phase.shrink],
)
settings.register_profile(
    "dev",
    max_examples=10,
    deadline=5000,
)
settings.load_profile("dev")  # Default to fast
```

### C. Property Test Pattern

```python
from hypothesis import given, strategies as st
from hypothesis import assume

@given(st.text(min_size=1, max_size=100))
def test_sanitize_project_name_produces_valid_identifier(name: str):
    """Property: sanitize_project_name always produces a valid Python identifier."""
    result = sanitize_project_name(name)
    # Property 1: Result is non-empty or raises
    assert len(result) > 0 or result == ""
    # Property 2: Result is valid identifier (if non-empty)
    if result:
        assert result.isidentifier() or result.replace("-", "_").isidentifier()
    # Property 3: Result doesn't start with number
    if result:
        assert not result[0].isdigit()
```

### D. pyproject.toml Addition

```toml
[project.optional-dependencies]
dev = [
    # ... existing deps ...
    "hypothesis>=6.100.0",
]

[tool.hypothesis]
database = ".hypothesis"
```

---

## 4. Golden Paths (2 Required)

### Golden Path 1: Run Property Tests

**Command:**
```bash
pytest tests/test_properties.py -v --hypothesis-show-statistics
```

**Expected output:**
```
tests/test_properties.py::test_sanitize_project_name_produces_valid_identifier PASSED
tests/test_properties.py::test_parse_model_name_roundtrip PASSED
tests/test_properties.py::test_extract_env_vars_finds_all PASSED

Hypothesis Statistics:
  - test_sanitize_project_name_produces_valid_identifier: 100 examples
  - test_parse_model_name_roundtrip: 100 examples
  - test_extract_env_vars_finds_all: 100 examples
```

**Expected exit code:** `0`

---

### Golden Path 2: Property Test Finds Bug

**Scenario:** Hypothesis generates edge case that reveals bug

**Command:**
```bash
pytest tests/test_properties.py::test_sanitize_project_name -v
```

**Expected output (if bug found):**
```
FAILED tests/test_properties.py::test_sanitize_project_name_produces_valid_identifier
Falsifying example: name='123abc'

AssertionError: Result '123abc' starts with digit
```

**Action:** Fix the bug, re-run to verify

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **hypothesis not installed** | ImportError | `pip install hypothesis` | None |
| 2 | **Property test too slow** | Timeout in CI | Reduce `max_examples` | Use "ci" profile |
| 3 | **Flaky test (non-deterministic)** | Random failures | Add `@seed` decorator | Fix randomness source |
| 4 | **No pure functions found** | No testable code | Test validators/parsers | Document limitation |
| 5 | **Shrinking takes too long** | CI timeout | Disable shrinking for CI | Adjust phases |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
pytest tests/test_properties.py -v --tb=short && \
python -c "import hypothesis; print(f'hypothesis {hypothesis.__version__}')" && \
echo "PASS"
```

**Expected PASS output:**
```
tests/test_properties.py::test_sanitize_project_name_produces_valid_identifier PASSED
tests/test_properties.py::test_parse_model_name_roundtrip PASSED
tests/test_properties.py::test_extract_env_vars_finds_all PASSED

3 passed
hypothesis 6.100.0
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
- [ ] Property clearly stated
- [ ] Invariant is valid
- [ ] Type hints complete

Pre-Flight Gates:
- ruff: PASS/FAIL
- mypy: PASS/FAIL
- pytest: PASS/FAIL

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
| CI pipeline | Property tests run with pytest |
| Dev dependencies | hypothesis added |
| `.hypothesis/` directory | Database for examples |

### Invariants (Hard Rules)

- **MUST test:** Pure functions only (no side effects)
- **MUST NOT modify:** Source code under test
- **MUST include:** At least 3 property tests
- **MUST configure:** Separate profiles for dev/CI

### Property Test Selection Criteria

```
┌─────────────────────────────────────────┐
│ Good Property Test Targets              │
├─────────────────────────────────────────┤
│ ✅ Pure functions (no side effects)     │
│ ✅ Parsers/validators                   │
│ ✅ Serialization round-trips            │
│ ✅ Mathematical invariants              │
│                                         │
│ ❌ Functions with I/O                   │
│ ❌ Database operations                  │
│ ❌ API calls                            │
│ ❌ File system operations               │
└─────────────────────────────────────────┘
```

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Add hypothesis to Dependencies

```text
DO:
- Add hypothesis>=6.100.0 to pyproject.toml under [project.optional-dependencies] dev
- Run pip install -e ".[dev]" to install
- Verify import works

GATE:
python -c "import hypothesis; print(hypothesis.__version__)"

EVIDENCE REQUIRED:
- hypothesis version printed (6.100.0+)
- No import errors

SELF-REVIEW (Builder):
- [ ] Version pinned appropriately (>=6.100.0)
- [ ] Added to dev dependencies (not main)
- [ ] Installation successful

PRE-FLIGHT GATES:
ruff check . && mypy .

MODE 4 VERIFICATION:
- Verifier audits: Dependency correct? Version appropriate?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Configure Hypothesis Profiles

```text
DO:
- Add hypothesis settings to tests/conftest.py
- Create profiles:
  - "ci": max_examples=100, deadline=timedelta(seconds=1)
  - "dev": max_examples=50, deadline=timedelta(seconds=0.5)
  - "thorough": max_examples=1000 (for edge case hunting)
- Use @settings(profile="ci") or load from env var

GATE:
pytest --collect-only 2>&1 | grep "conftest.py"

EVIDENCE REQUIRED:
- conftest.py updated with hypothesis settings
- Profiles defined

SELF-REVIEW (Builder):
- [ ] CI profile has enough examples (100+)
- [ ] Dev profile is fast for local testing
- [ ] Deadline prevents hanging tests

PRE-FLIGHT GATES:
ruff check tests/conftest.py && mypy tests/conftest.py

MODE 4 VERIFICATION:
- Verifier audits: Profiles appropriate? Settings correct?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Identify Target Functions

```text
DO:
- Scan codebase for pure functions (no side effects)
- Select 3+ functions from Section 3.A target list:
  - droid_models.py: resolve_model(), get_models_for_scenario()
  - scaffold.py: sanitize_project_name(), validate_project_path()
  - config parsing functions
- Document invariants for each:
  - What must always be true about the output?
  - What relationships must hold?

GATE:
echo "3+ target functions with invariants documented"

EVIDENCE REQUIRED:
- List of target functions
- Invariant for each function

SELF-REVIEW (Builder):
- [ ] Functions are truly pure (no I/O, no global state)
- [ ] Invariants are meaningful (not trivial)
- [ ] Functions are representative of codebase

MODE 4 VERIFICATION:
- Verifier audits: Functions pure? Invariants meaningful?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create Property Tests

```text
DO:
- Create tests/test_properties.py
- Implement 3+ property tests following pattern from Section 3.C:
  - @given(st.text()) for string inputs
  - @given(st.integers(min_value=0)) for numeric inputs
  - @given(st.lists(st.text())) for collection inputs
- Each test should assert an invariant
- Use assume() to filter invalid inputs

GATE:
pytest tests/test_properties.py -v --hypothesis-show-statistics

EVIDENCE REQUIRED:
- test_properties.py exists
- 3+ property tests pass
- Statistics show examples generated

SELF-REVIEW (Builder):
- [ ] Properties test meaningful invariants
- [ ] assume() used appropriately (not over-filtering)
- [ ] Tests don't trivially pass
- [ ] No side effects in tests

PRE-FLIGHT GATES:
ruff check tests/test_properties.py && mypy tests/test_properties.py

MODE 4 VERIFICATION:
- Verifier audits: Properties meaningful? Tests robust?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Create Documentation

```text
DO:
- Create docs/reference/property-testing.md
- Document:
  - What is property-based testing?
  - When to use it (pure functions, parsers, serializers)
  - Hypothesis patterns (strategies, given, assume, settings)
  - Example test from test_properties.py
  - Target functions and their invariants
  - CI vs dev profiles

GATE:
test -f docs/reference/property-testing.md && grep "@given" docs/reference/property-testing.md

EVIDENCE REQUIRED:
- property-testing.md exists
- Contains example with @given

SELF-REVIEW (Builder):
- [ ] Clear explanation of property testing
- [ ] Practical examples included
- [ ] Patterns are reusable
- [ ] Follows Fabrik doc standards

MODE 4 VERIFICATION:
- Verifier audits: Documentation clear? Examples useful?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Final Verification

```text
DO:
- Run full test suite: pytest tests/ -v
- Run property tests with statistics: pytest tests/test_properties.py --hypothesis-show-statistics
- Update CHANGELOG.md with GAP-08 entry

GATE (CANONICAL):
pytest tests/test_properties.py -v && \
python -c "import hypothesis; assert hypothesis.__version__ >= '6.100.0'" && \
echo "PASS"

EVIDENCE REQUIRED:
- All property tests pass
- Statistics show meaningful example counts
- CHANGELOG updated

SELF-REVIEW (Builder):
- [ ] 3+ property tests implemented and passing
- [ ] hypothesis installed correctly
- [ ] Documentation complete

MODE 4 VERIFICATION (FINAL):
- Verifier audits: Tests pass? Documentation complete? Ready to use?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- hypothesis cannot be installed (dependency conflict)
- No pure functions found in codebase (unlikely)
- Property tests consistently timeout

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `test_properties.py`, `property-testing.md` |
| Files to MODIFY | `pyproject.toml`, `conftest.py`, `CHANGELOG.md` |
| Dependency | `hypothesis>=6.100.0` |
| Canonical Gate | 3+ property tests pass |
| Minimum tests | 3 property tests with clear invariants |

**All sections complete.** Ready for Mode 3 (Build) execution.
