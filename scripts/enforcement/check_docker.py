#!/usr/bin/env python3
"""Check Docker conventions (base images, healthcheck)."""

import re
from pathlib import Path

ALPINE_PATTERN = re.compile(r"FROM\s+.*alpine", re.IGNORECASE)
HEALTHCHECK_PATTERN = re.compile(r"HEALTHCHECK", re.IGNORECASE)

APPROVED_BASES = [
    "python:3.12-slim-bookworm",
    "python:3.12-slim",
    "node:22-bookworm-slim",
    "node:20-bookworm-slim",
    "debian:bookworm-slim",
    "ubuntu:24.04",
]


def check_file(file_path: Path) -> list:
    """Check Docker files for convention violations."""
    from .validate_conventions import CheckResult, Severity

    results = []
    name = file_path.name.lower()

    # Only check Dockerfiles
    if name != "dockerfile" and not name.endswith(".dockerfile"):
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Check for Alpine base image
    if ALPINE_PATTERN.search(content):
        line_num = 1
        for i, line in enumerate(content.splitlines(), 1):
            if ALPINE_PATTERN.search(line):
                line_num = i
                break
        results.append(
            CheckResult(
                check_name="docker",
                severity=Severity.ERROR,
                message="Alpine base image detected. Use Debian/Ubuntu for ARM64 compatibility.",
                file_path=str(file_path),
                line_number=line_num,
                fix_hint="Use python:3.12-slim-bookworm or node:22-bookworm-slim",
            )
        )

    # Check for HEALTHCHECK instruction
    if not HEALTHCHECK_PATTERN.search(content):
        results.append(
            CheckResult(
                check_name="docker",
                severity=Severity.WARN,
                message="No HEALTHCHECK instruction found",
                file_path=str(file_path),
                line_number=1,
                fix_hint="Add: HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1",
            )
        )

    return results
