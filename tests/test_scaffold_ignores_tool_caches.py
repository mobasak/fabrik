"""A scaffold never copies a source tree's tool caches into a new project.

The trees the scaffolder copies from (fabrik-lib's docs-site, the hub's scripts/enforcement, the
templates) are working directories on this box, so they collect __pycache__, .mypy_cache,
.pytest_cache, .ruff_cache and stray .pyc files. docs-site's __pycache__ is not gitignored in a
project, so its .pyc files landed in a new saas-skeleton project's first commit.
"""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

import pytest

import fabrik.scaffold as scaffold

CACHE_DIRS = ("__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache")
CACHE_NAMES = [*CACHE_DIRS, "stray.pyc"]


def _plant_caches(root: Path) -> None:
    for d in (root, *[p for p in root.rglob("*") if p.is_dir()]):
        for cache in CACHE_DIRS:
            (d / cache).mkdir()
            (d / cache / "junk").write_text("x")
        (d / "stray.pyc").write_bytes(b"\0")


def _leaked(tree: Path) -> list[str]:
    return sorted(
        str(p.relative_to(tree))
        for p in tree.rglob("*")
        if p.name in CACHE_DIRS or p.suffix == ".pyc"
    )


def test_vendored_docs_site_carries_no_tool_cache(tmp_path, monkeypatch):
    src = tmp_path / "lib" / "docs-site"
    (src / "scripts").mkdir(parents=True)
    (src / "package.json").write_text('{"name": "docs-site"}\n')
    (src / "scripts" / "translate.py").write_text("x = 1\n")
    _plant_caches(src)
    monkeypatch.setattr(scaffold, "FABRIK_LIB_DIR", tmp_path / "lib")
    project = tmp_path / "proj"
    project.mkdir()

    scaffold._vendor_docs_site(project, "proj")

    assert (project / "docs-site" / "scripts" / "translate.py").exists()
    assert _leaked(project / "docs-site") == []


def test_the_saas_template_copy_loop_carries_no_tool_cache(tmp_path, monkeypatch):
    """saas-skeleton is copied by a hand-written rglob loop, not copytree."""
    template = tmp_path / "saas-skeleton"
    (template / "app").mkdir(parents=True)
    (template / "app" / "page.tsx").write_text("export default 1\n")
    _plant_caches(template)
    monkeypatch.setattr(scaffold, "SAAS_SKELETON_DIR", template)
    project = tmp_path / "proj"
    project.mkdir()

    scaffold._scaffold_saas_skeleton(project, "proj", "d")

    assert (project / "app" / "page.tsx").exists()
    assert _leaked(project) == []


@pytest.mark.parametrize("project_type", ["saas-skeleton", "static-site"])
def test_the_i18n_kit_loops_carry_no_stray_pyc(tmp_path, monkeypatch, project_type):
    """The react and snippets loops copy every top-level file of their kit folder."""
    kit = tmp_path / "i18n-kit"
    shutil.copytree(scaffold.I18N_KIT_DIR, kit, ignore=shutil.ignore_patterns(*CACHE_DIRS))
    for folder in ("react", "snippets"):
        (kit / folder / "stray.pyc").write_bytes(b"\0")
    monkeypatch.setattr(scaffold, "I18N_KIT_DIR", kit)
    project = tmp_path / "proj"
    (project / "app").mkdir(parents=True)
    # the react strategy also mounts the provider in the root layout it finds there
    shutil.copy2(scaffold.SAAS_SKELETON_DIR / "app" / "layout.tsx", project / "app" / "layout.tsx")

    scaffold._provision_i18n(project, project_type)

    assert any(project.rglob("*")), "the kit provisioned nothing — the check would be vacuous"
    assert _leaked(project) == []


def test_the_mobile_app_template_loop_carries_no_tool_cache(tmp_path, monkeypatch):
    """mobile-app copies its template's top-level entries one by one."""
    template = tmp_path / "mobile-app"
    shutil.copytree(
        scaffold.MOBILE_APP_TEMPLATE_DIR,
        template,
        ignore=shutil.ignore_patterns(*CACHE_DIRS, "*.pyc", "node_modules"),
    )
    for cache in CACHE_DIRS:
        (template / cache).mkdir()
        (template / cache / "junk").write_text("x")
    (template / "stray.pyc").write_bytes(b"\0")
    monkeypatch.setattr(scaffold, "MOBILE_APP_TEMPLATE_DIR", template)
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")

    scaffold.create_project(
        name="mob", description="d", base=tmp_path, project_type="mobile-app", generate_spec=False
    )

    assert (tmp_path / "mob" / "app.config.ts").exists()
    assert _leaked(tmp_path / "mob") == []


@pytest.mark.parametrize("name", CACHE_NAMES)
def test_the_loop_predicate_names_every_cache(name):
    assert scaffold._is_tool_cache(("a", name, "b"))
    assert not scaffold._is_tool_cache(("a", "cache.py", "b"))


def test_every_copytree_a_scaffold_runs_ignores_the_tool_caches(tmp_path, monkeypatch):
    """Run every scaffold type and ask each copytree's REAL ignore callable about the caches."""
    calls = []
    real = shutil.copytree

    def recording(src, dst, *args, **kwargs):
        # shutil's own recursion re-enters through the patched name; only the scaffolder's
        # call sites are the subject
        if sys._getframe(1).f_globals.get("__name__") == scaffold.__name__:
            calls.append((str(src), kwargs.get("ignore")))
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(scaffold.shutil, "copytree", recording)
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    types = sorted(scaffold.SCAFFOLD_TYPES - {"wordpress"})
    for i, project_type in enumerate(types):
        scaffold.create_project(
            name=f"p{i}",
            description="d",
            base=tmp_path,
            project_type=project_type,
            generate_spec=False,
        )

    assert len(calls) >= len(types), calls
    bad = [
        src
        for src, ignore in calls
        if ignore is None or not set(CACHE_NAMES) <= set(ignore(src, CACHE_NAMES))
    ]
    assert bad == []


def test_the_scaffolder_binds_no_bare_copytree():
    """The recording test above wraps shutil.copytree; a `from shutil import copytree` would
    slip past it."""
    tree = ast.parse(Path(scaffold.__file__).read_text())
    bare = [
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        and n.module == "shutil"
        and any(a.name in ("copytree", "*") for a in n.names)
    ]
    assert bare == []


def test_every_copytree_in_the_scaffolder_ignores_the_tool_caches_by_structure():
    """The recorder above sees only the copies create_project runs; fix_project's copies run
    elsewhere. Every call must pass exactly shutil.ignore_patterns(*_TOOL_CACHES, ...)."""
    tree = ast.parse(Path(scaffold.__file__).read_text())
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "shutil.copytree"
    ]

    def ignores_the_caches(call: ast.Call) -> bool:
        ignore = next((k.value for k in call.keywords if k.arg == "ignore"), None)
        return (
            isinstance(ignore, ast.Call)
            and ast.unparse(ignore.func) == "shutil.ignore_patterns"
            and bool(ignore.args)
            and isinstance(ignore.args[0], ast.Starred)
            and ast.unparse(ignore.args[0].value) == "_TOOL_CACHES"
        )

    assert len(calls) >= 16, len(calls)
    assert [c.lineno for c in calls if not ignores_the_caches(c)] == []


def test_the_hubs_local_claude_settings_never_reach_a_project(tmp_path, monkeypatch):
    """_scaffold_shared copies the hub's .claude/ for its hooks; the hub's untracked
    settings.local.json (its own permission approvals) must stay behind."""
    calls = []
    real = shutil.copytree

    def recording(src, dst, *args, **kwargs):
        if sys._getframe(1).f_globals.get("__name__") == scaffold.__name__:
            calls.append((Path(src), kwargs.get("ignore")))
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(scaffold.shutil, "copytree", recording)
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    scaffold.create_project(
        name="loc", description="d", base=tmp_path, project_type="python-api", generate_spec=False
    )

    [(src, ignore)] = [(s, i) for s, i in calls if s.name == ".claude"]
    assert "settings.local.json" in ignore(str(src), ["settings.local.json", "settings.json"])
    assert "settings.json" not in ignore(str(src), ["settings.local.json", "settings.json"])
