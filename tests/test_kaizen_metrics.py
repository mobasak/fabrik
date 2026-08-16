"""Behavior tests for the kaizen MEASUREMENT trigger (`scripts/sysadmin/kaizen_metrics.py`).

Every test builds its own tmp tree. Nothing here reads the live logs, the live kaizen
tables, `~/.claude-fleet`, or the crontab.

The load-bearing behavior is the honesty rule: a metric with no real source is written as
an em-dash WITH a reason, never as an invented number. `test_unavailable_metric_*` asserts
the absence of a number, not merely the presence of a dash -- a placeholder that happened
to look plausible would pass a dash-only assertion.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "kaizen_metrics",
    Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "kaizen_metrics.py",
)
assert _SPEC and _SPEC.loader
km = importlib.util.module_from_spec(_SPEC)
sys.modules["kaizen_metrics"] = km
_SPEC.loader.exec_module(km)


TABLE_HEADER = (
    "| Date | Gate first-pass rate | Death-classes /wk | Lesson-class recurrence | "
    "Review rounds /plan | Missed crons | Top friction fixed | Filed (spec/mail) |"
)
TABLE_SEP = "|---|---|---|---|---|---|---|---|"
BASELINE = "| 2026-08-12 | — | — | — | — | — | (baseline row — first real pass fills metrics) | — |"


def _kaizen_log(text_rows: list[str]) -> str:
    return "\n".join(
        [
            "# Kaizen log — infra (weekly, Monday after the cron batch; ≤90 min timebox)",
            "",
            "Prose that must survive an append.",
            "",
            TABLE_HEADER,
            TABLE_SEP,
            *text_rows,
            "",
        ]
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repo tree: both kaizen logs, a lessons file, an empty reviews dir."""
    agents = tmp_path / "docs" / "reference" / "agents"
    agents.mkdir(parents=True)
    for role in km.ROLES:
        (agents / f"kaizen-log-{role}.md").write_text(_kaizen_log([BASELINE]), encoding="utf-8")
    (tmp_path / "docs" / "development" / "reviews").mkdir(parents=True)
    (tmp_path / "docs" / "LESSONS_LEARNT.md").write_text(
        "# Lesson 1: something\n\n**Context (2026-08-14):** x\n", encoding="utf-8"
    )
    return tmp_path


def _review(repo: Path, name: str, body: str) -> None:
    (repo / "docs" / "development" / "reviews" / name).write_text(body, encoding="utf-8")


# --------------------------------------------------------------- review-rounds counting


def test_review_rounds_counts_heading_dialect(repo: Path) -> None:
    """`## Round N` headings: the per-ledger score is the highest round reached."""
    _review(repo, "2026-08-14-a-review.md", "# R\n\n## Round 1 (x)\n\n## Round 2 (y)\n")
    _review(repo, "2026-08-15-b-review.md", "# R\n\n## Round 1\n\n## Round 2\n\n## Round 3\n")

    m = km.measure_review_rounds(
        repo / "docs" / "development" / "reviews", dt.date(2026, 8, 10), dt.date(2026, 8, 16)
    )

    assert m.measured
    assert m.value.startswith("2.5 (n=2/2)")  # mean of 2 and 3


def test_review_rounds_counts_table_dialect(repo: Path) -> None:
    """A `| Round | ... |` ledger table counts too.

    The shipped 16-round stalled-midstream ledger uses ONLY this dialect. A heading-only
    counter scores it 0 and drags the mean toward a comfortable lie.
    """
    _review(
        repo,
        "2026-08-14-table-review.md",
        "# R\n\n## Round ledger\n\n"
        "| Round | Finder | Outcome |\n|---|---|---|\n"
        "| 1 | pool | 3 findings |\n| 2 | native | 1 finding |\n| 3 | native | found: 0 |\n",
    )

    m = km.measure_review_rounds(
        repo / "docs" / "development" / "reviews", dt.date(2026, 8, 10), dt.date(2026, 8, 16)
    )

    assert m.value.startswith("3.0 (n=1/1)")


def test_ledger_with_zero_round_headings_is_excluded_not_scored_zero(repo: Path) -> None:
    """A ledger with no round marker is NOT a zero-round review -- it is unmeasured.

    Scoring it 0 would invent a data point (every prose-only ledger did have rounds), and
    would pull the mean down exactly where the operator is asking "are reviews still taking
    30 rounds?". It must instead shrink the denominator, visibly.
    """
    _review(repo, "2026-08-14-prose-review.md", "# R\n\nWe reviewed it. No round headings.\n")
    _review(repo, "2026-08-15-scored-review.md", "# R\n\n## Round 1\n\n## Round 4\n")

    m = km.measure_review_rounds(
        repo / "docs" / "development" / "reviews", dt.date(2026, 8, 10), dt.date(2026, 8, 16)
    )

    assert m.value == "4.0 (n=1/2)", "the unmarked ledger must shrink n, not average in as 0"


def test_review_rounds_unavailable_when_no_ledger_carries_a_marker(repo: Path) -> None:
    _review(repo, "2026-08-14-prose-review.md", "# R\n\nNo markers at all.\n")

    m = km.measure_review_rounds(
        repo / "docs" / "development" / "reviews", dt.date(2026, 8, 10), dt.date(2026, 8, 16)
    )

    assert not m.measured
    assert m.cell == km.DASH
    assert m.reason


def test_review_rounds_respects_the_window(repo: Path) -> None:
    _review(repo, "2026-07-01-old-review.md", "# R\n\n## Round 9\n")
    _review(repo, "2026-08-15-new-review.md", "# R\n\n## Round 2\n")

    m = km.measure_review_rounds(
        repo / "docs" / "development" / "reviews", dt.date(2026, 8, 10), dt.date(2026, 8, 16)
    )

    assert m.value == "2.0 (n=1/1)"


# ------------------------------------------------------------- the honesty rule (`—`)


@pytest.mark.parametrize(
    "metric_name",
    ["Gate first-pass rate", "Lesson-class recurrence", "Missed crons"],
)
def test_unavailable_metric_is_dash_with_a_reason_and_no_invented_number(
    repo: Path, metric_name: str, tmp_path: Path
) -> None:
    """No source ⇒ an em-dash and a reason. Never a number, however plausible."""
    m = km.measure(repo, tmp_path / "absent-sound.log", dt.date(2026, 8, 16))
    metric = m.metrics[metric_name]

    assert not metric.measured
    assert metric.cell == km.DASH
    assert metric.reason and len(metric.reason) > 20, "a bare dash without a reason is a gap"
    assert not re.search(r"\d", metric.cell), f"a number was invented for {metric_name}"


def test_unavailable_reasons_reach_stderr(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reason has to be observable in the cron's log, or the `—` is silent."""
    km.main(
        [
            "--dry-run",
            "--repo-root",
            str(repo),
            "--sound-log",
            str(tmp_path / "absent-sound.log"),
            "--date",
            "2026-08-16",
        ]
    )

    err = capsys.readouterr().err
    assert "Gate first-pass rate" in err
    assert "Missed crons" in err
    # `Missed crons` is measured from the liveness audit's heartbeat proof. The fixture repo
    # has no such script, so the cell must be a DASH that NAMES the missing instrument --
    # never a plausible-looking 0.
    assert "no liveness audit at" in err


def test_missing_sound_log_yields_dash_not_zero(repo: Path, tmp_path: Path) -> None:
    """An absent log is unknown deaths, not zero deaths -- 0 would read as a healthy week."""
    m = km.measure_death_classes(tmp_path / "nope.log", dt.date(2026, 8, 10), dt.date(2026, 8, 16))

    assert not m.measured
    assert m.cell == km.DASH
    assert "0" not in m.cell


def test_death_classes_counts_occurrences_and_distinct_classes(repo: Path, tmp_path: Path) -> None:
    log = tmp_path / "sound-debug.log"
    log.write_text(
        "\n".join(
            [
                "2026-08-14 10:00:00  arg=fail  event=StopFailure  error=rate_limit  | sess=a",
                "2026-08-14 11:00:00  arg=fail  event=StopFailure  error=rate_limit  | sess=b",
                "2026-08-15 12:00:00  arg=fail  event=StopFailure  error=server_error | sess=c",
                "2026-08-15 12:30:00  arg=done  event=Stop  verdict=delegated error=- | sess=d",
                "2026-07-01 09:00:00  arg=fail  event=StopFailure  error=overloaded  | sess=e",
            ]
        ),
        encoding="utf-8",
    )

    m = km.measure_death_classes(log, dt.date(2026, 8, 10), dt.date(2026, 8, 16))

    assert m.value == "3 occ / 2 cls"  # the July death is out of window; Stop is not a death
    assert "rate_limit=2" in m.detail


# --------------------------------------------------------------------------- idempotence


def _rows(path: Path) -> list[str]:
    return km.parse_table(path.read_text(encoding="utf-8")).rows


def test_same_iso_week_run_updates_instead_of_appending(repo: Path, tmp_path: Path) -> None:
    """Two runs in one ISO week ⇒ one row. Monday's cron plus a manual re-run must not
    double-count the week."""
    log = repo / "docs" / "reference" / "agents" / "kaizen-log-infra.md"
    args = ["--once", "--no-mail", "--repo-root", str(repo), "--sound-log", str(tmp_path / "s.log")]

    km.main([*args, "--date", "2026-08-17"])  # Monday, ISO week 34
    after_first = _rows(log)
    km.main([*args, "--date", "2026-08-19"])  # Wednesday, same ISO week 34
    after_second = _rows(log)

    assert len(after_first) == 2, "baseline + the new row"
    assert len(after_second) == 2, "the same-week re-run must UPDATE, not append"
    assert km.split_row(after_second[-1])[0] == "2026-08-19"


def test_next_iso_week_appends_a_new_row(repo: Path, tmp_path: Path) -> None:
    log = repo / "docs" / "reference" / "agents" / "kaizen-log-infra.md"
    args = ["--once", "--no-mail", "--repo-root", str(repo), "--sound-log", str(tmp_path / "s.log")]

    km.main([*args, "--date", "2026-08-17"])  # week 34
    km.main([*args, "--date", "2026-08-24"])  # week 35

    assert len(_rows(log)) == 3


def test_same_week_update_preserves_analyst_filled_cells(repo: Path, tmp_path: Path) -> None:
    """The mechanical half must never stamp the analysis half's output back to `—`."""
    log = repo / "docs" / "reference" / "agents" / "kaizen-log-infra.md"
    args = ["--once", "--no-mail", "--repo-root", str(repo), "--sound-log", str(tmp_path / "s.log")]
    km.main([*args, "--date", "2026-08-17"])

    table = km.parse_table(log.read_text(encoding="utf-8"))
    cells = km.split_row(table.rows[-1])
    cells[1] = "12/14 (hand-counted)"  # analyst filled a metric the script cannot measure
    cells[6] = "hook latency fix"
    table.rows[-1] = km.render_row(cells)
    log.write_text(table.render(), encoding="utf-8")

    km.main([*args, "--date", "2026-08-19"])  # same ISO week

    final = km.split_row(_rows(log)[-1])
    assert final[1] == "12/14 (hand-counted)"
    assert final[6] == "hook latency fix"


# ------------------------------------------------------------------------- table shape


def test_append_preserves_table_shape_and_existing_rows(repo: Path, tmp_path: Path) -> None:
    log = repo / "docs" / "reference" / "agents" / "kaizen-log-infra.md"
    before = log.read_text(encoding="utf-8")

    km.main(
        [
            "--once",
            "--no-mail",
            "--repo-root",
            str(repo),
            "--sound-log",
            str(tmp_path / "s.log"),
            "--date",
            "2026-08-17",
        ]
    )

    after = log.read_text(encoding="utf-8")
    old_t, new_t = km.parse_table(before), km.parse_table(after)
    assert new_t.header == old_t.header, "the header must be byte-identical"
    assert new_t.separator == old_t.separator, "the separator must be byte-identical"
    assert new_t.head == old_t.head, "the prose above the table must be untouched"
    assert new_t.rows[0] == BASELINE, "the baseline row must be untouched"
    assert len(new_t.rows) == len(old_t.rows) + 1
    assert len(km.split_row(new_t.rows[-1])) == len(km.COLUMNS)


def test_both_role_logs_get_a_row(repo: Path, tmp_path: Path) -> None:
    km.main(
        [
            "--once",
            "--no-mail",
            "--repo-root",
            str(repo),
            "--sound-log",
            str(tmp_path / "s.log"),
            "--date",
            "2026-08-17",
        ]
    )

    for role in km.ROLES:
        assert len(_rows(km.log_path(repo, role))) == 2


# --------------------------------------------------------------------- mail is fail-soft


def test_mail_failure_does_not_lose_the_row(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The row is written BEFORE the hand-off. A dead mailer costs the notification, not the
    measurement -- otherwise a mail outage erases the only record of the week."""
    calls: list[str] = []

    def boom(repo_root: Path, role: str, body: str) -> bool:
        calls.append(role)
        raise RuntimeError("mail store unreachable")

    monkeypatch.setattr(km, "send_mail", boom)

    with pytest.raises(RuntimeError):
        km.main(
            [
                "--once",
                "--repo-root",
                str(repo),
                "--sound-log",
                str(tmp_path / "s.log"),
                "--date",
                "2026-08-17",
            ]
        )

    assert calls, "the hand-off was attempted"
    assert len(_rows(km.log_path(repo, "infra"))) == 2, "the row survived the mail failure"


def test_mail_nonzero_exit_is_reported_not_raised(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mailer that exits non-zero must be logged and stepped over, never fatal."""

    class _Proc:
        returncode = 3
        stdout = ""
        stderr = "refused: secret pattern"

    monkeypatch.setattr(km.subprocess, "run", lambda *a, **k: _Proc())

    rc = km.main(
        [
            "--once",
            "--repo-root",
            str(repo),
            "--sound-log",
            str(tmp_path / "s.log"),
            "--date",
            "2026-08-17",
        ]
    )

    assert rc == 0
    assert "ROW IS RECORDED" in capsys.readouterr().err
    for role in km.ROLES:
        assert len(_rows(km.log_path(repo, role))) == 2


def test_mail_body_carries_the_row_and_the_dash_reasons(repo: Path, tmp_path: Path) -> None:
    m = km.measure(repo, tmp_path / "absent.log", dt.date(2026, 8, 17))
    body = km.compose_mail("infra", m, m.row(), None)

    assert "2026-08-17" in body
    assert "no liveness audit at" in body, "the analyst must see WHY a cell is a dash"
    assert "liveness audit: NOT RUN" in body, "mechanism health rides the hand-off mail"
    assert "first measured pass" in body
    assert "docs/reference/agents/infra.md" in body


def test_mail_body_shows_deltas_against_the_previous_row(repo: Path, tmp_path: Path) -> None:
    m = km.measure(repo, tmp_path / "absent.log", dt.date(2026, 8, 24))
    previous = ["2026-08-17", "—", "10 occ / 2 cls", "—", "3.0 (n=2/2)", "—", "x", "y"]
    body = km.compose_mail("infra", m, m.row(), previous)

    assert "3.0 (n=2/2) ->" in body


# ------------------------------------------------------------------------------- modes


def test_dry_run_writes_nothing(repo: Path, tmp_path: Path) -> None:
    log = km.log_path(repo, "infra")
    before = log.read_text(encoding="utf-8")

    km.main(
        [
            "--dry-run",
            "--repo-root",
            str(repo),
            "--sound-log",
            str(tmp_path / "s.log"),
            "--date",
            "2026-08-17",
        ]
    )

    assert log.read_text(encoding="utf-8") == before


def test_report_prints_the_tables_and_writes_nothing(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = km.log_path(repo, "infra")
    before = log.read_text(encoding="utf-8")

    km.main(["--report", "--repo-root", str(repo), "--sound-log", str(tmp_path / "s.log")])

    out = capsys.readouterr().out
    assert "kaizen-log-infra.md" in out
    assert BASELINE in out
    assert log.read_text(encoding="utf-8") == before


# ── `Missed crons`: fed by the liveness audit, bound by the honesty rule ─────────


def _heartbeat(*findings: dict) -> dict:
    return {
        "summary": {"LIVE": 0, "DEAD": 0, "UNKNOWN": 0},
        "proofs": {
            "heartbeat": {"findings": list(findings), "unregistered": {"cron": {"owned": []}}},
            "vacuity": {"findings": []},
            "doc_claim": {"findings": [], "docs": 0},
        },
    }


def _surface(sid: str, verdict: str, reason: str = "", fault: str = "") -> dict:
    return {
        "proof": "heartbeat", "id": sid, "kind": "cron", "verdict": verdict,
        "detail": "", "instrument": "crontab -l", "instrument_fault": fault,
        "reason_class": reason, "doc": "",
    }


def test_missed_crons_counts_dead_surfaces_over_proven_ones(repo: Path) -> None:
    report = _heartbeat(
        _surface("a", "LIVE"),
        _surface("b", "DEAD", "overdue"),
        _surface("c", "DEAD", "unscheduled"),
    )
    m = km.measure_missed_crons(repo, report, "")

    assert m.measured and m.value == "2/3"
    assert "b (overdue)" in m.detail and "c (unscheduled)" in m.detail


def test_an_unknown_surface_is_never_rendered_as_a_number(repo: Path) -> None:
    """THE honesty rule at the metric boundary.

    An UNKNOWN means the probe's instrument failed. Counting it as a miss invents a defect;
    counting it as healthy hides one. It belongs in NEITHER half of the fraction, and the
    analyst must be told it was excluded and why.
    """
    report = _heartbeat(
        _surface("a", "LIVE"),
        _surface("b", "DEAD", "overdue"),
        _surface("c", "UNKNOWN", fault="/tmp is volatile"),
        _surface("d", "UNKNOWN", fault="crontab unreadable"),
    )
    m = km.measure_missed_crons(repo, report, "")

    assert m.value == "1/2", "UNKNOWN leaked into the numerator or the denominator"
    assert "2 surface(s) UNKNOWN" in m.detail
    assert "c" in m.detail and "d" in m.detail


def test_all_unknown_yields_a_dash_with_the_instrument_faults_named(repo: Path) -> None:
    report = _heartbeat(
        _surface("a", "UNKNOWN", fault="crontab -l returned no parseable cron entries")
    )
    m = km.measure_missed_crons(repo, report, "")

    assert not m.measured
    assert "no parseable cron entries" in (m.reason or "")
    assert "not a miss" in (m.reason or "")


def test_a_liveness_audit_that_did_not_run_yields_a_dash_not_zero(repo: Path) -> None:
    m = km.measure_missed_crons(repo, None, "the liveness audit timed out")

    assert not m.measured
    assert "timed out" in (m.reason or "")


def test_liveness_context_reports_inert_checks_and_stale_docs() -> None:
    report = _heartbeat(_surface("a", "LIVE"))
    report["proofs"]["vacuity"]["findings"] = [
        {"id": "check_ok", "verdict": "LIVE", "kind": "check", "instrument_fault": ""},
        {"id": "check_dead", "verdict": "DEAD", "kind": "check", "instrument_fault": ""},
        {
            "id": "check_unproven",
            "verdict": "UNKNOWN",
            "kind": "check",
            "instrument_fault": "no canary authored",
        },
    ]
    report["proofs"]["doc_claim"] = {
        "findings": [{"id": "docs/workstation/x.md:9", "verdict": "DEAD", "instrument_fault": ""}],
        "docs": 19,
    }
    lines = "\n".join(km.liveness_context(report, ""))

    assert "1 blocking rows proven able to FAIL" in lines
    assert "1 INERT (check_dead)" in lines
    assert "1 UNPROVEN" in lines
    assert "1 STALE across 19 workstation doc(s)" in lines


def test_liveness_context_never_counts_an_advisory_row_as_able_to_fail() -> None:
    """LIVE is not one thing.

    A row declared `warn_only=True` in `final_gate.py`, and an unwired diagnostic, are LIVE when
    they can SPEAK — neither has a failing exit path. Rolling them into "proven able to fail"
    would overstate enforcement by exactly the count of rows that can never fail, which is the
    finding the vacuity proof exists to surface.
    """
    report = _heartbeat(_surface("a", "LIVE"))
    report["proofs"]["vacuity"]["findings"] = [
        {"id": "check_real", "verdict": "LIVE", "kind": "check", "instrument_fault": ""},
        {"id": "check_adv", "verdict": "LIVE", "kind": "check(advisory)", "instrument_fault": ""},
        {"id": "check_off", "verdict": "LIVE", "kind": "check(unwired)", "instrument_fault": ""},
    ]
    lines = "\n".join(km.liveness_context(report, ""))

    assert "1 blocking rows proven able to FAIL" in lines
    assert "2 advisory/unwired proven to REPORT" in lines
