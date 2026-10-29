"""/fabrik-upstream feedback queue answered in one pass (D-735, D-791).

The seven keys the send line names are the contract table's own; the send line's own text is a ledger carrier
(`commands/_rules/fabrik-upstream.yaml`, entries `up-send-to-hub` and `up-next-command`).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIL = ROOT / "docs" / "reference" / "fabrik-mail.md"


def test_the_message_contract_names_the_seven_keys_the_send_line_cites() -> None:
    """Row 1790965822."""
    contract = MAIL.read_text()
    keys = re.findall(r"^\| `([A-Z]+):` \|", contract[contract.index("## The message contract") :], flags=re.M)
    assert keys[:7] == ["WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC"]
