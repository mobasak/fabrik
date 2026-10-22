#!/usr/bin/env python3
# AFTER-EDIT: tests/test_seat_guard.py, docs/workstation/hooks-index.md, .claude/settings.json
"""PreToolUse (Bash) seat guard — refuse a review seat's pattern kills, and its git and file writes outside scratch.

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
  * Writes (W-72dfd448, D-1116; spec docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md § The
    delta): a seat writes only under its scratch dir. The destinations judged are every output redirect (``>``,
    ``>>``, ``>|``, ``<>``, ``&>``, ``&>>``, ``>& <file>``) — on an empty, keyword, ``cd`` or ``bash -c`` line too —,
    ``tee``; ``cp``/``install``/``ln`` (last operand or ``-t``; ``install -d`` every operand; a one-operand ``ln``
    lands in the cwd); every operand of ``mv`` and ``rsync --remove-source-files``; ``rm``/``rmdir``/``unlink``/
    ``shred``/``touch``/``mkdir``/``truncate``/``gzip``/``gunzip``; ``sort -o``, ``curl -o``, ``wget -O``; in-place
    ``sed``/``perl``; ``dd of=``. ``/dev/…`` (lexically) is never a destination; ``~``, ``$``, a substitution, a brace or
    a ``..`` after a glob is outside scratch; a glob is judged by the directory before it; ``/tmp``,
    ``/tmp/claude-<uid>`` and ``/tmp/claude-<uid>/<slug>`` are never this seat's. An ``env -C`` moves the cwd for its
    own command only. Scratch here also means a repo's gitignored ``.tmp/`` (the D-836 run folder
    ``.tmp/runs/<sid>/`` and fabrik-lib's ``.tmp/<run>/`` seat folders), minus another session's ``.tmp/runs/<sid>/``
    and the ancestors ``.tmp`` and ``.tmp/runs``. A variable assigned a literal earlier on the line, ``$PWD``, and a
    ``for`` loop over plain words (none a ``/``, ``.`` or ``..``) are resolved; any other variable stays unknown.
    ``rsync -n`` writes nothing. (These came from replaying 54,727 real seat commands, D-1116 condition 2.)
    The rule runs inside its own ``try``: a bug in it never disarms the kill and git rules.
    Blind spots, verbatim from the spec § The delta: **The blind spot, stated (COBRA, D-253):** the cheapest way
    past the rule is a write the Bash string does not show — an interpreter (`python -c "open(p,'w')"`,
    `shutil.rmtree`), a script file, a write whose destinations come from stdin or a search (`xargs rm`, `find
    -delete`, `find -exec`), a write nested deeper than the scanner's three levels of `bash -c`/`$(…)`, a
    side-effect write by a tool run in the live tree (`pytest`'s `.pytest_cache`), and a variable holding the path
    (fail-closed only when the variable is the destination itself). The guard is defence-in-depth against ACCIDENTAL
    writes, not a boundary against an adversarial seat; the brief's prose stays as the second layer. Write verbs and
    forms outside the list are blind spots too: `chmod`/`chown`, `patch`, `split`, `tar -x`/`-C`, `unzip -d`,
    `bzip2`/`xz`, `curl -O` and a bare `wget URL` (both write into the cwd), `sed`'s `w file` and `s///w file`, and
    any other verb or form until a refused-or-missed seat write names it (§ Lifecycle, growth). A `$(…)`/backtick
    body is judged against the cwd from before the command line's own `cd` (the scanner extracts substitutions
    before it tracks `cd`): `cd <scratch> && v=$(touch x)` is refused and `cd <live> && v=$(touch x)` started in
    scratch is missed — accepted until a seat trips it, the tripwire below. **Tripwire:** a confirmed seat write to
    a live tree through an interpreter re-opens this design with approach D (below) or a filesystem-level fence.
  * Fail-CLOSED for a seat whose command cannot be tokenised AND mentions a git write verb, a
    kill word, or a write (a write verb as a command word, an in-place sed/perl, an output redirect
    other than to /dev/… or an fd); otherwise fail-open (any error, a malformed payload) with exit 0
    and no output.
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

import io
import json
import os
import re
import shlex
import subprocess
import sys

SEAT_TYPES = frozenset({"fabrik-reviewer"})
_OPS = frozenset({";", "&&", "||", "|", "&", "(", ")", "\n", ";;", "|&"})
_REDIR = frozenset({"<", ">", ">>", "<<", "<<<", ">&", "<&", "&>", "&>>", ">|", "<>"})
# redirects whose target is a file the shell opens for WRITING (`>&` only when its target is not an fd)
_OUT_REDIR = frozenset({">", ">>", ">|", "&>", "&>>", ">&", "<>"})
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


def _tokens_at(command: str) -> list[tuple[str, int]]:
    """Each token with the source offset shlex has read to after it (one character of lookahead
    included) — the only place whitespace between tokens is still visible."""
    stream = io.StringIO(command)
    lex = shlex.shlex(stream, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    out: list[tuple[str, int]] = []
    try:
        while True:
            tok = lex.get_token()
            if tok is None:
                return out
            out.append((tok, stream.tell()))
    except ValueError as exc:
        raise _UnparseableError(str(exc)) from exc


def _tokens(command: str) -> list[str]:
    return [t for t, _ in _tokens_at(command)]


# `<<` and `<<-` open a heredoc; `<<<` is a here-string, which opens nothing (W-72dfd448)
_HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
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
    "<>",
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
    i, n, in_double = 0, len(command), False
    while i < n:
        c = command[i]
        if c == "\\" and i + 1 < n:
            out.append(
                command[i : i + 2]
            )  # an escaped quote, backtick or `$` is data (W-72dfd448 replay)
            i += 2
            continue
        if c == "'" and not in_double:
            j = command.find("'", i + 1)
            if j == -1:
                out.append(command[i:])
                break
            out.append(command[i : j + 1])
            i = j + 1
            continue
        if c == '"':
            in_double = not in_double
            out.append(c)
            i += 1
            continue
        if (
            command[i : i + 2] == "$("
            or c == "`"
            or (command[i : i + 2] in ("<(", ">(") and not in_double)
        ):
            if c == "`":
                j = i + 1
                while j < n and command[j] != "`":
                    j += 2 if command[j] == "\\" else 1
                if j >= n:
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


def _split_punct(tokens: list) -> list:
    """shlex merges an adjacent run of punctuation (`);`, `&&(`) into one token — split it.

    Takes plain tokens or ``(token, offset)`` pairs; a split piece's offset is None (unknown)."""
    out: list = []
    for item in tokens:
        tok, at = item if isinstance(item, tuple) else (item, None)
        if tok and all(ch in ";&|()<>\n" for ch in tok) and tok not in _OPS | _REDIR:
            k = 0
            while k < len(tok):
                for op in _OP_ORDER:
                    if tok.startswith(op, k):
                        piece = op
                        break
                else:
                    piece = tok[k]
                out.append((piece, None) if isinstance(item, tuple) else piece)
                k += len(piece)
        else:
            out.append(item)
    return out


class _Cmd(list):
    """One simple command's words, plus ``redirs``: the ``(operator, target)`` of every redirect on it."""

    redirs: list[tuple[str, str]]

    def __init__(self) -> None:
        super().__init__()
        self.redirs = []


def _glued_fd(prev: tuple[str, int | None], op: tuple[str, int | None], source: str) -> bool:
    """An all-digit word is an fd number only when nothing separates it from the redirect operator
    and it is not quoted (``2>x``; ``2 >x`` and ``"2">x`` write the file ``x`` and keep the word)."""
    (word, w_at), (sym, o_at) = prev, op
    if not word.isdigit() or w_at is None or o_at is None:
        return False
    return (
        o_at - w_at == len(sym) and 2 <= w_at <= len(source) + 1 and source[w_at - 2] not in "\"'"
    )


def _simple_commands(tokens: list, source: str = "") -> list[list[str]]:
    """Split at operators; each command is a ``_Cmd`` carrying its redirects (W-72dfd448). A command
    whose word list is empty still carries them (``> f``, ``{ …; } > f``, ``(…) > f``)."""
    items = [t if isinstance(t, tuple) else (t, None) for t in tokens]
    out: list[list[str]] = []
    cur = _Cmd()
    prev: tuple[str, int | None] | None = None
    k = 0
    while k < len(items):
        tok, at = items[k]
        if tok in _OPS:
            if cur or cur.redirs:
                out.append(cur)
            cur = _Cmd()
            if tok in ("(", ")"):
                out.append([tok])  # subshell scope marker
            prev = None
        elif tok in _REDIR:
            if cur and prev is not None and _glued_fd(prev, (tok, at), source):
                cur.pop()  # `2>` — the fd number is not a word
            target = (
                items[k + 1][0]
                if k + 1 < len(items) and items[k + 1][0] not in _OPS | _REDIR
                else ""
            )
            if (
                tok in _OUT_REDIR
                and target
                and not (tok == ">&" and (target.isdigit() or target == "-"))
            ):
                cur.redirs.append((tok, target))
            k += 2 if target else 1  # the redirect's target file is not an argument
            prev = None
            continue
        else:
            cur.append(tok)
            prev = (tok, at)
        k += 1
    if cur or cur.redirs:
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


# --- the write rule (W-72dfd448, D-1116): a seat writes only under its scratch dir -----------------------------------
_ANCESTOR = re.compile(
    r"^/tmp(/claude-\d+(/[^/]+)?)?/?$"
)  # /tmp, /tmp/claude-<uid>, /tmp/claude-<uid>/<slug>
_GLOB = "*?["


def _dest_outside(path: str, base: str, ctx: dict) -> bool:
    """True when a write to ``path`` (relative to ``base``) may land outside this seat's scratch."""
    if not path:
        return False
    if path.startswith("~") or SUBST in path or "$" in path or "{" in path or SUBST in base:
        return True  # home, a substitution, a variable or a brace expansion: unknown, so outside
    full = path if os.path.isabs(path) else os.path.join(base, path)
    lexical = os.path.normpath(full)
    if lexical == "/dev" or lexical.startswith("/dev/"):
        return False  # a device sink (/dev/null, /dev/stderr) — judged lexically: realpath follows its symlinks
    if any(c in full for c in _GLOB):
        first = min(full.index(c) for c in _GLOB if c in full)
        if ".." in full[first:].split("/"):
            return True  # a `..` after a glob can climb out of the directory the glob starts in
        full = full[: full.rindex("/", 0, first)] or "/"
    real = os.path.realpath(full)
    if _ANCESTOR.match(real):
        return True  # an ancestor of other sessions' scratch is never this seat's
    return not (_in_scratch(full, ctx) or _repo_tmp(real, ctx))


def _repo_tmp(real: str, ctx: dict) -> bool:
    """A path inside a repo's gitignored ``.tmp/`` — the D-836 run scratch ``.tmp/runs/<sid>/`` and the seat
    folders fabrik-lib's briefs name — minus another session's ``.tmp/runs/<sid>/`` and the ancestors ``.tmp`` and
    ``.tmp/runs`` (the false-refusal replay, D-1116 condition 2: 2,280 of 2,713 refusals were these folders)."""
    parts = real.split("/")
    if ".tmp" not in parts:
        return False
    rest = [p for p in parts[parts.index(".tmp") + 1 :] if p]
    if not rest:
        return False
    if rest[0] == "runs":
        return len(rest) > 1 and (not ctx.get("sid") or rest[1] == ctx["sid"])
    return True


_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _expand(word: str, ctx: dict) -> str:
    """``$NAME``/``${NAME}`` replaced by a literal this command line assigned earlier; any other stays (unknown)."""
    known = dict(ctx.get("vars") or {})
    cwd = ctx.get("cwd") or SUBST
    if SUBST not in cwd and "$" not in cwd:
        known.setdefault("PWD", cwd)  # the shell's own $PWD is the cwd the scanner tracks
    return _VAR.sub(lambda m: known.get(m.group(1) or m.group(2), m.group(0)), word)


def _record_assignments(words: list[str], ctx: dict) -> None:
    """A line of bare assignments (``S=/tmp/x``, ``export S=…``) sets shell variables; a literal value is
    remembered, anything else (a substitution, an unknown variable) forgets the name."""
    if (
        len(words) >= 2
        and words[0] == "for"
        and _ASSIGN.match(words[1] + "=")
        and "=" not in words[1]
    ):
        # `for m in a b c`: every value lands in one directory when none is a path piece (`/`, `.`, `..`)
        values = [_expand(v, ctx) for v in words[3:]] if words[2:3] == ["in"] else []
        if values and all(
            v not in (".", "..") and not any(ch in v for ch in ("/", "$", "`", SUBST))
            for v in values
        ):
            ctx.setdefault("vars", {})[words[1]] = values[0]
        else:
            ctx.setdefault("vars", {}).pop(words[1], None)
        return
    body = words[1:] if words and words[0] in ("export", "readonly", "declare", "local") else words
    if not body or not all(_ASSIGN.match(w) for w in body):
        return
    known = ctx.setdefault("vars", {})
    for w in body:
        name, value = _ASSIGN.match(w).groups()  # type: ignore[union-attr]
        value = _expand(value, ctx)
        if "$" in value or SUBST in value or "`" in value:
            known.pop(name, None)
        else:
            known[name] = value


def _operands(args: list[str], takes_value: frozenset[str]) -> tuple[list[str], dict[str, str]]:
    """Positional operands, and the values of the options in ``takes_value`` (``-x V``, ``-xV``,
    ``--long V``, ``--long=V``). A short flag cluster ending in a value option takes the next word."""
    ops: list[str] = []
    vals: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            ops.extend(args[i + 1 :])
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            if name in takes_value:
                if eq:
                    vals[name] = val
                elif i + 1 < len(args):
                    vals[name] = args[i + 1]
                    i += 1
        elif a.startswith("-") and len(a) > 1:
            for k in range(1, len(a)):
                flag = "-" + a[k]
                if flag in takes_value:
                    if k + 1 < len(a):
                        vals[flag] = a[k + 1 :]
                    elif i + 1 < len(args):
                        vals[flag] = args[i + 1]
                        i += 1
                    break
                vals.setdefault("cluster:" + a[k], "")
        else:
            ops.append(a)
        i += 1
    return ops, vals


def _short_flags(args: list[str]) -> set[str]:
    return {ch for a in args if a.startswith("-") and not a.startswith("--") for ch in a[1:]}


_EVERY_OPERAND = {
    "rm": frozenset(),
    "rmdir": frozenset(),
    "unlink": frozenset(),
    "shred": frozenset({"-n", "-s", "--iterations", "--size", "--random-source"}),
    "touch": frozenset({"-r", "-d", "-t", "--reference", "--date"}),
    "mkdir": frozenset({"-m", "--mode", "--context"}),
    "truncate": frozenset({"-s", "-r", "-o", "--size", "--reference"}),
    "gzip": frozenset({"-S", "--suffix"}),
    "gunzip": frozenset({"-S", "--suffix"}),
}
_TARGET_DIR = frozenset({"-t", "--target-directory"})


def _destinations(words: list[str], cwd: str) -> list[tuple[str, str]]:
    """The paths a command writes, each with the directory it is relative to (spec § The delta 2)."""
    name, args = os.path.basename(words[0]), words[1:]
    out: list[str] = []
    if name in _EVERY_OPERAND:
        ops, vals = _operands(args, _EVERY_OPERAND[name])
        if name in ("gzip", "gunzip") and (
            set(args) & {"--stdout", "--to-stdout", "--list", "--test"}
            or _short_flags(args) & set("clt")
        ):
            return []
        out = ops
    elif name == "tee":
        out, _ = _operands(args, frozenset())
    elif name in ("cp", "install", "ln", "mv"):
        extra = (
            frozenset({"-m", "-o", "-g", "--mode", "--owner", "--group"})
            if name == "install"
            else frozenset()
        )
        ops, vals = _operands(args, _TARGET_DIR | frozenset({"-S", "--suffix"}) | extra)
        target = vals.get("-t") or vals.get("--target-directory")
        if name == "mv":
            out = ops + ([target] if target else [])  # mv deletes every source
        elif name == "install" and "cluster:d" in vals:
            out = ops  # install -d creates every operand
        elif target:
            out = [target]
        elif name == "ln" and len(ops) == 1:
            out = [os.path.basename(ops[0].rstrip("/"))]  # one operand: the link lands in the cwd
        elif len(ops) >= 2:
            out = [ops[-1]]
    elif name == "rsync":
        ops, _ = _operands(
            args, frozenset({"-e", "--rsh", "--exclude", "--include", "--filter", "-f"})
        )
        local = [o for o in ops if not re.match(r"^[^/]*:", o)]
        if "--dry-run" in args or "n" in _short_flags(args):
            return []  # a dry run writes nothing
        out = local if "--remove-source-files" in args else local[-1:]
    elif name in ("sort", "curl", "wget"):
        opt = {
            "sort": ("-o", "--output"),
            "curl": ("-o", "--output"),
            "wget": ("-O", "--output-document"),
        }[name]
        _, vals = _operands(args, frozenset(opt))
        out = [v for v in (vals.get(opt[0]), vals.get(opt[1])) if v and v != "-"]
    elif name == "sed":
        inplace = any(a.startswith("--in-place") for a in args) or any(
            a.startswith("-") and not a.startswith("--") and "i" in a[1:] for a in args
        )
        if inplace:
            script_given = any(
                a in ("-e", "-f") or a.startswith(("--expression", "--file")) for a in args
            ) or any(
                a.startswith("-")
                and not a.startswith("--")
                and re.search(r"[ef]", a.split("i", 1)[0][1:])
                for a in args
            )
            ops, _ = _operands(
                [
                    a
                    for a in args
                    if not (a.startswith("-") and not a.startswith("--") and "i" in a[1:])
                ],
                frozenset({"-e", "-f", "-l", "--expression", "--file", "--line-length"}),
            )
            out = ops if script_given else ops[1:]
    elif name == "perl":
        clusters = [
            a for a in args if a.startswith("-") and not a.startswith(("--", "-M", "-m", "-I"))
        ]
        if any("i" in a[1:] for a in clusters):
            code_given = any(a[-1:] in ("e", "E") for a in clusters)
            ops, _ = _operands(
                [a for a in args if not (a.startswith("-") and a[-1:] in ("e", "E"))]
                if code_given
                else args,
                frozenset({"-M", "-m", "-I"}),
            )
            out = ops[1:]  # the first remaining word is the -e code, or with no -e the script file
    elif name == "dd":
        out = [a[3:] for a in args if a.startswith("of=")]
    return [(p, cwd) for p in out]


def _write_reason(
    words: list[str], redirs: list[tuple[str, str]], ctx: dict, cwd_before: str
) -> str:
    """'' or the reason this command writes outside the seat's scratch (W-72dfd448)."""
    dests = [(target, cwd_before) for _, target in redirs]
    if words:
        dests += _destinations(words, ctx["cwd"])
    for path, base in dests:
        if _dest_outside(path, base, ctx):
            shown = path if os.path.isabs(path) or SUBST in base else os.path.join(base, path)
            return f"a review seat writes only under its scratch dir — {shown} is outside it"
    return ""


def _safe_write_reason(
    words: list[str], redirs: list[tuple[str, str]], ctx: dict, cwd_before: str
) -> str:
    """The write rule inside its own try: a bug in it never disarms the kill and git rules (D-1116)."""
    try:
        return _write_reason(words, redirs, ctx, cwd_before)
    except Exception:
        return ""


def _scan(command: str, ctx: dict, depth: int) -> str:
    raw_command = command
    try:
        command = _strip_heredocs(command)
        inner, command = _extract_substitutions(command)
        cmds = _simple_commands(_split_punct(_tokens_at(command)), command)
    except _UnparseableError:
        writes = "|".join(
            sorted(WORKTREE_VERBS | STORE_VERBS | {"stash", "branch", "tag", "config", "worktree"})
        )
        # any git … <write verb> on one command line, flags in between included; any kill word
        if re.search(rf"\bgit\b[^;&|\n]*?\s({writes})\b|\b(pkill|killall|kill)\b", raw_command):
            return "the command cannot be tokenised and names a git write or a kill"
        # a write verb as a command word (not a path piece or an option: `/tmp/cp`, `--rm`), an in-place
        # sed/perl, or an output redirect to something other than /dev/… or an fd (W-72dfd448)
        if re.search(
            r"(?<![-/.\w])(tee|cp|mv|install|rsync|ln|rm|rmdir|unlink|shred|touch|mkdir|truncate|gzip|gunzip|dd)\b"
            r"|\b(sed|perl)\b[^;&|\n]*\s-\w*i"
            r"|(?<![<>&\d])\d*>{1,2}\|?\s*(?!/dev/|&|\d)\S",
            raw_command,
        ):
            return "the command cannot be tokenised and names a write (a review seat writes only under its scratch dir)"
        return ""
    if depth < 3:
        for sub in inner:
            reason = _scan(
                sub,
                {**ctx, "targets": [], "dirs": [], "vars": dict(ctx.get("vars") or {})},
                depth + 1,
            )
            if reason:
                return reason
    scopes: list[tuple[str, list[str], dict[str, str]]] = []
    for raw in cmds:
        if raw == ["("]:
            scopes.append((ctx["cwd"], list(ctx.get("dirs", [])), dict(ctx.get("vars") or {})))
            continue
        if raw == [")"]:
            if scopes:
                ctx["cwd"], ctx["dirs"], ctx["vars"] = (
                    scopes.pop()
                )  # a subshell's cd, pushd and variables die with it
            continue
        ctx["targets"], ctx["git_dir"], ctx["work_tree"] = [], False, False
        cwd_before = ctx["cwd"]
        redirs = [(op, _expand(t, ctx)) for op, t in getattr(raw, "redirs", [])]
        _record_assignments(list(raw), ctx)
        words = _strip([_expand(w, ctx) for w in raw], ctx)
        # the write rule runs first, so a redirect on an empty, keyword, cd or bash -c line is judged;
        # redirects resolve against the cwd before an `env -C`, operands against the moved one
        reason = _safe_write_reason(words, redirs, ctx, cwd_before)
        if reason:
            return reason
        if not words:
            ctx["cwd"] = cwd_before
            continue
        head = os.path.basename(words[0])
        if head in ("cd", "pushd"):
            ctx["cwd"] = cwd_before  # an `env -C dir cd x` is not a shell cd into dir
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
                        reason = _scan(
                            rest[0],
                            {**ctx, "targets": [], "dirs": [], "vars": dict(ctx.get("vars") or {})},
                            depth + 1,
                        )
                        if reason:
                            return reason
                    break
            ctx["cwd"] = cwd_before
            continue
        reason = _kill_reason(words) or _git_reason(words, ctx)
        ctx["cwd"] = cwd_before  # `env -C` moves the cwd for its own command only
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
