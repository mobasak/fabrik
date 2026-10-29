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


# ── W-c83c550c: a first-party editable package seen from a linked worktree ─────────────────────────────────────
# Builder worktrees share the main checkout's .venv (D-471), so an editable install resolves to ANOTHER tree of the
# same repository. These build real git worktrees: the rule is git's answer, so a stubbed resolver would prove
# nothing about it.
_GIT = [
    "git",
    "-c",
    "user.email=t@t",
    "-c",
    "user.name=t",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",  # a box-wide hook must not run inside the fixture repos
]


def _repo_with_worktrees(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A repo tracking libs/twin_pkg, plus two linked worktrees nested the way builders' are."""
    import subprocess

    main = tmp_path / "main"
    _write(main, "requirements.txt", "# empty\n")
    _write(main, "libs/twin_pkg/__init__.py", "value = 1\n")
    _write(main, "src/app/main.py", "import twin_pkg\n")
    subprocess.run([*_GIT, "init", "-q", str(main)], check=True)
    subprocess.run([*_GIT, "-C", str(main), "add", "-A"], check=True)
    subprocess.run([*_GIT, "-C", str(main), "commit", "-qm", "init"], check=True)
    trees = []
    for name in ("wt1", "wt2"):
        wt = main / ".claude" / "worktrees" / name
        subprocess.run(
            [*_GIT, "-C", str(main), "worktree", "add", "-q", "--detach", str(wt)], check=True
        )
        trees.append(wt)
    return main, trees[0], trees[1]


def _clear_caches(mod) -> None:
    for name in ("_work_tree_of", "_tracked_in"):
        clear = getattr(getattr(mod, name, None), "cache_clear", None)
        if clear is not None:
            clear()


@pytest.mark.parametrize("installed_from", ["main", "sibling"])
def test_editable_package_from_another_tree_of_the_repo_is_local(
    tmp_path: Path, monkeypatch, installed_from: str
):
    """youtube's yt1/yt2/yt3: `import mt_router` read as an undeclared dependency in every builder worktree
    because the shared venv's editable install points at the main checkout (or, after a builder re-installs,
    at a sibling worktree). The tree being checked tracks the same path, so it is first-party."""
    mod = _load()
    _clear_caches(mod)
    main, wt1, wt2 = _repo_with_worktrees(tmp_path)
    monkeypatch.syspath_prepend(str((main if installed_from == "main" else wt2) / "libs"))
    monkeypatch.setattr(
        mod.importlib.metadata, "packages_distributions", lambda: {"twin_pkg": ["twin-pkg"]}
    )
    assert mod._module_is_local("twin_pkg", wt1) is True
    assert mod.find_undeclared_imports(wt1) == []
    assert mod._module_is_local("twin_pkg", wt1 / "src") is True  # a root below the top level


def test_path_this_tree_does_not_track_stays_flagged(tmp_path: Path, monkeypatch):
    """A package only the other tree has (an untracked local install there) is not this branch's code."""
    mod = _load()
    _clear_caches(mod)
    main, wt1, _ = _repo_with_worktrees(tmp_path)
    _write(main, "extras/only_main/__init__.py", "value = 1\n")
    monkeypatch.syspath_prepend(str(main / "extras"))
    assert mod._module_is_local("only_main", wt1) is False


def test_twin_of_the_other_kind_stays_flagged(tmp_path: Path, monkeypatch):
    """The other tree's package directory is matched only by a tracked DIRECTORY here, never by a tracked file
    at the same path."""
    import subprocess

    mod = _load()
    _clear_caches(mod)
    main, wt1, _ = _repo_with_worktrees(tmp_path)
    _write(wt1, "extras/odd_pkg", "a file, not a package\n")
    subprocess.run([*_GIT, "-C", str(wt1), "add", "extras/odd_pkg"], check=True)
    _write(main, "extras/odd_pkg/__init__.py", "value = 1\n")
    monkeypatch.syspath_prepend(str(main / "extras"))
    assert mod._module_is_local("odd_pkg", wt1) is False


def test_twin_test_failure_keeps_the_package_flagged(tmp_path: Path, monkeypatch):
    """An error inside the twin test answers "not local" — it must never escape to main(), whose blanket except
    prints "internal error (skipping)" and exits 0, a silent pass for every import."""
    mod = _load()
    _clear_caches(mod)
    main, wt1, _ = _repo_with_worktrees(tmp_path)
    monkeypatch.syspath_prepend(str(main / "libs"))

    def boom(*a, **k):
        raise RuntimeError("git exploded")

    monkeypatch.setattr(mod, "_tracked_in", boom)
    assert mod._module_is_local("twin_pkg", wt1) is False


def test_twin_test_runs_git_once_per_directory(tmp_path: Path, monkeypatch):
    import subprocess

    mod = _load()
    _clear_caches(mod)
    main, wt1, _ = _repo_with_worktrees(tmp_path)
    monkeypatch.syspath_prepend(str(main / "libs"))
    calls: list[list[str]] = []
    real = subprocess.run

    def counting(cmd, *a, **k):
        calls.append(list(cmd))
        return real(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", counting)
    for _ in range(3):
        assert mod._module_is_local("twin_pkg", wt1) is True
    rev_parse = [c for c in calls if "rev-parse" in c]
    ls_files = [c for c in calls if "ls-files" in c]
    assert len(rev_parse) == 2 and len(ls_files) == 1, (
        calls
    )  # their directory, my root; my tree's file list


def test_a_separate_clone_tracking_the_same_path_stays_flagged(tmp_path: Path, monkeypatch):
    """Only a working tree of the SAME repository (one git common dir) is a twin: an unrelated clone that happens to
    track libs/twin_pkg is someone else's code."""
    import subprocess

    mod = _load()
    _clear_caches(mod)
    _, wt1, _ = _repo_with_worktrees(tmp_path)
    other = tmp_path / "other"
    _write(other, "libs/twin_pkg/__init__.py", "value = 2\n")
    subprocess.run([*_GIT, "init", "-q", str(other)], check=True)
    subprocess.run([*_GIT, "-C", str(other), "add", "-A"], check=True)
    subprocess.run([*_GIT, "-C", str(other), "commit", "-qm", "init"], check=True)
    monkeypatch.syspath_prepend(str(other / "libs"))
    assert mod._module_is_local("twin_pkg", wt1) is False


def test_a_package_of_the_same_tree_outside_the_root_stays_flagged(tmp_path: Path, monkeypatch):
    """The twin rule is for ANOTHER tree: a root below the top does not adopt its own tree's other directories."""
    mod = _load()
    _clear_caches(mod)
    _, wt1, _ = _repo_with_worktrees(tmp_path)
    monkeypatch.syspath_prepend(str(wt1 / "libs"))
    assert mod._module_is_local("twin_pkg", wt1 / "src") is False


def test_a_namespace_package_twin_is_local_but_another_trees_top_is_not(
    tmp_path: Path, monkeypatch
):
    """A namespace package (a directory with no __init__.py) is matched by a tracked directory here; the other tree's
    TOP is never a twin, even with the repo's parent on sys.path."""
    import subprocess

    mod = _load()
    _clear_caches(mod)
    main, wt1, _ = _repo_with_worktrees(tmp_path)
    for tree in (main, wt1):
        _write(tree, "libs/ns_pkg/mod.py", "value = 1\n")
    subprocess.run([*_GIT, "-C", str(wt1), "add", "libs/ns_pkg/mod.py"], check=True)
    monkeypatch.syspath_prepend(str(main / "libs"))
    assert mod._module_is_local("ns_pkg", wt1) is True
    monkeypatch.syspath_prepend(
        str(tmp_path)
    )  # `main` now resolves as a namespace package: the other tree's top
    assert mod._module_is_local("main", wt1) is False
