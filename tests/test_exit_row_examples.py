"""W-cf9ec0cf — the exit-row examples the command corpus quotes are graded by the graders they teach.

WHY. `commands/_sources/fabrik-review.md`, `commands/_sources/fabrik-epics-review.md` and
`commands/_fragments/term-edit.md` each show a worked Pass Ledger that an agent copies into a receipt. Two graders
read the copy: `check_review_coverage.py` (its `_ledger_shapes` extraction, refusals and the D-206 `_confirmed_quiet`
exit rule) and `check_convergence.py` (`_PASS_ROW`, `QUIET_PASS` and `_closing_row_fail`). Nothing checked the examples
themselves, so a grader change, or an edit to an example, could leave the corpus teaching a row shape the gate
refuses. This test finds every example table with the graders' own row pattern and grades it with their own rules.

Cheapest ways to satisfy it without the outcome (D-253), and their counters: delete the examples (the floor counts
tables and names the three files), or zero an example's history so no prefix is ever refused (every table must hold
a confirming row before its quiet close). Out of scope by design: a pipe-less prose ledger
(`fabrik-docs-review.md`'s `Pass 1 — …` rows), which `_PASS_ROW` cannot see; it belongs to that grader's owner.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_convergence as C  # noqa: E402, N812
import check_review_coverage as R  # noqa: E402, N812

_NUMBERED = re.compile(
    r"(?:Pass|Round)\s*\d", re.I
)  # a header row (`| Pass | seats |`) carries no number


def _example_tables() -> list[tuple[str, list[str]]]:
    """Runs of `_PASS_ROW` lines (blank lines between rows kept inside one run) in the corpus, with their file."""
    out: list[tuple[str, list[str]]] = []
    for path in sorted(
        [*ROOT.glob("commands/_sources/*.md"), *ROOT.glob("commands/_fragments/*.md")]
    ):
        block: list[str] = []
        for line in [*path.read_text(encoding="utf-8").splitlines(), "<end>"]:
            if C._PASS_ROW.match(line) and _NUMBERED.search(line):
                block.append(line.strip())
            elif block and not line.strip():
                continue
            elif block:
                out.append((str(path.relative_to(ROOT)), block))
                block = []
    return out


TABLES = _example_tables()
IDS = [f"{p}:{i}" for i, (p, _) in enumerate(TABLES)]


def _quiet(row: tuple) -> bool:
    q = R._confirmed_quiet(row)
    return q if q is not None else row[0] == 0  # legacy pair: the closing row's found: is 0


def test_the_corpus_still_carries_its_exit_row_examples() -> None:
    files = {f for f, _ in TABLES}
    assert len(TABLES) >= 3, TABLES
    assert {
        "commands/_sources/fabrik-review.md",
        "commands/_sources/fabrik-epics-review.md",
        "commands/_fragments/term-edit.md",
    } <= files, files


@pytest.mark.parametrize(("path", "rows"), TABLES, ids=IDS)
def test_each_example_table_is_read_whole_and_closes_quiet(path: str, rows: list[str]) -> None:
    _, _, ordered, refusals = R._ledger_shapes("\n".join(rows))
    assert refusals == [], (path, refusals)
    assert len(ordered) == len(rows), (path, rows, ordered)
    assert _quiet(ordered[-1]), (path, rows[-1])
    assert C.QUIET_PASS.search(rows[-1]), (path, rows[-1])
    assert C._closing_row_fail("\n".join(rows)) is None, path


@pytest.mark.parametrize(("path", "rows"), TABLES, ids=IDS)
def test_each_example_table_shows_a_refused_confirming_prefix(path: str, rows: list[str]) -> None:
    _, _, ordered, _ = R._ledger_shapes("\n".join(rows))
    confirming = [i for i, row in enumerate(ordered[:-1]) if not _quiet(row)]
    assert confirming, (
        path,
        "the example shows no round that confirmed a defect before its quiet close",
    )
    prefix = rows[: confirming[-1] + 1]
    assert C._closing_row_fail("\n".join(prefix)) is not None, (path, prefix[-1])
