"""T07 — the page layer as one whole (plan 2026-10-17-plan-1, ticket T07).

Three scans over the integrated board. INV-4: no string that holds an HTML tag is built anywhere
but `dashboard_ui/components.py` — an AST walk over the dashboard module and every package module.
The catalogue (D-926): every view, rendered through the real module under a stand-in catalogue,
shows no catalogue-owned English, and no view module passes a word-bearing literal to a component.
INV-2: a fixed inventory of what today's five tabs showed — taken from the old builders before
they were deleted — renders in some view.

Every collector and the probe are stubbed with fixture data (the module's own `_view_data` and
`_render_view` run for real): nothing reads ~/.claude*, the fleet or the network.

Cobra check (D-253): the cheapest way to pass the tag scan without the outcome is to build markup
from pieces that hold no tag on their own (``"<" + tag``); the scan reads f-string parts with a
letter in place of each value and `%`/`.format` templates, and its own mutants pin each shape.
The cheapest way to pass the inventory is a test that renders a catalogue key without the datum
behind it; each entry asserts the fixture's value beside the key where the old tab showed one.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import string
import sys
import time
from pathlib import Path

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "scripts" / "sysadmin" / "quota_dashboard.py"
_PKG = _ROOT / "scripts" / "sysadmin" / "dashboard_ui"
sys.path.insert(0, str(_PKG.parent))

from dashboard_ui import strings as cat  # noqa: E402
from dashboard_ui.views import VIEWS  # noqa: E402

# ---------------------------------------------------------------- INV-4: the tag scan
_TAG = re.compile(r"<[a-zA-Z/!]")
_TEMPLATE_TAG = re.compile(r"<(?:%[-0-9.]*[sdrfi]|\{[^}]*\})")  # "<%s>" % tag, "<{}>".format(tag)
_PATTERN_CALLS = {
    "compile",
    "match",
    "fullmatch",
    "search",
    "sub",
    "subn",
    "findall",
    "finditer",
    "split",
}


def _markup_literals(src: str) -> list[tuple[int, str]]:
    """Every string constant in ``src`` that holds an HTML tag or a tag template. Docstrings are
    prose, and the pattern argument of an `re` call READS markup (the corpus's comments), never
    builds it; everything else counts — a plain literal, an f-string's text with a letter standing
    in for each value, a `%` or `.format` template."""
    tree = ast.parse(src)
    skip: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and body
        ):
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skip.add(id(first.value))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _PATTERN_CALLS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
            and node.args
        ):
            skip |= {id(n) for n in ast.walk(node.args[0])}
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, bytes) and b"<" in node.value:
            out.append((node.lineno, repr(node.value[:80])))  # b"<b>".decode() builds markup too
            continue
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "chr"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == 60
        ):
            out.append((node.lineno, "chr(60)"))  # "<" spelled as a code point
            continue
        if (isinstance(node, ast.Attribute) and node.attr == "Template"
                and getattr(node.value, "id", "") == "string") or (
            isinstance(node, ast.ImportFrom) and node.module == "string"
            and any(a.name == "Template" for a in node.names)
        ):  # fmt: skip
            out.append((node.lineno, "string.Template"))  # "<$tag>" templates escape no value
            continue
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.strip() in ("<", "</")
        ):
            out.append((node.lineno, node.value))  # "<" + tag + ">": a tag from pieces
            continue
        if isinstance(node, ast.JoinedStr):
            skip |= {id(v) for v in node.values}
            text = "".join(v.value if isinstance(v, ast.Constant) else "x" for v in node.values)
            # `f'{lt}b>'` / `f'{lt}{tag}>'`: a tag's text and its `>` right after a value — the `<`
            # arrived as a variable. Text right after a value that runs to a `>` with no `<` of its own
            after_value = [
                v.value
                for prev, v in zip(node.values, node.values[1:], strict=False)
                if isinstance(prev, ast.FormattedValue) and isinstance(v, ast.Constant)
            ]
            ends_tag = isinstance(node.values[-1], ast.FormattedValue) is False and any(
                re.fullmatch(r"[A-Za-z/!][^<\s]*>.*", v, re.S) or re.fullmatch(r">.*", v, re.S)
                for v in after_value
            )
            if ends_tag:
                out.append((node.lineno, text[:80]))
                continue
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        else:
            continue
        if _TAG.search(text) or _TEMPLATE_TAG.search(text):
            out.append((node.lineno, text[:80]))
    return out


def _safe_calls(src: str) -> list[int]:
    """Lines that reach `Safe` other than to annotate with it: ANY reference to the name (`Safe`,
    `ui.Safe`, an import alias) outside an annotation — a call, a subclass, a bound name, a
    `str.__new__(ui.Safe, …)` — plus `getattr(…, "Safe")` and `type(<a component call>)`, which hand
    back the class without naming it. `Safe` marks component output; wrapping caller text in it at
    the call site is the cheapest way to defeat "every value escaped" (components.py's Cobra check)."""
    tree = ast.parse(src)
    names = {"Safe"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {a.asname for a in node.names if a.name == "Safe" and a.asname}
    annotation: set[int] = set()
    for node in ast.walk(tree):
        parts: list[ast.AST | None] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(node.returns)
            a = node.args
            parts += [x.annotation for x in a.posonlyargs + a.args + a.kwonlyargs]
            parts += [x.annotation for x in (a.vararg, a.kwarg) if x is not None]
        elif isinstance(node, ast.AnnAssign):
            parts.append(node.annotation)
        for part in parts:
            if part is not None:
                annotation |= {id(n) for n in ast.walk(part)}
    out = []
    for node in ast.walk(tree):
        if id(node) in annotation:
            continue
        named = (isinstance(node, ast.Name) and node.id in names) or (
            isinstance(node, ast.Attribute) and node.attr == "Safe"
        )
        fetched = isinstance(node, ast.Call) and (
            (
                getattr(node.func, "id", "") == "getattr"
                and any(isinstance(a, ast.Constant) and a.value == "Safe" for a in node.args[1:2])
            )
            or (
                getattr(node.func, "id", "") == "type"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Call)
            )
        )
        if named or fetched:
            out.append(node.lineno)
    return sorted(set(out))


def test_nothing_outside_the_components_constructs_safe():
    """components.py promises this scan: `Safe(...)` appears only there (views/__init__.py may
    import the name for its type annotation — an import is no construction)."""
    found = {
        str(f.relative_to(_ROOT)): lines
        for f in _scanned()
        if (lines := _safe_calls(f.read_text(encoding="utf-8")))
    }
    assert found == {}


@pytest.mark.parametrize(
    "mutant",
    [
        "from .components import Safe\nx = Safe(text)\n",
        "from .. import components as ui\nx = ui.Safe(text)\n",
        "import dashboard_ui.components\nx = dashboard_ui.components.Safe(text)\n",
        "from ..components import Safe as S\nx = S(text)\n",
        "from ..components import Safe\ncls = Safe\nx = cls(text)\n",
        "from ..components import Safe\nx = str.__new__(Safe, text)\n",
        "from .. import components as ui\nx = str.__new__(ui.Safe, text)\n",
        "from .. import components as ui\nx = getattr(ui, 'Safe')(text)\n",
        "from .. import components as ui\nclass M(ui.Safe):\n    pass\nx = M(text)\n",
        "from .. import components as ui\nx = type(ui.fragment())(text)\n",
        "from ..components import Safe\nmarked = [Safe]\n",
    ],
)
def test_the_safe_scan_catches_every_way_to_construct_it(mutant):
    assert _safe_calls(mutant) != []


def test_the_safe_scan_allows_an_annotation_import():
    assert (
        _safe_calls("from ..components import Safe\n\ndef f(x: Safe) -> Safe:\n    return x\n")
        == []
    )
    assert _safe_calls("from ..components import Safe\nclass R:\n    html: Safe\n") == []


def _scanned() -> list[Path]:
    return [_SRC] + sorted(p for p in _PKG.rglob("*.py") if p != _PKG / "components.py")


def test_no_string_holding_an_html_tag_is_built_outside_the_components():
    files = _scanned()
    assert _SRC in files and _PKG / "views" / "overview.py" in files and len(files) >= 12
    found = {
        str(f.relative_to(_ROOT)): hits
        for f in files
        if (hits := _markup_literals(f.read_text(encoding="utf-8")))
    }
    assert found == {}


@pytest.mark.parametrize(
    "mutant",
    [
        "def f(v):\n    return '<span>' + v\n",
        "def f(v):\n    return f'<b>{v}</b>'\n",
        "def f(tag):\n    return f'<{tag} class=\"a\">'\n",
        "def f(v):\n    return '%s<br>' % v\n",
        "def f(tag):\n    return '<%s>' % tag\n",
        "def f(tag):\n    return '<{}>'.format(tag)\n",
        "def f():\n    return '<!doctype html>'\n",
        "X = '</div>'\n",
        "def f(tag):\n    return '<' + tag + '>'\n",
        "def f(tag):\n    return '</' + tag + '>'\n",
        "def f():\n    return chr(60) + 'b>'\n",
        "def f():\n    return b'<b>'.decode()\n",
        "import string\nT = string.Template('$x')\n",
        "from string import Template\nT = Template('$x')\n",
        "def f(lt, t):\n    return f'{lt}{t}>'\n",
        "def f(lt):\n    return f'{lt}b>x'\n",
    ],
)
def test_the_tag_scan_catches_every_way_to_build_markup(mutant):
    assert _markup_literals(mutant) != []


def test_the_tag_scan_skips_docstrings_and_regex_patterns_only():
    src = (
        'def f():\n    """Reads ``<repo>/x``."""\n'
        '    return re.compile(r"<!--.*?-->")\n'
        "def g():\n    return 'a < b' + '<i>'\n"
    )
    assert _markup_literals(src) == [(5, "<i>")]


# ---------------------------------------------------------------- the view-literal scan
# The component parameters that carry WORDS onto the page (every other parameter is an id, an enum,
# a flag, a number or a data payload, which the kit validates or serialises).
_TEXT_SLOTS = {
    "badge": ({1}, {"text"}),
    "link": ({0}, {"label"}),
    "card": ({0, 1}, {"title", "body", "age"}),
    "table": ({1, 2, 3}, {"label", "headers", "rows"}),
    "button": ({0}, {"label"}),
    "select": ({0}, {"label"}),
    "status_text": ({0}, {"text"}),
    "field": ({0}, {"label", "placeholder", "value"}),
    "group": ({0}, {"body", "label"}),
    "section": ({0, 1}, {"title", "body"}),
    "dialog": ({1, 2, 3, 4}, {"title", "body", "confirm_label", "cancel_label"}),
    "disclosure": ({0, 1}, {"summary", "body"}),
    "tabs": ({0, 1}, {"label", "items"}),
    "clamp": ({0}, {"text"}),
    "region_state": ({1}, {"message"}),
    "stale_banner": ({0, 1}, {"age_text", "cause"}),
    "fragment": (set(range(64)), set()),
}


# keyword parameters that carry no words; any OTHER keyword — a misspelt `heading=`, a new one —
# is read as text, so a literal cannot hide behind a name the scan does not know
_NON_TEXT_KWS = {"id", "kind", "data", "tag", "new_tab", "note", "open", "lines", "retry", "name",
                 "min", "max", "row_data", "href", "label_id", "active", "severity", "options",
                 "align"}  # fmt: skip


def _component_name(func: ast.expr, aliases: dict[str, str] | None = None) -> str | None:
    if isinstance(func, ast.Name):
        name = (aliases or {}).get(func.id, func.id)
        return name if name in _TEXT_SLOTS else None
    if isinstance(func, ast.Attribute) and func.attr in _TEXT_SLOTS:
        return func.attr
    return None


def _component_aliases(tree: ast.AST) -> dict[str, str]:
    """`from ..components import button as b` → {"b": "button"}."""
    return {
        a.asname: a.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for a in node.names
        if a.asname and a.name in _TEXT_SLOTS
    }


_STR_METHODS = {"format", "upper", "lower", "title", "capitalize", "strip", "casefold", "swapcase"}


def _worded(node: ast.AST, bound: dict[str, list[ast.AST]] | None = None) -> list[str]:
    """Literals with a letter in them that ``node`` puts in the slot: the node itself, or a list, a
    tuple, a concatenation, a conditional or an f-string of them; a string method on a literal
    (`"x {}".format(n)`, `"x".upper()`), `str("x")`, a `join` (its separator and its list); and a
    name the module binds to such a literal. Any other call is not descended — `t(...)` is the
    catalogue, a component call is scanned on its own, a helper's arguments are not text."""
    bound = bound or {}

    def again(n: ast.AST) -> list[str]:
        return _worded(n, bound)

    if isinstance(node, ast.Name):
        return [w for v in bound.get(node.id, []) for w in again(v)]
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in _STR_METHODS:
            return again(f.value) + [w for a in node.args for w in again(a)]
        if isinstance(f, ast.Attribute) and f.attr == "join":
            return again(f.value) + [w for a in node.args for w in again(a)]
        if isinstance(f, ast.Name) and f.id in ("str", "format"):
            return [w for a in node.args for w in again(a)]
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value] if re.search("[A-Za-z]", node.value) else []
    if isinstance(node, ast.JoinedStr):
        text = "".join(v.value if isinstance(v, ast.Constant) else "" for v in node.values)
        return [text] if re.search("[A-Za-z]", text) else []
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [w for e in node.elts for w in again(e)]
    if isinstance(node, ast.Dict):  # a cell or a row that is a mapping: its values are text
        return [w for v in node.values if v is not None for w in again(v)]
    if isinstance(node, ast.Starred):
        return again(node.value)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return again(node.elt)
    if isinstance(node, ast.BinOp):
        return again(node.left) + again(node.right)
    if isinstance(node, ast.IfExp):
        return again(node.body) + again(node.orelse)
    if isinstance(node, ast.BoolOp):
        return [w for v in node.values for w in again(v)]
    return []


def _literal_bindings(tree: ast.AST, grown: bool = False) -> dict[str, list[ast.AST]]:
    """Every literal a module name is given, any scope: `name = <literal>` — the values a name passed
    to a text slot may carry. With ``grown`` also `name += <literal>`, `name.extend(<literal>)`,
    `name.append(<literal>)` and `for name in <literal list>`: the options scan wants these, the other
    slots do not (a `rows.append([... f"{n}x"])` suffix is a unit, not a hard-coded word)."""
    literal = (ast.Constant, ast.JoinedStr, ast.List, ast.Tuple, ast.Dict)
    out: dict[str, list[ast.AST]] = {}

    def bind(name: ast.AST, value: ast.AST | None) -> None:
        if isinstance(name, ast.Name) and isinstance(value, literal):
            out.setdefault(name.id, []).append(value)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and (
            grown or not isinstance(node, ast.AugAssign)
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t_ in targets:
                bind(t_, node.value)
        elif grown and (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("extend", "append")
            and node.args
        ):
            arg = node.args[0]
            bind(node.func.value, ast.List(elts=[arg]) if node.func.attr == "append" else arg)
        elif grown and isinstance(node, ast.For) and isinstance(node.iter, (ast.List, ast.Tuple)):
            for elt in node.iter.elts:
                bind(node.target, elt)
    return out


def _view_literals(src: str) -> list[str]:
    """Every word-bearing literal a view module hands a component's text slot directly (in a list,
    a tuple, a concatenation or an f-string included) instead of through `strings.t`."""
    bad: list[str] = []
    tree = ast.parse(src)
    bound = _literal_bindings(tree)
    grown = _literal_bindings(tree, grown=True)
    aliases = _component_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _component_name(node.func, aliases)
        if name is None:
            continue
        pos, kws = _TEXT_SLOTS[name]
        if (
            name == "tabs"
            and len(node.args) > 1
            and isinstance(node.args[1], (ast.List, ast.Tuple))
        ):
            # a tab is (id, title, body): the id is a name, the title and body are text
            items = [e for e in node.args[1].elts if isinstance(e, ast.Tuple) and len(e.elts) == 3]
            bad += [w for e in items for w in _worded(e.elts[1], bound) + _worded(e.elts[2], bound)]
            pos = pos - {1}
        for i, arg in enumerate(node.args):
            if i in pos or isinstance(arg, ast.Starred):  # a splat lands in some slot: read it
                bad += _worded(arg, bound)
        for kw in node.keywords:
            if name == "select" and kw.arg == "value":
                continue  # an option KEY, not displayed text
            if name == "select" and kw.arg == "options":
                bad += _option_labels(kw.value, grown)  # the LABEL of each pair is displayed text
            elif kw.arg in kws or (kw.arg is not None and kw.arg not in _NON_TEXT_KWS):
                bad += _worded(kw.value, bound)
    return bad


def _is_pair(node: ast.AST) -> bool:
    return isinstance(node, (ast.Tuple, ast.List)) and len(node.elts) == 2


def _options_of(
    node: ast.AST, bound: dict[str, list[ast.AST]], seen: frozenset[str] = frozenset()
) -> list[ast.AST]:
    """The option pairs an ``options`` expression yields. An option is a two-element tuple or list that
    is an ITEM of the expression: an element of a list, tuple or set literal, the element of a
    comprehension, an item reached through ``*``, or an item of a collection a bound name, ``+``,
    ``list``, ``tuple`` or ``sorted`` builds. The expression itself is a collection, never an option."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [o for e in node.elts for o in ([e] if _is_pair(e) else _options_of(e, bound, seen))]
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return [node.elt] if _is_pair(node.elt) else []
    if isinstance(node, ast.Starred):
        return _options_of(node.value, bound, seen)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _options_of(node.left, bound, seen) + _options_of(node.right, bound, seen)
    if isinstance(node, ast.IfExp):
        return _options_of(node.body, bound, seen) + _options_of(node.orelse, bound, seen)
    if isinstance(node, ast.Name) and node.id not in seen:
        # a name bound to ONE pair (a loop variable) is an option; one bound to a collection is not
        return [
            o
            for v in bound.get(node.id, [])
            for o in (
                [v]
                if _is_pair(v) and not any(_is_pair(x) for x in v.elts)
                else _options_of(v, bound, seen | {node.id})
            )
        ]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("list", "tuple", "sorted")
    ):
        return [o for a in node.args for o in _options_of(a, bound, seen)]
    return []


def _option_labels(node: ast.AST, bound: dict[str, list[ast.AST]]) -> list[str]:
    """The word-bearing literals in the LABEL (element 1) of each option in an ``options`` expression;
    an option's key (element 0) and everything that is not a label are never read."""
    return [w for opt in _options_of(node, bound) for w in _worded(opt.elts[1], bound)]


def test_no_view_module_hands_a_component_a_literal_word():
    views = sorted((_PKG / "views").glob("*.py"))
    assert len(views) == 7  # the six views and the registry
    found = {p.name: b for p in views if (b := _view_literals(p.read_text(encoding="utf-8")))}
    assert found == {}


@pytest.mark.parametrize(
    "mutant",
    [
        "ui.button('Accept')\n",
        "badge('ok', f'{n} more')\n",
        "ui.table('x', t('a'), ['Item', t('b')], [])\n",
        "ui.card(title='Quota', body=b)\n",
        "ui.fragment(t('a'), ' and more')\n",
        "region_state('error', 'failed: ' + e)\n",
        "ui.button('Accept {}'.format(n))\n",
        "ui.badge('ok', 'accept'.upper())\n",
        "ui.button(str('Accept'))\n",
        "ui.fragment(' '.join(['Accept', x]))\n",
        "label = 'Accept'\nui.button(label)\n",
        "def f():\n    word: str = 'Reject'\n    return ui.button(word)\n",
        "ui.table('x', t('a'), [t('h')], [[{'label': 'Accept'}]])\n",
        "ui.card(heading='Quota', body=b)\n",
        "ui.button(*['Accept'])\n",
        "from ..components import button as b\nb('Accept')\n",
        "ui.table('x', t('a'), [t('h')], [['Accept' for _ in xs]])\n",
        "rows = [['Accept', 1], ['Reject', 2]]\nui.table('x', t('a'), [t('h')], rows)\n",
        "ui.select('Cost', name='c', id='i', options=[])\n",
        "ui.select(label='Cost', name='c', id='i', options=[])\n",
        "ui.status_text('3 shown')\n",
        "ui.status_text(text='3 shown')\n",
    ],
)
def test_the_view_literal_scan_catches_a_hard_coded_word(mutant):
    assert _view_literals(mutant) != []


def test_the_view_literal_scan_passes_catalogue_words_and_punctuation():
    assert (
        _view_literals(
            "ui.fragment(t('a', n=1), ' · ', t('b'))\nui.button(t('x'), kind='primary')\n"
        )
        == []
    )


def test_the_new_parameters_are_scanned_or_named_non_text():
    """`select`'s label and `status_text`'s text are text slots; `options` and `align` carry values
    and an enum, so they are named non-text keywords (a literal in an option label is the caller's
    catalogue lookup to make — the scan does not read it)."""
    assert _TEXT_SLOTS["select"] == ({0}, {"label"})
    assert _TEXT_SLOTS["status_text"] == ({0}, {"text"})
    assert {"options", "align"} <= _NON_TEXT_KWS
    assert (
        _view_literals(
            "ui.select(t('a'), name='c', id='i', options=[('x', t('b'))], value='')\n"
            "ui.table('x', t('a'), [t('h')], [], align=['right'])\n"
            "ui.status_text(t('s'), data={'filter-status': ''})\n"
        )
        == []
    )


# ---------------------------------------------------------------- the integrated board, from fixtures
def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    monkeypatch.setenv("QUOTA_DASH_CREDITS_KEY_FILE", str(tmp_path / "no-key.env"))
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "0")
    monkeypatch.setenv("QUOTA_DASH_RENDERED_COMMANDS", str(tmp_path / "rendered"))
    isolate(tmp_path, monkeypatch)  # tests/quota_dashboard_isolation.py
    spec = importlib.util.spec_from_file_location(f"qd_layer_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    after_load(mod, monkeypatch)
    return mod


def _iso(ts: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def work_fixture(now: float | None = None) -> list[dict]:
    """Two repos as `_collect_work` returns them: the hub with a decision, a claimed tagged task and a
    blocked one plus a skipped file; a second repo whose store could not be read."""
    now = time.time() if now is None else now  # read at call time: a run can take minutes
    items = [
        {"id": "W-0000000a", "kind": "decision", "status": "awaiting-operator", "title": "ship the board",
         "question": "Ship the redesigned board?", "ground": "gate", "creator": "infra",
         "created": _iso(now - 7200), "owner": "", "next": "", "_prio": 1, "_claim": ""},
        {"id": "W-0000000b", "kind": "task", "status": "open", "title": "tidy the doc", "owner": "infra",
         "next": "rewrite the routes section", "tags": ["docs", "ui"], "_prio": 2, "_claim": "infra",
         "comments": [{"by": "operator", "action": "comment", "text": "keep it short", "at": now - 60}]},
        {"id": "W-0000000c", "kind": "task", "status": "blocked", "title": "wait on the vendor",
         "owner": "kaizen", "next": "", "_prio": 3, "_claim": ""},
    ]  # fmt: skip
    return [
        {"name": "fabrik", "items": items, "error": None, "skipped": ["W-bad.json: not JSON"],
         "main": "/x/fabrik", "root": "/x/fabrik"},
        {"name": "shop", "items": [], "error": "OSError: store unreadable", "skipped": []},
    ]  # fmt: skip


def box_fixture(now: float | None = None) -> dict:
    """Every agent state and every agents-block field today's `_agent_row` showed."""
    now = time.time() if now is None else now  # read at call time: a run can take minutes

    def agent(name, state, **extra):
        a = {"name": name, "window": state != "away", "windows": 1, "named_from": "", "state": state,
             "now": None, "claim": None, "next": {"queued": 0, "top": []}, "merges": [],
             "merge_owner": False, "paused": None, "can_pause": True, "pause_honoured": True}  # fmt: skip
        a.update(extra)
        return a

    return {
        "repos": [
            {
                "name": "fabrik",
                "dormant": 2,
                "agents": [
                    agent(
                        "infra",
                        "working",
                        named_from="record",
                        windows=2,
                        now={
                            "command": "fabrik-task",
                            "phase": 3,
                            "phases": 5,
                            "title": "the board",
                            "surface": "the doc",
                            "updated_ts": now - 30,
                        },
                        claim={"id": "W-0000000b", "title": "tidy the doc"},
                        next={"queued": 3, "top": [{"id": "W-0000000d", "title": "next up"}]},
                        merges=[{"sha": "abc1234", "ts": now - 600, "item": "W-0000000e"}],
                    ),
                    agent(
                        "kaizen",
                        "idle",
                        paused={
                            "by": "operator",
                            "at": now
                            - 330,  # mid-minute: the render reads its own clock a moment later
                            "why": "hold for review",
                            "partial": True,
                            "name": "kaizen",
                            "names": ["kaizen", "tree2"],
                        },
                        pause_honoured=False,
                    ),
                    agent("coordinator", "stale", merge_owner=True),
                    agent("intel", "away", can_pause=False),
                ],  # fmt: skip
            },
            {"name": "shop", "agents": [], "error": "OSError: agents unreadable"},
            {"name": "quiet", "agents": []},
        ]
    }


def _acct(slug: str, email: str, *, five: float, seven: float, now: float, **extra) -> dict:
    a = {
        "slugs": [slug],
        "email": email,
        "five_hour": {"utilization": five, "resets_at_epoch": now + 3600},
        "seven_day": {"utilization": seven, "resets_at_epoch": now + 3 * 86400},
        "model_windows": {"Fable": {"utilization": 10.0, "resets_at_epoch": now + 3 * 86400}},
        "source": "live",
        "age_s": None,
        "weekly_cap": None,
        "cap_walled": False,
    }
    a.update(extra)
    return a


def payload_fixture(now: float | None = None, **over) -> dict:
    """An active account at its session wall (so it is first AND its own return slot), a standby, a
    parked one, a capped one, one scaffolded-but-unlogged dir, a fleet warning."""
    now = time.time() if now is None else now  # read at call time: a run can take minutes
    p = {
        "active": "alpha",
        "pause": None,
        "fleet_warnings": ["delta is weekly-walled"],
        "pending": ["echo"],
        "accounts": [
            _acct("alpha", "alpha@example.com", five=100.0, seven=40.0, now=now),
            _acct("bravo", "bravo@example.com", five=10.0, seven=20.0, now=now, weekly_cap=80),
            _acct("charlie", "charlie@example.com", five=5.0, seven=5.0, now=now, parked=True),
            _acct("delta", "delta@example.com", five=5.0, seven=100.0, now=now, cap_walled=True),
        ],
    }
    p.update(over)
    return p


def budget_fixture(now: float | None = None) -> dict:
    now = time.time() if now is None else now  # read at call time: a run can take minutes
    return {
        "seats": [
            {
                "label": "read-only",
                "key": "read_only",
                "allowed": 6,
                "box": 6,
                "taken": 0,
                "floored": False,
                "quota_cap": None,
                "has_quota_cap": False,
            },
            {
                "label": "heavy",
                "key": "heavy",
                "allowed": 3,
                "box": 3,
                "taken": 1,
                "floored": False,
                "quota_cap": None,
                "has_quota_cap": False,
            },
        ],  # fmt: skip
        "cli_cap": 8,
        "hold": False,
        "quota": {
            "ok": True,
            "active": "alpha",
            "hottest_pct": 41,
            "eligible": 2,
            "eligible_raw": 3,
        },
        "caveats": ["sibling seats unknown, not subtracted"],
        "read_at": now,
    }


def _misc():
    from tests import test_quota_dashboard_views_misc as misc

    return misc


def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, payload: dict | None = None,
          probe_failed: bool = True, commands: list | None = None):  # fmt: skip
    """The module with every collector stubbed from the fixtures above; returns it."""
    qd = _load(tmp_path, monkeypatch)
    misc = _misc()
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)  # never a probe, never a regeneration
    monkeypatch.setattr(qd, "_probe", lambda: (_ for _ in ()).throw(AssertionError("probe")))
    monkeypatch.setattr(qd, "_work_data", work_fixture)
    monkeypatch.setattr(qd, "_box_data", box_fixture)
    monkeypatch.setattr(qd, "_budget_data", budget_fixture)
    monkeypatch.setattr(qd, "_spend_data", lambda: misc.SPEND)
    rows = misc._commands_data()["commands"] if commands is None else commands
    monkeypatch.setattr(qd, "_load_commands", lambda: rows)
    data = misc._services_data()
    monkeypatch.setattr(qd, "_pool_credits", lambda *a, **k: data["pool"])
    monkeypatch.setattr(qd, "_api_quotas", lambda *a, **k: data["apis"])
    qd._set_last_status(time.time(), payload if payload is not None else payload_fixture())
    if probe_failed:
        qd._LAST_PROBE_FAILURE[0] = (time.time() - 5, "RuntimeError")
    return qd


def render_all(qd) -> dict[str, str]:
    return {name: qd._render_view(name) for name in VIEWS}


def _fields(template: str) -> list[str]:
    return [f for _lit, f, _spec, _conv in string.Formatter().parse(template) if f]


def stand_in() -> dict[str, str]:
    """Every key renders as ``⟦key⟧`` followed by its filled fields, so a rendered key and the data
    beside it are both visible; the page language stays a valid one."""
    out = {}
    for k, v in cat.CATALOGUE.items():
        out[k] = v if k == "app.lang" else f"⟦{k}⟧" + "".join(f" {{{f}}}" for f in _fields(v))
    return out


def _visible(html: str) -> str:
    return re.sub(r"⟦[a-z0-9_.-]+⟧", "", html)


# ---------------------------------------------------------------- the catalogue scan
def test_every_view_renders_no_catalogue_owned_english_under_a_stand_in(tmp_path, monkeypatch):
    qd = board(tmp_path, monkeypatch)
    english = render_all(qd)
    for name, html in english.items():
        assert "data-view-root" in html and 'data-state="error"' not in html.split(">", 1)[0], name
    with cat.use(stand_in()):
        swapped = render_all(qd)
    # a phrase is catalogue-owned beyond doubt; a single word ("operator", "comment") is also data
    owned = [
        v for k, v in cat.CATALOGUE.items() if k != "app.lang" and " " in v.strip() and len(v) >= 6
    ]
    used = {name: [v for v in owned if v in english[name]] for name in VIEWS}
    for name in VIEWS:
        assert len(used[name]) >= 5, (name, used[name])  # the positive control: English was there
        assert "⟦" in swapped[name], name
        leaked = [v for v in used[name] if v in _visible(swapped[name])]
        assert leaked == [], (name, leaked)


# ---------------------------------------------------------------- INV-2: the inventory of today's five tabs
def K(key: str) -> str:  # noqa: N802 — reads as the catalogue mark it builds
    assert key in cat.CATALOGUE, key
    return f"⟦{key}⟧"


# (tab, what today's tab showed, the view it now lives in, every substring that proves it renders)
INVENTORY: list[tuple[str, str, str, tuple[str, ...]]] = [
    # Repos — `_repos_body`, `_repo_pane`, `_verdict_cell`, `_item_line`
    ("repos", "the repo picker", "work", (K("work.repo_picker"), 'data-picker="repo"', 'data-pick-to="fabrik"')),
    ("repos", "the owner chips with counts", "work",
     (K("work.chips_label"), K("work.chip_all") + " 3", ">infra 1<", ">kaizen 1<", ">operator 1<")),
    ("repos", "the tag filter", "work", (K("work.tag_label"), 'data-filter="tag"')),
    ("repos", "the skipped-store list", "work", (K("work.skipped") + " 1", "W-bad.json: not JSON")),
    ("repos", "the repo error banner", "work", (K("work.repo_failed") + " shop OSError: store unreadable",)),
    ("repos", "the item-row fields", "work",
     tuple(K(f"work.col.{c}") for c in ("item", "kind", "status", "prio", "title", "next", "tags", "claim", "operator"))
     + ("W-0000000b", "tidy the doc", "rewrite the routes section", "docs, ui", K("work.claimed_by") + " infra",
        K("work.prio") + " 2", K("work.last") + " operator comment keep it short")),
    ("repos", "Accept / Reject / Comment", "work",
     (K("work.accept"), K("work.reject"), K("work.comment"), 'data-post="/item-verdict"')),
    # the agents block — `_agents_block`, `_agent_row`, `_pause_cell`
    ("repos", "the summary counts line and the quiet repos", "overview", (K("ov.ag.counts") + " 1 1 1 1 1",)),
    ("repos", "an agents repo's error banner", "overview",
     (K("ov.ag.repo_error") + " shop OSError: agents unreadable",)),
    ("repos", "each agent's state", "overview",
     tuple(K(f"ov.ag.state.{s}") for s in ("working", "idle", "stale", "away"))),
    ("repos", "NOW", "overview",
     (K("ov.ag.h.now"), K("ov.ag.now") + " fabrik-task", K("ov.ag.phase") + " 3 5", "the board")),
    ("repos", "Holds", "overview", (K("ov.ag.h.holds"), K("ov.ag.item") + " W-0000000b tidy the doc")),
    ("repos", "NEXT with its queued count", "overview",
     (K("ov.ag.h.next"), K("ov.ag.item") + " W-0000000d next up", K("ov.ag.more_queued") + " 2")),
    ("repos", "the last merge", "overview", (K("ov.ag.h.merge"), K("ov.ag.merge") + " abc1234", "W-0000000e")),
    ("repos", "the merge owner", "overview", (K("ov.ag.merge_owner"),)),
    ("repos", "named from the record", "overview", (K("ov.ag.named"),)),
    ("repos", "the window count", "overview", (K("ov.ag.windows") + " 2",)),
    ("repos", "paused by, at and why", "overview",
     (K("ov.ag.paused") + " operator " + K("ov.dur.min") + " 5", K("ov.ag.paused_why") + " hold for review")),
    ("repos", "a partial pause", "overview", (K("ov.ag.paused_partial"),)),
    ("repos", "a pause not honoured", "overview", (K("ov.ag.not_honoured"),)),
    ("repos", "the dormant count", "overview", (K("ov.ag.dormant") + " fabrik 2",)),
    ("repos", "Pause and Resume", "overview",
     (K("ov.ag.pause"), K("ov.ag.resume"), 'data-post="/agent-pause"', K("ov.ag.resume_body") + " kaizen, tree2")),
    # Quota — `render`, `_row`, `_switch_cell`, `_return_row`, `_pending_row`, `_governor_panel`
    ("quota", "the probe-failed banner", "accounts", (K("accounts.banner.probe") + " RuntimeError",)),
    ("quota", "the account-row fields", "accounts",
     tuple(K(f"accounts.col.{c}") for c in ("account", "session", "weekly", "fable", "controls"))
     + ("alpha@example.com", K("accounts.rank.active_also"), K("accounts.rank.next") + " 2",
        K("accounts.badge.parked"), K("accounts.badge.cap") + " 80", K("accounts.badge.reserved"))),
    ("quota", "the four account controls", "accounts",
     (K("accounts.btn.switch"), K("accounts.btn.disable"), K("accounts.btn.enable"), K("accounts.btn.cap"),
      K("accounts.btn.thr"), 'data-post="/switch"', 'data-post="/park"', 'data-post="/cap"',
      'data-post="/threshold"')),
    ("quota", "the returning row", "accounts", (K("accounts.return.name"),)),
    ("quota", "the pending row", "accounts", (K("accounts.pending.badge"), "echo")),
    ("quota", "the governor verdict", "accounts", (K("accounts.gov.title") + " alpha", K("accounts.gov.detail"))),
    ("quota", "the Warnings list", "accounts", (K("accounts.warnings"), "delta is weekly-walled")),
    ("quota", "the rotation note with its threshold and probe interval", "accounts",
     (K("accounts.rule") + " 99 20",)),
    # Usage — `_spend_panel`
    ("usage", "the spend data with built_at and the window", "usage",
     (K("usage.intro"), "2026-09-30", "2026-10-02", K("usage.table"), "opus")),
    # Commands — `_commands_table`, `_ext_matrix_intro`, `_ext_matrix_table`, `_budget_banner`
    ("commands", "the nine catalogue columns", "commands",
     tuple(K(f"commands.col.{c}") for c in ("n", "command", "stage", "purpose", "when", "skip", "next",
                                            "natives", "tiers"))),
    ("commands", "the intro with its source count", "commands", (K("commands.intro") + " 3",)),
    ("commands", "the matrix with its intro, caveat and totals", "commands",
     (K("commands.matrix.intro"), K("commands.matrix.caveat"), K("commands.matrix.total"))),
    ("commands", "the box-budget line", "overview", (K("ov.h.budget"), K("ov.h.budget_caveats"))),
    # External — `_pool_credits_panel`, `_api_quotas_panel`, `_ext_services_intro`
    ("external", "the pool credits", "services", (K("services.pool.line"), "225")),
    ("external", "the search-API quotas", "services", (K("services.apis.table"), "Brave Search")),
    ("external", "the external-services inventory in place of the old page link", "services",
     (K("services.inv.title"), K("services.inv.sum.label"), K("services.inv.filter.find"),
      K("services.inv.attn.title"))),
]  # fmt: skip

# the entries a second fixture shows: a banner only one state of the payload can carry
VARIANTS: list[tuple[str, str, dict, tuple[str, ...]]] = [
    ("quota", "the rotation-paused banner", {"pause": "marker"}, (K("accounts.banner.paused"),)),
    (
        "quota",
        "the pause-unreadable banner",
        {"pause": "error"},
        (K("accounts.banner.pause_error"),),
    ),
    (
        "quota",
        "the no-accounts banner",
        {"accounts": [], "pending": []},
        (K("accounts.banner.none"),),
    ),
]


def test_every_datum_and_control_of_todays_five_tabs_renders_in_some_view(tmp_path, monkeypatch):
    qd = board(tmp_path, monkeypatch)
    with cat.use(stand_in()):
        out = render_all(qd)
    missing = [
        (tab, what, view, [s for s in needles if s not in out[view]])
        for tab, what, view, needles in INVENTORY
        if any(s not in out[view] for s in needles)
    ]
    assert missing == []
    assert {tab for tab, *_ in INVENTORY + VARIANTS} == {
        "repos",
        "quota",
        "usage",
        "commands",
        "external",
    }


@pytest.mark.parametrize("tab,what,over,needles", VARIANTS, ids=[v[1] for v in VARIANTS])
def test_each_banner_of_todays_quota_tab_renders_in_the_accounts_view(
    tmp_path, monkeypatch, tab, what, over, needles
):
    qd = board(tmp_path, monkeypatch, payload=payload_fixture(**over), probe_failed=False)
    with cat.use(stand_in()):
        html = qd._render_view("accounts")
    assert all(s in html for s in needles), (what, html[:400])


def test_the_corpus_unreadable_banner_renders_in_the_commands_view(tmp_path, monkeypatch):
    qd = board(tmp_path, monkeypatch, commands=[])
    with cat.use(stand_in()):
        html = qd._render_view("commands")
    assert K("commands.unreadable") in html


def test_the_shared_formatters_take_every_word_from_the_catalogue():
    """`fmt`'s outputs reach every view ("cached 2h ago", "(due)", "no burn yet"): under the stand-in
    each is its catalogue key and the numbers beside it, never English."""
    from dashboard_ui import fmt

    posture = {"active": {"windows": {"five_hour": {"utilization": 50, "burn_per_min": 0.5,
               "verdict": "wall_first", "minutes_to_wall": 12}}}}  # fmt: skip
    with cat.use(stand_in()):
        outs = {
            "ago": fmt.ago(time.time() - 7200),
            "age": fmt.fmt_age(7200),
            "due": fmt.fmt_reset(time.time() - 60),
            "in": fmt.fmt_reset(time.time() + 7200),
            "none": fmt.fmt_reset(None),
            "burn": fmt.posture_sub(posture, "five_hour"),
            "noburn": fmt.posture_sub(
                {"active": {"windows": {"five_hour": {"utilization": 1}}}}, "five_hour"
            ),
        }
    assert outs["ago"] == K("fmt.ago_h") + " 2" and outs["age"] == K("fmt.cached_h") + " 2"
    assert outs["due"].startswith(K("fmt.reset_due")) and outs["none"] == K("fmt.reset_none")
    assert outs["in"].startswith(K("fmt.reset_in")) and K("fmt.left_h") + " 2" in outs["in"]
    assert outs["burn"] == K("fmt.burn_wall") + " 0.50 12" and outs["noburn"] == K("fmt.no_burn")
    for words in ("ago", "cached", "due", "burn", "wall", " in "):
        assert all(words not in _visible(v) for v in outs.values()), words


# ---------------------------------------------------------------- review pass 1: select options and value
@pytest.mark.parametrize(
    "mutant",
    [
        "ui.select(t('a'), name='c', id='i', options=[('paid', 'Paid')])\n",
        "ui.select(t('a'), name='c', id='i', options=[['paid', 'Paid']])\n",
        "ui.select(t('a'), name='c', id='i', options=[(v, 'Paid') for v in vs])\n",
        "ui.select(t('a'), name='c', id='i', options=[('', t('x')), ('paid', 'Paid')])\n",
        "ui.select(t('a'), name='c', id='i', options=[('', t('x'))] + [('p', 'Paid')])\n",
        "OPTS = [('p', 'Paid')]\nui.select(t('a'), name='c', id='i', options=OPTS)\n",
        "ui.select(t('a'), name='c', id='i', options=[*[(v, 'Paid') for v in vs]])\n",
        "ui.select(t('a'), name='c', id='i', options=list((('p', 'Paid'),)))\n",
        "ui.select(t('a'), name='c', id='i', options=sorted(OPTS) + [('p', f'Paid {n}')])\n",
    ],
)
def test_the_view_literal_scan_reads_a_select_option_label(mutant):
    assert _view_literals(mutant) != []


def test_the_view_literal_scan_reads_the_label_and_not_the_value_of_a_select_option():
    assert (
        _view_literals(
            "ui.select(t('a'), name='c', id='i', options=[('paid', t('x')), ('free', t('y'))],"
            " value='paid')\n"
            "ui.select(t('a'), name='c', id='i', options=[(v, t('x')) for v in vs])\n"
        )
        == []
    )


def _labels(src: str) -> list[str]:
    tree = ast.parse(src)
    (call,) = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "select"
    ]
    (opts,) = [k.value for k in call.keywords if k.arg == "options"]
    return _option_labels(opts, _literal_bindings(tree, grown=True))


@pytest.mark.parametrize(
    "options,expected",
    [
        ('[("", "All"), ("paid", "Paid")]', ["All", "Paid"]),
        ('(("a", "Paid"), ("b", "Free"))', ["Paid", "Free"]),
        ('[("a", "Paid")]', ["Paid"]),
        ('[("a", "One"), ("b", "Two"), ("c", "Three")]', ["One", "Two", "Three"]),
        ('[("", t("x"))] + [("p", "Paid")]', ["Paid"]),
        ("OPTS", ["Paid"]),
        ('[*[(v, "Paid") for v in vs]]', ["Paid"]),
        ('list((("p", "Paid"),))', ["Paid"]),
        ('sorted(OPTS) + [("q", "Free")]', ["Paid", "Free"]),
        ('[("p", f"{n:d} x")]', [" x"]),
        ('[(v, t("x")) for v in vs if v != "none"]', []),
        ('[(v, t("x")) for v in ("a", "b")]', []),
        ('[("p", t("paid"))]', []),
        ('[("paid", t("x"))]', []),
        ('[("p", "Paid" if x else t("y"))]', ["Paid"]),
    ],
)
def test_the_option_label_scan_reports_exactly_the_words_in_option_labels(options, expected):
    src = f"OPTS = [('p', 'Paid')]\nui.select(t('a'), name='c', id='i', options={options})\n"
    assert _labels(src) == expected


@pytest.mark.parametrize(
    "prelude,options",
    [
        ("OPTS = []\nOPTS += [('p', 'Paid')]\n", "OPTS"),
        ("OPTS = []\nOPTS.extend([('p', 'Paid')])\n", "OPTS"),
        ("OPTS = []\nOPTS.append(('p', 'Paid'))\n", "OPTS"),
        ("for o in [('p', 'Paid')]:\n    pass\n", "[o]"),
    ],
)
def test_the_option_label_scan_follows_a_name_grown_after_its_first_binding(prelude, options):
    src = f"{prelude}ui.select(t('a'), name='c', id='i', options={options})\n"
    assert _labels(src) == ["Paid"]
