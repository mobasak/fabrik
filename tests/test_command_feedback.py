"""Behavior-Contract tests for the structured close-out USAGE feedback (D-175, operator's 6th ask).

Every close (`done` / `blocked` / `handoff`) of a run started after the cutoff must carry the four
labelled fields — `confusion:` `waste:` `change:` `filed:` — so the feedback describes how the
COMMAND behaved (what confused, what cost tokens for nothing, the one edit that would have made
the run faster or more accurate, what was filed), not only what was mailed. The close refuses
anything else, appends a row to the fleet-wide ledger with the auto-captured wall-clock and
round count, and prints the exact `FEEDBACK:` line to paste into the FINAL OUTPUT block.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
STRUCTURED = (
    "confusion: step 3's 'arm' verb read as a dispatch · waste: two gate re-runs on an "
    "unchanged tree · change: name the rubric command in step 2 · filed: none — surfaces "
    "exercised: the rubric, the round ledger"
)


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state" / "command-runs"
    d.mkdir(parents=True)
    return d


def _cr(run_dir: Path, *args: str, sid: str = "s1") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "COMMAND_RUN_DIR": str(run_dir), "CLAUDE_SESSION_ID": sid}
    env.pop("CLAUDE_AGENT", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env
    )


def _start(run_dir: Path) -> None:
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "3",
        "--terminal",
        "found:0 no-op round",
    )
    assert r.returncode == 0, r.stdout + r.stderr


def _ledger(run_dir: Path) -> list[dict]:
    p = run_dir.parent / "command-feedback.jsonl"
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_a_close_without_the_four_usage_fields_is_refused(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "round 3 found: 0",
        "--feedback",
        "none — surfaces exercised: the rubric, the round ledger",
    )
    assert r.returncode == 1, r.stdout
    assert "confusion:" in r.stdout and "waste:" in r.stdout and "change:" in r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running"  # the refusal leaves the record where the Stop hook sees it
    assert _ledger(run_dir) == []


def test_a_structured_close_lands_a_ledger_row_with_the_auto_captured_metrics(
    run_dir: Path,
) -> None:
    _start(run_dir)
    _cr(run_dir, "round", "--findings", "4", "--classes-swept", "a,b", "--classes-new", "")
    _cr(run_dir, "round", "--findings", "0", "--classes-swept", "a,b", "--classes-new", "")
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "round 2 found: 0",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    rows = _ledger(run_dir)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["command"] == "fabrik-probe" and row["state"] == "done" and row["sid"] == "s1"
    assert row["rounds"] == 2 and row["findings"] == [4, 0]
    assert isinstance(row["wall_s"], (int, float)) and row["wall_s"] >= 0
    assert row["confusion"].startswith("step 3's")
    assert row["waste"].startswith("two gate re-runs")
    assert row["change"].startswith("name the rubric")
    assert row["filed"].startswith("none — surfaces exercised")
    # the printed line is the FINAL OUTPUT block's 7th line, ready to paste
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("FEEDBACK:"))
    assert "/fabrik-probe" in line and "rounds 2" in line and "change: name the rubric" in line
    # the filing verdict is still classified from the `filed:` field alone
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["feedback"] == "none", rec["feedback"]


def test_a_filed_field_still_classifies_as_filed(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-probe",
        "--reason",
        "missing infra - searched: a - missing: b",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: 01M11VS2ZE to intel — dead modules",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["feedback"] == "filed" and rec["feedback_to"] == ["intel"]
    assert _ledger(run_dir)[0]["state"] == "blocked"


def test_an_empty_field_value_is_refused_like_a_missing_one(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: · waste: none · change: none · filed: none — surfaces exercised: x",
    )
    assert r.returncode == 1, r.stdout
    assert "confusion:" in r.stdout


def test_a_bare_none_in_the_filed_field_is_still_refused(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: none",
    )
    assert r.returncode == 1, r.stdout
    assert "surfaces" in r.stdout.lower()
