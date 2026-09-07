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


def test_since_zero_is_a_real_cutoff_and_medians_are_integral_when_they_are(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("fabrik-review", 600, 4, "a", days_ago=0.5),
            _row("fabrik-review", 600, 2, "b", days_ago=0.5),
        ],
    )
    out = json.loads(_run(ledger, "--json", "--since", "0").stdout)
    assert out["examined"] == 0 and out["total_rows"] == 2  # 0 days back examines nothing
    full = json.loads(_run(ledger, "--json").stdout)
    assert full["commands"]["fabrik-review"]["median_rounds"] == 3  # not 3.0


def test_the_text_report_states_a_zero_day_bound(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(ledger, [_row("fabrik-review", 600, 4, "a", days_ago=0.5)])
    text = _run(ledger, "--since", "0").stdout
    assert "0 of 1 ledger rows examined (last 0 days)" in text, text


def test_agent_filter_and_cost_sum_per_command(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("fabrik-review", 600, 4, "a", agent="infra", cost_usd=0.01, surface="plan-1"),
            _row("fabrik-review", 600, 4, "b", agent="fleet", cost_usd=0.02, surface="plan-2"),
            _row("fabrik-review", 600, 4, "c", agent="", cost_usd=None, surface=""),
        ],
    )
    out = json.loads(_run(ledger, "--json").stdout)
    assert out["commands"]["fabrik-review"]["cost_usd"] == 0.03
    only = json.loads(_run(ledger, "--json", "--agent", "infra").stdout)
    assert only["examined"] == 1 and only["commands"]["fabrik-review"]["cost_usd"] == 0.01
    assert only["backlog"][0]["agent"] == "infra" and only["backlog"][0]["surface"] == "plan-1"
    text = _run(ledger, "--agent", "fleet").stdout
    assert "[fleet · plan-2]" in text, text


def test_token_columns_are_summed_and_medianed_per_command(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row(
                "fabrik-review",
                600,
                4,
                "a",
                tok_in=100,
                tok_out=1000,
                tok_cache_read=9000,
                tok_cache_create=900,
                tok_msgs=10,
            ),
            _row(
                "fabrik-review",
                600,
                4,
                "b",
                tok_in=300,
                tok_out=3000,
                tok_cache_read=27000,
                tok_cache_create=2700,
                tok_msgs=30,
            ),
            _row(
                "fabrik-review",
                600,
                4,
                "c",
                tok_in=None,
                tok_out=None,
                tok_cache_read=None,
                tok_cache_create=None,
                tok_msgs=0,
            ),
        ],
    )
    out = json.loads(_run(ledger, "--json").stdout)
    c = out["commands"]["fabrik-review"]
    assert c["tok_total"] == 44000 and c["tok_rows"] == 2  # the null row is counted, not zeroed
    assert c["tok_partial_rows"] == 0
    assert c["median_tok"] == 22000 and c["cache_hit"] == 0.9  # cache_read / (in + read + create)
    text = _run(ledger).stdout
    assert "22.0k" in text and "90%" in text, text


def test_a_command_with_no_token_rows_renders_a_dash_not_zero(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row(
                "fabrik-spec",
                100,
                1,
                "x",
                tok_in=None,
                tok_out=None,
                tok_cache_read=None,
                tok_cache_create=None,
                tok_msgs=0,
            )
        ],
    )
    out = json.loads(_run(ledger, "--json").stdout)
    assert out["commands"]["fabrik-spec"]["median_tok"] is None
    assert out["commands"]["fabrik-spec"]["tok_rows"] == 0
    assert "| — (0) | — |" in _run(ledger).stdout


def test_an_unreadable_ledger_is_an_empty_report_not_a_crash(tmp_path: Path) -> None:
    import os

    ledger = tmp_path / "command-feedback.jsonl"
    _write(ledger, [_row("fabrik-review", 600, 4, "a")])
    ledger.chmod(0)
    try:
        if os.access(ledger, os.R_OK):  # root can always read — nothing to prove here
            return
        r = _run(ledger, "--json")
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["total_rows"] == 0
    finally:
        ledger.chmod(0o600)


def test_an_empty_agent_filter_declares_its_bound_and_handoff_has_its_own_cell(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("c1", 60, 1, "a", agent="infra"),
            _row("c1", 60, 1, "b", agent="", state="handoff"),
            _row("c1", 60, 1, "c", agent="", state="blocked"),
        ],
    )
    text = _run(ledger, "--agent", "").stdout
    assert "2 of 3 ledger rows examined" in text and "(unattributed)" in text, text
    full = _run(ledger).stdout
    assert "| done/blocked/handoff |" in full and "| 1/1/1 |" in full, full


def test_models_are_aggregated_and_the_population_is_declared(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("c1", 60, 1, "a", models=["claude-a"]),
            _row("c1", 60, 1, "b", models=["claude-b", "claude-a"]),
        ],
    )
    out = json.loads(_run(ledger, "--json").stdout)
    assert out["commands"]["c1"]["models"] == ["claude-a", "claude-b"]
    text = _run(ledger).stdout
    assert "claude-a, claude-b" in text and "coroner" in text and "nested" in text, text


def test_a_command_with_no_cost_rows_renders_a_dash_not_zero(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(ledger, [_row("fabrik-spec", 100, 1, "x", cost_usd=None)])
    text = _run(ledger).stdout
    assert "| — (0) | — (0) | — |" in text, text  # pool $, median tokens, cache hit


def test_the_default_ledger_is_the_path_the_close_writes(tmp_path: Path, monkeypatch) -> None:
    import importlib

    sys.path.insert(0, str(ROOT / "scripts"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "state" / "command-runs"))
    import command_feedback_report as rep  # noqa: PLC0415
    import command_run as cr  # noqa: PLC0415

    importlib.reload(rep)
    assert rep._default_ledger() == cr._feedback_ledger_path()


def test_booleans_are_not_numbers_in_the_report_helpers() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_feedback_report import _cost, _tok_total  # noqa: PLC0415

    assert _cost({"cost_usd": True}) is None
    assert (
        _tok_total({"tok_in": True, "tok_out": 1, "tok_cache_read": 1, "tok_cache_create": 1})
        is None
    )


def test_a_repeated_item_lists_every_surface_it_was_raised_on(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    _write(
        ledger,
        [
            _row("c1", 60, 1, "same text", agent="infra", surface="plan-1"),
            _row("c1", 60, 1, "same text", agent="fleet", surface="spec-2"),
        ],
    )
    out = json.loads(_run(ledger, "--json").stdout)
    item = out["backlog"][0]
    assert (
        item["count"] == 2
        and item["agent"] == "infra,fleet"
        and item["surface"] == "plan-1, spec-2"
    )
    assert "[infra,fleet · plan-1, spec-2]" in _run(ledger).stdout


def test_is_none_tokenises_on_any_whitespace() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_feedback_report import _is_none  # noqa: PLC0415

    assert _is_none("none\textra") and _is_none("none — x") and not _is_none("nonetheless")


def test_k_rolls_over_to_millions_at_the_rounded_boundary() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_feedback_report import _k  # noqa: PLC0415

    assert (
        _k(999_999) == "1.0M"
        and _k(999_499) == "999.5k"
        and _k(999.4) == "999"
        and _k(1000) == "1.0k"
    )


def test_a_whitespace_only_value_is_none() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from command_feedback_report import _is_none  # noqa: PLC0415

    assert _is_none("   ") and _is_none("\t\n") and _is_none("") and not _is_none(" x ")


def test_a_non_finite_cost_in_an_old_row_is_not_summed(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    ledger.write_text(
        json.dumps(_row("c1", 60, 1, "a", cost_usd=0.01))
        + "\n"
        + '{"ts": 1, "sid": "s", "repo": "/opt/x", "command": "c1", "state": "done", "wall_s": 1, "rounds": 1, "findings": [], "phases": 1, "confusion": "none", "waste": "none", "change": "b", "filed": "none — x", "cost_usd": Infinity}\n',
        encoding="utf-8",
    )
    out = json.loads(_run(ledger, "--json").stdout)
    assert out["commands"]["c1"]["cost_usd"] == 0.01 and out["commands"]["c1"]["cost_rows"] == 1
