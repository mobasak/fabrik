#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py | none
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

import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED = "Agent-Role"
# A dedicated status for "the trailers do not parse", so the shim can tell a VERDICT from a
# CRASH. Anything else the interpreter returns means the guard broke, and a broken guard must
# never block a commit.
REJECT_CODE = 9
# Git's cut line is ONE exact string — 24 dashes, space, >8, space, 24 dashes — confirmed by
# reading a real `git commit -v` buffer. Accepting "any run of dashes" made the guard truncate a
# message at any prose line of that rough shape, and then reject it for having its trailers
# "below a scissors line" while git parsed them perfectly. The literal `# ---- >8 ----` appears in
# this guard's OWN rejection text and in hooks-index.md, so every commit documenting this guard —
# which this review loop produces each round — was self-blocked, with a remedy that was
# impossible to follow and a verify command that contradicted the verdict.
def scissors_re(cc: str = "#") -> re.Pattern[str]:
    """git's cut line for the configured comment char: 24 dashes, space, >8, space, 24 dashes."""
    return re.compile(rf"^{re.escape(cc)} -{{24}} >8 -{{24}}\s*$")


def parsed_trailers(message: str) -> dict[str, list[str]] | None:
    """Return the trailers git ITSELF parses — never a reimplementation of its rules.

    Shelling out to `git interpret-trailers --parse` is the point: a hand-rolled parser would
    drift from git's actual behaviour, and drift between the guard and the tool it guards is
    exactly how a check goes quietly vacuous.
    """
    try:
        proc = subprocess.run(
            # --no-divider: `interpret-trailers` stops at a `---` line by default, but
            # `%(trailers:key=…)` — the query CLAUDE.md says the trailers exist for, and the
            # only consumer that matters — does not. Without this the guard rejected commits
            # whose provenance was fully intact, merely because the body quoted a diff header
            # or a markdown rule above the block. Diverging from the tool you guard is the
            # failure this module's docstring calls worse than having no guard.
            ["git", "interpret-trailers", "--no-divider", "--parse"],
            input=message,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            # git RAN but could not parse — a broken config, an ancient git without
            # interpret-trailers, a wrapper. That is "cannot verify", not "no trailers": treating
            # it as the latter rejected perfectly well-formed commits, which is the same
            # breakage-indistinguishable-from-violation failure the shim was hardened against.
            return None
        out = proc.stdout
    except OSError:
        # No git on PATH. A hook that cannot consult git has no verdict it can justify, and a
        # traceback out of a hook is unactionable — return the sentinel and let main() fail open.
        return None
    # ⚠️ ALL values per key, not the last one. git's `%(trailers:key=Agent-Role)` returns every
    # matching trailer, so a message carrying `Agent-Role: primary` followed by a valueless
    # `agent-role:` still has provenance — but a last-write-wins dict saw only the empty one and
    # rejected it. Keys are lower-cased because git matches them case-insensitively.
    trailers: dict[str, list[str]] = {}
    for line in out.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            # Lower-cased KEY, because `%(trailers:key=Agent-Role)` matches case-insensitively.
            # Round 27 made the PRESENCE gate case-insensitive and left this dict lookup
            # case-sensitive, so a well-formed `agent-role:` block — which git parses perfectly —
            # was hard-rejected with the diagnosis "the final paragraph is not all-trailers",
            # which was simply false. Exactly the self-blocking class that commit set out to end.
            trailers.setdefault(key.strip().lower(), []).append(value.strip())
    return trailers


def hooks_dir() -> Path | None:
    """The hooks directory git ACTUALLY consults, honouring core.hooksPath and worktrees."""
    try:
        configured = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, check=False,
        )
        if configured.returncode == 0 and configured.stdout.strip():
            # If this is ever set, installing into .git/hooks would put the guard somewhere git
            # never looks while every "is it installed" check kept passing.
            raw = Path(configured.stdout.strip()).expanduser()
            if raw.is_absolute():
                return raw.resolve()
            # ⚠️ git resolves a RELATIVE core.hooksPath against the top of the working tree, not
            # against the process cwd. Resolving it against cwd installed into
            # <repo>/scripts/.githooks/ — reporting success while git kept looking at
            # <repo>/.githooks/ — the exact blindness this branch was added to prevent.
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=False,
            )
            if top.returncode != 0:
                return None
            return (Path(top.stdout.strip()) / raw).resolve()
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None  # no git at all — the caller reports "not a git checkout"
    if common.returncode != 0:
        return None
    # --git-common-dir resolves to the SHARED git dir from a worktree too, where `.git` is a
    # file and a naive `<repo>/.git/hooks` path would install nowhere useful.
    return Path(common.stdout.strip()).resolve() / "hooks"


def main_checkout_guard() -> Path:
    """This script as it lives in the MAIN checkout — the path every worktree's hook must use."""
    here = Path(__file__).resolve()
    try:
        # NOT --path-format=absolute: that needs git >= 2.31, and on an older git rev-parse
        # returns non-zero and this silently fell back to __file__ — reinstating the worktree
        # bug this function exists to fix, with no signal. Resolve the relative form ourselves.
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], capture_output=True, text=True, check=False
        )
    except OSError:
        return here
    if common.returncode != 0 or not common.stdout.strip():
        return here
    candidate = (Path.cwd() / common.stdout.strip()).resolve().parent / "scripts" / here.name
    # Identity check, not merely is_file(): another repo may legitimately have a file of this
    # name, and pointing every checkout's hook at a stranger's script is worse than falling back.
    if candidate.is_file() and REQUIRED in candidate.read_text(errors="replace"):
        return candidate
    return here


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
    # ⚠️ CHERRY_PICK_HEAD ONLY. Including MERGE_HEAD was a real BYPASS, reproduced: after a
    # conflicted `git merge`, the resolver runs `git commit` — a NORMAL, newly-AUTHORED commit
    # — while MERGE_HEAD still exists, and a malformed trailer sailed through unchecked. Rebase
    # replay and `git revert --no-edit` do not fire this hook at all (measured), so listing them
    # bought nothing and only widened the hole. Cherry-pick is the one case that both fires the
    # hook AND carries a message authored by someone else, which is what this exemption is for.
    d = Path(git_dir.stdout.strip())
    return (d / "CHERRY_PICK_HEAD").exists()


# git's candidate list for `core.commentChar=auto`, in its own order (see git's
# adjust_comment_line_char): it takes the first character that does not begin any line of the
# message. Reproducing the list is the only way to know which one git actually chose.
AUTO_CANDIDATES = "#;@!$%^&|:"


def verdict_comment_char() -> str:
    """The comment char git uses when DECIDING whether a trailer block survived.

    Measured, because the two cases differ and the difference is a silent lost commit:
      * `core.commentChar` set explicitly to a single char  -> `%(trailers:key=…)` HONOURS it and
        cuts at that char's cut line, so a block below one is genuinely lost.
      * `core.commentChar=auto` (or unset)                  -> parsing falls back to '#'.

    ⚠️ The reason for that second line is NOT "git only resolves auto when writing a template" —
    that is false, `adjust_comment_line_char()` runs for `-F`/`-m` too (proof: a `-F` message
    starting lines with all ten candidates makes git itself abort with "unable to select a
    comment character"). The real reason is narrower: `git log` is a SEPARATE process with no
    message to adjust against, so `auto` never resolves there. Rounds 29 and 30 both reasoned
    from the wrong premise and shipped a defect each time; the conclusion survived, the
    justification did not.

    Pinning this to '#' unconditionally was a FALSE ACCEPT under an explicit `;`: git dropped the
    block (query empty) and the guard said nothing — exactly the silent lost provenance this
    guard exists to catch. Pinning it to the DETECTED char was the mirror false reject. It has to
    be neither: it has to be what git itself will use.
    """
    try:
        got = subprocess.run(
            ["git", "config", "--get", "core.commentChar"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return "#"
    value = got.stdout.strip() if got.returncode == 0 else ""
    return value if len(value) == 1 else "#"


def comment_char(message: str | None = None) -> str:
    """git's comment character. Hardcoding '#' left a latent hijack: with `core.commentChar=;`
    neither the scissors match nor the comment strip fires, so a whole `git commit -v` diff stays
    in the authored text and a diff CONTEXT line ` Agent-Role: …` reads as an indented trailer —
    rejecting a commit over a line its author never wrote and cannot fix."""
    try:
        got = subprocess.run(
            ["git", "config", "--get", "core.commentChar"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return "#"
    value = got.stdout.strip() if got.returncode == 0 else ""
    if value == "auto" and message is not None:
        # ⚠️ Resolve it, do not assume '#'. With `auto` and a body line starting with '#' — a
        # markdown heading, routine in this repo's commit bodies — git picks ';' instead, so a
        # '#'-assuming guard neither matched the cut line nor stripped comments: the whole
        # `git commit -v` diff stayed in the authored text and a diff CONTEXT line
        # ` Agent-Role: …` read as an indented trailer, rejecting the commit over a line its
        # author never wrote. Same hijack the ';' fix closed, reached through 'auto'.
        # Detect the char git ACTUALLY used rather than recomputing its choice — the buffer
        # already contains git's own comments, so "the first candidate that starts no line"
        # excludes the very character it picked (that reasoning returned '@' where git chose ';').
        #
        # Over-eager detection is SAFE here, and that is deliberate. This char is used only by
        # authored_text(), whose sole job is deciding what the author wrote; truncating too much
        # can only make the guard see no trailer and pass the commit through — and git, which
        # resolves `auto` to '#' for parsing, will have parsed the block, so the two agree.
        # The hard-reject path (trailers_lost_below_scissors) is pinned to '#' precisely so that
        # a mis-detection can never cost anyone a rejected commit. An earlier version added a
        # "must also have a comment block" requirement to make detection conservative; with the
        # reject path pinned it bought nothing and broke detection of git's own template.
        lines = message.splitlines()
        for candidate in AUTO_CANDIDATES:
            pattern = scissors_re(candidate)
            if any(pattern.match(ln) for ln in lines):
                return candidate
        # No template of git's own making. '#' is what git itself falls back to for trailer
        # parsing under `auto`, so it is also the right answer here.
        return "#"
    return value if len(value) == 1 else "#"


def diff_region_start(lines: list[str], after: int) -> int | None:
    """Index of the `diff --git` line that begins a `git commit -v` diff, if one follows."""
    return next(
        (i for i in range(after, len(lines)) if lines[i].startswith("diff --git ")), None
    )


def cut_index(lines: list[str]) -> int | None:
    """Where git will cut this buffer — and ONLY where git will actually cut it.

    Two separate reasons to truncate, and keying both on the auto-DETECTED comment char was a
    silent FALSE ACCEPT: under `core.commentChar=auto` a message merely QUOTING a `;` cut line
    was truncated there, so a MALFORMED trailer block below it became invisible and the commit
    landed with no provenance at all. The comment that justified it — "over-truncating can only
    cause a pass-through, and git will have parsed the block, so the two agree" — is false
    exactly where it matters: git does NOT parse a malformed block, which is the only case this
    guard exists for.

    So truncate only when one of these actually holds:
      1. a cut line for the char git will DECIDE with — that is git's real cleanup;
      2. a cut line for any candidate char that is FOLLOWED BY A DIFF — the `git commit -v`
         region, which git strips regardless, and whose ` Agent-Role: …` context lines would
         otherwise read as an indented trailer and reject a commit over a line nobody wrote.
    A quoted cut line with no diff under it satisfies neither, so the block below stays visible.
    """
    verdict = scissors_re(verdict_comment_char())
    hit = next((i for i, ln in enumerate(lines) if verdict.match(ln)), None)
    if hit is not None:
        return hit
    for candidate in AUTO_CANDIDATES:
        pattern = scissors_re(candidate)
        found = next((i for i, ln in enumerate(lines) if pattern.match(ln)), None)
        if found is not None and diff_region_start(lines, found) is not None:
            return found
    return None


def authored_text(message: str) -> str:
    """The part of the buffer the author actually wrote — what git will keep as the commit."""
    lines = message.splitlines()
    cut = cut_index(lines)
    if cut is not None:
        lines = lines[:cut]
    # Strip comments for BOTH the configured char and any auto-detected one: dropping a comment
    # line can never hide a trailer, since git ignores those lines too.
    chars = {verdict_comment_char(), comment_char(message)}
    return "\n".join(ln for ln in lines if not any(ln.startswith(c) for c in chars))



TRAILER_LINE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s")


def declares_agent_role(body: str) -> bool:
    """Whether this commit is TRYING to declare provenance.

    Column 0 always counts. An INDENTED key counts only when the final paragraph is genuinely a
    trailer block — i.e. it also holds a column-0 `Key: value` line. That distinction is what
    separates the two mirror-image defects:

      * the bypass: `Agent-Context: c` / ` Agent-Role: primary` / `Co-Authored-By: …` — a real
        trailer block whose indented key git folds into the previous trailer, silently losing
        the provenance. Must be REJECTED.
      * the false reject: a docs commit whose body quotes the canonical example in an indented
        code block, with no trailer block at all. Must PASS — and it did not, which mattered
        because CLAUDE.md's own example is indented and commits about it are routine here.
    """
    lines = body.splitlines()
    # Case-insensitive, because `%(trailers:key=Agent-Role)` is: a commit writing
    # `agent-role:` with a broken block parsed as nothing and slipped past a case-sensitive
    # test entirely.
    if any(ln.lower().startswith(f"{REQUIRED.lower()}:") for ln in lines):
        return True
    # Any indented key in the FINAL paragraph counts. Requiring a column-0 anchor alongside it
    # re-opened the bypass for a block that is indented in its ENTIRETY — structurally identical
    # to a quoted example, and there is no way to tell them apart from the text. Reject is the
    # right default: a lost block is silent and permanent, while a genuinely quoted example is
    # fixed by putting the commit's own real trailer block below it (every automated producer
    # here emits one) or moving the example out of the last paragraph. The diagnosis says so.
    final = body.rstrip().split("\n\n")[-1].splitlines()
    return any(ln.strip().lower().startswith(f"{REQUIRED.lower()}:") for ln in final)


def trailers_lost_below_scissors(message: str) -> bool:
    """True when an authored trailer block sits BELOW a scissors line, where git discards it.

    A commit body that documents git's scissors line — which this repo writes routinely — and
    then puts its trailer block underneath loses its provenance silently: git honours the
    scissors marker too, so `%(trailers:key=Agent-Role)` is empty, and the guard classified the
    commit as "not an agent commit" and waved it through. That is the exact lost-provenance
    outcome this guard exists to prevent.

    Only a line starting at COLUMN 0 counts. In `git commit -v` the discarded region is a
    unified diff, where every content line carries a ' ', '+' or '-' prefix — so a real diff of
    this very file cannot trip it.
    """
    lines = message.splitlines()
    # ⚠️ Hoisted. Inside the generator's condition this ran once PER LINE, and comment_char()
    # forks `git config` — 600-line message, 600 subprocesses, 1.3s of pure hook latency where
    # the module-level constant it replaced cost nothing. It is worst exactly where it is least
    # affordable: this branch runs for every commit WITHOUT a parsable Agent-Role (the common
    # case), and with no scissors line `next()` never short-circuits, so it scans every line.
    # ⚠️ The char git will DECIDE with — see verdict_comment_char(). Not the auto-detected one
    # (that rejected a message merely quoting a `;` cut line, whose block git kept), and not a
    # hardcoded '#' either (that silently ACCEPTED a block git really dropped under an explicit
    # `core.commentChar=;`). authored_text() deliberately uses the detected char instead: there
    # over-truncating can only cause a pass-through, which agrees with git.
    pattern = scissors_re(verdict_comment_char())
    scissors = next((i for i, ln in enumerate(lines) if pattern.match(ln)), None)
    if scissors is None:
        return False
    # Stop at a `git commit -v` diff: its content lines carry a ' '/'+'/'-' prefix, and an
    # indented match there would reject a commit over a line its author never wrote. Below the
    # cut line but ABOVE any diff, an INDENTED key counts — declares_agent_role() was taught to
    # catch that shape and this path disagreed with it, letting an indented block sitting below
    # a genuine cut line be discarded by git in silence.
    region = lines[scissors + 1 :]
    diff_at = diff_region_start(region, 0)
    if diff_at is not None:
        region = region[:diff_at]
    return any(ln.strip().lower().startswith(f"{REQUIRED.lower()}:") for ln in region)


def diagnose(message: str) -> str:
    """Name the specific defect, so the fix is obvious without re-deriving git's rules."""
    lines = message.rstrip().splitlines()
    idx = next(
        (i for i, ln in enumerate(lines)
         if ln.strip().lower().startswith(f"{REQUIRED.lower()}:")),
        None,
    )
    if idx is None:
        return "no Agent-Role: line found"
    if lines[idx] != lines[idx].strip():
        return (
            f"line {idx + 1} is INDENTED ({lines[idx][:60]!r}). Git folds an indented line into "
            f"the previous trailer as a continuation, so {REQUIRED} never parses. Remove the "
            f"leading whitespace."
        )
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
#
# ⚠️ FAIL OPEN, ALWAYS. A hook that cannot run must never block a commit. Pinning one absolute
# interpreter once made a rebuilt venv reject EVERY commit in the repo. `command -v` was not
# enough of a fix: under /bin/sh (dash here) `command -v` ACCEPTS an existing but
# non-executable file, so a lost exec bit or a noexec mount still reached `exec`, which fails
# 126 and never falls through — the identical repo-wide blocker. Test executability directly.
GUARD={guard}
# -r, not -f: python must READ this file. An existing but unreadable guard would make the
# interpreter exit non-zero and block the commit — failing closed on a permissions problem.
[ -r "$GUARD" ] || exit 0
for PY in {pythons}; do
    case "$PY" in
        /*) [ -f "$PY" ] && [ -x "$PY" ] || continue ;;  # -x alone is true for a directory
        *)  PY=$(command -v "$PY" 2>/dev/null) || continue
            [ -x "$PY" ] || continue ;;
    esac
    "$PY" "$GUARD" "$1"
    rc=$?
    # ⚠️ ONLY a deliberate rejection blocks. The guard exits {reject} to say "this trailer block
    # does not parse"; ANY other status is the guard failing, not the commit — a syntax error
    # from a sibling's half-written edit, a bad import, a missing dependency. This file is a
    # live edit target on a tree three agents share, so `exec`ing it made every commit in the
    # repo hostage to whoever was mid-save. Reproduced: SyntaxError -> rc=1 -> a plain commit
    # with no trailers rejected.
    [ "$rc" = {reject} ] && exit 1
    exit 0
done
exit 0
"""


def install(force: bool = False) -> int:
    """Write .git/hooks/commit-msg. Idempotent; refuses to clobber a foreign hook.

    `--force` exists because `pre-commit install --hook-type commit-msg` — a command the docs
    used to recommend — REPLACES this hook with pre-commit's generated one and moves ours to
    `commit-msg.legacy`. That silently restores the doubled staged_files_only() stash cycle this
    guard was moved off pre-commit to avoid. Without --force, install() saw a foreign hook and
    refused, leaving no way back short of deleting the file by hand.
    """
    hook = hooks_dir()
    if hook is None:
        print("not a git checkout", file=sys.stderr)
        return 1
    hook = hook / "commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() and "check_commit_trailers" not in hook.read_text(errors="replace"):
        existing = hook.read_text(errors="replace")
        # pre-commit's generated hook is a KNOWN, self-inflicted takeover, not a third party's
        # work: `pre-commit install --hook-type commit-msg` silently replaces this hook and
        # restores the doubled stash cycle the guard was moved off pre-commit to avoid. Reclaim
        # it automatically, so the unattended boot heal — which cannot pass --force safely for
        # the general case — can actually recover. Anything else still needs an explicit --force.
        # ⚠️ Match pre-commit's GENERATED hook, not the word "pre-commit". A bare substring
        # fired on any hook whose COMMENTS mentioned pre-commit — reproduced against a commitlint
        # hook whose only offence was referencing .pre-commit-config.yaml in a comment; it was
        # silently destroyed with no --force and no backup. These two markers are written by
        # pre-commit itself into every hook it generates.
        if "File generated by pre-commit" in existing or "pre_commit.main" in existing:
            print(
                f"reclaiming {hook} from pre-commit — its commit-msg stage restores the "
                f"doubled staged_files_only() stash cycle",
                file=sys.stderr,
            )
        elif force:
            print(f"--force: replacing the existing hook at {hook}", file=sys.stderr)
        else:
            print(
                f"refusing to overwrite an existing unrelated hook: {hook}\n"
                f"  (re-run with --force if you are sure)",
                file=sys.stderr,
            )
            return 1
    # ⚠️ Embed the MAIN checkout's copy of this script, never `__file__`. install() writes to
    # the SHARED hooks dir, so running it from a worktree pointed every checkout's hook at a
    # worktree-local path — and when that worktree was removed, `[ -f "$GUARD" ] || exit 0`
    # disabled the guard for the whole repo, permanently and silently, while every "is it
    # installed" assertion still passed. Reproduced: malformed commit landed rc=0, trailer empty.
    # Worktrees are routine here (plan execution + subagents), and the docs tell readers to run
    # --install from wherever they are.
    guard_path = main_checkout_guard()
    if hook.exists() and "check_commit_trailers" not in hook.read_text(errors="replace"):
        # Unique name: a single fixed backup path silently destroyed the FIRST foreign hook the
        # second time install() replaced one, and nothing ever restores this file.
        backup = hook.with_suffix(f".replaced-by-fabrik.{os.getpid()}")
        n = 0
        while backup.exists():
            n += 1
            backup = hook.with_suffix(f".replaced-by-fabrik.{os.getpid()}.{n}")
        backup.write_text(hook.read_text(errors="replace"))
        print(f"backed up the previous hook to {backup}", file=sys.stderr)
    payload = (
        SHIM.format(
            guard=shlex.quote(str(guard_path)),
            # shlex.quote: an apostrophe anywhere in a path (`/opt/o'brien/...`) produced an
            # unterminated string and rc=2 — every commit rejected, the exact opposite of the
            # FAIL OPEN the shim promises.
            pythons=" ".join(shlex.quote(x) for x in (sys.executable, "python3", "python")),
            reject=REJECT_CODE,
        )
    )
    # Atomic: install() now runs on every interactive shell, and a `git commit` that started the
    # hook inside a truncate->write window would read a partial (or empty) script — an empty sh
    # script exits 0, so that commit would pass unchecked and silently.
    # A SHARED fixed temp name reintroduced the very race the atomic write closed, one level
    # down: install() now runs on every interactive shell on a three-agent box, and two shells
    # interleaving on one `commit-msg.tmp` could publish a zero-length file — an empty sh script
    # exits 0, i.e. the guard silently off. mkstemp gives each writer its own inode.
    fd, tmp_name = tempfile.mkstemp(dir=str(hook.parent), prefix="commit-msg.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(payload)
        tmp.chmod(0o755)
        tmp.replace(hook)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    print(f"installed {hook} -> {guard_path}")
    return 0


def _warn_agent_name_mismatch(trailers: dict[str, list[str]]) -> None:
    """ADVISORY (D-034): a session with CLAUDE_AGENT set signing an Agent-Name that
    differs is the mis-signed-day class — warn loudly, never reject (a wrong warning
    must not block a shared tree; promotion waits on measured fire rate). Env unset
    (every project repo, unnamed hub windows) or no Agent-Name trailer → silent."""
    env_name = os.environ.get("CLAUDE_AGENT", "").strip()
    signed = [v.strip() for v in trailers.get("agent-name", []) if v.strip()]
    if not env_name or not signed or env_name in signed:
        return
    print(
        f"\n⚠️  [advisory] Agent-Name mismatch: this session is CLAUDE_AGENT={env_name} "
        f"but the commit signs Agent-Name: {', '.join(signed)} — the mis-signed-day class "
        f"(D-034). Commit proceeds; fix the trailer if the env var is right.\n",
        file=sys.stderr,
    )


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "--install":
        return install(force="--force" in argv[2:])
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
    # ⚠️ Compare the STRIPPED line. A single leading space makes git fold the key into the
    # previous trailer as a continuation, so `%(trailers:key=Agent-Role)` comes back empty —
    # and a column-0-only test read that as "no trailer here" and accepted the commit. That is
    # the lost-provenance outcome the guard exists to stop. A diff line (`+Agent-Role:`) still
    # does not match, because stripping whitespace leaves the `+`.
    if not declares_agent_role(body):
        if trailers_lost_below_scissors(message):
            cc = verdict_comment_char()  # the char this verdict was computed against
            print(
                f"\n❌ COMMIT REJECTED — a {REQUIRED} block sits BELOW git's cut line.\n\n"
                f"   Under -m/-F and under `git commit -v`, git discards everything below\n"
                f"   `{cc} ------------------------ >8 ------------------------`, so these\n"
                f"   trailers would be thrown away and the commit would land with no provenance.\n"
                f"   Move the trailer block ABOVE that line, or break up the quoted cut line.\n\n"
                f"   ⚠️ Known limitation: an INTERACTIVE editor commit under the default cleanup\n"
                f"   mode STRIPS that line instead of truncating at it, and would have kept your\n"
                f"   trailers. The hook cannot tell the two apart from the message alone, and it\n"
                f"   errs toward the mode every automated commit here uses. If that is your case,\n"
                f"   `git commit --no-verify` is the right escape.\n",
                file=sys.stderr,
            )
            # Deliberately NOT printing the `git log --format=%(trailers:…)` verify line here:
            # on the editor path that query would print the role and flatly contradict this
            # verdict, which is worse than saying nothing.
            return REJECT_CODE
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
    # any() over the values: one non-empty value is provenance, exactly as git reports it.
    if any(trailers.get(REQUIRED.lower(), [])):
        _warn_agent_name_mismatch(trailers)
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
    return REJECT_CODE


if __name__ == "__main__":
    sys.exit(main(sys.argv))
