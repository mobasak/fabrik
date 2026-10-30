#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/kaizen.md, tests/test_merge_tripwire.py
"""The merge program's daily tripwire (W-622ec42c, D-1384, D-1385) — kaizen's measure of the merge path.

Three readings per LOCAL day, from records that already exist:

1. **Wall time per merged request** — from the request (its id is the request mail's ULID, whose first
   10 characters encode the send instant in ms) to the record's last write (``merge_request.py``
   rewrites the record at its reply, the end of the requester's wait). Median and max of that day's
   merged requests, bucketed by REQUEST day so a day's numbers never move once its requests settle.
2. **Refusals by class** — the ``reason`` of every ``outcome: refused`` record, classed by
   ``refusal_class`` (ledger-conflict · conflict · tests-red · dirty-main · preflight · other), for the
   day and the 14 days ending on it (D-1385's "under 5 refusals per 14 days, zero ledger-conflict").
3. **The red-master series before and after the post-merge valve** — ``waste_red_master_rework``
   (published daily by ``kaizen_waste.py``) pooled as Σ red-master fixes / Σ arrivals over the 14 days
   before the valve day versus the 7 newest days after it. The valve day is the first commit on
   ``$MERGE_TRIPWIRE_REF`` (default ``origin/master``) whose ``.fabrik/merge-tests`` carries
   ``merge-tests-after-merge-above: 0`` (D-1384's own text); with no such commit the valve is OFF and
   only the "before" level prints.

**The tripwire (D-1384):** when the 7 newest post-valve days are all published and their pooled rate is
above the pre-valve level, the series has risen for a week — one mail to the coordinator per episode
(the episode ends the first day the condition is false), saying the threshold goes back to 40.

Outputs, both under the repo's merge-record directory (``<git common dir>/fabrik-merge/``) so a
project's coordinator reads its own repo's numbers: ``tripwire.jsonl`` (one row per day, idempotent)
and ``tripwire-line.txt`` (the one line ``work.py prompt_block`` shows a coordinator).

Honesty: a day with no settled records publishes its counts as 0 only when records exist around it; a
red-master day not yet published is missing, never 0, and a missing day blocks the tripwire rather than
firing it. Record times come from the file's mtime: a tool that rewrote an old record would move its
reply instant — none does today (``merge_request.py`` writes a record only while it owns it).

Cobra (D-253): the cheapest way to keep the wall time low without faster merges is to refuse more (a
refusal is not a merged request); the refusal counts print beside it in the same line, so a fall in
wall time that comes with a rise in refusals is visible. The cheapest way to keep the red-master
reading flat is to stop writing "master red" in fix messages; that series' own counter
(``waste_seat_share``) and the post-merge leg's P0 items stay the check.

Usage:
    merge_tripwire.py --day 2026-10-30            # print the day's line
    merge_tripwire.py --publish --day 2026-10-30  # write the row + the line, mail on a tripped episode
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kaizen_collect_v2 as kc  # noqa: E402 - same directory (store paths, warn)

REPO = Path(__file__).resolve().parents[2]
GIT_TIMEOUT_S = 20
PRE_DAYS = 14  # the pre-valve level pools this many days before the valve day
WEEK = 7  # D-1384: a rise "for a week"
REFUSAL_WINDOW = 14  # D-1385: "under 5 refusals per 14 days"
RED_METRIC = "waste_red_master_rework"
VALVE_RE = re.compile(r"^\s*#?\s*merge-tests-after-merge-above:\s*0\s*$", re.M)
LEDGERS = (
    "CHANGELOG.md",
    "docs/DECISIONS.md",
    "INDEX.md",
    "docs/STRATEGIC_BACKLOG.md",
    "docs/LESSONS_LEARNT.md",
)  # merge_request.LEDGERS, plus the work-item files below
_ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def repo_root() -> Path:
    return Path(os.environ.get("MERGE_TRIPWIRE_REPO") or REPO)


def _git(args: list[str]) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo_root()), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def records_dir() -> Path:
    common = Path(_git(["rev-parse", "--git-common-dir"]).strip())
    return (common if common.is_absolute() else repo_root() / common) / "fabrik-merge"


def ulid_time(ulid: str) -> float | None:
    try:
        n = 0
        for c in ulid[:10].upper():
            n = n * 32 + _ULID.index(c)
    except (ValueError, AttributeError):
        return None
    return n / 1000


def _local_day(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).astimezone().date().isoformat()


def refusal_class(reason: str) -> str:
    """One class per refusal reason, first match wins (the reason strings merge_request.py writes)."""
    if "owner tests red" in reason:
        return "tests-red"
    if "in the main checkout" in reason:  # "is dirty in" / "is staged differently from HEAD in"
        return "dirty-main"
    m = re.search(r"conflict in (.+?)(?: — |$)", reason)
    paths = [p.strip() for p in m.group(1).split(",")] if m else []
    m = re.search(r"(\S+): (?:a side edits|merge-item:)|collides in (\S+)", reason)
    if m:
        paths.append(m.group(1) or m.group(2))
    if paths:
        ledger = all(
            p in LEDGERS or re.fullmatch(r"\.fabrik/work/W-[0-9a-f]{8}\.json", p) for p in paths
        )
        return "ledger-conflict" if ledger else "conflict"
    if reason.lstrip().startswith("(a) preflight"):
        return "preflight"
    return "other"


def load_records(rdir: Path) -> list[dict]:
    """Every settled record: {day, outcome, wall_s, cls}. An unreadable or unsettled one is skipped."""
    out: list[dict] = []
    for p in sorted(rdir.glob("*.json")) if rdir.is_dir() else []:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            end = p.stat().st_mtime
        except (OSError, ValueError):
            continue
        if not isinstance(rec, dict) or rec.get("outcome") not in ("merged", "refused"):
            continue
        start = ulid_time(str(rec.get("id") or p.stem))
        if start is None:
            continue
        out.append(
            {
                "day": _local_day(start),
                "outcome": rec["outcome"],
                "wall_s": max(0.0, end - start),
                "cls": refusal_class(str(rec.get("reason") or ""))
                if rec["outcome"] == "refused"
                else "",
            }
        )
    return out


def valve_day(ref: str) -> str | None:
    """Local day of the first commit on ``ref`` whose .fabrik/merge-tests turns the valve on for every
    merge (threshold 0); None while no such commit exists."""
    try:
        log = _git(
            [
                "log",
                ref,
                "--reverse",
                "--format=%H %ct",
                "-G",
                "merge-tests-after-merge-above",
                "--",
                ".fabrik/merge-tests",
            ]
        )
        for line in log.splitlines():
            sha, ct = line.split()
            if VALVE_RE.search(_git(["show", f"{sha}:.fabrik/merge-tests"])):
                return _local_day(float(ct))
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        kc._warn(f"merge tripwire: valve lookup failed: {exc}")
    return None


def red_series(state: Path | None = None) -> dict[str, tuple[float, float]]:
    """{day: (numerator, denominator)} from the newest version of the red-master series file."""
    sdir = (state or kc.state_dir()) / "series"
    files = sorted(
        sdir.glob(f"{RED_METRIC}@v*.jsonl"),
        key=lambda p: int(re.search(r"@v(\d+)$", p.stem).group(1)),  # type: ignore[union-attr]
    )
    out: dict[str, tuple[float, float]] = {}
    if not files:
        return out
    for line in files[-1].read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            out[str(row["day"])] = (float(row["numerator"]), float(row["denominator"]))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def _days(end: str, n: int) -> list[str]:
    d = dt.date.fromisoformat(end)
    return [(d - dt.timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _pooled(series: dict[str, tuple[float, float]], days: list[str]) -> float | None:
    rows = [series[d] for d in days if d in series]
    den = sum(r[1] for r in rows)
    return sum(r[0] for r in rows) / den if den else None


def red_master(day: str, valve: str | None, series: dict[str, tuple[float, float]]) -> dict:
    """The pre-valve level, the post-valve week and whether the week tripped (all 7 days published,
    pooled above the level)."""
    before_end = (dt.date.fromisoformat(valve) - dt.timedelta(days=1)).isoformat() if valve else day
    pre = _pooled(series, _days(before_end, PRE_DAYS))
    out = {"valve_day": valve, "pre": pre, "week": None, "week_days": 0, "tripped": False}
    if not valve:
        return out
    week = [d for d in _days(day, WEEK) if d > valve]
    have = [d for d in week if d in series]
    out["week"], out["week_days"] = _pooled(series, have), len(have)
    out["tripped"] = (
        len(week) == WEEK and len(have) == WEEK and pre is not None and out["week"] > pre
    )
    return out


def measure(day: str, records: list[dict], red: dict) -> dict:
    mine = [r for r in records if r["day"] == day]
    walls = sorted(r["wall_s"] for r in mine if r["outcome"] == "merged")
    window = set(_days(day, REFUSAL_WINDOW))
    classes: dict[str, int] = {}
    for r in mine:
        if r["outcome"] == "refused":
            classes[r["cls"]] = classes.get(r["cls"], 0) + 1
    win: dict[str, int] = {}
    for r in records:
        if r["outcome"] == "refused" and r["day"] in window:
            win[r["cls"]] = win.get(r["cls"], 0) + 1
    return {
        "day": day,
        "merged": len(walls),
        "wall_median_s": round(statistics.median(walls)) if walls else None,
        "wall_max_s": round(walls[-1]) if walls else None,
        "refused": sum(classes.values()),
        "refusal_classes": dict(sorted(classes.items())),
        "refused_14d": sum(win.values()),
        "refusal_classes_14d": dict(sorted(win.items())),
        "red_master": red,
    }


def _mins(s: float | None) -> str:
    return "—" if s is None else f"{s / 60:.0f}m"


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{100 * v:.2f}%"


def line(m: dict) -> str:
    cls = ", ".join(f"{k} {v}" for k, v in m["refusal_classes_14d"].items()) or "none"
    red = m["red_master"]
    if red["valve_day"]:
        rm = (
            f"red-master week {_pct(red['week'])} ({red['week_days']}/{WEEK} d) vs pre-valve "
            f"{_pct(red['pre'])}, valve on {red['valve_day']}"
        )
    else:
        rm = f"red-master pre-valve {_pct(red['pre'])}, valve not on yet"
    # the verdict goes FIRST: the prompt block clips a long line from the end (work.LINE_MAX)
    head = "TRIPPED, threshold back to 40 (D-1384) — " if red["tripped"] else ""
    return (
        f"{head}merge tripwire {m['day']}: {m['merged']} merged, wall median {_mins(m['wall_median_s'])} "
        f"max {_mins(m['wall_max_s'])} · refused {m['refused']} (14 d: {m['refused_14d']} — {cls}) · {rm}"
    )


def compute(day: str, state: Path | None = None) -> dict:
    ref = os.environ.get("MERGE_TRIPWIRE_REF") or "origin/master"
    return measure(
        day, load_records(records_dir()), red_master(day, valve_day(ref), red_series(state))
    )


def _mail(m: dict) -> bool:
    red = m["red_master"]
    body = "\n".join(
        [
            f"Subject: merge tripwire TRIPPED {m['day']}: red-master week {_pct(red['week'])} "
            f"above pre-valve {_pct(red['pre'])} — put the post-merge threshold back to 40 (D-1384)",
            "",
            f"WHAT: the red-master series (kaizen_waste.waste_red_master_rework) pooled over the "
            f"{WEEK} days ending {m['day']} reads {_pct(red['week'])}, above its pre-valve level "
            f"{_pct(red['pre'])} ({PRE_DAYS} days before the valve day {red['valve_day']}).",
            "WHERE: .fabrik/merge-tests (merge-tests-after-merge-above), scripts/merge_request.py.",
            f"WHEN: every one of the {WEEK} days after the valve is published and the pooled rate is above.",
            "WHO: the coordinator (the merge owner) decides the threshold change; kaizen measured it.",
            "WHY: D-1384 kept the valve on only while the series does not rise past its pre-valve "
            "level for a week; this is that rise.",
            "HOW: set merge-tests-after-merge-above back to 40 in .fabrik/merge-tests, or rule "
            "otherwise in a new D-row.",
            f"SYSTEMIC: {line(m)}",
        ]
    )
    r = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "mail.py"),
            "send",
            "--to",
            os.environ.get("MERGE_TRIPWIRE_MAILBOX") or "fabrik",
            "--to-agent",
            "coordinator",
            "--kind",
            "finding",
            "--ack",
            "required",
        ],
        input=body,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        kc._warn(f"merge tripwire: mail failed rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.returncode == 0


def publish(day: str, state: Path | None = None) -> dict:
    """Append the day's row (once per day), rewrite the line file, and mail once per tripped episode."""
    m = compute(day, state)
    rdir = records_dir()
    rdir.mkdir(parents=True, exist_ok=True)
    rows_path = rdir / "tripwire.jsonl"
    rows = []
    if rows_path.is_file():
        for raw in rows_path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(raw))
            except ValueError:
                continue
    prev = max((r for r in rows if r.get("day", "") < day), key=lambda r: r["day"], default=None)
    episode_mailed = bool(prev and prev.get("red_master", {}).get("tripped") and prev.get("mailed"))
    m["mailed"] = episode_mailed
    if m["red_master"]["tripped"] and not episode_mailed:
        m["mailed"] = _mail(m)
    if not any(r.get("day") == day for r in rows):
        with open(rows_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(m, ensure_ascii=False, separators=(",", ":")) + "\n")
    newest = max([r.get("day", "") for r in rows] + [day])
    if day == newest:
        tmp = rdir / "tripwire-line.txt.tmp"
        tmp.write_text(line(m) + "\n", encoding="utf-8")
        tmp.replace(rdir / "tripwire-line.txt")
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--day", required=True, type=lambda v: dt.date.fromisoformat(v).isoformat())
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    m = publish(a.day) if a.publish else compute(a.day)
    print(json.dumps(m, indent=2) if a.json else line(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
