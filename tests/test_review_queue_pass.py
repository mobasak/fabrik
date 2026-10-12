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


def test_the_round_grammar_names_own_fix() -> None:
    """Row 1791764618 (D-778)."""
    assert "--own-fix <how many of those confirmed defects lie in text this review added in an earlier round>" in _norm(SRC)


def test_a_callers_plan_flip_follows_the_post_flip_gate_run() -> None:
    """Row 1791828832 (D-778): the reason is check_convergence's own skip."""
    assert "A caller that flips its plan to `EXECUTED` flips it only after that post-flip run is embedded: a red post-flip run sends the receipt back to `IN-PROGRESS`" in _norm(SRC)
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
    pats = [v for v in vars(check_convergence).values() if isinstance(v, re.Pattern) and "GATE-SCOPE" in v.pattern]
    assert len(pats) == 1
    assert not pats[0].search(line)
    assert pats[0].search(line.replace("<failing check>", "docs-links").replace("<N>", "3").replace("<command>", "grep x"))
