"""A freshly scaffolded python project passes the lint and type legs of the gate it ships into.

tryton-crm's completion gate went red right after scaffolding (01M3Q3DBYFTPA944ESADCDXRNR, relayed
as 01M44YG3CA): the vendored GlitchTip scrubber (``glitchtip_init.py``, byte-parity with
site-provisioner) was linted under the project's own rules, and the project's pyproject carried no
exclusion for it. The generated output was never run through the gate it ships into, so the hub
never saw it. This runs ruff (check and ``format --check``) on the project's own .py files by name,
as the gate passes changed files, the vendored one included (which is why the template sets
``force-exclude``), and mypy on ``src/<pkg>`` with the project's config.
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
# project has no .venv of its own here. ruff is found beside this interpreter (the hub venv), else on
# PATH.
_HUB_RUFF = Path(sys.executable).parent / "ruff"
RUFF = str(_HUB_RUFF) if _HUB_RUFF.exists() else shutil.which("ruff")


# The scaffold default, a name that sorts BEFORE ``fastapi_user_auth`` (an import order that depended on
# the name passed only for names after it), and the longest name the scaffolder accepts (50 characters —
# a line carrying the name must not reflow under ruff format).
NAMES = ["gate-clean", "acme-svc", "an-extremely-long-saas-application-name-for-reflow"]


def _run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=600)


def _run_input(argv: list[str], cwd: Path, stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=600)


@requires_fabrik_env
@pytest.mark.parametrize("name", [NAMES[0], NAMES[2]])
@pytest.mark.parametrize("project_type", ["python-api", "python-api-gpu"])
def test_scaffolded_python_project_passes_its_own_lint_and_types(tmp_path, project_type, name):
    assert RUFF, f"ruff is neither beside {sys.executable} nor on PATH"
    create_project(
        name=name,
        project_type=project_type,
        description="scaffold output passes its own gate",
        base=tmp_path,
        generate_spec=False,
    )
    proj = tmp_path / name
    pkg = Path("src") / name.replace("-", "_")
    vendored = pkg / "glitchtip_init.py"
    assert (proj / vendored).is_file()
    # The project's OWN Python files, passed by name as the gate passes changed files. Never a
    # directory walk: scripts/ holds the hub-synced enforcement copies, gitignored in the project,
    # which ruff honoured only some of the time (a flaky red on a hub file the project never edits).
    candidates = sorted(
        str(f.relative_to(proj))
        for d in ("src", "tests", "scripts")
        for f in (proj / d).rglob("*.py")
    )
    # git decides what is the project's own: the synced hub scripts are in the scaffold's .gitignore,
    # and a scaffolded scripts/ file the project owns (verify_prod_parity.py) is not.
    ignored = set(
        _run_input(["git", "check-ignore", "--stdin"], proj, "\n".join(candidates)).stdout.split()
    )
    own = [f for f in candidates if f not in ignored]
    assert str(vendored) in own and "scripts/verify_prod_parity.py" in own, own
    assert not any(f.startswith("scripts/enforcement/") for f in own), own
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


@requires_fabrik_env
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("project_type", ["saas-skeleton", "static-site", "office-extension"])
def test_scaffolded_server_backend_passes_its_own_lint_and_types(tmp_path, project_type, name):
    """W-1c722f35: the saas family's server/ backend ships three vendored trees (glitchtip_init.py,
    fastapi_user_auth, libs/audit_log). ruff resolves the nearest pyproject.toml per file and mypy reads
    its working directory's, so server/ carries its own config, and the WHOLE directory is linted, as a
    gate rooted at server/ would."""
    assert RUFF, f"ruff is neither beside {sys.executable} nor on PATH"
    create_project(
        name=name,
        project_type=project_type,
        description="server backend passes its own gate",
        base=tmp_path,
        generate_spec=False,
    )
    server = tmp_path / name / "server"
    vendored = Path("src") / name.replace("-", "_") / "glitchtip_init.py"
    assert (server / vendored).is_file() and (server / "pyproject.toml").is_file()
    assert (server / "src" / "fastapi_user_auth").is_dir() and (server / "libs").is_dir()
    checks = {
        "ruff check .": [RUFF, "check", "."],
        "ruff check <vendored file>": [RUFF, "check", str(vendored)],
        "ruff format --check .": [RUFF, "format", "--check", "."],
        "mypy src": [sys.executable, "-m", "mypy", "--config-file=pyproject.toml", "src"],
    }
    failures = {}
    for label, argv in checks.items():
        r = _run(argv, server)
        if r.returncode != 0:
            failures[label] = (r.stdout + r.stderr).strip()[-2000:]
    assert failures == {}, (project_type, name, RUFF, failures)


@requires_fabrik_env
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("project_type", ["chrome-extension", "mobile-app"])
def test_every_server_src_backend_lints_and_types_under_its_own_config(tmp_path, project_type, name):
    """01M47Z0D: chrome-extension and mobile-app also ship a server/src backend, and got no
    server/pyproject.toml — ruff ran with no project config and mypy on its defaults. Each now carries
    the root template's rules, and passes them from server/."""
    assert RUFF, f"ruff is neither beside {sys.executable} nor on PATH"
    create_project(
        name=name,
        project_type=project_type,
        description="server backend passes its own gate",
        base=tmp_path,
        generate_spec=False,
    )
    server = tmp_path / name / "server"
    config = (server / "pyproject.toml").read_text()
    assert "[tool.ruff" in config and "[tool.mypy]" in config, config
    checks = {
        "ruff check .": [RUFF, "check", "."],
        "ruff format --check .": [RUFF, "format", "--check", "."],
        "mypy src": [sys.executable, "-m", "mypy", "--config-file=pyproject.toml", "src"],
    }
    failures = {}
    for label, argv in checks.items():
        r = _run(argv, server)
        if r.returncode != 0:
            failures[label] = (r.stdout + r.stderr).strip()[-2000:]
    assert failures == {}, (project_type, name, failures)


def test_the_hub_ruff_passes_every_template_file():
    """A template file is graded by two configs: the scaffolded project's (above) and the hub's own,
    which an editor or a bare `ruff check` uses on the bytes in templates/. 10c243a6d sorted the
    mobile-app server imports for the project config and broke the hub's (2 I001); the template's
    hub-only server/pyproject.toml names the same first-party packages."""
    assert RUFF, f"ruff is neither beside {sys.executable} nor on PATH"
    repo = Path(__file__).resolve().parents[1]
    r = _run([RUFF, "check", "--output-format=concise", "templates/"], repo)
    assert r.returncode == 0, r.stdout + r.stderr


@requires_fabrik_env
@pytest.mark.parametrize(
    ("project_type", "typed"),
    [("python-api", "mypy src"), ("file-worker", "mypy --explicit-package-bases worker")],
)
def test_make_lint_types_the_package_not_the_whole_tree(tmp_path, project_type, typed):
    """W-1c722f35: `mypy .` walked scripts/enforcement (hub-synced, duplicate module names) and was
    red on a fresh project; lint and gate-lean type the project's own package — src for python-api,
    worker/ for file-worker (which has no src/)."""
    create_project(
        name="gate-clean",
        project_type=project_type,
        description="make lint types the package",
        base=tmp_path,
        generate_spec=False,
    )
    makefile = (tmp_path / "gate-clean" / "Makefile").read_text()
    assert "mypy ." not in makefile, makefile
    assert makefile.count(typed) == 2, makefile
    assert (tmp_path / "gate-clean" / typed.split()[-1]).is_dir(), typed


@requires_fabrik_env
@pytest.mark.parametrize(("project_type", "sub"), [("python-api", "."), ("static-site", "server")])
def test_the_vendored_libs_exclusion_does_not_hide_a_projects_own_libs_dir(
    tmp_path, project_type, sub
):
    """W-1c722f35 closing pass: a bare "libs" pattern excluded EVERY directory named libs at any depth,
    so project-owned code under src/<pkg>/libs/ was never linted. "libs/*" is anchored to the root."""
    assert RUFF, f"ruff is neither beside {sys.executable} nor on PATH"
    create_project(
        name="gate-clean",
        project_type=project_type,
        description="own libs dir is linted",
        base=tmp_path,
        generate_spec=False,
    )
    base = tmp_path / "gate-clean" / sub
    own = base / "src" / "gate_clean" / "libs" / "own.py"
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_text("import os\n")
    r = _run([RUFF, "check", "--output-format=concise", str(own.relative_to(base))], base)
    assert r.returncode == 1 and "F401" in r.stdout, r.stdout + r.stderr
