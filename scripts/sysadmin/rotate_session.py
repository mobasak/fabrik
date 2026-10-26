#!/usr/bin/env python3
# AFTER-EDIT: tests/test_rotate_session.py | docs/workstation/session-history-retention.md | docs/workstation/hooks-index.md
"""rotate_session — rotate an agent's session (/clear) at an item boundary, typed by a unit, never by an agent.

W-f975fee0 slice 2 (D-1119, D-1123, D-1135). A builder cannot type a slash command into its own prompt, and the auto-mode
classifier refuses a coordinator's `tmux send-keys` into an agent pane. So rotation is two halves:

    request <name> [--compact FOCUS] [--trigger T] [--repo ROOT]   the coordinator's verb (`agents_up.sh rotate-session`)
    execute                                                        the user systemd unit's (fabrik-rotate.path/.service)
    due [--mb-only] [--mail]                                       slice 3: the read-only list of agents past the line
                                                                   (hibernate `lift` offers it; the nightly mails it)

`request` resolves the pane, its claude process and its session, runs the checks below and writes ONE data-only request
file; `execute` claims each file, re-runs every check itself, types FIXED templates, verifies through the session registry
and the identity store, and appends one row per outcome to the rotations log. Keys typed while a session works are
QUEUED, not refused, so every check fails CLOSED and nothing is ever queued or retried.

RESOLVE: the tmux session agents_up names from the repo folder; panes deduped by id; exactly one `@agent` == name; its one
descendant `claude`; that pid's registry record (procStart must match) gives sid and cwd; the newest identity binding
of name in that toplevel must name that sid. CHECKS: (0) the transcript unwritten for 30 s (the registry's status lags, W-477d751a); (1) the transcript's last
timestamped row is a system turn end (turn_duration | stop_hook_summary), only away_summary / queue-operation / untimed
rows after it, and the metadata rows a resume writes (pr-link, frame-link, system informational); a registry that
turned busy AFTER that turn end vetoes; (2) no run record frame running; (3) no pool seat whose parent chain reaches the claude pid, and no
background Agent launch in the last 8 MB without its task-notification (no stamp precondition, an unreadable tail
aborts); (4) the worktree clean and pushed; (5) the screen's last `❯` line is empty between `─` rules.

COBRA (D-253): the cheapest pass is a request written without the checks, or an execute that trusts the file; the
counter is a data-only file whose keys `execute` builds from templates after re-running every check, and a row for every
outcome, aborts included. Residual race: a turn that starts between the last re-check and the first key queues the keys —
recorded as `partial:queued` when no new session id appears.

Env (test seams): ROTATE_HOME (~), ROTATE_PROC_ROOT (/proc), ROTATE_TMUX (tmux), ROTATE_REQUEST_DIR
(~/.claude/state/rotate-requests), ROTATIONS_LOG (~/.claude/state/rotations.jsonl), AGENT_IDENTITY_FILE, ROTATE_WAIT_S.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STALE_S = 60
ORPHAN_S = 900  # past the service's TimeoutStartSec (600 s): a `.claimed` nobody can still hold
IDLE_S = 30
# W-b72231b8 slice 2: every wait this script runs for one request, named so the worst case below is derived, never
# restated. Not counted: run_checks' git calls in hibernate.worktree_state (up to 3 per call, 60 s timeout each) —
# W-b728822f bounds them.
TMUX_TIMEOUT_S = 10  # one tmux call; a wait loop checks its deadline only after its capture returns
DISCARD_RECHECK_S = 2.0  # the discard reads the box twice, this far apart, before its key
DISCARD_WAIT_S = 10  # the box reads empty after the double Escape
SEND_SETTLE_S = 10  # a paste settles in the input line
SEND_SUBMIT_S = 20  # the input line changes after C-m
CLEAR_WAIT_S = 60  # the registry shows the new session after /clear
COMPACT_WAIT_S = 60  # the compact boundary lands (the compact path has no re-bind wait, so it is the shorter one)
# The re-bind wait after the resume prompt: the one late bind measured since W-b92aa5cf landed 98 s after the submit.
REBIND_GRACE_S = 180
# The worst /clear request: the discard's re-check sleep and its wait, two sends, the clear wait and the re-bind grace;
# the sleep each loop may take after its last check (0.5 s in the five capture loops, 1 s in the clear and re-bind loops
# — 4.5 s, rounded up to 5); and 17 tmux calls that can each take TMUX_TIMEOUT_S past any deadline — 12 outside every
# wait (resolve 1, the two run_checks 1 each, _one's box read 1, the discard's three box reads and its Escape pair 4,
# two pastes and two C-m 4) and the last capture of each of the five capture loops (the discard wait, two settles, two
# submits) — 487 s.
REQUEST_WORST_S = (
    DISCARD_RECHECK_S
    + DISCARD_WAIT_S
    + 2 * (SEND_SETTLE_S + SEND_SUBMIT_S)
    + CLEAR_WAIT_S
    + REBIND_GRACE_S
    + 5
    + 17 * TMUX_TIMEOUT_S
)
# `execute` claims no new request after this long, so the last request it starts ends inside the unit's
# TimeoutStartSec=600 with at least 60 s to spare (50 + 487 + 60 <= 600), the git calls above aside. A file left unclaimed
# stays for the path unit, which starts `execute` again when this one exits; two requests can only meet in one run by
# racing past `_pending`.
CLAIM_CUTOFF_S = 50
VETO_S = 300  # a registry flip after the last turn end vetoes this long; measured flips led a turn's first write by 0.02 s
SEAT_TAIL = 8 * 1024 * 1024
TURN_END = ("turn_duration", "stop_hook_summary")
FIELDS = {
    "name",
    "repo",
    "pane",
    "pid",
    "proc_start",
    "sid",
    "mode",
    "focus",
    "trigger",
    "created_at",
    "ctx_pre",
    "window",
    "mb_pre",
    "last_compact_age_s",
}
OPTIONAL = {"stale_text", "operator_ok"}  # --stale-input discard (W-ee19169d): both or neither
TRIGGERS = ("ctx", "mb", "unrelated", "compact", "manual", "lift")
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
_PANE = re.compile(r"%[0-9]{1,6}")
_NOTIFY = re.compile(
    r"<task-id>([^<\s]+)</task-id>.*?<status>([^<\s]+)</status>", re.S
)  # the Stop hook's forms


# W-05021a03: `request`'s exit names whether asking again can pass. TRANSIENT clears by itself (the session finishes its
# turn, run or seat; the rotation in flight rows; tmux answers; a pane restarts) → EXIT_RETRY; PERMANENT needs an act
# first → 1, which an uncaught crash also exits (read stderr and act, the same as a permanent abort). Fail direction:
# transient-called-permanent stops a rotation that would have passed, permanent-called-transient keeps the old loop, so
# a check is transient by default and a raise is permanent only on POSITIVE evidence that an act is needed (`transient=
# False`): a bad argument, the request dir's ownership, a dialog's numbered option on the prompt row, text typed in the
# box, two transcripts, no identity row or a binding elsewhere, uncommitted or unpushed work, a slash-command ending, a
# request the unit never claimed. COBRA (D-253): calling everything transient passes any exit test and keeps the loop;
# the measure is the consecutive-repeat census of rotations.jsonl, not the rc.
EXIT_RETRY = 75  # sysexits EX_TEMPFAIL
TRANSIENT_CHECKS = frozenset(
    {
        "status",
        "idle",
        "pending",
        "record",
        "seat",
        "tmux",
        "resolve",
        "transcript",
        "screen",
        "worktree",
    }
)
PERMANENT_CHECKS = frozenset({"args", "request", "stale-input"})


class CheckFailedError(Exception):
    """A check failed: (check, reason), and whether asking again can pass (`transient`)."""

    def __init__(self, check: str, reason: str, transient: bool | None = None) -> None:
        super().__init__(f"{check}: {reason}")
        self.check, self.reason = check, reason
        self.transient = check not in PERMANENT_CHECKS if transient is None else transient


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"_rot_{name}", HERE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name}.py beside rotate_session.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hib = _load("hibernate")
tsc = _load("transcript_size_check")


def _home() -> Path:
    return Path(os.environ.get("ROTATE_HOME") or Path.home())


def _proc() -> Path:
    return Path(os.environ.get("ROTATE_PROC_ROOT", "/proc"))


def _req_dir() -> Path:
    return Path(
        os.environ.get("ROTATE_REQUEST_DIR") or _home() / ".claude" / "state" / "rotate-requests"
    )


def _ensure_req_dir() -> Path:
    """The request directory, private (0700) and ours: a symlink or a directory another uid owns refuses (fail closed)."""
    d = _req_dir()
    try:
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        # one fd for the check and the chmod: O_NOFOLLOW refuses a symlink (ELOOP), so nothing can swap the path between
        fd = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise CheckFailedError(
            "request", f"{d} is not a plain directory ({type(exc).__name__})"
        ) from exc
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid():
            raise CheckFailedError("request", f"{d} is owned by uid {st.st_uid}")
        if stat.S_IMODE(st.st_mode) != 0o700:
            os.fchmod(fd, 0o700)
    except OSError as exc:
        raise CheckFailedError("request", f"{d}: {type(exc).__name__}") from exc
    finally:
        os.close(fd)
    return d


def _log() -> Path:
    return Path(
        os.environ.get("ROTATIONS_LOG") or _home() / ".claude" / "state" / "rotations.jsonl"
    )


def _identity() -> Path:
    return Path(
        os.environ.get("AGENT_IDENTITY_FILE")
        or _home() / ".claude" / "state" / "agent-identity.jsonl"
    )


def _wait_s(default: float) -> float:
    try:
        v = float(os.environ.get("ROTATE_WAIT_S", default))
    except ValueError:
        return default
    return v if math.isfinite(v) and v > 0 else default


_SID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)  # agents_up.sh's SID
REGISTRY_MAX = 1 << 20  # bytes of the registry read at most (agent_status.py:189)


def _session_registry(repo: str, sid: str) -> Path | None:
    """The repo's `.fabrik/session-agents.json` (sid -> agent name) — only for an absolute repo that is its own realpath,
    whose `.fabrik` is no symlink, and whose `<repo>/.git` is the git common dir the rotated session's newest binding
    names: `resolve` matches a pane by the repo's folder name alone, so another checkout of the same name would
    otherwise be written (W-b72231b8, review r1)."""
    try:
        p = Path(repo)
        if not p.is_absolute() or os.path.realpath(repo) != str(p):
            return None
        if os.path.realpath(p / ".fabrik") != str(p / ".fabrik"):
            return None
    except (OSError, ValueError):  # a NUL or a lone surrogate in a hand-written request
        return None
    tops = [r.get("toplevel") for r in _bindings() if r.get("session_id") == sid]
    if not tops or tops[-1] != str(p / ".git"):
        return None
    return p / ".fabrik" / "session-agents.json"


def _repoint_registry(path: Path, old_sid: str, new_sid: str, name: str) -> str:
    """Re-point `name`'s registry entry from `old_sid` to `new_sid` in place (W-b72231b8: the coordinator did it by hand
    after every rotation) and return the state the row records. Nothing agents_up.sh refuses is ever written — a file
    it would refuse is refused here unchanged — a missing entry is never added, and every failure is a returned state,
    never an exception: the rotation itself already happened."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        return f"error:{type(exc).__name__}"
    if not stat.S_ISREG(st.st_mode):
        return "refused:not a regular file"
    if not _SID.fullmatch(new_sid):
        return "refused:the new id is not a session id"
    if st.st_size > REGISTRY_MAX:
        return "refused:over 1 MiB"

    def no_repeats(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise KeyError("dup")
        return dict(pairs)

    try:
        raw = path.read_bytes()
        try:
            reg = json.loads(raw.decode("utf-8"), object_pairs_hook=no_repeats)
        except KeyError:
            return "refused:a session id appears twice"
        except (ValueError, RecursionError):
            return "refused:not valid JSON"
        if not isinstance(reg, dict) or not all(isinstance(v, str) for v in reg.values()):
            return "refused:not an object of session id -> agent name"
        if not all(_SID.fullmatch(k) for k in reg):
            return "refused:a key is not a session id"
        if not all(_NAME.fullmatch(v) for v in reg.values()):
            return "refused:a value is not an agent name"
        if new_sid in reg:
            if reg[new_sid] != name:
                return "refused:the new id already names another agent"
            if reg.get(old_sid) != name:
                return "current"
            out = {k: v for k, v in reg.items() if k != old_sid}
        elif reg.get(old_sid) == name:
            out = {(new_sid if k == old_sid else k): v for k, v in reg.items()}
        else:
            return "no-entry"
        text = json.dumps(out, indent=2) + "\n"
        if (
            len(text.encode("utf-8")) > REGISTRY_MAX
        ):  # its readers stop at REGISTRY_MAX and would read a torn file
            return "refused:over 1 MiB"
        # a hand edit landing between the re-read below and os.replace is still lost: hand edits are what this retires
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".session-agents.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.chmod(tmp, stat.S_IMODE(st.st_mode))
            if path.read_bytes() != raw:  # a hand edit since the read: never overwrite it
                return "refused:changed on disk"
            os.replace(tmp, path)
            tmp = ""
        finally:
            if tmp:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
        return "repointed"
    except OSError as exc:
        return f"error:{type(exc).__name__}"


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.environ.get("ROTATE_TMUX", "tmux"), *args],
        capture_output=True,
        text=True,
        timeout=TMUX_TIMEOUT_S,
    )


def slug(repo: str) -> str:
    """agents_up.sh's session name: the repo folder, every character outside [A-Za-z0-9_-] a dash."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", Path(repo).name)


def _ts(value: object) -> float:
    """A transcript row's ISO-8601 `timestamp` (a trailing Z is UTC) as epoch seconds; anything else is 0."""
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def append_row(row: dict) -> None:
    """One outcome row; never raises — a lost log write is said on stderr, never an aborted run."""
    line = json.dumps({"at": int(time.time()), **row}, sort_keys=True, default=str)
    try:
        log = _log()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"rotate-session: could not write the rotation row ({exc}): {line}", file=sys.stderr)


# ── resolve ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _status(proc: Path, pid: int) -> tuple[str, int | None]:
    name, ppid = "", None
    try:
        for line in (
            (proc / str(pid) / "status").read_text(encoding="utf-8", errors="replace").splitlines()
        ):
            if line.startswith("Name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("PPid:"):
                ppid = int(line.split(":", 1)[1].strip() or 0)
    except (OSError, ValueError):
        pass
    return name, ppid


def _claude_under(proc: Path, root: int) -> list[int]:
    """Every descendant of `root` whose process name is `claude` (the pane runs bash → bash -c → claude)."""
    parent: dict[int, int] = {}
    names: dict[int, str] = {}
    for d in proc.iterdir():
        if d.name.isdigit():
            n, pp = _status(proc, int(d.name))
            if pp is not None:
                parent[int(d.name)], names[int(d.name)] = pp, n
    out = []
    for pid, n in names.items():
        if n != "claude":
            continue
        cur, hops = parent.get(pid), 0
        while cur and hops < 16:
            if cur == root:
                out.append(pid)
                break
            cur, hops = parent.get(cur), hops + 1
    return sorted(out)


def _registry(home: Path, proc: Path, pid: int) -> dict:
    start = hib._proc_start(proc, pid)
    for f in hib._session_files(home):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            isinstance(d, dict)
            and d.get("pid") == pid
            and str(d.get("procStart")) == str(start)
            and start is not None
        ):
            return d
    raise CheckFailedError(  # a claude seconds old has not written its record yet
        "resolve", f"no registry record for claude pid {pid}", transient=True
    )


def _bindings() -> list[dict]:
    rows = []
    try:
        # a non-UTF-8 byte or a pathological nest skips its line, never raises: a raise here after the /clear rowed
        # the rotation `partial:clear` and never sent the resume prompt (W-b72231b8 review r2)
        for line in _identity().read_text(encoding="utf-8", errors="replace").splitlines():
            with contextlib.suppress(ValueError, RecursionError):
                r = json.loads(line)
                if isinstance(r, dict):
                    rows.append(r)
    except OSError:
        pass
    return rows


def _bound(name: str, sid: str) -> bool:
    """The newest row for this sid names `name`, and no newer row of `name` in that toplevel names another sid."""
    rows = _bindings()
    mine = [r for r in rows if r.get("session_id") == sid]
    if not mine:
        try:  # _bindings reads an unreadable store as empty: that is no evidence the session is unbound
            with _identity().open("rb") as fh:
                fh.read(1)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise CheckFailedError(
                "resolve", f"the identity store is unreadable ({type(exc).__name__})"
            ) from exc
        # every aborted:resolve in rotations.jsonl to 2026-10-25 (24 of 24) was this state; each bound only by a
        # `--force` re-bind 103-2493 s later, never by asking again (W-05021a03)
        raise CheckFailedError(
            "resolve",
            f"session {sid} has no identity binding yet — have that window run "
            f"python3 /opt/fabrik/scripts/whoami_agent.py --as {name} --force",
            transient=False,
        )
    if mine[-1].get("name") != name:
        return False
    top = mine[-1].get("toplevel")
    later = [
        r
        for r in rows[rows.index(mine[-1]) + 1 :]
        if r.get("name") == name and r.get("toplevel") == top
    ]
    return all(r.get("session_id") == sid for r in later)


def resolve(name: str, repo: str) -> dict:
    if not _NAME.fullmatch(name):
        raise CheckFailedError("resolve", f"bad agent name {name!r}", transient=False)
    home, proc = _home(), _proc()
    ls = _tmux("list-panes", "-a", "-F", "#{pane_id}\t#{session_name}\t#{@agent}\t#{pane_pid}")
    if ls.returncode != 0:
        raise CheckFailedError("resolve", "tmux is not answering", transient=True)
    panes: dict[str, int] = {}
    for line in ls.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 4 and parts[1] == slug(repo) and parts[2] == name and parts[3].isdigit():
            panes[parts[0]] = int(parts[3])
    if len(panes) != 1:
        raise CheckFailedError(
            "resolve", f"{len(panes)} panes tagged @agent {name} in the {slug(repo)} grid"
        )
    pane, root = next(iter(panes.items()))
    claudes = _claude_under(proc, root)
    if len(claudes) != 1:
        raise CheckFailedError("resolve", f"{len(claudes)} claude processes under pane {pane}")
    pid = claudes[0]
    reg = _registry(home, proc, pid)
    sid = reg.get("sessionId")
    if not isinstance(sid, str) or not sid:
        raise CheckFailedError(
            "resolve", f"the registry record of pid {pid} carries no session id", transient=True
        )
    if not _bound(name, sid):
        raise CheckFailedError(
            "resolve", f"{name} is bound to another window, not session {sid}", transient=False
        )
    return {
        "name": name,
        "repo": repo,
        "pane": pane,
        "pid": pid,
        "proc_start": str(reg.get("procStart")),
        "sid": sid,
        "cwd": str(reg.get("cwd") or ""),
        "reg": reg,
    }


def _transcript(proc: Path, home: Path, pid: int, sid: str) -> Path:
    config = None
    with contextlib.suppress(OSError):
        for kv in (proc / str(pid) / "environ").read_bytes().split(b"\0"):
            if kv.startswith(b"CLAUDE_CONFIG_DIR="):
                config = Path(kv.split(b"=", 1)[1].decode())
    # A worktree session's transcript sits under its worktree project AND the main checkout's, as hard-linked names
    # of ONE file (W-477d751a): count files by inode, never names. A name stat cannot follow fails closed.
    files: dict[tuple[int, int], Path] = {}
    for f in sorted((config or home / ".claude").glob(f"projects/*/{sid}.jsonl")):
        try:
            st = f.stat()
        except OSError as exc:
            raise CheckFailedError(
                "transcript", f"{f.name}: unreadable ({type(exc).__name__})"
            ) from exc
        files.setdefault((st.st_dev, st.st_ino), f)
    if len(files) != 1:
        raise CheckFailedError(  # none yet clears by itself; two need sorting out
            "transcript", f"{len(files)} transcripts for session {sid}", transient=len(files) < 2
        )
    return next(iter(files.values()))


# ── checks ────────────────────────────────────────────────────────────────────────────────────────────────────────


def _tail_rows(path: Path, size: int) -> list[dict]:
    total = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(max(0, total - size))
        data = fh.read()
    lines = data.split(b"\n")
    if total > size:
        lines = lines[1:]
    rows = []
    for raw in lines:
        with contextlib.suppress(ValueError, RecursionError):
            r = json.loads(raw)
            if isinstance(r, dict):
                rows.append(r)
    return rows


def _idle_row_check(rows: list[dict]) -> float:
    """The last turn end's time; raises unless the tail ends at one. Metadata rows written after a turn end — a resume
    writes pr-link, frame-link and system/informational rows (W-477d751a review: 129 pr-link rows after a turn end,
    quiet for up to 55 min) — are not a turn start."""
    for r in reversed(rows):
        kind, sub = r.get("type"), r.get("subtype")
        if (
            not r.get("timestamp")
            or kind in ("queue-operation", "pr-link", "frame-link")
            or (kind == "system" and sub in ("away_summary", "informational"))
        ):
            continue
        if kind == "system" and sub in TURN_END:
            ended = _ts(r.get("timestamp"))
            if not ended:
                raise CheckFailedError("idle", "the last turn end has no readable time")
            return ended
        content = (
            (r.get("message") or {}).get("content") if isinstance(r.get("message"), dict) else None
        )
        if kind == "user" and isinstance(content, str) and "<command-name>" in content:
            raise CheckFailedError(  # only a sent prompt ends it
                "idle",
                "a local slash command ended the transcript — send one prompt first",
                transient=False,
            )
        raise CheckFailedError("idle", f"the transcript ends mid-turn ({kind}/{sub or '-'})")
    raise CheckFailedError("idle", "no turn end in the transcript tail")


def seats_running(path: Path) -> set[str]:
    """Background Agent / review-workflow seats launched in the tail with no task-notification closing them. Mirrors the
    Stop hook's forms (final_gate_stop._seats_in_flight) without its stamp precondition; an unreadable tail raises."""
    running: set[str] = set()
    for obj in _tail_rows(path, SEAT_TAIL):
        kind, text = obj.get("type"), None
        if kind == "user":
            tur = obj.get("toolUseResult")
            if isinstance(tur, dict):
                aid = None
                if tur.get("status") == "async_launched":
                    aid = tur.get("agentId") or (
                        tur.get("taskId") if tur.get("taskType") == "local_workflow" else None
                    )
                aid = aid or tur.get("resumedAgentId")
                if isinstance(aid, str) and aid:
                    running.add(aid)
            origin = obj.get("origin")
            content = (
                (obj.get("message") or {}).get("content")
                if isinstance(obj.get("message"), dict)
                else None
            )
            if (
                isinstance(origin, dict)
                and origin.get("kind") == "task-notification"
                and isinstance(content, str)
            ):
                text = content
        elif kind == "queue-operation" and obj.get("operation") == "enqueue":
            content = obj.get("content")
            if isinstance(content, str) and content.lstrip().startswith("<task-notification>"):
                text = content
        elif kind == "attachment" and isinstance(obj.get("attachment"), dict):
            att = obj["attachment"]
            origin = att.get("origin")
            if att.get("commandMode") == "task-notification" or (
                isinstance(origin, dict) and origin.get("kind") == "task-notification"
            ):
                text = att.get("prompt") if isinstance(att.get("prompt"), str) else None
        if text:
            for aid, status in _NOTIFY.findall(text):
                if status not in ("running", "in_progress"):
                    running.discard(aid)
    return running


def screen_ok(screen: str) -> bool:
    """The last line starting `❯` is `❯` + only whitespace, a `─` rule right above it and one within three lines below."""
    lines = screen.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("❯")]
    if not idx:
        return False
    i = idx[-1]
    if lines[i].strip().replace("❯", "", 1).strip("  \t"):
        return False
    above = lines[i - 1].strip() if i > 0 else ""
    below = [ln.strip() for ln in lines[i + 1 : i + 4]]
    return above.startswith("─") and any(b.startswith("─") for b in below)


def run_checks(t: dict, stale_text: str = "") -> Path:
    """Checks 0-5 for a resolved target; returns its transcript path. Raises CheckFailedError at the first failure.
    Check 5 passes an empty input box, or under `--stale-input discard` exactly the request's `stale_text`."""
    home, proc = _home(), _proc()
    path = _transcript(proc, home, t["pid"], t["sid"])
    # Check 0 is the transcript's quiet time, never the registry's `status` (W-477d751a): measured 2026-10-23, infra-2
    # ended 13 turns and infra-3 8 after their records last changed (both "busy" since the 06:00 resume), so the
    # registry read busy for idle builders. Check 1 below still requires a turn end as the last real row.
    try:
        quiet = time.time() - path.stat().st_mtime
    except OSError as exc:
        raise CheckFailedError("status", f"transcript unreadable ({exc})") from exc
    if quiet < IDLE_S:
        raise CheckFailedError("status", f"the transcript changed less than {IDLE_S} s ago")
    try:
        rows = _tail_rows(path, 2 * 1024 * 1024)
    except OSError as exc:
        raise CheckFailedError("idle", f"transcript unreadable ({exc})") from exc
    try:
        ended = _idle_row_check(rows)
    except CheckFailedError as exc:
        # a turn held open by a permission dialog never ends by waiting
        if exc.transient and _dialog(_box_now(t["pane"])[1]):
            raise CheckFailedError("screen", _DIALOG, transient=False) from exc
        raise
    # The registry is a VETO only when it changed AFTER that turn end — a turn started since — and only for VETO_S after
    # that change, so its stale "busy" (measured above) never blocks and a busy stamp a resume leaves with no turn after
    # it expires; a turn whose first transcript write is still pending is what this catches. It is best effort: measured
    # 2026-10-23, a registry flip came 0.01-0.02 s before a turn's first write (n=3) but one flipped 1037 s AFTER it,
    # and the gap from a turn start to its first write cannot be read from row timestamps at all.
    reg = t["reg"]
    upd = reg.get("statusUpdatedAt")
    if (
        reg.get("status") not in ("idle", "shell")
        and isinstance(upd, (int, float))
        and upd / 1000 > ended
        and time.time() - upd / 1000 < VETO_S
    ):
        raise CheckFailedError(
            "status", f"the registry turned {reg.get('status')!r} after the last turn end"
        )
    rec = hib._run_record(home, t["sid"])
    if rec is None:
        raise CheckFailedError("record", "run record unreadable")
    for fr in [rec, *(f for f in (rec.get("stack") or []) if isinstance(f, dict))]:
        if fr.get("state") == "running":
            raise CheckFailedError("record", f"run /{fr.get('command', '?')} is still running")
    for s in hib.live_sessions(home, proc):
        if str(s.get("entrypoint") or "").startswith(hib.POOL_PREFIX):
            cur, hops = s.get("ppid"), 0
            while cur and hops < 16:
                if cur == t["pid"]:
                    raise CheckFailedError("seat", f"pool seat pid {s['pid']} is this session's")
                cur, hops = hib._ppid(proc, cur), hops + 1
    try:
        seats = seats_running(path)
    except OSError as exc:
        raise CheckFailedError("seat", f"transcript unreadable ({exc})") from exc
    if seats:
        raise CheckFailedError("seat", f"{len(seats)} background seat(s) still running")
    blocks, why = hib.worktree_state(t["cwd"])
    if blocks:  # an idle builder commits or pushes only when told; any other reason may be a probe that timed out
        raise CheckFailedError(
            "worktree", why, transient=not why.endswith(("uncommitted change(s)", "not pushed"))
        )
    box, screen = _box_now(t["pane"])
    if _dialog(screen):
        raise CheckFailedError("screen", _DIALOG, transient=False)
    if box is None:
        raise CheckFailedError(
            "screen", "no input box is drawn (a redraw, a scrolled or restarting pane)"
        )
    if box and box != stale_text:
        raise CheckFailedError(
            "screen",
            "text is in the input box — clear it, or ask with --stale-input discard",
            transient=False,
        )
    return path


_DIALOG = "a dialog is open in the pane — answer it"


def _dialog(screen: str) -> bool:
    """A permission or choice dialog holds the session: no input box is drawn, the pane's last `❯` row is a numbered
    option (`❯ 1. Yes`) and another numbered option sits within three rows of it. Text typed in the box (`❯ 1. fix
    it`) is the box's, and one numbered prompt left in scrollback has no sibling option (W-05021a03 review r2)."""
    if _box(screen) is not None:
        return False
    rows = [_undimmed(r).strip() for r in screen.splitlines()]
    at = [i for i, r in enumerate(rows) if r.startswith("❯")]
    if not at or not re.match(r"❯\s*\d+\.\s", rows[at[-1]]):
        return False
    near = rows[max(0, at[-1] - 3) : at[-1]] + rows[at[-1] + 1 : at[-1] + 4]
    return any(re.match(r"\d+\.\s", r) for r in near)


# ── request ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _pending() -> bool:
    d = _req_dir()
    for stray in d.glob(
        "*.claimed"
    ):  # an execute killed mid-run left it; past the unit's timeout nobody holds it
        with contextlib.suppress(OSError):
            if time.time() - stray.stat().st_mtime > ORPHAN_S:
                stray.unlink()
                append_row({"outcome": "refused:orphan", "reason": stray.name})
    for tmp in d.glob(
        ".*.tmp"
    ):  # a request killed between write and rename; the rename takes milliseconds
        with contextlib.suppress(OSError):
            if time.time() - tmp.stat().st_mtime > STALE_S:
                tmp.unlink()
                append_row({"outcome": "refused:orphan", "reason": tmp.name})
    # the unit claims a request within seconds and any claim ends inside its timeout, as ORPHAN_S says: a request this
    # old means nothing is claiming (lstat: a dangling name is aged too, never left pending forever)
    for left in d.glob("*.json"):
        with contextlib.suppress(OSError):
            age = time.time() - left.lstat().st_mtime
            if age > ORPHAN_S:
                raise CheckFailedError(
                    "pending",
                    f"{left.name} has waited {int(age)} s unclaimed — is fabrik-rotate.path running? "
                    "(scripts/sysadmin/install_rotate_unit.sh --check)",
                    transient=False,
                )
    if any(d.glob("*.json")) or any(d.glob("*.claimed")) or any(d.glob(".*.tmp")):
        return True
    with contextlib.suppress(OSError), (d / ".lock").open("a") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lk, fcntl.LOCK_UN)
        except OSError:
            return True
    return False


def _last_compact_age(path: Path) -> int | None:
    for r in reversed(_tail_rows(path, 2 * 1024 * 1024)):
        if r.get("type") == "system" and r.get("subtype") == "compact_boundary":
            ts = _ts(r.get("timestamp"))
            return int(time.time() - ts) if ts else None
    return None


def request(
    name: str,
    repo: str,
    compact: str | None,
    trigger: str,
    stale: bool = False,
    operator_ok: str = "",
) -> int:
    mode = "compact" if compact is not None else "clear"
    stale_text = ""
    try:
        if trigger not in TRIGGERS:
            raise CheckFailedError("args", f"trigger must be one of {', '.join(TRIGGERS)}")
        if compact is not None and not _focus_ok(compact):
            raise CheckFailedError(
                "args", "the focus must be one line of 1-300 printable characters"
            )
        if stale != bool(operator_ok) or (stale and not _focus_ok(operator_ok)):
            raise CheckFailedError(
                "args",
                "--stale-input discard needs --operator-ok with the operator's words (1-300 printable characters), "
                "and --operator-ok needs --stale-input discard",
            )
        _ensure_req_dir()
        if _pending():
            raise CheckFailedError(
                "pending", "one rotation at a time — wait for the pending request's row"
            )
        t = resolve(name, repo)
        if stale:
            box, screen = _box_now(t["pane"])
            if _dialog(screen):
                raise CheckFailedError("screen", _DIALOG, transient=False)
            if box is None:
                raise CheckFailedError("screen", "no input box is visible in the pane")
            stale_text = box[:1000]  # the refusal row below still carries what was seen
            if len(box) > 1000:
                raise CheckFailedError(
                    "stale-input", "the input box holds more than 1000 characters"
                )
        path = run_checks(t, stale_text)
    # a tmux call past TMUX_TIMEOUT_S is a slow server, not a refusal
    except (subprocess.TimeoutExpired, CheckFailedError) as raw:
        exc = (
            raw
            if isinstance(raw, CheckFailedError)
            else CheckFailedError("tmux", f"tmux took over {raw.timeout} s")
        )
        row = {
            "name": name,
            "repo": repo,
            "mode": mode,
            "trigger": trigger,
            "outcome": f"aborted:{exc.check}",
            "reason": exc.reason,
        }
        if stale:
            row.update(stale_text=_safe(stale_text), operator_ok=_safe(operator_ok))
        return request_aborted(exc, row)
    tokens = tsc._context_tokens(path)
    window = tsc._window()
    data = {
        "name": name,
        "repo": repo,
        "pane": t["pane"],
        "pid": t["pid"],
        "proc_start": t["proc_start"],
        "sid": t["sid"],
        "mode": mode,
        "focus": compact or "",
        "trigger": trigger,
        "created_at": time.time(),
        "ctx_pre": tokens,
        "window": window,
        "mb_pre": path.stat().st_size // (1024 * 1024),
        "last_compact_age_s": _last_compact_age(path),
    }
    if stale_text:  # optional fields: an ordinary request stays readable by an older unit
        data.update(stale_text=stale_text, operator_ok=operator_ok)
    dest = _req_dir() / f"{slug(repo)}--{name}.json"
    tmp = _req_dir() / f".{slug(repo)}--{name}.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, dest)
    print(
        f"rotate-session: requested {mode} of {name} (pane {t['pane']}); the outcome lands in {_log()}"
    )
    return 0


def request_aborted(exc: CheckFailedError, row: dict) -> int:
    """Row the abort, print the line that says whether asking again can pass, and exit by it (W-05021a03)."""
    append_row(row)
    if not exc.transient:
        hint = "permanent — asking again cannot pass: fix the cause above first"
    elif exc.check == "pending":
        hint = (
            f"transient — ask again once the pending rotation's row lands in {_log()} "
            f"(up to {ORPHAN_S} s); nothing to fix"
        )
    elif exc.check in ("status", "idle", "record", "seat"):
        hint = f"transient — ask again once {row['name']} ends its turn or its run or seat ends; nothing to fix"
    else:
        hint = "transient — ask again in a few seconds; nothing to fix"
    print(f"rotate-session: aborted — {exc.check}: {exc.reason} ({hint})", file=sys.stderr)
    return EXIT_RETRY if exc.transient else 1


def _focus_ok(focus: str) -> bool:
    return 0 < len(focus) <= 300 and focus.isprintable()


# ── execute ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _input_line(screen: str) -> str | None:
    """The text after the last `❯` on the screen, or None when no prompt is visible."""
    lines = [ln for ln in screen.splitlines() if ln.lstrip().startswith("❯")]
    return (
        lines[-1].strip().replace("❯", "", 1).strip() if lines else None
    )  # strip() takes the U+00A0 too


def _capture(pane: str) -> str:
    cap = _tmux("capture-pane", "-p", "-t", pane)
    return cap.stdout if cap.returncode == 0 else ""


# every escape sequence tmux's `capture-pane -e` can emit: CSI (SGR with `;` or `:` parameters, private `>`/`?` forms),
# OSC (a hyperlink, closed by BEL or ST) and the two-byte charset/keypad forms
_ESC = re.compile(
    r"\x1b(?:\[[0-9;:?>=!]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[()][0-9A-Za-z]|[=>78])"
)


def _undimmed(row: str) -> str:
    """The row's text WITHOUT its dim cells (SGR 2 — Claude Code's placeholder, measured), every escape dropped. SGR is
    walked as a terminal does: dim turns on with a 2 in any parameter list and off only with 0, 22 or an empty list —
    any other code (a colour, bold, inverse) leaves it as it was (review r1: a lazy regex ended the dim run at `39m`)."""
    out, dim, pos = [], False, 0
    for m in _ESC.finditer(row):
        if not dim:
            out.append(row[pos : m.start()])
        pos = m.end()
        seq = m.group(0)
        if seq.startswith("\x1b[") and seq.endswith("m"):
            params = [p.split(":")[0] for p in seq[2:-1].split(";")] if len(seq) > 3 else [""]
            for p in params:
                if p in ("", "0", "22"):
                    dim = False
                elif p == "2":
                    dim = True
    if not dim:
        out.append(row[pos:])
    return "".join(out)


def _box(screen: str) -> str | None:
    """The INPUT BOX's text from a `capture-pane -e` screen (W-ee19169d): the last `❯` row with a `─` rule directly
    above it, and every row down to the next `─` rule — a wrapped line continues on indented rows, a Shift+Enter line
    likewise (both measured) — joined with single spaces, whitespace collapsed; dim text (the fresh box's placeholder)
    is no text. "" for an empty box, None when no framed box is visible. Check 5 reads this, never the `❯` row alone,
    which missed every row below it."""
    rows = screen.splitlines()
    plain = [_ESC.sub("", r) for r in rows]
    starts = [
        i
        for i, r in enumerate(plain)
        if i > 0 and r.lstrip().startswith("❯") and plain[i - 1].strip().startswith("─")
    ]
    if not starts:
        return None
    i = starts[-1]
    end = next((j for j in range(i + 1, len(rows)) if plain[j].strip().startswith("─")), None)
    if end is None:
        return None
    parts = []
    for k in range(i, end):
        text = _undimmed(rows[k])
        if k == i:
            text = text.replace("❯", "", 1)
        parts.append(text)
    return " ".join(" ".join(parts).split())


def _box_now(pane: str) -> tuple[str | None, str]:
    cap = _tmux("capture-pane", "-p", "-e", "-t", pane)
    screen = cap.stdout if cap.returncode == 0 else ""
    return _box(screen), screen


def _discard(t: dict, seen: str) -> None:
    """Clear a stuck input box the coordinator's request saw (W-ee19169d), or raise `stale-input`. Before the key the
    box must read exactly `seen` on two captures 2 s apart (someone may be typing in that pane), and then EVERY check
    re-runs (`run_checks` with `seen` — the session idle, its box still exactly `seen`) right before it: an Escape in a
    running turn interrupts it (review r1). Claude Code clears a NON-empty box on a fast double Escape (one send-keys
    call; two sent 1.5 s apart do nothing); C-u deletes only the current row (both measured 2026-10-23). After the key
    a capture still showing `seen` is a redraw not yet drawn and is waited out, never acted on. A double Escape on an
    EMPTY box opens the Rewind menu (measured) — no framed box and the word on screen — which gets ONE Escape and a
    refusal; that Escape is the only key besides the pair."""
    pane = t["pane"]
    for wait in (0.0, DISCARD_RECHECK_S):
        time.sleep(wait)
        if _box_now(pane)[0] != seen:
            raise CheckFailedError("stale-input", "the input box changed since the request")
    run_checks(t, seen)
    # check 5 also passes an EMPTY box; a box emptied in this window would turn the pair into a Rewind (review r2)
    if _box_now(pane)[0] != seen:
        raise CheckFailedError("stale-input", "the input box changed since the request")
    if _tmux("send-keys", "-t", pane, "Escape", "Escape").returncode != 0:
        raise CheckFailedError("stale-input", "tmux refused the keys")
    deadline = time.time() + _wait_s(DISCARD_WAIT_S)
    while time.time() < deadline:
        box, screen = _box_now(pane)
        if box == "":
            return
        if box is None and "Rewind" in _ESC.sub("", screen):
            _tmux("send-keys", "-t", pane, "Escape")
            raise CheckFailedError(
                "stale-input", "the double Escape opened the Rewind menu; closed"
            )
        time.sleep(0.5)
    raise CheckFailedError(
        "stale-input", "the input box did not read empty after the double Escape"
    )


def _send(pane: str, text: str) -> None:
    """Type `text` and SUBMIT it (W-b92aa5cf). An Enter sent right behind a `-l` paste is swallowed by the paste, so
    the text sat unsent in every rotated pane. Now: paste; wait until the INPUT LINE shows this text (its first 20
    characters, or Claude Code's collapsed `[Pasted text`) unchanged over two captures — the input line only, so a
    ticking status line cannot stall it and a placeholder or a stale `❯` history line cannot pass for the paste; send
    C-m as its own call; then require the input line to hold something other than the settled text (empty, a
    placeholder after /clear, a dialog) — a blank redraw frame is no reading and is waited out. A text still there
    raises `unsent`, rowed `typed-unsent:<step>`; nothing is re-sent (keys are never retried)."""
    if _tmux("send-keys", "-t", pane, "-l", "--", text).returncode != 0:
        raise CheckFailedError("send", "tmux refused the keys")
    head, seen, prev, settled = text[:20], False, None, None
    deadline = time.time() + _wait_s(SEND_SETTLE_S)
    while time.time() < deadline:
        line = _input_line(_capture(pane))
        shown = bool(line) and (head in line or line.startswith("[Pasted text"))
        seen = seen or shown
        if shown and line == prev:
            settled = line
            break
        prev = line if shown else None
        time.sleep(0.5)
    if settled is None:
        why = "never settled" if seen else "never showed in the input line"
        raise CheckFailedError("unsent", f"the pasted text {why}")
    if _tmux("send-keys", "-t", pane, "C-m").returncode != 0:
        raise CheckFailedError("send", "tmux refused the Enter")
    deadline = time.time() + _wait_s(SEND_SUBMIT_S)
    while time.time() < deadline:
        line = _input_line(_capture(pane))
        if line is not None and line != settled:
            return
        time.sleep(0.5)
    raise CheckFailedError("unsent", "the text is still in the input line after C-m")


def resume_prompt(name: str) -> str:
    return (
        f"You were rotated at an item boundary (D-1119). First re-arm your self-watch: run bash "
        f"/opt/fabrik/scripts/sysadmin/selfwatch_arm.sh <your session id> in the background. Then run python3 "
        f"/opt/fabrik/scripts/whoami_agent.py --as {name} --force. Then read only your memory notes, python3 "
        f"scripts/work.py next and your run's seed if one is named there — never the previous transcript — and carry on. "
        # W-1783a9fe: one Bash call reading all of the above printed 40-47 KB, the harness saved it to a file, and paging
        # that file with sed on a shell variable stopped Claude Code's worktree-isolation check for a person (10 min in
        # intel's pane); the Read tool opens the same saved file with no prompt (measured)
        f"Read your memory notes and seed with the Read tool, not cat; run each command, git included, as a separate "
        f"Bash call (the self-watch arm stays in the background); open any output the harness saved to a file with "
        f"the Read tool (offset and limit) — never give sed, awk or head a shell variable or $( ), in the file name "
        f"or the expression."
    )


def _validate(data: object) -> dict:
    if not isinstance(data, dict) or not FIELDS <= set(data) <= FIELDS | OPTIONAL:
        raise CheckFailedError("request", "malformed request file")
    if set(data) & OPTIONAL and not (
        set(data) >= OPTIONAL
        and isinstance(data["stale_text"], str)
        and 0 < len(data["stale_text"]) <= 1000
        and isinstance(data["operator_ok"], str)
        and _focus_ok(data["operator_ok"])
    ):
        raise CheckFailedError("request", "bad stale_text or operator_ok")
    if not all(
        isinstance(data[k], str)
        for k in ("name", "repo", "pane", "sid", "proc_start", "mode", "focus", "trigger")
    ):
        raise CheckFailedError("request", "a text field is not a string")
    if (
        type(data["pid"]) is not int
        or not isinstance(data["created_at"], (int, float))
        or isinstance(data["created_at"], bool)
    ):
        raise CheckFailedError("request", "pid or created_at is not a number")
    if not math.isfinite(data["created_at"]) or data["created_at"] > time.time() + 5:
        raise CheckFailedError("request", "created_at is not a finite time in the past")
    if not _NAME.fullmatch(str(data["name"])) or not _PANE.fullmatch(str(data["pane"])):
        raise CheckFailedError("request", "bad name or pane")
    if data["mode"] not in ("clear", "compact") or data["trigger"] not in TRIGGERS:
        raise CheckFailedError("request", "bad mode or trigger")
    if data["mode"] == "compact" and not _focus_ok(str(data["focus"])):
        raise CheckFailedError("request", "bad focus")
    if time.time() - data["created_at"] > STALE_S:
        raise CheckFailedError("stale", f"the request is older than {STALE_S} s")
    return data


def _one(claimed: Path) -> dict:
    row: dict = {"outcome": "refused:request"}
    try:
        data = _validate(json.loads(claimed.read_text(encoding="utf-8")))
        row = {
            k: data[k]
            for k in (
                "name",
                "repo",
                "pane",
                "pid",
                "mode",
                "trigger",
                "ctx_pre",
                "window",
                "mb_pre",
                "last_compact_age_s",
            )
        }
        row["old_sid"] = data["sid"]
        stale_text = str(data.get("stale_text") or "")
        if stale_text:  # the discarded line stays recoverable from the log
            row.update(stale_text=_safe(stale_text), operator_ok=_safe(str(data["operator_ok"])))
        t = resolve(data["name"], data["repo"])
        if (t["pane"], t["pid"], t["proc_start"], t["sid"]) != (
            data["pane"],
            data["pid"],
            data["proc_start"],
            data["sid"],
        ):
            raise CheckFailedError(
                "resolve", "the pane, its claude or its session changed since the request"
            )
        path = run_checks(t, stale_text)
        if stale_text:
            box = _box_now(t["pane"])[0]
            # a blank or redrawing frame is no reading — never paste behind unseen text (review r1)
            if box is None:
                raise CheckFailedError("screen", "no input box is visible in the pane")
            # a refusal inside sends at most the Escape pair and one closing Escape
            if box:
                _discard(t, stale_text)
    except Exception as exc:  # noqa: BLE001 — before the first key every fault is a refusal, rowed, never a crash
        check = (
            exc.check
            if isinstance(exc, CheckFailedError)
            else ("request" if isinstance(exc, ValueError) else "error")
        )
        row["outcome"] = "stale" if check == "stale" else f"refused:{check}"
        row["reason"] = exc.reason if isinstance(exc, CheckFailedError) else str(exc)
        return row
    step = "send"
    try:
        sent_at = time.time()
        if data["mode"] == "compact":
            step = "compact-send"  # a row names WHICH text stayed unsent (review r1)
            _send(data["pane"], f"/compact {data['focus']}")
            step = "compact"
            deadline = time.time() + _wait_s(COMPACT_WAIT_S)
            while time.time() < deadline:
                if any(
                    r.get("subtype") == "compact_boundary"
                    and (_ts(r.get("timestamp")) or 0) >= sent_at - 1
                    for r in _tail_rows(path, 2 * 1024 * 1024)
                ):
                    row["outcome"] = "ok"
                    return row
                time.sleep(1)
            row["outcome"] = "partial:queued"
            return row
        _send(data["pane"], f"/clear {data['name']}-{time.strftime('%Y-%m-%d')}")
        step, new_sid, deadline = "clear", None, time.time() + _wait_s(CLEAR_WAIT_S)
        while time.time() < deadline:
            with contextlib.suppress(CheckFailedError):
                sid = _registry(_home(), _proc(), data["pid"]).get("sessionId")
                if isinstance(sid, str) and sid and sid != data["sid"]:
                    new_sid = sid
                    break
            time.sleep(1)
        if not new_sid:
            row["outcome"] = "partial:queued"
            return row
        row["new_sid"] = new_sid
        # W-b72231b8: the pane runs the new session now, bound or not — re-point before anything else can fail
        reg_file = _session_registry(data["repo"], data["sid"])
        row["registry"] = (
            "refused:repo"
            if reg_file is None
            else _repoint_registry(reg_file, data["sid"], new_sid, data["name"])
        )
        step = "resume"
        row["resume_sent_at"] = int(time.time())
        _send(data["pane"], resume_prompt(data["name"]))
        step, deadline = "rebind", time.time() + _wait_s(REBIND_GRACE_S)
        while time.time() < deadline:
            hit = [
                r
                for r in _bindings()
                if r.get("session_id") == new_sid and r.get("name") == data["name"]
            ]
            if hit:
                row["predecessor_row"] = hit[-1].get("predecessor") == data["sid"]
                at = hit[-1].get("at")
                if isinstance(at, (int, float)) and not isinstance(at, bool) and math.isfinite(at):
                    row["rebind_s"] = (
                        int(at) - row["resume_sent_at"]
                    )  # the bind's own time, not when it was seen
                row["outcome"] = "ok"
                return row
            time.sleep(1)
        row["predecessor_row"] = False
        row["outcome"] = "partial:rebind"
        return row
    except Exception as exc:  # noqa: BLE001 — after a key is sent the outcome is recorded, never retried
        unsent = isinstance(exc, CheckFailedError) and exc.check == "unsent"
        row["outcome"] = f"typed-unsent:{step}" if unsent else f"partial:{step}"
        row["reason"] = str(exc)
        return row


def execute() -> int:
    try:
        d = _ensure_req_dir()
    except CheckFailedError as exc:
        append_row({"outcome": f"refused:{exc.check}", "reason": exc.reason})
        print(f"rotate-session: refused — {exc.check}: {exc.reason}", file=sys.stderr)
        return 1
    with (d / ".lock").open("a") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0  # another execute holds it; the path unit fires again when it exits

        def _age(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except OSError:
                return 0.0  # dangling or vanished: claimed first, and refused below

        started = time.monotonic()
        for f in sorted(d.glob("*.json"), key=_age):
            if time.monotonic() - started > CLAIM_CUTOFF_S:
                break  # W-b72231b8: left for the path unit's next start, never begun where the timeout could kill it
            claimed = f.with_suffix(".claimed")
            try:
                if not f.is_file() or f.is_symlink():
                    raise OSError("not a regular file")
                os.replace(f, claimed)
            except (
                OSError
            ) as exc:  # never leave a matching file behind: the path unit would re-fire forever
                with contextlib.suppress(OSError):
                    f.unlink()
                if (
                    f.exists() or f.is_symlink()
                ):  # a directory: unlink cannot remove it, so move it out of the glob
                    with contextlib.suppress(OSError):
                        os.replace(
                            f, f.with_name(f"{f.name}.rejected-{time.time_ns()}")
                        )  # unique: never onto an earlier one
                append_row({"outcome": "refused:claim", "reason": f"{f.name}: {exc}"})
                continue
            try:
                row = _one(claimed)
            finally:
                with contextlib.suppress(OSError):
                    claimed.unlink()
            append_row(row)
        for stray in d.glob(
            "*.claimed"
        ):  # a crash mid-run left one: drop it, rowed, so the path unit never loops
            with contextlib.suppress(OSError):
                stray.unlink()
            append_row({"outcome": "refused:orphan", "reason": stray.name})
    return 0


# ── due: the read-only listing behind the lift offers and the nightly mail (slice 3) ──────────────────────────────────


def _safe(text: str) -> str:
    """Registry text (a session id, a cwd) can carry a lone surrogate from JSON: escape it, so printing a row or writing
    the mail body never raises UnicodeEncodeError (review B1)."""
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def due(home: Path, proc: Path, mb_only: bool = False, opt: str = "/opt") -> list[dict]:
    """Every live agent at/past ctx CTX_ROTATE_PCT or the hook's MB line (`state: due`), and every session that cannot
    be read, or is past the line with no agent name (`state: unread`, with its reason). Pool seats are never rows; the caller and the coordinators are. `mb_only`
    reads no context: the nightly runs while agents may be mid-item, and the MB line is the disk signal it owns."""
    threshold = tsc._threshold_mb()
    rows = []
    for s in hib.live_sessions(home, proc, opt):
        if hib._is_pool(s):
            continue
        row = {k: s.get(k) for k in ("agent", "repo", "sid", "pid", "entrypoint")}
        row.update({k: _safe(row[k]) for k in ("repo", "sid") if isinstance(row[k], str)})
        try:
            path = _transcript(proc, home, int(s["pid"]), str(s["sid"]))
            mb = path.stat().st_size // (1024 * 1024)
            ctx = None
            if not mb_only:
                tokens = tsc._context_tokens(path)
                if tokens is not None:
                    ctx = tokens * 100 // tsc._window()
        except Exception as exc:  # noqa: BLE001 — an unreadable session is a visible row, never a dropped one
            row.update(
                state="unread",
                reason=_safe(
                    f"{exc.check}: {exc.reason}"
                    if isinstance(exc, CheckFailedError)
                    else f"{type(exc).__name__}: {exc}"
                ),
            )
            rows.append(row)
            continue
        trigger = (
            "ctx"
            if ctx is not None and ctx >= tsc.CTX_ROTATE_PCT
            else "mb"
            if mb >= threshold
            else ""
        )
        if not trigger:
            continue
        if not _NAME.fullmatch(str(s.get("agent") or "")):
            # past the line but nameless: no command can name it — visible, never dropped; under the line it is no row,
            # so an unnamed small session never mails a repo nightly (review A6)
            rows.append(
                dict(row, state="unread", reason="agent: no valid agent name bound to this session")
            )
            continue
        rows.append(dict(row, state="due", trigger=trigger, ctx=ctx, mb=mb))
    return rows


def offer(row: dict) -> str:
    """The action for one due row: the exact rotate command for a tmux (cli) agent, the operator's /clear otherwise."""
    if not row.get("repo"):
        return "outside every /opt repo — no grid to rotate in; rotate it by hand"
    if row.get("entrypoint") == "cli":
        return (
            f"/opt/fabrik/scripts/sysadmin/agents_up.sh rotate-session {row['agent']} --repo {row['repo']} "
            f"--trigger {row['trigger']}"
        )
    return f"no pane — the operator types `/clear {row['agent']}-{time.strftime('%Y-%m-%d')}`"


def _line(row: dict) -> str:
    """One row as text — the one place the lift offer and the mail body read a row from, so it is escaped here whole
    (any registry field may carry a lone surrogate; review C1, r2)."""
    if row["state"] == "unread":
        text = f"- {row.get('agent') or '(unnamed)'} [{row.get('sid')}] unread — {row['reason']}"
    else:
        ctx = "—" if row.get("ctx") is None else f"{row['ctx']}%"
        text = f"- {row['agent']} ctx {ctx} · {row['mb']} MB → {offer(row)}"
    return _safe(text)


def mail_due(rows: list[dict]) -> int:
    """One `--ack no` request per repo with due or unread rows (the hub's to its coordinator); a session outside every
    /opt repo is printed, never mailed. A failed send is reported and exits 1, after every other repo was tried."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("repo"):
            by.setdefault(str(r["repo"]), []).append(r)
        else:
            print(f"rotate-session due: outside every repo, not mailed: {_line(r)}")
    rc = 0
    for repo, rs_ in sorted(by.items()):
        name = Path(repo).name
        n_due = sum(r["state"] == "due" for r in rs_)
        body = "\n".join(
            [
                f"Rotation due: {n_due} agent(s) in {name} past the rotation line, {len(rs_) - n_due} unread",
                "",
                f"WHAT: these sessions are at/past the rotation line (ctx {tsc.CTX_ROTATE_PCT}% or "
                f"{tsc._threshold_mb()} MB; a ctx of — was not read), or could not be read:",
                *(_line(r) for r in rs_),
                "WHY: a transcript past the line slows every load and its context costs every turn (D-1119, D-1123).",
                "WHERE: ~/.claude/state/rotations.jsonl records each rotation's outcome.",
                "HOW: never typed for you: run each at that agent's next item boundary.",
                f"WHEN: listed {time.strftime('%Y-%m-%d %H:%M')} by the nightly session-archive unit.",
                "WHO: this repo's coordinator.",
                "SYSTEMIC: the listing repeats nightly while a size stays past the line; the rotation row is the proof.",
            ]
        )
        cmd = [
            sys.executable,
            str(HERE.parent / "mail.py"),
            "send",
            "--to",
            name,
            "--kind",
            "request",
        ]
        cmd += ["--ack", "no", "--from", "fabrik"]
        if name == "fabrik":
            cmd += ["--to-agent", "coordinator"]
        try:  # the body file too: a full /tmp fails THIS repo's send, never the repos after it (review A7)
            with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as fh:
                fh.write(body + "\n")
                fh.flush()
                out = subprocess.run(
                    [*cmd, "--body-file", fh.name], capture_output=True, text=True, timeout=60
                )
            ok, why = out.returncode == 0, (out.stderr or out.stdout).strip()[-300:]
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            ok, why = False, str(exc)
        if not ok:
            print(f"rotate-session due: mail to {name} failed — {why}", file=sys.stderr)
            rc = 1
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rotate_session.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rq = sub.add_parser("request")
    rq.add_argument("name")
    rq.add_argument("--compact", metavar="FOCUS")
    rq.add_argument("--trigger", default="manual")
    rq.add_argument("--repo", default="")
    rq.add_argument(
        "--stale-input",
        choices=("discard",),
        help="clear the text stuck in the pane's input box first (W-ee19169d); needs --operator-ok",
    )
    rq.add_argument(
        "--operator-ok",
        default="",
        metavar="WORDS",
        help="the operator's words allowing the discard",
    )
    sub.add_parser("execute")
    du = sub.add_parser("due")
    du.add_argument("--mb-only", action="store_true")
    du.add_argument("--mail", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "execute":
        return execute()
    if a.cmd == "due":
        rows = due(_home(), _proc(), mb_only=a.mb_only)
        for r in rows:
            print(f"{r.get('repo') or '(no repo)'} {_line(r)}")
        return mail_due(rows) if a.mail else 0
    # the grid is named after the MAIN checkout's folder, so a coordinator in a linked worktree uses the common dir's parent
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    repo = a.repo or (str(Path(common).parent) if common else "")
    if not repo:
        print("rotate-session: not inside a git repo — pass --repo", file=sys.stderr)
        return 2
    return request(a.name, repo, a.compact, a.trigger, a.stale_input == "discard", a.operator_ok)


if __name__ == "__main__":
    sys.exit(main())
