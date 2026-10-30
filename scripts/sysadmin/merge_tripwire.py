#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/kaizen.md, tests/test_merge_tripwire.py
"""The merge program's daily tripwire (W-622ec42c, D-1384, D-1385) — kaizen's measure of the merge path.

Three readings per LOCAL day, from records that already exist:

1. **Wall time per merged request** — from the request (its id is the request mail's 26-character ULID,
   whose first 10 characters encode the send instant in ms) to the record's last write
   (``merge_request.py`` rewrites the record at its reply, the end of the requester's wait). Median and
   max of the merged requests, bucketed by REQUEST day; a request still in flight counts as pending.
2. **Refusals by class** — every refusal EVENT, classed by ``refusal_class`` (ledger-conflict ·
   conflict · tests-red · test-budget · dirty-main · preflight · other): a record's ``outcome: refused``
   and every earlier refusal its ``retries`` list keeps (``merge_request.py retry`` rewrites the record
   and moves the old reason there), for the day and the 14 days ending on it (D-1385's "under 5
   refusals per 14 days, zero ledger-conflict").
3. **The red-master series before and after the post-merge valve** — ``waste_red_master_rework``
   (published daily by ``kaizen_waste.py``) pooled as Σ red-master fixes / Σ arrivals over the 14 days
   before the valve day versus the 7 newest days after it. The valve day is the first commit on
   ``$MERGE_TRIPWIRE_REF`` (default ``origin/master``) whose ``.fabrik/merge-tests`` carries
   ``# merge-tests-after-merge-above: 0`` in ``merge_request.py``'s own grammar (``VALVE_RE``) and still
   holds at its tip; with no such commit the valve is OFF and only the "before" level prints.

**The tripwire (D-1384, "7 days running" in W-622ec42c's words):** the 14 pre-valve days are all
published, and on EACH of the last 7 days the trailing week (all post-valve, all published) carries more
red-master fixes than the pre-valve rate predicts for its arrivals by over 2 sigma (Poisson; the
margin's measured effect is in the D-row). Then the series has risen for a week — one mail to the repo's
coordinator per episode (an episode is a run of consecutive tripped days; a day whose row is missing
starts a new one, since a duplicate mail is cheaper than a silent one), saying the threshold goes back
to 40.

Outputs, both under the repo's merge-record directory (``<git common dir>/fabrik-merge/``) so a
project's coordinator reads its own repo's numbers: ``tripwire.jsonl`` (one row per day, rewritten on
each publish of that day) and ``tripwire-line.txt`` (the one line ``work.py prompt_block`` shows a
coordinator). ``publish_recent`` re-publishes the two days before the given one too, so a request
that settles a day late is counted.

Honesty: a record that cannot be read or whose id is not a ULID is counted as ``unreadable`` and
printed, never dropped; a red-master day not yet published is missing, never 0, and a missing day
blocks the tripwire rather than firing it; a valve lookup that fails prints ``unmeasured``, never
"valve not on yet". Record times come from the file's mtime: a tool that rewrote an old record would
move its reply instant — none does today (``merge_request.py`` writes a record only while it owns it).

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
import math
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
MAIL_TIMEOUT_S = 60
PRE_DAYS = 14  # the pre-valve level pools this many days before the valve day
WEEK = 7  # D-1384: a rise "for a week"
REFUSAL_WINDOW = 14  # D-1385: "under 5 refusals per 14 days"
RETRY_DAYS = 3  # publish_recent: the day and the two before it (a late-settling request)
RED_METRIC = "waste_red_master_rework"
# merge_request._AFTER_DECL_RE verbatim, first match read like _after_threshold: a line the merge does not
# honour is never "valve on" here (tests/test_merge_tripwire.py pins the two patterns equal)
VALVE_RE = re.compile(r"(?m)^#[ \t]*merge-tests-after-merge-above:[ \t]*([0-9]{1,4})[ \t\r]*$")
LEDGERS = (
    "CHANGELOG.md",
    "docs/DECISIONS.md",
    "INDEX.md",
    "docs/STRATEGIC_BACKLOG.md",
    "docs/LESSONS_LEARNT.md",
)  # merge_request.LEDGERS, plus the work-item files below
_ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# git show's two wordings for a path absent at a commit; any other failure is an unknown, never "off"
_ABSENT_RE = re.compile(r"does not exist in|exists on disk, but not in")


class ValveUnknownError(RuntimeError):
    """The valve lookup failed: the valve's state is unknown, never "off"."""


def repo_root(repo: Path | None = None) -> Path:
    # the env wins over the caller's repo: tests/conftest.py pins it so no grader reaches the live repo
    return Path(os.environ.get("MERGE_TRIPWIRE_REPO") or repo or REPO)


def _git(args: list[str], repo: Path | None = None) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo_root(repo)), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def records_dir(repo: Path | None = None) -> Path:
    common = Path(_git(["rev-parse", "--git-common-dir"], repo).strip())
    return (common if common.is_absolute() else repo_root(repo) / common) / "fabrik-merge"


def ulid_time(ulid: str) -> float | None:
    """The send instant a 26-character ULID encodes, or None for anything else."""
    if not isinstance(ulid, str) or len(ulid) != 26:
        return None
    n = 0
    for c in ulid[:10].upper():
        i = _ULID.find(c)
        if i < 0:
            return None
        n = n * 32 + i
    return n / 1000


def _local_day(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).astimezone().date().isoformat()


def refusal_class(reason: str) -> str:
    """One class per refusal reason, first match wins (the reason strings merge_request.py writes)."""
    if "owner tests red" in reason:
        return "tests-red"
    if "owner-test budget" in reason:  # "… ran out during the leg … — not a test verdict"
        return "test-budget"
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
    """One event per merged request, per refusal (the record's own and each kept in ``retries``) and
    per request still in flight (``pending``), plus one ``unreadable`` event per record that cannot be
    read or carries no ULID id — counted and shown, never dropped. A missing directory is []."""
    out: list[dict] = []
    for p in sorted(rdir.glob("*.json")) if rdir.is_dir() else []:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            end = p.stat().st_mtime
        except (OSError, ValueError):
            rec, end = None, 0.0
        start = ulid_time(str(rec.get("id") or p.stem)) if isinstance(rec, dict) else None
        try:
            day = _local_day(start) if start is not None else None
        except (ValueError, OverflowError, OSError):  # a ULID past year 9999
            day = None
        if day is None:
            out.append({"day": None, "outcome": "unreadable", "wall_s": None, "cls": ""})
            continue
        for retry in rec.get("retries") or []:
            if isinstance(retry, dict):
                cls = refusal_class(str(retry.get("reason") or ""))
                out.append({"day": day, "outcome": "refused", "wall_s": None, "cls": cls})
        # settled only once replied: merge_request.py sets `outcome` before the reply mail, and a
        # failed reply leaves the record unreplied until `resume`
        outcome = rec.get("outcome") if rec.get("phase") == "replied" else None
        if outcome == "merged":
            out.append(
                {"day": day, "outcome": "merged", "wall_s": max(0.0, end - start), "cls": ""}
            )
        elif outcome == "refused":
            cls = refusal_class(str(rec.get("reason") or ""))
            out.append({"day": day, "outcome": "refused", "wall_s": None, "cls": cls})
        else:
            out.append({"day": day, "outcome": "pending", "wall_s": None, "cls": ""})
    return out


def valve_day(ref: str, repo: Path | None = None) -> str | None:
    """Local day of the commit on ``ref`` that turned the valve on for every merge (threshold 0) and
    whose setting still holds at ``ref``'s tip; None while it is off there (never set, set back to
    40 — D-1384's own remedy — or the file deleted). A failed lookup raises ValveUnknownError."""
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
            ],
            repo,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise ValveUnknownError(str(exc)) from exc
    since: str | None = None  # the day the current on-run began
    for entry in log.splitlines():
        sha, ct = entry.split()
        try:
            text = _git(["show", f"{sha}:.fabrik/merge-tests"], repo)
        except RuntimeError as exc:
            if not _ABSENT_RE.search(str(exc)):
                raise ValveUnknownError(str(exc)) from exc
            text = ""  # the file is absent at this commit (a deletion): the valve is off
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValveUnknownError(str(exc)) from exc
        decl = VALVE_RE.search(text)
        on = bool(decl) and int(decl.group(1)) == 0
        if on and since is None:
            since = _local_day(float(ct))
        elif not on:
            since = None
    return since


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
    for raw in files[-1].read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
            out[str(row["day"])] = (float(row["numerator"]), float(row["denominator"]))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def _days(end: str, n: int) -> list[str]:
    d = dt.date.fromisoformat(end)
    return [(d - dt.timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _pooled(series: dict[str, tuple[float, float]], days: list[str]) -> tuple[float | None, int]:
    """(Σ numerator / Σ denominator, days published) — the rate is None unless EVERY day is published
    and the window saw at least one arrival: a partial window is unmeasured, never a level."""
    rows = [series[d] for d in days if d in series]
    den = sum(r[1] for r in rows)
    rate = sum(r[0] for r in rows) / den if den and len(rows) == len(days) else None
    return rate, len(rows)


def red_master(
    day: str, valve: str | None, series: dict[str, tuple[float, float]], error: str = ""
) -> dict:
    """The pre-valve level, the post-valve week and whether the week tripped (every day of both
    windows published, the week pooled above the level). ``error`` is a failed valve lookup."""
    out = {
        "valve_day": valve,
        "error": error,
        "pre": None,
        "pre_days": 0,
        "week": None,
        "week_days": 0,
        "tripped": False,
    }
    if error:
        return out
    before_end = (dt.date.fromisoformat(valve) - dt.timedelta(days=1)).isoformat() if valve else day
    out["pre"], out["pre_days"] = _pooled(series, _days(before_end, PRE_DAYS))
    if not valve:
        return out
    week = [d for d in _days(day, WEEK) if d > valve]
    out["week"], out["week_days"] = _pooled(series, week)
    # "rises … for a week" (D-1384), read as W-622ec42c words it, "7 days running": the trailing week
    # ending on EACH of the last 7 days is above the level by more than Poisson noise
    out["tripped"] = out["pre"] is not None and all(
        _risen(series, end, valve, out["pre"]) for end in _days(day, WEEK)
    )
    return out


def _risen(series: dict[str, tuple[float, float]], end: str, valve: str, pre: float) -> bool:
    """The 7 days ending on ``end`` are all after the valve and published, and their red-master count
    exceeds what the pre-valve rate predicts for their arrivals by more than 2 sigma (Poisson): a
    one-event wobble on 80–420 arrivals a day is not a rise."""
    days = _days(end, WEEK)
    if days[0] <= valve or any(d not in series for d in days):
        return False
    num = sum(series[d][0] for d in days)
    den = sum(series[d][1] for d in days)
    if not den:
        return False
    expected = pre * den
    return num > expected + 2 * math.sqrt(max(expected, 1.0))


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
        "pending": sum(1 for r in mine if r["outcome"] == "pending"),
        "unreadable": sum(1 for r in records if r["outcome"] == "unreadable"),
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
    """One line, verdict first and the variable-length class list last: the prompt block clips a long
    line from its END (work.LINE_MAX)."""
    red = m["red_master"]
    if red["error"]:
        rm = "red-master unmeasured (valve lookup failed)"
    elif red["valve_day"]:
        rm = (
            f"red-master week {_pct(red['week'])} ({red['week_days']}/{WEEK} d) vs pre-valve "
            f"{_pct(red['pre'])} ({red['pre_days']}/{PRE_DAYS} d), valve on {red['valve_day']}"
        )
    else:
        rm = f"red-master pre-valve {_pct(red['pre'])} ({red['pre_days']}/{PRE_DAYS} d), valve not on yet"
    head = "TRIPPED, threshold back to 40 (D-1384) — " if red["tripped"] else ""
    extra = "".join(
        f", {m[k]} {k}" for k in ("pending", "unreadable") if m.get(k)
    )  # an unknown is shown, never folded into 0
    cls = ", ".join(f"{k} {v}" for k, v in m["refusal_classes_14d"].items()) or "none"
    return (
        f"{head}merge tripwire {m['day']}: {m['merged']} merged{extra}, wall median "
        f"{_mins(m['wall_median_s'])} max {_mins(m['wall_max_s'])} · {rm} · refused {m['refused']} "
        f"(14 d: {m['refused_14d']} — {cls})"
    )


def compute(day: str, state: Path | None = None, repo: Path | None = None) -> dict:
    ref = os.environ.get("MERGE_TRIPWIRE_REF") or "origin/master"
    try:
        valve, error = valve_day(ref, repo), ""
    except ValveUnknownError as exc:
        kc._warn(f"merge tripwire: valve lookup failed: {exc}")
        valve, error = None, str(exc)[:200]
    return measure(
        day, load_records(records_dir(repo)), red_master(day, valve, red_series(state), error)
    )


def _mail(m: dict) -> bool:
    """Send the tripped mail; any failure (a timeout included) is False, so the next day retries."""
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
            f"WHEN: on each of the last {WEEK} days the trailing week after the valve carried more "
            "red-master fixes than the pre-valve rate predicts, by over 2 sigma.",
            "WHO: the coordinator (the merge owner) decides the threshold change; kaizen measured it.",
            "WHY: D-1384 kept the valve on only while the series does not rise past its pre-valve "
            "level for a week; this is that rise.",
            "HOW: set merge-tests-after-merge-above back to 40 in .fabrik/merge-tests, or rule "
            "otherwise in a new D-row.",
            f"SYSTEMIC: {line(m)}",
        ]
    )
    try:
        r = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "mail.py"),
                "send",
                "--to",
                os.environ.get("MERGE_TRIPWIRE_MAILBOX") or m.get("mailbox") or "fabrik",
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
            timeout=MAIL_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        kc._warn(f"merge tripwire: mail failed: {exc!r}")
        return False
    if r.returncode != 0:
        kc._warn(f"merge tripwire: mail failed rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.returncode == 0


def _read_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(raw)
                rows[str(row["day"])] = row
            except (ValueError, KeyError, TypeError):
                continue
    return rows


def publish(
    day: str,
    state: Path | None = None,
    repo: Path | None = None,
    mail: bool = True,
    today: str | None = None,
) -> dict:
    """Compute the day, (re)write its row and, when it is the newest day, the line; mail once per
    tripped episode. Only a complete day publishes — today and later are refused."""
    today = today or dt.date.today().isoformat()
    if day >= today:
        raise ValueError(
            f"refusing to publish {day}: only days before today ({today}) are complete"
        )
    m = compute(day, state, repo)
    rdir = records_dir(repo)
    rdir.mkdir(parents=True, exist_ok=True)
    m["mailbox"] = rdir.parent.parent.name  # <repo>/.git/fabrik-merge → the repo's own mailbox
    rows_path = rdir / "tripwire.jsonl"
    rows = _read_rows(rows_path)
    tripped = m["red_master"]["tripped"]
    prev = rows.get((dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat())
    # the episode's mail: already sent today (a re-publish), or by the previous calendar day of the
    # same episode; a missing previous row starts a new episode
    sent = bool(rows.get(day, {}).get("mailed")) or bool(
        prev and prev.get("red_master", {}).get("tripped") and prev.get("mailed")
    )
    m["mailed"] = tripped and (sent or (mail and _mail(m)))
    rows[day] = m
    tmp = rows_path.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "".join(
            json.dumps(rows[d], ensure_ascii=False, separators=(",", ":")) + "\n"
            for d in sorted(rows)
        ),
        encoding="utf-8",
    )
    tmp.replace(rows_path)
    if day == max(rows):
        tmp = rdir / "tripwire-line.txt.tmp"
        tmp.write_text(line(m) + "\n", encoding="utf-8")
        tmp.replace(rdir / "tripwire-line.txt")
    return m


def publish_recent(
    day: str, state: Path | None = None, repo: Path | None = None, mail: bool = True
) -> list[dict]:
    """The daily hook's entry: the RETRY_DAYS days ending on ``day``, oldest first, so a request that
    settled after its day's first publish is counted on the next run."""
    d = dt.date.fromisoformat(day)
    return [
        publish((d - dt.timedelta(days=back)).isoformat(), state, repo, mail)
        for back in range(RETRY_DAYS - 1, -1, -1)
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--day", required=True, type=lambda v: dt.date.fromisoformat(v).isoformat())
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--no-mail", action="store_true", help="publish without the tripped mail")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    m = publish(a.day, mail=not a.no_mail) if a.publish else compute(a.day)
    print(json.dumps(m, indent=2) if a.json else line(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
