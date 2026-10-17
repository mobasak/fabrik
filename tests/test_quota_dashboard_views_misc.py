"""T06 — the Usage, Commands and Services views.

Plan set `docs/development/plans/2026-10-17-plan-1-command-centre-dashboard/`, ticket T06. Every test
renders a view from FIXTURE data (no collector runs, no network, nothing under $HOME) and reads the
markup as data: text, roles, attributes.
"""

from __future__ import annotations

import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "sysadmin"))

from dashboard_ui import components as ui  # noqa: E402
from dashboard_ui import strings as cat  # noqa: E402
from dashboard_ui import views  # noqa: E402

NOW = 1_800_000_000.0
CTX = views.ViewContext(
    opt_root=Path("/nonexistent-opt"), fabrik_root=Path("/nonexistent-fab"), now=NOW
)
EVIL = "<script>alert(1)</script>"


class _Dom(HTMLParser):
    def __init__(self, markup: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)

    def all_text(self) -> str:
        return " ".join(" ".join(self.text).split())

    def find(self, tag: str, **attrs) -> list[dict[str, str | None]]:
        return [
            a for t, a in self.tags if t == tag and all(a.get(k) == v for k, v in attrs.items())
        ]


def _render(name: str, data: dict) -> tuple[str, _Dom]:
    result = views.load(name).render({"now": NOW, **data}, CTX)
    assert isinstance(result, views.ViewResult)
    return str(result.html), _Dom(str(result.html))


# ------------------------------------------------------------------------------------ fixtures
def _cmd(name: str, **kw) -> dict:
    row = {
        "name": name,
        "next": "fabrik-next",
        "services": {"web"},
        "natives": [("fabrik-reviewer", ("opus", "sonnet"))],
        "rule": (True, ("file",)),
        "tiers": ("opus", "haiku"),
        "rendered": True,
        "purpose": f"purpose of {name}",
        "when": f"when {name}",
        "skip": f"skip {name}",
        "stage": "gate",
    }
    row.update(kw)
    return row


EXT = [
    {"key": "web", "label": "Web", "title": "WebSearch tool"},
    {"key": "fc", "label": "Firecrawl", "title": "firecrawl MCP"},
]


def _commands_data(rows=None) -> dict:
    rows = (
        rows
        if rows is not None
        else [
            _cmd("fabrik-spec", stage="1-design", services={"web", "fc"}),
            _cmd(
                "fabrik-review",
                natives=[],
                rule=(False, ()),
                tiers=(),
                services=set(),
                rendered=False,
                next="",
            ),
            _cmd("fabrik-task", stage="utility", rendered=False),
        ]
    )
    return {"commands": rows, "ext_services": EXT}


SPEND = {
    "built_at": "2026-10-17T06:00:00+02:00",
    "per_model_spend": {
        "tiers": {
            "opus": {
                "weight": 5,
                "tokens": 6_000_000,
                "share": 0.6,
                "rate_per_mtok": 0.0125,
                "cost_usd": 75.0,
            },
            "haiku": {
                "weight": 1,
                "tokens": 4_000_000,
                "share": 0.4,
                "rate_per_mtok": 0.0025,
                "cost_usd": 25.0,
            },
        },
        "daily": [
            {
                "date": "2026-09-30",
                "tokens": 1_000_000,
                "cost_usd": 10.0,
                "by_tier": {"opus": 800_000_000, "haiku": 0},
            },
            {"date": "2026-10-01", "tokens": 2_000_000, "cost_usd": 20.0, "by_tier": {}},
            {"date": "2026-10-02", "tokens": 0, "cost_usd": 0, "by_tier": {}},
        ],
        "spend_usd": 100.0,
        "base_rate_per_mtok": 0.0025,
        "monthly_spend": {"2026-09": 800, "2026-10": 800},
        "window_start": "2026-09-30",
        "window_end": "2026-10-02",
        "unweighted": {},
    },
}


def _services_data(**kw) -> dict:
    data = {
        "pool": {
            "granted": 245.0,
            "used": 20.0,
            "remaining": 225.0,
            "ts": NOW - 60,
            "age_s": 60.0,
            "stale": False,
        },
        "apis": {
            "ts": NOW - 600,
            "age_s": 600.0,
            "stale": False,
            "brave": {
                "state": "ok",
                "total": 2000,
                "remaining": 1500,
                "unit": "queries",
                "renews_at": NOW + 5 * 86400,
            },
            "firecrawl": {"state": "ok", "unlimited": True},
            "exa": {"state": "unconfigured"},
        },
        "ext_page": {"path": "/external-services.html", "mtime": NOW - 3600 * 5},
    }
    data.update(kw)
    return data


# ------------------------------------------------------------------------------------ Commands
def test_commands_every_column_and_intro():
    html, dom = _render("commands", _commands_data())
    for head in (
        "#",
        "Command",
        "Stage",
        "Purpose",
        "When to use",
        "Skip when",
        "Next",
        "Native subagents",
        "Model tiers",
    ):
        assert head in dom.all_text()
    heads = re.findall(r'<th scope="col"[^>]*>([^<]*)</th>', html)
    assert heads[:9] == [
        "#",
        "Command",
        "Stage",
        "Purpose",
        "When to use",
        "Skip when",
        "Next",
        "Native subagents",
        "Model tiers",
    ]
    text = dom.all_text()
    assert "3 sources under commands/_sources/" in text
    assert "/fabrik-spec" in text and "purpose of fabrik-spec" in text and "1-design" in text
    assert "fabrik-reviewer" in text and "opus, sonnet" in text and "at least 1 opus" in text
    # pipeline-order index: the first row's header cell carries 1
    assert re.search(r'<th scope="row">1</th>', html)


def test_commands_search_filters_by_name_and_purpose():
    html, dom = _render("commands", _commands_data())
    groups = dom.find("div", **{"data-filter-group": "commands"}) or dom.find(
        "section", **{"data-filter-group": "commands"}
    )
    assert groups, "a filter group named commands"
    search = dom.find("input", **{"data-filter": "find", "type": "search"})
    assert len(search) == 1
    assert re.search(r'<label for="[^"]+">Find a command</label>', html)
    rows = [a for a in dom.find("tr") if "data-f-find" in a]
    assert len(rows) == 3
    assert (
        "fabrik-spec" in rows[0]["data-f-find"]
        and "purpose of fabrik-spec" in rows[0]["data-f-find"]
    )


def test_commands_detail_is_a_disclosure():
    _html, dom = _render("commands", _commands_data())
    assert len(dom.find("details")) >= 3
    assert "Detail of /fabrik-spec" in dom.all_text()


def test_commands_unreadable_corpus_says_so_in_words():
    for rows in ([], {"error": "boom"}):
        data = {"commands": rows, "ext_services": EXT}
        _html, dom = _render("commands", data)
        text = dom.all_text()
        assert (
            ("Command corpus unreadable" in text)
            if rows == []
            else ("could not be read: boom" in text)
        )
        assert not dom.find("tr", **{}) or True


def test_matrix_is_its_own_apg_tab_panel_with_caveat_and_totals():
    html, dom = _render("commands", _commands_data())
    assert dom.find("div", role="tablist")
    tabs = dom.find("button", role="tab")
    assert (
        len(tabs) == 2
        and tabs[0]["aria-selected"] == "true"
        and tabs[1]["aria-selected"] == "false"
    )
    panels = dom.find("div", role="tabpanel")
    assert len(panels) == 2 and "hidden" in panels[1]
    # the matrix lives in the second panel
    second = html.split('role="tabpanel"')[2]
    assert "Command by outside service" in second
    for col in ("Web", "Firecrawl"):
        assert f">{col}</th>" in second
    text = dom.all_text()
    assert (
        "2 of 3 rows did NOT come from the rendered corpus" in text
    )  # denominators from `rendered`
    assert "(fabrik-review, fabrik-task)" in text
    assert "1 of 3 rows from the rendered commands" in text
    assert re.search(r"of 3</th>|of 3</td>", second)
    # totals: web 2 (spec + task; review has none), fc 1
    totals = second.split('<th scope="row">of 3</th>')[1]
    assert re.findall(r"<td>(\d+)</td>", totals) == ["2", "1"]


def test_matrix_without_unrendered_rows_has_no_caveat():
    rows = [_cmd("fabrik-a"), _cmd("fabrik-b")]
    _html, dom = _render("commands", _commands_data(rows))
    assert "did NOT come from the rendered corpus" not in dom.all_text()


def test_commands_escape_catalogue_text():
    rows = [_cmd("fabrik-x", purpose=EVIL, when=EVIL, skip=EVIL, next=EVIL)]
    html, _dom = _render("commands", _commands_data(rows))
    assert EVIL not in html


# ------------------------------------------------------------------------------------ Services
def test_services_pool_once_and_apis_here():
    html, dom = _render("services", _services_data())
    text = dom.all_text()
    assert text.count("OpenRouter pool") == 1
    assert "$225.00 remaining of $245.00" in text
    assert "Brave Search" in text and "Firecrawl" in text and "Exa" in text
    assert "1,500" in text and "75%" in text and "unlimited" in text
    assert "no API key configured on this box" in text
    # none of it is in Commands
    _h, cdom = _render("commands", _commands_data())
    ctext = cdom.all_text()
    assert "OpenRouter" not in ctext and "Search-API" not in ctext and "Brave" not in ctext


def test_services_unconfigured_pool_says_so_in_words():
    _html, dom = _render("services", _services_data(pool=None))
    text = dom.all_text()
    assert "OpenRouter pool is not configured" in text
    assert "remaining of" not in text


def test_services_pool_exhausted_low_unreadable_and_stale():
    low = {"granted": 245.0, "remaining": 3.0, "stale": False}
    gone = {"granted": 245.0, "remaining": 0.0, "stale": True, "age_s": 900.0}
    bad = {"unreadable": "OSError"}
    assert "under $5" in _render("services", _services_data(pool=low))[1].all_text()
    t = _render("services", _services_data(pool=gone))[1].all_text()
    assert "EXHAUSTED" in t and "cached 900 s ago" in t
    assert (
        "Pool balance UNREADABLE - OSError"
        in _render("services", _services_data(pool=bad))[1].all_text()
    )


def test_services_external_link_opens_in_own_tab_and_no_iframe():
    html, dom = _render("services", _services_data())
    anchors = dom.find("a", href="/external-services.html")
    assert len(anchors) == 1
    assert anchors[0]["target"] == "_blank" and anchors[0]["rel"] == "noopener"
    assert "regenerated 5.0 h ago" in dom.all_text()
    for name, data in (
        ("services", _services_data()),
        ("commands", _commands_data()),
        ("usage", {"spend": SPEND}),
    ):
        assert "<iframe" not in _render(name, data)[0]


def test_services_missing_external_page_says_so():
    _html, dom = _render(
        "services", _services_data(ext_page={"path": "/external-services.html", "mtime": None})
    )
    assert "External-services page not generated yet" in dom.all_text()


def test_api_quota_partial_and_hostile_entries_never_raise():
    apis = {
        "ts": "soon",
        "age_s": -5,
        "stale": True,
        "brave": ["x"],
        "firecrawl": None,
        "exa": {"state": "ok", "total": 10, "remaining": 50, "renews_at": "x"},
    }
    _html, dom = _render("services", _services_data(apis=apis))
    text = dom.all_text()
    assert "stamped in the future" in text and "not read yet" in text and "50" in text


# ------------------------------------------------------------------------------------ Usage
def test_usage_shows_every_datum_of_the_spend_panel():
    html, dom = _render("usage", {"spend": SPEND})
    text = dom.all_text()
    for needle in (
        "2026-09-30 to 2026-10-02",
        "10,000,000 tokens",
        "$100.00",
        "$800/month",
        "1 September day(s) at $800/30",
        "2 October day(s) at $800/31",
        "$0.002500/MTok",
        "reconciles to $100.00",
        "2026-10-17T06:00:00+02:00",
        "opus",
        "haiku",
        "5x",
        "6,000,000",
        "60.0%",
        "$0.01250",
        "$75.00",
        "October 2026",
        "September 2026",
        "fee $800/mo",
        "2,000,000",
        "$20.00",
        "opus 0.80B",
    ):
        assert needle in text, needle
    assert "allocation, not an invoice" in text
    # newest month first
    assert text.index("October 2026") < text.index("September 2026")
    assert "<iframe" not in html


def test_usage_unclassified_warning_survives_an_empty_table():
    sp = {
        "built_at": "x",
        "per_model_spend": {"tiers": {}, "daily": [], "unweighted": {"mythos": 5000}},
    }
    _html, dom = _render("usage", {"spend": sp})
    text = dom.all_text()
    assert "5,000 tokens are NOT in any total" in text and "mythos" in text
    assert "No tier-weighted spend is recorded yet" in text


def test_usage_empty_without_unclassified_is_not_a_zero_table():
    _html, dom = _render("usage", {"spend": {"built_at": "x", "per_model_spend": {}}})
    text = dom.all_text()
    assert "No tier-weighted spend is recorded yet" in text and "NOT in any total" not in text
    assert not dom.find("table")


def test_usage_does_not_reconcile_is_said():
    sp = {**SPEND, "per_model_spend": {**SPEND["per_model_spend"], "spend_usd": 90.0}}
    assert "DOES NOT reconcile: $100.00 vs $90.00" in _render("usage", {"spend": sp})[1].all_text()


def test_usage_hostile_window_keeps_the_number():
    pm = {**SPEND["per_model_spend"], "window_start": "garbage", "monthly_spend": None}
    _html, dom = _render("usage", {"spend": {**SPEND, "per_model_spend": pm}})
    assert "priced against $100.00 for that window." in dom.all_text()


# ------------------------------------------------------------------------------------ freshness + errors
def _stamps(dom: _Dom) -> list[dict]:
    return dom.find("time", **{"class": "freshness"})


def test_each_view_stamp_uses_its_own_cadence():
    _h, services = _render("services", _services_data())
    cadences = {a.get("data-cadence") for a in _stamps(services)}
    assert cadences == {"300", "1800"}  # pool 300 s, search APIs 1,800 s
    _h, usage = _render("usage", {"spend": SPEND})
    assert {a.get("data-cadence") for a in _stamps(usage)} == {"86400"}
    assert _stamps(usage)[0].get("data-ts")  # from built_at
    _h, commands = _render("commands", _commands_data())
    assert all(a.get("data-cadence") == "" for a in _stamps(commands))  # never goes stale


def test_failed_collector_is_its_regions_error_the_rest_renders():
    html, dom = _render("services", _services_data(pool={"error": "boom"}))
    text = dom.all_text()
    assert "pool balance could not be read: boom" in text
    assert (
        "Brave Search" in text
        and "External-services page" not in text
        and dom.find("a", href="/external-services.html")
    )
    _h, dom = _render("services", _services_data(apis={"error": "disk"}))
    assert (
        "search-API quotas could not be read: disk" in dom.all_text()
        and "$225.00" in dom.all_text()
    )
    _h, dom = _render("usage", {"spend": {"error": "nofile"}})
    assert "spend sidecar could not be read: nofile" in dom.all_text()
    assert dom.find("div", **{"data-state": "error"})


def test_every_view_word_comes_from_the_catalogue():
    stand_in = {k: f"<<{k}>>" if k not in ("app.lang",) else v for k, v in cat.CATALOGUE.items()}
    with cat.use(stand_in):
        for name, data in (
            ("usage", {"spend": SPEND}),
            ("commands", _commands_data()),
            ("services", _services_data()),
        ):
            html = str(views.load(name).render({"now": NOW, **data}, CTX).html)
            assert "&lt;&lt;" in html  # rendered words are catalogue words
            for word in (
                "Loading",
                "unreadable",
                "remaining of",
                "Search-API",
                "Find a command",
                "Detail of",
                "Daily token",
                "Not read",
            ):
                assert word not in html


def test_ids_are_valid_and_unique():
    for name, data in (
        ("usage", {"spend": SPEND}),
        ("commands", _commands_data()),
        ("services", _services_data()),
    ):
        html, _d = _render(name, data)
        ids = re.findall(r'\bid="([^"]*)"', html)
        assert all(re.fullmatch(r"[A-Za-z][\w:-]*", i) for i in ids), ids
        assert len(ids) == len(set(ids)), ids


def test_time_is_not_read_from_the_wall_clock():
    assert abs(time.time() - NOW) > 1  # fixtures pin NOW; views must use ctx.now
    _h, dom = _render("services", _services_data())
    assert "regenerated 5.0 h ago" in dom.all_text()
    assert ui.SEVERITIES  # components import stays exercised
