"""Every check the hub ships to projects in scripts/enforcement/ is ruff-formatted.

check_lint_ratchet.py carried a stray blank line for three weeks (c2bd9b6c1 to the fix, mail
01M46GJZ2ER3FV64G01XRJKJGT): the hub gate formats only the files a change touches, and a project
gate ignores the synced directory, so nothing graded the shipped copy. A whole-tree
``ruff format --check`` in a scaffolded project tripped on it. The files are passed by NAME, because
ruff honours a project's gitignore for directory arguments and that made the old grader flaky.

Cobra check (D-253): the cheapest way to pass is to run ``ruff format`` on the directory, which is
the outcome wanted; excluding a file from the glob would also pass, so the glob is the whole
directory with no allowlist.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HUB_RUFF = Path(sys.executable).parent / "ruff"
RUFF = str(_HUB_RUFF) if _HUB_RUFF.exists() else shutil.which("ruff")


def test_every_synced_enforcement_script_is_ruff_formatted() -> None:
    files = sorted(str(p) for p in (ROOT / "scripts" / "enforcement").glob("*.py"))
    assert files, "no scripts/enforcement/*.py found — the glob regressed"
    assert RUFF, "ruff is not installed beside this interpreter or on PATH"
    proc = subprocess.run(
        [RUFF, "format", "--check", *files], cwd=ROOT, capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, (
        f"{len(files)} files checked; unformatted:\n{proc.stdout}{proc.stderr}"
    )
