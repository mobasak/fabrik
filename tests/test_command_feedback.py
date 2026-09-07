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
    assert "missing, empty or duplicated: confusion:" in r.stdout, r.stdout


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


def test_a_label_named_inside_a_value_does_not_split_the_field(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: rename the 'waste:' label to 'burn:' · "
        "filed: mailed the cost:5 defect 01M1XYZ to infra",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["change"] == "rename the 'waste:' label to 'burn:'", row
    assert row["filed"] == "mailed the cost:5 defect 01M1XYZ to infra", row
    assert row["cost"] == "", row


def test_a_duplicated_label_is_refused_not_last_wins(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: 01M1 to infra · filed: none",
    )
    assert r.returncode == 1, r.stdout
    assert "filed (duplicate):" in r.stdout, r.stdout
    assert _ledger(run_dir) == []


def test_a_grandfathered_close_writes_no_ledger_row_even_when_its_text_carries_a_label(
    run_dir: Path,
) -> None:
    _start(run_dir)
    f = run_dir / "s1.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    rec["started_at"] = (
        "2026-08-30T00:00:00+00:00"  # after the presence cutoff, before the usage one
    )
    f.write_text(json.dumps(rec), encoding="utf-8")
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--feedback",
        "filed: 01M1 to infra — the old free-text shape, one label by accident",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir) == []
    assert not any(ln.startswith("FEEDBACK:") for ln in r.stdout.splitlines())


def test_the_row_carries_agent_surface_account_and_a_numeric_cost(
    run_dir: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "active-account"
    marker.write_text("ob-ocoron-com-s-organization\n", encoding="utf-8")
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "CLAUDE_AGENT": "infra",
        "COMMAND_RUN_ACCOUNT_FILE": str(marker),
    }
    args = [
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "1",
        "--terminal",
        "t",
        "--surface",
        "docs/development/plans/2026-09-07-plan-1-x.md",
    ]
    r = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED + " · cost: pool $0.0125",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["agent"] == "infra"
    assert row["surface"] == "docs/development/plans/2026-09-07-plan-1-x.md"
    assert row["account"] == "ob-ocoron-com-s-organization"
    assert row["cost"] == "pool $0.0125" and row["cost_usd"] == 0.0125


def test_missing_agent_surface_account_and_cost_record_as_empty_not_absent(run_dir: Path) -> None:
    env = {
        **os.environ,
        "COMMAND_RUN_DIR": str(run_dir),
        "CLAUDE_SESSION_ID": "s1",
        "COMMAND_RUN_ACCOUNT_FILE": str(run_dir / "no-such-marker"),
    }
    env.pop("CLAUDE_AGENT", None)
    r = subprocess.run(  # no --surface, no CLAUDE_AGENT, no account marker
        [
            sys.executable,
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-probe",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "x",
            "--feedback",
            STRUCTURED,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _ledger(run_dir)[0]
    assert row["agent"] == "" and row["surface"] == "" and row["account"] == ""
    assert row["cost"] == "" and row["cost_usd"] is None


def test_the_close_can_name_the_surface_a_start_omitted(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--surface",
        "git diff a1b2c3d..HEAD",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir)[0]["surface"] == "git diff a1b2c3d..HEAD"


def test_cost_usd_parses_marked_or_whole_numbers_and_never_prose() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_run import _cost_usd  # noqa: PLC0415

    assert _cost_usd("pool $0.0125") == 0.0125
    assert _cost_usd("0.03") == 0.03
    assert _cost_usd("pool 0.0017 USD") == 0.0017
    assert _cost_usd("$1,234.50") == 1234.5
    assert _cost_usd("about 0.01 usd across three units") == 0.01
    assert _cost_usd("2 hold-era commits, 1 orphaned native pass") is None  # prose, not dollars
    assert _cost_usd("") is None


def test_a_refused_close_does_not_persist_its_late_surface(run_dir: Path) -> None:
    _start(run_dir)
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-other",
        "--evidence",
        "x",
        "--surface",
        "late-surface",
        "--feedback",
        STRUCTURED,
    )
    assert r.returncode == 1, r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["surface"] == "" and rec["state"] == "running"
    # a second, LATER refusal path — the usage-field check — must not persist it either
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "x",
        "--surface",
        "late-surface",
        "--feedback",
        "confusion: none · waste: none",
    )
    assert r.returncode == 1, r.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["surface"] == "" and rec["state"] == "running"
    assert _ledger(run_dir) == []
