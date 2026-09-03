"""The script-coupling header check: `# AFTER-EDIT: <files | none>` — the sentinel form
CLAUDE.md § Pointers mandates — split into a phantom coupled file named `none` that could never
be staged, a permanently unclosable WARN on 28 of 128 headers (external-services review pass 45,
DU2)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_script_headers as csh  # noqa: E402


def _coupled(header: str) -> list[str]:
    listed = header.split(":", 1)[1].strip()
    if listed.lower() in csh.NONE_VALUES:
        return []
    return [c for c in csh.SEPARATORS.split(listed) if c and c.lower() not in csh.NONE_VALUES]


def test_the_none_sentinel_is_never_a_coupled_file():
    assert _coupled("# AFTER-EDIT: a.py | b.md | none") == ["a.py", "b.md"]
    assert _coupled("# AFTER-EDIT: none") == []
    assert _coupled("# AFTER-EDIT: a.py b.md c.sh") == ["a.py", "b.md", "c.sh"]


def test_the_shipped_tokeniser_drops_the_sentinel():
    src = (REPO / "scripts" / "enforcement" / "check_script_headers.py").read_text(encoding="utf-8")
    assert re.search(r"SEPARATORS\.split\(listed\)[\s\S]{0,160}not in NONE_VALUES", src), (
        "the sentinel filter must live on the split, not only on the whole header"
    )
