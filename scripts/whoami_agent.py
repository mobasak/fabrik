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
import stat
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

# A spawned session id: a lowercase UUID, `agents_up.sh`'s `SID` shape (`scripts/sysadmin/agents_up.sh:120`).
_SID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# The agents lock the spawner holds across an `add`, in the repo's git common dir.
AGENTS_LOCK = "fabrik-agents.lock"
_GIT_LOCATION_VARS = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")

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
    cannot name a session it is not part of, because there is no input that sets this — except
    the env itself, which a SessionStart hook fills from Claude Code's payload before it calls
    `refresh()` (W-a77742db). A same-user process can always append a row to the store directly,
    so the store, not this read, is the trust root (D-1209).

    ONE exception, bounded by a lock: the spawner-only ``--spawned`` binding (`bind_spawned`) takes a
    NEW session's id as an argument, because the session it names does not exist yet. It is
    refused unless the caller passes a descriptor whose own open file description holds an
    EXCLUSIVE flock on ``<git common dir>/fabrik-agents.lock`` (`_caller_proof`), and it only binds
    an id no row the store still holds carries, so it cannot re-name a session the store knows.
    COBRA (D-253): the cheapest bypass is a caller that takes that lock itself and passes it;
    accepted, because the lock is hub tooling's alone — the plan adds its takers, the spawner
    ``agents_spawn.py add`` (T06) and the rotation's registry re-point in ``rotate_session.py``
    (T07) — and the row it writes carries ``spawned: true``
    and a null pid, so it is visible as a spawner's row and reserves the name against nobody.
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
    except (TypeError, ValueError, OverflowError):  # json reads `Infinity`; int() of it overflows
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


def _as_int(value: object) -> int | None:
    """A stored pid or start time as an int, or None. Rows are hand-editable JSON: a digit string
    counts, a bool never does (`True == 1` would make a corrupted row equal pid 1)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _pid_alive_same_start(row: dict) -> bool:
    """True only when the row's pid is alive AND is the same process the row was written for.

    ⚠️ A row with NO pid is NOT a holder. That is a GAP, not a safety property — a session whose
    pid could not be determined gets no collision protection — and `bind()` says so in its success
    message rather than implying a protection it does not have.
    """
    pid = _as_int(row.get("pid"))
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
    # Compared as ints: a start time stored as a digit string must not read as a DEAD holder, which
    # would let any other session take a live name with no refusal.
    return _pid_start(pid) == _as_int(was)


def _toplevel(cwd: str | None = None) -> str:
    """The git COMMON DIR, or "" — the collision scope.

    With ``cwd`` (the spawner-only bind's ``--repo``), git runs THERE with its own location
    variables (``GIT_DIR``, ``GIT_COMMON_DIR``, ``GIT_WORK_TREE``, ``GIT_INDEX_FILE``) removed, so a
    value inherited from a hook or an IDE cannot redirect the scope — the same as
    ``agents_up.sh``'s ``SCOPE``. Without it (every other caller) nothing changes.

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
    if cwd is not None:
        try:
            return _scope_of(cwd)[0]
        except (OSError, subprocess.SubprocessError):
            return ""
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


def _scope_of(repo: str) -> tuple[str, str]:
    """(`repo`'s git common dir, "") or ("", git's own first stderr line) — the STRICT read the spawned
    bind uses. git runs in `repo` with its location variables removed. A git that cannot RUN (absent,
    or past its 10 s timeout) RAISES, so the spawned path reports it as unexpected (exit 3) rather
    than as "not a repo"; a git that runs and refuses (not a repo, dubious ownership) is the caller's
    to read, so its own words are returned."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION_VARS}
    out = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        cwd=repo,
        env=env,
    )
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip(), ""
    lines = out.stderr.strip().splitlines()
    return "", (lines[0] if lines else f"git rev-parse exited {out.returncode}")


@contextlib.contextmanager
def _locked(path: Path, attempts: int = 50):
    """Exclusive flock across the whole READ-MODIFY-WRITE of a bind (`attempts` tries 0.1 s apart;
    `refresh` takes ONE, because it runs inside a SessionStart hook's 10 s budget).

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
        for i in range(max(1, attempts)):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if i + 1 < attempts:
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

    # This window's claude process, read AFTER the snapshot and inside the lock (the trim grader opens
    # its race inside this call), and only once the re-bind refusal above has passed. A /clear mints
    # a new session id in the SAME process, so a row with this exact (pid, pid_start) is this
    # window's predecessor, never a holder (W-34cb1ef9). Both halves must be known, and CLAUDE_PID,
    # when the real claude process exported it, must agree: a nested claude the /proc walk passes
    # through reaches the OUTER window's pid.
    me_pid = _session_pid()
    me_start = _pid_start(me_pid)
    claude_pid = (os.environ.get("CLAUDE_PID") or "").strip()
    same_window = me_pid is not None and me_start is not None and claude_pid in ("", str(me_pid))

    # Scanned with or without --force: force only skips the refusal, so a forced rotation still
    # records who it succeeded. A predecessor never ends the scan — a live foreign holder later in the
    # store still refuses. `predecessor` is the most recent such row of this name in this scope; a
    # /resume into an older id can make the chain cycle, so a reader walking it must bound itself.
    predecessor = ""
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
        if (
            same_window
            and _as_int(r.get("pid")) == me_pid
            and _as_int(r.get("pid_start")) == me_start
        ):
            predecessor = str(r.get("session_id"))
            continue
        if not force and _pid_alive_same_start(r):
            return 1, (
                f"whoami_agent: refused — {name!r} is held by a LIVE session (pid "
                f"{r.get('pid')}) in this repo. Pick another name, or --force if that session "
                "is gone. ⚠️ Two sessions on one name is the cheapest way to look named "
                "without being attributable, and nothing downstream catches it."
            )

    row = {
        "session_id": sid,
        "name": name,
        "pid": me_pid,
        "pid_start": me_start,
        "toplevel": top,
        "at": int(time.time()),
        "force": bool(force),
        "unlocked": not locked,  # auditable: this row was written without serialization
    }
    if predecessor:
        row["predecessor"] = predecessor
    _store_row(path, rows, row, top, name)
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
        + (f" (succeeds {predecessor})" if predecessor else "")
        + unprotected
    )


def _store_row(path: Path, rows: list[dict], row: dict, top: str, name: str) -> None:
    """Write `row` after the snapshot `rows`, trimming as it goes — the one writer both binds share."""
    cutoff = int(time.time()) - _TRIM_AFTER_S
    # ⚠️ A row's `at` is whatever is on disk. `int("abc")` raises ValueError and `int([1])` raises
    # TypeError (both executed), and an exception here would abort a BIND — the one operation the
    # operator runs by hand. An uncoercible timestamp is treated as ANCIENT and trimmed, never
    # fatal: a row we cannot date is a row we cannot honour.
    # Each (repo, name)'s NEWEST binding is kept whatever its age: it is how a quiet repo's launcher still finds its
    # builders (agents_up.sh reads the bindings when a repo has no registry, W-89474fc1), and it bounds the store at
    # one old row per name a repo ever bound. A row of no repo (empty toplevel) is never a launcher's, so it ages out
    # as before. The new row supersedes the named pair's old one, so that one is not kept for it.
    # Only a row that is still its SESSION's last row is kept that way: an old row of a session since bound to another
    # name would otherwise outlive the row that renamed it, and resurrect the old owner (review round 1). Only string
    # keys count — a hand-edited row with a list for a name must never abort a bind.
    newest: dict[tuple[str, str], int] = {}
    sid_last: dict[str, int] = {}
    for i, r in enumerate(rows):
        sid_last[str(r.get("session_id"))] = i
        t, n = r.get("toplevel"), r.get("name")
        if isinstance(t, str) and t and isinstance(n, str):
            newest[(t, n)] = i
    newest.pop((top, name), None)
    last = {i for i in newest.values() if sid_last.get(str(rows[i].get("session_id"))) == i}
    keep = [r for i, r in enumerate(rows) if _at(r) >= cutoff or i in last]
    if len(keep) != len(rows):
        _write_rows(path, keep + [row])
    else:
        _append_row(path, row)


def _holds_exclusive_flock(fdinfo: str) -> bool:
    """True when an fdinfo text lists an EXCLUSIVE flock owned by its open file description.

    Each ``lock:`` line reads ``lock:\\t1: FLOCK  ADVISORY  WRITE <pid> <dev>:<ino> 0 EOF``; a shared
    flock says ``READ`` and a POSIX (``lockf``/``fcntl``) lock says ``POSIX``. The fields are compared
    as TOKENS: a substring test for ``WRITE`` would also accept a POSIX write lock.
    """
    for line in fdinfo.splitlines():
        if not line.startswith("lock:"):
            continue
        if line.split()[2:5] == ["FLOCK", "ADVISORY", "WRITE"]:
            return True
    return False


def _caller_proof(top: str, fd: int) -> str:
    """Empty when descriptor `fd` proves the caller holds the agents lock, else the condition that failed.

    Two checks, and neither takes, converts or releases any lock: (a) `fd` is open on exactly
    ``<top>/fabrik-agents.lock`` — the literal path, which must not be a symlink, compared against
    ``readlink /proc/self/fd/<fd>`` and never realpath()'d first (a symlink there would point the
    proof at any file the caller can lock); (b) ``/proc/self/fdinfo/<fd>`` lists an EXCLUSIVE flock,
    which the kernel lists only for the open file description that owns it (a dup() of the holder
    shares it; a second, unlocked open of the same file lists nothing).

    Probing with flock was REJECTED (review pass 1): a fresh-open probe followed by a flock on the
    passed descriptor raced (a holder releasing between the two let an unlocked copy TAKE the lock,
    pass, and leave it held), and the flock on the passed descriptor changed the caller's own lock —
    it silently upgraded a shared holder to exclusive, or dropped it when the conversion failed.
    Reading fdinfo observes the lock without touching it: no window, no side effect.
    """
    expected = os.path.join(top, AGENTS_LOCK)
    try:
        held = os.readlink(f"/proc/self/fd/{fd}")
    except (OSError, ValueError):
        return f"--lock-fd {fd} is not an open descriptor"
    try:
        is_link = stat.S_ISLNK(os.lstat(expected).st_mode)
    except OSError:
        is_link = False  # absent: the comparison below names the file the descriptor IS open on
    if is_link:
        return (
            f"the agents lock {expected!r} is a symlink — only the literal file proves the caller"
        )
    if held != expected:
        return f"--lock-fd {fd} is open on {held!r}, not the agents lock {expected!r}"
    try:
        info = Path(f"/proc/self/fdinfo/{fd}").read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"/proc/self/fdinfo/{fd} could not be read ({exc.strerror or exc}): lock unproven"
    if not _holds_exclusive_flock(info):
        return (
            f"--lock-fd {fd} is open on the agents lock but does not hold an exclusive flock on it "
            "(a shared or POSIX lock, or none, is no proof)"
        )
    return ""


def bind_spawned(name: str, sid: str, repo: str, lock_fd: int) -> tuple[int, str]:
    """SPAWNER-ONLY: bind a NEW session id `sid` to `name` in `repo`'s scope. Returns (exit code, message).

    0 written · 1 a live pid-bearing row holds the name in this scope · 2 refused (name, repo, caller
    proof, a malformed id, or an id any row already carries). The row carries ``spawned: true`` and a
    null pid: stamping the CALLER's process would make the spawner the holder of the builder's name.
    """
    if not _NAME_RE.fullmatch(name):
        return 2, (
            f"whoami_agent: refused — {name!r} is not a valid agent name (^[a-z0-9-]{{1,32}}$)."
        )
    # The caller's input is checked HERE, in the parent, before git runs: an OSError from the run cannot say whether
    # git or the directory failed (a failed chdir names the cwd string as given, so `--repo git` read as git missing).
    repo = os.path.abspath(repo)
    if not os.path.isdir(repo):
        return 2, f"whoami_agent: refused — --repo {repo!r} is not a directory."
    if not os.access(repo, os.X_OK):
        return 2, f"whoami_agent: refused — --repo {repo!r} cannot be entered (permission denied)."
    try:
        top, git_err = _scope_of(repo)
    except (OSError, subprocess.TimeoutExpired) as exc:
        # --repo was enterable a moment ago, so any failure here is git failing to run (absent, not executable,
        # hung) or a directory changing under us — unexpected either way: main() reports it as exit 3.
        raise RuntimeError(f"git could not run in {repo!r}: {type(exc).__name__}: {exc}") from exc
    if not top:
        return 2, f"whoami_agent: refused — git could not read --repo {repo!r}: {git_err}"
    why = _caller_proof(top, lock_fd)
    if why:
        return 2, (
            f"whoami_agent: refused — {why}. --spawned is spawner-only: the caller must hold the "
            "repo's agents lock and pass that descriptor (--lock-fd)."
        )
    if not _SID_RE.fullmatch(sid):
        return 2, f"whoami_agent: refused — session id {sid!r} is not a lowercase UUID."
    path = store_path()
    with _locked(path) as (locked, lwhy):
        code, msg = _bind_spawned_locked(path, sid, name, top, locked)
    if code == 0 and not locked:
        msg += (
            f" ⚠️ the store lock could not be taken ({lwhy}); this bind was NOT serialized against"
            " a concurrent sibling"
        )
    return code, msg


def _bind_spawned_locked(
    path: Path, sid: str, name: str, top: str, locked: bool
) -> tuple[int, str]:
    """The read-modify-write half of `bind_spawned`. No window logic: the spawner's own process is never
    this row's window, so there is no `same_window` and no `predecessor`."""
    rows = _rows(path)
    if any(str(r.get("session_id")) == sid for r in rows):
        return 2, (
            f"whoami_agent: refused — session id {sid!r} is already in the identity store; "
            "--spawned binds only a FRESH id, never one of a session the store knows."
        )
    for r in rows:
        if str(r.get("name") or "") != name or str(r.get("toplevel") or "") != top:
            continue
        if _pid_alive_same_start(r):
            return 1, (
                f"whoami_agent: refused — {name!r} is held by a LIVE session (pid "
                f"{r.get('pid')}) in this repo. Pick another name."
            )
    row = {
        "session_id": sid,
        "name": name,
        "pid": None,
        "pid_start": None,
        "toplevel": top,
        "at": int(time.time()),
        "force": False,
        "unlocked": not locked,
        "spawned": True,
    }
    _store_row(path, rows, row, top, name)
    return 0, (
        f"whoami_agent: {name} bound to spawned session {sid} ⚠️ no pid: this binding does NOT"
        " reserve the name against a sibling until the builder re-binds on its first turn"
    )


def refresh(top: str | None = None) -> str:
    """Re-record this session's existing name under its CURRENT claude process; the name, or "".

    A session resumed into a new claude process (a window reload, a reboot, `claude --resume`)
    keeps its name by session id, but only `bind` writes a pid, so no row named the new process —
    and the quota lane's /clear re-bind, keyed on the process (D-1209), found nothing and held the
    merge owner for a whole lane (W-a77742db; 10 of 15 bound live windows on 2026-10-28). The
    SessionStart hook calls this on every start, passing its own git common dir as `top` so no
    second git runs inside its 10 s budget.

    It writes ONE row only when this session's LAST row in this scope names a valid name that is
    also the name of the session's last row overall (a row here must never flip the session back
    to an older name; an invalid-name last row refuses), still the newest row of that name here
    (nobody re-took it), this window's process is known (`same_window`'s rule in `_bind_locked`),
    and no row of the session carries a live process other than this window's own row in another
    repo — one test for both "already recorded under this window" and "the sid is live in another
    process" (left alone: a row here would strand that window at its next /clear). No store file
    at all writes nothing and creates nothing. Every other case, a busy store lock (ONE try) and
    any error write nothing. COBRA (D-253): the cheapest way to make a /clear re-bind pass without
    the outcome is a refresh for any name; this re-records only the session's own name, and
    planting a row by hand was already possible (the store is the lane's trust root, D-1209).
    """
    try:
        sid = session_id()
        scope = _toplevel() if top is None else top
        if not sid or not scope:
            return ""
        me_pid = _session_pid()
        me_start = _pid_start(me_pid)
        claude_pid = (os.environ.get("CLAUDE_PID") or "").strip()
        if me_pid is None or me_start is None or claude_pid not in ("", str(me_pid)):
            return ""
        path = store_path()
        if not path.is_file():
            return ""  # nothing bound anywhere: never create the state dir or a lock file for it
        with _locked(path, attempts=1) as (locked, _why):
            if not locked:
                return ""  # a refresh recurs at the next SessionStart; an unserialized one may be trimmed away
            rows = _rows(path)
            ours = [r for r in rows if r.get("session_id") == sid]
            # scope matched by REALPATH, as the lane's `_scoped_rows` reads it: the hook passes its
            # realpath'd common dir while `bind` stores `git rev-parse`'s string; the new row copies
            # the last row's own string, so every string-keyed reader sees the binding's scope
            want = os.path.realpath(scope)

            def this_window_elsewhere(r: dict) -> bool:
                t = r.get("toplevel")
                return (
                    _as_int(r.get("pid")) == me_pid
                    and _as_int(r.get("pid_start")) == me_start
                    and not (
                        isinstance(t, str) and os.path.isabs(t) and os.path.realpath(t) == want
                    )
                )

            # a live process on ANY row of the sid — another window, or this one already recorded
            # here — leaves it alone (a later row under a process since gone does not make an earlier
            # live one dead); this window's own row in ANOTHER repo says nothing about this one
            if any(_pid_alive_same_start(r) and not this_window_elsewhere(r) for r in ours):
                return ""
            real: dict[str, str] = {}
            here = []
            for r in rows:
                t = r.get("toplevel")
                if isinstance(t, str) and os.path.isabs(t):
                    if t not in real:
                        real[t] = os.path.realpath(t)
                    if real[t] == want:
                        here.append(r)
            mine = [r for r in here if r.get("session_id") == sid]
            if not mine:
                return ""
            last = mine[-1]
            name = str(last.get("name") or "")
            if not _NAME_RE.fullmatch(name):
                return ""
            if str(ours[-1].get("name") or "") != name:
                return ""  # the session resolves to another name now: a row here would flip it back
            if [r for r in here if str(r.get("name") or "") == name][-1] is not last:
                return ""  # re-taken since: a refresh would silently take it back
            _append_row(
                path,
                {
                    "session_id": sid,
                    "name": name,
                    "pid": me_pid,
                    "pid_start": me_start,
                    "toplevel": last["toplevel"],
                    "at": int(time.time()),
                    "force": False,
                    "unlocked": False,
                    "refresh": True,
                },
            )
            return name
    except Exception:
        return ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="whoami_agent.py",
        description="Bind THIS live session to an agent name, or print the resolved name.",
        # No prefix matching: `--spawn … --session … --rep … --lock …` bound at rc 0 (review pass 1).
        allow_abbrev=False,
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--as", dest="name", help="the agent name to bind this session to")
    # ⚠️ Mutually exclusive, and the branch below tests `is None` rather than truthiness. Before
    # this, `--as ""` (the live shape is an unset shell variable, `--as "$NAME"`) fell into the
    # --who branch and reported the OLD name at rc 0 — a silent no-op that reads as success — and
    # `--who --as fleet` silently ignored the bind.
    mode.add_argument("--who", action="store_true", help="print the resolved name and exit")
    mode.add_argument(
        "--spawned",
        metavar="NAME",
        help="SPAWNER-ONLY: bind a NEW session (--session-id) to NAME in --repo's scope; the caller "
        "must hold the repo's agents lock and pass it (--lock-fd). Exit 0 written, 1 live holder, "
        "2 refused, 3 crash",
    )
    ap.add_argument(
        "--session-id", dest="spawn_sid", help="with --spawned only: the new session's id"
    )
    ap.add_argument("--repo", dest="spawn_repo", help="with --spawned only: the repo it binds in")
    ap.add_argument(
        "--lock-fd", dest="spawn_fd", type=int, help="with --spawned only: the held agents-lock fd"
    )
    ap.add_argument("--force", action="store_true", help="override a collision, and record that")
    args = ap.parse_args(argv[1:])
    spawner = {
        "--session-id": args.spawn_sid,
        "--repo": args.spawn_repo,
        "--lock-fd": args.spawn_fd,
    }
    if args.spawned is None:
        given = [flag for flag, value in spawner.items() if value is not None]
        if given:
            ap.error(f"{', '.join(given)}: only with --spawned")
    else:
        missing = [flag for flag, value in spawner.items() if value is None]
        if missing:
            ap.error(f"--spawned needs {', '.join(missing)}")
        if args.force:
            ap.error("--spawned takes no --force: a live holder of the name always refuses")
        # Exit 3, not the `__main__` catch-all's 1, so a spawner can tell a crash from a collision.
        try:
            code, msg = bind_spawned(args.spawned, args.spawn_sid, args.spawn_repo, args.spawn_fd)
        except Exception as exc:
            print(f"whoami_agent: --spawned crashed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 3
        print(msg, file=sys.stderr if code else sys.stdout)
        return code
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
