#!/usr/bin/env python3
"""Enforce project documentation structure.

Ensures documents are placed in the correct locations per Fabrik conventions.
"""

import sys
from pathlib import Path

# Allowed .md files in project root
ALLOWED_ROOT_MD = {
    "README.md",
    "CHANGELOG.md",
    "tasks.md",
    "AGENTS.md",
    "PORTS.md",
    "LICENSE.md",
}

# Valid docs/ subdirectories
VALID_DOCS_SUBDIRS = {
    "guides",
    "reference",
    "operations",
    "development",
    "archive",
}

# Directories that should not contain .md files directly
NO_MD_DIRS = {
    "src",
    "tests",
    "config",
    "scripts",
    "logs",
    "data",
    "output",
    ".tmp",
    ".cache",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
}

# Legacy directories to warn about (should be migrated)
LEGACY_DIRS = {
    "specs",
    "proposals",
}


def check_structure(project_root: Path, files: list[str] | None = None) -> list[dict]:
    """Check project structure for violations.

    Args:
        project_root: Root directory of the project
        files: Optional list of files to check (for pre-commit).
               If None, checks entire project.

    Returns:
        List of violation dicts with keys: file, severity, message, fix_hint
    """
    violations = []

    if files:
        # Check only specified files
        paths_to_check = [Path(f) for f in files if f.endswith(".md")]
    else:
        # Check all .md files in project
        paths_to_check = list(project_root.rglob("*.md"))

    for path in paths_to_check:
        # Make path relative to project root
        if path.is_absolute():
            try:
                rel_path = path.relative_to(project_root)
            except ValueError:
                continue  # File outside project
        else:
            rel_path = path

        # Skip hidden directories (except .windsurf, .droid)
        parts = rel_path.parts
        if any(p.startswith(".") and p not in {".windsurf", ".droid"} for p in parts):
            continue
        if "node_modules" in parts or "__pycache__" in parts:
            continue

        # Flag forbidden directories as errors (not skip!)
        forbidden_dir = next((p for p in parts if p in NO_MD_DIRS), None)
        if forbidden_dir:
            violations.append(
                {
                    "file": str(rel_path),
                    "severity": "error",
                    "message": f"Markdown file forbidden in '{forbidden_dir}/' directory",
                    "fix_hint": "Move to docs/reference/ or docs/guides/",
                }
            )
            continue

        # Check root-level .md files
        if len(parts) == 1:
            filename = parts[0]
            if filename not in ALLOWED_ROOT_MD:
                violations.append(
                    {
                        "file": str(rel_path),
                        "severity": "error",
                        "message": f"Markdown file '{filename}' not allowed in project root",
                        "fix_hint": f"Move to docs/reference/{filename} or docs/guides/{filename}",
                    }
                )

        # Check docs/ structure
        elif parts[0] == "docs":
            if len(parts) == 2:
                # File directly in docs/ - only INDEX.md allowed
                filename = parts[1]
                if filename not in {
                    "INDEX.md",
                    "QUICKSTART.md",
                    "CONFIGURATION.md",
                    "TROUBLESHOOTING.md",
                    "BUSINESS_MODEL.md",
                    "SERVICES.md",
                    "FABRIK_OVERVIEW.md",
                    "ENVIRONMENT_VARIABLES.md",
                }:
                    violations.append(
                        {
                            "file": str(rel_path),
                            "severity": "warning",
                            "message": f"'{filename}' should be in a docs/ subdirectory",
                            "fix_hint": f"Move to docs/reference/{filename} or docs/guides/{filename}",
                        }
                    )
            elif len(parts) >= 3:
                subdir = parts[1]
                if subdir not in VALID_DOCS_SUBDIRS:
                    violations.append(
                        {
                            "file": str(rel_path),
                            "severity": "warning",
                            "message": f"Non-standard docs subdirectory: docs/{subdir}/",
                            "fix_hint": f"Use one of: {', '.join(sorted(VALID_DOCS_SUBDIRS))}",
                        }
                    )

        # Check legacy directories
        elif parts[0] in LEGACY_DIRS:
            violations.append(
                {
                    "file": str(rel_path),
                    "severity": "warning",
                    "message": f"Legacy directory '{parts[0]}/' should be migrated",
                    "fix_hint": "Move to docs/development/plans/ or docs/archive/",
                }
            )

        # Check templates (allowed)
        elif parts[0] == "templates":
            pass  # Templates are allowed anywhere

        # Check .droid (allowed for task files)
        elif parts[0] == ".droid":
            pass  # Droid task files allowed

        # Check .windsurf (allowed for rule files)
        elif parts[0] == ".windsurf":
            pass  # Windsurf rule files allowed

        # Other locations
        else:
            violations.append(
                {
                    "file": str(rel_path),
                    "severity": "error",
                    "message": f"Markdown file in unexpected location: {rel_path}",
                    "fix_hint": "Move to docs/ subdirectory or project root (if allowed)",
                }
            )

    return violations


def main() -> int:
    """CLI entry point for pre-commit hook."""
    import argparse

    parser = argparse.ArgumentParser(description="Check project structure")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="Project root directory"
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    project_root = args.project_root
    if not project_root.is_absolute():
        project_root = Path.cwd() / project_root

    violations = check_structure(project_root, args.files if args.files else None)

    if not violations:
        print("✓ Project structure OK")
        return 0

    errors = [v for v in violations if v["severity"] == "error"]
    warnings = [v for v in violations if v["severity"] == "warning"]

    if errors:
        print(f"\n❌ Structure errors ({len(errors)}):\n")
        for v in errors:
            print(f"  {v['file']}")
            print(f"    → {v['message']}")
            print(f"    Fix: {v['fix_hint']}\n")

    if warnings:
        print(f"\n⚠️  Structure warnings ({len(warnings)}):\n")
        for v in warnings:
            print(f"  {v['file']}")
            print(f"    → {v['message']}")
            print(f"    Fix: {v['fix_hint']}\n")

    if args.strict and (errors or warnings):
        return 1

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
