"""/fabrik-mail-handle feedback queue answered in one pass (D-735, D-784).

The verdicts name the mail contract, so the rule lives beside the cooperative-ack rule in
docs/reference/fabrik-mail.md; the handle-now order the other row asks for is CLAUDE.md's.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def test_an_author_never_acks_its_own_send_to_a_shared_mailbox() -> None:
    """Row 1789470575."""
    text = _norm(ROOT / "docs" / "reference" / "fabrik-mail.md")
    assert "Nor is a message your session SENT to its own shared mailbox ever acked by you: the ack is the reader's act" in text


def test_the_handle_now_order_already_ends_reply_then_ack() -> None:
    """Row 1789467912 was rejected on this sentence."""
    assert "→ reply → `ack` → archived" in _norm(ROOT / "CLAUDE.md")
