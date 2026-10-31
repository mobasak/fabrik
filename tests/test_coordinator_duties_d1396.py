"""D-1396 (operator, 2026-10-31): every repo's coordinator owns four duties in writing — its tabs in
`All Agents (tabbed).bat`, the decision to dispatch a tmux builder with that builder's charter written
first, watching every builder pane continuously, and knowing every builder's NOW, DONE and NEXT from
records. The duties live in the common coordinator paragraph both contracts carry byte-identically
(D-888), so a project coordinator loads them; the hub charter keeps only its hub delta.

Pinned WHOLE: a clause-pinned prose grader let force-changing mutants through before (kaizen lesson,
2026-10-29), so the sentence is compared byte for byte, once per contract, inside the paragraph.
"""

# AFTER-EDIT: none

from __future__ import annotations

from pathlib import Path

FABRIK = Path(__file__).resolve().parents[1]
TEMPLATE_REL = "templates/governance/CLAUDE.md"
COORDINATOR_LEAD = "**The coordinator role (hub D-868, D-871).**"

BUILDERS_SENTENCE = "**Builders** (hub D-1396): the coordinator decides when a tmux builder is dispatched and, before `add`, writes and commits on the base branch the builder's charter `docs/reference/agents/<name>.md` (first line `# Agent charter`) and, where the repo has none, the role charter `docs/reference/agents/<role>.md` that `add` requires (names read `<role>-<n>`; a builder with no charter of its own gets the role one); it checks that `All Agents (tabbed).bat` lists every grid and window it runs; it watches every builder pane at every turn and every hook nudge, never by a foreground poll loop, and interacts with it — typed briefs, answered prompts, rotations; and it knows every builder's NOW, DONE and NEXT, rebuilt from records, never memory, at every start, compact and resume and before any assignment: NOW its live run record and its pane, DONE its merges and the items they closed, NEXT its queued and claimed items (`python3 /opt/fabrik/scripts/agent_status.py --repo .` shows the records; no record, or a stale one, means read the pane and ask the builder)."


def _paragraph(text: str, lead: str) -> str:
    """The one paragraph (maximal run of non-blank lines) whose first line starts with `lead`."""
    found, cur = [], []
    for line in text.splitlines() + [""]:
        if line.strip():
            cur.append(line)
            continue
        if cur and cur[0].startswith(lead):
            found.append("\n".join(cur))
        cur = []
    assert len(found) == 1, f"{len(found)} paragraphs led by {lead!r}"
    return found[0]


def _section(text: str, heading: str) -> str:
    """The body under a `## ` heading, up to the next `## ` heading."""
    lines = text.splitlines()
    starts = [
        i for i, line in enumerate(lines) if line.startswith("## ") and line.startswith(heading)
    ]
    assert len(starts) == 1, f"{len(starts)} headings starting {heading!r}"
    body = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def test_both_contracts_carry_the_builders_sentence_whole_once_in_the_coordinator_paragraph() -> (
    None
):
    for rel in ("CLAUDE.md", TEMPLATE_REL):
        text = (FABRIK / rel).read_bytes().decode("utf-8")
        assert text.count(BUILDERS_SENTENCE) == 1, f"{rel}: {text.count(BUILDERS_SENTENCE)} copies"
        assert BUILDERS_SENTENCE in _paragraph(text, COORDINATOR_LEAD), (
            f"{rel}: outside the paragraph"
        )


def test_the_never_clause_allows_the_builders_charters() -> None:
    for rel in ("CLAUDE.md", TEMPLATE_REL):
        para = _paragraph((FABRIK / rel).read_bytes().decode("utf-8"), COORDINATOR_LEAD)
        assert "beyond those status edits and its builders' charters;" in para, rel


def test_the_coordinator_charter_points_at_the_paragraph_for_awareness() -> None:
    text = (FABRIK / "docs/reference/agents/coordinator.md").read_text(encoding="utf-8")
    body = _section(text, "## Awareness")
    assert "D-1396" in body and "coordinator paragraph" in body, body
    # the definitions moved to the paragraph: a second copy here would drift from it
    for gone in ("NOW =", "DONE =", "NEXT ="):
        assert gone not in body, f"the charter still defines {gone!r}"


def test_tmux_agents_names_watching_and_dispatching_under_d1396() -> None:
    text = (FABRIK / "docs/reference/tmux-agents.md").read_text(encoding="utf-8")
    assert "D-1396" in text.split("\n## ", 1)[0], "the opening rulings list lacks D-1396"
    assert "**Watch every turn.**" in _section(text, "## Coordinator to builder")
    assert "**Dispatching a builder.**" in _section(text, "## New grids and windows")
