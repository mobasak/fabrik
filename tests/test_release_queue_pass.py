"""/fabrik-release feedback queue answered in one pass (D-735, D-770).

Each test pins one sentence; the staleness test also reads docs_updater.py, so the "header, 90 days"
claim is the script's own constant and pattern.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-release.md"


def _flat() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def test_the_certification_precondition_leads_with_the_absence_case() -> None:
    """Row 1789489268."""
    text = _flat()
    head = text.index("## ⚠️ Precondition — no open certification handoffs")
    first = text[head : head + 400]
    assert "no file matching `docs/development/reviews/*-{user,service}-test-*.md` for this project is itself BLOCKED" in first
    assert "a `reviews/` directory holding other review types is not a certification report" in first
    assert text.count("No certification report at all") == 0


def test_the_docs_precondition_names_what_each_check_measures() -> None:
    """Rows 1789500677, 1789499509: the header and the 90 days are docs_updater.py's own."""
    text = _flat()
    assert "`docs_updater.py` reads the doc's own `**Last Updated:**` header (stale after 90 days)" in text
    assert "content is the tiebreak" in text
    assert "a date bump with no content change is never the fix" in text
    updater = (ROOT / "scripts" / "docs_updater.py").read_text()
    assert "STALENESS_DAYS = 90" in updater
    assert r"\*\*Last Updated:\*\*" in updater
