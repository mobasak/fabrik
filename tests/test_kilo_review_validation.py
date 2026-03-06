#!/usr/bin/env python3
"""
Pytest tests for Kilo review validation functions.

Tests coverage:
- validate_review_schema() - JSON schema validation
- validate_evidence() - Evidence quality enforcement
- validate_plan_coverage() - Plan requirement coverage validation
"""

import pytest
from scripts.kilo_code_review import (
    REVIEW_RESULT_SCHEMA,
    ReviewIssue,
    extract_plan_requirements,
    format_requirements_for_prompt,
    validate_evidence,
    validate_plan_coverage,
    validate_review_schema,
)


# =============================================================================
# validate_review_schema() Tests
# =============================================================================

def test_validate_review_schema_valid_minimal():
    """Valid minimal JSON passes schema validation."""
    data = {
        "verdict": "PASS",
        "summary": "All checks passed successfully",
        "issues": [],
        "plan_coverage": [
            {
                "requirement": "Test requirement",
                "status": "satisfied",
                "evidence": "Test evidence"
            }
        ],
        "notes": [],
        "stats": {}
    }
    is_valid, errors = validate_review_schema(data)
    assert is_valid, f"Schema validation failed: {errors}"
    assert len(errors) == 0


def test_validate_review_schema_valid_with_issue():
    """Valid JSON with issue passes schema validation."""
    data = {
        "verdict": "FAIL",
        "summary": "Found critical security issue",
        "issues": [
            {
                "severity": "BLOCKER",
                "category": "SECURITY",
                "file": "src/auth.py",
                "lines": "L10-L20",
                "snippet": "password = input()",
                "why": "Hardcoded credentials detected",
                "fix_hint": "Use environment variables",
                "evidence": {
                    "type": "file_line",
                    "ref": "src/auth.py:L10-L20"
                }
            }
        ],
        "plan_coverage": [
            {
                "requirement": "Security review",
                "status": "satisfied",
                "evidence": "Found security issue"
            }
        ],
        "notes": ["Additional context"],
        "stats": {"files_reviewed": 1}
    }
    is_valid, errors = validate_review_schema(data)
    assert is_valid, f"Schema validation failed: {errors}"
    assert len(errors) == 0


def test_validate_review_schema_missing_required_field():
    """Missing required field fails schema validation."""
    data = {
        "verdict": "PASS",
        "summary": "All good",
        "issues": []
        # Missing plan_coverage (required)
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid
    assert len(errors) > 0
    assert any("plan_coverage" in err for err in errors)


def test_validate_review_schema_additional_properties():
    """Extra top-level fields fail schema validation (additionalProperties: false)."""
    data = {
        "verdict": "PASS",
        "summary": "All checks passed",
        "issues": [],
        "plan_coverage": [{"requirement": "test", "status": "satisfied", "evidence": "ok"}],
        "extra_field": "not allowed"  # INVALID
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid
    assert len(errors) > 0


def test_validate_review_schema_invalid_verdict():
    """Invalid verdict value fails schema validation."""
    data = {
        "verdict": "MAYBE",  # Only PASS/FAIL allowed
        "summary": "Uncertain result",
        "issues": [],
        "plan_coverage": [{"requirement": "test", "status": "satisfied", "evidence": "ok"}]
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid
    assert len(errors) > 0


def test_validate_review_schema_missing_issue_evidence():
    """Issue without evidence fails schema validation."""
    data = {
        "verdict": "FAIL",
        "summary": "Found issue",
        "issues": [
            {
                "severity": "MAJOR",
                "category": "SPEC",
                "file": "src/test.py",
                "lines": "L5",
                "why": "Something wrong",
                "fix_hint": "Fix it"
                # Missing evidence (required)
            }
        ],
        "plan_coverage": [{"requirement": "test", "status": "satisfied", "evidence": "ok"}]
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid
    assert len(errors) > 0


def test_validate_review_schema_empty_plan_coverage():
    """Empty plan_coverage fails schema validation (minItems: 1)."""
    data = {
        "verdict": "PASS",
        "summary": "All good",
        "issues": [],
        "plan_coverage": []  # Empty array violates minItems: 1
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid
    assert len(errors) > 0


# =============================================================================
# validate_evidence() Tests
# =============================================================================

def test_validate_evidence_all_valid():
    """All issues with valid evidence pass validation."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Security issue",
            fix_hint="Fix it",
            evidence={"type": "file_line", "ref": "src/auth.py:L10"}
        ),
        ReviewIssue(
            severity="MAJOR",
            category="SPEC",
            file="src/main.py",
            lines="L20-L30",
            why="Spec violation",
            fix_hint="Update code",
            evidence={"type": "diff", "ref": "src/main.py:L20-L30", "explanation": "Details"}
        ),
        ReviewIssue(
            severity="MINOR",
            category="DOCS",
            file="README.md",
            lines="L5",
            why="Typo",
            fix_hint="Fix typo",
            evidence=None  # MINOR doesn't require evidence
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert is_valid, f"Validation failed: {violations}"
    assert len(violations) == 0


def test_validate_evidence_blocker_missing_evidence():
    """BLOCKER issue without evidence fails validation."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Critical security issue",
            fix_hint="Fix immediately",
            evidence=None  # BLOCKER requires evidence
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) > 0
    assert any("BLOCKER" in v and "src/auth.py" in v for v in violations)


def test_validate_evidence_major_missing_evidence():
    """MAJOR issue without evidence fails validation."""
    issues = [
        ReviewIssue(
            severity="MAJOR",
            category="SPEC",
            file="src/main.py",
            lines="L20",
            why="Important issue",
            fix_hint="Fix it",
            evidence=None  # MAJOR requires evidence
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) > 0


def test_validate_evidence_minor_no_evidence_ok():
    """MINOR issue without evidence passes validation."""
    issues = [
        ReviewIssue(
            severity="MINOR",
            category="DOCS",
            file="README.md",
            lines="L5",
            why="Small typo",
            fix_hint="Fix it",
            evidence=None  # MINOR can omit evidence
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert is_valid
    assert len(violations) == 0


def test_validate_evidence_empty_evidence_object():
    """BLOCKER with empty evidence dict fails validation."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Critical issue",
            fix_hint="Fix it",
            evidence={}  # Empty dict not sufficient
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) > 0


def test_validate_evidence_missing_type():
    """Evidence without type field fails validation."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Critical issue",
            fix_hint="Fix it",
            evidence={"ref": "src/auth.py:L10"}  # Missing type
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) > 0


def test_validate_evidence_file_line_without_ref():
    """file_line evidence without ref fails validation."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Critical issue",
            fix_hint="Fix it",
            evidence={"type": "file_line"}  # Missing ref
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) > 0


def test_validate_evidence_missing_without_explanation():
    """missing evidence type without explanation fails validation."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Issue not in diff",
            fix_hint="Fix it",
            evidence={"type": "missing"}  # Missing explanation
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) > 0


def test_validate_evidence_mixed_valid_invalid():
    """Mix of valid and invalid evidence reports only invalid ones."""
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/good.py",
            lines="L10",
            why="Good issue",
            fix_hint="Fix it",
            evidence={"type": "file_line", "ref": "src/good.py:L10"}  # Valid
        ),
        ReviewIssue(
            severity="MAJOR",
            category="SPEC",
            file="src/bad.py",
            lines="L20",
            why="Bad issue",
            fix_hint="Fix it",
            evidence=None  # Invalid for MAJOR
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid
    assert len(violations) == 1
    assert "src/bad.py" in violations[0]


# =============================================================================
# validate_plan_coverage() Tests
# =============================================================================

def test_validate_plan_coverage_all_satisfied():
    """All requirements covered with satisfied status pass validation."""
    requirements = [
        {"id": "REQ-1", "text": "Implement authentication"},
        {"id": "REQ-2", "text": "Add logging"}
    ]
    coverage = [
        {
            "requirement": "Implement authentication",
            "status": "satisfied",
            "evidence": "src/auth.py:L10-L50"
        },
        {
            "requirement": "Add logging",
            "status": "satisfied",
            "evidence": "src/logger.py:L5-L20"
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert is_valid, f"Validation failed: {violations}"
    assert len(violations) == 0


def test_validate_plan_coverage_missing_requirement():
    """Missing requirement in coverage fails validation."""
    requirements = [
        {"id": "REQ-1", "text": "Implement authentication"},
        {"id": "REQ-2", "text": "Add logging"}
    ]
    coverage = [
        {
            "requirement": "Implement authentication",
            "status": "satisfied",
            "evidence": "src/auth.py:L10-L50"
        }
        # REQ-2 missing
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert not is_valid
    assert len(violations) > 0
    assert any("REQ-2" in v for v in violations)


def test_validate_plan_coverage_case_insensitive():
    """Coverage matching is case-insensitive."""
    requirements = [
        {"id": "REQ-1", "text": "Implement Authentication"}
    ]
    coverage = [
        {
            "requirement": "implement authentication",  # Different case
            "status": "satisfied",
            "evidence": "src/auth.py"
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert is_valid


def test_validate_plan_coverage_id_prefix_normalization():
    """Coverage with REQ-1: prefix matches extracted requirement."""
    requirements = [
        {"id": "REQ-1", "text": "Implement authentication"}
    ]
    coverage = [
        {
            "requirement": "REQ-1: Implement authentication",  # With prefix
            "status": "satisfied",
            "evidence": "src/auth.py"
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert is_valid


def test_validate_plan_coverage_numbered_prefix_normalization():
    """Coverage with R1: or B1: prefix matches extracted requirement."""
    requirements = [
        {"id": "R1", "text": "Add feature X"}
    ]
    coverage = [
        {
            "requirement": "R1: Add feature X",  # With R prefix
            "status": "satisfied",
            "evidence": "implemented"
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert is_valid


def test_validate_plan_coverage_missing_status_weak_evidence():
    """Missing/partial status without detailed evidence generates warning."""
    requirements = [
        {"id": "REQ-1", "text": "Implement feature"}
    ]
    coverage = [
        {
            "requirement": "Implement feature",
            "status": "missing",
            "evidence": "N/A"  # Weak evidence for missing status
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert not is_valid
    assert len(violations) > 0


def test_validate_plan_coverage_partial_with_good_evidence():
    """Partial status with detailed evidence passes validation."""
    requirements = [
        {"id": "REQ-1", "text": "Full test coverage"}
    ]
    coverage = [
        {
            "requirement": "Full test coverage",
            "status": "partial",
            "evidence": "Unit tests added (src/test_auth.py), integration tests pending"
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert is_valid


def test_validate_plan_coverage_no_requirements_empty_coverage():
    """No requirements with empty coverage fails (need at least 1 entry)."""
    requirements = []  # Freeform plan
    coverage = []  # Empty
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert not is_valid
    assert len(violations) > 0


def test_validate_plan_coverage_no_requirements_with_coverage():
    """No requirements but coverage provided passes (freeform plan)."""
    requirements = []  # Freeform plan
    coverage = [
        {
            "requirement": "General code review",
            "status": "satisfied",
            "evidence": "Reviewed all changed files"
        }
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage)
    assert is_valid


# =============================================================================
# extract_plan_requirements() Tests
# =============================================================================

def test_extract_plan_requirements_explicit_ids():
    """Extract requirements with explicit REQ-# IDs."""
    plan = """
    Requirements:
    REQ-1: Implement authentication
    REQ-2: Add logging
    REQ-3: Update documentation
    """
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 3
    assert reqs[0]["id"] == "REQ-1"
    assert reqs[0]["text"] == "Implement authentication"
    assert reqs[1]["id"] == "REQ-2"
    assert reqs[2]["id"] == "REQ-3"


def test_extract_plan_requirements_numbered_list():
    """Extract requirements from numbered list."""
    plan = """
    1. Add user authentication
    2. Implement rate limiting
    3. Write unit tests
    """
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 3
    assert reqs[0]["id"] == "R1"
    assert reqs[0]["text"] == "Add user authentication"
    assert reqs[1]["id"] == "R2"
    assert reqs[2]["id"] == "R3"


def test_extract_plan_requirements_bulleted_list():
    """Extract requirements from bulleted list."""
    plan = """
    - Fix authentication bug
    - Add error handling
    - Update README
    """
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 3
    assert reqs[0]["id"] == "B1"
    assert reqs[0]["text"] == "Fix authentication bug"
    assert reqs[1]["id"] == "B2"
    assert reqs[2]["id"] == "B3"


def test_extract_plan_requirements_mixed_prefers_explicit():
    """When multiple formats present, prefer explicit IDs."""
    plan = """
    REQ-1: Primary requirement
    1. Numbered item (should be ignored)
    - Bullet item (should be ignored)
    """
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 1
    assert reqs[0]["id"] == "REQ-1"


def test_extract_plan_requirements_empty_plan():
    """Empty plan returns empty list."""
    reqs = extract_plan_requirements("")
    assert len(reqs) == 0


def test_extract_plan_requirements_freeform_text():
    """Freeform text without structure returns empty list."""
    plan = "This is just some general description without any structured requirements."
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 0


def test_extract_plan_requirements_filters_short_lines():
    """Very short lines (<5 chars) are filtered out."""
    plan = """
    1. OK requirement text
    2. Bad
    3. Another good requirement
    """
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 2
    assert "OK requirement text" in reqs[0]["text"]
    assert "Another good requirement" in reqs[1]["text"]


# =============================================================================
# format_requirements_for_prompt() Tests
# =============================================================================

def test_format_requirements_for_prompt_with_requirements():
    """Format requirements into prompt-ready string."""
    requirements = [
        {"id": "REQ-1", "text": "Add auth"},
        {"id": "REQ-2", "text": "Add logging"}
    ]
    formatted = format_requirements_for_prompt(requirements)
    assert "REQ-1: Add auth" in formatted
    assert "REQ-2: Add logging" in formatted
    assert "MUST be covered" in formatted


def test_format_requirements_for_prompt_empty():
    """Empty requirements return freeform plan message."""
    formatted = format_requirements_for_prompt([])
    assert "No explicit requirements" in formatted
    assert "at least 1 general coverage entry" in formatted
