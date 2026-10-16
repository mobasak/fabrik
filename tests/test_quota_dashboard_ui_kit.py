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
def _calls(x):
    """Every component called with the payload in ONE argument position at a time.

    Returns (name, thunk) pairs; numeric / enumerated arguments are covered by `_refusals`."""
    sev = "warning"
    return [
        ("badge.text", lambda: ui.badge(sev, x)),
        ("card.title", lambda: ui.card(x, "b")),
        ("card.body", lambda: ui.card("t", x)),
        ("card.badge", lambda: ui.card("t", "b", badge=x)),
        ("card.age", lambda: ui.card("t", "b", age=x)),
        ("card.actions", lambda: ui.card("t", "b", actions=x)),
        ("card.id", lambda: ui.card("t", "b", id=x)),
        ("table.label_id", lambda: ui.table(x, "L", ["h"], [["c"]])),
        ("table.label", lambda: ui.table("l", x, ["h"], [["c"]])),
        ("table.header", lambda: ui.table("l", "L", [x], [["c"]])),
        ("table.cell0", lambda: ui.table("l", "L", ["h", "i"], [[x, "c"]])),
        ("table.cell1", lambda: ui.table("l", "L", ["h", "i"], [["c", x]])),
        ("table.row_data", lambda: ui.table("l", "L", ["h"], [["c"]], row_data=[{"k": x}])),
        ("button.label", lambda: ui.button(x)),
        ("button.data", lambda: ui.button("b", data={"body": x})),
        ("field.label", lambda: ui.field(x, name="n", id="i")),
        ("field.name", lambda: ui.field("l", name=x, id="i")),
        ("field.id", lambda: ui.field("l", name="n", id=x)),
        ("field.value", lambda: ui.field("l", name="n", id="i", value=x)),
        ("field.textarea.value", lambda: ui.field("l", name="n", id="i", kind="textarea", value=x)),
        ("field.min", lambda: ui.field("l", name="n", id="i", kind="number", min=x)),
        ("field.max", lambda: ui.field("l", name="n", id="i", kind="number", max=x)),
        ("field.placeholder", lambda: ui.field("l", name="n", id="i", placeholder=x)),
        ("field.data", lambda: ui.field("l", name="n", id="i", data={"filter": x})),
        ("group.body", lambda: ui.group(x)),
        ("group.data", lambda: ui.group("b", data={"pick": x})),
        ("group.id", lambda: ui.group("b", id=x)),
        ("value_of", lambda: ui.value_of(x)),
        ("dialog.id", lambda: ui.dialog(x, "T", "B", "Go", "Stop")),
        ("dialog.title", lambda: ui.dialog("d", x, "B", "Go", "Stop")),
        ("dialog.body", lambda: ui.dialog("d", "T", x, "Go", "Stop")),
        ("dialog.confirm", lambda: ui.dialog("d", "T", "B", x, "Stop")),
        ("dialog.cancel", lambda: ui.dialog("d", "T", "B", "Go", x)),
        ("disclosure.summary", lambda: ui.disclosure(x, "b")),
        ("disclosure.body", lambda: ui.disclosure("s", x)),
        ("disclosure.data", lambda: ui.disclosure("s", "b", data={"k": x})),
        ("tabs.label", lambda: ui.tabs(x, [("a", "A", "a")])),
        ("tabs.id", lambda: ui.tabs("L", [(x, "A", "a")])),
        ("tabs.title", lambda: ui.tabs("L", [("a", x, "a")])),
        ("tabs.body", lambda: ui.tabs("L", [("a", "A", x)])),
        ("clamp.text", lambda: ui.clamp(x)),
        ("region_state.message", lambda: ui.region_state("error", x, retry=True)),
        ("stale_banner.age", lambda: ui.stale_banner(x, "c")),
        ("stale_banner.cause", lambda: ui.stale_banner("1 min", x)),
        ("shell.view_id", lambda: ui.shell([(x, "V")], x)),
        ("shell.view_title", lambda: ui.shell([("v", x)], "v")),
        ("fragment", lambda: ui.fragment(x)),
    ]


@pytest.mark.parametrize("name,call", _calls(PAYLOAD), ids=[n for n, _ in _calls(PAYLOAD)])
def test_every_component_escapes_every_argument(name, call):
    out = call()
    assert isinstance(out, ui.Safe), name
    assert PAYLOAD not in out, name
    assert "<script>alert" not in out, name
    assert ESCAPED in out, name


def test_the_escape_matrix_covers_every_component():
    """A component added without an escape case is a hole; the matrix names every public builder."""
    covered = {n.split(".")[0] for n, _ in _calls("x")}
    builders = {
        n
        for n, f in inspect.getmembers(ui, inspect.isfunction)
        if f.__module__ == ui.__name__ and not n.startswith("_")
    }
    assert builders - covered - {"live_region", "freshness"} == set()


@pytest.mark.parametrize(
    "call",
    [
        lambda: ui.badge(PAYLOAD, "t"),
        lambda: ui.button("b", kind=PAYLOAD),
        lambda: ui.field("l", name="n", id="i", kind=PAYLOAD),
        lambda: ui.group("b", tag=PAYLOAD),
        lambda: ui.dialog("d", "T", "B", "Go", "Stop", note=PAYLOAD),
        lambda: ui.region_state(PAYLOAD, "m"),
        lambda: ui.clamp("t", lines=PAYLOAD),
        lambda: ui.freshness(PAYLOAD, 20),
        lambda: ui.freshness(1.0, PAYLOAD),
    ],
)
def test_enumerated_and_numeric_arguments_refuse_anything_else(call):
    with pytest.raises((ValueError, TypeError)):
        call()


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


def test_no_user_visible_literal_in_components_outside_the_catalogue():
    """Every >-delimited text run in components.py source is markup only — words come from strings.t."""
    src = (_PKG / "components.py").read_text(encoding="utf-8")
    runs = re.findall(r">([A-Za-z][A-Za-z ,.'!?-]{2,})<", src)
    assert runs == []


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


def test_no_colour_literal_outside_the_one_palette_block():
    css = _css()
    pal = [
        b
        for s, b in _blocks(css)
        if s == ":root" and all(k.startswith("--c-") for k in _decls(b)) and _decls(b)
    ]
    assert len(pal) == 1
    rest = css.replace(pal[0], "")
    assert _COLOUR.findall(rest) == []
    assert all(
        _COLOUR.fullmatch(v) or re.fullmatch(r"#[0-9a-fA-F]{6}", v) for v in _decls(pal[0]).values()
    )
    src = (_PKG / "components.py").read_text(encoding="utf-8")
    assert _COLOUR.findall(src) == []
    assert "style=" not in src and "<iframe" not in src


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
TEXT = ("--text", "--text-muted")
MARKS = ("--border", "--focus", "--accent", "--danger") + tuple(f"--sev-{s}" for s in ui.SEVERITIES)
ON = (("--on-accent", "--accent"), ("--on-danger", "--danger"))


def test_every_mapping_is_palette_references_only_and_the_two_dark_ones_match():
    palette, light, dark, system = _palette_and_mappings()
    for mapping in (light, dark, system):
        for k, v in mapping.items():
            m = re.fullmatch(r"var\((--c-[a-z0-9-]+)\)", v)
            assert m and m.group(1) in palette, (k, v)
    assert dark == system
    assert set(light) == set(dark) >= set(SURFACES + TEXT + MARKS + tuple(a for a, _ in ON))


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


def test_layout_rules_mobile_first_motion_and_focus():
    css = _css()
    assert "max-width:" not in re.sub(
        r"\s", "", " ".join(s for s, _ in _blocks(css) if s.startswith("@media"))
    )
    widths = set(re.findall(r"@media[^{]*min-width:\s*(\d+)px", css))
    assert widths <= {"640", "768", "1024", "1280", "1536"} and "1024" in widths
    reduced = [b for s, b in _blocks(css) if "prefers-reduced-motion: reduce" in s]
    assert reduced and any(
        "transition-duration: 0ms" in b or "transition: none" in b for b in reduced
    )
    assert any("pointer: coarse" in s for s, _ in _blocks(css))
    assert "outline: none" not in css and "outline:none" not in css
    assert "scroll-padding-top" in css
