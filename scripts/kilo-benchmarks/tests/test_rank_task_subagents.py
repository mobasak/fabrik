"""Tests for rank_task_subagents.py — the subagent-runs flywheel aggregator.

Tests the pure ranking function against seeded fixtures — no live DB required.
The DB query itself is exercised in the smoke test in the phase gate.

Tests here are written to catch specific mutations, not just to pass:
- test_ranks_by_value_… asserts the numeric value math, not just ordering.
- test_zero_cost_… asserts the value is bounded (would fail if epsilon guard
  drifted from 1e-9 to 1.0).
- test_multiple_task_types_… asserts each model row lands under the correct
  section header (a mis-grouped row would fail).
- test_render_metadata_values asserts the actual configured constants surface
  in the doc (WINDOW_DAYS/MIN_RUNS regressions would fail).
- test_query_rows_fail_soft asserts the fail-soft contract of _query_rows
  (missing sudo binary → empty list, no raise).
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_empty_input_emits_stub_content() -> None:
    """No aggregated rows → stub markdown, exit 0."""
    from rank_task_subagents import render

    md = render([])
    assert "No aggregated runs yet" in md
    assert md.startswith("Last refresh:")
    # And critically, no `### <task_type>` sections at all — the module's
    # load_task_ranking() distinguishes stub from real data by the absence
    # of section headers (verified against select.py:112).
    assert "### " not in md


def test_ranks_by_value_success_x_quality_over_cost() -> None:
    """value = success × quality / cost — the numeric formula, not just ordering.

    Verifying value math directly catches the mutation `_value = -avg_cost` (which
    would still put cheap-good before expensive-top by luck of this fixture).
    """
    from rank_task_subagents import _value, render

    # Two models for task_type="spec"
    rows = [
        # (task_type, model, n, avg_cost, avg_quality, success_rate)
        ("spec", "cheap-good", 10, 0.10, 1.5, 0.90),  # value = 0.9 * 1.5 / 0.10 = 13.5
        ("spec", "expensive-top", 10, 0.50, 1.7, 0.95),  # value = 0.95 * 1.7 / 0.50 = 3.23
    ]
    # Direct math assertion — mutation-proof.
    assert _value(0.10, 1.5, 0.90) == 13.5
    assert abs(_value(0.50, 1.7, 0.95) - 3.23) < 0.01

    md = render(rows)
    # Cheap-good ranks #1 and its value column shows 13.50 (2dp per render()).
    lines = md.splitlines()
    rank_1_line = next(line for line in lines if line.startswith("| 1 "))
    assert "cheap-good" in rank_1_line
    assert "13.50" in rank_1_line, f"expected value=13.50 in rank-1 row, got: {rank_1_line}"
    rank_2_line = next(line for line in lines if line.startswith("| 2 "))
    assert "expensive-top" in rank_2_line
    assert "3.23" in rank_2_line


def test_ranks_flip_when_quality_drops() -> None:
    """A row where cheap-but-lower-quality should NOT win over expensive-but-top —
    catches the mutation `_value = -avg_cost` which ignores quality/success entirely.
    """
    from rank_task_subagents import _value, render

    rows = [
        # cheap but terrible: value = 0.5 * 0.5 / 0.10 = 2.5
        ("spec", "cheap-terrible", 10, 0.10, 0.5, 0.5),
        # pricier but excellent: value = 1.0 * 2.0 / 0.50 = 4.0
        ("spec", "pricier-top", 10, 0.50, 2.0, 1.0),
    ]
    assert _value(0.10, 0.5, 0.5) == 2.5
    assert _value(0.50, 2.0, 1.0) == 4.0

    md = render(rows)
    lines = md.splitlines()
    rank_1_line = next(line for line in lines if line.startswith("| 1 "))
    assert "pricier-top" in rank_1_line, (
        f"quality/success must beat pure-cost — expected pricier-top at #1, got: {rank_1_line}"
    )


def test_min_runs_threshold_filters_out_low_n() -> None:
    """Pairs with fewer than 3 runs must NOT appear in the ranking."""
    from rank_task_subagents import filter_min_runs

    rows = [
        ("spec", "flaky-once", 1, 0.05, 2.0, 1.0),  # 1 run — drop
        ("spec", "twice", 2, 0.05, 2.0, 1.0),  # 2 runs — drop
        ("spec", "thrice", 3, 0.05, 2.0, 1.0),  # 3 runs — keep
        ("spec", "many", 47, 0.32, 1.64, 0.94),  # keep
    ]
    kept = filter_min_runs(rows, min_n=3)
    kept_models = {r[1] for r in kept}
    assert kept_models == {"thrice", "many"}


def test_multiple_task_types_get_separate_sections_with_correct_placement() -> None:
    """Each task_type gets its own ### section AND its rows go under the RIGHT section.

    A mutation from `by_task.setdefault(r[0], ...)` to `by_task.setdefault(r[2], ...)`
    would put every row in a section named after `n`, and this test would fail.
    """
    from rank_task_subagents import render

    rows = [
        ("spec", "MODEL_SPEC", 47, 0.32, 1.64, 0.94),
        ("plan", "MODEL_PLAN", 62, 0.28, 1.30, 0.91),
        ("code", "MODEL_CODE", 100, 0.15, 1.20, 0.88),
    ]
    md = render(rows)

    # Each section header exists.
    assert "### spec (n_total=47)" in md
    assert "### plan (n_total=62)" in md
    assert "### code (n_total=100)" in md

    # And critically: each model appears in the correct section. Slice the doc by
    # `### ` headers and assert per-section membership.
    sections: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in md.splitlines():
        if line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(body)
            current = line.split()[1]  # 'spec' / 'plan' / 'code'
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = "\n".join(body)

    assert "MODEL_SPEC" in sections["spec"]
    assert "MODEL_SPEC" not in sections["plan"]
    assert "MODEL_SPEC" not in sections["code"]
    assert "MODEL_PLAN" in sections["plan"]
    assert "MODEL_PLAN" not in sections["spec"]
    assert "MODEL_CODE" in sections["code"]
    assert "MODEL_CODE" not in sections["plan"]


def test_render_metadata_values_reflect_configured_constants() -> None:
    """The header must contain the ACTUAL configured WINDOW_DAYS and MIN_RUNS,
    not just the labels. Catches a WINDOW_DAYS drift from 90 → 9000."""
    from rank_task_subagents import MIN_RUNS, WINDOW_DAYS, render

    md = render([])
    # The header lines must contain the numeric config values, not just the labels.
    assert f"Window: {WINDOW_DAYS} days" in md
    assert f"Min runs: {MIN_RUNS}" in md

    # And the date must be ISO YYYY-MM-DD (contract for the module's future
    # staleness reader — see UPSTREAM_FEEDBACK.md).
    assert re.search(r"^Last refresh: \d{4}-\d{2}-\d{2}", md, re.M)


def test_zero_cost_row_produces_bounded_value() -> None:
    """cost=0 must NOT crash AND the resulting value must be finite AND large enough
    that a real free-tier model actually ranks well. Catches:
      - guard drift from 1e-9 → 1.0 (would produce value ≈ 0.8 vs 8e8)
      - removal of the guard entirely (would raise ZeroDivisionError)
    """
    from rank_task_subagents import _value

    val = _value(0.0, 1.0, 0.80)
    # With max(0, 1e-9) → epsilon in denominator → value ≈ 8e8
    assert math.isfinite(val)
    assert val > 1e6, (
        f"free-tier value should dominate; if guard is 1.0 instead of 1e-9, "
        f"we'd get ≈0.8 — actual: {val}"
    )


def test_query_rows_fail_soft_on_missing_sudo(monkeypatch) -> None:
    """_query_rows() must return [] (never raise) when sudo/psql is unreachable.

    Fixes Finder B's finding #6: `_query_rows()` docstring promises "Fail-soft:
    any error → empty list", but no test proved this. Reverting the
    `except FileNotFoundError` handler would leak the exception up into
    daily_refresh.sh and wedge the whole nightly chain — this test catches
    that regression.
    """
    from rank_task_subagents import _query_rows

    def _boom(*args, **kwargs) -> subprocess.CompletedProcess:
        raise FileNotFoundError("no sudo binary")

    monkeypatch.setattr(subprocess, "run", _boom)
    rows = _query_rows()
    assert rows == []


def test_query_rows_fail_soft_on_psql_nonzero_exit(monkeypatch) -> None:
    """psql returning non-zero exit (DB down / table missing / permission denied)
    must also become empty rows, not an exception."""
    from rank_task_subagents import _query_rows

    def _bad_exit(*args, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=1,
            stdout="",
            stderr="FATAL: database does not exist",
        )

    monkeypatch.setattr(subprocess, "run", _bad_exit)
    rows = _query_rows()
    assert rows == []


def test_query_rows_skips_null_cost_row(monkeypatch, capsys) -> None:
    """A group where AVG(cost_usd) IS NULL (no cost signal at all) must be
    SKIPPED, not treated as cost=0 (which would rank it #1 via the epsilon
    guard — a completely un-instrumented model would appear to dominate)."""
    from rank_task_subagents import PSQL_FIELD_SEP, _query_rows

    # Two rows: one with NULL avg_cost (empty string in psql -A output),
    # one with a real cost. Only the second should survive.
    stdout = (
        f"spec{PSQL_FIELD_SEP}broken-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"{PSQL_FIELD_SEP}1.5{PSQL_FIELD_SEP}0.9\n"
        f"spec{PSQL_FIELD_SEP}good-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"0.10{PSQL_FIELD_SEP}1.5{PSQL_FIELD_SEP}0.9\n"
    )

    def _fake_run(*args, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    rows = _query_rows()
    assert len(rows) == 1
    assert rows[0][1] == "good-model"
    err = capsys.readouterr().err
    assert "no cost signal" in err  # operator-visible warning about the skipped row


def test_query_rows_treats_null_quality_as_neutral_not_zero(monkeypatch) -> None:
    """quality_score is NULL on the module's auto-ledger path (per fabrik-lib AI's
    2026-07-06 UPSTREAM_FEEDBACK reply — `quality_score` is orchestrator opt-in).
    Treating NULL as 0.0 would collapse `success × quality / cost = 0` for every
    un-scored row and destroy the ranking. NULL → 1.0 (neutral) is the fix.
    """
    from rank_task_subagents import PSQL_FIELD_SEP, _query_rows, _value

    # avg_quality column empty (NULL). success=0.9, cost=0.10
    stdout = (
        f"spec{PSQL_FIELD_SEP}auto-ledger-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"0.10{PSQL_FIELD_SEP}{PSQL_FIELD_SEP}0.9\n"
    )

    def _fake_run(*args, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    rows = _query_rows()
    assert len(rows) == 1
    assert rows[0][1] == "auto-ledger-model"
    # avg_quality was NULL → parsed as 1.0 (neutral), NOT 0.0 (collapse).
    assert rows[0][4] == 1.0, f"NULL avg_quality must → 1.0, got {rows[0][4]}"
    # And the value is non-zero — success / cost effectively.
    v = _value(rows[0][3], rows[0][4], rows[0][5])
    assert v > 0, f"un-scored row must have nonzero value; got {v}"
    assert v == 0.9 * 1.0 / 0.10  # exactly 9.0


def test_query_rows_skips_non_finite_or_negative_cost(monkeypatch, capsys) -> None:
    """NaN, +inf, and negative avg_cost values must all be skipped — max(nan, 1e-9)
    returns nan (silently mis-orders sort), and negative cost would clamp to 1e-9
    and rank as artificial #1. Catches Finder A #1 + #2."""
    from rank_task_subagents import PSQL_FIELD_SEP, _query_rows

    stdout = (
        # NaN cost (a caller inserted 'NaN'::float8)
        f"spec{PSQL_FIELD_SEP}nan-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"nan{PSQL_FIELD_SEP}1.5{PSQL_FIELD_SEP}0.9\n"
        # Negative cost (refund credited)
        f"spec{PSQL_FIELD_SEP}refund-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"-0.05{PSQL_FIELD_SEP}1.5{PSQL_FIELD_SEP}0.9\n"
        # +inf cost
        f"spec{PSQL_FIELD_SEP}inf-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"inf{PSQL_FIELD_SEP}1.5{PSQL_FIELD_SEP}0.9\n"
        # Real row survives
        f"spec{PSQL_FIELD_SEP}real-model{PSQL_FIELD_SEP}5{PSQL_FIELD_SEP}"
        f"0.10{PSQL_FIELD_SEP}1.5{PSQL_FIELD_SEP}0.9\n"
    )

    def _fake_run(*args, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    rows = _query_rows()
    assert len(rows) == 1
    assert rows[0][1] == "real-model"
    err = capsys.readouterr().err
    assert "bad avg_cost" in err  # each bad row logs, so the operator can trace the data
