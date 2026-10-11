#!/usr/bin/env python3
# AFTER-EDIT: tests/test_transcript_size_check.py | docs/workstation/hooks-index.md | docs/workstation/session-history-retention.md | scripts/sysadmin/install_user_hooks.py
"""transcript_size_check — the ROTATE advisory (C.1.3 of the session-history retention plan, D-736).

A USER-level `UserPromptSubmit` hook in every window of every repo. It reads the hook JSON, stats
the session's transcript and, when the file is at or past `ROTATE_ADVISE_MB` (default 200) AND has
crossed a 100 MB step this session has not been told about yet, prints ONE line:

    ROTATE: this session's transcript is <N> MB — run `/clear <agent>-<YYYY-MM-DD>` now, then
    `python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force` (safe here: the name's holder
    is pid <P>, this window's own claude process); the previous session stays resumable and is
    archived tonight (D-736)

Why 200: the VS Code extension host loads every listed session's history into its 4 GB heap
(anthropics/claude-code #89075); it crashed users at 467 MB (#23953) and crash-loops past 2 GiB
(#97229). A busy hub window grows ~25 MB/day, so 200 MB is roughly a week.

STAMPED, never per-prompt: `~/.claude/state/rotate-advised/<session_id>` holds the 100 MB step last
advised, and the line prints only when the size has crossed a NEW step (200, 300, 400 …). The
per-prompt shape was measured and rejected as wallpaper before this hook existed
(`install_user_hooks.py`, D-184/D-187).

The agent name is `CLAUDE_AGENT`, else the identity row for this session id, else the registry
join (the `~/.claude/sessions/<pid>.json` entry carrying this session id, joined on
`pid`+`procStart` to an identity row's `pid`+`pid_start`, both as integers — a `/clear` mints a new
session id but keeps the claude process). `<P>` is this window's claude pid, found by the same
`/proc` ancestry walk `whoami_agent._session_pid` uses. `--force` is needed because the plain
re-bind is refused: the holder row is this window's own pre-`/clear` session, alive on the same
pid (`whoami_agent.py:356-373`); the pid in the line is what makes typing `--force` informed.

FAIL-OPEN: any error ⇒ exit 0, no output. This hook can only ADD a line, never block a prompt.

Env: `ROTATE_ADVISE_MB` (process env, else the `ROTATE_ADVISE_MB=` line of
`SESSION_ARCHIVE_ENV_FILE`, default /opt/fabrik/.env, else 200), `ROTATE_STAMP_DIR`
(default ~/.claude/state/rotate-advised), `AGENT_IDENTITY_FILE`, `CLAUDE_SESSIONS_DIR`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

MB = 1024 * 1024
STEP_MB = 100
DEFAULT_THRESHOLD_MB = 200
_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent._NAME_RE, byte-identical
_ENV_LINE = re.compile(r"^(?:export\s+)?(ROTATE_ADVISE_MB)=(.*)$")


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def _threshold_mb() -> int:
    raw = os.environ.get("ROTATE_ADVISE_MB", "").strip()
    if not raw:
        try:
            for line in (
                _env_path("SESSION_ARCHIVE_ENV_FILE", "/opt/fabrik/.env")
                .read_text(encoding="utf-8")
                .splitlines()
            ):
                m = _ENV_LINE.match(line.strip())
                if m:
                    raw = re.split(r"\s+#", m.group(2).strip().strip("'\""), maxsplit=1)[0].strip()
        except (OSError, UnicodeDecodeError):
            raw = ""
    try:
        return max(1, int(float(raw))) if raw else DEFAULT_THRESHOLD_MB
    except ValueError:
        return DEFAULT_THRESHOLD_MB


def _step(size_mb: int, threshold_mb: int) -> int:
    """The 100 MB step a size sits on, counted from the threshold: at 200, 201→200, 305→300."""
    return threshold_mb + ((size_mb - threshold_mb) // STEP_MB) * STEP_MB


def _session_pid() -> int | None:
    """This window's `claude` process, by /proc ancestry (`whoami_agent._session_pid`)."""
    try:
        pid = os.getpid()
        for _ in range(12):
            status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8", errors="replace")
            name, ppid = "", 0
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


def _as_int(v: object) -> int | None:
    try:
        return int(str(v).strip()) if v is not None and str(v).strip() else None
    except ValueError:
        return None


def _identity_rows() -> list[dict]:
    path = _env_path("AGENT_IDENTITY_FILE", "~/.claude/state/agent-identity.jsonl")
    rows: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                rows.append(r)
    except (OSError, UnicodeDecodeError):
        pass
    return rows


def _agent_name(session_id: str) -> str:
    """CLAUDE_AGENT, else the latest identity row for this session id, else the registry join."""
    env = (os.environ.get("CLAUDE_AGENT") or "").strip()
    if _NAME_RE.fullmatch(env):
        return env
    rows = _identity_rows()
    best: tuple[int, str] | None = None
    for r in rows:
        if r.get("session_id") == session_id and _NAME_RE.fullmatch(str(r.get("name") or "")):
            at = _as_int(r.get("at")) or 0
            if best is None or at >= best[0]:
                best = (at, str(r["name"]))
    if best:
        return best[1]
    # the registry join: this session's entry → (pid, procStart) → an identity row's (pid, pid_start)
    sessions = _env_path("CLAUDE_SESSIONS_DIR", "~/.claude/sessions")
    try:
        entries = list(sessions.glob("*.json"))
    except OSError:
        return ""
    for entry in entries:
        try:
            e = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(e, dict) or e.get("sessionId") != session_id:
            continue
        pid, start = _as_int(e.get("pid")), _as_int(e.get("procStart"))
        if pid is None or start is None:
            continue
        best = None
        for r in rows:
            if (
                _as_int(r.get("pid")) == pid
                and _as_int(r.get("pid_start")) == start
                and _NAME_RE.fullmatch(str(r.get("name") or ""))
            ):
                at = _as_int(r.get("at")) or 0
                if best is None or at >= best[0]:
                    best = (at, str(r["name"]))
        if best:
            return best[1]
    return ""


def advise(payload: dict, now: float | None = None) -> str | None:
    """The ROTATE line for this prompt, or None. Pure apart from the stamp file."""
    tp = payload.get("transcript_path")
    sid = str(payload.get("session_id") or "")
    if not isinstance(tp, str) or not tp or not sid or "/" in sid:
        return None
    size_mb = Path(tp).stat().st_size // MB
    threshold = _threshold_mb()
    if size_mb < threshold:
        return None
    step = _step(size_mb, threshold)
    stamp_dir = _env_path("ROTATE_STAMP_DIR", "~/.claude/state/rotate-advised")
    stamp = stamp_dir / sid
    try:
        advised = int(stamp.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        advised = 0
    if step <= advised:
        return None
    try:
        stamp_dir.mkdir(parents=True, exist_ok=True)
        stamp.write_text(f"{step}\n", encoding="utf-8")
    except OSError:
        pass  # an unwritable stamp costs a repeat next prompt, never the advice
    agent = _agent_name(sid) or "<agent>"
    pid = _session_pid()
    holder = f"pid {pid}" if pid else "this window's claude pid"
    date = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
    return (
        f"ROTATE: this session's transcript is {size_mb} MB — run `/clear {agent}-{date}` now, then "
        f"`python3 /opt/fabrik/scripts/whoami_agent.py --as {agent} --force` (safe here: the name's "
        f"holder is {holder}, this window's own claude process); the previous session stays "
        f"resumable and is archived tonight (D-736)"
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        line = advise(payload)
        if line:
            print(line)
    except Exception:  # noqa: BLE001 — fail-open by contract: a hook may add a line, never block
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
