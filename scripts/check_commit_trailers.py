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


def parsed_trailers(message: str) -> dict[str, str] | None:
    """Return the trailers git ITSELF parses — never a reimplementation of its rules.

    Shelling out to `git interpret-trailers --parse` is the point: a hand-rolled parser would
    drift from git's actual behaviour, and drift between the guard and the tool it guards is
    exactly how a check goes quietly vacuous.
    """
    try:
        out = subprocess.run(
            ["git", "interpret-trailers", "--parse"],
            input=message,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        # No git on PATH. A hook that cannot consult git has no verdict it can justify, and a
        # traceback out of a hook is unactionable — return the sentinel and let main() fail open.
        return None
    trailers: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            trailers[key.strip()] = value.strip()
    return trailers


def replaying() -> bool:
    """True when git is replaying someone else's message rather than taking a new one."""
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"], capture_output=True, text=True, check=False
        )
    except OSError:
        return False  # no git — parsed_trailers() reports the same condition and fails open
    if git_dir.returncode != 0:
        return False
    d = Path(git_dir.stdout.strip())
    return any(
        (d / marker).exists()
        for marker in ("CHERRY_PICK_HEAD", "REVERT_HEAD", "MERGE_HEAD", "rebase-merge", "rebase-apply")
    )


def authored_text(message: str) -> str:
    """The part of the buffer the author actually wrote — what git will keep as the commit.

    Two things get discarded, mirroring git's own cleanup: everything below a scissors line
    (`git commit -v` puts the entire diff there, uncommented), and `#` comment lines.
    """
    lines = message.splitlines()
    scissors = next(
        (i for i, ln in enumerate(lines) if ln.startswith("#") and ">8" in ln), None
    )
    if scissors is not None:
        lines = lines[:scissors]
    return "\n".join(ln for ln in lines if not ln.startswith("#"))


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


SHIM = """#!/bin/sh
# Installed by scripts/check_commit_trailers.py --install. Deliberately a plain git hook rather
# than a pre-commit stage: pre-commit's commit-msg stage stashes and restores unstaged work a
# SECOND time per commit, and this tree is shared by three concurrent agents.
exec {python} {script} "$1"
"""


def install() -> int:
    """Write .git/hooks/commit-msg. Idempotent; refuses to clobber a foreign hook."""
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True, check=False
    )
    if common.returncode != 0:
        print("not a git checkout", file=sys.stderr)
        return 1
    # --git-common-dir resolves to the SHARED hooks dir from a worktree too, where `.git` is a
    # file and a naive `<repo>/.git/hooks` path would silently install nowhere useful.
    hook = (Path(common.stdout.strip()).resolve()) / "hooks" / "commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() and "check_commit_trailers" not in hook.read_text(errors="replace"):
        print(f"refusing to overwrite an existing unrelated hook: {hook}", file=sys.stderr)
        return 1
    hook.write_text(SHIM.format(python=sys.executable, script=Path(__file__).resolve()))
    hook.chmod(0o755)
    print(f"installed {hook}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--install":
        return install()
    if len(argv) < 2:
        print("usage: check_commit_trailers.py <commit-msg-file>", file=sys.stderr)
        return 2
    # A REPLAYED message was not authored here. `git cherry-pick` DOES fire the commit-msg hook
    # (measured; `git revert --no-edit` and rebase replay do not) — so without this, backporting
    # any of the ~190 historically-malformed hub commits would be hard-blocked, forcing the
    # operator to --no-verify or rewrite history. This guard exists to stop NEW bad trailers, not
    # to make old commits un-cherry-pickable.
    if replaying():
        return 0

    # errors="replace" rather than a hard UTF-8 decode, and a caught OSError: a non-UTF-8 byte
    # (i18n.commitEncoding) or an unreadable path must not throw a traceback out of a git hook,
    # which is an unactionable failure. Fail OPEN on a message we cannot read at all — the guard
    # has no opinion it can justify about bytes it never saw.
    try:
        message = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"[check_commit_trailers] cannot read {argv[1]}: {exc}", file=sys.stderr)
        return 0
    # ⚠️ The DECISION is made on the RAW message, never a preprocessed copy — git ignores
    # comment lines inside a trailer block itself, so stripping them here would only create
    # room for the guard's verdict to diverge from git's. Verified across 7 adversarial cases
    # (editor comments appended, a comment inside the block, `#123` issue refs, a markdown
    # heading in the body, and the two real defect shapes): 0 divergences, so the stripping
    # that used to live here was pure redundancy carrying pure risk. Pinned by
    # test_the_guards_verdict_never_diverges_from_git.
    # The PRESENCE check runs on the authored text only, and matches a LINE that STARTS with the
    # trailer key — never a substring. Two distinct false-rejects came from getting this wrong:
    #   * `git commit -v` appends the full diff below a scissors line, UNCOMMENTED, so any commit
    #     editing a file that contains `Agent-Role:` (this script, its tests, CLAUDE.md) carried
    #     the token without being an agent commit;
    #   * a substring test rejected `docs: explain why Agent-Role: must sit in the last paragraph`
    #     — prose that merely QUOTES the key, which governance commits in this repo do routinely.
    # The tell in both cases was a self-contradictory rejection: "Agent-Role is present" printed
    # directly above "no Agent-Role: line found". `diagnose()` always used `startswith`; only this
    # gate disagreed with it, and the disagreement was the bug.
    body = authored_text(message)
    if not any(ln.startswith(f"{REQUIRED}:") for ln in body.splitlines()):
        return 0  # not an agent commit — merges, reverts, and human commits pass through

    # The VERDICT is git's own, on the raw message: git ignores comments and scissors itself, so
    # asking it directly is the only way the guard cannot drift from the tool it guards.
    trailers = parsed_trailers(message)
    if trailers is None:
        print(
            "[check_commit_trailers] git is not available — cannot verify trailers, allowing",
            file=sys.stderr,
        )
        return 0
    if trailers.get(REQUIRED):
        return 0

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
