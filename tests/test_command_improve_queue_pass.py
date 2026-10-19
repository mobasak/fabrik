"""/fabrik-command-improve feedback queue answered in one pass (D-735): execute what a new sentence says a script does.

Each test pins one sentence in the phase that owns it.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-command-improve.md"
# the three sentences rows 1792038532 / 1792033691 / 1792000873 amended (one subject), pinned whole
B_CLAIM_CHECK = "A sentence naming what a gate or script reads or refuses is checked against every branch of that function and every other path that filters or grades the same input, traced from the entry point that receives it, for every shape the sentence covers;"
C_RUN_RULE = "A rule the edit adds is RUN before PHASE 4's first pin — applied to the edit's own grader and sentence, which obey it, and to the row's case quoted as the row gives it (or, when the row only describes it, the artifact it names, fetched and quoted), which it must flag, each verdict written beside its quote."
A_GROUNDING = "the tool's own runtime output when a verdict is about a gate, a check or a tool, and its code, read live, when the edit restates the gate's conditions — every condition and value copied, never the prose describing them;"


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
        "every test file that names the edited source or fragment, or a command that includes that fragment or points at it by path (`command grep -rl --include=*.py <each name> tests/`), since a size cap or a sentence pinned verbatim is invisible from the source"
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
    assert "and must be obeyable in each. " + C_RUN_RULE + " A mechanism the edit adds" in p3


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


def test_the_held_subject_search_reads_the_reasons_view() -> None:
    """Mail 01M4VX84J0 (infra, D-837): the held-subject search greps `--reasons` output by reason, not by tag."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    assert (
        "Before rejecting, search earlier reject reasons for the subject: `python3"
        " /opt/fabrik/scripts/command_feedback_report.py --reasons <command>`, without `--held` (an untagged reject"
        " is still final; it is an advice hold when its reason says the text lacks the advice but is"
        " not wrong, an answered reject when it says the text already states it or never said it (D-952's two grounds), and neither"
        " when it is misfiled or refuted), prints a header and then one line per rejected row (handle, tags or `-`, reason),"
        " so grep its REASON column, since a near-synonym matches no tag; the orchestrator runs it and pins the"
        " output into an audit seat's scratch, never the seat."
    ) in text


def test_fabrik_task_third_queue_pass_lines() -> None:
    """/fabrik-task rows 1791971413, 1791966319, 1791953313, 1791973990, 1791958891, 1791975925 (D-856):
    subprocess-run tests found by name, a relied-on grader red-proved, vendored copies searched, the
    live-store pin named, and MEASURE's slice re-run on the built tree."""
    text = re.sub(r"\s+", " ", (ROOT / "commands" / "_sources" / "fabrik-task.md").read_text())
    for needle in (
        "the tests that import, grade or run the declared files (grep the tests for each file's name and every mode"
        " or flag the change extends, since a test that runs a script by subprocess never imports it)",
        "a grader the design relies on is shown red on a deliberately broken input, since a pass proves nothing"
        " until it can fail",
        "and every vendored copy outside it (`find /opt` by the file's name)",
        "A test that writes a live store pins it to a tmp root: the hub's `tests/conftest.py` already pins the mail"
        " root and the `~/.claude/state` files, a work-store test passes a tmp repo, and a new store gets its pin there",
        "before phase 4, MEASURE's test slice re-runs on the built tree,",
    ):
        assert needle in text, needle


def test_phase_three_points_at_a_rule_stated_elsewhere_without_a_gloss() -> None:
    """Row 1792031068 (kaizen, the fabrik-review Residual-sentence run): a ten-word gloss of Phase 2's by-design rule
    became a THIRD wording beside the rule and term-edit's restatement, and cost a round. :249's clause covered a rule
    adapted from CLAUDE.md or a fragment and forbade only narrowing; a rule stated in another command or another section
    of the target, glossed without narrowing, was not covered. A recurrence of the held
    other-tool-behaviour-one-fact-plus-pointer subject (D-711). Written as an EXTENSION of :249's rule (it points at
    that rule by its own subject words, neither restating nor cutting a quote of it — the round-2 Opus seat caught a
    quote cut mid-clause), placed between two pinned spans, so the drive test's
    :247-252 pin and this file's :252-254 pin stay whole. Mutants, each run by the round-1 Opus seat on a copy: delete
    the sentence; 'carries a gloss' → 'carries a long gloss'; drop 'another command or another section'; 'only where' →
    'where'; drop 'names its source'; 'neither the pointer nor the quote' → 'the quote' (the raising case was a glossed
    POINTER); move the sentence after the script-behaviour sentence; append a gloss-allowing sentence after it (the
    seat's surviving mutant, killed by the follows-directly assertion)."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    head = "The rule above for a rule adapted from `CLAUDE.md` or a fragment holds"
    assert p3.count(head) == 1, "the pointer rule left PHASE 3, or is stated twice"
    tail = "keeps the words that do fit, and names its source."
    sentence = p3[p3.index(head) :]
    sentence = sentence[: sentence.index(tail) + len(tail)]
    assert (
        "holds for a rule stated in another command or another section of the target too, and neither the pointer nor"
        " the quote carries a gloss: a gloss is a new wording that drifts, and a fresh wording is written only where the"
        " rule's words do not fit the new subject, keeps the words that do fit, and names its source."
    ) in sentence, (
        "the extension, its gloss ban and its bounded allowance are one contiguous sentence"
    )
    for weakener in ("where practical", "where possible", "optionally"):
        assert weakener not in sentence, weakener
    # it sits between the two pinned spans — directly after the mechanism sentence and directly before the
    # script-behaviour sentence, so nothing can be slipped in beside it
    before = p3[: p3.index(head)]
    assert before.rstrip().endswith("this edit wires it in."), before[-80:]
    after = p3[p3.index(head) + len(sentence) :]
    assert after.lstrip().startswith(
        "A sentence that describes what a script, tool or another step DOES"
    ), after[:80]


def test_a_claim_about_a_gate_is_grounded_in_its_code_and_run_on_the_rows_case() -> None:
    """Rows 1792038532, 1792033691 and 1792000873 (kaizen, 2026-10-15) — one subject: a claim about a gate or script
    is grounded in the real artifact, never a stand-in. (1) "every branch of that function" let two misreadings through
    in one run, each a second code path the named function did not show (a sibling grader of the same plan text, a
    COMMANDS tuple filtering `--init`'s input): the check now reaches every other path that filters or grades the same
    input. (2) "checked … on the case that raised it" was satisfied by READING: a quote ban was drafted while the raising
    case was a glossed pointer; the rule is now RUN on the row's case quoted as the row gives it. (3) an edit restating a
    gate's conditions was drafted from the lane table's prose and dropped three of the gate's conditions: § Drive's
    Grounding bullet now names the gate's code, every condition and value copied. Rows (2) and (3) are second sightings
    of held subjects (apply-rule-to-origin-case, open-enforcing-code-before-restating; D-711). Mutants, each a failing
    assertion: drop "or refuses"; drop "and every other path that filters or grades the same input"; RUN → checked;
    drop "quoted as the row gives it"; drop the Grounding clause; "every condition and value" → "the conditions".
    Round 1 bounded each rule with its method: the other paths are traced from the entry point that receives the
    input (a grep of call sites is not a trace); the run names its route when the row only describes its case (the
    artifact it names, fetched and quoted) and writes each verdict beside its quote; the code is read live."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert B_CLAIM_CHECK in p3
    assert C_RUN_RULE in p3
    drive = text[
        text.index("- **Grounding — before drafting, not after review.**") : text.index(
            "- **Time.**"
        )
    ]
    assert A_GROUNDING in drive
    # each rule is stated once — a restatement elsewhere in the file would drift
    assert text.count("filters or grades the same input") == 1
    assert text.count("quoted as the row gives it") == 1
    assert text.count("every condition and value copied") == 1


def test_the_mark_step_says_a_handle_is_the_whole_ts_with_its_fraction() -> None:
    """Row 1792084693, a second verdict on the mark-handle subject (held as mark-handles-from-take-output): a
    handle typed without its fractional part was refused as matching no row. The tool compares handles as exact
    strings, so the sentence names the whole `ts`. Mutants: drop the clause, or let the tool match by prefix."""
    p5 = _phase("## PHASE 5", "Doc Sync:")
    assert (
        "copy them from `--queue` exactly, the whole `ts` with its fractional part (`1792030670` matches no row of"
        " `1792030670.5328414`)" in p5
    )
    # the sentence's example, executed: the row's key is its full ts, and mark_answered matches keys exactly —
    # read inside mark_answered, since --reject carries the same matching line (round-1 finding)
    import inspect
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import command_feedback_report as cfr

    assert cfr._ts_key(1792030670.5328414) == "1792030670.5328414"
    assert cfr._ts_key(1792030670.5328414) != "1792030670"
    assert "unknown = [t for t in wanted if t not in known]" in inspect.getsource(
        cfr.mark_answered
    ), "--mark-answered no longer matches handles exactly: the sentence's example is no longer true"


def test_grounding_reads_the_governing_spec_and_a_copied_recipe_names_its_form() -> None:
    """Rows 1792070803 and 1792087460, each a recurrence (held as reread-d-row-before-folding-review and as
    grounding-reads-the-cell-contract / copy-recipe-on-each-mechanism): grounding named only the hub ledger and
    backlog, never the spec whose decisions a row can reverse; and a recipe sentence never said what form the
    copied text is in, so a draft told a lead to paste a JS template literal. Mutants: drop either clause."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    assert (
        "`docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md` and the decisions or binding-constraints section of each"
        " spec the command cites, for the subject (a ruling already made is" in text
    )
    assert (
        "which the sentence cites — a recipe held in a template literal or an escaped string is pointed at by name"
        " for its reader to"
        " follow, never handed over to be pasted —" in _phase("## PHASE 3", "## PHASE 4")
    )


def test_a_recurrence_is_searched_by_its_step_and_answered_rejects_flag_a_line() -> None:
    """Rows 1792198197, 1792193148: three sightings of one re-read step hid under three nouns, so the
    search names the step and its mechanism words. Row 1792194121: answered rejects stay final, and
    three or more on one subject citing one line make that line a candidate group for the ONE edit."""
    phase2 = re.sub(r"\s+", " ", SRC.read_text())
    phase2 = phase2[phase2.index("## PHASE 2") : phase2.index("## PHASE 3")]
    assert (
        "never the seat. Grep it for the subject, for what the row asks the author to DO and for its mechanism"
        " words (such as a guard, both sides, a false green), since one step asked under three nouns is one"
        " subject."
    ) in phase2
    assert (
        "An answered reject (PHASE 1) stays final, but a line that three or more answered rejects on one subject"
        " cite is a line not followed: it is a candidate group for this phase's ONE edit, its target resolved and"
        " lock-checked as below."
    ) in phase2
    assert "(it warns only on an identical `HELD:` tag)" in phase2


def test_a_widened_subject_and_a_recipe_meet_their_breaking_inputs_before_the_pin() -> None:
    """Rows 1792200478, 1792189926: the line four answered rejects cite was not followed; a widened census
    subject was never run through its own search methods (they found 0 of 3 readers), and a recipe was
    run only on friendly inputs."""
    phase3 = re.sub(r"\s+", " ", SRC.read_text())
    phase3 = phase3[phase3.index("## PHASE 3") : phase3.index("## PHASE 4")]
    assert (
        "A rule whose subject the edit widens is run before PHASE 4's first pin, through the rule's own search"
        " methods, on a sample of the new subject, since a method that finds the old subject may find none of"
        " the new one."
    ) in phase3
    assert (
        "as well as a synthetic file built to break it in a scratch repo (round zero's input classes in"
        " `/opt/fabrik/commands/_fragments/term-coverage.md`, and for a recipe a regex metacharacter or backtick in a commit subject"
        " and a sibling commit inside the window the recipe scans, when it scans one)"
    ) in phase3
    # the pointer resolves: round zero there lists the input classes this clause leans on
    coverage = ROOT / "commands" / "_fragments" / "term-coverage.md"
    classes = "boundary, sentinel, prefix, overlapping, escaped and alternate-notation inputs"
    assert classes in re.sub(r"\s+", " ", coverage.read_text())


def test_the_audit_seat_reads_the_source_and_briefs_name_pins_and_consumers() -> None:
    """Rows 1792227360 (an audit seat told to grep the rendered ~/.claude command, which no seat may open),
    1792199420 (recurring held multi-span-coherence: the audit seat's proposed wording was not checked against the
    phases relying on it), 1792201686 (recurring held extend-a-pinned-sentence-as-a-new-sentence: a sentence placed
    beside a pinned one broke its pin) and 1792208187 (recurring held fragment-consumers-from-temp-render)."""
    p2 = re.sub(r"\s+", " ", _phase("## PHASE 2", "## PHASE 3"))
    assert (
        "That rendered-copy grep is the lead's: the audit seat reads the command source and the fragments it includes,"
        " pinned in its scratch, never the rendered `~/.claude` copy, which no seat opens, and checks any wording it"
        " proposes against the phases that rely on the sentence it would change." in p2
    )
    p3 = re.sub(r"\s+", " ", _phase("## PHASE 3", "## PHASE 4"))
    assert (
        "The tests that pin a paragraph's sentences are read before a sentence is placed in it (`command grep -rn '<a"
        " phrase of each neighbour>' tests/`), and the new text goes where no pinned span runs, the gap between two"
        " sentences one pin joins included; a pin that ends at a sentence's period also fails when that sentence is"
        " extended." in p3
    )
    p4 = re.sub(r"\s+", " ", _phase("## PHASE 4", "## PHASE 5"))
    assert (
        "For a `_fragments/` edit the brief names the consumers PHASE 3 names (each `{{include:}}` consumer and each"
        " source or fragment that names the fragment), so no seat hunts for homes the fragment does not have."
        in p4
    )


REMOVED_WORDS_RULE = (
    "A sentence a round rewords has its removed words grepped across `tests/`, test names and docstrings included, and"
    " the commit subject drafted for PHASE 5 (drafted now if not yet written), before that round's pin, and each hit is"
    " reworded with the sentence."
)
FRAGMENT_SCOPE_RULE = (
    "A sentence a `_fragments/` edit adds names, in its own words, the consumers that have its subject (for example a"
    " review loop or a round count) and binds no other."
)
TEST_PROBE_RULE = (
    "The run-before-review rule above holds for a sentence stating how a test or gate behaves: it is run on that"
    " test's or gate's own real cases before PHASE 4's review."
)


def test_test_fragment_and_removed_word_rules() -> None:
    """Row 1792241313 (five answered rejects on the probe rule: test and gate sentences never met their own cases),
    1792259406 (the third answered reject on "must be obeyable in each": a close-chain sentence bound 37 commands with
    no review loop) and 1792243098 (recurring held commit-subject-written-after-closing-round: removed words left in
    test names)."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "and its mail id goes in the FEEDBACK line. " + TEST_PROBE_RULE + " A rule whose" in p3
    assert (
        "may find none of the new one. "
        + FRAGMENT_SCOPE_RULE
        + " Then, **from the main master checkout only**"
        in p3
    )
    assert "A reworded sentence's removed words" not in p3
    p4 = _phase("## PHASE 4", "## PHASE 5")
    assert "it returns the line that states the row's step. " + REMOVED_WORDS_RULE in p4


SCRIPT_POINTER_RULE = (
    "An edit that must describe what a script does states only the fact its reader acts on and points for the rest at"
    " the `docs/` file the script's `# AFTER-EDIT:` header names for that behaviour, else at the script by path —"
    " never restating the rest."
)


def test_a_script_description_points_at_the_doc_that_owns_the_script() -> None:
    """Row 1792276714 (kaizen, 2026-10-18), recurring held other-tool-behaviour-one-fact-plus-pointer (1791508926): a
    fix that restated work.py's behaviour seeded a new edge case each round until it pointed at work-tracking.md."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    assert "so a one-sentence row gets one sentence. " + SCRIPT_POINTER_RULE in p3


def test_a_lengthened_paragraph_is_rewrapped_whole_by_a_word_checking_script() -> None:
    """Row 1792287785 (2026-10-18), recurring held rewrap-pinned-bullet-by-script (1792268556): hand-rewrapping a
    lengthened catalogue bullet pushed the overflow down a line twice before a script rewrapped it whole."""
    p3 = re.sub(r"\s+", " ", _phase("## PHASE 3", "## PHASE 4"))
    assert (
        "also fails when that sentence is extended. A wrapped paragraph or bullet the edit lengthens is rewrapped whole,"
        " at its width and never past the next list marker, blank line or fence, by a script that asserts its words"
        " unchanged, before PHASE 4's first pin. A row that prescribes" in p3
    )
    # round-1 review: a paragraph-joining script with a words-only check merged six § Drive bullets, and a ```bash
    # fence, into one paragraph while its assert passed — so the rule bounds the rewrap at markers, blanks and fences


def test_a_weakening_recurrence_routes_and_ledger_prose_follows_the_closing_pass() -> None:
    """Row 1792329659 (2026-10-18): PHASE 2's 'edited, never re-rejected' and PHASE 1's weakening refusal had no
    order, and row 1792326723 was both; row 1792329281, recurring held size-figure-after-closing-pass and
    commit-subject-written-after-closing-round: a CHANGELOG hunk drafted mid-review kept two refuted sentences."""
    p2 = re.sub(r"\s+", " ", _phase("## PHASE 2", "## PHASE 3"))
    assert (
        "The one exception is a recurrence whose edit PHASE 1 refuses as weakening: it is routed to the operator as a"
        " proposal, and its rows are rejected with a reason opening `HELD:<subject> ROUTED:` that names the proposal's"
        " mail id and quotes the line the edit would weaken; `--reject` still prints its held warning for it, and a"
        " subject an earlier reason already routed cites that proposal's mail id instead of routing again."
        in p2
    )
    terminal = re.sub(r"\s+", " ", SRC.read_text()[SRC.read_text().index("## Terminal") :])
    assert (
        "`no edit this run — the surviving row routed to the operator`, naming the row and the proposal's mail id"
        in terminal
    )
    chain = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / "close-chain.md").read_text())
    assert (
        "a draft written mid-loop carries none. In such a command, what an input says about the change — the commit"
        " message, the `--evidence` text, a D-row, a `CHANGELOG.md` or other ledger hunk — is written, or checked"
        " sentence by sentence against the final text, after that pass too, and again after any fix the chain's own"
        " check or `final_gate.py` forces. Then: (1)" in chain
    )


def test_a_widened_or_split_sentence_rereads_the_clauses_already_in_it() -> None:
    """Row 1792332697, the second sighting of held placement-keeps-anaphor-with-antecedent: widening 'you run the
    status probe' to 'and every other shell-only check' attached the sentence's existing WebFetch fallback to a quote
    check the command forbids. Review round 1: the rule sits beside the placement sentences (where the held reject
    sends it), reaches later sentences pointing back, and covers text placed between a pronoun and what it names."""
    p3 = re.sub(r"\s+", " ", _phase("## PHASE 3", "## PHASE 4"))
    assert (
        "and the draft is that answer. Before an edit widens a sentence's subject, splits the sentence or places text"
        ' between a pronoun (or an "above") and what it names, each clause that attaches to the changed part — in the'
        " sentence edited, in the sentence holding the pronoun, and in each later sentence or item pointing back into"
        " either — is read against what that clause will bind once the edit lands, since a clause written for one"
        " subject or one antecedent then binds whatever the widening adds, the split leaves beside it or the placed"
        " text puts nearer. An edit to what a SEAT may do"
    ) in p3
    assert (
        'every branch the sentence\'s subject can bind (a pronoun for "the review" binds each review the step can pick), and'
        in p3
    )


def test_phase_three_reads_the_path_pointed_files_and_the_neighbouring_items() -> None:
    """Rows 1792407169, 1792408957, 1792405310, 1792358510: a draft restated the probe catalogue's own hunt line (pointed at by
    path, never included), and two drafts narrowed or overruled the bullet or paragraph bound beside them. The
    sentence between its two neighbours is pinned by equality, so an added licence fails here."""
    p3 = _phase("## PHASE 3", "## PHASE 4")
    head = "(a mode may already cover the blind spot). "
    tail = "The tests that pin a paragraph's sentences are read before"
    assert p3.count(head) == 1 and p3.count(tail) == 1
    span = p3[p3.index(head) + len(head) : p3.index(tail)]
    assert span == (
        "Before the first draft, the files the target points at by path for the same subject are read too (a"
        " review command's probe catalogue), and so are the row's own words, the rule the edit extends, and the"
        " paragraph or list the new text joins (for a new paragraph, the paragraphs beside it; for a place the pins"
        " sentence below moves the text to, that place's), read whole — each one's lead-in and the items beside the"
        " new text — for the bounds each sets and the acts its sentences govern, which the new text leaves standing unless the row is a decision settled as the decision"
        " sentence below says. "
    ), span


def test_a_fragment_pointed_at_by_path_is_a_write_and_lock_target() -> None:
    """W-5048181b: PHASE 2's write-target list and its lock check named the fragments a command renders but not one it
    points at by path (the probe catalogue, read live and never rendered), so a row whose fix belongs there had no
    listed target and no lock check. Both lists now name it; the lock check's printed grep is RUN here on a real command
    source and must print the catalogue repo-relative, the form `owned_paths` uses, since an absolute path matches no
    lock and fails open. The weight sentence and PHASE 5's test pick count a by-path reader too."""
    p2 = _phase("## PHASE 2", "## PHASE 3")
    assert (
        "to one of the fragments that command renders or points at by path (a review command's probe catalogue), to"
        " the rule pack it cites" in p2
    )
    lock = p2[p2.index("the file you would WRITE is lock-owned") : p2.index("STOP and mail")]
    assert (
        "(`command grep -n 'include:' commands/_sources/<command>.md` names them) or points at by path (`command grep"
        " -no 'commands/_fragments/[a-z0-9-]*\\.md' commands/_sources/<command>.md`, repo-relative as `owned_paths`"
        " is, names them), a seat file under `commands/_agents/`" in lock
    )
    assert lock.index("points at by path") < lock.index(".fabrik/plan-locks/")
    pattern = re.search(r"grep -no '([^']+)'", lock).group(1)
    scoped = ROOT / "commands" / "_sources" / "fabrik-review-scoped.md"
    out = subprocess.run(
        ["grep", "-no", pattern, str(scoped)], capture_output=True, text=True, check=True
    ).stdout.split()
    paths = {line.split(":", 1)[1] for line in out}
    assert "commands/_fragments/review-probe-catalogue.md" in paths, paths
    assert not any(p.startswith("/") for p in paths), paths
    included = set(re.findall(r"\{\{include:([a-z0-9-]+)\}\}", scoped.read_text()))
    assert "review-probe-catalogue" not in included, included
    flat = re.sub(r"\s+", " ", SRC.read_text())
    assert (
        "renders into every command that INCLUDES it, and is read by every command that points at it by path"
        in flat
    )
    assert (
        "or a command that includes that fragment or points at it by path (`command grep -rl"
        in flat
    )


def test_the_lock_check_names_the_appended_fragment_and_how_an_entry_owns_a_path() -> None:
    """W-ddf1839c: the lock check's `include:` grep cannot see the two fragments the assembler appends with no include
    (close-feedback to every command, agent-feedback to every agent), and the bullet never said how an `owned_paths`
    entry matches a target while locks hold paths, directories and globs. Both sentences are pinned whole. Their facts
    are checked against the code: each append STATEMENT (deleting one fails here, the constant alone would not) and no
    source naming either fragment in an `include:`; and the three-shape ownership rule run through `_glob_matches` in
    scripts/epic_order.py, the one lock reader that implements all three."""
    import importlib.util
    import re as _re

    p2 = _phase("## PHASE 2", "## PHASE 3")
    lock = p2[p2.index("the file you would WRITE is lock-owned") : p2.index("STOP and mail")]
    appended = (
        "The assembler also appends two fragments with no `include:` (`commands/assemble_commands.py`):"
        " `commands/_fragments/close-feedback.md` to every rendered command (`_CLOSE_FEEDBACK`) and"
        " `commands/_fragments/agent-feedback.md` to every agent definition (`_AGENT_FEEDBACK`), so a row about the"
        " shared FEEDBACK duty can target one of them, while close wording one command owns stays in its source or"
        " `commands/_fragments/close-chain.md`."
    )
    owns = (
        "An entry owns the path it names, every path under it when it names a directory, and every path its glob"
        " matches (`dir/**`, with `*` inside one path segment), so test all three — the lock-reading scripts each match"
        " a different subset, so none of them is the rule — and read an entry written as prose by hand."
    )
    assert lock.count(appended) == 1 and lock.count(owns) == 1
    assert lock.index(appended) < lock.index("ONLY THEN read the locks") < lock.index(owns)
    asm = (ROOT / "commands" / "assemble_commands.py").read_text()
    assert (
        '_CLOSE_FEEDBACK = "close-feedback"' in asm and '_AGENT_FEEDBACK = "agent-feedback"' in asm
    )
    assert 'text = text.rstrip("\\n") + "\\n\\n" + frags[_CLOSE_FEEDBACK] + "\\n"' in asm
    assert (
        "body = frags.get(_AGENT_FEEDBACK" in asm
        and 'text = text.rstrip("\\n") + "\\n\\n" + body + "\\n"' in asm
    )
    for name in ("close-feedback", "agent-feedback", "close-chain"):
        assert (ROOT / "commands" / "_fragments" / f"{name}.md").exists()
    for src in (ROOT / "commands" / "_sources").glob("*.md"):
        assert not _re.search(
            r"\{\{include:\s*(close-feedback|agent-feedback)\s*\}\}", src.read_text()
        ), src.name
    spec = importlib.util.spec_from_file_location("eo", ROOT / "scripts" / "epic_order.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    g = mod._glob_matches
    assert g(
        "commands/_fragments/term-edit.md", "commands/_fragments/term-edit.md"
    )  # the path it names
    assert g("commands/_fragments", "commands/_fragments/term-edit.md")  # a directory's subtree
    assert g("templates/chrome-extension/**", "templates/chrome-extension/src/a.ts")  # a glob
    assert not g("src/a/*", "src/a/b/deep.py")  # `*` stays inside one segment
    assert not g("commands/_fragments", "commands/_fragments_old/x.md")
