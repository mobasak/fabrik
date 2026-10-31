"""T03 — the Overview view and the fleet-wide blocked-merge reader (plan 2026-10-17-plan-1, ticket T03).

`render` is called with exactly the keys T02's `_view_data("overview")` produces plus what this view's
own `collect` adds; every collector is a fixture. The merge reader runs over merge records written to
two temporary repos, and its owner resolver is a stub `decisions.py` under a temporary hub root — no
test reads /opt, ~/.claude* or the network. Markup is read as DATA (ids, attributes, text).
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "sysadmin"))

from dashboard_ui import components as ui  # noqa: E402
from dashboard_ui import fmt, merges, snapshot  # noqa: E402
from dashboard_ui import strings as cat  # noqa: E402
from dashboard_ui.strings import t  # noqa: E402
from dashboard_ui.views import ViewContext, ViewResult, overview  # noqa: E402

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC).timestamp()


# ---------------------------------------------------------------- a tiny DOM
class _Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, attrs, parent, [], ""

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def all_text(self) -> str:
        return self.text + "".join(c.all_text() for c in self.children)


_VOID = {"input", "meta", "link", "br", "hr", "img"}


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = _Node("#root", {}, None)

    def handle_starttag(self, tag, attrs):
        n = _Node(tag, dict(attrs), self.cur)
        self.cur.children.append(n)
        if tag not in _VOID:
            self.cur = n

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text += data


def parse(html: str) -> _Node:
    p = _Tree()
    p.feed(html)
    p.close()
    return p.root


def by_id(root: _Node, ident: str) -> _Node:
    hits = [n for n in root.walk() if n.attrs.get("id") == ident]
    assert len(hits) == 1, (ident, len(hits))
    return hits[0]


def find(root: _Node, tag: str | None = None, **attrs) -> list[_Node]:
    out = []
    for n in root.walk():
        if tag is not None and n.tag != tag:
            continue
        if all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items()):
            out.append(n)
    return out


def words(node: _Node) -> str:
    return " ".join(node.all_text().split())


# ---------------------------------------------------------------- fixtures
def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _item(ident, *, ground="gate", age_h=1.0, kind="decision", question="Ship it?", creator="infra",
          status="awaiting-operator", **extra):  # fmt: skip
    it = {"id": ident, "title": f"title of {ident}", "status": status, "kind": kind,
          "question": question, "created": _iso(NOW - age_h * 3600), "creator": creator, **extra}  # fmt: skip
    if ground is not None:
        it["ground"] = ground
    return it


def _repo(name, items, **extra):
    return {"name": name, "items": items, "error": None, "skipped": [], "main": f"/x/{name}",
            "root": f"/x/{name}", **extra}  # fmt: skip


def _agent(name, state="idle", **extra):
    base = {"name": name, "window": state != "away", "windows": 1, "named_from": "", "state": state,
            "now": None, "claim": None, "next": {"queued": 0, "top": []}, "merges": [],
            "merge_owner": False, "paused": None, "can_pause": True, "pause_honoured": True}  # fmt: skip
    base.update(extra)
    return base


def _status(band="GREEN", probe_failed=None, read_at=NOW - 5, hold=None):
    payload = {
        "active": "mob",
        "accounts": [
            {
                "email": "mob@example.com",
                "slugs": ["mob"],
                # the ACTIVE account's own resets differ from the fleet readers' (ob, can) below,
                # so a reset read from the wrong row shows
                "five_hour": {"utilization": 95, "resets_at_epoch": NOW + 600},
                "seven_day": {"utilization": 30, "resets_at_epoch": NOW + 86400 * 5},
                "model_windows": {"Fable": {"utilization": 10, "resets_at_epoch": NOW + 86400 * 3}},
            },
            {
                "email": "ob@example.com",
                "slugs": ["ob"],
                "five_hour": {"utilization": 41, "resets_at_epoch": NOW + 3600},
            },
            {
                "email": "can@example.com",
                "slugs": ["can"],
                "seven_day": {"utilization": 77, "resets_at_epoch": NOW + 86400 * 2},
            },
        ],  # fmt: skip
        "posture": {
            "active": {
                "slug": "mob",
                "email": "mob@example.com",
                "band": band,
                "band_fable": "GREEN",
            },
            "fleet": {
                "windows": {
                    "five_hour": {"utilization": 41, "slug": "ob"},
                    "seven_day": {"utilization": 77, "slug": "can"},
                    "fable": {"utilization": 12, "slug": "mob"},
                },  # fmt: skip
                "successor": {"email": "ob@example.com", "slug": "ob"},
                "next_relief": {
                    "epoch": NOW + 600,
                    "email": "can@example.com",
                    "window": "five_hour",
                },
                "hold": hold,
            },
        },
    }
    if probe_failed:
        payload["probe_failed"] = probe_failed
    return {"payload": payload, "read_at": read_at, "probe_failure": None}


def _data(**over):
    d = {
        "now": NOW,
        "refresh_s": 20,
        "probe_interval_s": 20,
        "work": [],
        "box": {"repos": []},
        "status": _status(),
        "budget": {"disabled": True},
        "health": {"stale": [], "failed": []},
        "ag_states": {"working": "working", "idle": "idle", "stale": "stale", "away": "away"},
        "hub_agents": ["coordinator", "infra", "fleet", "intel", "kaizen"],
        "blocked": [],
        "merge_unreadable": [],
    }
    d.update(over)
    return d


def _ctx(tmp_path: Path) -> ViewContext:
    return ViewContext(opt_root=tmp_path, fabrik_root=tmp_path, now=NOW)


def _render(tmp_path, **over) -> tuple[ViewResult, _Node, str]:
    res = overview.render(_data(**over), _ctx(tmp_path))
    assert isinstance(res, ViewResult)
    assert type(res.html) is ui.Safe
    return res, parse(res.html), str(res.html)


# ---------------------------------------------------------------- the blocked-merge reader
_CROCK = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid(ms: int, rand: int = 0) -> str:
    v, out = (ms << 80) | rand, []
    for _ in range(26):
        out.append(_CROCK[v & 31])
        v >>= 5
    return "".join(reversed(out))


_STUB = """
import pathlib, sys, time
log = pathlib.Path(__file__).with_name("calls.log")
with log.open("a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] != "--merge-owner":
    sys.exit(9)
repo = pathlib.Path(sys.argv[2]).name
if repo == "alpha":
    print("coordinator"); sys.exit(0)
if repo == "beta":
    print("UNDECLARED: beta declares no merge owner"); sys.exit(3)
if repo == "sleepy":
    time.sleep(0.4); print("intel"); sys.exit(0)
if repo == "filed":
    print(pathlib.Path(__file__).with_name("owner.txt").read_text().strip()); sys.exit(0)
if repo == "sleep4":
    time.sleep(4); print("fleet"); sys.exit(0)
if repo.startswith("slow"):
    time.sleep(5)
sys.stderr.write("decisions: cannot read /x/docs/DECISIONS.md (boom)\\n"); sys.exit(1)
"""


def _drain(timeout: float = 8.0) -> None:
    """Wait until no resolver call is in flight (a background refresh writes the cache when it lands)."""
    end = time.monotonic() + timeout
    while getattr(merges, "_INFLIGHT", None) and time.monotonic() < end:
        time.sleep(0.02)


@pytest.fixture(autouse=True)
def _fresh_owner_cache():
    merges._OWNER_CACHE.clear()
    yield
    _drain()
    merges._OWNER_CACHE.clear()


def _hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    (hub / "scripts").mkdir(parents=True)
    (hub / "scripts" / "decisions.py").write_text(_STUB, encoding="utf-8")
    return hub


def _records(opt: Path, repo: str, recs: list[dict]) -> Path:
    d = opt / repo / ".git" / "fabrik-merge"
    d.mkdir(parents=True, exist_ok=True)
    for r in recs:
        (d / f"{r['id']}.json").write_text(json.dumps(r), encoding="utf-8")
    return d


def _settled(opt: Path, hub: Path, **kw) -> list[dict]:
    """`blocked` once the owner lookups it started have landed: the first call never waits on the
    resolver (it reads "resolving"), so a test about the owner reads the call after the refresh."""
    merges.blocked(opt, hub, **kw)
    _drain()
    return merges.blocked(opt, hub, **kw)


def _rec(ms, branch, *, phase="replied", outcome=None, rand=0, **extra):
    r = {"id": _ulid(ms, rand), "phase": phase, "branch": branch, "item": "W-1", "requester": "fleet",
         **extra}  # fmt: skip
    if outcome is not None:
        r["outcome"] = outcome
    return r


def test_a_branch_is_blocked_only_when_its_newest_record_is_refused_or_catchup_refused(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    t0 = int((NOW - 7200) * 1000)
    d = _records(opt, "alpha", [
        _rec(t0, "b-merged-later", phase="refused", outcome="refused", reason="old"),
        _rec(t0 + 1000, "b-merged-later", outcome="merged"),
        _rec(t0, "b-refused", outcome="merged"),
        _rec(t0 + 1000, "b-refused", phase="refused", outcome="refused", reason="tests red"),
        _rec(t0 + 2000, "b-catchup", phase="catchup-refused", reason="behind main"),
        _rec(t0, "b-inflight", phase="refused", outcome="refused"),
        _rec(t0 + 5000, "b-inflight", phase="claimed"),
    ])  # fmt: skip
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    (d / "list.json").write_text("[1, 2]", encoding="utf-8")
    _records(opt, "beta", [_rec(t0, "x", phase="refused", outcome="refused", reason="conflict")])
    bad: list[str] = []
    merges.blocked(opt, hub, now=NOW)
    _drain()
    out = merges.blocked(opt, hub, unreadable=bad, now=NOW)
    got = {(b["repo"], b["branch"]) for b in out}
    assert got == {("alpha", "b-refused"), ("alpha", "b-catchup"), ("beta", "x")}
    refused = next(b for b in out if b["branch"] == "b-refused")
    assert refused["reason"] == "tests red"
    assert refused["item"] == "W-1" and refused["requester"] == "fleet"
    assert refused["id"] == _ulid(t0 + 1000)
    # the age is the ULID's own millisecond time, not the file's mtime
    assert refused["age_s"] == pytest.approx(7199.0)
    assert refused["owner"] == "coordinator" and refused["owner_error"] is None
    assert sorted(Path(p).name for p in bad) == ["broken.json", "list.json"]


def test_an_unresolvable_owner_is_named_with_the_resolvers_own_message(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    t0 = int((NOW - 60) * 1000)
    for repo in ("beta", "gamma"):
        _records(opt, repo, [_rec(t0, "x", phase="refused", outcome="refused")])
    out = {b["repo"]: b for b in _settled(opt, hub)}
    # exit 3: the resolver's own STDOUT, not a constant
    assert out["beta"]["owner"] is None
    assert out["beta"]["owner_error"] == "UNDECLARED: beta declares no merge owner"
    assert out["gamma"]["owner"] is None
    assert out["gamma"]["owner_error"] == "decisions: cannot read /x/docs/DECISIONS.md (boom)"
    # the resolver is asked with a REPO_DIR path, under --merge-owner
    calls = (hub / "scripts" / "calls.log").read_text().splitlines()
    assert f"--merge-owner {opt / 'beta'}" in calls


def test_a_resolver_that_hangs_is_reported_as_timed_out(tmp_path, monkeypatch):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    monkeypatch.setattr(merges, "OWNER_TIMEOUT_S", 0.5)
    _records(opt, "slow", [_rec(int(NOW * 1000), "x", phase="refused", outcome="refused")])
    (b,) = _settled(opt, hub)
    assert b["owner"] is None and b["owner_error"] == "timed out" and not b["owner_resolving"]


def test_a_render_never_waits_on_the_resolver(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    _records(opt, "sleep4", [_rec(int(NOW * 1000), "x", phase="refused", outcome="refused")])
    t0 = time.monotonic()
    got = overview.collect(ViewContext(opt_root=opt, fabrik_root=hub, now=NOW))
    assert time.monotonic() - t0 < 0.5  # the resolver needs 4 s
    (b,) = got["blocked"]
    assert b["owner"] is None and b["owner_error"] is None and b["owner_resolving"] is True
    _res, root, _ = _render(tmp_path, **got)
    assert t("ov.merge.owner_resolving") in words(by_id(root, "ov-merges"))
    _drain()  # the background lookup lands
    (b,) = merges.blocked(opt, hub)
    assert b["owner"] == "fleet" and b["owner_resolving"] is False


def test_the_owner_is_resolved_once_per_repo_and_cached(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    t0 = int(NOW * 1000)
    _records(opt, "alpha", [_rec(t0, "a", phase="refused", outcome="refused"),
                            _rec(t0, "b", phase="refused", outcome="refused", rand=1)])  # fmt: skip
    _records(opt, "delta", [_rec(t0, "a", outcome="merged")])  # nothing blocked: never asked
    _settled(opt, hub)
    merges.blocked(opt, hub)
    _drain()  # a refresh the third call started (an expired TTL) would land here
    calls = (hub / "scripts" / "calls.log").read_text().splitlines()
    assert calls == [f"--merge-owner {opt / 'alpha'}"]


def test_a_thread_that_cannot_start_never_wedges_the_repo(tmp_path, monkeypatch):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    _records(opt, "alpha", [_rec(int(NOW * 1000), "x", phase="refused", outcome="refused")])
    real, fails = threading.Thread.start, []

    def start_once(self):
        if not fails:
            fails.append(1)
            raise RuntimeError("can't start new thread")
        return real(self)

    monkeypatch.setattr(threading.Thread, "start", start_once)
    (b,) = merges.blocked(opt, hub)
    assert b["owner"] is None and b["owner_error"] == "RuntimeError: can't start new thread"
    assert not merges._INFLIGHT
    (b,) = _settled(opt, hub)  # the next render retries and resolves normally
    assert b["owner"] == "coordinator" and b["owner_error"] is None


def test_blocked_branches_come_out_in_ulid_order_whatever_the_case(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    t0 = int(NOW * 1000)
    older = _rec(t0, "one", phase="refused", outcome="refused", rand=10)  # ends in "A"
    older["id"] = older["id"].lower()  # "…a" sorts after "…B" as raw text
    newer = _rec(t0, "two", phase="refused", outcome="refused", rand=11)  # ends in "B"
    _records(opt, "alpha", [older, newer])
    assert [b["branch"] for b in merges.blocked(opt, hub)] == ["one", "two"]


def test_hanging_resolvers_run_in_parallel_in_the_background(tmp_path, monkeypatch):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    monkeypatch.setattr(merges, "OWNER_TIMEOUT_S", 0.5)
    for repo in ("slow1", "slow2", "slow3", "slow4"):
        _records(opt, repo, [_rec(int(NOW * 1000), "x", phase="refused", outcome="refused")])
    t0 = time.monotonic()
    out = merges.blocked(opt, hub)
    assert time.monotonic() - t0 < 0.4  # nothing waits on a resolver
    assert [b["owner_resolving"] for b in out] == [True] * 4
    _drain()
    took = time.monotonic() - t0
    assert took < 1.5, took  # all four in parallel; one after another would be >= 2.0 s
    assert [b["owner_error"] for b in merges.blocked(opt, hub)] == ["timed out"] * 4


def test_concurrent_renders_share_one_resolver_call_per_repo(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    t0 = int(NOW * 1000)
    for repo in ("sleepy", "alpha"):
        _records(opt, repo, [_rec(t0, "x", phase="refused", outcome="refused")])
    gate, results = threading.Barrier(4), []

    def render() -> None:
        gate.wait()
        results.append({b["repo"]: b["owner"] for b in merges.blocked(opt, hub)})

    threads = [threading.Thread(target=render) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(10)
    assert len(results) == 4
    _drain()
    assert {b["repo"]: b["owner"] for b in merges.blocked(opt, hub)} == {
        "sleepy": "intel",
        "alpha": "coordinator",
    }
    calls = sorted((hub / "scripts" / "calls.log").read_text().splitlines())
    assert calls == [f"--merge-owner {opt / 'alpha'}", f"--merge-owner {opt / 'sleepy'}"]


def test_an_expired_owner_is_served_while_one_refresh_runs_then_replaced(tmp_path, monkeypatch):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    monkeypatch.setattr(merges, "OWNER_TTL_S", 0.2)
    (hub / "scripts" / "owner.txt").write_text("fleet", encoding="utf-8")
    _records(opt, "filed", [_rec(int(NOW * 1000), "x", phase="refused", outcome="refused")])
    assert _settled(opt, hub)[0]["owner"] == "fleet"
    (hub / "scripts" / "owner.txt").write_text("intel", encoding="utf-8")
    time.sleep(0.3)  # past the TTL
    assert merges.blocked(opt, hub)[0]["owner"] == "fleet"  # the cached answer, while it refreshes
    _drain()
    assert merges.blocked(opt, hub)[0]["owner"] == "intel"
    assert len((hub / "scripts" / "calls.log").read_text().splitlines()) == 2


def test_a_record_without_a_ulid_id_is_unreadable_and_ids_compare_case_insensitively(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    t0 = int(NOW * 1000)
    older = _rec(t0, "b", outcome="merged", rand=10)  # ends in "A"
    older["id"] = older["id"].lower()  # "…a" sorts after "…B" as raw text
    newer = _rec(t0, "b", phase="refused", outcome="refused", rand=11)  # ends in "B"
    d = _records(opt, "alpha", [older, newer])
    (d / "numeric.json").write_text(json.dumps({"id": 5, "branch": "c", "outcome": "refused"}))
    (d / "word.json").write_text(
        json.dumps({"id": "not-a-ulid", "branch": "c", "outcome": "refused"})
    )
    bad: list[str] = []
    out = merges.blocked(opt, hub, unreadable=bad)
    assert [(b["branch"], b["id"]) for b in out] == [("b", newer["id"])]
    assert sorted(Path(p).name for p in bad) == ["numeric.json", "word.json"]


def test_collect_hands_the_blocked_list_and_the_unreadable_records_to_render(tmp_path):
    opt, hub = tmp_path / "opt", _hub(tmp_path)
    d = _records(opt, "alpha", [_rec(int(NOW * 1000), "a", phase="refused", outcome="refused")])
    (d / "bad.json").write_text("nope", encoding="utf-8")
    got = overview.collect(ViewContext(opt_root=opt, fabrik_root=hub, now=NOW))
    assert [b["branch"] for b in got["blocked"]] == ["a"]
    assert [Path(p).name for p in got["merge_unreadable"]] == ["bad.json"]


def test_a_blocked_merge_card_names_the_owner_or_says_it_is_unresolved(tmp_path):
    blocked = [
        {"repo": "alpha", "branch": "feat-a", "item": "W-1", "requester": "fleet", "id": "01X",
         "age_s": 7200.0, "reason": "tests red", "owner": "coordinator", "owner_error": None},
        {"repo": "beta", "branch": "feat-b", "item": "", "requester": "intel", "id": "01Y",
         "age_s": 60.0, "reason": "conflict", "owner": None, "owner_error": "UNDECLARED"},
    ]  # fmt: skip
    _res, root, _ = _render(tmp_path, blocked=blocked)
    sec = words(by_id(root, "ov-merges"))
    for text in (
        t("ov.merge.card_title", repo="alpha", branch="feat-a"),
        t("ov.merge.item", item="W-1"),
        t("ov.merge.requester", who="fleet"),
        t("ov.merge.reason", reason="tests red"),
        t("ov.merge.owner", owner="coordinator"),
        t("ov.merge.age", age=t("ov.dur.h", n=2)),
        t("ov.merge.no_item"),
        t("ov.merge.owner_unresolved", error="UNDECLARED"),
    ):
        assert text in sec, text
    # read-only: a blocked merge offers no action
    assert not find(by_id(root, "ov-merges"), "button")


def test_a_merge_card_with_nothing_recorded_says_so_in_its_own_words(tmp_path):
    blocked = [{"repo": "a", "branch": "b", "item": "", "requester": "", "id": "01", "age_s": None,
                "reason": "", "owner": None, "owner_error": None}]  # fmt: skip
    _res, root, _ = _render(tmp_path, blocked=blocked)
    sec = words(by_id(root, "ov-merges"))
    for key in ("ov.merge.no_requester", "ov.merge.no_reason", "ov.merge.owner_unresolved_bare"):
        assert t(key) in sec, key
    # the unknown-TIME phrase appears once, as the age, never as a requester, reason or owner
    assert sec.count(t("ov.dur.unknown")) == 1


# ---------------------------------------------------------------- decisions
def test_groups_hub_first_then_by_oldest_and_gate_first_inside(tmp_path):
    work = [
        _repo("zeta", [_item("W-z1", age_h=200)]),  # older than all fabrik: hub-first, not oldest-first
        _repo("alpha", [_item("W-a1", age_h=5)]),
        _repo("fabrik", [
            _item("W-f-new-gate", ground="gate", age_h=1),
            _item("W-f-none", ground=None, age_h=90),  # the OLDEST, and still last: ungrounded
            _item("W-f-old-owned", ground="owned", age_h=40),
            _item("W-f-old-gate", ground="gate", age_h=30),
            _item("W-f-done", status="open"),
        ]),
    ]  # fmt: skip
    _res, root, _ = _render(tmp_path, work=work)
    sec = by_id(root, "ov-decisions")
    groups = find(sec, "details")
    assert [g.attrs["data-repo"] for g in groups] == ["fabrik", "zeta", "alpha"]
    order = [a.attrs["id"] for a in find(groups[0], "article")]
    assert order == [
        ui.slug("fabrik/W-f-old-gate", "dc"),
        ui.slug("fabrik/W-f-new-gate", "dc"),
        ui.slug("fabrik/W-f-old-owned", "dc"),
        ui.slug("fabrik/W-f-none", "dc"),
    ]
    assert ["open" in g.attrs for g in groups] == [True, False, False]
    assert t("ov.dec.group", repo="zeta", n=1) in words(groups[1])


def test_the_first_non_empty_group_opens_when_the_hub_has_none(tmp_path):
    work = [_repo("fabrik", []), _repo("beta", [_item("W-b", age_h=2)]),
            _repo("alpha", [_item("W-a", age_h=9)])]  # fmt: skip
    _res, root, _ = _render(tmp_path, work=work)
    groups = find(by_id(root, "ov-decisions"), "details")
    assert [(g.attrs["data-repo"], "open" in g.attrs) for g in groups] == [
        ("alpha", True),
        ("beta", False),
    ]


def test_past_100_decisions_each_group_shows_its_five_oldest_and_a_work_link(tmp_path):
    hub = [_item(f"W-f{i:03d}", age_h=i) for i in range(60)]
    other = [_item(f"W-o{i:03d}", age_h=i, ground="owned") for i in range(41)]
    res, root, _ = _render(tmp_path, work=[_repo("fabrik", hub), _repo("my repo", other)])
    groups = find(by_id(root, "ov-decisions"), "details")
    first = [a.attrs["id"] for a in find(groups[0], "article")]
    assert first == [ui.slug(f"fabrik/W-f{i:03d}", "dc") for i in (59, 58, 57, 56, 55)]
    assert len(find(groups[1], "article")) == 5
    assert [a.attrs["href"] for a in find(groups[0], "a")] == ["/#work/fabrik"]
    assert [a.attrs["href"] for a in find(groups[1], "a")] == ["/#work/my%20repo"]
    assert t("ov.dec.more", n=60) in words(groups[0])
    # the targets are the items SHOWN
    shown = {(r["name"], i["id"]) for r in res.item_targets for i in r["items"]}
    assert len(shown) == 10


def test_the_growth_trigger_counts_decisions_only(tmp_path):
    decisions = [_item(f"W-d{i:03d}", age_h=i) for i in range(60)]
    notes = [_item(f"W-n{i:03d}", age_h=i, kind="note") for i in range(60)]
    _res, root, _ = _render(tmp_path, work=[_repo("fabrik", decisions + notes)])
    assert len(find(by_id(root, "ov-decisions"), "article")) == 120  # 60 decisions: no cut
    assert not find(by_id(root, "ov-decisions"), "a")


def test_past_100_a_group_that_hides_nothing_has_no_more_line(tmp_path):
    hub = [_item(f"W-f{i:03d}", age_h=i) for i in range(98)]
    small = [_item(f"W-s{i}", age_h=i) for i in range(3)]
    _res, root, _ = _render(tmp_path, work=[_repo("fabrik", hub), _repo("small", small)])
    groups = find(by_id(root, "ov-decisions"), "details")
    assert len(find(groups[1], "article")) == 3
    assert not find(groups[1], "a")
    assert t("ov.dec.more", n=3) not in words(groups[1])
    assert [a.attrs["href"] for a in find(groups[0], "a")] == ["/#work/fabrik"]


def test_exactly_100_decisions_still_show_every_card(tmp_path):
    items = [_item(f"W-{i:03d}", age_h=i) for i in range(100)]
    _res, root, _ = _render(tmp_path, work=[_repo("fabrik", items)])
    assert len(find(by_id(root, "ov-decisions"), "article")) == 100
    assert not find(by_id(root, "ov-decisions"), "a")


def _card(root, repo, ident):
    return by_id(root, ui.slug(f"{repo}/{ident}", "dc"))


def _posts(node):
    return {b.all_text().strip(): b for b in find(node, "button") if "data-post" in b.attrs}


def test_a_decision_card_shows_ground_asker_wait_and_clamped_question_with_three_verdicts(tmp_path):
    question = "Deploy <b>the</b> certified build?" + " long" * 80
    item = _item("W-d", ground="underivable", age_h=3, question=question, creator="fleet",
                 comments=[{"by": "operator", "text": "hm"}], alt_ids=["W-x"])  # fmt: skip
    _res, root, html = _render(tmp_path, work=[_repo("alpha", [item])])
    card = _card(root, "alpha", "W-d")
    text = words(card)
    assert t("ov.ground.underivable") in text
    assert t("ov.dec.asker", who="fleet") in text
    assert t("ov.dec.wait", age=t("ov.dur.h", n=3)) in text
    clamp = [n for n in find(card, "div") if "data-clamp" in n.attrs]
    assert len(clamp) == 1 and clamp[0].attrs["data-lines"] == "3"
    assert "<b>the</b>" not in html  # escaped, never markup
    posts = _posts(card)
    assert set(posts) == {t("ov.dec.accept"), t("ov.dec.reject"), t("ov.dec.comment")}
    tok = snapshot.token(item)
    for label, action in (("ov.dec.accept", "accept"), ("ov.dec.reject", "reject"),
                          ("ov.dec.comment", "comment")):  # fmt: skip
        b = posts[t(label)]
        assert b.attrs["data-post"] == "/item-verdict"
        assert json.loads(b.attrs["data-body"]) == {
            "repo": "alpha", "item": "W-d", "action": action, "token": tok}  # fmt: skip
    acc, rej, com = (posts[t(k)] for k in ("ov.dec.accept", "ov.dec.reject", "ov.dec.comment"))
    # Accept: a dialog carrying the FULL question, an optional note
    assert acc.attrs["data-note"] == "optional"
    dlg = by_id(root, acc.attrs["data-confirm"])
    assert dlg.tag == "dialog" and " ".join(question.split()) in words(dlg)
    assert find(dlg, "textarea") and "required" not in find(dlg, "textarea")[0].attrs
    assert t("ov.dec.accept_confirm", id="W-d") in words(dlg)
    # Reject: a dialog whose note is required
    assert rej.attrs["data-note"] == "required"
    rdlg = by_id(root, rej.attrs["data-confirm"])
    assert "required" in find(rdlg, "textarea")[0].attrs
    assert " ".join(question.split()) in words(rdlg)  # the operator rejects what they read
    # Comment: an inline field, no dialog
    assert "data-confirm" not in com.attrs
    field = by_id(root, com.attrs["data-text-from"])
    assert field.tag == "input"
    assert find(card, "label", **{"for": com.attrs["data-text-from"]})


@pytest.mark.parametrize("bad_id", [None, "", 7], ids=["missing", "empty", "number"])
def test_an_item_without_a_string_id_gets_no_controls_and_no_target(tmp_path, bad_id):
    item = _item("W-x", question="Who am I?")
    if bad_id is None:
        del item["id"]
    else:
        item["id"] = bad_id
    twin = dict(item)  # two id-less items in one repo must not share element ids
    res, root, html = _render(tmp_path, work=[_repo("alpha", [item, twin, _item("W-ok")])])
    sec = by_id(root, "ov-decisions")
    cards = find(sec, "article")
    assert len(cards) == 3
    nameless = [c for c in cards if "Who am I?" in words(c)]
    assert len(nameless) == 2
    for c in nameless:
        # the clamp's own "show all" toggle stays; no action control does
        assert not _posts(c) and not find(c, "dialog") and not find(c, "input")
        assert t("ov.dec.no_id") in words(c)
    ids = [n.attrs["id"] for n in root.walk() if "id" in n.attrs]
    assert len(ids) == len(set(ids))
    assert [i["id"] for r in res.item_targets for i in r["items"]] == ["W-ok"]


def test_an_awaiting_non_decision_offers_comment_only(tmp_path):
    item = _item("W-q", kind="question", ground=None)
    _res, root, _ = _render(tmp_path, work=[_repo("alpha", [item])])
    card = _card(root, "alpha", "W-q")
    posts = _posts(card)
    assert set(posts) == {t("ov.dec.comment")}
    assert json.loads(posts[t("ov.dec.comment")].attrs["data-body"])["token"] == snapshot.token(
        item
    )
    assert t("ov.ground.none") in words(card)


# ---------------------------------------------------------------- empty, summary, freshness
def test_nothing_waiting_shows_the_line_with_the_time_of_the_last_read(tmp_path):
    _res, root, _ = _render(tmp_path, work=[_repo("fabrik", [_item("W-o", status="open")])])
    sec = by_id(root, "ov-decisions")
    state = find(sec, "div", data_state="empty")
    assert state and t("ov.dec.none") in words(state[0])
    stamp = find(sec, "time")
    assert stamp and stamp[0].attrs["data-ts"] == str(int(NOW))


def test_the_summary_counts_match_the_stores_and_link_to_their_sections(tmp_path):
    work = [_repo("fabrik", [_item("W-1", age_h=2), _item("W-2", age_h=26)]),
            _repo("beta", [_item("W-3", age_h=1)])]  # fmt: skip
    box = {"repos": [{"name": "fabrik", "main": "/x/fabrik", "dormant": 0, "agents": [
        _agent("infra", "working", now={"command": "fabrik-task", "phase": 1, "phases": 6}),
        _agent("fleet", "idle"), _agent("intel", "away")]}]}  # fmt: skip
    blocked = [{"repo": "beta", "branch": "b", "item": "W-9", "requester": "x", "id": "01",
                "age_s": 5.0, "reason": "r", "owner": "infra", "owner_error": None}]  # fmt: skip
    health = {
        "stale": [{"view": "accounts", "age_s": 100.0}],
        "failed": [{"key": "box", "error": "E"}],
    }
    _res, root, _ = _render(tmp_path, work=work, box=box, blocked=blocked, health=health,
                            status=_status(band="AMBER"), merge_unreadable=["/r/bad.json"])  # fmt: skip
    links = [(a.attrs["href"], words(a)) for a in find(by_id(root, "ov-summary"), "a")]
    assert links == [
        ("#ov-decisions", t("ov.sum.decisions", repo="fabrik", n=2, age=t("ov.dur.h", n=26))),
        ("#ov-decisions", t("ov.sum.decisions", repo="beta", n=1, age=t("ov.dur.h", n=1))),
        ("#ov-merges", t("ov.sum.merges", n=1)),
        ("#ov-agents", t("ov.sum.agents", n=2)),
        ("#ov-quota", t("ov.sum.band", band="AMBER", account="mob")),
        ("#ov-health", t("ov.sum.health", n=3)),
    ]


def test_an_unreadable_collector_reads_unreadable_in_the_summary_never_zero(tmp_path):
    _res, root, _ = _render(tmp_path, blocked={"error": "E"}, box={"error": "F"})
    links = {words(a): a.attrs["href"] for a in find(by_id(root, "ov-summary"), "a")}
    assert links[t("ov.sum.merges_error")] == "#ov-merges"
    assert links[t("ov.sum.agents_error")] == "#ov-agents"
    assert t("ov.sum.merges", n=0) not in links and t("ov.sum.agents", n=0) not in links


def test_every_section_carries_a_freshness_stamp_at_its_cadence(tmp_path):
    _res, root, _ = _render(tmp_path, probe_interval_s=35)
    for sec in ("ov-summary", "ov-decisions", "ov-merges", "ov-agents", "ov-quota", "ov-health"):
        stamps = find(by_id(root, sec), "time")
        assert stamps, sec
        # the quota strip goes stale on the PROBE's cadence, every other section on the view's
        assert stamps[0].attrs["data-cadence"] == ("35" if sec == "ov-quota" else "20"), sec
    # the quota stamp is the probe's own read time
    assert find(by_id(root, "ov-quota"), "time")[0].attrs["data-ts"] == str(int(NOW - 5))
    # and the fragment declares the view's refresh period
    assert find(root, "div", data_refresh_s="20")


# ---------------------------------------------------------------- reorder (P5-r1)
def _order(html: str) -> list[str]:
    return re.findall(r'<section class="section" id="(ov-[a-z]+)"', html)


@pytest.mark.parametrize(
    "over",
    [
        {"status": _status(band="RED")},
        {"status": _status(band="WALL")},
        {"status": _status(probe_failed="TimeoutExpired")},
        {"health": {"stale": [], "failed": [{"key": "probe", "error": "OSError", "at": NOW}]}},
    ],
    ids=["red", "wall", "payload-probe-failed", "health-probe-failed"],
)
def test_red_wall_or_a_failed_probe_moves_quota_and_health_above_the_decisions(tmp_path, over):
    _res, _root, html = _render(tmp_path, **over)
    assert _order(html) == [
        "ov-summary", "ov-quota", "ov-health", "ov-decisions", "ov-merges", "ov-agents"]  # fmt: skip


@pytest.mark.parametrize(
    "over",
    [{}, {"status": _status(band="AMBER")},
     {"health": {"stale": [{"view": "accounts", "age_s": 99.0}], "failed": [{"key": "box", "error": "E"}]}}],
    ids=["green", "amber", "health-only-faulted"],
)  # fmt: skip
def test_without_red_wall_or_a_failed_probe_they_stay_below_the_agents(tmp_path, over):
    _res, _root, html = _render(tmp_path, **over)
    assert _order(html) == [
        "ov-summary", "ov-decisions", "ov-merges", "ov-agents", "ov-quota", "ov-health"]  # fmt: skip


# ---------------------------------------------------------------- agents
def _box():
    return {"repos": [
        {"name": "zz", "main": "/x/zz", "dormant": 0, "agents": [_agent("solo", "idle")]},
        {"name": "fabrik", "main": "/x/fabrik", "dormant": 3, "agents": [
            _agent("infra", "working", windows=2,
                   now={"command": "fabrik-task", "phase": 2, "phases": 6, "title": "build it",
                        "surface": "scripts/x.py", "updated_ts": NOW - 120, "stale": False},
                   claim={"id": "W-c1", "title": "the claimed thing"},
                   next={"queued": 5, "top": [{"id": "W-n1", "priority": 1, "title": "next one"},
                                              {"id": "W-n2", "priority": 2, "title": "next two"}]},
                   merges=[{"sha": "abc1234", "ts": NOW - 3600, "item": "W-m", "subject": "s"}]),
            _agent("coordinator", "idle", named_from="record", merge_owner=True),
            _agent("fleet", "stale", now={"command": "fabrik-review", "phase": 1, "phases": 3,
                                          "title": "t", "updated_ts": NOW - 50000, "stale": True}),
            _agent("kaizen", "away", can_pause=False),
            _agent("intel", "idle", pause_honoured=False,
                   paused={"name": "intel", "names": ["intel", "wt-intel"], "partial": True,
                           "by": "coordinator", "at": NOW - 600, "why": "quota"}),
        ]},
        {"name": "quiet", "main": "/x/quiet", "dormant": 0, "agents": []},
        {"name": "broken", "main": "/x/broken", "dormant": 0, "agents": [], "error": "OSError: no"},
    ]}  # fmt: skip


def _row(root, agent):
    rows = find(root, "tr", data_agent=agent)
    assert len(rows) == 1, agent
    return rows[0]


def test_every_agent_has_its_row_with_every_field(tmp_path):
    _res, root, _ = _render(tmp_path, box=_box())
    sec = by_id(root, "ov-agents")
    text = words(sec)
    assert t("ov.ag.counts", working=1, idle=3, stale=1, away=1, quiet=1) in text
    assert t("ov.ag.dormant", repo="fabrik", n=3) in text
    assert t("ov.ag.repo_error", repo="broken", error="OSError: no") in text
    # fabrik's table comes first
    tables = find(sec, "table")
    assert t("ov.ag.table", repo="fabrik") in words(tables[0])
    infra = words(_row(sec, "infra"))
    for s in (t("ov.ag.state.working"), t("ov.ag.now", command="fabrik-task"),
              t("ov.ag.phase", phase=2, phases=6), "build it", "scripts/x.py",
              t("ov.ag.updated", age=t("ov.dur.min", n=2)),
              t("ov.ag.item", id="W-c1", title="the claimed thing"),
              t("ov.ag.item", id="W-n1", title="next one"), t("ov.ag.more_queued", n=3),
              t("ov.ag.merge", sha="abc1234", age=t("ov.dur.h", n=1)), "W-m",
              t("ov.ag.windows", n=2)):  # fmt: skip
        assert s in infra, s
    coord = words(_row(sec, "coordinator"))
    for s in (t("ov.ag.merge_owner"), t("ov.ag.named"), t("ov.ag.no_command"),
              t("ov.ag.nothing_queued")):  # fmt: skip
        assert s in coord, s
    fleet = words(_row(sec, "fleet"))
    assert t("ov.ag.state.stale") in fleet and t("ov.ag.stale_note") in fleet
    assert t("ov.ag.updated", age=t("ov.dur.h", n=13)) not in fleet  # the note REPLACES the age
    assert t("ov.ag.state.away") in words(_row(sec, "kaizen"))
    intel = words(_row(sec, "intel"))
    for s in (t("ov.ag.paused", by="coordinator", age=t("ov.dur.min", n=10)),
              t("ov.ag.paused_partial"), t("ov.ag.paused_why", why="quota"),
              t("ov.ag.not_honoured")):  # fmt: skip
        assert s in intel, s
    assert words(_row(sec, "solo"))


def test_pause_states_the_turn_boundary_and_resume_names_every_marker(tmp_path):
    _res, root, _ = _render(tmp_path, box=_box())
    sec = by_id(root, "ov-agents")
    pause = _posts(_row(sec, "fleet"))[t("ov.ag.pause")]
    assert pause.attrs["data-post"] == "/agent-pause"
    assert json.loads(pause.attrs["data-body"]) == {
        "repo": "fabrik",
        "agent": "fleet",
        "action": "pause",
    }
    assert pause.attrs["data-note"] == "optional"
    dlg = by_id(root, pause.attrs["data-confirm"])
    assert t("ov.ag.pause_body", agent="fleet") in words(dlg)
    assert find(dlg, "textarea") and "required" not in find(dlg, "textarea")[0].attrs
    resume = _posts(_row(sec, "intel"))[t("ov.ag.resume")]
    assert json.loads(resume.attrs["data-body"]) == {
        "repo": "fabrik",
        "agent": "intel",
        "action": "resume",
    }
    rdlg = by_id(root, resume.attrs["data-confirm"])
    assert t("ov.ag.resume_body", names="intel, wt-intel", by="coordinator") in words(rdlg)
    # no pause button where work.py pause cannot succeed
    assert not _posts(_row(sec, "kaizen"))


# ---------------------------------------------------------------- quota and health
def test_the_quota_strip_shows_band_account_successor_windows_resets_and_hold(tmp_path):
    status = _status(
        band="RED", probe_failed="TimeoutExpired", hold={"tier": "walled", "since": NOW}
    )
    _res, root, _ = _render(tmp_path, status=status)
    text = words(by_id(root, "ov-quota"))
    for s in (
        t("ov.q.band", band="RED"),  # a hold is not one window's doing: no window named
        t("ov.q.band_fable", band="GREEN"),
        t("ov.q.active", account="mob"),
        t("ov.q.successor", account="ob"),
        t("ov.q.window", window=t("ov.q.w.five_hour"), pct="41", slug="ob", reset=fmt.fmt_reset(NOW + 3600)),
        t("ov.q.window", window=t("ov.q.w.seven_day"), pct="77", slug="can",
          reset=fmt.fmt_reset(NOW + 86400 * 2)),
        t("ov.q.window", window=t("ov.q.w.fable"), pct="12", slug="mob", reset=fmt.fmt_reset(NOW + 86400 * 3)),
        t("ov.q.hold", tier="walled"),
        t("ov.q.relief", account="can@example.com", when=fmt.fmt_reset(NOW + 600), window="five_hour"),
        t("ov.q.probe_failed", error="TimeoutExpired"),
    ):  # fmt: skip
        assert " ".join(s.split()) in text, s
    assert t("ov.q.band_on", band="RED", window=t("ov.q.w.seven_day")) not in text


def test_each_window_reset_is_its_own_readers_never_the_active_accounts(tmp_path):
    status = _status()
    status["payload"]["posture"]["fleet"]["windows"]["five_hour"] = {
        "utilization": 20,
        "slug": "gone",
    }
    _res, root, _ = _render(tmp_path, status=status)
    text = words(by_id(root, "ov-quota"))
    # "gone" has no account row: its reset is unknown, never the active mob's 10-minute one
    assert t("ov.q.window", window=t("ov.q.w.five_hour"), pct="20", slug="gone", reset="—") in text
    for w in ("five_hour", "seven_day", "fable"):  # (the next-relief line names NOW+600 itself)
        assert f"{t(f'ov.q.w.{w}')}:" in text
        assert "resets " + fmt.fmt_reset(NOW + 600) not in text, w


def _band_line(root) -> str:
    return words(find(by_id(root, "ov-quota"), "span", **{"class": "badge"})[0])


def test_the_band_names_its_window_from_the_session_and_weekly_readings_only(tmp_path):
    status = _status(band="RED")
    _res, root, _ = _render(tmp_path, status=status)
    assert t("ov.q.band_on", band="RED", window=t("ov.q.w.seven_day")) in _band_line(root)
    # a hot FABLE window never names the band's window: the band is not computed from it
    status = _status(band="GREEN")
    status["payload"]["posture"]["fleet"]["windows"]["fable"]["utilization"] = 95
    _res, root, _ = _render(tmp_path, status=status)
    assert t("ov.q.w.fable") not in _band_line(root)
    assert t("ov.q.band_on", band="GREEN", window=t("ov.q.w.seven_day")) in _band_line(root)
    # WALL is no single window's
    _res, root, _ = _render(tmp_path, status=_status(band="WALL"))
    assert _band_line(root).endswith(t("ov.q.band", band="WALL"))


def test_no_quota_reading_is_said_in_words(tmp_path):
    _res, root, _ = _render(tmp_path, status={"error": "OSError: quota.json unreadable"})
    state = find(by_id(root, "ov-quota"), "div", data_state="error")
    assert state and state[0].attrs["role"] == "alert"
    assert t("ov.q.none", error="OSError: quota.json unreadable") in words(state[0])
    assert t("ov.sum.band_unknown") in words(by_id(root, "ov-summary"))
    # the server's own "no reading yet" at start (`_status_data`) and a status with no payload
    # are the EMPTY state — nothing has failed yet
    for status in ({"error": "no reading yet"}, {}):
        _res, root, _ = _render(tmp_path, status=status)
        sec = by_id(root, "ov-quota")
        state = find(sec, "div", data_state="empty")
        assert state and t("ov.q.none_yet") in words(state[0]), status
        assert not find(sec, "div", data_state="error"), status


def test_health_lists_stale_views_failed_probes_unreadable_records_and_the_budget(tmp_path):
    health = {"stale": [{"view": "accounts", "age_s": 125.0}],
              "failed": [{"key": "box", "error": "OSError: x"}, {"key": "probe", "error": "TimeoutExpired"}]}  # fmt: skip
    budget = {
        "seats": [{"label": "read-only", "key": "read_only", "allowed": 4, "box": 6, "taken": 2,
                   "floored": True, "quota_cap": 3, "has_quota_cap": True},
                  {"label": "heavy", "key": "heavy", "allowed": 2, "box": 3, "taken": 2,
                   "floored": False, "quota_cap": None, "has_quota_cap": False}],
        "cli_cap": 10, "hold": False,
        "quota": {"ok": True, "active": "mob", "hottest_pct": 40, "eligible": 2, "eligible_raw": 3},
        "caveats": ["box probe is old"],
    }  # fmt: skip
    _res, root, _ = _render(tmp_path, health=health, budget=budget, merge_unreadable=["/a", "/b"])
    text = words(by_id(root, "ov-health"))
    # today's page wording (INV-2): the floor, the siblings' reservation and the quota cap survive
    seats = " · ".join([
        "read-only seats allowed now: 4 (box 6 = the floor, 2 reserved by sibling sessions, quota 3)",
        "heavy seats allowed now: 2 (box 3 after 2 reserved by sibling sessions)"])  # fmt: skip
    quota = t("ov.h.budget_quota", active="mob", pct=40, eligible=2, raw=3)
    for s in (
        t("ov.h.stale", view="accounts", age=t("ov.dur.min", n=2)),
        t("ov.h.failed", name="box", error="OSError: x"),
        t("ov.h.failed", name="probe", error="TimeoutExpired"),
        t("ov.h.unreadable", n=2),
        t("ov.h.budget", seats=seats, cli_cap=10, quota=quota),
        t("ov.h.budget_caveats", caveats="box probe is old"),
    ):
        assert s in text, s


def test_a_probe_failure_seen_twice_is_one_fault(tmp_path):
    health = {"stale": [], "failed": [{"key": "probe", "error": "TimeoutExpired"}]}
    _res, root, _ = _render(tmp_path, health=health, status=_status(probe_failed="TimeoutExpired"))
    text = words(by_id(root, "ov-health"))
    assert text.count(t("ov.h.failed", name="probe", error="TimeoutExpired")) == 1
    assert t("ov.sum.health", n=1) in words(by_id(root, "ov-summary"))


@pytest.mark.parametrize("honoured", [True, None, "no"], ids=["true", "missing", "truthy-text"])
def test_not_honoured_shows_only_when_the_reading_is_exactly_false(tmp_path, honoured):
    paused = {"name": "a", "names": ["a"], "partial": False, "by": "x", "at": NOW, "why": ""}
    agent = _agent("a", "idle", paused=paused)
    if honoured is None:
        del agent["pause_honoured"]
    else:
        agent["pause_honoured"] = honoured
    box = {"repos": [{"name": "r", "main": "/x/r", "dormant": 0, "agents": [agent]}]}
    _res, root, _ = _render(tmp_path, box=box)
    assert t("ov.ag.not_honoured") not in words(_row(root, "a"))


def test_a_seat_with_nothing_reserved_names_the_box_alone(tmp_path):
    budget = {"seats": [{"key": "heavy", "allowed": 3, "box": 3, "taken": 0, "floored": False,
                         "has_quota_cap": False}],
              "cli_cap": 10, "hold": False, "quota": {}, "caveats": []}  # fmt: skip
    _res, root, _ = _render(tmp_path, budget=budget)
    text = words(by_id(root, "ov-health"))
    assert "heavy seats allowed now: 3 (box 3)" in text
    assert "reserved" not in text and "quota 0" not in text


def test_a_healthy_board_says_so_and_a_disabled_budget_renders_nothing(tmp_path):
    _res, root, _ = _render(tmp_path)
    text = words(by_id(root, "ov-health"))
    assert t("ov.h.ok") in text and "Box budget" not in text


# ---------------------------------------------------------------- targets and robustness
def test_render_returns_item_targets_for_every_awaiting_item_and_pause_targets_for_every_repo(
    tmp_path,
):
    work = [_repo("fabrik", [_item("W-1"), _item("W-open", status="open")]),
            _repo("beta", [_item("W-2", kind="note")]),
            {"name": "bad", "items": [], "error": "OSError: x", "skipped": []}]  # fmt: skip
    box = _box()
    res, _root, _ = _render(tmp_path, work=work, box=box)
    targets = {
        (r["name"], i["id"]): (r["main"], r["root"]) for r in res.item_targets for i in r["items"]
    }
    assert targets == {
        ("fabrik", "W-1"): ("/x/fabrik", "/x/fabrik"),
        ("beta", "W-2"): ("/x/beta", "/x/beta"),
    }
    assert res.pause_targets == box["repos"]


def test_a_broken_collector_is_that_sections_error_never_the_views(tmp_path):
    res, root, _ = _render(tmp_path, work={"error": "boom"}, box={"error": "bang"},
                           blocked={"error": "merge fault"})  # fmt: skip
    assert t("ov.dec.error", error="boom") in words(by_id(root, "ov-decisions"))
    assert t("ov.ag.error", error="bang") in words(by_id(root, "ov-agents"))
    assert t("ov.merge.error", error="merge fault") in words(by_id(root, "ov-merges"))
    assert t("ov.sum.work_error") in words(by_id(root, "ov-summary"))
    assert res.item_targets == [] and res.pause_targets == []


def test_every_word_comes_from_the_catalogue(tmp_path):
    over = {"work": [_repo("fabrik", [_item("W-1"), _item("W-2", kind="note", ground=None)])],
            "box": _box(), "status": _status(band="RED", hold={"tier": "walled"})}  # fmt: skip
    _res, _root, english = _render(tmp_path, **over)
    stand_in = {k: "§" + k for k in cat.CATALOGUE}
    with cat.use(stand_in):
        _res2, _root2, out = _render(tmp_path, **over)
    used = [
        k for k, v in cat.CATALOGUE.items() if k.startswith("ov.") and len(v) >= 6 and v in english
    ]
    assert len(used) >= 25
    visible = re.sub(r"§[a-z0-9_.]+", "", out)  # the stand-in words themselves
    for k in used:
        assert cat.CATALOGUE[k] not in visible, k


# ---------------------------------------------------------------- a bad read time drops only its stamp
_BAD_TS = [-5, -1, float("nan"), float("inf"), 1e30, "1960-01-01T00:00:00"]
# the sections stamped from the data's `now` or the probe's `read_at`; merges + health use the clock
_DATA_STAMPED = ("ov-summary", "ov-decisions", "ov-agents", "ov-quota")


@pytest.mark.parametrize("bad", _BAD_TS, ids=repr)
def test_a_bad_read_time_drops_its_regions_stamp_and_the_view_still_renders(tmp_path, bad):
    """One collector's broken timestamp must cost that region its stamp, never crash the view."""
    _res, root, _ = _render(tmp_path, now=bad, status=_status(read_at=bad))
    for sec in _DATA_STAMPED:
        stamps = find(by_id(root, sec), "time")
        assert stamps and all("data-ts" not in s.attrs for s in stamps), sec
    for sec in ("ov-merges", "ov-health"):  # the clock-stamped sections keep their stamp
        assert find(by_id(root, sec), "time")[0].attrs.get("data-ts"), sec


@pytest.mark.parametrize("bad", [-1.0, float("nan"), 1e30], ids=repr)
def test_a_bad_clock_drops_the_clock_stamps_and_the_view_still_renders(tmp_path, bad):
    res = overview.render(_data(), ViewContext(opt_root=tmp_path, fabrik_root=tmp_path, now=bad))
    root = parse(res.html)
    for sec in ("ov-merges", "ov-health"):  # the two sections stamped with the request clock
        stamps = find(by_id(root, sec), "time")
        assert stamps and all("data-ts" not in s.attrs for s in stamps), sec


def test_the_resolver_timeout_is_ten_seconds_and_no_render_waits_on_it():  # wave r3, plan review 17
    # the timeout bounds the BACKGROUND lookup only; a render has no deadline because it never waits
    assert merges.OWNER_TIMEOUT_S == 10
    assert not hasattr(merges, "OWNER_DEADLINE_S")


def test_the_start_up_no_reading_yet_is_no_health_fault(tmp_path):  # wave r3
    # the server lists the start-up status as a failed collector; Quota calls it "not read yet", so
    # Health and the summary must not call it a fault
    status = {"error": "no reading yet"}
    health = {"stale": [], "failed": [{"key": "status", "error": "no reading yet"}]}
    _res, root, _ = _render(tmp_path, status=status, health=health)
    assert "no reading yet" not in words(by_id(root, "ov-health"))
    assert t("ov.sum.health", n=1) not in words(by_id(root, "ov-summary"))
    # a real status failure is still a fault
    health = {"stale": [], "failed": [{"key": "status", "error": "OSError: x"}]}
    _res, root, _ = _render(tmp_path, status={"error": "OSError: x"}, health=health)
    assert "OSError: x" in words(by_id(root, "ov-health"))


def test_overview_five_hour_retired(tmp_path):
    """D-1400 (W-992979e1) — a retired fleet 5h reading prints `retired`, not `0% used`, and never
    becomes the window the band is named on."""
    st = _status(band="AMBER")
    st["payload"]["posture"]["fleet"]["windows"]["five_hour"] = {
        "utilization": 0.0,
        "slug": "sarp",
        "retired": True,
    }
    st["payload"]["posture"]["fleet"]["windows"]["seven_day"] = {"utilization": 0.0, "slug": "can"}
    _res, root, _html = _render(tmp_path, status=st)
    quota = words(by_id(root, "ov-quota"))
    assert "5 h: retired (sarp)" in quota, quota
    assert "5 h: 0% used" not in quota
    assert "Band AMBER on Weekly" in quota, "a retired 0.0 ties the weekly 0.0 and must not win it"
