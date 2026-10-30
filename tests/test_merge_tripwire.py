"""The merge program's daily tripwire (W-622ec42c, D-1384, D-1385): wall time per merged request,
refusals by class, and the red-master series before/after the post-merge valve, with one mail to the
coordinator per tripped episode.

Every test runs on a throwaway git repo (``MERGE_TRIPWIRE_REPO``) whose ``.git/fabrik-merge`` holds
hand-written records, and a tmp kaizen store — never live state, never a real mail.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))
sys.path.insert(0, str(REPO / "scripts"))

import merge_tripwire as mt  # noqa: E402
import work  # noqa: E402

_ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid(ts: float) -> str:
    n, out = int(ts * 1000), ""
    for _ in range(10):
        out = _ULID[n % 32] + out
        n //= 32
    return out + "0" * 16


def _ts(day: str, hour: int = 12) -> float:
    return dt.datetime.fromisoformat(f"{day}T{hour:02d}:00:00").astimezone().timestamp()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "master")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "README.md").write_text("x\n")
    _git(r, "add", "README.md")
    _git(r, "commit", "-qm", "init")
    monkeypatch.setenv("MERGE_TRIPWIRE_REPO", str(r))
    monkeypatch.setenv("MERGE_TRIPWIRE_REF", "master")
    (r / ".git" / "fabrik-merge").mkdir()
    return r


def _record(repo: Path, start: float, wall_s: float, outcome: str, reason: str = "") -> None:
    rid = _ulid(start)
    rec = {"id": rid, "outcome": outcome, "phase": "replied"}
    if reason:
        rec["reason"] = reason
    p = repo / ".git" / "fabrik-merge" / f"{rid}.json"
    p.write_text(json.dumps(rec))
    os.utime(p, (start + wall_s, start + wall_s))


def _series(state: Path, points: dict[str, tuple[int, int]]) -> None:
    sdir = state / "series"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "waste_red_master_rework@v1.jsonl").write_text(
        '{"day":"2000-01-01","numerator":99,"denominator":1}\n'
    )
    (sdir / "waste_red_master_rework@v2.jsonl").write_text(
        "".join(
            json.dumps({"day": d, "numerator": n, "denominator": den}) + "\n"
            for d, (n, den) in sorted(points.items())
        )
    )


def _days(start: str, n: int) -> list[str]:
    d = dt.date.fromisoformat(start)
    return [(d + dt.timedelta(days=i)).isoformat() for i in range(n)]


# ── refusal classes ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reason", "cls"),
    [
        (
            "(a)-(d) build, preflight, tests, CAS: owner tests red (pytest tests/x.py, exit 1)",
            "tests-red",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: CHANGELOG.md: a side edits an existing line at a conflict — merge master",
            "ledger-conflict",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: conflict in .fabrik/work/W-aeb35e3a.json — merge master",
            "ledger-conflict",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: .fabrik/work/W-641ac619.json: merge-item: both sides changed owner",
            "ledger-conflict",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: D-616 collides in docs/DECISIONS.md — re-mint and resend",
            "ledger-conflict",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: conflict in docs/DECISIONS.md, scripts/x.py — merge master",
            "conflict",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: conflict in docs/workstation/hooks-index.md — merge master",
            "conflict",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: scripts/x.py is dirty in the main checkout (not a ledger)",
            "dirty-main",
        ),
        (
            "(a)-(d) build, preflight, tests, CAS: CHANGELOG.md is staged differently from HEAD in the main checkout",
            "dirty-main",
        ),
        ("(a) preflight: git fetch -q timed out after 60s", "preflight"),
        ("something new", "other"),
    ],
)
def test_refusal_class(reason, cls):
    assert mt.refusal_class(reason) == cls


# ── wall time and refusal counts ─────────────────────────────────────────────────────


def test_wall_time_runs_from_the_request_to_the_reply_bucketed_by_request_day(repo, tmp_path):
    day = "2026-10-20"
    _record(repo, _ts(day, 9), 600, "merged")
    _record(repo, _ts(day, 10), 1800, "merged")
    _record(repo, _ts(day, 11), 3000, "merged")
    _record(repo, _ts(day, 23), 7200, "merged")  # replied the next day: still the request's day
    _record(repo, _ts(day, 12), 60, "refused", "(a) preflight: git fetch -q timed out after 60s")
    _record(repo, _ts("2026-10-10", 12), 60, "refused", "conflict in CHANGELOG.md — x")
    _record(repo, _ts("2026-10-01", 12), 60, "refused", "owner tests red")  # outside 14 days
    _record(repo, _ts("2026-10-21", 12), 60, "merged")  # another day
    m = mt.compute(day, state=tmp_path / "state")
    assert (m["merged"], m["wall_median_s"], m["wall_max_s"]) == (4, 2400, 7200)
    assert m["refused"] == 1 and m["refusal_classes"] == {"preflight": 1}
    assert m["refused_14d"] == 2
    assert m["refusal_classes_14d"] == {"ledger-conflict": 1, "preflight": 1}


def test_an_unsettled_or_unreadable_record_is_skipped(repo, tmp_path):
    day = "2026-10-20"
    rdir = repo / ".git" / "fabrik-merge"
    (rdir / f"{_ulid(_ts(day))}.json").write_text(
        json.dumps({"id": _ulid(_ts(day)), "phase": "build"})
    )
    (rdir / "broken.json").write_text("{")
    m = mt.compute(day, state=tmp_path / "state")
    assert m["merged"] == 0 and m["wall_median_s"] is None and m["refused"] == 0


# ── the valve and the red-master week ────────────────────────────────────────────────


def _valve(repo: Path, value: str, when: float) -> None:
    (repo / ".fabrik").mkdir(exist_ok=True)
    (repo / ".fabrik" / "merge-tests").write_text(
        f"# merge-tests-after-merge-above: {value}\ntests/\n"
    )
    _git(repo, "add", ".fabrik/merge-tests")
    env = {**os.environ, "GIT_COMMITTER_DATE": f"@{int(when)}", "GIT_AUTHOR_DATE": f"@{int(when)}"}
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"valve {value}"], check=True, env=env)


def test_the_valve_day_is_the_first_commit_setting_the_threshold_to_zero(repo):
    assert mt.valve_day("master") is None
    _valve(repo, "40", _ts("2026-10-25"))
    assert mt.valve_day("master") is None  # D-1186's 40 is not the valve D-1384 turned on
    _valve(repo, "0", _ts("2026-10-31"))
    assert mt.valve_day("master") == "2026-10-31"


def test_without_the_valve_only_the_pre_level_prints_and_nothing_trips(tmp_path):
    state = tmp_path / "state"
    _series(state, dict.fromkeys(_days("2026-10-01", 20), (1, 100)))
    red = mt.red_master("2026-10-20", None, mt.red_series(state))
    assert red["pre"] == pytest.approx(0.01) and red["week"] is None and not red["tripped"]


def test_a_week_above_the_pre_valve_level_trips(tmp_path):
    state = tmp_path / "state"
    pts = dict.fromkeys(_days("2026-10-17", 14), (1, 100))  # pre: 10-17 .. 10-30
    pts |= dict.fromkeys(_days("2026-10-31", 7), (2, 100))  # post: 10-31 is the valve day, excluded
    pts["2026-10-31"] = (0, 100)
    pts["2026-11-07"] = (2, 100)
    _series(state, pts)
    series = mt.red_series(state)
    red = mt.red_master("2026-11-07", "2026-10-31", series)
    assert red["pre"] == pytest.approx(0.01)
    assert red["week_days"] == 7 and red["week"] == pytest.approx(0.02) and red["tripped"]
    # six post-valve days are not a week yet
    assert not mt.red_master("2026-11-06", "2026-10-31", series)["tripped"]
    # a missing day blocks the tripwire — never read as a quiet day
    del pts["2026-11-03"]
    _series(state, pts)
    red = mt.red_master("2026-11-07", "2026-10-31", mt.red_series(state))
    assert red["week_days"] == 6 and not red["tripped"]


def test_a_week_at_or_below_the_pre_valve_level_does_not_trip(tmp_path):
    state = tmp_path / "state"
    pts = dict.fromkeys(_days("2026-10-17", 22), (1, 100))
    _series(state, pts)
    assert not mt.red_master("2026-11-07", "2026-10-31", mt.red_series(state))["tripped"]


# ── publish: the row, the line, one mail per episode ─────────────────────────────────


def _tripped_store(state: Path) -> None:
    pts = dict.fromkeys(_days("2026-10-17", 14), (1, 100))
    pts |= dict.fromkeys(_days("2026-10-31", 10), (3, 100))
    _series(state, pts)


def test_publish_mails_once_per_tripped_episode(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "0", _ts("2026-10-31"))
    sent: list[str] = []
    monkeypatch.setattr(mt, "_mail", lambda m: sent.append(m["day"]) or True)
    for day in ("2026-11-06", "2026-11-07", "2026-11-08", "2026-11-08"):
        mt.publish(day, state=state)
    assert sent == ["2026-11-07"]
    rows = (repo / ".git" / "fabrik-merge" / "tripwire.jsonl").read_text().splitlines()
    assert [json.loads(r)["day"] for r in rows] == ["2026-11-06", "2026-11-07", "2026-11-08"]
    line = (repo / ".git" / "fabrik-merge" / "tripwire-line.txt").read_text()
    assert line.startswith("TRIPPED, threshold back to 40 (D-1384) — merge tripwire 2026-11-08:")


def test_a_failed_mail_is_retried_the_next_day(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "0", _ts("2026-10-31"))
    tries: list[str] = []
    monkeypatch.setattr(mt, "_mail", lambda m: tries.append(m["day"]) or len(tries) > 1)
    mt.publish("2026-11-07", state=state)
    mt.publish("2026-11-08", state=state)
    mt.publish("2026-11-09", state=state)
    assert tries == ["2026-11-07", "2026-11-08"]


def test_an_older_day_never_overwrites_the_newest_line(repo, tmp_path):
    state = tmp_path / "state"
    _series(state, {})
    mt.publish("2026-10-20", state=state)
    mt.publish("2026-10-18", state=state)
    line = (repo / ".git" / "fabrik-merge" / "tripwire-line.txt").read_text()
    assert "merge tripwire 2026-10-20:" in line


# ── the coordinator's prompt line ────────────────────────────────────────────────────


def test_only_a_fresh_line_reaches_the_coordinators_prompt(tmp_path, monkeypatch):
    tree = tmp_path / "main"
    (tree / ".git" / "fabrik-merge").mkdir(parents=True)
    path = tree / ".git" / "fabrik-merge" / "tripwire-line.txt"
    path.write_text("merge tripwire 2026-10-30: 9 merged\n")
    monkeypatch.setattr(work, "_scans_panes", lambda t: False)
    assert work._merge_tripwire_line(tree) == ""
    monkeypatch.setattr(work, "_scans_panes", lambda t: True)
    assert work._merge_tripwire_line(tree) == "merge tripwire 2026-10-30: 9 merged"
    old = time.time() - work.MERGE_TRIPWIRE_MAX_AGE_S - 60
    os.utime(path, (old, old))
    assert work._merge_tripwire_line(tree) == ""
