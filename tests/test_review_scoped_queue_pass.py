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
    assert (
        "never touch the pin while its seats run (the seats read the pin; you edit the working tree once every seat"
        " has returned and you have read the pass)" in te
    )
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
        "instead of seeding own-fix rounds. The same ASK carries the probe catalogue's rule verbatim (§ Before the"
        " first pin): \"enumerate each guard's ESCAPE VARIANTS in both directions — false green and false red —"
        ' committing the positive/negative probe list beside it"' in src
    )
    cat = re.sub(r"\s+", " ", (ROOT / "commands/_fragments/review-probe-catalogue.md").read_text())
    quote = "enumerate each guard's ESCAPE VARIANTS in both directions — false green and false red — committing the"
    assert quote + " positive/negative probe list beside it" in cat, (
        "the quoted source still says it"
    )
    assert src.count("totalling under 8 KB") == 1 and src.count("false green and false red") == 1


def test_a_hand_written_brief_points_seats_at_the_pin_import_recipe_and_an_import_brief_is_isolated_too() -> (
    None
):
    """Rows 1792082763 and 1792081436 (fleet), the 15th and 16th on this subject: the command pointed at the
    workflow's PIN_IMPORT/PYTEST_PINS recipe but never told a lead writing a brief by hand to send seats to it,
    so a fleet brief used `--rootdir=<copy>` and imported the live checkout's package, and seats retried
    importing a pinned script. § Seat isolation also bound only briefs that RUN TESTS, not ones that import
    pinned code. Mutants: drop the sentence; drop 'or imports pinned code' from the catalogue header or the
    command; rename a placeholder inside PIN_IMPORT or PYTEST_PINS, or let PIN_IMPORT stop deriving ROOTS."""
    cat = _norm(CAT)
    iso = _section(cat, "## Seat isolation", "## Loop bookkeeping")
    assert (
        "A brief the lead writes itself tells each seat to read and follow `PIN_IMPORT` — and `PYTEST_PINS` when"
        " it runs pytest — in `.claude/workflows/fabrik-review-loop.js`, and gives the values that recipe's"
        " `${args.base_sha}` and `${args.pins_dir}` stand for (and `${args.base_pin_dir}` when the lead wrote a"
        " base copy) and the seat's own folder as `SCRATCH`; the seat derives `ROOTS` as the recipe says, plus the roots this"
        " section's next sentence has the brief add, and the brief carries no import or pytest recipe of the"
        " lead's own" in iso
    )
    assert (
        "§ Seat isolation excepted: it applies whole in every brief that runs tests or imports pinned code"
        in cat
    )
    assert (
        "Its § Seat isolation applies whole, whatever the shape, in every brief that runs tests or imports pinned"
        " code:" in _norm(SRC)
    )
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text().splitlines()
    starts = {
        name: next(n for n, line in enumerate(js) if line.startswith(f"const {name} = "))
        for name in ("PIN_IMPORT", "PYTEST_PINS", "BASE_PIN")
    }
    # each recipe is one `const` line; BASE_PIN's ternary carries its text on the line after it
    consts = {name: js[n] for name, n in starts.items()}
    consts["BASE_PIN"] += js[starts["BASE_PIN"] + 1]
    # each placeholder the sentence names, read inside the constant that carries it — the same tokens appear in
    # other constants of the file, so a whole-file check stays green when the recipe drops one (round-1 finding);
    # ROOTS is read where the archive step uses it, since its prose mention survives a dropped use (round 2)
    for name, tokens in (
        (
            "PIN_IMPORT",
            (
                "${BASE_PIN}",
                "${args.pins_dir}",
                "SCRATCH/arch.tar ${args.base_sha} ROOTS",
                "ROOTS every",
            ),
        ),
        ("PYTEST_PINS", ("${args.base_sha}",)),
        ("BASE_PIN", ("args.base_pin_dir", "cp -r ${args.base_pin_dir} SCRATCH/arch")),
    ):
        for token in tokens:
            assert token in consts[name], (
                f"{name} lost {token!r}, which the catalogue sentence names"
            )


def test_archive_roots_are_read_from_every_path_the_tests_reach() -> None:
    """Row 1792288442 (and the answered rejects on this sentence before it): the lead hand-listed archive roots in a
    brief it wrote; the rule now names where the roots are read from, subprocess-run scripts included (round 1, Opus:
    imports and constants alone missed inline paths and a subprocess target), without restating the recipe."""
    assert (
        "derived from what the tests import, read or run, every path expression in the test files, the scripts they"
        " run by subprocess and what those scripts read included, never a hand-listed path set"
    ) in _norm(SRC)


def test_a_mutant_is_killed_against_whole_test_files_after_each_fix() -> None:
    """Row 1792406410: a mutation runner's `-k` filter cut before a fix added a test never ran that test, so a
    re-run mutant read as killed or surviving on a stale selection. W-33b84ff0: rows 1792401243, 1792273324,
    1792034388, 1791852372 and 1791939536 found a new script's or a fix's guards untested over several closing passes
    while the bullet asked one mutant per clause only, so it now asks one per guard it adds or alters, quoting
    term-coverage rule (4)'s removed-guard proof rather than restating it. The whole bullet is pinned by equality, so
    an added licence or a negation fails here, and the quote is checked against rule (4)'s own text."""
    tc = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    rule4 = tc[tc.index("(4) **A GRADER IS PROVEN") : tc.index("(5) **A GRADER OBSERVES")]
    assert (
        "each grader is proven it CAN fail by REMOVING THE GUARD, never by breaking an expression inside it"
        in rule4
    )
    pin = _section(_norm(CAT), "## Before the first pin", "## The brief's hunt lines")
    assert (
        pin.count("- One mutant per clause") == 1 and pin.count("- Run the repo's structural") == 1
    )
    bullet = _section(pin, "- One mutant per clause", "- Run the repo's structural").strip()
    assert bullet == (
        "- One mutant per clause the edit states and one per guard it adds or alters (that guard removed —"
        ' term-coverage rule (4): "each grader is proven it CAN fail by REMOVING THE GUARD, never by breaking an'
        ' expression inside it"), written as a literal before/after (an ordering claim names its mutant); re-run every prior mutant and the reproducing probe after each fix (a seat re-running a delta'
        " brief's mutant ids too) against every test file the change touched or added, collected again after the fix"
        " with no selection that leaves a test out (`-k`, node ids, `--lf`, `--deselect`, `-m`, `--ignore`) beyond"
        " term-coverage rule (4)'s environment-bound deselection (§ Seat isolation's exact node ids are for a seat's"
        " other test runs); probe each new grader with its mutant."
    ), bullet


def test_a_delta_brief_carries_the_bounded_hops_reader_run_inputs() -> None:
    """W-e2ff8f36: D-1047's reader run (a reader passing on the previous round's pin and failing on it with only the fix
    hunks applied) had no inputs in any brief. § Seat isolation now names them, has the lead state that the two pins
    differ by the round's fix alone (committed or not), and runs each reader once on each pin by the seat's archive
    recipe, pinned whole by equality; both review commands point at it; step 4's own-fix pin diff waits on the same
    check. The `unverified` route the bullet sends a barred reader to is checked to sit in § Loop bookkeeping."""
    cat = _norm(CAT)
    iso = _section(cat, "## Seat isolation", "## Loop bookkeeping")
    assert iso.count("- A delta brief also names") == 1
    bullet = iso[iso.index("- A delta brief also names") : iso.index("- No `uv`/`pip`")].strip()
    assert bullet == (
        "- A delta brief also names the previous pass's `base_sha` (for the working-tree pin "
        "`/fabrik-review-scoped` step 5 takes, the HEAD its `MANIFEST.json` records as `base_sha`, read back, "
        "never verified, since no md5 manifest covers it, and null in a repo with no commit; for any other "
        "pin the brief names the commit itself, since one taken `--base` records that commit (else its "
        "`--from` ref) and one written before `base_sha` was recorded has none) and pins_dir, for the bounded "
        "hop's reader run (a reader passing on the previous round's pin and failing on it with only the fix "
        "hunks applied). The lead first diffs the two pins' files (`diff -r -x change.diff -x 'MANIFEST*' "
        "<previous pins_dir> <this pins_dir>`) and the two `base_sha`s (`git diff --name-only <previous "
        "base_sha> <this base_sha>`), and states in the brief that the difference is the round's fix alone, "
        "committed or not, naming any other hunk or path, which leaves every reader it touches `unverified` "
        "(each `Only in` line, a path one pin holds and the other does not, is named too, and classed from "
        "`git diff --name-status <previous base_sha> <this base_sha>` for what the fix committed and `git "
        "status --short --untracked-files=all --ignored -- <path>` for what it did not (a fix can be both), "
        "since a removed path cannot be pinned and `change.diff` carries no entry for it: a path the fix "
        "added, modified, removed or renamed is the fix's own, and its readers run on both pins, a removal or "
        "rename whose old path this pass's `base_sha` still holds leaving those readers `unverified`; any "
        "other path pinned in only one pass is another path; a directory line covers every listed path under "
        "it; a fix's own path's readers are the tests the `tests/` grep above finds and, for a document, the "
        "citers the heading-or-term grep below finds, and an importer outside `tests/` is named and left "
        "`unverified`); the seat then runs each reader once on each pin by the `PIN_IMPORT`/`PYTEST_PINS` "
        "recipe with that pin's own `base_sha`, and greps a heading or term another section cites over each "
        "pin's tree, where its citers live; a reader the pre-pin section keeps the lead's (\"one that writes a "
        "live store, sends, commits, deploys or reaches a host\") takes § Loop bookkeeping's `unverified` "
        "route; and a reader that fails on the previous pin is no evidence of a break, and is `RECORDED` with "
        "its destination."
    ), bullet
    pre = _section(cat, "## Before the first pin", "## The brief's hunt lines")
    assert (
        "one that writes a live store, sends, commits, deploys or reaches a host stays the lead's"
        in pre
    )
    ledger = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    row = ledger[ledger.index("| D-1051 |") :]
    row = row[: row.index("\n")]
    assert (
        "§ Loop bookkeeping's `unverified` route" in row
        and "§ Seat isolation's existing `unverified`" not in row
    )
    assert iso.index("The brief names the fix as `git show <sha>`") < iso.index(
        "- A delta brief also names"
    )
    route = "a refuter that needs a forbidden surface marks it `unverified` naming the surface, and the lead executes it"
    assert route in cat[cat.index("## Loop bookkeeping") :]
    assert "git apply" not in bullet


def test_a_rule_or_recipe_a_fix_adds_runs_over_round_zeros_input_classes_before_the_pin() -> None:
    """Rows 1792430884 and 1792427348: leads ran a new classification rule and a new seat recipe on one case, and
    seats met the rest. Step 3's execute-or-delete sentence now has what a fix adds executed, with its command and
    output in the report, on a scratch copy of what it reads (a scratch repo, or § Seat isolation's archive or
    clone with the pins laid over it for a seat recipe), over the input classes term-coverage's round zero gives its shape; it stays inside that
    sentence, so the pointer-or-quote sentence still follows "a re-read is not execution." Limit of a text pin: it
    cannot show the run happened, nor add an input class round zero lacks."""
    zero = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    assert "**Round zero — the orchestrator's OWN pre-pin probe" in zero
    assert "the fix's own INPUT space is enumerated and executed before the pin" in zero


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
        "never replaced by a finder's own re-derivation: a finder that re-derives the claim, as the closing pass does,"
        " and gets a different answer raises the difference as a candidate." in cov
    )
    assert (
        "never replaced by a seat's own re-derivation: a seat that re-derives the claim, as this fragment's RE-DERIVE"
        " rule asks, and gets a different answer raises the difference as a candidate." in edit
    )
    for text in (cov, edit):
        assert (
            "never re-derived by a finder" not in text and "never re-derived by a seat" not in text
        )


def test_a_fix_reshaping_a_rule_subject_lists_the_old_cases_before_drafting() -> None:
    """Row 1792730405 (a recurrence of held fix-narrowed-input-strands-defensive-guards): a round-1 fix split a rule's
    subject, and the cases the new wording no longer covered cost the next two rounds. The Sweep bullet, read before
    the draft, quotes /fabrik-review's replaced-form question and its enumeration rule verbatim, and names the record
    each command keeps the list in."""
    cat = re.sub(r"\s+", " ", CAT.read_text())
    question = "does the new form still hold EVERY shape the form it replaces held"
    quote = (
        "the shapes enumerated from the OLD form before the fix is drafted, never from the new one"
    )
    assert (
        "held to `/fabrik-review-scoped` step 3's rule for what is already stated; a fix that narrows, widens or splits"
        " a rule's subject is held to `/fabrik-review`'s \""
        + question
        + '", with "'
        + quote
        + '": here each case'
        " no new clause covers, two now cover or only the new wording reaches, listed with where it now lands or, with"
        " its reason, that it is dropped on purpose, where your command records the fix (`/fabrik-review`'s Pass Ledger `method:` cell,"
        " `/fabrik-review-scoped`'s report);"
    ) in cat
    review = re.sub(r"\s+", " ", (ROOT / "commands" / "_sources" / "fabrik-review.md").read_text())
    assert question in review and quote in review


def test_a_committed_surface_is_pinned_from_its_commit_by_its_shape() -> None:
    """Rows 1792829562, 1792779119, 1792774372: three leads pinned a surface they had already committed with step 5's
    working-tree recipe and got an empty change.diff, because the --from/--base rule lives only in the catalogue's
    § Seat isolation, which a docs-only brief need not load. Step 5 now quotes that clause whole, adds the two shapes
    it leaves out (a merge as the last commit; a surface partly committed, which `pin --from` refuses or misreads) and
    names the base_sha such a pin records; the quote must stay word-for-word the catalogue's."""
    rule = (
        "a fix already committed is pinned with `--from <its last commit>`, plus `--base <the commit before the fix>`"
        " when it spans several, since a working-tree pin of a committed surface prints each file `UNCHANGED` with"
        " only a header line in its `change.diff`, and `--base` without `--from` pins the working tree, a sibling's"
        " later commit or uncommitted edit included."
    )
    assert (
        "so committing the surface leaves a pin taken before the commit valid, and an untracked file counts like a"
        " tracked one; a working-tree pin taken after the commit is the one that goes wrong. A surface already"
        " committed when you pin it — a docs-only change included — is pinned as the probe catalogue's § Seat"
        ' isolation says: "'
        + rule
        + '" A last commit that is a merge counts as several (`--from` alone diffs against its first parent). A'
        " surface partly committed and partly not (an untracked file included) is a shape `--from` cannot pin"
        " — it refuses a path absent at that commit and takes a file's committed bytes, not its uncommitted edit —"
        " so it is pinned from the working tree with `--base <the commit before the fix>`, its `change.diff` then"
        " carrying any sibling commit to those files too. Either way the brief's `base_sha` is the one that pin"
        " records (its `--base`, else its `--from` ref), read back from it, not a fresh `git rev-parse HEAD`. Seats"
        " read the copies"
    ) in _norm(SRC)
    assert (
        "`base_sha` = `git rev-parse HEAD` at that moment (a surface already committed takes its pin's own"
        " `base_sha`, below), then"
    ) in _norm(SRC)
    assert rule in _norm(CAT)
