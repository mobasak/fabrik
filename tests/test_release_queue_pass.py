"""/fabrik-release feedback queue answered in one pass (D-735, D-770).

The command-text pins moved to the rule ledger (`commands/_rules/fabrik-release.yaml`, D-1236); what stays is
the claim about the script, so the "header, 90 days" wording in the command is checked against `docs_updater.py`'s
own constant and list.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_docs_precondition_names_what_each_check_measures() -> None:
    """Rows 1789500677, 1789499509: the header and the 90 days are docs_updater.py's own."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import docs_updater

    assert docs_updater.STALENESS_DAYS == 90
    key_docs = ["docs/FEATURES.md", "docs/SERVICES.md", "docs/RESILIENCE.md", "docs/CONFIGURATION.md", "docs/DEPLOYMENT.md"]
    assert [d for d in key_docs if d in docs_updater.MANUAL_DOCS] == ["docs/CONFIGURATION.md"]
