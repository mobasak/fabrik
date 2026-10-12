"""/fabrik-upstream feedback queue answered in one pass (D-735, D-791).

The send line points at the message contract, and the seven keys it names are the contract table's own.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-upstream.md"
MAIL = ROOT / "docs" / "reference" / "fabrik-mail.md"


def test_the_send_line_names_the_message_contract_keys() -> None:
    """Row 1790965822."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    assert "a body with the message contract's WHAT, WHERE, WHEN, WHO, WHY, HOW and SYSTEMIC headers (`docs/reference/fabrik-mail.md` § The message contract)" in text
    contract = MAIL.read_text()
    keys = re.findall(r"^\| `([A-Z]+):` \|", contract[contract.index("## The message contract") :], flags=re.M)
    assert keys[:7] == ["WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC"]
