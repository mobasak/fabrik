"""T04 — the Work view (plan 2026-10-17-plan-1, ticket T04).

Every test feeds `work.render` a hand-built `_view_data("work")` dict and reads the markup as DATA
(elements, attributes, text); no collector runs, nothing is read under $HOME or probed.
"""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "dashboard_ui"
sys.path.insert(0, str(_PKG.parent))

from dashboard_ui import snapshot  # noqa: E402
from dashboard_ui.views import ViewContext, ViewResult, work  # noqa: E402

HUB = ["coordinator", "infra", "fleet", "intel", "kaizen"]
CTX = ViewContext(
    opt_root=Path("/nonexistent-opt"), fabrik_root=Path("/nonexistent-hub"), now=1000.0
)


class _N:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids, self.text = tag, attrs, parent, [], ""

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()

    def all_text(self):
        return self.text + "".join(k.all_text() for k in self.kids)


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _N("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = _N(tag, dict(attrs), self.cur)
        self.cur.kids.append(n)
        if tag not in {"input", "meta", "br"}:
            self.cur = n

    def handle_endtag(self, tag):
        c = self.cur
        while c is not self.root and c.tag != tag:
            c = c.parent
        if c is not self.root:
            self.cur = c.parent

    def handle_data(self, d):
        self.cur.text += d


def dom(html) -> _N:
    p = _P()
    p.feed(str(html))
    return p.root


def find(root, tag=None, **attrs):
    return [
        n
        for n in root.walk()
        if (tag is None or n.tag == tag) and all(n.attrs.get(k) == v for k, v in attrs.items())
    ]


def item(i, **kw):
    base = {
        "id": i,
        "kind": "task",
        "status": "open",
        "title": f"title {i}",
        "owner": "infra",
        "tags": [],
        "next": "",
        "comments": [],
        "_prio": 2,
        "_claim": "",
    }
    base.update(kw)
    return base


def repo(name, items=(), **kw):
    r = {
        "name": name,
        "items": list(items),
        "error": None,
        "skipped": [],
        "main": f"/m/{name}",
        "root": f"/m/{name}",
    }
    r.update(kw)
    return r


def data(repos, **kw):
    d = {
        "now": 1000.0,
        "refresh_s": 20,
        "work": repos,
        "hub_agents": HUB,
        "owner_order": {},
        "repos_ttl_s": 20.0,
        "next_cap": 20,
        "next_tip_cap": 60,
    }
    d.update(kw)
    return d


def render(repos, **kw):
    res = work.render(data(repos, **kw), CTX)
    assert isinstance(res, ViewResult)
    return res, dom(res.html)


def row_of(root, item_id):
    return [tr for tr in find(root, "tr") if tr.kids and tr.kids[0].all_text().strip() == item_id][
        0
    ]


def buttons_in(node):
    return [b for b in node.walk() if b.tag == "button" and "data-post" in b.attrs]


def labels(node):
    return [b.all_text().strip() for b in buttons_in(node)]


# ---------------------------------------------------------------- B1 picker
def test_fabrik_first_and_panes_addressable():
    # the collector's order is not the view's: a bigger repo listed first must not lead
    big = repo("zeta", [item("W-1"), item("W-2")])
    fab = repo("fabrik", [item("W-3")])
    small = repo("alpha", [])
    _, root = render([big, small, fab])
    grp = find(root, **{"data-pick-group": "repo"})
    assert grp
    panes = [n.attrs["data-pick"] for n in grp[0].walk() if "data-pick" in n.attrs]
    assert panes == ["fabrik", "zeta", "alpha"]
    picks = [b.attrs["data-pick-to"] for b in grp[0].walk() if "data-pick-to" in b.attrs]
    assert picks == panes


# ---------------------------------------------------------------- B2 verdict rule (D-917)
def test_verdict_controls_by_status_and_kind():
    r = repo(
        "fabrik",
        [
            item("W-open"),
            item("W-dec", status="awaiting-operator", kind="decision", question="Ship it?"),
            item("W-fyi", status="awaiting-operator", kind="task"),
        ],
    )
    _, root = render([r])
    assert labels(row_of(root, "W-open")) == ["Accept", "Reject", "Comment"]
    assert labels(row_of(root, "W-dec")) == ["Accept", "Reject", "Comment"]
    assert labels(row_of(root, "W-fyi")) == ["Comment"]


# ---------------------------------------------------------------- B3 token + dialogs
def test_verdict_bodies_carry_token_and_dialogs_gate_by_rule():
    it = item("W-dec", status="awaiting-operator", kind="decision", question="Ship <it>?")
    _, root = render([repo("fabrik", [it])])
    row = row_of(root, "W-dec")
    by_action = {}
    for b in buttons_in(row):
        body = json.loads(b.attrs["data-body"])
        assert b.attrs["data-post"] == "/item-verdict"
        assert body["token"] == snapshot.token(it)
        assert body["repo"] == "fabrik" and body["item"] == "W-dec"
        by_action[body["action"]] = b
    assert set(by_action) == {"accept", "reject", "comment"}
    acc, rej, com = by_action["accept"], by_action["reject"], by_action["comment"]
    assert acc.attrs["data-note"] == "optional" and rej.attrs["data-note"] == "required"
    assert "data-confirm" not in com.attrs and "data-note" not in com.attrs
    dialogs = {d.attrs["id"]: d for d in find(root, "dialog")}
    # the dialog each button names exists, and Accept's shows the full question
    assert acc.attrs["data-confirm"] in dialogs and rej.attrs["data-confirm"] in dialogs
    assert acc.attrs["data-confirm"] != rej.attrs["data-confirm"]
    assert "Ship <it>?" in dialogs[acc.attrs["data-confirm"]].all_text()
    note_acc = find(dialogs[acc.attrs["data-confirm"]], "textarea")[0]
    note_rej = find(dialogs[rej.attrs["data-confirm"]], "textarea")[0]
    assert "required" not in note_acc.attrs and "required" in note_rej.attrs
    # Comment reads its inline field, which exists in the row
    src = com.attrs["data-text-from"]
    assert any(n.attrs.get("id") == src for n in row.walk())


# ---------------------------------------------------------------- B4 chips, tags, next, skipped
def test_owner_chips_tags_next_and_skipped():
    long_next = "n" * 50
    r = repo(
        "fabrik",
        [
            item("W-1", owner="infra", tags=["alpha", "beta"], next=long_next),
            item("W-2", owner="", status="awaiting-operator", kind="decision", question="q"),
            item("W-3", owner="stranger", tags="solo"),
        ],
        skipped=["bad item file one", "bad claim two"],
    )
    _, root = render([r])
    chips = {
        b.attrs["data-filter"]: b.all_text()
        for b in find(root, "button")
        if b.attrs.get("data-filter", "").startswith("owner:")
    }
    for o in HUB:
        assert f"owner:{o}" in chips, o
    assert "0" in chips["owner:kaizen"] and "1" in chips["owner:infra"]
    # the awaiting unowned decision is the operator's
    assert "1" in chips["owner:operator"] and "owner:stranger" in chips
    unassigned = [k for k in chips if "unassigned" in chips[k]]
    assert len(unassigned) == 1 and "0" in chips[unassigned[0]]
    # each owner's section carries data-f-owner
    for o in ["infra", "kaizen", "operator", "stranger"]:
        assert find(root, **{"data-f-owner": o}), o
    # rows carry their tags; a string tag is one tag
    assert row_of(root, "W-1").attrs["data-f-tag"] == "alpha beta"
    assert row_of(root, "W-3").attrs["data-f-tag"] == "solo"
    # the tag box filters whole tokens
    box = find(root, "input", **{"data-filter": "tag"})[0]
    assert box.attrs["type"] == "search" and box.attrs["data-filter-mode"] == "token"
    # Next is capped at next_cap, the longer text (to next_tip_cap) is still in the page
    text = row_of(root, "W-1").all_text()
    assert "n" * 19 + "…" in text and "n" * 50 in text
    # skipped stores are listed, every one
    page = root.all_text()
    assert "bad item file one" in page and "bad claim two" in page


# ---------------------------------------------------------------- B5 failed collector
def test_failed_repo_shows_error_others_render_and_stamp():
    bad = repo("broken", [], error="OSError: store gone", main=None, root=None)
    good = repo("fabrik", [item("W-1")])
    _, root = render([bad, good])
    page = root.all_text()
    assert "OSError: store gone" in page and "broken" in page
    assert row_of(root, "W-1")
    fresh = find(root, "time")
    assert fresh and fresh[0].attrs["data-cadence"] == "20"
    assert any(n.attrs.get("data-refresh-s") == "20" for n in root.walk())
    # a failed repo offers no button
    assert not buttons_in(find(root, **{"data-pick": "broken"})[0])


def test_whole_collector_failure_and_empty_states():
    _, root = render({"error": "RuntimeError: boom"})
    err = find(root, **{"data-state": "error"})
    assert err and "RuntimeError: boom" in err[0].all_text()
    res, root = render([])
    assert find(root, **{"data-state": "empty"})
    assert res.item_targets == []


# ---------------------------------------------------------------- B6 item targets
def test_item_targets_cover_every_shown_item_in_publish_shape():
    a = repo("fabrik", [item("W-1"), item("W-2")])
    b = repo("other", [item("W-9")])
    bad = repo("broken", [], error="boom", main=None, root=None)
    res, root = render([a, b, bad])
    shown = {
        (json.loads(btn.attrs["data-body"])["repo"], json.loads(btn.attrs["data-body"])["item"])
        for btn in buttons_in(root)
    }
    assert shown == {("fabrik", "W-1"), ("fabrik", "W-2"), ("other", "W-9")}
    # the dashboard's `_publish_item_targets` shape: repo dicts with name/main/root/items[id]
    got = {
        (str(r["name"]), str(i["id"]))
        for r in res.item_targets
        if r.get("main") and not r.get("error")
        for i in r["items"]
    }
    assert got == shown


def test_hostile_text_is_escaped_and_ids_are_valid():
    r = repo("we.ird repo", [item("W-1", title="<img src=x onerror=1>", owner="a b")])
    res, root = render([r])
    assert "<img" not in str(res.html)
    ids = [n.attrs["id"] for n in root.walk() if "id" in n.attrs]
    assert len(ids) == len(set(ids))
