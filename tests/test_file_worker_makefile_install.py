"""A scaffolded file-worker's `make install` fills `.venv` from requirements.txt (W-0259f23b).

The shared Makefile.python template's `install:` runs `uv sync`, which needs a `[project]` table; a file-worker's
root pyproject.toml is tool-only (its deps live in requirements.txt), so `uv sync` created an EMPTY `.venv` on
uv's default Python and exited 0 — a silent false success. The file-worker patch now reuses a working `.venv`
(never rewriting the one `make setup-dev` made) or creates one with the same `python`, then
`.venv/bin/pip install -r requirements.txt`; `make dev` runs the worker from that venv. An install rule whose
body drifted from `uv sync` is refused; a template with no install rule is left alone.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.scaffold import create_project

_ROOT = Path(__file__).resolve().parent.parent
_REFUSAL = ".venv exists but .venv/bin/python cannot run: remove .venv and run make install again"
_INSTALL = [
    "if [ ! -e .venv ]; then python -m venv .venv; elif [ ! -x .venv/bin/python ]; then "
    f"echo '{_REFUSAL}' >&2; exit 1; fi",
    ".venv/bin/python -m pip --version >/dev/null 2>&1 || .venv/bin/python -m ensurepip",
    ".venv/bin/python -m pip install -r requirements.txt",
]


def _scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tpl: Path | None = None) -> Path:
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl or _ROOT / "templates" / "scaffold")
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    create_project(
        name="fw-install", project_type="file-worker", description="install", base=tmp_path
    )
    return tmp_path / "fw-install"


def _recipe(makefile: str, target: str) -> list[str]:
    body = makefile.split(f"\n{target}:\n", 1)[1]
    return body.split("\n\n", 1)[0].splitlines()


def test_install_installs_requirements_into_the_venv(tmp_path, monkeypatch):
    makefile = (_scaffold(tmp_path, monkeypatch) / "Makefile").read_text()
    assert _recipe(makefile, "install") == [
        "\t@" + _INSTALL[0],
        "\t@" + _INSTALL[1],
        "\t" + _INSTALL[2],
    ], makefile
    assert "uv sync" not in makefile
    assert _recipe(makefile, "dev") == ["\t.venv/bin/python -m worker.main"], makefile


def test_make_runs_the_venv_commands(tmp_path, monkeypatch):
    if shutil.which("make") is None:
        pytest.skip("GNU make is not on PATH")
    project = _scaffold(tmp_path, monkeypatch)

    def dry(target: str) -> list[str]:
        out = subprocess.run(
            ["make", "-n", "-C", str(project), target],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
        return [ln for ln in out.splitlines() if not ln.startswith("make")]

    assert dry("install") == _INSTALL
    assert dry("dev") == [".venv/bin/python -m worker.main"]


def _make_install(project: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the EMITTED `make install` for real: `python` on PATH is this test's interpreter, and an
    empty requirements.txt keeps pip offline (the recipe's venv and pip steps all still run)."""
    if shutil.which("make") is None:
        pytest.skip("GNU make is not on PATH")
    shim = tmp_path / "shim"
    shim.mkdir(exist_ok=True)
    (shim / "python").unlink(missing_ok=True)
    (shim / "python").symlink_to(sys.executable)
    (project / "requirements.txt").write_text("")
    env = {"PATH": f"{shim}:/usr/bin:/bin", "HOME": str(tmp_path), "PIP_NO_INPUT": "1"}
    return subprocess.run(
        ["make", "-C", str(project), "install"],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )


def _pip_works(project: Path) -> bool:
    py = project / ".venv" / "bin" / "python"
    return (
        subprocess.run(
            [str(py), "-m", "pip", "--version"], capture_output=True, timeout=60
        ).returncode
        == 0
    )


def test_a_fresh_project_gets_a_venv_with_pip(tmp_path, monkeypatch):
    project = _scaffold(tmp_path, monkeypatch)
    r = _make_install(project, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _pip_works(project)


@pytest.mark.parametrize("with_pip", [True, False], ids=["setup-dev-venv", "pipless-uv-style-venv"])
def test_an_existing_venv_is_kept_and_gets_pip(with_pip, tmp_path, monkeypatch):
    """setup-dev's venv is reused untouched; a pip-less venv (what the old `uv sync` left) keeps its
    packages and gains pip, so the install that follows can run."""
    project = _scaffold(tmp_path, monkeypatch)
    venv_args = [sys.executable, "-m", "venv", str(project / ".venv")]
    subprocess.run(venv_args + ([] if with_pip else ["--without-pip"]), check=True, timeout=300)
    cfg = project / ".venv" / "pyvenv.cfg"
    marker = project / ".venv" / "marker"
    marker.write_text("packages already installed")
    before = hashlib.md5(cfg.read_bytes()).hexdigest()
    r = _make_install(project, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert hashlib.md5(cfg.read_bytes()).hexdigest() == before
    assert marker.read_text() == "packages already installed"
    assert _pip_works(project)


@pytest.mark.parametrize("state", ["dangling-python", "python3-only", "windows-layout"])
def test_an_unrunnable_venv_is_refused_never_deleted(state, tmp_path, monkeypatch):
    project = _scaffold(tmp_path, monkeypatch)
    venv = project / ".venv"
    if state == "dangling-python":
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "python").symlink_to(project / "gone")
    elif state == "python3-only":
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "python3").symlink_to(sys.executable)
    else:
        (venv / "Scripts").mkdir(parents=True)
        (venv / "Scripts" / "python.exe").write_text("")
    marker = venv / "marker"
    marker.write_text("packages already installed")
    r = _make_install(project, tmp_path)
    assert r.returncode != 0
    assert _REFUSAL in r.stderr, r.stderr
    assert marker.read_text() == "packages already installed"


def _drifted_template(tmp_path: Path, old: str, new: str) -> Path:
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    mk = tpl / "docker" / "Makefile.python"
    src = mk.read_text()
    assert old in src
    mk.write_text(src.replace(old, new))
    return tpl


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("install:\n\tuv sync\n", "install:\n\tuv sync --frozen\n"),
        ("install:\n\tuv sync\n", "install:\n\tuv sync\n\nreinstall:\n\tuv sync\n"),
        ("install:\n\tuv sync\n", "install :\n\tpip install .\n"),
        ("install:\n\tuv sync\n", "install:\n\tuv sync\ninstall-again:\n\tuv sync\n"),
        # make lets a later rule override the patched one (review C4)
        ("install:\n\tuv sync\n", "install:\n\tuv sync\n\ninstall:\n\tpip install -e .\n"),
        # an extra body line would survive the replacement (review C5)
        ("install:\n\tuv sync\n", "install:\n\tuv sync\n\tuv run pre-commit install\n"),
    ],
    ids=[
        "other-body",
        "second-uv-sync",
        "spaced-rule-other-body",
        "two-install-lines",
        "second-install-rule",
        "extra-body-line",
    ],
)
def test_a_drifted_install_recipe_fails_the_scaffold(old, new, tmp_path, monkeypatch):
    tpl = _drifted_template(tmp_path, old, new)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-drift"
    project.mkdir()
    with pytest.raises(ValueError, match="install"):
        scaffold._scaffold_file_worker(project, "fw-drift", "drift")
    assert not (project / "Makefile").exists()


@pytest.mark.parametrize(
    "makefile",
    [
        ".PHONY: dev install\ndev:\n\tuvicorn x.main:app\n",  # a mention, no rule
        "install := 1\ndev:\n\tuvicorn x.main:app\n",  # an assignment, no rule
        "dev:\n\tuvicorn x.main:app\n",  # no install at all
    ],
    ids=["phony-mention", "assignment", "absent"],
)
def test_a_template_with_no_install_rule_is_left_alone(makefile, tmp_path, monkeypatch):
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    (tpl / "docker" / "Makefile.python").write_text(makefile)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-plain"
    project.mkdir()
    scaffold._scaffold_file_worker(project, "fw-plain", "plain")
    written = (project / "Makefile").read_text()
    # nothing install-shaped is added: only the dev rewrite touches this template
    assert written == makefile.replace(
        "\tuvicorn x.main:app\n", "\t.venv/bin/python -m worker.main\n"
    )
