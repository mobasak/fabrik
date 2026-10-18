"""check_synced_unmodified.py reads two lists from the HUB's live manifest (W-5feb6e9c).

Every project copy of the check reads `/opt/fabrik/scripts/fabrik_synced_manifest.py` — no project
holds a copy — so a hub rename of either symbol reaches every project gate at once (51 copies
under /opt, 2026-10-18). The old `from fabrik_synced_manifest import X` / `except ImportError` read
a MISSING SYMBOL exactly like a missing module (both raise ImportError, both with
`name == 'fabrik_synced_manifest'`) and ran the check with empty lists: reds blamed on the project,
with no word about the hub. These tests drive `main()` in-process against a fake hub and a fake
project; the last one loads THIS tree's manifest through the check's own loader.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import runpy
import sys
import types
from pathlib import Path

import pytest

_CHECK = Path(__file__).resolve().parents[1] / "scripts/enforcement/check_synced_unmodified.py"

_FULL_MANIFEST = (
    'SEEDED_NOT_ENFORCED = {"PORTS.md"}\nRETIRED_VENDORED_DIRS = ["libs/retired_mod"]\n'
)
_HUB_WORDS = "the HUB's defect, not this project's"
_PROJECT_BLAME = "You edited a synced copy"


def _load_check():
    spec = importlib.util.spec_from_file_location("check_synced_unmodified_under_test", _CHECK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def _run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest: str | None,
    files: dict[str, str],
    lock: dict[str, str],
    *,
    hub_exists: bool = True,
) -> int:
    """Run the check with a fake hub (`manifest` None = no manifest file; `hub_exists` False = no
    hub directory at all, the VPS case) and a fake project."""
    hub = tmp_path / "hub"
    if hub_exists:
        (hub / "scripts").mkdir(parents=True)
    if manifest is not None:
        (hub / "scripts" / "fabrik_synced_manifest.py").write_text(manifest, encoding="utf-8")
    project = tmp_path / "project"
    (project / ".fabrik").mkdir(parents=True)
    for rel, text in files.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(text, encoding="utf-8")
    (project / ".fabrik" / "synced.lock").write_text(json.dumps(lock), encoding="utf-8")

    check = _load_check()
    monkeypatch.setattr(check, "FABRIK_ROOT", hub)
    monkeypatch.setattr(sys, "argv", ["check", "--project-root", str(project)])
    return check.main()


@pytest.mark.parametrize("missing", ["SEEDED_NOT_ENFORCED", "RETIRED_VENDORED_DIRS"])
def test_a_manifest_missing_a_symbol_fails_red_naming_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing: str,
) -> None:
    manifest = "".join(
        line + "\n" for line in _FULL_MANIFEST.splitlines() if not line.startswith(missing)
    )
    # PORTS.md is edited: under the old swallow a seeded rename flagged it as the PROJECT's edit.
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, f"a manifest without {missing} must red the check, not degrade it:\n{out}"
    assert missing in out, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, f"the red must name the hub, not blame the project:\n{out}"


def test_a_manifest_that_fails_to_load_fails_red(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = "import a_module_that_does_not_exist_w5feb6e9c\n" + _FULL_MANIFEST
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "a_module_that_does_not_exist_w5feb6e9c" in out, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, out


def test_an_absent_manifest_file_degrades_and_names_the_hub_beside_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, None, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out  # empty lists: the edited seeded file reads as drift, as before
    assert "PORTS.md" in out, out
    assert "hub manifest" in out and "is missing" in out, out


def test_an_absent_hub_degrades_with_no_hub_note(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No `/opt/fabrik` at all (a VPS): empty lists, drift reported plainly, no hub note."""
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, None, files, lock, hub_exists=False)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "PORTS.md" in out, out
    assert "hub manifest" not in out, out


@pytest.mark.skipif(os.geteuid() == 0, reason="root traverses a mode-000 directory")
def test_a_hub_this_user_cannot_enter_degrades_like_an_absent_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`Path.is_file()` RAISES PermissionError (it swallows only ENOENT-class errors): a hub
    another uid owns must read as absent, never crash the check with a bare traceback."""
    hub_scripts = tmp_path / "hub" / "scripts"
    hub_scripts.mkdir(parents=True)
    (hub_scripts / "fabrik_synced_manifest.py").write_text(_FULL_MANIFEST, encoding="utf-8")
    rc = None
    try:
        hub_scripts.chmod(0)
        files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
        rc = _run(monkeypatch, tmp_path, None, files, lock, hub_exists=False)
    finally:
        hub_scripts.chmod(0o755)
    out = capsys.readouterr().out
    assert rc == 1, out  # empty lists: PORTS.md reads as drift, as with no hub
    assert "PORTS.md" in out, out
    assert "hub manifest" not in out, out  # unreadable is "cannot tell", never "missing"


@pytest.mark.parametrize(
    ("seeded", "retired"),
    [("None", "[]"), ("set()", '"libs/x"'), ("set()", "[1]"), ("{5}", "[]"), ("set()", "[()]")],
    ids=["seeded-None", "retired-a-string", "retired-an-int-entry", "seeded-an-int", "empty-tuple"],
)
def test_a_wrongly_typed_list_fails_red_naming_the_hub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    seeded: str,
    retired: str,
) -> None:
    """A present symbol of the wrong shape is a guessed list too: `set(None)` crashed with a bare
    TypeError, and a string was exploded into one-character prefixes that exempt nothing."""
    manifest = f"SEEDED_NOT_ENFORCED = {seeded}\nRETIRED_VENDORED_DIRS = {retired}\n"
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert _HUB_WORDS in out, out
    assert _PROJECT_BLAME not in out, out


@pytest.mark.parametrize("code", [0, 3])
def test_a_manifest_that_exits_while_loading_fails_red(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], code: int
) -> None:
    """`SystemExit` is no `Exception`: a manifest calling `sys.exit(0)` ended the check GREEN."""
    manifest = f"import sys\nsys.exit({code})\n" + _FULL_MANIFEST
    files, lock = {"PORTS.md": "edited"}, {"PORTS.md": _md5("orig")}
    rc = _run(monkeypatch, tmp_path, manifest, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "SystemExit" in out and _HUB_WORDS in out, out


def test_an_absent_manifest_file_with_a_clean_lock_stays_green(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A CONTROL (green before and after the fix): an absent manifest alone never reds."""
    rc = _run(monkeypatch, tmp_path, None, {"a.txt": "x"}, {"a.txt": _md5("x")})
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "match what was distributed" in out, out


def test_a_complete_manifest_applies_both_lists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both lists apply, with a STALE module cached under the manifest's name: the hub's FILE must
    answer, never `sys.modules` (red on the old import path, which the cache answered)."""
    stale = types.ModuleType("fabrik_synced_manifest")
    stale.SEEDED_NOT_ENFORCED = set()  # type: ignore[attr-defined]
    stale.RETIRED_VENDORED_DIRS = []  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fabrik_synced_manifest", stale)
    files = {"PORTS.md": "edited", "libs/retired_mod/a.py": "edited", "synced.py": "edited"}
    lock = {
        "PORTS.md": _md5("orig"),
        "libs/retired_mod/a.py": _md5("orig"),
        "synced.py": _md5("orig"),
    }
    rc = _run(monkeypatch, tmp_path, _FULL_MANIFEST, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out  # an edited non-exempt file is still drift
    assert "synced.py" in out, out
    assert "PORTS.md" not in out, out
    assert "libs/retired_mod" not in out, out


def test_the_repo_manifest_answers_the_checks_own_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """The renaming worktree reds HERE, before the sync carries a rename to every project.

    The check reads the live `/opt/fabrik` manifest, so no other hub test sees a rename made on a
    branch; loading THIS tree's manifest through the check's own loader does, and its lists must
    equal what an independent run of the file defines.
    """
    root = _CHECK.parents[2]
    check = _load_check()
    monkeypatch.setattr(check, "FABRIK_ROOT", root)
    seeded, retired = check._manifest_lists()
    defined = runpy.run_path(str(root / check.MANIFEST_REL))
    assert seeded == set(defined["SEEDED_NOT_ENFORCED"]), seeded
    assert retired == tuple(defined["RETIRED_VENDORED_DIRS"]), retired


def test_the_repo_manifest_imports_only_the_stdlib() -> None:
    """Every project's check loads the HUB's manifest under the project's own interpreter, where a
    third-party package the hub venv happens to have (`yaml`) may be absent — and a hub sibling
    script is never importable (no `sys.path` entry). So the manifest imports the stdlib only."""
    tree = ast.parse((_CHECK.parents[2] / "scripts/fabrik_synced_manifest.py").read_text())
    names = {
        (alias.name if isinstance(node, ast.Import) else node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert names, "no imports parsed — the walk read nothing"
    foreign = sorted(n for n in names if n not in sys.stdlib_module_names and n != "__future__")
    assert not foreign, f"the hub manifest imports non-stdlib modules: {foreign}"
