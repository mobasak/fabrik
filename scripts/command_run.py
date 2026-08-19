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
named ``<session_id>.json``; the session id comes from ``CLAUDE_SESSION_ID`` or ``--session``.

Fail-soft EVERYWHERE: a corrupt or unwritable record must never wedge an agent, and
``line``/``status`` never raise — they go silent instead. The Stop hook's matching
fail direction is deliberate and asymmetric: only a record that positively says
``running`` blocks; missing/corrupt/stale fails OPEN.

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
import contextlib
import fcntl
import hashlib
import json
import os
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


def _state_dir() -> Path:
    raw = os.environ.get("COMMAND_RUN_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "state" / "command-runs"


def _session_id(explicit: str | None) -> str:
    return explicit or os.environ.get("CLAUDE_SESSION_ID") or "nosession"


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


def _csv(raw: str | None) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


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


def convergence_warning(series: list[int]) -> str:
    """Advisory oscillation diagnosis, or "" — NEVER blocks (a heuristic must not trap).

    A converging loop trends DOWN (5 → 3 → 0). A pathological one oscillates
    (43 → 11 → 30 → 13 → 22) because each round RE-SCOPES instead of RE-SWEEPING
    the persisted class ledger.
    """
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
            '--evidence "<proof>"'
        )
        # A terminal round CLOSES the loop — never also scold it for oscillating. The
        # drop TO zero is what non-increasing was asking for; the series test alone
        # reads `13 → 22 → 0` as a rise (live smoke, 2026-08-16).
        return "\n".join(lines)
    warn = convergence_warning([int(r.get("findings", 0)) for r in rounds])
    if warn:
        lines.append(warn)
    return "\n".join(lines)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _touch(rec: dict[str, Any]) -> None:
    rec["updated_at"] = _now()
    rec["updated_ts"] = int(time.time())


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="command_run.py", description=__doc__)
    ap.add_argument("--session", help="session id (default: $CLAUDE_SESSION_ID)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start", help="begin a command run")
    p.add_argument("--command", required=True, help="e.g. fabrik-review")
    p.add_argument("--phases", required=True, type=int)
    p.add_argument("--terminal", default="", help="the run's terminal condition")

    p = sub.add_parser("step", help="advance to a phase")
    p.add_argument("--phase", required=True, type=int)
    p.add_argument("--title", default="")

    p = sub.add_parser("round", help="record one convergence round")
    p.add_argument("--findings", type=int, default=0)
    p.add_argument("--classes-swept", default="", help="comma-separated, swept CLEAN")
    p.add_argument("--classes-new", default="", help="comma-separated, newly opened")

    p = sub.add_parser("done", help="terminal: the contract is met")
    p.add_argument("--command", required=True, help="the run you are closing — must be the LIVE one")
    p.add_argument("--evidence", required=True)

    p = sub.add_parser("blocked", help="terminal: one of the three sanctioned BLOCKED cases")
    p.add_argument("--command", required=True, help="the run you are closing — must be the LIVE one")
    p.add_argument("--reason", required=True)

    sub.add_parser("line", help="print the pinned status line (silent when idle)")
    p = sub.add_parser("status", help="print the record")
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
        with _record_lock(sid):
            return _mutate(sid, args)
    except Exception as e:  # fail-soft — a state bug must never wedge an agent
        sys.stderr.write(f"[command_run] error, continuing: {e}\n")
        return 0


def _mutate(sid: str, args: argparse.Namespace) -> int:
    """The mutating subcommands. Runs with the record's flock HELD."""
    rec = load(sid)

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
            "rounds": [],
            "classes": {},
            "stack": stack,
        }
        _touch(new)
        save(sid, new)
        print(pinned_line(new))
        return 0

    if not rec:
        sys.stderr.write(
            "[command_run] no run record for this session — "
            "`start` one before step/round/done/blocked.\n"
        )
        return 0

    if args.cmd == "step":
        rec["phase"] = max(1, args.phase)
        rec["phase_title"] = args.title
        _touch(rec)
        save(sid, rec)
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
        _touch(rec)
        save(sid, rec)
        print(_round_report(rec))
        return 0

    if args.cmd in ("done", "blocked"):
        return _close(sid, rec, args)

    return 0


def _close(sid: str, rec: dict[str, Any], args: argparse.Namespace) -> int:
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

    if args.cmd == "done" and live in ("fabrik-review", "fabrik-repo-review"):
        # ARTIFACT-BY-FILESYSTEM (2026-08-19): check_review_coverage retired its command-name
        # sniff on the stated ground that "did the command emit its artifact" is THIS record's
        # enforcement moment — and a closing sweep then proved the claim false: `done` accepted
        # any evidence STRING, so a review run could close having written nothing. The claim is
        # now mechanically true: a review's `done` requires a changed/untracked report under
        # docs/development/reviews/ (git status) or one committed at HEAD — never a sentence
        # about one.
        try:
            porcelain = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=all",
                 "--", "docs/development/reviews/"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout
        except Exception:
            porcelain = None  # a broken git must not wedge the close — fail open HERE only
        if porcelain is not None and not any(
            ln[3:].strip().endswith(".md") for ln in porcelain.splitlines()
        ):
            try:
                head_files = subprocess.run(
                    ["git", "show", "--name-only", "--format=", "HEAD"],
                    capture_output=True, text=True, timeout=10, check=True,
                ).stdout
            except Exception:
                head_files = ""
            if "docs/development/reviews/" not in head_files:
                msg = (
                    f"REFUSED — closing /{live} with done requires its persisted report: no "
                    "changed, untracked, or HEAD-committed docs/development/reviews/*.md found. "
                    "A review that exists only in chat does not exist. Write the report (or "
                    "close as `blocked` if genuinely halted)."
                )
                sys.stderr.write(f"[command_run] {msg}\n")
                print(msg)
                return 1
    rec["state"] = args.cmd
    if args.cmd == "done":
        rec["evidence"] = args.evidence
    else:
        rec["blocked_reason"] = args.reason
    _touch(rec)
    stack = list(rec.get("stack") or [])
    if stack:
        parent = stack.pop()
        closed = {k: v for k, v in rec.items() if k != "stack"}
        parent["stack"] = stack
        parent.setdefault("nested", []).append(closed)
        _touch(parent)
        save(sid, parent)
        print(f"{args.cmd.upper()} /{closed.get('command')} — resuming:")
        print(pinned_line(parent))
        return 0
    save(sid, rec)
    print(f"{args.cmd.upper()} /{rec.get('command')} — run record closed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
