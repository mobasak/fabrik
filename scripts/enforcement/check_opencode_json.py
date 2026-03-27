#!/usr/bin/env python3
"""
Enforcement check: Validate opencode.json contains Kilo-safe rule list only.

This check ensures that opencode.json instructions exactly match the approved
Kilo-safe allowlist and ordering, preventing regression where Cascade-only
rules could be accidentally included.

Author: Cascade enforcement system
"""

import json
import sys
from pathlib import Path

# Expected Kilo-safe instruction list in exact order
# NOTE: Only AGENTS-compact.md for Kilo agents
EXPECTED_INSTRUCTIONS = [
    "AGENTS-compact.md",
]

# Forbidden files that must never appear in opencode.json
FORBIDDEN_PATTERNS = [
    ".windsurf/rules/*.md",  # The glob we replaced
    ".windsurf/rules/00-critical.md",  # Cascade-only (critical rules too verbose for Kilo)
]


def check_opencode_json(project_root: Path) -> tuple[bool, str]:
    """
    Validate opencode.json contains exactly the Kilo-safe instruction list.

    Returns:
        tuple: (is_valid, error_message)
    """
    opencode_path = project_root / "opencode.json"

    if not opencode_path.exists():
        return False, "opencode.json not found"

    try:
        with open(opencode_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in opencode.json: {e}"

    # Check structure
    if "instructions" not in data:
        return False, "Missing 'instructions' field in opencode.json"

    instructions = data["instructions"]

    if not isinstance(instructions, list):
        return False, "'instructions' must be a list"

    # Check for forbidden patterns
    for instruction in instructions:
        for forbidden in FORBIDDEN_PATTERNS:
            if forbidden in instruction:
                return False, f"Forbidden pattern found: {forbidden}"

    # Check exact match with expected list
    if instructions != EXPECTED_INSTRUCTIONS:
        diff_details = []

        # Missing instructions
        missing = set(EXPECTED_INSTRUCTIONS) - set(instructions)
        if missing:
            diff_details.append(f"Missing: {sorted(missing)}")

        # Extra instructions
        extra = set(instructions) - set(EXPECTED_INSTRUCTIONS)
        if extra:
            diff_details.append(f"Extra: {sorted(extra)}")

        # Order mismatch (if same items but different order)
        if set(instructions) == set(EXPECTED_INSTRUCTIONS):
            for i, (expected, actual) in enumerate(
                zip(EXPECTED_INSTRUCTIONS, instructions, strict=True)
            ):
                if expected != actual:
                    diff_details.append(
                        f"Order mismatch at position {i}: expected '{expected}', got '{actual}'"
                    )
                    break

        return False, f"Instructions don't match expected Kilo-safe list. {'; '.join(diff_details)}"

    return True, "opencode.json contains correct Kilo-safe instruction list"


def main():
    """Main entry point for enforcement check."""
    project_root = Path.cwd()

    is_valid, message = check_opencode_json(project_root)

    if is_valid:
        print(f"✓ {message}")
        sys.exit(0)
    else:
        print(f"✗ {message}")
        print("\nExpected Kilo-safe instruction list:")
        for i, instruction in enumerate(EXPECTED_INSTRUCTIONS, 1):
            print(f"  {i}. {instruction}")
        sys.exit(1)


if __name__ == "__main__":
    main()
