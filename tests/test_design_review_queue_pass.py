"""/design-review feedback queue answered in one pass (D-735, D-794)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "design-review.md"


def test_a_login_gated_screen_is_reached_through_the_auth_harness() -> None:
    """Row 1790921613: the grounding gate's step (1), where the real screen is seen."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    gate = text[text.index("GROUNDING GATE") : text.index("**(2) Check the frozen contracts**")]
    assert "a screen behind a login is reached through the vendored `fabrik-lib/ui-verify` auth harness" in gate
    assert "with credentials read from the environment, never pasted into a brief" in gate
    assert "the seat confirms the render is the signed-in screen, not a login redirect, before judging it" in gate
