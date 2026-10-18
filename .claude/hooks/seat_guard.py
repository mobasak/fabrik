#!/usr/bin/env python3
# AFTER-EDIT: tests/test_seat_guard.py, docs/workstation/hooks-index.md, .claude/settings.json
"""PreToolUse (Bash) seat guard — refuse a review seat's pattern kills, its git writes outside scratch and its network clients.

Review seats (``agent_type`` in ``SEAT_TYPES``) run Bash in the LEAD's shared tree, and their
isolation used to be brief prose only. Two incident classes hit live repos: a seat's
``git checkout/reset/commit`` in a main checkout destroyed the merge owner's uncommitted work
(iterative_image_editor 01M41B1SF8), and a seat's ``pkill -f`` killed two real mail watches
(fabrik-lib 01M3YFX4J1). Intel's brief half (D-653) lowers the rate; this hook closes those two
classes for commands a seat types into Bash (W-6569a3fa). It does NOT see git run from inside a
script or subprocess (a ``python3 probe.py`` that shells out), and it guards ``fabrik-reviewer``
seats only — both are stated limits, not oversights.

For a seat only (the payload's ``agent_id`` + ``agent_type``, documented hook input fields):
  * The whole command is tokenised ONCE, quote-aware (``shlex`` with punctuation), and split into
    simple commands at ``;`` ``&&`` ``||`` ``|`` ``&`` ``(`` ``)`` and newlines, so quoted data — a
    commit message, a printf payload — is never read as a command. Shell keywords and brace
    groups are skipped; ``bash|sh|zsh|dash`` with any flag cluster containing ``c`` is followed
    into its script (depth 3); for the kill and git classes these wrappers are unwrapped: env
    (``-C dir``, ``-u``, ``-i``), sudo, nice, timeout, nohup, exec, command (``xargs`` is not —
    only ``xargs kill`` is read, below).
  * Kills: ``pkill`` and ``killall`` are denied anywhere, ``xargs kill`` too (its pids come from a
    pattern); ``kill`` may name only positive pids > 1 or ``%jobs`` after at most one signal
    (``-9``, ``-TERM``, ``-term``, ``-s SIG``, ``-0``); ``-l``/``-L`` lists signals and passes.
  * Git: the targets are the ``-C`` directory (else the segment's ``cd``, else the payload cwd),
    plus ``--git-dir``/``--work-tree`` (either form) and ``GIT_DIR``/``GIT_WORK_TREE``. A write —
    a working-tree verb, a store verb, or a worktree add/remove/move outside scratch — needs EVERY
    target inside a scratch root; a store verb (stash push/pop/drop, branch/tag writes, update-ref,
    symbolic-ref, config writes, push, fetch, reflog/gc/notes) also needs the repo's
    ``--git-common-dir`` inside scratch, because a probe worktree's stash lands on the MAIN repo's
    shared stack. Read-only forms pass: stash list/show, clean -n, branch --show-current, config
    --get, worktree add <scratch>/x (the CLAUDE.md probe recipe), worktree list.
  * Scratch: any path under ``/tmp/`` EXCEPT another session's tree — a path under
    ``/tmp/claude-<uid>/<slug>/<sid>/`` whose ``<sid>`` is not this payload's ``session_id``
    (a sibling session's probe worktree is not this seat's scratch) — plus the payload's
    ``scratchpad_dir`` when present.
  * Network (W-d146dd3c; fleet 01M56C2E4F — two seats made live ssh/scp connections the brief
    forbade; a PATH shim misses ProxyJump's absolute-path hop, ProxyJump outranks a later
    ProxyCommand): a client in COMMAND POSITION — the first word after assignments, or the
    command slot of a launcher in ``_LAUNCHERS`` (its value options and positionals skipped, a
    command-string option or a whitespace-holding word re-scanned) or of ``find -exec`` — is
    refused: ``scp sftp ssh-copy-id ssh-keyscan sshpass autossh mosh sshfs sshuttle`` always;
    ``ssh``/``slogin`` unless OpenSSH's options carry ``-V`` or ``-G`` without ``-F`` (``-F`` lets
    a seat-written config run ``Match exec``); ``rsync`` with a remote end as rsync parses one;
    git's network verbs with a remote URL, an scp-like repository or an ssh override
    (``GIT_SSH``/``GIT_SSH_COMMAND``/``core.sshCommand``). A ``$VAR`` head resolves from this
    command's own assignments; a substitution head, or a glob that can only be a client, refuses
    when it hides one. Replayed over 95,240 seat Bash calls (14 days, 2026-10-18): 10 newly
    refused — the incident calls and a ``-G -F`` probe, plus 2 untokenisable commands naming a
    client (fail-closed). Limits, stated: other socket clients (curl, wget, nc), a ``git fetch
    <remote-name>`` whose URL is only in config, ``Match exec`` in ``~/.ssh/config``, a ``$VAR``
    set outside the command, and a reader word after a launcher (``xargs grep ssh`` is refused).
  * Fail-CLOSED for a seat whose command cannot be tokenised AND mentions a git write verb, a
    kill word or a network client; otherwise fail-open (any error, a malformed payload) with exit
    0 and no output.
  * Dotenv: an allowed seat call is rewritten (``updatedInput``, no ``permissionDecision`` — it
    still goes through the normal permission flow) to start with ``export
    PYTHON_DOTENV_DISABLED=1``, so a probe that imports a live tree's app loads no ``.env``
    (site-provisioner 01M4F154S2, 01M4F1KHHW). Limits, stated: ``dotenv_values()``, ``dotenv
    run``, pydantic-settings ``env_file``, a hand-rolled ``.env`` parser, credentials already in the
    session's environment, and ``env -i``/``sudo`` or a typed ``unset`` are not covered; a seat
    that needs ``.env`` loaded sets ``PYTHON_DOTENV_DISABLED=0`` inline, visibly.
The lead (no ``agent_id``) and every other agent type are never touched.

⚠️ COBRA (D-253): the cheapest bypass is indirection the Bash string does not show — a variable
holding the verb (``$G commit``), a script file, a subprocess. Stated, not hidden: the counter is
the brief half and the review loop's leak check (D-653); a reference-transaction hook keyed on a
seat marker is the candidate if scripted writes recur.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

SEAT_TYPES = frozenset({"fabrik-reviewer"})
_OPS = frozenset({";", "&&", "||", "|", "&", "(", ")", "\n", ";;", "|&"})
_REDIR = frozenset({"<", ">", ">>", "<<", "<<<", ">&", "<&", "&>", "&>>", ">|"})
_KEYWORDS = frozenset(
    {"{", "}", "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "time"}
)
_SHELLS = frozenset({"bash", "sh", "zsh", "dash"})
WORKTREE_VERBS = frozenset(
    {
        "checkout",
        "switch",
        "reset",
        "restore",
        "commit",
        "merge",
        "rebase",
        "apply",
        "am",
        "cherry-pick",
        "revert",
        "add",
        "rm",
        "mv",
        "clean",
        "pull",
        "init",
    }
)
STORE_VERBS = frozenset(
    {"update-ref", "symbolic-ref", "push", "fetch", "gc", "prune", "repack", "replace"}
)
_KILL_SIGNAL = re.compile(r"^-(\d+|[A-Za-z]+|SIG[A-Za-z]+)$")
# Network clients (W-d146dd3c, fleet 01M56C2E4F): a seat's ssh/scp/... reaches a real host whatever its
# options — a PATH shim misses ProxyJump's absolute-path hop, ProxyJump outranks a later ProxyCommand.
NET_CLIENTS = frozenset(
    {
        "ssh",
        "slogin",
        "scp",
        "sftp",
        "ssh-copy-id",
        "ssh-keyscan",
        "sshpass",
        "autossh",
        "mosh",
        "sshfs",
        "sshuttle",
    }
)
_SSH_ARG_LETTERS = frozenset(
    "BbcDEeFIiJLlmOoPpQRSWw"
)  # OpenSSH 9.6p1 getopt letters that take a value
# A launcher runs the command named in its command slot. Per launcher: the options whose value is the NEXT word,
# the options whose value is a command STRING (re-scanned), and how many positional words precede the command.
_LAUNCHERS: dict[str, tuple[frozenset, frozenset, int]] = {
    "env": (frozenset({"-u", "--unset", "-C", "--chdir"}), frozenset({"-S", "--split-string"}), 0),
    "sudo": (frozenset({"-u", "-g", "-C", "-p", "-h", "-r", "-t", "-U", "-D"}), frozenset(), 0),
    "doas": (frozenset({"-u", "-C"}), frozenset(), 0),
    "nice": (frozenset({"-n", "--adjustment"}), frozenset(), 0),
    "ionice": (frozenset({"-c", "-n", "-p", "-t", "--class", "--classdata"}), frozenset(), 0),
    "chrt": (frozenset({"-T", "-P", "-D"}), frozenset(), 1),
    "taskset": (frozenset({"-c", "--cpu-list"}), frozenset(), 1),
    "timeout": (frozenset({"-s", "-k", "--signal", "--kill-after"}), frozenset(), 1),
    "nohup": (frozenset(), frozenset(), 0),
    "setsid": (frozenset(), frozenset(), 0),
    "stdbuf": (frozenset({"-i", "-o", "-e"}), frozenset(), 0),
    "unbuffer": (frozenset({"-p"}), frozenset(), 0),
    "flock": (
        frozenset({"-w", "-E", "--timeout", "--conflict-exit-code"}),
        frozenset({"-c", "--command"}),
        1,
    ),
    "strace": (
        frozenset({"-e", "-o", "-p", "-s", "-u", "-E", "-I", "-b", "-a", "-O", "-S", "-X", "-P"}),
        frozenset(),
        0,
    ),
    "ltrace": (
        frozenset({"-e", "-o", "-p", "-s", "-u", "-n", "-a", "-A", "-D", "-F", "-l", "-x"}),
        frozenset(),
        0,
    ),
    "time": (frozenset({"-f", "-o", "--format", "--output"}), frozenset(), 0),
    "exec": (frozenset({"-a"}), frozenset(), 0),
    "command": (frozenset(), frozenset(), 0),
    "builtin": (frozenset(), frozenset(), 0),
    "xargs": (
        frozenset(
            {
                "-I",
                "-i",
                "-n",
                "-P",
                "-L",
                "-l",
                "-s",
                "-d",
                "-E",
                "-e",
                "-a",
                "--arg-file",
                "--delimiter",
            }
        ),
        frozenset(),
        0,
    ),
    "parallel": (
        frozenset({"-j", "--jobs", "-S", "--sshlogin", "--joblog", "--results"}),
        frozenset(),
        0,
    ),
    "watch": (frozenset({"-n", "--interval", "-d"}), frozenset(), 0),
    "script": (
        frozenset(
            {"-T", "-t", "-I", "-O", "-B", "-E", "-m", "--log-timing", "--log-in", "--log-out"}
        ),
        frozenset({"-c", "--command"}),
        0,
    ),
    "su": (
        frozenset({"-s", "-g", "-G", "-w", "--shell", "--group"}),
        frozenset({"-c", "--command"}),
        1,
    ),
    "runuser": (
        frozenset({"-s", "-g", "-G", "-u", "-w", "--shell", "--group", "--user"}),
        frozenset({"-c", "--command"}),
        1,
    ),
    "sg": (frozenset(), frozenset({"-c"}), 1),
    "chroot": (frozenset({"--userspec", "--groups"}), frozenset(), 1),
    "unshare": (frozenset({"-S", "-G", "--setuid", "--setgid", "--root", "--wd"}), frozenset(), 0),
    "nsenter": (frozenset({"-t", "--target", "-S", "-G", "--root", "--wd"}), frozenset(), 0),
    "firejail": (frozenset(), frozenset(), 0),
    "ssh-agent": (frozenset({"-a", "-E", "-P", "-t"}), frozenset(), 0),
    "capped_run.sh": (frozenset(), frozenset(), 0),
    "rund": (frozenset(), frozenset(), 0),
}
_DASHDASH_LAUNCHERS = frozenset({"capped_run.sh", "rund"})  # their command follows `--`
# a glob head is a client only when it cannot name an ordinary command: `ss[h]` is, a `case` pattern's `*)` is not
_GLOB_CONTROL = ("ls", "cat", "echo", "grep", "sed", "python3", "bash", "true", "test")
_FIND_EXEC = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
_DURATION = re.compile(r"^\d+(\.\d+)?[smhd]?$")
# rsync's value-taking options a separate value can follow (rsync(1): each documented as `--opt=VALUE`)
_RSYNC_VALUE_OPTS = frozenset(
    {
        "-e",
        "--rsh",
        "-f",
        "--filter",
        "-T",
        "--temp-dir",
        "-M",
        "--remote-option",
        "-B",
        "--block-size",
        "--rsync-path",
        "--exclude",
        "--include",
        "--exclude-from",
        "--include-from",
        "--files-from",
        "--chown",
        "--chmod",
        "--usermap",
        "--groupmap",
        "--out-format",
        "--log-file",
        "--log-file-format",
        "--partial-dir",
        "--backup-dir",
        "--suffix",
        "--compare-dest",
        "--copy-dest",
        "--link-dest",
        "--password-file",
        "--iconv",
        "--checksum-choice",
        "--compress-choice",
        "--compress-level",
        "--skip-compress",
        "--max-size",
        "--min-size",
        "--max-delete",
        "--max-alloc",
        "--modify-window",
        "--bwlimit",
        "--timeout",
        "--contimeout",
        "--port",
        "--sockopts",
        "--address",
        "--stop-at",
        "--stop-after",
        "--info",
        "--debug",
        "--outbuf",
        "--write-batch",
        "--only-write-batch",
        "--read-batch",
        "--protocol",
        "--early-input",
        "--copy-as",
    }
)
_GIT_NET_VERBS = frozenset(
    {"clone", "fetch", "pull", "push", "ls-remote", "archive", "submodule", "remote"}
)
_REMOTE_URL = re.compile(r"^(ssh|git|https?|rsync|git\+ssh|ssh\+git)://", re.IGNORECASE)
_GIT_SSH_ENV = frozenset({"GIT_SSH", "GIT_SSH_COMMAND"})
# a client word in raw text — `/usr/bin/ssh` counts, `~/.ssh`, `ssh-keygen` and `ssh_config` do not
_CLIENT_WORD = re.compile(
    r"(?<![\w.-])(ssh|slogin|scp|sftp|ssh-copy-id|ssh-keyscan|sshpass|autossh|mosh|sshfs|sshuttle|rsync)(?![\w./-])"
)
_TMP_SESSION = re.compile(r"^/tmp/claude-\d+/[^/]+/([^/]+)(/|$)")
_SAFE = (
    "run a git write only as `git -C <absolute repo under your scratch dir>` (a probe worktree "
    "of the main repo may not stash, branch, tag or push — those land in the shared store); "
    "never kill by pattern — kill a numeric pid you started; "
    "never ssh, scp, sftp, a remote rsync or a remote git URL — `ssh -G <host>` prints the resolved config "
    "without connecting"
)


class _UnparseableError(Exception):
    pass


def _tokens(command: str) -> list[str]:
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    try:
        return list(lex)
    except ValueError as exc:
        raise _UnparseableError(str(exc)) from exc


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_OP_ORDER = (
    "&&",
    "||",
    ";;",
    "|&",
    "&>>",
    "<<<",
    ">>",
    "<<",
    "&>",
    ">&",
    "<&",
    ">|",
    ";",
    "&",
    "|",
    "(",
    ")",
    "<",
    ">",
    "\n",
)
SUBST = "__SUBST__"


def _strip_heredocs(command: str) -> str:
    """Drop heredoc BODIES (data written to a file), keeping the line that opens them."""
    out: list[str] = []
    pending: list[str] = []
    for line in command.split("\n"):
        if pending:
            if line.strip("\t ") == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending.extend(m.group(2) for m in _HEREDOC.finditer(line))
    return "\n".join(out)


def _extract_substitutions(command: str) -> tuple[list[str], str]:
    """Pull out $(…), `…`, <(…) and >(…) — commands the shell RUNS — and leave a placeholder."""
    inner: list[str] = []
    out: list[str] = []
    i, n, in_single = 0, len(command), False
    while i < n:
        c = command[i]
        if c == "'" and not in_single:
            j = command.find("'", i + 1)
            if j == -1:
                out.append(command[i:])
                break
            out.append(command[i : j + 1])
            i = j + 1
            continue
        if command[i : i + 2] in ("$(", "<(", ">(") or c == "`":
            if c == "`":
                j = command.find("`", i + 1)
                if j == -1:
                    raise _UnparseableError("unclosed backtick")
                inner.append(command[i + 1 : j])
                i = j + 1
            else:
                depth, j = 1, i + 2
                while j < n and depth:
                    depth += {"(": 1, ")": -1}.get(command[j], 0)
                    j += 1
                if depth:
                    raise _UnparseableError("unclosed substitution")
                inner.append(command[i + 2 : j - 1])
                i = j
            out.append(SUBST)
            continue
        out.append(c)
        i += 1
    return inner, "".join(out)


def _split_punct(tokens: list[str]) -> list[str]:
    """shlex merges an adjacent run of punctuation (`);`, `&&(`) into one token — split it."""
    out: list[str] = []
    for tok in tokens:
        if tok and all(ch in ";&|()<>\n" for ch in tok) and tok not in _OPS | _REDIR:
            k = 0
            while k < len(tok):
                for op in _OP_ORDER:
                    if tok.startswith(op, k):
                        out.append(op)
                        k += len(op)
                        break
                else:
                    out.append(tok[k])
                    k += 1
        else:
            out.append(tok)
    return out


def _simple_commands(tokens: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    cur: list[str] = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok in _OPS:
            if cur:
                out.append(cur)
            cur = []
            if tok in ("(", ")"):
                out.append([tok])  # subshell scope marker
        elif tok in _REDIR:
            skip_next = True  # the redirect's target file is not an argument
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


def _strip(words: list[str], ctx: dict) -> list[str]:
    """Drop keywords, assignments and wrappers; record env/cwd effects into ``ctx``."""
    i = 0
    while i < len(words):
        w = words[i]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", w)
        if w in _KEYWORDS:
            i += 1
        elif m:
            if m.group(1) in ("GIT_DIR", "GIT_WORK_TREE"):
                ctx["targets"].append(m.group(2))
                ctx["git_dir" if m.group(1) == "GIT_DIR" else "work_tree"] = True
            i += 1
        elif w in ("nohup", "exec", "command", "builtin"):
            i += 1
        elif w == "env":
            i += 1
            while i < len(words) and (words[i].startswith("-") or "=" in words[i]):
                if words[i] in ("-C", "--chdir") and i + 1 < len(words):
                    ctx["cwd"] = os.path.join(ctx["cwd"], words[i + 1])
                    i += 2
                    continue
                if words[i].startswith("--chdir="):
                    ctx["cwd"] = os.path.join(ctx["cwd"], words[i].split("=", 1)[1])
                elif words[i] in ("-u", "--unset", "-S") and i + 1 < len(words):
                    i += 1
                elif "=" in words[i] and not words[i].startswith("-"):
                    k = words[i].split("=", 1)
                    if k[0] in ("GIT_DIR", "GIT_WORK_TREE"):
                        ctx["targets"].append(k[1])
                i += 1
        elif w in ("sudo", "nice"):
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-u", "-g", "-n", "-C") and i + 1 < len(words) else 1
        elif w == "timeout":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-s", "-k", "--signal", "--kill-after") else 1
            if i < len(words) and re.match(r"^\d+(\.\d+)?[smhd]?$", words[i]):
                i += 1
        else:
            break
    return words[i:]


def _in_scratch(path: str, ctx: dict) -> bool:
    if SUBST in path or "$" in path:
        return False  # a substituted or variable path is unknown — fail closed for a write
    real = os.path.realpath(path)
    sd = ctx.get("scratchpad")
    if sd and (real == sd or real.startswith(sd.rstrip("/") + "/")):
        return True
    if not (real == "/tmp" or real.startswith("/tmp/")):
        return False
    m = _TMP_SESSION.match(real + ("/" if not real.endswith("/") else ""))
    return not (m and ctx.get("sid") and m.group(1) != ctx["sid"])


def _kill_reason(words: list[str]) -> str:
    name = os.path.basename(words[0])
    if name in ("pkill", "killall"):
        return f"`{name}` kills by pattern and can hit another session's processes"
    if name == "xargs":
        rest = [w for w in words[1:] if not w.startswith("-")]
        if rest and os.path.basename(rest[0]) in ("kill", "pkill", "killall"):
            return "`xargs kill` kills whatever a pattern search returned"
        return ""
    if name != "kill":
        return ""
    args = words[1:]
    if args and args[0] in ("-l", "-L", "--list", "--table"):
        return ""
    i, seen_signal = 0, False
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            seen_signal = True
            continue
        if not seen_signal and a in ("-s", "-n") and i + 1 < len(args):
            i, seen_signal = i + 2, True
            continue
        if not seen_signal and _KILL_SIGNAL.match(a):
            i, seen_signal = i + 1, True
            continue
        if re.match(r"^%[1-9]\d*$", a) or (a.isdigit() and int(a) > 1):
            i += 1
            continue
        return f"`kill {a}` is not a single positive pid (0, 1, a negative group or a substitution can hit every session)"
    return ""


def _git_parse(words: list[str], ctx: dict) -> tuple[str, list[str], list[str]]:
    """(verb, verb args, targets) for a git command."""
    directory = ctx["cwd"]
    targets = list(ctx["targets"])
    explicit = {"dir": bool(ctx.get("git_dir")), "tree": bool(ctx.get("work_tree"))}
    i = 1
    while i < len(words) and words[i].startswith("-"):
        w = words[i]
        if w == "-C" and i + 1 < len(words):
            directory = os.path.join(directory, words[i + 1])
            i += 2
        elif w in ("--git-dir", "--work-tree") and i + 1 < len(words):
            targets.append(os.path.join(directory, words[i + 1]))
            explicit["dir" if w == "--git-dir" else "tree"] = True
            i += 2
        elif w.startswith(("--git-dir=", "--work-tree=")):
            targets.append(os.path.join(directory, w.split("=", 1)[1]))
            explicit["dir" if w.startswith("--git-dir") else "tree"] = True
            i += 1
        elif w == "-c" and i + 1 < len(words):
            key, _, val = words[i + 1].partition("=")
            if key.lower() == "core.worktree" and val:
                targets.append(os.path.join(directory, val))
                explicit["tree"] = True
            i += 2
        elif w in ("--exec-path", "--namespace") and i + 1 < len(words):
            i += 2
        else:
            i += 1
    if not (explicit["dir"] and explicit["tree"]):
        targets.insert(0, directory)  # with both given, the cwd only resolves relative paths
    verb = words[i] if i < len(words) else ""
    return verb, words[i + 1 :], targets


def _positional(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _git_kind(verb: str, args: list[str]) -> str:
    """'read' · 'tree' (working-tree write) · 'store' (shared-store write) · 'worktree'."""
    flags = set(args)
    if verb == "stash":
        sub = args[0] if args else "push"
        return "read" if sub in ("list", "show") else "store"
    if verb == "clean":
        return "read" if flags & {"-n", "--dry-run"} else "tree"
    if verb in WORKTREE_VERBS:
        return "tree"
    if verb in STORE_VERBS:
        return "store"
    if verb == "worktree":
        return "read" if (args[:1] == ["list"] or not args) else "worktree"
    if verb == "branch":
        writes = {
            "-d",
            "-D",
            "-m",
            "-M",
            "-f",
            "--force",
            "-c",
            "-C",
            "--delete",
            "--move",
            "--copy",
            "--set-upstream-to",
            "-u",
            "--unset-upstream",
            "--edit-description",
        }
        listing = flags & {
            "--show-current",
            "--list",
            "-l",
            "-a",
            "-r",
            "--contains",
            "--merged",
            "--no-merged",
            "-v",
            "-vv",
        }
        if flags & writes or (_positional(args) and not listing):
            return "store"
        return "read"
    if verb == "tag":
        writes = {"-d", "--delete", "-f", "--force", "-a", "-s", "-u", "-m", "-F"}
        if flags & writes:
            return "store"
        if flags & {"-l", "--list", "-n", "--contains", "--points-at"} or not _positional(args):
            return "read"
        return "store"
    if verb == "config":
        if flags & {
            "--get",
            "--get-all",
            "--get-regexp",
            "--list",
            "-l",
            "--get-urlmatch",
            "--show-origin",
            "--show-scope",
        }:
            return "read"
        if flags & {
            "--unset",
            "--unset-all",
            "--add",
            "--replace-all",
            "--rename-section",
            "--remove-section",
            "-e",
            "--edit",
        }:
            return "store"
        return "store" if len(_positional(args)) >= 2 else "read"
    if verb == "reflog":
        return "store" if args[:1] in (["expire"], ["delete"]) else "read"
    if verb == "notes":
        return "read" if (not args or args[0] in ("list", "show")) else "store"
    if verb == "remote":
        return "read" if (not args or args[0] in ("-v", "show", "get-url")) else "store"
    return "read"


def _common_dir_in_scratch(directory: str, ctx: dict) -> bool:
    if not os.path.isdir(directory):
        return True  # nothing there yet (an init target) — its store is the scratch path itself
    try:
        r = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if r.returncode != 0 or not r.stdout.strip():
        return True  # not a repository: no shared store to protect
    return _in_scratch(r.stdout.strip(), ctx)


def _git_reason(words: list[str], ctx: dict) -> str:
    if os.path.basename(words[0]) != "git":
        return ""
    verb, args, targets = _git_parse(words, ctx)
    kind = _git_kind(verb, args)
    if kind == "read":
        return ""
    if kind == "worktree":
        sub = args[0] if args else ""
        paths = _positional(args[1:])
        path = os.path.join(targets[0], paths[0]) if paths else targets[0]
        if sub == "add" and _in_scratch(path, ctx):
            return ""
        if (
            sub in ("remove", "move", "lock", "unlock", "repair")
            and paths
            and _in_scratch(path, ctx)
        ):
            return ""
        return f"`git worktree {sub}` touches {os.path.realpath(path)}, outside your scratch"
    for t in targets:
        if not _in_scratch(t, ctx):
            return f"`git {verb}` targets {os.path.realpath(t)}, outside your scratch"
    if kind == "store" and not _common_dir_in_scratch(targets[0], ctx):
        return (
            f"`git {verb}` writes the shared store of {os.path.realpath(targets[0])} "
            "(a probe worktree of a main repo)"
        )
    return ""


def _ssh_reason(name: str, args: list[str]) -> str:
    """ssh/slogin are local only as `-V` (version, exits while parsing) or `-G` without `-F` (print config).

    Options are read as OpenSSH 9.6p1 reads them: up to the second non-option word (destination, then the
    remote command), `--` ending them, a short-option cluster letter by letter, a value-taking letter
    consuming the rest of its word or the next word. `-F` with `-G` is refused: a config file a seat wrote
    runs `Match exec` while `-G` resolves it."""
    letters: set[str] = set()
    positional = 0
    i = 0
    while i < len(args) and positional < 2:
        a = args[i]
        if a == "--":
            break
        if a.startswith("-") and len(a) > 1:
            for k, ch in enumerate(a[1:], start=1):
                letters.add(ch)
                if ch in _SSH_ARG_LETTERS:
                    if k == len(a) - 1:
                        i += 1  # the value is the next word
                    break
        else:
            positional += 1
        i += 1
    if "V" in letters or ("G" in letters and "F" not in letters):
        return ""
    return f"`{name}` opens a network connection whatever its options"


def _rsync_reason(args: list[str]) -> str:
    i = 0
    while i < len(args):
        a = args[i]
        if a in _RSYNC_VALUE_OPTS:
            i += 2
            continue
        if not a.startswith("-"):
            head = a.split(":", 1)[0]
            if _REMOTE_URL.match(a) or "::" in a or (":" in a and "/" not in head):
                return f"`rsync` to `{a}` reaches a remote host"
        i += 1
    return ""


def _remote_git_arg(a: str) -> bool:
    """A git repository argument naming a remote end: a network URL or scp-like `[user@]host:path`."""
    if _REMOTE_URL.match(a):
        return True
    if a.lower().startswith("file:") or a.startswith(("-", ".", "/", "~")):
        return False
    head = a.split(":", 1)[0]
    return ":" in a and bool(head) and "/" not in head


# fetch/pull/push take refspecs (`src:dst`) after the repository, so only the repository counts there
_GIT_REFSPEC_VERBS = frozenset({"fetch", "pull", "push"})
_GIT_FETCH_VALUE_OPTS = frozenset(
    {
        "--depth",
        "-j",
        "--jobs",
        "--upload-pack",
        "--receive-pack",
        "-o",
        "--server-option",
        "--shallow-since",
        "--shallow-exclude",
        "--negotiation-tip",
        "--refmap",
        "--recurse-submodules-default",
        "--exec",
    }
)


def _git_net_reason(args: list[str], env: set[str]) -> str:
    """git's network verbs are refused when the command shows a remote end or an ssh override."""
    i, override = 0, bool(env & _GIT_SSH_ENV)
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-c" and i + 1 < len(args):
            override |= args[i + 1].split("=", 1)[0].lower() == "core.sshcommand"
            i += 2
        elif args[i] in (
            "-C",
            "--git-dir",
            "--work-tree",
            "--exec-path",
            "--namespace",
        ) and i + 1 < len(args):
            i += 2
        else:
            i += 1
    verb, rest = (args[i], args[i + 1 :]) if i < len(args) else ("", [])
    if verb not in _GIT_NET_VERBS:
        return ""
    if verb == "archive" and not any(a.startswith("--remote") for a in rest):
        return ""
    if verb in _GIT_REFSPEC_VERBS:
        candidates: list[str] = []
        k = 0
        while k < len(rest):
            if rest[k] in _GIT_FETCH_VALUE_OPTS:
                k += 2
            elif rest[k].startswith("-"):
                k += 1
            else:
                candidates = [rest[k]]  # the repository; what follows are refspecs
                break
    else:
        candidates = [a.split("=", 1)[1] if a.startswith("--remote=") else a for a in rest]
    if override or any(_remote_git_arg(a) for a in candidates):
        return f"`git {verb}` reaches a remote host"
    return ""


def _client_reason(words: list[str], env: set[str]) -> str | None:
    """The verdict for a client word at words[0]: a reason, "" (a client, allowed), or None (no client)."""
    name = os.path.basename(words[0])
    if name in ("ssh", "slogin"):
        return _ssh_reason(name, words[1:])
    if name in NET_CLIENTS:
        return f"`{name}` opens a network connection"
    if name == "rsync":
        return _rsync_reason(words[1:])
    if name == "git":
        return _git_net_reason(words[1:], env)
    return None


def _net_reason(raw: list[str], ctx: dict, raw_command: str, depth: int) -> str:
    """A network client in command position — the first word, or a launcher's command slot."""
    env: set[str] = set()
    variables = ctx.setdefault("vars", {})
    i = 0
    if raw[:1] == ["export"]:
        i = 1
    while i < len(raw) and (raw[i] in _KEYWORDS or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", raw[i])):
        if "=" in raw[i]:
            key, value = raw[i].split("=", 1)
            env.add(key)
            variables[key] = value  # a later `$key` head in the same command resolves to it
        i += 1
    while i < len(raw):
        w = raw[i]
        var = re.fullmatch(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", w)
        if var:
            value = variables.get(var.group(1))
            if not value:
                return ""  # set outside this command: a stated limit
            try:
                expanded = shlex.split(value)
            except ValueError:
                expanded = [value]
            return (
                _net_reason(expanded + raw[i + 1 :], {**ctx, "vars": {}}, raw_command, depth + 1)
                if depth < 3
                else ""
            )
        if SUBST in w:
            if _CLIENT_WORD.search(raw_command):
                return f"a command named by a substitution (`{w}`) next to a network client"
            return ""
        if "$" in w:
            return ""
        if any(c in w for c in "*?["):
            base = os.path.basename(w)
            if any(fnmatch.fnmatchcase(c, base) for c in NET_CLIENTS | {"rsync"}) and not any(
                fnmatch.fnmatchcase(c, base) for c in _GLOB_CONTROL
            ):
                return f"a command named by a glob (`{w}`) that can only be a network client"
            return ""
        verdict = _client_reason(raw[i:], env)
        if verdict is not None:
            return verdict
        name = os.path.basename(w)
        if name == "find":
            for k in range(i + 1, len(raw)):
                if raw[k] in _FIND_EXEC and k + 1 < len(raw):
                    v = _client_reason(raw[k + 1 :], env)
                    if v:
                        return v
            return ""
        spec = _LAUNCHERS.get(name)
        if spec is None:
            return ""
        value_opts, string_opts, positionals = spec
        i += 1
        if name == "command" and i < len(raw) and raw[i] in ("-v", "-V"):
            return ""  # a lookup, not a run
        if name in _DASHDASH_LAUNCHERS:
            while i < len(raw) and raw[i] != "--":
                i += 1
            i += 1
            continue
        if name == "taskset":
            positionals = 0 if any(a in ("-c", "--cpu-list") for a in raw[i:]) else positionals
        while i < len(raw):
            a = raw[i]
            if a.startswith("-") and not a.startswith("--") and len(a) > 2:
                # a short-option cluster (`-qc`): its LAST letter may take the next word
                tail = "-" + a[-1]
                if tail in string_opts or tail in value_opts:
                    a = tail
            if a in string_opts and i + 1 < len(raw):
                if depth < 3:
                    reason = _scan(raw[i + 1], {**ctx, "targets": [], "dirs": []}, depth + 1)
                    if reason:
                        return reason
                i += 2
            elif a in value_opts and i + 1 < len(raw):
                i += 2
            elif a.startswith("-"):
                i += 1
            elif "=" in a and name == "env":
                env.add(a.split("=", 1)[0])
                i += 1
            elif positionals and (_DURATION.match(a) or name not in ("timeout",)):
                positionals -= 1
                i += 1
            else:
                break
        if i < len(raw) and depth < 3 and any(ch.isspace() for ch in raw[i]):
            reason = _scan(raw[i], {**ctx, "targets": [], "dirs": []}, depth + 1)
            if reason:
                return reason
    return ""


def _scan(command: str, ctx: dict, depth: int) -> str:
    raw_command = command
    try:
        command = _strip_heredocs(command)
        inner, command = _extract_substitutions(command)
        cmds = _simple_commands(_split_punct(_tokens(command)))
    except _UnparseableError:
        writes = "|".join(
            sorted(WORKTREE_VERBS | STORE_VERBS | {"stash", "branch", "tag", "config", "worktree"})
        )
        # any git … <write verb> on one command line, flags in between included; any kill word
        if re.search(rf"\bgit\b[^;&|\n]*?\s({writes})\b|\b(pkill|killall|kill)\b", raw_command):
            return "the command cannot be tokenised and names a git write or a kill"
        if _CLIENT_WORD.search(raw_command):
            return "the command cannot be tokenised and names a network client"
        return ""
    if depth < 3:
        for sub in inner:
            reason = _scan(sub, {**ctx, "targets": [], "dirs": []}, depth + 1)
            if reason:
                return reason
    scopes: list[tuple[str, list[str]]] = []
    for raw in cmds:
        if raw == ["("]:
            scopes.append((ctx["cwd"], list(ctx.get("dirs", []))))
            continue
        if raw == [")"]:
            if scopes:
                ctx["cwd"], ctx["dirs"] = scopes.pop()  # a subshell's cd and pushd die with it
            continue
        ctx["targets"], ctx["git_dir"], ctx["work_tree"] = [], False, False
        reason = _net_reason(raw, ctx, raw_command, depth)
        if reason:
            return reason
        words = _strip(raw, ctx)
        if not words:
            continue
        head = os.path.basename(words[0])
        if head in ("cd", "pushd"):
            if head == "pushd":
                ctx.setdefault("dirs", []).append(ctx["cwd"])
            args = [w for w in words[1:] if not w.startswith("-") or w == "-"]
            if args:
                ctx["cwd"] = os.path.join(ctx["cwd"], args[0]) if args[0] != "-" else SUBST
            continue
        if head == "popd":
            if ctx.get("dirs"):
                ctx["cwd"] = ctx["dirs"].pop()
            continue
        if head in _SHELLS and depth < 3:
            for k, w in enumerate(words[1:], start=1):
                if w.startswith("-") and not w.startswith("--") and "c" in w[1:]:
                    rest = [x for x in words[k + 1 :] if not x.startswith("-")]
                    if rest:
                        reason = _scan(rest[0], {**ctx, "targets": [], "dirs": []}, depth + 1)
                        if reason:
                            return reason
                    break
            continue
        reason = _kill_reason(words) or _git_reason(words, ctx)
        if reason:
            return reason
    return ""


def decide(payload: dict) -> str:
    """The deny reason for this Bash call, or "" to allow."""
    if not payload.get("agent_id") or payload.get("agent_type") not in SEAT_TYPES:
        return ""
    command = (payload.get("tool_input") or {}).get("command") or ""
    sd = payload.get("scratchpad_dir")
    ctx = {
        "cwd": str(payload.get("cwd") or os.getcwd()),
        "targets": [],
        "dirs": [],
        "git_dir": False,
        "work_tree": False,
        "sid": str(payload.get("session_id") or ""),
        "scratchpad": os.path.realpath(sd) if isinstance(sd, str) and sd else "",
    }
    reason = _scan(command, ctx, 0)
    if reason:
        return f"seat guard (review seats run in the lead's shared tree): {reason}. {_SAFE}."
    return ""


_DOTENV_OFF = "export PYTHON_DOTENV_DISABLED=1"
# the switch already set as the FIRST statement (a trailing `;` or newline ends it); `=10` is not
# it — python-dotenv reads only 1/true/t/yes/y as on (review A-S1)
_ALREADY_OFF = re.compile(r"\s*export\s+PYTHON_DOTENV_DISABLED=1\s*(?:;|\n|$)")


def rewrite(payload: dict) -> dict | None:
    """The seat's ``tool_input`` with ``_DOTENV_OFF`` on its own first line, or None.

    site-provisioner 01M4F154S2 / 01M4F1KHHW: seats that imported the live tree's app had its
    import-time ``load_dotenv()`` restore every provider credential the brief told them to unset,
    and made real Namecheap and Cloudflare calls. Every program the rewritten command starts
    inherits the switch (python-dotenv >= 1.2.0 reads it on each ``load_dotenv`` call). Emitted as
    ``updatedInput`` WITHOUT a ``permissionDecision``: the hook rewrites, it never approves.
    """
    if not payload.get("agent_id") or payload.get("agent_type") not in SEAT_TYPES:
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return None
    if _ALREADY_OFF.match(command):
        return None
    return {**tool_input, "command": f"{_DOTENV_OFF}\n{command}"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    # the rewrite is computed apart from the scan: the deny half fails open by charter, and the
    # credential half must not fail with it
    try:
        updated = rewrite(payload)
    except Exception:
        updated = None
    try:
        reason = decide(payload)
    except Exception:
        reason = ""
    if not reason and updated is not None:
        print(
            json.dumps(
                {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}
            )
        )
        return 0
    if reason:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
