"""T01 — `app.js`'s behaviours, driven in a real browser over a fixture page.

A stdlib `http.server` on port 0 serves the package's `static/` files, a page built by
`components.shell`, fixture view fragments built by the same components, and records every POST.
Each test asserts what the operator sees or what reaches the server — roles, text, attributes, request
bodies — never a class string or a pixel (`.windsurf/rules/core/45-testing-strategy.md:21`).
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

sync_api = pytest.importorskip("playwright.sync_api")

_PKG = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "dashboard_ui"
sys.path.insert(0, str(_PKG.parent))

from dashboard_ui import components as ui  # noqa: E402
from dashboard_ui import strings as cat  # noqa: E402

VIEWS = [("overview", "Overview"), ("work", "Work"), ("usage", "Usage"), ("slow", "Slow")]


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.fragments: dict[str, str] = {}
        self.gets: list[str] = []
        self.posts: list[tuple[str, dict, dict]] = []
        self.get_headers: list[tuple[str, dict]] = []
        self.post_status = 200
        self.post_delay = 0.0
        self.post_error = "boom"

    def views_requested(self, path: str) -> int:
        with self.lock:
            return sum(1 for p in self.gets if p == path)


def _handler(state: _State):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 — http.server's own name
            path = self.path.split("?", 1)[0]
            with state.lock:
                state.gets.append(path)
                state.get_headers.append((path, dict(self.headers)))
            if path == "/":
                self._send(200, ui.shell(VIEWS, "overview").encode(), "text/html; charset=utf-8")
            elif path == "/nostrings":
                page = re.sub(
                    r'<script type="application/json" id="qd-strings">.*?</script>',
                    "",
                    ui.shell(VIEWS, "overview"),
                )
                self._send(200, page.encode(), "text/html; charset=utf-8")
            elif path in ("/static/app.css", "/static/app.js"):
                ctype = "text/css" if path.endswith(".css") else "text/javascript"
                self._send(200, (_PKG / path.lstrip("/")).read_bytes(), ctype + "; charset=utf-8")
            elif path.startswith("/v/") and path[3:] in state.fragments:
                self._send(200, state.fragments[path[3:]].encode(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            with state.lock:
                state.posts.append((self.path, body, dict(self.headers)))
                code, delay, error = state.post_status, state.post_delay, state.post_error
            if delay:
                time.sleep(delay)
            self._send(
                code, json.dumps({"ok": code == 200, "error": error}).encode(), "application/json"
            )

    return H


@pytest.fixture(scope="module")
def server():
    state = _State()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield state, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except sync_api.Error as exc:  # the package without its Chromium binary
            pytest.skip(f"Chromium cannot launch: {str(exc).splitlines()[0]}")
        yield b
        b.close()


@pytest.fixture
def board(server, browser):
    state, base = server
    with state.lock:
        state.fragments.clear()
        state.gets.clear()
        state.posts.clear()
        state.get_headers.clear()
        state.post_status = 200
        state.post_delay = 0.0
        state.post_error = "boom"
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.clock.install()
    page.clock.pause_at(1_000_000_000_000)

    def open_(hash_: str = "", fragments: dict[str, str] | None = None):
        state.fragments.update(fragments or {})
        page.goto(base + "/" + hash_)
        return page

    yield state, page, open_
    ctx.close()


def view(*parts, stamp="s1") -> str:
    return ui.group(ui.fragment(*parts), data={"stamp": stamp})


def posts(state: _State) -> list[tuple[str, dict]]:
    with state.lock:
        return [(p, b) for p, b, _ in state.posts]


def wait_posts(page, state: _State, n: int) -> None:
    for _ in range(100):
        if len(state.posts) >= n:
            return
        page.wait_for_timeout(20)
    raise AssertionError(f"expected {n} posts, saw {len(state.posts)}")


def settle(page) -> None:
    """Let in-flight fetches land (real time; the faked clock only drives timers)."""
    page.wait_for_timeout(150)


# ---------------------------------------------------------------- posts and dialogs
def _pause_view(note=None, path="/agent-pause"):
    btn = ui.button(
        "Pause infra",
        kind="danger",
        data={
            "post": path,
            "body": {"repo": "r", "agent": "infra"},
            "confirm": "dlg-p",
            "note": note,
        },
    )
    dlg = ui.dialog(
        "dlg-p",
        "Pause infra?",
        "It stops starting new work at its next turn boundary.",
        "Pause infra",
        "Keep running",
        note=note,
    )
    return view(btn, dlg)


def test_a_confirm_dialog_posts_only_on_confirm_and_returns_focus(board):
    state, page, open_ = board
    open_("#overview", {"overview": _pause_view()})
    pause = page.get_by_role("button", name="Pause infra")
    pause.click()
    dlg = page.get_by_role("dialog", name="Pause infra?")
    assert dlg.is_visible()
    page.get_by_role("button", name="Keep running").click()
    assert not dlg.is_visible()
    settle(page)
    assert posts(state) == []
    assert page.evaluate("document.activeElement.textContent") == "Pause infra"
    pause.click()
    page.keyboard.press("Escape")
    assert not dlg.is_visible() and posts(state) == []
    pause.click()
    dlg.get_by_role("button", name="Pause infra").click()
    wait_posts(page, state, 1)
    path, body, headers = state.posts[0]
    assert (path, body) == ("/agent-pause", {"repo": "r", "agent": "infra"})
    assert headers.get("X-Quota-Dash") == "1"
    settle(page)
    assert page.evaluate("document.activeElement.textContent") == "Pause infra"
    assert page.get_by_role("status").filter(has_text=cat.t("act.done")).count() == 1


def test_a_required_note_refuses_empty_and_sends_text_and_why(board):
    state, page, open_ = board
    open_("#overview", {"overview": _pause_view(note="required")})
    page.get_by_role("button", name="Pause infra").click()
    dlg = page.get_by_role("dialog")
    dlg.get_by_role("button", name="Pause infra").click()
    assert dlg.is_visible()
    assert dlg.get_by_role("alert").inner_text() == cat.t("act.refuse.note")
    settle(page)
    assert posts(state) == []
    dlg.get_by_label(cat.t("dialog.note.required")).fill("draining for the deploy")
    dlg.get_by_role("button", name="Pause infra").click()
    wait_posts(page, state, 1)
    assert posts(state)[0][1] == {
        "repo": "r",
        "agent": "infra",
        "text": "draining for the deploy",
        "why": "draining for the deploy",
    }


def test_an_inline_comment_posts_its_field_on_enter_and_refuses_empty(board):
    state, page, open_ = board
    frag = view(
        ui.field("Comment on W-1", name="c-w1", id="c-w1"),
        ui.button(
            "Comment", data={"post": "/item-comment", "body": {"item": "W-1"}, "text-from": "c-w1"}
        ),
    )
    open_("#overview", {"overview": frag})
    box = page.get_by_label("Comment on W-1")
    box.press("Enter")
    assert page.get_by_role("alert").inner_text() == cat.t("act.refuse.text")
    settle(page)
    assert posts(state) == []
    box.fill("looks right")
    box.press("Enter")
    wait_posts(page, state, 1)
    assert posts(state) == [("/item-comment", {"item": "W-1", "text": "looks right"})]
    settle(page)
    assert page.get_by_label("Comment on W-1").input_value() == ""


def _number_view():
    return view(
        ui.field("Weekly cap", name="cap-a", kind="number", id="cap-a", min=0, max=100),
        ui.button(
            "Set cap",
            data={
                "post": "/cap",
                "body": {"account": "a@x"},
                "input": "cap:int:0:100:nullable:cap-a",
            },
        ),
        ui.field("Rotate at", name="thr-a", kind="number", id="thr-a", min=50, max=100),
        ui.button(
            "Set rotate-at",
            data={
                "post": "/threshold",
                "body": {"account": "a@x"},
                "input": "threshold:float:50:100:nullable:thr-a",
            },
        ),
    )


def test_a_number_input_posts_null_when_empty_a_float_and_refuses_out_of_range(board):
    state, page, open_ = board
    open_("#overview", {"overview": _number_view()})
    page.get_by_role("button", name="Set cap").click()
    wait_posts(page, state, 1)
    assert posts(state)[0] == ("/cap", {"account": "a@x", "cap": None})
    settle(page)
    page.get_by_label("Weekly cap").fill("150")
    page.get_by_role("button", name="Set cap").click()
    assert page.get_by_role("alert").first.inner_text() == cat.t(
        "act.refuse.whole_or_empty", min="0", max="100"
    )
    page.get_by_label("Weekly cap").fill("40.5")
    page.get_by_role("button", name="Set cap").click()
    settle(page)
    assert len(posts(state)) == 1
    page.get_by_label("Rotate at").fill("87.5")
    page.get_by_role("button", name="Set rotate-at").click()
    wait_posts(page, state, 2)
    assert posts(state)[1] == ("/threshold", {"account": "a@x", "threshold": 87.5})


def test_a_confirm_dialog_states_the_typed_value(board):
    state, page, open_ = board
    frag = view(
        ui.field("Weekly cap", name="cap-a", kind="number", id="cap-a", min=0, max=100),
        ui.button(
            "Set cap",
            data={
                "post": "/cap",
                "body": {"account": "a@x"},
                "input": "cap:int:0:100:nullable:cap-a",
                "confirm": "dlg-cap",
            },
        ),
        ui.dialog(
            "dlg-cap",
            "Set the cap?",
            ui.fragment("Set the weekly cap on a@x to ", ui.value_of("cap-a"), "%?"),
            "Set cap",
            "Keep it",
        ),
    )
    open_("#overview", {"overview": frag})
    page.get_by_label("Weekly cap").fill("80")
    page.get_by_role("button", name="Set cap").click()
    dlg = page.get_by_role("dialog")
    sync_api.expect(dlg).to_contain_text("Set the weekly cap on a@x to 80%?")
    dlg.get_by_role("button", name="Keep it").click()
    page.get_by_label("Weekly cap").fill("")
    page.get_by_role("button", name="Set cap").click()
    sync_api.expect(dlg).to_contain_text(f"to {cat.t('act.clear')}%?")
    dlg.get_by_role("button", name="Set cap").click()
    wait_posts(page, state, 1)
    assert posts(state)[0][1] == {"account": "a@x", "cap": None}


def test_a_409_re_fetches_the_view_and_announces(board):
    state, page, open_ = board
    open_(
        "#overview",
        {
            "overview": view(
                ui.button("Accept", data={"post": "/item-verdict", "body": {"item": "W-1"}})
            )
        },
    )
    settle(page)
    before = state.views_requested("/v/overview")
    state.post_status = 409
    page.get_by_role("button", name="Accept").click()
    wait_posts(page, state, 1)
    settle(page)
    assert state.views_requested("/v/overview") == before + 1
    assert page.locator("#live").inner_text() == cat.t("act.changed")


def test_a_409_diverged_says_so_inline_keeps_the_card_and_never_re_fetches(board):
    """A 409 whose error is "diverged" (the board's checkout and main disagree about the item) cannot
    be cured by a reload, so it is said inline and announced, the card stays, and no view is fetched;
    any other 409 keeps the act.changed re-fetch above."""
    state, page, open_ = board
    open_(
        "#overview",
        {
            "overview": view(
                ui.card(
                    "W-1",
                    "q",
                    actions=ui.button(
                        "Accept", data={"post": "/item-verdict", "body": {"item": "W-1"}}
                    ),
                )
            )
        },
    )
    settle(page)
    before = state.views_requested("/v/overview")
    state.post_status = 409
    state.post_error = "diverged"
    page.get_by_role("button", name="Accept").click()
    wait_posts(page, state, 1)
    settle(page)
    assert page.get_by_role("alert").inner_text() == cat.t("act.diverged")
    assert page.locator("#live").inner_text() == cat.t("act.diverged")
    assert page.get_by_role("heading", name="W-1").is_visible()
    assert state.views_requested("/v/overview") == before


def test_any_other_failure_shows_inline_and_keeps_the_card(board):
    state, page, open_ = board
    open_(
        "#overview",
        {
            "overview": view(
                ui.card(
                    "W-1",
                    "q",
                    actions=ui.button("Accept", data={"post": "/item-verdict", "body": {}}),
                )
            )
        },
    )
    settle(page)
    before = state.views_requested("/v/overview")
    state.post_status = 500
    page.get_by_role("button", name="Accept").click()
    wait_posts(page, state, 1)
    settle(page)
    assert page.get_by_role("alert").inner_text() == cat.t("act.failed", error="boom")
    assert page.get_by_role("heading", name="W-1").is_visible()
    assert state.views_requested("/v/overview") == before


# ---------------------------------------------------------------- filters
def _filter_view(stamp="s1"):
    rows = [["api", "Alpha"], ["api-v2", "Beta"], ["ops", "Gamma"]]
    data = [{"f-tag": r[0], "f-name": r[1]} for r in rows]
    body = ui.fragment(
        ui.button("api", data={"filter": "tag:api"}),
        ui.field(
            "Tag",
            name="tag-box",
            kind="search",
            id="tag-box",
            data={"filter": "tag", "filter-mode": "token"},
        ),
        ui.field("Name", name="name-box", kind="search", id="name-box", data={"filter": "name"}),
        ui.table("t-f", "Items", ["Tag", "Name"], rows, row_data=data),
    )
    return view(ui.group(body, data={"filter-group": "items"}), stamp=stamp)


def _visible_rows(page) -> list[str]:
    return page.eval_on_selector_all(
        "tbody tr", "rs => rs.filter(r => !r.hidden).map(r => r.cells[0].textContent)"
    )


def test_chip_and_token_filters_match_token_equal_search_by_substring_and_survive_refresh(board):
    state, page, open_ = board
    open_("#overview", {"overview": _filter_view()})
    settle(page)
    assert _visible_rows(page) == ["api", "api-v2", "ops"]
    chip = page.get_by_role("button", name="api", exact=True)
    chip.click()
    assert _visible_rows(page) == ["api"]
    assert chip.get_attribute("aria-pressed") == "true"
    state.fragments["overview"] = _filter_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert _visible_rows(page) == ["api"]
    chip = page.get_by_role("button", name="api", exact=True)
    chip.click()
    assert _visible_rows(page) == ["api", "api-v2", "ops"]
    page.get_by_label("Tag").fill("api")
    assert _visible_rows(page) == ["api"]
    page.get_by_label("Tag").fill("")
    page.get_by_label("Name").fill("AMM")
    assert _visible_rows(page) == ["ops"]
    page.get_by_label("Name").blur()
    state.fragments["overview"] = _filter_view(stamp="s3")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert _visible_rows(page) == ["ops"]
    page.reload()
    settle(page)
    assert _visible_rows(page) == ["ops"]


# ---------------------------------------------------------------- filters: select, sections, count
_INV = {
    "Group one": [("alpha", "free"), ("beta", "freemium")],
    "Group two": [("gamma", "paid"), ("delta", "free")],
    "Group three": [("eps", "paid")],
}
_SID = {title: ui.slug(title, "inv") for title in _INV}
_FILTER_KEY, _OPEN_KEY = "qd-filter:inv", "qd-filter-open:inv"


def _inv_view(stamp="s1", *, same_summary=False, options=None, bar=True):
    sections = []
    for title, rows in _INV.items():
        table = ui.table(
            "t-" + _SID[title],
            title,
            ["Name", "Cost"],
            [[n, c] for n, c in rows],
            row_data=[{"filter-item": "", "f-name": n, "f-cost": c} for n, c in rows],
        )
        count = ui.group("", tag="span", data={"filter-count": ""})
        sections.append(
            ui.disclosure(
                ui.fragment("Group" if same_summary else title, " ", count),
                table,
                id=_SID[title],
                data={"filter-section": ""},
            )
        )
    controls = (
        [
            ui.field(
                "Name", name="name-box", kind="search", id="name-box", data={"filter": "name"}
            ),
            ui.select(
                "Cost",
                name="cost-sel",
                id="cost-sel",
                options=options or [("", "All"), ("free", "Free"), ("paid", "Paid")],
                data={"filter": "cost", "filter-mode": "token"},
            ),
        ]
        if bar
        else []
    )
    body = ui.fragment(
        *controls,
        ui.status_text("", data={"filter-status": ""}),
        *sections,
    )
    return view(ui.group(body, data={"filter-group": "inv"}), stamp=stamp)


def _sections(page) -> dict[str, tuple[bool, bool]]:
    """section id -> (hidden, open)"""
    rows = page.eval_on_selector_all(
        "details[data-filter-section]", "ds => ds.map(d => [d.id, d.hidden, d.open])"
    )
    return {i: (h, o) for i, h, o in rows}


def _counts(page) -> dict[str, str]:
    rows = page.eval_on_selector_all(
        "details[data-filter-section]",
        "ds => ds.map(d => [d.id, d.querySelector('[data-filter-count]').textContent])",
    )
    return dict(rows)


def _status(page) -> str:
    return page.locator("[data-filter-status]").text_content()


def _record(page):
    return json.loads(page.evaluate(f"localStorage.getItem({_OPEN_KEY!r})") or "null")


def _open_inv(open_, page):
    open_("#overview", {"overview": _inv_view()})
    settle(page)


def test_a_cost_select_in_token_mode_keeps_free_rows_and_never_freemium(board):
    state, page, open_ = board
    _open_inv(open_, page)
    assert _visible_rows(page) == ["alpha", "beta", "gamma", "delta", "eps"]
    page.select_option("#cost-sel", "free")
    assert _visible_rows(page) == ["alpha", "delta"]
    page.select_option("#cost-sel", "")
    assert _visible_rows(page) == ["alpha", "beta", "gamma", "delta", "eps"]
    page.select_option("#cost-sel", "paid")
    page.get_by_label("Name").fill("e")
    assert _visible_rows(page) == ["eps"]  # the select and the text box combine


def test_a_right_aligned_column_is_drawn_right_while_the_others_stay_left(board):
    state, page, open_ = board
    tbl = ui.table("t-a", "T", ["Name", "Keys"], [["a", "12"]], align=[None, "right"])
    open_("#overview", {"overview": view(tbl)})
    settle(page)
    align = "e => getComputedStyle(e).textAlign"
    assert page.locator("td").evaluate(align) == "right"
    assert page.locator("th[scope=col]").nth(1).evaluate(align) == "right"
    assert page.locator("th[scope=col]").nth(0).evaluate(align) in ("left", "start")
    figures = "e => getComputedStyle(e).fontVariantNumeric"
    assert "tabular-nums" in page.locator("td").evaluate(figures)
    assert "tabular-nums" not in page.locator("th[scope=col]").nth(0).evaluate(figures)


def test_a_stored_select_value_is_restored_and_an_unoffered_one_resets_to_all(board):
    state, page, open_ = board
    _open_inv(open_, page)
    stored = {"cost": {"v": "paid", "mode": "token", "chip": False}}
    page.evaluate(f"localStorage.setItem({_FILTER_KEY!r}, {json.dumps(json.dumps(stored))})")
    page.reload()
    settle(page)
    assert page.locator("#cost-sel").input_value() == "paid"
    assert _visible_rows(page) == ["gamma", "eps"]
    state.fragments["overview"] = _inv_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.locator("#cost-sel").input_value() == "paid"
    assert _visible_rows(page) == ["gamma", "eps"]
    gone = {
        "cost": {"v": "zzz", "mode": "token", "chip": False},
        "name": {"v": "e", "mode": "substr", "chip": False},
    }
    page.evaluate(f"localStorage.setItem({_FILTER_KEY!r}, {json.dumps(json.dumps(gone))})")
    page.reload()
    settle(page)
    assert page.locator("#cost-sel").input_value() == ""
    assert _visible_rows(page) == ["beta", "delta", "eps"]  # only the name key still filters
    kept = json.loads(page.evaluate(f"localStorage.getItem({_FILTER_KEY!r})"))
    assert list(kept) == ["name"]


def test_a_typed_term_opens_matching_sections_hides_the_rest_and_writes_the_counts(board):
    state, page, open_ = board
    _open_inv(open_, page)
    assert not any(o for _, o in _sections(page).values())
    page.get_by_label("Name").fill("gam")
    one, two, three = (_SID[k] for k in _INV)
    assert _sections(page) == {one: (True, False), two: (False, True), three: (True, False)}
    assert _record(page) == [two]
    assert _status(page) == cat.t("filter.shown", n=1, total=5)
    assert _counts(page)[two].strip() == cat.t("filter.group_count", n=1, total=2)
    assert _counts(page)[one].strip() == cat.t("filter.group_count", n=0, total=2)
    assert _counts(page)[three].strip() == cat.t("filter.group_count", n=0, total=1)


def test_clearing_the_filter_closes_what_it_opened_and_leaves_a_hand_opened_group_open(board):
    state, page, open_ = board
    _open_inv(open_, page)
    one, two, three = (_SID[k] for k in _INV)
    page.locator("summary", has_text="Group one").click()  # opened by hand
    page.get_by_label("Name").fill("a")
    assert _sections(page) == {one: (False, True), two: (False, True), three: (True, False)}
    assert _record(page) == [two]  # the hand-opened group is not the filter's to close
    page.get_by_label("Name").fill("")
    assert _sections(page) == {one: (False, True), two: (False, False), three: (False, False)}
    assert _record(page) == []
    assert _status(page) == cat.t("filter.shown", n=5, total=5)


def test_a_group_that_stops_matching_is_closed_while_the_filter_stays_on(board):
    state, page, open_ = board
    _open_inv(open_, page)
    one, two, three = (_SID[k] for k in _INV)
    page.get_by_label("Name").fill("gam")
    assert _record(page) == [two]
    page.get_by_label("Name").fill("eps")
    assert _sections(page) == {one: (True, False), two: (True, False), three: (False, True)}
    assert _record(page) == [three]


def test_the_filter_its_opened_groups_and_its_view_survive_a_swap_and_a_reload(board):
    state, page, open_ = board
    _open_inv(open_, page)
    one, two, three = (_SID[k] for k in _INV)
    page.get_by_label("Name").fill("gam")
    page.select_option("#cost-sel", "paid")
    before = (_sections(page), _record(page), _visible_rows(page), _status(page))
    assert before[1] == [two] and before[2] == ["gamma"]
    state.fragments["overview"] = _inv_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert (_sections(page), _record(page), _visible_rows(page), _status(page)) == before
    assert page.get_by_label("Name").input_value() == "gam"
    page.reload()
    settle(page)
    assert (_sections(page), _record(page), _visible_rows(page), _status(page)) == before
    assert page.get_by_label("Name").input_value() == "gam"
    assert page.locator("#cost-sel").input_value() == "paid"


@pytest.mark.parametrize("stored", ['{"a":1}', "[1,2]", '"x"', "not json", '[["a"]]'])
def test_a_corrupt_opened_group_record_is_reset_without_touching_the_filter_store(board, stored):
    state, page, open_ = board
    _open_inv(open_, page)
    page.get_by_label("Name").fill("gam")
    filt = page.evaluate(f"localStorage.getItem({_FILTER_KEY!r})")
    page.evaluate(f"localStorage.setItem({_OPEN_KEY!r}, {json.dumps(stored)})")
    page.reload()
    settle(page)
    assert page.evaluate(f"localStorage.getItem({_FILTER_KEY!r})") == filt
    assert _record(page) == [_SID["Group two"]]  # reset, then re-derived from the live filter
    assert _visible_rows(page) == ["gamma"]


# ---------------------------------------------------------------- clamp, menu, tabs, pick group
def test_the_clamp_toggle_shows_the_whole_question(board):
    state, page, open_ = board
    question = "Should the deploy go ahead tonight given the open incident? " * 40
    open_("#overview", {"overview": view(ui.clamp(question))})
    toggle = page.get_by_role("button", name=cat.t("clamp.more"))
    assert toggle.is_visible()
    box = page.locator("[data-clamp]")
    clamped = page.eval_on_selector(".clamp-text", "e => e.scrollHeight > e.clientHeight")
    assert clamped
    toggle.click()
    assert box.get_attribute("data-expanded") == ""
    assert (
        page.get_by_role("button", name=cat.t("clamp.less")).get_attribute("aria-expanded")
        == "true"
    )
    assert not page.eval_on_selector(".clamp-text", "e => e.scrollHeight > e.clientHeight + 1")


def test_the_menu_button_opens_and_escape_closes(board):
    state, page, open_ = board
    page.set_viewport_size({"width": 390, "height": 800})
    open_("#overview", {"overview": view("x")})
    menu = page.get_by_role("button", name=cat.t("shell.menu"))
    nav = page.get_by_role("navigation", name=cat.t("shell.nav_label"))
    assert menu.get_attribute("aria-expanded") == "false" and not nav.is_visible()
    menu.click()
    assert menu.get_attribute("aria-expanded") == "true" and nav.is_visible()
    page.keyboard.press("Escape")
    assert menu.get_attribute("aria-expanded") == "false" and not nav.is_visible()
    assert page.evaluate("document.activeElement.getAttribute('data-menu')") == ""


def test_the_tabs_move_with_the_arrow_keys_home_and_end(board):
    state, page, open_ = board
    open_(
        "#overview",
        {
            "overview": view(
                ui.tabs(
                    "Range",
                    [
                        ("d", "Day", "day body"),
                        ("w", "Week", "week body"),
                        ("m", "Month", "month body"),
                    ],
                )
            )
        },
    )
    day = page.get_by_role("tab", name="Day")
    day.focus()
    page.keyboard.press("ArrowRight")
    week = page.get_by_role("tab", name="Week")
    assert week.get_attribute("aria-selected") == "true" and week.get_attribute("tabindex") == "0"
    assert day.get_attribute("aria-selected") == "false" and day.get_attribute("tabindex") == "-1"
    assert page.get_by_role("tabpanel").inner_text() == "week body"
    page.keyboard.press("End")
    assert page.get_by_role("tab", name="Month").get_attribute("aria-selected") == "true"
    page.keyboard.press("Home")
    assert day.get_attribute("aria-selected") == "true"
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("document.activeElement.textContent") == "Month"


def test_a_hash_with_a_second_segment_shows_that_pane_and_fetches_the_view_only(board):
    state, page, open_ = board
    panes = ui.fragment(
        ui.button("a", data={"pick-to": "a"}),
        ui.button("b", data={"pick-to": "b"}),
        ui.group("pane a", data={"pick": "a"}),
        ui.group("pane b", data={"pick": "b"}),
    )
    open_("#work/b", {"work": view(ui.group(panes, data={"pick-group": "repos"}))})
    settle(page)
    assert page.get_by_text("pane b").is_visible() and not page.get_by_text("pane a").is_visible()
    assert state.views_requested("/v/work") == 1
    assert not any(p.startswith("/v/work/") for p in state.gets)
    page.get_by_role("button", name="a", exact=True).click()
    settle(page)
    assert page.evaluate("location.hash") == "#work/a"
    assert page.get_by_text("pane a").is_visible() and not page.get_by_text("pane b").is_visible()
    assert state.views_requested("/v/work") == 1
    assert page.get_by_role("link", name="Work").get_attribute("aria-current") == "page"


# ---------------------------------------------------------------- loading timers (faked clock)
def test_a_slow_view_shows_nothing_then_loading_still_loading_retry_and_error(board):
    state, page, open_ = board
    open_("#overview", {"overview": view("ready")})
    settle(page)
    held = []
    page.route("**/v/slow", lambda route: held.append(route))
    page.evaluate("location.hash = '#slow'")
    settle(page)
    page.clock.run_for(299)
    assert page.locator('[data-state="loading"]').count() == 0
    page.clock.run_for(2)
    loading = page.get_by_role("status").filter(has_text=cat.t("state.loading"))
    assert loading.count() == 1
    assert page.get_by_text(cat.t("state.still_loading")).count() == 0
    page.clock.run_for(2_700)
    assert page.get_by_text(cat.t("state.still_loading")).count() == 1
    assert page.get_by_role("button", name=cat.t("state.retry")).count() == 0
    page.clock.run_for(7_000)
    assert page.get_by_role("button", name=cat.t("state.retry")).count() == 1
    page.clock.run_for(20_000)
    err = page.get_by_role("alert")
    assert cat.t("state.too_long") in err.inner_text()
    assert err.get_by_role("button", name=cat.t("state.retry")).count() == 1


# ---------------------------------------------------------------- refresh skips (INV-5)
def _tick(page) -> None:
    page.clock.run_for(20_000)
    settle(page)


def test_a_refresh_tick_is_skipped_while_a_field_is_focused_a_dialog_open_text_selected_or_hidden(
    board,
):
    state, page, open_ = board
    frag = view(
        ui.field("Comment", name="c1", id="c1"),
        ui.button("Pause", data={"post": "/agent-pause", "body": {}, "confirm": "dlg"}),
        ui.dialog("dlg", "Pause?", "It stops.", "Pause", "Keep"),
        "some selectable words",
    )
    open_("#overview", {"overview": frag})
    settle(page)
    n = state.views_requested("/v/overview")
    _tick(page)
    assert state.views_requested("/v/overview") == n + 1  # the control: an idle tick does fetch
    n += 1
    page.get_by_label("Comment").focus()
    _tick(page)
    assert state.views_requested("/v/overview") == n
    page.get_by_label("Comment").blur()
    page.get_by_role("button", name="Pause").click()
    _tick(page)
    assert state.views_requested("/v/overview") == n
    page.get_by_role("button", name="Keep").click()
    page.evaluate("""() => { const r = document.createRange(); r.selectNodeContents(document.querySelector('main'));
                      getSelection().removeAllRanges(); getSelection().addRange(r); }""")
    _tick(page)
    assert state.views_requested("/v/overview") == n
    page.evaluate("getSelection().removeAllRanges()")
    page.evaluate(
        "Object.defineProperty(document, 'hidden', {configurable: true, get: () => true})"
    )
    _tick(page)
    assert state.views_requested("/v/overview") == n
    page.evaluate("delete document.hidden")
    _tick(page)
    assert state.views_requested("/v/overview") == n + 1


def test_the_refresh_after_a_successful_post_is_forced_past_the_skips(board):
    state, page, open_ = board
    frag = view(
        ui.field("Comment", name="c1", id="c1"),
        ui.button("Comment", data={"post": "/item-comment", "body": {}, "text-from": "c1"}),
    )
    open_("#overview", {"overview": frag})
    settle(page)
    n = state.views_requested("/v/overview")
    box = page.get_by_label("Comment")
    box.fill("done")
    box.press("Enter")  # the field keeps focus: an ordinary tick would skip
    wait_posts(page, state, 1)
    settle(page)
    assert state.views_requested("/v/overview") == n + 1


def test_a_half_typed_field_survives_a_swap_and_an_unchanged_stamp_is_not_swapped(board):
    state, page, open_ = board
    frag = view(
        ui.field("Comment", name="c-w1", id="c-w1"),
        ui.disclosure("Edit", "panel", id="ed-a"),
        stamp="s1",
    )
    open_("#overview", {"overview": frag})
    settle(page)
    page.get_by_label("Comment").fill("half a thou")
    page.get_by_label("Comment").blur()
    page.get_by_text("Edit").click()
    page.evaluate("document.querySelector('main [data-stamp]').setAttribute('data-mark', 'old')")
    _tick(page)
    assert page.locator("[data-mark]").count() == 1  # same stamp: no swap
    state.fragments["overview"] = view(
        ui.field("Comment", name="c-w1", id="c-w1"),
        ui.disclosure("Edit", "panel", id="ed-a"),
        stamp="s2",
    )
    _tick(page)
    assert page.locator("[data-mark]").count() == 0  # new stamp: swapped
    assert page.get_by_label("Comment").input_value() == "half a thou"
    assert page.locator("details#ed-a").get_attribute("open") == ""


# ---------------------------------------------------------------- theme
def test_the_theme_cycles_system_light_dark_and_persists_without_a_flash(board):
    state, page, open_ = board
    open_("#overview", {"overview": view("x")})
    toggle = page.get_by_role("button", name=cat.t("shell.theme.system"))
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") is None
    toggle.click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
    page.get_by_role("button", name=cat.t("shell.theme.light")).click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.route(
        "**/static/app.js",
        lambda route: route.fulfill(status=200, body="", content_type="text/javascript"),
    )
    page.reload()
    # the head script alone set it: app.js is stubbed out on this load
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"
    page.unroute("**/static/app.js")
    page.reload()
    page.get_by_role("button", name=cat.t("shell.theme.dark")).click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") is None
    assert page.evaluate("localStorage.getItem('qd-theme')") is None


# ---------------------------------------------------------------- review round 1 regressions
def _alert_texts(page) -> list[str]:
    return page.eval_on_selector_all(
        '[role="alert"]:not([hidden])', "es => es.map(e => e.textContent)"
    )


def test_a_view_fetch_carries_the_guard_header(board):
    state, page, open_ = board
    open_("#overview", {"overview": view("x")})
    settle(page)
    heads = [h for p, h in state.get_headers if p == "/v/overview"]
    assert heads and heads[0].get("X-Quota-Dash") == "1"


@pytest.mark.parametrize("confirm", ["dlg-missing", "not-a-dialog", ""])
def test_a_confirm_that_resolves_to_no_dialog_refuses_and_never_posts(board, confirm):
    state, page, open_ = board
    frag = view(
        ui.group("plain", id="not-a-dialog"),
        ui.button(
            "Accept", data={"post": "/item-verdict", "body": {"item": "W-1"}, "confirm": confirm}
        ),
    )
    open_("#overview", {"overview": frag})
    page.get_by_role("button", name="Accept").click()
    settle(page)
    assert posts(state) == []
    assert cat.t("act.refuse.confirm") in _alert_texts(page)
    assert page.locator("#live").inner_text() == cat.t("act.refuse.confirm")


def test_a_required_note_without_a_dialog_refuses(board):
    state, page, open_ = board
    frag = view(ui.button("Reject", data={"post": "/item-verdict", "body": {}, "note": "required"}))
    open_("#overview", {"overview": frag})
    page.get_by_role("button", name="Reject").click()
    settle(page)
    assert posts(state) == [] and cat.t("act.refuse.no_reason") in _alert_texts(page)


def test_a_number_input_whose_field_is_missing_refuses(board):
    state, page, open_ = board
    frag = view(
        ui.button(
            "Set cap", data={"post": "/cap", "body": {}, "input": "cap:int:0:100:nullable:gone"}
        )
    )
    open_("#overview", {"overview": frag})
    page.get_by_role("button", name="Set cap").click()
    settle(page)
    assert posts(state) == [] and cat.t("act.refuse.no_field") in _alert_texts(page)


@pytest.mark.parametrize("raw", ["1e2", "0x40", "6e1", "+60", "6 0"])
def test_a_number_is_parsed_strictly(board, raw):
    """Each value is inside 50-100 by Number(); only the strict grammar refuses it."""
    state, page, open_ = board
    open_("#overview", {"overview": _number_view()})
    page.get_by_label("Rotate at").wait_for()
    settle(page)
    page.evaluate(
        f"(() => {{ const f = document.getElementById('thr-a'); f.type = 'text'; f.value = {raw!r}; }})()"
    )
    assert page.get_by_label("Rotate at").input_value() == raw
    page.get_by_role("button", name="Set rotate-at").click()
    settle(page)
    assert posts(state) == []


def test_a_required_number_refuses_empty(board):
    state, page, open_ = board
    frag = view(
        ui.field("Cap", name="cap-r", kind="number", id="cap-r"),
        ui.button(
            "Set", data={"post": "/cap", "body": {}, "input": "cap:int:0:100:required:cap-r"}
        ),
    )
    open_("#overview", {"overview": frag})
    page.get_by_role("button", name="Set").click()
    settle(page)
    assert posts(state) == [] and cat.t("act.refuse.whole", min="0", max="100") in _alert_texts(
        page
    )


@pytest.mark.parametrize("raw", ["49", "101"])
def test_the_float_field_refuses_out_of_range_and_says_so(board, raw):
    state, page, open_ = board
    open_("#overview", {"overview": _number_view()})
    page.get_by_label("Rotate at").fill(raw)
    page.get_by_role("button", name="Set rotate-at").click()
    settle(page)
    assert posts(state) == []
    assert cat.t("act.refuse.range_or_empty", min="50", max="100") in _alert_texts(page)


def _slow_post_view(stamp="s1"):
    return view(
        ui.button("Resume", data={"post": "/agent-resume", "body": {"agent": "infra"}}), stamp=stamp
    )


def test_a_double_click_posts_once(board):
    state, page, open_ = board
    state.post_delay = 0.5
    open_("#overview", {"overview": _slow_post_view()})
    page.get_by_role("button", name="Resume").dblclick()
    page.wait_for_timeout(800)
    assert len(posts(state)) == 1


def test_a_tick_during_a_post_is_skipped_and_a_swap_keeps_the_control_disabled(board):
    state, page, open_ = board
    open_("#overview", {"overview": _slow_post_view()})
    settle(page)
    n = state.views_requested("/v/overview")
    state.post_delay = 1.0
    page.get_by_role("button", name="Resume").click()
    page.clock.run_for(20_000)
    page.wait_for_timeout(100)
    assert state.views_requested("/v/overview") == n  # the tick waited for the post
    state.fragments["overview"] = _slow_post_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    page.wait_for_timeout(150)
    assert page.get_by_role("button", name="Resume").is_disabled()
    page.get_by_role("button", name="Resume").click(force=True)
    page.wait_for_timeout(1200)
    assert len(posts(state)) == 1


def test_a_forced_refresh_waits_for_an_open_dialog(board):
    state, page, open_ = board
    frag = view(
        ui.button("Pause", data={"post": "/agent-pause", "body": {}, "confirm": "dlg"}),
        ui.dialog("dlg", "Pause?", "It stops.", "Pause", "Keep"),
    )
    open_("#overview", {"overview": frag})
    settle(page)
    n = state.views_requested("/v/overview")
    page.get_by_role("button", name="Pause").click()
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert state.views_requested("/v/overview") == n
    page.get_by_role("button", name="Keep").click()
    settle(page)
    assert state.views_requested("/v/overview") == n + 1


@pytest.mark.parametrize("declared,ticks_at", [("7", 7_000), ("1", 20_000), ("soon", 20_000)])
def test_data_refresh_s_is_read_from_the_new_view_and_clamped(board, declared, ticks_at):
    state, page, open_ = board
    frag = ui.group(ui.fragment("x"), data={"stamp": "s1", "refresh-s": declared})
    open_("#overview", {"overview": frag})
    settle(page)
    n = state.views_requested("/v/overview")
    page.clock.run_for(ticks_at - 500)
    settle(page)
    assert state.views_requested("/v/overview") == n
    page.clock.run_for(1_000)
    settle(page)
    assert state.views_requested("/v/overview") == n + 1


def test_a_view_without_cadence_gets_its_declared_refresh_after_the_load(board):
    state, page, open_ = board
    frag = ui.group(ui.fragment("u"), data={"stamp": "s1", "refresh-s": "8"})
    open_("#usage", {"usage": frag})
    settle(page)
    n = state.views_requested("/v/usage")
    page.clock.run_for(8_100)
    settle(page)
    assert state.views_requested("/v/usage") == n + 1


def test_typed_text_is_carried_by_field_id_not_shared_name(board):
    state, page, open_ = board

    def two(stamp):
        return view(
            ui.field("Comment A", name="comment", id="c-a"),
            ui.field("Comment B", name="comment", id="c-b"),
            stamp=stamp,
        )

    open_("#overview", {"overview": two("s1")})
    page.get_by_label("Comment A").fill("for A only")
    page.get_by_label("Comment A").blur()
    state.fragments["overview"] = two("s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.get_by_label("Comment A").input_value() == "for A only"
    assert page.get_by_label("Comment B").input_value() == ""


@pytest.mark.parametrize("bad", ["#%E0%A4%A", "#work/100%"])
def test_a_malformed_hash_falls_back_to_the_default_view_and_still_ticks(board, bad):
    state, page, open_ = board
    open_(bad, {"overview": view("home"), "work": view("w")})
    settle(page)
    assert page.locator("main").inner_text() == "home"
    n = state.views_requested("/v/overview")
    page.clock.run_for(20_000)
    settle(page)
    assert state.views_requested("/v/overview") == n + 1


@pytest.mark.parametrize(
    "stored", ['{"tag":{"v":5}}', "[1,2]", '{"tag":{"v":"api","mode":"evil"}}', "null-ish"]
)
def test_a_corrupt_stored_filter_resets(board, stored):
    state, page, open_ = board
    page.add_init_script(
        f"try {{ localStorage.setItem('qd-filter:items', {stored!r}); }} catch (e) {{}}"
    )
    open_("#overview", {"overview": _filter_view()})
    settle(page)
    assert _visible_rows(page) == ["api", "api-v2", "ops"]
    if stored != "null-ish":
        assert page.evaluate("localStorage.getItem('qd-filter:items')") == "{}"


def test_a_fault_while_showing_a_view_is_not_reported_as_a_network_failure(board):
    state, page, open_ = board
    open_("#overview", {"overview": view(ui.disclosure("Edit", "x", id="ed"), stamp="s1")})
    settle(page)
    page.get_by_text("Edit").click()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.evaluate(
        "Object.defineProperty(HTMLDetailsElement.prototype, 'open', {configurable: true,"
        " get() { return this.hasAttribute('open'); }, set(v) { throw new Error('boom'); }})"
    )
    state.fragments["overview"] = view(ui.disclosure("Edit", "x", id="ed"), stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert cat.t("state.broken") in page.locator("main").inner_text()
    assert cat.t("state.failed") not in page.locator("main").inner_text()
    assert any("could not be shown" in e for e in errors)


def test_a_tick_during_a_forced_fetch_keeps_it_forced(board):
    state, page, open_ = board
    open_("#overview", {"overview": view("old text", stamp="s1")})
    settle(page)
    held = []
    page.route("**/v/overview", lambda route: held.append(route))
    page.evaluate("window.qdRefresh(true)")
    page.wait_for_timeout(100)
    page.clock.run_for(20_000)
    page.wait_for_timeout(100)
    body = view("new text", stamp="s1")  # the same stamp: only a forced swap shows it
    for r in held:
        r.fulfill(status=200, body=body, content_type="text/html")
    settle(page)
    assert page.locator("main").inner_text() == "new text"


def test_a_new_fetch_aborts_the_one_in_flight(board):
    state, page, open_ = board
    page.add_init_script(
        "window._sigs = []; const f = window.fetch;"
        " window.fetch = function (u, i) { if (String(u).indexOf('/v/') >= 0) { window._sigs.push(i && i.signal); }"
        " return f.apply(this, arguments); };"
    )
    open_("#overview", {"overview": view("x")})
    settle(page)
    page.route("**/v/overview", lambda route: None)  # hold every later load
    page.evaluate("window.qdRefresh(true)")
    page.evaluate("window.qdRefresh(true)")
    assert page.evaluate("window._sigs.length") == 3
    assert page.evaluate("window._sigs[1].aborted") is True
    assert page.evaluate("window._sigs[2].aborted") is False


def test_a_clamp_in_a_hidden_tab_is_measured_when_shown_and_stays_expanded_across_a_swap(board):
    state, page, open_ = board
    question = "Should the deploy go ahead tonight given the open incident? " * 40

    def frag(stamp):
        return view(
            ui.tabs("Range", [("a", "First", "short"), ("b", "Second", ui.clamp(question))]),
            stamp=stamp,
        )

    open_("#overview", {"overview": frag("s1")})
    settle(page)
    page.get_by_role("tab", name="Second").click()
    toggle = page.get_by_role("button", name=cat.t("clamp.more"))
    assert toggle.is_visible()
    toggle.click()
    state.fragments["overview"] = frag("s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert (
        page.get_by_role("button", name=cat.t("clamp.less")).get_attribute("aria-expanded")
        == "true"
    )
    assert page.locator("[data-clamp]").get_attribute("data-expanded") == ""


def test_went_stale_is_announced_once_not_on_every_swap(board):
    state, page, open_ = board

    def frag(stamp):
        return view(ui.freshness(1.0, 20), stamp=stamp)

    open_("#overview", {"overview": frag("s1")})
    settle(page)
    assert page.locator("#live").inner_text() == cat.t("fresh.went_stale")
    page.evaluate("document.getElementById('live').textContent = ''")
    state.fragments["overview"] = frag("s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.locator("#live").inner_text() == ""


def test_a_fault_after_a_landed_write_is_not_reported_as_unreachable(board):
    state, page, open_ = board
    open_(
        "#overview",
        {"overview": view(ui.button("Resume", data={"post": "/agent-resume", "body": {}}))},
    )
    settle(page)
    page.evaluate(
        "Object.defineProperty(document.getElementById('live'), 'textContent',"
        " {configurable: true, set(v) { throw new Error('boom'); }, get() { return ''; }})"
    )
    page.get_by_role("button", name="Resume").click()
    wait_posts(page, state, 1)
    settle(page)
    assert cat.t("act.unreachable") not in _alert_texts(page)


def test_a_token_filter_with_several_tokens_needs_every_one(board):
    state, page, open_ = board
    rows = [["ops api", "Alpha"], ["api", "Beta"], ["ops", "Gamma"]]
    data = [{"f-tag": r[0], "f-name": r[1]} for r in rows]
    body = ui.fragment(
        ui.field(
            "Tag",
            name="tag-box",
            kind="search",
            id="tag-box",
            data={"filter": "tag", "filter-mode": "token"},
        ),
        ui.table("t-f", "Items", ["Tag", "Name"], rows, row_data=data),
    )
    open_("#overview", {"overview": view(ui.group(body, data={"filter-group": "items"}))})
    page.get_by_label("Tag").fill("api ops")
    assert _visible_rows(page) == ["ops api"]


def test_a_missing_catalogue_logs_and_shows_words_not_keys(board, server):
    state, page, open_ = board
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    state.fragments["overview"] = view("x")
    page.goto(server[1] + "/nostrings")
    settle(page)
    label = page.locator("[data-theme-toggle]").inner_text()
    assert "." not in label and label.strip() != ""
    assert any("qd-strings" in e for e in errors)


def test_enter_while_composing_does_not_submit(board):
    state, page, open_ = board
    frag = view(
        ui.field("Comment", name="c1", id="c1"),
        ui.button("Comment", data={"post": "/item-comment", "body": {}, "text-from": "c1"}),
    )
    open_("#overview", {"overview": frag})
    page.get_by_label("Comment").fill("こんにち")
    page.evaluate(
        "document.getElementById('c1').dispatchEvent(new KeyboardEvent('keydown',"
        " {key: 'Enter', isComposing: true, bubbles: true, cancelable: true}))"
    )
    settle(page)
    assert posts(state) == []


def test_a_non_object_body_posts_as_an_object(board):
    state, page, open_ = board
    open_("#overview", {"overview": view(ui.button("Go", data={"post": "/x", "body": [1, 2]}))})
    page.get_by_role("button", name="Go").click()
    wait_posts(page, state, 1)
    assert posts(state)[0] == ("/x", {})


@pytest.mark.parametrize("path", ["https://evil.example/x", "//evil.example/x", "x"])
def test_a_post_path_must_be_same_origin_absolute(board, path):
    state, page, open_ = board
    open_("#overview", {"overview": view(ui.button("Go", data={"post": path, "body": {}}))})
    page.get_by_role("button", name="Go").click()
    settle(page)
    assert posts(state) == [] and cat.t("act.refuse.path") in _alert_texts(page)


def test_becoming_visible_refreshes(board):
    state, page, open_ = board
    open_("#overview", {"overview": view("x")})
    settle(page)
    n = state.views_requested("/v/overview")
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    settle(page)
    assert state.views_requested("/v/overview") == n + 1


def test_the_theme_button_is_labelled_from_the_stored_theme_on_load(board):
    state, page, open_ = board
    page.add_init_script("try { localStorage.setItem('qd-theme', 'dark'); } catch (e) {}")
    open_("#overview", {"overview": view("x")})
    assert page.locator("[data-theme-toggle]").inner_text() == cat.t("shell.theme.dark")


def test_scroll_is_kept_across_a_swap(board):
    state, page, open_ = board
    tall = ui.fragment(*(ui.card(f"Card {i}", "body " * 50) for i in range(60)))
    open_("#overview", {"overview": view(tall, stamp="s1")})
    settle(page)
    page.evaluate("window.scrollTo(0, 1500)")
    state.fragments["overview"] = view(tall, stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.evaluate("window.scrollY") == 1500


def test_it_works_when_local_storage_throws(board):
    state, page, open_ = board
    page.add_init_script(
        "for (const m of ['getItem', 'setItem', 'removeItem']) {"
        " Storage.prototype[m] = function () { throw new Error('denied'); }; }"
    )
    open_("#overview", {"overview": _filter_view()})
    settle(page)
    page.get_by_role("button", name="api", exact=True).click()
    assert _visible_rows(page) == ["api"]
    page.get_by_role("button", name=cat.t("shell.theme.system")).click()
    assert page.evaluate("document.documentElement.getAttribute('data-theme')") == "light"


def test_arrow_right_wraps_from_the_last_tab(board):
    state, page, open_ = board
    open_(
        "#overview", {"overview": view(ui.tabs("Range", [("d", "Day", "1"), ("w", "Week", "2")]))}
    )
    page.get_by_role("tab", name="Week").click()
    page.keyboard.press("ArrowRight")
    assert page.get_by_role("tab", name="Day").get_attribute("aria-selected") == "true"
    assert page.evaluate("document.activeElement.textContent") == "Day"


def test_a_pick_value_with_reserved_characters_round_trips_through_the_hash(board):
    state, page, open_ = board
    odd = 'a%/b"c'
    panes = ui.fragment(
        ui.button("odd", data={"pick-to": odd}),
        ui.group("pane plain", data={"pick": "plain"}),
        ui.group("pane odd", data={"pick": odd}),
    )
    open_("#work", {"work": view(ui.group(panes, data={"pick-group": "repos"}))})
    settle(page)
    page.get_by_role("button", name="odd").click()
    settle(page)
    assert page.evaluate("location.hash") == "#work/a%25%2Fb%22c"
    assert (
        page.get_by_text("pane odd").is_visible()
        and not page.get_by_text("pane plain").is_visible()
    )


def test_a_server_error_is_shown_as_text_not_markup(board):
    state, page, open_ = board
    state.post_status = 500
    state.post_error = "<b>bold</b>"
    open_("#overview", {"overview": view(ui.button("Go", data={"post": "/x", "body": {}}))})
    page.get_by_role("button", name="Go").click()
    wait_posts(page, state, 1)
    settle(page)
    assert cat.t("act.failed", error="<b>bold</b>") in _alert_texts(page)
    assert page.locator("main b").count() == 0


def test_an_ordinary_tick_keeps_the_filters(board):
    state, page, open_ = board
    open_("#overview", {"overview": _filter_view()})
    settle(page)
    page.get_by_role("button", name="api", exact=True).click()
    state.fragments["overview"] = _filter_view(stamp="s9")
    page.get_by_role("button", name="api", exact=True).blur()
    page.clock.run_for(20_000)
    settle(page)
    assert page.locator("[data-stamp]").get_attribute("data-stamp") == "s9"
    assert _visible_rows(page) == ["api"]


# ---------------------------------------------------------------- review round 2 regressions
def test_a_hung_post_times_out_and_never_freezes_other_views(board):
    state, page, open_ = board
    open_("#overview", {"overview": _slow_post_view(), "work": view("w")})
    settle(page)
    page.route("**/agent-resume", lambda route: None)  # the board never answers
    page.get_by_role("button", name="Resume").click()
    page.wait_for_timeout(100)
    page.evaluate("location.hash = '#work'")
    settle(page)
    n = state.views_requested("/v/work")
    page.clock.run_for(20_000)
    settle(page)
    assert state.views_requested("/v/work") == n + 1  # the hung post on Overview does not stop Work
    page.evaluate("location.hash = '#overview'")
    settle(page)
    page.clock.run_for(61_000)
    settle(page)
    assert cat.t("act.unreachable") in _alert_texts(page)
    assert not page.get_by_role("button", name="Resume").is_disabled()


def test_a_hung_post_is_aborted_after_its_timeout(board):
    state, page, open_ = board
    open_("#overview", {"overview": _slow_post_view()})
    settle(page)
    page.route("**/agent-resume", lambda route: None)
    page.get_by_role("button", name="Resume").click()
    page.wait_for_timeout(100)
    page.clock.run_for(61_000)
    settle(page)
    assert cat.t("act.unreachable") in _alert_texts(page)
    assert not page.get_by_role("button", name="Resume").is_disabled()


def test_a_backslash_path_cannot_leave_the_origin(board):
    state, page, open_ = board
    seen = []
    page.on("request", lambda r: seen.append(r.url) if r.method == "POST" else None)
    open_(
        "#overview",
        {"overview": view(ui.button("Go", data={"post": "/\\evil.example/x", "body": {}}))},
    )
    page.get_by_role("button", name="Go").click()
    settle(page)
    assert not any("evil.example" in u for u in seen)
    assert cat.t("act.refuse.path") in _alert_texts(page)


def test_a_post_goes_to_the_resolved_same_origin_path(board):
    state, page, open_ = board
    open_(
        "#overview", {"overview": view(ui.button("Go", data={"post": "/a/../cap?x=1", "body": {}}))}
    )
    page.get_by_role("button", name="Go").click()
    wait_posts(page, state, 1)
    assert state.posts[0][0] == "/cap?x=1"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("kind", ["primary", "danger", "secondary"])
def test_a_disabled_button_of_every_kind_stays_legible(board, theme, kind):
    state, page, open_ = board
    page.add_init_script(f"try {{ localStorage.setItem('qd-theme', '{theme}'); }} catch (e) {{}}")
    open_(
        "#overview",
        {"overview": view(ui.button("Off", kind=kind, data={"post": "/x", "body": {}}))},
    )
    btn = page.get_by_role("button", name="Off")
    btn.evaluate("b => { b.disabled = true; }")
    btn.hover(force=True)
    page.wait_for_timeout(400)  # past the background transition
    ratio = btn.evaluate(
        """b => { const cs = getComputedStyle(b);
        const rgb = s => s.match(/\\d+(\\.\\d+)?/g).slice(0, 3).map(Number);
        const lum = c => { const l = c.map(v => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
                           return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]; };
        const a = lum(rgb(cs.color)), z = lum(rgb(cs.backgroundColor));
        return (Math.max(a, z) + 0.05) / (Math.min(a, z) + 0.05); }"""
    )
    assert ratio >= 4.5


def test_a_number_field_with_bad_input_refuses_instead_of_clearing(board):
    state, page, open_ = board
    open_("#overview", {"overview": _number_view()})
    page.get_by_label("Weekly cap").click()
    page.keyboard.type("1-")  # Chrome: value "" with validity.badInput
    assert page.get_by_label("Weekly cap").evaluate("f => f.validity.badInput") is True
    page.get_by_role("button", name="Set cap").click()
    settle(page)
    assert posts(state) == []


@pytest.mark.parametrize("raw,want", [(".5", 0.5), ("5.", 5), ("87.5", 87.5)])
def test_a_float_accepts_every_number_input_spelling(board, raw, want):
    state, page, open_ = board
    frag = view(
        ui.field("Ratio", name="r", kind="number", id="r"),
        ui.button("Set", data={"post": "/r", "body": {}, "input": "r:float:0:100:required:r"}),
    )
    open_("#overview", {"overview": frag})
    page.get_by_label("Ratio").wait_for()
    settle(page)
    page.evaluate(
        f"(() => {{ const f = document.getElementById('r'); f.type = 'text'; f.value = {raw!r}; }})()"
    )
    page.get_by_role("button", name="Set").click()
    wait_posts(page, state, 1)
    assert posts(state)[0][1] == {"r": want}


def test_a_confirm_button_outside_a_dialog_does_nothing_and_throws_nothing(board):
    state, page, open_ = board
    faults = []
    page.on("pageerror", lambda e: faults.append(str(e)))
    stray = ui.Safe('<button type="button" data-dialog-confirm>Stray</button>')
    open_("#overview", {"overview": view(stray)})
    page.get_by_role("button", name="Stray").click()
    settle(page)
    assert faults == [] and posts(state) == []


def test_a_clamp_under_a_hidden_ancestor_hides_its_toggle_until_measured(board):
    state, page, open_ = board
    frag = view(ui.tabs("Range", [("a", "First", "x"), ("b", "Second", ui.clamp("short"))]))
    open_("#overview", {"overview": frag})
    settle(page)
    assert page.locator("[data-clamp-toggle]").get_attribute("hidden") == ""
    page.get_by_role("tab", name="Second").click()
    assert (
        page.locator("[data-clamp-toggle]").get_attribute("hidden") == ""
    )  # short text: nothing cut


def test_the_window_scroll_is_restored_when_new_content_lands_above(board):
    state, page, open_ = board
    cards = [ui.card(f"Card {i}", "body " * 50) for i in range(60)]
    open_("#overview", {"overview": view(ui.fragment(*cards), stamp="s1")})
    settle(page)
    page.evaluate("window.scrollTo(0, 1500)")
    extra = [ui.card(f"New {i}", "body " * 50) for i in range(10)]
    state.fragments["overview"] = view(ui.fragment(*extra, *cards), stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.evaluate("window.scrollY") == 1500


def test_the_control_of_a_post_in_flight_is_disabled(board):
    state, page, open_ = board
    open_("#overview", {"overview": _slow_post_view()})
    page.route("**/agent-resume", lambda route: None)
    page.get_by_role("button", name="Resume").click()
    page.wait_for_timeout(100)
    assert page.get_by_role("button", name="Resume").is_disabled()


def test_post_itself_refuses_a_second_post_for_the_same_key(board):
    state, page, open_ = board
    body = {"agent": "infra"}
    frag = view(
        ui.button("Resume now", data={"post": "/agent-resume", "body": body}),
        ui.button("Resume", data={"post": "/agent-resume", "body": body, "confirm": "dlg-r"}),
        ui.dialog("dlg-r", "Resume?", "It starts again.", "Resume infra", "Keep paused"),
    )
    open_("#overview", {"overview": frag})
    held = []
    page.route("**/agent-resume", lambda route: held.append(route))
    page.get_by_role("button", name="Resume", exact=True).click()  # opens the dialog
    page.evaluate(
        "[...document.querySelectorAll('[data-post]')].find(b => !b.dataset.confirm).click()"
    )
    page.wait_for_timeout(100)
    page.get_by_role("button", name="Resume infra").click()  # confirm: post() for the same key
    page.wait_for_timeout(200)
    assert len(held) == 1


def test_the_topbar_never_overflows_at_phone_width(board):
    state, page, open_ = board
    page.set_viewport_size({"width": 390, "height": 800})
    open_("#overview", {"overview": view("x")})
    page.evaluate(
        "document.querySelector('.brand').textContent = 'A very long command centre title '.repeat(4);"
        "document.querySelector('[data-theme-toggle]').textContent = 'A very long theme label for another language';"
        "document.querySelector('[data-menu]').textContent = 'A much longer menu label in another language';"
    )
    box = page.evaluate(
        """() => { const bar = document.querySelector('.topbar'), r = bar.getBoundingClientRect();
        return { fits: [...bar.children].every(c => { const b = c.getBoundingClientRect();
                   return b.left >= r.left - 0.5 && b.right <= r.right + 0.5 && b.bottom <= r.bottom + 0.5; }),
                 wide: bar.scrollWidth <= bar.clientWidth }; }"""
    )
    assert box["fits"] and box["wide"]


def test_restoring_focus_never_moves_the_page(board):
    state, page, open_ = board
    cards = [ui.card(f"Card {i}", "body " * 50) for i in range(60)]

    def frag(stamp):
        return view(ui.field("Note", name="n1", id="n1"), ui.fragment(*cards), stamp=stamp)

    open_("#overview", {"overview": frag("s1")})
    settle(page)
    page.get_by_label("Note").focus()
    page.evaluate("window.scrollTo(0, 1500)")
    state.fragments["overview"] = frag("s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.evaluate("document.activeElement.id") == "n1"
    assert page.evaluate("window.scrollY") == 1500


# ---------------------------------------------------------------- review pass 1: filter invariants
def _flags(page) -> list[tuple[bool, bool]]:
    """(hidden, open) of each filter section, in document order (works for id-less sections)."""
    rows = page.eval_on_selector_all(
        "details[data-filter-section]", "ds => ds.map(d => [d.hidden, d.open])"
    )
    return [(h, o) for h, o in rows]


def test_a_stored_filter_key_no_control_names_is_dropped_and_filters_nothing(board):
    state, page, open_ = board
    _open_inv(open_, page)
    stored = {"account": {"v": "zz", "mode": "substr", "chip": False}}
    page.evaluate(f"localStorage.setItem({_FILTER_KEY!r}, {json.dumps(json.dumps(stored))})")
    page.reload()
    settle(page)
    assert page.evaluate(f"localStorage.getItem({_FILTER_KEY!r})") == "{}"
    assert not any(o or h for h, o in _flags(page))
    assert _status(page) == cat.t("filter.shown", n=5, total=5)
    assert _visible_rows(page) == ["alpha", "beta", "gamma", "delta", "eps"]
    assert (_record(page) or []) == []


def test_a_group_the_operator_closes_and_reopens_by_hand_stays_open_on_clear(board):
    state, page, open_ = board
    _open_inv(open_, page)
    two = _SID["Group two"]
    page.get_by_label("Name").fill("gam")
    assert _record(page) == [two]
    page.locator("summary", has_text="Group two").click()  # the operator closes it ...
    settle(page)
    page.locator("summary", has_text="Group two").click()  # ... and opens it again
    settle(page)
    assert _sections(page)[two] == (False, True)
    page.get_by_label("Name").fill("")
    assert _sections(page)[two] == (False, True)
    assert _record(page) == []


def test_sections_sharing_a_summary_are_told_apart_by_id_on_clear(board):
    state, page, open_ = board
    open_("#overview", {"overview": _inv_view(same_summary=True)})
    settle(page)
    one, two, three = (_SID[k] for k in _INV)
    page.locator("summary").nth(0).click()  # by hand
    page.get_by_label("Name").fill("a")
    assert _sections(page) == {one: (False, True), two: (False, True), three: (True, False)}
    assert _record(page) == [two]  # the hand-opened twin is not the filter's
    state.fragments["overview"] = _inv_view(stamp="s2", same_summary=True)
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    page.get_by_label("Name").fill("")
    assert _sections(page) == {one: (False, True), two: (False, False), three: (False, False)}
    assert _record(page) == []


def test_a_hand_toggle_of_one_twin_leaves_the_other_filter_opened_twin_recorded(board):
    state, page, open_ = board
    open_("#overview", {"overview": _inv_view(same_summary=True)})
    settle(page)
    one, two, three = (_SID[k] for k in _INV)
    page.get_by_label("Name").fill("a")
    assert _record(page) == [one, two]
    page.locator("summary").nth(0).click()  # the operator closes the first
    settle(page)
    assert _record(page) == [two]
    page.get_by_label("Name").fill("")
    assert _sections(page) == {one: (False, False), two: (False, False), three: (False, False)}
    assert _record(page) == []


def test_an_unoffered_stored_select_value_resets_to_all_and_a_picked_one_survives_a_swap(board):
    state, page, open_ = board
    open_("#overview", {"overview": _inv_view()})
    settle(page)
    page.select_option("#cost-sel", "free")
    assert _visible_rows(page) == ["alpha", "delta"]
    state.fragments["overview"] = _inv_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.locator("#cost-sel").input_value() == "free"
    page.select_option("#cost-sel", "")  # "all" is always there to return to
    assert _visible_rows(page) == ["alpha", "beta", "gamma", "delta", "eps"]
    stored = json.loads(page.evaluate(f"localStorage.getItem({_FILTER_KEY!r})"))
    assert stored.get("cost", {}).get("v", "") == ""


def test_a_stale_stored_record_never_outranks_the_pages_own_when_storage_cannot_write(board):
    state, page, open_ = board
    page.add_init_script(
        "window.__block = false; const set = Storage.prototype.setItem;"
        "Storage.prototype.setItem = function (k, v) {"
        " if (window.__block) { throw new Error('quota'); } return set.call(this, k, v); };"
    )
    _open_inv(open_, page)
    one, two, three = (_SID[k] for k in _INV)
    page.get_by_label("Name").fill("gam")
    page.evaluate("window.__block = true")
    page.get_by_label("Name").fill("eps")
    assert _sections(page)[three] == (False, True)
    state.fragments["overview"] = _inv_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    page.get_by_label("Name").fill("")
    assert _sections(page) == {one: (False, False), two: (False, False), three: (False, False)}


def test_saved_filters_survive_a_render_of_the_group_that_has_no_controls(board):
    state, page, open_ = board
    open_("#overview", {"overview": _inv_view(bar=False)})
    settle(page)
    stored = {"name": {"v": "gam", "mode": "substr", "chip": False}}
    page.evaluate(f"localStorage.setItem({_FILTER_KEY!r}, {json.dumps(json.dumps(stored))})")
    page.reload()  # the bar-less render: nothing there can show or clear the saved filter
    settle(page)
    assert not any(o or h for h, o in _flags(page))  # and it filters nothing
    assert _status(page) == cat.t("filter.shown", n=5, total=5)
    state.fragments["overview"] = _inv_view(stamp="s2")  # the bar is back
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.get_by_label("Name").input_value() == "gam"
    assert _visible_rows(page) == ["gamma"]


def _pick_view(default, stamp):
    sel = ui.select(
        "Pick", name="pick", id="pick", options=[("a", "A"), ("b", "B"), ("c", "C")], value=default
    )
    return view(sel, stamp=stamp)


def test_a_swap_keeps_a_select_the_operator_changed_and_takes_the_new_default_of_one_they_did_not(
    board,
):
    state, page, open_ = board
    open_("#overview", {"overview": _pick_view("b", "s1")})
    settle(page)
    state.fragments["overview"] = _pick_view("c", "s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.locator("#pick").input_value() == "c"  # untouched: the server's new default shows
    page.select_option("#pick", "a")
    page.locator("#pick").blur()
    state.fragments["overview"] = _pick_view("c", "s3")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    assert page.locator("#pick").input_value() == "a"  # changed by the operator: carried


def test_with_storage_blocked_a_swap_closes_the_groups_the_lost_filter_had_opened(board):
    state, page, open_ = board
    page.add_init_script(
        "Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }});"
    )
    _open_inv(open_, page)
    two = _SID["Group two"]
    page.get_by_label("Name").fill("gam")
    assert _sections(page)[two] == (False, True)
    state.fragments["overview"] = _inv_view(stamp="s2")
    page.evaluate("window.qdRefresh(true)")
    settle(page)
    # nothing persisted the filter, so the swap clears it; what it had opened must close with it
    assert page.get_by_label("Name").input_value() == ""
    assert _sections(page)[two] == (False, False)


def test_the_filter_survives_a_reload_and_clearing_it_then_closes_what_it_opened(board):
    state, page, open_ = board
    _open_inv(open_, page)
    one, two, three = (_SID[k] for k in _INV)
    page.get_by_label("Name").fill("gam")
    page.reload()
    settle(page)
    assert _sections(page) == {one: (True, False), two: (False, True), three: (True, False)}
    page.get_by_label("Name").fill("")
    assert _sections(page) == {one: (False, False), two: (False, False), three: (False, False)}
    assert _record(page) == []


@pytest.mark.parametrize("stored", ['{"a":1}', "[1,2]", '"x"', "not json", '[["a"]]'])
def test_a_corrupt_opened_group_record_with_no_filter_is_stored_empty_after_load(board, stored):
    state, page, open_ = board
    _open_inv(open_, page)
    page.evaluate(f"localStorage.setItem({_OPEN_KEY!r}, {json.dumps(stored)})")
    page.reload()
    settle(page)
    assert page.evaluate(f"localStorage.getItem({_OPEN_KEY!r})") == "[]"
    assert page.evaluate(f"localStorage.getItem({_FILTER_KEY!r})") is None


def _nested_view():
    def sec(title, names, key):
        sid = ui.slug(title, "nz")
        tbl = ui.table(
            "t-" + sid,
            title,
            ["Name"],
            [[n] for n in names],
            row_data=[{"filter-item": "", key: n} for n in names],
        )
        count = ui.group("", tag="span", data={"filter-count": ""})
        dis = ui.disclosure(
            ui.fragment(title, " ", count), tbl, id=sid, data={"filter-section": ""}
        )
        return dis, sid

    outer_sec, osid = sec("Outer sec", ["alpha", "beta"], "f-name")
    inner_sec, isid = sec("Inner sec", ["gamma", "delta"], "f-tag")
    inner = ui.group(
        ui.fragment(
            ui.field("Tag", name="tag-box", kind="search", id="tag-box", data={"filter": "tag"}),
            ui.status_text("", data={"filter-status": ""}),
            inner_sec,
        ),
        data={"filter-group": "inner"},
    )
    outer = ui.group(
        ui.fragment(
            ui.field(
                "Name", name="name-box", kind="search", id="name-box", data={"filter": "name"}
            ),
            ui.status_text("", data={"filter-status": ""}),
            outer_sec,
            inner,
        ),
        data={"filter-group": "outer"},
    )
    return view(outer), osid, isid


def test_a_nested_filter_group_keeps_its_own_counts_sections_and_record(board):
    state, page, open_ = board
    html, osid, isid = _nested_view()
    open_("#overview", {"overview": html})
    settle(page)
    assert page.locator("[data-filter-status]").all_text_contents() == [
        cat.t("filter.shown", n=2, total=2),
        cat.t("filter.shown", n=2, total=2),
    ]
    page.get_by_label("Name").fill("alp")
    assert page.locator("[data-filter-status]").all_text_contents() == [
        cat.t("filter.shown", n=1, total=2),
        cat.t("filter.shown", n=2, total=2),
    ]
    assert _sections(page) == {osid: (False, True), isid: (False, False)}
    assert json.loads(page.evaluate("localStorage.getItem('qd-filter-open:outer')")) == [osid]
    assert page.evaluate("localStorage.getItem('qd-filter-open:inner')") is None
    page.get_by_label("Tag").fill("gam")
    assert page.locator("[data-filter-status]").all_text_contents() == [
        cat.t("filter.shown", n=1, total=2),
        cat.t("filter.shown", n=1, total=2),
    ]
    assert json.loads(page.evaluate("localStorage.getItem('qd-filter-open:inner')")) == [isid]
