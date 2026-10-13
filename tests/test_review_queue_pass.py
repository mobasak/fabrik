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
        "on a copy: ruff `--config <repo>/pyproject.toml`, mypy `--config-file` with the same path"
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
    """Row 1791910374, a recurrence of the held gitdir-shim-recipe ("a history-reading test recipe"): the catalogue forbade
    `git worktree add` but a `git archive` pin has no history, so a history-reading test had no sanctioned route. The
    D-711 audit ran the clone: alternates point at the shared objects and nothing in the shared `.git` changed. Its own
    sentence, after the worktree ban, so the ban's colon still leads to the archive red-on-revert; live text only (an
    HTML comment around it reds). Not seen: a seat that runs the test in the archive anyway; the seat's red owns it."""
    iso = re.sub(
        r"<!--.*?-->", "", _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    )
    assert (
        "before its first gate. A seat test that reads git history runs in `git clone --shared --no-checkout <live repo>"
        " <scratch>/clone` at the pass's base SHA with the pins laid over it, and that test's red-on-revert overlays the"
        " revert on the clone: the clone reads the shared objects and writes nothing to the shared `.git`, but its only"
        " local branch is the live checkout's and every other is `origin/*`, so a test that inspects branch, worktree or"
        " stash state runs in the lead's throwaway worktree. Ruff" in iso
    )
    assert (
        "A SEAT never runs `git worktree add` (its metadata lands in the shared `.git`): a seat's red-on-revert overlays"
        " the revert on its archive copy" in iso
    )
