"""Tests for scripts/command_feedback_report.py — the per-command optimisation report over the
fleet-wide close-out ledger (`~/.claude/state/command-feedback.jsonl`)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_feedback_report.py"


def _row(cmd: str, wall: float, rounds: int, change: str, days_ago: float = 0.0, **kw) -> dict:
    base = {
        "ts": time.time() - days_ago * 86400,
        "sid": "s",
        "repo": "/opt/x",
        "command": cmd,
        "state": "done",
        "wall_s": wall,
        "rounds": rounds,
        "findings": [1, 0],
        "phases": 3,
        "confusion": "none",
        "waste": "none",
        "change": change,
        "filed": "none — surfaces exercised: x",
    }
    base.update(kw)
    return base


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _run(ledger: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--ledger", str(ledger), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_report_aggregates_per_command_and_lists_the_change_items(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("fabrik-review", 600, 4, "name the rubric command in step 2"),
            _row("fabrik-review", 1200, 2, "name the rubric command in step 2"),
            _row("fabrik-review", 300, 3, "none", confusion="step 3 'arm' reads as dispatch"),
            _row("fabrik-spec", 900, 1, "drop the literature step for delta profiles"),
        ],
    )
    r = _run(ledger, "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    rev = out["commands"]["fabrik-review"]
    assert rev["runs"] == 3 and rev["median_wall_min"] == 10.0 and rev["median_rounds"] == 3
    assert rev["change_none"] == 1
    assert out["backlog"][0]["item"] == "name the rubric command in step 2"
    assert out["backlog"][0]["count"] == 2 and out["backlog"][0]["command"] == "fabrik-review"
    assert any("arm" in c["item"] for c in out["confusion"])
    text = _run(ledger).stdout
    assert "fabrik-review" in text and "name the rubric command" in text


def test_since_and_command_filters_bound_the_report(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("fabrik-review", 600, 4, "old item", days_ago=40),
            _row("fabrik-review", 600, 4, "new item", days_ago=1),
            _row("fabrik-spec", 100, 1, "spec item", days_ago=1),
        ],
    )
    out = json.loads(_run(ledger, "--json", "--since", "30").stdout)
    assert out["commands"]["fabrik-review"]["runs"] == 1
    assert [b["item"] for b in out["backlog"]] == ["new item", "spec item"] or [
        b["item"] for b in out["backlog"]
    ] == ["spec item", "new item"]
    only = json.loads(_run(ledger, "--json", "--command", "fabrik-spec").stdout)
    assert list(only["commands"]) == ["fabrik-spec"]
    assert out["examined"] == 2 and out["total_rows"] == 3  # the bound is stated


def test_a_missing_ledger_is_an_empty_report_not_a_crash(tmp_path: Path) -> None:
    r = _run(tmp_path / "nope.jsonl", "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["commands"] == {} and out["total_rows"] == 0
