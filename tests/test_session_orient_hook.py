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


def _run(cwd: Path, home: Path, stdin: str, extra_env: dict | None = None) -> tuple[int, str]:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
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
    assert "(2 entries)" in out  # exact count — a bare digit hides 12/20/200


def test_no_memory_index_is_graceful(tmp_path: Path) -> None:
    proj = tmp_path / "opt" / "bare"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "no memory index yet" in out.lower()


def _mesh_home(tmp_path: Path) -> None:
    (tmp_path / ".claude/bin").mkdir(parents=True)
    (tmp_path / ".claude/bin/claude-selfwatch.sh").write_text("#!/bin/bash\n")


def test_selfwatch_arm_order_carries_the_real_session_id(tmp_path: Path) -> None:
    # Operator directive: auto-continue always on — every session is ordered to
    # arm its self-watch with ITS OWN sid as the first action (pane-safe path).
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "sid-42-abc"}))
    assert rc == 0
    assert "ARM YOUR SELF-WATCH" in out
    # Pin the invocation SHAPE, not just a substring: persistent:true is the one
    # property that makes the watch pane-safe — dropping it must fail this test.
    assert "Monitor(persistent: true" in out
    assert 'command: "bash ~/.claude/bin/claude-selfwatch.sh sid-42-abc"' in out


def test_arm_order_sanitizes_a_garbage_sid(tmp_path: Path) -> None:
    # sid is payload-controlled and lands inside a command the agent will run —
    # anything outside [A-Za-z0-9_-] must be neutralized before embedding.
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p3"
    proj.mkdir(parents=True)
    evil = 'x"; touch /tmp/pwned; echo "'
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": evil}))
    assert rc == 0
    assert "touch /tmp/pwned" not in out
    assert "claude-selfwatch.sh x_" in out  # sanitized to the shared allowlist


def test_headless_run_gets_no_arm_order(tmp_path: Path) -> None:
    # The headless reviver (claude -p) exports CLAUDE_MESH_HEADLESS=1 — a
    # headless process has no pane to wake; ordering it to arm is pure noise.
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p4"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "s4"}),
                   extra_env={"CLAUDE_MESH_HEADLESS": "1"})
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out
    assert "Governance" in out  # the rest of ORIENT still prints


def test_compact_source_gets_no_arm_order(tmp_path: Path) -> None:
    # Compaction keeps the same process — an already-armed Monitor SURVIVES it
    # (proven live 2026-08-09); re-ordering an arm there breeds duplicate watchers.
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p5"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path,
                   json.dumps({"cwd": str(proj), "session_id": "s5", "source": "compact"}))
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out
    rc, out = _run(proj, tmp_path,
                   json.dumps({"cwd": str(proj), "session_id": "s5", "source": "resume"}))
    assert rc == 0 and "ARM YOUR SELF-WATCH" in out  # a resumed PROCESS is new — arm


def test_no_selfwatch_script_no_arm_order(tmp_path: Path) -> None:
    proj = tmp_path / "opt" / "p2"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "s"}))
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out  # boxes without the mesh stay clean


def test_non_dict_payload_still_orients(tmp_path: Path) -> None:
    # Valid JSON of the wrong shape ([]) must not swallow the whole block.
    rc, out = _run(tmp_path, tmp_path, "[]")
    assert rc == 0
    assert "ORIENT" in out and "Governance" in out


def test_fail_open_on_garbage_stdin(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, tmp_path, "{not json")
    assert rc == 0  # fail-open: never block a session
    assert "ORIENT" in out  # and the block still prints — rc alone hides an empty hook


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
    assert "(1 entries)" in out and "MEMORY.md" in out


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
    # The bound must actually bind: 256KiB / 16 chars-per-line = 16384 counted
    # entries + the truncation marker. Without the cap this reads 200000.
    assert "(16384+ entries)" in proc.stdout, "read cap or truncation marker regressed"


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


def test_autonomous_env_drops_a_marker(tmp_path: Path) -> None:
    # Phase D (plan 2026-08-10-plan-1): a launcher marks its session autonomous; the
    # @reboot sweep resumes ONLY marked, mid-work sessions.
    locks = tmp_path / "locks"
    locks.mkdir()
    proj = tmp_path / "opt" / "auto"
    proj.mkdir(parents=True)
    rc, _ = _run(proj, tmp_path,
                 json.dumps({"cwd": str(proj), "session_id": "sid-auto",
                             "transcript_path": str(tmp_path / "t.jsonl")}),
                 extra_env={"CLAUDE_MESH_AUTONOMOUS": "1",
                            "CLAUDE_SOUND_LOCKDIR": str(locks)})
    assert rc == 0
    marker = locks / "sid-auto.autonomous"
    assert marker.is_file()
    data = json.loads(marker.read_text())
    assert data["sid"] == "sid-auto" and data["cwd"] == str(proj)


def test_autonomous_marker_even_when_headless(tmp_path: Path) -> None:
    # The sweep's whole population is headless autonomous runs — the marker block must be
    # INDEPENDENT of the pane arm-gate, or every batch session goes unmarked.
    _mesh_home(tmp_path)
    locks = tmp_path / "locks"
    locks.mkdir()
    proj = tmp_path / "opt" / "auto2"
    proj.mkdir(parents=True)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "sid-h"}),
                   extra_env={"CLAUDE_MESH_AUTONOMOUS": "1", "CLAUDE_MESH_HEADLESS": "1",
                              "CLAUDE_SOUND_LOCKDIR": str(locks)})
    assert rc == 0
    assert "ARM YOUR SELF-WATCH" not in out           # headless: no pane to wake
    assert (locks / "sid-h.autonomous").is_file()      # but still swept


def test_no_autonomous_env_no_marker(tmp_path: Path) -> None:
    locks = tmp_path / "locks"
    locks.mkdir()
    proj = tmp_path / "opt" / "manual"
    proj.mkdir(parents=True)
    rc, _ = _run(proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "sid-m"}),
                 extra_env={"CLAUDE_SOUND_LOCKDIR": str(locks)})
    assert rc == 0
    assert not (locks / "sid-m.autonomous").exists()   # panes are never swept
