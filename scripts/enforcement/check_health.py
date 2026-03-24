#!/usr/bin/env python3
"""Check that health endpoints test actual dependencies.

Also verifies that projects with health endpoints have corresponding test files.
"""

import re
from pathlib import Path

FAKE_HEALTH_PATTERN = re.compile(
    r'@(?:app|router)\.(?:get|route)\s*\(\s*[\'"]/?health[\'"]', re.IGNORECASE
)

GOOD_PATTERNS = [
    r"await\s+.*(?:execute|query|ping)",
    r"SELECT\s+1",
    r"\.ping\(",
    r"check.*connection",
    r"test.*db",
    r"\.health\(",  # Client.health() calls (e.g., CoolifyClient, DNSClient)
    r"check_coolify|check_dns",  # Fabrik-specific health check functions
]


def check_file(file_path: Path) -> list:
    """Check health endpoints test dependencies."""
    from .validate_conventions import CheckResult, Severity

    results: list[CheckResult] = []
    if file_path.suffix.lower() != ".py":
        return results
    if "test" in file_path.name.lower():
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Find health endpoint definitions
    for match in FAKE_HEALTH_PATTERN.finditer(content):
        start = match.start()
        # Get the function body (next 20 lines or until next decorator)
        end_search = content[start : start + 1000]

        # Check if any good pattern exists in this section
        has_dep_check = any(re.search(p, end_search, re.I) for p in GOOD_PATTERNS)

        # Check for simple return {"status": "ok"} without dependency check
        if not has_dep_check and re.search(r'return\s+\{[\'"]status[\'"]', end_search):
            line_num = content[:start].count("\n") + 1
            results.append(
                CheckResult(
                    check_name="health",
                    severity=Severity.WARN,
                    message="Health endpoint may not test dependencies",
                    file_path=str(file_path),
                    line_number=line_num,
                    fix_hint="Add DB/Redis ping: await db.execute('SELECT 1')",
                )
            )

    # Check for health test file existence when health endpoint found
    has_health_endpoint = FAKE_HEALTH_PATTERN.search(content) is not None
    if has_health_endpoint:
        # Find project root (go up until we find tests/ or pyproject.toml)
        project_root = file_path.parent
        while project_root != project_root.parent:
            if (project_root / "pyproject.toml").exists() or (project_root / "tests").exists():
                break
            project_root = project_root.parent

        tests_dir = project_root / "tests"
        test_health = tests_dir / "test_health.py"

        if tests_dir.exists() and not test_health.exists():
            results.append(
                CheckResult(
                    check_name="health_test",
                    severity=Severity.WARN,
                    message="Health endpoint exists but tests/test_health.py not found",
                    file_path=str(file_path),
                    fix_hint="Create tests/test_health.py to test the /health endpoint",
                )
            )

    return results
