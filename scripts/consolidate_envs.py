#!/usr/bin/env python3
"""Consolidate all .env files from /opt/* projects into /opt/fabrik/.env.

This script:
1. Scans all /opt/* projects (excludes _* prefixes)
2. Reads each project's .env file
3. Merges into /opt/fabrik/.env with project-scoped sections
4. Prevents duplication via intelligent merging
5. Preserves existing Fabrik-specific vars

Usage:
    python scripts/consolidate_envs.py          # Dry run (show what would change)
    python scripts/consolidate_envs.py --apply  # Apply changes to /opt/fabrik/.env
"""

import re
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

# Sensitive variable patterns (for masking in dry-run output)
SENSITIVE_PATTERNS = [
    r".*PASSWORD.*",
    r".*SECRET.*",
    r".*TOKEN.*",
    r".*KEY.*",
    r".*PASSPHRASE.*",
    r".*CREDENTIAL.*",
    r".*AUTH.*",
    r".*API_KEY.*",
]


def is_sensitive_var(var_name: str) -> bool:
    """Check if variable name matches sensitive patterns."""
    return any(re.match(pattern, var_name, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS)


def mask_value(value: str) -> str:
    """Mask sensitive value for display."""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def get_project_dirs() -> list[Path]:
    """Get all valid project directories under /opt/."""
    opt = Path("/opt")
    if not opt.exists():
        return []

    projects = []
    for item in sorted(opt.iterdir()):
        # Skip if not directory, starts with _, or is fabrik
        if not item.is_dir() or item.name.startswith("_") or item.name == "fabrik":
            continue
        projects.append(item)

    return projects


def parse_env_file(env_path: Path) -> dict[str, tuple[str, list[str]]]:
    """Parse .env file into dict of {var_name: (value, [comment_lines])}.

    Returns:
        OrderedDict with variables and their values plus preceding comments
    """
    if not env_path.exists():
        return OrderedDict()

    result = OrderedDict()
    current_comments = []

    for line in env_path.read_text().splitlines():
        stripped = line.strip()

        # Collect comment lines
        if stripped.startswith("#") or stripped == "":
            current_comments.append(line)
            continue

        # Parse variable line (CRITICAL: accept uppercase, lowercase, mixed-case)
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", stripped)
        if match:
            var_name = match.group(1)
            value = match.group(2).strip('"').strip("'")
            result[var_name] = (value, current_comments.copy())
            current_comments = []
        else:
            # Malformed line, treat as comment
            current_comments.append(line)

    return result


def consolidate_envs(dry_run: bool = True) -> tuple[str, dict[str, int]]:
    """Consolidate all project .env files into Fabrik .env.

    Returns:
        Tuple of (new_content, stats_dict)
    """
    fabrik_env = Path("/opt/fabrik/.env")
    fabrik_env_example = Path("/opt/fabrik/.env.example")

    # Parse existing Fabrik .env (if exists)
    fabrik_vars = parse_env_file(fabrik_env) if fabrik_env.exists() else OrderedDict()
    fabrik_example_vars = parse_env_file(fabrik_env_example)

    # Start with Fabrik's own variables
    sections = OrderedDict()
    sections["FABRIK_CORE"] = OrderedDict()

    # CRITICAL FIX: First, add ALL vars from existing .env (preserves all 137+ vars)
    # This is the primary source of truth - never lose existing vars
    for var_name, var_data in fabrik_vars.items():
        sections["FABRIK_CORE"][var_name] = var_data

    # Then, add any vars from .env.example that aren't already present
    # (provides defaults for vars that exist in example but not in .env)
    for var_name in fabrik_example_vars:
        if var_name not in sections["FABRIK_CORE"]:
            sections["FABRIK_CORE"][var_name] = fabrik_example_vars[var_name]

    # Scan all projects
    projects = get_project_dirs()
    stats = {"projects_scanned": 0, "vars_found": 0, "vars_added": 0}

    for project_dir in projects:
        env_file = project_dir / ".env"
        if not env_file.exists():
            continue

        stats["projects_scanned"] += 1
        project_vars = parse_env_file(env_file)

        if not project_vars:
            continue

        # Create section for this project
        section_name = "PROJECT_" + project_dir.name.upper().replace("-", "_")
        sections[section_name] = OrderedDict()

        for var_name, (value, comments) in project_vars.items():
            stats["vars_found"] += 1

            # Skip if already in Fabrik core
            if var_name in sections["FABRIK_CORE"]:
                continue

            # Add to project section
            sections[section_name][var_name] = (value, comments)
            stats["vars_added"] += 1

    # Build consolidated .env content
    lines = []
    lines.append("# Consolidated Environment Configuration")
    lines.append("# AUTO-GENERATED by scripts/consolidate_envs.py")
    lines.append("# Manual edits will be preserved in FABRIK_CORE section")
    lines.append("")

    for section_name, variables in sections.items():
        if not variables:
            continue

        # Section header
        lines.append("")
        lines.append("# " + "=" * 77)
        if section_name == "FABRIK_CORE":
            lines.append("# Fabrik Core Configuration")
        else:
            project_name = section_name.replace("PROJECT_", "").replace("_", "-").lower()
            lines.append(f"# Project: {project_name}")
        lines.append("# " + "=" * 77)

        # Variables in this section
        for var_name, (value, comments) in variables.items():
            # Add preserved comments
            for comment in comments:
                if comment.strip():  # Skip empty lines from comments
                    lines.append(comment)

            # Add variable
            lines.append(f"{var_name}={value}")

        lines.append("")

    return "\n".join(lines), stats


def main():
    """Main entry point."""
    dry_run = "--apply" not in sys.argv

    print("🔍 Consolidating .env files from /opt/* projects...")
    print()

    new_content, stats = consolidate_envs(dry_run=dry_run)

    print("📊 Statistics:")
    print(f"  Projects scanned: {stats['projects_scanned']}")
    print(f"  Variables found: {stats['vars_found']}")
    print(f"  Variables added to consolidated .env: {stats['vars_added']}")
    print()

    if dry_run:
        print("🔎 DRY RUN - No changes made")
        print()
        print("Preview of consolidated .env (secrets masked):")
        print("=" * 80)
        # Mask sensitive values in preview
        preview_lines = []
        for line in new_content.splitlines()[:50]:  # Show first 50 lines
            if "=" in line and not line.strip().startswith("#"):
                var_name = line.split("=", 1)[0]
                if is_sensitive_var(var_name):
                    value = line.split("=", 1)[1] if "=" in line else ""
                    line = f"{var_name}={mask_value(value)}"
            preview_lines.append(line)
        print("\n".join(preview_lines))
        if len(new_content.splitlines()) > 50:
            print(f"\n... ({len(new_content.splitlines()) - 50} more lines)")
        print("=" * 80)
        print()
        print("To apply changes, run: python scripts/consolidate_envs.py --apply")
        return 0

    # Write consolidated .env
    fabrik_env = Path("/opt/fabrik/.env")

    # Backup existing .env with timestamped name
    if fabrik_env.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = fabrik_env.parent / f".env.backup.{timestamp}"
        backup_path.write_text(fabrik_env.read_text())
        print(f"✅ Backed up existing .env to: {backup_path}")

    fabrik_env.write_text(new_content)
    print(f"✅ Consolidated .env written to: {fabrik_env}")
    print()
    print("⚠️  Next steps:")
    print("  1. Review /opt/fabrik/.env")
    print("  2. Remove duplicate vars from project .env files")
    print("  3. Update projects to source from Fabrik .env if needed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
