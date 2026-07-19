#!/usr/bin/env python3
"""Generate a single-file HTML browser for ALL AI models in kilo_agents.db.

Reads the chat catalog (`agents`, 435 rows), embedding catalog
(`embedding_models`, 26 rows), per-category classifications
(`agent_categories`), today's route pins (`agent_roles`), and embedding
role pins (`embedding_roles`). Emits `models_browser.html` with the
data embedded as a JSON blob — open directly in a browser, no server,
no network calls.

Usage:
    python export_models_browser.py            # writes models_browser.html
    python export_models_browser.py --open     # also xdg-open it

Idempotent: re-run anytime to regenerate after the daily WSL pipeline
refreshes the DB.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
TEMPLATE_PATH = SCRIPT_DIR / "models_browser_template.html"
OUTPUT_PATH = SCRIPT_DIR / "models_browser.html"


def _fetch_chat_models(conn: sqlite3.Connection, db_path: Path) -> list[dict]:
    """Load every agents row + joined category list + today's role pins.

    `db_path` is threaded through so the coding-subagent overlay ranks against
    the SAME DB the chat rows come from — a `--db /some/other.db` CLI arg
    otherwise silently ranked against the ranker's own default and produced
    incoherent overlay data.
    """
    conn.row_factory = sqlite3.Row
    agents = [dict(r) for r in conn.execute("SELECT * FROM agents").fetchall()]

    # Coding-subagent overlay — single source of truth is
    # `rank_coding_subagents.rank_all()`. Never fork EXCLUDE_MODELS /
    # PROVIDER_PINS / BODY_HINTS.
    from rank_coding_subagents import (
        CODING_EXCLUDE_MODELS,
        CODING_PROVIDER_PINS,
        fmt_body_hint,
        rank_all,
    )

    ranked_by_id = {r["id"]: r for r in rank_all(db_path)}
    for a in agents:
        mid = a["id"]
        ranked = ranked_by_id.get(mid)
        a["code_subagent_candidate"] = ranked is not None
        a["code_fit_score"] = round(ranked["score"], 3) if ranked else None
        a["doc_code_grade"] = ranked["doc_grade"] if ranked else None
        a["code_excluded_reason"] = (
            "reasoning-only — returns 0 output tokens when reasoning is excluded"
            if mid in CODING_EXCLUDE_MODELS
            else None
        )
        a["code_provider_pin"] = (
            list(CODING_PROVIDER_PINS[mid]) if mid in CODING_PROVIDER_PINS else None
        )
        hint = fmt_body_hint(mid)
        a["code_body_hint"] = hint if hint != "—" else None

    # Categories per agent (multi-row → list).
    cats_by_agent: dict[str, list[str]] = {}
    for r in conn.execute(
        "SELECT agent_id, category FROM agent_categories ORDER BY category"
    ).fetchall():
        cats_by_agent.setdefault(r["agent_id"], []).append(r["category"])

    # Today's openrouter:* role pins per agent.
    roles_by_agent: dict[str, list[dict]] = {}
    for r in conn.execute(
        "SELECT agent_id, role, priority FROM agent_roles "
        "WHERE assigned_by='category_route_mapper' "
        "ORDER BY role, priority"
    ).fetchall():
        roles_by_agent.setdefault(r["agent_id"], []).append(
            {
                "role": r["role"],
                "priority": r["priority"],
            }
        )

    for a in agents:
        a["categories"] = cats_by_agent.get(a["id"], [])
        a["openrouter_pins"] = roles_by_agent.get(a["id"], [])
        a["kind"] = "chat"
    return agents


def _fetch_embedding_models(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    models = [dict(r) for r in conn.execute("SELECT * FROM embedding_models").fetchall()]

    roles_by_model: dict[str, list[dict]] = {}
    try:
        for r in conn.execute(
            "SELECT model_id, role, priority FROM embedding_roles ORDER BY role, priority"
        ).fetchall():
            roles_by_model.setdefault(r["model_id"], []).append(
                {
                    "role": r["role"],
                    "priority": r["priority"],
                }
            )
    except sqlite3.OperationalError:
        pass

    for m in models:
        m["embedding_pins"] = roles_by_model.get(m["id"], [])
        m["kind"] = "embedding"
        # Synthesize `cheapest_gateway` for embeddings (the embedding_models
        # table doesn't carry the column). Every priced embedding is
        # `direct` at its input_cost_per_m; free embeddings map to direct $0.
        price = m.get("input_cost_per_m")
        if price is not None and price >= 0:
            m["cheapest_gateway"] = "direct"
            m["cheapest_gateway_price"] = float(price)
    return models


def _fetch_local_models(conn: sqlite3.Connection) -> list[dict]:
    """Load locally-installed Ollama models. These run on the dev
    machine via the `ollama` daemon and are visible to the Kilo CLI's
    Ollama provider. Free at the API-cost layer but consume local
    VRAM/RAM (surfaced via the existing `vram_required_gb` column)."""
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM local_models").fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for r in rows:
        d = dict(r)
        d["kind"] = "local"
        d["provider"] = "ollama"
        d.setdefault("name", d.get("id"))
        d["input_cost_per_m"] = 0
        d["output_cost_per_m"] = 0
        # Surface the role pin if assigned
        if d.get("assigned_role"):
            d["embedding_pins"] = [
                {"role": d["assigned_role"], "priority": d.get("role_priority", 1)}
            ]
        out.append(d)
    return out


def _fetch_gpu_providers(conn: sqlite3.Connection) -> list[dict]:
    """Load every gpu_providers row. Ordered by $/hr ascending so the default view
    shows the cheapest H100 first — most operators pick GPU rentals on cost.
    """
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM gpu_providers ORDER BY usd_per_hour ASC").fetchall()
    except sqlite3.OperationalError:
        # gpu_providers table doesn't exist yet on a partially-migrated DB.
        return []
    return [dict(r) for r in rows]


def _fetch_candidates(conn: sqlite3.Connection) -> list[dict]:
    """Union of watch-list rows across `agents` (LLM candidates the operator
    doesn't have a key for) and `gpu_providers` (GPU providers not yet signed up).

    Normalized to a shared shape so the browser can render one table:
      - kind: "llm" | "gpu" — which source table
      - id: unique provider/model id
      - provider: vendor name
      - service_type: for LLM = agents.service_type (usually "llm"); for GPU =
        the SKU string (e.g. "H100 / on-demand")
      - price: unit-normalized cost — LLM = $/M-in ($/1M input tokens);
               GPU = $/hr
      - price_unit: "M-in" | "/hr" — so the UI can render with the right suffix
      - signup_trigger: hand-authored one-liner explaining WHY this vendor is
        on the watch-list (from AI_VENDOR_ACCESS notes / seed_watchlist_and_gpu)

    Sorted (kind, price) so LLM candidates come first (grouped), then GPU;
    within each kind, cheapest first.
    """
    out: list[dict] = []
    try:
        for r in conn.execute(
            "SELECT id, provider, service_type, "
            "COALESCE(cheapest_gateway_price, input_cost_per_m) AS price, "
            "signup_trigger, quality_tier "
            "FROM agents "
            "WHERE reachable_with_existing_keys=0 AND status='active'"
        ).fetchall():
            out.append(
                {
                    "kind": "llm",
                    "id": r[0],
                    "provider": r[1],
                    "service_type": r[2] or "",
                    "price": r[3],
                    "price_unit": "M-in",
                    "signup_trigger": r[4] or "",
                    "quality_tier": r[5],
                }
            )
    except sqlite3.OperationalError:
        # Column reachable_with_existing_keys may not exist on old DBs.
        pass
    try:
        for r in conn.execute(
            "SELECT id, provider, gpu_sku, tier, usd_per_hour, "
            "signup_trigger, cold_start_s "
            "FROM gpu_providers "
            "WHERE reachable_with_existing_keys=0"
        ).fetchall():
            sku = f"{r[2] or ''} / {r[3]}" if r[3] else (r[2] or "")
            out.append(
                {
                    "kind": "gpu",
                    "id": r[0],
                    "provider": r[1],
                    "service_type": sku,
                    "price": r[4],
                    "price_unit": "/hr",
                    "signup_trigger": r[5] or "",
                    "cold_start_s": r[6],
                }
            )
    except sqlite3.OperationalError:
        pass
    # NULL price handled at the sort key (treated as +inf).
    out.sort(
        key=lambda r: (
            0 if r["kind"] == "llm" else 1,
            r["price"] if r["price"] is not None else float("inf"),
            r["id"],
        )
    )
    return out


def _render_gpu_rows_html(gpu: list[dict]) -> str:
    """Server-side rendered rows for `<tbody id="rows-gpu">`. Simpler than
    JS-side rendering + sort is fixed to $/hr ascending (matches TAB_DEFAULTS).
    Users clicking column headers on the rent-gpu tab do NOT re-sort — a
    documented limitation of the follow-up.
    """
    if not gpu:
        return '<tr><td colspan=99 style="padding:16px;color:var(--muted)">No gpu_providers rows in this DB. Run seed_watchlist_and_gpu.py to seed the initial set.</td></tr>'
    lines: list[str] = []
    for r in gpu:
        reach = int(r.get("reachable_with_existing_keys") or 0)
        badge = (
            '<span class="reach-badge reach-yes" title="reachable — you have a key for this provider">✅</span>'
            if reach
            else '<span class="reach-badge reach-no" title="{sig}">❌</span>'.format(
                sig=(r.get("signup_trigger") or "signup required").replace('"', "&quot;")
            )
        )
        price = f"${r['usd_per_hour']:.4f}" if r.get("usd_per_hour") is not None else "—"
        cold = f"{r['cold_start_s']:.0f}s" if r.get("cold_start_s") is not None else "—"
        lines.append(
            f"<tr>"
            f"<td><b>{r.get('provider') or '—'}</b></td>"
            f"<td>{r.get('gpu_sku') or '—'}</td>"
            f"<td>{r.get('tier') or '—'}</td>"
            f'<td style="text-align:right">{price} /hr</td>'
            f"<td>{cold}</td>"
            f"<td>{badge}</td>"
            f'<td style="font-size:11px;color:var(--muted)">{(r.get("signup_trigger") or "").replace("<", "&lt;")}</td>'
            f"</tr>"
        )
    return "\n".join(lines)


def _render_candidates_rows_html(cands: list[dict]) -> str:
    """Server-side rendered rows for `<tbody id="rows-candidates">`. Union of
    LLM + GPU non-reachable rows — kind column distinguishes them.
    """
    if not cands:
        return '<tr><td colspan=99 style="padding:16px;color:var(--muted)">No candidate rows. Every accessible row already has reachable_with_existing_keys=1.</td></tr>'
    lines: list[str] = []
    for r in cands:
        price = f"${r['price']:.4f} {r['price_unit']}" if r.get("price") is not None else "—"
        kind_pill = (
            '<span style="background:#334;color:#eee;padding:1px 6px;border-radius:8px;font-size:10px">LLM</span>'
            if r["kind"] == "llm"
            else '<span style="background:#453;color:#eee;padding:1px 6px;border-radius:8px;font-size:10px">GPU</span>'
        )
        sig = (r.get("signup_trigger") or "").replace("<", "&lt;")
        lines.append(
            f"<tr>"
            f"<td>{kind_pill}</td>"
            f"<td><code>{r['id']}</code></td>"
            f"<td>{r.get('provider') or '—'}</td>"
            f"<td>{r.get('service_type') or '—'}</td>"
            f'<td style="text-align:right">{price}</td>'
            f'<td style="font-size:11px;color:var(--muted)">{sig}</td>'
            f"</tr>"
        )
    return "\n".join(lines)


def _build_payload(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        chat = _fetch_chat_models(conn, db_path)
        embed = _fetch_embedding_models(conn)
        gpu = _fetch_gpu_providers(conn)
        cands = _fetch_candidates(conn)
    finally:
        conn.close()

    # Provider list for the filter sidebar (sorted by row count).
    provider_counts: dict[str, int] = {}
    for m in chat + embed:
        provider_counts[m["provider"] or "(unknown)"] = (
            provider_counts.get(m["provider"] or "(unknown)", 0) + 1
        )
    providers = sorted(provider_counts.items(), key=lambda x: (-x[1], x[0]))

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "chat_models": chat,
        "embedding_models": embed,
        "gpu_providers": gpu,
        "candidates": cands,
        "providers": providers,
        "stats": {
            "chat_total": len(chat),
            "chat_active": sum(
                1 for m in chat if m.get("status") == "active" and not m.get("blocked")
            ),
            "chat_free": sum(
                1
                for m in chat
                if (m.get("input_cost_per_m") or 0) == 0 and m.get("status") == "active"
            ),
            "embedding_total": len(embed),
            "embedding_active": sum(
                1 for m in embed if m.get("status") == "active" and not m.get("blocked")
            ),
            "providers_total": len(providers),
            "gpu_total": len(gpu),
            "gpu_reachable": sum(1 for g in gpu if g.get("reachable_with_existing_keys")),
            "candidates_total": len(cands),
            "candidates_llm": sum(1 for c in cands if c["kind"] == "llm"),
            "candidates_gpu": sum(1 for c in cands if c["kind"] == "gpu"),
        },
    }


def render(db_path: Path = DB_PATH, output_path: Path = OUTPUT_PATH) -> Path:
    payload = _build_payload(db_path)
    # Pre-render the 2 new tbodies server-side (simpler than JS-side rendering).
    # Sort is fixed at doc-emit time (matches TAB_DEFAULTS entries in the template);
    # column-header re-sort on rent-gpu/candidates is out of scope for this pass.
    gpu_rows_html = _render_gpu_rows_html(payload["gpu_providers"])
    cands_rows_html = _render_candidates_rows_html(payload["candidates"])
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Embed JSON inside a <script type="application/json" id="data">…</script> tag
    # so the page is fully offline.
    embedded = (
        template.replace("<!--DATA_PLACEHOLDER-->", json.dumps(payload, default=str))
        .replace("<!--GPU_ROWS_PLACEHOLDER-->", gpu_rows_html)
        .replace("<!--CANDIDATES_ROWS_PLACEHOLDER-->", cands_rows_html)
    )
    output_path.write_text(embedded, encoding="utf-8")
    print(f"[export_models_browser] wrote {output_path}")
    print(
        f"[export_models_browser] {payload['stats']['chat_total']} chat models · "
        f"{payload['stats']['embedding_total']} embedding models · "
        f"{payload['stats']['gpu_total']} gpu providers · "
        f"{payload['stats']['candidates_total']} signup candidates · "
        f"{payload['stats']['providers_total']} providers"
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--open", action="store_true", help="xdg-open the result")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: {args.db} does not exist. Run kilo_agents_db.py first.", file=sys.stderr)
        sys.exit(1)
    if not TEMPLATE_PATH.exists():
        print(f"ERROR: {TEMPLATE_PATH} does not exist.", file=sys.stderr)
        sys.exit(1)

    out = render(args.db, args.output)
    if args.open:
        try:
            subprocess.run(["xdg-open", str(out)], check=False)
        except FileNotFoundError:
            print("xdg-open not available; open manually:", out)


if __name__ == "__main__":
    main()
