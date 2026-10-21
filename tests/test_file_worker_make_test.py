"""A fresh Python scaffold's `make test` runs a real test with the project's own tools (W-ad15212d).

A scaffolded file-worker shipped an empty tests/, so `make test` exited 5 ("collected 0 items"), and the
shared Makefile.python ran bare `pytest`/`ruff`/`mypy` from PATH instead of the project's `.venv` (a fresh
python-api's PATH pytest could not even collect its own tests). The file-worker now ships
tests/test_logger.py over worker/logger.py, and the template's test/lint/format targets run `.venv/bin`
tools behind a prerequisite rule that names `make setup-dev` when one is missing.
"""

from __future__ import annotations

import itertools
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.scaffold import create_project

_ROOT = Path(__file__).resolve().parent.parent
_TYPES = ("file-worker", "python-api", "python-api-gpu")
_RECIPE_LINE = re.compile(r"^\t@?\.venv/bin/(pytest|ruff|mypy)\b")
_PREREQS = {
    "test": {".venv/bin/pytest"},
    "lint": {".venv/bin/ruff", ".venv/bin/mypy"},
    "format": {".venv/bin/ruff"},
}


@pytest.fixture(scope="module")
def projects(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base = tmp_path_factory.mktemp("scaffolds")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(scaffold, "TEMPLATE_DIR", _ROOT / "templates" / "scaffold")
        mp.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
        out = {}
        for i, project_type in enumerate(_TYPES):
            name = f"mt-{i}"
            create_project(
                name=name,
                project_type=project_type,
                description="make test",
                base=base,
                generate_spec=False,
            )
            out[project_type] = base / name
    return out


def _run_starter(proj: Path) -> subprocess.CompletedProcess[str]:
    # a subprocess with the project as cwd: the project's own pytest config, never the hub's;
    # LOG_LEVEL=ERROR, because a starter test that needs the default level fails in a shell exporting it
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_logger.py"],
        cwd=proj,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "LOG_LEVEL": "ERROR"},
    )


def _make(proj: Path, *targets: str) -> subprocess.CompletedProcess[str]:
    # no inherited make flags: a caller's `-n` or `-k` would change what make does here
    drop = {"MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL"}
    env = {k: v for k, v in os.environ.items() if k not in drop}
    return subprocess.run(
        ["make", *targets], cwd=proj, capture_output=True, text=True, timeout=60, env=env
    )


def _rule(makefile: str, target: str) -> tuple[set[str], list[str]]:
    """The rule's prerequisites and its recipe (the tab-led lines under the header)."""
    header, body = makefile.split(f"\n{target}:", 1)[1].split("\n", 1)
    return set(header.split()), list(
        itertools.takewhile(lambda ln: ln.startswith("\t"), body.splitlines())
    )


def test_file_worker_ships_a_passing_starter_test(projects):
    proj = projects["file-worker"]
    assert (proj / "tests" / "test_logger.py").is_file(), sorted(
        p.name for p in (proj / "tests").iterdir()
    )
    r = _run_starter(proj)
    assert r.returncode == 0 and "3 passed" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize(
    ("label", "old", "new"),
    [
        (
            "redactor returns its input",
            "    for k in list(event_dict.keys()):\n",
            "    return event_dict\n    for k in list(event_dict.keys()):\n",
        ),
        (
            "redactor dropped from the configured chain",
            "            _redact_sensitive,\n            structlog.processors.JSONRenderer(),\n        ],\n"
            "        wrapper_class=",
            "            structlog.processors.JSONRenderer(),\n        ],\n        wrapper_class=",
        ),
    ],
)
def test_starter_test_catches_broken_redaction(projects, tmp_path, label, old, new):
    proj = tmp_path / "mut"
    shutil.copytree(projects["file-worker"], proj, ignore=shutil.ignore_patterns(".git"))
    logger = proj / "worker" / "logger.py"
    text = logger.read_text()
    assert text.count(old) == 1, label
    logger.write_text(text.replace(old, new))
    r = _run_starter(proj)
    assert r.returncode == 1 and "failed" in r.stdout, (label, r.stdout + r.stderr)


@pytest.mark.parametrize("project_type", _TYPES)
def test_dev_targets_use_the_project_venv(projects, project_type):
    makefile = (projects[project_type] / "Makefile").read_text()
    for target, wanted in _PREREQS.items():
        prereqs, recipe = _rule(makefile, target)
        assert wanted <= prereqs, (project_type, target, prereqs)
        assert recipe and all(_RECIPE_LINE.match(line) for line in recipe), (
            project_type,
            target,
            recipe,
        )


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
@pytest.mark.parametrize("project_type", _TYPES)
def test_a_missing_venv_tool_names_setup_dev(projects, project_type):
    proj = projects[project_type]
    assert not (proj / ".venv").exists()
    r = _make(proj, "test")
    assert r.returncode == 2, r.stdout + r.stderr
    assert ".venv/bin/pytest is missing: run 'make setup-dev' first" in r.stderr, r.stderr
    assert ".venv/bin/pytest -v" not in r.stdout, r.stdout


@pytest.mark.skipif(shutil.which("make") is None, reason="make is not installed")
@pytest.mark.parametrize("project_type", _TYPES)
def test_a_present_venv_tool_runs(projects, tmp_path, project_type):
    """With the tool in .venv the prerequisite rule stays quiet and the recipe runs it (a tool path
    listed in .PHONY would fire the missing-tool rule even here)."""
    proj = tmp_path / "proj"
    shutil.copytree(projects[project_type], proj, ignore=shutil.ignore_patterns(".git"))
    stub = proj / ".venv" / "bin" / "pytest"
    stub.parent.mkdir(parents=True)
    stub.write_text('#!/bin/sh\necho "stub pytest $*"\n')
    stub.chmod(0o755)
    r = _make(proj, "test")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "stub pytest -v" in r.stdout and "is missing" not in r.stderr, r.stdout + r.stderr
