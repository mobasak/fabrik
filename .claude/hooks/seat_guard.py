#!/usr/bin/env python3
# AFTER-EDIT: tests/test_seat_guard.py, tests/test_shared_venv_guard.py, docs/workstation/hooks-index.md, .claude/settings.json
"""PreToolUse (Bash) seat guard — refuse a review seat's pattern kills and its git writes outside
scratch, and ANY session's sync or install into the venv a linked worktree shares (W-46d148b0).

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
    into its script (depth 3); wrappers are unwrapped, matched by basename: env (``-C dir``,
    ``-u``, ``-i``), sudo, nice, timeout, nohup, exec, command (``-v`` runs nothing), stdbuf,
    ionice, flock. ``#`` starts a comment only at an unquoted word start, as in the shell.
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
  * Dotenv: an allowed seat call is rewritten (``updatedInput``, no ``permissionDecision`` — it
    still goes through the normal permission flow) to start with ``export
    PYTHON_DOTENV_DISABLED=1``, so a probe that imports a live tree's app loads no ``.env``
    (site-provisioner 01M4F154S2, 01M4F1KHHW). Limits, stated: ``dotenv_values()``, ``dotenv
    run``, pydantic-settings ``env_file``, a hand-rolled ``.env`` parser, credentials already in the
    session's environment, and ``env -i``/``sudo`` or a typed ``unset`` are not covered; a seat
    that needs ``.env`` loaded sets ``PYTHON_DOTENV_DISABLED=0`` inline, visibly.
The lead (no ``agent_id``) and every other agent type pass the kill and git checks; EVERY session,
seats included, gets the shared-venv check (its own comment block, above ``_child``).

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
import shutil
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
    lex.commenters = ""  # shlex ends a word at `#`; the shell does not (`a#b`): _strip_comments
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


def _strip_comments(command: str) -> str:
    """Drop shell comments: an unquoted `#` at a word start, to the end of its line."""
    out: list[str] = []
    i, n, quote = 0, len(command), ""
    while i < n:
        c = command[i]
        if quote:
            out.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                out.append(command[i + 1])
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c == "\\" and i + 1 < n:
            out.append(command[i : i + 2])
            i += 2
            continue
        elif c in ("'", '"'):
            quote = c
            out.append(c)
        elif c == "#" and (i == 0 or command[i - 1] in " \t\n;&|()<>"):
            j = command.find("\n", i)
            i = n if j == -1 else j
            continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


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
            if cur and cur[-1].isdigit():
                cur.pop()  # `2>&1`: shlex splits the fd number off as a word
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
        b = os.path.basename(w)
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", w)
        if w in _KEYWORDS:
            i += 1
        elif m:
            ctx.setdefault("assign", {})[m.group(1)] = m.group(2)
            if m.group(1) in ("GIT_DIR", "GIT_WORK_TREE"):
                ctx["targets"].append(m.group(2))
                ctx["git_dir" if m.group(1) == "GIT_DIR" else "work_tree"] = True
            i += 1
        elif b in ("nohup", "exec", "builtin"):
            i += 1
        elif b == "command":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                if words[i] in ("-v", "-V"):
                    return []  # `command -v x` names x, it does not run it
                i += 1
        elif b in ("stdbuf", "ionice"):
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-i", "-o", "-e", "-c", "-n", "-p", "-P", "-u") else 1
        elif b == "flock":
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-w", "--timeout", "-E", "--conflict-exit-code") else 1
            i += 1  # the lock file
        elif b == "env":
            i += 1
            while i < len(words) and (words[i].startswith("-") or "=" in words[i]):
                if words[i] in ("-C", "--chdir") and i + 1 < len(words):
                    ctx["cwd"] = os.path.join(ctx["cwd"], words[i + 1])
                    i += 2
                    continue
                if words[i].startswith("--chdir="):
                    ctx["cwd"] = os.path.join(ctx["cwd"], words[i].split("=", 1)[1])
                elif words[i] in ("-u", "--unset") and i + 1 < len(words):
                    ctx.setdefault("assign", {})[words[i + 1]] = None
                    i += 1
                elif words[i] == "-S" and i + 1 < len(words):
                    i += 1
                elif "=" in words[i] and not words[i].startswith("-"):
                    k = words[i].split("=", 1)
                    ctx.setdefault("assign", {})[k[0]] = k[1]
                    if k[0] in ("GIT_DIR", "GIT_WORK_TREE"):
                        ctx["targets"].append(k[1])
                i += 1
        elif b in ("sudo", "nice"):
            i += 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in ("-u", "-g", "-n", "-C") and i + 1 < len(words) else 1
        elif b == "timeout":
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


# ── shared venv: EVERY session, not only seats (W-46d148b0) ────────────────────────────────────
# A linked worktree's `.venv` is a SYMLINK to the main checkout's venv (the synced settings'
# `worktree.symlinkDirectories`), so a sync or install into it rewrites the one runtime every agent
# of the repo shares — trade-intelligence 01M3RYGETKD5HQZRBTDF3EK3EK: twice in one day a worktree's
# `uv run` resolved SQLAlchemy 2.1 for everyone and re-pointed the editable install at a worktree.
# Refused when the write's target venv resolves to the venv a linked worktree shares through its
# `.venv` symlink — that worktree being the call's directory, the session's cwd, or the target's
# own. Writers: `uv run|sync|add|remove` (a project sync), `uv version` with a bump, `uv venv
# --clear|--allow-existing`, `uv pip install|sync|uninstall`, `pip|python -m pip
# install|uninstall`, and an installer `uv run --no-sync` starts in the project venv. Not writes:
# `--no-sync`/`UV_NO_SYNC`, `add|remove|version --frozen`/`UV_FROZEN`, `uv run
# --no-project|--isolated|--script|-s|--gui-script`, `uv sync --dry-run|--check`, help, pip
# `--dry-run|--target|--prefix|--root|--system|--user`. uv's options are read up to `uv run`'s
# command only — what follows is the command's. A pin the merge owner approved passes with the
# inline, visible `FABRIK_SHARED_VENV_WRITE=1` (an assignment, `env` or `export` in the command),
# never read from the inherited environment, so no settings file can switch the guard off.
# Fails OPEN on what it cannot resolve (a parse error, a `$VAR` or `$( )` path, `cd` with no
# argument or `~`, an unknown program): a missed write corrupts the shared runtime until the merge
# owner notices and re-syncs it, a wrongly refused one stops an agent's work, and a write the
# guard cannot see would pass a deny-by-default rule too. Not seen, stated: `make`, scripts,
# `find -exec`, pip-sync, poetry, pdm, hatch, a uv-workspace member resolving to the root's venv
# (0 of 44 fleet pyproject.toml files declare `tool.uv.workspace`, 2026-10-23).
# ⚠️ COBRA (D-253): the cheapest pass is a habitual `FABRIK_SHARED_VENV_WRITE=1` prefix — visible
# in every transcript, and the refusal offers it only for a pin the coordinator approved.
VENV_TAG = "shared venv guard"
VENV_OPT_IN = "FABRIK_SHARED_VENV_WRITE"
_TRUE = frozenset({"1", "true", "t", "yes", "y", "on"})
_UV_VERBS = frozenset(
    {"run", "init", "add", "remove", "version", "sync", "lock", "export", "tree", "format",
     "tool", "python", "pip", "venv", "build", "publish", "cache", "self", "help", "auth",
     "generate-shell-completion"}
)
_UV_WRITERS = frozenset({"run", "sync", "add", "remove", "version", "venv", "pip"})
# options whose VALUE is the next word (uv 0.11.31 `uv help run|sync|add|venv`, globals included)
_UV_VALUED = frozenset(
    {"--directory", "--project", "--color", "--cache-dir", "--config-file",
     "--allow-insecure-host", "--python-preference", "-p", "--python", "--with", "-w",
     "--with-editable", "--with-requirements", "--extra", "--no-extra", "--group", "--no-group",
     "--only-group", "--package", "--env-file", "--index", "--default-index", "-i",
     "--extra-index-url", "-f", "--find-links", "--exclude-newer", "--exclude-newer-package",
     "-P", "--upgrade-package", "-C", "--config-setting", "--index-strategy",
     "--keyring-provider", "--link-mode", "--prerelease", "--resolution", "--fork-strategy",
     "--refresh-package", "--reinstall-package", "--no-build-package", "--no-binary-package",
     "--prompt", "--bump", "--optional", "--branch", "--tag", "--rev", "--marker", "-m",
     "--script", "--dev-group", "--python-platform", "--output-format", "--bounds"}
)
_UV_HELP = frozenset({"-h", "--help", "-V", "--version"})
_UV_RUN_ELSEWHERE = frozenset({"--no-project", "--isolated", "--script", "-s", "--gui-script"})
_UV_PIP_WRITES = frozenset({"install", "sync", "uninstall"})
_PIP_WRITES = frozenset({"install", "uninstall"})
_PIP_ELSEWHERE = ("--dry-run", "--target", "-t", "--prefix", "--root", "--system", "--user")
_PIP_GLOBAL_VALUED = frozenset(
    {"--python", "--log", "--cache-dir", "--proxy", "--retries", "--timeout", "--exists-action",
     "--trusted-host", "--cert", "--client-cert", "--use-feature", "--use-deprecated",
     "--keyring-provider", "--src", "--resume-retries"}
)
_PIP_NAME = re.compile(r"^pip(3(\.\d+)?)?$")
_PY_NAME = re.compile(r"^python(3(\.\d+)?)?$")
_XARGS_VALUED = frozenset({"-a", "-I", "-n", "-P", "-d", "-E", "-L", "-s", "--arg-file",
                           "--delimiter", "--max-args", "--max-procs", "--max-lines"})
_WT = re.compile(r"^(.*?/\.claude/worktrees/[^/]+)(/|$)")


def _env(ctx: dict, name: str, inherited: bool = True) -> str | None:
    for layer in (ctx.get("assign") or {}, ctx.get("exported") or {}):
        if name in layer:
            return layer[name]
    return os.environ.get(name) if inherited else None


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in _TRUE


def _unknown(path: str | None) -> bool:
    return path is None or "$" in path or SUBST in path


def _shared_venv(path: str) -> tuple[str, str]:
    """(worktree, real path of its symlinked `.venv`) for the linked worktree holding ``path``."""
    if not path or _unknown(path):
        return "", ""
    m = _WT.match(os.path.abspath(path))
    if not m:
        return "", ""
    link = os.path.join(m.group(1), ".venv")
    return (m.group(1), os.path.realpath(link)) if os.path.islink(link) else ("", "")


def _nearest(start: str, name: str) -> str:
    cur = os.path.abspath(start)
    while True:
        if os.path.lexists(os.path.join(cur, name)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return ""
        cur = parent


def _venv_of(executable: str) -> str:
    """The venv directory an interpreter or pip path belongs to — never through the binary's own
    symlink (a venv's bin/python resolves to the base interpreter)."""
    path = os.path.abspath(executable)
    parent = os.path.dirname(path)
    return os.path.dirname(parent) if os.path.basename(parent) in ("bin", "Scripts") else path


def _which(program: str, ctx: dict) -> str:
    """``program`` resolved the way the call's shell would: a path against its cwd, a bare name
    against its PATH (relative entries made absolute against that cwd)."""
    if "/" in program:
        return "" if _unknown(program) else os.path.join(ctx["cwd"], program)
    entries = (_env(ctx, "PATH") or "").split(":")
    path = ":".join(e if os.path.isabs(e) else os.path.join(ctx["cwd"], e) for e in entries if e)
    return shutil.which(program, path=path) or ""


def _venv_msg(act: str, target: str, worktree: str) -> str:
    real = os.path.realpath(target)
    return (
        f"{VENV_TAG}: {act} writes {real}, the venv the worktree {worktree} shares with every "
        "agent of this repo through its `.venv` symlink — a worktree's lock or src would replace "
        "their runtime. To run on it as it is, use `uv run --no-sync <cmd>` or `.venv/bin/python` "
        "directly. A package or a sync is the merge owner's act: ask the coordinator; a pin it "
        f"approved runs as `{VENV_OPT_IN}=1 uv pip install --python {real}/bin/python "
        "<pkg>==<version>`"
    )


def _flagged(args: list[str], names: tuple[str, ...] | frozenset[str]) -> bool:
    return any(a in names or a.split("=", 1)[0] in names for a in args)


def _with_venv(ctx: dict, venv: str) -> dict:
    """``ctx`` for a command running inside ``venv`` (`uv run` puts it first on PATH)."""
    exported = {**(ctx.get("exported") or {}), **(ctx.get("assign") or {})}
    exported["VIRTUAL_ENV"] = venv
    exported["PATH"] = os.path.join(venv, "bin") + ":" + (_env(ctx, "PATH") or "")
    return {**ctx, "assign": {}, "exported": exported}


def _pip_target(program: str, args: list[str], ctx: dict) -> tuple[str, str]:
    verb, k = "", 0
    while k < len(args):  # pip's global options before the verb; a valued one hides its value
        if not args[k].startswith("-"):
            verb = args[k]
            break
        k += 2 if args[k] in _PIP_GLOBAL_VALUED else 1
    if verb not in _PIP_WRITES or _flagged(args, _PIP_ELSEWHERE + ("-h", "--help")):
        return "", ""
    for k, a in enumerate(args):  # pip's own global `--python` names the target environment
        if a == "--python" and k + 1 < len(args) and not _unknown(args[k + 1]):
            return f"`pip {verb}`", _venv_of(os.path.join(ctx["cwd"], args[k + 1]))
        if a.startswith("--python=") and not _unknown(a.split("=", 1)[1]):
            return f"`pip {verb}`", _venv_of(os.path.join(ctx["cwd"], a.split("=", 1)[1]))
    path = _which(program, ctx)
    return (f"`{os.path.basename(program)} {verb}`", _venv_of(path)) if path else ("", "")


def _project_venv(start: str, d: str, ctx: dict, opts: list[str]) -> str:
    if "--active" in opts and _env(ctx, "VIRTUAL_ENV"):
        return os.path.join(d, _env(ctx, "VIRTUAL_ENV") or "")
    proj = _nearest(start, "pyproject.toml")
    if not proj:
        return ""
    env_dir = _env(ctx, "UV_PROJECT_ENVIRONMENT")
    return os.path.join(proj, env_dir) if env_dir else os.path.join(proj, ".venv")


def _uv_reason(args: list[str], ctx: dict, depth: int) -> str:
    d, project = ctx["cwd"], _env(ctx, "UV_PROJECT")
    if _env(ctx, "UV_WORKING_DIR"):
        d = os.path.join(d, _env(ctx, "UV_WORKING_DIR") or "")
    verb, opts, pos, cmd, i = "", [], [], [], 0
    while i < len(args):
        a = args[i]
        if verb == "pip":
            pos = args[i:]
            break
        if a == "--":
            cmd = args[i + 1 :] if verb == "run" else []
            break
        if a.startswith("-") and a != "-":
            key = a.split("=", 1)[0]
            val = a.split("=", 1)[1] if "=" in a else None
            step = 1
            if key in _UV_VALUED and val is None:
                val, step = (args[i + 1] if i + 1 < len(args) else ""), 2
            if key == "--directory" and val is not None:
                d = os.path.join(d, val) if not _unknown(val) else SUBST
            elif key == "--project" and val is not None:
                project = val
            opts.append(key)
            i += step
            continue
        if not verb:
            if a not in _UV_VERBS:  # a value we did not know took one: find the verb itself
                j = next((k for k in range(i + 1, len(args)) if args[k] in _UV_WRITERS), None)
                if j is None:
                    return ""
                i = j
                a = args[i]
            verb = a
            i += 1
            continue
        if verb == "run":
            cmd = args[i:]
            break
        pos.append(a)
        i += 1
    if not verb or _unknown(d) or (project is not None and _unknown(project)):
        return ""
    if _flagged(opts, _UV_HELP):
        return ""
    start = os.path.join(d, project) if project else d
    no_sync = "--no-sync" in opts or _truthy(_env(ctx, "UV_NO_SYNC"))
    frozen = "--frozen" in opts or _truthy(_env(ctx, "UV_FROZEN"))
    act, target, inner = f"`uv {verb}`", "", ""
    if verb == "run":
        if _flagged(opts, _UV_RUN_ELSEWHERE) or _truthy(_env(ctx, "UV_NO_PROJECT")) or _truthy(
            _env(ctx, "UV_ISOLATED")
        ):
            return ""
        venv = _project_venv(start, d, ctx, opts)
        if venv and cmd and depth < 3:
            inner = _venv_reason(cmd, _with_venv(ctx, venv), depth + 1)
        target = "" if no_sync else venv
    elif verb == "sync":
        if not (no_sync or _flagged(opts, ("--dry-run", "--check"))):
            target = _project_venv(start, d, ctx, opts)
    elif verb in ("add", "remove"):
        if not (no_sync or frozen or "--dry-run" in opts):
            target = _project_venv(start, d, ctx, opts)
    elif verb == "version":
        if ("--bump" in opts or pos) and not (no_sync or frozen or "--dry-run" in opts):
            target = _project_venv(start, d, ctx, opts)
    elif verb == "venv":
        if _flagged(opts, ("-c", "--clear", "--allow-existing")) or _truthy(
            _env(ctx, "UV_VENV_CLEAR")
        ):
            target = os.path.join(d, pos[0] if pos else ".venv")
    elif verb == "pip" and pos and pos[0] in _UV_PIP_WRITES:
        act, pargs = f"`uv pip {pos[0]}`", pos[1:]
        if _flagged(pargs, _PIP_ELSEWHERE + ("-h", "--help")):
            return ""
        py = None
        for k, a in enumerate(pargs):
            if a in ("--python", "-p") and k + 1 < len(pargs):
                py = pargs[k + 1]
            elif a.startswith("--python="):
                py = a.split("=", 1)[1]
        if py and _unknown(py):
            return ""
        if py and "/" in py:
            target = _venv_of(os.path.join(d, py))
        elif _env(ctx, "VIRTUAL_ENV"):
            target = os.path.join(d, _env(ctx, "VIRTUAL_ENV") or "")
        else:
            near = _nearest(d, ".venv")
            target = os.path.join(near, ".venv") if near else ""
    eds = _editables(pos[1:], ctx) if verb == "pip" else []
    return _judge(act, target, ctx, start, eds) or inner


def _editables(args: list[str], ctx: dict) -> list[str]:
    """The local paths an install names as editable (`-e <path>`): a worktree's src installed
    editable into the venv that worktree shares re-points it for every agent (01M3RYGETK)."""
    out = []
    for k, a in enumerate(args):
        val = None
        if a in ("-e", "--editable") and k + 1 < len(args):
            val = args[k + 1]
        elif a.startswith("--editable="):
            val = a.split("=", 1)[1]
        elif a.startswith("-e") and len(a) > 2 and not a.startswith("--"):
            val = a[2:]
        if val and not _unknown(val) and "://" not in val and SUBST not in ctx["cwd"]:
            out.append(os.path.join(ctx["cwd"], val))
    return out


def _judge(
    act: str, target: str, ctx: dict, start: str = "", editables: list[str] | None = None
) -> str:
    if not target or _unknown(target):
        return ""
    real = os.path.realpath(target)
    for where in (target, start, ctx["cwd"], ctx.get("home_cwd") or "", *(editables or [])):
        worktree, shared = _shared_venv(where)
        if shared and (real == shared or real.startswith(shared + "/")):
            if _truthy(_env(ctx, VENV_OPT_IN, inherited=False)):
                return ""
            return _venv_msg(act, target, worktree)
    return ""


def _venv_reason(words: list[str], ctx: dict, depth: int = 0) -> str:
    name = os.path.basename(words[0])
    if name == "xargs":  # the words after its options are the program it runs
        i = 1
        while i < len(words) and words[i].startswith("-"):
            i += 2 if words[i] in _XARGS_VALUED else 1
        return _venv_reason(words[i:], ctx, depth) if i < len(words) else ""
    if name == "uv":
        return _uv_reason(words[1:], ctx, depth)
    pip_args: list[str] | None = None
    if _PIP_NAME.match(name):
        pip_args = words[1:]
    elif _PY_NAME.match(name):
        args = words[1:]
        for k, a in enumerate(args):
            if a == "-m" and k + 1 < len(args):
                pip_args = args[k + 2 :] if args[k + 1] == "pip" else None
                break
            if a.startswith("-m") and len(a) > 2:
                pip_args = args[k + 1 :] if a[2:] == "pip" else None
                break
            if not a.startswith("-"):
                break
    if pip_args is None:
        return ""
    act, target = _pip_target(words[0], pip_args, ctx)
    return _judge(act, target, ctx, "", _editables(pip_args, ctx))


def _child(ctx: dict) -> dict:
    """``ctx`` for a child shell: it inherits this command's assignments and exports; its own
    `export` never leaks back (a fresh dict)."""
    exported = {**(ctx.get("exported") or {}), **(ctx.get("assign") or {})}
    return {**ctx, "targets": [], "dirs": [], "assign": {}, "exported": exported}


def _scan(command: str, ctx: dict, depth: int, seat: bool = True) -> str:
    raw_command = command
    try:
        command = _strip_comments(_strip_heredocs(command))
        inner, command = _extract_substitutions(command)
        cmds = _simple_commands(_split_punct(_tokens(command)))
    except _UnparseableError:
        if not seat:
            return ""  # the venv check fails open
        writes = "|".join(
            sorted(WORKTREE_VERBS | STORE_VERBS | {"stash", "branch", "tag", "config", "worktree"})
        )
        # any git … <write verb> on one command line, flags in between included; any kill word
        if re.search(rf"\bgit\b[^;&|\n]*?\s({writes})\b|\b(pkill|killall|kill)\b", raw_command):
            return "the command cannot be tokenised and names a git write or a kill"
        return ""
    if depth < 3:
        for sub in inner:
            reason = _scan(sub, _child(ctx), depth + 1, seat)
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
        ctx["targets"], ctx["git_dir"], ctx["work_tree"], ctx["assign"] = [], False, False, {}
        words = _strip(raw, ctx)
        if not words:
            continue
        head = os.path.basename(words[0])
        if head in ("cd", "pushd"):
            if head == "pushd":
                ctx.setdefault("dirs", []).append(ctx["cwd"])
            args = [w for w in words[1:] if not w.startswith("-") or w == "-"]
            if not args or args[0] == "-" or args[0].startswith("~"):
                ctx["cwd"] = SUBST  # HOME, OLDPWD or a tilde path: not resolved here
            else:
                ctx["cwd"] = os.path.join(ctx["cwd"], args[0])
            continue
        if head in ("export", "unset"):
            for w in words[1:]:
                k, eq, v = w.partition("=")
                if head == "unset":
                    ctx.setdefault("exported", {})[w] = None
                elif eq:
                    ctx.setdefault("exported", {})[k] = v
            continue
        if head in ("source", ".") and len(words) > 1:
            act = re.match(r"^(.*)/bin/activate$", words[1])
            if act and SUBST not in ctx["cwd"]:
                venv = os.path.join(ctx["cwd"], act.group(1))
                exp = ctx.setdefault("exported", {})
                exp["PATH"] = os.path.join(venv, "bin") + ":" + (_env(ctx, "PATH") or "")
                exp["VIRTUAL_ENV"] = venv
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
                        reason = _scan(rest[0], _child(ctx), depth + 1, seat)
                        if reason:
                            return reason
                    break
            continue
        reason = (
            (_kill_reason(words) or _git_reason(words, ctx)) if seat else ""
        ) or _venv_reason(words, ctx)
        if reason:
            return reason
    return ""


def decide(payload: dict) -> str:
    """The deny reason for this Bash call, or "" to allow."""
    seat = bool(payload.get("agent_id")) and payload.get("agent_type") in SEAT_TYPES
    command = (payload.get("tool_input") or {}).get("command") or ""
    sd = payload.get("scratchpad_dir")
    ctx = {
        "cwd": str(payload.get("cwd") or os.getcwd()),
        "targets": [],
        "dirs": [],
        "git_dir": False,
        "work_tree": False,
        "assign": {},
        "exported": {},
        "home_cwd": str(payload.get("cwd") or os.getcwd()),
        "sid": str(payload.get("session_id") or ""),
        "scratchpad": os.path.realpath(sd) if isinstance(sd, str) and sd else "",
    }
    reason = _scan(command, ctx, 0, seat)
    if reason.startswith(VENV_TAG):
        return reason
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
