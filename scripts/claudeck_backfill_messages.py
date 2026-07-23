#!/usr/bin/env python3
"""Backfill claudeck's messages table from native Claude Code session jsonl.

claudeck renders transcripts ONLY from its own messages table, so adopted
sessions show an empty pane. This rebuilds a session's transcript as readable
prose: user + assistant text blocks in order (tool activity, thinking blocks,
system wrappers and neutralized legacy markers omitted). Full rebuild per
session (delete + insert) so ORDER BY id stays chronologically correct.

Usage: claudeck_backfill_messages.py <session.jsonl> [...]
"""
import json, sqlite3, sys
from datetime import datetime
from pathlib import Path

DB = Path.home() / ".claudeck/data.db"

def text_of(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"
                 and not str(b.get("text", "")).startswith("[legacy tool")]
        return "\n".join(p for p in parts if p).strip()
    return ""

def backfill(f: Path, db) -> None:
    sid = f.stem
    rows = []
    for line in open(f, errors="replace"):
        try: o = json.loads(line)
        except Exception: continue
        t, m = o.get("type"), o.get("message") or {}
        if t not in ("user", "assistant"): continue
        txt = text_of(m.get("content"))
        if not txt or txt.startswith(("<", "Caveat:")): continue
        ts = o.get("timestamp")
        try: sec = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except Exception: sec = 0
        rows.append((sid, t, json.dumps({"text": txt}), sec))
    db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    db.executemany("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", rows)
    db.commit()
    print(f"{sid[:12]}: transcript rebuilt, {len(rows)} messages")

if __name__ == "__main__":
    db = sqlite3.connect(DB)
    for a in sys.argv[1:]:
        backfill(Path(a), db)
