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
    assert "/opt/fabrik/commands/_fragments/review-probe-catalogue.md` that match the change's SHAPE" in _norm(SRC)
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
    assert "owes every round's readers — round 1's first — and that INDEPENDENT reader the guard or rule by NAME" in (
        _norm(SRC)
    )


def test_command_run_is_cited_by_symbol_not_line() -> None:
    """The line anchors into command_run.py had drifted (:556, :508, :593-595, :880, :2547-2554, :3116)."""
    text = _norm(SRC)
    assert not re.search(r"command_run\.py:\d", text)
    assert "`command_run.py::_trend_label`" in text
    assert "`command_run.py::AGENT_CLOSED_STATES`" in text


def test_a_revendor_brief_hands_the_byte_identity_result_as_a_claim() -> None:
    """Row 1791769363 (D-776)."""
    premise = _section(_norm(CAT), "- The premise:", "## Graders")
    assert "a re-vendor brief hands the seats the lead's executed byte-identity result (the diff command and its output) as a claim to attack" in premise
    assert "they re-run that command first, then spend on what byte identity cannot show: the vendored copy's own header and every importer of it" in premise


def test_seat_isolation_names_every_root_the_tests_import_read_or_run() -> None:
    """Rows 1791774523, 1791785471: the archive roots and the live repo."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    assert "the brief extends it to every top-level path the tests import, read or run" in iso
    assert "`templates/`, reads `.windsurf/` or runs `scripts/` by subprocess" in iso
    assert "names the live repo as the checkout `git rev-parse --show-toplevel` prints, never `/opt/fabrik` from a worktree" in iso


def test_own_fix_guards_helper_contracts_and_pinned_versions() -> None:
    """Rows 1791833683, 1791830180, 1791831690; 1791830163 rests on the scoped source's own guard rule."""
    text = _norm(CAT)
    assert "Run the changed artifact end to end when it can run (an emitted one-liner run as emitted, under its real shell)" in _section(text, "## Before the first pin", "## The brief's hunt lines")
    assert "a pure helper's own return contract, not only what its callers observe" in _section(text, "- Callers and consumers:", "- Parsers:")
    assert "a `fabrik-researcher` seat whose brief names the version the repo pins or deploys (its lockfile or spec line) and asks for the claim at that version" in _section(text, "- The premise:", "## Graders")
    assert "an explicit ASK for its ESCAPE VARIANTS" in _norm(ROOT / "commands" / "_sources" / "fabrik-review-scoped.md")
    assert max(len(line) for line in CAT.read_text().splitlines()) <= 120


def test_a_new_sibling_of_a_pinned_line_reads_its_comment_first() -> None:
    """Row 1791836370."""
    before = _section(_norm(CAT), "## Before the first pin", "## The brief's hunt lines")
    assert "before adding a sibling of a pinned or guarded line, read the comment on the line it copies" in before


def test_a_guard_brief_states_its_model_boundary() -> None:
    """Row 1791839280."""
    src = _norm(ROOT / "commands" / "_sources" / "fabrik-review-scoped.md")
    assert "an explicit ASK for its ESCAPE VARIANTS" in src
    assert "together with its MODEL BOUNDARY, the inputs it is meant to judge, so a variant outside that boundary is `RECORDED — by design (D-785)` in round 1" in src
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
    assert "A script a seat runs is run from its archive copy with every path argument under scratch (a script may treat any argument as a write path)" in iso
    assert "the pin carries the changed files' one-hop callees that are repo files (`review_loop_ledger.py pin` refuses the whole list when one path is missing, a symlink or outside the repo root)" in iso


def test_a_silent_refuter_is_already_retried_once_and_marked_failed() -> None:
    """Row 1791826392 (mailed): the workflow already retries; the ledger's `read` table is the gap."""
    js = (ROOT / ".claude" / "workflows" / "fabrik-review-loop.js").read_text()
    assert "const retry = await refuteCall(r.slice, missing, '-retry')" in js
    assert "STILL UNANSWERED (refuter failed)" in js


def test_a_reimplemented_tool_is_checked_against_its_own_output() -> None:
    """Row 1791844847: a fix modelling js-yaml's merge from memory took three rounds."""
    text = _norm(CAT)
    lead = text[text.index("## Before the first pin (the lead executes)") : text.index("- One mutant per clause")]
    assert "or reimplement another tool's semantics (a YAML merge, a compose override), and prove parity by an executable diff against that tool's own output over its edge cases (for a merge: nesting, mixed types, cycles) before the fix lands, never a model from memory" in lead


def test_a_matcher_sentence_is_executed_over_its_input_space() -> None:
    """Row 1791851271: two own-fix rounds came from a sentence about a regex nobody ran."""
    text = _norm(CAT)
    claims = text[text.index("- Claims:") : text.index("- A site a round re-opened")]
    assert "a sentence describing a matcher or regex executed over its input space (punctuation, underscore, empty) before the pin" in claims


def test_a_brief_names_the_fix_by_sha_never_a_bare_range() -> None:
    """Row 1791852611: a two-dot range over a shared branch carried another item's 1278 lines."""
    text = _norm(CAT)
    assert "The brief names the fix as `git show <sha>` — each sha when the fix spans several commits — or a pathspec-scoped diff, never a bare range on a branch others commit to" in text


def test_a_compose_overlay_is_read_through_its_merged_render() -> None:
    """Row 1791860340: precedence and port exposure only show in the merged compose render."""
    text = _norm(CAT)
    surfaces = text[text.index("- Surfaces:") : text.index("- The premise:")]
    assert "a changed compose overlay read through its merged render (`docker compose -f <base> -f <overlay> config`)" in surfaces


def test_a_shifted_cite_is_remapped_by_content_in_one_script() -> None:
    """Row 1791866581 (recurs held anchor-sweep-auto-compares-symbols): remapping by number took two passes."""
    text = _norm(CAT)
    sweep = text[text.index("- Sweep:") : text.index("- Claims:")]
    assert "a `path:line` cite a merge or an edit shifted, remapped by CONTENT in one script over every doc that cites the file" in sweep


def test_the_guard_or_rule_clause_defines_a_rule_and_names_its_cobra() -> None:
    """W-a8361c19: 'states a RULE' was undefined, the clause had no cobra counter, and it miscited D-066."""
    text = _norm(SRC)
    assert "A change that ships a GUARD, or states a RULE (any sentence with must, never or owes), owes" in text
    assert "Cobra: a brief can name variants nobody tests; the closing pass counts only variants a reader executed." in text
    assert "D-066 named only the heavy command" not in text
