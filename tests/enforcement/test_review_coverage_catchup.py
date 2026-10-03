"""Catch-up regressions for `check_review_coverage.py` — one guard per work item it closes.

Each test names the item it answers; the gate is loaded by path, the way every sibling suite
loads it, because `scripts/enforcement/` is not an importable package.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "enforcement" / "check_review_coverage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("crc_catchup", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crc = _load()


def test_docstring_does_not_advertise_the_retired_command_name_sniff(tmp_path: Path) -> None:
    """W-44f38118: the module docstring said a review naming `/fabrik-review` with NO Coverage
    Checklist fails; the sniff was retired at round 27 and `check_file` passes such a file. The
    docstring is the `--help` text, so it must describe the rule that actually runs."""
    f = tmp_path / "2026-10-03-x-review.md"
    f.write_text("# Review\n\nCommand: /fabrik-review\n\nSome findings.\n", encoding="utf-8")
    assert crc.check_file(f) == []  # the behaviour the docstring must agree with
    doc = " ".join((crc.__doc__ or "").split())
    assert "but has NO Coverage Checklist -> fail" not in doc, doc
    assert "retired" in doc.lower(), doc
