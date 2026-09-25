"""Behavior contract for linked items and duplicate retirement (plan 2026-09-25-plan-1, ticket T01).

``mail`` and ``feedback`` items are made and closed only through ``open_linked``/``close_linked``
(never ``add``, never a hand ``done``) and are exempt from drift class 6; ``drop <id>
--duplicate-of <keep>`` retires a duplicate awaiting question into the item that keeps it. Every
test runs against a throwaway git repo under ``tmp_path`` with an explicit ``env=`` — never the
hub's own store.
"""

from __future__ import annotations

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
BLOCK_2 = BLOCK.replace("production now?", "production today?")
MAIL = ("mail", "01MAILID")


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }


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


def run(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = run(args, env, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _store(tmp_path: Path, env: dict[str, str], distributor: str = "intel") -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    repo = work.resolve()
    _ok(["init", "--distributor", distributor], env, repo)
    return repo


def _shared(repo: Path) -> Path:
    return repo / ".git" / "fabrik-work"


def _item_file(repo: Path, item_id: str) -> Path:
    return repo / ".fabrik" / "work" / f"{item_id}.json"


def _item(repo: Path, item_id: str) -> dict:
    return json.loads(_item_file(repo, item_id).read_text(encoding="utf-8"))


def _items(repo: Path) -> dict[str, dict]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((repo / ".fabrik" / "work").glob("W-*.json"))
    }


def _claim(repo: Path, item_id: str) -> dict:
    return json.loads((_shared(repo) / "claims" / f"{item_id}.json").read_text(encoding="utf-8"))


def _snapshot(repo: Path) -> dict[str, bytes]:
    snap: dict[str, bytes] = {}
    for root in (repo / ".fabrik", _shared(repo)):
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file() and p.name not in ("readings.jsonl", ".lock"):
                    snap[str(p)] = p.read_bytes()
    return snap


def _edit(repo: Path, item_id: str, **fields: object) -> None:
    p = _item_file(repo, item_id)
    data = json.loads(p.read_text(encoding="utf-8"))
    data.update(fields)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture
def api(tmp_path, monkeypatch):
    """(module, env) with the process environment made hermetic for in-process API calls."""
    env = _env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    return _work_module(), env


def _two_awaiting(work: ModuleType, repo: Path, monkeypatch, agent: str = "infra"):
    """Two open awaiting items, A (BLOCK) and B (BLOCK_2), both created by ``agent``."""
    monkeypatch.setenv("CLAUDE_AGENT", agent)
    a = work.ensure_decision_item(repo, block=BLOCK, msg_digest="m1", session="S1")
    b = work.ensure_decision_item(repo, block=BLOCK_2, msg_digest="m2", session="S1")
    monkeypatch.delenv("CLAUDE_AGENT")
    assert a and b and a != b
    return a, b


# ── row 1: no hand-made mail / feedback / next items; the standing links stay three ──────────


def test_add_refuses_mail_feedback_and_next_and_links_stay_three(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    before = _snapshot(repo)
    for kind in ("mail", "feedback", "next"):
        r = run(["add", "--kind", kind, "--title", "x"], env, repo)
        assert r.returncode == 1, (kind, r.stderr)
        assert f"--kind {kind}" in r.stderr, r.stderr
        assert _snapshot(repo) == before, kind
    out = _ok(["add", "--kind", "task", "--title", "t", "--link", "spec=docs/s.md"], env, repo)
    item = _item(repo, Path(out.strip().splitlines()[-1]).stem)
    assert item["links"] == {"decision": "", "plan": "", "spec": "docs/s.md"}
    r = run(["add", "--kind", "task", "--title", "t", "--link", "mail=01X"], env, repo)
    assert r.returncode != 0


# ── row 2: open_linked is idempotent per link and claims for the calling session ─────────────


def test_open_linked_makes_one_item_per_link_and_claims_it_for_the_session(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    first = work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S1")
    assert first
    again = work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S1")
    assert again == first
    items = _items(repo)
    assert list(items) == [first]
    item = items[first]
    assert item["kind"] == "mail" and item["status"] == "open"
    assert item["links"]["mail"] == "01MAILID" and item["title"] == "subject"
    claim = _claim(repo, first)
    assert claim["session"] == "S1" and claim["token"] == 1 and claim["lease_s"] > 0
    # another session's call finds the same item and leaves the live claim with its holder
    assert work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S2") == first
    assert _claim(repo, first)["session"] == "S1"
    assert len(_items(repo)) == 1
    with pytest.raises(ValueError):
        work.open_linked(repo, kind="task", link=MAIL, title="x", session="S1")


# ── row 3: close_linked closes, ends the claim, and drift class 6 exempts the kind ───────────


def test_close_linked_closes_the_item_ends_its_claim_and_class_6_exempts_it(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    item_id = work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S1")
    got = work.close_linked(repo, kind="mail", link=MAIL, status="done", note="mail ack: fixed")
    assert got == item_id
    item = _item(repo, item_id)
    assert item["status"] == "done" and item["note"] == "mail ack: fixed"
    assert _claim(repo, item_id)["lease_s"] == 0
    assert (_shared(repo) / "closed" / f"{item_id}.json").exists()
    fb = work.open_linked(
        repo, kind="feedback", link=("command", "fabrik-review"), title="q", session="S1"
    )
    work.close_linked(
        repo, kind="feedback", link=("command", "fabrik-review"), status="done", note="abc123"
    )
    assert _item(repo, fb)["status"] == "done"
    out = run(["sync", "--check"], env, repo).stdout
    drift6 = [ln for ln in out.splitlines() if ln.startswith("DRIFT 6 (")]
    assert not any(item_id in ln or fb in ln for ln in drift6), out


# ── row 4: no open item → nothing; a hand `done` on a mail item is refused ───────────────────


def test_close_linked_without_an_item_writes_nothing_and_done_refuses_mail(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    before = _snapshot(repo)
    assert work.close_linked(repo, kind="mail", link=MAIL, status="done", note="n") is None
    assert _snapshot(repo) == before
    item_id = work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S1")
    (repo / "w.txt").write_text("w\n", encoding="utf-8")
    _git(repo, env, "add", "w.txt")
    _git(repo, env, "commit", "-q", "-m", f"work for {item_id}")
    sha = _git(repo, env, "rev-parse", "HEAD").strip()
    raw = _item_file(repo, item_id).read_bytes()
    r = run(["done", item_id, "--evidence", sha, "--session", "S1"], env, repo)
    assert r.returncode == 1
    assert f"done {item_id} refused: a mail item closes when its mail is acked" in r.stderr
    assert _item_file(repo, item_id).read_bytes() == raw


# ── row 5: drop A --duplicate-of B ────────────────────────────────────────────────────────────


def test_drop_duplicate_of_retires_a_into_b(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env)
    a, b = _two_awaiting(work, repo, monkeypatch)
    a_digest = _item(repo, a)["block_digest"]
    _ok(["drop", a, "--duplicate-of", b], _as(env, agent="infra"), repo)
    got_a, got_b = _item(repo, a), _item(repo, b)
    assert got_a["status"] == "dropped" and got_a["note"] == f"duplicate of {b}"
    assert got_b["status"] == "awaiting-operator"
    assert got_b["alt_block_digests"] == [a_digest]
    assert got_b["alt_ids"] == [a]
    lines = work.prompt_block(repo, "S9").splitlines()
    b_line = next(ln for ln in lines if b in ln)
    assert b_line.endswith(f"(also asked as {a})"), b_line
    assert not any(a in ln and b not in ln for ln in lines)


# ── row 6: a later re-ask of the retired wording refreshes the kept item ─────────────────────


def test_a_reask_of_the_retired_wording_refreshes_the_kept_item(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env)
    a, b = _two_awaiting(work, repo, monkeypatch)
    _ok(["drop", a, "--duplicate-of", b, "--why", "same ask"], _as(env, agent="infra"), repo)
    assert _item(repo, a)["note"] == f"duplicate of {b} — same ask"
    count = len(_items(repo))
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="m3", session="S2") == b
    assert "m3" in _item(repo, b)["msg_digests"]
    assert len(_items(repo)) == count


# ── row 7: who may retire, and what stays refused ─────────────────────────────────────────────


def test_drop_duplicate_of_refuses_the_unauthorised_and_the_degenerate(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env, distributor="intel")
    a, b = _two_awaiting(work, repo, monkeypatch, agent="infra")
    before = _snapshot(repo)
    r = run(["drop", a, "--duplicate-of", b], _as(env, agent="fleet"), repo)
    assert r.returncode == 1 and "duplicate-of" in r.stderr, r.stderr
    assert _snapshot(repo) == before
    r = run(["drop", a, "--duplicate-of", a], _as(env, agent="intel"), repo)
    assert r.returncode == 1 and "itself" in r.stderr, r.stderr
    r = run(["drop", a, "--why", "x"], _as(env, agent="intel"), repo)
    assert r.returncode == 1 and "answer" in r.stderr, r.stderr
    r = run(["drop", a], _as(env, agent="intel"), repo)
    assert r.returncode == 1 and "--why" in r.stderr, r.stderr
    assert _snapshot(repo) == before
    # an empty identity never matches an empty creator
    _edit(repo, a, creator="")
    _edit(repo, b, creator="")
    before = _snapshot(repo)
    r = run(["drop", a, "--duplicate-of", b], _as(env), repo)
    assert r.returncode == 1, r.stderr
    assert _snapshot(repo) == before
    # a keep that is not an open awaiting item is refused naming it
    plain = Path(_ok(["add", "--kind", "task", "--title", "p"], env, repo).split()[-1]).stem
    r = run(["drop", a, "--duplicate-of", plain], _as(env, agent="intel"), repo)
    assert r.returncode == 1 and plain in r.stderr, r.stderr
    # the distributor may retire it
    _ok(["drop", a, "--duplicate-of", b], _as(env, agent="intel"), repo)
    assert _item(repo, a)["status"] == "dropped"


# ── review pass 1 ─────────────────────────────────────────────────────────────────────────────


def _awaiting_by(work: ModuleType, repo: Path, monkeypatch, block: str, digest: str, agent: str):
    monkeypatch.setenv("CLAUDE_AGENT", agent)
    got = work.ensure_decision_item(repo, block=block, msg_digest=digest, session="S1")
    monkeypatch.delenv("CLAUDE_AGENT")
    assert got
    return got


def _marker(repo: Path, item_id: str, tree: Path) -> None:
    closed = _shared(repo) / "closed"
    closed.mkdir(parents=True, exist_ok=True)
    marker = {"at": time.time(), "id": item_id, "status": "done", "tree": str(tree)}
    (closed / f"{item_id}.json").write_text(json.dumps(marker), encoding="utf-8")


def test_a_failed_duplicate_close_restores_the_kept_item(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env)
    a, b = _two_awaiting(work, repo, monkeypatch)
    pre = _item_file(repo, b).read_bytes()
    real_write = work._write_item

    def fail_the_duplicate(repo_arg, item, *args, **kwargs):
        if item.get("id") == a:  # only the write inside _close; keep's own write succeeds
            raise OSError("disk full")
        return real_write(repo_arg, item, *args, **kwargs)

    monkeypatch.setattr(work, "_write_item", fail_the_duplicate)
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    assert work.main(["--repo", str(repo), "drop", a, "--duplicate-of", b]) == 1
    monkeypatch.delenv("CLAUDE_AGENT")
    assert _item(repo, a)["status"] == "awaiting-operator"
    assert _item_file(repo, b).read_bytes() == pre
    assert work.prompt_block(repo, "S9").count(a) == 1


def test_a_duplicate_already_closed_keeps_the_kept_items_record(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env)
    a, b = _two_awaiting(work, repo, monkeypatch)
    a_digest = _item(repo, a)["block_digest"]

    def boom(*_args, **_kwargs):
        raise OSError("claims dir gone")

    monkeypatch.setattr(work, "_end_claim", boom)  # _close's LAST step, after A is written
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    assert work.main(["--repo", str(repo), "drop", a, "--duplicate-of", b]) == 1
    monkeypatch.delenv("CLAUDE_AGENT")
    assert _item(repo, a)["status"] == "dropped"
    kept = _item(repo, b)
    assert a_digest in kept["alt_block_digests"]
    assert a in kept["alt_ids"] and "m1" in kept["msg_digests"]
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="m9", session="S1") == b


def test_close_linked_keeps_going_past_a_failed_item(tmp_path, api, monkeypatch, capsys):
    work, env = api
    repo = _store(tmp_path, env)
    first = work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S1")
    twin_id = "W-fffffff2"
    assert twin_id > first
    twin = dict(_item(repo, first), id=twin_id)
    _item_file(repo, twin_id).write_text(json.dumps(twin), encoding="utf-8")
    real_write = work._write_item

    def fail_the_twin(repo_arg, item, *args, **kwargs):
        if item.get("id") == twin_id:
            raise OSError("disk full")
        return real_write(repo_arg, item, *args, **kwargs)

    monkeypatch.setattr(work, "_write_item", fail_the_twin)
    capsys.readouterr()
    got = work.close_linked(repo, kind="mail", link=MAIL, status="done", note="acked")
    err = capsys.readouterr().err
    assert got == first
    assert _item(repo, first)["status"] == "done"
    assert _item(repo, twin_id)["status"] == "open"
    assert [ln for ln in err.splitlines() if twin_id in ln] and err.count(twin_id) == 1, err


def test_a_reharvest_of_the_dropped_items_own_message_resolves_to_the_kept_item(
    tmp_path, api, monkeypatch
):
    work, env = api
    repo = _store(tmp_path, env)
    a, b = _two_awaiting(work, repo, monkeypatch)
    _ok(["drop", a, "--duplicate-of", b], _as(env, agent="infra"), repo)
    assert "m1" in _item(repo, b)["msg_digests"]
    assert work.ensure_decision_item(repo, block=BLOCK, msg_digest="m1", session="S1") == b
    # whatever the id order: a dropped holder of a digest yields to the live item carrying it
    live = _item(repo, b)
    for item_id, fields in (
        ("W-00000001", {"status": "dropped", "msg_digests": ["mx"]}),
        ("W-fffffff1", {"status": "awaiting-operator", "msg_digests": ["mx"]}),
    ):
        data = dict(live, id=item_id, alt_ids=[], alt_block_digests=[], **fields)
        _item_file(repo, item_id).write_text(json.dumps(data), encoding="utf-8")
    got = work.ensure_decision_item(repo, block=BLOCK_2, msg_digest="mx", session="S1")
    assert got == "W-fffffff1"


def test_close_linked_closes_every_open_item_of_the_link(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    first = work.open_linked(repo, kind="mail", link=MAIL, title="subject", session="S1")
    twin = dict(_item(repo, first), id="W-0000abcd")
    _item_file(repo, "W-0000abcd").write_text(json.dumps(twin), encoding="utf-8")
    got = work.close_linked(repo, kind="mail", link=MAIL, status="done", note="acked")
    assert got in (first, "W-0000abcd")
    assert _item(repo, first)["status"] == "done"
    assert _item(repo, "W-0000abcd")["status"] == "done"


def test_drop_duplicate_of_needs_the_creator_of_both_not_either(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env, distributor="intel")
    a = _awaiting_by(work, repo, monkeypatch, BLOCK, "m1", "infra")
    b = _awaiting_by(work, repo, monkeypatch, BLOCK_2, "m2", "fleet")
    before = _snapshot(repo)
    r = run(["drop", a, "--duplicate-of", b], _as(env, agent="infra"), repo)
    assert r.returncode == 1 and "creator" in r.stderr, r.stderr
    assert _snapshot(repo) == before


def test_drop_duplicate_of_is_fenced_and_refuses_a_keep_closed_elsewhere(
    tmp_path, api, monkeypatch
):
    work, env = api
    repo = _store(tmp_path, env)
    a, b = _two_awaiting(work, repo, monkeypatch)
    claims = _shared(repo) / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    held = {"agent": "", "at": time.time(), "lease_s": 7200, "session": "S9", "token": 1}
    (claims / f"{a}.json").write_text(json.dumps(held), encoding="utf-8")
    before = _snapshot(repo)
    r = run(["drop", a, "--duplicate-of", b], _as(env, agent="infra", session="S1"), repo)
    assert r.returncode == 1 and "token mismatch" in r.stderr, r.stderr
    assert _snapshot(repo) == before
    (claims / f"{a}.json").unlink()
    elsewhere = tmp_path / "elsewhere"
    _marker(repo, b, elsewhere)
    before = _snapshot(repo)
    r = run(["drop", a, "--duplicate-of", b], _as(env, agent="infra", session="S1"), repo)
    assert r.returncode == 1 and str(elsewhere) in r.stderr, r.stderr
    assert _snapshot(repo) == before


def test_open_linked_reuses_only_an_open_item_and_takes_the_next_token(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    first = work.open_linked(repo, kind="mail", link=MAIL, title="s", session="S1")
    work.close_linked(repo, kind="mail", link=MAIL, status="done", note="acked")
    (_shared(repo) / "closed" / f"{first}.json").unlink()  # the item's own status must decide
    second = work.open_linked(repo, kind="mail", link=MAIL, title="s", session="S1")
    assert second and second != first
    _marker(repo, second, tmp_path / "elsewhere")
    third = work.open_linked(repo, kind="mail", link=MAIL, title="s", session="S1")
    assert third and third not in (first, second)
    token = _claim(repo, third)["token"]
    ended = dict(_claim(repo, third), lease_s=0)
    (_shared(repo) / "claims" / f"{third}.json").write_text(json.dumps(ended), encoding="utf-8")
    assert work.open_linked(repo, kind="mail", link=MAIL, title="s", session="S2") == third
    got = _claim(repo, third)
    assert got["session"] == "S2" and got["token"] == token + 1
