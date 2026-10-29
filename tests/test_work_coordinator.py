"""The coordinator's queue and triage (W-83021827, D-512 rebuilt in the simpler shape).

`work.py queue` reports per-agent queued work, `triage` tops present workers up to the floor, and
`queue --stop` gives the Stop hook one action. Every test runs against a throwaway git repo with a
fake process table (`FABRIK_WORK_PROC`), so presence is the real scan over a controlled `/proc`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"


def _env(tmp_path: Path, agent: str | None = None) -> dict[str, str]:
    """Hermetic: HOME and TMPDIR under tmp_path, git reads no user config, no session id."""
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp_path / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "tmp" / "state" / "command-runs"),
        "AGENT_IDENTITY_FILE": str(tmp_path / "tmp" / "identity.jsonl"),
        "FABRIK_WORK_PROC": os.environ.get("FABRIK_WORK_PROC", ""),  # conftest pin
    }
    if agent is not None:
        env["CLAUDE_AGENT"] = agent
    return env


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


def _repo(tmp_path: Path, env: dict[str, str]) -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "master", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    return work.resolve()


def run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _init(repo: Path, env: dict[str, str], distributor: str) -> None:
    r = run(["init", "--distributor", distributor], env, repo)
    assert r.returncode == 0, r.stderr


def _items(repo: Path) -> dict[str, dict]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((repo / ".fabrik" / "work").glob("W-*.json"))
    }


SID = "sid-worker"


def _proc(tmp_path: Path, *cwds: Path) -> Path:
    """A fake /proc: one `claude` process per cwd (comm + cwd symlink, as Linux shows them)."""
    root = tmp_path / "proc"
    root.mkdir(exist_ok=True)
    for n, cwd in enumerate(cwds, start=100):
        d = root / str(n)
        d.mkdir()
        (d / "comm").write_text("claude\n", encoding="utf-8")
        os.symlink(cwd, d / "cwd")
    # a non-claude process inside a worktree must not count
    other = root / "999"
    other.mkdir()
    (other / "comm").write_text("bash\n", encoding="utf-8")
    if cwds:
        os.symlink(cwds[0], other / "cwd")
    return root


def _setup(tmp_path: Path, *, workers: tuple[str, ...] = (), present: tuple[str, ...] = ()):
    env = _env(tmp_path, agent="coord")
    repo = _repo(tmp_path, env)
    _init(repo, env, distributor="coord")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "store")
    trees = {}
    for name in workers:
        wt = repo / ".claude" / "worktrees" / name
        _git(repo, env, "worktree", "add", "-q", "-b", f"w-{name}", str(wt))
        trees[name] = wt
    # a harness worktree is never a worker
    _git(
        repo,
        env,
        "worktree",
        "add",
        "-q",
        "-b",
        "h",
        str(repo / ".claude" / "worktrees" / ("agent-" + "a" * 17)),
    )
    env["FABRIK_WORK_PROC"] = str(_proc(tmp_path, *(trees[n] for n in present)))
    return env, repo, trees


def _add(repo: Path, env: dict, kind: str = "task", title: str = "T", *extra: str) -> str:
    r = run(["add", "--kind", kind, "--title", title, *extra], env, repo)
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip().splitlines()[-1]).stem


def _assign(repo: Path, env: dict, item: str, owner: str, *extra: str) -> None:
    r = run(["assign", item, "--owner", owner, *extra], env, repo)
    assert r.returncode == 0, r.stderr


def _queue(repo: Path, env: dict) -> dict:
    r = run(["queue", "--json"], env, repo)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[0])


def _stop(cwd: Path, env: dict, session: str = SID) -> dict:
    r = run(["queue", "--stop", "--session", session, "--cwd", str(cwd)], env, cwd)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 1, f"--stop must print exactly one line, got {r.stdout!r}"
    return json.loads(lines[0])


def test_queued_excludes_mail_and_untagged_backlog_and_routable_excludes_held(tmp_path):
    env, repo, _ = _setup(tmp_path)
    owned_task = _add(repo, env, "task", "mine")
    owned_backlog = _add(repo, env, "backlog", "mine later")
    promoted = _add(repo, env, "backlog", "promoted")
    mail_item = _add(repo, env, "backlog", "mail obligation")
    for item in (owned_task, owned_backlog, mail_item):
        _assign(repo, env, item, "coord")
    _assign(repo, env, promoted, "coord", "--tag", "queued")
    path = repo / ".fabrik" / "work" / f"{mail_item}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["kind"] = "mail"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _add(repo, env, "task", "free")
    _add(repo, env, "backlog", "free promoted", "--tag", "queued")
    _add(repo, env, "task", "reload", "--tag", "runtime")
    _add(repo, env, "task", "parked", "--tag", "hold")
    _add(repo, env, "task", "waiting", "--tag", "waits-volkan")
    _add(repo, env, "backlog", "someday")
    q = _queue(repo, env)
    me = {a["agent"]: a for a in q["agents"]}["coord"]
    assert me["queued"] == 2, (
        q
    )  # the task and the queued-tagged backlog — never mail or plain backlog
    assert q["routable"] == 2, q  # free task + free promoted backlog; runtime/hold/waits-* excluded
    assert q["backlog_waiting"] == 1, q
    assert q["held"] == 3, q


def test_triage_apply_tops_up_present_workers_only_and_never_promotes(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1", "w2"), present=("w1",))
    tasks = [_add(repo, env, "task", f"t{n}") for n in range(5)]
    backlog = _add(repo, env, "backlog", "someday")
    plan = run(["triage"], env, repo)
    assert plan.returncode == 0, plan.stderr
    assert all(i["owner"] in ("", None) or "owner" not in i for i in _items(repo).values()), (
        "triage without --apply must write nothing"
    )
    refused = run(["triage", "--apply"], {**env, "CLAUDE_AGENT": "w1"}, repo)
    assert refused.returncode == 1 and "distributor" in refused.stderr
    applied = run(["triage", "--apply"], env, repo)
    assert applied.returncode == 0, applied.stderr
    owners = {i["id"]: i.get("owner", "") for i in _items(repo).values()}
    assert [owners[t] for t in tasks].count("w1") == 3, owners  # the floor, K = 3
    assert "w2" not in owners.values(), "an absent worker (no claude process) is never topped up"
    assert owners[backlog] == "", "triage never promotes backlog"
    assert "w1" in applied.stdout and "merge" in applied.stdout


def test_stop_claim_for_a_worker_with_queued_work_in_its_own_tree(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    item = _add(trees["w1"], env, "task", "in my tree")
    _assign(trees["w1"], env, item, "w1")
    out = _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})
    assert out["action"] == "claim", out
    assert item in out["text"] and "work.py claim" in out["text"]


def test_stop_doorbell_for_an_empty_worker_when_only_backlog_waits(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    _add(repo, env, "backlog", "strategic")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "backlog")
    out = _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})
    assert out["action"] == "doorbell", out
    assert "backlog" in out["text"]


def test_stop_triage_for_the_coordinator_with_a_worker_below_the_floor(tmp_path):
    env, repo, _ = _setup(tmp_path, workers=("w1",), present=("w1",))
    _add(repo, env, "task", "free")
    out = _stop(repo, env, session="sid-coord")
    assert out["action"] == "triage", out
    assert "work.py triage --apply" in out["text"]


def test_stop_self_in_a_one_window_repo_with_only_backlog_and_no_name(tmp_path):
    env, repo, _ = _setup(tmp_path)
    _add(repo, env, "backlog", "strategic")
    nameless = {k: v for k, v in env.items() if k != "CLAUDE_AGENT"}
    out = _stop(repo, nameless, session="sid-solo")
    assert out["action"] == "self", out
    assert "--tag queued" in out["text"]


def test_stop_null_when_nothing_waits_or_a_claim_is_live(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    assert _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})["action"] is None
    item = _add(trees["w1"], env, "task", "mine")
    _assign(trees["w1"], env, item, "w1")
    r = run(["claim", item, "--session", SID], {**env, "CLAUDE_AGENT": "w1"}, trees["w1"])
    assert r.returncode == 0, r.stderr
    assert _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})["action"] is None


def test_stop_line_carries_a_count_fingerprint_not_ids(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    a = _add(trees["w1"], env, "task", "a")
    _assign(trees["w1"], env, a, "w1")
    first = _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})["fp"]
    b = _add(trees["w1"], env, "task", "b")
    _assign(trees["w1"], env, b, "w1")
    second = _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})["fp"]
    assert a not in first and first == second, (first, second)


def test_stop_with_a_cwd_outside_any_repo_prints_one_null_line(tmp_path):
    env, repo, _ = _setup(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    # the hook runs from inside the repo and passes the session's cwd, which may be anywhere
    r = run(["queue", "--stop", "--session", SID, "--cwd", str(outside)], env, repo)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["action"] is None, r.stdout


def test_the_floor_is_clamped_to_one_and_a_bad_value_falls_back(tmp_path):
    env, repo, _ = _setup(tmp_path)
    cfg = repo / ".fabrik" / "work" / "config.json"
    for raw, want in ((0, 1), (-2, 1), ("x", 3)):
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["queue_floor"] = raw
        cfg.write_text(json.dumps(data), encoding="utf-8")
        assert _queue(repo, env)["floor"] == want, raw


def test_a_worker_whose_only_process_is_not_claude_is_absent(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1", "w3"), present=("w1",))
    proc = Path(env["FABRIK_WORK_PROC"])
    d = proc / "777"
    d.mkdir()
    (d / "comm").write_text("bash\n", encoding="utf-8")
    os.symlink(trees["w3"], d / "cwd")
    for n in range(6):
        _add(repo, env, "task", f"t{n}")
    assert run(["triage", "--apply"], env, repo).returncode == 0
    owners = {i.get("owner", "") for i in _items(repo).values()}
    assert "w1" in owners and "w3" not in owners, owners


def test_a_shipped_plan_is_not_listed_as_open(tmp_path):
    env, repo, _ = _setup(tmp_path)
    plans = repo / "docs" / "development" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-01-01-plan-1.md").write_text(
        "# p\n\nStatus: SHIPPED (phases 1-8)\n", encoding="utf-8"
    )
    (plans / "2026-01-02-plan-2.md").write_text("# q\n\nStatus: CONVERGED\n", encoding="utf-8")
    listed = " ".join(_queue(repo, env)["plans"])
    assert "plan-2" in listed and "plan-1" not in listed, listed


def test_an_open_plan_set_is_listed_by_its_spine(tmp_path):
    """web-ecommerce-factory 01M46V7T0CR4MAXBF3K5D0FSDD: the plans glob was one level deep, so a
    directory-form set (`plans/<stem>/<stem>.md` + `T##` tickets) was never listed while open."""
    env, repo, _ = _setup(tmp_path)
    plans = repo / "docs" / "development" / "plans"
    for stem, status in (
        ("2026-01-03-plan-1-open-set", "CONVERGED"),
        ("2026-01-04-plan-2-done-set", "EXECUTED"),
    ):
        (plans / stem).mkdir(parents=True)
        (plans / stem / f"{stem}.md").write_text(f"# s\n\nStatus: {status}\n", encoding="utf-8")
        (plans / stem / "T01-ticket.md").write_text("# T01\n\nStatus: DRAFT\n", encoding="utf-8")
    (plans / "archived" / "2026-01-05-plan-3-old").mkdir(parents=True)
    old = plans / "archived" / "2026-01-05-plan-3-old" / "2026-01-05-plan-3-old.md"
    old.write_text("# o\n\nStatus: DRAFT\n", encoding="utf-8")
    (plans / "notes").mkdir()
    (plans / "notes" / "scratch.md").write_text("# n\n\nStatus: DRAFT\n", encoding="utf-8")
    # an undated directory is not a plan set, even with a same-stem file
    (plans / "notes" / "notes.md").write_text("# n\n\nStatus: DRAFT\n", encoding="utf-8")
    # review round 1: a dated set holding only tickets, an ARCHIVED spine still in plans/, and an
    # unreadable plan are skipped without emptying the view
    (plans / "2026-01-06-plan-4-tickets-only").mkdir()
    (plans / "2026-01-06-plan-4-tickets-only" / "T01-a.md").write_text("Status: DRAFT\n")
    (plans / "2026-01-07-plan-5-archived").mkdir()
    (plans / "2026-01-07-plan-5-archived" / "2026-01-07-plan-5-archived.md").write_text(
        "# a\n\nStatus: ARCHIVED\n", encoding="utf-8"
    )
    locked = plans / "2026-01-08-plan-6-locked"
    locked.mkdir()
    (locked / f"{locked.name}.md").write_text("# l\n\nStatus: DRAFT\n", encoding="utf-8")
    locked.chmod(0)
    try:
        listed = _queue(repo, env)["plans"]
    finally:
        locked.chmod(0o755)
    joined = " ".join(listed)
    assert "2026-01-03-plan-1-open-set/2026-01-03-plan-1-open-set.md" in joined, listed
    assert "tickets-only" not in joined and "plan-5-archived" not in joined, listed
    assert "done-set" not in joined and "plan-3-old" not in joined, listed
    assert "T01-ticket" not in joined and "notes/" not in joined, listed


def test_triage_reports_only_what_it_wrote_when_an_item_was_taken_meanwhile(
    tmp_path, monkeypatch, capsys
):
    import contextlib
    import importlib.util

    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    item = _add(repo, env, "task", "contested")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location("work_triage_race", SCRIPT)
    work = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(work)
    real_lock = work._store_lock

    @contextlib.contextmanager
    def racing_lock(*a, **kw):
        fresh = work._read_item(repo, item)
        fresh["owner"] = "someone-else"
        work._write_item(repo, fresh)
        with real_lock(*a, **kw) as held:
            yield held

    monkeypatch.setattr(work, "_store_lock", racing_lock)
    import argparse

    assert work.cmd_triage(repo, argparse.Namespace(apply=True)) == 0
    out = capsys.readouterr().out
    assert f"skipped {item}" in out
    assert "SendMessage" not in out, "no worker is told of an assignment that did not happen"
    assert _items(repo)[item]["owner"] == "someone-else"


def _commit_store(repo: Path, env: dict, msg: str = "store") -> None:
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", msg)


def _owned(repo: Path, owner: str) -> list[str]:
    return sorted(i["id"] for i in _items(repo).values() if i.get("owner") == owner)


def test_a_worker_queue_counts_main_assignments_before_the_worker_merges(tmp_path):
    """site-provisioner 01M4DNHWES: the coordinator assigns on main; a worker's tree sees those items only
    after it merges main. Counted from the tree, the worker read 0 — the coordinator's Stop kept saying
    `triage` and a second `triage --apply` handed out the floor again (6 against 3)."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    for n in range(6):
        _add(repo, env, "task", f"t{n}")
    assert run(["triage", "--apply"], env, repo).returncode == 0
    assert len(_owned(repo, "w1")) == 3
    q = {a["agent"]: a["queued"] for a in _queue(repo, env)["agents"]}
    assert q["w1"] == 3, q
    out = _stop(repo, env, session="sid-coord")
    assert out["action"] != "triage", out
    assert run(["triage", "--apply"], env, repo).returncode == 0
    assert len(_owned(repo, "w1")) == 3, (
        "a worker already at the floor on main is never topped up again"
    )


def test_a_worker_queue_takes_mains_copy_per_id_and_the_trees_own_items(tmp_path):
    """Main's file wins for an id it holds (D-516: the store of record for assignment), so an item
    reassigned away from w1 on main counts for w2 only — never for both; an item only w1's tree holds
    (its own, unmerged) counts once for w1."""
    env, repo, trees = _setup(tmp_path, workers=("w1", "w2"), present=("w1", "w2"))
    moved = _add(repo, env, "task", "moved")
    _assign(repo, env, moved, "w1")
    _commit_store(repo, env)
    _git(trees["w1"], env, "merge", "-q", "master")
    _assign(repo, env, moved, "w2")
    own = _add(trees["w1"], env, "task", "mine, unmerged")
    _assign(trees["w1"], env, own, "w1")
    q = {a["agent"]: a["queued"] for a in _queue(repo, env)["agents"]}
    assert q["w1"] == 1 and q["w2"] == 1, q


def test_a_worker_with_unmerged_assignments_is_told_to_merge(tmp_path):
    """The coordinator now stops nagging once a worker is at the floor on main, so the worker must hear
    it: a tree holding none of the items main assigns it gets `merge` naming the base branch and the
    first id, and once merged it gets `claim`."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    for n in range(3):
        _add(repo, env, "task", f"t{n}")
    assert run(["triage", "--apply"], env, repo).returncode == 0
    _commit_store(repo, env, "triage")
    first = _owned(repo, "w1")
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    out = _stop(trees["w1"], w1)
    assert out["action"] == "merge", out
    assert "master" in out["text"] and any(i in out["text"] for i in first), out["text"]
    _git(trees["w1"], env, "merge", "-q", "master")
    assert _stop(trees["w1"], w1, session="sid-w1-after")["action"] == "claim"


def test_under_autonomy_the_merge_rung_fingerprint_names_its_first_waiting_item(tmp_path):
    """Review A-S1: under `"autonomy": true` every rung but claim and triage collapsed to a constant
    `rung:<action>`, so a warned-through `merge` stayed silent while new assignments arrived. Like
    claim, merge keys on its first waiting item."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["autonomy"] = True
    cfg.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for n in range(3):
        _add(repo, env, "task", f"t{n}")
    assert run(["triage", "--apply"], env, repo).returncode == 0
    _commit_store(repo, env, "triage")
    out = _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})
    assert out["action"] == "merge", out
    fp = out["fp"]
    assert fp.startswith("rung:merge:W-") and fp[len("rung:merge:") :] in _owned(repo, "w1"), out


# --- print mode: a headless `claude -p` session takes no new work (iie 01M4PAJWV1) ---------------

_VSCODE_ARGV = (
    "/x/native-binary/claude",
    "--output-format",
    "stream-json",
    "--verbose",
    "--input-format",
    "stream-json",
    "--max-thinking-tokens",
    "31999",
    "--permission-prompt-tool",
    "stdio",
)


def _work():
    import importlib.util

    spec = importlib.util.spec_from_file_location("work_print_mode", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_chain(
    tmp_path: Path, *argvs: tuple[str, ...], exe: str | None = None
) -> tuple[Path, int]:
    """A fake proc root holding a parent chain: argvs[0] is the direct parent, each next one its
    parent. Returns (root, the direct parent's pid)."""
    root = tmp_path / "fakeproc"
    root.mkdir(parents=True, exist_ok=True)
    pids = list(range(500, 500 + len(argvs)))
    for i, (pid, argv) in enumerate(zip(pids, argvs, strict=True)):
        d = root / str(pid)
        d.mkdir()
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        ppid = pids[i + 1] if i + 1 < len(pids) else 1
        (d / "stat").write_text(f"{pid} (x y) S {ppid} 0 0\n", encoding="utf-8")
        if exe and i == len(argvs) - 1:
            os.symlink(exe, d / "exe")
    return root, pids[0]


def test_print_mode_reads_the_nearest_claude_ancestor(tmp_path, monkeypatch):
    w = _work()
    for env_name in ("FABRIK_HEADLESS", "CLAUDE_MESH_HEADLESS"):
        monkeypatch.delenv(env_name, raising=False)
    for flag in ("-p", "--print"):
        root, ppid = _fake_chain(
            tmp_path / flag.strip("-"), ("bash", "-c", "x"), ("/usr/bin/claude", flag, "do it")
        )
        monkeypatch.setenv("FABRIK_WORK_PROC", str(root))
        monkeypatch.setattr(w.os, "getppid", lambda p=ppid: p)
        assert w._print_mode() is True, flag
    # the resolved native binary (`…/claude/versions/2.1.296`) is found through exe
    root, ppid = _fake_chain(
        tmp_path / "native",
        ("sh", "-c", "x"),
        ("/home/u/.local/share/claude/versions/2.1.296", "-p", "q"),
        exe="/home/u/.local/share/claude/versions/2.1.296",
    )
    monkeypatch.setenv("FABRIK_WORK_PROC", str(root))
    monkeypatch.setattr(w.os, "getppid", lambda: ppid)
    assert w._print_mode() is True
    # a real process: work.py's parent is a `claude` whose argv holds -p
    out = subprocess.run(
        [
            "bash",
            "-c",
            f'exec -a claude bash -c "{sys.executable} -c \\"import importlib.util as u; '
            f"s=u.spec_from_file_location('w','{SCRIPT}'); m=u.module_from_spec(s); "
            f's.loader.exec_module(m); print(m._print_mode())\\"; true" -p',
        ],
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.stdout.strip() == "True", out


def test_print_mode_is_false_for_interactive_missing_or_unreadable(tmp_path, monkeypatch):
    w = _work()
    for env_name in ("FABRIK_HEADLESS", "CLAUDE_MESH_HEADLESS"):
        monkeypatch.delenv(env_name, raising=False)
    cases = {
        "vscode": [("bash", "-c", "x"), _VSCODE_ARGV],  # `--permission-prompt-tool` holds b"-p"
        "after-dashdash": [("bash",), ("claude", "--", "-p")],
        "no-claude": [("bash",), ("sshd",), ("init",)],
        "decoy": [("bash",), ("claude", "--print-config", "-pv")],
    }
    for name, chain in cases.items():
        root, ppid = _fake_chain(tmp_path / name, *chain)
        monkeypatch.setenv("FABRIK_WORK_PROC", str(root))
        monkeypatch.setattr(w.os, "getppid", lambda p=ppid: p)
        assert w._print_mode() is False, name
    # a parent with no readable cmdline, and an unreadable root
    root, ppid = _fake_chain(tmp_path / "nocmd", ("bash",), ("claude", "-p"))
    (root / str(ppid + 1) / "cmdline").unlink()
    monkeypatch.setenv("FABRIK_WORK_PROC", str(root))
    monkeypatch.setattr(w.os, "getppid", lambda: ppid)
    assert w._print_mode() is False
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "does-not-exist"))
    assert w._print_mode() is False


def test_print_mode_honours_the_headless_labels(tmp_path, monkeypatch):
    w = _work()
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "noproc"))
    for env_name in ("FABRIK_HEADLESS", "CLAUDE_MESH_HEADLESS"):
        monkeypatch.delenv("FABRIK_HEADLESS", raising=False)
        monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
        assert w._print_mode() is False
        monkeypatch.setenv(env_name, "1")
        assert w._print_mode() is True, env_name


def _autonomy(repo: Path) -> None:
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["autonomy"] = True
    cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_queue_stop_in_print_mode_keeps_only_own_claim_subjects(tmp_path):
    env, repo, _ = _setup(tmp_path)
    _autonomy(repo)
    queued = _add(repo, env, "task", "for coord")
    _assign(repo, env, queued, "coord")
    assert run(["commit-items"], env, repo).returncode == 0
    interactive = _stop(repo, env)
    assert interactive["action"], interactive  # the ladder orders work in a window
    headless = {**env, "FABRIK_HEADLESS": "1"}
    bare = _stop(repo, headless)
    assert bare["action"] is None and bare.get("reason") == "print-mode", bare
    assert "candidates" not in bare, bare  # a null action carrying candidates still blocks
    mine = _add(repo, env, "task", "held by this session")
    assert run(["claim", mine, "--session", SID], env, repo).returncode == 0
    assert run(["commit-items"], env, repo).returncode == 0
    held = _stop(repo, headless)
    acts = {c["action"] for c in held.get("candidates") or [held]}
    assert acts <= {"continue", "release"} and held["action"] in ("continue", "release"), held


def test_prompt_block_in_print_mode_keeps_only_own_claims(tmp_path, monkeypatch):
    env, repo, _ = _setup(tmp_path)
    free = _add(repo, env, "task", "free")
    mine = _add(repo, env, "task", "mine")
    assert run(["claim", mine, "--session", SID], env, repo).returncode == 0
    w = _work()
    monkeypatch.setenv("FABRIK_WORK_PROC", env["FABRIK_WORK_PROC"])
    monkeypatch.delenv("FABRIK_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    full = w.prompt_block(repo, SID)
    assert f"your claim — {mine}" in full and "ready" in full, full
    monkeypatch.setenv("FABRIK_HEADLESS", "1")
    lines = w.prompt_block(repo, SID).splitlines()
    assert lines and all("your claim" in ln for ln in lines), lines
    assert free not in "\n".join(lines)


def test_a_print_mode_claude_is_not_a_present_worker(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    proc = Path(env["FABRIK_WORK_PROC"])
    entry = next(d for d in proc.iterdir() if (d / "comm").read_text().strip() == "claude")
    (entry / "cmdline").write_bytes(b"claude\0-p\0copy this\0")
    for n in range(4):
        _add(repo, env, "task", f"t{n}")
    applied = run(["triage", "--apply"], env, repo)
    assert applied.returncode == 0, applied.stderr
    owners = {i.get("owner", "") for i in _items(repo).values()}
    assert "w1" not in owners, "a claude -p child in w1's tree is not a present worker"


def _proc_entry(root: Path, pid: int, argv: tuple[str, ...] | None, ppid: int) -> None:
    d = root / str(pid)
    d.mkdir(parents=True)
    if argv is not None:
        (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (d / "stat").write_text(f"{pid} (x) S {ppid} 0 0\n", encoding="utf-8")


def test_print_mode_walk_edges_from_review(tmp_path, monkeypatch):
    """Review round 1: pid 1 is inspected (a container's `claude -p` entrypoint), an unreadable
    intermediate is climbed past, and only claude's own cli.js counts as claude."""
    w = _work()
    for env_name in ("FABRIK_HEADLESS", "CLAUDE_MESH_HEADLESS"):
        monkeypatch.delenv(env_name, raising=False)
    cases = {
        "pid1-claude-p": ([(50, ("bash",), 1), (1, ("claude", "-p", "x"), 0)], 50, True),
        "unreadable-middle": ([(60, None, 61), (61, ("claude", "-p"), 1)], 60, True),
        "claude-cli-js": (
            [(70, ("node", "/n/lib/@anthropic-ai/claude-code/cli.js", "-p"), 1)],
            70,
            True,
        ),
        "worktree-cli-js": (
            [
                (90, ("node", "/p/.claude/worktrees/w1/node_modules/x/cli.js", "-p", "1"), 91),
                (91, _VSCODE_ARGV, 1),
            ],
            90,
            False,
        ),
        "foreign-cli-js": (
            [(80, ("node", "tools/cli.js", "-p", "8080"), 81), (81, _VSCODE_ARGV, 1)],
            80,
            False,
        ),
    }
    for name, (entries, ppid, want) in cases.items():
        root = tmp_path / name
        for pid, argv, parent in entries:
            _proc_entry(root, pid, argv, parent)
        monkeypatch.setenv("FABRIK_WORK_PROC", str(root))
        monkeypatch.setattr(w.os, "getppid", lambda p=ppid: p)
        assert w._print_mode() is want, name


def test_print_mode_stop_keeps_identity_and_errors():
    w = _work()
    out = w._print_mode_stop({"agent": "a", "role": "worker", "action": None, "error": "boom"})
    assert out["agent"] == "a" and out["role"] == "worker" and out["error"] == "boom", out
    assert out["action"] is None and "candidates" not in out, out


def test_queue_stop_under_a_real_claude_p_parent_is_null(tmp_path):
    env, repo, _ = _setup(tmp_path)
    _autonomy(repo)
    _assign(repo, env, _add(repo, env, "task", "for coord"), "coord")
    assert run(["commit-items"], env, repo).returncode == 0
    env = {k: v for k, v in env.items() if k != "FABRIK_WORK_PROC"}  # the real /proc
    cmd = f"{sys.executable} {SCRIPT} queue --stop --session {SID} --cwd {repo}; true"
    out = subprocess.run(
        ["bash", "-c", f'exec -a claude bash -c "{cmd}" -p'],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    got = json.loads(out.stdout.strip().splitlines()[0])
    assert got["action"] is None and got["reason"] == "print-mode", (got, out.stderr)


def test_prompt_block_in_print_mode_keeps_the_more_claims_line(tmp_path, monkeypatch):
    env, repo, _ = _setup(tmp_path)
    w = _work()
    for n in range(w.PROMPT_CLAIM_LINES + 2):
        item = _add(repo, env, "task", f"mine {n}")
        assert run(["claim", item, "--session", SID], env, repo).returncode == 0
    monkeypatch.setenv("FABRIK_WORK_PROC", env["FABRIK_WORK_PROC"])
    monkeypatch.setenv("FABRIK_HEADLESS", "1")
    lines = w.prompt_block(repo, SID).splitlines()
    assert any(ln.startswith("work: … and ") for ln in lines), lines
    assert sum(ln.startswith("work: your claim — ") for ln in lines) == w.PROMPT_CLAIM_LINES


# --- the coordinator role (plan 2026-10-15-plan-1-coordinator-role, D-871) ------------------


def _cfg(repo: Path, env: dict, **keys) -> None:
    """Merge ``keys`` into the store's config.json and commit it (coordinator_mode, queue_floor)."""
    path = repo / ".fabrik" / "work" / "config.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.update(keys)
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "cfg")


def _score(repo: Path, env: dict, item: str, impact: str, effort: str, *extra: str):
    return run(
        ["assign", item, "--impact", impact, "--effort", effort, "--why", "r", *extra], env, repo
    )


def test_score_derives_priority(tmp_path):
    env, repo, _ = _setup(tmp_path)
    for impact, effort, want in (("high", "low", 1), ("high", "high", 2), ("low", "low", 3)):
        item = _add(repo, env, "task", f"{impact}/{effort}")
        r = _score(repo, env, item, impact, effort)
        assert r.returncode == 0, r.stderr
        got = _items(repo)[item]
        assert (got["impact"], got["effort"], got["priority"]) == (impact, effort, want), got
        assert got["score_reason"] == "r", got


def test_time_sink_refused(tmp_path):
    env, repo, _ = _setup(tmp_path)
    one = _add(repo, env, "task", "one call")
    r = _score(repo, env, one, "low", "high")
    assert r.returncode != 0 and "drop --why" in r.stderr, r.stderr
    assert "impact" not in _items(repo)[one]
    two = _add(repo, env, "task", "two calls")
    assert run(["assign", two, "--impact", "low", "--why", "r"], env, repo).returncode == 0
    r = run(["assign", two, "--effort", "high", "--why", "r"], env, repo)
    assert r.returncode != 0 and "drop --why" in r.stderr, r.stderr
    assert "effort" not in _items(repo)[two]


def test_score_needs_reason(tmp_path):
    env, repo, _ = _setup(tmp_path)
    item = _add(repo, env, "task", "x")
    r = run(["assign", item, "--impact", "high"], env, repo)
    assert r.returncode != 0 and "--why" in r.stderr, r.stderr
    assert "impact" not in _items(repo)[item]


def test_assign_guard_knows_new_flags(tmp_path):
    env, repo, _ = _setup(tmp_path)
    a, b = _add(repo, env, "task", "a"), _add(repo, env, "task", "b")
    r = run(["assign", b, "--blocked-by", a], env, repo)
    assert r.returncode == 0, r.stderr
    assert _items(repo)[b]["blocked_by"] == [a]


def test_priority_override(tmp_path):
    env, repo, _ = _setup(tmp_path)
    item = _add(repo, env, "task", "incident")
    assert _score(repo, env, item, "high", "low").returncode == 0
    assert run(["assign", item, "--priority", "0"], env, repo).returncode == 0
    assert _items(repo)[item]["priority"] == 0
    r = run(["assign", item, "--priority", "3"], env, repo)
    assert r.returncode != 0 and "derived" in r.stderr, r.stderr
    assert _items(repo)[item]["priority"] == 0
    r = _score(repo, env, item, "high", "low")
    assert r.returncode == 0, r.stderr
    assert _items(repo)[item]["priority"] == 1
    assert "P0 override cleared" in r.stdout + r.stderr


def test_hold_and_release(tmp_path):
    env, repo, _ = _setup(tmp_path)
    x, y = _add(repo, env, "task", "x"), _add(repo, env, "task", "y")
    assert run(["assign", y, "--blocked-by", x], env, repo).returncode == 0
    listed = run(["ready", "--all"], env, repo).stdout
    assert x in listed and y not in listed, listed
    assert run(["assign", y, "--unblock", x], env, repo).returncode == 0
    assert y in run(["ready", "--all"], env, repo).stdout


def test_hold_refuses_bad_ids(tmp_path):
    env, repo, _ = _setup(tmp_path)
    x = _add(repo, env, "task", "x")
    assert run(["assign", x, "--blocked-by", "W-00000000"], env, repo).returncode != 0
    assert run(["assign", x, "--blocked-by", x], env, repo).returncode != 0
    assert not _items(repo)[x].get("blocked_by")


def test_triage_lists_unscored(tmp_path):
    env, repo, _ = _setup(tmp_path)
    scored = _add(repo, env, "task", "scored")
    assert _score(repo, env, scored, "high", "low").returncode == 0
    bare = _add(repo, env, "task", "bare")
    nxt = _add(repo, env, "task", "a next item")
    path = repo / ".fabrik" / "work" / f"{nxt}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["kind"] = "next"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    out = run(["triage"], env, repo).stdout
    line = next(ln for ln in out.splitlines() if ln.startswith("unscored "))
    assert line.startswith("unscored 1:") and bare in line, line
    assert scored not in line and nxt not in line, line


def _plan_ids(out: str) -> list[str]:
    return [ln.split()[2] for ln in out.splitlines() if ln.startswith("plan: ") and "W-" in ln]


def test_triage_scored_first(tmp_path):
    env, repo, _ = _setup(tmp_path, workers=("w1",), present=("w1",))
    older = _add(repo, env, "task", "unscored, older, P2")
    newer = _add(repo, env, "task", "scored low/low, P3")
    assert _score(repo, env, newer, "low", "low").returncode == 0
    assert _plan_ids(run(["triage"], env, repo).stdout)[0] == older  # no key: today's order
    _cfg(repo, env, coordinator_mode=True)
    assert _plan_ids(run(["triage"], env, repo).stdout)[0] == newer


def _blocked(repo: Path, item: str) -> None:
    path = repo / ".fabrik" / "work" / f"{item}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "blocked"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_one_major_in_flight(tmp_path):
    for state in ("open", "claimed", "blocked"):
        sub = tmp_path / state
        sub.mkdir()
        env, repo, _ = _setup(sub, workers=("w1", "w2"), present=("w1", "w2"))
        held = _add(repo, env, "task", "major in flight")
        assert _score(repo, env, held, "high", "high").returncode == 0
        _assign(repo, env, held, "w1")
        if state == "claimed":
            assert run(["claim", held, "--session", SID], env, repo).returncode == 0
        if state == "blocked":
            _blocked(repo, held)
        other = _add(repo, env, "task", "second major")
        assert _score(repo, env, other, "high", "high").returncode == 0
        r = run(["triage", "--apply"], env, repo)
        assert r.returncode == 0, r.stderr
        assert not _items(repo)[other].get("owner"), (state, r.stdout)
        assert held in r.stdout, (state, r.stdout)


def test_one_major_per_run(tmp_path):
    env, repo, _ = _setup(tmp_path, workers=("w1", "w2"), present=("w1", "w2"))
    majors = [_add(repo, env, "task", f"major {n}") for n in range(2)]
    for m in majors:
        assert _score(repo, env, m, "high", "high").returncode == 0
    assert run(["triage", "--apply"], env, repo).returncode == 0
    owned = [m for m in majors if _items(repo)[m].get("owner")]
    assert len(owned) == 1, _items(repo)


def _builder_fixture(tmp_path, *, mode: bool):
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    if mode:
        _cfg(repo, env, coordinator_mode=True)
    free = _add(repo, env, "task", "unowned, on main")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "item")
    _git(trees["w1"], env, "merge", "-q", "master")
    return env, repo, trees, free


def test_builder_sees_own_items(tmp_path, monkeypatch):
    env, repo, trees, free = _builder_fixture(tmp_path, mode=True)
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    assert free not in run(["next"], w1, trees["w1"]).stdout
    assert free not in run(["ready"], w1, trees["w1"]).stdout
    assert free in run(["ready", "--all"], w1, trees["w1"]).stdout
    assert free in run(["ready", "--all", "--mine"], w1, trees["w1"]).stdout
    assert free in run(["next"], env, repo).stdout  # the distributor still sees it
    w = _work()
    for key, value in w1.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("FABRIK_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    assert "ready —" not in w.prompt_block(trees["w1"], SID)


def test_unchanged_without_coordinator_mode(tmp_path):
    env, repo, trees, free = _builder_fixture(tmp_path, mode=False)
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    assert free in run(["next"], w1, trees["w1"]).stdout
    (tmp_path / "solo").mkdir()
    solo_env, solo, _ = _setup(tmp_path / "solo")
    item = _add(solo, solo_env, "task", "single window")
    assert item in run(["next"], solo_env, solo).stdout


def test_partial_score_keeps_todays_priority(tmp_path):
    """Review round 1: a half-scored item is unscored, so --priority behaves as today."""
    env, repo, _ = _setup(tmp_path)
    a, b = _add(repo, env, "task", "a"), _add(repo, env, "task", "b")
    r = run(["assign", a, "--impact", "high", "--why", "r", "--priority", "0"], env, repo)
    assert r.returncode == 0, r.stderr
    assert _items(repo)[a]["priority"] == 0
    r = run(["assign", b, "--effort", "low", "--why", "r", "--priority", "3"], env, repo)
    assert r.returncode == 0, r.stderr
    assert _items(repo)[b]["priority"] == 3


def test_first_score_keeps_an_existing_p0(tmp_path):
    env, repo, _ = _setup(tmp_path)
    item = _add(repo, env, "task", "incident first")
    assert run(["assign", item, "--priority", "0"], env, repo).returncode == 0
    assert _score(repo, env, item, "high", "low").returncode == 0
    assert _items(repo)[item]["priority"] == 0


def test_why_without_a_score_refused(tmp_path):
    env, repo, _ = _setup(tmp_path)
    item = _add(repo, env, "task", "x")
    r = run(["assign", item, "--owner", "w9", "--why", "r"], env, repo)
    assert r.returncode != 0 and "--why" in r.stderr, r.stderr


def test_hold_flag_edges_refused(tmp_path):
    env, repo, _ = _setup(tmp_path)
    x, y = _add(repo, env, "task", "x"), _add(repo, env, "task", "y")
    r = run(["assign", y, "--blocked-by", x, "--unblock", x], env, repo)
    assert r.returncode != 0 and "pick one" in r.stderr, r.stderr
    r = run(["assign", y, "--unblock", x], env, repo)  # x is not one of y's blockers
    assert r.returncode != 0 and x in r.stderr, r.stderr
    assert run(["assign", y, "--blocked-by", x], env, repo).returncode == 0
    r = run(["assign", x, "--blocked-by", y], env, repo)  # x <- y <- x is a cycle
    assert r.returncode != 0 and "cycle" in r.stderr, r.stderr
    assert not _items(repo)[x].get("blocked_by")


def test_a_claimed_unowned_major_holds_the_slot(tmp_path):
    env, repo, _ = _setup(tmp_path, workers=("w1",), present=("w1",))
    held = _add(repo, env, "task", "claimed, nobody assigned it")
    assert _score(repo, env, held, "high", "high").returncode == 0
    assert run(["claim", held, "--session", SID], env, repo).returncode == 0
    other = _add(repo, env, "task", "second major")
    assert _score(repo, env, other, "high", "high").returncode == 0
    r = run(["triage", "--apply"], env, repo)
    assert not _items(repo)[other].get("owner"), r.stdout
    assert held in r.stdout


def _major_lines(out: str, head: str) -> list[str]:
    return [ln[len(head) :].split()[0] for ln in out.splitlines() if ln.startswith(head)]


def test_a_held_major_is_not_in_flight(tmp_path):
    """A major held behind the in-flight major with `assign --blocked-by` (spec D3 job 3) prints as
    held, not in flight; once its blocker is dropped it is in flight."""
    env, repo, _ = _setup(tmp_path, workers=("w1", "w2"), present=("w1", "w2"))
    first = _add(repo, env, "task", "the major in flight")
    second = _add(repo, env, "task", "a major held behind it")
    for item, owner in ((first, "w1"), (second, "w2")):
        assert _score(repo, env, item, "high", "high").returncode == 0
        _assign(repo, env, item, owner)
    assert run(["assign", second, "--blocked-by", first], env, repo).returncode == 0
    out = run(["triage"], env, repo).stdout
    assert _major_lines(out, "major in flight: ") == [first], out
    assert _major_lines(out, "major held: ") == [second], out
    r = run(["drop", "--why", "blocker closed", first], env, repo)
    assert r.returncode == 0, r.stderr
    out = run(["triage"], env, repo).stdout
    assert _major_lines(out, "major in flight: ") == [second], out
    assert not _major_lines(out, "major held: "), out


def test_a_major_waiting_on_a_prerequisite_keeps_the_slot(tmp_path):
    """Only a hold behind another in-flight major frees the slot: a major waiting on its own
    prerequisite task is still in flight, so triage plans no second major. A second major held
    behind it makes the rule observable: "any blocker frees the slot" would hold both, and the
    fail-closed fallback would then print both as in flight (review pass 1, A-sonnet)."""
    env, repo, _ = _setup(tmp_path, workers=("w1", "w2"), present=("w1", "w2"))
    major = _add(repo, env, "task", "the major in flight")
    queued = _add(repo, env, "task", "a major held behind it")
    prereq = _add(repo, env, "task", "a small prerequisite")
    for item, owner in ((major, "w1"), (queued, "w2")):
        assert _score(repo, env, item, "high", "high").returncode == 0
        _assign(repo, env, item, owner)
    assert run(["assign", major, "--blocked-by", prereq], env, repo).returncode == 0
    assert run(["assign", queued, "--blocked-by", major], env, repo).returncode == 0
    other = _add(repo, env, "task", "second major")
    assert _score(repo, env, other, "high", "high").returncode == 0
    r = run(["triage", "--apply"], env, repo)
    assert r.returncode == 0, r.stderr
    assert _major_lines(r.stdout, "major in flight: ") == [major], r.stdout
    assert _major_lines(r.stdout, "major held: ") == [queued], r.stdout
    assert not _items(repo)[other].get("owner"), r.stdout


def test_an_unnamed_builder_still_sees_its_own_item(tmp_path):
    """Review round 1: the builder filter and `mine` must resolve the same caller."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    _cfg(repo, env, coordinator_mode=True)
    mine = _add(repo, env, "task", "owned by w1")
    _assign(repo, env, mine, "w1")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "item")
    _git(trees["w1"], env, "merge", "-q", "master")
    nameless = {k: v for k, v in env.items() if k != "CLAUDE_AGENT"}
    assert mine in run(["next"], nameless, trees["w1"]).stdout
    assert mine in run(["ready", "--mine"], nameless, trees["w1"]).stdout


def test_the_feedback_owner_is_not_a_builder(tmp_path):
    env, repo, trees = _setup(tmp_path, workers=("w1", "kz"), present=("w1", "kz"))
    _cfg(repo, env, coordinator_mode=True, feedback_owner="kz")
    free = _add(repo, env, "task", "unowned")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "item")
    _git(trees["kz"], env, "merge", "-q", "master")
    assert free in run(["next"], {**env, "CLAUDE_AGENT": "kz"}, trees["kz"]).stdout


def test_a_malformed_hold_does_not_break_assign(tmp_path):
    """Review round 2: a hand-edited non-list `blocked_by` must not crash an unrelated assign."""
    env, repo, _ = _setup(tmp_path)
    item = _add(repo, env, "task", "hand edited")
    path = repo / ".fabrik" / "work" / f"{item}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blocked_by"] = 5
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    r = run(["assign", item, "--owner", "w1"], env, repo)
    assert r.returncode == 0, r.stderr


def _held_behind_the_major(tmp_path):
    """The in-flight major (owned) and a second major held behind it (the spec D3 job 3 hold)."""
    env, repo, _ = _setup(tmp_path)
    flying = _add(repo, env, "task", "the major in flight")
    held = _add(repo, env, "task", "a major held behind it")
    for item in (flying, held):
        assert _score(repo, env, item, "high", "high").returncode == 0
    _assign(repo, env, flying, "w1")
    assert run(["assign", held, "--blocked-by", flying], env, repo).returncode == 0
    return env, repo, flying, held


def test_a_rescore_to_non_major_clears_the_major_hold(tmp_path):
    """W-0fe931b7: the hold exists only because the item is a major, so a re-score that makes it a
    quick win drops it and says how to re-add it; before, nine P1s sat unclaimable for 11 days."""
    env, repo, flying, held = _held_behind_the_major(tmp_path)
    r = _score(repo, env, held, "high", "low")
    assert r.returncode == 0, r.stderr
    got = _items(repo)[held]
    assert (got["priority"], got["blocked_by"]) == (1, []), got
    assert f"one-major hold cleared: {held} no longer waits on major {flying}" in r.stderr
    assert f"work.py assign {held} --blocked-by {flying}" in r.stderr, r.stderr
    assert held in run(["ready"], env, repo).stdout


def test_a_scored_medium_clears_its_major_hold(tmp_path):
    """The charter's second hold class: an unscored high-effort MEDIUM (tag only) held behind the
    in-flight major leaves the class when it is scored."""
    env, repo, flying, _ = _held_behind_the_major(tmp_path)
    medium = _add(repo, env, "task", "a high-effort medium")
    r = run(["assign", medium, "--tag", "medium", "--blocked-by", flying], env, repo)
    assert r.returncode == 0, r.stderr
    r = _score(repo, env, medium, "low", "low")
    assert r.returncode == 0, r.stderr
    assert _items(repo)[medium]["blocked_by"] == [], r.stderr
    assert f"one-major hold cleared: {medium}" in r.stderr, r.stderr


def test_a_rescore_to_non_major_keeps_other_holds(tmp_path):
    """Only a hold behind the IN-FLIGHT major is the one-major hold (triage's own predicate): a
    non-major prerequisite, a major the call names with --blocked-by, and an unowned major stay;
    an id the call removes with --unblock is the caller's and is not reported as cleared."""
    env, repo, flying, held = _held_behind_the_major(tmp_path)
    prereq = _add(repo, env, "task", "a small prerequisite")
    unowned = _add(repo, env, "task", "a major nobody owns")
    other = _add(repo, env, "task", "another major")
    for item in (unowned, other):
        assert _score(repo, env, item, "high", "high").returncode == 0
    _assign(repo, env, other, "w2")
    for dep in (prereq, unowned):
        assert run(["assign", held, "--blocked-by", dep], env, repo).returncode == 0
    r = _score(repo, env, held, "low", "low", "--blocked-by", other, "--unblock", flying)
    assert r.returncode == 0, r.stderr
    assert sorted(_items(repo)[held]["blocked_by"]) == sorted([prereq, unowned, other])
    assert "hold cleared" not in r.stderr, r.stderr


def test_a_rescore_that_was_or_stays_major_keeps_its_hold(tmp_path):
    """A major re-scored as a major keeps its hold; so does a quick win held behind the major by
    hand and re-scored, because it never was in the one-major hold class."""
    env, repo, flying, held = _held_behind_the_major(tmp_path)
    r = _score(repo, env, held, "high", "high")
    assert r.returncode == 0 and "hold cleared" not in r.stderr, r.stderr
    assert _items(repo)[held]["blocked_by"] == [flying]
    quick = _add(repo, env, "task", "a quick win held by hand")
    assert _score(repo, env, quick, "high", "low").returncode == 0
    assert run(["assign", quick, "--blocked-by", flying], env, repo).returncode == 0
    r = _score(repo, env, quick, "low", "low")
    assert r.returncode == 0 and "hold cleared" not in r.stderr, r.stderr
    assert _items(repo)[quick]["blocked_by"] == [flying]


def test_a_rescore_keeps_an_unreadable_hold_and_says_so(tmp_path):
    """Fail closed and loud: a hand-edited scalar hold naming no readable item survives the
    re-score unchanged, the call does not abort, and stderr names the kept hold."""
    env, repo, _, held = _held_behind_the_major(tmp_path)
    path = repo / ".fabrik" / "work" / f"{held}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blocked_by"] = 5
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    r = _score(repo, env, held, "high", "low")
    assert r.returncode == 0, r.stderr
    assert _items(repo)[held]["blocked_by"] == 5
    assert f"one-major hold kept: {held} still waits on 5" in r.stderr, r.stderr


def test_a_half_score_or_a_scored_medium_keeps_its_hold(tmp_path):
    """Review pass 1 (B1, B2): the clear needs the item SCORED after the call, and IN the class
    before it — an unscored `medium` item given only --impact is still unscored, and a quick win
    that also carries the `medium` tag was never in the class."""
    env, repo, flying, _ = _held_behind_the_major(tmp_path)
    medium = _add(repo, env, "task", "a high-effort medium")
    r = run(["assign", medium, "--tag", "medium", "--blocked-by", flying], env, repo)
    assert r.returncode == 0, r.stderr
    r = run(["assign", medium, "--impact", "low", "--why", "r"], env, repo)
    assert r.returncode == 0 and "hold cleared" not in r.stderr, r.stderr
    assert _items(repo)[medium]["blocked_by"] == [flying]
    quick = _add(repo, env, "task", "a quick win that also carries the medium tag")
    assert _score(repo, env, quick, "high", "low").returncode == 0
    r = run(["assign", quick, "--tag", "medium", "--blocked-by", flying], env, repo)
    assert r.returncode == 0, r.stderr
    r = _score(repo, env, quick, "low", "low")
    assert r.returncode == 0 and "hold cleared" not in r.stderr, r.stderr
    assert _items(repo)[quick]["blocked_by"] == [flying]


def test_the_clear_reads_the_blocker_as_triage_does(tmp_path):
    """Review pass 1 (B3): a live claim puts an unowned major in flight, so the hold behind it
    clears; a closed marker takes an owned major out of flight, so the hold behind it stays."""
    env, repo, flying, held = _held_behind_the_major(tmp_path)
    claimed = _add(repo, env, "task", "a major nobody owns, claimed")
    assert _score(repo, env, claimed, "high", "high").returncode == 0
    assert run(["claim", claimed, "--session", SID], env, repo).returncode == 0
    assert run(["assign", held, "--blocked-by", claimed], env, repo).returncode == 0
    closed = repo / ".git" / "fabrik-work" / "closed"
    closed.mkdir(parents=True, exist_ok=True)
    (closed / f"{flying}.json").write_text(json.dumps({"at": time.time()}) + "\n", encoding="utf-8")
    r = _score(repo, env, held, "high", "low")
    assert r.returncode == 0, r.stderr
    assert _items(repo)[held]["blocked_by"] == [flying], r.stderr
    assert f"no longer waits on major {claimed}" in r.stderr, r.stderr
    assert f"waits on major {flying}" not in r.stderr, r.stderr


def test_a_builder_tree_reads_the_blocker_from_the_main_checkout(tmp_path):
    """Review pass 1 (C4): a builder's branch holds an older copy of the in-flight major, made
    before the coordinator assigned it on the main checkout; triage reads main, and so does the
    clear, so a re-score in the builder tree drops the hold."""
    env, repo, _ = _setup(tmp_path)
    flying = _add(repo, env, "task", "the major in flight")
    held = _add(repo, env, "task", "a major held behind it")
    for item in (flying, held):
        assert _score(repo, env, item, "high", "high").returncode == 0
    assert run(["assign", held, "--blocked-by", flying], env, repo).returncode == 0
    _commit_store(repo, env)
    tree = repo / ".claude" / "worktrees" / "w1"
    _git(repo, env, "worktree", "add", "-q", "-b", "w-w1", str(tree))
    _assign(repo, env, flying, "w9")  # on main only: the builder's copy stays unowned
    assert not _items(tree)[flying].get("owner")
    r = _score(tree, env, held, "high", "low")
    assert r.returncode == 0, r.stderr
    assert _items(tree)[held]["blocked_by"] == [], r.stderr
    assert f"no longer waits on major {flying}" in r.stderr, r.stderr


def test_a_corrupt_main_copy_is_never_read_past(tmp_path):
    """Review pass 2: this tree's copy is read only for a blocker the main checkout LACKS; one
    main holds but cannot parse keeps the hold, said aloud, never judged from a branch copy."""
    env, repo, flying, held = _held_behind_the_major(tmp_path)
    _commit_store(repo, env)
    tree = repo / ".claude" / "worktrees" / "w1"
    _git(repo, env, "worktree", "add", "-q", "-b", "w-w1", str(tree))
    (repo / ".fabrik" / "work" / f"{flying}.json").write_text("{", encoding="utf-8")
    r = _score(tree, env, held, "high", "low")
    assert r.returncode == 0, r.stderr
    assert _items(tree)[held]["blocked_by"] == [flying], r.stderr
    assert f"one-major hold kept: {held} still waits on {flying}" in r.stderr, r.stderr


def test_a_stale_builder_tree_agrees_with_its_doorbell(tmp_path):
    """Review round 2: the key on main but not yet in the builder's branch — the filter is off,
    and the doorbell must say so too (one predicate for both)."""
    env, repo, trees, free = _builder_fixture(tmp_path, mode=False)
    _cfg(repo, env, coordinator_mode=True)  # main only; w1 has not merged it
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    assert free in run(["next"], w1, trees["w1"]).stdout
    out = _stop(trees["w1"], w1)
    assert out["action"] == "doorbell" and "work.py next" in out["text"], out


def test_doorbell_points_at_ready_all_mine(tmp_path):
    env, repo, trees, _ = _builder_fixture(tmp_path, mode=True)
    out = _stop(trees["w1"], {**env, "CLAUDE_AGENT": "w1"})
    assert out["action"] == "doorbell", out
    assert "ready --all --mine" in out["text"] and "unowned" in out["text"], out
    assert "work.py next" not in out["text"], out


def test_a_builder_named_unlike_its_tree_is_still_a_builder(tmp_path):
    """Finish review pass 1 (A-opus 1): the builder is decided by its TREE, as the Stop hook's
    worker check is — a window in `w1` whose CLAUDE_AGENT reads otherwise gets the filtered view,
    so `next` and the doorbell never disagree."""
    env, repo, trees, free = _builder_fixture(tmp_path, mode=True)
    alice = {**env, "CLAUDE_AGENT": "alice"}
    assert free not in run(["next"], alice, trees["w1"]).stdout
    assert free not in run(["ready"], alice, trees["w1"]).stdout
    out = _stop(trees["w1"], alice)
    assert out["action"] == "doorbell" and "ready --all --mine" in out["text"], out
    assert out["agent"] == "w1", out  # the ladder names the same builder `next` filters for


def test_unchanged_without_coordinator_mode_in_ready_and_the_prompt(tmp_path, monkeypatch):
    """Finish review pass 1 (A-opus 3): plan row A13 for `ready` and the prompt count, not only
    `next`."""
    env, repo, trees, free = _builder_fixture(tmp_path, mode=False)
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    assert free in run(["ready"], w1, trees["w1"]).stdout
    w = _work()
    for key, value in w1.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("FABRIK_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    assert "ready —" in w.prompt_block(trees["w1"], SID)


def test_hold_refuses_a_transitive_cycle(tmp_path):
    """Finish review pass 1 (A-opus 2): z <- y <- x, then x <- z closes a three-node cycle."""
    env, repo, _ = _setup(tmp_path)
    x, y, z = (_add(repo, env, "task", n) for n in ("x", "y", "z"))
    assert run(["assign", y, "--blocked-by", x], env, repo).returncode == 0
    assert run(["assign", z, "--blocked-by", y], env, repo).returncode == 0
    r = run(["assign", x, "--blocked-by", z], env, repo)
    assert r.returncode != 0 and "cycle" in r.stderr, r.stderr
    assert not _items(repo)[x].get("blocked_by")


def test_a_malformed_hold_does_not_break_the_queue(tmp_path):
    """Finish review pass 1 (A-sonnet 1): one hand-edited non-list `blocked_by` must not crash
    `ready`, `next`, `triage` or `claim` for every agent in the repo."""
    env, repo, _ = _setup(tmp_path)
    item = _add(repo, env, "task", "hand edited")
    path = repo / ".fabrik" / "work" / f"{item}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["blocked_by"] = 5
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for argv in (["ready"], ["ready", "--all"], ["next"], ["triage"]):
        r = run(argv, env, repo)
        assert r.returncode == 0 and "Traceback" not in r.stderr, (argv, r.stderr)
    assert item not in run(["ready", "--all"], env, repo).stdout  # the hold fails CLOSED
    r = run(["claim", item, "--session", SID], env, repo)
    assert r.returncode != 0 and "Traceback" not in r.stderr, r.stderr
    path.write_text(json.dumps({**data, "blocked_by": "W-00000000"}, indent=2) + "\n", "utf-8")
    assert item not in run(["ready", "--all"], env, repo).stdout  # a scalar id still holds


# ── paused workers (W-da4bc702): a shared marker the floor, triage and every Stop rung honour ─────


def _paused_dir(repo: Path) -> Path:
    return repo / ".git" / "fabrik-work" / "paused"


def _operator(env: dict) -> dict:
    """The operator's shell or the dashboard: no agent name AND no Claude session id."""
    return {k: v for k, v in env.items() if k not in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID")}


def test_pause_and_resume_mark_a_worker(tmp_path):
    """pause writes the shared marker and resume removes it; only the pauser, the distributor or the
    operator lifts a pause; an unnamed Claude session, another named agent and a bad name are
    refused; an unknown name is warned about, never refused."""
    env, repo, trees = _setup(tmp_path, workers=("w1", "w2"), present=("w1",))
    r = run(["pause", "w1", "--why", "operator hold"], env, repo)
    assert r.returncode == 0, r.stderr
    rec = json.loads((_paused_dir(repo) / "w1.json").read_text(encoding="utf-8"))
    assert rec["by"] == "coord" and rec["why"] == "operator hold" and rec["at"] > 0
    listing = run(["pause"], env, repo)
    assert listing.returncode == 0 and "w1" in listing.stdout and "coord" in listing.stdout
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    self_resume = run(["resume", "w1"], w1, trees["w1"])
    assert self_resume.returncode == 1 and "coord" in self_resume.stderr  # names the pauser
    assert (_paused_dir(repo) / "w1.json").exists()
    session_only = {**_operator(env), "CLAUDE_CODE_SESSION_ID": "s-unnamed"}
    assert run(["pause", "w2"], session_only, repo).returncode == 1  # an unnamed Claude session
    assert run(["pause", "w2"], w1, trees["w1"]).returncode == 1  # another named agent
    assert run(["pause", "Bad Name"], env, repo).returncode == 1
    op = run(["pause", "w2", "--by", "dashboard"], _operator(env), repo)
    assert op.returncode == 0, op.stderr
    assert json.loads((_paused_dir(repo) / "w2.json").read_text())["by"] == "dashboard"
    ghost = run(["pause", "ghost"], env, repo)
    assert ghost.returncode == 0 and "ghost" in ghost.stderr  # warned: matches no known agent
    assert run(["resume", "w1"], env, repo).returncode == 0  # the distributor lifts it
    assert not (_paused_dir(repo) / "w1.json").exists()
    assert run(["resume", "w2"], _operator(env), repo).returncode == 0  # the operator lifts it
    assert run(["pause", "w1"], w1, trees["w1"]).returncode == 0  # an agent may pause itself
    assert run(["resume", "w1"], w1, trees["w1"]).returncode == 0  # and lift its own pause
    # review round 1: a paused agent cannot re-pause over another's pause to make it its own
    assert run(["pause", "w1"], env, repo).returncode == 0
    overwrite = run(["pause", "w1"], w1, trees["w1"])
    assert overwrite.returncode == 1 and "already paused by coord" in overwrite.stderr
    assert run(["resume", "w1"], w1, trees["w1"]).returncode == 1
    assert run(["resume", "w1"], env, repo).returncode == 0
    # the check reads the marker's actor, never its label: --by w1 grants w1 nothing, and an agent
    # NAMED "operator" cannot lift a pause the operator set
    assert run(["pause", "w1", "--by", "w1"], _operator(env), repo).returncode == 0
    lifted = run(["resume", "w1"], w1, trees["w1"])
    assert lifted.returncode == 1 and "lifting it is the distributor's (coord) or the operator's" in lifted.stderr
    assert run(["resume", "w1"], {**env, "CLAUDE_AGENT": "operator"}, repo).returncode == 1
    assert run(["resume", "w1"], _operator(env), repo).returncode == 0
    # an entry that is no regular file pauses by presence and is never written or removed
    (_paused_dir(repo) / "w2.json").unlink(missing_ok=True)
    (_paused_dir(repo) / "w2.json").mkdir()
    odd = run(["resume", "w2"], env, repo)
    assert odd.returncode == 1 and "remove it by hand" in odd.stderr and "Traceback" not in odd.stderr
    assert run(["pause", "w2"], env, repo).returncode == 1


def test_a_paused_worker_is_never_pushed_to_start(tmp_path):
    """A paused worker's Stop action is null on the classic path and under autonomy, its claim kept;
    a window named unlike its tree is caught by either name."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    item = _add(trees["w1"], env, "task", "in my tree")
    _assign(trees["w1"], env, item, "w1")
    w1 = {**env, "CLAUDE_AGENT": "w1"}
    assert _stop(trees["w1"], w1)["action"] == "claim"
    assert run(["pause", "w1"], env, repo).returncode == 0
    out = _stop(trees["w1"], w1)
    assert out["action"] is None and out["role"] == "paused", out
    alice = {**env, "CLAUDE_AGENT": "alice"}  # a window named unlike its tree: caught by the tree
    assert _stop(trees["w1"], alice)["role"] == "paused"
    assert run(["resume", "w1"], env, repo).returncode == 0
    assert _stop(trees["w1"], alice)["role"] != "paused"
    assert run(["pause", "alice"], env, repo).returncode == 0  # ...and by its own name
    assert _stop(trees["w1"], alice)["role"] == "paused"
    assert run(["resume", "alice"], env, repo).returncode == 0
    held = _add(trees["w1"], env, "task", "held one")
    _assign(trees["w1"], env, held, "w1")
    assert run(["claim", held, "--session", SID], w1, trees["w1"]).returncode == 0
    cfg = repo / ".fabrik" / "work" / "config.json"
    cfg.write_text(json.dumps({**json.loads(cfg.read_text()), "autonomy": True}), encoding="utf-8")
    assert _stop(trees["w1"], w1)["action"] == "continue"  # autonomy pushes the held claim on
    assert run(["pause", "w1"], env, repo).returncode == 0
    out = _stop(trees["w1"], w1)
    assert out["action"] is None and not out.get("candidates"), out
    assert (repo / ".git" / "fabrik-work" / "claims" / f"{held}.json").exists()  # nothing lost


def test_the_floor_and_triage_skip_a_paused_worker(tmp_path, monkeypatch):
    """The coordinator's floor rung and triage skip a paused worker; a worker's doorbell skips a
    paused coordinator."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    _add(repo, env, "task", "free")
    assert _stop(repo, env, session="sid-coord")["action"] == "triage"
    assert run(["pause", "w1"], env, repo).returncode == 0
    # no triage owed: the only worker is paused (the store's uncommitted item file may still be named)
    assert _stop(repo, env, session="sid-coord")["action"] in (None, "commit-items")
    plan = run(["triage"], env, repo)
    assert plan.returncode == 0 and "plan: w1" not in plan.stdout and "paused: w1" in plan.stdout
    applied = run(["triage", "--apply"], env, repo)
    assert applied.returncode == 0
    assert all(i.get("owner", "") != "w1" for i in _items(repo).values())
    assert run(["resume", "w1"], env, repo).returncode == 0
    _add(repo, env, "backlog", "strategic")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "backlog")
    w = _work()
    monkeypatch.setenv("FABRIK_WORK_PROC", env["FABRIK_WORK_PROC"])
    monkeypatch.setenv("CLAUDE_AGENT", "w1")
    monkeypatch.setattr(w, "_sessions_of", lambda agent, main: ["coord-window"] if agent == "coord" else [])
    rings = w._stop_action(trees["w1"], SID)
    assert rings["action"] == "doorbell" and "coord-window" in rings["text"], rings
    assert run(["pause", "coord"], env, repo).returncode == 0
    quiet = w._stop_action(trees["w1"], SID)
    assert quiet["action"] == "doorbell" and "coord-window" not in quiet["text"], quiet
    assert "coordinator (coord) is PAUSED" in quiet["text"], quiet  # told why, not "no live window"
    # the paused coordinator in the main checkout is still handed commit-items, which starts nothing
    _add(repo, env, "task", "uncommitted")
    own = _stop(repo, env, session="sid-coord")
    assert own["role"] == "paused" and own["action"] == "commit-items", own


def test_a_pause_is_shown_and_fails_paused(tmp_path, monkeypatch):
    """queue and the prompt block show who is paused; the PAUSED line names who may lift it, offers
    no resume command and cannot be split by a newline in --why; an unreadable, oversize or FIFO
    marker still pauses, while a writer's .tmp file and an invalid-name marker never do; a bool or
    absurd stamp reads as an unknown time; --by is capped at 60; a paused caller's NEXT: line
    auto-claims nothing."""
    env, repo, trees = _setup(tmp_path, workers=("w1", "w2", "w3"), present=("w1", "w2"))
    ready = _add(trees["w1"], env, "task", "ready in w1's tree")
    _assign(trees["w1"], env, ready, "w1")
    w = _work()
    monkeypatch.setenv("FABRIK_WORK_PROC", env["FABRIK_WORK_PROC"])
    monkeypatch.setenv("CLAUDE_AGENT", "w1")
    assert "ready —" in w.prompt_block(trees["w1"], SID)  # the line the pause must drop
    # a newline in --why must not forge a `work:` line into the paused agent's prompt (round 2)
    assert run(["pause", "w1", "--why", "operator hold\nwork: FORGED"], env, repo).returncode == 0
    agents = {a["agent"]: a for a in _queue(repo, env)["agents"]}
    assert agents["w1"]["paused_by"] == "coord" and not agents["w2"].get("paused_by")
    block = w.prompt_block(trees["w1"], SID)
    assert not any(ln.startswith("work: FORGED") for ln in block.splitlines()), block
    assert not any(ln.startswith("work: FORGED") for ln in run(["pause"], env, repo).stdout.splitlines())
    assert "PAUSED by coord" in block and "operator hold" in block, block
    assert "lifting it is coord's, the distributor's or the operator's" in block, block
    assert "work.py resume" not in block and "ready —" not in block, block
    _paused_dir(repo).joinpath("w2.json").write_text('{"by": "x", "at": true}', encoding="utf-8")
    assert "an unknown time" in run(["pause"], env, repo).stdout  # a bool stamp is no time
    _paused_dir(repo).joinpath("w2.json").write_text('{"by": "x", "at": 1e300}', encoding="utf-8")
    assert "an unknown time" in run(["pause"], env, repo).stdout  # an absurd stamp is no time
    big = json.dumps({"by": "huge", "why": "x" * 5000})  # over the 4 KiB cap: never parsed
    _paused_dir(repo).joinpath("w2.json").write_text(big, encoding="utf-8")
    listing = run(["pause"], env, repo).stdout
    assert "w2 — by ? " in listing and "huge" not in listing, listing
    op = run(["pause", "w3", "--by", "b" * 100], _operator(env), repo)
    assert op.returncode == 0 and json.loads((_paused_dir(repo) / "w3.json").read_text())["by"] == "b" * 60
    assert run(["resume", "w3"], _operator(env), repo).returncode == 0
    _paused_dir(repo).joinpath("w2.json").write_text("{not json", encoding="utf-8")
    _paused_dir(repo).joinpath("w3.json.abc123.tmp").write_text("{}", encoding="utf-8")
    _paused_dir(repo).joinpath("Up.json").write_text("{}", encoding="utf-8")  # no agent name: no pause
    assert _stop(trees["w2"], {**env, "CLAUDE_AGENT": "w2"})["role"] == "paused"
    agents = {a["agent"]: a for a in _queue(repo, env)["agents"]}
    assert agents["w2"]["paused_by"] and not agents["w3"].get("paused_by")
    assert _queue(repo, env)["paused"] == ["w1", "w2"]  # the .tmp file is no pause under any name
    listing = run(["pause"], env, repo).stdout
    assert "an unknown time" in listing and "w3" not in listing, listing  # w2's marker has no stamp
    os.mkfifo(_paused_dir(repo) / "w3.json")  # a FIFO is never read: it would block every Stop hook
    fifo = run(["queue", "--stop", "--session", SID, "--cwd", str(trees["w3"])],
               {**env, "CLAUDE_AGENT": "w3"}, trees["w3"])
    assert fifo.returncode == 0 and json.loads(fifo.stdout)["role"] == "paused", fifo.stderr
    item = _add(trees["w1"], env, "task", "named in NEXT")
    w.on_harvest(trees["w1"], session=SID, next_text=f"NEXT: {item} — named in NEXT")
    assert not (repo / ".git" / "fabrik-work" / "claims" / f"{item}.json").exists()


# ── verdict: the operator's accept / reject / comment (W-e1f1a1bd) ─────────────────────────────


def _decision(repo: Path, env: dict) -> str:
    """An awaiting-operator decision (only the Stop harvest mints one; `add` refuses the kind)."""
    item = _add(repo, env, "task", "a gate")
    path = repo / ".fabrik" / "work" / f"{item}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(kind="decision", status="awaiting-operator")
    path.write_text(json.dumps(data), encoding="utf-8")
    return item


def _verdict(repo: Path, env: dict, item: str, action: str, text: str = "") -> subprocess.CompletedProcess[str]:
    opts = [f"--text={text}"] if text else []
    return run(["verdict", *opts, "--by=dashboard", "--", item, action], env, repo)


def test_verdict_is_the_operators_only(tmp_path):
    """An agent name or an unnamed Claude session is refused — stricter than pause's rule, which
    admits a named agent; nothing is written."""
    env, repo, _trees = _setup(tmp_path)
    item = _add(repo, env)
    named = _verdict(repo, env, item, "comment", "hi")
    assert named.returncode == 1 and "operator" in named.stderr
    session = _verdict(repo, {**_operator(env), "CLAUDE_CODE_SESSION_ID": "s1"}, item, "comment", "hi")
    assert session.returncode == 1
    assert "comments" not in _items(repo)[item]
    assert _verdict(repo, _operator(env), item, "comment", "hi").returncode == 0


def test_verdict_accept(tmp_path):
    """Accept answers an awaiting decision; on any other open item it adds operator-accepted and
    removes waits-operator-review (the hold), keeping the owner; an awaiting non-decision is refused."""
    env, repo, _trees = _setup(tmp_path)
    op = _operator(env)
    gate = _decision(repo, env)
    r = _verdict(repo, op, gate, "accept", "go ahead")
    assert r.returncode == 0, r.stderr
    closed = _items(repo)[gate]
    assert closed["status"] == "done" and closed["note"] == "accepted: go ahead"
    held = _add(repo, env)
    _assign(repo, env, held, "w1", "--tag", "waits-operator-review", "--tag", "dashboard")
    r = _verdict(repo, op, held, "accept")
    assert r.returncode == 0, r.stderr
    it = _items(repo)[held]
    assert it["status"] == "open" and it["owner"] == "w1"
    assert it["tags"] == ["dashboard", "operator-accepted"]
    odd = _decision(repo, env)
    path = repo / ".fabrik" / "work" / f"{odd}.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "kind": "task"}), encoding="utf-8")
    refused = _verdict(repo, op, odd, "accept")
    assert refused.returncode == 1 and "decision" in refused.stderr


def test_verdict_reject(tmp_path):
    """Reject drops an owned open item with the operator's words and answers an awaiting decision as
    rejected; reject needs text; another session's live claim refuses it."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    op = _operator(env)
    owned = _add(repo, env)
    _assign(repo, env, owned, "w1")
    assert _verdict(repo, op, owned, "reject").returncode == 1  # no text
    r = _verdict(repo, op, owned, "reject", "not needed")
    assert r.returncode == 0, r.stderr
    it = _items(repo)[owned]
    assert it["status"] == "dropped" and it["note"] == "rejected by the operator: not needed"
    gate = _decision(repo, env)
    assert _verdict(repo, op, gate, "reject", "no").returncode == 0
    assert _items(repo)[gate]["note"] == "rejected: no"
    claimed = _add(repo, env)
    _assign(repo, env, claimed, "w1")
    _commit_store(repo, env)
    _git(trees["w1"], env, "merge", "-q", "master")
    c = run(["claim", claimed, "--session", SID], {**env, "CLAUDE_AGENT": "w1"}, trees["w1"])
    assert c.returncode == 0, c.stderr
    fenced = _verdict(repo, op, claimed, "reject", "stop")
    assert fenced.returncode == 1 and "claim" in fenced.stderr
    assert _items(repo)[claimed]["status"] == "open"


def test_verdict_comment_logs_every_call(tmp_path):
    """Every call appends {at, by, via, action, text} to `comments`; the text is one printable line
    capped at 200; comment needs text; a resolved item is refused."""
    env, repo, _trees = _setup(tmp_path)
    op = _operator(env)
    item = _add(repo, env)
    assert _verdict(repo, op, item, "comment").returncode == 1
    assert _verdict(repo, op, item, "comment", "first\tline\x07 " + "x" * 300).returncode == 0
    assert _verdict(repo, op, item, "accept").returncode == 0
    log = _items(repo)[item]["comments"]
    assert [c["action"] for c in log] == ["comment", "accept"]
    first = log[0]
    assert first["by"] == "operator" and first["via"] == "dashboard" and first["at"] > 0
    assert first["text"].startswith("first line ") and len(first["text"]) == 200
    assert "\x07" not in first["text"]
    assert log[1]["text"] == ""
    assert run(["verdict", "--", item, "comment"], op, repo).returncode == 1
    done = _add(repo, env)
    assert _verdict(repo, op, done, "reject", "gone").returncode == 0
    assert _verdict(repo, op, done, "comment", "late").returncode == 1


def test_verdict_refusals_each_stand_alone(tmp_path):
    """Review round 1: each refusal is proven on its own — a resolved item with no closed marker, an
    item closed in another tree whose file here still reads open, another session's claim on ACCEPT,
    and a `comments` that is not a list (refused, never overwritten); an awaiting item that is no
    decision still takes a comment; a hand-edited string tag stays one tag."""
    env, repo, trees = _setup(tmp_path, workers=("w1",), present=("w1",))
    op = _operator(env)
    items = repo / ".fabrik" / "work"

    def edit(item: str, **fields) -> None:
        path = items / f"{item}.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), **fields}), encoding="utf-8")

    resolved = _add(repo, env)
    edit(resolved, status="done")
    r = _verdict(repo, op, resolved, "comment", "x")
    assert r.returncode == 1 and "already done" in r.stderr
    elsewhere = _add(repo, env)
    claimed = _add(repo, env)
    _assign(repo, env, claimed, "w1")
    _commit_store(repo, env)
    _git(trees["w1"], env, "merge", "-q", "master")
    assert _verdict(trees["w1"], op, elsewhere, "reject", "gone").returncode == 0  # closed in w1's tree
    r = _verdict(repo, op, elsewhere, "comment", "x")  # main's file still reads open
    assert r.returncode == 1 and "another working tree" in r.stderr
    assert run(["claim", claimed, "--session", SID], {**env, "CLAUDE_AGENT": "w1"}, trees["w1"]).returncode == 0
    r = _verdict(repo, op, claimed, "accept")
    assert r.returncode == 1 and "claim" in r.stderr
    assert _verdict(repo, op, claimed, "comment", "fine to note").returncode == 0  # comment never fences
    odd = _add(repo, env)
    edit(odd, status="awaiting-operator")
    assert _verdict(repo, op, odd, "comment", "seen").returncode == 0
    bad = _add(repo, env)
    edit(bad, comments={"x": 1})
    r = _verdict(repo, op, bad, "comment", "y")
    assert r.returncode == 1 and "not a list" in r.stderr
    assert json.loads((items / f"{bad}.json").read_text())["comments"] == {"x": 1}
    stringy = _add(repo, env)
    edit(stringy, tags="abc")
    assert _verdict(repo, op, stringy, "accept").returncode == 0
    assert _items(repo)[stringy]["tags"] == ["abc", "operator-accepted"]
