#!/usr/bin/env python3
# AFTER-EDIT: CLAUDE.md | templates/governance/CLAUDE.md | docs/reference/command-run-protocol.md | .claude/hooks/final_gate_stop.py | commands/_sources/fabrik-review.md | commands/_sources/fabrik-docs-review.md | commands/_sources/fabrik-execute-plan.md
"""COMMAND RUN-RECORD — the in-flight state of the `/fabrik-*` command an agent is running.

Three operator complaints, one record:
1. "reviews are still taking 30 rounds"      → the persistent CLASS LEDGER + the
   non-convergence detector (a converging loop's findings trend DOWN; an oscillating
   one is RE-SCOPING each round instead of RE-SWEEPING a fixed ledger).
2. "i want to see each commands status pinned in each agents reply"
                                             → `line`, the one-line pinned status.
3. "agents are still stopping without ... fully executing the commands"
                                             → the record is the Stop hook's FIFTH
   cause: a `running` record BLOCKS the stop (`.claude/hooks/final_gate_stop.py`).

ONE json per session at ``$COMMAND_RUN_DIR`` (default ``~/.claude/state/command-runs``),
named ``<session_id>.json``; the session id comes from ``--session``, ``CLAUDE_SESSION_ID``,
or ``CLAUDE_CODE_SESSION_ID`` (the harness exports the latter to Bash-tool shells; the Stop
hook keys on the same uuid from its payload, so records and hook lookups agree).

Fail-soft EVERYWHERE: a corrupt or unwritable record must never wedge an agent, and
``line``/``status`` never raise — they go silent instead. The Stop hook's matching
fail direction is deliberate and asymmetric: only a record that positively says
``running`` blocks; missing/corrupt/stale fails OPEN.

Every MUTATION also appends one kaizen event (``run_open``/``phase``/``round``/
``run_close``) — see § events below. The events are strictly ADDITIVE: they are emitted
after ``save()`` returns, OUTSIDE the record lock, each call wrapped, so a broken emitter
can never abort or corrupt a record mutation. The flush sits in a ``finally``, so an
ordinary exception anywhere in a verb's post-save tail cannot silently drop the event for
a mutation that already landed on disk. What is NOT covered — and is ACCEPTED as fail-open
telemetry rather than papered over — is a ``BaseException`` escape or an outright process
death (``SIGKILL``, OOM) between ``save()`` and the append: the record moves and the
stream does not. That residue belongs to the collector's hole metric, which counts
mutations with no matching event; hiding it behind a signal handler would trade a
measurable gap for an unmeasurable one.

Subcommands:
  start --command <name> --phases <N> [--terminal "<condition>"]
  step --phase <N> [--title "<t>"]
  round [--findings <N>] [--classes-swept a,b] [--classes-new c,d]
  done --command <name> --evidence "<proof>" | blocked --command <name> --reason "<case>"
  line     — the pinned status line (silent when no run is active)
  status --json
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Rounds needed before the oscillation heuristic may speak at all — below this a
# rising count is just an early loop widening its net, not a pathology.
NON_CONVERGENCE_MIN_ROUNDS = 5
# How many trailing findings counts must be non-increasing to look convergent.
CONVERGENCE_WINDOW = 3
# Bound on how much of one session's event file the sid join reads — the join is a
# best-effort fallback, never a reason to slurp a long-lived session's whole stream. It is
# read from the TAIL: a head-bounded scan hides exactly the sessions that have been busiest
# in this cwd, and a hidden candidate does not merely cost an adoption — it removes the
# second candidate that would have forced a REFUSAL, turning ambiguity into a confident
# wrong answer.
JOIN_TAIL_BYTES = 512 * 1024
# The exposure probe shells out to git. The flush runs after the mutation is already
# durable, so waiting buys nothing: take `unknown` over latency on an agent's hot path.
JOIN_PROBE_TIMEOUT_S = 2.0


def _state_dir() -> Path:
    raw = os.environ.get("COMMAND_RUN_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "state" / "command-runs"


def _session_id(explicit: str | None) -> str:
    """Explicit → CLAUDE_SESSION_ID → CLAUDE_CODE_SESSION_ID → the literal nosession.

    Bash-tool shells carry an EMPTY ``CLAUDE_SESSION_ID`` but DO carry the harness's
    ``CLAUDE_CODE_SESSION_ID`` (the real session uuid — the same id the Stop hook keys
    its record lookup on from its stdin payload). Before this chain existed, every
    concurrent session in a repo resolved to ONE ``nosession.json``: sibling ``start``
    calls clobbered each other's live records, ``line`` pinned a sibling's run, and a
    retried ``done`` could close a run it never opened (observed live three times,
    2026-08-20). ``nosession`` remains only for environments carrying neither var.
    """
    return (
        explicit
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("CLAUDE_CODE_SESSION_ID")
        or _nosession_key()
    )


def _nosession_key() -> str:
    """The last-resort key, scoped to the REPO — never the bare literal.

    The state dir is GLOBAL (``~/.claude/state/command-runs``) and the record is keyed on
    the session id alone, so a bare ``nosession`` meant every id-less session on the BOX —
    in any repo — merged into one file. Reported nine times by six senders
    (web-ecommerce-factory x3, tryton-crm x2, fleet, infra, trade-intelligence) between
    2026-08-16 and 08-20, escalating: tryton-crm watched its own ``step --phase 5`` land
    inside another repo's 4-phase record, and ``done`` was then correctly refused because
    the live record named a command it had never run — so the run could not be closed at
    all. ``repo_root`` was already stored INSIDE the record, which made the corruption
    visible but never prevented it.

    Scoping by repo kills the cross-repo case, which is the whole of the reported harm. Two
    id-less sessions in the SAME repo still share a record: there is nothing further to key
    on, and a per-process key would make the record unfindable by the Stop hook, which looks
    the uuid up from its own payload. A run with no id is already invisible to that hook, so
    this changes nothing about which records it can block on.
    """
    root = _repo_root()
    slug = "".join(c if (c.isalnum() or c in "-_") else "_" for c in Path(root).name)
    return f"nosession-{slug}" if slug else "nosession"


def _safe_sid(sid: str) -> str:
    """A filename-safe session id that NEVER collides with a different raw id.

    Flattening alone mapped `abc.xyz` and `abc xyz` onto one `abc_xyz` file, so an
    innocent session inherited (and was blocked by) another's run. When flattening
    changed anything, a short digest of the RAW id is appended — distinct raw ids
    therefore always get distinct files. Ordinary uuid-shaped ids are unchanged, so
    no existing record is renamed. ⚠️ `.claude/hooks/final_gate_stop.py` carries a
    byte-identical copy (it must not import this module — see its comment); the
    agreement is pinned by ``test_hook_and_script_agree_on_every_record_filename``.
    """
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)
    if not safe:
        return "nosession"
    if safe != sid:
        # blake2s, not sha1: this is a collision-avoidance tag, not a security hash,
        # and blake2s keeps bandit's B324 quiet without an ignore comment.
        safe += "-" + hashlib.blake2s(sid.encode("utf-8", "replace"), digest_size=4).hexdigest()
    return safe


def _record_path(sid: str) -> Path:
    return _state_dir() / f"{_safe_sid(sid)}.json"


@contextlib.contextmanager
def _record_lock(sid: str) -> Iterator[None]:
    """Exclusive flock held across the whole READ-MODIFY-WRITE of a mutating subcommand.

    Subagents routinely inherit the parent's ``CLAUDE_SESSION_ID``, so concurrent
    `round` calls hit one file: unlocked, 20 concurrent class-opens lost 14 (measured).
    A silently dropped class is a review reading CLEAN while a class was never swept —
    exactly the integrity the ledger exists to provide. Same `fcntl.flock` idiom as
    `claude_rotate.py`'s assignments lock; `line`/`status` stay lock-free readers.

    Fail-soft: if the lock cannot be taken (unwritable dir, no fcntl), the body still
    runs unserialized rather than wedging the agent — `save()` fails soft the same way.
    """
    fd: int | None = None
    try:
        lock = _record_path(sid).with_suffix(".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            fd = None
    try:
        yield
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass


def load(sid: str) -> dict[str, Any]:
    """The session's record, or {} — never raises (missing/corrupt/unreadable → {})."""
    try:
        data = json.loads(_record_path(sid).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save(sid: str, rec: dict[str, Any]) -> bool:
    """Atomically persist ``rec``. Returns False (never raises) on any I/O problem."""
    try:
        path = _record_path(sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception as e:
        sys.stderr.write(f"[command_run] state not persisted ({e}) — continuing.\n")
        return False


# Sentinels an agent reaches for to mean "nothing here". Without this they were recorded as
# LITERAL class names: a genuinely clean round passing `--classes-new "none"` produced
# `classes open: …, none, …` — the sentinel itself sat in the open list forever, so the loop could
# never retire it and the ledger contradicted the round it was recording (youtube, 2026-08-28,
# reproduced twice in one session across two different commands). The empty string already meant
# "nothing"; these are the words people type when a flag looks like it wants a value.
_NOTHING_TOKENS = frozenset({"none", "none-yet", "none yet", "nothing", "n/a", "na", "-", "—", "0"})


def _csv(raw: str | None) -> list[str]:
    return [
        p.strip()
        for p in (raw or "").split(",")
        if p.strip() and p.strip().casefold() not in _NOTHING_TOKENS
    ]


def pinned_line(rec: dict[str, Any]) -> str:
    """The pinned status line, or "" when no run is active.

    Format (all segments present):
      ``RUN: /<command> · phase <c>/<t> (<title>) · round <r> · terminal: <condition>``
    A segment whose data does not exist yet is omitted rather than filled with a
    placeholder — `round` before the first round, `(title)` before the first `step`
    that names one, `terminal:` when the command declared no terminal condition.
    """
    if not rec or rec.get("state") != "running":
        return ""
    cmd = rec.get("command") or "?"
    cur = rec.get("phase") or 1
    total = rec.get("phases") or "?"
    out = f"RUN: /{cmd} · phase {cur}/{total}"
    title = (rec.get("phase_title") or "").strip()
    if title:
        out += f" ({title})"
    rounds = rec.get("rounds") or []
    if rounds:
        out += f" · round {len(rounds)}"
    terminal = (rec.get("terminal") or "").strip()
    if terminal:
        out += f" · terminal: {terminal}"
    return out


# Commands whose rounds are PER-UNIT, not per-sweep. `/fabrik-execute-plan` in DISPATCHER mode runs
# N independent per-ticket review loops — round 4 is T11's review, round 5 is T08's — so a 0 followed
# by a 10 is "the previous ticket converged clean and the next ticket's first review found ten
# things", not oscillation. The detector's model (one brief, re-swept until dry) is correct for
# /fabrik-review and the gate commands and structurally wrong here; it fired on a healthy transdoc
# run (2026-08-28), named a specific wrong cause, and instructed a fix that did not apply. A loud
# advisory that is confidently wrong costs more than silence, because an agent that believes it
# starts re-scoping a loop that was converging.
PER_UNIT_ROUND_COMMANDS = frozenset({"fabrik-execute-plan"})


def convergence_warning(series: list[int], command: str = "") -> str:
    """Advisory oscillation diagnosis, or "" — NEVER blocks (a heuristic must not trap).

    A converging loop trends DOWN (5 → 3 → 0). A pathological one oscillates
    (43 → 11 → 30 → 13 → 22) because each round RE-SCOPES instead of RE-SWEEPING
    the persisted class ledger.
    """
    if str(command or "").strip().lower() in PER_UNIT_ROUND_COMMANDS:
        return ""  # per-unit rounds: consecutive counts describe different surfaces
    if len(series) < NON_CONVERGENCE_MIN_ROUNDS or len(series) < CONVERGENCE_WINDOW:
        return ""
    window = series[-CONVERGENCE_WINDOW:]
    if all(a >= b for a, b in zip(window, window[1:], strict=False)):
        return ""  # still non-increasing — converging, say nothing
    arrow = " → ".join(str(n) for n in window)
    full = " → ".join(str(n) for n in series)
    return (
        f"\n⚠️  NON-CONVERGENCE — findings are OSCILLATING: {arrow} "
        f"(round {len(series)}; full series: {full}).\n"
        "    Diagnosis: the loop is RE-SCOPING each round — inventing a fresh brief — "
        "instead of RE-SWEEPING the persisted class ledger.\n"
        "    Fix: re-sweep EVERY known class with the SAME brief (see `status --json` "
        "→ classes). A round that changes the question cannot converge; a round that "
        "repeats the question can.\n"
        "    (Advisory only — nothing is blocked.)"
    )


def _round_report(rec: dict[str, Any]) -> str:
    rounds = rec.get("rounds") or []
    classes: dict[str, str] = rec.get("classes") or {}
    last = rounds[-1] if rounds else {}
    open_c = sorted(k for k, v in classes.items() if v != "clean")
    clean_c = sorted(k for k, v in classes.items() if v == "clean")
    lines = [
        f"ROUND {len(rounds)} recorded · findings: {last.get('findings', 0)} "
        f"· classes open: {', '.join(open_c) or 'none'} "
        f"· clean: {', '.join(clean_c) or 'none'}"
    ]
    terminal = bool(classes) and not open_c and int(last.get("findings", 0)) == 0
    if terminal:
        lines.append(
            f"✅ TERMINAL VERDICT — round {len(rounds)} swept every known class "
            f"({', '.join(clean_c)}) clean and found 0 new findings. This IS the no-op "
            "round the contract demands. Close the run: "
            f"python3 scripts/command_run.py done --command {rec.get('command') or '<name>'} "
            '--evidence "<proof>" --feedback "<what you filed, to whom | none — surfaces swept>"'
        )
        # A terminal round CLOSES the loop — never also scold it for oscillating. The
        # drop TO zero is what non-increasing was asking for; the series test alone
        # reads `13 → 22 → 0` as a rise (live smoke, 2026-08-16).
        return "\n".join(lines)
    warn = convergence_warning(
        [int(r.get("findings", 0)) for r in rounds], str(rec.get("command") or "")
    )
    if warn:
        lines.append(warn)
    return "\n".join(lines)


PHASE_REVIEW_COMMANDS = frozenset({"fabrik-execute-plan"})


def _phase_review_exists(root: str, phase: int) -> bool:
    """Is there a review artifact for ``phase`` under docs/development/reviews/?

    transdoc finding 1.1 (2026-08-23), the highest-damage item in their report:
    `/fabrik-execute-plan` requires every phase boundary to reach `/fabrik-review`'s
    coverage-adjudicated exit, and `check_review_coverage.py`'s subject is the
    DIRECTORY ``docs/development/reviews/``. A per-phase review emitted nothing
    there, so at all 17 of their plan's phase boundaries the gate had NO SUBJECT
    and passed. 71 defects reached the first real gate — including a missing
    ``jobs.updated_at`` that meant no job could ever be claimed, i.e. the product's
    core pipeline was dead end to end while every gate said success.

    A contract clause with no mechanical binding is a suggestion. This is the
    binding: the artifact must EXIST before the next phase may open.

    Deliberately permissive about the NAME — projects date and slug their plans
    differently, and a rule that guesses the stem would fail honest runs. Any file
    under the reviews dir mentioning this phase counts; the gate then judges its
    CONTENT. We bind existence here, not quality: quality is check_review_coverage's
    job, and it can finally do it because it now has a subject.
    """
    if not root:
        return False
    d = Path(root) / "docs" / "development" / "reviews"
    if not d.is_dir():
        return False
    # DELIMITED, not substring: `phase-1` is a prefix of `phase-10`, so a bare `in`
    # let a phase-10 review satisfy phase 1 — a project that reviews only its last
    # phase would sail through every earlier boundary (found by re-verification of
    # this very guard, 2026-08-23).
    # PHASE mode names artifacts `…phase-<N>…`; DISPATCHER mode (spine+ticket plan sets) mandates
    # `<plan>-T<id>-review.md` instead (/fabrik-execute-plan § D4) and its § Plan Status Tracking
    # says the phase-boundary bullet does NOT apply there. Accepting only the phase form made the
    # two contracts unsatisfiable together: an executor naming artifacts correctly per D4 could
    # never satisfy `step`, and one that satisfied `step` had misnamed them (transdoc, 2026-08-28).
    # A ticket artifact is evidence a review ran, which is all this gate binds.
    pat = re.compile(
        rf"(?:^|[^0-9a-z])p(?:hase)?[-_ ]?{phase}(?:[^0-9]|$)|-T\d{{2}}[a-z]?-review\.md$", re.I
    )
    try:
        for f in d.rglob("*.md"):
            if not f.is_file() or not pat.search(f.name):
                continue
            try:
                # NON-EMPTY: `touch` created a complete silent bypass. This still binds
                # existence, not quality — but an empty file is not even existence.
                if f.stat().st_size > 0:
                    return True
            except OSError:
                continue
    except OSError:
        return False  # unreadable → treat as absent; the refusal names how to waive
    return False


def _repo_root() -> str:
    """The toplevel of the repo the invoking shell is in at START time — "" if none."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except Exception:
        return ""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _touch(rec: dict[str, Any]) -> None:
    rec["updated_at"] = _now()
    rec["updated_ts"] = int(time.time())


# ── kaizen events ────────────────────────────────────────────────────────────────────
#
# The record is the Stop hook's fifth cause and this file is fleet-synced, so the event
# stream is bolted on the OUTSIDE of it: emitted after `save()` returns, outside the
# record lock, every call wrapped. A project that has not yet received `kaizen_events`
# — and a `kaizen_events` that raises on every call — must both behave exactly as this
# script did before events existed.

_EVENTS_UNSET: Any = object()
_events_mod: Any = _EVENTS_UNSET


def _kaizen() -> Any:
    """The kaizen emitter module, or ``None`` — imported LAZILY, exactly once, fail-open.

    The ``sys.path`` additions are ADDITIVE and IDEMPOTENT (appended, never inserted, and
    only when absent), so importing this module can never shadow a caller's own packages.
    """
    global _events_mod
    if _events_mod is _EVENTS_UNSET:
        _events_mod = None
        try:
            for extra in (
                str(Path(__file__).resolve().parent / "sysadmin"),
                "/opt/fabrik/scripts/sysadmin",
            ):
                if extra not in sys.path:
                    sys.path.append(extra)
            import kaizen_events

            _events_mod = kaizen_events
        except Exception:
            _events_mod = None
    return _events_mod


def _cwd() -> str:
    try:
        return str(Path.cwd().resolve())
    except OSError:
        return "unknown"


def _project_of(cwd: str) -> str:
    """``/opt/<name>``'s ``<name>`` — the same derivation ``kaizen_events.exposure`` uses."""
    parts = Path(cwd).parts
    return parts[2] if len(parts) >= 3 and parts[1] == "opt" else ""


def _parse_ts(raw: str) -> dt.datetime | None:
    """An AWARE datetime, or None. A naive timestamp is treated as unusable rather than
    assumed to be local — a wrong assumption here silently mis-windows the join."""
    try:
        parsed = dt.datetime.fromisoformat(raw.strip()) if raw.strip() else None
    except ValueError:
        return None
    return parsed if parsed and parsed.tzinfo is not None else None


def _names_cwd(row: dict[str, Any], cwd: str, project: str) -> bool:
    """Does this event name the directory this run is executing in?

    An event carrying an explicit ``cwd`` (``session_start``, and this script's own
    events) is matched EXACTLY — that is the precise key. Everything else is matched on
    ``exposure.project``, which is deliberately coarse: in a repo with three concurrent
    sessions it makes the join AMBIGUOUS, which is the honest answer.
    """
    raw = row.get("cwd")
    if isinstance(raw, str) and raw:
        return raw == cwd
    exp = row.get("exposure")
    return bool(project) and isinstance(exp, dict) and exp.get("project") == project


def _naming_sid(path: Path, cwd: str, project: str, anchor: dt.datetime | None) -> tuple[str, bool]:
    """``(sid, provable)`` for one session file, reading its TAIL.

    ``sid`` is the id of an event naming ``cwd`` inside the window, or "". ``provable`` is
    False when the file was larger than :data:`JOIN_TAIL_BYTES` and nothing matched — the
    absence of a match is then a fact about the WINDOW READ, not about the session, and
    the caller must not treat it as evidence.

    The tail is the right end to read: a session's newest events are the ones that can
    still be in this run's window, and the first partial line after the seek is discarded
    so a half-record is never parsed.
    """
    try:
        size = path.stat().st_size
        truncated = size > JOIN_TAIL_BYTES
        with open(path, encoding="utf-8", errors="replace") as fh:
            if truncated:
                fh.seek(size - JOIN_TAIL_BYTES)
                fh.readline()  # discard the partial line the seek landed inside
            for raw in fh:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue  # a torn line is dropped, never guessed at
                if not isinstance(row, dict) or not _names_cwd(row, cwd, project):
                    continue
                if anchor is not None:
                    ts = _parse_ts(str(row.get("ts") or ""))
                    if ts is None or ts < anchor:
                        continue
                sid = str(row.get("sid") or "").strip()
                return sid or path.stem, True
    except OSError:
        return "", True  # an unreadable file is not a hidden candidate, it is no candidate
    return "", not truncated


def _sid_from_events(started_at: str) -> tuple[str, str]:
    """``(sid, why)`` — DETERMINISTIC JOIN OR NOTHING; ``sid`` is "" when it refuses.

    A Bash-tool shell carries an EMPTY ``CLAUDE_SESSION_ID``, so every such invocation
    resolves to `nosession` and their events would pile into one unattributable bucket.
    This optional join recovers the real sid from the event stream — but only when the
    answer is unambiguous.

    The window is every event naming this cwd since THIS run's own start (the whole
    window, never a trailing N minutes: a sliding boundary can hide the second candidate
    and mis-adopt). The `start` verb has no run to anchor on — there is no such thing as
    "since a run that has not begun" — so its window is the whole store, and the anchor is
    never read off whatever record happens to be lying in the file: that would filter the
    store by a FINISHED run's clock and hide the older candidate whose presence is the only
    reason to refuse.

    EVERY unresolved shape resolves toward refusal:
    - two or more proven candidates → refuse (ambiguity is not a coin flip);
    - a session whose file is too long to prove absence over → refuse, because "no match in
      the last 512 KiB" is not "no match";
    - a session whose events carry a clock running BACKWARDS relative to the anchor → its
      events fall outside the window and it simply is not a candidate. That is accepted
      fail-safe: a skewed clock makes a session indistinguishable from one that never named
      this cwd, and the join has no second source of time to arbitrate with. It costs an
      adoption, never a wrong one.

    The ambiguity is not lost by refusing — it becomes visible in the `unknown` stream as
    N distinct cwds mutating one record, which is the measurement this feature exists for.
    """
    mod = _kaizen()
    if mod is None:
        return "", "kaizen_events unavailable"
    try:
        anchor = _parse_ts(started_at)
        cwd, project = _cwd(), _project_of(_cwd())
        skip = {"nosession", str(getattr(mod, "UNKNOWN", "unknown"))}
        found: set[str] = set()
        unprovable: list[str] = []
        for path in sorted(mod.events_dir().glob("*.jsonl")):
            if path.stem in skip:
                continue
            sid, provable = _naming_sid(path, cwd, project, anchor)
            if sid and sid not in skip:
                found.add(sid)
            elif not provable:
                unprovable.append(path.stem)
        if unprovable:
            return "", (
                f"{len(unprovable)} session(s) too long to prove absence over "
                f"({', '.join(sorted(unprovable)[:3])}) — refusing to guess"
            )
        if len(found) == 1:
            return found.pop(), "single candidate"
        if found:
            return "", f"{len(found)} sessions name {cwd} in this window — refusing to guess"
        return "", f"no event names {cwd} in this window"
    except Exception as e:  # the join is a convenience — it never breaks a mutation
        return "", f"join failed ({e})"


def _flush_events(args: argparse.Namespace, outbox: dict[str, Any]) -> None:
    """Emit the mutation's events. Runs with the record lock RELEASED and the save done."""
    events: list[tuple[str, dict[str, Any]]] = outbox.get("events") or []
    if not events:
        return
    mod = _kaizen()
    if mod is None:
        return
    # `--session` is passed through; a bare env id is left to the emitter to resolve so
    # it is labelled `env` and not laundered into `explicit`.
    explicit = (getattr(args, "session", None) or "").strip()
    # The FULL env chain, matching _session_id (round 105): gating the join on
    # CLAUDE_SESSION_ID alone made it fire in the COMMON Bash-shell case (empty legacy
    # var, populated CLAUDE_CODE_SESSION_ID) — the record landed under the real sid
    # while the event was join-attributed into a SIBLING session's stream, reopening
    # the cross-session collision one layer over (events vs record).
    env_sid = (
        os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID") or ""
    ).strip()
    sid: str | None = explicit or None
    # `None` = let the emitter resolve and label it (`env`); `"join"` = RECONSTRUCTED here,
    # which is neither explicit nor env and must never be reported as either.
    source: str | None = None
    if not explicit and not env_sid and getattr(args, "adopt_sid", False):
        adopted, why = _sid_from_events(str(outbox.get("started_at") or ""))
        if adopted:
            sid, source = adopted, "join"
        else:
            sys.stderr.write(f"[command_run] --adopt-sid: no join ({why}).\n")
    for event, fields in events:
        try:
            payload = dict(fields)
            payload["cwd"] = _cwd()
            mod.emit(event, sid, sid_source=source, probe_timeout_s=JOIN_PROBE_TIMEOUT_S, **payload)
        except Exception as e:
            sys.stderr.write(f"[command_run] event not emitted ({e}) — the record is unaffected.\n")


def _queue(
    rec: dict[str, Any], outbox: dict[str, Any], event: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Queue one event and stamp it ORDER-FAITHFUL and SELF-DESCRIBING. Flock HELD.

    ``seq`` comes from a per-session counter incremented on the record under the same lock
    that serializes the mutation, so it is dense and gap-free even when twenty subagents
    write at once. It has to exist because the alternatives do not order anything: ``ts``
    is millisecond-quantized (concurrent events collide) and file order is whatever the
    kernel interleaved. The collector orders by ``(command, seq)``.

    ``command`` names the run being mutated, so a line means something on its own — a
    nested `/fabrik-review` inside `/fabrik-execute-plan` is otherwise attributable only by
    replaying the whole stack, which the collector cannot do from a single line.

    Returns the queued field dict so the caller can stamp `persisted` once `save()` answers.
    The queue happens BEFORE the save: `main()` flushes in a `finally`, so an event that is
    already queued survives any failure in the tail.
    """
    seq = int(rec.get("event_seq") or 0) + 1
    rec["event_seq"] = seq
    stamped = dict(fields, seq=seq, command=rec.get("command") or "", persisted=False)
    outbox["events"].append((event, stamped))
    return stamped


def _evidence_hash(text: str) -> str:
    """A fingerprint of the closing evidence — the stream records THAT it was given, and
    whether it changed between retries, without copying an agent's prose into the store."""
    return hashlib.blake2s((text or "").encode("utf-8", "replace"), digest_size=8).hexdigest()


# The three hub beats a finding can be routed to (charters: docs/reference/agents/). Matched as
# whole words so "infrastructure" does not read as a route to `infra`.
_BEATS = ("infra", "fleet", "intel")

# Runs STARTED before this instant close without a verdict, exactly as they always could. They
# were dispatched under a contract that did not require one, and trapping a peer mid-run to
# enforce a rule it never read is the failure mode this whole mechanism exists to prevent.
# UTC, and the landing instant — not a rounded local date. Set to a midnight that had not yet
# arrived in UTC, this whole mechanism ships INERT for hours while reading as enforced; the
# end-to-end tests caught exactly that before it landed.
_FEEDBACK_REQUIRED_FROM = dt.datetime(2026, 8, 27, 21, 15, tzinfo=dt.UTC)


def _feedback_is_required(rec: dict[str, Any]) -> bool:
    """Does this record owe a `--feedback` verdict at close?

    Fails OPEN on every unreadable or missing timestamp. A record whose `started_at` cannot be
    parsed is old, corrupt, or written by a version that did not stamp it — none of which is
    evidence the agent owes anything, and all of which would otherwise wedge a close with no way
    out. The duty binds forward, never retroactively.
    """
    started = _parse_ts(str(rec.get("started_at") or ""))
    return started is not None and started >= _FEEDBACK_REQUIRED_FROM


def _feedback_verdict(text: str | None) -> tuple[str, list[str]]:
    """Classify the close-out FEEDBACK line into (verdict, beats).

    Three values, and the third is the load-bearing one:
      ``filed``     - something was routed to a beat.
      ``none``      - the agent looked and had nothing to file. A real answer.
      ``unstated``  - no --feedback was passed at all.

    ``unstated`` must never collapse into ``none``. If it did, the metric would report perfect
    diligence for a corpus nobody ever looked at - the fail-silent-green shape reproduced inside the
    very telemetry built to measure it. That distinction is the whole reason this field exists.
    """
    if text is None:
        return "unstated", []
    stripped = (text or "").strip()
    if not stripped:
        return "unstated", []
    low = stripped.lower()
    beats = [b for b in _BEATS if re.search(rf"\b{b}\b", low)]
    # A beat name is NOT by itself a filing. `close-feedback.md` instructs the agent to write
    # "none - <the surfaces this run exercised>", and those surfaces are routinely the beat names
    # themselves ("infra rules", "the fleet specs"). Matching a beat anywhere therefore read an
    # HONEST `none` as a filing, inflating compliance and under-counting the exact verdict the
    # metric exists to tell apart. A filing needs a filing VERB.
    # PAST TENSE only. `filed?` also matched the bare infinitive, so "nothing to FILE" read as a
    # filing — the negation of the sentence lost to one optional character. A verdict claims a
    # COMPLETED act or it is not a claim.
    filed_verb = re.search(r"\b(filed|sent|routed|mailed|raised|reported)\b", low) is not None
    if re.match(r"^(none|nothing|n/?a)\b", low) and not filed_verb:
        return "none", []
    if beats or filed_verb:
        return "filed", beats
    return ("filed" if len(stripped) > 3 else "none"), beats


def _build_parser() -> argparse.ArgumentParser:
    # ⚠️ NOT `--session-*`: argparse resolves abbreviations, so a second flag sharing the
    # `--sess` prefix makes the long-standing `--sess <id>` spelling AMBIGUOUS and every
    # caller using it starts exiting 2. The name is deliberately in a different namespace.
    join_help = (
        "when no session id resolves, adopt one from the kaizen event stream — ONLY if "
        "exactly one session provably named this cwd in the window (else refuse). Affects "
        "the EVENTS only; the record file is named as it always was."
    )
    ap = argparse.ArgumentParser(prog="command_run.py", description=__doc__)
    ap.add_argument("--session", help="session id (default: $CLAUDE_SESSION_ID)")
    ap.add_argument("--adopt-sid", action="store_true", help=join_help)

    # The session flags are accepted on EITHER side of the subcommand: argparse would
    # otherwise reject `round --adopt-sid`, which is the only spelling an agent naturally
    # reaches for. `SUPPRESS` keeps the subparser copy from resetting a value the
    # top-level parser already captured.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--session", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    common.add_argument(
        "--adopt-sid",
        action="store_true",
        default=argparse.SUPPRESS,
        help=join_help,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start", help="begin a command run", parents=[common])
    p.add_argument("--command", required=True, help="e.g. fabrik-review")
    p.add_argument("--phases", required=True, type=int)
    p.add_argument("--terminal", default="", help="the run's terminal condition")

    p = sub.add_parser("step", help="advance to a phase", parents=[common])
    p.add_argument(
        "--review-waived",
        metavar="REASON",
        help="advance without the previous phase's review artifact — RECORDED in the run record",
    )
    p.add_argument("--phase", required=True, type=int)
    p.add_argument("--title", default="")

    p = sub.add_parser("round", help="record one convergence round", parents=[common])
    p.add_argument("--findings", type=int, default=0)
    p.add_argument("--classes-swept", default="", help="comma-separated, swept CLEAN")
    p.add_argument("--classes-new", default="", help="comma-separated, newly opened")

    p = sub.add_parser("done", help="terminal: the contract is met", parents=[common])
    p.add_argument(
        "--command", required=True, help="the run you are closing — must be the LIVE one"
    )
    p.add_argument("--evidence", required=True)
    p.add_argument(
        "--feedback",
        default=None,
        help=(
            "the close-out FEEDBACK line: what you filed and to whom, or 'none' plus the "
            "surfaces you exercised. OMITTING it records `unstated`, which is NOT the same as "
            "`none` and is counted separately - see commands/_fragments/close-feedback.md"
        ),
    )

    p = sub.add_parser(
        "handoff",
        help="terminal: NOT-QUIET — the loop is quiet but rows stay OPEN, routed in a RESUME block",
        parents=[common],
    )
    p.add_argument(
        "--command", required=True, help="the run you are closing — must be the LIVE one"
    )
    p.add_argument(
        "--resume",
        required=True,
        help=(
            "path to the artifact carrying the open rows + the `## RESUME` block. REQUIRED: this "
            "close is only legitimate when the successor is named, which makes it strictly harder "
            "to fake than the BLOCKED cause agents were stretching to reach"
        ),
    )
    p.add_argument("--reason", required=True, help="why rows remain open")
    p.add_argument(
        "--feedback",
        default=None,
        help="the close-out FEEDBACK line — see commands/_fragments/close-feedback.md",
    )

    p = sub.add_parser(
        "blocked", help="terminal: one of the three sanctioned BLOCKED cases", parents=[common]
    )
    p.add_argument(
        "--command", required=True, help="the run you are closing — must be the LIVE one"
    )
    p.add_argument("--reason", required=True)
    p.add_argument(
        "--feedback",
        default=None,
        help=(
            "the close-out FEEDBACK line: what you filed and to whom, or 'none' plus the "
            "surfaces you exercised. OMITTING it records `unstated`, which is NOT the same as "
            "`none` and is counted separately - see commands/_fragments/close-feedback.md"
        ),
    )

    sub.add_parser("line", help="print the pinned status line (silent when idle)", parents=[common])
    p = sub.add_parser("status", help="print the record", parents=[common])
    p.add_argument("--json", action="store_true", default=True)
    return ap


def main(argv: list[str]) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as e:  # argparse's own exit — keep it, it is a usage error
        return int(e.code or 0)
    try:
        sid = _session_id(args.session)

        # Readers run lock-free: `line` is invoked on EVERY reply, so it must stay
        # cheap and must never wait behind a writer.
        if args.cmd == "line":
            line = pinned_line(load(sid))
            if line:
                print(line)
            return 0

        if args.cmd == "status":
            print(json.dumps(load(sid), indent=2))
            return 0

        # Every MUTATING subcommand loads, modifies and saves under one exclusive
        # flock — the read-modify-write is otherwise lossy under concurrent subagents.
        # Events are QUEUED under the lock and emitted after it drops: a sensor must
        # never hold the lock an agent's next mutation is waiting on, and must never sit
        # between a mutation and its `save()`. The flush is a `finally` because the queue
        # is filled BEFORE `save()` — so a bug anywhere in a verb's tail (a report
        # formatter, a print) cannot leave a persisted mutation with no event, which is a
        # disagreement between record and stream that nothing downstream can ever repair.
        outbox: dict[str, Any] = {"events": [], "started_at": ""}
        try:
            rc = 0
            with _record_lock(sid):
                rc = _mutate(sid, args, outbox)
        finally:
            _flush_events(args, outbox)
        return rc
    except Exception as e:  # fail-soft — a state bug must never wedge an agent
        sys.stderr.write(f"[command_run] error, continuing: {e}\n")
        return 0


def _mutate(sid: str, args: argparse.Namespace, outbox: dict[str, Any]) -> int:
    """The mutating subcommands. Runs with the record's flock HELD.

    Appends ``(event, fields)`` to ``outbox["events"]`` — it never EMITS, so no sensor
    failure can land between a mutation and its ``save()``.
    """
    rec = load(sid)
    outbox["started_at"] = rec.get("started_at") or ""

    if args.cmd == "start":
        parent = rec if rec.get("state") == "running" else None
        stack = list(rec.get("stack") or []) if parent else []
        if parent:
            # A nested command (/fabrik-execute-plan → /fabrik-review at a phase
            # boundary) must not ERASE its caller's record: park the parent and
            # restore it when the nested run terminates.
            parent = {k: v for k, v in parent.items() if k != "stack"}
            stack.append(parent)
        new = {
            "session_id": sid,
            "command": (args.command or "").lstrip("/"),
            "phases": max(1, args.phases),
            "phase": 1,
            "phase_title": "",
            "terminal": args.terminal,
            "state": "running",
            "started_at": _now(),
            # numeric epoch alongside the display string — round 33: the close parsed
            # started_at with its %z DROPPED and re-interpreted the wall clock in the CLOSE
            # process's timezone, shifting the run-binding window by whole hours across any
            # TZ/DST difference between the two processes
            "started_epoch": time.time(),
            # the repo the run REVIEWS, resolved once at start — round 31 reproduced the close
            # check running against whatever repo the shell happened to be cd'd into
            "repo_root": _repo_root(),
            "rounds": [],
            "classes": {},
            "stack": stack,
            # Session-monotonic, so a nested run and a later run keep ascending rather
            # than restarting at 1 and colliding in the same session's stream.
            "event_seq": int(rec.get("event_seq") or 0),
        }
        # The `start` verb's join window is the WHOLE store, so the anchor is cleared —
        # never this record's own start (that would exclude every candidate landing
        # microseconds earlier, and `started_at` is second-truncated so WHICH ones would
        # depend on the second boundary), and never the PREVIOUS record's start, which
        # would filter the store by a finished run's clock.
        outbox["started_at"] = ""
        fields = _queue(
            new,
            outbox,
            "run_open",
            {
                "phases": new["phases"],
                "terminal": new["terminal"],
                "nested": bool(stack),
            },
        )
        _touch(new)
        fields["persisted"] = save(sid, new)
        print(pinned_line(new))
        return 0

    if not rec:
        sys.stderr.write(
            "[command_run] no run record for this session — "
            "`start` one before step/round/done/blocked.\n"
        )
        return 0

    if args.cmd == "step":
        target = max(1, args.phase)
        # EVERY intermediate phase, not just the immediate predecessor: `step --phase 5`
        # from phase 1 only ever demanded phase 4's artifact, so 2 and 3 vanished
        # silently. Report the LOWEST unreviewed phase — that is the one to go back to.
        prev = next(
            (
                n
                for n in range(1, target)
                if not _phase_review_exists(str(rec.get("repo_root") or ""), n)
            ),
            0,
        )
        if prev >= 1 and str(rec.get("command") or "").strip().lower() in PHASE_REVIEW_COMMANDS:
            if args.review_waived:
                waived = list(rec.get("waived_reviews") or [])
                waived.append({"phase": prev, "reason": args.review_waived, "at": _now()})
                rec["waived_reviews"] = waived
                print(
                    f"command_run: phase {prev} review WAIVED — {args.review_waived} "
                    "(recorded in the run record; an escape that leaves no trace is how "
                    "this contract became unenforceable in the first place)",
                    file=sys.stderr,
                )
            else:
                print(
                    f"REFUSED — phase {prev} has no review artifact under "
                    "docs/development/reviews/, so there is nothing for the review gate to "
                    "read. Emit it as either shape: PHASE mode a filename containing "
                    f"`phase-{prev}`, DISPATCHER mode `<plan>-T<id>-review.md` "
                    "(/fabrik-execute-plan D4). Or re-run with "
                    '--review-waived "<reason>" to record a deliberate skip.',
                    file=sys.stderr,
                )
                return 2
        # A run that advances phases while recording ZERO rounds has a convergence loop nothing
        # can see: the oscillation/terminal advisories all key on `round`, so an agent that never
        # calls it gets silence and reads silence as approval. job-agent (2026-08-28) ran NINE
        # discovery rounds and recorded none of them, and found out only when a round-9 call
        # printed "ROUND 1 recorded" — nothing anywhere had noticed. Their own framing is the
        # argument: a convergence check that depends on a voluntary call from the very agent whose
        # judgement it exists to check is load-bearing on the wrong party. ADVISORY, not a refusal
        # — a one-shot command legitimately records no rounds, and trapping it would be worse than
        # the silence. Fires from phase 3 so a normal two-phase run stays quiet.
        if target >= 3 and not (rec.get("rounds") or []):
            sys.stderr.write(
                f"[command_run] NOTICE — /{rec.get('command') or '?'} is at phase {target} with "
                "ZERO rounds recorded. If this command has a convergence loop, every round "
                "advisory (oscillation, terminal verdict) has been silent because it never ran, "
                "not because the loop is healthy. Record them: `round --findings <n> "
                "--classes-swept <…> --classes-new <…>`.\n"
            )
        rec["phase"] = target
        rec["phase_title"] = args.title
        fields = _queue(rec, outbox, "phase", {"n": rec["phase"], "title": rec["phase_title"]})
        _touch(rec)
        fields["persisted"] = save(sid, rec)
        print(pinned_line(rec))
        return 0

    if args.cmd == "round":
        rounds = list(rec.get("rounds") or [])
        classes: dict[str, str] = dict(rec.get("classes") or {})
        swept, new_c = _csv(args.classes_swept), _csv(args.classes_new)
        # Sweep first, then open: a class both swept AND re-found this round is
        # OPEN — a round that turned up a new defect in it did not retire it.
        for name in swept:
            classes[name] = "clean"
        for name in new_c:
            classes[name] = "open"
        rounds.append(
            {"n": len(rounds) + 1, "findings": args.findings, "swept": swept, "new": new_c}
        )
        rec["rounds"], rec["classes"] = rounds, classes
        fields = _queue(
            rec,
            outbox,
            "round",
            {
                "n": len(rounds),
                "findings": args.findings,
                "classes_swept": swept,
                "classes_new": new_c,
                "classes_open": sorted(k for k, v in classes.items() if v != "clean"),
            },
        )
        _touch(rec)
        fields["persisted"] = save(sid, rec)
        print(_round_report(rec))
        return 0

    if args.cmd in ("done", "blocked", "handoff"):
        return _close(sid, rec, args, outbox)

    return 0


def _close(sid: str, rec: dict[str, Any], args: argparse.Namespace, outbox: dict[str, Any]) -> int:
    """`done` / `blocked` — close ONLY the run the caller NAMED. Flock held.

    Closing whatever happens to be live is how this design reintroduces the very
    defect it exists to prevent: after a nested /fabrik-review pops back to its
    caller, a retried or duplicated `done` would close /fabrik-execute-plan at
    phase 2/5 — the pinned line goes silent and the Stop hook never blocks again
    for the remaining phases. So the caller must name the run, and a name that is
    not the live one is REFUSED (rc 1) rather than applied to the wrong record.
    """
    live = rec.get("command") or "?"
    passed = (args.command or "").lstrip("/")
    state = rec.get("state")

    if state != "running":
        # Already closed — a retry, not an error. Never mutate; never resurrect.
        msg = (
            f"{args.cmd.upper()} — /{live} is already {state}; nothing to close (no-op). "
            "If a DIFFERENT run is live, close that one by name."
        )
        sys.stderr.write(f"[command_run] {msg}\n")
        print(msg)
        return 0

    if passed != live:
        msg = (
            f"REFUSED — you asked to close /{passed}, but the LIVE run is /{live} "
            f"(phase {rec.get('phase')}/{rec.get('phases')}). Closing the wrong record "
            "would silence the pinned line and disarm the Stop hook for the rest of "
            f"/{live}. Re-run with --command {live} if that is genuinely what you mean."
        )
        sys.stderr.write(f"[command_run] {msg}\n")
        print(msg)
        return 1

    if args.cmd == "done" and live in (
        "fabrik-review",
        "fabrik-repo-review",
        # round 135: these three persist to docs/development/reviews/ by their own
        # contracts, yet closed with NO artifact check at all — the round-29 hole verbatim,
        # three commands over
        "fabrik-user-test",
        "fabrik-service-test",
        "fab-mega-04-validate",
    ):
        # ARTIFACT-BY-FILESYSTEM, RUN-BOUND (rounds 29+31). Round 29 proved `done` accepted any
        # evidence STRING; the first fix then shipped green-by-accident (its own bundled ledger
        # edit satisfied it) and round 31 reproduced four more holes: no cwd pinning (a wrong
        # repo's dirt passed; a subdir invocation false-refused), deletions counted as artifacts,
        # any HEAD touch of reviews/ counted regardless of WHEN, and the check had no binding to
        # THIS run at all. Now: git runs in the repo recorded at START; only non-deleted *.md
        # count; a file must be modified at-or-after the run began (mtime), or HEAD must be a
        # commit from this run's window touching reviews/ (line-anchored, not substring).
        root = rec.get("repo_root") or None
        if root is None:
            # Round 33: `"" or None` silently fell back to the CLOSE process's cwd — the
            # wrong-repo hole reborn for any run started outside a git repo. Unverifiable
            # means REFUSE, not guess.
            msg = (
                f"REFUSED — this /{live} run has no repo_root on record (start ran outside a "
                "git repo, or the record predates the field), so its report cannot be "
                "verified. The ONLY exit is `blocked --command "
                f"{live} --reason rootless-record` — a fresh `start` NESTS under this record "
                "rather than replacing it (round 35: an operator following a 'restart' remedy "
                "closed the child, saw DONE, and the rootless parent kept blocking forever)."
            )
            sys.stderr.write(f"[command_run] {msg}\n")
            print(msg)
            return 1
        # mtime binding is DECLARATIVE evidence (adjudicated round 33): os.utime forgery is
        # trivial and out of scope on a single-operator box — this is self-discipline, not a
        # security boundary; the same residual class as BLOCKED-section sincerity.
        started_epoch = rec.get("started_epoch") or 0.0
        if not started_epoch:
            # legacy record without the numeric field: parse WITH the offset the string
            # carries (round 33: truncating %z re-interpreted the wall clock in the close
            # process's local zone — hours of drift either direction across TZ/DST)
            started = rec.get("started_at", "")
            try:
                t = time.strptime(started, "%Y-%m-%dT%H:%M:%S%z")
                started_epoch = calendar.timegm(t) - (t.tm_gmtoff or 0)
            except Exception:
                started_epoch = 0.0
        ok_artifact = None  # None = unverifiable (fail open); False = verified absent
        candidates: list[Path] = []
        try:
            porcelain = subprocess.run(
                [
                    "git",
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                    "--",
                    "docs/development/reviews/",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
                cwd=root,
            ).stdout
            ok_artifact = False
            for ln in porcelain.splitlines():
                if ln[:2].strip() == "D" or not ln[3:].strip().endswith(".md"):
                    continue
                if "archived/" in ln:
                    # round 137: re-filing an old report satisfied the floor — archived/
                    # is excluded everywhere the review grammars read; here too
                    continue
                f = Path(root or ".") / ln[3:].split(" -> ")[-1].strip().strip('"')
                if f.is_symlink():
                    # round 139: an untracked symlink named *.md pointing at ANY fresh
                    # unrelated file satisfied the floor with zero review content
                    continue
                if f.is_file() and f.stat().st_mtime >= started_epoch - 2:
                    ok_artifact = True
                    candidates.append(f)
            if ok_artifact is False:
                # Round 137 rebuilt this branch from three live-reproduced holes: (a) only
                # HEAD was inspected, so a report committed mid-run followed by ANY later
                # unrelated commit (CHANGELOG, lessons-learnt — the Completion Contract's
                # own EXIT sequence) false-REFUSED the close; (b) the gate accepted any
                # touch of the prefix while only candidates required .md, so a committed
                # screenshot satisfied the floor with candidates=[] and the content floor
                # never ran; (c) archived/ counted. Now: walk the run window's commits
                # (bounded), and the SAME filter — live .md outside archived/ — decides
                # both the gate and the candidates.
                try:
                    # round 139 rebuilt the walk's three seams: %at not %ct (rebase — the
                    # exit ladder's own `git pull --rebase` — rewrites committer time, so a
                    # STALE replayed leftover looked fresh; author time survives replay, and
                    # a cherry-picked old report failing closed is the right direction);
                    # -m (a report finalized only in a merge-conflict resolution listed NO
                    # files in the default merge-suppressed log — false refusal); and the
                    # run's own TIME window instead of a commit count (55 phase/doc commits
                    # after the report pushed it past -n 50 — false refusal; the -n 500 is
                    # a runaway backstop, not the bound).
                    since = str(int(started_epoch))
                    log = subprocess.run(
                        [
                            "git",
                            "log",
                            "-m",
                            "--name-only",
                            "--format=%at",
                            f"--since={since}",
                            "-n",
                            "500",
                            "HEAD",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=True,
                        cwd=root,
                    ).stdout.splitlines()
                except Exception:
                    log = []  # no commits yet = no HEAD artifact; NOT "broken git" (round 31:
                    # the outer fail-open swallowed this and closed an empty repo clean)
                commit_epoch = 0.0
                for ln in log:
                    if ln.strip().isdigit():
                        commit_epoch = float(ln.strip())
                        continue
                    # >= floor(start), no broader grace: a commit AUTHORED before start is
                    # a previous task's artifact (round 31: the 60s grace let the pre-run
                    # commit count) — git timestamps are WHOLE seconds while started_epoch
                    # is fractional, so a same-second commit truncates below start and was
                    # false-refused (round 137, reproduced); within the shared second,
                    # "before" is indeterminate and resolves toward not refusing.
                    if (
                        commit_epoch >= int(started_epoch)
                        and ln.startswith("docs/development/reviews/")
                        and ln.endswith(".md")
                        and "archived/" not in ln
                    ):
                        hf = Path(root or ".") / ln
                        # EXISTENCE gates the gate (round 141): --name-only lines carry no
                        # status letter, so an add-then-delete pair inside the window
                        # matched the path test twice while the file no longer existed —
                        # ok_artifact went True with candidates=[], and BOTH refusal
                        # branches were skipped. The report must be on disk NOW.
                        if hf.is_file() and not hf.is_symlink():
                            ok_artifact = True
                            candidates.append(hf)
        except Exception:
            ok_artifact = None  # broken git must not wedge the close — fail open HERE only
        if ok_artifact is True and candidates:
            # CONTENT floor (round 135): a report declaring itself mid-loop satisfies no
            # terminal condition — `done` with ONLY `Status: IN-PROGRESS` artifacts is the
            # round-29 evidence-string hole wearing a file's clothes. Header-zone only
            # (first 10 lines, the template's slot); one non-mid-loop artifact suffices.
            def _midloop(f: Path) -> bool:
                try:
                    head10 = "".join(
                        f.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[
                            :10
                        ]
                    )
                except OSError:
                    return False
                import re as _re

                return bool(_re.search(r"^\s*\**Status:\**\s*IN-PROGRESS\b", head10, _re.M | re.I))

            if all(_midloop(f) for f in candidates):
                msg = (
                    f"REFUSED — every report this /{live} run persisted declares "
                    "`Status: IN-PROGRESS` (mid-loop). A terminal `done` needs a report "
                    "that has actually closed its loop; finish it, or close as `blocked`."
                )
                sys.stderr.write(f"[command_run] {msg}\n")
                print(msg)
                return 1
        if ok_artifact is False:
            msg = (
                f"REFUSED — closing /{live} with done requires its persisted report: no "
                "docs/development/reviews/*.md written or committed SINCE THIS RUN STARTED "
                f"in {root or 'the current repo'}. A review that exists only in chat does not "
                "exist. Write the report (or close as `blocked` if genuinely halted)."
            )
            sys.stderr.write(f"[command_run] {msg}\n")
            print(msg)
            return 1
    # ── the FEEDBACK duty, made non-optional at the only moment it can still be paid ──────────
    # Measured 2026-08-28, after the duty was written into both constitutions, auto-appended to
    # all 31 commands and 4 agent definitions, given a `--feedback` flag, a persisted verdict, a
    # kaizen cell and a grader: 13 closes in 14 days, 12 with NO verdict, and ZERO `filed` — ever.
    # Distribution was not the problem (30/30 commands carried it; the fleet copies were
    # byte-identical). It changed nothing because `done` returned 0 without the flag and the
    # grader is warn_only. Prose plus an advisory line does not bind an agent at the end of a long
    # run; a refused close does — and it needs no new hook and no new fleet-wide red, because the
    # record simply stays `running` and final_gate_stop.py ALREADY blocks the turn on that.
    if _feedback_is_required(rec) and not str(getattr(args, "feedback", "") or "").strip():
        msg = (
            f"REFUSED — closing /{live} needs its FEEDBACK verdict. You are the only witness to "
            "how the machinery behaved on this run, and this is the last moment you can say so.\n"
            f"  Filed something:  --feedback 'filed <what> to <infra|fleet|intel>'\n"
            "  Genuinely nothing: --feedback 'none — <the surfaces you exercised>'\n"
            "`none` is a valid verdict and is counted separately; silence is not a verdict. "
            "See commands/_fragments/close-feedback.md."
        )
        sys.stderr.write(f"[command_run] {msg}\n")
        print(msg)
        return 1
    rec["state"] = args.cmd
    # `closed_by` is ADDITIVE and never read by an existing consumer (the Stop hook keys
    # on `state == "running"` alone). `agent` is the only value this script writes; the
    # coroner writes `coroner`/`ttl` for the runs no agent ever came back to close.
    rec["closed_by"] = "agent"
    if args.cmd == "done":
        rec["evidence"] = args.evidence
    elif args.cmd == "handoff":
        # NOT-QUIET: the loop went quiet but rows stay OPEN and are ROUTED. /fabrik-user-test and
        # /fabrik-service-test both MANDATE this close; before it existed the only reachable words
        # were `done` (untrue - the contract is not met) and a stretched "unresolvable spec
        # contradiction". An agent ordered to produce a disposition it cannot record will either
        # lie or stall, and both are worse than a fourth word.
        rec["blocked_reason"] = args.reason
        rec["resume"] = args.resume
    else:
        rec["blocked_reason"] = args.reason
    _touch(rec)
    stack = list(rec.get("stack") or [])
    parent = stack.pop() if stack else None
    _fb_verdict, _fb_beats = _feedback_verdict(getattr(args, "feedback", None))
    # On the RECORD as well as the event: the event stream is box-local telemetry, while the record
    # is what a per-run check can read. Storing it only on the event left the record unable to
    # describe its own close, and left the duty ungradeable — which is how a prose obligation stays
    # prose. The verdict is stored; the PROSE never is (`feedback_hash` on the event covers that).
    rec["feedback"] = _fb_verdict
    rec["feedback_to"] = _fb_beats
    fields = _queue(
        rec,
        outbox,
        "run_close",
        {
            "verdict": args.cmd,
            "closed_by": "agent",
            "evidence_hash": _evidence_hash(args.evidence if args.cmd == "done" else args.reason),
            "resume": getattr(args, "resume", "") or "",
            # Kaizen's `Filed (spec/mail)` column has read "-" on every row since the 2026-08-12
            # baseline because nothing ever measured it. These three fields make it countable: the
            # verdict, which beats were routed to, and a HASH of the line (never the prose - the
            # same contract `evidence_hash` already keeps).
            "feedback": _fb_verdict,
            "feedback_to": _fb_beats,
            "feedback_hash": _evidence_hash(getattr(args, "feedback", None) or ""),
            "rounds": len(rec.get("rounds") or []),
            # A nested close is the one event whose meaning lives OUTSIDE the line: "resuming"
            # is only informative if it says what, and at what point. Without these the
            # collector would have to replay the whole stack to learn that the run continues.
            "resumed": (parent or {}).get("command") or "",
            "resumed_phase": (parent or {}).get("phase") or 0,
            "resumed_rounds": len((parent or {}).get("rounds") or []),
        },
    )
    if parent is not None:
        closed = {k: v for k, v in rec.items() if k != "stack"}
        parent["stack"] = stack
        parent.setdefault("nested", []).append(closed)
        # The counter belongs to the SESSION, not to the record that happens to hold it —
        # a restored parent must keep ascending from where the nested run left off.
        parent["event_seq"] = rec.get("event_seq")
        _touch(parent)
        fields["persisted"] = save(sid, parent)
        print(f"{args.cmd.upper()} /{closed.get('command')} — resuming:")
        print(pinned_line(parent))
        return 0
    fields["persisted"] = save(sid, rec)
    print(f"{args.cmd.upper()} /{rec.get('command')} — run record closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
