"""T05 — the Accounts view: banners, rotation order, meters, governor, warnings, Edit disclosure.

Plan set `docs/development/plans/2026-10-17-plan-1-command-centre-dashboard/`, ticket T05. Every
test renders the view from a FIXTURE `data` dict (what `quota_dashboard._view_data("accounts")`
hands in) and reads the markup as data. No collector, probe, credential or account file is touched.
"""

from __future__ import annotations

import json
import sys
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

from dashboard_ui.views import ViewContext, accounts  # noqa: E402

SLUG_RE = r"[a-z0-9][a-z0-9_-]{0,63}"
EMAIL_RE = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
NOW = 1_800_000_000.0
CTX = ViewContext(opt_root=Path("/nonexistent"), fabrik_root=Path("/nonexistent"), now=NOW)


class _Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, attrs, parent, [], ""

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def all_text(self):
        return "".join([self.text] + [c.all_text() + c.tail for c in self.children])

    tail = ""


class _Parser(HTMLParser):
    VOID = {"input", "meta", "link", "br", "img"}

    def __init__(self):
        super().__init__()
        self.root = _Node("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = _Node(tag, dict(attrs), self.cur)
        self.cur.children.append(n)
        if tag not in self.VOID:
            self.cur = n

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if self.cur.children:
            self.cur.children[-1].tail += data
        else:
            self.cur.text += data


def dom(markup):
    p = _Parser()
    p.feed(str(markup))
    return p.root


def find(node, tag=None, **attrs):
    return [
        n
        for n in node.walk()
        if (tag is None or n.tag == tag)
        and all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items())
    ]


def row(root, slug):
    hits = [
        r for r in find(root, "tr", **{"data-acct": slug}) if r.attrs.get("data-row") != "return"
    ]
    assert len(hits) == 1, (slug, len(hits))
    return hits[0]


def text(node):
    return " ".join(node.all_text().split())


def acct(slug, email, *, five=30.0, seven=40.0, fable=10.0, **extra):
    a = {
        "slugs": [slug],
        "email": email,
        "five_hour": {"utilization": five, "resets_at_epoch": NOW + 3600},
        "seven_day": {"utilization": seven, "resets_at_epoch": NOW + 86400 * 3},
        "model_windows": {"Fable": {"utilization": fable, "resets_at_epoch": NOW + 86400 * 3}},
        "source": "live",
    }
    a.update(extra)
    return a


def entry(n, a, kind, returns_at=None):
    return {"n": n, "slug": a["slugs"][0], "acct": a, "kind": kind, "returns_at": returns_at}


def make(**over):
    alpha = acct("alpha", "alpha@example.com", five=20.0, seven=30.0)
    bravo = acct("bravo", "bravo@example.com", weekly_cap=80)
    delta = acct("delta", "delta@example.com", seven=100.0, cap_walled=True)
    charlie = acct("charlie", "charlie@example.com", parked=True, weekly_cap=50)
    payload = {
        "active": "alpha",
        "accounts": [alpha, bravo, delta, charlie],
        "pending": ["echo"],
        "fleet_warnings": ["delta is weekly-walled"],
        "pause": None,
        "posture": {
            "active": {
                "windows": {
                    "five_hour": {
                        "utilization": 20,
                        "burn_per_min": 0.5,
                        "verdict": "reset_first",
                        "minutes_to_reset": 90,
                    }
                }
            }
        },
    }
    queue = [
        entry(1, alpha, "active"),
        entry(2, bravo, "eligible"),
        entry(3, delta, "returns", NOW + 86400),
        entry(4, alpha, "return", NOW + 7200),
        entry(5, charlie, "returns", None),
    ]
    data = {
        "now": NOW,
        "refresh_s": 20,
        "probe_interval_s": 20.0,
        "status": {"payload": payload, "read_at": NOW - 5, "probe_failure": None},
        "queue": queue,
        "trigger_threshold": 85.0,
        "reserve_pct": 80.0,
        "drain_band": 85.0,
        "five_hour_s": 18000.0,
        "seven_day_s": 604800.0,
        "switch_header": "X-Quota-Dash",
        "pool_policy_on": True,
        "slug_re": SLUG_RE,
        "email_re": EMAIL_RE,
    }
    data.update(over)
    return data


def render(data=None):
    r = accounts.render(data or make(), CTX)
    return str(r.html)


def controls(root, slug):
    """The data-post buttons inside the row's Edit disclosure, keyed by endpoint."""
    r = row(root, slug)
    out = {}
    for d in find(r, "details"):
        for b in find(d, "button"):
            if "data-post" in b.attrs:
                out.setdefault(b.attrs["data-post"], []).append(b)
    return out


def dialog_for(root, button):
    d = find(root, "dialog", id=button.attrs["data-confirm"])
    assert len(d) == 1
    return d[0]


# ---------------------------------------------------------------- B1: the four banners
def test_a_failed_probe_keeps_the_last_good_reading_under_its_banner():
    d = make()
    d["status"]["probe_failure"] = {"at": NOW, "error": "rotate CLI exited 2"}
    html = render(d)
    root = dom(html)
    assert "Live probe failed — showing the last good reading." in text(root)
    assert "rotate CLI exited 2" in text(root)
    assert row(root, "alpha")
    assert controls(root, "bravo")  # controls survive a failed probe


@pytest.mark.parametrize(
    ("pause", "words"),
    [
        ("marker", "Auto-rotation is PAUSED by the operator marker."),
        ("error", "Pause state unreadable — rotation is failing closed."),
    ],
)
def test_the_pause_banners_show_exactly_for_their_state(pause, words):
    d = make()
    d["status"]["payload"]["pause"] = pause
    assert words in text(dom(render(d)))
    other = make()
    assert "PAUSED" not in text(dom(render(other)))
    assert "Pause state unreadable" not in text(dom(render(other)))


def test_no_accounts_shows_the_banner_and_a_clean_view_has_none():
    d = make(queue=[])
    d["status"]["payload"]["accounts"] = []
    d["status"]["payload"]["pending"] = []
    assert "No fleet accounts reporting yet." in text(dom(render(d)))
    clean = text(dom(render()))
    assert "No fleet accounts reporting yet." not in clean
    assert "Live probe failed" not in clean


# ---------------------------------------------------------------- B2: order, returning, pending, meters
def test_rows_follow_the_queue_order_with_return_and_pending_rows_last():
    root = dom(render())
    order = [
        r.attrs["data-acct"] + ":" + r.attrs["data-row"]
        for r in find(root, "tr")
        if "data-acct" in r.attrs
    ]
    assert order == [
        "alpha:active",
        "bravo:eligible",
        "delta:returns",
        "alpha:return",
        "charlie:returns",
        "echo:pending",
    ]
    assert "#1 ACTIVE · also #4" in text(row(root, "alpha"))
    assert "#2 NEXT" in text(root)
    assert "return time unknown" in text(root)
    assert "pending-login" in text(find(root, "tr", **{"data-acct": "echo"})[0])


def test_each_account_row_carries_its_three_meters_and_the_active_burn():
    root = dom(render())
    alpha = text(row(root, "alpha"))
    assert "80% left" in alpha and "70% left" in alpha and "90% left" in alpha
    assert "0.50%/m, reset in ~90m" in alpha  # the active account's burn and reset
    assert "0.50%/m" not in text(row(root, "bravo"))  # a standby carries no posture
    cells = find(row(root, "bravo"), "td")
    assert len(cells) >= 3


def test_a_row_without_a_reading_and_a_rolled_over_cache_say_so_in_words():
    d = make()
    pl = d["status"]["payload"]
    pl["accounts"][1]["five_hour"] = {}
    pl["accounts"][1]["seven_day"]["utilization"] = None
    root = dom(render(d))
    assert "no reading" in text(row(root, "bravo"))
    d2 = make()
    stale = d2["status"]["payload"]["accounts"][1]
    stale.update(source="cache", age_s=7 * 86400)
    stale["five_hour"]["resets_at_epoch"] = NOW - 10
    d2["queue"][1] = entry(2, stale, "eligible")
    out = text(row(dom(render(d2)), "bravo"))
    assert "idle" in out and "not the active pointer" in out


# ---------------------------------------------------------------- B3: governor, warnings, rule
def test_governor_warnings_and_rotation_rule_show_with_their_numbers():
    root = dom(render())
    t = text(root)
    assert "Quota governor · alpha" in t
    assert "reserve 80%" in t and "cap_walled no" in t and "routine → ob@" in t
    assert "delta is weekly-walled" in t
    assert "85%" in t and "every 20s" in t and "Rotation flips the active pointer" in t


def test_the_governor_says_the_pool_is_off_unless_the_policy_is_exactly_true():
    d = make(pool_policy_on=False)
    d["status"]["payload"]["accounts"][0]["cap_walled"] = True
    d["queue"][0] = entry(1, d["status"]["payload"]["accounts"][0], "active")
    assert "pool OFF by ruling" in text(dom(render(d)))
    for off in ("yes", 1, {"error": "x"}, None):
        d2 = make(pool_policy_on=off)
        d2["status"]["payload"]["accounts"][0]["cap_walled"] = True
        assert "pool OFF by ruling" in text(dom(render(d2)))
    on = make(pool_policy_on=True)
    on["status"]["payload"]["accounts"][0]["cap_walled"] = True
    assert "pool OFF by ruling" not in text(dom(render(on)))


# ---------------------------------------------------------------- B4: controls, bodies, dialogs
def test_every_control_sits_in_a_closed_edit_disclosure_and_names_a_dialog():
    root = dom(render())
    for slug in ("alpha", "bravo", "delta", "charlie"):
        r = row(root, slug)
        det = find(r, "details")
        assert len(det) == 1 and "open" not in det[0].attrs
        assert text(find(det[0], "summary")[0]) == "Edit"
        for ep, btns in controls(root, slug).items():
            for b in btns:
                dlg = dialog_for(root, b)
                assert text(find(dlg, "h2")[0]) and ep in ("/switch", "/park", "/cap", "/threshold")
    # no data-post button lives outside an Edit disclosure
    for b in find(root, "button"):
        if "data-post" in b.attrs:
            anc, ok = b.parent, False
            while anc is not None:
                ok = ok or anc.tag == "details"
                anc = anc.parent
            assert ok


def test_the_four_controls_post_todays_bodies_to_todays_endpoints():
    root = dom(render())
    c = controls(root, "bravo")
    assert json.loads(c["/switch"][0].attrs["data-body"]) == {"account": "bravo"}
    assert json.loads(c["/park"][0].attrs["data-body"]) == {
        "account": "bravo@example.com",
        "park": True,
    }
    capb, thrb = c["/cap"][0], c["/threshold"][0]
    cap_id = capb.attrs["data-input"].split(":", 5)[5]
    thr_id = thrb.attrs["data-input"].split(":", 5)[5]
    assert capb.attrs["data-input"].startswith("cap:int:0:100:nullable:")
    assert thrb.attrs["data-input"].startswith("threshold:float:50:100:nullable:")
    assert json.loads(capb.attrs["data-body"]) == {"account": "bravo@example.com"}
    assert json.loads(thrb.attrs["data-body"]) == {"account": "bravo@example.com"}
    cap_in, thr_in = find(root, "input", id=cap_id), find(root, "input", id=thr_id)
    assert (
        len(cap_in) == 1
        and cap_in[0].attrs["type"] == "number"
        and cap_in[0].attrs["value"] == "80"
    )
    assert (
        thr_in[0].attrs["min"] == "50"
        and thr_in[0].attrs["max"] == "100"
        and thr_in[0].attrs["value"] == ""
    )


def test_a_rotate_at_of_87_5_survives_to_the_field_and_the_dialog_states_typed_values():
    d = make()
    d["status"]["payload"]["accounts"][1]["session_threshold"] = 87.5
    root = dom(render(d))
    thr = controls(root, "bravo")["/threshold"][0]
    thr_id = thr.attrs["data-input"].split(":", 5)[5]
    assert find(root, "input", id=thr_id)[0].attrs["value"] == "87.5"
    for ep in ("/cap", "/threshold"):
        b = controls(root, "bravo")[ep][0]
        dlg = dialog_for(root, b)
        spans = find(dlg, "span", **{"data-value-of": b.attrs["data-input"].split(":", 5)[5]})
        assert len(spans) == 1
        assert "rotation" in text(dlg)  # states the consequence
    park = dialog_for(root, controls(root, "bravo")["/park"][0])
    assert "out of service" in text(park)
    sw = dialog_for(root, controls(root, "bravo")["/switch"][0])
    assert "cached prefix" in text(sw)


def test_controls_appear_only_on_the_rows_today_shows_them_on():
    root = dom(render())
    assert "/switch" not in controls(root, "alpha")  # the active row
    assert "/switch" not in controls(root, "charlie")  # a parked row
    assert "/switch" in controls(root, "delta")  # walled rows still switch
    # a parked row offers Enable where others offer Disable, and its cap field is blank
    cb = controls(root, "charlie")
    assert json.loads(cb["/park"][0].attrs["data-body"])["park"] is False
    assert text(cb["/park"][0]) == "Enable"
    assert text(controls(root, "bravo")["/park"][0]) == "Disable"
    cap_id = cb["/cap"][0].attrs["data-input"].split(":", 5)[5]
    assert find(root, "input", id=cap_id)[0].attrs["value"] == ""
    # the ghost return row and the pending row carry no controls at all
    assert not find(find(root, "tr", **{"data-row": "return"})[0], "button")
    assert not find(find(root, "tr", **{"data-acct": "echo"})[0], "button")


def test_badges_show_parked_reserved_walled_cap_and_cache_age():
    d = make()
    pl = d["status"]["payload"]
    pl["accounts"][1].update(source="cache", age_s=7200)
    root = dom(render(d))
    assert "PARKED — out of service" in text(row(root, "charlie"))
    assert "RESERVED — fleet excluded" in text(row(root, "delta"))
    assert "WALLED" not in text(row(root, "charlie"))
    assert "cap 80%" in text(row(root, "bravo"))
    assert "cached 2h ago" in text(row(root, "bravo"))
    walled = make()
    walled["status"]["payload"]["accounts"][2]["cap_walled"] = False
    assert "WALLED" in text(row(dom(render(walled)), "delta"))


def test_a_slug_or_email_that_fails_its_pattern_loses_those_controls():
    d = make()
    pl = d["status"]["payload"]
    pl["accounts"][1]["slugs"] = ["Bad Slug!"]
    pl["accounts"][2]["email"] = "not-an-email"
    d["queue"][1] = entry(2, pl["accounts"][1], "eligible")
    d["queue"][2] = entry(3, pl["accounts"][2], "returns", NOW + 86400)
    root = dom(render(d))
    bad_slug = controls(root, "Bad Slug!")
    assert "/switch" not in bad_slug and "/park" in bad_slug
    assert "active" in text(row(root, "Bad Slug!"))  # the muted word stays
    # no email: no disable / cap / rotate-at; the switch stays, keyed on the slug
    assert set(controls(root, "delta")) == {"/switch"}


def test_every_id_is_unique_and_a_hostile_value_never_reaches_markup_raw():
    d = make()
    d["status"]["payload"]["fleet_warnings"] = ["<script>alert(1)</script>"]
    d["status"]["payload"]["accounts"][1]["email"] = 'x"><img src=1>@example.com'
    html = render(d)
    assert "<script>alert" not in html and "<img src=1>" not in html
    ids = [n.attrs["id"] for n in dom(html).walk() if "id" in n.attrs]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------- B5: no reading, freshness
def test_no_reading_at_all_shows_the_error_in_words_and_no_controls():
    root = dom(render(make(status={"error": "no reading yet"}, queue={"error": "no reading yet"})))
    t = text(root)
    assert "no reading yet" in t
    assert not find(root, "button", **{"data-kind": "primary"}) and not find(root, "details")
    assert not [b for b in find(root, "button") if "data-post" in b.attrs]


def test_a_queue_error_with_a_payload_is_also_the_error_state():
    root = dom(render(make(queue={"error": "KeyError: boom"})))
    assert "KeyError: boom" in text(root)
    assert not find(root, "details")


def test_the_view_carries_a_freshness_stamp_and_its_cadence():
    root = dom(render())
    stamps = find(root, "time")
    assert len(stamps) == 1 and stamps[0].attrs["data-cadence"] == "20"
    assert float(stamps[0].attrs["data-ts"]) == NOW - 5
    assert [n.attrs["data-refresh-s"] for n in root.walk() if "data-refresh-s" in n.attrs] == ["20"]
    unread = dom(
        render(
            make(
                status={
                    "payload": make()["status"]["payload"],
                    "read_at": None,
                    "probe_failure": None,
                }
            )
        )
    )
    assert "Not read yet" in text(unread)


def test_the_view_never_imports_the_dashboard_module():
    src = Path(accounts.__file__).read_text()
    imports = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    assert not [ln for ln in imports if "quota_dashboard" in ln]


# ---------------------------------------------------------------- wave review round 1 (slice C)
def _with(d, i, **upd):
    """Update account ``i`` in the payload and re-point its queue entries at the new dict."""
    a = d["status"]["payload"]["accounts"][i]
    a.update(upd)
    for e in d["queue"]:
        if a["slugs"] and e["slug"] == a["slugs"][0]:
            e["acct"] = a
    return a


def _cells(root, slug):
    return [text(c) for c in find(row(root, slug), "td")]


def test_two_slugless_accounts_get_distinct_disclosure_ids():  # C1
    d = make()
    one = acct("x", "one@example.com")
    two = acct("x", "two@example.com")
    one["slugs"] = two["slugs"] = []
    d["status"]["payload"]["accounts"] += [one, two]
    d["queue"] += [
        {"n": 6, "slug": "?", "acct": one, "kind": "eligible", "returns_at": None},
        {"n": 7, "slug": "?", "acct": two, "kind": "eligible", "returns_at": None},
    ]
    root = dom(render(d))
    ids = [n.attrs["id"] for n in root.walk() if "id" in n.attrs]
    assert len(ids) == len(set(ids))
    assert len(find(root, "details")) >= 6


def test_an_unknown_cache_age_is_said_in_words():  # C2
    d = make()
    a = _with(d, 0, source="cache", age_s=None)
    a["five_hour"]["resets_at_epoch"] = NOW - 5
    out = _cells(dom(render(d)), "alpha")[0]
    assert "an unknown time ago" in out and "last read ," not in out


def test_the_governor_route_words_and_the_empty_error_come_from_the_catalogue():  # C3
    from dashboard_ui import strings

    swapped = {
        **strings.CATALOGUE,
        "accounts.gov.route.pool": "POOLWORD",
        "accounts.gov.route.ob": "OBWORD",
        "accounts.gov.route.diagnose": "DIAGWORD",
        "accounts.error_none": "NOREADWORD",
    }
    d = make()
    d["status"]["payload"]["accounts"][0]["cap_walled"] = True
    with strings.use(swapped):
        out = text(dom(render(d)))
        assert "routine → POOLWORD" in out and "incident → DIAGWORD" in out
        assert "NOREADWORD" in text(dom(render(make(status={}, queue=[]))))
        calm = text(dom(render(make())))
        assert "routine → OBWORD" in calm and "ob@" not in calm


def test_missing_configuration_keys_degrade_instead_of_crashing_the_view():  # C4
    for key in ("trigger_threshold", "five_hour_s", "seven_day_s", "slug_re", "email_re"):
        d = make()
        del d[key]
        assert find(dom(render(d)), "table"), key
    d = make()
    del d["trigger_threshold"]
    assert "unknown" in text(dom(render(d)))
    d = make()
    del d["slug_re"]
    assert "/switch" not in controls(dom(render(d)), "bravo")


def test_cap_and_rotate_at_dialogs_read_correctly_for_a_number_or_a_clear():  # C5
    root = dom(render())
    for ep in ("/cap", "/threshold"):
        body = text(dialog_for(root, controls(root, "bravo")[ep][0]))
        # app.js fills the value span with the typed number, or the word "clear" when empty
        assert "in percent" in body and '"clear"' in body
        assert " %" not in body  # no unit glued after a value that may read "clear"


def test_a_string_probe_failure_is_its_own_reason():  # C6
    d = make()
    d["status"]["probe_failure"] = "timed out"
    assert "timed out" in text(dom(render(d)))


@pytest.mark.parametrize(("given", "want"), [(2, "5"), (4.9, "5"), (7, "7"), (None, "20")])
def test_refresh_below_five_floors_to_five(given, want):
    root = dom(render(make(refresh_s=given)))
    assert [n.attrs["data-refresh-s"] for n in root.walk() if "data-refresh-s" in n.attrs] == [want]


def test_a_passed_reset_with_a_fresh_cache_age_still_reads_rolled_over():
    d = make()
    a = _with(d, 1, source="cache", age_s=10)
    a["five_hour"]["resets_at_epoch"] = NOW - 1
    assert "idle" in _cells(dom(render(d)), "bravo")[0]


def test_the_active_account_with_a_rolled_over_cache_says_unknown():
    d = make()
    _with(d, 0, source="cache", age_s=20 * 3600)
    out = _cells(dom(render(d)), "alpha")[0]
    assert "unknown" in out and "re-reads on next use" in out and "5h window" in out
    assert "idle" not in out


def test_fable_and_weekly_cells_use_the_seven_day_window_under_a_rollover():
    d = make()
    _with(d, 1, source="cache", age_s=6 * 3600)  # past 5h, inside 7d, nothing reset yet
    cells = _cells(dom(render(d)), "bravo")
    assert "idle" in cells[0]
    assert "left" in cells[1] and "left" in cells[2]
    assert "idle" not in cells[1] + cells[2]


def test_the_cap_field_is_bounded_at_100():
    root = dom(render())
    cap_id = controls(root, "bravo")["/cap"][0].attrs["data-input"].split(":", 5)[5]
    f = find(root, "input", id=cap_id)[0]
    assert f.attrs["min"] == "0" and f.attrs["max"] == "100"


def test_a_parked_account_shows_no_cap_badge_and_no_reserved_badge():
    d = make()
    _with(d, 3, cap_walled=True)  # charlie: parked with weekly_cap 50
    out = text(row(dom(render(d)), "charlie"))
    assert "PARKED" in out and "cap 50%" not in out and "RESERVED" not in out


def test_a_queue_holding_only_a_return_row_still_shows_the_no_accounts_banner():
    d = make()
    d["queue"] = [d["queue"][3]]
    assert "No fleet accounts reporting yet." in text(dom(render(d)))


def test_a_pending_row_failing_the_slug_pattern_is_dropped():
    d = make()
    d["status"]["payload"]["pending"] = ["echo", "Bad Pending!"]
    root = dom(render(d))
    assert find(root, "tr", **{"data-acct": "echo"})
    assert not find(root, "tr", **{"data-acct": "Bad Pending!"})


def test_a_walled_governor_is_critical():
    d = make()
    d["status"]["payload"]["accounts"][0]["cap_walled"] = True

    def gov(markup):
        return [c for c in find(dom(markup), "article") if "Quota governor" in text(c)][0]

    card = gov(render(d))
    assert any(b.attrs.get("data-severity") == "critical" for b in card.walk())
    calm = gov(render())
    assert not any(b.attrs.get("data-severity") == "critical" for b in calm.walk())


def test_hostile_account_text_is_escaped_in_labels_and_dialogs():
    d = make(email_re=".+")
    _with(d, 1, email='"><img src=x onerror=1>@example.com')
    html = render(d)
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html


@pytest.mark.parametrize("bad", [-5, -1, float("nan"), float("inf"), 1e30], ids=repr)
def test_a_bad_read_at_drops_the_stamp_and_the_view_still_renders(bad):
    """A broken probe read time costs the view its stamp, never the whole view."""
    good = make()
    root = dom(render(make(status={**good["status"], "read_at": bad})))
    stamps = find(root, "time")
    assert stamps and all("data-ts" not in s.attrs for s in stamps)
    assert "alpha@example.com" in text(root)


# ---------------------------------------------------------------- wave review round 2 (slice C)
def _gov(markup):
    return [c for c in find(dom(markup), "article") if "Quota governor" in text(c)][0]


def _gov_severity(card):
    return [b.attrs["data-severity"] for b in card.walk() if "data-severity" in b.attrs][0]


def test_with_the_pool_off_a_hot_account_is_not_a_warning():  # C-r2-1
    off = make(pool_policy_on=False, reserve_pct=10.0)  # alpha's 30% max window is over the reserve
    card = _gov(render(off))
    assert "pool OFF by ruling" in text(card) and _gov_severity(card) == "ok"
    on = make(pool_policy_on=True, reserve_pct=10.0)
    assert _gov_severity(_gov(render(on))) == "warning"


def test_a_missing_threshold_never_reads_unknown_percent():  # C-r2-2
    d = make()
    del d["trigger_threshold"]
    t_all = text(dom(render(d)))
    assert "unknown%" not in t_all and "at unknown" not in t_all
    assert "configured line" in t_all and "empty = fleet default)" in t_all


def test_a_fractional_cap_is_shown_whole_and_never_prefilled_truncated():  # C-r2-3, wave r3
    d = make()
    _with(d, 1, weekly_cap=80.5)
    root = dom(render(d))
    assert "cap 80.5%" in text(row(root, "bravo"))
    spec = controls(root, "bravo")["/cap"][0].attrs["data-input"]
    cap_id = spec.split(":", 5)[5]
    # pre-filled as stored: never "80" (a resubmit lowers it) and never "" (an untouched Set clears it);
    # the field's int grammar refuses "80.5" client-side, so nothing posts until the operator types
    assert find(root, "input", id=cap_id)[0].attrs["value"] == "80.5"
    assert spec.startswith("cap:int:")
    assert "cap 80%" in text(row(dom(render(make())), "bravo"))


def test_a_missing_reserve_is_unknown_not_zero():  # C-r2-4
    d = make()
    del d["reserve_pct"]
    card = _gov(render(d))
    assert "reserve unknown" in text(card) and "reserve 0%" not in text(card)
    assert "routine → unknown" in text(card)
