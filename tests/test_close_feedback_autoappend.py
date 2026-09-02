"""The close-out feedback obligation must reach EVERY command, structurally.

Operator directive 2026-08-27: "for each command run, agents must give you feedback if they find
issues, or have suggestions about our commands and rules and infra, and send infra, intel or fleet a
message — they must be proactive."

The duty already existed in prose in BOTH constitutions (`templates/governance/CLAUDE.md` § Upstream
feedback for projects; `CLAUDE.md` § Behavior for the hub's three agents). Neither bound it to a
COMMAND RUN, which is the moment the machinery is actually being exercised and the only moment the
witness exists.

It is AUTO-APPENDED by the assembler rather than hand-included in 31 sources, because a hand-included
obligation is one a new command silently ships without — the exact shape of the run-record defect
(`docs/reference/command-corpus-check.md` predicate 5: the machinery was wired into 3 of 27 commands).
Auto-append makes "every command carries it" true by construction, so there is nothing to drift.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("asm", REPO / "commands" / "assemble_commands.py")
assert _spec and _spec.loader
asm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asm)

MARKER = "## ⚠️ Close-out feedback"


def _render() -> Path:
    tmp = Path(tempfile.mkdtemp())
    asm.render(tmp, tmp / "_skills")
    return tmp


def test_every_rendered_command_carries_the_feedback_obligation():
    out = _render()
    cmds = list(out.glob("*.md"))
    assert cmds, "render produced no commands — the harness is broken, not the assertion"
    missing = [p.name for p in cmds if MARKER not in p.read_text(encoding="utf-8")]
    assert not missing, f"{len(missing)} command(s) ship without the feedback obligation: {missing}"


def test_it_reaches_every_source_not_just_the_ones_that_opted_in():
    """The guarantee is STRUCTURAL. If this ever drops below the full source count, someone has made
    the obligation opt-in again."""
    out = _render()
    n_src = len(list((REPO / "commands" / "_sources").glob("*.md")))
    n_with = sum(1 for p in out.glob("*.md") if MARKER in p.read_text(encoding="utf-8"))
    assert n_with == n_src, f"{n_with} of {n_src} commands carry it"


def test_the_fragment_names_all_three_beats_so_routing_is_possible():
    body = (REPO / "commands" / "_fragments" / "close-feedback.md").read_text(encoding="utf-8")
    for beat in ("infra", "fleet", "intel"):
        assert f"**{beat}**" in body, f"{beat} has no row — an unroutable duty is not a duty"
    assert "mail.py send" in body, "must name the actual mechanism, not just the obligation"


def test_none_must_be_stated_rather_than_left_silent():
    """The session's recurring class: silence and 'I found nothing' are byte-identical, and only one
    of them is information. The fragment must demand the explicit verdict."""
    body = (REPO / "commands" / "_fragments" / "close-feedback.md").read_text(encoding="utf-8")
    assert "FEEDBACK:" in body, "no stated verdict line"
    # the fragment's wording of the same demand has moved twice (87c09d16 rewrote it 2026-09-01 and this
    # anchor went red at every baseline since); any of its three phrasings satisfies the intent
    flat = " ".join(body.split())  # the fragment wraps at ~100 cols; match the sentence, not the line
    assert (
        "never left as silence" in flat
        or "must be STATED" in flat
        or "it is a claim, and you are signing it" in flat
    )


def test_it_is_appended_once_not_duplicated():
    out = _render()
    for p in out.glob("*.md"):
        assert p.read_text(encoding="utf-8").count(MARKER) == 1, f"{p.name} carries it twice"
