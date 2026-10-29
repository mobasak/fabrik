"""W-79638b4a (kaizen's mail 01M4X6XQH0, two feedback verdicts):

1. An operator's "pause when you finish" had no honest close: `done` claims the terminal condition,
   `blocked` takes only the three named causes or `--wall`, so the Stop hook blocked every turn end
   until the session invented one. `blocked --paused --reason "<the operator's words>"` closes the
   run and keeps the same resume seed `--wall` keeps, so `start --resume-from` reopens it.
2. The close verbs name the run they close, but `round` could not, so a nested caller had no check
   that a round landed on the run it meant. `round --command <name>` is now refused (rc 1, nothing
   recorded) when it is not the live run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_command_run import _PROBE, _cr, _start, run_dir  # noqa: E402,F401 — shared helpers


def _rec(run_dir: Path, sid: str = "s1") -> dict:  # noqa: F811
    return json.loads((run_dir / f"{sid}.json").read_text(encoding="utf-8"))


def test_an_operator_pause_closes_the_run_and_keeps_a_resume_seed(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "2", "--confirmed", "1", "--classes-new", "a")
    out = _cr(
        run_dir,
        "blocked",
        "--command",
        _PROBE,
        "--paused",
        "--reason",
        "operator: pause when you finish",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    rec = _rec(run_dir)
    assert rec["state"] == "blocked" and rec.get("paused") is True, rec
    seed = Path(rec["resume_seed"])
    assert seed.is_file() and seed.parent == run_dir.resolve() / "seeds", seed
    assert f"--resume-from {seed}" in out.stdout, out.stdout
    assert "quota" not in out.stdout.lower(), out.stdout  # a pause is never called the wall


def test_a_paused_run_reopens_from_its_seed_with_its_rounds(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "2", "--confirmed", "1", "--classes-new", "a")
    _cr(run_dir, "blocked", "--command", _PROBE, "--paused", "--reason", "operator: stop for today")
    seed = _rec(run_dir)["resume_seed"]
    out = _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "5",
        "--terminal",
        "t",
        "--resume-from",
        seed,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    rec = _rec(run_dir)
    assert rec["state"] == "running" and len(rec.get("rounds") or []) == 1, rec


def test_paused_and_wall_are_exclusive(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(run_dir, "blocked", "--command", _PROBE, "--paused", "--wall", "--reason", "x")
    assert out.returncode == 2 and "not allowed with" in out.stderr, out.stdout + out.stderr
    assert _rec(run_dir)["state"] == "running"
    assert not (run_dir / "seeds").exists() or not any((run_dir / "seeds").iterdir())


def test_a_plain_blocked_still_keeps_no_seed(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(
        run_dir, "blocked", "--command", _PROBE, "--reason", "3 consecutive same-test failures"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    rec = _rec(run_dir)
    assert not rec.get("paused") and not rec.get("wall") and not rec.get("resume_seed"), rec


def test_round_with_the_live_command_records_the_round(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(run_dir, "round", "--command", _PROBE, "--findings", "1", "--confirmed", "0")
    assert out.returncode == 0, out.stdout + out.stderr
    assert len(_rec(run_dir)["rounds"]) == 1


def test_round_naming_a_run_that_is_not_live_is_refused_and_records_nothing(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(run_dir, "round", "--command", "fabrik-review", "--findings", "1", "--confirmed", "0")
    assert out.returncode == 1, out.stdout + out.stderr
    assert "LIVE run is /" + _PROBE in out.stdout + out.stderr, out.stdout + out.stderr
    assert not _rec(run_dir).get("rounds")


def test_round_without_command_is_unchanged(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(run_dir, "round", "--findings", "1", "--confirmed", "0")
    assert out.returncode == 0, out.stdout + out.stderr
    assert len(_rec(run_dir)["rounds"]) == 1


def _ledger(run_dir: Path) -> list[dict]:  # noqa: F811
    path = run_dir.parent / "command-feedback.jsonl"
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _events(run_dir: Path, sid: str = "s1") -> list[dict]:  # noqa: F811
    path = run_dir.parent / "events" / f"{sid}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_a_pause_is_counted_as_paused_in_the_ledger_row_and_the_close_event(run_dir: Path) -> None:  # noqa: F811
    """Critique fold: both `wall` writers carry `paused`, never `quota` (a mutant reverting them
    passed all seven tests before)."""
    _start(run_dir)
    _cr(run_dir, "blocked", "--command", _PROBE, "--paused", "--reason", "operator: pause")
    assert _ledger(run_dir)[-1]["wall"] == "paused", _ledger(run_dir)[-1]
    close = [e for e in _events(run_dir) if e.get("event") == "run_close"][-1]
    assert close["wall"] == "paused", close
    assert "-paused-" in Path(_rec(run_dir)["resume_seed"]).name


def test_a_resumed_paused_run_names_its_first_sitting_as_paused(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    _cr(run_dir, "blocked", "--command", _PROBE, "--paused", "--reason", "operator: pause")
    seed = _rec(run_dir)["resume_seed"]
    _cr(
        run_dir,
        "start",
        "--command",
        _PROBE,
        "--phases",
        "5",
        "--terminal",
        "t",
        "--resume-from",
        seed,
    )
    assert _rec(run_dir)["resumed_from"]["paused"] is True
    out = _cr(
        run_dir, "blocked", "--command", _PROBE, "--reason", "3 consecutive same-test failures"
    )
    assert "carried from the paused sitting" in out.stdout and "(wall: paused)" in out.stdout, (
        out.stdout
    )


def test_a_pause_reason_naming_the_quota_wall_is_still_a_pause(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(
        run_dir,
        "blocked",
        "--command",
        _PROBE,
        "--paused",
        "--reason",
        "operator: stop before the quota wall",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert _ledger(run_dir)[-1]["wall"] == "paused"
    assert "close with `blocked --wall` instead" in out.stderr, out.stderr


def test_a_nested_pause_names_the_parent_flag(run_dir: Path) -> None:  # noqa: F811
    _cr(run_dir, "start", "--command", "fabrik-execute-plan", "--phases", "5", "--terminal", "t")
    _start(run_dir)
    out = _cr(run_dir, "blocked", "--command", _PROBE, "--paused", "--reason", "operator: pause")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "close it too with `blocked --paused`" in out.stdout, out.stdout


def test_round_with_an_empty_command_is_refused(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(run_dir, "round", "--command", "", "--findings", "1", "--confirmed", "0")
    assert out.returncode == 1, out.stdout + out.stderr
    assert not _rec(run_dir).get("rounds")


def test_round_command_is_compared_normalised(run_dir: Path) -> None:  # noqa: F811
    """Review pass 1 (a raw-string compare mutant survived): a leading slash and another case
    name the same live run, as the close verbs accept."""
    _start(run_dir)
    out = _cr(
        run_dir, "round", "--command", "/" + _PROBE.upper(), "--findings", "0", "--confirmed", "0"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert len(_rec(run_dir)["rounds"]) == 1


def test_an_empty_round_command_says_it_was_empty(run_dir: Path) -> None:  # noqa: F811
    _start(run_dir)
    out = _cr(run_dir, "round", "--command", "  ", "--findings", "0", "--confirmed", "0")
    assert out.returncode == 1 and "(empty)" in out.stdout, out.stdout
