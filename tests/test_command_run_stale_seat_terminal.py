"""A round that closes only seats dispatched BEFORE the latest confirming round was recorded cannot
have read that round's fix, so it is never the TERMINAL round (W-128df814; fleet's row 1792465351,
confirmed [4, 0, 0]: a wave round for a round-1 Haiku seat printed TERMINAL before the fix was
re-verified).

The stamp keeps its seats as dispatch batches and a partial close is attributed OLDEST batch first, so
a stale seat closing alone reads stale even when a fresh one went out after it. Every test drives
`command_run.py` by subprocess through the `COMMAND_RUN_DIR` seam — no live state, no checkout.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
STALE = "⛔ NOT TERMINAL — every seat this round closed was dispatched before round"
TERMINAL = "✅ TERMINAL VERDICT"


def _cr(run_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        "KAIZEN_EVENTS_DIR": str(run_dir.parent / "events"),
        "CLAUDE_SESSION_ID": "s1",
        "FABRIK_SCRATCH_SWEEP": "0",
    }
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=str(run_dir.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _ok(p: subprocess.CompletedProcess[str]) -> str:
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runs"
    _ok(_cr(d, "start", "--command", "fabrik-review", "--phases", "5", "--terminal", "t"))
    return d


def _rec(run_dir: Path) -> dict:
    return json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))


def _confirming_round(run_dir: Path, *seats: str) -> None:
    _ok(
        _cr(
            run_dir,
            "round",
            "--findings",
            "20",
            "--confirmed",
            "4",
            "--own-fix",
            "0",
            "--classes-new",
            "a",
            *seats,
        )
    )


def _quiet(run_dir: Path, *extra: str) -> str:
    return _ok(
        _cr(
            run_dir,
            "round",
            "--findings",
            "0",
            "--confirmed",
            "0",
            "--own-fix",
            "0",
            "--classes-swept",
            "a",
            *extra,
        )
    )


def test_a_wave_round_after_a_confirming_round_is_not_terminal(run_dir: Path) -> None:
    """Behaviour 4 — the replayed incident: two round-1 seats go out, one returns with 4 confirmed,
    the slow one closes alone in round 2."""
    _ok(_cr(run_dir, "dispatch", "--seats", "2"))
    _confirming_round(run_dir, "--seats", "1")
    out = _quiet(run_dir)
    assert TERMINAL not in out, out
    assert f"{STALE} 1 RECORDED its 4 confirmed defect(s)" in out, out
    assert isinstance(_rec(run_dir)["rounds"][-1]["dispatched_at"], float)


def test_the_stale_check_boundary_and_its_fail_open_inputs() -> None:
    """Behaviour 4's edge: a seat dispatched AT the confirming round's record time is stale (it
    cannot have seen a fix written after that record); one dispatched later is not. An absent or
    non-numeric `dispatched_at`, or a confirming round with no usable `ts`, fails open."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("command_run_stale_ut", SCRIPT)
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    conf = {"confirmed": 4, "ts": 100.0}
    assert cr._stale_seat_round([conf, {"confirmed": 0, "dispatched_at": 100.0}]) == (1, 4)
    assert cr._stale_seat_round([conf, {"confirmed": 0, "dispatched_at": 100.5}]) is None
    assert cr._stale_seat_round([conf, {"confirmed": 0}]) is None
    assert cr._stale_seat_round([conf, {"confirmed": 0, "dispatched_at": "x"}]) is None
    assert cr._stale_seat_round([{"confirmed": 4}, {"confirmed": 0, "dispatched_at": 1.0}]) is None


def test_a_second_stale_wave_round_is_not_terminal(run_dir: Path) -> None:
    """Behaviour 5 — the anchor is the NEWEST confirming round, never round N-1 alone: a quiet
    stale round between them does not launder the next one."""
    _ok(_cr(run_dir, "dispatch", "--seats", "3"))
    _confirming_round(run_dir, "--seats", "1")
    assert STALE in _quiet(run_dir, "--seats", "1")
    out = _quiet(run_dir)
    assert TERMINAL not in out and f"{STALE} 1 RECORDED" in out, out


def test_batches_attribute_a_partial_close_oldest_first(run_dir: Path) -> None:
    """Behaviour 6 — a fresh verifier dispatched on top of a stale remainder: the stale seat's
    partial close is attributed to the OLD batch (not terminal), the fresh seat's close to the new one
    (terminal); `dispatch --seats 0` adds no batch."""
    _ok(_cr(run_dir, "dispatch", "--seats", "2"))
    _confirming_round(run_dir, "--seats", "1")
    _ok(_cr(run_dir, "dispatch", "--seats", "1"))
    _ok(_cr(run_dir, "dispatch", "--seats", "0"))
    batches = _rec(run_dir)["dispatch"]["batches"]
    assert [n for _ts, n in batches] == [1, 1], batches
    out = _quiet(run_dir, "--seats", "1")
    assert STALE in out and TERMINAL not in out, out
    stamp = _rec(run_dir)["dispatch"]
    assert stamp["seats"] == 1 and [n for _ts, n in stamp["batches"]] == [1], stamp
    assert stamp["batches"][0][0] > _rec(run_dir)["rounds"][0]["ts"], stamp
    out = _quiet(run_dir)
    assert TERMINAL in out, out


def test_a_zero_dispatch_never_buys_a_fresh_time(run_dir: Path) -> None:
    """Behaviour 6 (cobra) — `dispatch --seats 0` over a stale remainder re-dates the stamp's `ts`
    but adds no batch, so the stale seat's close still reads stale."""
    _ok(_cr(run_dir, "dispatch", "--seats", "2"))
    _confirming_round(run_dir, "--seats", "1")
    _ok(_cr(run_dir, "dispatch", "--seats", "0"))
    out = _quiet(run_dir)
    assert STALE in out and TERMINAL not in out, out


def test_legacy_and_unstamped_rounds(run_dir: Path, tmp_path: Path) -> None:
    """Behaviour 7 — a stamp written before batches existed counts as ONE batch at its `ts` (a zero
    dispatch on top of it cannot re-date it); a round with no stamp keeps today's verdict and records
    no `dispatched_at`."""
    _ok(_cr(run_dir, "dispatch", "--seats", "2"))
    _confirming_round(run_dir, "--seats", "1")
    path = run_dir / "s1.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec["dispatch"].pop("batches", None)  # the legacy shape
    path.write_text(json.dumps(rec), encoding="utf-8")
    _ok(_cr(run_dir, "dispatch", "--seats", "0"))
    out = _quiet(run_dir)
    assert STALE in out and TERMINAL not in out, out

    other = tmp_path / "runs2"
    _ok(_cr(other, "start", "--command", "fabrik-review", "--phases", "5", "--terminal", "t"))
    _confirming_round(other, "--seats", "3")
    out = _quiet(other, "--seats", "2")
    assert TERMINAL in out, out
    assert "dispatched_at" not in _rec(other)["rounds"][-1]
