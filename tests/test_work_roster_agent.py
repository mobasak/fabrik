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


@pytest.mark.parametrize("order", ["forward", "reverse"])
@pytest.mark.parametrize("case", ["swap", "chain"])
def test_renames_are_decided_on_a_snapshot_whatever_the_proc_order(
    tmp_path, monkeypatch, case, order
):
    """Two trees bound to each other's names swap; a tree bound to a name whose own tree is bound away takes it —
    and the /proc scan order never changes the answer (review C2, H1)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a", "b") if case == "swap" else ("dev1", "a"))
    pids = (400, 401) if order == "forward" else (401, 400)
    if case == "swap":
        _claude(proc, pids[0], t["a"], agent="b")
        _claude(proc, pids[1], t["b"], agent="a")
        assert _roster(repo) == {"a": "b", "b": "a"}
    else:
        _claude(proc, pids[0], t["dev1"], agent="dev2")
        _claude(proc, pids[1], t["a"], agent="dev1")
        assert _roster(repo) == {"dev1": "a", "dev2": "dev1"}


def test_a_name_a_kept_tree_holds_is_never_taken(tmp_path, monkeypatch):
    """A tree whose windows give two names keeps its directory; a tree bound to that directory name keeps its own."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a", "b"))
    _claude(proc, 300, t["a"], agent="dev1")
    _claude(proc, 301, t["a"], agent="dev2")
    _claude(proc, 302, t["b"], agent="a")
    assert _roster(repo) == {"a": "a", "b": "b"}


def test_a_tree_bound_to_the_feedback_owner_leaves_the_pool(tmp_path, monkeypatch):
    """The feedback owner (not the distributor) works its ledger, never the pool — under a borrowed tree too (H2)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a", "b"))
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["feedback_owner"] = "kz"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    _claude(proc, 300, t["a"], agent="kz")
    assert _roster(repo) == {"b": "b"}


def test_a_bad_stored_pid_or_a_binding_error_keeps_the_directory_roster(tmp_path, monkeypatch):
    """A whoami row whose pid is a superscript two names nothing; any error in the re-key leaves the directory map
    (review C1: `int('²')` escaped `_workers` into the Stop hook)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a",))
    _claude(proc, 500, t["a"], start=42)
    path = Path(os.environ["AGENT_IDENTITY_FILE"])
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"session_id": "s", "name": "dev1", "pid": "²", "pid_start": 42}) + "\n"
        )
    assert work._as_int("²") is None
    assert _roster(repo) == {"a": "a"}
    _bind(
        "dev1", 500, 42
    )  # the bad row is skipped on its own: a good row beside it still names the window
    assert _roster(repo) == {"dev1": "a"}

    def boom(*_a):
        raise ValueError("unexpected")

    monkeypatch.setattr(work, "_proc_agent", boom)
    assert _roster(repo) == {"a": "a"}


def test_a_directory_pause_never_covers_a_tree_whose_name_another_worker_carries(
    tmp_path, monkeypatch
):
    """Tree `fleet` holds infra's window while fleet works elsewhere: a pause of fleet is fleet's, not infra's (H3)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("fleet", "x"))
    _claude(proc, 600, t["fleet"], agent="infra")
    _claude(proc, 601, t["x"], agent="fleet")
    workers = work._workers(repo)
    assert {k: v.name for k, v in workers.items()} == {"infra": "fleet", "fleet": "x"}
    assert work._is_paused({"fleet": {"words": "w"}}, "infra", t["fleet"], workers) == ""
    assert work._is_paused({"fleet": {"words": "w"}}, "fleet", t["x"], workers) == "fleet"


def test_a_directory_pause_stops_the_floor_triage_and_status_too(tmp_path, monkeypatch):
    """`pause infra-uncapped` parks the window re-keyed to infra in the coordinator's floor, triage and status, as
    the Stop hook already did (review r1: the floor and triage subtracted pause NAMES, so infra stayed present)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("infra", "infra-uncapped"))
    _claude(proc, 100, t["infra-uncapped"], agent="infra")
    env = {**wc._env(tmp_path, agent="coord"), "FABRIK_WORK_PROC": str(proc)}
    wc._add(repo, env, "task", "free")
    assert wc._stop(repo, env, session="sid-coord")["action"] == "triage"
    paused = wc.run(["pause", "infra-uncapped"], env, repo)
    assert paused.returncode == 0 and "no worker tree" not in paused.stderr, paused.stderr
    assert wc._stop(repo, env, session="sid-coord")["action"] in (None, "commit-items")
    plan = wc.run(["triage"], env, repo)
    assert plan.returncode == 0 and "plan: infra" not in plan.stdout, plan.stdout
    row = next(a for a in wc._queue(repo, env)["agents"] if a["agent"] == "infra")
    assert row.get("paused_by"), row


def test_a_directory_pause_covers_a_dropped_second_window(tmp_path, monkeypatch):
    """A tree dropped as an agent's second window is still covered by a pause under its directory name."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("infra", "a"))
    _claude(proc, 100, t["infra"], agent="infra")
    _claude(proc, 101, t["a"], agent="infra")
    workers = work._workers(repo)
    assert "a" not in workers
    assert work._is_paused({"a": {"words": "w"}}, "infra", t["a"], workers) == "a"
    # the main checkout is no linked tree: a pause named after its directory never covers the coordinator there
    assert work._is_paused({repo.name: {"words": "w"}}, "coord", repo, workers) == ""


def test_an_unnamed_window_beside_a_named_one_keeps_the_directory_name(tmp_path, monkeypatch):
    """An unnamed window reads as its directory's agent, so a tree holding it and a window bound elsewhere is
    ambiguous and keeps its name (review r1 C-A4)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a",))
    _claude(proc, 100, t["a"])
    _claude(proc, 101, t["a"], agent="dev1")
    assert _roster(repo) == {"a": "a"}


def test_the_binding_read_edges(tmp_path, monkeypatch):
    """The last whoami row wins; a digit-string pid counts and a boolean never does; a window in a subdirectory
    of its tree is live; a comm holding ')' does not shift the stat fields (review r1 T1, T3, T4, T5, A2)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a",))
    sub = t["a"] / "scripts"
    sub.mkdir(exist_ok=True)
    _claude(proc, 700, sub, start=9)
    _bind("dev1", 700, 9)
    _bind("dev2", 700, 9)
    assert _roster(repo) == {"dev2": "a"}
    (proc / "700" / "stat").write_text(
        "700 (cl) aude) " + " ".join(["S"] + ["0"] * 18 + ["9"]) + "\n"
    )
    assert _roster(repo) == {"dev2": "a"}
    assert work._as_int(True) is None and work._as_int(" 42 ") == 42
    path = Path(os.environ["AGENT_IDENTITY_FILE"])
    path.write_text(
        json.dumps({"session_id": "s", "name": "dev3", "pid": "700", "pid_start": "9"}) + "\n"
    )
    assert _roster(repo) == {"dev3": "a"}
    # a process may set any bytes as its comm, and a proc root entry may be a non-ASCII numeral: both are skipped
    (proc / "²").mkdir()
    (proc / "²" / "comm").write_text("claude\n", encoding="utf-8")
    os.symlink(t["a"], proc / "²" / "cwd")
    (proc / "801").mkdir()
    (proc / "801" / "comm").write_bytes(b"\xffclaude\n")
    work._PROC_CACHE.clear()
    assert [p for p, _ in work._claude_procs() or []] == [700]
    # a cwd that is a symlink loop (RuntimeError under resolve()) is skipped too
    (proc / "802").mkdir()
    (proc / "802" / "comm").write_text("claude\n", encoding="utf-8")
    loop = tmp_path / "loop"
    os.symlink(loop, loop)
    os.symlink(loop, proc / "802" / "cwd")
    work._PROC_CACHE.clear()
    assert [p for p, _ in work._claude_procs() or []] == [700]


def test_a_bad_or_vanished_binding_names_nothing_for_that_window_only(tmp_path, monkeypatch):
    """A window whose stat vanished, or whose whoami row holds an invalid name, keeps its directory name while
    another tree's binding still applies (review r1 C7, C8: a stat error escaping would drop every binding)."""
    repo, t, proc = _world(tmp_path, monkeypatch, ("a", "b", "c"))
    _claude(proc, 900, t["a"], start=1)
    (proc / "900" / "stat").unlink()
    _claude(proc, 901, t["b"], start=2)
    _bind("Not_A_Name", 901, 2)
    _claude(proc, 902, t["c"], agent="dev1")
    assert _roster(repo) == {"a": "a", "b": "b", "dev1": "c"}
