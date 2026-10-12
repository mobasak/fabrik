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
    """Row 1790713088: term-edit makes every delta round state --own-fix; the recipe omitted it."""
    assert (
        "round --seats <n> --findings <found> --confirmed <confirmed> --own-fix <own-fix; round 1: 0>"
        in _norm()
    )


def test_phase_zero_points_at_the_flip_gates() -> None:
    """Rows 1789467454, 1789418890: the flipped-scratch-copy gate as a Phase 0 step."""
    p0 = _norm()[_norm().index("## Phase 0") : _norm().index("## Phase 1")]
    assert "run term-edit's flip gates on a flipped SCRATCH copy before Pass 1" in p0


def test_briefs_apply_the_probe_catalogue() -> None:
    """Row 1790716618: the catalogue the review family already applies."""
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in _norm()
    )
