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
import threading
import time
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"
_ID_RE = re.compile(r"^W-[0-9a-f]{8}$")


def _work_module() -> ModuleType:
    """scripts/work.py imported in-process (import-safe by contract)."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


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
        # hermetic: the obligation lines never read the real mailbox or feedback ledger
        "FABRIK_MAIL_ROOT": str(tmp_path / "tmp" / "mail"),
        "COMMAND_RUN_DIR": str(tmp_path / "tmp" / "state" / "command-runs"),
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


_STUB = """import sys
print({out!r})
sys.exit({rc})
"""


def _merge_owner_init(tmp_path, monkeypatch, capsys, out: str, rc: int) -> tuple[int, str, str]:
    """In-process `init` with DECISIONS_PY pointed at a stub — never the live decisions.py."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    stub = tmp_path / "decisions_stub.py"
    stub.write_text(_STUB.format(out=out, rc=rc), encoding="utf-8")
    work = _work_module()
    monkeypatch.setattr(work, "DECISIONS_PY", stub)
    code = work.main(["--repo", str(repo), "init"])
    cap = capsys.readouterr()
    cfg = json.loads((repo / ".fabrik" / "work" / "config.json").read_text(encoding="utf-8"))
    return code, cfg["distributor"], cap.err


def test_init_without_distributor_undeclared_leaves_it_empty(tmp_path, monkeypatch, capsys):
    code, distributor, _ = _merge_owner_init(tmp_path, monkeypatch, capsys, "UNDECLARED", 3)
    assert code == 0
    assert distributor == ""


def test_init_without_distributor_takes_a_declared_merge_owner(tmp_path, monkeypatch, capsys):
    code, distributor, _ = _merge_owner_init(tmp_path, monkeypatch, capsys, "intel", 0)
    assert code == 0
    assert distributor == "intel"


def test_init_without_distributor_ignores_an_invalid_merge_owner(tmp_path, monkeypatch, capsys):
    code, distributor, err = _merge_owner_init(tmp_path, monkeypatch, capsys, "Intel.bot", 0)
    assert code == 0
    assert distributor == ""
    assert "Intel.bot" in err and "[a-z0-9-]{1,32}" in err


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
time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 60)
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
    expected = f"work: the store lock ({lock}) was held for over 10 s — nothing was written; retry"
    assert expected in r.stderr.splitlines(), r.stderr
    assert 10.0 <= elapsed < 13.0
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
    _add(repo, env)  # init creates no shared dir; the first locked write does
    lock = _shared(repo) / ".lock"
    assert lock.is_file()
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
    assert 0.5 <= float(waited) < 2


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


def test_ready_all_lists_open_unblocked_items_by_priority_then_age(tmp_path):
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
    r = run(["ready", "--all"], env, repo)
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


# ── 6. review pass 1 ─────────────────────────────────────────────────────────────────────────


def test_init_ignores_temp_files_in_the_store(tmp_path):
    """A-S2 + A-O11: a temp orphaned by a killed writer is never committed by `git add`."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    store = repo / ".fabrik" / "work"
    assert (store / ".gitignore").read_text(encoding="utf-8") == "*.tmp\n"
    (store / "W-0000000a.json.abc123.tmp").write_text("{}", encoding="utf-8")
    _git(repo, env, "add", ".fabrik/work")
    staged = _git(repo, env, "diff", "--cached", "--name-only").split()
    assert ".fabrik/work/config.json" in staged
    assert not [p for p in staged if p.endswith(".tmp")]


def test_store_files_are_readable_by_the_group_and_others_per_umask(tmp_path):
    """A-O9: mkstemp's 0600 must not survive into the store."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    item_id = _add(repo, env)
    mask = os.umask(0)
    os.umask(mask)
    want = 0o666 & ~mask
    for name in ("config.json", f"{item_id}.json"):
        assert (repo / ".fabrik" / "work" / name).stat().st_mode & 0o777 == want, name
    env_intel = _env(tmp_path, agent="intel")
    assert run(["assign", item_id, "--owner", "fleet"], env_intel, repo).returncode == 0
    assert (repo / ".fabrik" / "work" / f"{item_id}.json").stat().st_mode & 0o777 == want


def test_ids_are_fullmatched_so_a_trailing_newline_is_refused(tmp_path):
    """A-O6."""
    env = _env(tmp_path, agent="intel")
    repo = _repo(tmp_path, env)
    _init(repo, env)
    good = _add(repo, env)
    src = repo / ".fabrik" / "work" / f"{good}.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    data["id"] = "W-0000000b\n"
    (repo / ".fabrik" / "work" / "W-0000000b\n.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    r = run(["assign", "W-0000000b\n", "--owner", "fleet"], env, repo)
    assert r.returncode != 0
    assert "is not an item id" in r.stderr
    ready = run(["ready"], env, repo)
    assert ready.returncode == 0
    assert _ids(ready.stdout) == [good]


def test_assign_refuses_a_file_whose_id_field_differs(tmp_path):
    """A-O1: a renamed/copied item file never redirects a write to another item."""
    env = _env(tmp_path, agent="intel")
    repo = _repo(tmp_path, env)
    _init(repo, env)
    real = _add(repo, env)
    store = repo / ".fabrik" / "work"
    (store / "W-11111111.json").write_bytes((store / f"{real}.json").read_bytes())
    before = _snapshot(repo)
    r = run(["assign", "W-11111111", "--owner", "fleet"], env, repo)
    assert r.returncode != 0
    assert "W-11111111" in r.stderr and real in r.stderr
    assert _snapshot(repo) == before


def test_owner_and_distributor_must_be_agent_names(tmp_path):
    """A-O4 + A-O5: an owner or distributor no agent can resolve to is refused, naming the rule."""
    env = _env(tmp_path, agent="intel")
    repo = _repo(tmp_path, env)
    bad = run(["init", "--distributor", "Intel"], env, repo)
    assert bad.returncode != 0
    assert "[a-z0-9-]{1,32}" in bad.stderr
    assert not (repo / ".fabrik").exists()
    _init(repo, env)
    item_id = _add(repo, env)
    before = _snapshot(repo)
    r = run(["assign", item_id, "--owner", "Not An Agent"], env, repo)
    assert r.returncode != 0
    assert "[a-z0-9-]{1,32}" in r.stderr
    assert _snapshot(repo) == before
    unassign = run(["assign", item_id, "--owner", ""], env, repo)
    assert unassign.returncode == 0, unassign.stderr


def test_an_invalid_claude_agent_is_named_as_invalid_not_unset(tmp_path):
    """A-S3 + A-O13."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env, distributor="intel")
    item_id = _add(repo, env)
    r = run(["assign", item_id, "--owner", "fleet"], _env(tmp_path, agent="Intel"), repo)
    assert r.returncode != 0
    assert "CLAUDE_AGENT='Intel' is not a valid agent name" in r.stderr, r.stderr
    unset = run(["assign", item_id, "--owner", "fleet"], env, repo)
    assert "CLAUDE_AGENT unset" in unset.stderr


def test_agent_name_fallback_validates_claude_agent(tmp_path, monkeypatch):
    """A-S3: when whoami_agent.py cannot be imported, the fallback applies the same name rule."""
    work = _work_module()
    monkeypatch.setattr(work, "WHOAMI_PY", tmp_path / "missing.py")
    monkeypatch.setenv("CLAUDE_AGENT", "intel \n rm -rf")
    assert work._agent_name() == ""
    monkeypatch.setenv("CLAUDE_AGENT", "intel")
    assert work._agent_name() == "intel"


def test_store_lock_and_readings_never_create_the_shared_dir_without_a_store(tmp_path):
    """A-O7: the no-implicit-store rule holds inside the helpers, not only in the verbs."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    work = _work_module()
    with work._store_lock(repo, 0.5, fail_open=True) as ok:
        assert ok is False
    raised = ""
    try:
        with work._store_lock(repo, 0.5, fail_open=False):
            pass
    except work.WorkError as exc:
        raised = str(exc)
    assert "init" in raised
    work._append_reading(repo, {"kind": "probe"})
    assert not _shared(repo).exists()
    assert not (repo / ".fabrik").exists()


_TRY_LOCK = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print("free")
except BlockingIOError:
    print("held")
"""


def test_store_lock_is_reentrant_within_one_process(tmp_path):
    """A-O8: a nested acquisition succeeds at once and the outer hold survives the inner exit."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    _add(repo, env)
    work = _work_module()
    lock = _shared(repo) / ".lock"

    def probe() -> str:
        return subprocess.run(
            [sys.executable, "-c", _TRY_LOCK, str(lock)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()

    with work._store_lock(repo, 10, fail_open=False) as outer:
        assert outer is True
        t0 = time.monotonic()
        with work._store_lock(repo, 0.5, fail_open=True) as inner:
            assert inner is True
        assert time.monotonic() - t0 < 0.1
        assert probe() == "held"
    assert probe() == "free"


def test_assign_checks_the_distributor_under_the_lock(tmp_path):
    """A-H1: a distributor named while `assign` waited on the lock still binds that assign."""
    env_none = _env(tmp_path)
    repo = _repo(tmp_path, env_none)
    _init(repo, env_none, distributor="")
    item_id = _add(repo, env_none)
    lock = _shared(repo) / ".lock"
    cfg = repo / ".fabrik" / "work" / "config.json"
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(lock), "1.5"],
        stdout=subprocess.PIPE,
        text=True,
        env=env_none,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), "assign", item_id, "--owner", "fleet"],
            cwd=repo,
            env=_env(tmp_path, agent="fleet"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.7)  # assign has passed its pre-lock checks and waits on the lock
        cfg.write_text(json.dumps({"distributor": "intel"}, indent=2) + "\n", encoding="utf-8")
        _out, err = proc.communicate(timeout=30)
    finally:
        holder.kill()
        holder.wait()
    assert proc.returncode != 0, err
    assert "intel" in err
    assert _items(repo)[item_id]["owner"] == ""


def test_git_errors_carry_gits_own_reason(tmp_path):
    """A-S4."""
    env = _env(tmp_path)
    missing = tmp_path / "does-not-exist"
    r = run(["--repo", str(missing), "ready"], env, tmp_path)
    assert r.returncode != 0
    assert "is not inside a git work tree" not in r.stderr
    assert "cannot change to" in r.stderr, r.stderr


def test_os_errors_are_named_one_line_messages_never_tracebacks(tmp_path):
    """A-O2."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    (repo / ".fabrik").write_text("not a dir\n", encoding="utf-8")
    r = run(["init", "--distributor", "intel"], env, repo)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert "already exists — the store is initialised" not in r.stderr
    assert r.stderr.startswith("work: cannot create .fabrik/work: "), r.stderr
    (repo / ".fabrik").unlink()
    (repo / ".fabrik").mkdir()
    (repo / ".fabrik" / "work").write_text("a file\n", encoding="utf-8")
    r2 = run(["init", "--distributor", "intel"], env, repo)
    assert r2.returncode != 0
    assert "Traceback" not in r2.stderr
    assert "already exists — the store is initialised" not in r2.stderr
    assert r2.stderr.startswith("work: cannot create .fabrik/work: "), r2.stderr


def test_a_write_into_a_read_only_store_is_a_named_error_not_a_traceback(tmp_path):
    """A-O2: main() turns any OSError into one named line (assign's temp create here)."""
    env = _env(tmp_path, agent="intel")
    repo = _repo(tmp_path, env)
    _init(repo, env)
    item_id = _add(repo, env)
    store = repo / ".fabrik" / "work"
    store.chmod(0o555)
    try:
        r = run(["assign", item_id, "--owner", "fleet"], env, repo)
    finally:
        store.chmod(0o755)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert r.stderr.startswith("work: assign failed — PermissionError"), r.stderr


def _linked_worktree(tmp_path: Path, env: dict[str, str], repo: Path, base: str) -> Path:
    wt = tmp_path / "wt"
    _git(repo, env, "worktree", "add", "-q", "-b", "side", str(wt), base)
    return wt.resolve()


def test_a_linked_worktree_shares_the_main_checkouts_lock_and_readings(tmp_path):
    """B-S1: lock and readings land in the one <git-common-dir>/fabrik-work/."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    _git(repo, env, "add", ".fabrik/work")
    _git(repo, env, "commit", "-q", "-m", "store")
    wt = _linked_worktree(tmp_path, env, repo, "HEAD")
    shared = _shared(repo)
    if shared.exists():
        for p in shared.iterdir():
            p.unlink()
        shared.rmdir()
    _add(wt, env)
    assert (shared / ".lock").is_file()
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(shared / ".lock"), "0.6"],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        _add(wt, env, title="waited")
    finally:
        holder.kill()
        holder.wait()
    rows = (shared / "readings.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(row)["kind"] == "lock-wait" for row in rows)
    local_gitdir = Path(_git(wt, env, "rev-parse", "--absolute-git-dir").strip())
    assert local_gitdir != (repo / ".git").resolve()
    assert not (local_gitdir / "fabrik-work").exists()


def test_init_in_a_linked_worktree_is_refused_when_the_main_checkout_has_a_store(tmp_path):
    """A-O10: no second, divergent config.json on a branch cut before init."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    seed = _git(repo, env, "rev-parse", "HEAD").strip()
    _init(repo, env)
    wt = _linked_worktree(tmp_path, env, repo, seed)
    ready = run(["ready"], env, wt)
    assert ready.returncode != 0
    assert str(repo) in ready.stderr
    r = run(["init", "--distributor", "fleet"], env, wt)
    assert r.returncode != 0
    assert str(repo) in r.stderr
    assert not (wt / ".fabrik").exists()


# ── 7. review pass 2 ─────────────────────────────────────────────────────────────────────────


def test_store_lock_excludes_another_thread_and_stays_reentrant_per_thread(tmp_path):
    """A-N1/A-O14: re-entrancy is per thread; a second thread waits on the real flock."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _init(repo, env)
    _add(repo, env)  # creates the shared dir
    work = _work_module()
    held = threading.Event()
    errors: list[BaseException] = []
    marks: dict[str, float] = {}

    def first() -> None:
        try:
            with work._store_lock(repo, 10, fail_open=False):
                held.set()
                t0 = time.monotonic()
                with work._store_lock(repo, 0.5, fail_open=True) as inner:
                    assert inner is True
                marks["nest"] = time.monotonic() - t0
                time.sleep(0.5)
                marks["released"] = time.monotonic()
        except BaseException as exc:  # surfaced below; a thread cannot fail the test itself
            errors.append(exc)

    def second() -> None:
        try:
            assert held.wait(5)
            with work._store_lock(repo, 10, fail_open=False) as ok:
                marks["second_in"] = time.monotonic()
                assert ok is True
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors, errors
    assert marks["nest"] < 0.1
    assert marks["second_in"] >= marks["released"]


def test_init_is_refused_when_any_other_worktree_holds_a_store(tmp_path):
    """A-O15: a store initialised in a linked worktree blocks init in the main checkout and in a
    second linked worktree, naming the tree that holds it."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    wt = _linked_worktree(tmp_path, env, repo, "HEAD")
    _init(wt, env)
    r = run(["init", "--distributor", "fleet"], env, repo)
    assert r.returncode != 0
    assert str(wt) in r.stderr, r.stderr
    assert not (repo / ".fabrik").exists()
    wt2 = tmp_path / "wt2"
    _git(repo, env, "worktree", "add", "-q", "-b", "side2", str(wt2), "HEAD")
    r2 = run(["init", "--distributor", "fleet"], env, wt2)
    assert r2.returncode != 0
    assert str(wt) in r2.stderr, r2.stderr
    assert not (wt2 / ".fabrik").exists()
