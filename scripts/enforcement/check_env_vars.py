#!/usr/bin/env python3
"""Check for hardcoded localhost/127.0.0.1 in code.

Detects environment variable violations that break Docker/VPS deployments.
"""

import re
from pathlib import Path

# Patterns that indicate hardcoded localhost
HARDCODED_PATTERNS = [
    (
        r"(?:host|HOST|url|URL|uri|URI|server|SERVER)"
        r"""\s*[=:]\s*['"](?:localhost|127\.0\.0\.1)['"]""",
        "hardcoded host assignment",
    ),
    (r'["\']localhost:\d+["\']', "hardcoded localhost with port"),
    (r'["\']127\.0\.0\.1:\d+["\']', "hardcoded 127.0.0.1 with port"),
    (r"http://localhost[:/]", "hardcoded http://localhost URL"),
    (r"http://127\.0\.0\.1[:/]", "hardcoded http://127.0.0.1 URL"),
]

# Patterns that indicate proper usage (allowlist) - must be specific
ALLOWED_CONTEXTS = [
    # os.getenv / os.environ.get default — allow an optional URL scheme so
    # os.getenv("LOKI_URL", "http://localhost:3100") is recognized as the
    # sanctioned pattern, not just the bare "localhost" form.
    r"os\.getenv\s*\([^)]*,\s*['\"](?:https?://)?(?:localhost|127\.0\.0\.1)",  # os.getenv default
    r"os\.environ\.get\s*\([^)]*,\s*['\"](?:https?://)?(?:localhost|127\.0\.0\.1)",  # os.environ.get default
    r"#\s*.*(?:localhost|127\.0\.0\.1)",  # Comments with localhost/127.0.0.1
    r"^\s*#",  # Line starting with comment
    r"\.env\.example",  # Example env files
    r"#\s*noqa",  # noqa comments
]


def check_file(file_path: Path) -> list:
    """Check a file for hardcoded localhost patterns.

    Returns list of CheckResult objects.
    """
    # Import here to avoid circular imports
    try:
        from .validate_conventions import CheckResult, Severity
    except ImportError:  # standalone run (final_gate executes `python <path>`)
        from validate_conventions import CheckResult, Severity

    results: list[CheckResult] = []

    # Check Python, TypeScript, JavaScript files
    if file_path.suffix.lower() not in (".py", ".ts", ".tsx", ".js", ".jsx"):
        return results

    # Skip test files
    if "test" in file_path.name.lower() or "spec" in file_path.name.lower():
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Template-generator modules (e.g. scaffold.py) EMIT localhost dev URLs into
    # scaffolded projects — their string literals are output templates, not runtime
    # config. Such a file opts out with a top-level `# noqa-file: template-generator`
    # marker. Scoped to THIS localhost check; all other gate checks still run.
    if "noqa-file: template-generator" in content:
        return results

    lines = content.splitlines()

    for line_num, line in enumerate(lines, 1):
        # Skip if line contains allowed pattern
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in ALLOWED_CONTEXTS):
            continue

        # Check for violations
        for pattern, description in HARDCODED_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                results.append(
                    CheckResult(
                        check_name="env_vars",
                        severity=Severity.ERROR,
                        message=f"{description.capitalize()}. Use os.getenv() instead.",
                        file_path=str(file_path),
                        line_number=line_num,
                        fix_hint="Replace with os.getenv('DB_HOST', 'localhost')",
                    )
                )
                break  # One violation per line is enough

    return results


def _changed_files() -> list[str]:
    """Files changed in git (unstaged + staged + untracked) — bound the scan to
    the diff, NOT the whole repo, so only new changes are gated."""
    import subprocess

    files: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--staged", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
            files.update(out.splitlines())
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return [f for f in files if f]


def main() -> int:
    """Scan CHANGED files for hardcoded localhost/127.0.0.1; exit 1 on any
    ERROR so final_gate's ".env Updates (Secrets)" gate actually bites.

    This file previously had no entry point — the gate was a permanent no-op.
    Runs standalone (how final_gate invokes it); the Severity import falls back
    to absolute when there is no package context.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from .validate_conventions import Severity
    except ImportError:
        from validate_conventions import Severity

    errors = [
        r
        for rel in _changed_files()
        if (p := Path(rel)).is_file()
        for r in check_file(p)
        if r.severity == Severity.ERROR
    ]
    for r in errors:
        print(f"❌ {r.file_path}:{r.line_number} — {r.message}")
    if errors:
        print(
            f"\n{len(errors)} hardcoded localhost/host violation(s) in changed files. "
            "Use os.getenv() — postgres-main:5432 / redis-main:6379 on the VPS, not localhost. "
            "(False positive? add `# noqa`.)"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
