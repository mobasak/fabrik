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


def test_a_mechanically_completed_skeleton_passes_the_coverage_grammar(repo: Path) -> None:
    out = repo / "r-review.md"
    assert _init(repo, "--out", str(out), "--changed", "app.py", "new.py").returncode == 0
    text = out.read_text(encoding="utf-8")
    done = text.replace("**Status:** IN-PROGRESS", "**Status:** CONVERGED")
    done = done.replace(
        "| UNCHECKED |",
        "| CLEAN (hunted app.py:1 and new.py:1 with their callers, nothing found) |",
    )
    done = done.replace(
        "### Phase 1 — <title>: UNCHECKED", "### Phase 1 — skeleton: CLEAN (app.py)"
    )
    done = done.replace(
        "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n",
        "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n"
        "| Pass 1 | pool qwen×3 + native opus×1 | found: 1, fixed: 1 | citation |\n"
        "| Pass 2 | pool qwen×3 + native opus×1 | found: 0, fixed: 0 | method: re-derivation |\n",
    )
    assert done != text
    out.write_text(done, encoding="utf-8")
    assert crc.check_file(out) == [], crc.check_file(out)


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
