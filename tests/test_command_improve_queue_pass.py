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
        " sentence, which obey it, and on the case that raised it, which it must flag. A mechanism the edit adds"
        in p3
    )


def test_a_reject_reason_cites_a_line_the_command_reaches() -> None:
    """Row 1791907618, a recurrence of the held reject-cites-what-the-command-reads: two rejects cited the round-zero rule
    in term-coverage.md, which /fabrik-review-scoped never points at, and the D-711 audit had to find the lines it does
    reach. Pinned whole inside PHASE 2's D-711 paragraph. Not seen: a contradicting sentence elsewhere in PHASE 2, or a
    reason that cites a reachable line for the wrong rule; the audit seat owns those."""
    p2 = _phase("## PHASE 2", "## PHASE 3")
    assert (
        "for misfiled text defects before any advice is rejected. A reject reason here cites a line the queue's command"
        " reaches — rendered into it, pointed at or run by it for that rule, or in the `CLAUDE.md` the session running"
        " it loads — never one that only exists elsewhere in the corpus (PHASE 1's answered-row reject already cites"
        " the command's current text)." in p2
    )


def test_a_count_lives_at_its_list() -> None:
    """W-66f398a3: a paragraph that says how MANY ("wrong in FIVE ways") away from its list goes stale when the next
    edit adds an item, and Phase D's scoped review-fix rounds kept confirming that residue. The rule lives once, in
    the hub CLAUDE.md's § Behavior, beside READ BEFORE YOU EDIT, which every hub session loads, including the review-fix loops
    that never render /fabrik-command-improve's PHASE 3."""
    text = re.sub(r"\s+", " ", (ROOT / "CLAUDE.md").read_text())
    behavior = text[text.index("## Behavior") : text.index("## ⚠️ THE FIX DIRECTIVE")]
    assert (
        "- **A count lives at its list.** An enumeration states how many in the clause that opens the list, or not at"
        " all (`the ways below`, never `five ways` a sentence away), and an edit that adds an item to a list, or"
        " removes one, re-counts every place that list's count is stated. **A worked example is re-read** against"
        " every caveat in its own paragraph before it is pinned or committed." in behavior
    )


def test_a_rule_lands_where_its_writers_load_it_and_a_mechanism_meets_its_consumer() -> None:
    """Rows 1791937927 and 1791940094 (kaizen's own closes, 2026-10-14): a count rule first written per command
    never reached the review-fix loops that wrote the stale count, and a panel's coder time box was written in
    before anyone checked that D6, the step meant to read its `TIMEOUT:` token, never reads it. The placement rule
    is § Drive's consistency rule (which the row names), PHASE 2 may target the home it names, and PHASE 3 checks a
    mechanism against its consumer."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    drive = text[text.index("## Drive") : text.index("## PHASE 1")]
    assert (
        "a rule that binds more than this command lives where every loop that WRITES the text it governs loads it"
        " — a fragment those commands INCLUDE, else the `CLAUDE.md` or pack they all load — never restated per"
        " command;" in drive
    )
    p2 = _phase("## PHASE 2", "## PHASE 3")
    assert (
        "or to the fragment, pack or `CLAUDE.md` that § Drive's consistency rule sends a shared rule to."
        in p2
    )
    assert (
        "names them), a seat file under `commands/_agents/`, § Drive's home for a shared rule, or the pack you would edit"
        in p2
    )
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert (
        "A mechanism the edit adds — a token, a field, a report shape, a panel's proposal included — is checked"
        " against the step or code that must consume it, and is written in only when that consumer reads it or"
        " this edit wires it in." in p3
    )


def test_a_reject_search_reads_the_render_and_a_seat_rule_lands_in_every_home() -> None:
    """Rows 1791941814 and 1791944106 (kaizen's own closes, 2026-10-14): a planned HELD reject said /fabrik-spec Phase 0
    dispatches no capped seat brief, but delegated-reads.md, which it includes, does; and a never-execute seat rule was
    first written into subagents-core alone. The reject search reads the rendered command; a seat rule goes to every
    home a grep names, and PHASE 2 admits the agent files those homes include."""
    p2 = re.sub(r"\s+", " ", _phase("## PHASE 2", "## PHASE 3"))
    assert (
        "to FIND that line, grep the rendered command (`~/.claude/commands/<command>.md`: every fragment, the"
        " appended close and every parameter), each file it points at for the rule, and the loaded `CLAUDE.md` for"
        " the row's subject, then cite the line in the file it renders from." in p2
    )
    assert "to a seat file under `commands/_agents/` (PHASE 3's seat rules)" in p2
    assert (
        "names them), a seat file under `commands/_agents/`, § Drive's home for a shared rule" in p2
    )
    p3 = re.sub(r"\s+", " ", _phase("## PHASE 3", "## PHASE 4"))
    assert (
        "An edit to what a SEAT may do lands everywhere seat rules live, since a rule in one home is not in force in"
        " the others: `command grep -rln -E '<two or more phrases of the neighbouring seat rule>' commands"
        " .claude/workflows .claude/hooks docs/reference` names them" in p3
    )
    for home in (
        "commands/_fragments/subagents-core.md",
        "commands/_sources/fabrik-review.md",
        "commands/_fragments/design-critique.md",
        "docs/reference/convergence-prompts.md",
        ".claude/workflows/fabrik-review-loop.js",
        ".claude/hooks/seat_guard.py",
        "commands/_agents/fabrik-reviewer.md",
    ):
        assert (ROOT / home).exists(), home
    assert "const SEAT_ISOLATION" in (ROOT / ".claude/workflows/fabrik-review-loop.js").read_text()


def test_a_row_prescribing_how_the_command_works_goes_to_the_panel_first() -> None:
    """Row 1791961631: a row whose prescribed step contradicts another line of the command is a decision."""
    p3 = re.sub(r"\s+", " ", _phase("## PHASE 3", "## PHASE 4"))
    assert (
        "A row that prescribes how the command works — a step, an order, a commit or a hand-off, not a wording — and"
        " contradicts a line that reading finds is a decision (a NEW mechanism still routes per PHASE 2), settled"
        ' before the first draft in CLAUDE.md § Autonomy\'s order ("the self-service sources first", then the Opus +'
        " Fable panel), and the draft is that answer."
    ) in p3
