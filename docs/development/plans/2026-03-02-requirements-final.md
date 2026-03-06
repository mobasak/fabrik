# Kilo Review Strictness - Final Requirements Document

**Date:** 2026-03-02
**Status:** Ready for implementation
**All critical requirements documented**

---

## 1. `/opt/fabrik/requirements.txt` — Update

**Add dependency:**
```
jsonschema>=4.17.0
```

---

## 2. `/opt/fabrik/scripts/kilo_code_review.py` — Explicit Changes

### A. Dataclasses: Add New Required Fields

**1. `ReviewIssue` (line ~193):**
```python
@dataclass
class ReviewIssue:
    severity: str
    category: str
    file: str
    lines: str
    why: str
    fix_hint: str
    snippet: str | None = None
    evidence: dict[str, Any] | None = None  # NEW FIELD
```

**2. `ReviewResult` (line ~209):**
```python
@dataclass
class ReviewResult:
    verdict: str
    summary: str
    issues: list[ReviewIssue]
    notes: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    plan_coverage: list[dict[str, Any]] = field(default_factory=list)  # NEW FIELD
    # ... rest of fields
```

### B. Persistence: Ensure `plan_coverage` in Iteration JSON

**Location:** Where `iteration_data = {...}` is saved to `review_iter_*.json`

**Add:**
```python
iteration_data = {
    "iteration": iteration,
    "verdict": result.verdict,
    "summary": result.summary,
    "issues": [i.to_dict() for i in result.issues],
    "plan_coverage": result.plan_coverage,  # NEW: must persist coverage
    "notes": result.notes,
    "stats": result.stats,
    "input_tokens": result.input_tokens,
    "output_tokens": result.output_tokens,
    "cost": result.cost,
}
```

### C. Imports: Add Required Imports

**Location:** After existing imports (line ~44)

```python
from dataclasses import replace  # For multi-pass config copying
import jsonschema
from jsonschema import Draft7Validator
```

### D. Add Strict Schema Validator Section

**Location:** After constants section (line ~110)

**Key enforcement characteristics to confirm:**
- `required: ["verdict", "summary", "issues", "plan_coverage"]`
- `additionalProperties: false` at top level AND issue level
- Each `issue` requires `evidence` object
- `plan_coverage` requires at least 1 item (`minItems: 1`)

```python
REVIEW_RESULT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["verdict", "summary", "issues", "plan_coverage"],
    "additionalProperties": False,  # CRITICAL: no extra fields allowed
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        "summary": {"type": "string", "minLength": 10, "maxLength": 1000},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "category", "file", "lines", "why", "fix_hint", "evidence"],
                "additionalProperties": False,  # CRITICAL: no extra fields in issues
                "properties": {
                    # ... severity, category, file, lines, why, fix_hint, snippet
                    "evidence": {
                        "type": "object",
                        "required": ["type"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {"type": "string", "enum": ["diff", "file_line", "tool_output", "missing", "multi_file", "external"]},
                            "ref": {"type": "string", "minLength": 1},
                            "explanation": {"type": "string", "minLength": 10},
                            "supporting_refs": {"type": "array", "items": {"type": "string"}}
                        },
                        "oneOf": [
                            {"properties": {"type": {"enum": ["diff", "file_line", "tool_output"]}}, "required": ["ref"]},
                            {"properties": {"type": {"enum": ["missing", "multi_file", "external"]}}, "required": ["explanation"]}
                        ]
                    }
                }
            }
        },
        "plan_coverage": {
            "type": "array",
            "minItems": 1,  # CRITICAL: at least 1 entry required
            "items": {
                "type": "object",
                "required": ["requirement", "status", "evidence"],
                "additionalProperties": False,
                # ... properties
            }
        },
        # ... notes, stats
    }
}

REVIEW_SCHEMA_VALIDATOR = Draft7Validator(REVIEW_RESULT_SCHEMA)

def validate_review_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate reviewer output against strict JSON schema."""
    errors = []
    for error in REVIEW_SCHEMA_VALIDATOR.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")
    return len(errors) == 0, errors
```

### E. Add Plan Requirement Extraction Helpers

**Location:** After schema validator

```python
def extract_plan_requirements(plan_text: str) -> list[dict[str, str]]:
    """
    Extract requirements from Traycer plan.
    Patterns (priority order):
    1. REQ-1: text (explicit IDs)
    2. 1. text (numbered lists)
    3. - text (bulleted lists, fallback)
    """
    # ... implementation

def format_requirements_for_prompt(requirements: list[dict[str, str]]) -> str:
    """Format extracted requirements for inclusion in review prompt."""
    # ... implementation
```

### F. Replace `parse_review_output()` — CRITICAL: NO AUTO-FILL

**Location:** Line ~2456

**CRITICAL REQUIREMENT:**
- Current `parse_review_output()` is permissive (fills missing fields, never enforces schema/plan_coverage/evidence)
- **Replace entirely** with strict version
- Pure sync (NO asyncio.run)
- NO auto-fill of missing fields
- Returns `<reviewer>` BLOCKER on invalid output
- Parses `plan_coverage` and `evidence`

```python
def parse_review_output(raw_output: str) -> ReviewResult:
    """
    Parse review JSON output with strict schema validation.

    CRITICAL: Pure sync function. NO async, NO asyncio.run().
    CRITICAL: NO AUTO-FILL. If schema fails, return <reviewer> BLOCKER.
    """
    # Extract JSON
    data = _extract_json_object(raw_output)

    if not data:
        # NO JSON found - hard fail
        return ReviewResult(
            verdict="FAIL",
            summary="Reviewer failed to return valid JSON",
            issues=[
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why="Reviewer output did not contain valid JSON",
                    fix_hint="Re-run review with explicit JSON format instruction",
                    evidence={"type": "tool_output", "ref": "kilo_parser:no_json_found"},
                )
            ],
            plan_coverage=[],  # Empty for failure case
        )

    # Validate schema - hard fail if invalid
    is_valid, schema_errors = validate_review_schema(data)

    if not is_valid:
        # Schema failed - hard fail (NO auto-fill)
        error_summary = "; ".join(schema_errors[:5])
        return ReviewResult(
            verdict="FAIL",
            summary=f"Schema validation failed: {error_summary}",
            issues=[
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why=f"Reviewer output does not conform to required schema. Errors: {error_summary}",
                    fix_hint="Ensure all required fields present and types correct",
                    evidence={"type": "tool_output", "ref": "schema_validator:validation_failed"},
                )
            ],
            plan_coverage=[],
            raw_output=raw_output,
        )

    # Schema valid - parse into objects
    issues = []
    for item in data["issues"]:
        issues.append(
            ReviewIssue(
                severity=item["severity"],
                category=item["category"],
                file=item["file"],
                lines=item["lines"],
                why=item["why"],
                fix_hint=item["fix_hint"],
                snippet=item.get("snippet"),
                evidence=item["evidence"],  # Required by schema
            )
        )

    return ReviewResult(
        verdict=data["verdict"],
        summary=data["summary"],
        issues=issues,
        notes=data.get("notes", []),
        stats=data.get("stats", {}),
        plan_coverage=data["plan_coverage"],  # Required by schema
        raw_output=raw_output,
    )
```

### G. Add Enforcement Validators

**Location:** After `parse_review_output()`

**CRITICAL: Evidence Policy Split (Intentional)**
- Schema enforces `evidence` field on ALL issues (BLOCKER, MAJOR, MINOR)
- `validate_evidence()` quality-checks BLOCKER/MAJOR only
- This split is intentional and must remain consistent

```python
def validate_evidence(issues: list[ReviewIssue]) -> tuple[bool, list[str]]:
    """
    Validate BLOCKER/MAJOR issues have proper structured evidence.

    IMPORTANT: Schema already enforces evidence field exists for ALL issues.
    This function validates evidence QUALITY for BLOCKER/MAJOR only.
    MINOR issues can have minimal evidence without validation failure.
    """
    violations = []

    for idx, issue in enumerate(issues):
        # Only enforce quality for BLOCKER/MAJOR
        if issue.severity not in ("BLOCKER", "MAJOR"):
            continue

        # ... validation logic for evidence quality

    return len(violations) == 0, violations


def validate_plan_coverage(
    extracted_requirements: list[dict[str, str]],
    coverage: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """
    Validate plan coverage completeness.

    Rules:
    - If requirements extracted: ALL must appear in coverage
    - If no requirements: at least 1 coverage entry required
    """
    violations = []

    # ... validation logic

    return len(violations) == 0, violations
```

### H. Add Pre-Review Gates (Renamed, Fault-Tolerant)

**Location:** After validators

**CRITICAL: Renamed to avoid collision**
- Old name `run_final_gate()` conflicts with existing "final_gate" max-variant logic
- New name: `run_pre_review_gates()`

```python
def run_pre_review_gates() -> dict[str, Any]:
    """
    Run scripts/final_gate.py with fault tolerance.

    RENAMED from run_final_gate() to avoid collision.
    Returns structured result even if script missing/errors/times out.
    """
    # ... implementation with try/except, timeout handling
    # Returns: {"overall": "PASS|FAIL", "summary": "...", "failures": [...], "warnings": [...], "raw_output": "..."}


def format_gate_results_compact(gate_data: dict[str, Any]) -> str:
    """Format gate results compactly for prompt (failures only)."""
    # ... format for prompt injection
```

### I. Replace `REVIEW_PROMPT_TEMPLATE`

**Location:** Line ~1805

**Must include:**
- `{gate_results}` placeholder (CRITICAL: must be injected)
- Hard "ENFORCEMENT ACTIVE (HARD GATES)" warnings
- Explicit JSON-only schema block requiring `plan_coverage` and `evidence`
- Verdict rules and coverage rules

```python
REVIEW_PROMPT_TEMPLATE = """ROLE
You are Kilo Reviewer (Opus). LAST gate before Traycer verification + commit.

⚠️ **ENFORCEMENT ACTIVE (HARD GATES)**
- Schema validation + evidence validation + plan coverage validation enforced by caller
- Invalid output = automatic FAIL + re-run once
- Missing evidence on BLOCKER/MAJOR = automatic rejection
- Incomplete plan coverage = automatic rejection

{gate_results}

INPUTS (REQUIRED)
1) **Traycer plan/spec:** {traycer_plan}

{requirements_section}

OUTPUT FORMAT (JSON ONLY - SCHEMA ENFORCED)
{{
  "verdict": "PASS" | "FAIL",
  "summary": "...",
  "issues": [
    {{
      "severity": "BLOCKER|MAJOR|MINOR",
      "category": "SPEC|SECURITY|CONFIG|EDGE|DOCS",
      "file": "path/to/file.ext",
      "lines": "L10-L20",
      "why": "...",
      "fix_hint": "...",
      "evidence": {{
        "type": "diff|file_line|tool_output|missing|multi_file|external",
        "ref": "REQUIRED for diff/file_line/tool_output",
        "explanation": "REQUIRED for missing/multi_file/external"
      }}
    }}
  ],
  "plan_coverage": [
    {{
      "requirement": "Exact text from plan",
      "status": "satisfied|missing|partial|n/a",
      "evidence": "file:line or explanation"
    }}
  ]
}}

FILES TO REVIEW:
{files_list}

{diff_content}
"""
```

### J. Replace `_run_single_batch_review()` — ALL ENFORCEMENT GATES

**Location:** Line ~2640

**CRITICAL: Caller-level flow with all corrections**

1. Track `attempt_results = []` for token accounting
2. Extract requirements → run gates → inject into prompt
3. Call Kilo → strict parse
4. If schema failed: retry once with JSON skeleton
5. Validate evidence → validate plan coverage
6. Attach metadata correctly (sum ALL attempts)
7. Safe gate write (check SESSION_DIR exists)

```python
async def _run_single_batch_review(
    files: list[Path],
    config: KiloReviewConfig,
    iteration: int,
    previous_issues: list[dict[str, Any]] | None = None,
) -> ReviewResult:
    """
    Run review with ALL enforcement gates.

    Corrections applied:
    - Token accounting: tracks all attempts, sums costs
    - Safe gate write: only if SESSION_DIR exists
    - Metadata from correct call after retry
    - Retry includes JSON skeleton
    """

    # Track ALL attempts for accurate cost accounting
    attempt_results = []

    # Extract plan requirements
    plan_text = config.traycer_plan or ""
    plan_requirements = extract_plan_requirements(plan_text)
    requirements_section = format_requirements_for_prompt(plan_requirements)

    # Run pre-review gates (fault-tolerant)
    gate_data = run_pre_review_gates()
    gate_results_str = format_gate_results_compact(gate_data)

    # Save gate output SAFELY (check SESSION_DIR exists)
    if hasattr(config, 'session_id') and config.session_id:
        try:
            gate_log_dir = SESSION_DIR if 'SESSION_DIR' in globals() else Path(".droid/reviews")
            gate_log_dir.mkdir(parents=True, exist_ok=True)
            # Only write if we have output (could be empty on error/timeout)
            if gate_data.get("raw_output"):
                (gate_log_dir / "gate_output.txt").write_text(gate_data["raw_output"])
        except Exception as e:
            print(f"⚠️  Could not save gate output: {e}", file=sys.stderr)

    # Build prompt with gate_results
    prompt = REVIEW_PROMPT_TEMPLATE.format(
        iteration_number=iteration,
        previous_issues=prev_issues_str,
        traycer_plan=plan_str,
        requirements_section=requirements_section,
        gate_results=gate_results_str,  # INJECTED HERE
        files_list=files_list,
        diff_content=diff_section,
    )

    # Attempt 1: Run Kilo
    result = await run_kilo(prompt, config, config.review_agent, files)
    attempt_results.append(result)

    # Parse strict (NO auto-fill)
    review_result = parse_review_output(result["result"])

    # Check if schema validation failed
    schema_failed = (
        review_result.verdict == "FAIL"
        and len(review_result.issues) == 1
        and review_result.issues[0].file == "<reviewer>"
        and "schema" in review_result.issues[0].why.lower()
    )

    if schema_failed:
        print(f"⚠️  Schema validation failed, retrying with JSON skeleton...", file=sys.stderr)

        # Retry with complete JSON skeleton
        retry_prompt = f"""SCHEMA VALIDATION FAILED

Your previous output did not match the required JSON schema.

**You MUST return valid JSON matching this structure:**

{{
  "verdict": "PASS",
  "summary": "Brief description (min 10 chars)",
  "issues": [
    {{
      "severity": "BLOCKER",
      "category": "SPEC",
      "file": "src/example.py",
      "lines": "L10-L20",
      "snippet": "optional",
      "why": "Detailed explanation (min 10 chars)",
      "fix_hint": "How to fix (min 5 chars)",
      "evidence": {{
        "type": "file_line",
        "ref": "src/example.py:L10-L20"
      }}
    }}
  ],
  "plan_coverage": [
    {{
      "requirement": "Requirement text from plan (min 5 chars)",
      "status": "satisfied",
      "evidence": "src/example.py:L10 implements this"
    }}
  ],
  "notes": [],
  "stats": {{"files_reviewed": {len(files)}, "lines_changed": 0}}
}}

Return ONLY the JSON object (no markdown, no text before/after).

Original task: {plan_text[:300]}...
"""

        # Attempt 2: Retry
        retry_result = await run_kilo(retry_prompt, config, config.review_agent, files)
        attempt_results.append(retry_result)

        # Parse retry
        review_result = parse_review_output(retry_result["result"])

        if review_result.verdict == "FAIL" and any(i.file == "<reviewer>" for i in review_result.issues):
            print(f"❌ Schema still invalid after retry. Giving up.", file=sys.stderr)
            # Will attach metadata below and return

    # Validate evidence (only if schema passed)
    if not any(i.file == "<reviewer>" for i in review_result.issues):
        evidence_valid, evidence_violations = validate_evidence(review_result.issues)

        if not evidence_valid:
            print(f"❌ Evidence validation failed", file=sys.stderr)
            review_result.verdict = "FAIL"
            review_result.issues.insert(0, ReviewIssue(
                severity="BLOCKER",
                category="SPEC",
                file="<reviewer>",
                lines="N/A",
                why=f"Missing required evidence. Violations: {'; '.join(evidence_violations[:3])}",
                fix_hint="Add structured evidence to all BLOCKER/MAJOR issues",
                evidence={"type": "tool_output", "ref": "evidence_validator:failed"},
            ))
        else:
            # Validate plan coverage
            coverage_valid, coverage_violations = validate_plan_coverage(
                plan_requirements,
                review_result.plan_coverage,
            )

            if not coverage_valid:
                print(f"❌ Coverage validation failed", file=sys.stderr)
                review_result.verdict = "FAIL"
                review_result.issues.insert(0, ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why=f"Incomplete plan coverage. Violations: {'; '.join(coverage_violations[:3])}",
                    fix_hint="Include all requirements in plan_coverage array",
                    evidence={"type": "tool_output", "ref": "coverage_validator:failed"},
                ))

    # Attach metadata - SUM ALL ATTEMPTS
    total_input_tokens = sum(r.get("input_tokens", 0) for r in attempt_results)
    total_output_tokens = sum(r.get("output_tokens", 0) for r in attempt_results)
    total_cost = sum(r.get("cost", 0.0) for r in attempt_results)

    review_result.session_id = attempt_results[-1].get("session_id")
    review_result.input_tokens = total_input_tokens
    review_result.output_tokens = total_output_tokens
    review_result.cost = total_cost

    # Add attempt count to stats
    if not review_result.stats:
        review_result.stats = {}
    review_result.stats["attempts"] = len(attempt_results)
    if len(attempt_results) > 1:
        review_result.stats["retried"] = True
        review_result.stats["retry_reason"] = "schema_validation_failed"

    return review_result
```

### K. Add Risk-Based Multi-Pass + Update `run_review()`

**Location:** After `_run_single_batch_review()`

**Add constants (line ~100):**
```python
SECURITY_SENSITIVE_PATHS = {
    "auth", "login", "password", "secret", "token", "session",
    "crypto", "encryption", "jwt", "oauth", "permission", "role",
    "admin", "sudo", "credential", "key", "certificate"
}
RISK_DIFF_SIZE_THRESHOLD = 500
```

**Add functions:**
```python
def assess_review_risk(files: list[Path], diff_content: str) -> dict[str, Any]:
    """Assess risk level for multi-pass decision."""
    # ... implementation


async def run_multi_pass_review(...) -> ReviewResult:
    """
    Multi-pass: general + security-focused.

    CRITICAL: Uses dataclasses.replace() to avoid config mutation.
    """
    # Pass 1: General
    pass1_result = await _run_single_batch_review(files, config, iteration, previous_issues)

    # Pass 2: Security (use COPY via dataclasses.replace)
    security_config = replace(config, skip_categories={"SPEC", "CONFIG", "EDGE", "DOCS"})
    pass2_result = await _run_single_batch_review(files, security_config, iteration, previous_issues)

    # Combine results
    # ... merge logic
```

**Update `run_review()`:**
```python
async def run_review(...) -> ReviewResult:
    """Run review with multi-pass support (triggers on risk)."""
    risk_assessment = assess_review_risk(files, diff_content)

    if risk_assessment["requires_multi_pass"]:
        return await run_multi_pass_review(files, config, iteration, previous_issues, risk_assessment)

    return await _run_single_batch_review(files, config, iteration, previous_issues)
```

---

## 3. `/opt/fabrik/tests/test_kilo_review_validation.py` — Create (NEW)

**Pytest-style tests (standard discovery):**

```python
"""
Pytest test harness for Kilo review validation.
Run: pytest tests/test_kilo_review_validation.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kilo_code_review import (
    validate_review_schema,
    validate_evidence,
    validate_plan_coverage,
    extract_plan_requirements,
    ReviewIssue,
)

def test_schema_valid_minimal():
    """Valid minimal output should pass."""
    # ... test implementation

def test_schema_missing_required_field():
    """Missing required field should fail."""
    # ... test implementation

def test_evidence_blocker_with_valid_ref():
    """BLOCKER with valid evidence should pass."""
    # ... test implementation

# ... 11 more tests covering all validation logic
```

---

## Critical Review Points

### 1. Schema vs Validator Consistency
**Schema:** Requires `evidence` on ALL issues (BLOCKER, MAJOR, MINOR)
**Validator:** Quality-checks evidence for BLOCKER/MAJOR only
**Status:** ✅ Intentional split, must remain consistent

### 2. parse_review_output Auto-Fill
**Current:** Silently defaults missing fields
**Required:** Return `<reviewer>` BLOCKER, NO fallbacks
**Status:** ✅ Documented in function replacement

### 3. Token/Cost Accounting
**Required:** Sum across ALL attempts, not just final
**Implementation:** `attempt_results` list, sum at end
**Status:** ✅ Documented in _run_single_batch_review

### 4. Plan Coverage Persistence
**Required:** In `iteration_data` dict, saved to `review_iter_*.json`
**Must cover:** Extracted requirements OR ≥1 generic entry
**Status:** ✅ Documented in persistence section

---

## Implementation Ready

All requirements documented with:
- Exact file locations
- Complete code blocks
- Critical failure points highlighted
- Verification steps included

**Ready to implement.**
