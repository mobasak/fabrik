"""/fabrik-features feedback queue answered in one pass (D-735, D-765).

Each test pins one sentence in the section that owns it; the plan-template terms the scoped mode names
are checked against the plan command that defines them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-features.md"
PLAN = ROOT / "commands" / "_sources" / "fabrik-plan-after-chat.md"
EXECUTE = ROOT / "commands" / "_sources" / "fabrik-execute-plan.md"


def _section(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_early_rows_cite_symbols_and_resolve_work_items() -> None:
    """Rows 1790688007, 1789583713, 1791507475."""
    p0 = _section("## Phase 0", "## Phase 1")
    assert "cites a SYMBOL in a named file (`src/billing.py::charge`), never a line number" in p0
    assert "resolves to `.fabrik/work/W-xxxxxxxx.json` in the store of the repo that filed it" in p0
    assert "a Planned row's symbol in a named file" in _section(
        "## Guardrails", "{{include:subagents-core}}"
    )


def test_scoped_refresh_names_its_denominator() -> None:
    """Rows 1791028841, 1791015873, 1790950308: the terms it names are the plan template's own."""
    p0 = _section("## Phase 0", "## Phase 1")
    assert (
        "**REFRESH, scoped** (`$ARGUMENTS` names a plan dir or one FEATURES section): the CODE stays the denominator"
        in p0
    )
    assert (
        "every row its merged tickets' `## Deltas` blocks wrote (`/fabrik-execute-plan` D3) is re-grounded"
        in p0
    )
    assert "A scoped run never hands off to certification" in p0
    assert "## Behavior Contract" in PLAN.read_text()
    assert "### D3 — Shared governance files: orchestrator-applied Deltas" in EXECUTE.read_text()


def test_rows_cover_every_route_mode_and_point_at_backlog_for_defects() -> None:
    """Rows 1791227229, 1790961162."""
    p2 = _section("## Phase 2", "## Phase 3")
    assert (
        "holds for every mode the route serves — its default and each query-parameter variant" in p2
    )
    assert (
        "a known defect is a pointer to its backlog row or work item, never an enumeration of its cases"
        in p2
    )
    assert "A shipped row states the CURRENT behaviour" in p2


def test_coverage_names_each_population_before_counting() -> None:
    """Row 1790692088."""
    p3 = _section("## Phase 3", "## Guardrails")
    assert "name each denominator's expected population and where it comes from" in p3
    assert (
        "never by `tail -n +N` after a filter (a separator row the filter drops shifts the offset)"
        in p3
    )


def test_a_grounded_code_defect_is_filed_never_patched() -> None:
    """Row 1791827504 (D-788): the doc-converge exit, in the phase that grounds rows."""
    p2 = _section("## Phase 2", "## Phase 3")
    assert (
        "A code defect the grounding finds with no row yet is filed to its owner (a mail to the code's owning session, or a backlog row) and the feature row points at that id — never patched inside a features run"
        in p2
    )


def test_a_planned_row_quotes_every_condition_of_its_spec_clause() -> None:
    """Row 1792017544 (infra, the coordinator-role EARLY run): rows written as summaries dropped the spec's
    conditions, and round 1 confirmed 14 findings from that one cause. Phase 0 EARLY asked only that a row be
    'traceable to the spec', which a paraphrase satisfies; it now says the Description states the behaviour, then
    carries `Spec §<n>:` and EVERY condition in the spec's own words, quoted as whole spans; REFRESH keeps those
    conditions on the row until a test asserts each. Mutants: delete the sentence, 'EVERY condition' to 'the
    conditions', drop 'never reworded', drop 'never elided', drop the section cite, move the sentence into the
    REFRESH bullet, prefix or suffix the EARLY bullet with 'where practical', drop the REFRESH clause — each fails
    an assertion (the sentence is bounded at its own full stop; the weakener scan covers the whole EARLY bullet)."""
    p0 = _section("## Phase 0", "## Phase 1")
    early = p0[p0.index("- **EARLY**") : p0.index("- **REFRESH** (post-build")]
    head = "A Planned row's Description states the behaviour as Phase 2 asks of every row, then carries `Spec §<n>:`"
    assert head in early, "the fidelity sentence left Phase 0's EARLY bullet"
    rest = early[early.index(head) :]
    sentence = rest[: rest.index("builds without.") + len("builds without.")]
    assert (
        "and EVERY condition of its clause — each when, unless, only-if, limit or other condition, wherever in the"
        " spec it sits, a neighbouring sentence or a table cell included — in the spec's own words or figures,"
        " quoted as whole spans cut only at their ends, never inside, never reworded and never elided with `…`,"
        " the section cited for each span"
    ) in sentence, "the conditions, the whole-span rule and the cite are one contiguous clause"
    assert (
        "a paraphrase still traces to the spec, and still drops the condition the plan then builds without"
        in (sentence)
    )
    assert "trimmed" not in sentence, "'trimmed' contradicted 'never elided' (round-1 finding)"
    # a word list cannot be complete (round-2 finding): pin the sentence's neighbours instead, so any
    # weakening clause inserted before or after it moves a pinned span
    assert "invented scope). A Planned row's Description states the behaviour" in early, (
        "something was inserted between the traceability rule and the fidelity sentence"
    )
    assert "builds without. A Planned row that points at existing code" in early, (
        "something was inserted after the fidelity sentence"
    )
    assert "(`Spec §3: … · §7: …`, on the row's one table line)" in sentence, (
        "the marker's multi-section form and the one-line cell bound"
    )
    for weakener in ("where practical", "where possible", "skip this", "optionally"):
        assert weakener not in early.lower(), weakener
    assert "every row traceable to the spec" in early, (
        "the sentence extends the traceability rule, not replaces it"
    )
    refresh = p0[p0.index("- **REFRESH** (post-build") :]
    assert (
        "its `Spec §<n>:` conditions stay on the row until a test asserts each); a `(Planned)` row with NO"
        in (refresh)
    ), (
        "the Planned-to-shipped flip must not drop the quoted conditions (the mirror of the EARLY rule), unweakened"
    )
