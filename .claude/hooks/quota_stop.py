#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, docs/workstation/claude-account-rotation.md, scripts/fabrik_synced_manifest.py, tests/test_quota_stop_hook.py
"""PreToolUse — the fleet-wide GRACEFUL STOP when the quota is exhausted with nothing to rotate to.

Operator rule (2026-09-02): broadcast only when there is NO account left to rotate to and agents
are about to hit the wall — and then every agent must stop gracefully, losing no work, ready to be
restarted. Mail reaches a session only at its next prompt; this hook reaches it at its next TOOL
CALL, which is the only moment a mid-turn agent can be stopped.

Signal: the rotation tick's exhaustion stamp (`<state>/fleet-exhausted`), written by
`claude_rotate.py::_fleet_active_wall_advisory` when the ACTIVE account is walled — OR its SESSION
window is at `ROTATE_URGENT_DRAIN_PCT` — and the picker found no validated successor (or the
operator paused rotation), and unlinked by the same tick the moment relief arrives (a flip or a
reset). THREE functions in `claude_rotate.py` write it — `_fleet_active_wall_advisory` (the
episode's first write), `_rearm_wall_stamp` (rebuilds it from the episode's ledger row) and
`_upgrade_stamp_tier_to_walled` (raises the tier when an episode escalates) — and THREE readers act
on it: this hook, `scripts/sysadmin/quota_posture_hook.py` (which stands down only at the `walled`
tier), and `claude_rotate.py` itself, whose picture turns the tier into the WALL band.

⚠️ THE STAMP CARRIES TWO TIERS AND ONLY ONE OF THEM HOLDS (D-306). Its second line names which
arm armed it. `walled` is the wall itself — a window at/over `ROTATE_THRESHOLD`, its `caps.json`
cap, or 100. `urgent-90` is the SESSION window at `ROTATE_URGENT_DRAIN_PCT` (90) with no
validated successor: NINE points of runway remain on the default `ROTATE_THRESHOLD` of 99. That
gap is on the SESSION window alone — `urgent` tests `five_hour` and a `caps.json` cap is applied
to `seven_day`, so a cap never shortens it; it walls the weekly window on its own axis and can
open an episode at `walled` outright. That runway is the whole reason the
arm exists (D-111). Holding EVERY session there killed in-flight subagents with quota still on the
clock — the premature stop the operator's "utilize quotas utmost" directive forbids (D-299) — but
allowing every session gave the last points to whoever asked first (D-1113). So the warning tier
is the LANE (W-18f559d9): `lane_exempt` lets the bound merge owner of a coordinator_mode repo and
the bound owner of an open P0 item continue with a nudge, and PARKS every other session with the
wall's allow-list plus the finishing verbs (`merge_request.py request`, `work.py
claim|release <W-id>`, SubagentHandback, SendMessage) and a park message naming its claimed items
and the lift time; `final_gate_stop.py` loads `lane_exempt` from this file for its urgent branch.
The wall tier holds everyone. A stamp that does not plainly name a
tier (every stamp written before this field, or an unreadable one) is read as `walled`: the
unknown case must never be the lenient one, because the lenient reading drops the fleet's only
hard stop at a real wall.

While the stamp stands the rule is DEFAULT-DENY: every tool that can change the world is held —
Edit/Write/MultiEdit/NotebookEdit, MCP editors (serena replace/insert/rename, browser clicks),
Agent/Workflow dispatch, and any Bash that is not ONE simple checkpoint or read command — with one instruction — commit + push your own work with
explicit pathspecs, close your run record, stop. Reads (the Read, Grep and Glob tools, and Bash cat, head, tail, grep, ls, wc and stat), the git checkpoint and read verbs with their plain flags (add -- <paths>, commit -m <msg> -- <paths>, push, fetch, status, diff, log, show, rev-parse and reset HEAD -- <paths>; through git -C /opt/<repo>, the read verbs only), `command_run.py`, `mail.py`,
`thread_anchor.py`, `Monitor`, the exact self-watch arm (`bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh <sid>`,
D-356), the pause's exact verbs (`python3 /opt/fabrik/scripts/sysadmin/hibernate.py status|woke|paused|lift`) and
`TaskStop` stay allowed, so a session can finish
cleanly and the Stop hook's commit-and-push law can be met. The block lifts when the tick clears the
stamp; the lift WAKES every ARMED self-watch (D-178) — an unarmed ended session waits for the operator.

FAIL-OPEN, deliberately: no stamp → allow; unreadable state → allow; a stamp older than the tick
could have refreshed (the tick log has not moved for QUOTA_STOP_TICK_STALE_S, default 900s) →
allow with a one-line warning, because a dead cron must never freeze the fleet behind a stale
flag. ROTATE_STATE_DIR is honored (the tick's own override) so tests never touch the real stamp.

THE ONE EXCEPTION TO THAT FAIL-OPEN — the `hibernate` tier (W-6e656dac, spec L2): a stamp whose raw line 2 reads
`hibernate` while the pause marker (`hibernate.json`, read INLINE — this file imports no hub module) is marked and not
lifted holds however old the tick log is, or with none at all, because a box that slept for days wakes with exactly
that log and the minutes before its first tick must stay held. The cheapest way past it (D-253) is a marker that
reads as lifted or unreadable: an unreadable marker reads as UNMARKED here (this hook fails open), so the dead-cron
fail-open returns — that cost is named, and the tick's own lift or the hub's `hibernate.py lift` is the real exit.
"""

from __future__ import annotations

import json
import math
import os
import posixpath
import pwd
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
    "TaskStop",  # stopping a background task never changes the world — and under the hold it is
    # the one way a held session stops its own native subagent from burning the quota the hold
    # is protecting (measured denied 2026-09-07 01:24; plan 2026-09-07-plan-1-relief-wake, D-177)
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
    r"^\s*(git\s+(add|commit|push|status|diff|log|fetch|show|rev-parse)(?!-)\b"  # (?!-): `commit-tree`/`diff-tree`/`show-ref` rode the verb's \b (F5)
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
    # the self-watch arm (D-356), EXACT form: the hold's lift wakes only an armed session, so an unarmed
    # one must be able to arm while held; the wrapper only reads marker files and prints one line
    # — the sid class is `_reason`'s own (1–80, alnum and `._-`): every order the hold prints must be one it allows
    r"|bash\s+/opt/fabrik/scripts/sysadmin/selfwatch_arm\.sh\s+[A-Za-z0-9._-]{1,80}\s*$"
    # the pause's own verbs (W-6e656dac, spec L2), EXACT forms beside the arm's: `status`, `woke` and `paused` only
    # read, each with exactly the arguments its argparse takes — `status` [--json] [--self <sid>] in either order,
    # `woke` [--self <sid>], `paused` bare — never `--home`/`--proc`, the test seams; a sid never starts with `-`
    # (argparse would read it as a flag). `lift` takes no argument at all; who may lift is `hibernate.py`'s own
    # caller check, never this hook's
    r"|python3\s+/opt/fabrik/scripts/sysadmin/hibernate\.py\s+(?:"
    r"status(?:\s+--json(?:\s+--self\s+[A-Za-z0-9._][A-Za-z0-9._-]{0,79})?"
    r"|\s+--self\s+[A-Za-z0-9._][A-Za-z0-9._-]{0,79}(?:\s+--json)?)?"
    r"|woke(?:\s+--self\s+[A-Za-z0-9._][A-Za-z0-9._-]{0,79})?"
    r"|paused|lift)\s*$"
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
    # …and each ends at a blank or the end, never at `\b`: `\b` holds before `-`, so `ls-evil` and
    # `cat-evil` — any planted program on PATH — matched (W-945bf009 review, pass 1, executed)
    r"|(cat|head|tail|grep|ls|wc|md5sum|readlink|echo|pwd|stat)(?=\s|$))"
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
# Whitespace Python's `\s` matches and bash does NOT split words on (U+00A0, U+2028, 0x0B-0x1F…):
# every pattern here reads `\s`, so `git<NBSP>log push --force` looked like `git log` while bash
# ran one unknown word — and stripped, a `-C /opt/x<NBSP>log` prefix left a push (W-945bf009, both
# design critiques, executed). Outside quotes only space, tab and newline are blanks.
_NOT_A_BLANK = re.compile(r"[^\S \t\n]")
# Unquoted BRACE EXPANSION turns one token into several before the command runs: `git push origin
# {+,}master` is a FORCE push (`+master master`), `git add {.,}` a sweep — while shlex hands every
# check one literal word (W-945bf009 review, pass 1, executed on base and new alike). Only the
# expanding shapes, a `,` or `..` inside, are refused: `@{u}` and `HEAD^{tree}` stay git syntax.
# No whitespace stops the match: an ESCAPED blank (`{+,\ }master`) is one word to bash and still
# expands — a force push again (pass 2, executed). Every expansion is refused, the harmless ones
# too (`git add -- a{1..3}.py`, `ls {a,b}`): judging which expansions are safe is the negative
# list this file abandoned at pass 19, so a held session writes its paths out instead.
_BRACE_EXPANSION = re.compile(r"\{[^}]*(?:,|\.\.)[^}]*\}")
# The RESOLVER (W-945bf009). A held session reads another checkout with `git -C <repo>`, goes back
# to its own root with `cd <root> &&`, and gives `mail.py send` a MULTI-LINE body on stdin — a
# here-string carries one line (a quoted newline is the multi-line veto), a file redirect is vetoed
# — and the start-anchored allow-list refused all three. Relaxing the
# anchor alone re-opened a force push, so each prefix is STRIPPED here, by a grammar this file
# owns, and every veto then judges what is left. A shape outside the grammar is left in place and
# the anchored allow-list refuses it: every unknown fails CLOSED.
#   `-C <repo>`: `/opt/<name>` or `/opt/<name>/.claude/worktrees/<name>`, the trust the absolute
#     `scripts/` anchor already grants; the segment is RELOCATED and may only read (a commit in
#     another repo is a HARD STOP this hook cannot otherwise see).
#   `cd <dir>`: only to the session's OWN repo root. The Bash tool's working directory persists
#     between calls, so a `cd` anywhere else would carry the next, un-relocated `git commit` into
#     another repo; a `cd` home is not a relocation and every rule applies as without it. The
#     target is resolved as bash's LOGICAL `cd` does — `..` drops the previous component of the
#     path as written, never of its symlink target — and must be absolute or start `./`, `../` (or
#     be `.`/`..`), the only names bash never looks up in CDPATH (a hidden `.x` is searched too) (W-945bf009 review, pass 1: through a symlinked
#     component, the physical realpath named home while bash landed in another repo, executed).
_REPO_DIR = r"/opt/[\w-][\w.-]*(?:/\.claude/worktrees/[\w-][\w.-]*)?/?"
_CD_PREFIX = re.compile(
    r"^[ \t]*cd[ \t]+((?:/|\.\.?/)[\w./-]*|\.\.?)[ \t]*(?:&&|;)[ \t]*", re.ASCII
)
_GIT_RELOCATE = re.compile(rf"^([ \t]*git)(?:[ \t]+-C[ \t]+{_REPO_DIR}(?=[ \t]))+", re.ASCII)
_RELOCATED_WRITE = re.compile(r"^[ \t]*git[ \t]+(add|commit|push|fetch|reset)(?!-)\b", re.ASCII)
# The one pipe: a body producer into `mail.py send`. Nothing else may pipe.
_PIPE_PRODUCER = re.compile(r"^[ \t]*(printf|echo)(?=[ \t]|$)", re.ASCII)
_PIPE_MAIL = re.compile(
    r"^[ \t]*python3?(?:\.\d+)?[ \t]+(?:/opt/[\w-][\w.-]*/)?scripts/mail\.py[ \t]+send(?=[ \t]|$)",
    re.ASCII,
)


def _own_root(cwd: str | None) -> str | None:
    """The session's repo root: the nearest ancestor of `cwd` holding a `.git` entry (a directory,
    or a linked worktree's file), realpath'd; None when there is no `cwd` or no repo above it."""
    if not cwd or not os.path.isabs(cwd):
        return None
    try:
        here = Path(os.path.realpath(cwd))
        for d in (here, *here.parents):
            if os.path.lexists(d / ".git"):
                return str(d)
    except (OSError, ValueError):
        return None
    return None


def _resolve(command: str, cwd: str | None) -> tuple[list[str], bool]:
    """(segments, relocated): the line with ONE leading `cd <own root> &&|;` and every `git -C
    <repo>` stripped, split at its single top-level `|`. Two or more pipes, or `||`, leave the line
    whole for `_UNSAFE_SHELL` to refuse; an escaped `\\|` splits into a half ending in a lone
    backslash, which shlex cannot parse, so `_git_flags_forbidden` refuses it. `_mask_quoted` keeps
    one character per character, so a `|` found on the masked line splits the raw line there."""
    rest = command
    m = _CD_PREFIX.match(command)
    if m and cwd and (root := _own_root(cwd)) is not None:
        try:
            if os.path.realpath(os.path.normpath(os.path.join(cwd, m.group(1)))) == root:
                rest = command[m.end() :]
        except (OSError, ValueError):
            pass
    masked = _mask_quoted(rest)
    pipes = [i for i, ch in enumerate(masked) if ch == "|"]
    if len(pipes) == 1 and len(masked) == len(rest):
        segments = [rest[: pipes[0]], rest[pipes[0] + 1 :]]
    else:
        segments = [rest]
    relocated = False
    out = []
    for seg in segments:
        stripped = _GIT_RELOCATE.sub(r"\1", seg, count=1)
        relocated = relocated or stripped != seg
        out.append(stripped)
    return out, relocated


def _segment_allowed(segment: str, pattern: re.Pattern[str]) -> bool:
    masked = _mask_quoted(segment, commit_body=segment.lstrip().startswith("git commit "))
    return bool(
        segment.strip()
        and not _UNSAFE_SHELL.search(masked)
        and not _FILE_REDIRECT.search(masked)
        and not _git_flags_forbidden(segment)
        and pattern.match(segment)
    )


def _bash_allowed(command: str, cwd: str | None = None) -> bool:
    masked = _mask_quoted(command)
    if _NOT_A_BLANK.search(masked) or _BRACE_EXPANSION.search(masked):
        return False
    segments, relocated = _resolve(command, cwd)
    if len(segments) == 2:
        return _segment_allowed(segments[0], _PIPE_PRODUCER) and _segment_allowed(
            segments[1], _PIPE_MAIL
        )
    (only,) = segments
    if relocated and _RELOCATED_WRITE.match(only):
        return False
    return _segment_allowed(only, _ALLOWED_BASH)


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
    if not argv or not argv[0].startswith("git"):
        return False
    if argv[0] != "git" or len(argv) < 2 or argv[1] not in _GIT_VERB_FLAGS:
        # Fail CLOSED on any git line whose verb is not one this check knows. It returned False
        # here, leaving the anchored allow-list as the only guard: `git -C /opt/fabrik push
        # --force` read `-C` as an unknown verb and the veto passed a force push — and
        # `git<NBSP>log` is one shlex word `bash` never runs as git (W-945bf009, executed).
        return True
    verb = argv[1]
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


def _mask_quoted(command: str, commit_body: bool = False) -> str:
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
      - a newline is never masked, quoted or not (a multi-line command stays refused) - EXCEPT inside a quoted span (either quote) of a `git commit` line (`commit_body`), the -m body's paragraph break the provenance trailers need (fleet 01M1W6KVH7Y0HQMQ9W3QTXDM7V);
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
            out.append(
                "x" if commit_body else ch
            )  # a quoted newline is the multi-line veto — except inside a git commit's quoted -m body (either quote: data to the shell)
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


# COPIED from `claude_rotate.py` (`_STAMP_TIERS`/`_stamp_tier`) — this hook is fleet-synced and
# imports nothing from the tick. `test_the_hooks_tier_reader_agrees_with_the_tick_that_writes_it`
# grades the two copies against the same bytes, including every fail-closed shape; the four-way
# graders in `tests/test_quota_posture.py` add `quota_posture_hook.py` and `final_gate_stop.py`.
_STAMP_TIER_WALLED = "walled"
_STAMP_TIER_URGENT = "urgent-90"
_STAMP_TIERS = frozenset({_STAMP_TIER_WALLED, _STAMP_TIER_URGENT})


def _stamp_tier(stamp: Path) -> str:
    """Which arm wrote this stamp — line 2. `walled` for anything not plainly saying otherwise:
    missing, unreadable, pre-tier (one numeric line), or a tier this version does not know."""
    try:
        # `is_file()` BEFORE the read: a FIFO at this path blocks forever, a hang is not an
        # OSError, and a PreToolUse hook that never returns stalls every tool call in the session
        # (executed: exit 124 under `timeout 5`; the pre-D-306 hook only called `.exists()`).
        # `.split("\n")`, never `.splitlines()` — the latter also breaks on VT/FF/FS/GS/RS/NEL/
        # U+2028/U+2029, so a control byte in line 1 shifted the read and a `walled` stamp was
        # allowed through as `urgent-90`: lenient, the one direction this reader must never be.
        if not stamp.is_file():
            return _STAMP_TIER_WALLED
        # `newline=""` disables UNIVERSAL-NEWLINE translation, without which Python turns a bare
        # `\r` in line 1 into a line break on read and line 2 shifts — the same class as the
        # control characters above, arriving through the reader instead of through `splitlines()`.
        with stamp.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return _STAMP_TIER_WALLED
    tier = lines[1].strip() if len(lines) > 1 else ""
    return tier if tier in _STAMP_TIERS else _STAMP_TIER_WALLED


def _stamp_is_battery(stamp: Path) -> bool:
    """The battery hold's stamp (W-83a8ee68, D-898): line 2 is `battery`. `_stamp_tier` folds it
    into `walled` — an unknown tier holds — so the DECISION never changes on it; this read only
    picks the message. The same raw read as `_stamp_tier` (`is_file()` first, `newline=""`)."""
    try:
        if not stamp.is_file():
            return False
        with stamp.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return False
    return len(lines) > 1 and lines[1].strip() == "battery"


# The credentials that may outrank or replace `ANTHROPIC_API_KEY` (W-effb7141): any one of them
# set beside the key holds the session. COPIED in `scripts/sysadmin/quota_posture_hook.py`.
_OTHER_AUTH = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
)


def _api_key_session() -> bool:
    """A session on an Anthropic API key draws no PLAN quota, so the plan's wall and lane must not
    hold it (W-effb7141). Today that is an interactive window the operator launches by hand with
    `ANTHROPIC_API_KEY` in its env — the `scripts/api_credit.py` children run `--safe-mode`, which
    disables hooks, so this file never runs there. Read from THIS process's env, which the hook
    inherits from the claude process — a Bash-tool `export` never reaches it.
    Any `_OTHER_AUTH` variable beside the key — a plan OAuth token, a bearer `ANTHROPIC_AUTH_TOKEN`,
    or a Bedrock/Vertex/Foundry switch — means another credential may be the one in use, so the
    session is HELD: unknown billing, fail-closed (any non-blank value counts as set). Only the
    env is read, never settings: a session whose sole credential is an `apiKeyHelper` has no env
    key and is held; one with the key in its env too is judged on the key. Extend `_OTHER_AUTH`
    if another route is ever launched on this box. COPIED in `scripts/sysadmin/quota_posture_hook.py`;
    `final_gate_stop.py` loads `api_key_exempt` from here. Cobra: a dummy key at launch passes this
    check, but Claude Code then authenticates with that key and every request fails — only a real
    paid key gets work through. Mirror: a key the interactive "use this API key?" prompt was told
    NOT to use leaves the window on its plan login while this check exempts it; reading Claude
    Code's own approval store to close that was rejected (undocumented internal state, absent from
    the active config — D-row). The prompt line's clause (`quota_posture_hook.py`) names the
    exemption to the session; the stderr note here reaches the verbose transcript only."""
    return bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip()) and not any(
        (os.environ.get(name) or "").strip() for name in _OTHER_AUTH
    )


def api_key_exempt(stamp: Path) -> bool:
    """True when a hold this stamp would place does not bind this session: an API-key session
    (`_api_key_session`) and a stamp whose line 2 PLAINLY reads one of the two quota tiers. The
    battery tier (D-898) and the hibernate tier (W-6e656dac) protect the box, not plan quota, and
    every other line 2 — pre-tier,
    unknown, unreadable — holds: the unknown case is never the lenient one. The same raw read as
    `_stamp_tier` (`is_file()` first, `newline=""`, `split("\n")`)."""
    if not _api_key_session():
        return False
    try:
        if not stamp.is_file():
            return False
        with stamp.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return False
    return len(lines) > 1 and lines[1].strip() in _STAMP_TIERS


def _stamp_is_hibernate(stamp: Path) -> bool:
    """The hibernate tier's stamp (W-6e656dac, Interface S): line 2 is `hibernate`. Like `battery` it is NEVER added
    to `_STAMP_TIERS` — `_stamp_tier` folds it into `walled`, so it holds — and this raw read only picks the message
    and whether a stale tick may open it. The same raw read as `_stamp_tier` (`is_file()` first, `newline=""`)."""
    try:
        if not stamp.is_file():
            return False
        with stamp.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return False
    return len(lines) > 1 and lines[1].strip() == "hibernate"


def _marker_path() -> Path:
    """The pause marker, resolved as `hibernate.py` resolves it (Interface M): `$ROTATE_STATE_DIR/hibernate.json` when
    set, else `<passwd home>/.claude/state/hibernate.json` — the passwd home, never `$HOME`."""
    raw = os.environ.get("ROTATE_STATE_DIR")
    if raw:
        return Path(raw) / "hibernate.json"
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".claude" / "state" / "hibernate.json"


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def _pause_marked() -> bool:
    """True exactly when `hibernate.py paused` would exit 0: a readable JSON object whose `paused_at` is a finite
    number, whose `lifted_at`/`deadline_at` are absent, null or finite numbers, and which is not lifted
    (`lifted_at >= paused_at`). Every other shape — no file, a corrupt one, a FIFO — is UNMARKED: this hook fails
    open. COPIED (not imported) into `quota_posture_hook.py`; `tests/test_hibernate_hooks.py` grades both copies
    against `paused` on the same bytes.

    The WHOLE body is inside `except Exception`: a 400-digit int overflows `float()` and deep nesting raises
    RecursionError in `json.loads`, and a hook that crashes exits 1, which the harness reads as non-blocking, so the
    hold itself opened (review J1, executed). A marker this reader cannot judge is UNMARKED — never a crash."""
    try:
        p = _marker_path()
        if not p.is_file():  # before the read: a FIFO blocks forever, and a hang is not an OSError
            return False
        m = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(m, dict):
            return False
        at = _finite(m.get("paused_at"))
        if at is None:
            return False
        for key in ("lifted_at", "deadline_at"):
            if m.get(key) is not None and _finite(m[key]) is None:
                return False
        lifted = _finite(m.get("lifted_at"))
        return lifted is None or lifted < at
    except Exception:
        return False


def _tick_log() -> Path:
    return Path(
        os.environ.get("QUOTA_STOP_TICK_LOG") or Path.home() / ".claude" / "rotate-tick.log"
    )


def _stale_after_s() -> float:
    """QUOTA_STOP_TICK_STALE_S, or 900 when it is garbage or non-finite. An unguarded `float()`
    here died with a traceback on EVERY tool call in every synced repo for a typo'd value
    (closing review P3-5), and a NaN bound made `tick_age_s > stale` False forever — a dead
    cron froze the fleet, the opposite of the documented direction (P3-6)."""
    raw = os.environ.get("QUOTA_STOP_TICK_STALE_S", "900")
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 900.0
    return v if math.isfinite(v) else 900.0


# ── THE LANE (W-18f559d9, D-1113) ──────────────────────────────────────────────────────────────
# Past 90% of the 5-hour window with nothing to rotate to, D-306 let every session spend the last
# points, so they went to whoever asked first and the sessions that merge and keep the records had
# none left. At `urgent-90` the lane holds every session EXCEPT (a) the bound merge owner of a
# coordinator_mode repo and (b) the bound owner of an open P0 item; a held session keeps the wall's
# allow-list plus the finishing verbs below. Every doubt is NOT exempt (held — it can still commit,
# push, mail and close, and the wall stays the safety net); a hook timeout fails OPEN (Claude Code
# runs the tool), so the one subprocess runs under `_LANE_TIMEOUT_S` and only when (a) can pass.
# Identity comes from the identity store ONLY (whoami_agent.py's format, read here — this hook is
# fleet-synced and imports nothing from scripts/), scoped to THIS repo's git common dir; CLAUDE_AGENT
# is never read, so a `claude -p` child inheriting a coordinator's env is held (ruling 2).
# ⚠️ COBRA (D-253): the cheapest way past the lane is to bind a session as the merge owner
# (`whoami_agent.py --as coordinator --force`) or to give yourself a P0 — both are same-user acts
# the store and the item files already record (a forced bind writes `force: true`, an item names its
# owner); the coordinator assigns P0, rarely (ruling 1). A held session may run the re-bind ONLY to
# the name its own claude process held last in this repo (`_same_window_name`, W-cff56c52): a
# `/clear` rotation mints a new sid in the same process and its first act is that re-bind, which
# the lane otherwise held until the lift. The identity store was already the trust root — a planted
# row for a session's own sid exempts it through `_bound_name` with no verb at all — so the
# re-bind adds no new way past the lane; a builder still cannot take another window's name.
# Known costs, stated not fixed: an exempt session's native subagents share its sid and are exempt
# too; the owner cache is same-user writable, no new trust boundary.
_LANE_TIMEOUT_S = 2.0
_HUB_DECISIONS_PY = "/opt/fabrik/scripts/decisions.py"  # the Stop hook's `_MERGE_OWNER_ARGV` copy
_LANE_CACHE_MAX = 64
_LANE_READ_MAX = 8 * 1024 * 1024
# whoami_agent.py `_NAME_RE` (fullmatch): a name outside it is never a binding
_AGENT_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")
_ITEM_ID_RE = re.compile(r"W-[0-9a-f]{8}")
# The finishing verbs, the LANE's alone (never the wall's): send the merge request for finished
# work, and renew or release a claim. Same anchors as `_ALLOWED_BASH`'s `scripts/` branch, and
# anchored at the END too: an open tail admitted `work.py claim <id> --session <another sid>`,
# `--repo /etc` and a second id (review round 1 F4, executed). `request` takes only the three
# options its argparse defines (`--review`, `--item`, `--base`), each value a plain word that is
# not an option; `merge_request.py` has no `send` verb (F3).
_LANE_VALUE = r"[\w./@+~][\w./@+~:-]*"
_LANE_BASH = re.compile(
    r"^[ \t]*python3?(?:\.\d+)?[ \t]+(?:/opt/[\w-][\w.-]*/)?scripts/"
    rf"(?:merge_request\.py[ \t]+request(?:[ \t]+--(?:review|base)[ \t]+{_LANE_VALUE}"
    r"|[ \t]+--item[ \t]+W-[0-9a-f]{8})*"
    r"|work\.py[ \t]+(?:claim|release)[ \t]+W-[0-9a-f]{8}"
    r"|work\.py[ \t]+next)[ \t]*\Z",
    re.ASCII,
)
# The rotation's re-bind (D-1119, D-1123), in the ONE shape the ROTATE line and the rotation prompt
# print: the hub's absolute path, exactly one `--as <name>`, at most one `--force` before or after.
# whoami's argparse is lenient (`--as=`, `--a`, `--f` and a repeated `--as`, last wins, all parse —
# executed by both W-cff56c52 critique seats), so every other spelling stays held.
_LANE_REBIND_NAME = r"[a-z0-9][a-z0-9-]{0,31}"
_LANE_REBIND = re.compile(
    r"^[ \t]*python3?(?:\.\d+)?[ \t]+/opt/fabrik/scripts/whoami_agent\.py[ \t]+"
    rf"(?:--force[ \t]+--as[ \t]+(?P<a>{_LANE_REBIND_NAME})"
    rf"|--as[ \t]+(?P<b>{_LANE_REBIND_NAME})(?:[ \t]+--force)?)[ \t]*\Z",
    re.ASCII,
)
# tools a parked session still needs to finish: a subagent's hand-back is text, and a merge
# request is finished by the SendMessage lines `merge_request.py request` prints
_LANE_TOOLS = frozenset({"SubagentHandback", "SendMessage"})


def _lane_bash_allowed(command: str, cwd: str | None = None) -> bool:
    """The finishing verbs, under every veto `_bash_allowed` applies to one segment."""
    masked = _mask_quoted(command)
    if _NOT_A_BLANK.search(masked) or _BRACE_EXPANSION.search(masked):
        return False
    segments, _relocated = _resolve(command, cwd)
    return len(segments) == 1 and _segment_allowed(segments[0], _LANE_BASH)


def _lane_rebind_allowed(command: str, cwd: str | None, rebind: str) -> bool:
    """The re-bind to `rebind` — the name `_same_window_name` resolved for this window — under the
    same vetoes; "" (no name resolved) allows nothing."""
    if not rebind:
        return False
    masked = _mask_quoted(command)
    if _NOT_A_BLANK.search(masked) or _BRACE_EXPANSION.search(masked):
        return False
    segments, _relocated = _resolve(command, cwd)
    if len(segments) != 1 or not _segment_allowed(segments[0], _LANE_REBIND):
        return False
    m = _LANE_REBIND.match(segments[0])
    return m is not None and (m.group("a") or m.group("b")) == rebind


def _regular_text(path: Path) -> str | None:
    """A REGULAR file's text (bounded), else None — a FIFO here would hang every tool call."""
    try:
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.read(_LANE_READ_MAX)
    except OSError:
        return None


def _git_common(start: Path) -> Path | None:
    """The git COMMON dir of the repo holding `start`, by a filesystem walk (no git subprocess on
    the per-tool path): a `.git` directory IS the common dir; a linked worktree's `.git` FILE names
    its gitdir, whose `commondir` file (or `<common>/worktrees/<n>` layout) names the common dir.
    None on anything else — a `.git` that is neither, an unreadable one, no repo above `start`."""
    try:
        for d in (start, *start.parents):
            dot = d / ".git"
            if dot.is_dir():
                return Path(os.path.realpath(dot))
            if not os.path.lexists(dot):
                continue
            text = _regular_text(dot)
            if text is None or not text.startswith("gitdir:"):
                return None
            gd = Path(text.split("\n", 1)[0][len("gitdir:") :].strip())
            gd = Path(os.path.realpath(gd if gd.is_absolute() else d / gd))
            cd = _regular_text(gd / "commondir")
            if cd is not None and cd.strip():
                rel = Path(cd.strip())
                return Path(os.path.realpath(rel if rel.is_absolute() else gd / rel))
            if gd.parent.name == "worktrees":
                return gd.parent.parent
            return None
    except (OSError, ValueError):
        return None
    return None


def _lane_project_dir(cwd: str | None = None) -> str | None:
    """The repo the lane judges: CLAUDE_PROJECT_DIR, else this hook's own repo, else the payload
    cwd — the first that sits in a git repo. Never the cwd first: a coordinator's seats work in
    scratch directories, and judging the scratch would hold the coordinator."""
    here = Path(__file__).resolve()
    for cand in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        str(here.parents[2]) if len(here.parents) > 2 else None,
        cwd,
    ):
        if cand and os.path.isabs(cand) and _git_common(Path(cand)) is not None:
            return cand
    return None


def _scoped_rows(common: Path) -> list[dict]:
    """The identity store's rows scoped to `common`, in file order, each with a valid name.
    `$AGENT_IDENTITY_FILE` else `$HOME/.claude/state/agent-identity.jsonl` (whoami_agent.py
    `store_path`); a corrupt line or a malformed name is skipped, as `resolve_agent_name` does."""
    raw = os.environ.get("AGENT_IDENTITY_FILE")
    store = Path(raw) if raw else Path.home() / ".claude" / "state" / "agent-identity.jsonl"
    text = _regular_text(store)
    if not text:
        return []
    want = os.path.realpath(common)
    real: dict[str, str] = {}  # one realpath per distinct scope: this runs on every parked call
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        top = row.get("toplevel")
        if not (isinstance(top, str) and os.path.isabs(top)):
            continue
        if top not in real:
            real[top] = os.path.realpath(top)
        if real[top] == want and _AGENT_NAME_RE.fullmatch(str(row.get("name") or "")):
            out.append(row)
    return out


def _bound_name(sid: str, common: Path) -> str:
    """The LAST valid binding for `sid` scoped to `common` in the identity store, or ""."""
    if not sid:
        return ""
    name = ""
    for row in _scoped_rows(common):
        if row.get("session_id") == sid:
            name = str(row["name"])
    return name


def _as_int(value: object) -> int | None:
    """whoami_agent.py `_as_int`: a stored pid or start time as an int — a digit string counts, a
    bool never does (`True == 1` would make a corrupted row equal pid 1)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _proc_start(proc: Path, pid: int) -> int | None:
    """Field 22 of `<proc>/<pid>/stat` (whoami_agent.py `_pid_start`), or None."""
    raw = _regular_text(proc / str(pid) / "stat")
    if raw is None:
        return None
    try:
        return int(raw[raw.rindex(")") + 1 :].split()[19])
    except (ValueError, IndexError):
        return None


def _claude_ancestor(proc: Path) -> int | None:
    """This hook's nearest `<proc>` ancestor named `claude` (whoami_agent.py `_session_pid`'s walk,
    12 hops), or None."""
    pid = os.getpid()
    for _ in range(12):
        status = _regular_text(proc / str(pid) / "status")
        if status is None:
            return None
        name, ppid = "", 0
        for line in status.splitlines():
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("PPid:"):
                try:
                    ppid = int(line.split(":", 1)[1].strip() or 0)
                except ValueError:
                    return None
        if name == "claude":
            return pid
        if ppid <= 1:
            return None
        pid = ppid
    return None


def _same_window_name(common: Path, cwd: str | None, proc_root: str | Path | None = None) -> str:
    """The name THIS window may re-bind at the lane (W-cff56c52), or "" — every doubt is "".

    This window is the `claude` process above this hook (pid AND start tick, D-748's process key —
    a `/clear` keeps the process and mints a new sid). The name is that process's LAST in-scope row
    when: `CLAUDE_PID` is unset or names that pid (a nested claude never reaches an outer window,
    whoami_agent.py `same_window`); it is also the LAST in-scope row of that name (nobody re-took
    it since); no OTHER row of the name belongs to a LIVE process (`--force` would override a live
    holder); and the payload `cwd` sits in this repo (whoami writes the cwd's scope). NO boot-time
    test (W-a77742db): WSL2's btime moves FORWARD with each host sleep (69,421 s measured on
    2026-10-28), so `at >= btime` came to refuse a live window's own row; a past boot's row
    matches only with the same pid AND the same start jiffy (D-1079 rejected boot tests already).
    A session resumed into a new process gets its row here from whoami's `refresh()` at
    SessionStart. `proc_root` (env `QUOTA_STOP_PROC_ROOT`, default /proc) is the test seam."""
    proc = Path(proc_root or os.environ.get("QUOTA_STOP_PROC_ROOT") or "/proc")
    if not cwd or not os.path.isabs(cwd):
        return ""
    here = _git_common(Path(cwd))
    if here is None or os.path.realpath(here) != os.path.realpath(common):
        return ""
    pid = _claude_ancestor(proc)
    start = _proc_start(proc, pid) if pid else None
    if pid is None or start is None:
        return ""
    claude_pid = (os.environ.get("CLAUDE_PID") or "").strip()
    if claude_pid not in ("", str(pid)):
        return ""

    def mine(row: dict) -> bool:
        return _as_int(row.get("pid")) == pid and _as_int(row.get("pid_start")) == start

    rows = _scoped_rows(common)
    last = None
    for row in rows:
        if mine(row):
            last = row
    if last is None:
        return ""
    name = str(last["name"])
    of_name = [r for r in rows if str(r["name"]) == name]
    if of_name[-1] is not last:
        return ""
    for row in of_name:
        if mine(row):
            continue
        other = _as_int(row.get("pid"))
        if not other:
            continue
        try:
            alive = (proc / str(other)).is_dir()
        except OSError:
            alive = True
        if not alive:
            continue
        was = row.get("pid_start")
        if was is None or _proc_start(proc, other) == _as_int(was):
            return ""  # a LIVE foreign holder (a row with no start is pid-only, as whoami reads it)
    return name


def _merge_owner(main: Path) -> str:
    """The repo's declared merge owner via the HUB `decisions.py --merge-owner` (run, never
    copied), or "". Cached in `<state>/lane-owner-cache.json` keyed by the ledger's realpath,
    mtime_ns and size and the resolver's realpath and mtime_ns; any cache error ignores the cache."""
    dpy = os.environ.get("QUOTA_STOP_DECISIONS_PY") or _HUB_DECISIONS_PY
    ledger = main / "docs" / "DECISIONS.md"
    try:
        if not ledger.is_file() or not os.path.isfile(dpy):
            return ""
        ls, ds = ledger.stat(), os.stat(dpy)
        key = (
            f"{os.path.realpath(ledger)}|{ls.st_mtime_ns}|{ls.st_size}|"
            f"{os.path.realpath(dpy)}|{ds.st_mtime_ns}"
        )
    except OSError:
        return ""
    cache_path = _state_dir() / "lane-owner-cache.json"
    cache: dict = {}
    try:
        loaded = json.loads(_regular_text(cache_path) or "{}")
        cache = loaded if isinstance(loaded, dict) else {}
    except ValueError:
        cache = {}
    hit = cache.get(key)
    if isinstance(hit, str):
        return hit
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_AGENT"}
    try:
        import subprocess

        res = subprocess.run(
            [sys.executable, "-I", dpy, "--merge-owner", str(main)],
            cwd=str(main),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_LANE_TIMEOUT_S,
        )
    except Exception:
        return ""
    if res.returncode == 0:
        lines = (res.stdout or "").strip().splitlines()
        owner = lines[0].strip() if lines else ""
    elif res.returncode == 3:
        owner = ""  # UNDECLARED: nobody owns the repo — a real answer, cached like one
    else:
        return ""
    cache.pop(key, None)
    cache[key] = owner
    while len(cache) > _LANE_CACHE_MAX:
        cache.pop(next(iter(cache)))
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_name(f".{cache_path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        os.replace(tmp, cache_path)
    except OSError:
        pass
    return owner


def _open_p0_items(main: Path, common: Path, name: str) -> list[str]:
    """Ids of the OPEN items with `priority` the int 0 whose `owner` is `name` (casefold): status
    exactly `open` (a `blocked` or `awaiting-operator` item is one its owner cannot work — work.py
    STATUSES) and no closed marker under `<common>/fabrik-work/closed/`."""
    key = name.casefold()
    closed = common / "fabrik-work" / "closed"
    out: list[str] = []
    try:
        files = sorted((main / ".fabrik" / "work").glob("W-*.json"))
    except OSError:
        return []
    for f in files:
        try:
            item = json.loads(_regular_text(f) or "null")
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        iid = item.get("id") if isinstance(item.get("id"), str) else f.stem
        prio = item.get("priority")
        if not (
            _ITEM_ID_RE.fullmatch(iid)
            and isinstance(prio, int)
            and not isinstance(prio, bool)
            and prio == 0
            and item.get("status") == "open"
            and str(item.get("owner") or "").strip().casefold() == key
        ):
            continue
        try:
            if (closed / f"{iid}.json").exists() or (closed / iid).exists():
                continue
        except OSError:
            continue
        out.append(iid)
    return out


def _claimed_items(common: Path, sid: str | None, now: float | None = None) -> list[str]:
    """Ids this session holds a LIVE claim on (`<common>/fabrik-work/claims/<id>.json`, live while
    `at + lease_s > now` — work.py `_is_live`); never raises."""
    if not sid:
        return []
    now = time.time() if now is None else now
    out: list[str] = []
    try:
        files = sorted((common / "fabrik-work" / "claims").glob("W-*.json"))
    except OSError:
        return []
    for f in files:
        try:
            rec = json.loads(_regular_text(f) or "null")
            if not (isinstance(rec, dict) and rec.get("session") == sid):
                continue
            if float(rec.get("at") or 0) + float(rec.get("lease_s") or 0) > now and (
                _ITEM_ID_RE.fullmatch(f.stem)
            ):
                out.append(f.stem)
        except (ValueError, TypeError, OverflowError):
            continue
    return out


def lane_exempt(sid: str | None, project_dir: str | None) -> tuple[bool, str]:
    """(exempt, why) for this session at the lane. Never raises; every doubt is (False, why)."""
    try:
        if not isinstance(sid, str) or not sid:
            return False, "no session id"
        if not project_dir or not os.path.isabs(project_dir):
            return False, "no repo to judge"
        common = _git_common(Path(project_dir))
        if common is None or common.name != ".git":
            return False, "not in a git checkout"
        main = common.parent
        name = _bound_name(sid, common)
        if not name:
            return False, "no agent name is bound to this session in this repo"
        try:
            cfg = json.loads(_regular_text(main / ".fabrik" / "work" / "config.json") or "null")
        except ValueError:
            cfg = None
        if isinstance(cfg, dict) and cfg.get("coordinator_mode") is True:
            owner = _merge_owner(main)
            if owner and owner.strip().casefold() == name.casefold():
                return True, f"{name} is this coordinator_mode repo's merge owner"
        p0 = _open_p0_items(main, common, name)
        if p0:
            return True, f"{name} owns open P0 item {', '.join(p0[:5])}"
        return False, f"bound as {name}: not the merge owner, and no open P0 item is yours"
    except Exception as exc:  # the hook must never raise on its own defect
        return False, f"lane check failed ({type(exc).__name__})"


# A lift epoch is believed only inside this window around now: `time.localtime` raises on an epoch
# outside the platform's time_t (1e20 — the hook then exited 1 with no JSON and Claude Code ran the
# tool, review round 1 F1), and no 5-hour window resets more than a weekly window away.
_LIFT_PAST_S = 86400.0
_LIFT_FUTURE_S = 8 * 86400.0


def _plausible_epoch(v: object, now: float) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        v = float(v)  # a JSON integer past float range overflows here (review round 2)
    except OverflowError:
        return None
    ok = math.isfinite(v) and now - _LIFT_PAST_S < v < now + _LIFT_FUTURE_S
    return v if ok else None


def _stamp_promise(stamp: Path, now: float | None = None) -> float | None:
    """Line 1 of the stamp — the tick's promised resume epoch — when it is a plausible epoch."""
    text = _regular_text(stamp)
    if text is None:
        return None
    try:
        v = float(text.split("\n", 1)[0].strip())
    except ValueError:
        return None
    return _plausible_epoch(v, time.time() if now is None else now)


def _posture_reset(now: float | None = None) -> float | None:
    """The posture's `active.windows.five_hour.resets_at`, when it is a plausible epoch."""
    try:
        doc = json.loads(_regular_text(_state_dir() / "quota-posture.json") or "null")
        v = doc["active"]["windows"]["five_hour"]["resets_at"]
    except (ValueError, TypeError, KeyError):
        return None
    return _plausible_epoch(v, time.time() if now is None else now)


def _render_lift(at: float, now: float) -> str | None:
    """`at HH:MM` today, `at YYYY-MM-DD HH:MM` another day; None for a past or unrenderable epoch."""
    if not (math.isfinite(at) and at > now):
        return None
    try:
        lt, nt = time.localtime(at), time.localtime(now)
        fmt = "%H:%M" if (lt.tm_year, lt.tm_yday) == (nt.tm_year, nt.tm_yday) else "%Y-%m-%d %H:%M"
        return f"at {time.strftime(fmt, lt)}"
    except (OverflowError, OSError, ValueError):
        return None


def _lane_lift(stamp: Path) -> str:
    """The lift line: the stamp's promise, else the posture's reset, the first still ahead.

    NEVER RAISES: it runs in `main()` outside any try, and a hook that exits non-zero is a
    non-blocking error — Claude Code runs the tool and the parked session escapes. So any failure
    reading either source (an int past float range, a posture nested past the recursion limit, an
    unreadable file) is the fallback text, never an exception (review rounds 1 and 2)."""
    now = time.time()
    when = None
    try:
        for at in (_stamp_promise(stamp, now), _posture_reset(now)):
            if at is not None and (when := _render_lift(at, now)) is not None:
                break
    except Exception:
        when = None
    when = when or "when the 5-hour window resets"
    return f"The lane lifts {when}, or earlier when a successor appears — the lift wakes an armed watch"


def decide(
    tool: str,
    command: str | None,
    *,
    stamp_exists: bool,
    tick_age_s: float | None,
    now: float | None = None,
    sid: str | None = None,
    tier: str = _STAMP_TIER_WALLED,
    battery: bool = False,
    hibernate: bool = False,
    pause_marked: bool = False,
    cwd: str | None = None,
    exempt: bool | None = None,
    why: str = "",
    items: tuple[str, ...] = (),
    lift: str = "",
    rebind: str = "",
) -> tuple[str, str]:
    """Decision. Returns (action, reason) with action ∈ {"allow", "deny", "allow_warn"}. Pure but
    for `cwd`: a `cd` prefix is resolved against the filesystem to find the session's own root.
    `hibernate` (the stamp's raw line 2) with `pause_marked` (the marker unlifted) skips the stale-tick fail-open.

    `exempt` is the LANE verdict at `urgent-90` (`lane_exempt`): True → allow with the lane nudge;
    False → the wall's allow-list plus the finishing verbs, denied with the park text naming the
    session's claimed `items` and the `lift`; `rebind` is the one name that session may re-bind
    (`_same_window_name`, "" for none). `None` means the caller never judged the lane — a pure probe — and keeps D-306's
    warning-tier allow; `main()` always judges it."""
    if not stamp_exists:
        return "allow", ""
    stale_after = _stale_after_s()
    held_pause = hibernate and pause_marked
    if not held_pause and (tick_age_s is None or tick_age_s > stale_after):
        return "allow_warn", (
            "quota-stop: the fleet-exhausted stamp exists but the rotation tick has not run for "
            f"{'unknown' if tick_age_s is None else f'{tick_age_s / 60:.0f}m'} — a stale flag never "
            "freezes the fleet; check `crontab -l` and ~/.claude/rotate-tick.log"
        )
    if tier == _STAMP_TIER_URGENT:
        # The LANE (D-1113): the fleet is at 90% of the session window with nothing to rotate to.
        # The runway is real, so an EXEMPT session keeps working — a seat mid-flight is not killed
        # — and is told the wall is next; every other session parks with the wall's allow-list
        # plus the finishing verbs, so the last points go to merging and keeping the records.
        if exempt is None or exempt:
            return "allow_warn", _nudge(why if exempt else None)
        if tool == "Bash":
            if command is not None and (
                _bash_allowed(command, cwd)
                or _lane_bash_allowed(command, cwd)
                or _lane_rebind_allowed(command, cwd, rebind)
            ):
                return "allow", ""
        elif tool in _READ_TOOLS or _READ_MCP.match(tool) or tool in _LANE_TOOLS:
            return "allow", ""
        return "deny", _park_reason(tool or "tool", sid, why=why, items=items, lift=lift)
    if tool == "Bash":
        # the vetoes read the MASKED segment (operators only); the allow-list reads the RAW
        # segment, because the leading command word is never quoted in a command we would allow.
        # `_resolve` first strips the one `cd`/`-C` and splits the one pipe the hold admits.
        if command is not None and _bash_allowed(command, cwd):
            return "allow", ""
        return "deny", _reason("Bash", sid, battery, hibernate)
    if tool in _READ_TOOLS or _READ_MCP.match(tool):
        return "allow", ""
    return "deny", _reason(tool or "tool", sid, battery, hibernate)


def _nudge(why: str | None = None) -> str:
    """The LANE's line for a session that CONTINUES (or a pure probe that never judged the lane).
    It asks for a CHECKPOINT, never a stop: the work in flight is exactly what the runway is for.
    THIS hook denies this session nothing while it prints — but it cannot say that nothing is
    denied, because `quota_posture_hook.py` holds new fan-out and new runs on the band, and at this
    tier that band is routinely RED. The wording must stay true of the SYSTEM, not just of this
    file."""
    who = (
        f"you continue ({why})"
        if why
        else "the merge owner and the owners of open P0 items continue"
    )
    return (
        "quota-stop: FLEET QUOTA LANE — the active account is at the urgent-drain line with no "
        f"account to rotate to; builders park and {who}. THE FLEET-WIDE HOLD (the wall) HAS NOT "
        "ARMED, so your in-flight work is not being cut short here. Whether a NEW fan-out or a "
        "new run is held depends on the band — "
        "read the QUOTA line on your prompt, or run `python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --status`. CHECKPOINT as you "
        "go so the "
        "wall costs you "
        "nothing: commit with explicit pathspecs, push, and keep your run record current "
        "(`command_run.py step|round`) — when the wall itself arrives every world-changing tool "
        "is held and only commit + push + close + stop gets through."
    )


def _literal_sid(sid: str | None) -> str:
    """The sid as the arm order may carry it (the arm regex's own class, 1–80 alnum and `._-`)."""
    return (
        sid
        if isinstance(sid, str)
        and 0 < len(sid) <= 80
        and all((c.isascii() and c.isalnum()) or c in "._-" for c in sid)
        else "<your sid>"
    )


# What a held session may still read and checkpoint, in the words of the allow-list itself (`_ALLOWED_BASH`,
# `_RELOCATED_WRITE`): "Reads, git" promised every git verb, and a held coordinator's `git -C /opt/fabrik grep` was
# refused under it (W-a77742db). No backticks: the park-message grader runs every backticked order through the lane.
# `git grep` stays held — the Grep tool already reads any path, and `git grep -O<pager>` runs a program.
_HELD_READS = (
    "Reads (the Read, Grep and Glob tools, and Bash cat, head, tail, grep, ls, wc and stat), the git checkpoint and "
    "read verbs with their plain flags (add -- <paths>, commit -m <msg> -- <paths>, push, fetch, status, diff, log, show, "
    "rev-parse and reset HEAD -- <paths>; through git -C /opt/<repo>, the read verbs only)"
)
# The wall's one message is pinned under 1,000 chars at the longest admitted sid for every built-in held tool
# (NotebookEdit, the longest, read 985 with "Reads, git"), so it carries the short true form; the lane message and
# this module's docstring carry the list.
_HELD_READS_SHORT = "Reads, git checkpoints"


def _park_reason(
    tool: str, sid: str | None, *, why: str = "", items: tuple[str, ...] = (), lift: str = ""
) -> str:
    """The LANE's park order. Every backticked command in it passes the lane's allow-list
    (`test_the_park_message_names_the_item_and_lift_and_orders_only_allowed_commands`), and
    `claude_rotate.py --status` is never ordered — it is not on the list. The head carries
    `fleet-exhausted`, the phrase `command_run.py::_WALL_REASON` keys a pasted reason on."""
    who = _literal_sid(sid)
    mine = ", ".join(items) if items else "none"
    return (
        "FLEET QUOTA LANE — the fleet-exhausted stamp stands at its urgent-90 tier: the 5-hour "
        "window is at the urgent-drain line with no account to rotate to, so only the merge owner "
        "of a coordinator_mode repo and the owner of an open P0 item continue"
        + (f" ({why})" if why else "")
        + f". {tool} is held. PARK NOW — your items: {mine}. Commit your own work with explicit "
        "pathspecs (`git commit -m '<msg>' -- <paths>` — single-quote the message), "
        "`git push`, close your run record with "
        "`python3 scripts/command_run.py blocked --wall --command <command> --reason '<why>'` "
        "(resumable by start --resume-from), send the merge request for finished work "
        "(`python3 scripts/merge_request.py request --review <receipt> --item <W-id>`), then end "
        f"the turn. {_HELD_READS}, command_run.py, mail.py, thread_anchor.py, the claim verbs "
        "(`python3 scripts/work.py claim <W-id>`), `python3 scripts/work.py next`, the rotation's "
        "re-bind of the one name this window held last (python3 "
        "/opt/fabrik/scripts/whoami_agent.py --as <that name> --force, that absolute path only), "
        "SubagentHandback, SendMessage, the self-watch "
        f"arm and TaskStop stay allowed. {lift or _lane_lift(_stamp())}; ARM the self-watch NOW "
        'if it is not: Bash(run_in_background: true, command: "bash '
        f'/opt/fabrik/scripts/sysadmin/selfwatch_arm.sh {who}").'
    )


def _reason(
    tool: str, sid: str | None = None, battery: bool = False, hibernate: bool = False
) -> str:
    """The one message every held session reads. It carries the LITERAL session id in the arm
    order when the payload names one — CLAUDE.md's arm rule needs a literal sid (an empty arg
    exits the watch as you arm it), and the relief wake reaches ONLY an armed watch."""
    who = _literal_sid(sid)
    if hibernate:
        head = (
            "HIBERNATE HOLD — the box is about to hibernate (the operator's /hibernate pause, T-3 has "
            "passed). A subagent returns NOW with its partial result."
        )
        lift = (
            "The hold lifts when the pause is lifted after the wake (the tick, or the hub's "
            "`python3 /opt/fabrik/scripts/sysadmin/hibernate.py lift`); "
            "`python3 /opt/fabrik/scripts/sysadmin/hibernate.py status`, "
            "`python3 /opt/fabrik/scripts/sysadmin/hibernate.py woke` and "
            "`python3 /opt/fabrik/scripts/sysadmin/hibernate.py paused` stay allowed too"
        )
    elif battery:
        head = (
            "BATTERY HOLD — the laptop is on battery at or below the hold line, and your context may "
            "be lost when it dies."
        )
        lift = "The hold lifts when mains power is back"
    else:
        head = "FLEET QUOTA EXHAUSTED — no account left to rotate to."
        lift = "The hold lifts when the tick sees relief"
    # the pause is an operator pause, never the quota wall: its close is `blocked --paused` (or
    # `handoff`), as the pause banner and the posture hook say (review r1, F5)
    close = (
        "`command_run.py blocked --paused` (or `handoff`), resumable by `start --resume-from`"
        if hibernate
        else "`command_run.py done` — or `blocked --wall`, resumable by `start --resume-from`"
    )
    return (
        f"{head} {tool} is held. STOP GRACEFULLY NOW: "
        "commit your own work with explicit pathspecs "
        "(`git commit -m '<msg>' -- <paths>` — SINGLE-QUOTE the message: a quoted newline is data, but `$(…)`/heredoc and a backtick in double quotes stay refused), "
        f"`git push`, close your run record ({close}), "
        f"then end the turn — no new edits, no new phases. {_HELD_READS_SHORT}, command_run.py, mail.py, "
        f"thread_anchor.py, the self-watch arm and TaskStop stay allowed. {lift}, "
        "and the lift WAKES every session whose self-watch is armed (a RESUME line naming where it left "
        "off) — an unarmed session stays idle until the operator restarts it, so ARM the self-watch NOW "
        'if it is not: Bash(run_in_background: true, command: "bash '
        f'/opt/fabrik/scripts/sysadmin/selfwatch_arm.sh {who}").'
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
    tier = _stamp_tier(_stamp()) if exists else _STAMP_TIER_WALLED
    hib = exists and _stamp_is_hibernate(_stamp())
    age: float | None
    try:
        age = time.time() - _tick_log().stat().st_mtime
    except OSError:
        age = None
    sid = payload.get("session_id") if isinstance(payload.get("session_id"), str) else None
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    exempt: bool | None = None
    why, items, lift, rebind = "", (), "", ""
    if exists and tier == _STAMP_TIER_URGENT and age is not None and age <= _stale_after_s():
        # the lane is judged only while it is in force; every doubt inside is NOT exempt
        project = _lane_project_dir(cwd)
        exempt, why = lane_exempt(sid, project)
        if not exempt:
            try:
                common = _git_common(Path(project)) if project else None
                items = tuple(_claimed_items(common, sid)) if common else ()
            except Exception:
                items = ()
            lift = _lane_lift(_stamp())
            if tool == "Bash" and isinstance(cmd, str) and "whoami_agent.py" in cmd:
                # lazily, on the re-bind's own call only: a raise here would fail OPEN, and the
                # /proc walk stays off every other parked call's 5 s hook budget
                try:
                    common = _git_common(Path(project)) if project else None
                    rebind = _same_window_name(common, cwd) if common else ""
                except Exception:
                    rebind = ""
    action, reason = decide(
        tool,
        cmd if isinstance(cmd, str) else None,
        stamp_exists=exists,
        tick_age_s=age,
        sid=sid,
        tier=tier,
        battery=exists and _stamp_is_battery(_stamp()),
        hibernate=hib,
        pause_marked=hib and _pause_marked(),
        cwd=cwd,
        exempt=exempt,
        why=why,
        items=items,
        lift=lift,
        rebind=rebind,
    )
    if action == "deny" and api_key_exempt(_stamp()):
        # judged on the DENY, so a stale tick keeps its own warning and an allowed call says nothing
        sys.stderr.write(
            "quota-stop: the fleet quota hold would hold this call, but this session runs on an "
            "Anthropic API key (no plan login), so it draws no plan quota and is not held "
            "(W-effb7141)\n"
        )
        return 0
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
