"""Behavior contract for the work-item store core (scripts/work.py, ticket T01a).

The store is one pretty-printed JSON file per item under ``<repo>/.fabrik/work/``, guarded by one
``fcntl`` lock in the git common directory. Every test runs against a throwaway git repo under
``tmp_path`` with an explicit ``env=`` — never the hub's own store.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
_ID_RE = re.compile(r"^W-[0-9a-f]{8}$")


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
    _git(tmp_path, env, "init", "-q", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    return work.resolve()


def run(
    args: list[str], env: dict[str, str], cwd: Path, timeout: float = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _shared(repo: Path) -> Path:
    return repo / ".git" / "fabrik-work"


def _items(repo: Path) -> dict[str, dict]:
    out = {}
    for p in sorted((repo / ".fabrik" / "work").glob("W-*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _snapshot(repo: Path) -> dict[str, bytes]:
    """Every file under the store dir and the shared dir, with its bytes."""
    snap: dict[str, bytes] = {}
    for root in (repo / ".fabrik", _shared(repo)):
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file():
                    snap[str(p)] = p.read_bytes()
    return snap


def _init(repo: Path, env: dict[str, str], distributor: str = "intel") -> None:
    r = run(["init", "--distributor", distributor], env, repo)
    assert r.returncode == 0, r.stderr


def _add(repo: Path, env: dict[str, str], *extra: str, title: str = "T") -> str:
    r = run(["add", "--kind", "backlog", "--title", title, *extra], env, repo)
    assert r.returncode == 0, r.stderr
    rel = r.stdout.strip().splitlines()[-1]
    assert rel.startswith(".fabrik/work/W-") and rel.endswith(".json"), r.stdout
    return Path(rel).stem


def _edit(repo: Path, item_id: str, **fields: object) -> None:
    p = repo / ".fabrik" / "work" / f"{item_id}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data.update(fields)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ids(stdout: str) -> list[str]:
    return [line.split()[0] for line in stdout.splitlines() if line.strip()]


# ── 1. no implicit store ─────────────────────────────────────────────────────────────────────


def test_no_store_every_verb_but_init_refuses_and_creates_nothing(tmp_path):
    env = _env(tmp_path, agent="intel")
    repo = _repo(tmp_path, env)
    sub = repo / "sub"
    sub.mkdir()
    for args in (
        ["add", "--kind", "backlog", "--title", "x"],
        ["ready"],
        ["ready", "--mine"],
        ["next"],
        ["assign", "W-00000000", "--owner", "fleet"],
    ):
        r = run(args, env, sub)
        assert r.returncode != 0, args
        assert "init" in r.stderr, (args, r.stderr)
    assert not (repo / ".fabrik").exists()
    assert not _shared(repo).exists()


def test_init_creates_store_config_and_prints_its_path(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    r = run(["init", "--distributor", "intel"], env, repo / ".")
    assert r.returncode == 0, r.stderr
    assert ".fabrik/work/config.json" in r.stdout
    cfg = json.loads((repo / ".fabrik" / "work" / "config.json").read_text(encoding="utf-8"))
    assert cfg["distributor"] == "intel"
    again = run(["init", "--distributor", "fleet"], env, repo)
    assert again.returncode != 0
    cfg2 = json.loads((repo / ".fabrik" / "work" / "config.json").read_text(encoding="utf-8"))
    assert cfg2["distributor"] == "intel"


def test_init_without_distributor_leaves_it_empty_when_undeclared(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "| ID | Date | Decision | Owner |\n|---|---|---|---|\n| D-001 | x | y | z |\n",
        encoding="utf-8",
    )
    r = run(["init"], env, repo)
    assert r.returncode == 0, r.stderr
    cfg = json.loads((repo / ".fabrik" / "work" / "config.json").read_text(encoding="utf-8"))
    assert cfg["distributor"] == ""


# ── 2. the durable item ──────────────────────────────────────────────────────────────────────


def test_add_twice_same_title_makes_two_distinct_sorted_pretty_items(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    a = _add(repo, env, title="T")
    b = _add(repo, env, title="T")
    assert a != b
    assert _ID_RE.match(a) and _ID_RE.match(b)
    for item_id in (a, b):
        p = repo / ".fabrik" / "work" / f"{item_id}.json"
        text = p.read_text(encoding="utf-8")
        data = json.loads(text)
        assert text == json.dumps(data, indent=2, sort_keys=True) + "\n"
        assert data["id"] == item_id
        assert data["status"] == "open"
        assert data["priority"] == 2
        assert data["kind"] == "backlog"
        assert data["title"] == "T"


def test_add_decision_is_refused_naming_decision_blocks(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    r = run(["add", "--kind", "decision", "--title", "Q"], env, repo)
    assert r.returncode != 0
    assert "DECISION block" in r.stderr
    assert _items(repo) == {}


def test_add_records_next_links_and_priority(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    item_id = _add(
        repo,
        env,
        "--next",
        "write the thing",
        "--link",
        "spec=docs/s.md",
        "--link",
        "decision=D-001",
        "--priority",
        "0",
    )
    data = _items(repo)[item_id]
    assert data["next"] == "write the thing"
    assert data["links"] == {"decision": "D-001", "plan": "", "spec": "docs/s.md"}
    assert data["priority"] == 0
    bad = run(["add", "--kind", "task", "--title", "x", "--link", "nope=1"], env, repo)
    assert bad.returncode != 0
    assert len(_items(repo)) == 1


# ── 3. the store lock ────────────────────────────────────────────────────────────────────────

_HOLDER = """
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
print("locked", flush=True)
time.sleep(60)
"""


def test_cli_verb_waits_10s_on_a_held_lock_then_fails_loud_and_writes_nothing(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    _add(repo, env)
    lock = _shared(repo) / ".lock"
    assert lock.exists()
    before = set(_items(repo))
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(lock)], stdout=subprocess.PIPE, text=True, env=env
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        t0 = time.monotonic()
        r = run(["add", "--kind", "backlog", "--title", "blocked"], env, repo)
        elapsed = time.monotonic() - t0
    finally:
        holder.kill()
        holder.wait()
    assert r.returncode != 0
    assert "lock" in r.stderr and "10" in r.stderr, r.stderr
    assert elapsed >= 10.0
    assert set(_items(repo)) == before
    rows = [
        json.loads(line)
        for line in (_shared(repo) / "readings.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    waits = [row for row in rows if row.get("kind") == "lock-wait"]
    assert len(waits) == 1
    assert waits[0]["wait_s"] >= 10.0
    assert waits[0]["acquired"] is False


def test_store_lock_fail_open_yields_false_after_its_own_timeout(tmp_path):
    """The hook-facing mode (T01b builds on it): a caller-chosen short wait, then False."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    lock = _shared(repo) / ".lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(lock)], stdout=subprocess.PIPE, text=True, env=env
    )
    code = (
        "import sys, time; sys.path.insert(0, sys.argv[1]); import work\n"
        "t0 = time.monotonic()\n"
        "with work._store_lock(work._repo_root(sys.argv[2]), 0.5, fail_open=True) as ok:\n"
        "    print(ok, round(time.monotonic() - t0, 2))\n"
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        r = subprocess.run(
            [sys.executable, "-c", code, str(SCRIPT.parent), str(repo)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        holder.kill()
        holder.wait()
    assert r.returncode == 0, r.stderr
    ok, waited = r.stdout.split()
    assert ok == "False"
    assert 0.5 <= float(waited) < 5


def test_import_is_side_effect_free(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    r = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(SCRIPT.parent)!r}); import work",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout == "" and r.stderr == ""
    assert not (repo / ".fabrik").exists() and not _shared(repo).exists()


# ── 4. ready / next ──────────────────────────────────────────────────────────────────────────


def test_ready_lists_open_unblocked_items_by_priority_then_age(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    p3_old = _add(repo, env, "--priority", "3", title="p3 old")
    p1_new = _add(repo, env, "--priority", "1", title="p1 new")
    p1_old = _add(repo, env, "--priority", "1", title="p1 old")
    p0 = _add(repo, env, "--priority", "0", title="p0")
    blocker = _add(repo, env, "--priority", "2", title="blocker")
    blocked = _add(repo, env, "--priority", "0", title="blocked")
    unblocked = _add(repo, env, "--priority", "2", title="blocker done")
    finished = _add(repo, env, "--priority", "2", title="finished")
    closed = _add(repo, env, "--priority", "0", title="dropped")
    _edit(repo, p3_old, created="2026-01-01T00:00:00.000000Z")
    _edit(repo, p1_old, created="2026-01-02T00:00:00.000000Z")
    _edit(repo, p1_new, created="2026-01-03T00:00:00.000000Z")
    _edit(repo, blocker, created="2026-01-04T00:00:00.000000Z")
    _edit(repo, unblocked, created="2026-01-05T00:00:00.000000Z", blocked_by=[finished])
    _edit(repo, finished, status="done")
    _edit(repo, closed, status="dropped")
    _edit(repo, blocked, blocked_by=[blocker])
    (repo / ".fabrik" / "work" / "W-deadbeef.json").write_text("{not json", encoding="utf-8")
    r = run(["ready"], env, repo)
    assert r.returncode == 0, r.stderr
    assert _ids(r.stdout) == [p0, p1_old, p1_new, blocker, unblocked, p3_old]


def test_ready_mine_lists_owned_first_then_unassigned_and_next_prints_the_first(tmp_path):
    env = _env(tmp_path, agent="infra")
    repo = _repo(tmp_path, env)
    _init(repo, env, distributor="")
    unassigned = _add(repo, env, "--priority", "0", title="free")
    mine = _add(repo, env, "--priority", "3", title="mine")
    theirs = _add(repo, env, "--priority", "0", title="theirs")
    _edit(repo, mine, owner="infra")
    _edit(repo, theirs, owner="fleet")
    r = run(["ready", "--mine"], env, repo)
    assert r.returncode == 0, r.stderr
    assert _ids(r.stdout) == [mine, unassigned]
    n = run(["next"], env, repo)
    assert n.returncode == 0, n.stderr
    assert _ids(n.stdout) == [mine]


# ── 5. ownership ─────────────────────────────────────────────────────────────────────────────


def test_assign_is_the_distributors_and_open_to_all_when_none_is_named(tmp_path):
    env_none = _env(tmp_path)
    env_fleet = _env(tmp_path, agent="fleet")
    env_intel = _env(tmp_path, agent="intel")
    repo = _repo(tmp_path, env_none)
    _init(repo, env_none, distributor="intel")
    item_id = _add(repo, env_none)
    for env in (env_none, env_fleet):
        r = run(["assign", item_id, "--owner", "fleet"], env, repo)
        assert r.returncode != 0
        assert "intel" in r.stderr
        assert _items(repo)[item_id]["owner"] == ""
    ok = run(["assign", item_id, "--owner", "fleet", "--priority", "1"], env_intel, repo)
    assert ok.returncode == 0, ok.stderr
    assert f".fabrik/work/{item_id}.json" in ok.stdout
    assert _items(repo)[item_id]["owner"] == "fleet"
    assert _items(repo)[item_id]["priority"] == 1

    # an empty distributor: any agent may assign
    cfg = repo / ".fabrik" / "work" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["distributor"] = ""
    cfg.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    anyone = run(["assign", item_id, "--owner", "infra"], env_fleet, repo)
    assert anyone.returncode == 0, anyone.stderr
    assert _items(repo)[item_id]["owner"] == "infra"


def test_assign_unknown_id_names_id_and_tree_and_changes_nothing(tmp_path):
    env = _env(tmp_path)  # not the distributor: the missing id is reported first
    repo = _repo(tmp_path, env)
    _init(repo, env)
    before = _snapshot(repo)
    r = run(["assign", "W-00000000", "--owner", "fleet"], env, repo)
    assert r.returncode != 0
    assert "W-00000000" in r.stderr
    assert str(repo) in r.stderr
    assert _snapshot(repo) == before
    bad = run(["assign", "../config", "--owner", "fleet"], env, repo)
    assert bad.returncode != 0
    assert _snapshot(repo) == before
