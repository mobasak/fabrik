#!/usr/bin/env python3
"""Check for hardcoded localhost/127.0.0.1 in code.

Detects environment variable violations that break Docker/VPS deployments.
"""

import re
from pathlib import Path

# Patterns that indicate hardcoded localhost
HARDCODED_PATTERNS = [
    (
        r'(?:host|HOST|url|URL|uri|URI|server|SERVER)\s*[=:]\s*[\'"](?:localhost|127\.0\.0\.1)[\'"]',
        "hardcoded host assignment",
    ),
    (r'["\']localhost:\d+["\']', "hardcoded localhost with port"),
    (r'["\']127\.0\.0\.1:\d+["\']', "hardcoded 127.0.0.1 with port"),
    (r"http://localhost[:/]", "hardcoded http://localhost URL"),
    (r"http://127\.0\.0\.1[:/]", "hardcoded http://127.0.0.1 URL"),
]

# Patterns that indicate proper usage (allowlist) - must be specific
ALLOWED_CONTEXTS = [
    r"os\.getenv\s*\([^)]*,\s*['\"]localhost",  # os.getenv('VAR', 'localhost') default
    r"os\.environ\.get\s*\([^)]*,\s*['\"]localhost",  # os.environ.get default
    r"#\s*.*localhost",  # Comments with localhost
    r"^\s*#",  # Line starting with comment
    r"\.env\.example",  # Example env files
]


def check_file(file_path: Path) -> list:
    """Check a file for hardcoded localhost patterns.

    Returns list of CheckResult objects.
    """
    # Import here to avoid circular imports
    from .validate_conventions import CheckResult, Severity

    results: list[CheckResult] = []

    # Only check Python files
    if file_path.suffix.lower() != ".py":
        return results

    # Skip test files
    if "test" in file_path.name.lower():
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        # Skip if line contains allowed pattern
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWED_CONTEXTS):
            continue

        # Check for violations
        for pattern, description in HARDCODED_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                results.append(
                    CheckResult(
                        check_name="env_vars",
                        severity=Severity.ERROR,
                        message=f"{description.capitalize()}. Use os.getenv() instead.",
                        file_path=str(file_path),
                        line_number=line_num,
                        fix_hint="Replace with os.getenv('DB_HOST', 'localhost')",
                    )
                )
                break  # One violation per line is enough

    return results
