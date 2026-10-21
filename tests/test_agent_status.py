"""scripts/agent_status.py — the coordinator's NOW / DONE / NEXT view of every hub worker (W-cfff98dd e, D-880).

Every test builds a throwaway git repo with a work store whose distributor is `coordinator`, worker
worktrees, a tmp run-record store (COMMAND_RUN_DIR) and a fake /proc (FABRIK_WORK_PROC), then runs the
real script — the readers it loads (work.py, command_run.py, mail.py) are the hub's real modules, so a
helper whose signature drifts shows up as wrong rows here, not only as an exception.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STATUS = REPO / "scripts" / "agent_status.py"
WORK = REPO / "scripts" / "work.py"
SETTINGS = REPO / ".claude" / "settings.json"


def _env(tmp: Path, agent: str | None = "coordinator") -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp / sub).mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp / "home"),
        "TMPDIR": str(tmp / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "FABRIK_MAIL_ROOT": str(tmp / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp / "tmp" / "state" / "command-runs"),
        "AGENT_IDENTITY_FILE": str(tmp / "tmp" / "identity.jsonl"),
        "FABRIK_WORK_PROC": str(tmp / "proc"),
    }
    if agent is not None:
        env["CLAUDE_AGENT"] = agent
    return env


def _git(cwd: Path, env: dict, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


def _work(repo: Path, env: dict, *args: str) -> str:
    r = subprocess.run(
        [sys.executable, str(WORK), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _status(repo: Path, env: dict, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STATUS), "--repo", str(repo), *args],
        cwd=repo,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _setup(tmp: Path, *, present: tuple[str, ...] = ()) -> tuple[dict, Path, dict[str, Path]]:
    env = _env(tmp)
    repo = tmp / "repo"
    _git(tmp, env, "init", "-q", "-b", "master", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    repo = repo.resolve()
    _work(repo, env, "init", "--distributor", "coordinator")
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "store")
    # the hub's shape: its builders named in the session registry (W-16d0ef14 — the roster is the repo's own)
    (repo / ".fabrik" / "session-agents.json").write_text(
        json.dumps(
            {"s0": "coordinator", "s1": "infra", "s2": "fleet", "s3": "intel", "s4": "kaizen"}
        ),
        encoding="utf-8",
    )
    trees = {}
    for name in ("infra", "fleet"):
        wt = repo / ".claude" / "worktrees" / name
        _git(repo, env, "worktree", "add", "-q", "-b", f"worktree-{name}", str(wt))
        trees[name] = wt
    proc = tmp / "proc"
    proc.mkdir()
    for n, name in enumerate(present, start=100):
        d = proc / str(n)
        d.mkdir()
        (d / "comm").write_text("claude\n", encoding="utf-8")
        os.symlink(trees[name], d / "cwd")
    return env, repo, trees


def _add(repo: Path, env: dict, title: str, owner: str = "", *extra: str) -> str:
    item = Path(
        _work(repo, env, "add", "--kind", "task", "--title", title).strip().splitlines()[-1]
    ).stem
    if owner:
        _work(repo, env, "assign", item, "--owner", owner, *extra)
    return item


def _record(env: dict, sid: str, **fields) -> None:
    d = Path(env["COMMAND_RUN_DIR"])
    d.mkdir(parents=True, exist_ok=True)
    rec = {
        "session_id": sid,
        "updated_ts": time.time(),
        "phase": 2,
        "phases": 5,
        "phase_title": "t",
        **fields,
    }
    (d / f"{sid}.json").write_text(json.dumps(rec), encoding="utf-8")


def _rows(repo: Path, env: dict) -> dict[str, dict]:
    r = _status(repo, env, "--json")
    assert r.returncode == 0, r.stderr
    return {row["role"]: row for row in json.loads(r.stdout)["agents"]}


def test_now_shows_the_roles_running_record_and_claim(tmp_path: Path) -> None:
    """NOW is the role's newest RUNNING record from any repo (another repo is named), its claim and
    whether a window is up; a done record, another agent's record and the distributor are not rows."""
    env, repo, trees = _setup(tmp_path, present=("infra",))
    _record(
        env,
        "s1",
        agent="infra",
        state="running",
        command="fabrik-task",
        surface="the reader",
        repo_root=str(trees["infra"]),
    )
    _record(
        env,
        "s2",
        agent="infra",
        state="done",
        command="fabrik-review",
        surface="old",
        repo_root=str(trees["infra"]),
    )
    _record(
        env,
        "s3",
        agent="fleet",
        state="running",
        command="fabrik-deploy",
        surface="vps1",
        repo_root="/opt/some-project",
    )
    _record(
        env,
        "s4",
        agent="sp1",
        state="running",
        command="fabrik-spec",
        surface="x",
        repo_root="/opt/other",
    )
    item = _add(repo, env, "build the reader", "infra")
    claim_env = {**env, "CLAUDE_AGENT": "infra", "CLAUDE_CODE_SESSION_ID": "s1"}
    _work(repo, claim_env, "claim", item)  # claims sit in the shared folder every tree reads
    rows = _rows(repo, env)
    assert "coordinator" not in rows, sorted(rows)
    infra, fleet = rows["infra"], rows["fleet"]
    assert infra["live"] is True and fleet["live"] is False
    assert infra["now"]["command"] == "fabrik-task" and infra["now"]["surface"] == "the reader"
    assert infra["claim"]["id"] == item and infra["claim"]["title"] == "build the reader"
    assert (
        fleet["now"]["command"] == "fabrik-deploy" and fleet["now"]["repo"] == "/opt/some-project"
    )
    assert rows["intel"]["now"] is None


def test_now_flags_a_stale_record_and_skips_a_corrupt_one(tmp_path: Path) -> None:
    """A running record older than the Stop hook's 12 h bound is flagged stale (its session is
    likely gone), and a record whose updated_ts is not a finite number ("abc", "inf", NaN, an int too
    large for a float) is skipped, never a crash."""
    env, repo, trees = _setup(tmp_path)
    _record(
        env,
        "old",
        agent="infra",
        state="running",
        command="fabrik-deploy",
        surface="x",
        repo_root=str(trees["infra"]),
        updated_ts=time.time() - 13 * 3600,
    )
    _record(
        env,
        "bad",
        agent="fleet",
        state="running",
        command="fabrik-spec",
        surface="y",
        repo_root=str(trees["fleet"]),
        updated_ts="abc",
    )
    _record(
        env,
        "inf",
        agent="fleet",
        state="running",
        command="fabrik-spec",
        surface="z",
        repo_root=str(trees["fleet"]),
        updated_ts="inf",
    )
    _record(
        env,
        "nan",
        agent="fleet",
        state="running",
        command="fabrik-spec",
        surface="n",
        repo_root=str(trees["fleet"]),
        updated_ts=float("nan"),
    )
    _record(
        env,
        "big",
        agent="fleet",
        state="running",
        command="fabrik-spec",
        surface="b",
        repo_root=str(trees["fleet"]),
        updated_ts=10**400,
    )  # float() of it raises OverflowError
    rows = _rows(repo, env)
    assert rows["infra"]["now"]["stale"] is True
    assert rows["fleet"]["now"] is None
    text = _status(repo, env)
    assert text.returncode == 0 and "STALE" in text.stdout, text.stdout + text.stderr


def test_done_lists_the_roles_merges_of_both_eras(tmp_path: Path) -> None:
    """DONE reads the base branch's merge subjects of BOTH merge-owner eras and skips a builder's
    back-merge of master; the 24 h count is the distinct items those subjects name."""
    env, repo, _ = _setup(tmp_path)
    for subject in (
        "merge(infra): worktree-infra — request 01AAA, item W-11111111",
        "merge(infra): origin/master into worktree-infra before the request",
        "merge(coordinator): worktree-infra — request 01BBB, item W-22222222",
        "merge(coordinator): worktree-fleet — request 01CCC, item none",
    ):
        _git(repo, env, "commit", "-q", "--allow-empty", "-m", subject)
    rows = _rows(repo, env)
    infra = rows["infra"]["done"]
    assert [m["item"] for m in infra["merges"]] == ["W-22222222", "W-11111111"], infra
    assert infra["items_24h"] == 2
    assert [m["item"] for m in rows["fleet"]["done"]["merges"]] == [""]
    assert rows["intel"]["done"]["merges"] == []


def test_done_finds_a_quiet_roles_merge_behind_many_commits(tmp_path: Path) -> None:
    """A role that merged long ago still shows that merge: the log is filtered to merge subjects
    BEFORE the commit limit applies, so 450 later non-merge commits cannot push it out of view."""
    env, repo, _ = _setup(tmp_path)
    _git(
        repo,
        env,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "merge(coordinator): worktree-fleet — request 01OLD, item W-33333333",
    )
    head = _git(repo, env, "rev-parse", "HEAD").strip()
    stream = []
    for n in range(450):
        msg = f"chore: filler {n}\n"
        stream.append(
            f"commit refs/heads/master\ncommitter t <t@example.invalid> {1790000000 + n} +0000\n"
            f"data {len(msg)}\n{msg}" + (f"from {head}\n" if n == 0 else "") + "\n"
        )
    subprocess.run(
        ["git", "fast-import", "--quiet", "--force"],
        cwd=repo,
        env=env,
        input="".join(stream),
        capture_output=True,
        text=True,
        check=True,
    )
    _git(repo, env, "reset", "-q", "--hard", "master")
    fleet = _rows(repo, env)["fleet"]["done"]
    assert [m["item"] for m in fleet["merges"]] == ["W-33333333"], fleet


def test_next_is_the_roles_queue(tmp_path: Path) -> None:
    """NEXT is the set `work.py queue` counts: owned, not parked, not claimed — never another
    owner's or an unowned item — top 3 by priority, with the queue's size and the parked count."""
    env, repo, _ = _setup(tmp_path)
    low = _add(repo, env, "low", "infra", "--priority", "3")
    high = _add(repo, env, "high", "infra", "--priority", "1")
    mid = _add(repo, env, "mid", "infra", "--priority", "2")
    extra = _add(repo, env, "extra", "infra", "--priority", "3")
    parked = _add(repo, env, "parked", "infra", "--tag", "waits-2099-01-01")
    _add(repo, env, "fleet's", "fleet")
    _add(repo, env, "nobody's")
    nxt = _rows(repo, env)["infra"]["next"]
    assert [i["id"] for i in nxt["top"]] == [high, mid, low] or [i["id"] for i in nxt["top"]] == [
        high,
        mid,
        extra,
    ]
    assert nxt["queued"] == 4 and nxt["parked"] == 1
    assert parked not in [i["id"] for i in nxt["top"]]


def test_session_start_prints_for_the_distributor_only(tmp_path: Path) -> None:
    """--session-start prints the table for the distributor (session id from the hook's stdin), stays
    quiet for a builder, says so when identity is unknown, and stays under the hook cap."""
    env, repo, trees = _setup(tmp_path)
    for n in range(40):
        _add(repo, env, "a long title " * 12 + str(n), "infra")
    payload = json.dumps({"session_id": "sid-coord", "source": "compact"})
    r = _status(repo, env, "--session-start", stdin=payload)
    assert r.returncode == 0, r.stderr
    assert "D-880" in r.stdout and "infra" in r.stdout and "fleet" in r.stdout
    assert len(r.stdout) < 9000, len(r.stdout)
    builder = _status(repo, {**env, "CLAUDE_AGENT": "infra"}, "--session-start", stdin=payload)
    assert builder.returncode == 0 and builder.stdout.strip() == ""
    unknown = _status(repo, _env(tmp_path, agent=None), "--session-start", stdin=payload)
    assert unknown.returncode == 0 and "whoami_agent.py --as" in unknown.stdout
    elsewhere = tmp_path / "plain"
    elsewhere.mkdir()
    quiet = _status(elsewhere, env, "--session-start", stdin=payload)
    assert quiet.returncode == 0 and quiet.stdout.strip() == ""


def test_the_session_start_entry_is_guarded(tmp_path: Path) -> None:
    """The SessionStart entry is its own hook (its own 10,000-character budget), guarded by `test -f`,
    so a repo the governance sync reaches without the script runs nothing and exits 0."""
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
    cmds = [
        h["command"] for e in hooks for h in e.get("hooks", []) if "agent_status.py" in h["command"]
    ]
    assert len(cmds) == 1, cmds
    cmd = cmds[0]
    assert cmd.startswith(
        'test -f "${CLAUDE_PROJECT_DIR}/scripts/agent_status.py" &&'
    ) and cmd.endswith("|| true")
    absent = tmp_path / "project"
    absent.mkdir()
    r = subprocess.run(
        ["sh", "-c", cmd],
        env={"PATH": os.environ["PATH"], "CLAUDE_PROJECT_DIR": str(absent)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


# ── the box view: every repo under the /opt seam (W-7159f8e2) ─────────────────────────────────────


def _box_repo(
    opt: Path, env: dict, name: str, *, store: bool = True, worktrees: tuple[str, ...] = ()
) -> Path:
    repo = opt / name
    _git(opt, env, "init", "-q", "-b", "master", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    repo = repo.resolve()
    if store:
        _work(repo, env, "init", "--distributor", "coordinator")
        _git(repo, env, "add", ".fabrik")
        _git(repo, env, "commit", "-q", "-m", "store")
    for wt in worktrees:
        _git(
            repo,
            env,
            "worktree",
            "add",
            "-q",
            "-b",
            f"worktree-{wt}",
            str(repo / ".claude" / "worktrees" / wt),
        )
    return repo


def _window(proc: Path, n: int, cwd: Path, agent: str = "", argv: str = "claude") -> None:
    d = proc / str(n)
    d.mkdir(parents=True)
    (d / "comm").write_text("claude\n", encoding="utf-8")
    (d / "cmdline").write_bytes(argv.replace(" ", "\0").encode() + b"\0")
    (d / "environ").write_bytes(
        (f"CLAUDE_AGENT={agent}\0" if agent else "").encode() + b"PATH=/bin\0"
    )
    os.symlink(cwd, d / "cwd")


def _box(opt: Path, env: dict) -> dict[str, dict]:
    r = subprocess.run(
        [sys.executable, str(STATUS), "--json", "--all", "--opt", str(opt)],
        cwd=opt,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return {repo["name"]: repo for repo in json.loads(r.stdout)["repos"]}


def _agents(repo: dict) -> dict[str, dict]:
    return {a["name"]: a for a in repo["agents"]}


def test_box_roster_from_windows_records_and_claims(tmp_path: Path) -> None:
    """Agents per repo: the live windows (named by CLAUDE_AGENT, else the worktree, else the main
    checkout's newest run record), the agents with a run record of THAT repo in the last 7 days, and
    claim holders; older ones are only counted dormant; a repo with no store but an agent is listed."""
    env = _env(tmp_path)
    opt = tmp_path / "opt"
    opt.mkdir()
    shop = _box_repo(opt, env, "shop", worktrees=("wef1", "wef3"))
    lib = _box_repo(opt, env, "lib", store=False)
    _box_repo(opt, env, "quiet")
    proc = tmp_path / "proc"
    _window(proc, 101, shop / ".claude" / "worktrees" / "wef1")
    _window(proc, 102, shop)
    _window(proc, 103, shop / ".claude" / "worktrees" / "wef3", agent="wef3")
    _window(proc, 104, shop, argv="claude -p hello")  # a headless child is no window
    week = time.time() - 8 * 86400
    _record(env, "m1", agent="wef2", state="done", command="fabrik-review", repo_root=str(shop))
    _record(
        env,
        "o1",
        agent="wef9",
        state="done",
        command="fabrik-task",
        repo_root=str(shop),
        updated_ts=week,
    )
    _record(env, "l1", agent="lib-dev1", state="done", command="fabrik-task", repo_root=str(lib))
    item = _add(shop, env, "fix the cart", "wef4")
    _work(shop, {**env, "CLAUDE_AGENT": "wef4", "CLAUDE_CODE_SESSION_ID": "c1"}, "claim", item)
    repos = _box(opt, env)
    assert "quiet" in repos and repos["quiet"]["agents"] == []
    shop_agents = _agents(repos["shop"])
    assert sorted(shop_agents) == ["wef1", "wef2", "wef3", "wef4"], sorted(shop_agents)
    assert (
        shop_agents["wef1"]["window"]
        and shop_agents["wef3"]["window"]
        and shop_agents["wef2"]["window"]
    )
    assert shop_agents["wef2"]["named_from"] == "record"
    assert (
        shop_agents["wef4"]["window"] is False
        and shop_agents["wef4"]["claim"]["title"] == "fix the cart"
    )
    assert repos["shop"]["dormant"] == 1  # wef9: last seen 8 days ago
    assert list(_agents(repos["lib"])) == ["lib-dev1"] and repos["lib"]["store"] is False


def test_box_state_comes_from_windows_and_records_not_bindings(tmp_path: Path) -> None:
    """working = a fresh running record of this repo; idle = a window with none; away = neither. An
    identity binding whose pid is ALIVE (this test's own) still makes nobody live — bindings outlive
    windows (measured: 0 of 29 newest bindings live while 8 windows were up)."""
    env = _env(tmp_path)
    opt = tmp_path / "opt"
    opt.mkdir()
    shop = _box_repo(opt, env, "shop", worktrees=("wef1", "wef3"))
    proc = tmp_path / "proc"
    _window(proc, 101, shop / ".claude" / "worktrees" / "wef1")
    _record(
        env,
        "r3",
        agent="wef3",
        state="running",
        command="fabrik-task",
        surface="the cart",
        repo_root=str(shop / ".claude" / "worktrees" / "wef3"),
    )
    _record(env, "r5", agent="wef5", state="done", command="fabrik-task", repo_root=str(shop))
    start = Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(")", 1)[1].split()[19]
    Path(env["AGENT_IDENTITY_FILE"]).write_text(
        json.dumps(
            {
                "session_id": "b5",
                "name": "wef5",
                "pid": os.getpid(),
                "pid_start": int(start),
                "toplevel": str(shop / ".git"),
                "at": int(time.time()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agents = _agents(_box(opt, env)["shop"])
    assert agents["wef3"]["state"] == "working" and agents["wef3"]["now"]["surface"] == "the cart"
    assert agents["wef1"]["state"] == "idle"
    assert agents["wef5"]["state"] == "away" and agents["wef5"]["window"] is False


def test_box_edges_are_named_honestly(tmp_path: Path) -> None:
    """The review's surviving mutants, each pinned: a headless `-p` child is no window; CLAUDE_AGENT
    beats the worktree name; an unreadable environ loses only the name; a harness tree is no agent; a
    stale running record reads stale; a future or non-finite stamp is no record; a main window with only
    an old record stays unnamed; only the main checkout's current agent is its merge owner; a binding-only
    name counts dormant; a symlinked alias is not a second repo."""
    env = _env(tmp_path)
    opt = tmp_path / "opt"
    opt.mkdir()
    shop = _box_repo(opt, env, "shop", worktrees=("wef1", "wef6", "wef7", "agent-0123456789abcdef"))
    old = _box_repo(opt, env, "old")
    os.symlink(shop, opt / "shop-alias")
    proc = tmp_path / "proc"
    wt = shop / ".claude" / "worktrees"
    _window(proc, 101, wt / "wef7", argv="claude -p hello")  # headless: wef7 has no window
    _window(proc, 102, wt / "wef1", agent="lead")  # named by its env, not its tree
    _window(proc, 103, wt / "wef6")
    (proc / "103" / "environ").chmod(0)  # unreadable: the window stays, named by its tree
    _window(proc, 104, wt / "agent-0123456789abcdef")  # a harness tree: nobody's window
    _window(proc, 105, old)  # a main window whose only record is 9 days old
    _record(
        env,
        "st",
        agent="wef8",
        state="running",
        command="fabrik-task",
        repo_root=str(shop),
        updated_ts=time.time() - 13 * 3600,
    )
    _record(
        env,
        "fu",
        agent="wef9",
        state="running",
        command="fabrik-task",
        repo_root=str(shop),
        updated_ts=time.time() + 10 * 86400,
    )
    _record(env, "nf", agent="wef5", state="running", command="fabrik-task", repo_root=str(shop))
    nf = Path(env["COMMAND_RUN_DIR"]) / "nf.json"
    nf.write_text(
        nf.read_text(encoding="utf-8").replace(
            str(json.loads(nf.read_text())["updated_ts"]), "NaN"
        ),
        encoding="utf-8",
    )
    _record(
        env,
        "o9",
        agent="ancient",
        state="done",
        command="fabrik-task",
        repo_root=str(old),
        updated_ts=time.time() - 9 * 86400,
    )
    _record(env, "mo", agent="boss", state="done", command="fabrik-review", repo_root=str(shop))
    _record(
        env,
        "mx",
        agent="former",
        state="done",
        command="fabrik-review",
        repo_root=str(shop),
        updated_ts=time.time() - 3600,
    )
    Path(env["AGENT_IDENTITY_FILE"]).write_text(
        json.dumps(
            {
                "session_id": "b1",
                "name": "ghost",
                "pid": 1,
                "pid_start": 1,
                "toplevel": str(shop / ".git"),
                "at": int(time.time()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    repos = _box(opt, env)
    assert "shop-alias" not in repos
    shop_agents = _agents(repos["shop"])
    assert "wef7" not in shop_agents and "agent-0123456789abcdef" not in shop_agents
    assert shop_agents["lead"]["named_from"] == "env" and "wef1" not in shop_agents
    assert shop_agents["wef6"]["window"] and shop_agents["wef6"]["named_from"] == "worktree"
    assert shop_agents["wef8"]["state"] == "stale"
    assert "wef9" not in shop_agents and "wef5" not in shop_agents
    assert shop_agents["boss"]["merge_owner"] and not shop_agents["former"]["merge_owner"]
    assert repos["shop"]["dormant"] == 1  # ghost: a binding with no record in reach
    old_agents = _agents(repos["old"])
    assert list(old_agents) == ["(unnamed)"] and repos["old"]["dormant"] == 1


def test_box_reports_each_agents_pause(tmp_path: Path) -> None:
    """Each agent carries its pause — by its own name or the tree its window sits in, with the
    marker's NAME (the one a resume must lift) — `can_pause` only for an agent name in a repo whose
    store has config.json, and `pause_honoured` from that repo's own work.py (W-7159f8e2 part 3)."""
    env = _env(tmp_path)
    opt = tmp_path / "opt"
    opt.mkdir()
    shop = _box_repo(opt, env, "shop", worktrees=("wef1", "wef2"))
    bare = opt / "bare"
    (bare / ".fabrik" / "work").mkdir(parents=True)  # a work dir with no config.json
    _git(bare, env, "init", "-q")
    proc = tmp_path / "proc"
    _window(
        proc, 101, shop / ".claude" / "worktrees" / "wef1", agent="lead"
    )  # named unlike its tree
    _window(proc, 102, shop / ".claude" / "worktrees" / "wef2")
    _window(proc, 103, shop)  # a main window with no record: "(unnamed)"
    _window(proc, 104, bare / ".fabrik")
    _record(env, "b1", agent="bob", state="done", command="fabrik-task", repo_root=str(bare))
    marker = shop / ".git" / "fabrik-work" / "paused"
    marker.mkdir(parents=True)
    (marker / "wef1.json").write_text(
        json.dumps({"by": "operator", "actor": "", "at": time.time()})
    )
    (shop / "scripts").mkdir()
    (shop / "scripts" / "work.py").write_text(
        "def cmd_pause(repo, args):\n    pass\n", encoding="utf-8"
    )
    repos = _box(opt, env)
    shop_agents = _agents(repos["shop"])
    assert shop_agents["lead"]["paused"]["name"] == "wef1"  # caught by its window's tree
    assert shop_agents["lead"]["paused"]["by"] == "operator"
    assert shop_agents["wef2"]["paused"] is None
    assert shop_agents["lead"]["can_pause"] and shop_agents["wef2"]["can_pause"]
    assert shop_agents["(unnamed)"]["can_pause"] is False
    assert shop_agents["lead"]["pause_honoured"] is True
    bob = _agents(repos["bare"])["bob"]
    assert bob["can_pause"] is False and bob["pause_honoured"] is False  # no config.json, no verb


def test_box_pause_edges(tmp_path: Path) -> None:
    """The review's findings, each pinned: a pause under the agent's own name; work.py pauses per
    WINDOW, so the row carries every marker stopping one of the agent's windows (Resume lifts them all)
    and reads `partial` while another window — a worktree or the main checkout — still runs; a marker
    with no time shows no age; a FIFO work.py never hangs the box view; the verb in a comment is not
    the verb."""
    env = _env(tmp_path)
    opt = tmp_path / "opt"
    opt.mkdir()
    shop = _box_repo(opt, env, "shop", worktrees=("wef1", "wef2", "wef3", "wef4", "wef5", "wef6"))
    fifo = _box_repo(opt, env, "fifo")
    cmt = _box_repo(opt, env, "cmt")
    proc = tmp_path / "proc"
    wt = shop / ".claude" / "worktrees"
    _window(
        proc, 101, wt / "wef1", agent="lead"
    )  # lead's two windows: wef1 (paused) and wef2 (not)
    _window(proc, 102, wt / "wef2", agent="lead")
    _window(proc, 103, wt / "wef3", agent="cara")  # paused by her own name
    _window(proc, 104, wt / "wef4", agent="duo")  # duo's two windows: both trees paused
    _window(proc, 105, wt / "wef5", agent="duo")
    _window(proc, 106, wt / "wef6", agent="mo")  # mo: a paused tree and a main-checkout window
    _window(proc, 107, shop, agent="mo")
    _record(env, "f", agent="fay", state="done", command="fabrik-task", repo_root=str(fifo))
    _record(env, "c", agent="cid", state="done", command="fabrik-task", repo_root=str(cmt))
    marker = shop / ".git" / "fabrik-work" / "paused"
    marker.mkdir(parents=True)
    for tree in ("wef1", "wef4", "wef5", "wef6"):
        (marker / f"{tree}.json").write_text(json.dumps({"by": "operator", "at": time.time()}))
    (marker / "cara.json").write_text(json.dumps({"by": "operator"}))  # no time
    (fifo / "scripts").mkdir()
    os.mkfifo(fifo / "scripts" / "work.py")
    (cmt / "scripts").mkdir()
    (cmt / "scripts" / "work.py").write_text(
        "# TODO: def cmd_pause(repo, args)\n", encoding="utf-8"
    )
    repos = _box(opt, env)  # a FIFO read would block here until the test's timeout
    shop_agents = _agents(repos["shop"])
    assert shop_agents["cara"]["paused"]["names"] == ["cara"]
    assert (
        shop_agents["cara"]["paused"]["at"] is None
        and shop_agents["cara"]["paused"]["partial"] is False
    )
    lead = shop_agents["lead"]["paused"]
    assert lead["names"] == ["wef1"] and lead["partial"] is True  # its wef2 window still runs
    duo = shop_agents["duo"]["paused"]
    assert duo["names"] == ["wef4", "wef5"] and duo["partial"] is False  # Resume must lift both
    assert shop_agents["mo"]["paused"]["partial"] is True  # its main-checkout window still runs
    assert _agents(repos["fifo"])["fay"]["pause_honoured"] is False
    assert _agents(repos["cmt"])["cid"]["pause_honoured"] is False


def test_box_now_is_keyed_by_repo(tmp_path: Path) -> None:
    """The same agent name in two repos never crosses: each repo's NOW is its own running record."""
    env = _env(tmp_path)
    opt = tmp_path / "opt"
    opt.mkdir()
    crm = _box_repo(opt, env, "crm")
    trade = _box_repo(opt, env, "trade")
    _record(
        env,
        "a",
        agent="agent-1",
        state="running",
        command="fabrik-spec",
        surface="crm side",
        repo_root=str(crm),
    )
    _record(
        env,
        "b",
        agent="agent-1",
        state="running",
        command="fabrik-task",
        surface="trade side",
        repo_root=str(trade),
        updated_ts=time.time() - 60,
    )
    repos = _box(opt, env)
    assert _agents(repos["crm"])["agent-1"]["now"]["surface"] == "crm side"
    assert _agents(repos["trade"])["agent-1"]["now"]["surface"] == "trade side"


# ── W-16d0ef14: the roster is the repo's own builders ───────────────────────────────────────────────────────────
def _bind(env: dict, repo: Path, *names: str) -> None:
    with open(env["AGENT_IDENTITY_FILE"], "a", encoding="utf-8") as fh:
        for n, name in enumerate(names):
            row = {"session_id": f"sid-{name}-{n}", "name": name, "toplevel": str(repo / ".git")}
            fh.write(json.dumps(row) + "\n")


def test_roster_without_a_registry_is_bound_builders_with_worktrees(tmp_path: Path) -> None:
    """youtube, fabrik-lib and trade-intelligence read the hub's five beats before W-16d0ef14. With no registry, a
    name bound to this repo that has a worktree is a builder; a task worktree nobody is bound to is not
    (web-ecommerce-factory's t03-… trees), and neither is a bound name with no worktree."""
    env, repo, _ = _setup(tmp_path)
    (repo / ".fabrik" / "session-agents.json").unlink()
    task = repo / ".claude" / "worktrees" / "t03-task"
    _git(repo, env, "worktree", "add", "-q", "-b", "t03-task", str(task))
    _bind(env, repo, "infra", "fleet", "ghost", "coordinator")
    assert sorted(_rows(repo, env)) == ["fleet", "infra"]


def test_roster_is_the_registry_minus_the_coordinators(tmp_path: Path) -> None:
    """Distinct string names of the registry, minus the distributor (here `lead`, not coordinator-shaped), any
    `*-coordinator` name and a value that is not a string (a TypeError before the guard)."""
    env, repo, _ = _setup(tmp_path)
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["distributor"] = "lead"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    registry = {
        "a": "lead",
        "b": "x-coordinator",
        "c": "infra",
        "d": "infra",
        "e": None,
        "f": 3,
        "g": "fleet",
    }
    (repo / ".fabrik" / "session-agents.json").write_text(json.dumps(registry), encoding="utf-8")
    assert sorted(_rows(repo, env)) == ["fleet", "infra"]


@pytest.mark.parametrize("body", ["{not json", '["infra"]', '{"s": "coordinator"}', "{}"])
def test_a_builderless_or_damaged_registry_falls_back(tmp_path: Path, body: str) -> None:
    env, repo, _ = _setup(tmp_path)
    (repo / ".fabrik" / "session-agents.json").write_text(body, encoding="utf-8")
    _bind(env, repo, "fleet")
    assert sorted(_rows(repo, env)) == ["fleet"]


def test_a_binding_to_another_repo_of_the_same_name_is_not_a_builder(tmp_path: Path) -> None:
    """The identity store is matched by PATH: a clone elsewhere with this repo's folder name binds nothing here."""
    env, repo, _ = _setup(tmp_path)
    (repo / ".fabrik" / "session-agents.json").unlink()
    elsewhere = tmp_path / "elsewhere" / repo.name
    _bind(env, elsewhere, "infra")
    _bind(env, repo, "fleet")
    assert sorted(_rows(repo, env)) == ["fleet"]


def test_the_bare_coordinator_name_is_never_a_row(tmp_path: Path) -> None:
    """With a distributor that is not `coordinator`, the bare name is dropped by the name rule alone."""
    env, repo, _ = _setup(tmp_path)
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["distributor"] = "lead"
    cfg.write_text(json.dumps(data), encoding="utf-8")
    registry = {"a": "coordinator", "b": "infra"}
    (repo / ".fabrik" / "session-agents.json").write_text(json.dumps(registry), encoding="utf-8")
    assert sorted(_rows(repo, env)) == ["infra"]


def test_the_ledger_merge_owner_is_never_a_row(tmp_path: Path) -> None:
    """A merge owner that differs from config's distributor (runbook step 7 can move it) reads the table too."""
    env, repo, _ = _setup(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | Date | Who | What | Why | Where |\n|---|---|---|---|---|---|\n"
        "| D-1 | 2026-01-01 | operator | MERGE OWNER: infra | the test | here |\n",
        encoding="utf-8",
    )
    assert sorted(_rows(repo, env)) == ["fleet", "intel", "kaizen"]


def test_a_registry_that_is_not_a_regular_file_falls_back_without_hanging(tmp_path: Path) -> None:
    """A FIFO at the registry path would block a plain read forever; it is skipped like a damaged file."""
    env, repo, _ = _setup(tmp_path)
    reg = repo / ".fabrik" / "session-agents.json"
    reg.unlink()
    os.mkfifo(reg)
    _bind(env, repo, "fleet")
    assert sorted(_rows(repo, env)) == ["fleet"]
