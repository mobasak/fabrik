#!/usr/bin/env python3
"""Test consolidate_envs.py to ensure no data loss."""

import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

import re

from consolidate_envs import consolidate_envs, parse_env_file


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


def test_sentinel_skipping_preserves_trailing_edits():
    """Regression test for LESSONS_LEARNT §8.16.

    Pre-sentinel behavior: a manual var appended AFTER the auto-generated
    project block was dropped because parse_env_file stopped at the first
    `# Project:` header.  Post-sentinel: the parser skips only between
    sentinels, so trailing edits survive.
    """
    print("\n=== Sentinel trailing-edit preservation ===")
    from consolidate_envs import AUTO_BEGIN_SENTINEL, AUTO_END_SENTINEL

    content = f"""# Consolidated Environment
# ===
# Fabrik Core Configuration
# ===
TOP_VAR=top

{AUTO_BEGIN_SENTINEL}

# ===
# Project: foo
# ===
PROJECT_VAR=mirrored

{AUTO_END_SENTINEL}

# Trailing manual addition (pre-sentinel: this was silently dropped)
TRAILING_VAR=should_survive
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        test_file = Path(f.name)

    try:
        vars_ = parse_env_file(test_file, skip_auto_sections=True)
        results = []
        for expected in ("TOP_VAR", "TRAILING_VAR"):
            ok = expected in vars_
            results.append(ok)
            print(f"{expected}: {'✓ PASS' if ok else '✗ FAIL — DROPPED'}")
        # PROJECT_VAR (inside sentinels) must be skipped
        skipped = "PROJECT_VAR" not in vars_
        results.append(skipped)
        print(f"PROJECT_VAR skipped: {'✓ PASS' if skipped else '✗ FAIL — leaked into FABRIK_CORE'}")
        return all(results)
    finally:
        test_file.unlink()


def test_legacy_fallback_without_sentinels():
    """Pre-migration files (no sentinels) must still parse correctly via
    the stop_at_project_sections fallback."""
    print("\n=== Legacy fallback (no sentinels) ===")
    content = """# Fabrik Core
TOP_VAR=top

# Project: foo
PROJECT_VAR=mirrored
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(content)
        test_file = Path(f.name)
    try:
        vars_ = parse_env_file(test_file, skip_auto_sections=True, stop_at_project_sections=True)
        ok_top = "TOP_VAR" in vars_
        ok_skip = "PROJECT_VAR" not in vars_
        print(f"TOP_VAR kept: {'✓ PASS' if ok_top else '✗ FAIL'}")
        print(f"PROJECT_VAR skipped via legacy path: {'✓ PASS' if ok_skip else '✗ FAIL'}")
        return ok_top and ok_skip
    finally:
        test_file.unlink()


def test_consolidator_emits_sentinels():
    """Full regeneration must bracket auto sections with sentinels."""
    print("\n=== Consolidator emits sentinels ===")
    from consolidate_envs import AUTO_BEGIN_SENTINEL, AUTO_END_SENTINEL

    content, _ = consolidate_envs()
    has_begin = AUTO_BEGIN_SENTINEL in content
    has_end = AUTO_END_SENTINEL in content
    # Ordering: BEGIN must come before END
    ordering_ok = (
        has_begin
        and has_end
        and content.index(AUTO_BEGIN_SENTINEL) < content.index(AUTO_END_SENTINEL)
    )
    print(f"BEGIN sentinel present: {'✓ PASS' if has_begin else '✗ FAIL'}")
    print(f"END sentinel present: {'✓ PASS' if has_end else '✗ FAIL'}")
    print(f"BEGIN before END: {'✓ PASS' if ordering_ok else '✗ FAIL'}")
    return has_begin and has_end and ordering_ok


if __name__ == "__main__":
    results = [
        test_parse_preserves_all_vars(),
        test_consolidation_preserves_existing(),
        test_sentinel_skipping_preserves_trailing_edits(),
        test_legacy_fallback_without_sentinels(),
        test_consolidator_emits_sentinels(),
    ]

    if all(results):
        print("\n✓ ALL TESTS PASSED")
        exit(0)
    else:
        print(f"\n✗ TESTS FAILED ({sum(results)}/{len(results)} passed)")
        exit(1)
