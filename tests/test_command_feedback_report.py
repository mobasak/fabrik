"""Tests for scripts/command_feedback_report.py — the per-command optimisation report over the
fleet-wide close-out ledger (`~/.claude/state/command-feedback.jsonl`)."""

from __future__ import annotations

import json
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
