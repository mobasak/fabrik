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

import importlib.util
import json
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str):
    """Import a FRESH module instance whose env-derived module constants point at tmp_path."""
    monkeypatch.setenv("QUOTA_DASH_OUT_DIR", str(tmp_path / "out"))
    # never the box's REAL pointer: a test render says "mob" while the box may point elsewhere,
    # and the pointer-moved regeneration would then fire on every view
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(tmp_path / "active"))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location(f"qd_{tmp_path.name}", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


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


def test_serving_inside_the_floor_costs_exactly_one_probe(tmp_path, monkeypatch):
    """The probe-volume bound: many views inside QUOTA_DASH_MAX_AGE_S → ONE probe."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    calls: list[float] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(time.time()), _payload())[1])

    first = qd._fresh_html()
    for _ in range(5):
        again = qd._fresh_html()

    assert len(calls) == 1, f"expected 1 probe for 6 views inside the floor, got {len(calls)}"
    assert "mob@ocoron.com" in first and "mob@ocoron.com" in again


def test_a_view_past_the_floor_reprobes(tmp_path, monkeypatch):
    """The other half of the bound: the page must not go stale forever."""
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="0")
    calls: list[int] = []
    monkeypatch.setattr(qd, "_probe", lambda: (calls.append(1), _payload())[1])

    qd._fresh_html()
    qd._fresh_html()
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
    html = qd.generate()

    assert "mob@ocoron.com" in html, "the last good board must survive a failed probe"
    assert "28%" in html, "…including its numbers (100-72 weekly remaining)"
    assert "live probe failed" in html.lower()
    assert "connection reset" in html


def test_the_board_reports_remaining_not_used(tmp_path, monkeypatch):
    """Inversion guard: 91% used must render as 9% left, not 91%."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=91.0))

    html = qd.generate()

    assert '<span class="pct warn">9%</span> left' in html, "weekly 91% used → 9% left"
    assert '<span class="pct ok">100%</span> left' in html, "session 0% used → 100% left"
    assert "91% used" in html, "the raw utilisation stays visible as the sub-line"


def test_red_starts_where_the_fleet_abandons_the_account(tmp_path, monkeypatch):
    """The crit boundary is not cosmetic: ≤5% left == ≥95% used == the flip threshold, i.e.
    red means 'the fleet is about to leave this account', amber means 'still usable'."""
    qd = _load(tmp_path, monkeypatch)

    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=95.0))
    assert '<span class="pct crit">5%</span> left' in qd.generate()

    monkeypatch.setattr(qd, "_probe", lambda: _payload(session=0.0, weekly=94.0))
    assert '<span class="pct warn">6%</span> left' in qd.generate()


def test_cap_walled_account_is_named_as_reserved(tmp_path, monkeypatch):
    """The operator's reserve must be legible on the board, not just in the CLI."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload()
    payload["accounts"][0].update(
        {"email": "ob@ocoron.com", "slugs": ["ob"], "weekly_cap": 90, "cap_walled": True}
    )
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert "cap 90%" in html
    assert "RESERVED" in html and "fleet excluded" in html


def test_generate_writes_both_artifacts(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", lambda: _payload())

    qd.generate()

    assert qd._HTML.is_file() and qd._JSON.is_file()
    assert json.loads(qd._JSON.read_text())["active"] == "mob"


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

    html = qd.generate()

    assert '<span class="pct ok">100%</span> left' not in html, "no unearned reassuring 100%"
    assert "idle" in html, "a non-active account's rolled window is EMPTY by construction — say so"
    assert "not the active pointer" in html, "and say why it is derivable, not measured"
    assert '<span class="pct warn">9%</span> left' in html, "the 7-day cell survives at 8.5h"


def test_a_cached_reading_younger_than_its_window_still_shows_the_number(tmp_path, monkeypatch):
    """The other half: 30 minutes into a 5-hour window the cached reading is still about the
    window we are in, so suppressing it would throw away real information."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=40.0, weekly=50.0)
    payload["accounts"][0].update({"source": "cache", "age_s": 1800.0})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert '<span class="pct ok">60%</span> left' in html
    assert "which has since rolled" not in html


def test_the_active_account_cannot_claim_idle_when_its_window_rolled(tmp_path, monkeypatch):
    """The 'idle' shortcut is only sound because a non-active account cannot burn fleet quota.
    The ACTIVE account can, so a rolled-over window there is genuinely unknown, not idle."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=50.0)
    payload["active"] = "mob"  # the row below IS mob
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    html = qd.generate()

    assert "unknown" in html and ">idle<" not in html


def test_a_capped_account_surfaces_the_browser_blind_spot(tmp_path, monkeypatch):
    """A cap exists because the operator uses that account in the browser — usage no probe of
    ours can see. An 'idle' cell there must not imply we checked."""
    qd = _load(tmp_path, monkeypatch)
    payload = _payload(session=0.0, weekly=91.0)
    payload["active"] = "someone-else"
    payload["accounts"][0].update({"source": "cache", "age_s": 8.5 * 3600, "weekly_cap": 90})
    monkeypatch.setattr(qd, "_probe", lambda: payload)

    assert "browser use is not visible here" in qd.generate()


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
    html = qd._row(acct, "sarp")
    assert ">24%</span> left" in html, "Fable cell shows remaining (100-76) in its own column"
    assert "76% used" in html


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
    assert "no reading" in qd._row(acct, "ob")


def test_header_has_fable_weekly_column(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    html = qd.render({"accounts": [], "active": None}, 0.0)
    assert "Fable 5 weekly remaining" in html


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


def test_every_idle_row_has_a_switch_button_and_the_active_row_has_none(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _multi_payload)
    html = qd.generate()
    assert 'data-slug="sarp"' in html
    assert 'data-slug="mob"' not in html  # mob is the active pointer


def test_a_short_body_cannot_hold_a_handler_thread_forever(tmp_path, monkeypatch):
    """A client that promises 100 bytes and sends 10 must be dropped by the socket timeout,
    not parked on `rfile.read()` until it decides to leave (measured before the fix: the
    handler thread hung for as long as the client stayed connected)."""
    import socket

    monkeypatch.setenv("QUOTA_DASH_SOCKET_TIMEOUT_S", "0.5")  # the knob the fix reads at import
    qd, _stub = _switch_env(tmp_path, monkeypatch)
    httpd, base = _serve(qd)
    try:
        host, port = httpd.server_address[:2]
        s = socket.create_connection((host, port), timeout=5)
        s.sendall(
            b"POST /switch HTTP/1.1\r\nHost: x\r\nX-Quota-Dash: 1\r\n"
            b"Content-Type: application/json\r\nContent-Length: 100\r\n\r\n" + b'{"account"'
        )
        t0 = time.time()
        try:
            data = s.recv(4096)  # either a response or a clean close — never a hang past 5s
        except TimeoutError:
            pytest.fail("handler held the connection open past 5s on a short body")
        assert time.time() - t0 < 4.0
        assert data == b"" or data.startswith(b"HTTP/1.")
        s.close()
    finally:
        httpd.shutdown()


def test_a_pointer_change_regenerates_before_the_floor(tmp_path, monkeypatch):
    """The operator switched accounts and the board kept showing the OLD pointer for up to
    floor + reload (~5 min) — measured 2026-09-02 after a `--switch`. A pointer that no longer
    matches the rendered `active` must regenerate on the next view, floor or no floor."""
    pointer = tmp_path / "active"
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(pointer))
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    state = {"active": "mob"}
    monkeypatch.setattr(qd, "_probe", lambda: {**_payload(), "active": state["active"]})
    pointer.symlink_to(tmp_path / "mob")
    assert 'who">mob' in qd.generate()
    # the pointer moves (a --switch or a tick flip); the render on disk is seconds old
    pointer.unlink()
    pointer.symlink_to(tmp_path / "can")
    state["active"] = "can"
    assert 'who">can' in qd._fresh_html(), "a moved pointer must not wait for the floor"
    assert 'who">can' in qd._fresh_html()  # and the second view costs no second probe path


def test_a_probe_hang_after_a_flip_blocks_one_view_not_every_view(tmp_path, monkeypatch):
    """After a flip the board regenerates synchronously ONCE. If that probe FAILS, the fallback
    payload must carry the live pointer so the next views serve instantly instead of each
    paying the probe timeout until the probe recovers (review finding on the pointer-moved path)."""
    pointer = tmp_path / "active"
    monkeypatch.setenv("QUOTA_DASH_POINTER", str(pointer))
    qd = _load(tmp_path, monkeypatch, QUOTA_DASH_MAX_AGE_S="600")
    monkeypatch.setattr(qd, "_probe", lambda: {**_payload(), "active": "mob"})
    pointer.symlink_to(tmp_path / "mob")
    qd.generate()
    pointer.unlink()
    pointer.symlink_to(tmp_path / "can")
    calls: list[int] = []

    def _hang():
        calls.append(1)
        raise TimeoutError("probe hung")

    monkeypatch.setattr(qd, "_probe", _hang)
    qd._fresh_html()  # the one synchronous attempt after the flip — it fails
    qd._fresh_html()
    qd._fresh_html()
    assert len(calls) == 1, f"every view re-ran the failed probe: {len(calls)} probes for 3 views"
    assert 'who">can' in qd._fresh_html(), (
        "the pointer is a local fact — shown even when the probe is down"
    )


def test_the_rendered_script_parses(tmp_path, monkeypatch):
    """The page's ONE <script> carries the auto-reloader AND the switch handlers. A syntax error
    anywhere in it silently kills both (measured 2026-09-02: a raw newline inside the confirm()
    string — the board froze on the old account and every button was inert). Parse it."""
    import re
    import shutil
    import subprocess

    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_probe", _multi_payload)
    html = qd.generate()
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    # no JS string literal may span a line: a raw newline inside quotes is the exact defect
    for line in script.splitlines():
        assert line.count('"') % 2 == 0, f"unbalanced quotes → a string spans lines: {line[:80]!r}"
    node = shutil.which("node")
    if node:
        js = tmp_path / "page.js"
        js.write_text(script, encoding="utf-8")
        r = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[:400]


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
