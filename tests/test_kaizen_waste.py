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
            ("kaizen", "k2", DAY),  # rotation, transcript missing
        ],
    )
    _transcript(env, "s2", cc=90_000, cr=20_000, inp=2)
    rot, rows = kw.compute_day(DAY)["waste_rotation_rebuild"]
    assert rot.measurable and rot.value == 110_002
    assert (rot.numerator, rot.denominator) == (110_002, 1)
    assert "1 unfound" in rot.cell
    assert {r["key"] for r in rows if r["by"] == "agent"} == {"intel"}
    quiet, _ = kw.compute_day("2026-10-11")["waste_rotation_rebuild"]
    assert quiet.measurable and quiet.value == 0  # the store was read and holds none
    _identity(env, [("fleet", "f1", "2026-10-12"), ("fleet", "f2", "2026-10-12")])
    lost, _ = kw.compute_day("2026-10-12")["waste_rotation_rebuild"]
    assert not lost.measurable and "unfound" in lost.detail


def test_wall_rate_counts_quota_closes_and_quota_pauses(env):
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
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REPO", str(repo))
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REF", "master")
    rm, rows = kw.compute_day(DAY)["waste_red_master_rework"]
    assert rm.measurable and rm.value == 2, rm
    assert {r["key"]: r["value"] for r in rows if r["by"] == "agent"} == {
        "kaizen": 1,
        "unattributed": 1,
    }
    before, _ = kw.compute_day("2026-10-09")["waste_red_master_rework"]
    assert before.measurable and before.value == 0  # not yet on master that day
    monkeypatch.setenv("KAIZEN_WASTE_GIT_REPO", str(env / "missing"))
    broken, _ = kw.compute_day(DAY)["waste_red_master_rework"]
    assert not broken.measurable and broken.detail


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
    # a racing second writer of the same (day, metric) adds nothing
    kw._write_breakdown(DAY, {"waste_context_per_call": [{"by": "agent", "key": "x"}]}, None)
    assert len((env / "kaizen" / "waste-breakdown@v1.jsonl").read_text().splitlines()) == len(bd)
    with pytest.raises(ValueError):
        kw.publish_day("2026-10-20", today="2026-10-20")  # never today


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


def test_digest_control_section_frozen_limits_and_rules(env):
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
    # a short baseline says so instead of judging
    _points(env, "waste_wall_rate", [1, 2, 3], start="2026-06-01")
    assert "waste_wall_rate: baseline 2/14 — no limits yet" in kd.compose(env / "kaizen")
    # a ratio day under 20 closes is plotted, never judged, however far out it reads
    _points(env, "waste_context_per_call", [500], start="2026-09-17", closes=5)
    lines = kd.compose(env / "kaizen").splitlines()
    assert "waste_context_per_call: 2026-09-17 under 20 closes — plotted, not judged" in lines
    assert not any(ln.startswith("OUT OF CONTROL ↑ waste_context_per_call") for ln in lines)
