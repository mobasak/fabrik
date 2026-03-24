#!/usr/bin/env python3
"""
Check that the One-Test Rule proposal exists in the latest plan.

This script verifies that when agents create or modify code, they have
documented their test justification following the Solo-Dev Creed.

Exit codes:
    0: One-Test Rule proposal found (or no plan exists)
    1: Plan exists but missing One-Test Rule metadata
"""

import sys
from pathlib import Path


def check_proposal() -> bool:
    """Check latest plan for One-Test Rule proposal.

    Returns:
        True if proposal found or no plan exists, False if missing
    """
    plans_dir = Path("docs/development/plans/")

    # If no plans directory exists, skip check
    if not plans_dir.exists():
        print("INFO: No plans directory found - skipping One-Test Rule check")
        return True

    # Find latest plan by modification time (not alphabetical)
    plans = list(plans_dir.glob("*.md"))
    if not plans:
        print("INFO: No plan files found - skipping One-Test Rule check")
        return True

    latest_plan = max(plans, key=lambda p: p.stat().st_mtime)
    content = latest_plan.read_text()

    # Required keywords for One-Test Rule proposal
    required_keywords = ["One-Test Rule", "Given", "When", "Then"]

    missing = [k for k in required_keywords if k.lower() not in content.lower()]

    if missing:
        print(f"FAIL: Plan {latest_plan.name} is missing One-Test Rule metadata")
        print(f"      Missing keywords: {', '.join(missing)}")
        print("\nOne-Test Rule format:")
        print("  ## One-Test Rule")
        print("  **Why:** [Justification]")
        print("  **Contract:**")
        print("  - **Given:** [Initial state]")
        print("  - **When:** [Action]")
        print("  - **Then:** [Expected result]")
        print("  - **Mocked:** [What is mocked vs. real]")
        return False

    print(f"PASS: One-Test Rule proposal found in {latest_plan.name}")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_proposal() else 1)
