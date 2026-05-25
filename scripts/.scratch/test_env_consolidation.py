#!/usr/bin/env python3
"""Test consolidate_envs.py to ensure no data loss."""

import re
import tempfile
from pathlib import Path

from scripts.consolidate_envs import consolidate_envs, parse_env_file


def test_parse_preserves_all_vars():
    """Test that parse_env_file reads all variable types."""
    test_content = """# Test comment
UPPERCASE_VAR=value1
lowercase_var=value2
MixedCase_Var=value3
_UNDERSCORE=value4
VAR_WITH_QUOTES="quoted value"
VAR_WITH_SPACES=value with spaces
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(test_content)
        f.flush()
        test_file = Path(f.name)

    try:
        result = parse_env_file(test_file)

        expected_vars = {
            "UPPERCASE_VAR": "value1",
            "lowercase_var": "value2",
            "MixedCase_Var": "value3",
            "_UNDERSCORE": "value4",
            "VAR_WITH_QUOTES": "quoted value",
            "VAR_WITH_SPACES": "value with spaces",
        }

        print("=== Parse Test Results ===")
        for var_name, expected_value in expected_vars.items():
            if var_name in result:
                actual_value = result[var_name][0]
                status = (
                    "✓ PASS" if actual_value == expected_value else f"✗ FAIL (got: {actual_value})"
                )
                print(f"{var_name}: {status}")
            else:
                print(f"{var_name}: ✗ MISSING")

        print(f"\nTotal vars parsed: {len(result)}/{len(expected_vars)}")

        return len(result) == len(expected_vars)

    finally:
        test_file.unlink()


def test_consolidation_preserves_existing():
    """Test that consolidation keeps all existing .env vars."""
    # This would test against real .env but we'll do dry-run only
    print("\n=== Consolidation Preservation Test ===")

    # Parse actual .env
    actual_env = Path("/opt/fabrik/.env")
    if not actual_env.exists():
        print("✗ .env not found")
        return False

    original_vars = parse_env_file(actual_env)
    original_count = len(original_vars)

    print(f"Original .env vars: {original_count}")

    # Run consolidation
    consolidated_content, stats = consolidate_envs()

    # Parse consolidated output
    consolidated_vars = {}
    for line in consolidated_content.splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.strip())
        if match:
            consolidated_vars[match.group(1)] = match.group(2).strip('"').strip("'")

    print(f"Consolidated vars: {len(consolidated_vars)}")

    # Find missing vars
    missing = set(original_vars.keys()) - set(consolidated_vars.keys())

    if missing:
        print(f"\n✗ FAIL - Missing {len(missing)} vars:")
        for var in sorted(missing)[:10]:
            print(f"  - {var}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return False
    else:
        print("✓ PASS - All original vars preserved")
        return True


if __name__ == "__main__":
    parse_ok = test_parse_preserves_all_vars()
    consolidate_ok = test_consolidation_preserves_existing()

    if parse_ok and consolidate_ok:
        print("\n✓ ALL TESTS PASSED")
        exit(0)
    else:
        print("\n✗ TESTS FAILED")
        exit(1)
