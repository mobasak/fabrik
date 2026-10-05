"""A freshly scaffolded python project passes the lint and type legs of the gate it ships into.

tryton-crm's completion gate went red right after scaffolding (01M3Q3DBYFTPA944ESADCDXRNR, relayed
as 01M44YG3CA): the vendored GlitchTip scrubber (``glitchtip_init.py``, byte-parity with
site-provisioner) was linted under the project's own rules, and the project's pyproject carried no
exclusion for it. The generated output was never run through the gate it ships into, so the hub
never saw it. This runs the same tools the project gate runs: ruff over the tree and over the
vendored file by name (the gate passes files explicitly, which is why the template sets
``force-exclude``), ``ruff format --check``, and mypy with the project's config.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik.scaffold import FABRIK_ROOT, create_project

requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)

BIN = Path(sys.executable).parent


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=600)


@requires_fabrik_env
def test_scaffolded_python_api_passes_its_own_lint_and_types(tmp_path):
    ruff = BIN / "ruff"
    assert ruff.exists(), f"ruff is not installed next to {sys.executable}"
    create_project(
        name="gate-clean",
        project_type="python-api",
        description="scaffold output passes its own gate",
        base=tmp_path,
        generate_spec=False,
    )
    proj = tmp_path / "gate-clean"
    vendored = Path("src") / "gate_clean" / "glitchtip_init.py"
    assert (proj / vendored).is_file()
    checks = {
        "ruff check .": [str(ruff), "check", "."],
        "ruff check <vendored file>": [str(ruff), "check", str(vendored)],
        "ruff format --check .": [str(ruff), "format", "--check", "."],
        "mypy src": [sys.executable, "-m", "mypy", "--config-file=pyproject.toml", "src"],
    }
    failures = {}
    for label, argv in checks.items():
        r = _run(argv, proj)
        if r.returncode != 0:
            failures[label] = (r.stdout + r.stderr).strip()[-2000:]
    assert failures == {}, failures
