"""T01b — the sync emits the multi-agent-per-repo worktree artifacts into every project.

WHY (design spec `docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md`
§ Lifecycle "Adoption" + "Synced-file drift inside a live worktree"): scaffold.py seeds
`rerere.enabled` + `push.autoSetupRemote` for a repo it CREATES
(`_configure_git_repo`, shipped `b7d7a727`) — that never reaches the ~46 repos that
already exist. And `.worktreeinclude` copies its gitignored set into a linked worktree
only at Claude Code's own creation-time hook, so a sync landing mid-epic otherwise
updates the main checkout alone.

CORRECTED premise (acceptance round 1, 2026-09-05): `.fabrik/synced.lock` is NOT one of
the ~55 patterns `worktreeinclude_text()` emits, so a worktree created before this
change had NO lock at all and `check_synced_unmodified.py` printed "not yet re-synced;
skipped" — it was SKIPPED, never falsely green against a stale copy. `resync_worktree_
artifacts` now runs AFTER the main checkout's lock is freshly written and copies that
fresh lock in too, so the worktree's own check has something real to compare against.

SECURITY, round 1 (class 1): a linked worktree's tracked `.gitignore` comes from
whatever branch it has checked out — often one cut before `.env`/`.mcp.json`
protection existed. `resync_worktree_artifacts` seeds the shared
`git-common-dir/info/exclude` (covers every worktree of the repo at once, regardless of
branch) and verifies with a real `git check-ignore` before copying either secret in.

DESTRUCTIVE, round 2 (class 1): the round-1 orphan-prune inside a worktree's directory
patterns deleted ANY destination file absent from the main checkout — including a
coding agent's own WIP under a synced directory (e.g. a new `scripts/enforcement/*.py`
not yet promoted to the hub) and even a file the worktree's own branch had COMMITTED.
A destination file is now pruned only when it (a) is absent from the main checkout's
current copy, (b) was named in a "prior history" record, and (c) is not tracked by
the worktree's own git.

DESTRUCTIVE, round 3 (class 1): round 2's "prior history" record was the worktree's
COPY OF THE MAIN CHECKOUT'S OWN `.fabrik/synced.lock` — which lists every path the
MAIN checkout manages, not what THIS worktree actually received (a secret the
check-ignore floor skipped, a locally-modified file left alone without `--force`, a
failed copy all show up there). Reading it as "this worktree's history" let a hub
retirement DELETE an agent's untracked, locally-edited file the resync had never
touched. Fixed with a genuine per-worktree ledger (`_WORKTREE_LEDGER_REL`,
`.fabrik/worktree-synced.lock`) that `resync_worktree_artifacts` itself writes AFTER
the copy loop, listing only the paths IT confirmed present this run (COPY/BACKUP, or
already byte-identical) — the copied main lock is NEVER read for prune authorization.
A left-alone file (WARN, no `--force`) is also surfaced now instead of silently
dropped (class 2), and the per-project summary line states the worktree contribution
so it agrees with the final `Results:` line (class 3).

SECRETS CLASSIFICATION, round 2 (class 2+3): measured 2026-09-05 across the 82 live
worktrees on seo/trade-intelligence/web-ecommerce-factory — `.mcp.json` is ignored in 0
of 82, TRACKED (already committed to the worktree's own branch — unfixable by an
ignore-rule fix) in 23 of 82 (trade-intelligence), and genuinely unprotected
(unignored AND untracked) in 59 of 82. `.env` is ignored in 82 of 82 — fully safe
today, corrected from round 1's wrong "unignored there too" claim. A tracked secret now
gets ONE informational NOTE per project, never a per-worktree WARN.

Every test uses a REAL tmp git repo — never a real /opt project (the sync must never
run for real against /opt/* from a test; a `--dry-run` fire-rate sweep is a one-off
manual run, quoted in the T01b ticket report, not something this suite repeats).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import fabrik_synced_manifest as manifest  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sync_worktree_adoption_mod", REPO / "scripts" / "sync_enforcement_to_projects.py"
)
assert _spec and _spec.loader
sync = importlib.util.module_from_spec(_spec)
sys.modules["sync_worktree_adoption_mod"] = sync  # dataclass field resolution needs the registry
_spec.loader.exec_module(sync)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q"], path)
    _run(["git", "config", "user.email", "t@example.com"], path)
    _run(["git", "config", "user.name", "t"], path)
    (path / "README.md").write_text("x\n")
    _run(["git", "add", "README.md"], path)
    _run(["git", "commit", "-q", "-m", "init"], path)
    return path


def _add_worktree(repo: Path, name: str, ref: str = "HEAD") -> Path:
    wt_dir = repo / ".claude" / "worktrees" / name
    wt_dir.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "worktree", "add", "-q", "-b", f"wt-{name}", str(wt_dir), ref], repo)
    return wt_dir


def _git_cfg(repo: Path, key: str) -> str | None:
    out = subprocess.run(
        ["git", "config", "--local", "--get", key], cwd=repo, capture_output=True, text=True
    )
    return out.stdout.strip() if out.returncode == 0 else None


def _touch_mtime(path: Path, seconds_from_now: float) -> None:
    t = time.time() + seconds_from_now
    os.utime(path, (t, t))


# --------------------------------------------------------------------------- #
# git-config seeding                                                          #
# --------------------------------------------------------------------------- #


def test_git_config_is_seeded_and_idempotent(tmp_path: Path):
    """Given a project directory, when the sync runs without --dry-run, then both keys
    are set to 'true', and a second run changes nothing."""
    repo = _init_repo(tmp_path / "proj")
    assert _git_cfg(repo, "rerere.enabled") is None, "guard: fresh repo has neither key"
    assert _git_cfg(repo, "push.autoSetupRemote") is None

    sync.seed_git_workflow_config(repo)

    assert _git_cfg(repo, "rerere.enabled") == "true"
    assert _git_cfg(repo, "push.autoSetupRemote") == "true"

    # An operator who turned one off keeps their answer — seed, never enforce.
    subprocess.run(
        ["git", "config", "--local", "rerere.enabled", "false"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    sync.seed_git_workflow_config(repo)  # second run
    assert _git_cfg(repo, "rerere.enabled") == "false", "an answered key must never be overwritten"
    assert _git_cfg(repo, "push.autoSetupRemote") == "true"


def test_git_config_key_order_matches_scaffold(tmp_path: Path):
    """scaffold.py:_configure_git_repo seeds push.autoSetupRemote before
    rerere.enabled — the sync's own seeding must use the identical order so the two
    paths are indistinguishable in a `git config --list` dump."""
    import ast

    src = (REPO / "src" / "fabrik" / "scaffold.py").read_text()
    tree = ast.parse(src)
    scaffold_order: list[str] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_configure_git_repo":
            for sub in ast.walk(node):
                if isinstance(sub, ast.For) and isinstance(sub.iter, ast.Tuple):
                    scaffold_order = [
                        elt.elts[0].value
                        for elt in sub.iter.elts
                        if isinstance(elt, ast.Tuple) and isinstance(elt.elts[0], ast.Constant)
                    ]
                    break
    assert scaffold_order == ["push.autoSetupRemote", "rerere.enabled"], scaffold_order

    src_sync = (REPO / "scripts" / "sync_enforcement_to_projects.py").read_text()
    tree_sync = ast.parse(src_sync)
    sync_order: list[str] | None = None
    for node in ast.walk(tree_sync):
        if isinstance(node, ast.FunctionDef) and node.name == "seed_git_workflow_config":
            for sub in ast.walk(node):
                if isinstance(sub, ast.For) and isinstance(sub.iter, ast.Tuple):
                    sync_order = [
                        elt.elts[0].value
                        for elt in sub.iter.elts
                        if isinstance(elt, ast.Tuple) and isinstance(elt.elts[0], ast.Constant)
                    ]
                    break
    assert sync_order == scaffold_order, (sync_order, scaffold_order)


def test_git_config_dry_run_writes_nothing(tmp_path: Path, capsys):
    repo = _init_repo(tmp_path / "proj")
    sync.seed_git_workflow_config(repo, dry_run=True)
    assert _git_cfg(repo, "rerere.enabled") is None
    assert _git_cfg(repo, "push.autoSetupRemote") is None
    out = capsys.readouterr().out
    assert "rerere.enabled" in out
    assert "push.autoSetupRemote" in out


# --------------------------------------------------------------------------- #
# Basic worktree re-copy                                                     #
# --------------------------------------------------------------------------- #


def test_worktree_artifacts_are_recopied_and_count_printed(tmp_path: Path, capsys):
    """Given a project with a linked worktree under .claude/worktrees/, when the sync
    lands, then the manifest's gitignored set is re-copied into that worktree and the
    run prints the REAL file count — after the loop, never a pre-loop guess."""
    repo = _init_repo(tmp_path / "proj")
    # A pattern `.worktreeinclude` actually carries (verbatim from the tracked template):
    # a plain governance file at the root.
    (repo / "AGENTS.md").write_text("agents doc\n")
    # A directory-shaped pattern: `.windsurf/` is one of the entries `worktreeinclude_text()`
    # emits (it walks GOVERNANCE_DIRS, which includes `.windsurf/rules`).
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "10-python.md").write_text("rule\n")

    wt_dir = _add_worktree(repo, "agent-x")

    count = sync.resync_worktree_artifacts(repo)

    assert count == 1
    assert (wt_dir / "AGENTS.md").read_text() == "agents doc\n"
    assert (wt_dir / ".windsurf" / "rules" / "core" / "10-python.md").read_text() == "rule\n"
    out = capsys.readouterr().out
    assert "Re-synced 2 file(s)" in out, out
    assert "1" in out and "worktree" in out.lower()


def test_no_worktrees_means_no_copy_and_unchanged_output(tmp_path: Path, capsys):
    """Given a project with NO worktrees, when the sync runs, then the loop performs no
    copy and the run's output is otherwise unchanged (no worktree line at all) — even
    though the secrets-exclude seed (class 7) still runs silently underneath."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")

    count = sync.resync_worktree_artifacts(repo)

    assert count == 0
    out = capsys.readouterr().out
    assert out == "", (
        "zero worktrees must print nothing — the loop costs nothing when it fires on none"
    )


def test_worktree_dry_run_counts_but_never_writes(tmp_path: Path):
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    wt_dir = _add_worktree(repo, "agent-x")

    count = sync.resync_worktree_artifacts(repo, dry_run=True)

    assert count == 1
    assert not (wt_dir / "AGENTS.md").exists(), "--dry-run must never write"


def test_dry_run_previews_an_orphan_deletion_without_deleting_it(tmp_path: Path, capsys):
    """class 1: `--dry-run` must enumerate would-delete files, not just print a
    worktree count. A file this worktree's own prior lock proves the sync wrote
    (hash-verified — round 6, class 1), now absent from the main checkout, is listed
    as a would-be deletion and survives."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / ".windsurf" / "rules" / "core").mkdir(parents=True)
    retired = wt_dir / ".windsurf" / "rules" / "core" / "retired.md"
    retired.write_text("stale\n")
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
        json.dumps({".windsurf/rules/core/retired.md": sync.compute_file_hash(retired)})
    )

    count = sync.resync_worktree_artifacts(repo, dry_run=True)

    assert count == 1
    assert (wt_dir / ".windsurf" / "rules" / "core" / "retired.md").exists(), (
        "--dry-run must never actually delete"
    )
    out = capsys.readouterr().out
    assert "Would delete (orphan removed (worktree))" in out, out
    assert "retired.md" in out


# --------------------------------------------------------------------------- #
# DESTRUCTIVE orphan-prune safety (class 1, round 2)                          #
# --------------------------------------------------------------------------- #


def test_worktree_local_content_survives_even_when_absent_from_source(tmp_path: Path):
    """DESTRUCTIVE regression (class 1, round 2) — reproduces the exact probe that
    found the bug: a worktree with one COMMITTED and one UNCOMMITTED file under a
    synced directory, neither ever recorded in this worktree's own lock (it has none —
    first resync). Both must survive: an untracked worktree-local file is not
    sync-managed just because it sits inside a synced directory tree, and a tracked
    file is the worktree's own branch content, never the sync's to touch."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "scripts" / "enforcement").mkdir(parents=True)
    (repo / "scripts" / "enforcement" / "check_x.py").write_text("# hub check\n")

    wt_dir = _add_worktree(repo, "agent-x")
    # scripts/enforcement/ was never committed in the main repo, so `git worktree add`
    # (which checks out only TRACKED files) does not create it in the worktree either.
    (wt_dir / "scripts" / "enforcement").mkdir(parents=True)
    (wt_dir / "scripts" / "enforcement" / "committed_wip.py").write_text(
        "# agent's new check, committed\n"
    )
    _run(["git", "add", "scripts/enforcement/committed_wip.py"], wt_dir)
    _run(["git", "commit", "-q", "-m", "wip: new enforcement check"], wt_dir)
    (wt_dir / "scripts" / "enforcement" / "uncommitted_wip.py").write_text(
        "# agent's new check, not yet committed\n"
    )

    sync.resync_worktree_artifacts(repo)

    assert (wt_dir / "scripts" / "enforcement" / "committed_wip.py").exists(), (
        "a file tracked in the worktree's own branch is never the sync's to delete"
    )
    assert (wt_dir / "scripts" / "enforcement" / "uncommitted_wip.py").exists(), (
        "an untracked worktree-local file merely living inside a synced directory "
        "is not an orphan — the sync never proved it wrote this"
    )
    assert (wt_dir / "scripts" / "enforcement" / "check_x.py").read_text() == "# hub check\n"


def test_worktree_directory_copy_prunes_a_file_the_sync_previously_wrote(tmp_path: Path, capsys):
    """A destination file IS pruned once its history is proven: seed the worktree's
    OWN ledger (`_WORKTREE_LEDGER_REL` — never the copied main lock) naming it, remove
    it from the main checkout, and confirm deletion — AND appears in the printed
    output (class 1, round 3). `__pycache__`/`.pyc` are skipped on both copy and
    prune, mirroring the VENDORED_DIRS leg (class 6, round 2)."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")
    (repo / ".windsurf" / "rules" / "core" / "__pycache__").mkdir()
    (repo / ".windsurf" / "rules" / "core" / "__pycache__" / "mod.pyc").write_bytes(b"\x00")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / ".windsurf" / "rules" / "core").mkdir(parents=True)
    retired = wt_dir / ".windsurf" / "rules" / "core" / "retired.md"
    retired.write_text("stale\n")
    (wt_dir / ".windsurf" / "rules" / "core" / "__pycache__").mkdir()
    (wt_dir / ".windsurf" / "rules" / "core" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    # Prove history via THIS worktree's OWN ledger — the mechanism round 3 requires;
    # the copied main lock (round 2's source) must NOT be read for this purpose. The
    # hash must be REAL (round 6, class 1): membership alone is no longer enough.
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
        json.dumps({".windsurf/rules/core/retired.md": sync.compute_file_hash(retired)})
    )

    sync.resync_worktree_artifacts(repo)
    out = capsys.readouterr().out

    assert (wt_dir / ".windsurf" / "rules" / "core" / "keep.md").read_text() == "keep\n"
    assert not (wt_dir / ".windsurf" / "rules" / "core" / "retired.md").exists(), (
        "proven history + absent from source = a real orphan, safe to delete"
    )
    assert "retired.md" in out, "a real deletion must appear in the output"
    assert (wt_dir / ".windsurf" / "rules" / "core" / "__pycache__" / "x.pyc").exists(), (
        "pycache is never touched by the worktree copy/prune, mirroring VENDORED_DIRS"
    )


def test_worktree_prune_never_deletes_a_tracked_file_even_if_ledger_names_it(tmp_path: Path):
    """Defense in depth: even a path THIS worktree's own ledger names is never pruned
    if the worktree's own branch has since committed it — that content is no longer
    the sync's to remove."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (wt_dir / ".windsurf" / "rules" / "core" / "adopted.md").write_text("now mine\n")
    _run(["git", "add", ".windsurf/rules/core/adopted.md"], wt_dir)
    _run(["git", "commit", "-q", "-m", "adopt this synced file as our own"], wt_dir)
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(json.dumps([".windsurf/rules/core/adopted.md"]))

    sync.resync_worktree_artifacts(repo)

    assert (wt_dir / ".windsurf" / "rules" / "core" / "adopted.md").exists(), (
        "a file committed to the worktree's own branch must never be deleted by the sync"
    )


def test_empty_dir_prune_is_gated_on_the_ledger_and_reported(tmp_path: Path, capsys):
    """[L] round 3 (native-finder), class 5: a bare `rmdir()` on any empty directory
    bypassed the three-part prune predicate entirely and went unreported. Only a
    directory the ledger proves the sync once populated is removed, and it is
    reported like any other deletion."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    # A directory the ledger DOES claim the sync populated (a file it once wrote
    # there has since been pruned/retired) -- now empty, it should be removed too.
    (wt_dir / ".windsurf" / "rules" / "core" / "sub-owned").mkdir(parents=True)
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
        json.dumps({".windsurf/rules/core/sub-owned/retired.md": ""})
    )
    # A directory the sync NEVER populated -- a coding agent's own empty scratch dir
    # that merely happens to sit inside the same synced tree.
    (wt_dir / ".windsurf" / "rules" / "core" / "agent-scratch").mkdir(parents=True)

    sync.resync_worktree_artifacts(repo)
    out = capsys.readouterr().out

    assert not (wt_dir / ".windsurf" / "rules" / "core" / "sub-owned").exists(), (
        "an empty directory the ledger proves the sync populated must be removed"
    )
    assert (wt_dir / ".windsurf" / "rules" / "core" / "agent-scratch").exists(), (
        "an empty directory the ledger never claims must survive"
    )
    assert "sub-owned" in out, "the directory removal must be reported like any other deletion"


def test_file_ledger_row_does_not_authorize_deleting_a_samepath_directory(tmp_path: Path, capsys):
    """[M] round 7, class 9: `ledger_owns_dir` accepted `p == rel_dir` — a ledger
    row for a FILE the sync once wrote AT THIS EXACT PATH — as proof it also owns a
    DIRECTORY later created at that same relative path. A retired file and a
    same-named directory an agent creates afterward are two different objects; only
    a row for a file UNDER the directory (a real prefix match) is evidence the sync
    ever populated the directory itself. Grader: a ledger row for `core/foo` (a
    FILE, now retired) while `core/foo` is currently an EMPTY DIRECTORY on disk must
    survive — unlike a genuinely sync-owned empty directory (whose row is a PREFIX
    match), which is still removed and reported with its own `deletion.reason`."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    core = wt_dir / ".windsurf" / "rules" / "core"
    # The false-positive case: a ledger row EXACTLY matching a directory's own path
    # (proof a FILE once lived there, never proof of a directory).
    (core / "foo").mkdir(parents=True)
    # The genuine case, alongside it: a ledger row for a FILE UNDER a (now-empty)
    # directory — a real prefix match.
    (core / "sub-owned").mkdir(parents=True)
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
        json.dumps(
            {
                ".windsurf/rules/core/foo": "some-stale-file-hash",
                ".windsurf/rules/core/sub-owned/retired.md": "",
            }
        )
    )

    sync.resync_worktree_artifacts(repo)
    out = capsys.readouterr().out

    assert (core / "foo").exists(), (
        "a FILE-row exact match must never authorize deleting a same-named directory"
    )
    assert not (core / "sub-owned").exists(), (
        "a genuine prefix-match row must still authorize removing the empty directory"
    )
    assert "sub-owned" in out and "empty dir removed (worktree)" in out, out


def test_prune_backs_up_a_deleted_file_when_backup_flag_set(tmp_path: Path):
    """[L] round 3, class 6, CORRECTED in round 4 (class 6): the prune's `unlink`
    ignored `--backup` while every copy path honors it — back up before deleting.
    Round 4 relocates the backup OUTSIDE the worktree's own tree
    (`.fabrik/backups/worktrees/<name>/…`) — litter beside the pruned file inside a
    live worktree is never cleaned."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / ".windsurf" / "rules" / "core").mkdir(parents=True)
    retired = wt_dir / ".windsurf" / "rules" / "core" / "retired.md"
    retired.write_text("stale content\n")
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
        json.dumps({".windsurf/rules/core/retired.md": sync.compute_file_hash(retired)})
    )

    sync.resync_worktree_artifacts(repo, backup=True)

    assert not (wt_dir / ".windsurf" / "rules" / "core" / "retired.md").exists()
    # Never beside the pruned file, inside the live worktree:
    assert not list((wt_dir / ".windsurf" / "rules" / "core").glob("retired.md.backup.*")), (
        "backup litter must never land inside the worktree's own tree"
    )
    backup_root = repo / ".fabrik" / "backups" / "worktrees" / "agent-x"
    backups = list(backup_root.glob("**/retired.md.backup.*"))
    assert backups, "backup=True must back up a pruned file, outside the worktree"
    assert backups[0].read_text() == "stale content\n"


def test_backup_stamp_survives_two_calls_in_the_same_second(tmp_path: Path):
    """[M] round 8, class 4: the round-7 fix (microsecond-precision backup
    timestamps, `%Y%m%d-%H%M%S-%f`) shipped ungraded — it was the sole survivor of a
    14-mutant sweep. Before that fix, two backups of the SAME path inside one wall-
    clock second (e.g. a ledger-refresh COPY followed by a later PRUNE of that same
    file, both routing through `_backup_worktree_file`) collided on their
    second-resolution stamp and the second write silently clobbered the first —
    never surfaced, since both calls report success. Calling it twice back-to-back
    on one path must leave TWO distinct files, each holding its own content."""
    repo = _init_repo(tmp_path / "proj")
    wt_dir = _add_worktree(repo, "agent-x")
    target = wt_dir / "some" / "path.md"
    target.parent.mkdir(parents=True)

    target.write_text("version one\n")
    sync._backup_worktree_file(target, wt_dir, repo)

    target.write_text("version two\n")
    sync._backup_worktree_file(target, wt_dir, repo)

    backup_root = repo / ".fabrik" / "backups" / "worktrees" / "agent-x"
    backups = sorted(backup_root.glob("**/path.md.backup.*"))
    assert len(backups) == 2, (
        f"two backups inside one second must never collide onto the same filename: {backups}"
    )
    contents = {b.read_text() for b in backups}
    assert contents == {"version one\n", "version two\n"}, (
        "the second backup must never silently clobber the first"
    )


def test_unlink_failure_during_prune_leaves_the_file_and_its_row_intact(
    tmp_path: Path, monkeypatch, capsys
):
    """[H] round 7, class 2: the prune loop used to record the DELETE result, print
    "Deleted orphan", and pop the ledger row BEFORE calling `existing.unlink()` — an
    EPERM/ENOENT there left the file physically ON DISK while every downstream
    bookkeeping step had already treated it as gone (an inflated deletion count, a
    false "Deleted" line, and a popped row that could never again prove the file
    "already ours"). `unlink()` now runs FIRST, inside the same per-item
    try/except, so a failure there falls straight into the WARN branch and never
    reaches the report/pop code at all. Grader: 3 orphan candidates, one poisoned —
    it survives on disk, its ledger row survives, the tally counts exactly 2
    removed (not 3), and exactly one WARN covers the survivor."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    core = wt_dir / ".windsurf" / "rules" / "core"
    core.mkdir(parents=True, exist_ok=True)
    ledger: dict[str, str] = {}
    paths: dict[str, Path] = {}
    for name in ("a.py", "b.py", "c.py"):
        p = core / name
        p.write_text(f"{name} stale\n")
        paths[name] = p
        ledger[f".windsurf/rules/core/{name}"] = sync.compute_file_hash(p)
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(json.dumps(ledger))

    real_unlink = Path.unlink
    trigger = str(paths["b.py"].resolve())

    def flaky_unlink(self, *a, **kw):
        if str(self) == trigger:
            raise OSError(1, "simulated EPERM (unlink)")
        return real_unlink(self, *a, **kw)

    warnings_before = sync._WORKTREE_TALLY["warnings"]
    deletions_before = sync._WORKTREE_TALLY["deletions"]
    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    try:
        sync.resync_worktree_artifacts(repo)
    finally:
        monkeypatch.undo()
    out = capsys.readouterr().out

    # The poisoned file survives, unmodified, on disk...
    assert paths["b.py"].exists(), "a failed unlink must leave the file physically in place"
    assert paths["b.py"].read_text() == "b.py stale\n"
    # ...and its ledger row survives (never popped for a deletion that never happened).
    ledger_after = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert ledger_after.get(".windsurf/rules/core/b.py") == ledger[".windsurf/rules/core/b.py"], (
        "a row must survive its file's own failed prune"
    )
    # The other two were genuinely removed, and their rows are gone.
    assert not paths["a.py"].exists()
    assert not paths["c.py"].exists()
    assert ".windsurf/rules/core/a.py" not in ledger_after
    assert ".windsurf/rules/core/c.py" not in ledger_after
    # Exactly 2 counted removed (never 3 — no false "Deleted" for the survivor).
    assert sync._WORKTREE_TALLY["deletions"] - deletions_before == 2, sync._WORKTREE_TALLY
    assert sync._WORKTREE_TALLY["warnings"] - warnings_before == 1, sync._WORKTREE_TALLY
    assert out.count("orphan removed (worktree)") == 2, out
    assert "b.py" in out and "WARN" in out, out


def test_backup_directory_is_gitignored_by_the_manifest(tmp_path: Path, monkeypatch):
    """[L] round 5, class 4: `<project>/.fabrik/backups/` landed untracked —
    `git check-ignore` reported NOT IGNORED in 3 of 3 sampled projects (it only fires
    under a manual `--backup`; the production wrapper passes `--force` only, so this
    was latent rather than actively dirtying every project). The manifest's
    gitignore block must cover it, and a full sync must patch it into a project's
    tracked `.gitignore`."""
    assert "/.fabrik/backups/" in manifest.gitignore_block_text().splitlines()

    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)

    result = sync.sync_scripts_to_project(repo, dry_run=False)
    assert result.success, result.message

    (repo / ".fabrik" / "backups" / "worktrees" / "agent-x").mkdir(parents=True)
    (repo / ".fabrik" / "backups" / "worktrees" / "agent-x" / "x.backup.1").write_text("x\n")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert ".fabrik/backups" not in status, status


def test_worktree_ledger_is_gitignored_by_the_manifest(tmp_path: Path, monkeypatch):
    """[L] round 7, class 1: the per-worktree ledger `resync_worktree_artifacts`
    reads and writes (`_WORKTREE_LEDGER_REL`, `.fabrik/worktree-synced.lock`) — the
    record the whole prune/copy safety design rests on — was missing from the
    manifest's "Local state" list entirely, so it showed as `?? .fabrik/`
    (UNTRACKED, unignored) in every live worktree; an operator running `git clean
    -fd` there would delete it, silently reverting every worktree file to
    ledger-gap WARN state. Unlike `.fabrik/backups/` (written into the MAIN
    checkout — see `test_backup_directory_is_gitignored_by_the_manifest`), this
    ledger lives INSIDE each linked worktree, so the fix must actually reach a
    worktree's own checked-out `.gitignore`, not just the main checkout's."""
    assert ".fabrik/worktree-synced.lock" in manifest.gitignore_block_text().splitlines()

    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)

    result = sync.sync_scripts_to_project(repo, dry_run=False)
    assert result.success, result.message
    # The patch lands in the MAIN checkout's working tree only until committed — a
    # worktree cut afterwards inherits whatever is in HEAD, same as any other
    # tracked file.
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "patch gitignore"], repo)

    wt_dir = _add_worktree(repo, "agent-x")
    assert sync._worktree_ignores(wt_dir, ".fabrik/worktree-synced.lock"), (
        "the worktree's OWN checked-out .gitignore must cover its own ledger"
    )

    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(json.dumps({"AGENTS.md": "deadbeef"}))

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt_dir, capture_output=True, text=True
    ).stdout
    assert ".fabrik" not in status, status


def test_doc_step_2_pattern_list_matches_the_floor_tuple():
    """[M] round 12, class 1: `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` step 2
    ("Shared floor") said `_WORKTREE_FLOOR_PATTERNS` was "FOUR patterns as of round
    10" and enumerated four — the round-11 commit that added the fifth
    (`.fabrik/.ledger-tmp-*`) reworded the three lines above without updating the
    count or the list. Parses the backticked patterns out of that exact paragraph
    (between the `_WORKTREE_FLOOR_PATTERNS`: label and "Each needs this exact
    mechanism", the boundary this doc's own prose uses) and asserts set-equality
    with the real tuple — so the doc can never again silently drift from the code."""
    doc = (REPO / "docs" / "workflows" / "SYNC_ENFORCEMENT_WORKFLOW.md").read_text()
    start_marker = "with `_WORKTREE_FLOOR_PATTERNS`:"
    end_marker = "Each needs this"  # never a longer phrase — markdown line-wraps inside it
    start = doc.index(start_marker) + len(start_marker)
    end = doc.index(end_marker, start)
    span = doc[start:end]

    doc_patterns = set(re.findall(r"`(\.[^`]*)`", span))
    code_patterns = set(sync._WORKTREE_FLOOR_PATTERNS)

    assert doc_patterns == code_patterns, (
        f"doc step 2 lists {doc_patterns} but the code's floor is {code_patterns} — "
        "the doc drifted from _WORKTREE_FLOOR_PATTERNS"
    )


def test_dry_run_names_the_gitignore_patch_when_the_block_is_stale(
    tmp_path: Path, monkeypatch, capsys
):
    """[L] round 6, class 7: the `.gitignore` patch reaches every project's TRACKED
    `.gitignore` on the next real run (45 dirty trees fleet-wide) and
    `check_synced_unmodified` never flags it (`.gitignore` is not itself in
    `synced.lock`) — the default `--dry-run` preview named it nowhere
    (`grep -c "Fabrik-synced block"` was 0 without `--verbose`). Under the round-4
    precedent (a fleet-wide write earns a named preview line), `--dry-run` must print
    `Would patch … .gitignore (Fabrik-synced block)` for a project whose block is
    stale, and must NOT print it for one whose block is already current."""
    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)

    # A project with a STALE (absent) Fabrik-synced block.
    stale_repo = _init_repo(tmp_path / "stale-proj")
    (stale_repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], stale_repo)
    _run(["git", "commit", "-q", "-m", "add"], stale_repo)

    result = sync.sync_scripts_to_project(stale_repo, dry_run=True)
    assert result.success, result.message
    out_stale = capsys.readouterr().out
    assert "Would patch" in out_stale and ".gitignore" in out_stale, out_stale

    # A project whose block is already CURRENT (a prior real sync already patched it).
    current_repo = _init_repo(tmp_path / "current-proj")
    (current_repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], current_repo)
    _run(["git", "commit", "-q", "-m", "add"], current_repo)
    real_result = sync.sync_scripts_to_project(current_repo, dry_run=False)
    assert real_result.success, real_result.message
    capsys.readouterr()  # discard the real run's own output

    result2 = sync.sync_scripts_to_project(current_repo, dry_run=True)
    assert result2.success, result2.message
    out_current = capsys.readouterr().out
    assert "Would patch" not in out_current, out_current


def test_real_run_names_the_gitignore_patch_and_folds_it_into_results(
    tmp_path, monkeypatch, capsys
):
    """[L] round 7, class 3: the REAL (non-`--dry-run`) `.gitignore` patch write
    reaches every tracked `.gitignore` fleet-wide and used to announce it NOWHERE —
    no per-project print existed on this path (only `--dry-run` had one), and
    nothing in the run's own `Results:` summary line, the one line that survives
    the production wrapper's `tail -3` (`scripts/governance_sync_postcommit.sh:82`).
    A real run must now print its own disclosure line and roll the count into
    `Results:` as `gitignore patched: N` — and a clean second run, with the block
    already current, must show neither."""
    fake_opt = tmp_path / "opt"
    fake_opt.mkdir()
    repo = _init_repo(fake_opt / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)
    monkeypatch.setattr(sync, "OPT_ROOT", fake_opt)
    monkeypatch.setattr(sys, "argv", ["sync_enforcement_to_projects.py"])

    sync.main()
    out = capsys.readouterr().out

    assert "Patched" in out and ".gitignore" in out, out
    assert "gitignore patched: 1" in out, out

    # A second run — the block is now current; nothing left to patch or announce.
    sync.main()
    out2 = capsys.readouterr().out
    assert "gitignore patched" not in out2, out2
    assert "Patched" not in out2, out2


def test_dry_run_orphan_wording_is_future_tense(tmp_path: Path, capsys):
    """[L] round 3 (native-finder), class 7: the dry-run summary said "orphan(s)
    removed" in past tense on a run that deleted nothing — must say "would be
    removed"."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / ".windsurf" / "rules" / "core").mkdir(parents=True)
    retired = wt_dir / ".windsurf" / "rules" / "core" / "retired.md"
    retired.write_text("stale\n")
    (wt_dir / ".fabrik").mkdir()
    (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
        json.dumps({".windsurf/rules/core/retired.md": sync.compute_file_hash(retired)})
    )

    sync.resync_worktree_artifacts(repo, dry_run=True)
    out = capsys.readouterr().out

    assert "orphan(s) would be removed" in out, out
    assert (wt_dir / ".windsurf" / "rules" / "core" / "retired.md").exists(), (
        "--dry-run must never actually delete"
    )


def test_prune_never_uses_the_copied_main_lock_as_proof_of_authorship(tmp_path: Path):
    """[H] round 3, class 1 — the exact reproduction: the copied main
    `.fabrik/synced.lock` lists every path the MAIN checkout manages, including paths
    THIS worktree never actually received. Here, a locally-edited, untracked worktree
    file is left ALONE (WARN, no --force) on the first resync — never written here —
    yet the main lock still names its path (it exists in the main checkout). Reading
    that copied lock as "this worktree's history" (round 2's bug) would delete the
    agent's edit the moment the hub retires the path. The per-worktree ledger must
    never make that mistake: only what THIS resync itself wrote is ever authorization
    to prune."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "scripts" / "enforcement").mkdir(parents=True)
    (repo / "scripts" / "enforcement" / "check_x.py").write_text("# hub version\n")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / "scripts" / "enforcement").mkdir(parents=True)
    (wt_dir / "scripts" / "enforcement" / "check_x.py").write_text("# agent's local edit\n")
    _touch_mtime(wt_dir / "scripts" / "enforcement" / "check_x.py", 3600)  # newer than source

    # Simulate the main checkout's OWN lock (written by sync_scripts_to_project,
    # copied into the worktree as one of the worktreeinclude+lock patterns) naming
    # this path — because the MAIN checkout manages it, regardless of what this
    # worktree actually received.
    (repo / ".fabrik").mkdir()
    (repo / ".fabrik" / "synced.lock").write_text(
        json.dumps({"scripts/enforcement/check_x.py": "somehash"})
    )

    # First resync: WARN'd and left alone (no --force) — never actually written here,
    # so it must NOT enter this worktree's own ledger.
    sync.resync_worktree_artifacts(repo, force=False)
    assert (
        wt_dir / "scripts" / "enforcement" / "check_x.py"
    ).read_text() == "# agent's local edit\n"
    ledger = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert "scripts/enforcement/check_x.py" not in ledger, (
        "a file the resync only WARN'd about (never wrote) must not enter the ledger"
    )

    # The hub retires check_x.py.
    (repo / "scripts" / "enforcement" / "check_x.py").unlink()

    # Second resync must NOT delete the agent's untouched local file, even though the
    # (now stale) copied main lock in the worktree still names its path.
    sync.resync_worktree_artifacts(repo, force=False)

    assert (wt_dir / "scripts" / "enforcement" / "check_x.py").exists(), (
        "a file the resync never actually wrote into this worktree must survive "
        "retirement, even though the copied main lock happens to name its path"
    )


def test_prune_never_deletes_an_edited_file_whose_stale_row_survived_the_merge(
    tmp_path: Path, capsys
):
    """[H] round 6, class 1 — REGRESSION introduced by round 5's own merge fix. The
    exact chain: run1 establishes a REAL ledger row for x.py. The agent then edits
    x.py in the worktree — run2 correctly WARNs "edit preserved" and leaves it alone,
    but round 5's merge semantics carry x.py's OLD (pre-edit) row forward into the
    ledger unchanged (a WARN never updates it, and rows are never dropped just
    because a run didn't re-confirm them). Before this fix, the prune predicate
    checked only ledger MEMBERSHIP — so once the hub retires x.py, that surviving
    stale row was full authorization to delete it: "Deleted orphan" — the agent's
    edit, gone, with `--backup` never armed in production (the wrapper passes
    `--force` only). After the fix, pruning ALSO requires the ledger's recorded hash
    to match what is actually on disk; a mismatch (the edit) gets the same
    "differs from the ledger record" treatment the copy side already uses — WARN,
    never delete."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "x.py").write_text("hub v1\n")
    wt_dir = _add_worktree(repo, "agent-x")

    # run1: a REAL resync establishes a genuine ledger row for x.py.
    sync.resync_worktree_artifacts(repo)
    x_path = wt_dir / ".windsurf" / "rules" / "core" / "x.py"
    assert x_path.read_text() == "hub v1\n"
    ledger1 = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert ledger1.get(".windsurf/rules/core/x.py") == sync.compute_file_hash(x_path)

    # The agent works on x.py for hours; the hub also advances it.
    x_path.write_text("the agent's hours of work\n")
    (repo / ".windsurf" / "rules" / "core" / "x.py").write_text("hub v2\n")

    # run2: WARN'd and left alone — the edit survives, but round 5's merge keeps
    # x.py's OLD (pre-edit) row in the ledger regardless.
    sync.resync_worktree_artifacts(repo)
    assert x_path.read_text() == "the agent's hours of work\n"
    ledger2 = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert ".windsurf/rules/core/x.py" in ledger2, (
        "guard: the stale row must still be present — this is what round 5's merge does on purpose"
    )
    assert ledger2[".windsurf/rules/core/x.py"] != sync.compute_file_hash(x_path), (
        "guard: the surviving row must NOT match the agent's current edit"
    )

    # The hub retires x.py entirely.
    (repo / ".windsurf" / "rules" / "core" / "x.py").unlink()

    # run3: production never passes --backup — this must WARN, never delete.
    sync.resync_worktree_artifacts(repo)
    out = capsys.readouterr().out

    assert x_path.exists(), "the agent's edit must survive — a stale row is not proof of anything"
    assert x_path.read_text() == "the agent's hours of work\n"
    assert "Deleted orphan" not in out, out
    assert "differs from the ledger record — left in place, not pruned" in out, out


def test_ledger_is_merged_not_rebuilt_across_a_transient_pattern_failure(
    tmp_path: Path, monkeypatch, capsys
):
    """[H] round 5, class 1 — the exact three-run chain that found the destructive
    bug. run1 establishes a 2-row ledger. run2 hits a transient OSError deep in one
    pattern's prune loop (`(src_dir / rel).exists()` raising, e.g. on a locked
    subdir) — before this fix: silently (no print, no counter), the crashed
    function's partial `authored` map was discarded, and because the ledger was
    REBUILT from only what THIS run adjudicated, the write at the end WIPED it to
    `[]`; a later run then WARNs "edit preserved" on files the sync itself wrote,
    forever, with no visible cause. After the fix: the ledger MERGES (seeded from the
    previous ledger before the pattern loop), so rows a crashed pattern never got to
    re-confirm survive, and the crash itself is now a printed, counted WARN — never a
    silent continue."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "a.py").write_text("a v1\n")
    (repo / ".windsurf" / "rules" / "core" / "a2.py").write_text("a2 v1\n")
    wt_dir = _add_worktree(repo, "agent-x")

    # run1: establish the ledger.
    sync.resync_worktree_artifacts(repo)
    ledger1 = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert set(ledger1) == {
        ".windsurf/rules/core/a.py",
        ".windsurf/rules/core/a2.py",
    }, ledger1

    (repo / ".windsurf" / "rules" / "core" / "a.py").write_text("a v2\n")
    (repo / ".windsurf" / "rules" / "core" / "a2.py").write_text("a2 v2\n")

    # run2: inject the transient failure exactly where the finder pinpointed it —
    # (src_dir / rel).exists() inside the prune loop, for ONE file, well after the
    # copy phase has already refreshed both files on disk.
    real_exists = Path.exists
    trigger = str((repo / ".windsurf" / "rules" / "core" / "a2.py").resolve())

    def flaky_exists(self, *a, **kw):
        if str(self) == trigger:
            raise OSError(13, "Permission denied (simulated transient failure)")
        return real_exists(self, *a, **kw)

    monkeypatch.setattr(Path, "exists", flaky_exists)
    try:
        sync.resync_worktree_artifacts(repo)
    finally:
        monkeypatch.undo()
    out2 = capsys.readouterr().out

    # The crash is now VISIBLE — printed and counted — never a silent continue.
    assert "WARN" in out2 and "error" in out2.lower(), out2

    # The files that finished copying before the crash are genuinely on disk...
    assert (wt_dir / ".windsurf" / "rules" / "core" / "a.py").read_text() == "a v2\n"
    assert (wt_dir / ".windsurf" / "rules" / "core" / "a2.py").read_text() == "a2 v2\n"

    # ...and, the actual fix under test: the ledger is NOT wiped to [] — it still
    # carries the historical rows (merged, not rebuilt).
    ledger2 = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert ledger2, "the ledger must never be wiped by a transient failure elsewhere"
    assert set(ledger2) == {
        ".windsurf/rules/core/a.py",
        ".windsurf/rules/core/a2.py",
    }, ledger2

    # run3: a clean run — an UNRELATED file must keep converging normally; the
    # crashed pattern's own worktree never freezes the rest of the sync.
    (repo / "AGENTS.md").write_text("agents doc\n")
    sync.resync_worktree_artifacts(repo)
    assert (wt_dir / "AGENTS.md").read_text() == "agents doc\n", (
        "an unrelated file must sync normally on the next clean run"
    )


def test_corrupt_ledger_warns_before_treating_it_as_empty(tmp_path: Path, capsys):
    """[L] round 7, class 8: a corrupt ledger (bad JSON — an interrupted write, a
    crash mid-truncate before the round-6 atomic-write fix, hand-editing) used to be
    silently read as `{}` — indistinguishable from a worktree's genuine first-ever
    resync. An operator has no way to tell "nothing here yet" apart from "the ledger
    got corrupted and every row was just lost" without a signal. Must print one WARN
    naming the unreadable lock path before falling back to empty history."""
    repo = _init_repo(tmp_path / "proj")
    wt = _add_worktree(repo, "agent-x")
    lock_path = wt / sync._WORKTREE_LEDGER_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("{not valid json at all")

    result = sync._read_worktree_ledger(wt)
    out = capsys.readouterr().out

    assert result == {}, "a corrupt ledger must still fall back to empty history"
    assert "WARN" in out, out
    assert str(lock_path) in out, out


def test_corrupt_ledger_warn_reaches_the_surviving_results_line(tmp_path, monkeypatch, capsys):
    """[L] round 8, class 5: the corrupt-ledger WARN (round 7, class 8) printed a
    per-worktree line the production wrapper's `tail -3`
    (`scripts/governance_sync_postcommit.sh:82`) discards, and never reached
    `_WORKTREE_TALLY` either — so it was ALSO absent from the `Results:` line that
    DOES survive truncation. A corrupt ledger was invisible past the raw log. Must
    bump the tally so `main()`'s summary counts it like any other worktree WARN."""
    fake_opt = tmp_path / "opt"
    fake_opt.mkdir()
    repo = _init_repo(fake_opt / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)
    wt = _add_worktree(repo, "agent-x")
    lock_path = wt / sync._WORKTREE_LEDGER_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("{not valid json at all")

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)
    monkeypatch.setattr(sync, "OPT_ROOT", fake_opt)
    monkeypatch.setattr(sys, "argv", ["sync_enforcement_to_projects.py"])

    sync.main()
    out = capsys.readouterr().out

    results_line = next(line for line in out.splitlines() if line.startswith("Results:"))
    assert "warning(s)" in results_line, (
        f"the corrupt-ledger WARN never reached the surviving Results line: {results_line}"
    )


def test_ledger_write_is_atomic(tmp_path: Path, monkeypatch):
    """[M] round 6, class 3: `_write_worktree_ledger` used a bare `write_text`, which
    truncates the file before writing the new content — a kill between truncate and
    write (OOM, SIGKILL, a host reboot) leaves invalid JSON on disk, which
    `_read_worktree_ledger` then reads as "no history at all", turning every path
    this worktree ever legitimately held into a permanent gap needing the manual
    bootstrap. Fixed to write a same-directory tempfile then `os.replace` it into
    place (mirrors `_atomic_copy`). Grader: monkeypatch `os.replace` to raise and
    assert the ORIGINAL ledger bytes are completely untouched — the write is either
    fully applied or not applied at all, never partial."""
    repo = _init_repo(tmp_path / "proj")
    wt_dir = _add_worktree(repo, "agent-x")
    lock_path = wt_dir / sync._WORKTREE_LEDGER_REL

    original_payload = {"some/original/path.md": "original-hash"}
    sync._write_worktree_ledger(wt_dir, original_payload)
    original_bytes = lock_path.read_bytes()
    assert json.loads(original_bytes) == original_payload

    real_replace = os.replace

    def flaky_replace(*a, **kw):
        raise OSError(5, "simulated I/O failure mid-swap")

    monkeypatch.setattr(os, "replace", flaky_replace)
    try:
        sync._write_worktree_ledger(wt_dir, {"some/new/path.md": "new-hash"})
    finally:
        monkeypatch.setattr(os, "replace", real_replace)

    assert lock_path.read_bytes() == original_bytes, (
        "a failed atomic swap must never leave the original ledger partially written"
    )
    # No stray temp file left behind on failure either.
    leftovers = list(lock_path.parent.glob(".ledger-tmp-*"))
    assert not leftovers, f"a failed write must clean up its own tempfile: {leftovers}"


def test_write_reaps_only_an_agebarred_ledger_tempfile(tmp_path: Path):
    """[M] round 9, class 5, CORRECTED round 10, class 1: a process SIGKILLed
    between `mkstemp()` and `os.replace()`/`os.unlink()` leaves a `.ledger-tmp-*`
    sibling that nothing ever reaps — it is not the ledger itself
    (`_read_worktree_ledger` never looks at it) and carries no ignore rule either,
    so it sits forever as `?? .fabrik/` in `git status` (`git clean -fdn` would
    remove it). Round 9's fix reaped ANY `.ledger-tmp-*` unconditionally — wrong:
    this process is not the only writer. `daily_refresh.sh` documents "the script
    has no internal lock" (only the cron wrapper takes an flock);
    `governance_sync_postcommit.sh`, fabrik-lib's `distribute_subagents.sh` and
    `watch_enforcement_changes.sh` take none at all — three hub sessions' post-
    commit hooks and the 06:00 cron CAN run this concurrently, and an unconditional
    reap deletes a CONCURRENT run's still-live tempfile out from under it (its
    `os.replace` then raises `FileNotFoundError`, swallowed by `except OSError:
    pass`, silently discarding that run's entire ledger write — no row, no WARN, no
    tally bump). A tempfile is stale BY AGE, never provably orphaned. Grader: a
    FRESH tempfile (mtime now, simulating a concurrent writer mid-swap) must
    SURVIVE; an OLD one (mtime backdated 2h, past any plausible in-flight swap)
    must be reaped.

    round 11, class 3: the age guard REOPENS the exact `?? .fabrik/` window this
    whole floor mechanism exists to close — for up to an hour after a SIGKILLed
    sync, its OWN surviving `.ledger-tmp-*` sits untracked AND unignored (`git
    clean -fdn` would name it), because nothing seeded an ignore rule for the
    tempfile's own glob shape. `.fabrik/.ledger-tmp-*` joins
    `_WORKTREE_FLOOR_PATTERNS` to close it — asserted here directly: after seeding
    the shared exclude, the surviving FRESH tempfile must leave `git status`
    clean, exactly like the ledger and lock files it sits beside."""
    repo = _init_repo(tmp_path / "proj")
    wt_dir = _add_worktree(repo, "agent-x")
    lock_path = wt_dir / sync._WORKTREE_LEDGER_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fresh = lock_path.parent / ".ledger-tmp-concurrent-writer-mid-swap"
    fresh.write_text("a concurrent process's own in-flight tempfile\n")

    stale = lock_path.parent / ".ledger-tmp-orphaned-by-a-prior-sigkill"
    stale.write_text("half-written garbage from a killed process, 2h ago\n")
    two_hours_ago = time.time() - 7200
    os.utime(stale, (two_hours_ago, two_hours_ago))

    assert fresh.exists() and stale.exists(), "guard: both fixtures exist before the write"

    sync._write_worktree_ledger(wt_dir, {"some/path.md": "some-hash"})

    assert fresh.exists(), (
        "a fresh (possibly concurrent-owned) tempfile must NEVER be reaped by age alone"
    )
    assert not stale.exists(), "a genuinely old .ledger-tmp-* sibling must still be reaped"
    assert json.loads(lock_path.read_text()) == {"some/path.md": "some-hash"}, (
        "the actual write must still succeed normally"
    )

    # round 11, class 3: the surviving fresh tempfile must not reopen the `?? .fabrik/`
    # window — a normal resync would have already seeded this, done explicitly here
    # since this test drives `_write_worktree_ledger` directly.
    assert sync._seed_worktree_secrets_exclude(repo) is True
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt_dir, capture_output=True, text=True
    ).stdout
    assert ".fabrik" not in status, (
        f"a surviving in-flight tempfile must never reopen the ?? .fabrik/ window: {status!r}"
    )

    fresh.unlink()  # clean up the surviving fixture so it doesn't leak into other assertions


def test_ledger_tempfile_reap_never_fires_under_dry_run(tmp_path: Path):
    """[L] round 10, class 7: `_write_worktree_ledger` (and its reap) is called only
    from inside `resync_worktree_artifacts`'s `if not dry_run:` branch — nothing
    inside `_write_worktree_ledger` itself is dry-run-aware, so this rests entirely
    on that one call-site guard. A planted stale orphan must survive a `--dry-run`
    resync untouched."""
    repo = _init_repo(tmp_path / "proj")
    wt_dir = _add_worktree(repo, "agent-x")
    lock_path = wt_dir / sync._WORKTREE_LEDGER_REL
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    orphan = lock_path.parent / ".ledger-tmp-orphaned-by-a-prior-sigkill"
    orphan.write_text("half-written garbage from a killed process, 2h ago\n")
    two_hours_ago = time.time() - 7200
    os.utime(orphan, (two_hours_ago, two_hours_ago))

    sync.resync_worktree_artifacts(repo, dry_run=True)

    assert orphan.exists(), "--dry-run must never reap anything — it writes nothing at all"


def test_partial_failure_does_not_wedge_the_file_it_already_wrote(
    tmp_path: Path, monkeypatch, capsys
):
    """[M] round 6, class 5 — the exact reproduction: disk holds a2's v2 content (the
    copy loop wrote it successfully) but, before this fix, the crashed pattern's
    entire `authored` map was discarded at the OUTER level, so the ledger kept a2's
    OLD row (hash of v1) forever — a hash matching neither the current disk content
    nor the current hub source. Every future run then WARNs "differs from the ledger
    record — edit preserved" on the sync's OWN write, wedged, since nothing ever
    updates that stale row (run3, run4, ... all repeat it). After the fix
    (`_sync_dir_into_worktree` isolates the exception to the ONE item that raised,
    not the whole function), a2's successful copy is recorded in the SAME run it
    happened, so run3 sees a2 as identical to the (unchanged) hub source and
    converges silently — never wedged."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "a.py").write_text("a v1\n")
    (repo / ".windsurf" / "rules" / "core" / "a2.py").write_text("a2 v1\n")
    wt_dir = _add_worktree(repo, "agent-x")

    sync.resync_worktree_artifacts(repo)  # run1: establish the ledger

    (repo / ".windsurf" / "rules" / "core" / "a.py").write_text("a v2\n")
    (repo / ".windsurf" / "rules" / "core" / "a2.py").write_text("a2 v2\n")

    # run2: the transient failure hits a2's OWN prune-loop `.exists()` check, AFTER
    # the copy phase has already refreshed a2 to v2 on disk.
    real_exists = Path.exists
    trigger = str((repo / ".windsurf" / "rules" / "core" / "a2.py").resolve())

    def flaky_exists(self, *a, **kw):
        if str(self) == trigger:
            raise OSError(13, "Permission denied (simulated transient failure)")
        return real_exists(self, *a, **kw)

    monkeypatch.setattr(Path, "exists", flaky_exists)
    try:
        sync.resync_worktree_artifacts(repo)
    finally:
        monkeypatch.undo()
    capsys.readouterr()

    # The fix under test: a2's ledger row must reflect what is ACTUALLY on disk
    # (v2) right after the crashed run — not stay wedged at the pre-crash v1 hash.
    ledger_after_crash = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    a2_path = wt_dir / ".windsurf" / "rules" / "core" / "a2.py"
    assert ledger_after_crash.get(".windsurf/rules/core/a2.py") == sync.compute_file_hash(
        a2_path
    ), "a2's own successful write must be recorded in the SAME run it happened, not discarded"

    # run3 and run4: the hub does not advance further — a2 must converge silently,
    # never re-warning about the sync's own write.
    for _ in range(2):
        sync.resync_worktree_artifacts(repo)
        out = capsys.readouterr().out
        assert "a2.py" not in out or "WARN" not in out, (
            f"a2.py must not be wedged into a permanent false WARN: {out}"
        )
    assert a2_path.read_text() == "a2 v2\n"


def test_zombie_ledger_row_is_reaped_when_both_source_and_file_are_gone(tmp_path: Path):
    """[M] round 7, class 10: a row whose MAIN CHECKOUT source has been retired AND
    whose worktree file the agent independently deleted — never via this sync's own
    prune, which only iterates EXISTING destination files and so never reaches a row
    like this at all — used to survive in the ledger forever: the exact "zombie" the
    pop-on-delete comment says must not exist, just reached by a different path. It
    asserts nothing true about this worktree anymore and must be reaped."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "a.py").write_text("a v1\n")
    (repo / ".windsurf" / "rules" / "core" / "retiring.py").write_text("retiring v1\n")
    wt_dir = _add_worktree(repo, "agent-x")

    sync.resync_worktree_artifacts(repo)  # run1: establish the ledger with both rows
    ledger1 = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())
    assert ".windsurf/rules/core/retiring.py" in ledger1, ledger1

    # The hub retires the file (source gone)...
    (repo / ".windsurf" / "rules" / "core" / "retiring.py").unlink()
    # ...and, independently, the agent deletes its OWN worktree copy directly — not
    # via this sync's prune, which never even looks at a path missing on both sides.
    (wt_dir / ".windsurf" / "rules" / "core" / "retiring.py").unlink()

    sync.resync_worktree_artifacts(repo)  # run2: must reap the now-zombie row
    ledger2 = json.loads((wt_dir / sync._WORKTREE_LEDGER_REL).read_text())

    assert ".windsurf/rules/core/retiring.py" not in ledger2, (
        f"a row with no live source and no worktree file must be reaped: {ledger2}"
    )
    assert ".windsurf/rules/core/a.py" in ledger2, "an unrelated live row must survive"


# --------------------------------------------------------------------------- #
# Left-alone (WARN) surfacing (round 3, class 2)                             #
# --------------------------------------------------------------------------- #


def test_warn_message_distinguishes_ledger_gap_from_genuine_edit(tmp_path: Path):
    """[M] round 5, class 2: measured live — 5 of 5 hash-sampled instances of "no
    ledger record, dest != source" on the first fleet run were stale copies from an
    OLDER branch, not agent edits (worktree == the main checkout at some earlier
    point, just not the freshly-advanced hub). The remedy differs from a genuine
    edit (nothing to do vs. an operator-driven ledger-gap bootstrap), so the message
    must say which case applies."""
    repo = _init_repo(tmp_path / "proj")

    # Case A: a ledger GAP — no row for this path at all, and the worktree's content
    # genuinely differs from the (advanced) hub — e.g. a stale copy from an older
    # branch, never an agent edit.
    (repo / "AGENTS.md").write_text("hub v2\n")
    wt_gap = _add_worktree(repo, "agent-gap")
    (wt_gap / "AGENTS.md").write_text("stale copy from an older branch\n")
    result_gap = sync._copy_into_worktree_safely(
        repo / "AGENTS.md",
        wt_gap / "AGENTS.md",
        dry_run=False,
        backup=False,
        previously_authored_rel={},
        project_rel="AGENTS.md",
        dst_root=wt_gap,
        project_dir=repo,
    )
    assert result_gap.action == "WARN"
    assert "no ledger record" in result_gap.reason, result_gap.reason

    # Case B: a genuine edit — the ledger HAS a row for this path, and the worktree's
    # copy no longer matches it.
    wt_edit = _add_worktree(repo, "agent-edit")
    sync.resync_worktree_artifacts(repo)  # establishes the ledger, agent-edit included
    (repo / "AGENTS.md").write_text("hub v3\n")
    (wt_edit / "AGENTS.md").write_text("agent's actual edit\n")
    ledger = sync._read_worktree_ledger(wt_edit)
    result_edit = sync._copy_into_worktree_safely(
        repo / "AGENTS.md",
        wt_edit / "AGENTS.md",
        dry_run=False,
        backup=False,
        previously_authored_rel=ledger,
        project_rel="AGENTS.md",
        dst_root=wt_edit,
        project_dir=repo,
    )
    assert result_edit.action == "WARN"
    assert "differs from the ledger record" in result_edit.reason, result_edit.reason
    assert result_edit.reason != result_gap.reason


def test_legacy_empty_sentinel_reads_as_no_ledger_record_on_the_copy_side(tmp_path: Path):
    """[M] round 7, class 6: `_read_worktree_ledger` folds a legacy list-shaped
    ledger (a bare list of paths, no hashes) into `{path: ""}` — a KNOWN path with
    NO verified hash, never proof of anything. The copy side tested this with
    `if recorded_hash is None`, under which `""` is NOT `None` and so fell through
    to "differs from the ledger record — edit preserved" — a claim of a provable
    drift the empty sentinel can never actually prove. The prune side already used
    `if not recorded_hash` for the same case; the copy side must match it exactly."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("hub v2\n")
    wt = _add_worktree(repo, "agent-legacy")
    (wt / "AGENTS.md").write_text("worktree content, differs from hub v2\n")

    result = sync._copy_into_worktree_safely(
        repo / "AGENTS.md",
        wt / "AGENTS.md",
        dry_run=False,
        backup=False,
        previously_authored_rel={"AGENTS.md": ""},  # the legacy sentinel, not a real hash
        project_rel="AGENTS.md",
        dst_root=wt,
        project_dir=repo,
    )
    assert result.action == "WARN"
    assert "no ledger record" in result.reason, result.reason
    assert "differs from the ledger record" not in result.reason, result.reason


@pytest.mark.parametrize("mtime_offset", [3600, -3600], ids=["newer", "older"])
def test_worktree_leftalone_warning_is_surfaced_and_tallied(
    tmp_path: Path, capsys, mtime_offset: float
):
    """[M] round 3, class 2, strengthened in round 4 (class 2): a locally-modified
    worktree file left alone must not be silently discarded — surfaced in the output
    and counted in the tally's warnings, for BOTH the single-file leg and
    (separately) under --dry-run. Parametrized OLDER (-3600) as well as newer (+3600)
    — the production shape is an agent edit OLDER than a just-refreshed hub source
    (a governance commit propagates a fresh mtime into the main checkout), which the
    old mtime-based tiebreak did NOT protect; only the ledger-hash gate does, for
    either sign."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("new content\n")
    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / "AGENTS.md").write_text("worktree-local edit\n")
    _touch_mtime(wt_dir / "AGENTS.md", mtime_offset)

    before = sync._WORKTREE_TALLY["warnings"]
    sync.resync_worktree_artifacts(repo, force=False)
    out = capsys.readouterr().out
    after = sync._WORKTREE_TALLY["warnings"]

    assert "WARN" in out, out
    assert after - before >= 1, "the left-alone file must be counted in the tally"
    assert (wt_dir / "AGENTS.md").read_text() == "worktree-local edit\n", (
        "the edit must survive regardless of its mtime relative to the source"
    )

    # And under --dry-run too — a second worktree, same scenario.
    wt_dir2 = _add_worktree(repo, "agent-y")
    (wt_dir2 / "AGENTS.md").write_text("another local edit\n")
    _touch_mtime(wt_dir2 / "AGENTS.md", mtime_offset)

    sync.resync_worktree_artifacts(repo, dry_run=True)
    out2 = capsys.readouterr().out
    assert "WARN" in out2, out2


@pytest.mark.parametrize("mtime_offset", [3600, -3600], ids=["newer", "older"])
def test_worktree_directory_leg_surfaces_leftalone_warning(
    tmp_path: Path, capsys, mtime_offset: float
):
    """[M] round 3, class 2, strengthened in round 4 (class 2): the DIRECTORY leg
    must surface a left-alone WARN too, not just the single-file leg — parametrized
    OLDER (-3600) as well as newer (+3600), the same production-shape concern as
    above."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "x.md").write_text("new rule\n")

    wt_dir = _add_worktree(repo, "agent-x")
    (wt_dir / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (wt_dir / ".windsurf" / "rules" / "core" / "x.md").write_text("worktree-local edit\n")
    _touch_mtime(wt_dir / ".windsurf" / "rules" / "core" / "x.md", mtime_offset)

    before = sync._WORKTREE_TALLY["warnings"]
    sync.resync_worktree_artifacts(repo, force=False)
    out = capsys.readouterr().out
    after = sync._WORKTREE_TALLY["warnings"]

    assert "WARN" in out, out
    assert after - before >= 1
    assert (wt_dir / ".windsurf" / "rules" / "core" / "x.md").read_text() == "worktree-local edit\n"


# --------------------------------------------------------------------------- #
# Production-shape reproduction (round 4, class 1)                           #
# --------------------------------------------------------------------------- #


def test_production_shape_agent_edit_older_than_refreshed_hub_source_survives(
    tmp_path: Path, capsys
):
    """[H] round 4, class 1 — the exact production reproduction. Before this fix:
    an agent edit stamped 30 minutes old, against a hub copy whose mtime was just
    refreshed by `shutil.copy2` (as the main-checkout leg does on every governance
    commit) followed immediately by `--force` (as
    `scripts/governance_sync_postcommit.sh` runs), silently overwrote the agent's
    edit — "Re-synced 8 file(s)", no WARN, no backup, and the clobbered path then
    entered the ledger as sync-authored, identical with or without `--force` (mtime
    was the only gate on both paths, and the agent's file is essentially always
    OLDER than a source whose mtime a governance commit just reset). After the fix,
    the ledger-hash gate — never mtime — decides, so the edit survives regardless of
    which file it landed on."""
    repo = _init_repo(tmp_path / "proj")
    filenames = [
        "AGENTS.md",
        "agents-fabrik.md",
        "agents-fabrik-core.md",
        "AGENTS-compact.md",
        "opencode.json",
        ".windsurfrules",
        "CLAUDE.md",
        "PORTS.md",
    ]
    for name in filenames:
        (repo / name).write_text(f"{name} hub v1\n")

    wt_dir = _add_worktree(repo, "agent-x")
    sync.resync_worktree_artifacts(repo)  # establishes the ledger for all 8 files

    # The hub advances on every file (a governance commit), refreshing each source's
    # mtime to "now" — exactly what a real `shutil.copy2` propagation does.
    for name in filenames:
        (repo / name).write_text(f"{name} hub v2\n")

    # The agent edited exactly ONE of the eight files, 30 minutes ago.
    edited = "CLAUDE.md"
    (wt_dir / edited).write_text("agent's in-flight edit, 30 minutes old\n")
    _touch_mtime(wt_dir / edited, -1800)

    sync.resync_worktree_artifacts(repo, force=True)  # the production wrapper's own flag
    out = capsys.readouterr().out

    agent_edit_lost = (wt_dir / edited).read_text() != "agent's in-flight edit, 30 minutes old\n"
    assert not agent_edit_lost, f"AGENT EDIT LOST: {agent_edit_lost}"
    assert "WARN" in out, out
    # The other seven, genuinely untouched by the agent, still refresh normally.
    for name in filenames:
        if name == edited:
            continue
        assert (wt_dir / name).read_text() == f"{name} hub v2\n"


# --------------------------------------------------------------------------- #
# --backup / --force threading (class 4)                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mtime_offset", [3600, -3600], ids=["newer", "older"])
def test_worktree_force_never_overwrites_a_modified_file_but_does_overwrite_unmodified(
    tmp_path: Path, mtime_offset: float
):
    """[M] round 3, class 2 — ORCHESTRATOR-BINDING DECISION supersedes round 1/2's
    "--force always overwrites the worktree copy": worktrees are live agent trees, and
    production runs `--force` on every governance commit — a blanket overwrite would
    clobber in-flight edits fleet-wide with no backup. `--force` may overwrite a
    worktree file ONLY when it is byte-identical to what THIS worktree's own ledger
    recorded the sync writing there last time. A file the agent has actually edited is
    WARN'd and PRESERVED even under `--force`; a stale-but-UNMODIFIED file (mtime
    drifted, content did not) is still safely overwritten.

    Parametrized OLDER (-3600) as well as newer (+3600), round 4 class 2: every prior
    version of this test stamped the modified copy +3600s only — exactly the mtime
    region `sync_single_file`'s own tiebreak already protected, so it proved nothing
    about the ledger-hash gate itself (flipping the sign alone made the OLD
    implementation's test pass for the wrong reason). Production's actual shape is
    the OLDER case: a governance commit refreshes the hub file's mtime, which
    `copy2` propagates into the main checkout, so the agent's own edit — however
    recent — is almost always older than the freshly-synced source (round 4, class 1;
    measured live: 106 of 19,256 pairs `exists_differ_older`, 0 mtime-protected)."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("modified-file v1\n")
    (repo / "CLAUDE.md").write_text("unmodified-file v1\n")
    wt_dir = _add_worktree(repo, "agent-x")

    # Establish the ledger for both files with a normal (non-forced) resync.
    sync.resync_worktree_artifacts(repo, force=False)
    assert (wt_dir / "AGENTS.md").read_text() == "modified-file v1\n"
    assert (wt_dir / "CLAUDE.md").read_text() == "unmodified-file v1\n"

    # Main checkout advances on both files.
    (repo / "AGENTS.md").write_text("modified-file v2\n")
    (repo / "CLAUDE.md").write_text("unmodified-file v2\n")

    # AGENTS.md: the agent actually edited it in the worktree (drifted from the ledger).
    (wt_dir / "AGENTS.md").write_text("agent's in-flight edit\n")
    _touch_mtime(wt_dir / "AGENTS.md", mtime_offset)
    # CLAUDE.md: untouched by the agent — content still matches exactly what the
    # ledger recorded — but its mtime drifts too (e.g. a checkout/rebase touching
    # mtimes without changing content).
    _touch_mtime(wt_dir / "CLAUDE.md", mtime_offset)

    sync.resync_worktree_artifacts(repo, force=True)

    assert (wt_dir / "AGENTS.md").read_text() == "agent's in-flight edit\n", (
        "--force must NEVER clobber a file the agent has actually modified"
    )
    assert (wt_dir / "CLAUDE.md").read_text() == "unmodified-file v2\n", (
        "--force MUST still overwrite a file that is unmodified since the ledger recorded it"
    )


def test_worktree_single_file_leg_threads_backup(tmp_path: Path):
    """class 4 mutation-kill, CORRECTED in round 4 (class 1) and round 6 (class 2): a
    modified-but-older worktree copy is no longer "overwritten with a backup" —
    round 4 preserves it unconditionally (mtime plays no role at all). `backup=True`
    is proven instead on the SAFE refresh path: a worktree copy the ledger proves is
    unmodified since the sync wrote it still gets backed up before being refreshed to
    the hub's new content — and round 6 relocates that backup OUTSIDE the worktree
    tree (`.fabrik/backups/worktrees/<name>/…`), same as the prune path, instead of
    the bare `create_backup` litter that used to land beside the file."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("v1\n")
    wt_dir = _add_worktree(repo, "agent-x")

    sync.resync_worktree_artifacts(repo)  # establishes the ledger: AGENTS.md -> hash(v1)
    assert (wt_dir / "AGENTS.md").read_text() == "v1\n"

    (repo / "AGENTS.md").write_text("v2\n")  # hub advances; worktree copy untouched

    sync.resync_worktree_artifacts(repo, backup=True)

    assert not list(wt_dir.glob("AGENTS.md.backup.*")), (
        "backup litter must never land inside the worktree's own tree"
    )
    backup_root = repo / ".fabrik" / "backups" / "worktrees" / "agent-x"
    backups = list(backup_root.glob("**/AGENTS.md.backup.*"))
    assert backups, "backup=True on the single-file leg must produce a .backup.* file"
    assert backups[0].read_text() == "v1\n"
    assert (wt_dir / "AGENTS.md").read_text() == "v2\n"


@pytest.mark.parametrize("mtime_offset", [3600, -3600], ids=["newer", "older"])
def test_worktree_directory_leg_force_never_overwrites_a_modified_file(
    tmp_path: Path, mtime_offset: float
):
    """[M] round 3, class 2, strengthened in round 4 (class 2): the DIRECTORY leg
    (`_sync_dir_into_worktree`) must honor the SAME `--force` safety gate as the
    single-file leg — supersedes round 1/2's "always overwrite" contract for this leg
    too. Parametrized OLDER (-3600) as well as newer (+3600): the production shape is
    the OLDER case (see the single-file version of this test for the measured live
    numbers)."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "modified.md").write_text("v1\n")
    (repo / ".windsurf" / "rules" / "core" / "unmodified.md").write_text("v1\n")

    wt_dir = _add_worktree(repo, "agent-x")
    sync.resync_worktree_artifacts(repo, force=False)  # establish the ledger

    (repo / ".windsurf" / "rules" / "core" / "modified.md").write_text("v2\n")
    (repo / ".windsurf" / "rules" / "core" / "unmodified.md").write_text("v2\n")

    (wt_dir / ".windsurf" / "rules" / "core" / "modified.md").write_text("agent's edit\n")
    _touch_mtime(wt_dir / ".windsurf" / "rules" / "core" / "modified.md", mtime_offset)
    _touch_mtime(wt_dir / ".windsurf" / "rules" / "core" / "unmodified.md", mtime_offset)

    sync.resync_worktree_artifacts(repo, force=True)

    assert (
        wt_dir / ".windsurf" / "rules" / "core" / "modified.md"
    ).read_text() == "agent's edit\n", "--force must never clobber a modified worktree file"
    assert (wt_dir / ".windsurf" / "rules" / "core" / "unmodified.md").read_text() == "v2\n", (
        "--force must still overwrite a file unmodified since the ledger"
    )


def test_sync_dir_into_worktree_has_no_dead_force_parameter():
    """[L] round 5, class 6: `force` was threaded through `resync_worktree_artifacts`
    -> `_sync_dir_into_worktree` but never referenced in the latter's body — dead
    weight, dropped. The PUBLIC `resync_worktree_artifacts` signature keeps `force`
    (every other copy leg in this script accepts it, so callers need not special-case
    the worktree legs), but the private helper must not carry it too."""
    import inspect

    assert "force" not in inspect.signature(sync._sync_dir_into_worktree).parameters
    assert "force" in inspect.signature(sync.resync_worktree_artifacts).parameters


def test_worktree_directory_leg_threads_backup(tmp_path: Path):
    """class 4 mutation-kill, CORRECTED in round 4 (class 1) and round 6 (class 2):
    same shift as the single-file leg above — backup is proven on the SAFE
    (ledger-verified-unmodified) refresh path, not on an overwrite of a modified file
    (which round 4 preserves unconditionally), and lands OUTSIDE the worktree tree
    (round 6)."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
    (repo / ".windsurf" / "rules" / "core" / "x.md").write_text("v1\n")

    wt_dir = _add_worktree(repo, "agent-x")
    sync.resync_worktree_artifacts(repo)  # establishes the ledger
    assert (wt_dir / ".windsurf" / "rules" / "core" / "x.md").read_text() == "v1\n"

    (repo / ".windsurf" / "rules" / "core" / "x.md").write_text("v2\n")

    sync.resync_worktree_artifacts(repo, backup=True)

    assert not list((wt_dir / ".windsurf" / "rules" / "core").glob("x.md.backup.*")), (
        "backup litter must never land inside the worktree's own tree"
    )
    backup_root = repo / ".fabrik" / "backups" / "worktrees" / "agent-x"
    backups = list(backup_root.glob("**/x.md.backup.*"))
    assert backups, "backup=True on the directory leg must produce a .backup.* file"
    assert backups[0].read_text() == "v1\n"
    assert (wt_dir / ".windsurf" / "rules" / "core" / "x.md").read_text() == "v2\n"


def test_sync_scripts_to_project_forwards_backup_and_force_to_resync(tmp_path, monkeypatch):
    """class 4 mutation-kill: the call site (`sync_scripts_to_project`) must pass its
    OWN backup/force through to resync_worktree_artifacts, not silently drop them."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    # Already-covered .gitignore: sidesteps the unrelated safety-floor repair path
    # (which backs up a .gitignore that, absent one, does not yet exist) — irrelevant
    # to what this test is proving.
    (repo / ".gitignore").write_text(".env\n.venv/\n__pycache__/\n")
    _run(["git", "add", "AGENTS.md", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)

    calls = []
    original = sync.resync_worktree_artifacts

    def spy(project_dir, dry_run=False, *, backup=False, force=False):
        calls.append({"dry_run": dry_run, "backup": backup, "force": force})
        return original(project_dir, dry_run, backup=backup, force=force)

    monkeypatch.setattr(sync, "resync_worktree_artifacts", spy)

    result = sync.sync_scripts_to_project(repo, dry_run=False, backup=True, force=True)
    assert result.success, result.message

    assert calls, "sync_scripts_to_project must call resync_worktree_artifacts"
    assert calls[-1] == {"dry_run": False, "backup": True, "force": True}


# --------------------------------------------------------------------------- #
# Secrets floor (classes 1, 2, 3, 7)                                          #
# --------------------------------------------------------------------------- #


def test_worktree_on_old_branch_gets_secrets_protected_via_shared_exclude(tmp_path: Path):
    """SECURITY (class 1): a linked worktree's own tracked .gitignore comes from
    whatever branch it has checked out — often one cut BEFORE .mcp.json/.env
    protection existed. resync_worktree_artifacts must never copy a secret into a
    worktree that cannot prove it is ignored; it seeds the shared
    git-common-dir/info/exclude first so every worktree (old branch included) inherits
    the rule regardless of what its own .gitignore says."""
    repo = _init_repo(tmp_path / "proj")
    # OLD .gitignore: no protection for .mcp.json/.env at all — the state a worktree
    # branch cut before the protection existed would carry.
    (repo / ".gitignore").write_text("*.pyc\n")
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "old gitignore, no secrets rule"], repo)
    old_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    wt_dir = _add_worktree(repo, "agent-old", ref=old_sha)

    # Main checkout moves on: today's .gitignore protects the secrets.
    (repo / ".gitignore").write_text("*.pyc\n.mcp.json\n.env\n")
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "protect secrets"], repo)
    (repo / ".mcp.json").write_text('{"key": "sk-live-abc123"}\n')
    (repo / ".env").write_text("API_KEY=sk-live-xyz\n")

    # Guard: the worktree's OWN checked-out .gitignore really does not cover it yet.
    assert not sync._worktree_ignores(wt_dir, ".mcp.json")
    assert not sync._worktree_ignores(wt_dir, ".env")

    sync.resync_worktree_artifacts(repo)

    assert sync._worktree_ignores(wt_dir, ".mcp.json"), "the shared exclude must now cover it"
    assert sync._worktree_ignores(wt_dir, ".env")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt_dir, capture_output=True, text=True
    ).stdout
    assert ".mcp.json" not in status, status
    assert ".env" not in status, status
    # And the secret actually made it in, protected — never silently dropped.
    assert (wt_dir / ".mcp.json").read_text() == '{"key": "sk-live-abc123"}\n'
    assert (wt_dir / ".env").read_text() == "API_KEY=sk-live-xyz\n"


def test_worktree_on_old_branch_ignores_its_own_ledger_after_one_sync(tmp_path: Path):
    """[M] round 8, class 3: the round-7 fix added `.fabrik/worktree-synced.lock` to
    the MAIN checkout's tracked `.gitignore` block, but a linked worktree evaluates
    its OWN branch's copy of that file — a worktree cut from a branch older than that
    fix never has it. Measured live: 0 of 84 worktrees ignored the ledger (`?? .fabrik/`,
    `git clean -fdn` would remove it). The shared `git-common-dir/info/exclude` is the
    only mechanism that reaches every worktree regardless of branch — the same one
    already used for `.env`/`.mcp.json` — so the ledger must be seeded there too, and
    a SINGLE sync (which writes the ledger for the first time) must leave it ignored,
    exactly like the old-branch secrets case above."""
    repo = _init_repo(tmp_path / "proj")
    # OLD .gitignore — cut before even the ORIGINAL secrets protection existed, let
    # alone the round-7 ledger-ignore fix.
    (repo / ".gitignore").write_text("*.pyc\n")
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "old gitignore"], repo)
    old_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    wt_dir = _add_worktree(repo, "agent-old", ref=old_sha)

    # Guard: the worktree's OWN checked-out .gitignore really does not cover the
    # ledger path (it never mentions it at all).
    assert not sync._worktree_ignores(wt_dir, sync._WORKTREE_LEDGER_REL)

    sync.resync_worktree_artifacts(repo)  # one sync — writes the ledger for the first time

    assert (wt_dir / sync._WORKTREE_LEDGER_REL).exists(), "the sync must have written the ledger"
    assert sync._worktree_ignores(wt_dir, sync._WORKTREE_LEDGER_REL), (
        "the shared exclude must cover the ledger even on an old branch"
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt_dir, capture_output=True, text=True
    ).stdout
    assert ".fabrik" not in status, status


def test_repo_seeded_with_the_old_marker_gains_the_new_pattern(tmp_path: Path, capsys):
    """[M] round 8, class 3: the marker's mere PRESENCE used to short-circuit
    `_seed_worktree_secrets_exclude` to "already seeded, nothing to do" — correct the
    day only `.env`/`.mcp.json` existed, but it means a repo seeded BEFORE a later
    pattern (`_WORKTREE_LEDGER_REL`) was added to `needed` would never pick it up on
    any FUTURE sync, since the marker itself never changes and so never re-fires.
    Grader: hand-seed a repo with the OLD (pre-round-8) block — marker, secrets,
    END, nothing else — and assert one more sync appends the missing ledger pattern
    without duplicating the marker or END lines."""
    repo = _init_repo(tmp_path / "proj")
    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], repo).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    exclude_path = common_dir / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    old_block = "\n".join(
        [
            sync._WORKTREE_EXCLUDE_MARKER,
            "# old block, pre-round-8 — no ledger pattern",
            ".env",
            ".mcp.json",
            sync._WORKTREE_EXCLUDE_END,
            "",
        ]
    )
    exclude_path.write_text(old_block)

    assert sync._WORKTREE_LEDGER_REL not in old_block.splitlines(), (
        "guard: the fixture really is missing the new pattern"
    )

    # round 9, class 2: the round-8 --dry-run parity mirror
    # (`_worktree_secrets_exclude_already_seeded`'s per-pattern `all(...)` check)
    # shipped with no grader — replacing it with a bare `return True` ("marker
    # present, always done") left the suite green. On this exact legacy-marker
    # fixture, --dry-run must still say "Would seed" — a real run is about to
    # write an upgrade, so silence here would be the class-2 dry/real parity
    # break one level down.
    assert sync._worktree_secrets_exclude_already_seeded(repo) is False, (
        "a legacy-marker repo missing a needed pattern is NOT fully seeded"
    )
    sync.resync_worktree_artifacts(repo, dry_run=True)
    dry_run_out = capsys.readouterr().out
    assert "Would seed" in dry_run_out, dry_run_out
    # round 10, class 8: a bare "Would seed" substring is too weak to catch a
    # regression of the round-9 wording — assert the actual missing pattern is
    # named AND the "upgrade" phrasing survives (never claiming "first real run"
    # for a repo that is already marker-seeded).
    assert sync._WORKTREE_LEDGER_REL in dry_run_out, dry_run_out
    assert "already-seeded repo missing a newer pattern" in dry_run_out, dry_run_out

    ok = sync._seed_worktree_secrets_exclude(repo)
    assert ok is True

    updated = exclude_path.read_text()
    assert sync._WORKTREE_LEDGER_REL in updated.splitlines(), (
        "the missing pattern must be appended on the next seed"
    )
    # Never duplicated — the marker and END lines still appear exactly once each.
    assert updated.count(sync._WORKTREE_EXCLUDE_MARKER) == 1, updated
    assert updated.count(sync._WORKTREE_EXCLUDE_END) == 1, updated

    # And idempotent from here: a further call changes nothing more.
    before = exclude_path.read_text()
    ok2 = sync._seed_worktree_secrets_exclude(repo)
    assert ok2 is True
    assert exclude_path.read_text() == before, "once every pattern is present, nothing to add"


def test_two_successive_upgrades_get_two_distinct_dated_headers(tmp_path: Path, monkeypatch):
    """[M] round 11, class 1: round 10 dropped the hardcoded "(round 8)" from the
    upgrade header to stop every future upgrade from wearing a stale round number —
    but the replacement was UNDATED and UNVERSIONED, which is the exact same defect
    from the other side: two SEPARATE upgrades on one repo (this pattern added
    today, a DIFFERENT pattern added later) write byte-IDENTICAL header text, so
    nothing distinguishes them — reproduced: two successive upgrades on one fixture
    produced 2 occurrences of the SAME line. Also makes
    `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md`'s "a DATED addendum" claim true —
    the code never wrote a date before this. Grader: two upgrades, two different
    (monkeypatched) dates, must produce two DISTINCT header lines."""
    repo = _init_repo(tmp_path / "proj")
    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], repo).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    exclude_path = common_dir / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    # An OLD (pre-round-8) block: marker + only the two legacy secrets.
    old_block = "\n".join(
        [
            sync._WORKTREE_EXCLUDE_MARKER,
            "# old block, pre-round-8 — no ledger pattern, no lock pattern",
            ".env",
            ".mcp.json",
            sync._WORKTREE_EXCLUDE_END,
            "",
        ]
    )
    exclude_path.write_text(old_block)

    import datetime as datetime_mod

    class _FixedDatetime(datetime_mod.datetime):
        _fixed = datetime_mod.datetime(2026, 1, 1)

        @classmethod
        def now(cls, tz=None):
            return cls._fixed

    monkeypatch.setattr(sync, "datetime", _FixedDatetime)

    # First upgrade — today's real floor (adds whatever this fixture is missing).
    _FixedDatetime._fixed = datetime_mod.datetime(2026, 1, 1)
    ok1 = sync._seed_worktree_secrets_exclude(repo)
    assert ok1 is True

    # Second upgrade, a DIFFERENT day — simulate "a future pattern added after this
    # one" by widening the floor tuple to include a pattern the file genuinely does
    # not have yet.
    monkeypatch.setattr(
        sync,
        "_WORKTREE_FLOOR_PATTERNS",
        (*sync._WORKTREE_FLOOR_PATTERNS, ".fabrik/a-future-pattern"),
    )
    _FixedDatetime._fixed = datetime_mod.datetime(2026, 6, 15)
    ok2 = sync._seed_worktree_secrets_exclude(repo)
    assert ok2 is True

    content = exclude_path.read_text()
    headers = [
        line for line in content.splitlines() if line.startswith("# Fabrik worktree floor upgrade")
    ]
    assert len(headers) == 2, f"two separate upgrades must each get their own header: {headers}"
    assert headers[0] != headers[1], (
        f"two upgrades on different dates must never look identical: {headers}"
    )
    assert "2026-01-01" in headers[0], headers[0]
    assert "2026-06-15" in headers[1], headers[1]


def test_missing_pattern_append_never_welds_onto_the_last_existing_line(tmp_path: Path):
    """[L] round 9, class 4: the missing-pattern append's newline guard
    (`prefix = "" if existing.endswith("\\n") else "\\n"`) shipped ungraded. A
    legacy-marker repo whose exclude file's actual last byte is NOT a newline
    (e.g. a user's own pattern appended after Fabrik's block, saved by an editor
    that doesn't force a trailing newline) would, under the mutant (no guard, always
    `prefix=""`), get the addendum WELDED onto that last line — `*.tmp# Fabrik
    worktree floor upgrade …` is a single corrupted gitignore pattern, no longer
    matching `*.tmp` at all (`git check-ignore a.tmp` goes from ignored to NOT
    ignored). The guard must keep the user's own last pattern on its own line and
    genuinely still ignore what it always ignored."""
    repo = _init_repo(tmp_path / "proj")
    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], repo).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    exclude_path = common_dir / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    # The OLD (pre-round-8) Fabrik block, PLUS a user's own pattern appended after
    # it — and, load-bearing for this grader, NO trailing newline at all.
    old_block_no_trailing_newline = "\n".join(
        [
            sync._WORKTREE_EXCLUDE_MARKER,
            "# old block, pre-round-8 — no ledger pattern",
            ".env",
            ".mcp.json",
            sync._WORKTREE_EXCLUDE_END,
            "*.tmp",
        ]
    )
    assert not old_block_no_trailing_newline.endswith("\n"), (
        "guard: the fixture really has no trailing newline"
    )
    exclude_path.write_text(old_block_no_trailing_newline)

    # Guard: the user's own pattern really does work before any append.
    assert sync._worktree_ignores(repo, "a.tmp"), "guard: the fixture's own rule must work first"

    ok = sync._seed_worktree_secrets_exclude(repo)
    assert ok is True

    updated = exclude_path.read_text()
    assert "*.tmp" in updated.splitlines(), (
        f"the user's own pattern must survive as its own line, never welded: {updated!r}"
    )
    assert sync._WORKTREE_LEDGER_REL in updated.splitlines(), (
        "the missing pattern must still be appended"
    )
    # The real assertion: git itself must still honor the un-welded rule.
    assert sync._worktree_ignores(repo, "a.tmp"), (
        f"a welded line would silently stop matching *.tmp: {updated!r}"
    )


def test_tracked_secret_gets_one_note_never_a_perworktree_warning(tmp_path: Path, capsys):
    """class 2: a secret already committed to a worktree's own branch is unfixable by
    an ignore-rule fix — `git check-ignore` never reports a tracked path as ignored,
    however correct the rule is. Must be a ONE-LINE NOTE per project, never a
    per-worktree actionable WARN (measured live: trade-intelligence fired 23
    unfixable warnings, one per worktree, every sync — the fix must not repeat that)."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".gitignore").write_text("*.pyc\n")
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "no secrets rule"], repo)
    (repo / ".mcp.json").write_text('{"key": "sk-live"}\n')

    for name in ("agent-1", "agent-2"):
        wt = _add_worktree(repo, name)
        (wt / ".mcp.json").write_text('{"key": "sk-live-committed"}\n')
        _run(["git", "add", ".mcp.json"], wt)
        _run(["git", "commit", "-q", "-m", "oops, committed the key"], wt)

    sync.resync_worktree_artifacts(repo)

    out = capsys.readouterr().out
    assert out.count("NOTE") == 1, out
    assert "⚠️" not in out, (
        "a tracked secret is unfixable by ignore-rule advice — must never be a WARN"
    )


def test_secret_status_classifies_ignored_tracked_and_unprotected(tmp_path: Path):
    """Unit-level proof of the three-way classification `_worktree_secret_status`
    reuses from `_uncovered_essentials`'s tracked-vs-no-rule split."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".gitignore").write_text("*.pyc\n")
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "no rule"], repo)

    wt_unprotected = _add_worktree(repo, "agent-unprotected")
    (wt_unprotected / "secret.txt").write_text("x\n")
    assert sync._worktree_secret_status(wt_unprotected, "secret.txt") == "unprotected"

    wt_tracked = _add_worktree(repo, "agent-tracked")
    (wt_tracked / "secret.txt").write_text("x\n")
    _run(["git", "add", "secret.txt"], wt_tracked)
    _run(["git", "commit", "-q", "-m", "committed by mistake"], wt_tracked)
    assert sync._worktree_secret_status(wt_tracked, "secret.txt") == "tracked"

    wt_ignored = _add_worktree(repo, "agent-ignored")
    (wt_ignored / ".gitignore").write_text("secret.txt\n")
    (wt_ignored / "secret.txt").write_text("x\n")
    assert sync._worktree_secret_status(wt_ignored, "secret.txt") == "ignored"


def test_dry_run_secret_classification_simulates_the_post_seed_state(tmp_path: Path, capsys):
    """[M] round 3 (native-finder), class 4: `--dry-run` skips
    `_seed_worktree_secrets_exclude` (it must never write) — reading pre-seed reality
    would report `.mcp.json` as unfixably unprotected on EVERY dry-run sweep, when a
    real run would have already fixed it by seeding first. `_worktree_secret_status`
    must classify as if the seed had already been applied (read-only, via a scratch
    `core.excludesFile` overlay) so the preview matches what a real run actually does:
    no warning, and the copy is previewed as it would happen for real."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".gitignore").write_text("*.pyc\n")  # no rule for .mcp.json yet
    _run(["git", "add", ".gitignore"], repo)
    _run(["git", "commit", "-q", "-m", "no secrets rule"], repo)
    (repo / ".mcp.json").write_text('{"key": "sk-live"}\n')

    wt_dir = _add_worktree(repo, "agent-x")
    assert not sync._worktree_ignores(wt_dir, ".mcp.json"), "guard: genuinely unignored pre-seed"

    # Unit level: the dry-run classification must already say "ignored" — matching
    # what a real seed would produce — without writing anything.
    assert sync._worktree_secret_status(wt_dir, ".mcp.json", dry_run=True) == "ignored"
    assert not sync._worktree_ignores(wt_dir, ".mcp.json"), (
        "the dry-run classification must never actually seed info/exclude"
    )

    # End to end: resync_worktree_artifacts under --dry-run must not warn about it,
    # and must preview the copy.
    sync.resync_worktree_artifacts(repo, dry_run=True)
    out = capsys.readouterr().out
    assert ".mcp.json" not in out or "NOT ignored" not in out, out
    assert not (wt_dir / ".mcp.json").exists(), "--dry-run must never actually write the secret"


def test_secrets_exclude_seed_is_idempotent(tmp_path: Path):
    repo = _init_repo(tmp_path / "proj")
    sync._seed_worktree_secrets_exclude(repo)
    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], repo).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    exclude_path = common_dir / "info" / "exclude"
    first = exclude_path.read_text()
    sync._seed_worktree_secrets_exclude(repo)  # second call
    second = exclude_path.read_text()
    assert first == second, "a repeat seed must never duplicate the block"
    assert first.count(sync._WORKTREE_EXCLUDE_MARKER) == 1


def test_secrets_exclude_is_seeded_even_with_no_worktrees_today(tmp_path: Path):
    """class 7: the secrets floor must be seeded on every real run, even for a project
    with zero worktrees today — a FUTURE worktree inherits protection immediately
    instead of waiting for the sync to happen to run again after it is created."""
    repo = _init_repo(tmp_path / "proj")

    count = sync.resync_worktree_artifacts(repo)
    assert count == 0

    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], repo).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    exclude_path = common_dir / "info" / "exclude"
    assert exclude_path.exists(), "the exclude file must exist even with no worktrees"
    assert sync._WORKTREE_EXCLUDE_MARKER in exclude_path.read_text()


def test_seed_failure_reports_the_real_cause_not_the_worktree_gitignore(tmp_path: Path, capsys):
    """[M] round 5, class 3: when `info/exclude` cannot be written (e.g. the
    containing `.git/info/` directory is not writable), the secret is correctly
    withheld, but the seeder must REPORT its failure and the WARN must name the
    shared floor — never tell the operator to fix the worktree's branch `.gitignore`,
    which cannot help (the sibling of the c22bd91c safety-floor class: naming the
    wrong cause sends the fix where it cannot land)."""
    repo = _init_repo(tmp_path / "proj")
    (repo / ".mcp.json").write_text('{"key": "sk-live"}\n')
    _add_worktree(repo, "agent-x")

    common_dir = Path(_run(["git", "rev-parse", "--git-common-dir"], repo).stdout.strip())
    if not common_dir.is_absolute():
        common_dir = repo / common_dir
    info_dir = common_dir / "info"
    info_dir.mkdir(parents=True, exist_ok=True)
    exclude_path = info_dir / "exclude"
    # `git init` already creates this file, so appending to it needs only the FILE's
    # own write bit, not the directory's — mode 444 on the file is what actually
    # blocks the write (mode 555 on the directory alone would not: appending to an
    # existing inode never needs directory-write permission).
    exclude_path.touch(exist_ok=True)
    exclude_path.chmod(0o444)
    info_dir.chmod(0o555)
    try:
        ok = sync._seed_worktree_secrets_exclude(repo)
        assert ok is False, "the seeder must report failure, not silently swallow it"

        sync.resync_worktree_artifacts(repo)
        out = capsys.readouterr().out
    finally:
        info_dir.chmod(0o755)  # restore so tmp_path cleanup can remove the tree
        exclude_path.chmod(0o644)

    assert "could not be written (permission)" in out, out
    assert "checked-out branch" not in out, (
        "must never point at the worktree's own .gitignore — that is the wrong cause"
    )


def test_non_git_directory_never_warns_the_wrong_cause_on_a_real_run(tmp_path: Path, capsys):
    """[M] round 8, class 2: `_seed_worktree_secrets_exclude` returns False for a
    NON-GIT `/opt` directory (`git rev-parse --git-common-dir` fails exactly like a
    real permission failure would), and the real-run leg used to treat any `False`
    as "could not be written (permission)" — measured live, 4 of 45 projects WARNed
    this on EVERY real sync, the same 4 `--dry-run` was already silent for (a
    dry/real parity break on top of the wrong cause: there is no floor to write and
    no worktree can ever exist there). Guarded on `_is_git_repo`, matching
    `seed_git_workflow_config` and `_project_worktree_dirs` — a non-git directory is
    silent on BOTH `--dry-run` and a real run now; a real, git-backed permission
    failure (the sibling test above) still WARNs."""
    non_git = tmp_path / "not-a-repo"
    non_git.mkdir()
    (non_git / "AGENTS.md").write_text("agents doc\n")

    assert sync._is_git_repo(non_git) is False, "guard: this must genuinely not be a repo"

    count = sync.resync_worktree_artifacts(non_git)  # real run, not --dry-run
    out = capsys.readouterr().out

    assert count == 0
    assert "could not be written" not in out, out
    assert "info/exclude" not in out, out


def test_dry_run_discloses_the_secrets_exclude_seed(tmp_path: Path, capsys):
    """[M] round 4, class 4: `--dry-run` never disclosed the `git-common-dir/info/
    exclude` seed it previews — a write into every project on the first real run
    (`grep -ci exclude` over a live `--dry-run` transcript was 0). Print one
    `Would seed …` line per project, and ONLY while it has not been seeded yet."""
    repo = _init_repo(tmp_path / "proj")

    sync.resync_worktree_artifacts(repo, dry_run=True)
    out = capsys.readouterr().out
    assert "Would seed" in out, out

    # After a real seed, the dry-run line must not repeat — idempotent messaging.
    sync._seed_worktree_secrets_exclude(repo)
    sync.resync_worktree_artifacts(repo, dry_run=True)
    out2 = capsys.readouterr().out
    assert "Would seed" not in out2, out2


def test_dry_run_seed_disclosure_names_the_ledger_pattern(tmp_path: Path, capsys):
    """[M] round 9, class 1: the `Would seed …` line hardcoded "(.env, .mcp.json) —
    first real run only" — both halves went false the moment round 8 landed: the
    real write now seeds a THIRD pattern (`_WORKTREE_LEDGER_REL`), and on a
    legacy-marker repo it is not "the first real run" at all but an UPGRADE
    appending a missing pattern under an already-present marker. The line must
    name the actual pattern list and both possibilities."""
    repo = _init_repo(tmp_path / "proj")

    sync.resync_worktree_artifacts(repo, dry_run=True)
    out = capsys.readouterr().out

    assert "Would seed" in out, out
    assert sync._WORKTREE_LEDGER_REL in out, (
        f"the ledger pattern must be named, not just the two legacy secrets: {out}"
    )
    assert ".env" in out and ".mcp.json" in out, out


# --------------------------------------------------------------------------- #
# dry-run empty-dir accounting (round 4, class 5)                            #
# --------------------------------------------------------------------------- #


def test_dry_run_empty_dir_deletion_count_matches_real_run(tmp_path: Path):
    """[M] round 4, class 5: `--dry-run` judged directory emptiness against the tree
    AS IT STANDS, before applying its OWN would-be file deletions — undercounting a
    directory that only becomes empty once its own child file is pruned in the SAME
    pass (measured: 1 reported under `--dry-run` where a real run performs 2 — the
    file, then the directory it leaves empty). The two must agree."""

    def _make_fixture(root: Path) -> tuple[Path, Path]:
        repo = _init_repo(root / "proj")
        (repo / ".windsurf" / "rules" / "core").mkdir(parents=True)
        (repo / ".windsurf" / "rules" / "core" / "keep.md").write_text("keep\n")
        wt_dir = _add_worktree(repo, "agent-x")
        (wt_dir / ".windsurf" / "rules" / "core" / "sub-owned").mkdir(parents=True)
        retired = wt_dir / ".windsurf" / "rules" / "core" / "sub-owned" / "retired.md"
        retired.write_text("stale\n")
        (wt_dir / ".fabrik").mkdir()
        # A REAL hash (round 6, class 1): membership alone is no longer enough to
        # authorize a prune.
        (wt_dir / sync._WORKTREE_LEDGER_REL).write_text(
            json.dumps(
                {".windsurf/rules/core/sub-owned/retired.md": sync.compute_file_hash(retired)}
            )
        )
        return repo, wt_dir

    dry_repo, dry_wt = _make_fixture(tmp_path / "dry")
    before_dry = sync._WORKTREE_TALLY["deletions"]
    sync.resync_worktree_artifacts(dry_repo, dry_run=True)
    dry_count = sync._WORKTREE_TALLY["deletions"] - before_dry

    real_repo, real_wt = _make_fixture(tmp_path / "real")
    before_real = sync._WORKTREE_TALLY["deletions"]
    sync.resync_worktree_artifacts(real_repo)
    real_count = sync._WORKTREE_TALLY["deletions"] - before_real

    assert dry_count == real_count == 2, (dry_count, real_count)
    assert not (real_wt / ".windsurf" / "rules" / "core" / "sub-owned").exists(), (
        "the real run must remove both the file and the now-empty directory"
    )
    assert (dry_wt / ".windsurf" / "rules" / "core" / "sub-owned").exists(), (
        "--dry-run must never actually delete"
    )


# --------------------------------------------------------------------------- #
# --force never re-copies an identical file (round 4, class 8)               #
# --------------------------------------------------------------------------- #


def test_force_never_recopies_a_byte_identical_worktree_file(tmp_path: Path):
    """[L] round 4, class 8: `--force` previously re-copied a file even when the
    worktree's copy was already byte-identical to the source — ~19k needless writes
    fleet-wide per governance commit. The ledger (or a live hash compare) already
    proves it; SKIP instead of writing."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("same content\n")
    wt_dir = _add_worktree(repo, "agent-x")

    sync.resync_worktree_artifacts(repo)  # establishes the ledger, copies the file
    mtime_before = (wt_dir / "AGENTS.md").stat().st_mtime_ns

    sync.resync_worktree_artifacts(repo, force=True)
    mtime_after = (wt_dir / "AGENTS.md").stat().st_mtime_ns

    assert mtime_after == mtime_before, (
        "a byte-identical file must never be rewritten, even with --force"
    )


# --------------------------------------------------------------------------- #
# Lock timing (class 3)                                                      #
# --------------------------------------------------------------------------- #


def test_worktree_receives_the_fresh_lock_after_a_full_sync(tmp_path: Path, monkeypatch):
    """R3 corrected premise: `.fabrik/synced.lock` is not a `.worktreeinclude`
    pattern, so a worktree has none until the sync writes the main checkout's lock AND
    copies it in — IN THAT ORDER. After a full sync_scripts_to_project run, the
    worktree's lock must exist and equal the main checkout's byte-for-byte.

    round 10, class 3: this repo's worktree is cut from a branch with NO
    `.gitignore` at all (predating the manifest's `.fabrik/synced.lock` entry, the
    exact "old branch" shape) — reproduced live before the fix: `git status
    --porcelain` in the worktree showed `?? .fabrik/`, unignored, and a `git clean
    -fd` there would delete the lock this test just proved gets written. The
    shared `git-common-dir/info/exclude` floor (`_WORKTREE_FLOOR_PATTERNS`) must
    cover it exactly like the ledger and the secrets, so `git status` here comes
    back clean regardless of what the worktree's own branch's `.gitignore` says."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add AGENTS.md"], repo)

    wt_dir = _add_worktree(repo, "agent-x")

    # An empty fake hub root: every FABRIK_ROOT-sourced file simply doesn't exist, so
    # every "if source.exists()" guard in sync_scripts_to_project no-ops — the lock is
    # built from files that exist in the PROJECT, not from the hub source tree.
    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)

    result = sync.sync_scripts_to_project(repo, dry_run=False)
    assert result.success, result.message

    main_lock = repo / ".fabrik" / "synced.lock"
    wt_lock = wt_dir / ".fabrik" / "synced.lock"
    assert main_lock.exists(), "a full sync must write the main checkout's lock"
    assert wt_lock.exists(), (
        "the worktree must receive the FRESH lock — it is not a .worktreeinclude "
        "pattern, so only the post-write resync call can put it there"
    )
    assert wt_lock.read_bytes() == main_lock.read_bytes()

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=wt_dir, capture_output=True, text=True
    ).stdout
    assert ".fabrik" not in status, (
        f"the worktree's copy of the lock must be ignored on an old branch too: {status!r}"
    )


# --------------------------------------------------------------------------- #
# Production visibility (class 5)                                            #
# --------------------------------------------------------------------------- #


def test_worktree_tally_folds_into_the_final_summary_line(tmp_path, monkeypatch, capsys):
    """class 5: the production wrapper truncates the sync's stdout to the last 3
    lines (scripts/governance_sync_postcommit.sh:82) — every per-project worktree
    print (the count, the NOTEs, the WARNs) is dropped there. The worktree numbers
    must survive by riding the final `Results:` line main() already prints, which
    this test proves end-to-end via main() itself, not a proxy."""
    fake_opt = tmp_path / "opt"
    fake_opt.mkdir()
    repo = _init_repo(fake_opt / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)
    _add_worktree(repo, "agent-x")

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)
    monkeypatch.setattr(sync, "OPT_ROOT", fake_opt)
    monkeypatch.setattr(sys, "argv", ["sync_enforcement_to_projects.py"])

    sync.main()

    out = capsys.readouterr().out
    assert "| Worktrees:" in out, out
    assert "1 worktree(s) across 1 project(s)" in out, out


def test_worktree_tally_folds_into_the_final_summary_line_under_dry_run(
    tmp_path, monkeypatch, capsys
):
    """[M] round 3 (native-finder), class 3: `_WORKTREE_TALLY` was updated only on
    real runs, so the ticket-mandated `--dry-run` fire-rate sweep showed NOTHING on
    the one line the wrapper keeps. It must show the would-be totals, worded as
    "would re-sync" rather than claiming work already done."""
    fake_opt = tmp_path / "opt"
    fake_opt.mkdir()
    repo = _init_repo(fake_opt / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)
    _add_worktree(repo, "agent-x")

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)
    monkeypatch.setattr(sync, "OPT_ROOT", fake_opt)
    monkeypatch.setattr(sys, "argv", ["sync_enforcement_to_projects.py", "--dry-run"])

    sync.main()

    out = capsys.readouterr().out
    assert "| Worktrees: would re-sync" in out, out
    assert "1 worktree(s) across 1 project(s)" in out, out


def test_per_project_ok_message_includes_worktree_counts(tmp_path, monkeypatch):
    """[L] round 3, class 3: the per-project OK line (`ProjectSyncResult.message`)
    excluded worktree files while the final `Results:` line included them — the two
    disagreed about what "copied" meant for the SAME project. The per-project line
    must carry the same worktree breakdown."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "AGENTS.md").write_text("agents doc\n")
    _run(["git", "add", "AGENTS.md"], repo)
    _run(["git", "commit", "-q", "-m", "add"], repo)
    _add_worktree(repo, "agent-x")

    fake_fabrik_root = tmp_path / "fake-fabrik-root"
    fake_fabrik_root.mkdir()
    monkeypatch.setattr(sync, "FABRIK_ROOT", fake_fabrik_root)

    result = sync.sync_scripts_to_project(repo, dry_run=False)

    assert result.success, result.message
    assert "worktree" in result.message.lower(), result.message
    assert "1 worktree(s)" in result.message, result.message


# --------------------------------------------------------------------------- #
# _unreachable_vendored_copies false positives (native-finder round 3, class 1) #
# --------------------------------------------------------------------------- #


def test_unreachable_vendored_copies_ignores_worktree_resyncs(tmp_path: Path):
    """[H] `_unreachable_vendored_copies`'s os.walk otherwise descends into a linked
    worktree's own re-synced copy of VENDORED_DIRS (libs/subagents/, libs/health_probe/,
    both carrying __init__.py) and misreports each as an unreachable stray — it is the
    sync's OWN reachable output, not a project vendoring the module somewhere else.
    Measured (finder): 0 strays before any worktree exists, 8 after on a 4-worktree
    fixture (2 vendored dirs x 4 worktrees) -> 82 x 2 = 164 false hits fleet-wide."""
    repo = _init_repo(tmp_path / "proj")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "subagents" / "__init__.py").write_text("")
    (repo / "libs" / "health_probe").mkdir(parents=True)
    (repo / "libs" / "health_probe" / "__init__.py").write_text("")

    strays_before = sync._unreachable_vendored_copies([repo])
    assert strays_before == [], strays_before

    for i in range(4):
        wt = _add_worktree(repo, f"agent-{i}")
        for vendored_rel in ("libs/subagents", "libs/health_probe"):
            d = wt / vendored_rel
            d.mkdir(parents=True)
            (d / "__init__.py").write_text("")

    strays_after = sync._unreachable_vendored_copies([repo])
    assert strays_after == [], strays_after


# --------------------------------------------------------------------------- #
# Hub settings.json (class 8)                                                #
# --------------------------------------------------------------------------- #


def test_hub_settings_json_worktree_block_is_present_and_well_formed():
    """class 8, 2026-09-05 acceptance round 2: dropped the "worktree is the last key"
    and full-file byte-equality pins from round 1 — both red on any legitimate future
    top-level key (probed: adding a `statusLine` key failed the round-1 version).
    Keep only what is actually durable: the block's exact value, and the file's own
    2-space top-level indentation holding for the new key too.

    round 12, class 3: "hooks/permissions present and non-empty" is a much weaker
    claim than the Behavior Contract row this test exists to satisfy — "byte-
    identical to before" — a hook silently ADDED alongside the worktree block would
    still pass a bare non-empty check. `5fd58526` is the commit immediately before
    T01a/T01b touched this file (confirmed: it has no `worktree` key at all), so its
    `.claude/settings.json` is the real "before" — asserted via `git show`, not a
    hand-copied literal, so a legitimate future edit to hooks/permissions updates
    this test's baseline by moving the pinned commit forward, never by loosening the
    assertion."""
    raw = (REPO / ".claude" / "settings.json").read_text(encoding="utf-8")
    settings = json.loads(raw)  # raises if the file is not valid JSON

    assert settings["worktree"] == {"baseRef": "head", "symlinkDirectories": [".venv"]}

    base_raw = subprocess.run(
        ["git", "show", "5fd58526:.claude/settings.json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    base_settings = json.loads(base_raw)
    assert "worktree" not in base_settings, "guard: 5fd58526 must predate the worktree block"

    for key in ("hooks", "permissions", "enableAllProjectMcpServers"):
        assert settings[key] == base_settings[key], (
            f"{key} must be byte-identical to its value at 5fd58526 — the worktree "
            f"block is the ONLY sanctioned change to this file"
        )

    lines = raw.splitlines()

    def _indent(key: str) -> int:
        line = next(ln for ln in lines if ln.strip().startswith(f'"{key}"'))
        return len(line) - len(line.lstrip(" "))

    assert _indent("worktree") == _indent("hooks") == 2, (
        "top-level keys must share the file's own 2-space indentation"
    )
