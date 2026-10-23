"""W-f365c610 (D-1131): check_convergence's refusal readers read the text under BOTH span models — its own single-line
`_mask_spans` and the shared `_fences.blank_code_spans` model — and refuse when either refuses; the two CONVERGED
readers (check_rule_grounding, check_spec_convergence) answer as they did. Input domain: hand-built markdown strings,
the panel's documents D1-D5 and the two false refusals it named (F1, D4); no fixture is borrowed."""

from __future__ import annotations

import importlib.util
import re
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


def _spine_set(tmp_path: Path, spine: str, tickets: dict[str, str]) -> list[str]:
    cc = _load("check_convergence")
    d = tmp_path / "docs" / "development" / "plans" / "2026-10-23-plan-x"
    d.mkdir(parents=True)
    (d / "2026-10-23-plan-x.md").write_text(spine, encoding="utf-8")
    for name, body in tickets.items():
        (d / name).write_text(body, encoding="utf-8")
    return cc._check_spine_set(tmp_path, d / "2026-10-23-plan-x.md", spine)


def test_d2_wrapped_comment_opener_hides_no_closing_row() -> None:
    cc = _load("check_convergence")
    # the span `the <!--⏎marker` wraps; the single-line model reads its `<!--` as a comment that swallows Pass 2
    d2 = "| Pass 1 | seat | confirmed: 0 |\n\nsee `the <!--\nmarker` here\n\n| Pass 2 | seat | confirmed: 3 |\n\nthe end --> of the note\n"
    assert cc._closing_row_fail(d2) is not None


def test_d3_compact_row_in_a_wrapped_span_still_counts() -> None:
    cc = _load("check_convergence")
    # the shared model reads `a⏎|Pass 2|…⏎b` as one wrapped span and hides the compact row; the single-line one counts it
    d3 = "| Pass 1 | seat | confirmed: 0 |\n\nsee `a\n|Pass 2|seat|confirmed: 3|\nb` here\n"
    assert cc._closing_row_fail(d3) is not None
    assert cc._closing_row_fail("| Pass 1 | seat | confirmed: 0 |\n") is None


def test_spine_set_reads_both_models(tmp_path: Path) -> None:
    board = "# Plan\n\n## Ticket Board\n\n| T01 | x |\n\nsee `the <!--\nmarker` here\n\n| T02 | y |\n\nend -->\n"
    d2 = "| Pass 1 | seat | confirmed: 0 |\n\nsee `the <!--\nmarker` here\n\n| Pass 2 | seat | confirmed: 3 |\n\nend -->\n"
    # a wrapped span holding `<!--` hides Board row T02 (no ticket file: an orphan) and the loud Pass 2 row from the
    # single-line model; the spine set hands the RAW text to both readers, so neither is hidden
    fails = _spine_set(tmp_path / "a", board + "\n" + d2, {"T01-a.md": "# T01\n"})
    assert any("Board row T02" in f for f in fails), fails
    assert any("confirmed: 3" in f for f in fails), fails
    # a wrapped span putting `Status:` at a line start in a ticket: the ticket ban refuses, as it did
    fails = _spine_set(
        tmp_path / "b",
        "# Plan\n\n## Ticket Board\n\n| T01 | x |\n",
        {"T01-a.md": "Note `a\nStatus: x` b\n"},
    )
    assert any("carries a Status: line" in f for f in fails), fails


def test_receipt_routes_disagreeing_views_grade_both(tmp_path: Path) -> None:
    cc = _load("check_convergence")
    # a design-review receipt: a wrapped span holding `<!--` hides the checklist heading and the loud row from the
    # single-line model only; the views disagree on the route, so the design route's closing-row refusal is kept
    receipt = (
        "# Review\n\n**Command:** /fabrik-plan-review\n**Status:** CONVERGED\n\n| Pass 1 | s | confirmed: 0 |\n\n"
        "see `the <!--\nmarker` here\n\n## Coverage Checklist\n\n| Pass 2 | s | confirmed: 3 |\n\nend -->\n"
    )
    assert cc._is_design_receipt(
        "**Command:** /fabrik-plan-review\n", receipt, re.compile(r"^##\s+Coverage Checklist")
    ) == {True, False}
    rdir = tmp_path / "docs" / "development" / "reviews"
    rdir.mkdir(parents=True)
    (rdir / "r.md").write_text(receipt, encoding="utf-8")
    fails = cc._check_review(tmp_path, rdir / "r.md")
    assert any("confirmed: 3" in f for f in fails), fails


def test_converged_readers_are_pinned() -> None:
    rg, sc = _load("check_rule_grounding"), _load("check_spec_convergence")
    d1 = "# Plan\n\nSize: small `\nStatus: CONVERGED\nProfile: `delta`\n\n## Constraints Digest\n"  # a stray tick above
    d5 = "Status: DRAFT - the rule `Status: CONVERGED` is quoted\n"  # mid-line: spec_convergence counts it, fail closed
    # each reader's answer as measured at 63b0c254c, before W-f365c610 (D-1131 keeps them byte-identical)
    assert rg.CONVERGED_RE.search(d1) and sc.CONVERGED_RE.search(d1)
    assert rg.CONVERGED_RE.search(d5) is None  # line-anchored
    assert sc.CONVERGED_RE.search(d5)


def test_f1_a_non_destination_tail_shields_no_span() -> None:
    fences, cc = _load("_fences"), _load("check_convergence")
    # `u `confirmed: 3`` holds a space, so `](…)` is no link destination and the backticks open a code span
    assert "confirmed" not in fences.blank_code_spans("see [r](u `confirmed: 3`)")
    assert (
        cc._closing_row_fail("| Pass 1 | seat | confirmed: 0 | see [r](u `confirmed: 3`) |\n")
        is None
    )
    # a real tail still shields its raw text: a destination, a quoted title (escapes included), angle brackets,
    # nested parentheses, an empty destination
    links = (
        '[a](b "t`x")',
        "[a](<b c>)",
        "[a](b(c)d)",
        "[a](b 't`x')",
        "[a]()",
        '[a](b "t\\"q`x")',
        "[a](b (t\\)`x))",
    )
    for link in links:
        assert fences.blank_code_spans(link + " `c`") == link + "    ", link


def test_legacy_grandfather_needs_both_models(monkeypatch) -> None:
    cc = _load("check_convergence")
    monkeypatch.setattr(
        cc, "_first_commit_date", lambda root, rel: "2020-01-01"
    )  # before the D-206 cutover
    assert cc._legacy_receipt(Path("."), "r.md", "**Status:** CONVERGED\n") == "2020-01-01"
    # the single-line model reads the wrapped span's `Status:` line as live, the shared model as a quote: an
    # exemption holds only when both models grant it
    assert cc._legacy_receipt(Path("."), "r.md", "see `a\n**Status:** CONVERGED` b\n") == ""


def test_fences_comment_line_interrupts_a_span() -> None:
    fences, cc = _load("_fences"), _load("check_convergence")
    # a line-start `<!--` starts an HTML block, ending the paragraph: a stray tick above it pairs with nothing
    assert fences.blank_code_spans("x `a\n<!-- c\nb` y") == "x `a\n<!-- c\nb` y"
    parked = "| Pass 1 | s | confirmed: 0 |\n\nnote a ` tick\n<!-- ` old ledger:\n| Pass 2 | s | confirmed: 3 |\n-->\n"
    assert cc._closing_row_fail(parked) is None
