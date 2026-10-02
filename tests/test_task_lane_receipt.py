"""Graders for ``task_lane.check_review_receipt`` — the close's review receipt (plan T03b; spec
§ The delta D1, checks (a)-(d)).

Every receipt here is a REAL one: written by ``scripts/review_receipt.py --init --range`` in a
throwaway git repo, mechanically completed the way ``tests/test_review_receipt.py`` completes it,
and graded by a copy of the real ``check_review_coverage.py`` placed where the function looks for
it (``<root>/scripts/enforcement/``). One test per Behavior Contract row and per boundary; each
broken receipt differs from the valid one in ONE respect and must be refused with that check's
reason alone.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_review_receipt import _complete

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCRIPT = ROOT / "scripts" / "review_receipt.py"
CHECKER = ROOT / "scripts" / "enforcement" / "check_review_coverage.py"
REL = "docs/development/reviews/2026-10-02-widget-review.md"


def _module():
    name = "task_lane"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "task_lane.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return r.stdout.strip()


class Repo:
    def __init__(self, root: Path, seed: str, first: str, last: str) -> None:
        self.root, self.seed, self.first, self.last = root, seed, first, last

    @property
    def receipt(self) -> Path:
        return self.root / REL

    def text(self) -> str:
        return self.receipt.read_text(encoding="utf-8")

    def write(self, text: str, rel: str = REL) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    """seed → first → last, and a COMPLETED receipt made with ``--range seed..last``."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    seed = _git(r, "rev-parse", "HEAD")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")
    _git(r, "commit", "-q", "-am", "first")
    first = _git(r, "rev-parse", "HEAD")
    (r / "app.py").write_text("x = 3\n", encoding="utf-8")
    _git(r, "commit", "-q", "-am", "last")
    last = _git(r, "rev-parse", "HEAD")
    (r / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy2(CHECKER, r / "scripts" / "enforcement" / "check_review_coverage.py")
    out = r / REL
    made = subprocess.run(
        [
            sys.executable,
            str(RECEIPT_SCRIPT),
            "--init",
            "--project-root",
            str(r),
            "--out",
            str(out),
            "--changed",
            "app.py",
            "--range",
            f"{seed}..{last}",
        ],
        cwd=r,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert made.returncode == 0, made.stderr
    out.write_text(_complete(out.read_text(encoding="utf-8")), encoding="utf-8")
    return Repo(r, seed, first, last)


def _check(repo: Repo, path, commits) -> list[str]:
    return _module().check_review_receipt(Path(path), list(commits), root=repo.root)


def _only(reasons: list[str], check: str) -> None:
    """Exactly one reason, and it is ``check``'s own (the reason opens with ``(<letter>)``)."""
    assert len(reasons) == 1, reasons
    assert reasons[0].startswith(f"({check}) "), reasons


# ── the valid receipt (the baseline every refusal below differs from in ONE respect) ────────


def test_a_valid_receipt_passes_all_four_checks(repo: Repo) -> None:
    assert _check(repo, REL, [repo.first, repo.last]) == []


def test_the_receipt_path_is_normalised_like_measure_close_normalises_it(repo: Repo) -> None:
    """``./`` and a doubled slash are spelled the way ``_norm_path`` spells them; an absolute
    path inside the root is the same receipt."""
    for spelled in (f"./{REL}", REL.replace("/reviews/", "//reviews/"), str(repo.receipt)):
        assert _check(repo, spelled, [repo.last]) == [], spelled


# ── (a) the path lies under docs/development/reviews/ ─────────────────────────────────────


def test_a_receipt_outside_the_reviews_dir_is_refused_by_check_a_alone(repo: Repo) -> None:
    moved = "docs/development/2026-10-02-widget-review.md"
    repo.write(repo.text(), moved)
    _only(_check(repo, moved, [repo.last]), "a")


def test_a_path_that_climbs_out_of_the_reviews_dir_is_refused(repo: Repo) -> None:
    """``docs/development/reviews/../x`` normalises to a path OUTSIDE the directory — a prefix
    test on the raw spelling would admit it."""
    moved = "docs/development/2026-10-02-widget-review.md"
    repo.write(repo.text(), moved)
    climbed = "docs/development/reviews/../2026-10-02-widget-review.md"
    _only(_check(repo, climbed, [repo.last]), "a")


def test_a_sibling_dir_sharing_the_prefix_is_refused(repo: Repo) -> None:
    """``docs/development/reviews-old/`` starts with the directory's NAME but is not under it."""
    moved = "docs/development/reviews-old/2026-10-02-widget-review.md"
    repo.write(repo.text(), moved)
    _only(_check(repo, moved, [repo.last]), "a")


def test_an_absolute_path_outside_the_root_is_refused(repo: Repo, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "docs" / "development" / "reviews" / "x-review.md"
    outside.parent.mkdir(parents=True)
    outside.write_text(repo.text(), encoding="utf-8")
    reasons = _check(repo, outside, [repo.last])
    assert reasons and reasons[0].startswith("(a) "), reasons


def test_a_missing_receipt_is_refused_with_one_reason(repo: Repo) -> None:
    reasons = _check(repo, "docs/development/reviews/absent-review.md", [repo.last])
    assert len(reasons) == 1 and "not a file" in reasons[0], reasons


# ── (b) check_review_coverage.py exits 0 (fail closed) ────────────────────────────────────


def test_a_receipt_failing_the_coverage_checker_is_refused_by_check_b_alone(repo: Repo) -> None:
    """CONVERGED with a checklist row still UNCHECKED — the checker exits non-zero."""
    broken = repo.text().replace(
        "| CLEAN (hunted app.py:1 and new.py:1 with their callers, nothing found) |",
        "| UNCHECKED |",
        1,
    )
    assert broken != repo.text()
    repo.write(broken)
    _only(_check(repo, REL, [repo.last]), "b")


def test_a_missing_checker_is_a_refusal_never_a_pass(repo: Repo) -> None:
    (repo.root / "scripts" / "enforcement" / "check_review_coverage.py").unlink()
    _only(_check(repo, REL, [repo.last]), "b")


def test_a_checker_that_crashes_is_a_refusal(repo: Repo) -> None:
    (repo.root / "scripts" / "enforcement" / "check_review_coverage.py").write_text(
        "raise SystemExit(3)\n", encoding="utf-8"
    )
    _only(_check(repo, REL, [repo.last]), "b")


# ── (b) the header Status is CLOSED — a review that has not finished is not a review ──────

STATUS = "**Status:** CONVERGED"


def _status(repo: Repo, new: str) -> None:
    text = repo.text()
    assert text.count(STATUS) == 1
    repo.write(text.replace(STATUS, new, 1))


def _status_refused(reasons: list[str]) -> None:
    assert any(r.startswith("(b) ") and "**Status:**" in r for r in reasons), reasons


def test_an_in_progress_receipt_is_refused_by_its_status_alone(repo: Repo) -> None:
    """The checker EXEMPTS ``IN-PROGRESS`` (exit 0) — an unfilled ``--init`` skeleton would
    otherwise discharge the close."""
    _status(repo, "**Status:** IN-PROGRESS")
    reasons = _check(repo, REL, [repo.last])
    _only(reasons, "b")
    _status_refused(reasons)
    assert "IN-PROGRESS" in reasons[0], reasons


def test_an_unfilled_init_skeleton_is_refused(repo: Repo) -> None:
    """The cheapest path end to end: ``--init --range`` and never review."""
    skeleton = repo.root / "docs/development/reviews/2026-10-02-skeleton-review.md"
    made = subprocess.run(
        [
            sys.executable,
            str(RECEIPT_SCRIPT),
            "--init",
            "--project-root",
            str(repo.root),
            "--out",
            str(skeleton),
            "--changed",
            "app.py",
            "--range",
            f"{repo.seed}..{repo.last}",
        ],
        cwd=repo.root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert made.returncode == 0, made.stderr
    _status_refused(_check(repo, skeleton, [repo.last]))


def test_a_blocked_receipt_is_refused_by_its_status(repo: Repo) -> None:
    _status(repo, "**Status:** BLOCKED")
    _status_refused(_check(repo, REL, [repo.last]))


def test_a_receipt_with_no_status_line_is_refused(repo: Repo) -> None:
    _status(repo, "")
    _status_refused(_check(repo, REL, [repo.last]))


def test_a_converged_status_with_trailing_words_is_refused(repo: Repo) -> None:
    """Only bare ``CONVERGED`` (or the D-252 wording) closes — a prefix test admits this."""
    _status(repo, "**Status:** CONVERGED-ish — pending the last round")
    _status_refused(_check(repo, REL, [repo.last]))


def test_a_status_below_the_header_zone_does_not_count(repo: Repo) -> None:
    """The header zone is the first 10 lines, as ``check_review_coverage._in_progress`` reads it:
    a body-deep ``**Status:** CONVERGED`` is prose, never the receipt's status."""
    _status(repo, "")
    repo.write(repo.text() + f"\n{STATUS}\n")
    _status_refused(_check(repo, REL, [repo.last]))


def test_the_d252_scope_growth_wording_is_a_closed_status(repo: Repo) -> None:
    """``CONVERGED … on the D-252 scope-growth stop`` is the third sanctioned exit; the checker's
    own ledger half (two rounds that each confirmed something) is built here so (b)'s subprocess
    passes too."""
    text = repo.text().replace(
        "found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation |",
        "found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation |",
        1,
    )
    assert text != repo.text()
    repo.write(text)
    _status(repo, "**Status:** CONVERGED (2026-10-02) on the D-252 scope-growth stop")
    assert _check(repo, REL, [repo.last]) == []


def test_an_unloadable_status_reader_is_a_refusal(repo: Repo, monkeypatch, tmp_path: Path) -> None:
    """The Status half reuses the co-shipped checker's header-zone readers; if that module
    cannot load, the status is unread and the receipt is refused — never passed."""
    tl = _module()
    monkeypatch.setattr(tl, "_LOCAL_CHECKER", tmp_path / "absent.py")
    monkeypatch.setattr(tl, "_crc_cache", [])
    reasons = _check(repo, REL, [repo.last])
    _only(reasons, "b")
    assert "Status cannot be read" in reasons[0], reasons


def test_a_negated_d252_wording_is_refused(repo: Repo) -> None:
    _status(repo, "**Status:** CONVERGED — this did not close on the D-252 scope-growth stop")
    _status_refused(_check(repo, REL, [repo.last]))


# ── (a) follows symlinks ───────────────────────────────────────────────────────────────────


def test_a_symlink_under_reviews_pointing_outside_is_refused_by_check_a(repo: Repo) -> None:
    outside = "docs/development/2026-10-02-widget-review.md"
    repo.write(repo.text(), outside)
    link = repo.root / "docs/development/reviews/2026-10-02-link-review.md"
    link.symlink_to(repo.root / outside)
    reasons = _check(repo, "docs/development/reviews/2026-10-02-link-review.md", [repo.last])
    assert reasons and reasons[0].startswith("(a) "), reasons


def test_a_symlink_resolving_into_reviews_passes_check_a(repo: Repo) -> None:
    link = repo.root / "docs/2026-10-02-alias-review.md"
    link.symlink_to(repo.receipt)
    assert _check(repo, "docs/2026-10-02-alias-review.md", [repo.last]) == []


# ── (c) the **Command:** token is exactly /fabrik-review ──────────────────────────────────


def test_a_scoped_review_receipt_is_refused_by_check_c_alone(repo: Repo) -> None:
    """``/fabrik-review-scoped`` STARTS WITH ``/fabrik-review`` — a prefix test admits it."""
    scoped = repo.text().replace(
        "**Command:** /fabrik-review · ", "**Command:** /fabrik-review-scoped · ", 1
    )
    assert scoped != repo.text()
    repo.write(scoped)
    _only(_check(repo, REL, [repo.last]), "c")


def test_a_receipt_with_no_command_line_is_refused_by_check_c(repo: Repo) -> None:
    stripped = repo.text().replace("**Command:** /fabrik-review · ", "", 1)
    assert stripped != repo.text()
    repo.write(stripped)
    _only(_check(repo, REL, [repo.last]), "c")


def test_a_command_token_with_trailing_text_is_refused(repo: Repo) -> None:
    """The token is the text up to the next `` · ``, compared whole — not a startswith."""
    other = repo.text().replace(
        "**Command:** /fabrik-review · ", "**Command:** /fabrik-review x · ", 1
    )
    repo.write(other)
    _only(_check(repo, REL, [repo.last]), "c")


# ── (d) the range tip resolves to the last --commit ───────────────────────────────────────


def test_a_range_tip_that_is_not_the_last_commit_is_refused_by_check_d_alone(repo: Repo) -> None:
    """The receipt ends at ``last``; the close's last ``--commit`` is ``first``."""
    _only(_check(repo, REL, [repo.seed, repo.first]), "d")


def test_the_last_commit_decides_not_any_commit(repo: Repo) -> None:
    """``last`` is listed, but not LAST — the receipt does not cover the final commit."""
    _only(_check(repo, REL, [repo.last, repo.first]), "d")


def test_a_short_sha_tip_of_the_last_commit_passes(repo: Repo) -> None:
    short = repo.text().replace(f"range tip {repo.last}", f"range tip {repo.last[:10]}", 1)
    assert short != repo.text()
    repo.write(short)
    assert _check(repo, REL, [repo.last]) == []


def test_a_short_sha_tip_of_an_earlier_commit_is_refused(repo: Repo) -> None:
    short = repo.text().replace(f"range tip {repo.last}", f"range tip {repo.first[:10]}", 1)
    assert short != repo.text()
    repo.write(short)
    _only(_check(repo, REL, [repo.last]), "d")


def test_a_short_last_commit_is_compared_in_full(repo: Repo) -> None:
    assert _check(repo, REL, [repo.last[:10]]) == []


def test_a_receipt_made_without_range_is_refused_by_check_d(repo: Repo) -> None:
    """No ``range tip`` on the Surface line: the receipt reviewed the working tree, not the run."""
    line = next(ln for ln in repo.text().splitlines() if ln.startswith("**Surface:**"))
    bare = line.replace(f"; range tip {repo.last}", "")
    assert bare != line
    repo.write(repo.text().replace(line, bare, 1))
    _only(_check(repo, REL, [repo.last]), "d")


def test_a_range_tip_outside_the_surface_line_does_not_count(repo: Repo) -> None:
    """Only the ``**Surface:**`` line carries the tip; a ``range tip`` quoted in the body is
    prose."""
    line = next(ln for ln in repo.text().splitlines() if ln.startswith("**Surface:**"))
    bare = line.replace(f"; range tip {repo.last}", "")
    text = repo.text().replace(line, bare, 1) + f"\nrange tip {repo.last}\n"
    repo.write(text)
    _only(_check(repo, REL, [repo.last]), "d")


def test_no_commit_is_refused_by_check_d(repo: Repo) -> None:
    _only(_check(repo, REL, []), "d")


def test_an_unresolvable_tip_or_commit_is_refused(repo: Repo) -> None:
    _only(_check(repo, REL, ["0" * 40]), "d")
    unknown = repo.text().replace(f"range tip {repo.last}", "range tip ?", 1)
    repo.write(unknown)
    _only(_check(repo, REL, [repo.last]), "d")


def test_check_d_writes_no_git_index(repo: Repo) -> None:
    """No ``.git/index`` write: the mtime and bytes survive the check (GIT_OPTIONAL_LOCKS=0)."""
    index = repo.root / ".git" / "index"
    os.utime(index, (1_000_000, 1_000_000))
    before = index.read_bytes()
    (repo.root / "app.py").touch()  # a stat-dirty file a refreshing command would re-stat
    assert _check(repo, REL, [repo.last]) == []
    assert index.stat().st_mtime == 1_000_000 and index.read_bytes() == before
