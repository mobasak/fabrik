# AFTER-EDIT: .claude/hooks/session_orient.py, scripts/fabrik_synced_manifest.py
"""SessionStart orientation hook — every project agent starts with an explicit,
binding orientation block: CLAUDE.md governance loaded (synced, never edit
locally), MEMORY.md state, session-recall tools, and the connected enforcement
mesh. Fail-open: a broken hook must never block a session."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FABRIK = Path(__file__).resolve().parents[1]
HOOK = FABRIK / ".claude/hooks/session_orient.py"


def _run(cwd: Path, home: Path, stdin: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=15,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    return proc.returncode, proc.stdout


def test_orientation_names_the_connected_mesh(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, tmp_path, json.dumps({"cwd": str(tmp_path)}))
    assert rc == 0
    for token in ("CLAUDE.md", "session-recall", "search_chats", "Stop hook", "final_gate"):
        assert token in out, f"orientation must name {token!r}"
    assert "never edit" in out.lower()  # synced-governance rule surfaced at start


def test_memory_index_reported_when_present(tmp_path: Path) -> None:
    proj = tmp_path / "opt" / "someproj"
    proj.mkdir(parents=True)
    # harness convention: project key = full cwd with '/' -> '-'
    memdir = tmp_path / ".claude/projects" / str(proj).replace("/", "-") / "memory"
    memdir.mkdir(parents=True)
    (memdir / "MEMORY.md").write_text(
        "# Memory index\n\n- [A](a.md) — x\n- [B](b.md) — y\n", encoding="utf-8"
    )
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "MEMORY.md" in out
    assert "2" in out  # entry count surfaced


def test_no_memory_index_is_graceful(tmp_path: Path) -> None:
    proj = tmp_path / "opt" / "bare"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "no memory index yet" in out.lower()


def test_selfwatch_arm_order_carries_the_real_session_id(tmp_path: Path) -> None:
    # Operator directive: auto-continue always on — every session is ordered to
    # arm its self-watch with ITS OWN sid as the first action (pane-safe path).
    (tmp_path / ".claude/bin").mkdir(parents=True)
    (tmp_path / ".claude/bin/claude-selfwatch.sh").write_text("#!/bin/bash\n")
    proj = tmp_path / "opt" / "p"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "sid-42-abc"}))
    assert rc == 0
    assert "claude-selfwatch.sh sid-42-abc" in out
    assert "ARM YOUR SELF-WATCH" in out


def test_no_selfwatch_script_no_arm_order(tmp_path: Path) -> None:
    proj = tmp_path / "opt" / "p2"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "s"}))
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out  # boxes without the mesh stay clean


def test_fail_open_on_garbage_stdin(tmp_path: Path) -> None:
    rc, _ = _run(tmp_path, tmp_path, "{not json")
    assert rc == 0  # fail-open: never block a session


def test_hub_repo_gets_hub_orientation(tmp_path: Path) -> None:
    # In the HUB (identified by scripts/fabrik_synced_manifest.py at toplevel),
    # CLAUDE.md is the hub contract — canonical and editable — NOT a synced copy.
    hub = tmp_path / "opt" / "fabrikish"
    (hub / "scripts").mkdir(parents=True)
    (hub / "scripts/fabrik_synced_manifest.py").write_text("# marker\n", encoding="utf-8")
    rc, out = _run(hub, tmp_path, json.dumps({"cwd": str(hub)}))
    assert rc == 0
    assert "HUB" in out and "canonical" in out.lower()
    assert "never edit" not in out.lower(), "hub sessions must not be told CLAUDE.md is unedittable"


def test_memory_key_sanitizes_dots_like_the_harness(tmp_path: Path) -> None:
    # Claude Code's project key replaces '.' as well as '/' with '-'.
    proj = tmp_path / "opt" / "app.v2"
    proj.mkdir(parents=True)
    key = str(proj).replace("/", "-").replace(".", "-")
    memdir = tmp_path / ".claude/projects" / key / "memory"
    memdir.mkdir(parents=True)
    (memdir / "MEMORY.md").write_text("- [A](a.md) — x\n", encoding="utf-8")
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "1" in out and "MEMORY.md" in out


def test_huge_memory_index_is_bounded_and_output_survives_c_locale(tmp_path: Path) -> None:
    proj = tmp_path / "opt" / "big"
    proj.mkdir(parents=True)
    key = str(proj).replace("/", "-").replace(".", "-")
    memdir = tmp_path / ".claude/projects" / key / "memory"
    memdir.mkdir(parents=True)
    (memdir / "MEMORY.md").write_text("- [E](e.md) — x\n" * 200_000, encoding="utf-8")  # ~3.4 MB
    import subprocess as sp

    proc = sp.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"cwd": str(proj)}),
        capture_output=True,
        text=True,
        timeout=15,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0"},
    )
    assert proc.returncode == 0
    assert len(proc.stdout) > 200, "C locale must not silently swallow the whole block"


def test_hook_is_synced_and_wired() -> None:
    sys.path.insert(0, str(FABRIK / "scripts"))
    import fabrik_synced_manifest as m

    assert ".claude/hooks/session_orient.py" in m.AGENT_HOOK_FILES
    settings = json.loads((FABRIK / ".claude/settings.json").read_text(encoding="utf-8"))
    cmds = [
        h["command"]
        for grp in settings["hooks"]["SessionStart"]
        for h in grp["hooks"]
    ]
    assert any("session_orient.py" in c for c in cmds)
