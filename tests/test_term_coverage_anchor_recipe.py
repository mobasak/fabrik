"""term-coverage obligation 1 recomputes a `review_receipt.py --init` Surface line with that script (W-e9588939).

The old recipe (`git rev-parse HEAD` + `git diff HEAD | md5sum`) hashes the WHOLE tree diff, while `--init`
hashes `git diff HEAD -- <paths>` plus each untracked path's bytes, so an unchanged surface never matched and a
re-invoked `/fabrik-review` always ran the full pass. The fragment now names `--restamp` on a scratch copy of the
prior receipt, compared by `cmp`. These tests read the recipe OUT of the fragment and run it through the real
script on a throwaway repo, so a reverted fragment fails them at extraction, and the script's behaviour is graded
on every row of the design's input table.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "commands" / "_fragments" / "term-coverage.md"
SCRIPT = ROOT / "scripts" / "review_receipt.py"

NEW_TEXT = (
    "Compute the surface hash the way the prior line was made. A line `review_receipt.py --init` wrote (it starts "
    "`` `git rev-parse HEAD` = <sha>; ``) is recomputed from the repo root by "
    "`python scripts/review_receipt.py --restamp <the copy>` on an absolute scratch copy of that receipt, never the "
    "receipt itself, whose anchor it would rewrite. It matches only when it exits 0, the copy is then "
    "byte-identical to the receipt (`cmp`), and the paths that line names are the paths this review is over, since "
    "it hashes those paths alone; any other result is a mismatch whatever remedy its message names (that remedy is "
    "for a receipt being written), and a `--range` line always exits 1. Any "
    "other line of a DIFF surface is compared with `git rev-parse HEAD` + `git diff HEAD | md5sum`; a non-diff "
    "surface keeps the inventory hash below."
)
OLD_SENTENCE = "Compute the surface hash: `git rev-parse HEAD` + `git diff HEAD | md5sum`."
SET_CLAUSE = (
    "the paths that line names are the paths this review is over, since it hashes those paths alone"
)
_RECIPE = re.compile(r"`python scripts/review_receipt\.py (--\w+) <the copy>`")


def _obligation_one() -> str:
    text = FRAGMENT.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("1. **Anchor:**"))
    return " ".join(line.split())


def _recipe_verb() -> str:
    m = _RECIPE.search(_obligation_one())
    assert m, "obligation 1 names no `python scripts/review_receipt.py --<verb> <the copy>` recipe"
    return m.group(1)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    for name in ("app.py", "other.py"):
        (r / name).write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py", "other.py")
    _git(r, "commit", "-q", "-m", "seed")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")  # tracked, modified
    (r / "new.py").write_text("y = 1\n", encoding="utf-8")  # untracked
    return r


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=repo, capture_output=True, text=True, timeout=120
    )


def _prior(repo: Path, tmp_path: Path, *extra: str) -> Path:
    out = tmp_path / "prior-review.md"
    r = _run(
        repo,
        "--init",
        "--project-root",
        str(repo),
        "--out",
        str(out),
        "--changed",
        "app.py",
        "new.py",
        *extra,
    )
    assert r.returncode == 0, r.stderr
    return out


def _anchor(
    repo: Path, prior: Path, tmp_path: Path
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """The recipe as the fragment names it: its verb, on an absolute copy in scratch, from the repo root."""
    copy = tmp_path / "scratch" / "anchor-copy.md"
    copy.parent.mkdir()
    copy.write_bytes(prior.read_bytes())
    return _run(repo, _recipe_verb(), str(copy)), copy


def test_obligation_one_carries_the_restamp_anchor_text_whole() -> None:
    para = _obligation_one()
    assert NEW_TEXT in para
    assert OLD_SENTENCE not in para
    assert para.index("read the NEWEST") < para.index(NEW_TEXT)
    assert para.index(NEW_TEXT) < para.index(
        "If it matches the prior report's recorded `Surface:` line"
    )


def test_the_named_recipe_matches_an_unchanged_surface_and_leaves_the_receipt_alone(
    repo: Path, tmp_path: Path
) -> None:
    prior = _prior(repo, tmp_path)
    before = prior.read_bytes()
    r, copy = _anchor(repo, prior, tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith(f"restamped {copy}: "), r.stdout  # the verb rewrote the copy
    assert copy.read_bytes() == before  # `cmp` of copy and receipt: a match
    assert prior.read_bytes() == before


def test_the_named_recipe_differs_after_an_edit(repo: Path, tmp_path: Path) -> None:
    prior = _prior(repo, tmp_path)
    (repo / "app.py").write_text("x = 3\n", encoding="utf-8")
    r, copy = _anchor(repo, prior, tmp_path)
    assert r.returncode == 0, r.stderr
    assert copy.read_bytes() != prior.read_bytes()


def test_the_named_recipe_refuses_a_range_line(repo: Path, tmp_path: Path) -> None:
    _git(repo, "add", "app.py", "new.py")
    _git(repo, "commit", "-q", "-m", "work")
    prior = _prior(repo, tmp_path, "--range", "HEAD~1..HEAD")
    r, copy = _anchor(repo, prior, tmp_path)
    assert r.returncode == 1
    assert "not the working-tree form" in r.stderr
    assert copy.read_bytes() == prior.read_bytes()


def test_the_named_recipe_exits_one_on_an_empty_surface(repo: Path, tmp_path: Path) -> None:
    prior = _prior(repo, tmp_path)
    before = prior.read_bytes()
    _git(repo, "checkout", "-q", "--", "app.py")
    (repo / "new.py").unlink()
    r, copy = _anchor(repo, prior, tmp_path)
    assert r.returncode == 1
    assert "the surface is EMPTY" in r.stderr
    assert copy.read_bytes() == before and prior.read_bytes() == before


def test_an_unnamed_path_matches_so_the_text_requires_the_path_set(
    repo: Path, tmp_path: Path
) -> None:
    prior = _prior(repo, tmp_path)
    (repo / "other.py").write_text(
        "x = 9\n", encoding="utf-8"
    )  # a path the prior line does not name
    r, copy = _anchor(repo, prior, tmp_path)
    assert r.returncode == 0, r.stderr
    assert copy.read_bytes() == prior.read_bytes()  # the script alone would call this a match
    assert SET_CLAUSE in _obligation_one()  # so the text adds the path-set condition
