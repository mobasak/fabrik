"""/fabrik-spec feedback queue answered in one pass (D-735, D-760).

Each test pins one sentence in the section that owns it; the 1a wording is also run through the
convergence check's own pattern, so the recipe the command gives is one the check accepts.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-spec.md"
RESEARCHER = ROOT / "commands" / "_agents" / "fabrik-researcher.md"
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_spec_convergence  # noqa: E402


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(start: str, end: str) -> str:
    text = _flat(SRC)
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_an_amendment_states_no_external_facts_in_words_the_check_reads() -> None:
    """Row 1789399457: the recipe sentence clears SILENT-1a; the 'no NEW external facts' wording does not."""
    s1a = _section("### 1a", "### 1b")
    m = re.search(r"`(This amendment adds no external facts beyond [^`]+)`", s1a)
    assert m, "1a gives no amendment recipe"
    assert check_spec_convergence.NO_EXTERNAL_RE.search(m.group(1))
    assert not check_spec_convergence.NO_EXTERNAL_RE.search(
        "This amendment adds no new external facts."
    )


def test_a_best_practice_seat_carries_the_1a_facts() -> None:
    """Row 1791761722."""
    s1c = _section("### 1c", "## Phase 2")
    assert (
        "A 1c (best-practice) seat is dispatched after the 1a facts it rests on are grounded or executed"
        in s1c
    )
    assert "the 1a wave and the 1c wave are two dispatches" in s1c


def test_self_review_grades_a_converged_copy_of_the_draft() -> None:
    """Row 1789139668: the script never grades a DRAFT, so the self-review grades a flipped copy."""
    p5 = _section("## Phase 5", "## Phase 6")
    assert "set the copy's Status line to `CONVERGED`" in p5
    assert "scripts/enforcement/check_spec_convergence.py <the copy>" in p5
    assert "a DRAFT is not graded" in p5
    assert "`/fabrik-plan-review` for a `Size: small` spec" in p5


def _grade(tmp_path: Path, body: str, capsys) -> str:
    spec = tmp_path / "2026-10-12-amend-design.md"
    spec.write_text(body)
    check_spec_convergence.main([str(spec)])
    return capsys.readouterr().out


def test_the_check_skips_a_draft_and_grades_its_flipped_copy(tmp_path: Path, capsys) -> None:
    """The Phase 5 and 1a sentences, executed: the DRAFT is skipped; the copy prints the findings named."""
    draft = "# Amend\n\n**Status:** DRAFT\n\nThis amendment adds no new external facts.\n"
    assert "a DRAFT is not graded" in _grade(tmp_path, draft, capsys)
    flipped = _grade(tmp_path, draft.replace("DRAFT", "CONVERGED"), capsys)
    for finding in ("SILENT-1a", "APPROACH-FLOOR", "NO-PERSONAS", "NO-LIFECYCLE", "NO-INTAKE"):
        assert finding in flipped, finding
    recipe = draft.replace("DRAFT", "CONVERGED").replace(
        "adds no new external facts.",
        "adds no external facts beyond docs/x-design.md, last verified live 2026-09-01.",
    )
    graded = _grade(tmp_path, recipe, capsys)
    assert "SILENT-1a" not in graded and "APPROACH-FLOOR" in graded


def test_researcher_quotes_schema_and_versions_from_a_raw_fetch() -> None:
    """Row 1791275601."""
    text = _flat(RESEARCHER)
    assert (
        "on an HTML docs page a schema field or a parameter name is quoted from the raw arm" in text
    )
    assert "JSON/XML and version claims keep rule 3's routing" in text


def test_the_skip_line_routes_an_as_built_revision_to_an_amendment() -> None:
    """Row 1791859866: a CONVERGED spec's as-built re-freeze had no named home in the description."""
    desc = next(line for line in SRC.read_text().splitlines() if line.startswith("description:"))
    assert (
        "an as-built revision of a CONVERGED spec stays here as an amendment (`Profile: delta`)"
        in desc
    )


def test_local_claim_output_describes_key_material_never_pastes_it() -> None:
    """Row 1791966633: the spec cites each local claim's output, and the commit hook refuses a private-key PEM header."""
    text = re.sub(r"\s+", " ", SRC.read_text(encoding="utf-8"))
    assert (
        "its command and output cited in the spec (a key, token or credential in that output is described by its"
        " kind, length and a non-secret prefix, never pasted, its BEGIN line included: the `detect-private-key`"
        " commit hook refuses a private-key PEM header)"
    ) in text


def test_a_build_tool_setting_is_probed_by_a_build_or_its_source() -> None:
    """Row 1792191153, a recurrence of held execute-pack-config-before-relying: a design relied on a build-tool
    option its docs page described, and the build behaved otherwise."""
    phase = _section("### 1a — External facts", "### 1b — Internal capability")
    assert (
        "A build-tool setting the design relies on (any bundler, compiler, test-runner, package-manager or CI option, a"
        " config file's default included) is settled by a build you run or by the tool's own source read through `gh`"
        " — its docs page locates the setting but never settles it — else it is a named BLOCKING unknown."
    ) in phase
