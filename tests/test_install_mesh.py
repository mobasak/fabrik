"""`scripts/sysadmin/install_mesh.sh` (W-6e656dac T04, spec § Lifecycle) and the tracked mesh copies.

The installer puts a reviewed copy of the three tracked mesh scripts (`scripts/sysadmin/mesh/`) into
`~/.claude/bin`: every copy passes `bash -n` and the harness first, each live file is backed up to
`~/.claude/bin/backups/<f>.backup.<ts>` before anything is replaced, and each replace is a rename. Every test here
runs it against a TEMP home and a temp destination with a stub harness — never the operator's ~/.claude/bin.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "scripts" / "sysadmin" / "install_mesh.sh"
MESH = ROOT / "scripts" / "sysadmin" / "mesh"
FILES = ("claude-selfwatch.sh", "claude-reboot-sweep.sh", "claude-mesh-test.sh")


def _src(tmp: Path, **override: str) -> Path:
    src = tmp / "src"
    src.mkdir()
    for f in FILES:
        (src / f).write_text(override.get(f, f"#!/usr/bin/env bash\necho new {f}\n"), encoding="utf-8")
    return src


def _dest(tmp: Path) -> Path:
    dest = tmp / "home" / ".claude" / "bin"
    dest.mkdir(parents=True)
    for f in FILES:
        (dest / f).write_text(f"#!/usr/bin/env bash\necho old {f}\n", encoding="utf-8")
        (dest / f).chmod(0o755)
    return dest


def _harness(tmp: Path, rc: int = 0) -> tuple[Path, Path]:
    log = tmp / "harness.log"
    h = tmp / "harness.sh"
    h.write_text(f'#!/usr/bin/env bash\necho "src=$MESH_TEST_SRC" >> "{log}"\nexit {rc}\n', encoding="utf-8")
    return h, log


def _run(tmp: Path, *args: str, harness: Path) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp / "home"),  # never the operator's home
        "MESH_INSTALL_HARNESS": str(harness),
    }
    return subprocess.run(
        ["bash", str(INSTALL), *args], capture_output=True, text=True, timeout=60, env=env
    )


def _snapshot(dest: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(dest.rglob("*")) if p.is_file()}


def test_backup_first_then_an_atomic_replace(tmp_path: Path) -> None:
    """Each live file is backed up (byte-for-byte) under backups/, then replaced by a rename — a new inode, mode
    0755, no temp file left — after the harness ran on the copies being installed."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, log = _harness(tmp_path)
    old = {f: ((dest / f).read_bytes(), (dest / f).stat().st_ino) for f in FILES}
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode == 0, out.stderr
    assert log.read_text(encoding="utf-8").split() == [f"src={src}"]
    for f in FILES:
        backups = sorted((dest / "backups").glob(f"{f}.backup.*"))
        assert len(backups) == 1, (f, backups)
        assert re.fullmatch(rf"{re.escape(f)}\.backup\.\d{{8}}-\d{{6}}", backups[0].name)
        assert backups[0].read_bytes() == old[f][0]
        assert (dest / f).read_bytes() == (src / f).read_bytes()
        assert (dest / f).stat().st_ino != old[f][1], f"{f} was rewritten in place, not renamed"
        assert (dest / f).stat().st_mode & 0o777 == 0o755
    assert sorted(p.name for p in dest.iterdir()) == sorted([*FILES, "backups"])


def test_no_backup_means_no_replace(tmp_path: Path) -> None:
    """A backup that cannot be written refuses the install before ANY file is replaced."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    (dest / "backups").mkdir()
    (dest / "backups").chmod(0o555)
    before = _snapshot(dest)
    try:
        out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    finally:
        (dest / "backups").chmod(0o755)
    assert out.returncode != 0 and "backup" in out.stderr, out.stderr
    assert _snapshot(dest) == before


def test_a_copy_failing_bash_n_installs_nothing(tmp_path: Path) -> None:
    src = _src(tmp_path, **{"claude-reboot-sweep.sh": "#!/usr/bin/env bash\nif then fi (\n"})
    dest = _dest(tmp_path)
    harness, log = _harness(tmp_path)
    before = _snapshot(dest)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode != 0 and "bash -n" in out.stderr and "claude-reboot-sweep.sh" in out.stderr, out.stderr
    assert _snapshot(dest) == before and not log.exists()


def test_a_red_harness_installs_nothing(tmp_path: Path) -> None:
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path, rc=1)
    before = _snapshot(dest)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode != 0 and "harness" in out.stderr, out.stderr
    assert _snapshot(dest) == before


def test_a_missing_source_installs_nothing(tmp_path: Path) -> None:
    src, dest = _src(tmp_path), _dest(tmp_path)
    (src / "claude-selfwatch.sh").unlink()
    harness, log = _harness(tmp_path)
    before = _snapshot(dest)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode != 0 and "claude-selfwatch.sh" in out.stderr, out.stderr
    assert _snapshot(dest) == before and not log.exists()


def test_an_identical_file_is_left_alone_and_a_new_one_needs_no_backup(tmp_path: Path) -> None:
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    (dest / FILES[0]).write_bytes((src / FILES[0]).read_bytes())
    (dest / FILES[1]).unlink()
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode == 0, out.stderr
    backups = os.listdir(dest / "backups")
    assert len(backups) == 1 and backups[0].startswith(f"{FILES[2]}.backup."), backups
    for f in FILES:
        assert (dest / f).read_bytes() == (src / f).read_bytes()


def test_defaults_are_the_tracked_copies_and_home_bin(tmp_path: Path) -> None:
    """With no flags the source is the script's own mesh/ folder and the destination $HOME/.claude/bin (a temp
    home here)."""
    dest = _dest(tmp_path)
    harness, log = _harness(tmp_path)
    out = _run(tmp_path, harness=harness)
    assert out.returncode == 0, out.stderr
    assert log.read_text(encoding="utf-8").split() == [f"src={MESH}"]
    for f in FILES:
        assert (dest / f).read_bytes() == (MESH / f).read_bytes()


@pytest.mark.parametrize("bad", [("--src",), ("--bogus", "x")])
def test_bad_arguments_are_a_usage_error(tmp_path: Path, bad: tuple[str, ...]) -> None:
    harness, log = _harness(tmp_path)
    out = _run(tmp_path, *bad, harness=harness)
    assert out.returncode == 2 and "usage" in out.stderr and not log.exists(), out.stderr


# --- the tracked sweep (spec L4) ---------------------------------------------------------------------------------
SWEEP = MESH / "claude-reboot-sweep.sh"


def test_tracked_sweep_state_line_is_byte_identical() -> None:
    """The writer (session_orient.py) and the sweep derive the persistent marker dir independently;
    tests/test_session_orient_hook.py checks only the LIVE sweep, so the tracked copy is pinned here."""
    lines = SWEEP.read_text(encoding="utf-8").splitlines()
    assert [ln for ln in lines if ln.startswith("state=")] == [
        'state="${MESH_STATE_DIR:-$HOME/.claude/state/autonomous}"'
    ]


def test_tracked_sweep_never_resumes_with_claude_p() -> None:
    code = [
        ln
        for ln in SWEEP.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert not [ln for ln in code if re.search(r"\bclaude\s+-p\b", ln)]
    assert not [ln for ln in code if "CLAUDE_MESH_AUTONOMOUS=1" in ln]
