"""Tests for scripts/enforcement/check_undeclared_imports.py.

The gap this closes: check_deps_sync compares requirements.txt <-> pyproject.toml
(manifest vs manifest) and is blind to what the code actually imports. So a package
imported in code but absent from BOTH manifests sails through the gate, then a fresh
`pip install -r requirements.txt` (CI, or a fresh deploy) crashes on import. This is
exactly the pydantic-settings failure that broke trade-intelligence CI.

check_undeclared_imports scans the app source, maps each third-party import to its
installed distribution, and fails when that distribution is declared nowhere.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "enforcement"
    / "check_undeclared_imports.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("check_undeclared_imports", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_flags_import_missing_from_requirements(tmp_path: Path):
    # `import yaml` is provided by the INSTALLED distribution PyYAML (name mismatch
    # proves the packages_distributions mapping works), but requirements.txt is empty.
    _write(tmp_path, "requirements.txt", "# nothing declared\n")
    _write(tmp_path, "src/app/main.py", "import yaml\n\nx = yaml\n")
    undeclared = _load().find_undeclared_imports(tmp_path)
    dists = {d for _, d, _ in undeclared}
    assert "PyYAML" in dists, f"expected PyYAML flagged, got {undeclared}"


def test_passes_when_import_is_declared(tmp_path: Path):
    _write(tmp_path, "requirements.txt", "PyYAML>=6.0\n")
    _write(tmp_path, "src/app/main.py", "import yaml\n\nx = yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_passes_when_declared_only_in_pyproject(tmp_path: Path):
    # deploy uses requirements.txt, but declaring in pyproject shouldn't double-flag
    # here (check_deps_sync owns the manifest<->manifest drift).
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "pyproject.toml", '[project]\nname = "app"\ndependencies = ["PyYAML>=6.0"]\n')
    _write(tmp_path, "src/app/main.py", "import yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_skips_stdlib_imports(tmp_path: Path):
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/main.py", "import os\nimport sys\nimport json\nfrom pathlib import Path\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_skips_first_party_local_modules(tmp_path: Path):
    # importing a sibling package in the same repo must NOT be flagged as a missing dep
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/__init__.py", "")
    _write(tmp_path, "src/app/models.py", "")
    _write(tmp_path, "src/app/main.py", "from app import models\nimport app.models\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_skips_project_with_no_requirements_txt(tmp_path: Path):
    # non-requirements projects (pure pyproject, or non-python) are out of scope
    _write(tmp_path, "src/app/main.py", "import yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_ignores_tests_dir_dev_only_imports(tmp_path: Path):
    # test-only deps (pytest etc.) live in requirements-dev / CI, not the deploy
    # manifest — scanning tests/ would false-flag them. Deploy runs src/, not tests/.
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/main.py", "import os\n")
    _write(tmp_path, "tests/test_x.py", "import yaml\nimport pytest\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_main_exit_code(tmp_path: Path, capsys, monkeypatch):
    mod = _load()
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/main.py", "import yaml\n")
    monkeypatch.chdir(tmp_path)
    assert mod.main() == 1  # findings -> non-zero (fails the gate)
    out = capsys.readouterr().out
    assert "PyYAML" in out
    # now declare it -> exit 0
    _write(tmp_path, "requirements.txt", "PyYAML>=6\n")
    assert mod.main() == 0


def test_transitive_of_declared_is_not_flagged(tmp_path: Path):
    # pytest is installed and requires pluggy; importing pluggy while declaring only
    # pytest must NOT flag — a fresh `pip install pytest` pulls pluggy. This is the
    # starlette-via-fastapi case that must not red-gate the fleet.
    mod = _load()
    if "pluggy" not in mod._reachable_distributions({"pytest"}):
        pytest.skip("pytest->pluggy metadata not available in this env")
    _write(tmp_path, "requirements.txt", "pytest\n")
    _write(tmp_path, "src/app/main.py", "import pluggy\n")
    assert mod.find_undeclared_imports(tmp_path) == []


def test_reachable_includes_transitive_edges():
    mod = _load()
    reachable = mod._reachable_distributions({"pytest"})
    assert "pytest" in reachable
    assert "pluggy" in reachable  # a direct Requires-Dist of pytest


def test_vendored_editable_package_not_flagged(tmp_path: Path, monkeypatch):
    # youtube's real false-positive: libs/mt-router/mt_router is first-party but
    # editable-installed, so packages_distributions() maps it to a dist name. It must
    # be recognized as local because its file lives inside the repo — not flagged.
    mod = _load()
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "libs/vendored_pkg/__init__.py", "value = 1\n")
    _write(tmp_path, "src/app/main.py", "import vendored_pkg\n")
    monkeypatch.syspath_prepend(str(tmp_path / "libs"))
    monkeypatch.setattr(
        mod.importlib.metadata,
        "packages_distributions",
        lambda: {"vendored_pkg": ["vendored-pkg"]},
    )
    assert mod.find_undeclared_imports(tmp_path) == []


def test_fabrik_itself_is_clean():
    # The gate is fleet-synced; fabrik's own src/ must pass (baseline regression).
    root = Path(__file__).resolve().parent.parent
    if not (root / "requirements.txt").exists():
        pytest.skip("fabrik has no requirements.txt")
    undeclared = _load().find_undeclared_imports(root)
    assert undeclared == [], f"fabrik src/ has undeclared imports: {undeclared}"
