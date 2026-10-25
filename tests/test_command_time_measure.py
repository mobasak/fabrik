"""Fixture tests for scripts/command_time_measure.py — the lean program's time measure (D-1219).

Every input is a fixture under tmp_path: a feedback ledger, an events dir, a transcript projects root
and a git repo with a linked worktree. Nothing reads the live ~/.claude state.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "command_time_measure.py"
_spec = importlib.util.spec_from_file_location("command_time_measure", SCRIPT)
assert _spec is not None and _spec.loader is not None
ctm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctm)

END = "2026-10-15T00:00:00+00:00"
END_TS = 1792022400.0  # END as an epoch
DAY = 86400.0
SID = "11111111-2222-3333-4444-555555555555"


def _ledger(path: Path, rows: list[dict], *junk: str) -> Path:
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in rows) + "".join(j + "\n" for j in junk) + "\n"
    )
    return path


def _row(
    cmd: str,
    state: str,
    minutes: float,
    *,
    ago_days: float = 1.0,
    rounds: int = 0,
    surface: str = "",
    loc=None,
    mini=None,
    repo: str = "",
) -> dict:
    return {
        "command": cmd,
        "state": state,
        "wall_s": minutes * 60,
        "rounds": rounds,
        "ts": END_TS - ago_days * DAY,
        "surface": surface,
        "loc_added": loc,
        "oversized_mini": mini,
        "repo": repo,
        "sid": SID,
    }


def _args(tmp_path: Path, ledger: Path, *extra: str) -> list[str]:
    (tmp_path / "events").mkdir(exist_ok=True)
    (tmp_path / "projects").mkdir(exist_ok=True)
    return [
        "--ledger",
        str(ledger),
        "--events",
        str(tmp_path / "events"),
        "--projects",
        str(tmp_path / "projects"),
        "--end",
        END,
        "--no-commits",
        *extra,
    ]


def _run(argv: list[str], capsys) -> dict:
    assert ctm.main([*argv, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def test_every_state_counts_and_wall_clock_stats(tmp_path, capsys):
    rows = [_row("fabrik-review", "done", m) for m in (10, 20, 30, 40)]
    rows += [_row("fabrik-review", "blocked", 50), _row("fabrik-review", "handoff", 60)]
    rows += [_row("fabrik-task", "done", 99), _row("fabrik-review", "done", 5, ago_days=20)]
    out = _run(
        _args(tmp_path, _ledger(tmp_path / "l.jsonl", rows), "--commands", "fabrik-review"), capsys
    )
    m = out["windows"][0]["commands"]["fabrik-review"]
    assert m["closes"] == 6
    assert m["states"] == {"done": 4, "blocked": 1, "handoff": 1}
    assert m["non_done_share"] == pytest.approx(2 / 6)
    assert m["wall_min"]["median"] == pytest.approx(35.0)
    assert m["wall_min"]["mean"] == pytest.approx(35.0)
    assert m["wall_min"]["p90"] == pytest.approx(
        60.0
    )  # the table's p90: sorted(v)[int(6 * 0.9)] = v[5]
    assert out["params"]["states"] == []


def test_state_filter_restricts_closes_and_runs(tmp_path, capsys):
    rows = [_row("fabrik-review", "done", 10), _row("fabrik-review", "blocked", 50)]
    args = _args(
        tmp_path,
        _ledger(tmp_path / "l.jsonl", rows),
        "--commands",
        "fabrik-review",
        "--state",
        "done",
    )
    (tmp_path / "events" / f"{SID}.jsonl").write_text(
        _event("2026-10-14T10:00:00+00:00", "run_open")
        + _event("2026-10-14T10:01:00+00:00", "dispatch")
        + _event("2026-10-14T11:00:00+00:00", "run_close", verdict="blocked")
    )
    m = _run(args, capsys)["windows"][0]["commands"]["fabrik-review"]
    assert m["closes"] == 1 and m["non_done_share"] == 0.0
    assert m["dispatched_runs"] == 0  # the blocked run is filtered out too


def test_windows_are_equal_and_half_open(tmp_path, capsys):
    rows = [_row("fabrik-review", "done", 10, ago_days=d) for d in (0.0, 1.0, 14.0, 20.0, 28.0)]
    ledger = _ledger(tmp_path / "l.jsonl", rows)
    out = _run(_args(tmp_path, ledger, "--commands", "fabrik-review", "--windows", "2"), capsys)
    w_old, w_new = out["windows"]
    assert w_new["end"].startswith("2026-10-15T00:00:00")
    assert w_old["end"] == w_new["start"]
    # ago 0 sits AT the end: outside [start, end). ago 14 sits AT the boundary: the newer window's start.
    assert w_new["commands"]["fabrik-review"]["closes"] == 2  # ago 1, ago 14
    assert w_old["commands"]["fabrik-review"]["closes"] == 2  # ago 20, ago 28
    # --start alone spans --days, never "until now"
    args = [
        a for a in _args(tmp_path, ledger, "--commands", "fabrik-review") if a not in ("--end", END)
    ]
    out = _run([*args, "--start", "2026-09-17T00:00:00+00:00"], capsys)
    assert out["windows"][0]["end"].startswith("2026-10-01T00:00:00")
    assert (
        out["windows"][0]["commands"]["fabrik-review"]["closes"] == 2
    )  # ago 20 = 09-25, ago 28 = 09-17 (= start)
    for bad in (
        ["--end", "2026-10-15T00:00:00"],
        ["--start", "2026-10-01T00:00:00+00:00", "--end", END, "--windows", "2"],
        ["--start", "2026-10-01T00:00:00+00:00", "--end", END, "--days", "7"],
        ["--start", END, "--end", "2026-10-01T00:00:00+00:00"],
    ):
        with pytest.raises(SystemExit):
            ctm.main([*_args(tmp_path, ledger)[:6], "--no-commits", *bad])


def test_wall_clock_and_closes_per_work_item(tmp_path, capsys):
    rows = [
        _row("fabrik-task", "done", 10, surface="W-0000000a build"),
        _row("fabrik-task", "blocked", 20, surface="resume W-0000000a then W-0000000b"),
        _row("fabrik-task", "done", 7, surface="W-0000000b"),
        _row("fabrik-task", "done", 99, surface="no id here"),
    ]
    m = _run(
        _args(tmp_path, _ledger(tmp_path / "l.jsonl", rows), "--commands", "fabrik-task"), capsys
    )
    m = m["windows"][0]["commands"]["fabrik-task"]
    # item a = 10 + 20 (the blocked close's FIRST id is a), item b = 7
    assert m["item_wall_min"]["n"] == 2
    assert m["item_wall_min"]["median"] == pytest.approx(18.5)
    assert m["item_wall_min"]["p90"] == pytest.approx(30.0)
    assert m["item_closes"]["mean"] == pytest.approx(1.5)  # a took 2 closes, b 1
    assert m["closes_without_item"] == 1


def _event(ts: str, event: str, command: str = "fabrik-review", **kw) -> str:
    return json.dumps({"sid": SID, "ts": ts, "event": event, "command": command, **kw}) + "\n"


def _seat(path: Path, stamps: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps({"timestamp": t, "type": "assistant"}) + "\n" for t in stamps) + "{}\n"
    )


def test_seat_minutes_gap_cut_union_and_sum(tmp_path, capsys):
    rows = [_row("fabrik-review", "done", 60, ago_days=0.5)]
    args = _args(tmp_path, _ledger(tmp_path / "l.jsonl", rows), "--commands", "fabrik-review")
    (tmp_path / "events" / f"{SID}.jsonl").write_text(
        _event(
            "2026-10-14T00:00:00+00:00", "run_close", verdict="done"
        )  # a close with no open: ignored
        + _event("2026-10-14T10:00:00+00:00", "run_open")
        + _event("2026-10-14T10:01:00+00:00", "dispatch", seats=2)
        + _event("2026-10-14T11:00:00+00:00", "run_close", verdict="done")
        + _event(
            "2026-10-14T12:00:00+00:00", "run_open"
        )  # a run with seats but no dispatch: not measured
        + _event("2026-10-14T12:30:00+00:00", "run_close", verdict="done")
    )
    sub = tmp_path / "projects" / "-opt-x" / SID / "subagents"
    # seat A: 10:05-10:15, an idle gap of 20 min (cut), then 10:35-10:40
    _seat(
        sub / "agent-a.jsonl",
        [
            "2026-10-14T10:05:00Z",
            "2026-10-14T10:15:00Z",
            "2026-10-14T10:35:00Z",
            "2026-10-14T10:40:00Z",
        ],
    )
    # seat B overlaps A's first segment, then runs past the close: 10:10-10:20, then 10:55-11:04 clipped to
    # 11:00, a lone stamp at 11:30, then 12:05-12:10 inside the undispatched run
    _seat(
        sub / "agent-b.jsonl",
        [
            "2026-10-14T10:10:00Z",
            "2026-10-14T10:20:00Z",
            "2026-10-14T10:55:00Z",
            "2026-10-14T11:04:00Z",
            "2026-10-14T11:30:00Z",
            "2026-10-14T12:05:00Z",
            "2026-10-14T12:10:00Z",
        ],
    )
    (sub / "agent-c.jsonl").write_text("{}\n")  # no timestamps at all: skipped, not fatal
    out = _run([*args, "--per-run"], capsys)
    m = out["windows"][0]["commands"]["fabrik-review"]
    # union: 10:05-10:20 (15) + 10:35-10:40 (5) + 10:55-11:00 (5) = 25 min of a 60-min run
    assert m["seat_min"]["n"] == 1 and m["seat_min"]["median"] == pytest.approx(25.0)
    # sum: A 10 + 5 = 15, B 10 + 5 = 15
    assert m["seat_sum_min"]["median"] == pytest.approx(30.0)
    assert m["seat_share"] == pytest.approx(25 / 60)
    assert m["dispatched_runs"] == 1
    run = next(r for r in out["runs"] if r["dispatches"])
    assert (run["seats"], run["seat_s"], run["seat_sum_s"], run["wall_s"]) == (
        2,
        1500.0,
        1800.0,
        3600.0,
    )
    assert [c["state"] for c in out["closes"]] == ["done"]
    # no gap cut: A spans 10:05-10:40 and B 10:10 to the 11:00 close, so the union is 10:05-11:00 = 55
    m = _run([*args, "--gap-min", "1000"], capsys)["windows"][0]["commands"]["fabrik-review"]
    assert m["seat_min"]["median"] == pytest.approx(55.0)


def _git(cwd: Path, *a: str, when: str | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null", *a],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def test_runs_per_commit_counts_trailered_commits_once(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for name, when, trailer in (
        ("a", "2026-10-14T10:00:00+00:00", True),
        ("b", "2026-10-14T11:00:00+00:00", True),
        ("c", "2026-10-14T12:00:00+00:00", False),
        ("d", "2026-09-01T12:00:00+00:00", True),
    ):
        (repo / name).write_text(name)
        _git(repo, "add", name)
        _git(
            repo,
            "commit",
            "-q",
            "-m",
            f"{name}\n\nAgent-Role: primary\n" if trailer else name,
            when=when,
        )
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", "side")
    gone = str(tmp_path / "gone")
    removed_wt = str(repo / ".claude" / "worktrees" / "removed")  # read through its main checkout
    not_git = tmp_path / "plain"
    not_git.mkdir()
    rows = [
        _row("fabrik-review", "done", 10, repo=r)
        for r in (str(wt), gone, removed_wt, str(not_git), str(wt))
    ]
    args = [
        a
        for a in _args(tmp_path, _ledger(tmp_path / "l.jsonl", rows), "--commands", "fabrik-review")
        if a != "--no-commits"
    ]
    w = _run(args, capsys)["windows"][0]
    # a and b: c lacks the trailer, d is outside the window and is the tip `--since` would have stopped at;
    # main and side share one common dir
    assert w["commits"] == 2
    assert len(w["commit_repos"]) == 1
    assert w["repos_gone"] == [gone]
    assert w["commit_errors"] == [str(not_git)]
    assert w["commands"]["fabrik-review"]["runs_per_commit"] == pytest.approx(5 / 2)


def test_surface_size_and_unparseable_input(tmp_path, capsys):
    rows = [
        _row("fabrik-task", "done", 1, loc="10", mini="0"),
        _row("fabrik-task", "done", 1, loc="30", mini="0"),
        _row("fabrik-task", "blocked", 1, loc="0", mini="unmeasurable=no-commit"),
        _row("fabrik-task", "done", 1, loc=None),
        _row("fabrik-task", "done", 1, loc="n/a"),
    ]
    bad_ts = json.dumps(_row("fabrik-task", "done", 1) | {"ts": "1792000000"})
    ledger = _ledger(tmp_path / "l.jsonl", rows, "not json", bad_ts)
    args = _args(tmp_path, ledger, "--commands", "fabrik-task")
    (tmp_path / "events" / f"{SID}.jsonl").write_text(
        "{broken\n"
        + json.dumps(
            {"sid": SID, "ts": "2026-10-14T10:00:00", "event": "run_open", "command": "fabrik-task"}
        )
        + "\n"
    )
    out = _run(args, capsys)
    m = out["windows"][0]["commands"]["fabrik-task"]
    assert m["loc_added"]["n"] == 2 and m["loc_added"]["median"] == pytest.approx(20.0)
    assert out["skipped"] == {"ledger_lines": 2, "event_lines": 2}
    with pytest.raises(SystemExit):
        ctm.main([*args[:2], "--events", str(tmp_path / "missing"), *args[4:]])


def test_text_report_runs_as_a_script(tmp_path):
    rows = [_row("fabrik-review", "done", 10)]
    p = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            *_args(tmp_path, _ledger(tmp_path / "l.jsonl", rows), "--commands", "fabrik-review"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 0, p.stderr
    assert "fabrik-review: closes 1" in p.stdout and "wall-clock min  median 10.0" in p.stdout
    assert "runs per commit not counted" in p.stdout
