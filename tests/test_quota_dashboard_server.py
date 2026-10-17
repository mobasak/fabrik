"""T02 — the command-centre dashboard's server wiring (plan 2026-10-17-plan-1, ticket T02).

The request guard (Host allowlist → 421, a cross-site POST → 403 before the body is read), the
`/v/<view>` and `/static/<name>` routes, the view registry and the data each view receives, the
per-view target slices published as one union, the probe state behind the stale banner, the budget's
data half, the work-data cache and the snapshot token behind the verdict endpoint's 409.

Every test runs the module in-process as `tests/test_quota_dashboard.py` does (a fresh instance per
test, its env-derived constants pointed at tmp_path), with `QUOTA_DASH_BUDGET=0` and a stubbed
probe: nothing here shells out to the fleet probe or writes under ~/.claude.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
import types
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QUOTA_DASH_BUDGET", "0")  # the budget banner shells out to the fleet probe
import pytest  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "scripts" / "sysadmin" / "quota_dashboard.py"
_HUB_WORK = _ROOT / "scripts" / "work.py"
_VIEWS = ("overview", "work", "accounts", "usage", "commands", "services")


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str):
    """A FRESH module instance whose env-derived constants point at tmp_path (the shape of
    `tests/test_quota_dashboard.py::_load`)."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    monkeypatch.setenv("QUOTA_DASH_CREDITS_KEY_FILE", str(tmp_path / "no-key.env"))
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "0")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location(f"qd_srv_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _payload(session: float = 40.0) -> dict:
    return {
        "active": "mob",
        "pause": None,
        "fleet_warnings": [],
        "accounts": [
            {
                "email": "mob@ocoron.com",
                "slugs": ["mob"],
                "five_hour": {"utilization": session, "resets_at_epoch": time.time() + 7200},
                "seven_day": {"utilization": 50.0, "resets_at_epoch": time.time() + 400000},
                "source": "live",
                "age_s": None,
                "weekly_cap": None,
                "cap_walled": False,
            }
        ],
    }


def _serve(qd):
    from http.server import ThreadingHTTPServer

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), qd._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _req(
    port: int,
    method: str,
    path: str,
    *,
    host: str | None = None,
    body: bytes | None = None,
    headers: dict | None = None,
):
    """One request with an EXPLICIT Host header (http.client sends the given one, never its own)."""
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    hdrs = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
    c.request(method, path, body=body, headers=hdrs)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, dict(r.getheaders()), data


def _fake_view(name: str, *, render=None, collect=None) -> types.ModuleType:
    mod = types.ModuleType(f"dashboard_ui.views.{name}")
    from dashboard_ui import components as ui
    from dashboard_ui.views import ViewResult

    def default(data, ctx):
        return ViewResult(html=ui.fragment(ui.group(f"view {name} keys={sorted(data)}")))

    mod.render = render or default
    if collect is not None:
        mod.collect = collect
    return mod


def _install(monkeypatch, name: str, mod: types.ModuleType) -> None:
    monkeypatch.setitem(sys.modules, f"dashboard_ui.views.{name}", mod)


# ── real work stores (the shape of tests/test_quota_dashboard.py's helpers) ─────────────────────────


def _opt() -> Path:
    return Path(os.environ["FABRIK_OPT_DIR"])


def _git_env(home: Path) -> dict:
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }


def _store_repo(name: str) -> Path:
    repo = _opt() / name
    env = _git_env(repo.parent)
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


def _store_item(repo: Path, title: str) -> str:
    env = {"PATH": os.environ["PATH"], "HOME": str(repo.parent), "GIT_CONFIG_NOSYSTEM": "1"}
    r = subprocess.run(
        [sys.executable, str(_HUB_WORK), "add", "--kind", "task", "--title", title],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip().splitlines()[-1]).stem


def _item_file(repo: Path, item: str) -> Path:
    return repo / ".fabrik" / "work" / f"{item}.json"


def _edit(repo: Path, item: str, **fields) -> None:
    p = _item_file(repo, item)
    p.write_text(json.dumps({**json.loads(p.read_text()), **fields}))


def _run_record(sid: str, **fields) -> None:
    d = Path(os.environ["COMMAND_RUN_DIR"])
    d.mkdir(parents=True, exist_ok=True)
    rec = {"session_id": sid, "updated_ts": time.time(), "phase": 3, "phases": 5, **fields}
    (d / f"{sid}.json").write_text(json.dumps(rec))


# ── INV-6: the Host allowlist ───────────────────────────────────────────────────────────────────────


def test_a_foreign_host_is_refused_421_and_runs_nothing(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_HOST="10.0.0.5")
    probes: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (probes.append(1), _payload())[1])
    switched: list[object] = []
    monkeypatch.setattr(
        qd, "switch_account", lambda slug: (switched.append(slug), (200, {"ok": True}))[1]
    )
    httpd, port = _serve(qd)
    try:
        for path in ("/", "/health", "/v/overview", "/static/app.css", "/quota.json"):
            status, hdrs, body = _req(port, "GET", path, host=f"evil.example:{port}")
            assert status == 421, (path, status)
            assert body.strip() and b"\n" not in body.strip()  # a one-line text body
        # the right name on the wrong port, or no port at all, is not this server either
        assert _req(port, "GET", "/health", host=f"127.0.0.1:{port + 1}")[0] == 421
        assert _req(port, "GET", "/health", host="localhost")[0] == 421
        status, _h, _b = _req(
            port,
            "POST",
            "/switch",
            host=f"evil.example:{port}",
            body=b'{"account":"mob"}',
            headers={qd.SWITCH_HEADER: "1"},
        )
        assert status == 421
        for host in (
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            f"[::1]:{port}",
            f"LOCALHOST:{port}",
            f"10.0.0.5:{port}",
        ):
            status, _h, body = _req(port, "GET", "/health", host=host)
            assert (status, body) == (200, b"ok"), host
    finally:
        httpd.shutdown()
    assert probes == [] and switched == []


def test_the_configured_host_is_admitted_only_when_configured(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)  # QUOTA_DASH_HOST unset: 127.0.0.1
    httpd, port = _serve(qd)
    try:
        assert _req(port, "GET", "/health", host=f"10.0.0.5:{port}")[0] == 421
    finally:
        httpd.shutdown()


# ── INV-6: a cross-site POST ────────────────────────────────────────────────────────────────────────


def test_a_cross_site_post_is_refused_403_before_the_body_is_read(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOTA_DASH_SOCKET_TIMEOUT_S", "5")
    qd = _load(tmp_path, monkeypatch)
    httpd, port = _serve(qd)
    try:
        # the client promises 100 bytes and sends 10: a server that read the body would sit on it
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        s.sendall(
            f"POST /switch HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n{qd.SWITCH_HEADER}: 1\r\n"
            "Sec-Fetch-Site: cross-site\r\nContent-Type: application/json\r\n"
            "Content-Length: 100\r\n\r\n".encode()
            + b'{"account"'
        )
        t0 = time.time()
        data = s.recv(4096)
        s.close()
        assert time.time() - t0 < 2.0, "the 403 waited for a body it must never read"
        assert data.startswith(b"HTTP/1.") and b" 403 " in data.split(b"\r\n", 1)[0]
        # every other Sec-Fetch-Site value, and none at all, reaches the existing header guard
        for site in ("same-origin", "same-site", "none", None):
            hdrs = {"Sec-Fetch-Site": site} if site else {}
            status, _h, body = _req(
                port, "POST", "/switch", body=b'{"account":"mob"}', headers=hdrs
            )
            assert status == 403 and qd.SWITCH_HEADER.encode() in body, site
    finally:
        httpd.shutdown()


def test_a_short_body_with_a_valid_host_is_still_dropped_by_the_socket_timeout(
    tmp_path, monkeypatch
):
    """The existing short-body test sends `Host: x`, which the allowlist now answers with 421 before
    any read; this replays it with an admitted Host so the socket-timeout path stays exercised."""
    monkeypatch.setenv("QUOTA_DASH_SOCKET_TIMEOUT_S", "0.5")
    qd = _load(tmp_path, monkeypatch)
    httpd, port = _serve(qd)
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        s.sendall(
            f"POST /switch HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n{qd.SWITCH_HEADER}: 1\r\n"
            "Content-Type: application/json\r\nContent-Length: 100\r\n\r\n".encode()
            + b'{"account"'
        )
        t0 = time.time()
        data = s.recv(4096)
        s.close()
        assert time.time() - t0 < 4.0
        assert data == b"" or data.startswith(b"HTTP/1.")
    finally:
        httpd.shutdown()


# ── /v/<view> and /static/<name> ────────────────────────────────────────────────────────────────────


def test_every_view_route_returns_its_fragment_and_any_other_name_is_404(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())
    monkeypatch.setattr(qd, "_collect_work", lambda opt: [])
    monkeypatch.setattr(
        qd, "_status_module", lambda: types.SimpleNamespace(collect_box=lambda opt: {"repos": []})
    )
    from dashboard_ui import views

    assert views.VIEWS == _VIEWS
    for name in _VIEWS:
        _install(monkeypatch, name, _fake_view(name))
    httpd, port = _serve(qd)
    try:
        for name in _VIEWS:
            status, hdrs, body = _req(port, "GET", f"/v/{name}")
            text = body.decode()
            assert status == 200, name
            assert hdrs["Content-Type"].startswith("text/html")
            assert hdrs["Cache-Control"] == "no-store"
            assert f"view {name} keys=" in text
            assert 'data-stamp="' in text.split(">", 1)[0], "the root element carries the stamp"
            assert not text.lstrip().lower().startswith("<!doctype"), "a fragment, not a page"
        # the stamp is a hash of the markup: the same data gives the same stamp
        a = _req(port, "GET", "/v/usage")[2].decode().split(">", 1)[0]
        b = _req(port, "GET", "/v/usage")[2].decode().split(">", 1)[0]
        assert a == b
        for path in ("/v/nope", "/v/work/fabrik", "/v/", "/v/Overview", "/v/__init__"):
            assert _req(port, "GET", path)[0] == 404, path
    finally:
        httpd.shutdown()


def test_the_view_data_carries_each_views_keys(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())
    monkeypatch.setattr(qd, "_collect_work", lambda opt: [])
    monkeypatch.setattr(
        qd, "_status_module", lambda: types.SimpleNamespace(collect_box=lambda opt: {"repos": []})
    )
    from dashboard_ui.views import ViewContext

    qd.generate()
    ctx = ViewContext(opt_root=_opt(), fabrik_root=_ROOT, now=time.time())
    common = {"now", "refresh_s", "probe_interval_s"}
    want = {
        "overview": {"work", "box", "status", "budget", "health", "ag_states", "hub_agents"},
        "work": {"work", "hub_agents", "owner_order", "repos_ttl_s", "next_cap", "next_tip_cap"},
        "accounts": {
            "status",
            "queue",
            "trigger_threshold",
            "reserve_pct",
            "drain_band",
            "five_hour_s",
            "seven_day_s",
            "switch_header",
            "pool_policy_on",
            "slug_re",
            "email_re",
        },
        "usage": {"spend"},
        "commands": {"commands", "ext_services"},
        "services": {"pool", "apis", "ext_page"},
    }
    for name, keys in want.items():
        data = qd._view_data(name, ctx)
        assert set(data) == common | keys, name
    acc = qd._view_data("accounts", ctx)
    assert acc["status"]["payload"]["accounts"][0]["email"] == "mob@ocoron.com"
    assert acc["slug_re"] == qd._SLUG_RE.pattern and acc["switch_header"] == qd.SWITCH_HEADER
    assert [e["kind"] for e in acc["queue"]][0] == "active"
    # a collector that raises becomes {"error": "<Type>: <message>"} for that key only
    monkeypatch.setattr(qd, "_load_commands", lambda: (_ for _ in ()).throw(OSError("corpus gone")))
    cmd = qd._view_data("commands", ctx)
    assert cmd["commands"] == {"error": "OSError: corpus gone"}
    assert [c["key"] for c in cmd["ext_services"]] == [k for k, *_ in qd._EXT_SERVICES]
    ov = qd._view_data("overview", ctx)
    assert {"key": "status"} not in ov["health"]["failed"]
    assert ov["budget"] == {"disabled": True}


def test_a_view_that_raises_returns_its_error_state_in_words(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)

    def boom(data, ctx):
        raise RuntimeError("secret /home/x/path detail")

    _install(monkeypatch, "usage", _fake_view("usage", render=boom))
    httpd, port = _serve(qd)
    try:
        status, _h, body = _req(port, "GET", "/v/usage")
    finally:
        httpd.shutdown()
    text = body.decode()
    assert status == 200
    assert 'role="alert"' in text and 'data-state="error"' in text and "data-retry" in text
    assert "RuntimeError" in text
    assert "Traceback" not in text and "/home/x/path" not in text


def test_the_static_files_are_served_with_an_etag_and_nothing_else_is(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    httpd, port = _serve(qd)
    try:
        for name, ctype in (("app.css", "text/css"), ("app.js", "javascript")):
            status, hdrs, body = _req(port, "GET", f"/static/{name}")
            assert status == 200 and ctype in hdrs["Content-Type"]
            assert hdrs["Cache-Control"] == "no-cache"
            src = (_SRC.parent / "dashboard_ui" / "static" / name).read_bytes()
            assert body == src
            etag = hdrs["ETag"]
            assert etag.startswith('"') and etag.endswith('"') and len(etag) > 2
            status, hdrs2, body2 = _req(
                port, "GET", f"/static/{name}", headers={"If-None-Match": etag}
            )
            assert (status, body2) == (304, b"") and hdrs2["ETag"] == etag
            assert (
                _req(port, "GET", f"/static/{name}", headers={"If-None-Match": '"other"'})[0] == 200
            )
        for path in (
            "/static/../quota_dashboard.py",
            "/static/%2e%2e/x",
            "/static/",
            "/static/APP.CSS",
            "/static/strings.py",
            "/static/app.css/x",
            "/static/./app.css",
        ):
            assert _req(port, "GET", path)[0] == 404, path
    finally:
        httpd.shutdown()


# ── the snapshot token (409) ────────────────────────────────────────────────────────────────────────


def test_snapshot_token_shape():
    sys.path.insert(0, str(_SRC.parent))
    from dashboard_ui import snapshot

    item = {
        "question": "q?",
        "status": "open",
        "ground": "gate",
        "comments": [{}, {}],
        "alt_ids": ["b", "a"],
    }
    tok = snapshot.token(item)
    assert len(tok) == 16 and all(c in "0123456789abcdef" for c in tok)
    assert tok == snapshot.token({**item, "alt_ids": ["a", "b"], "title": "ignored"})
    assert snapshot.token({}) == snapshot.token(
        {"question": None, "status": None, "ground": None, "comments": [], "alt_ids": []}
    )
    for change in (
        {"question": "q2"},
        {"status": "blocked"},
        {"ground": "owned"},
        {"comments": [{}]},
        {"alt_ids": ["a", "b", "c"]},
    ):
        assert snapshot.token({**item, **change}) != tok, change


def test_a_verdict_carrying_a_stale_token_is_refused_409_and_runs_nothing(tmp_path, monkeypatch):
    shop = _store_repo("shop")
    item = _store_item(shop, "a task")
    qd = _load(tmp_path, monkeypatch)
    qd._repos_page(fresh=True)
    from dashboard_ui import snapshot

    def tok() -> str:
        return snapshot.token(json.loads(_item_file(shop, item).read_text()))

    first = tok()
    assert qd.item_verdict("shop", item, "comment", "one", token=first)[0] == 200
    n = len(json.loads(_item_file(shop, item).read_text())["comments"])
    # before a comment was appended
    assert qd.item_verdict("shop", item, "comment", "two", token=first) == (
        409,
        {"ok": False, "error": "changed"},
    )
    # before the ground, the question or the status changed, before a duplicate merge
    for change in (
        {"ground": "gate"},
        {"question": "which?"},
        {"status": "blocked"},
        {"alt_ids": ["W-0000beef"]},
    ):
        before = tok()
        _edit(shop, item, **change)
        assert qd.item_verdict("shop", item, "accept", token=before)[0] == 409, change
    assert len(json.loads(_item_file(shop, item).read_text())["comments"]) == n, (
        "work.py ran on a 409"
    )
    # the current token is accepted, over HTTP too: do_POST passes body["token"]
    httpd, port = _serve(qd)
    try:
        body = json.dumps(
            {"repo": "shop", "item": item, "action": "comment", "text": "three", "token": tok()}
        ).encode()
        status, _h, raw = _req(
            port, "POST", "/item-verdict", body=body, headers={qd.SWITCH_HEADER: "1"}
        )
        assert status == 200, raw
        stale = json.dumps(
            {"repo": "shop", "item": item, "action": "comment", "text": "four", "token": first}
        ).encode()
        status, _h, raw = _req(
            port, "POST", "/item-verdict", body=stale, headers={qd.SWITCH_HEADER: "1"}
        )
        assert (status, json.loads(raw)) == (409, {"ok": False, "error": "changed"})
    finally:
        httpd.shutdown()
    assert json.loads(_item_file(shop, item).read_text())["comments"][-1]["text"] == "three"


def test_an_absent_token_is_accepted_only_inside_the_legacy_window(tmp_path, monkeypatch):
    shop = _store_repo("shop")
    item = _store_item(shop, "a task")
    qd = _load(tmp_path, monkeypatch)
    qd._repos_page(fresh=True)
    assert qd._LEGACY_TOKEN_UNTIL is None
    assert qd.item_verdict("shop", item, "comment", "legacy")[0] == 200
    monkeypatch.setattr(qd, "_LEGACY_TOKEN_UNTIL", date.today())  # on the date itself: still open
    assert qd.item_verdict("shop", item, "comment", "today")[0] == 200
    monkeypatch.setattr(qd, "_LEGACY_TOKEN_UNTIL", date.today() - timedelta(days=1))
    assert qd.item_verdict("shop", item, "comment", "late") == (
        409,
        {"ok": False, "error": "changed"},
    )
    assert json.loads(_item_file(shop, item).read_text())["comments"][-1]["text"] == "today"


# ── targets: one slice per view, one union ──────────────────────────────────────────────────────────


def test_each_views_targets_survive_the_others_and_a_failing_view_empties_only_its_own(
    tmp_path, monkeypatch
):
    shop = _store_repo("shop")
    item = _store_item(shop, "work-only")
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())
    monkeypatch.setattr(
        qd, "_status_module", lambda: types.SimpleNamespace(collect_box=lambda opt: {"repos": []})
    )
    from dashboard_ui import components as ui
    from dashboard_ui.views import ViewResult

    ghost = {
        "name": "ghost",
        "main": str(shop),
        "root": str(shop),
        "error": None,
        "items": [{"id": "W-0000dead"}],
    }
    state = {"raise": False}

    def work_render(data, ctx):
        if state["raise"]:
            raise RuntimeError("work view broke")
        return ViewResult(html=ui.group("w"), item_targets=[*data["work"], ghost])

    def overview_render(data, ctx):
        agents = [
            {
                "name": "ghost",
                "main": str(shop),
                "error": None,
                "agents": [{"name": "lead", "can_pause": True, "paused": None}],
            }
        ]
        return ViewResult(html=ui.group("o"), pause_targets=agents, item_targets=[])

    _install(monkeypatch, "work", _fake_view("work", render=work_render))
    _install(monkeypatch, "overview", _fake_view("overview", render=overview_render))
    httpd, port = _serve(qd)
    try:
        assert _req(port, "GET", "/v/work")[0] == 200
        assert _req(port, "GET", "/v/overview")[0] == 200  # renders after Work, holds no items
        assert ("shop", item) in qd._ITEM_TARGETS and ("ghost", "lead") in qd._PAUSE_TARGETS
        assert qd._ITEM_TARGETS[("shop", item)] == (str(shop), str(shop))
        rebuilt: list[int] = []
        real_page = qd._repos_page
        monkeypatch.setattr(
            qd, "_repos_page", lambda fresh=False: (rebuilt.append(1), real_page(fresh))[1]
        )
        assert qd.item_verdict("shop", item, "comment", "found")[0] == 200
        assert rebuilt == [], "a Work-only target was found without a rebuild"
        # a /repos.html build publishes its own slice and evicts no view's
        real_page(fresh=True)
        assert ("ghost", "W-0000dead") in qd._ITEM_TARGETS and (
            "ghost",
            "lead",
        ) in qd._PAUSE_TARGETS
        # the Work view raises: its own slice empties, the Overview's pause target stays
        state["raise"] = True
        assert _req(port, "GET", "/v/work")[0] == 200
        assert ("ghost", "W-0000dead") not in qd._ITEM_TARGETS
        assert ("ghost", "lead") in qd._PAUSE_TARGETS
        status, out = qd.item_verdict("ghost", "W-0000dead", "accept")
        assert status == 400 and "not on the board" in out["error"]
    finally:
        httpd.shutdown()


def test_after_a_restart_a_verdict_and_a_pause_are_found_by_the_rebuild_on_miss(
    tmp_path, monkeypatch
):
    shop = _store_repo("shop")
    item = _store_item(shop, "stored")
    _run_record("s1", agent="wef1", state="done", command="fabrik-task", repo_root=str(shop))
    qd = _load(tmp_path, monkeypatch)
    # a fresh process: no view rendered, no board built, every registry empty
    assert qd._ITEM_TARGETS == {} and qd._PAUSE_TARGETS == {}
    assert qd.item_verdict("shop", item, "comment", "after restart")[0] == 200
    qd._ITEM_TARGETS = {}
    qd._PAUSE_TARGETS = {}
    qd._TARGET_SLICES["item"].clear()
    qd._TARGET_SLICES["pause"].clear()
    status, out = qd.pause_agent("shop", "wef1", "pause", "hold")
    assert status == 200, out
    assert (shop / ".git" / "fabrik-work" / "paused" / "wef1.json").exists()


# ── the probe state and the stale banner ────────────────────────────────────────────────────────────


def _boom():
    raise RuntimeError("connection reset")


def test_a_failing_probe_banners_the_quota_views_and_keeps_the_last_good_time(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())
    for name in _VIEWS:
        _install(monkeypatch, name, _fake_view(name))
    monkeypatch.setattr(qd, "_collect_work", lambda opt: [])
    monkeypatch.setattr(
        qd, "_status_module", lambda: types.SimpleNamespace(collect_box=lambda opt: {"repos": []})
    )
    qd.generate()
    good = qd._LAST_STATUS[0][0]
    httpd, port = _serve(qd)
    try:
        assert 'id="render-failed"' not in _req(port, "GET", "/v/accounts")[2].decode(), (
            "fresh: no banner"
        )
        monkeypatch.setattr(qd, "_probe", _boom)
        for _ in range(3):
            qd.generate()
            assert qd._LAST_STATUS[0][0] == good, "a fallback pass never restamps the payload"
            assert qd._LAST_STATUS[0][1]["probe_failed"].startswith("RuntimeError")
        assert qd._LAST_PROBE_FAILURE[0][1] == "RuntimeError"
        for name in ("accounts", "overview"):
            text = _req(port, "GET", f"/v/{name}")[2].decode()
            assert 'id="render-failed"' in text and "RuntimeError" in text, name
        assert 'id="render-failed"' not in _req(port, "GET", "/v/usage")[2].decode(), (
            "not a quota view"
        )
        from dashboard_ui.views import ViewContext

        health = qd._view_data("overview", ViewContext(_opt(), _ROOT, time.time()))["health"]
        assert any(f["key"] == "probe" and "RuntimeError" in f["error"] for f in health["failed"])
        # the probe recovers: the failure clears and so does the banner
        monkeypatch.setattr(qd, "_probe", lambda: _payload())
        qd.generate()
        assert qd._LAST_PROBE_FAILURE[0] is None
        assert 'id="render-failed"' not in _req(port, "GET", "/v/accounts")[2].decode()
        # a payload older than one probe cycle (interval + timeout + 60 s) carries the banner
        old = time.time() - (qd.PROBE_INTERVAL_S + qd.PROBE_TIMEOUT_S + 120)
        qd._LAST_STATUS[0] = (old, qd._LAST_STATUS[0][1])
        monkeypatch.setattr(qd, "_regen_async", lambda: None)
        assert 'id="render-failed"' in _req(port, "GET", "/v/accounts")[2].decode()
    finally:
        httpd.shutdown()


def test_the_payload_time_is_seeded_before_the_first_probe(tmp_path, monkeypatch):
    """A process that starts with a good quota.json and whose very first probe fails carries the
    file's mtime, not the fallback's rewrite; one that starts with a `probe_failed` file is stale at once."""
    for case, seed, expect_known in (
        ("good", _payload(), True),
        ("failed", {**_payload(), "probe_failed": "TimeoutError: x"}, False),
    ):
        sub = tmp_path / case
        sub.mkdir()
        qd = _load(sub, monkeypatch, QUOTA_DASH_PROBE_INTERVAL_S="3600")
        qd.OUT_DIR.mkdir(parents=True)
        qd._JSON.write_text(json.dumps(seed))
        old = time.time() - 4000
        os.utime(qd._JSON, (old, old))
        monkeypatch.setattr(qd, "_probe", _boom)
        monkeypatch.setattr(qd, "_credits_async", lambda: None)
        stop = qd._start_probe_loop()
        for _ in range(500):
            if qd._LAST_PROBE_FAILURE[0] is not None:
                break
            time.sleep(0.01)
        stop.set()
        assert qd._LAST_PROBE_FAILURE[0] is not None
        ts = qd._LAST_STATUS[0][0]
        if expect_known:
            assert ts == pytest.approx(old, abs=1.0), case
        else:
            assert ts is None, case
        assert qd._status_stale(time.time()), case  # 4000 s old, or unknown: the banner shows


def test_a_fresh_process_serves_quota_json_without_probing(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    qd.OUT_DIR.mkdir(parents=True)
    qd._JSON.write_text(json.dumps(_payload()))
    calls: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(1), _payload())[1])
    _install(monkeypatch, "accounts", _fake_view("accounts"))
    from dashboard_ui.views import ViewContext

    data = qd._view_data("accounts", ViewContext(_opt(), _ROOT, time.time()))
    assert data["status"]["payload"]["accounts"][0]["email"] == "mob@ocoron.com"
    httpd, port = _serve(qd)
    try:
        assert _req(port, "GET", "/v/accounts")[0] == 200
    finally:
        httpd.shutdown()
    worker = qd._LAST_REGEN[0]
    if worker is not None:
        worker.join(timeout=10)
    assert calls == []
    # with nothing on disk and nothing probed yet, the status is said, never invented
    qd2 = _load(tmp_path / "empty", monkeypatch)
    data = qd2._view_data("accounts", ViewContext(_opt(), _ROOT, time.time()))
    assert data["status"] == {"error": "no reading yet"}


def test_a_moved_pointer_triggers_exactly_one_bounded_regeneration(tmp_path, monkeypatch):
    pointer = tmp_path / "active"
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    monkeypatch.setattr(qd, "_probe", lambda: _payload())
    pointer.symlink_to(tmp_path / "mob")
    qd.generate()
    pointer.unlink()
    pointer.symlink_to(tmp_path / "can")
    gens: list[int] = []
    real = qd.generate

    def counted():
        gens.append(1)
        return real()

    monkeypatch.setattr(qd, "generate", counted)
    monkeypatch.setattr(qd, "_probe", _boom)  # the flip's probe fails: the pointer still moved
    _install(monkeypatch, "accounts", _fake_view("accounts"))
    _install(monkeypatch, "overview", _fake_view("overview"))
    monkeypatch.setattr(qd, "_collect_work", lambda opt: [])
    monkeypatch.setattr(
        qd, "_status_module", lambda: types.SimpleNamespace(collect_box=lambda opt: {"repos": []})
    )
    httpd, port = _serve(qd)
    try:
        for path in ("/v/accounts", "/v/overview", "/v/accounts"):
            assert _req(port, "GET", path)[0] == 200
    finally:
        httpd.shutdown()
    assert gens == [1]


# ── the budget's data half ─────────────────────────────────────────────────────────────────────────


def test_the_budget_data_is_disabled_without_a_subprocess_and_never_blocks(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    ran: list[object] = []
    monkeypatch.setattr(
        qd.subprocess, "run", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError)
    )
    from dashboard_ui.views import ViewContext

    assert qd._view_data("overview", ViewContext(_opt(), _ROOT, time.time()))["budget"] == {
        "disabled": True
    }
    assert qd._budget_data() == {"disabled": True}
    assert ran == []
    # enabled, cache empty: the background thread starts and the call returns at once
    monkeypatch.setenv("QUOTA_DASH_BUDGET", "1")
    gate = threading.Event()
    payload = {
        "caps": {"concurrency_cap": 17},
        "box_caps": {"read_only": 23, "heavy": 12},
        "heavy_reasons": [],
        "reasons": ["sibling seats unknown <b>, not subtracted"],
        "quota": {"ok": True, "active": "a@x", "hottest_pct": 7.0, "eligible": 1, "hold": False},
    }

    class _R:
        stdout = json.dumps(payload)

    def slow(*a, **k):
        gate.wait(10)
        return _R()

    monkeypatch.setattr(qd.subprocess, "run", slow)
    t0 = time.time()
    first = qd._budget_data()
    assert time.time() - t0 < 1.0 and first.get("computing") is True
    th = qd._budget_cache["thread"]
    assert th is not None and th.is_alive()
    gate.set()
    th.join(timeout=10)
    data = qd._budget_data()
    assert data["caveats"] == ["sibling seats unknown <b>, not subtracted"], "plain, unescaped"
    assert [s["allowed"] for s in data["seats"]] == [17, 12]
    # the HTML half is unchanged: built from the same reading, escaped once
    assert "&lt;b&gt;" in qd._budget_cache["html"]


# ── the work-data cache ─────────────────────────────────────────────────────────────────────────────


def test_two_concurrent_work_requests_collect_once(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    calls: list[int] = []
    gate = threading.Event()

    def slow(opt):
        calls.append(1)
        gate.wait(5)
        return [
            {"name": "shop", "items": [], "error": None, "skipped": [], "main": "/x", "root": "/x"}
        ]

    monkeypatch.setattr(qd, "_collect_work", slow)
    _install(monkeypatch, "work", _fake_view("work"))
    httpd, port = _serve(qd)
    out: list[int] = []
    try:
        ts = [
            threading.Thread(target=lambda: out.append(_req(port, "GET", "/v/work")[0]))
            for _ in range(2)
        ]
        for t in ts:
            t.start()
        time.sleep(0.3)
        gate.set()
        for t in ts:
            t.join(timeout=10)
    finally:
        httpd.shutdown()
    assert out == [200, 200] and calls == [1]
    qd._drop_repos_cache()  # a board write drops the cached work data too
    qd._work_data()
    assert calls == [1, 1]


def test_collect_work_entries_carry_the_tree_they_were_read_from(tmp_path, monkeypatch):
    shop = _store_repo("shop")
    _store_item(shop, "x")
    qd = _load(tmp_path, monkeypatch)
    (entry,) = qd._collect_work(_opt())
    assert entry["root"] == str(shop) and entry["main"] == str(shop)


def test_the_view_package_never_imports_the_dashboard_module():
    import ast

    pkg = _SRC.parent / "dashboard_ui"
    files = sorted(pkg.rglob("*.py"))
    assert len(files) >= 5  # __init__, components, strings, fmt, snapshot, views/__init__
    for py in files:
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            )
            assert not any("quota_dashboard" in n for n in names), py
