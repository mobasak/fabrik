"""Behavior contract for the durable close ledger (W-5d7edd47, for W-04238176's control metric).

Every close (``done``/``drop``/``answer``) appends one row to ``<git common dir>/fabrik-work/
closed.jsonl``. Unlike the closed marker, the row is never pruned once the base branch reads the item
resolved, so a close's time, session and agent outlive the merge. Throwaway git repos under
``tmp_path`` only — never the hub's own store.
"""

from __future__ import annotations

import json

import pytest

from tests.test_work_claims import (
    BLOCK,
    _add,
    _commit_store,
    _digest,
    _env,
    _evidence,
    _git,
    _ok,
    _shared,
    _store,
    _work_module,
    _worktree,
    run,
)

ROW_KEYS = {"agent", "at", "id", "session", "status", "tree"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    """(module, env) with the process environment made hermetic for in-process API calls."""
    env = _env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    return _work_module(), env


def _rows(repo):
    path = _shared(repo) / "closed.jsonl"
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_every_closing_verb_appends_one_row(tmp_path, api):
    work, env = api
    repo = _store(tmp_path, env)
    decisions = repo / "docs" / "DECISIONS.md"
    decisions.parent.mkdir()
    decisions.write_text("| D-001 | x |\n", encoding="utf-8")
    done_id, drop_id = _add(repo, env, "to finish"), _add(repo, env, "to drop")
    asked = work.ensure_decision_item(repo, block=BLOCK, msg_digest=_digest("m"), session="S1")
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha = _evidence(wt, env, f"feat: the thing ({done_id})")
    _ok(["done", done_id, "--evidence", sha, "--session", "W1"], {**env, "CLAUDE_AGENT": "intel"}, wt)
    _ok(["drop", drop_id, "--why", "not needed"], env, repo)
    _ok(["answer", asked, "--note", "ship it", "--decision", "D-001"], env, repo)

    rows = _rows(repo)
    assert [(r["id"], r["status"]) for r in rows] == [
        (done_id, "done"),
        (drop_id, "dropped"),
        (asked, "done"),
    ]
    assert all(set(r) == ROW_KEYS for r in rows), rows
    first = rows[0]
    # the linked worktree's close lands in the ONE common-dir ledger, naming that tree
    assert first["session"] == "W1" and first["agent"] == "intel"
    assert first["tree"] == str(wt)
    assert isinstance(first["at"], float) and first["at"] > 0
    assert not (wt / ".git").is_dir()  # a linked worktree: no ledger of its own


def test_the_row_outlives_the_pruned_marker(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha = _evidence(wt, env, f"close {item}")
    _ok(["done", item, "--evidence", sha, "--session", "W"], env, wt)
    _commit_store(wt, env, "close it")
    _git(repo, env, "merge", "-q", "--no-ff", "-m", "merge wt", "wt")
    _add(repo, env, title="any write")  # the locked write that prunes the marker
    assert not (_shared(repo) / "closed" / f"{item}.json").exists()
    assert [(r["id"], r["session"]) for r in _rows(repo)] == [(item, "W")]


def test_a_failed_close_appends_no_row(tmp_path, api, monkeypatch):
    work, env = api
    repo = _store(tmp_path, env)
    item_id = _add(repo, env)
    item = json.loads((repo / ".fabrik" / "work" / f"{item_id}.json").read_text(encoding="utf-8"))
    item["status"] = "dropped"

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(work, "_write_item", _boom)
    with pytest.raises(OSError):
        work._close(repo, item, session="S", note="x")
    assert _rows(repo) == []
    assert not (_shared(repo) / "closed" / f"{item_id}.json").exists()


def test_an_unwritable_ledger_warns_and_the_close_stands(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env)
    (_shared(repo) / "closed.jsonl").mkdir(parents=True)  # a directory: every append fails
    r = run(["drop", item, "--why", "gone"], env, repo)
    assert r.returncode == 0, r.stderr
    assert "close ledger" in r.stderr, r.stderr
    status = json.loads((repo / ".fabrik" / "work" / f"{item}.json").read_text(encoding="utf-8"))
    assert status["status"] == "dropped"
