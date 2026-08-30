#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mcp_watch.py · scripts/sysadmin/mcp_health.py (cache writer) | none
"""UserPromptSubmit hook — the PER-MESSAGE MCP forcing layer (D-041; Fabrik-synced).

Injects into EVERY prompt, mechanically, what D-032's session-start line could only
say once and D-033's failure-moment rule only says on error:

1. STALENESS — the repo's `.mcp.json` (or the user roster) changed AFTER this
   session's transcript began → the session is running an OUTDATED tool universe
   (incl. the resumed-window class: the IDE resumes conversations, restoring a
   dead roster's tools — measured live on the youtube window, 2026-08-30).
   Banner: reload/new-conversation, every message, until it happens.
2. LIVENESS — the newest cached `mcp_health` verdict (a hook must answer in
   milliseconds, so probing is done by a DETACHED background refresh this hook
   spawns when the cache is older than its TTL). Dead assigned servers banner,
   every message, until fixed.

Fail-open everywhere: any error prints nothing and exits 0 — a broken watcher
must never block or slow a prompt. Fleet-safe: repos without .mcp.json get only
the staleness check against the user roster.
"""

from __future__ import annotations

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


def _session_start(transcript_path: str) -> float | None:
    try:
        st = os.stat(transcript_path)
        # ctime survives appends — a RESUMED conversation keeps its original file,
        # so this correctly reads as the ORIGINAL session start, not the resume.
        return min(st.st_ctime, st.st_mtime)
    except OSError:
        return None


def stale_configs(cwd: str, session_start: float) -> list[str]:
    """Config surfaces that changed AFTER the session began — its tool universe is outdated."""
    out = []
    for label, p in (("repo .mcp.json", Path(cwd) / ".mcp.json"), ("user roster", _ROSTER)):
        try:
            if p.exists() and p.stat().st_mtime > session_start:
                out.append(label)
        except OSError:
            pass
    return out


def _cache_file(cwd: str) -> Path:
    return _CACHE_DIR / (cwd.replace("/", "-").strip("-") + ".json")


def read_cache(cwd: str) -> dict | None:
    try:
        d = json.loads(_cache_file(cwd).read_text())
        return d if isinstance(d, dict) and "report" in d else None
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
    cwd = payload.get("cwd") or os.getcwd()
    lines: list[str] = []

    start = _session_start(payload.get("transcript_path", ""))
    if start is not None:
        stale = stale_configs(cwd, start)
        if stale:
            lines.append(
                f"⚠️ MCP CONFIG CHANGED after this session started ({' + '.join(stale)}) — "
                "this session runs an OUTDATED tool universe (resumed conversations keep the "
                "old roster's tools). Tell the operator a NEW conversation/window reload is "
                "needed; treat missing/dead servers accordingly (fix-first, D-033)."
            )

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
