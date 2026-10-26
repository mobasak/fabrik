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


def test_the_verdict_table_says_how_each_researcher_only_verdict_is_treated() -> None:
    """W-21b629ed (intel mail 01M5AQ4754, D-1056): every verdict the fabrik-researcher agent names, in its Return line and
    in Method step 4's list, has a row in the docs review's verdict table, so a new agent verdict with no row fails here.
    The pinned prose of those rows moved to the ledger (commands/_rules/fabrik-docs-review.yaml)."""
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
