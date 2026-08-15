#!/usr/bin/env python3
# AFTER-EDIT: .pre-commit-config.yaml, scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py | none
"""Reject a commit whose Agent Provenance Trailers do not actually PARSE.

Run as a `commit-msg` pre-commit hook, so it fires while the message is still editable —
after the commit lands it is unfixable without a force-push, which is a HARD STOP.

Why this exists, measured rather than assumed: on 2026-08-15, **200 of the last 200** hub
commits carried an `Agent-Role:` line and only **10** of them parsed. The cause was a single
malformed example in CLAUDE.md that every agent copied. That example was corrected fleet-wide
— and the next 50 commits STILL parsed at 0/50, including one written by the agent that made
the correction, working from a session-start snapshot of the file that predated its own fix.

That is the whole lesson: **documentation cannot enforce a machine-readable format.** An agent
reads the contract once at session start and writes commits for hours afterwards; any later fix
to the prose is invisible to every session already running. Only a check that reads the actual
message at write time closes it.

Git's rule (`git-interpret-trailers`): trailers are parsed from the LAST paragraph of the
message, and only when that paragraph is entirely trailers. So both of these silently yield an
empty `%(trailers:key=Agent-Role)`:

    Agent-Role: primary            <- demoted to prose: the blank line below ends the paragraph
                                      and `Co-Authored-By` alone becomes the trailer block
    Co-Authored-By: ...

    ...fixed the thing.            <- demoted to prose: no blank line above the block, so the
    Agent-Role: primary               paragraph is not all-trailers

Exit 1 with the offending message on failure; exit 0 when the commit carries no `Agent-Role:`
at all (merge commits, `git revert`, and human commits are not this hook's business).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REQUIRED = "Agent-Role"


def parsed_trailers(message: str) -> dict[str, str]:
    """Return the trailers git ITSELF parses — never a reimplementation of its rules.

    Shelling out to `git interpret-trailers --parse` is the point: a hand-rolled parser would
    drift from git's actual behaviour, and drift between the guard and the tool it guards is
    exactly how a check goes quietly vacuous.
    """
    out = subprocess.run(
        ["git", "interpret-trailers", "--parse"],
        input=message,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    trailers: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            trailers[key.strip()] = value.strip()
    return trailers


def diagnose(message: str) -> str:
    """Name the specific defect, so the fix is obvious without re-deriving git's rules."""
    lines = message.rstrip().splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.startswith(f"{REQUIRED}:")), None)
    if idx is None:
        return "no Agent-Role: line found"
    after = lines[idx + 1 :]
    if any(ln.strip() == "" for ln in after):
        blank = idx + 1 + next(i for i, ln in enumerate(after) if ln.strip() == "")
        return (
            f"there is a BLANK LINE at line {blank + 1}, below the trailer block. Git parses "
            f"only the LAST paragraph, so everything above that blank line — including "
            f"{REQUIRED} — is demoted to prose. Delete it: the trailers and Co-Authored-By "
            f"must sit in ONE unbroken paragraph."
        )
    if idx > 0 and lines[idx - 1].strip() != "":
        return (
            f"line {idx} ({lines[idx - 1][:60]!r}) is prose GLUED to the top of the trailer "
            f"block with no blank line between. That makes the final paragraph not "
            f"all-trailers, so git parses none of it. Add a blank line above {REQUIRED}."
        )
    if not re.match(r"^[A-Za-z][A-Za-z0-9-]*:\s", lines[idx]):
        return f"the {REQUIRED} line is malformed: {lines[idx][:80]!r}"
    return (
        "the final paragraph is not all-trailers — every line in it must be `Key: value` "
        "with no blank lines, no bullets, and no wrapped continuations."
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: check_commit_trailers.py <commit-msg-file>", file=sys.stderr)
        return 2
    # errors="replace" rather than a hard UTF-8 decode: a non-UTF-8 byte in a commit message
    # must not crash the hook with a traceback. The guard still runs; worst case a mangled
    # character appears in the diagnosis.
    message = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    # ⚠️ The DECISION is made on the RAW message, never a preprocessed copy — git ignores
    # comment lines inside a trailer block itself, so stripping them here would only create
    # room for the guard's verdict to diverge from git's. Verified across 7 adversarial cases
    # (editor comments appended, a comment inside the block, `#123` issue refs, a markdown
    # heading in the body, and the two real defect shapes): 0 divergences, so the stripping
    # that used to live here was pure redundancy carrying pure risk. Pinned by
    # test_the_guards_verdict_never_diverges_from_git.
    if f"{REQUIRED}:" not in message:
        return 0  # not an agent commit — merges, reverts, and human commits pass through

    if parsed_trailers(message).get(REQUIRED):
        return 0

    # Only the DIAGNOSIS drops comment lines, so reported line numbers describe the message
    # the author actually wrote rather than git's appended editor boilerplate.
    body = "\n".join(ln for ln in message.splitlines() if not ln.startswith("#"))

    print(
        f"\n❌ COMMIT REJECTED — {REQUIRED} is present but git CANNOT parse it.\n\n"
        f"   {diagnose(body)}\n\n"
        f"   Verify with:  git log -1 --format='%(trailers:key={REQUIRED},valueonly)'\n"
        f"   It must print the role, not an empty line. Fix the message and commit again —\n"
        f"   after the commit is pushed this is only fixable by a force-push, which is a\n"
        f"   HARD STOP.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
