#!/usr/bin/env python3
# AFTER-EDIT: tests/test_whoami_agent.py, docs/workstation/agent-identity.md
"""Bind THIS live session to an agent name, and resolve that binding — no relaunch (D-267/D-268).

Agent identity has always resolved from ``CLAUDE_AGENT`` alone, a LAUNCH-TIME variable, and every
control keyed on it fails SILENT when it is unset. A window ``/rename`` never reaches it: measured
2026-09-16 on three live `trade-intelligence` windows named ``agent-1/2/3`` in the UI — all three
``CLAUDE_AGENT=<UNSET>``, and 0 of their last 40 commits carried an ``Agent-Name`` trailer while
40 of 40 carried ``Agent-Role``.

THE ENABLING FACT, executed: ``CLAUDE_CODE_SESSION_ID`` IS exported into every shell a live session
runs, and git hooks inherit it (a scratch ``commit-msg`` printed the sid with ``CLAUDE_AGENT``
empty). ⚠️ The ``claude`` PROCESS ITSELF does not carry it — `/proc/<claude pid>/environ` has zero
occurrences — which is why the session pid is found by walking ancestry, never by matching the sid.

RESOLUTION ORDER, and it is the only one: a WELL-FORMED ``CLAUDE_AGENT`` → the binding for this
``CLAUDE_CODE_SESSION_ID`` → ``""``. A malformed env value falls through, which changes nothing for
anyone actually named (``command_run.py::_agent_name`` already returns ``""`` for one). The
``Agent-Name:`` trailer is deliberately NOT in the chain: it is what identity PRODUCES, so reading
it back to decide identity is circular, and a session that has not committed has none.

⚠️ FAIL-OPEN EVERYWHERE. Every read path returns ``""`` rather than raising: this module is imported
by a fleet-synced close gate, and an exception here would block a turn in ~46 repos. It can only ADD
identity, never remove it.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# The STRICTEST of the three live validators, deliberately. Executed 2026-09-16: `Agent-2`,
# `agent_2` and `agent.2` are accepted by `mail.py::_safe_agent` but REJECTED by both
# `command_run.py::_AGENT_NAME_RE` and `agent_role.py::_NAME_RE` — so a name outside this set would
# bind here and then be silently dropped by two consumers, leaving one session with two identities
# and no error anywhere. Byte-identical to `command_run.py:1602`; `tests/test_whoami_agent.py` pins
# the three copies against each other because none of these files may import another.
# ⚠️ Every use is `fullmatch`, never `match`: with `match`, `$` matches BEFORE a trailing
# newline, so `--as $'infra\n'` bound the name "infra\n" — and a newline inside an
# `Agent-Name:` trailer makes git parse the WHOLE block as nothing, reproducing the exact
# "0 of 40 commits carried Agent-Name" failure this feature was built to fix. `agent_role.py`
# already uses fullmatch, so `match` also falsified the "strictest of the three" claim below.
_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")

_TRIM_AFTER_S = 30 * 24 * 3600  # nothing else prunes ~/.claude/state: `scratch_sweep.py:59` states
# it touches only its own lock there and "reads, writes and deletes nothing else". An unowned store
# would grow forever, so the WRITER trims as it appends.


def store_path() -> Path:
    """``$AGENT_IDENTITY_FILE`` else ``$HOME/.claude/state/agent-identity.jsonl``.

    ⚠️ ``$HOME``-keyed, NOT ``$CLAUDE_CONFIG_DIR``-keyed — the same resolution
    ``command_run.py::_state_dir`` uses. On this box ``CLAUDE_CONFIG_DIR`` is
    ``~/.claude-fleet/active`` and has no state dir at all, so a session PINNED to another account
    slug still shares this store, which is what makes a pinned long job attributable.
    """
    raw = os.environ.get("AGENT_IDENTITY_FILE")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "state" / "agent-identity.jsonl"


def session_id() -> str:
    """This session's id, from the environment ONLY — never an argument.

    That is not a convenience: it is the structural half of the Cobra counter-measure. A process
    cannot name a session it is not part of, because there is no input that sets this.
    """
    return (os.environ.get("CLAUDE_CODE_SESSION_ID") or "").strip()


def _session_pid() -> int | None:
    """The `claude` process this writer is running under, by walking /proc ancestry.

    ⚠️ NEVER ``os.getpid()``. The writer is a short-lived process that exits immediately, so a
    recorded self-pid would be dead the moment anyone read it — which is what made an earlier
    draft's liveness check mark every binding inert at birth. Returns None when the walk fails, and
    a None pid is recorded as absent rather than guessed.
    """
    try:
        pid = os.getpid()
        for _ in range(12):  # bounded: python3 -> bash -> claude is 2 hops; 12 is generous
            status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace")
            name = ""
            ppid = 0
            for line in status.splitlines():
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("PPid:"):
                    ppid = int(line.split(":", 1)[1].strip() or 0)
            if name == "claude":
                return pid
            if ppid <= 1:
                return None
            pid = ppid
    except (OSError, ValueError):
        return None
    return None


def _at(row: dict) -> int:
    """A row's timestamp as an int, or 0 when it is missing or uncoercible (never raises)."""
    try:
        return int(row.get("at") or 0)
    except (TypeError, ValueError):
        return 0


def _pid_start(pid: int | None) -> int | None:
    """Field 22 of `/proc/<pid>/stat` (start time in clock ticks), or None.

    Recorded beside the pid so a RECYCLED pid cannot impersonate the original holder: rows live 30
    days and `pid_max` here is 4194304. Measured before this: a stale row carrying `pid: 1` refused
    a legitimate bind with "held by a LIVE session (pid 1)".
    """
    if not pid:
        return None
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        return int(raw[raw.rindex(")") + 1 :].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _pid_alive_same_start(row: dict) -> bool:
    """True only when the row's pid is alive AND is the same process the row was written for.

    ⚠️ A row with NO pid is NOT a holder. That is a GAP, not a safety property — a session whose
    pid could not be determined gets no collision protection — and `bind()` says so in its success
    message rather than implying a protection it does not have.
    """
    pid = row.get("pid")
    if not pid:
        return False
    try:
        if not Path(f"/proc/{pid}").is_dir():
            return False
    except OSError:
        return False
    was = row.get("pid_start")
    if was is None:
        return True  # a row written before start-times existed: pid-only, as before
    return _pid_start(pid) == was


def _toplevel() -> str:
    """The git COMMON DIR, or "" — the collision scope.

    ⚠️ Common-dir, NOT `--show-toplevel`: a worktree and its main checkout are ONE repo with two
    toplevels, so a toplevel scope let two sessions committing into one history hold one name
    (measured: they differ under `--show-toplevel`, agree under `--git-common-dir`). This repo has
    ~20 registered worktrees at any moment — a MOVING count, so re-derive it rather than
    quoting this sentence.

    ⚠️ NOT ``os.getcwd()``. Executed: with a cwd-scoped check, a plain ``cd`` into a subdirectory
    bound a name another live session held, at rc 0 and with no ``--force`` recorded — cheaper than
    the sanctioned override and leaving no trace. A session's cwd is not stable either
    (``docs/workstation/session-recall.md:43``: a session that changes cwd is RE-FILED mid-session,
    and ``EnterWorktree`` moves it into ``<repo>/.claude/worktrees/<name>``).
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@contextlib.contextmanager
def _locked(path: Path):
    """Exclusive flock across the whole READ-MODIFY-WRITE of a bind.

    ⚠️ Without this the 30-day TRIM silently destroys a sibling's binding. `bind()` snapshots the
    rows, and when any row is older than the window it REWRITES the file from that snapshot — so a
    row a sibling appended in between is gone. Executed: session B's row appended between A's read
    and A's write vanished, leaving only A's. That is invisible identity loss, and it becomes
    INEVITABLE once the store ages past 30 days.

    Same `fcntl.flock` idiom as `command_run.py`'s mutating subcommands (`:161-190`), including its
    fail-soft: if the lock cannot be taken the body still runs unserialized rather than wedging the
    caller — a binding that races is better than a binding that hangs.
    """
    fd = None
    why = ""
    try:
        lock_path = path.resolve().with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        # ⚠️ NON-blocking with a bounded retry. A bare LOCK_EX is BLOCKING, so the fail-soft this
        # docstring promises covered only the ERROR cases and never contention — executed, a bind
        # blocked past 12 s behind a stopped holder. The critical section is milliseconds, so ~5 s
        # of retry is generous; after that we proceed unserialized and SAY SO.
        for _ in range(50):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                time.sleep(0.1)
        else:
            why = "another process held the store lock for over 5 s"
            with contextlib.suppress(OSError):
                os.close(fd)
            fd = None
    except Exception as exc:
        why = f"{type(exc).__name__}: {exc}"
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
            fd = None
    try:
        yield fd is not None, why
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                os.close(fd)


def _rows(path: Path) -> list[dict]:
    """Every parseable row, oldest first. A corrupt line is skipped, never fatal."""
    try:
        # ⚠️ REGULAR FILES ONLY. `read_text` on a FIFO blocks forever with no writer — executed, it
        # hung past a 6 s timeout — and this function is reached from a fleet-synced close gate,
        # where a hang stalls the turn rather than failing it. A non-regular path reads as empty.
        if not path.is_file():
            return []
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("session_id"):
            out.append(row)
    return out


def resolve_agent_name() -> str:
    """The one resolution order. Returns "" when identity is genuinely unknown — never raises."""
    try:
        env = (os.environ.get("CLAUDE_AGENT") or "").strip()
        if _NAME_RE.fullmatch(env):
            return env
        sid = session_id()
        if not sid:
            return ""
        name = ""
        for row in _rows(store_path()):  # LAST row wins for this sid
            if row.get("session_id") == sid and _NAME_RE.fullmatch(str(row.get("name") or "")):
                name = str(row["name"])
        return name
    except Exception:
        return ""


def _write_rows(path: Path, rows: list[dict]) -> None:
    """Rewrite the store from `rows` via a temp file + atomic replace (the trim path)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            buf = data.encode("utf-8")
            while buf:
                buf = buf[os.write(fd, buf) :]
        finally:
            os.close(fd)
        os.replace(tmp, path)
    finally:
        # ⚠️ `os.replace` consumes `tmp` on success; on ANY failure it survives forever, because
        # `scratch_sweep.py:59` states it "reads, writes and deletes nothing else" in this
        # directory — an unowned leak in 46 distributed copies.
        with contextlib.suppress(OSError):
            tmp.unlink()


def _append_row(path: Path, row: dict) -> None:
    """One row under O_APPEND, short writes CONTINUED — `command_run.py:1488`'s idiom verbatim.

    Three sessions append to this store; measured at 30 concurrent writers x 400 rows, 0 torn rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        while data:
            data = data[os.write(fd, data) :]
    finally:
        os.close(fd)


def bind(name: str, force: bool = False) -> tuple[int, str]:
    """Bind this session to `name`. Returns (exit code, message)."""
    if not _NAME_RE.fullmatch(name):
        return 2, (
            f"whoami_agent: refused — {name!r} is not a valid agent name. The alphabet is "
            "^[a-z0-9-]{1,32}$, the strictest of the three live validators: a name outside it "
            "would bind here and be silently dropped by command_run.py and agent_role.py."
        )
    sid = session_id()
    if not sid:
        return 2, (
            "whoami_agent: refused — CLAUDE_CODE_SESSION_ID is empty, so there is no session to "
            "bind. This is expected outside a Claude Code session (cron, `env -i`)."
        )
    path = store_path()
    top = _toplevel()  # outside the lock: it shells out to git and must not hold the lock for that
    with _locked(path) as (locked, why):
        code, msg = _bind_locked(path, sid, name, force, top, locked)
    if code == 0 and not locked:
        msg += (
            f" ⚠️ the store lock could not be taken ({why}); this bind was NOT serialized against"
            " a concurrent sibling"
        )
    return code, msg


def _bind_locked(
    path: Path, sid: str, name: str, force: bool, top: str, locked: bool = True
) -> tuple[int, str]:
    """The read-modify-write half of `bind`, serialized by `_locked`."""
    rows = _rows(path)

    mine = [r for r in rows if r.get("session_id") == sid]
    if mine and not force:
        current = str(mine[-1].get("name") or "")
        if current and current != name:
            return 1, (
                f"whoami_agent: refused — this session id is already bound to {current!r}. "
                "A Task subagent INHERITS its dispatcher's CLAUDE_CODE_SESSION_ID, so re-binding "
                "without --force would silently re-identify the session that dispatched you."
            )

    if not force:
        for r in rows:
            if r.get("session_id") == sid or str(r.get("name") or "") != name:
                continue
            # ⚠️ An UNKNOWN scope is its own scope, never a wildcard. With `if top and …`, a
            # holder scoped "" was invisible to any checker inside a repo, and a checker scoped ""
            # matched every holder everywhere (both measured). `_toplevel()` returns "" on a
            # git-less dir AND on its 10 s timeout, so a transient git failure silently downgraded
            # a binding into the unprotected half.
            if str(r.get("toplevel") or "") != top:
                continue
            if _pid_alive_same_start(r):
                return 1, (
                    f"whoami_agent: refused — {name!r} is held by a LIVE session (pid "
                    f"{r.get('pid')}) in this repo. Pick another name, or --force if that session "
                    "is gone. ⚠️ Two sessions on one name is the cheapest way to look named "
                    "without being attributable, and nothing downstream catches it."
                )

    row = {
        "session_id": sid,
        "name": name,
        "pid": (_pid := _session_pid()),
        "pid_start": _pid_start(_pid),
        "toplevel": top,
        "at": int(time.time()),
        "force": bool(force),
        "unlocked": not locked,  # auditable: this row was written without serialization
    }
    cutoff = int(time.time()) - _TRIM_AFTER_S
    # ⚠️ A row's `at` is whatever is on disk. `int("abc")` raises ValueError and `int([1])` raises
    # TypeError (both executed), and an exception here would abort a BIND — the one operation the
    # operator runs by hand. An uncoercible timestamp is treated as ANCIENT and trimmed, never
    # fatal: a row we cannot date is a row we cannot honour.
    keep = [r for r in rows if _at(r) >= cutoff]
    if len(keep) != len(rows):
        _write_rows(path, keep + [row])
    else:
        _append_row(path, row)
    unprotected = (
        ""
        if row["pid"]
        else (
            " ⚠️ no session pid could be determined, so this binding does NOT reserve the name against"
            " a sibling"
        )
    )
    return 0, (
        f"whoami_agent: {name} bound to session {sid}"
        + (" (forced)" if force else "")
        + unprotected
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="whoami_agent.py",
        description="Bind THIS live session to an agent name, or print the resolved name.",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--as", dest="name", help="the agent name to bind this session to")
    # ⚠️ Mutually exclusive, and the branch below tests `is None` rather than truthiness. Before
    # this, `--as ""` (the live shape is an unset shell variable, `--as "$NAME"`) fell into the
    # --who branch and reported the OLD name at rc 0 — a silent no-op that reads as success — and
    # `--who --as fleet` silently ignored the bind.
    mode.add_argument("--who", action="store_true", help="print the resolved name and exit")
    ap.add_argument("--force", action="store_true", help="override a collision, and record that")
    args = ap.parse_args(argv[1:])
    if args.who or args.name is None:
        name = resolve_agent_name()
        print(name)
        return 0 if name else 1
    code, msg = bind(args.name, force=args.force)
    print(msg, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # fail-open: never let identity work break a caller
        print(f"whoami_agent: {exc}", file=sys.stderr)
        sys.exit(1)
