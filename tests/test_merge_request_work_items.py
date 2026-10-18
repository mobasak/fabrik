"""W-5f3617e6: `merge_request.py merge` refused a branch on a `.fabrik/work/W-*.json` conflict
whenever the coordinator scored an item on master after its builder closed it on the branch.

Root cause (the coordinator's diff of W-27a0dc32, base ee2bd684d, master 8d500228d, branch
09b8b7c47): the two sides changed DISJOINT keys — master `effort`/`impact`/`owner`/`priority`/
`score_reason`, the branch `evidence`/`status` — but `work.py` writes one key per line in sorted
order (`_dump`), so `evidence` sits beside `effort` and `status` beside `score_reason`, and git's
line merge refuses adjacent hunks from two sides. The merge is now key-wise against the base.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_merge_request_merge import _git, world  # noqa: E402,F401 — the merge tests' own fixture

ITEM = ".fabrik/work/W-27a0dc32.json"
BASE = {
    "blocked_by": [],
    "created": "2026-10-18T05:15:11.354114Z",
    "creator": "kaizen",
    "evidence": "",
    "id": "W-27a0dc32",
    "kind": "task",
    "legacy": False,
    "links": {"decision": "", "plan": "", "spec": ""},
    "next": "Decide whether fabrik-repo-review.md:66 gets the same SCRATCH: parenthesis",
    "note": "",
    "owner": "",
    "priority": 2,
    "status": "open",
    "title": "fabrik-repo-review names no root for its pins dir",
}
SCORED = {  # the coordinator's scoring on master
    **BASE,
    "effort": "low",
    "impact": "high",
    "owner": "kaizen",
    "priority": 1,
    "score_reason": "HIGH: kaizen work (D-956)",
}
CLOSED = {  # the builder's close on the branch
    **BASE,
    "evidence": "165fed26f8831a8b92c1a9819cb84703f4726519",
    "status": "done",
}


def _dump(data: dict) -> str:
    """`work.py::_dump` — the store's own byte format."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _seed(world) -> None:  # noqa: F811
    """The item in the merge base: committed on master, pushed, and taken into ``feat``."""
    world.write(ITEM, _dump(BASE))
    world.commit_main("seed item", ITEM)
    _git(world.main, "push", "-q", "origin", "master")
    _git(world.wt, "merge", "-q", "--ff-only", "master")


def _merged(world) -> dict:  # noqa: F811
    return json.loads(_git(world.main, "show", f"master:{ITEM}"))


def test_disjoint_keys_on_the_two_sides_merge_clean(world):  # noqa: F811
    """The W-27a0dc32 shape: every key takes the side that changed it."""
    _seed(world)
    head = world.branch({ITEM: _dump(CLOSED)})
    world.write(ITEM, _dump(SCORED))
    world.commit_main("score item", ITEM)
    msg_id = world.send(head)

    assert world.run("merge") == 0, world.replies(msg_id)
    assert _merged(world) == {**SCORED, "evidence": CLOSED["evidence"], "status": "done"}
    parents = _git(world.main, "log", "-1", "--format=%P", "master").split()
    assert len(parents) == 2 and parents[1] == head, parents  # a real merge of the branch
    assert msg_id in _git(world.main, "log", "-1", "--format=%B", "master")
    assert _git(world.main, "show", f"master:{ITEM}") + "\n" == _dump(_merged(world))


def test_a_nested_links_key_changed_on_both_sides_merges_per_subkey(world):  # noqa: F811
    """`work.py edit` writes `links` on a branch while master writes another `links` field."""
    _seed(world)
    head = world.branch({ITEM: _dump({**CLOSED, "links": {**BASE["links"], "plan": "p.md"}})})
    world.write(ITEM, _dump({**SCORED, "links": {**BASE["links"], "spec": "s.md"}}))
    world.commit_main("score item", ITEM)
    world.send(head)

    assert world.run("merge") == 0
    assert _merged(world)["links"] == {"decision": "", "plan": "p.md", "spec": "s.md"}


def test_one_key_changed_to_different_values_refuses_naming_it(world):  # noqa: F811
    _seed(world)
    head = world.branch({ITEM: _dump({**CLOSED, "next": "branch words"})})
    world.write(ITEM, _dump({**SCORED, "next": "master words"}))
    world.commit_main("score item", ITEM)
    msg_id = world.send(head)
    before = world.base()

    assert world.run("merge") == 1
    reply = world.replies(msg_id)["fleet"]
    assert ITEM in reply and "next" in reply, reply
    assert world.base() == before


def test_a_key_deleted_on_one_side_and_changed_on_the_other_refuses(world):  # noqa: F811
    _seed(world)
    branch_item = {k: v for k, v in CLOSED.items() if k != "note"}
    head = world.branch({ITEM: _dump(branch_item)})
    world.write(ITEM, _dump({**SCORED, "note": "master note"}))
    world.commit_main("score item", ITEM)
    msg_id = world.send(head)

    assert world.run("merge") == 1
    reply = world.replies(msg_id)["fleet"]
    assert ITEM in reply and "note" in reply, reply


def test_the_same_change_on_both_sides_merges_clean(world):  # noqa: F811
    _seed(world)
    head = world.branch({ITEM: _dump({**CLOSED, "owner": "kaizen"})})
    world.write(ITEM, _dump(SCORED))
    world.commit_main("score item", ITEM)
    world.send(head)

    assert world.run("merge") == 0
    assert _merged(world)["owner"] == "kaizen" and _merged(world)["status"] == "done"


def _merge_item_cli(tmp_path, base: str, ours: str, theirs: str):
    """`work.py merge-item` run directly on three files (git's %O %A %B shape)."""
    paths = []
    for name, text in (("base", base), ("ours", ours), ("theirs", theirs)):
        p = tmp_path / f"{name}.json"
        p.write_text(text, encoding="utf-8")
        paths.append(str(p))
    repo = Path(__file__).resolve().parent.parent
    res = subprocess.run(
        [sys.executable, str(repo / "scripts" / "work.py"), "merge-item", *paths],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return res, Path(paths[1])


def test_the_verb_merges_an_item_both_sides_added_against_an_empty_base(tmp_path):
    res, ours = _merge_item_cli(tmp_path, "", _dump(BASE), _dump({**BASE, "status": "done"}))
    assert res.returncode == 3 and "status" in res.stderr, res.stderr  # no base: both "changed" it
    res, ours = _merge_item_cli(tmp_path, "", _dump(BASE), _dump(BASE))
    assert res.returncode == 0, res.stderr
    assert ours.read_text(encoding="utf-8") == _dump(BASE)


def test_the_verb_refuses_a_side_that_is_not_a_json_object(tmp_path):
    res, ours = _merge_item_cli(tmp_path, _dump(BASE), "[1, 2]\n", _dump(CLOSED))
    assert res.returncode == 1 and "not a JSON object" in res.stderr, res.stderr
    assert ours.read_text(encoding="utf-8") == "[1, 2]\n"


def test_the_verb_leaves_ours_untouched_on_a_conflict_and_names_the_nested_key(tmp_path):
    a = _dump({**BASE, "links": {**BASE["links"], "plan": "a.md"}})
    b = _dump({**BASE, "links": {**BASE["links"], "plan": "b.md"}})
    res, ours = _merge_item_cli(tmp_path, _dump(BASE), a, b)
    assert res.returncode == 3 and "links.plan" in res.stderr, res.stderr
    assert ours.read_text(encoding="utf-8") == a


def test_set_lists_merge_as_sets_and_appended_lists_keep_both_sides_appends(tmp_path):
    """Critique fold: `tags`/`blocked_by` are sets (base + each side's adds − each side's removes)
    and `comments` is append-only, so two sides each adding an entry never conflict."""
    base = {**BASE, "tags": ["a", "b"], "blocked_by": ["W-00000001"], "comments": [{"at": 1}]}
    ours = {**base, "tags": ["a", "x"], "blocked_by": [], "comments": [{"at": 1}, {"at": 3}]}
    theirs = {**base, "tags": ["a", "b", "y"], "comments": [{"at": 1}, {"at": 2}]}
    res, out = _merge_item_cli(tmp_path, _dump(base), _dump(ours), _dump(theirs))
    assert res.returncode == 0, res.stderr
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert merged["tags"] == ["a", "x", "y"]  # ours removed b, both kept a, each added one
    assert merged["blocked_by"] == []
    assert merged["comments"] == [{"at": 1}, {"at": 2}, {"at": 3}]  # appends ordered by `at`


def test_an_appended_list_rewritten_on_one_side_still_conflicts(tmp_path):
    base = {**BASE, "comments": [{"at": 1}]}
    ours = {**base, "comments": [{"at": 9}]}  # rewrote, not appended
    theirs = {**base, "comments": [{"at": 1}, {"at": 2}]}
    res, _ = _merge_item_cli(tmp_path, _dump(base), _dump(ours), _dump(theirs))
    assert res.returncode == 3 and "comments" in res.stderr, res.stderr


def test_a_links_object_added_on_both_sides_merges_per_sub_key(tmp_path):
    ours = {k: v for k, v in BASE.items() if k != "links"} | {"links": {"plan": "p.md"}}
    theirs = {k: v for k, v in BASE.items() if k != "links"} | {"links": {"spec": "s.md"}}
    res, _ = _merge_item_cli(tmp_path, _dump(BASE), _dump(ours), _dump(theirs))
    assert res.returncode == 3, res.stderr  # base HAS links: each side deleted two sub-keys
    assert "links.plan" in res.stderr and "links.spec" in res.stderr, res.stderr
    base = {k: v for k, v in BASE.items() if k != "links"}
    res, out = _merge_item_cli(tmp_path, _dump(base), _dump(ours), _dump(theirs))
    assert res.returncode == 0, res.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["links"] == {"plan": "p.md", "spec": "s.md"}


def test_the_verb_needs_no_git_repository(tmp_path):
    """`merge-item` reads three files; run outside any repo it still merges (git driver shape)."""
    outside = tmp_path / "outside"
    outside.mkdir()
    paths = []
    for name, data in (("base", BASE), ("ours", CLOSED), ("theirs", SCORED)):
        p = outside / f"{name}.json"
        p.write_text(_dump(data), encoding="utf-8")
        paths.append(str(p))
    work = Path(__file__).resolve().parent.parent / "scripts" / "work.py"
    res = subprocess.run(
        [sys.executable, str(work), "merge-item", *paths],
        cwd=outside,
        env={"PATH": "/usr/bin:/bin", "GIT_CEILING_DIRECTORIES": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert json.loads(Path(paths[1]).read_text(encoding="utf-8"))["owner"] == "kaizen"


def test_an_item_conflict_beside_a_plain_file_conflict_still_refuses_on_the_plain_file(world):  # noqa: F811
    _seed(world)
    head = world.branch({ITEM: _dump(CLOSED), "README.md": "branch\n"})
    world.write(ITEM, _dump(SCORED))
    world.write("README.md", "base\n")
    world.commit_main("score item and readme", ITEM, "README.md")
    msg_id = world.send(head)
    before = world.base()

    assert world.run("merge") == 1
    assert "conflict in README.md" in world.replies(msg_id)["fleet"]
    assert world.base() == before


def test_an_item_deleted_on_one_side_refuses(world):  # noqa: F811
    _seed(world)
    head = world.branch({ITEM: None})
    world.write(ITEM, _dump(SCORED))
    world.commit_main("score item", ITEM)
    msg_id = world.send(head)

    assert world.run("merge") == 1
    assert "deleted on one side" in world.replies(msg_id)["fleet"]


def test_a_store_config_conflict_is_never_merged_key_wise(world):  # noqa: F811
    cfg = ".fabrik/work/config.json"
    world.write(cfg, _dump({"distributor": "intel"}))
    world.commit_main("config", cfg)
    _git(world.main, "push", "-q", "origin", "master")
    _git(world.wt, "merge", "-q", "--ff-only", "master")
    head = world.branch({cfg: _dump({"distributor": "intel", "autonomy": True})})
    world.write(cfg, _dump({"distributor": "intel", "coordinator_mode": True}))
    world.commit_main("config main", cfg)
    msg_id = world.send(head)

    assert world.run("merge") == 1
    assert f"conflict in {cfg}" in world.replies(msg_id)["fleet"]


def test_a_merged_item_whose_id_is_not_its_file_name_is_never_staged(world):  # noqa: F811
    """Critique fold: one side rewriting `id` merges key-wise, so the result is checked against
    the file name before `git add`."""
    _seed(world)
    head = world.branch({ITEM: _dump({**CLOSED, "id": "W-ffffffff"})})
    world.write(ITEM, _dump(SCORED))
    world.commit_main("score item", ITEM)
    msg_id = world.send(head)
    before = world.base()

    assert world.run("merge") == 1
    assert "W-ffffffff" in world.replies(msg_id)["fleet"]
    assert world.base() == before


def test_an_item_both_sides_added_merges_end_to_end(world):  # noqa: F811
    """No stage 1: both sides added the same item with disjoint keys; it merges against `{}`."""
    head = world.branch({ITEM: _dump({**BASE, "status": "done"})})
    world.write(ITEM, _dump({**BASE, "owner": "kaizen"}))
    world.commit_main("add item", ITEM)
    world.send(head)

    assert world.run("merge") == 1  # `status` and `owner` differ against an empty base
    head = world.branch({ITEM: _dump({**BASE, "owner": "kaizen", "score_reason": "branch"})})
    world.send(head)

    assert world.run("merge") == 0
    assert _merged(world) == {**BASE, "owner": "kaizen", "score_reason": "branch"}


def test_the_verb_names_a_side_that_is_not_utf8(tmp_path):
    """Review pass 1 (slice A): a non-UTF-8 side escaped as a traceback; it is a named refusal."""
    sides = {
        "base": _dump(BASE).encode(),
        "ours": _dump(CLOSED).encode(),
        "theirs": b'{"id": "\xff"}\n',
    }
    paths = []
    for name, data in sides.items():
        p = tmp_path / f"{name}.json"
        p.write_bytes(data)
        paths.append(str(p))
    work = Path(__file__).resolve().parent.parent / "scripts" / "work.py"
    res = subprocess.run(
        [sys.executable, str(work), "merge-item", *paths],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert res.returncode == 1 and "theirs" in res.stderr and "is not UTF-8" in res.stderr, (
        res.stderr
    )
    assert "Traceback" not in res.stderr
