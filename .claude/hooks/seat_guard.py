#!/usr/bin/env python3
# AFTER-EDIT: tests/test_seat_guard.py, docs/workstation/hooks-index.md, .claude/settings.json
"""PreToolUse (Bash) seat guard — refuse a review seat's pattern kills and its git writes outside scratch.

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
    into its script (depth 3); wrappers are unwrapped: env (``-C dir``, ``-u``, ``-i``), sudo,
    nice, timeout, nohup, exec, command, xargs.
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
  * Fail-CLOSED for a seat whose command cannot be tokenised AND mentions a git write verb or a
    kill word; otherwise fail-open (any error, a malformed payload) with exit 0 and no output.
The lead (no ``agent_id``) and every other agent type are never touched.

⚠️ COBRA (D-253): the cheapest bypass is indirection the Bash string does not show — a variable
holding the verb (``$G commit``), a script file, a subprocess. Stated, not hidden: the counter is
the brief half and the review loop's leak check (D-653); a reference-transaction hook keyed on a
seat marker is the candidate if scripted writes recur.
"""

from __future__ import annotations

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
_TMP_SESSION = re.compile(r"^/tmp/claude-\d+/[^/]+/([^/]+)(/|$)")
_SAFE = (
    "run a git write only as `git -C <absolute repo under your scratch dir>` (a probe worktree "
    "of the main repo may not stash, branch, tag or push — those land in the shared store); "
    "never kill by pattern — kill a numeric pid you started"
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
            return 0
        reason = decide(payload)
    except Exception:
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
