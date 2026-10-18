"""T02 — the external-services inventory module (plan 2026-10-18-plan-1-external-services-inventory).

`dashboard_ui/inventory.py`: `load` (the reader, fed fake connections that answer by SQL substring as
`tests/test_external_services_chain.py` does), `render` (the section, parsed back with a small DOM so
every assertion reads structure, not substrings) and `credit_cell`. One test per Behavior Contract row,
then the invariants those rows are instances of.

Cobra check (D-253): the cheapest way to pass "the attention list is right" without the outcome is to
assert the rules only on the rows that trip them. Every rule is pinned in BOTH directions on the same
fixture (49 h in, 47 h out, healthy out, paid-without-credential out), and the counts are recomputed
here from the fixture rows rather than read back from the output they check.
"""

from __future__ import annotations

import math
import re
import sys
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.external_services_fixture import CENSUS_NOW, census_rows

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "sysadmin"))
sys.path.insert(0, str(_ROOT / "scripts"))

from dashboard_ui import inventory  # noqa: E402
from dashboard_ui.strings import t  # noqa: E402

H = 3600.0
NOW = CENSUS_NOW


# ---------------------------------------------------------------- a small DOM
class El:
    def __init__(self, tag: str, attrs: dict[str, str | None], parent: El | None):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.kids: list[El | str] = []

    def walk(self):
        for k in self.kids:
            if isinstance(k, El):
                yield k
                yield from k.walk()

    def find(self, tag: str | None = None, **attrs) -> list[El]:
        out = []
        for el in self.walk():
            if tag is not None and el.tag != tag:
                continue
            if all(
                (k.replace("_", "-") in el.attrs)
                if v is True
                else el.attrs.get(k.replace("_", "-")) == v
                for k, v in attrs.items()
            ):
                out.append(el)
        return out

    def text(self) -> str:
        return "".join(k if isinstance(k, str) else k.text() for k in self.kids)

    def within(self, ancestor: El) -> bool:
        el = self.parent
        while el is not None:
            if el is ancestor:
                return True
            el = el.parent
        return False


class _Parser(HTMLParser):
    VOID = {"input", "br", "hr", "img", "meta", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = El("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        el = El(tag, dict(attrs), self.cur)
        self.cur.kids.append(el)
        if tag not in self.VOID:
            self.cur = el

    def handle_endtag(self, tag):
        el = self.cur
        while el is not self.root and el.tag != tag:
            el = el.parent
        if el is not self.root:
            self.cur = el.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def dom(markup: str) -> El:
    p = _Parser()
    p.feed(str(markup))
    return p.root


def render(rows, *, now=NOW, synced_at=NOW - H, classified_at=NOW - H, interactive=True):
    return inventory.render(
        rows, now=now, synced_at=synced_at, classified_at=classified_at, interactive=interactive
    )


def attention_card(root: El) -> El:
    (card,) = [
        c for c in root.find("article") if t("services.inv.attn.title") == c.find("h3")[0].text()
    ]
    return card


def base(provider="p", **kw) -> dict:
    row = {
        "provider": provider, "category": "search", "cost": "free", "url": "", "status": "active",
        "keys": 0, "unattributed": 0, "projects": [], "account": "", "balance": None, "unit": "",
        "credit_at": None, "renews": "", "price": "",
    }  # fmt: skip
    row.update(kw)
    return row


# ---------------------------------------------------------------- fake connections (the chain suite's shape)
class FakeCursor:
    def __init__(self, conn):
        self.conn, self.rows, self.sql = conn, [], ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, *a):
        self.sql = sql
        self.conn.events.append(("sql", sql))
        self.rows = next(v for k, v in self.conn.answers.items() if k in sql)

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        if self.rows:
            return self.rows[0]
        return (None,) if self.conn.empty_is_tuple and "max(last_seen)" in self.sql else None


class FakeConn:
    def __init__(self, answers=None, *, empty_is_tuple=False):
        self.answers = {
            "max(last_seen)": [],
            "FROM services": [],
            "information_schema": [(1,)],
            "FROM api_keys": [],
            "credit_snapshots": [],
            "FROM subscriptions": [],
        }
        self.answers.update(answers or {})
        self.empty_is_tuple, self.events = empty_is_tuple, []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        raise AssertionError("the reader never commits")

    def rollback(self):
        raise AssertionError("the reader never rolls back")

    def close(self):
        raise AssertionError("the reader never closes the caller's connection")


SERVICES = [
    (1, "apify", "scraping", "paid", "https://apify.com", "active"),
    (2, "mystery", None, None, None, None),
    (3, "github", "code", "free", "https://github.com", "active"),
    (4, "vercel", "hosting", "freemium", "https://vercel.com", "active"),
]
KEYS = [
    (1, ["alpha"], "me@x.io", "credential"),
    (2, ["beta"], None, "credential-unattributed"),
    (3, ["gamma"], None, "code-host"),
    (99, ["ghost"], None, "credential"),  # a service the registry does not hold: skipped
]


# ---------------------------------------------------------------- 1. load
@pytest.mark.parametrize("empty_is_tuple", [False, True], ids=["fetchone-None", "fetchone-(None,)"])
@pytest.mark.parametrize("hooked", [False, True], ids=["no-hook", "hook"])
def test_load_returns_credit_parts_and_an_epoch_or_none_in_both_empty_shapes(
    empty_is_tuple, hooked
):
    old = datetime(2026, 9, 1, 6, 0, tzinfo=UTC)
    conn = FakeConn(
        {
            "FROM services": SERVICES,
            "FROM api_keys": KEYS,
            "credit_snapshots": [(1, 12.5, "usd", old)],
            "FROM subscriptions": [(1, 20, "usd", None)],
        },
        empty_is_tuple=empty_is_tuple,
    )
    hook_calls = []

    def hook(cur):
        hook_calls.append(cur)
        conn.events.append(("hook", None))

    rows, synced_at = inventory.load(conn, **({"before_query": hook} if hooked else {}))
    by = {r["provider"]: r for r in rows}
    assert synced_at is None
    assert "credit" not in by["apify"]
    assert (by["apify"]["balance"], by["apify"]["unit"], by["apify"]["credit_at"]) == (
        12.5,
        "usd",
        old.timestamp(),
    )
    assert by["apify"]["price"] == "20 usd" and by["apify"]["account"] == "me@x.io"
    assert by["github"]["balance"] is None and by["github"]["credit_at"] is None
    assert (by["apify"]["keys"], by["apify"]["unattributed"]) == (1, 0)
    assert (by["mystery"]["keys"], by["mystery"]["unattributed"]) == (0, 1)
    assert (by["github"]["keys"], by["github"]["unattributed"]) == (
        0,
        0,
    )  # a call-site row proves use, never a key
    assert by["apify"]["projects"] == ["alpha"]
    assert by["mystery"]["projects"] == ["beta"] and by["github"]["projects"] == ["gamma"]
    assert (by["mystery"]["category"], by["mystery"]["cost"], by["mystery"]["status"]) == (
        "?",
        "?",
        "?",
    )
    assert [(r["category"], r["provider"]) for r in rows] == sorted(
        (r["category"], r["provider"]) for r in rows
    )
    sqls = [s for kind, s in conn.events if kind == "sql"]
    assert len(sqls) == 6  # the five queries of today plus max(last_seen): no other SQL
    if hooked:
        assert len(hook_calls) == 6
        assert [k for k, _ in conn.events] == ["hook", "sql"] * 6  # the hook ran before EACH query
    else:
        assert [k for k, _ in conn.events] == ["sql"] * 6


def test_load_keeps_the_literal_substrings_the_chain_fakes_dispatch_on():
    conn = FakeConn()
    inventory.load(conn)
    joined = "\n".join(s for _, s in conn.events)
    for needle in (
        "FROM services",
        "information_schema",
        "FROM api_keys",
        "credit_snapshots",
        "FROM subscriptions",
        "fetched_at DESC, id DESC",
    ):
        assert needle in joined, needle


def test_load_maps_max_last_seen_to_an_epoch_and_never_touches_the_connection():
    seen = datetime(2026, 10, 17, 11, 30, tzinfo=UTC)
    conn = FakeConn({"max(last_seen)": [(seen,)]})
    _rows, synced_at = inventory.load(conn)  # FakeConn raises on commit, rollback and close
    assert synced_at == seen.timestamp() and isinstance(synced_at, float)


def test_load_without_the_kind_column_counts_every_api_key_row_as_a_key():
    conn = FakeConn(
        {
            "FROM services": SERVICES[:1],
            "information_schema": [],
            "FROM api_keys": [(1, ["a"], None, "credential")],
        }
    )
    rows, _ = inventory.load(conn)
    assert rows[0]["keys"] == 1
    assert any("'credential'" in s for k, s in conn.events if k == "sql")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -5, -0.1, None, "x"])
def test_load_refuses_a_balance_and_a_price_that_are_not_finite_and_non_negative(bad):
    conn = FakeConn(
        {
            "FROM services": SERVICES[:1],
            "credit_snapshots": [(1, bad, "usd", datetime(2026, 9, 1, tzinfo=UTC))],
            "FROM subscriptions": [(1, bad, "usd", None)],
        }
    )
    (row,), _ = inventory.load(conn)
    assert (row["balance"], row["credit_at"], row["price"]) == (None, None, "")


def test_load_accepts_zero_as_a_balance_and_a_price():
    conn = FakeConn(
        {
            "FROM services": SERVICES[:1],
            "credit_snapshots": [(1, 0, "usd", datetime(2026, 9, 1, tzinfo=UTC))],
            "FROM subscriptions": [(1, 0, "usd", None)],
        }
    )
    (row,), _ = inventory.load(conn)
    assert (row["balance"], row["price"]) == (0.0, "0 usd")


def test_registry_connect_passes_keyword_arguments_through_and_none_is_todays_call(monkeypatch):
    import registry_db

    calls = []
    monkeypatch.setattr(
        registry_db.psycopg2, "connect", lambda *a, **k: calls.append((a, k)) or "c"
    )
    monkeypatch.setenv("SERVICES_REGISTRY_DSN", "postgresql:///x")
    assert registry_db.connect() == "c"
    assert registry_db.connect(connect_timeout=2, options="-c statement_timeout=2000") == "c"
    assert calls == [
        (("postgresql:///x",), {}),
        (("postgresql:///x",), {"connect_timeout": 2, "options": "-c statement_timeout=2000"}),
    ]


# ---------------------------------------------------------------- credit_cell
def test_credit_cell_is_stale_strictly_past_48_hours_and_refuses_non_finite_and_negative():
    assert inventory.STALE_AFTER_H == 48
    assert inventory.credit_cell(12.5, "usd", NOW - 20 * H, NOW) == "12.5 usd"
    assert inventory.credit_cell(12.5, "usd", NOW - 5 * 86400, NOW) == "⚠ 12.5 usd (5d old)"
    assert inventory.credit_cell(1, "usd", NOW - 48 * H, NOW) == "1 usd"  # the boundary, both sides
    assert inventory.credit_cell(1, "usd", NOW - 48 * H - 1, NOW).startswith("⚠ 1 usd")
    assert inventory.credit_cell(3, None, None, NOW) == "3"
    assert inventory.credit_cell(3, "usd", NOW + 9 * H, NOW) == "3 usd"  # clock skew is not stale
    for bad in (None, float("nan"), float("inf"), -1, True):
        assert inventory.credit_cell(bad, "usd", NOW - 99 * H, NOW) == ""
    assert (
        inventory.credit_cell(2, "usd", float("nan"), NOW) == "2 usd"
    )  # an unusable time flags nothing


# ---------------------------------------------------------------- 2. URLs
def test_only_an_http_or_https_url_link_accepts_whole_is_a_link():
    urls = {
        "ok": "https://ok.example",
        "upper": "HTTPS://UP.example",
        "path": "/admin",
        "frag": "#x",
        "space": "http://a b",
        "js": "javascript:alert(1)",
        "empty": "",
        "bare": "https://",
        "ctrl": "https://a\x00b.example",
    }
    rows = [base(name, url=url) for name, url in urls.items()]
    for interactive in (True, False):
        root = dom(render(rows, interactive=interactive))
        hrefs = {a.attrs["href"] for a in root.find("a")}
        assert hrefs == {"https://ok.example"} | ({"https://"} if "https://" in hrefs else set()), (
            hrefs
        )
        text = root.text()
        for name in urls:  # every other provider still shows its name, as plain text
            assert name in text
        (ok,) = [a for a in root.find("a") if a.attrs["href"] == "https://ok.example"]
        assert "ok" in ok.text()


# ---------------------------------------------------------------- 3. the census
def census_expectations(rows):
    return {
        "total": len(rows),
        "paid": sum(r["cost"] in ("paid", "freemium") for r in rows),
        "free": sum(r["cost"] in ("free", "self-host") for r in rows),
        "untriaged": sum(r["category"] == "?" for r in rows),
        "attention": sum(r["status"] in ("unidentified", "retiring") for r in rows),
        "categories": len({r["category"] for r in rows} - {"?"}),
        "projects": len({p for r in rows for p in r["projects"]}),
        "credentials": sum(r["keys"] > 0 for r in rows),
        "unattributed": sum(r["unattributed"] for r in rows),
        "renewals": sum(bool(r["renews"]) for r in rows),
    }


def test_the_fixture_is_the_census():
    rows = census_rows()
    from collections import Counter

    assert len(rows) == 466
    assert Counter(r["cost"] for r in rows) == {
        "?": 351,
        "paid": 49,
        "freemium": 34,
        "free": 19,
        "self-host": 13,
    }
    assert Counter(r["status"] for r in rows) == {
        "?": 331, "active": 113, "unidentified": 20, "retired": 1, "retiring": 1,
    }  # fmt: skip
    real = [r for r in rows if r["category"] not in ("?", "unidentified")]
    assert len(real) == 115 and len({r["category"] for r in real}) == 17
    assert max(Counter(r["category"] for r in real).values()) == 24
    assert sum(r["keys"] > 0 for r in rows) == 97
    assert len({p for r in rows for p in r["projects"]}) == 36
    assert sum(1 for r in real if not r["url"].startswith("https://")) == 5
    assert sum(r["balance"] is not None for r in rows) == 1
    assert census_rows(cost="paid")[7]["cost"] == "paid"
    assert census_rows(provider=lambda i: f"n{i}")[3]["provider"] == "n3"


def test_the_census_renders_attention_eighteen_tables_one_queue_and_the_counts_by_formula():
    rows = census_rows()
    root = dom(render(rows, classified_at=NOW - 90 * 86400))
    want = census_expectations(rows)
    assert (want["total"], want["paid"], want["free"], want["untriaged"], want["attention"]) == (
        466,
        83,
        32,
        331,
        21,
    )

    captions = [c for c in root.find("caption") if c.attrs["id"].startswith("tbl-")]
    assert len(captions) == 18
    assert (
        t("services.inv.cat.unidentified") in captions[-1].text()
    )  # the Unidentified table is last
    assert all(t("services.inv.cat.unidentified") not in c.text() for c in captions[:-1])
    assert [c.text() for c in captions[:-1]] == sorted(c.text() for c in captions[:-1])

    # 331 untriaged providers: one section of list entries, never a table row
    (queue,) = [d for d in root.find("details") if d.attrs["id"].startswith("queue-")]
    entries = queue.find("li", data_filter_item=True)
    assert len(entries) == 331
    assert not any("untr-" in tr.text() for tr in root.find("tr"))
    assert t("services.inv.untriaged.title", n=331) in queue.find("summary")[0].text()

    # an unidentified row is in Needs attention AND in the Unidentified table
    card = attention_card(root)
    (many,) = [d for d in card.find("details") if d.attrs["id"].startswith("attn-unidentified")]
    listed = [li.text() for li in many.find("li")]
    assert sorted(listed) == sorted(f"unid-{k:02d}" for k in range(20))
    assert (
        t("services.inv.attn.many.unidentified", n=20, hours=48) in many.find("summary")[0].text()
    )
    table_rows = [tr for tr in root.find("tr") if tr.text().startswith("unid-")]
    assert len(table_rows) == 20
    # census: the stalled classifier, "20 providers unidentified", and the one retiring provider by name
    assert len(card.find("ul")[0].kids) == 3
    assert "real-003: retiring" in card.text()
    assert t("services.inv.attn.classifier_stale", hours=48, n=331) in card.text()

    # the summary counts and the More counts each equal their formula
    for name in ("total", "paid", "free", "untriaged", "attention"):
        (li,) = root.find("li", data_count=name)
        assert re.search(rf"\b{want[name]}\b", li.text()), (name, li.text())
    for name, value in (
        ("categories", want["categories"]),
        ("projects", want["projects"]),
        ("credit_tracked", 1),
        ("credit_stale", 0),
        ("renewals", want["renewals"]),
        ("credentials", want["credentials"]),
        ("unattributed", want["unattributed"]),
    ):
        (tr,) = root.find("tr", data_count=name)
        assert tr.find("td")[-1].text() == str(value), name
    assert want["categories"] == 18 and want["projects"] == 36 and want["credentials"] == 97

    # every provider once: 135 table rows + 331 entries = 466 filter items; the attention list holds none
    items = root.find(None, data_filter_item=True)
    assert len(items) == 466 and not any(i.within(card) for i in items)


def test_group_summaries_carry_the_provider_paid_and_credential_counts_which_sum_to_the_tables():
    root = dom(render(census_rows()))
    groups = [d for d in root.find("details") if d.attrs["id"].startswith("grp-")]
    assert len(groups) == 18
    creds = 0
    for g in groups:
        rows_ = [tr for tr in g.find("tr") if tr.parent.tag == "tbody"]
        paid = sum(tr.find("td")[0].text() == "Paid" for tr in rows_)
        summary = g.find("summary")[0].text()
        cred = sum(tr.find("td")[2].text().split()[0] != "0" for tr in rows_)
        assert t("services.inv.group.counts", n=len(rows_), paid=paid, cred=cred) in summary
        creds += cred
    assert creds == 92  # the group summaries' credential counts sum to 92 (97 less 5 untriaged)


# ---------------------------------------------------------------- 4. the attention rules
def rule_rows():
    return [
        base("stale49", balance=5.0, unit="usd", credit_at=NOW - 49 * H, category="a"),
        base("unattr", unattributed=2, category="a"),
        base("unid", status="unidentified", category="unidentified", cost="?"),
        base("retire", status="retiring", category="a"),
        base("fresh47", balance=5.0, unit="usd", credit_at=NOW - 47 * H, category="a"),
        base("healthy", keys=1, cost="paid", projects=["x"], category="a"),
        base("paidnocred", cost="paid", keys=0, category="a"),
        base("queued", category="?", cost="?", status="?"),
    ]


def test_each_provider_rule_is_an_entry_and_the_near_misses_are_not():
    card = attention_card(dom(render(rule_rows())))
    text = card.text()
    for name, rule in (
        ("stale49", "stale_credit"),
        ("unattr", "unattributed"),
        ("unid", "unidentified"),
        ("retire", "retiring"),
    ):
        assert t(f"services.inv.attn.named.{rule}", name=name, hours=48) in text, rule
    for name in ("fresh47", "healthy", "paidnocred", "queued"):
        assert name not in text, name


@pytest.mark.parametrize(
    ("at", "entry"),
    [
        (NOW - 49 * H, True),
        (NOW - 47 * H, False),
        (None, True),
        (NOW - 48 * H, False),
        (NOW + 5 * H, False),
    ],
    ids=["49h", "47h", "none", "exactly-48h", "future"],
)
def test_the_registry_and_classifier_source_rules(at, entry):
    rows = rule_rows()
    reg = attention_card(dom(render(rows, synced_at=at))).text()
    cls = attention_card(dom(render(rows, classified_at=at))).text()
    reg_words = (
        t("services.inv.attn.registry_never")
        if at is None
        else t("services.inv.attn.registry_stale", hours=48)
    )
    cls_words = (
        t("services.inv.attn.classifier_never", hours=48, n=1)
        if at is None
        else t("services.inv.attn.classifier_stale", hours=48, n=1)
    )
    assert (reg_words in reg) is entry and (cls_words in cls) is entry


def test_a_stalled_classifier_over_an_empty_queue_is_not_an_entry():
    rows = [r for r in rule_rows() if r["category"] != "?"]
    text = attention_card(dom(render(rows, classified_at=NOW - 49 * H))).text()
    assert "classifier" not in text
    text = attention_card(dom(render(rows, classified_at=None))).text()
    assert "classifier" not in text


@pytest.mark.parametrize(("n", "collapsed"), [(5, False), (6, True)])
def test_five_rows_sharing_a_reason_are_named_and_six_collapse_into_one_counted_details(
    n, collapsed
):
    rows = [base(f"ret{i}", status="retiring", category="a") for i in range(n)]
    card = attention_card(dom(render(rows)))
    details = card.find("details")
    if collapsed:
        (d,) = details
        assert t("services.inv.attn.many.retiring", n=6, hours=48) in d.find("summary")[0].text()
        assert sorted(li.text() for li in d.find("li")) == sorted(f"ret{i}" for i in range(6))
    else:
        assert details == []
        for i in range(n):
            assert f"ret{i}: retiring" in card.text()


def test_a_row_with_two_reasons_appears_under_both_and_counts_once_in_needs_attention():
    rows = [base("both", status="retiring", unattributed=1, category="a")]
    root = dom(render(rows))
    text = attention_card(root).text()
    assert "both: retiring" in text and "both: credentials" in text
    (li,) = root.find("li", data_count="attention")
    assert re.search(r"\b1\b", li.text())


def test_nothing_needing_attention_says_so():
    rows = [base("fine", keys=1, projects=["x"])]
    card = attention_card(dom(render(rows)))
    assert t("services.inv.attn.none") in card.text()


# ---------------------------------------------------------------- 5. ids and the filter wire
def id_rows():
    return [
        base("www.googleapis", category="captcha", projects=["p"]),
        base("captcha", category="search"),
        base("captcha", category="?", cost="?", status="?", projects=["a", "b", "c", "d", "e"]),
        base("dup", category="dup"),
        base("dup", category="dup"),  # two rows that are the same text: still two distinct ids
    ] + [base(f"r{i}", status="retiring", category="search") for i in range(6)]


def test_every_details_has_a_slug_id_with_its_kinds_prefix_and_every_id_is_valid_and_unique():
    root = dom(render(id_rows()))
    ids = [el.attrs["id"] for el in root.walk() if "id" in el.attrs]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[A-Za-z][\w:-]*", i, re.ASCII) for i in ids)
    kinds = {"grp-": 0, "row-": 0, "untr-": 0, "attn-": 0, "queue-": 0, "more-": 0}
    for d in root.find("details"):
        assert "id" in d.attrs, d.text()[:40]
        (prefix,) = [p for p in kinds if d.attrs["id"].startswith(p)]
        kinds[prefix] += 1
    assert (
        kinds["grp-"] == 3 and kinds["untr-"] == 1 and kinds["attn-"] == 1 and kinds["queue-"] == 1
    )
    assert kinds["row-"] == 10  # every categorised row: 2 + 2 + 6, none shared by name


def test_every_filter_target_carries_a_data_f_attribute_for_each_control_name():
    root = dom(render(id_rows()))
    (group,) = root.find(None, data_filter_group=True)
    names = [c.attrs["data-filter"] for c in group.find(None, data_filter=True)]
    assert sorted(names) == ["cost", "find", "status"]
    items = group.find(None, data_filter_item=True)
    assert len(items) == len(id_rows())
    for item in items:
        for name in names:
            assert f"data-f-{name}" in item.attrs, (name, item.tag)
    sections = group.find("details", data_filter_section=True)
    assert len(sections) == 4 and all("id" in s.attrs for s in sections)
    assert len(group.find(None, data_filter_count=True)) == 4
    (status,) = group.find(None, data_filter_status=True)
    assert t("filter.shown", n=len(id_rows()), total=len(id_rows())) in status.text()


def test_the_cost_filter_is_token_mode_and_every_filter_select_offers_all_first():
    root = dom(render(id_rows()))
    for sel in root.find("select"):
        assert sel.attrs["data-filter-mode"] == "token"
        first = sel.find("option")[0]
        assert first.attrs["value"] == ""
    (cost,) = root.find("select", name="cost")
    assert first_label(cost) == t("services.inv.filter.all_costs")
    labels = [o.text() for o in cost.find("option")]
    assert t("services.inv.cost.free") in labels and t("services.inv.cost.freemium") in labels


def first_label(sel: El) -> str:
    return sel.find("option")[0].text()


def test_the_wire_is_one_group_and_the_attention_list_sits_outside_it():
    root = dom(render(census_rows()))
    (group,) = root.find(None, data_filter_group=True)
    assert not attention_card(root).within(group)
    assert group.find("p", role="status")


# ---------------------------------------------------------------- 6. interactive False
def test_the_static_render_has_no_control_no_clamp_no_button_and_no_status():
    rows = census_rows()
    markup = str(render(rows, interactive=False))
    root = dom(markup)
    assert root.find("input") == [] and root.find("select") == [] and root.find("button") == []
    assert root.find("script") == []
    for needle in (
        "data-filter",
        "data-clamp",
        "data-f-",
        "<button",
        "<input",
        "<select",
        'role="status"',
    ):
        assert needle not in markup, needle
    assert t("services.inv.static.never") not in markup
    assert re.search(r"Registry synced \d{4}-\d\d-\d\d \d\d:\d\d [+-]\d\d:\d\d", markup)
    assert re.search(r"Snapshot written \d{4}-\d\d-\d\d \d\d:\d\d [+-]\d\d:\d\d", markup)
    assert t("services.inv.static.legend", hours=48) in markup
    assert "<time" not in markup  # no script to tick a relative stamp


def test_the_static_render_says_never_synced_and_lists_project_names_past_three_in_a_native_details():
    rows = [base("many", category="?", cost="?", status="?", projects=["a", "b", "c", "d", "e"])]
    markup = str(render(rows, synced_at=None, interactive=False))
    assert t("services.inv.static.never") in markup
    root = dom(markup)
    (d,) = [x for x in root.find("details") if x.attrs["id"].startswith("untr-")]
    assert (
        "a, b, c, d, e" in d.text()
        and t("services.inv.more_names", n=2) in d.find("summary")[0].text()
    )
    shown = root.find("li")  # the three names a reader sees before opening it
    assert any("a, b, c" in li.text() for li in shown)


def test_the_live_render_has_a_fresh_stamp_of_the_registrys_own_time():
    root = dom(render(census_rows(), synced_at=NOW - 7 * H))
    (stamp,) = root.find("time")
    assert float(stamp.attrs["data-ts"]) == NOW - 7 * H
    root = dom(render(census_rows(), synced_at=None))
    assert t("fresh.never") in root.find("time")[0].text()


# ---------------------------------------------------------------- 7. escaping and secrets
EVIL = "</script><img src=x onerror=1>"
SECRET = "sk-live-0123456789abcdefSECRET"


@pytest.mark.parametrize("interactive", [True, False])
def test_a_credential_value_appears_nowhere_and_a_hostile_name_renders_as_text(interactive):
    rows = [
        base(
            EVIL,
            category=EVIL,
            url="https://e.example",
            projects=[EVIL],
            account=EVIL,
            value=SECRET,
        ),
        base(EVIL + "q", category="?", cost="?", status="?", url="https://q.example", value=SECRET),
        base("w", value_sha256=SECRET, secret=SECRET),
    ]
    markup = str(render(rows, interactive=interactive))
    assert SECRET not in markup
    assert "<img" not in markup and "</script>" not in markup
    assert "&lt;/script&gt;&lt;img src=x onerror=1&gt;" in markup
    root = dom(markup)
    assert root.find("img") == [] and root.find("script") == []


# ---------------------------------------------------------------- 8. speed
def test_a_5000_row_fixture_renders_in_under_200_ms():
    base_rows = census_rows()
    rows = [dict(r, provider=f"{r['provider']}-{k}") for k in range(11) for r in base_rows][:5000]
    assert len(rows) == 5000
    best = math.inf
    for _ in range(3):
        start = time.perf_counter()
        render(rows)
        best = min(best, time.perf_counter() - start)
    assert best < 0.2, best


# ---------------------------------------------------------------- invariants the rows are instances of
def test_a_row_missing_a_key_raises_keyerror():
    for key in base():
        row = base()
        del row[key]
        with pytest.raises(KeyError):
            render([row])


def test_render_is_pure_in_its_inputs_and_deterministic():
    rows = census_rows()
    first = str(render(rows))
    assert str(render(rows)) == first  # the live view's data-stamp depends on it
    assert str(render(list(reversed(rows)))) == first  # row order in is not order out


def test_an_empty_registry_is_zeros_and_empty_states_never_a_blank_page():
    for interactive in (True, False):
        root = dom(render([], interactive=interactive, synced_at=None, classified_at=None))
        for name in ("total", "paid", "free", "untriaged", "attention"):
            (li,) = root.find("li", data_count=name)
            assert re.search(r"\b0\b", li.text()), name
        text = root.text()
        assert t("services.inv.empty") in text and t("services.inv.untriaged.empty") in text


def test_render_refuses_a_now_that_is_not_a_finite_number():
    for bad in (float("nan"), float("inf"), "x", None, True):
        with pytest.raises(ValueError):
            render([], now=bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, None, "x", True, 1e30])
def test_an_unusable_time_reads_as_unknown_never_as_an_error(bad):
    rows = [base("c", balance=3.0, unit="usd", credit_at=bad)]
    for interactive in (True, False):
        markup = str(render(rows, synced_at=bad, classified_at=bad, interactive=interactive))
        assert "c" in markup
    assert (
        t("services.inv.attn.registry_never")
        in attention_card(dom(render(rows, synced_at=bad))).text()
    )


def test_a_date_stamp_survives_a_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Istanbul")
    time.tzset()
    try:
        markup = str(
            render(
                [],
                synced_at=datetime(2026, 10, 17, 11, 30, tzinfo=UTC).timestamp(),
                interactive=False,
            )
        )
        assert "Registry synced 2026-10-17 14:30 +03:00" in markup
    finally:
        monkeypatch.undo()
        time.tzset()


def test_the_module_imports_neither_the_registry_nor_the_board():
    src = (_ROOT / "scripts" / "sysadmin" / "dashboard_ui" / "inventory.py").read_text(
        encoding="utf-8"
    )
    for banned in ("registry_db", "psycopg2", "quota_dashboard"):
        assert not re.search(rf"^\s*(import|from)\s+{banned}", src, re.M), banned
    assert (_ROOT / "scripts/sysadmin/dashboard_ui/views/inventory.py").exists() is False


def test_no_catalogue_owned_english_survives_a_stand_in_catalogue():
    from dashboard_ui import strings

    stand_in = {k: v if k == "app.lang" else f"⟦{k}⟧" for k, v in strings.CATALOGUE.items()}
    with strings.use(stand_in):
        markup = str(render(census_rows()))
    english = [
        v
        for k, v in strings.CATALOGUE.items()
        if k.startswith("services.inv.") and " " in v and len(v) > 8 and "{" not in v
    ]
    assert english and not [v for v in english if v in markup]
