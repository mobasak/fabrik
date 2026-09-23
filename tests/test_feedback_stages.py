"""`command_feedback_report.py --stages` — how many review stages fire per change, and what each yields (row 5b
chunk 3, D-358; § 4.9 finding 35 of command-loop-performance.md).

`confirmed` is the ledger's per-round LIST (its real shape; a scalar fixture once hid a report of all zeros). A change is keyed from the row's `surface`: a plan slug (`YYYY-MM-DD-plan-…`), else a spec slug
(`YYYY-MM-DD-…-design`), else a decision id (`D-nnn`). Measured 2026-09-23: 101 of 239 review-family rows carried
one, so the report prints its own coverage — an unkeyed row is counted, never dropped.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "scripts" / "command_feedback_report.py"


def _ledger(tmp: Path) -> Path:
    rows = [
        {
            "command": "fabrik-spec-review",
            "surface": "docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md",
            "rounds": 5,
            "confirmed": [7, 3, 2, 0, 0],
            "wall_s": 3600,
            "repo": "/opt/fabrik",
            "ts": 1,
        },
        {
            "command": "fabrik-plan-review",
            "surface": "docs/development/plans/2026-09-18-plan-1-fabrik-task-lane",
            "rounds": 5,
            "confirmed": [40, 20, 10, 7, 0],
            "wall_s": 7200,
            "repo": "/opt/fabrik",
            "ts": 2,
        },
        {
            "command": "fabrik-review",
            "surface": "T01a of 2026-09-18-plan-1-fabrik-task-lane",
            "rounds": 3,
            "confirmed": [3, 1, 0],
            "wall_s": 1800,
            "repo": "/opt/fabrik",
            "ts": 3,
        },
        {
            "command": "fabrik-review-scoped",
            "surface": "the D-355 change",
            "rounds": 2,
            "confirmed": [1, 0],
            "wall_s": 600,
            "repo": "/opt/fabrik",
            "ts": 4,
        },
        {
            "command": "fabrik-review-scoped",
            "surface": "a plain-chat edit",
            "rounds": 2,
            "confirmed": [0, 0],
            "wall_s": 300,
            "repo": "/opt/fabrik",
            "ts": 5,
        },
        {
            "command": "fabrik-spec",
            "surface": "2026-09-17-fabrik-task-lane-design",
            "rounds": 0,
            "wall_s": 900,
            "repo": "/opt/fabrik",
            "ts": 6,
        },
    ]
    p = tmp / "ledger.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=60, check=False
    )


def test_stages_groups_review_runs_by_change_and_states_its_coverage(tmp_path: Path) -> None:
    r = _run("--stages", "--ledger", str(_ledger(tmp_path)), "--json")
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    by_key = {c["key"]: c for c in doc["changes"]}
    plan = by_key["2026-09-18-plan-1-fabrik-task-lane"]
    assert plan["stages"] == 2 and plan["commands"] == {"fabrik-plan-review": 1, "fabrik-review": 1}
    assert plan["confirmed"] == 81 and plan["rounds"] == 8
    assert by_key["2026-09-17-fabrik-task-lane-design"]["stages"] == 1, (
        "a non-review command is not a stage"
    )
    assert by_key["D-355"]["stages"] == 1
    assert doc["coverage"] == {"review_rows": 5, "keyed": 4, "unkeyed": 1}


def test_stages_text_names_the_denominator_and_refuses_another_mode(tmp_path: Path) -> None:
    led = str(_ledger(tmp_path))
    r = _run("--stages", "--ledger", led)
    assert r.returncode == 0 and "4 of 5 review-family runs keyed" in r.stdout, r.stdout
    both = _run("--stages", "--observer-rank", "--ledger", led)
    assert both.returncode == 2, both.stdout


def test_a_plans_review_receipt_keys_to_the_plan_itself(tmp_path: Path) -> None:
    """A receipt is named `<plan>-review.md`; its surface must key to the plan, or one change reads as two."""
    p = tmp_path / "l.jsonl"
    p.write_text(
        json.dumps(
            {
                "command": "fabrik-review",
                "surface": "docs/development/reviews/2026-09-18-plan-1-fabrik-task-lane-review.md",
                "rounds": 2,
                "confirmed": [1, 0],
                "wall_s": 60,
                "repo": "/r",
                "ts": 1,
            }
        )
        + "\n"
        + json.dumps(
            {
                "command": "fabrik-plan-review",
                "surface": "docs/development/plans/2026-09-18-plan-1-fabrik-task-lane",
                "rounds": 2,
                "confirmed": [3, 0],
                "wall_s": 60,
                "repo": "/r",
                "ts": 2,
            }
        )
        + "\n"
    )
    r = _run("--stages", "--ledger", str(p), "--json")
    keys = [c["key"] for c in json.loads(r.stdout)["changes"]]
    assert keys == ["2026-09-18-plan-1-fabrik-task-lane"], keys


def test_bad_numbers_never_bend_a_change_and_repos_are_named(tmp_path: Path) -> None:
    """Review of D-358 pass 1: a negative or non-numeric figure dragged a change negative (A-S1); hours were re-rounded
    on every row and drifted (B-S1); two repos sharing a slug printed as twin rows with no repo (A-S2)."""
    p = tmp_path / "l.jsonl"
    rows = [
        {
            "command": "fabrik-review",
            "surface": "2026-09-18-plan-1-x",
            "rounds": -5,
            "confirmed": [-100, "x", None, 3],
            "wall_s": -9999,
            "repo": "/opt/a",
            "ts": 1,
        },
        *[
            {
                "command": "fabrik-review",
                "surface": "2026-09-18-plan-1-x",
                "rounds": 1,
                "confirmed": [1],
                "wall_s": 1,
                "repo": "/opt/a",
                "ts": 2 + i,
            }
            for i in range(3)
        ],
        {
            "command": "fabrik-review",
            "surface": "2026-09-18-plan-1-x",
            "rounds": 1,
            "confirmed": [2],
            "wall_s": 3600,
            "repo": "/opt/b",
            "ts": 9,
        },
    ]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    doc = json.loads(_run("--stages", "--ledger", str(p), "--json").stdout)
    a = next(c for c in doc["changes"] if c["repo"] == "/opt/a")
    assert a["rounds"] == 3 and a["confirmed"] == 6 and a["hours"] == 0.0, a
    text = _run("--stages", "--ledger", str(p)).stdout
    assert "\trepo\tchange\t" in text, text
    assert "\ta\t2026-09-18-plan-1-x\t" in text and "\tb\t2026-09-18-plan-1-x\t" in text, text
