"""The dashboard's components — the ONLY place the page layer writes HTML (spec § Components, INV-4).

Every function returns `Safe`, a `str` subclass that marks markup a component built. Every argument
that is not `Safe` is escaped with `html.escape(str(x), quote=True)` before it reaches the markup, and
`fragment` is the one sanctioned way to join parts: a plain `"".join` or `+` yields a plain `str`,
which the next component escapes again — double-escaped text is visible and loud, never an injection.
Every `data=` / `row_data` mapping becomes `data-<key>` attributes; a key outside `[a-z0-9-]+`, or one
a component writes itself (`RESERVED_DATA_KEYS`), raises `ValueError`, because an attribute NAME cannot
be escaped into safety. Every element id must match `[A-Za-z][A-Za-z0-9_:-]*`. ``None`` renders as nothing. Every word a component writes
itself comes from `strings.t`; colour lives only in `static/app.css` (INV-3) — components name
severities and states as attributes, never as colours.

Cobra check (D-253): the cheapest way to pass "every value escaped" without the outcome is wrapping
caller text in `Safe(...)` at the call site. `Safe` is for component output; T07's page-layer scan
flags any `Safe(` outside this module.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import hashlib
import html
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime

from .strings import active as _catalogue
from .strings import t

SEVERITIES = ("critical", "warning", "ok", "info", "neutral")
# the shape that carries each severity besides its colour (design-system-template.md:1290)
SEVERITY_ICONS = {"critical": "✖", "warning": "▲", "ok": "✔", "info": "ℹ", "neutral": "●"}

BUTTON_KINDS = ("primary", "secondary", "danger")
FIELD_KINDS = ("text", "textarea", "number", "search")
GROUP_TAGS = ("div", "section", "ul", "ol", "li", "nav", "fieldset", "span", "tbody")
NOTES = (None, "optional", "required")
ALIGNS = (None, "right")
# data keys `app.js` reads: a filter control (a select must offer "") and a filter section (needs an id)
_FILTER_CONTROL, _FILTER_SECTION = ("filter", "filter-section")
STATES = ("loading", "empty", "error")
CLAMP_LINES = range(1, 7)

_DATA_KEY = re.compile(r"[a-z0-9-]+")
_ID = re.compile(r"[A-Za-z][\w:-]*", re.ASCII)
# a link target: a fragment, a same-site path (never `//` or `/\`, which leave the origin) or an http(s) URL
_HREF = re.compile(r"(#|/(?![/\\])|https?://)[^\s\x00-\x1f\x7f]*")
# data-* names a component writes itself; a caller's data= may not shadow them
RESERVED_DATA_KEYS = frozenset(
    {
        "kind", "severity", "state", "expanded", "lines", "clamp", "clamp-toggle", "retry", "value-of",
        "dialog-note", "dialog-error", "dialog-confirm", "dialog-cancel", "tabs", "theme-toggle", "menu",
        "nav", "live", "still", "inline-error", "open",
        # written by app.js (data-stale on a stamp, data-view on <main>) or by `freshness` itself
        "stale", "ts", "cadence", "view", "wrap",
        # written by `table(align=)` on a right-aligned header and cell
        "align",
    }
)  # fmt: skip


class Safe(str):
    """Markup a component built. Only this module constructs it."""

    __slots__ = ()


def _esc(x: object) -> str:
    if type(x) is Safe:  # exactly Safe: a subclass is not this module's output
        return x
    return "" if x is None else html.escape(str(x), quote=True)


def _id(value: object, what: str = "id") -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{what} {value!r} is outside [A-Za-z][A-Za-z0-9_:-]*")
    return value


def slug(text: object, prefix: str = "x") -> str:
    """A valid, stable element id for ANY string — a repo name, an email, an index.

    ``prefix-<readable part>-<8 hex of sha256(text)>``: the readable part keeps ASCII letters,
    digits, ``_`` and ``-`` (other characters become ``-``, cut to 40), and the hash keeps two
    different strings apart even when their readable parts agree (``my.repo`` vs ``my-repo``).
    The same text always gives the same id, so `app.js` can carry state across a refresh by it."""
    _id(prefix, "slug prefix")
    raw = "" if text is None else str(text)
    readable = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-")[:40]
    # surrogatepass: a non-UTF-8 name from os.listdir arrives surrogate-escaped and must still hash
    digest = hashlib.sha256(raw.encode("utf-8", "surrogatepass")).hexdigest()[:8]
    return f"{prefix}-{readable}-{digest}" if readable else f"{prefix}-{digest}"


def _flag(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{what} must be True or False, not {value!r}")
    return value


def _attr(name: str, value: object) -> str:
    return f' {name}="{html.escape(str(value), quote=True)}"'


def _data(data: Mapping[str, object] | None) -> str:
    if not data:
        return ""
    out = []
    for key, value in data.items():
        if not isinstance(key, str) or not _DATA_KEY.fullmatch(key):
            raise ValueError(f"data attribute name {key!r} is outside [a-z0-9-]+")
        if key in RESERVED_DATA_KEYS:
            raise ValueError(f"data attribute name {key!r} is written by the component itself")
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple, bool)):
            value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        out.append(_attr(f"data-{key}", value))
    return "".join(out)


def _choice(value: object, allowed: Iterable[object], what: str) -> None:
    if value not in tuple(allowed):
        raise ValueError(f"{what} {value!r} is not one of {tuple(allowed)!r}")


def fragment(*parts: object) -> Safe:
    """Join ``parts`` into markup, escaping every part that is not `Safe`; ``None`` is skipped."""
    return Safe("".join(_esc(p) for p in parts if p is not None))


BADGE_WRAP_AT = 40  # characters: a badge text this long may wrap; a shorter one stays on one line


def badge(severity: str, text: object) -> Safe:
    """A status badge: icon, the severity in words (for assistive tech) and the text — never colour
    alone. A text of `BADGE_WRAP_AT` characters or more (data: a collector's error, a path) is marked
    ``data-wrap`` so the stylesheet lets it wrap; a shorter one never wraps, so a table or a flex row
    cannot squeeze it to a letter a line."""
    _choice(severity, SEVERITIES, "severity")
    body = _esc(text)
    visible = html.unescape(re.sub(r"<[^>]*>", "", body))
    wrap = " data-wrap" if len(visible.strip()) >= BADGE_WRAP_AT else ""
    return Safe(
        f'<span class="badge"{wrap}{_attr("data-severity", severity)}>'
        f'<span class="badge-icon" aria-hidden="true">{SEVERITY_ICONS[severity]}</span>'
        f'<span class="sr-only">{_esc(t("sev." + severity))}: </span>'
        f'<span class="badge-text">{body}</span></span>'
    )


def link(label: object, href: object, *, new_tab: bool = False) -> Safe:
    """A link: ``href`` is a same-document fragment (``#…``), a same-site path (``/…``, never ``//`` or
    ``/\\``, which leave the origin) or an absolute ``http(s)://`` URL; anything else — ``javascript:``,
    ``data:``, a control character — raises. ``new_tab`` opens it in its own tab (``target="_blank"
    rel="noopener"``) and says so in words."""
    _flag(new_tab, "link new_tab")
    if not isinstance(href, str) or not _HREF.fullmatch(href):
        raise ValueError(
            f"link href {href!r} is not a fragment, a same-site path or an http(s) URL"
        )
    extra = (
        f' target="_blank" rel="noopener"><span class="sr-only">{_esc(t("link.new_tab"))} </span>'
        if new_tab
        else ">"
    )
    return Safe(f'<a class="link"{_attr("href", href)}{extra}{_esc(label)}</a>')


def card(
    title: object,
    body: object,
    *,
    badge: object = None,
    age: object = None,
    actions: object = Safe(""),
    id: object = None,
) -> Safe:
    """A card: title row (badge, heading, age), body, action row."""
    head = fragment(badge, Safe('<h3 class="card-title">'), title, Safe("</h3>"))
    if age is not None:
        head = fragment(head, Safe('<span class="card-age">'), age, Safe("</span>"))
    acts = _esc(actions)
    return Safe(
        f'<article class="card"{_attr("id", _id(id)) if id is not None else ""}>'
        f'<header class="card-head">{head}</header>'
        f'<div class="card-body">{_esc(body)}</div>'
        + (f'<div class="card-actions">{acts}</div>' if acts else "")
        + "</article>"
    )


def _mark(marks: Sequence[str], j: int) -> str:
    return marks[j] if j < len(marks) else ""


def table(
    label_id: object,
    label: object,
    headers: Sequence[object],
    rows: Sequence[Sequence[object]],
    *,
    row_data: Sequence[Mapping[str, object] | None] | None = None,
    align: Sequence[str | None] | None = None,
) -> Safe:
    """A real table inside a labelled, focusable scroll region; the first cell of a row is its header.
    ``align`` is one entry per column, ``"right"`` or ``None``: a right column's header and cells carry
    ``data-align="right"`` (a number column, set in tabular figures by the stylesheet)."""
    label_id = _id(label_id, "table label id")
    heads = list(headers)
    if align is None:
        marks = [""] * len(heads)
    else:
        if isinstance(align, str) or len(align) != len(heads):
            raise ValueError(f"table align {align!r} needs one entry per column ({len(heads)})")
        for a in align:
            _choice(a, ALIGNS, "table align")
        marks = [' data-align="right"' if a == "right" else "" for a in align]
    head = "".join(f'<th scope="col"{marks[i]}>{_esc(h)}</th>' for i, h in enumerate(heads))
    body = []
    for i, row in enumerate(rows):
        attrs = _data(row_data[i] if row_data is not None and i < len(row_data) else None)
        cells = [
            f'<th scope="row"{_mark(marks, j)}>{_esc(c)}</th>'
            if j == 0
            else f"<td{_mark(marks, j)}>{_esc(c)}</td>"
            for j, c in enumerate(row)
        ]
        body.append(f"<tr{attrs}>{''.join(cells)}</tr>")
    return Safe(
        f'<div class="table-wrap" role="region"{_attr("aria-labelledby", label_id)} tabindex="0">'
        f"<table><caption{_attr('id', label_id)}>{_esc(label)}</caption>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def button(
    label: object, *, kind: str = "secondary", data: Mapping[str, object] | None = None
) -> Safe:
    """A button whose visible label names the action; ``data`` declares what `app.js` does with it."""
    _choice(kind, BUTTON_KINDS, "button kind")
    return Safe(
        f'<button type="button" class="btn"{_attr("data-kind", kind)}{_data(data)}>{_esc(label)}</button>'
    )


def field(
    label: object,
    *,
    name: object,
    kind: str = "text",
    id: object,
    value: object = "",
    min: object = None,  # noqa: A002 — the HTML attribute's own name
    max: object = None,  # noqa: A002
    placeholder: object = "",
    data: Mapping[str, object] | None = None,
) -> Safe:
    """A form field with a visible `<label for>`."""
    _choice(kind, FIELD_KINDS, "field kind")
    id = _id(id, "field id")  # noqa: A001
    common = f"{_attr('id', id)}{_attr('name', '' if name is None else name)}"
    if placeholder not in ("", None):
        common += _attr("placeholder", placeholder)
    common += _data(data)
    if kind == "textarea":
        ctrl = f'<textarea class="input"{common}>{_esc(value)}</textarea>'
    else:
        extra = ""
        if kind == "number":
            extra += ' inputmode="decimal" step="any"'
            extra += _attr("min", min) if min is not None else ""
            extra += _attr("max", max) if max is not None else ""
        ctrl = f'<input class="input"{_attr("type", kind)}{common}{_attr("value", "" if value is None else value)}{extra}>'
    return Safe(f'<div class="field"><label{_attr("for", id)}>{_esc(label)}</label>{ctrl}</div>')


def select(
    label: object,
    *,
    name: object,
    id: object,
    options: Sequence[tuple[object, object]],
    value: object = "",
    data: Mapping[str, object] | None = None,
) -> Safe:
    """A labelled `<select>`; ``options`` are ``(value, label)`` pairs and the one whose ``str(value)``
    equals ``value`` is selected."""
    id = _id(id, "select id")  # noqa: A001
    want = "" if value is None else str(value)
    pairs = [("" if v is None else str(v), text) for v, text in options]
    if _FILTER_CONTROL in (data or {}) and not any(ov == "" for ov, _ in pairs):
        raise ValueError("a filter select must offer an option whose value is '' (no filter)")
    opts = "".join(
        f"<option{_attr('value', ov)}{' selected' if ov == want else ''}>{_esc(text)}</option>"
        for ov, text in pairs
    )
    common = f"{_attr('id', id)}{_attr('name', '' if name is None else name)}{_data(data)}"
    return Safe(
        f'<div class="field"><label{_attr("for", id)}>{_esc(label)}</label>'
        f'<select class="input"{common}>{opts}</select></div>'
    )


def status_text(text: object, *, data: Mapping[str, object] | None = None) -> Safe:
    """A polite status line (``role="status"``) that `app.js` may rewrite, e.g. the filter's count."""
    return Safe(f'<p class="status-text" role="status"{_data(data)}>{_esc(text)}</p>')


def group(
    body: object,
    *,
    tag: str = "div",
    data: Mapping[str, object] | None = None,
    id: object = None,
    label: object = None,
) -> Safe:
    """A container carrying attributes — a filter group, a pick group, a pane, a filterable section.
    ``label`` becomes its ``aria-label`` (an accessible name for a ``nav`` or a region)."""
    _choice(tag, GROUP_TAGS, "group tag")
    ident = _attr("id", _id(id)) if id is not None else ""
    name = _attr("aria-label", label) if label is not None else ""
    return Safe(f"<{tag}{ident}{name}{_data(data)}>{_esc(body)}</{tag}>")


def section(title: object, body: object, *, id: object) -> Safe:
    """A titled region of a view: `<section>` labelled by its own `<h2>`, so it is a landmark."""
    ident = _id(id, "section id")
    title_id = f"{ident}-title"
    return Safe(
        f'<section class="section"{_attr("id", ident)}{_attr("aria-labelledby", title_id)}>'
        f'<h2 class="section-title"{_attr("id", title_id)}>{_esc(title)}</h2>{_esc(body)}</section>'
    )


def value_of(input_id: object) -> Safe:
    """The span a dialog body embeds; `app.js` fills it with that field's value when the dialog opens."""
    return Safe(
        f'<span class="value-of"{_attr("data-value-of", _id(input_id, "input id"))}></span>'
    )


def dialog(
    id: object,
    title: object,
    body: object,
    confirm_label: object,
    cancel_label: object,
    *,
    note: str | None = None,
) -> Safe:
    """A native confirm dialog: the body states the request and its consequence; no default yes."""
    _choice(note, NOTES, "note")
    id = _id(id, "dialog id")  # noqa: A001
    title_id = f"{id}-title"
    note_html = ""
    if note is not None:
        note_id = f"{id}-note"
        req = ' required aria-required="true"' if note == "required" else ""
        note_html = (
            f'<div class="field"><label{_attr("for", note_id)}>{_esc(t("dialog.note." + note))}</label>'
            f'<textarea class="input"{_attr("id", note_id)}{_attr("name", note_id)} data-dialog-note{req}>'
            "</textarea></div>"
        )
    return Safe(
        f'<dialog class="dialog"{_attr("id", id)}{_attr("aria-labelledby", title_id)} aria-modal="true">'
        f'<form method="dialog"><h2 class="dialog-title"{_attr("id", title_id)}>{_esc(title)}</h2>'
        f'<div class="dialog-body">{_esc(body)}</div>{note_html}'
        '<p class="inline-error" data-dialog-error role="alert" hidden></p>'
        '<div class="dialog-actions">'
        f'<button type="button" class="btn" data-kind="secondary" data-dialog-cancel>{_esc(cancel_label)}</button>'
        f'<button type="button" class="btn" data-kind="primary" data-dialog-confirm>{_esc(confirm_label)}</button>'
        "</div></form></dialog>"
    )


def disclosure(
    summary: object,
    body: object,
    *,
    open: bool = False,  # noqa: A002 — the HTML attribute's own name
    data: Mapping[str, object] | None = None,
    id: object = None,
) -> Safe:
    """A `<details>` disclosure; ``id`` lets `app.js` keep it open across a refresh."""
    _flag(open, "disclosure open")
    if _FILTER_SECTION in (data or {}) and id is None:
        raise ValueError(
            "a filter section needs an id: the filter records its opened sections by it"
        )
    ident = _attr("id", _id(id)) if id is not None else ""
    return Safe(
        f'<details class="disclosure"{ident}{" open" if open else ""}{_data(data)}>'
        f"<summary>{_esc(summary)}</summary>"
        f'<div class="disclosure-body">{_esc(body)}</div></details>'
    )


def tabs(label: object, items: Sequence[tuple[object, object, object]]) -> Safe:
    """WAI-ARIA APG tabs: one tablist, one panel per tab, the first selected."""
    btns, panels = [], []
    seen: set[str] = set()
    for i, (ident, title, body) in enumerate(items):
        _id(ident, "tab id")
        if ident in seen:
            raise ValueError(f"tab id {ident!r} appears twice")
        seen.add(ident)
        tab_id, panel_id = f"tab-{ident}", f"tabpanel-{ident}"
        sel = i == 0
        btns.append(
            f'<button type="button" role="tab"{_attr("id", tab_id)}{_attr("aria-controls", panel_id)}'
            f' aria-selected="{"true" if sel else "false"}" tabindex="{"0" if sel else "-1"}">{_esc(title)}</button>'
        )
        panels.append(
            f'<div role="tabpanel" class="tabpanel"{_attr("id", panel_id)}{_attr("aria-labelledby", tab_id)}'
            f' tabindex="0"{"" if sel else " hidden"}>{_esc(body)}</div>'
        )
    return Safe(
        f'<div class="tabs" data-tabs><div role="tablist"{_attr("aria-label", label)}>{"".join(btns)}</div>'
        f"{''.join(panels)}</div>"
    )


def clamp(text: object, lines: int = 3) -> Safe:
    """Text clamped to ``lines`` lines with a "show all" toggle (`app.js` hides it when nothing is cut)."""
    if isinstance(lines, bool) or not isinstance(lines, int) or lines not in CLAMP_LINES:
        raise ValueError(f"clamp lines {lines!r} is not 1-6")
    return Safe(
        f'<div class="clamp" data-clamp{_attr("data-lines", lines)}><p class="clamp-text">{_esc(text)}</p>'
        f'<button type="button" class="clamp-toggle" data-clamp-toggle aria-expanded="false">'
        f"{_esc(t('clamp.more'))}</button></div>"
    )


def region_state(kind: str, message: object, *, retry: bool = False) -> Safe:
    """A region's loading, empty or error state, in words; an error may offer Retry."""
    _choice(kind, STATES, "state")
    _flag(retry, "retry")
    role = "alert" if kind == "error" else "status"
    again = (
        f'<button type="button" class="btn" data-kind="secondary" data-retry>{_esc(t("state.retry"))}</button>'
        if retry and kind == "error"
        else ""
    )
    icon = (
        f'<span class="badge-icon" aria-hidden="true">{SEVERITY_ICONS["critical"]}</span>'
        if kind == "error"
        else ""
    )
    return Safe(
        f'<div class="region-state"{_attr("data-state", kind)}{_attr("role", role)}>'
        f'{icon}<p class="state-message">{_esc(message)}</p>{again}</div>'
    )


def freshness(read_ts: float | None, cadence_s: float | None) -> Safe:
    """A `<time>` stamp of the last read; `app.js` ticks it relative and marks it stale after two
    missed ``cadence_s`` intervals. ``cadence_s=None`` never goes stale; ``read_ts=None`` is "not read"."""
    if cadence_s is None:
        cadence = ""
    else:
        if _real(cadence_s, "cadence") <= 0:
            raise ValueError(f"cadence {cadence_s!r} must be above 0")
        cadence = _num(cadence_s)
    if read_ts is None:
        return Safe(
            f'<time class="freshness"{_attr("data-cadence", cadence)}>{_esc(t("fresh.never"))}</time>'
        )
    ts = _real(read_ts, "read time")
    if ts < 0:
        raise ValueError(f"read time {read_ts!r} is before 1970")
    try:
        when = datetime.fromtimestamp(ts, tz=UTC)
        local = datetime.fromtimestamp(ts).astimezone().strftime("%H:%M:%S")
    except (OverflowError, OSError) as exc:
        raise ValueError(f"read time {read_ts!r} is out of range") from exc
    return Safe(
        f'<time class="freshness"{_attr("datetime", when.isoformat())}{_attr("data-ts", _num(ts))}'
        f"{_attr('data-cadence', cadence)}>{_esc(t('fresh.read_at', time=local))}</time>"
    )


def _real(x: object, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{what} {x!r} is not a number")
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{what} {x!r} is not finite")
    return v


def _num(x: object) -> str:
    v = _real(x, "number")
    return str(int(v)) if v.is_integer() else repr(v)


def live_region() -> Safe:
    """The one polite live region for action results and freshness changes."""
    return Safe('<div id="live" class="live" role="status" aria-live="polite" data-live></div>')


def stale_banner(age_text: object, cause: object) -> Safe:
    """The stale-render banner (D-557), styled by tokens only."""
    words = t("stale.banner", age=age_text, cause=cause)
    return Safe(
        '<div id="render-failed" class="banner" role="alert" data-severity="critical">'
        f'<span class="badge-icon" aria-hidden="true">{SEVERITY_ICONS["critical"]}</span>'
        f"<p>{_esc(words)}</p></div>"
    )


def last_resort(words: object) -> Safe:
    """A view's error fragment for when building its error state failed too: constant markup around
    ``words``, escaped with `html.escape` alone — no other component, no catalogue lookup, no id check —
    so it raises on nothing a caller can pass."""
    try:
        text = html.escape(str(words), quote=True)
    except Exception:  # noqa: BLE001 — a __str__ that raises still gets the fragment
        text = ""
    return Safe(
        '<section data-stamp="error"><div class="region-state" data-state="error" role="alert">'
        f'<p class="state-message">{text}</p></div></section>'
    )


# The head script: runs before the stylesheet, so the first paint already has the stored theme.
_THEME_SCRIPT = (
    "(function(){try{var t=localStorage.getItem('qd-theme');"
    "if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();"
)


def _json_for_script(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def shell(
    views: Sequence[tuple[object, object]], active: object, *, body: object = Safe("")
) -> Safe:
    """The page: skip link, top bar (menu button below 1024 px), sidebar, one `<main id="view">`.

    ``views`` is ``[(id, title), …]``; ``active`` the id first shown. `app.js` fetches the view
    fragment into ``<main>`` unless ``body`` is given."""
    views = [(_id(vid, "view id"), title) for vid, title in views]
    _id(active, "active view id")
    links = "".join(
        f"<li><a{_attr('href', '#' + str(vid))}{_attr('data-nav', vid)}"
        f"{_attr('aria-current', 'page') if vid == active else ''}>{_esc(title)}</a></li>"
        for vid, title in views
    )
    return Safe(
        "<!doctype html>"
        f'<html{_attr("lang", t("app.lang"))}><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(t('app.title'))}</title>"
        f"<script>{_THEME_SCRIPT}</script>"
        '<link rel="stylesheet" href="/static/app.css">'
        f'<script type="application/json" id="qd-strings">{_json_for_script(dict(_catalogue()))}</script>'
        '<script src="/static/app.js" defer></script>'
        "</head><body>"
        f'<a class="skip-link" href="#view">{_esc(t("shell.skip"))}</a>'
        '<header class="topbar">'
        '<button type="button" class="btn menu-btn" data-kind="secondary" data-menu'
        f' aria-expanded="false" aria-controls="sidebar">{_esc(t("shell.menu"))}</button>'
        f'<h1 class="brand">{_esc(t("app.title"))}</h1>'
        f'<button type="button" class="btn" data-kind="secondary" data-theme-toggle>{_esc(t("shell.theme.system"))}</button>'
        "</header>"
        '<div class="layout">'
        f'<nav id="sidebar" class="sidebar"{_attr("aria-label", t("shell.nav_label"))}><ul>{links}</ul></nav>'
        f'<main id="view" class="view" tabindex="-1"{_attr("data-view", active)}>{_esc(body)}</main>'
        f"</div>{live_region()}"
        f'<template id="qd-state-loading">{region_state("loading", t("state.loading"))}</template>'
        f'<template id="qd-state-error">{region_state("error", t("state.too_long"), retry=True)}</template>'
        f'<template id="qd-state-failed">{region_state("error", t("state.failed"), retry=True)}</template>'
        f'<template id="qd-state-broken">{region_state("error", t("state.broken"), retry=True)}</template>'
        "</body></html>"
    )
