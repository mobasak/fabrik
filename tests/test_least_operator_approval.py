"""W-4a03df79 (D-1110, D-1122) — least operator approval: the gate model the contracts and the deploy chain state.

WHY. D-1110 (operator, 2026-10-21/22) moves every gate class a coordinator can validate to the Opus + Fable panel and
keeps for the operator only the classes it names: public publishing, spend above the ceiling, recurring contracts,
operator-minted credentials and acts, and unbacked deletion, plus every spend while the ceiling is 0 and every
irreversible act. A block the operator keeps carries the label `operator-kept: <token>` on its Why line, which the
Stop hook reads (Phase B). Each test pins one Behaviour Contract row (A1-A7) of
`docs/development/plans/2026-10-22-plan-1-least-operator-approval.md`; dropping its clause turns that test red.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HUB = "CLAUDE.md"
TEMPLATE = "templates/governance/CLAUDE.md"
CONTRACTS = (HUB, TEMPLATE)
GATE_HEAD = "Name exactly ONE ground in the heading."
DEPLOY_SOURCES = (
    "commands/_sources/fabrik-deploy.md",
    "commands/_sources/fabrik-deploy-plan-review.md",
    "commands/_sources/fabrik-release.md",
    "commands/_fragments/deploy-chain.md",
)


def _norm(text: str) -> str:
    return " ".join(text.split())


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _line(rel: str, head: str) -> str:
    """The one line of `rel` that opens with `head` (a paragraph is one line in both contracts)."""
    lines = [ln for ln in _read(rel).splitlines() if ln.startswith(head)]
    assert len(lines) == 1, f"{rel}: {len(lines)} lines open with {head!r}"
    return lines[0]


def _between(rel: str, start: str, end: str) -> str:
    text = _read(rel)
    i = text.index(start)
    return text[i : text.index(end, i)]


def _next_map() -> dict[str, str]:
    src = _read("commands/assemble_commands.py")
    return dict(
        re.findall(r'^\s+"(fabrik-release|fabrik-deploy-plan-review)":\s*"([^"]*)",', src, re.M)
    )


@pytest.mark.parametrize("rel", CONTRACTS)
def test_a1_the_gate_ground_names_the_panel_decided_classes(rel: str) -> None:
    para = _norm(_line(rel, GATE_HEAD))
    for phrase in (
        "each class a coordinator can validate is first answered by the Opus + Fable panel in the operator's place",
        "design and plan approval (the design-gate review commands dispatch it), Gate 1, Gate 2 to our own VPS",
        "a destructive act on a branch, worktree, scratch area, test repo or old volume with a verified backup first",
        "a production-data window that dumps first and keeps the old volume",
        "credentials the fleet mints itself (database roles, tokens, service accounts) with a backup and a rollback",
        "publishing to our own surfaces",
        "and only a split panel reaches the operator, its block carrying the `Panel:` line",
    ):
        assert phrase in para, f"{rel}: missing {phrase!r}"
    assert "design approval is first answered" not in para


@pytest.mark.parametrize("rel", CONTRACTS)
def test_a2_the_gate_ground_names_the_operator_kept_label(rel: str) -> None:
    para = _norm(_line(rel, GATE_HEAD))
    for phrase in (
        "such a block's Why line carries its class token and the label `operator-kept:` with one of",
        "`public` (publishing to customers or the public, a customer-facing production deploy included)",
        "`above-ceiling` (spend above the operator's ceiling)",
        "`recurring` (any recurring contract)",
        "`operator-minted` (credentials, or an act at a third-party dashboard, email verification or payment provider,"
        " only the operator can perform)",
        "`unbacked` (deleting data with no backup)",
        "every spend stays the operator's while that ceiling is 0, and every irreversible act always, label or not",
        "A target is customer-facing when its service spec says `is_public: true` and its users are not us",
        "A design or plan approval is the panel's whatever it names, and it never approves the spend",
        "A builder's block reaches the operator only through its coordinator.",
    ):
        assert phrase in para, f"{rel}: missing {phrase!r}"
    example = _norm(_between(rel, "Legitimate:", "Refused (a manufactured"))
    assert (
        "- Why it is yours: deploy — Gate 2, operator-kept: public — a customer-facing production deploy."
        in example
    )
    assert "a destructive/irreversible action needing authorisation" not in example


def test_a3_autonomy_and_the_coordinator_escalation_name_the_panel() -> None:
    autonomy = _norm(_line(HUB, "**Autonomy — the hub's agents"))
    for phrase in (
        "`owned` stays the operator's, and so do the gate classes § FINAL OUTPUT keeps for the operator (D-1110",
        "a coordinator validates its two reports against the repo and the box before acting on them",
        "A seat that finds the act is one § FINAL OUTPUT keeps for the operator answers `operator-kept: <token>`, never"
        " an approval",
        "A coordinator asks the operator a clarifying question only when the answer materially changes the work and"
        " the repo is silent",
        "an act Claude Code's auto-mode classifier still refuses after a panel approved it goes to the operator once"
        " per class",
    ):
        assert phrase in autonomy, f"missing {phrase!r}"
    assert "`gate` and `owned` stay the operator's" not in autonomy
    for rel in CONTRACTS:
        role = _norm(_line(rel, "**The coordinator role ("))
        assert "a gate (deploy, destructive, spend, credentials) → the operator" not in role, rel
        assert (
            "a gate → the Opus + Fable panel, or, when § FINAL OUTPUT keeps it for the operator, the operator (D-1110)"
            in role
        ), rel


def test_a4_the_two_gate_paragraphs_are_twins() -> None:
    hub = _line(HUB, GATE_HEAD).replace("kept whole from D-054:", "kept whole from hub D-054:")
    assert hub == _line(TEMPLATE, GATE_HEAD)


def test_a5_the_template_hub_request_bullet_sends_a_gate_to_the_panel() -> None:
    bullet = _norm(
        _between(
            TEMPLATE, "- **⚠️ A request from the HUB carries the operator's authority**", "\n- **"
        )
    )
    assert (
        "every gate on the `ground: gate` closed list in § FINAL OUTPUT still goes to the panel, or to the operator"
        " through your coordinator when § FINAL OUTPUT keeps it for the operator" in bullet
    )
    assert (
        "a builder that cannot dispatch the panel hands the gate to its coordinator, who dispatches it"
        in bullet
    )
    assert "closed list in § FINAL OUTPUT still goes to the operator" not in bullet


def test_a6_the_deploy_chain_names_the_panels_go() -> None:
    texts = {rel: _norm(_read(rel)) for rel in DEPLOY_SOURCES}
    texts.update({f"NEXT[{k}]": _norm(v) for k, v in _next_map().items()})
    assert len(texts) == len(DEPLOY_SOURCES) + 2, sorted(texts)
    for name, text in texts.items():
        for old in (
            "the operator's explicit go",
            "Gate 2 — human approval",
            "the operator explicitly dispatched",
            'an explicit "go"',
        ):
            assert old not in text, f"{name}: still holds {old!r}"
        assert not re.search(r"(?i)operator[- ]dispatched(?! on a gate 2 go)", text), (
            f"{name}: operator-dispatched"
        )
    for rel in DEPLOY_SOURCES:
        assert "panel" in texts[rel], f"{rel}: names no panel go"
        assert "customer-facing" in texts[rel], f"{rel}: names no customer-facing case"
    assert "only the human takes" not in texts["commands/_sources/fabrik-release.md"]
    review = texts["commands/_sources/fabrik-deploy-plan-review.md"]
    assert "`PANEL APPROVED (<plan path>)`" in review
    split_why = "- Why it is yours: Gate 2 — the panel split on a deploy to our own VPS, its `Panel:` line below."
    assert split_why in review
    for name, text in texts.items():
        for why in re.findall(r"- Why it is yours: [^-]*?panel split[^\n]*?(?= - Options:)", text):
            assert "operator-kept:" not in why, f"{name}: a split Why line carries the label"
    assert (
        "- Why it is yours: deploy — operator-kept: operator-minted — the plan's OPERATOR-GATE step, an act at a third"
        " party only the operator can perform." in texts["commands/_sources/fabrik-deploy.md"]
    )


def test_a7_the_design_gate_panel_fragment_cites_d1110() -> None:
    frag = _norm(_read("commands/_fragments/design-gate-panel.md"))
    assert "widened to every gate class a coordinator can validate by D-1110" in frag
    assert (
        "A seat that finds the act is one the operator keeps answers `operator-kept: <token>`, never an approval."
        in frag
    )
    assert "for design approval only" not in frag
    assert "stay the operator's" not in frag
