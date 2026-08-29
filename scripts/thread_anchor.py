#!/usr/bin/env python3
# AFTER-EDIT: tests/test_thread_anchor.py, docs/reference/thread-anchors.md, .claude/hooks/final_gate_stop.py, .claude/settings.json | none
"""Thread anchors — the NEXT: line, made durable, multi-slot, and read-back.

THE DEFECT (measured live, 2026-08-29, one session): 905 ``NEXT:`` lines emitted, ZERO ever read
back. A thread carried in 85 consecutive NEXT: lines ("corpus audit — command N of 31") vanished
the moment an operator question arrived, because NEXT: is one slot: a tangent does not compete
with the standing task, it OVERWRITES it, silently. And the slot lives in the transcript, so a
compact erases it entirely.

THE FIX is mechanism, not discipline — discipline is what failed 85-lines-deep:

  harvest   Stop hook feeds it the final message (which agents already emit — no new obligation).
            The NEXT: line is extracted; lines matching LONG-RUNNING shapes ("N of M", a
            plan/epic/cert path) are promoted to ANCHORS keyed on their stable part, so
            "command 15 of 31" UPDATES the "command 14 of 31" anchor rather than stacking.
  line      SessionStart + UserPromptSubmit inject the open anchors into every prompt — the
            exact mail_notify.py pattern that makes mail structurally unmissable. Capped at 4
            anchors, silent when empty: an always-on block is wallpaper, and wallpaper is how
            CI died.
  done      Closes an anchor by substring. Staleness is visible in the output, so a dead anchor
            gets closed instead of scrolling forever.

State: one JSON per session under ``~/.claude/state/threads/`` (override: THREAD_ANCHOR_DIR).
Session-scoped because three concurrent sessions share this repo. EVERY path fails open — this
runs inside the Stop hook, where an exception would block end-of-turn fleet-wide.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

_NEXT_RE = re.compile(r"^NEXT:\s*(.+?)\s*$", re.M)
# Long-running shapes worth persisting past the turn that wrote them. Deliberately FEW: every
# shape added here is a line the injector may print on every prompt of every session.
_ANCHOR_RES = (
    re.compile(r"\b\d+\s+of\s+\d+\b", re.I),                      # "command 14 of 31", "TC3 of 12"
    re.compile(r"docs/development/(?:plans|epics|certifications)/[\w./-]+"),
    re.compile(r"\bphase\s+[A-Z]\b"),                             # mid-plan position
)
_MAX_SHOWN = 4
_MAX_ANCHORS = 12  # hard cap on stored anchors — beyond this the oldest are dropped, loudly


def _state_dir() -> Path:
    d = os.environ.get("THREAD_ANCHOR_DIR")
    return Path(d) if d else Path.home() / ".claude" / "state" / "threads"


def _state_path(session: str) -> Path:
    safe = re.sub(r"[^\w-]", "_", session or "nosession")[:64]
    return _state_dir() / f"{safe}.json"


def _load(session: str) -> dict:
    try:
        return json.loads(_state_path(session).read_text(encoding="utf-8"))
    except Exception:
        return {"anchors": [], "last_next": None}


def _save(session: str, state: dict) -> None:
    try:
        p = _state_path(session)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        tmp.replace(p)  # atomic on POSIX — a killed hook never leaves a torn file
    except Exception:
        pass  # fail-open: losing one harvest beats blocking a turn


def _anchor_key(text: str) -> str:
    """Stable identity across progress updates AND rewordings. Digits mask out ("14 of 31" ->
    "15 of 31" is the same thread advancing); the key then takes only the PREFIX, because the
    stable subject lives at the front and commentary accretes at the back — found live one hour
    after shipping, when appending "(now also held by the register)" minted a duplicate anchor
    that the injected block then showed twice."""
    return re.sub(r"\d+", "*", text.lower())[:72]


def _is_anchor(text: str) -> bool:
    return any(rx.search(text) for rx in _ANCHOR_RES)


def _age(ts: float) -> str:
    m = max(0, int((time.time() - ts) / 60))
    return f"{m}m" if m < 120 else f"{m // 60}h"


def cmd_harvest(session: str, text: str) -> None:
    matches = _NEXT_RE.findall(text)
    if not matches:
        return
    nxt = matches[-1][:300]  # the LAST NEXT: in the message is the operative one
    state = _load(session)
    state["last_next"] = {"ts": time.time(), "text": nxt}
    if _is_anchor(nxt):
        key = _anchor_key(nxt)
        for a in state["anchors"]:
            if a["key"] == key:
                a.update(text=nxt, ts=time.time())  # progress update, not a duplicate
                break
        else:
            state["anchors"].append({"key": key, "text": nxt, "ts": time.time()})
            if len(state["anchors"]) > _MAX_ANCHORS:
                state["anchors"] = state["anchors"][-_MAX_ANCHORS:]
    _save(session, state)


def cmd_line(session: str) -> str:
    state = _load(session)
    anchors = sorted(state["anchors"], key=lambda a: -a["ts"])[:_MAX_SHOWN]
    if not anchors and not state.get("last_next"):
        return ""
    out = []
    if anchors:
        out.append("## 🧵 OPEN THREADS (yours — close with `python3 scripts/thread_anchor.py done --match <substr>`)")
        out += [f"- {a['text']}  ({_age(a['ts'])} ago)" for a in anchors]
    last = state.get("last_next")
    # The latest successor, shown only when it is NOT already an anchor above.
    if last and (not anchors or _anchor_key(last["text"]) != anchors[0]["key"]):
        out.append(f"- NEXT (latest): {last['text']}")
    return "\n".join(out)


def cmd_done(session: str, match: str) -> None:
    state = _load(session)
    state["anchors"] = [a for a in state["anchors"] if match.lower() not in a["text"].lower()]
    # The latest-NEXT echo dies with its anchor — found by the suite's own red: `done` removed
    # the anchor and the stale last_next line resurrected the same text one line lower.
    last = state.get("last_next")
    if last and match.lower() in last["text"].lower():
        state["last_next"] = None
    _save(session, state)


def main(argv: list[str] | None = None) -> int:
    try:
        ap = argparse.ArgumentParser(description=__doc__)
        ap.add_argument("cmd", choices=("harvest", "line", "done"))
        ap.add_argument("--session", default=os.environ.get("CLAUDE_SESSION_ID", ""))
        ap.add_argument("--match", default="")
        ap.add_argument("--hook", action="store_true",
                        help="read the hook's stdin JSON for session_id (and, for harvest, use "
                             "its transcript_path if no text is piped)")
        args, _ = ap.parse_known_args(argv)

        # Read stdin ONLY where it is part of the contract (harvest text, --hook JSON).
        # Found live: `done --match …` from an agent's shell — stdin open, not a tty, nothing
        # piped — blocked forever here, and the 2-minute tool timeout was the only way out.
        needs_stdin = args.cmd == "harvest" or args.hook
        stdin_text = "" if (not needs_stdin or sys.stdin.isatty()) else sys.stdin.read()
        session = args.session
        if args.hook and stdin_text:
            try:
                session = str(json.loads(stdin_text).get("session_id") or session)
                stdin_text = ""
            except Exception:
                pass
        if not session:
            session = "nosession"

        if args.cmd == "harvest":
            cmd_harvest(session, stdin_text)
        elif args.cmd == "line":
            out = cmd_line(session)
            if out:
                print(out)
        elif args.cmd == "done":
            if args.match:
                cmd_done(session, args.match)
        return 0
    except Exception:
        return 0  # fail-open, always: this sits inside the Stop hook's path


if __name__ == "__main__":
    sys.exit(main())
