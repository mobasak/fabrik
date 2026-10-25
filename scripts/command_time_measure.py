#!/usr/bin/env python3
# AFTER-EDIT: tests/test_command_time_measure.py, INDEX.md
"""The lean program's time measure (D-1219): intel's W-0a91bf86 method as one pinned script.

Per command and per window, over EVERY close in the window (done, blocked and handoff alike, so a
long run that closes `blocked` cannot leave the median), it reports:

- closes, by state, and the non-`done` share;
- wall-clock per run: median, mean and p90 of the ledger's `wall_s`;
- rounds per run: the ledger's `rounds`. A /fabrik-task or /fabrik-execute-plan close records 0 —
  its rounds are its nested /fabrik-review run's own ledger rows;
- wall-clock per work item: closes grouped by the first `W-xxxxxxxx` id in their `surface`, the
  item's minutes summed; closes carrying no id are counted, never grouped. Grouped per command and
  per window, so an item straddling a window boundary is split, and a task's nested review counts
  under both commands;
- closes per item: how many closes each work item took — the direct signal that one review was
  split into several short runs;
- runs per commit: closes ÷ commits authored in the window (any branch or remote, no merges, an
  `Agent-Role:` trailer, one count per sha per git common dir) across ONE repo set for every window:
  the repos of every in-scope close in the ledger. It is a box-wide ratio, about a third of it
  work-store bookkeeping, so it moves with commits unrelated to these runs; closes per item is the
  split signal;
- surface size: `loc_added`, over closes that recorded a commit. Only /fabrik-task closes carry it
  (`command_run.py`'s close-time re-measure), and a close with no commit writes a placeholder "0"
  beside `oversized_mini: unmeasurable=no-commit`, which is left out; other commands print n 0;
- seat-minutes per run, two ways: `seat_min`, the union of every seat transcript's active segments
  inside the run's `run_open`..`run_close` window (the table's "seats running, idle gaps over 10 min
  cut" row: a segment breaks where two consecutive lines of one seat are more than `--gap-min`
  apart), and `seat_sum_min`, the sum of each seat's own clipped active time. Removing one of two
  seats that run side by side moves the sum and barely moves the union. Measured on runs with a
  `dispatch` event and at least one surviving seat transcript; a /fabrik-task run's figure includes
  its nested review's seats, as the table's did. Seat transcripts are pruned after 3 days (D-1182),
  so a window older than that reads n 0: store the `--per-run` rows nightly and aggregate those.
  The table published the gap-cut figure as a SHARE (`seat_share`); its per-run medians are new.

Sources: `~/.claude/state/command-feedback.jsonl` (one row per close, `ts` = the close's epoch),
`~/.claude/state/events/<sid>.jsonl` (run_open, dispatch, run_close; a run is a `run_open` to the
next `run_close` of the same command in the same session, nesting tracked as a stack), and the
seat transcripts `<projects root>/<project>/<sid>/subagents/*.jsonl` under `~/.claude/projects`
and every `~/.claude-fleet/*/projects`. Lines that do not parse (bad JSON, a non-number, a time with
no UTC offset) are skipped and COUNTED in the report's `skipped`; a missing ledger, events dir or
projects root stops the run (a silent seat n 0 would read as a met target). Nothing is written.
`--per-run` adds the rows behind the figures: every close (`closes`) and every event-stream run
(`runs`), so a nightly job can store them and later columns read the same rows.

Windows: `--windows` (1) windows of `--days` (14), the last ending at `--end` (default now); or,
with `--start`, one window `[--start, --start + --days)` — or `[--start, --end)` when both are
given. A close belongs to the window holding its close time.

COBRA (D-253): the cheapest way to move these numbers without moving the work is (a) closing runs
`blocked` or `handoff` to shorten the done runs — counter: every state counts and the non-done
share is printed; (b) splitting one review into several short runs — counter: closes per item
and wall-clock per work item; (c) committing more often to dilute runs per commit — counter:
closes per item does not read commits; (d') overlapping seats so the union shrinks with no less
seat work — counter: `seat_sum_min`; (d) stopping seats early — counter: rounds per run, and slice B's
later-findings column on fast-closed files.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import statistics
import subprocess
import sys

DEFAULT_COMMANDS = ("fabrik-review", "fabrik-review-scoped", "fabrik-task", "fabrik-execute-plan")
WORK_ID = re.compile(r"\bW-[0-9a-f]{8}\b")
NO_COMMIT = "unmeasurable=no-commit"
STATE = os.path.expanduser("~/.claude/state")


def _aware(value: object) -> dt.datetime | None:
    """An ISO 8601 time WITH a UTC offset, or None (a naive time cannot be ordered against the rest)."""
    if not isinstance(value, str):
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _stats(values: list[float]) -> dict:
    """median, mean and the table's p90 (`sorted(v)[int(n * 0.9)]`) — n 0 when there is nothing."""
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {
        "n": len(s),
        "median": statistics.median(s),
        "mean": statistics.mean(s),
        "p90": s[int(len(s) * 0.9)],
    }


def load_ledger(path: str, skipped: collections.Counter) -> list[dict]:
    rows = []
    with open(path, errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                skipped["ledger_lines"] += 1
                continue
            if isinstance(row, dict) and isinstance(row.get("ts"), (int, float)):
                rows.append(row)
            else:
                skipped["ledger_lines"] += 1
    return rows


def load_runs(events_dir: str, since: float, skipped: collections.Counter) -> list[dict]:
    """Every closed run in the event stream, any verdict."""
    runs = []
    for path in glob.glob(os.path.join(events_dir, "*.jsonl")):
        if os.path.getmtime(path) < since:
            continue
        evs = []
        with open(path, errors="replace") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    skipped["event_lines"] += 1
                    continue
                if not isinstance(r, dict) or r.get("event") not in (
                    "run_open",
                    "dispatch",
                    "run_close",
                ):
                    continue
                t = _aware(r.get("ts"))
                if t is None:
                    skipped["event_lines"] += 1
                    continue
                evs.append((t, r))
        evs.sort(key=lambda x: x[0])
        stack: list[dict] = []
        for t, r in evs:
            if r["event"] == "run_open":
                stack.append(
                    {"sid": r.get("sid"), "command": r.get("command"), "open": t, "dispatches": 0}
                )
            elif r["event"] == "dispatch":
                if stack and r.get("command") in (None, stack[-1]["command"]):
                    stack[-1]["dispatches"] += 1
            else:
                idx = next(
                    (
                        i
                        for i in range(len(stack) - 1, -1, -1)
                        if stack[i]["command"] == r.get("command")
                    ),
                    None,
                )
                if idx is None:
                    continue
                run = stack[idx]
                del stack[idx:]
                run["close"] = t
                run["verdict"] = r.get("verdict")
                runs.append(run)
    return runs


def seat_segments(
    path: str, gap_s: float, skipped: collections.Counter
) -> list[tuple[dt.datetime, dt.datetime]]:
    """A seat transcript's active segments: two consecutive timestamps more than gap_s apart split it."""
    stamps = []
    with open(path, errors="replace") as fh:
        for line in fh:
            if '"timestamp"' not in line:
                continue
            try:
                t = _aware(json.loads(line).get("timestamp"))
            except (ValueError, AttributeError):
                t = None
            if t is None:
                skipped["transcript_stamps"] += 1
                continue
            stamps.append(t)
    stamps.sort()
    segs: list[list[dt.datetime]] = []
    for t in stamps:
        if segs and (t - segs[-1][1]).total_seconds() <= gap_s:
            segs[-1][1] = t
        else:
            segs.append([t, t])
    return [(a, b) for a, b in segs]


def union_seconds(intervals: list[tuple[dt.datetime, dt.datetime]]) -> float:
    total, cur = 0.0, None
    for a, b in sorted(intervals):
        if cur is None or a > cur[1]:
            if cur:
                total += (cur[1] - cur[0]).total_seconds()
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        total += (cur[1] - cur[0]).total_seconds()
    return total


def seat_index(roots: list[str], sids: set[str]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = collections.defaultdict(list)
    seen = set()
    for root in roots:
        for path in glob.glob(os.path.join(root, "*", "*", "subagents", "*.jsonl")):
            sid = os.path.basename(os.path.dirname(os.path.dirname(path)))
            real = os.path.realpath(path)
            if sid in sids and real not in seen:
                seen.add(real)
                index[sid].append(real)
    return index


def per_run(
    runs: list[dict], seats: dict[str, list[str]], gap_s: float, skipped: collections.Counter
) -> list[dict]:
    """One row per run: wall and both seat figures, so a nightly job can store them before pruning."""
    cache: dict[str, list] = {}
    out = []
    for run in runs:
        o, c = run["open"], run["close"]
        clipped = []
        for path in seats.get(run["sid"], []):
            if path not in cache:
                cache[path] = seat_segments(path, gap_s, skipped)
            mine = [(max(o, a), min(c, b)) for a, b in cache[path] if a < c and b > o]
            if mine:
                clipped.append(mine)
        out.append(
            {
                "sid": run["sid"],
                "command": run["command"],
                "open": o.isoformat(),
                "close": c.isoformat(),
                "verdict": run.get("verdict"),
                "dispatches": run["dispatches"],
                "wall_s": (c - o).total_seconds(),
                "seats": len(clipped),
                "seat_s": union_seconds([iv for s in clipped for iv in s]) if clipped else None,
                "seat_sum_s": sum(union_seconds(s) for s in clipped) if clipped else None,
            }
        )
    return out


def commit_count(
    repos: set[str], start: dt.datetime, end: dt.datetime
) -> tuple[int, list[str], list[str], list[str]]:
    """Trailered commits in [start, end) on any branch or remote, one per sha per git common dir.

    Returns (count, common dirs read, paths gone, failures). A removed `.claude/worktrees/<name>`
    path is read through its main checkout, which holds its branches; any other path no longer on
    disk is listed as gone. A path that is not a git repo, or whose `git log` exits non-zero, is a
    failure. Both undercount, which reads as MORE runs per commit, so each is listed beside the
    number, never swallowed.
    """
    commons: dict[str, str] = {}
    gone, errors = [], []
    for repo in sorted(r for r in repos if r):
        if not os.path.isdir(repo):
            main_checkout = repo.split("/.claude/worktrees/")[0]
            if main_checkout != repo and os.path.isdir(main_checkout):
                repo = main_checkout
            else:
                gone.append(repo)
                continue
        p = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
        )
        if p.returncode:
            errors.append(repo)
            continue
        commons.setdefault(p.stdout.strip(), repo)
    shas: set[tuple[str, str]] = set()
    for common, repo in commons.items():
        # No --since/--until: git stops walking at the first commit older than --since, so a branch
        # tip committed before the window hides every in-window commit behind it. The window is
        # applied to the committer time below instead.
        p = subprocess.run(
            [
                "git",
                "-C",
                repo,
                "log",
                "--branches",
                "--remotes",
                "--no-merges",
                "--format=%H%x1f%ct%x1f%(trailers:key=Agent-Role,valueonly,separator=%x2c)%x1e",
            ],
            capture_output=True,
            text=True,
        )
        if p.returncode:
            errors.append(common)
            continue
        for rec in p.stdout.split("\x1e"):
            sha, _, rest = rec.strip("\n").partition("\x1f")
            ct, _, role = rest.partition("\x1f")
            if (
                sha
                and role.strip()
                and ct.isdigit()
                and start.timestamp() <= int(ct) < end.timestamp()
            ):
                shas.add((common, sha))
    return len(shas), sorted(commons), gone, errors


def measure(
    ledger: list[dict],
    rows: list[dict],
    commands: tuple[str, ...],
    start: dt.datetime,
    end: dt.datetime,
    commits: int | None,
) -> dict:
    lo, hi = start.timestamp(), end.timestamp()
    out: dict = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "commits": commits,
        "commands": {},
    }
    for cmd in commands:
        closes = [r for r in ledger if r.get("command") == cmd and lo <= r["ts"] < hi]
        states = collections.Counter(str(r.get("state")) for r in closes)
        wall = [r["wall_s"] / 60 for r in closes if isinstance(r.get("wall_s"), (int, float))]
        rounds = [float(r["rounds"]) for r in closes if isinstance(r.get("rounds"), int)]
        items: dict[str, float] = collections.defaultdict(float)
        item_closes: collections.Counter = collections.Counter()
        for r in closes:
            ids = WORK_ID.findall(str(r.get("surface") or ""))
            if ids:
                item_closes[ids[0]] += 1
                if isinstance(r.get("wall_s"), (int, float)):
                    items[ids[0]] += r["wall_s"] / 60
        # A close with no commit writes a placeholder "0" beside this marker (command_run.py's lane close).
        loc = [
            float(r["loc_added"])
            for r in closes
            if str(r.get("loc_added") or "").isdigit() and r.get("oversized_mini") != NO_COMMIT
        ]
        runs = [
            r
            for r in rows
            if r["command"] == cmd and lo <= dt.datetime.fromisoformat(r["close"]).timestamp() < hi
        ]
        seated = [r for r in runs if r["dispatches"] and r["seat_s"] is not None]
        seated_wall = sum(r["wall_s"] for r in seated)
        out["commands"][cmd] = {
            "closes": len(closes),
            "states": dict(states),
            "non_done_share": (len(closes) - states.get("done", 0)) / len(closes)
            if closes
            else None,
            "wall_min": _stats(wall),
            "wall_n_unreadable": len(closes) - len(wall),
            "rounds": _stats(rounds),
            "item_wall_min": _stats(list(items.values())),
            "closes_without_item": len(closes) - sum(item_closes.values()),
            "item_closes": _stats([float(n) for n in item_closes.values()]),
            "runs_per_commit": (len(closes) / commits) if commits else None,
            "loc_added": _stats(loc),
            "seat_min": _stats([r["seat_s"] / 60 for r in seated]),
            "seat_sum_min": _stats([r["seat_sum_s"] / 60 for r in seated]),
            "seat_share": (sum(r["seat_s"] for r in seated) / seated_wall)
            if seated_wall > 0
            else None,
            "dispatched_runs": sum(1 for r in runs if r["dispatches"]),
        }
    return out


def windows(
    start: str | None, end: str | None, days: int, count: int
) -> list[tuple[dt.datetime, dt.datetime]]:
    span = dt.timedelta(days=days)
    e = _aware(end) if end else None
    if end and e is None:
        raise SystemExit("--end needs ISO 8601 with a UTC offset")
    if start:
        s = _aware(start)
        if s is None:
            raise SystemExit("--start needs ISO 8601 with a UTC offset")
        e = e or s + span
        if s >= e:
            raise SystemExit("--start must precede --end")
        return [(s, e)]
    e = e or dt.datetime.now(dt.UTC)
    return [(e - span * (k + 1), e - span * k) for k in reversed(range(count))]


def _fmt(st: dict) -> str:
    if not st.get("n"):
        return "n 0"
    return f"median {st['median']:.1f} · mean {st['mean']:.1f} · p90 {st['p90']:.1f} · n {st['n']}"


def _ratio(value: float | None, unset: str) -> str:
    return f"{value:.3f}" if value is not None else unset


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="The lean program's time measure (D-1219), per command and window."
    )
    ap.add_argument(
        "--end", help="window end, ISO 8601 with a UTC offset (default: now, or --start + --days)"
    )
    ap.add_argument(
        "--start", help="one window starting here: [start, start + days) or [start, end)"
    )
    ap.add_argument("--days", type=int, default=None, help="window length in days (default 14)")
    ap.add_argument(
        "--windows", type=int, default=1, help="equal windows ending at --end, oldest first"
    )
    ap.add_argument("--commands", default=",".join(DEFAULT_COMMANDS))
    ap.add_argument(
        "--state",
        action="append",
        help="count only closes in this state (repeatable; default every state)",
    )
    ap.add_argument(
        "--gap-min",
        type=float,
        default=10.0,
        help="a seat idle longer than this many minutes is cut",
    )
    ap.add_argument("--no-commits", action="store_true", help="skip the git commit count")
    ap.add_argument("--ledger", default=os.path.join(STATE, "command-feedback.jsonl"))
    ap.add_argument("--events", default=os.path.join(STATE, "events"))
    ap.add_argument("--projects", action="append", help="a transcript projects root (repeatable)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--per-run", action="store_true", help="add one row per event-stream run to the JSON"
    )
    a = ap.parse_args(argv)
    if a.start and a.end and a.days is not None:
        ap.error("--start with --end names the window; drop --days")
    if a.start and a.windows != 1:
        ap.error("--start names one window; drop --windows")
    days = 14 if a.days is None else a.days
    if days < 1 or a.windows < 1 or a.gap_min <= 0:
        ap.error("--days and --windows must be >= 1 and --gap-min > 0")
    commands = tuple(c.strip() for c in a.commands.split(",") if c.strip())
    wins = windows(a.start, a.end, days, a.windows)
    roots = a.projects or sorted(
        {os.path.realpath(p) for p in glob.glob(os.path.expanduser("~/.claude-fleet/*/projects"))}
        | {os.path.realpath(os.path.expanduser("~/.claude/projects"))}
    )
    missing = [p for p in [a.events, *roots] if not os.path.isdir(p)]
    if missing:
        raise SystemExit(f"not a directory: {', '.join(missing)}")
    skipped: collections.Counter = collections.Counter()
    ledger = [r for r in load_ledger(a.ledger, skipped) if r.get("command") in commands]
    runs = [
        r for r in load_runs(a.events, wins[0][0].timestamp(), skipped) if r["command"] in commands
    ]
    if a.state:
        ledger = [r for r in ledger if r.get("state") in a.state]
        runs = [r for r in runs if r.get("verdict") in a.state]
    rows = per_run(runs, seat_index(roots, {r["sid"] for r in runs}), a.gap_min * 60, skipped)
    repos = {r.get("repo") for r in ledger}  # ONE repo set for every window, so windows compare
    report: dict = {
        "params": {
            "commands": list(commands),
            "states": a.state or [],
            "gap_min": a.gap_min,
            "days": days,
        },
        "windows": [],
    }
    for s, e in wins:
        commits, read, gone, failed = (
            (None, [], [], []) if a.no_commits else commit_count(repos, s, e)
        )
        w = measure(ledger, rows, commands, s, e, commits)
        w["commit_repos"], w["repos_gone"], w["commit_errors"] = read, gone, failed
        report["windows"].append(w)
    report["skipped"] = dict(skipped)
    if a.per_run:
        lo, hi = wins[0][0], wins[-1][1]
        report["closes"] = [
            {
                k: r.get(k)
                for k in (
                    "sid",
                    "command",
                    "state",
                    "ts",
                    "wall_s",
                    "rounds",
                    "surface",
                    "loc_added",
                    "oversized_mini",
                    "repo",
                )
            }
            for r in ledger
            if lo.timestamp() <= r["ts"] < hi.timestamp()
        ]
        report["runs"] = [r for r in rows if lo <= dt.datetime.fromisoformat(r["close"]) < hi]
    if a.json:
        json.dump(report, sys.stdout, indent=1, default=str)
        print()
        return 0
    for w in report["windows"]:
        head = f"window {w['start']} .. {w['end']} · "
        head += (
            "commits not counted"
            if w["commits"] is None
            else f"commits {w['commits']} from {len(w['commit_repos'])} repos"
        )
        if w["repos_gone"]:
            head += f" · {len(w['repos_gone'])} ledger repo paths no longer on disk (see --json repos_gone)"
        print(
            head
            + (f" · git FAILED for {', '.join(w['commit_errors'])}" if w["commit_errors"] else "")
        )
        for cmd, m in w["commands"].items():
            if not m["closes"]:
                print(f"  {cmd}: closes 0")
                continue
            print(
                f"  {cmd}: closes {m['closes']} {m['states']} · non-done {m['non_done_share'] * 100:.1f}%"
            )
            share = m["seat_share"]
            print(
                f"    wall-clock min  {_fmt(m['wall_min'])}"
                + (
                    f" · {m['wall_n_unreadable']} closes without a numeric wall_s"
                    if m["wall_n_unreadable"]
                    else ""
                )
            )
            print(
                f"    seat-minutes    {_fmt(m['seat_min'])} (of {m['dispatched_runs']} runs with a dispatch)"
                + (f" · {share * 100:.1f}% of those runs' wall-clock" if share is not None else "")
            )
            print(f"    seat sum min    {_fmt(m['seat_sum_min'])}")
            print(f"    rounds          {_fmt(m['rounds'])}")
            print(
                f"    per work item   {_fmt(m['item_wall_min'])} · closes without an id {m['closes_without_item']}"
            )
            print(f"    closes per item {_fmt(m['item_closes'])}")
            print(
                f"    runs per commit {_ratio(m['runs_per_commit'], 'not counted' if w['commits'] is None else 'no commits')}"
            )
            print(f"    surface loc     {_fmt(m['loc_added'])}")
    if report["skipped"]:
        print(
            "skipped (unparseable): "
            + ", ".join(f"{k} {v}" for k, v in sorted(report["skipped"].items()))
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
