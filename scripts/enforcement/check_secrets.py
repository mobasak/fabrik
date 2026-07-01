#!/usr/bin/env python3
"""Check for hardcoded secrets and credentials."""

import re
from pathlib import Path

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?:aws_secret|AWS_SECRET)[^=]*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", "AWS Secret Key"),
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API Key"),
    (r"sk-ant-[a-zA-Z0-9\-]{32,}", "Anthropic API Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub PAT"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Key"),
    (r"rk_live_[a-zA-Z0-9]{24,}", "Stripe Restricted Key"),
    # The (?!\$\{|\$[A-Z]|<) lookahead skips passwords that are SHELL VARIABLES
    # (${POSTGRES_PASSWORD}, $PGPASS) or ANGLE-BRACKET PLACEHOLDERS (<pw>,
    # <password>) in docstrings/READMEs — both are the correct way to REFERENCE
    # a secret, not hardcode one. A literal password (postgresql://u:realpass@)
    # is still caught.
    (r"postgresql://[^:]+:(?!\$\{|\$[A-Za-z_]|<)[^@\s]+@", "DB URL with password"),
    (r"mongodb(\+srv)?://[^:]+:(?!\$\{|\$[A-Za-z_]|<)[^@\s]+@", "MongoDB URL with password"),
    (r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    (r"Bearer\s+[a-zA-Z0-9\-_\.]{20,}", "Bearer Token"),
    # The (?![A-Z_]*=['"]?\s*$) trailing check rejects env-var NAME strings
    # like "WATCHDOG_RO_PG_PASSWORD=" that show up when code PARSES a .env
    # file — the quoted "value" is actually the search key ending in `=`,
    # not a credential. A real hardcoded credential ends in a value literal.
    # `[^'\"\n]` (not `[^'\"]`) forces the value to be ON THE SAME LINE. Without
    # \n exclusion the pattern spans line breaks and matches innocuous adjacent
    # code: `if x.startswith("WATCHDOG_PASSWORD=")` on line N glued to a quote
    # on line N+1. Same-line constraint mirrors how real hardcoded credentials
    # actually appear (`password = "hunter2"` on one line).
    (
        r"(?:password|secret|api_key|token)\s*[:=]\s*['\"][^'\"\n]{8,}['\"]",
        "Hardcoded credential",
    ),
]

SKIP_PATTERNS = [
    r"\.env\.example$",
    r"/test_[^/]+\.py$",
    r"fixtures/",
    r"mocks/",
    r"check_secrets\.py$",  # Skip self to avoid false positives on patterns
]


def check_file(file_path: Path) -> list:
    """Check a file for hardcoded secrets."""
    try:
        from .validate_conventions import CheckResult, Severity
    except ImportError:  # standalone run (final_gate executes `python <path>`)
        from validate_conventions import CheckResult, Severity

    results = []
    if any(re.search(p, str(file_path), re.I) for p in SKIP_PATTERNS):
        return results
    if file_path.suffix.lower() in (".jpg", ".png", ".gif", ".pdf", ".zip"):
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    lines = content.splitlines()
    for pattern, desc in SECRET_PATTERNS:
        for match in re.finditer(pattern, content, re.I):
            line_num = content[: match.start()].count("\n") + 1
            # Skip lines with noqa comments
            if line_num <= len(lines) and "noqa" in lines[line_num - 1]:
                continue
            secret = match.group()
            masked = secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "***"
            results.append(
                CheckResult(
                    check_name="secrets",
                    severity=Severity.ERROR,
                    message=f"{desc}: {masked}",
                    file_path=str(file_path),
                    line_number=line_num,
                    fix_hint="Use env vars. Store in .env, document in .env.example",
                )
            )
    return results


def _changed_files() -> list[str]:
    """Files changed in git (unstaged + staged + untracked) — bound the scan to
    the diff, NOT the whole repo (mirrors validate_conventions.get_git_diff_files
    so existing violations don't retroactively red every project; only new
    changes are gated)."""
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
    """Scan CHANGED files for hardcoded secrets; exit 1 on any ERROR-severity
    finding so final_gate's "Secrets (Zero Hardcoding)" gate actually bites.

    This file previously had no entry point — running it did nothing and the gate
    was a permanent no-op. Runs standalone (how final_gate invokes it); the
    Severity import falls back to absolute when there is no package context.
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
            f"\n{len(errors)} hardcoded secret(s) in changed files. Use env vars; "
            "store in .env, document in .env.example. (False positive? add `# noqa`.)"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
