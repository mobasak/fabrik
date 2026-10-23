#!/usr/bin/env python3
# AFTER-EDIT: tests/test_transcript_size_check.py | docs/workstation/hooks-index.md | docs/workstation/session-history-retention.md | scripts/sysadmin/install_user_hooks.py
"""transcript_size_check — the ROTATE advisories (C.1.3 of the session-history retention plan, D-736; the
context sensor of W-f975fee0, D-1119, D-1123).

A USER-level `UserPromptSubmit` hook in every window of every repo. It reads the hook JSON and runs two
independent, stamped checks — an error or an early return in one never skips the other:

1. SIZE. It stats the session's transcript and, when the file is at or past `ROTATE_ADVISE_MB` (default
   200) AND has crossed a 100 MB step this session has not been told about yet, prints:

    ROTATE: this session's transcript is <N> MB — at your next item boundary message your coordinator
    `rotate <agent>` (it types `/clear <agent>-<YYYY-MM-DD>`, then `python3 /opt/fabrik/scripts/whoami_agent.py
    --as <agent> --force` (safe here: the name's holder is pid <P>, this window's own claude process) and one
    resume prompt; a coordinator tells the operator); the previous session stays resumable and is archived
    tonight (D-736)

2. CONTEXT. It reads the last main-chain usage row in the transcript's last 2 MB — input_tokens +
   cache_creation_input_tokens + cache_read_input_tokens, the figure the status line shows — against the
   session's window, and prints one line per step from 40%: `ROTATE-DUE at your next item boundary: …
   message your coordinator `rotate <agent>`` below 85%, `COMPACT-DUE mid-item: … `compact <agent> <focus>``
   at 85% and over (D-1123's 40% rotate line and 85% compact line). Rotation is at an ITEM BOUNDARY, never
   mid-item (D-1119), and a builder cannot type a slash command: its coordinator types it (D-1034).

Why 200: the VS Code extension host loads every listed session's history into its 4 GB heap
(anthropics/claude-code #89075); it crashed users at 467 MB (#23953) and crash-loops past 2 GiB
(#97229). A busy hub window grows ~25 MB/day, so 200 MB is roughly a week.

STAMPED, never per-prompt: `~/.claude/state/rotate-advised/<session_id>` holds the 100 MB step last
advised, and the line prints only when the size has crossed a NEW step (200, 300, 400 …). The bare
per-prompt shape was measured and rejected as wallpaper before this hook existed
(`install_user_hooks.py`, D-184/D-187); the stamp is this hook's counter-measure — its fire rate is
bounded by steps, not prompts — and the read-compare-write runs under an `flock` on the stamp
directory so two windows of one session cannot both print one step (review 2026-10-11, hook-S2).

The agent name is `CLAUDE_AGENT`, else the identity row for this session id, else the registry
join (the `~/.claude/sessions/<pid>.json` entry carrying this session id, joined on
`pid`+`procStart` to an identity row's `pid`+`pid_start`, both as integers — a `/clear` mints a new
session id but keeps the claude process). An AMBIGUOUS join — two registry entries for one session
id resolving to different names — tags nothing (hook-S4). `<P>` is this window's claude pid, found
by the same `/proc` ancestry walk `whoami_agent._session_pid` uses. The PLAIN re-bind succeeds after a
`/clear` when whoami finds this window's pid (its own pre-`/clear` row is recorded as the `predecessor`,
never a holder — whoami_agent.py, W-34cb1ef9); `--force` also succeeds when that /proc walk fails, which is
why the line keeps it, and the pid in the line is what makes typing it informed.

The CONTEXT reading: in the transcript's last 2 MB (the split first line dropped, a non-JSON line skipped),
the LAST `type: assistant` row whose `isSidechain` is not true, whose `message` and `message.usage` are dicts
and whose model is not `<synthetic>`; a missing key reads 0, a present value counts only when it is a real
non-negative int (a bool or a string skips the row), and a zero sum skips the row. A `compact_boundary` row
AFTER that row means no reading (the next call is the real context). The window: `ROTATE_CONTEXT_WINDOW`
(process env, else the hub env file, a positive int), else the statusline tap's cache
(`STATUSLINE_CACHE_FILE`) `sessions[<sid>].model.id` — `[1m]` → 1,000,000, another id → 200,000 — else
1,000,000 (a reading past 200k takes 1M whatever the cache says). Percent is floored. Steps: 40, 50, 60, 70,
80, then 85, 90, 100. The stamp `<stamp dir>/.ctx/<sid>`
holds the step last advised: a reading below 40 writes 0 silently (a compaction re-arms the sensor), a step
above OR below the stamp prints and stamps (a drop that lands at 40+ is told once, as a rise is), an equal
step prints nothing. The line arrives only with a prompt: a builder that crosses 85% inside one long turn can
reach auto-compaction (~970k) before any COMPACT-DUE line. A 200k session absent from the cache reads the 1M
default and is under-told, and a tail whose last 2 MB holds no usage row (one huge tool result) gives no
reading until the next normal row. COBRA (D-253): the cheapest pass is a line on every prompt (wallpaper) or a threshold
no session reaches; the stamp bounds it to one line per step and per drop, from the panel's 40%.

FAIL-OPEN: any error ⇒ exit 0, no output. This hook can only ADD a line, never block a prompt.

Env: `ROTATE_ADVISE_MB` (process env, else the `ROTATE_ADVISE_MB=` line of
`SESSION_ARCHIVE_ENV_FILE`, default /opt/fabrik/.env, parsed like the archiver's `_env_value`,
else 200), `ROTATE_CONTEXT_WINDOW` (the same two sources, else the statusline cache, else 1,000,000),
`STATUSLINE_CACHE_FILE` (default ~/.claude/.claude-manager/statusline.json), `ROTATE_STAMP_DIR` (default
~/.claude/state/rotate-advised), `AGENT_IDENTITY_FILE`, `CLAUDE_SESSIONS_DIR`.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import time
from pathlib import Path

MB = 1024 * 1024
STEP_MB = 100
DEFAULT_THRESHOLD_MB = 200
TAIL_BYTES = 2 * MB  # the context reading looks at the transcript's last 2 MB only
DEFAULT_WINDOW = 1_000_000
SMALL_WINDOW = 200_000
CTX_ROTATE_PCT = 40  # D-1123: rotate at an item boundary from here
CTX_COMPACT_PCT = 85  # D-1123: a focused /compact mid-item from here
_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent._NAME_RE, byte-identical
_SID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")  # a file stem: no separators, not . or ..
_ENV_LINE = re.compile(r"^(?:export\s+)?(ROTATE_ADVISE_MB|ROTATE_CONTEXT_WINDOW)=(.*)$")


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def _env_value(raw: str) -> str:
    """A dotenv value, exactly as `archive_transcripts._env_value` reads it: a quoted value is the
    text inside its quotes (a trailing comment is ignored); an unquoted one ends at the first
    whitespace-preceded `#`."""
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        end = raw.find(raw[0], 1)
        return raw[1:end] if end > 0 else raw[1:]
    if raw.startswith("#"):
        return ""
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def _hub_setting(name: str) -> str:
    """`name` from the process env, else its LAST line in the hub env file (as dotenv reads), else ""."""
    raw = os.environ.get(name, "").strip()
    if raw:
        return raw
    try:
        lines = (
            _env_path("SESSION_ARCHIVE_ENV_FILE", "/opt/fabrik/.env")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    except (OSError, UnicodeDecodeError):
        lines = []
    for line in lines:
        m = _ENV_LINE.match(line.rstrip("\r").strip())
        if m and m.group(1) == name:
            raw = _env_value(m.group(2))  # the LAST line wins, as dotenv does
    return raw


def _threshold_mb() -> int:
    raw = _hub_setting("ROTATE_ADVISE_MB")
    try:
        return max(1, int(float(raw))) if raw else DEFAULT_THRESHOLD_MB
    except (ValueError, OverflowError):  # "nan" is a ValueError, "inf" an OverflowError at int()
        return DEFAULT_THRESHOLD_MB


def _step(size_mb: int, threshold_mb: int) -> int:
    """The 100 MB step a size sits on, counted from the threshold: at 200, 201→200, 305→300."""
    return threshold_mb + ((size_mb - threshold_mb) // STEP_MB) * STEP_MB


def _session_pid(proc_root: Path = Path("/proc")) -> int | None:
    """This window's `claude` process, by ancestry (`whoami_agent._session_pid`); `proc_root` is
    the test seam — a fake proc tree with `<pid>/status` files exercises the real walk."""
    try:
        pid = os.getpid()
        for _ in range(12):
            status = (proc_root / str(pid) / "status").read_text(encoding="utf-8", errors="replace")
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
    """The identity file is JSONL — one object per line."""
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


def _registry_entries() -> list[dict]:
    """Each `<pid>.json` is ONE JSON document, however it is laid out (pretty-printed included)."""
    sessions = _env_path("CLAUDE_SESSIONS_DIR", "~/.claude/sessions")
    out: list[dict] = []
    try:
        files = sorted(sessions.glob("*.json"))
    except OSError:
        return out
    for f in files:
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def _latest_name(rows: list[dict]) -> str:
    """The name of the row with the greatest `at` (a missing or unparsable `at` ranks below an
    explicit 0; equal `at` → the later row wins, as `whoami_agent.resolve_agent_name` reads)."""
    best: tuple[int, str] | None = None
    for r in rows:
        name = str(r.get("name") or "")
        if not _NAME_RE.fullmatch(name):
            continue
        at = _as_int(r.get("at"))
        at = -1 if at is None else at
        if best is None or at >= best[0]:
            best = (at, name)
    return best[1] if best else ""


def _agent_name(session_id: str) -> str:
    """CLAUDE_AGENT, else the latest identity row for this session id, else the registry join —
    and "" when the join is ambiguous (two registry entries for the id naming different agents)."""
    env = (os.environ.get("CLAUDE_AGENT") or "").strip()
    if _NAME_RE.fullmatch(env):
        return env
    rows = _identity_rows()
    direct = _latest_name([r for r in rows if r.get("session_id") == session_id])
    if direct:
        return direct
    names: set[str] = set()
    for e in _registry_entries():
        if e.get("sessionId") != session_id:
            continue
        pid, start = _as_int(e.get("pid")), _as_int(e.get("procStart"))
        if pid is None or start is None:
            continue
        joined = _latest_name(
            [
                r
                for r in rows
                if _as_int(r.get("pid")) == pid and _as_int(r.get("pid_start")) == start
            ]
        )
        if joined:
            names.add(joined)
    return names.pop() if len(names) == 1 else ""


def _claim_step(stamp_dir: Path, sid: str, step: int) -> bool:
    """Record `step` for `sid` unless an equal or higher step is already stamped — ONE winner per
    step even when two windows of one session prompt at once: the read-compare-write runs under an
    exclusive flock on `<stamp_dir>/.lock`. An unwritable stamp dir claims nothing but still returns
    True — the advice is worth a repeat, never a silence."""
    stamp = stamp_dir / sid
    try:
        stamp_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return True
    try:
        with (stamp_dir / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                try:
                    advised = int(stamp.read_text(encoding="utf-8").strip() or 0)
                except (OSError, ValueError):
                    advised = 0
                if step <= advised:
                    return False
                stamp.write_text(f"{step}\n", encoding="utf-8")
                return True
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    except OSError:
        return True


def _usage_tokens(row: object) -> int | None:
    """The context one main-chain usage row records, or None when the row is not one (see the docstring)."""
    if (
        not isinstance(row, dict)
        or row.get("type") != "assistant"
        or row.get("isSidechain") is True
    ):
        return None
    msg = row.get("message")
    if not isinstance(msg, dict) or msg.get("model") == "<synthetic>":
        return None
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return None
    total = 0
    for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        v = usage.get(key, 0)
        if type(v) is not int or v < 0:  # a bool is an int to isinstance; a string is not a count
            return None
        total += v
    return total or None


def _context_tokens(transcript: Path) -> int | None:
    """The last main-chain usage row's context in the transcript's last 2 MB, or None (no reading)."""
    size = transcript.stat().st_size
    with transcript.open("rb") as fh:
        start = max(0, size - TAIL_BYTES - 1)  # one byte early: is the cut at a line start?
        fh.seek(start)
        data = fh.read()
    if start > 0:
        # drop the first line only when the cut split it; a cut right after a newline keeps the row whole
        data = (
            data[1:]
            if data[:1] == b"\n"
            else data[data.find(b"\n") + 1 :]
            if b"\n" in data
            else b""
        )
    lines = data.split(b"\n")
    reading = None
    for raw in lines:
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except (ValueError, RecursionError):  # a hostile line skips itself, never the check
            continue
        tokens = _usage_tokens(row)
        if tokens is not None:
            reading = tokens
        elif (
            isinstance(row, dict)
            and row.get("subtype") == "compact_boundary"
            and row.get("type") == "system"
        ):
            reading = None  # a compaction after the last reading: the next call is the real context
    return reading


def _positive_int(raw: str) -> int | None:
    try:
        v = int(raw.strip())
    except ValueError:
        return None
    return v if v > 0 else None


def _window(sid: str, tokens: int = 0) -> int:
    """`ROTATE_CONTEXT_WINDOW`, else the statusline cache's model id for this session, else 1,000,000."""
    env = _positive_int(_hub_setting("ROTATE_CONTEXT_WINDOW"))
    if env:
        return env
    try:
        cache = json.loads(
            _env_path(
                "STATUSLINE_CACHE_FILE", "~/.claude/.claude-manager/statusline.json"
            ).read_text(encoding="utf-8")
        )
        model = ((cache.get("sessions") or {}).get(sid) or {}).get("model") or {}
        mid = model.get("id") if isinstance(model, dict) else None
    except (OSError, ValueError, UnicodeDecodeError, AttributeError):
        mid = None
    if isinstance(mid, str) and mid:
        # a reading past 200k proves the 1M window whatever a stale cache row says
        return DEFAULT_WINDOW if mid.endswith("[1m]") or tokens > SMALL_WINDOW else SMALL_WINDOW
    return DEFAULT_WINDOW


def _ctx_step(pct: int) -> int:
    """0 below 40; 40-80 by tens below 85; 85 for 85-89; 90 for 90-99; 100 at or past the window."""
    if pct < CTX_ROTATE_PCT:
        return 0
    if pct >= 100:
        return 100
    if pct >= 90:
        return 90
    if pct >= CTX_COMPACT_PCT:
        return CTX_COMPACT_PCT
    return pct // 10 * 10


def _claim_ctx_step(stamp_dir: Path, sid: str, step: int) -> bool:
    """Under the stamp dir's flock: step 0 writes 0 and claims nothing (a compaction re-arms); any OTHER step
    differing from the stamp is stamped and claimed (a rise or a drop to 40+); an equal step claims nothing.
    An unwritable stamp dir claims a non-zero step, as `_claim_step` does."""
    ctx_dir = (
        stamp_dir / ".ctx"
    )  # `_SID_RE` needs an alphanumeric first character: no sid names this dir
    stamp = ctx_dir / sid
    try:
        ctx_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return step > 0
    try:
        with (stamp_dir / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                try:
                    advised = int(stamp.read_text(encoding="utf-8").strip() or 0)
                except (OSError, ValueError):
                    advised = 0
                if step == advised:
                    return False
                stamp.write_text(f"{step}\n", encoding="utf-8")
                return step > 0
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    except OSError:
        return step > 0


def _is_coordinator(agent: str) -> bool:
    return agent == "coordinator" or agent.endswith("-coordinator")


def _ctx_line(agent: str, pct: int, tokens: int, window: int, size_mb: int, date: str) -> str:
    head = f"ctx {pct}% ({tokens // 1000}k of {window // 1000}k tokens)"
    if pct >= CTX_COMPACT_PCT:
        if not agent:
            return (
                f"COMPACT-DUE mid-item: {head} — type `/compact <one-line focus on the item in hand>` yourself "
                "(this window has no bound agent); at an item boundary, `/clear` instead"
            )
        if _is_coordinator(agent):
            return (
                f"COMPACT-DUE mid-item: {head} — tell the operator once: `/compact <one-line focus on the item in "
                f"hand>`, or at an item boundary `/clear {agent}-{date}`"
            )
        return (
            f"COMPACT-DUE mid-item: {head} — message your coordinator `compact {agent} <one-line focus on the item "
            f"in hand>`; if you are at an item boundary now, `rotate {agent}` instead (a repo's only agent: tell the "
            "operator once instead)"
        )
    boundary = (
        "start no new item; once this one is closed, committed and pushed (no run record running, no seat in "
        "flight, the worktree clean),"
    )
    if not agent:
        return (
            f"ROTATE-DUE at your next item boundary: {head}, {size_mb} MB — {boundary} type `/clear {date}` "
            "yourself (this window has no bound agent)"
        )
    if _is_coordinator(agent):
        return (
            f"ROTATE-DUE at your next item boundary: {head}, {size_mb} MB — {boundary} tell the operator once: "
            f"`/clear {agent}-{date}`"
        )
    return (
        f"ROTATE-DUE at your next item boundary: {head}, {size_mb} MB — {boundary} message your coordinator "
        f"`rotate {agent}` and end the turn `NEXT: none — terminal; awaiting the rotation` (a repo's only agent: "
        "tell the operator once instead)"
    )


def _size_line(sid: str, transcript: Path, size_mb: int, agent: str, date: str) -> str | None:
    """The MB check (D-736): the ROTATE line once per new 100 MB step at or past the threshold, else None."""
    threshold = _threshold_mb()
    if size_mb < threshold:
        return None
    step = _step(size_mb, threshold)
    if not _claim_step(_env_path("ROTATE_STAMP_DIR", "~/.claude/state/rotate-advised"), sid, step):
        return None
    name = agent or "<agent>"
    pid = _session_pid()
    holder = f"pid {pid}" if pid else "this window's claude pid"
    rebind = (
        f"`python3 /opt/fabrik/scripts/whoami_agent.py --as {name} --force` (safe here: the name's holder is "
        f"{holder}, this window's own claude process)"
    )
    if agent and not _is_coordinator(agent):
        return (
            f"ROTATE: this session's transcript is {size_mb} MB — at your next item boundary message your "
            f"coordinator `rotate {agent}` (it types `/clear {agent}-{date}`, then {rebind} and one resume prompt; "
            f"a coordinator tells the operator); the previous session stays resumable and is archived tonight (D-736)"
        )
    return (
        f"ROTATE: this session's transcript is {size_mb} MB — at your next item boundary type "
        f"`/clear {name}-{date}`{' (a coordinator: tell the operator once)' if agent else ''}, then {rebind}; the "
        f"previous session stays resumable and is archived tonight (D-736)"
    )


def _context_line(sid: str, transcript: Path, size_mb: int, agent: str, date: str) -> str | None:
    """The context check (W-f975fee0): ROTATE-DUE / COMPACT-DUE once per step and per drop, else None."""
    tokens = _context_tokens(transcript)
    if tokens is None:
        return None
    window = _window(sid, tokens)
    pct = tokens * 100 // window
    step = _ctx_step(pct)
    if not _claim_ctx_step(
        _env_path("ROTATE_STAMP_DIR", "~/.claude/state/rotate-advised"), sid, step
    ):
        return None
    return _ctx_line(agent, pct, tokens, window, size_mb, date)


def advise(payload: dict, now: float | None = None) -> list[str]:
    """The lines for this prompt — the MB line first, then the context line — each from its own fail-open check."""
    tp = payload.get("transcript_path")
    sid = str(payload.get("session_id") or "")
    # `_SID_RE` needs an alphanumeric first character, so `.`, `..` and every `/`-bearing id fail
    # here before any stamp path is built (hook-S5; the explicit `.`/`..` tuple was unreachable)
    if not isinstance(tp, str) or not tp or not _SID_RE.fullmatch(sid):
        return []
    transcript = Path(tp)
    size_mb = transcript.stat().st_size // MB
    agent = _agent_name(sid)
    date = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
    lines: list[str] = []
    for check in (_size_line, _context_line):
        try:
            line = check(sid, transcript, size_mb, agent, date)
        except Exception:  # noqa: BLE001 — fail-open per check: one check's fault never silences the other
            line = None
        if line:
            lines.append(line)
    return lines


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        for line in advise(payload):
            print(line)
    except Exception:  # noqa: BLE001 — fail-open by contract: a hook may add a line, never block
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
