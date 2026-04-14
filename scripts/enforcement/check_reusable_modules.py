#!/usr/bin/env python3
"""
Tier 2 enforcement (warning-level, non-blocking): verifies that every .py module
in src/utils/ and src/lib/ is listed in INDEX.md with a [reusable] marker.

Exit codes:
    0 - Always (this check is advisory only and never blocks)
"""

import os
import sys
from pathlib import Path


def get_module_files(repo_root: Path) -> list[Path]:
    """Collect .py files (excluding __init__.py) from src/utils/ and src/lib/."""
    modules = []
    for subdir in ("src/utils", "src/lib"):
        d = repo_root / subdir
        if d.is_dir():
            for py_file in sorted(d.glob("*.py")):
                if py_file.name != "__init__.py":
                    modules.append(py_file)
    return modules


def read_index_md(repo_root: Path) -> str:
    """Read INDEX.md content; return empty string if missing."""
    index_path = repo_root / "INDEX.md"
    if not index_path.exists():
        return ""
    try:
        return index_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def main() -> int:
    """Check that src/utils/ and src/lib/ modules are tagged [reusable] in INDEX.md."""
    repo_root = Path(os.environ.get("FABRIK_ROOT", Path.cwd()))

    modules = get_module_files(repo_root)
    if not modules:
        return 0

    index_content = read_index_md(repo_root)
    if not index_content:
        print(f"WARNING: INDEX.md missing but {len(modules)} reusable module(s) found")
        return 0

    untagged = []
    for mod in modules:
        mod_name = mod.name
        # Check line-by-line: module name and [reusable] must appear on the same line
        found_tagged = False
        for line in index_content.splitlines():
            if mod_name in line and "[reusable]" in line:
                found_tagged = True
                break
        if not found_tagged:
            untagged.append(mod)

    if untagged:
        print(
            f"WARNING: {len(untagged)} module(s) in src/utils/ or src/lib/"
            " not tagged [reusable] in INDEX.md:"
        )
        for mod in untagged:
            rel = mod.relative_to(repo_root)
            print(f"  {rel}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
