#!/usr/bin/env python3
"""
Update AGENTS.md Table of Contents

Automatically regenerates the TOC in AGENTS.md by scanning all ## headers.
Follows the same AUTO-GENERATED pattern as docs/INDEX.md.

Usage:
    python scripts/update_agents_toc.py              # Update AGENTS.md
    python scripts/update_agents_toc.py --check      # Verify TOC is current (exit 1 if stale)
    python scripts/update_agents_toc.py --dry-run    # Preview changes without writing

Workflow Doc: docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md (AGENTS.md maintenance)
  ⚠️  Update the workflow doc when modifying this script.
"""

import argparse
import re
import sys
from pathlib import Path


def generate_anchor(header_text: str) -> str:
    """
    Generate GitHub-style anchor link from header text.

    Examples:
        "Authority Model" -> "authority-model"
        "⚠️ MANDATORY WORKFLOW" -> "️-mandatory-workflow"
        "Build & Test" -> "build--test"
    """
    # Remove markdown formatting
    text = re.sub(r"[*_`]", "", header_text)
    # Convert to lowercase
    text = text.lower()
    # Replace spaces with hyphens
    text = text.replace(" ", "-")
    # Remove special chars except hyphens and emojis
    text = re.sub(r"[^a-z0-9\-\u0080-\uFFFF]", "", text)
    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def extract_headers(content: str) -> list[tuple[str, str]]:
    """
    Extract all ## headers from content (excluding # and TOC section).

    Returns:
        List of (header_text, anchor) tuples
    """
    headers = []
    in_toc_section = False

    for line in content.split("\n"):
        # Skip TOC section
        if "<!-- AUTO-GENERATED:TOC:START -->" in line:
            in_toc_section = True
            continue
        if "<!-- AUTO-GENERATED:TOC:END -->" in line:
            in_toc_section = False
            continue
        if in_toc_section:
            continue

        # Extract ## headers only (not # or ###)
        if line.startswith("## ") and not line.startswith("### "):
            header_text = line[3:].strip()
            anchor = generate_anchor(header_text)
            headers.append((header_text, anchor))

    return headers


def generate_toc(headers: list[tuple[str, str]]) -> str:
    """Generate TOC content from headers."""
    lines = [
        "<!-- AUTO-GENERATED:TOC:START -->",
        "<!-- This section is auto-generated. Do not edit manually."
        " Run: python scripts/update_agents_toc.py -->",
        "## Table of Contents",
    ]

    for header_text, anchor in headers:
        lines.append(f"- [{header_text}](#{anchor})")

    lines.append("<!-- AUTO-GENERATED:TOC:END -->")

    return "\n".join(lines)


def update_toc(file_path: Path, dry_run: bool = False) -> tuple[bool, str]:
    """
    Update TOC in AGENTS.md file.

    Returns:
        (changed, new_content) tuple
    """
    content = file_path.read_text()

    # Check if TOC markers exist
    if "<!-- AUTO-GENERATED:TOC:START -->" not in content:
        return False, content

    # Extract headers
    headers = extract_headers(content)

    # Generate new TOC
    new_toc = generate_toc(headers)

    # Replace TOC section
    pattern = r"<!-- AUTO-GENERATED:TOC:START -->.*?<!-- AUTO-GENERATED:TOC:END -->"
    new_content = re.sub(pattern, new_toc, content, flags=re.DOTALL)

    # Check if changed
    changed = content != new_content

    if changed and not dry_run:
        file_path.write_text(new_content)

    return changed, new_content


def main():
    parser = argparse.ArgumentParser(description="Update AGENTS.md Table of Contents")
    parser.add_argument(
        "--check", action="store_true", help="Check if TOC is current (exit 1 if stale)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    agents_md = Path(__file__).parent.parent / "AGENTS.md"

    if not agents_md.exists():
        print(f"Error: {agents_md} not found", file=sys.stderr)
        sys.exit(1)

    changed, new_content = update_toc(agents_md, dry_run=args.dry_run)

    if args.check:
        if changed:
            print(
                "❌ AGENTS.md TOC is stale. Run: python scripts/update_agents_toc.py",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print("✅ AGENTS.md TOC is current")
            sys.exit(0)

    if args.dry_run:
        if changed:
            print("Preview of changes:")
            print("=" * 60)
            # Show just the TOC section
            match = re.search(
                r"<!-- AUTO-GENERATED:TOC:START -->.*?<!-- AUTO-GENERATED:TOC:END -->",
                new_content,
                re.DOTALL,
            )
            if match:
                print(match.group(0))
            print("=" * 60)
        else:
            print("No changes needed")
        sys.exit(0)

    if changed:
        print(f"✅ Updated {agents_md}")
    else:
        print(f"✅ {agents_md} TOC already current")


if __name__ == "__main__":
    main()
