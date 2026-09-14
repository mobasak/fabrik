"""Tests for scripts/command_feedback_report.py — the per-command optimisation report over the
fleet-wide close-out ledger (`~/.claude/state/command-feedback.jsonl`)."""

from __future__ import annotations

import ast
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

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
    assert c["seat_total"] == 0 and c["seat_rows"] == 0 and c["seats_seen"] == 0  # no seat fields
    assert (
        c["seats_seen_rows"] == 0 and "(0 · —)" in _run(ledger).stdout
    )  # a zero over 0 rows is "—"
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


def test_non_finite_or_oversized_numbers_in_old_rows_never_crash_the_report(tmp_path: Path) -> None:
    ledger = tmp_path / "command-feedback.jsonl"
    good = json.dumps(
        _row(
            "c1",
            60,
            1,
            "a",
            cost_usd=0.01,
            tok_in=10,
            tok_out=1,
            tok_cache_read=0,
            tok_cache_create=0,
            tok_msgs=1,
        )
    )
    inf_tok = '{"ts": 1, "sid": "s", "repo": "/opt/x", "command": "c1", "state": "done", "wall_s": 1, "rounds": 1, "findings": [], "phases": 1, "confusion": "none", "waste": "none", "change": "b", "filed": "none — x", "cost_usd": 0.3, "tok_in": Infinity, "tok_out": 1, "tok_cache_read": 0, "tok_cache_create": 0, "tok_msgs": 1}'
    huge_cost = (
        '{"ts": 1, "sid": "s", "repo": "/opt/x", "command": "c1", "state": "done", "wall_s": 1, "rounds": 1, "findings": [], "phases": 1, "confusion": "none", "waste": "none", "change": "c", "filed": "none — x", "cost_usd": 1'
        + "0" * 320
        + "}"
    )
    ledger.write_text("\n".join([good, inf_tok, huge_cost]) + "\n", encoding="utf-8")
    r = _run(ledger, "--json")
    assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)["commands"]["c1"]
    assert c["runs"] == 3 and c["tok_rows"] == 1 and c["tok_total"] == 11
    assert (
        c["cost_rows"] == 2 and c["cost_usd"] == 0.31
    )  # the inf-token row's finite cost still counts


def test_malformed_wall_rounds_ts_models_in_old_rows_never_crash_the_report(tmp_path: Path) -> None:
    """Review pass 22: the pass-21 guard covered cost_usd/tok_* only — the sibling numeric reads
    (`wall_s`, `rounds`, the `--since` `ts` filter) and the `models` iteration still crashed the
    WHOLE report on one bad row in the shared, append-only ledger. A malformed value reads as
    'no datum' (0 / not a list), never a traceback, and the JSON stays valid (no Infinity)."""
    ledger = tmp_path / "command-feedback.jsonl"
    now = time.time()
    good = json.dumps(_row("c1", 60, 1, "a", cost_usd=0.01))

    def bad(**fields: str) -> str:
        base = {
            "ts": now,
            "sid": "s",
            "repo": "/opt/x",
            "command": "c1",
            "state": "done",
            "wall_s": 60,
            "rounds": 1,
            "findings": [],
            "phases": 1,
            "confusion": "none",
            "waste": "none",
            "change": "b",
            "filed": "none — x",
            "models": [],
        }
        text = json.dumps(base)
        for k, raw in fields.items():  # raw JSON tokens json.dumps cannot emit (NaN, 400 digits)
            text = text.replace(json.dumps({k: base[k]})[1:-1], f'"{k}": {raw}')
        return text

    rows = [
        good,
        bad(wall_s='"x"'),
        bad(wall_s="[1]"),
        bad(wall_s="9" * 400),
        bad(wall_s="1e400"),
        bad(rounds="NaN"),
        bad(rounds="Infinity"),
        bad(rounds='"x"'),
        bad(ts='"x"'),
        bad(ts="[1]"),
        bad(ts="9" * 400),
        bad(models="true"),
        bad(models="NaN"),
        bad(models='"abc"'),
    ]
    ledger.write_text("\n".join(rows) + "\n", encoding="utf-8")
    for args in (("--json",), ("--json", "--since", "30"), ()):
        r = _run(ledger, *args)
        assert r.returncode == 0, (args, r.stderr[-400:])
        assert "Infinity" not in r.stdout and "NaN" not in r.stdout, args
    c = json.loads(_run(ledger, "--json").stdout)["commands"]["c1"]
    assert c["runs"] == len(rows) and c["models"] == []
    # a malformed wall/rounds is NO datum: dropped from the medians and disclosed as a row count,
    # never a phantom 0 that drags the median (pass 23: 13 bad rows would have shown "0 min")
    assert c["median_wall_min"] == 1.0 and c["max_wall_min"] == 1.0 and c["median_rounds"] == 1
    assert c["wall_rows"] == len(rows) - 4 and c["rounds_rows"] == len(rows) - 3
    since = json.loads(_run(ledger, "--json", "--since", "30").stdout)
    assert since["examined"] == len(rows) - 3  # the three bad-ts rows fall outside any window


def test_a_malformed_wall_is_no_datum_never_a_phantom_zero_in_the_median(tmp_path: Path) -> None:
    """Pass 23 (seat B): one real 10-minute run + one row whose `wall_s` is a string must report a
    10-minute median over ONE timed row — a phantom 0 would print "5.0 min" for 2 runs, a real
    number silently wrong by 2x with no denominator."""
    ledger = tmp_path / "command-feedback.jsonl"
    good = json.dumps(_row("c1", 600, 3, "a"))
    corrupt = json.dumps(_row("c1", 1, 1, "b")).replace('"wall_s": 1', '"wall_s": "corrupt"')
    corrupt = corrupt.replace('"rounds": 1', '"rounds": [1]')
    assert '"wall_s": "corrupt"' in corrupt and '"rounds": [1]' in corrupt
    ledger.write_text(good + "\n" + corrupt + "\n", encoding="utf-8")
    r = _run(ledger, "--json")
    assert r.returncode == 0, r.stderr[-400:]
    c = json.loads(r.stdout)["commands"]["c1"]
    assert c["runs"] == 2 and c["median_wall_min"] == 10.0 and c["wall_rows"] == 1
    assert c["median_rounds"] == 3 and c["rounds_rows"] == 1
    assert "| 10.0 min (1) |" in _run(ledger).stdout and "| 3 (1) |" in _run(ledger).stdout


def test_no_timed_row_renders_a_dash_never_a_zero_minute_run(tmp_path: Path) -> None:
    """Pass 24 (seat B): a command whose EVERY row has a malformed wall/rounds has no timing
    datum — the median AND max cells print `—` with the `(0)` denominator, the way `pool $`
    already does, never a `0.0 min` that reads like a real zero-minute run."""
    ledger = tmp_path / "command-feedback.jsonl"
    row = json.dumps(_row("c1", 1, 1, "a")).replace('"wall_s": 1', '"wall_s": "x"')
    row = row.replace('"rounds": 1', '"rounds": "y"')
    assert '"wall_s": "x"' in row and '"rounds": "y"' in row
    ledger.write_text(row + "\n", encoding="utf-8")
    text = _run(ledger).stdout
    assert "| — (0) | — | — (0) |" in text, text
    assert "0.0 min" not in text and "| 0 (0) |" not in text
    c = json.loads(_run(ledger, "--json").stdout)["commands"]["c1"]
    assert c["wall_rows"] == 0 and c["median_wall_min"] is None and c["max_wall_min"] is None
    assert c["rounds_rows"] == 0 and c["median_rounds"] is None


def test_seat_tokens_are_rolled_up_beside_the_orchestrators_never_inside(tmp_path: Path) -> None:
    """D-192: 20M seat tokens beside 160 orchestrator tokens were invisible to every rollup here.
    The four seat fields come from the seats' own transcripts; a row without any is counted, not
    zeroed; a malformed seat field nulls that row's seat sum; `tok_total` stays the orchestrator's."""
    ledger = tmp_path / "ledger.jsonl"
    _write(
        ledger,
        [
            _row(
                "fabrik-review",
                100,
                1,
                "a",
                tok_in=100,
                tok_out=60,
                tok_cache_read=0,
                tok_cache_create=0,
                tok_msgs=1,
                tok_seat_in=10,
                tok_seat_out=2_000_000,
                tok_seat_cache_read=18_000_000,
                tok_seat_cache_create=0,
                seats_seen=3,
            ),
            _row(
                "fabrik-review",
                200,
                1,
                "b",
                tok_in=1,
                tok_out=1,
                tok_cache_read=0,
                tok_cache_create=0,
            ),
            _row("fabrik-review", 300, 1, "c", tok_seat_in="x", seats_seen=1),
            _row("fabrik-review", 400, 1, "d", seats_seen="bad"),  # never takes the report down
            _row("fabrik-review", 500, 1, "e", seats_seen=10, seats_declared=5, seats_partial=True),
            _row("fabrik-review", 600, 1, "f", seats_skipped=2),  # oversize seat files, named
        ],
    )
    out = json.loads(_run(ledger, "--json").stdout)
    c = out["commands"]["fabrik-review"]
    assert c["tok_total"] == 162 and c["seat_total"] == 20_000_010 and c["seat_rows"] == 1
    assert c["seats_seen"] == 14 and c["seats_skipped"] == 2 and c["seats_seen_rows"] == 3
    assert c["seats_partial_rows"] == 1 and c["seats_mismatch_rows"] == 1
    text = _run(ledger).stdout
    assert "seat tokens (rows · seats)" in text and "(1 · 14 · 2 skipped)" in text
    # the lower-bound rows reach the TEXT report, not only --json (round-7 Opus finding)
    assert (
        "⚠ LOWER BOUNDS" in text
        and "/fabrik-review: 1 declared/seen seat mismatch, 1 seat(s) still running" in text
    )


# --- Phase B: tokens per round behind the mass rule (plan rows B1–B9) --------------------------


def _cells(line: str) -> list[str]:
    """The row's cells, split on UNESCAPED pipes — a `\\|` inside a cell is content, not a boundary."""
    return re.split(r"(?<!\\)\|", line)[1:-1]


def _tok(cmd: str, rounds: int, tin: int, tout: int, **kw) -> dict:
    """A ledger row carrying a token pair and a round count — the two sides of tok/round."""
    return _row(cmd, 60.0, rounds, "none", tok_in=tin, tok_out=tout, **kw)


def test_mass_rule_clause1_precedes_the_ratio(tmp_path: Path) -> None:
    """B1 — a command whose TOTAL token mass is 0 publishes nothing and says "zero token mass".
    Clause 1 must run BEFORE the ratio: evaluating a ratio over a zero denominator is the division
    the rule exists to prevent, and a 0/0 would render as a confident 0.0 tokens per round."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("zero", 3, 0, 0), _tok("zero", 2, 0, 0)])
    out = _run(ledger, "--json").stdout
    cmd = json.loads(out)["commands"]["zero"]
    assert cmd["tok_per_round"] is None
    assert cmd["tok_per_round_reason"] == "zero token mass"
    assert cmd["mass_ratio"] is None, "no ratio is evaluated at all"


def test_mass_rule_silences_below_two_thirds(tmp_path: Path) -> None:
    """B2 — when the rows carrying BOTH sides hold less than ⅔ of the command's token mass, the
    figure would describe a minority of the work: it renders `—` with the measured ratio."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger, [_tok("thin", 4, 100, 100), _row("thin", 60.0, 0, "none", tok_in=800, tok_out=800)]
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["thin"]
    assert cmd["tok_per_round"] is None
    assert cmd["mass_ratio"] == pytest.approx(200 / 1800, abs=1e-6)
    assert "mass ratio" in cmd["tok_per_round_reason"]
    assert "0.1111" in cmd["tok_per_round_reason"], cmd["tok_per_round_reason"]


def test_tok_per_round_excludes_zero_round_rows_from_both_sides(tmp_path: Path) -> None:
    """B3 — the quantity is Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying BOTH a finite token
    pair and rounds > 0. A row with tokens and `rounds == 0` and a row with rounds and no tokens
    each contribute to NEITHER side; the three row counts are published beside the figure."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _tok("mix", 2, 1000, 1000),  # both sides
            _tok("mix", 3, 500, 500),  # both sides
            _row("mix", 60.0, 0, "none", tok_in=10, tok_out=10),  # tokens, no rounds
            _row("mix", 60.0, 4, "none"),  # rounds, no tokens
        ],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["mix"]
    assert cmd["tok_per_round"] == pytest.approx(3000 / 5)
    assert cmd["rows_with_numerator"] == 3, "three rows carry a token pair"
    assert cmd["rows_with_denominator"] == 3, "three rows carry rounds > 0"
    assert cmd["rows_both"] == 2, "only two carry both — the population the figure is over"
    assert cmd["rows_total"] == 4


def test_tok_per_round_states_its_divisor_and_exclusion(tmp_path: Path) -> None:
    """B4 — a figure whose divisor a reader must guess is a figure they will misread. Both the
    rendered report and `--json` state that the divisor is Σ rounds over the both-sides rows, and
    that cache tokens are excluded (unlike `median_tok`, which is cache-inclusive)."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("c", 2, 100, 100)])
    payload = json.loads(_run(ledger, "--json").stdout)
    conv = payload["conventions"]["tok_per_round"]
    assert "Σ rounds" in conv and "cache excluded" in conv
    median_conv = payload["conventions"]["median_tok"]
    assert "cache-inclusive" in median_conv
    # the population clause too: "over the rows carrying tokens" was FALSE — `_tok_total` needs all
    # four token fields, a narrower set than tok/round's pair, and the two cells disagreed in
    # silence (a row could read "median tokens — (0)" beside a live tok/round figure)
    assert "ALL FOUR" in median_conv, median_conv
    # "a narrower population" was FALSE in both directions — the two sets are incomparable: a row
    # with all four fields and rounds 0 is in this one and not the other, and the reverse holds too
    assert "DIFFERENT" in median_conv and "neither containing the other" in median_conv, median_conv
    assert "narrower" not in median_conv, median_conv
    text = _run(ledger).stdout
    assert "Σ rounds" in text and "cache" in text


def test_every_added_figure_carries_its_row_counts(tmp_path: Path) -> None:
    """B5 — a 0 over 0 rows is "nothing looked at", not an honest zero, so every figure this change
    adds publishes the population it was computed over, in `--json` and in the rendered cell."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("p", 2, 300, 300), _row("p", 60.0, 0, "none")])
    payload = json.loads(_run(ledger, "--json").stdout)
    cmd = payload["commands"]["p"]
    for key in ("rows_with_numerator", "rows_with_denominator", "rows_both", "rows_total"):
        assert isinstance(cmd[key], int), key
    text = _run(ledger).stdout
    assert "num/den/both" in text, "the column header names the three counts"
    assert "(1/1/1)" in text, text


def test_cost_usd_is_absent_from_every_derivation(tmp_path: Path) -> None:
    """B6 — `cost_usd` derives nothing (spec § Q2): it is a reported total, never an input to a
    figure. A row whose cost is absurd must not move tokens per round by one unit."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("k", 2, 400, 400, cost_usd=999999.0), _tok("k", 2, 400, 400)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["k"]
    assert cmd["tok_per_round"] == pytest.approx(1600 / 4)
    assert cmd["mass_ratio"] == pytest.approx(1.0)


def test_tok_per_round_excludes_cache_and_the_report_says_so(tmp_path: Path) -> None:
    """B7 — the shipped `median_tok` sums all four token fields; tokens per round sums only the two
    that are real input and output. Two conventions in one report must both be stated."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("cc", 2, 100, 100, tok_cache_read=9000, tok_cache_create=1000)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["cc"]
    assert cmd["tok_per_round"] == pytest.approx(200 / 2), "cache never enters the numerator"
    assert cmd["median_tok"] == 10200, "median_tok stays cache-inclusive"
    text = _run(ledger).stdout
    assert "cache excluded" in text and "cache-inclusive" in text


def test_two_thirds_exactly_publishes(tmp_path: Path) -> None:
    """B8 — the rule is ≥ ⅔, not > ⅔: a command sitting exactly on the boundary publishes."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [_tok("edge", 2, 1000, 1000), _row("edge", 60.0, 0, "none", tok_in=500, tok_out=500)],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["edge"]
    assert cmd["mass_ratio"] == pytest.approx(2 / 3)
    assert cmd["tok_per_round"] == pytest.approx(2000 / 2), "exactly two thirds publishes"


def test_the_rendered_header_separator_and_rows_have_thirteen_cells(tmp_path: Path) -> None:
    """B9 — a markdown table whose separator has fewer cells than its header renders as prose. The
    count is pinned at 13, not merely "equal", so this grader is RED on the shipped 12-column table."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("t", 2, 100, 100), _tok("u", 1, 50, 50)])
    rows = [ln for ln in _run(ledger).stdout.split("\n") if ln.startswith("|")]
    assert len(rows) >= 4, rows
    for line in rows:
        assert len(_cells(line)) == 13, (len(_cells(line)), line)


# --- Phase B round 2: the states the first pass could not express -----------------------------


def test_a_negative_token_count_is_corrupt_data_never_mass(tmp_path: Path) -> None:
    """Signed sums make the mass ratio UNBOUNDED: one corrupt row pushed it to 2.0 and the figure
    passed the very rule that exists to silence it, or published a negative tok/round outright."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("neg", 2, 100, 0), _row("neg", 60.0, 0, "none", tok_in=-50, tok_out=0)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["neg"]
    assert cmd["mass_ratio"] is None or cmd["mass_ratio"] <= 1.0, cmd
    assert cmd["rows_with_numerator"] == 1, "the negative row carries no measurable tokens"

    _write(ledger, [_tok("neg2", 2, -1000, -1000)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["neg2"]
    assert cmd["tok_per_round"] is None, "a negative tok/round is never published"


def test_a_zero_token_row_never_dilutes_the_divisor(tmp_path: Path) -> None:
    """The one failure the mass rule exists to prevent, passing it at PERFECT coverage: a row that
    spent nothing carries no work to attribute, but its rounds used to enter the divisor — 2000
    tokens over 2 real rounds published as 200/round, a 5x understatement, at mass_ratio 1.0."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("dilute", 2, 1000, 1000), _tok("dilute", 8, 0, 0)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["dilute"]
    assert cmd["tok_per_round"] == pytest.approx(2000 / 2), "the honest figure, not 2000/10"
    assert cmd["rows_both"] == 1, "the zero-token row is in neither side"


def test_a_half_token_pair_contributes_to_neither_side(tmp_path: Path) -> None:
    """Spec § Q2: the sums run over the rows carrying BOTH a token pair and rounds > 0, so a row
    with `tok_in` and no `tok_out` is not a token-carrying row — counting half a pair as a whole
    one inflated the numerator and over-reported the population it was computed over."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("half", 60.0, 2, "none", tok_in=1000), _tok("half", 2, 1000, 1000)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["half"]
    assert cmd["rows_with_numerator"] == 1, "only the complete pair counts"
    assert cmd["tok_per_round"] == pytest.approx(2000 / 2)


def test_a_float_round_count_is_not_a_divisor(tmp_path: Path) -> None:
    """`int()` TRUNCATES: a `rounds` of 2.7 overstated the figure by 26%, and a 0.9 left its tokens
    inside the mass and outside the numerator — silencing the command for a reason nobody can see."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger, [_tok("fr", 2, 500, 500), _row("fr", 60.0, 2.7, "none", tok_in=500, tok_out=500)]
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["fr"]
    assert cmd["rows_with_denominator"] == 1, "2.7 is not a round count"
    # its 1000 tokens are real mass the figure cannot attribute, so the command is SILENCED rather
    # than published at a truncated divisor — and the printed ratio is the reason, visible at last
    assert cmd["tok_per_round"] is None
    assert cmd["mass_ratio"] == pytest.approx(0.5)
    assert "mass ratio" in cmd["tok_per_round_reason"]


def test_nothing_measured_is_not_a_measurement_of_zero(tmp_path: Path) -> None:
    """ "Zero token mass" asserts a measurement; a command whose rows carry no token fields at all
    measured nothing. The file enforces this on its own figures ("a 0 over 0 rows is nothing looked
    at, not an honest zero") and the reason string now honours it."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("dry", 60.0, 5, "none"), _row("dry", 60.0, 3, "none")])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["dry"]
    assert cmd["tok_per_round_reason"] == "no token-carrying row"

    _write(ledger, [_tok("real", 5, 0, 0)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["real"]
    assert cmd["tok_per_round_reason"] == "zero token mass", "a measured zero still says so"


def test_the_row_counts_name_the_rows_they_actually_counted(tmp_path: Path) -> None:
    """`num`, `den` and `both` are three SEPARATE populations. A fixture where the token-carrying
    and round-carrying sets merely have the same SIZE cannot tell a correct count from one that
    silently reports the other set — so this one makes their cardinalities differ."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _tok("prov", 2, 500, 500),  # both
            _row("prov", 60.0, 0, "none", tok_in=10, tok_out=10),  # tokens only
            _row("prov", 60.0, 0, "none", tok_in=20, tok_out=20),  # tokens only
            _row("prov", 60.0, 7, "none"),  # rounds only
        ],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["prov"]
    assert cmd["rows_with_numerator"] == 3, "three rows carry a token pair"
    assert cmd["rows_with_denominator"] == 2, "two carry a whole rounds > 0"
    assert cmd["rows_both"] == 1, "one carries both"


def test_a_malformed_token_value_is_never_summed(tmp_path: Path) -> None:
    """The guard `_tok_total` carries and `_io_total` needs too: a string, a bool or a NaN in a
    token field must null the row's contribution, never be coerced into the mass."""
    ledger = tmp_path / "l.jsonl"
    rows = [_tok("bad", 2, 1000, 1000)]
    for junk in ("12", True, float("nan"), [5], {"a": 1}):
        rows.append(_row("bad", 60.0, 2, "none", tok_in=junk, tok_out=5))
    _write(ledger, rows)
    proc = _run(ledger, "--json")
    assert proc.returncode == 0, proc.stderr
    cmd = json.loads(proc.stdout)["commands"]["bad"]
    assert cmd["rows_with_numerator"] == 1, "only the well-formed row carries tokens"
    assert cmd["tok_per_round"] == pytest.approx(2000 / 2)


def test_a_pipe_in_a_command_or_model_name_cannot_break_the_table(tmp_path: Path) -> None:
    """A literal `|` inside a cell is an extra column boundary — the exact failure the 13-cell
    grader exists to catch, and the one shape its fixtures never built."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("piped|name", 2, 100, 100, models=["mod|a", "mod|b"])])
    rows = [ln for ln in _run(ledger).stdout.split("\n") if ln.startswith("|")]
    assert rows, "the table rendered"
    for line in rows:
        assert len(_cells(line)) == 13, (len(_cells(line)), line)
    body = [ln for ln in rows if ln.startswith("| /")]
    assert body and "piped" in body[0] and "\\|" in body[0], body


def test_the_conventions_state_the_rule_the_code_actually_runs(tmp_path: Path) -> None:
    """The published formula must compute the published number. The first draft said the figure ran
    over "the rows carrying both a token pair and a whole rounds > 0" — a reader applying that to a
    command with a zero-token row got 200 where the table printed 1000, because the code also
    requires the pair to be POSITIVE. A convention that yields a different answer is worse than none.
    """
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("conv", 2, 1000, 1000), _tok("conv", 8, 0, 0)])
    payload = json.loads(_run(ledger, "--json").stdout)
    cmd = payload["commands"]["conv"]
    assert cmd["tok_per_round"] == pytest.approx(1000.0)
    for text in (payload["conventions"]["tok_per_round"], _run(ledger).stdout):
        assert "POSITIVE token pair" in text, text
    counts = payload["conventions"]["row_counts"]
    assert "both = " in counts and "POSITIVE" in counts, counts


def test_the_ratio_is_claimed_only_where_it_exists(tmp_path: Path) -> None:
    """`mass_ratio` is null in the zero-mass branch — there is nothing to take a ratio of — so the
    prose may not promise it "either way"."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("zm", 3, 0, 0)])
    payload = json.loads(_run(ledger, "--json").stdout)
    assert payload["commands"]["zm"]["mass_ratio"] is None
    assert "either way" not in _run(ledger).stdout
    assert "nothing to take a ratio of" in payload["conventions"]["mass_rule"]


def test_the_tok_per_round_header_names_only_what_the_cell_shows(tmp_path: Path) -> None:
    """The header advertised `q/T` and the cell never rendered one, so a reader parsing it the way
    they parse `(num/den/both)` looked for a slash-pair that does not exist. The 13-cell grader is
    blind to the label, so the header needs its own."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("h", 2, 100, 100)])
    header = next(ln for ln in _run(ledger).stdout.split("\n") if ln.startswith("| command |"))
    assert "tok/round (num/den/both)" in header, header
    assert "q/T" not in header, header


def test_a_negative_token_count_never_reaches_median_tokens_or_cache_hit(tmp_path: Path) -> None:
    """The sign guard lived in `_io_total` alone, so `_tok_total` still summed negatives: cache hit
    divided a negative by a negative and printed a plausible 27% from garbage."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row(
                "neg",
                60.0,
                2,
                "none",
                tok_in=-7000,
                tok_out=1700,
                tok_cache_read=-2000,
                tok_cache_create=0,
            )
        ],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["neg"]
    assert cmd["tok_rows"] == 0, "a negative row carries no measurable tokens"
    assert cmd["median_tok"] is None
    assert cmd["cache_hit"] is None, "no percentage is derived from a negative denominator"


def test_a_float_round_count_is_not_truncated_into_the_median(tmp_path: Path) -> None:
    """`int()` in the median's comprehension was the unswept mirror of the divisor's truncation."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("fm", 60.0, 2.7, "none"), _row("fm", 60.0, 2.9, "none")])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["fm"]
    assert cmd["median_rounds"] == pytest.approx(2.8), "not 2 — the truncation is gone"


def test_a_backslash_before_a_pipe_cannot_open_a_column(tmp_path: Path) -> None:
    """Escaping the pipe without escaping the backslash first turns source `a\\|b` into `a\\\\|b`,
    which GFM reads as a literal backslash followed by a LIVE column boundary — reopening the very
    hole the escape closes."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("back", 2, 100, 100, models=["m\\|odel"])])
    rows = [ln for ln in _run(ledger).stdout.split("\n") if ln.startswith("|")]
    for line in rows:
        assert len(_cells(line)) == 13, (len(_cells(line)), line)
    body = next(ln for ln in rows if ln.startswith("| /back"))
    assert "\\\\\\|" in body, body


def test_one_negative_component_never_reaches_cache_hit_or_seat_tokens(tmp_path: Path) -> None:
    """The sign guard first landed on the SUM of four fields, but `cache_hit` recombines the same
    fields per-component behind that whole-row gate: one negative field with a non-negative total
    slipped through and printed -25% and 250% cache hits. `_seat_total` had no sign rule at all,
    so -10000 and +10000 rendered "0 (2 · —)" — two rows measured at zero, which is not true."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row(
                "mix",
                60.0,
                2,
                "none",
                tok_in=10000,
                tok_out=0,
                tok_cache_read=-2000,
                tok_cache_create=0,
            )
        ],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["mix"]
    assert cmd["cache_hit"] is None, "no percentage from a negative component"
    assert cmd["tok_rows"] == 0

    _write(
        ledger,
        [_tok("st", 2, 10, 10, tok_seat_in=-10000), _tok("st", 2, 10, 10, tok_seat_in=10000)],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["st"]
    assert cmd["seat_rows"] == 1, "only the trustworthy row carries a seat total"
    assert cmd["seat_total"] == 10000


def test_the_conventions_never_claim_an_ordering_the_counts_do_not_have(tmp_path: Path) -> None:
    """The rendered line asserted the third count is "narrower than the overlap of the first two".
    On the live ledger the two are EQUAL for every command, so the sentence pointed a reader at the
    wrong cause of the gap they can see — the whole-rounds requirement, not the positive-pair one."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("ord", 2, 100, 100), _row("ord", 60.0, 0, "none", tok_in=5, tok_out=5)])
    text = _run(ledger).stdout
    assert "narrower than the overlap" not in text, text
    assert "needs BOTH of the first two AND a positive pair" in text, text


def test_a_negative_value_never_drags_a_published_aggregate(tmp_path: Path) -> None:
    """The sign rule `_tok_total`, `_io_total` and `_seat_total` carry, swept to the four siblings
    that publish a human-facing number from the same corrupt-row threat model. One bad row used to
    print a median wall of -45 minutes, a median rounds of -3, a seats_seen of -95 and a pool spend
    reduced by a refund the writer never emits — each a number a reader cannot read as wrong."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("neg", 600.0, 3, "none", seats_seen=5, cost_usd=10.0),
            _row("neg", -6000.0, -9, "none", seats_seen=-100, cost_usd=-500.0),
        ],
    )
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["neg"]
    assert cmd["median_wall_min"] == pytest.approx(10.0), "the negative wall is not a measurement"
    assert cmd["wall_rows"] == 1
    assert cmd["median_rounds"] == 3
    assert cmd["rounds_rows"] == 1
    assert cmd["seats_seen"] == 5, "a tally never goes negative"
    assert cmd["seats_seen_rows"] == 1
    assert cmd["cost_usd"] == pytest.approx(10.0), "a negative amount is corrupt, not a refund"
    assert cmd["cost_rows"] == 1


def test_one_oversized_integer_never_takes_the_whole_report_down(tmp_path: Path) -> None:
    """`float()` itself overflows on a 400-digit int. Every numeric helper here carries an
    `OverflowError` catch except `_is_count`, which did not — so one such row in `seats_seen`
    raised out of `build` and the report exited 1 with no output at all, against the invariant its
    own call site states ("one malformed row must never take the whole report down")."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("big", 60.0, 2, "none", seats_seen=5),
            _row("big", 60.0, 2, "none", seats_seen=int("9" * 400)),
        ],
    )
    proc = _run(ledger, "--json")
    assert proc.returncode == 0, proc.stderr
    cmd = json.loads(proc.stdout)["commands"]["big"]
    assert cmd["seats_seen"] == 5, "the readable row still counts"
    assert cmd["seats_seen_rows"] == 1
    assert _run(ledger).returncode == 0, "the rendered report survives it too"


def test_a_negative_component_never_publishes_a_tokens_per_round(tmp_path: Path) -> None:
    """`_io_total` guarded the SUM, so -1000000 and +1000010 netted to a plausible +10 and published
    a confident figure over a corrupt pair at mass_ratio 1.0 — the last unswept site of the rule
    `_tok_total` and `_seat_total` already applied per component."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("comp", 2, -1000000, 1000010), _tok("comp", 2, 100, 100)])
    cmd = json.loads(_run(ledger, "--json").stdout)["commands"]["comp"]
    assert cmd["rows_with_numerator"] == 1, "the corrupt pair carries no tokens"
    assert cmd["tok_per_round"] == pytest.approx(200 / 2)
    assert cmd["mass_ratio"] == pytest.approx(1.0), "over the one row that is readable"


def test_an_oversized_seat_token_never_takes_the_whole_report_down(tmp_path: Path) -> None:
    """`_seat_total` was the LAST of the six numeric helpers here without the `OverflowError`
    catch — round 2 fixed the location (`_is_count`) and not the class, so one 400-digit integer in
    a seat field still exited 1 with no output. Six of six now carry it."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("seat", 60.0, 2, "none", tok_seat_in=2000, tok_seat_out=1000),
            _row("seat", 60.0, 2, "none", tok_seat_in=int("9" * 400)),
        ],
    )
    proc = _run(ledger, "--json")
    assert proc.returncode == 0, proc.stderr
    cmd = json.loads(proc.stdout)["commands"]["seat"]
    assert cmd["seat_total"] == 3000, "the readable row still sums"
    assert cmd["seat_rows"] == 1
    assert _run(ledger).returncode == 0, "the rendered report survives it too"


def test_a_token_sum_past_the_float_maximum_never_takes_the_report_down(tmp_path: Path) -> None:
    """Every helper guards its COMPONENTS; they return exact-int SUMS. Four fields each just under
    the float maximum sum past it, and both `statistics.median` and the final division then fail —
    rc 1, no output, in text and `--json` alike. A count of guarded call sites was never a proof of
    the guarded property, which is how three rounds read six-of-six as the class closed."""
    big = 10**308
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row(
                "huge",
                60.0,
                2,
                "none",
                tok_in=big,
                tok_out=big,
                tok_cache_read=big,
                tok_cache_create=big,
            ),
            _tok("huge", 2, 100, 100),
        ],
    )
    proc = _run(ledger, "--json")
    assert proc.returncode == 0, proc.stderr
    cmd = json.loads(proc.stdout)["commands"]["huge"]
    assert cmd["median_tok"] is None, "a sum it cannot reduce is null, never a crash"
    assert _run(ledger).returncode == 0, "the rendered report survives it too"

    # rounds=1: the divisor cannot bring 2e308 back inside the float range, where rounds=2 could
    _write(ledger, [_row("one", 60.0, 1, "none", tok_in=big, tok_out=big)])
    proc = _run(ledger, "--json")
    assert proc.returncode == 0, proc.stderr
    cmd = json.loads(proc.stdout)["commands"]["one"]
    assert cmd["tok_per_round"] is None
    assert cmd["tok_per_round_reason"] == "token mass too large to divide"


def test_every_published_figure_is_finite_or_null(tmp_path: Path) -> None:
    """The PROPERTY, asserted once over every figure rather than per site.

    Four rounds guarded this file site by site and each declared the class closed; a fifth found a
    third crashing caller and two silent `float -> inf` paths, because float addition overflows to
    infinity WITHOUT raising, so no `OverflowError` guard can see it. A per-site guard closes only
    the sites someone enumerated. This grader takes a ledger built to break every numeric path at
    once and asserts what a reader actually needs: the report renders, the JSON is valid, and every
    number in it is finite.
    """
    big, huge = 10**308, 17 * 10**307
    ledger = tmp_path / "l.jsonl"
    rows = [_tok("ok", 2, 100, 100)]
    for _ in range(300):  # a seat-token sum past the float maximum — the `_k` crash
        rows.append(_row("ok", 1.0, 1, "none", tok_seat_in=huge, tok_seat_out=huge))
    rows += [
        _row("ok", 1.7e308, 2, "none", cost_usd=1e308),  # float addition -> inf, no exception
        _row("ok", 1.0, 2, "none", cost_usd=1e308),
        _row(
            "ok", 1.0, 2, "none", tok_in=big, tok_out=big, tok_cache_read=big, tok_cache_create=big
        ),
        _row("ok", 1.0, int("9" * 400), "none", seats_seen=int("9" * 400)),
        # finite PER ROW, overflowing only in the sum — the shape that nulls a tally while its row
        # count stays non-zero, so a cell gated on the count alone prints the nulled value verbatim
        _row("ok", 1.0, 2, "none", seats_seen=1e308, seats_skipped=1e308),
        _row("ok", 1.0, 2, "none", seats_seen=1e308, seats_skipped=1e308),
    ]
    _write(ledger, rows)

    proc = _run(ledger, "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)  # bare Infinity would not be valid JSON
    assert "Infinity" not in proc.stdout and "NaN" not in proc.stdout, proc.stdout[:400]
    for name, stats in payload["commands"].items():
        for key, value in stats.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            assert math.isfinite(float(value)), f"{name}.{key} = {value!r}"

    rendered = _run(ledger)
    assert rendered.returncode == 0, rendered.stderr
    assert "inf" not in rendered.stdout.split("Conventions:")[0], rendered.stdout[:400]
    for line in (ln for ln in rendered.stdout.split("\n") if ln.startswith("| /")):
        assert len(line) < 400, f"an unrenderable cell widened the table: {len(line)} chars"
        # the READER's half of the property: a nulled figure must read as `—`, never as the string
        # "None" — five cells gated on a sibling row count while the value beside them was nulled
        assert "None" not in line, f"a nulled figure reached the reader verbatim: {line[:200]}"


def test_a_figure_nobody_measured_reads_as_a_dash_not_a_zero(tmp_path: Path) -> None:
    """`sum([]) == 0`, so a gate that tests only the VALUE publishes a confident 0 where nothing was
    measured — the file's own rule, written three times in its comments, is that a 0 over 0 rows is
    "nothing looked at", not an honest zero. Converting the gates to test the value alone regressed
    4 of 14 rows on the live ledger before this grader existed; the gate must test BOTH."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("bare", 2, 100, 100)])  # no seat fields, no cost, no seats_seen
    row = next(ln for ln in _run(ledger).stdout.split("\n") if ln.startswith("| /bare"))
    cells = _cells(row)
    assert cells[7].strip().startswith("—"), f"pool $ over 0 rows: {cells[7]!r}"
    assert cells[10].strip().startswith("—"), f"seat tokens over 0 rows: {cells[10]!r}"
    payload = json.loads(_run(ledger, "--json").stdout)["commands"]["bare"]
    assert payload["seat_rows"] == 0 and payload["cost_rows"] == 0


def test_a_non_finite_since_is_refused_rather_than_silently_emptying(tmp_path: Path) -> None:
    """`float("nan")` parses, then every `>= cutoff` comparison is False: the report silently
    emptied while reporting success, and `NaN` reached the JSON document, which no strict parser
    accepts. The sanitiser is scoped to the per-command figures, so this needed its own guard."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_tok("s", 2, 100, 100)])
    for bad in ("nan", "inf", "-inf"):
        # the `=` form: argparse reads a bare `-inf` as an option flag, not as this flag's value
        proc = _run(ledger, f"--since={bad}")
        assert proc.returncode != 0, f"--since {bad} was accepted: {proc.stdout[:200]}"
        assert "finite number of days" in proc.stderr, proc.stderr[:200]
    ok = _run(ledger, "--since", "7", "--json")
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["since_days"] == 7.0


# ---------------------------------------------------------------------------------------------
# Piece 1 — the axis key: four buckets in a fixed precedence, a mirror-safe `none` read, and the
# derived writer rank. Every grader here was proven red-on-revert against the change that added it.
# ---------------------------------------------------------------------------------------------

FRAGMENT = ROOT / "commands" / "_fragments" / "close-feedback.md"


def _axes(ledger: Path, cmd: str) -> dict:
    r = _run(ledger, "--json")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["commands"][cmd]


def test_an_axis_key_at_the_head_tallies_under_that_axis(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("fabrik-review", 60, 1, "lean: cut the rubric block to the matched rows"),
            _row("fabrik-review", 60, 1, "ACCURATE: the step cites a line that moved"),
            _row("fabrik-review", 60, 1, "waste: the seat polled instead of batching"),
        ],
    )
    c = _axes(ledger, "fabrik-review")
    assert c["axes"] == {"accurate": 1, "lean": 1, "waste": 1}
    assert c["axis_rows"] == 3


def test_a_second_axis_after_a_comma_never_re_keys_the_row(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("c", 60, 1, "lean: cut the digest, accurate: name the flag")])
    assert _axes(ledger, "c")["axes"] == {"lean": 1}


def test_a_value_with_no_key_is_unkeyed_and_counted_never_dropped(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("c", 60, 1, "the step should say which flag to pass"),
            _row("c", 60, 1, "lean shorten step 3 — no colon, so no key"),
        ],
    )
    c = _axes(ledger, "c")
    assert c["axes"] == {"unkeyed": 2} and c["axis_rows"] == 2


def test_a_key_outside_the_seven_is_bad_axis_not_unkeyed(tmp_path: Path) -> None:
    """An attempt that missed is a different instrument reading from no attempt at all."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("c", 60, 1, "speed: the loop polls"), _row("c", 60, 1, "no key here")])
    assert _axes(ledger, "c")["axes"] == {"bad-axis": 1, "unkeyed": 1}


def test_a_pasted_grammar_template_is_placeholder_with_or_without_brackets_or_a_key(
    tmp_path: Path,
) -> None:
    """`command_run.py::_is_placeholder` is a `re.fullmatch` on `<…>`, so an axis key in front of a
    pasted template defeats it at the close. This reader is what still catches it."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("c", 60, 1, "lean: <the ONE concrete edit to this command or a rule>"),
            _row("c", 60, 1, "the ONE concrete edit to this command or a rule that would"),
            _row("c", 60, 1, "foo: <the ONE concrete edit>"),
        ],
    )
    # all three are placeholder — and the third proves the precedence: it is ALSO a bad key
    assert _axes(ledger, "c")["axes"] == {"placeholder": 3}


def test_the_four_buckets_partition_the_non_none_rows(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("c", 60, 1, "lean: real"),
            _row("c", 60, 1, "speed: missed the vocabulary"),
            _row("c", 60, 1, "the ONE concrete edit to this command"),
            _row("c", 60, 1, "plain prose with no key"),
            _row("c", 60, 1, "none"),
            _row("c", 60, 1, "lean: none"),
        ],
    )
    c = _axes(ledger, "c")
    assert sum(c["axes"].values()) == c["axis_rows"] == 4, c["axes"]
    assert c["runs"] == 6 and c["change_none"] == 2  # the two `none` rows are NOT in the tally


def test_change_is_none_strips_the_axis_key_and_leaves_the_shared_helper_alone() -> None:
    """The mirror: `_is_none` gates `change`, `confusion` AND `waste` (`_items`) — teaching it about
    axis keys would silently re-classify a confusion value whose first word is `lean:`."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cfr", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m._change_is_none("lean: none") is True
    assert m._change_is_none("none") is True
    assert m._change_is_none("lean: cut the digest") is False
    # the shared helper is UNTOUCHED — this is the assertion the mirror needs
    assert m._is_none("lean: none") is False
    assert m._is_none("none") is True


def test_a_keyed_none_does_not_over_report_the_queue(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("c", 60, 1, "lean: none"), _row("c", 60, 1, "lean: a real edit")])
    c = _axes(ledger, "c")
    assert c["change_none"] == 1 and c["axis_rows"] == 1 and c["axes"] == {"lean": 1}


def test_an_axis_key_survives_a_value_at_the_ledger_cap(tmp_path: Path) -> None:
    """`command_run.py:1235` caps a stored field at 2000 chars; the key must still read."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("c", 60, 1, "lean: " + "x" * 1994)])
    assert _axes(ledger, "c")["axes"] == {"lean": 1}


def test_a_window_with_no_change_verdict_says_so_instead_of_zeroing_every_axis(
    tmp_path: Path,
) -> None:
    """The canary: a tally over zero rows must not print a confident 0 per axis — the phantom-zero
    class this report has already paid for once."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("c", 60, 1, "none"), _row("c", 60, 1, "none")])
    r = _run(ledger)
    assert r.returncode == 0, r.stderr
    assert "no row in this window carries a change: verdict" in r.stdout
    assert _axes(ledger, "c")["axes"] == {} and _axes(ledger, "c")["axis_rows"] == 0


def test_observer_rank_names_the_top_four_by_io_mean_and_ignores_cache(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    rows = []
    for i, cmd in enumerate(["a", "b", "c", "d", "e", "f"]):
        rows.append(_row(cmd, 60, 1, "lean: x", tok_in=1000 * (6 - i), tok_out=0))
    # a cache-heavy but io-light row must NOT climb: the rank is cache-excluded by construction
    rows.append(_row("f", 60, 1, "lean: x", tok_in=1, tok_out=0, tok_cache_read=10**9))
    _write(ledger, rows)
    r = _run(ledger, "--observer-rank")
    assert r.returncode == 0, r.stderr
    named = [ln.split("\t")[0] for ln in r.stdout.splitlines() if ln.startswith("/")]
    assert named == ["/a", "/b", "/c", "/d"], r.stdout
    assert "4 of 6 command(s) with a token pair" in r.stdout
    assert "n=" in r.stdout


def test_observer_rank_degrades_when_fewer_than_four_commands_qualify(tmp_path: Path) -> None:
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("a", 60, 1, "lean: x", tok_in=10, tok_out=1),
            _row("b", 60, 1, "lean: x", tok_in=5, tok_out=1),
            _row("c", 60, 1, "lean: x"),  # no token pair — does not qualify
        ],
    )
    r = _run(ledger, "--observer-rank")
    assert r.returncode == 0, r.stderr
    assert "2 of 2 command(s) with a token pair (of 3 seen)" in r.stdout
    assert len([ln for ln in r.stdout.splitlines() if ln.startswith("/")]) == 2


def test_observer_rank_says_nothing_is_measurable_rather_than_crashing(tmp_path: Path) -> None:
    """A closing agent that reads this falls through to writing its own line — the fragment's
    escape clause depends on this exiting 0 with a sentence, never on a traceback."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("a", 60, 1, "lean: x"), _row("b", 60, 1, "none")])
    r = _run(ledger, "--observer-rank")
    assert r.returncode == 0, r.stderr
    assert "nothing measurable" in r.stdout and "0 of 2 command(s)" in r.stdout


def test_the_placeholder_phrases_are_pinned_against_the_live_fragment() -> None:
    """The counter-measure rots the moment the fragment is reworded past every phrase this reader
    knows, and nothing else would notice. `command_run.py`'s own list is NOT imported — this file
    imports nothing from it, and that constant belongs to another plan's lock."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cfr", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    # the same collapse the classifier applies, plus the blockquote markers: the fragment prints
    # its grammar inside a `> ` quote that wraps across lines, so a phrase a reader sees as one
    # string is split by a marker no stored value ever carries
    text = " ".join(
        " ".join(
            re.sub(r"^\s*>\s?", "", ln) for ln in FRAGMENT.read_text(encoding="utf-8").splitlines()
        )
        .lower()
        .split()
    )
    missing = [p for p in m._GRAMMAR_PHRASES if p not in text]
    assert not missing, f"phrases no longer in the fragment: {missing}"
    raw = [re.sub(r"^\s*>\s?", "", ln) for ln in FRAGMENT.read_text(encoding="utf-8").splitlines()]
    i = next(k for k, ln in enumerate(raw) if "· change:" in ln)
    change_clause = " ".join(" ".join(raw[i : i + 2]).lower().split())
    assert any(p in change_clause for p in m._GRAMMAR_PHRASES), (
        "the change: clause matches no phrase this reader knows — a pasted template would now "
        "count as a real verdict"
    )
    # the no-import half, asserted on the AST rather than on prose: the module docstring
    # legitimately NAMES command_run.py as the writer of the rows it reads
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in (n.names if isinstance(n, ast.Import) else [None])
        if a is not None or isinstance(n, ast.ImportFrom)
    }
    assert not any("command_run" in name for name in imported), imported


def test_the_seven_axes_are_the_vocabulary_the_fragment_publishes() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("cfr", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    text = FRAGMENT.read_text(encoding="utf-8")
    for axis in m.AXES:
        assert f"`{axis}`" in text, f"the fragment never names the axis {axis}"
    assert len(m.AXES) == 7


# --- Phase A review round 1: the five defects five author-blind seats confirmed ---------------


def test_a_keyed_none_is_not_printed_as_an_actionable_backlog_item(tmp_path: Path) -> None:
    """One report, one definition of `none`. `change_none` reads the axis-aware helper and the
    backlog list read the shared one, so a single row was counted as 'nothing to change' AND
    listed as a change request — the two halves of one report disagreeing about one row."""
    ledger = tmp_path / "l.jsonl"
    _write(ledger, [_row("c", 60, 1, "lean: none"), _row("c", 60, 1, "lean: a real edit")])
    r = _run(ledger, "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    items = [it["item"] for it in out["backlog"]]
    assert items == ["lean: a real edit"], items
    assert out["commands"]["c"]["change_none"] == 1
    # and the confusion/waste lists are untouched by the axis-aware read
    _write(ledger, [_row("c", 60, 1, "none", confusion="lean: none")])
    out2 = json.loads(_run(ledger, "--json").stdout)
    assert [it["item"] for it in out2["confusion"]] == ["lean: none"]


def test_a_verdict_that_mentions_the_close_out_vocabulary_keeps_its_axis(tmp_path: Path) -> None:
    """The placeholder test is ANCHORED. Unanchored it ate real verdicts: the close-out grammar is
    this loop's own subject, so `lean: step 7 should print the mail id` — a genuine verdict —
    matched `mail id` and was filed as a pasted template. Five of six realistic verdicts."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("c", 60, 1, "lean: step 7 should print the mail id it filed"),
            _row("c", 60, 1, "waste: the brief asks for steps, turns and tokens twice"),
            _row(
                "c", 60, 1, "accurate: the rubric never says what in the command text is canonical"
            ),
            _row("c", 60, 1, "rules: name what your run touched in the filed: fallback"),
            _row("c", 60, 1, "infra: make the ONE concrete edit example machine-checkable"),
            _row("c", 60, 1, "lean: <the ONE concrete edit to this command>"),  # a real paste
        ],
    )
    assert _axes(ledger, "c")["axes"] == {
        "accurate": 1,
        "infra": 1,
        "lean": 1,
        "placeholder": 1,
        "rules": 1,
        "waste": 1,
    }


def test_a_colon_inside_a_url_or_a_path_is_not_a_key_attempt(tmp_path: Path) -> None:
    """A key attempt is one alphabetic word, a colon, then whitespace — the whitespace is what
    separates `lean: x` from `https://x`, whose colon is punctuation inside a token."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("c", 60, 1, "https://example.test/x 404s in step 3"),
            _row("c", 60, 1, "C:\\Users\\x is assumed to exist"),
            _row("c", 60, 1, "lean:nospace"),
            _row("c", 60, 1, "lean:"),  # a key with nothing after it keys nothing
        ],
    )
    assert _axes(ledger, "c")["axes"] == {"unkeyed": 4}


def test_the_comma_split_is_what_stops_a_late_colon_from_keying_the_row(tmp_path: Path) -> None:
    """Discriminating on purpose: with spaces, `partition(':')` alone would already stop at the
    first colon, so the earlier grader passed with the comma split REMOVED. This value can only
    classify correctly because the head is cut at the comma first."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cfr", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m._axis_of("prefix,lean: keyed") == "unkeyed"
    assert m._axis_of("lean: cut the digest, accurate: name the flag") == "lean"


def test_the_axis_section_renders_each_command_with_its_population(tmp_path: Path) -> None:
    """The human-facing half. The empty branch had a grader; the branch a reader actually sees on
    a real ledger had none, so the line could have lost its counts and stayed green."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("c", 60, 1, "lean: one"),
            _row("c", 60, 1, "lean: two"),
            _row("c", 60, 1, "speed: missed"),
            _row("c", 60, 1, "none"),
        ],
    )
    r = _run(ledger)
    assert r.returncode == 0, r.stderr
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("- /c ("))
    assert line == "- /c (3 with a change: value of 4 run(s)): bad-axis 1 · lean 2", line


def test_observer_rank_honours_the_window_and_the_command_filter(tmp_path: Path) -> None:
    """An all-time rank answering a --since question would name a command retired months ago, and
    the fragment tells every close to consult this before spending a seat."""
    ledger = tmp_path / "l.jsonl"
    _write(
        ledger,
        [
            _row("old", 60, 1, "lean: x", days_ago=400, tok_in=10**6, tok_out=0),
            _row("new", 60, 1, "lean: x", days_ago=1, tok_in=10, tok_out=1),
        ],
    )
    r = _run(ledger, "--since", "7", "--observer-rank")
    assert r.returncode == 0, r.stderr
    assert "/new" in r.stdout and "/old" not in r.stdout, r.stdout
    r2 = _run(ledger, "--since", "7", "--observer-rank", "--json")
    assert json.loads(r2.stdout)["observer_rank"][0].startswith("observer-rank:")
