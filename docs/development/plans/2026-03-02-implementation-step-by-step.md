# Kilo Review Strictness - Step-by-Step Implementation Guide

**Date:** 2026-03-02
**Task:** Always-on hard-gated Kilo review with schema/evidence/coverage enforcement

---

## Step 1: Extend Dataclasses + Persistence (45 min)

### 1.1: Add evidence field to ReviewIssue

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** Line ~193 (search for `class ReviewIssue`)

**Current code:**
```python
@dataclass
class ReviewIssue:
    """A single issue found during review."""

    severity: str  # BLOCKER, MAJOR, MINOR
    category: str  # SPEC, SECURITY, CONFIG, EDGE, DOCS
    file: str
    lines: str
    why: str
    fix_hint: str
    snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

**Change to:**
```python
@dataclass
class ReviewIssue:
    """A single issue found during review."""

    severity: str  # BLOCKER, MAJOR, MINOR
    category: str  # SPEC, SECURITY, CONFIG, EDGE, DOCS
    file: str
    lines: str
    why: str
    fix_hint: str
    snippet: str | None = None
    evidence: dict[str, Any] | None = None  # NEW: structured evidence object

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

### 1.2: Add plan_coverage field to ReviewResult

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** Line ~209 (search for `class ReviewResult`)

**Current code:**
```python
@dataclass
class ReviewResult:
    """Result of a Kilo review call."""

    verdict: str  # PASS, FAIL
    summary: str
    issues: list[ReviewIssue]
    notes: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    raw_output: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
```

**Change to:**
```python
@dataclass
class ReviewResult:
    """Result of a Kilo review call."""

    verdict: str  # PASS, FAIL
    summary: str
    issues: list[ReviewIssue]
    notes: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    plan_coverage: list[dict[str, Any]] = field(default_factory=list)  # NEW: required
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    raw_output: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
```

### 1.3: Update session persistence to include plan_coverage

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** Search for `iteration_data = {` (inside review loop, approximately line 2800-2900)

**Find this pattern:**
```python
iteration_data = {
    "iteration": iteration,
    "verdict": result.verdict,
    "summary": result.summary,
    "issues": [i.to_dict() for i in result.issues],
    "notes": result.notes,
    "stats": result.stats,
    "input_tokens": result.input_tokens,
    "output_tokens": result.output_tokens,
    "cost": result.cost,
}
```

**Change to:**
```python
iteration_data = {
    "iteration": iteration,
    "verdict": result.verdict,
    "summary": result.summary,
    "issues": [i.to_dict() for i in result.issues],
    "plan_coverage": result.plan_coverage,  # NEW: persist coverage
    "notes": result.notes,
    "stats": result.stats,
    "input_tokens": result.input_tokens,
    "output_tokens": result.output_tokens,
    "cost": result.cost,
}
```

**Verification:**
```bash
# Check dataclasses are updated
grep -A 15 "class ReviewIssue" scripts/kilo_code_review.py | grep evidence
grep -A 20 "class ReviewResult" scripts/kilo_code_review.py | grep plan_coverage

# Check persistence updated
grep -A 12 '"iteration":' scripts/kilo_code_review.py | grep plan_coverage
```

---

## Step 2: Add Dependencies + Schema Validator (30 min)

### 2.1: Update requirements.txt

**File:** `/opt/fabrik/requirements.txt`

**Add this line:**
```
jsonschema>=4.17.0
```

**Verification:**
```bash
pip install -r requirements.txt
python -c "import jsonschema; print(jsonschema.__version__)"
```

### 2.2: Add imports

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** After existing imports (line ~44, after other imports)

**Add these lines:**
```python
from dataclasses import replace  # For multi-pass config copying
import jsonschema
from jsonschema import Draft7Validator, ValidationError
```

### 2.3: Add schema definition and validator

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** After constants section (line ~110, after `DOC_EXTENSIONS = ...`)

**Add this complete section:**
```python
# =============================================================================
# STRICT SCHEMA VALIDATION (ENFORCED)
# =============================================================================

REVIEW_RESULT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["verdict", "summary", "issues", "plan_coverage"],
    "additionalProperties": False,
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["PASS", "FAIL"]
        },
        "summary": {
            "type": "string",
            "minLength": 10,
            "maxLength": 1000
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "category", "file", "lines", "why", "fix_hint", "evidence"],
                "additionalProperties": False,
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["BLOCKER", "MAJOR", "MINOR"]
                    },
                    "category": {
                        "type": "string",
                        "enum": ["SPEC", "SECURITY", "CONFIG", "EDGE", "DOCS"]
                    },
                    "file": {
                        "type": "string",
                        "minLength": 1
                    },
                    "lines": {
                        "type": "string",
                        "pattern": "^(L\\d+(-L\\d+)?|N/A)$"
                    },
                    "snippet": {
                        "type": "string"
                    },
                    "why": {
                        "type": "string",
                        "minLength": 10
                    },
                    "fix_hint": {
                        "type": "string",
                        "minLength": 5
                    },
                    "evidence": {
                        "type": "object",
                        "required": ["type"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["diff", "file_line", "tool_output", "missing", "multi_file", "external"]
                            },
                            "ref": {
                                "type": "string",
                                "minLength": 1
                            },
                            "explanation": {
                                "type": "string",
                                "minLength": 10
                            },
                            "supporting_refs": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "oneOf": [
                            {
                                "properties": {
                                    "type": {"enum": ["diff", "file_line", "tool_output"]}
                                },
                                "required": ["ref"]
                            },
                            {
                                "properties": {
                                    "type": {"enum": ["missing", "multi_file", "external"]}
                                },
                                "required": ["explanation"]
                            }
                        ]
                    }
                }
            }
        },
        "plan_coverage": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["requirement", "status", "evidence"],
                "additionalProperties": False,
                "properties": {
                    "requirement_id": {
                        "type": "string"
                    },
                    "requirement": {
                        "type": "string",
                        "minLength": 5
                    },
                    "status": {
                        "type": "string",
                        "enum": ["satisfied", "missing", "partial", "n/a"]
                    },
                    "evidence": {
                        "type": "string",
                        "minLength": 5
                    },
                    "notes": {
                        "type": "string"
                    }
                }
            }
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"}
        },
        "stats": {
            "type": "object",
            "properties": {
                "files_reviewed": {"type": "integer", "minimum": 0},
                "lines_changed": {"type": "integer", "minimum": 0},
                "issues_by_severity": {
                    "type": "object",
                    "properties": {
                        "BLOCKER": {"type": "integer", "minimum": 0},
                        "MAJOR": {"type": "integer", "minimum": 0},
                        "MINOR": {"type": "integer", "minimum": 0}
                    }
                }
            }
        }
    }
}

# Compile validator once (performance optimization)
REVIEW_SCHEMA_VALIDATOR = Draft7Validator(REVIEW_RESULT_SCHEMA)


def validate_review_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate reviewer output against strict JSON schema.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors = []
    for error in REVIEW_SCHEMA_VALIDATOR.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")
    return len(errors) == 0, errors
```

**Verification:**
```bash
python -c "
from scripts.kilo_code_review import REVIEW_SCHEMA_VALIDATOR, validate_review_schema
test = {'verdict': 'PASS', 'summary': 'Test summary string', 'issues': [], 'plan_coverage': [{'requirement': 'test', 'status': 'satisfied', 'evidence': 'test evidence'}]}
valid, errors = validate_review_schema(test)
print('Valid:', valid)
assert valid, f'Schema validation failed: {errors}'
"
```

---

## Step 3: Plan Requirement Extraction (30 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** After `validate_review_schema()` function

**Add these two functions:**

```python
# =============================================================================
# PLAN REQUIREMENT EXTRACTION
# =============================================================================

def extract_plan_requirements(plan_text: str) -> list[dict[str, str]]:
    """
    Extract requirements from Traycer plan.

    Recognizes patterns (priority order):
    1. REQ-1: text (explicit IDs)
    2. 1. text (numbered lists)
    3. - text (bulleted lists, fallback)

    Returns:
        [{"id": "REQ-1", "text": "Requirement description"}, ...]
        Empty list if no structured requirements found
    """
    if not plan_text or len(plan_text.strip()) < 10:
        return []

    requirements = []

    # Pattern 1: Explicit IDs (REQ-1:, REQ-2:, etc.)
    explicit_pattern = re.compile(r'\b(REQ-\d+):\s*(.+?)(?:\n|$)', re.MULTILINE)
    for match in explicit_pattern.finditer(plan_text):
        requirements.append({
            "id": match.group(1),
            "text": match.group(2).strip()
        })

    # If explicit IDs found, use only those
    if requirements:
        return requirements

    # Pattern 2: Numbered lists (1. text, 2. text, etc.)
    numbered_pattern = re.compile(r'^\s*(\d+)\.\s+(.+?)(?:\n|$)', re.MULTILINE)
    for match in numbered_pattern.finditer(plan_text):
        req_text = match.group(2).strip()
        # Filter out very short lines (likely not requirements)
        if len(req_text) > 5:
            requirements.append({
                "id": f"R{match.group(1)}",
                "text": req_text
            })

    # If numbered lists found, use those
    if requirements:
        return requirements

    # Pattern 3: Bulleted lists (- text or * text)
    bullets = []
    bullet_pattern = re.compile(r'^\s*[-*]\s+(.+?)(?:\n|$)', re.MULTILINE)
    for match in bullet_pattern.finditer(plan_text):
        req_text = match.group(1).strip()
        if len(req_text) > 5:
            bullets.append(req_text)

    if bullets:
        for idx, text in enumerate(bullets, 1):
            requirements.append({
                "id": f"B{idx}",
                "text": text
            })

    return requirements


def format_requirements_for_prompt(requirements: list[dict[str, str]]) -> str:
    """
    Format extracted requirements for inclusion in review prompt.

    Returns:
        Formatted string ready for prompt injection
    """
    if not requirements:
        return """[No explicit requirements extracted - plan is freeform]

**Coverage requirement:** Include at least 1 general coverage entry describing what was reviewed."""

    lines = ["**Extracted Requirements (MUST be covered in plan_coverage):**"]
    for req in requirements:
        lines.append(f"  {req['id']}: {req['text']}")

    lines.append("\n**You MUST include each requirement in plan_coverage array.**")

    return "\n".join(lines)
```

**Verification:**
```bash
python -c "
from scripts.kilo_code_review import extract_plan_requirements, format_requirements_for_prompt

# Test numbered
plan1 = '''
Task: Test
1. First requirement
2. Second requirement
'''
reqs = extract_plan_requirements(plan1)
assert len(reqs) == 2, f'Expected 2, got {len(reqs)}'
assert reqs[0]['id'] == 'R1', f'Expected R1, got {reqs[0][\"id\"]}'
print('✓ Numbered extraction works')

# Test explicit
plan2 = '''
REQ-1: First requirement
REQ-2: Second requirement
'''
reqs = extract_plan_requirements(plan2)
assert len(reqs) == 2
assert reqs[0]['id'] == 'REQ-1'
print('✓ Explicit ID extraction works')

# Test formatting
formatted = format_requirements_for_prompt(reqs)
assert 'REQ-1' in formatted
print('✓ Formatting works')
"
```

---

## Step 4: Parse Review Output (Strict, Sync, Pure) (30 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** Find and REPLACE the entire `parse_review_output()` function (approximately line 2456)

**CRITICAL REQUIREMENT: NO AUTO-FILL**
The current implementation silently defaults missing fields (verdict, summary, issues), which defeats hard gating.
The new implementation MUST return `<reviewer>` BLOCKER if schema validation fails. NO fallbacks, NO assumptions.

**REPLACE ENTIRE FUNCTION WITH:**

```python
def parse_review_output(raw_output: str) -> ReviewResult:
    """
    Parse review JSON output with strict schema validation.

    CRITICAL: This is a PURE SYNC function. NO async, NO asyncio.run().
    Retry logic is handled by the CALLER (_run_single_batch_review).

    CRITICAL: NO AUTO-FILL. If schema validation fails, return ReviewResult
    with <reviewer> BLOCKER. Do NOT silently default missing fields.

    Args:
        raw_output: Raw Kilo output (may contain markdown, text, JSON)

    Returns:
        ReviewResult object (may contain <reviewer> BLOCKER if validation failed)
    """
    # Step 1: Extract JSON object from output
    data = _extract_json_object(raw_output)

    if not data:
        # No JSON found - this is a reviewer failure
        return ReviewResult(
            verdict="FAIL",
            summary="Reviewer failed to return valid JSON",
            issues=[
                ReviewIssue(
                    severity="BLOCKER",
                    category="SPEC",
                    file="<reviewer>",
                    lines="N/A",
                    why="Reviewer output did not contain valid JSON. This is a reviewer failure.",
                    fix_hint="Re-run review with explicit JSON format instruction.",
                    evidence={"type": "tool_output", "ref": "kilo_parser:no_json_found"},
                )
            ],
            plan_coverage=[],  # Empty coverage for failure case
        )

    # Step 2: Validate against strict schema
    is_valid, schema_errors = validate_review_schema(data)

    if not is_valid:
        # Schema validation failed - return structured failure
        error_summary = "; ".join(schema_errors[:5])  # First 5 errors

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
                    fix_hint="Ensure all required fields are present and types are correct.",
                    evidence={"type": "tool_output", "ref": "schema_validator:validation_failed"},
                )
            ],
            plan_coverage=[],
            raw_output=raw_output,
        )

    # Step 3: Schema is valid - parse into ReviewResult
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
                snippet=item.get("snippet"),  # Optional
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

**Verification:**
```bash
python -c "
from scripts.kilo_code_review import parse_review_output

# Test valid output
valid_json = '''
{
  \"verdict\": \"PASS\",
  \"summary\": \"All checks passed successfully\",
  \"issues\": [],
  \"plan_coverage\": [{\"requirement\": \"test\", \"status\": \"satisfied\", \"evidence\": \"verified\"}]
}
'''
result = parse_review_output(valid_json)
assert result.verdict == 'PASS', f'Expected PASS, got {result.verdict}'
print('✓ Valid JSON parsing works')

# Test invalid (missing plan_coverage)
invalid_json = '''
{
  \"verdict\": \"PASS\",
  \"summary\": \"Test\",
  \"issues\": []
}
'''
result = parse_review_output(invalid_json)
assert result.verdict == 'FAIL', 'Should fail for missing plan_coverage'
assert any(i.file == '<reviewer>' for i in result.issues), 'Should have reviewer issue'
print('✓ Schema validation catches missing fields')
"
```

---

## Step 5: Evidence + Coverage Validation (45 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`
**Location:** After `parse_review_output()` function

**CRITICAL: Evidence Policy Split (Intentional)**
- **Schema (Step 2D):** Enforces `evidence` field present on ALL issues (BLOCKER, MAJOR, MINOR)
- **validate_evidence() (this step):** Quality-checks evidence for BLOCKER/MAJOR only
- **Why:** Schema catches missing fields at JSON level, validator ensures meaningful content for critical issues
- **This split is intentional and must remain consistent**

**Add these two validation functions:**

```python
# =============================================================================
# EVIDENCE + COVERAGE VALIDATION
# =============================================================================

def validate_evidence(issues: list[ReviewIssue]) -> tuple[bool, list[str]]:
    """
    Validate that BLOCKER/MAJOR issues have proper structured evidence.

    IMPORTANT: Schema already enforces evidence field exists for ALL issues.
    This function validates evidence QUALITY for BLOCKER/MAJOR only.
    MINOR issues can have minimal evidence without validation failure.

    Returns:
        (all_valid, list_of_violation_messages)
    """
    violations = []

    for idx, issue in enumerate(issues):
        # Only enforce quality for BLOCKER and MAJOR
        if issue.severity not in ("BLOCKER", "MAJOR"):
            continue

        # Check evidence object exists (should be caught by schema, but double-check)
        if not issue.evidence or not isinstance(issue.evidence, dict):
            violations.append(
                f"Issue #{idx+1} ({issue.severity}/{issue.category} in {issue.file}): "
                f"missing evidence object"
            )
            continue

        ev_type = issue.evidence.get("type")
        if not ev_type:
            violations.append(
                f"Issue #{idx+1} ({issue.file}): evidence.type is missing"
            )
            continue

        # Validate based on evidence type
        if ev_type in ("diff", "file_line", "tool_output"):
            # These types require "ref" field
            if not issue.evidence.get("ref"):
                violations.append(
                    f"Issue #{idx+1} ({issue.file}): "
                    f"evidence type '{ev_type}' requires 'ref' field (e.g., 'src/file.py:L10-L20')"
                )

        elif ev_type in ("missing", "multi_file", "external"):
            # These types require "explanation" field
            if not issue.evidence.get("explanation"):
                violations.append(
                    f"Issue #{idx+1} ({issue.file}): "
                    f"evidence type '{ev_type}' requires 'explanation' field"
                )
            # Soft recommendation: supporting_refs helps
            if not issue.evidence.get("supporting_refs"):
                print(
                    f"⚠️  Issue #{idx+1} ({issue.file}): "
                    f"evidence type '{ev_type}' should include supporting_refs if possible",
                    file=sys.stderr,
                )

        else:
            # Invalid evidence type (should be caught by schema)
            violations.append(
                f"Issue #{idx+1} ({issue.file}): "
                f"invalid evidence type '{ev_type}' (allowed: diff, file_line, tool_output, missing, multi_file, external)"
            )

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
    - missing/partial status should have detailed evidence

    Returns:
        (all_valid, list_of_violation_messages)
    """
    violations = []

    # If no explicit requirements, still need at least 1 coverage entry
    if not extracted_requirements:
        if not coverage:
            violations.append(
                "plan_coverage is empty - at least 1 entry required for freeform plans "
                "(describe what was reviewed)"
            )
        return len(violations) == 0, violations

    # Build requirement text lookup (case-insensitive, normalized)
    req_texts_normalized = {
        req["text"].lower().strip(): req["id"]
        for req in extracted_requirements
    }

    covered_texts_normalized = {
        c["requirement"].lower().strip()
        for c in coverage
    }

    # Check that all requirements are covered
    for req in extracted_requirements:
        req_normalized = req["text"].lower().strip()
        if req_normalized not in covered_texts_normalized:
            violations.append(
                f"Requirement '{req['id']}' not covered in plan_coverage: {req['text'][:60]}..."
            )

    # Check for missing/partial status without detailed evidence
    for item in coverage:
        if item["status"] in ("missing", "partial"):
            if not item.get("evidence") or len(item["evidence"]) < 10:
                violations.append(
                    f"Coverage item marked '{item['status']}' lacks detailed evidence: "
                    f"{item['requirement'][:40]}..."
                )

    return len(violations) == 0, violations
```

**Verification:**
```bash
python -c "
from scripts.kilo_code_review import validate_evidence, validate_plan_coverage, ReviewIssue

# Test evidence validation
issue_valid = ReviewIssue(
    severity='BLOCKER',
    category='SECURITY',
    file='test.py',
    lines='L10',
    why='Test issue with valid evidence',
    fix_hint='Fix it',
    evidence={'type': 'file_line', 'ref': 'test.py:L10'}
)
valid, violations = validate_evidence([issue_valid])
assert valid, f'Should be valid: {violations}'
print('✓ Evidence validation works for valid evidence')

# Test coverage validation
reqs = [{'id': 'R1', 'text': 'Test requirement'}]
coverage = [{'requirement': 'Test requirement', 'status': 'satisfied', 'evidence': 'Verified'}]
valid, violations = validate_plan_coverage(reqs, coverage)
assert valid, f'Should be valid: {violations}'
print('✓ Coverage validation works')
"
```

---

(Continuing in next file due to length...)
