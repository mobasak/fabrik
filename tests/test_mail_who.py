"""Behavior-contract tests for `mail.py who <agent>` (plan 2026-09-30-plan-1 T01b).

Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md § The delta 4, § Validation V3.

Everything is a FIXTURE: the session registry (`FABRIK_SESSIONS_ROOT`), the proc tree
(`FABRIK_PROC_ROOT`) and the whoami binding store (`AGENT_IDENTITY_FILE`) all live under tmp_path,
and the two repositories are REAL scratch git repos — the common-dir filter is only as good as the
git answer it reads, so it is never stubbed. The real ~/.claude and /proc are never read.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

_MAIL_PY = Path(__file__).resolve().parent.parent / "scripts" / "mail.py"


def _load_mail():
    spec = importlib.util.spec_from_file_location("fabrik_mail_who", _MAIL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mail = _load_mail()


def _git_init(path: Path) -> None:
    path.mkdir(parents=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(
        ["git", "init", "-q", "-b", "master", str(path)], check=True, env=env, timeout=60
    )


def _session(root: Path, proc: Path, pid: int, *, cwd: Path, name: str, sid: str,
             agent: str | None, alive: bool = True) -> None:
    (root / f"{pid}.json").write_text(
        json.dumps({"pid": pid, "sessionId": sid, "cwd": str(cwd), "name": name,
                    "messagingSocketPath": f"/tmp/fixture-{pid}.sock"}),
        encoding="utf-8",
    )
    if alive:
        (proc / str(pid)).mkdir()
        env = [b"PATH=/usr/bin", b"HOME=/nowhere"]
        if agent is not None:
            env.append(f"CLAUDE_AGENT={agent}".encode())
        (proc / str(pid) / "environ").write_bytes(b"\0".join(env) + b"\0")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    repo, other = tmp_path / "repo", tmp_path / "repo-other"  # prefix-sharing on purpose
    _git_init(repo)
    _git_init(other)
    sessions, proc = tmp_path / "sessions", tmp_path / "proc"
    sessions.mkdir()
    proc.mkdir()
    ident = tmp_path / "agent-identity.jsonl"
    monkeypatch.setenv("FABRIK_SESSIONS_ROOT", str(sessions))
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(ident))
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.chdir(repo)
    return {"repo": repo, "other": other, "sessions": sessions, "proc": proc, "ident": ident}


def test_mail_file_is_this_worktrees_copy():
    """W-83ff5917: the suite must exercise THIS tree's scripts/mail.py, not the main checkout's."""
    assert Path(mail.__file__).resolve() == _MAIL_PY


def test_who_finds_env_and_binding_sessions_in_this_repo_only(world, capsys):
    """V3: alpha by /proc CLAUDE_AGENT, beta by a whoami binding (last row wins); the
    prefix-sharing repo's session and a dead pid's stale registry file never ring."""
    repo, other = world["repo"], world["other"]
    s, p = world["sessions"], world["proc"]
    _session(s, p, 101, cwd=repo, name="fabrik-alpha", sid="sid-a", agent="alpha")
    _session(s, p, 102, cwd=repo / ".git", name="fabrik-beta", sid="sid-b", agent=None)
    # the third: same agents by BOTH sources, but under repo-other (a string prefix of nothing
    # that realpath-compares equal)
    _session(s, p, 103, cwd=other, name="other-both", sid="sid-o", agent="alpha")
    # a dead session bound to alpha: stale registry file, no /proc entry
    _session(s, p, 104, cwd=repo, name="dead-alpha", sid="sid-d", agent=None, alive=False)
    (s / "notes.txt").write_text("not a registry entry\n")
    (s / "105.json").write_text("{not json")
    rows = [
        {"session_id": "sid-b", "name": "gamma", "pid": 102},
        {"session_id": "sid-b", "name": "beta", "pid": 102},  # LAST row wins
        {"session_id": "sid-o", "name": "beta", "pid": 103},
        {"session_id": "sid-d", "name": "alpha", "pid": 104},
    ]
    world["ident"].write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    assert mail.main(["who", "alpha"]) == 0
    assert capsys.readouterr().out == "fabrik-alpha\n"
    assert mail.main(["who", "beta"]) == 0
    assert capsys.readouterr().out == "fabrik-beta\n"
    assert mail.main(["who", "gamma"]) == 0  # superseded binding
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("shape", ["absent", "unreadable", "a-file"])
def test_who_unreadable_or_absent_registry_prints_nothing_exit_zero(world, capsys, shape):
    """§ The delta 4: an unreadable or absent registry is an empty answer, never an error."""
    s = world["sessions"]
    _session(s, world["proc"], 101, cwd=world["repo"], name="fabrik-alpha", sid="sid-a",
             agent="alpha")
    if shape == "absent":
        for f in s.iterdir():
            f.unlink()
        s.rmdir()
    elif shape == "unreadable":
        if os.geteuid() == 0:
            pytest.skip("root reads a mode-000 directory")
        s.chmod(0)
    else:
        for f in s.iterdir():
            f.unlink()
        s.rmdir()
        s.write_text("a file where the registry dir should be\n")
    try:
        rc = mail.main(["who", "alpha"])
    finally:
        if shape == "unreadable":
            s.chmod(0o755)
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == ""
