"""Graders for ``task_lane.check_review_receipt`` — the close's review receipt (plan T03b; spec
§ The delta D1, checks (a)-(d)).

Every receipt here is a REAL one: written by ``scripts/review_receipt.py --init --range`` in a
throwaway git repo, mechanically completed the way ``tests/test_review_receipt.py`` completes it,
and graded by the real ``check_review_coverage.py`` shipped beside ``task_lane.py`` (never the
fixture repo's own copy — round-1 ruling O5/S1). One test per Behavior Contract row and per boundary; each
broken receipt differs from the valid one in ONE respect and must be refused with that check's
reason alone.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_review_receipt import _complete

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCRIPT = ROOT / "scripts" / "review_receipt.py"
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


def _swap_checker(monkeypatch, path: Path) -> None:
    """Point the (b) SUBPROCESS at ``path``; the Status reader keeps the real module, loaded
    first so its cache already holds it."""
    tl = _module()
    tl._crc()
    monkeypatch.setattr(tl, "_LOCAL_CHECKER", path)


def _unchecked(repo: Repo) -> None:
    broken = repo.text().replace(
        "| CLEAN (hunted app.py:1 and new.py:1 with their callers, nothing found) |",
        "| UNCHECKED |",
        1,
    )
    assert broken != repo.text()
    repo.write(broken)


def test_a_missing_checker_is_a_refusal_never_a_pass(
    repo: Repo, monkeypatch, tmp_path: Path
) -> None:
    _swap_checker(monkeypatch, tmp_path / "absent" / "check_review_coverage.py")
    _only(_check(repo, REL, [repo.last]), "b")


def test_a_checker_that_crashes_is_a_refusal(repo: Repo, monkeypatch, tmp_path: Path) -> None:
    stub = tmp_path / "check_review_coverage.py"
    stub.write_text("raise SystemExit(3)\n", encoding="utf-8")
    _swap_checker(monkeypatch, stub)
    _only(_check(repo, REL, [repo.last]), "b")


def test_a_checker_that_times_out_is_a_refusal(repo: Repo, monkeypatch, tmp_path: Path) -> None:
    """A hung checker (rc=None) refuses — it never reads as a pass (O2)."""
    stub = tmp_path / "check_review_coverage.py"
    stub.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    _swap_checker(monkeypatch, stub)
    monkeypatch.setattr(_module(), "_CHECKER_TIMEOUT", 1)
    reasons = _check(repo, REL, [repo.last])
    _only(reasons, "b")
    assert "rc=None" in reasons[0] and "TimeoutExpired" in reasons[0], reasons


def test_an_unlaunchable_checker_is_a_refusal(repo: Repo, monkeypatch) -> None:
    """The interpreter cannot be started (OSError, rc=None) — refused, never passed (O2)."""
    _module()._crc()
    monkeypatch.setattr(sys, "executable", "/nonexistent/python3")
    reasons = _check(repo, REL, [repo.last])
    _only(reasons, "b")
    assert "rc=None" in reasons[0], reasons


def test_the_repos_own_checker_copy_is_never_run(repo: Repo) -> None:
    """The lane run's commits can edit ``<root>/scripts/enforcement/check_review_coverage.py``;
    a stub there that always exits 0 must not pass an unadjudicated receipt (O5, S1)."""
    own = repo.root / "scripts" / "enforcement" / "check_review_coverage.py"
    own.parent.mkdir(parents=True)
    own.write_text("raise SystemExit(0)\n", encoding="utf-8")
    _unchecked(repo)
    _only(_check(repo, REL, [repo.last]), "b")


def test_the_callers_python_environment_cannot_change_the_verdict(
    repo: Repo, monkeypatch, tmp_path: Path
) -> None:
    """A PYTHONPATH sitecustomize that forces exit 0 must not reach the checker (O6)."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(
        "import atexit, os\natexit.register(lambda: os._exit(0))\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(site))
    _unchecked(repo)
    _only(_check(repo, REL, [repo.last]), "b")


def test_a_relative_root_is_resolved(repo: Repo, monkeypatch) -> None:
    """``root=Path('repo')`` from the parent directory: every half reads the same tree (O3)."""
    monkeypatch.chdir(repo.root.parent)
    tl = _module()
    assert tl.check_review_receipt(Path(REL), [repo.last], root=Path(repo.root.name)) == []


def _spy_checker_call(monkeypatch) -> list[tuple[list[str], dict]]:
    """Record the (b) subprocess's argv and kwargs, delegating to the real ``subprocess.run``."""
    tl = _module()
    real = subprocess.run
    calls: list[tuple[list[str], dict]] = []

    def spy(argv, *a, **kw):
        if str(tl._LOCAL_CHECKER) in [str(x) for x in argv]:
            calls.append(([str(x) for x in argv], kw))
        return real(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    return calls


def test_the_checker_runs_isolated_with_absolute_paths_and_a_scrubbed_env(
    repo: Repo, monkeypatch
) -> None:
    """O3 + O6: from a RELATIVE root the subprocess still gets an absolute ``--root``, receipt
    and cwd; it runs ``-I``; and its environment carries no ``PYTHON*`` (but
    ``PYTHONIOENCODING``) and no repository-moving git variable, with ``GIT_OPTIONAL_LOCKS=0``."""
    for k, v in {
        "PYTHONPATH": "/x",
        "PYTHONSAFEPATH": "",
        "PYTHONIOENCODING": "utf-8",
        "GIT_DIR": "/nowhere",
        "GIT_INDEX_FILE": "/nowhere/index",
    }.items():
        monkeypatch.setenv(k, v)
    calls = _spy_checker_call(monkeypatch)
    monkeypatch.chdir(repo.root.parent)
    tl = _module()
    assert tl.check_review_receipt(Path(REL), [repo.last], root=Path(repo.root.name)) == []
    assert len(calls) == 1, calls
    argv, kw = calls[0]
    assert argv[1] == "-I", argv
    root_arg = argv[argv.index("--root") + 1]
    assert root_arg == str(repo.root.resolve()), argv
    assert Path(argv[-1]) == (repo.root / REL).resolve(), argv
    assert Path(kw["cwd"]).is_absolute() and Path(kw["cwd"]) == repo.root.resolve(), kw
    env = kw["env"]
    assert not [k for k in env if k.startswith("PYTHON") and k != "PYTHONIOENCODING"], env
    assert env.get("PYTHONIOENCODING") == "utf-8"
    assert "GIT_DIR" not in env and "GIT_INDEX_FILE" not in env
    assert env.get("GIT_OPTIONAL_LOCKS") == "0"


def test_a_module_beside_the_checker_cannot_shadow_its_stdlib(
    repo: Repo, monkeypatch, tmp_path: Path
) -> None:
    """``-I`` keeps the script's own directory off ``sys.path``: an ``argparse.py`` planted next to
    the checker (forcing exit 0) is never imported, so an UNCHECKED receipt still refuses."""
    chk = tmp_path / "chk"
    chk.mkdir()
    real = Path(_module()._LOCAL_CHECKER)
    (chk / real.name).write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    (chk / "argparse.py").write_text("import os\nos._exit(0)\n", encoding="utf-8")
    _swap_checker(monkeypatch, chk / real.name)
    _unchecked(repo)
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
    """``CONVERGED … on the D-252 scope-growth stop`` is a closed Status. Since D-355 the receipt
    still closes on a confirmed-zero row, so the ledger stays quiet and only the wording is under
    test (kaizen 01M4CPWDK0)."""
    _status(repo, "**Status:** CONVERGED (2026-10-02) on the D-252 scope-growth stop")
    assert _check(repo, REL, [repo.last]) == []
    # the MIRROR: the same wording over a non-quiet last row no longer closes (D-355)
    text = repo.text().replace(
        "found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation |",
        "found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation |",
        1,
    )
    assert text != repo.text()
    repo.write(text)
    _only(_check(repo, REL, [repo.last]), "b")


def test_an_unloadable_status_reader_is_a_refusal(repo: Repo, monkeypatch, tmp_path: Path) -> None:
    """The header fields are read with the co-shipped checker's header-zone readers; if that
    module cannot load, (b)'s Status, (c) and (d) are each refused — never passed."""
    tl = _module()

    def _broken():
        raise ImportError("no reader")

    monkeypatch.setattr(tl, "_crc", _broken)
    reasons = _check(repo, REL, [repo.last])
    assert [r[:4] for r in reasons] == ["(b) ", "(c) ", "(d) "], reasons
    assert all("header cannot be read" in r for r in reasons), reasons


def test_a_negated_d252_wording_is_refused(repo: Repo) -> None:
    _status(repo, "**Status:** CONVERGED — this did not close on the D-252 scope-growth stop")
    _status_refused(_check(repo, REL, [repo.last]))


def test_a_second_in_progress_status_line_is_refused(repo: Repo) -> None:
    """``CONVERGED`` then ``IN-PROGRESS`` in the header: the checker exempts the whole grammar on
    the second line (exit 0 over an UNCHECKED row), so EVERY Status line must be closed (O1)."""
    _unchecked(repo)
    _status(repo, f"{STATUS}\n**Status:** IN-PROGRESS")
    reasons = _check(repo, REL, [repo.last])
    _status_refused(reasons)
    assert any("IN-PROGRESS" in r for r in reasons), reasons


@pytest.mark.parametrize(
    "line",
    [
        "**Status:** **CONVERGED**",
        "**Status**: CONVERGED",
        "**status:** converged",
        "Status: CONVERGED",
    ],
)
def test_the_bold_colon_and_case_forms_of_converged_pass(repo: Repo, line: str) -> None:
    """The Status reader normalises bold markers, the colon outside the bold, and case (O7)."""
    _status(repo, line)
    assert _check(repo, REL, [repo.last]) == []


@pytest.mark.parametrize(
    "value",
    ["CONVERGED-ish", "**CONVERGED**-ish", "CONVERGED/partial"],
)
def test_a_suffixed_converged_with_d252_wording_is_refused(repo: Repo, value: str) -> None:
    """``CONVERGED-ish`` / ``**CONVERGED**-ish`` / ``CONVERGED/partial`` ``… on the D-252
    scope-growth stop`` are not CONVERGED: a ``\\b`` match admits the hyphen, an end-only bold
    strip leaves ``CONVERGED**-ish``, and a negative look-ahead admits ``*`` and ``/`` (O7).
    The ledger stays quiet (D-355), so ONLY the Status half can refuse."""
    _status(repo, f"**Status:** {value} (2026-10-02) on the D-252 scope-growth stop")
    reasons = _check(repo, REL, [repo.last])
    _only(reasons, "b")
    _status_refused(reasons)


# ── (c)/(d) read the HEADER ZONE only (O4) ─────────────────────────────────────────────────


def test_a_blockquoted_scoped_command_is_not_rescued_by_a_body_line(repo: Repo) -> None:
    text = repo.text()
    line = next(ln for ln in text.splitlines() if ln.startswith("**Command:** "))
    scoped = "> " + line.replace("/fabrik-review ·", "/fabrik-review-scoped ·", 1)
    repo.write(text.replace(line, scoped, 1) + "\n**Command:** /fabrik-review\n")
    _only(_check(repo, REL, [repo.last]), "c")


def test_a_second_command_line_in_the_header_is_refused(repo: Repo) -> None:
    text = repo.text()
    line = next(ln for ln in text.splitlines() if ln.startswith("**Command:** "))
    repo.write(text.replace(line, f"{line}\n**Command:** /fabrik-review-scoped · x", 1))
    reasons = _check(repo, REL, [repo.last])
    assert any(r.startswith("(c) ") for r in reasons), reasons


def test_a_body_surface_line_does_not_carry_the_range_tip(repo: Repo) -> None:
    text = repo.text()
    line = next(ln for ln in text.splitlines() if ln.startswith("**Surface:**"))
    bare = line.replace(f"; range tip {repo.last}", "")
    repo.write(text.replace(line, bare, 1) + f"\n{line}\n")
    _only(_check(repo, REL, [repo.last]), "d")


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


def test_an_ancestor_listed_after_the_tip_passes(repo: Repo) -> None:
    """``first`` is inside ``seed..last``: listing it after the tip changes nothing — coverage is
    read from ancestry, never from the list's order (W-0b900e92)."""
    assert _check(repo, REL, [repo.last, repo.first]) == []


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
    """A range-form line with its tip cut is neither form check (d) reads — `git diff A..B` is not
    the working-tree `git diff HEAD` a receipt made without --range carries (W-ebbedc88)."""
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


# ── reasons accumulate (S2) and an ambiguous short SHA (S3) ────────────────────────────────


def test_a_missing_receipt_outside_reviews_keeps_its_a_reason(repo: Repo) -> None:
    reasons = _check(repo, "docs/development/outside-missing-review.md", [repo.last])
    assert any(r.startswith("(a) ") for r in reasons), reasons
    assert any("not a file" in r for r in reasons), reasons


def _ambiguous_prefix(repo: Repo) -> tuple[str, str, str]:
    """Make dangling commits on HEAD's tree until two share a 4+-hex prefix (bounded)."""
    tree = _git(repo.root, "rev-parse", "HEAD^{tree}")
    seen: dict[str, str] = {}
    for i in range(4000):
        sha = _git(repo.root, "commit-tree", tree, "-m", f"probe {i}")
        if sha[:4] in seen:
            other = seen[sha[:4]]
            n = 4
            while sha[: n + 1] == other[: n + 1]:
                n += 1
            return sha[:n], sha, other
        seen[sha[:4]] = sha
    pytest.fail("no 4-hex prefix collision in 4000 commits")


def test_an_ambiguous_short_sha_is_refused_never_guessed(repo: Repo) -> None:
    prefix, a, b = _ambiguous_prefix(repo)
    tl = _module()
    assert tl._resolve_commit(repo.root, prefix) is None
    assert tl._resolve_commit(repo.root, a) == a and tl._resolve_commit(repo.root, b) == b
    reasons = _check(repo, REL, [prefix])
    _only(reasons, "d")
    assert prefix in reasons[0] and "None" in reasons[0], reasons


# ── a receipt made WITHOUT --range: the working-tree Surface (W-ebbedc88) ─────────────────────


def _init_wt(r: Path, *changed: str) -> None:
    made = subprocess.run(
        [
            sys.executable,
            str(RECEIPT_SCRIPT),
            "--init",
            "--project-root",
            str(r),
            "--out",
            str(r / REL),
            "--changed",
            *changed,
        ],
        cwd=r,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert made.returncode == 0, made.stderr
    (r / REL).write_text(_complete((r / REL).read_text(encoding="utf-8")), encoding="utf-8")


def _restamp(r: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RECEIPT_SCRIPT), "--restamp", REL, "--project-root", str(r)],
        cwd=r,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _commit_all(r: Path, msg: str) -> str:
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", msg)
    return _git(r, "rev-parse", "HEAD")


@pytest.fixture
def wt(tmp_path: Path) -> Repo:
    """seed, then an uncommitted edit reviewed with ``--init`` (no --range); not yet committed."""
    r = tmp_path / "wt"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    seed = _git(r, "rev-parse", "HEAD")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")
    _init_wt(r, "app.py")
    return Repo(r, seed, seed, seed)


def _surface_line(repo: Repo) -> str:
    return next(ln for ln in repo.text().splitlines() if ln.startswith("**Surface:**"))


def test_a_working_tree_receipt_matching_its_commit_passes(wt: Repo) -> None:
    last = _commit_all(wt.root, "the reviewed change")
    assert _check(wt, REL, [last]) == []


def test_a_fix_after_the_receipt_is_refused_and_restamp_reanchors_it(wt: Repo) -> None:
    (wt.root / "app.py").write_text("x = 3\n", encoding="utf-8")  # a review fix after --init
    reasons = _check(wt, REL, [_commit_all(wt.root, "drifted")])
    assert len(reasons) == 1 and reasons[0].startswith("(d)")
    assert "is not the reviewed one" in reasons[0] and "--restamp" in reasons[0], reasons
    assert "range tip" not in reasons[0]
    # the same flow, re-anchored before the commit
    _git(wt.root, "reset", "-q", "--soft", "HEAD~1")
    (wt.root / "app.py").write_text("x = 4\n", encoding="utf-8")
    done = _restamp(wt.root)
    assert done.returncode == 0, done.stderr
    assert _check(wt, REL, [_commit_all(wt.root, "restamped")]) == []


def test_an_untracked_file_in_the_review_is_rebuilt_from_the_commit(tmp_path: Path) -> None:
    r = tmp_path / "u"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")
    (r / "new.py").write_text("y = 1\n", encoding="utf-8")
    _init_wt(r, "app.py", "new.py")
    repo = Repo(r, "", "", "")
    assert "+ 1 untracked file(s)" in _surface_line(repo)
    assert _check(repo, REL, [_commit_all(r, "with a new file")]) == []


def test_an_untracked_count_that_cannot_be_rebuilt_is_refused(tmp_path: Path) -> None:
    r = tmp_path / "u2"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    (r / "new.py").write_text("y = 1\n", encoding="utf-8")
    _init_wt(r, "new.py")
    repo = Repo(r, "", "", "")
    line = _surface_line(repo)
    repo.write(repo.text().replace(line, line.replace("+ 1 untracked", "+ 2 untracked"), 1))
    reasons = _check(repo, REL, [_commit_all(r, "new file")])
    assert len(reasons) == 1 and "cannot be rebuilt" in reasons[0], reasons


def test_an_unresolvable_surface_base_is_refused(wt: Repo) -> None:
    line = _surface_line(wt)
    head = line.split("= ", 1)[1].split(";", 1)[0]
    wt.write(wt.text().replace(line, line.replace(head, "0" * 40), 1))
    reasons = _check(wt, REL, [_commit_all(wt.root, "c")])
    assert len(reasons) == 1 and "does not resolve to a commit" in reasons[0], reasons


def test_a_receipt_anchored_to_an_empty_diff_is_refused(wt: Repo) -> None:
    last = _commit_all(wt.root, "c")
    line = _surface_line(wt)
    head = line.split("= ", 1)[1].split(";", 1)[0]
    empty = (
        line.replace(head, last).rsplit(" md5 ", 1)[0]
        + " md5 d41d8cd98f00b204e9800998ecf8427e (0 bytes)"
    )
    wt.write(wt.text().replace(line, empty, 1))
    reasons = _check(wt, REL, [last])
    assert len(reasons) == 1 and "is EMPTY" in reasons[0], reasons


def test_the_writer_and_the_reader_agree_on_the_working_tree_line(wt: Repo) -> None:
    """A change to `_surface`'s wording must red here, not silently refuse every close."""
    spec = importlib.util.spec_from_file_location("review_receipt_rt", RECEIPT_SCRIPT)
    assert spec and spec.loader
    rr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rr)
    body = _surface_line(wt).split("**Surface:** ", 1)[1]
    assert rr._WT_SURFACE.fullmatch(body) and _module()._WT_SURFACE.fullmatch(body)


def test_a_cited_design_path_names_its_file() -> None:
    norm = _module()._norm_cited
    for cited in (
        "scripts/x.py:340-373",
        "scripts/x.py::func",
        "scripts/x.py:12:5",
        "scripts/x.py:1,4-6",
        "./scripts/x.py:9",
    ):
        assert norm(cited) == "scripts/x.py", cited
    assert norm(":12") == ":12" and norm("a:b") == "a:b"


def _repo_seeded(tmp_path: Path, name: str) -> Path:
    r = tmp_path / name
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(r, "add", "app.py")
    _git(r, "commit", "-q", "-m", "seed")
    return r


def test_a_directory_token_with_new_files_is_rebuilt(tmp_path: Path) -> None:
    """Review A-S1: `--changed newdir` with untracked files inside it."""
    r = _repo_seeded(tmp_path, "dir")
    (r / "newdir").mkdir()
    (r / "newdir" / "b.txt").write_text("b\n", encoding="utf-8")
    (r / "newdir" / "a.txt").write_text("a\n", encoding="utf-8")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")
    _init_wt(r, "app.py", "newdir")
    repo = Repo(r, "", "", "")
    assert "+ 2 untracked file(s)" in _surface_line(repo)
    assert _check(repo, REL, [_commit_all(r, "dir")]) == []


def test_a_path_with_a_space_survives_the_round_trip(tmp_path: Path) -> None:
    """Review A-S3: the writer shell-quotes, the reader and --restamp shlex-split."""
    r = _repo_seeded(tmp_path, "sp")
    (r / "my file.py").write_text("y = 1\n", encoding="utf-8")
    _git(r, "add", "my file.py")
    _git(r, "commit", "-q", "-m", "add spaced")
    (r / "my file.py").write_text("y = 2\n", encoding="utf-8")
    (r / "new file.py").write_text("z = 1\n", encoding="utf-8")
    _init_wt(r, "my file.py", "new file.py")
    repo = Repo(r, "", "", "")
    assert "'my file.py'" in _surface_line(repo)
    (r / "my file.py").write_text("y = 3\n", encoding="utf-8")
    assert _restamp(r).returncode == 0
    assert _check(repo, REL, [_commit_all(r, "spaced")]) == []


def test_a_new_file_staged_before_the_review_still_matches(tmp_path: Path) -> None:
    r = _repo_seeded(tmp_path, "staged")
    (r / "new.py").write_text("n = 1\n", encoding="utf-8")
    _git(r, "add", "new.py")
    _init_wt(r, "new.py")
    repo = Repo(r, "", "", "")
    assert "untracked" not in _surface_line(repo)
    assert _check(repo, REL, [_commit_all(r, "staged")]) == []


def test_restamp_keeps_the_file_line_endings(tmp_path: Path) -> None:
    """Review: --restamp rewrites ONE line; a CRLF receipt stays CRLF everywhere else."""
    r = _repo_seeded(tmp_path, "crlf")
    (r / "app.py").write_text("x = 2\n", encoding="utf-8")
    _init_wt(r, "app.py")
    rec = r / REL
    rec.write_bytes(rec.read_bytes().replace(b"\n", b"\r\n"))
    before = rec.read_bytes().count(b"\r\n")
    (r / "app.py").write_text("x = 3\n", encoding="utf-8")
    assert _restamp(r).returncode == 0
    after = rec.read_bytes()
    assert after.count(b"\r\n") == before and b"\n" not in after.replace(b"\r\n", b"")


# ── (d) coverage is read from ancestry and touched paths, never --commit order (W-0b900e92) ──

_LEDGERS = {"CHANGELOG.md", "docs/DECISIONS.md"}


def _exempt(p: str) -> bool:
    return p in _LEDGERS or p.startswith("docs/development/reviews/")


def _commit_file(repo: Repo, rel: str, text: str, msg: str) -> str:
    repo.write(text, rel)
    _git(repo.root, "add", rel)
    _git(repo.root, "commit", "-q", "-m", msg)
    return _git(repo.root, "rev-parse", "HEAD")


def _check_x(repo: Repo, commits, exempt=_exempt) -> list[str]:
    return _module().check_review_receipt(Path(REL), list(commits), root=repo.root, exempt=exempt)


def test_exempt_commits_after_the_tip_pass_in_the_order_made(repo: Repo) -> None:
    """site-provisioner 01M4F5HTPS: the receipt and the ledger commits land after the reviewed
    tip and are listed in the order they were made."""
    rc = _commit_file(repo, REL, repo.text(), "receipt")
    lc = _commit_file(repo, "CHANGELOG.md", "## [Unreleased]\n", "ledger")
    assert _check_x(repo, [repo.first, repo.last, rc, lc]) == []


def test_a_later_code_commit_refuses_in_either_order(repo: Repo) -> None:
    """An unreviewed code commit after the tip refuses listed last AND listed before the tip —
    the reorder that used to pass."""
    late = _commit_file(repo, "app.py", "x = 4\n", "unreviewed fix")
    for commits in ([repo.last, late], [late, repo.last]):
        reasons = _check_x(repo, commits)
        _only(reasons, "d")
        assert late[:12] in reasons[0] and "app.py" in reasons[0], reasons


def test_without_an_exempt_rule_a_later_commit_refuses(repo: Repo) -> None:
    """No rule exempts nothing; a raising rule refuses (never escapes); one exempt path does not
    launder a code path in the same later commit."""
    lc = _commit_file(repo, "CHANGELOG.md", "## [Unreleased]\n", "ledger")
    _only(_check_x(repo, [repo.last, lc], exempt=None), "d")

    def boom(p: str) -> bool:
        raise RuntimeError(p)

    reasons = _check_x(repo, [repo.last, lc], exempt=boom)
    _only(reasons, "d")
    assert "RuntimeError" in reasons[0], reasons
    repo.write("## [Unreleased]\n- x\n", "CHANGELOG.md")
    repo.write("x = 5\n", "app.py")
    _git(repo.root, "add", "CHANGELOG.md", "app.py")
    _git(repo.root, "commit", "-q", "-m", "mixed")
    mixed = _git(repo.root, "rev-parse", "HEAD")
    _only(_check_x(repo, [repo.last, lc, mixed]), "d")


def test_a_later_merge_is_read_against_its_first_parent(repo: Repo) -> None:
    """A merge after the tip that brings in a code path refuses; its paths come from the first
    parent's diff (a merge read with no `-m` prints nothing and would pass vacuously)."""
    _git(repo.root, "checkout", "-q", "-b", "side", repo.seed)
    _commit_file(repo, "lib.py", "y = 1\n", "side work")
    _git(repo.root, "checkout", "-q", "-")
    _git(repo.root, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    merge = _git(repo.root, "rev-parse", "HEAD")
    reasons = _check_x(repo, [repo.last, merge])
    _only(reasons, "d")
    assert "lib.py" in reasons[0] and "app.py" not in reasons[0], reasons


def test_working_tree_form_is_order_independent(wt: Repo) -> None:
    """The anchor is the listed commit containing every other, never the list's last element:
    an unreviewed edit of the reviewed path refuses in both orders; sibling commits refuse."""
    tip = _commit_all(wt.root, "the reviewed change")
    (wt.root / "app.py").write_text("x = 9\n", encoding="utf-8")
    late = _commit_all(wt.root, "unreviewed edit")
    for commits in ([tip, late], [late, tip]):
        _only(_check_x(wt, commits), "d")
    sib = _git(wt.root, "commit-tree", f"{wt.seed}^{{tree}}", "-p", wt.seed, "-m", "sibling")
    reasons = _check_x(wt, [tip, sib])
    _only(reasons, "d")
    assert "contains every other" in reasons[0], reasons
