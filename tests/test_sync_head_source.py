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
    for marker in (
        "_SAFETY_FLOOR_FAILURES.clear()",
        "_head_drift.clear()",
        "_HUB_SOURCES.clear()",  # derive from the manifest, rebound per run (W-8c57e84a)
        "_HUB_BLOBS.clear()",
    ):
        assert marker in main_body, f"{marker} missing from main()"


def test_there_is_exactly_one_hub_root_constant(hub) -> None:
    """Two sources of truth for the same path meant a change to one left `_head_source` reading git
    in the WRONG tree and silently returning None — i.e. shipping the working tree again, with no
    warning, which is the failure the whole change exists to prevent."""
    src = SCRIPT  # one spelling for the module under test (see REPO/SCRIPT above)
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
    (Phase E review, round 4). The saving is the blob read (`git cat-file`, `git show` before W-ba306861) + `read_bytes`; `git ls-tree HEAD` still runs
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
    cold = [c for c in calls if c[:2] == ["git", "cat-file"]]
    assert len(cold) == 1, f"expected one the blob read (`git cat-file`) on a cold call, got {cold}"

    assert mod._head_source(committed) == first
    warm = [c for c in calls if c[:2] == ["git", "cat-file"]]
    assert len(warm) == 1, (
        f"the second call re-ran the blob read (`git cat-file`) — the cache is written but never read: {warm}"
    )

    os.utime(committed, (1_000_000_000, 1_000_000_000))  # a changed stat must MISS
    mod._head_source(committed)
    after = [c for c in calls if c[:2] == ["git", "cat-file"]]
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
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[1]
    st_before = f.stat()
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "b"], check=True, capture_output=True)
    idx_after = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-s", "--", "scripts/enforcement/x.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[1]

    # the premise: the old key's every component survived the commit unchanged
    assert idx_before == idx_after, "premise broken — the index SHA moved after all"
    assert (st_before.st_mtime_ns, st_before.st_size) == (f.stat().st_mtime_ns, f.stat().st_size)

    # and the memo still answers with the NEW HEAD
    assert mod._head_source(f)[0] == b"B\n", "served the pre-commit bytes from the cache"


_STUB_MANIFEST = '''"""A stub hub manifest: every name the sync imports; it ships CORE_SCRIPTS only."""
AGENT_HOOK_FILES = ()
CORE_SCRIPTS = (CORE-MARK)
GOVERNANCE_DIRS = ()
GOVERNANCE_FILES = ()
GOVERNANCE_TEMPLATES = ()
REFERENCE_DOCS = ()
RETIRED_CORE_SCRIPTS = ()
RETIRED_GOVERNANCE_FILES = ()
RETIRED_VENDORED_DIRS = ()
RUN_SCRIPTS = ()
RUN_SCRIPTS_SRC_DIR = "scripts/run"
SEED_IF_MISSING = ()
VENDORED_DIRS = ()


def iter_synced_pairs(project_root, fabrik_root):
    for name in CORE_SCRIPTS:
        yield fabrik_root / "scripts" / name, project_root / "scripts" / name


def worktreeinclude_text():
    return ""


def gitignore_block_text():
    return (
        "# ==========\\n# Fabrik-synced files BLOCK-MARK\\n"
        "# End Fabrik-synced block\\n# ==========\\n"
    )
'''


def test_the_gitignore_block_ships_from_heads_manifest_not_the_working_tree(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """W-8c57e84a: the sync read files out of HEAD (T12.17) but COMPUTED the `.gitignore` block —
    and took every synced list — from the imported WORKING-TREE manifest, so a sibling's uncommitted
    manifest edit patched ~46 repos with no drift line. `main()` now binds the manifest from HEAD and
    names a drifted manifest in the drift report, the contract every copied file already has."""
    mod, hub_root, _committed, _untracked = hub
    manifest = hub_root / "scripts" / "fabrik_synced_manifest.py"
    manifest.write_text(_stub("HEAD-BLOCK"), encoding="utf-8")
    subprocess.run(["git", "-C", str(hub_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "manifest"], check=True)
    manifest.write_text(_stub("TREE-BLOCK"), encoding="utf-8")
    opt = tmp_path / "opt"
    project = opt / "proj"
    project.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".gitignore").write_text(".env\n.venv/\n__pycache__/\n", encoding="utf-8")
    monkeypatch.setattr(mod, "OPT_ROOT", opt)
    monkeypatch.setattr(sys, "argv", ["sync"])
    mod.main()
    out = capsys.readouterr().out
    written = (project / ".gitignore").read_text(encoding="utf-8")
    assert "HEAD-BLOCK" in written, written
    assert "TREE-BLOCK" not in written, written
    assert "scripts/fabrik_synced_manifest.py" in out, out  # the drift line names the manifest


def _stub(block: str, core: str = "") -> str:
    return _STUB_MANIFEST.replace("BLOCK-MARK", block).replace("CORE-MARK", core)


def _manifest_hub(hub_root: Path, head: str, tree: str | None) -> None:
    """Commit `head` as the hub manifest; leave `tree` (if any) as an uncommitted edit on top."""
    manifest = hub_root / "scripts" / "fabrik_synced_manifest.py"
    manifest.write_text(head, encoding="utf-8")
    subprocess.run(["git", "-C", str(hub_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "manifest"], check=True)
    if tree is not None:
        manifest.write_text(tree, encoding="utf-8")


def _one_project(tmp_path: Path, monkeypatch, mod) -> Path:
    opt = tmp_path / "opt"
    project = opt / "proj"
    project.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".gitignore").write_text(".env\n.venv/\n__pycache__/\n", encoding="utf-8")
    monkeypatch.setattr(mod, "OPT_ROOT", opt)
    monkeypatch.setattr(sys, "argv", ["sync"])
    return project


def test_the_synced_lists_ship_from_heads_manifest_not_the_working_tree(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """WHAT ships comes from HEAD's manifest too, not only the block: HEAD lists `head_only.py`,
    the uncommitted edit lists `tree_only.py`, and only HEAD's file lands."""
    mod, hub_root, _committed, _untracked = hub
    for name in ("head_only.py", "tree_only.py"):
        (hub_root / "scripts" / name).write_text(f"# {name}\n", encoding="utf-8")
    _manifest_hub(hub_root, _stub("B", '"head_only.py",'), _stub("B", '"tree_only.py",'))
    project = _one_project(tmp_path, monkeypatch, mod)
    assert mod.main() == 0, capsys.readouterr().out
    assert (project / "scripts" / "head_only.py").exists()
    assert not (project / "scripts" / "tree_only.py").exists()


def test_the_drift_line_says_the_manifest_governs_what_ships(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """The manifest is a hub file, never a synced one: the drift line names what it governs."""
    mod, hub_root, _committed, _untracked = hub
    _manifest_hub(hub_root, _stub("HEAD-BLOCK"), _stub("TREE-BLOCK"))
    _one_project(tmp_path, monkeypatch, mod)
    mod.main()
    out = capsys.readouterr().out
    assert "hub file(s) differ" in out and "synced file(s) differ" not in out, out
    assert "is the manifest itself: what ships and the .gitignore block" in out, out


@pytest.mark.parametrize(
    "head",
    [
        _STUB_MANIFEST.replace("CORE-MARK", "").replace("BLOCK-MARK", "B")
        + "raise RuntimeError('x')\n",
        _STUB_MANIFEST.replace("CORE-MARK", "")
        .replace("BLOCK-MARK", "B")
        .replace("RETIRED_VENDORED_DIRS = ()\n", ""),
        _STUB_MANIFEST.replace("CORE-MARK", "").replace("BLOCK-MARK", "B") + "def broken(:\n",
        _STUB_MANIFEST.replace("CORE-MARK", "").replace("BLOCK-MARK", "B")
        + "import sys\nsys.exit(0)\n",
    ],
    ids=["raises-on-exec", "lacks-a-name", "syntax-error", "exits-zero"],
)
def test_an_unusable_head_manifest_is_a_named_refusal_never_a_tree_fallback(
    hub, tmp_path: Path, monkeypatch, capsys, head: str
) -> None:
    """Falling back to the working tree would ship uncommitted bytes, the incident this closes; a
    traceback would name nothing, and a `sys.exit(0)` would end the run green having synced
    nothing. The run stops with the reason before any project is touched."""
    mod, hub_root, _committed, _untracked = hub
    (hub_root / "scripts" / "head_only.py").write_text("# x\n", encoding="utf-8")
    _manifest_hub(hub_root, head, _stub("TREE-BLOCK", '"head_only.py",'))
    project = _one_project(tmp_path, monkeypatch, mod)
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "HEAD's scripts/fabrik_synced_manifest.py cannot be bound" in out, out
    assert (project / ".gitignore").read_text(encoding="utf-8") == ".env\n.venv/\n__pycache__/\n"
    assert not (project / "scripts").exists()  # the tree's list shipped nothing either


def test_a_dataclass_in_heads_manifest_binds(hub) -> None:
    """`dataclasses` resolves `sys.modules[cls.__module__]` at decoration time under
    `from __future__ import annotations`; an unregistered exec module turned a valid manifest into a
    refusal. The exec module is registered while it runs, and removed after."""
    mod, hub_root, _committed, _untracked = hub
    head = (
        "from __future__ import annotations\nfrom dataclasses import dataclass\n"
        + _stub("DC-BLOCK")
        + "\n@dataclass\nclass Row:\n    name: str\n"
    )
    _manifest_hub(hub_root, head, None)
    assert mod._bind_manifest_from_head() is None
    assert "DC-BLOCK" in mod.gitignore_block_text()
    assert "fabrik_synced_manifest_at_head" not in sys.modules


def test_a_manifest_resolving_paths_from_its_file_binds(hub) -> None:
    """An import sets `__file__`; the exec module must too, or a manifest that resolves a path from
    it (`Path(__file__).parent`) is refused although it is committed and valid."""
    mod, hub_root, _committed, _untracked = hub
    head = "from pathlib import Path\nHERE = Path(__file__).resolve().parent\n" + _stub("F-BLOCK")
    _manifest_hub(hub_root, head, None)
    assert mod._bind_manifest_from_head() is None
    assert "F-BLOCK" in mod.gitignore_block_text()


def test_a_refusal_restores_the_import_time_binding(hub) -> None:
    """A refused bind after a successful one must not leave the earlier HEAD binding in place."""
    mod, hub_root, _committed, _untracked = hub
    imported = mod.gitignore_block_text
    _manifest_hub(hub_root, _stub("HEAD-BLOCK"), None)
    assert mod._bind_manifest_from_head() is None
    assert mod.gitignore_block_text is not imported
    _manifest_hub(hub_root, _stub("B") + "raise RuntimeError('x')\n", None)
    assert mod._bind_manifest_from_head() is not None
    assert mod.gitignore_block_text is imported


def test_the_bind_runs_after_argparse_so_help_never_needs_the_manifest(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """`--help` answers even when HEAD's manifest cannot be bound."""
    mod, hub_root, _committed, _untracked = hub
    _manifest_hub(hub_root, _stub("B") + "raise RuntimeError('x')\n", None)
    _one_project(tmp_path, monkeypatch, mod)
    monkeypatch.setattr(sys, "argv", ["sync", "--help"])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    assert "cannot be bound" not in capsys.readouterr().out


def test_the_manifest_note_is_absent_when_only_synced_files_drift(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """The drift line's manifest note fires only when the manifest itself drifted."""
    mod, hub_root, committed, _untracked = hub
    (hub_root / "scripts" / "enforcement" / "committed.py").write_text("x = 1\n", encoding="utf-8")
    _manifest_hub(hub_root, _stub("B", '"enforcement/committed.py",'), None)
    committed.write_text(
        "COMMITTED = 2\n", encoding="utf-8"
    )  # a synced file drifts, not the manifest
    _one_project(tmp_path, monkeypatch, mod)
    mod.main()
    out = capsys.readouterr().out
    assert "hub file(s) differ" in out and "scripts/enforcement/committed.py" in out, out
    assert "is the manifest itself" not in out, out


def test_no_head_manifest_restores_the_import_time_binding(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """A run against a hub with no HEAD manifest (here a fresh repo with no commit) must not inherit
    an EARLIER in-process run's HEAD binding: the import-time binding comes back."""
    mod, hub_root, _committed, _untracked = hub
    imported = mod.gitignore_block_text
    _manifest_hub(hub_root, _stub("HEAD-BLOCK"), None)
    assert mod._bind_manifest_from_head() is None
    assert "HEAD-BLOCK" in mod.gitignore_block_text()
    other = tmp_path / "other-hub"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    monkeypatch.setattr(mod, "FABRIK_ROOT", other)
    assert mod._bind_manifest_from_head() is None
    assert mod.gitignore_block_text is imported


def test_the_rebound_names_are_exactly_the_modules_manifest_imports(hub) -> None:
    """A name imported from the manifest but missing from `_MANIFEST_NAMES` would stay bound to the
    working tree, silently; so would a second, function-local import (one in
    `_unreachable_vendored_copies` did)."""
    import ast

    mod = hub[0]
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "fabrik_synced_manifest"
    ]
    assert len(imports) == 1, [n.lineno for n in imports]
    assert {a.name for a in imports[0].names} == set(mod._MANIFEST_NAMES)


# ── W-ba306861: an unreadable source is named, never shipped silently ────────────────────────────


def _corrupt_object(hub_root: Path, sha: str) -> None:
    """Overwrite a loose object with bytes git cannot inflate (objects are written 0444)."""
    obj = hub_root / ".git" / "objects" / sha[:2] / sha[2:]
    obj.chmod(0o644)
    obj.write_bytes(b"not a zlib stream")


def _rev(hub_root: Path, what: str) -> str:
    return subprocess.run(
        ["git", "-C", str(hub_root), "rev-parse", what], capture_output=True, text=True, check=True
    ).stdout.strip()


def _fail_git_for(mod, monkeypatch, verb: str, rel: str, *, raise_exc: bool = False) -> None:
    """Make the module's `git <verb>` for one path fail (rc 128, or OSError), every other call real."""
    real = subprocess.run

    def fake(cmd, *a, **k):
        if cmd[:1] == ["git"] and verb in cmd and any(rel in str(c) for c in cmd):
            if raise_exc:
                raise FileNotFoundError(2, "No such file or directory", "git")
            return subprocess.CompletedProcess(cmd, 128, b"", b"fatal: simulated failure\n")
        return real(cmd, *a, **k)

    monkeypatch.setattr(mod.subprocess, "run", fake)


def _tail3(out: str) -> str:
    """What the production wrapper keeps (`$SYNC 2>&1 | tail -3`, governance_sync_postcommit.sh)."""
    return "\n".join(out.rstrip("\n").split("\n")[-3:])


def test_an_unreadable_working_copy_is_drift_with_its_reason(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """A tracked file whose working copy cannot be read ships HEAD's bytes — that IS a difference
    from what is on disk, and it was recorded as none. Named with its reason, on the summary line
    the post-commit wrapper keeps, and never served from the memo so a later read re-records it.
    The read is made to fail by patching it, not by chmod, so the test also runs as root."""
    mod, hub_root, committed, _untracked = hub
    _manifest_hub(hub_root, _stub("B", '"enforcement/committed.py",'), None)
    real_read = Path.read_bytes

    def unreadable(self: Path) -> bytes:
        if self == committed:
            raise PermissionError(13, "Permission denied", str(self))
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    assert mod._head_source(committed) == (b"COMMITTED = 1\n", 0o100755)
    rel = "scripts/enforcement/committed.py"
    assert rel in mod._head_drift
    assert mod._head_drift_why[rel] == "working copy unreadable (PermissionError)"
    mod._head_drift.clear()
    mod._head_drift_why.clear()
    mod._head_source(committed)
    assert rel in mod._head_drift_why, "a cached read lost the reason"
    _one_project(tmp_path, monkeypatch, mod)
    mod.main()
    out = capsys.readouterr().out
    assert "scripts/enforcement/committed.py (working copy unreadable (PermissionError))" in out, (
        out
    )
    assert "restore a deleted or unreadable copy" in out, out
    assert "HEAD drift: 1" in _tail3(out), _tail3(out)


def test_a_deleted_working_copy_says_deleted(hub) -> None:
    """A copy removed after the caller's `exists()` check is drift, and the reason says DELETED —
    "unreadable (FileNotFoundError)" would send the operator to fix a permission."""
    mod, _hub_root, committed, _untracked = hub
    committed.unlink()
    assert mod._head_source(committed) == (b"COMMITTED = 1\n", 0o100755)
    assert mod._head_drift_why["scripts/enforcement/committed.py"] == "deleted in the working tree"


def _branch_ref(hub_root: Path) -> Path:
    ref = subprocess.run(
        ["git", "-C", str(hub_root), "symbolic-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return hub_root / ".git" / ref


def test_a_hub_git_that_cannot_answer_is_named(
    hub, tmp_path: Path, tmp_path_factory, monkeypatch
) -> None:
    """`ls-tree` failing on a hub that HAS a commit — a corrupt branch ref, a corrupt tree, a
    directory that is no repo at all — or git not running, returned None exactly as an untracked
    file does, and the working tree shipped silently. Each is named; an untracked file still
    records nothing. A corrupt ref is the case `rev-parse -q` alone reads as an unborn HEAD."""
    mod, hub_root, committed, untracked = hub
    rel = "scripts/enforcement/committed.py"
    assert mod._head_source(untracked) is None
    assert mod._head_unread == {}, "an untracked source is not an unreadable one"
    ref = _branch_ref(hub_root)
    good_ref = ref.read_text(encoding="utf-8")
    ref.write_text("garbage\n", encoding="utf-8")
    assert mod._head_source(committed) is None
    assert mod._head_unread[rel].startswith("git ls-tree exited 128"), mod._head_unread
    ref.write_text(good_ref, encoding="utf-8")
    mod._head_unread.clear()
    _corrupt_object(hub_root, _rev(hub_root, "HEAD^{tree}"))
    assert mod._head_source(committed) is None
    assert mod._head_unread[rel].startswith("git ls-tree exited 128"), mod._head_unread
    plain = tmp_path_factory.mktemp("no-repo-hub")
    (plain / "x.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FABRIK_ROOT", plain)
    assert mod._head_source(plain / "x.py") is None
    assert mod._head_unread["x.py"].startswith("git ls-tree exited 128"), mod._head_unread
    monkeypatch.setattr(mod, "FABRIK_ROOT", hub_root)
    mod._head_unread.clear()
    _fail_git_for(mod, monkeypatch, "ls-tree", rel, raise_exc=True)
    assert mod._head_source(committed) is None
    assert mod._head_unread[rel].startswith("git not runnable (ls-tree)"), mod._head_unread


def test_an_unborn_hub_records_nothing_and_a_lost_ref_is_named(
    tmp_path_factory, monkeypatch
) -> None:
    """An unborn HEAD has nothing committed to read, like an untracked file. A hub whose only branch
    ref was deleted reads the same to `rev-parse`, but its objects are there: named."""
    mod = _mod()
    repo = tmp_path_factory.mktemp("unborn-hub")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    src = repo / "x.py"
    src.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(mod, "FABRIK_ROOT", repo)
    assert mod._head_source(src) is None
    assert mod._head_unread == {}, "an unborn hub is not a git that cannot answer"
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(repo), "config", *cfg], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "x.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x"], check=True)
    _branch_ref(repo).unlink()
    assert mod._head_source(src) is None
    assert mod._head_unread["x.py"].startswith("git ls-tree exited 128"), mod._head_unread


def test_a_pathspec_magic_name_is_read_literally(hub) -> None:
    """A tracked file named `:(…` is pathspec MAGIC to a plain `ls-tree`, which exits 128 on it."""
    mod, hub_root, _committed, _untracked = hub
    magic = hub_root / ":(glob)magic.py"  # magic is parsed only at a pathspec's START
    magic.write_text("MAGIC = 1\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(hub_root), "--literal-pathspecs", "add", "--", ":(glob)magic.py"],
        check=True,
    )
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "magic"], check=True)
    assert mod._head_source(magic) == (b"MAGIC = 1\n", 0o100644)
    assert mod._head_unread == {}


@pytest.mark.parametrize("dry_run", [False, True], ids=["real", "dry-run"])
def test_an_unread_source_is_on_the_summary_line(
    hub, tmp_path: Path, monkeypatch, capsys, dry_run: bool
) -> None:
    """The run's report and the one line the wrapper keeps both name the working-tree fallback, in
    the run's own verb: a dry run wrote nothing."""
    mod, hub_root, committed, _untracked = hub
    _manifest_hub(hub_root, _stub("B", '"enforcement/committed.py",'), None)
    _one_project(tmp_path, monkeypatch, mod)
    if dry_run:
        monkeypatch.setattr(sys, "argv", ["sync", "--dry-run"])
    _fail_git_for(mod, monkeypatch, "ls-tree", "scripts/enforcement/committed.py")
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "git could not read HEAD for 1 hub source(s)" in out, out
    assert (
        "scripts/enforcement/committed.py (git ls-tree exited 128: fatal: simulated failure)" in out
    )
    if dry_run:
        assert "nothing was written (--dry-run)" in out, out
        assert "HEAD unread: 1 (working tree would be used)" in _tail3(out), _tail3(out)
    else:
        assert "wherever this run wrote them, it wrote the WORKING TREE's bytes" in out, out
        assert "HEAD unread: 1 (working tree used)" in _tail3(out), _tail3(out)


def test_a_failed_blob_read_is_named_and_re_asked(hub, monkeypatch) -> None:
    """`ls-tree` listed the blob and git could not read it (a corrupt or missing object): the
    working tree shipped silently and the failure was CACHED, so it answered for the rest of the
    walk. Named, and asked again on the next call; a read that cannot RUN names its step."""
    mod, hub_root, committed, _untracked = hub
    rel = "scripts/enforcement/committed.py"
    blob = _rev(hub_root, f"HEAD:{rel}")
    obj = hub_root / ".git" / "objects" / blob[:2] / blob[2:]
    good = obj.read_bytes()
    _corrupt_object(hub_root, blob)
    assert mod._head_source(committed) is None
    assert mod._head_unread[rel].startswith("git cat-file exited 128"), mod._head_unread
    obj.write_bytes(good)
    mod._head_unread.clear()
    assert mod._head_source(committed) == (b"COMMITTED = 1\n", 0o100755), "a failure was cached"
    assert mod._head_unread == {}
    mod._head_cache.clear()
    _fail_git_for(mod, monkeypatch, "cat-file", "", raise_exc=True)
    assert mod._head_source(committed) is None
    assert mod._head_unread[rel].startswith("git not runnable (cat-file)"), mod._head_unread


def test_the_bytes_are_the_listed_blob_not_a_re_resolved_head(hub, monkeypatch) -> None:
    """`git show HEAD:<rel>` re-resolved HEAD after `ls-tree` had listed the blob: a sibling's
    commit between the two paired the NEW bytes with the OLD mode and cached them under the OLD
    SHA. The read names the listed blob."""
    mod, hub_root, committed, _untracked = hub
    seen: list[list[str]] = []
    real = subprocess.run

    def spy(cmd, *a, **k):
        seen.append(list(cmd))
        return real(cmd, *a, **k)

    monkeypatch.setattr(mod.subprocess, "run", spy)
    mod._head_source(committed)
    blob = _rev(hub_root, "HEAD:scripts/enforcement/committed.py")
    assert ["git", "cat-file", "blob", blob] in seen, seen
    assert not any("show" in c for c in seen), seen


def test_first_line_never_raises_on_undecodable_stderr(hub) -> None:
    """A reason is built from git's stderr, which carries the PATH; a non-UTF-8 path in it must not
    turn a named failure into a crash of the whole sync."""
    mod = hub[0]
    assert "bad" in mod._first_line(b"\xff\xfe bad path\nsecond line")
    assert mod._first_line(b"") == "(no message)"


def test_an_unreadable_head_manifest_refuses_the_run(
    hub, tmp_path: Path, monkeypatch, capsys
) -> None:
    """A hub git that cannot read HEAD's manifest fell back to the WORKING-TREE manifest — every
    synced list and the .gitignore block from a three-session tree, fleet-wide, at exit 0. The
    loader already refuses a manifest it cannot BIND for that reason; one it cannot READ is
    refused the same way, before any project is touched."""
    mod, hub_root, _committed, _untracked = hub
    (hub_root / "scripts" / "head_only.py").write_text("# x\n", encoding="utf-8")
    _manifest_hub(hub_root, _stub("B", '"head_only.py",'), None)
    project = _one_project(tmp_path, monkeypatch, mod)
    _corrupt_object(hub_root, _rev(hub_root, "HEAD:scripts/fabrik_synced_manifest.py"))
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert "HEAD's scripts/fabrik_synced_manifest.py cannot be read (git cat-file exited" in out, (
        out
    )
    assert not (project / "scripts").exists()


def test_a_non_file_head_entry_is_named(hub) -> None:
    """A directory's HEAD entry is a tree: reading it printed its LISTING and the sync would have
    written that listing, mode 0, as the file. Named, never shipped."""
    mod, hub_root, _committed, _untracked = hub
    assert mod._head_source(hub_root / "scripts" / "enforcement") is None
    assert mod._head_unread["scripts/enforcement"] == "not a file in HEAD (tree)"


def test_the_new_records_reset_before_the_manifest_bind(hub) -> None:
    """Reset after the bind and the manifest's own record is wiped before the report reads it."""
    mod = hub[0]
    main_body = Path(mod.__file__).read_text(encoding="utf-8").split("def main(")[1]
    bind = main_body.index("refusal = _bind_manifest_from_head()")
    for marker in ("_head_unread.clear()", "_head_drift_why.clear()", "_head_drift.clear()"):
        assert -1 < main_body.index(marker) < bind, marker


# ---- W-bb97199e: the FILE SET comes from HEAD too, not only the bytes ----------------------------
# T12.17 read a tracked file's bytes from HEAD, but every caller decided WHICH files exist from the
# working tree: a sibling's uncommitted deletion shipped nothing (a stale project copy, silently),
# and the vendored and governance-dir orphan prunes DELETED the project copy.


def _deleted_hub(hub, tmp_path: Path):
    """The hub fixture plus a vendored dir, a governance dir and one listed source, all committed;
    the project holds stale copies; then the working tree loses one file in each place."""
    mod, hub_root, _committed, _untracked = hub
    rels = {
        "walked": "scripts/enforcement/gone.py",
        "vendored": "libs/vend/gone.py",
        "govdir": ".windsurf/rules/gone.md",
        "listed": "AGENTS-gone.md",
    }
    for rel in (*rels.values(), "libs/vend/kept.py", ".windsurf/rules/kept.md"):
        (hub_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (hub_root / rel).write_text(f"# {rel} HEAD\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(hub_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "synced set"], check=True)
    project = tmp_path / "proj"
    a_day_ago = time.time() - 86400  # a stale copy predates HEAD's commit, as a real one does
    for rel in rels.values():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(f"# {rel} stale\n", encoding="utf-8")
        os.utime(project / rel, (a_day_ago, a_day_ago))
    for rel in rels.values():
        (hub_root / rel).unlink()  # the sibling's UNCOMMITTED deletion
    mod.VENDORED_DIRS = ["libs/vend"]
    mod.GOVERNANCE_DIRS = [".windsurf/rules"]
    mod.GOVERNANCE_FILES = [rels["listed"]]
    for name in (
        "CORE_SCRIPTS",
        "RUN_SCRIPTS",
        "GOVERNANCE_TEMPLATES",
        "REFERENCE_DOCS",
        "AGENT_HOOK_FILES",
    ):
        setattr(mod, name, [])
    mod._head_drift.clear()
    mod._head_drift_why.clear()
    return mod, hub_root, project, rels


def test_a_listed_source_deleted_in_the_tree_ships_head(hub, tmp_path: Path) -> None:
    mod, _hub_root, project, rels = _deleted_hub(hub, tmp_path)
    mod.sync_scripts_to_project(project)
    rel = rels["listed"]
    assert (project / rel).read_text() == f"# {rel} HEAD\n", "the stale copy was left in place"
    assert mod._head_drift_why.get(rel) == "deleted in the working tree", mod._head_drift_why


def test_a_walked_file_deleted_in_the_tree_ships_head(hub, tmp_path: Path) -> None:
    mod, _hub_root, project, rels = _deleted_hub(hub, tmp_path)
    mod.sync_scripts_to_project(project)
    for key in ("walked", "vendored", "govdir"):
        rel = rels[key]
        assert (project / rel).is_file(), f"{rel}: the project copy was deleted"
        assert (project / rel).read_text() == f"# {rel} HEAD\n", rel
        assert mod._head_drift_why.get(rel) == "deleted in the working tree", rel


def test_the_prunes_keep_what_head_holds_and_drop_what_it_retired(hub, tmp_path: Path) -> None:
    """A COMMITTED deletion is still a retirement: the prunes drop it. Only HEAD decides."""
    mod, hub_root, project, rels = _deleted_hub(hub, tmp_path)
    for rel in (rels["vendored"], rels["govdir"]):
        subprocess.run(["git", "-C", str(hub_root), "rm", "-q", "--cached", rel], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "retire"], check=True)
    mod._head_cache.clear()
    result = mod.sync_scripts_to_project(project)
    for rel in (rels["vendored"], rels["govdir"]):
        assert not (project / rel).exists(), f"{rel}: a retired file survived the prune"
    deleted = {r.destination for r in result.files if r.action == "DELETE"}
    assert {project / rels["vendored"], project / rels["govdir"]} <= deleted, deleted
    assert (project / "libs/vend/kept.py").read_text() == "# libs/vend/kept.py HEAD\n"


def test_a_deleted_head_symlink_is_not_shipped_as_a_file(hub, tmp_path: Path) -> None:
    """HEAD records a symlink as mode 120000 with the link TEXT as its blob: shipped, it landed as
    an unreadable mode-0 file in every project. A deleted one is skipped, as before, and named."""
    mod, hub_root, project, rels = _deleted_hub(hub, tmp_path)
    link = hub_root / "AGENTS-link.md"
    link.symlink_to("AGENTS-kept.md")
    subprocess.run(["git", "-C", str(hub_root), "add", "AGENTS-link.md"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "link"], check=True)
    link.unlink()
    mod.GOVERNANCE_FILES = ["AGENTS-link.md"]
    mod.sync_scripts_to_project(project)
    assert not (project / "AGENTS-link.md").exists()
    assert mod._link_refused["AGENTS-link.md"] == "a symlink in HEAD", (
        mod._link_refused
    )  # W-d537275a


def test_an_unreadable_gone_blob_is_one_warn_not_an_aborted_project(hub, tmp_path: Path) -> None:
    """Hashing the missing path raised FileNotFoundError and the whole project's sync stopped —
    the rest of the walk, the lock and the worktrees skipped. Now it is one WARN line."""
    mod, hub_root, project, rels = _deleted_hub(hub, tmp_path)
    _corrupt_object(hub_root, _rev(hub_root, f"HEAD:{rels['vendored']}"))
    result = mod.sync_scripts_to_project(project)
    assert result.success, result.message
    warned = {r.destination: r.reason for r in result.files if r.action == "WARN"}
    assert warned.get(project / rels["vendored"]) == mod._GONE_UNREADABLE
    lines = mod._file_lines(result.files, verbose=False, dry_run=False)
    assert f"  WARN ({mod._GONE_UNREADABLE}): gone.py" in lines, lines  # its own reason, printed
    assert (project / "libs/vend/kept.py").read_text() == "# libs/vend/kept.py HEAD\n"
    assert (project / ".fabrik" / "synced.lock").is_file(), "the lock leg never ran"


def test_a_project_edit_newer_than_heads_commit_is_not_clobbered(hub, tmp_path: Path) -> None:
    """A gone hub source has no mtime; HEAD's commit time stands in, so the "destination newer"
    guard protects a later project edit exactly as it does for a present source."""
    mod, _hub_root, project, rels = _deleted_hub(hub, tmp_path)
    edited = project / rels["listed"]
    edited.write_text("# a project-side edit\n", encoding="utf-8")  # mtime: now, after HEAD
    result = mod.sync_scripts_to_project(project)
    assert edited.read_text() == "# a project-side edit\n"
    assert any(r.action == "WARN" and r.destination == edited for r in result.files)


def test_the_lock_carries_a_file_shipped_from_head(hub, tmp_path: Path) -> None:
    """The manifest's pairs walk the working tree; a walked file shipped from HEAD was missing from
    the lock, so check_synced_unmodified stopped guarding exactly that copy."""
    mod, _hub_root, project, rels = _deleted_hub(hub, tmp_path)
    mod.sync_scripts_to_project(project)
    import json

    lock = json.loads((project / ".fabrik" / "synced.lock").read_text())
    for key in ("walked", "vendored", "govdir", "listed"):
        assert rels[key] in lock, (rels[key], sorted(lock))


def test_a_gone_source_is_read_once_and_keeps_its_reason(hub, monkeypatch) -> None:
    """Uncached, a gone source cost three blob reads per project; a cache hit must still name it."""
    mod, _hub_root, committed, _untracked = hub
    committed.unlink()
    rel = "scripts/enforcement/committed.py"
    real_run = mod.subprocess.run
    reads: list[list[str]] = []

    def counting(cmd, *a, **kw):
        if "cat-file" in cmd:
            reads.append(cmd)
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(mod.subprocess, "run", counting)
    for _ in range(3):
        mod._head_drift_why.clear()
        assert mod._head_source(committed) == (b"COMMITTED = 1\n", 0o100755)
        assert mod._head_drift_why[rel] == "deleted in the working tree"
    assert len(reads) == 1, reads


def _git_project(project: Path) -> None:
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".gitignore").write_text("# the project's own\n", encoding="utf-8")


def test_the_lock_never_takes_the_projects_own_gitignore(hub, tmp_path: Path) -> None:
    """Review pass 1: the lock's union took every COPY/SKIP result, the `.gitignore` block patch
    among them, so a project adding its own ignore line failed check_synced_unmodified."""
    mod, _hub_root, project, _rels = _deleted_hub(hub, tmp_path)
    _git_project(project)
    mod.sync_scripts_to_project(project)
    import json

    lock = json.loads((project / ".fabrik" / "synced.lock").read_text())
    assert ".gitignore" not in lock, sorted(lock)


def test_the_guard_dates_a_gone_source_by_its_own_last_commit(hub, tmp_path: Path) -> None:
    """Review pass 1: HEAD's LATEST commit time let an unrelated later commit make an older project
    edit look stale — edited after the file's own last commit, it was clobbered."""
    mod, hub_root, project, rels = _deleted_hub(hub, tmp_path)
    two_days, one_day = time.time() - 2 * 86400, time.time() - 86400
    rel = rels["listed"]
    (hub_root / rel).write_text("# v2\n", encoding="utf-8")
    env = {**os.environ, "GIT_COMMITTER_DATE": f"{int(two_days)} +0000"}
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qam", "v2"], check=True, env=env)
    (hub_root / "unrelated.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(hub_root), "add", "unrelated.txt"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "later, unrelated"], check=True)
    (hub_root / rel).unlink()
    edited = project / rel
    edited.write_text("# a project-side edit\n", encoding="utf-8")
    os.utime(edited, (one_day, one_day))
    mod._head_cache.clear()
    mod.sync_scripts_to_project(project)
    assert edited.read_text() == "# a project-side edit\n"


def test_a_head_shipped_copy_carries_its_commit_time(hub, tmp_path: Path) -> None:
    """Written with mtime "now", the copy reads as a newer project edit to every later sync."""
    mod, hub_root, project, rels = _deleted_hub(hub, tmp_path)
    rel = rels["walked"]
    (hub_root / rel).write_text("# v2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(hub_root), "add", rel], check=True)
    two_days = f"{int(time.time() - 2 * 86400)} +0000"  # far from "now", so a match is no accident
    env = {**os.environ, "GIT_COMMITTER_DATE": two_days}
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "v2"], check=True, env=env)
    (hub_root / rel).unlink()
    three_days = time.time() - 3 * 86400  # the stale copy predates the file's own commit
    os.utime(project / rel, (three_days, three_days))
    mod._head_cache.clear()
    mod.sync_scripts_to_project(project)
    when = int(
        subprocess.run(
            ["git", "-C", str(hub_root), "log", "-1", "--format=%ct", "HEAD", "--", rels["walked"]],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert int((project / rels["walked"]).stat().st_mtime) == when


def test_a_head_symlink_in_a_walked_dir_is_not_shipped(hub, tmp_path: Path) -> None:
    """The walk's own symlink skip — `_hub_present`'s check guards only the listed loops."""
    mod, hub_root, project, _rels = _deleted_hub(hub, tmp_path)
    link = hub_root / "libs" / "vend" / "link.py"
    link.symlink_to("kept.py")
    subprocess.run(["git", "-C", str(hub_root), "add", "libs/vend/link.py"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "link"], check=True)
    link.unlink()
    mod.sync_scripts_to_project(project)
    assert not (project / "libs" / "vend" / "link.py").exists()


def test_a_head_read_failing_at_the_copy_is_one_warn(hub, tmp_path: Path, monkeypatch) -> None:
    """The copy consults HEAD again; a transient failure there fell through to `copy2` of a path
    that is gone — FileNotFoundError, the whole project aborted."""
    mod, _hub_root, project, rels = _deleted_hub(hub, tmp_path)
    real = mod._head_source
    calls = {"n": 0}

    def flaky(source):
        calls["n"] += 1
        return None if calls["n"] >= 3 else real(source)  # the copy's own consult is the 3rd

    monkeypatch.setattr(mod, "_head_source", flaky)
    source = mod.FABRIK_ROOT / rels["listed"]
    result = mod.sync_single_file(source, project / rels["listed"])
    assert (result.action, result.reason) == ("WARN", mod._GONE_UNREADABLE), result


@pytest.mark.parametrize("shape", ["new file", "symlink", "forced"])
def test_every_copy_branch_warns_when_the_head_read_fails(
    hub, tmp_path: Path, monkeypatch, shape
) -> None:
    """Review pass 2: the guard covered only the final overwrite; the new-file, symlink and --force
    branches go through `_atomic_copy`, whose `copy2` of the gone path aborted the project. A
    replaced symlink is no longer unlinked first, so a WARN leaves it where it was."""
    mod, _hub_root, project, rels = _deleted_hub(hub, tmp_path)
    dest = project / rels["listed"]
    dest.unlink()
    if shape == "symlink":
        (project / "other.md").write_text("x\n", encoding="utf-8")
        dest.symlink_to(project / "other.md")
    elif shape == "forced":
        dest.write_text("# stale\n", encoding="utf-8")
    real = mod._head_source
    calls = {"n": 0}

    def flaky(source):
        calls["n"] += 1
        return None if calls["n"] >= 2 else real(source)  # the copy's own consult is the 2nd

    monkeypatch.setattr(mod, "_head_source", flaky)
    source = mod.FABRIK_ROOT / rels["listed"]
    result = mod.sync_single_file(source, dest, force=shape == "forced")
    assert (result.action, result.reason) == ("WARN", mod._GONE_UNREADABLE), result
    if shape == "symlink":
        assert dest.is_symlink(), "the link was removed before a copy that never happened"


# ---- W-d537275a: a symlinked hub source is refused, never shipped ---------------------------------
# `_head_source` read `source.resolve()`, i.e. the target the WORKING TREE points at: an uncommitted
# retarget shipped the new target, a link leaving the hub shipped the outside file's working bytes,
# and a committed link replaced by a regular file shipped the link text as a mode-0 file.


def _link_hub(hub, tmp_path: Path):
    mod, hub_root, _committed, _untracked = hub
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "ext.md").write_text("EXTERNAL working bytes\n", encoding="utf-8")
    (hub_root / "a.md").write_text("A committed\n", encoding="utf-8")
    (hub_root / "b.md").write_text("B committed\n", encoding="utf-8")
    (hub_root / "real").mkdir()
    (hub_root / "real" / "x.md").write_text("X committed\n", encoding="utf-8")
    (hub_root / "link.md").symlink_to("a.md")
    (hub_root / "out.md").symlink_to(outside / "ext.md")
    (hub_root / "dirlink").symlink_to("real")
    subprocess.run(["git", "-C", str(hub_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "links"], check=True)
    project = tmp_path / "proj"
    project.mkdir()
    mod._head_unread.clear()
    return mod, hub_root, project


def _refused(mod, source: Path, dest: Path) -> None:
    result = mod.sync_single_file(source, dest)
    assert result.action == "WARN", result
    assert result.reason.startswith("symlinked hub source not shipped"), result
    rel = mod._lexical_rel(source)[1]
    mod._head_source(source)
    assert "symlink" in mod._link_refused.get(rel, ""), mod._link_refused
    assert rel not in mod._head_unread, "a refusal is not a HEAD read failure"


def test_a_retargeted_symlink_is_refused(hub, tmp_path: Path) -> None:
    mod, hub_root, project = _link_hub(hub, tmp_path)
    (hub_root / "link.md").unlink()
    (hub_root / "link.md").symlink_to("b.md")  # the uncommitted retarget
    _refused(mod, hub_root / "link.md", project / "link.md")
    assert not (project / "link.md").exists(), "the working tree's new target shipped"


def test_a_symlink_leaving_the_hub_is_refused(hub, tmp_path: Path) -> None:
    mod, hub_root, project = _link_hub(hub, tmp_path)
    _refused(mod, hub_root / "out.md", project / "out.md")
    assert not (project / "out.md").exists(), "a file outside the hub shipped"


def test_a_link_replaced_by_a_file_is_refused(hub, tmp_path: Path) -> None:
    mod, hub_root, project = _link_hub(hub, tmp_path)
    (hub_root / "link.md").unlink()
    (hub_root / "link.md").write_text("UNCOMMITTED regular file\n", encoding="utf-8")
    _refused(mod, hub_root / "link.md", project / "link.md")
    assert not (project / "link.md").exists(), "the link text or the working file shipped"


def test_a_file_under_a_symlinked_dir_is_refused(hub, tmp_path: Path) -> None:
    mod, hub_root, project = _link_hub(hub, tmp_path)
    _refused(mod, hub_root / "dirlink" / "x.md", project / "x.md")
    assert not (project / "x.md").exists()


@pytest.mark.parametrize("in_tree", [True, False])
def test_a_link_committed_after_the_memo_answered_is_refused(hub, tmp_path, in_tree) -> None:
    """Review pass 1: the memo is per run, and a sibling's commit can add a link mid-run. A stale
    "not a link" answer must not ship it — present, the tree scan catches it; deleted, the HEAD
    listing `_head_source` makes itself does (its blob is link TEXT, once shipped as a mode-0 file)."""
    mod, hub_root, project = _link_hub(hub, tmp_path)
    mod._link_refusal_cache["link.md"] = None  # the memo answered before the commit landed
    if not in_tree:
        (hub_root / "link.md").unlink()
    _refused(mod, hub_root / "link.md", project / "link.md")
    assert not (project / "link.md").exists()


def test_a_source_spelled_through_the_real_root_is_still_checked(hub, tmp_path) -> None:
    """Review pass 1: a hub root reached through a symlink, with a source spelled by the real path,
    fell outside the lexical check while `_head_source` (which resolves both) read through it."""
    mod, hub_root, project = _link_hub(hub, tmp_path)
    alias = (
        tmp_path.parent / f"{tmp_path.name}-alias"
    )  # beside the hub (the fixture hub IS tmp_path)
    alias.symlink_to(hub_root)
    mod.FABRIK_ROOT = alias
    _refused(mod, hub_root / "out.md", project / "out.md")


def test_a_walked_link_deleted_from_the_tree_keeps_its_project_copy(hub, tmp_path) -> None:
    """Review pass 1: HEAD's 120000 entries were left out of the walk, so a link deleted from the
    working tree was in neither live set and the prune deleted the project copy, unnamed."""
    mod, hub_root, project, _rels = _deleted_hub(hub, tmp_path)
    link = hub_root / "libs" / "vend" / "link.py"
    link.symlink_to("kept.py")
    subprocess.run(["git", "-C", str(hub_root), "add", "libs/vend/link.py"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "link"], check=True)
    link.unlink()
    copy = project / "libs" / "vend" / "link.py"
    copy.write_text("# the project's copy\n", encoding="utf-8")
    result = mod.sync_scripts_to_project(project)
    assert copy.read_text() == "# the project's copy\n", "the prune deleted a copy HEAD still lists"
    assert any(r.action == "WARN" and r.destination == copy for r in result.files), result.files


def test_the_writer_never_copies_through_a_refused_link(hub, tmp_path) -> None:
    """Review pass 1: `_atomic_copy` fell back to `copy2` through the link when called directly."""
    mod, hub_root, project = _link_hub(hub, tmp_path)
    with pytest.raises(FileNotFoundError):
        mod._atomic_copy(hub_root / "out.md", project / "out.md")
    assert not (project / "out.md").exists()


def test_the_overwrite_tail_never_copies_through_a_late_link(hub, tmp_path, monkeypatch) -> None:
    """Review pass 2: round 1 guarded `_atomic_copy` but not the overwrite tail's own `copy2`
    fallback — an untracked source turned into a link between consults shipped the outside file."""
    mod, hub_root, project = _link_hub(hub, tmp_path)
    src = hub_root / "u.md"
    src.write_text("UNTRACKED\n", encoding="utf-8")
    dest = project / "u.md"
    dest.write_text("# older\n", encoding="utf-8")
    old = time.time() - 86400
    os.utime(dest, (old, old))
    real = mod._head_source
    calls = {"n": 0}

    def swapping(source):
        calls["n"] += 1
        if calls["n"] == 3:  # the tail's own consult: the source has become a link
            src.unlink()
            src.symlink_to(tmp_path / "outside" / "ext.md")
        return real(source)

    monkeypatch.setattr(mod, "_head_source", swapping)
    result = mod.sync_single_file(src, dest)
    assert result.action == "WARN" and "symlinked hub source" in result.reason, result
    assert dest.read_text() == "# older\n", "the outside file shipped through the late link"


def test_a_directory_link_in_a_walked_dir_is_refused(hub, tmp_path) -> None:
    """A committed directory link inside a walked dir is listed from HEAD and refused, never
    copied (copy2 of a directory raised IsADirectoryError and aborted the project — critique)."""
    mod, hub_root, project, _rels = _deleted_hub(hub, tmp_path)
    (hub_root / "pkg").mkdir()
    (hub_root / "pkg" / "m.py").write_text("M = 1\n", encoding="utf-8")
    (hub_root / "libs" / "vend" / "dirlink").symlink_to("../../pkg")
    subprocess.run(["git", "-C", str(hub_root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(hub_root), "commit", "-qm", "dirlink"], check=True)
    result = mod.sync_scripts_to_project(project)
    assert result.success, result.message
    dest = project / "libs" / "vend" / "dirlink"
    assert any(r.action == "WARN" and r.destination == dest for r in result.files), result.files
    assert not dest.exists()


def test_a_new_file_whose_source_becomes_a_link_names_the_refusal(
    hub, tmp_path, monkeypatch
) -> None:
    """Review pass 3: the new-file branch's copy refused through `_GoneSourceError`, but the WARN
    said "source missing and no readable HEAD copy" — nothing shipped, under the wrong reason."""
    mod, hub_root, project = _link_hub(hub, tmp_path)
    src = hub_root / "u.md"
    src.write_text("UNTRACKED\n", encoding="utf-8")
    real = mod._head_source
    calls = {"n": 0}

    def swapping(source):
        calls["n"] += 1
        if calls["n"] == 2:  # `_atomic_copy`'s own consult
            src.unlink()
            src.symlink_to(tmp_path / "outside" / "ext.md")
        return real(source)

    monkeypatch.setattr(mod, "_head_source", swapping)
    result = mod.sync_single_file(src, project / "u.md")
    assert result.action == "WARN", result
    assert result.reason.startswith("symlinked hub source not shipped"), result
    assert not (project / "u.md").exists()


# ---- W-47d91afa: the enforcement walk prunes its orphans, like the vendored walk -----------------
# A check the hub deleted or renamed stayed in every project forever (82 copies of two retired
# checks in 41 projects, measured 2026-10-20).


def _enf_hub(hub, tmp_path: Path):
    mod, hub_root, _committed, untracked = hub
    untracked.unlink()  # the fixture's untracked file is not part of these cases
    for name in (
        "CORE_SCRIPTS",
        "RUN_SCRIPTS",
        "GOVERNANCE_FILES",
        "GOVERNANCE_TEMPLATES",
        "GOVERNANCE_DIRS",
        "VENDORED_DIRS",
        "REFERENCE_DOCS",
        "AGENT_HOOK_FILES",
    ):
        setattr(mod, name, [])
    enf = tmp_path / "proj" / "scripts" / "enforcement"
    enf.mkdir(parents=True)
    (enf / "committed.py").write_text("COMMITTED = 1\n", encoding="utf-8")
    (enf / "retired_check.py").write_text("# the hub deleted this\n", encoding="utf-8")
    (enf / "__pycache__").mkdir()
    (enf / "__pycache__" / "retired_check.cpython-312.pyc").write_bytes(b"\0")
    return mod, hub_root, tmp_path / "proj", enf


def test_the_enforcement_walk_prunes_its_orphans(hub, tmp_path: Path) -> None:
    mod, _hub_root, project, enf = _enf_hub(hub, tmp_path)
    dry = mod.sync_scripts_to_project(project, dry_run=True)
    assert (enf / "retired_check.py").exists(), "a dry run deletes nothing"
    assert any(
        r.action == "DELETE" and r.destination == enf / "retired_check.py" for r in dry.files
    )
    result = mod.sync_scripts_to_project(project)
    assert not (enf / "retired_check.py").exists(), "the retired check lingered"
    assert (enf / "committed.py").read_text() == "COMMITTED = 1\n", "a live check was pruned"
    assert (enf / "__pycache__").exists(), "bytecode is not the prune's"
    assert any(
        r.action == "DELETE" and r.destination == enf / "retired_check.py" for r in result.files
    )


def test_a_tracked_enforcement_orphan_is_reported_not_deleted(hub, tmp_path: Path) -> None:
    """A project that commits its copies (fabrik-test-saas-skeleton) keeps them: a deletion would
    leave a `D` in its tree. Reported, never deleted."""
    mod, _hub_root, project, enf = _enf_hub(hub, tmp_path)
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(
        ["git", "-C", str(project), "add", "-f", "scripts/enforcement/retired_check.py"],
        check=True,
    )
    result = mod.sync_scripts_to_project(project)
    assert (enf / "retired_check.py").exists()
    assert any(
        r.action == "WARN" and r.destination == enf / "retired_check.py" for r in result.files
    )


def test_no_enforcement_prune_on_a_working_tree_only_listing(hub, tmp_path, monkeypatch) -> None:
    """When HEAD's listing failed, the live set is the working tree alone, and a sibling's
    uncommitted deletion would become a DELETE in every project — so nothing is pruned."""
    mod, _hub_root, project, enf = _enf_hub(hub, tmp_path)
    real = mod._hub_files

    def unreadable(src_dir):
        mod._head_unread["scripts/enforcement/"] = "git ls-tree -r exited 128: simulated"
        return real(src_dir)

    monkeypatch.setattr(mod, "_hub_files", unreadable)
    mod.sync_scripts_to_project(project)
    assert (enf / "retired_check.py").exists()


def test_an_uncommitted_enforcement_deletion_is_not_pruned(hub, tmp_path: Path) -> None:
    """HEAD still lists a file a sibling deleted without committing: it is live, and ships HEAD."""
    mod, hub_root, project, enf = _enf_hub(hub, tmp_path)
    (hub_root / "scripts" / "enforcement" / "committed.py").unlink()
    mod.sync_scripts_to_project(project)
    assert (enf / "committed.py").read_text() == "COMMITTED = 1\n"


def test_a_backup_this_run_made_survives_the_prune(hub, tmp_path: Path) -> None:
    """Review pass 1: `--backup` wrote `<name>.backup.<ts>` beside the check, and the prune — which
    runs after the walk — deleted it in the same run, defeating the flag."""
    mod, _hub_root, project, enf = _enf_hub(hub, tmp_path)
    (enf / "committed.py").write_text("# a stale copy\n", encoding="utf-8")
    mod.sync_scripts_to_project(project, backup=True, force=True)
    assert list(enf.glob("committed.py.backup.*")), "the --backup copy was pruned"
    assert not (enf / "retired_check.py").exists()


def test_a_project_git_that_cannot_answer_keeps_the_orphan(hub, tmp_path: Path) -> None:
    """Review pass 1: a corrupt project index made `ls-files` exit 128, read as "untracked", and
    the prune deleted a tracked copy. Any git failure other than "no match" now keeps the file."""
    mod, _hub_root, project, enf = _enf_hub(hub, tmp_path)
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(
        ["git", "-C", str(project), "add", "-f", "scripts/enforcement/retired_check.py"],
        check=True,
    )
    (project / ".git" / "index").write_bytes(b"not an index")
    mod.sync_scripts_to_project(project)
    assert (enf / "retired_check.py").exists(), "a tracked copy was deleted on a git fatal"


def test_a_live_sync_temp_file_is_left_for_its_writer(hub, tmp_path: Path) -> None:
    """Review pass 1: a concurrent sync's `.sync-tmp-*` file, mid-write, was unlinked before its
    rename. A young one is left alone; an old leftover is pruned."""
    mod, _hub_root, project, enf = _enf_hub(hub, tmp_path)
    young = enf / ".sync-tmp-young"
    young.write_text("mid-write\n", encoding="utf-8")
    old = enf / ".sync-tmp-old"
    old.write_text("leftover\n", encoding="utf-8")
    stale = time.time() - 7200
    os.utime(old, (stale, stale))
    mod.sync_scripts_to_project(project)
    assert young.exists()
    assert not old.exists()
