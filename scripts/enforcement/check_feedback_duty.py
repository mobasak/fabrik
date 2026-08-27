#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_feedback_duty.py
"""Close-out feedback gate — ADVISORY. A command run owes a FEEDBACK verdict before it closes.

THE DIRECTIVE (operator, stated twice, 2026-08-27): *"agents must give you feedback if they find
issues, or have suggestions about our commands and rules and infra, and send infra, intel or fleet a
message — they must be proactive."*

Running a command means USING the machinery, which makes the agent running it the only witness to
how that machinery actually behaved. A defect routed around silently dies in that session's context
when it ends. The duty was written into both constitutions, auto-appended to all 31 commands
(`commands/_fragments/close-feedback.md`), and made recordable via `command_run.py --feedback`.

**Nothing graded it.** Measured when this check was written: 11 closed run records on the box, 11
without a verdict. That is the class this repo keeps closing — the agent a prose obligation
constrains is the only one who could report having skipped it, and skipping is exactly what does not
get self-reported. So the omission is counted here instead.

WHAT `unstated` MEANS. Three verdicts: `filed` (routed to a beat), `none` (looked, nothing to file —
a real answer), `unstated` (no verdict given at all). A record with no `feedback` key closed without
one, which IS `unstated`; excusing those would let the metric report compliance that never happened.

WHAT IT CANNOT GRADE, stated because a grader hiding its blind spot rebuilds the defect one layer
down: it sees whether a verdict was GIVEN. It cannot see whether the filing was honest, whether the
mail was actually sent, or whether a `none` was earned by looking. See `SCOPE_NOTE`.

ADVISORY BY CONTRACT. Registered `warn_only=True` and **always exits 0** — a non-zero exit from a
`warn_only` check is a BLOCKING red across ~46 governance-synced repos. Silent when no run closed in
the window; a still-running record is never graded, because the duty attaches to the CLOSE.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

#: Default record store — the same default `command_run.py` writes to.
RUNS_DIR = Path.home() / ".claude" / "state" / "command-runs"

#: Only recent closes are signal. A months-old omission is not this week's problem, and
#: re-reporting it forever is how an advisory line becomes wallpaper nobody reads.
WINDOW_DAYS = 14

#: A record is closed (and therefore owes a verdict) in exactly these states.
CLOSED_STATES = frozenset({"done", "blocked", "handoff"})

SCOPE_NOTE = (
    "sees whether a verdict was GIVEN; cannot tell whether the filing was honest, whether the mail "
    "was sent, or whether a `none` was earned by looking"
)
CENSUS_NOTE = "verdict given or not; honesty not gradeable"

ADVISORY_BUDGET = 500
MAX_LINE = 200
MAX_LINES = 10

REMEDY = (
    "close with --feedback: what you filed and to whom, or 'none' plus the surfaces you "
    "exercised (commands/_fragments/close-feedback.md)"
)


def _say(line: str) -> None:
    """The ONLY print here, and the ASCII guarantee's home — a command name carrying a non-ASCII
    character must never turn this check's output into a swallowed `UnicodeEncodeError`, which reads
    exactly like a clean run."""
    print(line.encode("ascii", "backslashreplace").decode("ascii"))


def _recent(body: dict, now: dt.datetime) -> bool:
    """Closed within the window. An unparseable or absent timestamp counts as IN — an omission must
    not escape by carrying a broken date."""
    raw = str(body.get("closed_at") or body.get("updated_at") or "")
    if not raw:
        return True
    try:
        when = dt.datetime.fromisoformat(raw)
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    return (now - when).days <= WINDOW_DAYS


def _audit(runs: Path) -> tuple[int, list[tuple[str, str]]]:
    """Return (closes examined, [(command, record-name)] lacking a verdict)."""
    try:
        paths = sorted(p for p in runs.glob("*.json") if p.is_file())
    except OSError:
        return 0, []
    now = dt.datetime.now(dt.UTC)
    examined = 0
    unstated: list[tuple[str, str]] = []
    for path in paths:
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # a torn record is the coroner's business, not this check's
        if not isinstance(body, dict) or body.get("state") not in CLOSED_STATES:
            continue  # a RUNNING record has not yet owed its verdict
        if not _recent(body, now):
            continue
        examined += 1
        # Absent key == closed without a verdict == `unstated`. Not excused: excusing it would
        # report compliance that never happened.
        if str(body.get("feedback") or "unstated") == "unstated":
            unstated.append((str(body.get("command") or "?"), path.stem[:8]))
    return examined, unstated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advisory: a command run owes a FEEDBACK verdict.")
    parser.add_argument("--runs", default="", help=f"run-record dir (default: {RUNS_DIR})")
    # parse_KNOWN_args INSIDE the guard: argparse calls `sys.exit(2)` on a bad flag and `SystemExit`
    # derives from BaseException, so `except Exception` would miss it — the hole that made a sibling
    # warn_only check exit 2 earlier today.
    try:
        args, _unknown = parser.parse_known_args(argv)
        runs = Path(args.runs) if args.runs else Path(os.getenv("COMMAND_RUN_DIR", "") or RUNS_DIR)
        examined, unstated = _audit(runs)
    except SystemExit:
        return 0
    except Exception as exc:  # the CLASS, never an enumerated list of types
        try:
            _say(f"could not evaluate the feedback duty: {type(exc).__name__}")
        except Exception:  # pragma: no cover - stdout itself is broken; stay silent, stay 0
            pass
        return 0

    if examined == 0:
        return 0  # no run closed in the window - say nothing at all
    if not unstated:
        _say(f"feedback duty: {examined} close(s) in {WINDOW_DAYS}d, all carried a verdict")
        return 0

    census = (
        f"feedback duty: {examined} close(s) in {WINDOW_DAYS}d, "
        f"{len(unstated)} with NO verdict ({CENSUS_NOTE})"
    )
    _say(census)
    # The marker is CHARGED UP FRONT — paying for it out of the remainder is how a sibling check
    # lost its REMEDY line mid-word to final_gate's 500-char cut.
    marker_cost = len(f"  ... {len(unstated)} more - run the check directly") + 1
    budget = ADVISORY_BUDGET - (len(census) + 1) - (len(REMEDY) + 6) - marker_cost
    emitted = 0
    for command, stem in unstated:
        line = f"  UNSTATED: {command} ({stem})"
        if len(line) > MAX_LINE:
            line = line[: MAX_LINE - 3] + "..."  # exactly MAX_LINE, not MAX_LINE + 2
        if (budget - len(line) < 0 or emitted >= MAX_LINES - 3) and emitted:
            break
        _say(line)
        budget -= len(line) + 1
        emitted += 1
    if emitted < len(unstated):
        _say(f"  ... {len(unstated) - emitted} more - run the check directly")
    _say(f"  -> {REMEDY}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
