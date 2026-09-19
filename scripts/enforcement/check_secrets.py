#!/usr/bin/env python3
"""Check for hardcoded secrets and credentials."""
# AFTER-EDIT: tests/test_enforcement.py, tests/test_check_secrets_placeholders.py | none

from __future__ import annotations

import re
import sys
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
    # Vendor tokens this box actually issues, added 2026-08-30 after a LIVE MISS: a
    # literal Grafana service-account token reached a COMMIT in mcp_defs.json and was
    # stopped only by GitHub's push protection — this scanner had no Grafana pattern,
    # so the whole incident (history rewrite + a 4.5-month-old token rotated) traces
    # to a gap here. Each prefix below was confirmed PRESENT in this box's own config
    # before being added (fire rate measured, not guessed); each shape is specific
    # enough that a placeholder or prose mention cannot match.
    (r"glsa_[A-Za-z0-9_]{32,}", "Grafana Service Account Token"),
    (r"sk-or-v1-[0-9a-f]{48,}", "OpenRouter API Key"),
    (r"fc-[0-9a-f]{32}", "Firecrawl API Key"),
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
        # The opening quote is captured and the close must MATCH it — accepting either type at
        # either end read `'^X_PASSWORD=' … "` (a grep pattern then a later double quote) as one
        # quoted credential (youtube 01M1GNV1, 2026-08-31).
        r"(?:password|secret|api_key|token)\s*[:=]\s*(['\"])(?!\$[({A-Za-z_])[^'\"\n]{8,}\1",
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
                # Bounded to 1000 chars: real placeholder DSN lines are short, and the
                # greedy `(.+)@` backtracks quadratically on hostile many-@ lines.
                line_text = lines[line_num - 1] if line_num <= len(lines) else secret
                line_text = line_text[:1000]
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


def _inside_work_tree() -> bool:
    """Is there a repo here at all? Separates "git is unusable" (loud) from "this is not a git
    directory", which is the documented fail-open and must stay silent — otherwise a standalone
    or non-repo invocation reds for a condition that is not a finding."""
    # ⚠️ FILESYSTEM, not git. Every cause the loud path exists for — a noexec mount, a broken
    # PATH shim, ENOMEM on fork — breaks `git` itself, so probing WITH git returns False exactly
    # when the guard must fire: executed, a noexec shim gave rc 0 and silence with a real secret
    # sitting in the tree. A `.git` entry (dir, or the file a linked worktree carries) is the
    # question actually being asked.
    try:
        cwd = Path.cwd()
    except OSError:
        return False
    return any((d / ".git").exists() for d in (cwd, *cwd.parents))


class _GitUnusableError(RuntimeError):
    """Every git probe failed while a repo is plainly present — the scan saw nothing because it
    could not look, which on a secrets gate must fail LOUD rather than pass silently."""


def _is_file(p: Path) -> bool:
    """`Path.is_file()` swallows only ENOENT/ENOTDIR/EBADF/ELOOP — an OVERLONG path raises
    `OSError(ENAMETOOLONG)` straight out of `main()`. The filesystem cannot produce such a path
    (`git add` refuses first) but `git update-index --add --cacheinfo` accepts one at rc 0 and
    `git diff --staged --name-only` then emits it — and that plumbing call is the private-index
    commit recipe `CLAUDE.md` mandates for shared-append files. A path we cannot even stat is
    not a file this scan can read, so it is skipped rather than fatal."""
    try:
        return p.is_file()
    except OSError:
        return False


def _changed_files() -> list[str]:
    """Files changed in git (unstaged + staged + untracked) — bound the scan to
    the diff, NOT the whole repo (mirrors validate_conventions.get_git_diff_files
    so existing violations don't retroactively red every project; only new
    changes are gated)."""
    import subprocess

    files: set[str] = set()
    probed = False
    for cmd in (
        # ⚠️ `-z` and `errors="surrogateescape"`, both load-bearing. On git's DEFAULT config a
        # path holding a non-ASCII byte, a `"` or a `\` comes back QUOTED and octal-escaped —
        # `café.txt` arrives as the literal `"caf\303\251.txt"`, whose `Path(...).is_file()` is
        # False, so the file was skipped and a hardcoded secret in it went UNREPORTED in every
        # repo, silently, with no unusual configuration (executed). `-z` disables that quoting;
        # surrogateescape then round-trips a path that is not valid UTF-8, which under
        # `core.quotePath=false` otherwise raised `UnicodeDecodeError` right here — the same
        # crash this module just fixed 40 lines below, on paths instead of content.
        ["git", "diff", "--name-only", "-z"],
        ["git", "diff", "--staged", "--name-only", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ):
        try:
            # ⚠️ Decode the BYTES; do not pass `text=True`. Text mode wraps the pipe with
            # universal-newline translation, which rewrites a `\r` in a path to `\n` AFTER `-z`
            # removed git's quoting — two distinct tracked files then decode to the SAME string
            # and one silently vanishes from the scan (executed). `errors=` alone still forces
            # text mode, so only a manual decode avoids it.
            raw = subprocess.run(
                cmd, capture_output=True, check=True, stdin=subprocess.DEVNULL, timeout=60
            ).stdout
            files.update(raw.decode("utf-8", "surrogateescape").split("\0"))
            probed = True
        except (subprocess.SubprocessError, OSError):
            pass
    if not probed and _inside_work_tree():
        # ⚠️ NOT the same as "nothing changed". Widening the arms above to catch an UNUSABLE git
        # (a noexec mount, a broken PATH shim, ENOMEM on fork) stopped the crash — but on a
        # SECURITY gate "I could not look" must never read as "I looked and found nothing", and
        # `final_gate`'s `run_optional_check` discards stdout on rc 0, so a printed warning could
        # not surface. `main()` turns this into a loud failure instead.
        raise _GitUnusableError
    return [f for f in files if f]


# ⚠️ Digit runs are BOUNDED. `int()` raises ValueError above 4300 digits (Python 3.12), and a
# manufactured header (see the clamp) can carry an arbitrarily long run — an unbounded `\d+`
# here crashed `main()` before the clamp below could ever apply. A longer run now simply
# fails to match, which fails CLOSED.
_HUNK_RE = re.compile(r"^@@ -\d{1,9}(?:,\d{1,9})? \+(\d{1,9})(?:,(\d{1,9}))? @@")
# A hunk cannot legitimately name more lines than a file plausibly has; see the clamp's comment
# in `_changed_line_numbers` for why an unbounded count is reachable from CONTENT, not just a
# real header.
_MAX_HUNK_LINES = 1_000_000


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
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=60,
            ).returncode
            == 0
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if not tracked:
        return None  # untracked → all lines are new

    try:
        out = subprocess.run(
            ["git", "diff", "HEAD", "--unified=0", "--", rel],
            capture_output=True,
            text=True,
            # ⚠️ `errors="replace"`, not strict: git's own heuristic calls a file TEXT when its
            # first 8000 bytes hold no NUL, so an uncompressed PDF, an .ico, a font or latin-1
            # prose DIFFS as text and strict UTF-8 raised `UnicodeDecodeError` out of
            # `subprocess._translate_newlines` — which is neither of the two fail-open arms
            # below, so the whole secrets leg crashed for every agent in the repo over a file
            # class `check_file` never scans (web-ecommerce-factory, 01M2X0ZQX8YMZX022R9TC1E3M6).
            # Replacement is safe for what this reads: `_HUNK_RE` matches only the ASCII
            # `@@ -a,b +c,d @@` headers, and a replacement char cannot appear inside one — but
            # note it does NOT follow that only real headers reach the regex: `splitlines()`
            # can manufacture one out of a content line (see the clamp below).
            # Returning None instead would fail open to a WHOLE-FILE scan and throw away the
            # changed-line scoping that exists to stop re-flagging already-committed lines.
            errors="replace",
            check=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None  # no HEAD / git unavailable → fail-open, scan whole file

    changed: set[int] = set()
    saw_header = False
    for line in out.splitlines():
        m = _HUNK_RE.match(line)
        if not m:
            continue
        saw_header = True
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        # ⚠️ An implausible scope — one header's, or the accumulated set's — is not a scope this
        # can trust, so it FAILS OPEN to the whole-file scan like the no-header case below.
        # `str.splitlines()` also splits on `\r`, `\x0b`, `\x0c`, `\x1c-\x1e`, `\x85`, U+2028 and
        # U+2029, so a CHANGED CONTENT LINE can present its tail to this regex as a hunk header,
        # and one line can manufacture MANY: 300 of them reached MemoryError under a 2 GB cap,
        # measured at ~1.85 MB of child RSS per byte of crafted content (executed).
        # ⚠️ And do NOT truncate instead. `min(count, …)` was the first cut of this guard and it
        # SILENTLY DROPPED every finding past the cut — a real credential at line 1,000,003 of a
        # staged 1,000,005-line file was reported by the previous release and not by that cut
        # (executed, both directions). On a secrets gate a narrowed scope is a missed secret.
        if count > _MAX_HUNK_LINES or len(changed) + count > _MAX_HUNK_LINES:
            return None
        changed.update(range(start, start + count))  # count 0 → empty (deletion)
    if out and not saw_header:
        # Git emits NO `@@` header for a file it treats as binary — a `.gitattributes` `-diff`
        # rule, or one NUL byte. Returning the empty set here meant ALLOW NOTHING downstream
        # (`:148`), which SILENCED every finding in that file while the gate reported success:
        # one `*.cfg -diff` line disabled the secrets gate for an extension (executed). `None`
        # is this function's documented fail-open — scan the whole file, which `check_file`
        # still bounds by its own `read_text` guard. An empty set may only mean "nothing changed".
        # ⚠️ THE COST, stated because it is real: a PRE-EXISTING secret elsewhere in a
        # binary-diffed file is now reported when any line of it changes — the re-flag false
        # positive the scoping exists to prevent, re-opened for this file class only. Measured:
        # no slowdown (the scope was applied inside the match loop either way, 0.281s vs 0.294s
        # on 3.29 MB). Loud beats silent on a secrets gate, but `# noqa` is the only escape and
        # it is awkward on a machine-generated lock file.
        return None
    return changed


def main() -> int:
    """Scan CHANGED files for hardcoded secrets; exit 1 on any ERROR-severity
    finding so final_gate's "Secrets (Zero Hardcoding)" gate actually bites.

    This file previously had no entry point — running it did nothing and the gate
    was a permanent no-op. Runs standalone (how final_gate invokes it); the
    Severity import falls back to absolute when there is no package context.
    """
    # ⚠️ `_changed_files` round-trips an undecodable path as surrogates, and `sys.stdout` is a
    # STRICT utf-8 wrapper — printing one raised `UnicodeEncodeError`, and because stdout is
    # block-buffered to a pipe the process died before flushing, so EVERY finding was lost, not
    # just the offending line. The fix that let the path into the scan is what made this
    # reachable on the way out (executed).
    # `hasattr`: stdout is None under `1>&-` and a StringIO under `redirect_stdout`, and an
    # unguarded call turned a CLEAN repo into a traceback where the previous release returned 0.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    try:
        changed = _changed_files()
    except _GitUnusableError:
        print("❌ check_secrets could not run git — the scan saw NOTHING; not a clean result.")
        return 1
    errors = [
        r
        for rel in changed
        if _is_file(p := Path(rel))
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
