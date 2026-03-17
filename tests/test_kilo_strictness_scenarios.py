#!/usr/bin/env python3
"""
End-to-end test scenarios for Kilo review strictness enforcement.

Tests validate implementation against requirements documentation:
- 2026-03-02-requirements-final.md
- 2026-03-02-plan-kilo-strictness.md
- 2026-03-02-implementation-complete.md

Each scenario tests a specific critical requirement or failure point.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.kilo_code_review import (
    RISK_DIFF_SIZE_THRESHOLD,
    SECURITY_SENSITIVE_PATHS,
    ReviewIssue,
    assess_review_risk,
    extract_plan_requirements,
    parse_review_output,
    validate_evidence,
    validate_plan_coverage,
    validate_review_schema,
)

# =============================================================================
# SCENARIO 1: Schema Validation Enforces All Required Fields
# =============================================================================

def test_scenario_1_schema_requires_plan_coverage():
    """
    REQ: requirements-final.md line 93-94
    Schema must require plan_coverage with minItems: 1
    """
    # Missing plan_coverage should fail
    data = {
        "verdict": "PASS",
        "summary": "All checks passed",
        "issues": []
        # Missing plan_coverage
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid, "Schema should reject missing plan_coverage"
    assert any("plan_coverage" in err for err in errors)


def test_scenario_1_schema_requires_evidence_on_all_issues():
    """
    REQ: requirements-final.md line 102
    Schema must require evidence field on ALL issues
    """
    data = {
        "verdict": "FAIL",
        "summary": "Found issue",
        "issues": [
            {
                "severity": "MINOR",
                "category": "DOCS",
                "file": "README.md",
                "lines": "L5",
                "why": "Typo found",
                "fix_hint": "Fix it"
                # Missing evidence - should fail even for MINOR
            }
        ],
        "plan_coverage": [{"requirement": "test", "status": "satisfied", "evidence": "ok"}]
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid, "Schema should require evidence even for MINOR issues"


def test_scenario_1_schema_forbids_extra_fields():
    """
    REQ: requirements-final.md line 94, 103
    additionalProperties: false must prevent extra fields
    """
    data = {
        "verdict": "PASS",
        "summary": "All good",
        "issues": [],
        "plan_coverage": [{"requirement": "test", "status": "satisfied", "evidence": "ok"}],
        "extra_field": "not allowed"  # Should fail
    }
    is_valid, errors = validate_review_schema(data)
    assert not is_valid, "Schema should reject extra top-level fields"


# =============================================================================
# SCENARIO 2: parse_review_output Must NOT Auto-Fill
# =============================================================================

def test_scenario_2_parse_no_json_returns_blocker():
    """
    REQ: requirements-final.md line 174-175, 192-209
    NO auto-fill: missing JSON returns <reviewer> BLOCKER
    """
    raw_output = "This is just text without any JSON"
    result = parse_review_output(raw_output)

    assert result.verdict == "FAIL"
    assert len(result.issues) == 1
    assert result.issues[0].file == "<reviewer>"
    assert result.issues[0].severity == "BLOCKER"
    assert "json" in result.issues[0].why.lower()


def test_scenario_2_parse_invalid_schema_returns_blocker():
    """
    REQ: requirements-final.md line 212-233
    Invalid schema returns <reviewer> BLOCKER, NO auto-fill
    """
    raw_output = json.dumps({
        "verdict": "PASS",
        "summary": "Missing required fields"
        # Missing issues and plan_coverage
    })
    result = parse_review_output(raw_output)

    assert result.verdict == "FAIL"
    assert len(result.issues) == 1
    assert result.issues[0].file == "<reviewer>"
    assert result.issues[0].severity == "BLOCKER"
    assert "schema" in result.issues[0].why.lower()


# =============================================================================
# SCENARIO 3: Evidence Policy Split (Schema vs Validator)
# =============================================================================

def test_scenario_3_schema_enforces_evidence_all_severities():
    """
    REQ: requirements-final.md line 266-269
    Schema requires evidence on ALL issues (BLOCKER, MAJOR, MINOR)
    """
    # Try to create issue without evidence
    data_minor = {
        "verdict": "FAIL",
        "summary": "Minor issue",
        "issues": [{
            "severity": "MINOR",
            "category": "DOCS",
            "file": "README.md",
            "lines": "L5",
            "why": "Small typo",
            "fix_hint": "Fix it"
            # Missing evidence
        }],
        "plan_coverage": [{"requirement": "test", "status": "satisfied", "evidence": "ok"}]
    }
    is_valid, _ = validate_review_schema(data_minor)
    assert not is_valid, "Schema must require evidence even for MINOR"


def test_scenario_3_validator_checks_blocker_major_only():
    """
    REQ: requirements-final.md line 270-289
    validate_evidence() quality-checks BLOCKER/MAJOR only
    """
    # MINOR with minimal evidence should pass validator
    issues_minor = [
        ReviewIssue(
            severity="MINOR",
            category="DOCS",
            file="README.md",
            lines="L5",
            why="Typo",
            fix_hint="Fix it",
            evidence={}  # Empty evidence OK for MINOR
        )
    ]
    is_valid, _ = validate_evidence(issues_minor)
    assert is_valid, "Validator should allow minimal evidence for MINOR"

    # BLOCKER with empty evidence should fail validator
    issues_blocker = [
        ReviewIssue(
            severity="BLOCKER",
            category="SECURITY",
            file="src/auth.py",
            lines="L10",
            why="Critical issue",
            fix_hint="Fix it",
            evidence={}  # Empty evidence NOT OK for BLOCKER
        )
    ]
    is_valid, violations = validate_evidence(issues_blocker)
    assert not is_valid, "Validator should reject empty evidence for BLOCKER"
    assert len(violations) > 0


# =============================================================================
# SCENARIO 4: Plan Coverage Extraction and Validation
# =============================================================================

def test_scenario_4_extract_explicit_req_ids():
    """
    REQ: requirements-final.md line 154-167
    Extract requirements with REQ-# IDs (priority pattern)
    """
    plan = """
    Requirements:
    REQ-1: Implement authentication
    REQ-2: Add logging

    1. Numbered item (should be ignored)
    - Bullet item (should be ignored)
    """
    reqs = extract_plan_requirements(plan)
    assert len(reqs) == 2
    assert reqs[0]["id"] == "REQ-1"
    assert "authentication" in reqs[0]["text"].lower()


def test_scenario_4_coverage_requires_all_requirements():
    """
    REQ: requirements-final.md line 292-307
    All extracted requirements must be covered
    """
    requirements = [
        {"id": "REQ-1", "text": "Add auth"},
        {"id": "REQ-2", "text": "Add logging"}
    ]
    coverage_incomplete = [
        {"requirement": "Add auth", "status": "satisfied", "evidence": "done"}
        # REQ-2 missing
    ]
    is_valid, violations = validate_plan_coverage(requirements, coverage_incomplete)
    assert not is_valid, "Should fail when requirement missing from coverage"
    assert any("REQ-2" in v for v in violations)


def test_scenario_4_freeform_plan_needs_one_entry():
    """
    REQ: requirements-final.md line 299-307
    Freeform plans (no extracted requirements) need ≥1 coverage entry
    """
    requirements = []  # No structured requirements
    coverage_empty = []  # Empty coverage

    is_valid, violations = validate_plan_coverage(requirements, coverage_empty)
    assert not is_valid, "Should require at least 1 coverage entry for freeform plans"


# =============================================================================
# SCENARIO 5: Multi-Pass Review Risk Assessment
# =============================================================================

def test_scenario_5_security_path_triggers_multipass():
    """
    REQ: requirements-final.md line 593-600
    Security-sensitive paths should trigger multi-pass
    """
    files = [Path("src/auth.py"), Path("src/password_manager.py")]
    diff_content = "small diff\n" * 10  # Small diff

    risk = assess_review_risk(files, diff_content)
    assert risk["requires_multi_pass"], "Security paths should trigger multi-pass"
    assert "security_sensitive_paths" in risk["triggers"][0].lower()


def test_scenario_5_large_diff_triggers_multipass():
    """
    REQ: requirements-final.md line 600
    Diffs >500 lines should trigger multi-pass
    """
    files = [Path("src/normal.py")]  # No security keywords
    diff_content = "line\n" * 600  # Large diff

    risk = assess_review_risk(files, diff_content)
    assert risk["requires_multi_pass"], "Large diff should trigger multi-pass"
    assert "large_diff" in risk["triggers"][0].lower()


def test_scenario_5_low_risk_no_multipass():
    """
    REQ: requirements-final.md line 605-637
    Low-risk changes should use single-pass review
    """
    files = [Path("src/utils.py")]  # No security keywords
    diff_content = "small change\n" * 10  # Small diff

    risk = assess_review_risk(files, diff_content)
    assert not risk["requires_multi_pass"], "Low-risk should not trigger multi-pass"
    assert risk["risk_level"] == "low"


# =============================================================================
# SCENARIO 6: Plan Coverage Normalization
# =============================================================================

def test_scenario_6_coverage_strips_req_prefix():
    """
    ADDITIONAL: Plan coverage matching should handle REQ- prefix
    """
    requirements = [
        {"id": "REQ-1", "text": "Add feature"}
    ]
    coverage_with_prefix = [
        {"requirement": "REQ-1: Add feature", "status": "satisfied", "evidence": "done"}
    ]
    is_valid, _ = validate_plan_coverage(requirements, coverage_with_prefix)
    assert is_valid, "Should match coverage with REQ- prefix"


def test_scenario_6_coverage_strips_numbered_prefix():
    """
    ADDITIONAL: Plan coverage matching should handle R/B prefixes
    """
    requirements = [
        {"id": "R1", "text": "First requirement"}
    ]
    coverage_with_prefix = [
        {"requirement": "R1: First requirement", "status": "satisfied", "evidence": "done"}
    ]
    is_valid, _ = validate_plan_coverage(requirements, coverage_with_prefix)
    assert is_valid, "Should match coverage with R# prefix"


# =============================================================================
# SCENARIO 7: Retry Logic Catches All Failures
# =============================================================================

def test_scenario_7_retry_detects_no_json():
    """
    ADDITIONAL: Retry should trigger on no-JSON output
    """
    raw_output = "No JSON here, just text"
    result = parse_review_output(raw_output)

    # Should return BLOCKER that triggers retry in _run_single_batch_review
    assert result.verdict == "FAIL"
    assert result.issues[0].file == "<reviewer>"
    # Check if "json" in why (lowercase because retry check uses .lower())
    assert "json" in result.issues[0].why.lower()


# =============================================================================
# SCENARIO 8: Evidence Types and Validation
# =============================================================================

def test_scenario_8_evidence_file_line_requires_ref():
    """
    REQ: requirements-final.md line 111-118
    file_line evidence type must have ref field
    """
    issues = [
        ReviewIssue(
            severity="BLOCKER",
            category="SPEC",
            file="src/test.py",
            lines="L10",
            why="Issue found",
            fix_hint="Fix it",
            evidence={"type": "file_line"}  # Missing ref
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid, "file_line evidence requires ref field"


def test_scenario_8_evidence_missing_requires_explanation():
    """
    REQ: requirements-final.md line 111-118
    missing evidence type must have explanation field
    """
    issues = [
        ReviewIssue(
            severity="MAJOR",
            category="SPEC",
            file="src/test.py",
            lines="L10",
            why="Issue not in diff",
            fix_hint="Fix it",
            evidence={"type": "missing"}  # Missing explanation
        )
    ]
    is_valid, violations = validate_evidence(issues)
    assert not is_valid, "missing evidence requires explanation field"


# =============================================================================
# SCENARIO 9: Constants Match Documentation
# =============================================================================

def test_scenario_9_security_paths_defined():
    """
    REQ: requirements-final.md line 595-599
    Verify security-sensitive path keywords are defined
    """
    required_keywords = {"auth", "password", "token", "secret", "credential"}
    assert SECURITY_SENSITIVE_PATHS.issuperset(required_keywords)


def test_scenario_9_risk_threshold_correct():
    """
    REQ: requirements-final.md line 600
    Verify risk threshold is 500 lines
    """
    assert RISK_DIFF_SIZE_THRESHOLD == 500


# =============================================================================
# RUN ALL SCENARIOS
# =============================================================================

if __name__ == "__main__":
    import pytest

    # Run all test scenarios
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)
