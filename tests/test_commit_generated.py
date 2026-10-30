# AFTER-EDIT: none
"""W-5568be8d: a generator commits its OWN output in a main checkout, and nothing else.

Every test builds a throwaway main checkout under tmp_path; nothing here touches the live tree.
The helper under test is ``scripts/commit_generated.py``; the collector
(``scripts/sysadmin/kaizen_collect_v2.py``) is wired to it, and ``scripts/sync_projects.py``
stops rewriting PORTS.md when nothing changed.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cg = _load("commit_generated", "scripts/commit_generated.py")

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for var in ("GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "FABRIK_ROOT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FABRIK_GENERATED_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(cg, "LOCK_RETRY_S", 0.01)


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r.stdout.strip()


def _main_checkout(tmp_path: Path, files: dict[str, str], branch: str = "master") -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def _status(repo: Path) -> str:
    return git(repo, "status", "--porcelain")


def _landed(status: str) -> bool:
    return status.startswith("committed")


def test_clean_file_is_committed(tmp_path):
    repo = _main_checkout(tmp_path, {"log.md": "a\n", "other.md": "x\n"})
    (repo / "other.md").write_text("x\nsibling\n", encoding="utf-8")  # unrelated dirt stays
    git(repo, "add", "other.md")  # and a sibling's staged path is not bundled
    target = repo / "log.md"
    before = cg.snapshot([target])
    target.write_text("a\nb\n", encoding="utf-8")
    base = git(repo, "rev-parse", "HEAD")

    status = cg.commit_own([target], before, writer="kaizen-collector", context="test")

    assert _landed(status), status
    head = git(repo, "rev-parse", "HEAD")
    assert git(repo, "rev-parse", "HEAD^") == base
    assert git(repo, "show", "--name-only", "--format=", head) == "log.md"
    assert git(repo, "show", f"{head}:log.md") == "a\nb"
    trailers = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%B"],
        capture_output=True,
        text=True,
    ).stdout
    parsed = subprocess.run(
        ["git", "interpret-trailers", "--parse"], input=trailers, capture_output=True, text=True
    ).stdout
    assert "Agent-Role: primary" in parsed
    assert "Agent-Name: kaizen-collector" in parsed
    assert _status(repo) == "M  other.md"  # log.md clean in tree AND index; other.md untouched


def test_preexisting_edit_is_never_committed(tmp_path):
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    target = repo / "log.md"
    target.write_text("a\nSIBLING WIP\n", encoding="utf-8")  # someone's edit, before the write
    before = cg.snapshot([target])
    target.write_text("a\nSIBLING WIP\ngenerated\n", encoding="utf-8")
    base = git(repo, "rev-parse", "HEAD")

    status = cg.commit_own([target], before, writer="w", context="c")

    assert not _landed(status), status
    assert git(repo, "rev-parse", "HEAD") == base
    assert _status(repo) == "M log.md"


def test_staged_path_is_left_alone(tmp_path):
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    target = repo / "log.md"
    before = cg.snapshot([target])
    target.write_text("staged\n", encoding="utf-8")
    git(repo, "add", "log.md")
    target.write_text("staged\ngenerated\n", encoding="utf-8")
    base = git(repo, "rev-parse", "HEAD")

    status = cg.commit_own([target], before, writer="w", context="c")

    assert not _landed(status), status
    assert git(repo, "rev-parse", "HEAD") == base
    assert git(repo, "diff", "--cached", "--name-only") == "log.md"


def _attempt(target: Path, text: str) -> str:
    before = cg.snapshot([target])
    target.write_text(text, encoding="utf-8")
    return cg.commit_own([target], before, writer="w", context="c")


def test_not_a_main_checkout_commits_nothing(tmp_path):
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    head = git(repo, "rev-parse", "HEAD")
    # (1) a linked worktree — on branch `main`, so only the main-checkout guard can refuse it
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "main", str(wt))
    status = _attempt(wt / "log.md", "a\nwt\n")
    assert not _landed(status) and "linked worktree" in status, status
    assert git(wt, "rev-parse", "HEAD") == head
    # (2) not git at all
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "log.md").write_text("a\n", encoding="utf-8")
    assert not _landed(_attempt(plain / "log.md", "b\n"))
    # (3) a detached HEAD
    git(repo, "checkout", "-q", "--detach", head)
    assert not _landed(_attempt(repo / "log.md", "a\ndetached\n"))
    git(repo, "checkout", "-q", "--", "log.md")
    # (4) a branch other than master/main
    git(repo, "checkout", "-q", "-b", "feature")
    assert not _landed(_attempt(repo / "log.md", "a\nfeature\n"))
    git(repo, "checkout", "-q", "--", "log.md")
    git(repo, "checkout", "-q", "master")
    # (5) mid-revert: git ITSELF allows a partial commit here (it refuses one mid merge or
    # cherry-pick), so only this module's in-progress guard keeps the commit out
    (repo / ".git" / "REVERT_HEAD").write_text(head + "\n", encoding="utf-8")
    status = _attempt(repo / "log.md", "a\nrevert\n")
    assert not _landed(status) and "REVERT_HEAD" in status, status
    assert git(repo, "rev-parse", "HEAD") == head
    (repo / ".git" / "REVERT_HEAD").unlink()
    git(repo, "checkout", "-q", "--", "log.md")
    # (6) a path HEAD does not hold is never committed
    new = repo / "new.md"
    before = cg.snapshot([new])
    new.write_text("fresh\n", encoding="utf-8")
    status = cg.commit_own([new], before, writer="w", context="c")
    assert not _landed(status) and "not tracked at HEAD" in status, status
    assert git(repo, "rev-parse", "HEAD") == head


def test_main_branch_is_accepted(tmp_path):
    repo = _main_checkout(tmp_path, {"log.md": "a\n"}, branch="main")
    assert _landed(_attempt(repo / "log.md", "a\nmain\n"))
    assert _status(repo) == ""


def test_moved_head_and_held_lock(tmp_path, monkeypatch):
    repo = _main_checkout(tmp_path, {"log.md": "a\n", "other.md": "x\n"})
    target = repo / "log.md"

    # (1) HEAD moves on ANOTHER path between the snapshot and the commit: lands on the new HEAD.
    before = cg.snapshot([target])
    target.write_text("a\ngen1\n", encoding="utf-8")
    (repo / "other.md").write_text("y\n", encoding="utf-8")
    git(repo, "commit", "-q", "-m", "sibling", "--", "other.md")
    sibling = git(repo, "rev-parse", "HEAD")
    assert _landed(cg.commit_own([target], before, writer="w", context="c"))
    assert git(repo, "rev-parse", "HEAD^") == sibling
    assert git(repo, "show", "HEAD:other.md") == "y"
    assert _status(repo) == ""

    # (2) a peer holds index.lock past every retry: nothing lands, the leftover is recorded …
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    head = git(repo, "rev-parse", "HEAD")
    status = _attempt(target, "a\ngen2\n")
    assert not _landed(status) and "index.lock" in status, status
    assert git(repo, "rev-parse", "HEAD") == head
    lock.unlink()
    # … and the next run lands it, since the dirt is still this helper's own on the same blob.
    assert _landed(_attempt(target, "a\ngen2\n"))
    assert git(repo, "show", "HEAD:log.md") == "a\ngen2"
    assert _status(repo) == ""

    # (3) a lock that clears inside the retries lands the commit in the same run.
    lock.write_text("", encoding="utf-8")
    real_sleep = cg.time.sleep
    monkeypatch.setattr(cg.time, "sleep", lambda s: (lock.unlink(missing_ok=True), real_sleep(0)))
    assert _landed(_attempt(target, "a\ngen3\n"))
    monkeypatch.setattr(cg.time, "sleep", real_sleep)

    # (4) a leftover whose path changed at HEAD since it was recorded is never committed.
    lock.write_text("", encoding="utf-8")
    assert not _landed(_attempt(target, "a\ngen4\n"))  # recorded on gen3's blob
    lock.unlink()
    mine = target.read_text(encoding="utf-8")
    target.write_text("a\nsomeone else\n", encoding="utf-8")
    git(repo, "commit", "-q", "-m", "someone", "--", "log.md")
    target.write_text(mine, encoding="utf-8")  # the leftover, now on a moved blob
    status = cg.commit_own([target], cg.snapshot([target]), writer="w", context="c")
    assert not _landed(status), status
    assert git(repo, "show", "HEAD:log.md") == "a\nsomeone else"


def _sync_projects(monkeypatch, root: Path):
    monkeypatch.setenv("FABRIK_ROOT", str(root))
    sp = _load("sync_projects_under_test", "scripts/sync_projects.py")
    monkeypatch.setattr(sp, "FABRIK_ROOT", root)
    monkeypatch.setattr(sp, "scan_projects", lambda: [])
    monkeypatch.setattr(sp, "detect_deletions", lambda projects: [])
    monkeypatch.setattr(sp, "save_registry", lambda projects: root / "data" / "projects.yaml")
    return sp


def test_sync_projects_does_not_churn(tmp_path, monkeypatch):
    ports = (
        "# Ports\n\n<!-- AUTO-GENERATED:PORTS:START -->\nold\n<!-- AUTO-GENERATED:PORTS:END -->\n"
    )
    catalog = (
        "# Catalog\n\n<!-- AUTO-GENERATED:PROJECTS:START -->\nold\n"
        "<!-- AUTO-GENERATED:PROJECTS:END -->\n"
    )
    repo = _main_checkout(tmp_path, {"PORTS.md": ports, "docs/PROJECT_CATALOG.md": catalog})
    base = git(repo, "rev-parse", "HEAD")
    sp = _sync_projects(monkeypatch, repo)

    assert sp.main() == 0
    assert "Last synced" not in (repo / "PORTS.md").read_text(encoding="utf-8")
    assert git(repo, "rev-parse", "HEAD") == base  # sync_projects commits nothing (W-7999e0ea)
    stamps = {p: (repo / p).stat().st_mtime_ns for p in ("PORTS.md", "docs/PROJECT_CATALOG.md")}

    assert sp.main() == 0  # nothing changed: neither file is rewritten
    for p, ns in stamps.items():
        assert (repo / p).stat().st_mtime_ns == ns, p


def test_collector_upsert_commits_its_rows(tmp_path, monkeypatch):
    kc = _load("kaizen_collect_v2_under_test", "scripts/sysadmin/kaizen_collect_v2.py")
    header = "| " + " | ".join(kc.COLUMNS) + " |\n|" + "---|" * len(kc.COLUMNS) + "\n"
    logs = {
        "docs/reference/agents/kaizen-log-infra.md": "# infra\n\n" + header,
        "docs/reference/agents/kaizen-log-fleet.md": "# fleet\n\n" + header,
    }
    repo = _main_checkout(tmp_path, logs)
    monkeypatch.setenv("KAIZEN_LOCK_DIR", str(tmp_path / "locks"))
    # A fresh interpreter (-P: no cwd on sys.path) imports the collector by its file path, as the
    # cron does, so ONLY the collector's own sys.path lines can resolve `import commit_generated` —
    # this process's module cache (which holds it, loaded above) is not inherited.
    program = (
        "import importlib.util, sys\nfrom pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('kc', {str(REPO / 'scripts/sysadmin/kaizen_collect_v2.py')!r})\n"
        "kc = importlib.util.module_from_spec(spec); sys.modules['kc'] = kc\n"
        "spec.loader.exec_module(kc)\n"
        "cells = ['2026-10-29'] + ['—'] * (len(kc.COLUMNS) - 1)\n"
        f"kc.upsert_logs_and_commit([{', '.join(f'Path({str(repo / rel)!r})' for rel in logs)}], cells)\n"
        "print('commit_generated from', sys.modules['commit_generated'].__file__)\n"
    )
    run = subprocess.run(
        [sys.executable, "-P", "-B", "-c", program], capture_output=True, text=True, timeout=120
    )
    assert run.returncode == 0, run.stderr
    assert str(REPO / "scripts" / "commit_generated.py") in run.stdout, run.stdout + run.stderr

    assert _status(repo) == ""
    head = git(repo, "rev-parse", "HEAD")
    assert set(git(repo, "show", "--name-only", "--format=", head).split()) == set(logs)
    assert "2026-10-29" in git(repo, "show", f"{head}:docs/reference/agents/kaizen-log-infra.md")


# --- review pass 1 (W-5568be8d): one test per confirmed defect, each red on the pinned code ---


def test_caller_git_env_does_not_redirect_the_commit(tmp_path, monkeypatch):
    """AS-2: a GIT_WORK_TREE (or any repo-locating GIT_* variable) in the caller's environment
    pointed git elsewhere, so a good main checkout read as 'detached HEAD'."""
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    monkeypatch.setenv("GIT_COMMON_DIR", str(tmp_path / "nowhere"))
    status = _attempt(repo / "log.md", "a\nb\n")
    assert _landed(status), status


def test_a_glob_character_in_the_name_matches_that_file_only(tmp_path):
    """AS-5: `a*b.md` was read as a pathspec glob that also matched `axb.md`, so the target was
    refused; with literal pathspecs it lands and the sibling's edit is left alone."""
    repo = _main_checkout(tmp_path, {"a*b.md": "a\n", "axb.md": "x\n"})
    (repo / "axb.md").write_text("x\nSIBLING WIP\n", encoding="utf-8")
    status = _attempt(repo / "a*b.md", "a\ngen\n")
    assert _landed(status), status
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "a*b.md"
    assert _status(repo) == "M axb.md"


def test_no_git_group_writes_no_state(tmp_path, monkeypatch):
    """BS-1: a run whose paths reach no main checkout (a tmp log, a linked worktree) wrote an
    empty state file into the real ~/.claude/state."""
    state = tmp_path / "state-dir" / "generated-output.json"
    monkeypatch.setenv("FABRIK_GENERATED_STATE", str(state))
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "log.md").write_text("a\n", encoding="utf-8")
    assert not _landed(_attempt(plain / "log.md", "b\n"))
    assert not state.parent.exists()


def test_a_corrupt_state_file_is_read_as_empty(tmp_path, monkeypatch):
    """AS-7: a state file that is not a JSON object must not stop a clean write from landing."""
    state = tmp_path / "state.json"
    state.write_text("[not json", encoding="utf-8")
    monkeypatch.setenv("FABRIK_GENERATED_STATE", str(state))
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    assert _landed(_attempt(repo / "log.md", "a\nb\n"))


def test_mid_rebase_commits_nothing(tmp_path):
    """AS-7: the rebase-merge / rebase-apply directory guards had no test."""
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    head = git(repo, "rev-parse", "HEAD")
    for name in ("rebase-merge", "rebase-apply"):
        (repo / ".git" / name).mkdir()
        status = _attempt(repo / "log.md", f"a\n{name}\n")
        assert not _landed(status) and name in status, status
        (repo / ".git" / name).rmdir()
        git(repo, "checkout", "-q", "--", "log.md")
    assert git(repo, "rev-parse", "HEAD") == head


def test_a_commit_that_landed_but_timed_out_reads_as_landed(tmp_path, monkeypatch):
    """BS-4 / AS-6: a slow post-commit hook timing the call out after the commit landed was
    reported 'left dirty' and recorded a leftover for a committed path."""
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    real = cg._commit

    def _lands_then_times_out(top, rels, msg):
        real(top, rels, msg)
        return False, "timed out after 60s"

    monkeypatch.setattr(cg, "_commit", _lands_then_times_out)
    status = _attempt(repo / "log.md", "a\nb\n")
    assert _landed(status), status
    assert cg._load_state() == {}


def test_a_same_path_ref_move_before_the_commit_is_named(tmp_path, monkeypatch, capsys):
    """AH-1: a ref-only move of the branch that changes the same path between the eligibility
    check and the commit is reverted by the commit; it must be named on stderr."""
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    real = cg._commit

    def _merge_owner_moves_the_ref(top, rels, msg):
        blob = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input="a\nmerged\n",
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "-C", str(repo), "mktree"],
            input=f"100644 blob {blob}\tlog.md\n",
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        new = git(repo, "commit-tree", tree, "-p", "HEAD", "-m", "merge")
        git(repo, "update-ref", "refs/heads/master", new)
        git(repo, "reset", "-q", "--", "log.md")  # the owner's carry realigns the index
        return real(top, rels, msg)

    monkeypatch.setattr(cg, "_commit", _merge_owner_moves_the_ref)
    _attempt(repo / "log.md", "a\ngen\n")
    assert "REVERTS that change" in capsys.readouterr().err


def test_autocrlf_output_is_not_flagged_as_foreign(tmp_path, capsys):
    """AS-4: under core.autocrlf=input a CRLF write is committed LF; hashing the raw bytes without
    the path's filters flagged the commit as holding bytes the generator did not write."""
    repo = _main_checkout(tmp_path, {"log.md": "a\n"})
    git(repo, "config", "core.autocrlf", "input")
    status = _attempt(repo / "log.md", "a\r\nb\r\n")
    assert _landed(status), status
    assert "did not write" not in capsys.readouterr().err
