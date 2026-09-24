"""Behavior contract for claims, leases, the closing verbs and the hook-facing API (ticket T01b).

Claims live under ``<git common dir>/fabrik-work/claims/<id>.json`` and expire at read time;
``done``/``drop``/``answer`` write closed markers under ``fabrik-work/closed/``. Every test runs
against throwaway git repos (and real ``git worktree add`` worktrees) under ``tmp_path`` with an
explicit ``env=`` — never the hub's own store.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"

BLOCK = (
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Deploy the certified build to production now?\n"
    "- Why it is yours: gate — Gate 2, a destructive/irreversible action needing authorisation.\n"
    "- Options: A — deploy now · B — hold for one more smoke pass\n"
    "- Recommendation: A — the certification gauntlet already passed."
)
BLOCK_2 = BLOCK.replace("production now?", "staging first?")


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _digest(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8", "replace")).hexdigest()


def _env(tmp_path: Path, agent: str | None = None) -> dict[str, str]:
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


def _as(env: dict[str, str], agent: str | None = None, session: str | None = None) -> dict:
    out = {k: v for k, v in env.items() if k not in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID")}
    if agent:
        out["CLAUDE_AGENT"] = agent
    if session:
        out["CLAUDE_CODE_SESSION_ID"] = session
    return out


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def _repo(tmp_path: Path, env: dict[str, str]) -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(work))
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


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = run(args, env, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _shared(repo: Path) -> Path:
    return repo / ".git" / "fabrik-work"


def _item_file(tree: Path, item_id: str) -> Path:
    return tree / ".fabrik" / "work" / f"{item_id}.json"


def _item(tree: Path, item_id: str) -> dict:
    return json.loads(_item_file(tree, item_id).read_text(encoding="utf-8"))


def _claim(repo: Path, item_id: str) -> dict:
    return json.loads((_shared(repo) / "claims" / f"{item_id}.json").read_text(encoding="utf-8"))


def _set_claim(repo: Path, item_id: str, **fields: object) -> None:
    p = _shared(repo) / "claims" / f"{item_id}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data.update(fields)
    p.write_text(json.dumps(data), encoding="utf-8")


def _store(tmp_path: Path, env: dict[str, str], distributor: str = "intel") -> Path:
    repo = _repo(tmp_path, env)
    _ok(["init", "--distributor", distributor], env, repo)
    return repo


def _add(tree: Path, env: dict[str, str], title: str = "T") -> str:
    out = _ok(["add", "--kind", "backlog", "--title", title], env, tree)
    return Path(out.strip().splitlines()[-1]).stem


def _ready_ids(tree: Path, env: dict[str, str]) -> list[str]:
    return [ln.split()[0] for ln in _ok(["ready"], env, tree).splitlines() if ln.strip()]


def _commit_store(repo: Path, env: dict[str, str], msg: str = "store") -> None:
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", msg)


def _worktree(repo: Path, env: dict[str, str], name: str = "wt") -> Path:
    wt = repo.parent / name
    _git(repo, env, "worktree", "add", "-q", "-b", name, str(wt))
    return wt.resolve()


def _evidence(tree: Path, env: dict[str, str], message: str) -> str:
    (tree / "work.txt").write_text(message + "\n", encoding="utf-8")
    _git(tree, env, "add", "work.txt")
    _git(tree, env, "commit", "-q", "-m", message)
    return _git(tree, env, "rev-parse", "HEAD").strip()


@pytest.fixture
def api(tmp_path, monkeypatch):
    """(module, env) with the process environment made hermetic for in-process API calls."""
    env = _env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    return _work_module(), env


# ── V3: claim atomicity, expiry, fencing ─────────────────────────────────────────────────────


def test_three_processes_claiming_at_once_have_exactly_one_winner(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    go = tmp_path / "go"
    starter = (
        "import os, runpy, sys, time\n"
        "open(sys.argv[1], 'w').close()\n"
        f"while not os.path.exists({str(go)!r}): time.sleep(0.001)\n"
        f"sys.argv = [{str(SCRIPT)!r}] + sys.argv[2:]\n"
        f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n"
    )
    ready = [tmp_path / f"ready-{i}" for i in range(3)]
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", starter, str(ready[i]), "claim", item, "--session", f"s{i}"],
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(3)
    ]
    deadline = time.monotonic() + 30
    while not all(r.exists() for r in ready):
        assert time.monotonic() < deadline, "workers never signalled ready"
        time.sleep(0.005)
    go.write_text("go", encoding="utf-8")
    results = []
    for p in procs:
        out, err = p.communicate(timeout=60)
        results.append((p.returncode, out, err))
    winners = [r for r in results if r[0] == 0]
    assert len(winners) == 1, results
    holder = _claim(repo, item)["session"]
    assert holder in {"s0", "s1", "s2"}
    losers = [r for r in results if r[0] != 0]
    assert len(losers) == 2
    for _, _, err in losers:
        assert holder in err, err
    assert _claim(repo, item)["token"] == 1


def test_an_expired_claim_is_ready_again_and_a_new_claim_gets_a_higher_token(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    assert item not in _ready_ids(repo, env)
    first = _claim(repo, item)
    assert first["lease_s"] == 7200
    assert set(first) >= {"agent", "session", "at", "lease_s", "token"}
    r = run(["claim", item, "--session", "B"], env, repo)
    assert r.returncode != 0 and "A" in r.stderr
    _set_claim(repo, item, at=time.time() - 7201)
    assert item in _ready_ids(repo, env)
    _ok(["claim", item, "--session", "B"], env, repo)
    second = _claim(repo, item)
    assert second["session"] == "B"
    assert second["token"] > first["token"]


def test_the_live_holders_claim_and_on_harvest_push_the_lease_end_later(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    _set_claim(repo, item, at=time.time() - 3600)
    before = _claim(repo, item)
    _ok(["claim", item, "--session", "A"], env, repo)
    renewed = _claim(repo, item)
    assert renewed["at"] + renewed["lease_s"] > before["at"] + before["lease_s"]
    assert renewed["token"] == before["token"]
    _set_claim(repo, item, at=time.time() - 3600)
    before = _claim(repo, item)
    assert work.on_harvest(repo, session="A") is None
    after = _claim(repo, item)
    assert after["at"] + after["lease_s"] > before["at"] + before["lease_s"]
    # another session's harvest renews nothing of A's
    _set_claim(repo, item, at=time.time() - 3600)
    before = _claim(repo, item)
    work.on_harvest(repo, session="B")
    assert _claim(repo, item)["at"] == before["at"]


def test_after_a_takeover_the_first_claimers_done_is_refused_for_a_token_mismatch(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    _set_claim(repo, item, at=time.time() - 7201)
    _ok(["claim", item, "--session", "B"], env, repo)
    sha = _evidence(repo, env, f"work for {item}")
    before = _item_file(repo, item).read_bytes()
    r = run(["done", item, "--evidence", sha, "--session", "A"], env, repo)
    assert r.returncode != 0
    assert "token" in r.stderr and "B" in r.stderr, r.stderr
    assert _item_file(repo, item).read_bytes() == before
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()
    # the release is fenced the same way
    r = run(["release", item, "--session", "A"], env, repo)
    assert r.returncode != 0 and "B" in r.stderr
    assert _claim(repo, item)["session"] == "B"
    # the live holder closes it
    _ok(["done", item, "--evidence", sha, "--session", "B"], env, repo)
    assert _item(repo, item)["status"] == "done"


def test_a_claim_needs_a_session_and_the_env_session_counts(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    r = run(["claim", item], env, repo)
    assert r.returncode != 0
    assert "CLAUDE_CODE_SESSION_ID" in r.stderr and "--session" in r.stderr
    assert not (_shared(repo) / "claims" / f"{item}.json").exists()
    _ok(["claim", item], _as(env, session="S-env"), repo)
    assert _claim(repo, item)["session"] == "S-env"


def test_release_gives_the_claim_up_and_keeps_the_token_counter(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    _ok(["release", item, "--session", "A"], env, repo)
    assert item in _ready_ids(repo, env)
    _ok(["claim", item, "--session", "B"], env, repo)
    assert _claim(repo, item)["token"] == 2


def test_a_claim_from_a_linked_worktree_hides_the_item_from_ready_in_the_main_checkout(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    assert item in _ready_ids(repo, env)
    _ok(["claim", item, "--session", "W"], env, wt)
    common = {
        _git(t, env, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        for t in (repo, wt)
    }
    assert len(common) == 1
    shared_claim = Path(common.pop()) / "fabrik-work" / "claims" / f"{item}.json"
    assert shared_claim.is_file()
    assert json.loads(shared_claim.read_text(encoding="utf-8"))["session"] == "W"
    assert not (wt / ".git").is_dir()
    assert item not in _ready_ids(repo, env)
    assert item not in _ready_ids(wt, env)


# ── V4: evidence, closed markers ─────────────────────────────────────────────────────────────


def test_done_in_a_worktree_needs_real_evidence_and_its_marker_hides_the_main_copy(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    other = _add(repo, env, title="other")
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    _ok(["claim", item, "--session", "W"], env, wt)
    before = _item_file(wt, item).read_bytes()
    wrong = _evidence(wt, env, f"unrelated work {other}")
    for args in (
        ["done", item, "--session", "W"],
        ["done", item, "--evidence", "0123456789abcdef0123456789abcdef01234567", "--session", "W"],
        ["done", item, "--evidence", "not-a-sha", "--session", "W"],
        ["done", item, "--evidence", wrong, "--session", "W"],
    ):
        r = run(args, env, wt)
        assert r.returncode != 0, args
        assert r.stderr.strip(), args
        assert _item_file(wt, item).read_bytes() == before, args
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()
    sha = _evidence(wt, env, f"feat: the thing ({item})")
    out = _ok(["done", item, "--evidence", sha, "--session", "W"], env, wt)
    assert f".fabrik/work/{item}.json" in out
    done = _item(wt, item)
    assert done["status"] == "done" and done["evidence"] == sha
    marker = json.loads((_shared(repo) / "closed" / f"{item}.json").read_text(encoding="utf-8"))
    assert marker["evidence"] == sha and marker["status"] == "done"
    assert _item(repo, item)["status"] == "open"
    assert item not in _ready_ids(repo, env)
    assert other in _ready_ids(repo, env)
    # the claim ended with the item
    assert item not in _ready_ids(wt, env)
    r = run(["claim", item, "--session", "X"], env, repo)
    assert r.returncode != 0


def test_a_marker_is_pruned_once_the_main_head_reads_done_and_ignored_after_14_days(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    stale = _add(repo, env, title="stale")
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    for it in (item, stale):
        sha = _evidence(wt, env, f"close {it}")
        _ok(["done", it, "--evidence", sha, "--session", "W"], env, wt)
    _commit_store(wt, env, "close both")
    closed = _shared(repo) / "closed"
    # a marker older than 14 days stops hiding its item
    mp = closed / f"{stale}.json"
    data = json.loads(mp.read_text(encoding="utf-8"))
    data["at"] = time.time() - 15 * 86400
    mp.write_text(json.dumps(data), encoding="utf-8")
    assert stale in _ready_ids(repo, env)
    assert item not in _ready_ids(repo, env)
    # merge the branch: main HEAD now reads done, and the next locked write prunes the marker
    _git(repo, env, "merge", "-q", "--no-ff", "-m", "merge wt", "wt")
    assert _item(repo, item)["status"] == "done"
    assert (closed / f"{item}.json").exists()
    _add(repo, env, title="any write")
    assert not (closed / f"{item}.json").exists()


# ── awaiting-operator, answer, drop ──────────────────────────────────────────────────────────


def test_an_awaiting_item_refuses_drop_done_claim_and_closes_only_by_answer(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    decisions = repo / "docs" / "DECISIONS.md"
    decisions.parent.mkdir()
    decisions.write_text("| D-001 | x |\n", encoding="utf-8")
    item = work.ensure_decision_item(repo, block=BLOCK, msg_digest=_digest("m1"), session="S1")
    assert item
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha = _evidence(repo, env, f"answer {item}")
    before = _item_file(repo, item).read_bytes()
    for args in (
        ["drop", item, "--why", "x"],
        ["done", item, "--evidence", sha, "--session", "S1"],
        ["claim", item, "--session", "S1"],
    ):
        r = run(args, _as(env, agent="intel"), repo)
        assert r.returncode != 0, args
        assert "answer" in r.stderr, (args, r.stderr)
        assert _item_file(repo, item).read_bytes() == before, args
    assert work.prompt_block(wt, "S9").count(item) == 1
    dec_before = decisions.read_bytes()
    out = _ok(["answer", item, "--note", "ship it", "--decision", "D-001"], env, repo)
    assert f".fabrik/work/{item}.json" in out
    answered = _item(repo, item)
    assert answered["status"] == "done"
    assert answered["note"] == "ship it"
    assert answered["links"]["decision"] == "D-001"
    assert decisions.read_bytes() == dec_before
    marker = json.loads((_shared(repo) / "closed" / f"{item}.json").read_text(encoding="utf-8"))
    assert marker["note"] == "ship it" and marker["decision"] == "D-001"
    # the linked worktree's committed awaiting copy stops printing there at once
    assert _item(wt, item)["status"] == "awaiting-operator"
    assert item not in work.prompt_block(wt, "S9")
    # answer on an item that is not awaiting is refused
    other = _add(repo, env, title="plain")
    r = run(["answer", other, "--note", "n"], env, repo)
    assert r.returncode != 0


def test_answer_refuses_a_decision_link_that_is_not_a_ledger_id(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    item = work.ensure_decision_item(repo, block=BLOCK, msg_digest=_digest("m1"), session="S1")
    r = run(["answer", item, "--note", "n", "--decision", "decided"], env, repo)
    assert r.returncode != 0 and "D-" in r.stderr
    assert _item(repo, item)["status"] == "awaiting-operator"


def test_drop_is_the_owners_the_distributors_or_anyones_when_unassigned(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env, distributor="intel")
    a = _add(repo, env, title="a")
    b = _add(repo, env, title="b")
    c = _add(repo, env, title="c")
    for it in (a, b):
        _ok(["assign", it, "--owner", "fleet"], _as(env, agent="intel"), repo)
    before = _item_file(repo, a).read_bytes()
    r = run(["drop", a, "--why", "x"], _as(env, agent="infra"), repo)
    assert r.returncode != 0 and "fleet" in r.stderr and "intel" in r.stderr
    assert _item_file(repo, a).read_bytes() == before
    _ok(["drop", a, "--why", "not needed"], _as(env, agent="fleet"), repo)
    _ok(["drop", b, "--why", "superseded"], _as(env, agent="intel"), repo)
    _ok(["drop", c, "--why", "nobody's"], _as(env, agent="infra"), repo)
    for it, why in ((a, "not needed"), (b, "superseded"), (c, "nobody's")):
        got = _item(repo, it)
        assert got["status"] == "dropped" and got["note"] == why
        assert (_shared(repo) / "closed" / f"{it}.json").exists()
    r = run(["drop", a, "--why", "again"], _as(env, agent="fleet"), repo)
    assert r.returncode != 0


def test_every_verb_names_an_unknown_id_and_the_tree_before_any_authorisation(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env, distributor="intel")
    for args in (
        ["claim", "W-00000000", "--session", "A"],
        ["claim", "W-00000000"],
        ["release", "W-00000000", "--session", "A"],
        ["done", "W-00000000", "--evidence", "HEAD", "--session", "A"],
        ["drop", "W-00000000", "--why", "x"],
        ["answer", "W-00000000", "--note", "x"],
    ):
        r = run(args, _as(env, agent="infra"), repo)
        assert r.returncode != 0, args
        assert "W-00000000" in r.stderr and str(repo) in r.stderr, (args, r.stderr)
    assert not (_shared(repo) / "claims").exists()


def test_an_item_only_in_another_tree_is_not_found_in_the_callers_tree(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    item = _add(wt, env, title="branch only")
    r = run(["claim", item, "--session", "A"], env, repo)
    assert r.returncode != 0 and item in r.stderr and str(repo) in r.stderr


# ── the hook-facing API ──────────────────────────────────────────────────────────────────────


def test_ensure_decision_item_creates_skips_refreshes_and_recreates_after_an_answer(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    first = work.ensure_decision_item(repo, block=BLOCK, msg_digest="d1", session="S1")
    assert first
    item = _item(repo, first)
    assert item["kind"] == "decision" and item["status"] == "awaiting-operator"
    assert item["question"] == "Deploy the certified build to production now?"
    assert item["ground"] == "gate"
    assert item["msg_digests"] == ["d1"]
    assert item["block_digest"] == hashlib.sha256(BLOCK.strip().encode()).hexdigest()
    assert work.has_msg_digest(repo, "d1") is True
    assert work.has_msg_digest(repo, "d0") is False
    raw = _item_file(repo, first).read_bytes()
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="d1", session="S1") == first
    assert _item_file(repo, first).read_bytes() == raw
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="d2", session="S2") == first
    assert _item(repo, first)["msg_digests"] == ["d1", "d2"]
    _ok(["answer", first, "--note", "yes"], env, repo)
    # the same message harvested again never reopens the answered item
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="d2", session="S2") == first
    second = work.ensure_decision_item(repo, block=BLOCK, msg_digest="d3", session="S2")
    assert second and second != first
    assert _item(repo, second)["status"] == "awaiting-operator"
    assert len(list((repo / ".fabrik" / "work").glob("W-*.json"))) == 2
    third = work.ensure_decision_item(repo, block=BLOCK_2, msg_digest="d4", session="S2")
    assert third not in (first, second)


def test_a_block_answered_in_another_tree_is_asked_anew_not_refreshed(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    first = work.ensure_decision_item(repo, block=BLOCK, msg_digest="d1", session="S1")
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    _ok(["answer", first, "--note", "yes"], env, wt)
    assert _item(repo, first)["status"] == "awaiting-operator"
    again = work.ensure_decision_item(repo, block=BLOCK, msg_digest="d2", session="S1")
    assert again and again != first
    assert _item(repo, first)["msg_digests"] == ["d1"]


def test_ensure_decision_items_creates_every_missing_entry_under_one_lock(
    tmp_path, api, monkeypatch
):
    work, env = api
    repo = _store(tmp_path, env)
    calls = []
    real = work._store_lock

    @contextlib.contextmanager
    def counting(*a, **k):
        calls.append(a)
        with real(*a, **k) as held:
            yield held

    monkeypatch.setattr(work, "_store_lock", counting)
    ids = work.ensure_decision_items(repo, [(BLOCK, "d1", "S1"), (BLOCK_2, "d2", "S1")])
    assert ids is not None and len(ids) == 2 and len(set(ids)) == 2
    assert len(calls) == 1
    assert {_item(repo, i)["question"] for i in ids} == {
        "Deploy the certified build to production now?",
        "Deploy the certified build to staging first?",
    }


def test_on_harvest_writes_the_decision_then_the_items_next_under_one_lock(
    tmp_path, api, monkeypatch
):
    work, env = api
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "S1"], env, repo)
    calls = []
    real = work._store_lock

    @contextlib.contextmanager
    def counting(*a, **k):
        calls.append(k.get("fail_open"))
        with real(*a, **k) as held:
            yield held

    monkeypatch.setattr(work, "_store_lock", counting)
    writes = []
    real_item, real_claim = work._write_item, work._write_claim

    def item_write(repo_, it, **k):
        writes.append(("item", str(it.get("id")), str(it.get("kind"))))
        return real_item(repo_, it, **k)

    def claim_write(repo_, item_id, claim):
        writes.append(("claim", item_id, ""))
        return real_claim(repo_, item_id, claim)

    monkeypatch.setattr(work, "_write_item", item_write)
    monkeypatch.setattr(work, "_write_claim", claim_write)
    got = work.on_harvest(
        repo,
        session="S1",
        block=BLOCK,
        msg_digest="m1",
        next_text=f"{item}: write the migration test",
    )
    assert got and got != item
    assert _item(repo, got)["kind"] == "decision"
    assert _item(repo, item)["next"] == f"{item}: write the migration test"
    assert calls == [True]
    kinds = [(w[0], w[1] == got, w[1] == item) for w in writes]
    decision_at = kinds.index(("item", True, False))
    next_at = kinds.index(("item", False, True))
    renew_at = kinds.index(("claim", False, True))
    assert decision_at < next_at < renew_at, writes


def test_on_harvest_fails_open_when_the_lock_is_held(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    _add(repo, env)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl, sys, time; f = open(sys.argv[1], 'a');"
            " fcntl.flock(f, fcntl.LOCK_EX); print('held', flush=True); time.sleep(20)",
            str(_shared(repo) / ".lock"),
        ],
        stdout=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        t0 = time.monotonic()
        got = work.on_harvest(repo, session="S1", block=BLOCK, msg_digest="m1", lock_timeout=0.3)
        assert got is None
        assert time.monotonic() - t0 < 5
        assert work.ensure_decision_items(repo, [(BLOCK, "m1", "S1")], lock_timeout=0.3) is None
    finally:
        holder.kill()
        holder.wait(timeout=10)
    assert not work.has_msg_digest(repo, "m1")


def test_prompt_block_lists_awaiting_items_this_sessions_claims_and_the_ready_count(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    assert work.prompt_block(repo, "S1") == ""
    a = _add(repo, env, title="alpha")
    _add(repo, env, title="beta")
    _ok(["claim", a, "--session", "S1"], env, repo)
    dec = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m1", session="S2")
    block = work.prompt_block(repo, "S1")
    assert dec in block and "Deploy the certified build to production now?" in block
    assert a in block and "alpha" in block
    assert "1 ready" in block
    assert all(len(line) <= 300 for line in block.splitlines())
    other = work.prompt_block(repo, "S2")
    assert dec in other and a not in other


def test_hook_api_on_a_store_less_repo_returns_empty_and_creates_nothing(tmp_path, api):
    work, env = api
    repo = _repo(tmp_path, env)
    sub = repo / "sub"
    sub.mkdir()
    assert work.repo_root(sub) == repo
    assert work.repo_root(tmp_path / "home") is None
    assert work.has_store(repo) is False
    assert (
        work.on_harvest(sub, session="S", block=BLOCK, msg_digest="m", next_text="W-00000000 x")
        is None
    )
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="m", session="S") is None
    assert work.ensure_decision_items(repo, [(BLOCK, "m", "S")]) is None
    assert work.has_msg_digest(repo, "m") is False
    assert work.prompt_block(repo, "S") == ""
    assert not (repo / ".fabrik").exists()
    assert not _shared(repo).exists()
    assert work.prompt_block(tmp_path / "home", "S") == ""


# ── review pass 1 ────────────────────────────────────────────────────────────────────────────


def test_a_linked_worktree_does_not_hide_or_refuse_an_item_on_the_main_head_alone(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha = _evidence(repo, env, f"close {item}")
    _ok(["done", item, "--evidence", sha, "--session", "M"], env, repo)
    _commit_store(repo, env, "close")
    _add(repo, env, title="a locked write prunes the marker")
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()
    assert _item(wt, item)["status"] == "open"
    assert item in _ready_ids(wt, env)
    _ok(["claim", item, "--session", "W"], env, wt)


def test_init_records_the_base_branch_and_the_prune_reads_it_not_the_checked_out_branch(
    tmp_path,
):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    cfg = json.loads((repo / ".fabrik" / "work" / "config.json").read_text(encoding="utf-8"))
    assert cfg["base_branch"] == "main"
    item = _add(repo, env)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha = _evidence(wt, env, f"close {item}")
    _ok(["done", item, "--evidence", sha, "--session", "W"], env, wt)
    _commit_store(wt, env, "close")
    # the main checkout moves to a side branch on which the item reads done
    _git(repo, env, "checkout", "-q", "-b", "side")
    _git(repo, env, "merge", "-q", "--no-ff", "-m", "merge wt into side", "wt")
    assert _item(repo, item)["status"] == "done"
    _add(repo, env, title="a locked write")
    assert (_shared(repo) / "closed" / f"{item}.json").exists()
    # once the BASE branch reads done, the next locked write prunes it
    _git(repo, env, "checkout", "-q", "main")
    _git(repo, env, "merge", "-q", "--no-ff", "-m", "merge wt into main", "wt")
    _add(repo, env, title="another locked write")
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()


def test_drop_is_fenced_by_another_sessions_live_claim(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env, distributor="intel")
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    before = _item_file(repo, item).read_bytes()
    r = run(["drop", item, "--why", "x"], _as(env, agent="intel", session="B"), repo)
    assert r.returncode != 0 and "token" in r.stderr and "A" in r.stderr, r.stderr
    assert _item_file(repo, item).read_bytes() == before
    _ok(["drop", item, "--why", "mine to drop"], _as(env, agent="intel", session="A"), repo)
    assert _item(repo, item)["status"] == "dropped"
    other = _add(repo, env, title="expired")
    _ok(["claim", other, "--session", "A"], env, repo)
    _set_claim(repo, other, at=time.time() - 7201)
    _ok(["drop", other, "--why", "lapsed"], _as(env, agent="intel", session="B"), repo)


def test_on_harvest_leaves_the_next_of_an_item_another_session_holds(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    before = _item_file(repo, item).read_bytes()
    got = work.on_harvest(
        repo, session="B", block=BLOCK, msg_digest="m1", next_text=f"{item}: not yours"
    )
    assert got and _item(repo, got)["kind"] == "decision"
    assert _item_file(repo, item).read_bytes() == before
    work.on_harvest(repo, session="A", next_text=f"{item}: yours")
    assert _item(repo, item)["next"] == f"{item}: yours"


def _set_item(tree: Path, item_id: str, **fields: object) -> None:
    p = _item_file(tree, item_id)
    data = json.loads(p.read_text(encoding="utf-8"))
    data.update(fields)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_claim_is_refused_on_a_blocked_item(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    dep = _add(repo, env, title="dep")
    item = _add(repo, env, title="waits")
    _set_item(repo, item, blocked_by=[dep])
    r = run(["claim", item, "--session", "A"], env, repo)
    assert r.returncode != 0 and dep in r.stderr, r.stderr
    third = _add(repo, env, title="status blocked")
    _set_item(repo, third, status="blocked")
    r = run(["claim", third, "--session", "A"], env, repo)
    assert r.returncode != 0 and "blocked" in r.stderr, r.stderr
    assert not (_shared(repo) / "claims" / f"{item}.json").exists()
    assert not (_shared(repo) / "claims" / f"{third}.json").exists()
    sha = _evidence(repo, env, f"did {dep}")
    _ok(["done", dep, "--evidence", sha, "--session", "A"], env, repo)
    _ok(["claim", item, "--session", "A"], env, repo)


def test_ensure_decision_items_skips_an_entry_that_raises_and_keeps_the_rest(
    tmp_path, api, monkeypatch
):
    work, env = api
    repo = _store(tmp_path, env)
    real = work._ensure_decision_locked

    def flaky(root, block, msg_digest, session):
        if block == BLOCK_2:
            raise OSError("disk full")
        return real(root, block, msg_digest, session)

    monkeypatch.setattr(work, "_ensure_decision_locked", flaky)
    ids = work.ensure_decision_items(repo, [(BLOCK, "d1", "S1"), (BLOCK_2, "d2", "S1")])
    assert ids is not None and len(ids) == 1
    assert _item_file(repo, ids[0]).is_file()
    assert _item(repo, ids[0])["msg_digests"] == ["d1"]


def _closing_setup(tmp_path: Path, env: dict[str, str]) -> tuple[Path, str, str]:
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _ok(["claim", item, "--session", "A"], env, repo)
    sha = _evidence(repo, env, f"did {item}")
    return repo, item, sha


def test_a_failed_marker_write_leaves_the_item_open_and_the_claim_live(tmp_path, api, monkeypatch):
    work, env = api
    repo, item, sha = _closing_setup(tmp_path, env)
    before = _item_file(repo, item).read_bytes()

    def boom(*a, **k):
        raise OSError("marker write failed")

    monkeypatch.setattr(work, "_write_marker", boom)
    code = work.main(["--repo", str(repo), "done", item, "--evidence", sha, "--session", "A"])
    assert code != 0
    assert _item_file(repo, item).read_bytes() == before
    assert _claim(repo, item)["lease_s"] > 0


def test_a_failed_item_write_removes_the_marker_and_keeps_the_claim_live(
    tmp_path, api, monkeypatch
):
    work, env = api
    repo, item, sha = _closing_setup(tmp_path, env)
    before = _item_file(repo, item).read_bytes()

    def boom(*a, **k):
        raise OSError("item write failed")

    monkeypatch.setattr(work, "_write_item", boom)
    code = work.main(["--repo", str(repo), "done", item, "--evidence", sha, "--session", "A"])
    assert code != 0
    assert _item_file(repo, item).read_bytes() == before
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()
    assert _claim(repo, item)["lease_s"] > 0


def test_evidence_must_name_the_id_as_a_whole_token(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    for msg in (f"feat: {item}5 is something else", f"feat: x{item} is not it"):
        sha = _evidence(repo, env, msg)
        r = run(["done", item, "--evidence", sha], env, repo)
        assert r.returncode != 0, msg
    sha = _evidence(repo, env, f"feat: closes {item}.")
    _ok(["done", item, "--evidence", sha], env, repo)


# ── review pass 2 ────────────────────────────────────────────────────────────────────────────


def test_answer_is_fenced_by_another_sessions_live_claim(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    item = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m1", session="s1")
    claims = _shared(repo) / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    claim = {"agent": "", "at": time.time(), "lease_s": 7200, "session": "s1", "token": 1}
    (claims / f"{item}.json").write_text(json.dumps(claim), encoding="utf-8")
    before = _item_file(repo, item).read_bytes()
    r = run(["answer", item, "--note", "yes"], _as(env, session="s2"), repo)
    assert r.returncode != 0 and "token" in r.stderr and "s1" in r.stderr, r.stderr
    assert _item_file(repo, item).read_bytes() == before
    assert _claim(repo, item) == claim
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()
    _ok(["answer", item, "--note", "yes"], _as(env, session="s1"), repo)
    assert _item(repo, item)["status"] == "done"


def _residue_marker(repo: Path, item: str, tree: Path) -> Path:
    closed = _shared(repo) / "closed"
    closed.mkdir(parents=True, exist_ok=True)
    marker = closed / f"{item}.json"
    marker.write_text(
        json.dumps({"at": time.time(), "id": item, "status": "done", "tree": str(tree)}),
        encoding="utf-8",
    )
    return marker


def test_a_marker_from_this_tree_over_an_open_item_is_crash_residue(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    a = _add(repo, env, title="a")
    b = _add(repo, env, title="b")
    marker = _residue_marker(repo, a, repo)
    assert a in _ready_ids(repo, env)
    _ok(["claim", a, "--session", "S"], env, repo)
    assert not marker.exists()
    marker = _residue_marker(repo, b, repo)
    sha = _evidence(repo, env, f"did {b}")
    _ok(["done", b, "--evidence", sha, "--session", "S"], env, repo)
    assert _item(repo, b)["status"] == "done"
    # a marker another tree wrote still means closed elsewhere
    c = _add(repo, env, title="c")
    _residue_marker(repo, c, tmp_path / "elsewhere")
    r = run(["claim", c, "--session", "S"], env, repo)
    assert r.returncode != 0 and "another working tree" in r.stderr


def test_without_a_recorded_base_branch_no_marker_is_ever_pruned(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha = _evidence(wt, env, f"close {item}")
    _ok(["done", item, "--evidence", sha, "--session", "W"], env, wt)
    _commit_store(wt, env, "close")
    cfg_path = repo / ".fabrik" / "work" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    del cfg["base_branch"]
    cfg_path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _git(repo, env, "checkout", "-q", "-b", "side")
    _git(repo, env, "merge", "-q", "--no-ff", "-m", "merge wt into side", "wt")
    assert _item(repo, item)["status"] == "done"
    _add(repo, env, title="a locked write")
    assert (_shared(repo) / "closed" / f"{item}.json").exists()


def test_an_item_id_is_named_only_between_non_word_characters(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    a = _add(repo, env, title="a")
    sha = _evidence(repo, env, f"feat: {a}_x is another token")
    assert run(["done", a, "--evidence", sha], env, repo).returncode != 0
    sha = _evidence(repo, env, f"feat: x_{a} is another token")
    assert run(["done", a, "--evidence", sha], env, repo).returncode != 0
    sha = _evidence(repo, env, f"feat: closes ({a})")
    _ok(["done", a, "--evidence", sha], env, repo)
    b = _add(repo, env, title="b")
    sha = _evidence(repo, env, f"feat: closes {b}.")
    _ok(["done", b, "--evidence", sha], env, repo)
