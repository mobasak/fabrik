"""Behavior Contract for direct_vendor_parsers/anthropic.py Mythos whitelist.

Phase C of plan-4 (pipeline-health coverage closure).

The pre-Mythos guard `output <= input → skip` catches real parser bugs
(non-standard table layouts landing prices in the wrong cells) but was
never updated for Mythos-tier billing where a low output price for
cache-hit paths is documented. Whitelist those specific models.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _make_payload(model_name: str, prices: tuple[float, float, float, float, float]) -> str:
    """Build a minimal React-flight-chunk-shaped payload the parser will accept."""
    price_body = "".join(f' \\"$${p} / MTok\\" ' for p in prices)
    return (
        r'garbage_before '
        rf'\"children\":[\"{model_name}\"] more \"stuff\" '
        rf'{price_body}'
        r' tail_garbage'
    ).replace("\\", "\\")


def test_mythos_row_allowed_through():
    """B1: Mythos row with output < input emits a valid ParsedRow (not skipped)."""
    from direct_vendor_parsers.anthropic import extract

    payload = _make_payload("Claude Mythos 5", (7.5, 8.0, 8.0, 0.75, 1.5))
    rows = extract(payload, "https://docs.anthropic.com/pricing")
    slugs = [r.model_slug for r in rows]
    assert "Claude Mythos 5" in slugs, f"Mythos was skipped: {slugs}"


def test_non_mythos_still_skipped(capsys):
    """B2: unfamiliar model with output <= input still skipped + WARN.

    Uses "Claude Sonnet 9.9" — matches the parser's family anchor (Opus/
    Sonnet/Haiku/Fable/Mythos + version) but is NOT on the Mythos whitelist,
    so the safety net must still fire.
    """
    from direct_vendor_parsers.anthropic import extract

    payload = _make_payload("Claude Sonnet 9.9", (7.5, 8.0, 8.0, 0.75, 1.5))
    rows = extract(payload, "https://docs.anthropic.com/pricing")
    slugs = [r.model_slug for r in rows]
    assert "Claude Sonnet 9.9" not in slugs, f"safety net removed: {slugs}"
    captured = capsys.readouterr()
    assert "WARN" in captured.err and "Claude Sonnet 9.9" in captured.err


def test_mythos_case_and_whitespace_normalized():
    """B3: whitelist matches regardless of case + extra whitespace.

    Model name from the page could be `Claude Mythos Preview` (normal),
    `  claude   mythos   preview  ` (deviant); both should hit the whitelist.
    """
    from direct_vendor_parsers.anthropic import MYTHOS_OUTPUT_LESS_THAN_INPUT_OK, _model_key

    assert _model_key("Claude Mythos 5") in MYTHOS_OUTPUT_LESS_THAN_INPUT_OK
    assert _model_key("  claude   mythos   5  ") in MYTHOS_OUTPUT_LESS_THAN_INPUT_OK
    assert _model_key("CLAUDE MYTHOS PREVIEW") in MYTHOS_OUTPUT_LESS_THAN_INPUT_OK
    # Sanity: unrelated model does NOT hit the whitelist.
    assert _model_key("Claude Opus 4.8") not in MYTHOS_OUTPUT_LESS_THAN_INPUT_OK
