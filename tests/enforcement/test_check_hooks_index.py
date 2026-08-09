# AFTER-EDIT: scripts/enforcement/check_hooks_index.py
"""Hooks-index freshness gate — every hook in the live configs must appear in
docs/workstation/hooks-index.md (hub-side only; projects skip)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FABRIK = Path(__file__).resolve().parents[2]
CHECK = FABRIK / "scripts/enforcement/check_hooks_index.py"


def _run(root: Path, home: Path | None = None) -> tuple[int, str]:
    env = dict(**{"PATH": "/usr/bin:/bin"})
    if home is not None:
        env["HOME"] = str(home)  # isolate synthetic fixtures from the real user config
    else:
        env["HOME"] = str(Path.home())  # the live-hub test uses the real user hooks
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _seed_hub(tmp_path: Path, *, index: str) -> Path:
    root = tmp_path / "hub"
    (root / "templates/governance").mkdir(parents=True)
    (root / "templates/governance/CLAUDE.md").write_text("# t\n")
    (root / "scripts").mkdir()
    (root / "scripts/fabrik_synced_manifest.py").write_text(
        'AGENT_HOOK_FILES = [".claude/settings.json", ".claude/hooks/final_gate_stop.py",'
        ' ".claude/hooks/skill_router.py", ".claude/hooks/session_orient.py",'
        ' ".windsurf/hooks.json"]\n'
    )
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text(json.dumps({
        "hooks": {"Stop": [{"matcher": "", "hooks": [
            {"type": "command", "command": "python3 x/.claude/hooks/final_gate_stop.py"}]}]}
    }))
    (root / "docs/workstation").mkdir(parents=True)
    (root / "docs/workstation/hooks-index.md").write_text(index)
    return root


def test_hub_with_complete_index_passes(tmp_path: Path) -> None:
    idx = ("# Hooks Index\nfinal_gate_stop.py skill_router.py session_orient.py"
           " settings.json hooks.json\n")
    root = _seed_hub(tmp_path, index=idx)
    rc, out = _run(root, home=tmp_path)
    assert rc == 0, out


def test_hub_with_missing_hook_fails_naming_it(tmp_path: Path) -> None:
    idx = "# Hooks Index\nfinal_gate_stop.py settings.json hooks.json\n"  # router+orient missing
    root = _seed_hub(tmp_path, index=idx)
    rc, out = _run(root, home=tmp_path)
    assert rc == 1
    assert "skill_router.py" in out and "session_orient.py" in out


def test_hub_without_index_fails(tmp_path: Path) -> None:
    root = _seed_hub(tmp_path, index="x")
    (root / "docs/workstation/hooks-index.md").unlink()
    rc, out = _run(root, home=tmp_path)
    assert rc == 1
    assert "hooks-index.md" in out


def test_project_side_skips(tmp_path: Path) -> None:
    # No templates/governance/CLAUDE.md marker → not the hub → graceful skip.
    root = tmp_path / "proj"
    (root / "scripts").mkdir(parents=True)
    rc, _ = _run(root, home=tmp_path)
    assert rc == 0


def test_real_hub_index_is_current() -> None:
    # The live check against the live repo — the actual freshness guarantee.
    rc, out = _run(FABRIK)
    assert rc == 0, out
