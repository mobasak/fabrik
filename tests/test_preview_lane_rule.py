"""The preview lane for pre-release site UI (W-a0a32de2): one paragraph in § Orient step 0 of both
contracts, pointed at from every place that routes operator-named work up.

Each test reads the live text; the mutants that turn each one red are named in its docstring."""

from __future__ import annotations

from pathlib import Path

FABRIK = Path(__file__).resolve().parents[1]
HUB = FABRIK / "CLAUDE.md"
TEMPLATE = FABRIK / "templates/governance/CLAUDE.md"
SCOPED = FABRIK / "commands/_sources/fabrik-review-scoped.md"
TASK = FABRIK / "commands/_sources/fabrik-task.md"
PACK = FABRIK / ".windsurf/rules/core/50-code-review.md"

HEADING = "**Pre-release site UI — the preview lane.**"
POINTER = "the preview lane paragraph below"
ROUTER_POINTER = "preview lane"
STEP0_START = "0. **Task→skill routing:**"
STEP0_END = {HUB: "1. **Hub identity, not a scaffold type:**", TEMPLATE: "1. `project.yaml::type` tells you which"}


def _step0(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(STEP0_START)
    return text[start : text.index(STEP0_END[path], start)]


def _paragraph(path: Path) -> str:
    step0 = _step0(path)
    start = step0.index(HEADING)
    end = step0.find("\n\n", start)
    return step0[start : end if end != -1 else len(step0)]


def _one_line(text: str) -> str:
    return " ".join(text.split())


def test_both_contracts_carry_the_same_preview_lane_paragraph() -> None:
    """Mutants: delete the paragraph from either contract; change one word in one copy; move it out
    of step 0 or before the "No code surface at all" paragraph."""
    paragraphs = {}
    for path in (HUB, TEMPLATE):
        step0 = _step0(path)
        assert step0.count(HEADING) == 1, path.name
        assert step0.index("**No code surface at all**") < step0.index(HEADING), path.name
        assert step0.index(HEADING) < step0.index("**Tripwire:**"), path.name
        paragraphs[path] = _paragraph(path)
    assert paragraphs[HUB] == paragraphs[TEMPLATE]


def test_row_1b_points_to_the_preview_lane() -> None:
    """Mutants: drop the pointer from either row 1b; put it inside the pinned operator-named clause."""
    pinned = (
        "operator-named work (the operator explicitly asked for the full `/fabrik-review`, or asked by "
        "name for a code or config change — naming alone never routes up a diff with no code surface, "
        'the "No code surface at all" paragraph\'s set)'
    )
    for path in (HUB, TEMPLATE):
        row = next(line for line in _step0(path).splitlines() if line.lstrip().startswith("| 1b |"))
        assert pinned in row, path.name
        assert row.index(pinned) + len(pinned) <= row.index(POINTER), path.name


def test_nothing_outside_step_0_names_the_preview_lane() -> None:
    """The lane lives in ONE place per contract. Mutant: restate it in Completion Contract 1a."""
    for path in (HUB, TEMPLATE):
        text = path.read_text(encoding="utf-8")
        assert text.count("preview lane") == _step0(path).count("preview lane"), path.name


def test_each_router_carries_one_preview_lane_pointer() -> None:
    """Mutants: delete the pointer from the scoped classify step, the fabrik-task `heavy=yes`
    sentence or the pack's escalation bullet; state it twice in one of them."""
    scoped = SCOPED.read_text(encoding="utf-8")
    classify = next(p for p in scoped.split("\n\n") if p.startswith("**Before the record — classify"))
    assert _one_line(classify).count(ROUTER_POINTER) == 1
    assert _one_line(scoped).count(ROUTER_POINTER) == 1
    task = _one_line(TASK.read_text(encoding="utf-8"))
    assert task.count(ROUTER_POINTER) == 1
    assert task.index("`heavy=yes` includes operator-named work") < task.index(ROUTER_POINTER)
    pack = _one_line(PACK.read_text(encoding="utf-8"))
    assert pack.count(ROUTER_POINTER) == 1
    assert pack.index("operator-named work (CLAUDE.md lane row 1b") < pack.index(ROUTER_POINTER)


def test_the_paragraph_keeps_server_side_and_release_gates() -> None:
    """Mutants: drop a class that keeps its row, or a release gate, from the paragraph."""
    para = _one_line(_paragraph(HUB))
    for kept in ("server-side", "form endpoint", "auth", "secret", "schema", "synced or gate path"):
        assert kept in para, kept
    for gate in ("certification", "`/fabrik-deploy-checklist`", "`/fabrik-release`", "Gate 2"):
        assert gate in para, gate
    for verb in ("`/fabrik-review-scoped`", "`blocked --paused`", "`start --resume-from`", "ONCE"):
        assert verb in para, verb
