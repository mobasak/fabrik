"""/fabrik-flows feedback queue answered in one pass (D-735, D-772).

The commit rule quotes check_doc_index.py's own error for an untracked doc; the test checks both
halves of that quote are the script's message strings.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-flows.md"


def test_the_draft_is_committed_at_first_write_with_its_index_rows() -> None:
    """Row 1790700641."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    assert "**COMMIT the artifact** at its first write, `DRAFT` included, with its `INDEX.md` and `docs/README.md` rows" in text
    assert "an untracked `docs/` file reds every gate run in that checkout" in text
    checker = (ROOT / "scripts" / "enforcement" / "check_doc_index.py").read_text()
    assert "live doc not in INDEX.md: " in checker
    assert "(untracked — the run that creates a doc owes its INDEX row)" in checker
