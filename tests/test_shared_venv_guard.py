"""Behaviour graders for the shared-venv check in .claude/hooks/seat_guard.py (W-46d148b0).

A linked worktree's `.venv` is a symlink to the main checkout's venv (the synced settings'
`worktree.symlinkDirectories`), so a sync or install a worktree session runs into it rewrites the
runtime every agent of the repo shares (trade-intelligence 01M3RYGETKD5HQZRBTDF3EK3EK). The hook is
run as a process, hermetic (a bare PATH, no inherited uv or venv variables), on a tmp main checkout
whose linked worktree symlinks `.venv` — the layout the harness builds, not a mock.
Input domain: Bash command strings as an agent types them. Borrowed fixtures: none.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "seat_guard.py"
BARE_PATH = "/usr/bin:/bin"
TAG = "shared venv guard"


def _exe(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)


@pytest.fixture()
def tree(tmp_path: Path) -> dict[str, Path]:
    main = tmp_path / "repo"
    (main / ".venv" / "bin").mkdir(parents=True)
    for exe in ("python", "python3", "pip", "activate"):
        _exe(main / ".venv" / "bin" / exe)
    (main / "pyproject.toml").write_text("[project]\nname='x'\n")
    wt = main / ".claude" / "worktrees" / "agent-1"
    (wt / "sub").mkdir(parents=True)
    (wt / "pyproject.toml").write_text("[project]\nname='x'\n")
    (wt / ".venv").symlink_to(main / ".venv")
    other = tmp_path / "scratch" / "v"
    (other / "bin").mkdir(parents=True)
    for exe in ("python", "pip"):
        _exe(other / "bin" / exe)
    elsewhere = tmp_path / "other-project"
    elsewhere.mkdir()
    (elsewhere / "pyproject.toml").write_text("[project]\nname='y'\n")
    real_wt = main / ".claude" / "worktrees" / "agent-2"
    (real_wt / ".venv" / "bin").mkdir(parents=True)
    (real_wt / "pyproject.toml").write_text("[project]\nname='x'\n")
    return {"main": main, "wt": wt, "other": other, "elsewhere": elsewhere, "real_wt": real_wt}


def _hook(command: str, cwd: Path, *, env: dict | None = None, seat: bool = False) -> str:
    payload: dict = {
        "session_id": "sid-venv",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if seat:
        payload["agent_id"] = "agent-1"
        payload["agent_type"] = "fabrik-reviewer"
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": BARE_PATH, **(env or {})},
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _reason(out: str) -> str:
    if not out.strip():
        return ""
    spec = json.loads(out)["hookSpecificOutput"]
    return spec.get("permissionDecisionReason", "") if spec.get("permissionDecision") == "deny" else ""


def _refused(command: str, cwd: Path, **kw) -> bool:
    return _reason(_hook(command, cwd, **kw)).startswith(TAG)


def test_a_project_sync_from_a_linked_worktree_is_refused(tree: dict[str, Path]) -> None:
    wt = tree["wt"]
    for cmd in (
        "uv run pytest -q",
        "uv sync",
        "timeout 300 uv run --frozen pytest",
        "cd sub && uv add sqlalchemy",
        'bash -c "uv remove httpx"',
        "env A=1 uv run python -m pytest",
        "uv --color never sync",
        "uv --cache-dir /tmp/c run pytest",
        "uv run pytest --no-sync",
        "uv run --active pytest",
        "/usr/bin/env uv sync",
        "stdbuf -oL uv sync",
        "uv version --bump patch",
        "echo a#b ; uv sync",
        "UV_NO_SYNC=0 uv run pytest",
        # a valued option this uv does not know yet hides the verb: found anyway (fail-closed)
        "uv --some-future-option value sync",
        'flock /tmp/l -c "uv sync"',
        "flock -c 'uv sync' /tmp/l",
    ):
        assert _refused(cmd, wt), cmd
    # from the main checkout, a sync that lands in the worktree's shared venv
    assert _refused("uv sync --directory .claude/worktrees/agent-1", tree["main"])
    assert _refused("uv --project .claude/worktrees/agent-1 run pytest", tree["main"])


def test_an_install_into_the_shared_venv_is_refused(tree: dict[str, Path]) -> None:
    wt, main = tree["wt"], tree["main"]
    for cmd in (
        ".venv/bin/pip install requests",
        f"{main}/.venv/bin/python -m pip install -q pytest-timeout>=2.3.0",
        "uv pip install requests",
        "uv pip install --python .venv/bin/python requests",
        f"uv pip uninstall -y --python {main}/.venv/bin/python requests",
        "source .venv/bin/activate && pip install x",
        ". .venv/bin/activate && python -m pip install x",
        "uv run --no-sync pip install x",
        "echo x | xargs uv pip install",
        "uv venv --clear -p 3.12",
        "uv venv --clear 2>&1",
        "pip --python .venv/bin/python install x",
        "uv pip -q install foo",
        "uv pip --cache-dir /tmp/c install foo",
        ".venv/bin/python -W ignore -m pip install foo",
    ):
        assert _refused(cmd, wt), cmd
    assert _refused("pip install -e .", wt, env={"PATH": f"{wt}/.venv/bin:{BARE_PATH}"})
    assert _refused(".venv/bin/pip install -e .claude/worktrees/agent-1", main)


def test_forms_that_do_not_write_the_shared_venv_pass(tree: dict[str, Path]) -> None:
    wt = tree["wt"]
    for cmd in (
        "uv run --no-sync pytest -q",
        "UV_NO_SYNC=1 uv run pytest",
        "UV_NO_SYNC=1 bash -c 'uv run pytest'",
        "uv add --frozen httpx",
        "uv add --script x.py requests",
        ".venv/bin/python -c 'import pip' install",
        "uv sync --dry-run",
        "uv sync --check",
        "uv run --no-project --with pytest python -m pytest",
        "uv run -s script.py",
        "uv run --help",
        "uv venv",
        "uv venv --help",
        "uv pip list",
        "uv pip freeze",
        "uv lock",
        "uv tree",
        f"uv sync --project {tree['elsewhere']}",
        "pip install --target /tmp/t requests",
        ".venv/bin/pip install --dry-run requests",
        ".venv/bin/pip install --help",
        ".venv/bin/python -m pip list",
        ".venv/bin/python -m pytest -q",
        "uv run --no-sync pytest 2>&1 | tail -5",
    ):
        assert not _refused(cmd, wt), cmd


def test_other_venvs_and_unshared_checkouts_pass(tree: dict[str, Path]) -> None:
    wt, main, other = tree["wt"], tree["main"], tree["other"]
    assert not _refused(f"uv pip install --python {other}/bin/python x", wt)
    assert not _refused(f"{other}/bin/pip install x", wt)
    assert not _refused(f"uv venv --clear {other}", wt)
    assert not _refused(f"VIRTUAL_ENV={other} uv pip install x", wt)
    assert not _refused("uv sync", main)
    assert not _refused(".venv/bin/pip install -e .", main)
    assert not _refused("uv sync", tree["real_wt"])
    assert not _refused("cd ~/x && uv sync", wt)


def test_the_opt_in_is_inline_only(tree: dict[str, Path]) -> None:
    wt, main = tree["wt"], tree["main"]
    pin = f"uv pip install --python {main}/.venv/bin/python x==1.0"
    assert not _refused(f"FABRIK_SHARED_VENV_WRITE=1 {pin}", wt)
    assert not _refused(f"export FABRIK_SHARED_VENV_WRITE=1; {pin}", wt)
    assert not _refused(f"env FABRIK_SHARED_VENV_WRITE=1 {pin}", wt)
    assert not _refused(f"FABRIK_SHARED_VENV_WRITE=1 bash -c '{pin}'", wt)
    assert _refused(f"FABRIK_SHARED_VENV_WRITE=0 {pin}", wt)
    assert _refused(pin, wt, env={"FABRIK_SHARED_VENV_WRITE": "1"})
    assert _refused(f"bash -c 'export FABRIK_SHARED_VENV_WRITE=1' ; {pin}", wt)
    assert not _refused(f"FABRIK_SHARED_VENV_WRITE=TRUE {pin}", wt)
    assert _refused(f"FABRIK_SHARED_VENV_WRITE= {pin}", wt)
    assert _refused(f"export FABRIK_SHARED_VENV_WRITE=1; unset FABRIK_SHARED_VENV_WRITE; {pin}", wt)
    assert _refused(f"(export FABRIK_SHARED_VENV_WRITE=1); {pin}", wt)  # a subshell's export dies


def test_text_naming_the_verbs_is_not_a_call(tree: dict[str, Path]) -> None:
    wt = tree["wt"]
    for cmd in (
        "cat > notes.md <<'EOF'\nuv sync\npip install x\nEOF",
        "echo 'uv run pytest'",
        "command grep -rn 'uv sync' docs/",
        "# uv sync",
        "ls  # then ; uv sync",
        "command -v uv",
        "echo 'unclosed",
    ):
        assert not _refused(cmd, wt), cmd
    assert _refused("echo '#' ; uv sync", wt)


def test_the_deny_is_a_json_permission_decision(tree: dict[str, Path]) -> None:
    for seat in (False, True):
        spec = json.loads(_hook("uv sync", tree["wt"], seat=seat))["hookSpecificOutput"]
        assert spec["permissionDecision"] == "deny"
        reason = spec["permissionDecisionReason"]
        assert reason.startswith(TAG)
        assert "--no-sync" in reason and "FABRIK_SHARED_VENV_WRITE=1" in reason
        assert os.path.realpath(tree["main"] / ".venv") in reason
    # the kill and git checks stay seat-only: a lead in the same tree is not refused them
    for cmd in ("pkill -f x", "git reset --hard"):
        assert _reason(_hook(cmd, tree["wt"])) == "", cmd
    # the tokeniser fixes reach the seat checks too
    scratch = "/tmp/claude-1000/-opt-x/sid-venv/scratchpad"
    for cmd in (
        "echo a#b ; git reset --hard",
        "/usr/bin/env pkill -f x",
        "kill 0 > /dev/null",  # a spaced argument is not a redirect's fd number
        "flock -c 'git reset --hard' /tmp/x.lock",
    ):
        reason = _reason(_hook(cmd, Path("/opt/fabrik"), seat=True))
        assert reason.startswith("seat guard"), cmd
    label = _reason(_hook(".venv/bin/python -m pip install x", tree["wt"]))
    assert "`python -m pip install`" in label, label
    assert _reason(_hook(f"cd {scratch} && kill 1234 2>/dev/null", Path("/opt/fabrik"), seat=True)) == ""
