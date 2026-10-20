"""hibernate.py (W-1e9ae1e5): who gets the pause, when the box is safe, and how a woken agent knows it slept.

Driven against a fixture HOME (session records, identity store, run records, rotate ledger, the pause marker) and a
fixture /proc root, so no test reads the operator's live sessions; `status` runs real git in throwaway repos.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIB = ROOT / "scripts" / "sysadmin" / "hibernate.py"


def _run(home: Path, proc: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HIB), "--home", str(home), "--proc", str(proc), *args],
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
    )


class Box:
    """A fixture HOME + /proc: `session()` adds a session record and the process it names."""

    def __init__(self, tmp: Path) -> None:
        self.home, self.proc = tmp / "home", tmp / "proc"
        (self.home / ".claude" / "sessions").mkdir(parents=True)
        (self.home / ".claude" / "state" / "command-runs").mkdir(parents=True)
        self.proc.mkdir()
        self.store: list[dict] = []

    def session(
        self,
        pid: int,
        sid: str,
        cwd: str,
        peer: str,
        *,
        entrypoint: str = "cli",
        env_agent: str | None = None,
        bound: str | None = None,
        start: int = 1000,
        record_start: int | None = None,
        comm: str = "claude",
        ppid: int = 1,
        records: Path | None = None,
    ) -> None:
        rec = {
            "pid": pid,
            "sessionId": sid,
            "cwd": cwd,
            "name": peer,
            "kind": "interactive",
            "entrypoint": entrypoint,
            "procStart": str(start if record_start is None else record_start),
        }
        ((records or self.home / ".claude" / "sessions") / f"{pid}.json").write_text(json.dumps(rec), encoding="utf-8")
        p = self.proc / str(pid)
        p.mkdir()
        fields = ["S", str(ppid)] + ["0"] * 17 + [str(start)]
        (p / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + "\n", encoding="utf-8")
        (p / "comm").write_text(comm + "\n", encoding="utf-8")
        (p / "environ").write_bytes((f"CLAUDE_AGENT={env_agent}\0" if env_agent else "") .encode() + b"HOME=/h\0")
        if bound:
            self.store.append({"session_id": sid, "name": bound, "toplevel": cwd + "/.git", "at": 1})
            (self.home / ".claude" / "state" / "agent-identity.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in self.store), encoding="utf-8"
            )

    def run_record(self, sid: str, state: str, command: str = "fabrik-task", started: float = 0) -> None:
        (self.home / ".claude" / "state" / "command-runs" / f"{sid}.json").write_text(
            json.dumps({"state": state, "command": command, "started_epoch": started}), encoding="utf-8"
        )


# The grouping key is `/opt/<repo>` from the cwd and the coordinator is that repo's REAL ledger's merge owner
# (decisions.py), so the targets tests use the live hub and fabrik-lib names; the processes are all fixtures.


def test_targets_groups_live_agents_by_repo_with_the_ledgers_coordinator(tmp_path: Path) -> None:
    """A live agent session (record + matching start time + comm claude) is grouped by its /opt repo; the coordinator
    is the session holding the ledger's merge owner — by CLAUDE_AGENT or by its whoami binding — never a position."""
    box = Box(tmp_path)
    box.session(101, "s-coord", "/opt/fabrik", "fabrik-64", entrypoint="claude-vscode", bound="coordinator")
    box.session(102, "s-infra", "/opt/fabrik/.claude/worktrees/infra", "infra", env_agent="infra")
    box.session(103, "s-lead", "/opt/fabrik-lib", "fabrik-lib-5d", entrypoint="claude-vscode", env_agent="fabrik-lib-coordinator")
    box.session(104, "s-dev1", "/opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev1", "fabrik-lib-dev1", env_agent="fabrik-lib-dev1")
    out = _run(box.home, box.proc, "targets", "--json", "--self", "none")
    assert out.returncode == 0, out.stderr
    t = json.loads(out.stdout)
    rows = {r["repo"]: r for r in t["repos"]}
    # the real hub and fabrik-lib ledgers are read through decisions.py: their merge owners are the live truth
    assert rows["/opt/fabrik"]["coordinator"]["peer"] == "fabrik-64", rows["/opt/fabrik"]
    assert [s["agent"] for s in rows["/opt/fabrik"]["others"]] == ["infra"]
    assert rows["/opt/fabrik-lib"]["coordinator"]["peer"] == "fabrik-lib-5d", rows["/opt/fabrik-lib"]


def test_targets_never_messages_pool_sessions_and_drops_stale_records(tmp_path: Path) -> None:
    """`claude -p` pool workers and review seats (entrypoint sdk-cli/sdk-ts) are counted, never grouped as agents; a
    seat under a live agent is that agent's own work. A record whose start time does not match /proc (a reused pid) or
    whose process is not claude is not live."""
    box = Box(tmp_path)
    box.session(201, "s-infra", "/opt/fabrik/.claude/worktrees/infra", "infra", env_agent="infra")
    box.session(202, "s-seat", "/opt/fabrik/.claude/worktrees/infra", "fabrik-77", entrypoint="sdk-cli", ppid=201)
    box.session(203, "s-pool", "/opt/youtube", "youtube-94", entrypoint="sdk-cli", ppid=1)
    box.session(204, "s-stale", "/opt/fabrik", "fabrik-11", record_start=999)
    box.session(205, "s-node", "/opt/fabrik", "fabrik-12", comm="node")
    t = json.loads(_run(box.home, box.proc, "targets", "--json", "--self", "none").stdout)
    agents = [s["sid"] for r in t["repos"] for s in r["sessions"]]
    assert agents == ["s-infra"], t
    pool = {p["sid"]: p["parent_agent"] for p in t["pool"]}
    assert pool == {"s-seat": "infra", "s-pool": ""}, t["pool"]


def test_targets_flags_duplicate_missing_and_outside_sessions(tmp_path: Path) -> None:
    """Two live sessions holding the coordinator's name, or none, make the row say to message each session; a session
    outside /opt is listed for a direct message; the caller's own session is excluded."""
    box = Box(tmp_path)
    box.session(301, "s-c1", "/opt/fabrik", "fabrik-64", entrypoint="claude-vscode", bound="coordinator")
    box.session(302, "s-c2", "/opt/fabrik", "fabrik-6f", entrypoint="claude-vscode", bound="coordinator")
    box.session(303, "s-lib", "/opt/fabrik-lib/.claude/worktrees/fabrik-lib-dev1", "fabrik-lib-dev1", env_agent="fabrik-lib-dev1")
    box.session(304, "s-home", "/home/u", "u-1")
    box.session(305, "s-me", "/opt/fabrik/.claude/worktrees/infra", "infra", env_agent="infra")
    t = json.loads(_run(box.home, box.proc, "targets", "--json", "--self", "s-me").stdout)
    rows = {r["repo"]: r for r in t["repos"]}
    assert rows["/opt/fabrik"]["coordinator"] is None and "2 live sessions hold coordinator" in rows["/opt/fabrik"]["note"]
    assert rows["/opt/fabrik-lib"]["coordinator"] is None and "no live coordinator" in rows["/opt/fabrik-lib"]["note"]
    assert [s["sid"] for s in t["outside"]] == ["s-home"]
    assert all(s["sid"] != "s-me" for r in t["repos"] for s in r["sessions"])


def test_records_in_a_second_sessions_dir_are_found(tmp_path: Path) -> None:
    """A session started under another config dir (`~/.claude-<x>/sessions`) is as visible as one in ~/.claude."""
    box = Box(tmp_path)
    other = box.home / ".claude-youtube-headless" / "sessions"
    other.mkdir(parents=True)
    box.session(401, "s-yt", "/opt/youtube/.claude/worktrees/yt1", "yt1", env_agent="yt1", records=other)
    t = json.loads(_run(box.home, box.proc, "targets", "--json", "--self", "none").stdout)
    assert [s["sid"] for r in t["repos"] for s in r["sessions"]] == ["s-yt"], t


def test_brief_carries_the_drill_the_three_closes_and_the_cached_token_warning(tmp_path: Path) -> None:
    """The agent text says to let one's own subagents finish, commit and push on one's own branch, close each run in
    the first form the local command_run.py accepts, that the wake drops the cached prompt, and how to resume; the
    coordinator text carries the agent text verbatim."""
    box = Box(tmp_path)
    agent = _run(box.home, box.proc, "brief", "--role", "agent", "--words", "we need to hibernate").stdout
    for must in (
        'The operator, verbatim: "we need to hibernate"',
        "Let your OWN subagents and review\n   seats finish",
        "blocked --command <the live run> --paused --reason \"operator: we need to hibernate\"",
        "handoff --command <the run> --reason",
        "--resume <a file with a ## RESUME block>",
        "blocked --command <the run> --reason \"operator pause (no --paused in this copy)",
        "The wake DROPS your cached prompt",
        "PAUSED — <item> — branch pushed <sha> — seed <path|none> — next <step>",
        "woke",
    ):
        assert must in agent, must
    coord = _run(box.home, box.proc, "brief", "--role", "coordinator", "--words", "we need to hibernate").stdout
    assert coord.startswith("URGENT — HIBERNATE") and agent in coord


def _git_repo(path: Path, remote: Path | None = None) -> None:
    def g(*a: str, cwd: Path = path) -> None:
        subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)

    path.mkdir(parents=True)
    g("init", "-q", "-b", "main")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "c0")
    if remote is not None:
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True)
        g("remote", "add", "origin", str(remote))
        g("push", "-q", "-u", "origin", "main")


def test_status_says_safe_only_when_every_agent_worktree_is_clean_pushed_and_idle(tmp_path: Path) -> None:
    """Each live agent's cwd: a running run record, uncommitted tracked changes, unpushed commits, or a branch on no
    remote blocks; untracked files never block; SAFE only when nothing blocks."""
    box = Box(tmp_path)
    ok = tmp_path / "w" / "ok"
    _git_repo(ok, tmp_path / "r" / "ok.git")
    (ok / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    box.session(501, "s-ok", str(ok), "ok", env_agent="ok")
    box.session(502, "s-me", str(ok), "me", env_agent="me")
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert out.returncode == 0 and "SAFE TO HIBERNATE" in out.stdout and "1 untracked" in out.stdout, out.stdout
    box.run_record("s-ok", "running")
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert out.returncode == 1 and "run /fabrik-task still running" in out.stdout, out.stdout
    box.run_record("s-ok", "blocked")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "c1"], cwd=ok, check=True)
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert out.returncode == 1 and "1 commit(s) not pushed" in out.stdout, out.stdout
    lone = tmp_path / "w" / "lone"
    _git_repo(lone)  # no remote at all: its HEAD is on no remote branch
    box.session(503, "s-lone", str(lone), "lone", env_agent="lone")
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert "no upstream and HEAD is on no remote branch" in out.stdout, out.stdout
    (lone / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=lone, check=True)
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert "1 uncommitted change(s)" in out.stdout, out.stdout


def test_status_is_never_safe_on_an_empty_or_foreign_view(tmp_path: Path) -> None:
    """No live session found, or the caller not among them, is exit 2 — an empty table is not a safe one."""
    box = Box(tmp_path)
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert out.returncode == 2 and "no live agent session found" in out.stderr, out.stderr
    box.session(601, "s-other", str(tmp_path), "other", env_agent="other")
    out = _run(box.home, box.proc, "status", "--self", "s-me")
    assert out.returncode == 2 and "is not among the live sessions" in out.stderr, out.stderr


def _ledger(box: Box, *rows: dict) -> None:
    (box.home / ".claude" / "state" / "rotate-ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )


def test_woke_answers_only_for_a_real_wake_after_the_current_mark(tmp_path: Path) -> None:
    """`woke` is 0 only after a resume-wake of at least 15 minutes, or the hub's lift, that came AFTER the current
    mark; a wake before the mark, a short gap, no mark, and a session already running again all answer 1."""
    box = Box(tmp_path)
    assert _run(box.home, box.proc, "woke", "--self", "s1").returncode == 1  # no mark
    assert _run(box.home, box.proc, "mark", "--words", "we need to hibernate").returncode == 0
    paused = json.loads((box.home / ".claude" / "state" / "hibernate.json").read_text())["paused_at"]
    _ledger(box, {"event": "resume-wake", "ts": paused - 100, "gap_s": 9000})
    out = _run(box.home, box.proc, "woke", "--self", "s1")
    assert out.returncode == 1 and "stay paused" in out.stdout, out.stdout
    _ledger(box, {"event": "resume-wake", "ts": paused + 0.001, "gap_s": 300})
    assert _run(box.home, box.proc, "woke", "--self", "s1").returncode == 1  # a 5-minute gap is no sleep
    _ledger(box, {"event": "resume-wake", "ts": paused + 0.001, "gap_s": 38732})
    out = _run(box.home, box.proc, "woke", "--self", "s1")
    assert out.returncode == 0 and out.stdout.startswith("RESUME — the box slept 38732 s"), out.stdout
    box.run_record("s1", "running", started=paused + 120)
    out = _run(box.home, box.proc, "woke", "--self", "s1")
    assert out.returncode == 1 and "already resumed" in out.stdout, out.stdout
    # a second hibernate: the first wake no longer counts
    time.sleep(0.05)
    assert _run(box.home, box.proc, "mark", "--words", "again").returncode == 0
    assert _run(box.home, box.proc, "woke", "--self", "s2").returncode == 1


def test_lift_ends_a_pause_with_no_sleep(tmp_path: Path) -> None:
    """The hub's `lift` is a wake for every paused agent when the box never slept; with no mark it refuses."""
    box = Box(tmp_path)
    assert _run(box.home, box.proc, "lift").returncode == 1
    _run(box.home, box.proc, "mark", "--words", "w")
    assert _run(box.home, box.proc, "woke", "--self", "s1").returncode == 1
    assert _run(box.home, box.proc, "lift").returncode == 0
    out = _run(box.home, box.proc, "woke", "--self", "s1")
    assert out.returncode == 0 and "lifted by the hub" in out.stdout, out.stdout
