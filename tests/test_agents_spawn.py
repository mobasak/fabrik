"""`agents_up.sh add` / `agents_spawn.py add`, part 1 (W-b9ad80ae T06): the lock, the preflight, the worktree, the
binding, the registry, the item.

Every test builds its own throwaway git repo and HOME under `tmp_path`: the identity store is `AGENT_IDENTITY_FILE`
inside it, the refusal record lands in the tmp HOME, `systemctl`/`systemd-run` are fakes on PATH and the slice's cgroup
files sit behind the `FABRIK_AGENTS_CGROUP_DIR` seam. Nothing touches a real repo, tmux, claude or the user manager.
The module and the launcher are loaded from THIS checkout by path (the root conftest may pin another one).
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPAWN = ROOT / "scripts" / "sysadmin" / "agents_spawn.py"
UP = ROOT / "scripts" / "sysadmin" / "agents_up.sh"
GIB = 1024**3
ITEM = "W-0000abcd"
REAL_GIT = shutil.which("git") or "/usr/bin/git"

FAKE_SYSTEMCTL = """#!/bin/sh
echo "$*" >> "$HOME/systemctl.log"
[ -f "$HOME/manager-down" ] && exit 1
exit 0
"""
FAKE_SYSTEMD_RUN = "#!/bin/sh\nexit 0\n"
# a git that logs every call, so a test can prove which git commands ran (no `ls-remote` = no network)
FAKE_GIT = f'#!/bin/sh\necho "$*" >> "$HOME/git.log"\nexec {REAL_GIT} "$@"\n'
# the repo's work.py stand-in: logs what it saw, refuses a caller that is not the distributor, writes the owner
FAKE_WORK = """import json, os, sys
from pathlib import Path
home = Path(os.environ["HOME"])
args = sys.argv[1:]
facts = {
    "cwd": os.getcwd(),
    "args": args,
    "worktree": os.path.isfile(os.path.join(".claude", "worktrees", args[3], ".git")),
    "bound": args[3] in Path(os.environ["AGENT_IDENTITY_FILE"]).read_text(encoding="utf-8"),
}
with open(home / "work.log", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(facts) + "\\n")
cfg = json.loads(Path(".fabrik/work/config.json").read_text(encoding="utf-8"))
me = os.environ.get("CLAUDE_AGENT", "")
if me != cfg["distributor"]:
    print(f"work: assign is the distributor's ({cfg['distributor']}); this caller is {me}", file=sys.stderr)
    sys.exit(1)
path = Path(".fabrik/work") / (args[1] + ".json")
item = json.loads(path.read_text(encoding="utf-8"))
item["owner"] = args[3]
path.write_text(json.dumps(item), encoding="utf-8")
"""


def _load():
    spec = importlib.util.spec_from_file_location("agents_spawn_under_test", SPAWN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # a dataclass resolves its annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    out = subprocess.run(
        [REAL_GIT, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert out.returncode == 0, (args, out.stderr)
    return out.stdout.strip()


def _git_rc(repo: Path, *args: str) -> int:
    return subprocess.run(
        [REAL_GIT, "-C", str(repo), *args], capture_output=True, text=True, timeout=30, check=False
    ).returncode


class Box:
    """One throwaway repo + HOME + fakes; `env()` is the caller's environment for a run."""

    def __init__(
        self, tmp: Path, *, registry: dict | None = None, base_branch: str | None = "master"
    ) -> None:
        self.home = tmp / "home"
        self.bin = self.home / ".local" / "bin"
        self.bin.mkdir(parents=True)
        for tool, text in (
            ("systemctl", FAKE_SYSTEMCTL),
            ("systemd-run", FAKE_SYSTEMD_RUN),
            ("git", FAKE_GIT),
        ):
            (self.bin / tool).write_text(text, encoding="utf-8")
            (self.bin / tool).chmod(0o755)
            assert os.access(self.bin / tool, os.X_OK), tool  # the fake is really what PATH finds
        self.store = self.home / ".claude" / "state" / "agent-identity.jsonl"
        self.store.parent.mkdir(parents=True)
        self.spawn_log = self.home / ".claude" / "state" / "agents-spawn.jsonl"
        repo = tmp / "shop"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "master")
        (repo / "README.md").write_text("x\n", encoding="utf-8")
        charters = repo / "docs" / "reference" / "agents"
        charters.mkdir(parents=True)
        (charters / "builder.md").write_text("# Agent charter — builder\n", encoding="utf-8")
        (repo / "scripts").mkdir()
        (repo / "scripts" / "work.py").write_text(FAKE_WORK, encoding="utf-8")
        store = repo / ".fabrik" / "work"
        store.mkdir(parents=True)
        cfg: dict = {"distributor": "coordinator"}
        if base_branch:
            cfg["base_branch"] = base_branch
        (store / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (store / f"{ITEM}.json").write_text(json.dumps({"id": ITEM, "owner": ""}), encoding="utf-8")
        if registry is not None:
            (repo / ".fabrik" / "session-agents.json").write_text(
                json.dumps(registry), encoding="utf-8"
            )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
        self.repo = repo.resolve()
        self.scope = _git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        self.cg = self.home / "cgroup"
        self.cgroup(high=str(31 * GIB), mx="max", current=20 * GIB, inactive=8 * GIB)
        self.trust(self.repo)

    def trust(self, root: Path, accepted: bool = True) -> None:
        cfg = self.home / ".claude-fleet" / "active" / ".claude.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(
            json.dumps({"projects": {str(root): {"hasTrustDialogAccepted": accepted}}}),
            encoding="utf-8",
        )

    def cgroup(self, *, high: str, mx: str, current: int | None, inactive: int) -> None:
        self.cg.mkdir(exist_ok=True)
        (self.cg / "memory.high").write_text(high + "\n", encoding="utf-8")
        (self.cg / "memory.max").write_text(mx + "\n", encoding="utf-8")
        cur = self.cg / "memory.current"
        if current is None:
            cur.unlink(missing_ok=True)
        else:
            cur.write_text(f"{current}\n", encoding="utf-8")
        (self.cg / "memory.stat").write_text(
            f"anon 1\ninactive_file {inactive}\nactive_file 2\n", encoding="utf-8"
        )

    def env(self, **extra: str) -> dict:
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.home),
            "AGENT_IDENTITY_FILE": str(self.store),
            "FABRIK_AGENTS_CGROUP_DIR": str(self.cg),
            "CLAUDE_AGENT": "coordinator",
        }
        env.update(extra)
        return {k: v for k, v in env.items() if v is not None}

    def rows(self) -> list[dict]:
        if not self.store.is_file():
            return []
        return [
            json.loads(ln)
            for ln in self.store.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    def refusals(self) -> list[dict]:
        if not self.spawn_log.is_file():
            return []
        return [
            json.loads(ln)
            for ln in self.spawn_log.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    def wt(self, name: str) -> Path:
        return self.repo / ".claude" / "worktrees" / name


def _up(
    box: Box, *args: str, env: dict | None = None, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(UP), "add", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env or box.env(),
    )


def _spawn(box: Box, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SPAWN), "add", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env or box.env(),
    )


def _no_trace(box: Box, name: str) -> None:
    assert not box.wt(name).exists(), name
    assert (
        _git_rc(box.repo, "rev-parse", "--verify", "--quiet", f"refs/heads/worktree-{name}") != 0
    ), name
    assert not [r for r in box.rows() if r.get("name") == name], box.rows()


# ---- row 1: the whole path through the dispatch lines, in order -------------------------------------------------


def test_add_through_the_dispatch_creates_worktree_binding_registry_and_item_in_order(
    tmp_path: Path,
) -> None:
    box = Box(tmp_path, registry={})
    base_tip = _git(box.repo, "rev-parse", "master")
    # the main checkout sits on another branch, one commit past the base: the worktree still starts at the base tip
    _git(box.repo, "checkout", "-q", "-b", "elsewhere")
    (box.repo / "extra.txt").write_text("y\n", encoding="utf-8")
    _git(box.repo, "add", "extra.txt")
    _git(box.repo, "commit", "-q", "-m", "ahead")
    head_before = _git(box.repo, "rev-parse", "HEAD")

    out = _up(box, str(box.repo), "builder-1", "--item", ITEM)
    assert out.returncode == 0, out.stderr

    wt = box.wt("builder-1")
    assert (wt / ".git").is_file()
    assert _git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "worktree-builder-1"
    assert _git(wt, "rev-parse", "HEAD") == base_tip
    rows = [r for r in box.rows() if r.get("name") == "builder-1"]
    assert len(rows) == 1 and rows[0]["spawned"] is True and rows[0]["pid"] is None, rows
    assert rows[0]["toplevel"] == box.scope
    sid = rows[0]["session_id"]
    reg = json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))
    assert reg == {sid: "builder-1"}, reg
    item = json.loads((box.repo / ".fabrik" / "work" / f"{ITEM}.json").read_text(encoding="utf-8"))
    assert item["owner"] == "builder-1"
    # assigned on the main checkout, AFTER the worktree and the binding existed, and nothing committed
    facts = [
        json.loads(ln) for ln in (box.home / "work.log").read_text(encoding="utf-8").splitlines()
    ]
    assert len(facts) == 1 and facts[0]["cwd"] == str(box.repo), facts
    assert facts[0]["args"] == ["assign", ITEM, "--owner", "builder-1"], facts
    assert facts[0]["worktree"] and facts[0]["bound"], facts
    assert _git(box.repo, "rev-parse", "HEAD") == head_before
    assert f".fabrik/work/{ITEM}.json" in _git(box.repo, "status", "--porcelain")
    assert f"{ITEM} is assigned on {box.repo}" in out.stdout and "commit-items" in out.stdout, (
        out.stdout
    )
    assert not box.refusals()


def test_add_runs_its_steps_in_order_and_step_seven_outside_the_lock(
    tmp_path: Path, monkeypatch
) -> None:
    box = Box(tmp_path)
    for k, v in box.env().items():
        monkeypatch.setenv(k, v)
    mod = _load()
    order: list[str] = []
    for step in (
        "preflight",
        "make_worktree",
        "cold_start",
        "bind",
        "assign_item",
        "place_and_launch",
    ):
        real = getattr(mod, step)

        def wrapped(*a, _real=real, _step=step, **kw):
            order.append(_step)
            return _real(*a, **kw)

        monkeypatch.setattr(mod, step, wrapped)

    def launchers(ctx) -> None:
        order.append("launchers")
        fd = os.open(mod.lock_path(ctx.root), os.O_RDWR)
        try:
            fcntl.flock(
                fd, fcntl.LOCK_EX | fcntl.LOCK_NB
            )  # raises BlockingIOError if add still held it
            order.append("lock-free")
        finally:
            os.close(fd)

    monkeypatch.setattr(mod, "regenerate_launchers", launchers)
    assert mod.main(["add", str(box.repo), "builder-1", "--item", ITEM]) == 0
    assert order == [
        "preflight",
        "make_worktree",
        "cold_start",
        "bind",
        "assign_item",
        "place_and_launch",
        "launchers",
        "lock-free",
    ], order


# ---- row 2: two adds at once -------------------------------------------------------------------------------------


def test_a_second_add_waits_on_the_lock(tmp_path: Path) -> None:
    box = Box(tmp_path, registry={})
    mod = _load()
    lock = mod.lock_path(str(box.repo))
    assert lock == os.path.join(box.scope, "fabrik-agents.lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    proc = subprocess.Popen(
        [sys.executable, str(SPAWN), "add", str(box.repo), "builder-1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=box.env(),
    )
    try:
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            assert proc.poll() is None, proc.communicate()
            assert not box.wt("builder-1").exists()
            time.sleep(0.1)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    assert (box.wt("builder-1") / ".git").is_file()


def test_two_adds_together_create_each_artifact_once(tmp_path: Path) -> None:
    box = Box(tmp_path, registry={})
    procs = [
        subprocess.Popen(
            [sys.executable, str(SPAWN), "add", str(box.repo), "builder-1", "--item", ITEM],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=box.env(),
        )
        for _ in range(2)
    ]
    results = [(p.wait(timeout=60), p.communicate()) for p in procs]
    assert [rc for rc, _ in results] == [0, 0], results
    assert [r["name"] for r in box.rows()].count("builder-1") == 1, box.rows()
    reg = json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))
    assert list(reg.values()) == ["builder-1"], reg
    listed = _git(box.repo, "worktree", "list", "--porcelain")
    assert listed.count(f"worktree {box.wt('builder-1')}") == 1, listed
    # the second run found the owner already set and skipped step 5
    assert len((box.home / "work.log").read_text(encoding="utf-8").splitlines()) == 1


# ---- row 3: the preflight refusals, and the legitimate inputs of their class ----------------------------------


def _live_row(box: Box, name: str) -> None:
    row = {
        "session_id": "11111111-2222-4333-8444-555555555555",
        "name": name,
        "pid": os.getpid(),
        "pid_start": None,
        "toplevel": box.scope,
        "at": int(time.time()),
    }
    with box.store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


@pytest.mark.parametrize(
    ("label", "name", "args", "setup", "why"),
    [
        ("bad name", "Builder_1", (), None, "not an agent name"),
        ("coordinator name", "builder-coordinator", (), None, "coordinator"),
        ("merge owner", "builder-7", (), "owner", "merge owner"),
        ("live-bound", "builder-1", (), "live", "LIVE session"),
        ("untrusted", "builder-1", (), "untrusted", "accept the trust dialog"),
        ("uncapped", "builder-1", (), "uncapped", "FABRIK_AGENTS_UNCAPPED"),
        ("low headroom", "builder-1", (), "tight", "under the 2 GB floor"),
        ("no binding", "builder-1", (), "unbound", "add needs a bound coordinator"),
        ("unmarked role", "reviewer-1", ("--role", "reviewer"), "unmarked", "reviewer.md"),
        ("prefix", "x-1", (), None, "builder-"),
    ],
)
def test_preflight_refuses_with_no_trace_and_one_record(
    tmp_path: Path, label, name, args, setup, why
) -> None:
    box = Box(tmp_path)
    env = box.env()
    if setup == "owner":
        (box.repo / "docs" / "DECISIONS.md").write_text(
            "| ID | When | Who | What | Why | Where |\n|---|---|---|---|---|---|\n"
            "| D-001 | 2026-10-20 | operator | MERGE OWNER: builder-7 | the coordinator | here |\n",
            encoding="utf-8",
        )
    elif setup == "live":
        _live_row(box, name)
    elif setup == "untrusted":
        box.trust(box.repo, accepted=False)
    elif setup == "uncapped":
        (box.home / "manager-down").write_text("", encoding="utf-8")
    elif setup == "tight":
        box.cgroup(high=str(31 * GIB), mx="max", current=30 * GIB, inactive=0)
    elif setup == "unbound":
        env = box.env(CLAUDE_AGENT=None)
    elif setup == "unmarked":
        (box.repo / "docs" / "reference" / "agents" / "reviewer.md").write_text(
            "# Reviewer notes\n", encoding="utf-8"
        )
    rows_before = len(box.rows())
    out = _spawn(box, str(box.repo), name, *args, env=env)
    assert out.returncode == 2, (label, out.stdout, out.stderr)
    assert why in out.stderr, (label, out.stderr)
    assert not box.wt(name).exists(), label
    assert (
        _git_rc(box.repo, "rev-parse", "--verify", "--quiet", f"refs/heads/worktree-{name}") != 0
    ), label
    assert len(box.rows()) == rows_before, label
    recs = box.refusals()
    assert len(recs) == 1, (label, recs)
    assert set(recs[0]) == {"at", "repo", "name", "step", "reason"}, recs
    assert recs[0]["name"] == name and recs[0]["step"] == 1 and recs[0]["repo"] == str(box.repo), (
        recs
    )


@pytest.mark.parametrize("form", ["symlink", "trailing-slash", "symlink-trailing-slash"])
def test_a_symlinked_or_trailing_slash_root_names_the_same_trusted_repo(
    tmp_path: Path, form: str
) -> None:
    box = Box(tmp_path)
    link = tmp_path / "link-to-shop"
    link.symlink_to(box.repo)
    given = {
        "symlink": str(link),
        "trailing-slash": f"{box.repo}/",
        "symlink-trailing-slash": f"{link}/",
    }[form]
    out = _spawn(box, given, "builder-1")
    assert out.returncode == 0, out.stderr
    assert (box.wt("builder-1") / ".git").is_file()
    assert [r["toplevel"] for r in box.rows()] == [box.scope]


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("builder-1", ()),
        ("builder-12", ()),
        ("builder-a1", ()),
        ("reviewer-1", ("--role", "reviewer")),
    ],
)
def test_legitimate_names_and_roles_pass(tmp_path: Path, name: str, args: tuple) -> None:
    box = Box(tmp_path)
    (box.repo / "docs" / "reference" / "agents" / "reviewer.md").write_text(
        "# Agent charter\n", encoding="utf-8"
    )
    out = _spawn(box, str(box.repo), name, *args)
    assert out.returncode == 0, out.stderr
    assert (box.wt(name) / ".git").is_file() and not box.refusals()


def test_the_uncapped_override_passes(tmp_path: Path) -> None:
    box = Box(tmp_path)
    (box.home / "manager-down").write_text("", encoding="utf-8")
    out = _spawn(box, str(box.repo), "builder-1", env=box.env(FABRIK_AGENTS_UNCAPPED="1"))
    assert out.returncode == 0, out.stderr
    assert "UNCAPPED" in out.stderr


# ---- row 4: headroom ---------------------------------------------------------------------------------------------


def test_headroom_reads_memory_high_less_the_non_reclaimable_charge(
    tmp_path: Path, monkeypatch
) -> None:
    box = Box(tmp_path)
    monkeypatch.setenv("FABRIK_AGENTS_CGROUP_DIR", str(box.cg))
    mod = _load()
    assert mod.headroom_bytes() == 19 * GIB
    box.cgroup(high="max", mx=str(25 * GIB), current=20 * GIB, inactive=8 * GIB)
    assert mod.headroom_bytes() == 13 * GIB
    box.cgroup(high="max", mx="max", current=20 * GIB, inactive=8 * GIB)
    with pytest.raises(mod.RefusedError, match="no measurable memory limit"):
        mod.headroom_bytes()
    box.cgroup(high=str(31 * GIB), mx="max", current=None, inactive=8 * GIB)
    with pytest.raises(mod.RefusedError, match="no measurable memory limit"):
        mod.headroom_bytes()
    (box.cg / "memory.current").write_text("lots\n", encoding="utf-8")
    with pytest.raises(mod.RefusedError, match="no measurable memory limit"):
        mod.headroom_bytes()


@pytest.mark.parametrize("state", ["both-max", "unreadable"])
def test_add_refuses_an_unmeasurable_slice(tmp_path: Path, state: str) -> None:
    box = Box(tmp_path)
    if state == "both-max":
        box.cgroup(high="max", mx="max", current=1, inactive=0)
    else:
        box.cgroup(high=str(31 * GIB), mx="max", current=None, inactive=0)
    out = _spawn(box, str(box.repo), "builder-1")
    assert (
        out.returncode == 2 and "no measurable memory limit on fabrik-agents.slice" in out.stderr
    ), out.stderr
    _no_trace(box, "builder-1")


# ---- row 5: a leftover branch ------------------------------------------------------------------------------------


def test_a_leftover_branch_merged_into_base_is_recreated(tmp_path: Path) -> None:
    box = Box(tmp_path)
    _git(box.repo, "branch", "worktree-builder-1", "master~0")
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    assert _git(box.wt("builder-1"), "rev-parse", "--abbrev-ref", "HEAD") == "worktree-builder-1"


def test_a_leftover_branch_not_in_base_refuses_naming_it(tmp_path: Path) -> None:
    box = Box(tmp_path)
    _git(box.repo, "checkout", "-q", "-b", "worktree-builder-1")
    (box.repo / "work.txt").write_text("z\n", encoding="utf-8")
    _git(box.repo, "add", "work.txt")
    _git(box.repo, "commit", "-q", "-m", "unmerged work")
    tip = _git(box.repo, "rev-parse", "HEAD")
    _git(box.repo, "checkout", "-q", "master")
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 2, out.stderr
    assert (
        "worktree-builder-1" in out.stderr and "add stopped at step 2 (builder-1)" in out.stderr
    ), out.stderr
    assert not box.wt("builder-1").exists()
    assert _git(box.repo, "rev-parse", "worktree-builder-1") == tip  # the unmerged work is kept
    assert not [r for r in box.rows() if r.get("name") == "builder-1"]


def test_a_worktree_already_in_place_is_kept(tmp_path: Path) -> None:
    box = Box(tmp_path)
    assert _spawn(box, str(box.repo), "builder-1").returncode == 0
    marker = box.wt("builder-1") / "wip.txt"
    marker.write_text("keep\n", encoding="utf-8")
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    assert marker.read_text(encoding="utf-8") == "keep\n"
    assert [r["name"] for r in box.rows()].count("builder-1") == 1


# ---- row 6: the base branch --------------------------------------------------------------------------------------


def test_the_configured_base_is_used_with_no_network_call(tmp_path: Path) -> None:
    box = Box(tmp_path)
    _git(box.repo, "remote", "add", "origin", str(tmp_path / "nowhere.git"))  # unreachable
    out = _up(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    calls = (box.home / "git.log").read_text(encoding="utf-8")
    assert "worktree add" in calls, calls  # the logging git really is the one add ran
    assert "ls-remote" not in calls, calls


def test_no_config_and_no_remote_refuses_naming_the_key(tmp_path: Path) -> None:
    box = Box(tmp_path, base_branch=None)
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 2, out.stderr
    assert "no base_branch in" in out.stderr and "set base_branch" in out.stderr, out.stderr
    _no_trace(box, "builder-1")


def test_no_config_reads_the_remote_head(tmp_path: Path) -> None:
    box = Box(tmp_path, base_branch=None)
    remote = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(box.repo), str(remote))
    _git(box.repo, "remote", "add", "origin", str(remote))
    assert _load().resolve_base(str(box.repo)) == "master"


# ---- row 7: no registry ------------------------------------------------------------------------------------------


def test_a_repo_without_a_registry_gets_none(tmp_path: Path) -> None:
    box = Box(tmp_path, registry=None)
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    assert not (box.repo / ".fabrik" / "session-agents.json").exists()
    assert [r["name"] for r in box.rows()] == ["builder-1"]


# ---- row 8: assign refused, then re-run --------------------------------------------------------------------------


def test_assign_refused_stops_at_step_five_and_a_rerun_completes(tmp_path: Path) -> None:
    box = Box(tmp_path, registry={})
    out = _spawn(
        box, str(box.repo), "builder-1", "--item", ITEM, env=box.env(CLAUDE_AGENT="builder-9")
    )
    assert out.returncode == 2, out.stderr
    assert "assign is the distributor's (coordinator)" in out.stderr, out.stderr
    assert "add stopped at step 5 (builder-1)" in out.stderr, out.stderr
    assert (box.wt("builder-1") / ".git").is_file()  # the earlier steps stay
    item = json.loads((box.repo / ".fabrik" / "work" / f"{ITEM}.json").read_text(encoding="utf-8"))
    assert item["owner"] == ""

    out = _spawn(box, str(box.repo), "builder-1", "--item", ITEM)
    assert out.returncode == 0, out.stderr
    item = json.loads((box.repo / ".fabrik" / "work" / f"{ITEM}.json").read_text(encoding="utf-8"))
    assert item["owner"] == "builder-1"
    assert [r["name"] for r in box.rows()].count("builder-1") == 1, box.rows()
    reg = json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))
    assert list(reg.values()) == ["builder-1"], reg
    listed = _git(box.repo, "worktree", "list", "--porcelain")
    assert listed.count(f"worktree {box.wt('builder-1')}") == 1, listed
