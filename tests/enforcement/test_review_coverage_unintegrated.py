"""check_review_coverage grades review artifacts committed but not yet in an integration ref (W-f847a317, D-715).

Spec: docs/superpowers/specs/2026-10-08-review-coverage-commit-scope-design.md. Plan:
docs/development/plans/2026-10-08-plan-3-review-coverage-commit-scope.md (graders G1-G9, G11-G15). Every grader
builds a real git fixture — a bare `origin`, a main checkout, and where named a linked worktree — and runs the
checker as a subprocess with `--root`, so base resolution, the range log and the print path are all exercised.
The checker is loaded from THIS tree, never the main checkout's copy.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "enforcement" / "check_review_coverage.py"
RV = "docs/development/reviews"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("crc_unintegrated", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crc = _load()

_FAILING = (
    "# R\n**Status:** CONVERGED\n\n"
    "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
    "| 1 | fail-open/fail-closed | UNCHECKED | — |\n"
)
_IN_PROGRESS = (
    "# R\n**Status:** IN-PROGRESS\n\n"
    "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
    "| 1 | fail-open/fail-closed | UNCHECKED | — |\n"
)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _write(root: Path, name: str | bytes, text: str) -> Path:
    d = root / RV
    d.mkdir(parents=True, exist_ok=True)
    if isinstance(name, bytes):
        p = os.path.join(os.fsencode(d), name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return Path(os.fsdecode(p))
    p = d / name
    p.write_text(text, encoding="utf-8")
    return p


def _commit(root: Path, msg: str = "x") -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", msg)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _origin(tmp: Path, branch: str = "master") -> tuple[Path, Path]:
    """A bare origin and a main checkout on `branch`, one commit pushed with its upstream configured."""
    _git(tmp, "init", "-q", "--bare", "-b", branch, "origin.git")
    origin = tmp / "origin.git"
    _git(tmp, "clone", "-q", str(origin), "main")
    main = tmp / "main"
    (main / "README.md").write_text("base\n", encoding="utf-8")
    _commit(main, "base")
    _git(main, "push", "-q", "-u", "origin", branch)
    return origin, main


def _clone(tmp: Path, origin: Path, name: str) -> Path:
    _git(tmp, "clone", "-q", str(origin), name)
    return tmp / name


def _worktree(main: Path, tmp: Path, branch: str = "feat", start: str | None = None) -> Path:
    wt = tmp / f"wt-{branch}"
    _git(main, "worktree", "add", "-q", "-b", branch, str(wt), *([start] if start else []))
    return wt


# --- G1: committed-then-gated reds until integrated -------------------------------------------------------


def test_g1_an_unpushed_failing_review_blocks_until_it_is_integrated(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-g1-review.md", _FAILING)
    _commit(main)
    r = _run(main)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "2026-10-08-g1-review.md" in r.stdout, r.stdout
    _git(main, "push", "-q")
    r = _run(main)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAILED" not in r.stdout, r.stdout


# --- G2: the push-first cobra stays closed for a linked worktree -------------------------------------------


def test_g2_a_worktree_branch_pushed_to_its_own_remote_still_blocks(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    wt = _worktree(main, tmp_path)
    _write(wt, "2026-10-08-g2-review.md", _FAILING)
    _commit(wt)
    _git(wt, "push", "-q", "-u", "origin", "feat")
    r = _run(wt)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "2026-10-08-g2-review.md" in r.stdout, r.stdout


# --- G3: a catch-up merge of a remote that is ahead adds nothing --------------------------------------------


def test_g3_a_catch_up_merge_from_a_remote_ahead_adds_no_review(tmp_path: Path) -> None:
    origin, main = _origin(tmp_path)
    wt = _worktree(main, tmp_path)
    other = _clone(tmp_path, origin, "other")
    _write(other, "2026-10-08-other-review.md", _FAILING)
    _commit(other)
    _git(other, "push", "-q", "origin", "master")
    _git(wt, "fetch", "-q", "origin")
    _git(wt, "merge", "-q", "--no-edit", "origin/master")
    r = _run(wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2026-10-08-other-review.md" not in r.stdout, r.stdout
    assert "0 changed + 0 unintegrated" in r.stdout, r.stdout


def test_g3_the_configured_upstream_alone_excludes_a_remote_ahead_merge(tmp_path: Path) -> None:
    """No fallback ref exists in the I6 shape, so only B's configured upstream can exclude the merged
    commits — a lookup that silently drops it reds the worktree for another session's review."""
    origin, main = _origin(tmp_path, branch="mobasak/x")
    wt = _worktree(main, tmp_path)
    other = _clone(tmp_path, origin, "other")
    _write(other, "2026-10-08-other-review.md", _FAILING)
    _commit(other)
    _git(other, "push", "-q", "origin", "mobasak/x")
    _git(wt, "fetch", "-q", "origin")
    _git(wt, "merge", "-q", "--no-edit", "origin/mobasak/x")
    r = _run(wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2026-10-08-other-review.md" not in r.stdout, r.stdout
    assert "0 changed + 0 unintegrated" in r.stdout, r.stdout


# --- G4: a sibling's unpushed commit on the main checkout's branch is not the worktree's ---------------------


def test_g4_a_siblings_unpushed_commit_is_not_in_a_worktree_range(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-sib-review.md", _FAILING)
    _commit(main)
    wt = _worktree(main, tmp_path)  # cut AFTER the sibling's commit, so the branch contains it
    r = _run(wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2026-10-08-sib-review.md" not in r.stdout, r.stdout


# --- G5: no base, or a failing git log, degrades to today's scope with a NOTE --------------------------------


def test_g5_no_remote_keeps_todays_porcelain_scope(tmp_path: Path) -> None:
    root = tmp_path / "solo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _write(root, "2026-10-08-g5-review.md", _FAILING)
    _commit(root)
    r = _run(root)
    assert r.returncode == 0, r.stdout + r.stderr
    # no base is today's behaviour exactly: no scan, and no NOTE (spec § The delta 2)
    assert "NOTE" not in r.stdout and "0 changed + 0 unintegrated" in r.stdout, r.stdout


def test_g5_a_repo_with_no_commits_never_tracebacks(tmp_path: Path) -> None:
    origin, _ = _origin(tmp_path)
    root = tmp_path / "unborn"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "fetch", "-q", "origin")
    r = _run(root)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stdout + r.stderr


def test_g5_a_base_that_looks_like_an_option_is_refused(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-g5c-review.md", _FAILING)
    _commit(main)
    for bad in ("--all", "-x", ""):
        r = _run(main, f"--base={bad}")
        assert r.returncode == 2, (bad, r.stdout + r.stderr)


def test_g5_an_unresolvable_base_is_a_note_never_a_traceback(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-g5b-review.md", _FAILING)
    _commit(main)
    r = _run(main, "--base", "nosuchref")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOTE: unintegrated review scan skipped" in r.stdout, r.stdout
    assert "Traceback" not in r.stderr, r.stderr


def test_g5_a_review_removed_after_the_log_listed_it_never_tracebacks(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A path listed as changed or unintegrated but gone by the time it is read (a sibling checkout mid-run)
    is skipped and not counted — never a traceback from the IN-PROGRESS read or the grader."""
    _, main = _origin(tmp_path)
    gone = main / RV / "2026-10-08-gone-review.md"
    gone2 = main / RV / "2026-10-08-gone2-review.md"
    monkeypatch.setattr(crc, "_unintegrated_md", lambda root, prefix, bases: ([gone], {}, []))
    monkeypatch.setattr(crc, "_changed_md", lambda root, prefix: ([gone2], [], []))
    monkeypatch.setattr(sys, "argv", ["check_review_coverage.py", "--root", str(main)])
    assert crc.main() == 0
    assert "0 changed + 0 unintegrated" in capsys.readouterr().out


def test_g5_grading_a_vanished_review_is_a_failure_line_never_a_traceback(tmp_path: Path) -> None:
    """The race left after the listing filter (gone between the filter and the read) fails closed."""
    errs = crc._grade(tmp_path / RV / "2026-10-08-gone-review.md", tmp_path)
    assert len(errs) == 1 and "unreadable while being graded" in errs[0], errs


# --- G6: an unintegrated IN-PROGRESS receipt passes and is reported once -------------------------------------


def test_g6_an_in_progress_receipt_is_reported_exactly_once(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-g6-review.md", _IN_PROGRESS)
    _commit(main)
    r = _run(main)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("2026-10-08-g6-review.md") == 1, r.stdout


# --- G7: names git would quote are graded, renames grade the destination, odd bytes never raise --------------


def test_g7_a_non_ascii_name_is_graded_staged_and_unintegrated(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-ü-review.md", _FAILING)
    _git(main, "add", "-A")
    r = _run(main)
    assert r.returncode == 1 and "2026-10-08-ü-review.md" in r.stdout, r.stdout + r.stderr
    _git(main, "commit", "-qm", "x")
    r = _run(main)
    assert r.returncode == 1 and "2026-10-08-ü-review.md" in r.stdout, r.stdout + r.stderr


def test_g7_a_staged_rename_grades_the_destination_only(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "a.md", _FAILING)
    _commit(main)
    _git(main, "push", "-q")
    _git(main, "mv", f"{RV}/a.md", f"{RV}/b.md")
    r = _run(main)
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"{RV}/b.md" in r.stdout and f"{RV}/a.md" not in r.stdout, r.stdout


def test_g7_a_non_utf8_name_is_printed_escaped_on_every_path(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    p = _write(main, b"2026-10-08-\xff-review.md", _FAILING)
    _git(main, "add", "-A")
    r = _run(main)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "\\xff" in r.stdout and "Traceback" not in r.stderr, r.stdout + r.stderr
    r = _run(main, str(p))
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stdout + r.stderr


def test_g7_an_intent_to_add_peer_receipt_is_named_with_any_name(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-ü-review.md", _FAILING)
    _write(main, b"2026-10-08-\xff-review.md", _FAILING)
    _git(main, "add", "-N", RV)
    r = _run(main)
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stdout + r.stderr
    notes = [ln for ln in r.stdout.splitlines() if "is intent-to-add" in ln]
    assert any("2026-10-08-ü-review.md" in ln for ln in notes), r.stdout
    assert any("\\xff" in ln for ln in notes), r.stdout


# --- G8: a committed mega report is graded live=False --------------------------------------------------------


def _mega(h: str) -> str:
    return (
        "# Cross-Epic Validation Report\n"
        f"Surface: {h}\n\n"
        "Rounds:\n"
        "| round | found: | fixed: | md5(start) → md5(end) |\n"
        "|---|---|---|---|\n"
        f"| 1 | found: 7 | fixed: 6 | {'a' * 32} → {h} |\n"
        f"| 2 | found: 0 | fixed: 0 | {h} → {h} |\n"
        "\n## Feature Coverage: PASS — 12 features across 2 epics\n"
        "## Overall: PASS · Fixups this run: 6 · Routed back: none\n"
    )


def test_g8_an_unintegrated_mega_report_is_not_rehashed_against_moved_epics(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    epics = main / "docs/development/epics"
    epics.mkdir(parents=True)
    (epics / "2026-10-08-epic-1-a.md").write_text("# E1\n", encoding="utf-8")
    _commit(main)
    _git(main, "push", "-q")
    h = crc.epics_set_hash(main)
    assert h
    name = "2026-10-08-mega-vision-validation-review.md"
    _write(main, name, _mega(h))
    _git(main, "add", "-A")
    (epics / "2026-10-08-epic-1-a.md").write_text("# E1 moved\n", encoding="utf-8")
    r = _run(main)
    assert r.returncode == 1, (
        "uncommitted: today's live grading must red a moved epic set\n" + r.stdout
    )
    _commit(main)
    r = _run(main)
    assert r.returncode == 0, r.stdout + r.stderr


# --- G9: attribution and the two-source denominator ----------------------------------------------------------


def test_g9_a_failure_names_the_commit_and_its_agent(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-g9a-review.md", _FAILING)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "x\n\nAgent-Role: primary\nAgent-Name: intel")
    _write(main, "2026-10-08-g9b-review.md", _FAILING)
    _commit(main)
    r = _run(main)
    assert r.returncode == 1, r.stdout + r.stderr
    assert re.search(r"g9a-review\.md entered history in [0-9a-f]{7,} \(intel\)", r.stdout), (
        r.stdout
    )
    assert re.search(r"g9b-review\.md entered history in [0-9a-f]{7,} \(t\)", r.stdout), r.stdout
    assert "never push to clear it" in r.stdout, r.stdout


def test_g9_attribution_names_the_author_who_added_it_not_a_later_editor(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    p = _write(main, "2026-10-08-g9d-review.md", _FAILING)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "add\n\nAgent-Name: alice")
    p.write_text(_FAILING + "\nedited\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "edit\n\nAgent-Name: bob\nAgent-Name: carol")
    r = _run(main)
    assert re.search(r"g9d-review\.md entered history in [0-9a-f]{7,} \(alice\)", r.stdout), (
        r.stdout
    )
    # an edit-only review names its newest editor, all trailers on ONE line
    _git(main, "push", "-q")
    p.write_text(_FAILING + "\nedited again\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "edit2\n\nAgent-Name: bob\nAgent-Name: carol")
    r = _run(main)
    assert re.search(r"g9d-review\.md was changed in [0-9a-f]{7,} \(bob, carol\)", r.stdout), (
        r.stdout
    )


def test_g9_attribution_survives_renames_globs_and_re_adds(tmp_path: Path) -> None:
    """A rename is an edit (the renamer 'changed' it), a glob character matches only its own file, and
    an add-delete-re-add names the author of the file now on disk."""
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-orig-review.md", _FAILING)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "a\n\nAgent-Name: alice")
    _git(main, "push", "-q")
    _git(main, "mv", f"{RV}/2026-10-08-orig-review.md", f"{RV}/2026-10-08-moved-review.md")
    _git(main, "commit", "-qm", "mv\n\nAgent-Name: bob")
    _write(main, "2026-10-08-[x]-review.md", _FAILING)
    _write(main, "2026-10-08-x-review.md", _FAILING)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "g\n\nAgent-Name: carol")
    _write(main, "2026-10-08-x-review.md", _FAILING + "\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "x\n\nAgent-Name: dave")
    p = _write(main, "2026-10-08-re-review.md", _FAILING)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "r1\n\nAgent-Name: erin")
    p.unlink()
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "rm\n\nAgent-Name: erin")
    _write(main, "2026-10-08-re-review.md", _FAILING)
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "r2\n\nAgent-Name: frank")
    r = _run(main)
    assert re.search(r"moved-review\.md was changed in [0-9a-f]{7,} \(bob\)", r.stdout), r.stdout
    assert re.search(r"\[x\]-review\.md entered history in [0-9a-f]{7,} \(carol\)", r.stdout), (
        r.stdout
    )
    assert re.search(r"re-review\.md entered history in [0-9a-f]{7,} \(frank\)", r.stdout), r.stdout


def test_g9_an_edited_glob_named_review_names_its_own_editor(tmp_path: Path) -> None:
    """The edit query names the path LITERALLY: `[x]` as a glob would match `x` and blame its editor."""
    _, main = _origin(tmp_path)
    g = _write(main, "2026-10-08-[x]-review.md", _FAILING)
    x = _write(main, "2026-10-08-x-review.md", _FAILING)
    _commit(main)
    _git(main, "push", "-q")
    g.write_text(_FAILING + "\ng\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "g\n\nAgent-Name: carol")
    x.write_text(_FAILING + "\nx\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "x\n\nAgent-Name: dave")
    r = _run(main)
    assert re.search(r"\[x\]-review\.md was changed in [0-9a-f]{7,} \(carol\)", r.stdout), r.stdout


def test_g9_the_ok_line_counts_both_sources(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _write(main, "2026-10-08-g9c-review.md", _IN_PROGRESS)
    _commit(main)
    r = _run(main)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 changed + 1 unintegrated" in r.stdout, r.stdout


# --- G11: an integration branch that is neither master nor main -----------------------------------------------


def test_g11_a_main_checkout_on_a_non_master_branch_blocks_until_pushed(tmp_path: Path) -> None:
    _, main = _origin(tmp_path, branch="mobasak/x")
    _write(main, "2026-10-08-g11-review.md", _FAILING)
    _commit(main)
    r = _run(main)
    assert r.returncode == 1 and "2026-10-08-g11-review.md" in r.stdout, r.stdout + r.stderr
    _git(main, "push", "-q")
    assert _run(main).returncode == 0


# --- G12: a shallow clone skips the scan with a NOTE ----------------------------------------------------------


def test_g12_a_shallow_detached_clone_never_reds_an_integrated_review(tmp_path: Path) -> None:
    origin, main = _origin(tmp_path)
    _write(main, "2026-10-08-old-review.md", _FAILING)
    _commit(main)
    _git(main, "push", "-q")
    _git(main, "checkout", "-q", "-b", "feat")
    (main / "x.txt").write_text("x\n", encoding="utf-8")
    _commit(main)
    _git(main, "push", "-q", "origin", "feat")
    _git(
        tmp_path,
        "-c",
        "protocol.file.allow=always",
        "clone",
        "-q",
        "--depth",
        "1",
        "--no-single-branch",
        f"file://{origin}",
        "shallow",
    )
    sh = tmp_path / "shallow"
    _git(sh, "checkout", "-q", "--detach", "origin/feat")
    r = _run(sh)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "shallow clone" in r.stdout, r.stdout


# --- G13: a review hand-added inside a merge commit ------------------------------------------------------------


def test_g13_a_review_added_inside_a_merge_commit_blocks(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    wt = _worktree(main, tmp_path)
    (main / "y.txt").write_text("y\n", encoding="utf-8")
    _commit(main)
    _git(main, "push", "-q")
    _git(wt, "merge", "--no-ff", "--no-commit", "master")
    _write(wt, "2026-10-08-inmerge-review.md", _FAILING)
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "merge")
    r = _run(wt)
    assert r.returncode == 1 and "2026-10-08-inmerge-review.md" in r.stdout, r.stdout + r.stderr


def test_g13_a_clean_merge_adds_nothing(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    wt = _worktree(main, tmp_path)
    (main / "y.txt").write_text("y\n", encoding="utf-8")
    _commit(main)
    _git(main, "push", "-q")
    _git(wt, "merge", "-q", "--no-ff", "--no-edit", "master")
    r = _run(wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 changed + 0 unintegrated" in r.stdout, r.stdout


# --- G14: the main checkout parked on an upstream-less feature branch -------------------------------------------


def test_g14_a_main_checkout_on_a_feature_branch_does_not_red_integrated_reviews(
    tmp_path: Path,
) -> None:
    origin, main = _origin(tmp_path)
    _git(main, "checkout", "-q", "-b", "side")  # no upstream configured
    other = _clone(tmp_path, origin, "other")
    _write(other, "2026-10-08-int-review.md", _FAILING)
    _commit(other)
    _git(other, "push", "-q", "origin", "master")
    _git(main, "fetch", "-q", "origin")
    wt = _worktree(main, tmp_path, start="origin/master")
    r = _run(wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2026-10-08-int-review.md" not in r.stdout, r.stdout


# --- G15: a push to a new remote name clears nothing -------------------------------------------------------------


def test_g15_pushing_head_to_main_in_a_master_repo_clears_nothing(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    wt = _worktree(main, tmp_path)
    _write(wt, "2026-10-08-g15a-review.md", _FAILING)
    _commit(wt)
    _git(wt, "push", "-q", "origin", "HEAD:main")
    r = _run(wt)
    assert r.returncode == 1 and "2026-10-08-g15a-review.md" in r.stdout, r.stdout + r.stderr


def test_g15_pushing_head_to_master_in_a_non_master_repo_clears_nothing(tmp_path: Path) -> None:
    _, main = _origin(tmp_path, branch="mobasak/x")
    _write(main, "2026-10-08-g15b-review.md", _FAILING)
    _commit(main)
    _git(main, "push", "-q", "origin", "HEAD:master")
    r = _run(main)
    assert r.returncode == 1 and "2026-10-08-g15b-review.md" in r.stdout, r.stdout + r.stderr


def test_g15_a_local_tag_named_like_the_integration_ref_clears_nothing(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    wt = _worktree(main, tmp_path)
    _write(wt, "2026-10-08-g15d-review.md", _FAILING)
    _commit(wt)
    _git(wt, "tag", "origin/master", "HEAD")
    _git(wt, "tag", "master", "HEAD")
    r = _run(wt)
    assert r.returncode == 1 and "2026-10-08-g15d-review.md" in r.stdout, r.stdout + r.stderr


def test_g15_a_tag_shadowing_the_fallback_ref_clears_nothing(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _git(main, "checkout", "-q", "-b", "side")  # no upstream: the fallback origin/master is reached
    wt = _worktree(main, tmp_path, start="master")
    _write(wt, "2026-10-08-g15e-review.md", _FAILING)
    _commit(wt)
    _git(wt, "tag", "origin/master", "HEAD")
    r = _run(wt)
    assert r.returncode == 1 and "2026-10-08-g15e-review.md" in r.stdout, r.stdout + r.stderr


def test_g15_pushing_head_to_the_upstream_less_main_branch_clears_nothing(tmp_path: Path) -> None:
    _, main = _origin(tmp_path)
    _git(main, "checkout", "-q", "-b", "side")
    wt = _worktree(main, tmp_path, start="master")
    _write(wt, "2026-10-08-g15c-review.md", _FAILING)
    _commit(wt)
    _git(wt, "push", "-q", "origin", "HEAD:side")
    r = _run(wt)
    assert r.returncode == 1 and "2026-10-08-g15c-review.md" in r.stdout, r.stdout + r.stderr
