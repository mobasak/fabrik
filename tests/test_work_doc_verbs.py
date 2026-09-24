"""Doc <-> CLI verb parity for scripts/work.py (ticket T09).

Behavior Contract row 2 (T09-docs.md): every verb docs/reference/work-tracking.md names in its
``## The CLI`` table is a real ``work.py`` subcommand that runs ``--help`` cleanly, and every real
subcommand is named in the doc — neither side may drift from the other without this test catching it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
DOC = REPO / "docs" / "reference" / "work-tracking.md"

# One row of the doc's "## The CLI" table: a leading "| `<verb>" — the verb token itself, never the
# flags/args that may follow inside the same backtick-code cell (e.g. "`add --kind ...`").
_DOC_VERB_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z-]*)", re.M)


def _doc_verbs() -> set[str]:
    text = DOC.read_text(encoding="utf-8")
    section = re.search(r"^## The CLI\b.*?(?=^## |\Z)", text, re.M | re.S)
    assert section is not None, f"{DOC} has no '## The CLI' section"
    verbs = set(_DOC_VERB_ROW_RE.findall(section.group(0)))
    assert verbs, f"{DOC}'s '## The CLI' section named no verb — the row shape drifted"
    return verbs


def _script_verbs() -> set[str]:
    """The real subcommand set, from argparse's own subparsers action — never scraped from
    --help TEXT, which could be reworded without the parser itself changing."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    parser = work._parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("scripts/work.py's parser has no subparsers action")


def test_doc_names_every_real_verb_and_no_others() -> None:
    doc_verbs = _doc_verbs()
    script_verbs = _script_verbs()
    missing_from_doc = script_verbs - doc_verbs
    extra_in_doc = doc_verbs - script_verbs
    assert not missing_from_doc, f"work.py verbs the doc never names: {sorted(missing_from_doc)}"
    assert not extra_in_doc, f"doc names verbs work.py does not have: {sorted(extra_in_doc)}"


def test_every_doc_named_verb_help_runs_clean() -> None:
    for verb in sorted(_doc_verbs()):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), verb, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0, f"`work.py {verb} --help` failed:\n{proc.stderr}"
        assert proc.stdout.startswith("usage:"), f"`work.py {verb} --help` printed no usage line"
