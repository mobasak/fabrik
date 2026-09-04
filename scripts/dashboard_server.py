#!/usr/bin/env python3
# AFTER-EDIT: scripts/gen_dashboard.py
"""LIVE external-services dashboard — a tiny localhost server that queries the registry on every
load (auto-refresh 30s). Unlike gen_dashboard.py (a static snapshot), this is always current.

    python scripts/dashboard_server.py            # http://127.0.0.1:8770
    python scripts/dashboard_server.py 8888        # custom port

Binds 0.0.0.0 by default (a Windows browser reaches the WSL server through NAT — override with
DASHBOARD_HOST=127.0.0.1); the page is metadata + a value_sha256 COUNT — never a raw secret, and
it renders through gen_dashboard's own escaper/scheme-gate helpers (one source, FC4).
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:  # once (B65-7, FF1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_dashboard  # noqa: E402 - reuse CSS + the live DB query (load)

PORT = 8770  # the CLI argument is read in main(), never at import: an importer (a test, a tool) carries its own argv (FC4)
# Bind all interfaces by default so a Windows browser reaches the WSL server (a 127.0.0.1-only
# bind is often unreachable through WSL2 NAT). Override with DASHBOARD_HOST=127.0.0.1 to restrict.
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")  # noqa: S104 - metadata-only, single-operator dev box

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>External Services &amp; Credentials</title>
<style>__CSS__</style></head><body>
<div class="wrap">
  <header><h1>External Services &amp; Credentials</h1>
    <span class="sub" id="meta">loading…</span></header>
  <div class="stats" id="stats"></div>
  <div class="bar">
    <input id="q" type="search" placeholder="Filter by provider, project, account…" aria-label="Search">
    <select id="fcat" aria-label="Category"><option value="">All categories</option></select>
    <select id="fcost" aria-label="Cost"><option value="">All costs</option>
      <option>free</option><option>freemium</option><option>paid</option><option>self-host</option>
      <option value="?">? (triage)</option></select>
  </div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th data-k="provider">Provider</th><th data-k="category">Category</th><th data-k="cost">Cost</th>
    <th data-k="status">Status</th><th data-k="credit">Credit</th><th data-k="renews">Renews</th>
    <th data-k="price">Price</th><th data-k="keys" class="num">Keys</th><th data-k="account">Account</th>
    <th data-k="projects">Used by</th></tr></thead><tbody id="tb"></tbody></table></div>
  <footer>Live view of the fabrik_services registry · auto-refresh 30s · no secret values · ⚠ credit = last successful fetch older than __STALE_H__ h</footer>
</div>
<script>
let DATA=[],sortK='category',sortAsc=true;
const $=id=>document.getElementById(id);
__HELPERS__
function stats(){
  const n=DATA.length,cats=[...new Set(DATA.map(r=>r.category))].sort(),
    proj=new Set(DATA.flatMap(r=>r.projects)),bc=c=>DATA.filter(r=>r.cost===c).length;
  $('meta').textContent=n+' providers · '+proj.size+' projects · live '+new Date().toLocaleTimeString();
  const S=[[n,'services'],[cats.length,'categories'],[proj.size,'projects'],
    [bc('paid')+bc('freemium'),'paid / freemium'],[bc('free')+bc('self-host'),'free / self-host'],
    [DATA.filter(r=>r.credit&&!r.credit.startsWith('⚠')).length,'credit tracked'],[DATA.filter(r=>r.credit.startsWith('⚠')).length,'credit stale'],[DATA.filter(r=>r.renews).length,'renewals set'],
    [DATA.filter(r=>r.category==='?').length,'need triage'],[DATA.reduce((a,r)=>a+(r.unattributed||0),0),'unattributed keys']];
  $('stats').innerHTML=S.map(x=>'<div class="stat"><div class="n">'+x[0]+'</div><div class="l">'+x[1]+'</div></div>').join('');
  const cur=$('fcat').value;
  $('fcat').innerHTML='<option value="">All categories</option>'+cats.map(c=>'<option value="'+esc(c)+'"'+(c===cur?' selected':'')+'>'+esc(c)+'</option>').join('');
}
function render(){
  const term=$('q').value.toLowerCase(),fc=$('fcat').value,fk=$('fcost').value;
  let rows=DATA.filter(r=>(!fc||r.category===fc)&&(!fk||r.cost===fk)&&
    (!term||(r.provider+' '+r.account+' '+r.projects.join(' ')+' '+r.category).toLowerCase().includes(term)));
  rows.sort((a,b)=>{let x=a[sortK],y=b[sortK];if(sortK==='keys'){x=+x;y=+y;}else{x=(''+x).toLowerCase();y=(''+y).toLowerCase();}return (x<y?-1:x>y?1:0)*(sortAsc?1:-1);});
  let out='',cat=null;
  for(const r of rows){
    if(sortK==='category'&&r.category!==cat){cat=r.category;out+='<tr class="catrow"><td colspan="10">'+esc(cat)+'</td></tr>';}
    const url=href(r.url)?'<a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.provider)+'</a>':esc(r.provider);
    out+='<tr><td class="prov">'+url+'</td>'+cell(r.category)+'<td>'+cpill(r.cost)+'</td><td>'+cpill(r.status)+'</td>'
      +cell(r.credit,'num mono')+cell(r.renews,'mono')+cell(r.price,'num mono')+keysCell(r)
      +cell(r.account,'mono')+'<td class="projects">'+(r.projects.length?esc(r.projects.join(', ')):'<span class=empty>—</span>')+'</td></tr>';
  }
  $('tb').innerHTML=out||'<tr><td colspan="10" class="empty" style="padding:24px;text-align:center">No services match.</td></tr>';
}
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(sortK===k)sortAsc=!sortAsc;else{sortK=k;sortAsc=true;}document.querySelectorAll('th').forEach(h=>h.removeAttribute('aria-sort'));th.setAttribute('aria-sort',sortAsc?'ascending':'descending');render();});
['q','fcat','fcost'].forEach(id=>$(id).oninput=render);
function refresh(){fetch('/api/services').then(r=>r.json()).then(d=>{DATA=d;stats();render();}).catch(()=>{$('meta').textContent='registry unreachable';});}
refresh();setInterval(refresh,30000);
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    timeout = 30  # a client that opens a socket and stops no longer holds the server (FE1)

    def log_message(self, *_a):
        pass

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "X-Content-Type-Options", "nosniff"
        )  # a 0.0.0.0 bind: the JSON carries model-authored strings (FD7)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        try:
            if self.path.startswith("/api/services"):
                body, ctype = json.dumps(gen_dashboard.load()).encode("utf-8"), "application/json"
            else:
                body, ctype = (
                    PAGE.replace("__CSS__", gen_dashboard.CSS)
                    .replace("__HELPERS__", gen_dashboard.HELPERS)
                    .replace("__STALE_H__", str(gen_dashboard.STALE_AFTER_H))
                    .encode("utf-8"),
                    "text/html; charset=utf-8",
                )
        except Exception as exc:  # noqa: BLE001 - never crash the server on one bad request
            # the cause goes to the console, NEVER onto the wire: `send_error` writes the message
            # into the status line unsanitised — libpq's own text carries a newline (response
            # splitting), a `—`/`⚠` raised UnicodeEncodeError INSIDE the except (zero bytes sent),
            # and the WireGuard host + role name reached every LAN client (FD7)
            try:
                print(
                    f"dashboard: {exc.__class__.__name__}: {_safe(exc)}",
                    file=sys.stderr,
                )
            finally:
                try:
                    self.send_error(
                        500, "registry query failed"
                    )  # even when str(exc) itself raises (FE1)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client left before the 500 (a closed tab during the refresh) — the FE1 guard covered `_send` only; this path printed a 17-frame stdlib traceback per aborted request (FF1)
            return
        try:
            self._send(body, ctype)
        except (BrokenPipeError, ConnectionResetError):
            return  # the client left mid-response (a closed tab on the 30 s refresh): not a registry failure, not a traceback (FE1)


def _safe(exc: BaseException) -> str:
    try:
        return " ".join(str(exc).split())[:300]
    except Exception:  # noqa: BLE001 - a message that cannot be rendered is still a 500
        return "<str() failed>"


def _port(value: str) -> int:
    """`choices=range(1, 65536)` printed every choice — a 447 KB error for port 0 (FE1)."""
    import argparse  # noqa: PLC0415

    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"PORT must be an integer, got {value!r}") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"PORT must be 1-65535, got {port}")
    return port


class Server(socketserver.ThreadingTCPServer):
    """One stalled client no longer blocks every other client (a 0.0.0.0 bind; FE1). IPv4 only:
    `DASHBOARD_HOST=::1` cannot bind (the server family is AF_INET) — say so rather than grow a
    second family (FF1)."""

    allow_reuse_address = True
    daemon_threads = True


def main(argv: list[str] | None = None) -> int:
    import argparse  # noqa: PLC0415

    ap = argparse.ArgumentParser(
        description="Live external-services dashboard (reads the registry DB)."
    )
    ap.add_argument(
        "port", nargs="?", type=_port, default=PORT, metavar="PORT"
    )  # `abc`/`-1`/`99999` were tracebacks (FD7); a one-line bound, never a 447 KB choices dump (FE1)
    port = ap.parse_args(sys.argv[1:] if argv is None else argv).port
    try:
        srv = Server((HOST, port), Handler)
    except OSError as exc:  # a port in use or below 1024 without privilege was a traceback (FE1)
        print(f"ERROR: cannot bind {HOST}:{port} ({exc.strerror or exc})", file=sys.stderr)
        return 1
    with srv:
        url = f"http://localhost:{port}"  # noqa - user-facing message, not a backing-service host
        print(f"Live dashboard on {HOST}:{port} — open {url}  (Ctrl-C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
