#!/usr/bin/env python3
"""
Kilo Documentation Enforcer - Professional-grade documentation enforcement.

Analyzes git diff for documentation triggers and enforces updates.
Uses dynamic agent selection from kilo_agents.db for documentation tasks.

Workflow:
1. Detect code changes via git diff
2. Match changes against documentation triggers
3. Identify required documentation updates
4. Auto-generate docs using Kilo CLI with documentation agents (--auto-generate)
5. Enforce documentation coverage via exit codes (--enforce)

Usage:
    # Detect required docs (check mode)
    python scripts/kilo_docs_enforcer.py --detect

    # Enforce documentation requirements (fail if missing)
    python scripts/kilo_docs_enforcer.py --enforce

    # Output as JSON
    python scripts/kilo_docs_enforcer.py --detect --output json

    # Auto-generate docs using Kilo agents
    python scripts/kilo_docs_enforcer.py --auto-generate

    # Configurable threshold (default: 50 lines)
    KILO_DOCS_THRESHOLD=100 python scripts/kilo_docs_enforcer.py --enforce

Exit codes:
    0 - All required documentation present or updated
    1 - Missing required documentation (CRITICAL or MAJOR severity)
    2 - Error (git unavailable, database error, etc.)

Workflow Doc: docs/workflows/DOCUMENTATOR_WORKFLOW.md
  ⚠️  Update the workflow doc when modifying this script.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import contextlib
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# Add kilo-benchmarks to path for agent selection
SCRIPT_DIR = Path(__file__).parent
KILO_BENCHMARKS_DIR = SCRIPT_DIR / "kilo-benchmarks"
sys.path.insert(0, str(KILO_BENCHMARKS_DIR))

try:
    from agent_selector import NoAgentAvailableError, select_agent
except ImportError:
    print("Error: agent_selector.py not found in scripts/kilo-benchmarks/", file=sys.stderr)
    print("Run: python scripts/kilo-benchmarks/role_mapper.py to set up agents", file=sys.stderr)
    sys.exit(2)

PROJECT_ROOT = Path.cwd()

# Severity levels
SeverityLevel = Literal["CRITICAL", "MAJOR", "MINOR"]

# Complexity levels for agent selection
ComplexityLevel = Literal["simple", "medium", "complex"]


@dataclass
class DocTrigger:
    """Documentation update trigger pattern."""

    name: str
    pattern: str
    severity: SeverityLevel
    required_docs: list[str]
    exclude_paths: list[str]
    description: str
    file_filters: list[str] = field(
        default_factory=list
    )  # Specific files to match (*.py, *.ts, etc.)


@dataclass
class DocViolation:
    """Detected documentation requirement violation."""

    trigger_name: str
    severity: SeverityLevel
    source_file: str
    matched_line: str
    required_docs: list[str]
    description: str
    line_number: int | None = None


@dataclass
class DocRequirement:
    """Documentation file that needs update."""

    doc_path: str
    severity: SeverityLevel
    triggers: list[DocViolation]
    exists: bool
    last_modified: datetime | None = None


# =============================================================================
# DOCUMENTATION TRIGGERS (Comprehensive detection patterns)
# =============================================================================

DOCUMENTATION_TRIGGERS: dict[str, DocTrigger] = {
    # CRITICAL severity - Block merge
    "new_public_function": DocTrigger(
        name="new_public_function",
        pattern=r"^\+\s*(?:async\s+)?def\s+[a-z][a-z0-9_]*\(",  # Exclude _private
        severity="CRITICAL",
        required_docs=["docs/reference/{module}.md", "CHANGELOG.md"],
        exclude_paths=["tests/", "test_", "__pycache__/"],
        description="New public function requires API documentation",
        file_filters=["*.py"],
    ),
    "new_class": DocTrigger(
        name="new_class",
        pattern=r"^\+\s*class\s+[A-Z][a-zA-Z0-9_]*[:(]",
        severity="CRITICAL",
        required_docs=["docs/reference/{module}.md", "CHANGELOG.md"],
        exclude_paths=["tests/", "test_"],
        description="New class requires API documentation",
        file_filters=["*.py"],
    ),
    "new_endpoint": DocTrigger(
        name="new_endpoint",
        pattern=r"^\+\s*@app\.(get|post|put|delete|patch|head|options)",
        severity="CRITICAL",
        required_docs=["README.md", "CHANGELOG.md"],
        exclude_paths=["tests/"],
        description="New API endpoint requires documentation",
        file_filters=["*.py"],
    ),
    "new_env_var": DocTrigger(
        name="new_env_var",
        pattern=r"^\+.*os\.getenv\(['\"]([A-Z_][A-Z0-9_]*)['\"]",
        severity="CRITICAL",
        required_docs=["docs/CONFIGURATION.md", ".env.example"],
        exclude_paths=["tests/"],
        description="New environment variable must be documented",
        file_filters=["*.py"],
    ),
    "breaking_change": DocTrigger(
        name="breaking_change",
        pattern=r"^\+.*#\s*BREAKING:",
        severity="CRITICAL",
        required_docs=["CHANGELOG.md", "docs/MIGRATION.md"],
        exclude_paths=[],
        description="Breaking change requires migration guide",
    ),
    "new_cli_command": DocTrigger(
        name="new_cli_command",
        pattern=r"^\+.*\.add_argument\(['\"]--[a-z-]+['\"]",
        severity="CRITICAL",
        required_docs=["README.md", "docs/QUICKSTART.md"],
        exclude_paths=["tests/"],
        description="New CLI argument requires documentation",
        file_filters=["*.py"],
    ),
    "new_dependency": DocTrigger(
        name="new_dependency",
        pattern=r"^\+[a-z0-9-]+[>=<]",
        severity="MAJOR",
        required_docs=["README.md", "docs/QUICKSTART.md"],
        exclude_paths=[],
        description="New dependency requires installation docs update",
        file_filters=["requirements.txt", "pyproject.toml", "package.json"],
    ),
    # MAJOR severity - Warn + fail
    "large_code_change": DocTrigger(
        name="large_code_change",
        pattern=r"^[\+\-]",  # Any addition/deletion
        severity="MAJOR",
        required_docs=["CHANGELOG.md"],
        exclude_paths=["tests/", "docs/"],
        description="Significant code change requires CHANGELOG entry",
        file_filters=["*.py", "*.ts", "*.tsx", "*.js", "*.jsx"],
    ),
    "schema_change": DocTrigger(
        name="schema_change",
        pattern=r"^\+.*(CREATE TABLE|ALTER TABLE|Column\(|add_column\()",
        severity="MAJOR",
        required_docs=["docs/database/schema.md", "CHANGELOG.md"],
        exclude_paths=["tests/"],
        description="Database schema change requires documentation",
        file_filters=["*.sql", "**/models.py", "**/migrations/*.py"],
    ),
    "error_handling": DocTrigger(
        name="error_handling",
        pattern=r"^\+.*(raise\s+\w+Error|except\s+\w+Error)",
        severity="MAJOR",
        required_docs=["docs/TROUBLESHOOTING.md"],
        exclude_paths=["tests/"],
        description="New error handling should be documented",
        file_filters=["*.py"],
    ),
    "config_default": DocTrigger(
        name="config_default",
        pattern=r"^\+.*=\s*os\.getenv\(['\"][A-Z_]+['\"]\s*,\s*['\"]",
        severity="MAJOR",
        required_docs=["docs/CONFIGURATION.md"],
        exclude_paths=["tests/"],
        description="Configuration default change requires documentation",
        file_filters=["*.py"],
    ),
    "docker_change": DocTrigger(
        name="docker_change",
        pattern=r"^\+.*(FROM|RUN|COPY|ENV|EXPOSE)",
        severity="MAJOR",
        required_docs=["README.md"],
        exclude_paths=[],
        description="Docker configuration change requires documentation",
        file_filters=["Dockerfile", "compose.yaml", "compose.yml"],
    ),
    # TypeScript/JavaScript triggers
    "new_ts_function": DocTrigger(
        name="new_ts_function",
        pattern=r"^\+\s*(?:export\s+)?(?:async\s+)?function\s+[a-z][a-zA-Z0-9_]*\(",
        severity="CRITICAL",
        required_docs=["docs/reference/{module}.md", "CHANGELOG.md"],
        exclude_paths=["tests/", "node_modules/", "__tests__/"],
        description="New TypeScript function requires documentation",
        file_filters=["*.ts", "*.tsx"],
    ),
    "new_ts_interface": DocTrigger(
        name="new_ts_interface",
        pattern=r"^\+\s*(?:export\s+)?interface\s+[A-Z][a-zA-Z0-9_]*",
        severity="MAJOR",
        required_docs=["docs/reference/{module}.md"],
        exclude_paths=["tests/", "node_modules/"],
        description="New Interface requires schema documentation",
        file_filters=["*.ts", "*.tsx"],
    ),
    "new_ts_type": DocTrigger(
        name="new_ts_type",
        pattern=r"^\+\s*(?:export\s+)?type\s+[A-Z][a-zA-Z0-9_]*\s*=",
        severity="MAJOR",
        required_docs=["docs/reference/{module}.md"],
        exclude_paths=["tests/", "node_modules/"],
        description="New Type alias requires documentation",
        file_filters=["*.ts", "*.tsx"],
    ),
    "new_react_component": DocTrigger(
        name="new_react_component",
        pattern=r"^\+\s*(?:export\s+)?(?:default\s+)?(?:function|const)\s+[A-Z][a-zA-Z0-9_]*",
        severity="MAJOR",
        required_docs=["docs/reference/{module}.md", "CHANGELOG.md"],
        exclude_paths=["tests/", "node_modules/"],
        description="New React component requires documentation",
        file_filters=["*.tsx", "*.jsx"],
    ),
    "new_npm_dependency": DocTrigger(
        name="new_npm_dependency",
        pattern=r'^\+\s*"[a-z0-9@/-]+"\s*:\s*"[\^~]?\d+',
        severity="MAJOR",
        required_docs=["README.md"],
        exclude_paths=[],
        description="New NPM package requires installation docs update",
        file_filters=["package.json"],
    ),
}

# Complexity thresholds for different doc types
DOC_COMPLEXITY_MAP: dict[str, ComplexityLevel] = {
    "CHANGELOG.md": "simple",
    "README.md": "medium",
    "docs/QUICKSTART.md": "medium",
    "docs/CONFIGURATION.md": "medium",
    "docs/TROUBLESHOOTING.md": "medium",
    "docs/reference/": "complex",  # API docs need high accuracy
    "docs/MIGRATION.md": "complex",  # Breaking changes need precision
    ".env.example": "simple",
}

# Kilo CLI configuration
VALID_AGENTS = {"ask", "code", "coder"}
VALID_VARIANTS = {"minimal", "low", "high", "max"}
KILO_IDLE_TIMEOUT = int(os.getenv("KILO_IDLE_TIMEOUT", "120"))
KILO_HARD_TIMEOUT = int(os.getenv("KILO_HARD_TIMEOUT", "600"))
KILO_POLL_INTERVAL = 1
MAX_RETRIES = 3
RETRYABLE_EXIT_CODES = {137, 143}  # SIGKILL, SIGTERM

# =============================================================================
# TEMPLATE LOADING
# =============================================================================

# Maps doc path patterns to template filenames
DOC_TEMPLATE_MAP: dict[str, str] = {
    "CHANGELOG.md": "CHANGELOG_TEMPLATE.md",
    "docs/reference/": "API_REFERENCE_TEMPLATE.md",
    "docs/CONFIGURATION.md": "CONFIGURATION_TEMPLATE.md",
    "docs/database/schema.md": "DATABASE_SCHEMA_TEMPLATE.md",
    "docs/TROUBLESHOOTING.md": "TROUBLESHOOTING_TEMPLATE.md",
    "docs/QUICKSTART.md": "QUICKSTART_TEMPLATE.md",
    "README.md": "PROJECT_README_TEMPLATE.md",
}

# Module-level cache for loaded templates
_template_cache: dict[str, str] = {}


def load_template(template_name: str) -> str:
    """
    Load a documentation template by name.

    Resolves template path from:
    1. SCRIPT_DIR.parent / "templates" / "scaffold" / "docs" / template_name
    2. SCRIPT_DIR.parent / "templates" / "docs" / template_name (fallback)

    Returns the template content as a string, or empty string if not found.
    Caches loaded templates to avoid repeated disk reads.
    """
    if template_name in _template_cache:
        return _template_cache[template_name]

    search_paths = [
        SCRIPT_DIR.parent / "templates" / "scaffold" / "docs" / template_name,
        SCRIPT_DIR.parent / "templates" / "docs" / template_name,
    ]

    for path in search_paths:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                _template_cache[template_name] = content
                return content
            except OSError:
                continue

    _template_cache[template_name] = ""
    return ""


def get_template_for_doc(doc_path: str) -> str:
    """
    Get the template content for a given doc path.

    Matches doc_path against DOC_TEMPLATE_MAP patterns and loads
    the corresponding template.

    Returns template content or empty string if no match.
    """
    for pattern, template_name in DOC_TEMPLATE_MAP.items():
        if pattern in doc_path or doc_path.endswith(pattern):
            return load_template(template_name)
    return ""


# =============================================================================
# GIT HELPERS
# =============================================================================


def get_git_root(cwd: Path | None = None) -> Path | None:
    """Get git repository root.

    Args:
        cwd: Directory to run git in. Defaults to PROJECT_ROOT.
    """
    try:
        git_path = shutil.which("git")
        if not git_path:
            return None
        run_cwd = str(cwd) if cwd else str(PROJECT_ROOT)
        result = subprocess.run(
            [git_path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=run_cwd,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_staged_diff(cwd: Path | None = None) -> str:
    """Get git diff of staged changes.

    Args:
        cwd: Directory to run git in. Defaults to PROJECT_ROOT.
    """
    try:
        git_path = shutil.which("git")
        if not git_path:
            return ""
        run_cwd = str(cwd) if cwd else str(PROJECT_ROOT)
        result = subprocess.run(
            [git_path, "diff", "--cached", "--unified=3"],
            capture_output=True,
            text=True,
            check=True,
            cwd=run_cwd,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def get_staged_files(cwd: Path | None = None) -> list[str]:
    """Get list of staged file paths.

    Args:
        cwd: Directory to run git in. Defaults to PROJECT_ROOT.
    """
    try:
        git_path = shutil.which("git")
        if not git_path:
            return []
        run_cwd = str(cwd) if cwd else str(PROJECT_ROOT)
        result = subprocess.run(
            [git_path, "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            cwd=run_cwd,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def get_diff_stats(cwd: Path | None = None) -> tuple[int, int]:
    """Get total lines added and removed.

    Args:
        cwd: Directory to run git in. Defaults to PROJECT_ROOT.
    """
    try:
        git_path = shutil.which("git")
        if not git_path:
            return 0, 0
        run_cwd = str(cwd) if cwd else str(PROJECT_ROOT)
        result = subprocess.run(
            [git_path, "diff", "--cached", "--numstat"],
            capture_output=True,
            text=True,
            check=True,
            cwd=run_cwd,
        )
        added, removed = 0, 0
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    with contextlib.suppress(ValueError):
                        added += int(parts[0]) if parts[0] != "-" else 0
                        removed += int(parts[1]) if parts[1] != "-" else 0
        return added, removed
    except subprocess.CalledProcessError:
        return 0, 0


# =============================================================================
# TRIGGER DETECTION
# =============================================================================


def should_skip_file(filepath: str, exclude_paths: list[str]) -> bool:
    """Check if file should be skipped based on exclude patterns."""
    return any(pattern in filepath for pattern in exclude_paths)


def matches_file_filter(filepath: str, file_filters: list[str]) -> bool:
    """Check if file matches any filter pattern."""
    if not file_filters:
        return True  # No filter = match all
    path = Path(filepath)
    for pattern in file_filters:
        if pattern.startswith("**/"):
            # Match anywhere in path
            if path.match(pattern):
                return True
        elif "*" in pattern:
            # Glob pattern
            if path.match(pattern):
                return True
        elif filepath.endswith(pattern.replace("*", "")):
            return True
    return False


def analyze_diff_for_triggers(diff: str, staged_files: list[str]) -> list[DocViolation]:
    """Analyze git diff and detect documentation triggers."""
    violations: list[DocViolation] = []
    current_file = ""
    line_number = 0

    for line in diff.split("\n"):
        # Track current file from diff headers
        if line.startswith("+++"):
            current_file = line[6:]  # Remove "+++ b/"
            line_number = 0
            continue

        # Track line numbers
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            if match:
                line_number = int(match.group(1))
            continue

        if line.startswith("+") and not line.startswith("+++"):
            line_number += 1

        # Check each trigger
        for trigger_name, trigger in DOCUMENTATION_TRIGGERS.items():
            # Skip large_code_change - handled separately with threshold check
            if trigger_name == "large_code_change":
                continue

            # Skip if file doesn't match filter
            if not matches_file_filter(current_file, trigger.file_filters):
                continue

            # Skip excluded paths
            if should_skip_file(current_file, trigger.exclude_paths):
                continue

            # Match pattern
            if re.search(trigger.pattern, line):
                violations.append(
                    DocViolation(
                        trigger_name=trigger_name,
                        severity=trigger.severity,
                        source_file=current_file,
                        matched_line=line.strip(),
                        required_docs=trigger.required_docs,
                        description=trigger.description,
                        line_number=line_number,
                    )
                )

    # Special case: large_code_change trigger requires threshold check
    threshold = int(os.getenv("KILO_DOCS_THRESHOLD", "50"))
    added, removed = get_diff_stats(cwd=PROJECT_ROOT)
    if added + removed > threshold:
        # Check if any non-doc, non-test files changed
        code_files = [
            f
            for f in staged_files
            if not any(skip in f for skip in ["tests/", "test_", "docs/", ".md", ".txt"])
        ]
        if code_files and not any(v.trigger_name == "large_code_change" for v in violations):
            # Create one violation per source file (max 5) so each source_file
            # is a valid single path for Kilo --file flag attachment.
            for cf in code_files[:5]:
                violations.append(
                    DocViolation(
                        trigger_name="large_code_change",
                        severity="MAJOR",
                        source_file=cf,
                        matched_line=f"{added} additions, {removed} deletions",
                        required_docs=["CHANGELOG.md"],
                        description=(
                            f"Large code change ({added + removed} lines) requires CHANGELOG entry"
                        ),
                    )
                )

    return violations


def group_violations_by_doc(violations: list[DocViolation]) -> dict[str, DocRequirement]:
    """Group violations by required documentation file."""
    doc_map: dict[str, DocRequirement] = {}

    for violation in violations:
        for doc_path in violation.required_docs:
            # Resolve {module} placeholders
            resolved_path = doc_path
            if "{module}" in doc_path:
                # Extract module from source file path
                source_path = Path(violation.source_file)
                if source_path.parts and "src" in source_path.parts:
                    src_idx = source_path.parts.index("src")
                    if len(source_path.parts) > src_idx + 1:
                        module = source_path.parts[src_idx + 1]
                        resolved_path = doc_path.replace("{module}", module)
                else:
                    # Fallback: extract from file path relative to project root
                    # For files outside src/, use first directory component
                    if len(source_path.parts) > 0:
                        module = source_path.parts[0]
                        resolved_path = doc_path.replace("{module}", module)

            if resolved_path not in doc_map:
                doc_file = PROJECT_ROOT / resolved_path
                doc_map[resolved_path] = DocRequirement(
                    doc_path=resolved_path,
                    severity=violation.severity,
                    triggers=[violation],
                    exists=doc_file.exists(),
                    last_modified=datetime.fromtimestamp(doc_file.stat().st_mtime)
                    if doc_file.exists()
                    else None,
                )
            else:
                doc_map[resolved_path].triggers.append(violation)
                # Escalate severity if higher
                if violation.severity == "CRITICAL":
                    doc_map[resolved_path].severity = "CRITICAL"
                elif (
                    violation.severity == "MAJOR" and doc_map[resolved_path].severity != "CRITICAL"
                ):
                    doc_map[resolved_path].severity = "MAJOR"

    return doc_map


# =============================================================================
# DOCUMENTATION VERIFICATION
# =============================================================================


def check_doc_updated_in_commit(doc_path: str, staged_files: list[str]) -> bool:
    """Check if documentation file is staged in current commit."""
    return doc_path in staged_files


def _strip_markdown_fences(content: str) -> str:
    """
    Strip markdown code fences from model output.

    Some models (e.g., Step 3.5 Flash) wrap their output in ```markdown ... ```
    which breaks content validation. This strips such fences while preserving
    the actual content.
    """
    stripped = content.strip()
    # Check for opening fence with optional language tag
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Remove opening fence line
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing fence if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return content


def get_doc_complexity(doc_path: str) -> ComplexityLevel:
    """Determine complexity level for documentation type."""
    for pattern, complexity in DOC_COMPLEXITY_MAP.items():
        if doc_path.startswith(pattern) or pattern in doc_path:
            return complexity
    return "medium"  # Default


# =============================================================================
# AGENT SELECTION
# =============================================================================


def select_documentation_agent(complexity: ComplexityLevel) -> dict[str, Any]:
    """
    Select documentation agent from database based on complexity.

    Args:
        complexity: Task complexity level (simple, medium, complex)

    Returns:
        Agent dict with api_id, name, provider, etc.

    Raises:
        NoAgentAvailableError: If no suitable agent found
    """
    try:
        agent = select_agent("documentation", complexity)
        if not agent:
            raise NoAgentAvailableError(
                f"No documentation agent available for complexity={complexity}"
            )
        return agent
    except Exception as e:
        print(f"Error selecting documentation agent: {e}", file=sys.stderr)
        raise


# =============================================================================
# ENFORCEMENT
# =============================================================================


def enforce_documentation(
    requirements: dict[str, DocRequirement], staged_files: list[str]
) -> tuple[bool, list[str]]:
    """
    Enforce documentation requirements.

    Returns:
        (passed, error_messages)
    """
    errors: list[str] = []
    critical_missing = False
    major_missing = False

    for doc_path, req in requirements.items():
        # Check if doc is updated in this commit
        if check_doc_updated_in_commit(doc_path, staged_files):
            continue

        # Not updated - report violation
        trigger_count = len(req.triggers)
        severity_emoji = {"CRITICAL": "🔴", "MAJOR": "🟡", "MINOR": "🟢"}[req.severity]

        error_msg = (
            f"{severity_emoji} [{req.severity}] {doc_path}"
            f" must be updated ({trigger_count} trigger(s))"
        )
        errors.append(error_msg)

        if req.severity == "CRITICAL":
            critical_missing = True
        elif req.severity == "MAJOR":
            major_missing = True

    # Determine pass/fail
    passed = not critical_missing and not major_missing
    return passed, errors


# =============================================================================
# REPORTING
# =============================================================================


def print_detection_report(
    violations: list[DocViolation],
    requirements: dict[str, DocRequirement],
    staged_files: list[str],
) -> None:
    """Print human-readable detection report."""
    print("\n" + "=" * 60)
    print("DOCUMENTATION ENFORCEMENT REPORT")
    print("=" * 60)

    if not violations:
        print("\n✓ No documentation updates required")
        return

    print(f"\n📝 Detected {len(violations)} trigger(s) requiring documentation updates")

    # Group by severity
    critical = [v for v in violations if v.severity == "CRITICAL"]
    major = [v for v in violations if v.severity == "MAJOR"]
    minor = [v for v in violations if v.severity == "MINOR"]

    if critical:
        print(f"\n🔴 CRITICAL: {len(critical)} trigger(s)")
        for v in critical[:5]:
            print(f"   - {v.description}")
            print(f"     File: {v.source_file}:{v.line_number or '?'}")

    if major:
        print(f"\n🟡 MAJOR: {len(major)} trigger(s)")
        for v in major[:5]:
            print(f"   - {v.description}")

    if minor:
        print(f"\n🟢 MINOR: {len(minor)} trigger(s)")

    # Required documentation
    print(f"\n📄 Required Documentation Updates: {len(requirements)}")
    for doc_path, req in requirements.items():
        updated = check_doc_updated_in_commit(doc_path, staged_files)
        status = "✓ Updated" if updated else "✗ Missing"
        severity_emoji = {"CRITICAL": "🔴", "MAJOR": "🟡", "MINOR": "🟢"}[req.severity]
        print(f"   {severity_emoji} {status} - {doc_path} ({len(req.triggers)} trigger(s))")


def print_json_report(
    violations: list[DocViolation], requirements: dict[str, DocRequirement]
) -> None:
    """Print JSON report for machine consumption."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "violations": [
            {
                "trigger": v.trigger_name,
                "severity": v.severity,
                "source_file": v.source_file,
                "line": v.line_number,
                "description": v.description,
                "required_docs": v.required_docs,
            }
            for v in violations
        ],
        "requirements": [
            {
                "doc_path": doc_path,
                "severity": req.severity,
                "exists": req.exists,
                "trigger_count": len(req.triggers),
                "triggers": [t.trigger_name for t in req.triggers],
            }
            for doc_path, req in requirements.items()
        ],
    }
    print(json.dumps(report, indent=2))


# =============================================================================
# KILO CLI INTEGRATION
# =============================================================================


def find_kilo_executable() -> str | None:
    """Find kilo executable with TOCTOU protection."""
    # Check KILO_PATH env var first
    kilo_path_env = os.getenv("KILO_PATH")
    if kilo_path_env:
        kilo_path_env = os.path.abspath(kilo_path_env)
        if os.path.isfile(kilo_path_env) and os.access(kilo_path_env, os.X_OK):
            return kilo_path_env

    # Check common locations
    paths_to_check = [
        os.path.expanduser("~/.npm-global/bin/kilo"),
        shutil.which("kilo"),
        os.path.expanduser("~/.local/bin/kilo"),
        "/usr/local/bin/kilo",
    ]
    for path in paths_to_check:
        if path:
            path = os.path.abspath(path)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None


def build_kilo_command(
    kilo_path: str,
    model: str,
    agent: str,
    variant: str,
    file_paths: list[Path] | None = None,
) -> list[str]:
    """Build kilo CLI command with validation."""
    # Validate model format
    cli_model = model if model.startswith("kilo/") else f"kilo/{model}"
    if not re.match(r"^kilo/[a-zA-Z0-9/_.\-:]+$", cli_model):
        raise ValueError(f"Invalid model format: {cli_model}")

    if variant and variant not in VALID_VARIANTS:
        raise ValueError(f"Invalid variant: {variant}")

    if agent and agent not in VALID_AGENTS:
        raise ValueError(f"Invalid agent: {agent}")

    args = [kilo_path, "run", "--format", "json", "--auto"]
    args.extend(["--model", cli_model])

    if variant and variant in VALID_VARIANTS:
        args.extend(["--variant", variant])

    if agent and agent in VALID_AGENTS:
        args.extend(["--agent", agent])

    if file_paths:
        for fpath in file_paths:
            args.extend(["--file", str(fpath)])

    return args


def parse_kilo_jsonl(output: str) -> dict[str, Any]:
    """Parse Kilo JSONL output."""
    import json

    result_text = []
    session_id = ""
    input_tokens = 0
    output_tokens = 0
    cost = 0.0
    has_step_finish = False

    for line in output.strip().split("\n"):
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue

        # Extract session ID
        if "sessionID" in obj:
            session_id = obj["sessionID"]
        elif "session_id" in obj:
            session_id = obj["session_id"]

        event_type = obj.get("type", "")

        # Handle errors
        if event_type == "error":
            error_data = obj.get("error", {})
            error_name = error_data.get("name", "UnknownError")
            error_msg = error_data.get("data", {}).get("message", str(error_data))
            raise RuntimeError(f"Kilo API error ({error_name}): {error_msg}")

        # Collect text
        if event_type == "text":
            text = obj.get("text", "")
            if not text and "part" in obj:
                text = obj["part"].get("text", "")
            if text:
                result_text.append(text)

        # Collect tokens/cost
        elif event_type == "step_finish":
            has_step_finish = True
            part = obj.get("part", {})
            tokens = obj.get("tokens") or part.get("tokens", {})
            input_tokens += tokens.get("input", 0)
            output_tokens += tokens.get("output", 0)
            cost += obj.get("cost") or part.get("cost", 0.0)

    if not has_step_finish:
        raise RuntimeError("Kilo run incomplete - no step_finish event")

    return {
        "result": "".join(result_text),
        "session_id": session_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
    }


def _monitor_process(proc, idle_timeout, hard_timeout, poll_interval, stream_output=False):
    """
    Monitor subprocess with liveness checking and optional streaming.

    Uses reader threads to avoid blocking on pipe reads.
    Tracks BOTH stdout AND stderr growth to detect progress.

    Args:
        proc: subprocess.Popen instance
        idle_timeout: seconds without output before killing
        hard_timeout: absolute max seconds before killing
        poll_interval: seconds between health checks
        stream_output: if True, stream JSONL text events to stderr in real-time

    Returns:
        (stdout_bytes, stderr_bytes, returncode)

    Raises:
        TimeoutError: if idle or hard timeout exceeded
    """
    import queue
    import threading

    stdout_queue = queue.Queue()
    stderr_queue = queue.Queue()

    def reader_thread(stream, q):
        """Read stream in chunks, push to queue."""
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                q.put(("data", chunk))
        except Exception as e:
            q.put(("error", e))
        finally:
            q.put(("eof", None))

    # Start reader threads
    stdout_thread = threading.Thread(target=reader_thread, args=(proc.stdout, stdout_queue))
    stderr_thread = threading.Thread(target=reader_thread, args=(proc.stderr, stderr_queue))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()

    # Monitor loop
    start_time = time.time()
    last_output_time = start_time
    stdout_chunks = []
    stderr_chunks = []
    text_buffer = ""  # For streaming text extraction

    while proc.poll() is None:
        time.sleep(poll_interval)

        got_output = False

        # Drain stdout queue
        while not stdout_queue.empty():
            msg_type, data = stdout_queue.get_nowait()
            if msg_type == "data":
                stdout_chunks.append(data)
                got_output = True

                # Stream text events in real-time (extract from JSONL)
                if stream_output:
                    text_buffer += data.decode("utf-8", errors="replace")
                    # Parse complete JSONL lines
                    while "\n" in text_buffer:
                        line, text_buffer = text_buffer.split("\n", 1)
                        if line.strip():
                            try:
                                obj = json.loads(line)
                                # Extract and print text events
                                if obj.get("type") == "text":
                                    text = obj.get("text", "") or obj.get("part", {}).get(
                                        "text", ""
                                    )
                                    if text:
                                        print(text, end="", file=sys.stderr, flush=True)
                            except json.JSONDecodeError:
                                pass  # Not valid JSON, skip

        # Drain stderr queue - ALSO counts as progress
        while not stderr_queue.empty():
            msg_type, data = stderr_queue.get_nowait()
            if msg_type == "data":
                stderr_chunks.append(data)
                got_output = True  # stderr counts as progress too

        if got_output:
            last_output_time = time.time()

        # Check timeouts
        elapsed = time.time() - start_time
        idle = time.time() - last_output_time

        if idle > idle_timeout:
            proc.kill()
            proc.wait()
            if stream_output:
                print(f"\n[TIMEOUT] Idle: no output for {idle:.0f}s", file=sys.stderr)
            raise TimeoutError(f"Idle timeout: no output for {idle:.0f}s (limit {idle_timeout}s)")

        if elapsed > hard_timeout:
            proc.kill()
            proc.wait()
            if stream_output:
                print(f"\n[TIMEOUT] Hard limit: {elapsed:.0f}s", file=sys.stderr)
            raise TimeoutError(
                f"Hard timeout: total runtime {elapsed:.0f}s (limit {hard_timeout}s)"
            )

    # Collect remaining output
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    while not stdout_queue.empty():
        msg_type, data = stdout_queue.get_nowait()
        if msg_type == "data":
            stdout_chunks.append(data)

    while not stderr_queue.empty():
        msg_type, data = stderr_queue.get_nowait()
        if msg_type == "data":
            stderr_chunks.append(data)

    if stream_output:
        print("", file=sys.stderr)  # Newline after streaming

    return (b"".join(stdout_chunks), b"".join(stderr_chunks), proc.returncode)


async def run_kilo(
    prompt: str,
    model: str,
    agent: str,
    variant: str,
    file_paths: list[Path] | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Execute Kilo CLI with monitored process execution.

    Args:
        prompt: Prompt to send
        model: Model API ID (e.g., "anthropic/claude-sonnet-4.5")
        agent: Agent type ("ask", "code")
        variant: Reasoning level ("minimal", "low", "high", "max")
        file_paths: Files to attach
        verbose: Enable verbose output

    Returns:
        Dict with 'result', 'session_id', 'input_tokens', 'output_tokens', 'cost'
    """
    kilo_path = find_kilo_executable()
    if not kilo_path:
        raise RuntimeError("Kilo executable not found. Is it installed?")

    cmd = build_kilo_command(
        kilo_path=kilo_path,
        model=model,
        agent=agent,
        variant=variant,
        file_paths=file_paths,
    )

    if verbose:
        print(f"[KILO] Running: {' '.join(cmd)}", file=sys.stderr)

    # Retry loop
    for attempt in range(MAX_RETRIES):
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )

            # Write prompt
            try:
                if process.stdin:
                    process.stdin.write(prompt.encode("utf-8"))
                    process.stdin.flush()
                    process.stdin.close()
            except (BrokenPipeError, OSError):
                pass

            # Monitor in executor with live streaming
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                stdout, stderr, returncode = await loop.run_in_executor(
                    executor,
                    _monitor_process,
                    process,
                    KILO_IDLE_TIMEOUT,
                    KILO_HARD_TIMEOUT,
                    KILO_POLL_INTERVAL,
                    verbose,  # stream_output = verbose
                )

            # Retry on transient failures
            if returncode in RETRYABLE_EXIT_CODES and attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt
                print(
                    f"⏳ Kilo transient failure (exit {returncode}). Retrying in {wait_time}s...",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait_time)
                continue

            if returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")[:200]
                raise RuntimeError(f"Kilo failed (exit {returncode}): {error_msg}")

            output = stdout.decode("utf-8", errors="replace")

            if verbose:
                print(f"[KILO] Output: {len(output)} chars", file=sys.stderr)

            return parse_kilo_jsonl(output)

        except TimeoutError as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2**attempt
                print(f"⏳ {e}. Retrying in {wait_time}s...", file=sys.stderr)
                await asyncio.sleep(wait_time)
                continue
            raise

    raise RuntimeError(f"Kilo failed after {MAX_RETRIES} attempts")


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

CHANGELOG_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a CHANGELOG entry generator. You output ONLY the changelog
entry text. You NEVER output conversational responses, greetings, or explanations.
Your entire output is a valid Keep a Changelog format entry.

**Git Diff:**
{git_diff}

**Triggered Changes:**
{violations}

**Requirements:**
1. Follow Keep a Changelog format (https://keepachangelog.com/)
2. Categorize: Added, Changed, Deprecated, Removed, Fixed, Security
3. Use present tense ("Add feature" not "Added feature")
4. Be specific and technical for developers
5. Include relevant file/function names

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
I can help you write a changelog entry. What would you like to document?
```

**GOOD output (ALWAYS do this):**
```
### Added - New user API endpoints (2026-03-23)
- Add `get_user(user_id)` function in `src/api.py` to retrieve user details
- Add `update_user(user_id, data)` function to modify user records
```

Now generate the CHANGELOG entry. Start your output with "###" and continue:

###"""

API_DOCS_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a documentation generator. You output ONLY markdown documentation.
You NEVER output conversational text, greetings, or explanations.
You NEVER say "I am ready to assist". Your entire output is valid markdown documentation.

**Source Files:**
{source_files}

**Git Diff:**
{git_diff}

**Functions/Classes to Document:**
{violations}

**Requirements:**
1. Document all public functions and classes
2. Include type hints in signatures
3. Show usage examples
4. Document exceptions raised
5. Cross-reference related functions
6. Use clear, concise language

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
I'm ready to assist with your documentation needs. How can I help?
```

**GOOD output (ALWAYS do this):**
```markdown
## get_user

**Signature:** `get_user(user_id: int) -> dict`

**Description:** Retrieves user details by ID from the database.

**Parameters:**
- `user_id` (int): Unique identifier for the user

**Returns:**
- `dict`: User object with `id` and `name` fields

**Example:**
```python
user = get_user(123)
print(user['name'])
```
```

Now generate the documentation. Start your output with "##" and continue with the function name:

##"""

ENV_VAR_DOCS_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are an environment variable documentation generator.
You output ONLY markdown documentation. You NEVER output conversational text or greetings.
Your entire output is valid markdown documenting environment variables.

**Source Files:**
{source_files}

**Git Diff:**
{git_diff}

**Environment Variables Found:**
{violations}

**Requirements:**
1. List each variable with description
2. Include data type and default value
3. Specify if required or optional
4. Show example values

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
I'm ready to help document your environment variables.
```

**GOOD output (ALWAYS do this):**
```markdown
### `DATABASE_URL`
- **Type:** string
- **Required:** Yes
- **Default:** None
- **Description:** PostgreSQL connection string
- **Example:** `DATABASE_URL=postgresql://user:pass@localhost/db`
```

Now generate the documentation. Start your output with "###" and continue:

###"""

MIGRATION_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a migration guide generator. You output ONLY markdown documentation
for migration guides. You NEVER output conversational text, greetings, or explanations.
Your entire output is a valid migration guide.

**Git Diff:**
{git_diff}

**Breaking Changes Detected:**
{violations}

**Requirements:**
1. Document all breaking changes with before/after code examples
2. Provide numbered, atomic migration steps
3. Include rollback procedure
4. List affected components with impact level
5. Include deprecation timeline if applicable

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
I'd be happy to help you create a migration guide for these changes.
```

**GOOD output (ALWAYS do this):**
```markdown
## Breaking Changes

### Renamed `process_payment` to `execute_payment`

**Before:**
```python
result = process_payment(order_id, amount)
```

**After:**
```python
result = execute_payment(order_id, amount, currency="USD")
```

## Migration Steps

1. Update all calls to `process_payment` to use `execute_payment`
2. Add the required `currency` parameter to each call
```

Now generate the migration guide. Start your output with "##" and continue:

##"""

SCHEMA_DOCS_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a database schema documentation generator.
You output ONLY markdown documentation for database schemas.
You NEVER output conversational text, greetings, or explanations.
Your entire output is valid schema documentation.

**Source Files:**
{source_files}

**Git Diff:**
{git_diff}

**Schema Changes Detected:**
{violations}

**Requirements:**
1. Document all table changes (new tables, columns, indexes)
2. Include column types, nullability, defaults, and descriptions
3. Document relationships and foreign keys
4. Include migration SQL for the changes
5. Note data integrity constraints

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
Let me help you document your database schema changes.
```

**GOOD output (ALWAYS do this):**
```markdown
## Tables

### users

**Purpose:** Stores user account information.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | `gen_random_uuid()` | Primary key |
| `email` | VARCHAR(255) | NO | — | User email address |
```

Now generate the schema documentation. Start your output with "##" and continue:

##"""

README_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a README/documentation updater. You output ONLY the markdown
section(s) that need to be added or updated. You NEVER output conversational text,
greetings, or explanations. Your entire output is valid markdown.

**Current File:** {doc_path}

**Git Diff:**
{git_diff}

**Changes Requiring Documentation:**
{violations}

**Requirements:**
1. Document new features, endpoints, or CLI commands
2. Include usage examples with code blocks
3. Update feature lists and tables
4. Be specific and technical for developers
5. Follow the existing document structure

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
Here's an updated section for your README with the new changes.
```

**GOOD output (ALWAYS do this):**
```markdown
## New Feature: User Authentication

JWT-based authentication for all API endpoints.

### Usage

```bash
curl -X POST http://localhost:8000/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{{"username": "admin", "password": "secret"}}'
```
```

Now generate the documentation section. Start your output with "##" and continue:

##"""


CONFIGURATION_GUIDE_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a configuration guide generator. You output ONLY markdown
documentation for a configuration guide. You NEVER output conversational text,
greetings, or explanations. Your entire output is valid markdown.

**IMPORTANT:** `.env.example` is the AUTHORITATIVE variable reference.
This configuration guide documents HOW to configure the service and WHY certain
configurations exist — it does NOT list individual variables.

**Source Files:**
{source_files}

**Git Diff:**
{git_diff}

**Changes Requiring Documentation:**
{violations}

**Requirements:**
1. Document HOW to get credentials for new services/APIs
2. Explain environment-specific setup differences (dev vs production)
3. Document architecture context and configuration philosophy
4. Reference `.env.example` for the actual variable list — do NOT duplicate variable tables here
5. Include troubleshooting tips for configuration problems
6. Follow the existing document structure

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
### `DATABASE_URL`
- **Type:** string
- **Required:** Yes
```

**GOOD output (ALWAYS do this):**
```markdown
## Getting Credentials

### Database Access

**Why needed:** The service stores user session data and API logs.

**Options:**

**Shared postgres-main (recommended):**
```bash
DATABASE_URL=postgresql://myapp:password@postgres-main:5432/myapp
```

**Local PostgreSQL:**
```bash
DATABASE_URL=postgresql://localhost:5432/myapp_dev
```

All variables are documented in `.env.example` with inline comments.
```

Now generate the configuration guide section. Start your output with "##" and continue:

##"""

TROUBLESHOOTING_PROMPT_TEMPLATE = """
SYSTEM ROLE: You are a troubleshooting guide generator. You output ONLY markdown
documentation for a troubleshooting guide. You NEVER output conversational text,
greetings, or explanations. Your entire output is valid markdown with
issue/cause/solution structure.

**Source Files:**
{source_files}

**Git Diff:**
{git_diff}

**Changes Requiring Documentation:**
{violations}

**Requirements:**
1. Document each issue with: Symptoms, Cause, Solution, Prevention
2. Include specific error messages users might encounter
3. Provide actionable diagnostic commands
4. Include code examples for fixes
5. Group by issue category (startup, runtime, configuration, performance)
6. Follow the existing document structure

**Reference Structure (follow this format):**
{template_structure}

**BAD output (NEVER do this):**
```
Here are some tips for debugging your application. You might want to check the logs.
```

**GOOD output (ALWAYS do this):**
```markdown
## Common Issues

### Issue: Service returns 500 on /api/process

**Symptoms:**
- HTTP 500 response from `/api/process` endpoint
- Error in logs: `RuntimeError: Worker pool exhausted`

**Cause:**
All background workers are busy processing long-running tasks.

**Solution:**
```bash
# Increase worker pool size
WORKER_POOL_SIZE=10 uvicorn src.main:app --reload

# Or check current worker status
curl http://localhost:8000/health | jq .workers
```

**Prevention:**
Set `WORKER_POOL_SIZE` in `.env` to match expected concurrent load.
```

Now generate the troubleshooting guide section. Start your output with "##" and continue:

##"""


def _calculate_code_echo_ratio(content: str, requirement: DocRequirement) -> float:
    """
    Calculate how much the output 'echoes' the raw input code.

    Returns a ratio 0.0-1.0 where higher means more similar (bad).
    """
    raw_source = "\n".join([v.matched_line for v in requirement.triggers])
    return difflib.SequenceMatcher(None, raw_source, content).ratio()


def validate_generated_content(
    content: str,
    doc_path: str,
    requirement: DocRequirement | None = None,
) -> tuple[bool, str]:
    """
    Production-grade documentation validation.

    Checks for:
    1. Minimum length and markdown formatting
    2. Conversational fillers and AI "monologues"
    3. Unresolved placeholders (e.g., [Insert Description])
    4. Semantic relevance (ensuring trigger identifiers are present)
    5. Code echo detection (prevent 1:1 copying of source)
    6. .env format strictness

    Returns:
        (is_valid, reason) — True if content passes quality checks.
    """
    stripped_content = content.strip()

    # --- 1. Minimum Length Check ---
    min_lengths = {
        "CHANGELOG": 50,
        "docs/reference/": 100,
        "docs/CONFIGURATION": 80,
        ".env.example": 30,
    }
    min_len = 60  # default
    for pattern, length in min_lengths.items():
        if pattern in doc_path:
            min_len = length
            break

    if len(stripped_content) < min_len:
        return False, f"Content too short ({len(stripped_content)} chars, minimum {min_len})"

    # --- 2. Placeholder Detection (Lazy Agent Check) ---
    placeholder_patterns = [
        (r"\[(Insert|Describe|Enter|Add|Your)[^\]]*\]", "bracketed placeholder"),
        (r"<(insert|describe|add|your)[^>]*>", "angle bracket placeholder"),
        (r"TODO:\s*\w", "TODO marker"),  # Must have content after TODO:
        (r"FIXME:\s*\w", "FIXME marker"),
        (r"INSERT_HERE", "INSERT_HERE marker"),
    ]
    for pattern, description in placeholder_patterns:
        if re.search(pattern, stripped_content, re.IGNORECASE):
            return False, f"Unresolved placeholder detected: {description}"

    # --- 3. Conversational Filter ---
    bad_starts = [
        "I ",
        "I'm ",
        "Sure",
        "Here is",
        "Here's",
        "Of course",
        "I can help",
        "I'd be happy",
        "Let me",
        "Certainly",
        "Thank you",
        "Great",
        "Absolutely",
        "Yes,",
        "I've updated",
        "I have generated",
    ]
    first_line = stripped_content.split("\n")[0].strip()

    # Normalize by stripping a leading markdown heading prefix (e.g. "### " or "## ")
    normalized_first_line = re.sub(r"^#{2,}\s*", "", first_line).strip()
    if doc_path == ".env.example":
        normalized_first_line = re.sub(r"^#\s*={3}\s*", "", normalized_first_line).strip()

    for phrase in bad_starts:
        if normalized_first_line.startswith(phrase):
            return (
                False,
                f"Conversational output detected: starts with '{phrase}'",
            )

    # --- 4. Monologue Filtering (Thought Leakage) ---
    # These are AI-specific phrases that should never appear in documentation
    monologue_markers = [
        "Note to developer:",  # More specific - needs colon
        "As you requested",
        "I will now",
        "Let's start by",
        "(Note to self",
        "<thought>",
        "I have generated",
        "Here is the documentation",
    ]
    for marker in monologue_markers:
        if marker.lower() in stripped_content.lower():
            return False, f"Internal AI monologue detected: '{marker}'"

    # --- 5. Semantic Relevance (Identifier Verification) ---
    # Only check for primary triggers in API reference docs
    # Skip for CHANGELOG (summaries), schema docs, etc.
    primary_triggers = {"new_public_function", "new_class", "new_endpoint", "new_cli_command"}
    skip_identifier_check = {".env.example", "CHANGELOG.md", "README.md", "docs/QUICKSTART.md"}
    if requirement and not any(skip in doc_path for skip in skip_identifier_check):
        for violation in requirement.triggers:
            # Only verify identifiers for primary trigger types
            if violation.trigger_name not in primary_triggers:
                continue
            # Extract func/class name with word boundary: "def my_func(" -> "my_func"
            # Requires space after def/class to avoid matching "default"
            match = re.search(
                r"(?:def |class |getenv\(['\"])([a-zA-Z_][a-zA-Z0-9_]*)",
                violation.matched_line,
            )
            if match:
                identifier = match.group(1)
                # Only check identifiers >3 chars to avoid false positives
                if len(identifier) > 3 and identifier not in stripped_content:
                    return (
                        False,
                        f"Identifier '{identifier}' not mentioned in generated docs",
                    )

    # --- 6. Code Echo Detection (Plagiarism Check) ---
    if requirement and doc_path != ".env.example" and len(requirement.triggers) > 0:
        echo_ratio = _calculate_code_echo_ratio(stripped_content, requirement)
        if echo_ratio > 0.85:
            return (
                False,
                f"Output is {echo_ratio:.0%} similar to source code (echoing)",
            )

    # --- 7. .env.example Format Validation ---
    if doc_path == ".env.example":
        has_env_var = False
        invalid_lines: list[tuple[int, str]] = []
        for line_idx, line in enumerate(content.split("\n"), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if re.match(r"^[A-Z_][A-Z0-9_]*=", stripped):
                has_env_var = True
                continue
            invalid_lines.append((line_idx, stripped))

        if not has_env_var:
            return False, "No KEY=value lines found — expected .env format, not markdown"

        if invalid_lines:
            examples = "; ".join(f"line {n}: '{text[:60]}'" for n, text in invalid_lines[:3])
            return (
                False,
                f"Invalid .env content: {len(invalid_lines)} line(s) are not comments "
                f"or KEY=value assignments ({examples})",
            )
        return True, "OK"

    # --- 8. Code Fence Check (Template Echo) ---
    fence_lines = 0
    total_lines = 0
    in_fence = False
    for line in stripped_content.split("\n"):
        total_lines += 1
        if line.strip().startswith("```"):
            in_fence = not in_fence
            fence_lines += 1
        elif in_fence:
            fence_lines += 1
    if total_lines > 5 and fence_lines / total_lines > 0.8:
        return (
            False,
            f"Content is >80% code fences ({fence_lines}/{total_lines} lines)"
            " — likely template echo",
        )

    # --- 9. Markdown Formatting Check ---
    has_markdown = any(marker in content for marker in ["###", "##", "**", "- ", "```"])
    if not has_markdown:
        return False, "No markdown formatting detected"

    return True, "OK"


# =============================================================================
# DOCUMENTATION GENERATION
# =============================================================================


async def generate_documentation_for_file(
    doc_path: str,
    requirement: DocRequirement,
    git_diff: str,
    _staged_files: list[str],
    verbose: bool = False,
) -> str:
    """
    Generate documentation content using Kilo agent.

    Args:
        doc_path: Path to documentation file
        requirement: DocRequirement with triggers
        git_diff: Git diff content
        staged_files: List of staged files
        verbose: Enable verbose output

    Returns:
        Generated documentation content
    """
    # Determine complexity and select agent
    complexity = get_doc_complexity(doc_path)

    try:
        agent_info = select_documentation_agent(complexity)
    except NoAgentAvailableError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Falling back to simple complexity agent...", file=sys.stderr)
        try:
            agent_info = select_documentation_agent("simple")
        except NoAgentAvailableError:
            raise RuntimeError("No documentation agents available in database")

    # Determine variant based on complexity
    variant_map = {"simple": "low", "medium": "high", "complex": "max"}
    variant = variant_map[complexity]

    # Select prompt template and build prompt
    violations_text = "\n".join(
        f"- {v.description} (File: {v.source_file}:{v.line_number})"
        for v in requirement.triggers[:10]
    )

    # Load template content for the doc type
    template_structure = get_template_for_doc(doc_path)
    source_files = "\n".join({v.source_file for v in requirement.triggers})

    if "CHANGELOG" in doc_path:
        prompt = CHANGELOG_PROMPT_TEMPLATE.format(
            git_diff=git_diff[:2000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    elif "docs/reference/" in doc_path or (".md" in doc_path and "reference" in doc_path):
        prompt = API_DOCS_PROMPT_TEMPLATE.format(
            source_files=source_files,
            git_diff=git_diff[:3000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    elif "CONFIGURATION" in doc_path:
        prompt = CONFIGURATION_GUIDE_PROMPT_TEMPLATE.format(
            source_files=source_files,
            git_diff=git_diff[:2000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    elif "MIGRATION" in doc_path:
        prompt = MIGRATION_PROMPT_TEMPLATE.format(
            git_diff=git_diff[:2000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    elif "database/schema" in doc_path:
        prompt = SCHEMA_DOCS_PROMPT_TEMPLATE.format(
            source_files=source_files,
            git_diff=git_diff[:3000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    elif "TROUBLESHOOTING" in doc_path:
        prompt = TROUBLESHOOTING_PROMPT_TEMPLATE.format(
            source_files=source_files,
            git_diff=git_diff[:2000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    elif doc_path in ("README.md", "docs/QUICKSTART.md"):
        prompt = README_PROMPT_TEMPLATE.format(
            doc_path=doc_path,
            git_diff=git_diff[:2000],
            violations=violations_text,
            template_structure=template_structure or "(no template available)",
        )
    else:
        # Generic documentation prompt with template if available
        template_section = ""
        if template_structure:
            template_section = (
                f"\n\n**Reference Structure (follow this format):**\n{template_structure}"
            )
        prompt = f"""Document the following code changes for {doc_path}:

{git_diff[:2000]}

Triggered by:
{violations_text}{template_section}

Write clear, concise documentation suitable for developers.
"""

    if verbose:
        print(f"\n[DOC GEN] {doc_path}", file=sys.stderr)
        print(f"[DOC GEN] Agent: {agent_info['name']}", file=sys.stderr)
        print(f"[DOC GEN] Complexity: {complexity}, Variant: {variant}", file=sys.stderr)

    # Call Kilo — resolve source files relative to PROJECT_ROOT so that
    # --project-root actually controls which files are attached.
    result = await run_kilo(
        prompt=prompt,
        model=agent_info["api_id"],
        agent="ask",
        variant=variant,
        file_paths=[PROJECT_ROOT / v.source_file for v in requirement.triggers[:5]],
        verbose=verbose,
    )

    if verbose:
        print(
            f"[DOC GEN] Generated {len(result['result'])} chars, cost: ${result['cost']:.4f}",
            file=sys.stderr,
        )

    content = result["result"]

    # Strip markdown code fences if model wrapped output in ```markdown ... ```
    # This is common with some models (e.g., Step 3.5 Flash)
    content = _strip_markdown_fences(content)

    # Validate raw model output BEFORE adding any prefix.
    # This ensures conversational replies (e.g. "Sure, here's...") are caught
    # before a forced prefix like "###" masks them.
    is_valid, reason = validate_generated_content(content, doc_path, requirement)
    if not is_valid:
        print(
            f"⚠️ Quality check failed for {doc_path} (agent: {agent_info['name']}): {reason}",
            file=sys.stderr,
        )
        # Retry with a different agent at a lower complexity tier
        _fallback: dict[ComplexityLevel, ComplexityLevel] = {
            "complex": "medium",
            "medium": "simple",
        }
        retry_complexity = _fallback.get(complexity)
        if retry_complexity:
            print(f"Retrying with {retry_complexity} complexity agent...", file=sys.stderr)
            try:
                retry_agent = select_documentation_agent(retry_complexity)
                retry_variant = variant_map[retry_complexity]
                retry_result = await run_kilo(
                    prompt=prompt,
                    model=retry_agent["api_id"],
                    agent="ask",
                    variant=retry_variant,
                    file_paths=[PROJECT_ROOT / v.source_file for v in requirement.triggers[:5]],
                    verbose=verbose,
                )
                content = _strip_markdown_fences(retry_result["result"])
                retry_valid, retry_reason = validate_generated_content(content, doc_path)
                if not retry_valid:
                    raise RuntimeError(
                        f"Documentation generation failed for {doc_path} after retry "
                        f"(agent: {retry_agent['name']}): {retry_reason}"
                    )
                if verbose:
                    print(
                        f"[DOC GEN] Retry succeeded with {retry_agent['name']} "
                        f"({len(content)} chars, cost: ${retry_result['cost']:.4f})",
                        file=sys.stderr,
                    )
            except NoAgentAvailableError:
                raise RuntimeError(
                    f"Documentation generation failed for {doc_path}: {reason}. "
                    "No fallback agent available for retry."
                )
        else:
            raise RuntimeError(
                f"Documentation generation failed for {doc_path}: {reason}. "
                "Already at lowest complexity — no retry possible."
            )

    # Normalize prefix: only add the forced prefix if the model didn't already emit it.
    # This avoids duplication like "### ### Added" when the model follows instructions.
    # .env.example is NOT markdown — skip prefix normalization entirely.
    if doc_path == ".env.example":
        # Strip any accidental markdown that the model may have produced
        if content.lstrip().startswith("#") and not content.lstrip().startswith("# ==="):
            # Model likely produced markdown instead of env format — prefix with section header
            content = "# === New Variables ===\n\n" + content
    elif "CHANGELOG" in doc_path and not content.lstrip().startswith("###"):
        content = "### " + content
    elif (
        "docs/reference/" in doc_path
        or (".md" in doc_path and "reference" in doc_path)
        or "CONFIGURATION" in doc_path
        or "MIGRATION" in doc_path
        or "database/schema" in doc_path
        or "TROUBLESHOOTING" in doc_path
        or doc_path in ("README.md", "docs/QUICKSTART.md")
    ) and not content.lstrip().startswith("##"):
        content = "## " + content

    return content


async def auto_generate_all_docs(
    requirements: dict[str, DocRequirement],
    git_diff: str,
    staged_files: list[str],
    verbose: bool = False,
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Auto-generate all missing documentation files.

    Returns:
        Tuple of (generated, failures) where:
        - generated: dict mapping doc_path -> generated_content
        - failures: dict mapping doc_path -> error message
    """
    generated = {}
    failures = {}

    for doc_path, req in requirements.items():
        # Skip if already staged
        if check_doc_updated_in_commit(doc_path, staged_files):
            if verbose:
                print(f"[SKIP] {doc_path} already staged", file=sys.stderr)
            continue

        try:
            content = await generate_documentation_for_file(
                doc_path, req, git_diff, staged_files, verbose
            )
            generated[doc_path] = content
        except Exception as e:
            error_msg = str(e)
            print(f"Error generating {doc_path}: {error_msg}", file=sys.stderr)
            failures[doc_path] = error_msg

    return generated, failures


def _strip_orphaned_comments(lines: list[str]) -> list[str]:
    """Strip orphaned comment blocks from .env content.

    After duplicate key removal, comment blocks (one or more consecutive
    ``#`` lines) that are not followed by a KEY=value assignment are
    considered orphaned and are removed.  Section headers (``# === ... ===``)
    without a subsequent variable are also removed.

    This prevents misleading comments from being appended to .env.example
    when the variable they described was already present.
    """
    result: list[str] = []
    comment_buffer: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Blank line: flush comment buffer (they are still "pending")
            # but keep the blank line itself
            comment_buffer.append(line)
            continue
        if stripped.startswith("#"):
            # Accumulate comments
            comment_buffer.append(line)
            continue
        # Non-blank, non-comment line — this is a KEY=value line.
        # Flush the preceding comment buffer (they belong to this variable).
        if comment_buffer:
            result.extend(comment_buffer)
            comment_buffer = []
        result.append(line)

    # Any remaining comment_buffer has no following variable — drop it
    # (these are orphaned comments).
    return result


def write_generated_docs(generated: dict[str, str], dry_run: bool = False) -> list[str]:
    """
    Write generated documentation to files.

    Returns:
        List of written file paths
    """
    written = []

    for doc_path, content in generated.items():
        file_path = PROJECT_ROOT / doc_path

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            print(f"[DRY RUN] Would write {doc_path} ({len(content)} chars)")
        else:
            # For CHANGELOG, append instead of overwrite
            if "CHANGELOG" in doc_path and file_path.exists():
                existing = file_path.read_text()
                # Insert after ## [Unreleased]
                if "## [Unreleased]" in existing:
                    parts = existing.split("## [Unreleased]", 1)
                    new_content = (
                        parts[0] + "## [Unreleased]\n\n" + content.strip() + "\n\n" + parts[1]
                    )
                    file_path.write_text(new_content)
                else:
                    file_path.write_text(content)
            elif doc_path == ".env.example" and file_path.exists():
                # Append new variables with deduplication
                existing = file_path.read_text()
                existing_keys = set()
                for line in existing.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        key = stripped.split("=", 1)[0].strip()
                        existing_keys.add(key)

                # Filter out variables that already exist
                new_lines = []
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        key = stripped.split("=", 1)[0].strip()
                        if key in existing_keys:
                            continue  # Skip duplicate
                    new_lines.append(line)

                # Strip orphaned comment blocks: remove trailing comment-only
                # lines that remain after duplicate key removal (comments that
                # described a removed variable and are now misleading).
                cleaned_lines = _strip_orphaned_comments(new_lines)

                new_content = "\n".join(cleaned_lines).strip()
                if new_content:
                    file_path.write_text(existing.rstrip() + "\n\n" + new_content + "\n")
                else:
                    # All vars already exist — nothing to append
                    print(f"ℹ️ {doc_path}: all variables already present, no changes needed")
                    continue
            else:
                file_path.write_text(content)

            print(f"✓ Generated: {doc_path}")
            written.append(doc_path)

    return written


# =============================================================================
# MAIN
# =============================================================================


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Kilo Documentation Enforcer - Professional-grade documentation enforcement"
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Detect required documentation updates (read-only)",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Enforce documentation requirements (fail if missing)",
    )
    parser.add_argument(
        "--auto-generate",
        action="store_true",
        help="Auto-generate missing documentation using Kilo agents",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be generated without writing"
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Explicit project root directory (default: current working directory)",
    )

    args = parser.parse_args()

    # Override PROJECT_ROOT if --project-root is given
    global PROJECT_ROOT
    if args.project_root:
        PROJECT_ROOT = Path(args.project_root).resolve()
        if not PROJECT_ROOT.is_dir():
            print(
                f"Error: --project-root '{args.project_root}' is not a directory", file=sys.stderr
            )
            return 2

    # Default to enforce mode if no mode specified
    if not args.detect and not args.enforce and not args.auto_generate:
        args.enforce = True

    # Get git root — scoped to PROJECT_ROOT
    git_root = get_git_root(cwd=PROJECT_ROOT)
    if not git_root:
        print("Error: Not in a git repository", file=sys.stderr)
        return 2

    # Validate that the discovered git root matches PROJECT_ROOT
    if git_root.resolve() != PROJECT_ROOT.resolve():
        print(
            f"Warning: git root ({git_root}) differs from PROJECT_ROOT ({PROJECT_ROOT}). "
            f"Using PROJECT_ROOT as the working directory for git commands.",
            file=sys.stderr,
        )

    # Get staged files and diff — scoped to PROJECT_ROOT
    staged_files = get_staged_files(cwd=PROJECT_ROOT)
    if not staged_files:
        if args.verbose:
            print("No staged files - nothing to check", file=sys.stderr)
        return 0

    diff = get_staged_diff(cwd=PROJECT_ROOT)
    if not diff:
        if args.verbose:
            print("No diff found", file=sys.stderr)
        return 0

    # Analyze diff for triggers
    violations = analyze_diff_for_triggers(diff, staged_files)
    requirements = group_violations_by_doc(violations)

    # Output report
    if args.output == "json":
        print_json_report(violations, requirements)
    else:
        print_detection_report(violations, requirements, staged_files)

    # Auto-generate if requested
    if args.auto_generate:
        print("\n" + "=" * 60)
        print("AUTO-GENERATING DOCUMENTATION")
        print("=" * 60)

        # Determine which docs actually need generation (not already staged)
        docs_needing_generation = {
            doc_path: req
            for doc_path, req in requirements.items()
            if not check_doc_updated_in_commit(doc_path, staged_files)
        }

        # If nothing needed generation in the first place, report accurately
        if not docs_needing_generation:
            print("\n✓ All required documentation already staged")
            return 0

        # --dry-run: true no-side-effects mode.  Report which docs would be
        # generated without calling generate_documentation_for_file() / run_kilo().
        if args.dry_run:
            print(f"\n[DRY RUN] Would generate {len(docs_needing_generation)} file(s):")
            for doc_path, req in docs_needing_generation.items():
                trigger_names = ", ".join(sorted({t.trigger_name for t in req.triggers}))
                print(
                    f"  - {doc_path} [{req.severity}] "
                    f"({len(req.triggers)} trigger(s): {trigger_names})"
                )
            return 0

        generated, failures = await auto_generate_all_docs(
            requirements, diff, staged_files, args.verbose
        )

        # Report failures loudly
        if failures:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("DOCUMENTATION GENERATION FAILURES", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            for doc_path, error_msg in failures.items():
                print(f"  ✗ {doc_path}: {error_msg}", file=sys.stderr)

        # Write successfully generated docs
        if generated:
            written = write_generated_docs(generated, dry_run=False)
            print(f"\n✓ Generated {len(written)} documentation file(s)")
            print("\nNext steps:")
            print("  git add " + " ".join(written))
            print("  python scripts/kilo_docs_enforcer.py --enforce")

        # Fail if any required docs could not be generated
        if failures:
            print(
                f"\nError: Failed to generate compliant documentation for "
                f"{len(failures)} file(s): {', '.join(failures.keys())}",
                file=sys.stderr,
            )
            return 1

        return 0

    # Enforce if requested
    if args.enforce:
        passed, errors = enforce_documentation(requirements, staged_files)

        if not passed:
            print("\n" + "=" * 60)
            print("ENFORCEMENT FAILED")
            print("=" * 60)
            for error in errors:
                print(error)
            print("\nFix: Update the required documentation files and stage them with git add")
            print("Or: Run with --auto-generate to generate docs automatically")
            return 1

        print("\n✓ All required documentation present or updated")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
