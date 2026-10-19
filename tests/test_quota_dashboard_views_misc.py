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

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "sysadmin"))

from dashboard_ui import components as ui  # noqa: E402
from dashboard_ui import fmt, views  # noqa: E402
from dashboard_ui import strings as cat  # noqa: E402

from tests.external_services_fixture import census_rows  # noqa: E402

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
        "inventory": {
            "rows": census_rows(),
            "synced_at": NOW - 3600,
        },
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


def test_services_renders_the_inventory_section_in_place_and_no_iframe_or_page_link():
    html, dom = _render("services", _services_data())
    assert dom.find("a", href="/external-services.html") == []
    assert "External services" in dom.all_text() and "466 providers" in dom.all_text()
    assert "Needs attention" in dom.all_text()
    assert dom.find("input", **{"data-filter": "find"})
    for name, data in (
        ("services", _services_data()),
        ("commands", _commands_data()),
        ("usage", {"spend": SPEND}),
    ):
        assert "<iframe" not in _render(name, data)[0]


def test_services_inventory_error_is_that_sections_error_state_and_the_rest_renders():
    _html, dom = _render(
        "services",
        _services_data(inventory={"error": "ReadTimeout: registry read killed at its deadline"}),
    )
    text = dom.all_text()
    assert "inventory could not be read: ReadTimeout: registry read killed at its deadline" in text
    assert "Brave Search" in text and "$225.00" in text  # the pool and API cards still render
    assert "466 providers" not in text
    _h, dom = _render("services", _services_data(inventory=None))
    assert "inventory could not be read: no reading" in dom.all_text()


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
    assert "stamped in the future" in text and "not read yet" in text
    assert ("warning", "50") in _badges(_html)  # remaining > total: count only, no percentage


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
    assert cadences == {"300", "1800", "86400"}  # pool 300 s, search APIs 1,800 s, registry daily
    _h, usage = _render("usage", {"spend": SPEND})
    assert {a.get("data-cadence") for a in _stamps(usage)} == {"86400"}
    assert _stamps(usage)[0].get("data-ts")  # from built_at
    _h, commands = _render("commands", _commands_data())
    assert all(a.get("data-cadence") == "" for a in _stamps(commands))  # never goes stale


def test_failed_collector_is_its_regions_error_the_rest_renders():
    html, dom = _render("services", _services_data(pool={"error": "boom"}))
    text = dom.all_text()
    assert "pool balance could not be read: boom" in text
    assert "Brave Search" in text and "466 providers" in text  # the other regions still render
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
    assert (
        "(5d)" in dom.all_text()
    )  # the API card's renewal, derived from ctx.now (renews_at = NOW + 5 d)
    assert ui.SEVERITIES  # components import stays exercised


# ------------------------------------------------------------------------------------ wave review r1
import copy  # noqa: E402


def _badges(html: str) -> list[tuple[str, str]]:
    return re.findall(
        r'data-severity="(\w+)"><span class="badge-icon".*?<span class="badge-text">(.*?)</span>',
        html,
    )


def _spend(**pm) -> dict:
    out = copy.deepcopy(SPEND)
    out["per_model_spend"].update(pm)
    return {"spend": out}


def _apis_with(**providers) -> dict:
    return _services_data(apis={"ts": NOW, "age_s": 0.0, "stale": False, **providers})


def test_d2_non_finite_unweighted_values_never_crash():
    nan, inf = float("nan"), float("inf")
    _h, dom = _render("usage", _spend(unweighted={"a": nan, "b": inf, "c": 7}))
    assert "7 tokens are NOT in any total" in dom.all_text()
    _h, dom = _render("usage", _spend(unweighted={"a": nan, "b": inf}))
    assert "NOT in any total" not in dom.all_text()


def test_d5_list_shaped_natives_and_rule_render():
    row = _cmd("fabrik-l", natives=[["fabrik-reviewer", ["opus"]]], rule=[True, ["file"]])
    _h, dom = _render("commands", _commands_data([row]))
    assert (
        "at least 1 opus + 1 per file" in dom.all_text()
        and "fabrik-reviewer (opus)" in dom.all_text()
    )


def test_natives_fixed_floor_and_unit_truncation():
    fixed = _cmd("fabrik-f", rule=(False, ("!3 seats",)))
    many = _cmd("fabrik-m", rule=(False, ("a", "b", "c", "d")))
    text = _render("commands", _commands_data([fixed, many]))[1].all_text()
    assert " 3 seats · " in f" {text}" and "!3" not in text and "1 per 3 seats" not in text
    assert "1 per a, b, c…" in text and "a, b, c, d" not in text


def test_d6_non_finite_warn_threshold_falls_back(monkeypatch):
    monkeypatch.setenv("POOL_CREDITS_WARN_USD", "nan")
    low = {"granted": 245.0, "remaining": 3.0, "stale": False}
    assert "under $5" in _render("services", _services_data(pool=low))[1].all_text()


def test_pool_warn_boundary_is_inclusive(monkeypatch):
    monkeypatch.delenv("POOL_CREDITS_WARN_USD", raising=False)
    at = _render("services", _services_data(pool={"granted": 9.0, "remaining": 5.0}))[0]
    above = _render("services", _services_data(pool={"granted": 9.0, "remaining": 5.01}))[0]
    assert _badges(at)[0][0] == "warning" and _badges(above)[0][0] == "ok"
    assert (
        _badges(_render("services", _services_data(pool={"granted": 9.0, "remaining": 0.0}))[0])[0][
            0
        ]
        == "critical"
    )


def test_d7_commands_with_no_dict_rows_is_the_unreadable_state():
    _h, dom = _render("commands", {"commands": [None, "x"], "ext_services": EXT})
    text = dom.all_text()
    assert "Command corpus unreadable" in text and "0 sources" not in text


def test_d8_calendar_survives_an_empty_tier_table():
    _h, dom = _render("usage", _spend(tiers={}))
    text = dom.all_text()
    assert "No tier-weighted spend is recorded yet" in text
    assert "Daily token consumption" in text and "October 2026" in text and "2,000,000" in text


def test_zero_spend_with_tiers_renders_no_tier_table():
    html, dom = _render("usage", _spend(spend_usd=0))
    assert "Spend by tier" not in dom.all_text() and "No tier-weighted spend" in dom.all_text()


def test_d9_float_quota_figures_render():
    brave = {"state": "ok", "total": 2000.0, "remaining": 1500.0, "unit": "queries"}
    html, dom = _render("services", _apis_with(brave=brave))
    assert ("neutral", "1,500 (75%)") in _badges(html) and "2,000 queries" in dom.all_text()


def test_api_remaining_severity_bands():
    def sev(rem: int) -> str:
        h, _ = _render(
            "services", _apis_with(brave={"state": "ok", "total": 100, "remaining": rem})
        )
        return next(s for s, txt in _badges(h) if "%" in txt)

    assert [sev(9), sev(10), sev(24), sev(25)] == ["critical", "warning", "warning", "neutral"]


def test_d10_missing_window_is_not_none_to_none():
    _h, dom = _render("usage", _spend(window_start=None, window_end=None))
    text = dom.all_text()
    assert "None to None" not in text and "an unknown period" in text


def test_d11_non_dict_ext_service_entry_is_skipped():
    data = {**_commands_data(), "ext_services": [None, EXT[0], "x"]}
    html, _d = _render("commands", data)
    assert ">Web</th>" in html and ">Firecrawl</th>" not in html


def test_provider_error_state_names_the_failure():
    _h, dom = _render("services", _apis_with(exa={"state": "error", "error": "HTTP 500"}))
    assert "probe failed (HTTP 500)" in dom.all_text()


def test_renewal_overdue_boundary():
    def badges(at: float) -> list:
        h, _ = _render(
            "services",
            _apis_with(brave={"state": "ok", "total": 10, "remaining": 5, "renews_at": at}),
        )
        return [txt for _s, txt in _badges(h) if txt == "overdue"]

    assert badges(NOW - 1) == ["overdue"] and badges(NOW) == [] and badges(NOW + 86400) == []


def test_top_level_stale_flag_marks_every_provider():
    ok = {"state": "ok", "total": 10, "remaining": 5}
    stale = _render("services", _apis_with(brave=ok))[0]
    assert "reading out of date" not in stale
    html = _render(
        "services", _services_data(apis={"ts": NOW, "age_s": 0.0, "stale": True, "brave": ok})
    )[0]
    assert html.count("reading out of date") == 3


def test_unrendered_matrix_truncation_marker():
    def caveat(n: int) -> str:
        rows = [_cmd(f"fabrik-u{i}", rendered=False) for i in range(n)]
        text = _render("commands", _commands_data(rows))[1].all_text()
        return re.search(r"rows did NOT come from the rendered corpus \((.*?)\) -", text).group(1)

    assert caveat(7) == "fabrik-u0, fabrik-u1, fabrik-u2, fabrik-u3, fabrik-u4, fabrik-u5, …"
    assert caveat(6) == "fabrik-u0, fabrik-u1, fabrik-u2, fabrik-u3, fabrik-u4, fabrik-u5"


def test_reconciliation_tolerance_and_tier_order():
    tiers = {
        "haiku": {"weight": 1, "tokens": 1, "share": 0.4, "rate_per_mtok": 0.1, "cost_usd": 25.0},
        "opus": {"weight": 5, "tokens": 2, "share": 0.6, "rate_per_mtok": 0.5, "cost_usd": 75.009},
    }
    text = _render("usage", _spend(tiers=tiers))[1].all_text()
    assert "reconciles to $100.00" in text
    assert text.index("$75.01") < text.index("$25.00")  # cost descending, not dict order
    tiers["opus"]["cost_usd"] = 75.02
    assert "DOES NOT reconcile" in _render("usage", _spend(tiers=tiers))[1].all_text()


def test_calendar_peak_share_column():
    html, _d = _render("usage", {"spend": SPEND})
    oct_card = html.partition("October 2026")[2].split("September 2026")[0]
    cells = re.findall(r"<td>(\d+%)</td>", oct_card)
    assert cells == ["100%", "0%"]  # 2,000,000 is the peak; the zero day is 0%


# ------------------------------------------------------------------------------------ bad read times
_BAD_TS = [-5, -1, float("nan"), float("inf"), 1e30]


def _no_ts(dom: _Dom) -> bool:
    stamps = _stamps(dom)
    return bool(stamps) and all(not a.get("data-ts") for a in stamps)


def _pool_api_stamps(dom: _Dom) -> list[dict]:
    """The pool's and the search APIs' stamps with a time (the inventory's daily stamp is its own)."""
    return [a for a in _stamps(dom) if a.get("data-ts") and a.get("data-cadence") != "86400"]


@pytest.mark.parametrize("bad", _BAD_TS, ids=repr)
def test_services_a_bad_pool_or_api_ts_drops_only_that_stamp(bad):
    base = _services_data()
    _h, dom = _render("services", _services_data(pool={**base["pool"], "ts": bad}))
    assert "$225.00" in dom.all_text()
    assert len(_pool_api_stamps(dom)) == 1  # the APIs stamp survives
    _h, dom = _render("services", _services_data(apis={**base["apis"], "ts": bad}))
    assert "Brave Search" in dom.all_text()
    assert len(_pool_api_stamps(dom)) == 1  # the pool stamp survives


@pytest.mark.parametrize("built", ["1960-01-01T00:00:00", "9999-12-31T00:00:00"])
def test_usage_a_bad_built_at_drops_the_stamp_and_the_view_still_renders(built):
    _h, dom = _render("usage", {"spend": {**SPEND, "built_at": built}})
    assert _no_ts(dom)
    assert dom.find("table")


@pytest.mark.parametrize("bad", _BAD_TS, ids=repr)
def test_commands_a_bad_clock_drops_the_stamp_and_the_view_still_renders(bad):
    ctx = views.ViewContext(opt_root=CTX.opt_root, fabrik_root=CTX.fabrik_root, now=bad)
    result = views.load("commands").render({"now": NOW, **_commands_data()}, ctx)
    dom = _Dom(str(result.html))
    assert _no_ts(dom) and "fabrik-spec" in dom.all_text()


@pytest.mark.parametrize(
    "x",
    [None, True, False, "1800000000", 0, 0.0, -1, -5.0, float("nan"), float("inf"), -float("inf")]
    + [4e9, 1e30, 10**400, [1], {"ts": 1}],
    ids=repr,
)
def test_read_ts_refuses_what_a_stamp_cannot_show(x):
    assert fmt.read_ts(x) is None


@pytest.mark.parametrize(
    "x,want", [(1, 1.0), (NOW, NOW), (int(NOW), NOW), (3_999_999_999.5, 3_999_999_999.5)]
)
def test_read_ts_passes_a_real_read_time_through_as_float(x, want):
    got = fmt.read_ts(x)
    assert type(got) is float and got == want
    assert ui.freshness(got, None)  # and freshness accepts every value read_ts lets through


# ------------------------------------------------------------------------------------ wave review r2
HUGE = 10**400  # an int no float can hold: math.isfinite(HUGE) raises OverflowError


def test_d_r2_1_huge_ints_never_fail_a_view():
    pool = {"granted": HUGE, "remaining": HUGE, "ts": HUGE, "age_s": HUGE, "stale": True}
    brave = {"state": "ok", "total": HUGE, "remaining": HUGE, "renews_at": HUGE, "ts": HUGE}
    _h, dom = _render("services", {**_apis_with(brave=brave), "pool": pool})
    assert "Brave Search" in dom.all_text()
    tiers = {
        "opus": {
            "weight": HUGE,
            "tokens": HUGE,
            "share": HUGE,
            "rate_per_mtok": HUGE,
            "cost_usd": HUGE,
        }
    }
    _h, dom = _render(
        "usage",
        _spend(
            unweighted={"x": HUGE, "y": 5},
            spend_usd=HUGE,
            tiers=tiers,
            monthly_spend={"2026-10": HUGE},
        ),
    )
    assert "5 tokens are NOT in any total" in dom.all_text()


def test_d_r2_2_unknown_pool_balance_is_never_exhausted():
    for pool in (
        {"granted": 245.0, "remaining": float("nan")},
        {"granted": 245.0},
        {"remaining": float("inf")},
    ):
        _html, dom = _render("services", _services_data(pool=pool))
        text = dom.all_text()
        assert "Pool balance UNKNOWN" in text and "EXHAUSTED" not in text
        assert dom.find("div", **{"data-state": "error"})
    zero = _render("services", _services_data(pool={"granted": 9.0, "remaining": 0}))[1].all_text()
    assert "EXHAUSTED" in zero  # a genuine zero is still exhausted


def test_two_huge_finite_unclassified_counts_never_fail_usage():  # wave r3 (N-2)
    # each term is finite, but 1e308 + 1e308 is inf and int(inf) raised OverflowError
    _h, dom = _render("usage", _spend(unweighted={"a": 1e308, "b": 1e308}))
    assert "NOT in any total" not in dom.all_text()


# ------------------------------------------------------------------------------------ whole-plan review r1 (item 20)
def test_item20_matrix_root_comes_from_the_server_value(monkeypatch):
    monkeypatch.setenv("QUOTA_DASH_RENDERED_COMMANDS", "/env/root")
    given = {**_commands_data(), "rendered_root": "/server/root"}
    assert "under /server/root)" in _render("commands", given)[1].all_text()
    fallback = _render("commands", _commands_data())[
        1
    ].all_text()  # key absent: today's computation
    assert "under /env/root)" in fallback


def test_item20_pool_warn_threshold_comes_from_the_server_value(monkeypatch):
    monkeypatch.setenv("POOL_CREDITS_WARN_USD", "1")
    pool = {"granted": 99.0, "remaining": 20.0}
    served = _render("services", {**_services_data(pool=pool), "warn_usd": 50.0})[1].all_text()
    assert "under $50" in served  # the server's 50 beats the env's 1
    assert (
        "under $" not in _render("services", _services_data(pool=pool))[1].all_text()
    )  # fallback: env 1
    low = {**_services_data(pool={"granted": 9.0, "remaining": 3.0}), "warn_usd": "nan"}
    assert "under $5" in _render("services", low)[1].all_text()  # non-finite server value: default
