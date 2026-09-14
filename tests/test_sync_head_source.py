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
from pathlib import Path

import pytest

REPO = Path("/opt/fabrik")
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
    mod._HUB_ROOT = tmp_path
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
    `git ls-files -s`. A synced hook that lands 644 does not run."""
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
