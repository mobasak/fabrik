#!/usr/bin/env python3
# AFTER-EDIT: .fabrik/liveness-registry.json docs/reference/external-services-registry.md tests/test_external_services_chain.py
"""Render the external-services registry (fabrik_services) as a self-contained HTML dashboard.

Reads services/api_keys/credit_snapshots/subscriptions and emits ONE static HTML file (data
embedded, inline CSS/JS, no external requests) — a scan-first control panel: summary stats,
then a sortable/filterable table by capability category. ZERO secrets: metadata + a value_sha256
COUNT only, never a raw key. Body-content only (no <html>/<head>/<body>) so it publishes as an
Artifact cleanly.

    python scripts/gen_dashboard.py [out.html]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import registry_db  # noqa: E402


def load() -> list[dict]:
    conn = registry_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, provider, category, cost_tier, url, status FROM services")
            svc = {
                r[0]: {
                    "provider": r[1],
                    "category": r[2] or "?",
                    "cost": r[3] or "?",
                    "url": r[4] or "",
                    "status": r[5] or "?",
                    "keys": 0,
                    "projects": set(),
                    "account": "",
                    "credit": "",
                    "renews": "",
                    "price": "",
                }
                for r in cur.fetchall()
            }
            cur.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
                "AND table_name='api_keys' AND column_name='kind'"
            )
            has_kind = (
                cur.fetchone() is not None
            )  # a registry never synced by the new registry_sync
            cur.execute(
                "SELECT service_id, used_by_projects, account_email, "
                + ("kind" if has_kind else "'credential'")
                + " FROM api_keys"
            )
            for sid, projects, email, kind in cur.fetchall():
                s = svc.get(sid)
                if not s:
                    continue
                if kind == "credential":  # a code call-site row proves USE, never a key
                    s["keys"] += 1
                s["projects"].update(projects or [])
                if email and not s["account"]:
                    s["account"] = email
            cur.execute(
                "SELECT DISTINCT ON (service_id) service_id, balance, unit "
                "FROM credit_snapshots ORDER BY service_id, fetched_at DESC"
            )
            for sid, bal, unit in cur.fetchall():
                if sid in svc and bal is not None:
                    svc[sid]["credit"] = f"{bal:g} {unit or ''}".strip()
            cur.execute("SELECT service_id, price, currency, renews_on FROM subscriptions")
            for sid, price, curr, renews in cur.fetchall():
                s = svc.get(sid)
                if not s:
                    continue
                if renews:
                    s["renews"] = str(renews)
                if price is not None:
                    s["price"] = f"{price:g} {curr or ''}".strip()
    finally:
        conn.close()
    rows = sorted(svc.values(), key=lambda r: (r["category"], r["provider"]))
    for r in rows:
        r["projects"] = sorted(r["projects"])
    return rows


CSS = """
:root{--bg:#f6f7f9;--surface:#fff;--surface-2:#eef1f4;--text:#161a20;--muted:#5f6875;--border:#e2e6ea;
--accent:#0d9488;--accent-weak:#0d948815;--free:#15803d;--freemium:#1d4ed8;--paid:#b45309;
--selfhost:#475569;--unknown:#7c3aed;--shadow:0 1px 2px #0000000d,0 1px 3px #0000000a;}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--surface:#161a21;--surface-2:#1d232c;--text:#e7eaee;
--muted:#98a1ad;--border:#262d38;--accent:#2dd4bf;--accent-weak:#2dd4bf1a;--free:#4ade80;--freemium:#60a5fa;
--paid:#fbbf24;--selfhost:#94a3b8;--unknown:#c084fc;--shadow:0 1px 2px #00000040;}}
:root[data-theme="light"]{--bg:#f6f7f9;--surface:#fff;--surface-2:#eef1f4;--text:#161a20;--muted:#5f6875;
--border:#e2e6ea;--accent:#0d9488;--accent-weak:#0d948815;--free:#15803d;--freemium:#1d4ed8;--paid:#b45309;
--selfhost:#475569;--unknown:#7c3aed;--shadow:0 1px 2px #0000000d,0 1px 3px #0000000a;}
:root[data-theme="dark"]{--bg:#0e1116;--surface:#161a21;--surface-2:#1d232c;--text:#e7eaee;--muted:#98a1ad;
--border:#262d38;--accent:#2dd4bf;--accent-weak:#2dd4bf1a;--free:#4ade80;--freemium:#60a5fa;--paid:#fbbf24;
--selfhost:#94a3b8;--unknown:#c084fc;--shadow:0 1px 2px #00000040;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:32px 24px 64px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:12px}
h1{font-size:24px;font-weight:680;letter-spacing:-.01em;margin:0}
.sub{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow)}
.stat .n{font-size:26px;font-weight:660;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.stat .l{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-top:2px}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:18px 0 12px}
.bar input,.bar select{background:var(--surface);color:var(--text);border:1px solid var(--border);
border-radius:9px;padding:8px 11px;font-size:13px;font-family:inherit}
.bar input{flex:1;min-width:180px}
.bar input:focus,.bar select:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:transparent}
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:var(--surface);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--border);white-space:nowrap}
th{position:sticky;top:0;background:var(--surface-2);font-size:11px;text-transform:uppercase;
letter-spacing:.05em;color:var(--muted);cursor:pointer;user-select:none;font-weight:600}
th:hover{color:var(--accent)}
th[aria-sort="ascending"]::after{content:" ▲";color:var(--accent)}
th[aria-sort="descending"]::after{content:" ▼";color:var(--accent)}
tbody tr:hover{background:var(--accent-weak)}
td.num{font-variant-numeric:tabular-nums;text-align:right}
td.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.prov{font-weight:600;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600}
.c-free{color:var(--free);background:color-mix(in srgb,var(--free) 13%,transparent)}
.c-freemium{color:var(--freemium);background:color-mix(in srgb,var(--freemium) 13%,transparent)}
.c-paid{color:var(--paid);background:color-mix(in srgb,var(--paid) 15%,transparent)}
.c-self-host{color:var(--selfhost);background:color-mix(in srgb,var(--selfhost) 15%,transparent)}
.c-unknown,.c-retiring{color:var(--unknown);background:color-mix(in srgb,var(--unknown) 14%,transparent)}
.c-active{color:var(--free);background:color-mix(in srgb,var(--free) 12%,transparent)}
.projects{color:var(--muted);font-size:12px;white-space:normal;max-width:260px}
.empty{color:var(--muted);opacity:.5}
.catrow td{background:var(--surface-2);font-weight:660;font-size:11px;text-transform:uppercase;
letter-spacing:.06em;color:var(--muted)}
footer{color:var(--muted);font-size:12px;margin-top:20px;text-align:center}
"""

SCRIPT = r"""<script>
const DATA=__DATA__;
const tb=document.getElementById('tb'),q=document.getElementById('q'),
  fcat=document.getElementById('fcat'),fcost=document.getElementById('fcost');
let sortK='category',sortAsc=true;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));  // `'` too — a single-quoted attribute must never be the day this bites (BB9)
const href=u=>/^https?:\/\//i.test(String(u||''))?u:null;  // render-time scheme gate: a hand-edited or pre-guard `javascript:` url is never a live link (AS5)
const cpill=v=>{const k=v==='?'?'unknown':String(v).replace(/[^A-Za-z0-9]+/g,'-');return '<span class="pill c-'+k+'">'+esc(v)+'</span>';};  // class token restricted: cost/status are model-authored (AP1)
const cell=(v,cls)=>v?'<td class="'+(cls||'')+'">'+esc(v)+'</td>':'<td class="empty">—</td>';
function render(){
  const term=q.value.toLowerCase(),fc=fcat.value,fk=fcost.value;
  let rows=DATA.filter(r=>(!fc||r.category===fc)&&(!fk||r.cost===fk)&&
    (!term||(r.provider+' '+r.account+' '+r.projects.join(' ')+' '+r.category).toLowerCase().includes(term)));
  rows.sort((a,b)=>{let x=a[sortK],y=b[sortK];if(sortK==='keys'){x=+x;y=+y;}
    else{x=(''+x).toLowerCase();y=(''+y).toLowerCase();}return (x<y?-1:x>y?1:0)*(sortAsc?1:-1);});
  let out='',cat=null;
  for(const r of rows){
    if(sortK==='category'&&r.category!==cat){cat=r.category;out+='<tr class="catrow"><td colspan="10">'+esc(cat)+'</td></tr>';}
    const url=href(r.url)?'<a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.provider)+'</a>':esc(r.provider);
    out+='<tr><td class="prov">'+url+'</td>'+cell(r.category)+'<td>'+cpill(r.cost)+'</td>'
      +'<td>'+cpill(r.status)+'</td>'+cell(r.credit,'num mono')+cell(r.renews,'mono')+cell(r.price,'num mono')
      +'<td class="num mono">'+r.keys+'</td>'+cell(r.account,'mono')
      +'<td class="projects">'+(r.projects.length?esc(r.projects.join(', ')):'<span class=empty>—</span>')+'</td></tr>';
  }
  tb.innerHTML=out||'<tr><td colspan="10" class="empty" style="padding:24px;text-align:center">No services match.</td></tr>';
}
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{
  const k=th.dataset.k;if(sortK===k)sortAsc=!sortAsc;else{sortK=k;sortAsc=true;}
  document.querySelectorAll('th').forEach(h=>h.removeAttribute('aria-sort'));
  th.setAttribute('aria-sort',sortAsc?'ascending':'descending');render();});
[q,fcat,fcost].forEach(el=>el.oninput=render);
render();
</script>"""


def json_for_script(rows: list[dict]) -> str:
    """JSON that is safe INSIDE an inline `<script>`: `json.dumps` leaves `</script>` intact, and
    the registry's `provider`/`url` strings are model-authored (`classify_services` writes the pool
    model's answer to the catalog), so a `</script><script>…` in one of them would run in the
    operator's browser before the page's own `esc()` ever sees it (AM4). `\u003c` is valid JSON."""
    return (
        json.dumps(rows, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render(rows: list[dict]) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cats = sorted({r["category"] for r in rows})
    by_cost = {
        c: sum(1 for r in rows if r["cost"] == c) for c in ("free", "freemium", "paid", "self-host")
    }
    nproj = len({p for r in rows for p in r["projects"]})
    stats = [
        (len(rows), "services"),
        (len(cats), "categories"),
        (nproj, "projects"),
        (by_cost["paid"] + by_cost["freemium"], "paid / freemium"),
        (by_cost["free"] + by_cost["self-host"], "free / self-host"),
        (sum(1 for r in rows if r["credit"]), "credit tracked"),
        (sum(1 for r in rows if r["renews"]), "renewals set"),
        (sum(1 for r in rows if r["category"] == "?"), "need triage"),
    ]
    statcards = "".join(
        f'<div class="stat"><div class="n">{v}</div><div class="l">{html.escape(lbl)}</div></div>'
        for v, lbl in stats
    )
    cat_opts = "".join(f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in cats)
    body = f"""<div class="wrap">
  <header><h1>External Services &amp; Credentials</h1>
    <span class="sub">{len(rows)} providers · {nproj} projects · generated {now}</span></header>
  <div class="stats">{statcards}</div>
  <div class="bar">
    <input id="q" type="search" placeholder="Filter by provider, project, account…" aria-label="Search">
    <select id="fcat" aria-label="Category"><option value="">All categories</option>{cat_opts}</select>
    <select id="fcost" aria-label="Cost"><option value="">All costs</option>
      <option>free</option><option>freemium</option><option>paid</option><option>self-host</option>
      <option value="?">? (triage)</option></select>
  </div>
  <div class="tablewrap"><table id="t"><thead><tr>
    <th data-k="provider">Provider</th><th data-k="category">Category</th><th data-k="cost">Cost</th>
    <th data-k="status">Status</th><th data-k="credit">Credit</th><th data-k="renews">Renews</th>
    <th data-k="price">Price</th><th data-k="keys" class="num">Keys</th><th data-k="account">Account</th>
    <th data-k="projects">Used by</th></tr></thead><tbody id="tb"></tbody></table></div>
  <footer>Read-only view of the fabrik_services registry · no secret values (metadata + key hashes only)</footer>
</div>"""
    script = SCRIPT.replace("__DATA__", json_for_script(rows))
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>External Services &amp; Credentials</title>\n"
        f"<style>{CSS}</style></head>\n<body>\n{body}\n{script}\n</body></html>"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "out",
        nargs="?",
        default="external-services-dashboard.html",
        help="output path (default: ./external-services-dashboard.html)",
    )
    out = Path(
        ap.parse_args(argv).out
    )  # `--help` exits here — it used to WRITE a file named --help
    rows = load()
    tmp = out.with_name(out.name + ".tmp")  # atomic: the mtime is a liveness heartbeat, so a
    tmp.unlink(missing_ok=True)  # half-written file must never be fresh; no leftover either way
    try:
        tmp.write_text(render(rows), encoding="utf-8")
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)  # a failed write leaves nothing behind (AC14)
    print(f"wrote {out} — {len(rows)} services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
