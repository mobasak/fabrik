"""The /fabrik-task lane replay (plan T02, spec § Validation V0, § The delta D12 (1)).

Reads T01's pinned fixture ONLY through ``scripts/lane_replay_capture.py::load`` (the file is
front-coded) and asks ``scripts/task_lane.py`` for every commit's verdict and every task row's
admission. The fixture's expected verdicts were produced by ``classify_commit`` at capture time, so
this pins ``classify_commit`` against the COMMITTED capture (a regression lock, not an independent
oracle); the independent graders are the hand-written rule cases in the T01 and T02 test files.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "lane_replay.json"
TASKS = ROOT / "tests" / "fixtures" / "lane_replay_tasks.json"


def _module(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        del sys.modules[name]
        raise
    return mod


def _fixture() -> dict:
    return _module("lane_replay_capture").load(FIXTURE)


def test_every_pinned_commit_verdict_matches_classify_commit():
    tl = _module("task_lane")
    fx = _fixture()
    regex = fx["header"]["sync_regex"]
    entries = fx["commits"] + fx["extras"]
    assert len(entries) > 900, len(entries)  # hub 300 + four projects + wef1
    wrong = []
    for c in entries:
        rows = [tuple(r) for r in c["rows"]]
        got = tl.classify_commit(rows, repo_kind=c["kind"], sync_regex=regex)
        if got != c["expected"]:
            wrong.append(f"{c['repo']} {c['sha'][:12]}: pinned {c['expected']!r}, got {got!r}")
    assert not wrong, f"{len(wrong)} of {len(entries)} differ:\n" + "\n".join(wrong[:30])


def test_every_verdict_class_is_exercised_by_the_fixture():
    fx = _fixture()
    seen = {c["expected"] for c in fx["commits"] + fx["extras"]}
    assert seen == set(fx["header"]["verdicts"]), seen


def _declaration(upgrade: str | None) -> tuple[dict[str, str], list[str], str | None]:
    """The task row's declaration, derived from its upgrade token (the fixture's ``_about``)."""
    declared = {
        "decision": "yes",
        "heavy": "no",
        "mechanism": "no",
        "oneway": "no",
        "tradeoffs": "no",
        "consumers": "internal",
    }
    files = ["src/feature.py", "tests/test_feature.py"]
    why = None
    if upgrade in ("tradeoffs", "oneway"):
        declared[upgrade] = "yes"
        why = "approach A vs approach B"
    elif upgrade == "files":
        files = ["src/a.py", "src/b.py", "src/c.py", "tests/test_a.py"]
    elif upgrade == "heavy":
        declared["heavy"] = "yes"
    else:
        assert upgrade is None, upgrade
    return declared, files, why


def _as_string(verdict) -> str:
    if verdict.route == "lane" and verdict.review == "full":
        return "lane: full-review"
    return verdict.route


def test_every_task_row_admits_as_pinned_at_version_2():
    tl = _module("task_lane")
    rows = json.loads(TASKS.read_text())["rows"]
    assert len(rows) == 21
    wrong, skipped = [], 0
    for row in rows:
        if row["expected"] == "not-a-lane-verdict":
            skipped += 1
            continue
        declared, files, why = _declaration(row["upgrade"])
        v = tl.admit(declared, files, sync_hits=set(), appetite=None, why=why, version=2)
        if _as_string(v) != row["expected"]:
            wrong.append(f"{row['repo']} {row['surface'][:50]}: {row['expected']!r} != {v!r}")
    assert skipped == 1
    assert not wrong, "\n".join(wrong)


def test_the_wef1_page_sample_is_refused_at_version_1_and_admitted_at_version_2():
    tl = _module("task_lane")
    rows = json.loads(TASKS.read_text())["rows"]
    (wef1,) = [r for r in rows if r["repo"] == "wef1"]
    declared, files, why = _declaration(wef1["upgrade"])
    v1 = tl.admit(declared, files, sync_hits=set(), appetite=None, why=why, version=1)
    v2 = tl.admit(declared, files, sync_hits=set(), appetite=None, why=why, version=2)
    assert v1.route == "chain: files", v1
    assert v2.route == "lane", v2
