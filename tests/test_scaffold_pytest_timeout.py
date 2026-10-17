"""Every scaffolded test run gets a per-test time limit (W-046828fb, D-935).

Input domain: every scaffold type create_project emits (wordpress is refused), scaffolded once under the offline
seam tests/conftest.py pins (no venv, pip, pnpm or database). For each emitted directory holding ``test_*.py``,
the grader asks pytest itself — ``_pytest.config.findpaths.determine_setup``, the function a real run calls — which
config file it would load when that directory is the argument, so a config that exists but is never read
(chrome-extension's ``server/pyproject.toml`` for its root ``tests/``) does not count. Assumed invocation: one test
directory per run (the gate's ``pytest tests/``; the saas server's documented ``cd server && pytest tests``); a bare
``pytest`` from a project root whose tests sit only under ``server/`` resolves no config. Trees vendored from
fabrik-lib (``docs-site``) are exempt, their tests and their dependency files both: they are the module's own, and the
hub never edits a vendored copy. ``determine_setup`` is private pytest API; its ``override_ini`` keyword
and its 4-tuple return are pytest 9's (pytest 8 has neither), so an older pytest skips this module with that reason
instead of failing with a TypeError.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from _pytest.config.findpaths import determine_setup

import fabrik.scaffold as scaffold
from fabrik.scaffold import SCAFFOLD_TYPES, create_project

TIMEOUT_KEYS = ("timeout", "faulthandler_timeout")
DEP_FILES = ("requirements.txt", "requirements-dev.txt", "pyproject.toml")
# the `pytest` requirement itself — never pytest-asyncio, pytest-cov or a comment
PYTEST_REQ = re.compile(r"""^\s*["']?pytest(?![\w-])""", re.M)
TIMEOUT_REQ = re.compile(r"""^\s*["']?pytest-timeout(?![\w-])""", re.M)
TYPES = sorted(t for t in SCAFFOLD_TYPES if t != "wordpress")
VENDORED = ("docs-site",)

pytestmark = [
    pytest.mark.skipif(
        not Path("/opt/fabrik").exists() or os.getenv("CI") == "true",
        reason="Requires the full fabrik environment (templates dir)",
    ),
    pytest.mark.skipif(
        int(pytest.__version__.split(".")[0]) < 9,
        reason="determine_setup's override_ini parameter and 4-tuple return are pytest 9's",
    ),
]


@pytest.fixture(scope="module")
def projects(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base = tmp_path_factory.mktemp("timeout")
    out: dict[str, Path] = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
        mp.setattr(scaffold, "_post_scaffold_sync", lambda *_a, **_k: None)
        mp.setattr(scaffold, "_emit_mcp_config", lambda *_a, **_k: None)
        mp.setattr(scaffold, "_install_pre_commit", lambda *_a, **_k: True)
        for kind in TYPES:
            name = f"to-{kind}"[:30]
            create_project(
                name=name, project_type=kind, description="timeout", base=base, generate_spec=False
            )
            out[kind] = base / name
    return out


def _skip(path: Path) -> bool:
    return any(part in {"node_modules", ".venv", ".git"} for part in path.parts)


def _resolved_config(test_dir: Path, root: Path) -> tuple[Path, dict[str, str]] | None:
    """The config file pytest would load with ``test_dir`` as the argument, and its options, or None
    when it would load none inside the project."""
    _rootdir, inipath, inicfg, _ = determine_setup(
        inifile=None,
        override_ini=None,
        args=[str(test_dir)],
        rootdir_cmd_arg=None,
        invocation_dir=root,
    )
    if inipath is None or not inipath.is_relative_to(root):
        return None
    return inipath, {k: str(getattr(v, "value", v)) for k, v in inicfg.items()}


def _bounded(value: str | None) -> bool:
    """A missing key, 0 (which disables the limit), inf and a non-number all leave the test unbounded."""
    try:
        return value is not None and 0 < float(value) < float("inf")
    except ValueError:
        return False


def _test_dirs(root: Path) -> list[Path]:
    return sorted(
        {
            p.parent
            for p in root.rglob("test_*.py")
            if not _skip(p.relative_to(root)) and p.relative_to(root).parts[0] not in VENDORED
        }
    )


def _dep_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.name in DEP_FILES
        and p.is_file()
        and not _skip(p.relative_to(root))
        and p.relative_to(root).parts[0] not in VENDORED
    )


@pytest.mark.parametrize("kind", TYPES)
def test_every_test_directory_resolves_a_timeout(projects: dict[str, Path], kind: str) -> None:
    root = projects[kind]
    missing = []
    for test_dir in _test_dirs(root):
        resolved = _resolved_config(test_dir, root)
        rel = test_dir.relative_to(root).as_posix()
        if resolved is None:
            missing.append(f"{rel}: no pytest config resolves")
            continue
        path, opts = resolved
        for key in TIMEOUT_KEYS:
            value = opts.get(key)
            if not _bounded(value):
                missing.append(f"{rel}: {path.relative_to(root).as_posix()} {key}={value!r}")
    assert not missing, missing


@pytest.mark.parametrize("kind", TYPES)
def test_every_pytest_dependency_brings_pytest_timeout(
    projects: dict[str, Path], kind: str
) -> None:
    root = projects[kind]
    lacking = [
        p.relative_to(root).as_posix()
        for p in _dep_files(root)
        if PYTEST_REQ.search(p.read_text(encoding="utf-8"))
        and not TIMEOUT_REQ.search(p.read_text(encoding="utf-8"))
    ]
    assert not lacking, lacking


@pytest.mark.parametrize("kind", TYPES)
def test_every_project_with_pytest_config_installs_the_plugin(
    projects: dict[str, Path], kind: str
) -> None:
    root = projects[kind]
    if not any(_resolved_config(d, root) for d in _test_dirs(root)):
        pytest.skip(f"{kind}: no test directory resolves a pytest config")
    assert any(TIMEOUT_REQ.search(p.read_text(encoding="utf-8")) for p in _dep_files(root)), [
        p.relative_to(root).as_posix() for p in _dep_files(root)
    ]


def test_file_worker_dev_file_carries_the_makefile_tools(projects: dict[str, Path]) -> None:
    """file-worker's Makefile installs requirements-dev.txt, then runs ruff and mypy from .venv; its copied
    pytest config sets asyncio_mode and timeout, which need pytest-asyncio and pytest-timeout."""
    dev = projects["file-worker"] / "requirements-dev.txt"
    assert dev.is_file()
    text = dev.read_text(encoding="utf-8")
    for tool in ("pytest", "pytest-asyncio", "pytest-timeout", "ruff", "mypy"):
        assert re.search(rf"^{re.escape(tool)}(?![\w-])", text, re.M), tool
