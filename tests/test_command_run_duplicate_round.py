"""A blind retry of `command_run.py round` is refused, never recorded as a second round (W-fe322585).

The reporter piped every call through `2>&1 | tail -1`, saw no confirmation and re-ran it: round 3
landed twice (fabrik-lib row 1792454713.9674861). Worse, a retried quiet round 1 printed TERMINAL — the
retry met the two-round minimum with no closing pass run. A retry is recognised by what it lacks: the
last round closed seats, and nothing has run since — no fresh stamp, no newer seat transcript — while
the figures repeat. The behaviour tests drive the CLI by subprocess through the `COMMAND_RUN_DIR`,
`KAIZEN_EVENTS_DIR` and transcript seams (no live state, no checkout).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
REFUSED = "REFUSED — round 1 was already recorded"
TERMINAL = "✅ TERMINAL VERDICT"
# the first round every case retries: stamped seats, a confirming pass, a class opened
BASE = ("--findings", "3", "--confirmed", "2", "--classes-swept", "a,b", "--classes-new", "x")


def _transcript(run_dir: Path) -> Path:
    """The session transcript the seat count reads beside — present and empty: a session whose
    transcript cannot be found is never refused (its seats may sit elsewhere)."""
    return run_dir.parent / "transcript.jsonl"


def _cr(run_dir: Path, *args: str, transcript: bool = True) -> subprocess.CompletedProcess[str]:
    if transcript and not _transcript(run_dir).exists():
        _transcript(run_dir).parent.mkdir(parents=True, exist_ok=True)
        _transcript(run_dir).write_text("", encoding="utf-8")
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        "KAIZEN_EVENTS_DIR": str(run_dir.parent / "events"),
        "COMMAND_RUN_ACCOUNT_FILE": str(run_dir.parent / "no-marker"),
        "COMMAND_RUN_TRANSCRIPT": str(_transcript(run_dir)),
        "CLAUDE_SESSION_ID": "s1",
        "FABRIK_SCRATCH_SWEEP": "0",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
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


def _rec(run_dir: Path) -> dict:
    return json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))


def _start(run_dir: Path) -> None:
    _ok(_cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", "--terminal", "t"))


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A review record whose round 1 closed two stamped seats."""
    d = tmp_path / "runs"
    _start(d)
    _ok(_cr(d, "dispatch", "--seats", "2"))
    _ok(_cr(d, "round", *BASE, "--own-fix", "0"))
    assert _rec(d)["rounds"][-1]["seats"] == 2
    return d


def _refused(p: subprocess.CompletedProcess[str], run_dir: Path, rounds: int = 1) -> None:
    assert p.returncode == 2, p.stdout + p.stderr
    assert p.stdout.splitlines()[-1].startswith(REFUSED), p.stdout
    assert len(_rec(run_dir)["rounds"]) == rounds


def _recorded(p: subprocess.CompletedProcess[str], run_dir: Path, rounds: int = 2) -> None:
    assert p.returncode == 0, p.stdout + p.stderr
    assert REFUSED not in p.stdout
    assert len(_rec(run_dir)["rounds"]) == rounds


def test_a_blind_retry_of_a_stamped_round_is_refused(run_dir: Path) -> None:
    p = _cr(run_dir, "round", *BASE, "--own-fix", "0")
    _refused(p, run_dir)
    # the landed round's verdict — what the hidden output lost — is printed above the refusal
    assert "ROUND 1" in p.stdout
    # the refusal names both honest ways to record a new pass
    assert "dispatch --seats" in p.stdout.splitlines()[-1]
    assert "round --seats 0" in p.stdout.splitlines()[-1]
    # a caller reading stderr alone (stdout to /dev/null) sees it too
    assert REFUSED in p.stderr


def test_slices_decide_when_stated_on_both_sides(tmp_path: Path) -> None:
    d = tmp_path / "runs"
    _start(d)
    _ok(_cr(d, "dispatch", "--seats", "2"))
    _ok(_cr(d, "round", *BASE, "--own-fix", "0", "--slices", "A:1/2"))
    _refused(_cr(d, "round", *BASE, "--own-fix", "0", "--slices", "A:1/2"), d)
    _recorded(_cr(d, "round", *BASE, "--own-fix", "0", "--slices", "A:2/2"), d)


def test_a_retried_round_one_never_prints_terminal(tmp_path: Path) -> None:
    d = tmp_path / "runs"
    _start(d)
    _ok(_cr(d, "dispatch", "--seats", "2"))
    first = _ok(_cr(d, "round", "--findings", "0", "--confirmed", "0", "--classes-swept", "a"))
    assert TERMINAL not in first  # round 1 is the full pass, never the closing round
    p = _cr(d, "round", "--findings", "0", "--confirmed", "0", "--classes-swept", "a")
    _refused(p, d)
    assert TERMINAL not in p.stdout


@pytest.mark.parametrize(
    "spelling",
    [
        # the same call with its flags in another order
        (
            "--own-fix",
            "0",
            "--classes-new",
            "x",
            "--confirmed",
            "2",
            "--classes-swept",
            "a,b",
            "--findings",
            "3",
        ),
        # the swept classes listed in another order
        (
            "--findings",
            "3",
            "--confirmed",
            "2",
            "--classes-swept",
            "b,a",
            "--classes-new",
            "x",
            "--own-fix",
            "0",
        ),
        # --own-fix dropped on the retry (absent on one side matches)
        BASE,
        # --classes-swept dropped on the retry
        ("--findings", "3", "--confirmed", "2", "--classes-new", "x", "--own-fix", "0"),
        # the seat count typed by hand, equal to what the round closed
        (*BASE, "--own-fix", "0", "--seats", "2"),
    ],
    ids=[
        "flags-reordered",
        "swept-reordered",
        "own-fix-dropped",
        "swept-dropped",
        "same-seats-typed",
    ],
)
def test_every_spelling_of_the_same_call_is_refused(run_dir: Path, spelling: tuple) -> None:
    _refused(_cr(run_dir, "round", *spelling), run_dir)


def test_own_fix_added_on_a_retry_is_refused(tmp_path: Path) -> None:
    """The :6995 NOTE asks for --own-fix; the natural retry adds it to a round that never stated it."""
    d = tmp_path / "runs"
    _start(d)
    _ok(_cr(d, "dispatch", "--seats", "2"))
    _ok(_cr(d, "round", *BASE))
    _refused(_cr(d, "round", *BASE, "--own-fix", "0"), d)


@pytest.mark.parametrize(
    "change",
    [
        ("--findings", "4", "--confirmed", "2", "--classes-swept", "a,b", "--classes-new", "x"),
        ("--findings", "3", "--confirmed", "1", "--classes-swept", "a,b", "--classes-new", "x"),
        ("--findings", "3", "--confirmed", "2", "--classes-swept", "a,c", "--classes-new", "x"),
        ("--findings", "3", "--confirmed", "2", "--classes-swept", "a,b", "--classes-new", "y"),
        (*BASE, "--own-fix", "1"),
    ],
    ids=["findings", "confirmed", "swept", "classes-new", "own-fix"],
)
def test_a_changed_figure_records_the_round(run_dir: Path, change: tuple) -> None:
    _recorded(_cr(run_dir, "round", *change), run_dir)


def test_new_decides_only_when_stated_on_both_sides(tmp_path: Path) -> None:
    d = tmp_path / "runs"
    _start(d)
    _ok(_cr(d, "dispatch", "--seats", "2"))
    _ok(_cr(d, "round", *BASE, "--new", "1"))
    _recorded(_cr(d, "round", *BASE, "--new", "2"), d)  # stated on both and different: a new pass
    e = tmp_path / "runs-2"
    _start(e)
    _ok(_cr(e, "dispatch", "--seats", "2"))
    _ok(_cr(e, "round", *BASE))
    _refused(_cr(e, "round", *BASE, "--new", "1"), e)  # added on the retry only: a re-spelling


def test_a_new_phase_records_the_round(run_dir: Path) -> None:
    _ok(_cr(run_dir, "step", "--phase", "2", "--title", "next"))
    _recorded(_cr(run_dir, "round", *BASE, "--own-fix", "0"), run_dir)


def test_the_named_escapes_record_and_a_zero_dispatch_does_not(tmp_path: Path) -> None:
    def fresh() -> Path:
        d = tmp_path / f"runs-{len(list(tmp_path.iterdir()))}"
        _start(d)
        _ok(_cr(d, "dispatch", "--seats", "2"))
        _ok(_cr(d, "round", *BASE, "--own-fix", "0"))
        return d

    d = fresh()  # a fresh stamp: a new seat pass went out
    _ok(_cr(d, "dispatch", "--seats", "1"))
    _recorded(_cr(d, "round", *BASE, "--own-fix", "0"), d)
    d = fresh()  # a pass the lead ran alone says so
    _recorded(_cr(d, "round", *BASE, "--own-fix", "0", "--seats", "0"), d)
    d = fresh()  # `dispatch --seats 0` is a known zero, not a stamp
    _ok(_cr(d, "dispatch", "--seats", "0"))
    _refused(_cr(d, "round", *BASE, "--own-fix", "0"), d)
    d = fresh()  # a seat transcript newer than the last round: something ran, unstamped
    time.sleep(1.1)  # the seat line's whole-second stamp must clear the round's sub-second ts
    sub = d.parent / "transcript" / "subagents"
    sub.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    line = {
        "agentId": "z",
        "isSidechain": True,
        "type": "assistant",
        "timestamp": stamp,
        "message": {"id": "m", "usage": {"input_tokens": 1, "output_tokens": 1}},
    }
    (sub / "agent-z.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    _recorded(_cr(d, "round", *BASE, "--own-fix", "0"), d)


def test_no_seats_or_a_malformed_last_round_records(tmp_path: Path) -> None:
    d = tmp_path / "runs"  # a round that closed no seats: an in-shell backfill, never refused
    _start(d)
    _ok(_cr(d, "round", *BASE, "--own-fix", "0"))
    _recorded(_cr(d, "round", *BASE, "--own-fix", "0"), d)
    for bad in ("2", True, None):  # a hand-edited seat count fails open
        rp = d / "s1.json"
        rec = json.loads(rp.read_text(encoding="utf-8"))
        rec["rounds"][-1]["seats"] = bad
        rp.write_text(json.dumps(rec), encoding="utf-8")
        n = len(rec["rounds"])
        _recorded(_cr(d, "round", *BASE, "--own-fix", "0"), d, rounds=n + 1)


def test_a_refusal_emits_its_event_and_moves_nothing(run_dir: Path) -> None:
    before = _rec(run_dir)
    time.sleep(1.1)  # `updated_ts` is whole seconds: a `_touch` in the same second would not show
    _refused(_cr(run_dir, "round", *BASE, "--own-fix", "0"), run_dir)
    after = _rec(run_dir)
    assert after["updated_ts"] == before["updated_ts"]
    assert after["rounds"] == before["rounds"] and after["dispatch"] == before["dispatch"]
    assert after["event_seq"] == before["event_seq"] + 1  # dense: the event's seq is kept
    events = [
        json.loads(line)
        for f in (run_dir.parent / "events").glob("*.jsonl")
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    refused = [e for e in events if e.get("event") == "round_refused"]
    assert len(refused) == 1 and refused[0]["n"] == 1, events
    assert refused[0]["seq"] == after["event_seq"]
    assert [e["n"] for e in events if e.get("event") == "round"] == [1]


def _inproc(run_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """The script loaded in-process on the same seams `_cr` uses, for failure paths no CLI input
    reaches."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("command_run_dup_ut", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for k, v in {
        "COMMAND_RUN_DIR": str(run_dir),
        "KAIZEN_EVENTS_DIR": str(run_dir.parent / "events"),
        "COMMAND_RUN_ACCOUNT_FILE": str(run_dir.parent / "no-marker"),
        "COMMAND_RUN_TRANSCRIPT": str(_transcript(run_dir)),
        "CLAUDE_SESSION_ID": "s1",
        "FABRIK_SCRATCH_SWEEP": "0",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.chdir(run_dir.parent)
    return mod


def _boom(*_a: object, **_k: object) -> list:
    raise OSError("unreadable")


def test_an_unfinished_seat_count_records_rather_than_refuses(
    run_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seat scan that could not complete may have missed a seat that ran: the guard fails toward
    recording. Unreachable from data through the CLI, so the module runs in-process with the scan
    made to raise."""
    mod = _inproc(run_dir, monkeypatch)
    monkeypatch.setattr(mod, "_seat_transcripts", _boom)
    assert mod.main(["round", *BASE, "--own-fix", "0"]) == 0
    assert len(_rec(run_dir)["rounds"]) == 2


def test_a_missing_session_transcript_records_rather_than_refuses(tmp_path: Path) -> None:
    """No transcript, no evidence either way: its seat directory may sit elsewhere (round-1 review,
    both slice-A seats — a real seat pass typed with the same count was refused)."""
    d = tmp_path / "runs"
    _ok(
        _cr(
            d,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            "--terminal",
            "t",
            transcript=False,
        )
    )
    _ok(_cr(d, "dispatch", "--seats", "3", transcript=False))
    _ok(_cr(d, "round", *BASE, transcript=False))
    p = _cr(d, "round", *BASE, "--seats", "3", transcript=False)
    _recorded(p, d)
    assert not _transcript(d).exists()


def test_a_report_that_raises_never_swallows_the_refusal(
    run_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _inproc(run_dir, monkeypatch)
    monkeypatch.setattr(mod, "_round_report", _boom)
    assert mod.main(["round", *BASE, "--own-fix", "0"]) == 2
    assert capsys.readouterr().out.splitlines()[-1].startswith(REFUSED)
    assert len(_rec(run_dir)["rounds"]) == 1


def test_an_unreadable_landed_time_is_said_as_unknown(run_dir: Path) -> None:
    rp = run_dir / "s1.json"
    rec = json.loads(rp.read_text(encoding="utf-8"))
    rec["rounds"][-1]["ts"] = "not-a-time"
    rp.write_text(json.dumps(rec), encoding="utf-8")
    p = _cr(run_dir, "round", *BASE, "--own-fix", "0")
    _refused(p, run_dir)
    assert "recorded at an unknown time with these figures" in p.stdout.splitlines()[-1]
