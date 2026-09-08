"""D-192 — the assembler grades D-191: a rendered command that fans out must carry the dispatch step.

The rule multiplied fleet spend with zero graders (the D-191 review's Opus seat: `grep -rn
dispatch_headroom scripts/enforcement/ .claude/hooks/` printed nothing; 0 of 97 recorded rounds
carried `--seats`). `dispatch_step_gaps` is the cheapest real one — measured on the 36 rendered
commands before it shipped: 27 fan out and carry the step, 3 fanned out without it, 6 are serial by
design and match neither, 0 false positives. And the judgement-kind floors (grounding, adjudication)
name no Haiku seat: a judgement unit has no grep-able angle.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ac", REPO / "commands" / "assemble_commands.py")
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)

STEP = (
    "**Dispatch step (D-191):** run `dispatch_headroom.py --units <N>` and dispatch what it prints."
)


def test_a_command_that_fans_out_without_the_dispatch_step_is_a_gap():
    rendered = {
        "fans-out-covered": "dispatch one seat per screen, all in a single message. " + STEP,
        "fans-out-bare": "dispatch **one `fabrik-reviewer` seat per claim, all in a single message**.",
        "fans-out-verb": "Finders are dispatched together in ONE message so they run in parallel.",
        "serial-by-design": "Walk the checklist yourself; no subagent is dispatched here.",
        # "seats per" in prose about cost is not a fan-out (round-4: the branch was untethered)
        "prose-only": "Fewer seats per round drops recall; the seat per group ratio is a budget matter.",
        "step-no-fanout": "THE DISPATCH STEP (D-191, binding on every fan-out): …",
        # the named-unit branch alone: no "seat", no "dispatch" — one reader per file
        "fans-out-named": "Run one `fabrik-reviewer` per file, all in ONE message; merge the union.",
        # a step that survives only inside a POOL-OFF comment does not cover the live text
        "fans-out-masked": "one seat per claim, all in a single message. <!-- POOL OFF: "
        + STEP
        + " -->",
    }
    assert ac.dispatch_step_gaps(rendered) == [
        "fans-out-bare",
        "fans-out-masked",
        "fans-out-named",
        "fans-out-verb",
    ]


def test_the_live_corpus_has_no_gap_and_the_detector_fires_on_real_fan_outs(tmp_path):
    """Executed on the rendered corpus, not asserted from the source list: every command that fans
    out carries the step, and the detector is not wallpaper — it fires on the real fan-outs."""
    ac.render(tmp_path, tmp_path / "_skills", agents_dest=tmp_path / "_agents")
    rendered = {f.stem: f.read_text() for f in tmp_path.glob("*.md")}
    assert len(rendered) >= 30
    assert ac.dispatch_step_gaps(rendered) == []
    fan = [n for n, t in rendered.items() if ac._FANOUT_RE.search(t)]
    assert len(fan) >= 25, fan  # 30 of 36 when this shipped
    assert {"fabrik-review", "design-review", "fabrik-rivals", "fabrik-upstream"} <= set(fan)


def test_judgement_floors_name_no_haiku_seat_and_review_floors_name_a_class_wide_one():
    grounding = ac._floor("grounding", "`fabrik-researcher`")
    review = ac._floor("review", "`fabrik-reviewer`")
    assert "no mechanical seat" in grounding and "--mechanical 0" in grounding
    assert "haiku" not in grounding.lower()
    # both judgement kinds — dropping "adjudication" from the set reopened F27 unnoticed (round 4)
    adjudication = ac._floor("adjudication", "`fabrik-reviewer`")
    assert "an adjudication unit" in adjudication and "haiku" not in adjudication.lower()
    assert "one Haiku mechanical seat per INDEPENDENT unit" in review
    assert "sweeps ONE grep-able class across every unit" in review
