# Kilo Strictness - Code Changes Summary

**CRITICAL FAILURE POINTS TO AVOID:**

1. **parse_review_output MUST NOT auto-fill** - Current code defaults missing fields → defeats gating
2. **Evidence policy split is INTENTIONAL** - Schema enforces all, validator quality-checks BLOCKER/MAJOR only
3. **Token accounting MUST sum all attempts** - Not just final call
4. **Plan coverage MUST be persisted** - Add to iteration_data dict

---

## Files Modified

### 1. `/opt/fabrik/requirements.txt`
**Add:** `jsonschema>=4.17.0`

### 2. `/opt/fabrik/scripts/kilo_code_review.py`

**Line ~44 - Add imports:**
```python
from dataclasses import replace
import jsonschema
from jsonschema import Draft7Validator
```

**Line ~193 - ReviewIssue dataclass:**
Add field: `evidence: dict[str, Any] | None = None`

**Line ~209 - ReviewResult dataclass:**
Add field: `plan_coverage: list[dict[str, Any]] = field(default_factory=list)`

**Line ~110 - After constants, add:**
- `REVIEW_RESULT_SCHEMA` (full JSON schema)
- `REVIEW_SCHEMA_VALIDATOR = Draft7Validator(REVIEW_RESULT_SCHEMA)`
- `validate_review_schema(data) -> (bool, list[str])`
- `extract_plan_requirements(plan_text) -> list[dict]`
- `format_requirements_for_prompt(requirements) -> str`

**Line ~2456 - Replace parse_review_output() (CRITICAL - NO AUTO-FILL):**
- Pure sync function (no asyncio.run)
- **NO auto-fill of missing fields** (current code silently defaults verdict/summary/issues)
- Returns ReviewResult with <reviewer> BLOCKER if schema fails
- NO fallbacks, NO assumptions - hard fail on invalid schema

**After parse_review_output, add:**
- `validate_evidence(issues) -> (bool, list[str])`
- `validate_plan_coverage(requirements, coverage) -> (bool, list[str])`
- `run_pre_review_gates() -> dict` (renamed from run_final_gate)
- `format_gate_results_compact(gate_data) -> str`

**Line ~1805 - Replace REVIEW_PROMPT_TEMPLATE:**
- Add `{gate_results}` placeholder
- Add enforcement warnings
- Add evidence/coverage rules

**Line ~2640 - Replace _run_single_batch_review() (ALL CORRECTIONS):**

**CRITICAL CHANGES:**
1. Track `attempt_results = []` for accurate token accounting
2. Run gates and inject via `{gate_results}` placeholder
3. Safe gate write (check SESSION_DIR exists)
4. Retry includes complete JSON skeleton
5. Sum tokens/cost from ALL attempts (not just final call)

Key implementation:
```python
# Track ALL attempts for accurate cost accounting
attempt_results = []

# Extract requirements
plan_requirements = extract_plan_requirements(config.traycer_plan or "")
requirements_section = format_requirements_for_prompt(plan_requirements)

# Run gates (fault-tolerant)
gate_data = run_pre_review_gates()
gate_results_str = format_gate_results_compact(gate_data)

# Safe gate write (check SESSION_DIR exists)
if hasattr(config, 'session_id') and config.session_id:
    try:
        gate_log_dir = SESSION_DIR if 'SESSION_DIR' in globals() else Path(".droid/reviews")
        gate_log_dir.mkdir(parents=True, exist_ok=True)
        if gate_data.get("raw_output"):  # Only write if output exists
            (gate_log_dir / "gate_output.txt").write_text(gate_data["raw_output"])
    except Exception as e:
        print(f"⚠️  Could not save gate output: {e}", file=sys.stderr)

# Build prompt with gate_results
prompt = REVIEW_PROMPT_TEMPLATE.format(
    gate_results=gate_results_str,  # INJECTED
    requirements_section=requirements_section,
    # ... other fields
)

# Attempt 1
result = await run_kilo(prompt, ...)
attempt_results.append(result)

# Parse strict (NO auto-fill)
review_result = parse_review_output(result["result"])

# Retry with JSON skeleton if schema failed
if schema_failed:
    retry_prompt = """... complete JSON skeleton with all required fields ..."""
    retry_result = await run_kilo(retry_prompt, ...)
    attempt_results.append(retry_result)
    review_result = parse_review_output(retry_result["result"])

# Validate evidence (BLOCKER/MAJOR only)
if not any(i.file == "<reviewer>" for i in review_result.issues):
    evidence_valid, evidence_violations = validate_evidence(review_result.issues)
    if not evidence_valid:
        # Insert <reviewer> BLOCKER
        review_result.verdict = "FAIL"
        review_result.issues.insert(0, ...)
    else:
        # Validate plan coverage
        coverage_valid, coverage_violations = validate_plan_coverage(...)
        if not coverage_valid:
            # Insert <reviewer> BLOCKER
            review_result.verdict = "FAIL"
            review_result.issues.insert(0, ...)

# Sum tokens/cost from ALL attempts
total_input_tokens = sum(r.get("input_tokens", 0) for r in attempt_results)
total_output_tokens = sum(r.get("output_tokens", 0) for r in attempt_results)
total_cost = sum(r.get("cost", 0.0) for r in attempt_results)

review_result.input_tokens = total_input_tokens
review_result.output_tokens = total_output_tokens
review_result.cost = total_cost
review_result.stats["attempts"] = len(attempt_results)
if len(attempt_results) > 1:
    review_result.stats["retried"] = True
```

**After _run_single_batch_review, add:**
- `assess_review_risk(files, diff_content) -> dict`
- `run_multi_pass_review(...) -> ReviewResult` (uses dataclasses.replace)

**Update run_review():**
```python
async def run_review(...):
    risk = assess_review_risk(files, diff_content)
    if risk["requires_multi_pass"]:
        return await run_multi_pass_review(...)
    return await _run_single_batch_review(...)
```

**Line ~2800 - Update iteration save:**
Add: `"plan_coverage": result.plan_coverage,`

### 3. `/opt/fabrik/tests/test_kilo_review_validation.py` (NEW)

**Create pytest-style tests:**
```python
from scripts.kilo_code_review import (
    validate_review_schema,
    validate_evidence,
    validate_plan_coverage,
    extract_plan_requirements,
    ReviewIssue,
)

def test_schema_valid_minimal(): ...
def test_schema_missing_required(): ...
def test_evidence_blocker_valid(): ...
def test_evidence_blocker_missing(): ...
def test_coverage_complete(): ...
def test_coverage_missing(): ...
def test_extract_numbered(): ...
def test_extract_explicit(): ...
# ... 14 tests total
```

Run: `pytest tests/test_kilo_review_validation.py -v`

## Key Corrections Applied

1. **Async-safe retry** - No asyncio.run in parse
2. **Token accounting** - Track all attempts, sum costs
3. **Safe gate write** - Check SESSION_DIR exists
4. **Config copy** - Use dataclasses.replace
5. **Pytest format** - Standard discovery
6. **Evidence policy** - Schema enforces all, validator checks quality for BLOCKER/MAJOR

## Testing

```bash
# Install
pip install -r requirements.txt

# Run tests
pytest tests/test_kilo_review_validation.py -v

# Real review
python scripts/kilo_code_review.py review src/file.py \
  --plan "Task description" \
  --output json
```
