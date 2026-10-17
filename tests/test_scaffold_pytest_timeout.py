"""Every scaffolded test run gets a per-test time limit (W-046828fb, D-935).

Input domain: every scaffold type create_project emits (wordpress is refused), scaffolded once under the offline
seam tests/conftest.py pins (no venv, pip, pnpm or database). For each emitted directory holding ``test_*.py``,
the grader resolves the config file pytest itself would load for that directory — its own search order, walking
up to the project root: ``pytest.ini``, ``.pytest.ini``, ``pyproject.toml`` with a ``[tool.pytest.ini_options]``
table, ``tox.ini`` with ``[pytest]``, ``setup.cfg`` with ``[tool:pytest]`` — so a config that exists but is
never read (chrome-extension's ``server/pyproject.toml`` for its root ``tests/``) does not count.
"""

from __future__ import annotations

import configparser
import os
import re
import tomllib
from pathlib import Path

import pytest

import fabrik.scaffold as scaffold
from fabrik.scaffold import SCAFFOLD_TYPES, create_project

TIMEOUT_KEYS = ("timeout", "faulthandler_timeout")
DEP_FILES = ("requirements.txt", "requirements-dev.txt", "pyproject.toml")
# the `pytest` requirement itself — never pytest-asyncio, pytest-cov or a comment
PYTEST_REQ = re.compile(r"""^\s*["']?pytest(?![\w-])""", re.M)
TIMEOUT_REQ = re.compile(r"""^\s*["']?pytest-timeout(?![\w-])""", re.M)
TYPES = sorted(t for t in SCAFFOLD_TYPES if t != "wordpress")

pytestmark = pytest.mark.skipif(
    not Path("/opt/fabrik").exists() or os.getenv("CI") == "true",
    reason="Requires the full fabrik environment (templates dir)",
)


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


def _ini_section(path: Path, section: str) -> dict[str, str] | None:
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return dict(parser[section]) if parser.has_section(section) else None


def _resolved_config(test_dir: Path, root: Path) -> tuple[Path, dict] | None:
    """The config file pytest would load for ``test_dir`` and its options, or None."""
    for d in [test_dir, *test_dir.parents]:
        for name in ("pytest.ini", ".pytest.ini"):
            if (d / name).is_file():
                return d / name, _ini_section(d / name, "pytest") or {}
        pp = d / "pyproject.toml"
        if pp.is_file():
            table = tomllib.loads(pp.read_text(encoding="utf-8")).get("tool", {}).get("pytest", {})
            if "ini_options" in table:
                return pp, table["ini_options"]
        for name, section in (("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
            if (d / name).is_file():
                opts = _ini_section(d / name, section)
                if opts is not None:
                    return d / name, opts
        if d == root:
            return None
    return None


# Trees vendored from fabrik-lib: their tests are the module's own and the hub never edits a vendored copy.
VENDORED = ("docs-site",)


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
        if p.name in DEP_FILES and p.is_file() and not _skip(p.relative_to(root))
    )


@pytest.mark.parametrize("kind", TYPES)
def test_every_test_directory_resolves_a_timeout(projects: dict[str, Path], kind: str) -> None:
    root = projects[kind]
    missing = []
    for test_dir in _test_dirs(root):
        resolved = _resolved_config(test_dir, root)
        rel = test_dir.relative_to(root).as_posix()
        if resolved is None:
            # a test dir with no config at all is a test dir nothing configures; it must still be bounded
            missing.append(f"{rel}: no pytest config resolves")
            continue
        path, opts = resolved
        for key in TIMEOUT_KEYS:
            if key not in opts:
                missing.append(f"{rel}: {path.relative_to(root).as_posix()} has no {key}")
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
        pytest.skip(f"{kind} emits no Python tests")
    assert any(TIMEOUT_REQ.search(p.read_text(encoding="utf-8")) for p in _dep_files(root)), [
        p.relative_to(root).as_posix() for p in _dep_files(root)
    ]


def test_file_worker_dev_file_carries_the_makefile_tools(projects: dict[str, Path]) -> None:
    """file-worker's Makefile installs requirements-dev.txt, then runs ruff and mypy from .venv."""
    dev = projects["file-worker"] / "requirements-dev.txt"
    assert dev.is_file()
    text = dev.read_text(encoding="utf-8")
    for tool in ("pytest", "pytest-timeout", "ruff", "mypy"):
        assert re.search(rf"^{re.escape(tool)}(?![\w-])", text, re.M), tool
