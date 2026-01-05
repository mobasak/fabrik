#!/usr/bin/env python3
"""
Fabrik Conventions Hook - PostToolUse

Validates that code changes follow Fabrik conventions:
- No hardcoded localhost (use os.getenv)
- No Alpine base images (use bookworm)
- Health endpoints must test dependencies
- Config must use os.getenv() not class-level

Exit codes:
- 0: Pass (or not applicable)
- 2: Block with feedback to Droid
"""

import json
import os
import re
import sys

# Patterns that indicate convention violations
VIOLATIONS = {
    # Hardcoded localhost/127.0.0.1 (detected separately, getenv defaults excluded in check_file)
    "hardcoded_localhost": {
        "pattern": r'(?:host|HOST|url|URL|uri|URI|server|SERVER)\s*[=:]\s*[\'"](?:localhost|127\.0\.0\.1)[\'"]',
        "file_types": [".py"],
        "message": "Hardcoded localhost detected. Use os.getenv('DB_HOST', 'localhost') instead.",
        "severity": "error",
    },
    # Alpine base image
    "alpine_image": {
        "pattern": r"FROM\s+.*alpine",
        "file_types": ["Dockerfile", ".dockerfile"],
        "message": "Alpine base image detected. Use python:3.12-slim-bookworm for ARM64 compatibility.",
        "severity": "error",
    },
    # Class-level config with getenv (evaluated at import time)
    "class_config": {
        "pattern": r"class\s+\w*[Cc]onfig.*:\s*\n(?:[^\n]*\n)*?\s+\w+\s*=\s*.*os\.getenv",
        "file_types": [".py"],
        "message": "Class-level os.getenv() detected. Config loads at import time when env vars may not be set. Use functions instead.",
        "severity": "warning",
    },
    # Health endpoint that just returns ok without testing
    "fake_health": {
        "pattern": r'@.*(?:get|route).*[\'"]/?health[\'"].*\n(?:[^\n]*\n)*?\s+return\s+\{[\'"]status[\'"]:\s*[\'"]ok[\'"]',
        "file_types": [".py"],
        "message": "Health endpoint returns ok without testing dependencies. Health checks MUST test actual DB/Redis connections.",
        "severity": "warning",
    },
    # Hardcoded passwords (exclude getenv/environ patterns)
    "hardcoded_password": {
        "pattern": r'(?:password|passwd|pwd)\s*=\s*[\'"](?!.*getenv|.*environ)[a-zA-Z0-9_@#$%^&*]{4,}[\'"]',
        "file_types": [".py", ".yaml", ".yml", ".json"],
        "message": "Hardcoded password detected. Use environment variables for credentials.",
        "severity": "error",
    },
    # Using /tmp instead of .tmp
    "system_tmp": {
        "pattern": r'[\'"]\/tmp\/',
        "file_types": [".py", ".sh"],
        "message": "Using /tmp/ detected. Use project-local .tmp/ directory instead (data survives container restarts).",
        "severity": "warning",
    },
}


def check_file(file_path: str, content: str) -> list[tuple[str, str, str]]:
    """Check file content for Fabrik convention violations."""
    issues = []

    for name, rule in VIOLATIONS.items():
        # Check if file type matches
        matches_type = False
        for ft in rule["file_types"]:
            if file_path.endswith(ft) or ft in file_path:
                matches_type = True
                break

        if not matches_type:
            continue

        # Check for pattern
        if re.search(rule["pattern"], content, re.IGNORECASE | re.MULTILINE):
            issues.append((name, rule["severity"], rule["message"]))

    return issues


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only check Write/Edit operations
    if tool_name not in ["Write", "Edit"]:
        sys.exit(0)

    # Skip if no file path
    if not file_path:
        sys.exit(0)

    # Skip test files
    if "test" in file_path.lower() or "spec" in file_path.lower():
        sys.exit(0)

    # Get content - for Write it's in input, for Edit read the file
    if tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        # For Edit, read the file after edit
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        else:
            sys.exit(0)

    # Check for violations
    issues = check_file(file_path, content)

    if not issues:
        sys.exit(0)

    # Report issues
    errors = [i for i in issues if i[1] == "error"]
    warnings = [i for i in issues if i[1] == "warning"]

    if warnings:
        for name, severity, message in warnings:
            print(f"⚠️ Fabrik Warning [{name}]: {message}", file=sys.stderr)

    if errors:
        for name, severity, message in errors:
            print(f"❌ Fabrik Error [{name}]: {message}", file=sys.stderr)
        print("\nPlease fix the above issues to follow Fabrik conventions.", file=sys.stderr)
        print("See: /opt/fabrik/AGENTS.md for Fabrik standards.", file=sys.stderr)
        sys.exit(2)  # Block with feedback

    # Warnings only - don't block
    sys.exit(0)


if __name__ == "__main__":
    main()
