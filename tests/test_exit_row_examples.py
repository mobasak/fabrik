"""W-cf9ec0cf — the exit-row examples the command corpus quotes are graded by the graders they teach.

WHY. `commands/_sources/fabrik-review.md`, `commands/_sources/fabrik-epics-review.md` and
`commands/_fragments/term-edit.md` each show a worked Pass Ledger: `| Pass N | … found: F, new: N, confirmed: C,
fixed: X, unexecuted: U | … |`. An agent copies those rows into a receipt, and two graders read the copy:
`check_review_coverage.py` parses the counters and `check_convergence.py` refuses a flip whose last Pass row does
not read `confirmed: 0`. Nothing checked the examples themselves, so a grader change, or an edit to an example,
could leave the corpus teaching a row shape the gate refuses, and nothing would go red until an agent's receipt
did. This test extracts every example table from the corpus and runs it through both graders.

Cheapest way to satisfy it without the outcome (D-253): delete the example tables. The floor below counts them, so
an emptied corpus reds the test instead of passing it vacuously.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_convergence  # noqa: E402
import check_review_coverage  # noqa: E402

_ROW = re.compile(r"^\| Pass \d+ \|")


def _example_tables() -> list[tuple[str, list[str]]]:
    """Every run of consecutive `| Pass N |` lines in the corpus sources and fragments, with its file."""
    out: list[tuple[str, list[str]]] = []
    for path in sorted(
        [*ROOT.glob("commands/_sources/*.md"), *ROOT.glob("commands/_fragments/*.md")]
    ):
        block: list[str] = []
        for line in [*path.read_text(encoding="utf-8").splitlines(), ""]:
            if _ROW.match(line):
                block.append(line)
            elif block:
                out.append((str(path.relative_to(ROOT)), block))
                block = []
    return out


TABLES = _example_tables()


def test_the_corpus_still_carries_its_exit_row_examples() -> None:
    files = {f for f, _ in TABLES}
    assert len(TABLES) >= 3, TABLES
    assert {
        "commands/_sources/fabrik-review.md",
        "commands/_sources/fabrik-epics-review.md",
        "commands/_fragments/term-edit.md",
    } <= files, files


@pytest.mark.parametrize(("path", "rows"), TABLES, ids=[f"{p}:{r[0][:12]}" for p, r in TABLES])
def test_every_example_row_parses_under_the_coverage_grader(path: str, rows: list[str]) -> None:
    block = "\n".join(rows)
    assert check_review_coverage._unparsed_pass_lines(block) == [], path
    for row in rows:
        parsed = check_review_coverage._pass_counters_ext(row)
        assert isinstance(parsed, tuple), (path, row, parsed)


@pytest.mark.parametrize(("path", "rows"), TABLES, ids=[f"{p}:{r[0][:12]}" for p, r in TABLES])
def test_each_example_table_closes_quiet_and_its_confirming_prefix_does_not(
    path: str, rows: list[str]
) -> None:
    assert check_convergence._closing_row_fail("\n".join(rows)) is None, path
    found, confirmed, fixed, unexecuted = check_review_coverage._pass_counters_ext(rows[-1])
    assert (confirmed, fixed, unexecuted or 0) == (0, 0, 0), (path, rows[-1])
    confirming = [r for r in rows[:-1] if (check_review_coverage._pass_counters_ext(r)[1] or 0) > 0]
    if confirming:
        prefix = rows[: rows.index(confirming[-1]) + 1]
        assert check_convergence._closing_row_fail("\n".join(prefix)) is not None, (
            path,
            prefix[-1],
        )
