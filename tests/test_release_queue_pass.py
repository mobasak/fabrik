"""/fabrik-release feedback queue answered in one pass (D-735, D-770).

Each test pins one sentence; the staleness test also reads docs_updater.py, so the "header, 90 days"
claim is the script's own constant and pattern.
"""

import re
import sys
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
    assert "No file matching `docs/development/reviews/*-{user,service}-test-*.md` for this project is itself BLOCKED" in first
    assert "every scaffold type owes one" in first
    assert "a `reviews/` directory holding other review types is not a certification report" in first
    assert text.count("No certification report at all") == 0


def test_the_docs_precondition_names_what_each_check_measures() -> None:
    """Rows 1789500677, 1789499509: the header and the 90 days are docs_updater.py's own."""
    text = _flat()
    assert "reads the `**Last Updated:**` header of only the docs in its `MANUAL_DOCS` list (of these key docs, `CONFIGURATION.md`)" in text
    assert "print `DOCS-TIEBREAK: <doc> — <shas> — <claims still true>` in the Gate-2 block" in text
    assert "never by a date bump alone" in text
    sys.path.insert(0, str(ROOT / "scripts"))
    import docs_updater

    assert docs_updater.STALENESS_DAYS == 90
    key_docs = ["docs/FEATURES.md", "docs/SERVICES.md", "docs/RESILIENCE.md", "docs/CONFIGURATION.md", "docs/DEPLOYMENT.md"]
    assert [d for d in key_docs if d in docs_updater.MANUAL_DOCS] == ["docs/CONFIGURATION.md"]
