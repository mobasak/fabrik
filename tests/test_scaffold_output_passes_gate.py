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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik.scaffold import FABRIK_ROOT, create_project

requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)

# The tools are resolved as scripts/final_gate.py resolves them from the PROJECT root: the project's
# own .venv first (its ruff/mypy versions are what its gate runs), then beside this interpreter, then PATH.
_HUB_RUFF = Path(sys.executable).parent / "ruff"


def _tools(proj: Path) -> tuple[str | None, str]:
    venv = proj / ".venv" / "bin"
    ruff = venv / "ruff"
    python = venv / "python"
    has_mypy = python.exists() and _run([str(python), "-c", "import mypy"], proj).returncode == 0
    resolved_ruff = (
        str(ruff)
        if ruff.exists()
        else (str(_HUB_RUFF) if _HUB_RUFF.exists() else shutil.which("ruff"))
    )
    return resolved_ruff, str(python) if has_mypy else sys.executable


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=600)


@requires_fabrik_env
@pytest.mark.parametrize("project_type", ["python-api", "python-api-gpu"])
def test_scaffolded_python_project_passes_its_own_lint_and_types(tmp_path, project_type):
    create_project(
        name="gate-clean",
        project_type=project_type,
        description="scaffold output passes its own gate",
        base=tmp_path,
        generate_spec=False,
    )
    proj = tmp_path / "gate-clean"
    ruff, python = _tools(proj)
    assert ruff, "ruff is in neither the project venv, beside the interpreter, nor on PATH"
    pkg = Path("src") / "gate_clean"
    vendored = pkg / "glitchtip_init.py"
    assert (proj / vendored).is_file()
    # The gate formats changed .py files only (never markdown), and runs mypy on the src package.
    py_dirs = [d for d in ("src", "tests", "scripts") if (proj / d).is_dir()]
    checks = {
        "ruff check .": [ruff, "check", "."],
        "ruff check <vendored file>": [ruff, "check", str(vendored)],
        "ruff format --check <python dirs>": [ruff, "format", "--check", *py_dirs],
        "mypy src/<pkg>": [python, "-m", "mypy", "--config-file=pyproject.toml", str(pkg)],
    }
    failures = {}
    for label, argv in checks.items():
        r = _run(argv, proj)
        if r.returncode != 0:
            failures[label] = (r.stdout + r.stderr).strip()[-2000:]
    assert failures == {}, (project_type, failures)
