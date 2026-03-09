#!/usr/bin/env python3
"""
Traycer Report Writer

Extracts report markdown from agent stdout and writes to .droid/traycer-reports/latest.md.
Used by factory_wait.py to persist agent-generated reports for the Windsurf Report Panel.

Usage:
    python scripts/traycer_write_report.py < agent_stdout.txt
    python scripts/traycer_write_report.py --file agent_stdout.txt --slug task-name

Usage Example:
    # Pipe agent output directly to the report writer
    kilo run --model gpt-5.1-codex-max "$PROMPT" | python scripts/traycer_write_report.py --slug my-task
    factory_wait.py | python scripts/traycer_write_report.py
"""

import argparse
import os
import re
import sys
from pathlib import Path


def sanitize_slug(slug: str) -> str:
    """
    Sanitize slug for safe filename usage.

    Algorithm:
    1. Convert to lowercase
    2. Replace any character not [a-z0-9] with '-'
    3. Collapse multiple '-' into single '-'
    4. Strip leading/trailing '-'

    Example:
        "/// auth  v2  ///" -> "auth-v2"
    """
    # Step 1: lowercase
    slug = slug.lower()

    # Step 2: replace non-alphanumeric with '-'
    slug = re.sub(r"[^a-z0-9]+", "-", slug)

    # Step 3: collapse multiple '-' into one
    slug = re.sub(r"-+", "-", slug)

    # Step 4: strip leading/trailing '-'
    slug = slug.strip("-")

    return slug or "traycer-task"  # fallback if empty after sanitization


def resolve_slug(args_slug: str | None) -> str:
    """
    Resolve slug from multiple sources in priority order.

    Priority:
    1. --slug CLI argument
    2. TRAYCER_TASK_ID environment variable
    3. TRAYCER_PHASE_ID environment variable
    4. Fallback: "traycer-task"
    """
    slug = (
        args_slug or os.getenv("TRAYCER_TASK_ID") or os.getenv("TRAYCER_PHASE_ID") or "traycer-task"
    )
    return sanitize_slug(slug)


def extract_report(content: str) -> str | None:
    """
    Extract report markdown between delimiters.

    Returns:
        Report content without delimiters, or None if not found.
    """
    pattern = r"BEGIN_TRAYCER_REPORT_MD\s*(.*?)\s*END_TRAYCER_REPORT_MD"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None


def write_report_atomic(report_dir: Path, slug: str, content: str) -> None:
    """
    Write report to timestamped file and atomic latest.md symlink.

    Args:
        report_dir: .droid/traycer-reports directory
        slug: sanitized slug for filename
        content: report markdown content
    """
    from datetime import datetime

    # Ensure directory exists
    report_dir.mkdir(parents=True, exist_ok=True)

    # Timestamped filename with microseconds to prevent collisions
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    timestamped_file = report_dir / f"{timestamp}-{slug}.md"

    # Write timestamped file
    timestamped_file.write_text(content, encoding="utf-8")

    # Atomic write to latest.md (unique temp file with PID, then rename)
    latest_file = report_dir / "latest.md"
    temp_file = report_dir / f".latest.md.tmp.{os.getpid()}"

    temp_file.write_text(content, encoding="utf-8")
    temp_file.rename(latest_file)  # POSIX atomic on same filesystem

    print("📝 Report written: .droid/traycer-reports/latest.md", file=sys.stderr)


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (always 0 - never fail pipeline)
    """
    parser = argparse.ArgumentParser(description="Extract and write Traycer report")
    parser.add_argument("--file", help="Input file (default: stdin)")
    parser.add_argument("--slug", help="Report slug (default: from env or 'traycer-task')")
    args = parser.parse_args()

    try:
        # Read input
        content = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()

        # Extract report
        report = extract_report(content)

        if report is None:
            print("⚠️ No report block found; panel will not update.", file=sys.stderr)
            return 0  # Not a failure - just no report to write

        # Resolve slug and write
        slug = resolve_slug(args.slug)

        # Use current working directory (project root where Traycer runs the agent)
        # This allows reports to work in any /opt/* project, not just /opt/fabrik/
        repo_root = Path.cwd()
        report_dir = repo_root / ".droid" / "traycer-reports"

        write_report_atomic(report_dir, slug, report)

    except Exception as e:
        # Log error but don't fail pipeline
        print(f"⚠️ Report writer error: {e}", file=sys.stderr)

    return 0  # Always exit 0 - never fail pipeline


if __name__ == "__main__":
    sys.exit(main())
