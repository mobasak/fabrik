"""Pins the headings `/fabrik-epics` walks in each planning pack to the packs themselves.

`/fabrik-epics` § the overlay-merge rule carries a table of `| <pack path> | <heading> |` rows and walks
that heading BY NAME in each loaded pack — "If the heading has moved, stop and report". The four
`00-domain-*` packs are `activation: manual`, so no glob check ever touches them; renaming the heading
during a currency pass would stop the command with no gate turning red.

This test reads the table from the command SOURCE (never a copy of it) and asserts each pack exists and
carries its heading as a whole line. The cheap way to satisfy it without the outcome is to delete a row
from the command's table; `test_every_domain_pack_is_in_the_table` closes that by requiring every
`00-domain-*.md` pack on disk to have a row.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "commands" / "_sources" / "fabrik-epics.md"
ROW = re.compile(r"^\|\s*`(\.windsurf/rules/[^`]+\.md)`\s*\|\s*`(#{2,4} [^`]+)`\s*\|\s*$", re.M)


def _rows() -> list[tuple[str, str]]:
    return ROW.findall(COMMAND.read_text(encoding="utf-8"))


def test_table_is_found() -> None:
    assert len(_rows()) >= 4, "the overlay-merge table in fabrik-epics.md moved or changed shape"


@pytest.mark.parametrize(("pack", "heading"), _rows())
def test_pack_carries_the_heading_the_command_walks(pack: str, heading: str) -> None:
    path = ROOT / pack
    assert path.is_file(), f"{pack} is named by /fabrik-epics but does not exist"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert heading in lines, f"{pack} no longer has the line {heading!r} that /fabrik-epics walks"


def test_every_domain_pack_is_in_the_table() -> None:
    named = {pack for pack, _ in _rows()}
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / ".windsurf" / "rules").rglob("00-domain-*.md")
    }
    assert on_disk <= named, f"domain packs with no /fabrik-epics row: {sorted(on_disk - named)}"
