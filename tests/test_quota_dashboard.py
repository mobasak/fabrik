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
import re
import subprocess
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
    stop = qd._start_probe_loop()
    time.sleep(0.8)
    stop.set()
    probes = [c for c in _calls(stub) if c[:2] == ["--status", "--json"]]
    assert len(probes) >= 3, probes


def test_the_active_account_crossing_the_session_threshold_triggers_the_tick_at_once(
    tmp_path, monkeypatch
):
    """Operator rule: rotate as soon as the 5h window hits 98%. The board, which now probes every
    20s, invokes the rotation tick the moment the ACTIVE account's session ≥ ROTATE_THRESHOLD —
    once per cooldown, never at 90%."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=86.0, QUOTA_DASH_TRIGGER_COOLDOWN_S="60")
    qd.generate()
    assert qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text())) is None
    assert not [c for c in _calls(stub) if c[:1] == ["--tick"]]
    (tmp_path / "stub_rotate.py.payload").write_text(json.dumps(_payload(session=98.2)))
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


def test_the_page_is_wide_and_refreshes_every_20s(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    html = qd.render(_payload(), time.time())
    assert qd.REFRESH_S == 20 and "refreshes every 20s" in html
    assert "max-width:1600px" in html


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
    assert qd.TRIGGER_THRESHOLD == cr._rotate_threshold() == 95.0


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
    html = qd.render(payload, now)
    first = html.index("sarp@ocoron.com")
    assert (
        first
        < html.index("can@ocoron.com")
        < html.index("mob@ocoron.com")
        < html.index("ob@ocoron.com")
    )
    assert "next" in html.lower()  # the rank is labelled, not implied


def test_the_probe_interval_is_a_period_not_a_pause_after_each_probe(tmp_path, monkeypatch):
    """A probe of four accounts takes ~20s itself; waiting the full interval AFTER it made the real
    cadence ~40s (measured live 2026-09-03: 43s between quota.json writes). The interval is the
    PERIOD: the loop waits interval minus the probe's own duration."""
    qd, stub = _tick_env(tmp_path, monkeypatch, QUOTA_DASH_PROBE_INTERVAL_S="0.15")
    real = qd.generate

    def slow_generate():
        time.sleep(0.1)
        return real()

    monkeypatch.setattr(qd, "generate", slow_generate)
    stop = qd._start_probe_loop()
    # 1.6s, not 0.8s. The counts are what discriminate, and small counts flake: at 0.8s this asserted
    # >=4 against an expected 5 — a 20% margin that a loaded box (three pool dispatches running
    # alongside it, 2026-09-05) eats through thread-scheduling jitter alone, then reds a correct
    # implementation. Doubling the window doubles both predictions and widens the gap in absolute
    # terms: period 0.15 -> ~10 probes; pause-after-probe (0.15 + 0.1 per cycle) -> ~6. A floor of 7
    # sits 30% under the correct model and still above the wrong one, so the test discriminates
    # HARDER than it did while flaking less.
    time.sleep(1.6)
    stop.set()
    probes = [c for c in _calls(stub) if c[:2] == ["--status", "--json"]]
    assert len(probes) >= 7, probes


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
    """The guard `_generate_locked`'s own comment promised but did not have. The pool balance is a
    panel; the quota board is the reason the page exists."""
    qd = _load(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise RuntimeError("pool exploded")

    monkeypatch.setattr(qd, "_pool_credits", boom)
    monkeypatch.setattr(qd, "_probe", _payload)
    html = qd.generate()
    assert "Claude account quota" in html and "mob" in html


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
    src_dir = qd._FABRIK_ROOT / "commands" / "_sources"
    hits = {
        f.stem: {k for k, rx in qd._EXT_COMPILED if rx.search(f.read_text(encoding="utf-8"))}
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
    # and the honest limit is ON THE PAGE, not only in a comment
    intro = qd._ext_matrix_intro(qd._load_commands())
    assert "reads no NEGATIONS" in intro and "preserves both is invisible" in intro
    # R6: "cannot go stale against the corpus" survived round 5 and sat one clause from the sentence
    # explaining exactly how it CAN — an absolute claim next to its own counterexample.
    assert "cannot go stale" not in intro


def test_an_unreadable_pool_balance_says_so_on_the_page(tmp_path, monkeypatch):
    """Round 4, and it corrects THIS session's own earlier fix. Guarding the render stopped the
    board dying, but the panel then vanished — and "no panel" already means "the pool is not
    configured on this box". A fault that renders identically to a deliberate absence, traceable
    only in a log nobody reads, is the exact shape of the freeze this file was carrying an hour ago.
    The board must SAY it, and must not print a zero the operator would act on."""
    qd = _load(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(qd, "_pool_credits", boom)
    monkeypatch.setattr(qd, "_probe", _payload)
    html = qd.generate()
    assert "Claude account quota" in html and "mob" in html  # the board still stands
    assert "Pool balance UNREADABLE" in html and "PermissionError" in html
    assert "not zero" in html, "a missing balance must not read as an exhausted one"
    # and a pool that is simply NOT CONFIGURED still renders no panel at all — the two are different
    monkeypatch.setattr(qd, "_pool_credits", lambda *a, **k: None)
    assert "Pool balance UNREADABLE" not in qd.generate()


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
        "fly": ["record_agent_run(spec, result)"],
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
    # A reader raised "a hand-edited title containing a literal quote breaks the title attribute".
    # REFUTED, and pinned: html.escape defaults to quote=True, so the attribute survives.
    hostile = '"><script>alert(1)</script>'
    monkeypatch.setattr(qd, "_EXT_SERVICES", ((("x", "x", hostile, "zzz"),)))
    html = qd._ext_matrix_table([{"name": "c", "services": set(), "rendered": True}])
    assert "<script>" not in html and "&quot;&gt;&lt;script&gt;" in html


def test_every_command_gets_a_matrix_row_and_the_totals_carry_their_denominator(
    tmp_path, monkeypatch
):
    """A count with no denominator is indistinguishable from having looked at nothing
    (CLAUDE.md § HARD STOPS), so the footer states `of N` and each total is re-derived here."""
    qd = _load(tmp_path, monkeypatch)
    rows = qd._load_commands()
    html = qd._ext_matrix_table(rows)
    assert html.count('<td class="cmd"><strong>/') == len(rows)
    assert f'<td class="cmd tot">of {len(rows)}</td>' in html
    for key, _l, _t, _p in qd._EXT_SERVICES:
        assert f'<td class="dot tot">{sum(1 for r in rows if key in r["services"])}</td>' in html
    # the live corpus must actually exercise the matrix — an all-blank grid would pass every
    # assertion above and tell the operator nothing
    assert sum(len(r["services"]) for r in rows) > len(rows), "the live corpus reaches services"


def test_an_unrendered_corpus_is_declared_never_silently_underreported(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", tmp_path / "absent")
    qd._cmd_cache_key = None
    rows = qd._load_commands()
    intro = qd._ext_matrix_intro(rows)
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
    monkeypatch.setattr(qd, "RENDERED_COMMANDS", Path.home() / ".claude" / "commands")
    qd._cmd_cache_key = None
    assert "UNDER-report" not in qd._ext_matrix_intro(qd._load_commands())


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


def test_the_matrix_is_in_the_commands_pane_and_names_its_maintenance_point(tmp_path, monkeypatch):
    """The operator's second ask: a note that says how this is kept current. The registry name and
    its file must be ON THE PAGE — a maintenance contract only in a code comment is unfindable."""
    qd = _load(tmp_path, monkeypatch)
    html = qd.render(_payload(), time.time())
    pane = html[
        html.index('<section id="pane-commands"') : html.index('<section id="pane-external"')
    ]
    assert "External services per command" in pane and 'table class="matrix"' in pane
    assert "_EXT_SERVICES" in pane and "scripts/sysadmin/quota_dashboard.py" in pane
    # R2, all three independent readers: the opening sentence used to assert the data came from the
    # rendered corpus unconditionally, which a missing or PARTIAL render made false two sentences
    # before the caveat said otherwise. It must state how many rows actually came from there.
    rows = qd._load_commands()
    n_r = sum(1 for r in rows if r["rendered"])
    assert f"{n_r} of {len(rows)} rows from the rendered" in pane


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


def test_page_has_two_tabs_quota_default_commands_second(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    html = qd.render(_payload(), time.time())
    assert 'data-tab="quota"' in html and 'data-tab="commands"' in html
    assert html.index('data-tab="quota"') < html.index('data-tab="commands"')
    assert '<section id="pane-quota" class="pane">' in html
    assert '<section id="pane-commands" class="pane" hidden>' in html
    assert html.count('<tr><td class="ord">') == len(qd._load_commands())
    assert "location.hash" in html  # the chosen tab survives the 20s reload
    for col in ("Command", "Stage", "Purpose", "When to use", "Skip when", "Next"):
        assert f"<th>{col}</th>" in html


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
    html = qd.render(_payload(), time.time())
    assert "Command corpus unreadable" in html


# ── External-services tab (operator ask 2026-09-03; seen RED first) ───────────────────────────


def test_external_services_page_is_served_from_the_static_file_and_404s_when_absent(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)
    page = tmp_path / "external-services-dashboard.html"
    monkeypatch.setattr(qd, "EXT_SERVICES_HTML", page)
    httpd, base = _serve(qd)
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/external-services.html", timeout=10)
        assert e.value.code == 404
        page.write_text(
            "<html><title>External Services</title><body>ok</body></html>", encoding="utf-8"
        )
        with urllib.request.urlopen(base + "/external-services.html", timeout=10) as r:
            assert r.status == 200 and "text/html" in r.headers["Content-Type"]
            assert b"External Services" in r.read()
    finally:
        httpd.shutdown()


def test_page_has_an_external_services_tab_with_a_lazy_iframe_and_freshness(tmp_path, monkeypatch):
    qd = _load(tmp_path, monkeypatch)
    page = tmp_path / "external-services-dashboard.html"
    page.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(qd, "EXT_SERVICES_HTML", page)
    html = qd.render(_payload(), time.time())
    assert 'data-tab="external"' in html and html.index('data-tab="commands"') < html.index(
        'data-tab="external"'
    )
    assert '<section id="pane-external" class="pane" hidden>' in html
    assert 'data-src="/external-services.html"' in html  # set to src only when the tab is shown
    import re as _re

    # the phrase SHAPE is pinned: reusing `_fmt_age` once produced "regenerated cached 10h ago ago"
    assert _re.search(r"regenerated \d+\.\d h ago by the daily chain", html)
    # The hash keeps the tab across the 20s reload. Pinned on the MECHANISM, not on the literal
    # `"#external"` an earlier implementation happened to contain: the restore became GENERIC on
    # 2026-09-05 (any pane restorable by its own hash, because naming tabs literally meant every tab
    # added later fell through to quota on every auto-reload). The old assertion went red against a
    # strictly better behaviour. These two fail if the restore is deleted or narrowed back to a
    # hardcoded list.
    assert 'location.pathname : "#" + name' in html, "choosing a tab must write its hash"
    assert 'document.getElementById("pane-" + want)' in html, (
        "and any existing pane restores from it"
    )
    monkeypatch.setattr(qd, "EXT_SERVICES_HTML", tmp_path / "missing.html")
    absent = qd.render(_payload(), time.time())
    assert (
        "not generated yet" in absent and '<iframe id="ext-frame"' not in absent
    )  # no iframe element → no 404 rendered inside it (the JS may still name the id)


def test_external_services_route_serves_only_a_regular_html_file(tmp_path, monkeypatch):
    """Review: the env override followed a symlink to /etc/hostname. A directory, a symlink whose
    name is not .html, or a non-.html file all 404 — the single-operator threat model is stated in
    the route comment; this is the cheap guard that still makes the measured leak impossible."""
    import os

    qd = _load(tmp_path, monkeypatch)
    link = tmp_path / "l"
    os.symlink("/etc/hostname", link)
    httpd, base = _serve(qd)
    try:
        for target in (tmp_path, link, tmp_path / "nope.html"):
            monkeypatch.setattr(qd, "EXT_SERVICES_HTML", target)
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(base + "/external-services.html", timeout=10)
            assert e.value.code == 404, target
    finally:
        httpd.shutdown()


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
    """A drain tick at 91 followed 30 s later by 96 must fire AGAIN — a shared cooldown would
    hold the flip for up to two minutes, which a burst covers from 95 to 100."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    qd, stub = _tick_env(tmp_path, monkeypatch, session=91.0, QUOTA_DASH_TRIGGER_COOLDOWN_S="600")
    qd.generate()
    t = qd._maybe_trigger_rotation(json.loads(qd._JSON.read_text()))
    assert t is not None
    t.join(10)
    (tmp_path / "stub_rotate.py.payload").write_text(json.dumps(_payload(session=96.0)))
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
    assert qd._pool_credits_panel(None) == ""
    html = qd.render(_payload(), time.time())
    assert "<table" in html, "the board still renders"


def test_the_key_never_reaches_the_page_or_the_cache(tmp_path, monkeypatch):
    """The one thing that must never leak. The panel and the on-disk cache are both readable by
    anything that can read the board."""
    qd = _credits_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        qd, "_credits_get", lambda key: {"data": {"total_credits": 100.0, "total_usage": 40.0}}
    )
    c = qd._pool_credits(now=1000.0)

    panel = qd._pool_credits_panel(c)
    assert "TESTKEY" not in panel
    assert "TESTKEY" not in qd.CREDITS_CACHE.read_text()
    assert "TESTKEY" not in qd.render(_payload(), time.time(), credits=c)


def test_the_panel_reaches_the_page_and_goes_critical_when_the_pool_is_dry(tmp_path, monkeypatch):
    qd = _credits_env(tmp_path, monkeypatch)

    healthy = qd._pool_credits_panel(
        {"granted": 245.0, "used": 25.0, "remaining": 220.0, "age_s": 0.0, "stale": False}
    )
    assert "ok" in healthy and "$220.00" in healthy

    dry = qd._pool_credits_panel(
        {"granted": 245.0, "used": 245.01, "remaining": -0.01, "age_s": 0.0, "stale": False}
    )
    assert "crit" in dry
    assert "402" in dry, "say WHAT the operator will see, not just that a number is low"

    html = qd.render(
        _payload(),
        time.time(),
        credits={"granted": 1.0, "used": 0.0, "remaining": 1.0, "age_s": 0.0, "stale": False},
    )
    assert "OpenRouter" in html, "the panel must actually be placed in the page"


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


def test_the_pool_banner_shows_on_the_external_services_tab_too(tmp_path, monkeypatch):
    """Operator, 2026-09-04, looking at #external: "i dont see it here?" — and they were right to
    look there. OpenRouter is listed on the external-services page as a paid provider with a
    `credit` field that nothing fills, so that tab is where a person goes to ask "is my third-party
    spend OK". The Quota tab is about Claude ACCOUNTS; putting the pool balance only there hid it
    behind a mental model the board does not actually teach."""
    qd = _credits_env(tmp_path, monkeypatch)
    c = {"granted": 245.0, "used": 225.87, "remaining": 19.13, "age_s": 0.0, "stale": False}

    html = qd.render(_payload(), time.time(), credits=c)

    ext = html[html.index('<section id="pane-external"') :]
    assert "OpenRouter pool" in ext, "the external-services pane must carry the balance"
    quota = html[html.index('<section id="pane-quota"') : html.index('<section id="pane-commands"')]
    assert "OpenRouter pool" in quota, "and it stays on the quota tab — it IS a quota"
    assert html.count("OpenRouter pool") == 2, "exactly the two panes, not a third copy"


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

    panel = qd._spend_panel()

    assert "4,200,000,000 tokens are NOT in any total on this page" in panel
    assert "claude-mythos-5-1" in panel, "name the model, or nobody can act on the warning"


def test_no_unclassified_tokens_means_no_warning(tmp_path, monkeypatch):
    """A warning that shows when nothing is wrong is wallpaper, and wallpaper is how a real one gets
    read past."""
    qd = _sidecar(tmp_path, monkeypatch, {})

    panel = qd._spend_panel()

    assert "NOT in any total" not in panel
    assert "Daily token consumption" in panel, (
        "the panel still rendered — the assertion above is real"
    )


def test_the_warning_survives_the_blank_panel_path(tmp_path, monkeypatch):
    """All-unrecognised is precisely the state that empties `tiers`, and an empty `tiers` is the
    early return that renders nothing at all. So the one case where the whole panel goes silent is
    the one case where the reader most needs to be told why — the warning is computed before that
    return, not beside the table."""
    qd = _sidecar(tmp_path, monkeypatch, {"claude-mythos-5-1": 9_000_000})
    blank = json.loads(qd._COST_SIDECAR.read_text(encoding="utf-8"))
    blank["per_model_spend"]["tiers"] = {}
    blank["per_model_spend"]["spend_usd"] = None
    blank["per_model_spend"]["base_rate_per_mtok"] = None
    qd._COST_SIDECAR.write_text(json.dumps(blank), encoding="utf-8")

    panel = qd._spend_panel()

    assert "9,000,000 tokens are NOT in any total on this page" in panel
    assert "<table>" not in panel, "no zeroed table — only the explanation"


def test_an_unreadable_sidecar_still_renders_nothing(tmp_path, monkeypatch):
    """The fail-soft contract is unchanged for every other cause: no file, bad JSON, old format."""
    qd = _load(tmp_path, monkeypatch)
    monkeypatch.setattr(qd, "_COST_SIDECAR", tmp_path / "does-not-exist.json")
    assert qd._spend_panel() == ""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(qd, "_COST_SIDECAR", bad)
    assert qd._spend_panel() == ""


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

    panel = qd._spend_panel()

    assert "$800/month" in panel, "the FEE must be on the page, not only the window slice"
    assert "25 August days at $800/31" in panel and "5 September days at $800/30" in panel
    assert "not a calendar month" in panel


def test_an_underivable_fee_breakdown_is_omitted_not_guessed(tmp_path, monkeypatch):
    """The window's own months are what the breakdown needs. If the sidecar does not carry a fee for
    one of them, the number still stands and the explanation is simply absent — an invented split
    would be worse than none."""
    qd = _sidecar(tmp_path, monkeypatch, {})  # monthly_spend has 2026-09 only; the window spans 08
    panel = qd._spend_panel()
    assert "priced against <b>$800.00</b> for that window" in panel
    assert "August days at" not in panel and "$800/month" not in panel


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
    html = qd.render(_pending_payload(["ozgurbasak"]), 1_900_000_000.0)
    assert "ozgurbasak" in html, "the scaffolded dir vanished from the board"
    assert "pending-login" in html, "the row must say WHY it is not an account yet"
    assert "/login" in html, "the row must name the one action that pins it"
    # it is never mistaken for a candidate: no switch button, and it sorts after every account
    assert html.index("ob@ocoron.com") < html.index("ozgurbasak")


def test_no_pending_key_renders_no_pending_row(tmp_path, monkeypatch):
    """The control: an older --status --json without `pending` must not conjure a row."""
    qd = _load(tmp_path, monkeypatch)
    p = _pending_payload([])
    del p["pending"]
    html = qd.render(p, 1_900_000_000.0)
    assert "pending-login" not in html


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


def test_queue_is_numbered_active_first_then_the_picker_order_then_returns_by_time(
    tmp_path, monkeypatch
):
    qd = _load(tmp_path, monkeypatch)
    order = [e["slug"] for e in qd._queue(_queue_payload(), _NOW)]
    assert order == ["ob", "zeta", "alpha", "mob", "can"], order
    html = qd.render(_queue_payload(), _NOW)
    # every account row carries its 1-based queue position, in display order. Search the TABLE
    # BODY only: a bare "#3" also matches hex colours in the stylesheet ("#333") — first probe did.
    body = html[html.index("<tbody>") :]
    pos = [body.index(f"#{n} ") for n in (1, 2, 3, 4, 5)]
    assert pos == sorted(pos), "queue numbers are not in ascending order on the page"
    assert (
        html.index("ob@ocoron.com")
        < html.index("zeta@ocoron.com")
        < html.index("alpha@ocoron.com")
        < html.index("mob@ocoron.com")
        < html.index("can@ocoron.com")
    )


def test_ineligible_tail_is_ordered_by_when_it_returns_not_by_utilization(tmp_path, monkeypatch):
    """mob (session-spent, back in 2h) must precede can (cap-walled, back in 20h) even though
    mob's session reads 100% and can's reads 5% — the queue is about WHEN, not how full."""
    qd = _load(tmp_path, monkeypatch)
    entries = {e["slug"]: e for e in qd._queue(_queue_payload(), _NOW)}
    assert entries["mob"]["returns_at"] == _NOW + 2 * 3600
    assert entries["can"]["returns_at"] == _NOW + 20 * 3600
    html = qd.render(_queue_payload(), _NOW)
    assert "returns" in html.lower()


def test_a_session_capped_active_account_is_both_first_and_its_return_slot(tmp_path, monkeypatch):
    """Active at 96% session with a 5h reset in 4h: it is #1 now AND it comes back after mob (2h)
    but before can (20h) → a ghost row at #5 saying so, and a badge on the active row."""
    qd = _load(tmp_path, monkeypatch)
    p = _queue_payload(active_five=96.0, active_five_reset=_NOW + 4 * 3600)
    slugs = [e["slug"] for e in qd._queue(p, _NOW)]
    assert slugs == ["ob", "zeta", "alpha", "mob", "ob", "can"], slugs
    html = qd.render(p, _NOW)
    assert html.count("ob@ocoron.com") >= 2, "the active account must appear at its return slot too"
    assert "is-return" in html, "the return slot must be a visibly distinct ghost row"
    assert "also #5" in html, "the active row must say which later slot is its return"


def test_a_healthy_active_account_has_no_return_slot(tmp_path, monkeypatch):
    """At 20% session the active account is not leaving; a return row would be noise."""
    qd = _load(tmp_path, monkeypatch)
    slugs = [e["slug"] for e in qd._queue(_queue_payload(active_five=20.0), _NOW)]
    assert slugs.count("ob") == 1
    assert "is-return" not in qd.render(_queue_payload(active_five=20.0), _NOW)


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
    assert "is-return" in qd.render(p, _NOW)
