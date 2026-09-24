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

COMPACTION SURVIVAL (spec § C3, 2026-09-23 stop-and-compaction design): on a SessionStart whose
``source`` is ``compact``, ``line --hook`` prints ``## ⏮ WHERE YOU ARE`` INSTEAD of its usual
block, built only from records — the live command run, the last NEXT:, an open DECISION block,
this session's unpushed commits and dirty files, and the open threads, folded. The DECISION block
is stored only by a Stop-side ``harvest --decision-ok`` (the hook passes the flag only when it
accepted the block) and cleared by the next UserPromptSubmit whose first whole token is not a
built-in slash command. Anchors older than 72 h fold into one line and are never expired.

State: one JSON per session under ``~/.claude/state/threads/`` (override: THREAD_ANCHOR_DIR).
Session-scoped because three concurrent sessions share this repo. EVERY path fails open — this
runs inside the Stop hook, where an exception would block end-of-turn fleet-wide.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

_NEXT_RE = re.compile(r"^NEXT:\s*(.+?)\s*$", re.M)
# Long-running shapes worth persisting past the turn that wrote them. Deliberately FEW: every
# shape added here is a line the injector may print on every prompt of every session.
_ANCHOR_RES = (
    re.compile(r"\b\d+\s+of\s+\d+\b", re.I),  # "command 14 of 31", "TC3 of 12"
    re.compile(r"docs/development/(?:plans|epics|certifications)/[\w./-]+"),
    re.compile(r"\bphase\s+[A-Z]\b"),  # mid-plan position
)
_MAX_SHOWN = 4
# Anchors younger than _FOLD_AGE_S are capped at _MAX_ANCHORS; older ones fold into one line and
# are capped separately at _MAX_FOLDED. An eviction under EITHER cap drops the OLDEST anchor of
# its own class and increments state["dropped"], which the fold line prints — the Stop-side
# harvest's stderr is captured and read by nobody, so the fold line is the only place a drop can
# surface. The cap used to drop by LIST POSITION, which evicted exactly the standing thread paused
# behind days of tangents that this register exists to keep (A-O13).
# ⚠️ COBRA (D-253): the cheapest way to make the "dropped" count read 0 is to raise the caps until
# the injected block is wallpaper again; the caps are the anti-wallpaper bound, so a large count
# is answered by closing threads (`done`), never by moving these numbers.
_MAX_ANCHORS = 12
_MAX_FOLDED = 50
_FOLD_AGE_S = 72 * 3600
# The built-in slash commands that are NOT the operator's answer to an open DECISION block. The
# prompt's WHOLE first token must equal one of these: `/contextualize x` shares `/context`'s prefix
# and is a custom command, and a custom command (like plain text) clears the block (A-O41).
_BUILTIN_SLASH = frozenset(
    {"/compact", "/context", "/cost", "/model", "/autocompact", "/clear", "/help"}
)
_GIT_TIMEOUT_S = 2.0
_MAX_LISTED = 10  # unpushed commits and dirty files in WHERE YOU ARE, each


def _warn(msg: str) -> None:
    """One stderr line — never a traceback: `line --hook` runs on every SessionStart fleet-wide."""
    try:
        sys.stderr.write("thread_anchor: " + " ".join(str(msg).split()) + "\n")
    except Exception:
        pass


_HOOK: ModuleType | None = None
_HOOK_ERR: str | None = None


def _hook() -> ModuleType:
    """The Stop hook, imported BY PATH from this script's own repo (the hook ships to every
    project beside this script) — once per process; a failure is cached and re-raised."""
    global _HOOK, _HOOK_ERR
    if _HOOK is not None:
        return _HOOK
    if _HOOK_ERR is not None:
        raise ImportError(_HOOK_ERR)
    path = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
    try:
        spec = importlib.util.spec_from_file_location("_thread_anchor_final_gate_stop", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        _HOOK_ERR = f"cannot import {path}: {type(e).__name__}: {e}"
        raise ImportError(_HOOK_ERR) from None
    _HOOK = mod
    return mod


def _ts(a: dict[str, Any]) -> float:
    try:
        return float(a.get("ts") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _state_dir() -> Path:
    d = os.environ.get("THREAD_ANCHOR_DIR")
    return Path(d) if d else Path.home() / ".claude" / "state" / "threads"


def _state_path(session: str) -> Path:
    safe = re.sub(r"[^\w-]", "_", session or "nosession")[:64]
    return _state_dir() / f"{safe}.json"


def _load(session: str) -> dict:
    try:
        state = json.loads(_state_path(session).read_text(encoding="utf-8"))
    except Exception:
        state = None
    if not isinstance(state, dict):
        return {"anchors": [], "last_next": None}
    if not isinstance(state.get("anchors"), list):
        state["anchors"] = []
    return state


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


def _enforce_caps(state: dict, now: float) -> None:
    """Evict the OLDEST anchor of each class over its cap — young (< 72 h) over _MAX_ANCHORS,
    folded over _MAX_FOLDED — and count every eviction in state["dropped"]."""
    anchors = state["anchors"]
    young = sorted((a for a in anchors if now - _ts(a) < _FOLD_AGE_S), key=_ts)
    old = sorted((a for a in anchors if now - _ts(a) >= _FOLD_AGE_S), key=_ts)
    drop = young[: max(0, len(young) - _MAX_ANCHORS)] + old[: max(0, len(old) - _MAX_FOLDED)]
    if drop:
        gone = {id(a) for a in drop}
        state["anchors"] = [a for a in anchors if id(a) not in gone]
        state["dropped"] = int(state.get("dropped") or 0) + len(drop)


def cmd_harvest(session: str, text: str, decision_ok: bool = False) -> None:
    """Store the message's last NEXT: (promoting long-running shapes to anchors) and, ONLY with
    ``decision_ok`` — the Stop hook passes it when it ACCEPTED the block — its DECISION block.
    Without the flag no block is ever stored: a refused or malformed block must not come back
    after a compaction as if it were open (C-O8's twin, A-O30)."""
    matches = _NEXT_RE.findall(text)
    block = None
    if decision_ok and text:
        try:
            block = _hook().extract_decision_block(text)
        except Exception as e:
            _warn(f"DECISION block not stored — {e}")
    if not matches and not block:
        return
    now = time.time()
    state = _load(session)
    if block:
        state["decision"] = {"ts": now, "text": block}
    if matches:
        nxt = matches[-1][:300]  # the LAST NEXT: in the message is the operative one
        state["last_next"] = {"ts": now, "text": nxt}
        if _is_anchor(nxt):
            key = _anchor_key(nxt)
            for a in state["anchors"]:
                if _same_thread(a["key"], key):
                    # Progress update, not a duplicate — and the key RE-ROOTS to the newest text,
                    # so a thread whose wording tightens over time keeps one identity.
                    a.update(text=nxt, key=key, ts=now)
                    break
            else:
                state["anchors"].append({"key": key, "text": nxt, "ts": now})
    _enforce_caps(state, now)
    _save(session, state)


def cmd_clear_decision(session: str, prompt: object) -> None:
    """UserPromptSubmit: the operator's next prompt answers an open DECISION block — unless its
    WHOLE first token is a built-in slash command (`/compact` is not an answer; `/contextualize x`
    and `/fabrik-deploy prod` are). A payload with no string ``prompt`` is no evidence of an
    answer, so it clears nothing."""
    if not isinstance(prompt, str):
        return
    toks = prompt.split()
    if toks and toks[0] in _BUILTIN_SLASH:
        return
    state = _load(session)
    if state.get("decision"):
        state["decision"] = None
        _save(session, state)


def _thread_lines(state: dict, session: str, now: float) -> tuple[list[dict], str | None]:
    """(the young anchors shown in full, newest first, capped) and the fold line, or None.

    The fold line prints whenever an anchor is older than 72 h OR an eviction was counted — a
    young-cap eviction in a session with no folded anchor must still surface (A-O19)."""
    anchors = state["anchors"]
    young = [a for a in anchors if now - _ts(a) < _FOLD_AGE_S]
    old = [a for a in anchors if now - _ts(a) >= _FOLD_AGE_S]
    shown = sorted(young, key=lambda a: -_ts(a))[:_MAX_SHOWN]
    try:
        dropped = int(state.get("dropped") or 0)
    except (TypeError, ValueError):
        dropped = 0
    parts = []
    if old:
        parts.append(
            f"{len(old)} older thread(s), oldest {_age(min(_ts(a) for a in old))} — close with "
            f"python3 scripts/thread_anchor.py done --session {session} --match <substr>"
        )
    if dropped > 0:
        parts.append(f"… {dropped} dropped over the cap")
    return shown, ("- " + " ".join(parts)) if parts else None


def cmd_line(session: str) -> str:
    state = _load(session)
    anchors, fold = _thread_lines(state, session, time.time())
    last = state.get("last_next")
    if not anchors and not fold and not last:
        return ""
    out = []
    if anchors or fold:
        out.append(
            f"## 🧵 OPEN THREADS (yours — close with `python3 scripts/thread_anchor.py done --session {session} --match <substr>`)"
        )
        out += [f"- {a['text']}  ({_age(_ts(a))} ago)" for a in anchors]
        if fold:
            out.append(fold)
    # The latest successor, shown only when it is NOT already an anchor above.
    if last and (not anchors or not _same_thread(_anchor_key(last["text"]), anchors[0]["key"])):
        out.append(f"- NEXT (latest): {last['text']}")
    return "\n".join(out)


def _run_line(rec: dict) -> str:
    cmd = str(rec.get("command") or "?").lstrip("/")
    where = f"phase {rec.get('phase') or 1}/{rec.get('phases') or '?'}"
    title = str(rec.get("phase_title") or "").strip()
    if title:
        where += f" ({title})"
    rounds = rec.get("rounds")
    if isinstance(rounds, list) and rounds:
        where += f" · round {len(rounds)}"
    terminal = str(rec.get("terminal") or "its own completion contract").strip()
    surface = str(rec.get("surface") or "").strip()
    return (
        f"- RUN: /{cmd} · {where} · terminal: {terminal}"
        + (f" · surface: {surface}" if surface else "")
        + " — run it to that terminal condition; do not hand back control mid-command."
    )


def _git_root(cwd: Path) -> Path:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).resolve()
    except Exception:
        pass
    return cwd


def _dirty_authored(root: Path, authored: set[str]) -> list[str]:
    """This session's files with uncommitted changes — `git status --porcelain` filtered to
    ``authored``; bounded (2 s, 10 at most). A git error or timeout raises to the caller."""
    if not authored:
        return []
    out = subprocess.run(
        ["git", "-c", "core.quotePath=false", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_S,
        check=True,
    ).stdout
    paths: set[str] = set()
    for line in out.splitlines():
        body = line[3:]
        if " -> " in body:
            body = body.split(" -> ", 1)[1]
        body = body.strip().strip('"')
        if body in authored:
            paths.add(body)
    return sorted(paths)[:_MAX_LISTED]


def cmd_where(session: str, cwd: Path, transcript_path: str) -> str:
    """`## ⏮ WHERE YOU ARE` — printed after a compaction INSTEAD of the usual block, built only
    from records (spec § C3). Each item that fails is omitted with one stderr line; the rest print.
    Silent when every item is empty."""
    state = _load(session)
    now = time.time()
    items: list[str] = []
    try:  # 1. the live command run
        rec = _hook()._run_record(session)
        if isinstance(rec, dict) and rec.get("state") == "running":
            items.append(_run_line(rec))
    except Exception as e:
        _warn(f"WHERE YOU ARE: the live run omitted — {e}")
    last = state.get("last_next")  # 2. the last NEXT:
    if isinstance(last, dict) and last.get("text"):
        items.append(f"- NEXT (before the compaction): {last['text']}")
    dec = state.get("decision")  # 3. an open DECISION block
    if isinstance(dec, dict) and dec.get("text"):
        items.append("- OPEN DECISION — awaiting the operator's answer; never treat it as settled:")
        items += [f"    {ln}" for ln in str(dec["text"]).splitlines()]
    if transcript_path:  # 4. this session's unpushed commits and dirty files
        try:
            h = _hook()
            root = _git_root(cwd)
            authored = set(
                h._this_sessions_edits(
                    h._session_files(transcript_path, root), h._baseline_floor(session)
                )
            )
            commits = h.session_unpushed(root, authored, timeout=_GIT_TIMEOUT_S, limit=_MAX_LISTED)
            dirty = _dirty_authored(root, authored)
            if commits:
                items.append("- UNPUSHED (this session's commits): " + " · ".join(commits))
            if dirty:
                items.append("- DIRTY (this session's files): " + ", ".join(dirty))
        except Exception as e:
            _warn(f"WHERE YOU ARE: unpushed commits and dirty files omitted — {e}")
    anchors, fold = _thread_lines(state, session, now)  # 5. open threads, folded
    if anchors or fold:
        items.append(
            f"- OPEN THREADS (close with python3 scripts/thread_anchor.py done --session "
            f"{session} --match <substr>):"
        )
        items += [f"    - {a['text']}  ({_age(_ts(a))} ago)" for a in anchors]
        if fold:
            items.append("    " + fold)
    if not items:
        return ""
    return "\n".join(["## ⏮ WHERE YOU ARE — rebuilt from records after the compaction", *items])


def cmd_done(session: str, match: str) -> None:
    """Close every anchor whose text contains `match` — and SAY what happened. A close that prints
    nothing is byte-identical to a typo'd match (youtube + wef, 2026-09-03: two threads "closed",
    both re-printed by the next hook; the agent had told the operator they were closed)."""
    state = _load(session)
    before = len(state["anchors"])
    state["anchors"] = [a for a in state["anchors"] if match.lower() not in a["text"].lower()]
    closed = before - len(state["anchors"])
    if closed:
        print(f"closed {closed} anchor(s) ({len(state['anchors'])} remain)")
    else:
        print(f"no anchor matched {match!r} ({before} open)")
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
        ap.add_argument(
            "--decision-ok",
            action="store_true",
            help="harvest only: the Stop hook ACCEPTED this message's DECISION block, so store "
            "it; without this flag no block is ever stored",
        )
        args, _ = ap.parse_known_args(argv)

        # Read stdin ONLY where it is part of the contract (harvest text, --hook JSON).
        # Found live: `done --match …` from an agent's shell — stdin open, not a tty, nothing
        # piped — blocked forever here, and the 2-minute tool timeout was the only way out.
        needs_stdin = args.cmd == "harvest" or args.hook
        stdin_text = "" if (not needs_stdin or sys.stdin.isatty()) else sys.stdin.read()
        session = args.session
        transcript_path = ""
        payload: dict = {}
        if args.hook and stdin_text:
            try:
                parsed = json.loads(stdin_text)
                if isinstance(parsed, dict):
                    payload = parsed
                    session = str(payload.get("session_id") or session)
                    transcript_path = str(payload.get("transcript_path") or "")
                    stdin_text = ""
            except Exception:
                pass
        if not session:
            if args.cmd == "done":
                # `done` without a session used to "close" into a placeholder store and exit 0 — a
                # silent no-op that read as success. CLAUDE_SESSION_ID is NOT in an agent's shell;
                # the hook now prints the session in its close command — copy it from there.
                print(
                    "thread_anchor: no session id — pass --session <id> (the OPEN THREADS line prints "
                    "it) or run under --hook; nothing was closed",
                    file=sys.stderr,
                )
                return 2
            session = "nosession"

        if args.cmd == "harvest":
            # --hook with nothing piped: extract from the payload's transcript (the help
            # text promised this from day one; the code now delivers it).
            if not stdin_text and transcript_path:
                stdin_text = _final_message_text(transcript_path)
            cmd_harvest(session, stdin_text, decision_ok=args.decision_ok)
        elif args.cmd == "line":
            # The race-free second harvest pass: at prompt time the PREVIOUS turn's final
            # message is always flushed, so this catches whatever the Stop-side harvest
            # raced past (measured chars=0 at a turn-final Stop, 2026-08-29). It NEVER passes
            # decision_ok: only the Stop hook judges a DECISION block, so this pass can clear
            # one (below) but never re-store it (C-O8).
            if transcript_path:
                cmd_harvest(session, _final_message_text(transcript_path))
            if payload.get("hook_event_name") == "UserPromptSubmit":
                cmd_clear_decision(session, payload.get("prompt"))
            if payload.get("source") == "compact":
                cwd = Path(str(payload.get("cwd") or os.getcwd())).resolve()
                out = cmd_where(session, cwd, transcript_path)
            else:
                out = cmd_line(session)
            if out:
                print(out)
        elif args.cmd == "done":
            if args.match:
                cmd_done(session, args.match)
        return 0
    except Exception as e:
        _warn(f"{type(e).__name__}: {e} — skipped")
        return 0  # fail-open, always: this sits inside the Stop hook's path


if __name__ == "__main__":
    sys.exit(main())
