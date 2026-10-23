#!/usr/bin/env python3
# AFTER-EDIT: tests/test_seat_guard.py, docs/workstation/hooks-index.md, .claude/settings.json
"""PreToolUse (Bash) seat guard — refuse a review seat's pattern kills, and its git and file writes outside scratch.

FENCE MODE (W-72dfd448 Phase B, D-1129): where ``/usr/bin/bwrap`` runs, a seat's whole command is wrapped by
``rewrite()`` in a bubblewrap filesystem fence — read-only everywhere but the scratchpad, the session's run folder
and a seeded run's record scratch; docker, D-Bus, tmux and the WSL interop masked — so the OS, not this parser,
is the boundary, and the write rule below does not run. Where bwrap cannot run (absent, the probe failing, no
``scratchpad_dir``) the parser below is the FALLBACK: it refuses the constructs it does not model and fails
closed for a seat on its own crash. Residuals either way: localhost TCP and other sockets, the per-session
width, the settings entry's fail-open. COBRA (D-253): the test seams ``SEAT_GUARD_BWRAP`` and
``SEAT_GUARD_CACHE`` choose inputs, never the mode, so a test cannot fake the fence by skipping the probe.

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
    own command only. Scratch here also means a repo's ``.tmp/`` (gitignored by convention, not checked) — a ``.tmp`` whose parent holds
    ``.git``, outside ``/tmp`` (the D-836 run folder ``.tmp/runs/<sid>/`` and fabrik-lib's ``.tmp/<run>/`` seat
    folders) — minus another session's ``.tmp/runs/<sid>/`` and the ancestors ``.tmp`` and ``.tmp/runs``. For the
    write rule and a ``cd`` target only (the kill and git rules still refuse any ``$``), a variable is resolved when
    the line assigned it a literal unconditionally — at depth 0 of ``do``/``then``/``{``, not in a pipeline or a
    background job, not after ``&&``/``||`` unless the ``&&`` chain is unbroken — and nothing since could have
    changed it (``unset``, ``read``, ``printf -v``, ``declare``, ``eval``, ``export -n``, ``+=`` forget it); a value
    with whitespace, a glob, ``~``, ``{`` or a ``$`` is never resolved; ``$PWD`` is the tracked cwd; a ``for`` loop
    over plain words is judged once per value; a ``bash -c`` script starts with no variables. A quoted or escaped
    operator or ``$`` is data (``grep '>' f``, ``touch '$S'``). A ``cd`` in a pipeline changes nothing, and a ``cd``
    not guarded by ``&&`` into a directory that is missing (and not made earlier on the line) leaves the cwd
    unknown. ``rsync -n`` writes nothing. (These came from replaying 55,791 real seat commands, D-1116 condition 2,
    and from the Phase A review's round 1.) The rule runs inside its own ``try``: a bug in it never disarms the kill
    and git rules.
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
    Also blind, found by the Phase A review: a symlink made earlier on the same line (``ln -s /opt/x <scratch>/l;
    rm -rf <scratch>/l/src`` — the guard resolves links that exist when it runs), and a ``$(…)`` body never sees a
    variable the outer line assigned (a false refusal, not a miss). Round 2 added: a ``case`` arm is conditional;
    ``IFS= read``, ``builtin read``, ``command unset``, ``printf -vS`` clear the table; ``$'…'`` and ``$((…))`` are
    data to the comment and heredoc scanners; a ``cd`` into a missing directory is certain only within its ``&&``
    chain; only a ``mkdir`` (ancestors with ``-p``; without it, only under an existing parent) makes a directory a
    later ``cd`` on the line may enter — so ``git worktree add x; cd x``, ``tar -C``, ``unzip -d`` and a ``venv``
    refuse the next relative write until joined with ``&&`` (a stated cost, review round 3); a glob is refused
    when the directory it expands in holds a link out of scratch (one listing, never a walk — the hook has 5 s), so
    ``rm -rf <scratch>/*`` there is refused even though it would remove only the link, and a link in a deeper
    directory the glob passes through is not seen.
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

import hashlib
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
    lex.commenters = (
        ""  # `_strip_comments` already cut them; shlex's own cut swallowed the newline after one
    )
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


def _ansi_end(s: str, i: int) -> int:
    """The offset just past the ``$'…'`` word starting at ``i`` (``\\'`` does not close it)."""
    j = i + 2
    while j < len(s) and s[j] != "'":
        j += 2 if s[j] == "\\" else 1
    return min(j + 1, len(s))


def _arith_end(s: str, i: int) -> int:
    """The offset just past the ``$((…))``/``((…))`` starting at ``i`` (a ``<<`` in it is a shift, not a heredoc)."""
    j = s.find("))", i)
    return len(s) if j == -1 else j + 2


def _line_syntax(line: str, quote: str = "") -> tuple[set[int], int, str]:
    """The offsets of ``line`` the shell reads as syntax (outside quotes, not escaped) and where its unquoted
    ``#`` comment starts (``len(line)`` when it has none) — so a ``<<EOF`` inside quotes or after ``#`` opens no
    heredoc, and a comment hides no next line (review round 1). ``quote`` is the quote still open from the line
    before, and the third value the one still open after this line (review round 3: a multi-line string)."""
    live: set[int] = set()
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if line.startswith(
            "$'", i
        ):  # review round 2: ANSI-C quoting is data, `\\'` does not close it
            i = _ansi_end(line, i)
            continue
        if line.startswith("$((", i) or (
            line.startswith("((", i) and (i == 0 or line[i - 1] in " \t;&|(")
        ):
            i = _arith_end(line, i)
            continue
        if c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t;&|("):
            return live, i, quote
        else:
            live.add(i)
        i += 1
    return live, n, quote


def _strip_comments(command: str) -> str:
    """Each line cut at its unquoted ``#`` comment, keeping the newline (shlex's own cut swallowed it)."""
    out: list[str] = []
    i, n, quote = (
        0,
        len(command),
        "",
    )  # the quote state carries across lines (a multi-line `-c '…'` script)
    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"':
                out.append(command[i : i + 2])
                i += 2
                continue
            quote = "" if c == quote else quote
        elif c == "\\":
            out.append(command[i : i + 2])
            i += 2
            continue
        elif command.startswith("$'", i):
            end = _ansi_end(command, i)
            out.append(command[i:end])
            i = end
            continue
        elif c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or command[i - 1] in " \t\n;&|("):
            j = command.find("\n", i)
            i = n if j == -1 else j  # drop the comment, keep its newline
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _strip_heredocs(command: str) -> str:
    """Drop heredoc BODIES (data written to a file), keeping the line that opens them."""
    out: list[str] = []
    pending: list[str] = []
    quote = ""
    for line in command.split("\n"):
        if pending:
            if line.strip("\t ") == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        quote_in = quote
        live, _, quote = _line_syntax(line, quote)
        if (
            not quote_in
        ):  # a line that starts inside a carried quote opens no heredoc: the scanner may
            # misread a quote it does not model (`"$(echo "'")"`), and opening one would hide the lines
            # after it, so a carried quote may only ever SUPPRESS a heredoc (review round 4)
            pending.extend(m.group(2) for m in _HEREDOC.finditer(line) if m.start() in live)
    return "\n".join(out)


# a character the shell takes literally (quoted or escaped) that would otherwise read as an operator or a
# variable: mapped to a private-use stand-in so `'>'` is a word and `'$S'` is never expanded (review round 1)
_LITERAL = ";&|()<>$"
_STAND_IN = {c: chr(0xE000 + ord(c)) for c in _LITERAL}
_UNSTAND = {v: k for k, v in _STAND_IN.items()}


def _protect(command: str) -> str:
    """``command`` with every quoted or escaped ``;&|()<>$`` replaced by its stand-in (``$`` stays live inside
    double quotes, as in the shell). Runs after ``_extract_substitutions``, so a ``$(…)`` is already a placeholder."""
    out: list[str] = []
    i, n, quote = 0, len(command), ""
    while i < n:
        c = command[i]
        if quote == "'":
            out.append(_STAND_IN.get(c, c))
            quote = "" if c == "'" else quote
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            nxt = command[
                i + 1
            ]  # an escaped operator or `$` is a literal character; anything else as written
            out.append(_STAND_IN[nxt] if nxt in _STAND_IN else command[i : i + 2])
            i += 2
            continue
        if quote == '"':
            out.append(c if c in '"$' else _STAND_IN.get(c, c))
            quote = "" if c == '"' else quote
            i += 1
            continue
        if command.startswith("$'", i):
            j = i + 2
            while j < n and command[j] != "'":
                j += 2 if command[j] == "\\" else 1
            body = command[
                i + 2 : j
            ]  # ANSI-C quoting: all literal; shlex reads it as a plain '…' word
            out.append("'" + "".join(_STAND_IN.get(ch, ch) for ch in body.replace("'", "")) + "'")
            i = j + 1
            continue
        if c in "'\"":
            quote = c
        out.append(c)
        i += 1
    return "".join(out)


def _shown(text: str) -> str:
    return "".join(_UNSTAND.get(ch, ch) for ch in text)


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
        if command.startswith("$'", i) and not in_double:
            j = (
                i + 2
            )  # ANSI-C quoting: `\'` does not close it, so a plain `'` scan would misplace the end
            while j < n and command[j] != "'":
                j += 2 if command[j] == "\\" else 1
            out.append(command[i : j + 1])
            i = j + 1
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
                # the shell un-escapes `\\`, `` \` `` and `\$` in a backtick body before running it, so a
                # nested `` \`…\` `` is a substitution of its own
                inner.append(re.sub(r"\\([\\`$])", r"\1", command[i + 1 : j]))
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
    before: str  # the operator that preceded it ("" at the start of the line)
    sep: str  # the operator that ended it ("" at the end of the line)

    def __init__(self, before: str = "") -> None:
        super().__init__()
        self.redirs = []
        self.before = before
        self.sep = ""


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
                cur.sep = tok
                out.append(cur)
            cur = _Cmd(before=tok)
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
        # ASCII digits only: `str.isdigit()` is true for `²`, which `int()` refuses (a raise fails the whole hook open)
        if re.fullmatch(r"%[1-9][0-9]*", a) or (re.fullmatch(r"[0-9]+", a) and int(a) > 1):
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
    if (
        path.startswith("~")
        or SUBST in path
        or "$" in path
        or "{" in path
        or (
            SUBST in base and not os.path.isabs(path)
        )  # an unknown cwd matters to a relative path only
    ):
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
        if _links_out(full, ctx):
            return True  # a glob here can expand through a link that points out of scratch
    real = os.path.realpath(full)
    if _ANCESTOR.match(real):
        return True  # an ancestor of other sessions' scratch is never this seat's
    return not (_in_scratch(full, ctx) or _repo_tmp(real, ctx))


_LIST_CAP = (
    4096  # entries read from one directory at most; a bigger one counts as holding a link out
)


def _links_out(directory: str, ctx: dict) -> bool:
    """True when ``directory`` (the one a glob expands in) holds a symlink pointing outside scratch, or is too big
    to list. One ``os.scandir`` of that directory only — never a walk, so the hook's 5 s budget holds (review
    round 3: a tree walk took 48 s). A link in a deeper directory the glob passes through is not seen."""
    try:
        with os.scandir(directory) as it:
            for k, entry in enumerate(it):
                if k >= _LIST_CAP:
                    return True
                if entry.is_symlink():
                    real = os.path.realpath(entry.path)
                    if not (_in_scratch(real, ctx) or _repo_tmp(real, ctx)):
                        return True
    except OSError:
        return False  # a directory that is not there holds no link
    return False


def _repo_tmp(real: str, ctx: dict) -> bool:
    """A path inside a repo's ``.tmp/`` (gitignored by convention; the test is a parent holding ``.git``) — the D-836 run scratch ``.tmp/runs/<sid>/`` and the seat
    folders fabrik-lib's briefs name — minus another session's ``.tmp/runs/<sid>/`` and the ancestors ``.tmp`` and
    ``.tmp/runs`` (the false-refusal replay, D-1116 condition 2: 2,280 of 2,713 refusals were these folders). A
    repo is a directory holding ``.git`` (a dir, or a worktree's file); a path under ``/tmp`` is the ``/tmp`` rule's,
    so another session's ``/tmp`` tree never becomes scratch through a ``.tmp`` inside it (review round 1)."""
    if real == "/tmp" or real.startswith("/tmp/"):
        return False
    parts = real.split("/")
    for k, part in enumerate(parts):
        if part != ".tmp" or not os.path.exists("/".join(parts[:k]) + "/.git"):
            continue
        rest = [p for p in parts[k + 1 :] if p]
        if not rest:
            return False
        if rest[0] == "runs":
            return len(rest) > 1 and (not ctx.get("sid") or rest[1] == ctx["sid"])
        return True
    return False


_VAR = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(\+?)=(.*)$")
# builtins that set or unset a variable some other way than `NAME=value`: one in a command forgets the table
_VAR_BUILTINS = frozenset(
    {
        "unset",
        "read",
        "mapfile",
        "readarray",
        "declare",
        "typeset",
        "local",
        "eval",
        "let",
        "getopts",
        "source",
        ".",
    }
)
_OPENS, _CLOSES = frozenset({"do", "then", "{"}), frozenset({"done", "fi", "}"})
_UNSAFE_VALUE = re.compile(r"[\s*?\[{~`$]|" + re.escape(SUBST))
_UNSAFE_LOOP = re.compile(r"[\s{~`$]|" + re.escape(SUBST))


_LOOP_CAP = 64  # destinations judged per word at most; past it the word stays unknown


def _expand(word: str, ctx: dict) -> str:
    """``$NAME``/``${NAME}`` replaced by a literal the line assigned earlier, as the WRITE rule judges it
    (the kill and git rules never see a resolved variable); anything else stays (unknown)."""
    known = dict(ctx.get("vars") or {})
    cwd = ctx.get("cwd") or SUBST
    if SUBST not in cwd and "$" not in cwd:
        known.setdefault("PWD", cwd)  # the shell's own $PWD is the cwd the scanner tracks
    return _VAR.sub(lambda m: known.get(m.group(1) or m.group(2), m.group(0)), word)


def _expansions(word: str, ctx: dict) -> list[str]:
    """Every word a ``for`` loop's variables can make of ``word``, one per value so each is judged (review
    round 1: ``for d in tmp opt; do rm -rf /$d/fabrik``), each then ``_expand``-ed; just ``_expand(word)`` when
    no loop variable is in it or the combinations pass ``_LOOP_CAP``."""
    out = [word]
    for name, values in (ctx.get("loopvars") or {}).items():
        pattern = re.compile(r"\$(\{" + re.escape(name) + r"\}|" + re.escape(name) + r"\b)")
        if name in (ctx.get("vars") or {}) or not pattern.search(word):
            continue
        out = [pattern.sub(lambda _m, v=v: v, w) for w in out for v in values]
        if len(out) > _LOOP_CAP:
            return [_expand(word, ctx)]
    return [_expand(w, ctx) for w in out]


def _record_assignments(raw: list[str], ctx: dict) -> None:
    """Keep the variable table conservative (review round 1): a ``NAME=literal`` line is remembered only when it
    runs unconditionally in this shell — at depth 0 of ``do``/``then``/``{``, not in a pipeline or background job,
    not after ``&&``/``||``. Any other assignment forgets its name; a builtin that sets variables another way
    (``unset``, ``read``, ``printf -v``, ``declare``, ``eval``, …) or ``export -n`` forgets the whole table. A
    value holding whitespace, a glob, ``~``, ``{``, a variable or a substitution is never remembered."""
    words = list(raw)
    known = ctx.setdefault("vars", {})
    loop = ctx.setdefault("loopvars", {})
    while words and words[0] in _KEYWORDS:
        if words[0] in _OPENS:
            ctx["depth"] = ctx.get("depth", 0) + 1
        elif words[0] in _CLOSES:
            ctx["depth"] = max(0, ctx.get("depth", 0) - 1)
        words = words[1:]
    if not words:
        return
    if words[0] == "case":
        ctx["depth"] = ctx.get("depth", 0) + 1  # every arm runs conditionally (review round 2)
    elif words[0] == "esac":
        ctx["depth"] = max(0, ctx.get("depth", 0) - 1)
    head = words[0]
    if head == "for" and len(words) >= 2:
        values = [_expand(v, ctx) for v in words[3:]] if words[2:3] == ["in"] else []
        # a plain word, or a glob with no `/` (its matches are names in the cwd; never one starting `.`,
        # which can match `.`/`..`); the name must be an identifier (review round 2: `for * in` raised)
        ok = (
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", words[1])
            and values
            and all(
                not v.startswith(".") and "/" not in v and not _UNSAFE_LOOP.search(v)
                for v in values
            )
        )
        known.pop(words[1], None)
        if ok:
            loop[words[1]] = values
        else:
            loop.pop(words[1], None)
        return
    # the command word behind assignments and `builtin`/`command` (review round 2: `IFS= read -r S`)
    cmd = (
        [w for w in words if not _ASSIGN.match(w)]
        if not all(_ASSIGN.match(w) for w in words)
        else []
    )
    while cmd and cmd[0] in ("builtin", "command"):
        cmd = cmd[1:]
        while cmd and cmd[0].startswith(
            "-"
        ):  # `command -p printf …`: its own flags, never the next word's
            cmd = cmd[1:]
    if cmd and (
        cmd[0] in _VAR_BUILTINS
        or (cmd[0] == "printf" and any(w.startswith("-v") for w in cmd))
        or (cmd[0] == "export" and "-n" in cmd)
    ):
        known.clear()
        loop.clear()
        return
    body = words[1:] if head in ("export", "readonly") else words
    if not body or not all(_ASSIGN.match(w) for w in body):
        return  # a command, maybe with `NAME=x` env prefixes, which set no shell variable
    before, sep = getattr(raw, "before", ""), getattr(raw, "sep", "")
    # inside an unbroken `a && S=x && b` chain the assignment is certain for the rest of the chain only
    chained = before == "&&" and sep == "&&"
    steady = (
        ctx.get("depth", 0) == 0
        and (before not in ("|", "&", "|&", "&&", "||") or chained)
        and sep not in ("|", "&", "|&")
    )
    for w in body:
        name, plus, value = _ASSIGN.match(w).groups()  # type: ignore[union-attr]
        value = _expand(value, ctx)
        loop.pop(name, None)
        if steady and not plus and not _UNSAFE_VALUE.search(value):
            known[name] = value
            if chained:
                ctx.setdefault("chain", []).append(name)
        else:
            known.pop(name, None)


def _operands(
    args: list[str], takes_value: frozenset[str], collect: list[str] | None = None
) -> tuple[list[str], dict[str, str]]:
    """Positional operands, and the values of the options in ``takes_value`` (``-x V``, ``-xV``,
    ``--long V``, ``--long=V``). A short flag cluster ending in a value option takes the next word.
    ``collect`` receives EVERY value given, where ``vals`` keeps only the last (``curl -o a u1 -o b u2``)."""
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
                if collect is not None and name in vals:
                    collect.append(vals[name])
        elif a.startswith("-") and len(a) > 1:
            for k in range(1, len(a)):
                flag = "-" + a[k]
                if flag in takes_value:
                    if k + 1 < len(a):
                        vals[flag] = a[k + 1 :]
                    elif i + 1 < len(args):
                        vals[flag] = args[i + 1]
                        i += 1
                    if collect is not None and flag in vals:
                        collect.append(vals[flag])
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
# rsync options that take a value, so a value that looks like `-n` is never read as the dry-run flag
_RSYNC_VALUE = frozenset(
    {
        "-e",
        "--rsh",
        "--exclude",
        "--include",
        "--filter",
        "-f",
        "-T",
        "--temp-dir",
        "-B",
        "--block-size",
        "--log-file",
        "--partial-dir",
        "--backup-dir",
        "--compare-dest",
        "--copy-dest",
        "--link-dest",
        "--exclude-from",
        "--include-from",
        "--files-from",
        "--chmod",
        "--chown",
        "--rsync-path",
        "--out-format",
        "--password-file",
        "-M",
        "--remote-option",
        "--suffix",
        "--usermap",
        "--groupmap",
    }
)


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
        ops, vals = _operands(args, _RSYNC_VALUE)
        local = [o for o in ops if not re.match(r"^[^/]*:", o)]
        flags = args[: args.index("--")] if "--" in args else args
        if "--dry-run" in flags or "cluster:n" in vals:
            return []  # a dry run writes nothing (an `-n` that is an option's VALUE is not one)
        out = local if "--remove-source-files" in flags else local[-1:]
    elif name in ("sort", "curl", "wget"):
        opt = {
            "sort": ("-o", "--output"),
            "curl": ("-o", "--output"),
            "wget": ("-O", "--output-document"),
        }[name]
        given: list[str] = []
        _operands(args, frozenset(opt), given)
        out = [v for v in given if v and v != "-"]
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
    dests = [(e, cwd_before) for _, target in redirs for e in _expansions(target, ctx)]
    if words:
        dests += [(e, b) for p, b in _destinations(words, ctx["cwd"]) for e in _expansions(p, ctx)]
    for path, base in dests:
        if _dest_outside(path, base, ctx):
            shown = path if os.path.isabs(path) or SUBST in base else os.path.join(base, path)
            return (
                f"a review seat writes only under its scratch dir — {_shown(shown)} is outside it"
            )
    return ""


def _safe_write_reason(
    words: list[str], redirs: list[tuple[str, str]], ctx: dict, cwd_before: str
) -> str:
    """The write rule inside its own try: a bug in it never disarms the kill and git rules (D-1116).

    Fence mode never calls it (the fence is the boundary); in FALLBACK mode a crash here DENIES, since
    the parser is then the only boundary (spec:146-148).
    """
    try:
        return _write_reason(words, redirs, ctx, cwd_before)
    except Exception as exc:
        return f"the write rule crashed in fallback mode ({type(exc).__name__}) — refused"


def _child(ctx: dict, inherit: bool) -> dict:
    """The context a nested scan starts from: a ``$(…)`` body inherits the shell's variables; a ``bash -c``
    child does not (only exported ones reach it, so the table starts empty — review round 1)."""
    return {
        **ctx,
        "targets": [],
        "dirs": [],
        "depth": 0,
        "vars": dict(ctx.get("vars") or {}) if inherit else {},
        "loopvars": dict(ctx.get("loopvars") or {}) if inherit else {},
    }


def _made_dirs(words: list[str], ctx: dict) -> list[str]:
    """Directories a ``mkdir`` creates, for a later ``cd`` on the line: every operand and its ancestors with
    ``-p``; without it, an operand whose parent exists or was made. Nothing else counts (review round 3: a ``cp``,
    ``git clone`` or ``venv`` may fail or make a file, and a ``cd`` after it would then stay in the old cwd)."""
    if os.path.basename(words[0]) != "mkdir":
        return []
    args = words[1:]
    parents = "p" in _short_flags(args) or "--parents" in args
    ops, _ = _operands(args, _EVERY_OPERAND["mkdir"])
    made = ctx.get("made") or set()
    out: list[str] = []
    for d in ops:
        full = _expand(d, ctx)
        if SUBST in full or "$" in full or any(c in full for c in _GLOB + "{~"):
            continue
        full = os.path.normpath(os.path.join(ctx["cwd"], full))
        if not parents and not (
            os.path.isdir(os.path.dirname(full)) or os.path.dirname(full) in made
        ):
            continue
        out.append(full)
        while parents and os.path.dirname(full) not in ("/", "", full):
            full = os.path.dirname(full)
            out.append(full)
    return out


def _cd_target(arg: str, raw: list[str], ctx: dict) -> str:
    """Where a ``cd`` leaves the shell. A ``cd`` that may fail (its directory missing now) and is not
    guarded by ``&&`` leaves the cwd unknown: the next command runs wherever the shell already was. A
    directory an earlier command on the line writes (``mkdir -p x; cd x``) counts as existing."""
    target = os.path.join(ctx["cwd"], arg)
    if SUBST in target or "$" in target:
        return target
    if os.path.isdir(target) or os.path.normpath(target) in (ctx.get("made") or set()):
        return target
    if getattr(raw, "sep", "") == "&&":
        ctx["cd_unsure"] = True  # certain only while the `&&` chain lasts (review round 2)
        return target
    return SUBST


def _scan(command: str, ctx: dict, depth: int) -> str:
    raw_command = command
    try:
        command = _strip_comments(_strip_heredocs(command))
        inner, command = _extract_substitutions(command)
        command = _protect(command)
        cmds = _simple_commands(_split_punct(_tokens_at(command)), command)
    except _UnparseableError:
        writes = "|".join(
            sorted(WORKTREE_VERBS | STORE_VERBS | {"stash", "branch", "tag", "config", "worktree"})
        )
        # any git … <write verb> on one command line, flags in between included; any kill word
        if re.search(rf"\bgit\b[^;&|\n]*?\s({writes})\b|\b(pkill|killall|kill)\b", raw_command):
            return "the command cannot be tokenised and names a git write or a kill"
        if ctx.get("fence"):
            return ""
        # a write verb as a command word (not a path piece or an option: `/tmp/cp`, `--rm`), an in-place
        # sed/perl, or an output redirect to something other than /dev/… or an fd (W-72dfd448)
        if re.search(
            r"(?<![-/.\w])(tee|cp|mv|install|rsync|ln|rm|rmdir|unlink|shred|touch|mkdir|truncate|gzip|gunzip|dd"
            r"|sort|curl|wget)\b"
            r"|\b(sed|perl)\b[^;&|\n]*\s-\w*i"
            r"|(?:(?<![<>&\d])\d*|(?<![<>&])&)>{1,2}\|?\s*(?!/dev/|&)\S",
            raw_command,
        ):
            return "the command cannot be tokenised and names a write (a review seat writes only under its scratch dir)"
        return ""
    if depth < 3:
        for sub in inner:
            reason = _scan(sub, _child(ctx, inherit=True), depth + 1)
            if reason:
                return reason
    scopes: list[tuple] = []
    for raw in cmds:
        if raw == ["("]:
            scopes.append(
                (
                    ctx["cwd"],
                    list(ctx.get("dirs", [])),
                    dict(ctx.get("vars") or {}),
                    dict(ctx.get("loopvars") or {}),
                    ctx.get("cd_unsure", False),
                )
            )
            continue
        if raw == [")"]:
            if scopes:
                # a subshell's cd, pushd and variables die with it
                ctx["cwd"], ctx["dirs"], ctx["vars"], ctx["loopvars"], ctx["cd_unsure"] = (
                    scopes.pop()
                )
            continue
        ctx["targets"], ctx["git_dir"], ctx["work_tree"] = [], False, False
        if getattr(raw, "before", "") != "&&":
            for name in ctx.pop("chain", []):  # the `&&` chain that made these certain has ended
                (ctx.get("vars") or {}).pop(name, None)
            if ctx.pop("cd_unsure", False):
                ctx["cwd"] = (
                    SUBST  # a `cd <missing> && …` may have failed: the shell is wherever it was
                )
        cwd_before = ctx["cwd"]
        words = _strip(list(raw), ctx)
        # the write rule runs first, so a redirect on an empty, keyword, cd or bash -c line is judged;
        # redirects resolve against the cwd before an `env -C`, operands against the moved one; this
        # line's own assignments are recorded after it is judged (the shell expands its words first)
        reason = (
            ""
            if ctx.get("fence")
            else _safe_write_reason(words, getattr(raw, "redirs", []), ctx, cwd_before)
        )
        _record_assignments(raw, ctx)
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
            if (
                args
                and getattr(raw, "sep", "") not in ("|", "&", "|&")
                and getattr(raw, "before", "") not in ("|", "|&")
            ):
                ctx["cwd"] = (
                    _cd_target(_expand(args[0], ctx), raw, ctx) if args[0] != "-" else SUBST
                )
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
                        # the script is shell text again: its quoted operators were stand-ins only for THIS line
                        reason = _scan(_shown(rest[0]), _child(ctx, inherit=False), depth + 1)
                        if reason:
                            return reason
                    break
            ctx["cwd"] = cwd_before
            continue
        ctx.setdefault("made", set()).update(_made_dirs(words, ctx))
        reason = _kill_reason(words) or _git_reason(words, ctx)
        ctx["cwd"] = cwd_before  # `env -C` moves the cwd for its own command only
        if reason:
            return reason
    return ""


def decide(payload: dict, mode: dict | None = None) -> str:
    """The deny reason for this Bash call, or "" to allow. ``mode`` is ``_fence_mode``'s answer;
    None means fallback (the parser is the boundary)."""
    if not payload.get("agent_id") or payload.get("agent_type") not in SEAT_TYPES:
        return ""
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return ""  # nothing will run, so nothing to judge (a malformed payload is not a crash)
    fence = bool(mode) and mode.get("mode") == "fence"
    if not fence:
        what = _unmodelled(command)
        if what:
            why = (mode or {}).get("why") or "no fence"
            return (
                f"seat guard (fallback mode — {why}): the command holds {what}, which the parser does not "
                f"model, so it is refused. {_SAFE}."
            )
    sd = payload.get("scratchpad_dir")
    ctx = {
        "cwd": str(payload.get("cwd") or os.getcwd()),
        "targets": [],
        "dirs": [],
        "git_dir": False,
        "work_tree": False,
        "sid": str(payload.get("session_id") or ""),
        "scratchpad": os.path.realpath(sd) if isinstance(sd, str) and sd else "",
        "fence": fence,
    }
    reason = _scan(command, ctx, 0)
    if reason:
        return f"seat guard (review seats run in the lead's shared tree): {reason}. {_SAFE}."
    return ""


# ---- the fence (W-72dfd448 Phase B; spec § Amendment 2026-10-22, D-1129) -------------------------
# A seat's whole command runs inside bubblewrap: the filesystem read-only, writable only the
# session scratchpad, the session's run folder and a seeded run's record scratch. The parser above
# stays as the FALLBACK where bwrap cannot run. COBRA (D-253): the cheapest way to make the fence
# tests pass without a fence is a seam that skips the probe — so the two seams below choose INPUTS
# (the binary, the cache file), never the mode itself.

_BWRAP_DEFAULT = "/usr/bin/bwrap"
_WSL_INTEROP = "/proc/sys/fs/binfmt_misc/WSLInterop"
_APPARMOR_USERNS = "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
_WIN_PROBE = "/mnt/c/Windows/System32/cmd.exe"
# the fixed flag template the probe runs; its hash is part of the cache key, so a changed flag set
# re-probes (spec:129-135)
_FLAG_TEMPLATE = (
    "--ro-bind / / --dev /dev --proc /proc | masks: docker.sock /run/user/<uid> /tmp/tmux-<uid> "
    "/run/WSL /mnt WSL_INTEROP | binds: scratchpad run-folder record-scratch | TMPDIR "
    "--unshare-pid --die-with-parent --chdir"
)


def _bwrap_path() -> str:
    return os.environ.get("SEAT_GUARD_BWRAP") or _BWRAP_DEFAULT


def _cache_file() -> str:
    return os.environ.get("SEAT_GUARD_CACHE") or f"/tmp/claude-{os.getuid()}/seat-guard-bwrap.json"


def _cr_state_dir() -> str:
    """``scripts/command_run.py::_state_dir`` (pinned equal by test B11; never imported here)."""
    raw = os.environ.get("COMMAND_RUN_DIR")
    if raw:
        return raw
    return os.path.join(os.path.expanduser("~"), ".claude", "state", "command-runs")


def _cr_safe_sid(sid: str) -> str:
    """``scripts/command_run.py::_safe_sid``, byte-for-byte (pinned equal by test B11)."""
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)
    if not safe:
        return "nosession"
    if safe != sid:
        safe += "-" + hashlib.blake2s(sid.encode("utf-8", "replace"), digest_size=4).hexdigest()
    return safe


def _cr_record_path(sid: str) -> str:
    """``scripts/command_run.py::_record_path`` (pinned equal by test B11)."""
    return os.path.join(_cr_state_dir(), f"{_cr_safe_sid(sid)}.json")


def _cr_scratch_main(cwd: str) -> str | None:
    """``scripts/command_run.py::_scratch_main`` for the checkout holding ``cwd``: the parent of
    the common git dir, so every worktree of one repo shares one run root."""
    try:
        r = subprocess.run(
            [
                "git",
                "-C",
                cwd,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
                "--show-toplevel",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = r.stdout.splitlines()
    if r.returncode != 0 or len(lines) < 2:
        return None
    common, top = lines[0], lines[1]
    return os.path.dirname(common) if os.path.basename(common) == ".git" else top


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def _writable_binds(payload: dict) -> list[str]:
    """The writable bind set (spec:113-121): scratchpad, run folder, a seeded run's record scratch."""
    scratch = os.path.realpath(payload["scratchpad_dir"])
    binds = [scratch]
    cwd = str(payload.get("cwd") or "")
    sid = str(payload.get("session_id") or "")
    main = _cr_scratch_main(cwd) if cwd else None
    if main and sid:
        runs = os.path.realpath(os.path.join(main, ".tmp", "runs"))
        run_folder = os.path.join(runs, _cr_safe_sid(sid))
        if os.path.isdir(run_folder):
            binds.append(run_folder)
        try:
            with open(_cr_record_path(sid), encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            rec = {}
        prev = rec.get("scratch") if isinstance(rec, dict) else None
        if isinstance(prev, str) and prev and os.path.isdir(prev):
            prev = os.path.realpath(prev)
            if _under(prev, runs) and not _under(prev, run_folder) and not _under(prev, scratch):
                binds.append(prev)
    return binds


def _masks(cwd: str, scratch: str) -> list[str]:
    """The service masks of spec:90-102, each only when its path exists."""
    uid = os.getuid()
    out: list[str] = []
    if os.path.exists("/run/docker.sock"):
        out += ["--ro-bind", "/dev/null", "/run/docker.sock"]
    for path in (f"/run/user/{uid}", f"/tmp/tmux-{uid}", "/run/WSL"):
        if os.path.isdir(path):
            out += ["--tmpfs", path]
    # the drvfs mounts hold every Windows executable; skipped when the seat's own cwd or scratch
    # lives there (spec:96-99) — that call runs with interop unproven
    if os.path.isdir("/mnt") and not _under(cwd, "/mnt") and not _under(scratch, "/mnt"):
        out += ["--tmpfs", "/mnt"]
    out += ["--unsetenv", "WSL_INTEROP"]
    return out


def _fence_argv(payload: dict) -> list[str]:
    """The bwrap vector for this seat call (spec:88-124). Raises on a per-call failure the hook can
    see (a cwd that is not a directory), which DENIES the call (spec:81-83)."""
    cwd = str(payload.get("cwd") or "")
    if not cwd or not os.path.isdir(cwd):
        raise ValueError(f"the payload cwd {cwd!r} is not a directory")
    binds = _writable_binds(payload)
    argv = [_bwrap_path(), "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
    argv += _masks(cwd, binds[0])
    for b in binds:
        argv += ["--bind", b, b]
    argv += ["--setenv", "TMPDIR", binds[0], "--unshare-pid", "--die-with-parent", "--chdir", cwd]
    return argv


def _cache_key(binary: str) -> dict:
    try:
        mtime = os.stat(binary).st_mtime_ns
    except OSError:
        mtime = None
    try:
        with open(_APPARMOR_USERNS, encoding="utf-8") as fh:
            apparmor = fh.read().strip()
    except OSError:
        apparmor = "absent"
    return {
        "binary": binary,
        "mtime": mtime,
        "kernel": os.uname().release,
        "apparmor_userns": apparmor,
        "flags": hashlib.sha256(_FLAG_TEMPLATE.encode()).hexdigest()[:16],
    }


def _probe(binary: str) -> dict:
    """Run the fixed flag set over a private folder (never a per-call path), and on WSL the interop
    launch of spec:103-112. Returns the mode record that is cached."""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="seat-guard-probe-")
    try:
        base = [binary, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
        tail = ["--unshare-pid", "--die-with-parent", "--chdir", tmp]
        masked = base + _masks(tmp, tmp) + ["--bind", tmp, tmp]
        try:
            ok = (
                subprocess.run(
                    masked + tail + ["--", "/bin/true"], capture_output=True, timeout=3
                ).returncode
                == 0
            )
        except (OSError, subprocess.SubprocessError):
            ok = False
        if not ok:
            return {
                "mode": "fallback",
                "interop": "n/a",
                "why": "the bwrap probe failed (user namespaces refused?)",
            }
        interop = "n/a"
        if os.path.exists(_WSL_INTEROP):
            interop = "unproven"
            if os.path.isfile(_WIN_PROBE):
                exe = os.path.join(tmp, "probe.exe")
                launch = (
                    masked + ["--ro-bind", _WIN_PROBE, exe] + tail + ["--", exe, "/c", "exit 0"]
                )
                try:
                    rc = subprocess.run(launch, capture_output=True, timeout=3).returncode
                except (OSError, subprocess.SubprocessError):
                    rc = 1
                interop = "open" if rc == 0 else "masked"
        return {"mode": "fence", "interop": interop, "why": ""}
    finally:
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def _fence_mode(payload: dict) -> dict:
    """fence or fallback for this seat call (spec:129-139), the probe cached per host (spec:131)."""
    sd = payload.get("scratchpad_dir")
    if not isinstance(sd, str) or not sd or not os.path.isdir(sd):
        return {"mode": "fallback", "interop": "n/a", "why": "no scratchpad_dir"}
    binary = _bwrap_path()
    if not (os.path.isfile(binary) and os.access(binary, os.X_OK)):
        return {"mode": "fallback", "interop": "n/a", "why": f"{binary} is absent"}
    key = _cache_key(binary)
    path = _cache_file()
    try:
        with open(path, encoding="utf-8") as fh:
            cached = json.load(fh)
        if (
            isinstance(cached, dict)
            and cached.get("key") == key
            and cached.get("mode") in ("fence", "fallback")
        ):
            return {
                "mode": cached["mode"],
                "interop": cached.get("interop", "n/a"),
                "why": cached.get("why", ""),
            }
    except (OSError, ValueError):
        pass
    result = _probe(binary)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.{os.getpid()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump({"key": key, **result}, fh)
        os.replace(tmp_path, path)
    except OSError:
        pass
    return result


# the constructs the parser does not model; in FALLBACK mode a seat command holding one is refused
# (spec:140-145)
_UNMODELLED = (
    (re.compile(r"(?:^|[;&|(\s])(?:ba|z|da|k)?sh\b[^\n;&|]*<<(?!<)"), "a heredoc to a shell"),
    (re.compile(r"\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b"), "a pipe into a shell"),
    (re.compile(r"(?:^|[;&|(\s])(?:eval|source)\b"), "`eval`/`source`"),
    (re.compile(r"(?:^|[;&|(\s])\.\s+\S"), "`.` (source)"),
    (re.compile(r"\$'"), "`$'…'`"),
    (re.compile(r"\(\(|\[\["), "`((`/`[[`"),
    (
        re.compile(
            r"(?:^|[;&|(\s])(?:command\s+-p|time\s+-p|ionice|stdbuf|flock|busybox|exec\s+-a)\b"
        ),
        "an unknown wrapper",
    ),
    (re.compile(r"(?:&&|\|\||\bthen|\belse|\bdo)\s+cd\b"), "a conditional `cd`"),
    (re.compile(r"(?:^|[;&|(\s])cd\s+[^\n;&|]*\$\("), "a `$(…)` in a cd position"),
    (re.compile(r">>?\|?\s*[^\s;&|]*\$\("), "a `$(…)` in a write position"),
)


def _unmodelled(command: str) -> str:
    for rx, what in _UNMODELLED:
        if rx.search(command):
            return what
    return ""


_DOTENV_OFF = "export PYTHON_DOTENV_DISABLED=1"
# the switch already set as the FIRST statement (a trailing `;` or newline ends it); `=10` is not
# it — python-dotenv reads only 1/true/t/yes/y as on (review A-S1)
_ALREADY_OFF = re.compile(r"\s*export\s+PYTHON_DOTENV_DISABLED=1\s*(?:;|\n|$)")


def rewrite(payload: dict, mode: dict | None = None) -> dict | None:
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
    fence = bool(mode) and mode.get("mode") == "fence"
    if _ALREADY_OFF.match(command):
        if not fence:
            return None
        inner = command  # the prefix is already there; the wrap still applies (spec:77-80)
    else:
        inner = f"{_DOTENV_OFF}\n{command}"
    if not fence:
        return {**tool_input, "command": inner}
    argv = _fence_argv(payload)
    wrapped = " ".join(shlex.quote(a) for a in argv) + " -- /bin/bash -c " + shlex.quote(inner)
    return {**tool_input, "command": wrapped}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    seat = bool(payload.get("agent_id")) and payload.get("agent_type") in SEAT_TYPES
    # the mode is computed ONCE, for a seat only, so rewrite() and decide() never disagree; a raise
    # in it is fallback mode for this call (plan-2 Phase B)
    mode: dict | None = None
    if seat:
        try:
            mode = _fence_mode(payload)
        except Exception as exc:
            mode = {
                "mode": "fallback",
                "interop": "n/a",
                "why": f"mode check raised {type(exc).__name__}",
            }
    fence = bool(mode) and mode.get("mode") == "fence"
    # the rewrite is computed apart from the scan; for a seat in fence mode a failed wrap DENIES, so
    # a seat command never runs unwrapped (spec:81-83)
    try:
        updated = rewrite(payload, mode)
        wrap_error = ""
    except Exception as exc:
        updated = None
        wrap_error = f"{type(exc).__name__}: {exc}"
    try:
        reason = decide(payload, mode)
    except Exception as exc:
        # fails open for the lead and in fence mode; in fallback mode the parser is the boundary
        reason = (
            f"seat guard (fallback mode): the check crashed ({type(exc).__name__}), so the call is refused. {_SAFE}."
            if seat and not fence
            else ""
        )
    if seat and fence and wrap_error and not reason:
        reason = f"seat guard (fence mode): the call could not be wrapped ({wrap_error}), so it is refused. {_SAFE}."
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
