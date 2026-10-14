"""The phase-review gate finds a receipt a linked worktree holds (W-9fca9008, mail 01M48QZDFM):
a plan built in `.claude/worktrees/<name>` commits its receipts on the worktree branch, while the
run record — opened in the main checkout — roots the search at the main checkout.

A sibling tree only offers NEW evidence: `git worktree add` re-stamps every checked-out file with the
checkout time, so a receipt root already tracks, or an old commit on a sibling branch, never counts.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
REVIEWS = Path("docs") / "development" / "reviews"


def _load():
    spec = importlib.util.spec_from_file_location("command_run_phase_wt", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cr = _load()


def _git(cwd: Path, *args: str, env: dict | None = None) -> str:
    r = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
        env={**os.environ, **(env or {})},
    )
    return r.stdout


def _repo(tmp_path: Path) -> Path:
    main = tmp_path / "main"
    (main / REVIEWS).mkdir(parents=True)
    (main / "README.md").write_text("x\n", encoding="utf-8")
    _git(main, "init", "-q")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    return main


def _receipt(tree: Path, name: str) -> Path:
    p = tree / REVIEWS / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# review\nStatus: CONVERGED\n", encoding="utf-8")
    return p


def test_a_receipt_in_a_linked_worktree_satisfies_the_gate(tmp_path: Path) -> None:
    """Behaviour 1: the run is rooted at the main checkout; only the worktree holds the receipt."""
    main = _repo(tmp_path)
    since = time.time() - 5
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "build", str(wt))
    _receipt(wt, "2026-10-14-plan-1-x-phase-1-review.md")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "phase 1 receipt")
    assert not (main / REVIEWS / "2026-10-14-plan-1-x-phase-1-review.md").exists()
    assert cr._phase_review_exists(str(main), 1, since=since)


def test_a_wrong_phase_receipt_in_a_worktree_still_fails(tmp_path: Path) -> None:
    """Behaviour 2: phase-10's receipt in the worktree never satisfies phase 1."""
    main = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "build", str(wt))
    _receipt(wt, "x-phase-10-review.md")
    assert not cr._phase_review_exists(str(main), 1, since=time.time() - 5)


def test_a_non_git_root_searches_only_itself(tmp_path: Path) -> None:
    """Behaviour 3: no git → today's root-only search, unchanged."""
    root = tmp_path / "plain"
    _receipt(root, "x-phase-1-review.md")
    assert cr._phase_review_exists(str(root), 1)
    assert not cr._phase_review_exists(str(tmp_path / "other"), 1)


def test_a_replicated_receipt_in_a_later_worktree_does_not_satisfy(tmp_path: Path) -> None:
    """Behaviour 4: an OLD receipt root tracks, re-stamped by a worktree created after the run
    started, is replicated history — never new evidence (both design critiques measured this)."""
    main = _repo(tmp_path)
    old = _receipt(main, "x-phase-1-review.md")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "an old plan's receipt")
    then = time.time() - 30 * 86400
    os.utime(old, (then, then))
    since = time.time() - 5
    assert not cr._phase_review_exists(str(main), 1, since=since), "root alone: too old"
    _git(main, "worktree", "add", "-q", "-b", "sibling", str(tmp_path / "sibling"))
    copy = tmp_path / "sibling" / REVIEWS / "x-phase-1-review.md"
    assert copy.stat().st_mtime >= since, "checkout re-stamped the file — the trap"
    assert not cr._phase_review_exists(str(main), 1, since=since)


def test_a_sibling_receipt_is_aged_by_its_commit_and_an_unreadable_tree_is_skipped(
    tmp_path: Path, monkeypatch
) -> None:
    """Behaviour 5: a sibling branch's receipt committed BEFORE the run started does not count even
    though its checkout mtime is fresh; an unreadable sibling never hides root's own receipt."""
    main = _repo(tmp_path)
    _git(main, "branch", "old-plan")
    stage = tmp_path / "stage"
    _git(main, "worktree", "add", "-q", str(stage), "old-plan")
    _receipt(stage, "y-phase-2-review.md")
    _git(stage, "add", "-A")
    past = "2020-01-01T00:00:00+00:00"
    _git(stage, "commit", "-qm", "old", env={"GIT_COMMITTER_DATE": past, "GIT_AUTHOR_DATE": past})
    _git(main, "worktree", "remove", "--force", str(stage))
    since = time.time() - 5
    _git(main, "worktree", "add", "-q", str(tmp_path / "late"), "old-plan")
    assert (tmp_path / "late" / REVIEWS / "y-phase-2-review.md").stat().st_mtime >= since
    assert not cr._phase_review_exists(str(main), 2, since=since), "aged by commit, not checkout"

    # an earlier sibling that RAISES while being read never hides a later sibling's new receipt
    good = tmp_path / "zz-good"
    _git(main, "worktree", "add", "-q", "-b", "good", str(good))
    _receipt(good, "z-phase-3-review.md")
    late = (tmp_path / "late").resolve()
    real_rglob = Path.rglob

    def rglob(self, pattern):
        if self.resolve().is_relative_to(late):
            raise PermissionError(13, "denied", str(self))
        return real_rglob(self, pattern)

    order = [t.resolve() for t in cr._review_trees(str(main))[0]]
    assert order.index(late) < order.index(good.resolve()), "the raising tree is read first"
    monkeypatch.setattr(Path, "rglob", rglob)
    assert cr._phase_review_exists(str(main), 3, since=since)


def _commit_at(tree: Path, msg: str, when: str) -> None:
    _git(tree, "add", "-A")
    _git(tree, "commit", "-qm", msg, env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})


PAST = "2020-01-01T00:00:00+00:00"


def test_another_plans_stemless_receipt_in_a_sibling_never_satisfies_a_named_plan(
    tmp_path: Path,
) -> None:
    """Review r1 #1: a concurrent session's plan in another worktree is not this plan's evidence —
    when the record names its plan, a sibling's receipt must carry that plan's prefix or stem."""
    main = _repo(tmp_path)
    since = time.time() - 5
    wt = tmp_path / "other"
    _git(main, "worktree", "add", "-q", "-b", "other", str(wt))
    _receipt(wt, "2026-10-14-plan-9-other-phase-1-review.md")
    _receipt(wt, "x-phase-1-review.md")
    mine = "2026-10-14-plan-1-mine"
    assert not cr._phase_review_exists(str(main), 1, plan_stem=mine, since=since)
    _receipt(wt, f"{mine}-phase-1-review.md")
    assert cr._phase_review_exists(str(main), 1, plan_stem=mine, since=since)


def test_a_rebased_or_renamed_old_receipt_is_still_old(tmp_path: Path) -> None:
    """Review r1 #2/#3: a rebase re-stamps the committer time and a rename reads as an add to a
    path-limited log — the receipt is aged by its AUTHOR time, following renames."""
    main = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "b", str(wt))
    _receipt(wt, "r-phase-1-review.md")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "rebased", env={"GIT_AUTHOR_DATE": PAST})  # committer = now
    since = time.time() - 5
    assert not cr._phase_review_exists(str(main), 1, since=since), "committer time re-stamped"
    _git(wt, "mv", str(REVIEWS / "r-phase-1-review.md"), str(REVIEWS / "s-phase-2-review.md"))
    _git(wt, "commit", "-qm", "rename")
    assert not cr._phase_review_exists(str(main), 2, since=since), "a rename is not new evidence"


def test_a_receipt_root_tracks_but_the_branch_rewrote_is_new_evidence(tmp_path: Path) -> None:
    """Review r1 #4: the replicated-history skip is by CONTENT — a re-executed plan that rewrites
    its same-named receipt on the worktree branch satisfies the gate."""
    main = _repo(tmp_path)
    _receipt(main, "c-phase-1-review.md")
    _commit_at(main, "old receipt", PAST)
    os.utime(main / REVIEWS / "c-phase-1-review.md", (0, 0))
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "b", str(wt))
    since = time.time() - 5
    assert not cr._phase_review_exists(str(main), 1, since=since)
    (wt / REVIEWS / "c-phase-1-review.md").write_text("# review\nre-run\n", encoding="utf-8")
    _git(wt, "commit", "-qam", "rewritten receipt")
    assert cr._phase_review_exists(str(main), 1, since=since)


def test_the_refusal_note_never_outlives_its_scan(tmp_path: Path) -> None:
    """Review r1 #7: a call that scans nothing clears the previous call's coverage note."""
    main = _repo(tmp_path)
    cr._phase_review_exists(str(main), 1)
    assert cr._REVIEW_SCAN["note"]
    cr._phase_review_exists("", 1)
    assert cr._REVIEW_SCAN["note"] == ""


def test_a_templated_new_receipt_is_not_dated_by_its_older_lookalike(tmp_path: Path) -> None:
    """Review r2 R2-1: rename-following is EXACT — a fresh receipt sharing a template with an old
    one is new evidence, not the old file's history."""
    main = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "b", str(wt))
    body = "".join(f"| row {i} | CLEAN (template line {i}) |\n" for i in range(40))
    (wt / REVIEWS).mkdir(parents=True, exist_ok=True)
    (wt / REVIEWS / "t-phase-1-review.md").write_text("# phase 1\n" + body, encoding="utf-8")
    _commit_at(wt, "old receipt", PAST)
    since = time.time() - 5
    (wt / REVIEWS / "t-phase-2-review.md").write_text("# phase 2\n" + body, encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "new receipt from the template")
    assert cr._phase_review_exists(str(main), 2, since=since)


def test_a_recreated_untracked_receipt_is_aged_by_its_mtime(tmp_path: Path) -> None:
    """Review r2 R2-3: a receipt removed from the index and rewritten is untracked again — its old
    add commit says nothing about the new file."""
    main = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "b", str(wt))
    _receipt(wt, "u-phase-1-review.md")
    _commit_at(wt, "old receipt", PAST)
    _git(wt, "rm", "-q", str(REVIEWS / "u-phase-1-review.md"))
    since = time.time() - 5
    _receipt(wt, "u-phase-1-review.md")
    assert cr._phase_review_exists(str(main), 1, since=since)


def test_an_undated_stem_binds_no_sibling_receipt(tmp_path: Path) -> None:
    """Review r4 (stated cost): only a `<date>-plan-<n>` prefix binds a sibling's receipt — an
    undated stem falls back to the time bound, exactly as a record with no stem does."""
    main = _repo(tmp_path)
    since = time.time() - 5
    wt = tmp_path / "other"
    _git(main, "worktree", "add", "-q", "-b", "other", str(wt))
    _receipt(wt, "anything-phase-1-review.md")
    assert cr._phase_review_exists(str(main), 1, plan_stem="command-machinery", since=since)
    assert cr._sibling_bind_label("command-machinery") is None
    assert cr._sibling_bind_label("2026-10-14-plan-2a-x") == "2026-10-14-plan-2a"


def test_replicated_receipts_cost_no_subprocess_each(tmp_path: Path, monkeypatch) -> None:
    """Review r2: the replicated-history skip hashed every candidate with `git hash-object` —
    3,253 calls, ~25 s, on a 25-tree hub. The skip costs no subprocess per file."""
    main = _repo(tmp_path)
    for n in range(12):
        _receipt(main, f"old-{n}-phase-1-review.md")
    _commit_at(main, "old receipts", PAST)
    for w in ("a", "b"):
        _git(main, "worktree", "add", "-q", "-b", w, str(tmp_path / w))
    scan = cr.review_scan(str(main))
    calls = []
    real = subprocess.run
    monkeypatch.setattr(cr.subprocess, "run", lambda *a, **k: calls.append(a) or real(*a, **k))
    assert not cr._phase_review_exists(str(main), 1, since=time.time() + 60, scan=scan)
    assert len(calls) == 0, f"{len(calls)} git calls for 24 replicated receipts"


def test_the_refusal_names_the_prefix_a_sibling_receipt_must_carry(tmp_path: Path) -> None:
    """Review r2 R2-2 (the stated cost of plan binding): an unprefixed receipt in a worktree is
    refused, and the refusal tells the agent which name start would have counted."""
    main = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "b", str(wt))
    runs = tmp_path / "runs"
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(runs),
        "KAIZEN_EVENTS_DIR": str(tmp_path / "events"),
        "CLAUDE_SESSION_ID": "s-wt",
    }

    def cr_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=str(main),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    started = cr_cli(
        "start", "--command", "fabrik-execute-plan", "--phases", "3", "--terminal", "built",
        "--surface", "docs/development/plans/2026-10-14-plan-1-mine.md",
    )  # fmt: skip
    assert started.returncode == 0, started.stderr
    _receipt(wt, "2026-10-14-phase-1-review.md")
    refused = cr_cli("step", "--phase", "2", "--title", "B")
    assert refused.returncode == 2, refused.stderr
    assert "starts with `2026-10-14-plan-1`" in refused.stderr, refused.stderr
    _receipt(wt, "2026-10-14-plan-1-mine-phase-1-review.md")
    assert cr_cli("step", "--phase", "2", "--title", "B").returncode == 0


def test_glob_characters_in_a_receipt_name_are_literal(tmp_path: Path) -> None:
    """Review r3 R3-1: `[x]-phase-2-review.md` is not the pathspec glob matching `x-phase-…`."""
    main = _repo(tmp_path)
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "b", str(wt))
    _receipt(wt, "x-phase-2-review.md")
    _commit_at(wt, "old receipt", PAST)
    since = time.time() - 5
    _receipt(wt, "[x]-phase-2-review.md")
    assert cr._phase_review_exists(str(main), 2, since=since)


def test_a_dated_prefix_binds_every_honest_spelling_and_no_other_plan(tmp_path: Path) -> None:
    """Review r3/r4: five legitimate receipt spellings of plan 2 count; plan 20, 2a and 3 do not."""
    main = _repo(tmp_path)
    since = time.time() - 5
    wt = tmp_path / "other"
    _git(main, "worktree", "add", "-q", "-b", "other", str(wt))
    stem = "2026-10-14-plan-2-mine"
    for bad in ("2026-10-14-plan-20-x", "2026-10-14-plan-2a-x", "2026-10-14-plan-3-x"):
        _receipt(wt, f"{bad}-phase-1-review.md")
    assert not cr._phase_review_exists(str(main), 1, plan_stem=stem, since=since)
    for n, good in enumerate(
        ("-phase-2", "_phase_3", " phase 4", "-p5", "-other-slug-phase-6"), start=2
    ):
        _receipt(wt, f"2026-10-14-plan-2{good}-review.md")
        assert cr._phase_review_exists(str(main), n, plan_stem=stem, since=since), good


def test_a_replicated_symlink_receipt_hashes_as_git_does(tmp_path: Path) -> None:
    """Review r3 R3-3: git's blob of a symlink is its target path, not the target's bytes."""
    main = _repo(tmp_path)
    real = _receipt(main, "real.md")
    (main / REVIEWS / "s-phase-1-review.md").symlink_to("real.md")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "symlinked receipt")
    blob = cr._tracked_reviews(main)[f"{REVIEWS.as_posix()}/s-phase-1-review.md"]
    assert cr._blob_of(main, f"{REVIEWS.as_posix()}/s-phase-1-review.md", blob) == blob
    assert real.exists()
