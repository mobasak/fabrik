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
    dists = {d for _, d, _, _ in undeclared}
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
    _write(
        tmp_path,
        "src/app/main.py",
        "import os\nimport sys\nimport json\nfrom pathlib import Path\n",
    )
    assert _load().find_undeclared_imports(tmp_path) == []


def test_skips_first_party_local_modules(tmp_path: Path):
    # importing a sibling package in the same repo must NOT be flagged as a missing dep
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/__init__.py", "")
    _write(tmp_path, "src/app/models.py", "")
    _write(tmp_path, "src/app/main.py", "from app import models\nimport app.models\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_optional_import_guarded_by_try_except_not_flagged(tmp_path: Path):
    # `try: import X except ImportError` is OPTIONAL — the app handles its absence, so
    # a fresh install missing it does not crash. Flagging it is a false positive.
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(
        tmp_path,
        "src/app/main.py",
        "try:\n    import yaml\nexcept ImportError:  # pragma: no cover\n    yaml = None\n",
    )
    assert _load().find_undeclared_imports(tmp_path) == []


def test_required_import_still_flagged_when_try_catches_other_error(tmp_path: Path):
    # a try that catches a NON-import error does not make the import optional
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/main.py", "try:\n    import yaml\nexcept ValueError:\n    pass\n")
    dists = {d for _, d, _, _ in _load().find_undeclared_imports(tmp_path)}
    assert "PyYAML" in dists


def test_fallback_import_in_handler_still_flagged(tmp_path: Path):
    # the fallback that runs when the primary import fails IS required on that path
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(
        tmp_path,
        "src/app/main.py",
        "try:\n    import cjson\nexcept ImportError:\n    import yaml  # fallback\n",
    )
    dists = {d for _, d, _, _ in _load().find_undeclared_imports(tmp_path)}
    assert "PyYAML" in dists  # the fallback (yaml) is flagged; cjson (optional) is not


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


def test_follows_r_includes_in_requirements(tmp_path: Path):
    # deps declared via `-r base.txt` must count as declared (finding B regression)
    _write(tmp_path, "requirements.txt", "-r base.txt\n")
    _write(tmp_path, "base.txt", "PyYAML>=6\n")
    _write(tmp_path, "src/app/main.py", "import yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_r_include_cycle_does_not_hang(tmp_path: Path):
    _write(tmp_path, "requirements.txt", "-r a.txt\n")
    _write(tmp_path, "a.txt", "-r requirements.txt\nPyYAML>=6\n")  # cycle back
    _write(tmp_path, "src/app/main.py", "import yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []  # terminates + PyYAML found


def test_multi_provider_module_not_flagged_when_one_declared(tmp_path: Path, monkeypatch):
    # a module provided by multiple dists is satisfied if ANY provider is declared
    # (finding F regression)
    mod = _load()
    _write(tmp_path, "requirements.txt", "declared-dist>=1\n")
    _write(tmp_path, "src/app/main.py", "import shared_ns\n")
    monkeypatch.setattr(
        mod.importlib.metadata,
        "packages_distributions",
        lambda: {"shared_ns": ["other-dist", "declared-dist"]},
    )
    monkeypatch.setattr(mod, "_module_is_local", lambda m, root: False)
    # 'declared-dist' has no installed metadata -> requires() skips; it's still in the
    # declared set, so shared_ns is satisfied.
    assert mod.find_undeclared_imports(tmp_path) == []


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


def test_pyproject_only_dep_flagged_when_dockerfile_installs_requirements(tmp_path: Path):
    """The curl_cffi/trade-intelligence class: declared in pyproject.toml only, while
    the Dockerfile installs -r requirements.txt -> the container never gets it."""
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "app"\ndependencies = ["PyYAML>=6.0"]\n',
    )
    _write(
        tmp_path,
        "Dockerfile",
        "FROM python:3.12\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n",
    )
    _write(tmp_path, "src/app/main.py", "import yaml\n\nx = yaml\n")
    found = _load().find_undeclared_imports(tmp_path)
    assert any(d == "PyYAML" and reason == "pyproject-only" for _, d, _, reason in found), found


def test_pyproject_only_dep_ok_without_requirements_dockerfile(tmp_path: Path):
    """No Dockerfile installing requirements.txt -> the manifest union stays authoritative."""
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "app"\ndependencies = ["PyYAML>=6.0"]\n',
    )
    _write(tmp_path, "src/app/main.py", "import yaml\n\nx = yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []


def test_shipped_scripts_scanned_when_dockerfile_copies_them(tmp_path: Path):
    """`COPY . .` ships scripts/ -> a module-level undeclared import there is a
    container crash and must be flagged; without a shipping Dockerfile scripts/ stays
    excluded as dev tooling."""
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "src/app/main.py", "x = 1\n")
    _write(tmp_path, "scripts/refresh.py", "import yaml\n\nx = yaml\n")
    # no Dockerfile -> dev tooling, not scanned
    assert _load().find_undeclared_imports(tmp_path) == []
    _write(
        tmp_path, "Dockerfile", "FROM python:3.12\nRUN pip install -r requirements.txt\nCOPY . .\n"
    )
    found = _load().find_undeclared_imports(tmp_path)
    assert any(d == "PyYAML" and "scripts" in example for _, d, example, _ in found), found


def test_module_is_local_never_claims_site_packages(tmp_path: Path):
    """Regression (curl_cffi incident): the project .venv lives INSIDE the repo, so an
    installed dep's origin is under the root — it must still not count as first-party.
    Uses the live env: yaml resolves from THIS venv's site-packages; pick the venv's
    ancestor as project_root so the old code would have said True."""
    import yaml  # noqa: F401  (guaranteed installed — the check itself maps it)

    mod = _load()
    venv_ancestor = Path(yaml.__file__).resolve()
    while venv_ancestor.name not in (".venv", "venv") and venv_ancestor != venv_ancestor.parent:
        venv_ancestor = venv_ancestor.parent
    project_root = venv_ancestor.parent  # repo root containing the venv
    assert mod._module_is_local("yaml", project_root) is False


def test_untracked_file_not_scanned_in_git_repo(tmp_path: Path):
    """A gitignored/untracked file on disk (a Fabrik-synced script) never reaches a
    clean checkout or the container -> its imports must not fire the check."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(
        tmp_path, "Dockerfile", "FROM python:3.12\nRUN pip install -r requirements.txt\nCOPY . .\n"
    )
    _write(tmp_path, "src/app/main.py", "x = 1\n")
    _write(tmp_path, "scripts/kilo_code_review.py", "import yaml\n\nx = yaml\n")  # NOT git-added
    subprocess.run(
        ["git", "add", "requirements.txt", "Dockerfile", "src/app/main.py"],
        cwd=tmp_path,
        check=True,
    )
    assert _load().find_undeclared_imports(tmp_path) == []
    # the same file TRACKED -> flagged
    subprocess.run(["git", "add", "scripts/kilo_code_review.py"], cwd=tmp_path, check=True)
    found = _load().find_undeclared_imports(tmp_path)
    assert any(d == "PyYAML" for _, d, _, _ in found), found


def test_dockerfile_regexes_review_matrix(tmp_path: Path):
    """Review findings 3/4/7: line-continuations, pip install . detection, exact-manifest token."""
    m = _load()
    # finding 3: backslash line-continuation must still activate the class
    assert m._dockerfile_installs_requirements(
        "RUN pip install --no-cache-dir \\\n    -r requirements.txt\n"
    )
    # finding 7: a DIFFERENT manifest file must NOT activate requirements-only reasoning
    assert not m._dockerfile_installs_requirements("RUN pip install -r prod-requirements.txt\n")
    assert m._dockerfile_installs_requirements("RUN pip install -r ./requirements.txt\n")
    # finding 4: `pip install .` variants pull pyproject deps into the image
    for line in (
        "RUN pip install .\n",
        "RUN pip install -e .\n",
        'RUN pip install ".[dev,test]"\n',
        "RUN pip install .[all]\n",
        "RUN pip install --no-cache-dir -r requirements.txt && pip install .\n",
    ):
        assert m._dockerfile_installs_pyproject(line), line
    for line in ("RUN pip install -r requirements.txt\n", "RUN pip install foo==1.2\n"):
        assert not m._dockerfile_installs_pyproject(line), line


def test_pyproject_only_not_flagged_when_image_also_installs_pyproject(tmp_path: Path):
    """Review finding 4 end-to-end: `pip install .` in the image -> pyproject deps DO ship."""
    _write(tmp_path, "requirements.txt", "# empty\n")
    _write(tmp_path, "pyproject.toml", '[project]\nname = "app"\ndependencies = ["PyYAML>=6.0"]\n')
    _write(
        tmp_path,
        "Dockerfile",
        "FROM python:3.12\nRUN pip install -r requirements.txt\nRUN pip install .\n",
    )
    _write(tmp_path, "src/app/main.py", "import yaml\n\nx = yaml\n")
    assert _load().find_undeclared_imports(tmp_path) == []
