#!/usr/bin/env python3
"""Check for hardcoded secrets and credentials."""
# AFTER-EDIT: tests/test_enforcement.py | none

from __future__ import annotations

import re
from pathlib import Path

try:
    from .validate_conventions import CheckResult, Severity
except ImportError:  # standalone run (final_gate executes `python <path>`)
    from validate_conventions import CheckResult, Severity  # type: ignore[no-redef]

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
    (r"postgresql://[^:]+:(?!\$\{|\$\(|\$[A-Za-z_]|<)[^@\s]+@", "DB URL with password"),
    (r"mongodb(\+srv)?://[^:]+:(?!\$\{|\$\(|\$[A-Za-z_]|<)[^@\s]+@", "MongoDB URL with password"),
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
        # (?!\$[({A-Za-z_]) — a value that is a shell substitution "$(...)", expansion
        # "${...}", or bare variable reference "$RESTIC_PW" is by construction NOT a
        # hardcoded secret. The DSN patterns above already accept the bare-$VAR form
        # (\$[A-Za-z_]); this member lacked it — live false-positive 2026-08-07:
        # RESTIC_PASSWORD="$RESTIC_PW" in a sibling's sysadmin script tripped the gate.
        # (Also routed upstream earlier from a tryton-crm gauntlet: G3_PW via $(python3 …).)
        r"(?:password|secret|api_key|token)\s*[:=]\s*['\"](?!\$[({A-Za-z_])[^'\"\n]{8,}['\"]",
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

# Documentation placeholders that REFERENCE (not hardcode) a credential — README/example values
# like `API_KEY="your-key-here"`, `<your-token>`, `{{VAR}}`, `changeme`. Anchored to the WHOLE
# captured value, so a real secret that merely CONTAINS one of these words is still flagged.
_PLACEHOLDER_VALUES = re.compile(
    r"^(?:"
    r"<[^>]*>"  # <your-token>, <password>
    r"|\{\{?[^}]*\}?\}"  # {{VAR}} / {value}
    r"|x{4,}|\.{3,}|-{3,}|\*{3,}|_{3,}"  # xxxx / ... / --- / *** / ___
    r"|your[-_][a-z0-9-]*"  # your-key-here, your_api_key
    r"|[a-z0-9]*[-_]?(?:key|token|secret|password|pw)[-_]?here"  # key-here, api-key-here
    r"|(?:change[-_]?me|replace[-_]?me|placeholder|redacted|dummy|example|sample|todo|tbd|none|null)"
    r")$",
    re.I,
)

# DSN credential segments that are obvious connection-string EXAMPLES, not real
# passwords — `postgresql://user:pass@host:port/db`, `mongodb://user:password@…`.
# A backtick-wrapped example DSN in a reference doc is the #1 secrets false positive;
# the quote-anchored _PLACEHOLDER_VALUES check above never sees it (backticks ≠ quotes).
# A real hardcoded password (`admin:Xk9d2@`) does NOT match — only literal placeholders do.
# Deliberately NARROWER than _PLACEHOLDER_VALUES: `example`/`sample`/`dummy`/`todo`/
# `tbd` are real shipped weak credentials (`POSTGRES_PASSWORD: example` is the
# canonical upstream compose default) — exempting them in a CREDENTIAL position
# would hide genuinely deployed secrets. Only tokens that virtually never appear
# as real deployed passwords qualify here.
_DSN_PLACEHOLDER_PW = re.compile(
    r"^(?:pass|passwd|password|pwd|pw|secret|your[-_]?password"
    r"|change[-_]?me|replace[-_]?me|placeholder|redacted)$",
    re.I,
)

# Pattern descriptions the DSN-credential exemption may apply to. Applying it to
# every SECRET_PATTERNS match lets a placeholder DSN embedded in a longer literal
# suppress a REAL secret elsewhere in the same match.
_DSN_PATTERN_DESCS = frozenset({"DB URL with password", "MongoDB URL with password"})


def check_file(file_path: Path, allowed_lines: set[int] | None = None) -> list[CheckResult]:
    """Check a file for hardcoded secrets.

    ``allowed_lines`` — when given, only findings on those (new-side) line numbers
    are reported; findings on unchanged lines are dropped. This bounds the gate to
    what the current diff actually TOUCHED, so a sibling's unrelated edit elsewhere
    in a shared file doesn't retroactively re-flag a pre-existing (already-committed)
    line — the exact false positive the whole-file scan produced on shared master.
    ``None`` (the default) scans the whole file, preserving standalone/test callers
    and the untracked-file case (every line is new).
    """
    results: list[CheckResult] = []
    if any(re.search(p, str(file_path), re.I) for p in SKIP_PATTERNS):
        return results
    if file_path.suffix.lower() in (".jpg", ".png", ".gif", ".pdf", ".zip"):
        return results

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return results

    # Template-generator modules (e.g. scaffold.py) EMIT project config into scaffolded
    # projects — their string literals are output templates (localhost dev URLs,
    # <user>:<pass> example creds), not runtime secrets. Such a file opts out with a
    # top-level `# noqa-file: template-generator` marker. Scoped to THIS content check;
    # all other gate checks still run on the file. Runtime secrets belong in .env.
    if "noqa-file: template-generator" in content:
        return results

    lines = content.splitlines()
    for pattern, desc in SECRET_PATTERNS:
        for match in re.finditer(pattern, content, re.I):
            line_num = content[: match.start()].count("\n") + 1
            # Only gate lines the current diff actually touched (when scoped).
            if allowed_lines is not None and line_num not in allowed_lines:
                continue
            # Skip lines with noqa comments
            if line_num <= len(lines) and "noqa" in lines[line_num - 1]:
                continue
            secret = match.group()
            # Skip obvious doc placeholders (your-key-here, <token>, {{VAR}}, changeme…) — the
            # quoted value REFERENCES a credential in an example, it doesn't hardcode one.
            value = re.search(r"['\"]([^'\"\n]+)['\"]", secret)
            if value and _PLACEHOLDER_VALUES.match(value.group(1).strip()):
                continue
            # DSN example with a placeholder credential (`://user:pass@`) — a doc
            # connection-string template, not a hardcoded secret. Scoped to the DSN
            # patterns ONLY (never suppresses another pattern's whole match), and the
            # credential is captured GREEDILY to the last `@` before the host so a
            # real password containing `@` after a placeholder prefix
            # (`tbd@ReallySecret@host`) is judged in full, not truncated.
            if desc in _DSN_PATTERN_DESCS:
                # The pattern match ends at the first `@`; extract from the full LINE
                # so the credential runs greedily to the last `@` before the host.
                line_text = lines[line_num - 1] if line_num <= len(lines) else secret
                dsn_pw = re.search(r"://[^:@\s]+:(.+)@[^@\s/]+", line_text)
                if dsn_pw and _DSN_PLACEHOLDER_PW.match(dsn_pw.group(1).strip()):
                    continue
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


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _changed_line_numbers(rel: str) -> set[int] | None:
    """Working-tree line numbers ``rel`` changed vs HEAD (both staged + unstaged).

    A single ``git diff HEAD --unified=0`` — its new-side numbers are the
    working-tree line numbers ``check_file`` reads off disk, so staged and unstaged
    edits share one coordinate space (a two-diff union would mix index-space and
    working-tree-space numbers and mis-map lines on a staged+unstaged file).
    Returns ``None`` for an untracked file (no diff base — every line is new, scan
    the whole file); ``None`` is also the fail-open fallback when git is
    unavailable or HEAD doesn't exist, so the check never silently gates nothing.
    """
    import subprocess

    try:
        tracked = (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel],
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )
    except FileNotFoundError:
        return None
    if not tracked:
        return None  # untracked → all lines are new

    try:
        out = subprocess.run(
            ["git", "diff", "HEAD", "--unified=0", "--", rel],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None  # no HEAD / git unavailable → fail-open, scan whole file

    changed: set[int] = set()
    for line in out.splitlines():
        m = _HUNK_RE.match(line)
        if not m:
            continue
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        changed.update(range(start, start + count))  # count 0 → empty (deletion)
    return changed


def main() -> int:
    """Scan CHANGED files for hardcoded secrets; exit 1 on any ERROR-severity
    finding so final_gate's "Secrets (Zero Hardcoding)" gate actually bites.

    This file previously had no entry point — running it did nothing and the gate
    was a permanent no-op. Runs standalone (how final_gate invokes it); the
    Severity import falls back to absolute when there is no package context.
    """
    errors = [
        r
        for rel in _changed_files()
        if (p := Path(rel)).is_file()
        for r in check_file(p, _changed_line_numbers(rel))
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
