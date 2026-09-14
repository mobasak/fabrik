#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_script_headers.py
"""Enforce the `# AFTER-EDIT:` coupling header on staged scripts.

Every script self-declares which files must be updated when *it* changes, via a header
line in its first lines:

    # AFTER-EDIT: scripts/fabrik_synced_manifest.py, .gitignore     (or `none`)

This gate mirrors check_doc_sync (touch-on-change, WARN-tier — never blocks):
- WARN if a staged `scripts/**/*.py` has no `# AFTER-EDIT:` header.
- WARN if the header names a coupled file that was NOT also staged in this change.

Touch-on-change by design: a script gains its header the next time it is edited, so there is no
mass backfill. WARN-only (always exit 0); promote to an ERROR gate once the active scripts are
headered.

SCOPE (T12.14, 01M1SNNTS): the index when anything is staged, ELSE the working-tree diff. The
completion workflow runs `final_gate.py --check` BEFORE `git add` — the gate is what tells you the
change is ready to commit — so a staged-ONLY check had nothing to inspect in the one moment it
matters, and a vendored twin diverged for a commit because of it (e8f0473d). Every line of output
names the scope it used, because on a shared tree the working-tree diff carries other sessions'
unstaged edits; reading them is safe where writing them would not be, and this check never writes.

⚠️ WHAT THIS CHECK DELIBERATELY DOES NOT DO, measured rather than assumed. wef2 reported
(01M1V2P02) that the coupling is DIRECTIONAL and points the wrong way for how these files change —
a checker script is stable while the DATA it measures churns, so editing `registry.json` without
its doc satisfies every check while breaking the declared coupling. The proposed remedy was to
symmetrise: inspect the header whenever ANY file it names is staged. Measured over 1,037 commits
since 2026-09-01 before building it:

    all named files .................. fires on 591 commits (57 %)
    minus the Doc-Sync sinks ......... fires on 383 commits (37 %)
    minus sinks and every docs/ path . fires on 276 commits (27 %)

The top trigger is `CHANGELOG.md` (400 of the 591) — named by exactly one header, touched by
almost every commit. At 27 % a WARN line is noise that teaches readers to skip the block, which is
how enforcement dies (FIX DIRECTIVE 5). So the symmetrisation is REJECTED on measurement, and the
real answer — a header opting IN to a symmetric coupling per file, where the author knows it is
true — is filed as spec-sized work rather than half-built here.
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

HEADER_RE = re.compile(
    r"#\s*AFTER-EDIT:[ \t]*(.*)$", re.IGNORECASE
)  # an EMPTY declaration matches too: `# AFTER-EDIT:` with trailing whitespace read as `none`, without it as "no header" (FC7)


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
    """The first HEADER_SCAN_LINES of the STAGED blob — what will be committed — never the
    working tree, which a later edit or a partial stage can make differ from the index in either
    direction (EQ2). Read through `git cat-file --batch` with the path on STDIN as UTF-8 bytes:
    a non-ASCII path could not even be encoded as an argv under an ASCII locale (EZ6), and the
    batch protocol says `missing` for a path without a stage-0 blob instead of an English fatal
    message the caller had to pattern-match (EY1). None when the index holds no stage-0 blob."""
    try:
        proc = subprocess.run(
            [
                "git",
                "cat-file",
                "--batch",
                "-z",
            ],  # NUL-delimited input: a newline in a path split the request into two `missing` answers (FB2)
            input=(":" + path + "\0").encode("utf-8", "surrogateescape"),
            capture_output=True,
            timeout=20,
            env={**os.environ, "LANGUAGE": "C"},
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise GitUnavailableError(f"git cat-file :{path}: {exc.__class__.__name__}") from exc
    if proc.returncode != 0:
        # a git that FAILED (a corrupt index mid-loop) is not a deletion — the old branch called it one (EY1)
        raise GitUnavailableError(
            f"git cat-file :{path}: exit {proc.returncode}: {proc.stderr.decode('utf-8', 'replace').strip()[:160]}"
        )
    header, _, rest = proc.stdout.partition(b"\n")
    if header.endswith((b" missing", b" ambiguous")):
        return None
    parts = header.split()
    if len(parts) != 3 or parts[1] != b"blob":
        raise GitUnavailableError(f"git cat-file :{path}: unexpected answer {header[:80]!r}")
    body = rest[: int(parts[2])].decode("utf-8", "replace")
    return "\n".join(
        re.split(r"\r\n|\r|\n", body)[:HEADER_SCAN_LINES]
    )  # universal newlines ONLY — `str.splitlines` also breaks on \x0c/\u2028, which the tokenizer does not, so a form feed in a docstring shrank the window (FC7)


# Both separators the corpus actually uses: `a.py, b.md` AND `a.py | b.md`. The pipe form is the
# majority style in scripts/sysadmin/ and was parsed as FILENAMES — every pipe became a coupled
# file named "|" that was obviously never staged, so those scripts warned on every edit. Invisible
# until 2026-08-16, because the check was registered without `advisory`/`warn_only` and
# `run_optional_check` discarded its stdout on exit 0.
SEPARATORS = re.compile(r"[,|\s]+")
NONE_VALUES = {"none", "n/a", "na", "-"}


def _stat(p: Path, kind: str) -> bool:
    """`is_file`/`is_dir`/`exists` that never raise: pathlib swallows ENOENT/ENOTDIR/EBADF/ELOOP only,
    so a >255-byte token (ENAMETOOLONG) or a token under a mode-000 directory (EACCES) was a traceback
    out of a WARN-only check — a red gate for a header typo, fleet-wide (FC7)."""
    try:
        return bool(getattr(p, kind)())
    except (OSError, ValueError):
        return False


def _coupled_tokens(listed: str, script: Path) -> list[str]:
    """The tokens of an `# AFTER-EDIT:` list that name a FILE. A sentinel (`none`, `n/a`), a `·`
    or a prose word (`(§ fix-first)`) never does (DU2/DW2); a token names a file when it has a
    path shape (a `/` or a `.`) OR exists on disk — repo-rooted or relative to the script's own
    directory — so `Makefile` counts and `(§ fix-first)` does not (DY2)."""
    out: list[str] = []
    for raw in SEPARATORS.split(listed):
        # trailing full stops are a SENTENCE's, never a file's: `none.`, `callers.` (the last word of
        # trailing prose was minted a phantom file by its period), `docs/coupled.md.` (a real path
        # made unsatisfiable by its period), `...` — every token is stripped, then tested (EY2/EZ6/FB2)
        c = raw.rstrip(".")
        if not c or c.lower() in NONE_VALUES:
            continue
        if (
            "/" in c or "." in c or _stat(Path(c), "is_file") or _stat(script.parent / c, "is_file")
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
    if not token.endswith("/") and _stat(Path(token), "is_dir"):
        token += "/"  # a directory named without its slash could never be satisfied (EZ6)
    cands = [token]
    if not _stat(Path(token), "exists"):
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
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            timeout=20,
            env={**os.environ, "LANGUAGE": "C"},  # git's fatal messages in English (EZ6)
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise GitUnavailableError(f"git {' '.join(args)}: {exc.__class__.__name__}") from exc
    if proc.returncode != 0:
        # a git that ANSWERS with a failure (a corrupt index, no work tree, a cwd inside `.git/`)
        # read as "nothing staged" — a convincing green for a check that could not ask (EY1)
        raise GitUnavailableError(
            f"git {' '.join(args)}: exit {proc.returncode}: {proc.stderr.decode('utf-8', 'replace').strip()[:160]}"
        )
    # LOSSLESS decoding: `errors="replace"` turned a non-UTF-8 byte into U+FFFD, which re-encoded
    # to DIFFERENT bytes for `cat-file`, so every such path was a false "staged deletion" (FB2);
    # a surrogate prints as `?` because the streams are reconfigured to replace (EZ6)
    out = proc.stdout.decode("utf-8", "surrogateescape")
    return [x for x in out.strip(sep).split(sep) if x] if out.strip(sep) else []


def _index_entries(paths: list[str]) -> dict[str, tuple[str, str]]:
    """`git ls-files -s -z` for the staged scripts: path → (mode, stage). The INDEX is what a
    commit takes; the working tree lied three ways — a file deleted after `git add` read as "a
    deletion" (its staged blob committed unchecked), a sparse-checkout path never on disk the
    same, and a script rewritten as a symlink after `git add` skipped as a symlink (EZ6)."""
    out: dict[str, tuple[str, str]] = {}
    wanted = set(paths)
    # the whole index, filtered here: a non-ASCII PATHSPEC could not even be encoded for git
    # under an ASCII locale (UnicodeEncodeError before git ran) (EZ6)
    for rec in _git(["ls-files", "-s", "-z"], sep="\0"):
        meta, _, path = rec.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and path in wanted:
            out.setdefault(
                path, (parts[0], parts[2])
            )  # stage 0 first; a conflict's stages 1–3 land only when 0 is absent
    return out


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
    for stream in (
        sys.stdout,
        sys.stderr,
    ):  # a non-ASCII path in a WARN line under an ASCII locale was a UnicodeEncodeError (EZ6)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
    scope = "staged"
    if not staged:
        # T12.14 (01M1SNNTS): the completion workflow runs `final_gate.py --check` BEFORE
        # `git add`, because the gate is what tells you the change is ready to commit. At that
        # moment the index is empty and the one check designed to catch a coupled-file omission
        # had nothing to inspect. It cost a real divergence: `scripts/sysadmin/claude_rotate.py`
        # was committed without the vendored twin its own header names, and for one commit the
        # fleet carried two copies broadcasting different resume instants (e8f0473d).
        #
        # So the pre-stage run falls back to the WORKING TREE diff. Reading it is safe where
        # writing it would not be — this check never mutates and never stages; the scope is named
        # in every line of output so a warning about a file you did not touch is legible as a
        # sibling's rather than a mystery.
        staged = _git(["diff", "--name-only", "-z"], sep="\0")
        scope = "working-tree (pre-stage)"
    if not staged:
        # "Nothing staged" is a REASON, not a silent pass. This early return is the shape the
        # bare run in 01M1E6S1EAK7DNP74C1K9YHP3Z actually hit (the reporter's scripts were
        # modified-UNSTAGED, and this check is staged-scoped by design).
        if not quiet:
            # The same `N of M staged script(s) inspected` shape as the clean path (without its third
            # count — nothing is staged), so a reader (and a test) matches one phrasing for one fact.
            print(
                "OK — nothing staged or modified; this check reads the index, "
                "falling back to the working tree (0 of 0 script(s) inspected)."
            )
        return 0
    staged_set = set(staged)
    scripts = [f for f in staged if f.startswith("scripts/") and f.endswith(".py") and not _skip(f)]
    # path → (mode, stage): what will be COMMITTED, never the working tree (EZ6). In the
    # pre-stage fallback there IS no index entry for these paths, so the index probe is skipped
    # and the working-tree file is read directly — the same files, one commit earlier.
    index = _index_entries(scripts) if scope == "staged" else {}

    warnings: list[str] = []
    inspected = 0
    for f in scripts:
        entry = index.get(f)
        p = Path(f)
        if scope != "staged":
            # Pre-stage fallback: there is no index entry for these paths BY CONSTRUCTION, so the
            # index probes below would report every file as a staged deletion. A file the diff
            # lists but disk no longer has is a deletion here too.
            if not p.exists():
                continue
        elif entry is None:
            # listed by the diff but no index entry: a `git rm` (silent — nothing is committed
            # there) or a `git rm --cached` with the file still on disk (said, so the operator
            # sees the tracking leave) (EW1/EZ6)
            if p.exists():
                warnings.append(f"{f}: staged deletion or unresolved merge — not checked")
            continue
        elif entry[1] != "0":
            warnings.append(f"{f}: staged deletion or unresolved merge — not checked")
            continue
        mode = entry[0] if entry else ("120000" if p.is_symlink() else "100644")
        if mode == "120000":
            # the staged blob of a symlink is its LINK TEXT, never a script (EY1); the index says
            # symlink even when the working tree was rewritten since `git add` (EZ6)
            warnings.append(
                f"{f}: dangling symlink — not checked"
                if not Path(f).exists()
                else f"{f}: symlink — not checked (the target is inspected on its own)"
            )
            continue
        if mode == "160000":
            warnings.append(f"{f}: a submodule gitlink — not checked")
            continue
        try:
            head = _staged_head(f)
        except GitUnavailableError as exc:
            # ONE path git could not answer for must not discard every other script's finding (EZ6)
            warnings.append(f"{f}: git did not answer ({exc}) — not checked")
            continue
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
        if not listed.strip():
            warnings.append(
                f"{f}: empty `# AFTER-EDIT:` — name the coupled files, or `none`."
            )  # FC7
            continue
        if listed.lower() in NONE_VALUES:
            continue
        coupled = _coupled_tokens(listed, p)
        missing = [c for c in coupled if not _satisfied(c, p, staged_set)]
        if missing:
            warnings.append(
                f"{f}: `# AFTER-EDIT:` lists coupled file(s) not updated in this change: "
                f"{', '.join(missing)}."
            )

    if warnings and scope != "staged":
        # A warning about a file you did not touch must be legible as a sibling's rather than a
        # mystery: on a shared tree the working-tree diff carries their unstaged edits too.
        print(
            f"NOTE: nothing is staged, so these were read from the {scope} diff — on a shared "
            "tree some of these files may be another session's uncommitted work."
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
            f"OK — {inspected} of {len(scripts)} {scope} script(s) inspected "
            f"({len(staged)} {scope} file(s))."
        )
    return 0  # WARN-only — never blocks the gate


if __name__ == "__main__":
    sys.exit(main())
