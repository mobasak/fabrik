#!/usr/bin/env python3
"""
Lint Fix Sub-Agent - Cheap agent for lint-only fixes.

Called by main agent when final_gate.py fails with only lint issues.
Uses the cheapest available agent (DeepSeek, Free tier) to fix the issues.

Usage:
    python scripts/lint_fix_agent.py --files src/file.py --errors "mypy: Missing return"

This is a cost optimization: instead of expensive coder agent fixing lint,
use a cheap agent specifically for lint fixes.

Cost comparison:
    - Sonnet 4.6: ~$0.30-0.50 per call
    - DeepSeek v3.2: ~$0.01-0.03 per call (10x cheaper)
"""

import argparse
import subprocess
import sys

# Cheapest model for lint fixes
LINT_FIX_MODEL = "kilo/deepseek/deepseek-v3.2"
LINT_FIX_AGENT = "code"
LINT_FIX_VARIANT = "low"


def run_lint_fix(files: list[str], errors: str, dry_run: bool = False) -> int:
    """Run cheap agent to fix lint errors."""
    prompt = f"""Fix these lint errors. Make minimal changes only.

FILES: {", ".join(files)}

ERRORS:
{errors}

Rules:
1. Fix ONLY the reported errors
2. Do not refactor or improve other code
3. Preserve existing style
4. If unsure, add type: ignore comment with explanation
"""

    cmd = [
        "kilo",
        "run",
        "--model",
        LINT_FIX_MODEL,
        "--agent",
        LINT_FIX_AGENT,
        "--variant",
        LINT_FIX_VARIANT,
        "--auto",
        "--format",
        "default",
    ]

    # Add files
    for f in files:
        cmd.extend(["--file", f])

    # Use -- to separate options from message (prevents kilo treating prompt as file)
    cmd.append("--")
    cmd.append(prompt)

    if dry_run:
        print(f"[DRY RUN] Would run: {' '.join(cmd[:10])}...")
        print(f"[DRY RUN] Files: {files}")
        print(f"[DRY RUN] Errors:\n{errors}")
        return 0

    print(f"🔧 Running lint fix agent ({LINT_FIX_MODEL})...")
    print(f"📁 Files: {', '.join(files)}")
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def parse_gate_output(gate_output: str) -> tuple[list[str], str]:
    """Parse final_gate.py output to extract failed files and errors."""
    files = set()
    errors = []

    for line in gate_output.split("\n"):
        # Extract file paths from error messages
        if ".py:" in line:
            # Format: src/file.py:10:5: error
            parts = line.split(":")
            if parts and parts[0].endswith(".py"):
                files.add(parts[0])
                errors.append(line)
        elif "[FAIL]" in line:
            errors.append(line)

    return list(files), "\n".join(errors)


def main():
    parser = argparse.ArgumentParser(description="Lint fix sub-agent")
    parser.add_argument("--files", nargs="+", help="Files to fix")
    parser.add_argument("--errors", help="Error messages to fix")
    parser.add_argument("--gate-output", help="Parse final_gate.py output")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    if args.gate_output:
        files, errors = parse_gate_output(args.gate_output)
    elif args.files and args.errors:
        files = args.files
        errors = args.errors
    else:
        print("Error: Provide --files + --errors OR --gate-output")
        return 1

    if not files:
        print("No files to fix")
        return 0

    return run_lint_fix(files, errors, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
