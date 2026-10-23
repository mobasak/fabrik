"""hibernate.py (W-1e9ae1e5): who gets the pause, when the box is safe, and how a woken agent knows it slept.

Driven against a fixture HOME (session records, identity store, run records, rotate ledger, the pause marker), a
fixture /proc root and a fixture /opt root whose repos carry their own ledgers, so no test reads the operator's live
sessions or a live ledger; `status` runs real git in throwaway repos, and the pause text's close forms run through the
real command_run.py against a fixture state dir.
"""

from __future__ import annotations

import importlib.util
import json
import os
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

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(HIB),
                "--home",
                str(self.home),
                "--proc",
                str(self.proc),
                "--opt",
                str(self.opt),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={"PATH": "/usr/bin:/bin", "HOME": str(self.home)},
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
    box.run_record("s-me", "running", command="hibernate")
    out = _status(box)
    assert out.returncode == 0 and "(you)" in out.stdout, out.stdout
    pool = tmp_path / "pool"
    pool.mkdir()  # not a git checkout: as a row it would block
    box.session(702, "s-pool", str(pool), "p", entrypoint="sdk-cli")
    assert _status(box).returncode == 0
    box.session(703, "s-new", str(pool), "n", entrypoint="desktop-2027")
    assert _status(box).returncode == 1
    (me / "x.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "x.txt"], cwd=me, check=True)
    out = _status(box)
    assert "1 uncommitted change(s) (you)" in out.stdout, out.stdout


def test_status_exempts_only_the_callers_own_top_frame_hibernate_run(tmp_path: Path) -> None:
    """Only the caller's own TOP-frame /hibernate run is exempt: any other run of the caller, or a running parent
    frame under its /hibernate run, would stay running across the sleep and blocks."""
    box = Box(tmp_path)
    me = tmp_path / "me"
    _git_repo(me, tmp_path / "me.git")
    box.session(751, "s-me", str(me), "me", env_agent="me")
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


def test_woke_answers_only_for_a_wake_after_the_current_mark(tmp_path: Path) -> None:
    """`woke` is 0 only after a resume-wake row (any gap: the tick already applied its threshold) or the hub's lift
    that came AFTER the current mark; a wake before the mark, another event's row, no mark, and a session whose run
    started again after the wake all answer 1; a corrupt start time never stops a resume."""
    box = Box(tmp_path)
    assert box.run("woke", "--self", "s1").returncode == 1  # no mark
    assert box.run("mark", "--words", "we need to hibernate").returncode == 0
    paused = json.loads((box.home / ".claude" / "state" / "hibernate.json").read_text())[
        "paused_at"
    ]
    _ledger(
        box,
        {"event": "resume-wake", "ts": paused - 100, "gap_s": 9000},
        {"event": "hold-lifted", "ts": paused + 1, "gap_s": 9000},
    )
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "stay paused" in out.stdout, out.stdout
    _ledger(box, {"event": "resume-wake", "ts": paused + 0.001, "gap_s": 750})
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 0 and out.stdout.startswith("RESUME — the box slept 750 s"), out.stdout
    box.run_record(
        "s1", "running", started=paused - 50
    )  # running since BEFORE the wake: not resumed
    assert box.run("woke", "--self", "s1").returncode == 0
    box.run_record("s1", "running", started="x")
    assert box.run("woke", "--self", "s1").returncode == 0
    box.run_record(
        "s1", "running", started=float("inf")
    )  # json writes Infinity; it never blocks a resume
    assert box.run("woke", "--self", "s1").returncode == 0
    box.run_record("s1", "running", started=paused + 120)
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "already resumed" in out.stdout, out.stdout
    time.sleep(0.05)  # a second hibernate: the first wake no longer counts
    assert box.run("mark", "--words", "again").returncode == 0
    assert box.run("woke", "--self", "s2").returncode == 1


def test_lift_ends_a_pause_with_no_resume_wake_row(tmp_path: Path) -> None:
    """The hub's `lift` is a wake for every paused agent when no resume-wake row came (no sleep, or a sleep during a
    quota hold); with no mark it refuses."""
    box = Box(tmp_path)
    assert box.run("lift").returncode == 1
    box.run("mark", "--words", "w")
    assert box.run("woke", "--self", "s1").returncode == 1
    assert box.run("lift").returncode == 0
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 0 and "lifted by the hub" in out.stdout, out.stdout


def test_a_lift_after_the_real_wake_never_re_resumes_a_resumed_agent(tmp_path: Path) -> None:
    """The hub always lifts once awake, AFTER the resume-wake row: an agent whose run started between the two has
    resumed, and the later lift does not tell it to resume again."""
    box = Box(tmp_path)
    box.run("mark", "--words", "w")
    paused = json.loads((box.home / ".claude" / "state" / "hibernate.json").read_text())[
        "paused_at"
    ]
    _ledger(box, {"event": "resume-wake", "ts": paused + 0.001, "gap_s": 3600})
    box.run_record("s1", "running", started=paused + 0.002)
    assert box.run("woke", "--self", "s1").returncode == 1
    time.sleep(0.05)
    assert box.run("lift").returncode == 0
    out = box.run("woke", "--self", "s1")
    assert out.returncode == 1 and "already resumed" in out.stdout, out.stdout


def test_the_run_record_filename_is_command_runs_own() -> None:
    """status and woke find a session's run record under the name command_run.py writes it (`_safe_sid`)."""
    hib, cr = _load("hib_probe", HIB), _load("cr_probe", COMMAND_RUN)
    for sid in ("66b5e327-a366-4213-99e6-e362925e6142", "abc.xyz", "abc xyz", "", "a/b", "ü"):
        assert hib._safe_sid(sid) == cr._safe_sid(sid), sid


def test_lift_prints_rotation_offers_and_survives_their_fault(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """W-f975fee0 slice 3: once the pause is lifted, `lift` offers `rotate-session` for every live agent at/past the
    threshold; a fault in the offer never fails the lift."""
    box = Box(tmp_path)
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
    box.run("mark", "--words", "w")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(box.home),
        "SESSION_ARCHIVE_ENV_FILE": str(tmp_path / "none.env"),
    }
    out = subprocess.run(
        [
            sys.executable,
            str(HIB),
            "--home",
            str(box.home),
            "--proc",
            str(box.proc),
            "--opt",
            str(box.opt),
            "lift",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert out.returncode == 0, out.stderr
    assert "rotation offers" in out.stdout, out.stdout
    assert f"rotate-session dev1 --repo {repo} --trigger lift" in out.stdout, out.stdout
    hib = _load("hibernate_lift_fault", HIB)
    box.run("mark", "--words", "w2")

    def boom():
        raise RuntimeError("offer loader broke")

    monkeypatch.setattr(hib, "_load_rotate", boom)
    rc = hib.main(["--home", str(box.home), "--proc", str(box.proc), "--opt", str(box.opt), "lift"])
    marker = json.loads((box.home / ".claude" / "state" / "hibernate.json").read_text())
    assert rc == 0 and "lifted_at" in marker
    assert "rotation offers unavailable" in capsys.readouterr().err
