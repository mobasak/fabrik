#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_doc_index.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""INDEX.md ↔ docs/ tree drift gate (docs-truth convergence, 2026-07-20).

Two directions:

(a) every ``docs/``-prefixed markdown link target named in INDEX.md exists on disk
    (directories allowed);
(b) every tracked live doc under ``docs/`` appears in INDEX.md by full path or
    basename — excluding archives, the plan/epic/review/spec pipeline content,
    and the daily-regenerated selection set (``docs/reference/kilo/*_SELECTION.md``
    plus KILO_MODEL_CAPABILITIES.md / KILO_AGENT_SELECTION_GUIDE.md and
    ``docs/traycer/kilo_selected_agents.md`` — sourced from daily_refresh.sh's
    git-add block, verified 2026-07-20).

Exit 0 clean; exit 1 on drift (Tier-2 blocking).
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import re
import stat as stat_module
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

EXCLUDE_PREFIXES = (
    "docs/archive/",
    "docs/infrastructure/archive/",
    "docs/development/plans/",
    "docs/development/epics/",
    "docs/development/reviews/",
    # Certification boards are the fourth per-run, dated, machine-generated artifact class, and
    # they arrived (2026-08-27) without this exclusion — so a synced COMMAND mandated the directory
    # while a synced CHECK penalised it, and every project reddened its gate on its first
    # certification (job-agent: 16 ERRORs, worked around by injecting 16 per-run rows into a
    # curated index). Board shape, ticket naming, dispositions and evidence paths already have a
    # dedicated grader in check_certification_coverage.py; INDEX.md maps DURABLE docs, and a cert
    # board is a run record.
    "docs/development/certifications/",
    "docs/superpowers/",
)
EXCLUDE_EXACT = {
    "docs/.doc-policy.md",  # scaffold dot-stub, deliberately unindexed
    "docs/reference/kilo/KILO_MODEL_CAPABILITIES.md",
    "docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md",
    "docs/traycer/kilo_selected_agents.md",
}
_SELECTION_RE = re.compile(r"^docs/reference/kilo/[A-Z_]*_?SELECTION\.md$")

# Hub-SEEDED and project-OWNED — exempt only while the file is still the HUB'S OWN BYTES.
#
# The governance sync drops docs/DECISIONS.md into every repo ONCE
# (fabrik_synced_manifest.SEED_IF_MISSING) and deliberately keeps it OUT of the generated
# .gitignore block, because an ignored ledger can never be committed and its git history IS the
# who/when corroboration layer. Every OTHER doc the sync writes under docs/ IS gitignored and
# therefore invisible to `ls-files --others --exclude-standard` — so this is the single file for
# which the untracked-counts-as-live rule below rests on a false premise: no session in this repo
# authored it, so "the run that creates a doc owes its INDEX row" has no author to bill, and the
# red lands on whoever next runs a gate.
#
# ⚠️ THE PREDICATE IS PROVENANCE, NOT TRACKED-NESS, and that distinction is the whole rule.
# The first version of this exemption skipped any UNTRACKED docs/DECISIONS.md, which an
# author-blind seat broke in one fixture: a project agent obeying CLAUDE.md § decision-ledger
# appends two real decision rows and runs the gate before staging — and got a GREEN, which is
# verbatim the transdoc 01M17VA9 false-green the untracked rule right below exists to prevent.
# Tracked-ness was also the wrong axis mechanically: `--others` means "not in the INDEX", so a
# bare `git add docs/` revoked the exemption and `git rm --cached` restored it, while three
# documents described it as "commits".
#
# Content settles all of it. The sync records the md5 it distributed in `.fabrik/synced.lock`,
# so "did the hub write these exact bytes" is answerable on disk, and the obligation attaches the
# moment the repo writes its FIRST decision — which is the real act of adoption.
#
# Measured 2026-09-11 over the 45 git repos under /opt that carry the file: 25 are PRISTINE
# (md5 c9081f23…, byte-identical to templates/governance/DECISIONS.md) and every one of those 25
# is untracked with no INDEX row; 20 carry their OWN decision rows and every one of those 20 is
# tracked. Pristine-and-tracked: 0. So the two axes agree on today's fleet — which is exactly why
# the tracked-ness version passed every test and every measurement, and why the hole was latent
# rather than visible. Of the 20 adopted repos, 10 owe an INDEX row they do not have; 9 of those
# 10 can actually report it — fabrik-lib is the one repo of the 45 carrying no copy of this
# check at all (sync-EXCLUDED), so nothing there ever runs it.
# The md5 of every seed the governance sync has ever distributed as docs/DECISIONS.md. A file
# matching one of these is still the HUB's bytes: the repo has recorded no decision of its own.
#
# ⚠️ Why a pinned constant and not `.fabrik/synced.lock` — measured, not assumed. The lock LOOKS
# like a provenance record and is not: it stores the md5 of what is in the destination NOW, so a
# repo that has written ten decision rows carries a lock entry matching its OWN modified file.
# Verified on /opt/trading-core, whose ledger carries exactly one added row: lock md5 and on-disk are the
# same value, so a lock-based check called it pristine and silently exempted a repo that genuinely
# owes its INDEX row. Nine true positives would have gone quiet. The only self-contained answer is
# the seed's own bytes, and `test_the_current_template_seed_is_pinned` fails the moment
# templates/governance/DECISIONS.md changes without this set being extended — so the pin cannot
# rot silently, and an unknown hash simply means NO exemption (fail closed).
_PRISTINE_SEEDS: dict[str, frozenset[str]] = {
    # Keyed by PATH, not a flat hash set: the moment this grows past one entry a flat set would
    # let file A's seed hash exempt file B, which is a sentinel collision nobody would see.
    "docs/DECISIONS.md": frozenset(
        {
            "c9081f23d0feda07d8b24562e53f7d12",  # the 14-line D-000 seed, live in 25 of 45 repos
        }
    ),
}
# There is deliberately NO second constant here. A derived `SEEDED_UNADOPTED` frozenset stood in
# this spot for one round, and an author-blind seat then proved the "it stays derived" assertion
# could constrain nothing while the pin holds a single key: HARDCODING the constant survived the
# entire mutation battery. So it was DELETED rather than better-guarded — the exemption asks
# `_PRISTINE_SEEDS` directly, a path can only be exempt if the pin knows its seed, and there is
# no second name left to drift.


# ENOENT is not the only errno that means "not there": Path.exists() also answers False for
# ENOTDIR (a parent replaced by a file), ELOOP (a symlink cycle) and EBADF. Everything else —
# EACCES above all — means "could not TELL", which is neither, and must never be silently folded
# into either. THREE call sites read path liveness; an earlier fix in this same review patched
# exactly one of them and an author-blind seat found the other two still raising, so the answer
# lives in one place now.
_ABSENT_ERRNOS = frozenset({errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EBADF})


def _printable(text: str) -> str:
    """Render a surrogateescape string safely for a UTF-8 stdout.

    Decoding git's `-z` bytes with ``surrogateescape`` is what lets a non-UTF-8 FILENAME reach a
    finding instead of raising `UnicodeDecodeError` in the decode. It also moves the failure: a
    lone surrogate raises `UnicodeEncodeError` at `print()` instead — reproduced end-to-end on a
    `docs/caf\xe9.md` fixture, where `--json` printed happily (json escapes surrogates) and the
    plain-text branch died. Same defect, one layer down. `backslashreplace` renders the raw byte
    visibly and never raises.
    """
    escaped = text.encode("utf-8", "backslashreplace").decode("utf-8")
    # C0 controls too: a `\r` inside a filename rendered one finding as TWO lines, and
    # `final_gate.py` captures with text=True, whose newline translation then makes that
    # permanent. ⚠️ NEWLINE IS ESCAPED AS WELL, and an earlier version of this line excluded it
    # on the reasoning that a newline "is the separator, not content" — true of the separator
    # `print()` adds, false of a newline INSIDE a filename, which git reports verbatim through
    # `-z` and which split a finding across two lines exactly like the CR did. Fixing one member
    # of a set and leaving its sibling open is the defect this whole review kept re-finding; the
    # string passed here never contains a separator of its own, so escaping all 32 is safe.
    return escaped.translate({i: f"\\x{i:02x}" for i in range(32)})


def _lstat_state(path: Path) -> str:
    """``absent`` | ``present`` | ``unknown`` — via lstat, so a BROKEN SYMLINK is PRESENT.

    Direction (b) asks "is this path still a thing in the worktree", and a dangling symlink is:
    a live doc with a broken target. Treating it as absent lost a finding the pre-fix version
    reported.

    ⚠️ KNOWN AND DELIBERATE, because the skip below calls the same shape "a nonsense edit to make
    a gate happy" and a seat rightly flagged the two paragraphs as disagreeing. A dangling symlink
    IS caught between the directions: (b) demands an INDEX row, and adding the natural link makes
    (a) report the target as missing. The difference from a deleted file is that a dangling
    symlink is a REAL defect in the repo — the fix is to repair or remove the link, not to edit
    INDEX.md — so being told about it twice is correct, where being told about a file you already
    deleted is not.
    """
    try:
        path.lstat()
    except ValueError:
        # `Path.exists()` — the call these helpers replaced — has TWO except arms, and the
        # rewrite reproduced only the OSError one. A non-encodable path (an embedded NUL, which
        # direction (a)'s regex happily accepts) raised straight out of the check where the
        # pre-rewrite version reported it. Proven red-on-revert by an author-blind seat.
        return "absent"
    except OSError as exc:
        return "absent" if exc.errno in _ABSENT_ERRNOS else "unknown"
    return "present"


def _target_state(path: Path) -> str:
    """``absent`` | ``present`` | ``unknown`` — via stat, so a BROKEN SYMLINK is ABSENT.

    Direction (a) asks "does what INDEX.md points at resolve", where following the link IS the
    question. ``unknown`` is reported in its own right rather than guessed in either direction.
    """
    try:
        path.stat()
    except ValueError:
        return "absent"  # non-encodable path — what Path.exists() answered here
    except OSError as exc:
        return "absent" if exc.errno in _ABSENT_ERRNOS else "unknown"
    return "present"


def _is_pristine_seed(rel: str) -> bool:
    """True when ``rel`` on disk is byte-identical to a seed the sync distributed.

    Any failure to read is False — an unprovable file is treated as the repo's own, which is the
    fail-CLOSED direction and simply restores the pre-exemption behaviour.
    """
    known = _PRISTINE_SEEDS.get(rel)
    if not known:
        return False
    try:
        # usedforsecurity=False: this is a content-identity check, not a security primitive, and
        # saying so keeps bandit's B324 honest rather than silenced by a noqa.
        return hashlib.md5((REPO / rel).read_bytes(), usedforsecurity=False).hexdigest() in known
    except OSError:
        return False


def main() -> int:
    # `_printable` below neutralises lone SURROGATES, and an author-blind seat showed that is one
    # member of the set, not the set: a valid non-ASCII character still raises on a non-UTF-8
    # stdout — including the em dash in this module's own "OK" line, which made a CLEAN repo exit
    # 1 with a traceback under `PYTHONIOENCODING=ascii`. `final_gate.py` invokes the plain-text
    # branch and inherits the gate's environment, so that is reachable. Reconfiguring the STREAM
    # covers every print, including the literals a wrapper function can never reach.
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(errors="backslashreplace")
    as_json = "--json" in sys.argv
    # T4.6 (01M23D1BF): the lean-tier mode — only the UNTRACKED live docs, so the run that
    # creates a doc sees its own INDEX debt while the file is still in hand, instead of an
    # arbitrary later run paying for it at its completion gate
    untracked_only = "--untracked-only" in sys.argv
    index_path = REPO / "INDEX.md"

    def _fail(message: str) -> int:
        if as_json:
            payload = {"status": "failure", "drift": [message]}
            if untracked_only:
                # review round 2: the lean row exits 0 here too, so say that NOTHING was examined
                payload["mode"] = "untracked-only"
                payload["examined"] = 0
            print(json.dumps(payload))
        else:
            print(f"ERROR: {_printable(message)}")
        return 0 if untracked_only else 1

    index_state = _lstat_state(index_path)
    if index_state == "unknown":
        return _fail(
            "INDEX.md could not be examined (its own directory is unreadable) — the shape test "
            "ran before the guarded read and raised out of the check"
        )
    is_regular = False
    if index_state == "present":
        # `is_file()` stats the TARGET and re-raises EACCES, so it tracebacked one call to the
        # right of the guard written to prevent exactly that — a location fix, not a class fix
        # (an INDEX.md symlinked into a mode-000 directory reproduces it).
        try:
            is_regular = stat_module.S_ISREG(index_path.stat().st_mode)
        except ValueError:
            is_regular = False
        except OSError as exc:
            if exc.errno not in _ABSENT_ERRNOS:
                return _fail(
                    "INDEX.md could not be examined (its target is unreadable) — the shape test "
                    "stats through the symlink and raised past the guard above"
                )
    if not is_regular:
        # A "skip when the repo has no docs to index" guard was written here and then DELETED,
        # because measuring it is what a new mechanism owes (FIX DIRECTIVE 5): all 8 directories
        # under /opt that carry this check and have no INDEX.md hold between 22 and 34 markdown
        # files under docs/, so the guard fired ZERO times fleet-wide. It was wallpaper, and the
        # red it would have suppressed is a TRUE positive — those repos have a docs tree and no
        # index, which is exactly what the Doc Sync Matrix requires them to have.
        # is_file() is False for a DIRECTORY and for a BROKEN SYMLINK too, and telling either of
        # those to "create the index" sends the reader after the wrong thing (both reproduced).
        shape = "is not a regular file" if index_state == "present" else "is missing"
        return _fail(
            f"INDEX.md {shape} — the docs index every Doc Sync Matrix row points at. "
            "Before this guard the read raised an uncaught exception and the gate showed a "
            "TRACEBACK, which names no remedy and reads as a broken check; the exit code is "
            "unchanged."
        )
    try:
        # read_BYTES, decoded exactly as git's `-z` output is. Two defects rode on the old
        # `read_text(errors="replace")`: text mode translates a `\r` INSIDE a filename to `\n`,
        # and `replace` yields U+FFFD where the path side yields `\udcXX`. Either way the two
        # sides of the membership test below could never match, so the finding was a red with NO
        # reachable remedy — worse than a false green, because the only exit was deleting the
        # file. Both sides now use one encoding contract.
        index_text = index_path.read_bytes().decode("utf-8", "surrogateescape")
    except OSError as exc:
        # FileNotFoundError was only ONE member of this class: an unreadable INDEX.md (mode 000)
        # still tracebacked past the guard above. Catch the class, not the instance.
        return _fail(f"INDEX.md could not be read ({exc.__class__.__name__}): {exc}")
    problems: list[str] = []

    # (a) INDEX targets exist
    for m in re.finditer(r"\]\((docs/[^)#\s]+?)(?:#[^)]*)?\)", index_text):
        t = m.group(1).replace("%20", " ").rstrip("/")
        state = _target_state(REPO / t)
        if state == "absent":
            problems.append(f"INDEX.md names missing path: {t}")
        elif state == "unknown":
            problems.append(f"INDEX.md names a path that cannot be read: {t}")

    # (b) live docs are indexed (path or basename)
    # quotePath=false: git escapes non-ASCII paths by default ("\342\200\223" for
    # an en dash) and wraps them in quotes — the escaped form never matches
    # INDEX.md's real text, false-flagging an indexed doc as missing
    # (trade-intelligence upstream, 2026-08-05).
    _ls_failure: list[str] = []

    def _ls(*extra: str) -> list[str] | None:
        """None when git could not answer — NOT an empty doc list.

        `check=False` plus `.stdout` alone silently turned git's exit 128 ("not a git
        repository") into zero docs examined and a cheerful OK: a clean-looking green with a
        denominator of nothing, which is the shape the hub contract bans outright. Reproduced on
        a non-git directory holding an INDEX.md and an unindexed doc.
        """
        try:
            proc = subprocess.run(
                # -z, and BYTES: `core.quotePath=false` only stops git quoting NON-ASCII. It
                # still C-quotes any path holding a control char, a double quote or a backslash,
                # unconditionally — and the quoted literal (`"docs/a\"b.md"`) resolves to nothing
                # on disk, so the liveness check below read five such live docs as DELETED and
                # returned a clean green. `-z` is the only output git never quotes. `text=True`
                # goes with it: universal-newline translation rewrites a `\r` inside a path into
                # `\n` and re-opens the same hole. Decoding with surrogateescape also retires the
                # UnicodeDecodeError a non-UTF-8 filename used to raise here.
                [
                    "git",
                    "-c",
                    "core.quotePath=false",
                    "ls-files",
                    "-z",
                    *extra,
                    "docs/**/*.md",
                    "docs/*.md",
                ],
                cwd=REPO,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            # The same "git could not answer" class as a non-zero exit, but a DIFFERENT cause:
            # sending an operator with no git binary off to check `.git/` wastes their time.
            _ls_failure.append(f"git could not be run ({exc.__class__.__name__}: {exc})")
            return None
        if proc.returncode != 0:
            return None
        return [
            chunk.decode("utf-8", "surrogateescape") for chunk in proc.stdout.split(b"\0") if chunk
        ]

    tracked = _ls()
    if tracked is None:
        return _fail(
            (
                _ls_failure[0]
                if _ls_failure
                else "git could not list docs/ here (is this a git repository?)"
            )
            + " — direction (b) examined 0 docs, which is not the same as finding none"
        )
    # UNTRACKED docs count as live (transdoc 01M17VA9): tracked-only scoping gave the
    # AUTHORING run a false green — the run that creates a doc got success, committed on
    # it, and the missing INDEX row surfaced as the NEXT agent's red (on a shared tree,
    # somebody else's red, with the authoring context already gone). A doc that exists on
    # disk under the INDEX-governed tree is a live doc whether or not it is staged; the
    # per-run pipeline dirs stay excluded, so in-flight drafts there never fire.
    untracked_list = _ls("--others", "--exclude-standard")
    if untracked_list is None:
        return _fail(
            (_ls_failure[0] if _ls_failure else "git could not list untracked docs/ here")
            + " — direction (b) is not trustworthy"
        )
    untracked = set(untracked_list)
    # sorted(): `untracked` is a set, so the finding ORDER varied between runs on identical input.
    for p in dict.fromkeys([*tracked, *sorted(untracked)]):
        if untracked_only and p not in untracked:
            continue
        if p.startswith(EXCLUDE_PREFIXES) or p in EXCLUDE_EXACT or _SELECTION_RE.match(p):
            continue
        if p in _PRISTINE_SEEDS and _is_pristine_seed(p):
            continue  # still the hub's own bytes — this repo has written no decision to index
        if _lstat_state(REPO / p) == "absent":
            # Tracked but deleted from the worktree. Demanding an INDEX row here puts the two
            # directions in direct contradiction: add the natural `](docs/…)` link and direction
            # (a) immediately reports the target as missing, so only a link-less bare-basename
            # mention satisfies both — a nonsense edit to make a gate happy. `unknown` (an
            # unreadable parent) deliberately falls through: the membership test below reads only
            # the path STRING, so an unreadable doc still owes its row.
            continue
        base = Path(p).name
        if p not in index_text and base not in index_text:
            tag = (
                " (untracked — the run that creates a doc owes its INDEX row)"
                if p in untracked
                else ""
            )
            problems.append(f"live doc not in INDEX.md: {p}{tag}")

    if as_json:
        payload = {"status": "success" if not problems else "failure", "drift": problems}
        if untracked_only:
            payload["mode"] = "untracked-only"
            payload["examined"] = len(untracked)
        print(json.dumps(payload))
    else:
        for x in problems:
            print(f"ERROR: {_printable(x)}")
        if not problems:
            print("check_doc_index: OK — INDEX.md and the live docs tree agree")
    # `--untracked-only` is the lean tier's ADVISORY row (final_gate registers it warn_only, whose
    # contract is "no failing exit"): the findings are the message, the exit is always 0
    return 0 if untracked_only else (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
