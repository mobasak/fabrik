"""Behavior-Contract tests for scripts/review_receipt.py — the review-artifact skeleton.

The skeleton must be exactly the grammar check_review_coverage.py grades: an IN-PROGRESS file the
gate leaves alone ONLY because of its Status (the flip alone must fail it), whose mechanical
completion passes the gate with zero findings. Every test runs against a throwaway git repo
(the hub's rubric extractor is invoked against that root), so the surface is under the test's
control: one tracked modified file, one untracked new file.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts.enforcement import check_review_coverage as crc

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "review_receipt.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")  # tracked, modified
    (r / "new.py").write_text("y = 1\n", encoding="utf-8")  # untracked
    return r


def _init(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--init", "--project-root", str(repo), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_init_writes_an_in_progress_skeleton_that_only_its_status_exempts(repo: Path) -> None:
    out = repo / "r-review.md"
    r = _init(repo, "--out", str(out), "--changed", "app.py", "new.py", "--title", "Widget")
    assert r.returncode == 0, r.stderr
    text = out.read_text(encoding="utf-8")
    assert crc._in_progress(text), text[:300]
    assert crc.check_file(out) == []
    assert crc.RUBRIC_RUN.search(text), "the rubric's generated header must be pasted verbatim"
    assert crc.SURFACE.search(crc._strip_fences(text)), "Surface: hash line missing"
    section = crc._checklist_section(text)
    assert section is not None
    body = "\n".join(crc._table_rows(section))
    missing = [n for n, pat in crc.RECURRENCE.items() if not pat.search(body)]
    assert not missing, missing
    assert "Pass Ledger" in text and "Phase 1" in text
    # the exemption is the Status line and nothing else: flip it unfilled → the gate names the slots
    flipped = out.with_name("flipped-review.md")
    flipped.write_text(text.replace("**Status:** IN-PROGRESS", "**Status:** CONVERGED"), "utf-8")
    findings = crc.check_file(flipped)
    assert findings and any("UNCHECKED" in f for f in findings), findings


def _complete(text: str) -> str:
    """The MECHANICAL completion of a skeleton — ONE definition, shared by every test that needs
    a receipt the gate accepts, so a change to what "passing" means cannot drift between them."""
    done = text.replace("**Status:** IN-PROGRESS", "**Status:** CONVERGED")
    # ONE row takes a RECORDED verdict — the hygiene adjudication of D4/DD13. Before the D6
    # widening of `VERDICT` this row was a `noverdict` row and the completed skeleton failed;
    # the four RECORDED forms are verdicts, not missing ones.
    done = done.replace(
        "| UNCHECKED |",
        "| RECORDED — hygiene false positive (the `{{` sits inside a fenced example, "
        "scripts/review_receipt.py:170) |",
        1,
    )
    done = done.replace(
        "| UNCHECKED |",
        "| CLEAN (hunted app.py:1 and new.py:1 with their callers, nothing found) |",
    )
    done = done.replace(
        "### Phase 1 — <title>: UNCHECKED", "### Phase 1 — skeleton: CLEAN (app.py)"
    )
    # The D-206 closing row: `confirmed: 0` is the exit counter, the Finders cell names the seats
    # that read the fix diff (V11), and `unexecuted: 0` states that nothing was left unexecuted.
    done = done.replace(
        "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n",
        "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n"
        "| Pass 1 | native opus×1 + sonnet×2 | found: 1, new: 1, confirmed: 1, fixed: 1 "
        "| citation |\n"
        "| Pass 2 | native opus×1 + sonnet×2 | found: 0, new: 0, confirmed: 0, fixed: 0, "
        "unexecuted: 0 | method: re-derivation |\n",
    )
    assert done != text, "the completion changed nothing — the template's anchors moved"
    return done


def test_a_mechanically_completed_skeleton_passes_the_coverage_grammar(repo: Path) -> None:
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py", "new.py").returncode == 0
    text = out.read_text(encoding="utf-8")
    done = _complete(text)
    assert done != text
    out.write_text(done, encoding="utf-8")
    assert crc.check_file(out) == [], crc.check_file(out)
    # the closing row is read under the NEW grammar, not the legacy pair
    *_, ordered, refusals = crc._ledger_shapes(done)
    assert refusals == [], refusals
    assert ordered[-1][:4] == (0, 0, 0, 0), ordered[-1]


def test_init_writes_the_five_counter_row_shape_the_residual_section_and_the_verdicts(
    repo: Path,
) -> None:
    """The TEMPLATE's own text, read from `--init`'s output — not a row the test hand-builds.

    Round 1: every test in this file passed against the PRE-T02 template because each one
    constructed the ledger row itself, so the template could have shipped the old shape and no
    test would have known. These assertions read `render()`'s bytes.
    """
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py").returncode == 0
    text = out.read_text(encoding="utf-8")
    # LINE-JOINED and whitespace-normalised, never a line grep: the ledger prose wraps, and a
    # sentence that renders correctly but is split across a newline is exactly what a raw `in`
    # check misses (the spec names that trap for its own three D-191 wordings).
    joined = " ".join(text.split())
    # the five counters, in the spec's order, in the Pass Ledger prose AND in the fenced example
    assert "found: F, new: N, confirmed: C, fixed: X, unexecuted: U" in joined, text
    assert "found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0" in text, text
    # the four RECORDED verdict forms the widened `VERDICT` accepts
    for kind in ("unexecuted", "by design", "measured", "hygiene false positive"):
        assert f"RECORDED — {kind}" in text, kind
    # a `## Residual` section, and its example rows FENCED so the residual scan never reads the
    # template's own literal as a by-design row
    assert "\n## Residual\n" in text, text
    stripped = crc._strip_fences(text)
    assert "## Residual" in stripped
    assert not crc._BY_DESIGN.search(stripped), "the template's own example must be fenced"
    # and the skeleton still passes the gate it is written for
    assert crc.check_file(out) == []


def test_the_closing_row_must_name_its_finder_seats(repo: Path) -> None:
    """V11 end-to-end on a receipt that otherwise PASSES: the closing round names who read it."""
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py", "new.py").returncode == 0
    done = _complete(out.read_text(encoding="utf-8"))
    out.write_text(done, encoding="utf-8")
    assert crc.check_file(out) == []
    # the finders cell names no model token
    seatless = done.replace(
        "| Pass 2 | native opus×1 + sonnet×2 |", "| Pass 2 | the orchestrator |"
    )
    assert seatless != done
    out.write_text(seatless, encoding="utf-8")
    errs = crc.check_file(out)
    assert any("names no finder seat" in e for e in errs), errs
    # a CELL-ANCHORED closing row appended after the Pass rows has no finders cell at all — and
    # it must not bypass the check by being a row the Pass-head scan walks back past (round 1)
    appended = done.replace(
        "| method: re-derivation |\n",
        "| method: re-derivation |\n| 99 | found: 0 | confirmed: 0 | fixed: 0 |\n",
        1,
    )
    assert appended != done
    out.write_text(appended, encoding="utf-8")
    errs = crc.check_file(out)
    assert any("carries no `Pass N` head" in e for e in errs), errs


def test_v11_is_satisfiable_on_a_prose_ledger(repo: Path) -> None:
    """ROUND 2 — `_row_cells` returns [] for a prose row, so `len(cells) < 2` made V11 impossible
    to satisfy there: a prose closing row that NAMED its seats was refused for naming none. The
    prose ledger is a legal grammar, so its seats are read from the row text before the counters."""
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py", "new.py").returncode == 0
    done = _complete(out.read_text(encoding="utf-8"))
    table = (
        "| Pass 1 | native opus×1 + sonnet×2 | found: 1, new: 1, confirmed: 1, fixed: 1 "
        "| citation |\n"
        "| Pass 2 | native opus×1 + sonnet×2 | found: 0, new: 0, confirmed: 0, fixed: 0, "
        "unexecuted: 0 | method: re-derivation |\n"
    )
    assert table in done
    seated = done.replace(
        table,
        "\nPass 1 (native opus×1 + sonnet×2): found: 1, confirmed: 1, fixed: 1\n"
        "Pass 2 (native opus×1 + sonnet×2): found: 0, confirmed: 0, fixed: 0 — "
        "method: re-derivation\n\n",
        1,
    )
    out.write_text(seated, encoding="utf-8")
    assert crc.check_file(out) == [], crc.check_file(out)
    # and a prose closing row that names NO seat is still refused, in the prose row's own shape
    seatless = seated.replace(
        "Pass 2 (native opus×1 + sonnet×2): found: 0", "Pass 2 (the orchestrator): found: 0", 1
    )
    out.write_text(seatless, encoding="utf-8")
    errs = crc.check_file(out)
    assert any("names no finder seat before its counters" in e for e in errs), errs


def test_a_checklist_row_citing_a_line_is_told_the_citation_repair(repo: Path) -> None:
    """ROUND 2 — where the citation-idiom refusal CAN fire (a receipt with a checklist section),
    the message must name an edit the row's author can make."""
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py", "new.py").returncode == 0
    done = _complete(out.read_text(encoding="utf-8"))
    out.write_text(done, encoding="utf-8")
    assert crc.check_file(out) == []
    cited = done.replace(
        "| CLEAN (hunted app.py:1 and new.py:1 with their callers, nothing found) |",
        "| CLEAN (hunted app.py:1 and new.py:1; verifier confirmed :63; :47-53) |",
        1,
    )
    assert cited != done
    out.write_text(cited, encoding="utf-8")
    errs = crc.check_file(out)
    assert any("confirmed at :63" in e for e in errs), errs
    assert not any("between `new:` and `fixed:`" in e for e in errs), errs


def test_the_surface_anchor_covers_untracked_files(repo: Path) -> None:
    out = repo / "r-review.md"
    r = _init(repo, "--out", str(out), "--changed", "new.py")  # untracked only: git diff is empty
    assert r.returncode == 0, r.stderr
    line = next(ln for ln in out.read_text("utf-8").splitlines() if ln.startswith("**Surface:**"))
    assert "+ 1 untracked file(s)" in line and "(0 bytes)" not in line, line
    assert "d41d8cd98f00b204e9800998ecf8427e" not in line  # never md5("")


def test_init_refuses_an_empty_surface(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--", "app.py")  # app.py now clean; new.py untouched
    out = repo / "r-review.md"
    r = _init(repo, "--out", str(out), "--changed", "app.py")
    assert r.returncode == 1, (r.returncode, r.stderr)
    assert "EMPTY" in r.stderr
    assert not out.exists()


def test_init_refuses_to_overwrite_an_existing_artifact(repo: Path) -> None:
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py").returncode == 0
    before = out.read_bytes()
    r = _init(repo, "--out", str(out), "--changed", "app.py")
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert "exists" in r.stderr.lower()
    assert out.read_bytes() == before


def test_a_dated_scope_is_not_double_dated(repo: Path) -> None:
    r = _init(repo, "--scope", "2026-01-02-plan-3-widget", "--changed", "app.py")
    assert r.returncode == 0, r.stderr
    made = list((repo / "docs" / "development" / "reviews").glob("*-review.md"))
    assert [p.name for p in made] == ["2026-01-02-plan-3-widget-review.md"], made
    r2 = _init(repo, "--scope", "widget", "--changed", "app.py")
    assert r2.returncode == 0, r2.stderr
    names = sorted(p.name for p in (repo / "docs" / "development" / "reviews").glob("*-review.md"))
    assert (
        len(names) == 2 and names[-1].endswith("-widget-review.md") and names[-1].count("20") >= 1
    )


def test_the_rubric_guard_is_the_gates_own_pattern() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("rr", SCRIPT)
    rr = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(rr)
    assert rr.RUBRIC_RUN.pattern == crc.RUBRIC_RUN.pattern
    assert rr._RUBRIC_RUN_LITERAL.pattern == crc.RUBRIC_RUN.pattern  # the fallback twin, pinned


def test_a_range_surface_names_the_range_tip(repo: Path) -> None:
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-q", "-m", "second")
    out = repo / "r-review.md"
    r = _init(repo, "--out", str(out), "--changed", "app.py", "--range", "HEAD~1..HEAD")
    assert r.returncode == 0, r.stderr
    line = next(ln for ln in out.read_text("utf-8").splitlines() if ln.startswith("**Surface:**"))
    assert "range tip" in line and "git diff HEAD~1..HEAD" in line, line


def test_the_residual_grammar_example_sits_under_a_heading_that_says_example(repo: Path) -> None:
    """T2.15 (01M22VA3X): the quoted row-shape block is an EXAMPLE, never rows — a heading says so,
    so no reader (human or scan) takes the template's own sample rows for the receipt's residuals."""
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py").returncode == 0
    text = out.read_text(encoding="utf-8")
    assert text.count("### Verdict grammar — an EXAMPLE, never rows") == 1
    assert text.index("### Verdict grammar") < text.index("| F12 | RECORDED — unexecuted")
