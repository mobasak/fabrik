"""check_synced_unmodified.py reads two lists from the HUB's live manifest (W-5feb6e9c).

Every project copy of the check imports `/opt/fabrik/scripts/fabrik_synced_manifest.py` — no
project holds a copy — so a hub rename of either symbol reaches ~46 gates at once. The old
`from fabrik_synced_manifest import X` / `except ImportError` read a MISSING SYMBOL exactly like a
missing module (both raise ImportError, both with `name == 'fabrik_synced_manifest'`) and ran the
check with empty lists: reds blamed on the project, with no word about the hub. These tests drive
`main()` in-process against a fake hub and a fake project.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_CHECK = Path(__file__).resolve().parents[1] / "scripts/enforcement/check_synced_unmodified.py"

_FULL_MANIFEST = (
    'SEEDED_NOT_ENFORCED = {"PORTS.md"}\nRETIRED_VENDORED_DIRS = ["libs/retired_mod"]\n'
)


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
    # A manifest some other test imported must never answer for the fake hub's file.
    monkeypatch.delitem(sys.modules, "fabrik_synced_manifest", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
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
    rc = _run(monkeypatch, tmp_path, manifest, {"a.txt": "x"}, {"a.txt": _md5("x")})
    out = capsys.readouterr().out
    assert rc == 1, f"a manifest without {missing} must red the check, not degrade it:\n{out}"
    assert missing in out, out


def test_a_manifest_that_fails_to_load_fails_red(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = "import a_module_that_does_not_exist_w5feb6e9c\n" + _FULL_MANIFEST
    rc = _run(monkeypatch, tmp_path, manifest, {"a.txt": "x"}, {"a.txt": _md5("x")})
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "a_module_that_does_not_exist_w5feb6e9c" in out, out


def test_an_absent_manifest_file_still_degrades_quietly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _run(monkeypatch, tmp_path, None, {"a.txt": "x"}, {"a.txt": _md5("x")})
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "match what was distributed" in out, out


def test_a_complete_manifest_applies_both_lists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"PORTS.md": "edited", "libs/retired_mod/a.py": "edited", "synced.py": "edited"}
    lock = {
        "PORTS.md": _md5("orig"),
        "libs/retired_mod/a.py": _md5("orig"),
        "synced.py": _md5("orig"),
    }
    rc = _run(monkeypatch, tmp_path, _FULL_MANIFEST, files, lock)
    out = capsys.readouterr().out
    assert rc == 1, out  # THE CONTROL: an edited non-exempt file is still drift
    assert "synced.py" in out, out
    assert "PORTS.md" not in out, out
    assert "libs/retired_mod" not in out, out
