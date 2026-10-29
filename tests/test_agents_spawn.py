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
    "xdg": os.environ.get("XDG_RUNTIME_DIR"),
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
# T08b: the agents_up.sh stand-in behind FABRIK_AGENTS_UP. It logs every call (argv, the FABRIK_SPAWN_* it saw, which
# names were bound and which worktrees existed then) to $HOME/agents-up.log and answers from $HOME/agents-up.json:
#   detach        rc per successive --detach call, the last repeating (default: 0 when FABRIK_SPAWN_NAME is set, else 3)
#   grid          tags: on a --detach that exits 0 with no session yet, make <S> on $FABRIK_TMUX, one pane per tag; the
#                 tag FABRIK_SPAWN_NAME names runs a process named claude carrying `--session-id <its bound id>`
#   building      the `@agents_up_building` value the grid's --detach leaves on <S> (another start still building it)
#   claude_after  the stub grid's pane is a shell whose claude child appears this many seconds on ("never": not at all)
#   print_sleep   seconds each --print takes
#   detach_current  memory.current written into $FABRIK_AGENTS_CGROUP_DIR after a --detach exiting 0
#   builders      the names --print reports, `ok` until running_after seconds past the first --print, then `running`
#   print_grow    bytes added to memory.current on every --print
#   pane_cmd      {"rc", "out", "err"} for --pane-cmd (default rc 0, "sleep 600")
FAKE_UP = (
    f"#!{sys.executable}\n"
    + r"""import json, os, shlex, subprocess, sys, time
from pathlib import Path
home = Path(os.environ["HOME"])
argv = sys.argv[1:]
scn_path = home / "agents-up.json"
scn = json.loads(scn_path.read_text(encoding="utf-8")) if scn_path.is_file() else {}
log = home / "agents-up.log"
past = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []
store = Path(os.environ["AGENT_IDENTITY_FILE"])
rows = [json.loads(ln) for ln in store.read_text(encoding="utf-8").splitlines() if ln.strip()] if store.is_file() else []
root = argv[1] if len(argv) > 1 else ""
wts = Path(root) / ".claude" / "worktrees"
entry = {
    "argv": argv,
    "spawn": {k: v for k, v in os.environ.items() if k.startswith("FABRIK_SPAWN_")},
    "bound": [r.get("name") for r in rows],
    "worktrees": sorted(p.name for p in wts.iterdir()) if wts.is_dir() else [],
    "t": time.monotonic(),
}
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(entry) + "\n")
cg = os.environ.get("FABRIK_AGENTS_CGROUP_DIR")

def bump(value=None, grow=0):
    cur = Path(cg) / "memory.current"
    now = int(cur.read_text(encoding="utf-8")) if value is None else value
    cur.write_text(str(now + grow) + "\n", encoding="utf-8")

mode = argv[0]
if mode == "--detach":
    n = sum(1 for e in past if e["argv"][0] == "--detach")
    if "detach" in scn:
        rc = scn["detach"][min(n, len(scn["detach"]) - 1)]
    else:  # no grid comes up: no builder (3), unless the spawner named the new one (0)
        rc = 0 if os.environ.get("FABRIK_SPAWN_NAME") else 3
    if rc == 0 and "grid" in scn:
        tmux = shlex.split(os.environ["FABRIK_TMUX"])
        if subprocess.run([*tmux, "has-session", "-t", "=shop"], capture_output=True).returncode != 0:
            for i, tag in enumerate(scn["grid"]):
                cmd = "sleep 600"
                if tag == os.environ.get("FABRIK_SPAWN_NAME"):  # T02: the new builder starts --session-id <its bound id>
                    sid = [r["session_id"] for r in rows if r.get("name") == tag][-1]
                    # `; :` keeps bash from exec-ing sleep in its place (the claude-named argv must stay)
                    cmd = f"bash -c \"exec -a claude bash -c 'sleep 600; :' claude -n {tag} --session-id {sid}\""
                if i == 0:
                    verb = ["new-session", "-d", "-s", "shop", "-n", "agents", "-x", "240", "-y", "60"]
                else:
                    verb = ["split-window", "-d", "-t", "=shop:"]
                pane = subprocess.run([*tmux, *verb, "-P", "-F", "#{pane_id}", cmd], capture_output=True, text=True, check=True).stdout.strip()
                subprocess.run([*tmux, "select-layout", "-t", "=shop:", "even-horizontal"], check=True)
                subprocess.run([*tmux, "set", "-p", "-t", pane, "@agent", tag], check=True)
            if "building" in scn:  # another start still building the grid (agents_up.sh's `<pid>:<start time>`)
                subprocess.run([*tmux, "set-option", "-t", "=shop:", "@agents_up_building", scn["building"]], check=True)
    spawned = os.environ.get("FABRIK_SPAWN_NAME")
    if rc == 0 and "grid" not in scn and spawned and os.environ["FABRIK_TMUX"].endswith("fake-tmux"):
        # the Box's stub grid: one pane tagged with the new builder, its claude in the fake /proc (T02's --session-id)
        sid = [r["session_id"] for r in rows if r.get("name") == spawned][-1]
        (home / "fake-grid").write_text(f"@1\tagents\t%1\t4242\t{spawned}\n", encoding="utf-8")
        p = Path(os.environ["FABRIK_PROC_ROOT"])
        (p / "4242" / "task" / "4242").mkdir(parents=True, exist_ok=True)
        (p / "4242" / "task" / "4242" / "children").write_text("", encoding="utf-8")
        claude = b"\0".join(a.encode() for a in ["claude", "-n", spawned, "--session-id", sid]) + b"\0"
        later = scn.get("claude_after")
        if later is None:
            (p / "4242" / "cmdline").write_bytes(claude)
        else:  # a capped pane: the shell first; its claude child 4243 appears `later` seconds on ("never": not at all)
            (p / "4242" / "cmdline").write_bytes(b"sh\0")
            if later != "never":
                (p / "4243" / "task" / "4243").mkdir(parents=True, exist_ok=True)
                (p / "4243" / "task" / "4243" / "children").write_text("", encoding="utf-8")
                (p / "4243" / "cmdline").write_bytes(claude)
                writer = (
                    "import sys, time; time.sleep(float(sys.argv[1])); "
                    "open(sys.argv[2], 'w').write('4243 ')"
                )
                subprocess.Popen(
                    [sys.executable, "-c", writer, str(later), str(p / "4242" / "task" / "4242" / "children")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                )
    if rc == 0 and "detach_current" in scn:
        bump(scn["detach_current"])
    sys.exit(rc)
if mode == "--print":
    time.sleep(scn.get("print_sleep", 0))
    if "print_grow" in scn:
        bump(grow=scn["print_grow"])
    prints = [e for e in past if e["argv"][0] == "--print"]
    first = prints[0]["t"] if prints else entry["t"]
    state = "running" if entry["t"] - first >= scn.get("running_after", 0) else "ok"
    print("session shop")
    for name in scn.get("builders", []):
        print(f"pane {name} 00000000-0000-4000-8000-000000000000 /x/{name} {state}")
    with (home / "print-states.log").open("a", encoding="utf-8") as fh:
        fh.write(state + "\n")
    sys.exit(0)
if mode == "--pane-cmd":
    pc = scn.get("pane_cmd", {})
    sys.stdout.write(pc.get("out", "sleep 600\n"))
    sys.stderr.write(pc.get("err", ""))
    sys.exit(pc.get("rc", 0))
sys.exit(9)
"""
)
# the Box's default tmux: no grid until the fake agents_up.sh writes $HOME/fake-grid (one list-panes line), then
# has-session answers yes and list-panes prints it; every other call fails
FAKE_TMUX_DOWN = """#!/bin/sh
grid="$HOME/fake-grid"
case "$1" in
  has-session) [ -f "$grid" ] ;;
  list-panes) [ -f "$grid" ] && cat "$grid" ;;
  *) exit 1 ;;
esac
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
            ("fake-agents-up", FAKE_UP),
            ("fake-tmux", FAKE_TMUX_DOWN),
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
        self.meminfo_path = self.home / "meminfo"
        self.meminfo(16)
        self.trust(self.repo)

    def meminfo(self, avail_gib: float) -> None:
        """The box's /proc/meminfo behind the FABRIK_AGENTS_MEMINFO seam (MemAvailable in kB)."""
        kb = int(avail_gib * 1024 * 1024)
        self.meminfo_path.write_text(
            f"MemTotal:       {64 * 1024 * 1024} kB\nMemFree:  1 kB\nMemAvailable:   {kb} kB\n",
            encoding="utf-8",
        )

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
            "FABRIK_AGENTS_MEMINFO": str(self.meminfo_path),
            "CLAUDE_AGENT": "coordinator",
            "FABRIK_AGENTS_UP": str(self.bin / "fake-agents-up"),
            "FABRIK_TMUX": str(self.bin / "fake-tmux"),
            "FABRIK_PROC_ROOT": str(self.home / "proc"),
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
        ("trailing hyphen", "builder-", (), None, "needs an ordinal after 'builder-'"),
        ("double hyphen", "builder--", (), None, "needs an ordinal after 'builder-'"),
        ("uncapped low box", "builder-1", (), "uncapped-low", "under the 2 GB floor"),
        ("cold slice low box", "builder-1", (), "cold-low", "under the 2 GB floor"),
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
    elif setup == "uncapped-low":
        (box.home / "manager-down").write_text("", encoding="utf-8")
        box.meminfo(1.5)
        env = box.env(FABRIK_AGENTS_UNCAPPED="1")
    elif (
        setup == "cold-low"
    ):  # capped, but the slice has no cgroup yet (no grid since boot): the box is measured
        box.meminfo(1.5)
        env = box.env(FABRIK_AGENTS_CGROUP_DIR=None)
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
        ("builder-a2", ()),
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


def test_the_uncapped_override_passes_on_the_box_floor(tmp_path: Path) -> None:
    """F5: the override still measures — the box's MemAvailable, not the slice — and says so."""
    box = Box(tmp_path)
    (box.home / "manager-down").write_text("", encoding="utf-8")
    box.cgroup(high=str(3 * GIB), mx="max", current=3 * GIB, inactive=0)  # a slice that is not read
    out = _spawn(box, str(box.repo), "builder-1", env=box.env(FABRIK_AGENTS_UNCAPPED="1"))
    assert out.returncode == 0, out.stderr
    assert "UNCAPPED" in out.stderr and "MemAvailable" in out.stderr, out.stderr


def test_a_cold_slice_is_measured_on_the_box(tmp_path: Path) -> None:
    """F4: capped, but the slice's ControlGroup reads empty (no grid since boot) → the box's MemAvailable decides."""
    box = Box(tmp_path)
    out = _spawn(box, str(box.repo), "builder-1", env=box.env(FABRIK_AGENTS_CGROUP_DIR=None))
    assert out.returncode == 0, out.stderr
    assert "MemAvailable" in out.stderr, out.stderr
    assert "show -p ControlGroup --value fabrik-agents.slice" in (
        box.home / "systemctl.log"
    ).read_text(encoding="utf-8")


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


# ---- review pass 1 (F1-F9) ---------------------------------------------------------------------------------------

OLD = "11111111-2222-4333-8444-555555555555"


def _row(box: Box, sid: str, name: str, **kw) -> None:
    row = {"session_id": sid, "name": name, "pid": None, "pid_start": None, "toplevel": box.scope}
    row.update({"at": int(time.time()), **kw})
    with box.store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


@pytest.mark.parametrize("shape", ["dead-pid", "as-no-pid", "spawned-then-rebound"])
def test_a_binding_that_is_not_an_unstarted_spawn_is_never_reused(
    tmp_path: Path, shape: str
) -> None:
    """F1: step 4 reuses ONLY an earlier add's `spawned: true` row with no live pid; a dead `--as` row (or a spawned
    session its builder has since re-bound) gets a FRESH id, and the registry names that fresh id alone."""
    box = Box(tmp_path, registry={})
    if shape == "dead-pid":
        _row(box, OLD, "builder-1", pid=999999, pid_start=1)
    elif shape == "as-no-pid":
        _row(box, OLD, "builder-1")
    else:
        _row(box, OLD, "builder-1", spawned=True)
        _row(box, OLD, "builder-1", pid=999999, pid_start=1)  # the builder's own first-turn re-bind
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    fresh = [r for r in box.rows() if r["session_id"] != OLD]
    assert len(fresh) == 1 and fresh[0]["spawned"] is True, box.rows()
    reg = json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))
    assert reg == {fresh[0]["session_id"]: "builder-1"}, reg


def test_an_unstarted_spawned_binding_is_reused(tmp_path: Path) -> None:
    """F1 mirror: a re-run after a later step failed keeps the spawned id from step 4 — no second binding."""
    box = Box(tmp_path, registry={})
    _row(box, OLD, "builder-1", spawned=True)
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    assert [r["session_id"] for r in box.rows()] == [OLD], box.rows()
    reg = json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))
    assert reg == {OLD: "builder-1"}, reg


def test_the_registry_ends_with_exactly_one_row_for_the_name(tmp_path: Path) -> None:
    """F2: a stale `{old: builder-1}` row is replaced by `{sid: builder-1}`; other names' rows stay."""
    other = "22222222-3333-4444-8555-666666666666"
    box = Box(tmp_path, registry={OLD: "builder-1", other: "builder-2"})
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    sid = [r["session_id"] for r in box.rows() if r["name"] == "builder-1"][-1]
    reg = json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))
    assert reg == {other: "builder-2", sid: "builder-1"}, reg


def test_a_linked_worktree_root_refuses_naming_the_main_checkout(tmp_path: Path) -> None:
    """F3: the root must be the main checkout; a linked worktree path refuses before any write."""
    box = Box(tmp_path, registry=None)
    wt2 = tmp_path / "wt2"
    _git(box.repo, "worktree", "add", "-q", "-b", "side", str(wt2))
    wt2 = wt2.resolve()
    box.trust(wt2)
    out = _spawn(box, str(wt2), "builder-1")
    assert out.returncode == 2, out.stderr
    assert f"pass the main checkout {box.repo}, not a linked worktree" in out.stderr, out.stderr
    assert not (wt2 / ".claude" / "worktrees" / "builder-1").exists()
    assert not box.rows() and len(box.refusals()) == 1, box.refusals()


def test_a_subdirectory_of_the_main_checkout_refuses(tmp_path: Path) -> None:
    """F3 mirror: a subdirectory is not the main checkout either."""
    box = Box(tmp_path, registry=None)
    sub = (box.repo / "docs").resolve()
    box.trust(sub)
    out = _spawn(box, str(sub), "builder-1")
    assert out.returncode == 2, out.stderr
    assert f"pass the main checkout {box.repo}" in out.stderr, out.stderr
    assert not (sub / ".claude").exists() and not box.rows()


def test_a_main_checkout_with_a_separate_git_dir_passes(tmp_path: Path) -> None:
    """N1: a main checkout whose `.git` is a `gitdir:` pointer file (git init --separate-git-dir) is still the main
    checkout — its common dir lives elsewhere, so the main checkout is never `dirname(common dir)`."""
    box = Box(tmp_path, registry=None)
    elsewhere = tmp_path / "elsewhere.git"
    (box.repo / ".git").rename(elsewhere)
    (box.repo / ".git").write_text(f"gitdir: {elsewhere}\n", encoding="utf-8")
    _git(box.repo, "config", "core.worktree", str(box.repo))
    out = _up(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    assert (box.wt("builder-1") / ".git").is_file()


def test_a_refusal_never_names_a_git_dir_as_the_main_checkout(tmp_path: Path) -> None:
    """P1: under a separate git dir, `git worktree list`'s first entry is the git dir, not a checkout — a linked
    worktree is still refused, and the hint names no path rather than the git dir."""
    box = Box(tmp_path, registry=None)
    elsewhere = tmp_path / "elsewhere.repo"
    (box.repo / ".git").rename(elsewhere)
    (box.repo / ".git").write_text(f"gitdir: {elsewhere}\n", encoding="utf-8")
    _git(box.repo, "config", "core.worktree", str(box.repo))
    wt2 = tmp_path / "wt2"
    _git(box.repo, "worktree", "add", "-q", "-b", "side", str(wt2))
    wt2 = wt2.resolve()
    box.trust(wt2)
    out = _spawn(box, str(wt2), "builder-1")
    assert out.returncode == 2, out.stderr
    assert "main checkout" in out.stderr and str(elsewhere) not in out.stderr, out.stderr
    assert not (wt2 / ".claude" / "worktrees" / "builder-1").exists() and not box.rows()


def test_a_whoami_crash_is_a_recorded_refusal(tmp_path: Path, monkeypatch) -> None:
    """F7: an exception inside whoami_agent.py's helpers exits 2 with one record and the step line, never a trace."""
    box = Box(tmp_path)
    for k, v in box.env().items():
        monkeypatch.setenv(k, v)
    broken = tmp_path / "whoami_agent.py"
    text = (ROOT / "scripts" / "whoami_agent.py").read_text(encoding="utf-8")
    broken.write_text(
        text + "\n\ndef _rows(path):\n    raise RuntimeError('boom')\n", encoding="utf-8"
    )
    mod = _load()
    monkeypatch.setattr(mod, "WHOAMI", broken)
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["reason"] == "whoami crashed: RuntimeError: boom", recs
    _no_trace(box, "builder-1")


def test_an_unexpected_exception_at_a_step_is_a_recorded_refusal(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """F7: any other exception at a step maps to a refusal at THAT step."""
    box = Box(tmp_path)
    for k, v in box.env().items():
        monkeypatch.setenv(k, v)
    mod = _load()

    def boom(ctx) -> None:
        raise KeyError("nope")

    monkeypatch.setattr(mod, "assign_item", boom)
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 5, recs
    assert "add stopped at step 5 (builder-1)" in capsys.readouterr().err


def test_the_callers_environment_reaches_work_py_unchanged(tmp_path: Path) -> None:
    """F8: add never writes os.environ — an unset XDG_RUNTIME_DIR stays unset for `work.py assign`."""
    if not os.path.exists(f"/run/user/{os.getuid()}/bus"):
        pytest.skip(
            "no user bus here: _capped() would have nothing to add, so the test could not fail"
        )
    box = Box(tmp_path)
    out = _spawn(box, str(box.repo), "builder-1", "--item", ITEM, env=box.env(XDG_RUNTIME_DIR=None))
    assert out.returncode == 0, out.stderr
    log = (box.home / "work.log").read_text(encoding="utf-8").splitlines()
    facts = [json.loads(ln) for ln in log]
    assert facts[0]["xdg"] is None, facts


@pytest.mark.parametrize("mode", [0o644, 0o664])
def test_the_registry_keeps_its_mode(tmp_path: Path, mode: int) -> None:
    """F9: the atomic replace keeps the previous file's mode (mkstemp alone would leave 0600)."""
    box = Box(tmp_path, registry={})
    reg = box.repo / ".fabrik" / "session-agents.json"
    reg.chmod(mode)
    out = _spawn(box, str(box.repo), "builder-1")
    assert out.returncode == 0, out.stderr
    assert (reg.stat().st_mode & 0o777) == mode


# --- W-b9ad80ae T08a: the live read, placement into windows of four, the overflow sessions, adoption ---------------
# These run `place_pane` in-process against a SCRATCH `tmux -L <unique>` server (never the default socket), reached
# through the FABRIK_TMUX seam, and assert the server's STATE — windows, panes, sessions, groups, tags. Every pane runs a
# harmless `sleep`, never claude; adoption reads a fake /proc tree behind FABRIK_PROC_ROOT, keyed on the REAL pane_pid.

SID = "0b1e2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
OTHER_SID = "ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb"
SLEEP = "sleep 600"


class _Grid:
    """A scratch tmux server; `S` is the repo's base session name. Killed in teardown, its socket file removed."""

    def __init__(self, tmp_path: Path, request: pytest.FixtureRequest, monkeypatch) -> None:
        self.real = shutil.which("tmux") or ""
        if not self.real:
            pytest.skip("no tmux on this box")
        self.server = f"t08a-{os.getpid()}-{abs(hash(str(tmp_path))) % 10**8}"
        self.tmp = tmp_path
        self.S = "shop"
        self.wt = tmp_path / "wt"
        self.wt.mkdir()
        request.addfinalizer(self.close)
        monkeypatch.setenv("FABRIK_TMUX", f"{self.real} -L {self.server}")
        monkeypatch.delenv("TMUX", raising=False)
        self.mod = _load()

    def close(self) -> None:
        killed = self.tmux("kill-server")
        sock = Path(os.environ.get("TMUX_TMPDIR", "/tmp")) / f"tmux-{os.getuid()}" / self.server
        if killed.returncode == 0 or self.tmux("list-sessions").returncode != 0:
            sock.unlink(missing_ok=True)

    def tmux(self, *a: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.real, "-L", self.server, *a], capture_output=True, text=True, timeout=20
        )

    def ok(self, *a: str) -> str:
        out = self.tmux(*a)
        assert out.returncode == 0, (a, out.stderr)
        return out.stdout.strip()

    def lines(self, *a: str) -> list[str]:
        return self.tmux(*a).stdout.splitlines()

    # -- building a grid by hand --
    def base(self, window: str = "agents", panes: int = 1, tags: tuple[str, ...] = ()) -> str:
        """Create <S> with one window `window` of `panes` panes; returns the window id."""
        wid = self.ok(
            "new-session",
            "-d",
            "-s",
            self.S,
            "-n",
            window,
            "-x",
            "240",
            "-y",
            "60",
            "-P",
            "-F",
            "#{window_id}",
            SLEEP,
        )
        self.fill(wid, panes, tags)
        return wid

    def window(self, name: str, panes: int, tags: tuple[str, ...] = ()) -> str:
        wid = self.ok(
            "new-window", "-d", "-t", f"={self.S}:", "-n", name, "-P", "-F", "#{window_id}", SLEEP
        )
        self.fill(wid, panes, tags)
        return wid

    def fill(self, wid: str, panes: int, tags: tuple[str, ...] = ()) -> None:
        for _ in range(panes - int(self.panes_of(wid))):
            self.ok("split-window", "-d", "-t", wid, SLEEP)
            self.ok("select-layout", "-t", wid, "even-horizontal")
        for pid, tag in zip(
            self.lines("list-panes", "-t", wid, "-F", "#{pane_id}"), tags, strict=False
        ):
            self.ok("set", "-p", "-t", pid, "@agent", tag)

    # -- reading the state --
    def panes_of(self, wid: str) -> str:
        return self.ok("display-message", "-p", "-t", wid, "#{window_panes}")

    def windows(self) -> list[str]:
        return self.lines(
            "list-windows", "-t", f"={self.S}", "-F", "#{window_name} #{window_panes}"
        )

    def sessions(self) -> list[str]:
        return sorted(self.lines("list-sessions", "-F", "#{session_name}"))

    def one(self, session: str, fmt: str) -> str:
        return self.tmux("display-message", "-p", "-t", f"={session}:", fmt).stdout.strip()

    def tags(self) -> list[str]:
        return sorted(
            self.lines("list-panes", "-s", "-t", f"={self.S}", "-F", "#{window_name} #{@agent}")
        )

    def snapshot(self) -> tuple:
        return (
            self.sessions(),
            self.windows(),
            self.lines(
                "list-panes", "-a", "-F", "#{session_name} #{window_id} #{pane_id} #{@agent}"
            ),
        )

    def place(self, name: str, sid: str = SID):
        return self.mod.place_pane("/r/shop", self.S, name, sid, str(self.wt), SLEEP)


def test_a_failing_or_empty_tmux_read_refuses_and_creates_nothing(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """D9, C4: an error, or nothing while has-session says the grid is up, is never read as an empty grid."""
    g = _Grid(tmp_path, request, monkeypatch)
    g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))
    before = g.snapshot()
    for mode, body in (
        ("error", 'echo "server exited unexpectedly" >&2; exit 1'),
        ("empty", "exit 0"),
    ):
        wrapper = tmp_path / f"tmux-{mode}"
        wrapper.write_text(
            "#!/bin/sh\n"
            f'if [ "$1" = list-panes ]; then {body}; fi\n'
            f'exec {g.real} -L {g.server} "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        monkeypatch.setenv("FABRIK_TMUX", str(wrapper))
        with pytest.raises(g.mod.PlacementRefused) as exc:
            g.place("dev5")
        assert "tmux read failed — not placing" in exc.value.reason, (mode, exc.value.reason)
        assert isinstance(exc.value, g.mod.RefusedError) and exc.value.step == 6
        assert g.snapshot() == before, mode


def test_a_fifth_builder_opens_agents_2_with_its_grouped_session_and_leaves_tab_1(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """D4, W-14219e6f point 11: `agents-2` in the background, `<S>+2` grouping a still-ungrouped `<S>`."""
    g = _Grid(tmp_path, request, monkeypatch)
    first = g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))
    assert g.one(g.S, "#{session_group}") == ""
    res = g.place("dev5")
    assert g.windows() == ["agents 4", "agents-2 1"], g.windows()
    wid2 = g.ok(
        "list-windows", "-t", f"={g.S}", "-f", "#{==:#{window_name},agents-2}", "-F", "#{window_id}"
    )
    assert (res.window_id, res.new_window_k, res.adopted) == (wid2, 2, False), res
    assert (
        g.ok("display-message", "-p", "-t", res.pane_id, "#{window_id} #{@agent}") == f"{wid2} dev5"
    )
    assert g.sessions() == [g.S, f"{g.S}+2"], g.sessions()
    group = g.one(g.S, "#{session_group}")
    assert group and g.one(f"{g.S}+2", "#{session_group}") == group
    assert g.one(f"{g.S}+2", "#{window_id}") == wid2  # the overflow session shows agents-2
    assert g.one(g.S, "#{window_id}") == first  # tab 1 still shows agents


def test_no_agents_and_a_full_agents_2_recreates_agents_as_the_current_window(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """W-14219e6f point 8, C2: the re-created first window becomes `<S>`'s current one."""
    g = _Grid(tmp_path, request, monkeypatch)
    g.base(window="agents-2", panes=4, tags=("dev5", "dev6", "dev7", "dev8"))
    res = g.place("dev1")
    assert sorted(g.windows()) == ["agents 1", "agents-2 4"], g.windows()
    assert (res.new_window_k, res.adopted) == (1, False), res
    assert g.one(g.S, "#{window_id} #{window_name}") == f"{res.window_id} agents"
    assert g.sessions() == [g.S], g.sessions()  # `agents` gets no overflow session
    assert "agents dev1" in g.tags()


def test_no_agents_and_agents_2_with_room_joins_agents_2(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """C2, B12: the lowest window WITH ROOM wins before `agents` is re-created; the target is the window id."""
    g = _Grid(tmp_path, request, monkeypatch)
    wid2 = g.base(window="agents-2", panes=3, tags=("dev5", "dev6", "dev7"))
    res = g.place("dev8")
    assert g.windows() == ["agents-2 4"], g.windows()
    assert (res.window_id, res.new_window_k, res.adopted) == (wid2, None, False), res
    assert g.tags() == ["agents-2 dev5", "agents-2 dev6", "agents-2 dev7", "agents-2 dev8"]


def test_overflow_sessions_are_reused_only_when_in_the_base_group(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """Pass-2 class rewrite: a stale `<S>+2` (an old killed base's group) and a `<S>+4` with no group are killed and
    re-created in `<S>`'s group; `<S>+3`, already in it, is reused."""
    g = _Grid(tmp_path, request, monkeypatch)
    # <S>+2 grouped with an old base that is then killed: its group keeps the old base's name
    g.ok("new-session", "-d", "-s", "oldshop", SLEEP)
    g.ok("new-session", "-d", "-t", "=oldshop", "-s", f"{g.S}+2")
    g.ok("kill-session", "-t", "=oldshop")
    assert g.one(f"{g.S}+2", "#{session_group}") == "oldshop"
    g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+3")
    g.ok("new-session", "-d", "-s", f"{g.S}+4", SLEEP)
    assert g.one(f"{g.S}+4", "#{session_group}") == ""
    ids = {k: g.one(f"{g.S}+{k}", "#{session_id}") for k in (2, 3, 4)}
    group = g.one(g.S, "#{session_group}")
    assert group
    for k in (2, 3, 4):
        res = g.place(f"dev{4 * k - 3}")
        assert res.new_window_k == k, res
        g.fill(res.window_id, 4)
        assert g.one(f"{g.S}+{k}", "#{session_group}") == group, k
        assert g.one(f"{g.S}+{k}", "#{window_id}") == res.window_id, k
    now = {k: g.one(f"{g.S}+{k}", "#{session_id}") for k in (2, 3, 4)}
    assert now[3] == ids[3], "the member already in <S>'s group is reused"
    assert now[2] != ids[2] and now[4] != ids[4], (ids, now)
    assert g.sessions() == sorted([g.S, f"{g.S}+2", f"{g.S}+3", f"{g.S}+4"]), g.sessions()


def test_another_repos_dash_session_is_untouched(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """`+` is outside the base-name alphabet: `<S>-2` is another repo's base session and is never used or killed."""
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", f"{g.S}-2", "-n", "agents", SLEEP)
    theirs = g.ok(
        "list-panes", "-s", "-t", f"={g.S}-2", "-F", "#{session_id} #{window_id} #{pane_id}"
    )
    g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))
    g.place("dev5")
    assert g.sessions() == sorted([g.S, f"{g.S}+2", f"{g.S}-2"]), g.sessions()
    assert (
        g.ok("list-panes", "-s", "-t", f"={g.S}-2", "-F", "#{session_id} #{window_id} #{pane_id}")
        == theirs
    )
    assert g.one(f"{g.S}-2", "#{session_group}") == ""


def test_a_stale_member_of_a_group_named_s_refuses_the_overflow_and_creates_nothing(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """T03's refusal mirrored: while `<S>` is ungrouped, a session joined to a group NAMED `<S>` would drag `<S>` into
    it on `new-session -t =<S>` — refuse naming it, kill nothing that is not ours."""
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", g.S, SLEEP)
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", "viewer")
    g.ok("kill-session", "-t", f"={g.S}")
    g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))
    assert g.one(g.S, "#{session_group}") == "" and g.one("viewer", "#{session_group}") == g.S
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert "viewer" in exc.value.reason and "kill-session -t =viewer" in exc.value.reason, (
        exc.value.reason
    )
    assert g.snapshot() == before


def _fake_proc(
    root: Path, chain: dict[int, list[int]], cmdlines: dict[int, list[str]], tids=None
) -> None:
    """`<root>/<pid>/task/<tid>/children` and `<root>/<pid>/cmdline` (NUL-separated). `tids` maps a pid to the
    thread a child is listed under (default: the pid itself)."""
    for pid, kids in chain.items():
        by_tid: dict[int, list[int]] = {}
        for kid in kids:
            by_tid.setdefault((tids or {}).get(kid, pid), []).append(kid)
        by_tid.setdefault(pid, [])
        for tid, ks in by_tid.items():
            d = root / str(pid) / "task" / str(tid)
            d.mkdir(parents=True, exist_ok=True)
            (d / "children").write_text(
                " ".join(map(str, ks)) + (" " if ks else ""), encoding="utf-8"
            )
    for pid, argv in cmdlines.items():
        (root / str(pid)).mkdir(parents=True, exist_ok=True)
        (root / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")


def _tagged(g: _Grid, name: str = "b-1") -> tuple[str, int]:
    g.base(panes=2, tags=("dev1", name))
    pane, pid = g.ok(
        "list-panes",
        "-s",
        "-t",
        f"={g.S}",
        "-f",
        f"#{{==:#{{@agent}},{name}}}",
        "-F",
        "#{pane_id} #{pane_pid}",
    ).split()
    return pane, int(pid)


@pytest.mark.parametrize(
    "shape",
    ["capped-resume", "session-id", "resume-equals", "short-r", "uncapped-child", "other-thread"],
)
def test_a_tagged_pane_running_the_bound_session_is_adopted(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, shape: str
) -> None:
    """D2, C1: the tag AND the claude descendant's `--resume`/`--session-id` id adopt the pane; no pane is added."""
    g = _Grid(tmp_path, request, monkeypatch)
    pane, pp = _tagged(g)
    proc = tmp_path / "proc"
    claude = ["claude", "-n", "b-1", "--resume", SID, "--settings", "{}", "carry on"]
    if shape == "session-id":
        claude = ["/home/u/.local/bin/claude", "-n", "b-1", "--session-id", SID, "first turn"]
    elif shape == "resume-equals":
        claude = ["claude", f"--resume={SID}"]
    elif shape == "short-r":  # F2: agents_up.sh::status_of reads `-r <id>` too
        claude = ["claude", "-n", "b-1", "-r", SID]
    if shape == "uncapped-child":
        _fake_proc(proc, {pp: [pp + 1], pp + 1: []}, {pp: ["sh", "-c", "x"], pp + 1: claude})
    else:
        # the capped chain: the pane's shell → systemd-run --scope → bash -c → claude
        _fake_proc(
            proc,
            {pp: [pp + 1], pp + 1: [pp + 2], pp + 2: [pp + 3], pp + 3: []},
            {
                pp: ["sh", "-c", "env -i systemd-run ..."],
                pp + 1: [
                    "systemd-run",
                    "--user",
                    "--scope",
                    "--",
                    "bash",
                    "-c",
                    f"claude --resume {OTHER_SID}",
                ],
                pp + 2: ["bash", "-c", f"claude -n b-1 --resume {OTHER_SID}"],
                pp + 3: claude,
            },
            tids={pp + 3: pp + 7} if shape == "other-thread" else None,
        )
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    before = g.snapshot()
    res = g.place("b-1")
    assert res.adopted is True and res.pane_id == pane and res.new_window_k is None, res
    assert g.snapshot() == before


@pytest.mark.parametrize("shape", ["no-claude", "shell-only", "other-id"])
def test_a_tagged_pane_without_the_bound_claude_refuses(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, shape: str
) -> None:
    """C1, C4: a kept shell names the respawn remedy; another session id names both ids; nothing is added."""
    g = _Grid(tmp_path, request, monkeypatch)
    pane, pp = _tagged(g)
    proc = tmp_path / "proc"
    if shape == "no-claude":  # the claude exited: the scope's bash kept a login shell
        _fake_proc(
            proc,
            {pp: [pp + 1], pp + 1: [pp + 2], pp + 2: []},
            {pp: ["sh"], pp + 1: ["systemd-run", "--scope"], pp + 2: ["bash", "-l"]},
        )
    elif shape == "shell-only":  # no children file content at all
        _fake_proc(proc, {pp: []}, {pp: ["bash", "-l"]})
    else:
        _fake_proc(
            proc,
            {pp: [pp + 1], pp + 1: []},
            {pp: ["sh"], pp + 1: ["claude", "-n", "b-1", "--resume", OTHER_SID]},
        )
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("b-1")
    reason = exc.value.reason
    if shape == "other-id":
        assert SID in reason and OTHER_SID in reason, reason
    else:
        assert "runs no claude" in reason and f"tmux respawn-pane -k -t {pane}" in reason, reason
    assert g.snapshot() == before


def test_a_seventh_builder_after_a_six_builder_grid_is_agents_2s_third_pane(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """IF3: the grid T03 builds for six (agents 4, agents-2 2, `<S>+2` grouped) takes a seventh in agents-2 by id."""
    g = _Grid(tmp_path, request, monkeypatch)
    first = g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))
    wid2 = g.window("agents-2", 2, ("dev5", "dev6"))
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+2")
    g.ok("select-window", "-t", f"={g.S}+2:{wid2}")
    plus2 = g.one(f"{g.S}+2", "#{session_id}")
    res = g.place("dev7")
    assert (res.window_id, res.new_window_k) == (wid2, None), res
    assert g.windows() == ["agents 4", "agents-2 3"], g.windows()
    assert g.lines("list-panes", "-t", wid2, "-F", "#{@agent}")[2] == "dev7"
    assert g.one(f"{g.S}+2", "#{session_id}") == plus2 and g.one(g.S, "#{window_id}") == first


# --- T08a review pass 1 ----------------------------------------------------------------------------------------------


def _wrap(g: _Grid, label: str, body: str) -> None:
    """Point FABRIK_TMUX at a wrapper around the scratch server; `body` runs first and may exit or exec."""
    wrapper = g.tmp / f"tmux-{label}"
    wrapper.write_text(
        f'#!/bin/sh\nREAL="{g.real} -L {g.server}"\n{body}\nexec $REAL "$@"\n', encoding="utf-8"
    )
    wrapper.chmod(0o755)
    os.environ["FABRIK_TMUX"] = str(wrapper)  # monkeypatch.setenv in _Grid restores it


def _full(g: _Grid) -> str:
    return g.base(panes=4, tags=("dev1", "dev2", "dev3", "dev4"))


@pytest.mark.parametrize("value", ["tmux -L 'unbalanced", "   "])
def test_f1_a_fabrik_tmux_that_is_not_a_command_refuses(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, value: str
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    before = g.snapshot()
    monkeypatch.setenv("FABRIK_TMUX", value)
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert exc.value.reason.startswith("FABRIK_TMUX is not a command:"), exc.value.reason
    assert g.snapshot() == before


def test_f7_a_sid_flag_with_no_value_is_no_id(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _pane, pp = _tagged(g)
    proc = tmp_path / "proc"
    _fake_proc(
        proc,
        {pp: [pp + 1], pp + 1: []},
        {pp: ["sh"], pp + 1: ["claude", "--resume", "--settings", "{}"]},
    )
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("b-1")
    assert "(no session id)" in exc.value.reason and "--settings" not in exc.value.reason, (
        exc.value.reason
    )


def test_f6_a_cmdline_without_a_trailing_nul_keeps_its_last_argument(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    pane, pp = _tagged(g)
    proc = tmp_path / "proc"
    _fake_proc(proc, {pp: [pp + 1], pp + 1: []}, {pp: ["sh"]})
    (proc / str(pp + 1)).mkdir(parents=True, exist_ok=True)
    (proc / str(pp + 1) / "cmdline").write_bytes(f"claude\0--resume\0{SID}".encode())
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    res = g.place("b-1")
    assert res.adopted and res.pane_id == pane, res


def test_f9_a_process_tree_past_the_walk_bound_refuses(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    pane, pp = _tagged(g)
    proc = tmp_path / "proc"
    _fake_proc(
        proc,
        {pp: [pp + 1], pp + 1: [pp + 2], pp + 2: [pp + 3], pp + 3: []},
        {pp: ["sh"], pp + 1: ["sd"], pp + 2: ["bash"], pp + 3: ["claude", "--resume", SID]},
    )
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    monkeypatch.setattr(g.mod, "_PROC_WALK_MAX", 2)
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("b-1")
    assert f"process tree of pane {pane} is too large to read" in exc.value.reason, exc.value.reason


def test_f12_an_empty_session_id_refuses_before_any_read(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    log = tmp_path / "calls.log"
    _wrap(g, "log", f'echo "$*" >> "{log}"')
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused):
        g.place("dev5", sid="")
    assert not log.exists(), log.read_text(encoding="utf-8")
    assert g.snapshot() == before


def test_f3_a_leftover_overflow_session_is_killed_before_the_group_is_joined(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """An old base killed left `<S>+3` in a group NAMED `<S>`; `new-session -t =<S>` would join it and give `<S>` the
    old grid's windows. While `<S>` is ungrouped every `<S>+<digits>` is a leftover: killed first."""
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", g.S, "-n", "oldwin", SLEEP)
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+3")
    g.ok("kill-session", "-t", f"={g.S}")
    _full(g)
    assert g.one(g.S, "#{session_group}") == "" and g.one(f"{g.S}+3", "#{session_group}") == g.S
    res = g.place("dev5")
    assert g.sessions() == [g.S, f"{g.S}+2"], g.sessions()
    assert g.windows() == ["agents 4", "agents-2 1"], g.windows()  # never the old grid's `oldwin`
    group = g.one(g.S, "#{session_group}")
    assert group and g.one(f"{g.S}+2", "#{session_group}") == group
    assert g.one(f"{g.S}+2", "#{window_id}") == res.window_id


def test_f8_a_superscript_digit_session_is_not_an_overflow_session(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", f"{g.S}+²", SLEEP)
    _full(g)
    g.place("dev5")
    assert f"{g.S}+²" in g.sessions(), g.sessions()


def test_f11_a_failed_list_sessions_refuses_and_creates_nothing(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    _wrap(g, "nols", '[ "$1" = list-sessions ] && { echo "lost server" >&2; exit 1; }')
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert "tmux read failed" in exc.value.reason and "list-sessions" in exc.value.reason
    assert "lost server" in exc.value.reason, (
        exc.value.reason
    )  # Q2: the rc check, not a missing-<S> read
    assert g.snapshot() == before


def test_f4_an_overflow_session_showing_other_windows_is_not_left_behind(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    # tmux makes the session but not in <S>'s group: it shows its own window, never agents-2
    _wrap(g, "ungrouped", f'[ "$1" = new-session ] && exec $REAL new-session -d -s "$6" {SLEEP}')
    res = g.place("dev5")
    assert f"{g.S}+2" not in g.sessions(), g.sessions()
    assert g.windows() == ["agents 4", "agents-2 1"] and res.new_window_k == 2
    assert "shows other windows than window agents-2" in capsys.readouterr().err


@pytest.mark.parametrize("where", ["split", "new-window"])
def test_f5_a_failed_tag_removes_the_new_pane_and_refuses(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, where: str
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    if where == "split":
        g.base(panes=2, tags=("dev1", "dev2"))
    else:
        _full(g)
    _wrap(g, "noset", '[ "$1" = set ] && { echo "set refused" >&2; exit 1; }')
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert "could not tag" in exc.value.reason, exc.value.reason
    assert g.snapshot() == before


def test_f10_two_windows_sharing_a_name_refuse_naming_both(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    a = g.window("agents-2", 1, ("dev5",))
    b = g.window("agents-2", 1, ("dev6",))
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev7")
    assert a in exc.value.reason and b in exc.value.reason, exc.value.reason
    assert g.snapshot() == before


def test_t1_two_panes_tagged_with_the_name_refuse_naming_both(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    g.base(panes=3, tags=("b-1", "dev2", "b-1"))
    ids = g.lines(
        "list-panes", "-s", "-t", f"={g.S}", "-f", "#{==:#{@agent},b-1}", "-F", "#{pane_id}"
    )
    assert len(ids) == 2
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("b-1")
    assert all(i in exc.value.reason for i in ids), exc.value.reason
    assert g.snapshot() == before


def test_t2_decoy_window_names_are_never_grid_windows(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    decoys = ("agents-2 old", "agents-02", "agents-1", "agents-0", "agentsx", "agents-")
    for d in decoys:
        g.window(d, 1)
    res = g.place("dev5")
    assert res.new_window_k == 2, res
    assert (
        g.ok("display-message", "-p", "-t", res.window_id, "#{window_name} #{window_panes}")
        == "agents-2 1"
    )
    counts = dict(w.rsplit(" ", 1) for w in g.windows())
    assert all(counts[d] == "1" for d in decoys), counts


def test_t2_agents_10_with_room_is_joined_when_lower_windows_are_full_or_absent(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    w10 = g.window("agents-10", 1, ("dev9",))
    res = g.place("dev5")
    assert (res.window_id, res.new_window_k) == (w10, None), res
    assert g.windows() == ["agents 4", "agents-10 2"], g.windows()


def test_t3_a_split_moves_neither_the_active_pane_nor_the_current_window(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    wid = g.base(panes=2, tags=("dev1", "dev2"))
    other = g.window("notes", 1)
    active = g.ok("display-message", "-p", "-t", wid, "#{pane_id}")
    current = g.one(g.S, "#{window_id}")
    assert current == wid and other != wid
    res = g.place("dev3")
    assert res.window_id == wid and res.pane_id != active
    assert g.ok("display-message", "-p", "-t", wid, "#{pane_id}") == active
    assert g.one(g.S, "#{window_id}") == current


@pytest.mark.parametrize("panes", [1, 3])
def test_t4_the_placed_window_is_laid_out_even_horizontal(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, panes: int
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    wid = g.base(panes=panes)
    g.place("dev9")
    placed = g.ok("display-message", "-p", "-t", wid, "#{window_layout}")
    g.ok("select-layout", "-t", wid, "even-horizontal")
    assert g.ok("display-message", "-p", "-t", wid, "#{window_layout}") == placed


def test_t5_the_lowest_window_with_room_wins(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    first = g.base(panes=2)
    g.window("agents-2", 2)
    res = g.place("dev9")
    assert res.window_id == first and g.windows() == ["agents 3", "agents-2 2"], (res, g.windows())
    (tmp_path / "only3").mkdir()
    h = _Grid(tmp_path / "only3", request, monkeypatch)
    w3 = h.base(window="agents-3", panes=2)
    res = h.place("dev9")
    assert (res.window_id, res.new_window_k) == (w3, None) and h.windows() == ["agents-3 3"], (
        h.windows()
    )


# --- T08a review pass 2 ----------------------------------------------------------------------------------------------


def _sid_of_session(g: _Grid, name: str) -> str:
    return g.one(name, "#{session_id}")


def test_p1_a_stale_member_refuses_before_any_leftover_is_killed(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", g.S, "-n", "oldwin", SLEEP)
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+3")
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", "viewer")
    g.ok("kill-session", "-t", f"={g.S}")
    _full(g)
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert "viewer" in exc.value.reason and "kill-session -t =viewer" in exc.value.reason
    assert g.snapshot() == before  # <S>+3 and viewer both still there, nothing created


def test_p2_overflow_named_sessions_outside_the_group_named_s_are_untouched(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", f"{g.S}+7", SLEEP)  # ungrouped, running a process
    g.ok("new-session", "-d", "-s", "elsewhere", SLEEP)
    g.ok("new-session", "-d", "-t", "=elsewhere", "-s", f"{g.S}+8")  # grouped under another name
    _full(g)
    ids = {n: _sid_of_session(g, n) for n in (f"{g.S}+7", f"{g.S}+8")}
    res = g.place("dev5")
    assert {n: _sid_of_session(g, n) for n in ids} == ids
    assert g.one(f"{g.S}+8", "#{session_group}") == "elsewhere"
    group = g.one(g.S, "#{session_group}")
    assert group and g.one(f"{g.S}+2", "#{window_id}") == res.window_id


def test_p3_the_stale_decision_reads_one_snapshot(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    log = tmp_path / "calls.log"
    _wrap(g, "log", f'echo "$*" >> "{log}"')
    g.place("dev5")
    calls = log.read_text(encoding="utf-8").splitlines()
    upto = calls[: next(i for i, c in enumerate(calls) if c.startswith("new-window"))]
    assert sum(c.startswith("list-sessions") for c in upto) == 1, upto
    assert not any(c.startswith("display-message") for c in upto), upto


def test_p3_a_grouped_base_kills_nothing(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+9")  # a live member of <S>'s group
    ids = _sid_of_session(g, f"{g.S}+9")
    g.place("dev5")
    assert _sid_of_session(g, f"{g.S}+9") == ids and f"{g.S}+2" in g.sessions(), g.sessions()


def test_p4_a_failed_group_read_never_kills_the_overflow_session(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+2")
    ids = _sid_of_session(g, f"{g.S}+2")
    _wrap(g, "nobase", f'[ "$1" = display-message ] && [ "$4" = "={g.S}:" ] && exit 1')
    g.place("dev5")
    assert _sid_of_session(g, f"{g.S}+2") == ids
    assert "stays in" in capsys.readouterr().err


def test_p5_a_snapshot_without_s_refuses(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)
    _wrap(
        g,
        "nobase",
        f'[ "$1" = list-sessions ] && {{ $REAL "$@" | grep -v "^{g.S}|~|"; exit 0; }}',
    )
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert f"no session {g.S} in list-sessions" in exc.value.reason, exc.value.reason
    assert g.snapshot() == before


def test_p6_the_walk_stops_at_the_bound_claude(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    pane, pp = _tagged(g)
    proc = tmp_path / "proc"
    kids = [pp + 2 + i for i in range(8)] + [pp + 1]  # the claude is the first walked
    chain = {pp: kids, **{k: [] for k in kids}}
    cmds = {pp: ["sh"], pp + 1: ["claude", "--resume", SID], **{k: ["sleep"] for k in kids[:-1]}}
    _fake_proc(proc, chain, cmds)
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    monkeypatch.setattr(g.mod, "_PROC_WALK_MAX", 3)
    res = g.place("b-1")
    assert res.adopted and res.pane_id == pane, res


# --- T08a review pass 3 ----------------------------------------------------------------------------------------------


def _patch_tmux(g: _Grid, monkeypatch, fake) -> None:
    """Patch `_tmux` in-process: `fake(args)` returns a CompletedProcess or None to run the real call."""
    real = g.mod._tmux

    def patched(*args: str):
        out = fake(args)
        return real(*args) if out is None else out

    monkeypatch.setattr(g.mod, "_tmux", patched)


def test_q1_a_failed_leftover_kill_refuses_and_creates_nothing(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    g.ok("new-session", "-d", "-s", g.S, "-n", "oldwin", SLEEP)
    g.ok("new-session", "-d", "-t", f"={g.S}", "-s", f"{g.S}+3")
    g.ok("kill-session", "-t", f"={g.S}")
    _full(g)
    _patch_tmux(
        g,
        monkeypatch,
        lambda a: (
            subprocess.CompletedProcess(a, 1, "", "kill refused")
            if a[0] == "kill-session"
            else None
        ),
    )
    before = g.snapshot()
    with pytest.raises(g.mod.PlacementRefused) as exc:
        g.place("dev5")
    assert f"{g.S}+3" in exc.value.reason and "kill refused" in exc.value.reason, exc.value.reason
    assert g.snapshot() == before
    assert g.one(g.S, "#{session_group}") == ""


@pytest.mark.parametrize("reads", ["failed", "empty"])
def test_q3_a_failed_create_with_unconfirmed_groups_is_said_and_leaves_nothing(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys, reads: str
) -> None:
    g = _Grid(tmp_path, request, monkeypatch)
    _full(g)

    def fake(a):
        if a[0] == "new-session":
            return subprocess.CompletedProcess(a, 1, "", "create refused")
        if a[0] == "display-message" and a[-1] == "#{session_group}":
            if reads == "failed":
                return subprocess.CompletedProcess(a, 1, "", "read refused")
            return subprocess.CompletedProcess(a, 0, "\n", "")
        return None

    _patch_tmux(g, monkeypatch, fake)
    res = g.place("dev5")
    assert res.new_window_k == 2
    assert f"could not create the tmux session {g.S}+2" in capsys.readouterr().err
    assert g.sessions() == [g.S], g.sessions()


# --- W-b9ad80ae T08b: the cold start, the second headroom measure, the launch -------------------------------------
# `add` runs in-process with the Box's environment, the fake agents_up.sh behind FABRIK_AGENTS_UP and — where a grid is
# needed — a scratch `tmux -L` server behind FABRIK_TMUX (the fake builds the restored grid there). State is asserted: the
# fake's recorded argv/env, the store, the registry, the worktree, the scratch server's panes and tags.

NEW_SID = "12345678-aaaa-4bbb-8ccc-dddddddddddd"


def _scenario(box: Box, **scn) -> None:
    (box.home / "agents-up.json").write_text(json.dumps(scn), encoding="utf-8")


def _calls(box: Box, mode: str | None = None) -> list[dict]:
    log = box.home / "agents-up.log"
    if not log.is_file():
        return []
    rows = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [r for r in rows if mode is None or r["argv"][0] == mode]


def _inproc(box: Box, monkeypatch, request=None, tmp_path=None, **extra: str):
    """Set the Box's environment in this process; with `request`, also a scratch tmux server (returns the _Grid)."""
    for k, v in box.env(**extra).items():
        monkeypatch.setenv(k, v)
    if request is None:
        return None, _load()
    g = _Grid(tmp_path, request, monkeypatch)
    return g, g.mod


def _registry(box: Box) -> dict:
    return json.loads((box.repo / ".fabrik" / "session-agents.json").read_text(encoding="utf-8"))


def test_b1_a_cold_start_restores_the_grid_first_and_a_low_second_measure_refuses_keeping_steps_1_to_5(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    box = Box(tmp_path, registry={OLD: "builder-1", OTHER_SID: "builder-2"})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    # the restored grid takes the room: 31 - (37.5 - 8) = 1.5 GB after it (19 GB at the preflight)
    _scenario(
        box,
        detach=[0],
        grid=["builder-1", "builder-2"],
        detach_current=int(37.5 * GIB),
        builders=["builder-1", "builder-2"],
    )
    assert mod.main(["add", str(box.repo), "builder-3"]) == 2
    detaches = _calls(box, "--detach")
    assert len(detaches) == 1 and detaches[0]["argv"] == ["--detach", str(box.repo)], detaches
    assert "builder-3" not in detaches[0]["bound"], detaches  # both back BEFORE b-3 was recorded
    assert _calls(box, "--print"), "the settle wait read the restored panes"
    assert not _calls(box, "--pane-cmd")  # refused before the launch
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 6, recs
    assert (
        "under the 2 GB floor" in recs[0]["reason"] and "after the cold start" in recs[0]["reason"]
    )
    assert (box.wt("builder-3") / ".git").is_file()
    rows = [r for r in box.rows() if r["name"] == "builder-3"]
    assert len(rows) == 1 and rows[0]["spawned"] is True, rows
    assert _registry(box).get(rows[0]["session_id"]) == "builder-3"
    assert g.tags() == ["agents builder-1", "agents builder-2"], g.tags()


def test_b2_no_session_and_no_builder_starts_the_grid_with_the_new_builder_and_skips_place_pane(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    monkeypatch.delenv(
        "FABRIK_PROC_ROOT"
    )  # the pane's claude-named process is real: read the real /proc
    # the second --detach makes the grid: builder-1 its first pane, a claude carrying --session-id <its bound id>
    _scenario(box, detach=[3, 0], grid=["builder-1"])

    def no_place(*a, **kw):
        raise AssertionError("place_pane must not be called")

    monkeypatch.setattr(mod, "place_pane", no_place)
    assert mod.main(["add", str(box.repo), "builder-1", "--item", ITEM]) == 0
    first, second = _calls(box, "--detach")
    assert first["spawn"] == {} and "builder-1" not in first["bound"], first
    assert second["argv"] == ["--detach", str(box.repo)]
    assert second["spawn"] == {
        "FABRIK_SPAWN_NAME": "builder-1",
        "FABRIK_SPAWN_COORDINATOR": "coordinator",
        "FABRIK_SPAWN_ITEM": ITEM,
    }, second
    # the second --detach resolves it: binding and worktree in place, never started (T02 launches --session-id)
    assert "builder-1" in second["bound"] and "builder-1" in second["worktrees"], second
    rows = [r for r in box.rows() if r["name"] == "builder-1"]
    assert rows[0]["spawned"] is True and rows[0]["pid"] is None
    assert not _calls(box, "--pane-cmd") and not _calls(box, "--print")
    assert not box.refusals()
    assert g.tags() == ["agents builder-1"], g.tags()


def test_b2_a_second_detach_that_fails_stops_at_step_six(tmp_path: Path, monkeypatch) -> None:
    box = Box(tmp_path, registry={})
    _, mod = _inproc(box, monkeypatch)
    _scenario(box, detach=[3, 3])
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 6 and "exited 3" in recs[0]["reason"], recs


@pytest.mark.parametrize("rc", [1, 2, 4])
def test_b2_a_first_detach_failing_otherwise_stops_at_step_three(
    tmp_path: Path, monkeypatch, capsys, rc: int
) -> None:
    box = Box(tmp_path, registry={})
    _, mod = _inproc(box, monkeypatch)
    _scenario(box, detach=[rc])
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 3 and f"exited {rc}" in recs[0]["reason"], recs
    assert not [r for r in box.rows() if r["name"] == "builder-1"]  # step 4 never ran
    assert "add stopped at step 3" in capsys.readouterr().err


@pytest.mark.parametrize(("settle", "label"), [("10", "settles"), ("1", "times-out")])
def test_b3_the_second_measure_follows_the_settle_and_reads_the_grown_value(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys, settle: str, label: str
) -> None:
    box = Box(tmp_path, registry={OLD: "builder-1", OTHER_SID: "builder-2"})
    g, mod = _inproc(box, monkeypatch, request, tmp_path, FABRIK_AGENTS_SETTLE_S=settle)
    _scenario(
        box,
        detach=[0],
        grid=["builder-1", "builder-2"],
        builders=["builder-1", "builder-2"],
        running_after=2,
        print_grow=GIB,
    )
    assert mod.main(["add", str(box.repo), "builder-3"]) == 0
    prints = _calls(box, "--print")
    launch = _calls(box, "--pane-cmd")[0]
    states = (box.home / "print-states.log").read_text(encoding="utf-8").split()
    waited = launch["t"] - prints[0]["t"]
    if label == "settles":
        assert states[-1] == "running" and states[:-1] == ["ok"] * (len(states) - 1), states
        assert 2 <= waited < 10, waited
    else:
        assert set(states) == {"ok"}, states
        assert waited >= 1, waited  # the bound, not the panes, ended the wait
    # 19 GB at the preflight, one GB less per --print: the measure saw the value after the LAST one
    grown = 19 - len(prints)
    err = capsys.readouterr().err
    assert f"fabrik-agents.slice after the cold start: {grown:.1f} GB" in err, err
    assert ("did not all read running in time" in err) == (label == "times-out"), err
    assert "agents builder-3" in g.tags()


def _grid_up(g: _Grid, *tags: str) -> None:
    g.base(panes=len(tags), tags=tags)


@pytest.mark.parametrize("item", [ITEM, None])
def test_b4_the_launch_names_the_callers_coordinator_and_the_item(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, item: str | None
) -> None:
    box = Box(tmp_path, registry={})
    cfg = box.repo / ".fabrik" / "work" / "config.json"
    cfg.write_text(
        json.dumps({"distributor": "coord-a", "base_branch": "master"}), encoding="utf-8"
    )
    g, mod = _inproc(box, monkeypatch, request, tmp_path, CLAUDE_AGENT="coord-a")
    _grid_up(g, "builder-1")
    args = ["add", str(box.repo), "builder-4"] + (["--item", item] if item else [])
    assert mod.main(args) == 0
    (call,) = _calls(box, "--pane-cmd")
    sid = next(r["session_id"] for r in box.rows() if r["name"] == "builder-4")
    want = ["--pane-cmd", str(box.repo), "builder-4", sid, "--new", "--coordinator", "coord-a"]
    assert call["argv"] == want + (["--item", item] if item else []), call
    assert call["spawn"] == {}, call
    assert "agents builder-4" in g.tags()  # the no-item launch starts too


def test_b4_the_cold_start_branch_passes_the_same_facts_by_variable(
    tmp_path: Path, monkeypatch
) -> None:
    box = Box(tmp_path, registry={})
    cfg = box.repo / ".fabrik" / "work" / "config.json"
    cfg.write_text(
        json.dumps({"distributor": "coord-a", "base_branch": "master"}), encoding="utf-8"
    )
    # a stale variable in the caller's environment never reaches the first --detach
    _, mod = _inproc(box, monkeypatch, CLAUDE_AGENT="coord-a", FABRIK_SPAWN_NAME="builder-9")
    assert mod.main(["add", str(box.repo), "builder-4"]) == 0
    first, second = _calls(box, "--detach")
    assert first["spawn"] == {}, first
    assert second["spawn"] == {
        "FABRIK_SPAWN_NAME": "builder-4",
        "FABRIK_SPAWN_COORDINATOR": "coord-a",
    }, second


START = "777"  # the claude's start time in its fake /proc/<pid>/stat (field 22)


def _stat(proc: Path, pid: int, start: str = START) -> None:
    """`/proc/<pid>/stat` with `start` as field 22 (hibernate._proc_start: the 20th field after the `)`)."""
    (proc / str(pid)).mkdir(parents=True, exist_ok=True)
    fields = ["S"] + ["1"] * 18 + [start] + ["0"] * 6
    (proc / str(pid) / "stat").write_text(f"{pid} (claude) {' '.join(fields)}\n", encoding="utf-8")


def _record(box: Box, pid: int, sid: str, start: str = START, where: str = ".claude") -> None:
    """A claude session record (`<home>/.claude*/sessions/*.json`, `pid` + `procStart` + `sessionId`)."""
    d = box.home / where / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(
        json.dumps({"pid": pid, "procStart": start, "sessionId": sid}), encoding="utf-8"
    )


def _pane_pids(g: _Grid) -> dict[str, int]:
    out = g.lines("list-panes", "-s", "-t", f"={g.S}", "-F", "#{@agent} #{pane_pid}")
    return {a: int(p) for a, p in (ln.split() for ln in out)}


def _claude_under(proc: Path, pp: int, argv: list[str], start: str = START) -> int:
    """The pane's shell `pp` with ONE claude child `pp + 1` running `argv`; returns the claude's pid."""
    _fake_proc(proc, {pp: [pp + 1], pp + 1: []}, {pp: ["sh"], pp + 1: argv})
    _stat(proc, pp + 1, start)
    return pp + 1


def _heal_grid(tmp_path, request, monkeypatch, registry, *tags):
    box = Box(tmp_path, registry=registry)
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, *tags)
    proc = tmp_path / "proc"
    proc.mkdir()
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    return box, g, mod, proc


def test_b5_f8_a_row_behind_its_live_session_record_is_re_pointed(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """PF3, F8: a rotation /clears the SAME claude, so its argv keeps the old id; the session record (pid + start
    time) holds the live one, as rotate_session.py reads it."""
    box, g, mod, proc = _heal_grid(
        tmp_path,
        request,
        monkeypatch,
        {OLD: "builder-2", OTHER_SID: "builder-1"},
        "builder-1",
        "builder-2",
    )
    pids = _pane_pids(g)
    c1 = _claude_under(
        proc, pids["builder-1"], ["claude", "-n", "builder-1", "--resume", OTHER_SID]
    )
    c2 = _claude_under(proc, pids["builder-2"], ["claude", "-n", "builder-2", "--resume", OLD])
    _record(box, c1, OTHER_SID)
    _record(
        box, c2, NEW_SID, where=".claude-fleet/acct-b"
    )  # a fleet account's records are read too
    assert mod.main(["add", str(box.repo), "builder-4"]) == 0
    sid4 = next(r["session_id"] for r in box.rows() if r["name"] == "builder-4")
    assert _registry(box) == {NEW_SID: "builder-2", OTHER_SID: "builder-1", sid4: "builder-4"}


def test_b5_f8_a_successful_rotation_is_never_reverted(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """F8: the row already names the record's new id while the argv still carries the old one — nothing changes."""
    box, g, mod, proc = _heal_grid(
        tmp_path, request, monkeypatch, {NEW_SID: "builder-2"}, "builder-2"
    )
    c2 = _claude_under(proc, _pane_pids(g)["builder-2"], ["claude", "--resume", OLD])
    _record(box, c2, NEW_SID)
    path = box.repo / ".fabrik" / "session-agents.json"
    before = path.stat()
    mod.heal_registry(str(box.repo), mod.live_panes(g.S))
    after = path.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    assert _registry(box) == {NEW_SID: "builder-2"}


@pytest.mark.parametrize("shape", ["no-record", "start-mismatch", "other-pid", "no-stat"])
def test_b5_f8_no_matching_record_keeps_the_row(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys, shape: str
) -> None:
    box, g, mod, proc = _heal_grid(tmp_path, request, monkeypatch, {OLD: "builder-2"}, "builder-2")
    c2 = _claude_under(proc, _pane_pids(g)["builder-2"], ["claude", "--resume", NEW_SID])
    if shape == "start-mismatch":
        _record(box, c2, NEW_SID, start="999")
    elif shape == "other-pid":
        _record(box, c2 + 50, NEW_SID)
    elif shape == "no-stat":
        _record(box, c2, NEW_SID)
        (proc / str(c2) / "stat").unlink()
    mod.heal_registry(str(box.repo), mod.live_panes(g.S))
    assert _registry(box) == {OLD: "builder-2"}
    assert "registry row for builder-2 kept" in capsys.readouterr().err


def test_b5_f1_an_id_another_name_holds_keeps_both_rows(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    box, g, mod, proc = _heal_grid(
        tmp_path, request, monkeypatch, {OLD: "builder-2", NEW_SID: "builder-1"}, "builder-2"
    )
    c2 = _claude_under(proc, _pane_pids(g)["builder-2"], ["claude", "--resume", NEW_SID])
    _record(box, c2, NEW_SID)
    mod.heal_registry(str(box.repo), mod.live_panes(g.S))
    assert _registry(box) == {OLD: "builder-2", NEW_SID: "builder-1"}
    err = capsys.readouterr().err
    assert "builder-2 kept" in err and "builder-1" in err, err


@pytest.mark.parametrize("sid", ["not-a-session", NEW_SID.upper(), NEW_SID + "x", ""])
def test_b5_f2_a_record_id_that_is_not_a_session_id_is_never_written(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, sid: str
) -> None:
    box, g, mod, proc = _heal_grid(tmp_path, request, monkeypatch, {OLD: "builder-2"}, "builder-2")
    c2 = _claude_under(proc, _pane_pids(g)["builder-2"], ["claude", f"--resume={sid}"])
    _record(box, c2, sid)
    mod.heal_registry(str(box.repo), mod.live_panes(g.S))
    assert _registry(box) == {OLD: "builder-2"}


def test_b5_heal_registry_touches_nothing_without_a_file_or_with_two_live_ids(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    box, g, mod, proc = _heal_grid(tmp_path, request, monkeypatch, None, "builder-2")
    pp = _pane_pids(g)["builder-2"]
    c2 = _claude_under(proc, pp, ["claude", "--resume", NEW_SID])
    _record(box, c2, NEW_SID)
    panes = mod.live_panes(g.S)
    mod.heal_registry(str(box.repo), panes)
    reg_path = box.repo / ".fabrik" / "session-agents.json"
    assert not reg_path.exists()
    # two claudes under the pane whose records name two different ids: the row is kept
    reg_path.write_text(json.dumps({OLD: "builder-2"}), encoding="utf-8")
    _fake_proc(
        proc,
        {pp: [pp + 1, pp + 2], pp + 1: [], pp + 2: []},
        {pp: ["sh"], pp + 1: ["claude"], pp + 2: ["claude"]},
    )
    _stat(proc, pp + 2)
    _record(box, pp + 2, OTHER_SID)
    mod.heal_registry(str(box.repo), panes)
    assert json.loads(reg_path.read_text(encoding="utf-8")) == {OLD: "builder-2"}


def test_b5_f11_a_failed_heal_is_said_and_the_launch_goes_on(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, "builder-1")

    def broken(root, panes):
        raise mod.RefusedError("the registry is not a valid registry (boom)")

    monkeypatch.setattr(mod, "heal_registry", broken)
    assert mod.main(["add", str(box.repo), "builder-4"]) == 0
    assert "agents builder-4" in g.tags() and not box.refusals()
    assert "registry heal skipped" in capsys.readouterr().err


# ---- review pass 1: the cold start and the settle wait ------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "why"),
    [
        ("abc", "is not a number of seconds"),
        ("-1", "is negative — 0 to 300 seconds"),
        ("nan", "is not a finite number of seconds (0 to 300)"),
        ("inf", "is not a finite number of seconds (0 to 300)"),
        ("1e999", "is not a finite number of seconds (0 to 300)"),
        ("301", "at most 300"),
    ],
)
def test_f6_f9_a_bad_settle_bound_refuses_at_step_three_before_any_detach(
    tmp_path: Path, monkeypatch, value: str, why: str
) -> None:
    box = Box(tmp_path, registry={})
    _, mod = _inproc(box, monkeypatch, FABRIK_AGENTS_SETTLE_S=value)
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 3 and why in recs[0]["reason"], recs
    assert not _calls(box, "--detach")
    assert not [r for r in box.rows() if r["name"] == "builder-1"]


@pytest.mark.parametrize("value", ["0", "2.5", "300", " 20 ", ""])
def test_f6_legitimate_settle_bounds_pass(tmp_path: Path, monkeypatch, value: str) -> None:
    box = Box(tmp_path, registry={})
    _, mod = _inproc(box, monkeypatch, FABRIK_AGENTS_SETTLE_S=value)
    assert mod.main(["add", str(box.repo), "builder-1"]) == 0, box.refusals()


def test_f5_a_print_that_cannot_run_is_not_settled_and_add_goes_on(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    box = Box(tmp_path, registry={OLD: "builder-1"})
    g, mod = _inproc(box, monkeypatch, request, tmp_path, FABRIK_AGENTS_SETTLE_S="1")
    _scenario(box, detach=[0], grid=["builder-1"], builders=["builder-1"])
    real = mod._agents_up

    def fake(step, *args, **kw):
        if args[0] == "--print":
            raise mod.RefusedError("agents_up.sh --print could not run: OSError: boom", step)
        return real(step, *args, **kw)

    monkeypatch.setattr(mod, "_agents_up", fake)
    assert mod.main(["add", str(box.repo), "builder-3"]) == 0, box.refusals()
    assert "agents builder-3" in g.tags()
    assert "did not all read running in time" in capsys.readouterr().err


def test_f5_a_slow_print_never_overruns_the_bound_by_more_than_a_poll(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    box = Box(tmp_path, registry={OLD: "builder-1"})
    g, mod = _inproc(box, monkeypatch, request, tmp_path, FABRIK_AGENTS_SETTLE_S="1")
    _scenario(box, detach=[0], grid=["builder-1"], builders=["builder-1"], print_sleep=5)
    t0 = time.monotonic()
    assert mod.main(["add", str(box.repo), "builder-3"]) == 0, box.refusals()
    detach_t = _calls(box, "--detach")[0]["t"]
    launch_t = _calls(box, "--pane-cmd")[0]["t"]
    assert launch_t - detach_t < 1 + mod.SETTLE_POLL_S + 1.0, launch_t - detach_t
    assert time.monotonic() - t0 < 30


def test_f10_a_rerun_with_an_unstarted_binding_passes_the_facts_to_the_first_detach(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    box = Box(tmp_path, registry={})
    _row(box, SID, "builder-1", spawned=True)  # a first add bound it and stopped before its pane
    _, mod = _inproc(box, monkeypatch, request=None)
    # the restored grid (the Box's stub) holds builder-1's pane, started --session-id SID: step 6 adopts it
    _scenario(box, detach=[0], builders=[])
    assert mod.main(["add", str(box.repo), "builder-1", "--item", ITEM]) == 0, box.refusals()
    (first,) = _calls(box, "--detach")
    assert first["spawn"] == {
        "FABRIK_SPAWN_NAME": "builder-1",
        "FABRIK_SPAWN_COORDINATOR": "coordinator",
        "FABRIK_SPAWN_ITEM": ITEM,
    }, first
    assert not _calls(box, "--pane-cmd") and not box.refusals()
    assert "builder-1's live pane %1 is adopted" in capsys.readouterr().out


def test_f10_a_first_add_passes_no_facts_to_the_first_detach(tmp_path: Path, monkeypatch) -> None:
    box = Box(tmp_path, registry={})
    _row(
        box, SID, "builder-1"
    )  # an --as row (not spawned): a fresh id is minted, nothing to restore
    _, mod = _inproc(box, monkeypatch)
    assert mod.main(["add", str(box.repo), "builder-1"]) == 0
    assert _calls(box, "--detach")[0]["spawn"] == {}


# ---- review pass 1: the no-builder second --detach, the pane command --------------------------------------------


def test_f3_a_second_detach_that_brought_up_a_grid_without_the_builder_falls_through_to_the_launch(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """F3: --detach also exits 0 when another --detach raced it and the grid was already up — never a silent success."""
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _scenario(box, detach=[3, 0], grid=["builder-9"])
    assert mod.main(["add", str(box.repo), "builder-1"]) == 0, box.refusals()
    sid = next(r["session_id"] for r in box.rows() if r["name"] == "builder-1")
    (call,) = _calls(box, "--pane-cmd")
    assert call["argv"][:5] == ["--pane-cmd", str(box.repo), "builder-1", sid, "--new"], call
    assert g.tags() == ["agents builder-1", "agents builder-9"], g.tags()


@pytest.mark.parametrize(
    ("out", "ok"),
    [("sleep 600\n\n", False), ("sleep 600\nsleep 1\n", False), ("\n", False), ("sleep 600", True)],
)
def test_f7_the_pane_command_is_exactly_one_line(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, out: str, ok: bool
) -> None:
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, "builder-1")
    _scenario(box, pane_cmd={"rc": 0, "out": out})
    rc = mod.main(["add", str(box.repo), "builder-4"])
    if ok:
        assert rc == 0 and "agents builder-4" in g.tags()
    else:
        recs = box.refusals()
        assert rc == 2 and len(recs) == 1 and recs[0]["step"] == 6, recs
        assert "no single command line" in recs[0]["reason"], recs
        assert g.tags() == ["agents builder-1"]


def test_b6_a_grid_up_launches_the_pane_cmd_output_unchanged_even_horizontal_and_tagged(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, "builder-1", "builder-2")
    line = "sleep 601 ; : 'a b' \"c\" $HOME"
    _scenario(box, pane_cmd={"rc": 0, "out": line + "\n"})
    seen: list[tuple] = []
    real = mod.place_pane

    def spy(*a):
        seen.append(a)
        return real(*a)

    monkeypatch.setattr(mod, "place_pane", spy)
    assert mod.main(["add", str(box.repo), "builder-4"]) == 0
    assert not _calls(box, "--detach")  # the grid was up: no cold start
    sid = next(r["session_id"] for r in box.rows() if r["name"] == "builder-4")
    assert seen == [(str(box.repo), "shop", "builder-4", sid, str(box.wt("builder-4")), line)], seen
    pane = g.ok(
        "list-panes", "-s", "-t", f"={g.S}", "-f", "#{==:#{@agent},builder-4}", "-F", "#{pane_id}"
    )
    assert pane and g.ok("display-message", "-p", "-t", pane, "#{pane_current_path}") == str(
        box.wt("builder-4")
    )
    wid = g.ok("display-message", "-p", "-t", pane, "#{window_id}")
    widths = g.lines("list-panes", "-t", wid, "-F", "#{pane_top} #{pane_height}")
    assert len({w.split()[0] for w in widths}) == 1, (
        widths
    )  # side by side: one row, even-horizontal
    assert g.tags() == ["agents builder-1", "agents builder-2", "agents builder-4"]


def test_b7_a_refusing_pane_cmd_stops_at_step_six_and_creates_no_pane(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, "builder-1")
    _scenario(
        box,
        pane_cmd={"rc": 2, "out": "", "err": "agents_up: X has a transcript — not a new session\n"},
    )
    before = g.snapshot()
    assert mod.main(["add", str(box.repo), "builder-4"]) == 2
    err = capsys.readouterr().err
    assert (
        "agents_up: X has a transcript — not a new session" in err
        and "add stopped at step 6" in err
    )
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 6 and "has a transcript" in recs[0]["reason"], recs
    assert g.snapshot() == before


def test_b8_a_live_pane_of_the_name_is_adopted_and_pane_cmd_never_runs(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys
) -> None:
    box = Box(tmp_path, registry={})
    _row(box, SID, "builder-4", spawned=True)  # an earlier add bound it; step 4 keeps it
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, "builder-1", "builder-4")
    pane, pp = g.ok(
        "list-panes",
        "-s",
        "-t",
        f"={g.S}",
        "-f",
        "#{==:#{@agent},builder-4}",
        "-F",
        "#{pane_id} #{pane_pid}",
    ).split()
    proc = tmp_path / "proc"
    _fake_proc(
        proc,
        {int(pp): [int(pp) + 1], int(pp) + 1: []},
        {int(pp): ["sh"], int(pp) + 1: ["claude", "-n", "builder-4", "--session-id", SID]},
    )
    monkeypatch.setenv("FABRIK_PROC_ROOT", str(proc))
    _scenario(
        box, pane_cmd={"rc": 2, "out": "", "err": "agents_up: refused\n"}
    )  # the resolver now refuses
    before = g.snapshot()
    assert mod.main(["add", str(box.repo), "builder-4"]) == 0
    assert not _calls(box, "--pane-cmd")
    assert g.snapshot() == before and not box.refusals()
    assert f"builder-4's live pane {pane} is adopted" in capsys.readouterr().out


# --- T08b review pass 2: the no-builder branch after the second --detach -------------------------------------------


def test_p1_the_new_panes_claude_starting_late_is_waited_for_and_adopted(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """P1: a capped pane is still `sh → systemd-run → bash -c` when --detach returns; its claude is waited for."""
    box = Box(tmp_path, registry={})
    _, mod = _inproc(box, monkeypatch, FABRIK_AGENTS_SETTLE_S="10")
    _scenario(box, claude_after=0.5)
    t0 = time.monotonic()
    assert mod.main(["add", str(box.repo), "builder-1"]) == 0, box.refusals()
    assert time.monotonic() - t0 < 10
    assert len(_calls(box, "--detach")) == 2 and not _calls(box, "--pane-cmd")
    assert not box.refusals()
    assert "the grid was started with builder-1 as its first pane" in capsys.readouterr().out


def test_p1_a_claude_that_never_starts_refuses_at_the_bound(tmp_path: Path, monkeypatch) -> None:
    box = Box(tmp_path, registry={})
    _, mod = _inproc(box, monkeypatch, FABRIK_AGENTS_SETTLE_S="1")
    _scenario(box, claude_after="never")
    t0 = time.monotonic()
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    assert time.monotonic() - t0 >= 1
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 6, recs
    want = "builder-1's new pane started no claude within the settle bound (1 s) — re-run add once it starts"
    assert recs[0]["reason"] == want, recs
    assert "respawn" not in recs[0]["reason"], recs
    assert not _calls(box, "--pane-cmd")


def test_p1_a_pane_running_another_session_refuses_at_once(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """P1's guard: only a pane with NO claude yet is waited for; a different session is never adopted or waited on."""
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path, FABRIK_AGENTS_SETTLE_S="10")
    monkeypatch.delenv("FABRIK_PROC_ROOT")
    _scenario(box, detach=[3, 0], grid=["builder-1"])
    # the pane the grid makes runs claude with the bound id; re-bind the name to ANOTHER id before step 6 reads it
    real_launch = mod.place_and_launch

    def launch(ctx):
        ctx.sid = OTHER_SID
        return real_launch(ctx)

    monkeypatch.setattr(mod, "place_and_launch", launch)
    t0 = time.monotonic()
    assert mod.main(["add", str(box.repo), "builder-1"]) == 2
    assert time.monotonic() - t0 < 5
    recs = box.refusals()
    assert len(recs) == 1 and recs[0]["step"] == 6 and OTHER_SID in recs[0]["reason"], recs
    assert not _calls(box, "--pane-cmd")


def test_q1_a_grid_up_pane_with_no_claude_keeps_the_respawn_advice(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch
) -> None:
    """Q1's other half: outside the no-builder path, `_adopt`'s text (the respawn remedy) is unchanged."""
    box = Box(tmp_path, registry={})
    _row(box, SID, "builder-4", spawned=True)
    g, mod = _inproc(box, monkeypatch, request, tmp_path)
    _grid_up(g, "builder-1", "builder-4")  # builder-4's pane runs a plain sleep: no claude
    assert mod.main(["add", str(box.repo), "builder-4"]) == 2
    (rec,) = box.refusals()
    assert (
        rec["step"] == 6 and "runs no claude — respawn it (`tmux respawn-pane -k" in rec["reason"]
    ), rec


def _proc_start_of(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def _dead_pid() -> int:
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


@pytest.mark.parametrize("who", ["live", "dead", "reused-pid", "malformed"])
def test_p2_a_grid_another_start_is_still_building_is_never_fallen_through(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch, capsys, who: str
) -> None:
    """P2: the second --detach exits 0 while another agents_up.sh still builds the grid (its `@agents_up_building`
    names a live pid with that pid's start time): wait to the bound, then refuse — never a second launch. A dead pid, a
    pid whose start time is another process's, or a malformed value reads "not building" and the launch goes on."""
    box = Box(tmp_path, registry={})
    g, mod = _inproc(box, monkeypatch, request, tmp_path, FABRIK_AGENTS_SETTLE_S="1")
    value = {
        "live": f"{os.getpid()}:{_proc_start_of(os.getpid())}",
        "dead": f"{_dead_pid()}:12345",
        "reused-pid": f"{os.getpid()}:1",
        "malformed": f"{os.getpid()}",
    }[who]
    _scenario(box, detach=[3, 0], grid=["builder-9"], building=value)
    rc = mod.main(["add", str(box.repo), "builder-1"])
    if who == "live":
        assert rc == 2
        recs = box.refusals()
        assert len(recs) == 1 and recs[0]["step"] == 6, recs
        assert "another start is building the shop grid — re-run add" in recs[0]["reason"], recs
        assert not _calls(box, "--pane-cmd")
        assert g.tags() == ["agents builder-9"], g.tags()
    else:
        assert rc == 0, box.refusals()
        assert len(_calls(box, "--pane-cmd")) == 1
        assert g.tags() == ["agents builder-1", "agents builder-9"], g.tags()
