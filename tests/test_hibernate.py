"""hibernate.py (W-1e9ae1e5): who gets the pause, when the box is safe, and how a woken agent knows it slept.

Driven against a fixture HOME (session records, identity store, run records, rotate ledger, the pause marker), a
fixture /proc root and a fixture /opt root whose repos carry their own ledgers, so no test reads the operator's live
sessions or a live ledger; `status` runs real git in throwaway repos, and the pause text's close forms run through the
real command_run.py against a fixture state dir.
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import pty
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HIB = ROOT / "scripts" / "sysadmin" / "hibernate.py"
COMMAND_RUN = ROOT / "scripts" / "command_run.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class Box:
    """A fixture HOME + /proc + /opt: `session()` adds a session record and the process it names; `repo()` a repo
    folder under the fixture /opt whose ledger declares a merge owner (or none)."""

    def __init__(self, tmp: Path) -> None:
        self.home, self.proc, self.opt = tmp / "home", tmp / "proc", tmp / "opt"
        (self.home / ".claude" / "sessions").mkdir(parents=True)
        (self.home / ".claude" / "state" / "command-runs").mkdir(parents=True)
        self.proc.mkdir()
        self.opt.mkdir()
        self.store: list[dict] = []
        self.locks = tmp / "locks"
        self._held: list[
            int
        ] = []  # open lock fds: a flock held by THIS process is a live holder to the child

    def arm(self, *sids: str) -> None:
        """A held `<safe>.selfwatch.lock` per session: what an armed self-watch looks like to a probing process."""
        self.locks.mkdir(exist_ok=True)
        for sid in sids:
            fd = os.open(self.locks / f"{sid}.selfwatch.lock", os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._held.append(fd)

    def heartbeat(self, age: float = 0.0) -> None:
        """`battery-tick-last`: the epoch the minute cron wrote `age` seconds ago."""
        (self.state / "battery-tick-last").write_text(f"{time.time() - age}\n", encoding="utf-8")

    def ready(self, *sids: str) -> None:
        """Everything `status` needs besides the worktrees: a fresh heartbeat and an armed watch per session."""
        self.heartbeat()
        self.arm(*sids)

    def mark(self, deadline_in: float | None = None, **extra: object) -> None:
        now = time.time()
        m: dict[str, object] = {"paused_at": now - 5, "words": "close the lid", **extra}
        if deadline_in is not None:
            m["deadline_at"] = now + deadline_in
        (self.state / "hibernate.json").write_text(json.dumps(m), encoding="utf-8")

    def closed(self, sid: str, state: str, ts: float, **extra: object) -> None:
        (self.state / "command-runs" / f"{sid}.json").write_text(
            json.dumps({"state": state, "command": "fabrik-task", "updated_ts": int(ts), **extra}),
            encoding="utf-8",
        )

    def repo(self, name: str, owner: str | None) -> str:
        repo = self.opt / name
        (repo / "docs").mkdir(parents=True)
        if owner is not None:
            (repo / "docs" / "DECISIONS.md").write_text(
                "| id | when | who | what | why | where |\n|---|---|---|---|---|---|\n"
                f"| D-001 | 2026-10-21 | operator | MERGE OWNER: {owner} | why | here |\n",
                encoding="utf-8",
            )
        return str(repo)

    def session(
        self,
        pid: int,
        sid: str,
        cwd: str,
        peer: str,
        *,
        entrypoint: str | None = "cli",
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
            "procStart": str(start if record_start is None else record_start),
        }
        if entrypoint is not None:
            rec["entrypoint"] = entrypoint
        ((records or self.home / ".claude" / "sessions") / f"{pid}.json").write_text(
            json.dumps(rec), encoding="utf-8"
        )
        p = self.proc / str(pid)
        p.mkdir()
        fields = ["S", str(ppid)] + ["0"] * 17 + [str(start)]
        (p / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + "\n", encoding="utf-8")
        (p / "comm").write_text(comm + "\n", encoding="utf-8")
        (p / "environ").write_bytes(
            (f"CLAUDE_AGENT={env_agent}\0" if env_agent else "").encode() + b"HOME=/h\0"
        )
        if bound:
            self.store.append(
                {"session_id": sid, "name": bound, "toplevel": cwd + "/.git", "at": 1}
            )
            (self.home / ".claude" / "state" / "agent-identity.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in self.store), encoding="utf-8"
            )

    def run_record(
        self, sid: str, state: str, command: str = "fabrik-task", started: object = 0
    ) -> None:
        (self.home / ".claude" / "state" / "command-runs" / f"{sid}.json").write_text(
            json.dumps({"state": state, "command": command, "started_epoch": started}),
            encoding="utf-8",
        )

    @property
    def state(self) -> Path:
        return self.home / ".claude" / "state"

    def process(self, pid: int, ppid: int, comm: str = "bash") -> None:
        """A /proc entry with no session record — a shell, tmux, an editor between the caller and a session."""
        p = self.proc / str(pid)
        p.mkdir()
        fields = ["S", str(ppid)] + ["0"] * 17 + ["1000"]
        (p / "stat").write_text(f"{pid} ({comm}) " + " ".join(fields) + "\n", encoding="utf-8")
        (p / "comm").write_text(comm + "\n", encoding="utf-8")
        (p / "environ").write_bytes(b"HOME=/h\0")

    def run(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        stdin: int = subprocess.DEVNULL,
        under_pytest: bool = True,
        proc: str | None = None,
        home_arg: bool = True,
        timeout: float = 120,
    ) -> subprocess.CompletedProcess[str]:
        # ROTATE_STATE_DIR: the marker and the rotate ledger live in the fixture's state dir (conftest pins the
        # variable per test for in-process callers; this subprocess env is explicit, so it is set here). stdin is
        # /dev/null unless a test hands it a real pseudo-terminal (`_shell_lift`). PYTEST_CURRENT_TEST is carried, as
        # `lift` honours its fixture roots and resolver seam only under a test; `under_pytest=False` drops it.
        base = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "TZ": "UTC",
            "ROTATE_STATE_DIR": str(self.state),
            "CLAUDE_SOUND_LOCKDIR": str(self.locks),
            "HIBERNATE_STATUS_GAP_S": "0",  # the seam: no 5 s wait between status's two reads
        }
        if under_pytest:
            base["PYTEST_CURRENT_TEST"] = os.environ.get("PYTEST_CURRENT_TEST", "fixture")
        roots = ["--home", str(self.home)] if home_arg else []
        return subprocess.run(
            [
                sys.executable,
                str(HIB),
                *roots,
                "--proc",
                proc or str(self.proc),
                "--opt",
                str(self.opt),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=stdin,
            env={**base, **(env or {})},
        )

    def targets(self, self_sid: str = "none") -> dict:
        out = self.run("targets", "--json", "--self", self_sid)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)


def test_targets_groups_live_agents_by_repo_with_the_ledgers_coordinator(tmp_path: Path) -> None:
    """A live agent session (record + matching start time + comm claude) is grouped by its repo; the coordinator is
    the session holding the ledger's merge owner — by CLAUDE_AGENT or by its whoami binding — never a position."""
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    lib = box.repo("fabrik-lib", "fabrik-lib-coordinator")
    box.session(101, "s-coord", hub, "fabrik-64", entrypoint="claude-vscode", bound="coordinator")
    box.session(102, "s-infra", hub + "/.claude/worktrees/infra", "infra", env_agent="infra")
    box.session(
        103,
        "s-lead",
        lib,
        "fabrik-lib-5d",
        entrypoint="claude-vscode",
        env_agent="fabrik-lib-coordinator",
    )
    box.session(104, "s-dev1", lib + "/.claude/worktrees/dev1", "fabrik-lib-dev1", env_agent="dev1")
    rows = {r["repo"]: r for r in box.targets()["repos"]}
    assert sorted(rows) == [hub, lib], (
        rows
    )  # /opt/fabrik and /opt/fabrik-lib never merge on a prefix
    assert rows[hub]["coordinator"]["peer"] == "fabrik-64", rows[hub]
    assert [s["agent"] for s in rows[hub]["others"]] == ["infra"]
    assert rows[lib]["coordinator"]["peer"] == "fabrik-lib-5d", rows[lib]
    assert [s["agent"] for s in rows[lib]["others"]] == ["dev1"]


def test_targets_never_messages_pool_sessions_drops_stale_records_and_keeps_unknown_clients(
    tmp_path: Path,
) -> None:
    """`claude -p` pool workers and review seats (every `sdk-*` entrypoint) are counted, never grouped as agents; a
    seat under a live agent is that agent's own work. Any other entrypoint — a missing or new one — is an agent (fail
    closed). A record whose start time does not match /proc (a reused pid) or whose process is not claude is not
    live."""
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    box.session(201, "s-infra", hub + "/w/infra", "infra", env_agent="infra")
    box.session(202, "s-seat", hub + "/w/infra", "fabrik-77", entrypoint="sdk-cli", ppid=201)
    box.session(203, "s-pool", hub, "youtube-94", entrypoint="sdk-ts", ppid=1)
    box.session(204, "s-stale", hub, "fabrik-11", record_start=999)
    box.session(205, "s-node", hub, "fabrik-12", comm="node")
    box.session(206, "s-new", hub + "/w/new", "fabrik-13", entrypoint="desktop-2027")
    box.session(207, "s-bare", hub + "/w/bare", "fabrik-14", entrypoint=None)
    box.session(208, "s-py", hub, "fabrik-15", entrypoint="sdk-py", ppid=1)
    t = box.targets()
    agents = sorted(s["sid"] for r in t["repos"] for s in r["sessions"])
    assert agents == ["s-bare", "s-infra", "s-new"], t
    assert {p["sid"]: p["parent_agent"] for p in t["pool"]} == {
        "s-seat": "infra",
        "s-pool": "",
        "s-py": "",
    }


def test_targets_flags_duplicate_missing_failed_self_and_outside(tmp_path: Path) -> None:
    """Two live sessions holding the coordinator's name, or none, make the row say to message each session; a
    FAILED owner lookup names nobody even for a lone session (only a declared none does); the caller's own repo picks
    no coordinator; a session outside /opt — `/opt//x` included — is listed for a direct message; the caller's own
    session is never a target."""
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    lib = box.repo("fabrik-lib", "fabrik-lib-coordinator")
    none = box.repo("loner", None)
    broken = box.repo("broken", "x")
    ledger = Path(broken) / "docs" / "DECISIONS.md"
    me = box.repo("mine", None)
    box.session(301, "s-c1", hub, "fabrik-64", entrypoint="claude-vscode", bound="coordinator")
    box.session(302, "s-c2", hub, "fabrik-6f", entrypoint="claude-vscode", bound="coordinator")
    box.session(303, "s-lib", lib + "/w/dev1", "fabrik-lib-dev1", env_agent="dev1")
    box.session(304, "s-loner", none, "loner-1", env_agent="l")
    box.session(305, "s-broken", broken, "broken-1", env_agent="b")
    box.session(306, "s-me", me, "me-1", env_agent="me")
    box.session(307, "s-mine2", me + "/w/two", "me-2", env_agent="two")
    box.session(308, "s-home", "/home/u", "u-1")
    box.session(309, "s-dbl", str(box.opt) + "//x", "dbl-1")
    ledger.chmod(0)
    try:
        t = box.targets("s-me")
    finally:
        ledger.chmod(0o644)
    rows = {r["repo"]: r for r in t["repos"]}
    assert (
        rows[hub]["coordinator"] is None and "2 live sessions hold coordinator" in rows[hub]["note"]
    )
    assert rows[lib]["coordinator"] is None and "no live coordinator" in rows[lib]["note"]
    assert rows[none]["coordinator"]["sid"] == "s-loner", rows[none]
    assert rows[broken]["coordinator"] is None, rows[broken]
    assert rows[broken]["owner_why"].startswith("lookup failed"), rows[broken]
    assert rows[me]["coordinator"] is None and "your own repo" in rows[me]["note"]
    assert sorted(s["sid"] for s in t["outside"]) == ["s-dbl", "s-home"]
    assert all(s["sid"] != "s-me" for r in t["repos"] for s in r["sessions"])


def test_records_in_a_second_sessions_dir_are_found(tmp_path: Path) -> None:
    """A session started under another config dir (`~/.claude-<x>/sessions`) is as visible as one in ~/.claude."""
    box = Box(tmp_path)
    yt = box.repo("youtube", "youtube-coordinator")
    other = box.home / ".claude-youtube-headless" / "sessions"
    other.mkdir(parents=True)
    box.session(401, "s-yt", yt + "/w/yt1", "yt1", env_agent="yt1", records=other)
    assert [s["sid"] for r in box.targets()["repos"] for s in r["sessions"]] == ["s-yt"]


def test_brief_carries_the_drill_and_close_forms_the_real_command_run_accepts(
    tmp_path: Path,
) -> None:
    """The agent text says to let one's own subagents finish, commit and push on one's own branch, close each run in
    the first form the local command_run.py accepts, that the wake drops the cached prompt, and how to resume; each
    close form, as printed and parsed by a shell, is ACCEPTED by the hub's command_run.py (a form missing its
    --feedback is refused) and carries the operator's words whole, a quote and a `$(…)` included; the coordinator
    text carries the agent text verbatim and never closes the hub's run."""
    box = Box(tmp_path)
    words = 'we need to "hibernate" $(true)'
    agent = box.run("brief", "--role", "agent", "--words", words).stdout
    for must in (
        f'The operator, verbatim: "{words}"',
        "Let your OWN subagents and review\n   seats finish",
        "The wake DROPS your cached prompt",
        "PAUSED — <item> — branch pushed <sha> — seed <path|none> — next <step>",
        "woke",
    ):
        assert must in agent, must
    forms = [
        ln[ln.index("python3 ") :]
        for ln in agent.splitlines()
        if "command_run.py " in ln and "--reason" in ln
    ]
    assert len(forms) == 3, forms
    resume = tmp_path / "resume.md"
    resume.write_text("## RESUME\nnext: x\n", encoding="utf-8")
    for i, form in enumerate(forms):
        state = tmp_path / f"cr{i}"
        env = {
            **os.environ,
            "COMMAND_RUN_DIR": str(state),
            "COMMAND_RUN_TRANSCRIPT": str(tmp_path / "none.jsonl"),
            "KAIZEN_EVENTS_DIR": str(tmp_path / f"ke{i}"),
            "CLAUDE_CODE_SESSION_ID": f"brief-{i}",
        }
        start = [sys.executable, str(COMMAND_RUN), "start", "--command", "fabrik-review"]
        subprocess.run(
            start + ["--phases", "5", "--terminal", "t", "--surface", "s"],
            env=env,
            capture_output=True,
            check=True,
            timeout=120,
        )
        argv = shlex.split(
            form.replace("<the live run>", "fabrik-review")
            .replace("<the run>", "fabrik-review")
            .replace("<a file with a ## RESUME block>", str(resume))
        )
        assert argv[:2] == ["python3", "scripts/command_run.py"], argv
        assert any(a.endswith(words) for a in argv), argv  # the words arrive as one whole argument
        feedback = argv[argv.index("--feedback") + 1]
        assert "<" not in feedback, feedback  # a pasted line records no placeholder
        done = subprocess.run(
            [sys.executable, str(COMMAND_RUN), *argv[2:]],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert done.returncode == 0, (form, done.stdout[-600:], done.stderr[-600:])
        rec = json.loads(next(state.glob("*.json")).read_text())
        assert rec["state"] in ("blocked", "handoff"), rec["state"]
    coord = box.run("brief", "--role", "coordinator", "--words", words).stdout
    assert coord.startswith("URGENT — HIBERNATE") and agent in coord
    assert "never close the hub's /hibernate run" in coord


def _git_repo(path: Path, remote: Path | None = None) -> None:
    def g(*a: str) -> None:
        subprocess.run(["git", *a], cwd=path, check=True, capture_output=True)

    path.mkdir(parents=True)
    g("init", "-q", "-b", "main")
    g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "c0")
    if remote is not None:
        subprocess.run(
            ["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True
        )
        g("remote", "add", "origin", str(remote))
        g("push", "-q", "-u", "origin", "main")


def _commit(path: Path, msg: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            msg,
        ],
        cwd=path,
        check=True,
    )


def _status(box: Box, me: str = "s-me") -> subprocess.CompletedProcess[str]:
    return box.run("status", "--self", me)


def test_status_says_safe_only_when_every_agent_worktree_is_clean_pushed_and_idle(
    tmp_path: Path,
) -> None:
    """Each live agent's cwd: a running run record, uncommitted tracked changes, unpushed commits, or a branch on no
    remote blocks (exit 1, no SAFE line); untracked files never block; SAFE (exit 0) only when nothing blocks."""
    box = Box(tmp_path)
    ok = tmp_path / "w" / "ok"
    _git_repo(ok, tmp_path / "r" / "ok.git")
    (ok / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    me = tmp_path / "w" / "me"
    _git_repo(me, tmp_path / "r" / "me.git")
    box.session(501, "s-ok", str(ok), "ok", env_agent="ok")
    box.session(502, "s-me", str(me), "me", env_agent="me")
    box.ready("s-ok", "s-me")
    out = _status(box)
    assert out.returncode == 0 and "SAFE TO HIBERNATE" in out.stdout, out.stdout
    assert "1 untracked" in out.stdout, out.stdout

    def blocked(why: str) -> None:
        out = _status(box)
        assert out.returncode == 1 and "SAFE TO HIBERNATE" not in out.stdout, out.stdout
        assert why in out.stdout, out.stdout

    box.run_record("s-ok", "running")
    blocked("run /fabrik-task still running")
    box.run_record("s-ok", "blocked")
    _commit(ok, "c1")
    blocked("1 commit(s) not pushed")
    subprocess.run(["git", "push", "-q"], cwd=ok, check=True, capture_output=True)
    lone = tmp_path / "w" / "lone"
    _git_repo(lone)  # no remote at all: its HEAD is on no remote branch
    box.session(503, "s-lone", str(lone), "lone", env_agent="lone")
    blocked("no upstream and HEAD is on no remote branch")
    (lone / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=lone, check=True)
    blocked("1 uncommitted change(s)")


@pytest.mark.parametrize(
    "case, why",
    [
        ("empty-cwd", "no absolute cwd recorded"),
        ("relative-cwd", "no absolute cwd recorded"),
        ("missing", "missing"),
        ("not-git", "not a git checkout"),
        ("detached", "detached HEAD"),
        ("corrupt-record", "run record unreadable"),
        ("no-sid", "no session id in its record"),
        ("int-cwd", "no absolute cwd recorded"),
    ],
)
def test_status_blocks_every_unprovable_row(tmp_path: Path, case: str, why: str) -> None:
    """A row status cannot prove clean blocks: an empty or relative cwd (`git -C ""` would read the CALLER's tree), a
    missing folder, a folder that is no git checkout, a detached HEAD, and a run record that is not a JSON object."""
    box = Box(tmp_path)
    me = tmp_path / "me"
    _git_repo(me, tmp_path / "me.git")
    box.session(601, "s-me", str(me), "me", env_agent="me")
    target = tmp_path / "t"
    if case == "empty-cwd":
        cwd = ""
    elif case == "relative-cwd":
        cwd = "w/t"
    elif case == "missing":
        cwd = str(tmp_path / "gone")
    elif case == "not-git":
        target.mkdir()
        cwd = str(target)
    else:
        _git_repo(target, tmp_path / "t.git")
        cwd = str(target)
        if case == "detached":
            subprocess.run(["git", "checkout", "-q", "--detach"], cwd=target, check=True)
    box.session(602, "" if case == "no-sid" else "s-t", cwd, "t", env_agent="t")
    if case == "int-cwd":  # a record whose cwd is no string is read as having none, never a crash
        rec_path = box.home / ".claude" / "sessions" / "602.json"
        rec_path.write_text(
            json.dumps({**json.loads(rec_path.read_text()), "cwd": 5}), encoding="utf-8"
        )
    if case == "corrupt-record":
        (box.home / ".claude" / "state" / "command-runs" / "s-t.json").write_text(
            "[]", encoding="utf-8"
        )
    out = _status(box)
    assert out.returncode == 1 and "SAFE TO HIBERNATE" not in out.stdout, out.stdout
    assert why in out.stdout, out.stdout


def test_status_checks_the_callers_own_tree_but_not_its_own_run_and_skips_pool_sessions(
    tmp_path: Path,
) -> None:
    """The caller's own /hibernate run is running by design and never blocks, but its worktree is checked like any
    other; a pool session's tree is never a row; a session with an unknown entrypoint is a row."""
    box = Box(tmp_path)
    me = tmp_path / "me"
    _git_repo(me, tmp_path / "me.git")
    box.session(701, "s-me", str(me), "me", env_agent="me")
    box.ready("s-me")
    box.run_record("s-me", "running", command="hibernate")
    out = _status(box)
    assert out.returncode == 0 and "(you)" in out.stdout, out.stdout
    pool = tmp_path / "pool"
    pool.mkdir()  # not a git checkout: its tree is never a row
    box.session(702, "s-pool", str(pool), "p", entrypoint="sdk-cli")
    out = _status(box)  # check 1: a headless session that is no agent's seat blocks before T-3 ...
    assert out.returncode == 1 and "headless" in out.stdout, out.stdout
    assert "not a git checkout" not in out.stdout, out.stdout
    box.mark(deadline_in=60)  # ... and from T-3 it is held, not blocking
    out = _status(box)
    assert out.returncode == 0 and "held (headless)" in out.stdout, out.stdout
    (box.state / "hibernate.json").unlink()
    box.session(703, "s-new", str(pool), "n", entrypoint="desktop-2027")
    assert _status(box).returncode == 1
    (me / "x.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "x.txt"], cwd=me, check=True)
    out = _status(box)
    assert "1 uncommitted change(s): x.txt (you)" in out.stdout, out.stdout


def test_status_exempts_only_the_callers_own_top_frame_hibernate_run(tmp_path: Path) -> None:
    """Only the caller's own TOP-frame /hibernate run is exempt: any other run of the caller, or a running parent
    frame under its /hibernate run, would stay running across the sleep and blocks."""
    box = Box(tmp_path)
    me = tmp_path / "me"
    _git_repo(me, tmp_path / "me.git")
    box.session(751, "s-me", str(me), "me", env_agent="me")
    box.ready("s-me")
    box.run_record("s-me", "running", command="fabrik-task")
    out = _status(box)
    assert out.returncode == 1 and "run /fabrik-task still running" in out.stdout, out.stdout
    record = box.home / ".claude" / "state" / "command-runs" / "s-me.json"
    parent = {"state": "running", "command": "fabrik-review"}
    record.write_text(
        json.dumps({"state": "running", "command": "hibernate", "stack": [parent]}),
        encoding="utf-8",
    )
    out = _status(box)
    assert out.returncode == 1 and "run /fabrik-review still running" in out.stdout, out.stdout
    record.write_text(json.dumps({"state": "running", "command": "hibernate", "stack": []}))
    assert _status(box).returncode == 0


def test_status_is_never_safe_on_an_empty_foreign_or_anonymous_view(tmp_path: Path) -> None:
    """No session id, no live session found, or the caller not among them, is exit 2 — an empty table is not a safe
    one."""
    box = Box(tmp_path)
    out = _status(box)
    assert out.returncode == 2 and "no live agent session found" in out.stderr, out.stderr
    box.session(801, "s-other", str(tmp_path), "other", env_agent="other")
    out = _status(box)
    assert out.returncode == 2 and "is not among the live sessions" in out.stderr, out.stderr
    out = box.run("status", "--self", "")
    assert out.returncode == 2 and "pass --self" in out.stderr, out.stderr


def test_status_blocks_when_git_cannot_run(tmp_path: Path) -> None:
    """A git that cannot start (or times out) is a blocking row with a reason, never a traceback with no table."""
    box = Box(tmp_path)
    me = tmp_path / "me"
    _git_repo(me, tmp_path / "me.git")
    box.session(901, "s-me", str(me), "me", env_agent="me")
    argv = [sys.executable, str(HIB), "--home", str(box.home), "--proc", str(box.proc)]
    out = subprocess.run(
        argv + ["--opt", str(box.opt), "status", "--self", "s-me"],
        capture_output=True,
        text=True,
        timeout=120,
        env={"PATH": str(tmp_path / "no-bin"), "HOME": str(box.home)},
    )
    assert out.returncode == 1, (out.stdout, out.stderr)
    assert "not a git checkout (git could not start)" in out.stdout, (out.stdout, out.stderr)


def _ledger(box: Box, *rows: dict) -> None:
    (box.home / ".claude" / "state" / "rotate-ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )


def _marker(box: Box) -> dict:
    return json.loads((box.state / "hibernate.json").read_text(encoding="utf-8"))


def _rows(box: Box, event: str) -> list[dict]:
    try:
        text = (box.state / "rotate-ledger.jsonl").read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [r for r in map(json.loads, text.splitlines()) if r.get("event") == event]


def _decisions_stub(tmp_path: Path, owner: str) -> str:
    """A `decisions.py` stand-in: `--merge-owner <repo>` answers `owner` (the FABRIK_DECISIONS_PY seam)."""
    stub = tmp_path / "decisions-stub.py"
    stub.write_text(f"print({owner!r})\n", encoding="utf-8")
    return str(stub)


def _shell_lift(box: Box) -> tuple[subprocess.CompletedProcess[str], str]:
    """`lift` from the operator's plain shell: the test process (the lift's parent) is a bash whose parent is pid 1,
    and the lift's stdin is a real pseudo-terminal. Returns the result and that terminal's name."""
    if not (box.proc / str(os.getpid())).exists():
        box.process(os.getpid(), 1)
    master, slave = pty.openpty()
    try:
        return box.run("lift", stdin=slave), os.ttyname(slave)
    finally:
        os.close(slave)
        os.close(master)


def test_mark_deadline_and_paused_exit_codes(tmp_path: Path) -> None:
    """`paused` is 0 while a pause is marked and not lifted, 1 with no marker file or after a lift, and 2 on a marker
    file it cannot read or parse — never the empty-dict 'unmarked' answer. `mark --deadline 10m` writes T = the mark
    + 600 s and keeps no key of an earlier pause."""
    box = Box(tmp_path)
    assert box.run("paused").returncode == 1  # no marker file
    (box.state / "hibernate.json").write_text(
        json.dumps({"paused_at": 1.0, "lifted_at": 2.0, "lift_path": "hub", "words": "old"}),
        encoding="utf-8",
    )
    assert box.run("paused").returncode == 1  # lifted
    assert box.run("mark", "--words", "w", "--deadline", "10m").returncode == 0
    m = _marker(box)
    assert set(m) == {"paused_at", "deadline_at", "words"}, m  # no old key survives a fresh mark
    assert abs(m["deadline_at"] - m["paused_at"] - 600) < 1e-6, m
    out = box.run("paused")
    assert out.returncode == 0, (out.stdout, out.stderr)
    assert _shell_lift(box)[0].returncode == 0
    assert box.run("paused").returncode == 1
    # review G4: a marker that EXISTS but cannot be read or parsed is PAUSED (exit 0, one stderr line naming the
    # file) — every launcher reads anything but 0 as "proceed", so the old exit 2 let them all run on a torn marker
    for bad in ("{torn", "{", "[]", '{"paused_at": "soon"}'):
        (box.state / "hibernate.json").write_text(bad, encoding="utf-8")
        out = box.run("paused")
        assert out.returncode == 0, (bad, out.stdout, out.stderr)
        assert "hibernate.json" in out.stderr and out.stdout == "", (bad, out.stdout, out.stderr)
    (box.state / "hibernate.json").unlink()
    (box.state / "hibernate.json").mkdir()  # exists, cannot be read
    out = box.run("paused")
    assert out.returncode == 0 and "hibernate.json" in out.stderr, (out.stdout, out.stderr)
    assert box.run("mark", "--words", "w", "--deadline", "soon").returncode == 2


def test_update_marker_keeps_both_writers_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two writers read-modify-writing the marker at once both land: the flock on hibernate.json.lock serialises
    them, so neither key set is lost."""
    import threading

    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    hib = _load("hib_lock_probe", HIB)
    hib.update_marker(tmp_path, lambda _old: {"paused_at": 1.0})

    def writer(key: str) -> None:
        def fn(old: dict) -> dict:
            new = dict(old)
            time.sleep(0.3)  # widen the read-modify-write window: an unlocked pair loses one key
            new[key] = 1
            return new

        hib.update_marker(tmp_path, fn)

    threads = [threading.Thread(target=writer, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert hib.marker_path(tmp_path) == tmp_path / "state" / "hibernate.json"
    assert hib.read_marker(tmp_path) == {"paused_at": 1.0, "a": 1, "b": 1}


def test_woke_answers_resume_only_after_the_lift(tmp_path: Path) -> None:
    """A resume-wake row is the lift's evidence, never `woke`'s: with no lift `woke` is 1 and names the lift paths;
    after the lift it is 0 while this session has started no run since (a run started before it, or a corrupt start
    time, never blocks); a run started after the lift — in any state — is `no pending resume`; a fresh mark resets
    it."""
    box = Box(tmp_path)
    assert box.run("woke", "--self", "s1").returncode == 1  # no mark
    assert box.run("mark", "--words", "we need to hibernate").returncode == 0
    paused = _marker(box)["paused_at"]
    _ledger(box, {"event": "resume-wake", "ts": paused + 1, "gap_s": 9000})
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "no pending resume" in out.stdout, out.stdout
    assert "hibernate.py lift" in out.stdout and "30 min" in out.stdout, (
        out.stdout
    )  # the lift paths
    # the sleep path as the tick applies it (T06): a nap during the drain lifts nothing
    assert (
        "a resume-wake row whose gap began after the mark and ended at or after T-3" in out.stdout
    ), out.stdout
    assert _shell_lift(box)[0].returncode == 0
    lifted = _marker(box)["lifted_at"]
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 0 and out.stdout.startswith("RESUME — the hibernate pause ended"), (
        out.stdout
    )
    box.run_record("s1", "blocked", started=paused - 50)  # the run the pause closed: not a resume
    assert box.run("woke", "--self", "s1").returncode == 0
    box.run_record("s1", "running", started="x")
    assert box.run("woke", "--self", "s1").returncode == 0
    box.run_record("s1", "running", started=float("inf"))  # json writes Infinity; it never blocks
    assert box.run("woke", "--self", "s1").returncode == 0
    box.run_record("s1", "done", started=lifted + 5)  # a run after the lift, in ANY state
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "no pending resume" in out.stdout, out.stdout
    time.sleep(0.05)
    assert box.run("mark", "--words", "again").returncode == 0
    assert box.run("woke", "--self", "s2").returncode == 1


@pytest.mark.parametrize("case", ["24h", "migration"])
def test_woke_never_answers_a_day_old_or_migration_lift(tmp_path: Path, case: str) -> None:
    """A lift 24 h old (a daily relaunch must never re-run a finished seed) or one the migration wrote is `no pending
    resume`."""
    box = Box(tmp_path)
    now = time.time()
    m = {"paused_at": now - 3600, "words": "w", "lifted_at": now - 60, "lift_path": "hub"}
    if case == "24h":
        m.update(paused_at=now - 26 * 3600, lifted_at=now - 24 * 3600 - 60)
    else:
        m["lift_path"] = "migration"
    (box.state / "hibernate.json").write_text(json.dumps(m), encoding="utf-8")
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "no pending resume" in out.stdout, out.stdout
    m.update(lifted_at=now - 60, lift_path="hub")  # the same marker, an ordinary fresh lift: RESUME
    (box.state / "hibernate.json").write_text(json.dumps(m), encoding="utf-8")
    assert box.run("woke", "--self", "s1").returncode == 0


def test_woke_lists_seeds_newest_first_with_each_abandoned_seats_state(tmp_path: Path) -> None:
    """RESUME lists this session's seeds written since the mark, newest first — a JSON seed as its `start
    --resume-from` line, a `.md` handoff as a fresh start following its ## RESUME — each abandoned seat with its
    state at the wake (only `exited, no output` is ordered re-run), and one get_chat line; an older seed and another
    session's seed are not listed."""
    box = Box(tmp_path)
    sid = "66b5e327-a366-4213-99e6-e362925e6142"
    assert box.run("mark", "--words", "w").returncode == 0
    paused = _marker(box)["paused_at"]
    seeds = box.state / "command-runs" / "seeds"
    seeds.mkdir()
    box.process(4242, 1, comm="claude")  # a seat still alive at the wake
    done_out = tmp_path / "seat-done.txt"
    done_out.write_text("verdict\n", encoding="utf-8")
    parent = seeds / f"{sid}-paused-aaaa.json"
    parent.write_text(
        json.dumps(
            {
                "command": "fabrik-review",
                "phases": 5,
                "abandoned_seats": [
                    {"pid": 4242, "purpose": "slice A", "brief": "/s/a.md", "output": "/s/a.out"},
                    {
                        "pid": 4343,
                        "purpose": "slice B",
                        "brief": "/s/b.md",
                        "output": str(done_out),
                    },
                    {"pid": 4444, "purpose": "slice C", "brief": "/s/c.md", "output": "/s/c.out"},
                ],
            }
        ),
        encoding="utf-8",
    )
    child = seeds / f"{sid}-paused-bbbb.json"
    child.write_text(json.dumps({"command": "fabrik-task", "phases": 6}), encoding="utf-8")
    handoff = seeds / f"{sid}-cccc.md"
    handoff.write_text("## RESUME\nnext: x\n", encoding="utf-8")
    old = seeds / f"{sid}-paused-0000.json"
    old.write_text(json.dumps({"command": "old", "phases": 1}), encoding="utf-8")
    other = (
        seeds / f"{sid}0-paused-dddd.json"
    )  # a longer sid sharing the prefix: not this session's
    other.write_text(json.dumps({"command": "other", "phases": 1}), encoding="utf-8")
    os.utime(old, (paused - 10, paused - 10))
    os.utime(handoff, (paused + 10, paused + 10))
    os.utime(child, (paused + 20, paused + 20))
    os.utime(parent, (paused + 30, paused + 30))
    os.utime(other, (paused + 40, paused + 40))
    assert _shell_lift(box)[0].returncode == 0
    out = box.run("woke", "--self", sid)
    assert out.returncode == 0, out.stdout
    text = out.stdout
    assert str(old) not in text and str(other) not in text, text
    order = [text.index(str(p)) for p in (parent, child, handoff)]
    assert order == sorted(order), text  # newest first: the parent closes last
    assert f"start --command fabrik-review --phases 5 --resume-from {parent}" in text, text
    assert f"start --command fabrik-task --phases 6 --resume-from {child}" in text, text
    assert "open a fresh start and follow its ## RESUME" in text, text
    assert "slice A: still running (pid 4242)" in text, text
    assert f"slice B: finished (output at {done_out})" in text, text
    seat_c = next(ln for ln in text.splitlines() if "slice C" in ln)
    assert "exited, no output" in seat_c and "re-run" in seat_c and "/s/c.md" in seat_c, seat_c
    assert not any(
        "re-run" in ln for ln in text.splitlines() if "slice A" in ln or "slice B" in ln
    ), text
    chat = [ln for ln in text.splitlines() if "get_chat" in ln]
    assert len(chat) == 1 and sid in chat[0], text
    assert time.strftime("%H:%M", time.gmtime(paused)) in chat[0], chat


def test_lift_passes_the_merge_owner_and_touches_no_stamp(tmp_path: Path) -> None:
    """The nearest live claude ancestor of the `lift` process — found past any number of hops (no 8-hop cap) — is
    the hub's merge owner: the lift writes `lifted_at` and `lift_path=hub` and nothing else, and the fleet-exhausted
    stamp is untouched."""
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    box.session(9001, "s-hub", hub, "fabrik-64", env_agent="coordinator")
    chain = list(range(9100, 9120))  # 20 shells between the session and the caller
    box.process(chain[0], 9001)
    for i in range(1, len(chain)):
        box.process(chain[i], chain[i - 1])
    box.process(os.getpid(), chain[-1])
    stamp = box.state / "fleet-exhausted"
    stamp.write_text("1800000000\nhibernate\n", encoding="utf-8")
    env = {"FABRIK_DECISIONS_PY": _decisions_stub(tmp_path, "coordinator")}
    assert box.run("lift", env=env).returncode == 1  # no pause marked: nothing to lift
    assert box.run("mark", "--words", "w").returncode == 0
    before = _marker(box)
    out = box.run("lift", env=env)
    assert out.returncode == 0, (out.stdout, out.stderr)
    after = _marker(box)
    assert set(after) - set(before) == {"lifted_at", "lift_path"} and after["lift_path"] == "hub", (
        after
    )
    assert {k: after[k] for k in before} == before, after
    assert stamp.read_text(encoding="utf-8") == "1800000000\nhibernate\n"
    assert _rows(box, "hibernate-lift-refused") == [] and _rows(box, "hibernate-lift-shell") == []
    again = box.run(
        "lift", env=env
    )  # a second lift never moves lifted_at (a resumed session stays resumed)
    assert again.returncode == 0 and _marker(box)["lifted_at"] == after["lifted_at"], again.stdout


@pytest.mark.parametrize("case", ["not-owner", "sdk-seat", "detached", "unprovable-chain"])
def test_lift_is_refused_for_every_other_caller(tmp_path: Path, case: str) -> None:
    """A session that is not the merge owner's, a headless `sdk-*` seat (refused before its inherited CLAUDE_AGENT is
    read), a process with no claude ancestor and no terminal (setsid, systemd-run), and a chain that cannot be walked
    to pid 1 are each refused with exit 3 and a `hibernate-lift-refused` ledger row; the marker stays unlifted."""
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    if case == "not-owner":
        box.session(9001, "s-infra", hub, "infra", env_agent="infra")
        box.process(os.getpid(), 9001)
    elif case == "sdk-seat":
        box.session(9001, "s-hub", hub, "fabrik-64", env_agent="coordinator")
        box.session(
            9002,
            "s-seat",
            hub,
            "fabrik-77",
            entrypoint="sdk-cli",
            env_agent="coordinator",
            ppid=9001,
        )
        box.process(os.getpid(), 9002)
    elif case == "detached":
        box.process(os.getpid(), 1)
    # unprovable-chain: the caller's parent has no /proc entry, so the walk never reaches pid 1 — given a REAL
    # terminal, so only the unprovable chain (never the no-terminal rule) can refuse it
    assert box.run("mark", "--words", "w").returncode == 0
    env = {"FABRIK_DECISIONS_PY": _decisions_stub(tmp_path, "coordinator")}
    master, slave = pty.openpty()
    try:
        out = box.run(
            "lift", env=env, stdin=slave if case == "unprovable-chain" else subprocess.DEVNULL
        )
    finally:
        os.close(slave)
        os.close(master)
    assert out.returncode == 3, (out.stdout, out.stderr)
    assert "lifted_at" not in _marker(box)
    rows = _rows(box, "hibernate-lift-refused")
    assert len(rows) == 1 and isinstance(rows[0].get("ts"), float), rows
    if case == "unprovable-chain":
        assert "unprovable" in rows[0]["why"], rows
    assert box.run("paused").returncode == 0


def test_a_plain_shell_lift_passes_and_writes_its_terminal_row(tmp_path: Path) -> None:
    """With no claude session on the chain to pid 1 and a terminal on stdin, the lift passes as the operator's
    plain shell, and the rotate ledger gains a `hibernate-lift-shell` row naming that terminal."""
    box = Box(tmp_path)
    assert box.run("mark", "--words", "w").returncode == 0
    out, tty = _shell_lift(box)
    assert out.returncode == 0, (out.stdout, out.stderr)
    assert _marker(box)["lift_path"] == "hub"
    rows = _rows(box, "hibernate-lift-shell")
    assert len(rows) == 1 and rows[0]["tty"] == tty and tty.startswith("/dev/"), rows


def test_no_env_var_fakes_the_terminal(tmp_path: Path) -> None:
    """The plain-shell pass reads the REAL stdin: an environment variable claiming a terminal (the retired
    FABRIK_LIFT_TTY seam, or any other) on a pipe stdin is a detached caller — refused with exit 3 and a row."""
    box = Box(tmp_path)
    box.process(os.getpid(), 1)
    assert box.run("mark", "--words", "w").returncode == 0
    out = box.run("lift", env={"FABRIK_LIFT_TTY": "/dev/pts/7"}, stdin=subprocess.PIPE)
    assert out.returncode == 3, (out.stdout, out.stderr)
    assert "lifted_at" not in _marker(box) and _rows(box, "hibernate-lift-shell") == []
    assert len(_rows(box, "hibernate-lift-refused")) == 1


def test_brief_deadline_names_t3_and_t_as_clock_times(tmp_path: Path) -> None:
    """`brief --deadline` names T-3 and T (the marked deadline) as clock times, and the agent text no longer says
    the exit means the box slept; with no deadline marked it refuses."""
    box = Box(tmp_path)
    assert box.run("brief", "--role", "agent", "--words", "w", "--deadline").returncode == 2
    assert box.run("mark", "--words", "w", "--deadline", "10m").returncode == 0
    t = _marker(box)["deadline_at"]
    out = box.run("brief", "--role", "agent", "--words", "w", "--deadline")
    assert out.returncode == 0, out.stderr
    t3, tt = (time.strftime("%H:%M", time.gmtime(x)) for x in (t - 180, t))
    assert f"T-3 at {t3}" in out.stdout and f"T at {tt}" in out.stdout, out.stdout
    assert "Exit 0 means the box slept" not in out.stdout
    assert "Exit 2: it cannot tell — stay paused and tell the hub coordinator" in out.stdout  # G5
    coord = box.run("brief", "--role", "coordinator", "--words", "w", "--deadline").stdout
    assert out.stdout in coord
    plain = box.run("brief", "--role", "agent", "--words", "w").stdout
    assert "T-3 at" not in plain and "Exit 0 means the box slept" not in plain


def test_the_run_record_filename_is_command_runs_own() -> None:
    """status and woke find a session's run record under the name command_run.py writes it (`_safe_sid`)."""
    hib, cr = _load("hib_probe", HIB), _load("cr_probe", COMMAND_RUN)
    for sid in ("66b5e327-a366-4213-99e6-e362925e6142", "abc.xyz", "abc xyz", "", "a/b", "ü"):
        assert hib._safe_sid(sid) == cr._safe_sid(sid), sid


# ── review pass 1 (F1-F13) ───────────────────────────────────────────────────────────────────────────────────────


def _lifted_marker(box: Box, **extra: object) -> None:
    now = time.time()
    m = {"paused_at": now - 3600, "words": "w", "lifted_at": now - 60, "lift_path": "hub", **extra}
    (box.state / "hibernate.json").write_text(json.dumps(m), encoding="utf-8")


def test_f1_the_resolver_seam_is_honoured_only_under_a_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1: outside a test, FABRIK_DECISIONS_PY never names the owner — a stub naming the caller does not pass (the
    hub's real decisions.py answers); under a test the same stub does."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    hib = _load("hib_f1_probe", HIB)
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    box.session(9001, "s-infra", hub, "infra", env_agent="infra")
    monkeypatch.setattr(hib.os, "getppid", lambda: 9001)
    monkeypatch.setenv("FABRIK_DECISIONS_PY", _decisions_stub(tmp_path, "infra"))
    hub_stub = tmp_path / "hub-decisions-stub.py"  # hermetic: never the live ledger's owner (G9)
    hub_stub.write_text("print('coordinator')\n", encoding="utf-8")
    monkeypatch.setattr(hib, "HUB_DECISIONS", hub_stub)
    hib.update_marker(box.home, lambda _old: {"paused_at": time.time(), "words": "w"})
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    rc, msg = hib.lift(box.home, box.proc, str(box.opt))
    assert rc == 3, msg
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "fixture")
    rc, msg = hib.lift(box.home, box.proc, str(box.opt))
    assert rc == 0, msg


def test_f2_lift_reads_the_real_proc_and_home_only_outside_a_test(tmp_path: Path) -> None:
    """F2: outside a test, `lift --proc <other>` or `--home <other>` is refused (exit 2) before anything is read."""
    box = Box(tmp_path)
    assert box.run("mark", "--words", "w").returncode == 0
    out = box.run("lift", under_pytest=False)
    assert out.returncode == 2 and "real /proc and home only" in out.stderr, (
        out.stdout,
        out.stderr,
    )
    out = box.run("lift", under_pytest=False, proc="/proc")
    assert out.returncode == 2 and "real /proc and home only" in out.stderr, (
        out.stdout,
        out.stderr,
    )
    # G3: no --home at all, only a forged --proc
    out = box.run("lift", under_pytest=False, home_arg=False)
    assert out.returncode == 2 and "real /proc and home only" in out.stderr, (
        out.stdout,
        out.stderr,
    )
    assert "lifted_at" not in _marker(box)
    # G7: every forged-root refusal leaves its ledger row
    rows = _rows(box, "hibernate-lift-refused")
    assert len(rows) == 3 and all("forged" in r["why"] for r in rows), rows


def test_g1_a_null_lifted_or_deadline_is_absent(tmp_path: Path) -> None:
    """G1: a present-but-null `lifted_at` or `deadline_at` is absent, never corrupt."""
    box = Box(tmp_path)
    for m in ('{"paused_at": 1, "lifted_at": null}', '{"paused_at": 1, "deadline_at": null}'):
        (box.state / "hibernate.json").write_text(m, encoding="utf-8")
        out = box.run("paused")
        assert out.returncode == 0, (m, out.stdout, out.stderr)


def _pw(monkeypatch: pytest.MonkeyPatch, hib, home: Path) -> None:
    """The passwd entry names `home`, whatever $HOME says."""
    monkeypatch.setattr(hib.pwd, "getpwuid", lambda _uid: type("PW", (), {"pw_dir": str(home)})())


def test_g2_a_plain_lift_uses_the_passwd_home_whatever_home_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2/H2/H3: outside a test, `lift` with no --home/--proc is never refused as forged because $HOME differs from
    the passwd home — and it READS the passwd home (a spy on `live_sessions`), never $HOME. Hermetic: no live
    sessions, no live decisions.py."""
    passwd_home = tmp_path / "passwd-home"
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ROTATE_LEDGER_FALLBACK", str(tmp_path / "fallback.jsonl"))
    monkeypatch.setenv("HOME", str(tmp_path / "not-the-passwd-home"))
    hib = _load("hib_g2_probe", HIB)
    _pw(monkeypatch, hib, passwd_home)
    seen: list[Path] = []
    monkeypatch.setattr(
        hib, "live_sessions", lambda home, proc, opt="/opt": seen.append(home) or []
    )
    stub = tmp_path / "hub-decisions-stub.py"
    stub.write_text("print('coordinator')\n", encoding="utf-8")
    monkeypatch.setattr(hib, "HUB_DECISIONS", stub)
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    monkeypatch.setattr(
        hib, "_terminal", lambda: ""
    )  # under `-s` stdin is a real terminal and `lift` would pass
    hib.update_marker(passwd_home, lambda _old: {"paused_at": time.time(), "words": "w"})
    rc = hib.main(["lift"])
    assert rc == 3, (
        rc
    )  # reached the caller check (refused: no terminal, no session) — never the forged-root exit 2
    assert seen == [passwd_home], seen


def test_h1_every_verb_defaults_to_the_one_passwd_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H1: with $HOME != the passwd home and ROTATE_STATE_DIR unset, `mark`, `lift` and `paused` all use the passwd
    home's marker — the lift lands."""
    passwd_home, env_home = tmp_path / "passwd-home", tmp_path / "env-home"
    monkeypatch.delenv("ROTATE_STATE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(env_home))
    hib = _load("hib_h1_probe", HIB)
    _pw(monkeypatch, hib, passwd_home)
    caller = {"sid": "s", "agent": "infra", "entrypoint": "cli", "pid": 1}
    monkeypatch.setattr(hib, "live_sessions", lambda home, proc, opt="/opt": [])
    monkeypatch.setattr(hib, "_caller", lambda proc, sessions: (caller, ""))
    monkeypatch.setattr(hib, "merge_owner", lambda hub, resolver=None, **kw: ("infra", ""))
    assert hib.main(["mark", "--words", "w"]) == 0
    assert (passwd_home / ".claude" / "state" / "hibernate.json").exists()
    assert not (env_home / ".claude" / "state" / "hibernate.json").exists()
    assert hib.main(["lift"]) == 0
    assert hib.main(["paused"]) == 1  # lifted, read from the same home


def _stub_resolver(tmp_path: Path, body: str) -> Path:
    stub = tmp_path / "stub_decisions.py"
    stub.write_text("import sys, time\n" + body + "\n", encoding="utf-8")
    return stub


def _ledgered_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "DECISIONS.md").write_text("# ledger\n", encoding="utf-8")
    return repo


def test_merge_owner_reads_decisions_at_call_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Merge review O-C1: with no resolver passed, `merge_owner` reads the module's DECISIONS when it RUNS (master's
    late binding), so a patched DECISIONS is the resolver used — never the path frozen at import."""
    hib = _load("hib_late_binding", HIB)
    # the stub names an owner; the real decisions.py names none on this owner-less ledger
    monkeypatch.setattr(hib, "DECISIONS", _stub_resolver(tmp_path, "print('stub-owner')"))
    assert hib.merge_owner(str(_ledgered_repo(tmp_path))) == (
        "stub-owner",
        "the ledger's merge owner",
    )


def test_merge_owner_runs_the_given_resolver_under_the_given_timeout(tmp_path: Path) -> None:
    """Merge review C1/C4: a resolver passed positionally AND a keyword timeout both apply — a resolver that outlives
    the timeout is a failed lookup (fail closed: not "no owner"), never a hang."""
    hib = _load("hib_resolver_timeout", HIB)
    repo = str(_ledgered_repo(tmp_path))
    slow = _stub_resolver(tmp_path, "time.sleep(5)")
    t0 = time.monotonic()
    name, why = hib.merge_owner(repo, slow, timeout=0.5)
    assert time.monotonic() - t0 < 4
    assert name == "" and why.startswith("lookup failed") and why not in hib.NO_OWNER


def test_merge_owner_reads_an_empty_answer_as_a_failed_lookup(tmp_path: Path) -> None:
    """Merge review C5: a resolver that exits 0 and prints nothing names no owner — the why says the lookup failed,
    never "the ledger's merge owner" with an empty name (which `lift` would print as its refusal reason)."""
    hib = _load("hib_empty_answer", HIB)
    name, why = hib.merge_owner(
        str(_ledgered_repo(tmp_path)), _stub_resolver(tmp_path, "sys.exit(0)")
    )
    assert name == "" and why.startswith("lookup failed") and why not in hib.NO_OWNER


def test_g6_a_lift_older_than_the_mark_is_no_resume(tmp_path: Path) -> None:
    """Review G6: a `lifted_at` before the CURRENT mark is the last pause's lift — `woke` is 1 and says the pause is not
    lifted yet, never RESUME (the `lifted_at < paused_at` half of the guard; `is None` alone lets it through)."""
    box = Box(tmp_path)
    assert box.run("mark", "--words", "w").returncode == 0
    m = _marker(box)
    m["lifted_at"] = m["paused_at"] - 1
    m["lift_path"] = "sleep"
    (box.state / "hibernate.json").write_text(json.dumps(m), encoding="utf-8")
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "is not lifted yet" in out.stdout, (out.stdout, out.stderr)


def test_h4_h5_a_null_paused_at_or_a_bad_deadline_is_corrupt(tmp_path: Path) -> None:
    """H4/H5: a PRESENT `paused_at` that is null is corrupt (`paused` exit 0 — held, review G4 — and `woke` 2), never
    "not paused"; a non-numeric `deadline_at` is corrupt too."""
    box = Box(tmp_path)
    for m in (
        '{"paused_at": null, "words": "w"}',
        '{"paused_at": 1, "deadline_at": "x"}',
    ):
        (box.state / "hibernate.json").write_text(m, encoding="utf-8")
        assert box.run("paused").returncode == 0, m  # corrupt holds the launchers (G4)
        if "null" in m:
            assert box.run("woke", "--self", "s1").returncode == 2, m


def test_h6_the_forged_root_refusal_row_lands_in_the_real_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H6: outside a test, `lift --home <other>` is exit 2 and its `hibernate-lift-refused` row lands in the passwd
    home's ledger, not under the forged --home."""
    passwd_home, forged = tmp_path / "passwd-home", tmp_path / "forged-home"
    monkeypatch.delenv("ROTATE_STATE_DIR", raising=False)
    monkeypatch.setenv("ROTATE_LEDGER_FALLBACK", str(tmp_path / "fallback.jsonl"))
    hib = _load("hib_h6_probe", HIB)
    _pw(monkeypatch, hib, passwd_home)
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    assert hib.main(["--home", str(forged), "lift"]) == 2
    ledger = passwd_home / ".claude" / "state" / "rotate-ledger.jsonl"
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["hibernate-lift-refused"], rows
    assert not (forged / ".claude" / "state" / "rotate-ledger.jsonl").exists()


def test_g4_a_held_ledger_lock_never_hangs_lift(tmp_path: Path) -> None:
    """G4: a trim holding the ledger's exclusive lock delays a refused lift by the bound only; the row still lands."""
    import fcntl

    box = Box(tmp_path)
    ledger = box.state / "rotate-ledger.jsonl"
    ledger.write_text("", encoding="utf-8")
    with open(ledger, "rb") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        t0 = time.monotonic()
        out = box.run("lift", timeout=20)
        elapsed = time.monotonic() - t0
    assert out.returncode == 3 and elapsed < 10, (elapsed, out.stderr)
    assert len(_rows(box, "hibernate-lift-refused")) == 1


def test_f3_a_seat_pid_held_by_another_process_is_not_still_running(tmp_path: Path) -> None:
    """F3: with no procStart recorded, a seat's pid now held by a non-claude process (pid reuse) is not `still
    running`."""
    box = Box(tmp_path)
    sid = "s-f3"
    assert box.run("mark", "--words", "w").returncode == 0
    seeds = box.state / "command-runs" / "seeds"
    seeds.mkdir()
    box.process(4545, 1, comm="bash")
    (seeds / f"{sid}-paused-aaaa.json").write_text(
        json.dumps(
            {"command": "c", "phases": 1, "abandoned_seats": [{"pid": 4545, "purpose": "slice Z"}]}
        ),
        encoding="utf-8",
    )
    assert _shell_lift(box)[0].returncode == 0
    out = box.run("woke", "--self", sid)
    line = next(ln for ln in out.stdout.splitlines() if "slice Z" in ln)
    assert "exited, no output" in line, out.stdout


def test_f4_woke_honours_command_run_dir(tmp_path: Path) -> None:
    """F4: the run record and the seeds are read from $COMMAND_RUN_DIR (and its seeds/) when set, as command_run.py
    writes them."""
    box = Box(tmp_path)
    runs = tmp_path / "runs"
    (runs / "seeds").mkdir(parents=True)
    _lifted_marker(box)
    seed = runs / "seeds" / "s-f4-paused-aaaa.json"
    seed.write_text(json.dumps({"command": "fabrik-task", "phases": 6}), encoding="utf-8")
    env = {"COMMAND_RUN_DIR": str(runs)}
    out = box.run("woke", "--self", "s-f4", env=env)
    assert out.returncode == 0 and str(seed) in out.stdout, out.stdout
    (runs / "s-f4.json").write_text(json.dumps({"state": "running", "started_epoch": time.time()}))
    out = box.run("woke", "--self", "s-f4", env=env)
    assert out.returncode == 1 and "no pending resume" in out.stdout, out.stdout


@pytest.mark.parametrize("deadline", ["9" * 400, "25h", "179s", "2m"])
def test_f5_f7_an_unusable_deadline_is_refused_before_any_write(
    tmp_path: Path, deadline: str
) -> None:
    """F5/F7: a deadline over 24 h (or one no float can hold) or under T-3 (180 s) is exit 2 and writes nothing."""
    box = Box(tmp_path)
    out = box.run("mark", "--words", "w", "--deadline", deadline)
    assert out.returncode == 2 and "Traceback" not in out.stderr, (out.stdout, out.stderr)
    assert not (box.state / "hibernate.json").exists()
    assert box.run("mark", "--words", "w", "--deadline", "3m").returncode == 0


@pytest.mark.parametrize(
    "marker",
    ['{"paused_at": 1.0, "lifted_at": "soon"}', '{"paused_at": "x"}', "{", "[]"],
)
def test_f6_woke_exits_2_on_a_corrupt_marker(tmp_path: Path, marker: str) -> None:
    """F6: a marker `paused` calls corrupt (its stderr line; it holds the launchers with exit 0, review G4) is corrupt
    for `woke` too — exit 2 naming it, never `stay paused`."""
    box = Box(tmp_path)
    (box.state / "hibernate.json").write_text(marker, encoding="utf-8")
    p = box.run("paused")
    assert p.returncode == 0 and "hibernate.json" in p.stderr, (p.stdout, p.stderr)
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 2 and "hibernate.json" in out.stdout + out.stderr, (
        out.stdout,
        out.stderr,
    )


def test_f8_woke_exits_2_on_an_unreadable_run_record(tmp_path: Path) -> None:
    """F8: a run record that exists but cannot be parsed is exit 2 — `woke` cannot tell whether a run started after
    the lift, so it never answers RESUME."""
    box = Box(tmp_path)
    _lifted_marker(box)
    (box.state / "command-runs" / "s1.json").write_text("{", encoding="utf-8")
    out = box.run("woke", "--self", "s1")
    assert (
        out.returncode == 2
        and "cannot tell whether a run started after the lift" in out.stdout + out.stderr
    )


def test_f9_a_passing_lift_replaces_a_corrupt_marker(tmp_path: Path) -> None:
    """F9: a corrupt marker leaves `paused` at 2; a passing lift replaces it with a well-formed lifted marker and
    says so; a refused caller still changes nothing."""
    box = Box(tmp_path)
    path = box.state / "hibernate.json"
    path.write_text("{", encoding="utf-8")
    os.utime(path, (1_700_000_000, 1_700_000_000))
    assert box.run("lift").returncode == 3  # no terminal, no session: refused
    assert path.read_text(encoding="utf-8") == "{"
    out, _tty = _shell_lift(box)
    assert out.returncode == 0 and "unreadable" in out.stdout, (out.stdout, out.stderr)
    m = _marker(box)
    assert (
        m["paused_at"] == 1_700_000_000
        and m["lift_path"] == "hub"
        and m["lifted_at"] > m["paused_at"]
    ), m
    assert m["words"] == "(unreadable marker replaced by lift)"
    assert box.run("paused").returncode == 1


def test_f11_an_in_flight_tmp_seed_is_not_listed(tmp_path: Path) -> None:
    """F11: command_run's in-flight `<name>.<pid>.tmp` beside the seeds is never listed."""
    box = Box(tmp_path)
    _lifted_marker(box)
    seeds = box.state / "command-runs" / "seeds"
    seeds.mkdir()
    tmp = seeds / "s1-paused-aaaa.json.4242.tmp"
    tmp.write_text("{}", encoding="utf-8")
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 0 and str(tmp) not in out.stdout, out.stdout


def test_f12_an_unwritable_ledger_puts_the_row_in_the_fallback(tmp_path: Path) -> None:
    """F12: a ledger that cannot be created sends the refused-lift row to the fallback file and one stderr line."""
    box = Box(tmp_path)
    assert box.run("mark", "--words", "w").returncode == 0
    fallback = tmp_path / "fallback.jsonl"
    box.state.chmod(0o500)
    try:
        out = box.run("lift", env={"ROTATE_LEDGER_FALLBACK": str(fallback)})
    finally:
        box.state.chmod(0o700)
    assert out.returncode == 3, (out.stdout, out.stderr)
    rows = [json.loads(ln) for ln in fallback.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["hibernate-lift-refused"], rows
    assert "rotate ledger write failed" in out.stderr and str(fallback) in out.stderr, out.stderr
    assert (fallback.stat().st_mode & 0o777) == 0o600


def test_f13_a_lift_exactly_24h_old_is_no_pending_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F13: the RESUME window is less than 24 h — a lift exactly 24 h old answers 1, one second younger 0."""
    box = Box(tmp_path)
    monkeypatch.setenv("ROTATE_STATE_DIR", str(box.state))
    hib = _load("hib_f13_probe", HIB)
    (box.state / "hibernate.json").write_text(
        json.dumps({"paused_at": 1000.0, "words": "w", "lifted_at": 2000.0, "lift_path": "hub"}),
        encoding="utf-8",
    )
    assert hib.woke(box.home, box.proc, "s1", now=2000.0 + 24 * 3600)[0] == 1
    assert hib.woke(box.home, box.proc, "s1", now=2000.0 + 24 * 3600 - 1)[0] == 0


def test_g8_a_fifo_at_the_ledger_path_never_hangs_lift(tmp_path: Path) -> None:
    """G8: a FIFO with no reader standing at the ledger path never hangs a refused lift: it returns exit 3 within
    the bound and the row lands in the fallback file."""
    box = Box(tmp_path)
    os.mkfifo(box.state / "rotate-ledger.jsonl")
    fallback = tmp_path / "fallback.jsonl"
    out = box.run("lift", env={"ROTATE_LEDGER_FALLBACK": str(fallback)}, timeout=10)
    assert out.returncode == 3, (out.stdout, out.stderr)
    rows = [json.loads(ln) for ln in fallback.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["hibernate-lift-refused"], rows


def test_g8_the_torn_line_read_never_blocks_on_a_fifo(tmp_path: Path) -> None:
    """G8: the torn-line read itself meets a FIFO with no writer (one swapped in after the write side opened, which
    the end-to-end test above cannot stage: a FIFO with no reader already fails the write-side open) and returns at
    once, False, instead of blocking."""
    fifo = tmp_path / "rotate-ledger.jsonl"
    os.mkfifo(fifo)
    probe = (
        "import importlib.util; from pathlib import Path;"
        f"s = importlib.util.spec_from_file_location('hib_g8', {str(HIB)!r});"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m);"
        f"print(m._ledger_torn(Path({str(fifo)!r})))"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=10)
    assert out.returncode == 0 and out.stdout.strip() == "False", (out.stdout, out.stderr)


# ── T01b: the status checks ──────────────────────────────────────────────────────────────────────────────────────


def _clean_agent(box: Box, tmp_path: Path, pid: int, sid: str, name: str) -> Path:
    tree = tmp_path / "w" / name
    _git_repo(tree, tmp_path / "r" / f"{name}.git")
    box.session(pid, sid, str(tree), name, env_agent=name)
    return tree


def test_status_row_one_a_headless_session_blocks_before_t3_and_is_held_after(
    tmp_path: Path,
) -> None:
    """Check 1: an `sdk-*` session whose parent chain reaches no live agent is its own row; one that IS an agent's seat
    is not (check 2 counts it)."""
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 1001, "s-me", "me")
    box.ready("s-me")
    box.session(1002, "s-head", str(tmp_path), "h", entrypoint="sdk-cli")
    out = _status(box)
    assert out.returncode == 1 and "BLOCKS" in out.stdout and "headless" in out.stdout, out.stdout
    box.mark(deadline_in=100)  # inside T-3 (180 s)
    out = _status(box)
    assert out.returncode == 0 and "held (headless)" in out.stdout, out.stdout
    box.mark(deadline_in=1000)  # a marked pause that is still before T-3 blocks
    assert _status(box).returncode == 1


def test_status_row_two_live_seats_block_until_the_close_names_them(tmp_path: Path) -> None:
    """Check 2: an agent with a live `sdk-*` child blocks before T-3; from T-3 it blocks unless its closed record
    names at least as many abandoned seats, and the table lists them."""
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 1101, "s-me", "me")
    other = _clean_agent(box, tmp_path, 1102, "s-b", "builder")
    box.ready("s-me", "s-b")
    box.session(1103, "s-seat", str(other), "seat", entrypoint="sdk-cli", ppid=1102)
    out = _status(box)
    assert out.returncode == 1 and "1 live seat(s)" in out.stdout, out.stdout
    assert "headless" not in out.stdout, out.stdout  # an agent's seat is no headless row
    box.mark(deadline_in=100)
    out = _status(box)
    assert out.returncode == 1 and "1 live seat(s)" in out.stdout and "not named" in out.stdout, (
        out.stdout
    )
    abandoned = [{"purpose": "review seat A", "brief": "/b/a.md"}]
    seed = tmp_path / "seed.json"
    seed.write_text("{}", encoding="utf-8")
    box.closed("s-b", "blocked", time.time(), abandoned_seats=abandoned, resume_seed=str(seed))
    out = _status(box)
    assert out.returncode == 0, out.stdout
    assert "abandoned seat: review seat A (/b/a.md)" in out.stdout, out.stdout
    box.closed("s-b", "blocked", time.time(), abandoned_seats=[])
    assert _status(box).returncode == 1


def test_status_row_three_names_up_to_five_uncommitted_paths_then_the_rest(tmp_path: Path) -> None:
    box = Box(tmp_path)
    me = _clean_agent(box, tmp_path, 1201, "s-me", "me")
    box.ready("s-me")
    for i in range(7):
        (me / f"f{i}.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=me, check=True)
    out = _status(box)
    assert (
        "7 uncommitted change(s): f0.txt, f1.txt, f2.txt, f3.txt, f4.txt +2 more" in out.stdout
    ), out.stdout
    assert "f5.txt" not in out.stdout, out.stdout


def test_status_row_four_header_names_the_pause_t3_t_and_the_time_left(tmp_path: Path) -> None:
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 1301, "s-me", "me")
    box.ready("s-me")
    out = _status(box)
    assert "PAUSE" not in out.stdout, out.stdout  # no mark, no header
    box.mark(deadline_in=600)
    out = _status(box)
    head = out.stdout.splitlines()[0]
    assert head.startswith("PAUSE marked") and "close the lid" in head, out.stdout
    assert "T-3 at " in head and ", T at " in head and "left" in head, head
    js = json.loads(box.run("status", "--json", "--self", "s-me").stdout)
    assert js["header"] == head, js


def test_status_row_five_a_blocked_close_after_the_mark_needs_a_seed(tmp_path: Path) -> None:
    """Check 5, with 1 s of slack for command_run's whole-second `updated_ts`; `done` after the mark is its own row."""
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 1401, "s-me", "me")
    _clean_agent(box, tmp_path, 1402, "s-b", "builder")
    box.ready("s-me", "s-b")
    box.mark(deadline_in=1000)
    paused_at = json.loads((box.state / "hibernate.json").read_text())["paused_at"]
    box.closed("s-b", "blocked", paused_at - 5)  # closed before the mark: not this pause's
    assert "no resume seed" not in _status(box).stdout
    box.closed(
        "s-b", "blocked", paused_at - 0.5
    )  # whole-second flooring: updated_ts + 1 >= floor(paused_at)
    out = _status(box)
    assert "BLOCKS" in out.stdout and "no resume seed" in out.stdout, out.stdout
    seed = tmp_path / "seed.json"
    seed.write_text("{}", encoding="utf-8")
    box.closed("s-b", "blocked", paused_at + 1, resume_seed=str(seed))
    assert "no resume seed" not in _status(box).stdout
    box.closed("s-b", "handoff", paused_at + 1, resume_copy=str(tmp_path / "gone.md"))
    assert "no resume seed" in _status(box).stdout  # a seed path that does not read is no seed
    box.closed("s-b", "done", paused_at + 1)
    out = _status(box)
    assert "done since the mark — verify" in out.stdout and "no resume seed" not in out.stdout, (
        out.stdout
    )
    done_row = next(ln for ln in out.stdout.splitlines() if "done since the mark" in ln)
    assert done_row.startswith("ok"), done_row


def test_status_row_six_an_unarmed_self_watch_blocks_even_outside_opt(tmp_path: Path) -> None:
    box = Box(tmp_path)
    me = _clean_agent(box, tmp_path, 1501, "s-me", "me")
    box.heartbeat()
    out = _status(box)  # the lock dir does not exist at all
    assert out.returncode == 1 and "self-watch not armed" in out.stdout, out.stdout
    box.arm("s-me")
    assert _status(box).returncode == 0
    # a lock file nobody holds is a watch that died
    (box.locks / "s-out.selfwatch.lock").write_text("", encoding="utf-8")
    _clean_agent(box, tmp_path, 1502, "s-out", "outsider")
    out = _status(box)
    assert out.returncode == 1 and "self-watch not armed" in out.stdout, out.stdout
    assert any("outside /opt" in ln and "BLOCKS" in ln for ln in out.stdout.splitlines()), (
        out.stdout
    )
    # the name the watcher writes is the tick's transform: a session id with unsafe characters
    box.session(1503, "s/odd id", str(me), "odd", env_agent="odd")
    box.arm("s_odd_id")
    out = _status(box)
    assert next(ln for ln in out.stdout.splitlines() if " odd " in ln).startswith("ok"), out.stdout


def test_status_blocks_with_no_minute_cron(tmp_path: Path) -> None:
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 1601, "s-me", "me")
    box.arm("s-me")
    out = _status(box)  # absent
    assert out.returncode == 1 and "no minute cron" in out.stdout, out.stdout
    box.heartbeat(age=200)
    assert "no minute cron" in _status(box).stdout
    box.heartbeat(age=100)
    out = _status(box)
    assert out.returncode == 0 and "no minute cron" not in out.stdout, out.stdout
    (box.state / "battery-tick-last").write_text("garbage\n", encoding="utf-8")
    assert "no minute cron" in _status(box).stdout


def test_status_says_safe_only_after_two_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tree dirtied in the gap between the two reads turns the first SAFE into NOT SAFE."""
    box = Box(tmp_path)
    me = _clean_agent(box, tmp_path, 1701, "s-me", "me")
    box.ready("s-me")
    hib = _load("hib_two_reads", HIB)
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(box.locks))
    monkeypatch.setenv("ROTATE_STATE_DIR", str(box.state))
    gaps: list[float] = []

    def dirty(gap: float) -> None:
        gaps.append(gap)
        (me / "late.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "late.txt"], cwd=me, check=True)

    args = (box.home, box.proc, "s-me", str(box.opt))
    rc, rows = hib.status_confirmed(*args, gap=5.0, sleep=dirty)
    assert gaps == [5.0] and rc == 1, (gaps, rc, rows)
    gaps.clear()
    rc, _ = hib.status_confirmed(*args, gap=5.0, sleep=gaps.append)
    assert rc == 1 and gaps == []  # a first read that blocks needs no second
    subprocess.run(["git", "reset", "-q", "--hard"], cwd=me, check=True)
    rc, _ = hib.status_confirmed(*args, gap=5.0, sleep=gaps.append)
    assert rc == 0 and gaps == [5.0]


def test_a_uid_with_no_passwd_entry_reads_the_marker_under_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T01a review P4-keyerror: `getpwuid` raising KeyError falls back to `~`; `paused` never exits 1 on that error."""
    monkeypatch.delenv("ROTATE_STATE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    hib = _load("hib_keyerror", HIB)

    def no_entry(_uid: int) -> None:
        raise KeyError("getpwuid(): uid not found")

    monkeypatch.setattr(hib.pwd, "getpwuid", no_entry)
    state = tmp_path / ".claude" / "state"
    state.mkdir(parents=True)
    (state / "hibernate.json").write_text(json.dumps({"paused_at": time.time(), "words": "w"}))
    assert hib.main(["paused"]) == 0


def test_the_armed_name_transform_is_the_ticks_own() -> None:
    """`_selfwatch_safe` is a copy of `claude_rotate.py`'s (the watcher's `tr | head -c 64`); the two must agree."""
    hib = _load("hib_safe_probe", HIB)
    rot = _load("rot_safe_probe", ROOT / "scripts" / "sysadmin" / "claude_rotate.py")
    for sid in ("s-me", "s/odd id", "é-ü", "x" * 90, "a b\tc", ""):
        assert hib._selfwatch_safe(sid) == rot._selfwatch_safe(sid), sid


# ── T01b wave-2 review fixes ─────────────────────────────────────────────────────────────────────────────────────


def test_k1_no_passwd_entry_and_no_home_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no passwd entry and no $HOME, `~` stays literal and the marker would resolve against the cwd: `woke` and
    `lift` exit 2 instead, and `paused` exits 0 — held, since its callers read 2 as "proceed" (review N1)."""
    monkeypatch.delenv("ROTATE_STATE_DIR", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    hib = _load("hib_k1", HIB)

    def no_entry(_uid: int) -> None:
        raise KeyError("uid not found")

    monkeypatch.setattr(hib.pwd, "getpwuid", no_entry)
    state = tmp_path / "~" / ".claude" / "state"  # where a relative "~" would land
    state.mkdir(parents=True)
    (state / "hibernate.json").write_text(json.dumps({"paused_at": time.time(), "words": "w"}))
    # `paused` holds instead (review N1): launchers read every non-0 as "proceed", so a home it cannot resolve is
    # PAUSED (exit 0) with its one stderr line; `woke` and `lift` still refuse with 2
    assert hib.main(["paused"]) == 0
    for argv in (["woke"], ["lift"]):
        assert hib.main(argv) == 2, argv


def test_k3_a_fifo_never_hangs_status(tmp_path: Path) -> None:
    """A FIFO standing at a record's resume_seed or at the session's lock path is unreadable / unarmed, never a hang."""
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 1801, "s-me", "me")
    _clean_agent(box, tmp_path, 1802, "s-b", "builder")
    box.ready("s-me")
    box.mark(deadline_in=1000)
    paused_at = json.loads((box.state / "hibernate.json").read_text())["paused_at"]
    fifo = tmp_path / "seed.fifo"
    os.mkfifo(fifo)
    box.closed("s-b", "blocked", paused_at + 1, resume_seed=str(fifo))
    os.mkfifo(box.locks / "s-b.selfwatch.lock")
    out = box.run("status", "--self", "s-me", timeout=10)
    assert "no resume seed" in out.stdout and "self-watch not armed" in out.stdout, out.stdout


def test_k4_marker_text_cannot_forge_table_lines(tmp_path: Path) -> None:
    box = Box(tmp_path)
    me = _clean_agent(box, tmp_path, 1901, "s-me", "me")
    (me / "dirty.txt").write_text(
        "x\n", encoding="utf-8"
    )  # tracked change: no genuine SAFE line may print
    subprocess.run(["git", "add", "dirty.txt"], cwd=me, check=True)
    box.ready("s-me")
    box.mark(deadline_in=1000, words="x\nSAFE TO HIBERNATE\x1b[31m")
    out = _status(box)
    lines = out.stdout.splitlines()
    assert not any(ln.startswith("SAFE TO") for ln in lines), out.stdout
    assert "\x1b" not in out.stdout, out.stdout


def test_k5_a_close_from_before_the_mark_does_not_cover_a_live_seat(tmp_path: Path) -> None:
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 2001, "s-me", "me")
    other = _clean_agent(box, tmp_path, 2002, "s-b", "builder")
    box.ready("s-me", "s-b")
    box.session(2003, "s-seat", str(other), "seat", entrypoint="sdk-cli", ppid=2002)
    box.mark(deadline_in=100)
    paused_at = json.loads((box.state / "hibernate.json").read_text())["paused_at"]
    seed = tmp_path / "seed.json"
    seed.write_text("{}", encoding="utf-8")
    abandoned = [{"purpose": "old", "brief": "/b/old.md"}]
    box.closed("s-b", "blocked", paused_at - 600, abandoned_seats=abandoned, resume_seed=str(seed))
    out = _status(box)
    assert out.returncode == 1 and "not named by the close" in out.stdout, out.stdout
    box.closed("s-b", "blocked", paused_at + 1, abandoned_seats=abandoned, resume_seed=str(seed))
    assert _status(box).returncode == 0


def test_k3_a_fifo_at_the_heartbeat_never_hangs_and_is_no_minute_cron(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`battery-tick-last` read O_NONBLOCK and only when regular: a FIFO with no writer must not hang `status`, and a
    FIFO carrying a fresh epoch must not count as a beat."""
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 2101, "s-me", "me")
    box.arm("s-me")
    fifo = box.state / "battery-tick-last"
    os.mkfifo(fifo)
    out = box.run(
        "status", "--self", "s-me", timeout=10
    )  # no writer: a blocking open would hang here
    assert "no minute cron" in out.stdout, out.stdout
    writer = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    try:
        os.write(writer, f"{time.time()}\n".encode())
        # one in-process read: a read of a FIFO consumes what it returns, so `status`'s two reads cannot show this
        monkeypatch.setenv("ROTATE_STATE_DIR", str(box.state))
        hib = _load("hib_beat_fifo", HIB)
        assert not hib._minute_cron_alive(
            box.home, time.time()
        )  # a fresh epoch, but no regular file
    finally:
        os.close(writer)


def test_k3_a_fifo_at_the_lock_path_is_not_armed_even_when_flocked(tmp_path: Path) -> None:
    """A lock path that is no regular file is never an armed watch, whoever holds a flock on it."""
    box = Box(tmp_path)
    _clean_agent(box, tmp_path, 2201, "s-me", "me")
    box.heartbeat()
    box.locks.mkdir()
    fifo = box.locks / "s-me.selfwatch.lock"
    os.mkfifo(fifo)
    out = box.run("status", "--self", "s-me", timeout=10)  # no writer: must not hang
    assert "self-watch not armed" in out.stdout, out.stdout
    holder = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX)
        out = box.run("status", "--self", "s-me", timeout=10)
        assert "self-watch not armed" in out.stdout, out.stdout
    finally:
        os.close(holder)


def test_lift_prints_rotation_offers_and_survives_their_fault(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """W-f975fee0 slice 3: once the pause is lifted, `lift` offers `rotate-session` for every live agent at/past the
    threshold; a fault in the offer never fails the lift. The caller is the hub merge owner's session (W-6e656dac
    T01a: `lift` is refused for every other caller), in the subprocess and in-process alike."""
    box = Box(tmp_path)
    hub = box.repo("fabrik", "coordinator")
    box.session(9001, "s-hub", hub, "fabrik-64", env_agent="coordinator")
    box.process(os.getpid(), 9001)
    stub = _decisions_stub(tmp_path, "coordinator")
    repo = box.repo("r1", "coordinator")
    sid = "33333333-3333-4333-8333-333333333333"
    box.session(4242, sid, repo, "dev1-peer", env_agent="dev1")
    tr = box.home / ".claude" / "projects" / "-r1" / f"{sid}.jsonl"
    tr.parent.mkdir(parents=True)
    tr.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"model": "m", "usage": {"cache_read_input_tokens": 450000}},
            }
        )
        + "\n"
    )
    assert box.run("mark", "--words", "w").returncode == 0
    out = box.run(
        "lift",
        env={"FABRIK_DECISIONS_PY": stub, "SESSION_ARCHIVE_ENV_FILE": str(tmp_path / "none.env")},
    )
    assert out.returncode == 0, out.stderr
    assert "rotation offers" in out.stdout, out.stdout
    assert f"rotate-session dev1 --repo {repo} --trigger lift" in out.stdout, out.stdout
    hib = _load("hibernate_lift_fault", HIB)
    monkeypatch.setenv("ROTATE_STATE_DIR", str(box.state))  # where box.run marks
    monkeypatch.setenv("FABRIK_DECISIONS_PY", stub)
    monkeypatch.setattr(hib.os, "getppid", lambda: 9001)
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp_path / "none.env"))
    argv = ["--home", str(box.home), "--proc", str(box.proc), "--opt", str(box.opt), "lift"]
    real_loader = hib._load_rotate
    box.run("mark", "--words", "w2")

    def boom():
        raise RuntimeError("offer loader broke")

    monkeypatch.setattr(hib, "_load_rotate", boom)
    capsys.readouterr()
    rc = hib.main(argv)
    marker = _marker(box)
    assert rc == 0 and marker["lifted_at"] >= marker["paused_at"], marker
    assert "rotation offers unavailable" in capsys.readouterr().err
    # review B1/B2: a fault past the loader — SystemExit inside due(), or one raised while printing — never fails it
    for fault in (SystemExit(3), UnicodeEncodeError("utf-8", "x", 0, 1, "surrogate")):

        class Rs:
            @staticmethod
            def due(*a, _f=fault, **k):
                raise _f

        box.run("mark", "--words", "w3")
        monkeypatch.setattr(hib, "_load_rotate", lambda: Rs)
        assert hib.main(argv) == 0
        assert "rotation offers unavailable" in capsys.readouterr().err
    # a REFUSED lift offers nothing: the offers follow only a lift that exited 0. The REAL loader, so an offer
    # wrongly made would print dev1's line on stdout (the subprocess run above proves it would)
    box.run("mark", "--words", "w4")
    monkeypatch.setattr(hib, "_load_rotate", real_loader)
    monkeypatch.setattr(hib.os, "getppid", lambda: 4242)  # dev1's session: not the merge owner
    capsys.readouterr()
    assert hib.main(argv) == 3
    cap = capsys.readouterr()
    assert "rotation offers" not in cap.out + cap.err, (cap.out, cap.err)
