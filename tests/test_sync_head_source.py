"""The sync distributes COMMITTED bytes, never the hub's working tree (T12.17, 01M1Y86PQ).

This script is the fleet-distribution mechanism and it copied whatever was on disk: an uncommitted
edit — mine, or a sibling's, on a tree three sessions share — shipped to every project. Measured on
2026-09-07: 48 copies carried one. A project then holds a file that exists in no commit anywhere,
and `check_synced_unmodified.py` compares project copies against the hub's HEAD, so the project
reds for a divergence it did not cause.

Every test calls the REAL `_head_source` / `_atomic_copy` — re-implementing them here would grade a
copy while production drifted, which is the defect the sibling suite's own header warns about.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

# the tree this test file LIVES IN — never a hardcoded absolute. With `/opt/fabrik` pinned
# here, a red-on-revert run against a copied tree silently graded the LIVE script and went
# green on a reverted copy sitting right beside it.
REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sync_enforcement_to_projects.py"


def _mod():
    # REGISTER before exec: the module defines @dataclass classes, and `dataclasses` resolves
    # `sys.modules[cls.__module__].__dict__` during decoration — an unregistered module raises
    # `AttributeError: 'NoneType' object has no attribute '__dict__'` there, which reads like a
    # defect in the script under test rather than in the loader.
    name = "sync_head_src"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


@pytest.fixture(autouse=True)
def _pop_the_module_after_each_test():
    """Leave no module behind. The sibling file added in this same range
    (`test_scratch_sweep_sync_materialised.py`) pops its module on teardown and this one did not —
    dead state in `sys.modules` for the rest of the pytest process, and an asymmetry between two
    files written the same hour. Low risk here (the name is unique), fixed because the review
    asked whether it was deliberate and the honest answer was no."""
    yield
    sys.modules.pop("sync_head_src", None)


@pytest.fixture
def hub(tmp_path: Path):
    """A throwaway 'hub' with one committed synced file and one untracked one."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(tmp_path), "config", *cfg], check=True)
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    committed = tmp_path / "scripts" / "enforcement" / "committed.py"
    committed.write_text("COMMITTED = 1\n", encoding="utf-8")
    committed.chmod(0o755)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    untracked = tmp_path / "scripts" / "enforcement" / "untracked.py"
    untracked.write_text("UNTRACKED = 1\n", encoding="utf-8")
    mod = _mod()
    # the module has ONE hub-root constant (a second one, `_HUB_ROOT`, was removed in review:
    # two sources of truth for the same path meant a change to one left `_head_source` reading
    # git in the wrong tree and silently shipping the working tree again).
    mod.FABRIK_ROOT = tmp_path
    mod._head_drift.clear()
    return mod, tmp_path, committed, untracked


def test_an_uncommitted_edit_does_not_ship(hub, tmp_path: Path) -> None:
    """The defect, reproduced: dirty the tracked file and the sync must still carry HEAD's bytes."""
    mod, hub_root, committed, _untracked = hub
    committed.write_text("COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8")
    dest = tmp_path / "out" / "committed.py"
    mod._atomic_copy(committed, dest)
    assert dest.read_text() == "COMMITTED = 1\n", (
        "the hub's uncommitted edit shipped to a project — this is the 48-copy incident"
    )


def test_the_drift_is_named_not_swallowed(hub, tmp_path: Path) -> None:
    """Syncing HEAD silently while the operator looks at their own unsynced edit would trade one
    surprise for a quieter one, so every drifting path is recorded for the run's report."""
    mod, _hub_root, committed, _untracked = hub
    committed.write_text("COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8")
    mod._atomic_copy(committed, tmp_path / "out" / "committed.py")
    assert "scripts/enforcement/committed.py" in mod._head_drift


def test_a_clean_tracked_file_records_no_drift(hub, tmp_path: Path) -> None:
    """A false drift line is as bad as a missing one — it would fire on every ordinary sync."""
    mod, _hub_root, committed, _untracked = hub
    mod._atomic_copy(committed, tmp_path / "out" / "committed.py")
    assert mod._head_drift == set()


def test_an_untracked_source_still_ships_the_working_tree(hub, tmp_path: Path) -> None:
    """A new script on its first sync has no HEAD blob, and the working tree is all there is. That
    path stays — it is not an error, and refusing it would make a new check undistributable."""
    mod, _hub_root, _committed, untracked = hub
    dest = tmp_path / "out" / "untracked.py"
    mod._atomic_copy(untracked, dest)
    assert dest.read_text() == "UNTRACKED = 1\n"
    assert mod._head_drift == set(), "an untracked file cannot 'differ from HEAD'"


def test_the_executable_bit_survives_the_head_read(hub, tmp_path: Path) -> None:
    """`shutil.copy2` carried the mode; reading bytes from git does not, so the mode comes from
    `git ls-tree HEAD`. A synced hook that lands 644 does not run."""
    mod, _hub_root, committed, _untracked = hub
    dest = tmp_path / "out" / "committed.py"
    mod._atomic_copy(committed, dest)
    assert stat.S_IMODE(os.stat(dest).st_mode) & 0o111, f"lost +x: {oct(os.stat(dest).st_mode)}"
    # ...and it is GIT's mode, not the local file's. `shutil.copy2` carried the source's full mode;
    # git records only 100644/100755, so a source that is 0o775 on this box (a umask artifact git
    # never tracked and a fresh clone never has) now arrives 0o755 — what CI would check out.
    # Measured live when this landed on `.claude/hooks/final_gate_stop.py`.
    committed.chmod(0o775)
    dest2 = tmp_path / "out2" / "committed.py"
    mod._atomic_copy(committed, dest2)
    assert stat.S_IMODE(os.stat(dest2).st_mode) == 0o755, (
        f"expected git's 100755, got {oct(stat.S_IMODE(os.stat(dest2).st_mode))} — the local "
        "umask must not ride the sync into 46 repos"
    )


def test_a_source_outside_the_hub_is_left_alone(hub, tmp_path: Path) -> None:
    """`_head_source` must not try to read git for a path that is not in the hub tree at all."""
    mod, _hub_root, _committed, _untracked = hub
    outsider = tmp_path.parent / "outsider.py"
    outsider.write_text("OUTSIDE = 1\n", encoding="utf-8")
    try:
        assert mod._head_source(outsider) is None
    finally:
        outsider.unlink(missing_ok=True)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))


# ── found by the Phase E review: three ways the HEAD-bytes writer broke the sync's own machinery ──


def test_the_ledger_records_what_ships_not_what_is_on_disk(hub, tmp_path: Path) -> None:
    """The worktree ledger records "last known good content" and `_copy_into_worktree_safely`
    refuses to refresh a copy whose hash does not match that record. Recording the WORKING-TREE
    hash while WRITING HEAD bytes froze every drifted file's project copy behind a false "agent
    edit" WARN — permanently, including after the operator committed and re-ran exactly as the
    drift report instructs. One definition (`_shipped_hash`) now feeds both sides."""
    mod, _hub_root, committed, _untracked = hub
    committed.write_text("COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8")
    dest = tmp_path / "out" / "committed.py"
    mod._atomic_copy(committed, dest)
    assert mod._shipped_hash(committed) == mod.compute_file_hash(dest), (
        "the ledger would record a hash that disagrees with the bytes on disk"
    )


def test_the_shipped_hash_falls_back_for_an_untracked_source(hub, tmp_path: Path) -> None:
    """An untracked file has no HEAD blob, so what ships IS the working tree — and the hash must
    say so, or the fallback path inherits the same disagreement."""
    mod, _hub_root, _committed, untracked = hub
    dest = tmp_path / "out" / "untracked.py"
    mod._atomic_copy(untracked, dest)
    assert mod._shipped_hash(untracked) == mod.compute_file_hash(dest)


def test_the_mtime_is_carried_or_the_sync_blocks_itself_forever(hub, tmp_path: Path) -> None:
    """`shutil.copy2` carried content + mode + MTIME. Reading bytes from git carries the first two,
    and the third is not cosmetic: `sync_single_file` skips a copy whose `dest_mtime >
    source_mtime` ("destination newer"). A dest written with mtime=now refuses every later sync of
    that file — permanently, because `git commit` does not touch the working file's mtime."""
    mod, _hub_root, committed, _untracked = hub
    # ⚠️ THE SOURCE'S MTIME IS PINNED OLD, and the assertion is EQUALITY, not "within a second".
    # The first cut of this grader compared two files both created inside this test, so their
    # mtimes were within the same wall-clock second whether or not the code carried anything —
    # executed with `os.utime` neutered in BOTH writers, it still passed (round 3 of the Phase E
    # review). A tolerance wider than the thing you are measuring is not a grader.
    old = 1_000_000_000  # 2001-09-09, unmistakably not "now"
    os.utime(committed, (old, old))
    dest = tmp_path / "out" / "committed.py"
    mod._atomic_copy(committed, dest)
    assert dest.stat().st_mtime == committed.stat().st_mtime == old, (
        f"dest {dest.stat().st_mtime} vs source {committed.stat().st_mtime} — a dest stamped "
        "'now' makes the 'destination newer' guard refuse every later sync of this file, forever"
    )
    # and the byte-level writer, which `sync_single_file` uses and no grader reached before
    head = mod._head_source(committed)
    dest2 = tmp_path / "out2" / "committed.py"
    mod._atomic_write(head[0], head[1], dest2, source=committed)
    assert dest2.stat().st_mtime == committed.stat().st_mtime == old


def test_every_dry_run_branch_reports_drift(hub, tmp_path: Path) -> None:
    """The dry-run HEAD consult sat in ONE branch, so `--dry-run --force` — precisely how an
    operator previews the forced sync the contract tells them to run — and a brand-new file both
    reported no drift at all. The consult is hoisted above every branch."""
    mod, _hub_root, committed, _untracked = hub
    committed.write_text("COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8")
    for label, kwargs, make_dest in (
        ("exists+older", {"dry_run": True}, True),
        ("--force", {"dry_run": True, "force": True}, True),
        ("new file", {"dry_run": True}, False),
    ):
        mod._head_drift.clear()
        dest = tmp_path / label.replace("+", "_").replace("-", "") / "committed.py"
        if make_dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("old\n")
            os.utime(dest, (1, 1))
        mod.sync_single_file(committed, dest, **kwargs)
        assert mod._head_drift, f"{label}: a dry run reported no drift for a drifted source"


def test_head_drift_is_reset_like_every_other_module_global(hub) -> None:
    """`main()` clears the other three module-level mutables, with a comment naming the reason (a
    dry-run-then-real in-process flow inherits the previous run's state). This one was not."""
    mod, _hub_root, _c, _u = hub
    src = Path(mod.__file__).read_text(encoding="utf-8")
    main_body = src.split("def main(")[1]
    for marker in ("_SAFETY_FLOOR_FAILURES.clear()", "_head_drift.clear()"):
        assert marker in main_body, f"{marker} missing from main()"


def test_there_is_exactly_one_hub_root_constant(hub) -> None:
    """Two sources of truth for the same path meant a change to one left `_head_source` reading git
    in the WRONG tree and silently returning None — i.e. shipping the working tree again, with no
    warning, which is the failure the whole change exists to prevent."""
    src = Path(Path(__file__).resolve().parents[1] / "scripts" / "sync_enforcement_to_projects.py")
    text = src.read_text(encoding="utf-8")
    assert "_HUB_ROOT" not in text, "a second hub-root constant is back"
    assert "FABRIK_ROOT.resolve()" in text, (
        "both sides of the relative_to must be resolved, or a symlinked hub root silently "
        "disables the HEAD read fleet-wide"
    )


# ── round 3 of the Phase E review: three defects INSIDE round 1's own fixes ──


def test_the_comparison_hashes_what_ships_or_the_sync_never_converges(hub, tmp_path: Path) -> None:
    """`_shipped_hash` exists so the comparison and the writer cannot disagree — and the leg that
    syncs every project's MAIN checkout kept calling `compute_file_hash(source)`. Executed: a
    drifted file was re-copied on EVERY run, forever, in all 47 `.fabrik/synced.lock` repos."""
    mod, _hub_root, committed, _untracked = hub
    committed.write_text("COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8")
    dest = tmp_path / "proj" / "committed.py"
    actions = [mod.sync_single_file(committed, dest).action for _ in range(3)]
    assert actions == ["COPY", "SKIP", "SKIP"], (
        f"{actions} — a sync that never reaches SKIP rewrites every drifted file in every repo on "
        "every run, and reports each one as `copied`"
    )


def test_a_project_copy_holding_the_uncommitted_bytes_is_corrected(hub, tmp_path: Path) -> None:
    """The state T12.17 was built to end — 48 project copies carrying a hub edit that exists in no
    commit — hashed EQUAL to the working tree and returned SKIP/identical, so it was the one state
    the mechanism could not correct. The dest is aged because that is the real fleet shape: the
    project copy was written days ago, the hub edit is recent."""
    mod, _hub_root, committed, _untracked = hub
    committed.write_text("COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8")
    dest = tmp_path / "proj" / "committed.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "COMMITTED = 1\nUNCOMMITTED_EDIT = True\n", encoding="utf-8"
    )  # the hub's WORKING bytes
    os.utime(dest, (time.time() - 86_400, time.time() - 86_400))
    result = mod.sync_single_file(committed, dest)
    assert result.action == "COPY", f"{result.action}/{result.reason} — the uncommitted bytes stay"
    assert "UNCOMMITTED_EDIT" not in dest.read_text(encoding="utf-8")


def test_the_drift_report_never_claims_a_sync_a_dry_run_did_not_do(hub, tmp_path: Path) -> None:
    """`_head_source` is consulted on every branch, including those that write nothing, so the
    report's verb has to come from the RUN, not from the drift set being non-empty."""
    src = SCRIPT.read_text(encoding="utf-8")  # the module under test, not a CWD-relative guess
    assert "nothing was written (--dry-run)" in src
    assert "wherever this run wrote, it wrote the COMMITTED bytes" in src
    # the flat claim is gone — it was printed verbatim on dry runs and on SKIP/WARN branches
    assert "the COMMITTED bytes were synced, not what is on disk (T12.17" not in src


def test_head_source_is_not_re_shelled_for_every_caller(hub, monkeypatch) -> None:
    """⚠️ COUNT THE SUBPROCESSES, which is the claim in this test's own name.

    The first cut asserted `len(mod._head_cache)` grew — satisfied by a cache that is WRITTEN
    every call and never READ, which is precisely the bug it would have to catch. Proven: neuter
    the read branch and the dict still reaches 1 then 2, and the old assertions still passed
    (Phase E review, round 4). The saving is `git show` + `read_bytes`; `git ls-files` still runs
    every call because it is where the blob SHA comes from, and the SHA is what makes the memo
    HEAD-aware."""
    mod, _hub_root, committed, _untracked = hub
    calls: list[list[str]] = []
    real = mod.subprocess.run

    def counting(cmd, *a, **k):
        calls.append(list(cmd))
        return real(cmd, *a, **k)

    monkeypatch.setattr(mod.subprocess, "run", counting)
    mod._head_cache.clear()

    first = mod._head_source(committed)
    cold = [c for c in calls if c[:2] == ["git", "show"]]
    assert len(cold) == 1, f"expected one `git show` on a cold call, got {cold}"

    assert mod._head_source(committed) == first
    warm = [c for c in calls if c[:2] == ["git", "show"]]
    assert len(warm) == 1, (
        f"the second call re-ran `git show` — the cache is written but never read: {warm}"
    )

    os.utime(committed, (1_000_000_000, 1_000_000_000))  # a changed stat must MISS
    mod._head_source(committed)
    after = [c for c in calls if c[:2] == ["git", "show"]]
    assert len(after) == 2, "a since-touched file was served from a stale cache entry"


def _commit_new_blob(hub_dir: Path, rel: str, data: bytes) -> None:
    """Move HEAD to a new commit for `rel` WITHOUT touching the working file — a sibling's commit
    landing mid-run, which is the whole point. Plumbing, so no hook fires and no file is written."""
    sha = (
        subprocess.run(
            ["git", "-C", str(hub_dir), "hash-object", "-w", "--stdin"],
            input=data,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    subprocess.run(
        ["git", "-C", str(hub_dir), "update-index", "--add", "--cacheinfo", f"100755,{sha},{rel}"],
        check=True,
    )
    tree = subprocess.run(
        ["git", "-C", str(hub_dir), "write-tree"], capture_output=True, text=True, check=True
    ).stdout.strip()
    head = subprocess.run(
        ["git", "-C", str(hub_dir), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    new = subprocess.run(
        ["git", "-C", str(hub_dir), "commit-tree", tree, "-p", head, "-m", "sibling"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # the branch by NAME, read from the repo — `init.defaultBranch` is a local setting and
    # hard-coding "master" made an earlier probe of mine print a false negative on a `main` repo
    branch = subprocess.run(
        ["git", "-C", str(hub_dir), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(hub_dir), "update-ref", f"refs/heads/{branch}", new], check=True
    )


def test_the_memo_sees_a_head_that_moved_under_it(hub) -> None:
    """⚠️ THE EDIT THAT MATTERS IS A COMMIT, and a commit does not touch the working file.

    The first cut keyed on `(rel, st_mtime_ns, st_size)` and its comment claimed "an edit DURING a
    run is never served stale". Executed round 4: a sibling's commit landed mid-run, the working
    stat was byte-identical, and the memo served the pre-commit bytes — to every remaining repo of
    the 47, all reported `copied`, with the drift report computed against the stale HEAD. This runs
    as a POST-COMMIT hook on a tree three sessions commit to, so that race is the normal case, not
    an exotic one. The key now carries the blob SHA that `git ls-tree HEAD` already prints."""
    mod, hub_dir, committed, _untracked = hub
    mod._head_cache.clear()
    assert mod._head_source(committed)[0] == b"COMMITTED = 1\n"
    before = committed.stat()
    _commit_new_blob(hub_dir, "scripts/enforcement/committed.py", b"COMMITTED = 2\n")
    after = committed.stat()
    assert (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size), (
        "the fixture touched the working file — the staleness this guards would be invisible"
    )
    assert mod._head_source(committed)[0] == b"COMMITTED = 2\n", (
        "the memo served pre-commit bytes after HEAD moved — every later repo in the run gets them"
    )


def test_a_commit_of_already_staged_content_is_not_served_from_the_cache(tmp_path):
    """The memo must key on what the function RETURNS — HEAD's blob — not on the index entry.

    `git ls-files -s` prints the INDEX entry, which is written at STAGE time and is NOT touched
    by the commit. Executed: stage B (index f70f…→223b…, HEAD still A), then commit — the index
    SHA, the working file's mtime and its size are ALL unchanged while HEAD moves A→B. The whole
    cache key was therefore blind to the one event it was introduced to catch, and on a tree three
    sessions commit to, a sibling's mid-walk commit left every remaining repo of the 47 served the
    pre-commit bytes and reported `copied`.
    """
    mod = _mod()
    repo = tmp_path / "hub"
    (repo / "scripts" / "enforcement").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), "config", *cfg], check=True)
    f = repo / "scripts" / "enforcement" / "x.py"
    f.write_text("A\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "a"], check=True, capture_output=True)

    mod.FABRIK_ROOT = repo

    # ⚠️ THE CACHE MUST BE POPULATED BETWEEN THE STAGE AND THE COMMIT, or the defect cannot
    # reproduce: call before staging and the index SHA legitimately changes, so the old key is a
    # MISS and the read is fresh by accident. The staleness needs the index already holding B
    # while HEAD is still A — which is the real shape, because the gate stages and the contract
    # commits as two steps. Getting this wrong is a grader that cannot fail.
    f.write_text("B\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "scripts/enforcement/x.py"], check=True, capture_output=True
    )
    assert mod._head_source(f)[0] == b"A\n"  # staged B, HEAD still A — memo populated here
    idx_before = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-s", "--", "scripts/enforcement/x.py"],
        capture_output=True, text=True, check=True,
    ).stdout.split()[1]
    st_before = f.stat()
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "b"], check=True, capture_output=True)
    idx_after = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-s", "--", "scripts/enforcement/x.py"],
        capture_output=True, text=True, check=True,
    ).stdout.split()[1]

    # the premise: the old key's every component survived the commit unchanged
    assert idx_before == idx_after, "premise broken — the index SHA moved after all"
    assert (st_before.st_mtime_ns, st_before.st_size) == (f.stat().st_mtime_ns, f.stat().st_size)

    # and the memo still answers with the NEW HEAD
    assert mod._head_source(f)[0] == b"B\n", "served the pre-commit bytes from the cache"
