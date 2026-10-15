"""/fabrik-review feedback queue answered in one pass (D-735): the catalogue pointer and the text fixes.

Each test pins one subject's sentence in the section that owns it, so a section moved or a fix reverted fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-review.md"
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_phase_one_points_at_the_probe_catalogue() -> None:
    """The catalogue's rows were asked of /fabrik-review too; Phase 1 names it by its hub path."""
    p1 = _section(_norm(SRC), "## Phase 1 — Independent finders", "**Run the review-hygiene check")
    assert (
        "`/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE"
        in p1
    )
    assert CAT.exists()


def test_agent_tool_shape_covers_a_review_the_operator_did_not_invoke() -> None:
    """Row 1791755835: Workflow runs only on the operator's opt-in, so a hook- or caller-started review uses Agent."""
    assert (
        "or the operator did not invoke this review (the tool runs only on their explicit opt-in)"
        in _norm(SRC)
    )


def test_a_failed_refuters_candidates_are_executed_by_the_lead() -> None:
    """Rows 1791418194, 1791410409: a NO RESULT refuter is never a re-dispatch of the whole pass."""
    p2 = _section(_norm(SRC), "## Phase 2 — EXECUTE", "## Phase 3")
    assert "every candidate of a slice whose refuter failed or read `NO RESULT`" in p2
    assert "never a re-dispatch of the pass" in p2


def test_the_delta_brief_names_its_must_read_files() -> None:
    """Rows 1791506864, 1791478572: the fix diff's files and the previous pass's gap files, by path."""
    p4 = _section(_norm(SRC), "## Phase 4 — Converge", "## Behavior Contract")
    assert (
        "The brief lists that file set by path as must-read, with every file the previous pass left as a `gap`."
        in p4
    )


def test_next_rows_merge_into_slices_by_name() -> None:
    """Row 1791493834: `next` prints `{name, ledger}` rows, merged by name; the quiet-round-1 shape is intel's."""
    p4 = _section(_norm(SRC), "## Phase 4 — Converge", "## Behavior Contract")
    assert (
        "(it prints `{name, ledger}` rows: each `ledger` goes on the `args.slices` entry of the same `name`, "
        "which keeps its `files`)" in p4
    )
    assert "a fresh hunt of their own slice" not in p4


def test_next_prints_name_and_ledger_rows_and_nothing_for_no_ids(tmp_path, capsys) -> None:
    """The shape the Phase 4 sentence describes, executed: `{name, ledger}` rows without `files`; no ids, no rows."""
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "review_loop_ledger", ROOT / "scripts" / "review_loop_ledger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pass_file = tmp_path / "pass-1.json"
    pass_file.write_text(
        json.dumps({"candidates": [{"id": "A-S1", "file": "x.py", "line": 3, "claim": "c"}]})
    )
    assert mod.main(["next", str(pass_file), "--ids", "A-S1"]) in (0, None)
    rows = json.loads(capsys.readouterr().out)
    assert rows == [
        {"name": "A", "ledger": [{"id": "A-S1", "file": "x.py", "line": 3, "claim": "c"}]}
    ]
    assert (
        "files" not in rows[0]
    )  # so the rows are merged into a slice entry, never passed as `args.slices`
    assert mod.main(["next", str(pass_file), "--ids", ""]) in (0, None)
    assert json.loads(capsys.readouterr().out) == []


def test_the_opt_in_fallback_is_stated_in_every_copy() -> None:
    """Every file that states the Agent-tool fallback ("cannot load the script") carries the opt-in clause too."""
    roots = [
        ROOT / "commands" / "_sources",
        ROOT / "commands" / "_fragments",
        ROOT / "docs" / "reference",
    ]
    copies = [
        p for r in roots for p in sorted(r.rglob("*.md")) if "cannot load the script" in _norm(p)
    ]
    assert len(copies) >= 10, [p.name for p in copies]
    missing = [
        p.name for p in copies if "(the tool runs only on their explicit opt-in)" not in _norm(p)
    ]
    assert not missing, missing


def test_a_refuter_that_returns_nothing_is_not_re_dispatched_as_a_finder() -> None:
    """C6 of the review: the FAILED-seat re-dispatch rule names finders; a refuter's candidates go to Phase 2."""
    text = _norm(SRC)
    assert (
        "A finder that returns nothing is a FAILED seat (re-dispatch it), never a clean round; a refuter"
        in text
    )
    assert "A seat that returns nothing is a FAILED seat" not in text


def test_close_order_stages_before_the_in_progress_gate() -> None:
    """Row 1791508831: the gate's ruff leg lints staged changes only, so an unstaged fix is linted by nothing."""
    assert (
        "Close in this ORDER: stage your own files (the gate's ruff leg lints only staged changes"
        in _norm(SRC)
    )


def test_trimmed_single_finder_slice_gets_its_second_next_wave() -> None:
    """Row 1791511465 and intel 01M4F7QT11: the remedy sits beside Phase 1's unread-slice rule."""
    assert (
        "named unread, as that line says (a slice it left with one finder gets its second in the next wave)"
        in (_norm(SRC))
    )


def test_catalogue_holds_the_two_recurring_probes() -> None:
    """Rows 1791336906/1791400423 (redactor timing) and 1790358705/1790361809 (what a fix leaves unchanged)."""
    cat = _norm(CAT)
    assert (
        "a regex redactor is also timed on a 100k-character input and probed at its truncation edges"
        in _section(cat, "## The brief's hunt lines", "## Graders")
    )
    assert (
        "a fix recipe handed to a coder names one input it must leave unchanged and the test that holds it"
        in (_section(cat, "## Graders", "## Prose and docs fixes"))
    )
    assert (
        "a sentence describing a record format or a code string quotes the emit site's keys or the string verbatim"
        in (_section(cat, "## Prose and docs fixes", "## Seat isolation"))
    )
    assert (
        "on a copy: ruff `--no-cache --config <repo>/pyproject.toml`, mypy `--config-file` with the same path; ruff"
        " writes `.ruff_cache` in its working directory and fails inside a read-only pin without `--no-cache`"
        in (_section(cat, "## Seat isolation", "## Loop bookkeeping"))
    )


def test_a_guard_a_fix_adds_is_briefed_in_the_next_round() -> None:
    """Row 1791838673 (D-787): the catalogue both review commands read."""
    cat = _norm(ROOT / "commands" / "_fragments" / "review-probe-catalogue.md")
    assert (
        "a guard a fix adds goes into every brief from that next one on, by name, with its escape variants (quote styles, unreadable values, globbed paths) and its model boundary"
        in cat
    )


def test_the_round_grammar_names_own_fix() -> None:
    """Row 1791764618 (D-778)."""
    assert (
        "--own-fix <how many of those confirmed defects lie in text this review added in an earlier round>"
        in _norm(SRC)
    )


def test_a_callers_plan_flip_follows_the_post_flip_gate_run() -> None:
    """Row 1791828832 (D-778): the reason is check_convergence's own skip."""
    assert (
        "A caller that flips its plan to `EXECUTED` flips it only after that post-flip run is embedded: a red post-flip run sends the receipt back to `IN-PROGRESS`"
        in _norm(SRC)
    )
    conv = (ROOT / "scripts" / "enforcement" / "check_convergence.py").read_text()
    assert re.search(r"if _receipt_in_progress\(rtext\):\s+continue", conv)


def test_the_receipt_template_shows_the_gate_scope_line_the_gate_accepts_filled() -> None:
    """Rows 1791829774, 1791828719 (D-778): the placeholder never reads as a declaration; a filled one does."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))
    try:
        import check_convergence
    finally:
        sys.path.pop(0)
    tmpl = (ROOT / "scripts" / "review_receipt.py").read_text()
    line = "`GATE-SCOPE: out-of-surface — <failing check>; findings naming this surface: 0 of <N>; measured by: <command>`"
    assert line in tmpl
    pats = [
        v
        for v in vars(check_convergence).values()
        if isinstance(v, re.Pattern) and "GATE-SCOPE" in v.pattern
    ]
    assert len(pats) == 1
    assert not pats[0].search(line)
    assert pats[0].search(
        line.replace("<failing check>", "docs-links")
        .replace("<N>", "3")
        .replace("<command>", "grep x")
    )


def test_a_scope_growth_remainder_round_restates_every_slice() -> None:
    """Row 1791847183: the exit's re-verify step never said the remainder round still re-states every slice."""
    text = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    assert (
        "re-verify the fixed set alone (in a slice-partitioned loop, its `round --slices` still re-states every earlier slice;"
        in text
    )


def test_a_capped_round_one_merges_low_risk_slices() -> None:
    """Row 1791847121: a box cap dropped a slice to one finder and cost a second wave."""
    text = _norm(CAT)
    remainder = text[text.index("- Remainder rounds:") : text.index("- Route-up and close:")]
    assert (
        "or, when the cap is known before round 1, merge two low-risk slices so the riskiest keeps both finders"
        in remainder
    )


def test_a_fix_outside_the_pin_is_pinned_or_named() -> None:
    """Row 1791844045: a CHANGELOG fix outside the pins was re-raised from the base copy."""
    text = _norm(CAT)
    assert (
        "a ledger row whose fix landed in a file outside the pin (a CHANGELOG or ledger hunk) has that file pinned next pass, or the brief names it"
        in text
    )


def test_the_closing_method_cell_rule_matches_the_gate() -> None:
    """Row 1791860808: a closing cell worded 'method: remainder pass — re-derivation' failed the coverage gate."""
    import importlib.util
    import sys

    path = ROOT / "scripts" / "enforcement" / "check_review_coverage.py"
    spec = importlib.util.spec_from_file_location("crc_for_queue_pass", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["crc_for_queue_pass"] = mod
    spec.loader.exec_module(mod)
    assert "Write the closing row's method cell as `method: re-derivation`" in _norm(SRC)
    assert mod._REDERIVATION_ROW.search(
        "| Pass 3 | sonnet×1 | found: 0 | method: re-derivation — closing pass |"
    )
    assert not mod._REDERIVATION_ROW.search(
        "| Pass 3 | sonnet×1 | found: 0 | method: remainder pass — re-derivation |"
    )


def test_the_checklist_is_filled_before_the_in_progress_gate_run() -> None:
    """Row 1791869394: an empty checklist passed the IN-PROGRESS run and reddened only after the flip."""
    text = _norm(SRC)
    fill = "Fill every Coverage Checklist and Pass Ledger row before the close: the IN-PROGRESS run below skips both convergence checkers"
    assert fill in text
    assert text.index(fill) < text.index("Close in this ORDER: stage your own files")
    assert (
        "an untracked receipt is skipped outright until it is staged, whatever its Status" in text
    )


def test_an_injected_line_is_read_back_through_its_consumer() -> None:
    """Row 1791889493: a pointer fix to a pack line read green in the source and red in review_rubric.py's output."""
    pre_pin = _section(_norm(CAT), "## Before the first pin", "## ")
    rule = (
        "- A line another tool injects or renders, changed or with a rendering the change alters, is read back"
        " whole through that tool's output after the edit and before each delta pin, under an invocation that"
        " emits it — a pack line in `review_rubric.py --changed <a path its globs hit>`, a fragment edit's"
        " consumers rendered to a temp dir, a template's emitted file — never in its source alone; a line the"
        " change leaves emitted by no invocation (a pack line with no mandate keyword, a section under a"
        " conditional heading) is named in the brief as dropped."
    )
    assert pre_pin.count(rule) == 1
    assert "render a fragment edit's consumers to a temp dir and read each" not in _norm(CAT)


def test_the_callers_hunt_line_names_readers_that_never_import_the_file() -> None:
    """Row 1791891025: a seat cannot infer a consumer it was never told exists, and a scaffold fold or drift checker
    reads a file's TEXT without importing it, so no importer grep finds it. The class sits in the general Callers and
    consumers hunt line (any changed or vendored file, not only a re-vendor), with the recipe that finds the readers
    and who names them. Pinned as the contiguous span between its neighbours inside that bullet, so a truncated,
    qualified or relocated clause reds. Cheapest bypass: a brief that names the class but lists no reader; the seat
    reading that brief owns it, not this pin."""
    callers = _section(_norm(CAT), "- Callers and consumers:", "- Parsers:")
    assert (
        "every gate grading the old name; every reader of a changed or vendored file's text that never imports it (a"
        " scaffold fold such as `src/fabrik/scaffold.py::_audit_log_schema_block`, a drift or sync checker), found by"
        " the lead grepping the hub and the fleet repos for the file's path, basename and directory and reading"
        " `scripts/fabrik_synced_manifest.py` for a glob that covers it (a covered file is also read through each"
        " project's `.fabrik/synced.lock` by `scripts/enforcement/check_synced_unmodified.py`), each hit that reads the"
        " file named in the brief; every outbound sink" in callers
    )
    # the round-1 draft put it in the re-vendor premise; neither wording may remain anywhere else
    assert _norm(CAT).count("that never imports it") == 1


def test_a_seat_reads_git_history_from_a_shared_clone_not_a_worktree() -> None:
    """Mail 01M4VMNGGM (intel, executed and re-run here): branch, worktree and stash state lands in the clone's own
    `.git`, and a push from the clone writes the live repo, so the push is disabled first.
    Row 1791910374, a recurrence of the held gitdir-shim-recipe ("a history-reading test recipe"): the catalogue forbade
    `git worktree add` but a `git archive` pin has no history, so a history-reading test had no sanctioned route. The
    D-711 audit ran the clone: alternates point at the shared objects and nothing in the shared `.git` changed. Its own
    sentence, after the worktree ban, so the ban's colon still leads to the archive red-on-revert; live text only (an
    HTML comment around it reds). Not seen: a seat that runs the test in the archive anyway; the seat's red owns it."""
    iso = re.sub(
        r"<!--.*?-->", "", _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    )
    assert (
        "before its first gate. A seat test that reads git history runs in a clone the seat makes with `git -C "
        "<scratch> clone --shared --no-checkout <live checkout> clone`, checks out at `git -C <scratch>/clone "
        "checkout -q <the pass's base SHA>` (until then its status reads every file deleted), with its push to "
        "`origin` disabled at once (`git -C <scratch>/clone config remote.origin.pushurl /nonexistent.invalid`: "
        "`origin` is the live repo, so a push writes its `.git`; no other remote is ever pushed to) and the pins laid"
        " over it, committed in the clone when the test reads HEAD, a diff or the status; that test's red-on-revert "
        "overlays the revert on the clone. Branch, worktree and stash state the test creates lands in the clone's own"
        " `.git`; only a test that reads the live checkout's own branches, worktrees or stash runs in the lead's "
        "throwaway worktree. Ruff" in iso
    )
    assert (
        "A SEAT never runs `git worktree add` on the live repo (its metadata lands in the shared `.git`): a seat's"
        " red-on-revert overlays"
        " the revert on its archive copy" in iso
    )


def test_the_scope_paragraph_says_where_round_zero_and_rule_five_bind() -> None:
    """W-eaa66f83: term-coverage's scope paragraph said every obligation 'binds all five consumers alike' while round
    zero (:16) runs before round one and every re-dispatch of a consumer that runs delta rounds, which a certification
    gauntlet runs only where its own text names one, and rule (5) governs only a fix to a checker or a gate."""
    text = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / "term-coverage.md").read_text())
    assert (
        "binds all five consumers alike, while round zero binds only a consumer that runs delta rounds — before its round"
        " one and before every re-dispatch — and rule (5) only a fix to a checker or a gate."
    ) in text


def test_rule_three_pointer_is_opened_before_the_pin() -> None:
    """W-c9b727ab: rule (3) let a restating sentence be replaced by 'at most a pointer to where the fact is
    re-derivable' without anyone opening that pointer, so a pointer to a place that no longer holds the fact passed as
    a deletion. The pointer is now read before the pin, as rule (2)'s sweep reads each mirror, and recorded."""
    text = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / "term-coverage.md").read_text())
    assert (
        "replaced by at most a pointer to where the fact is re-derivable (each pointer OPENED before the pin and the"
        " fact seen at it, then recorded by APPENDING one `· pointer: <path:line> read` per pointer to the Pass Ledger"
        " row's `method:` cell, after its `; class rewrite` text), never by a re-cut of the claim;"
    ) in text


def test_an_agent_tool_seat_gets_the_pin_import_placement() -> None:
    """Mail 01M4W155SB (intel): the Agent-tool seat list states PIN_IMPORT's sys.path placement and its -P condition
    and points at the recipe, and the pointed-at recipe still says the same."""
    assert (
        "never `sys.path.insert` the live tree, puts the directory that holds the top-level import name"
        " (`<extract>/src` for `import fabrik`) at the index of the first entry ending in `site-packages` or"
        " `dist-packages` (at the end when there is none), never at index 0, where a package named like a stdlib"
        " module shadows the stdlib, runs every probe as `python -P -B` with any PYTHONPATH entries dropped from"
        " sys.path (without `-P` the working directory, the live repo, sits ahead of the extract) — `PIN_IMPORT` in"
        " `.claude/workflows/fabrik-review-loop.js` is the recipe"
    ) in _norm(SRC)
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text(encoding="utf-8")
    recipe = js[js.index("const PIN_IMPORT") : js.index("const SEAT_ISOLATION")]
    assert (
        "at the index of the first entry ending in site-packages or dist-packages, or at the end when"
        in recipe
    )
    assert "never at index 0" in recipe
    assert "run every probe as \\`python -P -B\\`" in recipe
    assert "drop its entries from sys.path" in recipe


def test_an_equivalent_mutant_is_discarded_never_reported_as_a_test_gap() -> None:
    """Row 1791937766: a no-op mutant (an f-string that renders the same) survived and was reported as a gap; both
    homes of the mutant rule now require a survivor to change observable behaviour first."""
    cov = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    assert (
        "shown applied by a diff of the copy against the pin, never a grep count; a survivor is reported only once"
        " shown to change observable behaviour (an output, return value, exit code, raised exception or written state"
        " diffed against the unmutated copy), and an equivalent mutant, a named one included, is struck with that diff"
        " quoted, never reported as a test gap"
    ) in cov
    assert (
        "survivors reported only once shown to change observable behaviour (an output, return value, exit code, raised"
        " exception or written state diffed against the unmutated copy), and an equivalent mutant is struck with that"
        " diff quoted, never a test gap"
    ) in _norm(CAT)


def test_fourth_review_queue_pass_lines() -> None:
    """/fabrik-review queue, fourth pass (2026-10-14): overlay copy and pin currency (1791933800, 1791937887,
    1791958467, 1791961253, 1791965991, 1791967675, 1791972544, 1791958633, 1791971384), write-path isolation
    seams (1791935553), visible text of real builds (1791936682, 1791950533, 1791953413, 1791958187), re-vendor
    tests that assume a co-located hub (1791959728), identity keys (1791982821) and predicate readers (1791985566)."""
    text = _norm(CAT)
    for needle in (
        "a fix's identity or dedup key (byte vs text read, line endings, recycled ids such as inode reuse),",
        "every reader of a changed predicate's verdict (a notice, message or wall line that reads the same hold), named"
        " before the closing round.",
        "and whether that test assumes a co-located hub tree, so a standalone run of it is a known false red;",
        "a change that writes outside its state dir: every isolation seam its callers' tests use (`COMMAND_RUN_DIR`, a"
        " `HOME` or `TMPDIR` override), each shown to land under its own root by listing the live checkout after the suite.",
        "a page-type or reader move: base and head are built and each page's visible text and heading outline (h1-h3"
        " counts) are diffed independently of any identity diff the change ships",
        "a seat copies each file to its own path or runs `cp -r <pin>/. <dest>/` then `chmod -R u+w <dest>`, never"
        " `cp -r <pin> <dest>` onto a directory that exists",
        "`git archive` omits untracked files, so the pin also carries the gitignored inputs the tests read (the repo's"
        " `.worktreeinclude` list, `.env` excepted)",
        "Each later pass's brief names its own pin dir and digest, cut after the last fix, never the round-1 pin,",
    ):
        assert needle in text, needle


def test_a_fix_is_probed_against_every_shape_the_form_it_replaces_held() -> None:
    """Rows 1792001701 and 1792016553 (fabrik-review): a closing pass accepted a selector-to-id fix that dropped the
    scoped shape the selector had matched, and a restored test guard that covered fewer pages and languages than
    the test it replaced; 22 of 542 rejected reasons had already named the mirror clause, so the held subject
    recurs and is edited (D-711). Phase 3's verify-the-fix list gains the question — the shapes enumerated from the
    OLD form and listed in the fix's ledger row — and the catalogue's closing-pass brief re-checks every replaced
    form against them. Mutants: delete the question, drop 'EVERY shape', drop 'before the fix is drafted', 'never
    from the new one' to 'or from the new one', drop a named shape, drop a cite, move the question or a shape past
    its '?', drop the catalogue's re-check — each fails an assertion (the question is bounded by its own '?', so a
    clause moved elsewhere in the paragraph is not found)."""
    text = _norm(SRC)
    para = _section(
        text, "verify the FIX, not just the finding", "**Never apply a fix you can't stand behind"
    )
    head = "does the new form still hold EVERY shape the form it replaces held"
    assert head in para, "the question left Phase 3's verify-the-fix list"
    rest = para[para.index(head) :]
    assert "?" in rest, "the question lost its question mark"
    q = rest[: rest.index("?") + 1]
    assert q.endswith(
        'population before it widens or narrows", asked here of every replaced form)?'
    ), q[-80:]
    assert (
        "the shapes enumerated from the OLD form before the fix is drafted, never from the new one, and listed in"
        " the fix's Pass Ledger `method:` cell beside its `round-zero probe` note"
    ) in q, (
        "the enumeration, its source and its record are one contiguous clause; an insertion breaks it"
    )
    for shape in (
        "a selector replaced by an id or a scoped lookup",
        "a guard replaced by a narrower one",
        "a restored test by one covering fewer pages or languages",
    ):
        assert shape in q, shape
    # the two cites quote their sources, which must still carry the quoted words
    cite_cat = "what a replaced guard covered that its replacement does not"
    cite_cov = "against its live population before it widens or narrows"
    assert cite_cat in q and cite_cov in q
    assert cite_cat in _norm(CAT), "the cite names a catalogue line that no longer exists"
    cov = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    assert cite_cov in cov, "the cite names a round-zero clause that no longer exists"
    assert "; round-zero probe — <what>" in cov, (
        "the method-cell note the question points at is gone"
    )
    assert "for a matcher or replacer" in q, (
        "the cite must name the subject term-coverage gives the phrase"
    )
    assert "matcher clause" not in q, "an invented label a reader cannot grep for"
    assert "or from the new one" not in q
    assert "2026-" not in q, "a rule carries no dated incident"
    # the closing-pass seats re-check the lead's enumeration, so the lead's step is not the only reader
    assert (
        "the closing-pass brief has every seat list each slice file it read, by path, and re-check every fix that"
        " replaced a form against the shapes the OLD form held, as the fix's ledger row lists them"
    ) in _norm(CAT)


def test_a_reader_over_another_language_starts_from_a_fail_closed_grammar() -> None:
    """Row 1792019529 (wef2, a /fabrik-review under /fabrik-task over a TypeScript reader): four rounds and 10.7 h
    went to a tokenizer that a strict line grammar replaced in one; the catalogue's Parsers row said 'the parsing
    model before tokens' but never that the grammar REFUSES unknown lines, that its refusal is executed before
    every pin, or where the seats aim. The second verdict on a held parser subject (parser-residue-replace,
    parser-fix-scope-growth-early-exit), so the subject is edited (D-711). Round 1 of its review added the
    fail-closed COST (the lead runs the grammar over the live files and classes every refusal) and closed the
    renamed-tokenizer and trivial-fixture escapes. Mutants: delete the clause, 'REFUSES' to 'flags', drop 'none a
    catch-all', 'every pin' to 'the pin', drop the live-files run, drop the tokenizer escape, append 'where time
    allows' — each fails an assertion (the clause is bounded to the Parsers row)."""
    text = _norm(CAT)
    row = text[text.index("- Parsers: the producer's real output contract first") :]
    row = row[: row.index(" - ", 1)]
    assert (
        "a hand-written reader whose input is source in a language other than its own (TypeScript read by Python,"
        " SQL, a Dockerfile), with no real parser of that language at hand, starts from a strict grammar that REFUSES"
        " any line matching none of its named forms, none a catch-all, its refusal executed before every pin on a line"
        " of that language's own syntax that no named form admits, and run by the lead over the live files the reader"
        " will read, each refusal there classed a grammar gap or a true out-of-grammar line; the seats attack what the"
        " grammar wrongly accepts — a tokenizer is built only where the brief names the construct no line form can"
        " hold."
    ) in row, (
        "the grammar-first rule, its executed refusal, its fail-closed cost and its escape are one clause"
    )
    assert row.rstrip().endswith("no line form can hold."), row[-80:]
    assert "attack only" not in row, "'only' forbade probing wrongful refusals (round-1 finding)"
    assert "hand-written reader" in row and "no real parser of that language at hand" in row, (
        "a reader that uses the language's real parser is outside the clause (round-2 finding)"
    )
    for weakener in ("where time allows", "where practical", "optionally", "should"):
        assert weakener not in row.lower(), weakener
    assert "the parsing model before tokens" in row, (
        "the clause sharpens the existing model-before-tokens rule"
    )


def test_the_receipt_sentence_says_owners_only_inside_the_by_design_parentheses() -> None:
    """Row 1792029250 (infra, the coordinator-role whole-plan review): one gate round-trip on by-design rows,
    because the receipt-time sentence of the Residual section repeated the owner-and-round rule without the
    owners-only / reason-after rule Phase 2's bullet states 240 lines earlier; the third verdict on the by-design
    grammar (two earlier rows were routed to the receipt skeleton, infra's code), so the text is edited (D-711).
    The clause is a POINTER in the rule's own words ("and nothing else … the reason follows them"), never a third
    wording — term-edit.md:21 already carries a second. Mutants: delete the clause, drop 'and nothing else', drop
    'the reason follows them', drop the Phase 2 pointer, move the clause after `Pass N`, move the by-design bullet
    out of Phase 2 — each fails an assertion."""
    text = _norm(SRC)
    residual = text[text.index("**Every candidate that did not enter `confirmed:` is rowed") :]
    sentence = residual[: residual.index("That section is NOT a parking lot")]
    assert (
        "(or a `D-nnn` with no round token) and nothing else inside the parentheses — the reason follows them, as"
        " Phase 2's `by design` bullet shows; the gate refuses an absent owner"
    ) in sentence, (
        "the receipt-time sentence must carry the owners-only rule as a pointer to Phase 2"
    )
    assert "owners only" not in sentence, (
        "a third wording of the rule (round-1 finding); point, do not restate"
    )
    # the pointer's target is INSIDE Phase 2 and still states the rule it points at
    phase2 = _section(text, "## Phase 2 — EXECUTE", "## Phase 3")
    assert "The parentheses hold the owner and nothing else" in phase2
    assert "a reason inside them, `(D-432: <why>)`, is refused as an absent owner" in phase2


def test_the_catalogue_probes_a_deletion_surface() -> None:
    """Rows 1792031092 and 1792030357 (kaizen, 2026-10-15), the third and fourth sightings of the held deletion-probe
    subject 1790199460 (a whole-tree grep for deletions, HELD 2026-10-08; the review-scoped queue held the
    removal-vs-classification half the same day): a deleting probe left an emptied directory behind and a `readdirSync`
    on it stayed hidden; a test seed restored inputs the code under test read by name. The catalogue's hunt lines had
    no deletion shape (0 probe rows matched 'delet' among the 7 bullets). One row now names the shape and its four
    probes, each a command a seat can run: a `.git`-pruned `find -type d -empty` run before and after the deletion
    (an unpruned one prints `.git/` and pre-existing empty directories, a false red; `-name .git` prunes whatever
    way `<root>` is spelled), a grep of the code under test for each input read by name or by listing a directory,
    the Callers grep above run from the hub and the fleet
    repos for each deleted path, basename and directory (pointed at, not restated narrower), and, per guard on a
    deleted input, whether it re-runs at removal or only at classification. Mutants, each a failing assertion: drop
    the row; drop 'up to the root'; drop 'by grepping the code under test'; 'never the package' → 'the package';
    drop the removal-vs-classification clause; drop the head's bound; a second deletion row under any head."""
    cat = _norm(CAT)
    hunt = _section(cat, "## The brief's hunt lines", "## Graders")
    row = (
        "- Deletions (a change that deletes a file, directory or input): a deleting probe also removes every directory it"
        " empties, up to the root, as `git rm` does (`find <root> -name .git -prune -o -type d -empty -print`, run before"
        " and after the deletion, prints no new line; a leftover hides a `readdirSync`); a seed restoring deleted inputs"
        " first lists, by grepping the code under test, each input it reads by name or by listing a directory, and restores"
        " no other; the Callers grep above runs for each deleted path, basename and directory from the hub and the fleet"
        " repos, never the package; seats name, for each guard on a deleted input, whether it re-runs at removal or only at"
        " classification."
    )
    assert hunt.count(row) == 1, (
        "the Deletions hunt row is stated once, in § The brief's hunt lines"
    )
    # it sits between the Surfaces row and The premise row, the shape order the lead reads top to bottom
    assert hunt.index("- Surfaces:") < hunt.index("- Deletions (") < hunt.index("- The premise:")
    # one deletion row, however a second one is headed: the probe's own phrase appears once in the whole catalogue
    assert cat.count("- Deletions (") == 1
    assert cat.count("deleting probe") == 1
    # the grep clause points at the Callers row above it instead of restating it narrower
    callers = hunt[hunt.index("- Callers and consumers:") : hunt.index("- Deletions (")]
    assert "the hub and the fleet repos for the file's path, basename and directory" in callers


def test_the_slices_ledger_is_defined_with_its_closing_example() -> None:
    """Row 1792065733, the third verdict on the subject: the round line named `<verified>/<claims>` without saying what
    either counts, so a closing seat that verified one claim did not know to record `A:1/1`."""
    text = _norm(SRC)
    rule = (
        "`<claims>` counts the claims in that slice's ledger and `<verified>` those its owning seats re-ran to"
        " `DEFECT_ABSENT`, so a closing pass that found its slice's one claim absent records `A:1/1`, and the terminal"
        " needs every slice at n/n"
    )
    assert rule in text
    i = text.index("**Record the pass before you decide:**")
    assert i < text.index(rule) < text.index("Its TERMINAL verdict", i)


def test_a_fixture_equal_to_the_codes_own_literal_is_a_test_quality_finding() -> None:
    """Row 1792054051, a recurrence of held watched-fail-first-real-fixture: a test whose expected value is the code's
    own constant is green whatever the constant says; the checklist names it and the mutation that exposes it."""
    text = _norm(SRC)
    checklist = _section(
        text, "**Test-quality checklist", "Flag any of these as a test-quality finding."
    )
    assert "**a fixture that IS the code's own constant**" in checklist
    # the qualifier is the rule: a test importing a constant for any other reason is not the defect
    assert "read from the very constant whose VALUE is the behaviour under test" in checklist
    assert (
        "the finder mutates that constant on a copy under its scratch dir and the test must go red"
        in checklist
    )
