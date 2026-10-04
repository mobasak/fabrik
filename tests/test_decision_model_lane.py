"""Pins the decision-model lane across the four rule packs that carry it (D-527).

A typed decision model (TypeSafe's Jev, reached through fabrik-lib's `decision-gate`) may take a closed-answer decision
that would otherwise go to the `claude -p` ladder. The rule lives once, in ai/00's dispatch ladder; ai/50, ai/80 and
core/65 point at it for their own shapes. Five things can go false with no other gate red:

1. ai/00 names the lane inside its dispatch ladder, lists all six conditions with the clause that carries each one's
   force, and points at it from the binding subscription-first paragraph and from its anti-patterns.
2. The lane is wired only through `decision-gate`, which a project copies in with the change that wires its first
   consumer (never ahead of one), and that consumer stays off until the egress condition (criterion 6) is met.
3. The safety clauses hold: abstention is built in, thresholds are calibrated on held-out data, pilots run in shadow
   first, and a decision model is never the only guard on an irreversible act.
4. ai/50 allows typed gates only to tighten a loop, ai/80 keeps a human or rule on irreversible removals, and core/65
   adds the relevance gate only with a measured lift.
5. Every cited artifact exists (the hub map, the egress work item), and the new text carries no version literal in any
   shape — the detector is the one `tests/test_vision_pack.py` defines.

Guards read emphasis-stripped, whitespace-collapsed text and pin the force clause, not only the subject, so a reversed
verb fails. The cheapest way past (1) is a condition reworded so the guard's phrase survives with the opposite meaning;
the review reads the sentence, and each guard's phrase includes the verb.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
AI00 = RULES / "ai" / "00-ai-model-selection.md"
AI50 = RULES / "ai" / "50-agentic.md"
AI80 = RULES / "ai" / "80-specialized-domains.md"
CORE65 = RULES / "core" / "65-rag-search.md"
HUB_MAP = ROOT / "docs" / "reference" / "jev-decision-model-map.md"
EGRESS_ITEM = ROOT / ".fabrik" / "work" / "W-5e7743d9.json"


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _lane() -> str:
    text = AI00.read_text(encoding="utf-8")
    start = text.index("\n### Closed-answer decisions — the decision-model lane\n")
    end = text.find("\n## ", start + 1)
    return _plain(text[start : end if end != -1 else len(text)])


def _ladder() -> str:
    text = AI00.read_text(encoding="utf-8")
    start = text.index("\n## In-code AI agent calls — the dispatch ladder (BINDING)\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_lane_sits_inside_the_dispatch_ladder() -> None:
    assert "### Closed-answer decisions — the decision-model lane" in _ladder(), (
        "the decision-model lane left ai/00's dispatch ladder section"
    )
    lane = _lane()
    assert "runs on the ladder above by default" in lane, "the lane no longer says the ladder is the default"
    assert "only when all six hold" in lane, "the lane no longer requires all six conditions"


def test_six_conditions_carry_their_force() -> None:
    lane = _lane()
    for phrase in (
        "number at most about 25; beyond that, split the question into stages",
        "stays inside the model's input budget",
        "runs on every message, request or agent turn, or drains a backlog, or it replaces a regex",
        "a confidence threshold sends the uncertain answer to the fallback",
        "the model returns probabilities, never a reason",
        "a data class the project's owner has ruled may go to TypeSafe",
        "until that ruling exists the lane is not wired for that class",
        "customer text needs that ruling first",
    ):
        assert phrase in lane, f"a lane condition lost its force clause: {phrase!r}"


def test_wired_only_through_decision_gate_vendored_with_its_first_consumer() -> None:
    lane = _lane()
    assert "only through fabrik-lib's decision-gate module, never a hand-rolled client" in lane
    assert "a project copies it in with the change that wires its first consumer, never ahead of one" in lane, (
        "the lane no longer ties vendoring the module to wiring a consumer"
    )
    assert "that consumer stays off until criterion 6 is met" in lane, (
        "the lane no longer holds a wired consumer behind the egress criterion"
    )


def test_safety_clauses() -> None:
    lane = _lane()
    for phrase in (
        "deterministic rules decide first",
        "every question carries an explicit insufficient option, because the model never abstains",
        "calibrated per decision on the project's own labelled data, scored on a held-out split",
        "everything under the threshold falls back to the ladder above",
        "runs in shadow mode first and is armed only when its wrong-allow rate is no worse",
        "Never make a decision model the only guard on an irreversible act",
        "never judge quality or compliance with it",
        "never ask it to count, compare dates or do arithmetic",
    ):
        assert phrase in lane, f"a lane safety clause is gone or reversed: {phrase!r}"


def test_ai00_points_at_the_lane_from_binding_and_anti_patterns() -> None:
    text = _plain(AI00.read_text(encoding="utf-8"))
    assert "may take that section's decision-model lane instead, and only when its six conditions hold" in text, (
        "the subscription-first paragraph no longer routes closed-answer decisions to the lane's conditions"
    )
    assert (
        "Asking a general LLM for one label on a hot path the decision-model lane covers, or making a decision model "
        "the only guard on an irreversible act" in text
    ), "the lane's anti-pattern is gone from ai/00"


def test_ai50_typed_gates_only_tighten() -> None:
    text = _plain(AI50.read_text(encoding="utf-8"))
    assert "Typed gates inside a loop." in text
    assert "ai/00's decision-model lane may take it when its six conditions hold" in text
    assert "Such a gate only tightens what the loop allows" in text, "ai/50 no longer limits typed gates to tightening"
    assert "allowed_tools, disallowed_tools and dontAsk stay the permission boundary" in text
    assert "is never the only thing between the agent and an irreversible act" in text


def test_ai80_moderation_never_the_only_guard() -> None:
    text = _plain(AI80.read_text(encoding="utf-8"))
    assert "may run in ai/00's decision-model lane, through fabrik-lib's decision-gate" in text
    assert "A human or a deterministic rule still owns any removal that cannot be undone" in text
    assert "so it is never the only guard" in text, "ai/80 no longer forbids a decision model as the only guard"


def test_core65_relevance_gate_needs_a_measured_lift() -> None:
    raw = CORE65.read_text(encoding="utf-8")
    text = _plain(raw)
    # the row ALONE — the re-ranker row below says "Only with a measured lift" too, and must not satisfy this guard
    row = _plain(next((ln for ln in raw.splitlines() if ln.startswith("| **Relevance gate** (optional) |")), ""))
    assert row, "core/65 lost its relevance-gate row"
    assert "ai/00's decision-model lane (fabrik-lib decision-gate, copied in by the change that wires the gate)" in row
    assert "Only with a measured lift" in row, "core/65's relevance gate is no longer gated on a measured lift"
    assert "a closed label set at volume may take ai/00's decision-model lane instead" in text


def test_cited_artifacts_exist() -> None:
    assert HUB_MAP.exists(), f"the lane cites {HUB_MAP.relative_to(ROOT)}, which is gone"
    assert EGRESS_ITEM.exists(), "the lane cites the egress question W-5e7743d9, whose work item is gone"
    for pack in (AI00, AI80, CORE65):
        assert "/opt/fabrik/docs/reference/jev-decision-model-map.md" in pack.read_text(encoding="utf-8")


def test_no_version_literals_in_the_new_text() -> None:
    spec = importlib.util.spec_from_file_location("vision_pack", ROOT / "tests" / "test_vision_pack.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    new_text = " ".join(
        [
            _lane(),
            _plain(AI50.read_text(encoding="utf-8")).split("Typed gates inside a loop.")[1].split("Reasoning depth")[0],
            _plain(AI80.read_text(encoding="utf-8")).split("A moderation, spam or prompt-injection check")[1],
            _plain(CORE65.read_text(encoding="utf-8")).split("| Relevance gate (optional) |")[1].split("\n")[0][:600],
        ]
    )
    found = mod.VERSION_RE.findall(new_text)
    assert not found, f"version literals in the decision-model lane text: {found}"


def test_egress_wording_matches_the_work_item_state() -> None:
    """The lane must call the hub's egress question open exactly while its work item is unanswered."""
    import json

    status = json.loads(EGRESS_ITEM.read_text(encoding="utf-8")).get("status", "")
    lane = _lane()
    says_open = "In the hub the question is still open (hub work item W-5e7743d9)" in lane
    if status in ("awaiting-operator", "open", "ready", "claimed"):
        assert says_open, f"W-5e7743d9 is {status!r}, but the lane no longer says the hub's egress question is open"
    else:
        assert not says_open, f"W-5e7743d9 is {status!r}: re-word the lane to the operator's ruling"
    assert "the hub's ruling is W-5e7743d9" not in lane, "the lane calls an unanswered work item a ruling"
