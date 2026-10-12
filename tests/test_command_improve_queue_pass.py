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
    """Nine rows: advisories, finding classes, other steps' output, edge cases, mechanism names, recipes, fleet artifacts."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "A sentence that describes what a script, tool or another step DOES" in p3
    assert "is executed against the real thing before the first pin and quoted as it prints" in p3
    assert "when no recipe runs, the row is routed to the script's owner instead of worded" in p3


def test_phase_five_tests_in_the_commit_shell_and_marks_only_covered_rows() -> None:
    """Rows 1791770802, 1791753412: a refused write cannot carry a red grader in; mark only coverage-checked rows."""
    p5 = _phase("## PHASE 5", "## Terminal")
    assert "Run the edit's tests after the last edit, in the shell that commits" in p5
    assert "mark only the rows PHASE 4's seats found answered in the new text" in p5
