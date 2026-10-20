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
_VENV_LINE = "\t@test -x .venv/bin/python || python -m venv --clear .venv"
_PIP_LINE = "\t.venv/bin/pip install -r requirements.txt"


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
    assert _recipe(makefile, "install") == [_VENV_LINE, _PIP_LINE], makefile
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

    assert dry("install") == [
        "test -x .venv/bin/python || python -m venv --clear .venv",
        ".venv/bin/pip install -r requirements.txt",
    ]
    assert dry("dev") == [".venv/bin/python -m worker.main"]


def _run_venv_line(project: Path, python: str) -> None:
    # the EMITTED recipe's first line as make's /bin/sh runs it, `python` bound to this interpreter
    first = _recipe((project / "Makefile").read_text(), "install")[0]
    assert "python -m venv" in first, first
    line = first.lstrip("\t@").replace("python -m venv", f"{python} -m venv --without-pip")
    subprocess.run(["sh", "-c", line], cwd=project, check=True, timeout=120)


def test_an_existing_venv_is_reused(tmp_path, monkeypatch):
    project = _scaffold(tmp_path, monkeypatch)
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(project / ".venv")],
        check=True,
        timeout=120,
    )
    cfg = project / ".venv" / "pyvenv.cfg"
    marker = project / ".venv" / "marker"
    marker.write_text("setup-dev's packages")
    before = hashlib.md5(cfg.read_bytes()).hexdigest()
    _run_venv_line(project, sys.executable)
    assert hashlib.md5(cfg.read_bytes()).hexdigest() == before
    assert marker.read_text() == "setup-dev's packages"


@pytest.mark.parametrize("state", ["absent", "dangling"])
def test_a_missing_or_broken_venv_is_created(state, tmp_path, monkeypatch):
    project = _scaffold(tmp_path, monkeypatch)
    if state == "dangling":
        (project / ".venv" / "bin").mkdir(parents=True)
        (project / ".venv" / "bin" / "python").symlink_to(project / "gone")
    _run_venv_line(project, sys.executable)
    assert (
        subprocess.run(
            [str(project / ".venv" / "bin" / "python"), "-c", "import sys; print(sys.prefix)"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        .stdout.strip()
        .endswith(".venv")
    )


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
    ],
    ids=["other-body", "second-uv-sync", "spaced-rule-other-body", "two-install-lines"],
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
    assert "uv sync" not in (project / "Makefile").read_text()
