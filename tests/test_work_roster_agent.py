"""W-84ad2ff1: a pool worker is named by the agent its live window is bound to, not by its worktree directory.

infra's live window ran in `.claude/worktrees/infra-uncapped` (CLAUDE_AGENT=infra), so `work.py` listed a present
worker `infra-uncapped` with an empty queue and the coordinator's Stop hook demanded triage every turn. Every test
runs against a throwaway git repo and a fake process table (`FABRIK_WORK_PROC`) whose claude entries carry `comm`,
`cwd`, `cmdline`, `environ` and `stat`, as Linux shows them; the whoami store is a tmp file (`AGENT_IDENTITY_FILE`).
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wc = _load(
    "_roster_wc", Path(__file__).with_name("test_work_coordinator.py")
)  # the suite's repo helpers
work = _load("_roster_work", SCRIPT)


def _claude(root: Path, pid: int, cwd: Path, agent: str | None = None, start: int = 5000) -> None:
    """One claude window: comm, cwd, cmdline, environ (CLAUDE_AGENT when given) and stat (field 22 = start)."""
    d = root / str(pid)
    d.mkdir(parents=True)
    (d / "comm").write_text("claude\n", encoding="utf-8")
    os.symlink(cwd, d / "cwd")
    (d / "cmdline").write_bytes(b"claude\0")
    (d / "environ").write_bytes(f"CLAUDE_AGENT={agent}\0".encode() if agent else b"HOME=/x\0")
    (d / "stat").write_text(f"{pid} (claude) " + " ".join(["S"] + ["0"] * 18 + [str(start)]) + "\n")


def _world(tmp_path: Path, monkeypatch, trees: tuple[str, ...]):
    env = wc._env(tmp_path, agent="coord")
    repo = wc._repo(tmp_path, env)
    wc._init(repo, env, distributor="coord")
    wc._git(repo, env, "add", ".fabrik")
    wc._git(repo, env, "commit", "-q", "-m", "store")
    out = {}
    for name in trees:
        wt = repo / ".claude" / "worktrees" / name
        wc._git(repo, env, "worktree", "add", "-q", "-b", f"w-{name}", str(wt))
        out[name] = wt.resolve()
    proc = tmp_path / "proc"
    proc.mkdir()
    for k in ("HOME", "AGENT_IDENTITY_FILE", "GIT_CONFIG_NOSYSTEM"):
        monkeypatch.setenv(k, env[k])
    monkeypatch.setenv("FABRIK_WORK_PROC", str(proc))
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    work._PROC_CACHE.clear()
    return repo, out, proc


def _bind(name: str, pid: int, start: int) -> None:
    path = Path(os.environ["AGENT_IDENTITY_FILE"])
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"session_id": f"s-{pid}", "name": name, "pid": pid, "pid_start": start})
            + "\n"
        )


def _roster(repo: Path) -> dict[str, str]:
    work._PROC_CACHE.clear()
    return {k: v.name for k, v in work._workers(repo).items()}


def test_a_live_tree_is_named_by_its_bound_agent(tmp_path, monkeypatch):
    """The live stray tree takes its agent's name; the idle same-named tree yields; the others stay."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("infra", "infra-uncapped", "fleet"))
    _claude(proc, 100, t["infra-uncapped"], agent="infra")
    _claude(proc, 101, t["fleet"], agent="fleet")
    assert _roster(repo) == {"infra": "infra-uncapped", "fleet": "fleet"}
    assert work._present(work._workers(repo)) == {"infra", "fleet"}


def test_the_name_comes_from_environ_else_the_session_binding(tmp_path, monkeypatch):
    """No CLAUDE_AGENT: the whoami row with this pid AND pid_start names it; a stale pid_start does not."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("stray",))
    _claude(proc, 200, t["stray"], start=7777)
    _bind("dev1", 200, 1234)  # a reused pid: an older process's row
    assert _roster(repo) == {"stray": "stray"}
    _bind("dev1", 200, 7777)
    assert _roster(repo) == {"dev1": "stray"}


@pytest.mark.parametrize(
    "case",
    [
        "no-name",
        "bad-name",
        "two-names-in-one-tree",
        "two-stray-trees",
        "distributor",
        "second-window",
    ],
)
def test_unreadable_or_ambiguous_bindings_keep_the_directory_name(tmp_path, monkeypatch, case):
    """Fail-open to the directory name; a tree bound to the distributor, or an agent's second window while its own
    tree is live, leaves the pool (never a worker under a borrowed name)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("infra", "a", "b"))
    want = {"infra": "infra", "a": "a", "b": "b"}
    if case == "no-name":
        _claude(proc, 300, t["a"])
    elif case == "bad-name":
        _claude(proc, 300, t["a"], agent="Not_A_Name")
    elif case == "two-names-in-one-tree":
        _claude(proc, 300, t["a"], agent="dev1")
        _claude(proc, 301, t["a"], agent="dev2")
    elif case == "two-stray-trees":
        _claude(proc, 300, t["a"], agent="dev1")
        _claude(proc, 301, t["b"], agent="dev1")
    elif case == "distributor":
        _claude(proc, 300, t["a"], agent="coord")
        want = {"infra": "infra", "b": "b"}
    elif case == "second-window":
        _claude(proc, 300, t["infra"], agent="infra")
        _claude(proc, 301, t["a"], agent="infra")
        want = {"infra": "infra", "b": "b"}
    assert _roster(repo) == want


def test_the_floor_and_triage_use_the_bound_name(tmp_path, monkeypatch):
    """The coordinator's floor counts the window under its agent's name; a pause under the tree's directory name
    still covers it."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("infra", "infra-uncapped"))
    _claude(proc, 100, t["infra-uncapped"], agent="infra")
    workers = work._workers(repo)
    assert work._present(workers) == {"infra"} and workers["infra"] == t["infra-uncapped"]
    paused = {"infra-uncapped": {"words": "w"}}
    assert work._is_paused(paused, "infra", t["infra-uncapped"], workers) == "infra-uncapped"
    assert work._is_paused({}, "infra", t["infra-uncapped"], workers) == ""
