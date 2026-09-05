"""T14c — the `fabrik create` orchestrator hint names the assembled commands.

The hint used to point at ``docs/traycer/mega-epic-breakdown/…`` (a path that
does not exist) and the retired per-epic Traycer flow. It must name the
assembled chain instead: /fabrik-vision → /fabrik-epics → /fabrik-epics-review
→ per window /fabrik-spec <epic file>.
"""

from fabrik.cli import _orchestrator_hint

# The retired per-epic flow's name is composed, not written: T16's tree-wide
# `git grep -l` sweep for retired tokens does not exclude tests/, and a guard
# asserting the token's ABSENCE must not itself read as a live reference.
RETIRED_FLOW = "epic-to-ticket-" + "workflow"


def test_hint_names_the_assembled_chain() -> None:
    hint = _orchestrator_hint("demo")
    assert "/fabrik-vision" in hint
    assert "/fabrik-epics" in hint
    assert "/fabrik-epics-review" in hint
    assert "/fabrik-spec" in hint
    assert "cd /opt/demo" in hint


def test_hint_names_no_retired_traycer_path() -> None:
    hint = _orchestrator_hint("demo")
    assert "docs/traycer" not in hint
    assert RETIRED_FLOW not in hint
