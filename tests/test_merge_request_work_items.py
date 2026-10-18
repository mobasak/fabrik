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
