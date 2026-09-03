#!/usr/bin/env python3
# AFTER-EDIT: none
"""Check for hardcoded localhost/127.0.0.1 in code.

Detects environment variable violations that break Docker/VPS deployments.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    from .validate_conventions import CheckResult, Severity
except ImportError:  # standalone run (final_gate executes `python <path>`)
    from validate_conventions import CheckResult, Severity  # type: ignore[no-redef]

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
    # Any-scheme URL whose host is localhost, with optional userinfo — catches
    # `postgresql://user@localhost:5432/db` and `redis://localhost:6379`, the exact
    # DATABASE_URL/REDIS_URL "@localhost" HARD STOP that the http-only patterns above
    # miss. Sanctioned env-var defaults are exempted first via ALLOWED_CONTEXTS.
    (
        r"://(?:[^'\"\s/@]*@)?(?:localhost|127\.0\.0\.1)[:/]",
        "hardcoded localhost in URL (any scheme)",
    ),
]

# A localhost/127.0.0.1 literal is SANCTIONED only when it is the dev-time DEFAULT of
# an environment-variable read — the same code reads the real host (postgres-main,
# redis-main, …) from the env in Docker/VPS. Recognize that idiom broadly, or the gate
# false-flags legitimate config: the check scans .py AND .ts/.tsx/.js/.jsx, so it must
# know the JS/TS `process.env.X || "…"` / `?? "…"` form too, not just Python's; it must
# accept ANY URL scheme (redis://, postgresql://, amqp://, ws://, http(s)://), not only
# http(s); and Python's keyword-arg `default="…"` form, not only the positional one.
# The teeth stay intact: a bare `url = "http://localhost:3000"` (no env read) is NOT
# matched here and is still flagged by HARDCODED_PATTERNS.
_ENV_DEFAULT_LOCALHOST = (
    r"['\"](?:[a-zA-Z][\w+.\-]*://)?(?:[^'\"@\s/]*@)?(?:localhost|127\.0\.0\.1)"
)

# Patterns that indicate proper usage (allowlist) - must be specific
ALLOWED_CONTEXTS = [
    # Python: os.getenv(KEY, "…localhost…") / os.environ.get(KEY, default="…localhost…")
    rf"os\.getenv\s*\([^)]*,\s*(?:default\s*=\s*)?{_ENV_DEFAULT_LOCALHOST}",
    rf"os\.environ\.get\s*\([^)]*,\s*(?:default\s*=\s*)?{_ENV_DEFAULT_LOCALHOST}",
    # JS/TS: process.env.KEY || "…localhost…"  /  process.env.KEY ?? "…localhost…"
    rf"process\.env\.[A-Za-z0-9_]+\s*(?:\|\||\?\?)\s*{_ENV_DEFAULT_LOCALHOST}",
    r"#\s*.*(?:localhost|127\.0\.0\.1)",  # Python comments referencing localhost/127.0.0.1
    r"^\s*#",  # Line starting with comment
    r"\.env\.example",  # Example env files
    r"#\s*noqa",  # noqa comments
]


# The getenv-default positions a shared constant may legitimately occupy. ``{name}`` is
# substituted with the constant's own identifier, so an unrelated symbol never matches.
_CONST_DEFAULT_USES = (
    r"os\.getenv\s*\([^)]*\)\s*or\s+{name}\b",  # os.getenv("K") or NAME
    r"os\.getenv\s*\([^)]*,\s*(?:default\s*=\s*)?{name}\b",  # os.getenv("K", NAME)
    r"os\.environ\.get\s*\([^)]*\)\s*or\s+{name}\b",
    r"os\.environ\.get\s*\([^)]*,\s*(?:default\s*=\s*)?{name}\b",
    r"process\.env\.[A-Za-z0-9_]+\s*(?:\|\||\?\?)\s*{name}\b",  # JS/TS
)

_CONST_ASSIGN_RE = re.compile(
    # Python `NAME = "…"` / `NAME: str = "…"` and the JS/TS `export const NAME = "…";` form —
    # this check scans .ts/.tsx/.js/.jsx as well as .py, so a Python-only shape would leave the
    # JS half of the false positive in place.
    r"""^\s*(?:(?:export\s+)?(?:const|let|var)\s+)?"""
    r"""(?P<name>[A-Z][A-Z0-9_]*)\s*(?::\s*[^=]+)?=\s*['"][^'"]*['"]\s*;?\s*(?:(?:#|//).*)?$"""
)


def _is_env_default_constant(line: str, lines: list[str], line_num: int) -> bool:
    """Is *line* a bare UPPER_SNAKE constant whose EVERY other mention is a getenv default?

    The sanctioned ``os.getenv(KEY, default)`` idiom, written across two lines: a module
    constant holding the default and a getenv read consuming it (wef finding
    01M1MC5BBHEJJ3SYMS55NZBHAD — the per-line regex graded the FORM of the safe pattern
    instead of the pattern, because it cannot see a read two hundred lines away). Sharing one
    default between the getenv read and the test that asserts it is idiomatic, so the false
    positive recurs wherever that is done.

    Deliberately narrow, so the ban keeps its teeth: returns False when the constant is never
    read (an unused localhost literal is still a smell) and when ANY mention sits outside a
    getenv-default position — including a direct use such as ``requests.get(DEFAULT_API_URL)``,
    which is precisely what the ban exists to catch. Comment lines are ignored.
    """
    m = _CONST_ASSIGN_RE.match(line)
    if m is None:
        return False
    name = re.escape(m.group("name"))
    uses = [
        other
        for i, other in enumerate(lines, 1)
        if i != line_num and re.search(rf"\b{name}\b", other)
    ]
    if not uses:
        return False
    patterns = [re.compile(p.format(name=name)) for p in _CONST_DEFAULT_USES]
    return all(
        other.lstrip().startswith("#") or any(p.search(other) for p in patterns) for other in uses
    )


def check_file(file_path: Path) -> list[CheckResult]:
    """Check a file for hardcoded localhost patterns.

    Returns list of CheckResult objects.
    """

    results: list[CheckResult] = []

    # Check Python, TypeScript, JavaScript files
    if file_path.suffix.lower() not in (".py", ".ts", ".tsx", ".js", ".jsx"):
        return results

    # Skip test files
    if "test" in file_path.name.lower() or "spec" in file_path.name.lower():
        return results

    # docs/ holds documentation + archived examples, never production code.
    if file_path.parts and file_path.parts[0] == "docs":
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
        # Container-internal localhost: inside a `docker exec … sh -c '…'` command string,
        # localhost IS the container — the correct host, not an app→DB shortcut (fleet
        # finding 01M05N9CVESBMTS7QX80NY8AYB: a meilisearch self-probe redded the gate on
        # every unrelated touch of the file). A shell command is routinely a MULTI-LINE
        # Python string, so the docker-exec marker sits on a NEARBY line: look back a
        # short, fixed window. The teeth stay: without `docker exec` above, localhost in
        # a string is still flagged.
        if any(
            "docker exec" in lines[i].lower()
            for i in range(max(0, line_num - 4), line_num)  # this line + 3 above
        ):
            continue

        # The same sanctioned idiom split across two lines: a shared DEFAULT constant and the
        # getenv read that consumes it. See _is_env_default_constant for the narrow conditions.
        if _is_env_default_constant(line, lines, line_num):
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
