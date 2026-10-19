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


def _section(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))] if end else text[i:]


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


def test_the_catalogue_sections_hold_their_probes() -> None:
    """One anchor line per section, so a section moved or dropped fails here."""
    cat = _norm(CAT)
    pin = _section(cat, "## Before the first pin", "## The brief's hunt lines")
    assert "Trace the entry path: the first caller that reaches the fixed function" in pin
    assert "One mutant per clause the edit states and one per guard it adds or alters" in pin
    hunt = _section(cat, "## The brief's hunt lines", "## Graders")
    assert "every caller of a changed exit code, output line or gated script" in hunt
    assert "who waits on a new lock and behind what" in hunt
    graders = _section(cat, "## Graders", "## Prose and docs fixes")
    assert "Grade the PROPERTY across every example, never one spelling" in graders
    assert "isolation is proven by a reversed-order run and by removing the fixture" in graders
    prose = _section(cat, "## Prose and docs fixes", "## Seat isolation")
    assert "re-read an inserted sentence with the one after it" in prose
    iso = _section(cat, "## Seat isolation", "## Loop bookkeeping")
    assert (
        "A SEAT never runs `git worktree add` on the live repo (its metadata lands in the shared `.git`)"
        in iso
    )
    assert "never `resumeFromRunId`" in _section(cat, "## Loop bookkeeping", None)
    loop = _section(cat, "## Loop bookkeeping", None)
    assert "`confirmed` counts DEFECTS, never checks passed" in loop


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


def test_a_revendor_brief_hands_the_byte_identity_result_as_a_claim() -> None:
    """Row 1791769363 (D-776); rows 1791896579 and 1791905875: the identity diff reads the source's committed
    blob, and the brief names the source's own regression test; row 1791918689: byte identity holds while the
    copy reads a name a module vendored beside it lacks. Pinned in the premise bullet. Not seen: a brief
    that names a test but never runs it; the seats' transcripts own that."""
    premise = _section(_norm(CAT), "- The premise:", "## Graders")
    assert (
        "a re-vendor brief hands the seats the lead's executed byte-identity result (the diff command and its output) as"
        " a claim to attack — the diff reads the source's COMMITTED blob at the SHA the copy records (a `VENDORED-FROM`"
        " header, else the `Vendored-From:` trailer of the commit that vendored it; HEAD when neither does: `git -C"
        " <source> show <sha>:<source path>`) against the copy minus that"
        " header, never the source's working file, where a sibling's uncommitted edit reads as drift — and the brief"
        " names the source's own regression test for the file at that SHA, run with its import path pointed at the"
        " copy (or says the source has none) and whether that test assumes a co-located hub tree, so a standalone"
        " run of it is a known false red; they re-run that command and that test first, then spend on what byte"
        " identity cannot show: the"
        " vendored copy's own header, every importer of it, and every name it reads from each module vendored"
        " beside it (its `from … import` names and each `module.attr` use), each shown present in that module's copy."
        in premise
    )


def test_a_dependency_claim_is_checked_against_the_dependencys_own_case_set() -> None:
    """/fabrik-review row 1791925061, recurring held subject guard-key-aliases-from-the-target-library (row
    1791919154): a guard and a docs sentence were checked against the cases the author named, not the aliases and
    branches the dependency itself has. Bounded to the claim's keys; docs plus a probe where no source is readable."""
    premise = _section(_norm(CAT), "- The premise:", "## Graders")
    assert (
        "asks for the claim at that version; a claim about what a dependency accepts or does (a guard over its keys, a"
        " docs sentence about its behaviour) is checked against every case the dependency defines for the keys or"
        " behaviour the claim covers — each branch and alias in its source at that version, else its versioned"
        " reference docs plus an executed probe — never only the cases the author listed;"
    ) in premise


def test_seat_isolation_names_every_root_the_tests_import_read_or_run() -> None:
    """Rows 1791774523, 1791785471: the archive roots and the live repo."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    assert "the brief extends it to every top-level path the tests import, read or run" in iso
    assert "`templates/`, reads `.windsurf/` or runs `scripts/` by subprocess" in iso
    assert (
        "names the live repo as the checkout `git rev-parse --show-toplevel` prints, never `/opt/fabrik` from a worktree"
        in iso
    )


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


def test_a_new_sibling_of_a_pinned_line_reads_its_comment_first() -> None:
    """Row 1791836370."""
    before = _section(_norm(CAT), "## Before the first pin", "## The brief's hunt lines")
    assert (
        "before adding a sibling of a pinned or guarded line, read the comment on the line it copies"
        in before
    )


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


def test_seats_run_scripts_from_the_archive_and_pin_callees() -> None:
    """Rows 1791842699, 1791841558 (D-792)."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    assert (
        "A script a seat runs is run from its archive copy with every path argument under scratch (a script may treat any argument as a write path)"
        in iso
    )
    assert (
        "the pin carries the changed files' one-hop callees that are repo files (`review_loop_ledger.py pin` refuses the whole list when one path is missing, a symlink or outside the repo root)"
        in iso
    )


def test_a_silent_refuter_is_already_retried_once_and_marked_failed() -> None:
    """Row 1791826392 (mailed): the workflow already retries; the ledger's `read` table is the gap."""
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text()
    assert "const retry = await refuteCall(r.slice, missing, '-retry')" in js
    assert "STILL UNANSWERED (refuter failed)" in js


def test_a_reimplemented_tool_is_checked_against_its_own_output() -> None:
    """Row 1791844847: a fix modelling js-yaml's merge from memory took three rounds."""
    text = _norm(CAT)
    lead = text[
        text.index(
            "## Before the first pin, and again before each delta pin (the lead executes)"
        ) : text.index("- One mutant per clause")
    ]
    assert (
        "or reimplement another tool's semantics (a YAML merge, a compose override), and prove parity by an executable diff against that tool's own output over its edge cases (for a merge: nesting, mixed types, cycles) before the fix lands, never a model from memory"
        in lead
    )


def test_a_matcher_sentence_is_executed_over_its_input_space() -> None:
    """Row 1791851271: two own-fix rounds came from a sentence about a regex nobody ran. Rows 1792088209 (a
    recurrence of held guard-false-positives-negatives-against) and 1792086831 extend it to a guard's accepts-or-covers
    sentence, written from both sides of its executed inputs, the seats' returned variants included."""
    text = _norm(CAT)
    claims = text[text.index("- Claims:") : text.index("- A site a round re-opened")]
    assert (
        "a sentence (a comment, a docstring, a doc line) describing a matcher, regex or guard written from its input"
        " space executed on both sides (punctuation, underscore, empty, the lead's escape variants and every one the"
        " seats returned) before the pin, never from its subject's own docstring;" in claims
    )


def test_a_brief_names_the_fix_by_sha_never_a_bare_range() -> None:
    """Row 1791852611: a two-dot range over a shared branch carried another item's 1278 lines."""
    text = _norm(CAT)
    assert (
        "The brief names the fix as `git show <sha>` — each sha when the fix spans several commits — or a pathspec-scoped diff, never a bare range on a branch others commit to"
        in text
    )


def test_a_compose_overlay_is_read_through_its_merged_render() -> None:
    """Row 1791860340: precedence and port exposure only show in the merged compose render."""
    text = _norm(CAT)
    surfaces = text[text.index("- Surfaces:") : text.index("- The premise:")]
    assert (
        "a changed compose overlay read through its merged render (`docker compose -f <base> -f <overlay> config`)"
        in surfaces
    )


def test_a_shifted_cite_is_remapped_by_content_in_one_script() -> None:
    """Row 1791866581 (recurs held anchor-sweep-auto-compares-symbols): remapping by number took two passes."""
    text = _norm(CAT)
    sweep = text[text.index("- Sweep:") : text.index("- Claims:")]
    assert (
        "a `path:line` cite a merge or an edit shifted, remapped by CONTENT in one script over every doc that cites the file"
        in sweep
    )


def test_a_range_cite_grader_checks_both_ends() -> None:
    """Row 1791914277: a grader that checks a cited range's first line alone passes when its last line moved. Rows
    1792259629 and 1792258433 (recurring held test-message-content-mutants): a fixed-prose or deterministic-message
    grader asserts by equality, so an appended clause or a leaked value fails it — as this test does."""
    text = _norm(CAT)
    bullet = _section(text, "- Grade the PROPERTY", "- Each parser-output shape").strip()
    assert bullet == (
        "- Grade the PROPERTY across every example, never one spelling; a new assertion must fail when its subject "
        "is absent (an absence assertion over never-written state is vacuous); a grader EXECUTES an executable "
        "subject, through the real production adapter and the consumer's entry point (the command's output, as the "
        "gate passes files by name), never reads it; a premise guard asserts at the call site, not on constants; a "
        "grader of fixed prose or of a deterministic message asserts the whole sentence, bullet or message it pins "
        "by equality (`==` against all of it, every line of a message, never `in`, a prefix, a suffix or a regex "
        "over part of it), so an added clause or a leaked value fails it, and a grader of that text's position, of "
        "its absence or of a property across its examples sits beside that equality grader, never in place of it; a"
        " grader of MOVED text (a sentence, clause, bullet or row), added in the edit that moves it, also fails "
        "when the text sits at its old position; a test-quality seat checks docstring claims against the scan; a "
        "fix recipe handed to a coder names one input it must leave unchanged and the test that holds it; a grader "
        "of a `path:N-M` cite asserts its first line AND its last line still hold the text the cite backs."
    )


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


def test_the_graders_section_pins_moved_texts_old_position() -> None:
    """Row 1791894842: a fix that moved a sentence kept a grader that passed with the sentence folded back into its
    old paragraph, so a later round found the gap. The clause is pinned as the contiguous span from the premise-guard
    clause before it to the test-quality clause after it, inside the Graders section, so the clause moved alone,
    truncated, or qualified inside the span reds. Not seen: a qualifier placed before the span, a contradicting line
    elsewhere, the three clauses moved together, and a review grader that names the old position but asserts nothing
    there — the last is the cheapest bypass, and a seat reading that grader owns it."""
    graders = _section(_norm(CAT), "## Graders", "## Prose and docs fixes")
    assert (
        "a premise guard asserts at the call site, not on constants; a grader of fixed prose or of a deterministic "
        "message asserts the whole sentence, bullet or message it pins by equality (`==` against all of it, every "
        "line of a message, never `in`, a prefix, a suffix or a regex over part of it), so an added clause or a "
        "leaked value fails it, and a grader of that text's position, of its absence or of a property across its "
        "examples sits beside that equality grader, never in place of it; a grader of MOVED text (a sentence, "
        "clause, bullet or row), added in the edit that moves it, also fails when the text sits at its old "
        "position; a test-quality seat checks docstring claims against the scan;" in graders
    )


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


def test_a_brief_states_the_count_to_report_never_the_expected_one() -> None:
    """/fabrik-review row 1791931043: a closing-pass brief that names the count, verdict or output the lead expects is a leading question;
    no reached line said a brief must not carry it (Opus audit 2026-10-14: no governing line)."""
    loop = _section(_norm(CAT), "## Loop bookkeeping", None)
    assert (
        "each brief embeds its ledger text and states what the seat must report (a count, a verdict, an output),"
        " never the value the lead expects; the closing-pass brief"
    ) in loop


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


def test_a_database_test_runs_with_the_connection_the_lead_proved() -> None:
    """/fabrik-review-scoped rows 1791980872, 1790801583 and 1791515801: three projects' seats skipped,
    re-implemented or failed a database test because no `.env` reaches a seat. The brief names the variable
    and the connection form the lead proved by one connect, and a seat's own database probe is covered too."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    assert (
        "a test that needs a database (the suite skips or fails it without a database variable: no `.env` is"
        " copied, and the `.invalid` dummy serves imports only) runs with the variable the suite reads"
        " (`TEST_DATABASE_URL`, an isolated `DATABASE_URL`) in place of that dummy, and a seat probe that must connect"
        " uses the same variable; both connect over the form the lead proved by one connect before the pin (a"
        " unix-socket DSN where TCP `localhost` fails password auth), the variable and the form named in the brief, and"
        " where only a password form connects the lead runs that test or probe itself and quotes its result, never"
        " writing the password into a brief"
    ) in iso


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


def test_seat_isolation_names_where_the_editable_pth_sits() -> None:
    """Row 1792294821, a third verdict on the archive-roots subject (1792228739, 1792229273): seats feared an editable
    install's .pth shadowing a copied src; under PIN_IMPORT the copy sits ahead of it (probed), so the catalogue says
    where the live src can still win instead of warning about a shadow that the recipe prevents."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    anchor = "never `/opt/fabrik` from a worktree."
    start = iso.find(anchor)
    end = iso.find("The pins line follows", start)
    assert start != -1 and end != -1, (
        "the worktree clause and the pins-line sentence still bound the note"
    )
    sentence = iso[start + len(anchor) : end].strip()
    assert sentence == (
        "An editable install's `.pth` entry never outranks a copy placed as `PIN_IMPORT` says; live code still runs"
        " instead of the pin through a `PYTHONPATH` entry (`PIN_IMPORT`), a pytest run from the live repo"
        " (`PYTEST_PINS`) and a child process started with its own `env=`, which resolves the `.pth` again."
    ), sentence
    assert "is a false red without it) and names the live repo" in iso, (
        "the roots parenthesis holds no import-order note"
    )


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
    src = _norm(SRC)
    pointer = (
        "A delta pass's brief also names the previous pass's `base_sha` and pins_dir, as the probe catalogue's § Seat"
        " isolation says."
    )
    assert src.count(pointer) == 1
    step5 = _section(src, "5. **Loop:**", "6. **Gate + close:**")
    assert pointer in step5
    step4 = _section(src, "4. **Record each pass:**", "5. **Loop:**")
    assert (
        "shown by diffing that round's pin against the next pass's pin once the lead has stated the difference is that"
        " round's fix alone, as the probe catalogue's § Seat isolation says, or for a broken reader by"
        in step4
    )


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
    workflow's SEAT_ISOLATION copy is intel's and is mailed, not checked here."""
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


def test_a_brief_says_what_the_pin_holds_and_where_the_rest_is_read() -> None:
    """Rows 1792446899, 1792432410 and 1792416541: a pin holds only the files it names, so seats either missed a file a
    fix pointed at or copied the rest of a module from the live tree. The isolation bullet now pins each file a fix's
    text points at and names the base tree, with the pins laid over it, as the place every other file is read."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    assert (
        "or outside the repo root). The pin also carries each file a fix's text points at by path, and the brief says"
        " the pin holds only the files it lists, so a seat reads any other file, the rest of a changed module's"
        " directory included, from the base tree with the pins laid over it (`<pins_dir>.base` when the pin was taken"
        " `--base`, else the archive of its `base_sha`), never from the live tree beyond what the seat prompt's recipes"
        " (`PIN_IMPORT`, `PYTEST_PINS`, `GATE_PINS`) take from the live disk and name UNPINNED." in iso
    )


def test_a_brief_tells_each_seat_to_create_its_folder_first() -> None:
    """Row 1792414928: two Agent-tool seats hit ENOENT writing into a seat folder nothing had created. The Workflow's
    seat prompt already says "create it first with `mkdir -p SCRATCH` — its parent exists and nothing creates it for
    you"; the subagents-core seat-folder rule, which a lead's own brief follows, now says the same."""
    core = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / "subagents-core.md").read_text())
    assert (
        "so nothing durable is written there (resume artifacts go to `SCRATCH:`), and the brief tells each seat to"
        " create its folder first with `mkdir -p` on the absolute path, since its parent exists and nothing creates it"
        " for the seat;" in core
    )

