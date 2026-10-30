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

import kaizen_collect_v2 as kc  # noqa: E402
import merge_tripwire as mt  # noqa: E402
import work  # noqa: E402

_ULID = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TODAY = "2026-12-01"  # every publish below is of a day before it


def _ulid(ts: float) -> str:
    n, out = int(ts * 1000), ""
    for _ in range(10):
        out = _ULID[n % 32] + out
        n //= 32
    return out + "0" * 16


def _ts(day: str, hour: int = 12) -> float:
    return dt.datetime.fromisoformat(f"{day}T{hour:02d}:00:00").astimezone().timestamp()


def _git_env() -> dict:
    # a grader run from a git hook inherits GIT_DIR/GIT_INDEX_FILE: never let them steer the tmp repo
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return env | {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env or _git_env(),
    ).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "fabrik"
    r.mkdir()
    _git(r, "init", "-q", "-b", "master")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "README.md").write_text("x\n")
    _git(r, "add", "README.md")
    _git(r, "commit", "-qm", "init")
    monkeypatch.setenv("MERGE_TRIPWIRE_REPO", str(r))
    monkeypatch.setenv("MERGE_TRIPWIRE_REF", "master")
    monkeypatch.delenv("MERGE_TRIPWIRE_MAILBOX", raising=False)
    (r / ".git" / "fabrik-merge").mkdir()
    return r


def _record(
    repo: Path,
    start: float,
    wall_s: float,
    outcome: str | None,
    reason: str = "",
    *,
    phase: str = "replied",
    retries: list | None = None,
    rid: str | None = None,
) -> None:
    rid = rid or _ulid(start)
    rec: dict = {"id": rid, "phase": phase}
    if outcome:
        rec["outcome"] = outcome
    if reason:
        rec["reason"] = reason
    if retries:
        rec["retries"] = retries
    p = repo / ".git" / "fabrik-merge" / f"{rid}.json"
    p.write_text(json.dumps(rec))
    os.utime(p, (start + wall_s, start + wall_s))


def _series(state: Path, points: dict[str, tuple[int, int]], version: int = 2) -> None:
    sdir = state / "series"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "waste_red_master_rework@v1.jsonl").write_text(
        '{"day":"2000-01-01","numerator":99,"denominator":1}\n'
    )
    (sdir / f"waste_red_master_rework@v{version}.jsonl").write_text(
        "".join(
            json.dumps({"day": d, "numerator": n, "denominator": den}) + "\n"
            for d, (n, den) in sorted(points.items())
        )
    )


def _days(start: str, n: int) -> list[str]:
    d = dt.date.fromisoformat(start)
    return [(d + dt.timedelta(days=i)).isoformat() for i in range(n)]


def _flat(start: str, n: int, num: int, den: int = 100) -> dict[str, tuple[int, int]]:
    return dict.fromkeys(_days(start, n), (num, den))


# ── refusal classes ──────────────────────────────────────────────────────────────────

_CAS = "(a)-(d) build, preflight, tests, CAS: "


@pytest.mark.parametrize(
    ("reason", "cls"),
    [
        (_CAS + "owner tests red (pytest tests/x.py, exit 1)", "tests-red"),
        (_CAS + "owner tests red (exit 1): … conflict in scripts/x.py — merge", "tests-red"),
        (_CAS + "the owner-test budget of this run (3600s) ran out during the leg", "test-budget"),
        (
            _CAS + "CHANGELOG.md: a side edits an existing line at a conflict — merge",
            "ledger-conflict",
        ),
        (_CAS + "conflict in .fabrik/work/W-aeb35e3a.json — merge master", "ledger-conflict"),
        (
            _CAS + ".fabrik/work/W-641ac619.json: merge-item: both sides changed owner",
            "ledger-conflict",
        ),
        (_CAS + "D-616 collides in docs/DECISIONS.md — re-mint and resend", "ledger-conflict"),
        (_CAS + "conflict in docs/DECISIONS.md, scripts/x.py — merge master", "conflict"),
        (_CAS + "conflict in docs/workstation/hooks-index.md — merge master", "conflict"),
        (_CAS + "scripts/x.py is dirty in the main checkout (not a ledger)", "dirty-main"),
        (_CAS + "x.md is dirty in the main checkout; conflict in y.py — merge", "dirty-main"),
        (_CAS + "CHANGELOG.md is staged differently from HEAD in the main checkout", "dirty-main"),
        ("(a) preflight: git fetch -q timed out after 60s", "preflight"),
        (_CAS + "something nobody has seen", "other"),
    ],
)
def test_refusal_class(reason, cls):
    assert mt.refusal_class(reason) == cls


# ── records: wall time, refusal events, unknowns ─────────────────────────────────────


def test_wall_time_runs_from_the_request_to_the_reply_bucketed_by_request_day(repo, tmp_path):
    day = "2026-10-20"
    _record(repo, _ts(day, 9), 600, "merged")
    _record(repo, _ts(day, 10), 1800, "merged")
    _record(repo, _ts(day, 11), 3000, "merged")
    _record(repo, _ts(day, 23), 7200, "merged")  # replied the next day: still the request's day
    _record(
        repo, _ts(day, 13), -50, "merged"
    )  # an mtime before the request clamps to 0, never negative
    _record(repo, _ts(day, 12), 60, "refused", "(a) preflight: git fetch -q timed out after 60s")
    _record(repo, _ts("2026-10-21", 12), 60, "merged")  # another day
    m = mt.compute(day, state=tmp_path / "state")
    assert (m["merged"], m["wall_median_s"], m["wall_max_s"]) == (5, 1800, 7200)
    assert m["refused"] == 1 and m["refusal_classes"] == {"preflight": 1}


def test_a_reply_written_before_its_request_is_a_zero_wall_never_negative(repo, tmp_path):
    day = "2026-10-20"
    _record(repo, _ts(day, 9), -3000, "merged")  # clock skew: the reply mtime precedes the ULID
    _record(repo, _ts(day, 10), 600, "merged")
    m = mt.compute(day, state=tmp_path / "state")
    assert m["wall_median_s"] == 300  # (0 + 600) / 2 — unclamped it would read -1200


def test_every_refusal_event_counts_the_retried_ones_included(repo, tmp_path):
    day = "2026-10-20"
    retry = [{"at": "x", "reason": _CAS + "conflict in CHANGELOG.md — merge"}]
    _record(repo, _ts(day, 9), 600, "merged", retries=retry)
    _record(repo, _ts(day, 10), 60, "refused", _CAS + "owner tests red (exit 1)", retries=retry)
    m = mt.compute(day, state=tmp_path / "state")
    assert m["merged"] == 1 and m["refused"] == 3
    assert m["refusal_classes"] == {"ledger-conflict": 2, "tests-red": 1}


def test_the_refusal_window_is_the_14_days_ending_on_the_day(repo, tmp_path):
    _record(repo, _ts("2026-10-07", 12), 60, "refused", "x")  # 13 days back: inside
    _record(repo, _ts("2026-10-06", 12), 60, "refused", "y")  # 14 days back: outside
    m = mt.compute("2026-10-20", state=tmp_path / "state")
    assert m["refused_14d"] == 1


def test_unsettled_and_unreadable_records_are_counted_never_zero(repo, tmp_path):
    day = "2026-10-20"
    rdir = repo / ".git" / "fabrik-merge"
    _record(repo, _ts(day, 9), 600, None, phase="build")  # in flight
    _record(repo, _ts(day, 10), 600, "merged", phase="synced")  # merged, reply not yet sent
    (rdir / "broken.json").write_text("{")
    _record(repo, _ts(day, 11), 600, "merged", rid="ABC")  # not a ULID: never 1970
    _record(repo, _ts(day, 11), 600, "merged", rid="Z" * 26)  # a ULID past year 9999: never a crash
    lower = _ulid(_ts(day, 12)).lower()
    _record(repo, _ts(day, 12), 600, "merged", rid=lower)  # a lowercase ULID is still a ULID
    m = mt.compute(day, state=tmp_path / "state")
    assert (m["merged"], m["pending"], m["unreadable"]) == (1, 2, 3)
    text = mt.line(m)
    assert "1 merged, 2 pending, 3 unreadable" in text


# ── the valve ────────────────────────────────────────────────────────────────────────


def _valve(repo: Path, text: str | None, when: float) -> None:
    path = repo / ".fabrik" / "merge-tests"
    if text is None:
        _git(repo, "rm", "-q", ".fabrik/merge-tests")
    else:
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"{text}\ntests/\n")
        _git(repo, "add", ".fabrik/merge-tests")
    env = _git_env() | {"GIT_COMMITTER_DATE": f"@{int(when)}", "GIT_AUTHOR_DATE": f"@{int(when)}"}
    _git(repo, "commit", "-qm", f"valve {text}", env=env)


def test_the_valve_day_is_the_start_of_the_on_run_that_holds_at_the_tip(repo):
    assert mt.valve_day("master") is None
    _valve(repo, "# merge-tests-after-merge-above: 40", _ts("2026-10-25"))
    assert mt.valve_day("master") is None  # D-1186's 40 is not the valve D-1384 turned on
    _valve(repo, "# merge-tests-after-merge-above: 0", _ts("2026-10-31"))
    assert mt.valve_day("master") == "2026-10-31"
    _valve(repo, "# merge-tests-after-merge-above: 40", _ts("2026-11-05"))
    assert mt.valve_day("master") is None  # D-1384's remedy turned it off again
    _valve(repo, None, _ts("2026-11-06"))
    _valve(repo, "# merge-tests-after-merge-above: 00", _ts("2026-11-09"))
    assert (
        mt.valve_day("master") == "2026-11-09"
    )  # a deletion is "off", never the end of the search


@pytest.mark.parametrize(
    "text",
    [
        "# merge-tests-after-merge-above: 05",  # a threshold that only starts with 0
        "# merge-tests-after-merge-above: 0  # D-1384",  # merge_request ignores a trailing reason
        "merge-tests-after-merge-above: 0",  # not a comment: not the declaration
    ],
)
def test_a_line_the_merge_does_not_honour_is_not_the_valve(repo, text):
    _valve(repo, text, _ts("2026-10-31"))
    assert mt.valve_day("master") is None


def test_the_valve_grammar_is_merge_requests_own():
    import merge_request

    assert mt.VALVE_RE.pattern == merge_request._AFTER_DECL_RE.pattern


def test_a_git_show_failure_that_is_not_a_deletion_is_unknown(repo, monkeypatch):
    real = mt._git

    def git(args, repo=None):
        if args[0] == "show":
            raise RuntimeError("git show rc=128: fatal: bad object deadbeef")
        return real(args, repo)

    _valve(repo, "# merge-tests-after-merge-above: 0", _ts("2026-10-31"))
    monkeypatch.setattr(mt, "_git", git)
    with pytest.raises(mt.ValveUnknownError):
        mt.valve_day("master")


def test_a_failed_valve_lookup_is_unmeasured_never_valve_off(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("MERGE_TRIPWIRE_REF", "no-such-ref")
    with pytest.raises(mt.ValveUnknownError):
        mt.valve_day("no-such-ref")
    m = mt.compute("2026-10-20", state=tmp_path / "state")
    assert m["red_master"]["error"] and not m["red_master"]["tripped"]
    assert "red-master unmeasured (valve lookup failed)" in mt.line(m)
    assert "valve not on yet" not in mt.line(m)


# ── the red-master week ──────────────────────────────────────────────────────────────

VALVE = "2026-10-31"
PRE = _flat("2026-10-17", 14, 1)  # 10-17 .. 10-30 at 1%


def test_the_series_reads_the_newest_version_by_number(tmp_path):
    state = tmp_path / "state"
    _series(state, {"2026-10-01": (1, 10)}, version=10)
    (state / "series" / "waste_red_master_rework@v2.jsonl").write_text(
        '{"day":"2026-10-01","numerator":9,"denominator":10}\n'
    )
    assert mt.red_series(state) == {"2026-10-01": (1.0, 10.0)}


def test_without_the_valve_only_the_pre_level_prints_and_nothing_trips(tmp_path):
    state = tmp_path / "state"
    _series(state, _flat("2026-10-01", 20, 1))
    red = mt.red_master("2026-10-20", None, mt.red_series(state))
    assert red["pre"] == pytest.approx(0.01) and red["pre_days"] == 14
    assert red["week"] is None and not red["tripped"]


def test_a_partial_or_arrival_free_pre_window_is_no_level(tmp_path):
    series = {"2026-10-19": (1.0, 100.0)}
    assert mt.red_master("2026-10-20", None, series)["pre"] is None  # 1 of 14 days
    zero = dict.fromkeys(_days("2026-10-07", 14), (0.0, 0.0))
    assert mt.red_master("2026-10-20", None, zero)["pre"] is None  # no arrivals: unknown, not 0


def test_a_rise_sustained_for_7_days_trips(tmp_path):
    series = {k: (float(n), float(d)) for k, (n, d) in (PRE | _flat(VALVE, 20, 4)).items()}
    series[VALVE] = (0.0, 100.0)
    # the 13th post-valve day is the first whose last 7 trailing weeks all lie after the valve
    assert not mt.red_master("2026-11-12", VALVE, series)["tripped"]
    red = mt.red_master("2026-11-13", VALVE, series)
    assert red["tripped"] and red["week"] == pytest.approx(0.04) and red["week_days"] == 7


def test_a_rise_inside_poisson_noise_does_not_trip(tmp_path):
    series = {k: (float(n), float(d)) for k, (n, d) in (PRE | _flat(VALVE, 20, 1)).items()}
    for d in _days("2026-11-01", 20):
        series[d] = (2.0, 100.0) if d.endswith(("1", "5")) else (1.0, 100.0)
    assert not mt.red_master("2026-11-20", VALVE, series)["tripped"]


def test_a_missing_day_or_the_valve_day_never_counts_in_the_week(tmp_path):
    series = {k: (float(n), float(d)) for k, (n, d) in (PRE | _flat(VALVE, 20, 4)).items()}
    series[VALVE] = (90.0, 100.0)  # the valve day itself: excluded from every week
    red = mt.red_master("2026-11-06", VALVE, series)
    assert red["week_days"] == 6 and red["week"] == pytest.approx(0.04)
    del series["2026-11-10"]
    assert not mt.red_master("2026-11-13", VALVE, series)["tripped"]


def test_a_week_at_the_pre_valve_level_does_not_trip(tmp_path):
    series = {k: (float(n), float(d)) for k, (n, d) in _flat("2026-10-17", 40, 1).items()}
    assert not mt.red_master("2026-11-20", VALVE, series)["tripped"]


# ── publish: rows, the line, one mail per episode ────────────────────────────────────


def _tripped_store(state: Path) -> None:
    _series(state, PRE | _flat(VALVE, 25, 5))
    _series_point = state / "series" / "waste_red_master_rework@v2.jsonl"
    assert _series_point.is_file()


def _publish(day: str, state: Path, **kw) -> dict:
    return mt.publish(day, state=state, today=TODAY, **kw)


def test_publish_mails_once_per_tripped_episode_even_on_a_rerun(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "# merge-tests-after-merge-above: 0", _ts(VALVE))
    sent: list[str] = []
    monkeypatch.setattr(mt, "_mail", lambda m: sent.append(m["day"]) or True)
    for day in ("2026-11-12", "2026-11-13", "2026-11-13", "2026-11-14", "2026-11-14"):
        _publish(day, state)
    assert sent == ["2026-11-13"]
    rows = (repo / ".git" / "fabrik-merge" / "tripwire.jsonl").read_text().splitlines()
    assert [json.loads(r)["day"] for r in rows] == ["2026-11-12", "2026-11-13", "2026-11-14"]
    assert [json.loads(r)["mailed"] for r in rows] == [False, True, True]
    line = (repo / ".git" / "fabrik-merge" / "tripwire-line.txt").read_text()
    assert line.startswith("TRIPPED, threshold back to 40 (D-1384) — merge tripwire 2026-11-14:")


def test_a_day_with_no_row_starts_a_new_episode(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "# merge-tests-after-merge-above: 0", _ts(VALVE))
    sent: list[str] = []
    monkeypatch.setattr(mt, "_mail", lambda m: sent.append(m["day"]) or True)
    _publish("2026-11-13", state)
    _publish(
        "2026-11-16", state
    )  # 11-14 and 11-15 never published: the episode is not known to run on
    assert sent == ["2026-11-13", "2026-11-16"]


def test_an_untripped_previous_day_does_not_suppress_the_mail(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "# merge-tests-after-merge-above: 0", _ts(VALVE))
    rows = repo / ".git" / "fabrik-merge" / "tripwire.jsonl"
    rows.write_text(
        json.dumps({"day": "2026-11-12", "mailed": True, "red_master": {"tripped": False}}) + "\n"
    )
    sent: list[str] = []
    monkeypatch.setattr(mt, "_mail", lambda m: sent.append(m["day"]) or True)
    _publish("2026-11-13", state)
    assert sent == ["2026-11-13"]


def test_a_failed_or_timed_out_mail_keeps_the_row_and_retries_next_day(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "# merge-tests-after-merge-above: 0", _ts(VALVE))
    calls: list[list[str]] = []

    def run(argv, **kw):
        calls.append(argv)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(mt.subprocess, "run", run)
    monkeypatch.setattr(mt, "valve_day", lambda ref, repo=None: VALVE)
    monkeypatch.setattr(mt, "records_dir", lambda repo=None: repo_dir)
    repo_dir = repo / ".git" / "fabrik-merge"
    m = _publish("2026-11-13", state)
    assert m["mailed"] is False and (repo_dir / "tripwire.jsonl").is_file()
    assert _publish("2026-11-14", state)["mailed"] is True
    argv = calls[-1]
    assert (
        argv[argv.index("--to") + 1] == "fabrik"
        and argv[argv.index("--to-agent") + 1] == "coordinator"
    )


def test_no_mail_publishes_without_mailing(repo, tmp_path, monkeypatch):
    state = tmp_path / "state"
    _tripped_store(state)
    _valve(repo, "# merge-tests-after-merge-above: 0", _ts(VALVE))
    monkeypatch.setattr(mt, "_mail", lambda m: pytest.fail("mailed under mail=False"))
    assert _publish("2026-11-13", state, mail=False)["mailed"] is False


def test_only_a_complete_day_publishes(repo, tmp_path):
    with pytest.raises(ValueError, match="only days before today"):
        mt.publish(TODAY, state=tmp_path / "state", today=TODAY)


def test_a_republish_counts_a_request_that_settled_late(repo, tmp_path):
    state = tmp_path / "state"
    _series(state, {})
    day = "2026-10-20"
    _record(repo, _ts(day, 23), 600, None, phase="build")
    assert _publish(day, state)["pending"] == 1
    _record(repo, _ts(day, 23), 3600, "merged")  # the same request settles after the first publish
    m = _publish(day, state)
    assert (m["merged"], m["pending"]) == (1, 0)
    rows = (repo / ".git" / "fabrik-merge" / "tripwire.jsonl").read_text().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["merged"] == 1


def test_publish_recent_covers_the_day_and_the_two_before(repo, tmp_path, monkeypatch):
    days: list[str] = []
    monkeypatch.setattr(mt, "publish", lambda d, *a, **kw: days.append(d) or {})
    mt.publish_recent("2026-10-20", state=tmp_path)
    assert days == ["2026-10-18", "2026-10-19", "2026-10-20"]


def test_an_older_day_never_overwrites_the_newest_line(repo, tmp_path):
    state = tmp_path / "state"
    _series(state, {})
    _publish("2026-10-20", state)
    _publish("2026-10-18", state)
    line = (repo / ".git" / "fabrik-merge" / "tripwire-line.txt").read_text()
    assert "merge tripwire 2026-10-20:" in line


def test_the_line_puts_the_class_list_last_so_a_clip_loses_only_it(repo, tmp_path):
    state = tmp_path / "state"
    _series(state, PRE)
    m = mt.compute("2026-10-30", state=state)
    m["refusal_classes_14d"] = {f"class-{i}": 99 for i in range(30)}
    text = mt.line(m)
    clipped = work._clip("work: " + text)
    assert "red-master pre-valve 1.00% (14/14 d)" in clipped and len(clipped) <= work.LINE_MAX


# ── the coordinator's prompt line and the daily hook ─────────────────────────────────


def _coordinator_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "main"
    tree.mkdir()
    _git(tree, "init", "-q", "-b", "master")  # a real main checkout: prompt_block reads its git dir
    (tree / ".git" / "fabrik-merge").mkdir()
    (tree / ".fabrik" / "work").mkdir(parents=True)
    (tree / ".fabrik" / "work" / "config.json").write_text('{"coordinator_mode": true}')
    return tree


def test_only_a_coordinator_sees_the_line_and_a_stale_one_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "_print_mode", lambda: False)
    tree = _coordinator_tree(tmp_path)
    path = tree / ".git" / "fabrik-merge" / "tripwire-line.txt"
    assert work._merge_tripwire_line(tree) == ""  # never written here: nothing
    path.write_text("merge tripwire 2026-10-30: 9 merged\n")
    assert work._merge_tripwire_line(tree) == "merge tripwire 2026-10-30: 9 merged"
    old = time.time() - work.MERGE_TRIPWIRE_MAX_AGE_S - 60
    os.utime(path, (old, old))
    assert work._merge_tripwire_line(tree).startswith("merge tripwire STALE — last written ")
    path.write_bytes(b"\xff\xfe broken")
    assert work._merge_tripwire_line(tree) == ""  # a non-UTF-8 file never raises
    builder = tmp_path / "builder"
    builder.mkdir()
    (builder / ".git").write_text("gitdir: elsewhere\n")  # a linked worktree: not the coordinator
    (builder / ".fabrik" / "work").mkdir(parents=True)
    (builder / ".fabrik" / "work" / "config.json").write_text('{"coordinator_mode": true}')
    assert work._merge_tripwire_line(builder) == ""


def test_the_prompt_block_carries_the_line(tmp_path, monkeypatch):
    tree = _coordinator_tree(tmp_path)
    monkeypatch.setattr(work, "_api_root", lambda repo: tree)
    monkeypatch.setattr(work, "_panes_waiting", lambda root, name: ([], ""))
    monkeypatch.setattr(work, "_merge_tripwire_line", lambda root: "merge tripwire 2026-10-30: X")
    monkeypatch.setattr(work, "_print_mode", lambda: False)
    assert "work: merge tripwire 2026-10-30: X" in work.prompt_block(tree, "sid").splitlines()


def test_the_daily_hook_forwards_the_repo_and_no_mail(tmp_path, monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(mt, "publish_recent", lambda day, **kw: seen.update(day=day, **kw))
    monkeypatch.setitem(sys.modules, "merge_tripwire", mt)
    kc._publish_merge_tripwire("2026-10-30", tmp_path / "st", tmp_path / "repo", True)
    assert seen == {
        "day": "2026-10-30",
        "state": tmp_path / "st",
        "repo": tmp_path / "repo",
        "mail": False,
    }
