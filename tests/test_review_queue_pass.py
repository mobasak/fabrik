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
    # W-e2ff8f36: the bounded hop's reader run takes the previous pass's pin; the inputs live in § Seat isolation.
    pointer = "It also names the previous pass's `base_sha` and pins_dir, as the probe catalogue's § Seat isolation says."
    assert _norm(SRC).count(pointer) == 1 and pointer in p4


def test_the_callers_hunt_line_names_the_join_against_another_producer() -> None:
    """Row 1792365642: a fix changed one producer's path form and the line that joined its output with a second
    producer's keys was never re-derived (W-42ddde8f, final_gate_stop.py's commit leg), so the hunt line names it."""
    callers = _section(_norm(CAT), "- Callers and consumers:", "- Parsers:")
    assert (
        "callers that use a normaliser's return value; every line that joins, compares or keys a changed output"
        " against another producer's, named with the form each side's values take (a path relative to a"
        " subdirectory or to the top level, say); a pure helper's own return contract" in callers
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
    for clause in (
        # D-961 (supersedes D-957 in part): the hub never calls the Workflow tool, so a hub review's
        # seats always take the Agent-tool path and no approval dialog reaches the operator
        "or the session is in the hub (D-961: the hub never calls the `Workflow` tool), "
        "or the operator did not invoke this",
        "(the tool runs only on their explicit opt-in)",
    ):
        missing = [p.name for p in copies if clause not in _norm(p)]
        assert not missing, (clause, missing)


_BANNER = ROOT / "commands" / "_fragments" / "no-workflow-hub.md"


def test_every_workflow_command_carries_the_no_workflow_in_the_hub_note() -> None:
    """D-961: the override sits at the TOP of every source that launches the review-loop Workflow, so
    no lead sentence ("They run as ONE `Workflow` call …") is read before it; the note names the hub
    test and replaces every launch, later passes and relaunches included."""
    note = _norm(_BANNER)
    for phrase in (
        "NO `Workflow` IN THE HUB — D-961",
        "a session whose `git rev-parse --show-toplevel` is `/opt/fabrik` or a worktree under "
        "`/opt/fabrik/.claude/worktrees/` — never call the `Workflow` tool",
        "Every `Workflow` launch this command names (a round-1 pass, a delta or closing pass, a "
        "relaunch, a wave) is replaced by its Agent-tool fallback",
        "A workflow, permission or approval question never goes to the operator.",
        "Outside the hub this command's text stands as written.",
    ):
        assert phrase in note, phrase
    launching = [
        p
        for p in sorted((ROOT / "commands" / "_sources").glob("*.md"))
        if "fabrik-review-loop.js" in p.read_text(encoding="utf-8")
    ]
    assert len(launching) >= 7, [p.name for p in launching]
    for p in launching:
        head = p.read_text(encoding="utf-8").split("\n")[:8]
        assert "{{include:no-workflow-hub}}" in head, p.name
    doc = _norm(ROOT / "docs" / "reference" / "review-loop-workflow.md")
    assert "NO `Workflow` IN THE HUB — D-961" in doc.split("## Launch")[0]
    assert "## Launch (outside the hub — D-961;" in doc
    # the shared texts that reach commands WITHOUT the note gate every Workflow step inline
    core = _norm(ROOT / "commands" / "_fragments" / "subagents-core.md")
    assert "runs, outside the hub (D-961: the hub never calls it), as ONE `Workflow` call" in core
    assert "pass it, outside the hub (D-961), into the `fabrik-review-loop.js` args" in core
    cat = _norm(CAT)
    assert "outside the hub (D-961), write the Workflow args JSON to scratch and relaunch" in cat
    assert "in the hub, re-dispatch its `Agent` seats over the same ledger" in cat


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
        "Close in this ORDER:** 1. Stage your own files (the gate's ruff leg lints only staged changes"
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


def test_a_fix_outside_the_pin_is_pinned_next_pass() -> None:
    """Row 1791844045: a CHANGELOG fix outside the pins was re-raised from the base copy. Naming the file instead of
    pinning it left the seat no place to read it, since every unpinned file is read from the base tree (rows
    1792416541, 1792432410)."""
    text = _norm(CAT)
    assert (
        "a ledger row whose fix landed in a file outside the pin (a CHANGELOG or ledger hunk) has that file pinned next"
        " pass, so the seat never reads the base copy" in text
    )
    assert "or the brief names it" not in text


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
    assert text.index(fill) < text.index("Close in this ORDER:** 1. Stage your own files")
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
        "before its first gate. A seat test that reads git history or the tracked set (`git ls-files`: neither the"
        " archive nor a pin copy has a `.git`) runs in a clone the seat makes with `git -C "
        "<scratch> clone --shared --no-checkout <live checkout> clone`, checks out at `git -C <scratch>/clone "
        "checkout -q <the pass's base SHA>` (until then its status reads every file deleted), with its push to "
        "`origin` disabled at once (`git -C <scratch>/clone config remote.origin.pushurl /nonexistent.invalid`: "
        "`origin` is the live repo, so a push writes its `.git`; no other remote is ever pushed to) and the pins laid"
        " over it, committed in the clone when the test reads HEAD, a diff, the status or the tracked set; that test's"
        " red-on-revert "
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
        "every reader of a changed predicate's verdict (a notice, message or wall line that reads the same hold), and"
        " of each field a fix writes, named before the closing round.",
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


def test_the_fourth_pass_answers_its_recurring_subjects_in_their_homes() -> None:
    """D-711 recurrences, 2026-10-17 pass: receipt re-made after a fix commit (1792137103, 1792184935), counts name
    their commit (1792072266), a served build's real port (1792087244), two fix forms (1792119582, 1792111760),
    branches a doc sentence summarises (1792088847), readers of a written field (1792081559), and the post-fix prose
    sweep (1792085958, 1792067212, 1792084655). Mutants: drop any clause."""
    src = _norm(SRC)
    assert (
        "a fix committed after the draft's `--init` moves the tip, which is why that form writes the receipt itself"
        " only at the close (`--init --lane --changed <every path in base..last> --scope <slug> --range <base>..<last fix commit>`,"
        " its rows carried from the draft — `--init`"
        " never overwrites, and `--restamp` re-anchors only a working-tree receipt)"
    ) in _section(src, "## Reporting", "{{include:close-chain}}")
    # rows 1792097032 (the seat folder exists first) and 1792082624 (two vacuous-test shapes, recurring
    # negation-safe-assertions)
    assert (
        "`<scratch_dir>/seat-p<pass>-<digest8>-<slice>-<model>/`, made with `mkdir -p` before its first write"
        in src
    )
    assert (
        "**a value compared with itself, or a matcher softened until it cannot fail** (a substring where the contract"
        " is equality, a regex widened to `.*`)"
    ) in _section(src, "**Test-quality checklist", "## Phase 2")
    lessons = _section(
        src, "Every finder brief carries these lessons VERBATIM", "**HARD TIME BOX 15 minutes**"
    )
    assert (
        "print a DENOMINATOR, and the commit (or the pin's md5) it was measured at, beside every count"
        in lessons
    )
    assert (
        "a probe of a served build reads the port the server actually bound, from its own output, or serves the"
        " files with no port at all (Playwright `page.route`), never a port the brief assumed"
    ) in lessons
    fixed = _section(src, "## Phase 3 — Prove & fix", "## Phase 4 — Converge")
    assert (
        "**Two fix forms recur:** two predicates over one input (an arm and its lift, an allow and its deny) become"
        " ONE classifier both read, its grader sweeping every input pair; a sanitizing fix is an allowlist of"
        " spelled-out characters, never a bracket range"
    ) in fixed
    assert "(with bash's `globasciiranges` off, `B` matches `[a-c]` under `en_US.UTF-8`)" in fixed
    cat = _norm(CAT)
    assert (
        "trace each rationale sentence's mechanism to the code through every branch it summarises (refusals and"
        " fallbacks, not only the happy path)"
    ) in cat
    assert "and of each field a fix writes, named before the closing round." in cat
    assert (
        "each quote a fix writes re-read against its source verbatim before the pin; each sentence a fix writes that"
        " restates a rule already stated elsewhere, found at its source by that restated rule's terms and two rewordings"
        " of them and then held to `/fabrik-review-scoped` step 3's rule for what is already stated; every doc line, docstring,"
        " comment and `Raises` section stating an outcome a fix changes (when a function raises or deletes, a module that no"
        " longer exists), found by grepping its verb and each removed name across the WHOLE file, not only its hunks,"
        " in the round the fix lands (a `Raises` section phrased by its rule, never an enumeration that the next fix"
        " outdates), and every comment and docstring of a function whose behaviour a fix changes re-read whole, since"
        " a paraphrase names neither the verb nor a removed name;"
    ) in cat


def test_a_by_design_d_owner_is_a_ledger_row_and_the_refusals_point_at_the_gate() -> None:
    """Mail 01M4YS0EZV (W-91ef9165): infra's 66ed34d47 (D-876) made check_review_coverage V5 refuse a by-design
    D-nnn absent from the checkout's ledger. Phase 2's bullet, where the grammar is defined, now says the D-owner
    is a row of that ledger; the Reporting paragraph points at the gate's own messages instead of listing a subset
    (a three-item list missed three refusals and the ledger check's fail-open)."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    assert "or a row of this checkout's `docs/DECISIONS.md`, which takes no round token." in text
    assert (
        "the gate refuses an absent owner, and the messages of `check_review_coverage.py::_residual_errors` name"
        " every other licence it refuses (it checks a `D-nnn` only against a ledger with readable `| D-n |` rows)."
    ) in text
    gate = (ROOT / "scripts" / "enforcement" / "check_review_coverage.py").read_text()
    assert "def _residual_errors(" in gate, "the pointer names a function the gate defines"


def test_round_zero_runs_a_guard_the_fix_adds_over_the_fix_itself() -> None:
    """Row 1792201902 (infra), the fourth answered row on the round-zero live-population clause (reasons 1792090895,
    1791195745, 1791156134): both late findings were a new guard missing the fix's own code. Both round-zero homes
    now name the fix's own hunks among the guard's inputs."""
    for name in ("term-coverage", "term-edit"):
        text = " ".join((ROOT / "commands" / "_fragments" / f"{name}.md").read_text().split())
        assert "a guard the fix ADDS run over the fix's own hunks too," in text, name


def test_briefs_durable_unchanged_slices_said_guards_round_trip_counts_from_receipt() -> None:
    """Rows 1792252856 (briefs and fix lists homeless, recurring the routed row 1791906916 and held
    close-input-durable-folder), 1792251120 (closing seats re-proved byte identity, recurring held
    closing-pass-unchanged-surface), 1792255300 (a guard written for the one bad input, recurring held
    denylist-to-allowlist-convergence), 1792247279 (mid-loop counts in a D-row, recurring held
    changelog-figure-before-close and changelog-test-count-from-pytest)."""
    review = _norm(SRC)
    assert (
        "or the session scratchpad when `start` printed no line that begins `SCRATCH:`, and so do the briefs and fix lists the "
        "lead writes for each pass, so a resumed review has them (the seats' candidates, verdicts, notes and "
        "`files_read` are already in the pass files there); only the seats' copies go under"
    ) in review
    assert (
        "When the fix diff leaves a slice's files untouched, the closing-pass brief says so, naming each file's md5 "
        "in both passes' pin manifests, so its seats open those files and re-execute their ledger without "
        "re-proving byte identity."
    ) in review
    for frag in ("term-coverage", "term-edit"):
        text = _norm(ROOT / "commands" / "_fragments" / f"{frag}.md")
        assert (
            "all at once, never one patch per shape; a guard added because one bad input reached a reader is "
            "written as the readers' round-trip (a value is accepted only when every reader parses back what was "
            "written), never as a check for that one input"
        ) in text, frag
    cc = _norm(ROOT / "commands" / "_fragments" / "close-chain.md")
    assert (
        "In a command that runs a review loop, a mutant or test count reaches the D-row or `CHANGELOG.md` only "
        "after the closing pass, printed then by its producing command; a draft written mid-loop carries none."
    ) in cc


def test_round_zero_opens_a_pointer_from_every_repo_the_surface_ships_to() -> None:
    """Row 1792275662 (2026-10-18), recurring held pointer-resolve-test-same-change (1790686995): a synced pack's
    fix cited a hub-only fragment, a pointer that resolves nowhere in the fleet."""
    cov = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    assert (
        "never as a check for that one input; a pointer the fix writes — rule (3)'s included — into a file"
        " `/opt/fabrik/scripts/fabrik_synced_manifest.py` distributes is opened with `test -e` from a synced project repo as well"
        " as from the hub, since a path only `/opt/fabrik` holds resolves nowhere in the fleet;"
    ) in cov


def test_round_zero_writes_one_owner_for_a_fact_from_the_first_draft() -> None:
    """Rows 1792277512 (recurring held status-vocabulary-single-source / checked-format-pointer: a CHANGELOG or doc
    line restating a constant the code owns) and 1792274565 (recurring held
    a-validator-fix-emits-the-value-its-check-tested: a fix and a neighbouring check reading one field two ways)."""
    cov = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    assert (
        "resolves nowhere in the fleet; a CHANGELOG or doc line the fix writes that would restate, count or partition"
        " what another artifact owns is a pointer to that owner from the first draft, opened before the pin and"
        " recorded by APPENDING `· pointer: <path:line> read` after the round-zero probe text below; a fix that reads"
        " a field another check in the same file or call path already validates (grep the pin for the field name)"
        " takes both reads from one helper, and the readers' round-trip above still holds; the Pass Ledger's"
    ) in cov
    assert "vagueness buys nothing either; (2)" in cov, "rule (1) carries no drafting rule"


def test_a_wording_change_seat_runs_the_command_the_sentence_names() -> None:
    """Row 1792262881 (2026-10-18), recurring held wording-claim-execution (1791453535): both seats of a wording
    review ran the command the changed text described, unprompted; the brief now asks for it."""
    cat = _norm(ROOT / "commands" / "_fragments" / "review-probe-catalogue.md")
    assert (
        "run a README snippet, usage text or rewritten docstring instruction as a caller would, and hand each seat of"
        " the brief that same command to run under § Seat isolation — one that writes a live store, sends, commits,"
        " deploys or reaches a host stays the lead's — and probe"
    ) in cat
    assert "every citation in a docs change, every cross-repo claim" in cat, (
        "the Execute line stays the lead's"
    )


def test_rule_three_rewrites_a_heuristic_picker_at_its_first_residue() -> None:
    """Row 1792289039 (second verdict on the held parser-residue-replace subject): a function that picks ONE item from
    a list by heuristic is patched round after round, each patch moving the pick to the next wrong item, so rule (3)
    rewrites it at the first delta round its site yields, after the deletion text so 'that residue' keeps its
    antecedent, with a one-round method cell and an earlier foundation error."""
    text = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / "term-coverage.md").read_text())
    clause = (
        "goes on drifting; a function under review that picks ONE item from a list by heuristic (a first match, a reason"
        " line taken from a log) takes this rule's ONE-batch rewrite at the first delta round in which its site yields"
        " an own-fix defect, recast, when it is not deleted, as the whole list filtered by a noise rule probed against the"
        " list's live population like any matcher above, with a single pick taken from the filtered list where its callers need one, and its"
        " row's method cell appends `; class rewrite — <site> (round k)`; a second yield at that site without the"
        " rewrite is already the foundation error the next clause names for a third residue pass; a third residue pass"
        " without a rewrite"
    )
    assert text.count(clause) == 1
    assert "(rounds k, k+1)`; when that residue is itself a sentence" in text, (
        "the deletion clause keeps its antecedent"
    )
    assert "a heuristic that SELECTS" not in text


def test_rule_three_rewrite_first_asks_whether_the_branch_can_go() -> None:
    """Row 1792293982, a recurrence of held 1791980043 (delete rather than re-cut a residue site): four rounds patched
    one regex tail before its yielding branch was deleted, which ended the residue the patches kept regenerating."""
    clause = (
        " first asking whether the yielding site, or a {} in it, can be deleted outright (a deletion is that rewrite),"
        " since a deletion ends the residue and a re-cut restarts it,"
    )
    for name, unit in (("term-coverage.md", "branch or clause"), ("term-edit.md", "clause")):
        text = re.sub(r"\s+", " ", (ROOT / "commands" / "_fragments" / name).read_text())
        start = text.index("in ONE batch instead of a third patch,") + len(
            "in ONE batch instead of a third patch,"
        )
        span = text[start : text.index(" and the row's method cell APPENDS", start)]
        assert span == clause.format(unit), (name, span)
    picker = re.sub(
        r"\s+", " ", (ROOT / "commands" / "_fragments" / "term-coverage.md").read_text()
    )
    assert "own-fix defect, recast, when it is not deleted, as the whole list filtered" in picker


def test_a_routed_fix_carries_its_invariant_and_shapes() -> None:
    """Row 1792291617, a recurrence of held reproduction-verbatim-in-fix-brief (1791058267): the lead routed a fix to
    a coder as a patch, and the coder's version held for the reported shape only. The fix list now carries the
    invariant, the shapes the replaced form held and the reproduction, right after the shapes are enumerated."""
    text = _norm(SRC)
    start = text.index("asked here of every replaced form)?") + len(
        "asked here of every replaced form)?"
    )
    end = text.find("A **wrong fix to a real finding is itself a defect**", start)
    assert end != -1, "the wrong-fix sentence still follows"
    assert text[start:end].strip() == (
        "A fix the lead hands to a coder subagent to implement is written in the pass's fix list as the invariant it"
        " must hold plus those shapes and the reproduction it answers (for a PLAUSIBLE survivor fixed defensively,"
        " its failure scenario), never as the patch alone."
    )


def test_both_review_commands_carry_the_seat_isolation_sentence_verbatim() -> None:
    """Rows 1792303600, 1792302600 (three earlier answered rejects on seat staging): /fabrik-review's brief pointer to
    the probe catalogue carries review-scoped's § Seat isolation sentence word for word up to its recipe's roots, so a
    lead copying either command's brief stages the whole archive. review-scoped's 'it is not restated here' is left out
    of fabrik-review, whose brief list restates `PIN_IMPORT`. Mutant: drop or reword it in either source."""
    src = ROOT / "commands" / "_sources"
    flat = {
        n: " ".join((src / f"{n}.md").read_text().split())
        for n in ("fabrik-review", "fabrik-review-scoped")
    }
    tail = "the pytest config with the roots)"
    start = flat["fabrik-review-scoped"].find("Its § Seat isolation applies whole")
    assert start >= 0
    end = flat["fabrik-review-scoped"].find(tail, start)
    assert end > start
    sentence = flat["fabrik-review-scoped"][start : end + len(tail)]
    assert flat["fabrik-review"].count(sentence) == 1
    # per paragraph, so text appended after the sentence or a paragraph break before it is caught
    paras = [
        " ".join(p.split()) for p in re.split(r"\n[ \t]*\n", (src / "fabrik-review.md").read_text())
    ]
    pointer = [
        p for p in paras if "isolation and bookkeeping steps earlier runs found missing." in p
    ]
    assert len(pointer) == 1
    assert pointer[0].endswith(
        "isolation and bookkeeping steps earlier runs found missing. " + sentence + "."
    )
    assert "it is not restated here" not in flat["fabrik-review"]


def test_the_gate_runs_before_the_closing_pin_so_a_gate_fix_is_reviewed() -> None:
    """Row 1792335517, the second sighting of held final-gate-before-closing-pass: a fix final_gate forced landed
    after the closing seats had read the surface."""
    text = _norm(SRC)
    sentence = (
        "Before the pin of every pass that follows a fix (any of them may be the closing pass), stage your own files"
        " and run `final_gate.py --check --json` too, so a fix the gate forces is in the surface that pass's seats read;"
        " a red outside the surface forces no fix (measure it as the `GATE-SCOPE` paragraph below does, and pin"
        " unchanged). Close in this ORDER:** 1. Stage your own files"
    )
    assert sentence in text


def test_an_in_surface_red_at_the_close_reopens_a_closing_pass_over_the_fix():
    """W-c71703cb: a fix forced by the post-flip gate run is read by a new closing pass, never shipped unreviewed."""
    assert (
        "embed THAT run in place of the first (a red whose findings name this surface or its receipt is yours: flip"
        " back to `IN-PROGRESS`, fix it, run a new closing pass unless the fix edits the receipt alone, and repeat the"
        " order;"
    ) in _norm(SRC)
    assert "or its receipt is fixed as the post-flip run's is). 3. THEN flip the Status" in _norm(
        SRC
    )
    assert (
        "A finding that names this review's receipt counts as naming this surface. A non-zero count is YOUR debt, not"
        " another lane's — fix it as the close order fixes a red whose findings name this surface or its receipt."
    ) in _norm(SRC)


def test_a_seat_brief_runs_the_tests_that_load_each_changed_module() -> None:
    """Row 1792359501 (a recurrence of held full-suite-import-time-registration): the catalogue said HOW a seat runs
    tests, never WHICH — so a new import that breaks a stubbed loader, which only the tests loading the module by path
    exercise, passed every review run. The brief now names those tests for every seat to run."""
    text = re.sub(
        r"\s+", " ", (ROOT / "commands" / "_fragments" / "review-probe-catalogue.md").read_text()
    )
    assert (
        "tests run by exact node id, and a brief over changed code names the tests that load each changed "
        "module (by import, or by path through a loader or a stub — found by grepping `tests/` for each "
        "changed file's stem, its name without `.py`, or an `__init__.py`'s package dotted name, and keeping "
        "the hits that import or load it) for every seat to run by the `PIN_IMPORT`/`PYTEST_PINS` recipe (a "
        "test it leaves unrun stays unverified), so a new import that breaks a stubbed loader reds in the "
        "pass."
    ) in text


def test_the_close_order_is_a_numbered_list_with_the_embed_its_own_step() -> None:
    """Rows 1792410448, 1792405487: the embed step sat mid-sentence and was skipped; the order is now four items."""
    text = _section(
        _norm(SRC),
        "Close in this ORDER:**",
        "A `CONVERGED` receipt with nothing embedded is refused",
    )
    raw = SRC.read_text()
    block = raw[
        raw.index("Close in this ORDER:**") : raw.index(
            "A `CONVERGED` receipt with nothing embedded"
        )
    ]
    items = [line[:3] for line in block.splitlines() if line[:1].isdigit()]
    assert items == ["1. ", "2. ", "3. ", "4. "], items
    assert " 1. Stage your own files" in text
    assert " 2. Embed that JSON in a fence" in text
    assert " 3. THEN flip the Status to `CONVERGED`." in text
    assert (
        " 4. THEN run the gate once more" in text and "embed THAT run in place of the first" in text
    )


def test_a_duplicate_raise_of_a_confirmed_defect_is_not_a_residual_row() -> None:
    """Row 1792427611: the Residual sentence read literally took a second seat's raise of a confirmed defect."""
    residual = _section(
        _norm(SRC),
        "**Every candidate that did not enter `confirmed:` is rowed",
        "Pre-existing issues",
    )
    assert (
        "A second seat's raise, in the same pass, of a defect another candidate of that pass confirmed by execution is"
        " named in that defect's disposition row and counted under its terminal state, never rowed here; a later"
        " pass's raise of a defect an earlier pass fixed is a fresh candidate, executed."
    ) in residual


def test_a_seat_proposed_behaviour_change_is_probed_against_its_bound() -> None:
    """Row 1792455454 (a recurrence of held refuter-run-proposed-fix): a seat's suggested change was applied unprobed."""
    p3 = _section(
        _norm(SRC), "**A real finding does not make the obvious fix correct", "no performative"
    )
    assert (
        "for a behaviour change a seat proposed, does a probe on a copy show the change still holds the bound it"
        " claims to protect?"
    ) in p3


def test_a_later_pass_brief_carries_the_environment_earlier_seats_set() -> None:
    """Row 1792447814 (a recurrence of held closing-pass-kaizen-state-dir): seats rediscovered env every pass."""
    p4 = _section(_norm(SRC), "## Phase 4 — Converge", "**The round in which you made a fix")
    assert (
        "It carries, too, every environment value an earlier pass's seats set before their probes ran (a state"
        " directory, `COMMAND_RUN_DIR`, a `transcripts_dir` source), copied from their `MACHINERY:` notes"
    ) in p4


def test_a_generated_script_names_each_root_only_path_as_a_referent() -> None:
    """Row 1792415591 (a recurrence of held copy-create-privilege-chain): finders checked only the work-dir token."""
    p1 = _section(_norm(SRC), "## Phase 1 — Independent finders", "## Phase 2")
    assert (
        "for a **generated script**, every path it touches that only root may write, so its privilege is checked"
        " path by path, never at the work-dir token alone."
    ) in p1


def test_a_counter_word_in_a_method_cell_is_named_as_refused() -> None:
    """Row 1792413725 (a recurrence of held counter-word-colon-cell-restriction), executed: a `Confirmed: 2` in a
    Method cell gets the row refused by _row_refusals, so the sentence beside the Method-cell example says so."""
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(
            "crc_q", ROOT / "scripts" / "enforcement" / "check_review_coverage.py"
        )
        crc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(crc)
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    row = "| Pass 2 | sonnet×1 + haiku×1 | found: 2, new: 1, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — "
    assert crc._row_refusals(row + "Confirmed: 2 by A-sonnet |")
    old_grammar = "| Pass 2 | sonnet×1 | found: 2, fixed: 0 | method: re-derivation — "
    assert not crc._row_refusals(
        old_grammar + "CONFIRMED: two by A-sonnet |"
    )  # the _label_exempt carve-out
    assert not crc._row_refusals(row + "seats: A-sonnet 3/4 |")
    assert (
        "a `confirmed:` or `unexecuted:` outside the counter cell, `Confirmed: 2` included, gets a row whose counters"
        " state `confirmed:` refused by `check_review_coverage.py`'s token rule, `_row_refusals` — only an ALL-CAPS"
        " prose label on a row with no `confirmed:` counter is exempt, `_label_exempt`"
    ) in _norm(SRC)


def test_a_shifted_anchor_is_remapped_after_each_round_fix() -> None:
    """Row 1792464841 (a recurrence of held cite-remap-after-every-round): anchors were retargeted only at the end."""
    assert (
        "never renumbered by hand, and the remap runs after each round's fix, before the next pin, over every anchor a"
        " brief or mutant list carries."
    ) in _norm(CAT)


def test_a_review_whose_fixes_are_committed_makes_its_receipt_once() -> None:
    """W-60629ce4 (D-1070): the committed-fix form keeps a generated draft during the passes and writes the receipt
    once, after the last fix commit; every other form creates it before Pass 1. Each clause is pinned where it
    lives — the fragment's obligation 3 (included by five command sources) and the later-pass high-water mark."""
    frag = _norm(ROOT / "commands" / "_fragments" / "term-coverage.md")
    for clause in (
        "One form makes it later — `/fabrik-review` over work whose review FIXES are COMMITTED during the review",
        "--out <SCRATCH>/<scope>-receipt-draft.md",
        "`review_receipt.py --init --lane --changed <every path in base..last> --scope <slug> --range <base>..<last"
        " fix commit>` writes the receipt under `docs/development/reviews/` once",
        "a class row the late rubric adds that the draft lacked is a hunt still owed, never carried `CLEAN`",
        "the receipt becomes the draft again: move it back over the draft (`mv`, since it is not yet committed and `--init` never overwrites)",
        "and every other command this fragment renders into — creates it NOW",
        "at the close — after the last fix commit and a `final_gate.py --check --json` run that forced none —",
        "then the close ORDER of `/fabrik-review` § Reporting runs on it",
        "A fix that ORDER still forces is a closing-pass fix: commit it",
    ):
        assert clause in frag, clause
    assert (
        "the receipt's sha at dispatch (in the committed-fix form below, the draft's last row id and md5)"
    ) in _norm(SRC)
    task = _norm(ROOT / "commands" / "_sources" / "fabrik-task.md")
    assert (
        "run `final_gate.py --check --json` BEFORE that `--init`, so a fix the gate forces is a run commit that"
        " lands first"
    ) in task
    assert (
        "run `/fabrik-review`'s close ORDER on it (the gate while IN-PROGRESS, embedded, flipped to"
        in task
    )
    assert "carry the draft's rows into it (a rubric class the draft lacked is a hunt still owed)" in task
