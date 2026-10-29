"""Every reader that harvests backticked tokens reads a CommonMark code span, never a naive pair.

kaizen 01M5JTMSVY (W-f2e97f00): `_design_paths` paired single backticks, so one double-backtick
span (``a`b``) in a design's APPROACH shifted the pairing and every later path was misread — the
close then refused paths that WERE named. The same regex sat in three more readers; each case below
puts a double span before two paths, and the last test keeps the naive pattern from coming back.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SPAN_THEN_PATHS = "``a`b`` then `scripts/x.py` and `tests/test_x.py`"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_design_paths_read_past_a_double_backtick_span() -> None:
    cr = _load("cr_code_span", "scripts/command_run.py")
    got = cr._design_paths(f"APPROACH: {_SPAN_THEN_PATHS}.\nMIRROR: ```q``` breaks `docs/a.md`.\n")
    assert got == ["a`b", "scripts/x.py", "tests/test_x.py", "q", "docs/a.md"]


def test_doc_sync_tokens_read_past_a_double_backtick_span() -> None:
    cr = _load("cr_code_span_matrix", "scripts/command_run.py")
    text = "## Doc Sync Matrix\n| Change | Update |\n|---|---|\n| x | ``a`b`` + `docs/X.md` + `INDEX.md` |\n"
    assert {"docs/X.md", "INDEX.md"} <= cr._doc_sync_tokens(text)


def test_mail_cited_tokens_read_past_a_double_backtick_span() -> None:
    mail = _load("mail_code_span", "scripts/mail.py")
    toks = mail._cited_tokens(f"WHERE: {_SPAN_THEN_PATHS}")
    assert "scripts/x.py" in toks and "tests/test_x.py" in toks, toks


def test_review_coverage_changed_list_reads_past_a_double_backtick_span() -> None:
    crc = _load("crc_code_span", "scripts/enforcement/check_review_coverage.py")
    receipt = "# R\n**Changed:** ``a`b``, `x.py`, `y.py`\n\nHunt: `x.py`\n"
    gaps = crc._hunt_gaps(receipt)
    assert len(gaps) == 1 and "`y.py`" in gaps[0], gaps
    # the Hunt side reads a double span too: a row written ``y.py`` hunts y.py
    assert crc._hunt_gaps(receipt + "Hunt: ``y.py``\n") == []


def test_a_lone_backtick_run_stays_literal() -> None:
    """CommonMark: an opening run with no closing run of the SAME length is literal text, so the
    spans after it still pair."""
    cr = _load("cr_code_span_lone", "scripts/command_run.py")
    assert cr._design_paths("APPROACH: a `` b, `scripts/x.py` and `tests/y.py`\n") == [
        "scripts/x.py",
        "tests/y.py",
    ]


def test_no_reader_pairs_single_backticks_naively() -> None:
    """The class guard: `([^`]…)` between two single backticks is the pattern that unpairs on a
    double span. A reader of backticked tokens uses the run-length pattern instead."""
    naive = re.compile(r"""compile\(\s*r?["']`\(\[\^`""")
    hits = [
        f"{p.relative_to(_REPO)}:{n}"
        for root in ("scripts", ".claude/hooks")
        for p in sorted((_REPO / root).rglob("*.py"))
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if naive.search(line)
    ]
    assert hits == [], hits
