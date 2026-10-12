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
    """The researcher keeps the live external re-verification it alone can do (web, no shell)."""
    assert "a `fabrik-researcher` seat (web, no shell) re-verifies it" in _norm()


def test_an_out_of_surface_red_gate_is_declared_not_blocking() -> None:
    """Rows 1791335151, 1791193035, 1790986690, 1790725631, 1790295897: docs_updater --check is repo-wide."""
    text = _norm()
    assert (
        "a red whose findings name none of the reviewed docs is embedded verbatim with the one-line `GATE-SCOPE:"
        in text
    )
    assert "docs_updater --check green, or red only out-of-surface and declared" in text


def test_seat_briefs_point_at_the_probe_catalogue() -> None:
    """Rows 1791418037, 1791009623, 1790223788: the catalogue lines the review family already applies."""
    p2 = _norm()[_norm().index("### Parallelism") :]
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in p2
    )
