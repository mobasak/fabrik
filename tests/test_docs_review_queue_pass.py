"""/fabrik-docs-review feedback queue answered in one pass (D-735): the seat that can run a command, the gate scope.

The seat test renders the floor and reads the agent's own tool list, so the claim is executed, not spelled.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-docs-review.md"
sys.path.insert(0, str(ROOT / "commands"))

import assemble_commands as ac  # noqa: E402


def _norm() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def test_the_docs_review_floor_seat_can_run_the_commands_the_text_orders() -> None:
    """Rows 1791450604, 1789580660: Phase 2 verifies a runnable example by RUNNING it; the floor seat needs Bash."""
    floor = ac.PARAMS["fabrik-docs-review"]["subagents-core"]["FLOOR"]
    seat = re.search(r"native `([a-z-]+)`", floor).group(1)
    agent = (ROOT / "commands" / "_agents" / f"{seat}.md").read_text()
    disallowed = re.search(r"^disallowedTools:(.*)$", agent, re.M)
    assert not (disallowed and "Bash" in disallowed.group(1)), seat
    assert "verified by RUNNING it" in _norm()


def test_external_claims_go_to_the_web_seat() -> None:
    """The researcher keeps the live external re-verification it alone can do, as its own workflow slice."""
    assert (
        "a `fabrik-researcher` seat (web, no shell) — a unit of its own, the workflow slice's `agent`"
        in _norm()
    )


def test_an_out_of_surface_red_gate_is_declared_not_blocking() -> None:
    """Rows 1791335151, 1791193035, 1790986690, 1790725631, 1790295897: docs_updater --check is repo-wide."""
    text = _norm()
    assert "a red none of whose findings the change under review caused" in text
    assert "the doc-sync gate green, or red only out-of-surface and declared" in text
    # every sentence that states the terminal or the convergence bar allows the declared red
    assert (
        "md5 unchanged) with the doc-sync gate green, or red only out-of-surface and declared"
        in text
    )
    assert (
        "+ the gate green (or its out-of-surface red embedded with the `GATE-SCOPE` line)" in text
    )


def test_seat_briefs_and_the_orchestrator_apply_the_probe_catalogue() -> None:
    """Rows 1791418037, 1791009623: the catalogue binds the seats' briefs and the orchestrator's own doc edits."""
    p2 = _norm()[_norm().index("### Parallelism") :]
    assert (
        "Every seat brief, and the orchestrator's own doc edits, apply the lines of "
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in p2
    )


def test_the_verdict_table_says_how_each_researcher_only_verdict_is_treated() -> None:
    """W-21b629ed (intel mail 01M5AQ4754, D-1056): the fabrik-researcher agent returns INFERENCE and NEEDS-RAW-FETCH,
    which the docs review's verdict table had no row for. Each now has one, and every verdict the agent names, in its
    Return line and in Method step 4's list, has a row, so a new agent verdict with no table row fails here. Both
    resolve into the other rows (a live-checkable claim is VERIFIED-or-WRONG), so neither has a self-audit count, and
    only the orchestrator curls."""
    src = _norm()
    table = src[src.index("### Verdict taxonomy") : src.index("A seat's return cites")]
    rows = set(re.findall(r"\| \*\*([A-Za-z0-9_-]+)\*\* \|", table))
    agent = (ROOT / "commands" / "_agents" / "fabrik-researcher.md").read_text()
    line = re.search(r"`<claim> → ([^ `]+) ·", agent)
    assert line, "the agent's Return line moved"
    returned = set(line.group(1).split("|"))
    step4 = agent[agent.index("4. **Report a verdict**") : agent.index("5. **Freshness binds:**")]
    leads = re.findall(r"^\s+- (.+?) —", step4, re.M)
    listed = {name for lead in leads for name in re.findall(r"`([A-Za-z0-9_-]+)`", lead)}
    assert listed == returned, sorted(listed ^ returned)
    assert returned <= rows, sorted(returned - rows)
    assert "rewrite the claim to what a source line states and re-verify it" in table
    assert "The orchestrator curls the named URL and section (a seat never curls)" in table
    assert "not live-checkable, so it is UNVERIFIABLE, naming what a human should check" in table
    assert "/ DEAD-removed / UNVERIFIABLE)" in src
