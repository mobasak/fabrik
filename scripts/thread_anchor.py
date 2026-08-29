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
    re.compile(r"\b\d+\s+of\s+\d+\b", re.I),  # "command 14 of 31", "TC3 of 12"
    re.compile(r"docs/development/(?:plans|epics|certifications)/[\w./-]+"),
    re.compile(r"\bphase\s+[A-Z]\b"),  # mid-plan position
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
    """The thread's IDENTITY — learned three times, so the reasoning stays with the code.

    Round 1: full-text keys → appended commentary minted duplicates. Round 2: a 72-char prefix
    → texts diverging at char ~54 duplicated again (a constant was never the fix). Round 3: raw
    containment → "… — /fabrik-user-test (in progress)" vs "… — /fabrik-flows" share a subject
    but neither contains the other.

    What is ACTUALLY stable is the leading SUBJECT: NEXT: lines here read
    "<subject> — <position> — <per-step tail>", and only the tail churns. So:
      1. ≥2 em-dash separators → the first two segments ARE the identity
         ("the corpus audit — command * of *"), and the per-step tail is dropped.
      2. else a plan/epic/cert PATH is the identity (each slug its own thread — a shared-prefix
         heuristic here would merge two different plans, losing one: the founding defect again).
      3. else digits masked, trailing parenthetical stripped, first 72 chars.
    """
    s = re.sub(r"\d+", "*", text.lower()).strip()
    segs = re.split(r"\s+—\s+", s)
    if len(segs) >= 3:
        return " — ".join(segs[:2])[:96]
    m = re.search(r"docs/development/(?:plans|epics|certifications)/[\w./*-]+", s)
    if m:
        return m.group(0)[:96]
    return re.sub(r"\s*\(.*$", "", s)[:72]


def _same_thread(a: str, b: str) -> bool:
    """Equality on canonical keys, plus containment (≥24 chars) as the belt for the
    free-text fallback, where one wording may simply extend another."""
    if a == b:
        return True
    a, b = (a, b) if len(a) <= len(b) else (b, a)
    return len(a) >= 24 and b.startswith(a)


def _is_anchor(text: str) -> bool:
    return any(rx.search(text) for rx in _ANCHOR_RES)


def _age(ts: float) -> str:
    m = max(0, int((time.time() - ts) / 60))
    return f"{m}m" if m < 120 else f"{m // 60}h"


_TAIL_BYTES = 2 * 1024 * 1024


def _final_message_text(transcript_path: str) -> str:
    """Text of the last assistant entry that HAS text blocks, from the transcript tail.

    Skips textless (tool_use/thinking-only) assistant entries: the harness can fire hooks
    BEFORE the final text entry is flushed, and at that moment the tail ends in the closing
    tool_use entry (measured live 2026-08-29 via anchor_harvest telemetry: chars=0 at the
    turn-final Stop while the 4KB message was on disk minutes later). The last flushed text
    is the best available message; the prompt-side pass catches what this one misses.
    """
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _TAIL_BYTES))
            lines = f.read().decode("utf-8", "replace").splitlines()
        for line in reversed(lines):
            if '"type"' not in line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("type") != "assistant":
                continue
            content = (entry.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            text = "\n".join(
                str(b.get("text") or "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ).strip()
            if text:
                return text
        return ""
    except Exception:
        return ""


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
            if _same_thread(a["key"], key):
                # Progress update, not a duplicate — and the key RE-ROOTS to the newest text,
                # so a thread whose wording tightens over time keeps one identity.
                a.update(text=nxt, key=key, ts=time.time())
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
        out.append(
            "## 🧵 OPEN THREADS (yours — close with `python3 scripts/thread_anchor.py done --match <substr>`)"
        )
        out += [f"- {a['text']}  ({_age(a['ts'])} ago)" for a in anchors]
    last = state.get("last_next")
    # The latest successor, shown only when it is NOT already an anchor above.
    if last and (not anchors or not _same_thread(_anchor_key(last["text"]), anchors[0]["key"])):
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
        ap.add_argument(
            "--hook",
            action="store_true",
            help="read the hook's stdin JSON for session_id (and, for harvest, use "
            "its transcript_path if no text is piped)",
        )
        args, _ = ap.parse_known_args(argv)

        # Read stdin ONLY where it is part of the contract (harvest text, --hook JSON).
        # Found live: `done --match …` from an agent's shell — stdin open, not a tty, nothing
        # piped — blocked forever here, and the 2-minute tool timeout was the only way out.
        needs_stdin = args.cmd == "harvest" or args.hook
        stdin_text = "" if (not needs_stdin or sys.stdin.isatty()) else sys.stdin.read()
        session = args.session
        transcript_path = ""
        if args.hook and stdin_text:
            try:
                payload = json.loads(stdin_text)
                session = str(payload.get("session_id") or session)
                transcript_path = str(payload.get("transcript_path") or "")
                stdin_text = ""
            except Exception:
                pass
        if not session:
            session = "nosession"

        if args.cmd == "harvest":
            # --hook with nothing piped: extract from the payload's transcript (the help
            # text promised this from day one; the code now delivers it).
            if not stdin_text and transcript_path:
                stdin_text = _final_message_text(transcript_path)
            cmd_harvest(session, stdin_text)
        elif args.cmd == "line":
            # The race-free second harvest pass: at prompt time the PREVIOUS turn's final
            # message is always flushed, so this catches whatever the Stop-side harvest
            # raced past (measured chars=0 at a turn-final Stop, 2026-08-29).
            if transcript_path:
                cmd_harvest(session, _final_message_text(transcript_path))
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
