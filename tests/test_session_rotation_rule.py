"""W-4c894cef — both contracts state D-1119's session-rotation rule in their "Session history" bullet.

WHY. The bullet told an agent to "run `/clear <agent>-<date>` now" when the transcript-size `ROTATE:` line appears.
D-1119 (operator, 2026-10-22) widens and corrects it: an agent may rotate at an item boundary, when the next work is
unrelated to the last ("when an agent will stop a new work irrelevant to previous one, it can use clear command"),
must rotate once the ROTATE line appears, and never mid-item; a builder in a pane cannot type `/clear` into itself,
so it asks its coordinator. The hub copy and the ~46-repo template copy must say the same thing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACTS = ("CLAUDE.md", "templates/governance/CLAUDE.md")


def _bullet(rel: str) -> str:
    """The `Session history (D-736)` bullet of one contract, whitespace collapsed."""
    text = (REPO / rel).read_text(encoding="utf-8")
    head = "- **Session history (D-736):**"
    assert text.count(head) == 1, f"{rel}: the Session history bullet is missing or doubled"
    tail = text.split(head, 1)[1]
    body = tail.split("\n- **", 1)[0]
    return " ".join(body.split())


@pytest.mark.parametrize("rel", CONTRACTS)
def test_both_contracts_allow_an_item_boundary_rotation(rel: str) -> None:
    bullet = _bullet(rel)
    assert "at an item boundary" in bullet, bullet
    assert "D-1119" in bullet, bullet
    assert "when an agent will stop a new work irrelevant to previous one, it can use clear command" in bullet


@pytest.mark.parametrize("rel", CONTRACTS)
def test_both_contracts_route_the_rotation_through_the_coordinator(rel: str) -> None:
    bullet = _bullet(rel)
    assert "never mid-item" in bullet, bullet
    assert "ask your coordinator to rotate you" in bullet, bullet
    assert "run `/clear <agent>-<date>` now" not in bullet, "the old 'run it now' instruction survives"


@pytest.mark.parametrize("rel", CONTRACTS)
def test_the_rebind_command_survives(rel: str) -> None:
    bullet = _bullet(rel)
    assert "python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force" in bullet, bullet
