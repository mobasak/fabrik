# AFTER-EDIT: scripts/wip_backup.sh
"""WIP safety net — the snapshot must capture staged+unstaged+untracked WITHOUT
touching the repo's real index, HEAD, branches, or stash (concurrent agents
must be completely unaffected)."""

from __future__ import annotations

import glob
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/wip_backup.sh"

# A dated ref's tail (after the LAST "-") is the exact UTC timestamp shape the
# script itself requires; a rolling ref (refs/wip/wt-<name>-<id8>) never has
# one. Used to tell rolling vs dated refs apart without needing to replicate
# the script's own sha1(realpath) id computation in Python.
_TS_TAIL_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=15
    ).stdout.strip()


def _seed_repo(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-qm", "base")
    return repo


def _run(root: Path) -> str:
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={"PATH": "/usr/bin:/bin", "WIP_BACKUP_ROOT": str(root), "HOME": str(root)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _run_traced(root: Path, trace_file: Path) -> str:
    # GIT_TRACE=1 writes to the git process's own stderr, which several of
    # the script's git invocations explicitly redirect to /dev/null — an
    # absolute-path GIT_TRACE value writes straight to that file instead,
    # bypassing the script's own redirects entirely.
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": "/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(root),
            "HOME": str(root),
            "GIT_TRACE": str(trace_file),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _classify_wt_refs(repo: Path, name_glob: str) -> tuple[list[str], list[str]]:
    # Split refs matching refs/wip/wt-<name_glob>* into (rolling, dated) by
    # whether their tail (after the LAST "-") is the exact timestamp shape —
    # avoids needing to replicate the script's sha1(realpath) id in Python.
    refs = _git(
        repo, "for-each-ref", "--format=%(refname)", f"refs/wip/wt-{name_glob}*"
    ).splitlines()
    rolling = [r for r in refs if not _TS_TAIL_RE.match(r.rsplit("-", 1)[-1])]
    dated = [r for r in refs if _TS_TAIL_RE.match(r.rsplit("-", 1)[-1])]
    return rolling, dated


def _exclude_path(repo: Path, relpath: str) -> None:
    # Mirrors the real hub checkout, which excludes .claude/worktrees/ via
    # .git/info/exclude (spec residual R2: "the hub only carries it in
    # .git/info/exclude:11") rather than a committed .gitignore — a linked
    # worktree nested under the main tree is otherwise reported as an
    # untracked "embedded git repository" by `git status`, which would dirty
    # the main tree merely because the worktree exists.
    (repo / ".git" / "info" / "exclude").write_text(f"{relpath}/\n")


def _slow_add_git_wrapper(bin_dir: Path, delay: float = 5.0, sentinel: Path | None = None) -> None:
    # A `git` on PATH ahead of the real one that sleeps only for `add -A`,
    # delegating everything else immediately — gives a deterministic window
    # to interrupt the script while it is genuinely blocked in that call.
    # Round 8 acceptance finding 3: when `sentinel` is given, TOUCH it the
    # instant the `add -A` branch is entered (before the sleep) — a caller
    # can wait on that file to know `add -A` has genuinely been reached
    # (i.e. the preceding `read-tree` already succeeded and the isolated
    # index it populated genuinely exists), rather than racing a glob
    # against the index file's own name, which can catch the file's brief
    # window between mktemp creating it and the script's own `rm -f`
    # (before `read-tree` recreates it) — a SIGTERM landing in that gap
    # proves nothing about the trap under test.
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "git"
    sentinel_cmd = f'touch "{sentinel}"; ' if sentinel is not None else ""
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f'if [ "$1" = "add" ] && [ "$2" = "-A" ]; then {sentinel_cmd}sleep {delay}; fi\n'
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)


def _slow_push_git_wrapper(bin_dir: Path, delay: float = 600.0) -> None:
    # A `git` on PATH ahead of the real one that sleeps only for `push`,
    # delegating everything else immediately — simulates an unbounded
    # network stall on the push call (the round 9 acceptance finding 1 [H]
    # regression: neither push site had a `timeout`, so a stalled push left
    # the main tree's own dirt completely unprotected and would wedge every
    # LATER repo in a real cron run under `flock -n`). 600s stands in for
    # "long enough that an unbounded call would never return in this test's
    # lifetime" — the fix bounds it via `timeout "$WIP_BACKUP_PUSH_TIMEOUT"`,
    # so the caller overrides that env var to a small value for a fast test.
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f'if [ "$1" = "push" ]; then sleep {delay}; fi\n'
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)


def _failing_mktemp_wrapper(bin_dir: Path, needle: str) -> None:
    # A `mktemp` on PATH ahead of the real one that fails (no output, exit 1)
    # only for a template containing `needle`, delegating everything else —
    # simulates mktemp genuinely failing (disk full, permissions) without
    # touching real filesystem state.
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "mktemp"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f'for a in "$@"; do case "$a" in *{needle}*) exit 1 ;; esac; done\n'
        'exec /usr/bin/mktemp "$@"\n'
    )
    wrapper.chmod(0o755)


def _readonly_after_mktemp_wrapper(bin_dir: Path, needle: str) -> None:
    # A `mktemp` on PATH ahead of the real one that, only for a template
    # containing `needle`, creates the file via the REAL mktemp and then
    # immediately chmods it read-only before printing its path back —
    # simulates a write failure on that specific file (e.g. ENOSPC, or a
    # permissions problem) WITHOUT touching mktemp's own success path: the
    # file genuinely exists and is genuinely readable, only appending to it
    # fails, which is exactly the class round 9 acceptance finding 7 [L]
    # targets (an ENOSPC mid-run silently drops a live-id line while the
    # file itself stays present and readable).
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "mktemp"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do case "$a" in\n'
        f"    *{needle}*)\n"
        '        p="$(/usr/bin/mktemp "$@")"\n'
        '        chmod 0444 "$p"\n'
        '        printf "%s\\n" "$p"\n'
        "        exit 0\n"
        "        ;;\n"
        "esac; done\n"
        'exec /usr/bin/mktemp "$@"\n'
    )
    wrapper.chmod(0o755)


def _timeout_arg_capture_wrapper(bin_dir: Path, capture_file: Path) -> None:
    # A `timeout` on PATH ahead of the real one that appends its own FIRST
    # argument (the duration the caller computed) to `capture_file`, then
    # execs the real `timeout` with the same args so the wrapped command
    # still actually runs normally — lets a test observe exactly what
    # value scripts/wip_backup.sh's own `WIP_BACKUP_PUSH_TIMEOUT` validation
    # produced, without needing to wait out a real multi-second bound.
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "timeout"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$1" >> "{capture_file}"\n'
        'exec /usr/bin/timeout "$@"\n'
    )
    wrapper.chmod(0o755)


def _partial_worktree_list_git_wrapper(bin_dir: Path, keep_lines: int = 3) -> None:
    # A `git` on PATH ahead of the real one that, only for `worktree list`,
    # prints a TRUNCATED porcelain output then exits 128 — simulates git
    # itself failing partway through the enumeration, delegating everything
    # else (including plain `git worktree list --porcelain`'s exit-0 path
    # elsewhere) untouched.
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "worktree" ] && [ "$2" = "list" ]; then\n'
        f'    /usr/bin/git "$@" | head -n {keep_lines}\n'
        "    exit 128\n"
        "fi\n"
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)


def _complete_but_failing_worktree_list_git_wrapper(bin_dir: Path) -> None:
    # A `git` on PATH ahead of the real one that, only for `worktree list`,
    # prints the COMPLETE, untruncated porcelain output but still exits
    # non-zero — isolates `wt_enum_ok` (the captured EXIT STATUS) from the
    # count check (`grep -c '^worktree '` against expected): a complete list
    # satisfies the count on its own, so only honouring the exit status
    # itself can catch this shape. `_partial_worktree_list_git_wrapper`
    # above is caught by the count mismatch instead — this one is not.
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "worktree" ] && [ "$2" = "list" ]; then\n'
        '    /usr/bin/git "$@"\n'
        "    exit 1\n"
        "fi\n"
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)


def test_tracked_but_gitignored_files_survive_snapshot_and_recovery(tmp_path: Path) -> None:
    # Tracked files matched by .gitignore must NOT appear as deletions in the
    # snapshot (live finding: recovery via cherry-pick DELETED them — /opt/proxy
    # has 1342 such files).
    repo = _seed_repo(tmp_path, "trig")
    (repo / "tracked-ignored.conf").write_text("precious\n")
    _git(repo, "add", "-f", "tracked-ignored.conf")
    _git(repo, "commit", "-qm", "add tracked-ignored")
    (repo / ".gitignore").write_text("tracked-ignored.conf\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore it")
    (repo / "dirty.txt").write_text("wip\n")  # make it dirty → snapshot fires
    _run(tmp_path)
    status = _git(repo, "diff", "--name-status", "HEAD", "refs/wip/autobackup")
    assert "tracked-ignored.conf" not in status, f"snapshot records a deletion: {status}"


def test_linked_worktree_repos_are_covered(tmp_path: Path) -> None:
    # A linked worktree has a .git FILE, not dir — it must still be netted
    # (live finding: two dirty /opt worktrees had zero snapshots).
    main = _seed_repo(tmp_path, "mainrepo")
    wt = tmp_path / "wtrepo"
    _git(main, "worktree", "add", "-b", "side", str(wt))
    (wt / "wip.txt").write_text("worktree wip\n")
    _run(tmp_path)
    tree = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "refs/wip/autobackup"],
        cwd=wt,
        capture_output=True,
        text=True,
    ).stdout
    assert "wip.txt" in tree


def test_snapshot_captures_all_without_touching_agent_state(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, "proj")
    # An agent's in-flight state: one STAGED file, one unstaged edit, one untracked.
    (repo / "staged.txt").write_text("staged by sibling\n")
    _git(repo, "add", "staged.txt")
    (repo / "base.txt").write_text("unstaged edit\n")
    (repo / "untracked.txt").write_text("brand new\n")
    head_before = _git(repo, "rev-parse", "HEAD")

    _run(tmp_path)

    # Snapshot exists and contains all three states.
    tree_files = _git(repo, "ls-tree", "-r", "--name-only", "refs/wip/autobackup")
    assert {"base.txt", "staged.txt", "untracked.txt"} <= set(tree_files.splitlines())
    assert "unstaged edit" in _git(repo, "show", "refs/wip/autobackup:base.txt")
    # Agent state UNTOUCHED: HEAD same, staged file still (and only) staged.
    assert _git(repo, "rev-parse", "HEAD") == head_before
    staged = _git(repo, "diff", "--cached", "--name-only")
    assert staged.splitlines() == ["staged.txt"]
    assert _git(repo, "stash", "list") == ""


def test_clean_repo_and_unchanged_dirty_repo_are_skipped(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, "clean")
    _run(tmp_path)
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    )  # clean → no snapshot

    (repo / "x.txt").write_text("dirty\n")
    _run(tmp_path)
    first = _git(repo, "rev-parse", "refs/wip/autobackup")
    _run(tmp_path)  # dirty but unchanged → no new commit object
    assert _git(repo, "rev-parse", "refs/wip/autobackup") == first


def test_archived_dir_is_skipped(tmp_path: Path) -> None:
    # The guard must fire on $ROOT/archived ITSELF being a repo (the one-level
    # glob visits exactly that; the old nested fixture never reached the guard —
    # review finding: the test passed with the guard deleted).
    repo = _seed_repo(tmp_path, "archived")
    (repo / "y.txt").write_text("z\n")
    _run(tmp_path)
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    )


def test_dirty_linked_worktree_under_claude_worktrees_is_snapshotted(tmp_path: Path) -> None:
    # T13 row 1: a dirty worktree nested at .claude/worktrees/<name> is inside
    # the repo dir but is its OWN working tree — the outer glob never visits
    # it, so it needs its own discovery + snapshot.
    repo = _seed_repo(tmp_path, "wtdirty")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtdirty-side", str(wt))
    (wt / "change.txt").write_text("wip in worktree\n")

    assert _git(repo, "status", "--porcelain") == "", "fixture premise: main tree must be clean"

    _run(tmp_path)

    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1, f"expected exactly one rolling ref, got {rolling}"
    assert len(dated) == 1, f"expected exactly one dated ref, got {dated}"
    content = subprocess.run(
        ["git", "cat-file", "-p", f"{dated[0]}:change.txt"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    assert content == "wip in worktree\n"

    # The main tree was clean throughout — no main-tree snapshot fired.
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    )


def test_clean_linked_worktree_produces_no_ref_dirty_sibling_does(tmp_path: Path) -> None:
    # T13 row 2, REWRITTEN per acceptance round 1 finding 9: the original
    # cross-repo byte-identical comparison passed vacuously against the BASE
    # script (3 failed, 6 passed — this row was among the 6 passes with the
    # feature entirely absent). A dirty SIBLING worktree in the SAME repo
    # forces the discriminator to actually run: the clean one must produce no
    # ref while the dirty one must, which reds on a script with no worktree
    # awareness at all.
    repo = _seed_repo(tmp_path, "wtclean2")
    _exclude_path(repo, ".claude/worktrees")
    wt_clean = repo / ".claude" / "worktrees" / "beta"
    wt_dirty = repo / ".claude" / "worktrees" / "gamma"
    _git(repo, "worktree", "add", "-q", "-b", "wtclean2-beta", str(wt_clean))
    _git(repo, "worktree", "add", "-q", "-b", "wtclean2-gamma", str(wt_dirty))
    (wt_dirty / "change.txt").write_text("dirty sibling\n")

    _run(tmp_path)

    clean_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-beta*")
    assert clean_refs == "", f"clean worktree must produce no ref, got: {clean_refs}"

    dirty_refs = _git(
        repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-gamma*"
    ).splitlines()
    assert len(dirty_refs) >= 1, "dirty sibling worktree must be snapshotted"


def test_worktree_missing_directory_is_skipped_and_main_tree_still_snapshotted(
    tmp_path: Path,
) -> None:
    # T13 row 3: a worktree deleted without `git worktree prune` must be
    # skipped (one log line), never abort the rest of the repo's own snapshot.
    repo = _seed_repo(tmp_path, "wtmissing")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtmissing-side", str(wt))
    shutil.rmtree(wt)  # deleted WITHOUT `git worktree prune`

    (repo / "dirty.txt").write_text("main tree dirt\n")

    out = _run(tmp_path)

    skip_lines = [line for line in out.splitlines() if "beta" in line and "skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "missing directory" in skip_lines[0]

    # The repo loop was not aborted: the main tree still got its snapshot.
    assert _git(repo, "rev-parse", "-q", "--verify", "refs/wip/autobackup")


def test_prune_widens_to_wt_refs_parsing_timestamp_from_the_end(tmp_path: Path) -> None:
    # T13 row 4: refs/wip/wt-<name>-<ts> refs are swept by the same KEEP_DAYS
    # cutoff as bak-*, and the timestamp must be parsed from the END of the
    # ref name — a worktree name may itself contain "-".
    repo = _seed_repo(tmp_path, "wtprune")
    head = _git(repo, "rev-parse", "HEAD")

    now = datetime.now(UTC)
    old_ts = (now - timedelta(days=10)).strftime("%Y%m%dT%H%M%SZ")
    recent_ts = (now - timedelta(days=1)).strftime("%Y%m%dT%H%M%SZ")
    name = "agent-ae36d1bbd7a83c091"  # worktree name containing '-'

    old_ref = f"refs/wip/wt-{name}-{old_ts}"
    recent_ref = f"refs/wip/wt-{name}-{recent_ts}"
    _git(repo, "update-ref", old_ref, head)
    _git(repo, "update-ref", recent_ref, head)

    _run(tmp_path)

    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", old_ref],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    ), "ref older than KEEP_DAYS must be pruned"
    assert _git(repo, "rev-parse", "-q", "--verify", recent_ref) == head


# --- T13 acceptance round 1 FIXUP (native finder, ORCHESTRATOR DECISIONS 1 & 6) ---


def test_locked_dirty_worktree_is_still_snapshotted(tmp_path: Path) -> None:
    # Finding 1 [H], ORCHESTRATOR DECISION: `locked` on this box means an
    # agent is RUNNING there, not that a read-only snapshot is unsafe — it
    # must NOT be skipped. Only clean, missing, or unenterable worktrees are.
    repo = _seed_repo(tmp_path, "wtlocked")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtlocked-side", str(wt))
    (wt / "change.txt").write_text("wip while locked\n")
    _git(repo, "worktree", "lock", str(wt), "--reason", "agent running")

    _run(tmp_path)

    rolling, _dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1, f"a locked dirty worktree must still get a rolling ref, got {rolling}"


def test_unchanged_dirty_worktree_mints_one_dated_ref_across_runs(tmp_path: Path) -> None:
    # Finding 2 [H]: mirror the main path exactly — a rolling refs/wip/wt-<name>
    # updated only on a tree change, plus a dated ref written only on that
    # same change. 3 runs on an unchanged dirty worktree → 1 dated ref, not 3.
    #
    # Round 8 acceptance finding 2: `len(dated_refs) == 1` is near-vacuous
    # WITHOUT the dedup guard too, whenever all 3 runs land in the same UTC
    # second — the dated ref's NAME (refs/wip/wt-<id>-<ts>) is then IDENTICAL
    # across all 3 runs regardless of dedup, so `git update-ref` just
    # overwrites the same ref 3 times and the count still comes out to 1
    # (observed: the dedup guard removed, 13 of 15 runs still green). The
    # deterministic signal dedup actually controls is whether the snapshot
    # step runs AT ALL on runs 2 and 3 — with dedup, only the FIRST run's
    # `_wip_snapshot_worktree` call reaches its "snapshotted" echo; without
    # it, every run does. Assert THAT directly, from all 3 runs' own stdout,
    # not from a ref count that a timestamp collision can satisfy either way.
    repo = _seed_repo(tmp_path, "wtdedup")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtdedup-side", str(wt))
    (wt / "change.txt").write_text("stable wip\n")

    out1 = _run(tmp_path)
    out2 = _run(tmp_path)
    out3 = _run(tmp_path)

    snapshotted_lines = [
        line
        for out in (out1, out2, out3)
        for line in out.splitlines()
        if "worktree beta snapshotted" in line
    ]
    assert len(snapshotted_lines) == 1, (
        "expected exactly one 'worktree beta snapshotted' line across 3 unchanged "
        f"runs (dedup must suppress runs 2 and 3), got {len(snapshotted_lines)}: "
        f"{snapshotted_lines!r}"
    )

    rolling_refs, dated_refs = _classify_wt_refs(repo, "beta")
    assert len(rolling_refs) == 1, f"expected exactly one rolling ref, got {rolling_refs}"
    assert len(dated_refs) == 1, (
        f"expected exactly one dated ref across 3 unchanged runs, got {dated_refs}"
    )
    rolling = _git(repo, "rev-parse", rolling_refs[0])
    assert rolling == _git(repo, "rev-parse", dated_refs[0]), (
        "rolling ref must track the same commit"
    )


def test_worktree_name_with_space_is_sanitised_into_a_valid_ref(tmp_path: Path) -> None:
    # Finding 3 [M], sanitisation half: a directory name with a space is a
    # refname git rejects outright — replace anything outside
    # [A-Za-z0-9._-] with "-" so the worktree still gets netted.
    repo = _seed_repo(tmp_path, "wtspace")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "has space"
    _git(repo, "worktree", "add", "-q", "-b", "wtspace-side", str(wt))
    (wt / "change.txt").write_text("wip\n")

    out = _run(tmp_path)

    refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-has-space*").splitlines()
    assert len(refs) >= 1, (
        f"a space in the worktree name must be sanitised into a valid ref, got out={out!r}"
    )
    assert not any("ref update failed" in line for line in out.splitlines())


def test_worktree_name_that_git_rejects_as_a_refname_logs_once_and_never_a_false_success(
    tmp_path: Path,
) -> None:
    # Finding 3 [M], exit-status half: ".." survives sanitisation (dots are
    # allowed) but git still refuses it as a refname component — the failure
    # path must log exactly ONE line naming the worktree + the git error, and
    # never print a false "snapshotted" success.
    repo = _seed_repo(tmp_path, "wtbadref")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "a..b"
    _git(repo, "worktree", "add", "-q", "-b", "wtbadref-side", str(wt))
    (wt / "change.txt").write_text("wip\n")

    out = _run(tmp_path)

    matching = [line for line in out.splitlines() if "a..b" in line]
    assert len(matching) == 1, f"expected exactly one log line naming the worktree, got: {matching}"
    assert "ref update failed" in matching[0], matching[0]
    assert "snapshotted" not in matching[0], (
        f"must never claim success on a rejected refname: {matching[0]}"
    )

    no_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-a..b*")
    assert no_refs == ""


def test_worktree_unenterable_is_skipped_with_one_log_line(tmp_path: Path) -> None:
    # Finding 4 [M]: an existing-but-unenterable worktree (chmod 000) was
    # dropped with ZERO log lines (`cd ... || exit 0` after the `-d` check
    # passed). It must log one line, as the missing-dir case does, and never
    # abort the repo's own snapshot.
    repo = _seed_repo(tmp_path, "wtdenied")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtdenied-side", str(wt))
    (repo / "dirty.txt").write_text("main tree dirt\n")

    wt.chmod(0o000)
    try:
        out = _run(tmp_path)
    finally:
        wt.chmod(0o755)  # restore so pytest's tmp_path teardown can recurse into it

    skip_lines = [line for line in out.splitlines() if "beta" in line and "skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "unenterable" in skip_lines[0]

    assert _git(repo, "rev-parse", "-q", "--verify", "refs/wip/autobackup")


def test_symlinked_root_is_normalized_before_matching_worktree_paths(tmp_path: Path) -> None:
    # Finding 5 [M]: the scope guard was a textual prefix on $repo — under a
    # symlinked/bind-mounted ROOT every worktree would vanish silently since
    # git's own (already-canonical) worktree path never textually matches the
    # symlinked route. Normalise both sides before comparing.
    real_base = tmp_path / "real"
    real_base.mkdir()
    repo = _seed_repo(real_base, "wtsym")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtsym-side", str(wt))
    (wt / "change.txt").write_text("wip via symlink\n")

    root_link = tmp_path / "root_link"
    root_link.symlink_to(real_base, target_is_directory=True)

    _run(root_link)

    refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-beta*")
    assert refs != "", (
        "a worktree reached through a symlinked ROOT must still be discovered and snapshotted"
    )


def test_worktree_scope_widened_beyond_claude_worktrees(tmp_path: Path) -> None:
    # Finding 6 [M], ORCHESTRATOR DECISION: widen the scope from
    # .claude/worktrees/ to ANY linked worktree nested under the repo (live
    # census: /opt/youtube/.kilo/worktrees/frost-nightshade and
    # .tmp/subagents/agent-* worktrees were covered by nothing).
    repo = _seed_repo(tmp_path, "wtwide")
    _exclude_path(repo, ".kilo/worktrees")
    wt = repo / ".kilo" / "worktrees" / "frost-nightshade"
    _git(repo, "worktree", "add", "-q", "-b", "wtwide-side", str(wt))
    (wt / "change.txt").write_text("dirty outside .claude\n")

    _run(tmp_path)

    refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-frost-nightshade*")
    assert refs != "", (
        "any linked worktree under the repo must be netted, not just .claude/worktrees/"
    )


def test_rolling_worktree_refs_are_pushed_to_origin_in_one_push(tmp_path: Path) -> None:
    # Finding 7 [M] (round 1) + Finding 2 [M] (round 2): wt snapshots never
    # left the box — push the rolling refs/wip/wt-<name>-<id8> the same way
    # the main tree pushes refs/wip/autobackup; and with TWO dirty worktrees,
    # that must be ONE `git push` covering both refspecs, not one push per
    # worktree per run (measured live: 28 pushes/15min in seo).
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtpush")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt_a = repo / ".claude" / "worktrees" / "alpha"
    wt_b = repo / ".claude" / "worktrees" / "bravo"
    _git(repo, "worktree", "add", "-q", "-b", "wtpush-a", str(wt_a))
    _git(repo, "worktree", "add", "-q", "-b", "wtpush-b", str(wt_b))
    (wt_a / "change.txt").write_text("push me a\n")
    (wt_b / "change.txt").write_text("push me b\n")

    trace_file = tmp_path / "trace.log"
    _run_traced(tmp_path, trace_file)

    rolling_a, _ = _classify_wt_refs(repo, "alpha")
    rolling_b, _ = _classify_wt_refs(repo, "bravo")
    assert len(rolling_a) == 1 and len(rolling_b) == 1, "both worktrees must get a rolling ref"

    for ref in (*rolling_a, *rolling_b):
        on_origin = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", ref],
            cwd=origin,
            capture_output=True,
            timeout=15,
        )
        assert on_origin.returncode == 0, f"{ref} must be pushed off-box like refs/wip/autobackup"

    push_lines = [
        line for line in trace_file.read_text().splitlines() if "trace: built-in: git push" in line
    ]
    assert len(push_lines) == 1, (
        f"expected exactly ONE push covering both worktrees, got: {push_lines}"
    )


def test_prune_requires_timestamp_shape_and_spares_the_rolling_ref(tmp_path: Path) -> None:
    # Finding 8 [L]: the prune parsed t="${ref##*-}" and deleted any wt-* ref
    # whose tail sorted before the cutoff (refs/wip/wt-2020 deleted blindly).
    # Require the timestamp SHAPE before comparing; a genuinely stale DATED
    # ref must still be pruned, and the rolling wt-<name> ref must never be.
    repo = _seed_repo(tmp_path, "wtprune2")
    head = _git(repo, "rev-parse", "HEAD")

    now = datetime.now(UTC)
    old_valid_ts = (now - timedelta(days=10)).strftime("%Y%m%dT%H%M%SZ")
    old_valid_ref = f"refs/wip/wt-somebody-{old_valid_ts}"
    junk_ref = "refs/wip/wt-junk"
    year_ref = "refs/wip/wt-2020"
    rolling_ref = "refs/wip/wt-somebody"

    for ref in (old_valid_ref, junk_ref, year_ref, rolling_ref):
        _git(repo, "update-ref", ref, head)

    _run(tmp_path)

    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", old_valid_ref],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    ), "a genuinely stale DATED ref must still be pruned"
    for ref in (junk_ref, year_ref, rolling_ref):
        assert _git(repo, "rev-parse", "-q", "--verify", ref) == head, (
            f"{ref} must survive the shape guard"
        )


# --- T13 acceptance round 2 FIXUP (pool layer, 3 classes) ---


def test_worktree_basename_collision_after_sanitisation_gets_distinct_refs(tmp_path: Path) -> None:
    # Finding 1 [H]: two worktrees whose basenames sanitise to the SAME
    # refname ("a b" and "a-b" both become "a-b") must not share one rolling
    # ref — the dedup would compare the wrong tree and one worktree's
    # snapshot would silently overwrite the other's. The ref name carries an
    # 8-hex id derived from sha1(realpath), which is unique per worktree.
    repo = _seed_repo(tmp_path, "wtcollide")
    _exclude_path(repo, ".claude/worktrees")
    wt1 = repo / ".claude" / "worktrees" / "a b"  # sanitises to "a-b"
    wt2 = repo / ".claude" / "worktrees" / "a-b"  # already "a-b"
    _git(repo, "worktree", "add", "-q", "-b", "wtcollide-1", str(wt1))
    _git(repo, "worktree", "add", "-q", "-b", "wtcollide-2", str(wt2))
    (wt1 / "change.txt").write_text("from a b\n")
    (wt2 / "change.txt").write_text("from a-b\n")

    _run(tmp_path)

    rolling, _dated = _classify_wt_refs(repo, "a-b")
    assert len(rolling) == 2, (
        f"expected two distinct rolling refs for colliding basenames, got {rolling}"
    )

    contents = set()
    for ref in rolling:
        c = subprocess.run(
            ["git", "cat-file", "-p", f"{ref}:change.txt"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        contents.add(c)
    assert contents == {"from a b\n", "from a-b\n"}, (
        f"each worktree's own content must survive intact, got {contents}"
    )


def test_dangling_rolling_ref_is_treated_as_no_previous_snapshot(tmp_path: Path) -> None:
    # Finding 3 [L]: `git rev-parse -q --verify "$ref^{tree}" || true` yields
    # "" when the rolling ref points at a dangling/garbage-collected commit —
    # this must be a DELIBERATE "no previous snapshot" disposition (a fresh
    # snapshot is taken, nothing extra is logged), not an accident that also
    # happens to silently disable dedup. `git update-ref` itself refuses to
    # write a nonexistent object, so the dangling ref is manufactured by
    # writing the loose ref FILE directly, bypassing that check — exactly
    # what a real concurrent prune racing a read would leave behind.
    repo = _seed_repo(tmp_path, "wtdangle")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtdangle-side", str(wt))
    (wt / "change.txt").write_text("wip v1\n")

    _run(tmp_path)  # creates the real rolling ref

    rolling, _dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1, f"expected exactly one rolling ref after the first run, got {rolling}"
    rolling_ref = rolling[0]

    bogus_sha = "d34dbeef" * 5  # 40 hex chars, syntactically valid, never an object
    ref_path = repo / ".git" / rolling_ref
    ref_path.write_text(bogus_sha + "\n")
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"{rolling_ref}^{{tree}}"],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    ), "fixture premise: the rolling ref must be unresolvable"

    (wt / "change.txt").write_text("wip v2\n")  # give it something new to snapshot

    out = _run(tmp_path)

    assert "beta" in out and "snapshotted" in out, f"a fresh snapshot must still happen: {out!r}"
    assert "fatal" not in out.lower() and "error" not in out.lower(), (
        f"must log nothing extra: {out!r}"
    )

    new_head = _git(repo, "rev-parse", rolling_ref)
    assert new_head != bogus_sha
    content = subprocess.run(
        ["git", "cat-file", "-p", f"{new_head}:change.txt"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    assert content == "wip v2\n"


# --- T13 acceptance round 2 FIXUP, native finder over 666343d8 (5 classes) ---


def test_main_tree_temp_index_is_cleaned_up_on_signalled_interruption(tmp_path: Path) -> None:
    # Finding 1 [H] + incident, widened by round 6 acceptance finding 2: the
    # /tmp/wip-wt-* temp files (push queue, live-ids, the captured
    # enumeration) are ALSO in the top-level trap. Widened again by round 7
    # acceptance finding 3: the WORKTREE subshell's OWN EXIT trap (its own
    # /tmp/wip-index-<repo>-<worktree>.XXXXXX, a SEPARATE file from the
    # main tree's) had no grader either — deleting it left the suite green
    # while a real SIGTERM leaked it (mutant 3/3; production run 0/15).
    # A worktree is added so its OWN `add -A` (same slow wrapper) is
    # reached WHILE all of these files are still allocated.
    # Round 9 acceptance finding 5 [L]: the seed name is process-UNIQUE
    # (pid-suffixed), not the bare literal "wtleak" — the old literal name
    # meant every process running this suite (a concurrent sibling session
    # on this 3-session hub) produced the identical /tmp/wip-index-wtleak*
    # prefix, so a decoy writer running alongside this test could leave
    # files misread as our own leak (reproduced: 83 foreign files misread
    # as our leak, 85 deleted by the old finally-block cleanup). A
    # pid-suffixed name is unique per OS process, so the glob below can
    # only ever match THIS test's own files — the real production cron
    # never creates a repo directory named anything like "wtleak<pid>" in
    # the first place (it only ever touches genuine /opt project repos),
    # so there is nothing left to guard against by borrowing the cron's
    # own lock either (round 9 finding 3, below).
    repo = _seed_repo(tmp_path, f"wtleak{os.getpid()}")
    (repo / "dirty.txt").write_text("dirt\n")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtleak-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    bin_dir = tmp_path / "bin"
    # Round 8 acceptance finding 3: wait on a SENTINEL touched the instant
    # `add -A` is entered, not on the index file's own glob pattern — the
    # index file briefly EXISTS the moment `mktemp` creates it, then the
    # script's own `rm -f "$tmp_index"` removes it before `read-tree`
    # recreates it; a SIGTERM landing in that narrow gap proves nothing
    # about the trap under test (observed: the mutated-away trap then only
    # got caught ~1 run in 4). The sentinel fires only once `add -A` is
    # genuinely reached — i.e. `read-tree` already succeeded and the index
    # file genuinely, stably exists.
    add_started = tmp_path / "add-started.sentinel"
    _slow_add_git_wrapper(bin_dir, delay=5.0, sentinel=add_started)

    # Round 10 acceptance finding 1 [M]: the pid-unique repo name (round 9
    # finding 5) only reaches /tmp/wip-index-<repo>* — the three per-repo
    # coordination files (wip-wt-push/-live/-enum.XXXXXX) carry NO repo
    # name and no pid, so globbing the REAL /tmp for `wip-wt-*` and diffing
    # against a pre-existing snapshot still misreads a file the box's own
    # live cron (or a sibling suite run) creates DURING this test's own
    # window as our leak — and then deletes it (reproduced with a decoy:
    # a foreign wip-wt-push.* created mid-window was caught by the old
    # `remaining_wt` check and removed by the old finally-block sweep,
    # which for `wt_push_file` specifically means that repo's worktree
    # refs silently never reach origin that tick). Point the script's OWN
    # mktemp calls at a directory under THIS test's tmp_path instead of
    # sharing the real /tmp with the cron at all — no pre-existing-set
    # diffing is even needed once the namespace itself is private.
    wip_tmp = tmp_path / "wiptmp"
    wip_tmp.mkdir()
    wt_pattern = str(wip_tmp / "wip-wt-*")
    # Round 10 acceptance finding 4 [L]: dot/dash-ANCHORED, never a bare
    # `{repo.name}*` prefix — even though wip_tmp already isolates this
    # test from every sibling process, a bare prefix would still let one
    # pid's sweep match a DIFFERENT, longer pid's files sharing the same
    # numeric prefix (12345 matching 123456) were they ever to land in the
    # same directory. Two patterns: the main tree's own dot-suffixed index,
    # and the worktree's own dash-suffixed one.
    index_glob_patterns = [
        str(wip_tmp / f"wip-index-{repo.name}.*"),
        str(wip_tmp / f"wip-index-{repo.name}-*"),
    ]

    # Grader for this finding: a decoy matching the exact shape the real
    # cron would leave — created in the REAL /tmp, not under wip_tmp — must
    # be untouched by this test's assertions or cleanup, now that the
    # script never touches the real /tmp for these files at all.
    # Round 11 acceptance finding 4 [L]: `mkstemp(...)[1]` discards the
    # returned fd, an unclosed raw int leaked for the rest of the process.
    _decoy_fd, _decoy_path = tempfile.mkstemp(prefix="wip-wt-push.", dir="/tmp")
    os.close(_decoy_fd)
    real_tmp_decoy = Path(_decoy_path)

    proc = subprocess.Popen(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "WIP_BACKUP_TMP_DIR": str(wip_tmp),
            "HOME": str(tmp_path),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        # The dot matters on BOTH index patterns: the worktree's OWN temp
        # index is named wip-index-<repo>-<worktree-ref-name>.XXXXXX — a
        # bare trailing "*" (no dot) on the MAIN pattern would also match
        # it, turning its own timing into a false leak on the wrong file.
        main_index_pattern = str(wip_tmp / f"wip-index-{repo.name}.*")
        wt_index_pattern = str(wip_tmp / f"wip-index-{repo.name}-beta.*")

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not add_started.exists():
            time.sleep(0.05)
        assert add_started.exists(), "add -A was never reached — fixture premise failed"

        # Round 11 acceptance finding 3 [L]: without this, the whole grader
        # is VACUOUS if WIP_BACKUP_TMP_DIR regresses (e.g. the script
        # silently ignores it and falls back to the real /tmp) — every
        # glob below is rooted under wip_tmp, so an empty "remaining" list
        # would read as "no leak" when the true story is "the script never
        # wrote here in the first place". Prove the knob actually routed
        # the index INTO wip_tmp before ever asserting it was cleaned up.
        assert glob.glob(main_index_pattern) or glob.glob(wt_index_pattern), (
            "neither index file ever appeared under wip_tmp — WIP_BACKUP_TMP_DIR "
            "was not honoured (or this grader would be vacuously green)"
        )

        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.communicate(timeout=10)

        # proc.communicate() only confirms the TOP-LEVEL bash process
        # exited — the worktree's own snapshot code runs in a `( ... )`
        # subshell, a SEPARATE forked process in the SAME signalled group,
        # which can take a beat longer to process its own copy of SIGTERM
        # and run its own trap. Poll briefly rather than asserting the
        # instant the parent is reaped. Every glob is rooted under wip_tmp,
        # this test's own private namespace — no diffing against a
        # pre-existing snapshot is needed, and nothing here can ever see a
        # concurrent sibling's or the real cron's own file.
        cleanup_deadline = time.monotonic() + 2
        remaining_main_index = remaining_wt_index = remaining_wt = None
        while time.monotonic() < cleanup_deadline:
            remaining_main_index = glob.glob(main_index_pattern)
            remaining_wt_index = glob.glob(wt_index_pattern)
            remaining_wt = glob.glob(wt_pattern)
            if not (remaining_main_index or remaining_wt_index or remaining_wt):
                break
            time.sleep(0.05)
        assert remaining_main_index == [], f"main-tree temp index leaked: {remaining_main_index}"
        assert remaining_wt_index == [], (
            f"the WORKTREE's own temp index leaked: {remaining_wt_index}"
        )
        assert remaining_wt == [], (
            f"a wip-wt-* temp file leaked after signalled interruption: {remaining_wt}"
        )
        assert real_tmp_decoy.exists(), (
            "a foreign /tmp file (simulating the real cron) must never be touched"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)
        real_tmp_decoy.unlink(missing_ok=True)
        # wip_tmp is entirely this test's own — pytest's tmp_path cleanup
        # handles it; no /tmp sweep is needed or performed here.
        for pattern in index_glob_patterns:
            for leftover in glob.glob(pattern):
                os.remove(leftover)
        for leftover in glob.glob(wt_pattern):
            os.remove(leftover)


def test_main_tree_own_temp_index_trap_is_load_bearing_with_no_worktree_present(
    tmp_path: Path,
) -> None:
    # Round 9 acceptance finding 2 [M]: the sibling test above always adds a
    # worktree, so its own SENTINEL fires the instant the WORKTREE's `add
    # -A` is entered — which happens BEFORE the main tree's own snapshot
    # code even starts (the worktree loop runs first per repo). SIGTERM
    # lands there, at which point the main tree's `mktemp` for `tmp_index`
    # (:237 top-level `tmp_index=""` / the trap referencing it) hasn't even
    # been called yet — `main_index_pattern` is empty by construction, so
    # `assert remaining_main_index == []` was VACUOUS for that trap
    # specifically (proven: mutating the top-level trap's `[ -n "$tmp_index"
    # ] && rm -f "$tmp_index"` line away to `:` still leaves all 44 tests
    # green). This variant has NO worktree at all, so the first (and only)
    # delayed `add -A` the slow wrapper ever sees is the MAIN tree's own —
    # the sentinel can only fire there, genuinely exercising this trap.
    repo = _seed_repo(tmp_path, f"wtnowt{os.getpid()}")
    (repo / "dirty.txt").write_text("dirt\n")

    bin_dir = tmp_path / "bin"
    add_started = tmp_path / "add-started-main.sentinel"
    _slow_add_git_wrapper(bin_dir, delay=5.0, sentinel=add_started)

    # Round 10 acceptance finding 1 [M]: same as the sibling test above —
    # point the script's own mktemp calls at a private directory under
    # tmp_path rather than sharing the real /tmp with the box's live cron.
    wip_tmp = tmp_path / "wiptmp"
    wip_tmp.mkdir()
    # Round 10 acceptance finding 4 [L]: dot-anchored, never a bare
    # `{repo.name}*` prefix (no worktree here, so no dash-suffixed form
    # is needed).
    main_index_pattern = str(wip_tmp / f"wip-index-{repo.name}.*")

    proc = subprocess.Popen(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "WIP_BACKUP_TMP_DIR": str(wip_tmp),
            "HOME": str(tmp_path),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not add_started.exists():
            time.sleep(0.05)
        assert add_started.exists(), "add -A was never reached — fixture premise failed"

        # Round 11 acceptance finding 3 [L]: without this, the grader is
        # VACUOUS if WIP_BACKUP_TMP_DIR regresses — an empty "remaining"
        # list below would read as "no leak" even if the script never
        # wrote under wip_tmp in the first place. Prove the knob actually
        # routed the index there before ever asserting it was cleaned up.
        assert glob.glob(main_index_pattern), (
            "the index file never appeared under wip_tmp — WIP_BACKUP_TMP_DIR "
            "was not honoured (or this grader would be vacuously green)"
        )

        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.communicate(timeout=10)

        cleanup_deadline = time.monotonic() + 2
        remaining_main_index: list[str] = []
        while time.monotonic() < cleanup_deadline:
            remaining_main_index = glob.glob(main_index_pattern)
            if not remaining_main_index:
                break
            time.sleep(0.05)
        assert remaining_main_index == [], (
            f"main-tree temp index leaked with no worktree present: {remaining_main_index}"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)
        for leftover in glob.glob(main_index_pattern):
            os.remove(leftover)


def test_worktree_unreadable_file_does_not_lose_the_readable_ones(tmp_path: Path) -> None:
    # Finding 2 [M], part 1: `git add -A` aborts the WHOLE add on a single
    # permission error (proven: a chmod-000 file among two good ones lost
    # ALL three, not just the bad one — good1.txt/good2.txt vanished too).
    # `--ignore-errors` must let the readable files still get snapshotted.
    repo = _seed_repo(tmp_path, "wtunreadable")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtunreadable-side", str(wt))
    (wt / "good1.txt").write_text("good1\n")
    (wt / "good2.txt").write_text("good2\n")
    (wt / "denied.txt").write_text("secret\n")
    (wt / "denied.txt").chmod(0o000)

    try:
        out = _run(tmp_path)
    finally:
        (wt / "denied.txt").chmod(0o644)

    assert "partial add" in out, f"expected a partial-add log line, got: {out!r}"

    rolling, _dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1, f"expected the readable files to still be snapshotted, got {rolling}"
    names = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", f"{rolling[0]}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.splitlines()
    assert "good1.txt" in names and "good2.txt" in names, (
        f"the readable files must survive: {names}"
    )
    assert "denied.txt" not in names


def test_worktree_unborn_head_logs_one_line(tmp_path: Path) -> None:
    # Finding 2 [M], part 2: an unborn-HEAD worktree (`git worktree add
    # --orphan`) makes `read-tree HEAD` fail — proven to previously drop the
    # worktree with ZERO log lines and zero refs. Every failure path must log
    # exactly one line naming the worktree.
    repo = _seed_repo(tmp_path, "wtunborn")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "--orphan", "-b", "unbornbranch", str(wt))
    (wt / "newwork.txt").write_text("new\n")

    out = _run(tmp_path)

    skip_lines = [line for line in out.splitlines() if "beta" in line and "skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"

    no_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-beta*")
    assert no_refs == ""


def test_worktree_mktemp_failure_logs_one_line(tmp_path: Path) -> None:
    # Finding 4 [L]: mktemp's OWN stderr was unsuppressed on the worktree
    # path, so a genuine mktemp failure (disk full, permissions) leaked a raw
    # stderr line and dropped the worktree with no clean skip line.
    repo = _seed_repo(tmp_path, "wtmktemp")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtmktemp-side", str(wt))
    (wt / "change.txt").write_text("wip\n")

    bin_dir = tmp_path / "bin"
    _failing_mktemp_wrapper(bin_dir, needle="wip-index")

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    skip_lines = [line for line in out.splitlines() if "beta" in line and "skipped" in line]
    assert len(skip_lines) == 1, (
        f"expected exactly one skip line, got: out={out!r} err={proc.stderr!r}"
    )
    assert "mktemp" in skip_lines[0]
    assert proc.stderr.strip() == "", f"mktemp's own stderr must not leak raw: {proc.stderr!r}"

    no_refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/wip/wt-beta*")
    assert no_refs == ""


def test_reaper_removes_orphaned_rolling_ref_once_its_dated_ref_has_aged_out(
    tmp_path: Path,
) -> None:
    # Finding 3 [M] (round 2 acceptance): a rolling refs/wip/wt-<name> for a
    # worktree that was `worktree remove`d + pruned is otherwise IMMORTAL —
    # it pins its commit's objects forever, locally and on origin (measured
    # live: 17 live vs 30 ever-created agent worktrees in the hub). Once the
    # worktree is fully gone from `git worktree list` AND its last dated ref
    # has already aged past KEEP_DAYS, the reaper must delete it locally and
    # push the deletion. A SECOND, still-live worktree ("alpha") is required
    # in the fixture — round 3 acceptance finding 1 made the reaper fail
    # CLOSED on an empty live-ids file (a repo with zero live worktrees left
    # skips the reaper entirely, one log line, rather than treating "no
    # positive data" as "everything is orphaned"), so a single-worktree
    # version of this fixture would only prove the skip, not the reap.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtreap")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt_alpha = repo / ".claude" / "worktrees" / "alpha"
    wt_beta = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtreap-alpha", str(wt_alpha))
    _git(repo, "worktree", "add", "-q", "-b", "wtreap-beta", str(wt_beta))
    (wt_alpha / "change.txt").write_text("alpha stays\n")
    (wt_beta / "change.txt").write_text("beta goes\n")

    _run(tmp_path)
    rolling_a, _dated_a = _classify_wt_refs(repo, "alpha")
    rolling_b, dated_b = _classify_wt_refs(repo, "beta")
    assert len(rolling_a) == 1 and len(rolling_b) == 1 and len(dated_b) == 1, (
        "fixture premise: both worktrees' refs must exist after run 1"
    )
    rolling_ref_a, rolling_ref_b = rolling_a[0], rolling_b[0]
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref_b],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "fixture premise: beta's rolling ref must already be on origin"

    _git(repo, "worktree", "remove", "--force", str(wt_beta))
    _git(repo, "worktree", "prune")
    # Simulate beta's last dated ref having already aged past KEEP_DAYS and
    # been pruned by the existing age-sweep — the terminal state a real
    # orphaned rolling ref eventually reaches on its own. alpha stays live,
    # keeping wt_live_file non-empty this run.
    _git(repo, "update-ref", "-d", dated_b[0])

    out = _run(tmp_path)

    assert "reaped" in out and rolling_ref_b in out, (
        f"expected a reap log line for beta, got: {out!r}"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref_b],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    ), "beta's orphaned rolling ref must be deleted locally"
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref_b],
            cwd=origin,
            capture_output=True,
        ).returncode
        != 0
    ), "the deletion must be pushed to origin too"
    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref_a), (
        "alpha is still registered — its rolling ref must never be touched"
    )


def test_reaper_spares_rolling_ref_while_its_dated_ref_is_still_fresh(tmp_path: Path) -> None:
    # Finding 3 [M], the negative case: a worktree removed only moments ago
    # must NOT lose its rolling ref immediately — only once its newest dated
    # ref (if any) has itself aged past KEEP_DAYS. A second, still-live
    # worktree keeps wt_live_file non-empty so the reaper actually reaches
    # the age check (round 3 finding 1's fail-closed fix would otherwise
    # skip the reaper entirely here, making this assertion true for the
    # wrong reason).
    repo = _seed_repo(tmp_path, "wtreapfresh")
    _exclude_path(repo, ".claude/worktrees")
    wt_alpha = repo / ".claude" / "worktrees" / "alpha"
    wt_beta = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtreapfresh-alpha", str(wt_alpha))
    _git(repo, "worktree", "add", "-q", "-b", "wtreapfresh-beta", str(wt_beta))
    (wt_alpha / "change.txt").write_text("alpha stays\n")
    (wt_beta / "change.txt").write_text("beta goes\n")

    _run(tmp_path)
    rolling_b, _dated_b = _classify_wt_refs(repo, "beta")
    assert len(rolling_b) == 1
    rolling_ref_b = rolling_b[0]

    _git(repo, "worktree", "remove", "--force", str(wt_beta))
    _git(repo, "worktree", "prune")

    _run(tmp_path)

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref_b), (
        "a rolling ref whose dated sibling is still within KEEP_DAYS must survive"
    )


def test_reaper_never_touches_a_ref_outside_this_script_own_id_shape(tmp_path: Path) -> None:
    # The reaper must only ever consider refs/wip/wt-<name>-<id8> — its OWN
    # naming scheme. A hand-made or legacy ref that merely starts with
    # refs/wip/wt- but doesn't end in an 8-hex-char id (e.g. one crafted by
    # an operator, or predating this scheme) must never be touched, even
    # with a live worktree present (so the reaper actually runs) and no
    # dated sibling for the legacy ref either.
    repo = _seed_repo(tmp_path, "wtreapshape")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "alpha"
    _git(repo, "worktree", "add", "-q", "-b", "wtreapshape-alpha", str(wt))
    (wt / "change.txt").write_text("keeps the reaper running\n")
    _run(tmp_path)

    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/wip/wt-not-a-real-id", head)

    _run(tmp_path)

    assert _git(repo, "rev-parse", "-q", "--verify", "refs/wip/wt-not-a-real-id") == head


def test_live_registered_worktree_survives_even_with_no_dated_ref_left(tmp_path: Path) -> None:
    # Findings 1+2 (round 3 acceptance): the three-line live-ids guard
    # (`grep -qxF "$wid" "$wt_live_file" ... continue`) had ZERO coverage —
    # deleting it left the suite green, because every prior reaper test
    # either had no live worktree at all (so the NEW fail-closed skip saves
    # it, unrelated to this guard) or wasn't exercising the "still
    # registered, no dated ref" combination. This worktree is NEVER removed
    # — only its dated ref is gone — so the ONLY thing that can save its
    # rolling ref is the live-ids check itself, not the age check (which
    # alone would see zero surviving dated refs and call it eligible).
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtguard")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtguard-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]

    # The worktree is STILL fully registered — never removed or pruned.
    _git(repo, "update-ref", "-d", dated[0])

    _run(tmp_path)

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "a still-registered worktree's rolling ref must survive even with no dated sibling left"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and it must still be present on origin too"


def test_sibling_nested_worktree_survives_store_wide_live_tracking(tmp_path: Path) -> None:
    # Finding 1 [H] (round 4 acceptance): the reaper's DELETE scope is the
    # whole SHARED ref store, but the SNAPSHOT scope (and so the old
    # live-ids file) was only worktrees nested under repo_root itself — a
    # LIVE, DIRTY worktree nested under a root-level SIBLING worktree of the
    # SAME store was invisible to the "parent" repo's own live file, so the
    # parent's reaper judged it orphaned and reaped its rolling ref, locally
    # AND on origin, even while it was registered and dirty. Live shape
    # today: /opt/fabrik-lib with /opt/fabrik-lib-account and
    # /opt/fabrik-lib-review as top-level linked worktrees. Doubles as
    # finding 2's "trigger A" no-reopen grader.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    parent = _seed_repo(tmp_path, "parent")
    _git(parent, "remote", "add", "origin", str(origin))
    _exclude_path(parent, ".claude/worktrees")
    # parent needs its OWN directly-nested worktree too: otherwise parent's
    # OWN live-ids file is empty regardless of the bug (nothing at all is
    # nested directly under parent), and the (separate, legitimate) empty
    # -file skip masks whether store-wide recording does anything — the
    # same masking finding 3 found in the repo_is_worktree test.
    agentx = parent / ".claude" / "worktrees" / "agentx"
    _git(parent, "worktree", "add", "-q", "-b", "agentxbranch", str(agentx))
    (agentx / "change.txt").write_text("agent work\n")
    # aa-sidecar sorts BEFORE "parent" in the outer glob.
    sidecar = tmp_path / "aa-sidecar"
    _git(parent, "worktree", "add", "-q", "-b", "sidecarbranch", str(sidecar))
    beta = sidecar / ".claude" / "worktrees" / "beta"
    _git(parent, "worktree", "add", "-q", "-b", "betabranch", str(beta))
    (beta / "dirty.txt").write_text("dirty\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(parent, "beta")
    assert len(rolling) == 1 and len(dated) == 1, (
        "fixture premise: beta's ref must exist after run 1"
    )
    rolling_ref = rolling[0]
    # beta is NEVER removed — still registered and dirty under the sidecar.
    # Age out its dated ref so only correct store-wide live tracking (not
    # the age check, which alone would call it eligible) can save it.
    _git(parent, "update-ref", "-d", dated[0])

    out = _run(tmp_path)

    assert "reaped" not in out, (
        f"beta must never be reaped while still live under the sidecar: {out!r}"
    )
    assert _git(parent, "rev-parse", "-q", "--verify", rolling_ref), (
        "beta's rolling ref must survive — it is live under a sibling worktree of the same store"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"


def test_reaper_closes_the_empty_live_file_cost_after_worktree_removal(tmp_path: Path) -> None:
    # Finding 2 [M]: round 4's fail-closed fix (an empty live-ids file skips
    # the reaper) had an accepted cost — a repo whose LAST worktree was
    # removed would skip the reaper FOREVER (its live file stayed empty on
    # every future run too), never actually reaping the orphan. Recording
    # the store-wide enumeration (including the main entry's own id) via
    # _wip_record_live_id, combined with the enumeration-completeness gate,
    # makes a healthy run's live-ids file non-empty even with zero
    # worktrees of its own, closing this cost.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtcost")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtcost-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]

    _git(repo, "worktree", "remove", "--force", str(wt))
    _git(repo, "worktree", "prune")
    _git(repo, "update-ref", "-d", dated[0])

    for _ in range(3):
        _run(tmp_path)

    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    ), "the orphan must eventually be reaped now, not skipped forever"
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        != 0
    ), "and the deletion must be pushed to origin too"


def test_plain_repo_with_no_worktrees_logs_nothing_from_reaper(tmp_path: Path) -> None:
    # Finding 4 [M]: the "reaper skipped (no live-worktree data this run)"
    # line fired on the COMMON case — most /opt repos have zero nested
    # worktrees (measured: 39 of 45). With store-wide live tracking (every
    # worktree _wip_record_live_id sees, including the main entry) and the
    # enumeration-completeness gate in place, a plain repo's live-ids file
    # is non-empty (the main entry is always recorded) — the reaper runs,
    # finds nothing to reap, and produces NO output; the skip line is
    # reserved for the genuine anomaly (mktemp failure / a failed
    # enumeration), never the common case.
    _seed_repo(tmp_path, "plainrepo")
    out = _run(tmp_path)
    assert out == "", (
        f"a plain repo with no worktrees must log nothing from the reaper, got: {out!r}"
    )


def test_top_level_linked_worktree_repo_never_runs_the_reaper(tmp_path: Path) -> None:
    # Finding 3 [M] (round 6 acceptance), RE-GROUNDED by finding 5 (round 7
    # acceptance): the ORIGINAL claim here ("guard removed -> the sidecar's
    # own path appears in a REAP line") does not reproduce — executed with
    # repo_is_worktree disabled, the suite stays green and the reap is still
    # attributed to the true owner, because the sidecar's iteration is
    # independently blocked by the enumeration-completeness check (its
    # `.git` is a FILE, so `.git/worktrees` doesn't exist as a directory —
    # expected=1 vs the actual store-wide list of 2, "enumeration incomplete:
    # 2 of 1"). What the guard actually still does is suppress THAT skip
    # line: with it present, the sidecar's own iteration is silent (`: #
    # never reap`); without it, a "reaper skipped (enumeration incomplete...)"
    # line naming the SIDECAR's own path would be printed instead. So the
    # true, reproducing assertion is narrower: no line at all — reap or
    # skip — ever names the sidecar's path; the reap itself is correctly
    # attributed to the true owning repo.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    mainrepo = _seed_repo(tmp_path, "zparent")
    _git(mainrepo, "remote", "add", "origin", str(origin))
    _exclude_path(mainrepo, ".claude/worktrees")
    # aa-sidecar sorts BEFORE "zparent" in the outer glob.
    sidecar = tmp_path / "aa-sidecar"
    _git(mainrepo, "worktree", "add", "-q", "-b", "sidecarbranch", str(sidecar))
    gamma = sidecar / ".claude" / "worktrees" / "gamma"
    _git(mainrepo, "worktree", "add", "-q", "-b", "gammabranch", str(gamma))
    (gamma / "change.txt").write_text("gamma work\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(mainrepo, "gamma")
    assert len(rolling) == 1 and len(dated) == 1, (
        "fixture premise: gamma's ref must exist after run 1"
    )
    rolling_ref = rolling[0]

    _git(sidecar, "worktree", "remove", "--force", str(gamma))
    _git(mainrepo, "worktree", "prune")
    _git(mainrepo, "update-ref", "-d", dated[0])

    out = _run(tmp_path)

    reap_lines = [line for line in out.splitlines() if "reaped" in line and rolling_ref in line]
    assert len(reap_lines) == 1, f"expected exactly one reap line for gamma, got: {out!r}"
    assert str(mainrepo) in reap_lines[0], (
        f"the reap must be attributed to the true owning repo, not the sidecar: {reap_lines[0]!r}"
    )
    assert not any(str(sidecar) in line for line in out.splitlines()), (
        f"no line — reap or skip — may ever name the sidecar's own path: {out!r}"
    )


def test_failed_mktemp_for_live_ids_file_reaps_nothing(tmp_path: Path) -> None:
    # Finding 1 [H], trigger B: mktemp failing for the live-ids file yields
    # wt_live_file == /dev/null. The old guard (`!= /dev/null && grep ...`)
    # short-circuited FALSE in that case and fell through to reaping,
    # deleting even a still-registered worktree's rolling ref.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtmktemplive")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtmktemplive-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    # Simulate the dated ref having already aged out, so ONLY the live-ids
    # guard (not the age check) can save the rolling ref this run.
    _git(repo, "update-ref", "-d", dated[0])

    bin_dir = tmp_path / "bin"
    _failing_mktemp_wrapper(bin_dir, needle="wip-wt-live")

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "a still-registered worktree's rolling ref must survive a failed live-ids mktemp"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    )


def test_isolated_index_invariant_holds_for_worktree_snapshot(tmp_path: Path) -> None:
    # Mirrors test_snapshot_captures_all_without_touching_agent_state, but
    # for a WORKTREE: its own real index, HEAD/branch, staged list and stash
    # must be BYTE-IDENTICAL before and after, and the snapshot must still
    # hold all three states (staged, unstaged, untracked).
    repo = _seed_repo(tmp_path, "wtisolated")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtisolated-side", str(wt))

    (wt / "staged.txt").write_text("staged by sibling\n")
    subprocess.run(["git", "add", "staged.txt"], cwd=wt, check=True, timeout=15)
    (wt / "base.txt").write_text("unstaged edit\n")
    (wt / "untracked.txt").write_text("brand new\n")

    wt_git_dir = subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    real_index = Path(wt_git_dir) / "index"
    index_md5_before = subprocess.run(
        ["md5sum", str(real_index)],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    branch_before = subprocess.run(
        ["git", "symbolic-ref", "HEAD"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    staged_before = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    stash_before = subprocess.run(
        ["git", "stash", "list"],
        cwd=wt,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout

    _run(tmp_path)

    rolling, _dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1
    tree_files = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", rolling[0]],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.splitlines()
    assert {"base.txt", "staged.txt", "untracked.txt"} <= set(tree_files)
    unstaged_content = subprocess.run(
        ["git", "cat-file", "-p", f"{rolling[0]}:base.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    assert unstaged_content == "unstaged edit\n"

    index_md5_after = subprocess.run(
        ["md5sum", str(real_index)],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    assert index_md5_after == index_md5_before, "the worktree's REAL index must be byte-identical"
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wt,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        == head_before
    )
    assert (
        subprocess.run(
            ["git", "symbolic-ref", "HEAD"],
            cwd=wt,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        == branch_before
    )
    assert (
        subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=wt,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        == staged_before
    )
    assert (
        subprocess.run(
            ["git", "stash", "list"],
            cwd=wt,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
        == stash_before
    )


def test_unreadable_worktree_admin_dir_reaps_nothing(tmp_path: Path) -> None:
    # Finding 1 [M] (round 5 acceptance), proof B: `git worktree list` from
    # a non-repo exits 128 with 0 lines, but with real git 2.43 a chmod-000
    # on a WORKTREE'S OWN .git/worktrees/<id> admin dir makes the enumeration
    # silently OMIT that worktree while still exiting 0 — the old reaper
    # (bare pipe, exit status discarded) then judged the still-registered,
    # dirty worktree "removed" and reaped its rolling ref, locally and on
    # origin. The dated ref is aged out FIRST so only the
    # enumeration-completeness gate (not the age check) can save it.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtadmin")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtadmin-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    _git(repo, "update-ref", "-d", dated[0])

    admin_ids = [p.name for p in (repo / ".git" / "worktrees").iterdir()]
    assert len(admin_ids) == 1, f"fixture premise: exactly one admin dir, got {admin_ids}"
    admin_dir = repo / ".git" / "worktrees" / admin_ids[0]
    admin_dir.chmod(0o000)
    try:
        out = _run(tmp_path)
    finally:
        admin_dir.chmod(0o755)

    skip_lines = [line for line in out.splitlines() if "reaper skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "enumeration incomplete" in skip_lines[0], skip_lines[0]

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "beta's rolling ref must survive a truncated (but exit-0) enumeration"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"


def test_worktree_list_exit_nonzero_after_partial_output_reaps_nothing(tmp_path: Path) -> None:
    # Finding 1 [M]: `git worktree list --porcelain 2>/dev/null | while ...`
    # discarded git's own exit status. A shim that prints a truncated list
    # then exits 128 must be caught by the captured, exit-status-honoured
    # enumeration — never treated as "the repo has no other worktrees".
    repo = _seed_repo(tmp_path, "wtexit128")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtexit128-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    # A genuine first run (no shim) creates beta's rolling+dated ref; the
    # dated ref is then aged out so ONLY a correctly-honoured exit status
    # (not the independent age check) can save the rolling ref from a
    # subsequent truncated-then-128 enumeration.
    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    _git(repo, "update-ref", "-d", dated[0])

    bin_dir = tmp_path / "bin"
    _partial_worktree_list_git_wrapper(bin_dir, keep_lines=3)  # keeps only the main entry's block

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    assert "reaped" not in out, (
        f"a truncated-then-128 enumeration must never reap anything: {out!r}"
    )
    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "beta's rolling ref must survive an enumeration that exited non-zero"
    )


def test_worktree_list_exit_nonzero_after_complete_output_reaps_nothing(tmp_path: Path) -> None:
    # Finding 5 [L] (round 8 acceptance): `wt_enum_ok` (the captured exit
    # status of `git worktree list --porcelain`) is load-bearing but had no
    # test of its own — the existing partial-output test above is caught by
    # the COUNT check (`grep -c '^worktree '` against the admin-dir-derived
    # expected), never by the exit status itself, so a mutant that sets
    # `wt_enum_ok=1` unconditionally (ignoring git's real exit code) would
    # sail through it whenever the printed list happens to be complete. This
    # shim isolates exactly that: the COMPLETE, untruncated list, but git
    # itself still exits non-zero — only honouring the exit status (not the
    # count) can catch it.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtenumok")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtenumok-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    # A genuine first run (no shim) creates beta's rolling+dated ref, then
    # remove+prune the worktree so it becomes a genuine orphan candidate,
    # and age its dated ref out — a shim that let this repo's reaper
    # proceed anyway (mutant: wt_enum_ok=1 unconditionally) would reap it,
    # despite the list's own exit code saying the call failed.
    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    _git(repo, "worktree", "remove", "--force", str(wt))
    _git(repo, "worktree", "prune")
    _git(repo, "update-ref", "-d", dated[0])

    bin_dir = tmp_path / "bin"
    _complete_but_failing_worktree_list_git_wrapper(bin_dir)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    assert "reaped" not in out, (
        f"a complete-but-exit-nonzero enumeration must never reap anything: {out!r}"
    )
    skip_lines = [line for line in out.splitlines() if "reaper skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "exited non-zero" in skip_lines[0], skip_lines[0]
    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "the orphan's rolling ref must survive a complete-but-exit-nonzero enumeration"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"


def test_readonly_live_ids_file_reaps_nothing(tmp_path: Path) -> None:
    # Round 9 acceptance finding 7 [L] (pool item, agreed): the live-ids
    # append (`echo "$wt_id" >> "$wt_live_file"`) silently discarded its own
    # failure (`2>/dev/null`, no exit-status check) — a readable, non-empty
    # live-ids file that is nonetheless MISSING lines (e.g. an ENOSPC on
    # /tmp mid-run) was indistinguishable from a genuinely complete one to
    # every existing FAILS-CLOSED check (only /dev/null, `wt_enum_complete`
    # and `-r` were ever consulted), so a live, dirty worktree's rolling ref
    # could be wrongly reaped. Same shape as the enumeration-incomplete
    # test above, but for the WRITE side: the live-ids file is made
    # read-only the instant it is created, so every `_wip_record_live_id`
    # append fails — a genuine orphan elsewhere in this repo must survive,
    # exactly as it would if the enumeration itself had come back short.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, f"wtliveronly{os.getpid()}")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtliveronly-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    # A genuine first run (no shim) creates beta's rolling+dated ref, then
    # remove+prune the worktree so it becomes a genuine orphan candidate,
    # and age its dated ref out — a mutant that ignored the append's own
    # failure would reap it despite the live-ids file being incomplete.
    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    _git(repo, "worktree", "remove", "--force", str(wt))
    _git(repo, "worktree", "prune")
    _git(repo, "update-ref", "-d", dated[0])

    bin_dir = tmp_path / "bin"
    _readonly_after_mktemp_wrapper(bin_dir, needle="wip-wt-live")

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    assert "reaped" not in out, (
        f"a read-only (incomplete) live-ids file must never reap anything: {out!r}"
    )
    skip_lines = [line for line in out.splitlines() if "reaper skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "live-ids incomplete" in skip_lines[0], skip_lines[0]
    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "the orphan's rolling ref must survive a read-only (incomplete) live-ids file"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"


def test_push_queue_mktemp_failure_logs_one_line(tmp_path: Path) -> None:
    # Finding 2 [M]: a failed mktemp for the PUSH QUEUE fell back to
    # /dev/null; refspecs were echoed into it via `[ -n "$wt_push_file" ]`
    # (always true — "/dev/null" is a non-empty string), so the discard was
    # silent, contradicting the header's "every failure path logs exactly
    # one line". Local snapshotting must still work; nothing reaches origin.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtpushq")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtpushq-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    bin_dir = tmp_path / "bin"
    _failing_mktemp_wrapper(bin_dir, needle="wip-wt-push")

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    skip_lines = [line for line in out.splitlines() if "pushes skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one push-queue-skip line, got: out={out!r}"
    assert "mktemp failed for push queue" in skip_lines[0]

    rolling, _dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1, (
        "the worktree must still be snapshotted locally despite the push-queue failure"
    )
    on_origin = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "refs/wip/wt-*"],
        cwd=origin,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    assert on_origin == "", "nothing must have reached origin"


def test_stalled_push_never_costs_the_main_tree_its_snapshot(tmp_path: Path) -> None:
    # Round 9 acceptance finding 1 [H] REGRESSION grader: the worktree leg's
    # `git push` runs BEFORE the main-tree snapshot ("Anything to protect?"
    # / read-tree / add -A / update-ref refs/wip/autobackup), and neither
    # push site had a `timeout` — an unbounded network stall there left the
    # main tree's own dirt completely unprotected (refs/wip/autobackup never
    # created) and, under the cron's own `flock -n`, would wedge every LATER
    # repo in a real run too. Both push sites are now `timeout
    # "$WIP_BACKUP_PUSH_TIMEOUT" git push …`; this test overrides that env
    # var to a small value so a 600s-sleeping push shim still lets the
    # WHOLE script complete in a few seconds, and asserts the main tree's
    # snapshot happened despite the worktree's push never returning.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, f"wtpushbound{os.getpid()}")
    _git(repo, "remote", "add", "origin", str(origin))
    (repo / "dirty.txt").write_text("dirt\n")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtpushbound-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    bin_dir = tmp_path / "bin"
    _slow_push_git_wrapper(bin_dir, delay=600.0)

    # Round 10 acceptance finding 5 [L]: `subprocess.run(..., timeout=30)`
    # with no `start_new_session` only kills the TOP-LEVEL bash process on
    # its own TimeoutExpired path — the shim's `sleep 600` is a GRANDCHILD
    # (spawned by `git`, spawned by bash) in no special process group, so a
    # failure here (the bound not firing as expected) would leave an
    # orphaned `sleep 600` running for the full 10 minutes. Use Popen with
    # its own session so the whole tree can be reaped via killpg either way.
    start = time.monotonic()
    proc = subprocess.Popen(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
            "WIP_BACKUP_PUSH_TIMEOUT": "2",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        stdout, stderr = proc.communicate(timeout=5)
        raise
    elapsed = time.monotonic() - start
    assert proc.returncode == 0, stderr
    # Two bounded push sites at most, ~2s each, plus normal overhead — well
    # under the 600s the shim sleeps for, proving the bound actually fired
    # rather than the real push eventually succeeding some other way.
    assert elapsed < 30, f"run took {elapsed:.1f}s — the push bound did not fire (shim sleeps 600s)"

    autobackup = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert autobackup.returncode == 0, (
        "refs/wip/autobackup must exist — the main tree's own snapshot must "
        f"still happen despite the worktree's push stalling; run took {elapsed:.1f}s, "
        f"stdout={stdout!r}"
    )

    # Round 11 acceptance finding 1 [M]: `if ! cmd; then rc=$?; fi` reads $?
    # AFTER the `!`-negated conditional itself already ran, so it is always
    # 0 inside the then-branch — the exit-124 ("timed out") branch at BOTH
    # push sites was dead code; every timeout, real or not, logged the
    # generic "failed … (offline/auth?)" line instead. This 600s shim with
    # a 2s bound guarantees a real timeout (exit 124) at both sites.
    assert "timed out after 2s" in stdout, (
        f"a genuine push timeout (exit 124) must say so distinctly, not "
        f"read as a generic offline/auth failure; stdout={stdout!r}"
    )
    assert "(offline/auth?)" not in stdout, (
        f"a timeout must never ALSO log the generic failure line; stdout={stdout!r}"
    )


def test_failed_push_to_a_bad_remote_logs_the_plain_failure_line(tmp_path: Path) -> None:
    # Round 11 acceptance finding 1 [M], the sibling case: a push that
    # fails for a reason OTHER than the timeout (here, a remote URL that
    # can never be reached) must still log the plain "(offline/auth?)"
    # line, not "timed out" — proving the fixed `push_rc` capture
    # distinguishes the two causes correctly in BOTH directions, not just
    # by making the timeout branch reachable.
    #
    # Round 12 acceptance finding 1 [L]: the WORKTREE leg's own generic
    # line (a SEPARATE echo from the main tree's, scripts/wip_backup.sh
    # "push failed for … worktrees (offline/auth?)") was UNGRADED — this
    # fixture originally had no linked worktree at all, so only the main
    # leg's echo was ever exercised; silencing the worktree leg's line on
    # a copy still left the suite green. Add a dirty linked worktree (same
    # shape as test_stalled_push_never_costs_the_main_tree_its_snapshot)
    # so BOTH push sites fail against the same unreachable remote.
    repo = _seed_repo(tmp_path, f"wtbadremote{os.getpid()}")
    _git(repo, "remote", "add", "origin", "https://127.0.0.1:1/definitely-not-a-real-remote.git")
    (repo / "dirty.txt").write_text("dirt\n")
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtbadremote-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": "/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
            "WIP_BACKUP_PUSH_TIMEOUT": "5",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "(offline/auth?)" in proc.stdout, (
        f"expected the plain failure line, got: {proc.stdout!r}"
    )
    assert "worktrees (offline/auth?)" in proc.stdout, (
        f"expected the WORKTREE leg's own generic failure line too, got: {proc.stdout!r}"
    )
    assert "timed out after" not in proc.stdout, (
        f"a plain connection failure must never be misreported as a timeout: {proc.stdout!r}"
    )


def _run_with_push_timeout_override(tmp_path: Path, override: str) -> tuple[Path, Path]:
    # Shared fixture for round 10 acceptance finding 3 [L]'s two graders: a
    # dirty main tree, a real (fast) bare origin, and a `timeout` shim on
    # PATH that records the FIRST argument it was actually invoked with —
    # letting a test observe what WIP_BACKUP_PUSH_TIMEOUT validation
    # produced without waiting out any real bound. Returns (repo, capture_file).
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, f"wtpushval{os.getpid()}")
    _git(repo, "remote", "add", "origin", str(origin))
    (repo / "dirty.txt").write_text("dirt\n")

    bin_dir = tmp_path / "bin"
    capture_file = tmp_path / "timeout-args.txt"
    _timeout_arg_capture_wrapper(bin_dir, capture_file)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
            "WIP_BACKUP_PUSH_TIMEOUT": override,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return repo, capture_file


def test_non_numeric_push_timeout_falls_back_to_the_real_default(tmp_path: Path) -> None:
    # Round 10 acceptance finding 3 [L]: `WIP_BACKUP_PUSH_TIMEOUT=abc` (or
    # any non-numeric value, e.g. `-5`) makes GNU `timeout` itself exit
    # non-zero BEFORE `git push` ever runs — the push silently never
    # happens at all, logged identically to an offline/auth failure. The
    # validation case-statement must normalize it back to 120 up front.
    repo, capture_file = _run_with_push_timeout_override(tmp_path, "abc")

    captured = capture_file.read_text().splitlines() if capture_file.exists() else []
    assert captured and all(v == "120" for v in captured), (
        f"expected every timeout invocation to use the validated default 120, got: {captured}"
    )
    autobackup_on_origin = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
        cwd=repo.parent / "origin.git",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert autobackup_on_origin.returncode == 0, (
        "the push must actually reach origin — a non-numeric override must never silently skip it"
    )


def test_zero_push_timeout_falls_back_to_the_real_default(tmp_path: Path) -> None:
    # Round 10 acceptance finding 3 [L]: `WIP_BACKUP_PUSH_TIMEOUT=0` is GNU
    # `timeout`'s OWN "no limit" sentinel — passed through unvalidated, it
    # silently re-introduces the exact unbounded push round 9 finding 1
    # fixed. The validation case-statement must normalize `0` back to 120.
    repo, capture_file = _run_with_push_timeout_override(tmp_path, "0")

    captured = capture_file.read_text().splitlines() if capture_file.exists() else []
    assert captured and all(v == "120" for v in captured), (
        f"expected every timeout invocation to use the validated default 120 (never the literal 0), got: {captured}"
    )
    autobackup_on_origin = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
        cwd=repo.parent / "origin.git",
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert autobackup_on_origin.returncode == 0, "the push must actually reach origin"


def test_relative_tmp_dir_falls_back_to_the_real_default(tmp_path: Path) -> None:
    # Round 11 acceptance finding 2 [L]: the main loop `cd`s into each repo
    # before every mktemp call, so a RELATIVE `WIP_BACKUP_TMP_DIR` (e.g.
    # "tmp") resolves to <repo>/tmp — the isolated temp index (and its own
    # lockfile) then land INSIDE the repo's own working tree, where the
    # very next `git add -A` in the SAME run indexes them into the
    # snapshot it was never meant to be part of. Reject anything that
    # isn't an absolute path.
    # A "tmp" dir must already exist under the repo for the bug to actually
    # manifest — `mktemp` does not create missing parent directories, so
    # without one the relative path just fails closed (mktemp itself
    # errors, the repo is skipped) and the vulnerable path is never
    # exercised at all. Plenty of real repos legitimately have one.
    repo = _seed_repo(tmp_path, f"wtreltmp{os.getpid()}")
    (repo / "tmp").mkdir()
    (repo / "dirty.txt").write_text("dirt\n")

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": "/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
            "WIP_BACKUP_TMP_DIR": "tmp",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr

    tree = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "refs/wip/autobackup"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    assert "wip-index-" not in tree, (
        f"a relative WIP_BACKUP_TMP_DIR must never let the temp index land "
        f"inside the repo and get committed into the snapshot, got tree: {tree!r}"
    )
    assert list((repo / "tmp").iterdir()) == [], (
        "the fixture's own <repo>/tmp dir must stay untouched — with the fix, "
        "the script never writes into it at all (falls back to the real /tmp)"
    )


def test_unreadable_worktrees_parent_admin_dir_reaps_nothing(tmp_path: Path) -> None:
    # Finding 1 [M] (round 6 acceptance): the `.git/worktrees`-UNREADABLE
    # guard itself had no grader — deleting that elif on a copy still left
    # 37/37 green. With the PARENT admin dir at chmod 000, `git worktree
    # list` prints only the main entry at exit 0 while a naive `ls -1` on
    # the unreadable dir also yields 0 (permission denied, suppressed) —
    # expected=1 matches actual=1, a compensating miscount that reads as
    # "complete" without the explicit unreadable-parent check.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtparentadmin")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtparentadmin-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    _git(repo, "update-ref", "-d", dated[0])

    admin_parent = repo / ".git" / "worktrees"
    admin_parent.chmod(0o000)
    try:
        out = _run(tmp_path)
    finally:
        admin_parent.chmod(0o755)

    skip_lines = [line for line in out.splitlines() if "reaper skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "unreadable" in skip_lines[0], skip_lines[0]

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "beta's rolling ref must survive with the parent admin dir unreadable"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"


def test_grep_c_empty_output_never_produces_a_two_line_count(tmp_path: Path) -> None:
    # Finding 3 [L]: `grep -c ... || echo 0` prints TWO lines when grep
    # itself finds zero matches (grep -c still prints "0" and exits 1 —
    # `|| echo 0` then ALSO fires, appending a second "0"), the same
    # unprefixed-continuation-line defect class already fixed for
    # wt_add_err. A `git` shim whose `worktree list --porcelain` succeeds
    # (exit 0) but prints NOTHING at all forces `grep -c '^worktree '` on
    # the captured file to hit exactly this zero-match case.
    _seed_repo(tmp_path, "wtgrepc")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "worktree" ] && [ "$2" = "list" ]; then exit 0; fi\n'
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    # `out.splitlines()` would itself mask a stray unprefixed continuation
    # line (it only contains "reaper skipped" on the FIRST of the two lines
    # the bug produces) — count total output lines instead: exactly one
    # line total proves no orphaned "0 of 1)"-style second line leaked out.
    lines = out.splitlines()
    assert len(lines) == 1, f"expected exactly one total output line, got: {out!r}"
    assert "reaper skipped" in lines[0] and "\n" not in lines[0]


def test_junk_admin_dir_without_gitdir_file_does_not_disable_the_reaper(tmp_path: Path) -> None:
    # Finding 4 [L]: `ls -1 .git/worktrees | wc -l` counts every admin
    # SUBDIR, including one git itself already treats as prunable (no
    # `gitdir` file inside) — that permanently over-counts the denominator,
    # disabling the reaper for this repo until someone runs `git worktree
    # prune` by hand. A hand-made junk dir with no `gitdir` file must be
    # excluded from the count, so a GENUINE orphan elsewhere still gets
    # reaped.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtjunkadmin")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtjunkadmin-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]

    _git(repo, "worktree", "remove", "--force", str(wt))
    _git(repo, "worktree", "prune")
    _git(repo, "update-ref", "-d", dated[0])

    junk = repo / ".git" / "worktrees" / "junkdir"
    junk.mkdir(parents=True)
    (junk / "somefile").write_text("not a gitdir file\n")

    out = _run(tmp_path)

    assert "reaped" in out and rolling_ref in out, (
        f"expected the genuine orphan to still be reaped, got: {out!r}"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    )


def test_junk_admin_dir_with_empty_gitdir_file_does_not_disable_the_reaper(tmp_path: Path) -> None:
    # Finding 4 [L] (round 8 acceptance): `[ -f "$wt_admin_entry/gitdir" ]`
    # counts an admin dir whose `gitdir` file EXISTS but is EMPTY (0 bytes)
    # — left behind by e.g. a crashed `git worktree add` — which `git
    # worktree list` never enumerates (an empty gitdir resolves to nothing).
    # Unlike the sibling test above (a junk dir with NO gitdir file at all,
    # already excluded by `-f`), a `-f` check alone counts this one FOREVER:
    # "enumeration incomplete: N of N+1" on every single tick, disabling the
    # reaper for this repo permanently — no `git worktree prune` clears an
    # admin dir git itself still considers a worktree entry with an
    # (empty) gitdir file present. `-s` (non-empty) excludes it, so a
    # GENUINE orphan elsewhere still gets reaped.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtemptygitdir")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtemptygitdir-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]

    _git(repo, "worktree", "remove", "--force", str(wt))
    _git(repo, "worktree", "prune")
    _git(repo, "update-ref", "-d", dated[0])

    ghost = repo / ".git" / "worktrees" / "ghostdir"
    ghost.mkdir(parents=True)
    (ghost / "gitdir").write_text("")  # exists, but empty — git worktree list never enumerates this

    out1 = _run(tmp_path)
    assert "reaped" in out1 and rolling_ref in out1, (
        f"an empty-but-present gitdir file must not over-count the denominator "
        f"forever, got: {out1!r}"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    )

    # Prove it is not a one-shot fluke of ordering: run again, the ghost
    # admin dir with its empty gitdir file is still there, and the reaper
    # must still be able to run (no "enumeration incomplete" skip line).
    out2 = _run(tmp_path)
    assert not any("enumeration incomplete" in line for line in out2.splitlines()), out2


def test_foreign_dated_ref_sharing_a_wid_prefix_does_not_pin_an_orphan_forever(
    tmp_path: Path,
) -> None:
    # Round 9 acceptance finding 6 [L]: the newest-dated-ref lookup globs
    # `refs/wip/wt-$wid-*` — a PREFIX match, not an exact-segment one. A
    # worktree literally named "<this wid>-<its own 8hex id>" has its own
    # refs (rolling AND dated) ALSO start with `refs/wip/wt-$wid-`, so they
    # leak into `head -1`'s pick before the (pre-fix) tail-only shape check
    # ever ran. Rather than relying on a real second worktree's sha1 hash
    # to collide by luck, plant a FOREIGN ref directly at the exact shape
    # the finding describes: refs/wip/wt-<real wid>-deadbeef-<far-future
    # timestamp> — its OWN tail segment ("<8 digits>T<6 digits>Z") passes
    # the OLD tail-only shape check, and being dated far in the future it
    # always reads as "still within KEEP_DAYS", permanently blocking the
    # age check and pinning an otherwise-genuine orphan forever.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, f"wtwidcollide{os.getpid()}")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtwidcollide-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    real_wid = rolling_ref[len("refs/wip/wt-") :]  # "beta-<real 8hex id>"

    # Make beta a genuine orphan candidate: remove + prune the worktree,
    # and delete its OWN real dated ref (so nothing legitimate protects it).
    _git(repo, "worktree", "remove", "--force", str(wt))
    _git(repo, "worktree", "prune")
    _git(repo, "update-ref", "-d", dated[0])

    # Plant the foreign, far-future-dated ref sharing beta's wid as a
    # PREFIX. "deadbeef" stands in for a second worktree's own 8hex id.
    head = _git(repo, "rev-parse", "HEAD")
    foreign_dated_ref = f"refs/wip/wt-{real_wid}-deadbeef-20991231T235959Z"
    _git(repo, "update-ref", foreign_dated_ref, head)

    out = _run(tmp_path)

    assert "reaped" in out and rolling_ref in out, (
        f"a foreign ref sharing this wid as a PREFIX must never pin the "
        f"genuine orphan forever, got: {out!r}"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=repo,
            capture_output=True,
        ).returncode
        != 0
    ), "beta's orphaned rolling ref must actually be gone"
    # The foreign ref itself is untouched — it belongs to a different wid
    # (a different, still-registered-in-spirit worktree in this scenario),
    # never something THIS wid's reap pass should delete.
    assert _git(repo, "rev-parse", "-q", "--verify", foreign_dated_ref), (
        "the foreign ref must be left alone — it is not beta's own"
    )


def test_worktree_name_starting_with_grep_option_char_survives_the_reaper(tmp_path: Path) -> None:
    # Finding 1 [H] (round 7 acceptance): `grep -qxF "$wid" "$wt_live_file"`
    # passed $wid unguarded. The sanitiser maps every non-[A-Za-z0-9._-]
    # character to "-", so a worktree basename STARTING with such a
    # character (e.g. "@beta") yields wid="-beta-<id8>" — grep parses a
    # leading "-" as OPTIONS, not a pattern, and exits 1 (never an error,
    # so nothing was ever logged) with no match. A live, dirty worktree's
    # rolling ref was reaped end-to-end: deleted locally and queued for
    # deletion on origin. Its dated ref is aged out across THREE runs so
    # the bug (if present) has every opportunity to fire.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtatname")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "@beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtatname-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "-beta")
    assert len(rolling) == 1 and len(dated) == 1, (
        "fixture premise: @beta's ref must exist after run 1"
    )
    rolling_ref = rolling[0]
    _git(repo, "update-ref", "-d", dated[0])

    for _ in range(3):
        out = _run(tmp_path)
        assert "reaped" not in out, (
            f"@beta must never be reaped while still live and dirty: {out!r}"
        )

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "@beta's rolling ref must survive across every run"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"


def test_live_ids_file_vanishing_mid_reap_loop_reaps_nothing(tmp_path: Path) -> None:
    # Finding 2 [M] (round 7 acceptance): grep's rc=2 (the live-ids file
    # gone or unreadable) was indistinguishable from rc=1 (genuinely not
    # found) — both fell through to "not live", so the FAILS-CLOSED
    # invariant did not actually hold across the reaper's own loop. A `git`
    # shim removes the live-ids file at the exact moment the reaper's OWN
    # `for-each-ref refs/wip/wt-*` enumeration call runs, emulating it
    # vanishing mid-loop; a still-registered, dirty worktree must survive.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, timeout=15)

    repo = _seed_repo(tmp_path, "wtvanish")
    _git(repo, "remote", "add", "origin", str(origin))
    _exclude_path(repo, ".claude/worktrees")
    wt = repo / ".claude" / "worktrees" / "beta"
    _git(repo, "worktree", "add", "-q", "-b", "wtvanish-side", str(wt))
    (wt / "change.txt").write_text("v1\n")

    _run(tmp_path)
    rolling, dated = _classify_wt_refs(repo, "beta")
    assert len(rolling) == 1 and len(dated) == 1
    rolling_ref = rolling[0]
    _git(repo, "update-ref", "-d", dated[0])

    # Round 8 acceptance finding 6: `rm -f /tmp/wip-wt-live.*` was an
    # UNANCHORED global glob — on this 3-session hub a live-ids file
    # belonging to a totally unrelated CONCURRENT process (another
    # session's own run of this script, or of this very test) could match
    # and get deleted as collateral damage (reproduced: a decoy file
    # created before this test started was swept away by the shim). Round
    # 10 acceptance finding 1 [M]: pre-existing-set diffing narrowed but
    # never closed this — the live-ids file carries no repo name or pid,
    # so a decoy created DURING the window (the live cron, not just one
    # that pre-existed) was still misread as ours. Route the script's own
    # mktemp through a private directory under THIS test's tmp_path
    # instead — the shim only ever sees files that live there.
    wip_tmp = tmp_path / "wiptmp"
    wip_tmp.mkdir()
    live_pattern = str(wip_tmp / "wip-wt-live.*")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "for-each-ref" ] && [ "$3" = "refs/wip/wt-*" ]; then\n'
        f"    rm -f {live_pattern} 2>/dev/null\n"
        "fi\n"
        'exec /usr/bin/git "$@"\n'
    )
    wrapper.chmod(0o755)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "WIP_BACKUP_ROOT": str(tmp_path),
            "WIP_BACKUP_TMP_DIR": str(wip_tmp),
            "HOME": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    skip_lines = [line for line in out.splitlines() if "reaper skipped" in line]
    assert len(skip_lines) == 1, f"expected exactly one skip line, got: {out!r}"
    assert "vanished" in skip_lines[0], skip_lines[0]

    assert _git(repo, "rev-parse", "-q", "--verify", rolling_ref), (
        "beta's rolling ref must survive a live-ids file vanishing mid-reap-loop"
    )
    assert (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", rolling_ref],
            cwd=origin,
            capture_output=True,
        ).returncode
        == 0
    ), "and must still be present on origin too"
