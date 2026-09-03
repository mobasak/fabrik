#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_script_headers.py
"""Enforce the `# AFTER-EDIT:` coupling header on staged scripts.

Every script self-declares which files must be updated when *it* changes, via a header
line in its first lines:

    # AFTER-EDIT: scripts/fabrik_synced_manifest.py, .gitignore     (or `none`)

This gate mirrors check_doc_sync (touch-on-change, WARN-tier — never blocks):
- WARN if a staged `scripts/**/*.py` has no `# AFTER-EDIT:` header.
- WARN if the header names a coupled file that was NOT also staged in this change.

Touch-on-change by design: only *staged* scripts are inspected, so there is no mass
backfill — a script gains its header the next time it is edited. WARN-only (always
exit 0); promote to an ERROR gate once the active scripts are headered.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import tokenize
from fnmatch import fnmatch
from pathlib import Path

HEADER_RE = re.compile(r"#\s*AFTER-EDIT:\s*(.+)", re.IGNORECASE)


def _header_of(head: str) -> str | None:
    """The `# AFTER-EDIT:` declaration among the head's COMMENT tokens — never a line inside a
    docstring or a string (this check's own docstring quotes the convention; a script with only
    such an example has NO header, and one that names a file there declared nothing) (EQ2)."""
    try:
        for tok in tokenize.generate_tokens(io.StringIO(head).readline):
            if tok.type == tokenize.COMMENT:
                m = HEADER_RE.match(tok.string)
                if m:
                    return m.group(1).strip()
    except (
        tokenize.TokenError,
        SyntaxError,
    ):  # the head is cut at HEADER_SCAN_LINES — a truncated block ends the stream after every comment before it was seen
        pass
    return None


def _staged_head(path: str) -> str | None:
    """The first HEADER_SCAN_LINES of the STAGED blob (`git show :path`) — what will be
    committed — never the working tree, which a later edit or a partial stage can make differ
    from the index in either direction (EQ2). None when the index has no blob (an intent-to-add
    path): the caller reads the working tree then."""
    proc = subprocess.run(
        ["git", "show", f":{path}"], capture_output=True, text=True, timeout=20, errors="replace"
    )
    if proc.returncode != 0:
        return None
    return "\n".join(proc.stdout.splitlines()[:HEADER_SCAN_LINES])


# Both separators the corpus actually uses: `a.py, b.md` AND `a.py | b.md`. The pipe form is the
# majority style in scripts/sysadmin/ and was parsed as FILENAMES — every pipe became a coupled
# file named "|" that was obviously never staged, so those scripts warned on every edit. Invisible
# until 2026-08-16, because the check was registered without `advisory`/`warn_only` and
# `run_optional_check` discarded its stdout on exit 0.
SEPARATORS = re.compile(r"[,|\s]+")
NONE_VALUES = {"none", "n/a", "na", "-", ""}


def _coupled_tokens(listed: str, script: Path) -> list[str]:
    """The tokens of an `# AFTER-EDIT:` list that name a FILE. A sentinel (`none`, `n/a`), a `·`
    or a prose word (`(§ fix-first)`) never does (DU2/DW2); a token names a file when it has a
    path shape (a `/` or a `.`) OR exists on disk — repo-rooted or relative to the script's own
    directory — so `Makefile` counts and `(§ fix-first)` does not (DY2)."""
    out: list[str] = []
    for c in SEPARATORS.split(listed):
        if not c or c.lower() in NONE_VALUES:
            continue
        if (
            "/" in c or "." in c or Path(c).is_file() or (script.parent / c).is_file()
        ):  # a FILE: a prose word that happens to name a directory (`docs`, `src`) is not promoted (EA2)
            out.append(c)
    return out


def _satisfied(token: str, script: Path, staged_set: set[str]) -> bool:
    """A coupled token is satisfied by a staged path that equals it repo-rooted OR relative to
    the script's directory (`tests/test_x.py` beside `scripts/kilo-benchmarks/x.py`), by any
    staged path under a directory token (`docs/orchestrator/`), or by a glob (`docs/**`). Before
    this, 8 of 106 hub headers could never be closed by any staging action (DY2)."""
    # repo-rooted FIRST; the script-relative reading only when the repo-rooted path does not
    # exist on disk — a same-named file inside the script's directory (`scripts/README.md`) must
    # never close a coupling declared on the root one (EA2); a directory token keeps its `/`
    cands = [token]
    if not Path(token).exists():
        cands.append((script.parent / token).as_posix() + ("/" if token.endswith("/") else ""))
    others = staged_set - {
        script.as_posix()
    }  # a glob that matches the script ITSELF proves nothing (EA2)
    for cand in cands:
        if cand in staged_set:
            return True
        if any(ch in cand for ch in "*?[") and any(fnmatch(s, cand) for s in others):
            return True
        if cand.endswith("/") and any(s.startswith(cand) for s in others):
            return True
    return False


SKIP_PATTERNS = ("tests/", "test_", "_test.py", "__pycache__/", "/__init__.py")
HEADER_SCAN_LINES = 25


def _git(args: list[str]) -> list[str]:
    out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20).stdout.strip()
    return out.split("\n") if out else []


def _skip(f: str) -> bool:
    """Skip test files and package markers by PATH SEGMENT, never by substring: a real enforcement
    script named `check_test_proposal.py` carries `test_` inside its name and was invisible to
    this check for as long as it existed (EQ2)."""
    parts = Path(f).parts
    name = parts[-1]
    return (
        "tests" in parts[:-1]
        or "__pycache__" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "__init__.py"
    )


def main() -> int:
    # ⚠️ `--quiet` exists ONLY for the gate, and the gate passes it (final_gate.py). Read why
    # before removing it: the denominator lines below were first shipped unconditionally, and
    # that put a content-free row in EVERY green gate run across the fleet — in human mode under
    # the `[ADVISORY] Script Coupling Header` row, AND in `--json`, because this check is
    # registered `warn_only=True` and the `advisory` array (final_gate.py, built from
    # WARN_ONLY_CHECKS) applies NO ⚠ filter — only the `warnings` array does. The sibling
    # advisory rows stay silent when clean; this one must too. The corpus already paid for this
    # lesson once: tests/enforcement/test_plan_lock_release.py asserts `out == ""` because "a
    # foreign-only corpus is not worth two lines on every gate run there, forever".
    # A BARE run (an agent or human invoking this directly) passes no flag and stays informative,
    # which is the whole point of 01M1E6S1EAK7DNP74C1K9YHP3Z.
    quiet = "--quiet" in sys.argv[1:]
    staged = _git(["diff", "--cached", "--name-only"])
    if not staged:
        # "Nothing staged" is a REASON, not a silent pass. This early return is the shape the
        # bare run in 01M1E6S1EAK7DNP74C1K9YHP3Z actually hit (the reporter's scripts were
        # modified-UNSTAGED, and this check is staged-scoped by design).
        if not quiet:
            # The same `N of M staged script(s) inspected` shape as the clean path (without its third
            # count — nothing is staged), so a reader (and a test) matches one phrasing for one fact.
            print(
                "OK — nothing staged; this check is staged-scoped (0 of 0 staged script(s) inspected)."
            )
        return 0
    staged_set = set(staged)
    scripts = [f for f in staged if f.startswith("scripts/") and f.endswith(".py") and not _skip(f)]

    warnings: list[str] = []
    inspected = 0
    for f in scripts:
        p = Path(f)
        if (
            not p.exists()
        ):  # a staged deletion — nothing to check; a dangling symlink lands HERE too
            if p.is_symlink():
                warnings.append(f"{f}: dangling symlink — not checked")
            continue
        head = _staged_head(f)
        if head is None:  # no index blob (an intent-to-add path): the working tree
            try:
                head = "\n".join(
                    p.read_text(encoding="utf-8", errors="replace").splitlines()[:HEADER_SCAN_LINES]
                )
            except OSError as exc:  # a staged path that exists but cannot be read (a permission-denied file): a WARN naming it, never a traceback that FAILS a warn-only gate for the wrong cause (DW2)
                warnings.append(
                    f"{f}: cannot read the header ({exc.__class__.__name__}) — not checked"
                )
                continue
        inspected += 1
        listed_header = _header_of(head)
        if listed_header is None:
            warnings.append(
                f"{f}: no `# AFTER-EDIT:` header — declare the files to update when this "
                "script changes (or `# AFTER-EDIT: none`)."
            )
            continue
        listed = listed_header
        if listed.lower() in NONE_VALUES:
            continue
        coupled = _coupled_tokens(listed, p)
        missing = [c for c in coupled if not _satisfied(c, p, staged_set)]
        if missing:
            warnings.append(
                f"{f}: `# AFTER-EDIT:` lists coupled file(s) not updated in this change: "
                f"{', '.join(missing)}."
            )

    for w in warnings:
        print(f"WARNING: {w}")
    if not warnings and not quiet:
        # ⚠️ State the DENOMINATOR on the clean path. Until 2026-09-01 this check printed
        # NOTHING on every silent outcome — no staged files, no staged scripts, and all-clean
        # were three different states that looked identical, and identical to the check never
        # having run (web-ecommerce-factory, 01M1E6S1EAK7DNP74C1K9YHP3Z: "pass and no-op are
        # indistinguishable"). A "0 findings" verdict that cannot say how many subjects it
        # examined is indistinguishable from having looked at nothing — the same law the
        # governance contract applies to agents, applied to the checker itself.
        # The `not quiet` guard is what keeps this out of every green fleet gate — see the
        # note in main()'s head for the mechanism (it is NOT the ⚠ filter, which guards only
        # the `warnings` array; warn_only stdout ships unfiltered in `advisory`).
        # `inspected` counts what was READ — a staged deletion, a dangling symlink and an
        # unreadable file are skipped above, and "1 inspected" for 0 read was the same
        # collected-vs-attempted overstatement the corpus gate corrected (DY2)
        print(
            f"OK — {inspected} of {len(scripts)} staged script(s) inspected "
            f"({len(staged)} staged file(s))."
        )
    return 0  # WARN-only — never blocks the gate


if __name__ == "__main__":
    sys.exit(main())
