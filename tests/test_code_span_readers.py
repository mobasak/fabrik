"""The backticked-token readers read a same-line code span (N <= 8 backticks), never a naive pair.

kaizen 01M5JTMSVY (W-f2e97f00): `_design_paths` paired single backticks, so one double-backtick
span (``a`b``) in a design's APPROACH shifted the pairing and every later path was misread — the
close then refused paths that WERE named. The same regex sat in three more readers; each case below
puts a double span before two paths, and the last test keeps the naive pattern from coming back.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import time
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


def test_one_space_each_side_is_stripped() -> None:
    """CommonMark strips one space from each side of a span that carries one on both sides, so a
    path written `` scripts/x.py `` is the path, not the path with spaces."""
    cr = _load("cr_code_span_strip", "scripts/command_run.py")
    assert cr._design_paths("APPROACH: `` scripts/x.py `` and `` `y` ``\n") == [
        "scripts/x.py",
        "`y`",
    ]
    assert cr._code_spans("` ` and `  `") == [" ", "  "]  # all spaces: kept whole


def test_a_run_of_nine_stays_literal() -> None:
    cr = _load("cr_code_span_nine", "scripts/command_run.py")
    nine = "`" * 9
    assert cr._code_spans(f"{nine}a{nine} `x.py`") == ["x.py"]
    assert cr._code_spans(f"{'`' * 8}a{'`' * 8}") == ["a"]


def test_the_three_copies_are_one_pattern() -> None:
    """Each script loads standalone in a synced project, so the pattern is copied, never imported;
    the copies must not drift."""
    pats = {
        rel: _load(f"pat_{i}", rel)._CODE_SPAN.pattern
        for i, rel in enumerate(
            (
                "scripts/command_run.py",
                "scripts/mail.py",
                "scripts/enforcement/check_review_coverage.py",
            )
        )
    }
    assert len(set(pats.values())) == 1, pats


def test_an_unclosed_run_per_length_never_goes_quadratic() -> None:
    """Every run length from 1 to 800 opened once and never closed, on one 321 KB line: an uncapped
    run length rescanned the line once per length (2.98 s measured); the cap of 8 keeps it linear."""
    cr = _load("cr_code_span_cost", "scripts/command_run.py")
    line = "".join("`" * k + "a " for k in range(1, 801))
    t = time.perf_counter()
    cr._code_spans(line)
    assert time.perf_counter() - t < 0.5


# Pre-existing naive pairs, each a path and how many of its lines carry one. W-8183ecc2 decides per
# site whether it is a token reader to switch to `_CODE_SPAN`; a site fixed or added changes this set.
_KNOWN_NAIVE = {
    ".claude/hooks/final_gate_stop.py": 3,
    "scripts/doc_reconcile.py": 1,
    "scripts/enforcement/_fences.py": 2,
    "scripts/enforcement/check_traycer_chain.py": 1,
    "scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py": 1,
    "scripts/review_rubric.py": 1,
}


def test_no_new_reader_pairs_single_backticks_naively() -> None:
    """The class guard: a single backtick, an optional group (plain, `(?:` or `(?P<name>`), then a
    negated-backtick class — the shape that unpairs on a double span — in any line of any .py under
    scripts/ or .claude/hooks/ (archived trees excepted). A new site fails; a fixed one must leave
    `_KNOWN_NAIVE` too. A pattern split across lines or built by concatenation is not seen."""
    naive = re.compile(r"`(?:\((?:\?:|\?P<\w+>)?\s*)?\[\^`")
    hits: dict[str, int] = {}
    for root in ("scripts", ".claude/hooks"):
        for p in sorted((_REPO / root).rglob("*.py")):
            rel = p.relative_to(_REPO).as_posix()
            if not p.is_file() or "/archived/" in rel or "/.archive/" in rel:
                continue
            n = sum(
                1
                for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
                if naive.search(ln)
            )
            if n:
                hits[rel] = n
    assert hits == _KNOWN_NAIVE
