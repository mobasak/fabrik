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


def test_the_catalogue_sections_hold_their_probes() -> None:
    """One anchor line per section, so a section moved or dropped fails here."""
    cat = _norm(CAT)
    pin = _section(cat, "## Before the first pin", "## The brief's hunt lines")
    assert "Trace the entry path: the first caller that reaches the fixed function" in pin
    assert "One mutant per clause the edit states, written as a literal before/after" in pin
    hunt = _section(cat, "## The brief's hunt lines", "## Graders")
    assert "every caller of a changed exit code, output line or gated script" in hunt
    assert "who waits on a new lock and behind what" in hunt
    graders = _section(cat, "## Graders", "## Prose and docs fixes")
    assert "Grade the PROPERTY across every example, never one spelling" in graders
    assert "isolation is proven by a reversed-order run and by removing the fixture" in graders
    prose = _section(cat, "## Prose and docs fixes", "## Seat isolation")
    assert "re-read an inserted sentence with the one after it" in prose
    iso = _section(cat, "## Seat isolation", "## Loop bookkeeping")
    assert "A SEAT never runs `git worktree add` (its metadata lands in the shared `.git`)" in iso
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
    blob, and the brief names the source's own regression test. Pinned in the premise bullet. Not seen: a brief
    that names a test but never runs it; the seats' transcripts own that."""
    premise = _section(_norm(CAT), "- The premise:", "## Graders")
    assert (
        "a re-vendor brief hands the seats the lead's executed byte-identity result (the diff command and its output) as"
        " a claim to attack — the diff reads the source's COMMITTED blob at the SHA the copy records (a `VENDORED-FROM`"
        " header, else the `Vendored-From:` trailer of the commit that vendored it; HEAD when neither does: `git -C"
        " <source> show <sha>:<source path>`) against the copy minus that"
        " header, never the source's working file, where a sibling's uncommitted edit reads as drift — and the brief"
        " names the source's own regression test for the file at that SHA, run with its import path pointed at the"
        " copy (or says the source has none); they re-run that command and that test first, then spend on what byte identity cannot show: the"
        " vendored copy's own header and every importer of it" in premise
    )


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
    """Row 1791851271: two own-fix rounds came from a sentence about a regex nobody ran."""
    text = _norm(CAT)
    claims = text[text.index("- Claims:") : text.index("- A site a round re-opened")]
    assert (
        "a sentence describing a matcher or regex executed over its input space (punctuation, underscore, empty) before the pin"
        in claims
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
    """Row 1791914277: a grader that checks a cited range's first line alone passes when its last line moved."""
    text = _norm(CAT)
    bullet = _section(text, "- Grade the PROPERTY", "- Each parser-output shape").strip()
    assert bullet == (
        "- Grade the PROPERTY across every example, never one spelling; a new assertion must fail when its subject is"
        " absent (an absence assertion over never-written state is vacuous); a grader EXECUTES an executable subject,"
        " through the real production adapter and the consumer's entry point (the command's output, as the gate passes"
        " files by name), never reads it; a premise guard asserts at the call site, not on constants; a prose grader"
        " asserts the whole generated sentence, not a substring, and one for MOVED text (a sentence, clause, bullet or"
        " row), added in the edit that moves it, also fails when the text sits at its old position; a test-quality seat"
        " checks docstring claims against the scan; a fix recipe handed to a coder names one input it must leave"
        " unchanged and the test that holds it; a grader of a `path:N-M` cite asserts its first line AND its last line"
        " still hold the text the cite backs."
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
        "a premise guard asserts at the call site, not on constants; a prose grader asserts the whole generated"
        " sentence, not a substring, and one for MOVED text (a sentence, clause, bullet or row), added in the edit"
        " that moves it, also fails when the text sits at its old position; a test-quality seat checks docstring"
        " claims against the scan;" in graders
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
