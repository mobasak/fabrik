"""W-4c894cef — both contracts state D-1119's session-rotation rule in their "Session history" bullet.

WHY. The bullet told an agent to "run `/clear <agent>-<date>` now" when the transcript-size `ROTATE:` line appears.
D-1119 (operator, 2026-10-22) widens and corrects it: an agent may rotate at an item boundary, when the next work is
unrelated to the last, must rotate at the latest at the first boundary after the ROTATE line, and never mid-item; no
agent can type a slash command into its own prompt, so a builder asks its coordinator, who sends the keys over tmux.
The hub copy and the ~46-repo template copy must say the same thing. Each phrase below is one clause a reader acts on;
dropping any of them from either contract turns its test red.
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


def _assert_all(rel: str, phrases: tuple[str, ...]) -> None:
    bullet = _bullet(rel)
    missing = [p for p in phrases if p not in bullet]
    assert not missing, f"{rel}: missing {missing}"


@pytest.mark.parametrize("rel", CONTRACTS)
def test_both_contracts_allow_an_item_boundary_rotation(rel: str) -> None:
    _assert_all(
        rel,
        (
            "at an item boundary, never mid-item",
            "D-1119",
            "no run record `running`",
            "when the next work is unrelated to the last",
            "must happen at the latest at the first boundary after the transcript-size `ROTATE:` line",
            "once per 100 MB step from `ROTATE_ADVISE_MB` (200 MB by default)",
            "never a command typed for you",
        ),
    )


@pytest.mark.parametrize("rel", CONTRACTS)
def test_both_contracts_route_the_rotation_through_the_coordinator(rel: str) -> None:
    _assert_all(
        rel,
        (
            "start no new item",
            "`handoff --command <run> --reason '<why>' --resume <artifact>`",
            "never `blocked --wall`",
            "messages its coordinator `rotate <name>` and waits for the keys",
            "`tmux send-keys`",
            "`@agent <name>`",
            "W-f975fee0",
            "telling the builder to re-bind",
            "`work.py next`",
            "never the old transcript",
            "single-window repo's one agent tells the operator once",
        ),
    )
    assert "run `/clear <agent>-<date>` now" not in _bullet(rel), "the old 'run it now' instruction survives"


@pytest.mark.parametrize("rel", CONTRACTS)
def test_the_rebind_command_survives(rel: str) -> None:
    _assert_all(rel, ("python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force",))
