"""T01 — `app.js`'s behaviours, driven in a real browser over a fixture page.

A stdlib `http.server` on port 0 serves the package's `static/` files, a page built by
`components.shell`, fixture view fragments built by the same components, and records every POST.
Each test asserts what the operator sees or what reaches the server — roles, text, attributes, request
bodies — never a class string or a pixel (`.windsurf/rules/core/45-testing-strategy.md:21`).
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

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
        self.post_status = 200

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
            if path == "/":
                self._send(200, ui.shell(VIEWS, "overview").encode(), "text/html; charset=utf-8")
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
                code = state.post_status
            self._send(
                code, json.dumps({"ok": code == 200, "error": "boom"}).encode(), "application/json"
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
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def board(server, browser):
    state, base = server
    with state.lock:
        state.fragments.clear()
        state.gets.clear()
        state.posts.clear()
        state.post_status = 200
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
