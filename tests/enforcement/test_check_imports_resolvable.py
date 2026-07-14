"""Behavior contract for scripts/enforcement/check_imports_resolvable.py.

The check exists because `final_gate` ran in the developer's `.venv`, where a gitignored module is physically
present — so it went green while CI and the deployed container hit `ModuleNotFoundError`. Every test below
builds a REAL throwaway git repo, because git tracked-ness IS the thing under test: "what will CI actually
check out?" cannot be faked with mocks.
"""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_imports_resolvable.py"


def _run_check(root: Path) -> tuple[int, str]:
    """Load the check with ROOT bound to `root` and run it, capturing stdout."""
    spec = importlib.util.spec_from_file_location("chk_mod", CHECK)
    assert spec and spec.loader
    chk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chk)
    chk.ROOT = root
    cwd, saved_path, saved_argv = Path.cwd(), list(sys.path), list(sys.argv)
    # ⚠️ Purge cached first-party packages. `find_spec("libs.subagents")` consults the ALREADY-IMPORTED
    # parent's __path__, so a `libs` left in sys.modules by a previous test resolves against THAT repo and the
    # check silently sees nothing. In production this cannot bite (the gate runs as a fresh subprocess), but
    # in-process tests must isolate or they quietly assert on the wrong repo.
    for name in [n for n in sys.modules if n.split(".")[0] in {"libs", "pkg", "src"}]:
        del sys.modules[name]
    importlib.invalidate_caches()
    os.chdir(root)
    sys.argv = ["chk"]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = chk.main()
    finally:
        os.chdir(cwd)
        sys.path[:] = saved_path
        sys.argv = saved_argv
    return rc, buf.getvalue()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo with a src/ package."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    return tmp_path


def _commit(repo: Path, *paths: str) -> None:
    subprocess.run(["git", "add", *paths], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True)


def test_gitignored_absolute_import_is_an_error(repo: Path) -> None:
    """THE motivating bug: src/ imports a gitignored synced dir (libs/subagents)."""
    (repo / ".gitignore").write_text("libs/subagents/\n")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "web_tools.py").write_text("def execute_web_tool(): ...\n")
    (repo / "src" / "pkg" / "app.py").write_text("from libs.subagents.web_tools import execute_web_tool\n")
    _commit(repo, ".gitignore", "libs/__init__.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 1
    assert "libs.subagents.web_tools" in out
    assert "PHANTOM DEPENDENCY" in out


def test_vendored_but_uncommitted_relative_import_is_an_error(repo: Path) -> None:
    """The half-done vendor: the fix the check *recommends*, applied but never `git add`ed.

    A relative import to an untracked sibling breaks a clean checkout identically — and an earlier version of
    this check skipped relative imports entirely, so it would have blessed this.
    """
    (repo / "src" / "pkg" / "vendored.py").write_text("def helper(): ...\n")  # deliberately NOT added
    (repo / "src" / "pkg" / "app.py").write_text("from .vendored import helper\n")
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 1
    assert "vendored.py" in out
    assert "NOT IN THE REPOSITORY" in out


def test_properly_vendored_and_committed_passes(repo: Path) -> None:
    """The correct end state: vendored INTO tracked source. This is what we tell people to do."""
    (repo / "src" / "pkg" / "vendored.py").write_text("def helper(): ...\n")
    (repo / "src" / "pkg" / "app.py").write_text("from .vendored import helper\n")
    _commit(repo, "src/pkg/vendored.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 0, out


def test_guarded_import_is_exempt(repo: Path) -> None:
    """A try/except-ImportError import is a deliberate optional dep — the pattern CLAUDE.md prescribes for
    the subagent pool. It degrades gracefully, so it must NOT fail the gate."""
    (repo / ".gitignore").write_text("libs/subagents/\n")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "__init__.py").write_text("fanout = None\n")
    (repo / "src" / "pkg" / "app.py").write_text(
        "try:\n    from libs.subagents import fanout\nexcept ImportError:\n    fanout = None\n"
    )
    _commit(repo, ".gitignore", "libs/__init__.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 0, out


def test_stdlib_and_installed_deps_are_not_phantoms(repo: Path) -> None:
    """The cry-wolf guard. `.venv/` is itself gitignored, so a naive tracked-ness test flags every pip dep;
    and frozen stdlib modules report a pseudo-origin ('frozen') that is not a real path. Either bug makes the
    gate flag `import os` and get noqa'd into uselessness."""
    (repo / "src" / "pkg" / "app.py").write_text("import os\nimport sys\nimport json\nimport pytest\n")
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 0, out


def test_phantom_in_scripts_is_warn_not_error(repo: Path) -> None:
    """scripts/ is dev tooling, never deployed — a papercut, not an outage. It must not block the gate."""
    (repo / ".gitignore").write_text("libs/subagents/\n")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "__init__.py").write_text("")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool.py").write_text("from libs.subagents import fanout\n")
    _commit(repo, ".gitignore", "libs/__init__.py", "scripts/tool.py")

    rc, out = _run_check(repo)
    assert rc == 0, out
    assert "WARN" in out
