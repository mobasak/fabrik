#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, docs/workstation/claude-account-rotation.md, scripts/fabrik_synced_manifest.py, tests/test_quota_stop_hook.py
"""PreToolUse — the fleet-wide GRACEFUL STOP when the quota is exhausted with nothing to rotate to.

Operator rule (2026-09-02): broadcast only when there is NO account left to rotate to and agents
are about to hit the wall — and then every agent must stop gracefully, losing no work, ready to be
restarted. Mail reaches a session only at its next prompt; this hook reaches it at its next TOOL
CALL, which is the only moment a mid-turn agent can be stopped.

Signal: the rotation tick's exhaustion stamp (`<state>/fleet-exhausted`), written by
`claude_rotate.py::_fleet_active_wall_advisory` exactly when the ACTIVE account is walled and the
picker found no successor (or the operator paused rotation), and unlinked by the same tick the
moment relief arrives (a flip or a reset). No other writer, no other reader with authority.

While the stamp stands the rule is DEFAULT-DENY: every tool that can change the world is held —
Edit/Write/MultiEdit/NotebookEdit, MCP editors (serena replace/insert/rename, browser clicks),
Agent/Workflow dispatch, and any Bash that is not ONE simple checkpoint or read command — with one instruction — commit + push your own work with
explicit pathspecs, close your run record, stop. Reads (Read/Grep/Glob/LS), git checkpointing,
`command_run.py`, `mail.py` and `thread_anchor.py` stay allowed, so a session can finish cleanly
and the Stop hook's commit-and-push law can be met. The block lifts by itself when the tick clears
the stamp; a session that already ended is restarted by the operator (or the resume mesh).

FAIL-OPEN, deliberately: no stamp → allow; unreadable state → allow; a stamp older than the tick
could have refreshed (the tick log has not moved for QUOTA_STOP_TICK_STALE_S, default 900s) →
allow with a one-line warning, because a dead cron must never freeze the fleet behind a stale
flag. ROTATE_STATE_DIR is honored (the tick's own override) so tests never touch the real stamp.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import sys
import time
from pathlib import Path

# While the stamp stands the matcher is `.*` and the rule is DEFAULT-DENY for anything that can
# change the world: an edit through an MCP tool (serena replace/insert/rename, a browser click, an
# Agent/Workflow dispatch) is an edit. Reads stay open so a session can orient and checkpoint.
_READ_TOOLS = {
    "Read",
    "Grep",
    "Glob",
    "LS",
    "ToolSearch",
    "AskUserQuestion",
    "TaskOutput",
    "Monitor",
    "ListMcpResourcesTool",
    "ReadMcpResourceTool",
    "ReadMcpResourceDirTool",
    "ListAgents",
}
_READ_MCP = re.compile(
    r"^mcp__(session-recall__|serena__(find_|get_|read_memory|list_memories|initial_instructions|onboarding))"
)
# Bash commands a stopping session still needs: checkpoint, close records, read. ONE simple
# command per call — the allow-list is matched against the WHOLE line, and a line carrying a
# control operator, a substitution or a file redirection is refused outright (review finding:
# `git push && python3 evil.py` passed a first-segment match).
_ALLOWED_BASH = re.compile(
    # `branch` is OFF the verb list (pass 17): `git branch -D x` deleted a ref under `allow`;
    # `git rev-parse --abbrev-ref HEAD` / `git status` answer the read. `fetch`/`push` stay —
    # the hold ORDERS a push — but their own program-running flags are vetoed below.
    r"^\s*(git\s+(add|commit|push|status|diff|log|fetch|show|rev-parse)\b"
    # index realign ONLY, the exact form — `HEAD\b` alone admitted `HEAD^`, `HEAD~1` and a trailing
    # `--hard` (pass 20, executed: a commit rewound, an edit destroyed); after `--` git reads paths
    r"|git\s+reset\s+(-q\s+)?HEAD\s+--\s+\S"
    # Anchored to the `scripts/` directory the manifest syncs them to: `\S*command_run\.py`
    # matched ANY path ending in the basename, so a planted `x/command_run.py` ran under
    # `allow` (pass 17, executed). Relative (`scripts/…`) and absolute (`/opt/fabrik/scripts/…`)
    # both match; nothing else has ever needed to.
    # …and the prefix is ABSOLUTE or absent: `(?:\S*/)?` admitted `../scripts/command_run.py`
    # and `x/scripts/mail.py`, a look-alike reached by traversal (pass 19, executed). A held
    # session in a subdirectory uses the absolute path.
    # …and an absolute prefix is a fleet repo under /opt (every synced repo lives there): `/\S*/`
    # admitted any planted `/x/scripts/command_run.py` (pass 20, executed)
    # `python3.12` is a python; a repo segment may not be `..` (`/opt/../scripts/x.py` escaped
    # the anchor) and `.py` must END the token (`command_run.py.bak` ran) — pass 21, executed
    r"|python3?(?:\.\d+)?\s+(?:/opt/[\w-][\w.-]*/)?scripts/(command_run|mail|thread_anchor)\.py(?=\s|$)"
    # `find` is OFF the list: `find . -name x -delete` destroys files with no shell operator to
    # veto — proven by execution, a held session deleted a file (review 2026-09-05, pass 14). A
    # held session locating files uses `ls -R` or `grep -rl`; enumerating find's
    # action flags (-delete/-exec/-ok/-fprint…) would be one more list to be wrong about.
    # `sed` is OFF the list too (pass 16): the `-n … never with -i` lookahead read the RAW line
    # and wanted whitespace before `-i`, so `'-i'`, `-Ei`, `--in-place` and GNU's prefixes
    # (`--i`, `--in`) all passed — and each TRUNCATED the file to 0 bytes (`-n` suppresses the
    # in-place output). With no flag at all, sed's own script writes (`w file`) and executes
    # (`e cmd`); both proven on disk under `allow`. `cat -n` / `grep -n` cover a held read.
    # `rg` is OFF the list (pass 17): `rg --pre <program>` runs the program on every file it
    # reads — proven on disk under `allow`. `grep` has no exec path and covers every held read.
    # `date` is off too: `date -s` sets the clock (root-gated here, not everywhere) — the very
    # clock the tick-staleness check reads. No checkpoint needs it.
    r"|(cat|head|tail|grep|ls|wc|md5sum|readlink|echo|pwd|stat)\b)"
)
# A lone `&` is bash's BACKGROUND separator — `git status & evil` runs both, and the whole-line
# hardening listed `&&` but never the single form: proven by execution (a held session's
# `git status & touch marker` was allowed and the marker appeared — review 2026-09-05, pass 13).
# `(?<!>)&(?!&)`: not an fd-duplication (`2>&1`, `>&2` — the `&` there follows `>`) and not the
# `&&` the first branch already catches. The lookbehind once also excused a DIGIT, for which no
# legitimate form exists: `git status 1& touch m` and `git log 2>&1& touch m` both backgrounded
# the first command and ran the second (pass 17, executed — a pool finder's claim, proven).
# `<(` / `>(` is PROCESS SUBSTITUTION — bash runs the inner command: `git status <(touch m)` was
# allowed and the marker appeared (review 2026-09-05, pass 14, executed). No operator on the
# list, no quote to mask; the paren after `<`/`>` is the tell.
# `$'…'` (ANSI-C) and `$"…"` (locale) QUOTING: bash decodes the span into a plain word — `$'--output=m'`
# and even `$'\x2d\x2doutput=m'` reached git as `--output=m` and wrote (pass 19, executed, raised
# by a pool finder) — while shlex, which the git-flag veto reads, keeps the `$` glued to the
# token so no `--` is seen. Neither form has a place in a checkpoint command; on the masked line
# the quote char survives masking, so `\$['"]` at top level is the tell (inside double quotes the
# inner quote is masked, so a commit message containing `$'` stays data).
# An UNQUOTED `$NAME`/`${NAME}` word-splits at run time: `git push $PV` with `PV='origin --force'`
# set before the hold made a FORCED UPDATE on a remote, and `git commit -m $MSG` with a `--amend`
# inside amended a pushed commit (pass 24, P23-A, executed) — the argv the checker reads has one
# opaque token where bash has two. Quoted, it is one word and stays data (masked above).
# …and since pass 25 ANY `$` the masker leaves visible is a veto: an unquoted one in any form
# (`$@`, `$*` and friends escaped `\$[\w{]`), or one that OPENS a double-quoted span (`"$F"` — a
# whole word that can be a flag). A `$` inside quoted text is masked and never reaches this.
_UNSAFE_SHELL = re.compile(r"&&|\|\||;|\||\$|`|\n|(?<!>)&(?!&)|[<>]\(")
# git VERBS carry no flag scope of their own, and every flag list of DANGEROUS ones was wrong the
# next pass: `--output` (pass 14), `--upload-pack`/`--receive-pack` (17), quoted and abbreviated
# forms (18), `--ext-diff`/`--chmod` (19), and then the convergence sweep (P19-A, 93 candidates,
# 23 confirmed on disk): `push --force`/`-f`/`+ref`/`--delete`/`:ref`, `commit --amend`/`-a`,
# `add -A`, `--textconv` — each a HARD STOP of CLAUDE.md, each admitted by a bare verb word.
# So the set is POSITIVE: per verb, the flags a checkpoint or a read needs; anything else holds.
# Read as ARGV on the RAW line (a quoted flag is still a flag; `$'…'` is vetoed upstream), a
# bare `--` ends options, a `-abc` cluster must be all-listed letters (trailing digits allowed —
# `-n1`, `-U3`, `-5`), a long option is matched by its full name only (git's own abbreviations
# are refused — fail-closed), and a push REFSPEC may not start with `+` (force) or `:` (delete).
# The cost is named: an unlisted READ flag is refused with the same message.
_GIT_READ_LONG = frozenset(
    [
        "--cached",
        "--staged",
        "--stat",
        "--numstat",
        "--shortstat",
        "--name-only",
        "--name-status",
        "--summary",
        "--patch",
        "--no-patch",
        "--word-diff",
        "--color",
        "--no-color",
        "--unified",
        "--function-context",
        "--ignore-all-space",
        "--ignore-space-change",
        "--ignore-blank-lines",
        "--find-renames",
        "--no-renames",
        "--quiet",
        "--exit-code",
        "--relative",
        "--diff-filter",
        "--no-prefix",
        "--check",
        "--abbrev",
        "--compact-summary",
        "--text",
        "--no-ext-diff",
        "--no-textconv",
        "--oneline",
        "--format",
        "--pretty",
        "--graph",
        "--decorate",
        "--no-decorate",
        "--abbrev-commit",
        "--date",
        "--author",
        "--committer",
        "--grep",
        "--since",
        "--after",
        "--until",
        "--before",
        "--max-count",
        "--skip",
        "--reverse",
        "--topo-order",
        "--date-order",
        "--first-parent",
        "--no-merges",
        "--merges",
        "--follow",
        "--all",
        "--branches",
        "--tags",
        "--remotes",
        "--not",
        "--relative-date",
        "--show-signature",
        "--no-show-signature",
        "--expand-tabs",
        "--parents",
        "--children",
        "--left-right",
        "--cherry",
        "--pickaxe-regex",
        "--pickaxe-all",
        "--diff-merges",
        "--no-diff-merges",
        "--cc",
        "--combined",
        "--exclude",
        "--glob",
    ]
)
_GIT_VERB_FLAGS: dict[str, tuple[frozenset[str] | None, str | None]] = {
    "add": (frozenset({"--verbose", "--dry-run"}), "vn"),
    "commit": (frozenset({"--message", "--file", "--quiet", "--verbose", "--only"}), "mFqvo"),
    "push": (frozenset({"--set-upstream", "--quiet", "--verbose", "--porcelain"}), "uqv"),
    "fetch": (
        frozenset({"--quiet", "--verbose", "--tags"}),
        "qvt",
    ),  # no --prune: a checkpoint never deletes refs
    "status": (
        frozenset(
            [
                "--short",
                "--porcelain",
                "--branch",
                "--long",
                "--verbose",
                "--untracked-files",
                "--ignored",
                "--show-stash",
                "--ahead-behind",
                "--no-ahead-behind",
                "--column",
                "--no-column",
                "--renames",
                "--no-renames",
                "--find-renames",
            ]
        ),
        "sbvu",
    ),
    "diff": (_GIT_READ_LONG, "pUuwbWMCRzqSGaDlOr"),
    "log": (_GIT_READ_LONG, "pUuwbWMCRzqSGaDlOrnLgiEFPmc"),
    "show": (_GIT_READ_LONG, "pUuwbWMCRzqSGaDlOrnLgiEFPmc"),
    "rev-parse": (None, None),  # pure read; every flag, long or short, is a query
    "reset": (frozenset(), "q"),  # the allow regex fixes the form; listed so the PATHSPEC rule runs
}


def _git_flags_forbidden(command: str) -> bool:
    """True when a git line carries any flag outside its verb's checkpoint/read set — or, for
    the verbs that WRITE the index/refs, a pathspec or refspec that sweeps instead of naming.

    `git add .`, `git commit -m x -- .` and `git reset -q HEAD -- .` each swept a SIBLING's work on
    disk under `allow` (pass 21, P20-A): the flag set never looked at the positional argument, and
    `.` is the HARD STOP CLAUDE.md names in one breath with `-A`. A pathspec to add/commit/reset
    may not normalise to `.`/`..` or escape upward (`../x`), nor be a glob or git's `:(magic)` form
    (a directory path still names a scope;
    named, not held). A push refspec may not START with `+` (force) or `:` (empty source =
    delete; `a:b` is a plain push); a fetch refspec may not start with `+` or contain `:` at all
    (`git fetch origin +x:x` force-moved a local branch) — before OR after `--`, which ends
    options for git — but not for this check, which reads every flag-shaped token wherever it
    sits (`git push origin -- +master` was a force push; `git commit -m -- --amend` an amend).
    """
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return True  # unbalanced quote: cannot know the argv — fail closed
    if len(argv) < 2 or argv[0] != "git":
        return False
    verb = argv[1]
    if verb not in _GIT_VERB_FLAGS:
        return False  # not a verb the allow-list regex admits
    long_ok, short_ok = _GIT_VERB_FLAGS[verb]
    if verb == "commit" and _commit_lacks_the_template_shape(argv):
        return True
    # Every flag-shaped token is checked WHEREVER it sits. `--` used to end the flag check, but a
    # value-taking flag CONSUMES the next token: `git commit -m -- --amend` made `--` the message
    # and git read `--amend` as the flag it is — an amend fired on a pushed commit (pass 23,
    # P22-A, executed). Enumerating which flags take values is one more list to be wrong about;
    # a real file named `--hard` after `--` is refused instead, fail-closed.
    message_value_next = False
    for tok in argv[2:]:
        is_message_value, message_value_next = message_value_next, False
        if tok == "--":
            continue
        if tok.startswith("--"):
            if long_ok is not None and tok.split("=", 1)[0] not in long_ok:
                return True
            message_value_next = tok in ("--message", "--file")
        elif tok.startswith("-") and len(tok) > 1:
            if short_ok is not None and any(
                ch not in short_ok for ch in tok[1:].rstrip("0123456789")
            ):
                return True
            # git attaches whatever FOLLOWS the first value-taking letter as that letter's value:
            # `-mF` is `-m` with message "F", and the NEXT token is a pathspec — keying on the
            # LAST letter exempted `.` after `-mF` and a sibling's staged file was committed
            # (pass 27, P26-A, executed). Only a cluster that ENDS at its first m/F takes the
            # next token as the value.
            # …and "follows" includes DIGITS: `-m5` is message "5" — the digit strip that serves
            # the letter check must not run before this, or `-m5 . -- f` exempts the `.` and a
            # sibling's staged file is committed (pass 28, executed).
            cluster = tok[1:]
            first = min((cluster.find(ch) for ch in "mF" if ch in cluster), default=-1)
            message_value_next = verb == "commit" and first != -1 and first == len(cluster) - 1
        elif not is_message_value and _positional_forbidden(verb, tok):
            # the token after `-m`/`-F` is the MESSAGE, never a pathspec: `git commit -m 'fix *.py?'
            # -- f` was refused as a glob sweep (pass 24, pool finder). A flag-shaped message
            # (`-m --amend`) is still refused above — fail-closed, and git would read it the same way.
            return True
    return False


def _commit_lacks_the_template_shape(argv: list[str]) -> bool:
    """A held commit is exactly the exit the message orders: `git commit -m <msg> -- <paths>`.
    A bare `git commit -m x` committed a SIBLING's staged hunks (the whole index) and a
    `git commit -- f` without a message reached git and was saved only by its headless-editor
    refusal (pass 22, P21-A, both executed). So: a message flag AND `--` followed by at least one
    path, or the line is held."""
    try:
        dd = argv.index("--", 2)
    except ValueError:
        return True  # no `--`: no pathspec the template's way
    options, paths = (
        argv[2:dd],
        argv[dd + 1 :],
    )  # the FIRST `--`; a later flag is still checked by the caller
    # the message flag is looked for BEFORE `--` only: after it, `-m` is a path (pass 23 —
    # `git commit -- -m` passed the shape with `-m` counted as its own message)
    has_message = any(
        tok in ("--message", "--file")
        or tok.startswith(("--message=", "--file="))
        or (tok.startswith("-") and not tok.startswith("--") and ("m" in tok[1:] or "F" in tok[1:]))
        for tok in options
    )
    return not (has_message and paths)


def _positional_forbidden(verb: str, tok: str) -> bool:
    """A refspec that forces or names a destination, or a pathspec that sweeps instead of naming."""
    if verb in ("push", "fetch", "add", "commit", "reset") and ("$" in tok or "`" in tok):
        # an expansion INSIDE a positional token cannot be evaluated here and bash will: `git add
        # "./$FILES"` with `FILES='.'` normalised to `$FILES`, passed every literal check, and
        # staged a sibling's untracked file — add, commit and reset alike (pass 26, P25-A,
        # executed). A path or ref never legitimately carries `$` or a backtick; held outright.
        return True
    if verb == "push":
        return tok[:1] in (
            "+",
            ":",
        )  # `+ref` forces; `:ref` (empty source) deletes — `a:b` is a plain push
    if verb == "fetch":
        return tok.startswith("+") or ":" in tok  # `src:dst` writes a LOCAL ref; `+` forces it
    if verb in ("add", "commit", "reset"):
        # normalised, so `./`, `././`, `./../`, `docs/..` are seen for the `.`/`..` they are
        # (pass 22: `git add ./../` swept the parent past the literal list). `[` counts as a glob
        # because git reads `docs/[draft].md` as one — a real file so named is refused, by design.
        norm = posixpath.normpath(tok) if tok else "."
        return (
            norm in (".", "..")
            or norm.startswith("../")
            or any(ch in tok for ch in "*?[")
            or tok.startswith(":")
        )
    return False


# `(?!>)` after the optional second `>` and `>` in the lookbehind: without them `>>?` BACKTRACKED
# on `>> /dev/null` — the two-char match failed the /dev/null exemption, so the engine matched a
# single `>` whose lookahead saw `> /dev/null` and refused the very form the exemption names
# (review 2026-09-05, closing pass, found by execution; fail-closed, so it only over-refused).
_FILE_REDIRECT = re.compile(
    # The exemption is the DEVICE, not a prefix: `/dev/null` must be followed by whitespace,
    # end of line or a shell operator — `>/dev/nullx`, `>/dev/null/../x` and `>/dev/null.txt`
    # all matched the bare prefix and were allowed (review 2026-09-05, pass 12, executed).
    # `>&` is an fd DUPLICATION only when a digit or `-` follows (`2>&1`, `>&2`, `>&-`); `>&word`
    # is bash's "redirect stdout+stderr to FILE word" — proven by execution: `git log >&x` was
    # allowed and created `x` (review 2026-09-05, pass 12, native finder). The fd must be the
    # WHOLE token: `>&1x` opens a file named `1x`.
    r"(?<![0-9>])>>?(?!>)(?!\s*/dev/null(?![^\s;&|)]))(?!&(?:\d+|-)(?![\w.]))"
    r"|(?<!>)\d>>?(?!>)(?!\s*/dev/null(?![^\s;&|)]))(?!&(?:\d+|-)(?![\w.]))"
)


def _mask_quoted(command: str) -> str:
    """Blank shell-QUOTED spans so the vetoes above see OPERATORS, not DATA.

    They scan the raw line, so a `;` or `|` inside a quoted ARGUMENT reads as a control operator
    and refuses an otherwise-allowed command. Not hypothetical: the BLOCKED format CLAUDE.md
    mandates ("<what> - searched: <a>; <b> - missing: <need>") puts a semicolon in the `--reason`
    of the very `command_run.py blocked` call this hold's own message orders a held session to
    make, so the hold structurally refused its own graceful exit while the Stop hook blocked the
    turn for the record it could not close (trade-intelligence 01M1NTZJEHF9NY93JW8YZNDAVB;
    mechanism proven by fleet 01M1NTZZEZJGHKYR7VQF4PZAM2, who wrote the whole-line scan).

    Every existing tooth survives, because masking only removes characters the SHELL would not
    have acted on either:
      - single-quoted spans are masked whole - the shell expands nothing inside them;
      - double-quoted spans KEEP `$(`, a backtick and a `$` that OPENS the span (a whole-word
        expansion can be a flag), which the shell still runs or substitutes there, so
        `git status "$(rm -rf x)"` is still refused;
      - a backslash escape inside double quotes masks BOTH characters, since an escaped dollar
        or backtick is a literal rather than an expansion;
      - a newline is NEVER masked, quoted or not - a multi-line command stays refused;
      - an UNBALANCED quote returns the line untouched, so something that would not even parse
        meets the vetoes raw and fails closed.

    `shlex.split` is not a substitute: it returns ['git', 'status;evil'] for `git status;evil`,
    so a leading-word parse would ALLOW the chained bypass this masking still denies.
    """
    out: list[str] = []
    quote: str | None = None
    span_start = False  # True for the first character inside a double-quoted span
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        at_span_start, span_start = span_start, False
        if quote is None:
            if ch == "\\" and i + 1 < n:
                # OUTSIDE quotes a backslash makes the next character literal, whatever it is —
                # so `\'` is a quote CHARACTER, never a quote OPENER. Without this the first cut
                # of the masker toggled quote state on any bare quote, and a real operator
                # placed between two escaped single quotes was masked to data and ALLOWED:
                # `git status \'; rm -rf x\'` passed decide() and bash ran the second command
                # (review pass 1, native finder, proven by execution with a file side effect).
                # Both characters are kept visible: an escaped operator (`\;`) stays refused,
                # which is the pre-existing fail-closed the finder confirmed CLEAN.
                out.extend((ch, command[i + 1]))
                i += 2
                continue
            if ch in ("'", '"'):
                quote = ch
                span_start = True
            out.append(ch)
            i += 1
        elif ch == quote:
            quote = None
            out.append(ch)
            i += 1
        elif ch == "\n":
            out.append(ch)  # a quoted newline is still a refused multi-line command
            i += 1
        elif quote == '"' and ch == "\\" and i + 1 < n:
            # an escaped $ ` " or \ is a literal, not an expansion — but an escaped NEWLINE is a
            # line continuation bash REMOVES, so `"\<nl>$F"` reached git as `"$F"` while the masked
            # pair hid both the newline veto and the span-opening `$` (pass 26, pool finder,
            # executed): the newline stays visible and the multi-line veto holds.
            out.extend(("x", "\n" if command[i + 1] == "\n" else "x"))
            i += 2
        elif quote == '"' and (
            ch == "`"
            or (ch == "$" and i + 1 < n and command[i + 1] == "(")
            or (ch == "$" and at_span_start)
        ):
            # the shell RUNS `$(` and a backtick inside double quotes - keep them visible (the `(`
            # rides along: _UNSAFE_SHELL keys on the PAIR). A `$` that OPENS the span is kept too:
            # `"$F"` is one word, and one word can BE a flag - `git push origin "$F"` with
            # `F='--force'` made a forced update on a remote (pass 25, executed, twice) while shlex
            # saw `$F`; `git add "$X"` staged a sibling's file, `-- "$FILES"` swept one. A `$`
            # inside text (`"fix $X"`) is masked: that word starts with text and can never be
            # flag-shaped. (Pass 24 masked every quoted `$`; its claim that a quoted expansion
            # "cannot become a flag" was false for the whole-word form.)
            out.append(ch)
            i += 1
            if ch == "$" and i < n and command[i] == "(":
                out.append("(")
                i += 1
        else:
            out.append("x")
            i += 1
    return command if quote is not None else "".join(out)


def _state_dir() -> Path:
    return Path(os.environ.get("ROTATE_STATE_DIR") or Path.home() / ".claude" / "state")


def _stamp() -> Path:
    return _state_dir() / "fleet-exhausted"


def _tick_log() -> Path:
    return Path(
        os.environ.get("QUOTA_STOP_TICK_LOG") or Path.home() / ".claude" / "rotate-tick.log"
    )


def decide(
    tool: str,
    command: str | None,
    *,
    stamp_exists: bool,
    tick_age_s: float | None,
    now: float | None = None,
) -> tuple[str, str]:
    """Pure decision. Returns (action, reason) with action ∈ {"allow", "deny", "allow_warn"}."""
    if not stamp_exists:
        return "allow", ""
    stale_after = float(os.environ.get("QUOTA_STOP_TICK_STALE_S", "900"))
    if tick_age_s is None or tick_age_s > stale_after:
        return "allow_warn", (
            "quota-stop: the fleet-exhausted stamp exists but the rotation tick has not run for "
            f"{'unknown' if tick_age_s is None else f'{tick_age_s / 60:.0f}m'} — a stale flag never "
            "freezes the fleet; check `crontab -l` and ~/.claude/rotate-tick.log"
        )
    if tool == "Bash":
        # the vetoes read the MASKED line (operators only); the allow-list reads the RAW line,
        # because the leading command word is never quoted in a command we would allow.
        masked = _mask_quoted(command) if command is not None else ""
        if (
            command is not None
            and not _UNSAFE_SHELL.search(masked)
            and not _FILE_REDIRECT.search(masked)
            and not _git_flags_forbidden(command)
            and _ALLOWED_BASH.match(command)
        ):
            return "allow", ""
        return "deny", _reason("Bash")
    if tool in _READ_TOOLS or _READ_MCP.match(tool):
        return "allow", ""
    return "deny", _reason(tool or "tool")


def _reason(tool: str) -> str:
    return (
        f"FLEET QUOTA EXHAUSTED — no account left to rotate to (the tick's fleet-exhausted stamp is "
        f"set). {tool} is held. STOP GRACEFULLY NOW: commit your own work with explicit pathspecs "
        "(`git commit -m <msg> -- <paths>`), `git push`, close your run record (`command_run.py done|blocked`), "
        "then end the turn — no new edits, no new phases. Reads, git, command_run.py, mail.py and "
        "thread_anchor.py stay allowed. The hold lifts by itself when the tick sees relief (a reset "
        "or a new account); a session that ended is restarted by the operator."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # unreadable payload — never block on our own defect
    if not isinstance(payload, dict):
        return 0  # a non-object payload is not ours to judge — fail open (pass-2 probe: it raised)
    tool = str(payload.get("tool_name") or "")
    cmd = (
        (payload.get("tool_input") or {}).get("command")
        if isinstance(payload.get("tool_input"), dict)
        else None
    )
    try:
        exists = _stamp().exists()
    except OSError:
        exists = False
    age: float | None
    try:
        age = time.time() - _tick_log().stat().st_mtime
    except OSError:
        age = None
    action, reason = decide(
        tool, cmd if isinstance(cmd, str) else None, stamp_exists=exists, tick_age_s=age
    )
    if action == "deny":
        # ONLY the current PreToolUse contract: the installed CLI (2.1.258) deprecates the legacy
        # `decision` key here — "PreToolUse, use hookSpecificOutput.permissionDecision instead".
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    },
                }
            )
        )
    elif action == "allow_warn":
        sys.stderr.write(reason + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
