"""/fabrik-spec-review feedback queue answered in one pass (D-735): the pass ceiling, the round recipe, Phase 0.

The ceiling test is a property over every command source, since the same wrong phrase sat in four of them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "commands" / "_sources"
SRC = SOURCES / "fabrik-spec-review.md"


def _norm(path: Path = SRC) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def test_no_command_caps_the_workflow_pass_number() -> None:
    """Row 1790692298: term-edit has no round ceiling and the workflow never validates `pass`."""
    capped = [p.name for p in sorted(SOURCES.glob("*.md")) if "`pass: 2|3`" in _norm(p)]
    assert not capped, capped
    for name in (
        "fabrik-spec-review.md",
        "fabrik-plan-review.md",
        "fabrik-review-scoped.md",
        "fabrik-review.md",
    ):
        assert "`pass: <n>`, the next pass number (unbounded)" in _norm(SOURCES / name), name


def test_the_round_recipe_states_own_fix() -> None:
    """Row 1790713088: term-edit makes every delta round state --own-fix; both recipes omitted it."""
    for path in (SRC, SOURCES / "fabrik-plan-review.md"):
        assert (
            "--own-fix <own-fix; round 1: 0> --slices <name>:<verified>/<claims>,… --classes-swept <every class swept>"
            in _norm(path)
        ), path.name


def test_phase_zero_points_at_the_flip_gates() -> None:
    """Rows 1789467454, 1789418890: the flipped-scratch-copy gate as a Phase 0 step."""
    p0 = _norm()[_norm().index("## Phase 0") : _norm().index("## Phase 1")]
    assert (
        "**Flip gates, at Pass 1 and at the close:** run term-edit's flip gates on a flipped SCRATCH copy before Pass 1 and again at the close"
        in p0
    )


def test_briefs_apply_the_probe_catalogue() -> None:
    """Row 1790716618: the catalogue the review family already applies."""
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in _norm()
    )


def test_flow_fixes_panel_residue_and_absolute_brief_paths() -> None:
    """Rows 1791937893 and 1791945243: a code-FLOW fix is invariants from its first edit; routed panel-delta
    residue is recorded, never confirmed, so it keeps the flip; a brief's pin, copy and fix paths are absolute."""
    assert (
        "every fix inside such a section is written as invariants + touchpoints from its FIRST edit — not only "
        "once the edit loop's TWO CONSECUTIVE RESIDUE PASSES rule forces a rewrite there — and never as a re-worded "
        "sequence or new mechanism"
    ) in _norm()
    critique = _norm(ROOT / "commands" / "_fragments" / "design-critique.md")
    assert (
        "residue a delta round raises AFTER the stop fired is `RECORDED — measured` there (term-edit's scope-growth "
        "stop), not confirmed, so it does not hold the flip, while the round that fires the stop confirms and "
        "fixes its defects and does"
    ) in critique
    core = _norm(ROOT / "commands" / "_fragments" / "subagents-core.md")
    assert (
        "The dispatcher writes every pin, copy, fix and scratch path a brief names as a literal absolute path, never "
        "one relative to a checkout or a placeholder the seat expands"
    ) in core


def test_both_design_reviews_name_the_receipt_and_the_command_line_the_gate_routes_on(
    tmp_path: Path,
) -> None:
    """Mail 01M4W4ZWTZ: check_convergence routes a design receipt by its header `Command:` line, so each review
    command names its receipt path and that line, and the line as written routes through the real checker."""
    from scripts.enforcement import check_convergence as cc

    ledger = (
        "\n## Pass Ledger\n| Pass 1 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 |\n"
    )
    for kind in ("spec", "plan"):
        text = _norm(SOURCES / f"fabrik-{kind}-review.md")
        assert (
            "The Pass Ledger lives in the review receipt,"
            f" `docs/development/reviews/<YYYY-MM-DD>-<slug>-{kind}-review.md`, whose first 10 lines carry the line"
            f" `**Command:** /fabrik-{kind}-review`: once the receipt claims a finished review,"
            " `check_convergence.py` grades it by its ledger only under that label, and demands a code review's"
            " gate embed without it."
        ) in text
        line = re.search(r"`(\*\*Command:\*\* /fabrik-" + kind + r"-review)`", text).group(1)
        inside = tmp_path / f"{kind}-inside.md"
        inside.write_text(f"# Review\n\n**Status:** CONVERGED\n{line}\n{ledger}")
        assert cc._check_review(tmp_path, inside) == []
        past = tmp_path / f"{kind}-past.md"
        past.write_text("# Review\n\n**Status:** CONVERGED\n" + "x\n" * 7 + f"{line}\n{ledger}")
        assert cc._check_review(tmp_path, past)
