"""A command's rendered Pass-Ledger axis list (`PARAMS[cmd]["term-edit"]["AXES"]`) has one entry per
axis its own source defines (kaizen 01M4RXJYDW): /fabrik-flows-review listed seven of its eight
lettered axes, and nothing compared the renderer's constant with the source it describes.

Scope: the commands whose source defines its review axes as lettered bold headings (`**A) …`,
`**E2) …`, `**A0b) …`). A command without them states its axes elsewhere and is not graded here.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "ac_axes", REPO / "commands" / "assemble_commands.py"
)
assert _spec and _spec.loader
ac = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ac
_spec.loader.exec_module(ac)

_HEADING = re.compile(r"^\*\*([A-Z]\d?[a-z]?)\) ", re.M)


def _lettered(cmd: str) -> list[str]:
    src = REPO / "commands" / "_sources" / f"{cmd}.md"
    return _HEADING.findall(src.read_text(encoding="utf-8")) if src.is_file() else []


def test_the_axes_list_has_one_entry_per_lettered_axis() -> None:
    """A COUNT check: an axis added to or dropped from either side goes red. A renamed or
    reordered entry passes it — `test_the_flows_axes_are_pinned` holds those two exactly."""
    graded = 0
    for cmd, params in ac.PARAMS.items():
        axes = (params.get("term-edit") or {}).get("AXES")
        letters = _lettered(cmd)
        if not axes or len(letters) < 3:
            continue
        graded += 1
        named = [a.strip() for a in axes.split("·") if a.strip()]
        assert len(named) == len(letters), (cmd, letters, named)
    assert graded >= 3, f"only {graded} commands graded — the heading pattern no longer matches"


def test_flows_review_names_life_cycle_arcs_as_ui_only() -> None:
    """E2 applies to UI-bearing types only (`--units 7` otherwise), so the header says so."""
    axes = ac.PARAMS["fabrik-flows-review"]["term-edit"]["AXES"]
    assert "life-cycle arcs (UI types)" in axes


def test_the_flows_axes_are_pinned() -> None:
    """Exact strings for the two commands the 01M4RXJYDW fix touched: /fabrik-flows letters no
    headings (its axes are its Phase-6 gate), so only a pin guards it. Changing an axis in either
    source means changing this pin in the same commit."""
    assert ac.PARAMS["fabrik-flows-review"]["term-edit"]["AXES"] == (
        "tracing · personas · second actors · gap states · primary/resilience · "
        "life-cycle arcs (UI types) · discipline · cross-artifact"
    )
    assert ac.PARAMS["fabrik-flows"]["term-edit"]["AXES"] == (
        "criteria · personas · second actors · gap states · primary paths · resilience · "
        "contract inputs · i18n · exclusions · length · life-cycle arcs (UI types)"
    )
