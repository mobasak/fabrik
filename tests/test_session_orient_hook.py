# AFTER-EDIT: .claude/hooks/session_orient.py, scripts/fabrik_synced_manifest.py
"""SessionStart orientation hook — every project agent starts with an explicit,
binding orientation block: CLAUDE.md governance loaded (synced, never edit
locally), MEMORY.md state, session-recall tools, and the connected enforcement
mesh. Fail-open: a broken hook must never block a session."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FABRIK = Path(__file__).resolve().parents[1]
HOOK = FABRIK / ".claude/hooks/session_orient.py"


def _run(cwd: Path, home: Path, stdin: str, extra_env: dict | None = None) -> tuple[int, str]:
    # KAIZEN_EVENTS_DIR is pinned EXPLICITLY, not left to fall out of the tmp HOME: the
    # hook emits kaizen events, and "the default happens to resolve under our tmp home"
    # is a coupling one refactor away from seeding the operator's real event store with
    # synthetic sessions (38 such files found and purged 2026-08-19 from the sibling
    # suite, which launches the hook with the developer's real environment).
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "KAIZEN_EVENTS_DIR": str(home / "kaizen-events"),
    }
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


def _hub_env(hub: Path) -> dict:
    """The hook's own test seam for the hub path (`FABRIK_ORIENT_HUB_ROOT`, default
    `/opt/fabrik`) — a tmp dir stands in for the hub, never the real checkout. Hook-specific:
    `FABRIK_HUB_ROOT` is `command_run.py`'s, for another purpose."""
    return {"FABRIK_ORIENT_HUB_ROOT": str(hub)}


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
    # Pin the invocation SHAPE (D-356): a background Bash task through the arm wrapper — a Monitor
    # ends within 30 minutes and has no persistent mode at 2.1.280.
    assert "Bash(run_in_background: true" in out
    assert 'command: "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh sid-42-abc"' in out
    assert "ONE wake per arm" in out and "re-arm order" in out
    assert "Monitor(persistent" not in out


def test_no_branch_teaches_the_nohup_arming_form(tmp_path: Path) -> None:
    # web-ecommerce-factory, 2026-08-30: a session revived 13 times stopped being
    # revivable after it re-armed per the STATIC mesh paragraph, which still taught
    # `nohup ... >/dev/null 2>&1 &`. A watch armed that way prints its ONE wake line
    # into /dev/null and exits — structurally incapable of waking the pane — while
    # still consuming the death marker. The Monitor form is the only wake channel;
    # no branch of this hook may ever emit the nohup form again.
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p"
    proj.mkdir(parents=True)
    for payload in (
        {"cwd": str(proj), "session_id": "sid-42-abc"},
        {"cwd": str(proj), "session_id": "sid-42-abc", "source": "compact"},
    ):
        rc, out = _run(proj, tmp_path, json.dumps(payload))
        assert rc == 0
        assert "nohup bash" not in out, f"nohup arming form leaked (source={payload.get('source')})"
        if payload.get("source") != "compact":
            # the one arm order that prints must mandate the background-task channel (D-356)
            assert "Bash(run_in_background: true" in out


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
    assert "selfwatch_arm.sh x_" in out  # sanitized to the shared allowlist


def test_headless_run_gets_no_arm_order(tmp_path: Path) -> None:
    # The headless reviver (claude -p) exports CLAUDE_MESH_HEADLESS=1 — a
    # headless process has no pane to wake; ordering it to arm is pure noise.
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p4"
    proj.mkdir(parents=True)
    rc, out = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj), "session_id": "s4"}),
        extra_env={"CLAUDE_MESH_HEADLESS": "1"},
    )
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out
    assert "Governance" in out  # the rest of ORIENT still prints


def test_fabrik_headless_run_gets_no_arm_order(tmp_path: Path) -> None:
    # The declared headless spawners (ci_fix_dispatcher, claude_broker, rivals_run) set
    # FABRIK_HEADLESS=1 alone; with tools on, a `claude -p` worker obeys the order and
    # burns its timeout re-arming a watch (intel, 01M3C9BH).
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p4b"
    proj.mkdir(parents=True)
    rc, out = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj), "session_id": "s4b"}),
        extra_env={"FABRIK_HEADLESS": "1"},
    )
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out
    assert "Governance" in out  # the rest of ORIENT still prints


def test_compact_source_gets_no_arm_order(tmp_path: Path) -> None:
    # Compaction keeps the same process — an already-armed Monitor SURVIVES it
    # (proven live 2026-08-09); re-ordering an arm there breeds duplicate watchers.
    _mesh_home(tmp_path)
    proj = tmp_path / "opt" / "p5"
    proj.mkdir(parents=True)
    rc, out = _run(
        proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "s5", "source": "compact"})
    )
    assert rc == 0 and "ARM YOUR SELF-WATCH" not in out
    rc, out = _run(
        proj, tmp_path, json.dumps({"cwd": str(proj), "session_id": "s5", "source": "resume"})
    )
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
    # Hub identity is the manifest AND the hub path (D4); the test seam names this dir the hub.
    rc, out = _run(hub, tmp_path, json.dumps({"cwd": str(hub)}), _hub_env(hub))
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
        env={
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "PYTHONCOERCECLOCALE": "0",
            "KAIZEN_EVENTS_DIR": str(tmp_path / "kaizen-events"),
        },
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
    cmds = [h["command"] for grp in settings["hooks"]["SessionStart"] for h in grp["hooks"]]
    assert any("session_orient.py" in c for c in cmds)


def test_autonomous_env_drops_a_marker(tmp_path: Path) -> None:
    # Phase D (plan 2026-08-10-plan-1), RETARGETED by plan 2026-08-13-plan-1: the marker
    # must land in the PERSISTENT state dir (MESH_STATE_DIR), not the /tmp lock dir — a
    # VM termination wipes /tmp and with it every sweep eligibility (the Modern Standby
    # incident). The @reboot sweep resumes ONLY marked, mid-work sessions.
    state = tmp_path / "state"
    proj = tmp_path / "opt" / "auto"
    proj.mkdir(parents=True)
    rc, _ = _run(
        proj,
        tmp_path,
        json.dumps(
            {
                "cwd": str(proj),
                "session_id": "sid-auto",
                "transcript_path": str(tmp_path / "t.jsonl"),
            }
        ),
        extra_env={"CLAUDE_MESH_AUTONOMOUS": "1", "MESH_STATE_DIR": str(state)},
    )
    assert rc == 0
    marker = state / "sid-auto.autonomous"
    assert marker.is_file()
    data = json.loads(marker.read_text())
    assert data["sid"] == "sid-auto" and data["cwd"] == str(proj)
    assert (marker.stat().st_mode & 0o777) == 0o600  # cwd/transcript paths stay private


def test_marker_never_lands_in_the_lock_dir(tmp_path: Path) -> None:
    # The inverse of the retarget: with BOTH envs set, the ephemeral lock dir stays empty —
    # a marker there would be wiped by the next VM cut and is a regression to the incident.
    state = tmp_path / "state"
    locks = tmp_path / "locks"
    locks.mkdir()
    proj = tmp_path / "opt" / "auto3"
    proj.mkdir(parents=True)
    rc, _ = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj), "session_id": "sid-b"}),
        extra_env={
            "CLAUDE_MESH_AUTONOMOUS": "1",
            "MESH_STATE_DIR": str(state),
            "CLAUDE_SOUND_LOCKDIR": str(locks),
        },
    )
    assert rc == 0
    assert (state / "sid-b.autonomous").is_file()
    assert not (locks / "sid-b.autonomous").exists()


def test_unwritable_state_dir_is_fail_open(tmp_path: Path) -> None:
    # A broken state dir must never block a session (hook fail-open discipline).
    state = tmp_path / "state"
    state.mkdir(mode=0o500)
    proj = tmp_path / "opt" / "auto4"
    proj.mkdir(parents=True)
    try:
        rc, out = _run(
            proj,
            tmp_path,
            json.dumps({"cwd": str(proj), "session_id": "sid-ro"}),
            extra_env={"CLAUDE_MESH_AUTONOMOUS": "1", "MESH_STATE_DIR": str(state)},
        )
    finally:
        state.chmod(0o700)
    assert rc == 0
    # fail-open means "never blocks AND still orients" — a swallowed OSError that also
    # swallowed the ORIENT block would silently strip governance from every autonomous
    # session (closer F13)
    assert "ORIENT" in out


def test_state_dir_defaults_agree_writer_and_sweep() -> None:
    """The writer (session_orient.py) and the consumer (claude-reboot-sweep.sh) derive the
    DEFAULT persistent dir independently — two hand-written strings with no shared source.
    If either drifts, every marker is silently orphaned and the standby incident returns
    with all suites green (closer F12). Skips off-hub (the sweep is a box surface)."""
    import re

    sweep = Path.home() / ".claude" / "bin" / "claude-reboot-sweep.sh"
    if not sweep.is_file():
        return  # box sweep not present (non-hub environment) — nothing to compare
    hook_src = HOOK.read_text()
    sweep_src = sweep.read_text()
    # writer side: the three Path components that build the default
    assert '/ ".claude" / "state" / "autonomous"' in hook_src, (
        "writer default no longer derives ~/.claude/state/autonomous"
    )
    m = re.search(r'state="\$\{MESH_STATE_DIR:-\$HOME/([^}]+)\}"', sweep_src)
    assert m and m.group(1) == ".claude/state/autonomous", (
        "sweep default drifted from the writer's",
        m.group(1) if m else None,
    )


def test_rerun_rewrites_a_consumed_marker(tmp_path: Path) -> None:
    # RS7's repo half (bounce-loop self-heal): the sweep consumes the marker before its
    # resume; the resumed session's own SessionStart must re-write it, else a resume killed
    # by the next VM bounce is lost forever.
    state = tmp_path / "state"
    proj = tmp_path / "opt" / "auto5"
    proj.mkdir(parents=True)
    payload = json.dumps({"cwd": str(proj), "session_id": "sid-r"})
    env = {"CLAUDE_MESH_AUTONOMOUS": "1", "MESH_STATE_DIR": str(state)}
    rc, _ = _run(proj, tmp_path, payload, extra_env=env)
    assert rc == 0
    marker = state / "sid-r.autonomous"
    assert marker.is_file()
    marker.unlink()  # the sweep's consume
    rc, _ = _run(proj, tmp_path, payload, extra_env=env)
    assert rc == 0
    assert marker.is_file()  # re-marked by the resumed session


def test_autonomous_marker_even_when_headless(tmp_path: Path) -> None:
    # The sweep's whole population is headless autonomous runs — the marker block must be
    # INDEPENDENT of the pane arm-gate, or every batch session goes unmarked.
    _mesh_home(tmp_path)
    locks = tmp_path / "locks"
    locks.mkdir()
    proj = tmp_path / "opt" / "auto2"
    proj.mkdir(parents=True)
    rc, out = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj), "session_id": "sid-h"}),
        extra_env={
            "CLAUDE_MESH_AUTONOMOUS": "1",
            "CLAUDE_MESH_HEADLESS": "1",
            "MESH_STATE_DIR": str(locks / "state"),
        },
    )
    assert rc == 0
    assert "ARM YOUR SELF-WATCH" not in out  # headless: no pane to wake
    assert (locks / "state" / "sid-h.autonomous").is_file()  # but still swept


def test_no_autonomous_env_no_marker(tmp_path: Path) -> None:
    locks = tmp_path / "locks"
    locks.mkdir()
    proj = tmp_path / "opt" / "manual"
    proj.mkdir(parents=True)
    rc, _ = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj), "session_id": "sid-m"}),
        extra_env={"CLAUDE_SOUND_LOCKDIR": str(locks)},
    )
    assert rc == 0
    assert not (locks / "sid-m.autonomous").exists()  # panes are never swept


# --- T04: _sessions_line — the "N sessions share this main checkout" advisory ---


def _fake_proc(tmp: Path, entries: list[tuple[str, str, str | None]]) -> Path:
    """Build a fake /proc tree: entries = [(pid, comm, cwd_or_None), ...].

    A None cwd omits the `cwd` symlink entirely (mimics a pid the scan cannot
    introspect — e.g. a race where the process exits mid-scan); any string
    creates a `cwd` symlink to that path, dangling or not.
    """
    proc = tmp / "fake_proc"
    proc.mkdir(parents=True, exist_ok=True)
    for pid, comm, cwd in entries:
        d = proc / pid
        d.mkdir()
        (d / "comm").write_text(comm + "\n", encoding="utf-8")
        if cwd is not None:
            (d / "cwd").symlink_to(cwd)
    return proc


def test_sessions_advisory_fires_at_three_shared_sessions(tmp_path: Path) -> None:
    scratch = tmp_path / "opt" / "scratch"
    scratch.mkdir(parents=True)
    proc = _fake_proc(
        tmp_path,
        [
            ("101", "claude", str(scratch)),
            ("102", "claude", str(scratch)),
            ("103", "claude", str(scratch)),
            ("104", "bash", str(scratch)),  # wrong comm — not counted
            ("105", "claude", None),  # no cwd at all — not counted
            ("106", "claude-foo", str(scratch)),  # comm merely PREFIXED with claude — not counted
        ],
    )
    rc, out = _run(
        scratch,
        tmp_path,
        json.dumps({"cwd": str(scratch)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    assert out.count("sessions share this main checkout") == 1
    lines = [ln for ln in out.splitlines() if "sessions share this main checkout" in ln]
    assert lines[0].startswith("- ⚠️ **3 sessions share this main checkout.**")
    # placed in _identity_line's slot: after Governance/Memory, before the MCP line
    idx_gov = out.index("**Governance")
    idx_line = out.index("sessions share this main checkout")
    idx_mcp = out.index("**Your ASSIGNED MCPs")
    assert idx_gov < idx_line < idx_mcp


def test_sessions_advisory_fires_at_exactly_two_shared_sessions(tmp_path: Path) -> None:
    # Pins the `< 2` boundary itself — a mutant that reads `< 3` still leaves every
    # OTHER test green (they all use 0, 1, or 3 matching entries).
    scratch = tmp_path / "opt" / "pair"
    scratch.mkdir(parents=True)
    proc = _fake_proc(
        tmp_path,
        [
            ("111", "claude", str(scratch)),
            ("112", "claude", str(scratch)),
        ],
    )
    rc, out = _run(
        scratch,
        tmp_path,
        json.dumps({"cwd": str(scratch)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    lines = [ln for ln in out.splitlines() if "sessions share this main checkout" in ln]
    assert len(lines) == 1
    assert lines[0].startswith("- ⚠️ **2 sessions share this main checkout.**")


def test_sessions_advisory_silent_below_two(tmp_path: Path) -> None:
    scratch = tmp_path / "opt" / "solo"
    scratch.mkdir(parents=True)
    proc = _fake_proc(tmp_path, [("201", "claude", str(scratch))])
    rc, out = _run(
        scratch,
        tmp_path,
        json.dumps({"cwd": str(scratch)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    assert "sessions share this main checkout" not in out
    # byte-identical to a run with no FABRIK_PROC_ROOT at all for this cwd
    rc2, out2 = _run(scratch, tmp_path, json.dumps({"cwd": str(scratch)}))
    assert rc2 == 0
    assert out == out2


def test_sessions_advisory_suppressed_in_worktree(tmp_path: Path) -> None:
    scratch = tmp_path / "work" / ".claude" / "worktrees" / "agent1"
    scratch.mkdir(parents=True)
    proc = _fake_proc(
        tmp_path,
        [
            ("301", "claude", str(scratch)),
            ("302", "claude", str(scratch)),
            ("303", "claude", str(scratch)),
        ],
    )
    rc, out = _run(
        scratch,
        tmp_path,
        json.dumps({"cwd": str(scratch)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    assert "sessions share this main checkout" not in out


def test_sessions_advisory_suppressed_in_hub(tmp_path: Path) -> None:
    hub = tmp_path / "opt" / "hubish2"
    (hub / "scripts").mkdir(parents=True)
    (hub / "scripts" / "fabrik_synced_manifest.py").write_text("# marker\n", encoding="utf-8")
    proc = _fake_proc(
        tmp_path,
        [
            ("401", "claude", str(hub)),
            ("402", "claude", str(hub)),
            ("403", "claude", str(hub)),
        ],
    )
    rc, out = _run(
        hub,
        tmp_path,
        json.dumps({"cwd": str(hub)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc), **_hub_env(hub)},
    )
    assert rc == 0
    assert "sessions share this main checkout" not in out


def test_sessions_advisory_dangling_cwd_never_raises(tmp_path: Path) -> None:
    # A lone dangling entry makes `rc == 0` a vacuous check: the `__main__` guard
    # (session_orient.py) swallows ANY exception raised anywhere in main() and
    # still exits 0 -- but in that case NOTHING is printed at all, since the crash
    # happens while building the print() argument, before print() ever runs. So a
    # standalone dangling entry can't tell "correctly skipped" apart from "silently
    # crashed": both leave "sessions share..." absent from (a possibly empty) out.
    # Putting the dangling entry BESIDE two live, matching entries closes that gap:
    # if the per-entry fail-open ever regresses to an abort, the whole ORIENT block
    # (this advisory included) goes missing and the "2 sessions" assertion below
    # fails -- pinning skip-not-abort rather than merely "the process didn't crash".
    scratch = tmp_path / "opt" / "danglecase"
    scratch.mkdir(parents=True)
    proc = _fake_proc(
        tmp_path,
        [
            ("501", "claude", str(scratch)),
            ("502", "claude", str(scratch)),
            ("503", "claude", str(tmp_path / "gone-nowhere")),  # dangling -- skipped, not fatal
        ],
    )
    rc, out = _run(
        scratch,
        tmp_path,
        json.dumps({"cwd": str(scratch)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    lines = [ln for ln in out.splitlines() if "sessions share this main checkout" in ln]
    assert len(lines) == 1
    assert lines[0].startswith("- ⚠️ **2 sessions share this main checkout.**")


def test_sessions_advisory_live_scan_is_fast(tmp_path: Path) -> None:
    # Direct import-call against the REAL /proc (no FABRIK_PROC_ROOT) — bounds
    # the scan itself, not subprocess/interpreter startup overhead.
    import importlib.util
    import time

    spec = importlib.util.spec_from_file_location("session_orient_direct_t04", HOOK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    scratch = tmp_path / "opt" / "timingcase"
    scratch.mkdir(parents=True)
    saved = os.environ.pop("FABRIK_PROC_ROOT", None)
    try:
        start = time.perf_counter()
        result = mod._sessions_line(str(scratch))
        elapsed = time.perf_counter() - start
    finally:
        if saved is not None:
            os.environ["FABRIK_PROC_ROOT"] = saved
    assert isinstance(result, str)
    assert elapsed < 0.2


def _adopted_repo(tmp_path: Path, owner: str | None, plans_marker: str | None = None) -> Path:
    """A PROJECT repo (no manifest file). `owner` writes a real MERGE OWNER ledger row — the
    only thing that declares adoption. `plans_marker` writes the RENDERED PLANS.md comment,
    which must NEVER be sufficient on its own (it is deletable; the ledger row is not)."""
    proj = tmp_path / "opt" / "adoptedish"
    (proj / "docs" / "development").mkdir(parents=True)
    rows = "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
    if owner:
        rows += (
            f"| D-029 | 2026-09-16 | agent-1 (--adopt) | MERGE OWNER: {owner} — the only writer"
            " of the base branch | declared at adoption | docs/development/PLANS.md |\n"
        )
    (proj / "docs/DECISIONS.md").write_text(rows, encoding="utf-8")
    body = "# Plans\n\n" + (plans_marker + "\n" if plans_marker else "") + "\n## Board\n"
    (proj / "docs/development/PLANS.md").write_text(body, encoding="utf-8")
    return proj


def test_adopted_project_warns_an_unnamed_session_and_names_the_owner(tmp_path: Path) -> None:
    # The multi-agent model's only identity channel is CLAUDE_AGENT and every control keyed on
    # it fails SILENT when unset, while `--adopt` targets repos whose sessions are already
    # running and cannot set it (trade-intelligence 01M2N1MJK1, D-030/D-267).
    proj = _adopted_repo(tmp_path, "agent-1")
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "ORIENT" in out  # the block still prints — rc alone hides an empty hook
    assert "CLAUDE_AGENT is UNSET" in out
    assert "DECLARES merge owner `agent-1`" in out
    # Every consequence the message asserts is pinned, so a mutant that rewrites the prose
    # into a false claim cannot stay green (round 1: a wrong path in this string killed 0/34).
    assert "agent_role.py" in out and "check_commit_trailers.py" in out
    # ⚠️ "attributable" is a SUBSTRING of "unattributable", so the obvious pin passes on the
    # exact regression it exists to catch (executed: "remain unattributable, sadly" passed).
    assert "command_run.py" in out
    assert "is attributable" in out and "unattributable" not in out
    # ⚠️ The advisory must name the REMEDY THAT WORKS WITHOUT A RELAUNCH. It previously asserted
    # "a live session cannot change its own environment" — true of the env var, but D-271 shipped
    # whoami_agent.py, which makes the SESSION nameable anyway, so that sentence became false in
    # 46 distributed copies the moment the writer landed.
    assert "whoami_agent.py --as" in out
    assert "without a relaunch" in out
    assert "cannot change its own environment" not in out, "a claim this fleet's own code falsified"
    # ⚠️ And it must not OVERPROMISE. `command_run.py` resolves the agent at `start`, so a run
    # record already open keeps its empty cell — an advisory saying attribution is fixed
    # "immediately" sends the reader on to file another unattributable FEEDBACK row.
    assert "ALREADY OPEN" in out, "the advisory must state what binding does NOT retroactively fix"
    assert "attributable immediately" not in out
    # and the charter needs a named relaunch either way: agent_role.py reads the env var only
    assert "charter waits for your next start" not in out


def test_the_rendered_plans_marker_alone_never_declares_adoption(tmp_path: Path) -> None:
    # THE REGRESSION GUARD FOR D-267's first cut. The PLANS.md comment is RENDERED from the
    # ledger row (docs_updater.py::_merge_owner_header_line), so keying on it let anyone
    # silence the advisory for good by deleting one HTML comment, while read_merge_owner()
    # still returned the owner. Executed against the real docs_updater before this fix.
    proj = _adopted_repo(
        tmp_path, None, plans_marker="<!-- Merge owner: agent-1 | source: D-029 -->"
    )
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "ORIENT" in out
    assert "CLAUDE_AGENT is UNSET" not in out


def test_live_sessions_alone_warn_once_not_twice(tmp_path: Path) -> None:
    # /opt/iterative_image_editor runs three lanes with 14 plan-locks and has NEITHER a ledger
    # row NOR a PLANS.md marker (executed 2026-09-16) — an adoption-keyed advisory can never
    # reach it. A repo is multi-agent when several agents are IN it, so this MUST warn.
    # ⚠️ But exactly ONCE: b5c01855 printed two bullets about the same measured fact with two
    # DIFFERENT relaunch commands, live in 5 of 45 repos. `_sessions_line` owns this case
    # because its remedy (the worktree form) is the right one for a shared MAIN checkout.
    proj = _adopted_repo(tmp_path, None)
    proc = _fake_proc(tmp_path, [("301", "claude", str(proj)), ("302", "claude", str(proj))])
    rc, out = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    assert "ORIENT" in out
    assert out.count("sessions share this main checkout") == 1
    assert "CLAUDE_AGENT is UNSET and 2 live sessions" not in out, "two bullets, one fact"


def test_a_declared_owner_still_warns_even_with_one_session(tmp_path: Path) -> None:
    # The suppression above must not swallow the DECLARED case, which `_sessions_line` never
    # covers (it needs >=2 live sessions and this has one).
    proj = _adopted_repo(tmp_path, "agent-1")
    proc = _fake_proc(tmp_path, [("311", "claude", str(proj))])
    rc, out = _run(
        proj, tmp_path, json.dumps({"cwd": str(proj)}), extra_env={"FABRIK_PROC_ROOT": str(proc)}
    )
    assert rc == 0
    assert "DECLARES merge owner `agent-1`" in out


def test_an_undeclared_row_is_not_an_owner(tmp_path: Path) -> None:
    # `--adopt` cannot mint the name (its own ^[a-z0-9-]{1,32}$ refuses it), but a HUMAN writes
    # `MERGE OWNER: UNDECLARED — we un-adopted` as an ordinary row. Without the lookahead the
    # hook announces `UNDECLARED` as the merge owner. Case-insensitive: the phrase match is.
    for name in ("UNDECLARED", "undeclared", "Undeclared"):
        proj = _adopted_repo(tmp_path / name, f"{name} — we un-adopted, no single writer")
        rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
        assert rc == 0, name
        assert "DECLARES merge owner" not in out, name


def test_a_merge_owner_row_below_the_head_window_is_still_found(tmp_path: Path) -> None:
    # The merge-owner row is written ONCE at adoption and never moves, while new rows are
    # appended — so a head-only window RETIRES this key by ordinary use. Executed on the real
    # fleet before this fix: +30 rows to the only declared ledger silenced it.
    proj = tmp_path / "opt" / "bigledger"
    (proj / "docs" / "development").mkdir(parents=True)
    filler = "| D-%03d | 2026-09-16 | w | routine row | y | z |\n"
    rows = "".join(filler % i for i in range(1, 2000))  # comfortably past one 64 KB window
    (proj / "docs/DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        + rows
        + "| D-901 | 2026-09-16 | a | MERGE OWNER: deepowner | y | z |\n",
        encoding="utf-8",
    )
    assert (proj / "docs/DECISIONS.md").stat().st_size > 64 * 1024
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "DECLARES merge owner `deepowner`" in out


def test_a_byte_cap_cut_never_renders_a_truncated_owner_name(tmp_path: Path) -> None:
    # A cut landing INSIDE the owner name used to render the truncated name as fact
    # (`alphab` for `alphabravocharliedelta`) — the loud-and-wrong side of a bounded read.
    # The row is placed so a 64 KB cut falls 6 characters into the NAME. The hook now reads the
    # WHOLE ledger (W-076ff4a9: a head+tail window hid a mid-file winner), so the full name is
    # rendered; the remaining bound is `_LEDGER_MAX_BYTES`, exercised here by lowering it onto
    # the same cut, where the cut line must be DROPPED rather than read as `alphab`.
    proj = tmp_path / "opt" / "cutledger"
    (proj / "docs" / "development").mkdir(parents=True)
    hdr = "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
    filler = "| D-%03d | 2026-09-16 | w | routine row | y | z |\n"
    row = "| D-999 | 2026-09-16 | a | MERGE OWNER: alphabravocharliedelta | y | z |\n"
    target = 64 * 1024 - (len(b"| D-999 | 2026-09-16 | a | MERGE OWNER: ") + 6)
    body = hdr
    i = 1
    while len(body.encode()) + len((filler % i).encode()) <= target:
        body += filler % i
        i += 1
    pad = target - len(body.encode())  # a non-row filler line lands the row start on target
    if pad:
        body += "x" * (pad - 1) + "\n"
    assert len(body.encode()) == target, len(body.encode())
    body += row
    body += "".join(filler % j for j in range(i, i + 4000))  # wider than two windows
    (proj / "docs/DECISIONS.md").write_text(body, encoding="utf-8")
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "`alphab`" not in out, "a truncated name was rendered as the declared owner"
    assert "DECLARES merge owner `alphabravocharliedelta`" in out, "a mid-file row must be read"

    import importlib.util

    spec = importlib.util.spec_from_file_location("session_orient_cut", HOOK)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    hook._LEDGER_MAX_BYTES = 64 * 1024  # the cut now lands 6 characters into the name
    assert hook._ledger_merge_owner(str(proj)) == ""


def test_the_last_merge_owner_row_wins(tmp_path: Path) -> None:
    # The ledger's own law: a changed owner is a NEW superseding row, so the LAST one wins.
    # A first-match-wins mutant passed every grader before this test existed.
    proj = tmp_path / "opt" / "superseded"
    (proj / "docs" / "development").mkdir(parents=True)
    (proj / "docs/DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        "| D-010 | 2026-09-01 | a | MERGE OWNER: oldowner | y | z |\n"
        "| D-020 | 2026-09-16 | a | MERGE OWNER: newowner — supersedes D-010 | y | z |\n",
        encoding="utf-8",
    )
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "DECLARES merge owner `newowner`" in out
    assert "oldowner" not in out


def test_a_lowercase_row_id_still_parses(tmp_path: Path) -> None:
    # `_LEDGER_ROW_RE` carries re.I; nothing graded it, so dropping the flag was free.
    proj = tmp_path / "opt" / "lowercase"
    (proj / "docs" / "development").mkdir(parents=True)
    (proj / "docs/DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        "| d-029 | 2026-09-16 | a | MERGE OWNER: caseowner | y | z |\n",
        encoding="utf-8",
    )
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "DECLARES merge owner `caseowner`" in out


def test_single_session_unadopted_repo_stays_silent(tmp_path: Path) -> None:
    proj = _adopted_repo(tmp_path, None)
    proc = _fake_proc(tmp_path, [("303", "claude", str(proj))])
    rc, out = _run(
        proj,
        tmp_path,
        json.dumps({"cwd": str(proj)}),
        extra_env={"FABRIK_PROC_ROOT": str(proc)},
    )
    assert rc == 0
    assert "ORIENT" in out
    assert "CLAUDE_AGENT is UNSET" not in out


def test_named_session_in_an_adopted_repo_gets_no_warning(tmp_path: Path) -> None:
    proj = _adopted_repo(tmp_path, "agent-1")
    rc, out = _run(
        proj, tmp_path, json.dumps({"cwd": str(proj)}), extra_env={"CLAUDE_AGENT": "agent-2"}
    )
    assert rc == 0
    assert "ORIENT" in out
    assert "CLAUDE_AGENT is UNSET" not in out


def test_the_hub_keeps_its_own_wording_not_the_adopted_one(tmp_path: Path) -> None:
    hub = tmp_path / "opt" / "fabrikish"
    (hub / "scripts").mkdir(parents=True)
    (hub / "scripts/fabrik_synced_manifest.py").write_text("# marker\n", encoding="utf-8")
    (hub / "docs").mkdir(parents=True)
    (hub / "docs/DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        "| D-029 | 2026-09-16 | a | MERGE OWNER: agent-1 | x | y |\n",
        encoding="utf-8",
    )
    rc, out = _run(hub, tmp_path, json.dumps({"cwd": str(hub)}), _hub_env(hub))
    assert rc == 0
    assert "this hub session is UNNAMED" in out
    assert "DECLARES merge owner" not in out


def test_an_over_long_owner_name_cannot_flood_the_first_message(tmp_path: Path) -> None:
    # The PLANS/ledger grammar is deliberately permissive (docs_updater.py:944-947), so a
    # hand-minted row can carry a name `--adopt`'s own ^[a-z0-9-]{1,32}$ would refuse.
    proj = _adopted_repo(tmp_path, "a" * 5000)
    rc, out = _run(proj, tmp_path, json.dumps({"cwd": str(proj)}))
    assert rc == 0
    assert "a" * 5000 not in out
    assert "a" * 32 in out  # capped at the grammar's own 32, not dropped


def test_a_nul_in_cwd_still_prints_the_whole_block(tmp_path: Path) -> None:
    # `os.path.realpath` raises ValueError on an embedded NUL and `print()` evaluates every
    # argument before emitting, so one raise used to cost the ENTIRE block at rc 0 / 0 bytes.
    rc, out = _run(tmp_path, tmp_path, json.dumps({"cwd": str(tmp_path) + "\x00x"}))
    assert rc == 0
    assert "ORIENT" in out


def test_the_merge_owner_grammar_tracks_its_sources_and_names_its_one_divergence(
    tmp_path: Path,
) -> None:
    # This hook is standalone and fleet-synced, so it cannot import either owner of the grammar;
    # the copy is pinned here (the precedent command_run.py set for its axis list).
    # ⚠️ The pin asserts the CAPTURE verbatim — INCLUDING the quantifier, which an earlier cut
    # stopped one character short of, leaving it structurally blind to the only position where
    # the three actually differed. The one deliberate divergence is the UNDECLARED lookahead
    # inside the hook's owner regex, asserted HERE so it cannot be dropped silently; the
    # un-adoption TOKEN regex and the `supersedes D-NNN:` prefix (W-076ff4a9) are shared by all
    # three readers byte for byte.
    hook = (FABRIK / ".claude/hooks/session_orient.py").read_text(encoding="utf-8")
    du = (FABRIK / "scripts/docs_updater.py").read_text(encoding="utf-8")
    dec = (FABRIK / "scripts/decisions.py").read_text(encoding="utf-8")
    bs = chr(92)
    capture = "([A-Za-z0-9][A-Za-z0-9_.@-]*)"
    # the optional supersedes prefix a changed owner's NEW row opens with
    prefix = r'_SUPERSEDES_PREFIX = r"(?:supersedes\s+D-\d+[^:.]{0,160}[:.][\s*]*)?"'
    phrase = "MERGE OWNER:" + bs + "s*"
    # the formatter wraps a long `re.compile(...)` over lines, so the USE is matched with all
    # whitespace removed; the pattern literals themselves hold no spaces to lose
    flat = {n: "".join(src.split()) for n, src in (("hook", hook), ("du", du), ("dec", dec))}
    for name, src in (("hook", hook), ("docs_updater", du), ("decisions.py", dec)):
        assert prefix in src, f"{name}'s supersedes prefix drifted"
    uses = r'MERGE_OWNER_RE=re.compile(r"^\**\s*"+_SUPERSEDES_PREFIX+r"MERGEOWNER:'
    for name, src in flat.items():
        assert uses in src, f"{name}'s owner regex does not use the prefix"
    assert phrase + capture in du, "docs_updater's MERGE_OWNER_RE drifted"
    assert phrase + capture in dec, "decisions.py's MERGE_OWNER_RE drifted"
    # token-exact, so `undeclared-team` stays an owner as decisions.py reads it; a trailing full stop
    # is punctuation (`UNDECLARED.` is an un-adoption row), a dot before a name character is not
    token = "UNDECLARED(?![A-Za-z0-9_@-]|" + bs + ".[A-Za-z0-9_@-])"
    undeclared = '_UNDECLARED_RE = re.compile(r"^' + bs + "**" + bs + 's*" + _SUPERSEDES_PREFIX'
    undeclared += ' + r"MERGE OWNER:' + bs + "s*" + token + '", re.I'
    undeclared = "".join(undeclared.split())
    for name, src in flat.items():
        assert undeclared in src, f"{name}'s un-adoption token regex drifted"
    lookahead = "(?!UNDECLARED(?![A-Za-z0-9_@-]|\\.[A-Za-z0-9_@-]))"
    assert phrase + lookahead + capture in hook, "the hook's grammar drifted from its sources"
    assert lookahead not in du and lookahead not in dec, (
        "a source grew the hook's lookahead — reconcile deliberately, do not let it drift in"
    )


# --- T04a (spec 2026-09-29 hub-worktree cut-over, D1/D4/D5, V6/V7) -----------------------------


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env={"HOME": str(cwd), "PATH": "/usr/bin:/bin"},
    )
    return proc.stdout.strip()


def _git_repo(root: Path, owner: str | None, *, hub: bool = False) -> Path:
    """A real throwaway git repo carrying the Fabrik markers the hook keys on: the synced
    `scripts/docs_updater.py` (the adopt tool), a ledger with or without a MERGE OWNER row, and —
    for a stand-in hub — the synced manifest."""
    (root / "scripts").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "scripts/docs_updater.py").write_text("# stub\n", encoding="utf-8")
    if hub:
        (root / "scripts/fabrik_synced_manifest.py").write_text("# marker\n", encoding="utf-8")
    rows = "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
    if owner:
        rows += f"| D-001 | 2026-09-29 | a | MERGE OWNER: {owner} — adopted | y | z |\n"
    (root / "docs/DECISIONS.md").write_text(rows, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "scripts", "docs")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def _linked_worktree(repo: Path, name: str) -> Path:
    wt = repo / ".claude" / "worktrees" / name
    _git(repo, "worktree", "add", "-q", "-b", f"worktree-{name}", str(wt))
    return wt


def _common_dir(repo: Path) -> str:
    return _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")


def _pid_start(pid: int) -> int:
    raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return int(raw[raw.rindex(")") + 1 :].split()[19])


def _store(tmp_path: Path, rows: list[dict]) -> dict:
    """A whoami_agent.py identity store under tmp_path (its `AGENT_IDENTITY_FILE` override) —
    the real store is never touched."""
    path = tmp_path / "agent-identity.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return {"AGENT_IDENTITY_FILE": str(path)}


def test_a_single_session_in_an_unadopted_main_checkout_is_prompted_to_adopt(
    tmp_path: Path,
) -> None:
    # V7 / D1: the first window adopts before a second one opens. `--adopt` itself refuses below
    # two live sessions without `--single-window`, so the prompt must name that flag.
    repo = _git_repo(tmp_path / "opt" / "fresh", None)
    proc = _fake_proc(tmp_path, [("601", "claude", str(repo))])
    env = {"FABRIK_PROC_ROOT": str(proc)}
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), env)
    assert rc == 0
    assert "docs_updater.py --adopt" in out
    assert "--single-window" in out
    # a linked worktree is not where the merge owner adopts from
    wt = _linked_worktree(repo, "beta")
    rc, out = _run(wt, tmp_path, json.dumps({"cwd": str(wt)}), env)
    assert rc == 0 and "ORIENT" in out
    assert "docs_updater.py --adopt" not in out


def test_a_non_owner_session_in_a_main_checkout_is_told_to_move(tmp_path: Path) -> None:
    # D5 (a): owner `alpha`, this session resolved as `beta` through its whoami binding.
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    env = _store(tmp_path, [{"session_id": "sess-beta", "name": "beta", "at": 1}])
    payload = json.dumps({"cwd": str(repo), "session_id": "sess-beta"})
    rc, out = _run(repo, tmp_path, payload, env)
    assert rc == 0
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    assert len(move) == 1, out
    assert ".claude/worktrees/beta" in move[0]
    assert "conversation follows" in move[0]
    assert "`alpha`" in move[0]


def test_the_move_line_stays_silent_where_it_does_not_apply(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    # the owner itself stays in the main checkout
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "alpha"})
    assert rc == 0 and "ORIENT" in out
    assert "EnterWorktree" not in out
    # a non-owner already in its linked worktree
    wt = _linked_worktree(repo, "beta")
    rc, out = _run(wt, tmp_path, json.dumps({"cwd": str(wt)}), {"CLAUDE_AGENT": "beta"})
    assert rc == 0 and "ORIENT" in out
    assert "EnterWorktree" not in out
    # a project with no merge owner
    bare = _git_repo(tmp_path / "opt" / "unadopted", None)
    rc, out = _run(bare, tmp_path, json.dumps({"cwd": str(bare)}), {"CLAUDE_AGENT": "beta"})
    assert rc == 0 and "ORIENT" in out
    assert "EnterWorktree" not in out


def test_an_unnamed_session_is_told_to_bind_first_then_move(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo), "session_id": "nobody"}))
    assert rc == 0
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    assert len(move) == 1, out
    assert "python3 /opt/fabrik/scripts/whoami_agent.py --as <name>" in move[0]
    assert "bind first" in move[0]
    assert ".claude/worktrees/<name>" in move[0]


def test_the_hub_main_checkout_tells_a_non_owner_to_move(tmp_path: Path) -> None:
    # D5 (a) reaches the hub: the old manifest-in-cwd early returns hid every advisory there.
    hub = _git_repo(tmp_path / "opt" / "hubrepo", "infra", hub=True)
    env = {**_hub_env(hub), "CLAUDE_AGENT": "fleet"}
    rc, out = _run(hub, tmp_path, json.dumps({"cwd": str(hub)}), env)
    assert rc == 0
    assert "Governance (HUB)" in out
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    assert len(move) == 1, out
    assert ".claude/worktrees/fleet" in move[0] and "`infra`" in move[0]


def test_a_hub_worktree_is_the_hub_and_a_manifest_carrying_project_is_not(
    tmp_path: Path,
) -> None:
    # D4: identity is the manifest AND the git common dir's parent being the hub path — the rule
    # of final_gate.py::_is_hub and check_vendored_drift.py::_is_hub.
    hub = _git_repo(tmp_path / "opt" / "hubrepo", None, hub=True)
    wt = _linked_worktree(hub, "intel")
    rc, out = _run(wt, tmp_path, json.dumps({"cwd": str(wt)}), _hub_env(hub))
    assert rc == 0
    assert "Governance (HUB)" in out
    # the mirror: a repo that merely carries the manifest has its OWN common dir
    other = _git_repo(tmp_path / "opt" / "impostor", None, hub=True)
    rc, out = _run(other, tmp_path, json.dumps({"cwd": str(other)}), _hub_env(hub))
    assert rc == 0 and "ORIENT" in out
    assert "Governance (HUB)" not in out


def test_live_whoami_bindings_are_listed_and_a_dead_pid_is_not(tmp_path: Path) -> None:
    # V6: the COBRA counter to binding yourself as the merge owner is that everyone sees who holds
    # which name. Only rows whose pid is live (same start time) and whose scope is THIS repo.
    repo = _git_repo(tmp_path / "opt" / "bound", "alpha")
    common = _common_dir(repo)
    dead = subprocess.Popen(["true"])
    dead.wait()
    me, parent = os.getpid(), os.getppid()
    live = {"toplevel": common}
    rows = [
        {"session_id": "s1", "name": "alpha", "pid": me, "pid_start": _pid_start(me), **live},
        {
            "session_id": "s2",
            "name": "beta",
            "pid": parent,
            "pid_start": _pid_start(parent),
            **live,
        },
        {"session_id": "s3", "name": "gamma", "pid": dead.pid, "pid_start": 1, **live},
        {
            "session_id": "s4",
            "name": "delta",
            "pid": me,
            "pid_start": _pid_start(me),
            "toplevel": str(tmp_path / "elsewhere" / ".git"),
        },
        {"session_id": "s5", "name": "epsilon", "pid": me, "pid_start": _pid_start(me) + 1, **live},
    ]
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), _store(tmp_path, rows))
    assert rc == 0
    line = [ln for ln in out.splitlines() if "whoami` bindings" in ln]
    assert len(line) == 1, out
    assert "`alpha`" in line[0] and "`beta`" in line[0]
    for gone in ("gamma", "delta", "epsilon"):
        assert gone not in line[0], gone
    assert "CLAUDE_AGENT" in line[0], "the stated limit: launch-named sessions write no binding"
    # the same bindings are visible from a linked worktree of the repo (one common dir)
    wt = _linked_worktree(repo, "beta")
    rc, out = _run(wt, tmp_path, json.dumps({"cwd": str(wt)}), _store(tmp_path, rows))
    assert rc == 0
    assert any("`alpha`" in ln and "whoami` bindings" in ln for ln in out.splitlines())


def test_the_move_line_owner_agrees_with_decisions_py_on_a_deep_ledger(tmp_path: Path) -> None:
    # The hook reads the owner in-process (a `decisions.py --merge-owner` subprocess costs as much
    # as the whole hook — measured). Its answer must be decisions.py's: the WHOLE ledger, highest id
    # wins, so an owner row sunk far below a 64 KB window still counts (the hub ledger is
    # newest-first and ~750 KB).
    repo = _git_repo(tmp_path / "opt" / "deep", None)
    filler = "| D-%03d | 2026-09-16 | w | routine row | y | z |\n"
    (repo / "docs/DECISIONS.md").write_text(
        "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
        + "".join(filler % i for i in range(1, 2000))
        + "| D-2001 | 2026-09-16 | a | MERGE OWNER: deepowner | y | z |\n"
        + "".join(filler % i for i in range(3000, 5000)),
        encoding="utf-8",
    )
    ref = subprocess.run(
        [sys.executable, str(FABRIK / "scripts/decisions.py"), "--merge-owner", str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert ref.stdout.strip() == "deepowner"
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "beta"})
    assert rc == 0
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    assert len(move) == 1 and "`deepowner`" in move[0], out


# --- T04a fixup (wave-3 review) ------------------------------------------------------------------

_HDR = "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
_ALICE = "| D-001 | d | a | MERGE OWNER: alice | y | z |\n"


@pytest.mark.parametrize(
    "rows",
    [
        # an escaped pipe in the WHEN cell: the owner cell is `a`, so alice stays the owner
        _ALICE + "| D-002 | d \\| x | MERGE OWNER: bob | y | z |\n",
        # an escaped pipe in the WHO cell: the owner cell IS `MERGE OWNER: bob`
        _ALICE + "| D-002 | d | a \\| b | MERGE OWNER: bob | y | z |\n",
        # `\|` inside a code span is still cell content
        _ALICE + "| D-002 | d | `a\\|b` | MERGE OWNER: carol | y | z |\n",
        # a markdown-escaped name decodes to `bob_x`
        "| D-001 | d | a | MERGE OWNER: bob\\_x | y | z |\n",
        # an un-adoption row: last row wins, so nobody owns it
        _ALICE + "| D-002 | d | a | MERGE OWNER: UNDECLARED — un-adopted | y | z |\n",
        # a code span opened in the WHO cell runs into the owner cell: `\_` inside a span is NOT
        # unescaped, so the name stops at the backslash (decisions.py answers `a`, not `a_b`)
        "| D-002 | d | `x | MERGE OWNER: a\\_b` | y | z |\n",
        # an owner NAME that merely starts with the word: decisions.py captures the whole token
        _ALICE + "| D-002 | d | a | MERGE OWNER: undeclared-team | y | z |\n",
    ],
    ids=[
        "pipe-in-when",
        "pipe-in-who",
        "code-span-pipe",
        "escaped-name",
        "undeclared-last",
        "code-span-backslash",
        "owner-named-undeclared-team",
    ],
)
def test_the_owner_reader_agrees_with_decisions_py(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: str
) -> None:
    repo = _git_repo(tmp_path / "opt" / "parity", None)
    (repo / "docs/DECISIONS.md").write_text(_HDR + rows, encoding="utf-8")
    # docs_updater decodes the same GFM escapes (W-076ff4a9 ported `_ledger_cells`), so it is held
    # to the same answer over the same escaped-pipe / code-span / escaped-name ledgers
    monkeypatch.syspath_prepend(str(FABRIK / "scripts"))
    import docs_updater as du

    monkeypatch.setattr(du, "PROJECT_ROOT", repo)
    got = du.read_merge_owner()
    ref = subprocess.run(
        [sys.executable, str(FABRIK / "scripts/decisions.py"), "--merge-owner", str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    want = ref.stdout.strip()
    # decisions.py prints `UNDECLARED` at rc 3 for "none" — no row, or an un-adoption row winning
    want = "" if want == "UNDECLARED" else want
    assert (got[0] if got else "") == want, "docs_updater.read_merge_owner"
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "zed"})
    assert rc == 0 and "ORIENT" in out
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    if want:
        assert len(move) == 1 and f"merge owner is `{want}`" in move[0], (want, out)
    else:
        assert move == [], out
        assert "docs_updater.py --adopt" in out


@pytest.mark.parametrize(
    ("row", "owner"),
    [
        # a sentence period ends the token: an un-adoption row written as prose is still one
        ("MERGE OWNER: UNDECLARED.", ""),
        # a period followed by a name character is part of a name, so this one is an owner
        ("MERGE OWNER: UNDECLARED.team", "UNDECLARED.team"),
    ],
    ids=["undeclared-full-stop", "owner-named-undeclared-dot-team"],
)
def test_a_full_stop_after_undeclared_is_punctuation_not_a_name(
    tmp_path: Path, row: str, owner: str
) -> None:
    """A human's un-adoption row ending in a full stop must not read as an owner called
    `UNDECLARED.` (decisions.py once captured it as one; since W-076ff4a9 all three readers share
    the token regex, which the parity test below executes)."""
    repo = _git_repo(tmp_path / "opt" / "stop", None)
    (repo / "docs/DECISIONS.md").write_text(
        _HDR + _ALICE + f"| D-002 | d | a | {row} | y | z |\n", encoding="utf-8"
    )
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "zed"})
    assert rc == 0 and "ORIENT" in out
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    if owner:
        assert len(move) == 1 and f"merge owner is `{owner}`" in move[0], out
    else:
        assert move == [], out
        assert "docs_updater.py --adopt" in out


# --- W-076ff4a9: ONE selection rule in three readers -----------------------------------------
# The ledger's header says row POSITION is a convention nothing reads, and a changed decision is a
# NEW row whose what-cell OPENS `supersedes D-NNN:`. So the merge owner is the highest-id matching
# row, wherever it sits; all three readers are executed over the same fixtures and must agree.

_A1 = "| D-001 | x | op | MERGE OWNER: alpha | y | z |\n"
_BIG_FILL = "".join(
    f"| D-{i:04d} | 2026-09-16 | w | routine row | y | z |\n" for i in range(100, 3100)
)


def _row2(what: str, rid: str = "D-002") -> str:
    return f"| {rid} | x | op | {what} | y | z |\n"


# Every opening spelling the hub ledger's real superseding rows use (a grep of docs/DECISIONS.md
# for what-cells opening `supersedes`, 2026-10-01: 39 of 463 rows): `:` or `.` closes the clause,
# `**` may wrap it, any case, and a qualifier may sit between the id and the close.
_SUPERSEDES_SPELLINGS = [
    "**supersedes D-001:** MERGE OWNER: beta",
    "**supersedes D-001.** MERGE OWNER: beta",
    "**supersedes D-001's scope:** MERGE OWNER: beta",
    "**Supersedes D-001 on its WHY clause:** MERGE OWNER: beta",
    "**SUPERSEDES D-001 ON THE MECHANISM:** MERGE OWNER: beta",
    "supersedes D-001 (delegation clause only): MERGE OWNER: beta",
    "**Supersedes D-001 (2) and (5).** MERGE OWNER: beta",
    "**Supersedes D-000, D-001 and D-003:** MERGE OWNER: beta",
    "supersedes D-001: **MERGE OWNER: beta**",
]

_BIG_OWNER = _A1 + _BIG_FILL + _row2("MERGE OWNER: beta", "D-9000") + _BIG_FILL
_BIG_UNDECLARED = _A1 + _BIG_FILL + _row2("MERGE OWNER: UNDECLARED", "D-9000") + _BIG_FILL

_OWNER_CASES = [
    ("higher-id-above", _row2("MERGE OWNER: beta") + _A1, "beta"),
    ("higher-id-below", _A1 + _row2("MERGE OWNER: beta", "D-010"), "beta"),
    ("undeclared-highest-id", _row2("MERGE OWNER: UNDECLARED — un-adopted") + _A1, ""),
    ("undeclared-via-supersedes", _row2("SUPERSEDES D-001. MERGE OWNER: UNDECLARED.") + _A1, ""),
    (
        "undeclared-lower-id-is-history",
        _row2("MERGE OWNER: alpha", "D-003") + _row2("MERGE OWNER: UNDECLARED"),
        "alpha",
    ),
    # an escaped pipe in an EARLIER cell of the winning row: GFM makes it content, so the what
    # cell is still column 4 (a plain `|` split read `op` there and fell back to alpha)
    ("escaped-pipe-winner", "| D-002 | x \\| y | op | MERGE OWNER: beta | y | z |\n" + _A1, "beta"),
    # the phrase MID-prose is never an owner row, supersedes clause or not: alpha stands
    ("mid-prose-after-colon", _row2("supersedes D-001: the old MERGE OWNER: beta") + _A1, "alpha"),
    ("mid-prose-in-qualifier", _row2("supersedes D-001 on the MERGE OWNER: beta") + _A1, "alpha"),
    ("mid-prose-no-supersedes", _row2("we noted MERGE OWNER: beta") + _A1, "alpha"),
    # a >128 KB ledger whose winning row sits in the MIDDLE, outside any 64 KB head/tail window
    ("big-ledger-mid-owner", _BIG_OWNER, "beta"),
    ("big-ledger-mid-undeclared", _BIG_UNDECLARED, ""),
] + [(f"supersedes-{i}", _row2(w) + _A1, "beta") for i, w in enumerate(_SUPERSEDES_SPELLINGS)]


def test_the_big_fixtures_really_exceed_both_windows() -> None:
    for rows in (_BIG_OWNER, _BIG_UNDECLARED):
        size = len((_HDR + rows).encode())
        mid = (_HDR + rows).encode().index(b"| D-9000 |")
        assert size > 2 * 64 * 1024 and 64 * 1024 < mid < size - 64 * 1024, (size, mid)


@pytest.mark.parametrize(
    ("rows", "owner"), [c[1:] for c in _OWNER_CASES], ids=[c[0] for c in _OWNER_CASES]
)
def test_the_three_owner_readers_pick_the_highest_id_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: str, owner: str
) -> None:
    import importlib.util

    repo = tmp_path / "opt" / "parityrepo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs/DECISIONS.md").write_text(_HDR + rows, encoding="utf-8")

    spec = importlib.util.spec_from_file_location("session_orient_w076", HOOK)
    assert spec and spec.loader
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    monkeypatch.syspath_prepend(str(FABRIK / "scripts"))
    import docs_updater as du

    assert Path(du.__file__).resolve() == (FABRIK / "scripts/docs_updater.py").resolve()
    monkeypatch.setattr(du, "PROJECT_ROOT", repo)

    ref = subprocess.run(
        [sys.executable, str(FABRIK / "scripts/decisions.py"), "--merge-owner", str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (ref.returncode, ref.stdout.strip()) == ((0, owner) if owner else (3, "UNDECLARED"))
    got = du.read_merge_owner()
    assert (got[0] if got else "") == owner, "docs_updater.read_merge_owner"
    assert hook._ledger_merge_owner(str(repo)) == owner, "hook move-line reader"
    # the identity line's reader, observed through the hook's real output (no CLAUDE_AGENT set)
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}))
    assert rc == 0 and "ORIENT" in out
    if owner:
        assert f"DECLARES merge owner `{owner}`" in out, "hook identity line"
    else:
        assert "DECLARES merge owner" not in out, "hook identity line"


def _instruction_lines(out: str) -> list[str]:
    marks = ("whoami_agent.py --as", "claude --worktree", "EnterWorktree")
    return [ln for ln in out.splitlines() if any(m in ln for m in marks)]


def test_an_unnamed_session_in_a_shared_adopted_checkout_gets_one_instruction(
    tmp_path: Path,
) -> None:
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    proc = _fake_proc(tmp_path, [("701", "claude", str(repo)), ("702", "claude", str(repo))])
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"FABRIK_PROC_ROOT": str(proc)})
    assert rc == 0
    lines = _instruction_lines(out)
    assert len(lines) == 1, lines
    assert "EnterWorktree" in lines[0] and "whoami_agent.py --as" in lines[0]
    assert "CLAUDE_AGENT is UNSET" not in out


def test_a_whoami_bound_session_is_not_also_told_it_is_unset(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    env = _store(tmp_path, [{"session_id": "sess-beta", "name": "beta", "at": 1}])
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo), "session_id": "sess-beta"}), env)
    assert rc == 0
    assert "CLAUDE_AGENT is UNSET" not in out
    lines = _instruction_lines(out)
    assert len(lines) == 1 and "You are `beta`" in lines[0], lines


def test_an_invalid_claude_agent_is_unnamed_to_every_advisory(tmp_path: Path) -> None:
    # `ALPHA` fails whoami_agent.py's [a-z0-9-]{1,32}: one validity test, in every bullet.
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    wt = _linked_worktree(repo, "beta")
    rc, out = _run(wt, tmp_path, json.dumps({"cwd": str(wt)}), {"CLAUDE_AGENT": "ALPHA"})
    assert rc == 0
    assert "CLAUDE_AGENT is UNSET" in out and "not to a valid" in out
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "ALPHA"})
    assert rc == 0
    lines = _instruction_lines(out)
    assert len(lines) == 1 and "bind first" in lines[0], lines


def test_the_general_hub_env_var_cannot_make_a_project_the_hub(tmp_path: Path) -> None:
    # `FABRIK_HUB_ROOT` belongs to command_run.py; and no seam value can make a manifest-less
    # repo the hub, because the manifest is checked before the path.
    repo = _git_repo(tmp_path / "opt" / "project", None)
    env = {"FABRIK_HUB_ROOT": str(repo), "FABRIK_ORIENT_HUB_ROOT": str(repo)}
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), env)
    assert rc == 0 and "ORIENT" in out
    assert "Governance (HUB)" not in out


def test_an_owner_differing_only_in_case_is_not_told_to_move(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "cased", "Alpha")
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "alpha"})
    assert rc == 0 and "ORIENT" in out
    assert "EnterWorktree" not in out


def test_the_hub_adopt_prompt_fires_at_two_sessions_without_single_window(
    tmp_path: Path,
) -> None:
    hub = _git_repo(tmp_path / "opt" / "hubrepo", None, hub=True)
    proc = _fake_proc(tmp_path, [("801", "claude", str(hub)), ("802", "claude", str(hub))])
    env = {**_hub_env(hub), "FABRIK_PROC_ROOT": str(proc)}
    rc, out = _run(hub, tmp_path, json.dumps({"cwd": str(hub)}), env)
    assert rc == 0
    assert "Governance (HUB)" in out
    adopt = [ln for ln in out.splitlines() if "docs_updater.py --adopt" in ln]
    assert len(adopt) == 1, out
    assert "--single-window" not in adopt[0]


def _live_row(sid: str, name: str, common: str, **extra: object) -> dict:
    me = os.getpid()
    row = {"session_id": sid, "name": name, "pid": me, "pid_start": _pid_start(me)}
    row.update({"toplevel": common, **extra})
    return row


def _bindings(out: str) -> str:
    lines = [ln for ln in out.splitlines() if "whoami` bindings" in ln]
    assert len(lines) <= 1, lines
    return lines[0] if lines else ""


def test_a_live_binding_older_than_the_store_tail_is_still_listed(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "bigstore", "alpha")
    common = _common_dir(repo)
    rows = [_live_row("s-old", "oldtimer", common)]
    dead = {"pid": 999999999, "pid_start": 1, "toplevel": common}
    rows += [{"session_id": f"d{i}", "name": "dead", **dead} for i in range(6000)]  # > 256 KB
    env = _store(tmp_path, rows)
    assert Path(env["AGENT_IDENTITY_FILE"]).stat().st_size > 256 * 1024
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), env)
    assert rc == 0
    assert "`oldtimer`" in _bindings(out), out


def test_a_cut_store_never_reads_its_partial_first_line(tmp_path: Path) -> None:
    # Past the 4 MB cap the tail is read, and the line the cut lands in is dropped: here the cut
    # falls exactly on a `{` whose suffix — and the suffix one byte earlier, a space — is a valid
    # live row inside an otherwise invalid line, so any reader that keeps the partial line lists it.
    repo = _git_repo(tmp_path / "opt" / "cutstore", "alpha")
    common = _common_dir(repo)
    cap = 4 * 1024 * 1024
    ghost = json.dumps(_live_row("s-ghost", "ghost", common))
    last = json.dumps(_live_row("s-last", "lastone", common)) + "\n"
    room = cap - len(ghost) - 1 - len(last)
    filler = ("x" * 999 + "\n") * (room // 1000)
    rest = room - len(filler)
    filler += ("y" * (rest - 1) + "\n") if rest else ""
    body = "garbage " + ghost + "\n" + filler + last
    assert body[-cap:].startswith(ghost) and body[-cap - 1] == " "
    path = tmp_path / "agent-identity.jsonl"
    path.write_text(body, encoding="utf-8")
    env = {"AGENT_IDENTITY_FILE": str(path)}
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), env)
    assert rc == 0
    line = _bindings(out)
    assert "`lastone`" in line, out
    assert "ghost" not in line


def test_a_store_cut_on_a_line_start_keeps_that_row(tmp_path: Path) -> None:
    # The mirror of the partial-line test: when the 4 MB cut lands exactly on a line start, the
    # row that starts there is whole and must be kept (the reader seeks one byte before the cut).
    repo = _git_repo(tmp_path / "opt" / "edgestore", "alpha")
    common = _common_dir(repo)
    cap = 4 * 1024 * 1024
    edge = json.dumps(_live_row("s-edge", "edgerow", common)) + "\n"
    last = json.dumps(_live_row("s-last", "lastone", common)) + "\n"
    room = cap - len(edge) - len(last)
    filler = ("x" * 999 + "\n") * (room // 1000)
    rest = room - len(filler)
    filler += ("y" * (rest - 1) + "\n") if rest else ""
    body = "z" * 100 + "\n" + edge + filler + last
    assert body[-cap:].startswith(edge) and body[-cap - 1] == "\n"
    path = tmp_path / "agent-identity.jsonl"
    path.write_text(body, encoding="utf-8")
    env = {"AGENT_IDENTITY_FILE": str(path)}
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), env)
    assert rc == 0
    line = _bindings(out)
    assert "`edgerow`" in line and "`lastone`" in line, out


def _charter_bullet(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if "by whoami" in ln]


def test_a_whoami_only_hub_session_learns_it_has_no_charter(tmp_path: Path) -> None:
    # T04a-11: a hub session bound by whoami with no CLAUDE_AGENT has no role charter and no beat
    # routing (both read the env var only), so it is told so — without a "bind now" remedy.
    hub = _git_repo(tmp_path / "opt" / "hubrepo", None, hub=True)
    env = {**_hub_env(hub), **_store(tmp_path, [{"session_id": "s-infra", "name": "infra"}])}
    rc, out = _run(hub, tmp_path, json.dumps({"cwd": str(hub), "session_id": "s-infra"}), env)
    assert rc == 0
    lines = _charter_bullet(out)
    assert len(lines) == 1, out
    assert "`infra`" in lines[0] and "charter" in lines[0] and "beat routing" in lines[0]
    assert "CLAUDE_AGENT=infra claude" in lines[0]
    assert "bind" not in lines[0].lower()
    assert "this hub session is UNNAMED" not in out


def test_a_whoami_only_worktree_session_learns_it_has_no_charter(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    wt = _linked_worktree(repo, "beta")
    env = _store(tmp_path, [{"session_id": "s-beta", "name": "beta"}])
    rc, out = _run(wt, tmp_path, json.dumps({"cwd": str(wt), "session_id": "s-beta"}), env)
    assert rc == 0
    lines = _charter_bullet(out)
    assert len(lines) == 1, out
    assert "`beta`" in lines[0] and "charter" in lines[0]
    assert "CLAUDE_AGENT=beta claude" in lines[0]
    assert "beat routing" not in lines[0], "beat routing is the hub's alone"
    assert "bind" not in lines[0].lower()
    assert "CLAUDE_AGENT is UNSET and" not in out


def test_malformed_binding_rows_are_skipped(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "badrows", "alpha")
    common = _common_dir(repo)
    rows = [
        _live_row("s-ok", "okrow", common),
        {"session_id": "s-bool", "name": "boolpid", "pid": True, "toplevel": common},
        _live_row(5, "intsid", common),  # type: ignore[arg-type]
        _live_row("s-str", "strpid", common, pid=str(os.getpid())),
    ]
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), _store(tmp_path, rows))
    assert rc == 0
    line = _bindings(out)
    assert "`okrow`" in line, out
    for bad in ("boolpid", "intsid", "strpid"):
        assert bad not in line, bad


def test_a_pid_only_row_is_live_and_the_list_is_capped_at_twelve(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path / "opt" / "manyrows", "alpha")
    common = _common_dir(repo)
    rows = [_live_row(f"s{i:02d}", f"n{i:02d}", common) for i in range(12)]
    rows.append({"session_id": "s-pidonly", "name": "pidonly", "pid": os.getpid()})
    rows[-1]["toplevel"] = common  # a row written before start times existed
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), _store(tmp_path, rows))
    assert rc == 0
    line = _bindings(out)
    assert line.count("` (pid ") == 12, line
    assert "(+1 more)" in line
    # with one row fewer the pid-only row is shown by name
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), _store(tmp_path, rows[1:]))
    assert rc == 0
    assert "`pidonly`" in _bindings(out), out


def test_the_move_line_tells_the_mover_to_check_the_worktreeinclude_set(tmp_path: Path) -> None:
    """EnterWorktree applied `.worktreeinclude` in both hub moves (2026-09-30, Claude Code 2.1.280),
    but a mover must still check the gitignored set arrived — the move line says so, once."""
    repo = _git_repo(tmp_path / "opt" / "adopted", "alpha")
    rc, out = _run(repo, tmp_path, json.dumps({"cwd": str(repo)}), {"CLAUDE_AGENT": "beta"})
    assert rc == 0
    move = [ln for ln in out.splitlines() if "EnterWorktree" in ln]
    assert len(move) == 1 and "`.worktreeinclude` lists" in move[0], out
