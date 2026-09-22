"""D-335 § 5 item 7 — every command's opening executes the four things the goal names.

The `orient` fragment carries the four executed lines (MCPs · rules · infra · manifesto) and the
`ORIENT:` reply line; every command source includes it right after its run record opens, before
its first phase. Measured before this landed (2026-09-22): 0 / 9 / 7 / 0 of 38 sources named
`mcp_health.py` / `select_rules.py` / `agents-fabrik.md` / the operating manifesto.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / "commands" / "_sources"
FRAGMENT = REPO / "commands" / "_fragments" / "orient.md"

_START_RE = re.compile(r"\{\{include:run-record\}\}|command_run\.py start ")
_PHASE_RE = re.compile(r"^#{2,3} .*Phase [01]\b|step --phase 1\b", re.M)


def test_the_orient_fragment_names_the_four_executables_and_the_reply_line() -> None:
    body = FRAGMENT.read_text(encoding="utf-8")
    for needle in (
        "scripts/sysadmin/mcp_health.py",
        "scripts/select_rules.py",
        "agents-fabrik.md",
        "docs/reference/operating-manifesto.md",
        "ORIENT:",
    ):
        assert needle in body, needle


def test_every_command_source_includes_orient_between_its_start_and_its_first_phase() -> None:
    sources = sorted(SOURCES.glob("*.md"))
    assert len(sources) >= 30, len(sources)
    missing, misplaced = [], []
    for path in sources:
        text = path.read_text(encoding="utf-8")
        at = text.find("{{include:orient}}")
        if at < 0:
            missing.append(path.name)
            continue
        start = _START_RE.search(text)
        phase = _PHASE_RE.search(text)
        if start is None or start.start() > at or (phase is not None and phase.start() < at):
            misplaced.append(path.name)
    assert not missing, f"sources without {{{{include:orient}}}}: {missing}"
    assert not misplaced, f"orient included before the start or after phase 1: {misplaced}"
