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
TRIGGERS = ("ctx", "mb", "unrelated", "compact", "manual", "lift")
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
_PANE = re.compile(r"%[0-9]{1,6}")
_NOTIFY = re.compile(
    r"<task-id>([^<\s]+)</task-id>.*?<status>([^<\s]+)</status>", re.S
)  # the Stop hook's forms


class CheckFailedError(Exception):
    """A check failed: (check, reason)."""

    def __init__(self, check: str, reason: str) -> None:
        super().__init__(f"{check}: {reason}")
        self.check, self.reason = check, reason


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
        st = d.lstat()
    except OSError as exc:
        raise CheckFailedError("request", f"{d}: {type(exc).__name__}") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise CheckFailedError("request", f"{d} is not a plain directory")
    if st.st_uid != os.getuid():
        raise CheckFailedError("request", f"{d} is owned by uid {st.st_uid}")
    if stat.S_IMODE(st.st_mode) != 0o700:
        d.chmod(0o700)
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


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [os.environ.get("ROTATE_TMUX", "tmux"), *args], capture_output=True, text=True, timeout=10
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
    raise CheckFailedError("resolve", f"no registry record for claude pid {pid}")


def _bindings() -> list[dict]:
    rows = []
    try:
        for line in _identity().read_text(encoding="utf-8").splitlines():
            with contextlib.suppress(ValueError):
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
    if not mine or mine[-1].get("name") != name:
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
        raise CheckFailedError("resolve", f"bad agent name {name!r}")
    home, proc = _home(), _proc()
    ls = _tmux("list-panes", "-a", "-F", "#{pane_id}\t#{session_name}\t#{@agent}\t#{pane_pid}")
    if ls.returncode != 0:
        raise CheckFailedError("resolve", "tmux is not answering")
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
        raise CheckFailedError("resolve", f"the registry record of pid {pid} carries no session id")
    if not _bound(name, sid):
        raise CheckFailedError(
            "resolve", f"{name}'s identity binding is stale or another window's (session {sid})"
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
        raise CheckFailedError("transcript", f"{len(files)} transcripts for session {sid}")
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
            raise CheckFailedError(
                "idle", "a local slash command ended the transcript — send one prompt first"
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


def run_checks(t: dict) -> Path:
    """Checks 0-5 for a resolved target; returns its transcript path. Raises CheckFailedError at the first failure."""
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
    ended = _idle_row_check(rows)
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
    if blocks:
        raise CheckFailedError("worktree", why)
    cap = _tmux("capture-pane", "-p", "-t", t["pane"])
    if cap.returncode != 0 or not screen_ok(cap.stdout):
        raise CheckFailedError("screen", "the pane is not at an empty prompt")
    return path


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


def request(name: str, repo: str, compact: str | None, trigger: str) -> int:
    mode = "compact" if compact is not None else "clear"
    try:
        if trigger not in TRIGGERS:
            raise CheckFailedError("args", f"trigger must be one of {', '.join(TRIGGERS)}")
        if compact is not None and not _focus_ok(compact):
            raise CheckFailedError(
                "args", "the focus must be one line of 1-300 printable characters"
            )
        _ensure_req_dir()
        if _pending():
            raise CheckFailedError(
                "pending", "one rotation at a time — wait for the pending request's row"
            )
        t = resolve(name, repo)
        path = run_checks(t)
    except CheckFailedError as exc:
        append_row(
            {
                "name": name,
                "repo": repo,
                "mode": mode,
                "trigger": trigger,
                "outcome": f"aborted:{exc.check}",
                "reason": exc.reason,
            }
        )
        print(f"rotate-session: aborted — {exc.check}: {exc.reason}", file=sys.stderr)
        return 1
    tokens = tsc._context_tokens(path)
    window = tsc._window(t["sid"], tokens or 0)
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
    dest = _req_dir() / f"{slug(repo)}--{name}.json"
    tmp = _req_dir() / f".{slug(repo)}--{name}.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, dest)
    print(
        f"rotate-session: requested {mode} of {name} (pane {t['pane']}); the outcome lands in {_log()}"
    )
    return 0


def _focus_ok(focus: str) -> bool:
    return 0 < len(focus) <= 300 and focus.isprintable()


# ── execute ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _send(pane: str, text: str) -> None:
    for args in (("send-keys", "-t", pane, "-l", "--", text), ("send-keys", "-t", pane, "Enter")):
        if _tmux(*args).returncode != 0:
            raise CheckFailedError("send", "tmux refused the keys")


def resume_prompt(name: str) -> str:
    return (
        f"You were rotated at an item boundary (D-1119). First re-arm your self-watch: run bash "
        f"/opt/fabrik/scripts/sysadmin/selfwatch_arm.sh <your session id> in the background. Then run python3 "
        f"/opt/fabrik/scripts/whoami_agent.py --as {name} --force. Then read only your memory notes, python3 "
        f"scripts/work.py next and your run's seed if one is named there — never the previous transcript — and carry on."
    )


def _validate(data: object) -> dict:
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise CheckFailedError("request", "malformed request file")
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
        path = run_checks(t)
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
            _send(data["pane"], f"/compact {data['focus']}")
            step = "compact"
            deadline = time.time() + _wait_s(60)
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
        step, new_sid, deadline = "clear", None, time.time() + _wait_s(60)
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
        step = "resume"
        _send(data["pane"], resume_prompt(data["name"]))
        step, deadline = "rebind", time.time() + _wait_s(90)
        while time.time() < deadline:
            hit = [
                r
                for r in _bindings()
                if r.get("session_id") == new_sid and r.get("name") == data["name"]
            ]
            if hit:
                row["predecessor_row"] = hit[-1].get("predecessor") == data["sid"]
                row["outcome"] = "ok"
                return row
            time.sleep(1)
        row["predecessor_row"] = False
        row["outcome"] = "partial:rebind"
        return row
    except Exception as exc:  # noqa: BLE001 — after a key is sent the outcome is recorded, never retried
        row["outcome"] = f"partial:{step}"
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

        for f in sorted(d.glob("*.json"), key=_age):
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


def due(home: Path, proc: Path, mb_only: bool = False, opt: str = "/opt") -> list[dict]:
    """Every live agent at/past ctx CTX_ROTATE_PCT or the hook's MB line (`state: due`), and every one that cannot be
    read (`state: unread`, with its reason). Pool seats are never rows; the caller and the coordinators are. `mb_only`
    reads no context: the nightly runs while agents may be mid-item, and the MB line is the disk signal it owns."""
    threshold = tsc._threshold_mb()
    rows = []
    for s in hib.live_sessions(home, proc, opt):
        if hib._is_pool(s):
            continue
        row = {k: s.get(k) for k in ("agent", "repo", "sid", "pid", "entrypoint")}
        try:
            if not _NAME.fullmatch(str(s.get("agent") or "")):
                raise CheckFailedError("agent", "no valid agent name bound to this session")
            path = _transcript(proc, home, int(s["pid"]), str(s["sid"]))
            mb = path.stat().st_size // (1024 * 1024)
            ctx = None
            if not mb_only:
                tokens = tsc._context_tokens(path)
                if tokens is not None:
                    ctx = tokens * 100 // tsc._window(str(s["sid"]), tokens)
        except Exception as exc:  # noqa: BLE001 — an unreadable session is a visible row, never a dropped one
            row.update(
                state="unread",
                reason=f"{exc.check}: {exc.reason}"
                if isinstance(exc, CheckFailedError)
                else f"{type(exc).__name__}: {exc}",
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
        if trigger:
            rows.append(dict(row, state="due", trigger=trigger, ctx=ctx, mb=mb))
    return rows


def offer(row: dict) -> str:
    """The action for one due row: the exact rotate command for a tmux (cli) agent, the operator's /clear otherwise."""
    if row.get("entrypoint") == "cli":
        return (
            f"/opt/fabrik/scripts/sysadmin/agents_up.sh rotate-session {row['agent']} --repo {row['repo']} "
            f"--trigger {row['trigger']}"
        )
    return f"no pane — the operator types `/clear {row['agent']}-{time.strftime('%Y-%m-%d')}`"


def _line(row: dict) -> str:
    if row["state"] == "unread":
        return f"- {row.get('agent') or '(unnamed)'} [{row.get('sid')}] unread — {row['reason']}"
    ctx = "—" if row.get("ctx") is None else f"{row['ctx']}%"
    return f"- {row['agent']} ctx {ctx} · {row['mb']} MB → {offer(row)}"


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
                f"{tsc._threshold_mb()} MB), or could not be read:",
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
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as fh:
            fh.write(body + "\n")
            fh.flush()
            try:
                out = subprocess.run(
                    [*cmd, "--body-file", fh.name], capture_output=True, text=True, timeout=60
                )
                ok, why = out.returncode == 0, (out.stderr or out.stdout).strip()[-300:]
            except (OSError, subprocess.TimeoutExpired) as exc:
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
    return request(a.name, repo, a.compact, a.trigger)


if __name__ == "__main__":
    sys.exit(main())
