"""The hub's vendored `libs/deep_research` must import itself the way canonical fabrik-lib does.

The vendoring commit (e33495d4) rewrote the package's two self-imports to `libs.deep_research.…`,
which only resolves when `/opt/fabrik` itself is on sys.path — true in the hub, false in every
project that takes `/fabrik-rivals`' hub fallback (`rivals_run._resolve_engine` puts
`/opt/fabrik/libs` on the path, as canonical top-level imports need). So the fallback path — the
one exercised only by repos WITHOUT a local copy — failed importing the engine (youtube
01M1R7GK8RHJ63QJ4RFFPHFH70, 2026-09-05). Un-forking the two lines is the class fix; widening the
fallback to insert `/opt/fabrik` would shadow a project's own `libs` package.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "libs" / "deep_research"


def test_vendored_package_has_no_hub_relative_self_import():
    hits = [
        (p.name, line)
        for p in PKG.glob("*.py")
        for line in p.read_text(encoding="utf-8").splitlines()
        if re.match(r"^\s*(from|import)\s+libs\.", line)
    ]
    assert hits == [], hits


def test_hub_fallback_imports_the_engine_from_a_foreign_repo(tmp_path: Path):
    """A project-shaped dir: its own `libs/` (no engine), the synced driver under `scripts/`."""
    (tmp_path / "libs" / "something_of_theirs").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "rivals_run.py", tmp_path / "scripts" / "rivals_run.py")
    code = (
        "import sys; sys.path.insert(0, r'%s'); import rivals_run as rr; "
        "print('engine:', rr._resolve_engine()); import deep_research; "
        "print('imported from:', deep_research.__file__)" % (tmp_path / "scripts")
    )
    r = subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=tmp_path, capture_output=True, text=True, timeout=120
    )
    assert r.returncode == 0, r.stderr[-800:]
    assert "engine: hub" in r.stdout and str(ROOT / "libs" / "deep_research") in r.stdout, r.stdout
