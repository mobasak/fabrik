#!/usr/bin/env python3
"""Enforce OpenAPI/API documentation synchronization.

When API endpoints change, documentation must be updated.

Triggers on changes to:
- Files with @app.get, @app.post, @router.get, etc.
- FastAPI route definitions

Enforces (WARNING only - auto-gen possible):
- openapi.json updated, OR
- docs/api/*.md updated, OR
- API docstrings present

Exit codes:
    0 - Pass (always - warnings only)
"""

import re
import subprocess
import sys

ROUTE_PATTERNS = [
    r"@app\.(get|post|put|patch|delete|options|head)\s*\(",
    r"@router\.(get|post|put|patch|delete|options|head)\s*\(",
    r"@api_router\.(get|post|put|patch|delete|options|head)\s*\(",
]

API_DOC_FILES = [
    "openapi.json",
    "openapi.yaml",
    "swagger.json",
    "swagger.yaml",
    "docs/api/",
    "docs/reference/api.md",
]


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
        )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def has_new_routes(filepath: str) -> bool:
    """Check if file has new route definitions in the diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        added_lines = [line for line in diff_content.split("\n") if line.startswith("+")]

        for line in added_lines:
            for pattern in ROUTE_PATTERNS:
                if re.search(pattern, line):
                    return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def has_route_docstring(filepath: str) -> bool:
    """Check if new routes have docstrings."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        route_count = 0
        docstring_count = 0

        lines = diff_content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("+"):
                for pattern in ROUTE_PATTERNS:
                    if re.search(pattern, line):
                        route_count += 1
                        for j in range(i + 1, min(i + 5, len(lines))):
                            if '"""' in lines[j] or "'''" in lines[j]:
                                docstring_count += 1
                                break

        return route_count > 0 and docstring_count >= route_count
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def api_docs_updated(staged_files: list[str]) -> bool:
    """Check if API documentation was updated."""
    for doc in API_DOC_FILES:
        if doc.endswith("/"):
            for f in staged_files:
                if f.startswith(doc):
                    return True
        elif doc in staged_files:
            return True
    return False


def main() -> int:
    """Check OpenAPI/API documentation sync."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    py_files = [f for f in staged_files if f.endswith(".py")]
    files_with_new_routes = [f for f in py_files if has_new_routes(f)]

    if not files_with_new_routes:
        print("✅ OpenAPI sync check PASSED (no new routes)")
        return 0

    if api_docs_updated(staged_files):
        print("✅ OpenAPI sync check PASSED (API docs updated)")
        return 0

    files_with_docstrings = [f for f in files_with_new_routes if has_route_docstring(f)]
    if len(files_with_docstrings) == len(files_with_new_routes):
        print("✅ OpenAPI sync check PASSED (routes have docstrings)")
        return 0

    print("WARNING: New API routes detected without documentation update.")
    print("")
    print("Files with new routes:")
    for f in files_with_new_routes[:5]:
        has_docs = "✓ has docstrings" if f in files_with_docstrings else "✗ missing docstrings"
        print(f"  - {f} ({has_docs})")
    print("")
    print("Recommendation:")
    print("  1. Add docstrings to route functions (FastAPI uses these for OpenAPI)")
    print("  2. Or update docs/api/*.md manually")
    print('  3. Or run: python -c "from app import app; print(app.openapi())" > openapi.json')
    print("")
    print("(This is a WARNING - commit will proceed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
