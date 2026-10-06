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
