#!/usr/bin/env python3
# AFTER-EDIT: tests/test_thread_anchor.py, docs/reference/thread-anchors.md, .claude/hooks/final_gate_stop.py, .claude/settings.json, scripts/work.py | none
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
accepted the block AND allowed that Stop — a blocked Stop gets no prompt to clear it) and cleared by the next UserPromptSubmit whose first whole token is not on
the closed _BUILTIN_SLASH list; an answered block is never stored again. Anchors older than 72 h
fold into one line and are never expired. The WHERE render runs under a wall-clock budget.

Every load-modify-save runs under an exclusive per-session flock (``<sid>.lock``) and writes
through a unique temp file — a concurrent harvest must never write back a cleared DECISION.

THE WORK STORE (work tracking, spec 2026-09-24 § NEXT, DECISION blocks and the register). With a
repo — ``--repo``, else the hook payload's ``cwd``, NEVER the process cwd — whose ``.fabrik/work/``
exists, ``scripts/work.py`` (loaded by path, beside this script) is called in-process:
  harvest   ONE ``on_harvest`` call after the session lock is released (never both locks at once):
            the accepted DECISION block becomes an awaiting item, a NEXT naming ``W-…`` sets that
            item's ``next``, and the session's live claims are renewed — a quiet turn included.
            The stored slot carries the resolved ``repo``.
  line      the second chance: every session's slot for this repo (≤ 7 days old) whose message
            digest no item holds is created in ONE ``ensure_decision_items`` call; a failed write
            prints one warning line. Then ``prompt_block`` prints first, never folded.
A repo without a store, or a copy without ``work.py``, does none of this.

State: one JSON per session under ``~/.claude/state/threads/`` (override: THREAD_ANCHOR_DIR).
Session-scoped because three concurrent sessions share this repo. EVERY path fails open — this
runs inside the Stop hook, where an exception would block end-of-turn fleet-wide.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    import fcntl
except ImportError:  # not POSIX: no session lock, the pre-lock behaviour
    fcntl = None  # type: ignore[assignment]

# The footer shapes the Stop hook reads as `NEXT:` (`final_gate_stop._NEXT_LINE_RE`: bold, bulleted,
# quoted) — a plain-only harvest showed WHERE YOU ARE an older NEXT than the one the agent last wrote.
# At most 3 spaces of indent (4 is a markdown code block); `pre` keeps the markers so `_next_values`
# can prefer an unquoted footer and strip a closing `**`/`__` only when the line opened bold.
_NEXT_RE = re.compile(
    r"^(?P<pre>[ ]{0,3}(?:[>*_-][ \t]*)*)NEXT[*_]*[ \t]*:(?P<close>[*_]*)[ \t]*(?P<v>.*?)[ \t]*$",
    re.M,
)
_FENCE_LINE_RE = re.compile(r"^[ \t>]*(?:```|~~~)")


def _next_values(text: str) -> list[str]:
    """Every footer-shaped NEXT value outside a fenced block, the operative one LAST: a quoted
    (`> NEXT:`) line is someone else's words, so it is operative only when no unquoted one exists.
    A fence left open at the end is not a fence — its lines count, or a footer written after an
    unclosed snippet would be lost."""
    kept: list[str] = []
    held: list[str] = []
    fenced = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _FENCE_LINE_RE.match(line):
            if fenced:
                held = []
            fenced = not fenced
        elif fenced:
            held.append(line)
        else:
            kept.append(line)
    kept += held
    plain: list[str] = []
    quoted: list[str] = []
    for m in _NEXT_RE.finditer("\n".join(kept)):
        v, pre = m.group("v"), m.group("pre")
        for mark in ("**", "__"):
            # the closer pairs with the opener before NEXT only when the value's own marks are odd
            if mark in pre and not m.group("close") and v.endswith(mark) and v.count(mark) % 2:
                v = v[: -len(mark)].rstrip()
        if v:
            (quoted if ">" in pre else plain).append(v)
    return plain or quoted


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
# The built-in and UI/local slash commands that can reach UserPromptSubmit and are NOT the
# operator's answer to an open DECISION block — a CLOSED list. The prompt's WHOLE first token must
# equal one of these, case-insensitively: `/contextualize x` shares `/context`'s prefix and is a
# custom command, and a custom command (like plain text) clears the block (A-O41, A-O8).
_BUILTIN_SLASH = frozenset(
    {
        "/compact",
        "/context",
        "/cost",
        "/model",
        "/autocompact",
        "/clear",
        "/help",
        "/status",
        "/config",
        "/memory",
        "/usage",
        "/resume",
        "/rewind",
        "/mcp",
        "/agents",
        "/permissions",
        "/export",
        "/todos",
        "/doctor",
        "/hooks",
        "/ide",
        "/login",
        "/logout",
        "/statusline",
        "/terminal-setup",
        "/vim",
        "/exit",
        "/add-dir",
        "/plugin",
        "/bashes",
        "/output-style",
        "/release-notes",
        "/theme",
        "/privacy-settings",
        "/upgrade",
    }
)
_GIT_TIMEOUT_S = 2.0
_MAX_LISTED = 10  # unpushed commits and dirty files in WHERE YOU ARE, each
_MAX_LINE = 300  # every WHERE YOU ARE line, cut with "…"
# The WHERE YOU ARE render's wall-clock budget, inside the SessionStart entry's 10 s timeout
# (`.claude/settings.json`): a 50 MB transcript alone takes 4-11 s to scan. Past it, the costly
# items (the hook's run record, the git/transcript scan) are skipped with ONE line; the items read
# from this script's own state still print.
_WHERE_BUDGET_S = 5.0
_LOCK_TIMEOUT_S = 1.0  # a state write that cannot take the session lock in time is skipped
_RESCUE_MAX_AGE_S = 7 * 86400  # a DECISION slot older than this is never rescued into the store


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
        # Whatever the hook prints at import would land in the injected context; a SystemExit
        # there would escape `except Exception` and silence the whole SessionStart output.
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        _HOOK_ERR = f"cannot import {path}: {type(e).__name__}: {e}"
        raise ImportError(_HOOK_ERR) from None
    _HOOK = mod
    return mod


_WORK: ModuleType | None = None
_WORK_ERR: str | None = None


def _work() -> ModuleType | None:
    """``scripts/work.py`` beside this script, imported BY PATH once per process; None (cached)
    when it is missing or fails to import — a repo the sync has not yet delivered it to fails
    open, and the work store is simply not used. An import FAILURE says so in one stderr line."""
    global _WORK, _WORK_ERR
    if _WORK is not None or _WORK_ERR is not None:
        return _WORK
    path = Path(__file__).resolve().parent / "work.py"
    try:
        if not path.is_file():
            _WORK_ERR = f"{path} does not exist"
            return None
        spec = importlib.util.spec_from_file_location("_thread_anchor_work", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        _WORK_ERR = f"work store unavailable — {type(e).__name__}: {e}"
        _warn(_WORK_ERR)
        return None
    _WORK = mod
    return mod


def _resolve_repo(raw: object) -> Path | None:
    """The work tree's top level for ``raw`` (``--repo`` or the payload's ``cwd``) through
    ``work.repo_root`` — None when nothing was given, work.py is unavailable, or it is no repo."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    w = _work()
    if w is None:
        return None
    try:
        root = w.repo_root(raw)
    except Exception:
        return None
    return root if isinstance(root, Path) else None


def _ts(a: dict[str, Any]) -> float | None:
    """The anchor's timestamp, or None when it is missing or not a positive finite number — an
    UNKNOWN age, which stays young: read as 0 it folded as ~497,000 h old and was evicted first."""
    ts = a.get("ts")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return None
    try:
        return float(ts) if math.isfinite(ts) and ts > 0 else None
    except OverflowError:  # a JSON int past float range (10**400) — unknown, never a wedge
        return None


def _is_old(a: dict[str, Any], now: float) -> bool:
    ts = _ts(a)
    return ts is not None and now - ts >= _FOLD_AGE_S


def _recency(a: dict[str, Any]) -> float:
    """Sort key, oldest first; an unknown age sorts as the NEWEST, so it is never evicted first."""
    ts = _ts(a)
    return math.inf if ts is None else ts


def _dropped(state: dict) -> int:
    try:
        return max(0, int(state.get("dropped") or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _cap(line: str) -> str:
    return line if len(line) <= _MAX_LINE else line[: _MAX_LINE - 1] + "…"


def _bounded(fn: Callable[[], Any], timeout: float) -> Any:
    """Run ``fn`` with a wall-clock bound: a daemon thread, joined for ``timeout`` seconds. A
    timeout raises TimeoutError (the thread is abandoned; its git calls carry their own timeouts)."""
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = fn()
        except BaseException as e:  # re-raised below as an ordinary exception
            box["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(max(0.0, timeout))
    if t.is_alive():
        raise TimeoutError(f"over the {_WHERE_BUDGET_S:g} s budget")
    err = box.get("error")
    if err is not None:
        raise err if isinstance(err, Exception) else RuntimeError(repr(err))
    return box.get("value")


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
    """Atomic write through a UNIQUE temp in the same directory — two writers never share a temp
    name, and a killed hook never leaves a torn file. Fail-open with one stderr line."""
    tmp = ""
    try:
        p = _state_path(session)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=p.name + ".", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(state, indent=1))
        os.replace(tmp, p)
    except Exception as e:
        _warn(f"state not saved — {type(e).__name__}: {e}")  # losing one write beats a blocked turn
        if tmp:
            with contextlib.suppress(OSError):
                os.unlink(tmp)


@contextlib.contextmanager
def _locked(session: str) -> Iterator[bool]:
    """An exclusive per-session flock, waited on for at most _LOCK_TIMEOUT_S. Yields False when it
    cannot be taken; the caller then skips its write. Closing the descriptor releases it."""
    if fcntl is None:
        yield True
        return
    try:
        lock = _state_path(session).with_suffix(".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as e:
        _warn(f"state lock unavailable — {e}")
        yield False
        return
    try:
        deadline = time.monotonic() + _LOCK_TIMEOUT_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    yield False
                    return
                time.sleep(0.02)
        yield True
    finally:
        os.close(fd)


def _update(session: str, fn: Callable[[dict], bool]) -> bool:
    """Load → ``fn(state)`` → save, as ONE step under the session lock: an unlocked
    read-modify-write let a Stop-side harvest write back a DECISION the operator had just
    answered. ``fn`` returns whether it changed anything. A lock not taken in time skips the
    write with one stderr line (fail-open)."""
    with _locked(session) as ok:
        if not ok:
            _warn(f"session state busy for over {_LOCK_TIMEOUT_S:g} s — this write was skipped")
            return False
        state = _load(session)
        if fn(state):
            _save(session, state)
        return True


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


def _age(ts: float | None) -> str:
    if ts is None:
        return "?"
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
    """Evict the OLDEST anchor of each class over its cap — young (< 72 h, or of unknown age) over
    _MAX_ANCHORS, folded over _MAX_FOLDED — and count every eviction in state["dropped"]."""
    anchors = state["anchors"]
    young = sorted((a for a in anchors if not _is_old(a, now)), key=_recency)
    old = sorted((a for a in anchors if _is_old(a, now)), key=_recency)
    drop = young[: max(0, len(young) - _MAX_ANCHORS)] + old[: max(0, len(old) - _MAX_FOLDED)]
    if drop:
        gone = {id(a) for a in drop}
        state["anchors"] = [a for a in anchors if id(a) not in gone]
        state["dropped"] = _dropped(state) + len(drop)


def _digest(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8", "replace")).hexdigest()


def cmd_harvest(
    session: str, text: str, decision_ok: bool = False, repo: Path | None = None
) -> None:
    """Store the message's last NEXT: (promoting long-running shapes to anchors) and, ONLY with
    ``decision_ok`` — the Stop hook passes it when it ACCEPTED the block and ALLOWED the Stop —
    its DECISION block.
    Without the flag no block is ever stored: a refused or malformed block must not come back
    after a compaction as if it were open (C-O8's twin, A-O30).

    A stored block carries the digest of the WHOLE message it came in (``msg``). The Stop hook
    falls back to the previous turn's text when the new one is not flushed yet (A-O7), so after the
    operator answers, the SAME whole message can be harvested again: when the incoming text's
    digest equals ``cleared_msg`` the block is not re-stored. No clock is involved — the echo is
    refused however long the turn ran — and a word-for-word re-ask arrives in a NEW message, so it
    is stored at once. Older state shapes (``cleared_decision``) suppress nothing.

    With ``repo`` (the Stop side only — the prompt-time re-harvest never passes it) the slot stores
    it, and ONE ``work.on_harvest`` call follows on BOTH exits — after ``_update`` has released the
    session lock, so the two locks are never held together (≤ 1 s + ≤ 2 s, inside the Stop hook's
    5 s subprocess timeout)."""
    matches = _next_values(text)
    block = None
    if decision_ok and text:
        try:
            block = _hook().extract_decision_block(text)
        except Exception as e:
            _warn(f"DECISION block not stored — {e}")
    if not matches and not block:
        _store_harvest(repo, session, None, "", None)  # a quiet turn still renews its claims
        return
    now = time.time()
    msg = _digest(text)

    def apply(state: dict) -> bool:
        if block and msg != state.get("cleared_msg"):
            state["decision"] = {"ts": now, "text": block, "msg": msg}
            if repo is not None:
                state["decision"]["repo"] = str(repo)
        if matches:
            nxt = matches[-1][:300]  # the LAST NEXT: in the message is the operative one
            state["last_next"] = {"ts": now, "text": nxt}
            if _is_anchor(nxt):
                key = _anchor_key(nxt)
                for a in state["anchors"]:
                    if _same_thread(a["key"], key):
                        # Progress update, not a duplicate — and the key RE-ROOTS to the newest
                        # text, so a thread whose wording tightens over time keeps one identity.
                        a.update(text=nxt, key=key, ts=now)
                        break
                else:
                    state["anchors"].append({"key": key, "text": nxt, "ts": now})
        _enforce_caps(state, now)
        return True

    _update(session, apply)
    _store_harvest(repo, session, block, msg, matches[-1] if matches else None)


def _store_harvest(
    repo: Path | None, session: str, block: str | None, msg: str, next_text: str | None
) -> None:
    """The Stop harvest's ONE store call (``work.on_harvest``, fail-open inside). Never raises."""
    if repo is None:
        return
    w = _work()
    if w is None:
        return
    try:
        w.on_harvest(repo, session=session, block=block, msg_digest=msg, next_text=next_text)
    except Exception as e:
        _warn(f"work store not updated — {type(e).__name__}: {e}")


def _rescue_decisions(session: str, repo: Path) -> tuple[str | None, str]:
    """The second chance, on a prompt-side ``line --hook``: every session's DECISION slot for
    ``repo`` (≤ 7 days old) whose MESSAGE digest no item holds is created in ONE
    ``ensure_decision_items`` call — one ≤ 2 s store wait however many slots. Matched by the
    message digest, never the block's: a block answered, then re-asked word for word in a new
    message whose Stop write failed, still gets its item. Other sessions' files are only read, and
    no session lock is held across the store call.

    Returns (the ``msg`` this session's slot carried when it was read — None when the rescue did
    not cover it — and a warning line, "" unless the write failed). Never raises."""
    seen: str | None = None
    w = _work()
    if w is None:
        return seen, ""
    try:
        if not w.has_store(repo):
            return seen, ""
        own = _state_path(session)
        cutoff = time.time() - _RESCUE_MAX_AGE_S
        entries: list[tuple[str, str, str]] = []
        for path in sorted(_state_dir().glob("*.json")):
            try:
                if path.stat().st_mtime < cutoff:  # every slot write rewrites its file
                    continue
                dec = json.loads(path.read_text(encoding="utf-8")).get("decision")
            except Exception:
                continue
            if not isinstance(dec, dict) or dec.get("repo") != str(repo):
                continue
            msg, text, ts = dec.get("msg"), dec.get("text"), _ts(dec)
            if not (isinstance(msg, str) and msg and isinstance(text, str) and text.strip()):
                continue
            if path == own:
                seen = msg
            if ts is None or ts < cutoff or w.has_msg_digest(repo, msg):
                continue
            entries.append((text, msg, session if path == own else path.stem))
        if not entries:
            return seen, ""
        ids = w.ensure_decision_items(repo, entries)
        failed = len(entries) - len(ids or [])
    except Exception as e:
        _warn(f"DECISION rescue skipped — {type(e).__name__}: {e}")
        return seen, ""
    if failed <= 0:
        return seen, ""
    return seen, _cap(
        f"work: ⚠ {failed} DECISION block(s) not written to the work store of {repo} (store "
        "busy or write failed) — those questions are NOT tracked as work items"
    )


def cmd_clear_decision(session: str, prompt: object, expect_msg: str | None = None) -> None:
    """UserPromptSubmit: the operator's next prompt answers an open DECISION block — unless its
    WHOLE first token is on the closed _BUILTIN_SLASH list, case-insensitively (`/compact` is not
    an answer; `/contextualize x` and `/fabrik-deploy prod` are). A payload with no string
    ``prompt`` is no evidence of an answer, so it clears nothing; a real one always carries it.
    The answered block's message digest moves to ``cleared_msg``, so the same whole message
    harvested again is not re-stored (A-O7; see cmd_harvest).

    ``expect_msg`` is the slot's ``msg`` as the second chance read it: the slot is cleared only
    while it still carries that message — one a concurrent Stop harvest replaced in between is
    left for its own next prompt. None (no rescue ran) clears exactly as before."""
    if not isinstance(prompt, str):
        return
    toks = prompt.split()
    if toks and toks[0].lower() in _BUILTIN_SLASH:
        return

    def apply(state: dict) -> bool:
        dec = state.get("decision")
        if not dec:
            return False
        msg = dec.get("msg") if isinstance(dec, dict) else None
        if expect_msg is not None and msg != expect_msg:
            return False
        state["cleared_msg"] = msg if isinstance(msg, str) else None
        state["decision"] = None
        return True

    _update(session, apply)


def _thread_lines(state: dict, session: str, now: float) -> tuple[list[dict], str | None]:
    """(the young anchors shown in full, newest first, capped) and the fold line, or None.

    The fold line prints whenever an anchor is older than 72 h, OR an eviction was counted while
    at least one anchor is still open — a young-cap eviction in a session with no folded anchor
    must still surface (A-O19), and `done` resets the count, so it never prints forever (A-S3)."""
    anchors = state["anchors"]
    young = [a for a in anchors if not _is_old(a, now)]
    old = [a for a in anchors if _is_old(a, now)]
    shown = sorted(young, key=lambda a: -_recency(a))[:_MAX_SHOWN]
    dropped = _dropped(state) if anchors else 0
    parts = []
    if old:
        parts.append(
            f"{len(old)} older thread(s), oldest {_age(min(_recency(a) for a in old))} — close "
            f"with python3 scripts/thread_anchor.py done --session {session} --match <substr>"
        )
    if dropped > 0:
        parts.append(f"… {dropped} dropped over the cap")
    return shown, ("- " + " ".join(parts)) if parts else None


def _next_is_shown(last: object, anchors: list[dict]) -> bool:
    """The latest NEXT: is already on screen when the newest anchor shown was MADE from it — its text
    IS the anchor's text (one rule, read by the usual block and by WHERE YOU ARE). A key match is
    not enough: the key lower-cases and masks digits, so a NEXT that was never promoted can share
    the anchor's key while its own text appears nowhere (B-S2)."""
    return (
        isinstance(last, dict)
        and bool(anchors)
        and str(last.get("text") or "") == str(anchors[0].get("text") or "")
    )


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
    if last and not _next_is_shown(last, anchors):
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


def _git_root(cwd: Path, timeout: float) -> Path:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip()).resolve()
    except Exception:
        pass
    return cwd


def _dirty_authored(root: Path, authored: set[str], timeout: float = _GIT_TIMEOUT_S) -> list[str]:
    """This session's files with uncommitted changes — `git status --porcelain=v1 -z` filtered to
    ``authored``; bounded (``timeout``, 10 at most). NUL-separated records, so no C-quoting and no
    ` -> ` ambiguity; a rename or copy record carries a second (source) path. A git error or
    timeout raises to the caller."""
    if not authored:
        return []
    out = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        encoding="utf-8",
        errors="surrogateescape",
        timeout=timeout,
        check=True,
    ).stdout
    fields = out.split("\0")
    paths: set[str] = set()
    i = 0
    while i < len(fields):
        rec = fields[i]
        i += 1
        if len(rec) < 4:
            continue
        names = [rec[3:]]
        if "R" in rec[:2] or "C" in rec[:2]:
            if i < len(fields):
                names.append(fields[i])
            i += 1
        paths.update(n for n in names if n in authored)
    return sorted(paths)[:_MAX_LISTED]


def _session_git(session: str, cwd: Path, transcript_path: str, deadline: float) -> list[str]:
    """Item 4's lines: this session's unpushed commits and dirty files. Each git call is bounded by
    the shorter of its own timeout and what is left of the render budget."""

    def left() -> float:
        return max(0.1, min(_GIT_TIMEOUT_S, deadline - time.monotonic()))

    h = _hook()
    root = _git_root(cwd, left())
    authored = set(
        h._this_sessions_edits(h._session_files(transcript_path, root), h._baseline_floor(session))
    )
    commits = h.session_unpushed(root, authored, timeout=left(), limit=_MAX_LISTED)
    dirty = _dirty_authored(root, authored, left())
    lines: list[str] = []
    if commits:
        lines.append("- UNPUSHED (this session's commits, newest first):")
        lines += [f"    {c}" for c in commits[:_MAX_LISTED]]
    if dirty:
        lines.append("- DIRTY (this session's files):")
        lines += [f"    {d}" for d in dirty]
    return lines


def cmd_where(session: str, cwd: Path, transcript_path: str, repo: Path | None = None) -> str:
    """`## ⏮ WHERE YOU ARE` — printed after a compaction INSTEAD of the usual block, built only
    from records (spec § C3). Each item that fails is omitted with one stderr line; the rest print.
    The costly items run under one wall-clock budget (_WHERE_BUDGET_S); past it, what remains of
    them collapses into one `- (skipped: time budget)` line. Every line is cut at _MAX_LINE.
    Silent when every item is empty. The OPEN DECISION slot is left out only when ``repo``'s work
    store holds its message's item — the unfolded block above already lists it."""
    deadline = time.monotonic() + _WHERE_BUDGET_S
    state = _load(session)
    now = time.time()
    anchors, fold = _thread_lines(state, session, now)
    items: list[str] = []
    skipped: list[str] = []

    def costly(name: str, fn: Callable[[], list[str]]) -> None:
        if deadline - time.monotonic() <= 0:
            skipped.append(name)
            return
        try:
            items.extend(_bounded(fn, deadline - time.monotonic()))
        except TimeoutError:
            skipped.append(name)
        except Exception as e:
            _warn(f"WHERE YOU ARE: {name} omitted — {e}")

    def run_item() -> list[str]:  # 1. the live command run
        rec = _hook()._run_record(session)
        ok = isinstance(rec, dict) and rec.get("state") == "running"
        return [_run_line(rec)] if ok else []

    costly("the live run", run_item)
    last = state.get("last_next")  # 2. the last NEXT: (once — not when it is the newest anchor)
    if isinstance(last, dict) and last.get("text") and not _next_is_shown(last, anchors):
        items.append(f"- NEXT (before the compaction): {last['text']}")
    dec = state.get("decision")  # 3. an open DECISION block
    if isinstance(dec, dict) and dec.get("text") and not _in_store(repo, dec.get("msg")):
        items.append("- OPEN DECISION — awaiting the operator's answer; never treat it as settled:")
        items += [f"    {ln}" for ln in str(dec["text"]).splitlines()]
    if transcript_path:  # 4. this session's unpushed commits and dirty files
        costly(
            "unpushed commits and dirty files",
            lambda: _session_git(session, cwd, transcript_path, deadline),
        )
    if skipped:
        items.append("- (skipped: time budget) " + "; ".join(skipped))
    if anchors or fold:  # 5. open threads, folded
        items.append(
            f"- OPEN THREADS (close with python3 scripts/thread_anchor.py done --session "
            f"{session} --match <substr>):"
        )
        items += [f"    - {a['text']}  ({_age(_ts(a))} ago)" for a in anchors]
        if fold:
            items.append("    " + fold)
    if not items:
        return ""
    head = "## ⏮ WHERE YOU ARE — rebuilt from records after the compaction"
    return "\n".join(_cap(ln) for ln in [head, *items])


def _in_store(repo: Path | None, msg: object) -> bool:
    w = _work() if repo is not None else None
    if w is None or not isinstance(msg, str) or not msg:
        return False
    try:
        return bool(w.has_msg_digest(repo, msg))
    except Exception:
        return False


def _prompt_block(repo: Path, session: str) -> str:
    w = _work()
    if w is None:
        return ""
    try:
        return str(w.prompt_block(repo, session) or "")
    except Exception as e:
        _warn(f"work block skipped — {type(e).__name__}: {e}")
        return ""


def cmd_done(session: str, match: str) -> None:
    """Close every anchor whose text contains `match` — and SAY what happened. A close that prints
    nothing is byte-identical to a typo'd match (youtube + wef, 2026-09-03: two threads "closed",
    both re-printed by the next hook; the agent had told the operator they were closed). A `done`
    that closes at least one anchor also resets the "dropped over the cap" count: it is the
    acknowledgement that silences it."""
    said: list[str] = []

    def apply(state: dict) -> bool:
        before = len(state["anchors"])
        state["anchors"] = [
            a for a in state["anchors"] if match.lower() not in str(a.get("text", "")).lower()
        ]
        closed = before - len(state["anchors"])
        if closed:
            said.append(f"closed {closed} anchor(s) ({len(state['anchors'])} remain)")
        else:
            said.append(f"no anchor matched {match!r} ({before} open)")
        # The latest-NEXT echo dies with its anchor — found by the suite's own red: `done` removed
        # the anchor and the stale last_next line resurrected the same text one line lower.
        last = state.get("last_next")
        if isinstance(last, dict) and match.lower() in str(last.get("text", "")).lower():
            state["last_next"] = None
        if closed:
            state["dropped"] = 0  # a typo'd match acknowledges nothing
        return True

    if not _update(session, apply):
        said.append("nothing was closed — the session state is busy; run it again")
    for s in said:
        print(s)


def main(argv: list[str] | None = None) -> int:
    # The real stdout, pinned before any work: a hook import abandoned past the render budget can
    # still be inside its redirect_stdout when the block prints.
    real_stdout = sys.stdout
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
        ap.add_argument(
            "--repo",
            default="",
            help="the repo whose work store (.fabrik/work/) the harvest writes; else the hook "
            "payload's cwd; never the process cwd",
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

        # The work store's repo: --repo, else the payload's cwd — NEVER os.getcwd() (tests and
        # hooks run from another tree and would read, and lock, ITS store).
        repo = _resolve_repo(args.repo or payload.get("cwd")) if args.cmd != "done" else None

        if args.cmd == "harvest":
            # --hook with nothing piped: extract from the payload's transcript (the help
            # text promised this from day one; the code now delivers it).
            if not stdin_text and transcript_path:
                stdin_text = _final_message_text(transcript_path)
            cmd_harvest(session, stdin_text, decision_ok=args.decision_ok, repo=repo)
        elif args.cmd == "line":
            # The race-free second harvest pass: at prompt time the PREVIOUS turn's final
            # message is always flushed, so this catches whatever the Stop-side harvest
            # raced past (measured chars=0 at a turn-final Stop, 2026-08-29). It NEVER passes
            # decision_ok: only the Stop hook judges a DECISION block, so this pass can clear
            # one (below) but never re-store it (C-O8).
            if transcript_path:
                cmd_harvest(session, _final_message_text(transcript_path))
            event = payload.get("hook_event_name")
            seen: str | None = None
            head: list[str] = []
            if repo is not None:
                warning = ""
                if event in ("UserPromptSubmit", "SessionStart"):
                    seen, warning = _rescue_decisions(session, repo)
                head = [ln for ln in (_prompt_block(repo, session), warning) if ln]
            if event == "UserPromptSubmit":
                cmd_clear_decision(session, payload.get("prompt"), expect_msg=seen)
            if payload.get("source") == "compact":
                cwd = Path(str(payload.get("cwd") or os.getcwd())).resolve()
                out = cmd_where(session, cwd, transcript_path, repo=repo)
            else:
                out = cmd_line(session)
            # The work block first, never folded — above the usual block and WHERE YOU ARE.
            out = "\n".join([*head, out] if out else head)
            if out:
                # Flushed HERE: past the budget the abandoned import thread still holds sys.stdout
                # redirected at exit, so nothing flushes this stream for us (0 bytes, measured).
                real_stdout.write(out + "\n")
                real_stdout.flush()
        elif args.cmd == "done":
            if args.match:
                cmd_done(session, args.match)
        return 0
    except Exception as e:
        _warn(f"{type(e).__name__}: {e} — skipped")
        return 0  # fail-open, always: this sits inside the Stop hook's path


if __name__ == "__main__":
    sys.exit(main())
