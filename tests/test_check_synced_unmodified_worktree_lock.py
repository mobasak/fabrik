"""check_synced_unmodified.py in a linked worktree that has no lock of its own (W-c77f91c6).

A worktree is born without `.fabrik/synced.lock` (Claude Code copies the `.worktreeinclude`
set, which carries the check but not the lock; the sync copies the main checkout's lock in on
its next run). Until then the check used to skip and read green. It now grades the worktree
against the MAIN checkout's lock, present files only. Real git repos and `git worktree add`
under tmp_path; the module runs in-process with FABRIK_ROOT pointed at a tmp hub that has no
manifest, so the live /opt/fabrik never answers for the fixture.
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
    _lock(main, {"rules/a.md": _md5("new\n")})
    wt = _worktree(main, tmp_path / "wt")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "   - rules/a.md" in out
    assert str(main / ".fabrik/synced.lock") in out
    assert f"cp {main / 'rules/a.md'} rules/a.md" in out


def test_borrowed_lock_skips_absent_rows(tmp_path, hub, monkeypatch, capsys):
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    _lock(main, {"rules/a.md": _md5("same\n"), "rules/never-copied.md": _md5("x\n")})
    wt = _worktree(main, tmp_path / "wt")
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 0, out
    assert "DELETED" not in out
    assert str(main / ".fabrik/synced.lock") in out
    assert "1 not yet received" in out


def test_own_lock_still_reds_a_deletion(tmp_path, hub, monkeypatch, capsys):
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    wt = _worktree(main, tmp_path / "wt")
    _lock(wt, {"rules/a.md": _md5("same\n"), "rules/gone.md": _md5("x\n")})
    rc, out = _run(_load(monkeypatch, hub), wt, monkeypatch, capsys)
    assert rc == 1, out
    assert "rules/gone.md — DELETED locally" in out


def test_no_lock_anywhere_still_skips(tmp_path, hub, monkeypatch, capsys):
    main = _repo(tmp_path / "main", {"rules/a.md": "same\n"})
    wt = _worktree(main, tmp_path / "wt")
    module = _load(monkeypatch, hub)
    for root in (main, wt):
        rc, out = _run(module, root, monkeypatch, capsys)
        assert rc == 0, out
        assert "synced-files check skipped" in out


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
