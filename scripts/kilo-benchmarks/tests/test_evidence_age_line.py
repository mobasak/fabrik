# AFTER-EDIT: ../rank_task_subagents.py | ../../../docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
"""The routing doc's `Evidence age:` line (operator ask 2026-09-08, D-182 follow-up).

`Last refresh:` is the day the RANKER RAN; the cron re-stamps it every morning. It says nothing
about how old the EVIDENCE is, so a ranking built on frozen data wears a current date. With the
pool OFF by ruling nothing new enters `subagent_runs` (native Claude seats produce no AgentResult
and never record), so the two dates diverge from the moment the corpus flip lands.

⚠️ DELIBERATE DEVIATION from this directory's zero-mock/real-DB convention, stated rather than
silent: these tests stub `subprocess.run` at the module boundary. The SQL here is one
`max(ts), count(*)` — the risk is NOT the query, it is the STATE LOGIC (fresh / frozen / drained /
unreadable) and the WORDING each state emits, since the whole point of the line is what a human
reads months later. `test_canary_grounding_column.py` keeps the real-DB oracle for the ranking SQL.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
KILO_DIR = TESTS_DIR.parent
REPO = KILO_DIR.parent.parent
for _p in (str(KILO_DIR), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rank_task_subagents as rts  # noqa: E402


def _stub(monkeypatch, stdout: str, returncode: int = 0):
    def fake(*_a, **_k):
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(rts.subprocess, "run", fake)


def test_fresh_evidence_reads_as_a_plain_fact(monkeypatch):
    _stub(monkeypatch, f"2026-09-08{rts.PSQL_FIELD_SEP}16847\n")
    line = rts._evidence_age("2026-09-08")
    assert line.startswith("Evidence age:") and "⚠️" not in line
    assert "2026-09-08" in line and "16,847" in line


def test_frozen_evidence_warns_and_names_the_date_the_window_drains(monkeypatch):
    """THE line this exists for. No new runs → the ranking is frozen while `Last refresh` advances.
    The reader must be told (a) the evidence is stale, (b) WHEN the window empties, and (c) that
    `Last refresh` is not the age of the data — otherwise a re-enable months later routes on it."""
    _stub(monkeypatch, f"2026-09-07{rts.PSQL_FIELD_SEP}16847\n")
    line = rts._evidence_age("2026-11-01")
    assert "⚠️" in line and "FROZEN" in line
    assert "55d old" in line, line
    assert "2026-12-06" in line, "must name the exact date the 90-day window empties"
    assert "vendored table" in line, "must name the consequence, not just the staleness"
    assert "not the age of its data" in line


def test_a_drained_window_says_the_sections_are_empty_and_routing_falls_back(monkeypatch):
    """The dangerous end-state: an empty window emits empty sections, and select.py's
    `table.get(task_type) or _TABLE[task_type]` then hands EVERY task type to the unrestricted
    vendored table. That must read as an alarm, not as a quiet zero."""
    _stub(monkeypatch, f"{rts.PSQL_FIELD_SEP}0\n")
    line = rts._evidence_age("2026-12-31")
    assert "⚠️" in line and "EMPTY" in line
    assert "UNRESTRICTED" in line and "not a policy" in line


def test_an_unreadable_evidence_query_never_emits_an_empty_line(monkeypatch):
    """A MISSING line reads as 'no problem' — the exact illusion this feature removes. Every
    failure path must still say something, and must not take the ranking down."""
    _stub(monkeypatch, "", returncode=1)
    assert "UNKNOWN" in rts._evidence_age("2026-09-08")

    def boom(*_a, **_k):
        raise OSError("psql gone")

    monkeypatch.setattr(rts.subprocess, "run", boom)
    line = rts._evidence_age("2026-09-08")
    assert line.strip() and "UNKNOWN" in line and "OSError" in line

    _stub(
        monkeypatch, f"not-a-date{rts.PSQL_FIELD_SEP}12\n"
    )  # real separator; the DATE is the junk
    assert "UNKNOWN" in rts._evidence_age("2026-09-08")


def test_the_line_is_in_the_rendered_header_under_last_refresh(monkeypatch):
    """Position matters: it must sit directly under `Last refresh` so the two dates are read
    together, not paragraphs apart."""
    _stub(monkeypatch, f"2026-09-07{rts.PSQL_FIELD_SEP}42\n")
    monkeypatch.setenv("_TEST_FIXED_DATE", "2026-11-01")
    doc = rts.render([], state="ok")
    lines = [ln for ln in doc.splitlines() if ln.strip()]
    i = next(n for n, ln in enumerate(lines) if ln.startswith("Last refresh:"))
    assert lines[i + 1].lstrip("⚠️ ").startswith("Evidence age:"), lines[i : i + 2]
