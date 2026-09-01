"""Behavior contract for scripts/enforcement/check_imports_resolvable.py.

The check exists because `final_gate` ran in the developer's `.venv`, where a gitignored module is physically
present — so it went green while CI and the deployed container hit `ModuleNotFoundError`. Every test below
builds a REAL throwaway git repo, because git tracked-ness IS the thing under test: "what will CI actually
check out?" cannot be faked with mocks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CHECK = (
    Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_imports_resolvable.py"
)


def _run_check(root: Path, extra_syspath: list[str] | None = None) -> tuple[int, str]:
    """Run the check EXACTLY as production does: a fresh subprocess, rooted in the project.

    ⚠️ This used to run in-process with `chk.ROOT` monkeypatched and a hardcoded `sys.modules` purge of
    `{"libs","pkg","src"}`. That is a test-quality defect: production invokes it via
    `final_gate.run_optional_check` → `run_cmd` → `subprocess.run([PYTHON, script])`. An in-process
    harness proves something the shipped code never does — and the purge set was a crutch that would
    silently leak state for any fixture using a different top-level package name, resolving against the
    WRONG repo. Copy the check into the throwaway repo and shell out; ROOT then derives from `__file__`
    exactly as it does in the field.
    """
    dest = root / "scripts" / "enforcement"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CHECK, dest / CHECK.name)

    env = dict(os.environ)
    if extra_syspath:
        env["PYTHONPATH"] = os.pathsep.join([*extra_syspath, env.get("PYTHONPATH", "")]).rstrip(
            os.pathsep
        )
    proc = subprocess.run(
        [sys.executable, str(dest / CHECK.name)],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


@pytest.fixture
def outside(tmp_path_factory) -> Path:
    """A directory GENUINELY OUTSIDE the repo under test.

    ⚠️ Do NOT build this from `tmp_path`: the `repo` fixture RETURNS `tmp_path`, so a test taking both
    gets the SAME directory — `external` would land INSIDE the repo and the assertion would be satisfied
    by the `_is_tracked` branch, never by the outside-the-repo logic it claims to cover. That is a test
    that cannot fail when its fix is reverted (proven: reverting `_is_phantom`'s outside-repo branch
    still passed). A separate factory dir is what makes the test real.
    """
    return tmp_path_factory.mktemp("outside")


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
    (repo / "src" / "pkg" / "app.py").write_text(
        "from libs.subagents.web_tools import execute_web_tool\n"
    )
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
    (repo / "src" / "pkg" / "vendored.py").write_text(
        "def helper(): ...\n"
    )  # deliberately NOT added
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


def test_phantom_inside_a_plain_if_block_is_caught(repo: Path) -> None:
    """REGRESSION — a plain top-level `if:` is NOT a guard.

    The original check walked only `tree.body`, so ANY import nested in an `if` / `with` / `for`
    block was skipped as "guarded". But only `try/except ImportError` actually handles absence — a
    plain `if` executes at import time and hard-fails. This exact shape passed the gate (exit 0) and
    would ModuleNotFoundError in the container: a silent recall hole in a SHOWSTOPPER check.
    """
    (repo / ".gitignore").write_text("libs/subagents/\n")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "__init__.py").write_text("fanout = None\n")
    (repo / "src" / "pkg" / "app.py").write_text(
        'import os\nif os.getenv("FEATURE"):\n    from libs.subagents import fanout\n'
    )
    _commit(repo, ".gitignore", "libs/__init__.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 1, f"a plain `if:` import is NOT guarded and must be caught:\n{out}"
    assert "libs.subagents" in out


def test_type_checking_import_is_exempt(repo: Path) -> None:
    """`if TYPE_CHECKING:` never executes at runtime — flagging it would cry wolf."""
    (repo / ".gitignore").write_text("libs/subagents/\n")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "__init__.py").write_text("")
    (repo / "src" / "pkg" / "app.py").write_text(
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from libs.subagents import fanout\n"
    )
    _commit(repo, ".gitignore", "libs/__init__.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 0, f"TYPE_CHECKING imports are annotations-only and must NOT be flagged:\n{out}"


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
    (repo / "src" / "pkg" / "app.py").write_text(
        "import os\nimport sys\nimport json\nimport pytest\n"
    )
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 0, out


def test_a_raising_parent_package_does_not_crash_the_gate(repo: Path) -> None:
    """REGRESSION — `find_spec` IMPORTS parent packages, executing arbitrary code at gate time.

    A package whose `__init__.py` raises (config validation, a bare `raise`, `sys.exit()`) propagated
    a RuntimeError straight out of the check and CRASHED it. This is a SYNCED Tier-1 gate: a crash
    blocks `final_gate` in every project that merely *has* such a package. It must swallow and skip.
    """
    (repo / "badpkg").mkdir()
    (repo / "badpkg" / "__init__.py").write_text('raise RuntimeError("import-time explosion")\n')
    (repo / "src" / "pkg" / "app.py").write_text("from badpkg.sub import thing\n")
    _commit(repo, "badpkg/__init__.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)  # must not raise
    assert "Traceback" not in out
    assert rc in (0, 1), f"gate must survive a raising parent package, got rc={rc}:\n{out}"


def test_compiled_extension_is_not_a_phantom(repo: Path) -> None:
    """A `.so` is a BUILD ARTIFACT, not source. Cython/cffi modules are routinely gitignored and
    produced by the build — absent from the repo yet PRESENT in the container. Flagging one as
    'will ModuleNotFoundError in the container' is exactly backwards and hard-ERRORs a valid project.
    """
    (repo / ".gitignore").write_text("*.so\n")
    (repo / "src" / "_ext.so").write_bytes(b"\x7fELF")  # gitignored build artifact
    (repo / "src" / "pkg" / "app.py").write_text("import _ext\n")
    _commit(repo, ".gitignore", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo)
    assert rc == 0, f"a compiled build artifact must NOT be a phantom:\n{out}"


def test_phantom_outside_the_repo_root_is_caught(repo: Path, outside: Path, monkeypatch) -> None:
    """REGRESSION — the check used to BLESS every module outside the repo (`except ValueError: return
    False`), which silently exempted the very bug class it exists to catch: put `libs/` on PYTHONPATH,
    or `pip install -e /opt/fabrik-lib`, or symlink it, and the import resolves here but NOT in CI.

    What CI actually receives is: the repo + pip-installed packages + the interpreter. A path outside
    ALL THREE exists only on this developer's machine.
    """
    external = outside / "external"
    (external / "extlib").mkdir(parents=True)
    (external / "extlib" / "__init__.py").write_text("def go(): ...\n")

    (repo / "src" / "pkg" / "app.py").write_text("from extlib import go\n")
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    monkeypatch.setenv("PYTHONPATH", str(external))
    rc, out = _run_check(repo, extra_syspath=[str(external)])
    assert rc == 1, f"a module CI will not have must be a phantom:\n{out}"
    assert "extlib" in out


def test_escape_hatch_exempts_generated_code(repo: Path, outside: Path, monkeypatch) -> None:
    """Without an escape hatch, a module gitignored BY DESIGN and regenerated in the Dockerfile
    (protobuf `*_pb2.py`, an OpenAPI client) is an UNFIXABLE hard ERROR — which is exactly how a gate
    gets disabled fleet-wide. `# phantom-ok` keeps the gate trustworthy instead of discarded."""
    external = outside / "external"
    (external / "extlib").mkdir(parents=True)
    (external / "extlib" / "__init__.py").write_text("def go(): ...\n")

    (repo / "src" / "pkg" / "app.py").write_text(
        "from extlib import go   # phantom-ok: generated in the Dockerfile\n"
    )
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    monkeypatch.setenv("PYTHONPATH", str(external))
    rc, out = _run_check(repo, extra_syspath=[str(external)])
    assert rc == 0, f"an explicitly-exempted import must not fail the gate:\n{out}"


def test_escape_hatch_works_on_a_multiline_import(repo: Path, outside: Path, monkeypatch) -> None:
    """REGRESSION — the hatch checked only `node.lineno` (the `from` line), so a marker on the closing
    paren of a parenthesised import was MISSED: the gate still errored while the author believed they
    had opted out. A safety valve that silently fails to open is worse than none — it teaches people
    the gate is broken, and that is how a gate gets deleted."""
    external = outside / "external"
    (external / "extlib").mkdir(parents=True)
    (external / "extlib" / "__init__.py").write_text("a = 1\nb = 2\n")

    (repo / "src" / "pkg" / "app.py").write_text(
        "from extlib import (\n    a,\n    b,\n)  # phantom-ok: generated in the Dockerfile\n"
    )
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    monkeypatch.setenv("PYTHONPATH", str(external))
    rc, out = _run_check(repo, extra_syspath=[str(external)])
    assert rc == 0, f"the marker anywhere in the import's span must exempt it:\n{out}"


def test_self_editable_install_is_not_a_phantom(repo: Path) -> None:
    """`pip install -e .` puts the project's OWN source on sys.path via a .pth. Reproducible in CI, and
    the code is in the repo anyway — never a phantom."""
    site = repo / ".venv" / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    (site / "__editable__.myproj.pth").write_text(f"{repo / 'src'}\n")

    (repo / "src" / "pkg" / "lib.py").write_text("def go(): ...\n")
    (repo / "src" / "pkg" / "app.py").write_text("from pkg.lib import go\n")
    _commit(repo, "src/pkg/lib.py", "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo, extra_syspath=[str(repo / "src"), str(site)])
    assert rc == 0, f"a self-editable install is not a phantom:\n{out}"


def test_editable_install_of_an_outside_tree_is_still_a_phantom(
    repo: Path, outside: Path, monkeypatch
) -> None:
    """REGRESSION — the fix for the editable false-positive must NOT swallow the real bug.

    `pip install -e /opt/fabrik` puts SOMEONE ELSE'S source tree on sys.path. That path does not exist in
    CI or the container, and it is only reproducible if the distribution is DECLARED in requirements —
    which this check deliberately does not verify. Blessing every editable root wholesale re-opened the
    exact hole the gate exists to close: it is precisely how `wpf`'s test imports `fabrik` (absent from
    its requirements) while its CI fails to collect the suite. Verified live: blessing them dropped wpf's
    true positive to zero.
    """
    src = outside / "other_tree"
    (src / "otherlib").mkdir(parents=True)
    (src / "otherlib" / "__init__.py").write_text("def go(): ...\n")

    site = outside / "venv" / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    (site / "__editable__.otherlib.pth").write_text(f"{src}\n")

    (repo / "src" / "pkg" / "app.py").write_text("from otherlib import go\n")
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    rc, out = _run_check(repo, extra_syspath=[str(src), str(site)])
    assert rc == 1, f"an editable install of an OUTSIDE tree is not reproducible in CI:\n{out}"


def test_an_unreadable_directory_does_not_crash_the_gate(repo: Path) -> None:
    """REGRESSION — `rglob("*.py")` raises PermissionError mid-iteration on a directory it cannot list
    (a `chmod 700` dir owned by someone else, a dead symlink, a vanished mount). That escaped as a
    traceback and took the gate down. This is a SHOWSTOPPER check in 47 repos: it must skip what it
    cannot see, never die on it."""
    (repo / "src" / "pkg" / "app.py").write_text("import os\n")
    _commit(repo, "src/pkg/app.py", "src/pkg/__init__.py")

    locked = repo / "src" / "locked"
    locked.mkdir()
    (locked / "mod.py").write_text("x = 1\n")
    locked.chmod(0o000)  # unlistable
    try:
        rc, out = _run_check(repo)
        assert "Traceback" not in out, f"an unreadable dir must be skipped, not crash:\n{out}"
        assert rc == 0, out
    finally:
        locked.chmod(0o755)  # so pytest can clean the tmpdir up


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
    assert "⚠" in out  # the gate's warning prefix — bare WARN: is --json-invisible


# --- layout applicability: the check must say when it looked at nothing --------------
# ERROR_AREAS is a project-shaped assumption (src/app/tests). A library-layout repo has
# none of them, so the area walk covers zero of its modules while `errors` stays pinned
# empty and the summary still reads "no phantom imports in src/app/tests — N imports
# checked" — a denominator built entirely from scripts/. Measured 2026-08-23: 7 of the 49
# repos carrying this check have none of the three dirs. Reported by fabrik-lib, who
# adopted the check on a synthetic src/ probe that answered "CAN this check fail?" when
# the question was "can it fail in THIS repo's layout?".


def test_no_error_area_present_says_not_applicable(repo: Path) -> None:
    """A library layout: modules live at <name>/<pkg>/, none of src/ app/ tests/ exist."""
    shutil.rmtree(repo / "src")
    (repo / "mylib" / "mylib").mkdir(parents=True)
    (repo / "mylib" / "mylib" / "__init__.py").write_text("")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool.py").write_text("import os\n")
    _commit(repo, "mylib/mylib/__init__.py", "scripts/tool.py")

    rc, out = _run_check(repo)
    assert rc == 0, out
    assert "NOT APPLICABLE" in out, f"a check that scanned none of its areas must say so:\n{out}"
    # and it must NOT claim the clean-bill-of-health it did not earn
    assert "no phantom" not in out, f"claimed a verdict over areas it never walked:\n{out}"


def test_one_error_area_present_still_reports_normally(repo: Path) -> None:
    """Applicability is 'any ERROR_AREA exists', not 'all of them' — src/ alone is enough."""
    (repo / "src" / "pkg" / "mod.py").write_text("import os\n")
    _commit(repo, "src/pkg/__init__.py", "src/pkg/mod.py")

    rc, out = _run_check(repo)
    assert rc == 0, out
    assert "NOT APPLICABLE" not in out, out
    assert "no phantom" in out, out


def test_not_applicable_does_not_mask_a_real_scripts_warning(repo: Path) -> None:
    """WARN_AREAS still get walked and reported — not-applicable is about ERROR_AREAS only."""
    shutil.rmtree(repo / "src")
    (repo / ".gitignore").write_text("libs/subagents/\n")
    (repo / "libs" / "subagents").mkdir(parents=True)
    (repo / "libs" / "__init__.py").write_text("")
    (repo / "libs" / "subagents" / "__init__.py").write_text("")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool.py").write_text("from libs.subagents import fanout\n")
    _commit(repo, ".gitignore", "libs/__init__.py", "scripts/tool.py")

    rc, out = _run_check(repo)
    assert rc == 0, out
    assert "NOT APPLICABLE" in out, out
    assert "⚠" in out, f"a scripts/ phantom must still surface:\n{out}"


def test_nested_source_root_is_not_a_phantom(repo: Path, outside: Path) -> None:
    """transdoc 01M12A2D90: the checker hardcoded ROOT/src as the only source layout, so a
    saas-skeleton whose Python lives under server/src/<pkg> — the scaffold's OWN emitted
    layout — had every repo-resident import called a PHANTOM (four false errors, one cause).
    The real trigger needs the package ALSO resolvable outside the repo (the "exists on
    this machine" half) — mimicked via extra_syspath. Source roots are discovered (any
    first-level */src), not assumed."""
    (outside / "transdoc").mkdir()
    (outside / "transdoc" / "__init__.py").write_text("")
    (repo / "server" / "src" / "transdoc").mkdir(parents=True)
    (repo / "server" / "src" / "transdoc" / "__init__.py").write_text("")
    (repo / "server" / "src" / "transdoc" / "billing_routes.py").write_text("X = 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_billing.py").write_text(
        "import os, sys\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server', 'src'))\n"
        "from transdoc import billing_routes  # noqa: E402\n"
    )
    _commit(repo, ".")
    rc, out = _run_check(repo, extra_syspath=[str(outside)])
    assert "transdoc" not in out, f"repo-resident nested-src module flagged as phantom:\n{out}"
