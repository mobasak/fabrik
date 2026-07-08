"""sandbox.py — the OS sandbox that confines run_command to the worktree.

Highest-risk guarantee: an allow-listed interpreter (``python``) CANNOT write outside
its worktree, even with an absolute path — the exact escape seen live 2026-07-06. These
tests pin (1) fail-closed behaviour when the sandbox is unavailable, (2) the wrap shape,
and (3) the real kernel-level containment (EROFS) when bwrap is present.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from subagents import AgentSpec, run_agents, sandbox
from subagents.tools import execute_tool

_HAVE = sandbox.sandbox_available()
requires_bwrap = pytest.mark.skipif(not _HAVE, reason="bubblewrap unavailable on host")

# The $HOME-based EROFS differential tests need a real, user-writable, non-tmp path (so the
# ro-bind EROFS is exercised, not the tmpfs mask). On a hardened/rootless CI runner where
# $HOME is read-only or sits under $TMPDIR, skip rather than fail for the wrong reason.
_HOME = Path.home()
_HOME_EROFS_OK = os.access(_HOME, os.W_OK) and not str(_HOME).startswith(
    tempfile.gettempdir()
)
requires_home_erofs = pytest.mark.skipif(
    not _HOME_EROFS_OK,
    reason="$HOME must be writable and outside the tmpfs'd temp dir for a real EROFS test",
)


def test_fail_closed_raises_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the platform can't sandbox, wrap_command REFUSES — never returns bare argv."""
    monkeypatch.setattr(sandbox, "sandbox_available", lambda: False)
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.wrap_command(["python3", "-c", "print(1)"], "/some/workdir")


def test_run_command_fails_closed_when_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """execute_tool(run_command) with sandbox on + no sandbox → ok=False, not executed."""
    monkeypatch.setattr(sandbox, "sandbox_available", lambda: False)
    res = execute_tool(
        "run_command",
        {"cmd": "python3 -c \"print(1)\""},
        workdir=str(tmp_path),
        sandbox_on=True,
    )
    assert res.ok is False
    assert "sandbox required" in (res.error or "")


def test_wrap_command_empty_argv_rejected() -> None:
    with pytest.raises(ValueError):
        sandbox.wrap_command([], "/w")


def test_preflight_refuses_tool_agent_when_unsandboxable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool-enabled + sandbox agent on a host without bwrap is refused UP FRONT —
    no worktree, no loop call, no spend — with an actionable error."""
    monkeypatch.setattr(sandbox, "sandbox_available", lambda: False)

    def _boom(**_kw: object) -> object:
        raise AssertionError("loop_fn must NOT run — pre-flight should short-circuit")

    specs = [
        AgentSpec(
            task="build it", model="x/y", tools_enabled=True, sandbox=True,
            owned_paths=["a/**"],
        )
    ]
    (r,) = run_agents(
        specs, repo=str(tmp_path), ledger_path=str(tmp_path / "l.jsonl"), loop_fn=_boom
    )
    assert r.status == "error"
    assert "sandbox unavailable" in (r.error or "")
    assert r.cost_usd in (None, 0)  # nothing spent


@requires_bwrap
def test_wrap_shape(tmp_path: Path) -> None:
    """The wrapped argv pins the SECURITY-load-bearing operands, not just token presence:
    the whole FS is `--ro-bind / /` (the basis of EROFS), the worktree is the writable
    `--bind`, network + namespaces are unshared, and `--` separates bwrap flags from argv."""
    wd = str(tmp_path)
    wrapped = sandbox.wrap_command(["pytest", "-q"], wd)
    assert wrapped[0] == "bwrap"
    # WHOLE filesystem read-only — a regressed `--ro-bind /etc /etc` must NOT pass.
    ro = wrapped.index("--ro-bind")
    assert wrapped[ro + 1 : ro + 3] == ["/", "/"]
    # EXACTLY ONE writable bind, and it's the worktree — a second `--bind <elsewhere>`
    # would be a new writable escape hatch, so pin the count too.
    assert wrapped.count("--bind") == 1
    b = wrapped.index("--bind")
    assert wrapped[b + 1 : b + 3] == [wd, wd]
    # isolation invariants
    for flag in ("--unshare-net", "--unshare-user", "--unshare-pid", "--die-with-parent"):
        assert flag in wrapped, flag
    # argv is passed after `--`, unmodified
    assert wrapped[-2:] == ["pytest", "-q"]
    assert "--" in wrapped and wrapped.index("--") == len(wrapped) - 3


@requires_bwrap
@requires_home_erofs
def test_sandbox_blocks_escape_that_would_otherwise_succeed(tmp_path: Path) -> None:
    """THE proof, revert-surviving: the SAME absolute-path write outside the worktree
    SUCCEEDS unsandboxed but is DENIED (EROFS) sandboxed. Target is under $HOME — a real,
    user-writable, NON-tmp path — so this exercises the `--ro-bind / /` EROFS guarantee
    (not the tmpfs mask, and not the trivial 'non-root can't write /' case that would pass
    even with the sandbox reverted)."""
    probe = _HOME / f".subagents_erofs_probe_{os.getpid()}"
    probe.unlink(missing_ok=True)
    try:
        # unsandboxed: the escape WORKS → confirms the command is genuinely capable of it
        # (this is what makes the test fail if the sandbox is reverted — both runs would write)
        off = execute_tool(
            "run_command",
            {"cmd": f"python3 -c \"open('{probe}','w').write('ESCAPED')\""},
            workdir=str(tmp_path),
            sandbox_on=False,
        )
        assert off.ok is True and probe.exists(), "precondition: write must succeed unsandboxed"
        probe.unlink()
        # sandboxed: the SAME escape is denied at the kernel; nothing lands on the host
        on = execute_tool(
            "run_command",
            {"cmd": f"python3 -c \"open('{probe}','w').write('ESCAPED')\""},
            workdir=str(tmp_path),
            sandbox_on=True,
        )
        assert on.ok is False  # EROFS → non-zero exit
        assert not probe.exists()  # host untouched
    finally:
        probe.unlink(missing_ok=True)


@requires_bwrap
@requires_home_erofs
def test_run_command_sandboxes_by_default(tmp_path: Path) -> None:
    """Containment happens by DEFAULT — no `sandbox_on` passed. Would fail (probe created,
    ok=True) if the default flipped to False anywhere in the chain. This is the only test
    that proves the *default* is safe, not just the explicit `sandbox_on=True`."""
    probe = _HOME / f".subagents_default_probe_{os.getpid()}"
    probe.unlink(missing_ok=True)
    try:
        res = execute_tool(
            "run_command",
            {"cmd": f"python3 -c \"open('{probe}','w').write('x')\""},
            workdir=str(tmp_path),  # NO sandbox_on → the default must sandbox
        )
        assert res.ok is False
        assert not probe.exists()
    finally:
        probe.unlink(missing_ok=True)


@requires_bwrap
def test_real_host_file_never_mutated(tmp_path: Path) -> None:
    """Complements the EROFS test by covering the OTHER containment mechanism — the
    **tmpfs mask**: a victim UNDER the temp dir is shadowed, so a write "succeeds" into the
    throwaway tmpfs yet the real host file is unchanged (read back on the host to prove it).
    Asserts only the host file, not ToolResult (the write may land in tmpfs = ok=True)."""
    shared = tmp_path / "shared"
    wt = shared / ".wt"
    wt.mkdir(parents=True)
    victim = shared / "victim.txt"
    victim.write_text("SURVIVE")

    execute_tool(
        "run_command",
        {"cmd": f"python3 -c \"open('{victim}','w').write('PWNED')\""},
        workdir=str(wt),
        sandbox_on=True,
    )
    assert victim.read_text() == "SURVIVE"  # real fs untouched, whatever the sandbox did


@requires_bwrap
def test_write_inside_worktree_succeeds(tmp_path: Path) -> None:
    """Legit work inside the worktree still works — the sandbox isn't a straitjacket."""
    ok = execute_tool(
        "run_command",
        {"cmd": "python3 -c \"open('made.txt','w').write('x')\""},
        workdir=str(tmp_path),
        sandbox_on=True,
    )
    assert ok.ok is True
    assert (tmp_path / "made.txt").read_text() == "x"


@requires_bwrap
def test_sandboxed_stdout_flows_back(tmp_path: Path) -> None:
    """A sandboxed command's stdout must flow back through bwrap into ToolResult.output
    (a `--new-session`/tty regression could break capture only under the sandbox)."""
    res = execute_tool(
        "run_command",
        {"cmd": "python3 -c \"print('SBX_MARKER')\""},
        workdir=str(tmp_path),
        sandbox_on=True,
    )
    assert res.ok is True
    assert "SBX_MARKER" in res.output


@requires_bwrap
def test_sandboxed_command_is_killed_at_timeout(tmp_path: Path) -> None:
    """The timeout must reap the SANDBOXED grandchild — a SIGKILL to the outer `bwrap`
    tears down the interpreter via `--unshare-pid` + `--die-with-parent`. (test_tools.py's
    timeout test runs unsandboxed; this covers the reaping the sandbox recipe relies on.)"""
    res = execute_tool(
        "run_command",
        {"cmd": 'python3 -c "import time; time.sleep(5)"'},
        workdir=str(tmp_path),
        timeout_s=0.5,
        sandbox_on=True,
    )
    assert res.ok is False
    assert res.error is not None and "timeout" in res.error.lower()


@requires_bwrap
def test_sandbox_off_escape_hatch_runs_unconfined(tmp_path: Path) -> None:
    """sandbox_on=False is the trusted escape hatch — it runs raw (no bwrap wrap)."""
    res = execute_tool(
        "run_command",
        {"cmd": "python3 -c \"print('trusted')\""},
        workdir=str(tmp_path),
        sandbox_on=False,
    )
    assert res.ok is True
    assert "trusted" in res.output
