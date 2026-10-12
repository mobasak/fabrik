"""/fabrik-command-improve feedback queue answered in one pass (D-735): execute what a new sentence says a script does.

Each test pins one sentence in the phase that owns it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-command-improve.md"


def _phase(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_phase_three_executes_what_a_new_sentence_says_a_script_does() -> None:
    """Eight rows: advisories, finding strings, other steps' output, edge cases, mechanism names, recipes, fleet artifacts."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "A sentence that describes what a script, tool or another step DOES" in p3
    assert "is executed on the scenario the sentence states before PHASE 4's review and quoted as it prints" in p3
    assert "a mechanism name it cites is grepped in the hub and dropped when nothing matches" in p3
    # the no-recipe route is a mail to the owning beat, the routing PHASE 2 and the charter use
    assert "the row is mailed to the beat that owns the script" in p3
    assert "routed to the script's owner" not in p3


def test_phase_five_tests_before_the_commit_and_marks_only_covered_rows() -> None:
    """Rows 1791770802, 1791753412: tests run before the commit, and trailer + marks name only rows PHASE 4 found answered."""
    p4 = _phase("## PHASE 4", "## PHASE 5")
    assert "for each row it finds answered, it returns the line that states the row's step" in p4
    p5 = _phase("## PHASE 5", "## Terminal")
    run = p5.index("Run the edit's tests after the last edit, in the shell that commits")
    assert run < p5.index("Agent-Role: primary") < p5.index("Then MARK the rows answered")
    assert "The trailer's `rows` and the `--mark-answered` list below name the same rows" in p5
