"""T01a — the six gate-ending command sources state their gate as a DECISION block.

WHY. Six `commands/_sources/*.md` files end a run at a human gate (design approval,
journey-freeze approval, UI-design approval, Gate 2, `/fabrik-release`'s hand-off, and
`/fabrik-deploy`'s mid-run verify-in-session suspension plus its store-surface publish
hand-off). Before this ticket, five of them told the agent only to "ask for approval" in
prose, and the sixth (`fabrik-deploy.md`) justified its suspension with "the hook exemption
is line-scoped" — a sentence the stop-and-compaction spec
(`docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md` § C2)
retires: the Stop hook's DEFERRAL check (§ C1) no longer exempts named-gate prose at all,
only a well-formed `DECISION NEEDED (ground: gate)` block or `BLOCKED:`. A command source
that still tells the agent to close a gate with plain prose is now teaching it to trip the
hook it is trying to pass.

Review round 1 added three more failure modes this file also guards: a block whose "Why it
is yours:" line names no class the hook's closed `_DECISION_GATE_RE` list accepts (the hook
refuses the block as malformed); a field left empty after its colon (same refusal); and
`fabrik-deploy.md`'s store-ending NEXT template, which can independently regress to a bare
`operator decision: <...>` with no pointer to the block above it.

Review round 2 found three of round 1's own graders too loose to prove what they claimed:
the class check matched a bare substring, so "unpublished"/"redeployed"/"suspended" would
have passed as naming "publish"/"deploy"/"spend"; the NEXT-template check matched only the
literal `operator decision: <` and missed any other bare-operator-decision NEXT phrasing;
and nothing graded round 1's own "written as plain lines, not inside a code fence" fix at
all — a source could lose that sentence and every existing test would stay green. This file
now uses word-boundary matching for the class check, flags any `NEXT:` line naming
`operator decision` without a `see DECISION NEEDED` pointer, and asserts the fence-escape
sentence precedes every block's fence.

This guards: every DECISION block in each of the six sources carries all four required
fields within 12 lines of its heading, none of those fields is empty, every block's Why
line names a closed gate class as a whole word/phrase, every block's fence is preceded
within 3 lines by the fence-escape instruction, the retired sentence does not survive
anywhere in the source corpus, and `fabrik-deploy.md` never ends a NEXT line on a bare
operator decision.
"""

from __future__ import annotations

import re
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
FIELD_ORDER: tuple[str, ...] = (
    "- Question:",
    "- Why it is yours:",
    "- Options:",
    "- Recommendation:",
)
WHY_FIELD = "- Why it is yours:"
# The ticket's own bound: "within 12 lines" of the heading.
WINDOW_LINES = 12
RETIRED_PHRASE = "the hook exemption is line-scoped"

# The Stop hook's closed `gate` class list (spec § C2, `_DECISION_GATE_RE`), matched as a
# case-insensitive WHOLE WORD/PHRASE (`\b`-bounded) against a block's "Why it is yours:"
# line — a bare substring test would pass "unpublished"/"redeployed"/"suspended" as if they
# named "publish"/"deploy"/"spend".
CLOSED_GATE_CLASSES: tuple[str, ...] = (
    "deploy",
    "destructive",
    "irreversible",
    "spend",
    "cross-repo",
    "publish",
    "credentials",
    "design approval",
    "plan approval",
    "gate 1",
    "gate 2",
    "production data",
)


def _read_lines(source_name: str) -> list[str]:
    return (SOURCES_DIR / source_name).read_text(encoding="utf-8").splitlines()


def _heading_indices(lines: list[str]) -> list[int]:
    """Every line index in `lines` that carries the DECISION heading (a file may have more
    than one gate-ending block — `fabrik-deploy.md` has two: the mid-run suspension and the
    store-ending publish hand-off; its Termination-contract summary only NAMES the block by
    reference and carries no heading of its own, so it is not counted here)."""
    return [i for i, line in enumerate(lines) if DECISION_HEADING in line]


def _window(lines: list[str], heading_idx: int) -> list[str]:
    return lines[heading_idx : heading_idx + 1 + WINDOW_LINES]


def _field_line(window: list[str], field: str) -> str:
    """Return the first line in `window` carrying `field`, or "" if none does."""
    return next((line for line in window if field in line), "")


@pytest.mark.parametrize("source_name", GATE_SOURCES)
def test_source_states_its_gate_as_a_decision_block(source_name: str) -> None:
    lines = _read_lines(source_name)
    heading_indices = _heading_indices(lines)
    assert heading_indices, (
        f"{source_name} has no '{DECISION_HEADING}' heading — "
        "the gate must be stated as a DECISION block, not prose"
    )
    for heading_idx in heading_indices:
        window_text = "\n".join(_window(lines, heading_idx))
        missing = [field for field in FIELD_ORDER if field not in window_text]
        assert not missing, (
            f"{source_name} (block at line {heading_idx + 1}): missing {missing} within "
            f"{WINDOW_LINES} lines of '{DECISION_HEADING}'"
        )


@pytest.mark.parametrize("source_name", GATE_SOURCES)
def test_no_decision_field_is_empty(source_name: str) -> None:
    lines = _read_lines(source_name)
    for heading_idx in _heading_indices(lines):
        window = _window(lines, heading_idx)
        for field in FIELD_ORDER:
            field_line = _field_line(window, field)
            assert field_line, (
                f"{source_name} (block at line {heading_idx + 1}): '{field}' not found "
                f"within {WINDOW_LINES} lines"
            )
            value = field_line.split(field, 1)[1].strip()
            assert value, (
                f"{source_name} (block at line {heading_idx + 1}): '{field}' has no "
                "content after its colon"
            )


@pytest.mark.parametrize("source_name", GATE_SOURCES)
def test_why_line_names_a_closed_gate_class(source_name: str) -> None:
    lines = _read_lines(source_name)
    for heading_idx in _heading_indices(lines):
        window = _window(lines, heading_idx)
        why_line = _field_line(window, WHY_FIELD)
        assert why_line, (
            f"{source_name} (block at line {heading_idx + 1}): no '{WHY_FIELD}' line "
            f"within {WINDOW_LINES} lines"
        )
        matched = [
            cls
            for cls in CLOSED_GATE_CLASSES
            if re.search(r"\b" + re.escape(cls) + r"\b", why_line, re.IGNORECASE)
        ]
        assert matched, (
            f"{source_name} (block at line {heading_idx + 1}): '{WHY_FIELD}' line names "
            f"no class from the hook's closed list — {why_line.strip()!r}"
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


def test_deploy_next_template_never_ends_on_a_bare_operator_decision() -> None:
    lines = _read_lines("fabrik-deploy.md")
    offending = [
        line.strip()
        for line in lines
        if line.strip().startswith("NEXT:")
        and "operator decision" in line
        and "see DECISION NEEDED" not in line
    ]
    assert not offending, (
        "fabrik-deploy.md: a NEXT: line names an operator decision with no pointer to the "
        f"DECISION block above it: {offending}"
    )


def _fence_open_index(lines: list[str], heading_idx: int) -> int | None:
    """The line index of the ``` that opens the fence a DECISION block at `heading_idx`
    lives inside — the nearest bare ``` line above it — or None if none exists."""
    for i in range(heading_idx - 1, -1, -1):
        if lines[i].strip() == "```":
            return i
    return None


@pytest.mark.parametrize("source_name", GATE_SOURCES)
def test_fence_is_preceded_by_the_escape_instruction(source_name: str) -> None:
    lines = _read_lines(source_name)
    for heading_idx in _heading_indices(lines):
        fence_idx = _fence_open_index(lines, heading_idx)
        assert fence_idx is not None, (
            f"{source_name} (block at line {heading_idx + 1}): no fence-open line found "
            "above the DECISION heading"
        )
        lead_in = " ".join(
            line.strip() for line in lines[max(0, fence_idx - 3) : fence_idx]
        )
        assert "not inside a code fence" in lead_in, (
            f"{source_name} (fence at line {fence_idx + 1}): the 3 lines before it do not "
            "say 'not inside a code fence' — an agent copying the fence verbatim into its "
            "own output would hide the block from the Stop hook's extractor"
        )
