"""W-7b5a6a17: the bounded-hop rule (D-230) counts a break a fix's own hunks created in a reader of what they changed.

A round-1 fix changed the path form `_range_files` returns and the commit leg that joined it against `_commit_files`
keys broke (W-42ddde8f); three review seats then read the rule both ways, and a review could close `confirmed: 0` on
a regression its own fix introduced. Each corpus home of the rule now counts that break, discriminated by the reader
passing on the previous round's pin and failing on this one. Cheapest bypass: a reviewer who relabels a pre-existing
caller defect as "the hunk broke it" — the two-pin run is what refutes that label, so a claim without it is RECORDED.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOMES = (
    "commands/_fragments/term-edit.md",
    "commands/_fragments/term-coverage.md",
    "commands/_agents/fabrik-reviewer.md",
)
CLAUSE = (
    "a live contradiction those hunks created with a sentence of the same section, or the break those hunks created"
    " in a reader of what they changed (such as a returned value or type, a key or path form, a field, a signature, a"
    " raised exception, an exit code, a printed line, or a heading or term another section cites), shown by that"
    " reader passing on the previous round's pin and failing on that pin with only those hunks applied, whatever line"
    " holds the defect; a defect one hop out that the hunks did not create"
)
# the exclusion still RECORDS (fragments) or never raises (seat file) what the hunks did not create
TAIL = {
    "commands/_fragments/term-edit.md": "a pre-existing claim — is RECORDED with a named destination",
    "commands/_fragments/term-coverage.md": "a pre-existing claim — is RECORDED with a named destination",
    "commands/_agents/fabrik-reviewer.md": "a pre-existing claim) is named in notes with a destination and never raised",
}


@pytest.mark.parametrize("rel", HOMES)
def test_each_home_counts_a_reader_the_hunk_broke(rel: str) -> None:
    text = re.sub(r"\s+", " ", (ROOT / rel).read_text(encoding="utf-8"))
    assert text.count(CLAUSE) == 1, rel
    after = text[text.index(CLAUSE) + len(CLAUSE) :]
    assert after.lstrip(" —(").startswith(
        "a caller, a callee, a neighbouring section, " + TAIL[rel]
    ), after[:200]
