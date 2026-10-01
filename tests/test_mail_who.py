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
import signal
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


BTIME = 1_700_000_000  # the fixture boot time (epoch seconds) written to <proc>/stat
FILE_AT = BTIME + 10_000  # every registry file's mtime
CLK = os.sysconf("SC_CLK_TCK")
# argv[0] of a live VS Code session, read from this box's own process tree (/proc/<ppid>/cmdline)
CLAUDE_ARGV0 = (
    "/home/u/.vscode-server/extensions/anthropic.claude-code-2.1.280-linux-x64/resources/"
    "native-binary/claude"
)


def _session(
    root: Path,
    proc: Path,
    pid: int,
    *,
    cwd: Path | str,
    name: str,
    sid: str,
    agent: str | None,
    alive: bool = True,
    born: int | None = 5_000,
    pad: int = 0,
    argv: tuple[str, ...] = (CLAUDE_ARGV0, "--output-format", "stream-json"),
    body: str | None = None,
) -> Path:
    """One registry entry + its fake /proc/<pid>. ``born`` = process start, seconds after BTIME
    (the file is written at BTIME+10000, so 5000 is an original session and 20000 a recycled
    pid); None writes no stat file. ``argv`` is the pid's cmdline; ``body`` replaces the JSON."""
    entry = root / f"{pid}.json"
    entry.write_text(
        body
        if body is not None
        else json.dumps(
            {
                "pid": pid,
                "sessionId": sid,
                "cwd": str(cwd),
                "name": name,
                "messagingSocketPath": f"/tmp/fixture-{pid}.sock",
            }
        )
        + " " * pad,
        encoding="utf-8",
    )
    os.utime(entry, (FILE_AT, FILE_AT))
    if alive:
        (proc / str(pid)).mkdir()
        env = [b"PATH=/usr/bin", b"HOME=/nowhere"]
        if agent is not None:
            env.append(f"CLAUDE_AGENT={agent}".encode())
        (proc / str(pid) / "environ").write_bytes(b"\0".join(env) + b"\0")
        (proc / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        if born is not None:
            # field 22 (starttime, clock ticks since boot); a comm with a space and a ')' inside
            fields = ["S"] + ["0"] * 18 + [str(born * CLK)] + ["0"] * 5
            (proc / str(pid) / "stat").write_text(f"{pid} (claude) x) {' '.join(fields)}\n")
    return entry


@pytest.fixture()
def world(tmp_path, monkeypatch):
    repo, other = tmp_path / "repo", tmp_path / "repo-other"  # prefix-sharing on purpose
    _git_init(repo)
    _git_init(other)
    sessions, proc = tmp_path / "sessions", tmp_path / "proc"
    sessions.mkdir()
    proc.mkdir()
    (proc / "stat").write_text(f"cpu  1 2 3 4\nintr 0\nctxt 0\nbtime {BTIME}\nprocesses 1\n")
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
    _session(
        s, world["proc"], 101, cwd=world["repo"], name="fabrik-alpha", sid="sid-a", agent="alpha"
    )
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


def _bind(world, *rows: tuple[str, str]) -> None:
    world["ident"].write_text(
        "".join(json.dumps({"session_id": s, "name": n}) + "\n" for s, n in rows),
        encoding="utf-8",
    )


def _who(agent: str, capsys) -> str:
    assert mail.main(["who", agent]) == 0
    return capsys.readouterr().out


class _BlockedError(BaseException):
    """Raised by the alarm. ⚠️ NOT TimeoutError: that is an OSError, which the per-entry skip
    swallows — the FIFO mutant then passed after the timeout instead of failing."""


@pytest.fixture()
def alarm():
    """A blocking read (a FIFO opened for reading) fails the test instead of hanging it."""

    def _boom(*_a):
        raise _BlockedError("who blocked on a registry entry")

    old = signal.signal(signal.SIGALRM, _boom)
    signal.alarm(5)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


def test_who_skips_hostile_entries_beside_a_good_one(world, capsys, alarm, tmp_path):
    """Review item 4 + the FIFO / mode-000 shapes: every per-entry probe sits inside the
    per-entry skip, so one bad entry never blocks, never aborts, and never hides the good one."""
    if os.geteuid() == 0:
        pytest.skip("root reads mode-000 files")
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 101, cwd=repo, name="fabrik-alpha", sid="sid-a", agent="alpha")
    os.mkfifo(s / "201.json")  # a FIFO registry entry: read_text would block forever
    denied = _session(s, p, 202, cwd=repo, name="denied", sid="sid-x", agent="alpha")
    denied.chmod(0)
    # an unstat-able /proc/<pid>: its path runs through a mode-000 directory (EACCES on stat)
    _session(s, p, 203, cwd=repo, name="unstatable", sid="sid-u", agent="alpha", alive=False)
    locked = tmp_path / "locked"
    (locked / "x").mkdir(parents=True)
    (p / "203").symlink_to(locked / "x")
    locked.chmod(0)
    try:
        out = _who("alpha", capsys)
    finally:
        locked.chmod(0o755)
        denied.chmod(0o644)
    assert out == "fabrik-alpha\n"


def test_who_never_rings_a_recycled_pid(world, capsys):
    """Review item 1: a process born AFTER its registry file was written is a recycled pid —
    the stale file and its old binding must not ring it. No readable start time = no ring."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 55555, cwd=repo, name="stale-alpha", sid="sid-old", agent=None, born=20_000)
    _session(s, p, 55556, cwd=repo, name="no-stat-alpha", sid="sid-ns", agent=None, born=None)
    _session(s, p, 101, cwd=repo, name="fabrik-alpha", sid="sid-a", agent=None)
    _bind(world, ("sid-old", "alpha"), ("sid-ns", "alpha"), ("sid-a", "alpha"))
    assert _who("alpha", capsys) == "fabrik-alpha\n"


def test_who_env_name_outranks_the_binding(world, capsys):
    """Review item 2, mirroring resolve_agent_name: a VALID env CLAUDE_AGENT alone decides; the
    binding is read only when the env carries no valid name; an invalid env value never matches."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 301, cwd=repo, name="env-alpha", sid="sid-301", agent="alpha")
    _session(s, p, 302, cwd=repo, name="bad-env", sid="sid-302", agent="Alpha")
    _bind(world, ("sid-301", "beta"), ("sid-302", "gamma"))
    assert _who("beta", capsys) == ""  # the leftover binding loses to the env
    assert _who("alpha", capsys) == "env-alpha\n"
    assert _who("Alpha", capsys) == ""  # an invalid env value is no identity
    assert _who("gamma", capsys) == "bad-env\n"  # invalid env => the binding decides


def test_who_skips_unsafe_names_relative_cwds_and_oversized_entries(world, capsys):
    """Review items 3, 5, 6: one entry never prints as two lines; a relative cwd never resolves
    against the caller's cwd; an entry over the size cap is never read."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 101, cwd=repo, name="fabrik-alpha", sid="sid-a", agent="alpha")
    _session(s, p, 401, cwd=repo, name="evil\nfabrik-injected", sid="s1", agent="alpha")
    _session(s, p, 402, cwd=repo, name="tab\there", sid="s2", agent="alpha")
    _session(s, p, 403, cwd=".", name="relative-cwd", sid="s3", agent="alpha")
    _session(s, p, 404, cwd=repo, name="oversized", sid="s4", agent="alpha", pad=70_000)
    assert _who("alpha", capsys) == "fabrik-alpha\n"


def test_who_survives_a_deeply_nested_entry(world, capsys):
    """O10: '[' * 60000 is under the size cap and makes json.loads raise RecursionError —
    neither OSError nor ValueError. One hostile entry must not abort the verb."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 101, cwd=repo, name="fabrik-alpha", sid="sid-a", agent="alpha")
    _session(s, p, 501, cwd=repo, name="x", sid="x", agent="alpha", body="[" * 60_000)
    assert _who("alpha", capsys) == "fabrik-alpha\n"


def test_who_rides_a_clock_step_but_never_a_foreign_process(world, capsys):
    """O11: a forward wall-clock step after the session wrote its entry makes a live session's
    start read a little LATER than the file — it must still ring (within the slack). A pid
    recycled into a non-claude process never rings, whatever its start time."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 601, cwd=repo, name="stepped", sid="s601", agent="alpha", born=10_002)
    _session(
        s,
        p,
        602,
        cwd=repo,
        name="bash-at-old-pid",
        sid="s602",
        agent="alpha",
        argv=("/usr/bin/bash", "-l"),
    )
    _session(s, p, 603, cwd=repo, name="no-cmdline", sid="s603", agent="alpha", argv=())
    assert _who("alpha", capsys) == "stepped\n"


def test_who_env_path_survives_a_missing_whoami_module(world, capsys, monkeypatch):
    """O12: whoami_agent failing to import costs only the BINDING source; a live session whose
    environ names the agent still rings, and the local name pattern equals whoami's."""
    import whoami_agent  # resolvable: mail.py put scripts/ on sys.path at load

    assert mail._AGENT_NAME_RE.pattern == whoami_agent._NAME_RE.pattern
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    _session(s, p, 101, cwd=repo, name="fabrik-alpha", sid="sid-a", agent="alpha")
    _session(s, p, 102, cwd=repo, name="bound-only", sid="sid-b", agent=None)
    _bind(world, ("sid-b", "alpha"))
    monkeypatch.setattr(mail, "_whoami", lambda: None)
    assert _who("alpha", capsys) == "fabrik-alpha\n"


def test_read_capped_never_trusts_st_size_and_never_blocks(tmp_path, alarm):
    """O13: procfs pseudo-files are S_ISREG with st_size 0, so a stat-based cap reads them
    unbounded; the read itself must stop at cap+1 bytes. A FIFO opens without blocking and is
    refused by fstat on the SAME descriptor (no stat-then-open window)."""
    status = Path("/proc/self/status")
    assert status.stat().st_size == 0  # the premise: the kernel reports no size
    asked: list[int] = []
    real_read = os.read

    def spy(fd, n):
        asked.append(n)
        return real_read(fd, n)

    mail.os.read = spy  # the module's os IS this os: restored in finally, nothing else reads here
    try:
        assert mail._read_capped(status, 100) is None  # over the cap by READ, not by stat
    finally:
        mail.os.read = real_read
    # bounded by what is REQUESTED, not just by the answer: an unbounded read also returns None
    assert asked and sum(asked) <= 101
    got = mail._read_capped(status, 1_000_000)
    assert got is not None and b"Name:" in got[0]
    fifo = tmp_path / "f.json"
    os.mkfifo(fifo)
    assert mail._read_capped(fifo, 100) is None


def test_who_keeps_real_names_and_drops_only_control_characters(world, capsys):
    """O14: strip the ends, then reject only control characters (and line separators) or
    over-long names; 'café', 'feat/x' and a trailing space are real session names."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    for pid, name in [
        (701, "fabrik-97 "),
        (702, "café"),
        (703, "feat/x"),
        (704, "bell\x07"),
        (705, "nel\x85x"),
        (706, "ls x"),
        (707, "z" * 129),
    ]:
        _session(s, p, pid, cwd=repo, name=name, sid=f"s{pid}", agent="alpha")
    assert _who("alpha", capsys) == "café\nfabrik-97\nfeat/x\n"


def test_who_rings_long_argv_and_node_launched_sessions(world, capsys):
    """O15: a cmdline over 4 KB is read as a bounded PREFIX, never refused whole. O16: a session
    launched as `node …/claude-code/cli.js` names claude in argv[1], not argv[0]."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    long_argv = (CLAUDE_ARGV0, "--append-system-prompt", "x" * 6000)
    _session(s, p, 801, cwd=repo, name="long-argv", sid="s801", agent="alpha", argv=long_argv)
    node = ("/usr/bin/node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js")
    _session(s, p, 802, cwd=repo, name="node-cli", sid="s802", agent="alpha", argv=node)
    other = ("/usr/bin/node", "/srv/app/server.js")
    _session(s, p, 803, cwd=repo, name="node-other", sid="s803", agent="alpha", argv=other)
    assert _who("alpha", capsys) == "long-argv\nnode-cli\n"


def test_who_keeps_format_characters_that_do_not_break_lines(world, capsys):
    """O17: only Cc, Zl/Zp or a splitlines() break refuse a name; Cf format characters such as
    ZWJ (U+200D, emoji sequences) and the soft hyphen (U+00AD) stay."""
    s, p, repo = world["sessions"], world["proc"], world["repo"]
    for pid, name in [(901, "dev‍ops"), (902, "soft­hyphen"), (903, "ls x")]:
        _session(s, p, pid, cwd=repo, name=name, sid=f"s{pid}", agent="alpha")
    assert _who("alpha", capsys) == "dev‍ops\nsoft­hyphen\n"
