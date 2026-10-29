"""T07 — the wired board in a real browser (plan 2026-10-17-plan-1, ticket T07; spec § Validation).

The dashboard's own `_Handler` runs in-process on port 0 over FIXTURE stores — real git repos with
real work stores under the /opt seam (tests/conftest.py pins FABRIK_OPT_DIR per test), real run
records under COMMAND_RUN_DIR, and a quota payload set by hand: the probe is stubbed to fail loudly
if anything calls it, so nothing here reaches the fleet, ~/.claude* or the network. A verdict the
browser sends runs the hub's real `work.py` against the fixture store.

Each test asserts what the operator sees or what lands in the store — roles, names, text, focus,
geometry of the page itself — never a class string (`.windsurf/rules/core/45-testing-strategy.md:21`).
playwright 1.61.0 with chromium-1228 is in the hub `.venv`; pytest-playwright is not, so the browser
is launched here with `sync_playwright`.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.quota_dashboard_isolation import (  # noqa: E402, F401
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse network guard
)

sync_api = pytest.importorskip("playwright.sync_api")

from tests import test_quota_dashboard as base  # noqa: E402 — the stores, the loader, the payload

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "sysadmin"))

from dashboard_ui.strings import t  # noqa: E402

LONG_QUESTION = (
    "Ship the redesigned board to the operator today? It replaces the five tabs with six views, keeps "
    "every collector and endpoint, and moves the agents table onto the Overview. "
) * 4
DESKTOP = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}
ZOOMED = {"width": 720, "height": 450}  # a 1440 x 900 window at 200 % zoom: the same CSS viewport


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except sync_api.Error as exc:  # the package without its Chromium binary
            pytest.skip(f"Chromium cannot launch: {str(exc).splitlines()[0]}")
        yield b
        b.close()


def _decision(repo: Path, title: str, question: str, age_h: float) -> str:
    """A real item turned into a decision waiting on the operator."""
    item = base._store_item(repo, title)
    path = repo / ".fabrik" / "work" / f"{item}.json"
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_h * 3600))
    path.write_text(json.dumps({**json.loads(path.read_text()), "status": "awaiting-operator",
                                "kind": "decision", "question": question, "ground": "gate",
                                "creator": "infra", "created": created}))  # fmt: skip
    return item


class Board:
    def __init__(self, qd, url: str, repos: dict[str, Path], items: dict[str, str]):
        self.qd, self.url, self.repos, self.items = qd, url, repos, items

    def awaiting(self) -> dict[str, int]:
        """The decisions waiting per repo, read straight off the stores — never off the page."""
        out = {}
        for name, repo in self.repos.items():
            n = 0
            for f in (repo / ".fabrik" / "work").glob("W-*.json"):
                if json.loads(f.read_text()).get("status") == "awaiting-operator":
                    n += 1
            out[name] = n
        return out

    def item(self, repo: str, item: str) -> dict:
        return base._item(self.repos[repo], item)


@pytest.fixture
def board(tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "0")
    fabrik = base._store_repo("fabrik")
    shop = base._store_repo("shop")
    items = {
        "first": _decision(fabrik, "ship the board", LONG_QUESTION, age_h=5),
        "second": _decision(fabrik, "drop the old page", "Drop the old Repos page now?", age_h=1),
        "shop": _decision(shop, "price change", "Raise the price?", age_h=2),
    }
    task = base._store_item(fabrik, "tidy the doc")
    path = fabrik / ".fabrik" / "work" / f"{task}.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "owner": "infra"}))
    items["task"] = task
    base._run_record(
        "s1", agent="infra", state="running", command="fabrik-task", repo_root=str(fabrik)
    )
    qd = base._load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    monkeypatch.setattr(qd, "_probe", lambda: (_ for _ in ()).throw(AssertionError("no probe")))
    qd._set_last_status(time.time(), base._payload())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), qd._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield Board(
            qd,
            f"http://127.0.0.1:{httpd.server_address[1]}",
            {"fabrik": fabrik, "shop": shop},
            items,
        )
    finally:
        httpd.shutdown()
        httpd.server_close()


def _open(browser, board: Board, viewport: dict, hash_: str = "", **ctx):
    context = browser.new_context(viewport=viewport, **ctx)
    page = context.new_page()
    page.goto(board.url + "/" + hash_)
    view = hash_.split("/")[0].lstrip("#") or "overview"
    page.wait_for_selector(
        f'[data-view-root="{view if view in board.qd._views.VIEWS else "overview"}"]'
    )
    return context, page


def _active(page) -> dict:
    return page.evaluate(
        "() => { const a = document.activeElement; return { tag: a.tagName, text: (a.textContent || '').trim(),"
        " body: a.getAttribute('data-body'), inDialog: !!a.closest('dialog'), id: a.id }; }"
    )


def _first_card(page):
    group = page.locator("#ov-decisions details[open]").first
    return group.locator("article").first


# ---------------------------------------------------------------- the first screen and its counts
@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["1440", "390"])
def test_the_summary_strip_then_needs_you_sit_in_the_first_screen(browser, board, viewport):
    context, page = _open(browser, board, viewport)
    try:
        strip = page.locator("#ov-summary").bounding_box()
        needs = page.locator("#ov-decisions").bounding_box()
        assert strip is not None and needs is not None
        assert strip["y"] < needs["y"] < viewport["height"], (strip, needs)
        # the strip's counts are the stores' counts
        words = page.locator("#ov-summary").inner_text()
        for repo, n in board.awaiting().items():
            assert f"{repo}: {n} waiting" in words, (repo, n, words)
        # and the hub's group is first and the only one expanded
        groups = page.locator("#ov-decisions details")
        assert groups.count() == 2
        assert (
            groups.nth(0).get_attribute("open") is not None
            and groups.nth(1).get_attribute("open") is None
        )
        assert groups.nth(0).locator("summary").inner_text().startswith("fabrik")
    finally:
        context.close()


@pytest.mark.parametrize("viewport", [PHONE, ZOOMED], ids=["390", "1440-at-200pct"])
def test_no_view_scrolls_the_page_sideways(browser, board, viewport):
    context, page = _open(browser, board, viewport)
    try:
        for view in board.qd._views.VIEWS:
            page.goto(board.url + "/#" + view)
            page.wait_for_selector(f'[data-view-root="{view}"]')
            over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            assert over <= 0, (view, over)
    finally:
        context.close()


LONG_ERROR = (
    "CalledProcessError: Command '/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/"
    "dispatch_headroom.py --units 1 --json' returned non-zero exit status 1 after reading "
    "/home/someone/.claude/state/command-runs/0123456789abcdef0123456789abcdef.json"
)


@pytest.mark.parametrize("viewport", [PHONE, ZOOMED], ids=["390", "1440-at-200pct"])
def test_a_long_data_badge_wraps_instead_of_scrolling_the_page(
    browser, board, monkeypatch, viewport
):
    """A badge carries DATA as well as labels — a collector's error, a path — and a long one on one
    line pushed the Overview sideways at 390 px. It wraps; the page never scrolls sideways."""
    monkeypatch.setattr(board.qd, "_budget_data", lambda: {"error": LONG_ERROR})
    context, page = _open(browser, board, viewport)
    try:
        assert LONG_ERROR[:40] in page.locator("#ov-health").inner_text()
        over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert over <= 0, over
    finally:
        context.close()


_SQUEEZED = """() => Array.from(document.querySelectorAll('.badge-text')).filter((el) => {
  const text = (el.textContent || '').trim();
  if (!text || text.length >= 40 || el.getClientRects().length === 0) { return false; }
  const cs = getComputedStyle(el);
  const line = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.5;
  return el.getBoundingClientRect().height > line * 1.5;
}).map((el) => el.textContent.trim())"""


@pytest.mark.parametrize("viewport", [PHONE, ZOOMED, DESKTOP], ids=["390", "720", "1440"])
def test_a_short_badge_stays_on_one_line_in_every_view(browser, board, viewport):
    """Letting a badge wrap must not let a table or a flex row squeeze a SHORT one to a letter a
    line ("Warning: awaiting-operator" at 44 x 338 px): every badge under 40 characters is one line
    high, in every view, at every width."""
    context, page = _open(browser, board, viewport)
    try:
        for view in board.qd._views.VIEWS:
            page.goto(board.url + "/#" + view)
            page.wait_for_selector(f'[data-view-root="{view}"]')
            for d in page.locator("details").all():  # the closed sections' badges count too
                page.evaluate("(el) => { el.open = true; }", d.element_handle())
            assert page.evaluate(_SQUEEZED) == [], view
    finally:
        context.close()


# ---------------------------------------------------------------- the keyboard
def test_from_the_skip_link_tab_reaches_the_first_action_of_the_first_card(browser, board):
    context, page = _open(browser, board, DESKTOP)
    try:
        page.keyboard.press("Tab")
        assert _active(page)["text"] == t("shell.skip")  # the skip link is the first stop
        page.keyboard.press("Enter")
        assert _active(page)["id"] == "view"  # it lands in <main>
        first_accept = json.loads(
            _first_card(page)
            .get_by_role("button", name=t("ov.dec.accept"))
            .get_attribute("data-body")
        )
        for _presses in range(1, 30):
            page.keyboard.press("Tab")
            a = _active(page)
            if a["body"] and json.loads(a["body"]).get("action") in ("accept", "reject", "comment"):
                break
        assert json.loads(a["body"]) == first_accept, (
            _presses,
            a,
        )  # no other card's action came first
        assert (
            first_accept["item"] == board.items["first"]
        )  # the oldest gate item leads the hub's group
    finally:
        context.close()


def _to_first_card_toggle(page) -> None:
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    toggle = _first_card(page).locator("[data-clamp-toggle]")
    for _ in range(30):
        page.keyboard.press("Tab")
        if page.evaluate("(el) => el === document.activeElement", toggle.element_handle()):
            return
    raise AssertionError("the first card's Show all is not in the Tab order")


def test_the_primary_loop_completes_by_keyboard_alone_in_four_steps(browser, board):
    """Open, read, Accept, confirm — each a keyboard act on the first card, no pointer:
    1 open: Enter on "Show all" expands the clamped question; 2 read: the whole question shows;
    3 Accept: Tab, Enter opens the confirm dialog, which restates the question;
    4 confirm: Tab past the optional note and Keep waiting, Enter on "Accept <id>"."""
    context, page = _open(browser, board, DESKTOP)
    try:
        _to_first_card_toggle(page)
        card = _first_card(page)
        page.keyboard.press("Enter")  # 1 open
        assert card.locator("[data-clamp-toggle]").get_attribute("aria-expanded") == "true"
        assert card.locator(".clamp-text").inner_text().strip() == LONG_QUESTION.strip()  # 2 read
        page.keyboard.press("Tab")
        assert _active(page)["text"] == t("ov.dec.accept")
        page.keyboard.press("Enter")  # 3 Accept
        dialog = page.locator("dialog[open]")
        assert dialog.count() == 1 and LONG_QUESTION.strip()[:80] in dialog.inner_text()
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        assert _active(page)["text"] == t("ov.dec.accept_confirm", id=board.items["first"])
        page.keyboard.press("Enter")  # 4 confirm
        for _ in range(100):
            if board.item("fabrik", board.items["first"]).get("status") != "awaiting-operator":
                break
            page.wait_for_timeout(50)
        item = board.item("fabrik", board.items["first"])
        assert item["status"] != "awaiting-operator", item
        assert (
            item["comments"][-1]["action"] == "accept"
            and item["comments"][-1]["via"] == "dashboard"
        )
        page.wait_for_function("() => document.querySelector('[data-live]').textContent.length > 0")
        assert page.locator("[data-live]").inner_text() == t("act.done")
    finally:
        context.close()


def test_the_dialog_traps_focus_and_returns_it_to_its_invoker(browser, board):
    context, page = _open(browser, board, DESKTOP)
    try:
        accept = _first_card(page).get_by_role("button", name=t("ov.dec.accept"))
        accept.focus()
        page.keyboard.press("Enter")
        assert page.locator("dialog[open]").count() == 1
        for _ in range(8):  # the dialog has three stops: the note, Keep waiting, Accept <id>
            page.keyboard.press("Tab")
            assert _active(page)["inDialog"], _active(page)
        for _ in range(4):
            page.keyboard.press("Shift+Tab")
            assert _active(page)["inDialog"], _active(page)
        page.keyboard.press("Escape")
        assert page.locator("dialog[open]").count() == 0
        assert page.evaluate("(el) => el === document.activeElement", accept.element_handle())
        assert (
            board.item("fabrik", board.items["first"])["status"] == "awaiting-operator"
        )  # nothing sent
    finally:
        context.close()


# ---------------------------------------------------------------- refresh never clobbers the operator
def _stamp(page) -> str:
    return page.locator("[data-view-root]").first.get_attribute("data-stamp")


def test_a_half_typed_comment_and_an_open_dialog_survive_a_refresh_tick(browser, board):
    context, page = _open(browser, board, DESKTOP)
    try:
        card = _first_card(page)
        field = card.get_by_role("textbox")
        field.fill("half a thought")
        card.get_by_role("button", name=t("ov.dec.accept")).focus()  # off the field: the tick runs
        before = _stamp(page)
        # the stores move under the page (an agent comments on the second card): a new stamp
        token = board.qd._snapshot.token(board.item("fabrik", board.items["second"]))
        assert (
            board.qd.item_verdict(
                "fabrik", board.items["second"], "comment", "agent note", token=token
            )[0]
            == 200
        )
        page.evaluate("() => window.qdRefresh(false)")
        page.wait_for_function(
            "(s) => document.querySelector('[data-view-root]').getAttribute('data-stamp') !== s",
            arg=before,
        )
        assert _first_card(page).get_by_role("textbox").input_value() == "half a thought"
        # an open dialog holds the tick, and focus goes back to its invoker on close
        accept = _first_card(page).get_by_role("button", name=t("ov.dec.accept"))
        accept.focus()
        page.keyboard.press("Enter")
        assert page.locator("dialog[open]").count() == 1
        held = _stamp(page)
        token = board.qd._snapshot.token(board.item("fabrik", board.items["second"]))
        board.qd.item_verdict("fabrik", board.items["second"], "comment", "another", token=token)
        page.evaluate("() => window.qdRefresh(false)")
        page.wait_for_timeout(300)
        assert page.locator("dialog[open]").count() == 1 and _stamp(page) == held
        page.keyboard.press("Escape")
        assert page.evaluate("(el) => el === document.activeElement", accept.element_handle())
    finally:
        context.close()


def test_a_view_that_lands_while_a_dialog_is_open_waits_for_it_to_close(browser, board):
    """INV-5, the race the skip cannot see: a refresh fetch already in flight when the operator opens
    a dialog must not swap the view under it — the dialog's invoker and the text being typed live in
    that markup. The response waits; the view refreshes once the dialog closes."""
    context, page = _open(browser, board, DESKTOP)
    held: list = []
    try:
        before = _stamp(page)
        page.route("**/v/overview", lambda route: held.append(route))
        token = board.qd._snapshot.token(board.item("fabrik", board.items["second"]))
        assert (
            board.qd.item_verdict("fabrik", board.items["second"], "comment", "moved", token=token)[
                0
            ]
            == 200
        )
        page.evaluate("() => window.qdRefresh(false)")  # the tick's fetch goes out ...
        for _ in range(100):
            if held:
                break
            page.wait_for_timeout(20)
        assert held, "the refresh fetch was not issued"
        _first_card(page).get_by_role("button", name=t("ov.dec.accept")).focus()
        page.keyboard.press("Enter")  # ... the operator opens a dialog ...
        assert page.locator("dialog[open]").count() == 1
        held[0].continue_()  # ... and the response lands now
        page.unroute("**/v/overview")
        page.wait_for_timeout(400)
        assert page.locator("dialog[open]").count() == 1 and _stamp(page) == before
        page.keyboard.press("Escape")
        page.wait_for_function(
            "(s) => document.querySelector('[data-view-root]').getAttribute('data-stamp') !== s",
            arg=before,
        )
    finally:
        context.close()


def test_a_hash_naming_an_object_prototype_member_is_not_a_view(browser, board):
    """`known[view]` read `Object.prototype`: `#constructor` fetched `/v/constructor`."""
    context = browser.new_context(viewport=DESKTOP)
    page = context.new_page()
    fetched: list[str] = []
    page.on("request", lambda r: fetched.append(r.url) if "/v/" in r.url else None)
    try:
        page.goto(board.url + "/#constructor")
        page.wait_for_selector('[data-view-root="overview"]')
        for name in ("toString", "__proto__", "hasOwnProperty"):
            page.evaluate("(h) => { location.hash = h; }", name)
            page.wait_for_timeout(150)
        assert all(u.endswith("/v/overview") for u in fetched), fetched
    finally:
        context.close()


def test_a_409_announces_the_changed_item_and_reloads_the_view(browser, board):
    context, page = _open(browser, board, DESKTOP)
    try:
        # the item changes after the page drew its card: the card's snapshot token is now stale
        token = board.qd._snapshot.token(board.item("fabrik", board.items["first"]))
        assert (
            board.qd.item_verdict(
                "fabrik", board.items["first"], "comment", "moved on", token=token
            )[0]
            == 200
        )
        accept = _first_card(page).get_by_role("button", name=t("ov.dec.accept"))
        accept.focus()
        page.keyboard.press("Enter")
        page.locator("dialog[open] [data-dialog-confirm]").click()
        page.wait_for_function(
            "(w) => document.querySelector('[data-live]').textContent === w", arg=t("act.changed")
        )
        assert (
            board.item("fabrik", board.items["first"])["status"] == "awaiting-operator"
        )  # refused
    finally:
        context.close()


# ---------------------------------------------------------------- theme and the URL
def test_the_theme_holds_across_a_reload_with_no_flash(browser, board):
    context = browser.new_context(viewport=DESKTOP)
    # record the theme the page has at the moment its stylesheet is inserted — before first paint
    context.add_init_script(
        "new MutationObserver((ms, o) => { for (const m of ms) for (const n of m.addedNodes) {"
        " if (n.tagName === 'LINK' && n.rel === 'stylesheet') { window.__themeAtCss ="
        " document.documentElement.getAttribute('data-theme'); o.disconnect(); } } })"
        ".observe(document, { childList: true, subtree: true });"
    )
    page = context.new_page()
    try:
        page.goto(board.url + "/")
        toggle = page.locator("[data-theme-toggle]")
        while toggle.inner_text() != t("shell.theme.dark"):
            toggle.click()
        page.reload()
        page.wait_for_selector('[data-view-root="overview"]')
        assert page.evaluate("() => window.__themeAtCss") == "dark"
        assert page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
        assert toggle.inner_text() == t("shell.theme.dark")
    finally:
        context.close()


def test_a_reload_on_a_summary_anchor_opens_the_overview_and_keeps_refreshing(browser, board):
    """The routed P1-A-P1: the summary strip links `#ov-merges` and its siblings; a reload on one of
    those names no view, and `app.js` used to stop there — a blank page that never refreshed."""
    context = browser.new_context(viewport=DESKTOP)
    page = context.new_page()
    fetched: list[str] = []
    page.on("request", lambda r: fetched.append(r.url) if "/v/overview" in r.url else None)
    page.clock.install()
    try:
        page.goto(board.url + "/#ov-merges")
        page.wait_for_selector('[data-view-root="overview"]')
        assert (
            page.evaluate("() => document.querySelector('main').getAttribute('data-view')")
            == "overview"
        )
        n = len(fetched)
        page.clock.run_for(21_000)  # past the Overview's 20 s cadence
        page.wait_for_timeout(200)
        assert len(fetched) > n, "the refresh tick never scheduled"
    finally:
        context.close()


def test_the_owner_chips_filter_the_work_view_and_the_choice_survives_a_reload(browser, board):
    context, page = _open(browser, board, DESKTOP, "#work/fabrik")
    try:
        pane = page.locator('[data-pick="fabrik"]')
        pane.get_by_role("button", name="infra 1").click()
        sections = pane.locator("details[data-f-owner]")
        shown = [
            s.locator("summary").inner_text().split(" (")[0]
            for s in sections.all()
            if s.is_visible()
        ]
        assert shown == ["infra"], shown
        page.reload()
        page.wait_for_selector('[data-view-root="work"]')
        sections = page.locator('[data-pick="fabrik"] details[data-f-owner]')
        shown = [
            s.locator("summary").inner_text().split(" (")[0]
            for s in sections.all()
            if s.is_visible()
        ]
        assert shown == ["infra"], shown
    finally:
        context.close()


# ---------------------------------------------------------------- the external-services inventory (plan 2026-10-18-plan-1, T04)
# The Services view at census scale: the isolation's stub answers the 466-row fixture, so the section
# is the real one at the real size. `window.qdRefresh(true)` is the forced swap.
LAPTOP = {"width": 1280, "height": 900}
SMALL = {"width": 375, "height": 800}
_AXE_SCS = {"wcag131", "wcag141", "wcag143", "wcag1411", "wcag211", "wcag332", "wcag413"}
_GROUP = '[data-filter-group="inventory"]'
_VISIBLE_ROWS = (
    "() => Array.from(document.querySelectorAll('[data-filter-group=\"inventory\"] [data-filter-item]'))"
    ".filter((r) => !r.hidden).map((r) => ({find: r.dataset.fFind, cost: r.dataset.fCost,"
    " status: r.dataset.fStatus}))"
)
_SECTIONS = (
    "() => Array.from(document.querySelectorAll('[data-filter-group=\"inventory\"] [data-filter-section]'))"
    ".map((s) => ({title: s.querySelector('summary').textContent.split(' · ')[0], open: s.open,"
    " hidden: s.hidden, count: (s.querySelector('[data-filter-count]') || {}).textContent}))"
)


def _inventory_page(browser, board, viewport, **ctx):
    context, page = _open(browser, board, viewport, "#services", **ctx)
    page.wait_for_selector(_GROUP)
    return context, page


def _status(page) -> str:
    return page.locator(_GROUP + " [data-filter-status]").inner_text()


def _sideways(page) -> int:
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def _attention(page):
    return page.locator(
        "article", has=page.locator("h3", has_text=t("services.inv.attn.title"))
    ).last


def _by_title(sections: list[dict]) -> dict[str, dict]:
    return {s["title"]: s for s in sections}


@pytest.mark.parametrize("viewport", [LAPTOP, SMALL], ids=["1280", "375"])
def test_the_inventory_filter_opens_hides_counts_survives_a_swap_and_clears(
    browser, board, viewport
):
    context, page = _inventory_page(browser, board, viewport)
    try:
        total = 466
        assert _status(page) == t("filter.shown", n=total, total=total)
        assert not [s for s in page.evaluate(_SECTIONS) if s["open"] or s["hidden"]]
        attention = _attention(page).inner_html()
        # a group opened BY HAND before any filter
        page.locator("details[data-filter-section] > summary", has_text="cat-00 ·").click()
        assert _by_title(page.evaluate(_SECTIONS))["cat-00"]["open"]

        # typing a provider name: the groups holding the match open, the rest hide, the count updates
        page.locator("#inventory-find").fill("real-03")
        page.wait_for_function("(s) => document.querySelector('[data-filter-status]').textContent === s",
                               arg=t("filter.shown", n=10, total=total))  # fmt: skip
        sections = _by_title(page.evaluate(_SECTIONS))
        assert [k for k, s in sections.items() if not s["hidden"]] == ["cat-02", "cat-03"]
        assert sections["cat-02"]["open"] and sections["cat-03"]["open"]
        assert sections["cat-02"]["count"] == t("filter.group_count", n=6, total=6)
        assert sections["cat-03"]["count"] == t("filter.group_count", n=4, total=6)
        assert (
            sections["cat-00"]["hidden"] and sections["cat-00"]["open"]
        )  # hidden, still the operator's
        assert (
            _attention(page).inner_html() == attention
        )  # the filter never narrows Needs attention
        assert _sideways(page) <= 0

        # clearing closes what the filter opened, returns the hidden groups, keeps the hand-opened one
        page.locator("#inventory-find").fill("")
        page.wait_for_function("(s) => document.querySelector('[data-filter-status]').textContent === s",
                               arg=t("filter.shown", n=total, total=total))  # fmt: skip
        sections = _by_title(page.evaluate(_SECTIONS))
        assert not [k for k, s in sections.items() if s["hidden"]]
        assert [k for k, s in sections.items() if s["open"]] == ["cat-00"]
        assert page.evaluate("() => localStorage.getItem('qd-filter-open:inventory')") == "[]"

        # each select, one at a time: the shown rows are exactly the rows carrying the token
        for name in ("cost", "status"):
            for value in page.evaluate(
                "(n) => Array.from(document.querySelectorAll('#inventory-' + n + ' option'))"
                ".map((o) => o.value).filter((v) => v !== '')", name):  # fmt: skip
                page.locator("#inventory-" + name).select_option(value)
                want = page.evaluate(
                    "([n, v]) => Array.from(document.querySelectorAll('[data-filter-item]'))"
                    ".filter((r) => r.dataset['f' + n[0].toUpperCase() + n.slice(1)] === v).length",
                    [name, value],
                )
                page.wait_for_function("(s) => document.querySelector('[data-filter-status]').textContent === s",
                                       arg=t("filter.shown", n=want, total=total))  # fmt: skip
                rows = page.evaluate(_VISIBLE_ROWS)
                assert len(rows) == want and {r[name] for r in rows} == ({value} if want else set())
                if (name, value) == ("cost", "free"):
                    assert want == 19 and not [r for r in rows if r["cost"] == "freemium"]
                assert _attention(page).inner_html() == attention
            page.locator("#inventory-" + name).select_option("")

        # a forced swap with the filter on: values, the open record and the filtering survive
        page.locator("#inventory-find").fill("real-04")
        page.locator("#inventory-status").select_option("active")
        page.wait_for_function("(s) => document.querySelector('[data-filter-status]').textContent === s",
                               arg=t("filter.shown", n=10, total=total))  # fmt: skip
        before = {
            "find": page.locator("#inventory-find").input_value(),
            "status": page.locator("#inventory-status").input_value(),
            "record": page.evaluate("() => localStorage.getItem('qd-filter-open:inventory')"),
            "rows": page.evaluate(_VISIBLE_ROWS),
            "sections": page.evaluate(_SECTIONS),
        }
        assert before["record"] not in (None, "[]")
        page.evaluate(
            "() => { document.querySelector('[data-view-root]').__old = true; window.qdRefresh(true); }"
        )
        page.wait_for_function("() => !document.querySelector('[data-view-root]').__old")
        page.wait_for_selector(_GROUP)
        assert page.locator("#inventory-find").input_value() == before["find"]
        assert page.locator("#inventory-status").input_value() == before["status"]
        assert (
            page.evaluate("() => localStorage.getItem('qd-filter-open:inventory')")
            == before["record"]
        )
        assert page.evaluate(_VISIBLE_ROWS) == before["rows"]
        assert page.evaluate(_SECTIONS) == before["sections"]
        assert _status(page) == t("filter.shown", n=10, total=total)
        assert _attention(page).inner_html() == attention
        assert _sideways(page) <= 0

        # clearing after the swap still closes what the filter opened and keeps the hand-opened group
        page.locator("#inventory-find").fill("")
        page.locator("#inventory-status").select_option("")
        page.wait_for_function("(s) => document.querySelector('[data-filter-status]').textContent === s",
                               arg=t("filter.shown", n=total, total=total))  # fmt: skip
        sections = _by_title(page.evaluate(_SECTIONS))
        assert [k for k, s in sections.items() if s["open"]] == ["cat-00"]
        assert not [k for k, s in sections.items() if s["hidden"]]
        assert _sideways(page) <= 0
    finally:
        context.close()


def _static_file(tmp_path, monkeypatch) -> Path:
    """The file gen_dashboard writes from the census fixture — through its own `main`, registry faked."""
    import importlib.util

    from tests.external_services_fixture import CENSUS_NOW, census_rows

    spec = importlib.util.spec_from_file_location(
        "gen_dashboard_t04", _ROOT / "scripts" / "gen_dashboard.py"
    )
    gd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gd)
    monkeypatch.setattr(gd, "_read", lambda: (census_rows(), CENSUS_NOW - 3600))
    out = tmp_path / "external-services-dashboard.html"
    assert gd.main([str(out)]) == 0
    return out


_CARD_HEIGHT = (
    "() => { const g = document.querySelector('[data-filter-group=\"inventory\"]');"
    " const card = g ? g.closest('article') : document.querySelector('main article');"
    " return card.getBoundingClientRect().height; }"
)


@pytest.mark.parametrize("viewport", [LAPTOP, SMALL], ids=["1280", "375"])
def test_the_collapsed_inventory_section_is_at_most_4000px_tall_live_and_static(
    browser, board, tmp_path, monkeypatch, viewport
):
    context, page = _inventory_page(browser, board, viewport)
    try:
        live = page.evaluate(_CARD_HEIGHT)
        assert 0 < live <= 4000, live
        assert _sideways(page) <= 0
    finally:
        context.close()
    static = _static_file(tmp_path, monkeypatch)
    context = browser.new_context(viewport=viewport)
    page = context.new_page()
    try:
        page.goto(static.as_uri())
        assert 0 < page.evaluate(_CARD_HEIGHT) <= 4000
        assert _sideways(page) <= 0  # the tables scroll inside their own wrapper, never the page
        assert page.evaluate("() => document.scripts.length") == 0  # D7: no script at all
    finally:
        context.close()


def _axe_source() -> str:
    import glob
    import os

    path = os.environ.get("AXE_CORE_JS") or next(
        iter(sorted(glob.glob("/opt/*/node_modules/axe-core/axe.min.js"))), ""
    )
    if not path or not Path(path).is_file():
        pytest.skip("axe-core is not installed on this box (set AXE_CORE_JS to its axe.min.js)")
    return Path(path).read_text(encoding="utf-8")


_AXE_RUN = """async () => {
  const r = await axe.run(document, { runOnly: { type: 'tag', values:
    ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } });
  return r.violations.map((v) => ({ id: v.id, tags: v.tags, impact: v.impact,
    nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) }));
}"""


def _open_a_group_and_its_row_detail(page) -> None:
    page.locator(
        "details > summary", has_text="cat-00 ·"
    ).click()  # the static file has no filter marker
    page.locator("details[open] th details > summary").first.click()
    assert page.locator("details[open] th details[open]").count() == 1


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("viewport", [LAPTOP, SMALL], ids=["1280", "375"])
@pytest.mark.parametrize("surface", ["live", "static"])
def test_axe_reports_no_violation_of_the_inventory_success_criteria_with_a_row_detail_open(
    browser, board, tmp_path, monkeypatch, surface, viewport, theme
):
    axe = _axe_source()
    if surface == "live":
        context, page = _inventory_page(browser, board, viewport)
    else:
        context = browser.new_context(viewport=viewport)
        page = context.new_page()
        page.goto(_static_file(tmp_path, monkeypatch).as_uri())
    try:
        page.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)", theme)
        _open_a_group_and_its_row_detail(page)
        page.evaluate(axe)
        found = page.evaluate(_AXE_RUN)
        print(
            f"AXE {surface} {viewport['width']} {theme}: "
            + json.dumps([[v["id"], v["tags"], v["nodes"]] for v in found])
        )
        bad = [v for v in found if _AXE_SCS & set(v["tags"])]
        assert bad == [], bad
    finally:
        context.close()
