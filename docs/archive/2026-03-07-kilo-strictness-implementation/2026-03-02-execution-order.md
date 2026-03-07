# Kilo Review Strictness - Exact Execution Order

**Status:** COMPLETE (Implemented 2026-03-02, Verified 2026-03-07)
**Date:** 2026-03-02
**Total Time:** 4 hours (completed as estimated)

---

## ✅ Implementation Complete

All 14 steps implemented successfully in codebase.
All features verified working.

**READY TO ARCHIVE**

---

## Execution Order (Follow Exactly)

### Step 1 — Update Dependency (5 min)

**File:** `/opt/fabrik/requirements.txt`

**Add:**
```
jsonschema>=4.17.0
```

**Install:**
```bash
pip install -r requirements.txt
```

**Verify:**
```bash
python -c "import jsonschema; print(jsonschema.__version__)"
```

---

### Step 2 — Update Dataclasses (10 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Modify `ReviewIssue` (line ~193):**

Add field:
```python
evidence: dict[str, Any] | None = None
```

**Complete dataclass:**
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
    evidence: dict[str, Any] | None = None  # NEW

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

**Modify `ReviewResult` (line ~209):**

Add field:
```python
plan_coverage: list[dict[str, Any]] = field(default_factory=list)
```

**Complete dataclass:**
```python
@dataclass
class ReviewResult:
    verdict: str
    summary: str
    issues: list[ReviewIssue]
    notes: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    plan_coverage: list[dict[str, Any]] = field(default_factory=list)  # NEW
    session_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    raw_output: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
```

**Why:** These are mandatory for schema validation and coverage enforcement.

---

### Step 3 — Update Iteration Persistence (5 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Find:** `iteration_data = {` (approximately line 2800-2900)

**Add:**
```python
"plan_coverage": result.plan_coverage,
```

**Complete block:**
```python
iteration_data = {
    "iteration": iteration,
    "verdict": result.verdict,
    "summary": result.summary,
    "issues": [i.to_dict() for i in result.issues],
    "plan_coverage": result.plan_coverage,  # NEW - must be saved to review_iter_*.json
    "notes": result.notes,
    "stats": result.stats,
    "input_tokens": result.input_tokens,
    "output_tokens": result.output_tokens,
    "cost": result.cost,
}
```

**Why:** This must be saved to `review_iter_*.json` for coverage tracking.

---

### Step 4 — Add Imports (5 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Location:** Near top imports section (after existing imports, line ~44)

**Add:**
```python
from dataclasses import replace  # For multi-pass config copying
import jsonschema
from jsonschema import Draft7Validator
```

---

### Step 5 — Add Strict JSON Schema Validator (30 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Location:** After constants section (line ~110)

**Add:**

```python
# =============================================================================
# STRICT SCHEMA VALIDATION (ENFORCED)
# =============================================================================

REVIEW_RESULT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["verdict", "summary", "issues", "plan_coverage"],
    "additionalProperties": False,  # CRITICAL: enforces hard-gated output
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
                "additionalProperties": False,  # CRITICAL: no extra fields in issues
                "properties": {
                    "severity": {"type": "string", "enum": ["BLOCKER", "MAJOR", "MINOR"]},
                    "category": {"type": "string", "enum": ["SPEC", "SECURITY", "CONFIG", "EDGE", "DOCS"]},
                    "file": {"type": "string", "minLength": 1},
                    "lines": {"type": "string", "pattern": "^(L\\d+(-L\\d+)?|N/A)$"},
                    "snippet": {"type": "string"},
                    "why": {"type": "string", "minLength": 10},
                    "fix_hint": {"type": "string", "minLength": 5},
                    "evidence": {
                        "type": "object",
                        "required": ["type"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["diff", "file_line", "tool_output", "missing", "multi_file", "external"]
                            },
                            "ref": {"type": "string", "minLength": 1},
                            "explanation": {"type": "string", "minLength": 10},
                            "supporting_refs": {"type": "array", "items": {"type": "string"}}
                        },
                        "oneOf": [
                            {
                                "properties": {"type": {"enum": ["diff", "file_line", "tool_output"]}},
                                "required": ["ref"]
                            },
                            {
                                "properties": {"type": {"enum": ["missing", "multi_file", "external"]}},
                                "required": ["explanation"]
                            }
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
                "properties": {
                    "requirement_id": {"type": "string"},
                    "requirement": {"type": "string", "minLength": 5},
                    "status": {"type": "string", "enum": ["satisfied", "missing", "partial", "n/a"]},
                    "evidence": {"type": "string", "minLength": 5},
                    "notes": {"type": "string"}
                }
            }
        },
        "notes": {"type": "array", "items": {"type": "string"}},
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

**Important schema requirements:**
- `required`: verdict, summary, issues, plan_coverage
- `additionalProperties: false` (top level AND issue level)
- `issues[].evidence` required
- `plan_coverage` minItems = 1

**Why:** This enforces **hard-gated output** - no extra fields, all required fields present.

---

### Step 6 — Add Requirement Extraction (20 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Location:** After `validate_review_schema()`

**Add:**

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

**Why:** These convert plan text into structured requirements for coverage validation.

---

### Step 7 — Replace `parse_review_output()` Completely (20 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Location:** Line ~2456

**CRITICAL RULES:**
- **NO AUTO-FILL**
- **NO ASYNC**
- **NO FALLBACKS**

**If schema fails:** Return ReviewResult with `<reviewer>` BLOCKER

**Invalid output must FAIL, not be corrected silently.**

**REPLACE ENTIRE FUNCTION:**

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
        # No JSON found - this is a reviewer failure (NO AUTO-FILL)
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

    # Step 2: Validate against strict schema (NO AUTO-FILL)
    is_valid, schema_errors = validate_review_schema(data)

    if not is_valid:
        # Schema validation failed - return structured failure (NO AUTO-FILL)
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

---

### Step 8 — Add Validation Functions (30 min)

**File:** `/opt/fabrik/scripts/kilo_code_review.py`

**Location:** After `parse_review_output()`

**Important Policy Split:**

**Schema enforces:** evidence exists on ALL issues (BLOCKER, MAJOR, MINOR)

**Validator enforces quality for:** BLOCKER, MAJOR only

**MINOR can contain minimal evidence.**

**Add:**

```python
# =============================================================================
# EVIDENCE + COVERAGE VALIDATION
# =============================================================================

def validate_evidence(issues: list[ReviewIssue]) -> tuple[bool, list[str]]:
    """
    Validate that BLOCKER/MAJOR issues have proper structured evidence.

    Evidence rules (enforced):
    - diff/file_line/tool_output: MUST have "ref" field
    - missing/multi_file/external: MUST have "explanation" field

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

        else:
            # Invalid evidence type (should be caught by schema)
            violations.append(
                f"Issue #{idx+1} ({issue.file}): "
                f"invalid evidence type '{ev_type}'"
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

---

(Continuing in next message due to length...)
