"""T01 — the dashboard UI kit: escaped components, the string catalogue, the palette and its contrast.

Plan set `docs/development/plans/2026-10-17-plan-1-command-centre-dashboard/`, ticket T01. Every test
reads markup and `app.css` as DATA — landmarks, roles, text, attributes and computed contrast ratios —
never a rendered pixel or a class string as the outcome (`.windsurf/rules/core/45-testing-strategy.md:21`).
"""

from __future__ import annotations

import inspect
import re
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
_PKG = _ROOT / "scripts" / "sysadmin" / "dashboard_ui"
sys.path.insert(0, str(_PKG.parent))

from dashboard_ui import components as ui  # noqa: E402
from dashboard_ui import strings as cat  # noqa: E402

PAYLOAD = "<script>alert(1)</script>\"'&"
ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;&quot;&#x27;&amp;"


# ---------------------------------------------------------------- a tiny DOM, enough for these asserts
class _Node:
    def __init__(self, tag: str, attrs: dict[str, str | None], parent: _Node | None) -> None:
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: list[_Node] = []
        self.text = ""

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def all_text(self) -> str:
        return self.text + "".join(c.all_text() for c in self.children)


_VOID = {"meta", "link", "input", "br", "hr", "img"}


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, dict(attrs), self.cur))

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


def find_all(root: _Node, tag: str | None = None, **attrs: str) -> list[_Node]:
    out = []
    for n in root.walk():
        if tag is not None and n.tag != tag:
            continue
        if all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items()):
            out.append(n)
    return out


# ---------------------------------------------------------------- every component, every argument
def _escapes(x):
    """(component.param, thunk): the payload in ONE argument position at a time, expected ESCAPED."""
    sev = "warning"
    return [
        ("badge.text", lambda: ui.badge(sev, x)),
        ("link.label", lambda: ui.link(x, "/p", new_tab=True)),
        ("link.href", lambda: ui.link("l", "/p?q=" + x)),
        ("card.title", lambda: ui.card(x, "b")),
        ("card.body", lambda: ui.card("t", x)),
        ("card.badge", lambda: ui.card("t", "b", badge=x)),
        ("card.age", lambda: ui.card("t", "b", age=x)),
        ("card.actions", lambda: ui.card("t", "b", actions=x)),
        ("table.label", lambda: ui.table("l", x, ["h"], [["c"]])),
        ("table.headers", lambda: ui.table("l", "L", [x], [["c"]])),
        ("table.rows", lambda: ui.table("l", "L", ["h", "i"], [[x, "c"]])),
        ("table.rows#td", lambda: ui.table("l", "L", ["h", "i"], [["c", x]])),
        ("table.row_data", lambda: ui.table("l", "L", ["h"], [["c"]], row_data=[{"k": x}])),
        ("select.label", lambda: ui.select(x, name="n", id="i", options=[("a", "A")])),
        ("select.name", lambda: ui.select("l", name=x, id="i", options=[("a", "A")])),
        ("select.options", lambda: ui.select("l", name="n", id="i", options=[("a", x)])),
        ("select.options#value", lambda: ui.select("l", name="n", id="i", options=[(x, "A")])),
        ("select.value", lambda: ui.select("l", name="n", id="i", options=[(x, "A")], value=x)),
        (
            "select.data",
            lambda: ui.select("l", name="n", id="i", options=[("", "All")], data={"filter": x}),
        ),
        ("status_text.text", lambda: ui.status_text(x)),
        ("status_text.data", lambda: ui.status_text("t", data={"filter-status": x})),
        ("button.label", lambda: ui.button(x)),
        ("button.data", lambda: ui.button("b", data={"body": x})),
        ("field.label", lambda: ui.field(x, name="n", id="i")),
        ("field.name", lambda: ui.field("l", name=x, id="i")),
        ("field.value", lambda: ui.field("l", name="n", id="i", value=x)),
        ("field.value#textarea", lambda: ui.field("l", name="n", id="i", kind="textarea", value=x)),
        ("field.min", lambda: ui.field("l", name="n", id="i", kind="number", min=x)),
        ("field.max", lambda: ui.field("l", name="n", id="i", kind="number", max=x)),
        ("field.placeholder", lambda: ui.field("l", name="n", id="i", placeholder=x)),
        ("field.data", lambda: ui.field("l", name="n", id="i", data={"filter": x})),
        ("group.body", lambda: ui.group(x)),
        ("group.data", lambda: ui.group("b", data={"pick": x})),
        ("group.label", lambda: ui.group("b", label=x)),
        ("link.label#fragment", lambda: ui.link(x, "#a")),
        ("link.href#fragment", lambda: ui.link("t", "#" + x)),
        ("link.href#url", lambda: ui.link("t", "https://x.example/?q=" + x)),
        ("section.title", lambda: ui.section(x, "b", id="s")),
        ("section.body", lambda: ui.section("t", x, id="s")),
        ("dialog.title", lambda: ui.dialog("d", x, "B", "Go", "Stop")),
        ("dialog.body", lambda: ui.dialog("d", "T", x, "Go", "Stop")),
        ("dialog.confirm_label", lambda: ui.dialog("d", "T", "B", x, "Stop")),
        ("dialog.cancel_label", lambda: ui.dialog("d", "T", "B", "Go", x)),
        ("disclosure.summary", lambda: ui.disclosure(x, "b")),
        ("disclosure.body", lambda: ui.disclosure("s", x)),
        ("disclosure.data", lambda: ui.disclosure("s", "b", data={"k": x})),
        ("tabs.label", lambda: ui.tabs(x, [("a", "A", "a")])),
        ("tabs.items", lambda: ui.tabs("L", [("a", x, "a")])),
        ("tabs.items#body", lambda: ui.tabs("L", [("a", "A", x)])),
        ("clamp.text", lambda: ui.clamp(x)),
        ("region_state.message", lambda: ui.region_state("error", x, retry=True)),
        ("stale_banner.age_text", lambda: ui.stale_banner(x, "c")),
        ("stale_banner.cause", lambda: ui.stale_banner("1 min", x)),
        ("shell.views", lambda: ui.shell([("v", x)], "v")),
        ("shell.body", lambda: ui.shell([("v", "V")], "v", body=x)),
        ("fragment.parts", lambda: ui.fragment(x)),
        ("last_resort.words", lambda: ui.last_resort(x)),
    ]


def _refusals(x):
    """(component.param, thunk): the payload in an id, enum, number or flag position, expected REFUSED."""
    return [
        ("badge.severity", lambda: ui.badge(x, "t")),
        ("link.href#javascript", lambda: ui.link("l", "javascript:" + x)),
        ("link.new_tab", lambda: ui.link("l", "/p", new_tab=x)),
        ("card.id", lambda: ui.card("t", "b", id=x)),
        ("table.label_id", lambda: ui.table(x, "L", ["h"], [["c"]])),
        ("button.kind", lambda: ui.button("b", kind=x)),
        ("table.align", lambda: ui.table("l", "L", ["h"], [["c"]], align=[x])),
        ("select.id", lambda: ui.select("l", name="n", id=x, options=[])),
        ("field.kind", lambda: ui.field("l", name="n", id="i", kind=x)),
        ("field.id", lambda: ui.field("l", name="n", id=x)),
        ("group.tag", lambda: ui.group("b", tag=x)),
        ("group.id", lambda: ui.group("b", id=x)),
        ("value_of.input_id", lambda: ui.value_of(x)),
        ("link.href#bare", lambda: ui.link("t", x)),
        ("section.id", lambda: ui.section("t", "b", id=x)),
        ("dialog.id", lambda: ui.dialog(x, "T", "B", "Go", "Stop")),
        ("dialog.note", lambda: ui.dialog("d", "T", "B", "Go", "Stop", note=x)),
        ("disclosure.open", lambda: ui.disclosure("s", "b", open=x)),
        ("disclosure.id", lambda: ui.disclosure("s", "b", id=x)),
        ("tabs.items#id", lambda: ui.tabs("L", [(x, "A", "a")])),
        ("clamp.lines", lambda: ui.clamp("t", lines=x)),
        ("region_state.kind", lambda: ui.region_state(x, "m")),
        ("region_state.retry", lambda: ui.region_state("error", "m", retry=x)),
        ("freshness.read_ts", lambda: ui.freshness(x, 20)),
        ("freshness.cadence_s", lambda: ui.freshness(1.0, x)),
        ("shell.views#id", lambda: ui.shell([(x, "V")], "v")),
        ("shell.active", lambda: ui.shell([("v", "V")], x)),
        ("slug.prefix", lambda: ui.slug("t", prefix=x)),
    ]


def _id_makers(x):
    """(component.param, thunk): the payload turned into an id, expected VALID (never escaped markup)."""
    return [("slug.text", lambda: ui.slug(x))]


@pytest.mark.parametrize("name,call", _id_makers(PAYLOAD), ids=[n for n, _ in _id_makers(PAYLOAD)])
def test_an_id_maker_turns_any_text_into_a_valid_id(name, call):
    assert re.fullmatch(r"[A-Za-z][\w:-]*", call(), re.ASCII)


@pytest.mark.parametrize("name,call", _escapes(PAYLOAD), ids=[n for n, _ in _escapes(PAYLOAD)])
def test_every_component_escapes_every_text_argument(name, call):
    out = call()
    assert type(out) is ui.Safe, name
    assert PAYLOAD not in out, name
    assert "<script>alert" not in out, name
    assert ESCAPED in out, name


@pytest.mark.parametrize("name,call", _refusals(PAYLOAD), ids=[n for n, _ in _refusals(PAYLOAD)])
def test_every_id_enum_number_and_flag_argument_refuses_anything_else(name, call):
    with pytest.raises((ValueError, TypeError)):
        call()


def test_the_matrix_covers_every_parameter_of_every_component():
    """A component or a parameter added without a matrix row is a hole: read the signatures."""
    covered = {n.split("#")[0] for n, _ in _escapes("x") + _refusals("x") + _id_makers("x")}
    wanted = set()
    for name, fn in inspect.getmembers(ui, inspect.isfunction):
        if fn.__module__ != ui.__name__ or name.startswith("_"):
            continue
        for param in inspect.signature(fn).parameters:
            wanted.add(f"{name}.{param}")
    assert wanted - covered == set()
    assert "live_region" in {n for n, f in inspect.getmembers(ui, inspect.isfunction)}


@pytest.mark.parametrize("bad", ["", "1a", "a b", 'a"b', "a<b", "-a", "a/b"])
def test_an_id_outside_the_html_id_alphabet_is_refused(bad):
    for call in (
        lambda: ui.card("t", "b", id=bad),
        lambda: ui.field("l", name="n", id=bad),
        lambda: ui.dialog(bad, "T", "B", "Go", "Stop"),
        lambda: ui.tabs("L", [(bad, "A", "a")]),
        lambda: ui.value_of(bad),
    ):
        with pytest.raises(ValueError):
            call()
    assert 'id="ok:a_1-b"' in ui.card("t", "b", id="ok:a_1-b")


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html,x",
        "ftp://x.example/",
        "//x.example/",
        "/\\x.example",
        "",
        "# a",
        "/a\nb",
        "/a\x00b",
        "#a\x7fb",
        "x.example",
    ],
)
def test_a_link_leaving_the_origin_or_carrying_a_scheme_is_refused(href):
    with pytest.raises(ValueError):
        ui.link("t", href)


@pytest.mark.parametrize(
    "href",
    ["#work-fabrik", "/#work/fabrik", "/p?q=1", "https://example.com/x", "http://x.example/"],
)
def test_a_fragment_a_same_site_path_and_an_http_url_are_accepted(href):
    (a,) = find_all(parse(ui.link("t", href)), "a")
    assert a.attrs["href"] == href


def test_a_link_and_a_section_are_labelled_markup():
    root = parse(ui.fragment(ui.link("Go", "/#work/my%20repo"), ui.section("Title", "b", id="s1")))
    (a,) = find_all(root, "a")
    assert a.attrs["href"] == "/#work/my%20repo" and a.all_text() == "Go"
    (sec,) = find_all(root, "section")
    assert sec.attrs["aria-labelledby"] == "s1-title"
    (h2,) = find_all(sec, "h2")
    assert h2.attrs["id"] == "s1-title" and h2.all_text() == "Title"


def test_tabs_refuse_duplicate_ids():
    with pytest.raises(ValueError):
        ui.tabs("L", [("a", "A", "1"), ("a", "B", "2")])


def test_the_last_resort_fragment_raises_on_nothing():
    class Bad:
        def __str__(self):
            raise RuntimeError("no words")

    for words in ("x", None, 3, Bad()):
        out = ui.last_resort(words)
        assert type(out) is ui.Safe and 'role="alert"' in out and 'data-stamp="error"' in out


def test_none_renders_as_nothing_and_a_none_data_value_is_skipped():
    for out in (
        ui.badge("ok", None),
        ui.card("t", "b", actions=None),
        ui.field("l", name="n", id="i", value=None, placeholder=None),
        ui.button("b", data={"post": None}),
        ui.fragment(None, "x"),
    ):
        assert "None" not in out
    assert "data-post" not in ui.button("b", data={"post": None})
    assert "placeholder" not in ui.field("l", name="n", id="i", placeholder=None)


def test_bool_and_tuple_data_values_are_json():
    btn = find_all(parse(ui.button("b", data={"flag": True, "pair": (1, "a")})), "button")[0]
    assert btn.attrs["data-flag"] == "true" and btn.attrs["data-pair"] == '[1,"a"]'


@pytest.mark.parametrize(
    "key", ["kind", "severity", "state", "expanded", "lines", "clamp", "retry", "value-of"]
)
def test_a_data_key_owned_by_a_component_is_refused(key):
    with pytest.raises(ValueError):
        ui.button("b", data={key: "x"})


@pytest.mark.parametrize("key", ["stale", "ts", "cadence", "view"])
def test_a_data_key_app_js_or_a_component_writes_itself_is_refused(key):
    """`app.js` writes data-stale on a freshness stamp and data-view on <main>; `freshness` writes
    data-ts and data-cadence: a caller's value would be overwritten or misread."""
    with pytest.raises(ValueError):
        ui.group("b", data={key: "1"})


@pytest.mark.parametrize("key", ["refresh-s", "stamp", "filter", "filter-mode", "pick", "pick-to"])
def test_the_keys_views_declare_for_app_js_stay_allowed(key):
    """These are the views' and the server's own declarations to `app.js` — passed through `data=`."""
    assert f'data-{key}="1"' in ui.group("b", data={key: "1"})


def test_a_subclass_of_safe_is_escaped():
    class Sneaky(ui.Safe):
        pass

    assert "&lt;b&gt;" in ui.card("t", Sneaky("<b>x</b>"))


@pytest.mark.parametrize(
    "call",
    [
        lambda k: ui.button("b", data={k: "v"}),
        lambda k: ui.field("l", name="n", id="i", data={k: "v"}),
        lambda k: ui.group("b", data={k: "v"}),
        lambda k: ui.disclosure("s", "b", data={k: "v"}),
        lambda k: ui.table("l", "L", ["h"], [["c"]], row_data=[{k: "v"}]),
    ],
)
def test_a_data_attribute_name_outside_the_safe_alphabet_is_refused(call):
    for bad in ("a onfocus=x", 'a"b', "A", "a_b", ""):
        with pytest.raises(ValueError):
            call(bad)
    assert 'data-ok-1="v"' in call("ok-1")


def test_fragment_escapes_only_the_plain_parts():
    out = ui.fragment(ui.Safe("<b>kept</b>"), "<i>esc</i>", None)
    assert isinstance(out, ui.Safe)
    assert "<b>kept</b>" in out
    assert "&lt;i&gt;esc&lt;/i&gt;" in out
    # a plain join yields a plain str, which the next component escapes again
    joined = ui.Safe("<b>x</b>") + "y"
    assert not isinstance(joined, ui.Safe)
    assert "&lt;b&gt;" in ui.card("t", joined)


def test_a_mapping_value_becomes_json_in_the_attribute():
    out = ui.button("Go", data={"post": "/x", "body": {"a": "<b>", "n": 1}})
    btn = find_all(parse(out), "button")[0]
    assert btn.attrs["data-post"] == "/x"
    assert btn.attrs["data-body"] == '{"a":"<b>","n":1}'
    assert btn.attrs["type"] == "button"


# ---------------------------------------------------------------- badge
@pytest.mark.parametrize("sev", ui.SEVERITIES)
def test_each_severity_carries_an_icon_and_a_text_label(sev):
    root = parse(ui.badge(sev, "3 waiting"))
    badge = [n for n in root.walk() if n.attrs.get("data-severity") == sev]
    assert len(badge) == 1
    icon = [n for n in badge[0].walk() if n.attrs.get("aria-hidden") == "true"]
    assert icon and icon[0].all_text().strip() == ui.SEVERITY_ICONS[sev]
    text = badge[0].all_text()
    assert "3 waiting" in text
    assert cat.t(f"sev.{sev}") in text  # the severity in words, not only colour


def test_severities_are_the_five_named():
    assert ui.SEVERITIES == ("critical", "warning", "ok", "info", "neutral")
    assert len(set(ui.SEVERITY_ICONS.values())) == 5


# ---------------------------------------------------------------- select, aligned table, status text
def test_a_select_is_a_labelled_control_and_selects_the_matching_option_only():
    out = ui.select(
        "Cost",
        name="cost",
        id="cost-sel",
        options=[("", "All"), ("free", "Free"), (PAYLOAD, PAYLOAD)],
        value=PAYLOAD,
        data={"filter": "cost", "filter-mode": "token"},
    )
    root = parse(out)
    (lab,) = find_all(root, "label")
    (sel,) = find_all(root, "select")
    assert lab.attrs["for"] == sel.attrs["id"] == "cost-sel" and lab.all_text() == "Cost"
    assert sel.attrs["name"] == "cost" and sel.attrs["data-filter"] == "cost"
    assert sel.attrs["data-filter-mode"] == "token"
    opts = find_all(sel, "option")
    assert [o.attrs["value"] for o in opts] == ["", "free", PAYLOAD]
    assert [("selected" in o.attrs) for o in opts] == [False, False, True]
    assert PAYLOAD not in out and "<script>alert" not in out and ESCAPED in out


def test_a_select_matches_its_value_by_string_and_selects_nothing_for_an_unknown_one():
    out = ui.select("n", name="n", id="i", options=[(1, "One"), (2, "Two")], value=2)
    opts = find_all(parse(out), "option")
    assert [("selected" in o.attrs) for o in opts] == [False, True]
    out = ui.select("n", name="n", id="i", options=[(1, "One")], value="zzz")
    assert "selected" not in out


def test_a_select_refuses_a_bad_id_and_a_bad_data_key():
    for kw in ({"id": "a b"}, {"id": "1a"}, {"data": {"A": "x"}}, {"data": {"align": "x"}}):
        args = {"name": "n", "id": "i", "options": [("a", "A")]} | kw
        with pytest.raises(ValueError):
            ui.select("l", **args)


def test_a_table_aligns_the_named_columns_right_in_header_and_cells():
    out = ui.table("t", "T", ["Name", "Keys"], [["a", "1"], ["b", "22"]], align=[None, "right"])
    root = parse(out)
    heads = find_all(root, "th", scope="col")
    assert [h.attrs.get("data-align") for h in heads] == [None, "right"]
    cells = find_all(root, "td")
    assert [c.attrs.get("data-align") for c in cells] == ["right", "right"]
    assert all("data-align" not in r.attrs for r in find_all(root, "th", scope="row"))


def test_a_table_aligns_the_row_header_column_too_and_positional_calls_are_unchanged():
    out = ui.table("t", "T", ["N", "K"], [["1", "2"]], align=["right", None])
    (rowh,) = find_all(parse(out), "th", scope="row")
    assert rowh.attrs["data-align"] == "right"
    plain = ui.table("t", "T", ["N", "K"], [["1", "2"]])
    assert "data-align" not in plain
    assert plain == ui.table("t", "T", ["N", "K"], [["1", "2"]], align=None)
    assert "data-align" not in ui.table("t", "T", ["N", "K"], [["1", "2"]], align=[None, None])


@pytest.mark.parametrize("bad", ["left", "RIGHT", "", 1])
def test_a_table_refuses_an_align_entry_that_is_not_right_or_none(bad):
    with pytest.raises(ValueError):
        ui.table("t", "T", ["N", "K"], [["1", "2"]], align=[bad, None])


@pytest.mark.parametrize("bad", [["right"], ["right", None, None], "rt", ()])
def test_a_table_refuses_an_align_that_is_not_one_entry_per_column(bad):
    with pytest.raises(ValueError):
        ui.table("t", "T", ["N", "K"], [["1", "2"]], align=bad)


def test_a_status_text_is_a_polite_status_paragraph_with_its_hooks():
    out = ui.status_text("3 of 5", data={"filter-status": ""})
    (p,) = find_all(parse(out), "p")
    assert p.attrs["role"] == "status" and "data-filter-status" in p.attrs
    assert p.all_text() == "3 of 5"
    with pytest.raises(ValueError):
        ui.status_text("t", data={"Bad": "x"})


# ---------------------------------------------------------------- dialog, field, table, tabs
def test_the_dialog_is_native_has_a_verb_confirm_and_no_default_yes():
    out = ui.dialog(
        "dlg-a", "Accept W-1a2b?", "It authorises the deploy.", "Accept W-1a2b", "Keep waiting"
    )
    root = parse(out)
    dlg = find_all(root, "dialog")
    assert len(dlg) == 1 and dlg[0].attrs["id"] == "dlg-a"
    assert dlg[0].attrs.get("aria-modal") == "true"
    title_id = dlg[0].attrs["aria-labelledby"]
    assert find_all(root, id=title_id)[0].all_text() == "Accept W-1a2b?"
    confirm = [b for b in find_all(root, "button") if "data-dialog-confirm" in b.attrs]
    cancel = [b for b in find_all(root, "button") if "data-dialog-cancel" in b.attrs]
    assert confirm[0].all_text() == "Accept W-1a2b" and cancel[0].all_text() == "Keep waiting"
    assert all("autofocus" not in b.attrs for b in find_all(root, "button"))
    assert not find_all(root, "textarea")
    assert "It authorises the deploy." in dlg[0].all_text()
    forms = find_all(dlg[0], "form")
    assert len(forms) == 1 and forms[0].attrs.get("method") == "dialog"


def test_value_of_names_its_input_in_data_value_of():
    span = find_all(parse(ui.value_of("cap-a")), "span")[0]
    assert span.attrs["data-value-of"] == "cap-a"


@pytest.mark.parametrize("note", ["optional", "required"])
def test_the_dialog_textarea_appears_only_with_a_note(note):
    root = parse(ui.dialog("d", "T", "B", "Reject", "Keep", note=note))
    ta = find_all(root, "textarea")
    assert len(ta) == 1
    label = [n for n in find_all(root, "label") if n.attrs.get("for") == ta[0].attrs["id"]]
    assert label and label[0].all_text() == cat.t(f"dialog.note.{note}")
    assert ("required" in ta[0].attrs) is (note == "required")


@pytest.mark.parametrize("kind", ["text", "textarea", "number", "search"])
def test_every_field_has_a_visible_label_for_its_id(kind):
    root = parse(ui.field("Weekly cap", name="cap", kind=kind, id="cap-a", min=0, max=100))
    ctrl = [n for n in root.walk() if n.tag in ("input", "textarea")]
    assert len(ctrl) == 1 and ctrl[0].attrs["id"] == "cap-a" and ctrl[0].attrs["name"] == "cap"
    label = find_all(root, "label")
    assert len(label) == 1 and label[0].attrs["for"] == "cap-a"
    assert label[0].all_text() == "Weekly cap"
    if kind == "number":
        assert ctrl[0].attrs["min"] == "0" and ctrl[0].attrs["max"] == "100"
    if kind in ("text", "search", "number"):
        assert ctrl[0].attrs["type"] == kind


def test_the_table_is_a_labelled_scroll_region_around_a_real_table():
    out = ui.table(
        "t-acc",
        "Accounts",
        ["Account", "Weekly"],
        [["a@x", "40%"], ["b@x", ui.badge("ok", "fine")]],
        row_data=[{"f-tag": "api"}, None],
    )
    root = parse(out)
    region = [n for n in root.walk() if n.attrs.get("role") == "region"]
    assert len(region) == 1
    assert region[0].attrs["aria-labelledby"] == "t-acc" and region[0].attrs["tabindex"] == "0"
    assert find_all(root, id="t-acc")[0].all_text() == "Accounts"
    assert [h.all_text() for h in find_all(root, "th", scope="col")] == ["Account", "Weekly"]
    rows = find_all(find_all(root, "tbody")[0], "tr")
    assert len(rows) == 2 and rows[0].attrs.get("data-f-tag") == "api"
    assert [h.all_text() for h in find_all(root, "th", scope="row")] == ["a@x", "b@x"]
    assert find_all(rows[1], "td")[0].all_text().strip().endswith("fine")


def test_the_tabs_follow_the_apg_markup():
    root = parse(ui.tabs("Usage", [("u-day", "Day", "d"), ("u-week", "Week", "w")]))
    tl = [n for n in root.walk() if n.attrs.get("role") == "tablist"]
    assert tl and tl[0].attrs["aria-label"] == "Usage"
    tabs = [n for n in root.walk() if n.attrs.get("role") == "tab"]
    panels = [n for n in root.walk() if n.attrs.get("role") == "tabpanel"]
    assert [t.attrs["aria-selected"] for t in tabs] == ["true", "false"]
    assert [t.attrs["tabindex"] for t in tabs] == ["0", "-1"]
    for tab, panel in zip(tabs, panels, strict=True):
        assert tab.attrs["aria-controls"] == panel.attrs["id"]
        assert panel.attrs["aria-labelledby"] == tab.attrs["id"]
    assert "hidden" not in panels[0].attrs and "hidden" in panels[1].attrs


def test_region_state_freshness_live_region_and_banner():
    err = parse(ui.region_state("error", "Failed to load.", retry=True))
    box = [n for n in err.walk() if n.attrs.get("data-state") == "error"][0]
    assert box.attrs["role"] == "alert" and "Failed to load." in box.all_text()
    assert [b for b in find_all(err, "button") if "data-retry" in b.attrs][0].all_text() == cat.t(
        "state.retry"
    )
    load = parse(ui.region_state("loading", "Loading"))
    assert [n for n in load.walk() if n.attrs.get("data-state") == "loading"][0].attrs[
        "role"
    ] == "status"
    t = find_all(parse(ui.freshness(0.0, 20)), "time")[0]
    assert t.attrs["datetime"] == "1970-01-01T00:00:00+00:00" and t.attrs["data-cadence"] == "20"
    assert t.attrs["data-ts"] == "0"
    never_stale = find_all(parse(ui.freshness(0.0, None)), "time")[0]
    assert never_stale.attrs["data-cadence"] == ""
    live = [n for n in parse(ui.live_region()).walk() if n.attrs.get("aria-live") == "polite"]
    assert len(live) == 1
    banner = [
        n
        for n in parse(ui.stale_banner("4 min", "no regeneration finished")).walk()
        if n.attrs.get("role") == "alert"
    ]
    assert (
        banner
        and "4 min" in banner[0].all_text()
        and "no regeneration finished" in banner[0].all_text()
    )
    assert "style=" not in ui.stale_banner("4 min", "c")


# ---------------------------------------------------------------- shell
def _shell() -> str:
    return ui.shell([("overview", "Overview"), ("work", "Work")], "work")


@pytest.mark.parametrize(
    "kind,retry", [("error", False), ("loading", True), ("empty", True), ("loading", False)]
)
def test_retry_shows_only_on_an_error_that_asks_for_it(kind, retry):
    root = parse(ui.region_state(kind, "m", retry=retry))
    assert [b for b in find_all(root, "button") if "data-retry" in b.attrs] == []
    assert cat.t("state.retry") not in root.all_text()


@pytest.mark.parametrize(
    "read_ts,cadence",
    [
        (float("nan"), 20),
        (float("inf"), 20),
        (-1.0, 20),
        (True, 20),
        ("12", 20),
        (1e300, 20),
        (1.0, 0),
        (1.0, -5),
        (1.0, float("nan")),
        (1.0, float("inf")),
        (1.0, True),
        (1.0, "20"),
    ],
)
def test_freshness_refuses_a_timestamp_or_cadence_that_is_not_a_real_number(read_ts, cadence):
    with pytest.raises(ValueError):
        ui.freshness(read_ts, cadence)


def test_the_skip_link_is_the_first_focusable_element():
    root = parse(_shell())
    body = find_all(root, "body")[0]
    focusable = [
        n
        for n in body.walk()
        if (n.tag == "a" and "href" in n.attrs)
        or n.tag in ("button", "input", "select", "textarea")
        or n.attrs.get("tabindex") == "0"
    ]
    first = focusable[0]
    assert first.tag == "a" and first.attrs["href"] == "#view"
    assert first.all_text() == cat.t("shell.skip")
    main = find_all(root, "main")
    assert len(main) == 1 and main[0].attrs["id"] == "view" and main[0].attrs["data-view"] == "work"
    assert len(find_all(root, "h1")) == 1
    assert find_all(root, "html")[0].attrs["lang"] == cat.t("app.lang")


def test_the_theme_script_runs_in_head_before_the_stylesheet_inside_try():
    html = _shell()
    root = parse(html)
    head = find_all(root, "head")[0]
    order = [n for n in head.children if n.tag in ("script", "link")]
    inline = [
        n
        for n in order
        if n.tag == "script" and "src" not in n.attrs and n.attrs.get("type") is None
    ]
    css = [n for n in order if n.tag == "link" and n.attrs.get("rel") == "stylesheet"]
    assert inline and css and css[0].attrs["href"] == "/static/app.css"
    assert order.index(inline[0]) < order.index(css[0])
    code = inline[0].all_text()
    try_at, read_at, catch_at = code.find("try"), code.find("localStorage"), code.find("catch")
    assert -1 < try_at < read_at < catch_at
    assert "qd-theme" in code and "data-theme" in code
    scripts = [n for n in root.walk() if n.tag == "script" and n.attrs.get("src")]
    assert [s.attrs["src"] for s in scripts] == ["/static/app.js"]
    assert "<iframe" not in html and "style=" not in html


def test_the_shell_navigation_and_menu_button():
    root = parse(_shell())
    nav = find_all(root, "nav")
    assert len(nav) == 1 and nav[0].attrs["aria-label"] == cat.t("shell.nav_label")
    links = find_all(nav[0], "a")
    assert [(a.attrs["href"], a.all_text()) for a in links] == [
        ("#overview", "Overview"),
        ("#work", "Work"),
    ]
    assert [a.attrs.get("aria-current") for a in links] == [None, "page"]
    menu = [b for b in find_all(root, "button") if "data-menu" in b.attrs][0]
    assert (
        menu.attrs["aria-expanded"] == "false" and menu.attrs["aria-controls"] == nav[0].attrs["id"]
    )


def test_the_shell_hands_the_catalogue_to_the_script_as_inert_json():
    import json

    root = parse(_shell())
    blob = [
        n for n in root.walk() if n.tag == "script" and n.attrs.get("type") == "application/json"
    ]
    assert len(blob) == 1 and blob[0].attrs["id"] == "qd-strings"
    assert json.loads(blob[0].all_text()) == cat.CATALOGUE
    with cat.use({**cat.CATALOGUE, "act.done": "</script><script>alert(1)</script>"}):
        assert "</script><script>alert" not in ui.shell([("o", "O")], "o")


# ---------------------------------------------------------------- the catalogue
def test_an_unknown_key_raises():
    with pytest.raises(KeyError):
        cat.t("no.such.key")
    with cat.use({"a": "A"}), pytest.raises(KeyError):
        cat.t("sev.ok")


def test_a_template_with_slots_called_without_fields_raises():
    with pytest.raises(KeyError):
        cat.t("act.failed")


def test_use_is_isolated_per_thread_when_blocks_interleave():
    import threading

    a, b = {**cat.CATALOGUE, "sev.ok": "A"}, {**cat.CATALOGUE, "sev.ok": "B"}
    seen: dict[str, str] = {}
    a_in, b_in, a_out = threading.Event(), threading.Event(), threading.Event()

    def run_a():
        with cat.use(a):
            a_in.set()
            b_in.wait(5)
            seen["a"] = cat.t("sev.ok")
        a_out.set()

    def run_b():
        a_in.wait(5)
        with cat.use(b):
            b_in.set()
            a_out.wait(5)
            seen["b"] = cat.t("sev.ok")

    ts = [threading.Thread(target=run_a), threading.Thread(target=run_b)]
    for th in ts:
        th.start()
    for th in ts:
        th.join(10)
    assert seen == {"a": "A", "b": "B"}
    assert cat.t("sev.ok") == cat.CATALOGUE["sev.ok"]


def test_t_formats_fields():
    assert cat.t("act.failed", error="boom") == cat.CATALOGUE["act.failed"].format(error="boom")
    assert "boom" in cat.t("act.failed", error="boom")


def _every_component() -> str:
    return ui.fragment(
        *(ui.badge(s, "x") for s in ui.SEVERITIES),
        ui.dialog("d1", "T", "B", "Go", "Stop", note="optional"),
        ui.dialog("d2", "T", "B", "Go", "Stop", note="required"),
        ui.clamp("question"),
        ui.region_state("error", "m", retry=True),
        ui.freshness(0.0, 20),
        ui.freshness(None, 20),
        ui.live_region(),
        ui.stale_banner("1 min", "c"),
        ui.shell([("o", "O")], "o"),
    )


def test_under_a_stand_in_catalogue_no_built_in_english_remains():
    english = _every_component()
    stand_in = {k: "§" + k for k in cat.CATALOGUE}
    with cat.use(stand_in):
        out = _every_component()
    used = [k for k, v in cat.CATALOGUE.items() if len(v) >= 4 and v in english]
    assert len(used) >= 15  # the positive control: the English render did carry the catalogue
    for k in used:
        visible = cat.CATALOGUE[k]
        # the JSON blob carries every key; strip it so the check reads the visible markup
        assert visible not in re.sub(
            r'<script type="application/json".*?</script>', "", out, flags=re.S
        ), k
    for k in (
        "sev.critical",
        "dialog.note.required",
        "clamp.more",
        "state.retry",
        "shell.skip",
        "stale.banner",
    ):
        assert "§" + k in out, k


_NAME = re.compile(r"[a-z0-9_.:# \\\x00-]*")
_ATTR_FRAGMENT = re.compile(r'(\s+[a-z-]+(="[^"<>]*")?)+\s*')
_LABEL_ATTRS = ("aria-label", "title", "alt", "placeholder", "aria-description")
_ALLOWED = {"%H:%M:%S"}  # a strftime format, not words


_LABEL_CALLS = ("_choice", "_id", "_flag", "_real")
_EXTRA_NAMES = {"page"}  # the aria-current token


def _known_names(tree, texts: list[str]) -> set[str]:
    """Words the module uses as NAMES: tag and attribute names and values in its markup, `_attr`
    attribute names, and the string values of its module-level constants (kinds, severities, keys)."""
    import ast

    names: list[str] = []
    for text in texts:
        for tag in re.findall(r"<[^<>]*>?", text):
            names.append(re.sub(r'"[^"]*"', " ", tag))
            names += re.findall(r'"([^"]*)"', tag)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_attr" and node.args:
            if isinstance(node.args[0], ast.Constant):
                names.append(str(node.args[0].value))
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and not any(
            getattr(t, "id", "") == "_THEME_SCRIPT" for t in getattr(node, "targets", [])
        ):
            names += [
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            ]
    words = {w for n in names for w in re.findall(r"[a-z]+", n)}
    return words | _EXTRA_NAMES


def _visible_words(src: str) -> list[str]:
    """Every string literal in ``src`` that would put WORDS on the page: text between tags, or a
    labelling attribute's value. Literals inside t() calls, raise statements and docstrings, and
    literals that are names (attribute names, keys, enum values), are not words."""
    import ast

    tree = ast.parse(src)
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t":
            skip |= {id(n) for n in ast.walk(node)}
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in (
            "compile",
            "fullmatch",
            "match",
            "sub",
            "encode",  # codec and error-handler names, never page words
        ):
            # only the ARGUMENTS are patterns or codec names; the receiver is still scanned
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                skip |= {id(n) for n in ast.walk(arg)}
        if isinstance(node, ast.Raise):
            skip |= {id(n) for n in ast.walk(node)}
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in _LABEL_CALLS:
            skip |= {id(n) for n in ast.walk(node)}  # error-message labels, never on the page
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skip.add(id(first.value))
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "_THEME_SCRIPT" for t in node.targets
        ):
            skip |= {id(n) for n in ast.walk(node)}
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_attr"
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in _LABEL_ATTRS
            and isinstance(node.args[1], ast.Constant)
            and re.search("[A-Za-z]", str(node.args[1].value))
        ):
            return [str(node.args[1].value)]
    texts = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.JoinedStr):
            skip |= {id(v) for v in node.values}
            texts.append(
                "".join(v.value if isinstance(v, ast.Constant) else "\0" for v in node.values)
            )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            texts.append(node.value)
    known = _known_names(tree, texts)
    bad = []
    for text in texts:
        if text in _ALLOWED:
            continue
        if "<" not in text and ">" not in text and _NAME.fullmatch(text):
            # a name-like literal: every word of four letters or more must be a name the module uses
            if any(len(w) >= 4 and w not in known for w in re.findall(r"[a-z]+", text)):
                bad.append(text)
            continue
        for attr in _LABEL_ATTRS:
            for value in re.findall(attr + r'="([^"\0]*)"', text):
                if re.search("[A-Za-z]", value):
                    bad.append(value)
        if "<" not in text and ">" not in text and _ATTR_FRAGMENT.fullmatch(text):
            continue
        stripped = re.sub(r"<[^<>]*>", "", text)
        stripped = re.sub(r"^[^<]*>", "", stripped) if ">" in stripped.split("<")[0] else stripped
        stripped = re.sub(r"<[^>]*$", "", stripped)
        if re.search("[A-Za-z]", stripped):
            bad.append(text)
    return bad


def test_no_user_visible_literal_in_components_outside_the_catalogue():
    """Words come from strings.t: no literal in components.py puts English on the page."""
    assert _visible_words((_PKG / "components.py").read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "mutant",
    [
        "def f():\n    return Safe('<p>Close:</p>')\n",
        "def f(x):\n    return Safe(f'<p class=\"a\">{x} more</p>')\n",
        "def f():\n    return Safe('<button aria-label=\"Close\">x</button>')\n",
        "def f():\n    return _attr('aria-label', 'close')\n",
        "def f():\n    return 'Close'\n",
    ],
)
def test_the_literal_guard_catches_hard_coded_words(mutant):
    assert _visible_words(mutant) != []


# ---------------------------------------------------------------- app.css: tokens and contrast
_CSS = _PKG / "static" / "app.css"
_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


def _css() -> str:
    return re.sub(r"/\*.*?\*/", "", _CSS.read_text(encoding="utf-8"), flags=re.S)


def _blocks(css: str) -> list[tuple[str, str]]:
    """(selector-or-at-rule, body) for every top-level block; a nested @media yields its inner blocks."""
    out, i = [], 0
    while True:
        m = re.compile(r"([^{}]+)\{").search(css, i)
        if not m:
            return out
        depth, j = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        sel, body = m.group(1).strip(), css[m.end() : j - 1]
        if sel.startswith("@media") and "{" in body:
            out += [(sel + " " + s, b) for s, b in _blocks(body)]
        else:
            out.append((sel, body))
        i = j


def _decls(body: str) -> dict[str, str]:
    return {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in body.split(";") if ":" in d)}


def _palette_and_mappings():
    blocks = _blocks(_css())
    palette = [
        b
        for s, b in blocks
        if s == ":root" and _decls(b) and all(k.startswith("--c-") for k in _decls(b))
    ]
    assert len(palette) == 1, "exactly one :root palette block of --c-* values"
    light = [b for s, b in blocks if s == ":root" and "--surface" in _decls(b)]
    dark = [b for s, b in blocks if s == '[data-theme="dark"]' and "--surface" in _decls(b)]
    system = [
        b
        for s, b in blocks
        if s.startswith("@media")
        and "prefers-color-scheme: dark" in s
        and ':root:not([data-theme="light"])' in s
    ]
    assert len(light) == len(dark) == len(system) == 1
    return _decls(palette[0]), _decls(light[0]), _decls(dark[0]), _decls(system[0])


_NAMED = frozenset(
    re.findall(
        r"[a-z]+",
        "aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown "
        "burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan "
        "darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred "
        "darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink "
        "deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold "
        "goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush "
        "lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey "
        "lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime "
        "limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen "
        "mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin "
        "navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise "
        "palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue "
        "saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow "
        "springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen "
        "canvas canvastext linktext visitedtext activetext buttonface buttontext buttonborder field fieldtext "
        "highlight highlighttext mark marktext graytext accentcolor accentcolortext",
    )
)
_COLOUR_FN = re.compile(
    r"\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix|[a-z-]*gradient)\(", re.I
)


def _colour_leaks(css: str) -> list[str]:
    """Every colour that is not a palette reference, outside the one palette block."""
    blocks = _blocks(css)
    out = []
    for sel, body in blocks:
        decls = _decls(body)
        if sel == ":root" and decls and all(k.startswith("--c-") for k in decls):
            continue
        for prop, value in decls.items():
            v = re.sub(r"var\(--[a-z0-9-]+(,[^)]*)?\)", "", value)
            if _COLOUR.search(v) or _COLOUR_FN.search(v):
                out.append(f"{sel} {prop}: {value}")
                continue
            words = re.findall(r"(?<![-\w])[a-zA-Z]+(?![-\w(])", v)
            if prop != "font-family" and any(w.lower() in _NAMED for w in words):
                out.append(f"{sel} {prop}: {value}")
    return out


def test_no_colour_literal_outside_the_one_palette_block():
    css = _css()
    pal = [
        b
        for s, b in _blocks(css)
        if s == ":root" and all(k.startswith("--c-") for k in _decls(b)) and _decls(b)
    ]
    assert len(pal) == 1
    assert all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in _decls(pal[0]).values())
    assert _colour_leaks(css) == []
    src = (_PKG / "components.py").read_text(encoding="utf-8")
    assert _COLOUR.findall(src) == [] and not _COLOUR_FN.search(src)
    assert "style=" not in src and "<iframe" not in src


@pytest.mark.parametrize(
    "mutant",
    [
        ".x { color: white; }",
        ".x { background: color-mix(in srgb, var(--surface) 50%, var(--text)); }",
        ".x { background: linear-gradient(black, hotpink); }",
        ".x { border: 1px solid #000; }",
        ".x { box-shadow: 0 0 0 1px rgb(0 0 0); }",
        ".x { color: oklch(50% 0.1 30); }",
    ],
)
def test_the_colour_guard_catches_every_colour_shape(mutant):
    assert _colour_leaks(_css() + mutant) != []


def _lum(hexv: str) -> float:
    h = hexv.lstrip("#")
    ch = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_the_luminance_formula_is_the_wcag_one():
    assert round(_ratio("#000000", "#ffffff"), 2) == 21.0
    assert round(_ratio("#777777", "#ffffff"), 2) == 4.48


SURFACES = ("--surface", "--surface-1", "--surface-2")
# every token app.css paints TEXT with: the body text, muted text, links (accent), the inline error
# and stale stamp (severities), and the danger colour
TEXT = ("--text", "--text-muted", "--accent", "--danger") + tuple(
    f"--sev-{s}" for s in ui.SEVERITIES
)
MARKS = ("--border", "--focus")
ON = (("--on-accent", "--accent"), ("--on-danger", "--danger"))


def _text_tokens_used_in_css() -> set[str]:
    out = set()
    for _sel, body in _blocks(_css()):
        for prop, value in _decls(body).items():
            if prop == "color":
                out |= set(re.findall(r"var\((--[a-z0-9-]+)\)", value))
    return out


def test_every_token_used_as_text_is_graded_as_text():
    assert _text_tokens_used_in_css() - set(TEXT) - {"--on-accent", "--on-danger"} == set()


def test_every_mapping_is_palette_references_only_and_the_two_dark_ones_match():
    palette, light, dark, system = _palette_and_mappings()
    for mapping in (light, dark, system):
        for k, v in mapping.items():
            if k == "color-scheme":
                continue
            m = re.fullmatch(r"var\((--c-[a-z0-9-]+)\)", v)
            assert m and m.group(1) in palette, (k, v)
    assert dark == system
    assert set(light) == set(dark) >= set(SURFACES + TEXT + MARKS + tuple(a for a, _ in ON))


def test_color_scheme_follows_the_theme():
    _palette, light, dark, system = _palette_and_mappings()
    assert (
        light["color-scheme"] == "light"
        and dark["color-scheme"] == "dark" == system["color-scheme"]
    )
    forced_light = [b for s, b in _blocks(_css()) if s == '[data-theme="light"]']
    assert forced_light and _decls(forced_light[0])["color-scheme"] == "light"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_contrast_is_computed_for_every_pair_in_both_themes(theme):
    palette, light, dark, _ = _palette_and_mappings()
    mapping = light if theme == "light" else dark

    def col(tok: str) -> str:
        return palette[re.fullmatch(r"var\((--c-[a-z0-9-]+)\)", mapping[tok]).group(1)]

    low = []
    for s in SURFACES:
        low += [(t, s, 4.5) for t in TEXT]
        low += [(m, s, 3.0) for m in MARKS]
    low += [(a, b, 4.5) for a, b in ON]
    failures = [
        (a, b, round(_ratio(col(a), col(b)), 2), need)
        for a, b, need in low
        if _ratio(col(a), col(b)) < need
    ]
    assert failures == []
    assert len(low) == 3 * (len(TEXT) + len(MARKS)) + len(ON)


def _rule(selector: str) -> dict[str, str]:
    hits = [_decls(b) for s, b in _blocks(_css()) if selector in [x.strip() for x in s.split(",")]]
    assert hits, selector
    merged: dict[str, str] = {}
    for h in hits:
        merged.update(h)
    return merged


_OUTLINE_OFF = re.compile(r"outline\s*:\s*(none|0)\b|outline-(width|style)\s*:\s*(0|none)\b")


def test_layout_rules_mobile_first_motion_and_focus():
    css = _css()
    media = [s for s, _ in _blocks(css) if s.startswith("@media")]
    assert not any("max-width" in m for m in media)
    widths = set(re.findall(r"@media[^{]*min-width:\s*(\d+)px", css))
    assert widths == {"640", "768", "1024", "1280", "1536"}
    reduced = [_decls(b) for s, b in _blocks(css) if "prefers-reduced-motion: reduce" in s]
    assert reduced and reduced[0]["transition-duration"].startswith("0ms")
    assert reduced[0]["animation-duration"].startswith("0ms")
    html = _rule("html")
    assert html["--target"] == "24px" and html["--ring"] == "2px"
    coarse = [_decls(b) for s, b in _blocks(css) if "pointer: coarse" in s]
    assert coarse and coarse[0]["--target"] == "44px"
    focus = _rule(":focus-visible")
    assert "var(--ring)" in focus["outline"] and "var(--focus)" in focus["outline"]
    assert _OUTLINE_OFF.findall(css) == []
    assert "scroll-padding-top" in html


@pytest.mark.parametrize(
    "mutant",
    [
        ".x { outline: none; }",
        ".x { outline: 0; }",
        ".x { outline-width: 0; }",
        ".x { outline-style: none; }",
    ],
)
def test_the_focus_guard_catches_every_way_to_remove_the_ring(mutant):
    assert _OUTLINE_OFF.findall(mutant)


def test_scroll_containers_leave_room_for_the_focus_ring():
    for sel in (".table-wrap", ".sidebar"):
        rule = _rule(sel)
        assert "padding" in rule and "scroll-padding" in rule, sel


def test_the_topbar_height_is_fixed_and_the_brand_ellipsises():
    bar = _rule(".topbar")
    assert bar.get("height") == "var(--topbar-h)" and "min-height" not in bar
    brand = _rule(".brand")
    assert brand.get("text-overflow") == "ellipsis" and brand.get("white-space") == "nowrap"


def test_the_table_region_has_a_max_height_so_its_header_sticks():
    assert _rule(".table-wrap").get("max-height") == "70vh"


def test_a_disabled_button_is_muted_and_dashed_not_faded():
    rule = _rule(".btn:disabled")
    assert "opacity" not in rule and rule.get("color") == "var(--text-muted)"
    assert rule.get("border-style") == "dashed"


# ---------------------------------------------------------------- review round 2 regressions
@pytest.mark.parametrize(
    "text", ["my.repo", "a@x.com", "1", "", "with space", "ünïcode", "a" * 300, "W-1a2b"]
)
def test_slug_maps_any_string_to_a_valid_stable_id(text):
    sid = ui.slug(text)
    assert re.fullmatch(r"[A-Za-z][\w:-]*", sid, re.ASCII)
    assert ui.slug(text) == sid
    assert f'id="{sid}"' in ui.card("t", "b", id=sid)
    assert ui.slug(text, prefix="card").startswith("card-")


def test_slug_keeps_different_strings_apart():
    texts = ["my.repo", "my-repo", "my_repo", "my repo", "a@x.com", "a-x-com", "1", "01", "", " "]
    assert len({ui.slug(s) for s in texts}) == len(texts)


def test_slug_refuses_a_prefix_that_is_not_an_id():
    with pytest.raises(ValueError):
        ui.slug("x", prefix="1bad")


@pytest.mark.parametrize(
    "mutant",
    [
        "def f():\n    return 'close'\n",
        "def f(x):\n    return x + ' more'\n",
        "def f():\n    return 'Close'.encode()\n",
        "def f():\n    return Safe('<p>Close the door</p>'.encode().decode())\n",
    ],
)
def test_the_literal_guard_catches_lowercase_words(mutant):
    assert _visible_words(mutant) != []


def test_a_disabled_button_of_every_kind_is_muted_on_a_surface():
    blocks = [(s, _decls(b)) for s, b in _blocks(_css())]
    hit = [d for s, d in blocks if ".btn[data-kind]:disabled" in [x.strip() for x in s.split(",")]]
    assert hit, "a rule covering disabled buttons of every kind"
    rule = hit[0]
    assert rule["background"] == "var(--surface-1)" and rule["border-color"] == "var(--border)"
    assert rule["color"] == "var(--text-muted)"
    sels = [x.strip() for s, _ in blocks for x in s.split(",") if ":disabled" in s and s == s]
    assert ".btn[data-kind]:disabled:hover" in sels
    palette, light, dark, _ = _palette_and_mappings()
    for mapping in (light, dark):

        def col(tok, mapping=mapping):
            return palette[re.fullmatch(r"var\((--c-[a-z0-9-]+)\)", mapping[tok]).group(1)]

        assert _ratio(col("--text-muted"), col("--surface-1")) >= 4.5
        assert _ratio(col("--border"), col("--surface-1")) >= 3.0


@pytest.mark.parametrize(
    "text", [chr(55357), __import__("os").fsdecode(b"\xff"), "repo-" + chr(0xDC80)]
)
def test_slug_survives_a_surrogate_escaped_name(text):
    sid = ui.slug(text)
    assert re.fullmatch(r"[A-Za-z][\w:-]*", sid, re.ASCII)
    assert ui.slug(text) == sid and ui.slug(text) != ui.slug("")


def test_only_a_long_badge_is_marked_to_wrap():
    """`data-wrap` from `BADGE_WRAP_AT` visible characters on — escaped text counts as the reader
    sees it, so `&lt;` is one character, not four."""
    assert "data-wrap" not in ui.badge("info", "1-design")
    assert "data-wrap" not in ui.badge("warning", "<" * (ui.BADGE_WRAP_AT - 1))
    assert "data-wrap" in ui.badge("critical", "x" * ui.BADGE_WRAP_AT)
    assert "data-wrap" in ui.badge("critical", ui.fragment("budget failed: ", "y" * 40))


# ---------------------------------------------------------------- review pass 1: select values, headers
def test_a_select_defaults_to_selecting_the_empty_valued_option_alone():
    opts = [("", "All"), ("free", "Free"), ("paid", "Paid")]
    for kw in ({}, {"value": None}, {"value": ""}):
        out = ui.select("c", name="c", id="i", options=opts, **kw)
        sel = [o.attrs["value"] for o in find_all(parse(out), "option") if "selected" in o.attrs]
        assert sel == [""], kw
    out = ui.select("c", name="c", id="i", options=[("free", "Free"), ("paid", "Paid")])
    assert "selected" not in out  # no empty-valued option, nothing to select by default


def test_an_option_whose_value_is_none_renders_empty_and_is_selected_as_empty():
    opts = [("free", "Free"), (None, "All")]
    for value in ("", None):
        out = ui.select("c", name="c", id="i", options=opts, value=value)
        picked = [o.attrs["value"] for o in find_all(parse(out), "option") if "selected" in o.attrs]
        assert picked == [""], value


def test_a_positional_table_call_accepts_any_iterable_of_headers():
    out = ui.table("t", "T", (h for h in ["a", "b"]), [["1", "2"]])
    assert [h.all_text() for h in find_all(parse(out), "th", scope="col")] == ["a", "b"]
    out = ui.table("t", "T", (h for h in ["a", "b"]), [["1", "2"]], align=[None, "right"])
    heads = find_all(parse(out), "th", scope="col")
    assert [h.attrs.get("data-align") for h in heads] == [None, "right"]


# ---------------------------------------------------------------- review pass 3: two contracts at the component
def test_a_filter_section_disclosure_needs_an_id():
    with pytest.raises(ValueError):
        ui.disclosure("s", "b", data={"filter-section": ""})
    out = ui.disclosure("s", "b", data={"filter-section": ""}, id="sec-a")
    assert 'id="sec-a"' in out and "data-filter-section" in out
    assert "<details" in ui.disclosure("s", "b")  # an ordinary disclosure still needs none


def test_a_filter_select_always_offers_the_empty_all_option():
    for options in ([], [("free", "Free")], [(None, "x"), ("a", "A")][1:]):
        with pytest.raises(ValueError):
            ui.select("c", name="c", id="i", options=options, data={"filter": "cost"})
    for options in ([("", "All"), ("free", "Free")], [(None, "All")]):
        out = ui.select("c", name="c", id="i", options=options, data={"filter": "cost"})
        assert "data-filter" in out
    # a select that is no filter control has no such obligation
    assert "<select" in ui.select("c", name="c", id="i", options=[("free", "Free")])
