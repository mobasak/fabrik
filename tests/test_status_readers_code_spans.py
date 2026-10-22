"""W-f365c610: the enforcement readers that judge a `Status:` line or a ledger read inline code spans as the shared
`_fences` model does (D-1114) — a span may wrap across lines inside a paragraph, and what it holds is a quote."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ENF = Path(__file__).resolve().parent.parent / "scripts" / "enforcement"


def _load(name: str):
    if str(ENF) not in sys.path:
        sys.path.insert(0, str(ENF))
    spec = importlib.util.spec_from_file_location(f"_t_{name}", ENF / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_comment_opener_inside_a_wrapped_span_hides_no_ledger_row() -> None:
    cc = _load("check_convergence")
    # the span `the <!--⏎marker` wraps; read as one literal run, its `<!--` swallowed the last Pass row (fail open)
    text = (
        "| Pass 1 | seat | confirmed: 0 |\n\nsee `the <!--\nmarker` here\n\n"
        "| Pass 2 | seat | confirmed: 3 |\n\nthe end --> of the note\n"
    )
    assert cc._closing_row_fail(text) is not None


def test_a_status_line_inside_a_wrapped_span_is_no_ticket_status() -> None:
    cc = _load("check_convergence")
    # a wrapped span that puts `Status:` at a line start is a quote (the ban failed CLOSED on it)
    assert cc.ANY_STATUS_LINE.search(cc._blank_quoted("Note `a\nStatus: x` b\n")) is None
    assert cc.ANY_STATUS_LINE.search(cc._blank_quoted("Status: DRAFT\n")) is not None


def test_rule_grounding_grades_only_a_status_outside_every_span() -> None:
    rg = _load("check_rule_grounding")
    assert rg._converged("Status: CONVERGED\n")
    assert not rg._converged("quoted `a\nStatus: CONVERGED` here\n")


def test_spec_convergence_grades_only_a_status_outside_every_span() -> None:
    sc = _load("check_spec_convergence")
    assert sc._converged("Status: CONVERGED\n")
    assert not sc._converged("Status: DRAFT — the rule `Status: CONVERGED` is quoted\n")
