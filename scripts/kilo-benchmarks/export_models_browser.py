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


def _fetch_chat_models(conn: sqlite3.Connection) -> list[dict]:
    """Load every agents row + joined category list + today's role pins."""
    conn.row_factory = sqlite3.Row
    agents = [dict(r) for r in conn.execute("SELECT * FROM agents").fetchall()]

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
    return models


def _build_payload(db_path: Path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        chat = _fetch_chat_models(conn)
        embed = _fetch_embedding_models(conn)
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
        },
    }


def render(db_path: Path = DB_PATH, output_path: Path = OUTPUT_PATH) -> Path:
    payload = _build_payload(db_path)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Embed JSON inside a <script type="application/json" id="data">…</script> tag
    # so the page is fully offline.
    embedded = template.replace(
        "<!--DATA_PLACEHOLDER-->",
        json.dumps(payload, default=str),
    )
    output_path.write_text(embedded, encoding="utf-8")
    print(f"[export_models_browser] wrote {output_path}")
    print(
        f"[export_models_browser] {payload['stats']['chat_total']} chat models · "
        f"{payload['stats']['embedding_total']} embedding models · "
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
