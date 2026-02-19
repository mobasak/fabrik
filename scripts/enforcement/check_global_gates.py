#!/usr/bin/env python3
"""Global gate runner for Fabrik projects.

Deterministic gate checks with PROJECT/MONOREPO_ROOT classification.
Exit codes: 0=pass, 1=warn (root symlink mismatch only), 2=fail.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def classify_path(path: Path) -> str:
    """Classify path as PROJECT or MONOREPO_ROOT.

    Returns "PROJECT" if all of:
      - pyproject.toml exists
      - path starts with /opt/
      - path does NOT start with /opt/fabrik
      - .windsurf/ directory exists

    Returns "MONOREPO_ROOT" otherwise.
    """
    has_pyproject = (path / "pyproject.toml").exists()
    is_opt = str(path).startswith("/opt/")
    is_not_fabrik = not str(path).startswith("/opt/fabrik")
    has_windsurf = (path / ".windsurf").exists()

    if has_pyproject and is_opt and is_not_fabrik and has_windsurf:
        return "PROJECT"
    return "MONOREPO_ROOT"


def run_cmd(cmd: list[str], cwd: Path, label: str) -> bool:
    """Run a command and return True on success.

    Prints stdout/stderr on failure.
    """
    print(f"[{label}] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[{label}] FAILED (exit {result.returncode})")
        if result.stdout.strip():
            print(result.stdout)
        if result.stderr.strip():
            print(result.stderr)
        return False

    print(f"[{label}] PASSED")
    return True


def check_symlinks(path: Path, mode: str) -> int:
    """Check symlink integrity.

    Returns:
        0 - all symlinks correct
        1 - warn (MONOREPO_ROOT with missing/wrong symlink)
        2 - fail (PROJECT with missing/wrong symlink)
    """
    symlinks = [
        (".windsurfrules", "/opt/fabrik/windsurfrules"),
        (".windsurf/rules", "/opt/fabrik/.windsurf/rules"),
    ]

    code = 0

    for symlink, target in symlinks:
        link_path = path / symlink
        target_path = Path(target)

        if not link_path.is_symlink():
            # Missing or regular file
            if mode == "PROJECT":
                print(f"FAIL: missing symlink {symlink}")
                return 2
            else:
                print(f"WARN: missing symlink {symlink}")
                code = max(code, 1)
            continue

        # Check target matches
        try:
            resolved = Path(link_path).resolve()
            expected = Path(target_path).resolve()

            if resolved != expected:
                if mode == "PROJECT":
                    print(f"FAIL: symlink {symlink} points to {resolved}, expected {expected}")
                    return 2
                else:
                    print(f"WARN: symlink {symlink} points to {resolved}, expected {expected}")
                    code = max(code, 1)
        except OSError as e:
            if mode == "PROJECT":
                print(f"FAIL: cannot resolve symlink {symlink}: {e}")
                return 2
            else:
                print(f"WARN: cannot resolve symlink {symlink}: {e}")
                code = max(code, 1)

    if code == 0:
        print("[Symlinks] PASSED")
    return code


def main() -> int:
    """Run all global gates."""
    parser = argparse.ArgumentParser(description="Run global gates for Fabrik projects")
    parser.add_argument("--path", default=".", help="Path to check (default: current directory)")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    print(f"Checking path: {path}")

    mode = classify_path(path)
    print(f"Classification: {mode}")
    print()

    fabrik_root = Path("/opt/fabrik")

    # Gate 1: pytest tests/
    if not run_cmd(["pytest", "tests/"], cwd=fabrik_root, label="Tests"):
        return 2

    # Gate 2: ruff check
    if not run_cmd(["ruff", "check", str(path)], cwd=path, label="Lint"):
        return 2

    # Gate 3: mypy
    if not run_cmd(["mypy", str(path)], cwd=path, label="Types"):
        return 2

    # Gate 4: pre-commit
    if not run_cmd(["pre-commit", "run", "--all-files"], cwd=path, label="Pre-commit"):
        return 2

    # Gate 5: docs-check (only valid at repo root)
    if path != fabrik_root:
        print("FAIL: docs-check requires repo root (/opt/fabrik)")
        return 2
    if not run_cmd(["make", "docs-check"], cwd=fabrik_root, label="Docs"):
        return 2

    # Gate 6: symlinks
    symlink_code = check_symlinks(path, mode)
    if symlink_code == 2:
        return 2

    print()
    if symlink_code == 0:
        print("All gates PASSED")
    else:
        print("All gates passed with warnings")

    return symlink_code


if __name__ == "__main__":
    sys.exit(main())
