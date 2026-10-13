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
    assert (
        "is executed on the scenario the sentence states before PHASE 4's review and quoted as it prints"
        in p3
    )
    assert "a mechanism name it cites is grepped in the hub and dropped when nothing matches" in p3
    # the no-recipe route is a mail to the owning beat, the routing PHASE 2 and the charter use
    assert "the row is mailed to the beat that owns the script" in p3
    assert "routed to the script's owner" not in p3


def test_phase_five_tests_before_the_commit_and_marks_only_covered_rows() -> None:
    """Rows 1791770802, 1791753412: tests run before the commit, and trailer + marks name only rows PHASE 4 found answered."""
    p4 = _phase("## PHASE 4", "## PHASE 5")
    assert "for each row it finds answered, it returns the line that states the row's step" in p4
    p5 = _phase("## PHASE 5", "## Terminal")
    run = p5.index(
        "Run the edit's tests — the queue-pass test plus every test file that names the edited source"
    )
    assert "after the last edit, in the shell that commits" in p5
    assert run < p5.index("Agent-Role: primary") < p5.index("Then MARK the rows answered")
    assert "The trailer's `rows` and the `--mark-answered` list below name the same rows" in p5


def test_phase_three_reads_what_already_governs_the_subject() -> None:
    """Rows 1791779653, 1791778642, 1791774646, 1791780696 (D-767)."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "read what already governs its subject: the target's intro and guardrails" in p3
    assert (
        "the fragments it includes (§ Drive's consistency rule says where a shared rule lives)"
        in p3
    )
    assert "the target's own routing rules (state the overlap)" in p3
    assert "the --help and argument handling of any script the sentence works around" in p3


def test_phase_three_runs_verbs_end_to_end_and_recipes_on_real_artifacts() -> None:
    """Rows 1791777600, 1791775906 (D-767): a sentence that tells the agent to run a verb is bound too."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert (
        "or tells the agent to run one of its verbs is executed on the scenario the sentence states"
        in p3
    )
    assert (
        "is run on a real artifact the command produces and on two fleet ones as well as a synthetic file"
        in p3
    )
    assert (
        "a verb is run end to end in a scratch repo, never on the repo's own work store or mailbox"
        in p3
    )


def test_phase_five_runs_every_test_that_names_the_edited_source() -> None:
    """Row 1791830357 (D-790): fabrik-task.md's size cap and verbatim pins sit in a test the queue-pass test is not."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    assert (
        "every test file that names the edited source or fragment, or a command that includes that fragment (`command grep -rl --include=*.py <each name> tests/`), since a size cap or a sentence pinned verbatim is invisible from the source"
        in text
    )
    import subprocess

    found = subprocess.run(
        ["grep", "-rl", "--include=*.py", "fabrik-task.md", "tests/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert "tests/test_fabrik_task_source.py" in found
    assert not [p for p in found if not p.endswith(".py")]


def test_phase_three_reads_the_executor_the_fan_out_and_every_branch() -> None:
    """Rows 1791845066, 1791846266, 1791847237: three edits each cost a review round on one of these."""
    text = " ".join(_phase("## PHASE 3", "## PHASE 4").split())
    assert (
        "its fan-out paragraph and the section whose executor — lead, seat or fixer — acts on the sentence"
        in text
    )
    assert "every branch the sentence's subject can bind" in text


def test_a_fragment_edit_names_its_by_path_consumers_too() -> None:
    """Row 1791892288: the probe catalogue is never included, only named, so an include-only consumer list found none
    and missed the review commands that point at it. The rule lives in PHASE 3, and its recipe runs here: by-path
    pointers, a fragment that names another, and the includers too."""
    import subprocess

    p3 = re.sub(r"\s+", " ", _phase("## PHASE 3", "## PHASE 4"))
    assert (
        "a `_fragments/` edit names each `{{include:}}` consumer with its bound placeholders, and each source or"
        " fragment that names it (`command grep -rlw <its file name without .md> commands/_sources"
        " commands/_fragments`, which lists the includers too; `test_a_fragment_edit_names_its_by_path_consumers_too`"
        " runs it), and must be obeyable in each." in p3
    )

    def recipe(stem: str) -> set[str]:
        return set(
            subprocess.run(
                ["grep", "-rlw", stem, "commands/_sources", "commands/_fragments"],
                capture_output=True,
                text=True,
                cwd=ROOT,
            ).stdout.split()
        )

    assert {
        "commands/_sources/fabrik-review.md",
        "commands/_sources/fabrik-review-scoped.md",
    } <= recipe("review-probe-catalogue")
    coverage = recipe("term-coverage")
    assert "commands/_fragments/subagents-core.md" in coverage  # a fragment that names it
    assert (
        "commands/_sources/fabrik-user-test.md" in coverage
    )  # an includer: {{include:term-coverage}}


def test_phase_three_checks_an_added_rule_on_the_edit_and_its_origin_case() -> None:
    """Row 1791896044, a recurrence of the held apply-rule-to-origin-case: the catalogue's moved-text rule (403ab35e)
    was drafted with a section-scoped grader, the weakness that rule names, and its review's round 1 caught it before
    the commit. Pinned as the whole sentence between its neighbours in PHASE 3, so the sentence deleted, moved, or
    qualified inside the span reds. Not seen: a qualifier or contradicting line elsewhere in PHASE 3 or in another
    section, and an edit that cites the sentence without running the check — the review seats own that."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert (
        "and must be obeyable in each. A rule the edit adds is checked before PHASE 4's pin on the edit's own grader and"
        " sentence, which obey it, and on the case that raised it, which it must flag. A sentence that describes"
        in p3
    )
