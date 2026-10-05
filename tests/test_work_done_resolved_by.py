# AFTER-EDIT: scripts/work.py, docs/reference/work-tracking.md
"""`work.py done <id> --resolved-by <other>` — closing an item another item's commit fixed.

`done` accepts only a commit whose message names the item being closed, and `drop --duplicate-of` takes
awaiting-operator items only. So an OPEN item fixed by another item's commit could be closed only by an empty
commit naming it, which satisfies the evidence rule without the outcome (trade-intelligence mail 01M3T2C7,
W-f154f3f3). `--resolved-by` accepts a commit that names the CITED item, provided that item is itself closed
done, and writes `resolved_by` on the record and the closed marker. Every test runs against throwaway git repos
under tmp_path.
"""

from __future__ import annotations

import json

from tests.test_work_claims import (
    _add,
    _commit_store,
    _env,
    _evidence,
    _git,
    _item,
    _item_file,
    _ok,
    _shared,
    _store,
    _worktree,
    run,
)


def _two(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    a = _add(repo, env, title="A")
    b = _add(repo, env, title="B")
    return env, repo, a, b


def _done(tree, env, item, session="S"):
    sha = _evidence(tree, env, f"fix: the shared cause ({item})")
    _ok(["done", item, "--evidence", sha, "--session", session], env, tree)
    return sha


def test_resolved_by_closes_an_item_fixed_under_another_items_commit(tmp_path):
    env, repo, a, b = _two(tmp_path)
    sha = _done(repo, env, a)
    _ok(["done", b, "--resolved-by", a, "--session", "S"], env, repo)
    rec = _item(repo, b)
    assert rec["status"] == "done" and rec["evidence"] == sha and rec["resolved_by"] == a
    marker = json.loads((_shared(repo) / "closed" / f"{b}.json").read_text(encoding="utf-8"))
    assert marker["status"] == "done" and marker["evidence"] == sha
    plain = json.loads((_shared(repo) / "closed" / f"{a}.json").read_text(encoding="utf-8"))
    assert "resolved_by" not in plain, "a plain done's marker carries no resolved_by key"
    # without the flag, today's rule stands: a commit naming only A does not close B
    c = _add(repo, env, title="C")
    r = run(["done", c, "--evidence", sha, "--session", "S"], env, repo)
    assert r.returncode == 1 and c in r.stderr and "resolved_by" not in _item(repo, c)


def test_resolved_by_refuses_unless_the_cited_item_is_done(tmp_path):
    env, repo, a, b = _two(tmp_path)
    before = _item_file(repo, b).read_bytes()
    r = run(["done", b, "--resolved-by", a, "--session", "S"], env, repo)
    assert r.returncode == 1 and a in r.stderr and "not done" in r.stderr, r.stderr
    _ok(["drop", a, "--why", "not needed"], env, repo)
    r = run(["done", b, "--resolved-by", a, "--session", "S"], env, repo)
    assert r.returncode == 1 and a in r.stderr and "not done" in r.stderr, r.stderr
    assert _item_file(repo, b).read_bytes() == before
    # a done item that records no evidence (an answered decision, a legacy row) carries no fix
    c = _add(repo, env, title="C")
    p = _item_file(repo, c)
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec.update(status="done", evidence="")
    p.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    r = run(["done", b, "--resolved-by", c, "--session", "S"], env, repo)
    assert r.returncode == 1 and "no evidence" in r.stderr, r.stderr
    assert _item_file(repo, b).read_bytes() == before


def test_resolved_by_refuses_evidence_other_than_the_cited_items(tmp_path):
    env, repo, a, b = _two(tmp_path)
    sha = _done(repo, env, a)
    later = _evidence(repo, env, f"re {a}: a later empty-ish commit")
    r = run(["done", b, "--resolved-by", a, "--evidence", later, "--session", "S"], env, repo)
    assert r.returncode == 1 and sha[:12] in r.stderr, r.stderr
    assert _item(repo, b)["status"] == "open"
    # A's stored evidence is canonicalised before it is compared or carried
    p = _item_file(repo, a)
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["evidence"] = sha.upper()
    p.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    _ok(["done", b, "--resolved-by", a, "--evidence", sha, "--session", "S"], env, repo)
    assert _item(repo, b)["evidence"] == sha
    # recorded evidence that is a ref, not a SHA, is refused: it would re-resolve later
    _git(repo, env, "branch", "moving-ref", sha)
    rec["evidence"] = "moving-ref"
    p.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    c = _add(repo, env, title="C")
    r = run(["done", c, "--resolved-by", a, "--session", "S"], env, repo)
    assert r.returncode == 1 and "not a commit SHA" in r.stderr, r.stderr


def test_resolved_by_refuses_self_and_unknown_ids(tmp_path):
    env, repo, a, b = _two(tmp_path)
    _done(repo, env, a)
    for cited, why in ((b, "itself"), ("W-00000000", "not done"), ("W-xyz", "not an item id")):
        r = run(["done", b, "--resolved-by", cited, "--session", "S"], env, repo)
        assert r.returncode == 1 and why in r.stderr, (cited, r.stderr)
    assert _item(repo, b)["status"] == "open"


def test_resolved_by_reads_a_marker_or_base_branch_closed_item_as_done(tmp_path):
    env, repo, a, b = _two(tmp_path)
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    # marker shape: A closed in the worktree; the main checkout's copy still reads open
    sha = _done(wt, env, a, session="W")
    assert _item(repo, a)["status"] == "open"
    _ok(["done", b, "--resolved-by", a, "--session", "M"], env, repo)
    assert _item(repo, b)["evidence"] == sha
    # base-branch shape: C is created and closed on main AFTER the worktree branched
    c = _add(repo, env, title="C")
    sha_c = _done(repo, env, c)
    _commit_store(repo, env, "close C")
    d = _add(wt, env, title="D")
    assert not _item_file(wt, c).exists()
    _ok(["done", d, "--resolved-by", c, "--session", "W"], env, wt)
    assert _item(wt, d)["evidence"] == sha_c and _item(wt, d)["resolved_by"] == c


def test_resolved_by_records_the_root_of_a_chain(tmp_path):
    env, repo, a, b = _two(tmp_path)
    sha = _done(repo, env, a)
    _ok(["done", b, "--resolved-by", a, "--session", "S"], env, repo)
    c = _add(repo, env, title="C")
    _ok(["done", c, "--resolved-by", b, "--session", "S"], env, repo)
    assert _item(repo, c)["resolved_by"] == a and _item(repo, c)["evidence"] == sha
    # the same chain seen through a closed marker: E is closed in a worktree, so the main
    # checkout reads E only from its marker, which must carry the root
    d, e, f = (_add(repo, env, title=t) for t in ("D", "E", "F"))
    _commit_store(repo, env)
    wt = _worktree(repo, env)
    sha_d = _done(wt, env, d, session="W")
    _ok(["done", e, "--resolved-by", d, "--session", "W"], env, wt)
    assert _item(repo, e)["status"] == "open"
    _ok(["done", f, "--resolved-by", e, "--session", "M"], env, repo)
    assert _item(repo, f)["resolved_by"] == d and _item(repo, f)["evidence"] == sha_d


def test_a_resolved_by_item_is_not_class_6_drift(tmp_path):
    env, repo, a, b = _two(tmp_path)
    _done(repo, env, a)
    _ok(["done", b, "--resolved-by", a, "--session", "S"], env, repo)
    _commit_store(repo, env, "close A and B")
    out = run(["status"], env, repo)
    assert "DRIFT 6" not in out.stdout + out.stderr, out.stdout
    # a hand-written resolved_by that names a different item still reads class 6
    p = _item_file(repo, b)
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["resolved_by"] = "W-00000000"
    p.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    _commit_store(repo, env, "tamper")
    out = run(["status"], env, repo)
    assert "DRIFT 6" in out.stdout + out.stderr and b in out.stdout + out.stderr, out.stdout
