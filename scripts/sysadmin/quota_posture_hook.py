#!/usr/bin/env python3
# AFTER-EDIT: tests/test_quota_posture.py | docs/workstation/hooks-index.md | docs/workstation/claude-account-rotation.md
"""The box-local quota-posture hook — one injected line per prompt, one hold at RED.

Reads the posture file the rotation tick writes (`_quota_posture` in
`scripts/sysadmin/claude_rotate.py`, D-269) and serves two hook events:

* **`UserPromptSubmit`** — prints ONE line to stdout, which the CLI lands as context:
  ``QUOTA: <slug> · 5h <n>% (<forecast>) · weekly <n>% (<forecast>) · Fable <n>% ·
  band <GREEN|AMBER|RED|WALL> · successor <slug or none>``.
* **`PreToolUse`** — at RED, HOLDS the two things that START new work: the ``Agent``
  tool outside a live run record, and a fresh ``command_run.py start`` outside the
  review family. Everything a checkpoint needs — edits, tests, git, ``done``,
  ``round``, mail, Monitor, TaskStop — stays allowed, so RED is finish-and-checkpoint,
  never freeze. At AMBER it says so ONCE per (session, band) through
  ``additionalContext``, carrying no permission decision at all.

⚠️ **BOX-LOCAL, NOT FLEET-SYNCED.** `--install` wires this into the six user-level
``settings.json`` files, so it reaches every window on this box without shipping into
the ~46 project repos. ``scripts/sysadmin/`` is absent from ``fabrik_synced_manifest.py``;
keep it that way.

⚠️ **FAIL-OPEN, ALWAYS.** A missing, unreadable or stale (>``QUOTA_POSTURE_STALE_S``)
posture is ABSENT: it holds nothing, and the line SAYS so rather than implying quota is
fine. That is the posture ``.claude/hooks/quota_stop.py`` already takes for the
fleet-exhausted stamp. A dead cron must never freeze the fleet and a session must never
be trapped, so every failure path here returns 0.

⚠️ **THE WALL IS NOT OURS.** While the ``fleet-exhausted`` stamp stands, ``quota_stop.py``
owns the deny and this hook is SILENT on ``PreToolUse``. The stamp is read BEFORE the
band, so a lagging RED posture cannot produce a second, differently worded deny for the
same call.

FIRE RATE (FIX DIRECTIVE 5), measured over 2,361 rotation-tick rows on 2026-09-16:
AMBER (>=85) 6.0%, RED (>=90) 4.7%, the 98 flip line 0. Signal, not wallpaper.

⚠️ **THE COBRA CHECK (D-253).** The cheapest way to satisfy "no heavy dispatch at RED"
WITHOUT producing the outcome is to finish the current work fast and dispatch after the
flip — which IS the wanted behaviour, so the measure and the goal agree. Spending RED on
many small non-``Agent`` calls is the gaming path that remains, and it burns quota visibly
on the injected line every prompt; NO second gate is added for it, because a gate on tool
COUNT would punish exactly the checkpoint work RED exists to protect.

⚠️ The FIRST draft of this block named that as "the one gaming path", and the review found
two far cheaper ones that a regex predicate could not see: QUOTE the script path, or lead
with a decoy ``--command fabrik-review`` before the real one. Both defeated the hold
entirely. Naming the wrong cheapest path is worse than naming none, because it tells the
next reader the question has already been asked — so the answer here is now a property of
the PREDICATE (it tokenises with ``shlex`` and reads the LAST ``--command`` the way argparse
does) rather than a claim in prose, and the bypass corpus in the graders is what keeps it
true.

Env keys, declared here and nowhere else:
  ``ROTATE_STATE_DIR``       the state dir holding the posture file and the stamp
  ``QUOTA_POSTURE_STALE_S``  the staleness bound in seconds (default 900 = 3 ticks)
  ``COMMAND_RUN_DIR``        the run-record dir (through the LOCAL copy below)
  ``QUOTA_POSTURE_SETTINGS`` ``os.pathsep``-joined settings files for --install/--check
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

_STALE_S_DEFAULT = 900.0
# the same bound `.claude/hooks/final_gate_stop.py` applies to the same record: a run nobody has
# touched in half a day is not a session in flight, and treating it as one licensed fan-out at RED
_RUN_RECORD_STALE_S = 12 * 3600.0
_TAIL_BYTES = 64 * 1024
_ROTATE = "/opt/fabrik/scripts/sysadmin/claude_rotate.py"
_REMEDY = f"run python3 {_ROTATE} --status"
_READ_ERRORS = (OSError, ValueError)

# ── local copies (NEVER an import of scripts/command_run.py) ────────────────────────
# This runs on EVERY tool call in EVERY window on this box. Importing a 1,000-line CLI
# on that path costs interpreter time per call and couples a box-local hook to a
# fleet-synced script's import side effects; `.claude/hooks/final_gate_stop.py` carries
# the same copies for the same reason. The agreement is not left to prose —
# `tests/test_quota_posture.py` re-derives both against `command_run`'s own functions
# over a sid corpus and asserts the two REVIEW_FAMILY sets are equal.

REVIEW_FAMILY = frozenset({"fabrik-review", "fabrik-review-scoped"})


def _state_dir() -> Path:
    """The run-record dir — byte-identical to ``command_run._state_dir``."""
    raw = os.environ.get("COMMAND_RUN_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "state" / "command-runs"


def _safe_sid(sid: str) -> str:
    """A filename-safe session id — byte-identical to ``command_run._safe_sid``.

    Flattening alone mapped ``abc.xyz`` and ``abc xyz`` onto one file, so an innocent
    session inherited another's run. When flattening changes anything, a short digest of
    the RAW id is appended, so distinct raw ids always get distinct files.
    """
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)
    if not safe:
        return "nosession"
    if safe != sid:
        tag = hashlib.blake2s(sid.encode("utf-8"), digest_size=4).hexdigest()
        safe = f"{safe}-{tag}"
    return safe


# ── the posture file ───────────────────────────────────────────────────────────────


def _rotate_state_dir() -> Path:
    raw = os.environ.get("ROTATE_STATE_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "state"


def _stale_s() -> float:
    """The staleness bound, read ONCE here so no reader hardcodes a second 900."""
    raw = os.environ.get("QUOTA_POSTURE_STALE_S")
    if not raw:
        return _STALE_S_DEFAULT
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return _STALE_S_DEFAULT
    # a non-finite or non-positive bound makes every posture stale, or none ever — a
    # silent policy change from an env typo. Keep the default instead.
    return v if math.isfinite(v) and v > 0 else _STALE_S_DEFAULT


def _load_posture(now: float) -> tuple[dict | None, str]:
    """``(posture, "")`` when fresh, else ``(None, reason)`` — ``absent`` · ``unreadable``
    · ``stale <m>m``. NEVER raises: every arm here is a reader's fail-open."""
    try:
        raw = (_rotate_state_dir() / "quota-posture.json").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "absent"
    except _READ_ERRORS:
        return None, "unreadable"
    try:
        # ⚠️ Both halves matter. A bare `NaN` passes `isinstance(ts, (int, float))`, and
        # `now - nan` is `nan`, which is never `>` the staleness bound — so a posture with a
        # non-finite `ts` renders as FRESH FOREVER and `posture unavailable` can never fire. That is
        # the worst failure direction this hook has: not a crash, a permanently confident wrong
        # answer on every prompt. The rotation script's own reader refuses these the same way.
        data = json.loads(
            raw,
            parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"non-finite: {c}")),
        )
    except ValueError:
        return None, "unreadable"
    ts = data.get("ts") if isinstance(data, dict) else None
    if not (isinstance(ts, (int, float)) and not isinstance(ts, bool) and math.isfinite(ts)):
        return None, "unreadable"
    age = now - float(ts)
    if age > _stale_s():
        return None, f"stale {age / 60:.0f}m"
    return data, ""


def _stamp_exists() -> bool:
    try:
        return (_rotate_state_dir() / "fleet-exhausted").exists()
    except OSError:
        return False


# ── the line ───────────────────────────────────────────────────────────────────────


def _pct(w: object) -> str:
    u = w.get("utilization") if isinstance(w, dict) else None
    ok = isinstance(u, (int, float)) and not isinstance(u, bool) and math.isfinite(u)
    return f"{u:.0f}%" if ok else "—"


def _forecast(w: object) -> str:
    """``reset in <h:mm>`` · ``wall in ~<m>m at <n>%/m`` · ``no burn`` — whichever the
    tick's own verdict names. The contract's grammar, byte for byte (D-269)."""
    if not isinstance(w, dict) or w.get("utilization") is None:
        return "—"

    # ⚠️ `_finite` is defence in depth, not decoration. The file reader refuses non-finite JSON, so
    # a poisoned window cannot arrive from the posture file — but this renderer is also reached from
    # `--status`, and `int(nan)` raises ValueError while `int(inf)` raises OverflowError. A renderer
    # that can raise on its own data can take down the command the contract names as the authority,
    # so an unusable number is treated as NO forecast rather than as an exception.
    def _finite(x: object) -> float | None:
        ok = isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
        return float(x) if ok else None

    v = w.get("verdict")
    mtr = _finite(w.get("minutes_to_reset"))
    if v == "reset_first" and mtr is not None:
        m = int(mtr)
        return f"reset in {m // 60}:{m % 60:02d}"
    mtw = _finite(w.get("minutes_to_wall"))
    if v == "wall_first" and mtw is not None:
        b = _finite(w.get("burn_per_min"))
        bt = f"{b:.2f}" if b is not None else "—"
        return f"wall in ~{int(mtw)}m at {bt}%/m"
    return "no burn"


def _format_line(posture: dict, band: str | None) -> str:
    act = posture.get("active") if isinstance(posture.get("active"), dict) else {}
    wins = act.get("windows") if isinstance(act.get("windows"), dict) else {}
    fleet = posture.get("fleet") if isinstance(posture.get("fleet"), dict) else {}
    succ = fleet.get("successor")
    succ_slug = succ.get("slug") if isinstance(succ, dict) else None
    fh, wk = wins.get("five_hour"), wins.get("seven_day")
    return (
        f"QUOTA: {act.get('slug') or '—'} · 5h {_pct(fh)} ({_forecast(fh)}) · "
        f"weekly {_pct(wk)} ({_forecast(wk)}) · Fable {_pct(wins.get('fable'))} · "
        f"band {band or '?'} · successor {succ_slug or 'none'}"
    )


def _unavailable(reason: str) -> str:
    """⚠️ Says the posture could not be READ — never that quota is fine."""
    return f"QUOTA: posture unavailable ({reason}) — {_REMEDY}"


# ── the session's model ────────────────────────────────────────────────────────────


def _session_model(transcript_path: object) -> str | None:
    """The model of the LAST assistant entry, from the transcript's final 64 KiB.

    The hook payload carries NO model (the live hooks reference, 2026-09-16: only
    SessionStart names one, and only optionally), and a hook on the tool path may not
    read a multi-megabyte transcript whole — so the read is bounded and a 2 MiB
    transcript costs what a 2 KiB one does. No match, an unreadable file, or no path is
    UNKNOWN, and unknown never bands on Fable.
    """
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            tail = fh.read().decode("utf-8", "ignore")
    except (OSError, ValueError):
        return None
    lines = tail.splitlines()
    # the first line is dropped ONLY when the read was actually truncated, because that is the one
    # the slice cut in half. Dropping it unconditionally threw away the whole transcript whenever
    # the file fit inside the window — which is every short session, and every test fixture.
    if size > _TAIL_BYTES:
        lines = lines[1:]
    # ⚠️ The LAST ASSISTANT ENTRY, scanned line-wise — not the last `"model"` string anywhere in the
    # tail. A structured tool result following the final assistant turn can carry a `model` field of
    # its own (a subagent's, say), and the substring version picked it up: an Opus session whose
    # last tool result mentioned a Fable model was banded on the Fable window and could be DENIED at
    # RED on a window that does not bind it.
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("type") == "assistant":
            msg = entry.get("message")
            model = msg.get("model") if isinstance(msg, dict) else None
            return model if isinstance(model, str) else None
    return None


def _band_for_session(posture: dict, transcript_path: object) -> tuple[str | None, bool]:
    """``(band, is_fable)`` for THIS session: on a Fable model the Fable window joins the
    hottest-of, so ``band_fable`` governs; on any other model, or an unknown one, the
    plain ``band`` does. The LINE shows the Fable figure either way.

    The flag is returned rather than re-inferred downstream, because the obvious inference —
    comparing the two bands — is always true at RED and named the wrong window in every deny.
    """
    act = posture.get("active") if isinstance(posture.get("active"), dict) else {}
    band = act.get("band")
    model = _session_model(transcript_path)
    # ⚠️ The prefix is grounded, not guessed, and the two sides of this system identify Fable from
    # DIFFERENT sources, which is why it is worth writing down. The POSTURE names the window from
    # the usage API's `scope.model.display_name == "Fable"`; the SESSION names its model from the
    # transcript's `"model"` field, which carries the API model id — `claude-fable-5-1` for Fable
    # 5.1, beside `claude-opus-5`, `claude-sonnet-5` and `claude-haiku-4-5-20251001`. The prefix
    # match covers the whole family, so a point release does not silently stop banding. If the id
    # scheme ever changes, this branch goes quiet rather than wrong: an unrecognised model keeps the
    # plain band, so the failure direction is a Fable session under-banded, never anything
    # over-held.
    if isinstance(model, str) and model.startswith("claude-fable"):
        fb = act.get("band_fable")
        if isinstance(fb, str):
            return fb, True
    return (band if isinstance(band, str) else None), False


# ── the RED predicate ──────────────────────────────────────────────────────────────

_SEPARATORS = re.compile(r"[;&|\n]+")


def _has_live_run(sid: object) -> bool:
    """True when this session has a run record that is READABLE and says ``running``.

    An unreadable record is not a live run here. The caller only ever uses this to ALLOW, so False
    is the conservative direction — and a session held at RED can clear it by starting (or
    repairing) its own run record, which the review family is permitted to do. ⚠️ That last clause
    was FALSE as shipped: a quoted ``--command 'fabrik-review'`` read as an unnamed start and was
    denied, so the escape the sentence promised did not exist for anyone who quotes their arguments.

    ⚠️ A record has to be live, not merely present. `final_gate_stop.py` applies a 12 h staleness
    bound to the same file and this reader applied none, so a crashed session's abandoned `running`
    record licensed unlimited fan-out at RED forever. The same bound is applied here, from the same
    reasoning: a record nobody has touched in half a day is not a session in flight.
    """
    if not isinstance(sid, str) or not sid:
        return False
    p = _state_dir() / f"{_safe_sid(sid)}.json"
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("state") != "running":
            return False
        return (time.time() - p.stat().st_mtime) <= _RUN_RECORD_STALE_S
    except (*_READ_ERRORS, AttributeError):
        return False


def _is_new_run_start(command: object) -> tuple[bool, str | None]:
    """``(True, name)`` when this Bash command STARTS a fresh run record.

    ⚠️ TOKENISED with ``shlex``, never matched as a substring, and the review that forced this
    rewrite found three HIGH defects in the regex version — all of them in the direction that
    matters, because this predicate is the only thing standing between RED and a fresh fan-out:

    * a QUOTED script path (``python3 "…/command_run.py" start``) failed the whitespace-after-`.py`
      match, so the hold VANISHED and any new run started at RED;
    * a QUOTED ``--command 'fabrik-review'`` fell outside the value class, so the name read as
      ``None`` and the review family — the one start RED must allow — was DENIED;
    * the regex took the FIRST ``--command`` while ``command_run.py``'s argparse takes the LAST, so
      a decoy ``--command fabrik-review`` in front of the real one allowed anything.

    And a substring match had no command position at all, so ``git commit -m "ran command_run.py
    start …"`` was denied — a COMMIT, which is exactly what RED mandates. Tokenising fixes that for
    free: the phrase inside a quoted argument is ONE token and matches nothing.

    Every legitimate spelling still lands, now by construction rather than by hope: a bare
    invocation, a ``uv run`` prefix, an env assignment, a ``cd … &&`` chain, an absolute or quoted
    path, reordered flags, ``--command=name``. Each of those is a case in the graders' corpus, which
    is the only reason that sentence is worth anything — the previous version made the same claim
    and three of the cases in it were false.

    FAIL-CLOSED on what cannot be read: an unparseable line that mentions the script is treated as
    an unnamed start and denied. A hold that gives up on the hard cases is not a hold.
    """
    if not isinstance(command, str) or "command_run.py" not in command:
        return False, None
    starts, names = 0, []
    for segment in _SEPARATORS.split(command):
        try:
            tokens = shlex.split(segment, comments=False)
        except ValueError:
            if "command_run.py" in segment:
                return True, None  # unreadable and it names the script ⇒ unnamed start ⇒ denied
            continue
        for i, tok in enumerate(tokens):
            if tok.rsplit("/", 1)[-1] == "command_run.py" and tokens[i + 1 : i + 2] == ["start"]:
                starts += 1
            if tok == "--command" and i + 1 < len(tokens):
                names.append(tokens[i + 1])
            elif tok.startswith("--command="):
                names.append(tok.split("=", 1)[1])
    if not starts:
        return False, None
    if starts > 1:
        # two starts on one line cannot be blessed by one name; judged as unnamed, so denied
        return True, None
    # argparse resolves a repeated flag to the LAST occurrence, so the hold must read it the same
    # way — reading the first is what let a decoy through
    return True, (names[-1] if names else None)


def decide(
    band: str | None, tool: str, command: object, *, sid: object, stamp: bool
) -> tuple[str, str]:
    """``("deny"|"notice"|"pass", what)`` — PURE, so the graders drive it directly.

    The stamp wins BEFORE the band: while the fleet-exhausted stamp stands the WALL is
    ``quota_stop.py``'s alone and this hook says nothing.
    """
    if stamp or band == "WALL":
        return "pass", ""
    if band == "RED":
        if tool == "Agent" and not _has_live_run(sid):
            return "deny", "The Agent tool"
        is_start, name = _is_new_run_start(command)
        if tool == "Bash" and is_start and name not in REVIEW_FAMILY:
            return "deny", f"Starting /{name or '<unnamed>'}"
        return "pass", ""
    if band == "AMBER":
        return "notice", ""
    return "pass", ""


def _deny_reason(posture: dict, band: str, what: str, *, is_fable: bool = False) -> str:
    """The operator-facing evidence for a hold, so the window it names has to be the one that binds.

    ⚠️ It used to infer Fable-ness by comparing `band == band_fable`, which is ALWAYS true at RED:
    `band_fable` is the hottest INCLUDING Fable, so whenever the plain band is RED the Fable one is
    too. Every RED deny therefore reported the Fable window, to Opus and Sonnet sessions alike — a
    window that does not bind them. The caller already knows the model, so it says so.
    """
    act = posture.get("active") if isinstance(posture.get("active"), dict) else {}
    wins = act.get("windows") if isinstance(act.get("windows"), dict) else {}
    hot = act.get("hottest_fable") if is_fable else act.get("hottest")
    w = wins.get(hot) if isinstance(hot, str) else None
    return (
        f"QUOTA {band} on {act.get('slug') or 'the active account'} — "
        f"{hot or 'the hottest window'} {_pct(w)} ({_forecast(w)}). {what} starts NEW work, and at "
        f"RED the only path is finish, commit, push, close your run record. Every tool a checkpoint "
        f"needs is allowed, and so is the review of the change you are checkpointing. {_REMEDY} — "
        f"it is the authority on when you resume, not this line's forecast."
    )


def _clear_said(sid: object) -> None:
    """Drop this session's AMBER marker, called on any band that is not AMBER.

    ⚠️ Two jobs, one line. A session that went AMBER, dropped to RED and came back to AMBER was
    never told again, because the marker only ever accumulated. And nothing pruned these files: one
    per session per band, forever, in the state dir the tick reads, with no owner — the plan called
    for a prune in the tick and there wasn't one. Clearing on the band change is better than a
    timed prune, because it is exactly when the fact stops being true.
    """
    if not isinstance(sid, str) or not sid:
        return
    try:
        (_rotate_state_dir() / f"quota-posture-said-{_safe_sid(sid)}-AMBER").unlink()
    except OSError:
        pass  # absent is the normal case; unreadable is not worth a word on the tool path


def _said_already(sid: object, band: str) -> bool:
    """True when this (session, band) already heard the notice.

    The marker is CREATED by the asking, exclusively, so the check and the claim cannot
    disagree and two concurrent tool calls cannot both decide they are first.
    """
    if not isinstance(sid, str) or not sid:
        return False
    p = _rotate_state_dir() / f"quota-posture-said-{_safe_sid(sid)}-{band}"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return True
    except OSError:
        return True  # cannot record it ⇒ do not repeat it on every call
    os.close(fd)
    return False


# ── the installer ──────────────────────────────────────────────────────────────────

_EVENTS = ("UserPromptSubmit", "PreToolUse")
_HOOK_PATH = "/opt/fabrik/scripts/sysadmin/quota_posture_hook.py"
_BASENAME = "quota_posture_hook.py"


def settings_files() -> list[Path]:
    """The user-level settings files this hook is wired into: one per account dir, plus
    the top-level one.

    ⚠️ The fleet root's ``active`` entry is a SYMLINK to whichever account is current.
    Including it would wire ONE account twice and take a second backup of an
    already-edited file, so symlinked dirs are excluded exactly as
    ``claude_rotate._fleet_dirs`` excludes them.
    """
    raw = os.environ.get("QUOTA_POSTURE_SETTINGS")
    if raw:
        # de-duplicated: a repeated path would inflate `--check`'s own denominator ("0 of 2" for one
        # real file) and print one file's verdict twice, which is the count-without-its-denominator
        # defect this repo's contract names, committed by the thing that reports counts.
        return [Path(p) for p in dict.fromkeys(x for x in raw.split(os.pathsep) if x)]
    out = [Path.home() / ".claude" / "settings.json"]
    try:
        root = Path.home() / ".claude-fleet"
        out += sorted(
            d / "settings.json" for d in root.iterdir() if d.is_dir() and not d.is_symlink()
        )
    except OSError:
        pass
    return out


def _is_wired(cfg: dict, event: str) -> bool:
    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict):
        return False
    lst = hooks.get(event)
    return _BASENAME in json.dumps(lst) if isinstance(lst, list) else False


def check(paths: list[Path]) -> list[tuple[Path, str]]:
    out = []
    for p in paths:
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            out.append((p, "MISSING (no settings file)"))
            continue
        except _READ_ERRORS:
            out.append((p, "MISSING (unreadable)"))
            continue
        if not isinstance(cfg, dict):
            out.append((p, "MISSING (not a JSON object)"))
            continue
        absent = [e for e in _EVENTS if not _is_wired(cfg, e)]
        out.append((p, "OK" if not absent else f"MISSING ({', '.join(absent)})"))
    return out


def install(paths: list[Path]) -> list[tuple[Path, str]]:
    """Add one entry per event to each file, idempotently, preserving every other key.

    ⚠️ The files are INDEPENDENT — two of them carry a deliberately different ``model``
    key — so nothing here copies one over another: each is read, amended and written in
    place, backed up beside itself before its first modification.
    """
    out = []
    for p in paths:
        try:
            cfg = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except _READ_ERRORS:
            out.append((p, "SKIPPED (unreadable — not overwritten)"))
            continue
        if not isinstance(cfg, dict) or not isinstance(cfg.setdefault("hooks", {}), dict):
            out.append((p, "SKIPPED (not the expected shape — not overwritten)"))
            continue
        hooks = cfg["hooks"]
        added, blocked = [], []
        for event in _EVENTS:
            if _is_wired(cfg, event):
                continue
            # ⚠️ `setdefault` returns the EXISTING value when the key is present, so an event key
            # holding a non-list used to fall through this guard, skip the event WITHOUT recording
            # it, and let the file report `OK (already wired)` forever while `check()` said MISSING.
            # A verdict that says OK about something it did not fix is worse than a crash: the
            # operator has no reason to look again. Say it instead, and never rewrite their value.
            if event in hooks and not isinstance(hooks[event], list):
                blocked.append(event)
                continue
            lst = hooks.setdefault(event, [])
            if not isinstance(lst, list):
                blocked.append(event)
                continue
            lst.append(
                {"hooks": [{"type": "command", "command": f"python3 {_HOOK_PATH}", "timeout": 10}]}
            )
            added.append(event)
        if blocked and not added:
            out.append((p, f"SKIPPED ({', '.join(blocked)} is not a list — not overwritten)"))
            continue
        if not added:
            out.append((p, "OK (already wired)"))
            continue
        try:
            if p.exists():
                # ⚠️ pid-qualified like the staging name below, and for a stronger reason: two
                # installs of one file inside the same wall-clock second used to overwrite each
                # other's backup, and this backup is the ONLY undo this installer offers.
                stamp = time.strftime("%Y%m%d-%H%M%S")
                shutil.copy2(p, p.with_name(p.name + f".backup.{stamp}.{os.getpid()}"))
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, p)
        except OSError as exc:
            out.append((p, f"FAILED ({type(exc).__name__})"))
            continue
        verdict = f"WIRED ({', '.join(added)})"
        if blocked:
            verdict += f" · SKIPPED {', '.join(blocked)} (not a list)"
        out.append((p, verdict))
    return out


# ── main ───────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--install" in argv or "--check" in argv:
        paths = settings_files()
        if "--install" in argv:
            for p, verdict in install(paths):
                print(f"{verdict:34s} {p}")
        if "--check" in argv:
            bad = 0
            for p, verdict in check(paths):
                print(f"{verdict:34s} {p}")
                bad += verdict != "OK"
            print(f"{bad} of {len(paths)} settings file(s) not wired")
            return 1 if bad else 0
        return 0

    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # unreadable payload — never block on our own defect
    if not isinstance(payload, dict):
        return 0  # a non-object payload is not ours to judge
    event = payload.get("hook_event_name")
    now = time.time()
    posture, reason = _load_posture(now)

    if event == "UserPromptSubmit":
        if posture is None:
            print(_unavailable(reason))
        else:
            band, _is_fable = _band_for_session(posture, payload.get("transcript_path"))
            print(_format_line(posture, band))
        return 0

    if event != "PreToolUse":
        return 0

    # ⚠️ the stamp is read BEFORE the band, so a lagging RED posture can never produce a
    # second deny for a call `quota_stop.py` is already denying
    if _stamp_exists() or posture is None:
        return 0
    band, is_fable = _band_for_session(posture, payload.get("transcript_path"))
    tool = str(payload.get("tool_name") or "")
    ti = payload.get("tool_input")
    command = ti.get("command") if isinstance(ti, dict) else None
    sid = payload.get("session_id")
    action, what = decide(band, tool, command, sid=sid, stamp=False)
    # ⚠️ Any band that is NOT amber clears this session's amber marker, which does two jobs with one
    # line: a session that drops to RED and comes back to AMBER hears it again (it never did), and
    # the markers stop accumulating in the state dir with nobody to prune them.
    if band != "AMBER":
        _clear_said(sid)
    if action == "deny":
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": _deny_reason(
                            posture, band or "RED", what, is_fable=is_fable
                        ),
                    }
                }
            )
        )
    elif action == "notice" and not _said_already(sid, band or "AMBER"):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": _format_line(posture, band)
                        + " — AMBER: finish what you started, start nothing heavy.",
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
