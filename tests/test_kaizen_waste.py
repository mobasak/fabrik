"""The token-waste series (W-02472911, D-1118): six waste categories per local day, published
into the kaizen series store, with frozen XmR control limits read back by the daily digest.

Every test runs on tmp ledgers: the feedback ledger through ``COMMAND_RUN_DIR`` (its parent holds
``command-feedback.jsonl``, as ``command_run.py`` resolves it), the identity store through
``AGENT_IDENTITY_FILE``, transcripts through ``KAIZEN_TRANSCRIPT_ROOTS``, the store through
``KAIZEN_STATE_DIR`` and a throwaway git repo through ``KAIZEN_WASTE_GIT_REPO`` — never live state.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

import kaizen_waste as kw  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "kaizen_digest_w", REPO / "scripts" / "sysadmin" / "kaizen_digest.py"
)
kd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kd)

DAY = "2026-10-10"


def _ts(day: str, hour: int = 12) -> float:
    return dt.datetime.fromisoformat(f"{day}T{hour:02d}:00:00").astimezone().timestamp()


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "state" / "command-runs"
    runs.mkdir(parents=True)
    monkeypatch.setenv("COMMAND_RUN_DIR", str(runs))
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(tmp_path / "state" / "agent-identity.jsonl"))
    monkeypatch.setenv("KAIZEN_TRANSCRIPT_ROOTS", str(tmp_path / "projects"))
    monkeypatch.setenv("KAIZEN_STATE_DIR", str(tmp_path / "kaizen"))
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REPO", str(tmp_path / "nogit"))
    return tmp_path


def _feedback(env: Path, rows: list[dict]) -> None:
    p = env / "state" / "command-feedback.jsonl"
    with open(p, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _close(day: str = DAY, **kw_) -> dict:
    row = {
        "ts": _ts(day),
        "state": "done",
        "agent": "intel",
        "command": "fabrik-task",
        "tok_in": 10,
        "tok_out": 100,
        "tok_cache_read": 1000,
        "tok_cache_create": 50,
        "tok_msgs": 10,
        "tok_seat_in": 0,
        "tok_seat_out": 0,
        "tok_seat_cache_read": 0,
        "tok_seat_cache_create": 0,
        "wall": "",
    }
    row.update(kw_)
    return row


def test_per_call_metrics_use_top_level_closes_only(env):
    _feedback(
        env,
        [
            _close(tok_cache_read=1000, tok_out=100, tok_msgs=10),
            _close(tok_cache_read=3000, tok_out=300, tok_msgs=10, agent="kaizen"),
            # nested: its window overlaps its parent's — never counted
            _close(tok_cache_read=99_000, tok_out=9_900, tok_msgs=1, parent="fabrik-task"),
            # zero turns: changes neither operand
            _close(tok_cache_read=50_000, tok_out=5_000, tok_msgs=0),
        ],
    )
    res = kw.compute_day(DAY)
    ctx, ctx_rows = res["waste_context_per_call"]
    out, _ = res["waste_output_per_call"]
    assert ctx.measurable and ctx.value == pytest.approx(200.0)  # 4000 / 20
    assert (ctx.numerator, ctx.denominator) == (4000, 20)
    assert out.value == pytest.approx(20.0)  # 400 / 20
    by_agent = {r["key"]: r for r in ctx_rows if r["by"] == "agent"}
    assert by_agent["kaizen"]["numerator"] == 3000 and by_agent["intel"]["numerator"] == 1000
    assert "1 nested" in ctx.detail
    closes = [r for r in ctx_rows if r["by"] == "total" and r["key"] == "closes"]
    assert closes[0]["value"] == 3  # top-level closes, the 20-close floor's count
    # a torn ledger value (a string, NaN) is absent for its row, never a crash of the day
    _feedback(
        env,
        [_close(tok_msgs="7"), _close(tok_msgs=float("nan"), gap_s="1h"), _close(tok_msgs=10**400)],
    )
    assert kw.compute_day(DAY)["waste_context_per_call"][0].value == pytest.approx(200.0)


def test_seat_share_counts_four_fields_and_refuses_days_before_the_field(env):
    early = "2026-10-01"
    _feedback(
        env,
        [
            {k: v for k, v in _close(early).items() if not k.startswith("tok_seat")},
            _close(
                tok_in=0,
                tok_out=0,
                tok_cache_read=600,
                tok_cache_create=0,
                tok_seat_in=100,
                tok_seat_out=100,
                tok_seat_cache_read=100,
                tok_seat_cache_create=100,
                rounds=3,
            ),
        ],
    )
    seat, _ = kw.compute_day(DAY)["waste_seat_share"]
    assert seat.value == pytest.approx(40.0)  # 400 seat of 1000 total
    before, _ = kw.compute_day(early)["waste_seat_share"]
    assert not before.measurable and "not yet recorded" in before.detail
    ctx, _ = kw.compute_day("2026-09-01")["waste_context_per_call"]
    assert not ctx.measurable and "not yet recorded" in ctx.detail
    for mid in ("waste_output_per_call", "waste_wall_rate"):
        early, _ = kw.compute_day("2026-09-01")[mid]
        assert not early.measurable and "not yet recorded" in early.detail, mid


def _identity(env: Path, rows: list[tuple[str, str, str]]) -> None:
    p = env / "state" / "agent-identity.jsonl"
    with open(p, "a", encoding="utf-8") as fh:
        for name, sid, day in rows:
            fh.write(json.dumps({"name": name, "session_id": sid, "at": _ts(day)}) + "\n")


def _transcript(env: Path, sid: str, cc: int, cr: int, inp: int) -> None:
    d = env / "projects" / "-opt-x"
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "user", "message": {"content": "hi"}},
        {
            "type": "assistant",
            "message": {
                "id": "m1",
                "usage": {
                    "input_tokens": inp,
                    "cache_creation_input_tokens": cc,
                    "cache_read_input_tokens": cr,
                },
            },
        },
        {"type": "assistant", "message": {"id": "m2", "usage": {"input_tokens": 999_999}}},
    ]
    (d / f"{sid}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def test_rotation_counts_rebinds_not_births_and_names_unfound_transcripts(env):
    _identity(
        env,
        [
            ("intel", "s1", "2026-10-09"),  # birth — not a rotation
            ("intel", "s2", DAY),  # rotation
            ("intel", "s2", DAY),  # a --force rebind of the same session — not a new one
            ("kaizen", "k1", DAY),  # birth
        ],
    )
    _transcript(env, "s2", cc=90_000, cr=20_000, inp=2)
    rot, rows = kw.compute_day(DAY)["waste_rotation_rebuild"]
    assert rot.measurable and rot.value == 110_002
    assert (rot.numerator, rot.denominator) == (110_002, 1)
    assert {r["key"] for r in rows if r["by"] == "agent"} == {"intel"}
    quiet, _ = kw.compute_day("2026-10-11")["waste_rotation_rebuild"]
    assert quiet.measurable and quiet.value == 0  # the store was read and holds none
    # one found and one unfound: unmeasured (a partial total would be frozen low for good)
    _identity(
        env,
        [
            ("fleet", "f1", "2026-10-11"),
            ("fleet", "f2", "2026-10-12"),
            ("kaizen", "k1", "2026-10-11"),
        ],
    )
    _identity(env, [("kaizen", "k2", "2026-10-12")])
    _transcript(env, "f2", cc=1, cr=1, inp=1)
    lost, _ = kw.compute_day("2026-10-12")["waste_rotation_rebuild"]
    assert not lost.measurable and "1 of 2" in lost.detail
    # a transcript with no usage line yet (here a non-object message) is unknown, never a crash or a 0
    (env / "projects" / "-opt-x" / "k2.jsonl").write_text('{"type":"assistant","message":[1]}\n')
    assert not kw.compute_day("2026-10-12")["waste_rotation_rebuild"][0].measurable


def test_wall_rate_counts_quota_closes_not_operator_pauses(env):
    _feedback(
        env,
        [
            _close(state="blocked", wall="quota"),
            _close(state="blocked", wall="paused", surface="W-1 the quota lane work"),
            _close(),
            _close(
                resumed_from={"reason": "fleet quota wall approaching", "session_id": "x"},
                gap_s=7200.0,
            ),
        ],
    )
    wall, rows = kw.compute_day(DAY)["waste_wall_rate"]
    # 1 quota wall of 4 top-level closes; an operator pause is not a wall, whatever its surface says
    assert wall.value == pytest.approx(25.0)
    assert (wall.numerator, wall.denominator) == (1, 4)
    assert "2.0 h" in wall.detail  # the resumed wait whose reason names the quota wall
    assert any(r["by"] == "total" and r["key"] == "closes" and r["value"] == 4 for r in rows)


def _git(repo: Path, *args: str, date: str | None = None) -> str:
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t")
    e["GIT_COMMITTER_EMAIL"] = "t@x"
    if date:
        e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = date
    return subprocess.run(
        ["git", "-C", str(repo), *args], env=e, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_red_master_counts_arrivals_and_fails_open(env, monkeypatch):
    repo = env / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init", date="2026-10-08T10:00:00")
    # authored the day before, merged on DAY: counted on DAY (arrival), not on its author day
    _git(repo, "checkout", "-q", "-b", "w")
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "fix(tests): master red after the merge\n\nAgent-Name: kaizen",
        date="2026-10-09T10:00:00",
    )
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "docs: Measured since the change, registered on master",
        date="2026-10-09T11:00:00",
    )
    # fix-shaped but only a substring lookalike: the word boundary alone excludes it
    _git(repo, "commit", "-q", "--allow-empty", "-m", "fix: tidy hooks registered on master")
    # the real phrase in a non-fix subject: the fix-shape alone excludes it
    _git(repo, "commit", "-q", "--allow-empty", "-m", "docs: note the red master episode")
    # the trailing boundaries: a longer word, and a subject that only starts like `fix`
    _git(repo, "commit", "-q", "--allow-empty", "-m", "fix: red mastery of the queue")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "fixture: red master sample")
    # a bare Agent-Name key never takes the next trailer line as the agent
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "fix(x): red master again\n\nAgent-Name:\nCo-Authored-By: t",
    )
    _git(repo, "checkout", "-q", "master")
    _git(
        repo,
        "merge",
        "-q",
        "--no-ff",
        "w",
        "-m",
        "merge(w): red master fix",
        date=f"{DAY}T09:00:00",
    )
    # a direct first-parent commit on DAY
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "fix: allowlist x (red on master since W-1)",
        date=f"{DAY}T15:00:00",
    )
    # a hypothetical on DAY is no red master (W-d633d5f5): the count stays 3
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "fix: re-apply x\n\nleft on the branch it would turn master red",
        date=f"{DAY}T16:00:00",
    )
    # exactly at the next midnight: the next day's, never both (git's --until is inclusive)
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "fix: red master at midnight",
        date="2026-10-11T00:00:00",
    )
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REPO", str(repo))
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REF", "master")
    rm, rows = kw.compute_day(DAY)["waste_red_master_rework"]
    assert rm.measurable and rm.value == 3, rm
    assert {r["key"]: r["value"] for r in rows if r["by"] == "agent"} == {
        "kaizen": 1,
        "unattributed": 2,
    }
    # no refresh since 10-11 ended (no newer commit, no reflog, no fetch): unknown, never a quiet 0
    _git(repo, "reflog", "expire", "--expire=now", "--all")
    stale, _ = kw.compute_day("2026-10-11")["waste_red_master_rework"]
    assert not stale.measurable and "stale" in stale.detail
    # a later fetch of ANOTHER branch vouches for nothing: still unknown
    fetched = repo / ".git" / "FETCH_HEAD"
    fetched.write_text("abc\t\tbranch 'feature' of example\n")
    late = _ts("2026-10-13")
    os.utime(fetched, (late, late))
    assert not kw.compute_day("2026-10-12")["waste_red_master_rework"][0].measurable
    # a fetch of this ref's branch after the day proves a quiet day quiet: measured, and 0
    fetched.write_text("abc\t\tbranch 'master' of example\n")
    os.utime(fetched, (late, late))
    quiet, _ = kw.compute_day("2026-10-12")["waste_red_master_rework"]
    assert quiet.measurable and quiet.value == 0, quiet
    before, _ = kw.compute_day("2026-10-09")["waste_red_master_rework"]
    assert before.measurable and before.value == 0  # not yet on master that day
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    time.tzset()
    try:
        _git(
            repo,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "fix: red master in the 25th hour",
            date="2026-11-01T23:30:00-05:00",
        )
        _git(
            repo,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "chore: tip",
            date="2026-11-03T12:00:00-05:00",
        )
        assert kw.compute_day("2026-11-01")["waste_red_master_rework"][0].value == 1
        assert kw.compute_day("2026-11-02")["waste_red_master_rework"][0].value == 0
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REPO", str(env / "missing"))
    broken, _ = kw.compute_day(DAY)["waste_red_master_rework"]
    assert not broken.measurable and broken.detail


def test_red_master_phrase_skips_hypotheticals():
    # W-d633d5f5: a modal governing the verb that forms the phrase is a hypothetical, not a red
    # master (2edc9545f, 0e8aacd73 on origin/master); the escape variants both ways
    not_rework = (
        "fix: re-apply it\n\ncarried on a branch that is merge-requested, it would turn master red.",
        "fix: pin the charter\n\nold charter words and would read red on master without this).",
        "fix: guard\n\nit could not go red on master",
        "fix: guard\n\nthis will turn master red once merged",
        "fix: guard\n\nit won't go red on master",
        "fix: guard\n\nit can't turn master red",
        "fix: guard\n\nit cannot go red on master",
        "fix: guard\n\nit would've turned master red",
        "fix: guard\n\nit'd turn master red",
        "fix: guard\n\nit `would` turn master red",
        "fix: guard\n\nit WOULD\nturn master red",
        "fix: guard\n\nit is going to turn master red",
        "fix: guard\n\nit would turn the build on master red",
        "fix: guard\n\nit would turn the whole build on master red",
        "fix: guard\n\nit would also turn master red",
        "fix: guard\n\nit could easily go red on master",
        "fix: guard\n\nit would mean master is red",
        "fix: guard\n\nit would cause a red master",
    )
    rework = (
        "fix: allowlist x (red on master since W-1)",
        "fix(tests): two graders red on master since the retention merge",
        "fix: x\n\ntest_y went red on master. Both byte-identical paragraphs moved.",
        "fix: x\n\nMaster went red after the /hibernate merge",
        "fix: x\n\nthe cap was not updated, so master went red. W-7c8e293f.",
        "fix: x\n\nthe test would not run, so master went red",
        "fix: x\n\nthe test would not run so master went red",
        "fix: x\n\nthe gate should have caught this but master went red",
        "fix: x\n\nwe can see that master is red",
        "fix: x\n\nsince 3 May master went red",
        "fix: x\n\nwe'd left master red for two hours",
        "fix: x\n\nthe merge they'd made left master red",
        "fix: x\n\nwe will be fine now since master is red",
        "fix: x\n\nit will keep working because master turned red",
        "fix: x\n\na bad merge can and did turn master red",
        "fix: x\n\nit would turn it off. Then master went red",
        "fix: x\n\nthe scan " + "q" * 75 + " master went red",
        "fix: x\n\nit would turn master red. Separately, red on master since a90b35a3b",
        "fix(x): one grader per text (red on master's skeleton: the bare `citation` cell).",
        "fix: x\n\n3 failed on master 0ac19d87d; the existing gate test is the grader (red on master)",
        "fix: red master again",
    )
    for msg in not_rework:
        assert not kw._is_red_master_rework(msg), msg
    for msg in rework:
        assert kw._is_red_master_rework(msg), msg


def test_a_version_bump_republishes_the_breakdown_and_the_digest_reads_its_own_version(env):
    # W-d633d5f5: a day whose breakdown was written under v1 gets its v2 cut beside it (once),
    # and the digest reads only the cut whose `def` matches the series version it judges
    state = env / "kaizen"
    mid = "waste_red_master_rework"
    assert kw.registry()[mid]["version"] == 2
    old = {"day": DAY, "metric": mid, "version": 1, "by": "agent", "key": "old", "numerator": 3}
    state.mkdir(parents=True, exist_ok=True)
    kw.breakdown_path(state).write_text(json.dumps(old) + "\n")
    cut = {mid: [{"by": "agent", "key": "new", "numerator": 2}]}
    kw._write_breakdown(DAY, cut, state)
    kw._write_breakdown(DAY, cut, state)  # idempotent per (day, metric, def)
    rows = [json.loads(ln) for ln in kw.breakdown_path(state).read_text().splitlines()]
    assert [(r["key"], r.get("def", 1)) for r in rows] == [("old", 1), ("new", 2)]
    v1 = {mid: state / "series" / f"{mid}@v1.jsonl"}
    v2 = {mid: state / "series" / f"{mid}@v2.jsonl"}
    assert [r["key"] for r in kd._cut(rows, v2)[(DAY, mid)]] == ["new"]
    assert [r["key"] for r in kd._cut(rows, v1)[(DAY, mid)]] == ["old"]


def _series_day(env: Path, metric: str, day: str) -> None:
    d = env / "kaizen" / "series"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{metric}@v1.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"day": day, "metric": metric, "value": 1}) + "\n")


def test_backfill_is_idempotent_bounded_and_writes_breakdown(env):
    _feedback(env, [_close("2026-10-08"), _close("2026-10-09"), _close(DAY), _close("2026-10-11")])
    _identity(env, [("intel", "s1", "2026-10-01")])
    # the collector has published up to DAY only: the waste backfill must not pass it
    _series_day(env, "hole_count", DAY)
    written = kw.backfill(since="2026-10-08", today="2026-10-20")
    assert written
    ctx = env / "kaizen" / "series" / "waste_context_per_call@v1.jsonl"
    days = [json.loads(x)["day"] for x in ctx.read_text().splitlines()]
    assert days == ["2026-10-08", "2026-10-09", DAY]
    assert kw.backfill(since="2026-10-08", today="2026-10-20") == []  # idempotent
    assert [json.loads(x)["day"] for x in ctx.read_text().splitlines()] == days
    bd = [
        json.loads(x)
        for x in (env / "kaizen" / "waste-breakdown@v1.jsonl").read_text().splitlines()
    ]
    keys = {(r["day"], r["metric"], r["by"], r["key"]) for r in bd}
    assert (DAY, "waste_context_per_call", "agent", "intel") in keys
    assert (DAY, "waste_context_per_call", "command", "fabrik-task") in keys
    assert len(bd) == len(keys)  # one row per (day, metric, by, key) after two runs
    # a second write of the same (day, metric) adds nothing
    kw._write_breakdown(DAY, {"waste_context_per_call": [{"by": "agent", "key": "x"}]}, None)
    assert len((env / "kaizen" / "waste-breakdown@v1.jsonl").read_text().splitlines()) == len(bd)
    with pytest.raises(ValueError):
        kw.publish_day("2026-10-20", today="2026-10-20")  # never today
    calls: list[str] = []

    def flaky(day: str, *_a, **_k) -> list:
        calls.append(day)
        if day == "2026-10-08":
            raise OSError("disk")
        return []

    real = kw.publish_day
    kw.publish_day = flaky
    try:
        kw.publish_recent("2026-10-10", today="2026-10-20")
    finally:
        kw.publish_day = real
    assert calls == ["2026-10-08", "2026-10-09", "2026-10-10"]
    # past the collector's newest day: the daily hook's direct call waits, writing nothing
    assert kw.publish_day("2026-10-11", today="2026-10-20") == []
    assert kw.breakdown_path(env / "kaizen").name == kd.BREAKDOWN_FILE
    with pytest.raises(SystemExit):
        kw.main(["--day", "20261010"])  # one spelling of a day, or the series key forks
    with pytest.raises(SystemExit):
        kw.main(["--rebaseline", "waste_seat_share"])  # a rebaseline names its day
    assert kw.main(["--publish", "--day", "2026-10-11"]) == 2  # past the bound


def _points(
    env: Path, metric: str, values: list[float], start: str = "2026-09-01", closes: int = 30
) -> list[str]:
    d0 = dt.date.fromisoformat(start)
    days = [(d0 + dt.timedelta(days=i)).isoformat() for i in range(len(values))]
    d = env / "kaizen" / "series"
    d.mkdir(parents=True, exist_ok=True)
    bd = env / "kaizen" / "waste-breakdown@v1.jsonl"
    # written newest-first: the reader must sort by day, never trust file order
    with open(d / f"{metric}@v1.jsonl", "a", encoding="utf-8") as fh, open(bd, "a") as bfh:
        for day, v in reversed(list(zip(days, values, strict=True))):
            fh.write(json.dumps({"day": day, "metric": metric, "value": v, "cell": f"{v}"}) + "\n")
            for by, key, val in (
                ("total", "closes", closes),
                ("agent", "kaizen", 7),
                ("agent", "intel", 3),
            ):
                row = {
                    "day": day,
                    "metric": metric,
                    "by": by,
                    "key": key,
                    "numerator": val,
                    "value": val,
                }
                bfh.write(json.dumps(row) + "\n")
        fh.write("{not json\n")
    return days


def test_digest_control_section_frozen_limits_and_rules(env, monkeypatch):
    base = [100, 102, 98, 101, 99, 100, 103, 97, 100, 101, 99, 102, 98, 100]
    days = _points(env, "waste_context_per_call", [*base, 100, 160])
    out = kd.compose(env / "kaizen")
    first = out.splitlines()[1]
    assert first.startswith("OUT OF CONTROL ↑ waste_context_per_call") and days[-1] in first, out
    assert "agent=kaizen" in first
    # the ordinary line reads the newest DAY, not the last line of the file
    assert f"waste_context_per_call: 160 @ {days[-1]}" in out
    # a frozen baseline: a sustained shift keeps alarming instead of being absorbed
    _points(env, "waste_seat_share", [*base, *([130] * 10)], start="2026-08-01")
    assert "OUT OF CONTROL ↑ waste_seat_share" in kd.compose(env / "kaizen")
    # a rebaseline row moves the limits to the new level: back in control
    kw.rebaseline("waste_seat_share", "2026-08-15", "kaizen closed W-x", state=env / "kaizen")
    seat_lines = [ln for ln in kd.compose(env / "kaizen").splitlines() if "waste_seat_share" in ln]
    assert not any(ln.startswith("OUT OF CONTROL") for ln in seat_lines), seat_lines
    # the 8-in-a-row rule fires inside the limits
    _points(env, "waste_output_per_call", [*base, *([101.5] * 8)], start="2026-07-01")
    assert "OUT OF CONTROL ↑ waste_output_per_call" in kd.compose(env / "kaizen")
    # a rare event count (mostly 0) is judged on a c-chart, never "flat": 4 fixes in a day alarms
    _points(
        env,
        "waste_red_master_rework",
        [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 4],
        start="2026-05-01",
    )
    assert "OUT OF CONTROL ↑ waste_red_master_rework" in kd.compose(env / "kaizen")
    # the c-chart, not XmR: a 1 after a sparse baseline is inside Poisson limits (XmR flags it)
    sparse = [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    (env / "kaizen" / "series" / "waste_red_master_rework@v1.jsonl").unlink()
    _points(env, "waste_red_master_rework", [*sparse, 1], start="2026-04-01")
    assert "OUT OF CONTROL ↑ waste_red_master_rework" not in kd.compose(env / "kaizen")
    # quiet days below a rare count's centre are the process, not a shift
    (env / "kaizen" / "series" / "waste_red_master_rework@v1.jsonl").unlink()
    _points(env, "waste_red_master_rework", [*sparse, *([0] * 8)], start="2026-04-01")
    assert "waste_red_master_rework" not in kd.compose(env / "kaizen").split("CONTROL:")[0]
    (env / "kaizen" / "series" / "waste_red_master_rework@v1.jsonl").unlink()
    # a flat ratio baseline has no width: any departure is a shift, never 'no limits'
    _points(env, "waste_wall_rate", [*([0.0] * 14), 25.0], start="2026-03-01")
    assert "OUT OF CONTROL ↑ waste_wall_rate" in kd.compose(env / "kaizen")
    (env / "kaizen" / "series" / "waste_wall_rate@v1.jsonl").unlink()
    # lower is better: a downward shift is an improvement to re-baseline, not an item
    _points(env, "waste_output_per_call", [*base, *([101.5] * 8), 60], start="2026-07-01")
    out = kd.compose(env / "kaizen")
    assert (
        "IMPROVED ↓ waste_output_per_call" in out
        and "OUT OF CONTROL ↑ waste_output_per_call" not in out
    )
    # a short baseline says so instead of judging
    _points(env, "waste_wall_rate", [1, 2, 3], start="2026-06-01")
    assert "waste_wall_rate: baseline 2/14 — no limits yet" in kd.compose(env / "kaizen")
    # a ratio day under 20 closes is plotted, never judged, however far out it reads
    _points(env, "waste_context_per_call", [500], start="2026-09-17", closes=5)
    lines = kd.compose(env / "kaizen").splitlines()
    assert "waste_context_per_call: 2026-09-17 under 20 closes — plotted, not judged" in lines
    assert not any(ln.startswith("OUT OF CONTROL ↑ waste_context_per_call") for ln in lines)
    # a flat baseline of a non-round value stays in control (no float-mean ulp drift)
    (env / "kaizen" / "series" / "waste_wall_rate@v1.jsonl").unlink()
    _points(env, "waste_wall_rate", [3432.42] * 15, start="2026-02-01")
    assert "waste_wall_rate" not in kd.compose(env / "kaizen").split("CONTROL:")[0]
    # a non-numeric latest point is said, never skipped for an older one
    with open(env / "kaizen" / "series" / "waste_wall_rate@v1.jsonl", "a") as fh:
        fh.write(json.dumps({"day": "2026-02-16", "value": float("nan")}) + "\n")
    assert "waste_wall_rate: 2026-02-16 is not a number — not judged" in kd.compose(env / "kaizen")
    # no close count at all is said as such, never as a small one
    _points(env, "waste_seat_share", [9], start="2026-10-30")
    bd = env / "kaizen" / "waste-breakdown@v1.jsonl"
    bd.write_text("".join(x + "\n" for x in bd.read_text().splitlines() if "2026-10-30" not in x))
    assert (
        "waste_seat_share: 2026-10-30 no close count in the breakdown — plotted, not judged"
        in kd.compose(env / "kaizen")
    )
    # the control section never costs the digest its other lines
    monkeypatch.setattr(kd, "_control", lambda *_: 1 / 0)
    broken = kd.compose(env / "kaizen")
    assert "CONTROL unavailable" in broken and "waste_seat_share: 9" in broken
