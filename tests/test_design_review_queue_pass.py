"""/design-review feedback queue answered in one pass (D-735, D-794)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "design-review.md"


def test_a_login_gated_screen_is_captured_by_an_env_reading_script() -> None:
    """Row 1790921613: the grounding gate's step (1), where the real screen is seen."""
    text = re.sub(r"\s+", " ", SRC.read_text())
    gate = text[text.index("GROUNDING GATE") : text.index("**(2) Check the frozen contracts**")]
    assert "a screen behind a login is captured by a script that signs in with credentials read from the environment (never pasted into a brief), and seats judge the captured screenshots" in gate
