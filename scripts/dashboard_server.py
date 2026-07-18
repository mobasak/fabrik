#!/usr/bin/env python3
# AFTER-EDIT: scripts/gen_dashboard.py
"""LIVE external-services dashboard — a tiny localhost server that queries the registry on every
load (auto-refresh 30s). Unlike gen_dashboard.py (a static snapshot), this is always current.

    python scripts/dashboard_server.py            # http://127.0.0.1:8770
    python scripts/dashboard_server.py 8888        # custom port

Localhost-only (127.0.0.1). Serves metadata + a value_sha256 COUNT — never a raw secret.
"""

from __future__ import annotations

import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_dashboard  # noqa: E402 - reuse CSS + the live DB query (load)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8770
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
  <footer>Live view of the fabrik_services registry · auto-refresh 30s · no secret values</footer>
</div>
<script>
let DATA=[],sortK='category',sortAsc=true;
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cpill=v=>{const k=v==='?'?'unknown':v.replace('_','-');return '<span class="pill c-'+k+'">'+esc(v)+'</span>';};
const cell=(v,cls)=>v?'<td class="'+(cls||'')+'">'+esc(v)+'</td>':'<td class="empty">—</td>';
function stats(){
  const n=DATA.length,cats=[...new Set(DATA.map(r=>r.category))].sort(),
    proj=new Set(DATA.flatMap(r=>r.projects)),bc=c=>DATA.filter(r=>r.cost===c).length;
  $('meta').textContent=n+' providers · '+proj.size+' projects · live '+new Date().toLocaleTimeString();
  const S=[[n,'services'],[cats.length,'categories'],[proj.size,'projects'],
    [bc('paid')+bc('freemium'),'paid / freemium'],[bc('free')+bc('self-host'),'free / self-host'],
    [DATA.filter(r=>r.credit).length,'credit tracked'],[DATA.filter(r=>r.renews).length,'renewals set'],
    [DATA.filter(r=>r.category==='?').length,'need triage']];
  $('stats').innerHTML=S.map(x=>'<div class="stat"><div class="n">'+x[0]+'</div><div class="l">'+x[1]+'</div></div>').join('');
  const cur=$('fcat').value;
  $('fcat').innerHTML='<option value="">All categories</option>'+cats.map(c=>'<option'+(c===cur?' selected':'')+'>'+esc(c)+'</option>').join('');
}
function render(){
  const term=$('q').value.toLowerCase(),fc=$('fcat').value,fk=$('fcost').value;
  let rows=DATA.filter(r=>(!fc||r.category===fc)&&(!fk||r.cost===fk)&&
    (!term||(r.provider+' '+r.account+' '+r.projects.join(' ')+' '+r.category).toLowerCase().includes(term)));
  rows.sort((a,b)=>{let x=a[sortK],y=b[sortK];if(sortK==='keys'){x=+x;y=+y;}else{x=(''+x).toLowerCase();y=(''+y).toLowerCase();}return (x<y?-1:x>y?1:0)*(sortAsc?1:-1);});
  let out='',cat=null;
  for(const r of rows){
    if(sortK==='category'&&r.category!==cat){cat=r.category;out+='<tr class="catrow"><td colspan="10">'+esc(cat)+'</td></tr>';}
    const url=r.url&&r.url!=='?'?'<a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.provider)+'</a>':esc(r.provider);
    out+='<tr><td class="prov">'+url+'</td>'+cell(r.category)+'<td>'+cpill(r.cost)+'</td><td>'+cpill(r.status)+'</td>'
      +cell(r.credit,'num mono')+cell(r.renews,'mono')+cell(r.price,'num mono')+'<td class="num mono">'+r.keys+'</td>'
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
    def log_message(self, *_a):
        pass

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        try:
            if self.path.startswith("/api/services"):
                self._send(json.dumps(gen_dashboard.load()).encode("utf-8"), "application/json")
            else:
                self._send(
                    PAGE.replace("__CSS__", gen_dashboard.CSS).encode("utf-8"),
                    "text/html; charset=utf-8",
                )
        except Exception as exc:  # noqa: BLE001 - never crash the server on one bad request
            self.send_error(500, str(exc)[:120])


def main() -> int:
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), Handler) as srv:
        url = f"http://localhost:{PORT}"  # noqa - user-facing message, not a backing-service host
        print(f"Live dashboard on {HOST}:{PORT} — open {url}  (Ctrl-C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
