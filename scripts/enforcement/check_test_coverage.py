#!/usr/bin/env python3
"""Enforce test coverage for new code.

When new public functions/classes are added to src/, corresponding tests should exist.

Triggers on:
- New .py files in src/
- New public functions (def name, not _name) in src/

Enforces (WARNING only):
- Corresponding test file exists, OR
- Function is tested somewhere in tests/

Exit codes:
    0 - Pass (always - warnings only)
"""

import re
import subprocess
import sys
from pathlib import Path


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


def is_new_file(filepath: str) -> bool:
    """Check if file is newly added."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", filepath],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().startswith("A")


def get_new_public_functions(filepath: str) -> list[str]:
    """Extract new public function names from diff."""
    functions = []
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        pattern = r"^\+\s*(?:async\s+)?def\s+([a-z][a-z0-9_]*)\s*\("
        for match in re.finditer(pattern, diff_content, re.MULTILINE):
            func_name = match.group(1)
            if not func_name.startswith("_"):
                functions.append(func_name)
    except (OSError, subprocess.SubprocessError):
        pass
    return functions


def get_new_public_classes(filepath: str) -> list[str]:
    """Extract new public class names from diff."""
    classes = []
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", filepath],
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout

        pattern = r"^\+\s*class\s+([A-Z][a-zA-Z0-9_]*)\s*[\(:]"
        for match in re.finditer(pattern, diff_content, re.MULTILINE):
            class_name = match.group(1)
            classes.append(class_name)
    except (OSError, subprocess.SubprocessError):
        pass
    return classes


def find_test_file(src_path: str) -> Path | None:
    """Find corresponding test file for a source file."""
    path = Path(src_path)

    if "src/" in src_path:
        test_path = Path("tests") / path.relative_to("src").with_name(f"test_{path.name}")
        if test_path.exists():
            return test_path

    test_name = f"test_{path.stem}.py"
    for test_dir in [Path("tests"), Path("test")]:
        if test_dir.exists():
            for test_file in test_dir.rglob(test_name):
                return test_file

    return None


def function_tested(func_name: str, test_dir: Path = Path("tests")) -> bool:
    """Check if function is tested somewhere in tests/."""
    if not test_dir.exists():
        return False

    patterns = [
        f"test_{func_name}",
        f"def test_.*{func_name}",
        f"{func_name}\\(",
    ]

    for test_file in test_dir.rglob("test_*.py"):
        try:
            content = test_file.read_text()
            for pattern in patterns:
                if re.search(pattern, content):
                    return True
        except (OSError, UnicodeDecodeError):
            pass

    return False


def main() -> int:
    """Check test coverage for new code."""
    staged_files = get_staged_files()

    if not staged_files or staged_files == [""]:
        return 0

    src_files = [f for f in staged_files if f.startswith("src/") and f.endswith(".py")]
    src_files = [f for f in src_files if "__init__.py" not in f]

    if not src_files:
        print("✅ Test coverage check PASSED (no src/ changes)")
        return 0

    untested_items: list[tuple[str, str, str]] = []

    for src_file in src_files:
        new_functions = get_new_public_functions(src_file)
        new_classes = get_new_public_classes(src_file)

        if not new_functions and not new_classes:
            continue

        for func in new_functions:
            if not function_tested(func):
                untested_items.append((src_file, "function", func))

        for cls in new_classes:
            if not function_tested(cls):
                untested_items.append((src_file, "class", cls))

    if not untested_items:
        print("✅ Test coverage check PASSED")
        return 0

    print("WARNING: New public code without apparent tests.")
    print("")
    print("Untested items:")
    for src_file, item_type, name in untested_items[:10]:
        print(f"  - {src_file}: {item_type} `{name}`")
    if len(untested_items) > 10:
        print(f"  ... and {len(untested_items) - 10} more")
    print("")
    print("Recommendation:")
    print("  - Add tests in tests/test_<module>.py")
    print("  - Or mark intentionally untested with # pragma: no cover")
    print("")
    print("(This is a WARNING - commit will proceed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
