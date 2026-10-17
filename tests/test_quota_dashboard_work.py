"""T04 — the Work view (plan 2026-10-17-plan-1, ticket T04).

Every test feeds `work.render` a hand-built `_view_data("work")` dict and reads the markup as DATA
(elements, attributes, text); no collector runs, nothing is read under $HOME or probed.
"""

from __future__ import annotations

import json
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

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


# ---------------------------------------------------------------- wave review round 1 (slice B)
def test_owner_tokens_are_distinct_whitespace_free_and_match_their_sections():
    r = repo(
        "fabrik",
        [item("W-1", owner="a b"), item("W-2", owner="a_b"), item("W-3", owner="(unassigned)")],
    )
    _, root = render([r])
    chips = [
        b.attrs["data-filter"].split(":", 1)[1]
        for b in find(root, "button")
        if b.attrs.get("data-filter", "").startswith("owner:")
    ]
    chips = [c for c in chips if c != ""]  # the All chip clears the filter
    sections = [n.attrs["data-f-owner"] for n in root.walk() if "data-f-owner" in n.attrs]
    assert len(chips) == len(set(chips)) == len(sections) == len(set(sections))
    assert sorted(chips) == sorted(sections)
    assert not any(any(ch.isspace() for ch in c) for c in chips)
    # a literal "(unassigned)" owner and the empty owner are two different tokens
    assert "%28unassigned%29" in chips and "%" in chips


def test_lone_surrogate_owner_does_not_break_the_view():
    r = repo("fabrik", [item("W-1", owner="a\ud800b"), item("W-2", owner="a\ud800c")])
    _, root = render([r])
    sections = [n.attrs["data-f-owner"] for n in root.walk() if "data-f-owner" in n.attrs]
    assert len(sections) == len(set(sections))
    assert not any(any(ch.isspace() for ch in s) for s in sections)


def test_duplicate_item_ids_get_unique_elements_and_own_dialogs():
    r = repo(
        "fabrik",
        [
            item("W-1", question="first question"),
            item("W-1", question="second question"),
        ],
    )
    _, root = render([r])
    ids = [n.attrs["id"] for n in root.walk() if "id" in n.attrs]
    assert len(ids) == len(set(ids))
    dialogs = {d.attrs["id"]: d.all_text() for d in find(root, "dialog")}
    seen = []
    for b in buttons_in(root):
        if json.loads(b.attrs["data-body"])["action"] == "accept":
            seen.append(dialogs[b.attrs["data-confirm"]])
    assert len(seen) == 2
    assert "first question" in seen[0] and "second question" not in seen[0]
    assert "second question" in seen[1] and "first question" not in seen[1]
    # the POST body still carries the real id
    assert all(json.loads(b.attrs["data-body"])["item"] == "W-1" for b in buttons_in(root))
    # each Comment button reads its own field
    srcs = [b.attrs["data-text-from"] for b in buttons_in(root) if "data-text-from" in b.attrs]
    assert len(set(srcs)) == 2


def test_a_faulting_pane_is_isolated_to_its_repo(monkeypatch):
    real = work._pane

    def boom(data, r, cap, tip_cap):
        if r["name"] == "bad":
            raise KeyError("x")
        return real(data, r, cap, tip_cap)

    monkeypatch.setattr(work, "_pane", boom)
    res, root = render([repo("fabrik", [item("W-1")]), repo("bad", [item("W-9")])])
    assert row_of(root, "W-1")
    pane = find(root, **{"data-pick": "bad"})[0]
    assert "KeyError" in pane.all_text() and find(pane, **{"data-state": "error"})
    assert [r["name"] for r in res.item_targets] == ["fabrik"]


def test_a_faulted_repo_is_not_counted_in_the_intro_or_the_picker(monkeypatch):
    real = work._pane

    def boom(data, r, cap, tip_cap):
        if r["name"] == "bad":
            raise KeyError("x")
        return real(data, r, cap, tip_cap)

    monkeypatch.setattr(work, "_pane", boom)
    _, root = render([repo("fabrik", [item("W-1")]), repo("bad", [item("W-9"), item("W-8")])])
    picks = {
        b.attrs["data-pick-to"]: b.all_text().strip()
        for b in root.walk()
        if "data-pick-to" in b.attrs
    }
    assert picks == {"fabrik": "fabrik 1", "bad": "bad"}
    intro = [n for n in root.walk() if n.tag == "span" and "remaining items" in n.all_text()][0]
    assert intro.all_text().startswith("1 repos") and "1 remaining items" in intro.all_text()


def test_navs_have_accessible_names():
    _, root = render([repo("fabrik", [item("W-1")])])
    navs = find(root, "nav")
    assert len(navs) == 2 and all(n.attrs.get("aria-label") for n in navs)


def test_item_without_an_id_has_no_controls_and_no_target():
    r = repo("fabrik", [item("W-1"), item("", title="no id"), item(None, title="none id")])
    res, root = render([r])
    assert [b.all_text().strip() for b in buttons_in(root)].count("Comment") == 1
    assert [i["id"] for i in res.item_targets[0]["items"]] == ["W-1"]


def test_last_comment_line_and_row_order():
    it = item(
        "W-1",
        comments=[
            {"by": "a", "text": "x"},
            {"by": "bob", "action": "accept", "text": "go ahead", "at": time.time() - 300},
        ],
    )
    bare = item("W-2", comments=[{"text": ""}])
    _, root = render([repo("fabrik", [it, bare])])
    text = row_of(root, "W-1").all_text()
    assert "bob accept: go ahead" in text and "2 notes" in text and "min ago" in text
    assert "operator comment" in row_of(root, "W-2").all_text()
    rows = [
        item("W-c", _prio=3),
        item("W-b", _prio=1),
        item("W-a", _prio=1),
        item("W-z", _prio=5, status="awaiting-operator", kind="decision", question="q"),
    ]
    _, root = render([repo("fabrik", rows)])
    ids = [
        tr.kids[0].all_text().strip()
        for tr in find(root, "tr")
        if tr.kids and tr.kids[0].attrs.get("scope") == "row"
    ]
    assert ids == ["W-z", "W-a", "W-b", "W-c"]
    assert "P1" in row_of(root, "W-a").all_text()


@pytest.mark.parametrize("bad", [-5, -1, float("nan"), float("inf"), 1e30], ids=repr)
def test_a_bad_read_time_drops_the_stamp_and_the_view_still_renders(bad):
    """A broken `now` costs the view its stamp, never the whole view."""
    _, root = render([repo("fabrik", [item("W-1")])], now=bad)
    assert row_of(root, "W-1")
    stamps = find(root, "time")
    assert stamps and all("data-ts" not in s.attrs for s in stamps)


def test_a_rows_element_ids_survive_other_rows_coming_and_going():  # wave r3 (B-6)
    # app.js carries a typed comment across a refresh by element id; an id that moves when another
    # row sorts in above would drop the operator's draft
    def cmt(rows):
        _, root = render([repo("fabrik", rows)])
        out = {}
        for b in buttons_in(root):
            if "data-text-from" in b.attrs:
                out[json.loads(b.attrs["data-body"])["item"]] = b.attrs["data-text-from"]
        return out

    before = cmt([item("W-B"), item("W-C")])
    after = cmt([item("W-A"), item("W-B"), item("W-C")])
    assert after["W-B"] == before["W-B"] and after["W-C"] == before["W-C"]
