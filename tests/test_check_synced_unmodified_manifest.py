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

import hashlib
import importlib.util
import json
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
) -> int:
    """Run the check with a fake hub (`manifest` None = no manifest file) and a fake project."""
    hub = tmp_path / "hub"
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
    assert "hub manifest" in out and "is missing" in out, out


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
    branch; loading THIS tree's manifest through the check's own loader does. It also reds if the
    manifest grows a non-stdlib import, which the file-location load (no `sys.path`) cannot resolve.
    """
    check = _load_check()
    monkeypatch.setattr(check, "FABRIK_ROOT", _CHECK.parents[2])
    seeded, retired = check._manifest_lists()
    assert seeded and retired, (seeded, retired)
