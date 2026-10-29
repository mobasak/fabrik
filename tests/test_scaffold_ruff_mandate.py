"""The scaffold's ruff select carries the rule families core/10-python.md mandates (W-37b23d2d).

`.windsurf/rules/core/10-python.md` § Lint: "Ruff's selected rule-sets MUST include `ASYNC` (blocking
IO in async code), `B` (bugbear) and `S` (bandit) ... configured in `pyproject.toml`, emitted by the
scaffolder." Every scaffolded project's own ruff run (tests/test_scaffold_output_passes_gate.py)
then enforces them.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "scaffold"
    / "python"
    / "pyproject.toml.template"
)
MANDATED = ("ASYNC", "B", "S")


def test_the_scaffold_ruff_select_carries_every_pack_mandated_family():
    lint = tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]
    selected = set(lint.get("select", []) + lint.get("extend-select", []))
    missing = [f for f in MANDATED if f not in selected]
    assert not missing, (
        f"scaffold ruff select lacks the pack-mandated {missing} (core/10-python.md)"
    )
    # ignoring single codes (B008, S603, …) is deliberate narrowing; muting a WHOLE family is not
    muted = set(lint.get("ignore", []) + lint.get("extend-ignore", []))
    for table in ("per-file-ignores", "extend-per-file-ignores"):
        muted |= {c for codes in lint.get(table, {}).values() for c in codes}
    whole = [(f, m) for f in MANDATED for m in muted if _mutes_more_than_one_code(m, f)]
    assert not whole, f"a pack-mandated family is muted beyond single codes by an ignore: {whole}"


def _mutes_more_than_one_code(entry: str, family: str) -> bool:
    """True for "ALL", the family itself, or a digit sub-prefix of it (B0, ASYNC1); a full code
    (B008, ASYNC210) is single-code narrowing, and another linter's prefix (SIM105 vs S, A vs
    ASYNC) does not touch the family."""
    if entry in ("ALL", family):
        return True
    rest = entry[len(family) :] if entry.startswith(family) else ""
    return rest.isdigit() and len(rest) < 3
