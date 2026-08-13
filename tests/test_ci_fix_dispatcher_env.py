"""Behavior-Contract test — the CI-fix dispatcher is a resume-mesh AUTONOMOUS launcher.

Plan 2026-08-13-plan-1 Leg A seed: the dispatcher's `claude -p` workers are exactly the
population the @reboot sweep exists to revive, but nothing marked them (closer finding F1:
the marker population was empty box-wide). The dispatcher must export
CLAUDE_MESH_AUTONOMOUS=1 into its worker env so session_orient.py drops the persistent
`.autonomous` marker and a VM cut mid-fix is swept back to life.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "ci_fix_dispatcher", REPO / "scripts" / "ci_fix_dispatcher.py")
cfd = importlib.util.module_from_spec(spec)
sys.modules["ci_fix_dispatcher"] = cfd
spec.loader.exec_module(cfd)


def test_dispatch_env_marks_worker_autonomous(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kw):
        captured.update(kw)
        captured["cmd"] = cmd

        class P:
            returncode = 0

        return P()

    monkeypatch.setattr(cfd.subprocess, "run", fake_run)
    monkeypatch.setattr(cfd, "LOG_DIR", tmp_path)
    rc = cfd.dispatch(tmp_path, "brief", tmp_path / "w.log", dry_run=False)
    assert rc == 0
    env = captured.get("env")
    assert env is not None and env.get("CLAUDE_MESH_AUTONOMOUS") == "1", (
        "worker env must carry CLAUDE_MESH_AUTONOMOUS=1 (the sweep-eligibility marker gate)",
        captured.get("env"),
    )
    # the export must EXTEND the inherited env, never replace it (PATH etc. must survive)
    assert env.get("PATH"), "inherited env lost — dispatcher must copy os.environ"


def test_dry_run_spawns_nothing(tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("dry-run must not spawn")

    monkeypatch.setattr(cfd.subprocess, "run", boom)
    assert cfd.dispatch(tmp_path, "brief", tmp_path / "w.log", dry_run=True) == 0
