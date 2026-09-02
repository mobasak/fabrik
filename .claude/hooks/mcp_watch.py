#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mcp_watch.py · scripts/sysadmin/mcp_health.py (cache writer) | none
"""UserPromptSubmit hook — the PER-MESSAGE MCP forcing layer (D-041; Fabrik-synced).

Injects into EVERY prompt, mechanically, what D-032's session-start line could only
say once and D-033's failure-moment rule only says on error:

1. STALENESS — the repo's `.mcp.json`, the account pointer, or the roster's MCP
   SLICE (hashed — never the roster file's mtime, which the harness rewrites every
   few seconds, so mtime fired on every prompt forever) changed AFTER this
   session's HARNESS PROCESS started (the moment the tool universe loads; D-070)
   → the session is running an OUTDATED tool universe (incl. the resumed-window
   class: the IDE resumes conversations, restoring a dead roster's tools —
   measured live on the youtube window, 2026-08-30). Banner leads with CHECK
   YOUR ASSIGNED MCPs + D-033 fix-first (the duty the agent can act on); the
   window reload is the remedy for the one class it restores, said to the
   operator — not the headline. Clock: /proc ancestry → the claude process, with
   the transcript-head first timestamp as fallback; NEVER stat times (ctime moves
   on append → the verdict raced the flush and went silent on stale sessions).
2. LIVENESS — the newest cached `mcp_health` verdict (a hook must answer in
   milliseconds, so probing is done by a DETACHED background refresh this hook
   spawns when the cache is older than its TTL). Dead assigned servers banner,
   every message, until fixed.

Fail-open everywhere: any error prints nothing and exits 0 — a broken watcher
must never block or slow a prompt. Fleet-safe: repos without .mcp.json get only
the staleness check against the user roster.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_TTL_S = 15 * 60
_CACHE_DIR = Path(f"/tmp/claude-{os.getuid()}/mcp-health-cache")
_HEALTH = "/opt/fabrik/scripts/sysadmin/mcp_health.py"
_ROSTER = Path.home() / ".claude-fleet/active/.claude.json"


def _btime() -> float | None:
    """Boot epoch from /proc/stat — a STABLE anchor for a process's absolute start.
    Preferred over `time.time() - uptime`, which re-derives boot time from the CURRENT
    wall clock and so drifts by any NTP step / suspend on this Modern-Standby host."""
    try:
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
    except Exception:
        pass
    return None


def _start_from_stat(raw: str) -> float | None:
    """Absolute process start from an ALREADY-READ /proc/<pid>/stat (no re-read → no
    TOCTOU / pid-reuse race). After `rsplit(') ', 1)` the tail begins at field 3, so
    index 19 = field 22 = starttime ticks; comm's own parens/spaces are irrelevant
    because no post-comm field contains ')'."""
    try:
        ticks = int(raw.rsplit(") ", 1)[1].split()[19])
        btime = _btime()
        if btime is None:
            return None
        return btime + ticks / os.sysconf("SC_CLK_TCK")
    except Exception:
        return None


def _proc_start_epoch(pid: int) -> float | None:
    try:
        return _start_from_stat(Path(f"/proc/{pid}/stat").read_text())
    except Exception:
        return None


def _cmdline_has_claude(pid: int) -> bool:
    try:
        return b"claude" in Path(f"/proc/{pid}/cmdline").read_bytes().lower()
    except Exception:
        return False


def _claude_ancestor_start() -> float | None:
    """Start time of the harness process (walk ≤10 parents to the claude process). A
    bare `node` comm is accepted ONLY when its cmdline names claude — an IDE/npx/pm2
    `node` between the hook and the true harness would otherwise return ITS (later)
    start and suppress a real staleness (silent-stale, the direction this fix bans)."""
    try:
        pid = os.getppid()
        for _ in range(10):
            raw = Path(f"/proc/{pid}/stat").read_text()
            comm = raw.split("(", 1)[1].rsplit(")", 1)[0]
            if comm == "claude" or (comm == "node" and _cmdline_has_claude(pid)):
                return _start_from_stat(raw)  # reuse the raw we just read (no 2nd read)
            ppid = int(raw.rsplit(") ", 1)[1].split()[1])
            if ppid <= 1:
                return None
            pid = ppid
    except Exception:
        pass
    return None


def _first_event_ts(transcript_path: str) -> float | None:
    """First parseable `timestamp` in the transcript head (bounded scan, fail-open).
    A non-ISO / numeric-epoch value is SKIPPED, never raised — an escaping ValueError
    would abort main() before the liveness banner (both banners silently suppressed)."""
    from datetime import UTC, datetime

    try:
        with open(transcript_path, encoding="utf-8", errors="ignore") as fh:
            for _ in range(20):
                # ⚠️ NEVER readline(N): a size-bounded readline that TRUNCATES does not advance
                # to the next line — the next iteration returns the REMAINDER of the same line,
                # so an over-long line 1 silently yields line 2's timestamp (start moves LATER
                # ⇒ suppression, measured: 80KB line 1 returned line 2's ts). Read whole lines
                # and SKIP over-long ones by length instead.
                line = fh.readline()
                if not line:
                    return None
                # A large line is PARSED, not skipped: an 80KB attachment line still carries
                # the turn's real timestamp, and skipping it answers with a LATER line — the
                # same wrong (suppressing) answer the truncating readline(N) gave. Only a
                # pathological multi-MB line is dropped, to bound json.loads cost.
                if len(line) > 4 * 1024 * 1024:
                    continue
                try:
                    ts = json.loads(line).get("timestamp")
                except Exception:
                    continue
                if ts:
                    try:
                        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    except ValueError:
                        continue  # numeric epoch / junk — try the next line, never raise
                    if dt.tzinfo is None:  # naive ⇒ UTC, never the box's local TZ
                        dt = dt.replace(tzinfo=UTC)
                    return dt.timestamp()
    except Exception:
        return None
    return None


def _session_start(transcript_path: str) -> float | None:
    # The tool universe is loaded at HARNESS PROCESS start, so that is "session start"
    # for staleness — and a window reload truthfully clears the banner. Two rejected
    # sources, both measured 2026-09-02 (wef 01M1GE3PWBPKZWETCANJXWGGRC + hub probe):
    # stat times — ctime is inode-CHANGE time on Linux and moves on every append, so
    # min(ctime, mtime) is "last write" and the verdict raced the transcript flush
    # (silent on genuinely stale sessions); first-line timestamp alone — a resumed
    # conversation keeps its file, so a months-old first line (live: 2026-05-13 on a
    # 2026-09-02 session) fires the banner forever and no reload can clear it. The
    # transcript head is the FALLBACK when no harness ancestor is visible: over-warning
    # beats the silent-stale direction there.
    start = _claude_ancestor_start()
    if start is not None:
        return start
    return _first_event_ts(transcript_path)


def tool_universe_fingerprint(cwd: str) -> str | None:
    """Hash of ONLY the MCP slice of the user roster — the servers this repo would load.

    ⚠️ The roster file's MTIME is worthless as a staleness signal: `~/.claude-fleet/active/
    .claude.json` is Claude Code's global STATE file (announcementImpressions, statsig gates,
    changelog fetch times, 121 project entries…) and the harness rewrites it every few seconds
    — measured advancing 3× in one minute of unrelated work. Comparing that mtime to any
    session start is unconditionally true, so the banner fired on EVERY prompt in EVERY repo,
    forever: wallpaper, printed directly above the liveness banner it discredits (the decay
    `liveness_banner` warns about). Only the mcpServers slice means "the tool universe changed".
    """
    try:
        d = json.loads(_ROSTER.read_text())
        if not isinstance(d, dict):
            return None
        slice_ = {
            "global": d.get("mcpServers"),
            "project": (d.get("projects") or {}).get(cwd, {}).get("mcpServers"),
        }
        return hashlib.sha256(
            json.dumps(slice_, sort_keys=True, default=str).encode()
        ).hexdigest()
    except Exception:
        return None


def _fingerprint_cache(cwd: str) -> Path:
    return _CACHE_DIR / ("fp-" + cwd.replace("/", "-").strip("-") + ".json")


def roster_tools_changed(cwd: str, session_start: float) -> bool:
    """True when the roster's MCP slice differs from the one first seen this session.

    Session-scoped by the harness start epoch: a new session (new process ⇒ new epoch)
    re-baselines, which is exactly what a window reload does — so the banner CLEARS on the
    remedy it names, instead of asserting a change nobody can act on.
    """
    fp = tool_universe_fingerprint(cwd)
    if fp is None:
        return False
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        f = _fingerprint_cache(cwd)
        prev = json.loads(f.read_text()) if f.exists() else None
        if not isinstance(prev, dict) or prev.get("session") != session_start:
            f.write_text(json.dumps({"session": session_start, "fp": fp}))  # baseline this session
            return False
        return prev.get("fp") != fp
    except Exception:
        return False


def stale_configs(cwd: str, session_start: float) -> list[str]:
    """Config surfaces that changed AFTER the session began — its tool universe is outdated."""
    out = []
    # The repo file is hand-edited, so its mtime IS the signal. The account pointer is the
    # rotation surface: `active -> <account>` re-points without touching the file or its
    # target dir, and lstat() only spares the FINAL component — so the SYMLINK itself is
    # watched, not the roster path (lstat-ing that path is a measured no-op: stat == lstat).
    for label, p in (
        ("repo .mcp.json", Path(cwd) / ".mcp.json"),
        ("account pointer", _ROSTER.parent),
    ):
        try:
            if not p.exists():
                continue
            # lstat the SYMLINK itself: a rotation re-points `active` without touching the
            # target dir or the roster file — and lstat-ing the roster PATH is a measured
            # no-op, since only the FINAL component escapes dereferencing.
            m = p.lstat().st_mtime if p.is_symlink() else p.stat().st_mtime
            if m > session_start:
                out.append(label)
        except OSError:
            pass
    # the roster's own mtime is meaningless (see tool_universe_fingerprint) — its MCP slice is not
    if roster_tools_changed(cwd, session_start):
        out.append("user roster MCP servers")
    return out


def _cache_file(cwd: str) -> Path:
    return _CACHE_DIR / (cwd.replace("/", "-").strip("-") + ".json")


def read_cache(cwd: str) -> dict | None:
    try:
        d = json.loads(_cache_file(cwd).read_text())
        # TYPE-check, not key-presence: a truncated/racing write from the detached refresh
        # gave `report` a list and `ts` a string, which raised out of main() and suppressed
        # BOTH banners (the harm this hook exists to prevent).
        if (isinstance(d, dict) and isinstance(d.get("report"), dict)
                and isinstance(d.get("ts"), (int, float))):
            return d
        return None
    except Exception:
        return None


def _refresh_detached(cwd: str) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [sys.executable, _HEALTH, "--repo", cwd, "--cache-out", str(_cache_file(cwd))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def stale_banner(stale: list[str], determined: bool = True) -> str:
    """Leads with the duty the AGENT can act on (D-033 fix-first); the window reload is
    the remedy for one diagnosed class, addressed to the operator — not the headline
    (operator, 2026-09-02: "it should say check your assigned MCPs, and if any is not
    functioning fix, not MCP roster changed after this session started").

    `determined=False` is the over-warn branch: session start was UNKNOWN, so the banner
    must not assert a comparison it never made — an operator who checks the file and finds
    it untouched learns the banner lies, which is how the mandate decays into wallpaper."""
    when = (
        "changed after this session began"
        if determined
        else "may have changed — this session's start could not be determined, assuming outdated"
    )
    return (
        f"⚠️ MCP: this session's tool universe may be OUTDATED ({' + '.join(stale)} "
        f"{when}). CHECK YOUR ASSIGNED MCPs FIRST "
        "and FIX any that are not functioning (D-033 fix-first; known classes: "
        "docs/workstation/mcp-roster.md; probe: python3 "
        "/opt/fabrik/scripts/sysadmin/mcp_health.py). A dead server that only a reload "
        "would restore additionally needs a NEW conversation/window — say so to the operator."
    )


def liveness_banner(report: dict, age_m: int) -> str | None:
    """The dead-server banner, or None when nothing is provably dead.

    Pure so the counting is testable: it is a RATIO shown to every session, and both
    halves must mean the same thing. A SKIPPED entry (docker-run — deliberately not
    probed) is excluded from the numerator, so it must also be excluded from the
    denominator; counting it said "1/15 NOT live" when only 14 were ever measured.
    Unprobed is not dead, and a ratio whose halves disagree teaches the reader to
    distrust the banner — which is how a fix-first mandate decays into wallpaper.
    """
    dead = {n: v for n, v in report.items()
            if v != "CONNECTED" and not str(v).startswith("SKIPPED")}
    if not dead:
        return None
    probed = sum(1 for v in report.values() if not str(v).startswith("SKIPPED"))
    return (
        f"⚠️ MCP HEALTH ({age_m}m ago): {len(dead)}/{probed} probed "
        f"server(s) NOT live — {', '.join(sorted(dead))}. FIX FIRST before the task "
        "(known classes: docs/workstation/mcp-roster.md; re-probe: "
        "python3 /opt/fabrik/scripts/sysadmin/mcp_health.py)."
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if not isinstance(payload, dict):  # a list/str payload raised out of .get() → both
        payload = {}                   # banners suppressed; the harm this hook prevents
    cwd = str(payload.get("cwd") or os.getcwd())
    lines: list[str] = []

    # start undetermined (no /proc ancestor AND no parseable transcript head) ⇒ OVER-WARN
    # per D-070's policy: epoch-0 makes any existing config read as changed-after. Silence
    # here would be the silent-stale direction the whole fix bans — but the banner SAYS the
    # start was undetermined rather than asserting a comparison it never made.
    start = _session_start(payload.get("transcript_path") or "")
    determined = start is not None
    if start is None:
        start = 0.0
    stale = stale_configs(cwd, start)
    if stale:
        lines.append(stale_banner(stale, determined=determined))

    if (Path(cwd) / ".mcp.json").is_file() and Path(_HEALTH).is_file():
        cache = read_cache(cwd)
        now = time.time()
        if cache and now - cache.get("ts", 0) <= _TTL_S:
            banner = liveness_banner(cache["report"], int((now - cache["ts"]) / 60))
            if banner:
                lines.append(banner)
        else:
            _refresh_detached(cwd)

    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
