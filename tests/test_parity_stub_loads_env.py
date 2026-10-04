"""The scaffold's parity stub loads the project `.env` once it imports the vendored health_probe.

fabrik-lib cfd9215f stopped `health_probe` loading `.env` at import (an explicit `load_env()` now).
Parity rows that read os.environ after the stub's lazy import relied on that load, so the stub calls
`load_env()` itself, once, with a real variable still winning (the 714dbf90e re-vendor review).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_PROBE = """
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("stub", sys.argv[1])
stub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stub)
assert stub._health_probe() is not None
stub._health_probe()
print(os.environ.get("ZZ_PARITY_FROM_DOTENV"), os.environ.get("ZZ_PARITY_REAL"), stub._ENV_LOADED)
"""


def _project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "templates/scaffold/scripts/verify_prod_parity.py", proj / "scripts")
    shutil.copytree(
        REPO / "libs/health_probe",
        proj / "libs/health_probe",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (proj / ".env").write_text("ZZ_PARITY_FROM_DOTENV=loaded\nZZ_PARITY_REAL=from-dotenv\n")
    return proj


def test_the_stub_loads_the_project_env_once_and_a_real_variable_wins(tmp_path):
    proj = _project(tmp_path)
    env = {"PATH": "/usr/bin:/bin", "ZZ_PARITY_REAL": "from-environment"}
    out = subprocess.run(
        [sys.executable, "-c", _PROBE, str(proj / "scripts" / "verify_prod_parity.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == ["loaded", "from-environment", "True"], out
