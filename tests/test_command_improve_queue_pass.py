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


def test_phase_three_reads_what_already_governs_the_subject() -> None:
    """Rows 1791779653, 1791778642, 1791774646, 1791780696 (D-767)."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "read what already governs its subject: the target's intro and guardrails" in p3
    assert "the fragments it includes (a rule about a shared mechanism" in p3
    assert "the target's own routing rules (state the overlap)" in p3
    assert "the --help and argument handling of any script the sentence works around" in p3


def test_phase_three_runs_verbs_end_to_end_and_recipes_on_real_artifacts() -> None:
    """Rows 1791777600, 1791775906, 1791779653 (D-767): the 1024 cap is the assembler's own."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "a verb the agent is told to run end to end in a scratch repo, never the live store" in p3
    assert "a recipe on two real artifacts the command produces as well as a synthetic file" in p3
    assert "the composed skill description is refused over 1024 characters" in p3
    assert "> 1024" in (ROOT / "commands" / "assemble_commands.py").read_text()
