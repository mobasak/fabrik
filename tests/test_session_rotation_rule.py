"""W-4c894cef — both contracts state D-1119's session-rotation rule in their "Session history" bullet.

WHY. The bullet told an agent to "run `/clear <agent>-<date>` now" when the transcript-size `ROTATE:` line appears.
D-1119 (operator, 2026-10-22) widens and corrects it: an agent may rotate at an item boundary, when the next work is
unrelated to the last, and D-1123 makes it due at 40% of the context window or the 200 MB ROTATE line, never
mid-item (a focused /compact at 85% mid-item instead); no agent can type a slash command into its own prompt, so a
builder asks its coordinator, who sends the keys over tmux.
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
            "at an item boundary, never mid-item — the item",
            "D-1119",
            "no run record `running`, no seat in flight, the worktree clean",
            "when the next work is unrelated to the last",
            "is due there once the context reaches 40% of the window",
            "or the transcript reaches the size at which the `ROTATE:` line prints",
            "no age or item-count trigger",
            "D-1123",
            "once per 100 MB step from `ROTATE_ADVISE_MB` (200 MB by default)",
            "never a command typed for you",
        ),
    )


@pytest.mark.parametrize("rel", CONTRACTS)
def test_both_contracts_route_the_rotation_through_the_coordinator(rel: str) -> None:
    _assert_all(
        rel,
        (
            "once a rotation is due, start no new item, so the item in hand closing is the boundary",
            "mid-item at 85% of the window, which the hook's `COMPACT-DUE` line reports, the coordinator sends a focused `/compact` instead",
            "`agents_up.sh rotate-session <name>` once infra's W-f975fee0 slice 2 lands",
            "messages its coordinator `rotate <name>` and waits for the keys",
            "a builder with no pane asks its coordinator the same way",
            "`STATE:` footer names the rotation and its `NEXT:` reads `none — terminal; awaiting the rotation`",
            "only when it is at its prompt with an empty input line, else aborts, never queues",
            "the `transcript_size_check.py` hook's `ROTATE-DUE` line says so",
            "`tmux send-keys`",
            "`@agent <name>`",
            "telling the builder to re-bind",
            "`work.py next`",
            "never the old transcript",
            "single-window repo's one agent, tells the operator once and starts no new item of its own",
            "(a coordinator keeps doing its standing jobs)",
        ),
    )
    assert "run `/clear <agent>-<date>` now" not in _bullet(rel), (
        "the old 'run it now' instruction survives"
    )
    for stale in ("once W-f975fee0 lands)", "W-f975fee0's sensor", "whatever its own"):
        assert stale not in _bullet(rel), f"{rel}: the shipped sensor is still described as future: {stale!r}"


@pytest.mark.parametrize("rel", CONTRACTS)
def test_the_rebind_command_survives(rel: str) -> None:
    _assert_all(rel, ("python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force",))
