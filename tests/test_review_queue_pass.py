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


def test_every_workflow_command_carries_the_no_workflow_in_the_hub_note() -> None:
    """D-961: the override sits at the TOP of every source that launches the review-loop Workflow, so
    no lead sentence ("They run as ONE `Workflow` call …") is read before it; the note names the hub
    test and replaces every launch, later passes and relaunches included."""
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
    assert (
        "survivors reported only once shown to change observable behaviour (an output, return value, exit code, raised"
        " exception or written state diffed against the unmutated copy), and an equivalent mutant is struck with that"
        " diff quoted, never a test gap"
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
    assert "attack only" not in row, "'only' forbade probing wrongful refusals (round-1 finding)"
    for weakener in ("where time allows", "where practical", "optionally", "should"):
        assert weakener not in row.lower(), weakener


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
    # it sits between the Surfaces row and The premise row, the shape order the lead reads top to bottom
    assert hunt.index("- Surfaces:") < hunt.index("- Deletions (") < hunt.index("- The premise:")
    # one deletion row, however a second one is headed: the probe's own phrase appears once in the whole catalogue
    assert cat.count("- Deletions (") == 1
    assert cat.count("deleting probe") == 1


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


def test_a_review_whose_fixes_are_committed_makes_its_receipt_once() -> None:
    """W-60629ce4 (D-1070): the committed-fix form keeps a generated draft during the passes and writes the receipt
    once, after the last fix commit; every other form creates it before Pass 1. Each clause is pinned where it
    lives — the fragment's obligation 3 (included by five command sources) and the later-pass high-water mark."""
    assert (
        "the receipt's sha at dispatch (in the committed-fix form below, the draft's last row id and md5)"
    ) in _norm(SRC)


CORE = ROOT / "commands" / "_fragments" / "subagents-core.md"


def _clause(text: str, after: str, end: str = ";") -> str:
    """The clause that immediately follows `after`, up to and including its first `end`."""
    assert after in text, f"anchor moved: {after!r}"
    i = text.index(after) + len(after)
    return text[i : text.index(end, i) + len(end)]


def test_a_worktree_lead_writes_scratch_files_directly() -> None:
    """D-1288: SCRATCH is the worktree's own since D-1268, so the cp-copy workaround of rows 1792495473,
    1792488144 and 1792486681 is gone and the pins sentence runs straight on to the tree-staging rule."""
    core = _norm(CORE)
    assert "do so an interrupted pass keeps its pins; and a tree" in core
    assert "01M4Y3N9GW" not in core and "refuses that main-checkout" not in core
    # a reworded reintroduction of the workaround (review pass 1, C4)
    assert "a reboot clears" not in core and "by a Bash `cp`" not in core


def test_fix_then_dispatch_the_reverifying_seats() -> None:
    """D-1288 (mail 01M5X8W0M1): `round`'s NOT TERMINAL anchor is the round's RECORD time, so a seat
    dispatched, or a pin cut, after the record but before its fix lands reads fresh (D-1268's accepted risk)."""
    core = _norm(CORE)
    rule = "**Fix, THEN pin and dispatch the re-verifying seats:**"
    record = "**Record the dispatch BEFORE you send it:**"
    assert rule in core
    # the why stays with the rule, right before the dispatch stamp (review pass 1, C3)
    assert "whether or not the fix has landed or is in the pin its seats read" in core
    assert 0 < core.index(record) - core.index(rule) < 400


def test_a_cwd_rooted_tool_runs_after_an_os_chdir(tmp_path: Path) -> None:
    """Row 1792495913: docs_updater roots at the cwd, so a seat's absolute argument rewrote the live INDEX.md."""
    clause = _clause(
        _norm(CORE),
        "absolute paths for anything written or run (the shell returns to the live checkout before every call); ",
    )
    assert clause == (
        "a tool that roots itself at the working directory (`scripts/docs_updater.py`'s `PROJECT_ROOT ="
        " Path.cwd()`) runs only from a python program that `os.chdir`s into the seat's copy before it imports or"
        " runs the tool, since an absolute argument does not move that root and a `cd` in its own call does not"
        " persist;"
    )
    core = _norm(CORE)
    assert core[core.index(clause) + len(clause) :].startswith(" never `pkill`"), (
        "a clause was added after the rule"
    )
    import subprocess
    import sys

    program = (
        "import os, sys; os.chdir(sys.argv[1]); sys.path.insert(0, sys.argv[2]); import docs_updater;"
        " print(docs_updater.PROJECT_ROOT)"
    )
    out = subprocess.run(
        [sys.executable, "-B", "-c", program, str(tmp_path), str(ROOT / "scripts")],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.strip()
    assert Path(out).resolve() == tmp_path.resolve()


def test_a_by_design_owner_row_decides_its_residual() -> None:
    """Row 1792467497: any existing D-id passed the gate as a by-design owner, a wrong one included."""
    sentence = _clause(_norm(SRC), "which takes no round token. ", ". ")
    assert sentence == (
        "That row is the one that decides THIS residual (its text names the subject's file or mechanism), since"
        " the gate checks only that the owner exists (a D-id in this checkout's `docs/DECISIONS.md`, a receipt"
        " row on another line with an earlier round), so any existing id passes it. "
    )
    src = _norm(SRC)
    assert src[src.index(sentence) + len(sentence) :].startswith("The parentheses hold the owner")


SUB = ROOT / "commands" / "_fragments" / "subagents-core.md"


def test_the_example_ledger_names_the_file_loops_seat_mix() -> None:
    """Row 1792607399: the example Pass rows named an Opus finder the file loop no longer seats (D-344)."""
    text = _norm(SRC)
    assert "| Pass 1 | sonnet×3 + haiku×3 | found: 5," in text
    assert "| Pass 2 | sonnet×1 + haiku×1 | found: 2," in text
    assert "| Pass 3 | sonnet×3 + haiku×3 | found: 1," in text
    assert "Note pass 3: the finders raised one FRESH candidate" in text
    assert "opus×1 + sonnet×3" not in text


def test_a_fix_between_round_one_waves_is_in_the_delta_surface() -> None:
    """Row 1792593605 (held trimmed-wave-round-recording): a fix made between waves had no stated pin or diff."""
    assert (
        "since round 1 is not complete until every slice is read. A fix the lead makes between waves is in the next"
        " wave's pin, as every fix is in the pin cut after it. **By SECTION,"
    ) in _norm(SUB)


def test_the_lead_creates_each_seat_folder_before_dispatch() -> None:
    """Row 1792628374 (held lead-creates-seat-dirs-before-dispatch, second verdict): a seat wrote into a folder nothing
    had made; the lead now makes it before the dispatching message and the seat's own mkdir stays as a no-op."""
    core = _norm(ROOT / "commands" / "_fragments" / "subagents-core.md")
    assert (
        "for a seat the lead briefs itself (a `Workflow` seat's prompt makes its own folder) the lead creates the folder"
        " with `mkdir -p` on its absolute path before the dispatching message, while the brief still tells the seat to"
        " run that same `mkdir -p` first (a no-op once the folder exists);"
    ) in core
    assert "nothing creates it for the seat" not in core
