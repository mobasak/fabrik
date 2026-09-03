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
import os
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


class GitUnavailableError(Exception):
    """git did not answer (a 20 s timeout behind a sibling's `index.lock`, or no git at all): the
    check cannot ask its question — a WARN that says so and exit 0, never a traceback, which the
    gate reads as a FAILURE of a warn-only check (EW1)."""


def _staged_head(path: str) -> str | None:
    """The first HEADER_SCAN_LINES of the STAGED blob (`git show :path`) — what will be
    committed — never the working tree, which a later edit or a partial stage can make differ
    from the index in either direction (EQ2). None when the index holds no stage-0 blob for a
    listed path — a `git rm --cached` deletion with the file still on disk, or an unresolved
    merge: nothing at that path is about to be committed, so nothing is checked (EW1)."""
    try:
        proc = subprocess.run(
            ["git", "show", f":{path}"],
            capture_output=True,
            text=True,
            timeout=20,
            errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise GitUnavailableError(f"git show :{path}: {exc.__class__.__name__}") from exc
    if proc.returncode != 0:
        # ONLY "no stage-0 blob" is None; a git that FAILED (a corrupt index mid-loop) is not a
        # deletion — the old branch called it one (EY1)
        if re.search(r"not in the index|not at stage 0|does not exist", proc.stderr):
            return None
        raise GitUnavailableError(
            f"git show :{path}: exit {proc.returncode}: {proc.stderr.strip()[:160]}"
        )
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
        core = (
            c[:-1] if c.endswith(".") and c.count(".") == 1 else c
        )  # `none.` — a sentence's full stop, not a file (EY2)
        if not c or core.lower() in NONE_VALUES:
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
        if (
            cand in staged_set
        ):  # a script naming ITSELF is a self-reference (2 of 130 hub headers do) — kept (EY2)
            return True
        if any(ch in cand for ch in "*?[") and any(fnmatch(s, cand) for s in others):
            return True
        if cand.endswith("/") and any(s.startswith(cand) for s in others):
            return True
    return False


HEADER_SCAN_LINES = 25


def _git(args: list[str], sep: str = "\n") -> list[str]:
    """Path lists are read with `-z` (NUL-separated, NEVER quoted): git's default C-quotes any
    path with a non-ASCII byte (`"scripts/na\\303\\257ve.py"`), and `core.quotepath=false` still
    quotes a tab, a backslash or a `"` — a quoted name matches neither `startswith("scripts/")`
    nor the staged set, so a headerless script was invisible and a staged coupled file "not
    updated" (EU1/EW1). A git that does not answer is GitUnavailableError, never a traceback."""
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise GitUnavailableError(f"git {' '.join(args)}: {exc.__class__.__name__}") from exc
    if proc.returncode != 0:
        # a git that ANSWERS with a failure (a corrupt index, no work tree, a cwd inside `.git/`)
        # read as "nothing staged" — a convincing green for a check that could not ask (EY1)
        raise GitUnavailableError(
            f"git {' '.join(args)}: exit {proc.returncode}: {proc.stderr.strip()[:160]}"
        )
    out = proc.stdout
    return [x for x in out.strip(sep).split(sep) if x] if out.strip(sep) else []


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
    try:
        return _main(quiet)
    except GitUnavailableError as exc:
        print(f"WARNING: {exc} — git did not answer; script coupling headers not checked")
        return 0


def _main(quiet: bool) -> int:
    top = _git(["rev-parse", "--show-toplevel"])
    if top and top[0] and Path(top[0]).is_dir():
        # the staged paths are repo-root-relative whatever the cwd; a bare run from `scripts/`
        # read every real script as "a staged deletion" and printed a clean 0-of-N (EU1)
        os.chdir(top[0])
    staged = _git(["diff", "--cached", "--name-only", "-z"], sep="\0")
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
        if p.is_symlink():
            # the staged blob of a symlink is its LINK TEXT, never a script: a dangling one was
            # already skipped; a live one (`scripts/verify_prod_parity.py`, the hub's one) was
            # "inspected" against a path string and warned "no header" on every stage (EY1)
            warnings.append(
                f"{f}: dangling symlink — not checked"
                if not p.exists()
                else f"{f}: symlink — not checked (the target is inspected on its own)"
            )
            continue
        if not p.exists():  # a staged deletion — nothing to check
            continue
        head = _staged_head(f)
        if head is None:
            # no stage-0 blob for a listed path: a `git rm --cached` deletion with the file still
            # on disk, or an unresolved merge — the WORKING TREE is not what will be committed and
            # is never read (EQ2's own principle; the fallback read it and reported "inspected"
            # for content about to leave tracking, or one side of a conflict — EW1)
            warnings.append(f"{f}: staged deletion or unresolved merge — not checked")
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
