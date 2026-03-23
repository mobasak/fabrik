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
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import contextlib
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
# GIT HELPERS
# =============================================================================


def get_git_root() -> Path | None:
    """Get git repository root."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            return None
        result = subprocess.run(
            [git_path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_staged_diff() -> str:
    """Get git diff of staged changes."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            return ""
        result = subprocess.run(
            [git_path, "diff", "--cached", "--unified=3"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def get_staged_files() -> list[str]:
    """Get list of staged file paths."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            return []
        result = subprocess.run(
            [git_path, "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def get_diff_stats() -> tuple[int, int]:
    """Get total lines added and removed."""
    try:
        git_path = shutil.which("git")
        if not git_path:
            return 0, 0
        result = subprocess.run(
            [git_path, "diff", "--cached", "--numstat"],
            capture_output=True,
            text=True,
            check=True,
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
    added, removed = get_diff_stats()
    if added + removed > threshold:
        # Check if any non-doc, non-test files changed
        code_files = [
            f
            for f in staged_files
            if not any(skip in f for skip in ["tests/", "test_", "docs/", ".md", ".txt"])
        ]
        if code_files and not any(v.trigger_name == "large_code_change" for v in violations):
            violations.append(
                DocViolation(
                    trigger_name="large_code_change",
                    severity="MAJOR",
                    source_file=", ".join(code_files[:3]),
                    matched_line=f"{added} additions, {removed} deletions",
                    required_docs=["CHANGELOG.md"],
                    description=f"Large code change ({added + removed} lines) requires CHANGELOG entry",
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

        error_msg = f"{severity_emoji} [{req.severity}] {doc_path} must be updated ({trigger_count} trigger(s))"
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

CHANGELOG_PROMPT_TEMPLATE = """SYSTEM ROLE: You are a CHANGELOG entry generator. You output ONLY the changelog entry text. You NEVER output conversational responses, greetings, or explanations. Your entire output is a valid Keep a Changelog format entry.

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

API_DOCS_PROMPT_TEMPLATE = """SYSTEM ROLE: You are a documentation generator. You output ONLY markdown documentation. You NEVER output conversational text, greetings, or explanations. You NEVER say "I am ready to assist". Your entire output is valid markdown documentation.

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

ENV_VAR_DOCS_PROMPT_TEMPLATE = """SYSTEM ROLE: You are an environment variable documentation generator. You output ONLY markdown documentation. You NEVER output conversational text or greetings. Your entire output is valid markdown documenting environment variables.

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


def validate_generated_content(content: str, doc_path: str) -> tuple[bool, str]:
    """
    Validate generated documentation content quality.

    Returns:
        (is_valid, reason) — True if content passes quality checks.
    """
    # Minimum length check
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

    if len(content.strip()) < min_len:
        return False, f"Content too short ({len(content.strip())} chars, minimum {min_len})"

    # Check for conversational text (agent ignored instructions)
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
    ]
    first_line = content.strip().split("\n")[0].strip()

    # Normalize by stripping a leading markdown heading prefix (e.g. "### " or "## ")
    # so that conversational replies like "### Sure, here's..." are still caught.
    normalized_first_line = re.sub(r"^#{2,}\s*", "", first_line).strip()

    for phrase in bad_starts:
        if normalized_first_line.startswith(phrase):
            return (
                False,
                f"Conversational output detected: starts with '{phrase}' (after heading prefix)",
            )

    # Check for expected markdown markers
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
    staged_files: list[str],
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

    if "CHANGELOG" in doc_path:
        prompt = CHANGELOG_PROMPT_TEMPLATE.format(
            git_diff=git_diff[:2000],
            violations=violations_text,
        )
    elif "docs/reference/" in doc_path or ".md" in doc_path and "reference" in doc_path:
        source_files = "\n".join({v.source_file for v in requirement.triggers})
        prompt = API_DOCS_PROMPT_TEMPLATE.format(
            source_files=source_files,
            git_diff=git_diff[:3000],
            violations=violations_text,
        )
    elif "CONFIGURATION" in doc_path or ".env.example" in doc_path:
        source_files = "\n".join({v.source_file for v in requirement.triggers})
        prompt = ENV_VAR_DOCS_PROMPT_TEMPLATE.format(
            source_files=source_files,
            git_diff=git_diff[:2000],
            violations=violations_text,
        )
    else:
        # Generic documentation prompt
        prompt = f"""Document the following code changes for {doc_path}:

{git_diff[:2000]}

Triggered by:
{violations_text}

Write clear, concise documentation suitable for developers.
"""

    if verbose:
        print(f"\n[DOC GEN] {doc_path}", file=sys.stderr)
        print(f"[DOC GEN] Agent: {agent_info['name']}", file=sys.stderr)
        print(f"[DOC GEN] Complexity: {complexity}, Variant: {variant}", file=sys.stderr)

    # Call Kilo
    result = await run_kilo(
        prompt=prompt,
        model=agent_info["api_id"],
        agent="ask",
        variant=variant,
        file_paths=[Path(v.source_file) for v in requirement.triggers[:5]],
        verbose=verbose,
    )

    if verbose:
        print(
            f"[DOC GEN] Generated {len(result['result'])} chars, cost: ${result['cost']:.4f}",
            file=sys.stderr,
        )

    content = result["result"]

    # Validate raw model output BEFORE adding any prefix.
    # This ensures conversational replies (e.g. "Sure, here's...") are caught
    # before a forced prefix like "###" masks them.
    is_valid, reason = validate_generated_content(content, doc_path)
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
                    file_paths=[Path(v.source_file) for v in requirement.triggers[:5]],
                    verbose=verbose,
                )
                content = retry_result["result"]
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
    if "CHANGELOG" in doc_path:
        if not content.lstrip().startswith("###"):
            content = "### " + content
    elif "docs/reference/" in doc_path or ("reference" in doc_path and ".md" in doc_path):
        if not content.lstrip().startswith("##"):
            content = "## " + content
    elif "CONFIGURATION" in doc_path or ".env.example" in doc_path:
        if not content.lstrip().startswith("###"):
            content = "### " + content

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

    args = parser.parse_args()

    # Default to enforce mode if no mode specified
    if not args.detect and not args.enforce and not args.auto_generate:
        args.enforce = True

    # Get git root
    git_root = get_git_root()
    if not git_root:
        print("Error: Not in a git repository", file=sys.stderr)
        return 2

    # Get staged files and diff
    staged_files = get_staged_files()
    if not staged_files:
        if args.verbose:
            print("No staged files - nothing to check", file=sys.stderr)
        return 0

    diff = get_staged_diff()
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

        generated, failures = await auto_generate_all_docs(
            requirements, diff, staged_files, args.verbose
        )

        # If nothing needed generation in the first place, report accurately
        if not docs_needing_generation:
            print("\n✓ All required documentation already staged")
            return 0

        # Report failures loudly
        if failures:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print("DOCUMENTATION GENERATION FAILURES", file=sys.stderr)
            print(f"{'=' * 60}", file=sys.stderr)
            for doc_path, error_msg in failures.items():
                print(f"  ✗ {doc_path}: {error_msg}", file=sys.stderr)

        # Write successfully generated docs
        if generated:
            written = write_generated_docs(generated, dry_run=args.dry_run)

            if args.dry_run:
                print(f"\n[DRY RUN] Would generate {len(generated)} file(s)")
            else:
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
