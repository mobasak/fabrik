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
    """The catalogue's rows were asked of /fabrik-review too; Phase 1 names it by its hub path (ledger entry rq-phase1-points-at-probe-catalogue)."""
    assert CAT.exists()


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


def test_a_callers_plan_flip_follows_the_post_flip_gate_run() -> None:
    """Row 1791828832 (D-778): the reason is check_convergence's own skip."""
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
    assert mod._REDERIVATION_ROW.search(
        "| Pass 3 | sonnet×1 | found: 0 | method: re-derivation — closing pass |"
    )
    assert not mod._REDERIVATION_ROW.search(
        "| Pass 3 | sonnet×1 | found: 0 | method: remainder pass — re-derivation |"
    )


def test_an_agent_tool_seat_gets_the_pin_import_placement() -> None:
    """Mail 01M4W155SB (intel): the Agent-tool seat list states PIN_IMPORT's sys.path placement and its -P condition
    and points at the recipe, and the pointed-at recipe still says the same."""
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


def test_a_by_design_d_owner_is_a_ledger_row_and_the_refusals_point_at_the_gate() -> None:
    """Mail 01M4YS0EZV (W-91ef9165): infra's 66ed34d47 (D-876) made check_review_coverage V5 refuse a by-design
    D-nnn absent from the checkout's ledger. Phase 2's bullet, where the grammar is defined, now says the D-owner
    is a row of that ledger; the Reporting paragraph points at the gate's own messages instead of listing a subset
    (a three-item list missed three refusals and the ledger check's fail-open)."""
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


def test_the_close_order_is_a_numbered_list_with_the_embed_its_own_step() -> None:
    """Rows 1792410448, 1792405487: the embed step sat mid-sentence and was skipped; the order is now four items.
    The four steps' text is ledger entries (rq-close-order-four-steps-*, ordered); the list shape is raw text."""
    raw = SRC.read_text()
    block = raw[
        raw.index("Close in this ORDER:**") : raw.index(
            "A `CONVERGED` receipt with nothing embedded"
        )
    ]
    items = [line[:3] for line in block.splitlines() if line[:1].isdigit()]
    assert items == ["1. ", "2. ", "3. ", "4. "], items


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
