#!/usr/bin/env python3
"""Import native Claude Code sessions (~/.claude/projects/*.jsonl) into claudeck's DB.

claudeck (v1.4.x) lists/resumes only sessions in its own SQLite (~/.claudeck/data.db);
it never reads Claude Code's native store. This importer adopts every native session
for /opt projects using claudeck's own minimal-insert shape (db/sqlite.js createSession:
INSERT OR IGNORE INTO sessions (id, claude_session_id, ...)). Idempotent: id = the
Claude session uuid, so re-runs no-op existing rows and only bump last_used_at.
Run manually or via wsl_startup_hook (daily). Backup written on first run of the day.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path

DB = Path.home() / ".claudeck/data.db"
STORE = Path.home() / ".claude/projects"
# Automation projects whose sessions are pipeline runs, not operator chats —
# they flood the claudeck list. Override per-run: --include-all
EXCLUDE = {"kilo-benchmarks", "iterative_image_editor"}
# Batch/pipeline sessions identified by their fixed harness prompt — never list in claudeck
EXCLUDE_TITLE_PREFIXES = ("Process a YouTube transcript",)
# Curated projects: ONLY these session ids are listed in claudeck for the given
# project (operator decision; batch/pipeline noise stays out). Edit to taste.
CURATED = {
    "/opt/fabrik": {
        "1970a0ff-baa3-401b-ba52-fb0c5de43261",  # read and comprend...
        "4e90716e-696b-4ddf-90ab-70e30f51f294",  # fix four bugs
        "dd3c06d1-41b1-4610-bfd5-deb4f29fcc2e",  # update agents.md
    },
    "/opt/fabrik-lib": {
        "610c3b1c-a5ef-4ba0-a662-f3f87399a58b",
        "413b420e-3b36-4d13-b4f6-ee3f71f98de2",
        "67ccc993-3fda-4dcd-a392-4531f01c6e5d",
    },
    "/opt/trade-intelligence": {
        "1991fa9b-fc01-4eba-a3b0-c5d04349c135",
        "37887efc-b5b9-4c00-b0f9-1590ad4b58c7",
    },
    "/opt/brand-identiy-creator": {
        "a79679a4-f4f1-40ac-bef6-08f216442cf2",
    },
    "/opt/youtube": {
        "e4578f91-6989-44f5-ac25-ec1131457c24",  # build responsive rag dashboard
        "50328fe3-24e5-489b-b2ff-74b80bc12a81",  # debug stale-charged
    },
}


def _epoch_ms(iso: str) -> int:
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except Exception:
        return int(time.time())


def scan(p: Path):
    """Return (cwd, title, first_ts, last_ts) from one session jsonl, cheaply."""
    cwd = title = summary = None
    first = last = None
    user_txt = None
    with open(p, errors="replace") as fh:
        for i, line in enumerate(fh):
            if i > 4000:
                break
            try:
                o = json.loads(line)
            except Exception:
                continue
            cwd = cwd or o.get("cwd")
            ts = o.get("timestamp")
            if ts:
                first = first or ts
                last = ts
            if o.get("type") == "summary" and not summary:
                summary = (o.get("summary") or "").strip()
            if not user_txt and o.get("type") == "user":
                c = (o.get("message") or {}).get("content")
                t = (
                    c
                    if isinstance(c, str)
                    else " ".join(b.get("text", "") for b in (c or []) if isinstance(b, dict))
                )
                t = (t or "").strip()
                if t and not t.startswith(("<", "[", "Caveat:")):
                    user_txt = t
    # last timestamp from the file TAIL — the head-capped scan under-reads long
    # sessions and sinks exactly the important chats to the bottom of the list
    try:
        with open(p, "rb") as fb:
            fb.seek(max(0, p.stat().st_size - 131072))
            tail_lines = fb.read().decode(errors="replace").splitlines()
        for line in reversed(tail_lines):
            try: ts = json.loads(line).get("timestamp")
            except Exception: continue
            if ts: last = ts; break
    except OSError:
        pass
    title = (summary or user_txt or p.stem)[:120]
    return cwd, title, first, last


def main() -> int:
    if not DB.exists():
        print("claudeck DB not found — run claudeck once first")
        return 1
    bak = DB.with_suffix(f".bak-{date.today():%Y%m%d}")
    if not bak.exists():
        shutil.copy2(DB, bak)
    db = sqlite3.connect(DB)
    ins = upd = 0
    for f in STORE.glob("*/*.jsonl"):
        sid = f.stem
        if len(sid) != 36:
            continue  # session files are uuid-named
        cwd, title, first, last = scan(f)
        if not cwd or not cwd.startswith("/opt/"):
            continue
        if Path(cwd).name in EXCLUDE and "--include-all" not in sys.argv:
            continue
        c_ms, l_ms = _epoch_ms(first or ""), _epoch_ms(last or "")
        # Group by the top-level /opt entry: fabrik-lib modules, worktrees and any
        # subdir cwd belong to their parent project, never listed as projects.
        top = Path(*Path(cwd).parts[:3])  # /opt/<name>
        cwd = str(top)
        name = top.name
        if title.startswith(EXCLUDE_TITLE_PREFIXES): continue
        if cwd in CURATED and sid not in CURATED[cwd]: continue
        cur = db.execute(
            "INSERT OR IGNORE INTO sessions (id, claude_session_id, project_name, project_path,"
            " created_at, last_used_at, title) VALUES (?,?,?,?,?,?,?)",
            (sid, sid, name, cwd, c_ms, l_ms, title),
        )
        if cur.rowcount:
            ins += 1
        else:
            cur = db.execute(
                "UPDATE sessions SET last_used_at=? WHERE id=? AND last_used_at<?",
                (l_ms, sid, l_ms),
            )
            upd += cur.rowcount
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print(f"claudeck import: +{ins} new, ~{upd} refreshed, {n} total sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
