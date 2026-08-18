#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/quota-dashboard.md, PORTS.md, docs/workstation/claude-account-rotation.md
#
# The account-quota dashboard: a localhost page showing every Claude account's session +
# weekly headroom, reset times, the active pointer, caps and warnings — the `--status` board
# rendered for a browser tab the operator leaves open.
#
# DESIGN — why there is no regeneration cron:
#   `claude_rotate.py --status --json` makes live API probes for fresh-token dirs. A */5 cron
#   would probe forever whether or not anyone is looking, and a self-refreshing browser tab
#   would probe on every reload. So the page is regenerated ON DEMAND, at most once per
#   QUOTA_DASH_MAX_AGE_S (default 240s): open tabs stay current, a closed tab costs nothing,
#   and refresh-spamming the page cannot multiply probe volume. The rendered page always
#   states the age of its own data — a stale render is visible, never silent.
#
# The server is stdlib-only, binds loopback by default, and is kept alive by cron
# (@reboot + a periodic --ensure). Read-only: it never writes outside its own output dir and
# never touches credential files (it shells the rotation CLI, which owns that contract).
"""Serve/generate the Claude account-quota dashboard (see module header)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROTATE_CLI = Path(
    os.getenv("QUOTA_DASH_ROTATE_CLI", "/opt/fabrik/scripts/sysadmin/claude_rotate.py")
)
OUT_DIR = Path(os.getenv("QUOTA_DASH_OUT_DIR", str(Path.home() / ".claude" / "quota-dashboard")))
HOST = os.getenv("QUOTA_DASH_HOST", "127.0.0.1")
PORT = int(os.getenv("QUOTA_DASH_PORT", "5051"))
MAX_AGE_S = float(os.getenv("QUOTA_DASH_MAX_AGE_S", "240"))
PROBE_TIMEOUT_S = float(os.getenv("QUOTA_DASH_PROBE_TIMEOUT_S", "60"))
REFRESH_S = int(os.getenv("QUOTA_DASH_REFRESH_S", "60"))

# The quota windows themselves. A cached reading older than its own window describes a window
# that has fully rolled over — reported as unknown, never as a reassuring percentage.
_FIVE_HOUR_S = 5 * 3600
_SEVEN_DAY_S = 7 * 86400

_HTML = OUT_DIR / "index.html"
_JSON = OUT_DIR / "quota.json"


def _probe() -> dict:
    """One `--status --json` run. Raises on failure — the caller decides fallback."""
    proc = subprocess.run(
        [sys.executable, str(ROTATE_CLI), "--status", "--json"],
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"rotate CLI exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout)


def _fmt_reset(epoch: float | None) -> str:
    if not epoch:
        return "—"
    dt = datetime.fromtimestamp(float(epoch)).astimezone()
    delta = float(epoch) - time.time()
    if delta <= 0:
        return dt.strftime("%a %d %b %H:%M") + " (due)"
    hours = delta / 3600.0
    left = f"{hours:.0f}h" if hours >= 1 else f"{delta / 60:.0f}m"
    if hours >= 24:
        left = f"{hours / 24:.1f}d"
    return f"{dt.strftime('%a %d %b %H:%M')} · in {left}"


def _fmt_age(age_s: float | None) -> str:
    if age_s is None:
        return ""
    h = age_s / 3600.0
    return f"cached {h:.0f}h ago" if h >= 1 else f"cached {age_s / 60:.0f}m ago"


def _bar(remaining: float, tone: str) -> str:
    return f'<div class="bar"><span class="fill {tone}" style="width:{max(0.0, min(100.0, remaining)):.1f}%"></span></div>'


def _tone(remaining: float) -> str:
    if remaining <= 5:
        return "crit"
    if remaining <= 25:
        return "warn"
    return "ok"


def _row(acct: dict, active: str | None) -> str:
    email = str(acct.get("email", "?"))
    slug = (acct.get("slugs") or ["?"])[0]
    is_active = bool(active) and slug == active
    five = acct.get("five_hour") or {}
    seven = acct.get("seven_day") or {}
    s_used = five.get("utilization")
    w_used = seven.get("utilization")
    s_left = 100.0 - float(s_used) if s_used is not None else None
    w_left = 100.0 - float(w_used) if w_used is not None else None
    cap = acct.get("weekly_cap")
    cap_walled = bool(acct.get("cap_walled"))
    walled = w_used is not None and float(w_used) >= 100.0
    stale = _fmt_age(acct.get("age_s")) if acct.get("source") == "cache" else ""

    badges = []
    if is_active:
        badges.append('<span class="badge active">ACTIVE</span>')
    if cap is not None:
        badges.append(f'<span class="badge cap">cap {int(cap)}%</span>')
    if cap_walled:
        badges.append('<span class="badge crit">RESERVED — fleet excluded</span>')
    elif walled:
        badges.append('<span class="badge crit">WALLED</span>')
    if stale:
        badges.append(f'<span class="badge stale">{escape(stale)}</span>')

    def cell(
        left: float | None, used: float | None, reset: float | None, window_s: float | None = None
    ) -> str:
        if left is None:
            return '<td class="num muted">no reading<br><span class="sub">—</span></td>'
        # A cached reading OLDER than the window it describes measures a window that has since
        # rolled over — so the NUMBER is not evidence. But the value is still derivable: an
        # account that is not the active pointer cannot be burning FLEET quota (no session binds
        # to it), so its rolled-over window is empty by construction. Say that, rather than
        # printing an unearned percentage ("plenty free" — the permanently-green class) or a
        # useless "unknown". The one blind spot is the operator's own claude.ai browser use,
        # which no probe of ours can see — surfaced on capped accounts, which exist for exactly
        # that reason.
        age = acct.get("age_s")
        if (
            acct.get("source") == "cache"
            and window_s
            and isinstance(age, (int, float))
            and age >= window_s
        ):
            blind = (
                " · browser use is not visible here" if acct.get("weekly_cap") is not None else ""
            )
            note = (
                f"idle — not the active pointer, so no fleet usage since this window rolled{blind}"
                if not is_active
                else f"last read {escape(_fmt_age(age))}, older than the "
                f"{window_s / 3600:.0f}h window — re-reads on next use"
            )
            label = "idle" if not is_active else "unknown"
            tone_i = "ok" if not is_active else "warn"
            return (
                f'<td class="num"><span class="pct {tone_i}">{label}</span>'
                f"{_bar(100.0 if not is_active else 0.0, tone_i)}"
                f'<span class="sub">{note}</span></td>'
            )
        tone = _tone(left)
        return (
            f'<td class="num"><span class="pct {tone}">{left:.0f}%</span> left'
            f"{_bar(left, tone)}"
            f'<span class="sub">{used:.0f}% used · resets {escape(_fmt_reset(reset))}</span></td>'
        )

    return (
        f'<tr class="{"is-active" if is_active else ""}">'
        f'<td class="acct"><strong>{escape(email)}</strong><span class="sub">{escape(slug)}</span>'
        f'<div class="badges">{"".join(badges)}</div></td>'
        f"{cell(s_left, s_used, five.get('resets_at_epoch'), _FIVE_HOUR_S)}"
        f"{cell(w_left, w_used, seven.get('resets_at_epoch'), _SEVEN_DAY_S)}"
        "</tr>"
    )


def render(payload: dict, generated_at: float, error: str | None = None) -> str:
    accounts = sorted(
        payload.get("accounts") or [],
        key=lambda a: (100.0 - float((a.get("seven_day") or {}).get("utilization") or 0.0)),
        reverse=True,
    )
    active = payload.get("active")
    warns = payload.get("fleet_warnings") or []
    pause = payload.get("pause")
    gen = datetime.fromtimestamp(generated_at).astimezone().strftime("%a %d %b %Y · %H:%M:%S %Z")

    banner = ""
    if error:
        banner = (
            f'<div class="banner crit">Live probe failed — showing the last good reading. '
            f"{escape(error)}</div>"
        )
    if pause == "marker":
        banner += '<div class="banner warn">Auto-rotation is PAUSED by the operator marker.</div>'
    elif pause == "error":
        banner += (
            '<div class="banner crit">Pause state unreadable — rotation is failing closed.</div>'
        )
    if not accounts:
        banner += '<div class="banner warn">No fleet accounts reporting yet.</div>'

    warn_html = ""
    if warns:
        items = "".join(f"<li>{escape(str(w))}</li>" for w in warns)
        warn_html = f'<section class="warns"><h2>Warnings</h2><ul>{items}</ul></section>'

    rows = "".join(_row(a, active) for a in accounts)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude quota — {escape(str(active or "no active account"))}</title>
<style>
 :root {{ color-scheme: light dark;
   --bg:#f6f7f9; --card:#fff; --fg:#14161a; --sub:#666e7a; --line:#e3e6ea;
   --ok:#1a9d5a; --warn:#c47f14; --crit:#c8402f; --accent:#3b6fd4; }}
 @media (prefers-color-scheme: dark) {{ :root {{
   --bg:#0f1216; --card:#171b21; --fg:#e8ecf1; --sub:#98a1ae; --line:#242a33;
   --ok:#3ecf8e; --warn:#e8b04b; --crit:#ff6b57; --accent:#6f9bff; }} }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; padding:24px; background:var(--bg); color:var(--fg);
   font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
 .wrap {{ max-width:980px; margin:0 auto; }}
 header {{ display:flex; flex-wrap:wrap; gap:12px; align-items:baseline;
   justify-content:space-between; margin-bottom:18px; }}
 h1 {{ font-size:20px; margin:0; font-weight:650; }}
 h1 .who {{ color:var(--accent); }}
 .stamp {{ color:var(--sub); font-size:13px; }}
 .banner {{ padding:10px 14px; border-radius:8px; margin-bottom:12px; font-size:14px; }}
 .banner.warn {{ background:color-mix(in srgb, var(--warn) 16%, transparent); border:1px solid var(--warn); }}
 .banner.crit {{ background:color-mix(in srgb, var(--crit) 16%, transparent); border:1px solid var(--crit); }}
 table {{ width:100%; border-collapse:separate; border-spacing:0; background:var(--card);
   border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
 th, td {{ padding:14px 16px; text-align:left; vertical-align:top;
   border-bottom:1px solid var(--line); }}
 thead th {{ font-size:12px; letter-spacing:.06em; text-transform:uppercase;
   color:var(--sub); font-weight:600; background:transparent; }}
 tbody tr:last-child td {{ border-bottom:none; }}
 tr.is-active {{ background:color-mix(in srgb, var(--accent) 8%, transparent); }}
 .acct strong {{ display:block; font-size:15px; }}
 .sub {{ display:block; color:var(--sub); font-size:12.5px; margin-top:3px; }}
 .num {{ width:32%; }}
 .pct {{ font-size:26px; font-weight:680; letter-spacing:-.02em; }}
 .pct.ok {{ color:var(--ok); }} .pct.warn {{ color:var(--warn); }} .pct.crit {{ color:var(--crit); }}
 .muted {{ color:var(--sub); }}
 .bar {{ height:6px; border-radius:99px; background:var(--line); margin:8px 0 4px; overflow:hidden; }}
 .fill {{ display:block; height:100%; border-radius:99px; }}
 .fill.ok {{ background:var(--ok); }} .fill.warn {{ background:var(--warn); }} .fill.crit {{ background:var(--crit); }}
 .badges {{ display:flex; flex-wrap:wrap; gap:5px; margin-top:7px; }}
 .badge {{ font-size:11px; padding:2px 7px; border-radius:99px; border:1px solid var(--line);
   color:var(--sub); white-space:nowrap; }}
 .badge.active {{ border-color:var(--accent); color:var(--accent); font-weight:650; }}
 .badge.cap {{ border-color:var(--accent); color:var(--accent); }}
 .badge.crit {{ border-color:var(--crit); color:var(--crit); }}
 .warns {{ margin-top:18px; background:var(--card); border:1px solid var(--line);
   border-radius:12px; padding:14px 18px; }}
 .warns h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em;
   color:var(--sub); margin:0 0 8px; }}
 .warns ul {{ margin:0; padding-left:18px; }} .warns li {{ margin:4px 0; font-size:13.5px; }}
 footer {{ margin-top:16px; color:var(--sub); font-size:12.5px; }}
 @media (max-width:720px) {{ .num {{ width:auto; }} th:nth-child(1) {{ width:40%; }} }}
</style></head><body><div class="wrap">
<header>
  <h1>Claude account quota — active: <span class="who">{escape(str(active or "none"))}</span></h1>
  <div class="stamp">updated {escape(gen)} · refreshes every {REFRESH_S}s ·
    <span id="conn">live</span></div>
</header>
{banner}
<table>
  <thead><tr><th>Account</th><th>Session (5h) remaining</th><th>Weekly remaining</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
{warn_html}
<footer>Rotation flips the active pointer at 95% on either window, or at an account's
configured cap. Data regenerates on view, at most once every {int(MAX_AGE_S)}s.</footer>
</div><script>
/* Health-gated auto-refresh (2026-08-18 — replaces meta http-equiv=refresh). The meta tag
   died on the first failed load after a WSL restart: the browser's error page carries no
   refresh tag, so the tab froze until a manual F5 — the operator hit this twice. This
   reloader NEVER navigates on failure: it polls /health and reloads only when the server
   answers, so the tab rides out server restarts, WSL restarts, and host hibernation, and
   self-heals the moment the box is back. */
(function () {{
  var conn = document.getElementById("conn");
  setInterval(function () {{
    fetch("/health", {{cache: "no-store"}})
      .then(function (r) {{ if (r.ok) location.reload(); }})
      .catch(function () {{
        if (conn) {{ conn.textContent = "server unreachable — retrying"; }}
      }});
  }}, {REFRESH_S} * 1000);
}})();
</script>
</body></html>"""


def generate() -> str:
    """Probe + write index.html/quota.json. Falls back to the last good payload on error."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    error = None
    try:
        payload = _probe()
        _JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    except Exception as exc:  # transport/CLI/JSON — degrade visibly, never blank the page
        error = f"{type(exc).__name__}: {exc}"[:200]
        try:
            payload = json.loads(_JSON.read_text(encoding="utf-8"))
        except OSError:
            payload = {}
        except ValueError:
            payload = {}
        sys.stderr.write(f"quota_dashboard: probe failed ({error})\n")
    html = render(payload, time.time(), error)
    _HTML.write_text(html, encoding="utf-8")
    return html


def _fresh_html() -> str:
    """Cached HTML when young enough, else a regeneration. Bounds probe volume."""
    try:
        age = time.time() - _HTML.stat().st_mtime
        if age < MAX_AGE_S:
            return _HTML.read_text(encoding="utf-8")
    except OSError:
        pass
    return generate()


class _Handler(BaseHTTPRequestHandler):
    server_version = "quota-dashboard"

    def do_GET(self) -> None:  # noqa: N802 (stdlib interface)
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body, ctype = _fresh_html().encode("utf-8"), "text/html; charset=utf-8"
        elif path == "/quota.json":
            _fresh_html()  # refresh the payload alongside the page
            try:
                body = _JSON.read_bytes()
            except OSError:
                body = b"{}"
            ctype = "application/json"
        elif path == "/health":
            body, ctype = b"ok", "text/plain"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_a) -> None:  # keep cron logs clean
        return


def serve() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), _Handler)
    sys.stderr.write(f"quota_dashboard: serving http://{HOST}:{PORT}/\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def ensure() -> int:
    """Start the server unless something already answers on the port (cron keepalive)."""
    import socket

    with socket.socket() as s:
        s.settimeout(2.0)
        if s.connect_ex((HOST, PORT)) == 0:
            return 0  # already up
    log = Path(os.getenv("QUOTA_DASH_LOG", str(Path.home() / ".claude" / "quota-dashboard.log")))
    with open(log, "a", encoding="utf-8") as fh:
        subprocess.Popen(  # noqa: S603 — fixed argv, no shell
            [sys.executable, str(Path(__file__).resolve()), "--serve"],
            stdout=fh,
            stderr=fh,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="regenerate the page and exit")
    g.add_argument("--serve", action="store_true", help="run the localhost server (foreground)")
    g.add_argument("--ensure", action="store_true", help="start the server if it is not running")
    args = ap.parse_args(argv)
    if args.once:
        generate()
        sys.stdout.write(f"{_HTML}\n")
        return 0
    if args.ensure:
        return ensure()
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
