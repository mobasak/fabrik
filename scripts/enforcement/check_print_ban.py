#!/usr/bin/env python3
# AFTER-EDIT: none
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
    "libs/health_probe/",  # vendored fabrik-lib health-probe (D-082): its print() IS its CLI output; re-vendored as shipped, never edited
    "docs/",
    ".claude/hooks/",  # Claude Code hooks inject context via stdout — print() IS their output
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


def changed_line_numbers(filepath: str) -> set[int] | None:
    """Added/changed line numbers for ``filepath`` in the staged diff (parses
    ``git diff --cached --unified=0`` hunk headers). Returns ``None`` when there is
    no usable diff (untracked / brand-new file / parse failure) → the caller then
    fails OPEN to a whole-file scan so a real print in a NEW file is still caught.

    This bounds the ban to lines THIS change actually touched: a pre-existing
    print() elsewhere in a file you merely edited (e.g. a `python -c "…print(x)"`
    subprocess string a sibling added) is not this change's to answer for — same
    fix already applied to check_secrets.py."""
    import re

    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--", filepath],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    changed: set[int] = set()
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", result.stdout, re.MULTILINE):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        changed.update(range(start, start + count))
    return changed


def should_skip(filepath: str) -> bool:
    """Check if file should be skipped (tests, scripts, cache, etc.)."""
    return any(pattern in filepath for pattern in SKIP_PATTERNS)


def is_template_generator(filepath: str) -> bool:
    """A file whose first lines carry a '# noqa-file: template-generator' COMMENT
    (e.g. src/fabrik/scaffold.py) emits code as strings; its apparent print()/console.log()
    are generated-PROJECT code, not this file's own runtime output — so the ban must not flag
    them. Matched only as a top-of-file COMMENT that BEGINS with the marker (a directive) — NOT
    a bare substring, and NOT a comment that merely mentions the marker in prose: a string
    literal referencing it (e.g. another check comparing against it) or a note like
    '# see noqa-file: ...' must not silently disable the ban. Honors the existing file-level
    marker instead of us noqa-ing each emitted line. Trade-off: this is a whole-file exemption
    (the marker's intent), so a real runtime print() in such a file is also unbanned — acceptable
    for a declared template generator, and scaffold.py uses logging for its own output."""
    try:
        with open(filepath, encoding="utf-8") as fh:
            head = [next(fh, "") for _ in range(20)]
    except (OSError, UnicodeDecodeError):
        return False
    return any(
        line.lstrip().startswith("#")
        and line.lstrip().lstrip("#").strip().startswith("noqa-file: template-generator")
        for line in head
    )


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
        if is_template_generator(filepath):
            continue

        # Bound the ban to lines THIS change touched (None → whole-file, so a
        # brand-new file's prints are still caught).
        changed = changed_line_numbers(filepath)

        ext = Path(filepath).suffix
        if ext in PRODUCTION_PY_EXTENSIONS:
            lines = scan_file_for_pattern(filepath, "print(")
            lines = [ln for ln in lines if changed is None or ln in changed]
            if lines:
                all_violations.append((filepath, "print(", lines))
        elif ext in PRODUCTION_JS_EXTENSIONS:
            lines = scan_file_for_pattern(filepath, "console.log(")
            lines = [ln for ln in lines if changed is None or ln in changed]
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
