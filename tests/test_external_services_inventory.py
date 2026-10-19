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
from dashboard_ui.strings import CATALOGUE, t  # noqa: E402

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


def render(rows, *, now=NOW, synced_at=NOW - H, interactive=True):
    return inventory.render(rows, now=now, synced_at=synced_at, interactive=interactive)


def plural(key: str, n: int, **fields) -> str:
    """The catalogue's one/other form of ``key`` for ``n``."""
    return t(f"{key}.{'one' if n == 1 else 'other'}", n=n, **fields)


def provider_heads(root: El) -> list[El]:
    """The Provider header cell of every row in a category table (not the More counts table)."""
    return [
        th
        for cap in root.find("caption")
        if cap.attrs["id"].startswith("tbl-")
        for th in cap.parent.find("th", scope="row")
    ]


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


def test_the_first_email_and_the_last_added_whole_plan_win():
    """W-a4bc74a6 (R13): the key read is ordered by insertion and the FIRST email wins; the plan read
    is one row per service, the highest id first, and its price and renewal come from that ONE row —
    two plans never merge column by column into a price of one and a renewal of the other. "Last
    added", not "latest declared": a re-declared plan keeps its id (the upsert updates in place) and
    the table holds no recency column. The fake returns rows in the order each ORDER BY asks for and
    ignores the SQL, so each read's ORDER BY TAIL and the plan read's DISTINCT ON HEAD are asserted
    exactly; a WHERE clause or a subquery between them is not checked here."""
    conn = FakeConn(
        {
            "FROM services": SERVICES[:1],
            "FROM api_keys": [(1, ["a"], "first@x.io", "credential"), (1, ["b"], "second@x.io", "credential")],
            "FROM subscriptions": [(1, 20, "eur", None), (1, 10, "usd", "2026-01-01")],  # id DESC
        }
    )  # fmt: skip
    (row,), _ = inventory.load(conn)
    assert row["account"] == "first@x.io"
    assert (row["price"], row["renews"]) == ("20 eur", "")  # the last-added plan, whole
    sqls = [s for kind, s in conn.events if kind == "sql"]
    keys = next(s for s in sqls if "FROM api_keys" in s and "max(last_seen)" not in s)
    plans = next(s for s in sqls if "FROM subscriptions" in s)
    # exactly these clauses — a substring would also pass `id DESC` (the LAST email) on the key read
    assert re.search(r"\bORDER BY service_id, id\s*$", keys), keys
    assert re.match(r"SELECT DISTINCT ON \(service_id\) ", plans), plans
    assert re.search(r"\bORDER BY service_id, id DESC\s*$", plans), plans


def test_a_null_project_element_is_skipped():
    """W-a4bc74a6 (R14): a NULL element of `used_by_projects` used to put None beside the names, and
    `sorted()` raised — the whole read failed. A lone NULL rendered as the text "None"."""
    conn = FakeConn(
        {
            "FROM services": SERVICES[:2],
            "FROM api_keys": [(1, ["b", None, "a"], None, "credential"), (2, [None], None, "credential")],
        }
    )  # fmt: skip
    rows, _ = inventory.load(conn)
    by = {r["provider"]: r for r in rows}
    assert by["apify"]["projects"] == ["a", "b"] and by["mystery"]["projects"] == []


def test_a_negative_zero_time_is_a_plain_zero():
    """W-a4bc74a6 (R28): `_epoch` kept -0.0's sign; every other accepted value is unchanged."""
    zero = inventory._epoch(-0.0)
    assert zero == 0.0 and math.copysign(1.0, zero) == 1.0
    assert inventory._epoch(0.0) == 0.0 and inventory._epoch(5) == 5.0
    assert inventory._epoch(1e308) is None and inventory._epoch(-1) is None


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
        "bare_http": "http://",
        "nohost": "https:///path",
        "plain_http": "http://ok.example",
        "ctrl": "https://a\x00b.example",
    }
    rows = [base(name, url=url) for name, url in urls.items()]
    for interactive in (True, False):
        root = dom(render(rows, interactive=interactive))
        hrefs = {a.attrs["href"] for a in root.find("a")}
        assert hrefs == {"https://ok.example", "http://ok.example"}, hrefs
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
    root = dom(render(rows))
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
    # census: "20 providers unidentified" and the one retiring provider by name; the 331-row
    # untriaged queue raises no source entry since D-1046 retired the classifier's
    assert len(card.find("ul")[0].kids) == 2
    assert "real-003: retiring" in card.text()
    assert "classifier" not in card.text().lower()

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
        assert plural("services.inv.group.counts", len(rows_), paid=paid, cred=cred) in summary
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
def test_the_registry_source_rule_and_no_classifier_rule(at, entry):
    """The registry's source rule fires on no time or past 48 h. The classifier's rule is gone
    (D-1046): its only engine was the pool, OFF since D-181, so the entry was permanent noise —
    an untriaged queue (rule_rows carries one) never raises a source entry."""
    rows = rule_rows()
    reg = attention_card(dom(render(rows, synced_at=at))).text()
    reg_words = (
        t("services.inv.attn.registry_never")
        if at is None
        else t("services.inv.attn.registry_stale", hours=48)
    )
    assert (reg_words in reg) is entry
    assert any(r["category"] == "?" for r in rows) and "classifier" not in reg.lower()
    assert not any(k.startswith("services.inv.attn.classifier") for k in CATALOGUE)


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
def _cpu_best(fn, runs: int = 5) -> float:
    best = math.inf
    for _ in range(runs):
        start = time.process_time()
        fn()
        best = min(best, time.process_time() - start)
    return best


def _reference_workload() -> None:
    """Escape-and-format work of the render's own kind: ~20 ms of CPU on an unloaded box."""
    import html

    for i in range(60000):
        html.escape(f"u{i}@y.io", quote=True)
        f"{i:g}".strip()


def test_a_5000_row_fixture_renders_within_0_6_s_and_ten_reference_workloads():
    """CPU time (process_time), best of 5, in both modes: the render's own cost. Load stretches a
    process's CPU time (shared cores) and the reference workload alike, so the ratio of the two is
    stable; the absolute 0.6 s ceiling holds on any box."""
    rows = [  # the WORST mix: every row categorised, with a link, projects, a credit and a renewal
        base(
            f"p{i}", category=f"cat-{i % 18:02d}", cost="paid", url=f"https://p{i}.example",
            keys=2, projects=["a", "b", "c", "d"], account=f"u{i}@y.io", balance=5.0, unit="usd",
            credit_at=NOW - H, renews="2026-11-01", price="20 usd",
        )
        for i in range(5000)
    ]  # fmt: skip
    for interactive in (True, False):
        best = _cpu_best(lambda mode=interactive: render(rows, interactive=mode))
        ratio = best / _cpu_best(_reference_workload)
        assert ratio < 10, (interactive, ratio)  # measured 6.2-8.5x on this box; load cancels out
        assert best < 0.6, (interactive, best)  # an absolute ceiling no box excuses


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
        root = dom(render([], interactive=interactive, synced_at=None))
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
        root = dom(render(rows, synced_at=bad, interactive=interactive))
        heads = [th for th in root.find("th", scope="row") if th.text().startswith("c")]
        assert len(heads) == 1 and heads[0].find("a") == []
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
    import string

    from dashboard_ui import strings

    stand_in = {k: v if k == "app.lang" else f"⟦{k}⟧" for k, v in strings.CATALOGUE.items()}
    with strings.use(stand_in):
        markup = re.sub(
            r"⟦[a-z0-9_.-]+⟧", "", dom(render(census_rows())).text()
        )  # what a reader sees
    leaked = []
    for k, v in strings.CATALOGUE.items():
        if not k.startswith("services.inv."):
            continue
        for lit, *_ in string.Formatter().parse(v):  # every literal chunk of every value
            word = lit.strip(" ·,.:()+")
            if re.search("[A-Za-z]{3}", word) and word in markup:
                leaked.append((k, word))
    assert leaked == []
    assert sum(k.startswith("services.inv.") for k in strings.CATALOGUE) > 60


# ---------------------------------------------------------------- pass-1 review fixes (G1-G17)
from decimal import Decimal  # noqa: E402


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        (1234567, "1234567"),
        (1234567.0, "1234567"),
        (Decimal("1234567"), "1234567"),
        (12.345678, "12.345678"),
        (Decimal("12.345678"), "12.345678"),
        (1e-7, "0.0000001"),
        (Decimal("0.0000001"), "0.0000001"),
        (12.5, "12.5"),
        (Decimal("12.50"), "12.5"),
        (0, "0"),
        (-0.0, "0"),
    ],
)
def test_g1_a_balance_and_a_price_print_exactly_never_in_scientific_notation_or_rounded(raw, want):
    assert inventory.credit_cell(raw, "tok", None, NOW) == f"{want} tok"
    conn = FakeConn({"FROM services": SERVICES[:1], "FROM subscriptions": [(1, raw, "usd", None)]})
    (row,), _ = inventory.load(conn)
    assert row["price"] == f"{want} usd"


@pytest.mark.parametrize(
    ("tz", "bad"),
    [
        ("Asia/Tokyo", 253402300799.0),
        ("Pacific/Kiritimati", 253402300799.0),
        ("America/New_York", -62135596800.0),
        ("UTC", float("nan")),
        ("UTC", float("inf")),
        ("UTC", float("-inf")),
        ("UTC", True),
        ("UTC", "x"),
    ],
)
def test_g2_a_time_the_reader_accepts_is_one_every_formatter_can_format(monkeypatch, tz, bad):
    monkeypatch.setenv("TZ", tz)
    time.tzset()
    try:
        for interactive in (True, False):
            markup = str(
                render(
                    [base("c", balance=3.0, unit="usd", credit_at=bad)],
                    synced_at=bad,
                    interactive=interactive,
                )
            )
            assert t("services.inv.attn.registry_never") in markup
    finally:
        monkeypatch.undo()
        time.tzset()


def test_g4_every_row_has_a_visible_name():
    rows = [
        base(None, category="a", status="retiring"),
        base("", category="a", status="active"),
        base("   ", category="?", cost="?", status="?"),
    ]
    fallback = t("services.inv.unnamed")
    for interactive in (True, False):
        root = dom(render(rows, interactive=interactive))
        assert "None" not in root.text()
        heads = [th.text() for th in provider_heads(root)]
        assert len(heads) == 2 and all(h.startswith(fallback) for h in heads)
        assert f"{fallback}: retiring" in attention_card(root).text()
        (queue,) = [d for d in root.find("details") if d.attrs["id"].startswith("queue-")]
        assert fallback in queue.text()
        ids = [el.attrs["id"] for el in root.walk() if "id" in el.attrs]
        assert len(ids) == len(set(ids))


def test_g4_a_name_is_escaped_like_any_other():
    markup = str(render([base("<b>x</b>")]))
    assert "<b>x" not in markup and "&lt;b&gt;x&lt;/b&gt;" in markup


def test_g5_the_static_data_age_lines_sit_with_the_heading_and_the_legend_stays_last():
    markup = str(render(census_rows(), interactive=False, synced_at=NOW - 7 * H))
    synced, written = markup.index("Registry synced"), markup.index("Snapshot written")
    summary = markup.index('data-count="total"')
    first_table = markup.index("<table")
    legend = markup.index(t("services.inv.static.legend", hours=48))
    assert synced < written < summary < first_table < legend
    live = str(render(census_rows(), interactive=True))
    assert "Registry synced" not in live and "Snapshot written" not in live


@pytest.mark.parametrize("n", [0, 1, 2])
def test_g6_counts_read_naturally_for_zero_one_and_two(n):
    rows = [base(f"p{i}", category="a", cost="paid", keys=1) for i in range(n)]
    rows += [base(f"q{i}", category="?", cost="?", status="?", keys=n) for i in range(n)]
    for interactive in (True, False):
        text = dom(render(rows, interactive=interactive)).text()
        assert plural("services.inv.providers", 2 * n) in text
        if n:
            assert plural("services.inv.group.counts", n, paid=n, cred=n) in text
            assert plural("services.inv.untriaged.keys", n) in text
        assert re.search(r"\b1 (providers|keys)\b", text) is None
    assert t("services.inv.providers.other", n=2) == "2 providers"
    assert t("services.inv.providers.other", n=0) == "0 providers"
    assert t("services.inv.providers.one", n=1) == "1 provider"
    assert t("services.inv.untriaged.keys.one", n=1) == "1 key"


@pytest.mark.parametrize("flag", ["no", 1, 0, None, "yes"])
def test_g17_interactive_must_be_a_bool(flag):
    with pytest.raises(ValueError, match="must be True or False"):
        render([], interactive=flag)
    render([], interactive=True)
    render([], interactive=False)


def test_g8_load_carries_a_renewal_date_and_a_priced_row_without_one_stays_blank():
    conn = FakeConn(
        {
            "FROM services": SERVICES[:2],
            "FROM subscriptions": [
                (1, 20, "usd", datetime(2026, 11, 1).date()),
                (2, 5, "usd", None),
            ],
        }
    )
    rows, _ = inventory.load(conn)
    by = {r["provider"]: r for r in rows}
    assert by["apify"]["renews"] == "2026-11-01" and by["mystery"]["renews"] == ""


def test_g9_every_attention_rule_counts_in_the_summary():
    rows = [
        base("stale-only", balance=1.0, unit="usd", credit_at=NOW - 49 * H),
        base("unattr-only", unattributed=2),
        base("healthy"),
    ]
    root = dom(render(rows))
    (li,) = root.find("li", data_count="attention")
    assert li.text() == t("services.inv.sum.attention", n=2)
    text = attention_card(root).text()
    assert "stale-only" in text and "unattr-only" in text and "healthy" not in text


def test_g10_a_credit_dated_in_the_future_is_not_stale_by_any_distance():
    for ahead in (9 * H, 49 * H, 4000 * H):
        assert inventory.credit_cell(3, "usd", NOW + ahead, NOW) == "3 usd"
        rows = [base("f", balance=3.0, unit="usd", credit_at=NOW + ahead)]
        assert "f:" not in attention_card(dom(render(rows))).text()


def test_g11_the_more_counts_read_their_real_inputs():
    rows = [
        base("stale", balance=1.0, unit="usd", credit_at=NOW - 49 * H),
        base("fresh", balance=2.0, unit="usd", credit_at=NOW - H),
        base("renew", renews="2026-11-01", category="b", projects=["p1", "p2"]),
        base("cred", keys=2, unattributed=3, category="c", projects=["p2", "p3"]),
        base("unattr", unattributed=1, category="c"),
    ]
    root = dom(render(rows))
    got = {
        tr.attrs["data-count"]: tr.find("td")[-1].text() for tr in root.find("tr", data_count=True)
    }
    assert got == {
        "categories": "3", "projects": "3", "credit_tracked": "1", "credit_stale": "1",
        "renewals": "1", "credentials": "1", "unattributed": "4",
    }  # fmt: skip


def test_g12_load_and_render_normalise_multi_valued_input():
    conn = FakeConn(
        {
            "FROM services": [
                (2, "b", "x", "free", "", "active"),
                (1, "a", "x", "free", "", "active"),
            ],
            "FROM api_keys": [
                (1, ["z", "k", "x", "c", "t", "a", "p"], "first@x.io", "credential"),
                (1, ["m", "w", "b"], "second@x.io", "credential"),
            ],
        }
    )
    rows, _ = inventory.load(conn)
    assert [r["provider"] for r in rows] == ["a", "b"]
    assert rows[0]["account"] == "first@x.io" and rows[0]["projects"] == sorted("zkxctapmwb")
    ordered = [base("alpha", account="1"), base("Zed"), base("Beta"), base("alpha", account="4")]
    root = dom(render(ordered))
    details = [d.text() for d in root.find("details") if d.attrs["id"].startswith("row-")]
    assert [d.split("Account: ")[1][:1] if "Account: " in d else "" for d in details][:2] == [
        "1",
        "4",
    ]
    heads = [th.text().split(t("services.inv.detail"))[0] for th in provider_heads(root)]
    assert heads == ["alpha", "alpha", "Beta", "Zed"]


def test_g13_the_static_stamp_is_now_and_the_note_is_interactive_only(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Istanbul")
    time.tzset()
    try:
        now = datetime(2026, 10, 18, 3, 0, tzinfo=UTC).timestamp()
        static = str(render([], now=now, synced_at=now - 7 * H, interactive=False))
        assert "Snapshot written 2026-10-18 06:00 +03:00" in static
        assert "Registry synced 2026-10-17 23:00 +03:00" in static
        assert t("services.inv.attn.note") not in static
        assert t("services.inv.attn.note") in str(render([], now=now, interactive=True))
    finally:
        monkeypatch.undo()
        time.tzset()


def test_g15_load_selects_no_secret_bearing_column():
    conn = FakeConn()
    inventory.load(conn)
    for _kind, sql in conn.events:
        assert not re.search(r"\b(value\w*|secret\w*|token\w*|password\w*|aliases)\b", sql, re.I), (
            sql
        )


def test_g16_fixture_overrides_are_copied_per_row():
    rows = census_rows(projects=[])
    rows[0]["projects"].append("x")
    assert rows[1]["projects"] == [] and rows[0]["projects"] is not rows[1]["projects"]


# ---------------------------------------------------------------- pass-2 review fixes (H1-H5)
@pytest.mark.parametrize(
    "url",
    [
        "https://u@", "http://user@", "http://u@/x", "https://user@/path", "https://u:p@",
        "https://[", "https://ok.example:", "https://", "http://", "https:///path", "HTTPS://UP.example",
        "/admin", "#x", "http://a b", "javascript:alert(1)", "ftp://ok.example",
    ],
)  # fmt: skip
def test_h1_a_url_with_no_host_or_a_broken_authority_is_text(url):
    for interactive in (True, False):
        root = dom(render([base("p", url=url)], interactive=interactive))
        assert root.find("a") == [], url


@pytest.mark.parametrize(
    "url",
    [
        "https://ok.example", "http://ok.example", "http://localhost", "https://[::1]/",
        "https://h:8080/x", "https://bücher.example/path?q=1#f",
    ],
)  # fmt: skip
def test_h1_a_parsed_http_url_with_a_host_is_the_link(url):
    for interactive in (True, False):
        root = dom(render([base("p", url=url)], interactive=interactive))
        assert [a.attrs["href"] for a in root.find("a")] == [url]


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        ("https://u:pw@h.example/", "https://h.example/"),
        ("https://u@h.example/", "https://h.example/"),
        ("https://@h.example/", "https://h.example/"),
        ("http://u:pw@h.example:8080/x", "http://h.example:8080/x"),
    ],
)
def test_h2_a_url_carrying_credentials_is_never_a_link_and_never_printed_with_them(url, shown):
    for interactive in (True, False):
        markup = str(render([base("p", url=url)], interactive=interactive))
        root = dom(markup)
        assert root.find("a") == []
        assert "pw" not in markup.replace("pw@", "") or "u:pw" not in markup
        assert "u:pw" not in markup and "u@" not in markup and "@h.example" not in markup
        assert shown in root.text()


def test_h3_one_stale_rule_the_cell_the_attention_list_and_the_count_agree_at_48_hours():
    for ahead, stale in ((0, False), (1, True)):
        row = base("edge", balance=4.0, unit="usd", credit_at=NOW - 48 * H - ahead)
        root = dom(render([row]))
        cell = inventory.credit_cell(4.0, "usd", NOW - 48 * H - ahead, NOW)
        assert cell.startswith("⚠") is stale
        assert ("edge:" in attention_card(root).text()) is stale
        got = {
            tr.attrs["data-count"]: tr.find("td")[-1].text()
            for tr in root.find("tr", data_count=True)
        }
        assert (got["credit_stale"], got["credit_tracked"]) == (("1", "0") if stale else ("0", "1"))


def test_h4_the_queue_shows_an_unattributed_badge_only_when_there_is_one():
    rows = [
        base("zero", category="?", cost="?", status="?", unattributed=0),
        base("two", category="?", cost="?", status="?", unattributed=2),
    ]
    root = dom(render(rows))
    (queue,) = [d for d in root.find("details") if d.attrs["id"].startswith("queue-")]
    entries = {
        li.text().split(" · ")[0]: li.text() for li in queue.find("li", data_filter_item=True)
    }
    assert t("services.inv.unattributed", n=2) in entries["two"]
    assert (
        t("services.inv.unattributed", n=0) not in entries["zero"]
        and "unattributed" not in entries["zero"]
    )


def test_h5_the_singular_heading_is_rendered():
    for interactive in (True, False):
        text = dom(render([base("only")], interactive=interactive)).text()
        assert t("services.inv.providers.one", n=1) in text
        assert re.search(r"(?<!of )(?<!\d)1 providers", text) is None


# ---------------------------------------------------------------- pass-3 fixes (J1-J3)
_J1_NAME_ALONE = [
    "https://./", "https://../", "https://.../", "https://evil.com\\@ok.example/", "https://u:pw@h.exa\tmple/",
    "https://ok.example/a b", "https://ok.example/\nx", "https://ok.example/\x00", "https://ok.example/\x7f",
    "https://", "http://", "https:///path", "https://u@", "https://[", "https://ok.example:",
    "https://h:abc/", "https://h:99999/", "HTTPS://UP.example", "/admin", "#x", "http://a b",
    "javascript:alert(1)", "ftp://ok.example", "ftp://u:pw@h.example/", "https://u:pw@h.example/\x01", "https://u:pw@h.example/\x7f", "HTTPS://u:pw@h.example/", "",
]  # fmt: skip
_J1_STRIPPED = [
    ("https://u:pw@h.example:8443/p?q=1#f", "https://h.example:8443/p?q=1#f"),
    ("https://a@b@h/x", "https://h/x"),
    ("https://u@h.example/", "https://h.example/"),
    ("https://@h.example/", "https://h.example/"),
    ("http://u:pw@h.example/", "http://h.example/"),
]
_J1_LINKS = [
    "https://ok.example", "http://ok.example", "http://localhost", "https://[::1]/",
    "https://h:8080/x", "https://bücher.example/path?q=1#f",
]  # fmt: skip


def _name_cell(url: str, interactive: bool) -> tuple[El, str]:
    root = dom(render([base("p", url=url)], interactive=interactive))
    (head,) = provider_heads(root)
    return root, head.text().split(t("services.inv.detail"))[0]


@pytest.mark.parametrize("url", _J1_NAME_ALONE)
def test_j1_a_url_the_rule_refuses_shows_the_provider_name_alone(url):
    for interactive in (True, False):
        root, shown = _name_cell(url, interactive)
        assert root.find("a") == [] and shown == "p", (url, shown)


@pytest.mark.parametrize(("url", "bare"), _J1_STRIPPED)
def test_j1_userinfo_is_cut_from_the_raw_url_and_the_rest_shown_byte_for_byte(url, bare):
    for interactive in (True, False):
        root, shown = _name_cell(url, interactive)
        assert root.find("a") == [] and shown == f"p {bare}", (url, shown)
        assert "pw" not in root.text() and "u@" not in root.text()


@pytest.mark.parametrize("url", _J1_LINKS)
def test_j1_a_parsed_http_url_with_a_real_host_that_link_accepts_is_the_link(url):
    for interactive in (True, False):
        root, shown = _name_cell(url, interactive)
        (a,) = root.find("a")
        assert (
            a.attrs["href"] == url
            and a.text().strip().endswith("p")
            and shown.strip().endswith("p")
        )
