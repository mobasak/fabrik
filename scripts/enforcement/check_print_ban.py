#!/usr/bin/env python3
"""
Tier 1 enforcement: bans print() in production .py files and console.log() in
production .ts/.tsx/.js/.jsx files.

Scans staged files only. Skips test files and the scripts/ directory.

Exit codes:
    0 - Pass (no print/console.log in production code)
    1 - Fail (violations found)
"""

import subprocess
import sys
from pathlib import Path

SKIP_PATTERNS = [
    "tests/",
    "test_",
    "_test.py",
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    "__pycache__/",
    ".pytest_cache/",
    "node_modules/",
    ".venv/",
    "scripts/",
]

PRODUCTION_PY_EXTENSIONS = {".py"}
PRODUCTION_JS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def should_skip(filepath: str) -> bool:
    """Check if file should be skipped (tests, scripts, cache, etc.)."""
    return any(pattern in filepath for pattern in SKIP_PATTERNS)


def scan_file_for_pattern(filepath: str, pattern: str) -> list[int]:
    """Scan a file for a substring pattern, returning matching line numbers."""
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    violations = []
    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        if pattern in line:
            violations.append(line_num)
    return violations


def main() -> int:
    """Check staged production files for print()/console.log() usage."""
    staged_files = get_staged_files()
    if not staged_files or staged_files == [""]:
        return 0

    all_violations: list[tuple[str, str, list[int]]] = []

    for filepath in staged_files:
        if should_skip(filepath):
            continue

        ext = Path(filepath).suffix
        if ext in PRODUCTION_PY_EXTENSIONS:
            lines = scan_file_for_pattern(filepath, "print(")
            if lines:
                all_violations.append((filepath, "print(", lines))
        elif ext in PRODUCTION_JS_EXTENSIONS:
            lines = scan_file_for_pattern(filepath, "console.log(")
            if lines:
                all_violations.append((filepath, "console.log(", lines))

    if all_violations:
        print("ERROR: print()/console.log() found in production code:")
        for filepath, pattern, lines in all_violations:
            line_str = ", ".join(str(ln) for ln in lines)
            print(f"  {filepath}:{line_str} — {pattern}")
        print("")
        print("Use structured logger instead (e.g., logger.info(), logger.debug())")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
