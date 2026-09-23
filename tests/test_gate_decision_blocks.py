"""T01a — the six gate-ending command sources state their gate as a DECISION block.

WHY. Six `commands/_sources/*.md` files end a run at a human gate (design approval,
journey-freeze approval, UI-design approval, Gate 2, `/fabrik-release`'s hand-off, and
`/fabrik-deploy`'s mid-run verify-in-session suspension). Before this ticket, five of them
told the agent only to "ask for approval" in prose, and the sixth (`fabrik-deploy.md`)
justified its suspension with "the hook exemption is line-scoped" — a sentence the
stop-and-compaction spec (`docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md`
§ C2) retires: the Stop hook's DEFERRAL check (§ C1) no longer exempts named-gate prose at
all, only a well-formed `DECISION NEEDED (ground: gate)` block or `BLOCKED:`. A command
source that still tells the agent to close a gate with plain prose is now teaching it to
trip the hook it is trying to pass.

This guards two things: every one of the six sources carries the block's four required
fields near its `DECISION NEEDED (ground: gate)` heading, and the retired sentence does not
survive anywhere in the rendered-from source corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = REPO_ROOT / "commands" / "_sources"

GATE_SOURCES: tuple[str, ...] = (
    "fabrik-spec-review.md",
    "fabrik-flows-review.md",
    "fabrik-ui-design-review.md",
    "fabrik-deploy-plan-review.md",
    "fabrik-release.md",
    "fabrik-deploy.md",
)

DECISION_HEADING = "DECISION NEEDED (ground: gate)"
REQUIRED_FIELDS: tuple[str, ...] = (
    "- Question:",
    "- Why it is yours:",
    "- Options:",
    "- Recommendation:",
)
# The ticket's own bound: "within 12 lines" of the heading.
WINDOW_LINES = 12
RETIRED_PHRASE = "the hook exemption is line-scoped"


def _read_lines(source_name: str) -> list[str]:
    return (SOURCES_DIR / source_name).read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("source_name", GATE_SOURCES)
def test_source_states_its_gate_as_a_decision_block(source_name: str) -> None:
    lines = _read_lines(source_name)
    heading_idx = next(
        (i for i, line in enumerate(lines) if DECISION_HEADING in line), None
    )
    assert heading_idx is not None, (
        f"{source_name} has no '{DECISION_HEADING}' heading — "
        "the gate must be stated as a DECISION block, not prose"
    )
    window_text = "\n".join(lines[heading_idx : heading_idx + 1 + WINDOW_LINES])
    missing = [field for field in REQUIRED_FIELDS if field not in window_text]
    assert not missing, (
        f"{source_name}: missing {missing} within {WINDOW_LINES} lines of "
        f"'{DECISION_HEADING}'"
    )


def test_no_source_still_says_the_hook_exemption_is_line_scoped() -> None:
    offenders = [
        path.name
        for path in sorted(SOURCES_DIR.glob("*.md"))
        if RETIRED_PHRASE in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"the retired sentence still appears in: {offenders} — "
        "it is rewritten per spec § C1/C2 (T01a)"
    )
