"""Behaviour tests for the box-local quota dashboard (scripts/sysadmin/quota_dashboard.py).

Three things carry real risk and are pinned here; the rest is presentation.

1. **The regeneration floor bounds probe volume.** `--status --json` makes live API probes,
   so a page that re-probed per view would turn a self-refreshing browser tab into a probe
   storm. Serving N requests inside the floor must cost exactly ONE probe.
2. **A failed probe never blanks the board.** The operator reads this to decide whether work
   can continue; an empty page on a transport blip is worse than a stale one, so the last
   good payload must survive with its failure visible.
3. **The board shows REMAINING, not used.** The CLI prints utilisation; this page inverts it,
   and an inversion bug would read as "plenty of quota" at the moment there is none.
"""

from __future__ import annotations

import html
import html.parser
import importlib.util
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault(
    "QUOTA_DASH_BUDGET", "0"
)  # the box-budget banner shells out to the fleet probe; not in tests
import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"


from tests.quota_dashboard_isolation import NET_DENIED as _NET_DENIED  # noqa: E402
from tests.quota_dashboard_isolation import (  # noqa: E402
    after_load,
    isolate,
    no_network,  # noqa: E402, F401 — autouse: the network guard
)


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str):
    """Import a FRESH module instance whose env-derived module constants point at tmp_path, under
    the shared isolation (`tests/quota_dashboard_isolation.py`: an empty HOME, no provider key, no
    proxy, no MCP config) — a run once printed "brave quota probe failed (HTTPError)": a live call."""
    isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    # never the box's REAL pointer: a test render says "mob" while the box may point elsewhere,
    # and the pointer-moved regeneration would then fire on every view
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    if "QUOTA_DASH_CREDITS_KEY_FILE" not in os.environ:
        monkeypatch.setenv("QUOTA_DASH_CREDITS_KEY_FILE", str(tmp_path / "no-key.env"))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location(f"qd_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    after_load(mod, monkeypatch)
    return mod


def test_a_loopback_proxy_cannot_carry_a_provider_call(tmp_path, monkeypatch):
    """urllib connects to a configured proxy — on 127.0.0.1 the guard would let it through and the
    proxy would resolve the provider. The isolation drops every proxy variable, so the call goes
    direct and the guard refuses it."""
    import socket
    import urllib.request

    proxy = socket.socket()
    proxy.bind(("127.0.0.1", 0))
    proxy.listen(1)
    proxy.settimeout(0.5)
    url = f"http://127.0.0.1:{proxy.getsockname()[1]}"
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(var, url)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    _load(tmp_path, monkeypatch)  # the isolation every test file's loader applies
    try:
        with pytest.raises(OSError):
            urllib.request.urlopen("https://api.search.brave.com/res/v1/web/search?q=x", timeout=2)
        try:
            proxy.accept()[0].close()
            reached = True
        except TimeoutError:
            reached = False
    finally:
        proxy.close()
    assert not reached, "the provider call went through the loopback proxy"
    assert any("brave" in d for d in _NET_DENIED), _NET_DENIED
    del _NET_DENIED[:]  # this test's own refusal was the point


def test_the_network_guard_refuses_and_records_a_non_loopback_connect():
    """The guard itself: a connect or a lookup off loopback raises AND is recorded (the teardown
    assertion fails the test that tried); loopback passes."""
    import socket

    for target in (("192.0.2.1", 9), ("api.search.brave.com", 443)):
        with pytest.raises(OSError, match="test network guard"):
            socket.create_connection(target, timeout=1)
    assert any("192.0.2.1" in d for d in _NET_DENIED) and any("brave" in d for d in _NET_DENIED)
    del _NET_DENIED[:]  # this test's own refusals were the point
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    socket.create_connection(srv.getsockname(), timeout=1).close()
    srv.close()
    assert _NET_DENIED == []


def _files_without_the_guard(tests_dir: Path) -> list[str]:
    """Every quota-dashboard test file whose module never imports `no_network` from the shared
    isolation module — the import is what activates the autouse guard in that file."""
    import ast

    missing = []
    for path in sorted(tests_dir.glob("test_quota_dashboard*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(
            isinstance(node, ast.ImportFrom)
            and (node.module or "").endswith("quota_dashboard_isolation")
            and any(alias.name == "no_network" for alias in node.names)
            for node in tree.body
        ):
            missing.append(path.name)
    return missing


def test_every_quota_dashboard_test_file_activates_the_network_guard(tmp_path):
    """The guard is live only where it is imported; dropping the import from one file must go red
    here, not silently let that file reach the network."""
    tests_dir = Path(__file__).resolve().parent
    assert len(list(tests_dir.glob("test_quota_dashboard*.py"))) >= 13
    assert _files_without_the_guard(tests_dir) == []
    (tmp_path / "test_quota_dashboard_x.py").write_text(
        "from tests.quota_dashboard_isolation import isolate\n", encoding="utf-8"
    )
    assert _files_without_the_guard(tmp_path) == ["test_quota_dashboard_x.py"]


def test_the_network_guard_also_refuses_connect_ex():
    """`connect_ex` is a second way to open a socket; the guard refuses and records it like
    `connect`."""
    import socket

    s = socket.socket()
    s.settimeout(1)
    try:
        with pytest.raises(OSError, match="test network guard"):
            s.connect_ex(("192.0.2.1", 9))
    finally:
        s.close()
    assert any("192.0.2.1" in d for d in _NET_DENIED), _NET_DENIED
    del _NET_DENIED[:]


def _payload(session: float = 40.0, weekly: float = 72.0) -> dict:
    return {
        "active": "mob",
        "pause": None,
        "fleet_warnings": [],
        "accounts": [
            {
                "email": "mob@ocoron.com",
                "slugs": ["mob"],
                "five_hour": {"utilization": session, "resets_at_epoch": time.time() + 7200},
                "seven_day": {"utilization": weekly, "resets_at_epoch": time.time() + 400000},
                "source": "live",
                "age_s": None,
                "weekly_cap": None,
                "cap_walled": False,
            }
        ],
    }


# The redesign (plan 2026-10-17-plan-1, T07) retired the five-tab page these tests once grepped; each
# now renders the view that carries the behaviour, through the module's own `_render_view`.
class _Node:
    def __init__(self, tag: str, attrs: dict, parent):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, attrs, parent, [], ""

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def words(self) -> str:
        return " ".join((self.text + " " + " ".join(c.words() for c in self.children)).split())


class _Tree(html.parser.HTMLParser):
    _VOID = {"input", "meta", "link", "br", "hr", "img"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = _Node("#root", {}, None)

    def handle_starttag(self, tag, attrs):
        n = _Node(tag, dict(attrs), self.cur)
        self.cur.children.append(n)
        if tag not in self._VOID:
            self.cur = n

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text += " " + data


def _dom(markup: str) -> _Node:
    p = _Tree()
    p.feed(markup)
    p.close()
    return p.root


def _find(root: _Node, tag: str | None = None, **attrs) -> list[_Node]:
    return [
        n
        for n in root.walk()
        if (tag is None or n.tag == tag)
        and all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items())
    ]


def _text(markup: str) -> str:
    """Every word the operator reads in ``markup``, unescaped and whitespace-collapsed."""
    return _dom(markup).words()


def _badges(markup: str) -> list[tuple[str, str]]:
    """(severity, text) of every status badge — the text without its icon and assistive prefix."""
    out = []
    for n in _find(_dom(markup), "span"):
        if "data-severity" in n.attrs and n.children:
            out.append((n.attrs["data-severity"], n.children[-1].words()))
    return out


def _view(qd, name: str) -> str:
    """One view's fragment exactly as `GET /v/<name>` serves it."""
    return qd._render_view(name)


def _accounts(qd) -> str:
    return _view(qd, "accounts")


def _acct_row(markup: str, slug: str, kind: str | None = None) -> _Node:
    rows = [
        r
        for r in _find(_dom(markup), "tr", data_acct=slug)
        if kind is None or r.attrs.get("data-row") == kind
    ]
    assert len(rows) == 1, (slug, kind, len(rows))
    return rows[0]


def _join_regen(qd) -> None:
    worker = qd._LAST_REGEN[0]
    if worker is not None:
        worker.join(timeout=10)


def test_generate_writes_quota_json_and_no_page(tmp_path, monkeypatch):
    """`generate()` keeps its probe, quota.json and `_LAST_STATUS` duty; the page is the live shell
    now, so no index.html is written (T07)."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())

    payload = qd.generate()

    assert payload["active"] == "mob" and qd._LAST_STATUS[0][1] == payload
    assert qd._JSON.is_file() and json.loads(qd._JSON.read_text())["active"] == "mob"
    assert not (qd.OUT_DIR / "index.html").exists()


def _one_account(qd, monkeypatch, acct: dict) -> str:
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)  # the reading is set by hand
    qd._set_last_status(time.time(), {"active": acct["slugs"][0], "accounts": [acct]})
    return _accounts(qd)


def test_serving_inside_the_floor_costs_exactly_one_probe(tmp_path, monkeypatch):
    """The probe-volume bound: many views inside QUOTA_DASH_MAX_AGE_S → ONE probe."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    calls: list[float] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(time.time()), _payload())[1])

    _accounts(qd)  # nothing on disk: the first view starts the one background probe
    _join_regen(qd)
    for _ in range(5):
        again = _accounts(qd)
        _join_regen(qd)

    assert len(calls) == 1, f"expected 1 probe for 6 views inside the floor, got {len(calls)}"
    assert "mob@ocoron.com" in again


def test_a_view_past_the_floor_reprobes(tmp_path, monkeypatch):
    """The other half of the bound: the board must not go stale forever."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="0")
    calls: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(1), _payload())[1])

    _accounts(qd)
    _join_regen(qd)
    _accounts(qd)
    # The second view kicks off a BACKGROUND regeneration; join it rather than race it (this
    # assertion failed 2-3 times in 10 before the join, on a code path nobody had changed).
    worker = qd._LAST_REGEN[0]
    assert worker is not None, "a stale view must schedule a regeneration"
    worker.join(timeout=10)

    assert len(calls) == 2


def test_probe_failure_keeps_the_last_good_board_and_says_so(tmp_path, monkeypatch):
    """Never blank: a transport failure renders the previous payload behind a banner."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload(weekly=72.0))
    qd.generate()  # seeds quota.json with a good payload

    def _boom():
        raise RuntimeError("connection reset")

    monkeypatch.setattr(qd, "_probe", _boom)
    payload = qd.generate()
    assert payload["probe_failed"] == "RuntimeError: connection reset"
    assert json.loads(qd._JSON.read_text())["probe_failed"] == "RuntimeError: connection reset"
    html_ = _accounts(qd)

    assert "mob@ocoron.com" in html_, "the last good board must survive a failed probe"
    assert ("ok", "28% left") in _badges(html_), "…including its numbers (100-72 weekly)"
    # the banner names the failure by class (a message can carry paths — W-6a0f3c65)
    assert (
        "critical",
        "Live probe failed — showing the last good reading. RuntimeError",
    ) in _badges(html_)


def test_the_board_reports_remaining_not_used(tmp_path, monkeypatch):
    """Inversion guard: 91% used must render as 9% left, not 91%."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=91.0))
    qd.generate()

    html_ = _accounts(qd)

    assert ("warning", "9% left") in _badges(html_), "weekly 91% used → 9% left"
    assert ("ok", "100% left") in _badges(html_), "session 0% used → 100% left"
    assert "91% used" in _text(html_), "the raw utilisation stays visible as the sub-line"


def test_red_starts_where_the_fleet_abandons_the_account(tmp_path, monkeypatch):
    """The crit boundary is not cosmetic: ≤5% left == ≥95% used == the flip threshold, i.e.
    red means 'the fleet is about to leave this account', amber means 'still usable'."""
    qd = _load(tmp_path, monkeypatch)

    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=95.0))
    qd.generate()
    assert ("critical", "5% left") in _badges(_accounts(qd))

    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=94.0))
    qd.generate()
    assert ("warning", "6% left") in _badges(_accounts(qd))


def test_cap_walled_account_is_named_as_reserved(tmp_path, monkeypatch):
    """The operator's reserve must be legible on the board, not just in the CLI."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload()
    payload["accounts"][0].update(
        {"email": "ob@ocoron.com", "slugs": ["ob"], "weekly_cap": 90, "cap_walled": True}
    )
    monkeypatch.setattr(qd, "_probe", lambda: payload)
    qd.generate()

    marks = _badges(_accounts(qd))

    assert ("info", "cap 90%") in marks
    assert ("critical", "RESERVED — fleet excluded") in marks


def test_no_credential_paths_are_read_by_the_dashboard():
    """Boundary: the view shells the rotation CLI; it must never touch credential files."""
    src = _SRC.read_text(encoding="utf-8")
    assert ".credentials.json" not in src
    assert "manager-accounts" not in src


def test_a_cached_reading_older_than_its_window_reads_unknown_not_100(tmp_path, monkeypatch):
    """The permanently-green class, caught live by the operator: an idle account's 5-hour
    reading cached 8h ago describes a window that has ROLLED OVER COMPLETELY. Rendering it as
    "100% left" can only ever reassure — it means "we have not looked", not "plenty of quota".
    The weekly cell keeps its number at that age (a 7-day window is still meaningful)."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=91.0)
    payload["active"] = "someone-else"  # this row must NOT be the active pointer
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600})
    monkeypatch.setattr(qd, "_probe", lambda: payload)
    qd.generate()

    html_ = _accounts(qd)

    assert ("ok", "100% left") not in _badges(html_), "no unearned reassuring 100%"
    assert ("ok", "idle") in _badges(html_), (
        "a non-active account's rolled window is EMPTY — say so"
    )
    assert "not the active pointer" in _text(html_), "and say why it is derivable, not measured"
    assert ("warning", "9% left") in _badges(html_), "the 7-day cell survives at 8.5h"


def test_a_cached_reading_younger_than_its_window_still_shows_the_number(tmp_path, monkeypatch):
    """The other half: 30 minutes into a 5-hour window the cached reading is still about the
    window we are in, so suppressing it would throw away real information."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=40.0, weekly=50.0)
    payload["accounts"][0].update({"source": "cache", "age_s": 1800.0})
    monkeypatch.setattr(qd, "_probe", lambda: payload)
    qd.generate()

    html_ = _accounts(qd)

    assert ("ok", "60% left") in _badges(html_)
    assert "since this window rolled" not in _text(html_)


def test_the_active_account_cannot_claim_idle_when_its_window_rolled(tmp_path, monkeypatch):
    """The 'idle' shortcut is only sound because a non-active account cannot burn fleet quota.
    The ACTIVE account can, so a rolled-over window there is genuinely unknown, not idle."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=50.0)
    payload["active"] = "mob"  # the row below IS mob
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600})
    monkeypatch.setattr(qd, "_probe", lambda: payload)
    qd.generate()

    marks = _badges(_accounts(qd))

    assert ("warning", "unknown") in marks and ("ok", "idle") not in marks


def test_a_capped_account_surfaces_the_browser_blind_spot(tmp_path, monkeypatch):
    """A cap exists because the operator uses that account in the browser — usage no probe of
    ours can see. An 'idle' cell there must not imply we checked."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=91.0)
    payload["active"] = "someone-else"
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600, "weekly_cap": 90})
    monkeypatch.setattr(qd, "_probe", lambda: payload)
    qd.generate()

    assert "browser use is not visible here" in _text(_accounts(qd))


# ── model-specific weekly windows on the board (2026-08-22: fable/opus visibility) ──
def test_row_renders_fable_weekly_column(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    acct = {
        "email": "sarp@ocoron.com",
        "slugs": ["sarp"],
        "source": "live",
        "five_hour": {"utilization": 10.0, "resets_at_epoch": None},  # 90% left
        "seven_day": {"utilization": 40.0, "resets_at_epoch": None},  # 60% left
        "model_windows": {"Fable": {"utilization": 76.0, "resets_at_epoch": None}},
    }
    row = _acct_row(_one_account(qd, monkeypatch, acct), "sarp", "active")
    fable = [c for c in row.children if c.tag == "td"][2]  # account | session | weekly | FABLE
    assert "24% left" in fable.words(), "Fable cell shows remaining (100-76) in its own column"
    assert "76% used" in fable.words()


def test_row_fable_column_says_no_reading_when_absent(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    acct = {
        "email": "ob@ocoron.com",
        "slugs": ["ob"],
        "source": "cache",
        "age_s": 1000.0,
        "five_hour": {"utilization": 0.0, "resets_at_epoch": None},
        "seven_day": {"utilization": 1.0, "resets_at_epoch": None},
    }
    # no Fable reading yet (idle, token unrefreshed) → the Fable cell is an honest "no reading"
    row = _acct_row(_one_account(qd, monkeypatch, acct), "ob", "active")
    assert [c for c in row.children if c.tag == "td"][2].words() == "no reading"


def test_header_has_fable_weekly_column(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    qd._set_last_status(time.time(), {"accounts": [], "active": None})
    heads = [h.words() for h in _find(_dom(_accounts(qd)), "th", scope="col")]
    assert heads == ["Account", "Session (5h)", "Weekly", "Fable", "Controls"]


# ---------------------------------------------------------------------------------------------
# Manual switch button (2026-09-02). The board gained ONE write path: POST /switch shells
# `claude_rotate.py --switch <slug>` — the CLI still owns the credential contract, the
# dashboard only relays the operator's click. Risk-ordered: a forged cross-origin POST from any
# page in the operator's browser must be refused; a slug the board does not know must never
# reach the CLI; a CLI failure must be shown, not swallowed.
# ---------------------------------------------------------------------------------------------

import threading  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402


def _multi_payload() -> dict:
    p = _payload()
    p["accounts"].append(
        {
            "email": "sarp@ocoron.com",
            "slugs": ["sarp"],
            "five_hour": {"utilization": 10.0, "resets_at_epoch": time.time() + 7200},
            "seven_day": {"utilization": 20.0, "resets_at_epoch": time.time() + 400000},
            "source": "live",
            "age_s": None,
            "weekly_cap": 90,
            "cap_walled": False,
        }
    )
    return p


def _serve(qd):
    """A real loopback server on an ephemeral port — the HTTP→subprocess path is exercised
    for real, not through a hand-built request object."""
    from http.server import ThreadingHTTPServer

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), qd._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _post(url: str, body: bytes, headers: dict | None = None):
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw.startswith("{") else {"raw": raw})


def _switch_env(tmp_path, monkeypatch):
    """A dashboard whose rotation CLI is a stub that RECORDS its argv (never the real CLI)."""
    stub = tmp_path / "stub_rotate.py"
    stub.write_text(
        "import sys, json, pathlib\n"
        "pathlib.Path(sys.argv[0] + '.calls').open('a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == '--status':\n"
        "    print(json.dumps(json.loads(pathlib.Path(sys.argv[0] + '.payload').read_text())))\n"
        "    sys.exit(0)\n"
        "if sys.argv[1] == '--switch':\n"
        "    if pathlib.Path(sys.argv[0] + '.fail').exists():\n"
        "        sys.stderr.write('switch failed — active pointer unchanged\\n'); sys.exit(1)\n"
        "    print('active fleet account -> ' + sys.argv[2]); sys.exit(0)\n"
        "if sys.argv[1] in ('--park', '--unpark'):\n"
        "    print(sys.argv[2] + (' PARKED' if sys.argv[1] == '--park' else ' back IN SERVICE'))\n"
        "    sys.exit(0)\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    (tmp_path / "stub_rotate.py.payload").write_text(json.dumps(_multi_payload()))
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_ROTATE_CLI=str(stub))
    qd.generate()  # the board knows its slugs from the last payload
    return qd, stub


def _calls(stub: Path) -> list[list[str]]:
    p = Path(str(stub) + ".calls")
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def test_switch_without_the_custom_header_is_refused(tmp_path, monkeypatch):
    """A plain cross-origin POST (any page in the operator's browser can send one to
    localhost) carries no custom header — the server refuses it and the CLI is never run."""
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        before = len(_calls(stub))
        status, body = _post(f"{base}/switch", b'{"account": "sarp"}')
        assert status == 403, body
        assert not any(c[:1] == ["--switch"] for c in _calls(stub)[before:])
    finally:
        httpd.shutdown()


def test_switch_rejects_a_slug_the_board_does_not_know(tmp_path, monkeypatch):
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        for bad in (b'{"account": "nope"}', b'{"account": "../x"}', b"{}", b"not json"):
            status, body = _post(f"{base}/switch", bad, {qd.SWITCH_HEADER: "1"})
            assert status == 400, (bad, body)
        assert not any(c[:1] == ["--switch"] for c in _calls(stub))
    finally:
        httpd.shutdown()


def test_switch_shells_the_rotation_cli_and_regenerates_the_board(tmp_path, monkeypatch):
    """The happy path: exactly one `--switch <slug>` call with the slug the operator clicked,
    then a FRESH render (the reload must show the new pointer, not a floor-cached one)."""
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        before = _calls(stub)
        status, body = _post(f"{base}/switch", b'{"account": "sarp"}', {qd.SWITCH_HEADER: "1"})
        assert status == 200 and body["ok"] is True, body
        assert "active fleet account -> sarp" in body["output"]
        after = _calls(stub)[len(before) :]
        assert [c for c in after if c[0] == "--switch"] == [["--switch", "sarp"]]
        assert ["--status", "--json"] in after  # the regeneration probe ran AFTER the switch
    finally:
        httpd.shutdown()


def test_switch_cli_failure_is_reported_not_hidden(tmp_path, monkeypatch):
    qd, stub = _switch_env(tmp_path, monkeypatch)
    Path(str(stub) + ".fail").touch()
    httpd, base = _serve(qd)
    try:
        status, body = _post(f"{base}/switch", b'{"account": "sarp"}', {qd.SWITCH_HEADER: "1"})
        assert status == 502 and body["ok"] is False
        assert "active pointer unchanged" in body["error"]
    finally:
        httpd.shutdown()


def _buttons(node: _Node, path: str) -> list[dict]:
    """The JSON body of every button in ``node`` that posts to ``path``."""
    return [
        json.loads(b.attrs.get("data-body") or "{}") for b in _find(node, "button", data_post=path)
    ]


def _two_accounts(active: str) -> dict:
    p = _payload()
    p["active"] = active
    p["accounts"].append({**p["accounts"][0], "email": "can@ocoron.com", "slugs": ["can"]})
    return p


def test_the_page_scripts_parse(tmp_path, monkeypatch):
    """A syntax error in the page's script silently kills every behaviour on it (measured
    2026-09-02: a raw newline inside a confirm() string — the board froze on the old account and
    every button was inert). The page now carries ONE inline script — the theme head script — and
    one static `app.js`; both must parse."""
    import shutil

    qd = _load(tmp_path, monkeypatch)
    page = qd._shell_page()
    inline = [m.group(1) for m in re.finditer(r"<script>(.*?)</script>", page, re.S)]
    assert len(inline) == 1 and "qd-theme" in inline[0]
    app_js = (qd.dashboard_ui.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the parse check needs it")
    for name, script in (("head.js", inline[0]), ("app.js", app_js)):
        js = tmp_path / name
        js.write_text(script, encoding="utf-8")
        r = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
        assert r.returncode == 0, (name, r.stderr[:400])


def test_every_idle_row_has_a_switch_button_and_the_active_row_has_none(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _multi_payload)
    qd.generate()
    html_ = _accounts(qd)
    assert _buttons(_acct_row(html_, "sarp"), "/switch") == [{"account": "sarp"}]
    assert _buttons(_acct_row(html_, "mob", "active"), "/switch") == []  # mob is the active pointer


def test_park_without_the_custom_header_is_refused(tmp_path, monkeypatch):
    """`/park` takes an account out of service — the same CSRF guard as `/switch`: a plain
    cross-origin POST carries no custom header, so it is refused and the CLI never runs."""
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        status, body = _post(f"{base}/park", b'{"account": "sarp@ocoron.com", "park": true}')
        assert status == 403, body
        assert not any(c[:1] in (["--park"], ["--unpark"]) for c in _calls(stub))
    finally:
        httpd.shutdown()


def test_park_rejects_an_account_the_board_does_not_know_or_a_non_bool_park(tmp_path, monkeypatch):
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        for bad in (
            b'{"account": "nobody@x.com", "park": true}',
            b'{"account": "sarp@ocoron.com", "park": "yes"}',
            b'{"account": "sarp@ocoron.com"}',
            b'{"account": "--help", "park": true}',
        ):
            status, body = _post(f"{base}/park", bad, {qd.SWITCH_HEADER: "1"})
            assert status == 400, (bad, body)
        assert not any(c[:1] in (["--park"], ["--unpark"]) for c in _calls(stub))
    finally:
        httpd.shutdown()


def test_park_and_unpark_shell_the_rotation_cli_and_regenerate_the_board(tmp_path, monkeypatch):
    """Operator 2026-09-29: "enabling it must be easy — put a button in the gui". One click is
    exactly one `--park`/`--unpark <email>` call, then a fresh render."""
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        for park, verb in ((True, "--park"), (False, "--unpark")):
            before = _calls(stub)
            payload = json.dumps({"account": "SARP@ocoron.com", "park": park}).encode()
            status, body = _post(f"{base}/park", payload, {qd.SWITCH_HEADER: "1"})
            assert status == 200 and body["ok"] is True, body
            after = _calls(stub)[len(before) :]
            assert [c for c in after if c[0] == verb] == [[verb, "sarp@ocoron.com"]]
            assert ["--status", "--json"] in after  # the regeneration probe ran AFTER it
    finally:
        httpd.shutdown()


def test_a_parked_row_shows_parked_and_enable_and_an_unparked_row_offers_disable(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)

    def payload():
        p = _multi_payload()
        p["accounts"][-1].update(weekly_cap=0, cap_walled=True, parked=True)  # sarp parked
        return p

    monkeypatch.setattr(qd, "_probe", payload)
    qd.generate()
    html_ = _accounts(qd)
    sarp, mob = _acct_row(html_, "sarp"), _acct_row(html_, "mob", "active")
    assert ("critical", "PARKED — out of service") in _badges(html_)
    assert _buttons(sarp, "/park") == [{"account": "sarp@ocoron.com", "park": False}]
    assert [b.words() for b in _find(sarp, "button", data_post="/park")] == ["Enable"]
    assert _buttons(sarp, "/switch") == [], "a parked account offers no switch → until enabled"
    assert _buttons(mob, "/park") == [{"account": "mob@ocoron.com", "park": True}]
    assert [b.words() for b in _find(mob, "button", data_post="/park")] == ["Disable"]
    assert ("info", "cap 0%") not in _badges(html_), (
        "a parked row names itself PARKED, not a 0% cap"
    )


def test_a_parked_account_is_never_shown_returning(tmp_path, monkeypatch):
    """Park review pass 1 (B-S1, B-S2): the board's own queue mirror computed a return from the
    weekly reset of a PARKED row, so the queue badge and the active row's ghost promised the
    account back at a time no reset can deliver — only `--unpark` returns it."""
    qd = _load(tmp_path, monkeypatch)
    now = time.time()
    acct = {
        "email": "sarp@ocoron.com",
        "slugs": ["sarp"],
        "weekly_cap": 0,
        "cap_walled": True,
        "parked": True,
        "five_hour": {"utilization": 99.0, "resets_at_epoch": now + 3600},
        "seven_day": {"utilization": 10.0, "resets_at_epoch": now + 86400},
    }
    assert qd._returns_at(acct, now) is None
    assert qd._returns_at(dict(acct, parked=False), now) == now + 86400, "control: unparked returns"
    # the queue's relief branch (pass 2, B-S2): an ACTIVE parked account in the drain band with an
    # eligible standby was drawn a `return` ghost from its raw window reset
    active = dict(
        acct, five_hour={"utilization": qd._drain_band() + 5, "resets_at_epoch": now + 3600}
    )
    standby = {
        "email": "ob@ocoron.com",
        "slugs": ["ob"],
        "weekly_cap": 95,
        "cap_walled": False,
        "five_hour": {"utilization": 5.0, "resets_at_epoch": now + 3600},
        "seven_day": {"utilization": 5.0, "resets_at_epoch": now + 86400},
    }

    def ghosts(active_row):
        payload = {"active": "sarp", "accounts": [active_row, standby]}
        return [e for e in qd._queue(payload, now) if e["kind"] == "return"]

    assert ghosts(active) == [], "a parked active account is never drawn returning"
    assert ghosts(dict(active, parked=False)), "control: the unparked twin does get its ghost"


def test_a_short_body_cannot_hold_a_handler_thread_forever(tmp_path, monkeypatch):
    """A client that promises 100 bytes and sends 10 must be dropped by the socket timeout,
    not parked on `rfile.read()` until it decides to leave (measured before the fix: the
    handler thread hung for as long as the client stayed connected). The request names the
    board's own Host, so it passes the INV-6 guard and reaches the body read — a foreign Host is
    answered 421 before any read and would prove nothing (the T02 review's vacuity finding)."""
    import socket

    monkeypatch.setenv("QUOTA_DASH_SOCKET_TIMEOUT_S", "0.5")  # the knob the fix reads at import
    qd, stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        host, port = httpd.server_address[:2]
        s = socket.create_connection((host, port), timeout=5)
        s.sendall(
            f"POST /switch HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Quota-Dash: 1\r\n".encode()
            + b"Content-Type: application/json\r\nContent-Length: 100\r\n\r\n"
            + b'{"account"'
        )
        t0 = time.time()
        try:
            data = s.recv(4096)  # either a response or a clean close — never a hang past 5s
        except TimeoutError:
            pytest.fail("handler held the connection open past 5s on a short body")
        assert time.time() - t0 < 4.0
        assert data == b"" or (data.startswith(b"HTTP/1.") and b" 421 " not in data[:16])
        s.close()
    finally:
        httpd.shutdown()
    assert not any(c[:1] == ["--switch"] for c in _calls(stub))


def test_a_pointer_change_regenerates_before_the_floor(tmp_path, monkeypatch):
    """The operator switched accounts and the board kept showing the OLD pointer for up to
    floor + reload (~5 min) — measured 2026-09-02 after a `--switch`. A pointer that no longer
    matches the reading's `active` must regenerate on the next view, floor or no floor."""
    pointer = tmp_path / "active"
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(pointer))
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    state = {"active": "mob"}
    calls: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(1), _two_accounts(state["active"]))[1])
    for d in ("mob", "can"):  # the fleet dirs exist; the CLI names a pointer by its real target
        (tmp_path / d).mkdir(exist_ok=True)
    pointer.symlink_to(tmp_path / "mob")
    qd.generate()
    assert _acct_row(_accounts(qd), "mob", "active")
    # the pointer moves (a --switch or a tick flip); the reading on disk is seconds old
    pointer.unlink()
    pointer.symlink_to(tmp_path / "can")
    state["active"] = "can"
    _accounts(qd)  # the view is served at once and starts the regeneration in the background
    _join_regen(qd)
    assert _acct_row(_accounts(qd), "can", "active"), "the next view shows it, not the floor's"
    _join_regen(qd)
    assert _acct_row(_accounts(qd), "can", "active")  # and the later views cost no second probe
    assert len(calls) == 2


def test_a_probe_hang_after_a_flip_blocks_one_view_not_every_view(tmp_path, monkeypatch):
    """After a flip the board regenerates ONCE (in the background). If that probe FAILS, the fallback
    payload must carry the live pointer so the next views serve instantly instead of each
    paying the probe timeout until the probe recovers (review finding on the pointer-moved path)."""
    pointer = tmp_path / "active"
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(pointer))
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    monkeypatch.setattr(qd, "_probe", lambda: _two_accounts("mob"))
    for d in ("mob", "can"):  # the fleet dirs exist; the CLI names a pointer by its real target
        (tmp_path / d).mkdir(exist_ok=True)
    pointer.symlink_to(tmp_path / "mob")
    qd.generate()
    pointer.unlink()
    pointer.symlink_to(tmp_path / "can")
    calls: list[int] = []

    def _hang():
        calls.append(1)
        raise TimeoutError("probe hung")

    monkeypatch.setattr(qd, "_probe", _hang)
    _accounts(qd)  # the one background attempt after the flip — it fails
    _join_regen(qd)
    _accounts(qd)
    _accounts(qd)
    _join_regen(qd)
    assert len(calls) == 1, f"every view re-ran the failed probe: {len(calls)} probes for 3 views"
    assert _acct_row(_accounts(qd), "can", "active"), (
        "the pointer is a local fact — shown even when the probe is down"
    )


def test_ensure_restarts_a_server_that_listens_but_does_not_answer(tmp_path, monkeypatch):
    """`--ensure` used to connect to the port and call it alive. A wedged server (accepts,
    never answers) then stayed wedged forever — the operator's "must be up no matter what".
    ensure() now demands an HTTP `ok` from /health; anything else kills the listener and respawns."""
    import socket
    import threading

    qd = _load(tmp_path, monkeypatch)
    wedged = socket.socket()
    wedged.bind(("127.0.0.1", 0))
    wedged.listen(1)
    port = wedged.getsockname()[1]
    threading.Thread(target=lambda: wedged.accept(), daemon=True).start()
    monkeypatch.setattr(qd, "PORT", port)
    monkeypatch.setenv("QUOTA_DASH_LOG", str(tmp_path / "log"))
    killed: list[int] = []
    spawned: list[list[str]] = []
    monkeypatch.setattr(qd, "_listener_pid", lambda port: 4242)
    monkeypatch.setattr(qd.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(qd.subprocess, "Popen", lambda argv, **kw: spawned.append(argv))
    monkeypatch.setenv("QUOTA_DASH_ENSURE_TIMEOUT_S", "0.5")
    assert qd.ensure() == 0
    # the stub keeps reporting pid 4242 as the holder, so ensure() escalates TERM → KILL
    assert killed and all(k == 4242 for k in killed), "the listener that never answers is killed"
    assert spawned and "--serve" in spawned[0], "…and a fresh server spawned"
    wedged.close()


# ── operator rules 2026-09-03: probe every 20s without a viewer; trigger the tick at 98% ──────


def _tick_env(tmp_path, monkeypatch, session: float = 40.0, **env: str):
    """A dashboard whose rotation CLI is a stub that also answers `--tick` (records argv)."""
    stub = tmp_path / "stub_rotate.py"
    stub.write_text(
        "import sys, json, pathlib\n"
        "pathlib.Path(sys.argv[0] + '.calls').open('a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == '--status':\n"
        "    print(json.dumps(json.loads(pathlib.Path(sys.argv[0] + '.payload').read_text())))\n"
        "    sys.exit(0)\n"
        "if sys.argv[1] == '--tick':\n"
        "    print('tick: ok'); sys.exit(0)\n"
        "sys.exit(2)\n",
        encoding="utf-8",
    )
    (tmp_path / "stub_rotate.py.payload").write_text(json.dumps(_payload(session=session)))
    # Isolate the rotation lock by default: the trigger takes `flock -n` on ROTATE_LOCK, and the
    # default is the LIVE box's ~/.claude/state/rotate.lock — a real tick holding it (the running
    # dashboard fires one on an account switch) made both trigger tests fail mid-suite 2026-09-03.
    env.setdefault("QUOTA_DASH_ROTATE_LOCK", str(tmp_path / "rotate.lock"))
    return _load(tmp_path, monkeypatch, QUOTA_DASH_ROTATE_CLI=str(stub), **env), stub


def test_the_server_probes_on_its_own_cadence_without_a_viewer(tmp_path, monkeypatch):
    """Operator rule: probe every 20 seconds — with NO page open. The probe loop is a server
    thread (`_start_probe_loop`), so the cadence no longer depends on a viewer's reloads."""
    qd, stub = _tick_env(tmp_path, monkeypatch, QUOTA_DASH_PROBE_INTERVAL_S="0.15")
    assert qd.PROBE_INTERVAL_S == 0.15
    # round-9 Opus finding: "≥3 probes in 0.8 s" sat on the boundary (2, 3, 2 measured) and was
    # red 5 of 5 under load. No wall clock: the loop's own stop event records its waits and
    # stops after three full cycles — three probes happened with NO viewer, deterministically.
    import threading

    waits: list[float] = []
    real_event = threading.Event
    made = {"n": 0}

    class _Ev(threading.Event):
        def wait(self, timeout=None):  # type: ignore[override]
            waits.append(float(timeout))
            if len(waits) >= 3:
                self.set()
            return True

    def first_event_records():
        made["n"] += 1
        return _Ev() if made["n"] == 1 else real_event()

    monkeypatch.setattr(qd.threading, "Event", first_event_records)
    stop = qd._start_probe_loop()
    for _ in range(500):
        if stop.is_set():
            break
        time.sleep(0.01)
    stop.set()
    probes = [c for c in _calls(stub) if c[:2] == ["--status", "--json"]]
    assert len(probes) >= 3, probes


def test_the_active_account_crossing_the_session_threshold_triggers_the_tick_at_once(
    tmp_path, monkeypatch
):
    """Operator rule: rotate as soon as the 5h window hits the flip line. The board, which probes
    every 20s, invokes the rotation tick the moment the ACTIVE account's session ≥ ROTATE_THRESHOLD —
    once per cooldown. The drain tier is pushed to 100 so ONLY the flip tier can fire here (a literal
    98.2 under the 99 default passed on the drain tier with the flip check dead — D-855 review)."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    qd, stub = _tick_env(
        tmp_path,
        monkeypatch,
        session=86.0,
        QUOTA_DASH_TRIGGER_COOLDOWN_S="60",
        ROTATE_URGENT_DRAIN_PCT="100",
    )
    qd.generate()
    assert qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text())) is None
    assert not [c for c in _calls(stub) if c[:1] == ["--tick"]]
    (tmp_path / "stub_rotate.py.payload").write_text(
        json.dumps(_payload(session=qd.TRIGGER_THRESHOLD + 0.2))
    )
    qd.generate()
    payload = json.loads(qd._JSON.read_text())
    t = qd._maybe_trigger_rotation(payload)
    assert t is not None
    t.join(10)
    assert qd._maybe_trigger_rotation(payload) is None  # inside the cooldown
    assert [c for c in _calls(stub) if c[:1] == ["--tick"]] == [["--tick"]]


def test_a_cap_walled_active_account_also_triggers_the_tick(tmp_path, monkeypatch):
    qd, stub = _tick_env(tmp_path, monkeypatch, session=10.0)
    payload = _payload(session=10.0)
    payload["accounts"][0]["cap_walled"] = True
    t = qd._maybe_trigger_rotation(payload)
    assert t is not None
    t.join(10)
    assert [c for c in _calls(stub) if c[:1] == ["--tick"]] == [["--tick"]]


# ── scoped review 2026-09-03 (seen RED first) ─────────────────────────────────────────────────


def test_generate_never_runs_two_probes_at_once(tmp_path, monkeypatch):
    """The loop, a past-the-floor view, a pointer-moved view and a switch all call `generate()`;
    only `_regen_async` held a lock. Two concurrent probes double the API cost and race the
    quota.json/index.html writes. `generate()` itself must serialize."""
    qd = _load(tmp_path, monkeypatch)
    state = {"running": 0, "max": 0}
    lock = threading.Lock()

    def slow_probe():
        with lock:
            state["running"] += 1
            state["max"] = max(state["max"], state["running"])
        time.sleep(0.15)
        with lock:
            state["running"] -= 1
        return _payload()

    monkeypatch.setattr(qd, "_probe", slow_probe)
    threads = [threading.Thread(target=qd.generate) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert state["max"] == 1, state


def test_the_trigger_runs_the_tick_under_the_cron_lock_and_off_the_loop_thread(
    tmp_path, monkeypatch
):
    """The cron runs `flock -n ~/.claude/state/rotate.lock … --tick`; the board's tick must take the
    SAME lock (two ticks deciding at once is the double-flip race) and must not stall the probe
    loop for up to TICK_TIMEOUT_S — it runs on its own thread, which the trigger returns."""
    monkeypatch.setenv("ROTATE_THRESHOLD", "98")  # fixture built on the pre-2026-10-14 line
    lockfile = tmp_path / "rotate.lock"
    qd, stub = _tick_env(tmp_path, monkeypatch, session=98.5, QUOTA_DASH_ROTATE_LOCK=str(lockfile))
    assert lockfile == qd.ROTATE_LOCK
    payload = _payload(session=98.5)
    t = qd._maybe_trigger_rotation(payload)
    assert t is not None and hasattr(t, "join"), t
    t.join(10)
    ticks = [c for c in _calls(stub) if c[:1] == ["--tick"]]
    assert ticks == [["--tick"]]
    # while the lock is HELD by someone else (the cron tick), the board's tick is skipped, not queued
    import fcntl

    with open(lockfile, "a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        qd._LAST_TRIGGER[0] = 0.0
        t2 = qd._maybe_trigger_rotation(payload)
        assert t2 is not None
        t2.join(10)
        fcntl.flock(holder, fcntl.LOCK_UN)
    assert [c for c in _calls(stub) if c[:1] == ["--tick"]] == [["--tick"]]  # no second tick ran


def test_dashboard_trigger_default_matches_the_tick_default(tmp_path, monkeypatch):
    """The board's threshold is a literal duplicate of the CLI's default (the cron sets no env, the
    board reads env at import) — the two must move together, and this test is the pin."""
    import importlib.util

    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    qd = _load(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location("cr_pin", _SRC.parent / "claude_rotate.py")
    cr = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cr)
    # 98 since 2026-09-08 (D-201). The literal is pinned deliberately — deriving BOTH sides from
    # the code would let the two drift together silently, which is the only failure this grader
    # exists to catch. Update it in the same change that moves the constants, never after.
    assert qd.TRIGGER_THRESHOLD == cr._rotate_threshold() == 99.0
    # and the no-successor mail must stay BELOW the flip line: with a successor the flip is the
    # remedy, without one this is, and it needs runway. 90 < 98 is the design (D-201).
    assert qd.DRAIN_TRIGGER_THRESHOLD < qd.TRIGGER_THRESHOLD


def test_rows_are_ordered_active_first_then_in_rotation_order(tmp_path, monkeypatch):
    """Operator rule 2026-09-03: the active account on top, then the account rotation would pick
    NEXT, then the one after, … — dynamic for any number of accounts. The order mirrors the tick's
    picker (`_pick_flip_target`): among ELIGIBLE standbys (not walled, not cap-walled, a known 5h
    reading ≤ the target budget), the SOONEST weekly reset first, ties to lower weekly then lower
    session; ineligible accounts (cap-walled, walled, no reading) after them, by the same key."""
    qd = _load(tmp_path, monkeypatch)
    now = time.time()

    def acct(slug, session, weekly, reset_in, cap_walled=False):
        return {
            "email": f"{slug}@ocoron.com",
            "slugs": [slug],
            "five_hour": {"utilization": session, "resets_at_epoch": now + 3600},
            "seven_day": {"utilization": weekly, "resets_at_epoch": now + reset_in},
            "source": "live",
            "age_s": None,
            "weekly_cap": None,
            "cap_walled": cap_walled,
        }

    payload = {
        "active": "sarp",
        "pause": None,
        "fleet_warnings": [],
        "accounts": [
            acct("ob", 10.0, 30.0, reset_in=5 * 86400, cap_walled=True),  # ineligible → last
            acct("can", 5.0, 40.0, reset_in=2 * 86400),  # next: soonest reset
            acct("sarp", 60.0, 70.0, reset_in=1 * 86400),  # active → first
            acct("mob", 20.0, 10.0, reset_in=4 * 86400),  # then
            acct("x5", 90.0, 5.0, reset_in=3600),  # no 5h budget → ineligible
        ],
    }
    order = [a["slugs"][0] for a in qd._display_order(payload, _NOW)]
    assert order == ["sarp", "can", "mob", "x5", "ob"], order
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    qd._set_last_status(now, payload)
    html_ = _accounts(qd)
    rows = [
        r.attrs["data-acct"]
        for r in _find(_dom(html_), "tr")
        if r.attrs.get("data-row") != "return" and "data-acct" in r.attrs
    ]
    assert rows == ["sarp", "can", "mob", "x5", "ob"], rows
    assert ("neutral", "#2 NEXT") in _badges(html_)  # the rank is labelled, not implied


def test_the_probe_interval_is_a_period_not_a_pause_after_each_probe(tmp_path, monkeypatch):
    """A probe of four accounts takes ~20s itself; waiting the full interval AFTER it made the real
    cadence ~40s (measured live 2026-09-03: 43s between quota.json writes). The interval is the
    PERIOD: the loop waits interval minus the probe's own duration."""
    qd, stub = _tick_env(tmp_path, monkeypatch, QUOTA_DASH_PROBE_INTERVAL_S="0.15")
    # round-9 finding: the median-gap version still needed three real cycles in 1.6 s and got ONE
    # under load 20 on the shared box (red 6 of 6). No wall clock at all now: a fake monotonic
    # clock the probe advances by 0.1, and an Event whose `wait` RECORDS the timeout the loop
    # computed — period model: interval − probe = 0.05; pause-after-probe: 0.15.
    import threading

    clock = {"t": 0.0}
    waits: list[float] = []

    class _Ev(threading.Event):
        def wait(self, timeout=None):  # type: ignore[override]
            waits.append(float(timeout))
            if len(waits) >= 4:
                self.set()
            return True

    real_event = threading.Event
    made = {"n": 0}

    def first_event_records():  # only the loop's own stop event; every other Event stays real
        made["n"] += 1
        return _Ev() if made["n"] == 1 else real_event()

    monkeypatch.setattr(qd.threading, "Event", first_event_records)
    monkeypatch.setattr(qd.time, "monotonic", lambda: clock["t"])

    def slow_generate():
        clock["t"] += 0.1
        return None

    monkeypatch.setattr(qd, "generate", slow_generate)
    stop = qd._start_probe_loop()
    # 1.6s, not 0.8s. The counts are what discriminate, and small counts flake: at 0.8s this asserted
    # >=4 against an expected 5 — a 20% margin that a loaded box (three pool dispatches running
    # alongside it, 2026-09-05) eats through thread-scheduling jitter alone, then reds a correct
    # implementation. Doubling the window doubles both predictions and widens the gap in absolute
    # terms: period 0.15 -> ~10 probes; pause-after-probe (0.15 + 0.1 per cycle) -> ~6. A floor of 7
    # sits 30% under the correct model and still above the wrong one, so the test discriminates
    # HARDER than it did while flaking less.
    # round-8 Opus finding: on a clean checkout the count sat at 6–7 (5 of 8 runs red) — the
    # floor discriminated nothing. Measure the quantity the loop CONTROLS: the gap between
    # probe starts is ~0.15 under the period model and ~0.25 under pause-after-probe; the
    # median sits 33 % from either, not on a count with no margin.
    for _ in range(200):
        if stop.is_set():
            break
        time.sleep(0.01)
    stop.set()
    assert len(waits) >= 4, waits
    assert all(abs(w - 0.05) < 1e-6 for w in waits[:4]), waits  # 0.15 − 0.1, never 0.15


# ── Commands tab (operator ask 2026-09-03; seen RED first) ─────────────────────────────────────


def test_description_parses_into_purpose_when_skip_stage(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    d = (
        'Do the thing — well. TRIGGER — EN: "do it", "make it"; TR: "yap". '
        "SKIP: undoing it (→ /fabrik-undo). Stage: 4-build."
    )
    p = qd._parse_description(d)
    assert p["purpose"] == "Do the thing — well."
    assert p["when"].startswith('EN: "do it"') and "yap" in p["when"]
    assert p["skip"].startswith("undoing it")
    assert p["stage"] == "4-build"
    bare = qd._parse_description("Just a purpose.")
    assert bare == {"purpose": "Just a purpose.", "when": "", "skip": "", "stage": ""}


def test_commands_table_covers_every_fabrik_source_in_pipeline_order(tmp_path, monkeypatch):
    """Denominator from the filesystem, never a hand count; order from PIPELINE_ORDER (CLAUDE.md
    § Pipeline) with the gates and utilities after the stages; NEXT from the assembler's map."""
    qd = _load(tmp_path, monkeypatch)
    sources = sorted(
        p.stem for p in (qd._FABRIK_ROOT / "commands" / "_sources").glob("fabrik-*.md")
    )
    cmds = qd._load_commands()
    assert [c["name"] for c in sorted(cmds, key=lambda c: c["name"])] == sources
    names = [c["name"] for c in cmds]
    # The table opens on the MULTI-EPIC front door (/fabrik-vision → epics → epics-review), then the
    # per-epic chain from /fabrik-rivals. This assertion read `names[0] == "fabrik-rivals"` until
    # b1f7e675 added those three sources with no PIPELINE_ORDER slot; the order below is the
    # placement, not merely the count.
    assert names[:3] == ["fabrik-vision", "fabrik-epics", "fabrik-epics-review"]
    assert names[3] == "fabrik-rivals" and names.index("fabrik-spec") < names.index(
        "fabrik-plan-review"
    )
    assert names.index("fabrik-deploy") < names.index("fabrik-deploy-verify")
    # operator ruling 2026-09-03: the contract freezes on the CERTIFIED build — after the gauntlets, before release
    assert (
        names.index("fabrik-service-test")
        < names.index("fabrik-deploy-checklist")
        < names.index("fabrik-release")
    )
    assert set(names) - set(qd.PIPELINE_ORDER) == set(), "every source has an explicit order slot"
    assert set(qd.PIPELINE_ORDER) - set(names) == set(), "no stale slot in PIPELINE_ORDER"
    by = {c["name"]: c for c in cmds}
    assert by["fabrik-deploy"]["next"].startswith("/fabrik-deploy-verify")
    assert by["fabrik-deploy-verify"]["stage"] == "6-release"
    assert by["fabrik-spec"]["when"] and by["fabrik-spec"]["purpose"]


def test_a_cached_pool_balance_does_not_freeze_the_board(tmp_path, monkeypatch):
    """Live 2026-09-06: `_pool_credits(now=None)` did `None - float(ts)` whenever the cache held a
    numeric ts — and NO caller ever passed `now`. From `_generate_locked` that TypeError took the
    render with it, and `_regen_async` runs generate() on a daemon thread that swallows the
    traceback, so the board silently froze at its last good page while claiming a 20s refresh."""
    qd = _load(tmp_path, monkeypatch)
    cache = tmp_path / "pool-credits.json"
    cache.write_text(
        json.dumps({"granted": 20.0, "used": 0.0, "remaining": 20.0, "ts": time.time()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(qd, "CREDITS_CACHE", cache)
    got = qd._pool_credits(fetch=False)  # no `now` — exactly how both real callers invoke it
    assert got and got["remaining"] == 20.0 and got["age_s"] >= 0.0


def test_a_broken_pool_balance_never_takes_the_board_down(tmp_path, monkeypatch):
    """The pool balance is a panel; the quota board is the reason the page exists. A raise in it is
    the Services view's pool error — the probe pass and the Accounts view never see it."""
    qd = _load(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise RuntimeError("pool exploded")

    monkeypatch.setattr(qd, "_pool_credits", boom)
    monkeypatch.setattr(qd, "_probe", _payload)
    assert qd.generate()["active"] == "mob"
    assert "mob@ocoron.com" in _accounts(qd)
    services = _text(_view(qd, "services"))
    assert "The pool balance could not be read: RuntimeError: pool exploded" in services
    assert "Search-API quotas" in services  # the rest of the view still renders


# ── Search-API quotas: brave · firecrawl · exa (operator ask 2026-09-07) ──────────────────────


def _quota_stub(qd, monkeypatch, *, brave_hdrs=None, fc_body=None, raise_for=()):
    """Replace the ONE network primitive. Every quota fetcher goes through `_get_json`, so a test
    never touches a provider — and neither does the render path, which is the point."""

    def fake(url, headers):
        for frag in raise_for:
            if frag in url:
                raise OSError("boom")
        if "search.brave.com" in url:
            return {}, brave_hdrs if brave_hdrs is not None else {}
        if "firecrawl" in url:
            return (fc_body if fc_body is not None else {}), {}
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(qd, "_get_json", fake)
    monkeypatch.setattr(qd, "_mcp_key", lambda *_a, **_k: "test-key")


_BRAVE_UNLIMITED = {
    "x-ratelimit-limit": "50, 0",
    "x-ratelimit-policy": "50;w=1, 0;w=2592000",
    "x-ratelimit-remaining": "49, 0",
    "x-ratelimit-reset": "1, 2079893",
}
_FC_OK = {
    "success": True,
    "data": {
        "remaining_credits": 2290,
        "plan_credits": 5000,
        "billing_period_start": "2026-08-12T12:16:19.000Z",
        "billing_period_end": "2026-09-12T12:16:19.000Z",
    },
}


def test_the_quota_views_refresh_themselves_every_20s(tmp_path, monkeypatch):
    """The board's cadence: the Overview and the Accounts view declare a 20 s refresh, which
    `app.js` reads off the fragment's root (the old page's meta refresh and its fixed 1600 px width
    were the five-tab page's; the shell's layout is the T01 stylesheet's, graded there)."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    qd._set_last_status(time.time(), _payload())
    assert qd.REFRESH_S == 20
    for name in ("overview", "accounts"):
        roots = [
            n.attrs.get("data-refresh-s")
            for n in _find(_dom(_view(qd, name)))
            if "data-refresh-s" in n.attrs
        ]
        assert roots and roots[0] == "20", (name, roots)


def _services_with(qd, monkeypatch, apis: dict) -> str:
    """The Services view as served, with ``apis`` as the search-API reading the cache holds (the
    real `_api_quotas` is put back after, so the test's later fetches are real)."""
    with monkeypatch.context() as m:
        m.setattr(qd, "_api_quotas", lambda *_a, **_k: apis)
        return _view(qd, "services")


def _api_row(markup: str, label: str) -> str:
    rows = [r.words() for r in _find(_dom(markup), "tr") if r.words().startswith(label)]
    assert len(rows) == 1, (label, rows)
    return rows[0]


def _firecrawl_row(qd, monkeypatch, now: float, **entry) -> str:
    apis = {"ts": now, "age_s": 1.0, "firecrawl": {"state": "ok", "unit": "credits", **entry}}
    return _api_row(_services_with(qd, monkeypatch, apis), "Firecrawl")


def test_braves_monthly_zero_means_unlimited_not_exhausted(tmp_path, monkeypatch):
    """THE trap in this feature, and it is live on this box today. Brave has no balance endpoint —
    the quota is the rate-limit header, comma-separated as "<per-second>, <monthly>", and our plan
    returns a monthly value of 0. The documentation says "15,000 requests per month (0 for
    unlimited)", so 0 is NO CAP. Read naively it renders as "0 remaining", painting a healthy
    unlimited plan as a dead one — a false alarm on the board the operator checks before working."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    _quota_stub(qd, monkeypatch, brave_hdrs=_BRAVE_UNLIMITED, fc_body=_FC_OK)
    now = time.time()
    q = qd._api_quotas(now)
    assert q["brave"]["unlimited"] is True
    assert q["brave"]["remaining"] is None and q["brave"]["total"] is None
    assert q["brave"]["per_second"] == 50
    brave = _api_row(_services_with(qd, monkeypatch, q), "Brave Search")
    assert "unlimited" in brave and "no monthly cap" in brave
    assert " 0 " not in f" {brave} " and "0 (0%)" not in brave, "an unlimited plan never reads 0"
    # a REAL cap still reports real numbers, and a low one is toned
    capped = dict(
        _BRAVE_UNLIMITED, **{"x-ratelimit-limit": "50, 15000", "x-ratelimit-remaining": "49, 900"}
    )
    _quota_stub(qd, monkeypatch, brave_hdrs=capped, fc_body=_FC_OK)
    (tmp_path / "q.json").unlink()
    qd._api_quotas_mem.clear()  # the in-memory TTL stamp (21eba0fb) outlives the disk cache
    q2 = qd._api_quotas(now)
    assert q2["brave"]["total"] == 15000 and q2["brave"]["remaining"] == 900
    assert ("critical", "900 (6%)") in _badges(_services_with(qd, monkeypatch, q2))  # 6% left


def test_the_reset_header_is_seconds_remaining_not_an_epoch(tmp_path, monkeypatch):
    """`X-RateLimit-Reset` is "Seconds until each quota resets". Treating it as a unix timestamp
    would date the renewal to 1970 and print a negative day count."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    _quota_stub(qd, monkeypatch, brave_hdrs=_BRAVE_UNLIMITED, fc_body=_FC_OK)
    now = time.time()
    q = qd._api_quotas(now)
    assert q["brave"]["renews_at"] == pytest.approx(now + 2079893, abs=2)
    assert "(24d)" in _api_row(_services_with(qd, monkeypatch, q), "Brave Search")
    # firecrawl's renewal is a real ISO date from the provider, not a computed offset
    assert q["firecrawl"]["renews_at"] == pytest.approx(
        datetime.fromisoformat("2026-09-12T12:16:19+00:00").timestamp(), abs=1
    )


def test_an_unwritable_cache_cannot_turn_the_ttl_into_the_probe_cadence(tmp_path, monkeypatch):
    """A metered-quota burn, reproduced before it was fixed and owed since the fleet-quota hold cut
    the round short (21eba0fb shipped the fix with this grader unwritten, and said so).

    `_refresh_pool_credits` calls `_api_quotas()` once per 20s probe cycle and leans on the TTL to
    gate the fetch — but the TTL was read only from the DISK cache. Make that cache unwritable (a
    stale directory in its place, a full disk, a permissions change) and every read misses, every
    cycle re-probes, and 1800s silently becomes 20s: 4,320 Brave queries a day instead of 48,
    against the one provider here that has no balance endpoint, so reading the quota SPENDS it —
    with nothing on the page or in the log to say so. Memory is the rate limiter; disk only carries
    the reading across a restart.
    """
    qd = _load(tmp_path, monkeypatch)
    blocked = tmp_path / "api-quotas.json"
    blocked.mkdir()  # a DIRECTORY where the cache file goes: every read and every write fails
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", blocked)
    # getattr, not attribute access: this must fail on the PROBE COUNT, not on an AttributeError.
    # Reverting the fix removes `_api_quotas_mem`, and a grader that dies at setup would also pass
    # for a version that kept the name and broke the gating — the mutation it exists to catch.
    getattr(qd, "_api_quotas_mem", {}).clear()
    calls: list[str] = []

    def counting(url, _headers):
        calls.append(url)
        return {"data": {"remaining_credits": 1, "plan_credits": 2}}, _BRAVE_UNLIMITED

    monkeypatch.setattr(qd, "_get_json", counting)
    monkeypatch.setattr(qd, "_mcp_key", lambda *_a, **_k: "k")
    now = time.time()
    for i in range(5):  # five refresher cycles, every one well inside a single TTL
        qd._api_quotas(now + i * 20)
    brave = [u for u in calls if "brave" in u]
    assert len(brave) == 1, (
        f"the TTL must hold without the disk — probed {len(brave)}x in one window, which at the "
        f"20s refresher cadence is {len(brave) / 5 * 3 * 60 * 24:.0f} Brave queries/day"
    )
    # ...and it must still probe once the window GENUINELY expires: a rate limiter that never
    # releases is a frozen panel, which is the other half of this board's recurring failure.
    qd._api_quotas(now + qd.API_QUOTAS_TTL_S + 60)
    assert len([u for u in calls if "brave" in u]) == 2


def test_a_refresh_mid_read_cannot_raise_on_the_render_path(tmp_path, monkeypatch):
    """Round 2, from an independent reader, and it is this board's oldest failure wearing new
    clothes. `_api_quotas(fetch=False)` builds `{**cached}` — which UNPACKS the in-memory dict — and
    the refresher thread does NOT hold `_gen_lock`. Mutating that dict in place (`clear()` then
    `update()`) mid-unpack raises "dictionary changed size during iteration" ON THE RENDER PATH,
    which is exactly how this page froze while advertising a 20s refresh. Rebinding is atomic: a
    reader gets the whole old dict or the whole new one."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    _quota_stub(qd, monkeypatch, brave_hdrs=_BRAVE_UNLIMITED, fc_body=_FC_OK)
    qd._api_quotas(time.time())  # prime memory with a big dict
    stop, errors = threading.Event(), []

    def reader():
        while not stop.is_set():
            try:
                qd._api_quotas(time.time(), fetch=False)
            except Exception as exc:  # noqa: BLE001 — recording is the whole point
                errors.append(exc)
                return

    def writer():
        for i in range(400):
            qd._api_quotas(time.time() + (i + 1) * qd.API_QUOTAS_TTL_S * 2)

    r = threading.Thread(target=reader, daemon=True)
    r.start()
    try:
        writer()
    finally:
        stop.set()
        r.join(timeout=5)
    assert not errors, f"the render path raised while the refresher rebuilt memory: {errors[:1]}"
    # ⚠️ the thread race above can MISS its window, so it cannot be the proof. The invariant that
    # makes the race impossible is deterministic and is what this asserts: a fetch REBINDS the
    # module attribute, so the dict a reader is unpacking is never the dict a writer touches.
    before = qd._api_quotas_mem
    snapshot = dict(before)
    qd._api_quotas(time.time() + qd.API_QUOTAS_TTL_S * 3)
    assert qd._api_quotas_mem is not before, "memory must be REBOUND, not mutated in place"
    assert before == snapshot, "the dict a reader may still hold must be left untouched"


def test_a_hand_edited_cache_timestamp_cannot_raise(tmp_path, monkeypatch):
    """Round 2. `float(cached["ts"])` on a non-numeric value raises ValueError — again on the render
    path, again a frozen board. The cache is a plain JSON file a human can edit, and `True` is an
    `int` in Python, so the numeric check has to exclude bool too."""
    qd = _load(tmp_path, monkeypatch)
    cache = tmp_path / "q.json"
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", cache)
    for junk in ('"soon"', "null", "true", "[]", '{"nested": 1}'):
        cache.write_text(f'{{"ts": {junk}, "brave": {{"state": "ok"}}}}', encoding="utf-8")
        # poison BOTH sides: an empty memory short-circuits the comparison, so a disk-only fixture
        # never reaches the conversion this test exists to guard
        monkeypatch.setattr(qd, "_api_quotas_mem", {"ts": json.loads(junk), "brave": {}})
        out = qd._api_quotas(time.time(), fetch=False)  # must NOT raise
        assert out.get("stale") is True, junk
    assert qd._stamp({"ts": True}) == 0.0, "bool is an int in Python; it is not a timestamp"
    assert qd._stamp({"ts": 5}) == 5.0 and qd._stamp({}) == 0.0


def test_a_page_wide_stale_reading_badges_its_rows(tmp_path, monkeypatch):
    """Round 2. `q["stale"]` is set only on the per-provider error-recovery path, so a whole
    reading an hour past its TTL rendered with no mark at all while the intro said "refreshed every
    30 min" — a fresh-looking panel of stale numbers, which is the silent half of this board's
    failure history."""
    qd = _load(tmp_path, monkeypatch)
    cache = tmp_path / "q.json"
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", cache)
    qd._api_quotas_mem.clear()
    old = time.time() - qd.API_QUOTAS_TTL_S * 4
    cache.write_text(
        json.dumps({"ts": old, "brave": {"state": "ok", "unlimited": True, "unit": "queries/mo"}}),
        encoding="utf-8",
    )
    q = qd._api_quotas(time.time(), fetch=False)
    assert q["stale"] is True
    marks = _badges(_view(qd, "services"))  # the real reader, fetch=False, off the cache above
    assert marks.count(("warning", "reading out of date")) == 3, marks  # every provider row


def test_impossible_numbers_are_shown_without_an_invented_percentage(tmp_path, monkeypatch):
    """Round 2, two readers. A provider can report remaining > total (a mid-period plan upgrade) or
    a negative remaining (permitted overage). Both rendered as a percentage: "6,000 (120%)" with a
    healthy green badge, and "-1 (-100%)". Neither is a number to act on."""
    qd = _load(tmp_path, monkeypatch)
    now = time.time()
    assert "(46%)" in _firecrawl_row(qd, monkeypatch, now, total=5000, remaining=2290)  # ordinary
    over = _firecrawl_row(qd, monkeypatch, now, total=5000, remaining=6000)
    assert "120%" not in over and "6,000" in over
    under = _firecrawl_row(qd, monkeypatch, now, total=5000, remaining=-1)
    assert "-1" in under and "%" not in under.split("credits", 1)[1]
    # a renewal already in the past is not a renewal
    past = _firecrawl_row(qd, monkeypatch, now, total=5, remaining=1, renews_at=now - 3 * 86400)
    assert "overdue" in past and "-3d" not in past


def test_a_partial_or_junk_provider_header_keeps_the_rest_of_the_reading(tmp_path, monkeypatch):
    """Closing round. `limit` was length-checked; `remaining` and `reset` are SEPARATE headers and
    were not. A plan sending only the per-second element raised IndexError, a non-numeric element
    raised ValueError, and either discarded the WHOLE Brave reading — plan, rate and renewal — over
    one missing field, leaving the panel stuck on "probe failed" until the provider behaved."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    assert qd._hdr_int(["50", "0"], 1) == 0 and qd._hdr_int(["50"], 1) is None
    assert qd._hdr_int(["50", "soon"], 1) is None and qd._hdr_int([], 0) is None
    for hdrs in (
        {
            "x-ratelimit-limit": "50, 15000",
            "x-ratelimit-remaining": "49",
            "x-ratelimit-reset": "1, 900",
        },  # remaining truncated
        {
            "x-ratelimit-limit": "50, 15000",
            "x-ratelimit-remaining": "49, soon",
            "x-ratelimit-reset": "1, 900",
        },  # remaining non-numeric
        {
            "x-ratelimit-limit": "50, 15000",
            "x-ratelimit-remaining": "49, 900",
            "x-ratelimit-reset": "1",
        },  # reset truncated
    ):
        _quota_stub(qd, monkeypatch, brave_hdrs=hdrs, fc_body=_FC_OK)
        qd._api_quotas_mem.clear()
        (tmp_path / "q.json").unlink(missing_ok=True)
        q = qd._api_quotas(time.time())
        assert q["brave"]["state"] == "ok", f"one bad field must not discard the reading: {hdrs}"
        assert q["brave"]["total"] == 15000 and q["brave"]["per_second"] == 50


def test_a_future_stamp_or_a_junk_renewal_date_cannot_raise_or_read_as_fresh(tmp_path, monkeypatch):
    """Closing round, two readers. `age_s` was never gated against a ts in the FUTURE, so a clock
    jump or a restored snapshot rendered "read -1218540 min ago". And `renews_at` is read straight
    out of the hand-editable cache — a string there raised TypeError on the render path, the same
    class already closed for `ts`, one field over."""
    qd = _load(tmp_path, monkeypatch)
    now = time.time()
    intro = _text(_services_with(qd, monkeypatch, {"ts": now + 9999, "age_s": -9999}))
    assert "stamped in the future" in intro and "-1" not in intro.split("Service")[0]
    for junk in ("bad", None, True, [], {}, 10**20):
        row = _firecrawl_row(qd, monkeypatch, now, total=5, remaining=1, renews_at=junk)
        assert row.startswith("Firecrawl"), junk  # rendered, not raised
    # ...and a PROVIDER ENTRY that is not a dict at all. A partial write or a hand edit makes
    # `quotas["brave"]` a list, and `q.get("state")` on a list is an AttributeError on the render
    # path — the same untrusted-value class as `ts` and `renews_at`, one level in.
    for junk in (["malformed"], "ok", 7, None, True):
        apis = {"ts": now, "age_s": 1.0, "brave": junk}
        assert "not read yet" in _api_row(_services_with(qd, monkeypatch, apis), "Brave Search")


def test_the_render_path_never_makes_a_network_call(tmp_path, monkeypatch):
    """Same rule the pool balance learned the hard way: a third-party endpoint on the render path
    is how this board froze. `fetch=False` must read the cache and nothing else."""
    qd = _load(tmp_path, monkeypatch)
    cache = tmp_path / "q.json"
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", cache)

    def explode(*_a, **_k):
        raise AssertionError("the render path made a network call")

    monkeypatch.setattr(qd, "_get_json", explode)
    assert qd._api_quotas(time.time(), fetch=False)["ts"] is None  # no cache, still no call
    cache.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "firecrawl": {"state": "ok", "total": 5000, "remaining": 10, "unit": "credits"},
            }
        ),
        encoding="utf-8",
    )
    q = qd._api_quotas(time.time(), fetch=False)
    assert q["firecrawl"]["remaining"] == 10
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    for name in qd._views.VIEWS:  # every view of the board, still no call
        assert "data-view-root" in _view(qd, name)


def test_one_dead_provider_does_not_blank_the_other_two(tmp_path, monkeypatch):
    """Three independent services owe three independent verdicts. A single `except` around the loop
    would turn one provider's outage into a blank panel — the shape this board keeps re-learning."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    _quota_stub(
        qd, monkeypatch, brave_hdrs=_BRAVE_UNLIMITED, fc_body=_FC_OK, raise_for=("firecrawl",)
    )
    now = time.time()
    q = qd._api_quotas(now)
    assert q["brave"]["state"] == "ok", "brave must survive firecrawl being down"
    assert q["firecrawl"]["state"] == "error" and q["firecrawl"]["error"] == "OSError"
    html_ = _services_with(qd, monkeypatch, q)
    assert "unlimited" in _api_row(html_, "Brave Search")
    assert "probe failed (OSError)" in _api_row(html_, "Firecrawl")


def test_exas_unavailability_is_stated_not_blank(tmp_path, monkeypatch):
    """Exa exposes no balance to a search key: the usage API needs a team-management SERVICE key
    (ours gets 403) and returns spend, never a balance or a renewal. A blank row would read as
    "nothing to report"; the operator needs to know it is unknowable, and why."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    _quota_stub(qd, monkeypatch, brave_hdrs=_BRAVE_UNLIMITED, fc_body=_FC_OK)
    now = time.time()
    exa = _api_row(_services_with(qd, monkeypatch, qd._api_quotas(now)), "Exa")
    assert "SERVICE key" in exa and "403" in exa
    # the stub configures every key (exa included): the row states WHY it is unknowable
    assert "returns spend, not a balance" in exa
    # and an absent key is a DIFFERENT verdict from an unavailable API — stated too. The disk
    # cache AND the in-memory TTL stamp (21eba0fb) must both go, or the configured row is served
    monkeypatch.setattr(qd, "_mcp_key", lambda *_a, **_k: None)
    (tmp_path / "q.json").unlink()
    qd._api_quotas_mem.clear()
    exa = _api_row(_services_with(qd, monkeypatch, qd._api_quotas(now)), "Exa")
    assert "no API key configured" in exa


def test_no_api_key_ever_reaches_the_page(tmp_path, monkeypatch):
    """The board reads three secrets out of the MCP configs. None may be rendered — the existing
    contract for the OpenRouter key, extended to the three that just joined it."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "API_QUOTAS_CACHE", tmp_path / "q.json")
    secret = "sk-do-not-render-me-12345"
    monkeypatch.setattr(qd, "_mcp_key", lambda *_a, **_k: secret)
    _quota_stub(qd, monkeypatch, brave_hdrs=_BRAVE_UNLIMITED, fc_body=_FC_OK)
    monkeypatch.setattr(qd, "_mcp_key", lambda *_a, **_k: secret)
    now = time.time()
    qd._api_quotas(now)
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    for name in qd._views.VIEWS:
        assert secret not in _view(qd, name), name
    assert secret not in qd._shell_page()
    assert secret not in (tmp_path / "q.json").read_text(encoding="utf-8")


# ── External-services matrix (operator ask 2026-09-06; seen RED first) ─────────────────────────


def _rendered(tmp_path: Path, name: str, body: str) -> Path:
    d = tmp_path / "rendered"
    d.mkdir(exist_ok=True)
    (d / f"{name}.md").write_text(body, encoding="utf-8")
    return d


def test_the_matrix_reads_the_rendered_corpus_not_the_sources(tmp_path, monkeypatch):
    """THE load-bearing behaviour. `assemble_commands.py` appends the shared pool and mail
    fragments, so a source-only read under-reports the pool by ~9 commands and fabrik-mail by 34
    (measured 2026-09-06). A command whose SOURCE never says `fanout(` still reaches the pool once
    rendered — the dot must follow the rendered text."""
    qd = _load(tmp_path, monkeypatch)
    name = sorted(p.stem for p in (qd._FABRIK_ROOT / "commands" / "_sources").glob("fabrik-*.md"))[
        0
    ]
    src = (qd._FABRIK_ROOT / "commands" / "_sources" / f"{name}.md").read_text(encoding="utf-8")
    assert "verify_citation" not in src, "fixture assumes the source does NOT reach the verifier"
    monkeypatch.setattr(
        qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, src + "\nrun verify_citation() here\n")
    )
    services, is_rendered = qd._command_services(name)
    assert is_rendered and "cit" in services
    # and with no rendered file the row falls back to the source, DECLARED, never silently
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", tmp_path / "absent")
    services, is_rendered = qd._command_services(name)
    assert not is_rendered and "cit" not in services
    # ⚠️ the assertion above is NEGATIVE, and an empty set satisfies it — so it alone would let a
    # mutation that DELETES the source fallback pass. Pin the POSITIVE half on a source that
    # genuinely matches: 28 of the 35 do (measured 2026-09-06), and this test FOUND that the first
    # one alphabetically is not among them — the shared pool and mail fragments the sources lack
    # are exactly what the assembler adds, which is the feature's whole premise.
    # The board blanks HTML comments (acffe9c1d: a commented pool contract must never light a dot)
    # and the shared boilerplate (1720d62f6) before matching, so the oracle reads each source the same
    # way — straight from the file, never through the fallback under test.
    src_dir = qd._FABRIK_ROOT / "commands" / "_sources"

    def _live(f: Path) -> str:
        text = qd._HTML_COMMENT_RE.sub("", f.read_text(encoding="utf-8"))
        for rx in qd._BOILERPLATE:
            text = rx.sub("", text)
        return text

    hits = {
        f.stem: {k for k, rx in qd._EXT_COMPILED if rx.search(_live(f))}
        for f in sorted(src_dir.glob("fabrik-*.md"))
    }
    rich = next(n for n, s in hits.items() if s)
    services, is_rendered = qd._command_services(rich)
    assert not is_rendered and services == hits[rich] and services, (
        "the source fallback must READ the source, not merely report un-rendered"
    )


def test_a_prose_mention_is_not_a_dot(tmp_path, monkeypatch):
    """The defect that made the first draft useless: `VPS`, `GitHub` and `flywheel` all appear in
    the beat-routing table every rendered command carries, so a prose match rated all 36 commands
    as VPS-touching. Only the service's own INVOCATION token counts."""
    qd = _load(tmp_path, monkeypatch)
    prose = (
        "the VPS git pulls from the GitHub remote; intel owns models, benchmarks, the flywheel, "
        "and an exact firecrawl-free reading of the pool"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, "fabrik-spec", prose))
    assert qd._command_services("fabrik-spec")[0] == set()
    invocations = "run `fabrik apply specs/services/x.yaml`, then gh pr create, then fanout( ... )"
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, "fabrik-spec", invocations))
    assert qd._command_services("fabrik-spec")[0] == {"vps", "gh", "pool"}


def test_a_corrupt_or_unreadable_command_file_never_takes_the_board_down(tmp_path, monkeypatch):
    """Round 3, from an independent reader. `read_text` raises UnicodeDecodeError — a ValueError,
    NOT an OSError — on a single non-UTF-8 byte, and the `except OSError` did not catch it. That is
    the THIRD instance in this file of the one failure that matters here: a raise on the render path
    reaches the regeneration thread and the board stops updating while its header still advertises a
    20s refresh. Both reads are covered: the services scan and the description parse."""
    qd = _load(tmp_path, monkeypatch)
    d = tmp_path / "rendered"
    d.mkdir()
    name = sorted(p.stem for p in (qd._FABRIK_ROOT / "commands" / "_sources").glob("fabrik-*.md"))[
        0
    ]
    (d / f"{name}.md").write_bytes(b"description: x\nfanout( \xff\xfe not utf-8\n")
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", d)
    services, is_rendered = qd._command_services(name)  # must NOT raise
    assert not is_rendered, "an undecodable rendered file falls through to the source"
    qd._cmd_cache_key = None
    assert len(qd._load_commands()) > 0  # the whole board survives it
    # and the DESCRIPTION read is guarded too — same class, previously unguarded entirely
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: (_ for _ in ()).throw(UnicodeDecodeError("utf-8", b"", 0, 1, "x")),
    )
    qd._cmd_cache_key = None
    rows = qd._load_commands()
    assert len(rows) > 0 and all(r["purpose"] == "" for r in rows)


def _commands(qd) -> str:
    return _view(qd, "commands")


def _matrix_rows(markup: str) -> list[list[str]]:
    """The service matrix's body rows as cell words (the first cell is the command)."""
    region = _find(_dom(markup), "div", aria_labelledby="commands-matrix-table")
    assert len(region) == 1
    return [
        [c.words() for c in r.children if c.tag in ("th", "td")]
        for r in _find(region[0], "tr")
        if any(c.tag == "td" for c in r.children)
    ]


def test_the_matrix_is_in_the_commands_view_and_names_its_maintenance_point(tmp_path, monkeypatch):
    """The operator's second ask: a note that says how this is kept current. The registry name and
    its file must be ON THE PAGE — a maintenance contract only in a code comment is unfindable."""
    qd = _load(tmp_path, monkeypatch)
    html_ = _commands(qd)
    tab = _find(_dom(html_), "button", role="tab", id="tab-commands-matrix")
    assert tab and tab[0].words() == "Service matrix"
    assert _find(_dom(html_), "div", aria_labelledby="commands-matrix-table")
    text = _text(html_)
    assert "_EXT_SERVICES" in text and "scripts/sysadmin/quota_dashboard.py" in text
    # R2, all three independent readers: the opening sentence used to assert the data came from the
    # rendered corpus unconditionally, which a missing or PARTIAL render made false two sentences
    # before the caveat said otherwise. It must state how many rows actually came from there.
    rows = qd._load_commands()
    n_r = sum(1 for r in rows if r["rendered"])
    assert f"{n_r} of {len(rows)} rows from the rendered" in text


def test_the_views_are_six_in_navigation_order_and_the_commands_list_every_source(
    tmp_path, monkeypatch
):
    """The five tabs became six views behind one navigation (spec § Information architecture): the
    Overview first, then Work (today's Repos tab), Accounts (Quota), Usage, Commands, Services
    (External). A link or a reload lands where it was — the hash names the view (`app.js`)."""
    qd = _load(tmp_path, monkeypatch)
    nav = _find(_dom(qd._shell_page()), "a")
    assert [(a.attrs.get("data-nav"), a.words()) for a in nav if "data-nav" in a.attrs] == [
        ("overview", "Overview"), ("work", "Work"), ("accounts", "Accounts"),
        ("usage", "Usage"), ("commands", "Commands"), ("services", "Services"),
    ]  # fmt: skip
    assert [a.attrs.get("href") for a in nav if "data-nav" in a.attrs][0] == "#overview"
    commands = _commands(qd)
    listing = _find(_dom(commands), "div", aria_labelledby="commands-table")[0]
    body_rows = [r for r in _find(listing, "tr") if any(c.tag == "td" for c in r.children)]
    assert len(body_rows) == len(qd._load_commands())
    heads = [h.words() for h in _find(listing, "th", scope="col")]
    for col in ("Command", "Stage", "Purpose", "When to use", "Skip when", "Next"):
        assert col in heads, col


def _pool_view(qd, monkeypatch, credits: dict) -> str:
    with monkeypatch.context() as m:
        m.setattr(qd, "_pool_credits", lambda *_a, **_k: credits)
        return _view(qd, "services")


def test_the_pool_balance_shows_once_on_the_services_view(tmp_path, monkeypatch):
    """Operator, 2026-09-04, looking at #external: "i dont see it here?" — the external-services
    tab is where a person asks "is my third-party spend OK", so the balance went there too and sat
    on two tabs. The redesign shows it ONCE (spec § Information architecture: Services, "shown
    ONCE"), on the Services view beside the search-API quotas and the external-services page."""
    qd = _credits_env(tmp_path, monkeypatch)
    c = {"granted": 245.0, "used": 225.87, "remaining": 19.13, "age_s": 0.0, "stale": False}
    monkeypatch.setattr(qd, "_pool_credits", lambda *_a, **_k: c)
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    seen = {name: _text(_view(qd, name)).count("OpenRouter pool") for name in qd._views.VIEWS}
    assert seen["services"] == 1, seen
    assert sum(seen.values()) == 1, "exactly one view carries the balance"


def _usage(qd) -> str:
    return _view(qd, "usage")


def test_an_unreadable_sidecar_is_said_never_a_zeroed_table(tmp_path, monkeypatch):
    """No file, bad JSON: the Usage view says it could not read the sidecar, in words, and shows no
    table — a zeroed one would read as "we spent nothing this month". (The old tab rendered an empty
    pane; the redesign gives every region an error state, spec § Lifecycle, Degradation.)"""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_COST_SIDECAR", tmp_path / "does-not-exist.json")
    for _case in ("missing", "bad json"):
        html_ = _usage(qd)
        assert "The spend sidecar could not be read" in _text(html_), _case
        assert 'data-state="error"' in html_ and "<table" not in html_
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(qd, "_COST_SIDECAR", bad)


def _pending_view(qd, monkeypatch, payload: dict) -> str:
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    qd._set_last_status(time.time(), payload)
    return _accounts(qd)


def test_a_negated_mention_is_the_limit_the_page_declares(tmp_path, monkeypatch):
    """Round 3. The ONLY `cit` match in the live corpus was fabrik-data-contract saying the
    verifier "does not apply here" — the whole column was one negation. A regex cannot read
    negation, so two things had to change: the bare SERVER NAME came out of that pattern (the tool
    token is the invocation; the server name is prose about it), and the page now STATES the limit
    instead of claiming a precision the method does not have."""
    qd = _load(tmp_path, monkeypatch)
    d = tmp_path / "rendered"
    d.mkdir()

    def services(body: str) -> set:
        (d / "fabrik-spec.md").write_text(body, encoding="utf-8")
        monkeypatch.setattr(qd, "RENDERED_COMMANDS", d)
        return qd._command_services("fabrik-spec")[0]

    assert services("the `fabrik-citation-verifier` MCP does not apply here") == set()
    assert "cit" in services("call verify_citation(doi) on every claim")
    assert "cit" in services("mcp__fabrik-citation-verifier__verify_batch")
    # the corpus's own browser tools are only two of ~20 the MCP exposes; the next one used must
    # not be a silent miss
    assert "brw" in services("then browser_take_screenshot to prove it rendered")
    assert "brw" in services("browser_navigate to the page")
    # and the honest limit is ON THE PAGE (the Commands view's matrix intro), not only in a comment
    intro = _text(_commands(qd))
    assert "reads no negations" in intro and "preserves both is invisible" in intro
    # R6: "cannot go stale against the corpus" survived round 5 and sat one clause from the sentence
    # explaining exactly how it CAN — an absolute claim next to its own counterexample.
    assert "cannot go stale" not in intro


def test_an_unreadable_pool_balance_says_so_on_the_page(tmp_path, monkeypatch):
    """Round 4. Guarding the render stopped the board dying, but the panel then vanished — and "no
    panel" already means "the pool is not configured on this box". A fault that renders identically
    to a deliberate absence, traceable only in a log nobody reads, is the exact shape of the freeze
    this file was carrying. The board must SAY it, and must not print a zero the operator would act
    on. Since the redesign the Services view says it, as that region's error state."""
    qd = _load(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(qd, "_pool_credits", boom)
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    assert "mob@ocoron.com" in _accounts(qd)  # the board still stands
    services = _text(_view(qd, "services"))
    assert "The pool balance could not be read: PermissionError" in services
    assert "$0.00" not in services, "a missing balance must not read as an exhausted one"
    # and a pool that is simply NOT CONFIGURED says that instead — the two are different
    monkeypatch.setattr(qd, "_pool_credits", lambda *a, **k: None)
    unconfigured = _text(_view(qd, "services"))
    assert "could not be read" not in unconfigured and "not configured on this box" in unconfigured


def test_every_registered_detector_is_pinned_by_a_positive_probe(tmp_path, monkeypatch):
    """Round 4. Only gh / brw / cit had positive assertions, so deleting any OTHER pattern's
    alternation — `firecrawl_[a-z]`, `search_chats`, `pick_models(` — would have passed the suite.
    One probe per registered key, derived from the token each column claims to detect."""
    qd = _load(tmp_path, monkeypatch)
    d = tmp_path / "rendered"
    d.mkdir()
    # ⚠️ ONE PROBE PER ALTERNATION ARM, not per key. A combined probe ("fabrik apply ... ssh vps1")
    # still lights the key after an arm is deleted, so it grades nothing: dropping the whole
    # `fabrik (apply|redeploy|…)` branch — 55 live matches — used to pass.
    probes = {
        "pool": [
            "fanout(",
            "pick_models(",
            "from libs.subagents import x",
            "import libs.subagents",
        ],
        "rec": ["search_chats", "recent_chats", "mcp__session-recall", "the session-recall MCP"],
        "web": ["WebSearch", "WebFetch"],
        "brv": ["brave_web_search", "brave-web-search", "mcp__brave-search", "brave-search"],
        # two members per CHARACTER-CLASS arm: one literal cannot pin `firecrawl_[a-z]`'s
        # generality, and a mutation narrowing the arm to that literal would pass (round 6)
        "fc": ["firecrawl_search", "firecrawl_extract", "mcp__firecrawl"],
        "exa": ["web_search_exa", "web_fetch_exa", "mcp__exa"],
        "brw": [
            "mcp__playwright",
            "mcp__chrome-devtools",
            "`playwright`",
            "`chrome-devtools`",
            "@axe-core/playwright",
            "browser_navigate",
            "browser_take_screenshot",
            "browser_press_key",
            "fabrik-gui",
        ],
        "gh": [
            "gh pr x",
            "gh issue x",
            "gh api x",
            "gh repo x",
            "gh release x",
            "gh run x",
            "gh search x",
            "gh browse x",
            "gh workflow x",
            "gh auth x",
        ],
        "vps": [
            "fabrik apply x",
            "fabrik redeploy x",
            "fabrik plan x",
            "fabrik destroy x",
            "fabrik status x",
            "ssh vps",
            "ssh root@h",
            "deployer_ssh",
            "vps1",
            "vps2",
            "vps3",
        ],
        "aic": ["ai-consult", "ai_consult"],
        "cit": [
            "verify_citation(doi)",
            "verify_batch(",
            "mcp__fabrik-citation-verifier__verify_citation",
        ],
        "mail": ["scripts/mail.py", "mail.py send"],
        "fly": ["record_agent_run(spec, r)", "set_quality(r.agent_id, 5)"],
    }
    registered = {k for k, _l, _t, _p in qd._EXT_SERVICES}
    assert set(probes) == registered, (
        "a new registry row needs its arms probed here — that is the point"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", d)
    for key, arms in probes.items():
        for text in arms:
            (d / "fabrik-spec.md").write_text(text, encoding="utf-8")
            got = qd._command_services("fabrik-spec")[0]
            assert key in got, f"{key}: arm {text!r} does not light it (-> {sorted(got)})"
    # and the mirror the class keeps re-teaching: a bare module PATH is prose, not a call
    (d / "fabrik-spec.md").write_text("see `libs/subagents` for the autoloader", encoding="utf-8")
    assert qd._command_services("fabrik-spec")[0] == set()


def test_the_service_registry_is_well_formed(tmp_path, monkeypatch):
    """The registry is the ONE hand-held fact — a duplicate key would silently drop a column and a
    bad pattern would take the whole board down at import."""
    qd = _load(tmp_path, monkeypatch)
    keys = [k for k, _l, _t, _p in qd._EXT_SERVICES]
    assert len(keys) == len(set(keys)) and len(keys) >= 10
    for key, label, title, pat in qd._EXT_SERVICES:
        assert key and label and title, key
        re.compile(pat)
    assert {"pool", "mail", "web"} <= set(keys), "the three most-used services stay registered"
    # The column HEAD is what the operator reads; the key is what the code joins on. They were the
    # same three-letter string until the operator asked why a 1600px-wide table was squeezed into
    # "fly / rec / brv / fc / brw / aic / cit" — the abbreviations were an unchecked assumption
    # about width, not a constraint. Labels are words now, and nothing but the KEY may shrink again.
    for key, label, _title, _pat in qd._EXT_SERVICES:
        assert len(label) >= 3, key
        assert label.lower() == key or len(label) > len(key), (
            f"{key}: the column head must not re-abbreviate"
        )
    # A hand-edited title or label carrying markup is TEXT on the page: every value goes through
    # a component, which escapes it (INV-4).
    hostile = '"><script>alert(1)</script>'
    monkeypatch.setattr(qd, "_EXT_SERVICES", ((("x", hostile, hostile, "zzz"),)))
    html_ = _commands(qd)
    assert "<script>" not in html_ and "&quot;&gt;&lt;script&gt;" in html_


def test_every_command_gets_a_matrix_row_and_the_totals_carry_their_denominator(
    tmp_path, monkeypatch
):
    """A count with no denominator is indistinguishable from having looked at nothing
    (CLAUDE.md § HARD STOPS), so the footer states `of N` and each total is re-derived here."""
    qd = _load(tmp_path, monkeypatch)
    rows = qd._load_commands()
    body = _matrix_rows(_commands(qd))
    *per_command, totals = body
    assert [r[0] for r in per_command] == [f"/{r['name']}" for r in rows]
    assert totals[0] == f"of {len(rows)}"
    for i, (key, _l, _t, _p) in enumerate(qd._EXT_SERVICES, 1):
        assert totals[i] == str(sum(1 for r in rows if key in r["services"])), key
    # the live corpus must actually exercise the matrix — an all-blank grid would pass every
    # assertion above and tell the operator nothing
    assert sum(len(r["services"]) for r in rows) > len(rows), "the live corpus reaches services"


def test_an_unrendered_corpus_is_declared_never_silently_underreported(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", tmp_path / "absent")
    qd._cmd_cache_key = None
    rows = qd._load_commands()
    intro = _text(_commands(qd))
    assert "UNDER-report" in intro and f"{len(rows)} of {len(rows)} rows did NOT come" in intro
    # R4: the headline used to say "derived on EVERY PAGE LOAD", which the mtime cache makes false
    # on every hit — a claim the page cannot support about its own machinery
    assert "every page load" not in intro
    # and the headline claim agrees with the caveat rather than contradicting it
    assert f"0 of {len(rows)} rows from the rendered" in intro
    # and it NAMES them: "N of N fell back" without saying WHICH is a number the operator cannot act
    # on, and a row whose source ALSO failed to open would otherwise be reported as read from
    # `_sources/` — a claim about a file that was never opened
    assert rows[0]["name"] in intro
    # a fully rendered corpus carries no caveat
    for r in rows:
        r["rendered"] = True
    monkeypatch.setattr(qd, "_load_commands", lambda: rows)
    assert "UNDER-report" not in _text(_commands(qd))


def test_a_vanishing_rendered_file_re_keys_instead_of_raising(tmp_path, monkeypatch):
    """Round 1, from an independent reader. `exists()`-then-`stat()` raced the ONE writer that
    prunes this directory: `assemble_commands.py` unlinks stale commands mid-render. The raise came
    out of `_load_commands` -> `render` -> `generate` on `_regen_async`'s daemon thread, which is
    exactly the shape that froze this board earlier today — a page that stops updating and says
    nothing. Absence must be a KEY VALUE, not an omitted entry, or a file appearing and vanishing
    could leave the key unchanged."""
    qd = _load(tmp_path, monkeypatch)
    missing = tmp_path / "gone.md"
    assert qd._mtime_key(missing) == (str(missing), -1, -1)
    present = tmp_path / "here.md"
    present.write_text("x", encoding="utf-8")
    assert qd._mtime_key(present)[1] > 0 and qd._mtime_key(present)[2] == 1
    # R2: SIZE is in the key because mtime alone cannot see a timestamp-preserving rewrite
    # (`cp -p`, a restore, an archive extraction) — a real shape for a corpus that is regenerated.
    before = qd._mtime_key(present)
    present.write_text("xxxx", encoding="utf-8")
    import os as _os

    _os.utime(present, ns=(before[1], before[1]))
    assert qd._mtime_key(present) != before, "a same-mtime rewrite must still re-key"
    # a directory in the file's place, and an unreadable parent, are OSErrors too — never a raise
    d = tmp_path / "adir"
    d.mkdir()
    assert qd._mtime_key(d / "under-a-dir" / "x.md") == (str(d / "under-a-dir" / "x.md"), -1, -1)
    # and the whole load survives a rendered corpus that is not there at all
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", tmp_path / "never-rendered")
    qd._cmd_cache_key = None
    assert len(qd._load_commands()) > 0
    # THE RACE ITSELF, which an `exists()` pre-check cannot close. Note the fixture shape: a stat
    # that ALWAYS raises makes `exists()` return False (it stats once and swallows OSError), so the
    # file is merely skipped and nothing reproduces. The real window is exists() SUCCEEDING and the
    # caller's own stat() then failing — hence first-call-ok, second-call-raises. The old call site
    # let that FileNotFoundError out of _load_commands, and the regen thread turned it into a board
    # that stopped updating while its header still advertised a 20s refresh.
    src = qd._FABRIK_ROOT / "commands" / "_sources"
    victim = sorted(src.glob("fabrik-*.md"))[0]
    real_stat = Path.stat
    seen: list[str] = []

    def flaky(self, *a, **kw):
        if str(self) == str(victim):
            seen.append("x")
            if len(seen) > 1:
                raise FileNotFoundError(2, "No such file or directory", str(self))
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(Path, "stat", flaky)
    qd._cmd_cache_key = None
    rows = qd._load_commands()  # must NOT raise
    assert len(rows) > 0 and any(r["name"] == victim.stem for r in rows)
    # `seen` is deliberately NOT asserted > 1: the fix makes exactly ONE stat per file, so a second
    # call happens only on the buggy path. That asymmetry IS the grader — one call here, red there.
    assert len(seen) == 1, "the fixed key must stat each file once, not pre-check then stat"


def test_the_detectors_catch_the_invocation_forms_the_live_corpus_actually_uses(
    tmp_path, monkeypatch
):
    """Round 1: two FALSE NEGATIVES, both found by re-deriving each column against the live corpus
    instead of trusting the pattern. `gh search` was outside a hand-listed alternation, and the
    browser MCPs are named in backticks (`playwright`, `chrome-devtools`) far more often than as
    `mcp__` tool ids. The mirror matters as much: bare "Browserless"/"Gotenberg" is a fleet SERVICE
    a project may deploy — prose about someone else's architecture — and must NOT earn a dot."""
    qd = _load(tmp_path, monkeypatch)
    d = tmp_path / "rendered"
    d.mkdir()

    def services(body: str) -> set:
        (d / "fabrik-spec.md").write_text(body, encoding="utf-8")
        monkeypatch.setattr(qd, "RENDERED_COMMANDS", d)
        return qd._command_services("fabrik-spec")[0]

    assert "gh" in services("use `gh search repos --language=python` for prior art")
    # R2: the alternation used to demand a TRAILING SPACE, so the same invocation at end of line or
    # before punctuation was a silent miss. The boundary must be \b, and it must still refuse a
    # longer word that merely starts with a subcommand.
    assert "gh" in services("check prior art with gh search")
    assert "gh" in services("run `gh pr create`.")
    assert services("the gh apiary sample, gh runner notes, and ghost writing") == set()
    assert "brw" in services("drive it with `playwright`")
    assert "brw" in services("the `chrome-devtools` MCP")
    assert "brw" in services("run @axe-core/playwright over the screen")
    assert services("the stack deploys Gotenberg/Browserless behind Traefik") == set()


def test_a_rerendered_corpus_invalidates_the_cache(tmp_path, monkeypatch):
    """The rows are cached on mtimes; the rendered corpus can be rewritten by the assembler with
    no `_sources/` mtime moving, so the dots would freeze at the previous render."""
    qd = _load(tmp_path, monkeypatch)
    names = sorted(p.stem for p in (qd._FABRIK_ROOT / "commands" / "_sources").glob("fabrik-*.md"))
    d = tmp_path / "rendered"
    d.mkdir()
    for n in names:
        (d / f"{n}.md").write_text("nothing external here\n", encoding="utf-8")
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", d)
    qd._cmd_cache_key = None
    assert sum(len(r["services"]) for r in qd._load_commands()) == 0
    (d / f"{names[0]}.md").write_text("now it calls fanout(...)\n", encoding="utf-8")
    assert "pool" in {s for r in qd._load_commands() for s in r["services"]}


def test_commands_cache_follows_the_assembler_and_an_empty_corpus_is_said(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    qd._load_commands()
    key1 = qd._cmd_cache_key
    # keyed on the FULL path since 2026-09-06: source and rendered files share basenames, and the
    # rendered corpus (which the external-services matrix reads) must be in the key too
    assert key1 and any(e[0].endswith("/assemble_commands.py") for e in key1)
    assert any(e[0].startswith(str(qd.RENDERED_COMMANDS) + "/") for e in key1)
    monkeypatch.setattr(qd, "_FABRIK_ROOT", tmp_path / "nowhere")
    assert qd._load_commands() == []
    assert "Command corpus unreadable" in _text(_commands(qd))


# ── The external-services inventory in the Services view (plan 2026-10-18-plan-1, T04) ──────────
# The registry is read by a child process (scripts/sysadmin/inventory_read.py) the collector spawns and
# kills at the read's deadline. Every test here uses the shared isolation's stub spawn or a fake child
# of its own; the two that run the REAL child point it at a socket that never answers or at a script
# that never ends. No test reads the real registry.


class _Ctx:
    now = 0.0


def _inv_data(qd):
    return qd._inventory(_Ctx())


class _FakeChild:
    """A child that answers when released, never when not, and ends when killed — the three things
    the collector's waiter thread asks of a ``Popen``."""

    def __init__(
        self, stdout: bytes = b"", code: int = 0, *, answers: bool = True, at_once: bool = False
    ):
        import threading

        self.stdout, self.code, self.answers = stdout, code, answers
        self.wake = threading.Event()
        if at_once:
            self.wake.set()
        self.killed = threading.Event()
        self.returncode = None

    def release(self) -> None:
        self.wake.set()

    def communicate(self, timeout=None):
        if not self.killed.is_set():
            self.wake.wait(timeout)
        if self.killed.is_set():
            self.returncode = -9
            return b"", b""
        if not (self.wake.is_set() and self.answers):
            raise subprocess.TimeoutExpired("inventory_read", timeout or 0)
        self.returncode = self.code
        return self.stdout, b""

    def kill(self) -> None:
        self.killed.set()
        self.wake.set()


def _fake_children(qd, monkeypatch, **kw):
    spawned: list[_FakeChild] = []

    def spawn(deadline):
        child = _FakeChild(**kw)
        spawned.append(child)
        return child

    monkeypatch.setattr(qd, "_inventory_spawn", spawn)
    return spawned


def _rows_json(rows=None, synced=1_790_000_000.0) -> bytes:
    return json.dumps(
        {"rows": [{"provider": "p"}] if rows is None else rows, "synced_at": synced}
    ).encode()


def _fast_deadlines(qd, monkeypatch, request_s=0.8, read_s=0.6):
    monkeypatch.setattr(qd, "INVENTORY_REQUEST_S", request_s)
    monkeypatch.setattr(qd, "INVENTORY_READ_S", read_s)


def _call_in_thread(qd, results: list, *, start_gap: float = 0.0):
    import threading

    def run():
        t0 = time.monotonic()
        out = _inv_data(qd)
        results.append((out, time.monotonic() - t0))

    th = threading.Thread(target=run, daemon=True)
    th.start()
    if start_gap:
        time.sleep(start_gap)
    return th


def test_a_board_test_never_reaches_the_registry(tmp_path, monkeypatch):
    """Isolation (spec § Validation): the spawn is the stub, the DSN names a socket directory that
    does not exist, the 60 s slot is empty, and a Services render reads the census fixture through
    the stub — one spawn, no process."""
    qd = _load(tmp_path, monkeypatch)
    stub = qd.INVENTORY_STUB
    assert qd._inv_good is None and qd._inv_flight is None
    assert qd._inventory_spawn == stub.spawn
    dsn = os.environ["SERVICES_REGISTRY_DSN"]
    assert "host=" in dsn and not Path(dsn.split("host=", 1)[1]).exists()
    text = _text(_view(qd, "services"))
    assert "466 providers" in text and len(stub.spawns) == 1


def test_the_board_process_imports_neither_registry_db_nor_psycopg2(tmp_path):
    """D9: psycopg2 lives in the child only. A fresh interpreter loads the board, renders the Services
    view through a stubbed spawn, and reports whether either module was ever imported."""
    script = tmp_path / "probe.py"
    script.write_text(
        "import importlib.util, json, sys\n"
        f"spec = importlib.util.spec_from_file_location('qd_probe', {str(_SRC)!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "class C:\n"
        "    returncode = 0\n"
        "    def communicate(self, timeout=None):\n"
        "        return json.dumps({'rows': [], 'synced_at': None}).encode(), b''\n"
        "m._inventory_spawn = lambda deadline: C()\n"
        "html = m._render_view('services')\n"
        "print(json.dumps({'psycopg2': 'psycopg2' in sys.modules,\n"
        "                  'registry_db': 'registry_db' in sys.modules,\n"
        "                  'rendered': 'data-view-root=\"services\"' in html}))\n",
        encoding="utf-8",
    )
    env = {**os.environ, "HOME": str(tmp_path), "QUOTA_DASH_BUDGET": "0", "NO_PROXY": "*"}
    for var in ("PYTHONPATH", "SERVICES_REGISTRY_DSN"):
        env.pop(var, None)
    out = subprocess.run(
        [sys.executable, "-I", str(script)], capture_output=True, text=True, timeout=60, env=env
    )
    assert out.returncode == 0, out.stderr[-500:]
    assert json.loads(out.stdout.splitlines()[-1]) == {
        "psycopg2": False,
        "registry_db": False,
        "rendered": True,
    }


def test_a_registry_that_accepts_and_never_answers_is_the_error_state_within_five_seconds(
    tmp_path, monkeypatch
):
    """The REAL child against a loopback server that accepts and never answers: libpq's own
    ``connect_timeout=2`` ends the child (~2 s, well before the board's 4.5 s kill), and the section shows
    that failure's class and first line; the child is gone; the pool and API cards render beside it. The
    kill path is proven by the sleeper test below."""
    import socket

    qd = _load(tmp_path, monkeypatch)
    qd.INVENTORY_STUB.use_real(monkeypatch)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    held: list = []
    stop = False

    def accept_and_hold():
        srv.settimeout(0.2)
        while not stop:
            try:
                held.append(srv.accept()[0])
            except OSError:
                continue

    import threading

    threading.Thread(target=accept_and_hold, daemon=True).start()
    monkeypatch.setenv(
        "SERVICES_REGISTRY_DSN", f"postgresql://u@127.0.0.1:{srv.getsockname()[1]}/none"
    )
    procs: list = []
    real_spawn = qd._inventory_spawn

    def recording_spawn(deadline):
        procs.append(real_spawn(deadline))
        return procs[-1]

    monkeypatch.setattr(qd, "_inventory_spawn", recording_spawn)
    monkeypatch.setattr(
        qd,
        "_pool_credits",
        lambda *_a, **_k: {
            "granted": 245.0,
            "used": 225.0,
            "remaining": 20.0,
            "age_s": 0.0,
            "stale": False,
        },
    )
    t0 = time.monotonic()
    try:
        html_ = _view(qd, "services")
    finally:
        stop = True
        for c in held:
            c.close()
        srv.close()
    took = time.monotonic() - t0
    text = _text(html_)
    assert took < 4.0, (
        took
    )  # the child ended by libpq's connect_timeout, not by the board's 4.5 s kill
    assert "The external-services inventory could not be read: " in text
    assert re.search(r"could not be read: OperationalError: .*timeout expired", text), text[-400:]
    assert "OpenRouter pool" in text and "Search-API quota" in text
    assert procs and procs[0].poll() is not None  # the child is gone
    assert "\n" not in re.search(r"could not be read: ([^<]*)", html_).group(1)


def test_a_child_that_never_ends_is_killed_at_the_read_deadline_and_reaped(tmp_path, monkeypatch):
    """A script that sleeps for a minute stands for a read a server stalls: the request ends inside
    its 5 s with the timeout's one line, the child is dead, and both its pipes are closed."""
    qd = _load(tmp_path, monkeypatch)
    qd.INVENTORY_STUB.use_real(monkeypatch)
    sleeper = tmp_path / "sleeper.py"
    sleeper.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(qd, "_INVENTORY_READ", sleeper)
    procs: list = []
    real_spawn = qd._inventory_spawn

    def recording_spawn(deadline):
        procs.append(real_spawn(deadline))
        return procs[-1]

    monkeypatch.setattr(qd, "_inventory_spawn", recording_spawn)
    t0 = time.monotonic()
    out = _inv_data(qd)
    took = time.monotonic() - t0
    assert out == {"error": "ReadTimeout: registry read killed at its deadline"}
    assert 4.0 < took < 5.0, took
    assert len(procs) == 1 and procs[0].poll() is not None
    assert procs[0].stdout.closed and procs[0].stderr.closed
    assert qd._inv_flight is None


def test_the_read_deadline_leaves_the_request_room_to_kill_clean_up_and_render(
    tmp_path, monkeypatch
):
    """The arithmetic the whole bound rests on: a read's deadline is 4.5 s after its spawning request's
    arrival, inside that request's 5 s, with half a second for the kill, the reap and the render."""
    mod = _load(tmp_path, monkeypatch)
    assert (mod.INVENTORY_REQUEST_S, mod.INVENTORY_READ_S, mod.INVENTORY_FRESH_S) == (
        5.0,
        4.5,
        60.0,
    )
    assert mod.INVENTORY_REQUEST_S - mod.INVENTORY_READ_S >= 0.5


def test_a_read_that_faults_before_the_deadline_still_kills_and_reaps_its_child(
    tmp_path, monkeypatch
):
    """At most one child is ever alive: whatever ends the first read of a running child (here an OSError),
    the waiter kills it and reaps it, and the field is clear for the next request."""
    qd = _load(tmp_path, monkeypatch)
    calls: list[str] = []

    class _Faulting:
        returncode = None

        def communicate(self, timeout=None):
            calls.append("communicate")
            if len(calls) == 1:
                raise OSError("pipe broke")
            self.returncode = -9
            return b"", b""

        def poll(self):
            return self.returncode

        def kill(self):
            calls.append("kill")

    monkeypatch.setattr(qd, "_inventory_spawn", lambda deadline: _Faulting())
    out = _inv_data(qd)
    assert out == {"error": "OSError: pipe broke"}
    assert calls == ["communicate", "kill", "communicate"]  # killed, then reaped
    assert qd._inv_flight is None


def test_the_real_child_bounds_itself_when_the_board_that_would_kill_it_is_gone(tmp_path):
    """A server that completes the handshake and stalls, and no board to kill the child: the child
    ends by its own alarm a moment past the deadline it was given."""
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "psycopg2.py").write_text(
        "import time\n\n\ndef connect(*a, **k):\n    time.sleep(60)\n", encoding="utf-8"
    )
    env = {**os.environ, "PYTHONPATH": str(stub), "SERVICES_REGISTRY_DSN": "postgresql://u@h/d"}
    t0 = time.monotonic()
    proc = subprocess.Popen(
        [sys.executable, str(_CHILD), "--deadline", repr(time.time() + 1.0)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        proc.wait(timeout=6.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("the child outlived its own bound") from None
    head = proc.stdout.read()[:200]
    proc.stdout.close()
    proc.stderr.close()
    assert proc.returncode == -signal.SIGALRM, (
        proc.returncode,
        head,
    )  # the alarm, not any fast failure
    assert head == b"", head  # an alarm-killed child writes nothing
    assert time.monotonic() - t0 < 6.0


def test_concurrent_requests_share_one_child_and_each_gets_the_result(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    spawned = _fake_children(qd, monkeypatch, stdout=_rows_json(), answers=True)
    _fast_deadlines(qd, monkeypatch, request_s=3.0, read_s=2.5)
    results: list = []
    first = _call_in_thread(qd, results, start_gap=0.2)
    second = _call_in_thread(qd, results, start_gap=0.2)
    assert len(spawned) == 1 and qd._inv_flight is not None  # one child in flight, two waiting
    spawned[0].release()
    first.join(5)
    second.join(5)
    assert len(spawned) == 1 and len(results) == 2
    assert all(r[0]["rows"] == [{"provider": "p"}] for r in results), results
    assert qd._inv_flight is None  # cleared on exit


def test_every_request_without_a_fresh_result_is_the_error_state_within_its_own_deadline(
    tmp_path, monkeypatch
):
    """A child that never answers, a joiner arriving later: both answer the error state, each inside
    5 s (here the scaled 0.8 s) of its OWN arrival, the child is killed, and the field is clear."""
    qd = _load(tmp_path, monkeypatch)
    spawned = _fake_children(qd, monkeypatch, answers=False)
    _fast_deadlines(qd, monkeypatch, request_s=0.8, read_s=0.6)
    results: list = []
    a = _call_in_thread(qd, results, start_gap=0.3)
    b = _call_in_thread(qd, results)
    a.join(5)
    b.join(5)
    assert len(spawned) == 1 and spawned[0].killed.is_set()
    assert [r[0] for r in results] == [{"error": qd._INV_TIMEOUT}] * 2
    assert all(r[1] < 0.8 + 0.25 for r in results), [r[1] for r in results]  # its own 5 s, scaled
    assert qd._inv_flight is None
    # the next request starts afresh: a new child, not a join of the dead one
    _inv_data(qd)
    assert len(spawned) == 2


def test_a_failed_child_is_the_error_state_and_leaves_the_last_good_read(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    good = ([{"provider": "kept"}], 1.0, time.monotonic() - 61)  # past its 60 s, still held
    monkeypatch.setattr(qd, "_inv_good", good)
    _fake_children(
        qd,
        monkeypatch,
        stdout=json.dumps({"error": "OperationalError: no route"}).encode(),
        code=1,
        at_once=True,
    )
    for _ in range(2):  # a failure is not cached: both requests read, both fail
        out = _inv_data(qd)
        assert out == {"error": "OperationalError: no route"}
        assert qd._inv_good is good  # the failed read never replaced it
        assert qd._inv_flight is None  # and the field cleared, so the next request starts afresh


def test_the_last_good_read_is_served_inside_its_60_seconds_and_a_new_child_starts_past_them(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)
    fresh = _rows_json([{"provider": "new"}])
    spawned = _fake_children(qd, monkeypatch, stdout=fresh)
    monkeypatch.setattr(qd, "_inv_good", ([{"provider": "old"}], 5.0, time.monotonic() - 59))
    assert (
        _inv_data(qd)["rows"] == [{"provider": "old"}] and spawned == []
    )  # 59 s: served, no child
    monkeypatch.setattr(qd, "_inv_good", ([{"provider": "old"}], 5.0, time.monotonic() - 61))
    out: list = []
    th = _call_in_thread(qd, out, start_gap=0.2)
    assert len(spawned) == 1  # 61 s: a new child
    spawned[0].release()
    th.join(5)
    assert out[0][0]["rows"] == [{"provider": "new"}]
    assert qd._inv_good[0] == [{"provider": "new"}]


def test_a_request_held_on_the_lock_answers_inside_its_own_deadline(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    spawned = _fake_children(qd, monkeypatch, stdout=_rows_json())
    _fast_deadlines(qd, monkeypatch, request_s=0.4, read_s=0.3)
    # the lock acquire is bounded by the constant the request reads, so the scaled value applies
    qd._inv_lock.acquire()
    try:
        results: list = []
        _call_in_thread(qd, results).join(5)
    finally:
        qd._inv_lock.release()
    assert results[0][0] == {
        "error": "ReadTimeout: registry lock not taken within the request's deadline"
    }
    assert (
        results[0][1] < 0.3 + 0.15
    )  # the wait is bounded by the read's share, leaving room to render
    assert spawned == []


def test_a_spawn_that_raises_is_the_error_state_and_clears_the_field(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)

    def broken(deadline):
        raise OSError("fork failed")

    monkeypatch.setattr(qd, "_inventory_spawn", broken)
    assert _inv_data(qd) == {"error": "OSError: fork failed"}
    assert qd._inv_flight is None and qd._inv_good is None


def test_a_thread_that_cannot_start_clears_the_field_so_the_next_request_starts_afresh(
    tmp_path, monkeypatch
):
    import threading

    qd = _load(tmp_path, monkeypatch)
    real_start = threading.Thread.start

    def refuse(self):
        if self.name == "inventory-read":
            raise RuntimeError("can't start new thread")
        return real_start(self)

    monkeypatch.setattr(threading.Thread, "start", refuse)
    assert _inv_data(qd) == {"error": "RuntimeError: can't start new thread"}
    assert qd._inv_flight is None
    monkeypatch.setattr(threading.Thread, "start", real_start)
    assert "rows" in _inv_data(qd)  # the stub answers: nothing stayed stuck in flight


def test_no_connection_is_ever_cancelled_and_the_board_never_imports_a_driver():
    """psycopg2's cancel() against a server that accepts and never answers froze every thread of the
    process (the plan review's pass-3 probe): the child's kill is the only way a read ends."""
    child = (_SRC.parent / "inventory_read.py").read_text(encoding="utf-8")
    board = _SRC.read_text(encoding="utf-8")
    assert not re.search(r"\.cancel\s*\(|\bcancel\s*\(", child)
    assert not re.search(
        r"\.cancel\s*\(",
        board[board.index("def _inventory_spawn") : board.index("def _pointer_slug")],
    )
    code = "\n".join(line for line in board.splitlines() if not line.lstrip().startswith("#"))
    assert not re.search(r"^\s*(import|from)\s+(psycopg2|registry_db)\b", code, re.M)


@pytest.mark.parametrize(
    "stdout,code,want",
    [
        (b'{"rows": [{"a": 1}], "synced_at": 5.5}', 0, ("ok", [{"a": 1}], 5.5)),
        (b'{"rows": [], "synced_at": null}', 0, ("ok", [], None)),
        (b'{"error": "ValueError: bad\\nsecond line"}', 1, ("err", "ValueError: bad")),
        (
            b'{"error": "X: y"}',
            0,
            ("err", "ReadFailed: exit status 0"),
        ),  # shape against exit status
        (b'{"rows": [], "synced_at": null}', 1, ("err", "ReadFailed: exit status 1")),
        (
            b'{"rows": [], "synced_at": null, "error": "X: y"}',
            0,
            ("err", "ReadFailed: exit status 0"),
        ),
        (b'{"rows": {}, "synced_at": null}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [1], "synced_at": null}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [], "synced_at": "yesterday"}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [], "synced_at": true}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [], "synced_at": NaN}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [], "synced_at": Infinity}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [], "synced_at": -Infinity}', 0, ("err", "ReadFailed: exit status 0")),
        (b'{"rows": [], "synced_at": -1}', 0, ("err", "ReadFailed: exit status 0")),
        (
            b'{"rows": [], "synced_at": ' + b"9" * 400 + b"}",
            0,
            ("err", "ReadFailed: exit status 0"),
        ),
        (
            b'{"rows": [], "synced_at": -' + b"9" * 400 + b"}",
            0,
            ("err", "ReadFailed: exit status 0"),
        ),
        (b'{"error": 5}', 1, ("err", "ReadFailed: exit status 1")),
        (b"[]", 0, ("err", "ReadFailed: exit status 0")),
        (b"not json", 0, ("err", "ReadFailed: exit status 0")),
        (b"", -9, ("err", "ReadFailed: exit status -9")),
        (b"\xff\xfe", 1, ("err", "ReadFailed: exit status 1")),
    ],
)
def test_the_childs_stdout_and_exit_status_are_one_outcome(
    tmp_path, monkeypatch, stdout, code, want
):
    qd = _load(tmp_path, monkeypatch)
    assert qd._inventory_outcome(stdout, code) == want


def test_the_board_reads_synced_at_by_the_pages_rule(tmp_path, monkeypatch):
    """W-a4bc74a6 (R27): the board had its own `_epoch`, which admitted a `synced_at` the page's
    refuses (no calendar holds it), so a payload the page renders as no time was a FRESH read here.
    One rule now: the page's. A real child already applies it, so only a foreign payload meets this."""
    qd = _load(tmp_path, monkeypatch)
    from dashboard_ui import inventory

    assert qd._epoch is inventory._epoch
    for synced in (b"1e308", b"253402300799"):
        payload = b'{"rows": [], "synced_at": ' + synced + b"}"
        assert qd._inventory_outcome(payload, 0) == ("err", "ReadFailed: exit status 0"), synced
    outcome = qd._inventory_outcome(b'{"rows": [], "synced_at": -0.0}', 0)
    assert outcome == ("ok", [], 0.0)
    assert math.copysign(1.0, outcome[2]) == 1.0  # `==` above ignores the sign of zero


def test_a_child_that_cannot_import_psycopg2_is_only_the_inventory_sections_error_state(
    tmp_path, monkeypatch
):
    """D9: a missing driver fails the CHILD. The error object names the import's exception class
    whatever the child's stderr holds (here it prints a decoy `{"error": …}` line), every other view
    serves, and the board process never imported psycopg2."""
    qd = _load(tmp_path, monkeypatch)
    qd.INVENTORY_STUB.use_real(monkeypatch)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "psycopg2.py").write_text(
        "import sys\n"
        'sys.stderr.write(\'{"error": "Decoy: stderr is never read"}\\n\')\n'
        "raise ModuleNotFoundError(\"No module named 'psycopg2'\", name='psycopg2')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(blocked))
    out = _inv_data(qd)
    assert out == {"error": "ModuleNotFoundError: No module named 'psycopg2'"}
    html_ = _view(qd, "services")
    assert "could not be read: ModuleNotFoundError: No module named" in _text(html_)
    assert "Decoy" not in html_
    for name in qd._views.VIEWS:
        if name != "services":
            assert 'data-state="error"' not in _view(qd, name).split(">", 1)[0], name
    assert "psycopg2" not in sys.modules or sys.modules["psycopg2"].__file__ != str(
        blocked / "psycopg2.py"
    )


def test_external_services_html_is_a_303_to_the_inventory_section_with_no_body(
    tmp_path, monkeypatch
):
    from datetime import date

    qd = _load(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        for path in ("/external-services.html", "/external-services.html?x=1"):
            status, hdrs, body = _get(base, path)
            assert status == 303 and hdrs["Location"] == "/#services" and body == b"", (
                path,
                status,
            )
            assert hdrs["Content-Length"] == "0" and hdrs["Cache-Control"] == "no-store"
        assert (
            qd._LEGACY_TOKEN_UNTIL is not None
        )  # the redirect is not tied to the work-verdict window
        monkeypatch.setattr(
            qd, "_LEGACY_TOKEN_UNTIL", date(2000, 1, 1)
        )  # that window closed long ago
        assert _get(base, "/external-services.html")[0] == 303
    finally:
        httpd.shutdown()


def test_no_link_card_ext_page_key_or_services_ext_string_remains(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    data = qd._view_data("services", type("C", (), {"now": time.time()})())
    assert "ext_page" not in data and "inventory" in data
    assert not [k for k in qd._strings.CATALOGUE if k.startswith("services.ext.")]
    assert not hasattr(qd, "EXT_SERVICES_HTML")
    source = _SRC.read_text(encoding="utf-8")
    assert "QUOTA_DASH_EXT_SERVICES" not in source
    html_ = _view(qd, "services")
    assert (
        'href="/external-services.html"' not in html_ and "external-services-dashboard" not in html_
    )


def test_the_inventory_carries_no_classifier_time(tmp_path, monkeypatch):
    """D-1046 retired the classifier's source rule: the board no longer stats classify_last.json
    and its inventory payload carries no `classified_at`."""
    qd = _load(tmp_path, monkeypatch)
    data = _inv_data(qd)
    assert "rows" in data and "synced_at" in data, (
        data
    )  # the read succeeded: the negative is not vacuous
    assert "classified_at" not in data
    assert not hasattr(qd, "_CLASSIFY_STAMP") and not hasattr(qd, "_inventory_classified_at")


def test_two_renders_of_the_services_view_a_minute_apart_carry_the_same_data_stamp(
    tmp_path, monkeypatch
):
    """Spec § Data flow: the stamp hashes the markup, so a render must not carry the clock — the
    summary, the attention list and the rows are the registry's, the same registry gives the same stamp."""
    qd = _load(tmp_path, monkeypatch)
    real_time = time.time

    def stamp_of(html_: str) -> str:
        root = re.match(r"<section[^>]*>", html_.strip()).group(0)
        assert 'data-view-root="services"' in root
        return re.search(r'data-stamp="([0-9a-f]{16})"', root).group(1)

    first = stamp_of(_view(qd, "services"))
    monkeypatch.setattr(qd.time, "time", lambda: real_time() + 60)
    monkeypatch.setattr(qd, "_inv_good", None)  # a read, not the cache
    second = stamp_of(_view(qd, "services"))
    assert len(qd.INVENTORY_STUB.spawns) == 2 and first == second


# ── the child process itself (scripts/sysadmin/inventory_read.py) ────────────────────────────

_CHILD = _SRC.parent / "inventory_read.py"


def _child_module(monkeypatch):
    """The child's module, loaded by path, with the registry's driver module and the reader faked:
    nothing here connects to anything."""
    monkeypatch.syspath_prepend(str(_SRC.parents[1]))
    monkeypatch.syspath_prepend(str(_SRC.parent))
    spec = importlib.util.spec_from_file_location("inventory_read_under_test", _CHILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _OneWrite:
    def __init__(self):
        self.writes: list[str] = []

    def write(self, text):
        self.writes.append(text)

    def flush(self):
        pass


def test_the_child_reports_a_read_as_one_json_object_with_floats_for_decimals(monkeypatch):
    from decimal import Decimal

    child = _child_module(monkeypatch)
    import registry_db
    from dashboard_ui import inventory

    seen: dict = {}

    class Conn:
        closed = False

        def set_session(self, **kw):
            pass

        def close(self):
            self.closed = True

    conn = Conn()

    def connect(**kw):
        seen["kw"] = kw
        return conn

    def load(c, *, before_query=None):
        assert c is conn and before_query is not None
        return [
            {
                "provider": "p",
                "balance": Decimal("12.50"),
                "projects": {"b", "a"},
                "keys": 2,
                "x": None,
            },
        ], Decimal("1790000000.5")

    monkeypatch.setattr(registry_db, "connect", connect)
    monkeypatch.setattr(inventory, "load", load)
    out = _OneWrite()
    monkeypatch.setattr(sys, "stdout", out)
    code = child.main(["inventory_read.py", "--deadline", str(time.time() + 4)])
    assert code == 0 and len(out.writes) == 1  # ONE write, the whole object
    obj = json.loads(out.writes[0])
    assert obj == {
        "rows": [{"provider": "p", "balance": 12.5, "projects": ["a", "b"], "keys": 2, "x": None}],
        "synced_at": 1790000000.5,
    }
    assert isinstance(obj["rows"][0]["balance"], float)
    assert seen["kw"] == {"connect_timeout": 2, "options": "-c statement_timeout=2000"}
    assert conn.closed  # closed on success


def test_the_child_re_arms_the_statement_timeout_to_the_deadline_left_never_below_one_ms(
    monkeypatch,
):
    child = _child_module(monkeypatch)
    import registry_db
    from dashboard_ui import inventory

    class Cur:
        def __init__(self):
            self.sql: list[str] = []

        def execute(self, sql):
            self.sql.append(sql)

    cur = Cur()
    conn = type("Conn", (), {"close": lambda self: None, "set_session": lambda self, **kw: None})()
    monkeypatch.setattr(registry_db, "connect", lambda **kw: conn)

    def load(c, *, before_query=None):
        before_query(cur)
        return [], None

    monkeypatch.setattr(inventory, "load", load)
    for deadline_in, low, high in ((3.0, 2500, 3000), (0.0004, 1, 1), (-5.0, 1, 1)):
        cur.sql.clear()
        monkeypatch.setattr(sys, "stdout", _OneWrite())
        assert child.main(["x", "--deadline", repr(time.time() + deadline_in)]) == 0
        (stmt,) = cur.sql
        ms = int(re.fullmatch(r"SET LOCAL statement_timeout = (\d+)", stmt).group(1))
        assert low <= ms <= high, (deadline_in, ms)  # 0 would DISABLE the bound in Postgres


def test_the_child_reads_the_registry_in_one_read_only_snapshot(monkeypatch):
    """W-a4bc74a6 (R15): under READ COMMITTED each of `load()`'s six statements took its own
    snapshot, so a read straddling `registry_sync`'s one-transaction commit showed pre-sync rows
    stamped with the post-sync `synced_at` (read last) — and the board keeps a read 60 s. The child
    asks for REPEATABLE READ, read-only, BEFORE the first statement: one snapshot for the six."""
    child = _child_module(monkeypatch)
    import registry_db
    from dashboard_ui import inventory

    events: list = []

    class Conn:
        def set_session(self, **kw):
            events.append(("set_session", kw))

        def close(self):
            events.append(("close", None))

    monkeypatch.setattr(registry_db, "connect", lambda **kw: Conn())

    def load(c, *, before_query=None):
        events.append(("load", None))
        return [], None

    monkeypatch.setattr(inventory, "load", load)
    monkeypatch.setattr(sys, "stdout", _OneWrite())
    assert child.main(["x", "--deadline", repr(time.time() + 4)]) == 0
    assert events == [
        ("set_session", {"isolation_level": "REPEATABLE READ", "readonly": True}),
        ("load", None),
        ("close", None),
    ]
    # a session the driver refuses is an error object AND a closed connection, never a leaked one
    events.clear()

    def refuse(self, **kw):
        events.append(("set_session", kw))
        raise RuntimeError("set_session cannot be used inside a transaction")

    monkeypatch.setattr(Conn, "set_session", refuse)
    out = _OneWrite()
    monkeypatch.setattr(sys, "stdout", out)
    assert child.main(["x", "--deadline", repr(time.time() + 4)]) == 1
    assert json.loads(out.writes[0]) == {
        "error": "RuntimeError: set_session cannot be used inside a transaction"
    }
    assert [e for e, _ in events] == ["set_session", "close"]  # load never ran; close did


@pytest.mark.parametrize(
    "argv,starts",
    [
        (["x"], "ValueError: usage"),
        (["x", "--deadline"], "ValueError: usage"),
        (["x", "--deadline", "soon"], "ValueError: could not convert string to float"),
        (["x", "--bogus", "1"], "ValueError: usage"),
        (["x", "--deadline", "1", "extra"], "ValueError: usage"),
    ],
)
def test_the_child_reports_a_bad_argv_the_same_way_as_any_failure(monkeypatch, argv, starts):
    child = _child_module(monkeypatch)
    out = _OneWrite()
    monkeypatch.setattr(sys, "stdout", out)
    assert child.main(argv) == 1 and len(out.writes) == 1
    err = json.loads(out.writes[0])["error"]
    assert err.startswith(starts) and "\n" not in err


def test_the_child_closes_the_connection_and_reports_the_first_line_when_the_read_fails(
    monkeypatch,
):
    child = _child_module(monkeypatch)
    import registry_db
    from dashboard_ui import inventory

    conn = type(
        "Conn",
        (),
        {
            "closed": False,
            "close": lambda self: setattr(self, "closed", True),
            "set_session": lambda self, **kw: None,
        },
    )()
    monkeypatch.setattr(registry_db, "connect", lambda **kw: conn)

    def load(c, *, before_query=None):
        raise RuntimeError("canceling statement due to statement timeout\nCONTEXT: second line")

    monkeypatch.setattr(inventory, "load", load)
    out = _OneWrite()
    monkeypatch.setattr(sys, "stdout", out)
    assert child.main(["x", "--deadline", "1"]) == 1
    assert json.loads(out.writes[0]) == {
        "error": "RuntimeError: canceling statement due to statement timeout"
    }
    assert conn.closed


def test_the_child_reports_an_interrupt_and_a_missing_connection_the_same_way(monkeypatch):
    child = _child_module(monkeypatch)
    import registry_db

    for exc, want in (
        (KeyboardInterrupt(), "KeyboardInterrupt"),
        (OSError("connection refused"), "OSError: connection refused"),
    ):

        def connect(_exc=exc, **kw):
            raise _exc

        monkeypatch.setattr(registry_db, "connect", connect)
        out = _OneWrite()
        monkeypatch.setattr(sys, "stdout", out)
        assert child.main(["x", "--deadline", "1"]) == 1
        assert json.loads(out.writes[0]) == {"error": want}


def test_the_real_child_process_with_no_argument_prints_one_error_object_and_exits_one():
    out = subprocess.run([sys.executable, str(_CHILD)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 1 and out.stderr == ""
    assert json.loads(out.stdout)["error"].startswith("ValueError: usage")


# ── 2026-09-03 20:10: the probe timed out 7× in a row (60 s each) while ob@ burned 96 → 100 ──


def test_a_blind_probe_triggers_the_tick_from_the_last_good_reading_at_the_drain_line(
    tmp_path, monkeypatch
):
    """The fast path was blind for the whole crossing: `--status --json` timed out seven times in a
    row and the last GOOD reading (96 < 98) never re-armed the trigger, so the wall came before any
    probe succeeded. When the probe is failing, the last good reading is minutes old — the bar drops
    to the drain line (85) and the TICK reads live; the cooldown still bounds it."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=86.0, QUOTA_DASH_TRIGGER_COOLDOWN_S="60")
    qd.generate()
    assert (
        qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text())) is None
    )  # 86: below the flip line (95) AND the drain tier (90), sighted

    def dead(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="rotate", timeout=60)

    monkeypatch.setattr(qd, "_probe", dead)
    qd.generate()
    payload = json.loads(qd._JSON.read_text())
    assert payload.get("probe_failed"), "a fallback payload must say the probe is blind"
    t = qd._maybe_trigger_rotation(payload)
    assert t is not None, "blind probe + last good 86 ≥ blind bar 85 → the tick reads live"
    t.join(10)
    assert [c for c in _calls(stub) if c[:1] == ["--tick"]] == [["--tick"]]
    assert qd._maybe_trigger_rotation(payload) is None  # cooldown still bounds the blind path


def test_a_blind_probe_below_the_drain_line_stays_quiet(tmp_path, monkeypatch):
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=40.0)
    qd.generate()

    def dead(*a, **kw):
        raise OSError("no rotate cli")

    monkeypatch.setattr(qd, "_probe", dead)
    qd.generate()
    assert qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text())) is None
    assert not [c for c in _calls(stub) if c[:1] == ["--tick"]]


def test_a_sighted_probe_clears_the_blind_flag(tmp_path, monkeypatch):
    qd, stub = _tick_env(tmp_path, monkeypatch, session=40.0)
    real = qd._probe

    def dead(*a, **kw):
        raise OSError("down")

    monkeypatch.setattr(qd, "_probe", dead)
    qd.generate()
    assert json.loads(qd._JSON.read_text()).get("probe_failed")
    monkeypatch.setattr(qd, "_probe", real)
    qd.generate()
    assert not json.loads(qd._JSON.read_text()).get("probe_failed")


# ── 2026-09-03 operator rule: at/over 90% session the tick must run within one probe interval
# so the URGENT "stop gracefully, hook to the next reset" mail goes out in seconds when no
# successor exists — on a cooldown of its OWN, so it can never delay the flip tier at 95 ──────


def test_ninety_percent_session_invokes_the_tick_on_the_drain_tier(tmp_path, monkeypatch):
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    monkeypatch.delenv("ROTATE_URGENT_DRAIN_PCT", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=91.0)
    qd.generate()
    t = qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text()))
    assert t is not None, "91% is on the drain tier — the tick must run"
    t.join(10)
    assert [c for c in _calls(stub) if c[:1] == ["--tick"]] == [["--tick"]]


def test_the_drain_tier_cooldown_never_delays_the_flip_tier(tmp_path, monkeypatch):
    """A drain-tier tick followed 30 s later by a flip-tier one must fire AGAIN — a shared
    cooldown would hold the flip for up to two minutes, which a measured burst covers easily
    (p99 rise 35 points per 5-min gap).

    Both readings are derived from the live constants, not typed: this test was written with a
    literal 96, which was a flip-tier reading at the old threshold of 95 and became a drain-tier
    reading the moment it went to 98 — so it failed for a stale fixture, not a real defect.
    """
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=91.0, QUOTA_DASH_TRIGGER_COOLDOWN_S="600")
    drain_tier = qd.DRAIN_TRIGGER_THRESHOLD + 1.0
    flip_tier = qd.TRIGGER_THRESHOLD + 1.0
    assert drain_tier < qd.TRIGGER_THRESHOLD, "the first reading must be BELOW the flip line"
    qd.generate()
    t = qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text()))
    assert t is not None
    t.join(10)
    (tmp_path / "stub_rotate.py.payload").write_text(json.dumps(_payload(session=flip_tier)))
    qd.generate()
    t2 = qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text()))
    assert t2 is not None, "the flip tier has its own cooldown"
    t2.join(10)
    assert len([c for c in _calls(stub) if c[:1] == ["--tick"]]) == 2


def test_below_ninety_the_board_stays_quiet(tmp_path, monkeypatch):
    monkeypatch.delenv("ROTATE_URGENT_DRAIN_PCT", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=89.0)
    qd.generate()
    assert qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text())) is None
    assert not [c for c in _calls(stub) if c[:1] == ["--tick"]]


# ── The OpenRouter pool balance — the fleet's OTHER quota, previously unwatched ───────────────
#
# 2026-09-04: the pool ran to -$0.0015 of $225 and NOTHING on the box knew. Three repos found out
# by hitting HTTP 402 mid-run; one lost 24 grounder units, another's closing review sweep silently
# fell back to a lane that records nothing to the flywheel. This board already polls every 20s and
# already holds the key — the balance is one GET away, and a level is worth watching because 402
# is issued on BALANCE, so a positive number is the direct signal, not a proxy for one.


def _key_file(tmp_path: Path, value: str = "sk-or-v1-TESTKEY") -> Path:
    cfg = tmp_path / "cfg"
    cfg.mkdir(exist_ok=True)
    f = cfg / "subagents.env"
    f.write_text(f'# comment\nOPENROUTER_API_KEY="{value}"\nOTHER=1\n')
    return f


def _credits_env(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("QUOTA_DASH_CREDITS_KEY_FILE", str(_key_file(tmp_path)))
    return _load(tmp_path, monkeypatch, **env)


def test_the_balance_is_read_and_inverted_into_remaining(tmp_path, monkeypatch):
    """The API reports granted and used. The board must show what is LEFT — the same inversion
    the account table does, and the same bug class if it is got wrong."""
    qd = _credits_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        qd, "_credits_get", lambda key: {"data": {"total_credits": 245.0, "total_usage": 225.0015}}
    )

    c = qd._pool_credits(now=1000.0)

    assert c is not None
    assert c["granted"] == 245.0
    assert round(c["remaining"], 4) == 19.9985, "granted MINUS used, never the raw usage"


def test_the_balance_is_cached_so_a_20s_refresh_is_not_a_20s_api_call(tmp_path, monkeypatch):
    """The page refreshes every 20s. Credits move only when something spends, so re-reading them
    per view would be 4,320 calls a day to learn a number that changes a few times an hour."""
    qd = _credits_env(tmp_path, monkeypatch)
    calls = []

    def fake(key):
        calls.append(key)
        return {"data": {"total_credits": 100.0, "total_usage": 40.0}}

    monkeypatch.setattr(qd, "_credits_get", fake)

    first = qd._pool_credits(now=1000.0)
    for t in (1005.0, 1100.0, 1000.0 + qd.CREDITS_TTL_S - 1):
        again = qd._pool_credits(now=t)
        assert again is not None and again["remaining"] == first["remaining"]
    assert len(calls) == 1, f"one call inside the TTL, got {len(calls)}"

    qd._pool_credits(now=1000.0 + qd.CREDITS_TTL_S + 1)
    assert len(calls) == 2, "and exactly one more once the TTL has passed"


def test_a_dead_endpoint_serves_the_last_known_balance_with_its_age(tmp_path, monkeypatch):
    """Same rule as the account table: a stale number with a date on it beats a blank."""
    qd = _credits_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        qd, "_credits_get", lambda key: {"data": {"total_credits": 100.0, "total_usage": 40.0}}
    )
    qd._pool_credits(now=1000.0)

    def boom(key):
        raise OSError("network down")

    monkeypatch.setattr(qd, "_credits_get", boom)
    c = qd._pool_credits(now=1000.0 + qd.CREDITS_TTL_S + 1)

    assert c is not None and c["remaining"] == 60.0
    assert c["stale"] is True and c["age_s"] >= qd.CREDITS_TTL_S


def test_no_key_is_not_an_error_and_never_blanks_the_board(tmp_path, monkeypatch):
    """A box without the pool configured must render exactly as before."""
    monkeypatch.setenv("QUOTA_DASH_CREDITS_KEY_FILE", str(tmp_path / "nope.env"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    qd = _load(tmp_path, monkeypatch)

    assert qd._pool_credits(now=1000.0) is None
    services = _view(qd, "services")
    assert "not configured on this box" in _text(services)
    assert 'data-state="error"' not in services, "an absent pool is not an error"
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    assert _find(_dom(_accounts(qd)), "table"), "the board still renders"


def test_the_key_never_reaches_the_page_or_the_cache(tmp_path, monkeypatch):
    """The one thing that must never leak. The panel and the on-disk cache are both readable by
    anything that can read the board."""
    qd = _credits_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        qd, "_credits_get", lambda key: {"data": {"total_credits": 100.0, "total_usage": 40.0}}
    )
    qd._pool_credits(now=time.time())
    assert "TESTKEY" not in qd.CREDITS_CACHE.read_text()
    services = _view(qd, "services")
    assert "$60.00 remaining of $100.00" in _text(services)  # the cached balance IS on the page
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    for name in qd._views.VIEWS:
        assert "TESTKEY" not in _view(qd, name), name
    assert "TESTKEY" not in qd._shell_page()


def test_the_panel_reaches_the_page_and_goes_critical_when_the_pool_is_dry(tmp_path, monkeypatch):
    qd = _credits_env(tmp_path, monkeypatch)
    healthy = _badges(_pool_view(qd, monkeypatch, {"granted": 245.0, "used": 25.0, "remaining": 220.0,
                                                   "age_s": 0.0, "stale": False}))  # fmt: skip
    assert ("ok", "$220.00 remaining of $245.00") in healthy

    dry = [b for b in _badges(_pool_view(qd, monkeypatch, {"granted": 245.0, "used": 245.01,
           "remaining": -0.01, "age_s": 0.0, "stale": False})) if "remaining of" in b[1]]  # fmt: skip
    assert dry and dry[0][0] == "critical"
    assert "402" in dry[0][1], "say WHAT the operator will see, not just that a number is low"
    view = _pool_view(
        qd,
        monkeypatch,
        {"granted": 1.0, "used": 0.0, "remaining": 1.0, "age_s": 0.0, "stale": False},
    )
    assert "OpenRouter pool" in _text(view), "the panel must actually be placed in the page"


def test_the_drain_advisory_fires_once_per_episode_and_re_arms_on_a_top_up(tmp_path, monkeypatch):
    """The latch the wall advisory taught us: one message per episode, re-armed the moment relief
    arrives — an alert that repeats every 20s is an alert everyone filters."""
    qd = _credits_env(tmp_path, monkeypatch, POOL_CREDITS_WARN_USD="5")
    sent = []
    monkeypatch.setattr(qd, "_notify", lambda msg: sent.append(msg))

    low = {"granted": 245.0, "used": 241.0, "remaining": 4.0, "age_s": 0.0, "stale": False}
    qd._maybe_alert_pool_credits(low)
    qd._maybe_alert_pool_credits(low)
    qd._maybe_alert_pool_credits(low)
    assert len(sent) == 1, f"latched — one message per drain episode, got {len(sent)}"
    assert "4.00" in sent[0] and "openrouter.ai" in sent[0], "name the number and where to fix it"

    qd._maybe_alert_pool_credits({**low, "remaining": 60.0})  # topped up → re-arm
    assert len(sent) == 1, "recovery is not an alarm"
    qd._maybe_alert_pool_credits(low)
    assert len(sent) == 2, "a NEW drain episode speaks again"


def test_a_healthy_balance_and_an_unknown_one_never_alert(tmp_path, monkeypatch):
    qd = _credits_env(tmp_path, monkeypatch, POOL_CREDITS_WARN_USD="5")
    sent = []
    monkeypatch.setattr(qd, "_notify", lambda msg: sent.append(msg))

    qd._maybe_alert_pool_credits(
        {"granted": 245.0, "used": 25.0, "remaining": 220.0, "age_s": 0.0, "stale": False}
    )
    qd._maybe_alert_pool_credits(None)  # no key / unreadable — silence, not a false alarm

    assert sent == []


def test_the_render_path_never_makes_the_network_call(tmp_path, monkeypatch):
    """Found by this file's own cadence tests when the first cut fetched inline: the GET is up to
    CREDITS_TIMEOUT_S and `_generate_locked` holds `_gen_lock`, so an inline fetch puts a
    third-party endpoint on the board's critical path — the shape of the 2026-08-18 hang, where a
    stalled probe made every page load sit for its full timeout. (It also took this suite from
    9.9s to 38.6s, which is what surfaced it.)"""
    qd = _credits_env(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        qd,
        "_credits_get",
        lambda key: calls.append(key) or {"data": {"total_credits": 9.0, "total_usage": 1.0}},
    )

    assert qd._pool_credits(now=1000.0, fetch=False) is None, "no cache yet, and it must NOT fetch"
    assert calls == [], "the render path made a network call"

    qd._pool_credits(now=1000.0)  # the refresher warms the cache
    assert len(calls) == 1
    cached = qd._pool_credits(now=1_000_000.0, fetch=False)
    assert cached is not None and cached["remaining"] == 8.0
    assert cached["stale"] is True, "a cache served past its TTL must SAY it is stale"
    assert len(calls) == 1, "and still no second call from the render path"


def test_the_refresher_runs_off_the_lock_and_drops_an_overlapping_request(tmp_path, monkeypatch):
    qd = _credits_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        qd, "_credits_get", lambda key: {"data": {"total_credits": 9.0, "total_usage": 1.0}}
    )

    th = qd._credits_async()
    assert th is not None
    th.join(timeout=10)
    assert qd.CREDITS_CACHE.exists(), "the refresher warmed the cache"

    qd._credits_lock.acquire()  # simulate one already in flight
    try:
        assert qd._credits_async() is None, "an overlapping refresh is dropped, never queued"
    finally:
        qd._credits_lock.release()


def _sidecar(tmp_path, monkeypatch, unweighted: dict):
    """A minimal but VALID cost sidecar — `_spend_panel` renders nothing at all without tiers,
    spend and base rate, so a rig that omits them would prove the panel silent for the wrong reason."""
    qd = _load(tmp_path, monkeypatch)
    path = tmp_path / "claude_p_cost.json"
    path.write_text(
        json.dumps(
            {
                "built_at": "2026-09-05T00:00:00+03:00",
                "per_model_spend": {
                    "window_start": "2026-08-07",
                    "window_end": "2026-09-05",
                    "spend_usd": 800.0,
                    "base_rate_per_mtok": 0.007,
                    "tiers": {
                        "opus": {
                            "weight": 5.0,
                            "tokens": 1_000_000,
                            "share": 1.0,
                            "rate_per_mtok": 0.035,
                            "cost_usd": 800.0,
                            "models": ["claude-opus-5"],
                        }
                    },
                    "models": {"claude-opus-5": 1_000_000},
                    "daily": [
                        {
                            "date": "2026-09-05",
                            "tokens": 1_000_000,
                            "cost_usd": 800.0,
                            "by_tier": {"opus": 1_000_000},
                        }
                    ],
                    "monthly_spend": {"2026-09": 800.0},
                    "unweighted": unweighted,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(qd, "_COST_SIDECAR", path)
    return qd


def test_tokens_no_tier_claimed_are_named_on_the_page(tmp_path, monkeypatch):
    """`_tier_of` matches the four tier NAMES inside a model id, so a Claude model named outside that
    vocabulary (Mythos is already one, in Anthropic's own cache-pricing footnote) contributes to no
    tier, no cost and no calendar cell. The producer has always published those tokens under
    `unweighted`; the page never showed it, so the omission was invisible by construction — and it
    got sharper once empty months stopped being drawn, because such a month no longer appears at
    all rather than appearing blank."""
    qd = _sidecar(tmp_path, monkeypatch, {"claude-mythos-5-1": 4_200_000_000})

    panel = _text(_usage(qd))

    assert "4,200,000,000 tokens are NOT in any total on this page" in panel
    assert "claude-mythos-5-1" in panel, "name the model, or nobody can act on the warning"


def test_no_unclassified_tokens_means_no_warning(tmp_path, monkeypatch):
    """A warning that shows when nothing is wrong is wallpaper, and wallpaper is how a real one gets
    read past."""
    qd = _sidecar(tmp_path, monkeypatch, {})

    panel = _text(_usage(qd))

    assert "NOT in any total" not in panel
    assert "Daily token consumption" in panel, (
        "the panel still rendered — the assertion above is real"
    )


def test_the_warning_survives_the_blank_panel_path(tmp_path, monkeypatch):
    """All-unrecognised is precisely the state that empties `tiers`, and an empty `tiers` is the
    early return that renders no table. So the one case where the panel goes quiet is the one case
    where the reader most needs to be told why — the warning is computed before that return, not
    beside the table."""
    qd = _sidecar(tmp_path, monkeypatch, {"claude-mythos-5-1": 9_000_000})
    blank = json.loads(qd._COST_SIDECAR.read_text(encoding="utf-8"))
    blank["per_model_spend"]["tiers"] = {}
    blank["per_model_spend"]["spend_usd"] = None
    blank["per_model_spend"]["base_rate_per_mtok"] = None
    qd._COST_SIDECAR.write_text(json.dumps(blank), encoding="utf-8")

    html_ = _usage(qd)

    assert "9,000,000 tokens are NOT in any total on this page" in _text(html_)
    assert not _find(_dom(html_), "div", aria_labelledby="usage-tiers"), "no zeroed tier table"
    assert "No tier-weighted spend is recorded yet" in _text(html_), "only the explanation"


def test_the_headline_says_the_monthly_fee_not_just_the_window_slice(tmp_path, monkeypatch):
    """The operator read "$778.49" as the subscription price and asked why it was not $800 — which
    is the right question, because the sentence called it "the real subscription of $778.49". A
    rolling 30-day window straddles two months whose DAILY rates differ ($800/31 in August,
    $800/30 in September), so its sum is never the monthly fee. The header now states the fee, the
    day count and the split that produced the number."""
    qd = _sidecar(tmp_path, monkeypatch, {})
    doc = json.loads(qd._COST_SIDECAR.read_text(encoding="utf-8"))
    doc["per_model_spend"]["monthly_spend"] = {"2026-08": 800.0, "2026-09": 800.0}
    qd._COST_SIDECAR.write_text(json.dumps(doc), encoding="utf-8")

    panel = _text(_usage(qd))

    assert "$800/month" in panel, "the FEE must be on the page, not only the window slice"
    assert "25 August day(s) at $800/31" in panel and "5 September day(s) at $800/30" in panel
    assert "not a calendar month" in panel


def test_an_underivable_fee_breakdown_is_omitted_not_guessed(tmp_path, monkeypatch):
    """The window's own months are what the breakdown needs. If the sidecar does not carry a fee for
    one of them, the number still stands and the explanation is simply absent — an invented split
    would be worse than none."""
    qd = _sidecar(tmp_path, monkeypatch, {})  # monthly_spend has 2026-09 only; the window spans 08
    panel = _text(_usage(qd))
    assert "priced against $800.00 for that window" in panel
    assert "August day(s) at" not in panel and "$800/month" not in panel


# --- a scaffolded-but-unlogged dir is SHOWN, not dropped (5th account, 2026-09-06) ------------
# `--new-dir` records the slug in assignments.json as identity `pending-login`; `--status --json`
# reports it under `pending`, not `accounts`. The board read only `accounts`, so the operator who
# had just scaffolded `ozgurbasak` saw a four-row board and could not tell "not scaffolded" from
# "not logged in". The row must appear — greyed, ineligible, with the one action that pins it.


def _pending_payload(pending: list[str]) -> dict:
    return {
        "fleet_root": "/x/.claude-fleet",
        "active": "ob",
        "pause": None,
        "fleet_warnings": [],
        "pending": pending,
        "accounts": [
            {
                "email": "ob@ocoron.com",
                "slugs": ["ob"],
                "source": "live",
                "weekly_cap": 95,
                "cap_walled": False,
                "chain_stale": False,
                "five_hour": {"utilization": 10.0, "resets_at_epoch": 2_000_000_000},
                "seven_day": {"utilization": 20.0, "resets_at_epoch": 2_000_000_000},
            }
        ],
    }


def test_a_pending_login_dir_is_rendered_with_its_one_action(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    html_ = _pending_view(qd, monkeypatch, _pending_payload(["ozgurbasak"]))
    row = _acct_row(html_, "ozgurbasak", "pending")
    assert "ozgurbasak" in row.words(), "the scaffolded dir vanished from the board"
    assert "pending-login" in row.words(), "the row must say WHY it is not an account yet"
    assert "/login" in row.words(), "the row must name the one action that pins it"
    # it is never mistaken for a candidate: no switch button, and it sorts after every account
    assert _buttons(row, "/switch") == []
    order = [r.attrs["data-acct"] for r in _find(_dom(html_), "tr") if "data-acct" in r.attrs]
    assert order.index("ob") < order.index("ozgurbasak")


def test_no_pending_key_renders_no_pending_row(tmp_path, monkeypatch):
    """The control: an older --status --json without `pending` must not conjure a row."""
    qd = _load(tmp_path, monkeypatch)
    p = _pending_payload([])
    del p["pending"]
    html_ = _pending_view(qd, monkeypatch, p)
    assert "pending-login" not in _text(html_)
    assert not _find(_dom(html_), "tr", data_row="pending")


# --- the Quota tab is the ROTATION QUEUE, numbered 1..N, active first (operator, 2026-09-06) -----
# "active account at the top, upcoming account second, then the third, fourth, fifth" — and an
# active account that is session-capped but will come back "is both 1st and 3rd; it must be
# indicated." The queue mirrors the picker for eligible accounts (perishable-first) and orders the
# INELIGIBLE tail by the moment each becomes eligible again (session reset if only the session is
# spent, weekly reset if walled/capped, unknown last). The active account's own return slot is a
# ghost row at its position, plus a badge on the active row.

_NOW = 1_900_000_000.0


def _q(slug, five, seven, *, five_reset=None, seven_reset=None, cap=None, cap_walled=False):
    return {
        "email": f"{slug}@ocoron.com",
        "slugs": [slug],
        "source": "live",
        "weekly_cap": cap,
        "cap_walled": cap_walled,
        "chain_stale": False,
        "five_hour": {"utilization": five, "resets_at_epoch": five_reset},
        "seven_day": {"utilization": seven, "resets_at_epoch": seven_reset},
    }


def _queue_payload(active_five=20.0, active_five_reset=_NOW + 4 * 3600):
    return {
        "fleet_root": "/x",
        "active": "ob",
        "pause": None,
        "fleet_warnings": [],
        "pending": [],
        "accounts": [
            # active
            _q(
                "ob",
                active_five,
                60.0,
                five_reset=active_five_reset,
                seven_reset=_NOW + 3 * 86400,
                cap=90,
            ),
            # eligible: perishable-first → soonest WEEKLY reset wins
            _q("zeta", 5.0, 30.0, five_reset=_NOW + 3600, seven_reset=_NOW + 1 * 86400, cap=99),
            _q("alpha", 5.0, 10.0, five_reset=_NOW + 3600, seven_reset=_NOW + 2 * 86400, cap=99),
            # ineligible, session-spent (weekly fine): returns at its 5h reset, in 2h
            _q(
                "mob", 100.0, 40.0, five_reset=_NOW + 2 * 3600, seven_reset=_NOW + 4 * 86400, cap=99
            ),
            # ineligible, cap-walled: returns at its WEEKLY reset, in 20h
            _q(
                "can",
                5.0,
                99.0,
                five_reset=_NOW + 600,
                seven_reset=_NOW + 20 * 3600,
                cap=99,
                cap_walled=True,
            ),
        ],
    }


def _accounts_at(qd, payload: dict, now: float) -> str:
    """The Accounts view at a fixed clock: the module's own `_view_data` (its queue included) and
    the real view, both handed ``now`` — the queue fixtures sit at a fixed `_NOW`, not the wall clock."""
    from dashboard_ui.views import ViewContext

    qd._set_last_status(now, payload)
    ctx = ViewContext(opt_root=_opt(), fabrik_root=qd._FABRIK_ROOT, now=now)
    return str(qd._views.load("accounts").render(qd._view_data("accounts", ctx), ctx).html)


def _queue_rows(markup: str) -> list[tuple[str, str]]:
    """(slug, row kind) of every account-table row, in display order."""
    return [
        (r.attrs["data-acct"], r.attrs.get("data-row", ""))
        for r in _find(_dom(markup), "tr")
        if "data-acct" in r.attrs
    ]


def test_queue_is_numbered_active_first_then_the_picker_order_then_returns_by_time(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)
    order = [e["slug"] for e in qd._queue(_queue_payload(), _NOW)]
    assert order == ["ob", "zeta", "alpha", "mob", "can"], order
    html_ = _accounts_at(qd, _queue_payload(), _NOW)
    assert [s for s, _k in _queue_rows(html_)] == ["ob", "zeta", "alpha", "mob", "can"]
    # every account row carries its 1-based queue position — its rank badge — in display order
    per_row = []
    for slug, _kind in _queue_rows(html_):
        marks = [n for n in _find(_acct_row(html_, slug), "span") if "data-severity" in n.attrs]
        per_row.append(
            next(n.children[-1].words() for n in marks if n.children[-1].words().startswith("#"))
        )
    assert [p.split()[0] for p in per_row] == ["#1", "#2", "#3", "#4", "#5"], per_row
    assert (
        per_row[0].startswith("#1 ACTIVE")
        and per_row[1] == "#2 NEXT"
        and per_row[2] == "#3 in line"
    )


def test_ineligible_tail_is_ordered_by_when_it_returns_not_by_utilization(tmp_path, monkeypatch):
    """mob (session-spent, back in 2h) must precede can (cap-walled, back in 20h) even though
    mob's session reads 100% and can's reads 5% — the queue is about WHEN, not how full."""
    qd = _load(tmp_path, monkeypatch)
    entries = {e["slug"]: e for e in qd._queue(_queue_payload(), _NOW)}
    assert entries["mob"]["returns_at"] == _NOW + 2 * 3600
    assert entries["can"]["returns_at"] == _NOW + 20 * 3600
    html_ = _accounts_at(qd, _queue_payload(), _NOW)
    assert "#4 — returns" in _acct_row(html_, "mob").words()
    assert "#5 — returns" in _acct_row(html_, "can").words()


def test_a_session_capped_active_account_is_both_first_and_its_return_slot(tmp_path, monkeypatch):
    """Active at 96% session with a 5h reset in 4h: it is #1 now AND it comes back after mob (2h)
    but before can (20h) → a ghost row at #5 saying so, and a badge on the active row."""
    qd = _load(tmp_path, monkeypatch)
    p = _queue_payload(active_five=96.0, active_five_reset=_NOW + 4 * 3600)
    slugs = [e["slug"] for e in qd._queue(p, _NOW)]
    assert slugs == ["ob", "zeta", "alpha", "mob", "ob", "can"], slugs
    html_ = _accounts_at(qd, p, _NOW)
    rows = _queue_rows(html_)
    assert rows[0] == ("ob", "active") and rows[4] == ("ob", "return"), rows
    ghost = _acct_row(html_, "ob", "return")
    assert "ob@ocoron.com" in ghost.words(), "the active account must appear at its return slot too"
    assert "#5 — returns" in ghost.words(), "the return slot is a distinct row naming its position"
    assert "also #5" in _acct_row(html_, "ob", "active").words(), (
        "the active row names its return slot"
    )


def test_a_healthy_active_account_has_no_return_slot(tmp_path, monkeypatch):
    """At 20% session the active account is not leaving; a return row would be noise."""
    qd = _load(tmp_path, monkeypatch)
    slugs = [e["slug"] for e in qd._queue(_queue_payload(active_five=20.0), _NOW)]
    assert slugs.count("ob") == 1
    rows = _queue_rows(_accounts_at(qd, _queue_payload(active_five=20.0), _NOW))
    assert ("ob", "return") not in rows


# --- review pass 1 (2026-09-06): C5/C6/C7 — one sort key, one clock, a reset AT now is "now" ----
def test_display_order_and_queue_share_one_key_and_one_clock(tmp_path, monkeypatch):
    """C5/C6: _display_order had its own copy of the perishable-first key (unknown reset = now+365d)
    while _queue_for_render used inf, and read time.time() while render() passed generated_at — two
    copies that could disagree. One function, one `now`."""
    qd = _load(tmp_path, monkeypatch)
    p = _queue_payload()
    # P3-4: with every account carrying a weekly reset the two keys could not diverge (the pre-fix
    # function passed this test verbatim); strip one eligible account's resets so perishable-first
    # (unknown = inf vs now+365d) is exercised, at a clock far from time.time()
    for acc in p["accounts"]:
        if acc["slugs"][0] == "alpha":
            acc["five_hour"]["resets_at_epoch"] = None
            acc["seven_day"]["resets_at_epoch"] = None
    a = [e["slug"] for e in qd._queue_for_render(p, _NOW) if e["kind"] != "return"]
    b = [x["slugs"][0] for x in qd._display_order(p, _NOW)]
    assert a == b
    assert "alpha" in a
    assert "far = time.time()" not in Path(qd.__file__).read_text(), (
        "a second key closure crept back"
    )


def test_a_reset_exactly_at_now_reads_as_returning_now_not_unknown(tmp_path, monkeypatch):
    """C7: strict `>` made a reset AT now read as None → 'return time unknown', sorted last."""
    qd = _load(tmp_path, monkeypatch)
    a = _q("x", 100.0, 40.0, five_reset=_NOW, seven_reset=_NOW + 86400, cap=99)
    assert qd._returns_at(a, _NOW) == _NOW


def test_a_weekly_walled_account_in_the_pickers_refused_band_returns_at_its_session_reset(
    tmp_path, monkeypatch
):
    """P3-2 (board half): a weekly reset does not lift a session the picker refuses (≥85); the
    tail row said "returns in 1h" for an account at 90% whose 5h window resets in 10h."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.delenv("ROTATE_TARGET_SESSION_MAX_PCT", raising=False)
    a = _q(
        "band",
        90.0,
        99.0,
        five_reset=_NOW + 36000,
        seven_reset=_NOW + 3600,
        cap=99,
        cap_walled=True,
    )
    assert qd._returns_at(a, _NOW) == _NOW + 36000
    b = _q(
        "fine",
        20.0,
        99.0,
        five_reset=_NOW + 36000,
        seven_reset=_NOW + 3600,
        cap=99,
        cap_walled=True,
    )
    assert qd._returns_at(b, _NOW) == _NOW + 3600


def test_the_board_applies_the_rolled_over_rule_where_it_judges_eligibility(tmp_path, monkeypatch):
    """R4: the cell renderer said "idle — rolled over" while `_util`/`_eligible`/`_returns_at`
    read the raw 100% and called the same cached row walled — board and picker disagreed."""
    qd = _load(tmp_path, monkeypatch)
    a = _q("rolled", 100.0, 100.0, five_reset=_NOW - 600, seven_reset=_NOW - 600, cap=99)
    a["source"] = "cache"
    monkeypatch.setattr(qd.time, "time", lambda: _NOW)
    assert qd._util(a, "five_hour") == 0.0 and qd._util(a, "seven_day") == 0.0
    assert qd._eligible(a) is True


def test_exactly_at_the_session_bar_the_account_is_pickable_not_waiting(tmp_path, monkeypatch):
    """R5: the picker refuses `> bar`; `>=` at exactly 85.0 promised a wait the picker did not require."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.delenv("ROTATE_TARGET_SESSION_MAX_PCT", raising=False)
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    a = _q(
        "bar", 85.0, 99.0, five_reset=_NOW + 36000, seven_reset=_NOW + 3600, cap=99, cap_walled=True
    )
    assert qd._returns_at(a, _NOW) == _NOW + 3600


def test_the_session_bar_parses_like_claude_rotates_env_float(tmp_path, monkeypatch):
    """R6: a third parse of one knob with a fourth semantics — nan/abc/"" must fall back the way
    `_env_float` does, never silently disable the later-of-two rule."""
    qd = _load(tmp_path, monkeypatch)
    for bad in ("nan", "abc", "", "inf"):
        monkeypatch.setenv("ROTATE_TARGET_SESSION_MAX_PCT", bad)
        monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", "90")
        assert qd._session_bar() == 90.0, bad
    monkeypatch.setenv("ROTATE_TARGET_SESSION_MAX_PCT", "abc")
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    assert qd._session_bar() == 85.0


def _relief_payload(active=(93.0, 97.0), sibling=(0.0, 19.0)):
    p = _payload(session=active[0], weekly=active[1])
    p["accounts"][0]["weekly_cap"] = 99
    p["accounts"].append(
        {
            "email": "oz@ocoron.com",
            "slugs": ["oz"],
            "five_hour": {"utilization": sibling[0], "resets_at_epoch": time.time() + 7200},
            "seven_day": {"utilization": sibling[1], "resets_at_epoch": time.time() + 400000},
            "source": "live",
            "age_s": None,
            "weekly_cap": 99,
            "cap_walled": False,
        }
    )
    return p


def test_a_weekly_driven_relief_invokes_the_tick_from_the_fast_path(tmp_path, monkeypatch):
    """R6 (native reader on the relief flip): the fast path keyed on the SESSION only, so an
    active at session 93 / weekly 97 with a fresh sibling waited for the */5 cron."""
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=40.0)
    t = qd._maybe_trigger_rotation(_relief_payload(active=(40.0, 97.0)))
    assert t is not None
    t.join(10)
    assert [c for c in _calls(stub) if c[:1] == ["--tick"]] == [["--tick"]]


def test_the_relief_fast_path_needs_a_sibling_below_the_band(tmp_path, monkeypatch):
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=40.0)
    assert (
        qd._maybe_trigger_rotation(_relief_payload(active=(40.0, 97.0), sibling=(20.0, 88.0)))
        is None
    )
    assert qd._maybe_trigger_rotation(_relief_payload(active=(40.0, 70.0))) is None, (
        "below the band: nothing"
    )
    assert not [c for c in _calls(stub) if c[:1] == ["--tick"]]


def test_the_ghost_return_row_renders_for_an_active_the_tick_will_relief_flip(
    tmp_path, monkeypatch
):
    """R6 (board half): the ghost row fired at session >= 95 only; an active at 93/97 that the
    tick relief-flips away rendered as #1 only, telling the operator it is staying."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.delenv("ROTATE_DRAIN_THRESHOLD", raising=False)
    p = _queue_payload(active_five=93.0)
    p["accounts"][0]["seven_day"]["utilization"] = 97.0
    kinds = [e["kind"] for e in qd._queue(p, _NOW)]
    assert "return" in kinds, kinds
    assert ("ob", "return") in _queue_rows(_accounts_at(qd, p, _NOW))


def test_a_garbage_session_bar_knob_neither_crashes_import_nor_disagrees_with_itself(
    tmp_path, monkeypatch
):
    """F4 (non-author pass over 58041dbd, 2026-09-07): `_TARGET_SESSION_MAX` and
    `BLIND_TRIGGER_THRESHOLD` were import-time `float(os.getenv(...))` reads of the knobs
    `_session_bar` had just been hardened for — `abc` crashed the whole board at import and `nan`
    made nobody eligible while the guarded parser read 85. One lazy guarded parser now."""
    qd = _load(tmp_path, monkeypatch)
    assert not hasattr(qd, "_TARGET_SESSION_MAX") and not hasattr(qd, "BLIND_TRIGGER_THRESHOLD")
    row = {"five_hour": {"utilization": 84.0}, "seven_day": {"utilization": 10.0}}
    for bad in ("abc", "", "nan", "inf"):
        monkeypatch.setenv("ROTATE_TARGET_SESSION_MAX_PCT", bad)
        monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", bad)
        assert qd._session_bar() == 85.0 == qd._drain_band(), bad
        assert qd._eligible(row) is True, bad
    monkeypatch.setenv("ROTATE_TARGET_SESSION_MAX_PCT", "80")
    assert qd._eligible(row) is False, "the live knob, read lazily, decides"
    monkeypatch.delenv("ROTATE_TARGET_SESSION_MAX_PCT")
    monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", "70")
    assert qd._session_bar() == 70.0 == qd._drain_band()


def test_util_uses_the_callers_clock_so_returns_at_and_util_agree(tmp_path, monkeypatch):
    """F8: `_util` read `time.time()` inside functions handed an explicit `now`; a payload probed
    at T and rendered at T+Δ could have `_util` zero a rolled cached window against wall-clock
    while `_returns_at` judged the same reset against `generated_at`."""
    qd = _load(tmp_path, monkeypatch)
    reset = 1_000_000.0
    a = {
        "source": "cache",
        "five_hour": {"utilization": 100.0, "resets_at_epoch": reset},
        "seven_day": {"utilization": 20.0, "resets_at_epoch": reset + 86_400},
    }
    assert qd._util(a, "five_hour", reset - 1) == 100.0, "before the reset: the raw reading"
    assert qd._util(a, "five_hour", reset) == 0.0, "at/after the reset: rolled over"
    monkeypatch.setattr(qd.time, "time", lambda: reset + 5)
    assert qd._util(a, "five_hour") == 0.0, "no clock given: wall-clock, as before"
    # handed a clock BEFORE the reset, both mirrors see a spent window that returns at `reset`
    assert qd._returns_at(a, reset - 1) == reset
    # …and `_eligible` on the SAME clock agrees (closing reader over c233c0b7): spent before,
    # rolled over (eligible) after — never wall-clock-eligible beside a payload-clock `returns`
    assert qd._eligible(a, reset - 1) is False and qd._eligible(a, reset + 1) is True
    assert qd._hottest(a, reset - 1) == 100.0 and qd._hottest(a, reset + 1) == 20.0


def test_a_bad_percent_knob_is_ignored_loudly(tmp_path, monkeypatch, capsys):
    """Native closing reader N8: the picker's `_env_float` rejects a non-finite knob LOUDLY
    (a silently-disabled bar is the failure mode the knob guards against); the F4 consolidation
    reproduced its values and dropped that property."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", "nan")
    assert qd._drain_band() == 85.0
    monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", "abc")
    assert qd._drain_band() == 85.0
    err = capsys.readouterr().err
    assert "ROTATE_DRAIN_THRESHOLD='nan' is not finite" in err and "'abc' is not a number" in err


# ── D-181/D-182 — the pool column follows LIVE text; the native-subagents column (2026-09-08) ───────


def test_pool_dot_ignores_a_commented_pool_contract(tmp_path, monkeypatch):
    """The corpus keeps the pool contract inside `<!-- POOL OFF -->` comments for re-enable; a dot
    must follow the live text only — a rendered command whose ONLY `fanout(` sits in a comment
    reaches nothing, and one with a live call still lights the dot."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-review"
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(
            tmp_path, name, '# x\n<!-- POOL OFF: fanout("review", …) -->\nrun WebSearch here\n'
        ),
    )
    services, is_rendered = qd._command_services(name)
    assert is_rendered and "pool" not in services
    monkeypatch.setattr(
        qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, '# x\nfanout("review", units)\n')
    )
    services, _ = qd._command_services(name)
    assert "pool" in services  # a LIVE call would still be visible — the column is not blind


def _commands_with(qd, monkeypatch, rows: list[dict]) -> str:
    """The Commands view as served over ``rows`` (the catalogue's own fields filled in)."""
    full = [
        {"stage": "", "purpose": "", "when": "", "skip": "", "next": "", "natives": [], "rule": (False, ()),
         "tiers": (), "services": set(), "rendered": True, **r}
        for r in rows
    ]  # fmt: skip
    with monkeypatch.context() as m:
        m.setattr(qd, "_load_commands", lambda: full)
        return _view(qd, "commands")


def _catalogue_cells(markup: str, name: str) -> dict[str, str]:
    """The catalogue row of /<name>, as {column head: cell words}."""
    region = _find(_dom(markup), "div", aria_labelledby="commands-table")[0]
    heads = [h.words() for h in _find(region, "th", scope="col")]
    for r in _find(region, "tr"):
        cells = [c for c in r.children if c.tag in ("th", "td")]
        if len(cells) == len(heads) and cells[1].words() == f"/{name}":
            return {h: c.words() for h, c in zip(heads, cells, strict=True)}
    raise AssertionError(f"no catalogue row for /{name}")


def _budget_payload(**over) -> dict:
    p = {
        "caps": {"box_cap": 23, "concurrency_cap": 17},
        "box_caps": {"read_only": 23, "heavy": 12},
        "heavy_reasons": [],
        "quota": {"ok": True, "active": "a@x", "hottest_pct": 7.0, "eligible": 1, "hold": False},
    }
    p.update(over)
    return p


def _health_strip(qd, monkeypatch) -> str:
    """The Overview's Health strip words, rendered from whatever the budget cache now holds."""
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    qd._set_last_status(time.time(), {"active": "a", "accounts": []})
    html_ = _view(qd, "overview")
    return _text(html_.split('id="ov-health"', 1)[1])


def test_the_box_budget_shows_the_maximum_and_fails_soft(tmp_path, monkeypatch):
    """D-191: the operator wants the MAXIMUM visible on the board, not the rule. The probe runs
    dispatch_headroom.py --json (read-only and heavy) and reads what the box AND quota allow now —
    the min over every cap in the payload, the CLI cap read from it, and 0 with a loud HOLD line
    when the fleet is held (round 1: the box number printed beside `hold=True`); a failed probe
    says the reason, never an empty table head; QUOTA_DASH_BUDGET=0 disables it. The reading is
    data now (T07 removed the banner's HTML half); the Overview's Health strip renders it."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "1")
    qd._budget_cache.update(ts=0.0, data=None, thread=None)
    calls = []
    state = {"hold": False, "quota_cap": None}

    class _R:
        def __init__(self, args):
            calls.append(list(args))
            caps = {"box_cap": 23, "concurrency_cap": 17}
            if state["quota_cap"] is not None:
                caps["quota_cap"] = state["quota_cap"]
            q = {
                "ok": True,
                "active": "a@x",
                "hottest_pct": 7.0,
                "eligible": 1,
                "hold": state["hold"],
            }
            self.stdout = json.dumps(_budget_payload(caps=caps, quota=q))

    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _R(args))
    r = qd._budget_probe()
    seats = {s["key"]: s for s in r["seats"]}
    assert (seats["read_only"]["allowed"], seats["read_only"]["box"]) == (17, 23)
    assert (seats["heavy"]["allowed"], seats["heavy"]["box"]) == (12, 12)
    assert r["cli_cap"] == 17
    strip = _health_strip(qd, monkeypatch)
    assert (
        "read-only seats allowed now: 17 (box 23)" in strip
    )  # nothing reserved: no reservation clause
    assert "heavy seats allowed now: 12 (box 12" in strip
    assert "CLI cap 17" in strip and "CLI cap 20" not in strip
    # ONE probe per refresh — the fleet round-trip inside it is the thing the module bounds
    assert len(calls) == 1 and "--heavy" not in calls[0]
    # the quota cap binds when the payload carries it; a HOLD is 0 seats and says so
    state["quota_cap"] = 3
    r = qd._budget_probe()
    ro = next(s for s in r["seats"] if s["key"] == "read_only")
    assert ro["allowed"] == 3 and ro["box"] == 23 and ro["quota_cap"] == 3 and ro["has_quota_cap"]
    state["hold"] = True
    r = qd._budget_probe()
    assert r["hold"] is True and all(s["allowed"] == 0 for s in r["seats"])
    strip = _health_strip(qd, monkeypatch)
    assert (
        "allowed now: 0" in strip
        and "fleet hold — dispatch nothing" in strip
        and "at 7.0%" not in strip
    )

    def boom(args, **kw):
        raise OSError("probe down")

    monkeypatch.setattr(qd.subprocess, "run", boom)
    assert qd._budget_probe() == {"error": "OSError: probe down"}
    assert "budget failed: OSError: probe down" in _health_strip(qd, monkeypatch)
    # the line never blocks a render on the probe: a stale cache returns a placeholder and
    # starts ONE background refresh; the next render reads what it computed
    qd._budget_cache.update(ts=0.0, data=None, thread=None)
    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _R(args))
    assert qd._budget_data() == {"computing": True}
    qd._budget_cache["thread"].join(timeout=10)
    assert qd._budget_data()["seats"]
    # round 7: the sibling reservation and the floor are read from the script's own verdict; the
    # script's caveats (a failed sibling probe, a LOWER bound, an env-only own id) reach the board;
    # standbys are the COOL ones of the eligible
    payload = {
        "caps": {"box_cap": 3, "concurrency_cap": 17},
        "box_caps": {"read_only": 3, "heavy": 3},
        "floor": 3,
        "box": {"ok": True},
        "box_caps_floored": {
            "read_only": True,
            "heavy": True,
        },  # the script's own verdict (round 9)
        "heavy_reasons": [],
        "siblings": {"seats": 21, "ok": True},
        "quota": {
            "ok": True,
            "active": "a@x",
            "hottest_pct": 7.0,
            "eligible": 0,
            "eligible_raw": 1,
        },
        "reasons": ["2 running sibling session(s) carry NO seat figure — a LOWER bound"],
    }

    class _P:
        def __init__(self, args):
            self.stdout = json.dumps(payload)

    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _P(args))
    r = qd._budget_probe()
    assert all(s["floored"] and s["taken"] == 21 for s in r["seats"])
    assert r["quota"]["eligible"] == 0 and r["quota"]["eligible_raw"] == 1
    assert r["caveats"] == ["2 running sibling session(s) carry NO seat figure — a LOWER bound"]
    strip = _health_strip(qd, monkeypatch)
    assert "0 cool standbys of 1 eligible" in strip and "21 reserved by sibling sessions" in strip
    assert "Caveats: 2 running sibling session(s) carry NO seat figure — a LOWER bound" in strip
    payload["box_caps"] = {"read_only": 20, "heavy": 9}
    payload["box_caps_floored"] = {"read_only": False, "heavy": False}
    payload["caps"]["box_cap"] = 20
    payload["siblings"] = {"seats": 0, "ok": False, "why": "sibling probe failed: PermissionError"}
    payload["reasons"] = []
    r = qd._budget_probe()
    assert not any(s["floored"] for s in r["seats"]) and all(s["taken"] == 0 for s in r["seats"])
    assert r["caveats"] == [
        "sibling probe failed: PermissionError — sibling seats unknown, not subtracted"
    ]
    payload["siblings"] = {"seats": 2, "ok": True}
    r = qd._budget_probe()
    assert all(s["taken"] == 2 and not s["floored"] for s in r["seats"]) and r["caveats"] == []
    # a box or quota probe that FAILED is held at the floor — the caveat must say so (round 8)
    payload["reasons"] = ["psutil not importable — box unknown, held at the floor"]
    assert qd._budget_probe()["caveats"] == [
        "psutil not importable — box unknown, held at the floor"
    ]
    payload["reasons"] = [
        "quota: 0 of 1 standby(s) are COOL — every fallback is itself in the drain band"
    ]
    assert "0 of 1 standby(s) are COOL" in qd._budget_probe()["caveats"][0]
    # a DEAD box probe holds the cap at the floor: the caveat says so and the floor flag never blames
    # the sibling reservation for it (round-8 Opus finding)
    payload["box"] = {"ok": False, "why": "box probe failed: /proc/meminfo"}
    payload["box_caps"] = {"read_only": 3, "heavy": 3}
    payload["siblings"] = {"seats": 5, "ok": True}
    payload["reasons"] = ["box probe failed: /proc/meminfo — box unknown, held at the floor"]
    r = qd._budget_probe()
    assert not any(s["floored"] for s in r["seats"]) and all(s["taken"] == 5 for s in r["seats"])
    assert r["caveats"] == ["box probe failed: /proc/meminfo — box unknown, held at the floor"]
    payload.pop("box")
    # round 9: an ABSENT box block is unknown — the floor flag must not fire; the over-dispatch
    # caveat is spelled "NOT subtracted" by the script — case must not hide it; a hard cap below
    # the floor and a malformed concurrency cap are caveats too
    assert not any(s["floored"] for s in qd._budget_probe()["seats"])
    payload["box"] = {"ok": True}
    payload["siblings"] = {"seats": 0, "ok": False, "why": "sibling probe failed: EACCES"}
    payload["reasons"] = [
        "below the floor because a HARD cap binds (quota_cap=0) — dispatch nothing until relief"
    ]
    caveats = qd._budget_probe()[
        "caveats"
    ]  # round 11: an unrelated caveat must not hide a failed sibling probe
    assert "sibling probe failed: EACCES — sibling seats unknown, not subtracted" in caveats
    payload["siblings"] = {"seats": 0, "ok": True}
    payload["reasons"] = [
        "1 sibling record(s) unreadable (x.json) — their seats are NOT subtracted; the box number is an UPPER bound",
        "below the floor because a HARD cap binds (quota_cap=0) — dispatch nothing until relief",
        "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS='x' is not a number — using 20",
    ]
    caveats = qd._budget_probe()["caveats"]
    assert caveats == payload["reasons"]
    payload["reasons"] = []
    # the HEAVY half's reasons reach the caveats too, LABELLED (round-10 Opus: a heavy-only
    # over-commit rendered with no warning)
    payload["heavy_reasons"] = [
        "floor granted: 2 seat(s) past what the box has left after the sibling reservation"
    ]
    assert qd._budget_probe()["caveats"] == [
        "heavy half — floor granted: 2 seat(s) past what the box has left after the sibling reservation"
    ]
    payload["heavy_reasons"] = []
    # a probe that predates the halves SAYS so (round 11: an absent key read as "no heavy caveats")
    payload.pop("heavy_reasons")
    assert any("probe payload predates heavy_reasons" in c for c in qd._budget_probe()["caveats"])
    payload["heavy_reasons"] = []
    # the read-only half is read too — a caveat only IT carries renders (round 12)
    payload["reasons_read_only"] = ["read-only-only: box unknown, held at the floor"]
    assert qd._budget_probe()["caveats"] == ["read-only-only: box unknown, held at the floor"]
    payload.pop("reasons_read_only")
    # a line repeated INSIDE heavy_reasons renders once (round 13)
    payload["heavy_reasons"] = ["floor granted: 2 seat(s) past what the box has left"] * 2
    assert qd._budget_probe()["caveats"] == [
        "heavy half — floor granted: 2 seat(s) past what the box has left"
    ]
    # a cause in BOTH halves is not heavy-only: rendered once, unlabelled (round 14)
    payload["heavy_reasons"] = ["quota HOLD is on — dispatch nothing"]
    payload["reasons"] = ["quota HOLD is on — dispatch nothing"]
    assert qd._budget_probe()["caveats"] == ["quota HOLD is on — dispatch nothing"]
    # the read-only half and the heavy half sharing a cause the run's own half lacks: once, unlabelled
    payload["reasons"] = []
    payload["reasons_read_only"] = ["quota HOLD is on — dispatch nothing"]
    assert qd._budget_probe()["caveats"] == ["quota HOLD is on — dispatch nothing"]
    payload.pop("reasons_read_only")
    payload["heavy_reasons"] = []
    # an older probe without box_caps must not let the read-only cap pose as the heavy one
    monkeypatch.setattr(
        qd.subprocess,
        "run",
        lambda args, **kw: type(
            "R", (), {"stdout": json.dumps({"caps": {"box_cap": 23}, "quota": {}})}
        )(),
    )
    assert "carries no box_caps" in qd._budget_probe()["error"]
    # single-flight under CONCURRENT stale-cache renders: N threads, ONE probe thread started
    import threading

    qd._budget_cache.update(ts=0.0, data=None, thread=None)
    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _R(args))
    calls.clear()
    gate = threading.Barrier(6)

    def hit():
        gate.wait(timeout=5)
        qd._budget_data()

    ts = [threading.Thread(target=hit) for _ in range(6)]
    for th in ts:
        th.start()
    for th in ts:
        th.join(timeout=5)
    qd._budget_cache["thread"].join(timeout=10)
    assert len(calls) == 1
    # an account switch invalidates the cache (round 4): the next reading is a placeholder or a
    # fresh probe, never the old account's headroom
    qd._budget_cache.update(
        ts=time.time(), data={"quota": {"active": "OLD ACCOUNT"}, "seats": []}, thread=None
    )
    with qd._budget_lock:
        qd._budget_cache.update(ts=0.0, data=None)  # the exact statement `_rerender` runs
    assert qd._budget_data() == {"computing": True}
    qd._budget_cache["thread"].join(timeout=10)
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "0")
    assert qd._budget_data() == {"disabled": True}


def test_native_subagents_column_follows_the_commands_own_steps(tmp_path, monkeypatch):
    """Per command: how many native subagent types it names and which (operator ask 2026-09-08).
    Boilerplate every command carries by assembly (the D-181 banner's enumeration, the close-out
    fragment's 'Subagents are ephemeral' paragraph) never counts; a commented mention never
    counts; the command's own steps do, in display order."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-review"
    body = (
        "# x\n\n> POOL OFF — run every fan-out NATIVELY — Claude Task subagents "
        "(`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose): same unit split.\n\n"
        "Subagents are ephemeral. A `fabrik-reviewer` that notices a false-positive check, a\n"
        "`fabrik-researcher` that hits a dead reference — file it.\n\n"
        "<!-- POOL OFF: dispatch a `design-review` agent here -->\n"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, body))
    assert qd._command_natives(name) == []  # boilerplate + comment only → nothing of its own
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(
            tmp_path,
            name,
            body
            + "\n## Phase 1\nDispatch one `general-purpose` seat per screen, then a `fabrik-reviewer` on Opus.\n",
        ),
    )
    assert qd._command_natives(name) == [
        ("fabrik-reviewer", ("opus",)),  # the tier named beside the seat rides with it
        ("general-purpose", ()),  # no tier named → the name alone
    ]
    natives = [("fabrik-reviewer", ("opus", "sonnet")), ("general-purpose", ())]
    cells = _catalogue_cells(
        _commands_with(qd, monkeypatch, [{"name": name, "natives": natives}]), name
    )
    # the cell leads with the dispatch RULE (none in this fixture row), then the types
    assert (
        cells["Native subagents"]
        == "no per-unit rule · fabrik-reviewer (opus, sonnet), general-purpose"
    )
    cells = _catalogue_cells(_commands_with(qd, monkeypatch, [{"name": name, "natives": []}]), name)
    assert cells["Native subagents"] == "-" and "0 ·" not in cells["Native subagents"]


def test_a_tier_between_two_adjacent_seats_is_awarded_to_one_of_them(tmp_path, monkeypatch):
    """Round-1 finding, author-blind: the first fence bounded each seat's window by its NEIGHBOURS,
    which arbitrates only when a THIRD seat stands between two of them — so a tier in the gap
    between exactly two adjacent seats was credited to both. A tier belongs to the nearest seat."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-review"
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(tmp_path, name, "`fabrik-reviewer` on Opus and then `general-purpose`.\n"),
    )
    assert qd._command_natives(name) == [("fabrik-reviewer", ("opus",)), ("general-purpose", ())]


def test_general_purpose_is_a_seat_only_in_code_span_form(tmp_path, monkeypatch):
    """Round-1 finding, author-blind: `general-purpose` is also an ordinary English adjective, and
    fabrik-vision's "Never wire a general-purpose vendor SDK" — prose about someone else's
    architecture — was being counted as a dispatched seat. Measured that day: 13 of the corpus's 14
    live mentions are code spans, and the 14th is that sentence."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-vision"
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(tmp_path, name, "Never wire a general-purpose vendor SDK as the LLM path.\n"),
    )
    assert qd._command_natives(name) == []
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(tmp_path, name, "Dispatch one `general-purpose` seat per doc.\n"),
    )
    assert qd._command_natives(name) == [("general-purpose", ())]


def test_the_seat_column_reports_the_dispatch_rule_not_the_type_count(tmp_path, monkeypatch):
    """Operator, 2026-09-08: "i want to see subagents counts correctly". The column led with the
    number of seat TYPES, so /fabrik-review read as "1 subagent" when its own steps dispatch an Opus
    floor plus one Sonnet seat per failure-class group. Under D-186 the seat count IS the unit count,
    so the cell leads with the command's own rule: the floor it carries, and the unit it fans over."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-review"

    def cell() -> str:
        row = {
            "name": name,
            "natives": qd._command_natives(name),
            "rule": qd._command_seat_rule(name),
        }
        return _catalogue_cells(_commands_with(qd, monkeypatch, [row]), name)["Native subagents"]

    body = (
        "# x\n\n**⚠️ Floor — every review dispatches ≥1 native `fabrik-reviewer` on Opus** as the "
        "authoritative pass.\n\nAdd one `fabrik-reviewer` seat on Sonnet per INDEPENDENT unit of the "
        "surface.\n"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, body))
    assert qd._command_seat_rule(name) == (True, ("unit",))
    assert cell().startswith("at least 1 opus + 1 per unit") and "fabrik-reviewer" in cell()

    # the shared fragment's sizing paragraph rides INSIDE the D-181 banner paragraph in every
    # rendered command — that is the real shape (the first draft's fixture had it standalone, which
    # never occurs, and tested a regex the banner strip made dead) — it must NOT become every
    # command's rule, or all 20 that include it report the same one
    frag = (
        "**⚠️ POOL OFF — D-181 (operator, 2026-09-07).** Size the native fan-out to the SURFACE: "
        "dispatch ONE seat PER UNIT in a single message.\n\nDispatch a `fabrik-reviewer`.\n"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, frag))
    assert qd._command_seat_rule(name) == (False, ())
    assert cell().startswith("no per-unit rule")

    # a unit counts only NEXT TO a seat word — "naming, per claim, landed / deferred" is a report
    # format and "States per screen: empty · loaded" a checklist (round-1 findings on five commands)
    prose = (
        "# x\n\nReply naming, per claim, landed / deferred / refuted.\n\nStates per screen: empty "
        "· loaded · error.\n\n"
        + ("Ground truth first: read the contract, the spec and the code. " * 4)
        + "\n\nThen dispatch one native `fabrik-reviewer` seat per\nclaim, and one "
        "seat per external dependency, all in one message.\n"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, prose))
    assert qd._command_seat_rule(name) == (False, ("claim", "dependency"))

    # a command that states a FIXED floor instead of a per-unit rule reports the number, not "none"
    fixed = "# x\n\nThe floor is 2–3 readers: native `fabrik-reviewer` seats over the diff.\n"
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, fixed))
    assert qd._command_seat_rule(name) == (False, ("!2–3 readers",))
    assert cell().startswith("2–3 readers")


def test_the_seat_rule_reads_the_real_corpus_correctly(tmp_path, monkeypatch):
    """Golden values against the corpus rendered from THIS tree — the round-1 finder reproduced five
    wrong cells that no fixture test could see. It renders into tmp_path rather than reading the
    installed corpus, whose verdict depends on the last install, not on the commit under test."""
    qd = _load(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location(
        "assemble_commands_for_seat_rule", qd._FABRIK_ROOT / "commands" / "assemble_commands.py"
    )
    assert spec is not None and spec.loader is not None
    ac = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ac)
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    # all three destinations, so the render never touches the live agents or skills dirs
    ac.render(corpus, tmp_path / "skills", tmp_path / "agents")
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", corpus)
    rule = {
        n: qd._command_seat_rule(n)
        for n in (
            "fabrik-review",
            "fabrik-upstream",
            "fabrik-user-test",
            "fabrik-plan-review",
            "fabrik-vision",
            "fabrik-review-scoped",
            "fabrik-spec",
            "fabrik-catchup",
        )
    }
    # the flagship has no Opus finder floor (D-344). Its units are NOT pinned: its real rule — two
    # finders per SLICE — is worded like the shared closing-pass fragment 22 commands include, so a
    # "slice" token would light 24 of the 38 rendered cells (measured 2026-10-03, W-d7b0d34f).
    assert rule["fabrik-review"][0] is False
    assert "claim" in rule["fabrik-upstream"][1]  # the real dispatch line spans "per\nclaim"
    assert rule["fabrik-user-test"][1] == ("flow",)  # not persona/screen/journey from prose
    # plan-review partitions per TICKET ("The partition per ticket … one fresh seat"): no seat word
    # sits within the window, so "partition" is a dispatch word (W-d7b0d34f). Its cell still leads
    # with "unit", read from the shared term-edit sentence — true for its termination loop, not pinned.
    assert "ticket" in rule["fabrik-plan-review"][1]
    assert "dependency" in rule["fabrik-vision"][1]  # "per external dependency"
    # UNITS-sized now (D-208): a per-unit refuter outranks the old fixed "floor is 3 readers"
    assert rule["fabrik-review-scoped"][1] == ("unit",)
    # the grounding floor (round 4) adds "per INDEPENDENT unit" beside the per-dependency sentence
    assert rule["fabrik-spec"][1] == ("dependency", "unit")
    assert rule["fabrik-catchup"] == (False, ())


def test_model_tiers_column_catches_a_tier_no_seat_mention_is_near(tmp_path, monkeypatch):
    """The seat column can only report a tier written NEXT to a seat. A command that tiers its work
    in its own paragraph — "Haiku only for trivial-mechanical checks" — names a real tier that no
    seat mention is within reach of, and the operator asked for those by name (2026-09-08)."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-ui-design"
    body = (
        "# x\n\nDispatch one `general-purpose` seat per screen on **Sonnet**.\n\n"
        "**Model tier the native work:** **Opus** for the UX judgment; **Haiku** for the mechanical "
        "passes (reading the a11y tree, checking design-token compliance, and the rest).\n"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, body))
    assert qd._command_natives(name) == [("general-purpose", ("sonnet",))]
    assert qd._command_tiers(name) == ("opus", "sonnet", "haiku")  # canonical order, not text order
    row = {"name": name, "stage": "2-contract", "natives": [("general-purpose", ("sonnet",))],
           "tiers": ("opus", "sonnet", "haiku")}  # fmt: skip
    assert (
        _catalogue_cells(_commands_with(qd, monkeypatch, [row]), name)["Model tiers"]
        == "opus · sonnet · haiku"
    )


def test_flywheel_column_is_a_tombstone_the_retirement_notice_cannot_light(tmp_path, monkeypatch):
    """The column stays (operator ask 2026-09-08 — the mechanism is named, so its retirement is
    visible); the dots go. The D-181 banner NAMES `record_agent_run` in the instructions it
    suspends, so a bare-symbol pattern would light every command in the corpus; only a CALL —
    outside the `<!-- POOL OFF -->` comments — is live flywheel usage."""
    qd = _load(tmp_path, monkeypatch)
    assert "fly" in {k for k, _l, _t, _p in qd._EXT_SERVICES}
    name = "fabrik-review"
    banner = (
        "**⚠️ POOL OFF — D-181 (operator, 2026-09-07).** Skip every `fanout` / `pick_models` / "
        "`set_quality` / `record_agent_run` / `results_table` step named anywhere in this command.\n\n"
    )
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(
            tmp_path,
            name,
            banner + "<!-- POOL OFF: back-fill with set_quality(r.agent_id, 5) -->\nrun it\n",
        ),
    )
    assert "fly" not in qd._command_services(name)[0]
    assert "pool" not in qd._command_services(name)[0]
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(tmp_path, name, banner + "record_agent_run(spec, result)\n"),
    )
    assert "fly" in qd._command_services(name)[0]  # a live call is still visible


def test_pool_column_reads_backticked_prose_not_only_code(tmp_path, monkeypatch):
    """`fanout` one grounder per axis` is a dispatch instruction as surely as `fanout(` — eight
    such sentences survived the D-181 corpus pass because the paren-only pattern could not see
    them (2026-09-08). The banner's own enumeration of what it SUSPENDS must not light it."""
    qd = _load(tmp_path, monkeypatch)
    name = "fabrik-spec"
    banner = (
        "**⚠️ POOL OFF — D-181 (operator, 2026-09-07).** Skip every `fanout` / `pick_models` "
        "step named anywhere in this command.\n\n"
    )
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", _rendered(tmp_path, name, banner + "ground it\n"))
    assert "pool" not in qd._command_services(name)[0]
    monkeypatch.setattr(
        qd,
        "RENDERED_COMMANDS",
        _rendered(tmp_path, name, banner + "`fanout` one INDEPENDENT grounder per axis.\n"),
    )
    assert "pool" in qd._command_services(name)[0]


def test_governor_panel_never_advertises_shedding_to_a_pool_that_is_off(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    payload = {
        "active": "ob",
        "accounts": [
            {
                "email": "ob@x.com",
                "slugs": ["ob"],
                "cap_walled": True,
                "five_hour": {"utilization": 99},
            }
        ],
    }
    qd._set_last_status(time.time(), payload)

    def governor() -> str:
        cards = [
            c.words()
            for c in _find(_dom(_accounts(qd)), "article")
            if "Quota governor" in c.words()
        ]
        assert len(cards) == 1
        return cards[0]

    monkeypatch.setenv("FABRIK_POOL_POLICY", "off")
    assert "pool OFF by ruling" in governor() and "pool-diagnose" not in governor()
    monkeypatch.setenv("FABRIK_POOL_POLICY", "on")
    assert "pool-diagnose" in governor()


def test_a_switch_orphans_the_probe_already_in_flight(tmp_path, monkeypatch):
    """Round-5 finding: the switch reset the cache but a probe thread that had started BEFORE the
    switch wrote the OLD account's reading with a fresh stamp afterwards. The switch bumps a
    generation; a probe lands only if its generation is still current — graded through the REAL
    switch_account, the budget enabled (the F102 test had re-run the reset statement itself)."""
    import threading

    qd, stub = _switch_env(tmp_path, monkeypatch)
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "1")
    started = threading.Event()
    release = threading.Event()
    real_run = qd.subprocess.run

    def slow_probe(args, **kw):  # only the budget's dispatch_headroom probe is slowed
        if any("dispatch_headroom" in str(a) for a in args):
            started.set()
            release.wait(timeout=10)
            q = {
                "ok": True,
                "active": "OLD-ACCOUNT",
                "hottest_pct": 1.0,
                "eligible": 1,
                "hold": False,
            }
            return type("R", (), {"stdout": json.dumps(_budget_payload(quota=q))})()
        return real_run(args, **kw)

    monkeypatch.setattr(qd.subprocess, "run", slow_probe)
    qd._budget_cache.update(ts=0.0, data=None, thread=None, gen=0)
    assert qd._budget_data() == {"computing": True}  # the pre-switch probe is now in flight
    assert started.wait(timeout=10)
    gen_before = qd._budget_cache["gen"]
    monkeypatch.setattr(qd, "generate", lambda: None)  # the switch's own re-probe is not under test
    status, body = qd.switch_account("sarp")
    assert status == 200 and qd._budget_cache["gen"] == gen_before + 1
    old_thread = qd._budget_cache[
        "thread"
    ]  # read BEFORE the release: the orphan branch reassigns it
    release.set()
    old_thread.join(timeout=10)
    # the orphan re-kicks a probe for the current generation (round-6 finding); it lands
    nxt = qd._budget_cache["thread"]
    assert nxt is not old_thread
    nxt.join(timeout=10)
    data = qd._budget_cache["data"]
    assert data["quota"]["active"] == "OLD-ACCOUNT" and qd._budget_cache["ts"] > 0  # now current


def test_every_degraded_reason_the_script_can_emit_reaches_the_board(tmp_path, monkeypatch):
    """Round-9 Opus finding: the board's caveat filter is a word list, the script's reasons are
    prose — "NOT subtracted" (capitals) never matched "not subtracted". Walk the degraded matrix
    of `dispatch_headroom.budget()` and assert every reason that is not bookkeeping renders."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "dh", Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "dispatch_headroom.py"
    )
    dh = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(dh)
    qd = _load(tmp_path, monkeypatch)
    box_ok = {"ok": True, "mem_available_gb": 40.0, "cores": 24, "load1": 1.0}
    boxes = [box_ok, {"ok": False, "why": "box probe failed: /proc/meminfo"}]
    q_ok = {
        "ok": True,
        "active": "a@x",
        "hottest_pct": 10.0,
        "eligible": 1,
        "eligible_raw": 1,
        "active_in_band": False,
        "hold": False,
        "drain_band": 85.0,
    }
    quotas = [
        q_ok,
        dict(q_ok, hottest_pct=90.0, active_in_band=True),
        dict(q_ok, eligible=0, eligible_raw=2),
        dict(q_ok, eligible=0, eligible_raw=0),
        dict(q_ok, active=None, hottest_pct=None),
        dict(q_ok, hottest_pct=None),
        {"ok": False, "why": "quota probe failed"},
        dict(q_ok, hold=True),
    ]
    sibs = [
        {"ok": True, "seats": 0, "unrecorded": 0},
        {"ok": True, "seats": 21, "unrecorded": 0},
        {"ok": True, "seats": 0, "unrecorded": 2},
        {"ok": True, "seats": 0, "skipped": ["a.json"]},
        {"ok": True, "seats": 0, "own_source": "env"},
        {"ok": False, "seats": 0, "why": "sibling probe failed: EACCES"},
    ]
    bookkeeping = ("box allows ", "wanted ", "risky=", "mix has ")
    missed = set()
    # round 10: the walk also covers units 0 ("nothing to partition" — it had no word), heavy,
    # a clamped risky and the judgement-surface mechanical 0
    shapes = [(6, False, 1, None), (0, False, 0, None), (6, True, 3, 0), (2, False, 3, None)]
    for b in boxes:
        for q in quotas:
            for s in sibs:
                for units, heavy, risky, mech in shapes:
                    r = dh.budget(units, heavy, b, q, s, risky, mech)
                    _check(r, s, qd, bookkeeping, missed)
                    # the same reasons arriving as the HEAVY half must render too (round 13: the
                    # matrix never fed `heavy_reasons`; the prefixed path had one example)
                    _check(r, s, qd, bookkeeping, missed, key="heavy_reasons")
                    _check(r, s, qd, bookkeeping, missed, key="reasons_read_only")
    assert not missed, sorted(missed)


def _check(r, s, qd, bookkeeping, missed, key="reasons"):
    d = {"reasons": [], "reasons_read_only": [], "heavy_reasons": [], "siblings": s}
    d[key] = r["reasons"]  # every half present: the "predates" line must never pollute (round 15)
    lines = qd._budget_caveat_lines(d)
    assert not any("predates heavy_reasons" in x for x in lines)
    # the heavy half renders LABELLED — containment alone passed with the label dropped (round 14)
    label = "heavy half — " if key == "heavy_reasons" else ""
    for reason in r["reasons"]:
        if reason.startswith(bookkeeping):
            continue
        if label + reason not in lines:
            missed.add(key + ": " + reason[:90])


def test_an_orphaned_probe_re_kicks_only_when_no_other_probe_is_alive(tmp_path, monkeypatch):
    """Round-10 Opus finding (F276): every stale landing spawned a fresh fleet probe — K stale
    generations, K probes. With another probe thread ALIVE the orphan lands and spawns nothing;
    with none alive it re-kicks exactly one."""
    import threading

    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "1")
    payload = json.dumps(
        {
            "caps": {"box_cap": 5, "concurrency_cap": 20},
            "box_caps": {"read_only": 5, "heavy": 2},
            "heavy_reasons": [],
            "quota": {"ok": True, "active": "a@x", "hottest_pct": 1.0, "eligible": 1},
        }
    )
    started = []

    class _R:
        def __init__(self, args):
            started.append(list(args))
            self.stdout = payload

    monkeypatch.setattr(qd.subprocess, "run", lambda args, **kw: _R(args))
    hold = threading.Event()
    other = threading.Thread(target=hold.wait, daemon=True)
    other.start()
    qd._budget_cache.update(ts=0.0, data=None, thread=other, gen=7)
    qd._budget_probe(3)  # stale generation lands while `other` is alive: no re-kick
    assert qd._budget_cache["thread"] is other and len(started) == 1
    hold.set()
    other.join(timeout=5)
    qd._budget_cache["thread"] = None
    qd._budget_probe(3)  # stale again, nothing alive: exactly one re-kick for the current gen
    nxt = qd._budget_cache["thread"]
    assert nxt is not None and nxt is not other
    nxt.join(timeout=10)
    assert len(started) == 3 and qd._budget_cache["data"]["seats"]  # the re-kick landed as current


# ── Repos tab (operator ask 2026-10-11) ─────────────────────────────────────────────────────────
# "a tab should come first named repos. in it i want to be able to select different repos start with
# fabrik first." The repos come from FABRIK_OPT_DIR, which conftest pins to an empty dir per test.


def _work_repo(opt: Path, name: str, items: list[dict], *, closed=(), claims=None, git=True):
    repo = opt / name
    (repo / ".fabrik" / "work").mkdir(parents=True)
    if git:
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for it in items:
        item = {"kind": "task", "status": "open", "priority": 2, "owner": "", "next": "", **it}
        (repo / ".fabrik" / "work" / f"{item['id']}.json").write_text(json.dumps(item))
    shared = repo / ".git" / "fabrik-work"
    for item_id in closed:
        (shared / "closed").mkdir(parents=True, exist_ok=True)
        (shared / "closed" / f"{item_id}.json").write_text(json.dumps({"at": time.time()}))
    for item_id, agent in (claims or {}).items():
        (shared / "claims").mkdir(parents=True, exist_ok=True)
        claim = {"agent": agent, "session": "s1", "at": time.time(), "lease_s": 7200, "token": 1}
        (shared / "claims" / f"{item_id}.json").write_text(json.dumps(claim))
    return repo


def _opt() -> Path:
    return Path(os.environ["FABRIK_OPT_DIR"])


def _work(qd) -> str:
    return _view(qd, "work")


def _work_pane(markup: str, repo: str) -> _Node:
    panes = _find(_dom(markup), "div", data_pick=repo)
    assert len(panes) == 1, (repo, len(panes))
    return panes[0]


def _owner_sections(pane: _Node) -> list[tuple[str, _Node]]:
    """(summary words, section) of every owner section in a Work pane, in display order."""
    return [
        (next(c for c in d.children if c.tag == "summary").words(), d)
        for d in _find(pane, "details")
        if "data-f-owner" in d.attrs
    ]


def _owner_section(pane: _Node, owner: str) -> _Node:
    hits = [d for words, d in _owner_sections(pane) if words.split(" (")[0] == owner]
    assert len(hits) == 1, (owner, [w for w, _d in _owner_sections(pane)])
    return hits[0]


def _chip_words(pane: _Node) -> list[str]:
    navs = [n for n in _find(pane, "nav") if n.attrs.get("data-chips") == "owners"]
    return [b.words() for b in _find(navs[0], "button")] if navs else []


def _item_ids(node: _Node) -> list[str]:
    """The item ids of every Work table row under ``node``, in order (the row's header cell)."""
    out = []
    for r in _find(node, "tr"):
        cells = [c for c in r.children if c.tag in ("th", "td")]
        if cells and cells[0].tag == "th" and cells[0].attrs.get("scope") == "row":
            out.append(cells[0].words())
    return out


def test_the_quota_views_never_read_a_work_store(tmp_path, monkeypatch):
    """Isolation (the old Repos page's): a work store that raises costs the Work view — which says so
    in words — never the Accounts view, which reads the quota payload alone."""
    qd = _load(tmp_path, monkeypatch)

    def boom(_opt):
        raise RuntimeError("store exploded")

    monkeypatch.setattr(qd, "_collect_work", boom)
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    accounts = _accounts(qd)
    assert "store exploded" not in accounts and "mob@ocoron.com" in accounts
    work = _work(qd)
    assert "The work stores could not be read: RuntimeError: store exploded" in _text(work)
    assert 'data-state="error"' in work


def _agents_table(markup: str, repo: str) -> _Node:
    regions = [
        d
        for d in _find(_dom(markup), "div", role="region")
        if any(c.tag == "table" for c in d.children)
        and next(c for c in d.children if c.tag == "table").children[0].words()
        == f"Agents in {repo}"
    ]
    assert len(regions) == 1, (repo, len(regions))
    return regions[0]


def _agent_cells(markup: str, repo: str, agent: str) -> list[_Node]:
    rows = _find(_agents_table(markup, repo), "tr", data_agent=agent)
    assert len(rows) == 1, (repo, agent, len(rows))
    return [c for c in rows[0].children if c.tag in ("th", "td")]


def _overview(qd, monkeypatch) -> str:
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)  # the Agents block is not the quota
    return _view(qd, "overview")


def test_agents_block_failure_is_its_sections_error(tmp_path, monkeypatch):
    _work_repo(_opt(), "fabrik", [{"id": "W-0000000a", "title": "still listed"}])
    qd = _load(tmp_path, monkeypatch)

    def boom():
        raise RuntimeError("status exploded")

    monkeypatch.setattr(qd, "_status_module", boom)
    html_ = _overview(qd, monkeypatch)
    agents = html_.split('id="ov-agents"', 1)[1].split('id="ov-quota"', 1)[0]
    assert "The agents could not be read: RuntimeError: status exploded" in _text(agents)
    assert 'data-state="error"' in agents
    assert "still listed" in _work_pane(_work(qd), "fabrik").words()

    class Stub:  # a malformed agent row (a claim that is a bare string): every repo's rows stay
        @staticmethod
        def collect_box(_opt):
            return {"repos": [
                {"name": "bad", "agents": [{"name": "x", "claim": "W-1"}]},
                {"name": "good", "agents": [{"name": "fine", "state": "idle"}]},
            ]}  # fmt: skip

    monkeypatch.setattr(qd, "_status_module", lambda: Stub)
    qd._drop_repos_cache()
    html_ = _overview(qd, monkeypatch)
    assert (
        _agent_cells(html_, "bad", "x") and "idle" in _agent_cells(html_, "good", "fine")[1].words()
    )
    assert "still listed" in _work_pane(_work(qd), "fabrik").words()


def test_the_repo_picker_lists_fabrik_first_then_by_open_count(tmp_path, monkeypatch):
    opt = _opt()
    _work_repo(opt, "aaa", [])
    _work_repo(opt, "big", [{"id": f"W-0000000{i}"} for i in range(3)])
    _work_repo(opt, "mid", [{"id": "W-00000010"}, {"id": "W-00000011"}])
    _work_repo(opt, "fabrik", [{"id": "W-00000020"}])
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    picker = [n for n in _find(_dom(html_), "nav") if n.attrs.get("data-picker") == "repo"]
    assert [b.attrs["data-pick-to"] for b in _find(picker[0], "button")] == [
        "fabrik",
        "big",
        "mid",
        "aaa",
    ]
    # the picked repo is kept in the URL (`#work/<repo>`, app.js's pick group), so a reload keeps it
    assert _find(_dom(html_), "div", data_pick_group="repo")


def test_a_repo_shows_only_remaining_work_grouped_by_owner(tmp_path, monkeypatch):
    _work_repo(
        _opt(),
        "fabrik",
        [
            {"id": "W-0000000a", "owner": "zed", "title": "zed item"},
            {"id": "W-0000000b", "owner": "", "title": "nobody's"},
            {"id": "W-0000000c", "owner": "fleet", "status": "blocked", "title": "fleet item"},
            {"id": "W-0000000d", "owner": "infra", "title": "infra item", "next": "x" * 400},
            {
                "id": "W-0000000e",
                "owner": "operator",
                "status": "awaiting-operator",
                "kind": "decision",
            },
            {"id": "W-0000000f", "owner": "infra", "status": "done", "title": "finished"},
            {"id": "W-00000001", "owner": "infra", "status": "dropped", "title": "dropped one"},
            {"id": "W-00000002", "owner": "infra", "title": "closed elsewhere"},
        ],
        closed=["W-00000002"],
        claims={"W-0000000d": "infra"},
    )
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    for gone in ("W-0000000f", "W-00000001", "W-00000002"):
        assert gone not in html_, gone
    pane = _work_pane(html_, "fabrik")
    heads = [w.split(" (")[0] for w, _d in _owner_sections(pane)]
    assert heads == [
        "coordinator",
        "infra",
        "fleet",
        "intel",
        "kaizen",
        "operator",
        "zed",
        "(unassigned)",
    ]
    infra = _owner_section(pane, "infra")
    assert _item_ids(infra) == ["W-0000000d"]
    assert "infra item" in infra.words() and "claimed by infra" in infra.words()
    capped = [d for d in _find(infra, "details") if "data-f-owner" not in d.attrs]
    summary = next(c for c in capped[0].children if c.tag == "summary").words()
    assert summary == "x" * 159 + "…", len(summary)  # the Next cell is capped at 160 characters
    assert "blocked" in _owner_section(pane, "fleet").words()


def test_one_unreadable_repo_does_not_hide_the_others(tmp_path, monkeypatch):
    _work_repo(_opt(), "fabrik", [{"id": "W-00000004", "title": "still listed"}])
    _work_repo(_opt(), "nogit", [{"id": "W-00000005"}], git=False)
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    assert "still listed" in _work_pane(html_, "fabrik").words()
    nogit = _work_pane(html_, "nogit")
    assert (
        _find(nogit, "div", data_state="error")
        and "the work store could not be read" in nogit.words()
    )


def test_item_text_is_escaped(tmp_path, monkeypatch):
    _work_repo(_opt(), "fabrik", [{"id": "W-00000003", "title": "<script>x</script>"}])
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    assert "<script>x</script>" not in html_ and "&lt;script&gt;x&lt;/script&gt;" in html_


def test_rows_run_awaiting_operator_first_then_priority_then_id(tmp_path, monkeypatch):
    _work_repo(
        _opt(),
        "fabrik",
        [
            {"id": "W-000000c1", "owner": "infra", "priority": 1},
            {"id": "W-000000a3", "owner": "infra", "priority": 3},
            {"id": "W-000000b2", "owner": "infra", "priority": 1},
            {"id": "W-000000d9", "owner": "infra", "priority": 3, "status": "awaiting-operator"},
        ],
    )
    qd = _load(tmp_path, monkeypatch)
    assert _item_ids(_work_pane(_work(qd), "fabrik")) == [
        "W-000000d9",
        "W-000000b2",
        "W-000000c1",
        "W-000000a3",
    ]


def test_a_malformed_item_or_a_file_store_stays_inside_its_repo(tmp_path, monkeypatch):
    """A hand-broken item (a dict priority, an int tags) still renders; a store that is a FILE is
    that repo's error, in words; a symlinked alias of a repo is not listed twice."""
    opt = _opt()
    _work_repo(opt, "fabrik", [{"id": "W-00000006", "title": "still listed"}])
    bad = _work_repo(opt, "bad", [{"id": "W-00000007", "title": "odd fields"}])
    item = bad / ".fabrik" / "work" / "W-00000007.json"
    item.write_text(json.dumps({**json.loads(item.read_text()), "priority": {"x": 1}, "tags": 5}))
    (opt / "flat" / ".fabrik").mkdir(parents=True)
    (opt / "flat" / ".fabrik" / "work").write_text("not a dir")
    (opt / "alias").symlink_to(opt / "fabrik")
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    assert "still listed" in _work_pane(html_, "fabrik").words()
    assert "odd fields" in _work_pane(html_, "bad").words()
    flat = _work_pane(html_, "flat")
    assert _find(flat, "div", data_state="error") and "not a directory" in flat.words()
    picker = [n for n in _find(_dom(html_), "nav") if n.attrs.get("data-picker") == "repo"][0]
    names = [b.attrs["data-pick-to"] for b in _find(picker, "button")]
    assert sorted(names) == ["bad", "fabrik", "flat"]  # the symlinked alias is not listed twice


def test_the_owner_chips_name_the_hub_agents_and_unassigned_even_at_zero(tmp_path, monkeypatch):
    """Operator ask 2026-10-11: see infra, kaizen, intel, fleet and unassigned in the fabrik pane."""
    items = [{"id": "W-0000000a", "owner": "infra"}, {"id": "W-0000000b", "owner": "infra"}]
    _work_repo(_opt(), "fabrik", items + [{"id": "W-0000000c", "owner": "zed"}])
    qd = _load(tmp_path, monkeypatch)
    assert _chip_words(_work_pane(_work(qd), "fabrik")) == [
        "All 3", "coordinator 0", "infra 2", "fleet 0", "intel 0", "kaizen 0", "zed 1", "(unassigned) 0",
    ]  # fmt: skip


def test_every_owner_section_is_a_closed_details_and_empty_ones_say_so(tmp_path, monkeypatch):
    _work_repo(_opt(), "fabrik", [{"id": "W-0000000a", "owner": "infra"}, {"id": "W-0000000b"}])
    qd = _load(tmp_path, monkeypatch)
    pane = _work_pane(_work(qd), "fabrik")
    owners = [w.split(" (")[0] for w, _d in _owner_sections(pane)]
    assert owners == ["coordinator", "infra", "fleet", "intel", "kaizen", "(unassigned)"], owners
    # the work-data cache is shared by every viewer: no section is opened on the server
    assert all("open" not in d.attrs for _w, d in _owner_sections(pane))
    kaizen = _owner_section(pane, "kaizen")
    assert "No open items." in kaizen.words() and not _find(kaizen, "table")
    assert _item_ids(_owner_section(pane, "(unassigned)")) == ["W-0000000b"]


def test_a_literal_unassigned_owner_and_odd_names_stay_distinct_and_escaped(tmp_path, monkeypatch):
    _work_repo(
        _opt(),
        "fabrik",
        [{"id": "W-0000000a", "owner": "unassigned"}, {"id": "W-0000000b", "owner": 'a"b<c'}],
    )
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    labels = [w.rsplit(" ", 1)[0] for w in _chip_words(_work_pane(html_, "fabrik"))]
    assert "unassigned" in labels and "(unassigned)" in labels and 'a"b<c' in labels
    assert 'a"b<c' not in html_ and "a&quot;b&lt;c" in html_


def test_only_a_repo_with_remaining_work_carries_owner_chips(tmp_path, monkeypatch):
    _work_repo(_opt(), "fabrik", [{"id": "W-0000000a", "owner": "infra"}])
    _work_repo(_opt(), "quiet", [{"id": "W-0000000b", "status": "done"}])
    qd = _load(tmp_path, monkeypatch)
    html_ = _work(qd)
    assert _chip_words(_work_pane(html_, "fabrik"))
    quiet = _work_pane(html_, "quiet")
    assert _chip_words(quiet) == [] and "No remaining work in this repo." in quiet.words()


# ── per-account weekly caps from the board (operator ask 2026-10-14) ───────────────────────────


def _caps_env(tmp_path, monkeypatch, seed: dict | None):
    caps = tmp_path / "caps.json"
    if seed is not None:
        caps.write_text(json.dumps(seed))
    monkeypatch.setenv("QUOTA_DASH_CAPS_FILE", str(caps))
    qd, stub = _switch_env(tmp_path, monkeypatch)
    return qd, stub, caps


def test_cap_without_the_custom_header_is_refused(tmp_path, monkeypatch):
    """`/cap` writes caps.json — the same CSRF guard as `/switch` and `/park`."""
    qd, stub, caps = _caps_env(tmp_path, monkeypatch, {"mob@ocoron.com": 99})
    httpd, base = _serve(qd)
    try:
        status, body = _post(f"{base}/cap", b'{"account": "sarp@ocoron.com", "cap": 80}')
        assert status == 403, body
        assert json.loads(caps.read_text()) == {"mob@ocoron.com": 99}
    finally:
        httpd.shutdown()


def test_cap_rejects_an_unknown_account_or_a_bad_value(tmp_path, monkeypatch):
    qd, stub, caps = _caps_env(tmp_path, monkeypatch, {"mob@ocoron.com": 99})
    httpd, base = _serve(qd)
    try:
        for bad in (
            b'{"account": "nobody@x.com", "cap": 80}',
            b'{"account": "sarp@ocoron.com", "cap": "80"}',
            b'{"account": "sarp@ocoron.com", "cap": 150}',
            b'{"account": "sarp@ocoron.com", "cap": -1}',
            b'{"account": "sarp@ocoron.com", "cap": true}',
            b'{"account": "sarp@ocoron.com"}',
        ):
            status, body = _post(f"{base}/cap", bad, {qd.SWITCH_HEADER: "1"})
            assert status == 400, (bad, body)
        assert json.loads(caps.read_text()) == {"mob@ocoron.com": 99}
    finally:
        httpd.shutdown()


def test_cap_set_and_clear_write_caps_json_and_regenerate(tmp_path, monkeypatch):
    """One click sets (or clears, with null) ONE account's weekly cap, keeps every other entry,
    lowercases the key the rotation loader compares on, and re-renders the board."""
    qd, stub, caps = _caps_env(tmp_path, monkeypatch, {"mob@ocoron.com": 99})
    httpd, base = _serve(qd)
    try:
        before = _calls(stub)
        status, body = _post(
            f"{base}/cap", b'{"account": "SARP@ocoron.com", "cap": 80}', {qd.SWITCH_HEADER: "1"}
        )
        assert status == 200 and body["ok"] is True, body
        assert json.loads(caps.read_text()) == {"mob@ocoron.com": 99, "sarp@ocoron.com": 80}
        assert ["--status", "--json"] in _calls(stub)[len(before) :]  # re-rendered after the write
        status, body = _post(
            f"{base}/cap", b'{"account": "sarp@ocoron.com", "cap": null}', {qd.SWITCH_HEADER: "1"}
        )
        assert status == 200 and body["ok"] is True, body
        assert json.loads(caps.read_text()) == {"mob@ocoron.com": 99}
        assert caps.with_name("caps.json.tmp").exists() is False
    finally:
        httpd.shutdown()


def test_cap_never_overwrites_an_unreadable_caps_file(tmp_path, monkeypatch):
    """A caps.json that does not parse is refused, not replaced — rewriting it from {} would
    silently drop every other account's reserve."""
    qd, stub, caps = _caps_env(tmp_path, monkeypatch, None)
    caps.write_text("{not json")
    httpd, base = _serve(qd)
    try:
        status, body = _post(
            f"{base}/cap", b'{"account": "sarp@ocoron.com", "cap": 80}', {qd.SWITCH_HEADER: "1"}
        )
        assert status == 502, body
        assert caps.read_text() == "{not json"
    finally:
        httpd.shutdown()


def test_cap_on_a_missing_caps_file_creates_it(tmp_path, monkeypatch):
    qd, stub, caps = _caps_env(tmp_path, monkeypatch, None)
    assert not caps.exists()
    httpd, base = _serve(qd)
    try:
        status, body = _post(
            f"{base}/cap", b'{"account": "sarp@ocoron.com", "cap": 0}', {qd.SWITCH_HEADER: "1"}
        )
        assert status == 200, body
        assert json.loads(caps.read_text()) == {"sarp@ocoron.com": 0}
    finally:
        httpd.shutdown()


def _edit_panel(markup: str, slug: str) -> _Node:
    """The account row's Edit disclosure (its four controls live there)."""
    row = _acct_row(markup, slug)
    panels = _find(row, "details")
    assert len(panels) == 1, (slug, len(panels))
    return panels[0]


def _work_row(markup: str, item: str) -> _Node:
    rows = [r for r in _find(_dom(markup), "tr") if _item_ids(r) == [item]]
    assert len(rows) == 1, (item, len(rows))
    return rows[0]


def test_every_row_offers_a_cap_control_showing_the_current_cap(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _multi_payload)
    qd.generate()
    html_ = _accounts(qd)
    for acct in _multi_payload()["accounts"]:
        email, slug, cap = acct["email"], acct["slugs"][0], acct.get("weekly_cap")
        panel = _edit_panel(html_, slug)
        field = _find(panel, "input", name="cap")
        assert len(field) == 1, email
        assert field[0].attrs.get("value") == ("" if cap is None else f"{cap:g}"), (
            email,
            field[0].attrs,
        )
        assert _buttons(panel, "/cap") == [{"account": email}], email


# ── per-account rotate thresholds from the board (operator 2026-10-14) ─────────────────────────


def _thr_env(tmp_path, monkeypatch, seed: dict | None):
    f = tmp_path / "thresholds.json"
    if seed is not None:
        f.write_text(json.dumps(seed))
    monkeypatch.setenv("QUOTA_DASH_THRESHOLDS_FILE", str(f))
    monkeypatch.setenv("QUOTA_DASH_CAPS_FILE", str(tmp_path / "caps.json"))
    qd, stub = _switch_env(tmp_path, monkeypatch)
    return qd, stub, f


def test_threshold_set_clear_and_refusals(tmp_path, monkeypatch):
    qd, stub, f = _thr_env(tmp_path, monkeypatch, {"mob@ocoron.com": 98})
    httpd, base = _serve(qd)
    try:
        status, body = _post(
            f"{base}/threshold", b'{"account": "sarp@ocoron.com", "threshold": 97}'
        )
        assert status == 403, body
        for bad in (
            b'{"account": "nobody@x.com", "threshold": 97}',
            b'{"account": "sarp@ocoron.com", "threshold": 49}',
            b'{"account": "sarp@ocoron.com", "threshold": 101}',
            b'{"account": "sarp@ocoron.com", "threshold": "97"}',
            b'{"account": "sarp@ocoron.com", "threshold": false}',
            b'{"account": "sarp@ocoron.com"}',
        ):
            status, body = _post(f"{base}/threshold", bad, {qd.SWITCH_HEADER: "1"})
            assert status == 400, (bad, body)
        assert json.loads(f.read_text()) == {"mob@ocoron.com": 98}
        status, body = _post(
            f"{base}/threshold",
            b'{"account": "SARP@ocoron.com", "threshold": 97}',
            {qd.SWITCH_HEADER: "1"},
        )
        assert status == 200 and body["ok"], body
        assert json.loads(f.read_text()) == {"mob@ocoron.com": 98, "sarp@ocoron.com": 97}
        status, body = _post(
            f"{base}/threshold",
            b'{"account": "mob@ocoron.com", "threshold": null}',
            {qd.SWITCH_HEADER: "1"},
        )
        assert status == 200 and body["ok"], body
        assert json.loads(f.read_text()) == {"sarp@ocoron.com": 97}
    finally:
        httpd.shutdown()


def test_every_row_offers_a_threshold_control_and_the_trigger_reads_the_override(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)

    def payload():
        p = _multi_payload()
        p["accounts"][0]["session_threshold"] = 97.0
        return p

    monkeypatch.setattr(qd, "_probe", payload)
    qd.generate()
    html_ = _accounts(qd)
    for acct in payload()["accounts"]:
        panel = _edit_panel(html_, acct["slugs"][0])
        assert _find(panel, "input", name="threshold"), acct["email"]
        assert _buttons(panel, "/threshold") == [{"account": acct["email"]}], acct["email"]
    first = payload()["accounts"][0]
    field = _find(_edit_panel(html_, first["slugs"][0]), "input", name="threshold")[0]
    assert field.attrs.get("value") == "97", field.attrs
    assert qd._trip_line(payload()["accounts"][0]) == 97.0
    assert qd._trip_line(payload()["accounts"][1]) == qd.TRIGGER_THRESHOLD


def test_the_account_map_writer_drops_case_variants_and_holds_the_lock(tmp_path, monkeypatch):
    """D-855 review: a hand-written `OB@…` survived a board clear of `ob@…` (the loaders lowercase and
    the last duplicate wins), and no grader died when the flock was removed. The writer must drop every
    case-variant, and a write must WAIT while another holder has `<file>.lock`."""
    import fcntl
    import threading

    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_rerender", lambda: None)
    f = tmp_path / "thresholds.json"
    f.write_text(json.dumps({"OB@ocoron.com": 60, "x@y.co": 97}))
    status, _body = qd._edit_account_map(f, "ob@ocoron.com", None, "thresholds")
    assert status == 200 and json.loads(f.read_text()) == {"x@y.co": 97}
    status, _body = qd._edit_account_map(f, "x@y.co", 95, "thresholds")
    assert json.loads(f.read_text()) == {"x@y.co": 95}

    done = threading.Event()
    th = threading.Thread(
        target=lambda: (qd._edit_account_map(f, "z@y.co", 90, "thresholds"), done.set())
    )
    with open(tmp_path / "thresholds.json.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        th.start()
        try:
            assert not done.wait(0.5), "the writer did not wait for the lock holder"
            assert "z@y.co" not in json.loads(f.read_text())
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    th.join(5)
    assert done.is_set() and json.loads(f.read_text()) == {"x@y.co": 95, "z@y.co": 90}


# ── the Agents block and the live Repos page (operator 2026-10-15, W-7159f8e2) ─────────────────────


def _run_record(sid: str, **fields) -> None:
    d = Path(os.environ["COMMAND_RUN_DIR"])
    d.mkdir(parents=True, exist_ok=True)
    rec = {"session_id": sid, "updated_ts": time.time(), "phase": 3, "phases": 5, **fields}
    (d / f"{sid}.json").write_text(json.dumps(rec))


def test_agents_block_shows_every_repo_with_titles(tmp_path, monkeypatch):
    """Every repo with a recent agent gets its rows — state, NOW, HOLDS, NEXT — and every item id
    shown carries its title (operator: "i cant understand what is W-41c1ec56")."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    fab = _work_repo(_opt(), "fabrik", [
        {"id": "W-0000000a", "owner": "infra", "title": "build the agents table"},
        {"id": "W-0000000b", "owner": "infra", "title": 'next <script>alert("x")</script> one'},
    ], claims={"W-0000000a": "infra"})  # fmt: skip
    shop = _work_repo(_opt(), "shop", [])
    _run_record("s1", agent="infra", state="running", command="fabrik-task", surface="the table",
                repo_root=str(fab.resolve()))  # fmt: skip
    _run_record(
        "s2", agent="wef2", state="done", command="fabrik-review", repo_root=str(shop.resolve())
    )
    qd = _load(tmp_path, monkeypatch)
    html_ = _overview(qd, monkeypatch)
    who, state, now, holds, nxt, _merge = _agent_cells(html_, "fabrik", "infra")
    assert (
        "working" in state.words() and "/fabrik-task" in now.words() and "the table" in now.words()
    )
    assert holds.words() == "W-0000000a build the agents table"
    # NEXT: the queued (unclaimed) item with its title, escaped — never live markup
    assert 'W-0000000b next <script>alert("x")</script> one' in nxt.words()
    assert "<script>alert" not in html_
    assert "no window open" in _agent_cells(html_, "shop", "wef2")[1].words()
    tables = [c.words() for c in _find(_dom(html_), "caption") if c.words().startswith("Agents in")]
    assert tables.index("Agents in fabrik") < tables.index("Agents in shop")


def test_unowned_awaiting_operator_counts_under_operator(tmp_path, monkeypatch):
    """A decision waiting on the operator carries no owner: it is grouped under operator, while an
    unowned open item stays (unassigned) and an OWNED awaiting item stays with its owner."""
    _work_repo(_opt(), "fabrik", [
        {"id": "W-0000000e", "status": "awaiting-operator", "kind": "decision", "title": "gate one"},
        {"id": "W-0000000f", "status": "awaiting-operator", "owner": "fleet", "title": "fleet's gate"},
        {"id": "W-0000000b", "title": "nobody's"},
    ])  # fmt: skip
    qd = _load(tmp_path, monkeypatch)
    pane = _work_pane(_work(qd), "fabrik")
    assert _item_ids(_owner_section(pane, "operator")) == ["W-0000000e"]
    assert _item_ids(_owner_section(pane, "(unassigned)")) == ["W-0000000b"]
    assert _item_ids(_owner_section(pane, "fleet")) == ["W-0000000f"]
    chips = dict(w.rsplit(" ", 1) for w in _chip_words(pane))
    assert chips["operator"] == "1" and chips["(unassigned)"] == "1"


# ── Pause / Resume per agent (operator 2026-10-15, W-7159f8e2 part 3) ──────────────────────────────

_HUB_WORK = Path(__file__).resolve().parents[1] / "scripts" / "work.py"


def _store_repo(name: str) -> Path:
    """A real git repo with a real work store (config.json) under the /opt seam."""
    repo = _opt() / name
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(repo.parent),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }
    subprocess.run(["git", "init", "-q", "-b", "master", str(repo)], check=True, env=env)
    (repo / "README").write_text("seed\n")
    subprocess.run(["git", "-C", str(repo), "add", "README"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], check=True, env=env)
    r = subprocess.run(
        [sys.executable, str(_HUB_WORK), "init", "--distributor", "coord"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return repo.resolve()


def _paused_marker(repo: Path, name: str) -> Path:
    return repo / ".git" / "fabrik-work" / "paused" / f"{name}.json"


def test_agent_pause_endpoint_is_guarded(tmp_path, monkeypatch):
    """POST /agent-pause refuses without the custom header, for a pair the board never rendered, for
    an unknown action and for a row with no pause button — and runs nothing."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    _run_record("s1", agent="wef1", state="done", command="fabrik-task", repo_root=str(shop))
    qd = _load(tmp_path, monkeypatch)
    _overview(qd, monkeypatch)
    httpd, base = _serve(qd)
    try:
        body = json.dumps({"repo": "shop", "agent": "wef1", "action": "pause"}).encode()
        assert _post(base + "/agent-pause", body)[0] == 403  # no X-Quota-Dash header
        hdr = {qd.SWITCH_HEADER: "1"}
        unknown = json.dumps({"repo": "shop", "agent": "ghost", "action": "pause"}).encode()
        assert _post(base + "/agent-pause", unknown, hdr)[0] == 400
        escape = json.dumps({"repo": "../etc", "agent": "wef1", "action": "pause"}).encode()
        assert _post(base + "/agent-pause", escape, hdr)[0] == 400
        bad = json.dumps({"repo": "shop", "agent": "wef1", "action": "delete"}).encode()
        assert _post(base + "/agent-pause", bad, hdr)[0] == 400
    finally:
        httpd.shutdown()
    assert not _paused_marker(shop, "wef1").exists()


def test_agent_pause_acts_as_the_operator(tmp_path, monkeypatch):
    """A board pause runs work.py as the OPERATOR against the recorded repo even when the server carries
    an agent identity, a session id and a GIT_DIR; a `-`-led why is kept; resume lifts the marker the
    row showed, here one keyed by the window's tree."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    decoy = _store_repo("decoy")
    _run_record("s1", agent="wef1", state="done", command="fabrik-task", repo_root=str(shop))
    qd = _load(tmp_path, monkeypatch)
    _overview(qd, monkeypatch)
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sid-of-some-agent")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    status, out = qd.pause_agent("shop", "wef1", "pause", "--repo=/etc hold")
    assert status == 200, out
    rec = json.loads(_paused_marker(shop, "wef1").read_text())
    assert rec["actor"] == "" and rec["by"] == "dashboard" and rec["why"] == "--repo=/etc hold"
    assert not _paused_marker(decoy, "wef1").exists()
    status, out = qd.pause_agent("shop", "wef1", "resume")
    assert status == 200, out
    assert not _paused_marker(shop, "wef1").exists()
    # a pause keyed by another name (the window's tree) is lifted by the name the row carries
    for k in ("CLAUDE_AGENT", "CLAUDE_CODE_SESSION_ID", "GIT_DIR"):
        monkeypatch.delenv(k)
    for tree in ("tree1", "tree2"):  # the agent's two windows, both trees paused: Resume lifts both
        _paused_marker(shop, tree).write_text(
            json.dumps({"by": "operator", "actor": "", "at": time.time()})
        )
    qd._PAUSE_TARGETS = {("shop", "lead"): {"main": str(shop),
                                            "paused": {"name": "tree1", "names": ["tree1", "tree2"]}}}  # fmt: skip
    status, out = qd.pause_agent("shop", "lead", "resume")
    assert status == 200, out
    assert not _paused_marker(shop, "tree1").exists() and not _paused_marker(shop, "tree2").exists()

    class Stub:  # a partial pause says so on its row, and the row offers Resume
        @staticmethod
        def collect_box(_opt):
            lead = {"name": "lead", "state": "idle", "can_pause": True, "pause_honoured": True,
                    "paused": {"by": "operator", "at": None, "partial": True, "names": ["tree1"]}}  # fmt: skip
            return {"repos": [{"name": "shop", "main": str(shop), "agents": [lead]}]}

    monkeypatch.setattr(qd, "_status_module", lambda: Stub)
    qd._drop_repos_cache()
    _who, state, *_rest = _agent_cells(_overview(qd, monkeypatch), "shop", "lead")
    assert "only some of its windows" in state.words()
    assert _buttons(state, "/agent-pause") == [
        {"repo": "shop", "agent": "lead", "action": "resume"}
    ]


def test_agent_pause_refuses_buttonless_rows_and_odd_input(tmp_path, monkeypatch):
    """The review's round-1 findings, each pinned: a row with no button (no config.json) is refused; a
    NUL or a lone surrogate in the reason is dropped, never an uncaught error; a failed board read
    leaves no older read's pairs to act on; a write landing mid-read is never cached."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    bare = _work_repo(_opt(), "bare", [])  # a work dir, no config.json
    _run_record("s1", agent="wef1", state="done", command="fabrik-task", repo_root=str(shop))
    _run_record(
        "s3", agent="bob", state="done", command="fabrik-task", repo_root=str(bare.resolve())
    )
    qd = _load(tmp_path, monkeypatch)
    _overview(qd, monkeypatch)
    assert qd.pause_agent("bare", "bob", "pause")[0] == 400
    status, out = qd.pause_agent("shop", "wef1", "pause", "a\x00b\ud800c")
    assert status == 200, out
    assert json.loads(_paused_marker(shop, "wef1").read_text())["why"] == "abc"

    def broken():
        raise RuntimeError("box unreadable")

    monkeypatch.setattr(qd, "_status_module", broken)
    qd._drop_repos_cache()
    assert "The agents could not be read: RuntimeError: box unreadable" in _text(
        _overview(qd, monkeypatch)
    )
    assert qd._PAUSE_TARGETS == {}
    # a write that lands while the agents are being read: that read is served once, never cached

    class Racing:
        @staticmethod
        def collect_box(_opt):
            qd._drop_repos_cache()
            return {"repos": []}

    monkeypatch.setattr(qd, "_status_module", lambda: Racing)
    qd._drop_repos_cache()
    assert qd._box_data() == {"repos": []}
    assert qd._box_cache is None


# ── Accept / Reject / comment per work item (operator 2026-10-15, W-e1f1a1bd) ──────────────────────


def _store_item(repo: Path, title: str, *tags: str) -> str:
    """A real item in a real store, added by the hub's work.py as the operator (tagged when asked)."""
    env = {"PATH": os.environ["PATH"], "HOME": str(repo.parent), "GIT_CONFIG_NOSYSTEM": "1"}
    r = subprocess.run(
        [sys.executable, str(_HUB_WORK), "add", "--kind", "task", "--title", title],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    item = Path(r.stdout.strip().splitlines()[-1]).stem
    if tags:
        path = repo / ".fabrik" / "work" / f"{item}.json"
        path.write_text(json.dumps({**json.loads(path.read_text()), "tags": list(tags)}))
    return item


def _item(repo: Path, item: str) -> dict:
    return json.loads((repo / ".fabrik" / "work" / f"{item}.json").read_text())


def test_item_verdict_endpoint_is_guarded(tmp_path, monkeypatch):
    """POST /item-verdict refuses without the custom header, for an item the board never listed, for
    an unknown action and for a reject with no words — and runs nothing; a failed read lists no pairs."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    item = _store_item(shop, "a task")
    qd = _load(tmp_path, monkeypatch)
    _work(qd)
    httpd, base = _serve(qd)
    try:
        token = qd._snapshot.token(_item(shop, item))
        body = json.dumps(
            {"repo": "shop", "item": item, "action": "comment", "text": "hi", "token": token}
        ).encode()
        assert _post(base + "/item-verdict", body)[0] == 403  # no X-Quota-Dash header
        hdr = {qd.SWITCH_HEADER: "1"}
        ghost = json.dumps({"repo": "shop", "item": "W-00000000", "action": "accept"}).encode()
        assert _post(base + "/item-verdict", ghost, hdr)[0] == 400
        bad = json.dumps({"repo": "shop", "item": item, "action": "delete"}).encode()
        assert _post(base + "/item-verdict", bad, hdr)[0] == 400
        mute = json.dumps(
            {"repo": "shop", "item": item, "action": "reject", "text": " \x00 "}
        ).encode()
        assert _post(base + "/item-verdict", mute, hdr)[0] == 400
        blank = json.dumps({"repo": "shop", "item": item, "action": "comment", "text": ""}).encode()
        assert _post(base + "/item-verdict", blank, hdr)[0] == 400  # refused here, never a 502
        assert "comments" not in _item(shop, item) and _item(shop, item)["status"] == "open"
        assert _post(base + "/item-verdict", body, hdr)[0] == 200
    finally:
        httpd.shutdown()
    assert _item(shop, item)["comments"][-1]["text"] == "hi"
    qd._ITEM_TARGETS = {}  # a restarted server: the first write rebuilds the targets once, then acts
    token = qd._snapshot.token(_item(shop, item))
    assert qd.item_verdict("shop", item, "comment", "again", token=token)[0] == 200
    assert _item(shop, item)["comments"][-1]["text"] == "again"

    def broken(_opt):
        raise RuntimeError("stores unreadable")

    monkeypatch.setattr(qd, "_collect_work", broken)
    qd._drop_repos_cache()
    assert "The work stores could not be read: RuntimeError: stores unreadable" in _text(_work(qd))
    assert qd._ITEM_TARGETS == {}


def test_item_verdict_acts_as_the_operator(tmp_path, monkeypatch):
    """A board verdict runs the hub's work.py as the OPERATOR against the recorded main checkout even
    when the server carries an agent identity, a session id and a GIT_DIR; a `-`-led reason is kept
    (the options sit before `--`); accept lifts the review hold; reject drops an owned item."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    decoy = _store_repo("decoy")
    held = _store_item(shop, "held", "waits-operator-review")
    owned = _store_item(shop, "owned")
    path = shop / ".fabrik" / "work" / f"{owned}.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "owner": "wef1"}))
    qd = _load(tmp_path, monkeypatch)
    _work(qd)
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sid-of-some-agent")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    status, out = qd.item_verdict("shop", owned, "reject", "--repo=/etc not needed",
                                  token=qd._snapshot.token(_item(shop, owned)))  # fmt: skip
    assert status == 200, out
    gone = _item(shop, owned)
    assert (
        gone["status"] == "dropped"
        and gone["note"] == "rejected by the operator: --repo=/etc not needed"
    )
    assert gone["comments"][-1] == {
        **gone["comments"][-1],
        "by": "operator",
        "via": "dashboard",
        "action": "reject",
    }
    status, out = qd.item_verdict(
        "shop", held, "accept", token=qd._snapshot.token(_item(shop, held))
    )
    assert status == 200, out
    assert _item(shop, held)["tags"] == ["operator-accepted"]
    assert not list((decoy / ".fabrik" / "work").glob("W-*.json"))


_TAGS_DOM = r"""
const spec = JSON.parse(process.argv[process.argv.length - 1]);
const gets = [], store = {}; if (spec.stored !== null) { store["repo-tag"] = spec.stored; }
global.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
const rows = spec.rows.map((t) => ({ hidden: false, getAttribute: () => t }));
const box_ = (v) => ({ value: v, getAttribute: (k) => ({"data-repo": "shop", "data-item": "W-0000000a"})[k] });
let inputs = spec.typed.map(box_);
const opts = spec.known.map((v) => ({ value: v }));
let onInput = null;
const box = { value: "", addEventListener: (t, f) => { if (t === "input") { onInput = f; } } };
// #live: a swap (innerHTML set) rebuilds every comment box empty, as the browser does
const cur = { querySelector: () => ({ textContent: "read 10:00:00" }) };
Object.defineProperty(cur, "innerHTML", { set: () => { inputs = inputs.map(() => box_("")); }, get: () => "" });
const nw = { innerHTML: "NEW", querySelector: () => ({ textContent: "read 10:00:20" }) };
const inBox = { tagName: "INPUT", id: "", closest: (sel) => (sel === "#live" ? cur : null) };
global.document = { hidden: false, activeElement: spec.focused ? inBox : null,
  getElementById: (id) => (id === "tag-pick" ? box : id === "live" ? cur : null),
  querySelectorAll: (sel) => (sel === "tr[data-tags]" ? rows : sel === "#tag-list option" ? opts
    : sel === "input.iv-text" ? inputs : []),
  addEventListener: () => {} };
global.window = { scrollY: 0, scrollTo: () => {}, getSelection: () => "", frameElement: null };
global.DOMParser = function () { this.parseFromString = () => ({ getElementById: () => nw }); };
global.fetch = (url) => { gets.push(url); return Promise.resolve({ ok: true, text: () => Promise.resolve("x") }); };
global.setInterval = () => {};
eval(spec.script);
const first = rows.map((r) => r.hidden);
box.value = spec.typeTag; if (onInput) { onInput(); }
const after = rows.map((r) => r.hidden);
refreshRepos(spec.force);
setTimeout(() => console.log(JSON.stringify({first, after, gets, stored: store["repo-tag"],
  values: inputs.map((x) => x.value)})), 30);
"""


def test_item_rows_verdict_buttons_and_tag_filter(tmp_path, monkeypatch):
    """Rows carry Accept, Reject, a comment box and their tags; the last comment shows; an awaiting
    item that is no decision gets the box only; each Accept / Reject names its confirm dialog and
    posts the card's snapshot token; the tag box filters rows by their tags. (How the filter, the
    confirm and a half-typed comment behave in a browser is `app.js`'s — graded in
    tests/test_quota_dashboard_app_js.py and over these real views in tests/test_quota_dashboard_browser.py.)"""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    plain = _store_item(shop, "plain", "waits-operator-review")
    odd = _store_item(shop, "odd")
    path = shop / ".fabrik" / "work" / f"{odd}.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "status": "awaiting-operator"}))
    qd = _load(tmp_path, monkeypatch)
    _work(qd)
    token = qd._snapshot.token(_item(shop, plain))
    assert qd.item_verdict("shop", plain, "comment", "<b>look</b>", token=token)[0] == 200
    html_ = _work(qd)
    row = _work_row(html_, plain)
    assert row.attrs.get("data-f-tag") == "waits-operator-review"
    now_token = qd._snapshot.token(_item(shop, plain))
    for action, note in (("accept", "optional"), ("reject", "required")):
        btn = [b for b in _find(row, "button", data_post="/item-verdict")
               if json.loads(b.attrs["data-body"]).get("action") == action]  # fmt: skip
        assert len(btn) == 1, action
        body = json.loads(btn[0].attrs["data-body"])
        assert body == {"repo": "shop", "item": plain, "token": now_token, "action": action}
        assert btn[0].attrs.get("data-note") == note
        assert _find(_dom(html_), "dialog", id=btn[0].attrs["data-confirm"]), action
    assert _find(row, "input"), "the comment box"
    assert "operator comment: <b>look</b>" in row.words() and "<b>look</b>" not in html_
    odd_row = _work_row(html_, odd)
    actions = [
        json.loads(b.attrs["data-body"]).get("action")
        for b in _find(odd_row, "button", data_post="/item-verdict")
    ]
    assert actions == ["comment"] and _find(odd_row, "input")
    tag_box = _find(_dom(html_), "input", id="work-tag")
    assert (
        tag_box
        and tag_box[0].attrs.get("data-filter") == "tag"
        and tag_box[0].attrs.get("data-filter-mode") == "token"
    )


def test_agent_rows_pause_and_resume_buttons(tmp_path, monkeypatch):
    """Rows show Pause, or Resume with who paused; no button for a store-less repo; Pause asks for an
    optional reason in its confirm dialog and Resume names the markers it lifts (the confirm, the
    post and the forced refresh are `app.js`'s, graded in tests/test_quota_dashboard_app_js.py)."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    bare = _work_repo(_opt(), "bare", [])  # a work dir, no config.json
    _run_record("s1", agent="wef1", state="done", command="fabrik-task", repo_root=str(shop))
    _run_record("s2", agent="wef2", state="done", command="fabrik-task", repo_root=str(shop))
    _run_record(
        "s3", agent="bob", state="done", command="fabrik-task", repo_root=str(bare.resolve())
    )
    _paused_marker(shop, "wef2").parent.mkdir(parents=True, exist_ok=True)
    _paused_marker(shop, "wef2").write_text(
        json.dumps({"by": "operator", "actor": "", "at": time.time()})
    )
    qd = _load(tmp_path, monkeypatch)
    html_ = _overview(qd, monkeypatch)
    wef1 = _agent_cells(html_, "shop", "wef1")[1]
    wef2 = _agent_cells(html_, "shop", "wef2")[1]
    bob = _agent_cells(html_, "bare", "bob")[1]
    pause = _find(wef1, "button", data_post="/agent-pause")
    assert [b.words() for b in pause] == ["Pause"] and pause[0].attrs.get("data-note") == "optional"
    assert json.loads(pause[0].attrs["data-body"]) == {
        "repo": "shop",
        "agent": "wef1",
        "action": "pause",
    }
    dlg = _find(_dom(html_), "dialog", id=pause[0].attrs["data-confirm"])
    assert dlg and "stops starting new work at its next turn boundary" in dlg[0].words()
    resume = _find(wef2, "button", data_post="/agent-pause")
    assert [b.words() for b in resume] == ["Resume"] and "paused by operator" in wef2.words()
    assert "not honoured here" in wef2.words()  # the fixture repo has no synced work.py of its own
    assert _find(bob, "button") == []  # no config.json: the button could only fail


# ── INV-1 after the redesign: the rebuild-on-miss goes through the new builders (T07) ──────────────


# ── the routes after the redesign (T07): the shell, the old Repos bookmark, quota.json, --once ─────


def _get(base: str, path: str, *, host: str | None = None, headers: dict | None = None):
    """One GET with no redirect following: (status, headers, body)."""
    import http.client
    from urllib.parse import urlsplit

    u = urlsplit(base)
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
    c.request("GET", path, headers={"Host": host or f"{u.hostname}:{u.port}", **(headers or {})})
    r = c.getresponse()
    out = (r.status, dict(r.getheaders()), r.read())
    c.close()
    return out


def test_get_root_is_the_app_shell_with_the_overview_as_the_default_view(tmp_path, monkeypatch):
    """Spec § Contract deltas: `GET /` (and `/index.html`) is the app shell — a skip link first, the
    six-view navigation, one `<main>` that `app.js` fills with the Overview — and it carries no data,
    so it answers at once, before and without any probe."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: (_ for _ in ()).throw(AssertionError("no probe")))
    monkeypatch.setattr(
        qd, "_collect_work", lambda _o: (_ for _ in ()).throw(AssertionError("no store"))
    )
    httpd, base = _serve(qd)
    try:
        for path in ("/", "/index.html"):
            status, hdrs, body = _get(base, path)
            assert status == 200 and hdrs["Content-Type"].startswith("text/html"), (path, status)
            page = _dom(body.decode())
            mains = _find(page, "main")
            assert len(mains) == 1 and mains[0].attrs.get("data-view") == "overview", path
            assert mains[0].attrs.get("id") == "view" and not mains[0].children  # filled by app.js
            links = _find(page, "a")
            assert links[0].attrs.get("href") == "#view", "the skip link is the first link"
            current = [
                a.attrs.get("data-nav") for a in links if a.attrs.get("aria-current") == "page"
            ]
            assert current == ["overview"]
            scripts = [s.attrs.get("src") for s in _find(page, "script") if s.attrs.get("src")]
            assert scripts == ["/static/app.js"]
            assert [n.attrs.get("href") for n in _find(page, "link")] == ["/static/app.css"]
        assert not (qd.OUT_DIR / "index.html").exists() and not qd._JSON.exists()
    finally:
        httpd.shutdown()
    assert qd._LAST_REGEN[0] is None  # the shell starts no regeneration


def test_the_shell_is_behind_the_host_guard_too(tmp_path, monkeypatch):
    """INV-6 covers the new `/`: a page under any other name (a DNS-rebinding site) is answered 421
    before anything renders; a cross-site GET of the shell is harmless — it carries no data and acts
    on nothing — so it is served, as `/health` and the static files are."""
    qd = _load(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        status, _h, body = _get(base, "/", host="evil.example:5051")
        assert status == 421 and b"<main" not in body
        status, _h, _b = _get(base, "/", headers={"Sec-Fetch-Site": "cross-site"})
        assert status == 200
    finally:
        httpd.shutdown()


def test_the_repos_bookmark_redirects_to_work_inside_the_window_then_404s(tmp_path, monkeypatch):
    """Spec § Lifecycle: `/repos.html` sends a bookmark to `/#work` for the 14 days after the redesign,
    then is gone — the same date as the snapshot token's legacy window (spec § Which actions confirm),
    one constant for both."""
    from datetime import date, timedelta

    qd = _load(tmp_path, monkeypatch)
    assert date(2026, 10, 31) == qd._LEGACY_TOKEN_UNTIL  # coded 2026-10-17, + 14 days
    httpd, base = _serve(qd)
    try:
        monkeypatch.setattr(qd, "_LEGACY_TOKEN_UNTIL", date.today())  # the last day: still open
        for path in ("/repos.html", "/repos.html?fresh=1"):
            status, hdrs, body = _get(base, path)
            assert status == 303 and hdrs["Location"] == "/#work" and body == b"", (path, status)
        monkeypatch.setattr(qd, "_LEGACY_TOKEN_UNTIL", date.today() - timedelta(days=1))
        status, _h, _b = _get(base, "/repos.html")
        assert status == 404
        # the token window closed on the same date: a verdict with no token is refused
        assert qd._legacy_window_open() is False
    finally:
        httpd.shutdown()


def test_quota_json_is_served_at_once_and_an_old_one_starts_one_background_probe(
    tmp_path, monkeypatch
):
    """`/quota.json` serves the last payload on disk without waiting on the probe; nothing on disk is
    `{}`; a payload older than MAX_AGE_S starts ONE background regeneration, as the old page did."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    calls: list[int] = []
    gate = threading.Event()

    def slow():
        calls.append(1)
        gate.wait(10)
        return _payload()

    monkeypatch.setattr(qd, "_probe", slow)
    httpd, base = _serve(qd)
    try:
        t0 = time.time()
        status, hdrs, body = _get(base, "/quota.json")
        assert (
            status == 200 and body == b"{}" and time.time() - t0 < 2.0
        )  # never a wait on the probe
        assert hdrs["Content-Type"] == "application/json"
        worker = qd._LAST_REGEN[0]
        assert worker is not None
        _get(base, "/quota.json")  # a second request while the first probe runs starts none
        gate.set()
        worker.join(10)
        assert calls == [1]
        status, _h, body = _get(base, "/quota.json")
        assert json.loads(body)["active"] == "mob"
        assert qd._LAST_REGEN[0] is worker or qd._LAST_REGEN[0] is None  # fresh: no new probe
        assert calls == [1]
    finally:
        httpd.shutdown()


def test_quota_json_is_behind_the_cross_site_guard(tmp_path, monkeypatch):
    """`/quota.json` can start a regeneration — the same reason a view GET is guarded: a page on
    another site marked `Sec-Fetch-Site: cross-site` gets 403 and starts nothing."""
    qd = _load(tmp_path, monkeypatch)
    started: list[int] = []
    monkeypatch.setattr(qd, "_regen_async", lambda: started.append(1))
    httpd, base = _serve(qd)
    try:
        status, _h, body = _get(base, "/quota.json", headers={"Sec-Fetch-Site": "cross-site"})
        assert status == 403 and b"cross-site" in body and started == []
        status, _h, _b = _get(base, "/quota.json", headers={"Sec-Fetch-Site": "same-origin"})
        assert status == 200 and started == [1]
    finally:
        httpd.shutdown()


def test_quota_json_starts_a_regeneration_when_the_pointer_moved_even_if_fresh(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()  # fresh on disk
    started: list[int] = []
    monkeypatch.setattr(qd, "_regen_async", lambda: started.append(1))
    httpd, base = _serve(qd)
    try:
        assert (
            _get(base, "/quota.json")[0] == 200 and started == []
        )  # fresh, pointer still: nothing
        monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
        status, _h, body = _get(base, "/quota.json")
        assert status == 200 and json.loads(body)["active"] == "mob" and started == [1]
    finally:
        httpd.shutdown()


def test_a_regeneration_that_raises_ends_its_thread_cleanly(tmp_path, monkeypatch):
    """The background worker records the failure (as `_generate_held` does) and ends; nothing
    escapes into the thread machinery, and the next regeneration can start."""
    qd = _load(tmp_path, monkeypatch)
    escaped: list[object] = []
    monkeypatch.setattr(threading, "excepthook", lambda args: escaped.append(args.exc_type))

    def boom():
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(qd, "_generate_locked", boom)
    worker = qd._regen_async()
    assert worker is not None
    worker.join(10)
    assert escaped == [] and qd._LAST_PROBE_FAILURE[0][1] == "RuntimeError"
    again = qd._regen_async()
    assert again is not None, "the lock was released"
    again.join(10)


def test_a_pointer_through_a_second_symlink_is_not_read_as_moved(tmp_path, monkeypatch):
    """The board names the pointer the way the rotation CLI does — the final target's name
    (`realpath`), not the first link's: `active -> current -> mob` is `mob`, so a payload whose
    `active` is `mob` has not moved."""
    pointer = tmp_path / "active"
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(pointer))
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()  # quota.json says active "mob"
    (tmp_path / "mob").mkdir()
    (tmp_path / "current").symlink_to(tmp_path / "mob")
    pointer.symlink_to(tmp_path / "current")
    assert qd._pointer_slug() == "mob" and qd._pointer_moved() is False
    (tmp_path / "can").mkdir()
    (tmp_path / "current").unlink()
    (tmp_path / "current").symlink_to(tmp_path / "can")
    assert qd._pointer_slug() == "can" and qd._pointer_moved() is True


def test_quota_json_with_a_mismatch_that_never_clears_probes_once_per_window(tmp_path, monkeypatch):
    """A pointer that disagrees with every reading (a probe that never confirms the flip) must not
    turn every poll into a probe: the pointer-moved branch shares `_status_triggers`' window."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    probes: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (probes.append(1), _payload())[1])
    monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
    for _ in range(5):
        qd._quota_json()
        _join_regen(qd)
    assert probes == [1], probes


def test_once_probes_writes_quota_json_and_prints_its_path(tmp_path, monkeypatch, capsys):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _payload)
    assert qd.main(["--once"]) == 0
    assert capsys.readouterr().out.strip() == str(qd._JSON)
    assert json.loads(qd._JSON.read_text())["active"] == "mob"
    assert not (qd.OUT_DIR / "index.html").exists()
    with pytest.raises(SystemExit):
        qd.main(["--help"])
    assert "write quota.json" in capsys.readouterr().out


def test_after_a_restart_a_verdict_and_a_pause_post_find_targets_the_views_show(
    tmp_path, monkeypatch
):
    """A restarted server has rendered no view and holds no targets; a verdict POST for an item the
    Work view lists and a pause POST for an agent the Overview's Agents table lists are both found —
    the rebuild-on-miss renders the view that shows them, never a probe."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    item = _store_item(shop, "after a restart")
    _run_record("s1", agent="wef1", state="done", command="fabrik-task", repo_root=str(shop))
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: (_ for _ in ()).throw(AssertionError("no probe")))
    assert qd._ITEM_TARGETS == {} and qd._PAUSE_TARGETS == {}
    assert qd._TARGET_SLICES == {"pause": {}, "item": {}}
    httpd, base = _serve(qd)
    hdr = {qd.SWITCH_HEADER: "1"}
    try:
        token = qd._snapshot.token(_item(shop, item))
        body = {
            "repo": "shop",
            "item": item,
            "action": "comment",
            "text": "after restart",
            "token": token,
        }
        status, out = _post(base + "/item-verdict", json.dumps(body).encode(), hdr)
        assert status == 200, out
        assert ("shop", item) in qd._TARGET_SLICES["item"]["work"]
        why = {"repo": "shop", "agent": "wef1", "action": "pause", "why": "hold"}
        status, out = _post(base + "/agent-pause", json.dumps(why).encode(), hdr)
        assert status == 200, out
        assert ("shop", "wef1") in qd._TARGET_SLICES["pause"]["overview"]
    finally:
        httpd.shutdown()
    assert _item(shop, item)["comments"][-1]["text"] == "after restart"
    assert _paused_marker(shop, "wef1").exists()
    # the reason typed in the Pause dialog rides the POST's `why` into the marker
    assert json.loads(_paused_marker(shop, "wef1").read_text())["why"] == "hold"


def test_a_moved_pointer_never_probes_on_the_request_thread(tmp_path, monkeypatch):
    """`_view_data` promises "never a probe": a moved pointer starts ONE background regeneration and
    the view is served at once — the next refresh shows the new account. A slow probe on the HTTP
    thread would hold the view for the whole probe (the 2026-08-18 hang)."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    monkeypatch.setattr(qd, "_probe", _payload)
    qd.generate()
    ran_on: list[str] = []
    gate = threading.Event()

    def slow():
        ran_on.append(threading.current_thread().name)
        gate.wait(10)
        return _payload()

    monkeypatch.setattr(qd, "_probe", slow)
    monkeypatch.setattr(qd, "_pointer_moved", lambda: True)
    httpd, base = _serve(qd)
    try:
        for name in ("accounts", "overview"):
            t0 = time.time()
            status, _h, _b = _get(base, f"/v/{name}")
            assert status == 200 and time.time() - t0 < 2.0, (name, time.time() - t0)
    finally:
        gate.set()
        httpd.shutdown()
    _join_regen(qd)
    assert ran_on and all(n == "quota-regen" for n in ran_on), ran_on


def test_the_health_strip_and_the_stale_banner_agree_on_when_a_reading_is_stale(
    tmp_path, monkeypatch
):
    """One threshold for both: a reading is stale after one probe interval plus one probe timeout
    plus a minute (a healthy slow probe reaches interval + timeout before it lands). At 100 s the
    Health strip used to call it stale (2 x 20 s) while the banner did not (140 s)."""
    qd = _load(tmp_path, monkeypatch)
    from dashboard_ui.views import ViewContext

    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    bound = qd.PROBE_INTERVAL_S + qd.PROBE_TIMEOUT_S + 60
    for age, stale in ((100.0, False), (bound - 5, False), (bound + 5, True)):
        now = time.time()
        qd._set_last_status(now - age, _payload())
        health = qd._view_data("overview", ViewContext(_opt(), qd._FABRIK_ROOT, now))["health"]
        assert bool(health["stale"]) is stale, (age, health)
        assert qd._status_stale(now) is stale, age
        assert ('id="render-failed"' in _accounts(qd)) is stale, age


def test_a_refused_verdict_collects_the_stores_once(tmp_path, monkeypatch):
    """The rebuild-on-miss re-reads the stores ONCE: the Work rebuild fills the cache and the
    Overview fallback reads through it — never a second collection on the POST thread."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    _store_repo("shop")
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    real = qd._collect_work
    calls: list[int] = []
    monkeypatch.setattr(qd, "_collect_work", lambda opt: (calls.append(1), real(opt))[1])
    status, out = qd.item_verdict("shop", "W-0000dead", "comment", "ghost", token="t")
    assert status == 400 and "not on the board" in out["error"]
    assert calls == [1], calls


def test_a_regeneration_whose_thread_cannot_start_releases_its_lock(tmp_path, monkeypatch, capsys):
    """`Thread.start()` can raise (no threads left). The lock was taken first, so a failed start
    used to drop every later regeneration forever; it is released and the failure logged."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _payload)
    real_start = threading.Thread.start
    state = {"fail": True}

    def start(self):
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("can't start new thread")
        return real_start(self)

    monkeypatch.setattr(threading.Thread, "start", start)
    assert qd._regen_async() is None
    assert "regeneration could not start (RuntimeError)" in capsys.readouterr().err
    worker = qd._regen_async()
    assert worker is not None, "the lock was released: the next call regenerates"
    worker.join(10)
    assert qd._JSON.is_file()


def test_a_card_the_overview_shows_is_found_when_its_work_pane_faults(tmp_path, monkeypatch):
    """INV-1: the rebuild-on-miss of a verdict reads the Work view first; when that repo's Work pane
    faults (its own error state, no targets), the Overview still shows the decision card — so the
    rebuild falls through to the Overview before answering "not on the board"."""
    monkeypatch.setenv("FABRIK_WORK_PROC", str(tmp_path / "no-proc"))
    shop = _store_repo("shop")
    item = _store_item(shop, "a decision")
    path = shop / ".fabrik" / "work" / f"{item}.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "status": "awaiting-operator",
                                "kind": "decision", "question": "Ship?"}))  # fmt: skip
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_status_triggers", lambda: None)
    from dashboard_ui.views import work as work_view

    def broken(*_a, **_k):
        raise RuntimeError("pane broke")

    monkeypatch.setattr(work_view, "_pane", broken)
    _view(qd, "work")
    assert ("shop", item) not in qd._ITEM_TARGETS  # the faulted pane publishes no target
    qd._ITEM_TARGETS = {}
    for kind in ("item", "pause"):
        qd._TARGET_SLICES[kind].clear()
    token = qd._snapshot.token(_item(shop, item))
    status, out = qd.item_verdict("shop", item, "comment", "seen on the overview", token=token)
    assert status == 200, out
    assert _item(shop, item)["comments"][-1]["text"] == "seen on the overview"
