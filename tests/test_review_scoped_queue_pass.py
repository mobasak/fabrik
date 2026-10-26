"""/fabrik-review-scoped feedback queue answered in one pass (D-735): the probe catalogue and the text fixes.

The catalogue collects the specific probes the queue's rows asked for; the command points at it by its hub path and
stays lean. Each test pins one subject's lines in the section that owns them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-review-scoped.md"
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_the_command_points_at_the_catalogue_before_the_first_pin() -> None:
    """Step 5 names the catalogue by its hub path, and the file exists in this tree."""
    assert (
        "/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in _norm(SRC)
    )
    assert CAT.exists()


def test_the_command_applies_seat_isolation_to_every_brief_that_runs_tests() -> None:
    """Row 1792005608 and six earlier verdicts asked for archive roots derived from the test imports; the
    catalogue's § Seat isolation already says so, but the command sent the lead there only for lines that
    'match the change's SHAPE', so a hand-written brief kept listing paths by hand. The command now names
    § Seat isolation as shape-independent and the derived-roots rule in one sentence, pointing at the
    catalogue for the recipe. Mutants: drop 'whatever the shape' (the shape-keyed pointer returns), drop
    'never a hand-listed path set' (the rule the rows asked for is gone), or restate the recipe's commands
    here (two sources of truth) — each fails one assertion below."""
    src = _norm(SRC)
    # its own sentence, after the SHAPE-keyed list ends — spliced into that list, the SHAPE filter reads as
    # governing it (round-1 Sonnet finding)
    assert "runs found missing. Its § Seat isolation applies whole, whatever the shape" in src
    sentence = _section(
        src,
        "Its § Seat isolation applies whole, whatever the shape",
        "⚠️ **A brief states the QUESTION",
    )
    assert "in every brief that runs tests" in sentence
    # "an archive" alone let a brief archive HEAD, which moves under concurrent sessions (round-3 Opus finding)
    assert "run from an archive of the pin's base SHA, never the live tree or HEAD" in sentence
    assert "tests run against an archive of the pinned SHA" not in sentence, (
        "that is the catalogue's own wording (§ Seat isolation) — a verbatim copy is a second source"
    )
    assert "derived from what the tests import, read or run" in sentence
    assert "never a hand-listed path set" in sentence
    assert "live in this repo's `.claude/workflows/fabrik-review-loop.js`" in sentence, (
        "the pointer must LOCATE the recipe — the catalogue names the constants but not their file; the path "
        "is the REPO's own copy, which the sync manifest ships to every repo as an agent hook file "
        "(test_review_loop_workflow forbids a source launching the hub copy)"
    )
    assert "/opt/fabrik/.claude/workflows/" not in sentence, (
        "a source must never point seats at the hub copy"
    )
    assert "not restated here" in sentence
    for restatement in ("git archive", "ls-tree", "overlay", "chdir", "unless"):
        assert restatement not in sentence, (
            f"{restatement!r}: the recipe belongs to the workflow, not here"
        )
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text()
    assert "const PIN_IMPORT" in js and "const PYTEST_PINS" in js, "the pointer's target moved"
    assert "the root conftest.py, the pytest config" in js, (
        "the recipe no longer takes the conftest"
    )
    cat = _norm(CAT)
    assert (
        "never all of them, § Seat isolation excepted: it applies whole in every brief that runs tests"
        in cat
    ), "the catalogue's own header still says 'never all of them' without the exception"
    iso = _section(cat, "## Seat isolation", "## Loop bookkeeping")
    assert "The recipe names its roots by what the tests import" in iso, (
        "the pointer's target moved"
    )


def test_escape_variants_are_asked_from_round_one() -> None:
    """Row 1791496929: the ask sat under the closing reader only, so round 1 never attacked the guard."""
    assert (
        "owes every round's readers — round 1's first — and that INDEPENDENT reader the guard or rule by NAME"
        in (_norm(SRC))
    )


def test_command_run_is_cited_by_symbol_not_line() -> None:
    """The line anchors into command_run.py had drifted (:556, :508, :593-595, :880, :2547-2554, :3116)."""
    text = _norm(SRC)
    assert not re.search(r"command_run\.py:\d", text)
    assert "`command_run.py::_trend_label`" in text
    assert "`command_run.py::AGENT_CLOSED_STATES`" in text


def test_own_fix_guards_helper_contracts_and_pinned_versions() -> None:
    """Rows 1791833683, 1791830180, 1791831690; 1791830163 rests on the scoped source's own guard rule."""
    text = _norm(CAT)
    assert (
        "Run the changed artifact end to end when it can run (an emitted one-liner run as emitted, under its real shell)"
        in _section(text, "## Before the first pin", "## The brief's hunt lines")
    )
    assert "a pure helper's own return contract, not only what its callers observe" in _section(
        text, "- Callers and consumers:", "- Parsers:"
    )
    assert (
        "a `fabrik-researcher` seat whose brief names the version the repo pins or deploys (its lockfile or spec line) and asks for the claim at that version"
        in _section(text, "- The premise:", "## Graders")
    )
    assert "an explicit ASK for its ESCAPE VARIANTS" in _norm(
        ROOT / "commands" / "_sources" / "fabrik-review-scoped.md"
    )
    assert max(len(line) for line in CAT.read_text().splitlines()) <= 120


def test_a_guard_brief_states_its_model_boundary() -> None:
    """Row 1791839280."""
    src = _norm(ROOT / "commands" / "_sources" / "fabrik-review-scoped.md")
    assert "an explicit ASK for its ESCAPE VARIANTS" in src
    assert (
        "together with its MODEL BOUNDARY, the inputs it is meant to judge, so a variant outside that boundary is `RECORDED — by design (D-785)` in round 1"
        in src
    )
    import sys

    sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))
    try:
        import check_review_coverage
    finally:
        sys.path.pop(0)
    assert check_review_coverage.VERDICT.search("RECORDED — by design (D-785)")


def test_a_silent_refuter_is_already_retried_once_and_marked_failed() -> None:
    """Row 1791826392 (mailed): the workflow already retries; the ledger's `read` table is the gap."""
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text()
    assert "const retry = await refuteCall(r.slice, missing, '-retry')" in js
    assert "STILL UNANSWERED (refuter failed)" in js


def test_the_closing_reader_clause_cites_d118_not_d066() -> None:
    """W-a8361c19 residual 5: the clause pinned the asymmetry on D-066 (a finding-shape triage row); D-118 bound independent recall here."""
    text = _norm(SRC)
    assert "Before D-118 that was the asymmetry between the two commands" in text
    assert "D-066 named only the heavy command" not in text


def test_the_pre_pin_section_reads_as_every_pin_not_only_the_first() -> None:
    """Row 1791890873: the header, the heading and both consuming commands said 'first pin' while two of the
    section's bullets ran before each delta pin. The catalogue is checked as a property (every 'first pin' names
    delta or every within 60 characters; no 'first pin only' or 'round 1 only'); each command by its exact
    sentence, which is also what catches a revert.

    Cheapest ways to pass without the outcome: in the catalogue, a sentence that names "delta" or "every" while
    negating it ("solely on the first pin; skip it for delta pins"); in either command, any first-pin-only
    sentence added beside its exact one. This test pins wording, not meaning; the review reads meaning.
    """
    text = _norm(CAT)
    for m in re.finditer(r"(?i)first pin", text):
        assert re.search(r"(?i)delta|every", text[m.end() : m.end() + 60]), text[
            m.start() : m.end() + 60
        ]
    assert not re.search(
        r"(?i)first pin (alone|only)|only (before )?the first pin|round 1 only", text
    )
    assert "before every pin, the first and each delta" in text
    for path in (ROOT / "commands" / "_sources" / "fabrik-review.md", SRC):
        assert (
            "Before every pin, the first and each delta, and in every brief, apply the lines of"
            in _norm(path)
        )


def test_both_review_commands_name_surface_add_for_a_pre_start_file() -> None:
    """Intel 01M4TJJDG2: a running review's window opens at its `start`, so a file last edited before it, outside
    every earlier covered window and not named by `--surface`, is the case `command_run.py surface --add` exists for,
    and neither command said so. The sentence is pinned inside the section that opens the scope (review-scoped step
    1; fabrik-review between its `start` block and "Then, for the whole run:"), and the verb is RUN, so a renamed flag
    reds here. Cheapest bypass: `--help` keeps `--add` while the verb stops storing anything. This grader cannot see
    that; the behaviour is owned by `tests/test_command_run.py::test_surface_add_refuses_every_record_but_a_running_review`
    and `tests/test_stop_hook_spontaneous_review.py::test_a_running_review_widened_mid_run_exempts_a_pre_start_file_it_came_to_cover`."""
    import subprocess
    import sys

    sentence = (
        "While the record runs, a file you come to cover that was last edited before `start`, outside every earlier "
        "covered window, and not named by `--surface` is added with `python3 scripts/command_run.py surface --add "
        "<path>`: a running review's window opens at its `start`. The verb widens the TOP record only, so it is "
        "refused under a nested non-review `start` (every refusal: `docs/reference/command-run-protocol.md`)."
    )
    scoped = _norm(SRC)
    assert sentence in _section(scoped, "1. **Scope = this session's own work:**", "2. **Arm:**")
    review = _norm(ROOT / "commands" / "_sources" / "fabrik-review.md")
    assert sentence in _section(
        review, '--surface "<what this run is OVER', "Then, for the whole run:"
    )
    # its own paragraph, never folded back into the routed-up one (round 2, NEW-1)
    assert (
        "\n\nWhile the record runs, a file you come to cover"
        in (ROOT / "commands" / "_sources" / "fabrik-review.md").read_text()
    )
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "command_run.py"), "surface", "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert out.returncode == 0 and "--add" in out.stdout, out.stderr


def test_the_lead_runs_the_leak_check_around_every_scoped_pass() -> None:
    """Row 1791896900 (D-711 audit: MISFILED): review-scoped dispatches seats each pass but carried no lead leak check,
    which /fabrik-review has. Pinned inside step 5's dispatch text, before the POOL OFF comment, and the target bullet
    is pinned with its body, so the sentence moved into inactive text or the bullet emptied reds. The row's other half
    (a seat cds into scratch in the same call) needs no edit: the SEAT_ISOLATION brief and fabrik-reviewer.md already
    require absolute scratch paths. Not seen: the lead skipping the check; the seats' transcripts own that."""
    sentence = (
        "The lead runs the **Leak check** of `/fabrik-review` (its bullet of that name) before every dispatch and after"
        " each pass returns, since a seat can write to the shared tree."
    )
    scoped = _norm(SRC)
    # live text only: a comment wrapped around the sentence in place would keep it inside the section
    live = re.sub(r"<!--.*?-->", "", scoped)
    assert sentence in _section(live, "**The partition rule of", "6. **Gate + close:**")
    assert scoped.count(sentence) == 1
    # live text only: an HTML comment around the bullet would leave the pointer aimed at inactive text
    review = re.sub(r"<!--.*?-->", "", _norm(ROOT / "commands" / "_sources" / "fabrik-review.md"))
    assert (
        "- **Leak check — the lead, before EVERY dispatch and after the pass returns:** a tree baseline (`git diff HEAD |"
        " md5sum`, not the PIN digest) plus `git rev-parse HEAD`, `git status --porcelain --ignored` and `git stash list`"
        in _section(review, "- **The seats (native", "- **Every finder brief carries")
    )


def test_the_run_record_section_yields_to_a_step_named_before_it() -> None:
    """W-ae8fd45b: this command's 'classify the surface FIRST' sat two lines above the run-record include, whose
    heading says the record is the FIRST act, and a heading beats the paragraph above it. The fragment's first line
    now yields to a step the command names as running before the record; the command still names that step there."""
    frag = _norm(ROOT / "commands" / "_fragments" / "run-record.md")
    assert frag.startswith(
        "## Run record — open it as this command's FIRST act A step this command's text names as running BEFORE the"
        " record (`/fabrik-review-scoped`'s surface classification) runs first; then the record opens, unless that step"
        " routed to another command, whose record replaces this one."
    )
    src = _norm(SRC)
    assert src.index("**Before the record — classify the surface FIRST") < src.index(
        "{{include:run-record}}"
    )


def test_term_edit_pin_clause_does_not_license_a_mid_window_edit() -> None:
    """W-975b3652: term-edit's '(the seats read the pin; you edit the working tree)' read as
    licensing an edit while seats run, against subagents-core's 'While seats are out you do not edit the pinned
    files' in 14 of its 17 includers. Panel split (Opus parity, Fable reword); the repo's own rule against copying
    a fragment's rule into another settles it as a reword that states WHEN."""
    te = _norm(ROOT / "commands" / "_fragments" / "term-edit.md")
    assert "(the seats read the pin; you edit the working tree)" not in te


def test_step_five_keeps_ruff_findings_off_seats_and_names_the_hub_ledger() -> None:
    """Rows 1791982905 (a seat reported pre-existing HEAD formatting as a finding) and 1791982896 + 1791981699
    (a sync-excluded repo's vendored review_loop_ledger.py has no `pin` verb; hand-made pins twice)."""
    text = _norm(SRC)
    assert (
        "the brief says ruff's output is the lead's, so a seat reports no lint or format finding, pre-existing or not"
        in text
    )
    assert (
        "(every `review_loop_ledger.py` call in this step runs as `python3 /opt/fabrik/scripts/review_loop_ledger.py` in a"
        " sync-excluded repo, since a vendored copy there may lack `pin` or `read --pins`)"
    ) in text


def test_a_doc_fix_that_must_carry_a_clause_quotes_it_whole_never_paraphrases() -> None:
    """Row 1792025649 (kaizen, 2026-10-15): every own-fix of a run was a paraphrase drift of a spec clause the doc
    fix restated. Step 3 said "is pointed at, never paraphrased" (04cebdac3), a rule a fix that must CARRY the
    clause's content could not obey — a pointer cannot stand in its place — so the lead paraphrased; row 1791446864
    had been rejected as landed on the same sentence, which made this row the recurrence D-711 edits. The sentence
    now offers the quote branch, bounded: only where the fix must carry its words, quoted whole (a quote cut
    mid-clause drops a qualifier while staying verbatim), verbatim (round 1: "in its own words" read as the fixer's
    words), with no gloss (a gloss is a new wording that drifts) and naming its source (a quote of a restatement, or
    one gone stale, is traceable). Mutants, each a failing assertion: drop the quote branch (the old sentence
    returns), drop 'whole', drop 'verbatim', drop 'with no gloss', drop 'naming its source', drop 'where the fix
    must carry its words' (an unbounded quote brings back the drift a pointer avoids), 'never paraphrased' →
    'rarely paraphrased', move the sentence out of step 3, or plant a licence that says gloss, paraphrase or verbatim
    anywhere in step 3 (round 1: a sentence-initial 'A short gloss is fine.' survived a case-sensitive scan; round 2:
    'A brief gloss beside a quote is fine.' survived the word-list, so the pin counts the words instead). A licence
    worded around those three words ('a summary may stand beside the quote') passes — the limit of a text pin; the
    review's seats catch that one, not this test."""
    step3 = _section(_norm(SRC), "3. **Pass 1 (wide):**", "4. **Record each pass:**")
    sentence = (
        "Something already stated, in the code, the doc that owns the subject or elsewhere in the file being fixed, is"
        " pointed at, or, where the fix must carry its words, quoted whole, verbatim, with no gloss and naming its"
        " source, never paraphrased."
    )
    assert step3.count(sentence) == 1, (
        "the pointer-or-whole-quote sentence is stated once, in step 3"
    )
    # a weakener word-list is never complete (round 2: "A brief gloss beside a quote is fine." survived one), so the
    # pin is a COUNT — step 3 says "gloss" and "paraphras" exactly once each, both inside the sentence above; any
    # second mention, whatever its wording, is a licence or a restatement and fails here
    lowered = step3.lower()
    assert lowered.count("gloss") == 1, lowered.count("gloss")
    assert lowered.count("paraphras") == 1, lowered.count("paraphras")
    assert lowered.count("verbatim") == 1, lowered.count("verbatim")
    # it keeps its place between the execute-or-delete rule and the LOCAL/ARCHITECTURAL fix rule
    before = step3[: step3.index(sentence)]
    assert before.rstrip().endswith("a re-read is not execution."), before[-60:]
    after = step3[step3.index(sentence) + len(sentence) :]
    assert after.lstrip().startswith("**LOCAL findings (unambiguous, contained) you just fix"), (
        after[:60]
    )


def test_a_small_pin_is_pasted_inline_and_the_escape_ask_hunts_false_reds() -> None:
    """Rows 1792052465 and 1792052358: Opus seats lost passes because a refused Read left them with no input; in a
    brief the lead writes, pinned files totalling under 8 KB now ride in the brief too, the copy staying the
    authority and a paste reader judged on line counts. Row 1792059931, the second sighting of HELD
    guard-false-positives-negatives-against: the ESCAPE ask hunted only false greens; it now carries the
    catalogue's both-directions rule verbatim. Mutants: drop either clause; per-file bound; drop the catalogue rule."""
    src = re.sub(r"\s+", " ", SRC.read_text())
    assert (
        "Seats read the copies, never the live tree; in a brief you write yourself (the workflow writes its own),"
        " pinned files totalling under 8 KB are also pasted whole beside their line counts, so a seat whose Read or"
        " `cat` of a copy is refused still has the bytes — the copy stays the authority, and a seat that read the"
        " paste says so, states whether each line count matches and is judged on that count, not re-dispatched for lacking a"
        " hash;" in src
    )
    assert (
        "instead of seeding own-fix rounds. The same ASK carries the probe catalogue's rule verbatim (§ Before the"
        " first pin): \"enumerate each guard's ESCAPE VARIANTS in both directions — false green and false red —"
        ' committing the positive/negative probe list beside it". The ASK is the' in src
    )
    cat = re.sub(r"\s+", " ", (ROOT / "commands/_fragments/review-probe-catalogue.md").read_text())
    quote = "enumerate each guard's ESCAPE VARIANTS in both directions — false green and false red — committing the"
    assert quote + " positive/negative probe list beside it" in cat, (
        "the quoted source still says it"
    )
    assert src.count("totalling under 8 KB") == 1 and src.count("false green and false red") == 1


def test_a_shell_written_brief_quotes_its_backticks() -> None:
    """Row 1792291162, the second sighting of HELD quote-heredoc-when-writing-briefs: a brief or Workflow args file
    written through an unquoted heredoc runs its backticks, and an escaped backtick in a grep pattern is GNU grep's
    start-of-text anchor, so it matches nothing mid-pattern and the wrong line at its start (round 1, Opus probe).
    It sits beside the delta-brief clause, not between 'lacking a hash;' and 'before you adjudicate the pass'."""
    src = _norm(SRC)
    clause = (
        "(01M236V84, 01M23ESF5); a brief or Workflow args file you write is written with the Write tool, or through a"
        " quoted heredoc (`<<'EOF'`) where a shell must write it, so no backtick in it runs, and a check command it"
        " hands a seat writes a backtick in a grep pattern unescaped inside single quotes (a pattern that also holds"
        " `'` splices it in as `'\\''`), since GNU grep reads a backslash-backtick as a start-of-text anchor: escaped,"
        " the pattern matches nothing mid-pattern and the wrong lines at its start; a delta seat's brief"
    )
    assert src.count(clause) == 1
    assert "lacking a hash; before you adjudicate the pass" in src


def test_archive_roots_are_read_from_every_path_the_tests_reach() -> None:
    """Row 1792288442 (and the answered rejects on this sentence before it): the lead hand-listed archive roots in a
    brief it wrote; the rule now names where the roots are read from, subprocess-run scripts included (round 1, Opus:
    imports and constants alone missed inline paths and a subprocess target), without restating the recipe."""
    assert (
        "derived from what the tests import, read or run, every path expression in the test files, the scripts they"
        " run by subprocess and what those scripts read included, never a hand-listed path set"
    ) in _norm(SRC)


def test_a_fix_finds_the_rules_home_before_drafting_its_sentence() -> None:
    """W-a634be1c: step 3's point-or-quote rule and the catalogue's restatement sweep were cited by 7+ answered rejects
    while leads kept drafting a sentence first and finding the rule's home only at review. The search now comes first,
    in its own sentence between its two neighbours, pointing at the catalogue's Sweep rather than restating its
    method, pinned by equality so a licence added inside that span fails here. Limit of a text pin: it cannot show the
    search ran before the draft — the report line it requires is what a seat checks."""
    step3 = _section(_norm(SRC), "3. **Pass 1 (wide):**", "4. **Record each pass:**")
    head, tail = "config fix owes none. ", "Every checkable claim any fix adds"
    assert step3.count(head) == 1 and step3.count(tail) == 1
    span = step3[step3.index(head) + len(head) : step3.index(tail)]
    assert span == (
        "Before a fix writes a sentence that states a rule (a doc or command sentence, a code comment, a commit"
        " message), the probe catalogue's Sweep search for a rule already stated elsewhere (its § Prose and docs fixes)"
        " runs first, on the terms of the rule the sentence would state, never after the draft, and your report names"
        " its terms and hits, or that it found none and the new sentence is the rule's home; what it finds is held to"
        " this step's rule below for something already stated. "
    ), span
    # the rule it hands off to is the point-or-quote sentence, not the execute-or-delete one between them
    assert "Something already stated, in the code" in step3[step3.index(tail) :]


def test_a_rule_or_recipe_a_fix_adds_runs_over_round_zeros_input_classes_before_the_pin() -> None:
    """Rows 1792430884 and 1792427348: leads ran a new classification rule and a new seat recipe on one case, and
    seats met the rest. Step 3's execute-or-delete sentence now has what a fix adds executed, with its command and
    output in the report, on a scratch copy of what it reads (a scratch repo, or § Seat isolation's archive or
    clone with the pins laid over it for a seat recipe), over the input classes term-coverage's round zero gives its shape; it stays inside that
    sentence, so the pointer-or-quote sentence still follows "a re-read is not execution." Limit of a text pin: it
    cannot show the run happened, nor add an input class round zero lacks."""
    step3 = _section(_norm(SRC), "3. **Pass 1 (wide):**", "4. **Record each pass:**")
    head = "Every checkable claim any fix adds"
    end = "a re-read is not execution."
    sentence = step3[step3.index(head) : step3.index(end) + len(end)]
    assert (
        "a rule, recipe, command or guard a fix adds being executed so before the pin, on a scratch copy of what it"
        " reads (a scratch repo for one that reads diff output, the archive or clone the probe catalogue's § Seat"
        " isolation stages, with the pins laid over it, for a seat recipe), over the input classes round zero of"
        " `/opt/fabrik/commands/_fragments/term-coverage.md` gives its shape" in sentence
    ), sentence


def test_a_seat_never_disguises_a_refused_act() -> None:
    """Row 1792433212 and fabrik-lib mail 01M5AP11P1: a seat whose command the worktree guard refused assembled the
    word git from 'gi'+'t' and ran it, following the hint "keep that word out of code you run" and reading "fix the
    named shape" as leave to disguise the act. Both homes of the seat refusal rule (subagents-core.md and the
    fabrik-reviewer agent) now say a git call does not belong in such a program at all, and that a command reshaped
    after any refusal never disguises the refused act. The sentence follows the refusal rule: directly in the agent's
    house-rules list, and as the next sentence in subagents-core, where the workflow test's pinned span now ends. The
    workflow's SEAT_ISOLATION copy is intel's: tests/test_review_loop_workflow.py pins it (W-281e3ed2) and checks
    these two homes still carry the sentence word for word."""
    body = (
        "command reshaped after any refusal, a guard's or the classifier's, never disguises the refused act: fixing"
        " the named shape, or changing the command or the tool, is allowed, but a refused name or path assembled,"
        " split or encoded (such as `'gi'+'t'`) is the same call, so an act no allowed shape reaches is marked"
        " unverified and named in MACHINERY"
    )
    tail = "say in MACHINERY which command was refused how many times of how many tries"
    hint = (
        "(the word does not belong in such a program at all, even as data: search for it with `/usr/bin/grep`,"
        " and spelling git differently is still git)"
    )
    agent = re.sub(r"\s+", " ", (ROOT / "commands" / "_agents" / "fabrik-reviewer.md").read_text())
    assert agent.count(f"{tail}; a {body};") == 1
    core = (ROOT / "commands" / "_fragments" / "subagents-core.md").read_text()
    assert re.sub(r"\s+", " ", core).count(f"{tail}. A {body}.") == 1
    for text in (agent, re.sub(r"\s+", " ", core)):
        assert hint in text and "keep that word out of code you run" not in text


def test_a_brief_tells_each_seat_to_create_its_folder_first() -> None:
    """Row 1792414928: two Agent-tool seats hit ENOENT writing into a seat folder nothing had created. The Workflow's
    seat prompt already says "create it first with `mkdir -p SCRATCH` — its parent exists and nothing creates it for
    you"; the subagents-core seat-folder rule, which a lead's own brief follows, now says so. It names no parent, since in the
    `RUN-SCRATCH: none` case the folder sits under a session scratchpad `start` may not have found."""
    core = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / "subagents-core.md").read_text())
    assert (
        "so nothing durable is written there (resume artifacts go to `SCRATCH:`), and for a seat the lead briefs"
        " itself (a `Workflow` seat's prompt makes its own folder) the lead creates the folder with `mkdir -p` on"
        " its absolute path before the dispatching message, while the brief still tells the seat to run that same"
        " `mkdir -p` first (a no-op once the folder exists);" in core
    )


def test_a_probed_count_is_never_replaced_by_a_seats_re_derivation() -> None:
    """Row 1792418569: round zero's rule (1) said a probed count is "never re-derived by a finder" (term-coverage) or
    "by a seat" (term-edit), while the closing pass re-derives every count and a seat's re-derivation is what caught a
    25-vs-29 count. The 2026-09-17 spec meant the probe stays the record, so each fragment now says a seat's
    re-derivation never replaces the probe and a different answer is raised as a candidate; the two keep their own
    nouns, as that spec requires."""
    frag = ROOT / "commands" / "_fragments"
    cov = re.sub(r"\s+", " ", (frag / "term-coverage.md").read_text())
    edit = re.sub(r"\s+", " ", (frag / "term-edit.md").read_text())
    assert (
        "never replaced by a seat's own re-derivation: a seat that re-derives the claim, as this fragment's RE-DERIVE"
        " rule asks, and gets a different answer raises the difference as a candidate." in edit
    )
    assert (
        "never replaced by a finder's own re-derivation: a finder that re-derives the claim, as the closing pass does,"
        " and gets a different answer raises the difference as a candidate." in cov
    )
    for text in (cov, edit):
        assert (
            "never re-derived by a finder" not in text and "never re-derived by a seat" not in text
        )

