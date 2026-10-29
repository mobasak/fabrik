"""check_synced_unmodified.py in a linked worktree that has no lock of its own (W-c77f91c6).

A worktree is born without `.fabrik/synced.lock` (Claude Code copies the `.worktreeinclude`
set, which carries the check but not the lock; the sync copies the main checkout's lock in on
its next run). Until then the check used to skip and read green. It now grades the worktree
against the MAIN checkout's lock, present files only. Real git repos and `git worktree add`
under tmp_path; the check runs in-process with FABRIK_ROOT pointed at a tmp hub (no manifest
unless a test writes one), so the live /opt/fabrik manifest never answers for the fixture. The
final_gate tests load the real check unpatched; they read only the lock's keys, never the
manifest.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

CHECK = Path(__file__).resolve().parents[1] / "scripts/enforcement/check_synced_unmodified.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main"]


def _load(monkeypatch: pytest.MonkeyPatch, hub: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_synced_unmodified_wt", CHECK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "FABRIK_ROOT", hub)
    return module


def _run(module: ModuleType, root: Path, monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["check", "--project-root", str(root)])
    rc = module.main()
    return rc, capsys.readouterr().out


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def _repo(path: Path, files: dict[str, str]) -> Path:
    subprocess.run([*GIT, "init", "-q", str(path)], check=True)
    for rel, text in files.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(text)
    subprocess.run([*GIT, "-C", str(path), "add", "-A"], check=True)
    subprocess.run([*GIT, "-C", str(path), "commit", "-qm", "base"], check=True)
    return path


def _worktree(main: Path, path: Path) -> Path:
    subprocess.run([*GIT, "-C", str(main), "worktree", "add", "-q", str(path), "HEAD"], check=True)
    return path


def _lock(root: Path, rows: dict[str, str]) -> None:
    (root / ".fabrik").mkdir(exist_ok=True)
    (root / ".fabrik/synced.lock").write_text(json.dumps(rows))


@pytest.fixture
def hub(tmp_path: Path) -> Path:
    path = tmp_path / "hub"
    path.mkdir()
    return path


def test_borrowed_lock_reds_a_stale_copy(tmp_path, hub, monkeypatch, capsys):
    main = _repo(tmp_path / "main", {"rules/a.md": "old\n"})
    (main / "rules/a.md").write_text("new\n")  # the sync refreshed main, the commit lags
    _lock(main, {"rules/a.md": _md5("new\n"), "rules/never-copied.md": _md5("x\n")})
    wt = _worktree(main, tmp_path / "wt")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "   - rules/a.md" in out
    assert "never-copied" not in out
    assert (
        f"differ from the main checkout's lock ({main / '.fabrik/synced.lock'}; 1 not yet received)"
        in out
    )
    assert "You edited a synced copy" not in out
    assert f"cp {main / 'rules/a.md'} rules/a.md" in out


def test_borrowed_lock_skips_absent_rows(tmp_path, hub, monkeypatch, capsys):
    # a seeded row is exempt, never counted as a file present and matching
    (hub / "scripts").mkdir()
    (hub / "scripts/fabrik_synced_manifest.py").write_text(
        'SEEDED_NOT_ENFORCED = {"PORTS.md"}\nRETIRED_VENDORED_DIRS = ()\n'
    )
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    _lock(
        main,
        {"rules/a.md": _md5("same\n"), "rules/never-copied.md": _md5("x\n"), "PORTS.md": "0"},
    )
    wt = _worktree(main, tmp_path / "wt")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 0, out
    assert "DELETED" not in out
    assert (
        f"✓ all 1 Fabrik-synced files present match the main checkout's lock "
        f"({main / '.fabrik/synced.lock'}); 1 not yet received"
    ) in out


def test_own_lock_still_reds_a_deletion(tmp_path, hub, monkeypatch, capsys):
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    wt = _worktree(main, tmp_path / "wt")
    _lock(wt, {"rules/a.md": _md5("same\n"), "rules/gone.md": _md5("x\n")})
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "rules/gone.md — DELETED locally" in out


def test_no_borrowable_lock_still_skips(tmp_path, hub, monkeypatch, capsys):
    stale = {"rules/a.md": _md5("other\n")}  # any lock borrowed here would red
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    wt = _worktree(main, tmp_path / "wt")
    # a bare repo's worktree: the git dir's parent is no checkout, even when it holds a lock
    bare_parent = tmp_path / "bareparent"
    bare_parent.mkdir()
    subprocess.run(
        [*GIT, "clone", "-q", "--bare", str(main), str(bare_parent / "b.git")], check=True
    )
    _lock(bare_parent, stale)
    bare_wt = tmp_path / "barewt"
    subprocess.run(
        [*GIT, "-C", str(bare_parent / "b.git"), "worktree", "add", "-q", str(bare_wt), "HEAD"],
        check=True,
    )
    module = _load(monkeypatch, hub)
    for root in (main, wt, bare_wt):
        rc, out = _run(module, root, monkeypatch, capsys)
        assert rc == 0, (root, out)
        assert "synced-files check skipped" in out, (root, out)
    # a worktree SUBDIRECTORY whose main checkout has a lock: the root is not the worktree
    _lock(main, stale)
    rc, out = _run(module, wt / "rules", monkeypatch, capsys)
    assert rc == 0, out
    assert "synced-files check skipped" in out


@pytest.mark.parametrize("var", ["GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"])
def test_an_exported_git_env_var_never_picks_the_lock(tmp_path, hub, monkeypatch, capsys, var):
    """A hook or wrapper's leftover GIT_* value names another repo; the lock is still the main's."""
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    _lock(main, {"rules/a.md": _md5("same\n")})
    wt = _worktree(main, tmp_path / "wt")
    other = _repo(tmp_path / "other", {"rules/a.md": "same\n"})
    _lock(other, {"rules/a.md": _md5("other\n")})  # borrowing this one would red
    values = {
        "GIT_DIR": other / ".git",
        "GIT_WORK_TREE": other,
        "GIT_COMMON_DIR": other / ".git",
        "GIT_INDEX_FILE": other / ".git/index",
    }
    monkeypatch.setenv(var, str(values[var]))
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 0, out
    assert f"present match the main checkout's lock ({main / '.fabrik/synced.lock'})" in out


def test_hub_worktree_is_the_source(tmp_path, monkeypatch, capsys):
    hub_main = _repo(tmp_path / "hubmain", {"rules/a.md": "same\n"})
    wt = _worktree(hub_main, tmp_path / "hubwt")
    rc, out = _run(_load(monkeypatch, hub_main), wt, monkeypatch, capsys)
    assert rc == 0, out
    assert "source repo" in out


def test_unreadable_borrowed_lock_skips(tmp_path, hub, monkeypatch, capsys):
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    (main / ".fabrik").mkdir()
    (main / ".fabrik/synced.lock").write_text("{not json")
    wt = _worktree(main, tmp_path / "wt")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 0, out
    assert "unreadable" in out
    assert str(main / ".fabrik/synced.lock") in out


def test_final_gate_excludes_borrowed_synced_paths(tmp_path, monkeypatch):
    """The gate's lint/auto-fix exclusion reads the same lock the check grades against, so a
    re-copied synced file in a lockless worktree is never reformatted into a fresh red."""
    sys.path.insert(0, str(CHECK.parents[1]))
    try:
        import final_gate
    finally:
        sys.path.pop(0)
    main = _repo(tmp_path / "main", {"scripts/x.py": "x = 1\n"})
    _lock(main, {"scripts/x.py": _md5("x = 1\n")})
    wt = _worktree(main, tmp_path / "wt")
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", wt)
    assert final_gate._synced_paths() == {"scripts/x.py"}


def test_a_dangling_symlink_is_present_not_unreceived(tmp_path, hub, monkeypatch, capsys):
    """A path the worktree holds as a dangling symlink was received and broken, not never received:
    the borrowed lock reds it DELETED exactly as an own lock does."""
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    _lock(main, {"rules/a.md": _md5("same\n")})
    wt = _worktree(main, tmp_path / "wt")
    (wt / "rules/a.md").unlink()
    (wt / "rules/a.md").symlink_to(tmp_path / "nowhere")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "rules/a.md — DELETED locally" in out


def test_a_dangling_parent_symlink_is_present_not_unreceived(tmp_path, hub, monkeypatch, capsys):
    """The same holds one level up: a synced file under a dangling DIRECTORY symlink was received
    and broken, while a file missing under a real directory was never received."""
    main = _repo(
        tmp_path / "main", {"rules/a.md": "same\n", "docs/b.md": "same\n", "tools/t.py": "t\n"}
    )
    _lock(
        main,
        {
            "rules/a.md": _md5("same\n"),
            "docs/b.md": _md5("same\n"),
            "docs/c.md": _md5("x\n"),
            "tools/t.py": _md5("t\n"),
        },
    )
    wt = _worktree(main, tmp_path / "wt")
    (wt / "rules/a.md").unlink()
    (wt / "rules").rmdir()
    (wt / "rules").symlink_to(tmp_path / "nowhere-dir")
    (wt / "tools/t.py").unlink()
    (wt / "tools").rmdir()
    (wt / "tools").write_text("a file where the synced directory was\n")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "rules/a.md — DELETED locally" in out
    assert "tools/t.py — DELETED locally" in out
    assert "docs/c.md" not in out
    assert "1 not yet received" in out


def test_a_borrowed_red_asks_git_for_the_main_checkout_once(tmp_path, hub, monkeypatch, capsys):
    """The borrowed header and the `cp` remedy name ONE main checkout: the remedy reuses the one
    the lock was borrowed from instead of asking git a second time."""
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    _lock(main, {"rules/a.md": _md5("other\n")})
    wt = _worktree(main, tmp_path / "wt")
    module = _load(monkeypatch, hub)
    calls: list[Path] = []
    real = module._main_checkout
    monkeypatch.setattr(module, "_main_checkout", lambda root: calls.append(root) or real(root))
    rc, out = _run(module, wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "Re-copy it:" in out
    assert len(calls) == 1, calls


def test_a_retired_dir_stays_exempt_under_a_borrowed_lock(tmp_path, hub, monkeypatch, capsys):
    (hub / "scripts").mkdir()
    (hub / "scripts/fabrik_synced_manifest.py").write_text(
        'SEEDED_NOT_ENFORCED = set()\nRETIRED_VENDORED_DIRS = ("libs/old/",)\n'
    )
    main = _repo(tmp_path / "main", {"libs/old/x.py": "mine\n", "rules/a.md": "same\n"})
    _lock(main, {"libs/old/x.py": _md5("as distributed\n"), "rules/a.md": _md5("same\n")})
    wt = _worktree(main, tmp_path / "wt")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 0, out
    assert "✓ all 1 Fabrik-synced files present" in out


def test_final_gate_falls_back_to_the_own_lock_when_the_check_cannot_load(tmp_path, monkeypatch):
    sys.path.insert(0, str(CHECK.parents[1]))
    try:
        import final_gate
    finally:
        sys.path.pop(0)
    main = _repo(tmp_path / "main", {"scripts/x.py": "x = 1\n"})
    _lock(main, {"scripts/x.py": _md5("x = 1\n")})
    wt = _worktree(main, tmp_path / "wt")
    _lock(wt, {"scripts/own.py": _md5("y\n")})

    def refuse(*_a, **_k):
        raise ImportError("the check moved")

    monkeypatch.setattr(importlib.util, "spec_from_file_location", refuse)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", wt)
    assert final_gate._synced_paths() == {"scripts/own.py"}
    (wt / ".fabrik/synced.lock").unlink()
    assert final_gate._synced_paths() == set()
