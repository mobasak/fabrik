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
_NAME_RE = re.compile(r"^[a-z0-9-]{1,32}$")

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


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        return Path(f"/proc/{pid}").is_dir()
    except OSError:
        return False


def _toplevel() -> str:
    """The git toplevel, or "" — the collision scope.

    ⚠️ NOT ``os.getcwd()``. Executed: with a cwd-scoped check, a plain ``cd`` into a subdirectory
    bound a name another live session held, at rc 0 and with no ``--force`` recorded — cheaper than
    the sanctioned override and leaving no trace. A session's cwd is not stable either
    (``docs/workstation/session-recall.md:43``: a session that changes cwd is RE-FILED mid-session,
    and ``EnterWorktree`` moves it into ``<repo>/.claude/worktrees/<name>``).
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _rows(path: Path) -> list[dict]:
    """Every parseable row, oldest first. A corrupt line is skipped, never fatal."""
    try:
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
        if _NAME_RE.match(env):
            return env
        sid = session_id()
        if not sid:
            return ""
        name = ""
        for row in _rows(store_path()):  # LAST row wins for this sid
            if row.get("session_id") == sid and _NAME_RE.match(str(row.get("name") or "")):
                name = str(row["name"])
        return name
    except Exception:
        return ""


def _write_rows(path: Path, rows: list[dict]) -> None:
    """Rewrite the store from `rows` via a temp file + atomic replace (the trim path)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        buf = data.encode("utf-8")
        while buf:
            buf = buf[os.write(fd, buf) :]
    finally:
        os.close(fd)
    os.replace(tmp, path)


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
    if not _NAME_RE.match(name):
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
    rows = _rows(path)
    top = _toplevel()

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
            if top and str(r.get("toplevel") or "") != top:
                continue
            if _pid_alive(r.get("pid")):
                return 1, (
                    f"whoami_agent: refused — {name!r} is held by a LIVE session (pid "
                    f"{r.get('pid')}) in this repo. Pick another name, or --force if that session "
                    "is gone. ⚠️ Two sessions on one name is the cheapest way to look named "
                    "without being attributable, and nothing downstream catches it."
                )

    row = {
        "session_id": sid,
        "name": name,
        "pid": _session_pid(),
        "toplevel": top,
        "at": int(time.time()),
        "force": bool(force),
    }
    cutoff = int(time.time()) - _TRIM_AFTER_S
    keep = [r for r in rows if int(r.get("at") or 0) >= cutoff]
    if len(keep) != len(rows):
        _write_rows(path, keep + [row])
    else:
        _append_row(path, row)
    return 0, f"whoami_agent: {name} bound to session {sid}" + (" (forced)" if force else "")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="whoami_agent.py",
        description="Bind THIS live session to an agent name, or print the resolved name.",
    )
    ap.add_argument("--as", dest="name", help="the agent name to bind this session to")
    ap.add_argument("--force", action="store_true", help="override a collision, and record that")
    ap.add_argument("--who", action="store_true", help="print the resolved name and exit")
    args = ap.parse_args(argv[1:])
    if args.who or not args.name:
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
