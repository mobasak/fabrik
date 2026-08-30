"""The close REFUSES without a feedback verdict — the layer that makes the duty bind.

Operator, three times: *"agents must give you feedback if they find issues, or have suggestions
about our commands and rules and infra, and send infra, intel or fleet a message — they must be
proactive."* Three layers were built and none of them bound. Measured 2026-08-28 across the live
box: the duty was in 30/30 rendered commands and 4/4 agent definitions, the fleet copies were
byte-identical, `--feedback` existed, the verdict persisted, a grader read it — and there were
**13 closes in 14 days, 12 with no verdict, and zero `filed` verdicts ever recorded**.

The missing layer was mechanical: `done` returned 0 without the flag, and the grader is
`warn_only`. This refusal is the whole fix, and it deliberately adds no new blocking check — the
record stays `running`, which `final_gate_stop.py` already blocks the turn on.

The grandfather clause is not politeness: two peer sessions held live run records at the moment
this landed, dispatched under a contract that never mentioned the flag.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("cr", REPO / "scripts" / "command_run.py")
assert _spec and _spec.loader
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)


def _rec(started: dt.datetime) -> dict:
    return {"command": "fabrik-probe", "state": "running", "started_at": started.isoformat()}


AFTER = cr._FEEDBACK_REQUIRED_FROM + dt.timedelta(days=1)
BEFORE = cr._FEEDBACK_REQUIRED_FROM - dt.timedelta(days=1)


def test_a_run_started_after_the_cutoff_owes_a_verdict():
    assert cr._feedback_is_required(_rec(AFTER)) is True


def test_a_run_started_before_the_cutoff_is_grandfathered():
    """A peer mid-run when this landed must not be trapped by a rule it never read."""
    assert cr._feedback_is_required(_rec(BEFORE)) is False


def test_an_unparseable_or_missing_timestamp_fails_open():
    """Never wedge a close on a record we cannot date — that traps an agent with no way out."""
    for bad in ({}, {"started_at": ""}, {"started_at": "not-a-date"}, {"started_at": None},
                {"started_at": "2026-08-28T00:00:00"}):  # naive: _parse_ts rejects it
        assert cr._feedback_is_required(bad) is False, bad


def test_the_refusal_message_names_both_valid_verdicts(capsys, tmp_path, monkeypatch):
    """A refusal that does not say how to satisfy it converts one stall into another.

    Asserted on what the process actually PRINTS, not on the source text — a grep of the source
    passes even if the refusal never fires, which is the vacuity this suite exists to avoid."""
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    _run(monkeypatch, tmp_path, ["done", "--command", "fabrik-probe", "--evidence", "e"])
    printed = capsys.readouterr().out
    assert "--feedback 'filed" in printed, printed
    assert "--feedback 'none" in printed, printed
    assert "close-feedback.md" in printed, printed


def test_the_stop_hook_blocks_on_the_state_a_refused_close_leaves_behind():
    """The refusal has teeth only because the record stays `running` and the Stop hook keys on
    exactly that. If this coupling ever breaks, the refusal degrades to a printed complaint."""
    hook = (REPO / ".claude" / "hooks" / "final_gate_stop.py").read_text(encoding="utf-8")
    assert 'state' in hook and '"running"' in hook


def test_a_verdict_of_none_satisfies_the_requirement():
    """`none` is a verdict. Counting it as absence would push agents toward inventing filings."""
    verdict, beats = cr._feedback_verdict("none — exercised the flows corpus and the gate")
    assert verdict == "none" and beats == []


def test_whitespace_only_feedback_does_not_satisfy_it(monkeypatch, tmp_path):
    """A verdict of spaces is silence with extra steps. Exercised through the real close — the
    previous version of this test asserted a re-implementation of the production expression
    against a stub object, so it would have passed with the `.strip()` removed."""
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    rc = _run(monkeypatch, tmp_path, ["done", "--command", "fabrik-probe", "--evidence", "e",
                                      "--feedback", "   "])
    assert rc == 1
    rec = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert rec["state"] == "running", rec


def test_handoff_owes_a_verdict_too(monkeypatch, tmp_path):
    """The third close, and the one the certification gauntlets MANDATE — /fabrik-user-test and
    /fabrik-service-test close NOT-QUIET runs this way, so it is the disposition most likely to
    carry machinery friction, and it was the branch with no test."""
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    rc = _run(monkeypatch, tmp_path, ["handoff", "--command", "fabrik-probe", "--reason", "r",
                                      "--resume", "docs/x.md"])
    assert rc == 1
    rec = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert rec["state"] == "running", rec


def test_handoff_with_a_verdict_closes_and_releases_the_stop_hook(monkeypatch, tmp_path):
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    rc = _run(monkeypatch, tmp_path, ["handoff", "--command", "fabrik-probe", "--reason", "r",
                                      "--resume", "docs/x.md", "--feedback", "none — swept it"])
    assert rc == 0
    rec = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert rec["state"] == "handoff" and rec["feedback"] == "none", rec


# ── end to end: the refusal itself, through main(), against an isolated state dir ────────────


def _run(monkeypatch, tmp_path, argv: list[str], *, sid: str = "s1") -> int:
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
    return cr.main(argv)


def test_done_without_feedback_is_refused_and_the_record_stays_running(monkeypatch, tmp_path):
    """The behaviour the whole change exists for. `running` is load-bearing: it is what the Stop
    hook blocks the turn on, so a refused close is a blocked turn, not a printed suggestion."""
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    rc = _run(monkeypatch, tmp_path, ["done", "--command", "fabrik-probe", "--evidence", "e"])
    assert rc == 1, "a close with no verdict must be refused"
    rec = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert rec["state"] == "running", "a REFUSED close must not half-mutate the record"
    assert "feedback" not in rec


def test_done_with_feedback_closes_normally(monkeypatch, tmp_path):
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    rc = _run(monkeypatch, tmp_path, ["done", "--command", "fabrik-probe", "--evidence", "e",
                                      "--feedback", "filed a corpus defect to infra"])
    assert rc == 0
    rec = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert rec["state"] == "done" and rec["feedback"] == "filed"


def test_blocked_owes_a_verdict_too(monkeypatch, tmp_path):
    """A halted run has MORE to report about the machinery, not less."""
    _run(monkeypatch, tmp_path, ["start", "--command", "fabrik-probe", "--phases", "1",
                                 "--terminal", "t"])
    rc = _run(monkeypatch, tmp_path, ["blocked", "--command", "fabrik-probe", "--reason", "r"])
    assert rc == 1


def test_bare_none_refused_substance_floor():
    """D-036: a bare 'none' (no surfaces named) is REFUSED at close — semantically
    identical to the silence the field exists to end. 'none — <surfaces>' passes."""
    assert cr._feedback_lacks_substance("none")
    assert cr._feedback_lacks_substance("none.")
    assert cr._feedback_lacks_substance("N/A")
    assert cr._feedback_lacks_substance("nothing")
    assert cr._feedback_lacks_substance("none — x")  # decoration + noise is still bare
    assert not cr._feedback_lacks_substance("none — swept it")  # terse but real
    assert not cr._feedback_lacks_substance("none — surfaces exercised: mail.py send seam, rubric derivation")
    assert not cr._feedback_lacks_substance("filed the stale-twin finding to infra (01M1XXXX)")


def test_negated_filing_verb_stays_none():
    """MAJOR regression: 'not filed anywhere' counted as a filing — the negation
    lost to bare verb presence, inflating the diligence metric."""
    assert cr._feedback_verdict("none — not filed anywhere, swept infra rules")[0] == "none"
    assert cr._feedback_verdict("none — never filed, checked fleet specs only")[0] == "none"
    assert cr._feedback_verdict("filed the stale-twin to infra")[0] == "filed"


def test_bare_filed_lacks_substance():
    """MAJOR regression: a vacuous 'filed' passed the floor a vacuous 'none' failed."""
    assert cr._feedback_lacks_substance("filed")
    assert cr._feedback_lacks_substance("sent.")
    assert not cr._feedback_lacks_substance("filed the corpus defect to infra (01M1X)")


def test_stopword_none_lacks_substance():
    """MAJOR regression: 'none — nothing to report' is the bare none in a costume."""
    assert cr._feedback_lacks_substance("none — nothing")
    assert cr._feedback_lacks_substance("none: nothing to report")
    assert cr._feedback_lacks_substance("none))))))")
    assert not cr._feedback_lacks_substance("none — swept it")
