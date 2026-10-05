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

# The hub's ruff and mypy: tests/conftest.py scaffolds OFFLINE (FABRIK_SCAFFOLD_OFFLINE), so a scaffolded
# project has no .venv of its own here. ruff is found beside this interpreter, else on PATH, as
# scripts/final_gate.py finds it.
_HUB_RUFF = Path(sys.executable).parent / "ruff"
RUFF = str(_HUB_RUFF) if _HUB_RUFF.exists() else shutil.which("ruff")


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=600)


@requires_fabrik_env
@pytest.mark.parametrize("project_type", ["python-api", "python-api-gpu"])
def test_scaffolded_python_project_passes_its_own_lint_and_types(tmp_path, project_type):
    assert RUFF, f"ruff is neither beside {sys.executable} nor on PATH"
    create_project(
        name="gate-clean",
        project_type=project_type,
        description="scaffold output passes its own gate",
        base=tmp_path,
        generate_spec=False,
    )
    proj = tmp_path / "gate-clean"
    pkg = Path("src") / "gate_clean"
    vendored = pkg / "glitchtip_init.py"
    assert (proj / vendored).is_file()
    # The project's OWN Python files, passed by name as the gate passes changed files. Never a
    # directory walk: scripts/ holds the hub-synced enforcement copies, gitignored in the project,
    # which ruff honoured only some of the time (a flaky red on a hub file the project never edits).
    own = sorted(
        str(f.relative_to(proj)) for d in ("src", "tests") for f in (proj / d).rglob("*.py")
    )
    assert str(vendored) in own and len(own) > 1, own
    checks = {
        "ruff check <own .py>": [RUFF, "check", *own],
        "ruff check <vendored file>": [RUFF, "check", str(vendored)],
        "ruff format --check <own .py>": [RUFF, "format", "--check", *own],
        "mypy src/<pkg>": [sys.executable, "-m", "mypy", "--config-file=pyproject.toml", str(pkg)],
    }
    failures = {}
    for label, argv in checks.items():
        r = _run(argv, proj)
        if r.returncode != 0:
            failures[label] = (r.stdout + r.stderr).strip()[-2000:]
    assert failures == {}, (project_type, RUFF, failures)
