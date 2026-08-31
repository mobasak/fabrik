"""Behaviour tests for `scripts/enforcement/check_feedback_duty.py`.

Operator directive, stated twice: *"agents must give you feedback if they find issues, or have
suggestions about our commands and rules and infra, and send infra, intel or fleet a message — they
must be proactive."*

The duty was written into both constitutions and auto-appended to all 31 commands, and
`command_run.py --feedback` made the verdict recordable. **Nothing graded it.** Measured at the
moment this check was written: 11 closed run records on the box, **11 without a verdict** — which is
honest (the flag was hours old) and is exactly the baseline a grader exists to move.

A prose obligation nobody measures is the class this repo keeps closing: the agent it constrains is
the only one who could report the omission, and an omission is precisely what does not get reported.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_feedback_duty", REPO / "scripts" / "enforcement" / "check_feedback_duty.py"
)
assert _spec and _spec.loader
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def _rec(d: Path, name: str, *, state: str = "done", feedback: str | None = "filed",
         days_ago: int = 0, command: str = "fabrik-probe") -> None:
    import datetime as dt

    body = {
        "command": command,
        "state": state,
        "closed_at": (
            dt.datetime.now(dt.UTC) - dt.timedelta(days=days_ago)
        ).isoformat(),
    }
    if feedback is not None:
        body["feedback"] = feedback
    (d / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


# ── fleet safety: warn_only means a non-zero exit reddens ~46 repos ──────────────────────────────


@pytest.mark.parametrize("setup", ["empty", "all-stated", "all-unstated", "corrupt", "no-dir"])
def test_every_path_exits_zero(tmp_path, setup):
    d = tmp_path / "runs"
    if setup != "no-dir":
        d.mkdir()
    if setup == "all-stated":
        _rec(d, "a", feedback="filed")
    elif setup == "all-unstated":
        _rec(d, "a", feedback="unstated")
    elif setup == "corrupt":
        (d / "x.json").write_text("{not json", encoding="utf-8")
    assert chk.main(["--runs", str(d)]) == 0


@pytest.mark.parametrize("argv", [["--bogus"], ["--runs"], ["-x"], ["stray"]])
def test_malformed_argv_never_exits_nonzero(argv):
    try:
        rc = chk.main(argv)
    except SystemExit as exc:
        raise AssertionError(f"argv={argv} raised SystemExit({exc.code})")
    assert rc == 0


def test_output_is_ascii_by_construction(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    _rec(d, "a", feedback="unstated", command="fabrik-café-✅")
    chk.main(["--runs", str(d)])
    capsys.readouterr().out.encode("ascii")


def test_output_fits_the_advisory_budget(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    for i in range(20):
        _rec(d, f"r{i}", feedback="unstated", command=f"fabrik-a-long-command-name-{i:02d}")
    chk.main(["--runs", str(d)])
    out = capsys.readouterr().out
    assert len(out) <= chk.ADVISORY_BUDGET, f"{len(out)} chars"
    assert chk.REMEDY[-20:] in out


# ── silence where there is nothing to say ────────────────────────────────────────────────────────


def test_no_closed_runs_says_nothing(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    chk.main(["--runs", str(d)])
    assert capsys.readouterr().out == ""


def test_a_still_running_record_is_not_graded(tmp_path, capsys):
    """The duty attaches to the CLOSE. An open run has not yet owed its verdict."""
    d = tmp_path / "runs"
    d.mkdir()
    _rec(d, "a", state="running", feedback=None)
    chk.main(["--runs", str(d)])
    assert capsys.readouterr().out == ""


def test_a_fully_compliant_window_reports_its_denominator_and_no_finding(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    _rec(d, "a", feedback="filed")
    _rec(d, "b", feedback="none")
    chk.main(["--runs", str(d)])
    out = capsys.readouterr().out
    assert "2" in out, out
    assert "UNSTATED" not in out.upper(), "a stated `none` is compliance, not a finding"


# ── the finding ──────────────────────────────────────────────────────────────────────────────────


def test_an_unstated_close_is_a_finding(tmp_path, capsys):
    d = tmp_path / "runs"
    d.mkdir()
    _rec(d, "a", feedback="unstated")
    chk.main(["--runs", str(d)])
    assert "UNSTATED" in capsys.readouterr().out.upper()


def test_a_close_predating_the_field_is_counted_not_excused(tmp_path, capsys):
    """A record with no `feedback` key at all closed without a verdict — which is what `unstated`
    MEANS. Excusing it would let the metric report compliance that never happened."""
    d = tmp_path / "runs"
    d.mkdir()
    _rec(d, "a", feedback=None)
    chk.main(["--runs", str(d)])
    assert "UNSTATED" in capsys.readouterr().out.upper()


def test_stale_records_fall_out_of_the_window(tmp_path, capsys):
    """A months-old omission is not this week's signal, and re-reporting it forever is how an
    advisory line becomes wallpaper."""
    d = tmp_path / "runs"
    d.mkdir()
    _rec(d, "old", feedback="unstated", days_ago=90)
    chk.main(["--runs", str(d)])
    assert capsys.readouterr().out == ""


def test_the_check_states_what_it_cannot_grade(tmp_path):
    """It can see that a verdict was GIVEN. It cannot see whether the filing was honest, whether the
    mail was actually sent, or whether a `none` was earned by looking."""
    assert chk.SCOPE_NOTE and "cannot" in chk.SCOPE_NOTE.lower()


def test_no_module_constant_is_dead():
    src = (REPO / "scripts" / "enforcement" / "check_feedback_duty.py").read_text(encoding="utf-8")
    for name in [n for n in dir(chk) if n.isupper() and not n.startswith("_")]:
        assert src.count(name) > 1, f"{name} is defined and never used"


def test_d055_verdict_text_is_persisted_and_digest_prints_it(tmp_path, capsys):
    """D-055 (operator's 5th ask, 2026-08-31): the close used to classify the FEEDBACK prose into
    a token and DISCARD the text — five asks produced zero visible reports because nothing stored
    the substance. The record now carries feedback_text and --digest reads it back."""
    import json

    rec = {
        "command": "fabrik-probe",
        "state": "done",
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        "updated_ts": __import__("datetime").datetime.now(__import__("datetime").UTC).timestamp(),
        "feedback": "filed",
        "feedback_text": "filed: stale anchor in fabrik-review.md:48 to infra; surfaces: review loop",
    }
    (tmp_path / "probe.json").write_text(json.dumps(rec), encoding="utf-8")
    rc = chk.main(["--runs", str(tmp_path), "--digest"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "stale anchor in fabrik-review.md:48" in out, out
    # a pre-D-055 record (no text) is labelled, never silently blank
    rec.pop("feedback_text")
    (tmp_path / "probe.json").write_text(json.dumps(rec), encoding="utf-8")
    chk.main(["--runs", str(tmp_path), "--digest"])
    assert "text not persisted" in capsys.readouterr().out
