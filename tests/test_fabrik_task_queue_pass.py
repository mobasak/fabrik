"""/fabrik-task feedback queue answered in one pass (D-735) — each rule sits in the phase that owns it.

Rows answered: the /fabrik-task queue of 2026-10-11, then later passes (each commit's trailer lists its `ts`). Each test
pins one subject's rule inside the section a reader of that phase reads, so a rule moved to the wrong
phase or dropped fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-task.md"
CRITIQUE = ROOT / "commands" / "_fragments" / "design-critique.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(start: str, end: str) -> str:
    text = _norm(SRC)
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_measure_runs_a_codec_change_on_its_edge_inputs() -> None:
    """Row 1792291304, the second verdict on held design-list-input-grammar: MEASURE runs the codec a change touches
    on non-UTF-8 bytes, NUL and that codec's own escape before design.md is written."""
    assert (
        "the codec a change touches run on non-UTF-8 bytes, NUL and that codec's own escape, an independent parser for"
        " a parsed format" in _section("## Phase 1", "## Phase 2")
    )


def test_v1_commits_once_with_the_ledgers_and_graders_execute() -> None:
    """Row 1790689315 (v1's one commit vs phase 5's ledger commit) and S6 (graders)."""
    phase3 = _section("## Phase 3", "## Phase 4")
    assert (
        "At v1 that one commit also carries phase 5's ledgers, so nothing is committed before phase 5"
        in phase3
    )


def test_the_third_review_question_excludes_an_equivalent_implementation() -> None:
    """Row 1790692304: any nameable equivalent implementation read as an UPGRADE verdict."""
    phase4 = _section("## Phase 4", "## Phase 5")
    assert "the declaration said did not exist" not in phase4


def test_the_receipt_range_tip_is_the_last_commit_and_check_d_is_looser() -> None:
    """S5 (receipt close): the lane's recipe makes the tip the LAST --commit (a ban clause the lean
    ledger keeps verbatim); D-1291's check (d) takes any listed commit that only receipts and ledgers
    follow, so the text says never to reorder the list (D-1336)."""
    close = _section("## Phase 5", "## UPGRADE")
    assert "Its range tip must be the LAST `--commit` (`task_lane.py` check (d))" in close
    assert (
        "Check (d) itself is looser than that order: it takes any listed commit as the tip when every"
        " listed commit after it carries only receipts and ledgers, and list order decides nothing,"
        " so never reorder the `--commit` list to pass it." in close
    )
    phase4 = _section("## Phase 4", "## Phase 5")
    assert "that commit its `--range` tip" not in phase4
    assert "its `--range` tip one of the `--commit` values" in phase4
    assert "never captured or passed to `--commit`" in close
    # review_receipt.py requires --changed and --out/--scope; the tip is the last captured sha (round 1).
    assert (
        "--changed <every path in base..that sha> --scope <slug> --range <base>..<that sha>"
        in close
    )


def test_critique_is_not_rerun_on_the_folded_version() -> None:
    """Row 1791070230: 'once per artifact version' read as re-critiquing every folded design.md."""
    text = _norm(CRITIQUE)
    assert "a version that ONLY folds its ACCEPTED concerns is not a new one" in text


def test_size_declares_operator_named_work_as_heavy() -> None:
    """Row 1791755899: operator-named work is lane row 1b's heavy surface, declared at SIZE, not found at phase 4."""
    assert "`heavy=yes` includes operator-named work (lane row 1b)" in _section(
        "## SIZE", "## Phase 1"
    )


    # row 1792287653 (recurring held re-make-receipt-before-the-d-row-cites-it): the range tip is phase 5's last
    # commit, so a D-row the receipt cites is already in it — phase 5's own recipe commits the receipt alone after it


def test_phase_three_formats_the_declared_paths_only() -> None:
    """Row 1791848436: a package-wide formatter run rewrote eight files nobody declared."""
    text = " ".join((ROOT / "commands" / "_sources" / "fabrik-task.md").read_text().split())
    build = text[text.index("## Phase 3 — BUILD") : text.index("## Phase 4 — REVIEW")]
    assert "Never run a formatter by hand beyond the declared paths." in build


def test_design_tabulates_its_inputs_and_the_close_captures_by_subject() -> None:
    """Rows 1792119826, 1792097261, 1792094113 (a status file's third value, a forced refresh under a periodic
    guard and a rule's per-window unit each went untabled), recurring held design-branches-on-several and
    design-list-input-grammar, plus 1792019578 (a parser of another language); rows 1792057883 and 1792056989
    (a grown hook output passed the 10,000-character cap); row 1792008185 (`--terminal-amend` read as a later
    step); row 1792003124 (a pre-fold test made green); row 1792034245 (a HEAD read captured a sibling's commit).
    Mutants: drop any clause, let the amend ride "up to" the call again, or restore the HEAD-read capture."""
    design = _section("## Phase 2", "## Phase 3")
    assert "up to that call" not in design
    close = _section("## Phase 5", "## UPGRADE")
    # the subject comes from the -F message file (a pasted one would run its backticks); the grep finds a
    # candidate; the exact %s comparison refuses a body-quoting sibling, a prefix and a miss
    assert "trailers via -F <msg>," in close
    assert (
        '&& subj=$(head -n1 <msg>) && sha=$(git log -1 --format=%H -F --grep "$subj") && [ -n "$sha" ] \\'
        in close
    )
    assert (
        '&& [ "$(git log -1 --format=%s "$sha")" = "$subj" ] && echo "$sha" >> <durable>/commit.sha || exit 1'
    ) in close
    assert '"<your subject>"' not in close
    assert "rev-parse -q --verify HEAD" not in close
    assert (
        "with each hook output it grows sized against Claude Code's 10,000-character cap"
        " (https://code.claude.com/docs/en/hooks)"
    ) in _section("## Phase 1", "## Phase 2")


def test_measure_executes_the_incidents_sequel_both_geometries_prescribed_spellings_and_a_copied_mechanism() -> (
    None
):
    """Rows 1792361074, 1792363058, 1792365690, 1792401257: each design was sent back by its critiques for a case
    MEASURE never executed — what the reporter did next, a merge target that moved past the merge-base, a spelling
    another command prescribes, a copied guard on the live host — so MEASURE executes each before design.md is
    written, the grammar admits the recorded spellings, and the critiques run a copied mechanism."""
    assert (
        "a recipe's real target layout, the reported incident replayed on a copy one step past its symptom (what the"
        " reporter did next), a tool that scopes by a commit or diff range run where the branch's merge-base is its merge"
        " target's tip and where the target has moved past it, each spelling of a parsed input that the commands and docs"
        " feeding it prescribe, a mechanism copied from another script run read-only against the live state of each host"
        " it will run on (a side-effecting step on a copy),"
    ) in _section("## Phase 1", "## Phase 2")


def test_measure_runs_a_surfaced_outcome_twice() -> None:
    """Row 1792459184 (a recurrence of held replay-seat-recipe-twice): an outcome seen once was not traced to the
    line the operator reads."""
    assert "a surfaced outcome run twice and traced to the line the operator reads," in _section(
        "## Phase 1", "## Phase 2"
    )


def test_a_terminal_resting_on_another_partys_act_names_who_performs_it() -> None:
    """Row 1792612721, the second verdict on held what-do-terminal-names: a terminal naming a live effect on shared
    state (a port, a service, a deploy) said nothing about who triggers it. The rule lives in the run-record fragment,
    which 36 of the 39 commands that open a record include (the other three prescribe a terminal no third party
    acts on), and the terminal names the hand-off, since a close cannot wait for an act that comes after it."""
    live = re.sub(
        r"<!--.*?-->",
        "",
        (ROOT / "commands" / "_fragments" / "run-record.md").read_text(),
        flags=re.S,
    )
    frag = re.sub(r"\s+", " ", live)
    section = frag[frag.index("`--surface` is what makes") : frag.index("Close it EXACTLY ONE")]
    assert (
        "Where the outcome rests on an act this run does not perform (a deploy, a service restart, a port another"
        " process binds, a merge by its owner), the `--terminal` names the hand-off and who performs the act, and"
        " `--evidence` says whether they had acted at the close."
    ) in section
    src = re.sub(r"<!--.*?-->", "", SRC.read_text(), flags=re.S)
    assert src.index("{{include:run-record}}") < src.index("## SIZE")


def test_measure_runs_each_probe_under_an_interpreter_shown_to_import_it() -> None:
    """Rows 1792766698, 1792734746: an oracle probe imported the system python's markdown_it, which lacks linkify,
    and had to be re-pointed at the venv; most project venvs lack linkify too, so the import is shown, not assumed."""
    assert (
        "an independent parser for a parsed format (every probe run under an interpreter shown to import its"
        " libraries and each extra it enables: a system `python3` may lack one)"
    ) in _section("## Phase 1", "## Phase 2")

